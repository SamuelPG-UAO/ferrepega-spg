"""
Cliente del back: TODAS las llamadas al API Gateway pasan por aquí.

El navegador nunca habla con el back: habla con Flask, y Flask llama al
gateway con el token que guardó en la sesión del usuario.
"""
import time
from typing import Any, Optional

import requests
from flask import current_app, session


class ApiError(Exception):
    """El back respondió con un error (o no respondió)."""

    def __init__(self, codigo: int, detalle: Any):
        super().__init__(f"{codigo}: {detalle}")
        self.codigo = codigo
        self.detalle = detalle

    @property
    def mensaje(self) -> str:
        return mensaje_de_error(self.codigo, self.detalle)


class SesionVencida(ApiError):
    """No hay sesión, venció, o el back rechazó el token (401)."""


# ---------------------------------------------------------------------
# Mensajes de error legibles
# ---------------------------------------------------------------------
_CAMPOS = {
    "nombre": "El nombre", "correo": "El correo", "contrasena": "La contraseña",
    "precio": "El precio", "cantidad": "La cantidad", "motivo": "El motivo",
    "categoria_id": "La categoría", "stock_inicial": "El stock inicial",
    "stock_minimo": "El stock mínimo", "ciudad": "La ciudad", "descripcion": "La descripción",
    "producto_id": "El producto", "cliente_id": "El cliente", "items": "Los productos",
}


def _traducir_validacion(e: dict) -> str:
    """Convierte un error de validación de FastAPI (en inglés) a una frase en español."""
    loc = [str(p) for p in e.get("loc", []) if p not in ("body", "query", "path")]
    campo = _CAMPOS.get(loc[-1] if loc else "", "El dato")
    tipo, ctx = e.get("type", ""), e.get("ctx", {}) or {}
    if tipo == "string_too_short":
        return f"{campo} es demasiado corto (mínimo {ctx.get('min_length')} caracteres)."
    if tipo == "string_too_long":
        return f"{campo} es demasiado largo (máximo {ctx.get('max_length')} caracteres)."
    if tipo in ("greater_than", "greater_than_equal"):
        return f"{campo} debe ser mayor{' o igual' if tipo.endswith('equal') else ''} a {ctx.get('gt', ctx.get('ge'))}."
    if tipo in ("less_than", "less_than_equal"):
        return f"{campo} debe ser menor{' o igual' if tipo.endswith('equal') else ''} a {ctx.get('lt', ctx.get('le'))}."
    if tipo == "missing":
        return f"{campo} es obligatorio."
    if "email" in e.get("msg", "").lower() or "email" in tipo:
        return "El correo no tiene un formato válido."
    if tipo.endswith("_parsing") or tipo.endswith("_type"):
        return f"{campo} no tiene un formato válido."
    if tipo == "value_error":
        # Los validadores propios del back ya escriben el mensaje en español
        return str(e.get("msg", "")).replace("Value error, ", "")
    return f"{campo} no es válido."


def mensaje_de_error(codigo: int, detalle: Any) -> str:
    if isinstance(detalle, str):
        return detalle
    if isinstance(detalle, dict):
        if "faltantes" in detalle:
            partes = [f"{f['nombre']} (pediste {f['solicitado']}, hay {f['disponible']})"
                      for f in detalle["faltantes"]]
            return "No hay stock suficiente: " + "; ".join(partes) + "."
        return detalle.get("mensaje", "Ocurrió un error.")
    if isinstance(detalle, list):
        return " ".join(dict.fromkeys(_traducir_validacion(e) for e in detalle if isinstance(e, dict)))
    return "Ocurrió un error inesperado."


# ---------------------------------------------------------------------
# Llamadas
# ---------------------------------------------------------------------
def llamar(metodo: str, ruta: str, *, json: Any = None, params: Optional[dict] = None,
           autenticado: bool = True) -> Any:
    """Llama al gateway. Devuelve el JSON de la respuesta (o None si es 204)."""
    cabeceras = {}
    if autenticado:
        token, expira = session.get("token"), session.get("expira", 0)
        if not token or time.time() >= expira:
            raise SesionVencida(401, "Tu sesión venció. Inicia sesión de nuevo.")
        cabeceras["Authorization"] = f"Bearer {token}"

    # Los filtros vacíos no se envían (el back los tomaría como un valor)
    if params:
        params = {k: v for k, v in params.items() if v not in (None, "")}

    try:
        r = requests.request(metodo, current_app.config["API_URL"] + ruta, json=json,
                             params=params, headers=cabeceras,
                             timeout=current_app.config["API_TIMEOUT"])
    except requests.RequestException:
        raise ApiError(503, "No se pudo conectar con el servidor. Intenta de nuevo en unos segundos.")

    if r.status_code == 401 and autenticado:
        raise SesionVencida(401, "Tu sesión venció. Inicia sesión de nuevo.")
    if r.status_code >= 400:
        try:
            detalle = r.json().get("detail", r.text)
        except ValueError:
            detalle = r.text
        if r.status_code == 429:
            detalle = "Demasiados intentos seguidos. Espera un momento e inténtalo de nuevo."
        raise ApiError(r.status_code, detalle)
    if r.status_code == 204 or not r.content:
        return None
    return r.json()


def get(ruta, **params):
    return llamar("GET", ruta, params=params)


def post(ruta, cuerpo=None, **params):
    return llamar("POST", ruta, json=cuerpo, params=params or None)


def put(ruta, cuerpo=None):
    return llamar("PUT", ruta, json=cuerpo)


def delete(ruta):
    return llamar("DELETE", ruta)
