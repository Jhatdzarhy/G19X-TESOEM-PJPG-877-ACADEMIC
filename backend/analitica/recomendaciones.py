"""Motor de recomendaciones del Centro de soluciones (CC-01, CC-07, supuestos en CC-19).

Cada regla detecta un problema a la fecha de corte, arma 2 o 3 opciones y las compara por
COSTO TOTAL ESPERADO en MXN:

    costo total esperado = costo directo de la opcion + probabilidad de falla x costo de la falla

La opcion de menor costo es la recomendada; el impacto estimado es lo que se evita contra
no actuar (costo de "sin accion" menos costo de la recomendada). La IA solo recomienda: la
decision y la ejecucion son humanas (PDR seccion 2); los estados los cambian personas desde
el Centro de soluciones.

Reglas:
  QUIEBRE_PROYECTADO    INVENTARIOS  stock + llegadas en transito contra el pronostico de 14 dias
  EXCESO_INVENTARIO     INVENTARIOS  cobertura mayor a SUPUESTOS["exceso_cobertura_dias"]
  RETRASOS_PROVEEDOR    PROVEEDORES  puntualidad de 30 dias bajo el umbral y peor que la de 90
  ALZA_PRECIO           COMPRAS      precio de 30 dias contra la mediana de los 90 previos (con
                                     la senal de Isolation Forest como evidencia)
  CLIMA_RUTA            LOGISTICA    envios en transito por rutas con lluvia fuerte o tormenta
                                     reciente (clima real de Open-Meteo, CC-04)
  CONCENTRACION_GASTO   PROVEEDORES  participacion en compras de 90 dias sobre el umbral

Entradas: modelo de datos (CC-02), pronostico por SKU (analitica.pronostico), indice de
riesgo (analitica.riesgo) y score_anomalia (analitica.anomalias). Todo en MXN al FIX de
Banxico vigente en la fecha de corte (CC-03).

Escritura: reemplaza las recomendaciones NUEVA del motor; las que una persona ya movio
(EN_REVISION, ATENDIDA, DESCARTADA) se conservan, y el mismo caso no se vuelve a abrir mientras
este en curso ni durante 7 dias despues de cerrarlo o descartarlo.

Uso (desde backend, con .venv activo):  python -m analitica.recomendaciones
"""
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median

from psycopg2.extras import Json

from app.database import get_connection

CONFIG = Path(__file__).resolve().parents[1] / "etl" / "datos" / "config_simulacion.json"

# Supuestos economicos del motor (CC-19). Se guardan en la evidencia de cada recomendacion.
SUPUESTOS = {
    "margen_bruto": 0.30,                  # venta perdida = precio - costo, con precio = costo / (1 - margen)
    "costo_mantener_anual": 0.25,          # costo de mantener inventario, fraccion del valor por ano
    "factor_flete_expres": 1.8,            # flete expres contra flete normal
    "horizonte_dias": 14,                  # mismo horizonte del pronostico
    "cobertura_minima_origen_dias": 30,    # un almacen solo transfiere lo que exceda esta cobertura
    "exceso_cobertura_dias": 75,           # 1.5 veces la cobertura objetivo de la politica (50 dias)
    "umbral_puntualidad_30d": 0.80,        # entregas a tiempo de 30 dias (CC-16: critico bajo 85)
    "minimo_envios_30d": 3,
    "umbral_alza_precio": 0.03,            # 3% sobre la mediana de los 90 dias previos
    "umbral_concentracion": 0.35,          # 35% del gasto de 90 dias en un proveedor
    "prob_exito_negociacion": 0.5,
    "dias_manejo_transferencia": 1,
    "impacto_minimo_mxn": 5000,            # debajo de esto no se abre un caso (evita ruido)
}
CONDICIONES_SEVERAS = ("LLUVIA_FUERTE", "TORMENTA")


# ------------------------------------------------------------------ utilidades

def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _mxn(x):
    return round(float(x), 2)


# ------------------------------------------------------------------ contexto de datos

class Contexto:
    """Todo lo que las reglas necesitan, leido una sola vez."""

    def __init__(self, cur):
        self.cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.politica = self.cfg["politica_inventario"]
        self.transporte = self.cfg["transporte"]
        self.margen = SUPUESTOS["margen_bruto"]

        cur.execute("SELECT MAX(fecha) AS corte FROM demanda_diaria")
        self.corte = cur.fetchone()["corte"]
        if self.corte is None:
            raise RuntimeError("No hay datos operativos cargados")

        cur.execute("""SELECT tasa FROM tipo_cambio WHERE fuente = 'BANXICO_SIE' AND moneda_origen = 'USD'
                       AND moneda_destino = 'MXN' AND fecha <= %s ORDER BY fecha DESC LIMIT 1""", (self.corte,))
        fila = cur.fetchone()
        if fila is None:
            raise RuntimeError("No hay tipo de cambio FIX de Banxico a la fecha de corte")
        self.fix = float(fila["tasa"])

        cur.execute("SELECT producto_id, sku, nombre, costo_unitario FROM productos")
        self.productos = {r["producto_id"]: {"sku": r["sku"], "nombre": r["nombre"],
                                             "costo_mxn": float(r["costo_unitario"]) * self.fix}
                          for r in cur.fetchall()}
        self.producto_por_sku = {v["sku"]: k for k, v in self.productos.items()}

        cur.execute("SELECT almacen_id, nombre, latitud, longitud FROM almacenes")
        self.almacenes = {r["almacen_id"]: {"nombre": r["nombre"], "lat": float(r["latitud"]),
                                            "lon": float(r["longitud"])} for r in cur.fetchall()}

        cur.execute("SELECT proveedor_id, nombre FROM proveedores")
        conf = {p["nombre"]: p for p in self.cfg["proveedores"]}
        self.proveedores, self.proveedor_por_clave = {}, {}
        for r in cur.fetchall():
            c = conf.get(r["nombre"], {})
            self.proveedores[r["proveedor_id"]] = {
                "nombre": r["nombre"], "clave": c.get("clave"),
                "dias_preparacion": c.get("dias_preparacion", 2),
                "transito_internacional_dias": c.get("transito_internacional_dias", 0),
                "cargo_internacional_mxn": c.get("cargo_internacional_mxn", 0),
                "despacho": c.get("punto_despacho_mx"),
            }
            if c.get("clave"):
                self.proveedor_por_clave[c["clave"]] = r["proveedor_id"]
        # fuentes de cada producto (surtido de la configuracion)
        self.fuentes = defaultdict(dict)
        for sku, reparto in self.cfg["surtido"].items():
            if sku.startswith("_") or sku not in self.producto_por_sku:
                continue
            for clave, part in reparto.items():
                if clave in self.proveedor_por_clave:
                    self.fuentes[self.producto_por_sku[sku]][self.proveedor_por_clave[clave]] = part

        # stock al cierre de la fecha de corte
        cur.execute("""SELECT almacen_id, producto_id,
                              SUM(CASE WHEN tipo_movimiento = 'ENTRADA' THEN cantidad ELSE -cantidad END) AS stock
                       FROM movimientos_inventario WHERE fecha::date <= %s GROUP BY 1, 2""", (self.corte,))
        self.stock = {(r["almacen_id"], r["producto_id"]): max(0.0, float(r["stock"])) for r in cur.fetchall()}

        # demanda de los ultimos 28 dias
        cur.execute("""SELECT fecha, almacen_id, producto_id, unidades_solicitadas AS sol, unidades_entregadas AS ent
                       FROM demanda_diaria WHERE fecha > %s""", (self.corte - timedelta(days=28),))
        dem = cur.fetchall()
        self.dem28 = defaultdict(float)
        self.dem14 = defaultdict(float)
        self.dem_sku28 = defaultdict(float)
        for r in dem:
            k = (r["almacen_id"], r["producto_id"])
            self.dem28[k] += float(r["sol"])
            self.dem_sku28[r["producto_id"]] += float(r["sol"])
            if r["fecha"] > self.corte - timedelta(days=14):
                self.dem14[k] += float(r["sol"])

        # pronostico por SKU (red) y su MAPE
        cur.execute("""SELECT producto_id, fecha_prediccion, demanda_estimada, mape FROM forecast_demanda
                       WHERE producto_id IS NOT NULL ORDER BY fecha_prediccion""")
        self.pronostico, self.mape = defaultdict(list), {}
        for r in cur.fetchall():
            self.pronostico[r["producto_id"]].append(float(r["demanda_estimada"]))
            self.mape[r["producto_id"]] = float(r["mape"]) if r["mape"] is not None else None

        # envios con su orden y renglones
        cur.execute("""
            SELECT e.envio_id, e.orden_id, e.proveedor_id, e.almacen_origen_id AS almacen_id,
                   o.fecha_orden::date AS fecha_orden, e.fecha_salida::date AS salida,
                   e.fecha_llegada_estim::date AS estim, e.fecha_llegada_real::date AS real,
                   e.costo_flete, e.condicion_climatica AS clima, e.precipitacion_mm AS mm,
                   d.producto_id, d.cantidad, d.cantidad_recibida, d.precio_unitario
            FROM envios e
            JOIN ordenes_compra o ON o.orden_id = e.orden_id
            JOIN detalle_orden_compra d ON d.orden_id = e.orden_id
            WHERE o.fecha_orden::date <= %s
        """, (self.corte,))
        self.envios = {}
        for r in cur.fetchall():
            e = self.envios.setdefault(r["envio_id"], {
                "envio_id": r["envio_id"], "orden_id": r["orden_id"], "proveedor_id": r["proveedor_id"],
                "almacen_id": r["almacen_id"], "fecha_orden": r["fecha_orden"], "salida": r["salida"],
                "estim": r["estim"], "real": r["real"] if r["real"] and r["real"] <= self.corte else None,
                "flete": float(r["costo_flete"] or 0), "clima": r["clima"],
                "mm": float(r["mm"]) if r["mm"] is not None else None, "renglones": []})
            e["renglones"].append({"producto_id": r["producto_id"], "cantidad": float(r["cantidad"]),
                                   "precio_usd": float(r["precio_unitario"])})

        cur.execute("""SELECT fecha_id, producto_id, proveedor_id, MAX(score_anomalia) AS score
                       FROM fact_supply_chain WHERE score_anomalia IS NOT NULL GROUP BY 1, 2, 3""")
        self.scores = {(r["fecha_id"], r["producto_id"], r["proveedor_id"]): float(r["score"])
                       for r in cur.fetchall()}

    # --- derivados

    def recibidos(self, desde, hasta, proveedor_id=None):
        return [e for e in self.envios.values() if e["real"] and desde <= e["real"] <= hasta
                and (proveedor_id is None or e["proveedor_id"] == proveedor_id)]

    def en_transito(self):
        return [e for e in self.envios.values() if e["real"] is None]

    def puntualidad(self, proveedor_id, dias):
        envs = self.recibidos(self.corte - timedelta(days=dias - 1), self.corte, proveedor_id)
        if not envs:
            return None
        tarde = [(e["real"] - e["estim"]).days for e in envs if e["real"] > e["estim"]]
        return {"envios": len(envs), "a_tiempo": 1 - len(tarde) / len(envs),
                "retraso_promedio_tarde": (sum(tarde) / len(tarde)) if tarde else 0.0}

    def demanda_diaria(self, almacen_id, producto_id):
        """Demanda diaria proyectada: pronostico del SKU repartido por la participacion del
        almacen en los ultimos 28 dias (capta cambios locales como un pico regional)."""
        total = self.dem_sku28.get(producto_id, 0.0)
        part = self.dem28.get((almacen_id, producto_id), 0.0) / total if total else 0.0
        serie = self.pronostico.get(producto_id)
        if not serie:
            base = self.dem14.get((almacen_id, producto_id), 0.0) / 14
            return [base] * SUPUESTOS["horizonte_dias"]
        return [v * part for v in serie[:SUPUESTOS["horizonte_dias"]]]

    def media_diaria(self, almacen_id, producto_id):
        serie = self.demanda_diaria(almacen_id, producto_id)
        return sum(serie) / len(serie) if serie else 0.0

    def margen_unitario(self, producto_id):
        c = self.productos[producto_id]["costo_mxn"]
        return c / (1 - self.margen) - c

    def flete(self, origen, destino, proveedor_id=None):
        """Flete en MXN y dias de transito con la regla de transporte de la configuracion."""
        km = _haversine_km(origen[0], origen[1], destino[0], destino[1]) * self.transporte["factor_ruta"]
        costo = self.transporte["cargo_fijo_mxn"] + km * self.transporte["tarifa_mxn_km"]
        dias = math.ceil(km / self.transporte["velocidad_km_dia"])
        if proveedor_id is not None:
            p = self.proveedores[proveedor_id]
            costo += p["cargo_internacional_mxn"]
            dias += p["transito_internacional_dias"]
        return costo, max(1, dias), km

    def coord_almacen(self, almacen_id):
        a = self.almacenes[almacen_id]
        return a["lat"], a["lon"]

    def coord_despacho(self, proveedor_id):
        d = self.proveedores[proveedor_id]["despacho"]
        return d["latitud"], d["longitud"]

    def proyectar(self, almacen_id, producto_id, llegadas, extra_dias_retraso=0):
        """Stock proyectado dia por dia en el horizonte y unidades no surtidas."""
        demanda = self.demanda_diaria(almacen_id, producto_id)
        stock = self.stock.get((almacen_id, producto_id), 0.0)
        serie, faltante, primer_quiebre = [], 0.0, None
        for t, d in enumerate(demanda, start=1):
            dia = self.corte + timedelta(days=t)
            for fecha, qty in llegadas:
                if fecha + timedelta(days=extra_dias_retraso) == dia:
                    stock += qty
            stock -= d
            if stock < 0:
                faltante += -stock
                stock = 0.0
                if primer_quiebre is None:
                    primer_quiebre = t
            serie.append({"fecha": dia.isoformat(), "stock": round(stock, 1)})
        return serie, faltante, primer_quiebre


# ------------------------------------------------------------------ construccion de recomendaciones

def _opcion(clave, titulo, costo, detalle, riesgo=None):
    return {"clave": clave, "titulo": titulo, "costo_total_esperado_mxn": _mxn(costo),
            "detalle": detalle, "riesgo_residual": None if riesgo is None else round(riesgo, 3),
            "recomendada": False, "elegida": False}


def _elegir(opciones):
    """Marca la opcion de menor costo total esperado como recomendada (y elegida hasta que una
    persona elija otra en el Centro de soluciones); devuelve (opciones, mejor, sin_accion)."""
    opciones.sort(key=lambda o: o["costo_total_esperado_mxn"])
    opciones[0]["recomendada"] = opciones[0]["elegida"] = True
    sin_accion = next(o for o in opciones if o["clave"] == "SIN_ACCION")
    return opciones, opciones[0], sin_accion


def _reco(ctx, codigo, modulo, titulo, descripcion, opciones, confianza, evidencia, plan,
          producto_id=None, proveedor_id=None, almacen_id=None, envio_id=None, critico_si=None):
    opciones, mejor, sin_accion = _elegir(opciones)
    impacto = sin_accion["costo_total_esperado_mxn"] - mejor["costo_total_esperado_mxn"]
    if mejor["clave"] == "SIN_ACCION" or impacto < SUPUESTOS["impacto_minimo_mxn"]:
        return None  # actuar no conviene: no se genera ruido en el Centro de soluciones
    severidad = "CRITICO" if (critico_si or impacto >= 100000) else "ATENCION"
    evidencia = {**evidencia, "fecha_corte": ctx.corte.isoformat(), "tipo_cambio_fix": ctx.fix,
                 "supuestos": SUPUESTOS,
                 "metodo": "Costo total esperado = costo directo + probabilidad de falla x costo de la falla (CC-07, CC-19)"}
    return {
        "codigo_regla": codigo, "modulo": modulo, "severidad": severidad, "titulo": titulo[:200],
        "descripcion": descripcion, "solucion_recomendada": mejor["titulo"],
        "impacto_estimado_mxn": _mxn(impacto), "confianza": round(max(0.0, min(1.0, confianza)), 3),
        "evidencia": evidencia, "opciones": opciones, "plan": plan,
        "producto_id": producto_id, "proveedor_id": proveedor_id, "almacen_id": almacen_id, "envio_id": envio_id,
    }


# ------------------------------------------------------------------ reglas

def regla_quiebre(ctx):
    salida = []
    transito = ctx.en_transito()
    for (almacen_id, producto_id) in sorted({(a, p) for a in ctx.almacenes for p in ctx.productos}):
        media = ctx.media_diaria(almacen_id, producto_id)
        if media <= 0:
            continue
        llegadas, envios_rel, retraso_esp = [], [], 0.0
        for e in transito:
            if e["almacen_id"] != almacen_id:
                continue
            qty = sum(r["cantidad"] for r in e["renglones"] if r["producto_id"] == producto_id)
            if qty:
                pt = ctx.puntualidad(e["proveedor_id"], 90) or {"a_tiempo": 1.0, "retraso_promedio_tarde": 0}
                eta = max(e["estim"], ctx.corte + timedelta(days=1))
                llegadas.append((eta, qty))
                retraso_esp = max(retraso_esp, (1 - pt["a_tiempo"]) * pt["retraso_promedio_tarde"])
                envios_rel.append({"envio_id": e["envio_id"], "proveedor": ctx.proveedores[e["proveedor_id"]]["nombre"],
                                   "unidades": qty, "llegada_estimada": e["estim"].isoformat(),
                                   "prob_a_tiempo": round(pt["a_tiempo"], 3)})
        serie, faltante, dia_quiebre = ctx.proyectar(almacen_id, producto_id, llegadas, round(retraso_esp))
        if faltante < max(1.0, media):
            continue
        margen = ctx.margen_unitario(producto_id)
        nombre_p = ctx.productos[producto_id]["nombre"]
        nombre_a = ctx.almacenes[almacen_id]["nombre"]
        costo_unit = ctx.productos[producto_id]["costo_mxn"]
        seguridad = media * ctx.politica["stock_seguridad_dias"]
        opciones = [_opcion("SIN_ACCION", "Esperar las ordenes en transito", faltante * margen,
                            f"{faltante:.0f} u sin surtir en {SUPUESTOS['horizonte_dias']} dias; venta perdida al margen de {margen:,.0f} MXN por unidad",
                            1.0)]

        # A. transferencia desde el almacen con mas cobertura sobrante
        mejor_origen = None
        for b in ctx.almacenes:
            if b == almacen_id:
                continue
            mb = ctx.media_diaria(b, producto_id)
            sobrante = ctx.stock.get((b, producto_id), 0.0) - mb * SUPUESTOS["cobertura_minima_origen_dias"]
            if sobrante > 0 and (mejor_origen is None or sobrante > mejor_origen[1]):
                mejor_origen = (b, sobrante, mb)
        if mejor_origen:
            b, sobrante, mb = mejor_origen
            qty = min(sobrante, faltante + seguridad)
            flete, dias, km = ctx.flete(ctx.coord_almacen(b), ctx.coord_almacen(almacen_id))
            dias += SUPUESTOS["dias_manejo_transferencia"]
            _, falt_t, _ = ctx.proyectar(almacen_id, producto_id,
                                         llegadas + [(ctx.corte + timedelta(days=dias), qty)], round(retraso_esp))
            riesgo = falt_t / faltante
            opciones.append(_opcion("TRANSFERENCIA", f"Transferir {qty:.0f} u desde {ctx.almacenes[b]['nombre']}",
                                    flete + falt_t * margen,
                                    f"Flete {flete:,.0f} MXN ({km:,.0f} km, {dias} dias); quedan {falt_t:.0f} u sin surtir",
                                    riesgo))

        # B. orden urgente con flete expres al proveedor mas rapido del SKU
        mejor_prov = None
        for pid, part in ctx.fuentes.get(producto_id, {}).items():
            flete, dias, _ = ctx.flete(ctx.coord_despacho(pid), ctx.coord_almacen(almacen_id), pid)
            lt = max(1, ctx.proveedores[pid]["dias_preparacion"] - 1) + dias
            if mejor_prov is None or lt < mejor_prov[1]:
                mejor_prov = (pid, lt, flete)
        if mejor_prov:
            pid, lt, flete = mejor_prov
            pt = ctx.puntualidad(pid, 90) or {"a_tiempo": 1.0, "retraso_promedio_tarde": 0}
            qty = faltante + seguridad
            esperado_lt = lt + (1 - pt["a_tiempo"]) * pt["retraso_promedio_tarde"]
            _, falt_u, _ = ctx.proyectar(almacen_id, producto_id,
                                         llegadas + [(ctx.corte + timedelta(days=round(esperado_lt)), qty)],
                                         round(retraso_esp))
            costo = flete * SUPUESTOS["factor_flete_expres"] + falt_u * margen
            opciones.append(_opcion("ORDEN_URGENTE", f"Orden urgente con flete expres a {ctx.proveedores[pid]['nombre']}",
                                    costo, f"Llega en {lt} dias (a tiempo {pt['a_tiempo']:.0%}); "
                                           f"flete expres {flete * SUPUESTOS['factor_flete_expres']:,.0f} MXN; "
                                           f"quedan {falt_u:.0f} u sin surtir", falt_u / faltante))

        mape = ctx.mape.get(producto_id) or 0.15
        prob_transito = min([e["prob_a_tiempo"] for e in envios_rel], default=1.0)
        confianza = (1 - mape) * (0.85 + 0.15 * prob_transito)
        stock_hoy = ctx.stock.get((almacen_id, producto_id), 0.0)
        tendencia = (ctx.dem14.get((almacen_id, producto_id), 0) / 14) / (ctx.dem28.get((almacen_id, producto_id), 0) / 28 or 1) - 1
        r = _reco(
            ctx, "QUIEBRE_PROYECTADO", "INVENTARIOS",
            f"Quiebre proyectado de {nombre_p} en {nombre_a}",
            f"Con {stock_hoy:.0f} u en stock y la demanda pronosticada de {media:.1f} u diarias, "
            f"el stock se agota {'hoy' if dia_quiebre == 1 and stock_hoy == 0 else f'en {dia_quiebre} dias'} "
            f"y faltan {faltante:.0f} u en los proximos {SUPUESTOS['horizonte_dias']} dias.",
            opciones, confianza,
            {"tipo_grafica": "stock_proyectado", "stock_proyectado_sin_accion": serie,
             "stock_actual": stock_hoy, "demanda_diaria_pronosticada": round(media, 2),
             "unidades_sin_surtir": round(faltante, 1), "dias_para_quiebre": dia_quiebre,
             "punto_reorden": round(media * ctx.politica["stock_seguridad_dias"], 1),
             "variacion_demanda_14_vs_28_dias_pct": round(100 * tendencia, 1),
             "mape_pronostico_sku": mape, "envios_en_transito": envios_rel,
             "retraso_esperado_dias": round(retraso_esp, 1), "valor_unitario_mxn": round(costo_unit, 2),
             "razones": [f"Demanda pronosticada de {media:.1f} u diarias (Holt-Winters, MAPE {mape:.0%})",
                         f"Demanda de los ultimos 14 dias {tendencia:+.0%} contra los ultimos 28",
                         "Es la opcion con menor costo total esperado"]},
            [("Aprobar la opcion recomendada", "Gerencia de compras", 0),
             ("Ejecutar el movimiento o la orden", "Logistica", 1),
             (f"Revisar el punto de reorden de {nombre_p} en {nombre_a}", "Inventarios", 5),
             ("Medir el ahorro real a los 7 dias", "Seguimiento automatico", 7)],
            producto_id=producto_id, almacen_id=almacen_id,
            critico_si=dia_quiebre is not None and dia_quiebre <= 3)
        if r:
            salida.append(r)
    return salida


def regla_exceso(ctx):
    salida = []
    anual = SUPUESTOS["costo_mantener_anual"]
    for (almacen_id, producto_id), stock in ctx.stock.items():
        media = ctx.media_diaria(almacen_id, producto_id)
        if media <= 0 or stock / media <= SUPUESTOS["exceso_cobertura_dias"]:
            continue
        objetivo = ctx.politica["cobertura_objetivo_dias"]
        exceso = stock - media * objetivo
        costo_u = ctx.productos[producto_id]["costo_mxn"]
        dias_consumo = exceso / media
        mantener = exceso * costo_u * anual * (dias_consumo / 2) / 365
        opciones = [_opcion("SIN_ACCION", "Mantener el inventario y seguir el reorden normal", mantener,
                            f"{exceso:.0f} u sobre la cobertura objetivo; {dias_consumo:.0f} dias para consumirlas")]
        # transferir al almacen con menor cobertura
        destino = min((b for b in ctx.almacenes if b != almacen_id),
                      key=lambda b: ctx.stock.get((b, producto_id), 0) / max(ctx.media_diaria(b, producto_id), 1e-6))
        md = ctx.media_diaria(destino, producto_id)
        hueco = max(0.0, md * objetivo - ctx.stock.get((destino, producto_id), 0))
        qty = min(exceso, hueco)
        if qty > 0:
            flete, dias, km = ctx.flete(ctx.coord_almacen(almacen_id), ctx.coord_almacen(destino))
            resto = exceso - qty
            mantener_resto = resto * costo_u * anual * (resto / media / 2) / 365
            opciones.append(_opcion("TRANSFERENCIA", f"Transferir {qty:.0f} u a {ctx.almacenes[destino]['nombre']}",
                                    flete + mantener_resto,
                                    f"Flete {flete:,.0f} MXN; evita una compra en el destino y reduce el exceso"))
        # pausar el reorden: el exceso se consume sin nuevas entradas
        opciones.append(_opcion("PAUSAR_REORDEN", "Pausar el reorden hasta volver a la cobertura objetivo",
                                mantener * 0.6, "Sin compras nuevas del SKU en este almacen mientras dure el exceso"))
        r = _reco(
            ctx, "EXCESO_INVENTARIO", "INVENTARIOS",
            f"Exceso de {ctx.productos[producto_id]['nombre']} en {ctx.almacenes[almacen_id]['nombre']}",
            f"Cobertura de {stock / media:.0f} dias contra un objetivo de {objetivo}.",
            opciones, 1 - (ctx.mape.get(producto_id) or 0.15),
            {"tipo_grafica": "cobertura", "stock_actual": stock, "demanda_diaria_pronosticada": round(media, 2),
             "cobertura_dias": round(stock / media, 1), "cobertura_objetivo_dias": objetivo,
             "unidades_en_exceso": round(exceso, 1),
             "razones": [f"Cobertura de {stock / media:.0f} dias, {stock / media - objetivo:.0f} sobre el objetivo",
                         "Es la opcion con menor costo total esperado"]},
            [("Aprobar la opcion recomendada", "Inventarios", 0),
             ("Ajustar el punto de reorden del SKU", "Inventarios", 2),
             ("Medir el ahorro real a los 30 dias", "Seguimiento automatico", 30)],
            producto_id=producto_id, almacen_id=almacen_id)
        if r:
            salida.append(r)
    return salida


def regla_retrasos(ctx, cur):
    salida = []
    for pid, prov in ctx.proveedores.items():
        p30, p90 = ctx.puntualidad(pid, 30), ctx.puntualidad(pid, 90)
        if not p30 or p30["envios"] < SUPUESTOS["minimo_envios_30d"]:
            continue
        if p30["a_tiempo"] >= SUPUESTOS["umbral_puntualidad_30d"] or p30["a_tiempo"] >= p90["a_tiempo"]:
            continue
        # unidades no surtidas en los almacenes destino durante cada retraso de los ultimos 90 dias
        tardes = [e for e in ctx.recibidos(ctx.corte - timedelta(days=89), ctx.corte, pid) if e["real"] > e["estim"]]
        perdidas, valor = [], []
        for e in tardes:
            prods = [r["producto_id"] for r in e["renglones"]]
            cur.execute("""SELECT producto_id, SUM(unidades_solicitadas - unidades_entregadas) AS u
                           FROM demanda_diaria WHERE almacen_id = %s AND producto_id = ANY(%s)
                             AND fecha > %s AND fecha <= %s GROUP BY 1""",
                        (e["almacen_id"], prods, e["estim"], e["real"]))
            u = {r["producto_id"]: float(r["u"]) for r in cur.fetchall()}
            perdidas.append(sum(u.values()))
            valor.append(sum(v * ctx.margen_unitario(k) for k, v in u.items()))
        costo_por_tarde = sum(valor) / len(valor) if valor else 0.0
        envios_mes = max(1, p30["envios"])
        costo_sin = envios_mes * (1 - p30["a_tiempo"]) * costo_por_tarde
        prods_prov = sorted({r["producto_id"] for e in ctx.recibidos(ctx.corte - timedelta(days=89), ctx.corte, pid)
                             for r in e["renglones"]})
        opciones = [_opcion("SIN_ACCION", "Mantener la asignacion actual", costo_sin,
                            f"{envios_mes} envios al mes, {1 - p30['a_tiempo']:.0%} tarde; "
                            f"{costo_por_tarde:,.0f} MXN de venta perdida por envio tarde (medido)",
                            1 - p30["a_tiempo"])]
        # A. reasignar a la fuente alterna mas puntual de cada SKU
        dif_precio, prob_alt, alternos = 0.0, [], set()
        for prod in prods_prov:
            alt = [a for a in ctx.fuentes.get(prod, {}) if a != pid]
            alt = [(a, ctx.puntualidad(a, 90)) for a in alt]
            alt = [(a, s) for a, s in alt if s]
            if not alt:
                continue
            a, s = max(alt, key=lambda x: x[1]["a_tiempo"])
            alternos.add(ctx.proveedores[a]["nombre"])
            prob_alt.append(s["a_tiempo"])
            p_act = [r["precio_usd"] for e in ctx.recibidos(ctx.corte - timedelta(days=89), ctx.corte, pid)
                     for r in e["renglones"] if r["producto_id"] == prod]
            p_alt = [r["precio_usd"] for e in ctx.recibidos(ctx.corte - timedelta(days=89), ctx.corte, a)
                     for r in e["renglones"] if r["producto_id"] == prod]
            if p_act and p_alt:
                vol_mes = sum(ctx.media_diaria(al, prod) for al in ctx.almacenes) * 30 * ctx.fuentes[prod].get(pid, 0)
                dif_precio += max(0.0, median(p_alt) - median(p_act)) * ctx.fix * vol_mes
        if alternos:
            pa = sum(prob_alt) / len(prob_alt)
            opciones.append(_opcion("REASIGNAR", f"Reasignar las ordenes de 30 dias a {', '.join(sorted(alternos))}",
                                    dif_precio + envios_mes * (1 - pa) * costo_por_tarde,
                                    f"Diferencia de precio {dif_precio:,.0f} MXN; puntualidad alterna {pa:.0%}", 1 - pa))
        # B. colchon de seguridad igual al retraso promedio
        colchon = 0.0
        for prod in prods_prov:
            for al in ctx.almacenes:
                colchon += ctx.media_diaria(al, prod) * ctx.fuentes[prod].get(pid, 0) * p30["retraso_promedio_tarde"] \
                    * ctx.productos[prod]["costo_mxn"] * SUPUESTOS["costo_mantener_anual"] * 30 / 365
        opciones.append(_opcion("COLCHON", f"Agregar {p30['retraso_promedio_tarde']:.0f} dias de stock de seguridad a sus SKU",
                                colchon + costo_sin * 0.1, "Costo de mantener el colchon 30 dias; cubre ~90% de los retrasos", 0.1))
        r = _reco(
            ctx, "RETRASOS_PROVEEDOR", "PROVEEDORES",
            f"Retrasos de {prov['nombre']}",
            f"Entregas a tiempo de {p30['a_tiempo']:.0%} en 30 dias contra {p90['a_tiempo']:.0%} en 90; "
            f"retraso promedio de {p30['retraso_promedio_tarde']:.1f} dias.",
            opciones, min(0.95, 0.5 + 0.05 * p30["envios"]),
            {"tipo_grafica": "puntualidad", "a_tiempo_30d": round(p30["a_tiempo"], 3),
             "a_tiempo_90d": round(p90["a_tiempo"], 3), "envios_30d": p30["envios"],
             "retraso_promedio_dias": round(p30["retraso_promedio_tarde"], 1),
             "unidades_perdidas_por_envio_tarde": round(sum(perdidas) / len(perdidas), 1) if perdidas else 0,
             "razones": [f"Puntualidad de 30 dias {p30['a_tiempo']:.0%}, bajo el umbral de {SUPUESTOS['umbral_puntualidad_30d']:.0%}",
                         "Venta perdida medida en los almacenes destino durante los retrasos",
                         "Es la opcion con menor costo total esperado"]},
            [("Aprobar la opcion recomendada", "Gerencia de compras", 0),
             (f"Notificar a {prov['nombre']} el deterioro con la evidencia", "Compras", 1),
             ("Ajustar asignacion o stock de seguridad", "Inventarios", 3),
             ("Medir el ahorro real a los 30 dias", "Seguimiento automatico", 30)],
            proveedor_id=pid)
        if r:
            salida.append(r)
    return salida


def regla_alza_precio(ctx):
    salida = []
    reciente = ctx.corte - timedelta(days=29)
    base_desde = reciente - timedelta(days=90)
    for pid, prov in ctx.proveedores.items():
        for prod in sorted({r["producto_id"] for e in ctx.envios.values() if e["proveedor_id"] == pid
                            for r in e["renglones"]}):
            def precios(desde, hasta, proveedor):
                return [r["precio_usd"] for e in ctx.envios.values()
                        if e["proveedor_id"] == proveedor and desde <= e["fecha_orden"] <= hasta
                        for r in e["renglones"] if r["producto_id"] == prod]
            ahora, antes = precios(reciente, ctx.corte, pid), precios(base_desde, reciente - timedelta(days=1), pid)
            if len(ahora) < 2 or len(antes) < 2:
                continue
            p_ahora, p_base = sum(ahora) / len(ahora), median(antes)
            alza = p_ahora / p_base - 1
            if alza < SUPUESTOS["umbral_alza_precio"]:
                continue
            vol = sum(ctx.media_diaria(al, prod) for al in ctx.almacenes) * 30 * ctx.fuentes.get(prod, {}).get(pid, 0)
            if vol <= 0:
                continue
            costo_sin = p_ahora * ctx.fix * vol
            opciones = [_opcion("SIN_ACCION", "Mantener el precio actual", costo_sin,
                                f"{vol:.0f} u en 30 dias a {p_ahora:,.2f} USD ({alza:+.1%} sobre la base)")]
            pe = SUPUESTOS["prob_exito_negociacion"]
            opciones.append(_opcion("NEGOCIAR", "Negociar el regreso al precio base con la evidencia",
                                    (pe * p_base + (1 - pe) * p_ahora) * ctx.fix * vol,
                                    f"Probabilidad de exito supuesta de {pe:.0%}", 1 - pe))
            alternos = [a for a in ctx.fuentes.get(prod, {}) if a != pid]
            mejor = None
            for a in alternos:
                pa = precios(base_desde, ctx.corte, a)
                if pa and (mejor is None or median(pa) < mejor[1]):
                    mejor = (a, median(pa))
            if mejor:
                a, pa = mejor
                punt = ctx.puntualidad(a, 90) or {"a_tiempo": 1.0}
                opciones.append(_opcion("CAMBIAR_FUENTE", f"Mover el volumen a {ctx.proveedores[a]['nombre']}",
                                        pa * ctx.fix * vol * (1 + 0.02 * (1 - punt["a_tiempo"])),
                                        f"Precio {pa:,.2f} USD; puntualidad {punt['a_tiempo']:.0%}", 1 - punt["a_tiempo"]))
            scores = [v for (f, p_, pr), v in ctx.scores.items() if p_ == prod and pr == pid and f >= reciente]
            confianza = min(0.95, 0.6 + 0.05 * len(ahora) + (0.1 if scores and max(scores) > 0.5 else 0))
            r = _reco(
                ctx, "ALZA_PRECIO", "COMPRAS",
                f"Alza de precio de {prov['nombre']} en {ctx.productos[prod]['nombre']}",
                f"Precio promedio de 30 dias {p_ahora:,.2f} USD contra la mediana de 90 dias previos "
                f"{p_base:,.2f} USD ({alza:+.1%}).",
                opciones, confianza,
                {"tipo_grafica": "precio", "precio_actual_usd": round(p_ahora, 2), "precio_base_usd": round(p_base, 2),
                 "alza_pct": round(100 * alza, 2), "volumen_30_dias": round(vol, 0),
                 "ordenes_recientes": len(ahora),
                 "score_anomalia_max": round(max(scores), 3) if scores else None,
                 "razones": [f"Alza de {alza:.1%} sostenida en {len(ahora)} ordenes de 30 dias",
                             "Isolation Forest marca las ordenes como atipicas" if scores and max(scores) > 0.5
                             else "Comparacion contra la mediana historica del mismo proveedor",
                             "Es la opcion con menor costo total esperado"]},
                [("Aprobar la opcion recomendada", "Gerencia de compras", 0),
                 ("Solicitar cotizacion o negociar con la evidencia", "Compras", 2),
                 ("Medir el ahorro real a los 30 dias", "Seguimiento automatico", 30)],
                producto_id=prod, proveedor_id=pid)
            if r:
                salida.append(r)
    return salida


def regla_clima(ctx):
    """Envios en transito por rutas que tuvieron lluvia fuerte o tormenta en los ultimos 14 dias."""
    salida = []
    recientes = ctx.recibidos(ctx.corte - timedelta(days=13), ctx.corte)
    hist = ctx.recibidos(ctx.corte - timedelta(days=364), ctx.corte)

    def tarde(e):
        return e["real"] > e["estim"]

    sev = [e for e in hist if e["clima"] in CONDICIONES_SEVERAS]
    normal = [e for e in hist if e["clima"] not in CONDICIONES_SEVERAS]
    p_sev = sum(map(tarde, sev)) / len(sev) if sev else None
    p_norm = sum(map(tarde, normal)) / len(normal) if normal else None
    if p_sev is None or p_norm is None:
        return salida
    for e in ctx.en_transito():
        ruta = [x for x in recientes if x["proveedor_id"] == e["proveedor_id"] and x["almacen_id"] == e["almacen_id"]
                and x["clima"] in CONDICIONES_SEVERAS]
        if not ruta:
            continue
        retraso = sum((x["real"] - x["estim"]).days for x in sev if tarde(x)) / max(1, sum(map(tarde, sev)))
        costo_sin, prods = 0.0, []
        for r_ in e["renglones"]:
            prod = r_["producto_id"]
            llegadas = [(e["estim"], r_["cantidad"])]
            _, f0, _ = ctx.proyectar(e["almacen_id"], prod, llegadas)
            _, f1, _ = ctx.proyectar(e["almacen_id"], prod, llegadas, round(retraso))
            costo_sin += p_sev * (f1 - f0) * ctx.margen_unitario(prod)
            prods.append(ctx.productos[prod]["nombre"])
        flete_alt = e["flete"] * 0.3
        opciones = [_opcion("SIN_ACCION", "Mantener la ruta y la fecha estimada", costo_sin,
                            f"Probabilidad de retraso con lluvia fuerte {p_sev:.0%} contra {p_norm:.0%} normal", p_sev),
                    _opcion("REPROGRAMAR", "Reprogramar la recepcion y avisar al almacen",
                            costo_sin * 0.5, "Ajusta la fecha estimada y prioriza el surtido con el stock disponible", p_sev / 2),
                    _opcion("RUTA_ALTERNA", "Cambiar a ruta o transportista alterno",
                            flete_alt + costo_sin * (p_norm / p_sev if p_sev else 0),
                            f"Sobrecosto estimado de flete {flete_alt:,.0f} MXN (30%)", p_norm)]
        origen = ctx.proveedores[e["proveedor_id"]]["despacho"]["nombre"]
        destino = ctx.almacenes[e["almacen_id"]]["nombre"]
        r = _reco(
            ctx, "CLIMA_RUTA", "LOGISTICA",
            f"Lluvia fuerte en la ruta {origen} - {destino}",
            f"{len(ruta)} envios recientes de la ruta llegaron con lluvia fuerte o tormenta; "
            f"el envio {e['envio_id']} sigue en transito con llegada estimada {e['estim'].isoformat()}.",
            opciones, 0.6 + 0.1 * min(3, len(ruta)),
            {"tipo_grafica": "clima_ruta", "envio_id": e["envio_id"], "llegada_estimada": e["estim"].isoformat(),
             "envios_recientes_con_lluvia_fuerte": [{"envio_id": x["envio_id"], "condicion": x["clima"],
                                                    "precipitacion_mm": x["mm"]} for x in ruta],
             "prob_retraso_lluvia_fuerte": round(p_sev, 3), "prob_retraso_normal": round(p_norm, 3),
             "productos": prods, "fuente_clima": "Open-Meteo (historico real, CC-04)",
             "razones": [f"Con lluvia fuerte o tormenta, {p_sev:.0%} de los envios llegaron tarde (12 meses)",
                         "Es la opcion con menor costo total esperado"]},
            [("Aprobar la opcion recomendada", "Logistica", 0),
             ("Confirmar con el transportista la nueva fecha", "Logistica", 1),
             ("Medir el ahorro real al recibir el envio", "Seguimiento automatico", 7)],
            proveedor_id=e["proveedor_id"], almacen_id=e["almacen_id"], envio_id=e["envio_id"])
        if r:
            salida.append(r)
    return salida


def regla_concentracion(ctx):
    salida = []
    envs = [e for e in ctx.envios.values() if ctx.corte - timedelta(days=89) <= e["fecha_orden"] <= ctx.corte]
    gasto = defaultdict(float)
    for e in envs:
        gasto[e["proveedor_id"]] += sum(r["cantidad"] * r["precio_usd"] for r in e["renglones"]) * ctx.fix
    total = sum(gasto.values())
    for pid, g in gasto.items():
        part = g / total if total else 0
        if part < SUPUESTOS["umbral_concentracion"]:
            continue
        p90 = ctx.puntualidad(pid, 90) or {"a_tiempo": 1.0}
        # exposicion: si el proveedor falla 7 dias, la venta perdida de lo que depende de el
        dependiente = 0.0
        for prod, rep in ctx.fuentes.items():
            if pid in rep:
                dependiente += sum(ctx.media_diaria(al, prod) for al in ctx.almacenes) * rep[pid] * 7 \
                    * ctx.margen_unitario(prod)
        prob_falla = 1 - p90["a_tiempo"]
        costo_sin = prob_falla * dependiente
        opciones = [_opcion("SIN_ACCION", "Mantener la concentracion actual", costo_sin,
                            f"Exposicion de 7 dias {dependiente:,.0f} MXN x probabilidad de falla {prob_falla:.0%}",
                            prob_falla),
                    _opcion("DIVERSIFICAR", "Mover 20% del volumen a las fuentes alternas",
                            costo_sin * 0.8 + 0.01 * g * 0.2,
                            "Reduce la exposicion 20%; sobrecosto supuesto de 1% en el volumen movido", prob_falla * 0.8)]
        r = _reco(
            ctx, "CONCENTRACION_GASTO", "PROVEEDORES",
            f"Concentracion de gasto en {ctx.proveedores[pid]['nombre']}",
            f"{part:.0%} de las compras de 90 dias ({g:,.0f} MXN) con un solo proveedor.",
            opciones, 0.7,
            {"tipo_grafica": "participacion", "participacion_pct": round(100 * part, 1), "gasto_90d_mxn": round(g, 2),
             "participaciones": {ctx.proveedores[k]["nombre"]: round(100 * v / total, 1) for k, v in gasto.items()},
             "razones": [f"{part:.0%} del gasto, sobre el umbral de {SUPUESTOS['umbral_concentracion']:.0%}",
                         "Es la opcion con menor costo total esperado"]},
            [("Aprobar la opcion recomendada", "Gerencia de compras", 0),
             ("Cotizar con las fuentes alternas", "Compras", 5),
             ("Medir el ahorro real a los 90 dias", "Seguimiento automatico", 90)],
            proveedor_id=pid)
        if r:
            salida.append(r)
    return salida


# ------------------------------------------------------------------ escritura

def _llave(r):
    return (r["codigo_regla"], r["producto_id"], r["proveedor_id"], r["almacen_id"], r["envio_id"])


def generar(cur):
    ctx = Contexto(cur)
    recos = (regla_quiebre(ctx) + regla_exceso(ctx) + regla_retrasos(ctx, cur) + regla_alza_precio(ctx)
             + regla_clima(ctx) + regla_concentracion(ctx))
    return ctx, sorted(recos, key=lambda r: -r["impacto_estimado_mxn"])


def guardar(cur, ctx, recos):
    cur.execute("DELETE FROM recomendaciones WHERE estado = 'NUEVA'")
    # no se duplica un caso en curso ni uno que una persona cerro o descarto en los ultimos 7 dias
    cur.execute("""SELECT codigo_regla, producto_id, proveedor_id, almacen_id, envio_id FROM recomendaciones
                   WHERE estado = 'EN_REVISION'
                      OR (estado IN ('ATENDIDA', 'DESCARTADA') AND fecha_cierre >= NOW() - INTERVAL '7 days')""")
    en_curso = {(r["codigo_regla"], r["producto_id"], r["proveedor_id"], r["almacen_id"], r["envio_id"])
                for r in cur.fetchall()}
    # fechas de deteccion y compromiso en tiempo real: las decisiones humanas ocurren hoy,
    # aunque los datos operativos lleguen hasta la fecha de corte (guardada en la evidencia)
    deteccion = datetime.now().replace(microsecond=0)
    nuevas = 0
    for r in recos:
        if _llave(r) in en_curso:
            continue
        cur.execute("""
            INSERT INTO recomendaciones (codigo_regla, modulo, severidad, titulo, descripcion, solucion_recomendada,
                impacto_estimado_mxn, confianza, evidencia, producto_id, proveedor_id, almacen_id, envio_id,
                estado, fecha_deteccion, opciones)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'NUEVA', %s, %s)
            RETURNING recomendacion_id
        """, (r["codigo_regla"], r["modulo"], r["severidad"], r["titulo"], r["descripcion"],
              r["solucion_recomendada"], r["impacto_estimado_mxn"], r["confianza"], Json(r["evidencia"]),
              r["producto_id"], r["proveedor_id"], r["almacen_id"], r["envio_id"], deteccion, Json(r["opciones"])))
        rid = cur.fetchone()["recomendacion_id"]
        for paso, (desc, resp, dias) in enumerate(r["plan"], start=1):
            cur.execute("""INSERT INTO plan_acciones (recomendacion_id, orden_paso, descripcion, responsable,
                           fecha_compromiso, estado) VALUES (%s, %s, %s, %s, %s, 'PENDIENTE')""",
                        (rid, paso, desc[:300], resp, deteccion.date() + timedelta(days=dias)))
        nuevas += 1
    return nuevas


def main():
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                ctx, recos = generar(cur)
                nuevas = guardar(cur, ctx, recos)
    finally:
        conn.close()
    print(f"Motor de recomendaciones al {ctx.corte} (FIX {ctx.fix:.4f})")
    por_regla = defaultdict(int)
    for r in recos:
        por_regla[r["codigo_regla"]] += 1
    print("  por regla: " + ", ".join(f"{k} {v}" for k, v in sorted(por_regla.items())))
    for r in recos[:10]:
        print(f"  {r['severidad']:<8} {r['impacto_estimado_mxn']:>12,.0f} MXN  conf {r['confianza']:.0%}  "
              f"{r['titulo'][:60]}  -> {r['solucion_recomendada'][:50]}")
    print(f"  recomendaciones nuevas guardadas: {nuevas} (impacto total {sum(r['impacto_estimado_mxn'] for r in recos):,.0f} MXN)")


if __name__ == "__main__":
    main()