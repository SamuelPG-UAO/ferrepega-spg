#!/bin/bash
# =========================================================
# Paso 1 - Instala Docker en la VM. Se ejecuta en LAS DOS VM (back y front):
#     vagrant ssh back   ->  sudo bash /vagrant/docker/scripts/01_instalar_docker.sh
#     vagrant ssh front  ->  sudo bash /vagrant/docker/scripts/01_instalar_docker.sh
#
# Usamos el paquete docker.io de Ubuntu: ya incluye Docker Swarm.
# Se puede repetir sin problema.
# =========================================================
source "$(dirname "$0")/_comun.sh"

paso "Instalando Docker..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y docker.io curl openssl

paso "Arrancando Docker y habilitándolo al iniciar la VM..."
systemctl enable --now docker

paso "Permitiendo que el usuario vagrant use Docker sin sudo (vale desde la próxima sesión)..."
usermod -aG docker vagrant || true

paso "Listo:"
docker --version
docker info --format 'Docker {{.ServerVersion}} - Swarm: {{.Swarm.LocalNodeState}}'
