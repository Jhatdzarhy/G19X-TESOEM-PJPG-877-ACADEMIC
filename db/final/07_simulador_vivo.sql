-- ============================================================
-- Proyecto final: simulador en vivo (CC-09 y CC-22, control de cambios, riesgo R6)
--   eventos_vivo      : actividad en vivo (franja del Resumen, historial y Server-Sent Events)
--   simulador_estado  : una sola fila con el reloj simulado y el plan del dia en curso
--   refrescar_modelo_estrella_desde(fecha):
--                       refresca dim_tiempo y fact_supply_chain solo desde esa fecha;
--                       conserva score_anomalia y nivel_riesgo de los 12 meses validados (CC-18)
--   reiniciar_simulador_vivo():
--                       regresa la operacion a la fecha de corte base sin tocar los 12 meses
--                       ni el historial de decisiones humanas (CC-19, CC-20)
-- Aditivo e idempotente: no modifica ni elimina tablas o funciones existentes.
-- Requiere: 01 a 06 aplicados.
-- ============================================================
\set ON_ERROR_STOP on
\connect supply_chain_final
SET client_encoding = 'UTF8';
SET client_min_messages = warning;

BEGIN;

CREATE TABLE IF NOT EXISTS eventos_vivo (
    evento_id       BIGSERIAL PRIMARY KEY,
    fecha_simulada  DATE        NOT NULL,
    ocurrido        TIMESTAMP   NOT NULL,
    registrado      TIMESTAMP   NOT NULL DEFAULT NOW(),
    tipo            VARCHAR(30) NOT NULL,
    severidad       VARCHAR(10) NOT NULL DEFAULT 'INFO',
    modulo          VARCHAR(30) NOT NULL,
    titulo          VARCHAR(200) NOT NULL,
    datos           JSONB       NOT NULL DEFAULT '{}'::jsonb,
    orden_id        INT REFERENCES ordenes_compra(orden_id) ON DELETE SET NULL,
    proveedor_id    INT REFERENCES proveedores(proveedor_id),
    almacen_id      INT REFERENCES almacenes(almacen_id),
    CONSTRAINT ck_eventos_vivo_tipo CHECK (tipo IN ('RECEPCION', 'RECEPCION_TARDIA', 'RECEPCION_PARCIAL',
        'ORDEN_EMITIDA', 'VENTAS_DIA', 'ALERTA_KPI', 'CASO_NUEVO', 'SIMULACION_AL_DIA', 'SIMULACION_REINICIADA')),
    CONSTRAINT ck_eventos_vivo_severidad CHECK (severidad IN ('INFO', 'ATENCION', 'CRITICO')),
    CONSTRAINT ck_eventos_vivo_ascii CHECK (titulo ~ '^[ -~]*$' AND modulo ~ '^[a-z_]+$')
);
CREATE INDEX IF NOT EXISTS ix_eventos_vivo_fecha ON eventos_vivo (fecha_simulada);

COMMENT ON TABLE eventos_vivo IS
    'CC-09 y CC-22: actividad del simulador en vivo; evento_id sirve de id de Server-Sent Events (Last-Event-ID)';

CREATE TABLE IF NOT EXISTS simulador_estado (
    id                SMALLINT  PRIMARY KEY DEFAULT 1,
    fecha_corte_base  DATE      NOT NULL,
    dia_cerrado       DATE      NOT NULL,
    dia_en_curso      DATE,
    plan              JSONB,
    siguiente         INT       NOT NULL DEFAULT 0,
    llegadas          JSONB     NOT NULL DEFAULT '[]'::jsonb,
    estados_previos   JSONB,
    actualizado       TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_simulador_estado_unico CHECK (id = 1)
);

COMMENT ON TABLE simulador_estado IS
    'CC-22: reloj simulado (ultimo dia cerrado), plan del dia en curso y llegadas pendientes; nunca se guarda una llegada futura en envios';

-- ------------------------------------------------------------
-- Refresco incremental del modelo estrella (misma regla que refrescar_modelo_estrella)
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION refrescar_modelo_estrella_desde(p_desde DATE)
RETURNS TABLE (dias_tiempo INT, filas_fact INT, filas_refrescadas INT)
LANGUAGE plpgsql
AS $$
DECLARE
    v_fin DATE;
    v_filas INT;
BEGIN
    SELECT GREATEST((SELECT MAX(fecha) FROM demanda_diaria),
                    (SELECT MAX(fecha_entrega_real)::date FROM ordenes_compra))
      INTO v_fin;

    DELETE FROM dim_tiempo WHERE fecha_id >= p_desde;
    IF v_fin >= p_desde THEN
        INSERT INTO dim_tiempo (fecha_id, anio, mes, dia, trimestre)
        SELECT f::date, EXTRACT(YEAR FROM f)::int, EXTRACT(MONTH FROM f)::int,
               EXTRACT(DAY FROM f)::int, EXTRACT(QUARTER FROM f)::int
        FROM generate_series(p_desde, v_fin, INTERVAL '1 day') f;
    END IF;

    DELETE FROM fact_supply_chain WHERE fecha_id >= p_desde;

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
          AND o.fecha_entrega_real::date >= p_desde
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
    GET DIAGNOSTICS v_filas = ROW_COUNT;

    RETURN QUERY
    SELECT (SELECT COUNT(*)::int FROM dim_tiempo),
           (SELECT COUNT(*)::int FROM fact_supply_chain),
           v_filas;
END;
$$;

COMMENT ON FUNCTION refrescar_modelo_estrella_desde(DATE) IS
    'CC-22: refresca dim_tiempo y fact_supply_chain desde una fecha (grano por fecha de recepcion); conserva los scores anteriores';

-- ------------------------------------------------------------
-- Reinicio: regresa a la fecha de corte base
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION reiniciar_simulador_vivo()
RETURNS TABLE (fecha_corte DATE, ordenes_borradas INT, ordenes_restauradas INT)
LANGUAGE plpgsql
AS $$
DECLARE
    v_base DATE;
    v_borradas INT;
    v_restauradas INT;
BEGIN
    SELECT fecha_corte_base INTO v_base FROM simulador_estado WHERE id = 1;
    IF v_base IS NULL THEN
        RAISE EXCEPTION 'El simulador no se ha iniciado; no hay nada que reiniciar';
    END IF;

    -- operacion de los dias simulados
    DELETE FROM demanda_diaria WHERE fecha > v_base;
    DELETE FROM movimientos_inventario WHERE fecha::date > v_base;
    DELETE FROM eventos_vivo;

    -- ordenes emitidas en vivo
    DELETE FROM detalle_orden_compra
     WHERE orden_id IN (SELECT orden_id FROM ordenes_compra WHERE fecha_orden::date > v_base);
    DELETE FROM envios
     WHERE orden_id IN (SELECT orden_id FROM ordenes_compra WHERE fecha_orden::date > v_base);
    DELETE FROM ordenes_compra WHERE fecha_orden::date > v_base;
    GET DIAGNOSTICS v_borradas = ROW_COUNT;

    -- ordenes que estaban en transito en la fecha de corte base y llegaron en vivo
    UPDATE detalle_orden_compra SET cantidad_recibida = NULL
     WHERE orden_id IN (SELECT orden_id FROM ordenes_compra
                         WHERE fecha_orden::date <= v_base AND fecha_entrega_real::date > v_base);
    UPDATE envios SET fecha_llegada_real = NULL
     WHERE orden_id IN (SELECT orden_id FROM ordenes_compra
                         WHERE fecha_orden::date <= v_base AND fecha_entrega_real::date > v_base);
    UPDATE ordenes_compra SET fecha_entrega_real = NULL, estatus = 'EN_TRANSITO'
     WHERE fecha_orden::date <= v_base AND fecha_entrega_real::date > v_base;
    GET DIAGNOSTICS v_restauradas = ROW_COUNT;

    -- modelo estrella: solo los dias posteriores al corte base
    PERFORM refrescar_modelo_estrella_desde(v_base + 1);

    DELETE FROM simulador_estado WHERE id = 1;

    RETURN QUERY SELECT v_base, v_borradas, v_restauradas;
END;
$$;

COMMENT ON FUNCTION reiniciar_simulador_vivo() IS
    'CC-22: borra la operacion simulada en vivo y restaura las ordenes en transito al corte base; no toca recomendaciones ni decisiones';

COMMIT;

\echo '07_simulador_vivo.sql aplicado: eventos_vivo, simulador_estado y funciones del simulador en vivo.'