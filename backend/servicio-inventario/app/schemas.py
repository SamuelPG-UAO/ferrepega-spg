"""
Esquemas (Pydantic): qué datos entran y salen por la API.

FastAPI los usa para validar lo que envía el cliente (responde 422 si algo
no cumple) y para dar forma a lo que devuelve.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

OrdenarPor = Literal["nombre", "precio", "stock"]
LIMITE_UNIDADES = 1_000_000


class _Entrada(BaseModel):
    """Base de los datos que envía el cliente: recorta espacios sobrantes
    antes de validar, así "   " no cuenta como un nombre."""
    model_config = ConfigDict(str_strip_whitespace=True)


# =====================================================================
# Categorías
# =====================================================================
class CategoriaIn(_Entrada):
    nombre: str = Field(min_length=2, max_length=80)


class CategoriaOut(BaseModel):
    id: int
    nombre: str
    nombre_original: Optional[str] = None
    total_productos: int  # solo cuenta productos activos


# =====================================================================
# Productos
# =====================================================================
class ProductoCrearIn(_Entrada):
    nombre: str = Field(min_length=2, max_length=150)
    descripcion: Optional[str] = Field(default=None, max_length=2000)
    categoria_id: int
    # Decimal (no float) para dinero: evita errores de redondeo
    precio: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    stock_inicial: int = Field(default=0, ge=0, le=LIMITE_UNIDADES)
    stock_minimo: int = Field(default=5, ge=0, le=LIMITE_UNIDADES)


class ProductoActualizarIn(_Entrada):
    """Todos los campos son opcionales: solo se cambia lo que se envía.
    La cantidad en stock NO se cambia aquí, sino con /movimientos."""
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=150)
    descripcion: Optional[str] = Field(default=None, max_length=2000)
    categoria_id: Optional[int] = None
    precio: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    activo: Optional[bool] = None
    stock_minimo: Optional[int] = Field(default=None, ge=0, le=LIMITE_UNIDADES)


class ProductoOut(BaseModel):
    id: int
    codigo_origen: Optional[str] = None
    nombre: str
    descripcion: Optional[str] = None
    categoria_id: int
    categoria: str
    precio: float
    activo: bool
    stock: int
    stock_minimo: int
    disponible: bool   # hay al menos 1 unidad
    bajo_stock: bool   # el stock está por debajo del mínimo


class PaginaProductos(BaseModel):
    total: int          # cuántos productos cumplen el filtro (sin paginar)
    limite: int
    desplazamiento: int
    items: list[ProductoOut]


# =====================================================================
# Movimientos de stock
# =====================================================================
class MovimientoIn(_Entrada):
    """Entrada de mercancía o ajuste manual hecho por el administrador.
    Las SALIDAS no se registran aquí: las genera /stock/descontar."""
    producto_id: int
    tipo: Literal["ENTRADA", "AJUSTE"]
    # ENTRADA: siempre positiva.  AJUSTE: positiva (suma) o negativa (resta).
    cantidad: int = Field(ge=-LIMITE_UNIDADES, le=LIMITE_UNIDADES)
    motivo: Optional[str] = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _reglas_por_tipo(self):
        if self.cantidad == 0:
            raise ValueError("La cantidad no puede ser 0")
        if self.tipo == "ENTRADA" and self.cantidad < 0:
            raise ValueError("Una ENTRADA debe tener cantidad positiva")
        if self.tipo == "AJUSTE" and not self.motivo:
            raise ValueError("Un AJUSTE necesita un motivo")
        return self


class MovimientoOut(BaseModel):
    id: int
    producto_id: int
    producto_nombre: str
    tipo: str
    cantidad: int
    motivo: Optional[str] = None
    venta_id: Optional[int] = None
    usuario_id: Optional[int] = None
    fecha: datetime


class MovimientoCreadoOut(MovimientoOut):
    stock_actual: int  # stock del producto después del movimiento


# =====================================================================
# Descuento y devolución por ventas (los usa servicio-ventas)
# =====================================================================
class ItemStockIn(BaseModel):
    producto_id: int = Field(gt=0)
    cantidad: int = Field(gt=0, le=100_000)


class MovimientoVentaIn(BaseModel):
    venta_id: Optional[int] = None
    items: list[ItemStockIn] = Field(min_length=1, max_length=100)


class ItemStockOut(BaseModel):
    producto_id: int
    cantidad: int
    stock_actual: int


class MovimientoVentaOut(BaseModel):
    ok: bool = True
    venta_id: Optional[int] = None
    items: list[ItemStockOut]


# =====================================================================
# Alertas de bajo stock
# =====================================================================
class StockBajoItem(BaseModel):
    producto_id: int
    nombre: str
    categoria: str
    cantidad: int
    stock_minimo: int
    faltante: int  # cuántas unidades faltan para llegar al mínimo


class PaginaStockBajo(BaseModel):
    total: int
    items: list[StockBajoItem]
