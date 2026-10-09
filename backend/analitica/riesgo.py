"""Indice de riesgo de proveedor 0 a 100 (PDR seccion 7, CC-07, umbrales CC-16).

El PDR lo define como un score compuesto de retrasos, calidad y concentracion.
Ventana: 90 dias que terminan en la fecha de evaluacion.

  Componente      Medida                                          Satura en   Peso
  Retrasos        1 - entregas a tiempo / entregas recibidas      50% tarde   45%
  Cumplimiento    1 - unidades recibidas / unidades ordenadas     20% faltante 30%
  Concentracion   participacion en compras de la red (MXN)        50% del gasto 25%

  score = 100 x (0.45 r + 0.30 c + 0.25 k), cada componente acotado a [0, 1].
  Nivel: BAJO hasta 40, MEDIO hasta 60, ALTO arriba de 60 (CC-16).
  Indice de la red (KPI): promedio de los scores ponderado por participacion en compras.

Este modulo se usa en lote (escribe fact_supply_chain.nivel_riesgo) y desde la API.
"""
from datetime import timedelta

import pandas as pd

from app.database import get_connection

VENTANA_DIAS = 90
PESOS = {"retrasos": 0.45, "cumplimiento": 0.30, "concentracion": 0.25}
SATURACION = {"retrasos": 0.50, "cumplimiento": 0.20, "concentracion": 0.50}


def nivel(score):
    if score is None:
        return None
    return "BAJO" if score <= 40 else "MEDIO" if score <= 60 else "ALTO"


def cargar(cur):
    """Envios recibidos y renglones de fact_supply_chain, con lo necesario para el score."""
    cur.execute("""
        SELECT e.proveedor_id, e.fecha_llegada_real::date AS fecha,
               (e.fecha_llegada_real::date <= e.fecha_llegada_estim::date) AS a_tiempo,
               GREATEST(0, e.fecha_llegada_real::date - e.fecha_llegada_estim::date) AS dias_retraso
        FROM envios e WHERE e.fecha_llegada_real IS NOT NULL
    """)
    envios = pd.DataFrame([dict(r) for r in cur.fetchall()])
    cur.execute("""
        SELECT proveedor_id, fecha_id AS fecha, unidades_solicitadas, unidades_entregadas, costo_total
        FROM fact_supply_chain
    """)
    fact = pd.DataFrame([dict(r) for r in cur.fetchall()])
    cur.execute("SELECT proveedor_id, nombre, pais FROM proveedores ORDER BY proveedor_id")
    proveedores = pd.DataFrame([dict(r) for r in cur.fetchall()])
    for df in (envios, fact):
        if not df.empty:
            df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    for c in ("unidades_solicitadas", "unidades_entregadas", "costo_total"):
        if not fact.empty:
            fact[c] = fact[c].astype(float)
    return envios, fact, proveedores


def calcular(envios, fact, proveedores, hasta, dias=VENTANA_DIAS):
    """Score por proveedor en la ventana [hasta - dias + 1, hasta]. Devuelve (lista, indice_red)."""
    desde = hasta - timedelta(days=dias - 1)
    e = envios[(envios["fecha"] >= desde) & (envios["fecha"] <= hasta)] if not envios.empty else envios
    f = fact[(fact["fecha"] >= desde) & (fact["fecha"] <= hasta)] if not fact.empty else fact
    gasto_total = float(f["costo_total"].sum()) if not f.empty else 0.0

    resultado = []
    for p in proveedores.itertuples():
        ep = e[e["proveedor_id"] == p.proveedor_id] if not e.empty else e
        fp = f[f["proveedor_id"] == p.proveedor_id] if not f.empty else f
        if ep.empty or fp.empty:
            resultado.append({"proveedor_id": int(p.proveedor_id), "nombre": p.nombre, "pais": p.pais,
                              "score": None, "nivel": None, "envios": int(len(ep)), "componentes": None,
                              "participacion_compras_pct": 0.0})
            continue
        a_tiempo = float(ep["a_tiempo"].mean())
        fill = float(fp["unidades_entregadas"].sum() / fp["unidades_solicitadas"].sum())
        participacion = float(fp["costo_total"].sum() / gasto_total) if gasto_total else 0.0
        bruto = {"retrasos": 1 - a_tiempo, "cumplimiento": 1 - fill, "concentracion": participacion}
        comp = {k: min(1.0, max(0.0, v / SATURACION[k])) for k, v in bruto.items()}
        score = 100 * sum(PESOS[k] * comp[k] for k in PESOS)
        resultado.append({
            "proveedor_id": int(p.proveedor_id), "nombre": p.nombre, "pais": p.pais,
            "score": round(score, 1), "nivel": nivel(score), "envios": int(len(ep)),
            "participacion_compras_pct": round(100 * participacion, 1),
            "componentes": {
                "retrasos": {"entregas_a_tiempo_pct": round(100 * a_tiempo, 1),
                             "retraso_promedio_dias": round(float(ep["dias_retraso"].mean()), 1),
                             "aporte": round(100 * PESOS["retrasos"] * comp["retrasos"], 1)},
                "cumplimiento": {"fill_rate_proveedor_pct": round(100 * fill, 1),
                                 "aporte": round(100 * PESOS["cumplimiento"] * comp["cumplimiento"], 1)},
                "concentracion": {"participacion_compras_pct": round(100 * participacion, 1),
                                  "aporte": round(100 * PESOS["concentracion"] * comp["concentracion"], 1)},
            },
        })
    con_score = [r for r in resultado if r["score"] is not None]
    peso = sum(r["participacion_compras_pct"] for r in con_score)
    indice = (sum(r["score"] * r["participacion_compras_pct"] for r in con_score) / peso) if peso else None
    return resultado, (None if indice is None else round(indice, 1))


def main():
    """Escribe en fact_supply_chain el nivel de riesgo del proveedor vigente en la fecha de cada renglon."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                envios, fact, proveedores = cargar(cur)
                if fact.empty:
                    raise RuntimeError("fact_supply_chain esta vacia. Ejecute antes db/final/04_agregacion_fact.sql")
                niveles = {}
                for fecha in sorted(fact["fecha"].unique()):
                    lista, _ = calcular(envios, fact, proveedores, fecha)
                    for r in lista:
                        niveles[(fecha, r["proveedor_id"])] = r["nivel"]
                cur.execute("UPDATE fact_supply_chain SET nivel_riesgo = NULL")
                for (fecha, proveedor_id), valor in niveles.items():
                    if valor is not None:
                        cur.execute("UPDATE fact_supply_chain SET nivel_riesgo = %s "
                                    "WHERE fecha_id = %s AND proveedor_id = %s", (valor, fecha, proveedor_id))
                corte = max(fact["fecha"])
                actual, indice = calcular(envios, fact, proveedores, corte)
                previo, indice_previo = calcular(envios, fact, proveedores, corte - timedelta(days=30))
    finally:
        conn.close()

    previos = {r["proveedor_id"]: r["score"] for r in previo}
    print(f"Indice de riesgo de proveedores al {corte} (ventana {VENTANA_DIAS} dias)")
    for r in sorted(actual, key=lambda x: -(x["score"] or 0)):
        antes = previos.get(r["proveedor_id"])
        print(f"  {r['nombre']:<28} {str(r['score']):>6} {str(r['nivel']):<6} "
              f"(hace 30 dias: {antes})  envios: {r['envios']}  compras: {r['participacion_compras_pct']}%")
    print(f"Indice de la red (ponderado por compras): {indice}  (hace 30 dias: {indice_previo})")


if __name__ == "__main__":
    main()