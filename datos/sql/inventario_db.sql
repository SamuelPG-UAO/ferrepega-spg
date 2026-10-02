-- =========================================================
-- Ferrepega - Esquema de inventario_db (servicio-inventario)
-- Catálogo (categorías y productos) + stock + movimientos
-- =========================================================

CREATE TABLE IF NOT EXISTS categorias (
    id               SERIAL PRIMARY KEY,
    nombre           VARCHAR(80) NOT NULL UNIQUE,    -- nombre en español
    nombre_original  VARCHAR(100)                    -- nombre en el dataset (inglés)
);

CREATE TABLE IF NOT EXISTS productos (
    id             SERIAL PRIMARY KEY,
    codigo_origen  VARCHAR(40) UNIQUE,               -- product_id de Olist
    nombre         VARCHAR(150) NOT NULL,
    descripcion    TEXT,
    categoria_id   INTEGER NOT NULL REFERENCES categorias(id),
    precio         NUMERIC(12, 2) NOT NULL CHECK (precio >= 0),   -- en pesos
    activo         BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_productos_categoria ON productos(categoria_id);

CREATE TABLE IF NOT EXISTS stock (
    producto_id   INTEGER PRIMARY KEY REFERENCES productos(id) ON DELETE CASCADE,
    cantidad      INTEGER NOT NULL DEFAULT 0 CHECK (cantidad >= 0),
    stock_minimo  INTEGER NOT NULL DEFAULT 5 CHECK (stock_minimo >= 0)
);

CREATE TABLE IF NOT EXISTS movimientos (
    id           SERIAL PRIMARY KEY,
    producto_id  INTEGER NOT NULL REFERENCES productos(id),
    tipo         VARCHAR(10) NOT NULL CHECK (tipo IN ('ENTRADA', 'SALIDA', 'AJUSTE')),
    cantidad     INTEGER NOT NULL CHECK (cantidad <> 0),
    motivo       VARCHAR(200),
    venta_id     INTEGER,        -- id en ventas_db (sin llave foránea entre bases)
    usuario_id   INTEGER,        -- id en auth_db (sin llave foránea entre bases)
    fecha        TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_movimientos_producto ON movimientos(producto_id);
