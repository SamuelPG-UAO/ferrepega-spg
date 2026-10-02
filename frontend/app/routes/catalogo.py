"""
Catálogo de productos: lo ven todos los roles.
"""
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, render_template, request

from .. import api
from ..seguridad import login_required

bp = Blueprint("catalogo", __name__)
POR_PAGINA = 20


def numero(texto):
    """Texto -> número positivo, o None si está vacío o no es un número."""
    if not texto:
        return None
    try:
        v = Decimal(texto.replace(",", ".").strip())
    except InvalidOperation:
        return None
    return str(v) if v >= 0 else None


def parametros_busqueda():
    """Lee los filtros de la URL y los convierte al formato que espera el API."""
    a = request.args
    filtros = {
        "q": a.get("q", "").strip(),
        "categoria_id": a.get("categoria_id", ""),
        "disponible": a.get("disponible", ""),
        "precio_min": a.get("precio_min", "").strip(),
        "precio_max": a.get("precio_max", "").strip(),
        "ordenar_por": a.get("ordenar_por", "nombre") if a.get("ordenar_por") in ("nombre", "precio", "stock") else "nombre",
        "descendente": a.get("descendente") == "true",
    }
    for clave in ("precio_min", "precio_max"):
        if filtros[clave] and numero(filtros[clave]) is None:
            flash(f"El {'precio mínimo' if clave == 'precio_min' else 'precio máximo'} debe ser un número.", "aviso")
            filtros[clave] = ""
    try:
        despl = max(int(a.get("desplazamiento", 0)), 0)
    except ValueError:
        despl = 0
    return filtros, despl


def consultar_productos(filtros, desplazamiento, **extra):
    return api.get(
        "/api/inventario/productos",
        q=filtros["q"], categoria_id=filtros["categoria_id"],
        disponible={"si": "true", "no": "false"}.get(filtros["disponible"]),
        precio_min=numero(filtros["precio_min"]), precio_max=numero(filtros["precio_max"]),
        ordenar_por=filtros["ordenar_por"], descendente="true" if filtros["descendente"] else None,
        limite=POR_PAGINA, desplazamiento=desplazamiento, **extra)


@bp.get("/catalogo")
@login_required
def lista():
    filtros, despl = parametros_busqueda()
    pagina = consultar_productos(filtros, despl)
    categorias = api.get("/api/inventario/categorias")
    return render_template("catalogo/lista.html", filtros=filtros, pagina=pagina, categorias=categorias)


@bp.get("/catalogo/<int:producto_id>")
@login_required
def detalle(producto_id):
    producto = api.get(f"/api/inventario/productos/{producto_id}")
    return render_template("catalogo/detalle.html", p=producto)
