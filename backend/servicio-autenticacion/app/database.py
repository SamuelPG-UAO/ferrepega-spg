"""
Conexión a PostgreSQL (auth_db) con SQLAlchemy.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

# El "engine" administra un grupo de conexiones reutilizables.
#  - pool_pre_ping: antes de usar una conexión comprueba que siga viva.
#  - client_encoding: fuerza UTF-8 para guardar bien tildes y eñes.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"client_encoding": "utf8"},
)

# Cada petición HTTP trabaja con su propia sesión.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Clase base de la que heredan todos los modelos."""


def get_db():
    """Dependencia de FastAPI: entrega una sesión y la cierra al terminar
    la petición, aunque haya ocurrido un error."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
