"""Contratos Pydantic y puerto del motor de decisiones TypeSafe JEV."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from jev_ai.observability.usage import TokenUsage

DEFAULT_JEV_MODEL = "jev-1.13.0"


class _RequestModel(BaseModel):
    """Base de los objetos que se envían a TypeSafe."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class _ResponseModel(BaseModel):
    """Base tolerante a campos nuevos que añada el proveedor."""

    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)


class NoulCriteria(_RequestModel):
    """Descripciones opcionales para una respuesta binaria."""

    true: str | None = None
    false: str | None = None


class NoulQuestion(_RequestModel):
    """Pregunta de sí/no que devuelve una probabilidad."""

    type: Literal["noul"] = "noul"
    instructions: str = Field(min_length=1)
    criteria: NoulCriteria | None = None


class ChoiceQuestion(_RequestModel):
    """Pregunta de clasificación con un catálogo cerrado de opciones."""

    type: Literal["choice"] = "choice"
    instructions: str = Field(min_length=1)
    criteria: dict[str, str] = Field(min_length=1, max_length=255)

    @field_validator("criteria")
    @classmethod
    def validate_criteria(cls, value: dict[str, str]) -> dict[str, str]:
        """Exige nombres y descripciones no vacíos."""
        if any(not key.strip() or not description.strip() for key, description in value.items()):
            raise ValueError("choice criteria must have non-empty keys and descriptions")
        return value


class BoxQuestion(_RequestModel):
    """Pregunta de localización sobre una imagen (Jev 1.14+)."""

    type: Literal["box"] = "box"
    instructions: str = Field(min_length=1)


class ScoreQuestion(_RequestModel):
    """Pregunta ordinal con entre dos y diez niveles."""

    type: Literal["score"] = "score"
    instructions: str = Field(min_length=1)
    criteria: list[str] = Field(min_length=2, max_length=10)

    @field_validator("criteria")
    @classmethod
    def validate_criteria(cls, value: list[str]) -> list[str]:
        """Exige niveles no vacíos."""
        if any(not level.strip() for level in value):
            raise ValueError("score criteria must have non-empty levels")
        return value


Question = Annotated[
    NoulQuestion | ChoiceQuestion | ScoreQuestion | BoxQuestion,
    Field(discriminator="type"),
]


class DecisionRequest(_RequestModel):
    """Petición a ``POST /v1/systemone``.

    ``model`` es opcional para permitir que el cliente aplique su modelo por
    defecto. Si se envía, prevalece sobre la configuración del cliente.
    """

    state: str | dict[str, Any] | list[Any]
    questions: dict[str, Question] = Field(min_length=1)
    model: str | None = Field(default=None, min_length=1)

    @field_validator("questions")
    @classmethod
    def validate_question_names(cls, value: dict[str, Question]) -> dict[str, Question]:
        """Evita nombres vacíos que harían ambiguas las respuestas."""
        if any(not name.strip() for name in value):
            raise ValueError("question names must not be empty")
        return value


Probability = Annotated[float, Field(ge=0, le=1)]


class NoulAnswer(_ResponseModel):
    """Respuesta binaria con su probabilidad."""

    type: Literal["noul"]
    noul: Probability
    confidence: Probability | None = None


class ChoiceAnswer(_ResponseModel):
    """Opción elegida y distribución de probabilidades."""

    type: Literal["choice"]
    choice: str
    probabilities: dict[str, Probability] | None = None
    confidence: Probability | None = None


class ScoreAnswer(_ResponseModel):
    """Nivel elegido dentro de una escala ordinal."""

    type: Literal["score"]
    score: float
    probabilities: dict[str, Probability] | None = None
    confidence: Probability | None = None
    legend: dict[str, str] | None = None


class BoxCoordinates(_ResponseModel):
    """Coordenadas normalizadas de una caja sobre la imagen."""

    top: Probability
    bottom: Probability
    left: Probability
    right: Probability


class BoxAnswer(_ResponseModel):
    """Región de la imagen que responde a la pregunta."""

    type: Literal["box"]
    box: BoxCoordinates
    confidence: Probability | None = None


Answer = Annotated[
    NoulAnswer | ChoiceAnswer | ScoreAnswer | BoxAnswer,
    Field(discriminator="type"),
]


class DecisionUsage(_ResponseModel):
    """Tokens reportados por TypeSafe; solo la entrada se factura."""

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)

    def to_token_usage(self) -> TokenUsage:
        """Convierte el usage del proveedor al contrato interno."""
        return TokenUsage(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )


class DecisionResponse(_ResponseModel):
    """Respuesta de ``POST /v1/systemone``."""

    model: str = Field(min_length=1)
    answers: dict[str, Answer] = Field(min_length=1)
    usage: DecisionUsage | None = None


@dataclass(frozen=True)
class DecisionResult:
    """Respuesta validada y metadatos de transporte útiles para soporte."""

    response: DecisionResponse
    request_id: str | None = None

    @property
    def usage(self) -> TokenUsage | None:
        """Expone el usage normalizado para coste y telemetría."""
        if self.response.usage is None:
            return None
        return self.response.usage.to_token_usage()


class DecisionProvider(ABC):
    """Puerto para motores que responden preguntas estructuradas.

    No es un ``LLMProvider``: Jev no redacta texto libre. El resto del sistema
    puede depender de esta interfaz para clasificar o validar sin acoplarse a
    TypeSafe.
    """

    @property
    def provider_name(self) -> str:
        """Nombre estable del proveedor para métricas."""
        return self.__class__.__name__

    @property
    def model_name(self) -> str:
        """Modelo configurado por el proveedor."""
        return DEFAULT_JEV_MODEL

    @abstractmethod
    async def decide(self, request: DecisionRequest) -> DecisionResult:
        """Ejecuta una o varias preguntas sobre el mismo estado."""
