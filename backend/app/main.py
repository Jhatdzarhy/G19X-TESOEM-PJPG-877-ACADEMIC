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

@app.get("/kpis/inventario")
def get_inventario():
    """Stock actual por producto: entradas - salidas (Módulo de Inventarios)"""
    query = """
        SELECT
            p.producto_id,
            p.nombre,
            p.sku,
            COALESCE(SUM(CASE WHEN m.tipo_movimiento = 'ENTRADA' THEN m.cantidad ELSE 0 END), 0) AS total_entradas,
            COALESCE(SUM(CASE WHEN m.tipo_movimiento = 'SALIDA' THEN m.cantidad ELSE 0 END), 0) AS total_salidas
        FROM productos p
        LEFT JOIN movimientos_inventario m ON m.producto_id = p.producto_id
        GROUP BY p.producto_id, p.nombre, p.sku
        ORDER BY p.nombre;
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
    finally:
        conn.close()

    inventario = []
    for row in rows:
        entradas = float(row["total_entradas"])
        salidas = float(row["total_salidas"])
        inventario.append({
            "producto_id": row["producto_id"],
            "nombre": row["nombre"],
            "sku": row["sku"],
            "total_entradas": entradas,
            "total_salidas": salidas,
            "stock_actual": entradas - salidas
        })

    return {"inventario": inventario}