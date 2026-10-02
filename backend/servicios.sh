#!/usr/bin/env bash
# servicios.sh - ayudante de DESARROLLO para arrancar/parar los microservicios
# a mano dentro de la VM ferrepega-back. Una vez desplegado el gateway
# (aprovisionamiento/gateway.sh) los administra systemd y este script solo avisa.
#
# Uso (dentro de la VM):
#   bash /vagrant/backend/servicios.sh iniciar [servicio]
#   bash /vagrant/backend/servicios.sh detener [servicio]
#   bash /vagrant/backend/servicios.sh reiniciar [servicio]
#   bash /vagrant/backend/servicios.sh estado
#   bash /vagrant/backend/servicios.sh logs <servicio>
# Sin [servicio] actúa sobre todos.

BACKEND_DIR="${BACKEND_DIR:-/vagrant/backend}"
VENV="${VENV:-$HOME/venv}"
RUN_DIR="${RUN_DIR:-$HOME/ferrepega-run}"
HOST_SALUD="${HOST_SALUD:-127.0.0.1}"

# nombre:puerto:ruta de salud
SERVICIOS=(
  "servicio-autenticacion:8001:/api/auth/salud"
  "servicio-inventario:8002:/api/inventario/salud"
  "servicio-ventas:8003:/api/ventas/salud"
  "servicio-analitica:8004:/api/analitica/salud"
)

mkdir -p "$RUN_DIR"

campo() { # campo <entrada> <n>
  echo "$1" | cut -d: -f"$2"
}

pid_de() { cat "$RUN_DIR/$1.pid" 2>/dev/null; }

corriendo() {
  local pid; pid="$(pid_de "$1")"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

# ¿Este servicio lo administra systemd? (después de correr gateway.sh, sí)
# Si es así, lanzarlo "a mano" chocaría con el puerto que ya tiene ocupado.
gestionado_por_systemd() {
  systemctl is-enabled --quiet "ferrepega-${1#servicio-}.service" 2>/dev/null
}

aviso_systemd() {
  echo "  - $1: lo administra systemd. Usa:  sudo systemctl restart ferrepega-${1#servicio-}"
}

iniciar() {
  local nombre="$1" puerto="$2" ruta="$3" dir="$BACKEND_DIR/$1"
  if gestionado_por_systemd "$nombre"; then aviso_systemd "$nombre"; return; fi
  if [[ ! -d "$dir/app" ]]; then
    echo "  - $nombre: aún no existe, se omite"; return
  fi
  if [[ ! -f "$dir/.env" ]]; then
    echo "  - $nombre: falta $dir/.env (cp .env.example .env), se omite"; return
  fi
  if corriendo "$nombre"; then
    echo "  - $nombre: ya estaba en marcha (pid $(pid_de "$nombre"))"; return
  fi
  (
    cd "$dir" || exit 1
    # shellcheck disable=SC1091
    source "$VENV/bin/activate"
    nohup uvicorn app.main:app --host 0.0.0.0 --port "$puerto" \
      >"$RUN_DIR/$nombre.log" 2>&1 &
    echo $! >"$RUN_DIR/$nombre.pid"
  )
  # espera hasta 10 s a que responda
  for _ in $(seq 1 20); do
    if curl -fs "http://$HOST_SALUD:$puerto$ruta" >/dev/null 2>&1; then
      echo "  - $nombre: OK en el puerto $puerto"; return
    fi
    sleep 0.5
  done
  echo "  - $nombre: NO respondió. Revisa: bash $0 logs $nombre"
}

detener() {
  local nombre="$1"
  if gestionado_por_systemd "$nombre"; then aviso_systemd "$nombre"; return; fi
  if corriendo "$nombre"; then
    kill "$(pid_de "$nombre")" 2>/dev/null
    echo "  - $nombre: detenido"
  else
    echo "  - $nombre: no estaba en marcha"
  fi
  rm -f "$RUN_DIR/$nombre.pid"
}

estado() {
  local nombre="$1" puerto="$2" ruta="$3"
  if gestionado_por_systemd "$nombre"; then
    local act; act="$(systemctl is-active "ferrepega-${nombre#servicio-}.service" 2>/dev/null)"
    if curl -fs "http://$HOST_SALUD:$puerto$ruta" >/dev/null 2>&1; then
      echo "  - $nombre: systemd ($act) y sano (puerto $puerto)"
    else
      echo "  - $nombre: systemd ($act) pero /salud no responde"
    fi
  elif corriendo "$nombre"; then
    if curl -fs "http://$HOST_SALUD:$puerto$ruta" >/dev/null 2>&1; then
      echo "  - $nombre: en marcha y sano (puerto $puerto)"
    else
      echo "  - $nombre: proceso vivo pero /salud no responde"
    fi
  else
    echo "  - $nombre: detenido"
  fi
}

accion="$1"; objetivo="$2"
[[ -z "$accion" ]] && { sed -n '2,13p' "$0"; exit 1; }

if [[ "$accion" == "logs" ]]; then
  [[ -z "$objetivo" ]] && { echo "Indica el servicio: logs <servicio>"; exit 1; }
  tail -n 40 "$RUN_DIR/$objetivo.log"
  exit 0
fi

echo "== $accion =="
encontrado=0
for entrada in "${SERVICIOS[@]}"; do
  nombre="$(campo "$entrada" 1)"; puerto="$(campo "$entrada" 2)"; ruta="$(campo "$entrada" 3)"
  [[ -n "$objetivo" && "$objetivo" != "$nombre" ]] && continue
  encontrado=1
  case "$accion" in
    iniciar)   iniciar "$nombre" "$puerto" "$ruta" ;;
    detener)   detener "$nombre" ;;
    reiniciar) detener "$nombre"; sleep 1; iniciar "$nombre" "$puerto" "$ruta" ;;
    estado)    estado "$nombre" "$puerto" "$ruta" ;;
    *) echo "Acción desconocida: $accion"; exit 1 ;;
  esac
done
[[ $encontrado -eq 0 ]] && echo "Servicio desconocido: $objetivo"
exit 0
