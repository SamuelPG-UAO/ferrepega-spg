-- =========================================================
-- Ferrepega - Esquema de ventas_db (servicio-ventas)
-- =========================================================

CREATE TABLE IF NOT EXISTS clientes (
    id             SERIAL PRIMARY KEY,
    codigo_origen  VARCHAR(40) UNIQUE,               -- customer_unique_id de Olist
    nombre         VARCHAR(100) NOT NULL,
    correo         VARCHAR(120),
    ciudad         VARCHAR(80)
);

CREATE TABLE IF NOT EXISTS ventas (
    id             SERIAL PRIMARY KEY,
    codigo_origen  VARCHAR(40) UNIQUE,               -- order_id de Olist (nulo en ventas nuevas)
    cliente_id     INTEGER REFERENCES clientes(id),
    vendedor_id    INTEGER NOT NULL,                 -- id en auth_db (sin llave foránea)
    fecha          TIMESTAMP NOT NULL,
    total          NUMERIC(14, 2) NOT NULL DEFAULT 0,
    estado         VARCHAR(12) NOT NULL DEFAULT 'COMPLETADA'
                   CHECK (estado IN ('COMPLETADA', 'ANULADA'))
);
CREATE INDEX IF NOT EXISTS idx_ventas_fecha    ON ventas(fecha);
CREATE INDEX IF NOT EXISTS idx_ventas_vendedor ON ventas(vendedor_id);

CREATE TABLE IF NOT EXISTS detalle_venta (
    id               SERIAL PRIMARY KEY,
    venta_id         INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
    producto_id      INTEGER NOT NULL,               -- id en inventario_db (sin llave foránea)
    nombre_producto  VARCHAR(150) NOT NULL,          -- copia, para no depender del catálogo
    categoria        VARCHAR(80) NOT NULL,           -- copia, para los dashboards
    cantidad         INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario  NUMERIC(12, 2) NOT NULL,
    subtotal         NUMERIC(14, 2) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_detalle_venta ON detalle_venta(venta_id);
