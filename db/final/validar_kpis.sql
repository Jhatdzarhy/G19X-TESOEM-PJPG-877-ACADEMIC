-- ============================================================
-- Validacion de los datos simulados y de los 11 KPIs del PDR (seccion 7)
-- Criterio de aceptacion del PDR (seccion 12): cada KPI con fuente trazable
-- en el esquema de la seccion 8, ampliado por CC-02 (control de cambios, riesgo R6).
--
-- Comprueba:
--   A. Integridad: stock diario no negativo, fechas coherentes, recepciones
--      ligadas a su orden, demanda igual a salidas, texto en ASCII (CC-11).
--   B. Los 11 KPIs calculados con SQL sobre todo el periodo, contra un rango
--      de plausibilidad. Indice de riesgo y MAPE se calculan en FastAPI
--      (Sprint 2); aqui se valida que sus insumos esten completos.
--
-- No modifica datos: todo termina en ROLLBACK.
-- El volumen por SKU vive en backend/etl/datos/volumen_por_sku.json (decision
-- registrada: no se modifica el esquema del PDR); se recibe en base64 en la
-- variable vol_b64. Ejecucion desde la raiz del proyecto (PowerShell):
--   $vol = [Convert]::ToBase64String([IO.File]::ReadAllBytes("$PWD\backend\etl\datos\volumen_por_sku.json"))
--   psql -U postgres -h localhost -d postgres -P pager=off -v vol_b64=$vol -f db\final\validar_kpis.sql
-- ============================================================
\set ON_ERROR_STOP on
\connect supply_chain_final
SET client_encoding = 'UTF8';
SET client_min_messages = warning;

BEGIN;

CREATE TEMP TABLE resultado_kpi (
    n          SERIAL,
    bloque     TEXT,
    prueba     TEXT,
    valor      TEXT,
    criterio   TEXT,
    resultado  TEXT
) ON COMMIT DROP;

-- ------------------------------------------------------------
-- Insumos comunes
-- ------------------------------------------------------------
CREATE TEMP TABLE periodo ON COMMIT DROP AS
SELECT MIN(fecha) AS inicio, MAX(fecha) AS fin, (MAX(fecha) - MIN(fecha) + 1) AS dias
FROM demanda_diaria;

CREATE TEMP TABLE volumen ON COMMIT DROP AS
SELECT p.producto_id, v.value::numeric AS m3
FROM jsonb_each_text(convert_from(decode(:'vol_b64', 'base64'), 'UTF8')::jsonb) v
JOIN productos p ON p.sku = v.key;

-- stock al cierre de cada dia por almacen y producto (incluye el inventario inicial)
CREATE TEMP TABLE stock_diario ON COMMIT DROP AS
WITH neto AS (
    SELECT almacen_id, producto_id, fecha::date AS f,
           SUM(CASE WHEN tipo_movimiento = 'ENTRADA' THEN cantidad ELSE -cantidad END) AS neto
    FROM movimientos_inventario
    GROUP BY 1, 2, 3
),
pares AS (SELECT DISTINCT almacen_id, producto_id FROM neto),
inicial AS (
    SELECT n.almacen_id, n.producto_id, SUM(n.neto) AS inicial
    FROM neto n, periodo p WHERE n.f < p.inicio GROUP BY 1, 2
),
rejilla AS (
    SELECT pa.almacen_id, pa.producto_id, d::date AS dia
    FROM pares pa, periodo p, generate_series(p.inicio, p.fin, INTERVAL '1 day') d
)
SELECT r.almacen_id, r.producto_id, r.dia,
       COALESCE(i.inicial, 0)
         + SUM(COALESCE(n.neto, 0)) OVER (PARTITION BY r.almacen_id, r.producto_id ORDER BY r.dia) AS stock
FROM rejilla r
LEFT JOIN neto n    ON n.almacen_id = r.almacen_id AND n.producto_id = r.producto_id AND n.f = r.dia
LEFT JOIN inicial i ON i.almacen_id = r.almacen_id AND i.producto_id = r.producto_id;

-- tipo de cambio FIX vigente (ultima publicacion en o antes de la fecha), CC-03
CREATE TEMP TABLE compras_mxn ON COMMIT DROP AS
SELECT o.orden_id, o.fecha_orden::date AS dia, o.monto_total AS monto_usd,
       (SELECT t.tasa FROM tipo_cambio t
         WHERE t.fuente = 'BANXICO_SIE' AND t.moneda_origen = 'USD' AND t.moneda_destino = 'MXN'
           AND t.fecha <= o.fecha_orden::date
         ORDER BY t.fecha DESC LIMIT 1) AS tc
FROM ordenes_compra o;

-- ------------------------------------------------------------
-- A. Integridad de los datos
-- ------------------------------------------------------------
INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'Integridad', 'Stock diario negativo (almacen, producto, dia)', COUNT(*)::text, '= 0',
       CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'FALLA' END
FROM stock_diario WHERE stock < 0;

INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'Integridad', 'Demanda completa: filas de demanda_diaria', COUNT(*)::text,
       '= dias x almacenes x productos',
       CASE WHEN COUNT(*) = (SELECT dias FROM periodo) * (SELECT COUNT(*) FROM almacenes) * (SELECT COUNT(*) FROM productos)
            THEN 'OK' ELSE 'FALLA' END
FROM demanda_diaria;

INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'Integridad', 'Entregado en demanda_diaria igual a SALIDA de inventario', COUNT(*)::text, '0 diferencias',
       CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'FALLA' END
FROM (
    SELECT d.fecha, d.almacen_id, d.producto_id
    FROM demanda_diaria d
    LEFT JOIN (SELECT fecha::date f, almacen_id, producto_id, SUM(cantidad) s
               FROM movimientos_inventario WHERE tipo_movimiento = 'SALIDA' GROUP BY 1, 2, 3) m
           ON m.f = d.fecha AND m.almacen_id = d.almacen_id AND m.producto_id = d.producto_id
    WHERE d.unidades_entregadas <> COALESCE(m.s, 0)
) x;

INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'Integridad', 'Recepciones: ENTRADA por orden igual a cantidad_recibida', COUNT(*)::text, '0 diferencias',
       CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'FALLA' END
FROM (
    SELECT d.orden_id, d.producto_id
    FROM detalle_orden_compra d
    LEFT JOIN (SELECT orden_id, producto_id, SUM(cantidad) s FROM movimientos_inventario
               WHERE orden_id IS NOT NULL GROUP BY 1, 2) m
           ON m.orden_id = d.orden_id AND m.producto_id = d.producto_id
    WHERE d.cantidad_recibida IS NOT NULL
    GROUP BY d.orden_id, d.producto_id, m.s
    HAVING SUM(d.cantidad_recibida) <> COALESCE(m.s, 0)
) x;

INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'Integridad', 'Recibido mayor que lo ordenado', COUNT(*)::text, '= 0',
       CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'FALLA' END
FROM detalle_orden_compra WHERE cantidad_recibida > cantidad;

INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'Integridad', 'Fechas incoherentes en ordenes y envios', COUNT(*)::text, '= 0',
       CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'FALLA' END
FROM ordenes_compra o JOIN envios e ON e.orden_id = o.orden_id
WHERE e.fecha_salida < o.fecha_orden::date
   OR o.fecha_entrega_estim < o.fecha_orden
   OR e.fecha_llegada_real < e.fecha_salida
   OR (o.fecha_entrega_real IS DISTINCT FROM e.fecha_llegada_real);

INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'Integridad', 'Estatus coherente con la recepcion', COUNT(*)::text, '= 0',
       CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'FALLA' END
FROM ordenes_compra
WHERE (estatus = 'EN_TRANSITO' AND fecha_entrega_real IS NOT NULL)
   OR (estatus IN ('RECIBIDA', 'RECIBIDA_PARCIAL') AND fecha_entrega_real IS NULL)
   OR estatus NOT IN ('EN_TRANSITO', 'RECIBIDA', 'RECIBIDA_PARCIAL');

INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'Integridad', 'Texto fuera de ASCII (CC-11)', COUNT(*)::text, '= 0',
       CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'FALLA' END
FROM (
    SELECT nombre || COALESCE(pais, '') || COALESCE(ciudad, '') AS t FROM proveedores
    UNION ALL SELECT nombre || COALESCE(ubicacion, '') FROM almacenes
    UNION ALL SELECT sku || nombre || COALESCE(categoria, '') || COALESCE(unidad_medida, '') || COALESCE(moneda, '') FROM productos
    UNION ALL SELECT estatus FROM ordenes_compra
    UNION ALL SELECT COALESCE(condicion_climatica, '') FROM envios
    UNION ALL SELECT tipo_movimiento FROM movimientos_inventario
    UNION ALL SELECT moneda_origen || moneda_destino || fuente FROM tipo_cambio
) x
WHERE t ~ '[^ -~]';

INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'Integridad', 'Ordenes sin tipo de cambio FIX vigente (CC-03)', COUNT(*)::text, '= 0',
       CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'FALLA' END
FROM compras_mxn WHERE tc IS NULL;

INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'Integridad', 'Productos sin volumen en volumen_por_sku.json', COUNT(*)::text, '= 0',
       CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'FALLA' END
FROM productos p WHERE NOT EXISTS (SELECT 1 FROM volumen v WHERE v.producto_id = p.producto_id);

-- ------------------------------------------------------------
-- B. KPIs del PDR (seccion 7), periodo completo
-- ------------------------------------------------------------

-- 1. Lead time de proveedor = fecha de recepcion - fecha de orden
INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'KPI', '01 Lead time de proveedor (dias)', ROUND(v, 2)::text, '3 a 40',
       CASE WHEN v BETWEEN 3 AND 40 THEN 'OK' ELSE 'REVISAR' END
FROM (SELECT AVG(EXTRACT(EPOCH FROM (fecha_entrega_real - fecha_orden)) / 86400) AS v
      FROM ordenes_compra WHERE fecha_entrega_real IS NOT NULL) x;

-- 2. Variacion de costo de compra = (costo real - presupuestado) / presupuestado
--    presupuestado = costo_unitario del catalogo (costo estandar)
INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'KPI', '02 Variacion de costo de compra', ROUND(v * 100, 2)::text || ' %', '-10 % a 15 %',
       CASE WHEN v BETWEEN -0.10 AND 0.15 THEN 'OK' ELSE 'REVISAR' END
FROM (SELECT SUM(d.cantidad * d.precio_unitario) / SUM(d.cantidad * p.costo_unitario) - 1 AS v
      FROM detalle_orden_compra d JOIN productos p USING (producto_id)) x;

-- 3. Rotacion de inventario = costo de mercancia vendida / inventario promedio (valor, USD)
-- 5. Dias de inventario disponible = inventario promedio / consumo diario promedio
WITH cogs AS (
    SELECT SUM(m.cantidad * p.costo_unitario) AS v
    FROM movimientos_inventario m JOIN productos p USING (producto_id), periodo pe
    WHERE m.tipo_movimiento = 'SALIDA' AND m.fecha::date BETWEEN pe.inicio AND pe.fin
),
inv AS (
    SELECT AVG(valor) AS v FROM (
        SELECT s.dia, SUM(s.stock * p.costo_unitario) AS valor
        FROM stock_diario s JOIN productos p USING (producto_id) GROUP BY s.dia) d
)
INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'KPI', '03 Rotacion de inventario (veces al ano)', ROUND(cogs.v / inv.v * 365.0 / pe.dias, 2)::text, '3 a 30',
       CASE WHEN cogs.v / inv.v * 365.0 / pe.dias BETWEEN 3 AND 30 THEN 'OK' ELSE 'REVISAR' END
FROM cogs, inv, periodo pe
UNION ALL
SELECT 'KPI', '05 Dias de inventario disponible (DOH)', ROUND(inv.v / (cogs.v / pe.dias), 1)::text, '10 a 120',
       CASE WHEN inv.v / (cogs.v / pe.dias) BETWEEN 10 AND 120 THEN 'OK' ELSE 'REVISAR' END
FROM cogs, inv, periodo pe;

-- 4. Nivel de servicio (Fill Rate de servicio, CC-05) = entregadas / solicitadas
INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'KPI', '04 Fill Rate de servicio', ROUND(v * 100, 2)::text || ' %', '85 % a 100 %',
       CASE WHEN v BETWEEN 0.85 AND 1 THEN 'OK' ELSE 'REVISAR' END
FROM (SELECT SUM(unidades_entregadas) / NULLIF(SUM(unidades_solicitadas), 0) AS v FROM demanda_diaria) x;

-- 6. OTIF = entregas completas y a tiempo / total de entregas (CC-02: cantidad_recibida)
INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'KPI', '06 OTIF', ROUND(v * 100, 2)::text || ' %', '60 % a 98 %',
       CASE WHEN v BETWEEN 0.60 AND 0.98 THEN 'OK' ELSE 'REVISAR' END
FROM (
    SELECT AVG(CASE WHEN e.fecha_llegada_real::date <= e.fecha_llegada_estim::date
                     AND NOT EXISTS (SELECT 1 FROM detalle_orden_compra d
                                     WHERE d.orden_id = e.orden_id AND d.cantidad_recibida < d.cantidad)
                    THEN 1.0 ELSE 0.0 END) AS v
    FROM envios e WHERE e.fecha_llegada_real IS NOT NULL
) x;

-- 7. Costo de transporte por unidad = flete total / unidades transportadas (MXN)
INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'KPI', '07 Costo de transporte por unidad (MXN)', ROUND(v, 2)::text, '5 a 200',
       CASE WHEN v BETWEEN 5 AND 200 THEN 'OK' ELSE 'REVISAR' END
FROM (
    SELECT SUM(e.costo_flete) / NULLIF(SUM(u.unidades), 0) AS v
    FROM envios e
    JOIN (SELECT orden_id, SUM(cantidad_recibida) unidades FROM detalle_orden_compra GROUP BY 1) u USING (orden_id)
    WHERE e.fecha_llegada_real IS NOT NULL
) x;

-- 8. Utilizacion de almacen = espacio ocupado / espacio total (promedio y maximo diario)
WITH diaria AS (
    SELECT a.almacen_id, a.nombre, s.dia, SUM(s.stock * v.m3) / a.capacidad_m3 AS u
    FROM stock_diario s JOIN volumen v USING (producto_id) JOIN almacenes a USING (almacen_id)
    GROUP BY a.almacen_id, a.nombre, a.capacidad_m3, s.dia
)
INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'KPI', '08 Utilizacion de almacen: ' || nombre,
       ROUND(AVG(u) * 100, 1)::text || ' % prom, ' || ROUND(MAX(u) * 100, 1)::text || ' % max',
       'prom 30 % a 95 %, max <= 100 %',
       CASE WHEN AVG(u) BETWEEN 0.30 AND 0.95 AND MAX(u) <= 1.0 THEN 'OK' ELSE 'REVISAR' END
FROM diaria GROUP BY almacen_id, nombre ORDER BY almacen_id;

-- 9. Indice de riesgo de proveedor: se calcula en FastAPI (CC-07); aqui, insumos completos
INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'KPI', '09 Riesgo de proveedor: proveedores con menos de 5 envios recibidos',
       COUNT(*)::text, '= 0', CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'REVISAR' END
FROM proveedores p
WHERE (SELECT COUNT(*) FROM envios e WHERE e.proveedor_id = p.proveedor_id AND e.fecha_llegada_real IS NOT NULL) < 5;

-- 10. MAPE del pronostico: se calcula en FastAPI (CC-07); aqui, serie diaria completa por SKU
INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'KPI', '10 MAPE: productos con serie diaria incompleta', COUNT(*)::text, '= 0',
       CASE WHEN COUNT(*) = 0 THEN 'OK' ELSE 'FALLA' END
FROM (SELECT producto_id FROM demanda_diaria GROUP BY producto_id
      HAVING COUNT(DISTINCT fecha) <> (SELECT dias FROM periodo)) x;

-- 11. Impacto de tipo de cambio = compras valuadas al FIX de cada orden
--     menos las mismas compras al FIX del inicio del periodo (MXN)
WITH base AS (
    SELECT t.tasa FROM tipo_cambio t, periodo p
    WHERE t.fuente = 'BANXICO_SIE' AND t.moneda_origen = 'USD' AND t.moneda_destino = 'MXN' AND t.fecha <= p.inicio
    ORDER BY t.fecha DESC LIMIT 1
),
calc AS (
    SELECT SUM(c.monto_usd * c.tc) AS real_mxn, SUM(c.monto_usd * b.tasa) AS base_mxn
    FROM compras_mxn c, base b
)
INSERT INTO resultado_kpi (bloque, prueba, valor, criterio, resultado)
SELECT 'KPI', '11 Impacto de tipo de cambio (MXN)',
       TO_CHAR(real_mxn - base_mxn, 'FM999,999,999,990') || ' (' || ROUND((real_mxn / base_mxn - 1) * 100, 2)::text || ' %)',
       '-20 % a 20 %',
       CASE WHEN real_mxn / base_mxn - 1 BETWEEN -0.20 AND 0.20 THEN 'OK' ELSE 'REVISAR' END
FROM calc;

-- ------------------------------------------------------------
-- Resultado
-- ------------------------------------------------------------
SELECT n, bloque, prueba, valor, criterio, resultado FROM resultado_kpi
ORDER BY bloque <> 'Integridad', CASE WHEN bloque = 'KPI' THEN prueba END, n;

SELECT COUNT(*) FILTER (WHERE resultado = 'OK')      AS ok,
       COUNT(*) FILTER (WHERE resultado = 'REVISAR') AS revisar,
       COUNT(*) FILTER (WHERE resultado = 'FALLA')   AS falla,
       COUNT(*)                                      AS total
FROM resultado_kpi;

ROLLBACK;