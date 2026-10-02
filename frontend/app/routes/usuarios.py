"""
Usuarios del sistema (solo administrador): crear, cambiar rol, activar/desactivar, restablecer contraseña.
"""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import api
from ..seguridad import roles_required, usuario_actual

bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")
POR_PAGINA = 20
ROLES = ("admin", "vendedor", "cliente")


@bp.get("")
@roles_required("admin")
def lista():
    a = request.args
    rol = a.get("rol", "") if a.get("rol") in ROLES else ""
    estado = a.get("estado", "") if a.get("estado") in ("activos", "inactivos") else ""
    try:
        despl = max(int(a.get("desplazamiento", 0)), 0)
    except ValueError:
        despl = 0
    # El back devuelve una lista sin total: se pide uno de más para saber si hay otra página
    filas = api.get("/api/auth/usuarios", rol=rol,
                    activo={"activos": "true", "inactivos": "false"}.get(estado),
                    limite=POR_PAGINA + 1, desplazamiento=despl)
    return render_template("usuarios/lista.html", filas=filas[:POR_PAGINA], hay_mas=len(filas) > POR_PAGINA,
                           despl=despl, por_pagina=POR_PAGINA, rol=rol, estado=estado, yo=usuario_actual()["id"])


@bp.post("/nuevo")
@roles_required("admin")
def nuevo():
    f = request.form
    cuerpo = {"nombre": f.get("nombre", "").strip(), "correo": f.get("correo", "").strip(),
              "contrasena": f.get("contrasena", ""), "rol": f.get("rol", "vendedor")}
    try:
        u = api.post("/api/auth/usuarios", cuerpo)
    except api.ApiError as e:
        flash(e.mensaje, "error")
    else:
        flash(f"Usuario «{u['nombre']}» creado como {u['rol']}.", "ok")
    return redirect(url_for("usuarios.lista"))


@bp.post("/<int:usuario_id>/editar")
@roles_required("admin")
def editar(usuario_id):
    f = request.form
    cuerpo = {"nombre": f.get("nombre", "").strip(), "rol": f.get("rol"), "activo": f.get("activo") == "1"}
    if f.get("contrasena"):
        cuerpo["contrasena"] = f["contrasena"]
    try:
        api.put(f"/api/auth/usuarios/{usuario_id}", cuerpo)
    except api.ApiError as e:
        flash(e.mensaje, "error")
    else:
        flash("Cambios guardados.", "ok")
    return redirect(request.form.get("volver") if (request.form.get("volver") or "").startswith("/usuarios") else url_for("usuarios.lista"))
