"""
Gestión de usuarios: solo para el rol administrador.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import requiere_roles
from ..models import Usuario
from ..schemas import Rol, UsuarioActualizarIn, UsuarioCrearIn, UsuarioOut
from ..security import cifrar_contrasena

router = APIRouter(
    prefix="/api/auth/usuarios",
    tags=["Gestión de usuarios (solo admin)"],
)

solo_admin = requiere_roles("admin")


@router.get("", response_model=list[UsuarioOut])
def listar(
    rol: Optional[Rol] = None,
    activo: Optional[bool] = None,
    limite: int = Query(50, ge=1, le=200),
    desplazamiento: int = Query(0, ge=0),
    _admin: Usuario = Depends(solo_admin),
    db: Session = Depends(get_db),
):
    """Lista usuarios, con filtros opcionales por rol y estado, y paginación."""
    consulta = select(Usuario).order_by(Usuario.id)
    if rol is not None:
        consulta = consulta.where(Usuario.rol == rol)
    if activo is not None:
        consulta = consulta.where(Usuario.activo == activo)
    return db.scalars(consulta.limit(limite).offset(desplazamiento)).all()


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear(
    datos: UsuarioCrearIn,
    _admin: Usuario = Depends(solo_admin),
    db: Session = Depends(get_db),
):
    """Crea un usuario con el rol indicado (por defecto, vendedor)."""
    correo = datos.correo.strip().lower()
    if db.scalar(select(Usuario).where(Usuario.correo == correo)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese correo")

    usuario = Usuario(
        nombre=datos.nombre.strip(),
        correo=correo,
        contrasena_hash=cifrar_contrasena(datos.contrasena),
        rol=datos.rol,
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese correo")
    db.refresh(usuario)
    return usuario


@router.put("/{usuario_id}", response_model=UsuarioOut)
def actualizar(
    usuario_id: int,
    datos: UsuarioActualizarIn,
    admin: Usuario = Depends(solo_admin),
    db: Session = Depends(get_db),
):
    """Edita nombre, rol, contraseña o estado (activar/desactivar) de un usuario."""
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")

    # Solo se aplican los campos enviados (y que no sean nulos)
    cambios = {k: v for k, v in datos.model_dump(exclude_unset=True).items() if v is not None}

    # Evita que el administrador se deje a sí mismo sin acceso
    if usuario.id == admin.id and (
        cambios.get("activo") is False or cambios.get("rol", "admin") != "admin"
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "No puedes desactivarte ni quitarte el rol de administrador")

    if "contrasena" in cambios:
        usuario.contrasena_hash = cifrar_contrasena(cambios.pop("contrasena"))
    for campo, valor in cambios.items():
        setattr(usuario, campo, valor)

    db.commit()
    db.refresh(usuario)
    return usuario
