"""
Modelos de datos: las tablas de ventas_db.

Las tablas las crea datos/sql/ventas_db.sql (las ejecuta el ETL).
Ojo: vendedor_id y producto_id son números que "apuntan" a otras bases de
datos (auth_db e inventario_db). No son llaves foráneas: cada microservicio
solo puede tocar su propia base.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_origen: Mapped[Optional[str]] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(100))
    correo: Mapped[Optional[str]] = mapped_column(String(120))
    ciudad: Mapped[Optional[str]] = mapped_column(String(80))


class Venta(Base):
    __tablename__ = "ventas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Solo tienen valor las ventas importadas del dataset; las nuevas lo dejan vacío.
    codigo_origen: Mapped[Optional[str]] = mapped_column(String(40), unique=True)
    cliente_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clientes.id"))
    vendedor_id: Mapped[int] = mapped_column(Integer)  # id en auth_db
    fecha: Mapped[datetime] = mapped_column(DateTime)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    estado: Mapped[str] = mapped_column(String(12))  # COMPLETADA o ANULADA

    cliente: Mapped[Optional[Cliente]] = relationship(lazy="joined")
    detalle: Mapped[list["DetalleVenta"]] = relationship(
        back_populates="venta", order_by="DetalleVenta.id",
        cascade="all, delete-orphan", lazy="selectin",
    )


class DetalleVenta(Base):
    __tablename__ = "detalle_venta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venta_id: Mapped[int] = mapped_column(ForeignKey("ventas.id", ondelete="CASCADE"))
    producto_id: Mapped[int] = mapped_column(Integer)  # id en inventario_db
    nombre_producto: Mapped[str] = mapped_column(String(150))  # copia
    categoria: Mapped[str] = mapped_column(String(80))         # copia
    cantidad: Mapped[int] = mapped_column(Integer)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    venta: Mapped[Venta] = relationship(back_populates="detalle")
