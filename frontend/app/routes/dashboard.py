"""
Paneles de ventas: el administrador ve el negocio completo; el vendedor, lo suyo.
"""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import api
from ..seguridad import login_required, roles_required, usuario_actual

bp = Blueprint("dashboard", __name__)


def nombres_de_usuarios():
    """id -> nombre de todos los usuarios (solo el administrador puede pedirlo)."""
    usuarios = api.get("/api/auth/usuarios", limite=200)
    return {u["id"]: u["nombre"] for u in usuarios}


@bp.get("/panel")
@login_required
def inicio():
    u = usuario_actual()
    if u["rol"] == "admin":
        return panel_admin()
    if u["rol"] == "vendedor":
        return panel_vendedor(u)
    return redirect(url_for("catalogo.lista"))


def panel_admin():
    metrica = "unidades" if request.args.get("metrica") == "unidades" else "ingresos"
    resumen = api.get("/api/analitica/resumen")
    datos = {"resumen": resumen}
    if resumen["actualizado_en"]:
        nombres = nombres_de_usuarios()
        mensuales = api.get("/api/analitica/ventas-mensuales")
        top = api.get("/api/analitica/top-productos", limite=8, ordenar_por=metrica)
        categorias = api.get("/api/analitica/ventas-por-categoria")
        vendedores = api.get("/api/analitica/ventas-por-vendedor")
        for v in vendedores:
            v["nombre"] = nombres.get(v["vendedor_id"], f"Vendedor {v['vendedor_id']}")
        datos.update(mensuales=mensuales, top=top, categorias=categorias, vendedores=vendedores)
    bajo = api.get("/api/inventario/stock/bajo", limite=5)
    return render_template("dashboard/admin.html", metrica=metrica, bajo=bajo, **datos)


def panel_vendedor(u):
    serie = api.get("/api/analitica/ventas-diarias", agrupar="mes")
    ultimas = api.get("/api/ventas", limite=6)
    total = sum(p["total_ventas"] for p in serie)
    cantidad = sum(p["num_ventas"] for p in serie)
    return render_template("dashboard/vendedor.html", serie=serie, ultimas=ultimas["items"],
                           total=total, cantidad=cantidad,
                           ticket=(total / cantidad) if cantidad else 0)


@bp.post("/panel/actualizar")
@roles_required("admin")
def actualizar():
    try:
        r = api.post("/api/analitica/actualizar")
    except api.ApiError as e:
        if e.codigo == 409:
            flash("Ya hay un recálculo en curso. Espera unos segundos y recarga.", "aviso")
        else:
            flash(e.mensaje, "error")
    else:
        flash(f"Datos actualizados: se procesaron {r['ventas_procesadas']} ventas en {r['segundos']} s.", "ok")
    return redirect(url_for("dashboard.inicio"))
