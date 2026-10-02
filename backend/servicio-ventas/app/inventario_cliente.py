"""
Cliente HTTP de servicio-inventario.

servicio-ventas NUNCA toca inventario_db: para consultar un precio o mover
stock le pregunta a servicio-inventario por su API REST, reenviando el mismo
token del usuario (así inventario aplica sus propios permisos).
"""
from typing import Any

import httpx

from .config import settings


class ErrorInventario(Exception):
    """Inventario respondió con un error (o no respondió)."""

    def __init__(self, codigo: int, detalle: Any):
        super().__init__(f"{codigo}: {detalle}")
        self.codigo = codigo      # código HTTP; 503 si ni siquiera hubo respuesta
        self.detalle = detalle


def _llamar(metodo: str, ruta: str, token: str, cuerpo: Any = None) -> Any:
    try:
        with httpx.Client(base_url=settings.inventario_url,
                          timeout=settings.inventario_timeout) as cliente:
            r = cliente.request(metodo, ruta, json=cuerpo,
                                headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError:
        raise ErrorInventario(503, "servicio-inventario no está disponible")

    if r.status_code >= 400:
        try:
            detalle = r.json().get("detail", r.text)
        except ValueError:
            detalle = r.text
        raise ErrorInventario(r.status_code, detalle)
    return r.json()


def obtener_producto(producto_id: int, token: str) -> dict:
    return _llamar("GET", f"/api/inventario/productos/{producto_id}", token)


def descontar(venta_id: int, items: list[dict], token: str) -> dict:
    return _llamar("POST", "/api/inventario/stock/descontar", token,
                   {"venta_id": venta_id, "items": items})


def devolver(venta_id: int, items: list[dict], token: str) -> dict:
    return _llamar("POST", "/api/inventario/stock/devolver", token,
                   {"venta_id": venta_id, "items": items})
