"""
Verificación de tokens JWT.

Este servicio NO consulta a servicio-autenticacion: comprueba la firma del
token con la clave compartida (JWT_SECRET). Si la firma es válida y el token
no ha vencido, confía en el id y el rol que trae dentro.
"""
import jwt
from fastapi import HTTPException, status

from .config import settings


def decodificar_token(token: str) -> dict:
    """Verifica firma y vencimiento. Si el token no sirve, responde 401."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "El token ha vencido",
                            headers={"WWW-Authenticate": "Bearer"})
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido",
                            headers={"WWW-Authenticate": "Bearer"})
