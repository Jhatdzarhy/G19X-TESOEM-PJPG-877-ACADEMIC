-- ============================================================
-- 05_asistente.sql
-- Historial del asistente de IA (CC-17, control de cambios, riesgo R6).
-- Tablas: asistente_conversaciones y asistente_mensajes, ligadas al usuario.
-- Aditivo, idempotente y transaccional; no modifica tablas del PDR.
-- Textos en ASCII (CC-11): el backend normaliza antes de insertar.
-- Ejecutar:
--   psql -U postgres -f db/final/05_asistente.sql
-- ============================================================
\set ON_ERROR_STOP on
\connect supply_chain_final
SET client_encoding = 'UTF8';
SET client_min_messages = warning;

BEGIN;

CREATE TABLE IF NOT EXISTS asistente_conversaciones (
    conversacion_id  SERIAL PRIMARY KEY,
    usuario          VARCHAR(60)  NOT NULL,
    titulo           VARCHAR(120) NOT NULL,
    fecha_creacion   TIMESTAMP    NOT NULL DEFAULT NOW(),
    fecha_actualizacion TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS asistente_mensajes (
    mensaje_id       SERIAL PRIMARY KEY,
    conversacion_id  INT          NOT NULL
        REFERENCES asistente_conversaciones(conversacion_id) ON DELETE CASCADE,
    rol              VARCHAR(10)  NOT NULL
        CONSTRAINT ck_asistente_rol CHECK (rol IN ('USUARIO', 'ASISTENTE')),
    contenido        TEXT         NOT NULL,
    modelo           VARCHAR(60),
    herramientas     JSONB
        CONSTRAINT ck_asistente_herramientas CHECK (herramientas IS NULL OR jsonb_typeof(herramientas) = 'array'),
    fecha_corte      DATE,
    fecha            TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_asis_conv_usuario ON asistente_conversaciones (usuario, fecha_actualizacion DESC);
CREATE INDEX IF NOT EXISTS idx_asis_msj_conv     ON asistente_mensajes (conversacion_id, mensaje_id);

COMMENT ON TABLE asistente_conversaciones IS 'CC-17: conversaciones del asistente de IA por usuario';
COMMENT ON TABLE asistente_mensajes IS
    'CC-17: mensajes del asistente; modelo que respondio, herramientas consultadas y fecha de corte de los datos';

COMMIT;

-- Verificacion
SELECT table_name, COUNT(*) AS columnas
FROM information_schema.columns
WHERE table_name IN ('asistente_conversaciones', 'asistente_mensajes')
GROUP BY table_name ORDER BY table_name;