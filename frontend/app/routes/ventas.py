"""
Ventas: listado, registrar una venta nueva, ver el detalle y anular (solo administrador).
"""
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from .. import api
from ..formatos import cop
from ..seguridad import login_required, roles_required, usuario_actual

bp = Blueprint("ventas", __name__)
POR_PAGINA = 20
staff = roles_required("admin", "vendedor")


def _entero_o_none(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


@bp.get("/ventas")
@staff
def lista():
    u = usuario_actual()
    a = request.args
    filtros = {"estado": a.get("estado", ""), "desde": a.get("desde", ""), "hasta": a.get("hasta", ""),
               "vendedor_id": a.get("vendedor_id", "") if u["rol"] == "admin" else ""}
    despl = max(_entero_o_none(a.get("desplazamiento")) or 0, 0)
    pagina = api.get("/api/ventas", limite=POR_PAGINA, desplazamiento=despl,
                     estado=filtros["estado"] if filtros["estado"] in ("COMPLETADA", "ANULADA") else None,
                     desde=filtros["desde"], hasta=filtros["hasta"], vendedor_id=_entero_o_none(filtros["vendedor_id"]))
    equipo = {}
    if u["rol"] == "admin":
        equipo = {x["id"]: x["nombre"] for x in api.get("/api/auth/usuarios", limite=200) if x["rol"] in ("vendedor", "admin")}
    return render_template("ventas/lista.html", pagina=pagina, filtros=filtros, equipo=equipo)


@bp.get("/ventas/<int:venta_id>")
@staff
def detalle(venta_id):
    venta = api.get(f"/api/ventas/{venta_id}")
    vendedor = None
    if usuario_actual()["rol"] == "admin":
        vendedor = {x["id"]: x["nombre"] for x in api.get("/api/auth/usuarios", limite=200)}.get(venta["vendedor_id"])
    elif venta["vendedor_id"] == usuario_actual()["id"]:
        vendedor = usuario_actual()["nombre"]
    return render_template("ventas/detalle.html", v=venta, vendedor=vendedor)


@bp.post("/ventas/<int:venta_id>/anular")
@roles_required("admin")
def anular(venta_id):
    try:
        r = api.post(f"/api/ventas/{venta_id}/anular")
    except api.ApiError as e:
        flash(e.mensaje, "error")
    else:
        if r["stock_reintegrado"]:
            flash(f"La venta #{venta_id} quedó anulada y las unidades volvieron al inventario.", "ok")
        else:
            flash(f"La venta #{venta_id} quedó anulada. Es una venta histórica importada: no devuelve unidades al inventario.", "ok")
    return redirect(url_for("ventas.detalle", venta_id=venta_id))


# ---------------------------------------------------------------------
# Nueva venta: la pantalla trabaja con estos tres servicios JSON (los usa venta_nueva.js)
# ---------------------------------------------------------------------
@bp.get("/ventas/nueva")
@staff
def nueva():
    return render_template("ventas/nueva.html")


@bp.get("/ventas/buscar-productos")
@staff
def buscar_productos():
    q = request.args.get("q", "").strip()
    pagina = api.get("/api/inventario/productos", q=q, disponible="true", limite=12, ordenar_por="nombre")
    return jsonify([{"id": p["id"], "nombre": p["nombre"], "categoria": p["categoria"],
                     "precio": p["precio"], "stock": p["stock"]} for p in pagina["items"]])


@bp.get("/ventas/buscar-clientes")
@staff
def buscar_clientes():
    q = request.args.get("q", "").strip()
    pagina = api.get("/api/ventas/clientes", q=q, limite=8)
    return jsonify([{"id": c["id"], "nombre": c["nombre"], "correo": c.get("correo"), "ciudad": c.get("ciudad")}
                    for c in pagina["items"]])


@bp.post("/ventas/nueva")
@staff
def crear():
    """Recibe el carrito como JSON, lo envía al back y responde con el id de la venta
    (o con un mensaje de error legible, p. ej. si no alcanza el stock)."""
    datos = request.get_json(silent=True) or {}
    items = [{"producto_id": int(i["producto_id"]), "cantidad": int(i["cantidad"])}
             for i in datos.get("items", []) if str(i.get("producto_id", "")).isdigit() and int(i.get("cantidad", 0)) > 0]
    if not items:
        return jsonify({"ok": False, "mensaje": "Agrega al menos un producto a la venta."}), 400
    try:
        venta = api.post("/api/ventas", {"cliente_id": _entero_o_none(datos.get("cliente_id")), "items": items})
    except api.SesionVencida:
        return jsonify({"ok": False, "mensaje": "Tu sesión venció. Recarga la página e inicia sesión de nuevo."}), 401
    except api.ApiError as e:
        return jsonify({"ok": False, "mensaje": e.mensaje}), (e.codigo if e.codigo in (404, 409, 422, 503) else 502)
    flash(f"Venta #{venta['id']} registrada por {cop(venta['total'])}.", "ok")
    return jsonify({"ok": True, "id": venta["id"], "destino": url_for("ventas.detalle", venta_id=venta["id"])})
