# Guion de la demostración en vivo (≈6 min dentro de los 15 de la exposición)

Antes de empezar (10 min antes): `bash docker/scripts/10_estado.sh` debe mostrar todo 2/2 y `db` 1/1.
Pestañas abiertas: http://ferrepega.test · http://192.168.56.10:3000 (Grafana, admin) · http://192.168.56.10:9090/targets · http://192.168.56.10:8080 (Spark UI) · una terminal en la VM `back` (`cd /vagrant`).

| Min | Acción | Qué decir |
|---|---|---|
| 0:00 | Mostrar `docker node ls` y `docker stack services ferrepega` | "Dos nodos Swarm; cada servicio tiene 2 réplicas repartidas entre ambos." |
| 0:45 | Navegador: login en ferrepega.test, registrar una venta | "El front llama al API Gateway; ventas llama a inventario por REST y descuenta stock." |
| 1:45 | Grafana: mostrar el panel (peticiones/s, ventas registradas, CPU) | "Prometheus raspa /metrics de cada réplica; la venta que acabo de hacer sube el contador." |
| 2:30 | Terminal: `bash docker/scripts/09_demo_fallos.sh` | "Mato una réplica a propósito: el sitio sigue respondiendo y Swarm levanta una nueva." |
| 3:30 | `docker service ps ferrepega_ventas` | "Aquí se ve la réplica caída y su reemplazo." |
| 4:00 | `bash docker/scripts/08_spark_actualizar.sh --verificar` | "Spark reparte las ventas en particiones (map), agrupa (shuffle) y suma (reduce); lo comparo con el cálculo en Python: coinciden." |
| 5:00 | Spark UI :8080 (workers y aplicación finalizada) | "Dos workers ejecutaron las tareas en paralelo." |
| 5:30 | Recargar el dashboard de analítica en el front | "El modelo de lectura quedó actualizado." |

## Si algo falla
- Spark en clúster no conecta → `08_spark_actualizar.sh --local` (mismo job, un solo proceso) y se explica.
- Todo Swarm falla → plan B `bash docker/scripts/11_volver_a_vm.sh` (versión anterior en VMs) y mostrar el diagrama.
- Grafana vacío → esperar 30 s de scrape; revisar http://192.168.56.10:9090/targets (todo UP).
