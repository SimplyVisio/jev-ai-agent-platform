"""Configuración de la aplicación cargada desde variables de entorno y `.env`."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración tipada de JEV AI.

    Attributes:
        app_name: Nombre que aparece en la documentación de OpenAPI.
        database_url: DSN de SQLAlchemy async, por ejemplo
            ``postgresql+asyncpg://user:password@host:5432/db``.
        llm_provider: ``mock`` durante el desarrollo o ``openai`` para usar la API.
        llm_api_key: Clave del proveedor; obligatoria si ``llm_provider='openai'``.
        llm_model: Modelo enviado al proveedor real.
        llm_base_url: Raíz de una API compatible con OpenAI.
        llm_timeout_seconds: Tiempo máximo de espera de una llamada al LLM.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "JEV AI"
    database_url: str
    llm_provider: Literal["mock", "openai"] = "mock"
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_timeout_seconds: float = Field(default=30.0, gt=0, le=120)


@lru_cache
def get_settings() -> Settings:
    """Devuelve una única instancia de ``Settings`` por proceso.

    El caché evita releer y revalidar el entorno en cada petición. Los tests que
    necesitan configuración distinta deben inyectarla explícitamente en
    ``create_app`` en lugar de modificar este caché.
    """
    return Settings()
