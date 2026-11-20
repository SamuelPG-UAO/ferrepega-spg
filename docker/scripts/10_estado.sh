#!/bin/bash
# =========================================================
# Estado rápido de todo el sistema (para revisar antes de la demostración).
# Se ejecuta en la VM back.
# =========================================================
source "$(dirname "$0")/_comun.sh"
solo_manager

paso "Nodos del Swarm"
docker node ls
paso "Servicios (REPLICAS debe ser n/n en todos)"
docker stack services "$STACK"
paso "Dónde corre cada réplica"
docker stack ps "$STACK" --filter desired-state=running --format 'table {{.Name}}\t{{.Node}}\t{{.CurrentState}}'
paso "Pruebas de respuesta"
for r in api/salud api/auth/salud api/inventario/salud api/ventas/salud api/analitica/salud; do
  printf '  %-24s' "/$r"; curl -s -m 3 -o /dev/null -w '%{http_code}\n' "http://127.0.0.1/$r"
done
printf '  %-24s' "front /salud"; curl -s -m 3 -o /dev/null -w '%{http_code}\n' -H 'Host: ferrepega.test' http://127.0.0.1/salud
printf '  %-24s' "prometheus"; curl -s -m 3 -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9090/-/ready
printf '  %-24s' "grafana"; curl -s -m 3 -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/api/health
paso "Direcciones"
cat <<TXT
  Aplicación : http://ferrepega.test           (API: http://api.ferrepega.test)
  Grafana    : http://$IP_MANAGER:3000          (usuario admin)
  Prometheus : http://$IP_MANAGER:9090/targets
  Spark      : http://$IP_MANAGER:8080
TXT
