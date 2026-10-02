"""
Inventario (solo administrador): productos, poco stock, movimientos y categorías.
"""
from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import api
from ..routes.catalogo import consultar_productos, numero, parametros_busqueda
from ..seguridad import roles_required

bp = Blueprint("inventario", __name__, url_prefix="/inventario")
solo_admin = roles_required("admin")
POR_PAGINA = 20


def volver(por_defecto="inventario.productos"):
    """Dirección a la que regresar tras guardar (solo dentro de /inventario)."""
    destino = request.form.get("volver", "")
    if destino.startswith("/inventario") and not urlparse(destino).netloc:
        return redirect(destino)
    return redirect(url_for(por_defecto))


def _int(valor):
    try:
        return int(str(valor).strip())
    except ValueError:
        return None


def _hecho(accion):
    """Ejecuta accion(); muestra el error si falla. Devuelve True si salió bien."""
    try:
        accion()
        return True
    except api.ApiError as e:
        flash(e.mensaje, "error")
        return False


# ---------------------------------------------------------------------
# Vistas
# ---------------------------------------------------------------------
@bp.get("")
@solo_admin
def productos():
    filtros, despl = parametros_busqueda()
    incluir = request.args.get("inactivos") == "1"
    pagina = consultar_productos(filtros, despl, incluir_inactivos="true" if incluir else None)
    categorias = api.get("/api/inventario/categorias")
    return render_template("inventario/productos.html", filtros=filtros, pagina=pagina,
                           categorias=categorias, incluir=incluir)


@bp.get("/bajo")
@solo_admin
def bajo():
    r = api.get("/api/inventario/stock/bajo", limite=200)
    return render_template("inventario/bajo.html", r=r)


@bp.get("/movimientos")
@solo_admin
def movimientos():
    a = request.args
    tipo = a.get("tipo", "") if a.get("tipo") in ("ENTRADA", "SALIDA", "AJUSTE") else ""
    despl = max(_int(a.get("desplazamiento", 0)) or 0, 0)
    # el back devuelve una lista; se pide uno de más para saber si hay página siguiente
    filas = api.get("/api/inventario/movimientos", tipo=tipo, producto_id=_int(a.get("producto_id", "")),
                    limite=POR_PAGINA + 1, desplazamiento=despl)
    hay_mas = len(filas) > POR_PAGINA
    equipo = {u["id"]: u["nombre"] for u in api.get("/api/auth/usuarios", limite=200)}
    return render_template("inventario/movimientos.html", filas=filas[:POR_PAGINA], tipo=tipo, despl=despl,
                           hay_mas=hay_mas, por_pagina=POR_PAGINA, equipo=equipo,
                           producto_id=a.get("producto_id", ""))


@bp.get("/categorias")
@solo_admin
def categorias():
    return render_template("inventario/categorias.html", categorias=api.get("/api/inventario/categorias"))


# ---------------------------------------------------------------------
# Acciones
# ---------------------------------------------------------------------
@bp.post("/producto/nuevo")
@solo_admin
def producto_nuevo():
    f = request.form
    precio = numero(f.get("precio", ""))
    if precio is None:
        flash("El precio debe ser un número mayor que cero.", "error")
        return volver()
    cuerpo = {"nombre": f.get("nombre", "").strip(), "descripcion": f.get("descripcion", "").strip() or None,
              "categoria_id": _int(f.get("categoria_id")), "precio": precio,
              "stock_inicial": _int(f.get("stock_inicial", "0")) or 0, "stock_minimo": _int(f.get("stock_minimo", "5")) or 0}
    if _hecho(lambda: api.post("/api/inventario/productos", cuerpo)):
        flash(f"Producto «{cuerpo['nombre']}» creado.", "ok")
    return volver()


@bp.post("/producto/<int:producto_id>/editar")
@solo_admin
def producto_editar(producto_id):
    f = request.form
    precio = numero(f.get("precio", ""))
    if precio is None:
        flash("El precio debe ser un número mayor que cero.", "error")
        return volver()
    cuerpo = {"nombre": f.get("nombre", "").strip(), "descripcion": f.get("descripcion", "").strip() or None,
              "categoria_id": _int(f.get("categoria_id")), "precio": precio,
              "stock_minimo": _int(f.get("stock_minimo", "")), "activo": f.get("activo") == "1"}
    if _hecho(lambda: api.put(f"/api/inventario/productos/{producto_id}", cuerpo)):
        flash("Cambios guardados.", "ok")
    return volver()


@bp.post("/producto/<int:producto_id>/estado")
@solo_admin
def producto_estado(producto_id):
    activar = request.form.get("activo") == "1"
    hecho = _hecho(lambda: api.put(f"/api/inventario/productos/{producto_id}", {"activo": True})
                   if activar else api.delete(f"/api/inventario/productos/{producto_id}"))
    if hecho:
        flash("Producto reactivado." if activar else "Producto desactivado: ya no aparece en el catálogo ni se puede vender.", "ok")
    return volver()


@bp.post("/stock")
@solo_admin
def stock():
    f = request.form
    cantidad = _int(f.get("cantidad", ""))
    if cantidad is None or cantidad == 0:
        flash("Escribe una cantidad distinta de cero.", "error")
        return volver()
    cuerpo = {"producto_id": _int(f.get("producto_id")), "tipo": f.get("tipo", "ENTRADA"), "cantidad": cantidad,
              "motivo": f.get("motivo", "").strip() or None}
    try:
        r = api.post("/api/inventario/movimientos", cuerpo)
    except api.ApiError as e:
        flash(e.mensaje, "error")
    else:
        flash(f"Stock actualizado: «{r['producto_nombre']}» ahora tiene {r['stock_actual']} unidades.", "ok")
    return volver()


@bp.post("/categoria/nueva")
@solo_admin
def categoria_nueva():
    nombre = request.form.get("nombre", "").strip()
    if _hecho(lambda: api.post("/api/inventario/categorias", {"nombre": nombre})):
        flash(f"Categoría «{nombre}» creada.", "ok")
    return redirect(url_for("inventario.categorias"))


@bp.post("/categoria/<int:categoria_id>/renombrar")
@solo_admin
def categoria_renombrar(categoria_id):
    nombre = request.form.get("nombre", "").strip()
    if _hecho(lambda: api.put(f"/api/inventario/categorias/{categoria_id}", {"nombre": nombre})):
        flash("Categoría renombrada.", "ok")
    return redirect(url_for("inventario.categorias"))


@bp.post("/categoria/<int:categoria_id>/eliminar")
@solo_admin
def categoria_eliminar(categoria_id):
    if _hecho(lambda: api.delete(f"/api/inventario/categorias/{categoria_id}")):
        flash("Categoría eliminada.", "ok")
    return redirect(url_for("inventario.categorias"))
