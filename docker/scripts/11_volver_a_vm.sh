#!/bin/bash
# =========================================================
# Plan B: vuelve al despliegue anterior (sin Docker): quita el stack de Swarm y
# enciende otra vez Nginx, PostgreSQL y los servicios de systemd.
# Se ejecuta en la VM back (y en la front para su Nginx y su servicio).
# =========================================================
source "$(dirname "$0")/_comun.sh"

if [ "$(docker info --format '{{.Swarm.ControlAvailable}}' 2>/dev/null)" = "true" ]; then
  paso "Quitando el stack de Swarm..."
  docker stack rm "$STACK" || true
  sleep 15
fi

paso "Encendiendo los servicios del despliegue anterior..."
for unidad in postgresql ferrepega-autenticacion ferrepega-inventario ferrepega-ventas ferrepega-analitica ferrepega-front nginx; do
  if systemctl list-unit-files "$unidad.service" 2>/dev/null | grep -q "^$unidad"; then
    systemctl enable --now "$unidad" 2>/dev/null && echo "  - $unidad: encendido" || echo "  - $unidad: no se pudo encender"
  fi
done
