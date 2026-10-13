from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import get_connection
from app import asistente_api, kpis, pronostico_api, recomendaciones_api, riesgo_api

app = FastAPI(
    title="Supply Chain Dashboard - Analytics API",
    version="0.2.0"
)

app.include_router(kpis.router)
app.include_router(pronostico_api.router)
app.include_router(riesgo_api.router)
app.include_router(recomendaciones_api.router)
app.include_router(asistente_api.router)

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

@app.get("/kpis/envios")
def get_envios():
    """Estado de envíos por proveedor: a tiempo / tardío / en tránsito (Módulo de Logística)"""
    query = """
        SELECT
            e.envio_id,
            pr.nombre AS proveedor,
            e.fecha_salida,
            e.fecha_llegada_estim,
            e.fecha_llegada_real,
            e.costo_flete
        FROM envios e
        JOIN proveedores pr ON pr.proveedor_id = e.proveedor_id
        ORDER BY e.fecha_salida;
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
    finally:
        conn.close()

    envios = []
    for row in rows:
        if row["fecha_llegada_real"] is None:
            estado = "En transito"
        elif row["fecha_llegada_real"] <= row["fecha_llegada_estim"]:
            estado = "A tiempo"
        else:
            estado = "Tardio"

        envios.append({
            "envio_id": row["envio_id"],
            "proveedor": row["proveedor"],
            "fecha_salida": row["fecha_salida"].strftime("%Y-%m-%d") if row["fecha_salida"] else None,
            "fecha_llegada_estim": row["fecha_llegada_estim"].strftime("%Y-%m-%d") if row["fecha_llegada_estim"] else None,
            "fecha_llegada_real": row["fecha_llegada_real"].strftime("%Y-%m-%d") if row["fecha_llegada_real"] else None,
            "costo_flete": float(row["costo_flete"]) if row["costo_flete"] is not None else 0,
            "estado": estado
        })

    return {"envios": envios}

@app.get("/kpis/almacenes")
def get_almacenes():
    query = """
        SELECT
            a.almacen_id,
            a.nombre,
            a.ubicacion,
            COALESCE(SUM(CASE WHEN m.tipo_movimiento = 'ENTRADA' THEN m.cantidad ELSE 0 END), 0) -
            COALESCE(SUM(CASE WHEN m.tipo_movimiento = 'SALIDA' THEN m.cantidad ELSE 0 END), 0) AS unidades_almacenadas
        FROM almacenes a
        LEFT JOIN movimientos_inventario m ON m.almacen_id = a.almacen_id
        GROUP BY a.almacen_id, a.nombre, a.ubicacion
        ORDER BY a.almacen_id;
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
    finally:
        conn.close()

    return {"almacenes": rows}

@app.get("/kpis/alertas")
def get_alertas():
    conn = get_connection()
    alertas = []
    try:
        with conn.cursor() as cur:
            # Alerta 1: productos sin stock
            cur.execute("""
                SELECT p.sku, p.nombre,
                       COALESCE(SUM(CASE WHEN m.tipo_movimiento='ENTRADA' THEN m.cantidad ELSE 0 END),0) -
                       COALESCE(SUM(CASE WHEN m.tipo_movimiento='SALIDA' THEN m.cantidad ELSE 0 END),0) AS stock_actual
                FROM productos p
                LEFT JOIN movimientos_inventario m ON m.producto_id = p.producto_id
                GROUP BY p.sku, p.nombre
                HAVING COALESCE(SUM(CASE WHEN m.tipo_movimiento='ENTRADA' THEN m.cantidad ELSE 0 END),0) -
                       COALESCE(SUM(CASE WHEN m.tipo_movimiento='SALIDA' THEN m.cantidad ELSE 0 END),0) <= 0;
            """)
            for row in cur.fetchall():
                alertas.append({
                    "tipo": "Inventario",
                    "severidad": "alta",
                    "mensaje": f"Producto {row['nombre']} ({row['sku']}) sin stock disponible"
                })

            # Alerta 2: envios tardios
            cur.execute("""
                SELECT pr.nombre AS proveedor, e.fecha_llegada_estim, e.fecha_llegada_real
                FROM envios e
                JOIN proveedores pr ON pr.proveedor_id = e.proveedor_id
                WHERE e.fecha_llegada_real IS NOT NULL
                AND e.fecha_llegada_real > e.fecha_llegada_estim;
            """)
            for row in cur.fetchall():
                alertas.append({
                    "tipo": "Logistica",
                    "severidad": "media",
                    "mensaje": f"Envio de {row['proveedor']} llego tarde (estimado {row['fecha_llegada_estim']}, real {row['fecha_llegada_real']})"
                })

            # Alerta 3: OTIF por debajo del umbral (70%)
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE fecha_entrega_real IS NOT NULL AND fecha_entrega_real <= fecha_entrega_estim) AS a_tiempo,
                    COUNT(*) FILTER (WHERE fecha_entrega_real IS NOT NULL) AS total
                FROM ordenes_compra;
            """)
            row = cur.fetchone()
            total = row["total"] or 0
            a_tiempo = row["a_tiempo"] or 0
            otif = (a_tiempo / total * 100) if total > 0 else 0
            if otif < 70:
                alertas.append({
                    "tipo": "Compras",
                    "severidad": "alta",
                    "mensaje": f"OTIF actual ({round(otif, 1)}%) esta por debajo del umbral minimo de 70%"
                })
    finally:
        conn.close()

    return {"alertas": alertas, "total_alertas": len(alertas)}

@app.get("/kpis/riesgo-proveedores")
def get_riesgo_proveedores():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT proveedor_id, nombre, calificacion FROM proveedores;")
            proveedores = cur.fetchall()

            cur.execute("""
                SELECT proveedor_id,
                       COUNT(*) FILTER (
                           WHERE fecha_llegada_real IS NOT NULL
                           AND fecha_llegada_real > fecha_llegada_estim
                       ) AS envios_tardios
                FROM envios
                GROUP BY proveedor_id;
            """)
            tardios_por_proveedor = {row["proveedor_id"]: row["envios_tardios"] for row in cur.fetchall()}
    finally:
        conn.close()

    resultado = []
    for p in proveedores:
        tardios = tardios_por_proveedor.get(p["proveedor_id"], 0)
        # Score: a menor calificacion y mas envios tardios, mayor riesgo
        score = round((5 - float(p["calificacion"])) * 10 + tardios * 20, 1)

        if score >= 40:
            nivel = "Alto"
        elif score >= 20:
            nivel = "Medio"
        else:
            nivel = "Bajo"

        resultado.append({
            "proveedor_id": p["proveedor_id"],
            "nombre": p["nombre"],
            "calificacion": float(p["calificacion"]),
            "envios_tardios": tardios,
            "score_riesgo": score,
            "nivel_riesgo": nivel
        })

    return {"riesgo_proveedores": resultado}