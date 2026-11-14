"""Schemas compartidos por los endpoints de la versión 1."""

from pydantic import BaseModel, ConfigDict


class TraceStep(BaseModel):
    """Paso real ejecutado por el grafo, expuesto solo en modo debug."""

    model_config = ConfigDict(from_attributes=True)

    node: str
    detail: str
    duration_ms: float
