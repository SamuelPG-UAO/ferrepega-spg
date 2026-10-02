"""
Cliente HTTP de servicio-ventas: lee las ventas COMPLETADAS, página por página.

servicio-analitica no tiene acceso a ventas_db; todo lo que sabe de las ventas
lo obtiene por la API REST de servicio-ventas (con el token del administrador
que pidió el recálculo).
"""
from typing import Iterator

import httpx

from .config import settings

TAMANO_PAGINA = 500
MAX_PAGINAS = 10_000  # freno de seguridad contra un bucle infinito


class ErrorVentas(Exception):
    def __init__(self, codigo: int, detalle):
        super().__init__(f"{codigo}: {detalle}")
        self.codigo = codigo  # 503 si ni siquiera hubo respuesta
        self.detalle = detalle


def leer_ventas(token: str) -> Iterator[dict]:
    """Entrega las ventas una a una, pidiendo páginas de 500 hasta que no haya más."""
    despues_de = 0
    try:
        with httpx.Client(base_url=settings.ventas_url, timeout=settings.ventas_timeout,
                          headers={"Authorization": f"Bearer {token}"}) as cliente:
            for _ in range(MAX_PAGINAS):
                r = cliente.get("/api/ventas/exportacion",
                                params={"despues_de": despues_de, "limite": TAMANO_PAGINA})
                if r.status_code >= 400:
                    try:
                        detalle = r.json().get("detail", r.text)
                    except ValueError:
                        detalle = r.text
                    raise ErrorVentas(r.status_code, detalle)
                pagina = r.json()
                yield from pagina["items"]
                despues_de = pagina["siguiente"]
                if despues_de is None:
                    return
            raise ErrorVentas(500, "Demasiadas páginas: se aborta el recálculo")
    except httpx.HTTPError:
        raise ErrorVentas(503, "servicio-ventas no está disponible")
