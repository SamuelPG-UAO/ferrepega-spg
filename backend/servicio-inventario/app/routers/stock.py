"""
Stock y movimientos.

 - /stock/descontar  -> lo usa servicio-ventas al registrar una venta (vendedor/admin)
 - /stock/devolver   -> lo usa servicio-ventas al anular una venta (admin)
 - /stock/bajo       -> alerta de productos por debajo del mínimo (admin)
 - /movimientos      -> entradas y ajustes manuales + historial (admin)

Regla de oro: el stock nunca queda negativo. Para garantizarlo, antes de
modificar una fila de stock se BLOQUEA (SELECT ... FOR UPDATE): si dos ventas
llegan al mismo tiempo por el último producto, la segunda espera a que la
primera termine y luego ve el stock ya actualizado.
"""
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import UsuarioToken, requiere_roles
from ..models import Categoria, Movimiento, Producto, Stock
from ..schemas import (ItemStockOut, MovimientoCreadoOut, MovimientoIn,
                       MovimientoOut, MovimientoVentaIn, MovimientoVentaOut,
                       PaginaStockBajo, StockBajoItem)

router = APIRouter(prefix="/api/inventario", tags=["Stock y movimientos"])

solo_admin = requiere_roles("admin")
vendedor_o_admin = requiere_roles("admin", "vendedor")


# ---------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------
def _agrupar_items(items) -> dict[int, int]:
    """Si el mismo producto viene dos veces, suma sus cantidades."""
    total: dict[int, int] = defaultdict(int)
    for it in items:
        total[it.producto_id] += it.cantidad
    return dict(total)


def _bloquear_stock(db: Session, ids: list[int]) -> dict[int, tuple[Producto, Stock]]:
    """Trae y bloquea las filas de stock de los productos indicados.

    Se piden SIEMPRE ordenadas por id: así, dos operaciones simultáneas que
    toquen los mismos productos los bloquean en el mismo orden y no se
    quedan esperándose mutuamente (interbloqueo / deadlock).
    """
    filas = db.execute(
        select(Producto, Stock)
        .join(Stock, Stock.producto_id == Producto.id)
        .where(Producto.id.in_(ids))
        .order_by(Producto.id)
        .with_for_update(of=Stock)
    ).all()
    return {p.id: (p, s) for p, s in filas}


def _movimiento_out(m: Movimiento, nombre: str) -> MovimientoOut:
    return MovimientoOut(id=m.id, producto_id=m.producto_id, producto_nombre=nombre,
                         tipo=m.tipo, cantidad=m.cantidad, motivo=m.motivo,
                         venta_id=m.venta_id, usuario_id=m.usuario_id, fecha=m.fecha)


# ---------------------------------------------------------------------
# Descuento y devolución (para servicio-ventas)
# ---------------------------------------------------------------------
@router.post("/stock/descontar", response_model=MovimientoVentaOut)
def descontar_stock(
    datos: MovimientoVentaIn,
    usuario: UsuarioToken = Depends(vendedor_o_admin),
    db: Session = Depends(get_db),
):
    """Descuenta el stock de TODOS los productos o de NINGUNO (atómico)."""
    pedido = _agrupar_items(datos.items)
    filas = _bloquear_stock(db, sorted(pedido))

    desconocidos = [pid for pid in pedido if pid not in filas]
    if desconocidos:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"Producto(s) no encontrado(s): {desconocidos}")

    inactivos = [pid for pid in pedido if not filas[pid][0].activo]
    if inactivos:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Producto(s) no disponibles para la venta: {inactivos}")

    faltantes = [
        {"producto_id": pid, "nombre": filas[pid][0].nombre,
         "solicitado": cant, "disponible": filas[pid][1].cantidad}
        for pid, cant in pedido.items() if filas[pid][1].cantidad < cant
    ]
    if faltantes:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT,
                            {"mensaje": "Stock insuficiente", "faltantes": faltantes})

    resultado = []
    for pid, cant in sorted(pedido.items()):
        stock = filas[pid][1]
        stock.cantidad -= cant
        db.add(Movimiento(producto_id=pid, tipo="SALIDA", cantidad=cant,
                          motivo="Venta", venta_id=datos.venta_id, usuario_id=usuario.id))
        resultado.append(ItemStockOut(producto_id=pid, cantidad=cant, stock_actual=stock.cantidad))
    db.commit()
    return MovimientoVentaOut(venta_id=datos.venta_id, items=resultado)


@router.post("/stock/devolver", response_model=MovimientoVentaOut)
def devolver_stock(
    datos: MovimientoVentaIn,
    admin: UsuarioToken = Depends(solo_admin),
    db: Session = Depends(get_db),
):
    """Reintegra al stock las unidades de una venta anulada."""
    pedido = _agrupar_items(datos.items)
    filas = _bloquear_stock(db, sorted(pedido))

    desconocidos = [pid for pid in pedido if pid not in filas]
    if desconocidos:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"Producto(s) no encontrado(s): {desconocidos}")

    motivo = (f"Devolución por anulación de la venta #{datos.venta_id}"
              if datos.venta_id else "Devolución por anulación de venta")
    resultado = []
    for pid, cant in sorted(pedido.items()):
        stock = filas[pid][1]
        stock.cantidad += cant
        db.add(Movimiento(producto_id=pid, tipo="ENTRADA", cantidad=cant,
                          motivo=motivo, venta_id=datos.venta_id, usuario_id=admin.id))
        resultado.append(ItemStockOut(producto_id=pid, cantidad=cant, stock_actual=stock.cantidad))
    db.commit()
    return MovimientoVentaOut(venta_id=datos.venta_id, items=resultado)


# ---------------------------------------------------------------------
# Alerta de bajo stock
# ---------------------------------------------------------------------
@router.get("/stock/bajo", response_model=PaginaStockBajo)
def stock_bajo(
    limite: int = Query(50, ge=1, le=200),
    _admin: UsuarioToken = Depends(solo_admin),
    db: Session = Depends(get_db),
):
    """Productos activos con menos unidades que su mínimo, los más críticos primero."""
    condicion = (Producto.activo.is_(True)) & (Stock.cantidad < Stock.stock_minimo)
    base = (select(Producto.id, Producto.nombre, Categoria.nombre, Stock.cantidad, Stock.stock_minimo)
            .join(Stock, Stock.producto_id == Producto.id)
            .join(Categoria, Categoria.id == Producto.categoria_id)
            .where(condicion))
    total = db.scalar(
        select(func.count()).select_from(Producto)
        .join(Stock, Stock.producto_id == Producto.id).where(condicion)) or 0

    faltante = Stock.stock_minimo - Stock.cantidad
    filas = db.execute(base.order_by(faltante.desc(), Producto.id).limit(limite)).all()
    return PaginaStockBajo(total=total, items=[
        StockBajoItem(producto_id=pid, nombre=nom, categoria=cat, cantidad=cant,
                      stock_minimo=minimo, faltante=minimo - cant)
        for pid, nom, cat, cant, minimo in filas
    ])


# ---------------------------------------------------------------------
# Movimientos manuales e historial (administrador)
# ---------------------------------------------------------------------
@router.post("/movimientos", response_model=MovimientoCreadoOut,
             status_code=status.HTTP_201_CREATED)
def registrar_movimiento(
    datos: MovimientoIn,
    admin: UsuarioToken = Depends(solo_admin),
    db: Session = Depends(get_db),
):
    """Registra una ENTRADA de mercancía o un AJUSTE manual de inventario."""
    filas = _bloquear_stock(db, [datos.producto_id])
    if datos.producto_id not in filas:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")

    producto, stock = filas[datos.producto_id]
    nuevo = stock.cantidad + datos.cantidad
    if nuevo < 0:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"El stock quedaría negativo (actual: {stock.cantidad})")

    stock.cantidad = nuevo
    mov = Movimiento(producto_id=producto.id, tipo=datos.tipo, cantidad=datos.cantidad,
                     motivo=datos.motivo, usuario_id=admin.id)
    db.add(mov)
    db.commit()
    db.refresh(mov)
    base = _movimiento_out(mov, producto.nombre)
    return MovimientoCreadoOut(**base.model_dump(), stock_actual=nuevo)


@router.get("/movimientos", response_model=list[MovimientoOut])
def listar_movimientos(
    producto_id: Optional[int] = None,
    tipo: Optional[str] = Query(None, pattern="^(ENTRADA|SALIDA|AJUSTE)$"),
    limite: int = Query(50, ge=1, le=200),
    desplazamiento: int = Query(0, ge=0),
    _admin: UsuarioToken = Depends(solo_admin),
    db: Session = Depends(get_db),
):
    """Historial de movimientos, del más reciente al más antiguo."""
    consulta = select(Movimiento, Producto.nombre).join(Producto, Producto.id == Movimiento.producto_id)
    if producto_id is not None:
        consulta = consulta.where(Movimiento.producto_id == producto_id)
    if tipo:
        consulta = consulta.where(Movimiento.tipo == tipo)
    filas = db.execute(consulta.order_by(Movimiento.fecha.desc(), Movimiento.id.desc())
                       .limit(limite).offset(desplazamiento)).all()
    return [_movimiento_out(m, nombre) for m, nombre in filas]
