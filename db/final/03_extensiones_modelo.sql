-- ============================================================
-- Proyecto final: extensiones del modelo de datos
-- CC-02 (control de cambios, riesgo R6). Aprobado.
-- Sustento: PDR seccion 12 (cada KPI con fuente trazable en el
-- esquema de la seccion 8) y seccion 8.2 (modelo estrella e indices).
--
-- Script ADITIVO: no modifica ni elimina ninguna tabla o columna del PDR.
-- Idempotente: puede ejecutarse varias veces sin error ni duplicados.
-- Atomico: todo corre en una sola transaccion; si algo falla, no se
-- aplica nada.
--
-- Orden de ejecucion: 01_esquema_pdr.sql -> 02_centro_soluciones.sql
-- -> 03_extensiones_modelo.sql. Si se vuelve a ejecutar 02 (que borra
-- recomendaciones y plan_acciones), se debe volver a ejecutar este 03.
-- ============================================================
\set ON_ERROR_STOP on
\connect supply_chain_final
SET client_encoding = 'UTF8';
SET client_min_messages = warning;

BEGIN;

-- ------------------------------------------------------------
-- 0. Precondicion: existen las 13 tablas de los scripts 01 y 02
-- ------------------------------------------------------------
DO $$
DECLARE
    requeridas TEXT[] := ARRAY[
        'proveedores','productos','almacenes','ordenes_compra',
        'detalle_orden_compra','movimientos_inventario','envios',
        'tipo_cambio','fact_supply_chain','dim_tiempo','forecast_demanda',
        'recomendaciones','plan_acciones'];
    t TEXT;
BEGIN
    FOREACH t IN ARRAY requeridas LOOP
        IF to_regclass('public.' || t) IS NULL THEN
            RAISE EXCEPTION 'Falta la tabla %. Ejecute antes 01_esquema_pdr.sql y 02_centro_soluciones.sql', t;
        END IF;
    END LOOP;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'almacenes' AND column_name = 'capacidad_m3') THEN
        RAISE EXCEPTION 'almacenes.capacidad_m3 no existe: el esquema 01 no coincide con PDR 8.1';
    END IF;
END $$;

-- ------------------------------------------------------------
-- 1. Cantidad recibida por renglon de orden (CC-02)
--    Fuente del "in full" de OTIF y del Fill Rate de proveedor (CC-05).
--    NULL = aun no recibido.
-- ------------------------------------------------------------
ALTER TABLE detalle_orden_compra
    ADD COLUMN IF NOT EXISTS cantidad_recibida NUMERIC(12,2)
        CONSTRAINT ck_detalle_cant_recibida CHECK (cantidad_recibida >= 0);

COMMENT ON COLUMN detalle_orden_compra.cantidad_recibida IS
    'CC-02: unidades recibidas del renglon; NULL si no se ha recibido. OTIF in full y Fill Rate de proveedor (CC-05)';

-- ------------------------------------------------------------
-- 2. Entrada de inventario ligada a su orden de compra (CC-02)
--    Llave foranea opcional: solo las ENTRADA por compra la llevan.
-- ------------------------------------------------------------
ALTER TABLE movimientos_inventario
    ADD COLUMN IF NOT EXISTS orden_id INT
        CONSTRAINT fk_mov_orden REFERENCES ordenes_compra(orden_id);

ALTER TABLE movimientos_inventario DROP CONSTRAINT IF EXISTS ck_mov_orden_solo_entrada;
ALTER TABLE movimientos_inventario
    ADD CONSTRAINT ck_mov_orden_solo_entrada
        CHECK (orden_id IS NULL OR tipo_movimiento = 'ENTRADA');

COMMENT ON COLUMN movimientos_inventario.orden_id IS
    'CC-02: orden de compra que origino la ENTRADA; NULL en salidas y ajustes';

-- ------------------------------------------------------------
-- 3. Demanda diaria solicitada contra entregada (CC-02)
--    Fuente del Fill Rate de servicio (KPI de Inventario, CC-05),
--    del pronostico Holt-Winters y del MAPE (CC-07).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS demanda_diaria (
    fecha                 DATE          NOT NULL,
    almacen_id            INT           NOT NULL REFERENCES almacenes(almacen_id),
    producto_id           INT           NOT NULL REFERENCES productos(producto_id),
    unidades_solicitadas  NUMERIC(12,2) NOT NULL CHECK (unidades_solicitadas >= 0),
    unidades_entregadas   NUMERIC(12,2) NOT NULL CHECK (unidades_entregadas >= 0),
    CONSTRAINT pk_demanda_diaria PRIMARY KEY (fecha, almacen_id, producto_id),
    CONSTRAINT ck_demanda_entregadas_le_solicitadas
        CHECK (unidades_entregadas <= unidades_solicitadas)
);

COMMENT ON TABLE demanda_diaria IS
    'CC-02: demanda diaria por almacen y producto. Fill Rate de servicio (CC-05), pronostico y MAPE (CC-07)';

-- ------------------------------------------------------------
-- 4. Ubicacion geografica de almacenes y proveedores (CC-02)
--    Coordenadas para el clima de Open-Meteo (CC-04) y el mapa de rutas.
-- ------------------------------------------------------------
ALTER TABLE almacenes
    ADD COLUMN IF NOT EXISTS latitud  NUMERIC(9,6)
        CONSTRAINT ck_almacen_latitud  CHECK (latitud  BETWEEN -90  AND 90),
    ADD COLUMN IF NOT EXISTS longitud NUMERIC(9,6)
        CONSTRAINT ck_almacen_longitud CHECK (longitud BETWEEN -180 AND 180);

ALTER TABLE proveedores
    ADD COLUMN IF NOT EXISTS ciudad   VARCHAR(100),
    ADD COLUMN IF NOT EXISTS latitud  NUMERIC(9,6)
        CONSTRAINT ck_proveedor_latitud  CHECK (latitud  BETWEEN -90  AND 90),
    ADD COLUMN IF NOT EXISTS longitud NUMERIC(9,6)
        CONSTRAINT ck_proveedor_longitud CHECK (longitud BETWEEN -180 AND 180);

-- ------------------------------------------------------------
-- 5. Precipitacion del envio (CC-02, CC-04)
--    Se escribe junto con condicion_climatica en el mismo paso del generador.
-- ------------------------------------------------------------
ALTER TABLE envios
    ADD COLUMN IF NOT EXISTS precipitacion_mm NUMERIC(6,2)
        CONSTRAINT ck_envio_precipitacion CHECK (precipitacion_mm >= 0);

COMMENT ON COLUMN envios.precipitacion_mm IS
    'CC-02 y CC-04: precipitacion diaria (mm) de Open-Meteo en la ruta, usada por el generador para el retraso';
COMMENT ON COLUMN envios.almacen_origen_id IS
    'CC-06: en el flujo de compras se interpreta como almacen de destino';

-- ------------------------------------------------------------
-- 6. Fuente del tipo de cambio y unicidad por dia (CC-02, CC-03)
--    Los registros existentes vienen de ExchangeRate-API (ETL del Sprint 1).
--    El cargador de Banxico SIE escribe fuente = 'BANXICO_SIE' explicitamente.
-- ------------------------------------------------------------
ALTER TABLE tipo_cambio
    ADD COLUMN IF NOT EXISTS fuente VARCHAR(30);

UPDATE tipo_cambio SET fuente = 'EXCHANGERATE_API' WHERE fuente IS NULL;

ALTER TABLE tipo_cambio ALTER COLUMN fuente SET DEFAULT 'EXCHANGERATE_API';
ALTER TABLE tipo_cambio ALTER COLUMN fuente SET NOT NULL;

ALTER TABLE tipo_cambio DROP CONSTRAINT IF EXISTS ck_tipo_cambio_fuente;
ALTER TABLE tipo_cambio
    ADD CONSTRAINT ck_tipo_cambio_fuente
        CHECK (fuente IN ('EXCHANGERATE_API','BANXICO_SIE'));

-- Si el ETL se ejecuto mas de una vez el mismo dia, se conserva el registro
-- mas reciente de cada par, fecha y fuente antes de crear la restriccion.
DELETE FROM tipo_cambio t
USING tipo_cambio t2
WHERE t.moneda_origen  IS NOT DISTINCT FROM t2.moneda_origen
  AND t.moneda_destino IS NOT DISTINCT FROM t2.moneda_destino
  AND t.fecha          IS NOT DISTINCT FROM t2.fecha
  AND t.fuente = t2.fuente
  AND t.tipo_cambio_id < t2.tipo_cambio_id;

ALTER TABLE tipo_cambio DROP CONSTRAINT IF EXISTS uq_tipo_cambio_par_fecha_fuente;
ALTER TABLE tipo_cambio
    ADD CONSTRAINT uq_tipo_cambio_par_fecha_fuente
        UNIQUE NULLS NOT DISTINCT (moneda_origen, moneda_destino, fecha, fuente);

COMMENT ON COLUMN tipo_cambio.fuente IS
    'CC-03: EXCHANGERATE_API (tasa diaria, PDR seccion 4) o BANXICO_SIE (historico FIX)';

-- ------------------------------------------------------------
-- 7. Centro de soluciones: opciones, ahorro real y descarte (CC-02 sobre CC-01)
--    opciones: arreglo JSON, una entrada por opcion comparada, por ejemplo
--    [{"clave":"A","descripcion":"Transferir 420 u desde CDMX",
--      "costo_total_esperado_mxn":25400,"recomendada":true,"elegida":false}]
--    La opcion que elige la persona se marca con "elegida": true.
--    La IA solo recomienda; no ejecuta compras (PDR seccion 2).
-- ------------------------------------------------------------
ALTER TABLE recomendaciones
    ADD COLUMN IF NOT EXISTS opciones JSONB
        CONSTRAINT ck_reco_opciones_arreglo
            CHECK (opciones IS NULL OR jsonb_typeof(opciones) = 'array'),
    ADD COLUMN IF NOT EXISTS ahorro_real_mxn NUMERIC(14,2),
    ADD COLUMN IF NOT EXISTS motivo_descarte VARCHAR(300);

-- Estado DESCARTADA: se reemplaza la restriccion original de 02.
ALTER TABLE recomendaciones DROP CONSTRAINT IF EXISTS recomendaciones_estado_check;
ALTER TABLE recomendaciones DROP CONSTRAINT IF EXISTS ck_reco_estado;
ALTER TABLE recomendaciones
    ADD CONSTRAINT ck_reco_estado
        CHECK (estado IN ('NUEVA','EN_REVISION','ATENDIDA','DESCARTADA'));

-- Descartar exige motivo (boton "Descartar con motivo").
ALTER TABLE recomendaciones DROP CONSTRAINT IF EXISTS ck_reco_descarte_con_motivo;
ALTER TABLE recomendaciones
    ADD CONSTRAINT ck_reco_descarte_con_motivo
        CHECK (estado <> 'DESCARTADA' OR motivo_descarte IS NOT NULL);

-- El ahorro real solo se registra en soluciones atendidas (ahorro real contra proyectado).
ALTER TABLE recomendaciones DROP CONSTRAINT IF EXISTS ck_reco_ahorro_solo_atendida;
ALTER TABLE recomendaciones
    ADD CONSTRAINT ck_reco_ahorro_solo_atendida
        CHECK (ahorro_real_mxn IS NULL OR estado = 'ATENDIDA');

COMMENT ON COLUMN recomendaciones.opciones IS
    'CC-02: opciones comparadas por costo total esperado (CC-07); la elegida lleva "elegida": true';
COMMENT ON COLUMN recomendaciones.ahorro_real_mxn IS
    'CC-02: ahorro medido al cierre del plan; se compara contra impacto_estimado_mxn';
COMMENT ON COLUMN recomendaciones.motivo_descarte IS
    'CC-02: obligatorio cuando estado = DESCARTADA';

-- ------------------------------------------------------------
-- 8. Vistas de dimensiones del modelo estrella (CC-02, PDR 8.2)
--    Vistas sobre los catalogos: una sola fuente de verdad, sin copias.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW dim_producto AS
SELECT producto_id, sku, nombre, categoria, unidad_medida, costo_unitario, moneda
FROM productos;

CREATE OR REPLACE VIEW dim_proveedor AS
SELECT proveedor_id, nombre, pais, ciudad, calificacion, activo, latitud, longitud
FROM proveedores;

CREATE OR REPLACE VIEW dim_almacen AS
SELECT almacen_id, nombre, ubicacion, capacidad_m3, latitud, longitud
FROM almacenes;

COMMENT ON VIEW dim_producto  IS 'CC-02: dimension producto del modelo estrella (PDR 8.2)';
COMMENT ON VIEW dim_proveedor IS 'CC-02: dimension proveedor del modelo estrella (PDR 8.2)';
COMMENT ON VIEW dim_almacen   IS 'CC-02: dimension almacen del modelo estrella (PDR 8.2)';

-- ------------------------------------------------------------
-- 9. Indices
--    9a. Recomendados por el PDR, seccion 8.2
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_fact_fecha           ON fact_supply_chain (fecha_id);
CREATE INDEX IF NOT EXISTS idx_fact_producto        ON fact_supply_chain (producto_id);
CREATE INDEX IF NOT EXISTS idx_fact_proveedor       ON fact_supply_chain (proveedor_id);
CREATE INDEX IF NOT EXISTS idx_oc_proveedor_fecha   ON ordenes_compra (proveedor_id, fecha_orden);

--    9b. Soporte de las llaves foraneas y consultas de KPIs (rendimiento)
CREATE INDEX IF NOT EXISTS idx_detalle_orden        ON detalle_orden_compra (orden_id);
CREATE INDEX IF NOT EXISTS idx_envios_orden         ON envios (orden_id);
CREATE INDEX IF NOT EXISTS idx_mov_orden            ON movimientos_inventario (orden_id);
CREATE INDEX IF NOT EXISTS idx_mov_alm_prod_fecha   ON movimientos_inventario (almacen_id, producto_id, fecha);
CREATE INDEX IF NOT EXISTS idx_demanda_prod_fecha   ON demanda_diaria (producto_id, fecha);

COMMIT;

\echo '03_extensiones_modelo.sql aplicado correctamente (CC-02).'