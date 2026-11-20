"""
Ventas: registrar, consultar y anular.

Registrar una venta toca DOS servicios (ventas e inventario), cada uno con su
propia base de datos, así que no hay una transacción única que cubra ambos.
El orden elegido es:

  1. Pedir a inventario el precio y estado de cada producto (solo lectura).
  2. Armar la venta en ventas_db y hacer "flush" (obtiene su id, SIN confirmar).
  3. Pedir a inventario que descuente el stock (atómico: todo o nada).
       - Si inventario rechaza (stock insuficiente...), se hace rollback aquí:
         no queda ninguna venta a medias.
       - Si acepta, se hace commit de la venta.

Limitación conocida: si el commit fallara justo después de que inventario
descontó (p. ej. se cae la base de ventas en ese instante), quedaría stock
descontado sin venta. Se registra en el log con el id de venta, y los
movimientos de inventario (SALIDA con venta_id) permiten conciliarlo.
"""
import logging
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from prometheus_client import Counter
from sqlalchemy import func, select
from sqlalchemy.orm import Session, lazyload

from .. import inventario_cliente as inventario
from ..database import get_db
from ..dependencies import UsuarioToken, requiere_roles
from ..inventario_cliente import ErrorInventario
from ..models import Cliente, DetalleVenta, Venta
from ..schemas import (AnulacionOut, DetalleOut, PaginaExportacion, PaginaVentas,
                       VentaCrearIn, VentaExportadaOut, VentaOut, VentaResumenOut)

log = logging.getLogger("servicio-ventas")

# Métrica de negocio para Grafana: ventas nuevas registradas desde que arrancó este contenedor
VENTAS_REGISTRADAS = Counter(
    "ferrepega_ventas_registradas",
    "Ventas nuevas registradas con éxito")

router = APIRouter(prefix="/api/ventas", tags=["Ventas"])

vendedor_o_admin = requiere_roles("admin", "vendedor")
solo_admin = requiere_roles("admin")

CENTAVOS = Decimal("0.01")


# ---------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------
def _resumen(v: Venta) -> VentaResumenOut:
    return VentaResumenOut(
        id=v.id, fecha=v.fecha, cliente_id=v.cliente_id,
        cliente_nombre=v.cliente.nombre if v.cliente else None,
        vendedor_id=v.vendedor_id, total=float(v.total), estado=v.estado,
    )


def _completa(v: Venta) -> VentaOut:
    return VentaOut(
        **_resumen(v).model_dump(),
        items=[DetalleOut(producto_id=d.producto_id, nombre_producto=d.nombre_producto,
                          categoria=d.categoria, cantidad=d.cantidad,
                          precio_unitario=float(d.precio_unitario), subtotal=float(d.subtotal))
               for d in v.detalle],
    )


def _error_http(e: ErrorInventario) -> HTTPException:
    """Traduce un error de inventario a la respuesta que ve el cliente."""
    if e.codigo in (404, 409):
        # Son errores "de negocio": se reenvían tal cual (incluye la lista de faltantes).
        return HTTPException(e.codigo, e.detalle)
    if e.codigo == 503 or e.codigo >= 500:
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                             "El servicio de inventario no está disponible; intenta de nuevo")
    return HTTPException(status.HTTP_502_BAD_GATEWAY,
                         f"Respuesta inesperada de inventario ({e.codigo})")


def _puede_ver(usuario: UsuarioToken, venta: Venta) -> bool:
    return usuario.rol == "admin" or venta.vendedor_id == usuario.id


# ---------------------------------------------------------------------
# Registrar una venta
# ---------------------------------------------------------------------
@router.post("", response_model=VentaOut, status_code=status.HTTP_201_CREATED)
def crear_venta(
    datos: VentaCrearIn,
    usuario: UsuarioToken = Depends(vendedor_o_admin),
    db: Session = Depends(get_db),
):
    if datos.cliente_id is not None and db.get(Cliente, datos.cliente_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El cliente indicado no existe")

    # Si el mismo producto viene dos veces, se suma en un solo renglón
    pedido: dict[int, int] = defaultdict(int)
    for it in datos.items:
        pedido[it.producto_id] += it.cantidad

    # 1) Precio y nombre salen del catálogo, nunca del cliente
    lineas = []
    try:
        for pid, cantidad in sorted(pedido.items()):
            p = inventario.obtener_producto(pid, usuario.token)
            if not p["activo"]:
                raise HTTPException(status.HTTP_409_CONFLICT,
                                    f"El producto {pid} no está disponible para la venta")
            precio = Decimal(str(p["precio"])).quantize(CENTAVOS)
            lineas.append(DetalleVenta(
                producto_id=pid, nombre_producto=p["nombre"], categoria=p["categoria"],
                cantidad=cantidad, precio_unitario=precio, subtotal=precio * cantidad))
    except ErrorInventario as e:
        raise _error_http(e)

    # 2) Armar la venta sin confirmarla todavía
    venta = Venta(cliente_id=datos.cliente_id, vendedor_id=usuario.id, fecha=func.now(),
                  total=sum((l.subtotal for l in lineas), Decimal("0")),
                  estado="COMPLETADA", detalle=lineas)
    db.add(venta)
    db.flush()

    # 3) Descontar stock; si no se puede, se descarta todo
    try:
        inventario.descontar(
            venta.id, [{"producto_id": l.producto_id, "cantidad": l.cantidad} for l in lineas],
            usuario.token)
    except ErrorInventario as e:
        db.rollback()
        raise _error_http(e)

    venta_id = venta.id
    try:
        db.commit()
        VENTAS_REGISTRADAS.inc()
    except Exception:
        log.exception("Inventario descontó stock para la venta #%s pero no se pudo guardar", venta_id)
        db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            f"No se pudo guardar la venta; avisa a un administrador (ref. {venta_id})")
    db.refresh(venta)
    return _completa(venta)


# ---------------------------------------------------------------------
# Exportación para analítica
# ---------------------------------------------------------------------
# IMPORTANTE: esta ruta va ANTES de "/{venta_id}", si no FastAPI intentaría
# leer la palabra "exportacion" como un número de venta.
@router.get("/exportacion", response_model=PaginaExportacion)
def exportar_ventas(
    despues_de: int = Query(0, ge=0, description="Devuelve ventas con id mayor a este"),
    limite: int = Query(500, ge=1, le=1000),
    _admin: UsuarioToken = Depends(solo_admin),
    db: Session = Depends(get_db),
):
    """Ventas COMPLETADAS con todos sus renglones, para que servicio-analitica
    recalcule sus resúmenes. Se pagina "por id" (no por desplazamiento): así, si
    mientras se exporta se registra o anula una venta, no se repiten ni se saltan filas."""
    ventas = db.scalars(
        select(Venta).options(lazyload(Venta.cliente))  # el cliente no hace falta aquí
        .where(Venta.estado == "COMPLETADA", Venta.id > despues_de)
        .order_by(Venta.id).limit(limite)
    ).unique().all()
    items = [VentaExportadaOut(
        id=v.id, fecha=v.fecha, vendedor_id=v.vendedor_id, total=float(v.total),
        items=[DetalleOut(producto_id=d.producto_id, nombre_producto=d.nombre_producto,
                          categoria=d.categoria, cantidad=d.cantidad,
                          precio_unitario=float(d.precio_unitario), subtotal=float(d.subtotal))
               for d in v.detalle]) for v in ventas]
    return PaginaExportacion(items=items, siguiente=ventas[-1].id if len(ventas) == limite else None)


# ---------------------------------------------------------------------
# Consultar
# ---------------------------------------------------------------------
@router.get("", response_model=PaginaVentas)
def listar_ventas(
    estado: Optional[Literal["COMPLETADA", "ANULADA"]] = None,
    cliente_id: Optional[int] = None,
    vendedor_id: Optional[int] = Query(None, description="Solo administrador; un vendedor siempre ve las suyas"),
    desde: Optional[date] = Query(None, description="Fecha inicial (inclusive), AAAA-MM-DD"),
    hasta: Optional[date] = Query(None, description="Fecha final (inclusive), AAAA-MM-DD"),
    limite: int = Query(20, ge=1, le=100),
    desplazamiento: int = Query(0, ge=0),
    usuario: UsuarioToken = Depends(vendedor_o_admin),
    db: Session = Depends(get_db),
):
    """El administrador ve todas las ventas; el vendedor solo las suyas."""
    if usuario.rol == "vendedor":
        vendedor_id = usuario.id

    consulta = select(Venta).options(lazyload(Venta.detalle))  # el listado no necesita las líneas
    if estado:
        consulta = consulta.where(Venta.estado == estado)
    if cliente_id is not None:
        consulta = consulta.where(Venta.cliente_id == cliente_id)
    if vendedor_id is not None:
        consulta = consulta.where(Venta.vendedor_id == vendedor_id)
    if desde:
        consulta = consulta.where(Venta.fecha >= datetime.combine(desde, time.min))
    if hasta:
        consulta = consulta.where(Venta.fecha < datetime.combine(hasta + timedelta(days=1), time.min))

    total = db.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    filas = db.scalars(consulta.order_by(Venta.fecha.desc(), Venta.id.desc())
                       .limit(limite).offset(desplazamiento)).unique().all()
    return PaginaVentas(total=total, limite=limite, desplazamiento=desplazamiento,
                        items=[_resumen(v) for v in filas])


@router.get("/{venta_id}", response_model=VentaOut)
def obtener_venta(
    venta_id: int,
    usuario: UsuarioToken = Depends(vendedor_o_admin),
    db: Session = Depends(get_db),
):
    venta = db.get(Venta, venta_id)
    # Para un vendedor, la venta de otro "no existe" (no se le revela nada)
    if venta is None or not _puede_ver(usuario, venta):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Venta no encontrada")
    return _completa(venta)


# ---------------------------------------------------------------------
# Anular
# ---------------------------------------------------------------------
@router.post("/{venta_id}/anular", response_model=AnulacionOut)
def anular_venta(
    venta_id: int,
    admin: UsuarioToken = Depends(solo_admin),
    db: Session = Depends(get_db),
):
    """Marca la venta como ANULADA y devuelve las unidades al inventario."""
    # Se bloquea la fila: si dos anulaciones llegan a la vez, la segunda espera
    # y luego ve que ya está anulada (no se devuelve el stock dos veces).
    venta = db.scalar(select(Venta).where(Venta.id == venta_id).with_for_update(of=Venta))
    if venta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Venta no encontrada")
    if venta.estado == "ANULADA":
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "La venta ya está anulada")

    reintegrar = venta.codigo_origen is None  # las históricas nunca descontaron stock aquí
    if reintegrar:
        try:
            inventario.devolver(
                venta.id, [{"producto_id": d.producto_id, "cantidad": d.cantidad} for d in venta.detalle],
                admin.token)
        except ErrorInventario as e:
            db.rollback()
            raise _error_http(e)

    venta.estado = "ANULADA"
    try:
        db.commit()
    except Exception:
        log.exception("Inventario devolvió stock de la venta #%s pero no se pudo marcar anulada", venta_id)
        db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            f"No se pudo guardar la anulación; avisa a un administrador (ref. {venta_id})")
    db.refresh(venta)
    return AnulacionOut(**_completa(venta).model_dump(), stock_reintegrado=reintegrar)
