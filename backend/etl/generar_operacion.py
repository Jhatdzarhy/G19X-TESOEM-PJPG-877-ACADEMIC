"""Generador de 12 meses de operacion simulada -> supply_chain_final.

Flujo del PDR seccion 5.2 (datos internos simulados con reglas de negocio).
Parametros: backend/etl/datos/config_simulacion.json

Control de cambios (riesgo R6):
  CC-02  llena cantidad_recibida, movimientos_inventario.orden_id, demanda_diaria,
         coordenadas, precipitacion_mm
  CC-04  el clima real de Open-Meteo (cache local) aumenta la probabilidad de retraso
  CC-05  la demanda solicitada contra entregada alimenta el Fill Rate de servicio
  CC-06  envios.almacen_origen_id guarda el almacen de destino
  CC-07  eventos inyectados con verdad conocida -> backend/etl/datos/eventos_inyectados.json
  CC-11  todos los textos en ASCII

Reglas:
  - Semilla fija: misma configuracion, mismos datos.
  - Idempotente: vacia y regenera las tablas operativas (no toca productos ni tipo_cambio).
    Tambien vacia recomendaciones y plan_acciones, que se recalculan despues.
  - Precios y montos en USD (moneda de productos); flete en MXN.
  - Ordenes que llegan despues del fin del periodo quedan EN_TRANSITO.

Uso (desde backend, con .venv activo):
  python -m etl.generar_operacion
"""
import json
import math
import random
from collections import defaultdict, deque
from datetime import date, datetime, time, timedelta
from pathlib import Path

from psycopg2.extras import execute_values

from app.database import get_connection

ETL = Path(__file__).resolve().parent
RAIZ = ETL.parents[1]
CONFIG = ETL / "datos" / "config_simulacion.json"
VOLUMEN = ETL / "datos" / "volumen_por_sku.json"
SALIDA_EVENTOS = ETL / "datos" / "eventos_inyectados.json"
ORDEN_CLIMA = {"DESPEJADO": 0, "LLUVIA": 1, "LLUVIA_FUERTE": 2, "TORMENTA": 3}


# ------------------------------------------------------------------ utilidades

def fecha(texto):
    return date.fromisoformat(texto)


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def clave_ascii(texto):
    return "_".join(texto.upper().replace(",", " ").split())


def en_rango(dia, ev):
    return fecha(ev["inicio"]) <= dia <= fecha(ev["fin"])


def a_dict(fila, columnas):
    """get_connection puede devolver diccionarios (RealDictCursor) o tuplas."""
    return dict(fila) if isinstance(fila, dict) else dict(zip(columnas, fila))


# ------------------------------------------------------------------ clima (CC-04)

class Clima:
    def __init__(self, cfg):
        self.reglas = cfg["clima"]
        carpeta = RAIZ / self.reglas["carpeta_cache"]
        self.datos = {}
        for archivo in carpeta.glob("*.json"):
            d = json.loads(archivo.read_text(encoding="utf-8"))
            diario = d["daily"]
            self.datos[archivo.stem] = {
                t: (c, p) for t, c, p in zip(diario["time"], diario["weather_code"], diario["precipitation_sum"])
            }
        if not self.datos:
            raise RuntimeError("No hay cache de clima. Ejecute antes: python backend/etl/descargar_clima.py")

    def condicion(self, punto, dia):
        codigo, mm = self.datos[punto].get(dia.isoformat(), (None, 0.0))
        mm = mm or 0.0
        r = self.reglas
        if (codigo is not None and int(codigo) in r["codigos_tormenta"]) or mm >= r["umbral_tormenta_mm"]:
            return "TORMENTA", mm
        if mm >= r["umbral_lluvia_fuerte_mm"]:
            return "LLUVIA_FUERTE", mm
        if mm >= r["umbral_lluvia_mm"]:
            return "LLUVIA", mm
        return "DESPEJADO", mm

    def peor_en_ruta(self, puntos, desde, hasta):
        """Peor condicion y precipitacion maxima en los puntos de la ruta entre dos fechas."""
        peor, mm_max = "DESPEJADO", 0.0
        dia = desde
        while dia <= hasta:
            for p in puntos:
                cond, mm = self.condicion(p, dia)
                if ORDEN_CLIMA[cond] > ORDEN_CLIMA[peor]:
                    peor = cond
                mm_max = max(mm_max, mm)
            dia += timedelta(days=1)
        return peor, round(mm_max, 2)


# ------------------------------------------------------------------ generador

class Generador:
    def __init__(self, cfg, productos, volumen):
        self.cfg = cfg
        self.rng = random.Random(cfg["simulacion"]["semilla"])
        self.inicio = fecha(cfg["simulacion"]["fecha_inicio"])
        self.fin = fecha(cfg["simulacion"]["fecha_fin"])
        self.clima = Clima(cfg)
        self.productos = productos                      # sku -> {producto_id, costo_unitario}
        self.volumen = volumen                          # sku -> m3 por unidad
        self.skus = list(cfg["demanda"]["base_diaria_por_sku"].keys())
        faltan = [s for s in self.skus if s not in productos]
        if faltan:
            raise RuntimeError(f"SKU sin producto cargado en la base: {faltan}")

        self.alm = {a["clave"]: dict(a, almacen_id=i + 1) for i, a in enumerate(cfg["almacenes"])}
        self.prov = {p["clave"]: dict(p, proveedor_id=i + 1) for i, p in enumerate(cfg["proveedores"])}
        self.eventos = cfg["eventos_inyectados"]["eventos"]
        self.pol = cfg["politica_inventario"]
        self.trans = cfg["transporte"]

        # lead time esperado (dias) por proveedor y almacen
        self.ruta = {}
        for pk, p in self.prov.items():
            d = p["punto_despacho_mx"]
            for ak, a in self.alm.items():
                km = haversine_km(d["latitud"], d["longitud"], a["latitud"], a["longitud"]) * self.trans["factor_ruta"]
                terrestre = max(1, math.ceil(km / self.trans["velocidad_km_dia"]))
                self.ruta[(pk, ak)] = {
                    "km": km,
                    "terrestre": terrestre,
                    "lt": p["dias_preparacion"] + p["transito_internacional_dias"] + terrestre,
                    "punto_clima": "DESP_" + clave_ascii(d["nombre"]),
                }

        # salida
        self.ordenes, self.detalles, self.envios = [], [], []
        self.movimientos, self.demanda = [], []
        self.verdad = {e["clave"]: {"evento": e, "orden_id": set(), "detalle_id": set(),
                                    "envio_id": set(), "demanda": []} for e in self.eventos}
        self.utilizacion = defaultdict(list)

    # ----------------------------------------------------------- eventos (CC-07)
    def eventos_activos(self, dia, tipo, **filtro):
        for e in self.eventos:
            if e["tipo"] != tipo or not en_rango(dia, e):
                continue
            if all(e.get(k) is None or (v in e[k] if isinstance(e[k], list) else e[k] == v)
                   for k, v in filtro.items()):
                yield e

    # ----------------------------------------------------------- demanda (CC-05)
    def demanda_del_dia(self, dia, ak, sku):
        dcfg = self.cfg["demanda"]
        media = dcfg["base_diaria_por_sku"][sku] * self.alm[ak]["reparto_demanda"]
        media *= dcfg["estacionalidad_semanal"]["factores"][dia.weekday()]
        media *= 1 + dcfg["tendencia_anual"] * (dia - self.inicio).days / 365.0
        for ev in dcfg["eventos_calendario"]:
            if en_rango(dia, ev):
                media *= ev["factor"]
        claves = []
        for tipo in ("PICO_DEMANDA", "CAIDA_DEMANDA"):
            for e in self.eventos_activos(dia, tipo, almacen=ak, skus=sku):
                media *= 1 + e["magnitud"]
                claves.append(e["clave"])
        cv = dcfg["ruido_cv"]
        sigma = math.sqrt(math.log(1 + cv * cv))
        valor = media * self.rng.lognormvariate(-sigma * sigma / 2, sigma)
        return max(0, int(round(valor))), claves

    # ----------------------------------------------------------- compras
    def elegir_proveedor(self, sku):
        surtido = self.cfg["surtido"][sku]
        claves, pesos = list(surtido.keys()), list(surtido.values())
        return self.rng.choices(claves, weights=pesos, k=1)[0]

    def lt_esperado(self, sku, ak):
        surtido = self.cfg["surtido"][sku]
        return sum(peso * self.ruta[(pk, ak)]["lt"] for pk, peso in surtido.items())

    def precio(self, dia, pk, sku):
        p = self.prov[pk]
        base = self.productos[sku]["costo_unitario"] * p["factor_precio"]
        ajuste, claves = 0.0, []
        for e in self.eventos_activos(dia, "ALZA_PRECIO", proveedor=pk, skus=sku):
            total = (fecha(e["fin"]) - fecha(e["inicio"])).days or 1
            avance = (dia - fecha(e["inicio"])).days / total if e.get("forma") == "GRADUAL" else 1.0
            ajuste += e["magnitud"] * min(1.0, max(0.0, avance))
            claves.append(e["clave"])
        ruido = self.rng.gauss(0, p["volatilidad_precio"])
        return round(base * (1 + ajuste) * (1 + ruido), 2), claves

    def cumplimiento(self, dia, pk):
        """Fraccion recibida de un renglon; el promedio es fill_rate_medio del proveedor."""
        fr, claves = self.prov[pk]["fill_rate_medio"], []
        for e in self.eventos_activos(dia, "BAJA_FILL_RATE", proveedor=pk):
            fr, claves = e["fill_rate_medio"], [e["clave"]]
        # faltantes poco frecuentes pero significativos: se recibe entre 40% y 80% del renglon
        prob_faltante = min(1.0, (1 - fr) / 0.40)
        if self.rng.random() < prob_faltante:
            return self.rng.uniform(0.40, 0.80), claves
        return 1.0, claves

    def retraso(self, dia, pk):
        p, claves = self.prov[pk], []
        prob, rango = p["prob_a_tiempo"], p["retraso_dias"]
        for e in self.eventos_activos(dia, "DETERIORO_PUNTUALIDAD", proveedor=pk):
            prob, rango, claves = e["prob_a_tiempo"], e["retraso_dias"], [e["clave"]]
        if self.rng.random() < prob:
            return 0, claves
        return self.rng.randint(rango[0], rango[1]), claves

    def flete(self, dia, pk, ak):
        r = self.ruta[(pk, ak)]
        costo = self.trans["cargo_fijo_mxn"] + r["km"] * self.trans["tarifa_mxn_km"] + self.prov[pk]["cargo_internacional_mxn"]
        claves = []
        for e in self.eventos_activos(dia, "ALZA_FLETE", proveedor=pk):
            costo *= 1 + e["magnitud"]
            claves.append(e["clave"])
        costo *= max(0.7, 1 + self.rng.gauss(0, self.trans["ruido_costo_cv"]))
        return round(costo, 2), claves

    # ----------------------------------------------------------- simulacion
    def ejecutar(self):
        stock = {(ak, s): 0 for ak in self.alm for s in self.skus}
        transito = defaultdict(int)                               # (ak, sku) -> unidades en camino
        llegadas = defaultdict(list)                              # fecha -> [orden]
        historial = {k: deque(maxlen=self.pol["ventana_demanda_media_dias"]) for k in stock}
        mov_id = det_id = orden_id = 0

        # inventario inicial (ENTRADA sin orden, un dia antes del periodo)
        dia0 = datetime.combine(self.inicio - timedelta(days=1), time(8, 0))
        for (ak, sku) in stock:
            media = self.cfg["demanda"]["base_diaria_por_sku"][sku] * self.alm[ak]["reparto_demanda"]
            cant = int(round(media * self.pol["cobertura_inicial_dias"]))
            stock[(ak, sku)] = cant
            for _ in range(self.pol["ventana_demanda_media_dias"]):
                historial[(ak, sku)].append(media)
            mov_id += 1
            self.movimientos.append((mov_id, self.alm[ak]["almacen_id"], self.productos[sku]["producto_id"],
                                     "ENTRADA", cant, dia0, None))

        dia = self.inicio
        while dia <= self.fin:
            # 1. recepciones del dia
            for o in llegadas.pop(dia, []):
                parcial = False
                for ln in o["lineas"]:
                    stock[(o["ak"], ln["sku"])] += ln["recibida"]
                    transito[(o["ak"], ln["sku"])] -= ln["cantidad"]
                    parcial |= ln["recibida"] < ln["cantidad"]
                    mov_id += 1
                    self.movimientos.append((mov_id, self.alm[o["ak"]]["almacen_id"],
                                             self.productos[ln["sku"]]["producto_id"], "ENTRADA",
                                             ln["recibida"], o["llegada_real"], o["orden_id"]))
                o["fila"][4] = o["llegada_real"]
                o["fila"][5] = "RECIBIDA_PARCIAL" if parcial else "RECIBIDA"

            # 2. demanda y salidas
            salida_ts = datetime.combine(dia, time(18, 0))
            for (ak, sku) in stock:
                solicitada, claves = self.demanda_del_dia(dia, ak, sku)
                entregada = min(solicitada, stock[(ak, sku)])
                stock[(ak, sku)] -= entregada
                historial[(ak, sku)].append(solicitada)
                self.demanda.append((dia, self.alm[ak]["almacen_id"], self.productos[sku]["producto_id"],
                                     solicitada, entregada))
                for c in claves:
                    self.verdad[c]["demanda"].append([dia.isoformat(), ak, sku])
                if entregada:
                    mov_id += 1
                    self.movimientos.append((mov_id, self.alm[ak]["almacen_id"], self.productos[sku]["producto_id"],
                                             "SALIDA", entregada, salida_ts, None))

            # utilizacion de almacen del dia (verificacion)
            for ak, a in self.alm.items():
                m3 = sum(stock[(ak, s)] * self.volumen[s] for s in self.skus)
                self.utilizacion[ak].append(m3 / a["capacidad_m3"])

            # 3. revision de inventario y pedidos consolidados por proveedor y almacen
            pedidos = defaultdict(list)
            m3_comprometido = {ak: sum((stock[(ak, s)] + transito[(ak, s)]) * self.volumen[s] for s in self.skus)
                               for ak in self.alm}
            for (ak, sku) in stock:
                dm = sum(historial[(ak, sku)]) / len(historial[(ak, sku)])
                lt = self.lt_esperado(sku, ak)
                posicion = stock[(ak, sku)] + transito[(ak, sku)]
                if posicion >= dm * (lt + self.pol["stock_seguridad_dias"]) or dm <= 0:
                    continue
                cant = int(math.ceil(dm * (lt + self.pol["cobertura_objetivo_dias"]) - posicion))
                # limite de capacidad del almacen
                libre = self.pol["utilizacion_maxima_para_ordenar"] * self.alm[ak]["capacidad_m3"] - m3_comprometido[ak]
                cant = min(cant, int(max(0.0, libre) / self.volumen[sku]))
                if cant <= 0:
                    continue
                m3_comprometido[ak] += cant * self.volumen[sku]
                pedidos[(self.elegir_proveedor(sku), ak)].append((sku, cant))

            for (pk, ak), lineas in sorted(pedidos.items()):
                orden_id += 1
                r = self.ruta[(pk, ak)]
                p = self.prov[pk]
                ts_orden = datetime.combine(dia, time(self.rng.randint(9, 16), self.rng.choice((0, 15, 30, 45))))
                salida = dia + timedelta(days=p["dias_preparacion"])
                llegada_estim = dia + timedelta(days=r["lt"])
                inicio_terrestre = salida + timedelta(days=p["transito_internacional_dias"])
                cond, mm = self.clima.peor_en_ruta([r["punto_clima"], "ALM_" + ak], inicio_terrestre, llegada_estim)
                dias_retraso, claves_ret = self.retraso(dia, pk)
                imp = self.cfg["clima"]["impacto"].get(cond)
                if imp and self.rng.random() < imp["prob_retraso_extra"]:
                    dias_retraso += self.rng.randint(*imp["retraso_extra_dias"])
                hora = time(self.rng.randint(8, 17), 0)
                llegada_real = datetime.combine(llegada_estim + timedelta(days=dias_retraso), hora)
                costo_flete, claves_flete = self.flete(dia, pk, ak)

                monto, lns, claves_lin = 0.0, [], []
                for sku, cant in lineas:
                    det_id += 1
                    precio, cp = self.precio(dia, pk, sku)
                    frac, cf = self.cumplimiento(dia, pk)
                    recibida = int(math.floor(cant * frac))
                    monto += cant * precio
                    lns.append({"sku": sku, "cantidad": cant, "recibida": recibida})
                    transito[(ak, sku)] += cant
                    self.detalles.append([det_id, orden_id, self.productos[sku]["producto_id"], cant, precio,
                                          recibida if llegada_real.date() <= self.fin else None])
                    for c in cp + cf:
                        self.verdad[c]["detalle_id"].add(det_id)
                        claves_lin.append(c)

                fila_orden = [orden_id, p["proveedor_id"], ts_orden,
                              datetime.combine(llegada_estim, time(12, 0)), None, "EN_TRANSITO", round(monto, 2)]
                self.ordenes.append(fila_orden)
                envio_id = orden_id
                self.envios.append((envio_id, orden_id, p["proveedor_id"], self.alm[ak]["almacen_id"],
                                    datetime.combine(salida, time(7, 0)),
                                    datetime.combine(llegada_estim, time(12, 0)),
                                    llegada_real if llegada_real.date() <= self.fin else None,
                                    costo_flete, cond, mm))
                for c in claves_ret + claves_flete + claves_lin:
                    self.verdad[c]["orden_id"].add(orden_id)
                    self.verdad[c]["envio_id"].add(envio_id)

                orden = {"orden_id": orden_id, "ak": ak, "lineas": lns, "llegada_real": llegada_real, "fila": fila_orden}
                if llegada_real.date() <= self.fin:
                    llegadas[llegada_real.date()].append(orden)
            dia += timedelta(days=1)

        self.stock_final = stock
        return self

    # ----------------------------------------------------------- resumen de verificacion
    def resumen(self):
        recibidas = [e for e in self.envios if e[6] is not None]
        det_por_orden = defaultdict(list)
        for d in self.detalles:
            det_por_orden[d[1]].append(d)
        otif = sum(1 for e in recibidas
                   if e[6].date() <= e[5].date() and all(d[5] is not None and d[5] >= d[3] for d in det_por_orden[e[1]]))
        a_tiempo = sum(1 for e in recibidas if e[6].date() <= e[5].date())
        fr_serv = sum(d[4] for d in self.demanda) / max(1, sum(d[3] for d in self.demanda))
        cerr = [d for d in self.detalles if d[5] is not None]
        fr_prov = sum(d[5] for d in cerr) / max(1, sum(d[3] for d in cerr))
        lt = [(e[6] - datetime.combine(o[2].date(), time(0))).days
              for e, o in zip(self.envios, self.ordenes) if e[6] is not None]
        unidades = sum(d[5] for d in cerr)
        flete = sum(e[7] for e in recibidas)
        clima = defaultdict(int)
        for e in self.envios:
            clima[e[8]] += 1
        print("Resumen de la simulacion (verificacion rapida, no sustituye a validar_kpis.sql)")
        print(f"  ordenes: {len(self.ordenes)}   renglones: {len(self.detalles)}   envios recibidos: {len(recibidas)}")
        print(f"  movimientos: {len(self.movimientos)}   demanda_diaria: {len(self.demanda)}")
        print(f"  OTIF: {otif / max(1, len(recibidas)):.1%}   a tiempo: {a_tiempo / max(1, len(recibidas)):.1%}")
        print(f"  Fill Rate de servicio: {fr_serv:.1%}   Fill Rate de proveedor: {fr_prov:.1%}")
        print(f"  Lead time promedio: {sum(lt) / max(1, len(lt)):.1f} dias")
        print(f"  Flete por unidad: {flete / max(1, unidades):.2f} MXN")
        print("  Utilizacion promedio / maxima: " + "  ".join(
            f"{ak} {sum(u) / len(u):.0%}/{max(u):.0%}" for ak, u in self.utilizacion.items()))
        print("  Condicion climatica de envios: " + ", ".join(f"{k} {v}" for k, v in sorted(clima.items())))


# ------------------------------------------------------------------ base de datos

def leer_productos(cur):
    cur.execute("SELECT producto_id, sku, costo_unitario FROM productos")
    filas = [a_dict(f, ("producto_id", "sku", "costo_unitario")) for f in cur.fetchall()]
    return {f["sku"]: {"producto_id": f["producto_id"], "costo_unitario": float(f["costo_unitario"])} for f in filas}


def escribir(cur, g):
    cur.execute("TRUNCATE plan_acciones, recomendaciones, envios, movimientos_inventario, detalle_orden_compra, "
                "ordenes_compra, demanda_diaria, almacenes, proveedores RESTART IDENTITY CASCADE")
    execute_values(cur, "INSERT INTO almacenes (almacen_id, nombre, ubicacion, capacidad_m3, latitud, longitud) VALUES %s",
                   [(a["almacen_id"], a["nombre"], a["ubicacion"], a["capacidad_m3"], a["latitud"], a["longitud"])
                    for a in g.alm.values()])
    execute_values(cur, "INSERT INTO proveedores (proveedor_id, nombre, pais, ciudad, calificacion, activo, "
                        "fecha_registro, latitud, longitud) VALUES %s",
                   [(p["proveedor_id"], p["nombre"], p["pais"], p["ciudad"], p["calificacion_inicial"], True,
                     datetime.combine(g.inicio - timedelta(days=365), time(9, 0)), p["latitud"], p["longitud"])
                    for p in g.prov.values()])
    execute_values(cur, "INSERT INTO ordenes_compra (orden_id, proveedor_id, fecha_orden, fecha_entrega_estim, "
                        "fecha_entrega_real, estatus, monto_total) VALUES %s", [tuple(o) for o in g.ordenes],
                   page_size=1000)
    execute_values(cur, "INSERT INTO detalle_orden_compra (detalle_id, orden_id, producto_id, cantidad, "
                        "precio_unitario, cantidad_recibida) VALUES %s", [tuple(d) for d in g.detalles],
                   page_size=1000)
    execute_values(cur, "INSERT INTO envios (envio_id, orden_id, proveedor_id, almacen_origen_id, fecha_salida, "
                        "fecha_llegada_estim, fecha_llegada_real, costo_flete, condicion_climatica, precipitacion_mm) "
                        "VALUES %s", g.envios, page_size=1000)
    execute_values(cur, "INSERT INTO movimientos_inventario (movimiento_id, almacen_id, producto_id, tipo_movimiento, "
                        "cantidad, fecha, orden_id) VALUES %s", g.movimientos, page_size=2000)
    execute_values(cur, "INSERT INTO demanda_diaria (fecha, almacen_id, producto_id, unidades_solicitadas, "
                        "unidades_entregadas) VALUES %s", g.demanda, page_size=2000)
    for tabla, columna in (("almacenes", "almacen_id"), ("proveedores", "proveedor_id"),
                           ("ordenes_compra", "orden_id"), ("detalle_orden_compra", "detalle_id"),
                           ("envios", "envio_id"), ("movimientos_inventario", "movimiento_id")):
        cur.execute(f"SELECT setval(pg_get_serial_sequence('{tabla}', '{columna}'), "
                    f"COALESCE((SELECT MAX({columna}) FROM {tabla}), 0) + 1, false)")


def guardar_verdad(g):
    salida = {
        "_meta": {
            "descripcion": "Eventos inyectados con verdad conocida para validar la deteccion de anomalias (CC-07).",
            "semilla": g.cfg["simulacion"]["semilla"],
            "generado": date.today().isoformat(),
        },
        "eventos": [],
    }
    for clave, v in g.verdad.items():
        salida["eventos"].append({
            **v["evento"],
            "orden_id": sorted(v["orden_id"]),
            "envio_id": sorted(v["envio_id"]),
            "detalle_id": sorted(v["detalle_id"]),
            "demanda_afectada": v["demanda"],
        })
    SALIDA_EVENTOS.write_text(json.dumps(salida, ensure_ascii=True, indent=1), encoding="utf-8")


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    volumen = json.loads(VOLUMEN.read_text(encoding="utf-8"))
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                productos = leer_productos(cur)
                g = Generador(cfg, productos, volumen).ejecutar()
                escribir(cur, g)
    finally:
        conn.close()
    guardar_verdad(g)
    g.resumen()
    print(f"Eventos inyectados: {SALIDA_EVENTOS.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()