"""Detalle de las vistas por modulo del dashboard (PDR seccion 6; diseno CC-10 y CC-24).

Los indicadores de cada modulo salen de /api/v1/kpis y /api/v1/estaciones (mismas cifras del
Resumen); estos endpoints solo dan el detalle que explica esas cifras, con la misma ventana de
30 dias que termina en la fecha de corte (ultimo dia de demanda_diaria):
  GET /api/v1/modulos/compras       tipo de cambio FIX (Banxico, real) y compras por proveedor
  GET /api/v1/modulos/inventarios   stock, demanda media y cobertura por almacen y SKU
  GET /api/v1/modulos/logistica     puntualidad por ruta y envios recientes con su clima real
  GET /api/v1/modulos/almacenes     utilizacion diaria por almacen y movimientos
  GET /api/v1/admin/usuarios        usuarios sin hash (solo lo llama el Servlet con rol ADMIN, CC-20)
Solo lectura; como toda la API, exige X-Token-Interno (CC-21).
"""
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter

from app.database import get_connection

router = APIRouter(prefix="/api/v1", tags=["Modulos"])

DATOS = Path(__file__).resolve().parents[1] / "etl" / "datos"
VOLUMEN_POR_SKU = json.loads((DATOS / "volumen_por_sku.json").read_text(encoding="utf-8"))
POLITICA = json.loads((DATOS / "config_simulacion.json").read_text(encoding="utf-8"))["politica_inventario"]
DIAS_VENTANA = 30
DIAS_SEGURIDAD = POLITICA["stock_seguridad_dias"]        # config_simulacion.json (12 dias)
DIAS_EXCESO = 75                                          # umbral de exceso de inventario (CC-19)
GRAVEDAD_CLIMA = {"DESPEJADO": 0, "LLUVIA": 1, "LLUVIA_FUERTE": 2, "TORMENTA": 3}


def _f(valor, decimales=2):
    return None if valor is None else round(float(valor), decimales)


def _ventana(cur):
    cur.execute("SELECT MAX(fecha) AS corte FROM demanda_diaria")
    corte = cur.fetchone()["corte"]
    return corte - timedelta(days=DIAS_VENTANA - 1), corte


def _meta(desde, corte, origen="SIMULADO"):
    return {"fecha_corte": corte.isoformat(), "desde": desde.isoformat(), "dias": DIAS_VENTANA, "origen": origen}


def _consultar(sql_y_parametros):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            return sql_y_parametros(cur)
    finally:
        conn.close()


# ---------------------------------------------------------------- compras

@router.get("/modulos/compras")
def compras():
    def leer(cur):
        desde, corte = _ventana(cur)
        cur.execute("""SELECT fecha, tasa FROM tipo_cambio
                       WHERE fuente = 'BANXICO_SIE' AND moneda_origen = 'USD' AND moneda_destino = 'MXN'
                       ORDER BY fecha""")
        fix = [{"fecha": f["fecha"].isoformat(), "tasa": _f(f["tasa"], 4)} for f in cur.fetchall()]
        cur.execute("""SELECT fecha, tasa FROM tipo_cambio
                       WHERE fuente = 'EXCHANGERATE_API' AND moneda_origen = 'USD' AND moneda_destino = 'MXN'
                       ORDER BY fecha DESC LIMIT 1""")
        diaria = cur.fetchone()
        cur.execute("""
            WITH renglones AS (
                SELECT o.orden_id, o.proveedor_id, o.fecha_orden, o.fecha_entrega_real,
                       d.cantidad, d.precio_unitario, p.costo_unitario,
                       (SELECT t.tasa FROM tipo_cambio t
                         WHERE t.fuente = 'BANXICO_SIE' AND t.moneda_origen = 'USD' AND t.moneda_destino = 'MXN'
                           AND t.fecha <= o.fecha_orden::date ORDER BY t.fecha DESC LIMIT 1) AS tc
                FROM ordenes_compra o
                JOIN detalle_orden_compra d ON d.orden_id = o.orden_id
                JOIN productos p ON p.producto_id = d.producto_id
                WHERE o.fecha_orden::date BETWEEN %s AND %s
            )
            SELECT pr.proveedor_id, pr.nombre, pr.pais,
                   COUNT(DISTINCT r.orden_id) AS ordenes,
                   SUM(r.cantidad) AS unidades,
                   SUM(r.cantidad * r.precio_unitario) AS monto_usd,
                   SUM(r.cantidad * r.precio_unitario * r.tc) AS monto_mxn,
                   SUM((r.precio_unitario - r.costo_unitario) * r.cantidad)
                       / NULLIF(SUM(r.costo_unitario * r.cantidad), 0) * 100 AS variacion_costo_pct,
                   COUNT(DISTINCT r.orden_id) FILTER (WHERE r.fecha_entrega_real IS NULL) AS en_transito
            FROM renglones r JOIN proveedores pr ON pr.proveedor_id = r.proveedor_id
            GROUP BY pr.proveedor_id, pr.nombre, pr.pais
            ORDER BY monto_mxn DESC NULLS LAST
        """, (desde, corte))
        filas = cur.fetchall()
        return desde, corte, fix, diaria, filas

    desde, corte, fix, diaria, filas = _consultar(leer)
    total = sum(float(f["monto_mxn"] or 0) for f in filas)
    proveedores = [{
        "proveedor_id": f["proveedor_id"], "nombre": f["nombre"], "pais": f["pais"],
        "ordenes": f["ordenes"], "en_transito": f["en_transito"], "unidades": int(f["unidades"] or 0),
        "monto_usd": _f(f["monto_usd"]), "monto_mxn": _f(f["monto_mxn"]),
        "participacion_pct": _f(100 * float(f["monto_mxn"] or 0) / total, 1) if total else None,
        "variacion_costo_pct": _f(f["variacion_costo_pct"]),
    } for f in filas]
    return {**_meta(desde, corte, "SIMULADO Y REAL"),
            "tipo_cambio": {"fuente": "Banxico SIE, FIX (serie SF43718)", "serie": fix,
                            "diaria": None if diaria is None else
                            {"fecha": diaria["fecha"].isoformat(), "tasa": _f(diaria["tasa"], 4),
                             "fuente": "ExchangeRate-API"}},
            "compras_mxn": _f(total), "proveedores": proveedores}


# ---------------------------------------------------------------- inventarios

def _estado_cobertura(stock, cobertura):
    if stock <= 0:
        return "SIN_STOCK"
    if cobertura is not None and cobertura < DIAS_SEGURIDAD:
        return "BAJO"
    if cobertura is not None and cobertura > DIAS_EXCESO:
        return "EXCESO"
    return "NORMAL"


@router.get("/modulos/inventarios")
def inventarios():
    ventana_demanda = POLITICA["ventana_demanda_media_dias"]

    def leer(cur):
        desde, corte = _ventana(cur)
        cur.execute("""
            WITH stock AS (
                SELECT almacen_id, producto_id,
                       SUM(CASE WHEN tipo_movimiento = 'ENTRADA' THEN cantidad ELSE -cantidad END) AS unidades
                FROM movimientos_inventario WHERE fecha::date <= %s GROUP BY almacen_id, producto_id),
            demanda AS (
                SELECT almacen_id, producto_id, AVG(unidades_solicitadas) AS media
                FROM demanda_diaria WHERE fecha > %s AND fecha <= %s GROUP BY almacen_id, producto_id),
            transito AS (
                SELECT e.almacen_origen_id AS almacen_id, d.producto_id, SUM(d.cantidad) AS unidades
                FROM ordenes_compra o JOIN envios e ON e.orden_id = o.orden_id
                JOIN detalle_orden_compra d ON d.orden_id = o.orden_id
                WHERE o.fecha_entrega_real IS NULL GROUP BY e.almacen_origen_id, d.producto_id)
            SELECT a.almacen_id, a.nombre AS almacen, p.producto_id, p.sku, p.nombre AS producto,
                   COALESCE(s.unidades, 0) AS stock, COALESCE(dm.media, 0) AS demanda_media,
                   COALESCE(t.unidades, 0) AS en_transito
            FROM almacenes a CROSS JOIN productos p
            LEFT JOIN stock s ON s.almacen_id = a.almacen_id AND s.producto_id = p.producto_id
            LEFT JOIN demanda dm ON dm.almacen_id = a.almacen_id AND dm.producto_id = p.producto_id
            LEFT JOIN transito t ON t.almacen_id = a.almacen_id AND t.producto_id = p.producto_id
            WHERE dm.media IS NOT NULL OR s.unidades IS NOT NULL
            ORDER BY p.nombre, a.nombre
        """, (corte, corte - timedelta(days=ventana_demanda), corte))
        return desde, corte, cur.fetchall()

    desde, corte, filas = _consultar(leer)
    detalle, red = [], defaultdict(lambda: {"stock": 0.0, "demanda": 0.0, "transito": 0.0})
    for f in filas:
        stock, media = float(f["stock"]), float(f["demanda_media"])
        cobertura = stock / media if media > 0 else None
        detalle.append({"almacen": f["almacen"], "sku": f["sku"], "producto": f["producto"],
                        "stock": int(stock), "demanda_media_diaria": _f(media, 1),
                        "en_transito": int(f["en_transito"]), "cobertura_dias": _f(cobertura, 1),
                        "estado": _estado_cobertura(stock, cobertura)})
        r = red[(f["sku"], f["producto"])]
        r["stock"] += stock
        r["demanda"] += media
        r["transito"] += float(f["en_transito"])
    por_sku = []
    for (sku, producto), r in red.items():
        cobertura = r["stock"] / r["demanda"] if r["demanda"] > 0 else None
        por_sku.append({"sku": sku, "producto": producto, "stock": int(r["stock"]),
                        "demanda_media_diaria": _f(r["demanda"], 1), "en_transito": int(r["transito"]),
                        "cobertura_dias": _f(cobertura, 1), "estado": _estado_cobertura(r["stock"], cobertura)})
    por_sku.sort(key=lambda x: (x["cobertura_dias"] is None, x["cobertura_dias"] or 0))
    return {**_meta(desde, corte), "umbral_seguridad_dias": DIAS_SEGURIDAD, "umbral_exceso_dias": DIAS_EXCESO,
            "ventana_demanda_dias": ventana_demanda, "por_sku": por_sku, "detalle": detalle}


# ---------------------------------------------------------------- logistica

@router.get("/modulos/logistica")
def logistica():
    def leer(cur):
        desde, corte = _ventana(cur)
        cur.execute("""
            SELECT pr.nombre AS proveedor, a.nombre AS almacen, COUNT(*) AS envios,
                   COUNT(*) FILTER (WHERE e.fecha_llegada_real::date <= e.fecha_llegada_estim::date) AS a_tiempo,
                   AVG(GREATEST(0, e.fecha_llegada_real::date - e.fecha_llegada_estim::date)) AS retraso_promedio,
                   AVG(e.costo_flete) AS flete_promedio,
                   COUNT(*) FILTER (WHERE e.condicion_climatica IN ('LLUVIA_FUERTE', 'TORMENTA')) AS con_clima_severo
            FROM envios e JOIN proveedores pr ON pr.proveedor_id = e.proveedor_id
            JOIN almacenes a ON a.almacen_id = e.almacen_origen_id
            WHERE e.fecha_llegada_real::date BETWEEN %s AND %s
            GROUP BY pr.nombre, a.nombre ORDER BY pr.nombre, a.nombre
        """, (desde, corte))
        rutas = cur.fetchall()
        cur.execute("""
            (SELECT e.envio_id, pr.nombre AS proveedor, a.nombre AS almacen, e.fecha_salida, e.fecha_llegada_estim,
                    NULL::timestamp AS fecha_llegada_real, e.condicion_climatica, e.precipitacion_mm, e.costo_flete
             FROM envios e JOIN proveedores pr ON pr.proveedor_id = e.proveedor_id
             JOIN almacenes a ON a.almacen_id = e.almacen_origen_id
             WHERE e.fecha_llegada_real IS NULL ORDER BY e.fecha_llegada_estim LIMIT 25)
            UNION ALL
            (SELECT e.envio_id, pr.nombre, a.nombre, e.fecha_salida, e.fecha_llegada_estim,
                    e.fecha_llegada_real, e.condicion_climatica, e.precipitacion_mm, e.costo_flete
             FROM envios e JOIN proveedores pr ON pr.proveedor_id = e.proveedor_id
             JOIN almacenes a ON a.almacen_id = e.almacen_origen_id
             WHERE e.fecha_llegada_real::date <= %s ORDER BY e.fecha_llegada_real DESC LIMIT 15)
        """, (corte,))
        return desde, corte, rutas, cur.fetchall()

    desde, corte, rutas, envios = _consultar(leer)
    lista_rutas = [{"proveedor": r["proveedor"], "almacen": r["almacen"], "envios": r["envios"],
                    "a_tiempo_pct": _f(100 * r["a_tiempo"] / r["envios"], 1) if r["envios"] else None,
                    "retraso_promedio_dias": _f(r["retraso_promedio"], 1),
                    "flete_promedio_mxn": _f(r["flete_promedio"]), "con_clima_severo": r["con_clima_severo"]}
                   for r in rutas]
    lista_envios = [_envio(e, corte) for e in envios]
    return {**_meta(desde, corte, "SIMULADO Y REAL"),
            "aviso_clima": "Clima real de Open-Meteo en el punto de despacho y en el almacen (CC-04, CC-22)",
            "rutas": lista_rutas, "envios": lista_envios}


def _envio(e, corte):
    """Estado del envio a la fecha de corte y su clima sin inventar dias sin dato.

    Un envio en transito cuya llegada estimada ya paso se marca ATRASADO. El clima de la ruta
    solo existe hasta la fecha de corte (historico de Open-Meteo); si la ruta sigue despues del
    corte, el clima es parcial, y si no hubo dato en ningun dia se reporta sin dato en lugar de
    DESPEJADO con 0 mm (datos confiables y trazables, CC-04 y CC-22).
    """
    estim = e["fecha_llegada_estim"].date()
    real = e["fecha_llegada_real"].date() if e["fecha_llegada_real"] else None
    if real is None:
        dias_tarde = max(0, (corte - estim).days)
        estado = "ATRASADO" if dias_tarde > 0 else "EN_TRANSITO"
    else:
        dias_tarde = max(0, (real - estim).days)
        estado = "TARDIO" if dias_tarde > 0 else "A_TIEMPO"
    condicion, mm = e["condicion_climatica"], _f(e["precipitacion_mm"], 1)
    clima_parcial = real is None and estim > corte
    if clima_parcial and condicion == "DESPEJADO" and not mm:
        condicion, mm = None, None
    return {
        "envio_id": e["envio_id"], "proveedor": e["proveedor"], "almacen": e["almacen"],
        "salida": e["fecha_salida"].date().isoformat() if e["fecha_salida"] else None,
        "llegada_estimada": estim.isoformat(), "llegada_real": real.isoformat() if real else None,
        "estado": estado, "dias_tarde": dias_tarde if estado in ("TARDIO", "ATRASADO") else None,
        "condicion_climatica": condicion, "precipitacion_mm": mm, "clima_parcial": clima_parcial,
        "costo_flete_mxn": _f(e["costo_flete"])}


# ---------------------------------------------------------------- almacenes

@router.get("/modulos/almacenes")
def almacenes():
    def leer(cur):
        desde, corte = _ventana(cur)
        cur.execute("SELECT almacen_id, nombre, capacidad_m3 FROM almacenes ORDER BY almacen_id")
        lista = cur.fetchall()
        cur.execute("SELECT producto_id, sku FROM productos")
        skus = {f["producto_id"]: f["sku"] for f in cur.fetchall()}
        cur.execute("""SELECT almacen_id, producto_id,
                              SUM(CASE WHEN tipo_movimiento = 'ENTRADA' THEN cantidad ELSE -cantidad END) AS unidades
                       FROM movimientos_inventario WHERE fecha::date < %s
                       GROUP BY almacen_id, producto_id""", (desde,))
        inicial = cur.fetchall()
        cur.execute("""SELECT fecha::date AS dia, almacen_id, producto_id, tipo_movimiento, SUM(cantidad) AS unidades
                       FROM movimientos_inventario WHERE fecha::date BETWEEN %s AND %s
                       GROUP BY fecha::date, almacen_id, producto_id, tipo_movimiento""", (desde, corte))
        return desde, corte, lista, skus, inicial, cur.fetchall()

    desde, corte, lista, skus, inicial, movimientos = _consultar(leer)
    m3 = {a["almacen_id"]: 0.0 for a in lista}
    for f in inicial:
        m3[f["almacen_id"]] += float(f["unidades"]) * VOLUMEN_POR_SKU.get(skus[f["producto_id"]], 0.0)
    por_dia = defaultdict(list)
    entradas, salidas = defaultdict(float), defaultdict(float)
    for f in movimientos:
        por_dia[f["dia"]].append(f)
        (entradas if f["tipo_movimiento"] == "ENTRADA" else salidas)[f["almacen_id"]] += float(f["unidades"])
    series = {a["almacen_id"]: [] for a in lista}
    dia = desde
    while dia <= corte:
        for f in por_dia.get(dia, []):
            signo = 1 if f["tipo_movimiento"] == "ENTRADA" else -1
            m3[f["almacen_id"]] += signo * float(f["unidades"]) * VOLUMEN_POR_SKU.get(skus[f["producto_id"]], 0.0)
        for a in lista:
            series[a["almacen_id"]].append({"fecha": dia.isoformat(),
                                            "utilizacion_pct": _f(100 * m3[a["almacen_id"]] / float(a["capacidad_m3"]), 1)})
        dia += timedelta(days=1)
    resultado = []
    for a in lista:
        serie = series[a["almacen_id"]]
        valores = [p["utilizacion_pct"] for p in serie]
        resultado.append({"almacen_id": a["almacen_id"], "nombre": a["nombre"], "capacidad_m3": _f(a["capacidad_m3"], 1),
                          "utilizacion_al_corte_pct": valores[-1] if valores else None,
                          "utilizacion_promedio_pct": _f(sum(valores) / len(valores), 1) if valores else None,
                          "utilizacion_maxima_pct": max(valores) if valores else None,
                          "entradas_unidades": int(entradas[a["almacen_id"]]),
                          "salidas_unidades": int(salidas[a["almacen_id"]]), "serie": serie})
    return {**_meta(desde, corte), "maximo_pct": 85.0, "almacenes": resultado}


# ---------------------------------------------------------------- administracion

@router.get("/admin/usuarios")
def usuarios():
    """Lista de usuarios sin ningun dato de la contrasena (CC-20). El rol ADMIN lo valida el Servlet."""
    def leer(cur):
        cur.execute("SELECT * FROM usuarios ORDER BY usuario")
        return cur.fetchall()

    lista = []
    for f in _consultar(leer):
        u = {}
        for k, v in dict(f).items():
            if "hash" in k or "contrasena" in k or "password" in k:
                continue
            if isinstance(v, datetime):
                v = v.isoformat(timespec="minutes")
            elif isinstance(v, date):
                v = v.isoformat()
            u[k] = v
        lista.append(u)
    return {"usuarios": lista,
            "aviso": "Alta, restablecimiento y baja de usuarios con python -m admin.crear_usuario (CC-20)"}