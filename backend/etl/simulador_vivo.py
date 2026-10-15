"""Simulador en vivo de la operacion -> supply_chain_final (CC-09 y CC-22, control de cambios, riesgo R6).

Continua la operacion despues de la fecha de corte con las MISMAS reglas del generador de
12 meses (generar_operacion.Generador): demanda, politica de reorden, proveedores, transporte,
clima y cumplimiento. No duplica ninguna regla.

Reloj simulado (CC-22):
  - Empieza el dia siguiente a la fecha de corte base (ultimo dia de demanda_diaria).
  - Cada dia simulado se publica como eventos, uno por uno, con 10 a 30 segundos entre cada uno:
    recepciones, ordenes emitidas y, al final, el cierre de ventas del dia (18:00).
  - Nunca simula un dia que aun no termina: se detiene en el dia de ayer real.
  - Cada dia usa una semilla propia (semilla + fecha): misma base, mismos resultados.
  - Cada evento se guarda en su propia transaccion; si se interrumpe, retoma donde iba.
  - Nunca escribe una fecha de llegada futura en envios: las llegadas pendientes viven en
    simulador_estado.llegadas hasta que ocurren.

Cierre de cada dia:
  - refrescar_modelo_estrella_desde(): conserva score_anomalia de los 12 meses (CC-18).
  - Vuelve a correr pronostico, riesgo y recomendaciones (python -m analitica.<modulo>).
    Isolation Forest NO se recalcula en vivo: su validacion esta fijada contra los eventos
    inyectados de los 12 meses (CC-18).
  - Publica una alerta si el estado de una estacion del Resumen cambia (CC-16) y un evento
    por cada caso nuevo del Centro de soluciones (CC-19).

Clima (CC-04 y CC-22): los dias posteriores al corte usan Open-Meteo (API de pronostico con
past_days) con cache local en backend/etl/cache/clima_vivo; mismos umbrales del SMN.

Uso (desde backend, con .venv activo):
  python -m etl.simulador_vivo                  corre hasta el dia de ayer y espera el siguiente
  python -m etl.simulador_vivo --dias 3         simula 3 dias y termina
  python -m etl.simulador_vivo --sin-espera     sin pausas entre eventos (QA)
  python -m etl.simulador_vivo --estado         muestra el estado y termina
  python -m etl.simulador_vivo --reiniciar      regresa a la fecha de corte base y termina
Ctrl+C lo detiene en cualquier momento; al volver a ejecutarlo retoma donde iba.
"""
import argparse
import json
import random
import subprocess
import sys
import time as reloj
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from datetime import date, datetime, time, timedelta

from app.database import get_connection
from etl import generar_operacion as gen
from etl.descargar_clima import puntos_desde_config

BACKEND = gen.ETL.parent
CACHE_VIVO = gen.RAIZ / "backend" / "etl" / "cache" / "clima_vivo"
URL_PRONOSTICO = "https://api.open-meteo.com/v1/forecast"
MODELOS = ("pronostico", "riesgo", "recomendaciones")
NIVEL = {"EN_META": 0, "ATENCION": 1, "CRITICO": 2}
TEXTO_ESTADO = {"EN_META": "En meta", "ATENCION": "Atencion", "CRITICO": "Critico"}
CANDADO = 20261014                      # pg_advisory_lock: un solo simulador a la vez
ESPERA_AL_DIA_S = 600


# ------------------------------------------------------------------ utilidades

def ascii_seguro(texto, largo=200):
    """CC-11: la base guarda texto en ASCII."""
    limpio = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    return " ".join(limpio.split())[:largo]


def ts(texto):
    return datetime.fromisoformat(texto)


def dias_txt(n):
    return "1 dia" if n == 1 else f"{n} dias"


def fmt_valor(valor, unidad):
    if valor is None:
        return "sin dato"
    return f"{valor}%" if unidad == "%" else f"{valor} {unidad}"


# ------------------------------------------------------------------ clima de los dias simulados

def actualizar_clima_vivo(cfg):
    """Descarga una vez al dia el clima de Open-Meteo para los dias posteriores al corte.
    Si falla, usa la cache anterior; sin dato, el generador toma DESPEJADO (riesgo R1)."""
    CACHE_VIVO.mkdir(parents=True, exist_ok=True)
    hoy = date.today().isoformat()
    variables = cfg["clima"]["variables_diarias"]
    for clave, punto in puntos_desde_config(cfg).items():
        ruta = CACHE_VIVO / f"{clave}.json"
        try:
            if json.loads(ruta.read_text(encoding="utf-8"))["_meta"]["descargado"] == hoy:
                continue
        except (OSError, ValueError, KeyError):
            pass
        params = {
            "latitude": f"{punto['latitud']:.4f}", "longitude": f"{punto['longitud']:.4f}",
            "daily": ",".join(variables), "timezone": cfg["simulacion"]["zona_horaria"],
            "past_days": 92, "forecast_days": 16,
        }
        peticion = urllib.request.Request(f"{URL_PRONOSTICO}?{urllib.parse.urlencode(params)}",
                                          headers={"User-Agent": "supply-chain-dashboard/1.0 (proyecto academico)"})
        try:
            with urllib.request.urlopen(peticion, timeout=30) as resp:
                datos = json.loads(resp.read().decode("utf-8"))
            if "daily" not in datos or "time" not in datos["daily"]:
                raise ValueError(datos.get("reason", "respuesta sin datos diarios"))
            datos["_meta"] = {"clave": clave, "nombre": punto["nombre"], "descargado": hoy,
                              "fuente": "Open-Meteo.com, API de pronostico (past_days), licencia CC BY 4.0"}
            ruta.write_text(json.dumps(datos, ensure_ascii=True), encoding="utf-8")
            reloj.sleep(1)
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            print(f"  aviso: no se pudo actualizar el clima de {clave} ({e}); se usa la cache anterior")


def correr_modelos():
    """Pronostico, riesgo y recomendaciones en procesos separados: si uno falla, el simulador sigue."""
    for modulo in MODELOS:
        inicio = reloj.time()
        r = subprocess.run([sys.executable, "-m", f"analitica.{modulo}"], cwd=BACKEND,
                           capture_output=True, text=True, timeout=900)
        if r.returncode == 0:
            print(f"  analitica.{modulo}: listo en {reloj.time() - inicio:.1f} s")
        else:
            ultimas = " | ".join((r.stderr or r.stdout).strip().splitlines()[-3:])
            print(f"  aviso: analitica.{modulo} termino con error: {ultimas}")


def fusionar_clima(clima):
    """El archivo historico manda hasta el corte; el clima en vivo solo agrega dias que no tiene."""
    for archivo in CACHE_VIVO.glob("*.json"):
        try:
            diario = json.loads(archivo.read_text(encoding="utf-8"))["daily"]
        except (OSError, ValueError, KeyError):
            continue
        destino = clima.datos.setdefault(archivo.stem, {})
        for t, c, p in zip(diario["time"], diario["weather_code"], diario["precipitation_sum"]):
            destino.setdefault(t, (c, p))


# ------------------------------------------------------------------ simulador

class Simulador:
    def __init__(self, conn, cfg, volumen, sin_espera=False):
        self.conn, self.cfg, self.volumen = conn, cfg, volumen
        self.sin_espera = sin_espera
        self.pausa = random.Random()
        with conn:
            with conn.cursor() as cur:
                self.productos = gen.leer_productos(cur)
        self.g = gen.Generador(cfg, self.productos, volumen)
        fusionar_clima(self.g.clima)
        g = self.g
        self.pid = {sku: p["producto_id"] for sku, p in self.productos.items()}
        self.sku_de = {v: k for k, v in self.pid.items()}
        self.aid = {ak: a["almacen_id"] for ak, a in g.alm.items()}
        self.ak_de = {v: k for k, v in self.aid.items()}
        self.prov_id = {p["proveedor_id"]: p for p in g.prov.values()}

    # ----------------------------------------------------------- estado
    def leer_estado(self, cur):
        cur.execute("SELECT * FROM simulador_estado WHERE id = 1")
        return cur.fetchone()

    def guardar(self, cur, **campos):
        partes, valores = [], []
        for k, v in campos.items():
            if k in ("plan", "llegadas", "estados_previos"):
                partes.append(f"{k} = %s::jsonb")
                valores.append(None if v is None else json.dumps(v, ensure_ascii=True))
            else:
                partes.append(f"{k} = %s")
                valores.append(v)
        cur.execute(f"UPDATE simulador_estado SET {', '.join(partes)}, actualizado = NOW() WHERE id = 1", valores)

    def publicar(self, cur, dia, ocurrido, tipo, severidad, modulo, titulo, datos=None,
                 orden_id=None, proveedor_id=None, almacen_id=None):
        titulo = ascii_seguro(titulo)
        cur.execute(
            "INSERT INTO eventos_vivo (fecha_simulada, ocurrido, tipo, severidad, modulo, titulo, datos, "
            "orden_id, proveedor_id, almacen_id) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s) "
            "RETURNING evento_id",
            (dia, ocurrido, tipo, severidad, modulo, titulo, json.dumps(datos or {}, ensure_ascii=True),
             orden_id, proveedor_id, almacen_id))
        evento_id = cur.fetchone()["evento_id"]
        print(f"  [{evento_id}] {ocurrido:%Y-%m-%d %H:%M} {severidad:<8} {titulo}")
        return evento_id

    # ----------------------------------------------------------- lectura de la base
    def leer_stock(self, cur):
        stock = {(ak, s): 0 for ak in self.g.alm for s in self.g.skus}
        cur.execute("SELECT almacen_id, producto_id, "
                    "SUM(CASE WHEN tipo_movimiento = 'ENTRADA' THEN cantidad ELSE -cantidad END) AS stock "
                    "FROM movimientos_inventario GROUP BY almacen_id, producto_id")
        for f in cur.fetchall():
            stock[(self.ak_de[f["almacen_id"]], self.sku_de[f["producto_id"]])] = int(f["stock"])
        return stock

    def leer_transito(self, cur):
        transito = defaultdict(int)
        cur.execute("SELECT e.almacen_origen_id AS almacen_id, d.producto_id, SUM(d.cantidad) AS unidades "
                    "FROM ordenes_compra o JOIN envios e ON e.orden_id = o.orden_id "
                    "JOIN detalle_orden_compra d ON d.orden_id = o.orden_id "
                    "WHERE o.estatus = 'EN_TRANSITO' GROUP BY e.almacen_origen_id, d.producto_id")
        for f in cur.fetchall():
            transito[(self.ak_de[f["almacen_id"]], self.sku_de[f["producto_id"]])] = int(f["unidades"])
        return transito

    def leer_historial(self, cur, hasta):
        ventana = self.g.pol["ventana_demanda_media_dias"]
        historial = {(ak, s): deque(maxlen=ventana) for ak in self.g.alm for s in self.g.skus}
        cur.execute("SELECT almacen_id, producto_id, unidades_solicitadas FROM demanda_diaria "
                    "WHERE fecha > %s AND fecha <= %s ORDER BY fecha",
                    (hasta - timedelta(days=ventana), hasta))
        for f in cur.fetchall():
            historial[(self.ak_de[f["almacen_id"]], self.sku_de[f["producto_id"]])].append(
                int(f["unidades_solicitadas"]))
        return historial

    # ----------------------------------------------------------- primera ejecucion
    def iniciar(self, cur):
        """Reproduce los 12 meses en memoria, verifica que coinciden con la base y toma el
        desenlace (llegada y cantidad recibida) de las ordenes que estaban en transito al corte."""
        cur.execute("SELECT MAX(fecha) AS corte FROM demanda_diaria")
        corte = cur.fetchone()["corte"]
        g12 = gen.Generador(self.cfg, self.productos, self.volumen)
        if g12.fin != corte:
            raise RuntimeError(f"La fecha de corte de la base ({corte}) no es la de config_simulacion.json ({g12.fin})")
        planes = []
        original = g12.planear_orden

        def capturar(*args):
            plan = original(*args)
            planes.append(plan)
            return plan

        g12.planear_orden = capturar
        g12.ejecutar()

        if self.leer_stock(cur) != g12.stock_final:
            raise RuntimeError("El inventario de la base no coincide con el generador; no se puede continuar en vivo")
        en_transito_gen = [e[1] for e in g12.envios if e[6] is None]
        cur.execute("SELECT o.orden_id, e.envio_id, e.almacen_origen_id AS almacen_id, o.proveedor_id, "
                    "o.fecha_entrega_estim FROM ordenes_compra o JOIN envios e ON e.orden_id = o.orden_id "
                    "WHERE o.estatus = 'EN_TRANSITO' ORDER BY o.orden_id")
        ordenes = cur.fetchall()
        if [o["orden_id"] for o in ordenes] != en_transito_gen:
            raise RuntimeError("Las ordenes en transito de la base no coinciden con el generador")

        llegadas = []
        for o in ordenes:
            plan = planes[o["orden_id"] - 1]
            recibida = {ln["sku"]: ln["recibida"] for ln in plan["lineas"]}
            cur.execute("SELECT detalle_id, producto_id, cantidad FROM detalle_orden_compra "
                        "WHERE orden_id = %s ORDER BY detalle_id", (o["orden_id"],))
            lineas = [{"detalle_id": d["detalle_id"], "producto_id": d["producto_id"],
                       "cantidad": int(d["cantidad"]), "recibida": recibida[self.sku_de[d["producto_id"]]]}
                      for d in cur.fetchall()]
            llegadas.append({"orden_id": o["orden_id"], "envio_id": o["envio_id"], "almacen_id": o["almacen_id"],
                             "proveedor_id": o["proveedor_id"],
                             "llegada_estim": o["fecha_entrega_estim"].isoformat(),
                             "llegada_real": plan["llegada_real"].isoformat(), "lineas": lineas})
        cur.execute("INSERT INTO simulador_estado (id, fecha_corte_base, dia_cerrado, llegadas) "
                    "VALUES (1, %s, %s, %s::jsonb)", (corte, corte, json.dumps(llegadas, ensure_ascii=True)))
        print(f"Simulador iniciado en la fecha de corte {corte}: base verificada contra el generador, "
              f"{len(llegadas)} ordenes en transito")

    # ----------------------------------------------------------- plan del dia
    def planear_dia(self, cur, estado):
        g = self.g
        dia = estado["dia_cerrado"] + timedelta(days=1)
        g.rng = random.Random(f"{g.cfg['simulacion']['semilla']}:{dia.isoformat()}")
        stock = self.leer_stock(cur)
        transito = self.leer_transito(cur)
        historial = self.leer_historial(cur, estado["dia_cerrado"])
        eventos = []

        # 1. recepciones del dia (misma regla del generador: se reciben antes de vender)
        for l in sorted(estado["llegadas"], key=lambda x: x["llegada_real"]):
            if ts(l["llegada_real"]).date() > dia:
                continue
            for ln in l["lineas"]:
                clave = (self.ak_de[l["almacen_id"]], self.sku_de[ln["producto_id"]])
                stock[clave] += ln["recibida"]
                transito[clave] -= ln["cantidad"]
            eventos.append({"tipo": "RECEPCION", "hora": l["llegada_real"], "orden_id": l["orden_id"]})

        # 2. demanda y ventas del dia
        ventas = []
        for (ak, sku) in stock:
            solicitada, _ = g.demanda_del_dia(dia, ak, sku)
            entregada = min(solicitada, stock[(ak, sku)])
            stock[(ak, sku)] -= entregada
            historial[(ak, sku)].append(solicitada)
            ventas.append([self.aid[ak], self.pid[sku], solicitada, entregada])

        # 3. revision de inventario y ordenes (generar_operacion.revisar_inventario y planear_orden)
        for (pk, ak), lineas in g.revisar_inventario(stock, transito, historial):
            plan = g.planear_orden(dia, pk, ak, lineas)
            eventos.append({"tipo": "ORDEN", "hora": plan["ts_orden"].isoformat(), "orden": {
                "proveedor_id": g.prov[pk]["proveedor_id"], "almacen_id": self.aid[ak],
                "salida": plan["salida"].isoformat(), "llegada_estim": plan["llegada_estim"].isoformat(),
                "llegada_real": plan["llegada_real"].isoformat(), "costo_flete": plan["costo_flete"],
                "condicion": plan["condicion"], "precipitacion_mm": plan["precipitacion_mm"],
                "lineas": [{"producto_id": self.pid[ln["sku"]], "cantidad": ln["cantidad"],
                            "precio": ln["precio"], "recibida": ln["recibida"]} for ln in plan["lineas"]]}})

        eventos.sort(key=lambda e: e["hora"])
        eventos.append({"tipo": "VENTAS", "hora": datetime.combine(dia, time(18, 0)).isoformat(), "ventas": ventas})
        return dia, eventos

    # ----------------------------------------------------------- aplicar eventos
    def aplicar(self, cur, dia, ev, llegadas):
        if ev["tipo"] == "RECEPCION":
            self.aplicar_recepcion(cur, dia, ev, llegadas)
        elif ev["tipo"] == "ORDEN":
            self.aplicar_orden(cur, dia, ev, llegadas)
        else:
            self.aplicar_ventas(cur, dia, ev)

    def aplicar_recepcion(self, cur, dia, ev, llegadas):
        l = next(x for x in llegadas if x["orden_id"] == ev["orden_id"])
        llegadas.remove(l)
        llegada = ts(l["llegada_real"])
        for ln in l["lineas"]:
            cur.execute("INSERT INTO movimientos_inventario (almacen_id, producto_id, tipo_movimiento, cantidad, "
                        "fecha, orden_id) VALUES (%s, %s, 'ENTRADA', %s, %s, %s)",
                        (l["almacen_id"], ln["producto_id"], ln["recibida"], llegada, l["orden_id"]))
            cur.execute("UPDATE detalle_orden_compra SET cantidad_recibida = %s WHERE detalle_id = %s",
                        (ln["recibida"], ln["detalle_id"]))
        pedidas = sum(ln["cantidad"] for ln in l["lineas"])
        recibidas = sum(ln["recibida"] for ln in l["lineas"])
        parcial = recibidas < pedidas
        cur.execute("UPDATE ordenes_compra SET fecha_entrega_real = %s, estatus = %s WHERE orden_id = %s",
                    (llegada, "RECIBIDA_PARCIAL" if parcial else "RECIBIDA", l["orden_id"]))
        cur.execute("UPDATE envios SET fecha_llegada_real = %s WHERE envio_id = %s", (llegada, l["envio_id"]))

        tarde = (llegada.date() - ts(l["llegada_estim"]).date()).days
        prov = self.prov_id[l["proveedor_id"]]["nombre"]
        alm = self.g.alm[self.ak_de[l["almacen_id"]]]["nombre"]
        envio = f"Envio ENV-{l['envio_id']:04d} de {prov}"
        if parcial:
            tipo, sev, modulo = "RECEPCION_PARCIAL", "ATENCION", "proveedores"
            titulo = f"{envio} llego incompleto a {alm}: {recibidas:,} de {pedidas:,} unidades"
            if tarde > 0:
                titulo += f", {dias_txt(tarde)} tarde"
        elif tarde > 0:
            tipo, sev, modulo = "RECEPCION_TARDIA", "ATENCION", "logistica"
            titulo = f"{envio} llego {dias_txt(tarde)} tarde a {alm}"
        else:
            tipo, sev, modulo = "RECEPCION", "INFO", "logistica"
            titulo = f"{envio} llego a tiempo a {alm}"
        self.publicar(cur, dia, llegada, tipo, sev, modulo, titulo,
                      {"envio_id": l["envio_id"], "dias_tarde": max(0, tarde), "unidades_pedidas": pedidas,
                       "unidades_recibidas": recibidas, "origen": "SIMULADO"},
                      orden_id=l["orden_id"], proveedor_id=l["proveedor_id"], almacen_id=l["almacen_id"])

    def aplicar_orden(self, cur, dia, ev, llegadas):
        o = ev["orden"]
        emitida = ts(ev["hora"])
        estimada = datetime.combine(date.fromisoformat(o["llegada_estim"]), time(12, 0))
        monto = round(sum(ln["cantidad"] * ln["precio"] for ln in o["lineas"]), 2)
        cur.execute("INSERT INTO ordenes_compra (proveedor_id, fecha_orden, fecha_entrega_estim, fecha_entrega_real, "
                    "estatus, monto_total) VALUES (%s, %s, %s, NULL, 'EN_TRANSITO', %s) RETURNING orden_id",
                    (o["proveedor_id"], emitida, estimada, monto))
        orden_id = cur.fetchone()["orden_id"]
        lineas = []
        for ln in o["lineas"]:
            cur.execute("INSERT INTO detalle_orden_compra (orden_id, producto_id, cantidad, precio_unitario, "
                        "cantidad_recibida) VALUES (%s, %s, %s, %s, NULL) RETURNING detalle_id",
                        (orden_id, ln["producto_id"], ln["cantidad"], ln["precio"]))
            lineas.append({"detalle_id": cur.fetchone()["detalle_id"], "producto_id": ln["producto_id"],
                           "cantidad": ln["cantidad"], "recibida": ln["recibida"]})
        cur.execute("INSERT INTO envios (orden_id, proveedor_id, almacen_origen_id, fecha_salida, fecha_llegada_estim, "
                    "fecha_llegada_real, costo_flete, condicion_climatica, precipitacion_mm) "
                    "VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, %s) RETURNING envio_id",
                    (orden_id, o["proveedor_id"], o["almacen_id"],
                     datetime.combine(date.fromisoformat(o["salida"]), time(7, 0)), estimada,
                     o["costo_flete"], o["condicion"], o["precipitacion_mm"]))
        envio_id = cur.fetchone()["envio_id"]
        llegadas.append({"orden_id": orden_id, "envio_id": envio_id, "almacen_id": o["almacen_id"],
                         "proveedor_id": o["proveedor_id"], "llegada_estim": estimada.isoformat(),
                         "llegada_real": o["llegada_real"], "lineas": lineas})

        prov = self.prov_id[o["proveedor_id"]]["nombre"]
        alm = self.g.alm[self.ak_de[o["almacen_id"]]]["nombre"]
        unidades = sum(ln["cantidad"] for ln in o["lineas"])
        titulo = (f"Orden OC-{orden_id:04d} a {prov}: {unidades:,} unidades para {alm}, "
                  f"llegada estimada {estimada:%d/%m}")
        if o["condicion"] in ("LLUVIA_FUERTE", "TORMENTA"):
            titulo += f" ({o['condicion'].replace('_', ' ').lower()} en la ruta)"
        self.publicar(cur, dia, emitida, "ORDEN_EMITIDA", "INFO", "compras", titulo,
                      {"envio_id": envio_id, "unidades": unidades, "monto_usd": monto,
                       "llegada_estimada": estimada.date().isoformat(), "condicion_climatica": o["condicion"],
                       "origen": "SIMULADO"},
                      orden_id=orden_id, proveedor_id=o["proveedor_id"], almacen_id=o["almacen_id"])

    def aplicar_ventas(self, cur, dia, ev):
        cierre = ts(ev["hora"])
        for almacen_id, producto_id, solicitada, entregada in ev["ventas"]:
            cur.execute("INSERT INTO demanda_diaria (fecha, almacen_id, producto_id, unidades_solicitadas, "
                        "unidades_entregadas) VALUES (%s, %s, %s, %s, %s)",
                        (dia, almacen_id, producto_id, solicitada, entregada))
            if entregada:
                cur.execute("INSERT INTO movimientos_inventario (almacen_id, producto_id, tipo_movimiento, cantidad, "
                            "fecha, orden_id) VALUES (%s, %s, 'SALIDA', %s, %s, NULL)",
                            (almacen_id, producto_id, entregada, cierre))
        sol = sum(v[2] for v in ev["ventas"])
        ent = sum(v[3] for v in ev["ventas"])
        quiebres = sum(1 for v in ev["ventas"] if v[3] < v[2])
        fill = round(100.0 * ent / sol, 1) if sol else 100.0
        sev = "CRITICO" if fill < 90 else "ATENCION" if fill < 95 else "INFO"   # umbrales de CC-16
        titulo = f"Cierre de ventas: {ent:,} de {sol:,} unidades entregadas, nivel de servicio {fill}%"
        if quiebres:
            titulo += f"; {quiebres} combinaciones de almacen y producto sin stock suficiente"
        self.publicar(cur, dia, cierre, "VENTAS_DIA", sev, "inventarios", titulo,
                      {"unidades_solicitadas": sol, "unidades_entregadas": ent, "fill_rate": fill,
                       "quiebres": quiebres, "origen": "SIMULADO"})

    # ----------------------------------------------------------- cierre del dia
    def estados_estaciones(self):
        """Estado de las 5 estaciones del Resumen con la misma funcion del endpoint (CC-16)."""
        try:
            from app import kpis
            respuesta = kpis.estaciones(dias=30)
            return {e["clave"]: {k: e[k] for k in ("nombre", "modulo", "etiqueta", "unidad", "valor", "meta", "estado")}
                    for e in respuesta["estaciones"]}
        except Exception as e:                                   # el cierre no debe detener al simulador
            print(f"  aviso: no se pudo calcular el estado de las estaciones ({e})")
            return None

    def casos_abiertos(self, cur):
        cur.execute("SELECT * FROM recomendaciones WHERE estado IN ('NUEVA', 'EN_REVISION')")
        return {f["titulo"]: f for f in cur.fetchall()}

    def cerrar_dia(self, estado):
        dia = estado["dia_cerrado"]
        cierre = datetime.combine(dia, time(18, 30))
        base = estado["fecha_corte_base"]
        with self.conn:
            with self.conn.cursor() as cur:
                antes = self.casos_abiertos(cur)
                cur.execute("SELECT * FROM refrescar_modelo_estrella_desde(%s)", (base + timedelta(days=1),))
        correr_modelos()
        estados = self.estados_estaciones()
        with self.conn:
            with self.conn.cursor() as cur:
                previos = estado["estados_previos"] or {}
                for clave, nuevo in (estados or {}).items():
                    viejo = previos.get(clave)
                    if not viejo or viejo["estado"] not in NIVEL or nuevo["estado"] not in NIVEL:
                        continue
                    if NIVEL[nuevo["estado"]] == NIVEL[viejo["estado"]]:
                        continue
                    empeora = NIVEL[nuevo["estado"]] > NIVEL[viejo["estado"]]
                    titulo = (f"{nuevo['nombre']}: {nuevo['etiqueta']} {fmt_valor(nuevo['valor'], nuevo['unidad'])} "
                              f"{'pasa' if empeora else 'vuelve'} de {TEXTO_ESTADO[viejo['estado']]} a "
                              f"{TEXTO_ESTADO[nuevo['estado']]} (meta {fmt_valor(nuevo['meta'], nuevo['unidad'])})")
                    self.publicar(cur, dia, cierre, "ALERTA_KPI", nuevo["estado"] if empeora else "INFO",
                                  nuevo["modulo"], titulo,
                                  {"estacion": clave, "estado_anterior": viejo["estado"], "estado": nuevo["estado"],
                                   "valor": nuevo["valor"], "meta": nuevo["meta"]})
                for titulo, caso in self.casos_abiertos(cur).items():
                    if titulo in antes:
                        continue
                    impacto = next((v for k, v in caso.items() if k.startswith("impacto") and v is not None), None)
                    texto = f"Nuevo caso en el Centro de soluciones: {titulo}"
                    if impacto is not None:
                        texto += f" ({float(impacto):,.0f} MXN en juego)"
                    severidad = caso.get("severidad") if caso.get("severidad") in ("ATENCION", "CRITICO") else "ATENCION"
                    self.publicar(cur, dia, cierre, "CASO_NUEVO", severidad, "ia", texto,
                                  {"recomendacion_id": caso.get("recomendacion_id")})
                self.guardar(cur, plan=None, siguiente=0,
                             estados_previos=estados if estados is not None else estado["estados_previos"])
        print(f"Dia {dia} cerrado.")

    # ----------------------------------------------------------- ciclo principal
    def esperar(self):
        if not self.sin_espera:
            reloj.sleep(self.pausa.uniform(10, 30))

    def ejecutar(self, dias_max=None):
        hechos = 0
        while True:
            with self.conn:
                with self.conn.cursor() as cur:
                    estado = self.leer_estado(cur)
                    if estado is None:
                        self.iniciar(cur)
                        estado = self.leer_estado(cur)
            if estado["estados_previos"] is None and not (estado["plan"] or {}).get("cierre"):
                previos = self.estados_estaciones()
                with self.conn:
                    with self.conn.cursor() as cur:
                        self.guardar(cur, estados_previos=previos)
                estado["estados_previos"] = previos

            if (estado["plan"] or {}).get("cierre"):
                self.cerrar_dia(estado)
                hechos += 1
                if dias_max and hechos >= dias_max:
                    return
                continue

            if estado["plan"] and estado["dia_en_curso"]:
                dia, eventos = estado["dia_en_curso"], estado["plan"]["eventos"]
                print(f"Retomando el dia {dia} en el evento {estado['siguiente'] + 1} de {len(eventos)}")
            else:
                dia = estado["dia_cerrado"] + timedelta(days=1)
                if dia > date.today() - timedelta(days=1):
                    self.al_dia(estado)
                    if dias_max or self.sin_espera:
                        return
                    print(f"Simulacion al dia. Siguiente revision en {ESPERA_AL_DIA_S // 60} minutos (Ctrl+C para salir).")
                    reloj.sleep(ESPERA_AL_DIA_S)
                    actualizar_clima_vivo(self.cfg)
                    fusionar_clima(self.g.clima)
                    continue
                with self.conn:
                    with self.conn.cursor() as cur:
                        dia, eventos = self.planear_dia(cur, estado)
                        self.guardar(cur, dia_en_curso=dia, plan={"eventos": eventos}, siguiente=0)
                print(f"Dia simulado {dia}: {len(eventos)} eventos")

            llegadas = estado["llegadas"]
            for i in range(estado["siguiente"] if estado["plan"] else 0, len(eventos)):
                with self.conn:
                    with self.conn.cursor() as cur:
                        self.aplicar(cur, dia, eventos[i], llegadas)
                        if i == len(eventos) - 1:
                            self.guardar(cur, dia_cerrado=dia, dia_en_curso=None, plan={"cierre": True},
                                         siguiente=0, llegadas=llegadas)
                        else:
                            self.guardar(cur, siguiente=i + 1, llegadas=llegadas)
                if i < len(eventos) - 1:
                    self.esperar()

    def al_dia(self, estado):
        with self.conn:
            with self.conn.cursor() as cur:
                cur.execute("SELECT tipo, fecha_simulada FROM eventos_vivo ORDER BY evento_id DESC LIMIT 1")
                ultimo = cur.fetchone()
                if ultimo and ultimo["tipo"] == "SIMULACION_AL_DIA" and ultimo["fecha_simulada"] == estado["dia_cerrado"]:
                    return
                self.publicar(cur, estado["dia_cerrado"], datetime.combine(estado["dia_cerrado"], time(23, 59)),
                              "SIMULACION_AL_DIA", "INFO", "resumen",
                              f"Simulacion al dia: operacion simulada hasta el {estado['dia_cerrado']:%d/%m/%Y}",
                              {"dia_cerrado": estado["dia_cerrado"].isoformat()})


# ------------------------------------------------------------------ comandos

def mostrar_estado(conn):
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM simulador_estado WHERE id = 1")
            e = cur.fetchone()
            cur.execute("SELECT COUNT(*) AS n, MAX(evento_id) AS ultimo FROM eventos_vivo")
            ev = cur.fetchone()
            cur.execute("SELECT MAX(fecha) AS corte FROM demanda_diaria")
            corte = cur.fetchone()["corte"]
    if e is None:
        print(f"Simulador sin iniciar. Fecha de corte de los datos: {corte}")
        return
    print(f"Fecha de corte base: {e['fecha_corte_base']}   ultimo dia cerrado: {e['dia_cerrado']}   corte actual: {corte}")
    if e["plan"] and e["dia_en_curso"]:
        print(f"Dia en curso: {e['dia_en_curso']}, evento {e['siguiente'] + 1} de {len(e['plan']['eventos'])}")
    elif e["plan"]:
        print("Cierre del ultimo dia pendiente")
    print(f"Llegadas pendientes: {len(e['llegadas'])}   eventos publicados: {ev['n']} (ultimo id {ev['ultimo']})")


def reiniciar(conn):
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS existe FROM simulador_estado WHERE id = 1")
            if cur.fetchone() is None:
                print("El simulador no esta iniciado: la base ya esta en la fecha de corte base. No hay nada que reiniciar.")
                return
            cur.execute("SELECT * FROM reiniciar_simulador_vivo()")
            r = cur.fetchone()
            cur.execute("INSERT INTO eventos_vivo (fecha_simulada, ocurrido, tipo, severidad, modulo, titulo) "
                        "VALUES (%s, %s, 'SIMULACION_REINICIADA', 'INFO', 'resumen', %s)",
                        (r["fecha_corte"], datetime.combine(r["fecha_corte"], time(23, 59)),
                         f"Simulacion reiniciada en la fecha de corte {r['fecha_corte']:%d/%m/%Y}"))
    print(f"Reiniciado al {r['fecha_corte']}: {r['ordenes_borradas']} ordenes en vivo borradas, "
          f"{r['ordenes_restauradas']} ordenes regresaron a EN_TRANSITO")
    correr_modelos()


def main():
    parser = argparse.ArgumentParser(description="Simulador en vivo de la operacion (CC-09, CC-22).")
    parser.add_argument("--dias", type=int, help="simula N dias y termina")
    parser.add_argument("--sin-espera", action="store_true", help="sin pausas entre eventos (QA)")
    parser.add_argument("--estado", action="store_true", help="muestra el estado y termina")
    parser.add_argument("--reiniciar", action="store_true", help="regresa a la fecha de corte base y termina")
    args = parser.parse_args()

    cfg = json.loads(gen.CONFIG.read_text(encoding="utf-8"))
    volumen = json.loads(gen.VOLUMEN.read_text(encoding="utf-8"))
    conn = get_connection()
    try:
        if args.estado:
            mostrar_estado(conn)
            return 0
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s) AS libre", (CANDADO,))
            libre = cur.fetchone()["libre"]
        conn.commit()
        if not libre:
            print("Ya hay un simulador en ejecucion en otra ventana; detengalo antes de continuar.")
            return 1
        if args.reiniciar:
            reiniciar(conn)
            return 0
        actualizar_clima_vivo(cfg)
        sim = Simulador(conn, cfg, volumen, sin_espera=args.sin_espera)
        sim.ejecutar(args.dias)
        return 0
    except KeyboardInterrupt:
        print("\nSimulador detenido. Al volver a ejecutarlo retoma donde iba.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())