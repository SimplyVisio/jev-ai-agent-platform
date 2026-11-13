"""Modelo declarativo base para todas las entidades SQLAlchemy."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Metadatos y configuración comunes de los modelos ORM."""
