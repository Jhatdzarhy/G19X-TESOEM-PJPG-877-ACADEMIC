"""Endpoints de riesgo de proveedores y anomalias (CC-07, CC-16).

GET /api/v1/proveedores/riesgo        score 0-100 por proveedor (ventana de 90 dias) con sus
                                      componentes, el score de hace 30 dias y el indice de la red
GET /api/v1/anomalias?limite=20       renglones de compra con mayor score de Isolation Forest
GET /api/v1/anomalias/evaluacion      precision y recall contra los eventos inyectados

El riesgo se calcula al momento con analitica.riesgo; las anomalias las escribe en lote
analitica.anomalias en fact_supply_chain.score_anomalia.
"""
import json
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from analitica import riesgo
from app.database import get_connection

router = APIRouter(prefix="/api/v1", tags=["Riesgo y anomalias"])

EVALUACION = Path(__file__).resolve().parents[1] / "analitica" / "evaluacion_anomalias.json"


def indice_red():
    """Indice de riesgo de la red a la fecha de corte (lo usa el KPI 9)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            envios, fact, proveedores = riesgo.cargar(cur)
    finally:
        conn.close()
    if fact.empty:
        return None
    _, indice = riesgo.calcular(envios, fact, proveedores, max(fact["fecha"]))
    return indice


@router.get("/proveedores/riesgo")
def riesgo_proveedores():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            envios, fact, proveedores = riesgo.cargar(cur)
    finally:
        conn.close()
    if fact.empty:
        raise HTTPException(status_code=503, detail="fact_supply_chain esta vacia")
    corte = max(fact["fecha"])
    actual, indice = riesgo.calcular(envios, fact, proveedores, corte)
    previo, indice_previo = riesgo.calcular(envios, fact, proveedores, corte - timedelta(days=30))
    antes = {r["proveedor_id"]: r["score"] for r in previo}
    for r in actual:
        r["score_hace_30_dias"] = antes.get(r["proveedor_id"])
        r["variacion"] = (None if r["score"] is None or r["score_hace_30_dias"] is None
                          else round(r["score"] - r["score_hace_30_dias"], 1))
    actual.sort(key=lambda r: -(r["score"] or 0))
    return {
        "fecha_corte": corte.isoformat(), "ventana_dias": riesgo.VENTANA_DIAS,
        "indice_red": indice, "indice_red_hace_30_dias": indice_previo,
        "metodo": "Score compuesto 0-100: retrasos 45%, cumplimiento 30%, concentracion 25% (CC-07)",
        "proveedores": actual,
    }


@router.get("/anomalias")
def anomalias(limite: int = Query(20, ge=1, le=200)):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT f.fecha_id, p.sku, p.nombre AS producto, pr.nombre AS proveedor, a.nombre AS almacen,
                       f.score_anomalia, f.lead_time_dias, f.unidades_solicitadas, f.unidades_entregadas,
                       f.costo_total, f.variacion_costo, f.costo_flete, f.nivel_riesgo
                FROM fact_supply_chain f
                JOIN productos p ON p.producto_id = f.producto_id
                JOIN proveedores pr ON pr.proveedor_id = f.proveedor_id
                JOIN almacenes a ON a.almacen_id = f.almacen_id
                WHERE f.score_anomalia IS NOT NULL
                ORDER BY f.score_anomalia DESC, f.fecha_id DESC
                LIMIT %s
            """, (limite,))
            filas = cur.fetchall()
    finally:
        conn.close()
    if not filas:
        raise HTTPException(status_code=404, detail="Sin anomalias. Ejecute python -m analitica.anomalias")
    return {
        "modelo": "Isolation Forest sobre precio, lead time, flete y faltantes relativos (CC-07)",
        "anomalias": [{**{k: (float(v) if k not in ("fecha_id", "sku", "producto", "proveedor", "almacen", "nivel_riesgo")
                               and v is not None else v) for k, v in dict(f).items()},
                       "fecha_id": f["fecha_id"].isoformat()} for f in filas],
    }


@router.get("/anomalias/evaluacion")
def evaluacion():
    if not EVALUACION.exists():
        raise HTTPException(status_code=404, detail="Sin evaluacion. Ejecute python -m analitica.anomalias")
    return json.loads(EVALUACION.read_text(encoding="utf-8"))