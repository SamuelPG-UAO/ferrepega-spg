"""
servicio-inventario - Ferrepega

Catálogo de productos (categorías, búsqueda) + control de stock + movimientos.
Arranque (desde la carpeta servicio-inventario):
    uvicorn app.main:app --host 0.0.0.0 --port 8002

Documentación interactiva (Swagger):  http://<ip>:8002/api/inventario/docs
"""
from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db
from .routers import catalogo, stock

app = FastAPI(
    title="Ferrepega - servicio-inventario",
    version="1.0.0",
    description="Catálogo de productos, existencias y movimientos de inventario.",
    docs_url="/api/inventario/docs",
    openapi_url="/api/inventario/openapi.json",
    redoc_url=None,
)


@app.get("/api/inventario/salud", tags=["Salud"])
def salud(db: Session = Depends(get_db)):
    """Público: comprueba que el servicio y su base de datos responden."""
    db.execute(text("SELECT 1"))
    return {"servicio": "servicio-inventario", "estado": "ok"}


app.include_router(catalogo.router)
app.include_router(stock.router)
