"""Deteccion de anomalias con Isolation Forest, validada contra eventos inyectados (CC-07).

1. Compras (un registro por renglon recibido). Variables relativas a lo normal de
   cada combinacion, para comparar productos y rutas distintos:
     precio_rel  = log(precio / mediana del precio del producto con ese proveedor)
     lead_rel    = log(lead time / mediana del proveedor hacia ese almacen)
     flete_rel   = log(flete del envio / mediana del flete del proveedor hacia ese almacen)
     faltante    = 1 - recibido / ordenado
   IsolationForest(contaminacion 6%, semilla fija). El score (0 a 1, mayor es mas raro)
   se guarda en fact_supply_chain.score_anomalia.

2. Demanda (por almacen, producto y dia). Variable: cociente entre la media de 7 dias y
   la de los 28 dias previos, dividido entre el mismo cociente de toda la red, para que
   Buen Fin o Navidad (que mueven a todos los productos) no cuenten como anomalia.

   Un cambio de nivel solo es detectable mientras no entra en la media de 28 dias, por eso
   cada evento de demanda se evalua por si se detecto y cuantos dias tardo, en sus primeros
   35 dias, ademas de las falsas alarmas por semana.

Validacion: se compara contra backend/etl/datos/eventos_inyectados.json (verdad conocida)
y se reporta precision, exhaustividad (recall) y F1, mas la exhaustividad por evento.
El resultado se guarda en backend/analitica/evaluacion_anomalias.json como evidencia.
"""
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from analitica.iforest import IsolationForest

from app.database import get_connection

BACKEND = Path(__file__).resolve().parents[1]
VERDAD = BACKEND / "etl" / "datos" / "eventos_inyectados.json"
CONFIG = BACKEND / "etl" / "datos" / "config_simulacion.json"
SALIDA = BACKEND / "analitica" / "evaluacion_anomalias.json"
CONTAMINACION = 0.06          # compras: ~6% de las ordenes llevan un evento inyectado
CONTAMINACION_DEMANDA = 0.01  # demanda: los cambios de nivel son raros entre ~13 mil series-dia
VENTANA_DETECCION_DIAS = 35   # un cambio de nivel solo es visible hasta que entra en la media de 28 dias
SEMILLA = 20260930
VARIABLES = ["precio_rel", "lead_rel", "flete_rel", "faltante"]


def _metricas(real, predicho):
    real, predicho = np.asarray(real, bool), np.asarray(predicho, bool)
    vp = int((real & predicho).sum())
    fp = int((~real & predicho).sum())
    fn = int((real & ~predicho).sum())
    precision = vp / (vp + fp) if vp + fp else 0.0
    recall = vp / (vp + fn) if vp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"verdaderos_positivos": vp, "falsos_positivos": fp, "falsos_negativos": fn,
            "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


def _compras(cur):
    cur.execute("""
        SELECT d.detalle_id, d.orden_id, d.producto_id, o.proveedor_id, e.almacen_origen_id AS almacen_id,
               o.fecha_entrega_real::date AS fecha, d.cantidad, d.cantidad_recibida, d.precio_unitario,
               e.costo_flete, EXTRACT(EPOCH FROM (o.fecha_entrega_real - o.fecha_orden)) / 86400 AS lead
        FROM detalle_orden_compra d
        JOIN ordenes_compra o ON o.orden_id = d.orden_id
        JOIN envios e ON e.orden_id = d.orden_id
        WHERE o.fecha_entrega_real IS NOT NULL
        ORDER BY d.detalle_id   -- orden fijo: Isolation Forest submuestrea por posicion (CC-18)
    """)
    df = pd.DataFrame([dict(r) for r in cur.fetchall()])
    for c in ("cantidad", "cantidad_recibida", "precio_unitario", "costo_flete", "lead"):
        df[c] = df[c].astype(float)
    df["precio_rel"] = np.log(df["precio_unitario"] / df.groupby(["producto_id", "proveedor_id"])["precio_unitario"].transform("median"))
    df["lead_rel"] = np.log(df["lead"] / df.groupby(["proveedor_id", "almacen_id"])["lead"].transform("median"))
    df["flete_rel"] = np.log(df["costo_flete"] / df.groupby(["proveedor_id", "almacen_id"])["costo_flete"].transform("median"))
    df["faltante"] = 1 - df["cantidad_recibida"] / df["cantidad"]
    df[VARIABLES] = df[VARIABLES].fillna(0.0)
    return df


def _explicar(df):
    """Variable que mas se aleja de lo normal en cada renglon (desviacion robusta)."""
    z = pd.DataFrame(index=df.index)
    for v in VARIABLES:
        mad = (df[v] - df[v].median()).abs().median() or 1e-6
        z[v] = (df[v] - df[v].median()).abs() / mad
    return z.idxmax(axis=1)


def detectar_compras(df):
    modelo = IsolationForest(n_estimators=300, contamination=CONTAMINACION, random_state=SEMILLA)
    x = df[VARIABLES].to_numpy()
    modelo.fit(x)
    bruto = -modelo.score_samples(x)
    df["score"] = (bruto - bruto.min()) / (bruto.max() - bruto.min())
    df["anomalia"] = modelo.predict(x) == -1
    df["causa"] = _explicar(df)
    return df


def _demanda(cur):
    cur.execute("SELECT fecha, almacen_id, producto_id, unidades_solicitadas AS u FROM demanda_diaria")
    df = pd.DataFrame([dict(r) for r in cur.fetchall()])
    df["u"] = df["u"].astype(float)
    df["fecha"] = pd.to_datetime(df["fecha"])
    piv = df.pivot_table(index="fecha", columns=["almacen_id", "producto_id"], values="u").sort_index()
    red = piv.sum(axis=1)

    def cociente(s):
        return s.rolling(7).mean() / s.shift(7).rolling(28).mean()

    rel = piv.apply(cociente).div(cociente(red), axis=0)
    largo = rel.stack(level=[0, 1], future_stack=True).rename("cociente").reset_index().dropna()
    largo["cociente"] = np.log(largo["cociente"].clip(lower=1e-3))
    return largo


def detectar_demanda(largo):
    modelo = IsolationForest(n_estimators=300, contamination=CONTAMINACION_DEMANDA, random_state=SEMILLA)
    x = largo[["cociente"]].to_numpy()
    modelo.fit(x)
    largo["anomalia"] = modelo.predict(x) == -1
    return largo


def main():
    verdad = json.loads(VERDAD.read_text(encoding="utf-8"))["eventos"]
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                compras = detectar_compras(_compras(cur))
                # el generador asigna almacen_id en el orden de config_simulacion.json
                almacen_por_clave = {a["clave"]: i + 1 for i, a in enumerate(
                    json.loads(CONFIG.read_text(encoding="utf-8"))["almacenes"])}
                cur.execute("SELECT producto_id, sku FROM productos")
                producto_por_sku = {r["sku"]: r["producto_id"] for r in cur.fetchall()}
                demanda = detectar_demanda(_demanda(cur))

                # score_anomalia en fact_supply_chain (mismo grano: renglon recibido)
                cur.execute("UPDATE fact_supply_chain SET score_anomalia = NULL")
                for r in compras.itertuples():
                    cur.execute("UPDATE fact_supply_chain SET score_anomalia = %s "
                                "WHERE fecha_id = %s AND producto_id = %s AND proveedor_id = %s "
                                "AND almacen_id = %s AND unidades_solicitadas = %s",
                                (round(float(r.score), 4), r.fecha, int(r.producto_id), int(r.proveedor_id),
                                 int(r.almacen_id), float(r.cantidad)))
    finally:
        conn.close()

    # --- evaluacion de compras, por orden (una orden es anomala si algun renglon lo es)
    eventos_compra = [e for e in verdad if e["orden_id"]]
    ordenes_verdad = set().union(*[set(e["orden_id"]) for e in eventos_compra])
    por_orden = compras.groupby("orden_id")["anomalia"].any()
    eval_compras = _metricas([o in ordenes_verdad for o in por_orden.index], por_orden.to_numpy())
    eval_compras["ordenes_evaluadas"] = int(len(por_orden))
    eval_compras["ordenes_anomalas_reales"] = int(sum(o in ordenes_verdad for o in por_orden.index))
    eval_compras["por_evento"] = {
        e["clave"]: {"ordenes": len(set(e["orden_id"]) & set(por_orden.index)),
                     "detectadas": int(sum(bool(por_orden.get(o, False)) for o in e["orden_id"]))}
        for e in eventos_compra}
    eval_compras["causas_detectadas"] = compras[compras["anomalia"]]["causa"].value_counts().to_dict()

    # --- evaluacion de demanda, por almacen, producto y dia
    marcados = set()
    for e in verdad:
        for dia, alm, sku in e.get("demanda_afectada", []):
            if alm in almacen_por_clave and sku in producto_por_sku:
                marcados.add((pd.Timestamp(dia), almacen_por_clave[alm], producto_por_sku[sku]))
    real = [(r.fecha, r.almacen_id, r.producto_id) in marcados for r in demanda.itertuples()]
    eval_demanda = _metricas(real, demanda["anomalia"].to_numpy())
    eval_demanda["por_evento"] = {}
    for e in verdad:
        dias = sorted({(pd.Timestamp(d), almacen_por_clave.get(a), producto_por_sku.get(s))
                       for d, a, s in e.get("demanda_afectada", [])})
        if not dias:
            continue
        inicio = dias[0][0]
        ventana = {k for k in dias if (k[0] - inicio).days < VENTANA_DETECCION_DIAS}
        sub = demanda[[(r.fecha, r.almacen_id, r.producto_id) in ventana for r in demanda.itertuples()]]
        alertas = sub[sub["anomalia"]]
        primera = alertas["fecha"].min() if not alertas.empty else None
        eval_demanda["por_evento"][e["clave"]] = {
            "detectado": primera is not None,
            "dias_hasta_detectar": None if primera is None else int((primera - inicio).days),
            "dias_con_alerta_en_ventana": int(len(alertas)), "dias_en_ventana": int(len(sub))}
    falsas = int(sum(1 for r, a in zip(real, demanda["anomalia"]) if a and not r))
    eval_demanda["falsas_alarmas_por_semana"] = round(falsas / (len(demanda["fecha"].unique()) / 7), 2)

    salida = {
        "_meta": {"modelo": "IsolationForest", "contaminacion": CONTAMINACION, "semilla": SEMILLA,
                  "variables_compras": VARIABLES, "variable_demanda": "cociente 7/28 dias relativo a la red",
                  "contaminacion_demanda": CONTAMINACION_DEMANDA, "ventana_deteccion_dias": VENTANA_DETECCION_DIAS,
                  "generado": date.today().isoformat()},
        "compras_por_orden": eval_compras,
        "demanda_por_dia": eval_demanda,
    }
    SALIDA.write_text(json.dumps(salida, ensure_ascii=True, indent=1), encoding="utf-8")

    print("Isolation Forest validado contra eventos inyectados")
    c = eval_compras
    print(f"  Compras ({c['ordenes_evaluadas']} ordenes, {c['ordenes_anomalas_reales']} anomalas reales): "
          f"precision {c['precision']:.0%}  recall {c['recall']:.0%}  F1 {c['f1']:.2f}")
    for clave, v in c["por_evento"].items():
        print(f"    {clave:<26} {v['detectadas']} de {v['ordenes']} ordenes")
    print(f"    causas de las alertas: {c['causas_detectadas']}")
    d = eval_demanda
    print(f"  Demanda (por dia): precision {d['precision']:.0%}  recall {d['recall']:.0%}  "
          f"falsas alarmas: {d['falsas_alarmas_por_semana']} por semana")
    for clave, v in d["por_evento"].items():
        estado = f"detectado a los {v['dias_hasta_detectar']} dias" if v["detectado"] else "no detectado"
        print(f"    {clave:<26} {estado} ({v['dias_con_alerta_en_ventana']} de {v['dias_en_ventana']} dias con alerta)")
    print(f"  renglones con score en fact_supply_chain: {len(compras)}")
    print(f"  evidencia: {SALIDA.relative_to(BACKEND.parent)}")


if __name__ == "__main__":
    main()