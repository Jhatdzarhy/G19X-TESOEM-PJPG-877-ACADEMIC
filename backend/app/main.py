from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import get_connection

app = FastAPI(
    title="Supply Chain Dashboard - Analytics API",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok", "service": "Supply Chain Analytics API"}


@app.get("/kpis/otif")
def get_otif():
    query = """
        SELECT
            COUNT(*) FILTER (
                WHERE fecha_entrega_real IS NOT NULL
                AND fecha_entrega_real <= fecha_entrega_estim
            ) AS entregas_a_tiempo,
            COUNT(*) FILTER (WHERE fecha_entrega_real IS NOT NULL) AS total_entregadas
        FROM ordenes_compra;
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
    finally:
        conn.close()

    total = row["total_entregadas"] or 0
    a_tiempo = row["entregas_a_tiempo"] or 0
    otif = round((a_tiempo / total) * 100, 2) if total > 0 else 0

    return {"otif_pct": otif, "entregas_a_tiempo": a_tiempo, "total_entregadas": total}


@app.get("/kpis/lead-time")
def get_lead_time():
    query = """
        SELECT AVG(EXTRACT(DAY FROM (fecha_entrega_real - fecha_orden))) AS lead_time_promedio
        FROM ordenes_compra
        WHERE fecha_entrega_real IS NOT NULL;
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
    finally:
        conn.close()

    valor = round(float(row["lead_time_promedio"]), 2) if row["lead_time_promedio"] else 0
    return {"lead_time_dias_promedio": valor}


@app.get("/kpis/proveedores")
def get_proveedores():
    query = "SELECT proveedor_id, nombre, pais, calificacion FROM proveedores ORDER BY calificacion DESC;"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
    finally:
        conn.close()

    return {"proveedores": rows}