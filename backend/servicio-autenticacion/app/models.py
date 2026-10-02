"""
Modelo de datos: la tabla "usuarios" de auth_db.

La tabla la crea datos/sql/auth_db.sql (la ejecuta el ETL). Aquí solo
describimos su forma para poder consultarla desde Python.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    correo: Mapped[str] = mapped_column(String(120), unique=True)
    contrasena_hash: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(20))  # admin, vendedor o cliente
    activo: Mapped[bool] = mapped_column(Boolean, server_default="true")
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
