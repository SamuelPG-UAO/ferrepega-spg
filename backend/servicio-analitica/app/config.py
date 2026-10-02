"""
Configuración del servicio (variables de entorno o archivo .env).
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

CARPETA_SERVICIO = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Sin valor por defecto: si faltan, el servicio no arranca y lo avisa.
    database_url: str
    jwt_secret: str  # la MISMA que usa servicio-autenticacion

    jwt_algorithm: str = "HS256"

    # Cómo llegar a servicio-ventas (segundos de espera máxima por respuesta)
    ventas_url: str = "http://127.0.0.1:8003"
    ventas_timeout: float = 30.0

    model_config = SettingsConfigDict(
        env_file=CARPETA_SERVICIO / ".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
