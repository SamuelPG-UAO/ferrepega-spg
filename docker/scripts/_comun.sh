# =========================================================
# Funciones comunes de los scripts (no se ejecuta solo: lo cargan los demás)
# =========================================================
set -euo pipefail

# Estos scripts necesitan permisos de administrador: si no los tienen, se piden solos
if [ "$(id -u)" -ne 0 ]; then
  exec sudo -E bash "$0" "$@"
fi

PROYECTO="${PROYECTO:-/vagrant}"          # carpeta compartida con Windows (C:\ferrepega)
IP_MANAGER="192.168.56.10"                # VM "back": administra el Swarm
IP_WORKER="192.168.56.11"                 # VM "front": nodo trabajador
STACK="ferrepega"
REGISTRO="127.0.0.1:5000"                 # registro local de imágenes (lo crea el script 05)
VERSION="1.0"

paso()  { echo; echo ">>> $*"; }
aviso() { echo "AVISO: $*"; }
falla() { echo "ERROR: $*" >&2; exit 1; }

solo_manager() {
  [ "$(docker info --format '{{.Swarm.ControlAvailable}}' 2>/dev/null)" = "true" ] \
    || falla "Este script se ejecuta en la VM 'back' (el nodo manager del Swarm)."
}
