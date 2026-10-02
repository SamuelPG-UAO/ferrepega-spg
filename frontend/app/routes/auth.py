"""
Inicio de sesión, registro de clientes y cierre de sesión.
"""
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from .. import api, seguridad

bp = Blueprint("auth", __name__)


def _destino_seguro(destino: str) -> bool:
    """Solo se acepta volver a una dirección de este mismo sitio (evita redirecciones a páginas ajenas)."""
    p = urlparse(destino or "")
    return bool(destino) and destino.startswith("/") and not destino.startswith("//") and not p.netloc


@bp.route("/login", methods=["GET", "POST"])
def login():
    u = seguridad.usuario_actual()
    if u and request.method == "GET":
        return redirect(seguridad.pagina_inicial(u["rol"]))

    siguiente = request.values.get("siguiente", "")
    correo = ""
    if request.method == "POST":
        correo = request.form.get("correo", "").strip()
        contrasena = request.form.get("contrasena", "")
        if not correo or not contrasena:
            flash("Escribe tu correo y tu contraseña.", "error")
        else:
            try:
                respuesta = api.llamar("POST", "/api/auth/login", autenticado=False,
                                       json={"correo": correo, "contrasena": contrasena})
            except api.ApiError as e:
                flash(e.mensaje, "error")
            else:
                seguridad.iniciar_sesion(respuesta)
                if _destino_seguro(siguiente):
                    return redirect(siguiente)
                return redirect(seguridad.pagina_inicial(respuesta["usuario"]["rol"]))
    return render_template("login.html", correo=correo, siguiente=siguiente,
                           demo=current_app.config["DEMO"])


@bp.route("/registro", methods=["GET", "POST"])
def registro():
    if seguridad.usuario_actual():
        return redirect(url_for("raiz"))
    datos = {"nombre": "", "correo": ""}
    if request.method == "POST":
        datos = {"nombre": request.form.get("nombre", "").strip(), "correo": request.form.get("correo", "").strip()}
        contrasena = request.form.get("contrasena", "")
        if contrasena != request.form.get("confirmar", ""):
            flash("Las contraseñas no coinciden.", "error")
        else:
            try:
                api.llamar("POST", "/api/auth/registro", autenticado=False,
                           json={**datos, "contrasena": contrasena})
            except api.ApiError as e:
                flash(e.mensaje, "error")
            else:
                flash("Cuenta creada. Ya puedes iniciar sesión.", "ok")
                return redirect(url_for("auth.login"))
    return render_template("registro.html", **datos)


@bp.post("/salir")
def salir():
    seguridad.cerrar_sesion()
    flash("Cerraste sesión.", "ok")
    return redirect(url_for("auth.login"))
