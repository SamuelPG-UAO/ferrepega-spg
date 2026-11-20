"""
servicio-autenticacion - Ferrepega

Punto de entrada. Arranque (desde la carpeta servicio-autenticacion):
    uvicorn app.main:app --host 0.0.0.0 --port 8001

Documentación interactiva (Swagger):  http://<ip>:8001/api/auth/docs
"""
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from .routers import auth, usuarios

app = FastAPI(
    title="Ferrepega - servicio-autenticacion",
    version="1.0.0",
    description="Registro, inicio de sesión (JWT) y gestión de usuarios y roles.",
    # Todas las rutas viven bajo /api/auth, igual que en el API Gateway (Nginx),
    # así el gateway podrá reenviar las peticiones sin reescribir direcciones.
    docs_url="/api/auth/docs",
    openapi_url="/api/auth/openapi.json",
    redoc_url=None,
)

# Métricas para Prometheus: GET /metrics (solo accesible dentro de la red de Docker;
# el gateway no enruta esta ruta hacia afuera).
Instrumentator(excluded_handlers=["/metrics"]).instrument(app).expose(
    app, endpoint="/metrics", include_in_schema=False)

app.include_router(auth.router)
app.include_router(usuarios.router)
