"""Endpoint de Demanda y pronostico (CC-07, CC-10).

GET /api/v1/pronostico?producto_id=&historia=60
  Serie real de los ultimos `historia` dias, pronostico Holt-Winters de 14 dias con
  intervalo de 90%, MAPE de validacion, total proyectado y variacion contra los
  ultimos 14 dias reales. Sin producto_id devuelve el total de todos los SKU.
  El pronostico lo calcula en lote analitica.pronostico; este endpoint solo lo lee.
"""
from fastapi import APIRouter, HTTPException, Query

from app.database import get_connection

router = APIRouter(prefix="/api/v1", tags=["Pronostico"])


@router.get("/pronostico")
def pronostico(producto_id: int | None = Query(None, description="Sin valor: todos los SKU"),
               historia: int = Query(60, ge=14, le=365, description="Dias de historia real")):
    filtro_fc = "producto_id IS NULL" if producto_id is None else "producto_id = %s"
    filtro_dd = "" if producto_id is None else "WHERE producto_id = %s"
    params = () if producto_id is None else (producto_id,)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT fecha_prediccion, demanda_estimada, intervalo_inferior, intervalo_superior, "
                        f"mape, fecha_generacion FROM forecast_demanda WHERE {filtro_fc} "
                        f"ORDER BY fecha_prediccion", params)
            futuro = cur.fetchall()
            if not futuro:
                raise HTTPException(status_code=404,
                                    detail="Sin pronostico. Ejecute python -m analitica.pronostico")
            cur.execute(f"SELECT fecha, SUM(unidades_solicitadas) AS real FROM demanda_diaria {filtro_dd} "
                        f"GROUP BY fecha ORDER BY fecha DESC LIMIT %s", params + (historia,))
            real = list(reversed(cur.fetchall()))
            nombre = "Todos los SKU"
            if producto_id is not None:
                cur.execute("SELECT nombre FROM productos WHERE producto_id = %s", (producto_id,))
                fila = cur.fetchone()
                nombre = fila["nombre"] if fila else str(producto_id)
    finally:
        conn.close()

    total_futuro = sum(float(f["demanda_estimada"]) for f in futuro)
    ultimos = [float(r["real"]) for r in real[-len(futuro):]]
    total_previo = sum(ultimos)
    mape = futuro[0]["mape"]
    return {
        "producto_id": producto_id,
        "producto": nombre,
        "modelo": "Holt-Winters aditivo, tendencia amortiguada, estacionalidad semanal (periodo 7)",
        "generado": futuro[0]["fecha_generacion"].isoformat(timespec="seconds") if futuro[0]["fecha_generacion"] else None,
        "fecha_corte": real[-1]["fecha"].isoformat() if real else None,
        "mape_pct": None if mape is None else round(float(mape) * 100, 1),
        "horizonte_dias": len(futuro),
        "total_proyectado": round(total_futuro),
        "total_periodo_anterior": round(total_previo),
        "variacion_pct": round((total_futuro / total_previo - 1) * 100, 1) if total_previo else None,
        "real": [{"fecha": r["fecha"].isoformat(), "valor": float(r["real"])} for r in real],
        "pronostico": [{"fecha": f["fecha_prediccion"].isoformat(),
                        "valor": float(f["demanda_estimada"]),
                        "inferior": float(f["intervalo_inferior"]),
                        "superior": float(f["intervalo_superior"])} for f in futuro],
        "aviso": "Demanda simulada; intervalo de 90% empirico a partir del error de validacion",
    }