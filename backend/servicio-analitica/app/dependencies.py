"""
Dependencias de FastAPI para proteger endpoints.

    Depends(requiere_roles("admin"))                       -> solo administrador
    Depends(requiere_roles("admin", "vendedor", "cliente")) -> cualquier usuario con sesión
"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .security import decodificar_token

# auto_error=False: controlamos nosotros el código (siempre 401) y el mensaje.
esquema_bearer = HTTPBearer(auto_error=False)


class UsuarioToken(BaseModel):
    """Los datos del usuario, tomados del token (no de una base de datos)."""
    id: int
    rol: str
    nombre: str
    token: str  # el JWT original: se reenvía a servicio-inventario al llamarlo


def usuario_actual(
    credenciales: Optional[HTTPAuthorizationCredentials] = Depends(esquema_bearer),
) -> UsuarioToken:
    if credenciales is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token de autenticación",
                            headers={"WWW-Authenticate": "Bearer"})

    datos = decodificar_token(credenciales.credentials)
    try:
        return UsuarioToken(id=int(datos["sub"]), rol=datos["rol"], nombre=datos.get("nombre", ""),
                            token=credenciales.credentials)
    except (KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido",
                            headers={"WWW-Authenticate": "Bearer"})


def requiere_roles(*roles: str):
    """Crea una dependencia que deja pasar solo a los roles indicados."""

    def verificar(usuario: UsuarioToken = Depends(usuario_actual)) -> UsuarioToken:
        if usuario.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "No tienes permiso para esta operación")
        return usuario

    return verificar
