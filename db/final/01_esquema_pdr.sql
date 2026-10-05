-- ============================================================
-- Proyecto final: esquema segun el PDR (secciones 8.1 y 8.2)
-- Se ejecuta SOLO contra supply_chain_final
-- ============================================================
\set ON_ERROR_STOP on
\connect supply_chain_final
SET client_encoding = 'UTF8';

DROP TABLE IF EXISTS forecast_demanda, fact_supply_chain, dim_tiempo, tipo_cambio,
    envios, movimientos_inventario, detalle_orden_compra, ordenes_compra,
    almacenes, productos, proveedores CASCADE;

-- 8.1 Esquema operacional (OLTP)

CREATE TABLE proveedores (
    proveedor_id    SERIAL PRIMARY KEY,
    nombre          VARCHAR(150) NOT NULL,
    pais            VARCHAR(80),
    calificacion    NUMERIC(3,2) DEFAULT 0,
    activo          BOOLEAN DEFAULT TRUE,
    fecha_registro  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE productos (
    producto_id     SERIAL PRIMARY KEY,
    sku             VARCHAR(50) UNIQUE NOT NULL,
    nombre          VARCHAR(150) NOT NULL,
    categoria       VARCHAR(80),
    unidad_medida   VARCHAR(20),
    costo_unitario  NUMERIC(12,2),
    moneda          VARCHAR(10) DEFAULT 'MXN'
);

CREATE TABLE almacenes (
    almacen_id      SERIAL PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL,
    ubicacion       VARCHAR(150),
    capacidad_m3    NUMERIC(12,2)
);

CREATE TABLE ordenes_compra (
    orden_id             SERIAL PRIMARY KEY,
    proveedor_id         INT REFERENCES proveedores(proveedor_id),
    fecha_orden          TIMESTAMP NOT NULL,
    fecha_entrega_estim  TIMESTAMP,
    fecha_entrega_real   TIMESTAMP,
    estatus              VARCHAR(30) DEFAULT 'PENDIENTE',
    monto_total          NUMERIC(14,2)
);

CREATE TABLE detalle_orden_compra (
    detalle_id       SERIAL PRIMARY KEY,
    orden_id         INT REFERENCES ordenes_compra(orden_id),
    producto_id      INT REFERENCES productos(producto_id),
    cantidad         NUMERIC(12,2),
    precio_unitario  NUMERIC(12,2)
);

CREATE TABLE movimientos_inventario (
    movimiento_id    SERIAL PRIMARY KEY,
    almacen_id       INT REFERENCES almacenes(almacen_id),
    producto_id      INT REFERENCES productos(producto_id),
    tipo_movimiento  VARCHAR(20) CHECK (tipo_movimiento IN ('ENTRADA','SALIDA')),
    cantidad         NUMERIC(12,2),
    fecha            TIMESTAMP DEFAULT NOW()
);

CREATE TABLE envios (
    envio_id             SERIAL PRIMARY KEY,
    orden_id             INT REFERENCES ordenes_compra(orden_id),
    proveedor_id         INT REFERENCES proveedores(proveedor_id),
    almacen_origen_id    INT REFERENCES almacenes(almacen_id),
    fecha_salida         TIMESTAMP,
    fecha_llegada_estim  TIMESTAMP,
    fecha_llegada_real   TIMESTAMP,
    costo_flete          NUMERIC(12,2),
    condicion_climatica  VARCHAR(80)
);

CREATE TABLE tipo_cambio (
    tipo_cambio_id  SERIAL PRIMARY KEY,
    moneda_origen   VARCHAR(10),
    moneda_destino  VARCHAR(10),
    tasa            NUMERIC(12,6),
    fecha           DATE DEFAULT CURRENT_DATE
);

-- 8.2 Esquema analitico (modelo estrella)

CREATE TABLE fact_supply_chain (
    fact_id               BIGSERIAL PRIMARY KEY,
    fecha_id              DATE NOT NULL,
    producto_id           INT,
    proveedor_id          INT,
    almacen_id            INT,
    lead_time_dias        NUMERIC(6,2),
    otif                  BOOLEAN,
    costo_total           NUMERIC(14,2),
    unidades              NUMERIC(12,2),
    unidades_solicitadas  NUMERIC(12,2),
    unidades_entregadas   NUMERIC(12,2),
    costo_flete           NUMERIC(12,2),
    variacion_costo       NUMERIC(12,2),
    nivel_riesgo          VARCHAR(20),
    score_anomalia        NUMERIC(5,4)
);

CREATE TABLE dim_tiempo (
    fecha_id   DATE PRIMARY KEY,
    anio       INT,
    mes        INT,
    dia        INT,
    trimestre  INT
);

CREATE TABLE forecast_demanda (
    forecast_id         SERIAL PRIMARY KEY,
    producto_id         INT,
    fecha_prediccion    DATE,
    demanda_estimada    NUMERIC(12,2),
    intervalo_inferior  NUMERIC(12,2),
    intervalo_superior  NUMERIC(12,2),
    mape                NUMERIC(6,4),
    fecha_generacion    TIMESTAMP DEFAULT NOW()
);

-- Indices recomendados por el PDR
CREATE INDEX idx_fact_fecha      ON fact_supply_chain (fecha_id);
CREATE INDEX idx_fact_producto   ON fact_supply_chain (producto_id);
CREATE INDEX idx_fact_proveedor  ON fact_supply_chain (proveedor_id);
CREATE INDEX idx_oc_prov_fecha   ON ordenes_compra (proveedor_id, fecha_orden);