"""Estados posibles de una interacción de chat."""

from enum import StrEnum


class ChatStatus(StrEnum):
    """Resultado de alto nivel de una interacción."""

    OK = "ok"
    NEEDS_CLARIFICATION = "needs_clarification"
    ERROR = "error"
