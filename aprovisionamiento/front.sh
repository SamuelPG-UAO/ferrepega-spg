#!/bin/bash
# =========================================================
# Ferrepega - Despliegue del FRONT: Flask + gunicorn + Nginx
#
# Se ejecuta DENTRO de la VM ferrepega-front, como administrador:
#     sudo bash /vagrant/aprovisionamiento/front.sh
#
# Qué hace (se puede repetir las veces que quieras: es idempotente):
#   1. Instala Nginx, Python y venv.
#   2. Crea el entorno virtual e instala Flask, requests y gunicorn.
#   3. Crea /etc/ferrepega-front.env con una clave de sesión ALEATORIA
#      (solo la primera vez; fuera de la carpeta del proyecto).
#   4. Instala el servicio de systemd (arranca solo al encender la VM).
#   5. Configura Nginx en el puerto 80.
#   6. Verifica que todo responde.
# =========================================================
set -e
export DEBIAN_FRONTEND=noninteractive
cd /tmp

if [ "$(id -u)" -ne 0 ]; then
  echo "Este script necesita permisos de administrador. Ejecútalo así:"
  echo "    sudo bash /vagrant/aprovisionamiento/front.sh"
  exit 1
fi

AP=/vagrant/aprovisionamiento
FRONT=/vagrant/frontend
VENV=/home/vagrant/venv-front
ENVF=/etc/ferrepega-front.env
API_URL="${FERREPEGA_API_URL:-http://192.168.56.10}"

if [ ! -f "$FRONT/wsgi.py" ]; then
  echo "ERROR: no encuentro $FRONT/wsgi.py. ¿Está la carpeta frontend en C:\\ferrepega?"
  exit 1
fi

echo ">>> [1/6] Zona horaria e instalación de Nginx y Python..."
timedatectl set-timezone America/Bogota
apt-get update -y
apt-get install -y nginx python3-venv python3-pip curl

echo ">>> [2/6] Creando el entorno virtual e instalando librerías..."
[ -d "$VENV" ] || sudo -u vagrant python3 -m venv "$VENV"
sudo -u vagrant "$VENV/bin/pip" install -q -r "$FRONT/requirements.txt"
echo "    listo: $("$VENV/bin/gunicorn" --version)"

echo ">>> [3/6] Configuración del front ($ENVF)..."
if [ ! -f "$ENVF" ]; then
  CLAVE=$(openssl rand -hex 32)
  cat > "$ENVF" <<EOT
FERREPEGA_API_URL=$API_URL
FERREPEGA_SECRET_KEY=$CLAVE
FERREPEGA_DEMO=1
FERREPEGA_COOKIE_SEGURA=0
EOT
  echo "    creado con una clave de sesión aleatoria nueva"
else
  echo "    ya existe, no se toca"
fi
chown root:vagrant "$ENVF"; chmod 640 "$ENVF"

echo ">>> [4/6] Instalando el servicio de systemd..."
cp "$AP/systemd/ferrepega-front.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable ferrepega-front.service >/dev/null 2>&1
systemctl restart ferrepega-front.service

echo ">>> [5/6] Configurando Nginx..."
rm -f /etc/nginx/sites-enabled/default
cp "$AP/nginx/ferrepega-proxy.inc" /etc/nginx/ferrepega-proxy.inc
cp "$AP/nginx/ferrepega-front.conf" /etc/nginx/conf.d/ferrepega-front.conf
nginx -t
systemctl enable nginx >/dev/null 2>&1
systemctl restart nginx

echo ">>> [6/6] Verificando..."
for _ in $(seq 1 20); do
  curl -fs http://127.0.0.1/salud >/dev/null 2>&1 && break
  sleep 0.5
done
curl -fs http://127.0.0.1/salud >/dev/null && echo "    front (Flask vía Nginx): OK" || { echo "    el front NO responde. Revisa: sudo journalctl -u ferrepega-front -n 40"; exit 1; }
ESTATICO=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/static/css/app.css)
[ "$ESTATICO" = "200" ] && echo "    archivos estáticos: OK" || echo "    AVISO: /static devolvió $ESTATICO"
curl -fs "$API_URL/api/auth/salud" >/dev/null && echo "    conexión con el back ($API_URL): OK" || echo "    AVISO: no llego al back en $API_URL (¿está la VM back encendida?)"
echo
echo "Listo. Desde Windows: http://192.168.56.11"
