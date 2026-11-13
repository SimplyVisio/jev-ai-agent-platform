"""Catálogo cerrado de intenciones y contrato del clasificador."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum


class Intent(StrEnum):
    """Intenciones que JEV AI puede reconocer."""

    TOP_ADS_BY_METRIC = "top_ads_by_metric"
    CAMPAIGN_PERFORMANCE = "campaign_performance"
    COMPARE_PERIODS = "compare_periods"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class IntentResult:
    """Resultado medible de una clasificación."""

    intent: Intent
    confidence: float
    reason: str


class IntentClassifier(ABC):
    """Interfaz intercambiable para clasificadores de intención."""

    @abstractmethod
    async def classify(self, message: str) -> IntentResult:
        """Clasifica un mensaje dentro del catálogo cerrado."""
