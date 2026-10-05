-- ============================================================
-- Proyecto final: tablas del Centro de soluciones
-- Cambio aprobado por el lider de proyecto (control de cambios, riesgo R6)
-- Requiere haber ejecutado antes 01_esquema_pdr.sql
-- La IA solo recomienda: no ejecuta compras (alcance del PDR, seccion 2)
-- ============================================================
\set ON_ERROR_STOP on
\connect supply_chain_final
SET client_encoding = 'UTF8';

DROP TABLE IF EXISTS plan_acciones, recomendaciones CASCADE;

CREATE TABLE recomendaciones (
    recomendacion_id      SERIAL PRIMARY KEY,
    codigo_regla          VARCHAR(40) NOT NULL,
    modulo                VARCHAR(20) NOT NULL
                          CHECK (modulo IN ('COMPRAS','INVENTARIOS','LOGISTICA','ALMACENES','PROVEEDORES','TIPO_CAMBIO')),
    severidad             VARCHAR(10) NOT NULL
                          CHECK (severidad IN ('CRITICO','ATENCION','INFO')),
    titulo                VARCHAR(200) NOT NULL,
    descripcion           TEXT,
    solucion_recomendada  TEXT NOT NULL,
    impacto_estimado_mxn  NUMERIC(14,2),
    confianza             NUMERIC(4,3) CHECK (confianza BETWEEN 0 AND 1),
    evidencia             JSONB,
    producto_id           INT REFERENCES productos(producto_id),
    proveedor_id          INT REFERENCES proveedores(proveedor_id),
    almacen_id            INT REFERENCES almacenes(almacen_id),
    envio_id              INT REFERENCES envios(envio_id),
    estado                VARCHAR(12) NOT NULL DEFAULT 'NUEVA'
                          CHECK (estado IN ('NUEVA','EN_REVISION','ATENDIDA')),
    fecha_deteccion       TIMESTAMP NOT NULL DEFAULT NOW(),
    fecha_cierre          TIMESTAMP
);

CREATE TABLE plan_acciones (
    accion_id         SERIAL PRIMARY KEY,
    recomendacion_id  INT NOT NULL REFERENCES recomendaciones(recomendacion_id) ON DELETE CASCADE,
    orden_paso        SMALLINT NOT NULL,
    descripcion       VARCHAR(300) NOT NULL,
    responsable       VARCHAR(100),
    fecha_compromiso  DATE,
    estado            VARCHAR(10) NOT NULL DEFAULT 'PENDIENTE'
                      CHECK (estado IN ('PENDIENTE','HECHA')),
    fecha_cierre      TIMESTAMP,
    UNIQUE (recomendacion_id, orden_paso)
);

CREATE INDEX idx_reco_estado_sev ON recomendaciones (estado, severidad);
CREATE INDEX idx_reco_fecha      ON recomendaciones (fecha_deteccion);
CREATE INDEX idx_plan_reco       ON plan_acciones (recomendacion_id);