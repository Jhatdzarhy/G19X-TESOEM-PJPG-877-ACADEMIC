-- ============================================================
-- Proyecto final: agregacion hacia el modelo estrella (PDR seccion 5.2 y 8.2)
--   dim_tiempo        : un registro por dia del periodo simulado
--   fact_supply_chain : un registro por renglon de orden de compra recibido
--
-- Grano y medidas de fact_supply_chain:
--   fecha_id              fecha de recepcion (fecha_entrega_real)
--   producto_id, proveedor_id, almacen_id (almacen de destino, CC-06)
--   lead_time_dias        recepcion - orden, en dias (KPI 1)
--   otif                  la orden completa llego a tiempo y sin faltantes (KPI 6, CC-02)
--   unidades_solicitadas  cantidad ordenada del renglon
--   unidades_entregadas   cantidad recibida del renglon (Fill Rate de proveedor, CC-05)
--   unidades              igual a unidades_entregadas (unidades transportadas, KPI 7)
--   costo_total           cantidad ordenada x precio, en MXN al FIX de la orden (CC-03)
--   variacion_costo       (precio - costo estandar) x cantidad, en MXN (KPI 2, CC-15)
--   costo_flete           flete del envio prorrateado por unidades recibidas, en MXN (KPI 7)
--   nivel_riesgo, score_anomalia
--                         NULL aqui; los escribe el motor analitico en FastAPI (CC-07)
--
-- El Fill Rate de servicio (KPI de Inventario) se calcula desde demanda_diaria (CC-05);
-- utilizacion, rotacion y DOH se calculan desde movimientos_inventario (CC-15).
--
-- Se define como funcion para que el simulador en vivo (CC-09) pueda refrescar el
-- modelo con SELECT refrescar_modelo_estrella(); la funcion es idempotente.
-- Requiere: 01, 02 y 03 aplicados, y datos de generar_operacion.py y cargar_banxico.py.
-- ============================================================
\set ON_ERROR_STOP on
\connect supply_chain_final
SET client_encoding = 'UTF8';
SET client_min_messages = warning;

BEGIN;

CREATE OR REPLACE FUNCTION refrescar_modelo_estrella()
RETURNS TABLE (dias_tiempo INT, filas_fact INT, renglones_sin_tc INT)
LANGUAGE plpgsql
AS $$
DECLARE
    v_inicio DATE;
    v_fin    DATE;
BEGIN
    -- periodo: desde la primera orden o demanda hasta la ultima recepcion o demanda
    SELECT LEAST(MIN(d.fecha), (SELECT MIN(fecha_orden)::date FROM ordenes_compra)),
           GREATEST(MAX(d.fecha), (SELECT MAX(fecha_entrega_real)::date FROM ordenes_compra))
      INTO v_inicio, v_fin
      FROM demanda_diaria d;

    IF v_inicio IS NULL THEN
        RAISE EXCEPTION 'No hay datos operativos. Ejecute antes etl.generar_operacion';
    END IF;

    -- dim_tiempo
    TRUNCATE dim_tiempo;
    INSERT INTO dim_tiempo (fecha_id, anio, mes, dia, trimestre)
    SELECT f::date, EXTRACT(YEAR FROM f)::int, EXTRACT(MONTH FROM f)::int,
           EXTRACT(DAY FROM f)::int, EXTRACT(QUARTER FROM f)::int
    FROM generate_series(v_inicio, v_fin, INTERVAL '1 day') f;

    -- fact_supply_chain
    TRUNCATE fact_supply_chain RESTART IDENTITY;

    INSERT INTO fact_supply_chain (
        fecha_id, producto_id, proveedor_id, almacen_id, lead_time_dias, otif,
        costo_total, unidades, unidades_solicitadas, unidades_entregadas,
        costo_flete, variacion_costo, nivel_riesgo, score_anomalia)
    WITH ordenes AS (
        SELECT o.orden_id, o.proveedor_id, o.fecha_orden, o.fecha_entrega_real,
               e.almacen_origen_id AS almacen_id, e.costo_flete,
               (e.fecha_llegada_real::date <= e.fecha_llegada_estim::date
                AND NOT EXISTS (SELECT 1 FROM detalle_orden_compra x
                                WHERE x.orden_id = o.orden_id AND x.cantidad_recibida < x.cantidad)) AS otif,
               (SELECT t.tasa FROM tipo_cambio t
                 WHERE t.fuente = 'BANXICO_SIE' AND t.moneda_origen = 'USD' AND t.moneda_destino = 'MXN'
                   AND t.fecha <= o.fecha_orden::date
                 ORDER BY t.fecha DESC LIMIT 1) AS tc,
               SUM(d.cantidad_recibida) OVER (PARTITION BY o.orden_id) AS unidades_orden
        FROM ordenes_compra o
        JOIN envios e ON e.orden_id = o.orden_id
        JOIN detalle_orden_compra d ON d.orden_id = o.orden_id
        WHERE o.fecha_entrega_real IS NOT NULL
    ),
    ordenes_unicas AS (SELECT DISTINCT ON (orden_id) * FROM ordenes)
    SELECT o.fecha_entrega_real::date,
           d.producto_id,
           o.proveedor_id,
           o.almacen_id,
           ROUND((EXTRACT(EPOCH FROM (o.fecha_entrega_real - o.fecha_orden)) / 86400)::numeric, 2),
           o.otif,
           ROUND(d.cantidad * d.precio_unitario * o.tc, 2),
           d.cantidad_recibida,
           d.cantidad,
           d.cantidad_recibida,
           ROUND(o.costo_flete * d.cantidad_recibida / NULLIF(o.unidades_orden, 0), 2),
           ROUND((d.precio_unitario - p.costo_unitario) * d.cantidad * o.tc, 2),
           NULL,
           NULL
    FROM ordenes_unicas o
    JOIN detalle_orden_compra d ON d.orden_id = o.orden_id
    JOIN productos p ON p.producto_id = d.producto_id;

    RETURN QUERY
    SELECT (SELECT COUNT(*)::int FROM dim_tiempo),
           (SELECT COUNT(*)::int FROM fact_supply_chain),
           (SELECT COUNT(*)::int FROM fact_supply_chain WHERE costo_total IS NULL);
END;
$$;

COMMENT ON FUNCTION refrescar_modelo_estrella() IS
    'PDR 5.2 y 8.2: regenera dim_tiempo y fact_supply_chain (un registro por renglon recibido); CC-03, CC-05, CC-06, CC-15';

SELECT * FROM refrescar_modelo_estrella();

COMMIT;

-- ------------------------------------------------------------
-- Conciliacion con validar_kpis.sql. Fill Rate de proveedor y costo de transporte
-- deben coincidir; el lead time puede diferir en decimas porque aqui se promedia por
-- renglon (no por orden), y la variacion de costo porque aqui se pondera en MXN.
-- ------------------------------------------------------------
SELECT 'Lead time de proveedor (dias, por renglon)' AS kpi,
       ROUND(AVG(lead_time_dias), 2)::text AS valor_fact
FROM fact_supply_chain
UNION ALL
SELECT 'Fill Rate de proveedor',
       ROUND(SUM(unidades_entregadas) / SUM(unidades_solicitadas) * 100, 2)::text || ' %'
FROM fact_supply_chain
UNION ALL
SELECT 'Variacion de costo de compra',
       ROUND(SUM(variacion_costo) / (SUM(costo_total) - SUM(variacion_costo)) * 100, 2)::text || ' %'
FROM fact_supply_chain
UNION ALL
SELECT 'Costo de transporte por unidad (MXN)',
       ROUND(SUM(costo_flete) / SUM(unidades), 2)::text
FROM fact_supply_chain;

\echo '04_agregacion_fact.sql aplicado: dim_tiempo y fact_supply_chain regenerados.'