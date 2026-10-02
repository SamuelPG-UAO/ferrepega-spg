-- =========================================================
-- Ferrepega - Esquema de analitica_db (servicio-analitica)
-- Tablas de agregados: las llena el propio servicio al recalcular
-- =========================================================

CREATE TABLE IF NOT EXISTS ventas_mensuales (
    anio          INTEGER NOT NULL,
    mes           INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    total_ventas  NUMERIC(16, 2) NOT NULL,
    num_pedidos   INTEGER NOT NULL,
    PRIMARY KEY (anio, mes)
);

CREATE TABLE IF NOT EXISTS top_productos (
    producto_id  INTEGER PRIMARY KEY,
    nombre       VARCHAR(150) NOT NULL,
    unidades     INTEGER NOT NULL,
    ingresos     NUMERIC(16, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS ventas_por_categoria (
    categoria     VARCHAR(80) PRIMARY KEY,
    total_ventas  NUMERIC(16, 2) NOT NULL,
    unidades      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ventas_por_vendedor (
    vendedor_id   INTEGER NOT NULL,
    fecha         DATE NOT NULL,
    total_ventas  NUMERIC(16, 2) NOT NULL,
    num_ventas    INTEGER NOT NULL,
    PRIMARY KEY (vendedor_id, fecha)
);

-- Bitácora de recálculos. (El servicio también la crea al arrancar si no existe,
-- para no obligar a repetir el ETL en bases creadas antes de añadirla.)
CREATE TABLE IF NOT EXISTS actualizaciones (
    id                 SERIAL PRIMARY KEY,
    fecha              TIMESTAMP NOT NULL DEFAULT now(),
    ventas_procesadas  INTEGER NOT NULL,
    segundos           NUMERIC(8, 2) NOT NULL,
    usuario_id         INTEGER NOT NULL
);
