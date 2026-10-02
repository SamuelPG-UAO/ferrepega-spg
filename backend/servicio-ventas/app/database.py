"""
Conexión a PostgreSQL (ventas_db) con SQLAlchemy.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"client_encoding": "utf8"},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Clase base de la que heredan todos los modelos."""


def get_db():
    """Entrega una sesión por petición y la cierra al terminar.
    Si la petición falla antes de hacer commit, los cambios se descartan."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
