"""
Catálogo: categorías y productos.

 - Lectura (categorías, búsqueda, detalle): cualquier usuario con sesión.
 - Escritura (crear, editar, desactivar): solo administrador.
"""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, contains_eager, joinedload

from ..database import get_db
from ..dependencies import UsuarioToken, requiere_roles
from ..models import Categoria, Movimiento, Producto, Stock
from ..schemas import (CategoriaIn, CategoriaOut, OrdenarPor, PaginaProductos,
                       ProductoActualizarIn, ProductoCrearIn, ProductoOut)

router = APIRouter(prefix="/api/inventario", tags=["Catálogo"])

cualquier_rol = requiere_roles("admin", "vendedor", "cliente")
solo_admin = requiere_roles("admin")


# ---------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------
def _a_producto_out(p: Producto) -> ProductoOut:
    """Convierte un Producto (con su categoría y stock cargados) en la
    respuesta de la API, calculando 'disponible' y 'bajo_stock'."""
    cantidad = p.stock.cantidad if p.stock else 0
    minimo = p.stock.stock_minimo if p.stock else 0
    return ProductoOut(
        id=p.id,
        codigo_origen=p.codigo_origen,
        nombre=p.nombre,
        descripcion=p.descripcion,
        categoria_id=p.categoria_id,
        categoria=p.categoria.nombre,
        precio=float(p.precio),
        activo=p.activo,
        stock=cantidad,
        stock_minimo=minimo,
        disponible=cantidad > 0,
        bajo_stock=cantidad < minimo,
    )


def _cargar_producto(db: Session, producto_id: int) -> Optional[Producto]:
    return db.scalar(
        select(Producto)
        .options(joinedload(Producto.categoria), joinedload(Producto.stock))
        .where(Producto.id == producto_id)
    )


def _categoria_out(c: Categoria, total_productos: int) -> CategoriaOut:
    return CategoriaOut(id=c.id, nombre=c.nombre, nombre_original=c.nombre_original,
                        total_productos=total_productos)


def _nombre_categoria_en_uso(db: Session, nombre: str, excepto_id: Optional[int] = None) -> bool:
    """Compara sin distinguir mayúsculas: 'Pinturas' y 'pinturas' son la misma."""
    consulta = select(Categoria.id).where(func.lower(Categoria.nombre) == nombre.lower())
    if excepto_id is not None:
        consulta = consulta.where(Categoria.id != excepto_id)
    return db.scalar(consulta) is not None


# ---------------------------------------------------------------------
# Categorías
# ---------------------------------------------------------------------
@router.get("/categorias", response_model=list[CategoriaOut])
def listar_categorias(
    _usuario: UsuarioToken = Depends(cualquier_rol),
    db: Session = Depends(get_db),
):
    """Lista las categorías con la cantidad de productos activos de cada una."""
    consulta = (
        select(Categoria, func.count(Producto.id))
        .outerjoin(Producto, and_(Producto.categoria_id == Categoria.id, Producto.activo.is_(True)))
        .group_by(Categoria.id)
        .order_by(Categoria.nombre)
    )
    return [_categoria_out(c, n) for c, n in db.execute(consulta).all()]


@router.post("/categorias", response_model=CategoriaOut, status_code=status.HTTP_201_CREATED)
def crear_categoria(
    datos: CategoriaIn,
    _admin: UsuarioToken = Depends(solo_admin),
    db: Session = Depends(get_db),
):
    if _nombre_categoria_en_uso(db, datos.nombre):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una categoría con ese nombre")
    categoria = Categoria(nombre=datos.nombre)
    db.add(categoria)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una categoría con ese nombre")
    db.refresh(categoria)
    return _categoria_out(categoria, 0)


@router.put("/categorias/{categoria_id}", response_model=CategoriaOut)
def renombrar_categoria(
    categoria_id: int,
    datos: CategoriaIn,
    _admin: UsuarioToken = Depends(solo_admin),
    db: Session = Depends(get_db),
):
    categoria = db.get(Categoria, categoria_id)
    if categoria is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Categoría no encontrada")
    if _nombre_categoria_en_uso(db, datos.nombre, excepto_id=categoria_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una categoría con ese nombre")

    categoria.nombre = datos.nombre
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una categoría con ese nombre")

    activos = db.scalar(select(func.count(Producto.id)).where(
        Producto.categoria_id == categoria_id, Producto.activo.is_(True)))
    return _categoria_out(categoria, activos or 0)


@router.delete("/categorias/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_categoria(
    categoria_id: int,
    _admin: UsuarioToken = Depends(solo_admin),
    db: Session = Depends(get_db),
):
    """Solo se pueden eliminar categorías sin productos (ni siquiera inactivos)."""
    categoria = db.get(Categoria, categoria_id)
    if categoria is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Categoría no encontrada")
    hay_productos = db.scalar(select(Producto.id).where(Producto.categoria_id == categoria_id).limit(1))
    if hay_productos is not None:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "La categoría tiene productos; no se puede eliminar")
    db.delete(categoria)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------
# Productos: consulta
# ---------------------------------------------------------------------
@router.get("/productos", response_model=PaginaProductos)
def buscar_productos(
    q: Optional[str] = Query(None, max_length=100, description="Texto a buscar en nombre o descripción"),
    categoria_id: Optional[int] = None,
    precio_min: Optional[Decimal] = Query(None, ge=0),
    precio_max: Optional[Decimal] = Query(None, ge=0),
    disponible: Optional[bool] = Query(None, description="true = solo con stock; false = agotados"),
    ordenar_por: OrdenarPor = "nombre",
    descendente: bool = False,
    incluir_inactivos: bool = Query(False, description="Solo tiene efecto para el administrador"),
    limite: int = Query(20, ge=1, le=100),
    desplazamiento: int = Query(0, ge=0),
    usuario: UsuarioToken = Depends(cualquier_rol),
    db: Session = Depends(get_db),
):
    """Búsqueda con filtros, orden y paginación."""
    consulta = select(Producto).outerjoin(Producto.stock)

    # Solo el administrador puede ver productos desactivados
    if not (incluir_inactivos and usuario.rol == "admin"):
        consulta = consulta.where(Producto.activo.is_(True))
    if q:
        consulta = consulta.where(or_(
            Producto.nombre.icontains(q, autoescape=True),
            Producto.descripcion.icontains(q, autoescape=True),
        ))
    if categoria_id is not None:
        consulta = consulta.where(Producto.categoria_id == categoria_id)
    if precio_min is not None:
        consulta = consulta.where(Producto.precio >= precio_min)
    if precio_max is not None:
        consulta = consulta.where(Producto.precio <= precio_max)
    if disponible is True:
        consulta = consulta.where(Stock.cantidad > 0)
    elif disponible is False:
        consulta = consulta.where(func.coalesce(Stock.cantidad, 0) <= 0)

    # Total de coincidencias, antes de aplicar la paginación
    total = db.scalar(select(func.count()).select_from(consulta.subquery())) or 0

    columna = {"nombre": Producto.nombre, "precio": Producto.precio, "stock": Stock.cantidad}[ordenar_por]
    orden = columna.desc() if descendente else columna.asc()
    productos = db.scalars(
        consulta
        .options(contains_eager(Producto.stock), joinedload(Producto.categoria))
        .order_by(orden, Producto.id)
        .limit(limite)
        .offset(desplazamiento)
    ).unique().all()

    return PaginaProductos(
        total=total, limite=limite, desplazamiento=desplazamiento,
        items=[_a_producto_out(p) for p in productos],
    )


@router.get("/productos/{producto_id}", response_model=ProductoOut)
def obtener_producto(
    producto_id: int,
    usuario: UsuarioToken = Depends(cualquier_rol),
    db: Session = Depends(get_db),
):
    producto = _cargar_producto(db, producto_id)
    if producto is None or (not producto.activo and usuario.rol != "admin"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")
    return _a_producto_out(producto)


# ---------------------------------------------------------------------
# Productos: gestión (solo administrador)
# ---------------------------------------------------------------------
@router.post("/productos", response_model=ProductoOut, status_code=status.HTTP_201_CREATED)
def crear_producto(
    datos: ProductoCrearIn,
    admin: UsuarioToken = Depends(solo_admin),
    db: Session = Depends(get_db),
):
    if db.get(Categoria, datos.categoria_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La categoría indicada no existe")

    producto = Producto(
        nombre=datos.nombre,
        descripcion=datos.descripcion,
        categoria_id=datos.categoria_id,
        precio=datos.precio,
    )
    db.add(producto)
    db.flush()  # le asigna su id sin terminar la transacción

    db.add(Stock(producto_id=producto.id, cantidad=datos.stock_inicial,
                 stock_minimo=datos.stock_minimo))
    if datos.stock_inicial > 0:
        db.add(Movimiento(producto_id=producto.id, tipo="ENTRADA", cantidad=datos.stock_inicial,
                          motivo="Stock inicial", usuario_id=admin.id))
    db.commit()
    return _a_producto_out(_cargar_producto(db, producto.id))


@router.put("/productos/{producto_id}", response_model=ProductoOut)
def actualizar_producto(
    producto_id: int,
    datos: ProductoActualizarIn,
    _admin: UsuarioToken = Depends(solo_admin),
    db: Session = Depends(get_db),
):
    """Edita datos del producto. También sirve para reactivar uno desactivado."""
    producto = _cargar_producto(db, producto_id)
    if producto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")

    cambios = {k: v for k, v in datos.model_dump(exclude_unset=True).items() if v is not None}
    if "categoria_id" in cambios and db.get(Categoria, cambios["categoria_id"]) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La categoría indicada no existe")

    stock_minimo = cambios.pop("stock_minimo", None)
    for campo, valor in cambios.items():
        setattr(producto, campo, valor)
    if stock_minimo is not None:
        if producto.stock is None:
            db.add(Stock(producto_id=producto.id, cantidad=0, stock_minimo=stock_minimo))
        else:
            producto.stock.stock_minimo = stock_minimo

    db.commit()
    return _a_producto_out(_cargar_producto(db, producto_id))


@router.delete("/productos/{producto_id}", status_code=status.HTTP_204_NO_CONTENT)
def desactivar_producto(
    producto_id: int,
    _admin: UsuarioToken = Depends(solo_admin),
    db: Session = Depends(get_db),
):
    """Borrado lógico: el producto queda inactivo, no se elimina. Así el
    historial de ventas y movimientos que lo mencionan sigue siendo válido."""
    producto = db.get(Producto, producto_id)
    if producto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")
    producto.activo = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
