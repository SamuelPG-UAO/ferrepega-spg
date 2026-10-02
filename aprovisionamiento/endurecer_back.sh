#!/bin/bash
# =========================================================
# Ferrepega - Ajustes finales del BACK antes de la entrega
#
# Se ejecuta DENTRO de la VM ferrepega-back, como administrador:
#     sudo bash /vagrant/aprovisionamiento/endurecer_back.sh
#
# Qué hace (se puede repetir sin problema: es idempotente):
#   1. Zona horaria America/Bogota en la VM y en las 4 bases de datos,
#      para que las ventas se guarden con la hora de Colombia (no UTC).
#   2. Cambia la clave JWT de desarrollo por una aleatoria, en los 4
#      microservicios a la vez (deben compartirla). Solo lo hace si todavía
#      tienen la clave de desarrollo: si lo repites, NO vuelve a rotarla
#      (rotarla cierra la sesión de todos los usuarios).
#   3. Reinicia los servicios y verifica.
# =========================================================
set -e
cd /tmp

if [ "$(id -u)" -ne 0 ]; then
  echo "Este script necesita permisos de administrador. Ejecútalo así:"
  echo "    sudo bash /vagrant/aprovisionamiento/endurecer_back.sh"
  exit 1
fi

BACK=/vagrant/backend
SERVICIOS="autenticacion inventario ventas analitica"
CLAVE_DEV="ferrepega-clave-de-desarrollo-cambiar-antes-del-despliegue-0123456789"

echo ">>> [1/3] Zona horaria America/Bogota..."
timedatectl set-timezone America/Bogota
for db in auth_db inventario_db ventas_db analitica_db; do
  sudo -u postgres psql -q -c "ALTER DATABASE ${db} SET timezone TO 'America/Bogota';"
done
echo "    VM: $(date '+%Y-%m-%d %H:%M %Z')"
echo "    bases de datos: listas (aplica a las conexiones nuevas)"

echo ">>> [2/3] Clave JWT..."
if grep -q "^JWT_SECRET=$CLAVE_DEV" "$BACK/servicio-autenticacion/.env"; then
  NUEVA=$(openssl rand -hex 32)
  for s in $SERVICIOS; do
    sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${NUEVA}|" "$BACK/servicio-$s/.env"
  done
  echo "    clave nueva (aleatoria, 64 caracteres) escrita en los 4 servicios"
else
  echo "    ya no es la de desarrollo: no se toca"
fi
# Las 4 deben coincidir; si no, los servicios se rechazarían los tokens entre sí
DISTINTAS=$(for s in $SERVICIOS; do grep "^JWT_SECRET=" "$BACK/servicio-$s/.env"; done | sort -u | wc -l)
[ "$DISTINTAS" -eq 1 ] || { echo "    ERROR: los 4 .env NO tienen la misma JWT_SECRET"; exit 1; }
echo "    las 4 claves coinciden"

echo ">>> [3/3] Reiniciando servicios..."
for s in $SERVICIOS; do systemctl restart "ferrepega-$s.service"; done
sleep 3
for par in autenticacion:8001 inventario:8002 ventas:8003 analitica:8004; do
  s=${par%%:*}; p=${par##*:}
  curl -fs "http://127.0.0.1:$p/api/${s/autenticacion/auth}/salud" >/dev/null \
    && echo "    servicio-$s: OK" || echo "    servicio-$s: NO responde (sudo journalctl -u ferrepega-$s -n 30)"
done
echo
echo "Listo. Las sesiones abiertas se cerraron: vuelve a iniciar sesión en el front."
