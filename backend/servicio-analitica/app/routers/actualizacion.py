"""
Recalcular los resúmenes (solo administrador).

Flujo: lee TODAS las ventas completadas desde servicio-ventas, las suma en
memoria y reemplaza las tablas de resumen en una sola transacción. Si algo falla
a la mitad, las tablas quedan como estaban (nunca a medias).
"""
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, insert, text
from sqlalchemy.orm import Session

from .. import ventas_cliente
from ..calculo import calcular
from ..database import get_db
from ..dependencies import UsuarioToken, requiere_roles
from ..models import (Actualizacion, TopProducto, VentaCategoria, VentaMensual,
                      VentaVendedor)
from ..schemas import ActualizacionOut
from ..ventas_cliente import ErrorVentas

log = logging.getLogger("servicio-analitica")

router = APIRouter(prefix="/api/analitica", tags=["Actualización"])

solo_admin = requiere_roles("admin")

CLAVE_BLOQUEO = 7001  # número cualquiera, igual para todas las copias del servicio


@router.post("/actualizar", response_model=ActualizacionOut)
def actualizar(admin: UsuarioToken = Depends(solo_admin), db: Session = Depends(get_db)):
    # Candado de PostgreSQL: si ya hay un recálculo en curso, este no arranca.
    # Se libera solo al terminar la transacción (commit o rollback).
    if not db.scalar(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": CLAVE_BLOQUEO}):
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya hay un recálculo en curso")

    inicio = time.monotonic()
    try:
        resultado = calcular(ventas_cliente.leer_ventas(admin.token))
    except ErrorVentas as e:
        db.rollback()
        if e.codigo in (401, 403):
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "servicio-ventas rechazó la consulta")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "El servicio de ventas no está disponible; intenta de nuevo")

    # Reemplazo completo, todo en la misma transacción
    for modelo in (VentaMensual, TopProducto, VentaCategoria, VentaVendedor):
        db.execute(delete(modelo))
    for modelo, clave in ((VentaMensual, "mensuales"), (TopProducto, "productos"),
                          (VentaCategoria, "categorias"), (VentaVendedor, "vendedores")):
        if resultado[clave]:
            db.execute(insert(modelo), resultado[clave])

    segundos = round(time.monotonic() - inicio, 2)
    registro = Actualizacion(ventas_procesadas=resultado["ventas_procesadas"],
                             segundos=segundos, usuario_id=admin.id)
    db.add(registro)
    db.commit()
    db.refresh(registro)
    log.info("Recálculo: %s ventas en %s s", resultado["ventas_procesadas"], segundos)

    return ActualizacionOut(
        ventas_procesadas=resultado["ventas_procesadas"], mensuales=len(resultado["mensuales"]),
        productos=len(resultado["productos"]), categorias=len(resultado["categorias"]),
        filas_vendedor=len(resultado["vendedores"]), segundos=segundos,
        actualizado_en=registro.fecha)
