#!/bin/bash
# =========================================================
# Paso 7 - Carga el dataset en las bases de datos (ETL) y calcula los resúmenes.
# Se ejecuta SOLO en la VM back (manager), con el stack ya desplegado.
#
# Lanza un contenedor "suelto" dentro de la red del Swarm que ejecuta
# datos/etl_olist.py contra el contenedor de PostgreSQL (host "db").
# Necesita los CSV de Olist en C:\ferrepega\datos (carpeta /vagrant/datos), igual que antes.
# =========================================================
source "$(dirname "$0")/_comun.sh"
solo_manager

[ -f "$PROYECTO/datos/olist_orders_dataset.csv" ] \
  || falla "Faltan los CSV de Olist en $PROYECTO/datos (carpeta C:\\ferrepega\\datos en Windows)."

paso "Esperando a que PostgreSQL esté sano..."
for i in $(seq 1 40); do
  id=$(docker ps -q --filter "name=${STACK}_db" --filter "health=healthy" | head -1)
  [ -n "$id" ] && break
  sleep 3
done
[ -n "${id:-}" ] || falla "El contenedor de PostgreSQL no está sano. Revisa:  docker service logs ${STACK}_db"

paso "Ejecutando el ETL (puede tardar un minuto)..."
docker run --rm --network "${STACK}_red" -e PGHOST=db \
  -v "$PROYECTO/datos:/datos:ro" "ferrepega/etl:$VERSION" --reiniciar

paso "Calculando los resúmenes de los dashboards (servicio-analitica)..."
CORREO="${ADMIN_CORREO:-admin@ferrepega.com}"
CLAVE="${ADMIN_CLAVE:-Admin2025*}"
TOKEN=$(curl -fs -X POST http://127.0.0.1/api/auth/login -H 'content-type: application/json' \
  -d "{\"correo\":\"$CORREO\",\"contrasena\":\"$CLAVE\"}" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])') \
  || falla "No se pudo iniciar sesión como $CORREO (¿los servicios ya están arriba?)"
curl -fs -X POST http://127.0.0.1/api/analitica/actualizar -H "Authorization: Bearer $TOKEN"; echo

paso "Listo. Abre http://ferrepega.test (o http://$IP_MANAGER si aún no tienes el dominio)."
