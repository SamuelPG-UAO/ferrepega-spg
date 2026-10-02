#!/bin/bash
# =========================================================
# Ferrepega - Despliegue del BACK: gateway Nginx + servicios systemd
#
# Se ejecuta DENTRO de la VM ferrepega-back, como administrador:
#     sudo bash /vagrant/aprovisionamiento/gateway.sh
#
# Qué hace (se puede repetir las veces que quieras: es idempotente):
#   1. Instala Nginx.
#   2. Instala las librerías Python de cada microservicio.
#   3. Crea el archivo .env de cada microservicio si no existe.
#   4. Apaga los servicios que hayas dejado corriendo "a mano" (servicios.sh).
#   5. Instala los servicios de systemd (arrancan solos al encender la VM).
#   6. Configura Nginx como API Gateway en el puerto 80.
#   7. Verifica que todo responde.
# =========================================================
set -e
export DEBIAN_FRONTEND=noninteractive
cd /tmp

if [ "$(id -u)" -ne 0 ]; then
  echo "Este script necesita permisos de administrador. Ejecútalo así:"
  echo "    sudo bash /vagrant/aprovisionamiento/gateway.sh"
  exit 1
fi

RAIZ=/vagrant
BACK=$RAIZ/backend
AP=$RAIZ/aprovisionamiento
PIP=/home/vagrant/venv/bin/pip
# nombre : puerto
SERVICIOS="autenticacion:8001 inventario:8002 ventas:8003 analitica:8004"

if [ ! -x "$PIP" ]; then
  echo "ERROR: no existe el entorno virtual /home/vagrant/venv."
  echo "Ejecuta primero:  vagrant provision back   (desde Windows)"
  exit 1
fi

echo ">>> [1/7] Instalando Nginx..."
apt-get update -y
apt-get install -y nginx

echo ">>> [2/7] Instalando las librerías de cada microservicio..."
for s in $SERVICIOS; do
  nombre=${s%%:*}
  sudo -u vagrant "$PIP" install -q -r "$BACK/servicio-$nombre/requirements.txt"
  echo "    servicio-$nombre: listo"
done

echo ">>> [3/7] Revisando los archivos .env..."
for s in $SERVICIOS; do
  nombre=${s%%:*}
  dir="$BACK/servicio-$nombre"
  if [ ! -f "$dir/.env" ]; then
    sudo -u vagrant cp "$dir/.env.example" "$dir/.env"
    echo "    servicio-$nombre: .env creado desde .env.example"
    echo "    AVISO: usa la clave JWT_SECRET de desarrollo; cámbiala antes de la entrega."
  else
    echo "    servicio-$nombre: .env ya existe"
  fi
done

echo ">>> [4/7] Apagando servicios lanzados a mano (si los hay)..."
sudo -u vagrant -H bash "$BACK/servicios.sh" detener || true
sleep 1

echo ">>> [5/7] Instalando los servicios de systemd..."
cp "$AP"/systemd/ferrepega-*.service "$AP"/systemd/ferrepega-back.target /etc/systemd/system/
systemctl daemon-reload
systemctl enable ferrepega-back.target >/dev/null 2>&1
for s in $SERVICIOS; do
  systemctl enable "ferrepega-${s%%:*}.service" >/dev/null 2>&1
done
# restart (y no solo start): así toman el código nuevo si ya estaban corriendo
systemctl restart ferrepega-back.target
for s in $SERVICIOS; do
  systemctl restart "ferrepega-${s%%:*}.service"
done

echo ">>> [6/7] Configurando Nginx como API Gateway..."
cp "$AP/nginx/ferrepega-gateway.conf" /etc/nginx/conf.d/ferrepega-gateway.conf
# El sitio de bienvenida de Nginx ocuparía el mismo puerto 80
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx >/dev/null 2>&1
systemctl restart nginx

echo ">>> [7/7] Verificando (puede tardar unos segundos mientras arrancan)..."
fallos=0
verificar() { # etiqueta, ruta
  for _ in $(seq 1 30); do
    if curl -fs "http://127.0.0.1$2" >/dev/null 2>&1; then
      echo "    OK       $1  ->  $2"; return
    fi
    sleep 1
  done
  echo "    FALLÓ    $1  ->  $2"; fallos=$((fallos + 1))
}
verificar "gateway           " /api/salud
verificar "autenticacion     " /api/auth/salud
verificar "inventario        " /api/inventario/salud
verificar "ventas            " /api/ventas/salud
verificar "analitica         " /api/analitica/salud

echo
if [ "$fallos" -eq 0 ]; then
  echo ">>> Todo en orden. El back responde en http://192.168.56.10/"
else
  echo ">>> $fallos comprobación(es) fallaron. Para ver por qué:"
  echo "      sudo systemctl status ferrepega-ventas       (cambia el nombre del servicio)"
  echo "      sudo journalctl -u ferrepega-ventas -n 40 --no-pager"
  exit 1
fi
