"""
Clientes de la ferretería: consultar y registrar (vendedor y administrador).
"""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import api
from ..seguridad import roles_required

bp = Blueprint("clientes", __name__)
POR_PAGINA = 20


@bp.get("/clientes")
@roles_required("admin", "vendedor")
def lista():
    q = request.args.get("q", "").strip()
    try:
        despl = max(int(request.args.get("desplazamiento", 0)), 0)
    except ValueError:
        despl = 0
    pagina = api.get("/api/ventas/clientes", q=q, limite=POR_PAGINA, desplazamiento=despl)
    return render_template("clientes/lista.html", pagina=pagina, q=q)


@bp.post("/clientes")
@roles_required("admin", "vendedor")
def crear():
    datos = {"nombre": request.form.get("nombre", "").strip(),
             "correo": request.form.get("correo", "").strip() or None,
             "ciudad": request.form.get("ciudad", "").strip() or None}
    try:
        c = api.post("/api/ventas/clientes", datos)
    except api.ApiError as e:
        flash(e.mensaje, "error")
    else:
        flash(f"Cliente «{c['nombre']}» registrado.", "ok")
    return redirect(url_for("clientes.lista"))
