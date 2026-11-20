#!/bin/bash
# =========================================================
# Paso 4 - Une la VM front al Swarm como nodo trabajador (worker).
# Se ejecuta SOLO en la VM front, después del paso 3.
# =========================================================
source "$(dirname "$0")/_comun.sh"

[ -f "$PROYECTO/.swarm-token" ] || falla "No existe $PROYECTO/.swarm-token. Ejecuta primero el paso 3 en la VM back."

if [ "$(docker info --format '{{.Swarm.LocalNodeState}}')" = "active" ]; then
  aviso "Este nodo ya forma parte de un Swarm."
else
  paso "Uniéndose al Swarm de $IP_MANAGER..."
  docker swarm join --token "$(cat "$PROYECTO/.swarm-token")" \
    --advertise-addr "$IP_WORKER" --data-path-addr "$IP_WORKER" "$IP_MANAGER:2377"
fi

paso "Listo. En la VM back puedes comprobarlo con:  docker node ls"
