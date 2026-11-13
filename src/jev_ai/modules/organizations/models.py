"""Entidades de organizaciones y claves de API."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jev_ai.infrastructure.database.base import Base


class Organization(Base):
    """Empresa cliente propietaria de los datos de marketing.

    Attributes:
        id: Identificador UUID generado por la aplicación.
        name: Nombre visible de la organización.
        currency_code: Código ISO 4217 usado en sus métricas monetarias.
        created_at: Fecha de alta, asignada por PostgreSQL.
        api_keys: Claves de acceso asociadas.
    """

    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120))
    currency_code: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class ApiKey(Base):
    """Credencial de una organización.

    Solo se almacena el hash SHA-256 de la clave. El texto plano se muestra una vez al
    crearla y nunca se persiste.

    Attributes:
        id: Identificador UUID de la credencial.
        organization_id: Organización a la que pertenece.
        key_hash: SHA-256 hexadecimal de 64 caracteres.
        created_at: Fecha de creación, asignada por PostgreSQL.
        organization: Relación inversa hacia ``Organization``.
    """

    __tablename__ = "api_keys"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    organization: Mapped[Organization] = relationship(back_populates="api_keys")
