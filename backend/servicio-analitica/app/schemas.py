"""
Esquemas (Pydantic): qué datos salen por la API de analítica.
"""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel

OrdenarProductos = Literal["ingresos", "unidades"]
Agrupar = Literal["dia", "mes"]


class ResumenOut(BaseModel):
    total_ventas: float
    num_pedidos: int
    unidades: int
    ticket_promedio: float          # total_ventas / num_pedidos
    actualizado_en: Optional[datetime] = None  # None = aún no se ha calculado nada


class VentaMensualOut(BaseModel):
    anio: int
    mes: int
    total_ventas: float
    num_pedidos: int


class TopProductoOut(BaseModel):
    producto_id: int
    nombre: str
    unidades: int
    ingresos: float


class CategoriaOut(BaseModel):
    categoria: str
    total_ventas: float
    unidades: int
    porcentaje: float  # parte del total de ventas, 0 a 100


class VendedorTotalOut(BaseModel):
    vendedor_id: int
    total_ventas: float
    num_ventas: int


class VentaDiariaOut(BaseModel):
    fecha: date  # con agrupar=mes es el día 1 de cada mes
    vendedor_id: Optional[int] = None  # vacío cuando se suman varios vendedores
    total_ventas: float
    num_ventas: int


class ActualizacionOut(BaseModel):
    ventas_procesadas: int
    mensuales: int
    productos: int
    categorias: int
    filas_vendedor: int
    segundos: float
    actualizado_en: datetime
