"""
Clientes de la ferretería. Los pueden consultar y registrar vendedores y administradores.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import UsuarioToken, requiere_roles
from ..models import Cliente
from ..schemas import ClienteIn, ClienteOut, PaginaClientes

router = APIRouter(prefix="/api/ventas/clientes", tags=["Clientes"])

vendedor_o_admin = requiere_roles("admin", "vendedor")


def _a_out(c: Cliente) -> ClienteOut:
    return ClienteOut(id=c.id, nombre=c.nombre, correo=c.correo, ciudad=c.ciudad)


@router.get("", response_model=PaginaClientes)
def listar_clientes(
    q: Optional[str] = Query(None, max_length=100, description="Texto a buscar en nombre o correo"),
    limite: int = Query(20, ge=1, le=100),
    desplazamiento: int = Query(0, ge=0),
    _usuario: UsuarioToken = Depends(vendedor_o_admin),
    db: Session = Depends(get_db),
):
    consulta = select(Cliente)
    if q:
        consulta = consulta.where(or_(Cliente.nombre.icontains(q, autoescape=True),
                                      Cliente.correo.icontains(q, autoescape=True)))
    total = db.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    filas = db.scalars(consulta.order_by(Cliente.nombre, Cliente.id)
                       .limit(limite).offset(desplazamiento)).all()
    return PaginaClientes(total=total, limite=limite, desplazamiento=desplazamiento,
                          items=[_a_out(c) for c in filas])


@router.get("/{cliente_id}", response_model=ClienteOut)
def obtener_cliente(
    cliente_id: int,
    _usuario: UsuarioToken = Depends(vendedor_o_admin),
    db: Session = Depends(get_db),
):
    cliente = db.get(Cliente, cliente_id)
    if cliente is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente no encontrado")
    return _a_out(cliente)


@router.post("", response_model=ClienteOut, status_code=status.HTTP_201_CREATED)
def crear_cliente(
    datos: ClienteIn,
    _usuario: UsuarioToken = Depends(vendedor_o_admin),
    db: Session = Depends(get_db),
):
    correo = datos.correo.lower() if datos.correo else None
    if correo and db.scalar(select(Cliente.id).where(func.lower(Cliente.correo) == correo).limit(1)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un cliente con ese correo")
    cliente = Cliente(nombre=datos.nombre, correo=correo, ciudad=datos.ciudad)
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return _a_out(cliente)
