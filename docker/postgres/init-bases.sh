#!/bin/bash
# =========================================================
# Ferrepega - Inicialización de PostgreSQL dentro del contenedor
#
# La imagen oficial de postgres ejecuta este script UNA sola vez, la primera
# vez que arranca con el volumen vacío. Hace lo mismo que crear_bd() de
# aprovisionamiento/back.sh: un usuario y una base de datos por microservicio,
# y nadie más puede conectarse a ella.
# Las tablas las crea el ETL (datos/etl_olist.py), igual que antes.
# =========================================================
set -e

crear_bd() {
  local bd="$1" usuario="$2" clave="$3"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<SQL
CREATE ROLE ${usuario} LOGIN PASSWORD '${clave}';
CREATE DATABASE ${bd} OWNER ${usuario};
REVOKE CONNECT ON DATABASE ${bd} FROM PUBLIC;
GRANT CONNECT ON DATABASE ${bd} TO ${usuario};
SQL
  echo ">>> creada ${bd} (dueño ${usuario})"
}

crear_bd "auth_db"       "auth_user"       "Ferre_auth_2025"
crear_bd "inventario_db" "inventario_user" "Ferre_inventario_2025"
crear_bd "ventas_db"     "ventas_user"     "Ferre_ventas_2025"
crear_bd "analitica_db"  "analitica_user"  "Ferre_analitica_2025"
