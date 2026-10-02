"""
Sesión, permisos por rol y protección CSRF.

La sesión guarda (en una cookie firmada y HttpOnly) el token del usuario y sus
datos básicos. Los permisos que se aplican aquí son una comodidad de la
interfaz; la autoridad real es el back, que revalida token y rol en cada llamada.
"""
import hmac
import secrets
import time
from functools import wraps

from flask import abort, flash, redirect, request, session, url_for

ROLES_TEXTO = {"admin": "Administrador", "vendedor": "Vendedor", "cliente": "Cliente"}


def usuario_actual():
    """Datos del usuario con sesión vigente, o None."""
    if not session.get("token") or time.time() >= session.get("expira", 0):
        return None
    return session.get("usuario")


def pagina_inicial(rol: str) -> str:
    return url_for("catalogo.lista") if rol == "cliente" else url_for("dashboard.inicio")


def iniciar_sesion(respuesta_login: dict):
    """Guarda en la sesión la respuesta de /api/auth/login."""
    session.clear()  # una sesión nueva evita reutilizar la anterior
    u = respuesta_login["usuario"]
    session["token"] = respuesta_login["access_token"]
    session["expira"] = time.time() + respuesta_login["expires_in"] - 10
    session["usuario"] = {"id": u["id"], "nombre": u["nombre"], "correo": u["correo"], "rol": u["rol"]}
    session["csrf"] = secrets.token_hex(16)


def cerrar_sesion():
    session.clear()


def login_required(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if usuario_actual() is None:
            if session.get("token"):
                flash("Tu sesión venció. Inicia sesión de nuevo.", "aviso")
            session.pop("token", None)
            return redirect(url_for("auth.login", siguiente=request.full_path.rstrip("?")))
        return vista(*args, **kwargs)
    return envoltura


def roles_required(*roles):
    """Deja pasar solo a los roles indicados; a los demás, 403."""
    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(*args, **kwargs):
            if usuario_actual()["rol"] not in roles:
                abort(403)
            return vista(*args, **kwargs)
        return envoltura
    return decorador


# ---------------------------------------------------------------------
# CSRF: evita que otro sitio haga que tu navegador envíe formularios a este
# ---------------------------------------------------------------------
def token_csrf() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def verificar_csrf():
    """Se ejecuta antes de cada petición que modifica datos."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    esperado = session.get("csrf", "")
    recibido = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
    if not esperado or not hmac.compare_digest(esperado, recibido):
        abort(400, description="El formulario venció o no es válido. Recarga la página e inténtalo de nuevo.")
