"""
servicio-analitica - Ferrepega

Resúmenes para los dashboards (ventas por mes, productos, categorías, vendedores).
Arranque (desde la carpeta servicio-analitica):
    uvicorn app.main:app --host 0.0.0.0 --port 8004

Documentación interactiva (Swagger):  http://<ip>:8004/api/analitica/docs
"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Actualizacion
from .routers import actualizacion, consultas


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    # Crea la tabla de bitácora si todavía no existe (las otras 4 las crea el ETL).
    Base.metadata.create_all(engine, tables=[Actualizacion.__table__])
    yield


app = FastAPI(
    title="Ferrepega - servicio-analitica",
    version="1.0.0",
    description="Datos agregados para los dashboards de administrador y vendedor.",
    docs_url="/api/analitica/docs",
    openapi_url="/api/analitica/openapi.json",
    redoc_url=None,
    lifespan=ciclo_de_vida,
)


@app.get("/api/analitica/salud", tags=["Salud"])
def salud(db: Session = Depends(get_db)):
    """Público: comprueba que el servicio y su base de datos responden."""
    db.execute(text("SELECT 1"))
    return {"servicio": "servicio-analitica", "estado": "ok"}


# Métricas para Prometheus: GET /metrics (solo accesible dentro de la red de Docker;
# el gateway no enruta esta ruta hacia afuera).
Instrumentator(excluded_handlers=["/metrics"]).instrument(app).expose(
    app, endpoint="/metrics", include_in_schema=False)

app.include_router(consultas.router)
app.include_router(actualizacion.router)
