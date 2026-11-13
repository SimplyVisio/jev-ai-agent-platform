"""Configuración de la aplicación cargada desde variables de entorno y `.env`."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración tipada de JEV AI.

    Attributes:
        app_name: Nombre que aparece en la documentación de OpenAPI.
        database_url: DSN de SQLAlchemy async, por ejemplo
            ``postgresql+asyncpg://user:password@host:5432/db``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "JEV AI"
    database_url: str


@lru_cache
def get_settings() -> Settings:
    """Devuelve una única instancia de ``Settings`` por proceso.

    El caché evita releer y revalidar el entorno en cada petición. Los tests que
    necesitan configuración distinta deben inyectarla explícitamente en
    ``create_app`` en lugar de modificar este caché.
    """
    return Settings()
