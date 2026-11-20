#!/bin/bash
# =========================================================
# Paso 9 - Demostración de alta disponibilidad: se "mata" un contenedor y se ve
# cómo el servicio sigue respondiendo y Swarm lo reemplaza solo.
# Se ejecuta SOLO en la VM back (manager).
#
#   sudo bash docker/scripts/09_demo_fallos.sh            # mata una réplica de ventas
#   sudo bash docker/scripts/09_demo_fallos.sh inventario # mata una réplica de otro servicio
#
# (La prueba de "se cae un nodo completo" se hace desde Windows con: vagrant halt front)
# =========================================================
source "$(dirname "$0")/_comun.sh"
solo_manager

SERVICIO="${1:-ventas}"
NOMBRE="${STACK}_${SERVICIO}"
docker service inspect "$NOMBRE" >/dev/null 2>&1 || falla "No existe el servicio $NOMBRE"

paso "ANTES: réplicas de $NOMBRE"
docker service ps "$NOMBRE" --filter desired-state=running --format 'table {{.Name}}\t{{.Node}}\t{{.CurrentState}}'

# Elegimos una réplica que corra en ESTE nodo para poder matarla con docker kill
CONTENEDOR=$(docker ps -q --filter "name=$NOMBRE" | head -1)
[ -n "$CONTENEDOR" ] || falla "No hay una réplica de $SERVICIO en este nodo (está toda en el otro)."

paso "Matando el contenedor $CONTENEDOR y consultando el servicio cada 0,5 s durante 20 s..."
docker kill "$CONTENEDOR" >/dev/null
fin=$((SECONDS + 20)); ok=0; mal=0
while [ $SECONDS -lt $fin ]; do
  if curl -fs -m 2 -o /dev/null "http://127.0.0.1/api/$( [ "$SERVICIO" = autenticacion ] && echo auth || echo "$SERVICIO" )/salud"; then ok=$((ok+1)); else mal=$((mal+1)); fi
  sleep 0.5
done
echo "  Respuestas correctas: $ok   Fallidas: $mal   (la otra réplica atendió mientras Swarm reemplazaba la caída)"

paso "DESPUÉS: Swarm creó un contenedor nuevo (fíjate en el historial)"
docker service ps "$NOMBRE" --format 'table {{.Name}}\t{{.Node}}\t{{.CurrentState}}\t{{.Error}}' | head -8
