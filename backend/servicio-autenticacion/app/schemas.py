"""
Esquemas (Pydantic): definen qué datos entran y salen por la API.

FastAPI los usa para validar automáticamente lo que envía el cliente
(responde 422 si algo no cumple) y para filtrar lo que devuelve.
Por eso UsuarioOut NO incluye contrasena_hash: nunca sale por la API.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Rol = Literal["admin", "vendedor", "cliente"]


class _ValidaContrasena(BaseModel):
    """bcrypt solo usa los primeros 72 bytes de una contraseña, así que
    rechazamos las más largas en lugar de truncarlas en silencio."""

    @field_validator("contrasena", check_fields=False)
    @classmethod
    def _maximo_72_bytes(cls, valor):
        if valor is not None and len(valor.encode("utf-8")) > 72:
            raise ValueError("La contraseña no puede superar 72 bytes")
        return valor


# ---------- Entrada ----------
class LoginIn(BaseModel):
    correo: str
    contrasena: str


class RegistroIn(_ValidaContrasena):
    nombre: str = Field(min_length=2, max_length=100)
    correo: EmailStr
    contrasena: str = Field(min_length=8)


class UsuarioCrearIn(_ValidaContrasena):
    """Lo usa el administrador para crear usuarios con cualquier rol."""
    nombre: str = Field(min_length=2, max_length=100)
    correo: EmailStr
    contrasena: str = Field(min_length=8)
    rol: Rol = "vendedor"


class UsuarioActualizarIn(_ValidaContrasena):
    """Todos los campos son opcionales: solo se cambia lo que se envía."""
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    rol: Optional[Rol] = None
    activo: Optional[bool] = None
    contrasena: Optional[str] = Field(default=None, min_length=8)


# ---------- Salida ----------
class UsuarioOut(BaseModel):
    # from_attributes permite construir este esquema desde un objeto
    # de SQLAlchemy (el modelo Usuario).
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    correo: str
    rol: Rol
    activo: bool
    creado_en: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos hasta que el token vence
    usuario: UsuarioOut
