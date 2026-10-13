-- =============================================================================
-- 06_usuarios.sql
-- Usuarios, contrasenas con hash y roles del dashboard.
-- CC-20 (control de cambios, riesgo R6): adicion de la tabla usuarios para el
-- Modulo 8 (Administracion) y la mitigacion del riesgo R7 del PDR.
--
-- Reglas:
--   - La contrasena nunca se guarda: solo su hash PBKDF2-HMAC-SHA256 con sal
--     aleatoria, en formato pbkdf2_sha256$iteraciones$sal$hash (base64).
--   - Roles: EJECUTIVO decide sobre recomendaciones, OPERACIONES ejecuta los
--     pasos del plan, ADMIN administra usuarios.
--   - Bloqueo temporal tras intentos fallidos (lo aplica backend/app/auth_api.py).
--   - Texto solo en ASCII (CC-11).
--
-- Aditivo, idempotente y transaccional. Base: supply_chain_final.
-- Ejecutar desde la raiz del proyecto:
--   psql -U postgres -d supply_chain_final -v ON_ERROR_STOP=1 -f db/final/06_usuarios.sql
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS usuarios (
    usuario_id          SERIAL       PRIMARY KEY,
    usuario             VARCHAR(60)  NOT NULL UNIQUE,
    nombre              VARCHAR(120) NOT NULL,
    rol                 VARCHAR(20)  NOT NULL,
    hash_contrasena     VARCHAR(200) NOT NULL,
    activo              BOOLEAN      NOT NULL DEFAULT TRUE,
    intentos_fallidos   INT          NOT NULL DEFAULT 0,
    bloqueado_hasta     TIMESTAMP,
    ultimo_acceso       TIMESTAMP,
    fecha_registro      TIMESTAMP    NOT NULL DEFAULT LOCALTIMESTAMP(0),
    CONSTRAINT usuarios_usuario_formato   CHECK (usuario ~ '^[a-z0-9._-]{3,60}$'),
    CONSTRAINT usuarios_nombre_ascii      CHECK (nombre ~ '^[ -~]+$'),
    CONSTRAINT usuarios_rol_valido        CHECK (rol IN ('EJECUTIVO', 'OPERACIONES', 'ADMIN')),
    CONSTRAINT usuarios_hash_formato      CHECK (left(hash_contrasena, 14) = 'pbkdf2_sha256$'),
    CONSTRAINT usuarios_intentos_validos  CHECK (intentos_fallidos >= 0)
);

COMMENT ON TABLE usuarios IS
    'Usuarios del dashboard: hash PBKDF2-HMAC-SHA256, rol y bloqueo por intentos fallidos (CC-20, riesgo R7)';
COMMENT ON COLUMN usuarios.hash_contrasena IS
    'pbkdf2_sha256$iteraciones$sal$hash en base64; la contrasena nunca se guarda';
COMMENT ON COLUMN usuarios.rol IS
    'EJECUTIVO decide recomendaciones, OPERACIONES marca pasos del plan, ADMIN administra usuarios';
COMMENT ON COLUMN usuarios.bloqueado_hasta IS
    'Fin del bloqueo temporal tras intentos fallidos consecutivos';

COMMIT;