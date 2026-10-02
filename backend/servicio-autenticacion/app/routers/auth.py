"""
Endpoints públicos y de sesión: salud, registro, login y perfil.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import usuario_actual
from ..models import Usuario
from ..schemas import LoginIn, RegistroIn, TokenOut, UsuarioOut
from ..security import (HASH_FALSO, cifrar_contrasena, crear_token,
                        verificar_contrasena)

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.get("/salud")
def salud(db: Session = Depends(get_db)):
    """Comprueba que el servicio y su base de datos responden."""
    db.execute(text("SELECT 1"))
    return {"servicio": "servicio-autenticacion", "estado": "ok"}


@router.post("/registro", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def registro(datos: RegistroIn, db: Session = Depends(get_db)):
    """Crea una cuenta nueva. Siempre con rol 'cliente': nadie puede
    hacerse administrador desde el registro público."""
    correo = datos.correo.strip().lower()

    if db.scalar(select(Usuario).where(Usuario.correo == correo)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese correo")

    usuario = Usuario(
        nombre=datos.nombre.strip(),
        correo=correo,
        contrasena_hash=cifrar_contrasena(datos.contrasena),
        rol="cliente",
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:  # dos registros simultáneos con el mismo correo
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese correo")
    db.refresh(usuario)
    return usuario


@router.post("/login", response_model=TokenOut)
def login(datos: LoginIn, db: Session = Depends(get_db)):
    """Valida correo y contraseña y entrega un token JWT."""
    usuario = db.scalar(select(Usuario).where(Usuario.correo == datos.correo.strip().lower()))

    # Siempre se verifica una contraseña (la real o el hash falso), y el
    # mensaje de error es el mismo si falla el correo o la contraseña.
    clave_correcta = verificar_contrasena(
        datos.contrasena, usuario.contrasena_hash if usuario else HASH_FALSO
    )
    if usuario is None or not clave_correcta:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos")

    if not usuario.activo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Usuario desactivado")

    token, segundos = crear_token(usuario)
    return TokenOut(
        access_token=token,
        expires_in=segundos,
        usuario=UsuarioOut.model_validate(usuario),
    )


@router.get("/yo", response_model=UsuarioOut)
def yo(usuario: Usuario = Depends(usuario_actual)):
    """Devuelve los datos del usuario que hizo la petición."""
    return usuario
