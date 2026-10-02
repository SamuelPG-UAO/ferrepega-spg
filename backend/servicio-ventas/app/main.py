"""
servicio-ventas - Ferrepega

Clientes y ventas. Para precios y stock consulta a servicio-inventario por HTTP.
Arranque (desde la carpeta servicio-ventas):
    uvicorn app.main:app --host 0.0.0.0 --port 8003

Documentación interactiva (Swagger):  http://<ip>:8003/api/ventas/docs
"""
from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db
from .routers import clientes, ventas

app = FastAPI(
    title="Ferrepega - servicio-ventas",
    version="1.0.0",
    description="Registro de ventas, clientes y anulaciones.",
    docs_url="/api/ventas/docs",
    openapi_url="/api/ventas/openapi.json",
    redoc_url=None,
)


# La ruta /salud se declara ANTES de incluir los routers para que no la capture
# la ruta /api/ventas/{venta_id}.
@app.get("/api/ventas/salud", tags=["Salud"])
def salud(db: Session = Depends(get_db)):
    """Público: comprueba que el servicio y su base de datos responden."""
    db.execute(text("SELECT 1"))
    return {"servicio": "servicio-ventas", "estado": "ok"}


# clientes primero: "/api/ventas/clientes" no debe confundirse con "/{venta_id}"
app.include_router(clientes.router)
app.include_router(ventas.router)
