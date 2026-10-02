"""
Esquemas (Pydantic): qué datos entran y salen por la API.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class _Entrada(BaseModel):
    """Recorta espacios sobrantes antes de validar."""
    model_config = ConfigDict(str_strip_whitespace=True)


# =====================================================================
# Clientes
# =====================================================================
class ClienteIn(_Entrada):
    nombre: str = Field(min_length=2, max_length=100)
    correo: Optional[EmailStr] = Field(default=None, max_length=120)
    ciudad: Optional[str] = Field(default=None, max_length=80)


class ClienteOut(BaseModel):
    id: int
    nombre: str
    correo: Optional[str] = None
    ciudad: Optional[str] = None


class PaginaClientes(BaseModel):
    total: int
    limite: int
    desplazamiento: int
    items: list[ClienteOut]


# =====================================================================
# Ventas
# =====================================================================
class ItemVentaIn(BaseModel):
    producto_id: int = Field(gt=0)
    cantidad: int = Field(gt=0, le=100_000)
    # No hay campo "precio": el precio SIEMPRE lo pone el sistema, tomado del
    # catálogo. Si el cliente pudiera enviarlo, podría venderse todo a $1.


class VentaCrearIn(BaseModel):
    cliente_id: Optional[int] = Field(default=None, gt=0)  # sin cliente = venta de mostrador
    items: list[ItemVentaIn] = Field(min_length=1, max_length=100)


class DetalleOut(BaseModel):
    producto_id: int
    nombre_producto: str
    categoria: str
    cantidad: int
    precio_unitario: float
    subtotal: float


class VentaResumenOut(BaseModel):
    id: int
    fecha: datetime
    cliente_id: Optional[int] = None
    cliente_nombre: Optional[str] = None
    vendedor_id: int
    total: float
    estado: str


class VentaOut(VentaResumenOut):
    items: list[DetalleOut]


class AnulacionOut(VentaOut):
    # False en ventas históricas importadas: nunca descontaron stock en este
    # sistema, así que anularlas no devuelve nada al inventario.
    stock_reintegrado: bool


class PaginaVentas(BaseModel):
    total: int
    limite: int
    desplazamiento: int
    items: list[VentaResumenOut]


# =====================================================================
# Exportación (la consume servicio-analitica)
# =====================================================================
class VentaExportadaOut(BaseModel):
    id: int
    fecha: datetime
    vendedor_id: int
    total: float
    items: list[DetalleOut]


class PaginaExportacion(BaseModel):
    items: list[VentaExportadaOut]
    siguiente: Optional[int] = None  # pasar como "despues_de" para pedir la página que sigue
