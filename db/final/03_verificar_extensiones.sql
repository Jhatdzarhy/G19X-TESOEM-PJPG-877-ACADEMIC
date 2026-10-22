-- ============================================================
-- Verificacion de 03_extensiones_modelo.sql (CC-02, control de cambios, riesgo R6)
-- Evidencia para QA (Fase 6). No deja datos: todo termina en ROLLBACK
-- y las pruebas usan llaves explicitas negativas para no consumir
-- secuencias SERIAL.
-- Resultado esperado: todas las filas con resultado = OK.
-- ============================================================
\set ON_ERROR_STOP on
-- Base destino: supply_chain_final, u otra con -v base=<nombre> (instalador y pruebas)
\if :{?base}
\else
\set base supply_chain_final
\endif
\connect :"base"
SET client_encoding = 'UTF8';
SET client_min_messages = warning;

BEGIN;

CREATE TEMP TABLE resultado_qa (
    n          SERIAL,
    prueba     TEXT,
    resultado  TEXT
) ON COMMIT DROP;

-- ------------------------------------------------------------
-- A. Estructura
-- ------------------------------------------------------------
INSERT INTO resultado_qa (prueba, resultado)
SELECT 'Columna ' || e.tabla || '.' || e.columna,
       CASE WHEN c.column_name IS NULL THEN 'FALTA' ELSE 'OK' END
FROM (VALUES
    ('detalle_orden_compra','cantidad_recibida'),
    ('movimientos_inventario','orden_id'),
    ('almacenes','latitud'), ('almacenes','longitud'),
    ('proveedores','ciudad'), ('proveedores','latitud'), ('proveedores','longitud'),
    ('envios','precipitacion_mm'),
    ('tipo_cambio','fuente'),
    ('recomendaciones','opciones'),
    ('recomendaciones','ahorro_real_mxn'),
    ('recomendaciones','motivo_descarte')
) AS e(tabla, columna)
LEFT JOIN information_schema.columns c
       ON c.table_schema = 'public' AND c.table_name = e.tabla AND c.column_name = e.columna;

INSERT INTO resultado_qa (prueba, resultado)
SELECT 'Tabla demanda_diaria',
       CASE WHEN to_regclass('public.demanda_diaria') IS NULL THEN 'FALTA' ELSE 'OK' END;

INSERT INTO resultado_qa (prueba, resultado)
SELECT 'Vista ' || v.nombre,
       CASE WHEN pv.viewname IS NULL THEN 'FALTA' ELSE 'OK' END
FROM (VALUES ('dim_producto'),('dim_proveedor'),('dim_almacen')) AS v(nombre)
LEFT JOIN pg_views pv ON pv.schemaname = 'public' AND pv.viewname = v.nombre;

INSERT INTO resultado_qa (prueba, resultado)
SELECT 'Indice ' || i.nombre,
       CASE WHEN pi.indexname IS NULL THEN 'FALTA' ELSE 'OK' END
FROM (VALUES
    ('idx_fact_fecha'),('idx_fact_producto'),('idx_fact_proveedor'),
    ('idx_oc_proveedor_fecha'),('idx_detalle_orden'),('idx_envios_orden'),
    ('idx_mov_orden'),('idx_mov_alm_prod_fecha'),('idx_demanda_prod_fecha')
) AS i(nombre)
LEFT JOIN pg_indexes pi ON pi.schemaname = 'public' AND pi.indexname = i.nombre;

INSERT INTO resultado_qa (prueba, resultado)
SELECT 'tipo_cambio sin fuente nula',
       CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'FALLA (' || COUNT(*) || ' filas)' END
FROM tipo_cambio WHERE fuente IS NULL;

INSERT INTO resultado_qa (prueba, resultado)
SELECT 'Total de tablas en public = 14',
       CASE WHEN COUNT(*) = 14 THEN 'OK' ELSE 'REVISAR (' || COUNT(*) || ')' END
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

-- ------------------------------------------------------------
-- B. Reglas de negocio (cada prueba en su propio subbloque)
-- ------------------------------------------------------------
DO $$
DECLARE
    c_ok CONSTANT TEXT := 'OK';
BEGIN
    -- 1. DESCARTADA sin motivo debe rechazarse
    BEGIN
        INSERT INTO recomendaciones (recomendacion_id, codigo_regla, modulo, severidad, titulo, solucion_recomendada, estado)
        VALUES (-1, 'QA', 'INVENTARIOS', 'INFO', 'qa', 'qa', 'DESCARTADA');
        INSERT INTO resultado_qa (prueba, resultado) VALUES ('Rechaza DESCARTADA sin motivo', 'FALLA');
    EXCEPTION WHEN check_violation THEN
        INSERT INTO resultado_qa (prueba, resultado) VALUES ('Rechaza DESCARTADA sin motivo', c_ok);
    END;

    -- 2. DESCARTADA con motivo debe aceptarse
    BEGIN
        INSERT INTO recomendaciones (recomendacion_id, codigo_regla, modulo, severidad, titulo, solucion_recomendada, estado, motivo_descarte)
        VALUES (-2, 'QA', 'INVENTARIOS', 'INFO', 'qa', 'qa', 'DESCARTADA', 'prueba de QA');
        INSERT INTO resultado_qa (prueba, resultado) VALUES ('Acepta DESCARTADA con motivo', c_ok);
    EXCEPTION WHEN OTHERS THEN
        INSERT INTO resultado_qa (prueba, resultado) VALUES ('Acepta DESCARTADA con motivo', 'FALLA: ' || SQLERRM);
    END;

    -- 3. Ahorro real en una recomendacion no atendida debe rechazarse
    BEGIN
        INSERT INTO recomendaciones (recomendacion_id, codigo_regla, modulo, severidad, titulo, solucion_recomendada, estado, ahorro_real_mxn)
        VALUES (-3, 'QA', 'INVENTARIOS', 'INFO', 'qa', 'qa', 'NUEVA', 1000);
        INSERT INTO resultado_qa (prueba, resultado) VALUES ('Rechaza ahorro real fuera de ATENDIDA', 'FALLA');
    EXCEPTION WHEN check_violation THEN
        INSERT INTO resultado_qa (prueba, resultado) VALUES ('Rechaza ahorro real fuera de ATENDIDA', c_ok);
    END;

    -- 4. ATENDIDA con ahorro real y opciones en arreglo debe aceptarse
    BEGIN
        INSERT INTO recomendaciones (recomendacion_id, codigo_regla, modulo, severidad, titulo, solucion_recomendada, estado, ahorro_real_mxn, opciones)
        VALUES (-4, 'QA', 'INVENTARIOS', 'INFO', 'qa', 'qa', 'ATENDIDA', 1000,
                '[{"clave":"A","costo_total_esperado_mxn":25400,"recomendada":true,"elegida":true}]');
        INSERT INTO resultado_qa (prueba, resultado) VALUES ('Acepta ATENDIDA con ahorro y opciones', c_ok);
    EXCEPTION WHEN OTHERS THEN
        INSERT INTO resultado_qa (prueba, resultado) VALUES ('Acepta ATENDIDA con ahorro y opciones', 'FALLA: ' || SQLERRM);
    END;

    -- 5. opciones que no es arreglo debe rechazarse
    BEGIN
        INSERT INTO recomendaciones (recomendacion_id, codigo_regla, modulo, severidad, titulo, solucion_recomendada, opciones)
        VALUES (-5, 'QA', 'INVENTARIOS', 'INFO', 'qa', 'qa', '{"clave":"A"}');
        INSERT INTO resultado_qa (prueba, resultado) VALUES ('Rechaza opciones que no son arreglo', 'FALLA');
    EXCEPTION WHEN check_violation THEN
        INSERT INTO resultado_qa (prueba, resultado) VALUES ('Rechaza opciones que no son arreglo', c_ok);
    END;

    -- 6. Una SALIDA no puede ligarse a una orden de compra
    BEGIN
        INSERT INTO movimientos_inventario (movimiento_id, tipo_movimiento, cantidad, orden_id)
        VALUES (-1, 'SALIDA', 1, -1);
        INSERT INTO resultado_qa (prueba, resultado) VALUES ('Rechaza SALIDA con orden_id', 'FALLA');
    EXCEPTION WHEN check_violation THEN
        INSERT INTO resultado_qa (prueba, resultado) VALUES ('Rechaza SALIDA con orden_id', c_ok);
    END;

    -- 7. Demanda: entregadas no puede superar solicitadas
    BEGIN
        INSERT INTO demanda_diaria (fecha, almacen_id, producto_id, unidades_solicitadas, unidades_entregadas)
        VALUES (DATE '1900-01-01', -1, -1, 3, 5);
        INSERT INTO resultado_qa (prueba, resultado) VALUES ('Rechaza entregadas > solicitadas', 'FALLA');
    EXCEPTION WHEN check_violation THEN
        INSERT INTO resultado_qa (prueba, resultado) VALUES ('Rechaza entregadas > solicitadas', c_ok);
    END;

    -- 8. Fuente de tipo de cambio fuera del catalogo
    BEGIN
        INSERT INTO tipo_cambio (tipo_cambio_id, moneda_origen, moneda_destino, tasa, fecha, fuente)
        VALUES (-1, 'USD', 'MXN', 1, DATE '1900-01-01', 'OTRA');
        INSERT INTO resultado_qa (prueba, resultado) VALUES ('Rechaza fuente fuera de catalogo', 'FALLA');
    EXCEPTION WHEN check_violation THEN
        INSERT INTO resultado_qa (prueba, resultado) VALUES ('Rechaza fuente fuera de catalogo', c_ok);
    END;

    -- 9. Tipo de cambio duplicado (mismo par, fecha y fuente)
    BEGIN
        INSERT INTO tipo_cambio (tipo_cambio_id, moneda_origen, moneda_destino, tasa, fecha, fuente)
        VALUES (-2, 'USD', 'MXN', 1, DATE '1900-01-01', 'BANXICO_SIE'),
               (-3, 'USD', 'MXN', 2, DATE '1900-01-01', 'BANXICO_SIE');
        INSERT INTO resultado_qa (prueba, resultado) VALUES ('Rechaza tipo de cambio duplicado', 'FALLA');
    EXCEPTION WHEN unique_violation THEN
        INSERT INTO resultado_qa (prueba, resultado) VALUES ('Rechaza tipo de cambio duplicado', c_ok);
    END;
END $$;

SELECT n, prueba, resultado FROM resultado_qa ORDER BY n;

SELECT COUNT(*) FILTER (WHERE resultado = 'OK') AS pruebas_ok,
       COUNT(*)                                AS pruebas_total
FROM resultado_qa;

ROLLBACK;