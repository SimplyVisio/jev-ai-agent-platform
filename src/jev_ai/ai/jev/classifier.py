"""Clasificador determinista de intenciones basado en reglas.

Es la primera implementación de ``IntentClassifier``. El dataset versionado en
``mocks/datasets/query_plans.json`` permite medir su precisión y detectar regresiones.
"""

import re

from jev_ai.ai.jev.intents import Intent, IntentClassifier, IntentResult

_COMPARE = re.compile(
    r"\b(compara|comparar|comparaci[oó]n|comparativa|vs\.?|frente a|diferencia entre)\b",
    re.IGNORECASE,
)
_TOP_ADS = re.compile(
    r"\b(top|mejores|mejor|ranking)\b.*\b(anuncios?|ads?)\b"
    r"|\b(anuncios?|ads?)\b.*\b(top|mejores|mejor|ranking)\b",
    re.IGNORECASE,
)
_CAMPAIGN = re.compile(r"\bcampa[nñ]a\b", re.IGNORECASE)
_HELP = re.compile(
    r"\b(ayuda|help|hola|buenas|qu[eé] puedes hacer|comandos)\b",
    re.IGNORECASE,
)


def classify_intent(message: str) -> IntentResult:
    """Clasifica un mensaje con reglas ordenadas por prioridad."""
    if _COMPARE.search(message):
        return IntentResult(Intent.COMPARE_PERIODS, 0.95, "compare_keyword")
    if _TOP_ADS.search(message):
        return IntentResult(Intent.TOP_ADS_BY_METRIC, 0.95, "top_ads_keyword")
    if _CAMPAIGN.search(message):
        return IntentResult(Intent.CAMPAIGN_PERFORMANCE, 0.95, "campaign_keyword")
    if _HELP.search(message):
        return IntentResult(Intent.HELP, 0.95, "help_keyword")
    return IntentResult(Intent.UNKNOWN, 0.2, "no_rule_matched")


class RuleBasedClassifier(IntentClassifier):
    """Implementación offline y determinista de ``IntentClassifier``."""

    async def classify(self, message: str) -> IntentResult:
        """Clasifica el mensaje sin llamar a ningún modelo externo."""
        return classify_intent(message)
