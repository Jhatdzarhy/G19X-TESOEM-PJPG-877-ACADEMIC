"""Motor de KPIs del dashboard (PDR seccion 7) sobre supply_chain_final.

Endpoints (prefijo /api/v1):
  GET /kpis?dias=30        los 11 KPIs del PDR en la ventana que termina en la fecha de corte
  GET /estaciones?dias=30  las 5 estaciones del Resumen ejecutivo (CC-10): KPI principal,
                           meta, estado, dato secundario, variacion contra la ventana anterior
                           y serie diaria para la minigrafica

Definiciones:
  - Fecha de corte: ultimo dia con datos en demanda_diaria (el "hoy" del dashboard).
  - Ventana: los `dias` dias que terminan en la fecha de corte; la serie de cada estacion
    calcula el mismo KPI con una ventana movil del mismo largo para cada dia.
  - Formulas de CC-05 (Fill Rate) y CC-15 (variacion de costo, rotacion, DOH e impacto de
    tipo de cambio); tipo de cambio FIX vigente de Banxico SIE (CC-03).
  - Metas y umbrales de estado en METAS (CC-16). Estados: EN_META, ATENCION, CRITICO,
    INFORMATIVO (sin meta) y SIN_DATOS.
  - Indice de riesgo y MAPE los calcula el motor de IA (CC-07); aqui se devuelven como
    SIN_DATOS hasta que existan sus resultados.

Rendimiento: 5 consultas agregadas por dia para todo el rango; las ventanas se suman en
Python, sin una consulta por punto de la serie.
"""
import json
from bisect import bisect_right
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.database import get_connection

router = APIRouter(prefix="/api/v1", tags=["KPIs"])

VOLUMEN_POR_SKU = json.loads(
    (Path(__file__).resolve().parents[1] / "etl" / "datos" / "volumen_por_sku.json").read_text(encoding="utf-8")
)

# CC-16: meta y umbral critico de cada KPI.
#   sentido "mayor": EN_META si valor >= meta; ATENCION si >= critico; CRITICO si menor.
#   sentido "menor": EN_META si valor <= meta; ATENCION si <= critico; CRITICO si mayor.
METAS = {
    "otif":                 {"meta": 90.0, "critico": 80.0, "sentido": "mayor"},
    "entregas_a_tiempo":    {"meta": 90.0, "critico": 85.0, "sentido": "mayor"},
    "lead_time":            {"meta": 7.0,  "critico": 9.0,  "sentido": "menor"},
    "variacion_costo":      {"meta": 2.0,  "critico": 5.0,  "sentido": "menor"},
    "fill_rate":            {"meta": 95.0, "critico": 90.0, "sentido": "mayor"},
    "rotacion":             {"meta": 6.0,  "critico": 4.0,  "sentido": "mayor"},
    "utilizacion":          {"meta": 85.0, "critico": 95.0, "sentido": "menor"},
    "mape":                 {"meta": 15.0, "critico": 25.0, "sentido": "menor"},
    "riesgo_proveedores":   {"meta": 40.0, "critico": 60.0, "sentido": "menor"},
}


# ---------------------------------------------------------------- utilidades

def _estado(clave, valor):
    if valor is None:
        return "SIN_DATOS"
    m = METAS.get(clave)
    if m is None:
        return "INFORMATIVO"
    if m["sentido"] == "mayor":
        return "EN_META" if valor >= m["meta"] else "ATENCION" if valor >= m["critico"] else "CRITICO"
    return "EN_META" if valor <= m["meta"] else "ATENCION" if valor <= m["critico"] else "CRITICO"


def _r(valor, decimales=2):
    return None if valor is None else round(float(valor), decimales)


def _div(a, b):
    return None if not b else a / b


def _dias(desde, hasta):
    d = desde
    while d <= hasta:
        yield d
        d += timedelta(days=1)


# ---------------------------------------------------------------- lectura de datos

def _fecha_corte(cur):
    cur.execute("SELECT MAX(fecha) AS corte FROM demanda_diaria")
    corte = cur.fetchone()["corte"]
    if corte is None:
        raise HTTPException(status_code=503, detail="No hay datos operativos cargados")
    return corte


def _leer_insumos(cur, desde, hasta):
    """Agregados diarios del rango [desde, hasta]; todo lo demas se calcula en memoria."""
    ins = {"desde": desde, "hasta": hasta}

    cur.execute("""
        SELECT fecha AS dia, SUM(unidades_solicitadas) AS solicitadas, SUM(unidades_entregadas) AS entregadas
        FROM demanda_diaria WHERE fecha BETWEEN %s AND %s GROUP BY fecha
    """, (desde, hasta))
    ins["demanda"] = {r["dia"]: r for r in cur.fetchall()}

    cur.execute("""
        SELECT m.fecha::date AS dia, SUM(m.cantidad * p.costo_unitario) AS cogs_usd
        FROM movimientos_inventario m JOIN productos p ON p.producto_id = m.producto_id
        WHERE m.tipo_movimiento = 'SALIDA' AND m.fecha::date BETWEEN %s AND %s
        GROUP BY 1
    """, (desde, hasta))
    ins["cogs"] = {r["dia"]: float(r["cogs_usd"]) for r in cur.fetchall()}

    # recepciones: un registro por envio recibido (OTIF, a tiempo, lead time, flete)
    cur.execute("""
        SELECT e.fecha_llegada_real::date AS dia,
               COUNT(*) AS envios,
               SUM(EXTRACT(EPOCH FROM (o.fecha_entrega_real - o.fecha_orden)) / 86400) AS lead_time_suma,
               COUNT(*) FILTER (WHERE e.fecha_llegada_real::date <= e.fecha_llegada_estim::date) AS a_tiempo,
               COUNT(*) FILTER (WHERE e.fecha_llegada_real::date <= e.fecha_llegada_estim::date
                                AND NOT EXISTS (SELECT 1 FROM detalle_orden_compra x
                                                WHERE x.orden_id = e.orden_id
                                                  AND x.cantidad_recibida < x.cantidad)) AS otif,
               SUM(e.costo_flete) AS flete_mxn,
               SUM((SELECT SUM(d.cantidad_recibida) FROM detalle_orden_compra d
                    WHERE d.orden_id = e.orden_id)) AS unidades
        FROM envios e JOIN ordenes_compra o ON o.orden_id = e.orden_id
        WHERE e.fecha_llegada_real::date BETWEEN %s AND %s
        GROUP BY 1
    """, (desde, hasta))
    ins["recepciones"] = {r["dia"]: r for r in cur.fetchall()}

    # compras por fecha de orden (variacion de costo e impacto de tipo de cambio)
    cur.execute("""
        SELECT o.fecha_orden::date AS dia,
               SUM(d.cantidad * d.precio_unitario) AS real_usd,
               SUM(d.cantidad * p.costo_unitario)  AS estandar_usd
        FROM ordenes_compra o
        JOIN detalle_orden_compra d ON d.orden_id = o.orden_id
        JOIN productos p ON p.producto_id = d.producto_id
        WHERE o.fecha_orden::date BETWEEN %s AND %s
        GROUP BY 1
    """, (desde, hasta))
    ins["compras"] = {r["dia"]: r for r in cur.fetchall()}

    cur.execute("""
        SELECT fecha, tasa FROM tipo_cambio
        WHERE fuente = 'BANXICO_SIE' AND moneda_origen = 'USD' AND moneda_destino = 'MXN'
        ORDER BY fecha
    """)
    filas = cur.fetchall()
    ins["fix_fechas"] = [r["fecha"] for r in filas]
    ins["fix_tasas"] = [float(r["tasa"]) for r in filas]

    # stock al cierre de cada dia por almacen y producto (rotacion, DOH y utilizacion)
    cur.execute("""
        WITH neto AS (
            SELECT almacen_id, producto_id, fecha::date AS f,
                   SUM(CASE WHEN tipo_movimiento = 'ENTRADA' THEN cantidad ELSE -cantidad END) AS neto
            FROM movimientos_inventario GROUP BY 1, 2, 3
        ),
        pares AS (SELECT DISTINCT almacen_id, producto_id FROM neto),
        inicial AS (SELECT almacen_id, producto_id, SUM(neto) AS s FROM neto WHERE f < %s GROUP BY 1, 2),
        rejilla AS (
            SELECT pa.almacen_id, pa.producto_id, g::date AS dia
            FROM pares pa, generate_series(%s::date, %s::date, INTERVAL '1 day') g
        )
        SELECT r.dia, r.almacen_id, p.sku, p.costo_unitario,
               COALESCE(i.s, 0) + SUM(COALESCE(n.neto, 0))
                   OVER (PARTITION BY r.almacen_id, r.producto_id ORDER BY r.dia) AS stock
        FROM rejilla r
        JOIN productos p ON p.producto_id = r.producto_id
        LEFT JOIN neto n ON n.almacen_id = r.almacen_id AND n.producto_id = r.producto_id AND n.f = r.dia
        LEFT JOIN inicial i ON i.almacen_id = r.almacen_id AND i.producto_id = r.producto_id
    """, (desde, desde, hasta))
    valor_inv, m3 = {}, {}
    for r in cur.fetchall():
        stock = float(r["stock"])
        valor_inv[r["dia"]] = valor_inv.get(r["dia"], 0.0) + stock * float(r["costo_unitario"])
        clave = (r["dia"], r["almacen_id"])
        m3[clave] = m3.get(clave, 0.0) + stock * VOLUMEN_POR_SKU.get(r["sku"], 0.0)
    ins["valor_inv"], ins["m3"] = valor_inv, m3

    cur.execute("SELECT almacen_id, nombre, capacidad_m3 FROM almacenes ORDER BY almacen_id")
    ins["almacenes"] = [dict(r) for r in cur.fetchall()]
    return ins


def _fix_vigente(ins, dia):
    """FIX publicado en o antes del dia (fines de semana y festivos: dia habil anterior, CC-03)."""
    i = bisect_right(ins["fix_fechas"], dia) - 1
    return ins["fix_tasas"][i] if i >= 0 else None


# ---------------------------------------------------------------- calculo por ventana

def _calcular(ins, desde, hasta):
    dias = list(_dias(desde, hasta))
    n = len(dias)

    def suma(tabla, campo):
        return sum(float(ins[tabla][d][campo] or 0) for d in dias if d in ins[tabla])

    k = {}
    envios = suma("recepciones", "envios")
    k["lead_time"] = _div(suma("recepciones", "lead_time_suma"), envios)
    k["otif"] = None if not envios else 100 * suma("recepciones", "otif") / envios
    k["entregas_a_tiempo"] = None if not envios else 100 * suma("recepciones", "a_tiempo") / envios
    k["costo_transporte_unidad"] = _div(suma("recepciones", "flete_mxn"), suma("recepciones", "unidades"))

    estandar = suma("compras", "estandar_usd")
    k["variacion_costo"] = None if not estandar else 100 * (suma("compras", "real_usd") / estandar - 1)

    solicitadas = suma("demanda", "solicitadas")
    k["fill_rate"] = None if not solicitadas else 100 * suma("demanda", "entregadas") / solicitadas

    cogs = sum(ins["cogs"].get(d, 0.0) for d in dias)
    inv_prom = sum(ins["valor_inv"].get(d, 0.0) for d in dias) / n
    k["rotacion"] = None if not inv_prom else cogs / inv_prom * 365.0 / n
    k["doh"] = _div(inv_prom, cogs / n)

    cap_total = sum(float(a["capacidad_m3"]) for a in ins["almacenes"])
    por_almacen = {}
    for a in ins["almacenes"]:
        cap = float(a["capacidad_m3"])
        por_almacen[a["nombre"]] = {
            "promedio": 100 * sum(ins["m3"].get((d, a["almacen_id"]), 0.0) for d in dias) / n / cap,
            "al_corte": 100 * ins["m3"].get((hasta, a["almacen_id"]), 0.0) / cap,
        }
    k["utilizacion"] = 100 * sum(ins["m3"].get((d, a["almacen_id"]), 0.0)
                                 for d in dias for a in ins["almacenes"]) / n / cap_total
    k["utilizacion_por_almacen"] = por_almacen

    # impacto de tipo de cambio (CC-15): compras al FIX de cada orden menos al FIX del inicio
    tc_inicio = _fix_vigente(ins, desde)
    real_usd_tc = sum(float(ins["compras"][d]["real_usd"]) * (_fix_vigente(ins, d) or 0)
                      for d in dias if d in ins["compras"])
    real_usd = suma("compras", "real_usd")
    if tc_inicio and real_usd:
        k["impacto_tc_mxn"] = real_usd_tc - real_usd * tc_inicio
        k["impacto_tc_pct"] = 100 * (real_usd_tc / (real_usd * tc_inicio) - 1)
    else:
        k["impacto_tc_mxn"] = k["impacto_tc_pct"] = None
    k["fix_inicio"], k["fix_corte"] = tc_inicio, _fix_vigente(ins, hasta)
    return k


def _kpi(clave, nombre, categoria, valor, unidad, fuentes, origen="SIMULADO", decimales=2, detalle=None, clave_meta=None):
    meta = METAS.get(clave_meta or clave)
    return {
        "clave": clave, "nombre": nombre, "categoria": categoria,
        "valor": _r(valor, decimales), "unidad": unidad,
        "meta": meta["meta"] if meta else None,
        "umbral_critico": meta["critico"] if meta else None,
        "sentido": meta["sentido"] if meta else None,
        "estado": _estado(clave_meta or clave, valor),
        "origen": origen, "fuentes": fuentes, "detalle": detalle,
    }


def _contexto(dias):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            corte = _fecha_corte(cur)
            ins = _leer_insumos(cur, corte - timedelta(days=2 * dias - 1), corte)
    finally:
        conn.close()
    return corte, ins


def _meta_respuesta(corte, dias):
    return {
        "fecha_corte": corte.isoformat(),
        "desde": (corte - timedelta(days=dias - 1)).isoformat(),
        "dias": dias,
        "generado": datetime.now().isoformat(timespec="seconds"),
        "aviso": "Datos operativos simulados; tipo de cambio real de Banxico SIE",
    }


# ---------------------------------------------------------------- endpoints

@router.get("/kpis")
def kpis(dias: int = Query(30, ge=7, le=180, description="Largo de la ventana en dias")):
    corte, ins = _contexto(dias)
    k = _calcular(ins, corte - timedelta(days=dias - 1), corte)
    lista = [
        _kpi("lead_time", "Lead time de proveedor", "Compras", k["lead_time"], "dias",
             ["ordenes_compra"]),
        _kpi("variacion_costo", "Variacion de costo de compra", "Compras", k["variacion_costo"], "%",
             ["detalle_orden_compra", "productos"], detalle="Contra el costo estandar del catalogo (CC-15)"),
        _kpi("rotacion", "Rotacion de inventario", "Inventario", k["rotacion"], "veces al ano",
             ["movimientos_inventario", "productos"]),
        _kpi("fill_rate", "Nivel de servicio (Fill Rate)", "Inventario", k["fill_rate"], "%",
             ["demanda_diaria"], detalle="Fill Rate de servicio (CC-05)"),
        _kpi("doh", "Dias de inventario disponible", "Inventario", k["doh"], "dias",
             ["movimientos_inventario", "productos"], decimales=1),
        _kpi("otif", "OTIF", "Logistica", k["otif"], "%",
             ["envios", "detalle_orden_compra"]),
        _kpi("costo_transporte_unidad", "Costo de transporte por unidad", "Logistica",
             k["costo_transporte_unidad"], "MXN", ["envios", "detalle_orden_compra"]),
        _kpi("utilizacion", "Utilizacion de almacen", "Almacen", k["utilizacion"], "%",
             ["movimientos_inventario", "almacenes", "volumen_por_sku.json"], decimales=1,
             detalle={n: {"promedio": _r(v["promedio"], 1), "al_corte": _r(v["al_corte"], 1)}
                      for n, v in k["utilizacion_por_almacen"].items()}),
        _kpi("riesgo_proveedores", "Indice de riesgo de proveedor", "Proveedores", None, "0 a 100",
             ["fact_supply_chain"], detalle="Lo calcula el motor de IA (CC-07)"),
        _kpi("mape", "Precision del pronostico (MAPE)", "IA / Predictivo", None, "%",
             ["forecast_demanda"], detalle="Lo calcula el motor de IA (CC-07)"),
        _kpi("impacto_tc", "Impacto de tipo de cambio", "Financiero", k["impacto_tc_mxn"], "MXN",
             ["ordenes_compra", "tipo_cambio (Banxico SIE)"], origen="SIMULADO Y REAL", decimales=0,
             detalle={"variacion_pct": _r(k["impacto_tc_pct"]), "fix_inicio": _r(k["fix_inicio"], 4),
                      "fix_corte": _r(k["fix_corte"], 4)}),
    ]
    return {**_meta_respuesta(corte, dias), "kpis": lista}


ESTACIONES = [
    # clave, nombre, modulo, kpi principal, etiqueta, unidad
    ("proveedores", "Proveedores", "proveedores", "otif", "OTIF", "%"),
    ("compras", "Compras", "compras", "lead_time", "Lead time", "dias"),
    ("transporte", "Transporte", "logistica", "entregas_a_tiempo", "A tiempo", "%"),
    ("almacenes", "Almacenes", "almacenes", "utilizacion", "Utilizacion", "%"),
    ("inventario", "Inventario", "inventarios", "fill_rate", "Fill rate", "%"),
]


def _secundario(clave, k):
    if clave == "proveedores":
        return None
    if clave == "compras":
        return {"etiqueta": "Variacion de costo", "valor": _r(k["variacion_costo"]), "unidad": "%"}
    if clave == "transporte":
        return {"etiqueta": "Flete por unidad", "valor": _r(k["costo_transporte_unidad"]), "unidad": "MXN"}
    if clave == "almacenes":
        nombre, v = max(k["utilizacion_por_almacen"].items(), key=lambda x: x[1]["al_corte"])
        return {"etiqueta": nombre + " al corte", "valor": _r(v["al_corte"], 1), "unidad": "%"}
    return {"etiqueta": "Rotacion y dias de inventario",
            "valor": _r(k["rotacion"], 1), "unidad": "veces", "doh": _r(k["doh"], 0)}


@router.get("/estaciones")
def estaciones(dias: int = Query(30, ge=7, le=90, description="Largo de la ventana en dias")):
    corte, ins = _contexto(dias)
    desde = corte - timedelta(days=dias - 1)
    actual = _calcular(ins, desde, corte)
    anterior = _calcular(ins, desde - timedelta(days=dias), desde - timedelta(days=1))
    series = {d: _calcular(ins, d - timedelta(days=dias - 1), d) for d in _dias(desde, corte)}

    resultado = []
    for clave, nombre, modulo, kpi, etiqueta, unidad in ESTACIONES:
        valor, previo = actual[kpi], anterior[kpi]
        meta = METAS[kpi]
        resultado.append({
            "clave": clave, "nombre": nombre, "modulo": modulo,
            "kpi": kpi, "etiqueta": etiqueta, "unidad": unidad,
            "valor": _r(valor, 1), "meta": meta["meta"], "umbral_critico": meta["critico"],
            "sentido": meta["sentido"], "estado": _estado(kpi, valor),
            "variacion_vs_anterior": None if valor is None or previo is None else _r(valor - previo, 1),
            "secundario": _secundario(clave, actual),
            "serie": [{"fecha": d.isoformat(), "valor": _r(v[kpi], 1)} for d, v in series.items()],
        })
    return {**_meta_respuesta(corte, dias), "estaciones": resultado}