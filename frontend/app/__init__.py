"""
Front de Ferrepega (Flask).

Páginas HTML renderizadas en el servidor; las gráficas usan Chart.js en el
navegador con los datos que Flask ya trae del back.
"""
from flask import Flask, flash, redirect, render_template, request, session, url_for
from markupsafe import Markup
from werkzeug.exceptions import HTTPException

from . import formatos, seguridad
from .api import ApiError, SesionVencida
from .config import Config


def create_app(config_extra=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_extra:
        app.config.update(config_extra)
    if not app.config["SECRET_KEY"]:
        raise RuntimeError(
            "Falta FERREPEGA_SECRET_KEY. Copia .env.example como .env y define una clave "
            "larga y aleatoria (instrucciones dentro del archivo).")

    # --- Filtros de plantilla ---------------------------------------------
    app.add_template_filter(formatos.cop, "cop")
    app.add_template_filter(formatos.cop_corto, "cop_corto")
    app.add_template_filter(formatos.entero, "entero")
    app.add_template_filter(formatos.fecha, "fecha")
    app.add_template_filter(formatos.fecha_hora, "fecha_hora")
    app.add_template_filter(formatos.fecha_iso, "fecha_iso")
    app.add_template_filter(formatos.mes_anio, "mes_anio")

    # --- Variables disponibles en todas las plantillas ---------------------
    @app.context_processor
    def contexto():
        usuario = seguridad.usuario_actual()
        return {
            "usuario": usuario,
            "rol_texto": seguridad.ROLES_TEXTO.get(usuario["rol"], "") if usuario else "",
            "menu": _menu(usuario["rol"], request.endpoint or "") if usuario else [],
            "csrf_input": lambda: Markup(
                f'<input type="hidden" name="csrf_token" value="{seguridad.token_csrf()}">'),
            "csrf_token": seguridad.token_csrf,
            "url_con": _url_con,
            "demo": app.config["DEMO"],
        }

    app.before_request(seguridad.verificar_csrf)

    @app.after_request
    def cabeceras_de_seguridad(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        # Solo se ejecuta JavaScript propio; nada de scripts en línea ni externos
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; frame-ancestors 'none'; form-action 'self'")
        if request.endpoint != "static":
            resp.headers["Cache-Control"] = "no-store"  # páginas con datos del usuario: no guardarlas
        return resp

    # --- Errores ----------------------------------------------------------
    @app.errorhandler(SesionVencida)
    def sesion_vencida(_e):
        seguridad.cerrar_sesion()
        flash("Tu sesión venció. Inicia sesión de nuevo.", "aviso")
        if request.method == "GET":
            return redirect(url_for("auth.login", siguiente=request.full_path.rstrip("?")))
        return redirect(url_for("auth.login"))

    @app.errorhandler(ApiError)
    def error_del_back(e):
        codigo = e.codigo if e.codigo in (403, 404, 409, 422, 503) else 502
        titulos = {403: "No tienes permiso", 404: "No encontrado", 503: "El servidor no responde"}
        return render_template("error.html", codigo=codigo, titulo=titulos.get(codigo, "No se pudo completar"),
                               mensaje=e.mensaje), codigo

    @app.errorhandler(HTTPException)
    def error_http(e):
        titulos = {400: "Solicitud no válida", 403: "No tienes permiso", 404: "Página no encontrada",
                   413: "La petición es demasiado grande"}
        mensajes = {403: "Tu rol no puede abrir esta página.",
                    404: "La dirección no existe o fue movida."}
        return render_template("error.html", codigo=e.code, titulo=titulos.get(e.code, "Ocurrió un error"),
                               mensaje=e.description if e.code == 400 else mensajes.get(e.code, e.description)), e.code

    @app.errorhandler(Exception)
    def error_interno(e):
        app.logger.exception("Error no controlado")
        return render_template("error.html", codigo=500, titulo="Algo salió mal",
                               mensaje="Ocurrió un error inesperado. Intenta de nuevo; si sigue pasando, avisa al administrador."), 500

    # --- Páginas ------------------------------------------------------------
    from .routes import auth, catalogo, clientes, dashboard, inventario, usuarios, ventas
    for modulo in (auth, catalogo, dashboard, ventas, clientes, inventario, usuarios):
        app.register_blueprint(modulo.bp)

    @app.get("/")
    def raiz():
        u = seguridad.usuario_actual()
        return redirect(seguridad.pagina_inicial(u["rol"]) if u else url_for("auth.login"))

    @app.get("/salud")
    def salud():
        return {"servicio": "ferrepega-front", "estado": "ok"}

    return app


def _menu(rol, endpoint_actual):
    """Entradas del menú lateral según el rol: dicts con destino, texto, ícono y si está activa."""
    def item(destino, texto, icono, *activos):
        # activa si estamos en su página o en alguna de sus páginas hijas (p. ej. el detalle)
        return {"destino": destino, "texto": texto, "icono": icono,
                "activo": endpoint_actual == destino or endpoint_actual in activos
                          or any(endpoint_actual.startswith(a) for a in activos if a.endswith("."))}

    catalogo = item("catalogo.lista", "Catálogo", "catalogo", "catalogo.detalle")
    if rol == "cliente":
        return [catalogo]
    entradas = [item("dashboard.inicio", "Panel", "panel"), catalogo,
                item("ventas.lista", "Ventas", "ventas", "ventas.detalle"),
                item("ventas.nueva", "Nueva venta", "mas"),
                item("clientes.lista", "Clientes", "clientes")]
    if rol == "admin":
        entradas += [item("inventario.productos", "Inventario", "inventario", "inventario."),
                     item("usuarios.lista", "Usuarios", "usuarios")]
    return entradas


def _url_con(**cambios):
    """URL de la página actual cambiando solo algunos parámetros (para paginar,
    ordenar o filtrar sin perder el resto). Un valor None quita el parámetro."""
    args = request.args.to_dict()
    for k, v in cambios.items():
        if v is None or v == "":
            args.pop(k, None)
        else:
            args[k] = v
    return url_for(request.endpoint, **{**(request.view_args or {}), **args})
