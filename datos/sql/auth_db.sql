-- =========================================================
-- Ferrepega - Esquema de auth_db (servicio-autenticacion)
-- =========================================================

CREATE TABLE IF NOT EXISTS usuarios (
    id               SERIAL PRIMARY KEY,
    nombre           VARCHAR(100) NOT NULL,
    correo           VARCHAR(120) NOT NULL UNIQUE,
    contrasena_hash  VARCHAR(255) NOT NULL,          -- bcrypt, nunca texto plano
    rol              VARCHAR(20)  NOT NULL
                     CHECK (rol IN ('admin', 'vendedor', 'cliente')),
    activo           BOOLEAN      NOT NULL DEFAULT TRUE,
    creado_en        TIMESTAMP    NOT NULL DEFAULT NOW()
);
