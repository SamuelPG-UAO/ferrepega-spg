"""
Configuración del front. Se lee de variables de entorno (o del archivo .env).
"""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _cargar_env():
    """Lee RAIZ/.env sin necesitar librerías extra. Las variables ya definidas
    en el entorno tienen prioridad sobre las del archivo."""
    archivo = RAIZ / ".env"
    if not archivo.is_file():
        return
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip())


_cargar_env()


class Config:
    API_URL = os.environ.get("FERREPEGA_API_URL", "http://192.168.56.10").rstrip("/")
    SECRET_KEY = os.environ.get("FERREPEGA_SECRET_KEY", "")
    DEMO = os.environ.get("FERREPEGA_DEMO", "1") == "1"

    # Cookie de sesión: no legible desde JavaScript, no se envía desde otros sitios
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("FERREPEGA_COOKIE_SEGURA", "0") == "1"
    SESSION_COOKIE_NAME = "ferrepega_sesion"
    MAX_CONTENT_LENGTH = 1024 * 1024  # 1 MB, igual que el gateway

    # Segundos máximos esperando al back: conectar / recibir respuesta
    API_TIMEOUT = (3, 40)
