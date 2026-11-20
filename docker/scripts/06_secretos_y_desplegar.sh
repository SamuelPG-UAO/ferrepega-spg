#!/bin/bash
# =========================================================
# Paso 6 - Crea los secretos y despliega TODA la aplicación en el Swarm.
# Se ejecuta SOLO en la VM back (manager).
#
# Secretos de Swarm: se guardan cifrados dentro del clúster y cada contenedor los
# recibe como un archivo en /run/secrets/ (no quedan en el repositorio ni en el
# archivo del stack). Solo se crean si no existen, así se puede repetir el script.
# =========================================================
source "$(dirname "$0")/_comun.sh"
solo_manager
cd "$PROYECTO/docker"

crear_secreto() {  # crear_secreto <nombre> <valor>
  if docker secret inspect "$1" >/dev/null 2>&1; then
    echo "  - $1: ya existía"
  else
    printf '%s' "$2" | docker secret create "$1" - >/dev/null
    echo "  - $1: creado"
  fi
}

paso "Creando secretos..."
crear_secreto jwt_secret        "$(openssl rand -hex 32)"
crear_secreto flask_secret      "$(openssl rand -hex 32)"
crear_secreto postgres_password "$(openssl rand -hex 16)"
CLAVE_GRAFANA="${GRAFANA_CLAVE:-ferrepega2025}"
crear_secreto grafana_password  "$CLAVE_GRAFANA"

paso "Desplegando el stack '$STACK' (esto descarga imágenes la primera vez: puede tardar unos minutos)..."
docker stack deploy -c stack.yml "$STACK"

paso "Esperando a que todos los servicios estén listos (máximo 5 minutos)..."
for i in $(seq 1 60); do
  pendientes=$(docker stack services "$STACK" --format '{{.Name}} {{.Replicas}}' \
    | awk '{split($2,a,"/"); if (a[1]!=a[2]) print $1" "$2}')
  [ -z "$pendientes" ] && break
  echo "  ($i) aún faltan: $(echo "$pendientes" | tr '\n' ';')"
  sleep 5
done

paso "Estado:"
docker stack services "$STACK"
echo
echo "Siguiente: cargar los datos ->  sudo bash /vagrant/docker/scripts/07_cargar_datos.sh"
echo "Grafana: usuario admin, clave: $CLAVE_GRAFANA   (cámbiala con la variable GRAFANA_CLAVE antes de crear el secreto)"
