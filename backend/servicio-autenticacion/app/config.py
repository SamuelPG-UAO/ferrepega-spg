"""
Configuración del servicio.

Los valores se leen de variables de entorno o del archivo .env que está
junto a requirements.txt. Así las claves no quedan escritas en el código.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Carpeta del servicio (la que contiene requirements.txt y .env)
CARPETA_SERVICIO = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Sin valor por defecto: si falta en el .env, el servicio no arranca
    # y avisa claramente, en vez de funcionar con una clave insegura.
    database_url: str
    jwt_secret: str

    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=CARPETA_SERVICIO / ".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
