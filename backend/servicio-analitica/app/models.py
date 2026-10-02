"""
Modelos de datos: las tablas de analitica_db.

Son tablas de RESUMEN: no son la fuente de verdad (esa es servicio-ventas),
sino una copia ya sumada para que los dashboards respondan al instante.
Se vacían y se vuelven a llenar completas cada vez que se recalcula.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class VentaMensual(Base):
    __tablename__ = "ventas_mensuales"

    anio: Mapped[int] = mapped_column(Integer, primary_key=True)
    mes: Mapped[int] = mapped_column(Integer, primary_key=True)
    total_ventas: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    num_pedidos: Mapped[int] = mapped_column(Integer)


class TopProducto(Base):
    # Guarda TODOS los productos vendidos; el endpoint recorta a los N primeros.
    __tablename__ = "top_productos"

    producto_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150))
    unidades: Mapped[int] = mapped_column(Integer)
    ingresos: Mapped[Decimal] = mapped_column(Numeric(16, 2))


class VentaCategoria(Base):
    __tablename__ = "ventas_por_categoria"

    categoria: Mapped[str] = mapped_column(String(80), primary_key=True)
    total_ventas: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    unidades: Mapped[int] = mapped_column(Integer)


class VentaVendedor(Base):
    __tablename__ = "ventas_por_vendedor"

    vendedor_id: Mapped[int] = mapped_column(Integer, primary_key=True)  # id en auth_db
    fecha: Mapped[date] = mapped_column(Date, primary_key=True)
    total_ventas: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    num_ventas: Mapped[int] = mapped_column(Integer)


class Actualizacion(Base):
    """Bitácora de recálculos: permite mostrar 'datos actualizados al ...'."""
    __tablename__ = "actualizaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ventas_procesadas: Mapped[int] = mapped_column(Integer)
    segundos: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    usuario_id: Mapped[int] = mapped_column(Integer)
