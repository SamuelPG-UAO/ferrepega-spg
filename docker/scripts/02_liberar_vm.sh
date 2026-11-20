#!/bin/bash
# =========================================================
# Paso 2 - Apaga lo que corría "a mano" en las VM (Nginx, microservicios con
# systemd, PostgreSQL, front) para liberar el puerto 80 y la memoria: ahora
# todo correrá en contenedores. NO borra nada: los datos y archivos siguen ahí,
# y 11_volver_a_vm.sh lo vuelve a encender si hace falta.
# Se ejecuta en LAS DOS VM.
# =========================================================
source "$(dirname "$0")/_comun.sh"

paso "Deteniendo los servicios del despliegue anterior (si existen)..."
for unidad in ferrepega-back.target ferrepega-autenticacion ferrepega-inventario ferrepega-ventas \
              ferrepega-analitica ferrepega-front nginx postgresql; do
  if systemctl list-unit-files "${unidad%.target}.service" "$unidad" 2>/dev/null | grep -q "^${unidad}"; then
    systemctl disable --now "$unidad" 2>/dev/null && echo "  - $unidad: detenido" || echo "  - $unidad: ya estaba detenido"
  fi
done

paso "Puertos que quedan ocupados (el 80 debe estar libre):"
ss -ltn | awk 'NR==1 || /:80 |:5432 |:8000 |:800[1-4] /' || true
