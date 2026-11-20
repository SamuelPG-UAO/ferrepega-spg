# Guía de sustentación individual (preguntas probables)

**¿Qué patrón usa su arquitectura?** API Gateway (Nginx "edge"), base de datos por servicio, comunicación síncrona REST, separación escritura/lectura estilo CQRS (ventas escribe; analítica mantiene un modelo de lectura precalculado), y procesamiento por lotes con Spark. Event-Driven NO está implementado: hoy no hay broker; sería el siguiente paso (ventas publica "venta registrada", analítica consume).

**¿Qué es un contenedor y por qué no una VM?** Comparte el kernel del host, arranca en segundos y pesa MB; la VM trae su propio sistema operativo. Aquí las VM son solo los "servidores" de Swarm.

**¿Qué hace Swarm?** Orquesta: reparte réplicas entre nodos, las vigila con healthcheck, las reemplaza, balancea con la red overlay y el routing mesh, y hace rolling updates (start-first).

**¿Cómo se llaman los servicios entre sí?** Por nombre (`http://ventas:8003`); el DNS interno de Swarm devuelve una IP virtual que reparte entre réplicas.

**¿Qué pasa si cae un nodo?** Las réplicas se reprograman en el otro. Limitaciones honestas: la base de datos está fijada al manager (volumen local) y con un solo manager no hay quórum Raft (haría falta 3).

**¿Cómo funciona el monitoreo?** Cada servicio expone `/metrics` (prometheus-fastapi-instrumentator / flask-exporter); Prometheus descubre las réplicas con `tasks.<servicio>` y raspa cada 10 s; node-exporter da CPU/RAM por nodo; Grafana consulta con PromQL (dashboard cargado por provisioning).

**¿Y Spark?** Master + 2 workers. El job lee ventas por la API (respeta DB por servicio), agrega con DataFrames (map → shuffle → reduce) y escribe en analitica_db en una transacción con advisory lock. `--verificar` compara con el cálculo en Python. Con este volumen de datos Spark es más lento que Python: se usa para demostrar el modelo y escalar.

**¿Seguridad?** Secretos de Swarm (JWT, Flask, Postgres, Grafana) vía archivos; contenedores sin root; /metrics no sale por el gateway; rate-limit en login. Limitaciones: sin HTTPS, contraseñas de BD de desarrollo en el stack.

**¿Cómo escalaría?** `docker service scale ferrepega_ventas=4`; más nodos worker con `docker swarm join`; BD réplica de lectura/gestor externo; broker para eventos.

**Mi parte** (completar): ______________________
