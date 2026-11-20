#!/bin/sh
# =========================================================
# Ferrepega - Entrada común de los contenedores
#
# Docker Swarm entrega los secretos como ARCHIVOS en /run/secrets/. Las
# aplicaciones leen sus claves de variables de entorno, así que aquí se
# convierte: si existe NOMBRE_FILE=/ruta/al/archivo, se carga el contenido
# del archivo en la variable NOMBRE. Así la clave JWT y la de sesión nunca
# aparecen en el archivo del stack ni en `docker inspect`.
# =========================================================
set -e

for var in JWT_SECRET FERREPEGA_SECRET_KEY; do
  eval "archivo=\${${var}_FILE:-}"
  if [ -n "$archivo" ]; then
    if [ -f "$archivo" ]; then
      export "$var=$(cat "$archivo")"
    else
      echo "ERROR: ${var}_FILE apunta a $archivo y no existe" >&2
      exit 1
    fi
  fi
done

exec "$@"
