"""
Seguridad: cifrado de contraseñas (bcrypt) y tokens JWT.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, status

from .config import settings


# ---------- Contraseñas ----------
def cifrar_contrasena(contrasena: str) -> str:
    """Devuelve el hash bcrypt de la contraseña. bcrypt agrega una sal
    aleatoria, así que dos usuarios con la misma clave tienen hashes distintos."""
    return bcrypt.hashpw(contrasena.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_contrasena(contrasena: str, hash_guardado: str) -> bool:
    """Compara la contraseña escrita con el hash guardado."""
    try:
        return bcrypt.checkpw(contrasena.encode("utf-8"), hash_guardado.encode("utf-8"))
    except ValueError:
        return False


# Hash de mentira. Cuando el correo no existe comparamos contra este, para que
# la respuesta tarde lo mismo que con un correo real y nadie pueda descubrir
# qué correos están registrados midiendo tiempos.
HASH_FALSO = cifrar_contrasena("contrasena-que-nadie-usa")


# ---------- Tokens JWT ----------
def crear_token(usuario) -> tuple[str, int]:
    """Crea un JWT firmado. Devuelve (token, segundos_de_vida).

    El token lleva dentro: sub (id del usuario), rol, nombre, iat (emitido)
    y exp (vencimiento). Los demás microservicios leerán el rol de aquí."""
    ahora = datetime.now(timezone.utc)
    vida = timedelta(minutes=settings.jwt_expire_minutes)
    datos = {
        "sub": str(usuario.id),
        "rol": usuario.rol,
        "nombre": usuario.nombre,
        "iat": ahora,
        "exp": ahora + vida,
    }
    token = jwt.encode(datos, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(vida.total_seconds())


def decodificar_token(token: str) -> dict:
    """Verifica la firma y el vencimiento. Si el token no sirve, responde 401."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "El token ha vencido",
                            headers={"WWW-Authenticate": "Bearer"})
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido",
                            headers={"WWW-Authenticate": "Bearer"})
