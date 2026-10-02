"""
Ferrepega - ETL del dataset Olist
=================================
Toma los CSV de Olist (carpeta datos/), conserva solo las categorías de
ferretería, las traduce al contexto de Ferrepega y reparte la información
en las cuatro bases de datos, una por microservicio:

    auth_db        usuarios de demostración (con contraseña cifrada)
    inventario_db  categorías, productos, stock inicial y movimientos
    ventas_db      clientes, ventas y detalle de ventas
    analitica_db   solo se crean las tablas (las llena servicio-analitica)

Uso (dentro de la VM, con el entorno virtual activo):
    python /vagrant/datos/etl_olist.py              # primera carga
    python /vagrant/datos/etl_olist.py --reiniciar  # borra y recarga todo

Datos: Olist, "Brazilian E-Commerce Public Dataset" (Kaggle),
licencia CC BY-NC-SA 4.0. Uso académico.
"""
import argparse
import os
import random
import sys
from pathlib import Path

import bcrypt
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# ---------------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------------
DIR_DATOS = Path(os.getenv("DATOS_DIR", "/vagrant/datos"))
DIR_SQL = DIR_DATOS / "sql"

PG_HOST = os.getenv("PGHOST", "localhost")
PG_PORT = os.getenv("PGPORT", "5432")

# (base de datos, usuario, contraseña): las mismas que crea back.sh.
# Son claves de desarrollo; los microservicios las leerán de archivos .env.
BASES = {
    "auth":       ("auth_db",       "auth_user",       "Ferre_auth_2025"),
    "inventario": ("inventario_db", "inventario_user", "Ferre_inventario_2025"),
    "ventas":     ("ventas_db",     "ventas_user",     "Ferre_ventas_2025"),
    "analitica":  ("analitica_db",  "analitica_user",  "Ferre_analitica_2025"),
}

# Los precios de Olist están en reales brasileños. Los convertimos a pesos
# con una tasa de REFERENCIA (aproximada, no es una cotización oficial).
FACTOR_COP = 700

NUM_VENDEDORES = 5   # cuántos vendedores de demostración se crean
SEMILLA = 42         # para que el stock aleatorio sea siempre el mismo

# Categorías de Olist que conservamos como ferretería.
#   clave   = nombre en inglés en product_category_name_translation.csv
#             (incluye los errores de ortografía "costruction" del dataset)
#   valor   = (nombre de la categoría en Ferrepega, nombre base del producto)
CATEGORIAS = {
    "garden_tools":                    ("Herramientas de jardín",      "Herramienta de jardín"),
    "construction_tools_construction": ("Herramientas de construcción", "Herramienta de construcción"),
    "home_construction":               ("Materiales de construcción",  "Material de construcción"),
    "construction_tools_lights":       ("Iluminación y eléctricos",    "Artículo de iluminación"),
    "costruction_tools_garden":        ("Jardinería y exteriores",     "Artículo de jardinería"),
    "signaling_and_security":          ("Señalización y seguridad",    "Artículo de señalización"),
    "construction_tools_safety":       ("Seguridad industrial",        "Equipo de seguridad"),
    "costruction_tools_tools":         ("Herramientas manuales",       "Herramienta manual"),
}

# Estados de pedido de Olist que conservamos y su equivalente en Ferrepega.
# Los demás (shipped, invoiced, processing...) se descartan: son pedidos
# sin terminar y no sirven para los dashboards.
ESTADOS = {"delivered": "COMPLETADA", "canceled": "ANULADA"}

# Usuarios de demostración: (nombre, correo, contraseña, rol)
USUARIOS_DEMO = (
    [("Administrador Ferrepega", "admin@ferrepega.com", "Admin2025*", "admin")]
    + [(f"Vendedor {i}", f"vendedor{i}@ferrepega.com", "Vende2025*", "vendedor")
       for i in range(1, NUM_VENDEDORES + 1)]
    + [("Cliente Demo", "cliente@ferrepega.com", "Cliente2025*", "cliente")]
)


# ---------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------
def salir(mensaje):
    """Muestra un error y termina el programa."""
    print(f"\nERROR: {mensaje}", file=sys.stderr)
    sys.exit(1)


def nativo(valor):
    """Convierte un valor de pandas/numpy a un tipo normal de Python.
    psycopg2 no sabe guardar numpy.int64, y los NaN deben ser NULL."""
    if isinstance(valor, pd.Timestamp):
        return None if pd.isna(valor) else valor.to_pydatetime()
    if pd.isna(valor):
        return None
    if hasattr(valor, "item"):
        return valor.item()
    return valor


def filas(df, columnas):
    """Convierte columnas de un DataFrame en una lista de tuplas listas
    para insertar en PostgreSQL."""
    return [
        tuple(nativo(v) for v in fila)
        for fila in df[columnas].itertuples(index=False, name=None)
    ]


def a_cop(precios_brl):
    """Convierte reales a pesos y redondea a la centena (precios 'de tienda')."""
    return (precios_brl * FACTOR_COP / 100).round().mul(100).clip(lower=100)


# ---------------------------------------------------------------
# EXTRACCIÓN: leer los CSV
# ---------------------------------------------------------------
def leer_csv():
    def leer(nombre, **opciones):
        ruta = DIR_DATOS / nombre
        if not ruta.exists():
            salir(f"No se encontró {ruta}. ¿Descomprimiste el dataset en datos/?")
        return pd.read_csv(ruta, **opciones)

    return {
        "productos": leer("olist_products_dataset.csv"),
        "items": leer("olist_order_items_dataset.csv"),
        "ordenes": leer("olist_orders_dataset.csv",
                        parse_dates=["order_purchase_timestamp"]),
        "clientes": leer("olist_customers_dataset.csv"),
        "traduccion": leer("product_category_name_translation.csv"),
    }


# ---------------------------------------------------------------
# TRANSFORMACIÓN: catálogo de productos
# ---------------------------------------------------------------
def describir(fila):
    """Arma una descripción con los datos físicos que sí trae el dataset."""
    partes = [f"Referencia {str(fila['product_id'])[:8]}."]
    if pd.notna(fila["product_weight_g"]):
        partes.append(f"Peso: {int(fila['product_weight_g'])} g.")
    medidas = [fila["product_length_cm"], fila["product_height_cm"],
               fila["product_width_cm"]]
    if all(pd.notna(m) for m in medidas):
        partes.append("Dimensiones: {} x {} x {} cm.".format(*[int(m) for m in medidas]))
    return " ".join(partes)


def stock_inicial(rng):
    """Genera (cantidad, stock_minimo). Cerca del 12 % de los productos
    quedan por debajo del mínimo, para que la alerta de bajo stock
    tenga datos que mostrar."""
    minimo = rng.choice([5, 8, 10, 15])
    if rng.random() < 0.12:
        cantidad = rng.randint(0, minimo - 1)
    else:
        cantidad = rng.randint(minimo + 5, 150)
    return cantidad, minimo


def preparar_catalogo(d):
    # 1. Unir cada producto con el nombre en inglés de su categoría
    prod = d["productos"].merge(d["traduccion"], on="product_category_name", how="inner")
    prod = prod.rename(columns={"product_category_name_english": "categoria_en"})

    # 2. Quedarnos solo con las categorías de ferretería
    prod = prod[prod["categoria_en"].isin(CATEGORIAS)].copy()

    # 3. El dataset no trae precio por producto: usamos el promedio de
    #    lo que se pagó por él en los pedidos, convertido a pesos.
    precio_medio = d["items"].groupby("product_id")["price"].mean()
    prod["precio"] = a_cop(prod["product_id"].map(precio_medio))
    prod = prod.dropna(subset=["precio"])

    # 4. El dataset tampoco trae nombres: los generamos por categoría.
    prod = prod.sort_values(["categoria_en", "product_id"]).reset_index(drop=True)
    prod["num"] = prod.groupby("categoria_en").cumcount() + 1
    prod["categoria_es"] = prod["categoria_en"].map(lambda c: CATEGORIAS[c][0])
    prod["nombre"] = [
        f"{CATEGORIAS[c][1]} {n:04d}"
        for c, n in zip(prod["categoria_en"], prod["num"])
    ]
    prod["descripcion"] = [describir(f) for f in prod.to_dict("records")]

    # 5. Stock inicial inventado (el dataset no tiene inventario)
    rng = random.Random(SEMILLA)
    stocks = [stock_inicial(rng) for _ in range(len(prod))]
    prod["stock"] = [s[0] for s in stocks]
    prod["stock_minimo"] = [s[1] for s in stocks]
    return prod


# ---------------------------------------------------------------
# TRANSFORMACIÓN: ventas, detalle y clientes
# ---------------------------------------------------------------
def preparar_ventas(d, catalogo):
    # Solo ítems de productos de ferretería, de pedidos entregados o cancelados
    items = d["items"][d["items"]["product_id"].isin(catalogo["product_id"])]
    ordenes = d["ordenes"][d["ordenes"]["order_status"].isin(ESTADOS)][
        ["order_id", "customer_id", "order_status", "order_purchase_timestamp"]
    ]
    items = items.merge(ordenes, on="order_id", how="inner")
    items = items.merge(
        d["clientes"][["customer_id", "customer_unique_id", "customer_city"]],
        on="customer_id", how="left",
    )
    items = items.assign(precio_cop=a_cop(items["price"]))

    # Detalle: en Olist cada fila es 1 unidad; agrupamos por pedido y producto
    detalle = items.groupby(["order_id", "product_id"], as_index=False).agg(
        cantidad=("order_item_id", "size"),
        subtotal=("precio_cop", "sum"),
    )
    detalle["precio_unitario"] = (detalle["subtotal"] / detalle["cantidad"]).round(2)

    # Ventas: una fila por pedido
    ventas = items.groupby("order_id", as_index=False).agg(
        customer_unique_id=("customer_unique_id", "first"),
        ciudad=("customer_city", "first"),
        fecha=("order_purchase_timestamp", "first"),
        estado_olist=("order_status", "first"),
        seller_id=("seller_id", "min"),
    )
    ventas["estado"] = ventas["estado_olist"].map(ESTADOS)
    ventas["total"] = ventas["order_id"].map(detalle.groupby("order_id")["subtotal"].sum())

    # Los miles de vendedores de Olist se reparten entre los 5 de demostración
    vendedores = sorted(ventas["seller_id"].unique())
    reparto = {s: i % NUM_VENDEDORES for i, s in enumerate(vendedores)}
    ventas["vendedor_idx"] = ventas["seller_id"].map(reparto)

    # Clientes: uno por persona real (customer_unique_id), con datos anónimos
    clientes = (
        ventas[["customer_unique_id", "ciudad"]]
        .drop_duplicates("customer_unique_id")
        .sort_values("customer_unique_id")
        .reset_index(drop=True)
    )
    clientes["nombre"] = [f"Cliente {i + 1:05d}" for i in range(len(clientes))]
    clientes["correo"] = [f"cliente{i + 1:05d}@ejemplo.com" for i in range(len(clientes))]
    clientes["ciudad"] = clientes["ciudad"].fillna("").str.title()

    return ventas, detalle, clientes


# ---------------------------------------------------------------
# CARGA: base de datos
# ---------------------------------------------------------------
def conectar(clave):
    bd, usuario, contrasena = BASES[clave]
    try:
        # client_encoding UTF8: los nombres llevan tildes (jardín, señalización)
        # y no queremos depender de la configuración regional de la máquina.
        conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=bd,
                                user=usuario, password=contrasena,
                                client_encoding="UTF8", connect_timeout=10)
    except psycopg2.OperationalError as e:
        salir(f"No se pudo conectar a {bd} como {usuario}: {e}")

    # La base de datos también debe guardar en UTF-8; si no, las tildes
    # se almacenarían mal.
    cur = conn.cursor()
    cur.execute("SHOW server_encoding")
    codificacion = cur.fetchone()[0]
    if codificacion.upper() != "UTF8":
        conn.close()
        salir(f"{bd} usa la codificación {codificacion} y se necesita UTF8. "
              "Borra y recrea las bases (ver instrucciones del paso 3).")
    return conn


def preparar_esquema(conn, bd, tablas, reiniciar, revisar_datos=True):
    """Crea las tablas (si faltan) y revisa que no haya datos de una carga
    anterior. Con --reiniciar vacía las tablas en lugar de abortar."""
    cur = conn.cursor()
    cur.execute((DIR_SQL / f"{bd}.sql").read_text(encoding="utf-8"))

    if revisar_datos and not reiniciar:
        cur.execute(f"SELECT COUNT(*) FROM {tablas[0]}")
        if cur.fetchone()[0] > 0:
            salir(f"{bd} ya tiene datos. Si quieres borrarlos y recargar, "
                  "ejecuta el script con --reiniciar.")
    if reiniciar:
        cur.execute("TRUNCATE TABLE " + ", ".join(tablas) + " RESTART IDENTITY CASCADE")


def cargar_auth(conn):
    cur = conn.cursor()
    datos = []
    for nombre, correo, contrasena, rol in USUARIOS_DEMO:
        cifrada = bcrypt.hashpw(contrasena.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        datos.append((nombre, correo, cifrada, rol))
    res = execute_values(
        cur,
        "INSERT INTO usuarios (nombre, correo, contrasena_hash, rol) "
        "VALUES %s RETURNING id, correo",
        datos, fetch=True,
    )
    ids = {correo: id_ for id_, correo in res}
    admin_id = ids["admin@ferrepega.com"]
    vendedores = [ids[f"vendedor{i}@ferrepega.com"] for i in range(1, NUM_VENDEDORES + 1)]
    return admin_id, vendedores


def cargar_inventario(conn, catalogo, admin_id):
    cur = conn.cursor()

    # Categorías
    res = execute_values(
        cur,
        "INSERT INTO categorias (nombre, nombre_original) VALUES %s RETURNING id, nombre_original",
        [(nombre_es, en) for en, (nombre_es, _) in CATEGORIAS.items()],
        fetch=True,
    )
    id_cat = {en: id_ for id_, en in res}
    catalogo["categoria_id"] = catalogo["categoria_en"].map(id_cat)

    # Productos (RETURNING nos da los ids que generó PostgreSQL)
    res = execute_values(
        cur,
        "INSERT INTO productos (codigo_origen, nombre, descripcion, categoria_id, precio) "
        "VALUES %s RETURNING id, codigo_origen",
        filas(catalogo, ["product_id", "nombre", "descripcion", "categoria_id", "precio"]),
        page_size=500, fetch=True,
    )
    id_prod = {cod: id_ for id_, cod in res}
    catalogo["producto_id"] = catalogo["product_id"].map(id_prod)

    # Stock
    execute_values(
        cur,
        "INSERT INTO stock (producto_id, cantidad, stock_minimo) VALUES %s",
        filas(catalogo, ["producto_id", "stock", "stock_minimo"]),
        page_size=500,
    )

    # Un movimiento de ENTRADA por el inventario inicial
    con_stock = catalogo[catalogo["stock"] > 0]
    movimientos = [
        (pid, "ENTRADA", cant, "Inventario inicial (carga ETL)", admin_id)
        for pid, cant in zip(con_stock["producto_id"].tolist(), con_stock["stock"].tolist())
    ]
    execute_values(
        cur,
        "INSERT INTO movimientos (producto_id, tipo, cantidad, motivo, usuario_id) VALUES %s",
        movimientos, page_size=500,
    )


def cargar_ventas(conn, ventas, detalle, clientes, catalogo, ids_vendedores):
    cur = conn.cursor()

    # Clientes
    res = execute_values(
        cur,
        "INSERT INTO clientes (codigo_origen, nombre, correo, ciudad) "
        "VALUES %s RETURNING id, codigo_origen",
        filas(clientes, ["customer_unique_id", "nombre", "correo", "ciudad"]),
        page_size=1000, fetch=True,
    )
    id_cli = {cod: id_ for id_, cod in res}
    ventas["cliente_id"] = ventas["customer_unique_id"].map(id_cli)
    ventas["vendedor_id"] = ventas["vendedor_idx"].map(lambda i: ids_vendedores[i])

    # Ventas
    res = execute_values(
        cur,
        "INSERT INTO ventas (codigo_origen, cliente_id, vendedor_id, fecha, total, estado) "
        "VALUES %s RETURNING id, codigo_origen",
        filas(ventas, ["order_id", "cliente_id", "vendedor_id", "fecha", "total", "estado"]),
        page_size=1000, fetch=True,
    )
    id_venta = {cod: id_ for id_, cod in res}

    # Detalle: guarda una copia del nombre y la categoría del producto
    info = catalogo.set_index("product_id")
    detalle["venta_id"] = detalle["order_id"].map(id_venta)
    detalle["producto_id"] = detalle["product_id"].map(info["producto_id"])
    detalle["nombre_producto"] = detalle["product_id"].map(info["nombre"])
    detalle["categoria"] = detalle["product_id"].map(info["categoria_es"])
    execute_values(
        cur,
        "INSERT INTO detalle_venta (venta_id, producto_id, nombre_producto, categoria, "
        "cantidad, precio_unitario, subtotal) VALUES %s",
        filas(detalle, ["venta_id", "producto_id", "nombre_producto", "categoria",
                        "cantidad", "precio_unitario", "subtotal"]),
        page_size=1000,
    )


def contar(conn, tabla):
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {tabla}")
    return cur.fetchone()[0]


# ---------------------------------------------------------------
# PROGRAMA PRINCIPAL
# ---------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="ETL del dataset Olist hacia Ferrepega")
    ap.add_argument("--reiniciar", action="store_true",
                    help="borra los datos existentes y vuelve a cargar todo")
    args = ap.parse_args()

    print("[1/5] Leyendo los CSV de Olist...")
    d = leer_csv()

    print("[2/5] Transformando: filtrando categorías y armando catálogo y ventas...")
    catalogo = preparar_catalogo(d)
    ventas, detalle, clientes = preparar_ventas(d, catalogo)
    print(f"      {len(catalogo)} productos, {len(ventas)} ventas, "
          f"{len(detalle)} líneas de detalle, {len(clientes)} clientes")

    print("[3/5] Conectando a las 4 bases de datos...")
    conns = {clave: conectar(clave) for clave in BASES}
    terminado = False
    try:
        print("[4/5] Preparando esquemas y cargando datos...")
        preparar_esquema(conns["auth"], "auth_db", ["usuarios"], args.reiniciar)
        preparar_esquema(conns["inventario"], "inventario_db",
                         ["movimientos", "stock", "productos", "categorias"], args.reiniciar)
        preparar_esquema(conns["ventas"], "ventas_db",
                         ["detalle_venta", "ventas", "clientes"], args.reiniciar)
        preparar_esquema(conns["analitica"], "analitica_db",
                         ["ventas_mensuales", "top_productos", "ventas_por_categoria",
                          "ventas_por_vendedor", "actualizaciones"], args.reiniciar,
                         revisar_datos=False)

        admin_id, ids_vendedores = cargar_auth(conns["auth"])
        cargar_inventario(conns["inventario"], catalogo, admin_id)
        cargar_ventas(conns["ventas"], ventas, detalle, clientes, catalogo, ids_vendedores)

        for conn in conns.values():
            conn.commit()
        terminado = True

        print("[5/5] Carga terminada. Filas por tabla:")
        for clave, tabla in [("auth", "usuarios"), ("inventario", "categorias"),
                             ("inventario", "productos"), ("inventario", "stock"),
                             ("inventario", "movimientos"), ("ventas", "clientes"),
                             ("ventas", "ventas"), ("ventas", "detalle_venta")]:
            print(f"      {tabla:<15} {contar(conns[clave], tabla):>7}")
    finally:
        for conn in conns.values():
            if not terminado:
                conn.rollback()
            conn.close()

    print("\nUsuarios de demostración (cámbialos antes del despliegue final):")
    for nombre, correo, contrasena, rol in USUARIOS_DEMO:
        if correo.startswith("vendedor") and not correo.startswith("vendedor1@"):
            continue
        print(f"      {rol:<9} {correo:<26} {contrasena}")
    print(f"      (hay {NUM_VENDEDORES} vendedores: vendedor1 ... vendedor{NUM_VENDEDORES}, misma clave)")


if __name__ == "__main__":
    main()
