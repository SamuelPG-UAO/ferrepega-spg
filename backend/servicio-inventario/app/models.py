"""
Modelos de datos: las tablas de inventario_db.

Las tablas las crea datos/sql/inventario_db.sql (las ejecuta el ETL).
Aquí solo describimos su forma para poder consultarlas desde Python.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (Boolean, DateTime, ForeignKey, Integer, Numeric,
                        String, Text, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True)
    nombre_original: Mapped[Optional[str]] = mapped_column(String(100))


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_origen: Mapped[Optional[str]] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(150))
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"))
    precio: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    activo: Mapped[bool] = mapped_column(Boolean, server_default="true")

    categoria: Mapped[Categoria] = relationship()
    # Un producto tiene una sola fila de stock (relación 1 a 1)
    stock: Mapped[Optional["Stock"]] = relationship(back_populates="producto", uselist=False)


class Stock(Base):
    __tablename__ = "stock"

    producto_id: Mapped[int] = mapped_column(
        ForeignKey("productos.id", ondelete="CASCADE"), primary_key=True
    )
    cantidad: Mapped[int] = mapped_column(Integer, server_default="0")
    stock_minimo: Mapped[int] = mapped_column(Integer, server_default="5")

    producto: Mapped[Producto] = relationship(back_populates="stock")


class Movimiento(Base):
    """Historial de cambios de stock. Nunca se borra ni se edita."""
    __tablename__ = "movimientos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    tipo: Mapped[str] = mapped_column(String(10))  # ENTRADA, SALIDA o AJUSTE
    cantidad: Mapped[int] = mapped_column(Integer)
    motivo: Mapped[Optional[str]] = mapped_column(String(200))
    venta_id: Mapped[Optional[int]] = mapped_column(Integer)    # id en ventas_db
    usuario_id: Mapped[Optional[int]] = mapped_column(Integer)  # id en auth_db
    fecha: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
