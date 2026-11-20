#!/bin/bash
# =========================================================
# Paso 3 - Crea el clúster Swarm. Se ejecuta SOLO en la VM back (será el "manager").
#
# Detalle importante: las VM de Vagrant tienen dos tarjetas de red; la primera
# (NAT) tiene la MISMA IP en las dos máquinas. Por eso se indica a Swarm cuál usar
# (la red privada 192.168.56.x), tanto para el control como para el tráfico de los
# contenedores (--data-path-addr).
# =========================================================
source "$(dirname "$0")/_comun.sh"

if [ "$(docker info --format '{{.Swarm.LocalNodeState}}')" = "active" ]; then
  aviso "Este nodo ya forma parte de un Swarm."
else
  paso "Creando el Swarm (manager en $IP_MANAGER)..."
  docker swarm init --advertise-addr "$IP_MANAGER" --data-path-addr "$IP_MANAGER"
fi

paso "Guardando el token para que la VM front pueda unirse..."
docker swarm join-token worker -q > "$PROYECTO/.swarm-token"
echo "  Guardado en $PROYECTO/.swarm-token (está en .gitignore; es un secreto)."

paso "Siguiente: en la VM front ejecuta  sudo bash /vagrant/docker/scripts/04_unir_worker.sh"
docker node ls
