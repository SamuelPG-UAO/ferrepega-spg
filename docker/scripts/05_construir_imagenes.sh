#!/bin/bash
# =========================================================
# Paso 5 - Construye las imágenes de Docker y las publica en un registro local.
# Se ejecuta SOLO en la VM back (manager).
#
# ¿Por qué un registro? Swarm puede poner un contenedor en CUALQUIER nodo, y cada
# nodo debe poder descargar la imagen. El registro (un contenedor más, publicado
# en el puerto 5000) es el "almacén" de donde las bajan los dos nodos.
# Se puede repetir: Docker reutiliza lo que no cambió.
# =========================================================
source "$(dirname "$0")/_comun.sh"
solo_manager
cd "$PROYECTO"

paso "Creando el registro local de imágenes (si no existe)..."
if ! docker service inspect registro >/dev/null 2>&1; then
  docker service create --name registro --constraint node.role==manager \
    --publish published=5000,target=5000 \
    --mount type=volume,source=registro,target=/var/lib/registry registry:2
fi
for i in $(seq 1 30); do
  curl -fs "http://$REGISTRO/v2/" >/dev/null 2>&1 && break
  sleep 2
done
curl -fs "http://$REGISTRO/v2/" >/dev/null || falla "El registro no responde en $REGISTRO"
echo "  Registro listo en $REGISTRO"

construir() {  # construir <nombre> <Dockerfile> [argumentos de build...]
  local nombre="$1" dockerfile="$2"; shift 2
  paso "Construyendo $nombre..."
  docker build -f "docker/$dockerfile" -t "$REGISTRO/ferrepega/$nombre:$VERSION" "$@" .
  docker push "$REGISTRO/ferrepega/$nombre:$VERSION"
}

construir autenticacion Dockerfile.servicio --build-arg SERVICIO=autenticacion --build-arg PUERTO=8001 --build-arg RUTA_SALUD=/api/auth/salud
construir inventario    Dockerfile.servicio --build-arg SERVICIO=inventario    --build-arg PUERTO=8002 --build-arg RUTA_SALUD=/api/inventario/salud
construir ventas        Dockerfile.servicio --build-arg SERVICIO=ventas        --build-arg PUERTO=8003 --build-arg RUTA_SALUD=/api/ventas/salud
construir analitica     Dockerfile.servicio --build-arg SERVICIO=analitica     --build-arg PUERTO=8004 --build-arg RUTA_SALUD=/api/analitica/salud
construir front         Dockerfile.front
construir edge          Dockerfile.edge
construir spark         Dockerfile.spark

paso "Construyendo la imagen del ETL (solo se usa aquí, en el manager)..."
docker build -f docker/Dockerfile.etl -t "ferrepega/etl:$VERSION" .

paso "Imágenes en el registro:"
curl -s "http://$REGISTRO/v2/_catalog"; echo
