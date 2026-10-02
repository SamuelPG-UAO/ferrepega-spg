"""
Ferrepega - Exploración del dataset Olist

Lee los CSV de la carpeta datos/ y muestra:
  1. Cuántas filas tiene cada tabla.
  2. Cuántos productos, unidades vendidas e ingresos tiene cada categoría.
  3. Cuáles categorías parecen de ferretería (marcadas con *).
  4. Estados de los pedidos y rango de fechas.

Uso (dentro de la VM):
    python /vagrant/datos/explorar.py
"""
import sys

import pandas as pd

# Carpeta con los CSV. Se puede pasar otra ruta como primer argumento.
RUTA = sys.argv[1] if len(sys.argv) > 1 else "/vagrant/datos/"
if not RUTA.endswith("/"):
    RUTA += "/"

# Palabras que delatan una categoría de ferretería.
# Ojo: el dataset original escribe mal "costruction" en dos categorías.
PALABRAS = ("construction", "costruction", "tools", "garden", "signaling")

# ---------------------------------------------------------------
# Carga de los archivos
# ---------------------------------------------------------------
productos = pd.read_csv(RUTA + "olist_products_dataset.csv")
items = pd.read_csv(RUTA + "olist_order_items_dataset.csv")
ordenes = pd.read_csv(
    RUTA + "olist_orders_dataset.csv",
    parse_dates=["order_purchase_timestamp"],
)
clientes = pd.read_csv(RUTA + "olist_customers_dataset.csv")
vendedores = pd.read_csv(RUTA + "olist_sellers_dataset.csv")
traduccion = pd.read_csv(RUTA + "product_category_name_translation.csv")

# ---------------------------------------------------------------
# 1. Tamaño de cada tabla
# ---------------------------------------------------------------
print("=== 1. Filas por tabla ===")
for nombre, tabla in [
    ("productos", productos),
    ("items de pedido", items),
    ("pedidos", ordenes),
    ("clientes", clientes),
    ("vendedores", vendedores),
    ("traducciones", traduccion),
]:
    print(f"{nombre:<18} {len(tabla):>8}")

# ---------------------------------------------------------------
# 2. Resumen por categoría
# ---------------------------------------------------------------
# Hay productos sin categoría: les ponemos una etiqueta para no perderlos.
productos["product_category_name"] = productos["product_category_name"].fillna(
    "sin_categoria"
)

# Cada ítem de pedido recibe la categoría de su producto.
items_cat = items.merge(
    productos[["product_id", "product_category_name"]],
    on="product_id",
    how="left",
)

resumen = (
    items_cat.groupby("product_category_name")
    .agg(
        productos=("product_id", "nunique"),
        unidades=("order_item_id", "size"),
        ingresos=("price", "sum"),
    )
    .reset_index()
)

# Agregamos el nombre en inglés. Si no hay traducción, dejamos el original.
resumen = resumen.merge(traduccion, on="product_category_name", how="left")
resumen["product_category_name_english"] = resumen[
    "product_category_name_english"
].fillna(resumen["product_category_name"])

resumen["ingresos"] = resumen["ingresos"].round(0).astype(int)
resumen = resumen.sort_values("unidades", ascending=False)

# Marca de candidata a ferretería
nombre_en = resumen["product_category_name_english"].str.lower()
resumen["candidata"] = nombre_en.apply(
    lambda n: "*" if any(p in n for p in PALABRAS) else ""
)

print("\n=== 2. Todas las categorías (ordenadas por unidades vendidas) ===")
print(
    resumen[
        [
            "candidata",
            "product_category_name_english",
            "product_category_name",
            "productos",
            "unidades",
            "ingresos",
        ]
    ].to_string(index=False)
)

# ---------------------------------------------------------------
# 3. Total de las categorías candidatas
# ---------------------------------------------------------------
cand = resumen[resumen["candidata"] == "*"]
print("\n=== 3. Categorías candidatas (*) ===")
print(f"Categorías : {len(cand)}")
print(f"Productos  : {cand['productos'].sum()}")
print(f"Unidades   : {cand['unidades'].sum()}")
print(f"Ingresos   : {cand['ingresos'].sum()}")

# ---------------------------------------------------------------
# 4. Pedidos
# ---------------------------------------------------------------
print("\n=== 4. Estados de los pedidos ===")
print(ordenes["order_status"].value_counts().to_string())
print(
    "\nPrimer pedido:", ordenes["order_purchase_timestamp"].min(),
    "\nÚltimo pedido:", ordenes["order_purchase_timestamp"].max(),
)
