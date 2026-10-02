"""
Dependencias de FastAPI para proteger endpoints.

Uso en una ruta:
    def mi_ruta(usuario = Depends(usuario_actual)): ...                 # cualquier rol
    def mi_ruta(admin = Depends(requiere_roles("admin"))): ...          # solo admin
"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import Usuario
from .security import decodificar_token

# auto_error=False: si falta el encabezado Authorization no responde por su
# cuenta, así controlamos nosotros el código (siempre 401) y el mensaje.
# Además, esto agrega el botón "Authorize" en la documentación Swagger.
esquema_bearer = HTTPBearer(auto_error=False)


def usuario_actual(
    credenciales: Optional[HTTPAuthorizationCredentials] = Depends(esquema_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    """Devuelve el usuario dueño del token enviado en el encabezado
    'Authorization: Bearer <token>'."""
    if credenciales is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token de autenticación",
                            headers={"WWW-Authenticate": "Bearer"})

    datos = decodificar_token(credenciales.credentials)
    try:
        usuario_id = int(datos["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido",
                            headers={"WWW-Authenticate": "Bearer"})

    # Se consulta la base: si el usuario fue desactivado, su token deja de servir.
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no válido o desactivado",
                            headers={"WWW-Authenticate": "Bearer"})
    return usuario


def requiere_roles(*roles: str):
    """Crea una dependencia que deja pasar solo a los roles indicados."""

    def verificar(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "No tienes permiso para esta operación")
        return usuario

    return verificar
