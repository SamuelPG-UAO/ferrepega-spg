"""
Consultas de los dashboards.

 - Administrador: todo (resumen, mensual, productos, categorías, vendedores).
 - Vendedor: solo sus propias ventas (/ventas-diarias).
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import UsuarioToken, requiere_roles
from ..models import (Actualizacion, TopProducto, VentaCategoria, VentaMensual,
                      VentaVendedor)
from ..schemas import (Agrupar, CategoriaOut, OrdenarProductos, ResumenOut,
                       TopProductoOut, VendedorTotalOut, VentaDiariaOut,
                       VentaMensualOut)

router = APIRouter(prefix="/api/analitica", tags=["Dashboards"])

solo_admin = requiere_roles("admin")
vendedor_o_admin = requiere_roles("admin", "vendedor")


def _validar_rango(desde: Optional[date], hasta: Optional[date]):
    if desde and hasta and desde > hasta:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "'desde' no puede ser posterior a 'hasta'")


@router.get("/resumen", response_model=ResumenOut)
def resumen(_admin: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    """Cifras generales para las tarjetas del dashboard."""
    total, pedidos = db.execute(
        select(func.coalesce(func.sum(VentaMensual.total_ventas), 0),
               func.coalesce(func.sum(VentaMensual.num_pedidos), 0))).one()
    unidades = db.scalar(select(func.coalesce(func.sum(VentaCategoria.unidades), 0)))
    ultima = db.scalar(select(func.max(Actualizacion.fecha)))
    return ResumenOut(
        total_ventas=float(total), num_pedidos=int(pedidos), unidades=int(unidades),
        ticket_promedio=round(float(total) / pedidos, 2) if pedidos else 0.0,
        actualizado_en=ultima)


@router.get("/ventas-mensuales", response_model=list[VentaMensualOut])
def ventas_mensuales(
    anio: Optional[int] = Query(None, ge=2000, le=2100),
    _admin: UsuarioToken = Depends(solo_admin),
    db: Session = Depends(get_db),
):
    """Ventas por mes, en orden cronológico (para la gráfica de líneas)."""
    consulta = select(VentaMensual).order_by(VentaMensual.anio, VentaMensual.mes)
    if anio is not None:
        consulta = consulta.where(VentaMensual.anio == anio)
    return [VentaMensualOut(anio=m.anio, mes=m.mes, total_ventas=float(m.total_ventas),
                            num_pedidos=m.num_pedidos) for m in db.scalars(consulta)]


@router.get("/top-productos", response_model=list[TopProductoOut])
def top_productos(
    limite: int = Query(10, ge=1, le=50),
    ordenar_por: OrdenarProductos = "ingresos",
    _admin: UsuarioToken = Depends(solo_admin),
    db: Session = Depends(get_db),
):
    columna = TopProducto.ingresos if ordenar_por == "ingresos" else TopProducto.unidades
    filas = db.scalars(select(TopProducto)
                       .order_by(columna.desc(), TopProducto.producto_id).limit(limite))
    return [TopProductoOut(producto_id=p.producto_id, nombre=p.nombre, unidades=p.unidades,
                           ingresos=float(p.ingresos)) for p in filas]


@router.get("/ventas-por-categoria", response_model=list[CategoriaOut])
def ventas_por_categoria(_admin: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    filas = db.scalars(select(VentaCategoria).order_by(VentaCategoria.total_ventas.desc(),
                                                       VentaCategoria.categoria)).all()
    gran_total = sum(float(c.total_ventas) for c in filas)
    return [CategoriaOut(categoria=c.categoria, total_ventas=float(c.total_ventas),
                         unidades=c.unidades,
                         porcentaje=round(float(c.total_ventas) * 100 / gran_total, 2) if gran_total else 0.0)
            for c in filas]


@router.get("/ventas-por-vendedor", response_model=list[VendedorTotalOut])
def ventas_por_vendedor(
    desde: Optional[date] = Query(None, description="AAAA-MM-DD (inclusive)"),
    hasta: Optional[date] = Query(None, description="AAAA-MM-DD (inclusive)"),
    _admin: UsuarioToken = Depends(solo_admin),
    db: Session = Depends(get_db),
):
    """Ranking de vendedores en un rango de fechas (sin rango = todo el historial)."""
    _validar_rango(desde, hasta)
    consulta = (select(VentaVendedor.vendedor_id,
                       func.sum(VentaVendedor.total_ventas), func.sum(VentaVendedor.num_ventas))
                .group_by(VentaVendedor.vendedor_id))
    if desde:
        consulta = consulta.where(VentaVendedor.fecha >= desde)
    if hasta:
        consulta = consulta.where(VentaVendedor.fecha <= hasta)
    filas = db.execute(consulta.order_by(func.sum(VentaVendedor.total_ventas).desc(),
                                         VentaVendedor.vendedor_id)).all()
    return [VendedorTotalOut(vendedor_id=v, total_ventas=float(t), num_ventas=int(n))
            for v, t, n in filas]


@router.get("/ventas-diarias", response_model=list[VentaDiariaOut])
def ventas_diarias(
    vendedor_id: Optional[int] = Query(None, description="Solo administrador; un vendedor siempre ve lo suyo"),
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    agrupar: Agrupar = "mes",
    limite: int = Query(400, ge=1, le=2000, description="Máximo de puntos; se conservan los más recientes"),
    usuario: UsuarioToken = Depends(vendedor_o_admin),
    db: Session = Depends(get_db),
):
    """Serie de ventas en el tiempo. El vendedor ve únicamente la suya;
    el administrador puede filtrar por vendedor o ver el total de todos."""
    _validar_rango(desde, hasta)
    if usuario.rol == "vendedor":
        vendedor_id = usuario.id

    if agrupar == "mes":
        periodo = func.date_trunc("month", VentaVendedor.fecha).cast(VentaVendedor.fecha.type)
    else:
        periodo = VentaVendedor.fecha
    consulta = select(periodo.label("periodo"), func.sum(VentaVendedor.total_ventas),
                      func.sum(VentaVendedor.num_ventas)).group_by(periodo)
    if vendedor_id is not None:
        consulta = consulta.where(VentaVendedor.vendedor_id == vendedor_id)
    if desde:
        consulta = consulta.where(VentaVendedor.fecha >= desde)
    if hasta:
        consulta = consulta.where(VentaVendedor.fecha <= hasta)

    # Se toman los más recientes y luego se devuelven en orden cronológico
    filas = db.execute(consulta.order_by(periodo.desc()).limit(limite)).all()
    return [VentaDiariaOut(fecha=f, vendedor_id=vendedor_id, total_ventas=float(t), num_ventas=int(n))
            for f, t, n in reversed(filas)]
