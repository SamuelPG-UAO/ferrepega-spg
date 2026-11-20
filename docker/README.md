# Ferrepega – Entrega final: Docker, Swarm, monitoreo y Spark

Esta carpeta convierte el despliegue "a mano" (Nginx + systemd + PostgreSQL en las VM)
en una solución **contenerizada y orquestada**. El código de los microservicios es el
mismo; solo cambia *cómo se empaqueta y se ejecuta*.

## 1. Qué hay ahora

```
 Windows ──► http://ferrepega.test, http://api.ferrepega.test, :3000, :9090, :8080
                         │  (todas apuntan a 192.168.56.10)
 ┌───────────────────────┴────────────────────────────────────────────┐
 │                    DOCKER SWARM (2 nodos)                          │
 │  VM back  (192.168.56.10, manager)    VM front (192.168.56.11, worker)
 │                                                                    │
 │  edge (Nginx) x2 ── API Gateway + entrada del front  (:80, routing mesh)
 │    │                                                               │
 │    ├─► front (Flask+gunicorn) x2 ──► edge ──► servicios            │
 │    └─► autenticacion x2 · inventario x2 · ventas x2 · analitica x2 │
 │                          │ REST síncrono (ventas→inventario,       │
 │                          │               analitica→ventas)         │
 │                          ▼                                         │
 │         db (PostgreSQL 14, 4 bases)  ← solo en el manager (volumen)│
 │                                                                    │
 │  prometheus ◄── /metrics de cada réplica ── node-exporter (cada nodo)
 │  grafana ──► dashboard "Ferrepega - Estado del sistema"            │
 │  spark-master + spark-worker x2 ──► recalcula resúmenes (analitica)│
 │  registro (registry:2) ── guarda las imágenes para los dos nodos   │
 └────────────────────────────────────────────────────────────────────┘
```

| Requisito del profesor | Dónde está |
|---|---|
| Microservicios migrados | `docker/Dockerfile.servicio` (4 imágenes) + `Dockerfile.front` |
| Docker | `docker/Dockerfile.*`, `docker/entrypoint.sh` |
| Docker Swarm | `docker/stack.yml`, `scripts/03`, `04`, `06` |
| Prometheus y Grafana | `docker/prometheus/`, `docker/grafana/`, `/metrics` en cada servicio |
| Alta disponibilidad | 2 réplicas, healthchecks, reinicio automático, `scripts/09_demo_fallos.sh` |
| Procesamiento paralelo | `spark/job_ventas.py` + servicios `spark-master` / `spark-worker` |
| Diagrama | `docs/arquitectura-ferrepega.drawio` (y `.png`) |

## 2. Antes de empezar (una sola vez)

1. **Copia** el contenido del zip sobre `C:\ferrepega` (carpetas `docker/`, `spark/`, `docs/` nuevas y
   archivos modificados en `backend/`, `frontend/`, `Vagrantfile`, `.gitignore`, `.dockerignore`).
2. En PowerShell, dentro de `C:\ferrepega`: `vagrant reload`  → las VM se reinician con más memoria
   (back 4 GB, front 3,5 GB; tu equipo tiene 16 GB).
3. **Archivo hosts** de Windows (`C:\Windows\System32\drivers\etc\hosts`, como administrador): los dos
   dominios ahora apuntan al **manager** (el Swarm responde en ambas VM, pero así sigue funcionando
   aunque se caiga el worker):
   ```
   192.168.56.10  ferrepega.test www.ferrepega.test api.ferrepega.test
   ```
   (borra las líneas anteriores de `ferrepega.test` que apuntaban a 192.168.56.11).
4. Los CSV de Olist deben seguir en `C:\ferrepega\datos`.

> **Plan B:** si algo sale mal y necesitas volver al despliegue anterior: `sudo bash /vagrant/docker/scripts/11_volver_a_vm.sh`
> (en las dos VM). No se borró nada del despliegue anterior.

## 3. Paso a paso

Todos los scripts se ejecutan **dentro de las VM** (`vagrant ssh back` / `vagrant ssh front`), son
idempotentes (se pueden repetir) y piden `sudo` solos.

### Paso 1 – Instalar Docker (en *back* y en *front*)
```bash
sudo bash /vagrant/docker/scripts/01_instalar_docker.sh
```
Instala el paquete `docker.io` de Ubuntu (ya incluye Swarm), lo habilita al arrancar y deja al usuario
`vagrant` en el grupo `docker`.

### Paso 2 – Liberar las VM (en *back* y en *front*)
```bash
sudo bash /vagrant/docker/scripts/02_liberar_vm.sh
```
Apaga el Nginx, PostgreSQL y los servicios de systemd del despliegue anterior. Es necesario porque
Swarm va a publicar el **puerto 80** y para devolver memoria. No borra datos ni archivos.

### Paso 3 – Crear el Swarm (en *back*)
```bash
sudo bash /vagrant/docker/scripts/03_iniciar_swarm.sh
```
`docker swarm init` convierte a *back* en **manager** (el que decide dónde corre cada contenedor).
Se indica `--advertise-addr` y `--data-path-addr 192.168.56.10` porque las VM de Vagrant tienen una
tarjeta NAT con **la misma IP en las dos máquinas**; sin esto los nodos no se encuentran.

### Paso 4 – Unir el segundo nodo (en *front*)
```bash
sudo bash /vagrant/docker/scripts/04_unir_worker.sh
```
En *back* comprueba: `docker node ls` → deben salir 2 nodos `Ready`.

### Paso 5 – Construir las imágenes (en *back*)
```bash
sudo bash /vagrant/docker/scripts/05_construir_imagenes.sh
```
- Crea un **registro local** (`registry:2`, puerto 5000): un almacén de imágenes del que descargan
  *los dos* nodos (Swarm puede poner un contenedor en cualquiera).
- Construye 7 imágenes: `autenticacion`, `inventario`, `ventas`, `analitica` (la misma receta,
  `Dockerfile.servicio`, con argumentos), `front`, `edge` (Nginx) y `spark`, y el ETL.
- La primera vez tarda varios minutos (descarga Python, Java y PySpark).

### Paso 6 – Desplegar (en *back*)
```bash
sudo bash /vagrant/docker/scripts/06_secretos_y_desplegar.sh
```
Crea los **secretos** de Swarm (clave JWT, clave de sesión del front, clave de PostgreSQL y de Grafana)
y ejecuta `docker stack deploy`. Espera hasta que todas las réplicas estén `n/n`.
Usuario de Grafana: `admin`; clave: `ferrepega2025` (o la que pongas en `GRAFANA_CLAVE=...`).

### Paso 7 – Cargar los datos (en *back*)
```bash
sudo bash /vagrant/docker/scripts/07_cargar_datos.sh
```
Lanza el ETL (`datos/etl_olist.py`) en un contenedor dentro de la red del Swarm contra el contenedor
`db`, y luego pide a `servicio-analitica` que calcule los resúmenes. **Usuarios de demostración**
(los de siempre): `admin@ferrepega.com / Admin2025*`, `vendedor1@ferrepega.com / Vende2025*`,
`cliente@ferrepega.com / Cliente2025*`.

> La base de datos nueva reinicia las contraseñas a las de demostración. Para cambiar la del admin:
> `bash /vagrant/aprovisionamiento/cambiar_clave_admin.sh`

### Paso 8 – Procesamiento paralelo con Spark (en *back*)
```bash
sudo bash /vagrant/docker/scripts/08_spark_actualizar.sh
```
Envía `job_ventas.py` al clúster de Spark (master + 2 workers). El trabajo lee las ventas por la API,
las reparte en particiones, suma por mes / producto / categoría / vendedor en paralelo, **verifica**
que el resultado coincide con el cálculo en Python del servicio y lo guarda en `analitica_db`.
Mientras corre abre `http://192.168.56.10:8080` para ver los workers y el trabajo en vivo.
Si el clúster diera problemas: `... 08_spark_actualizar.sh --local` (corre en un solo contenedor).

### Paso 9 – Revisar todo y probar la alta disponibilidad
```bash
sudo bash /vagrant/docker/scripts/10_estado.sh          # estado general
sudo bash /vagrant/docker/scripts/09_demo_fallos.sh     # mata una réplica de ventas
```
- **Se cae un contenedor:** el script lo mata (`docker kill`) y consulta el servicio cada 0,5 s: la otra
  réplica atiende y Swarm crea una nueva. En Grafana se ve bajar y subir "Réplicas vivas".
- **Se cae un nodo:** en PowerShell `vagrant halt front` → Swarm reubica las réplicas en *back* en unos
  segundos (la aplicación sigue en `http://ferrepega.test`). Para recuperarlo: `vagrant up front`.
- **Escalar:** `docker service scale ferrepega_ventas=4` → cuatro réplicas, sin parar el servicio.
- **Actualizar sin caída:** `docker service update --force ferrepega_ventas` (reemplaza réplica por réplica
  levantando primero la nueva: `update_config: order: start-first`).

## 4. Direcciones

| Qué | Dirección |
|---|---|
| Aplicación | http://ferrepega.test |
| API (Postman) | http://api.ferrepega.test (el mismo entorno de Postman de antes) |
| Grafana | http://192.168.56.10:3000 (admin / ferrepega2025) → dashboard *Ferrepega - Estado del sistema* |
| Prometheus | http://192.168.56.10:9090/targets |
| Spark master | http://192.168.56.10:8080 |

## 5. Conceptos (para la sustentación)

- **Imagen vs. contenedor:** la imagen es la receta empaquetada (código + Python + librerías); el contenedor
  es una copia en ejecución. Mismas imágenes en los dos nodos → mismo comportamiento.
- **Stack / servicio / tarea / réplica:** el stack (`stack.yml`) describe la aplicación; cada *servicio* es
  un componente; Swarm crea *tareas* (contenedores) hasta alcanzar las *réplicas* pedidas y las repone.
- **Red overlay y DNS de servicios:** todos los servicios están en la red `red`; se llaman por nombre
  (`http://inventario:8002`) y Swarm reparte entre réplicas (IP virtual + balanceo).
- **Routing mesh:** el puerto 80 responde en la IP de cualquier nodo y Swarm enruta a un `edge` vivo.
- **Healthcheck:** cada imagen declara cómo saber si está sana (`/salud`). Si falla, Swarm la reemplaza.
- **Secretos:** la clave JWT no está en el repositorio ni en el stack; llega como archivo en `/run/secrets`.
- **Patrones:** *API Gateway* (edge), *database per service*, comunicación *síncrona REST*
  (ventas→inventario, analitica→ventas), **CQRS** a nivel de servicio (ventas escribe; analitica mantiene un
  modelo de lectura precalculado), *procesamiento por lotes* (Spark) para el modelo de lectura.
- **Prometheus:** cada servicio expone `/metrics`; Prometheus lo "raspa" cada 10 s descubriendo las réplicas con
  el DNS `tasks.<servicio>`. **Grafana** dibuja esas series (dashboard preconfigurado por *provisioning*).
- **Spark:** `master` coordina, los `worker` ejecutan *tareas* sobre particiones (map → shuffle → reduce).

## 6. Limitaciones conocidas (dilas con honestidad)

- **PostgreSQL es un punto único de falla:** un solo contenedor fijado al manager con su volumen. Las réplicas de
  los servicios sí son tolerantes a fallos. Mejora posible: replicación de PostgreSQL (Patroni / réplica de lectura).
- **El manager también es único:** con 2 nodos no hay quórum de Raft; en producción se usan 3 managers.
- **Spark con este volumen de datos es más lento que el cálculo en Python** (arranque de la JVM y reparto); el
  valor es demostrar el modelo de cómputo, que escala al crecer los datos.
- **Sin HTTPS y con contraseñas de demostración en el stack** (las de las bases); en producción irían en secretos
  y detrás de TLS.
- La comunicación es **síncrona**; no hay broker de mensajes (la arquitectura orientada a eventos sería el
  siguiente paso: `ventas` publicaría "venta registrada" y `analitica` la consumiría).

## 7. Si algo falla

| Síntoma | Qué mirar |
|---|---|
| Un servicio se queda en `0/2` | `docker service ps --no-trunc ferrepega_<servicio>` y `docker service logs ferrepega_<servicio>` |
| `port 80 already in use` | no corriste el paso 2 en esa VM |
| El worker no descarga imágenes | `curl http://127.0.0.1:5000/v2/_catalog` en el worker; el registro corre en el manager |
| Los dos nodos no se ven | `docker node ls`; revisa que el paso 3 y 4 usaron la red `192.168.56.x` |
| El dashboard sale vacío | espera 30 s y genera tráfico (navega en la app); `http://192.168.56.10:9090/targets` debe mostrar todo `UP` |
| Spark: `Connection refused` | usa `--local` y revisa `docker service logs ferrepega_spark-master` |
| Quieres empezar de cero | `docker stack rm ferrepega` (los datos de PostgreSQL quedan en el volumen `ferrepega_pgdata`) |
