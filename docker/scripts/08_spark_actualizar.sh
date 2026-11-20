#!/bin/bash
# =========================================================
# Paso 8 - Lanza el trabajo de Spark que recalcula los resúmenes en paralelo.
# Se ejecuta SOLO en la VM back (manager).
#
#   sudo bash docker/scripts/08_spark_actualizar.sh            # en el clúster (master + 2 workers)
#   sudo bash docker/scripts/08_spark_actualizar.sh --local    # solo en el contenedor del master (plan B)
#
# Pide la contraseña del administrador (o usa ADMIN_CLAVE si ya está definida).
# El trabajo se manda al master con spark-submit; los 2 workers calculan en
# paralelo y el resultado queda en analitica_db. Puedes ver el trabajo en vivo
# en la interfaz del master:  http://192.168.56.10:8080
# =========================================================
source "$(dirname "$0")/_comun.sh"
solo_manager

MODO="cluster"; [ "${1:-}" = "--local" ] && MODO="local"

CORREO="${ADMIN_CORREO:-admin@ferrepega.com}"
if [ -z "${ADMIN_CLAVE:-}" ]; then
  read -r -s -p "Contraseña de $CORREO [Admin2025*]: " ADMIN_CLAVE; echo
  ADMIN_CLAVE="${ADMIN_CLAVE:-Admin2025*}"
fi

MASTER=$(docker ps -q --filter "name=${STACK}_spark-master" | head -1)
[ -n "$MASTER" ] || falla "No encuentro el contenedor spark-master. ¿Está desplegado el stack?"

if [ "$MODO" = "cluster" ]; then
  paso "Workers registrados en el master:"
  docker exec "$MASTER" python -c "
import json, urllib.request
d = json.load(urllib.request.urlopen('http://127.0.0.1:8080/json/'))
print('  workers vivos:', len([w for w in d['workers'] if w['state'] == 'ALIVE']), '| cores:', d['cores'], '| memoria:', d['memory'], 'MB')
"
  MAESTRO="spark://spark-master:7077"
else
  MAESTRO="local[*]"
fi

paso "Enviando el trabajo a Spark ($MAESTRO)..."
docker exec \
  -e ADMIN_CORREO="$CORREO" -e ADMIN_CLAVE="$ADMIN_CLAVE" \
  -e FERREPEGA_API_URL=http://edge -e PGHOST=db \
  "$MASTER" spark-submit --master "$MAESTRO" \
    --driver-memory 512m --executor-memory 512m --total-executor-cores 2 \
    --conf spark.driver.host=spark-master --conf spark.driver.bindAddress=0.0.0.0 \
    --conf spark.driver.port=40000 --conf spark.driver.blockManager.port=40001 \
    /app/job_ventas.py --verificar

paso "Listo. Actualiza el dashboard del administrador en http://ferrepega.test para ver los datos."
