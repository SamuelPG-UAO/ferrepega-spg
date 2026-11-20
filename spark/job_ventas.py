"""
Ferrepega - Trabajo Spark: recalcula los resúmenes de analítica EN PARALELO.

Qué hace (es lo mismo que POST /api/analitica/actualizar, pero repartido):
  1. Inicia sesión como administrador y lee TODAS las ventas completadas desde
     el API (/api/ventas/exportacion), igual que servicio-analitica. No se toca
     ventas_db directamente: cada servicio sigue siendo dueño de sus datos.
  2. Las convierte en DataFrames de Spark y las reparte en particiones; cada
     ejecutor (worker) suma las suyas y Spark junta los resultados parciales
     (map -> shuffle -> reduce, el mismo esquema de MapReduce).
  3. Calcula los 4 resúmenes: ventas por mes, productos, categorías y vendedores.
  4. Reemplaza las tablas de analitica_db en UNA transacción (con el mismo
     candado de PostgreSQL que usa el servicio), así los dashboards muestran
     los datos calculados por Spark.

Uso (lo lanza spark_actualizar.sh dentro del contenedor spark-master):
    spark-submit --master spark://spark-master:7077 /app/job_ventas.py [--verificar]

Variables de entorno:
    FERREPEGA_API_URL   gateway (por defecto http://edge)
    ADMIN_CORREO / ADMIN_CLAVE   credenciales del administrador (obligatorias)
    PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD   analitica_db
    SPARK_MASTER        por defecto el del spark-submit; local[*] para probar sin clúster
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal

import psycopg2
import requests
from psycopg2.extras import execute_values
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (DateType, DecimalType, IntegerType, LongType,
                               StringType, StructField, StructType, TimestampType)

API = os.getenv("FERREPEGA_API_URL", "http://edge").rstrip("/")
CLAVE_BLOQUEO = 7001  # el mismo número que usa servicio-analitica
TAMANO_PAGINA = 500
DINERO = DecimalType(18, 2)


def dinero(valor) -> Decimal:
    """float -> Decimal con centavos (igual que servicio-analitica/calculo.py)."""
    return Decimal(str(valor)).quantize(Decimal("0.01"))


# ---------------------------------------------------------------------
# 1. Leer las ventas desde el API
# ---------------------------------------------------------------------
def iniciar_sesion():
    correo, clave = os.getenv("ADMIN_CORREO"), os.getenv("ADMIN_CLAVE")
    if not correo or not clave:
        sys.exit("Faltan ADMIN_CORREO y ADMIN_CLAVE (el API exige ser administrador).")
    r = requests.post(f"{API}/api/auth/login", json={"correo": correo, "contrasena": clave}, timeout=15)
    if r.status_code != 200:
        sys.exit(f"No se pudo iniciar sesión ({r.status_code}): {r.text[:200]}")
    datos = r.json()
    return datos["access_token"], datos["usuario"]["id"]


def leer_ventas(token):
    """Devuelve la lista de ventas (diccionarios) leyendo páginas de 500."""
    ventas, despues_de = [], 0
    with requests.Session() as s:
        s.headers["Authorization"] = f"Bearer {token}"
        while True:
            r = s.get(f"{API}/api/ventas/exportacion",
                      params={"despues_de": despues_de, "limite": TAMANO_PAGINA}, timeout=60)
            if r.status_code != 200:
                sys.exit(f"El API de ventas respondió {r.status_code}: {r.text[:200]}")
            pagina = r.json()
            ventas.extend(pagina["items"])
            despues_de = pagina["siguiente"]
            if despues_de is None:
                return ventas


# ---------------------------------------------------------------------
# 2-3. Spark: repartir y sumar
# ---------------------------------------------------------------------
ESQUEMA_VENTAS = StructType([
    StructField("venta_id", LongType(), False), StructField("fecha", TimestampType(), False),
    StructField("vendedor_id", IntegerType(), False), StructField("total", DINERO, False)])
ESQUEMA_ITEMS = StructType([
    StructField("venta_id", LongType(), False), StructField("producto_id", IntegerType(), False),
    StructField("nombre", StringType(), False), StructField("categoria", StringType(), False),
    StructField("cantidad", IntegerType(), False), StructField("subtotal", DINERO, False)])


def calcular_con_spark(spark, ventas, particiones):
    # La fecha del API es "ingenua" (sin zona). Se marca como UTC y Spark trabaja en UTC,
    # así el mes y el día calculados no dependen de la zona horaria de la máquina.
    filas_ventas = [(v["id"], datetime.fromisoformat(v["fecha"]).replace(tzinfo=timezone.utc),
                     v["vendedor_id"], dinero(v["total"]))
                    for v in ventas]
    filas_items = [(v["id"], it["producto_id"], it["nombre_producto"], it["categoria"],
                    it["cantidad"], dinero(it["subtotal"])) for v in ventas for it in v["items"]]

    # repartition: reparte las filas entre las particiones (cada una la procesa un ejecutor)
    df_ventas = spark.createDataFrame(filas_ventas, ESQUEMA_VENTAS).repartition(particiones)
    df_items = spark.createDataFrame(filas_items, ESQUEMA_ITEMS).repartition(particiones)

    mensual = (df_ventas.groupBy(F.year("fecha").alias("anio"), F.month("fecha").alias("mes"))
               .agg(F.sum("total").alias("total_ventas"), F.count("*").alias("num_pedidos"))
               .orderBy("anio", "mes"))
    productos = (df_items.groupBy("producto_id")
                 .agg(F.max("nombre").alias("nombre"), F.sum("cantidad").alias("unidades"),
                      F.sum("subtotal").alias("ingresos")).orderBy("producto_id"))
    categorias = (df_items.groupBy("categoria")
                  .agg(F.sum("subtotal").alias("total_ventas"), F.sum("cantidad").alias("unidades"))
                  .orderBy("categoria"))
    vendedores = (df_ventas.groupBy("vendedor_id", F.to_date("fecha").alias("fecha"))
                  .agg(F.sum("total").alias("total_ventas"), F.count("*").alias("num_ventas"))
                  .orderBy("vendedor_id", "fecha"))

    # collect() dispara el cálculo distribuido; los resultados ya son pequeños
    return {
        "ventas_procesadas": len(filas_ventas),
        "mensuales": [dict(anio=r.anio, mes=r.mes, total_ventas=r.total_ventas, num_pedidos=r.num_pedidos)
                      for r in mensual.collect()],
        "productos": [dict(producto_id=r.producto_id, nombre=r.nombre, unidades=int(r.unidades),
                           ingresos=r.ingresos) for r in productos.collect()],
        "categorias": [dict(categoria=r.categoria, total_ventas=r.total_ventas, unidades=int(r.unidades))
                       for r in categorias.collect()],
        "vendedores": [dict(vendedor_id=r.vendedor_id, fecha=r.fecha, total_ventas=r.total_ventas,
                            num_ventas=r.num_ventas) for r in vendedores.collect()],
    }


# ---------------------------------------------------------------------
# 4. Guardar en analitica_db
# ---------------------------------------------------------------------
def guardar(resultado, segundos, usuario_id):
    conn = psycopg2.connect(
        host=os.getenv("PGHOST", "db"), port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "analitica_db"), user=os.getenv("PGUSER", "analitica_user"),
        password=os.getenv("PGPASSWORD", "Ferre_analitica_2025"), client_encoding="UTF8")
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_xact_lock(%s)", (CLAVE_BLOQUEO,))
            if not cur.fetchone()[0]:
                sys.exit("Ya hay un recálculo en curso; intenta de nuevo en un momento.")
            # La bitácora la crea servicio-analitica al arrancar; por si acaso:
            cur.execute("""CREATE TABLE IF NOT EXISTS actualizaciones (
                id SERIAL PRIMARY KEY, fecha TIMESTAMP NOT NULL DEFAULT now(),
                ventas_procesadas INTEGER NOT NULL, segundos NUMERIC(8,2) NOT NULL,
                usuario_id INTEGER NOT NULL)""")
            cur.execute("DELETE FROM ventas_mensuales")
            cur.execute("DELETE FROM top_productos")
            cur.execute("DELETE FROM ventas_por_categoria")
            cur.execute("DELETE FROM ventas_por_vendedor")
            execute_values(cur, "INSERT INTO ventas_mensuales(anio, mes, total_ventas, num_pedidos) VALUES %s",
                           [(r["anio"], r["mes"], r["total_ventas"], r["num_pedidos"]) for r in resultado["mensuales"]])
            execute_values(cur, "INSERT INTO top_productos(producto_id, nombre, unidades, ingresos) VALUES %s",
                           [(r["producto_id"], r["nombre"], r["unidades"], r["ingresos"]) for r in resultado["productos"]])
            execute_values(cur, "INSERT INTO ventas_por_categoria(categoria, total_ventas, unidades) VALUES %s",
                           [(r["categoria"], r["total_ventas"], r["unidades"]) for r in resultado["categorias"]])
            execute_values(cur, "INSERT INTO ventas_por_vendedor(vendedor_id, fecha, total_ventas, num_ventas) VALUES %s",
                           [(r["vendedor_id"], r["fecha"], r["total_ventas"], r["num_ventas"]) for r in resultado["vendedores"]])
            cur.execute("INSERT INTO actualizaciones(ventas_procesadas, segundos, usuario_id) VALUES (%s, %s, %s)",
                        (resultado["ventas_procesadas"], round(segundos, 2), usuario_id))
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Verificación opcional: ¿Spark da lo mismo que el cálculo en Python del servicio?
# ---------------------------------------------------------------------
def verificar(ventas, resultado):
    sys.path.insert(0, os.getenv("CALCULO_DIR", "/app"))
    from calculo import calcular  # copia de servicio-analitica/app/calculo.py

    esperado = calcular(ventas)
    ok = True
    for clave in ("ventas_procesadas", "mensuales", "productos", "categorias", "vendedores"):
        coincide = esperado[clave] == resultado[clave]
        ok &= coincide
        print(f"   verificación {clave:<18} {'COINCIDE' if coincide else 'DIFERENTE'}")
    return ok


def main():
    ap = argparse.ArgumentParser(description="Recalcula los resúmenes de analítica con Spark")
    ap.add_argument("--verificar", action="store_true",
                    help="compara el resultado con el cálculo en Python del servicio")
    ap.add_argument("--particiones", type=int, default=4, help="particiones de los DataFrames")
    ap.add_argument("--sin-guardar", action="store_true", help="calcula pero no escribe en analitica_db")
    args = ap.parse_args()

    token, usuario_id = iniciar_sesion()
    print("[1/4] Leyendo ventas desde el API...")
    t0 = time.monotonic()
    ventas = leer_ventas(token)
    print(f"      {len(ventas)} ventas leídas en {time.monotonic() - t0:.1f} s")

    print("[2/4] Iniciando Spark...")
    constructor = (SparkSession.builder.appName("ferrepega-resumenes")
                   .config("spark.sql.session.timeZone", "UTC")
                   .config("spark.sql.shuffle.partitions", str(args.particiones))
                   .config("spark.ui.showConsoleProgress", "false"))
    if os.getenv("SPARK_MASTER"):
        constructor = constructor.master(os.environ["SPARK_MASTER"])
    spark = constructor.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    sc = spark.sparkContext
    print(f"      master={sc.master}  paralelismo={sc.defaultParallelism}  app={sc.applicationId}")

    print(f"[3/4] Calculando en paralelo ({args.particiones} particiones)...")
    t1 = time.monotonic()
    resultado = calcular_con_spark(spark, ventas, args.particiones)
    segundos = time.monotonic() - t1
    print(f"      {resultado['ventas_procesadas']} ventas -> {len(resultado['mensuales'])} meses, "
          f"{len(resultado['productos'])} productos, {len(resultado['categorias'])} categorías, "
          f"{len(resultado['vendedores'])} filas de vendedor ({segundos:.1f} s)")

    ok = True
    if args.verificar:
        print("      Comparando con el cálculo en Python del servicio:")
        ok = verificar(ventas, resultado)

    if args.sin_guardar:
        print("[4/4] --sin-guardar: no se escribió nada en analitica_db.")
    else:
        print("[4/4] Guardando en analitica_db...")
        guardar(resultado, segundos, usuario_id)
        print("      Listo: los dashboards ya muestran los datos calculados por Spark.")

    spark.stop()
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
