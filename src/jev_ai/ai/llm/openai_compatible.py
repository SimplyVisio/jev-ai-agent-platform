"""Proveedor OpenAI-compatible que solo propone ``QueryPlan`` en JSON."""

import json
from datetime import date
from typing import Any

import httpx

from jev_ai.ai.jev.plans import MetricName, plan_to_dict
from jev_ai.ai.llm.base import ContextMessage, LLMContext, LLMProvider
from jev_ai.ai.llm.errors import (
    LLMConnectionError,
    LLMError,
    LLMNoResponseError,
    LLMTimeoutError,
)

_SYSTEM_PROMPT = f"""Eres el planificador de consultas de JEV AI.
Tu única salida debe ser un objeto JSON válido, sin markdown ni explicaciones.

Catálogo cerrado de operaciones:
1. top_ads_by_metric:
   {{"operation": "top_ads_by_metric", "metric": "...", "date_from": "YYYY-MM-DD",
     "date_to": "YYYY-MM-DD", "limit": 5}}
2. campaign_performance:
   {{"operation": "campaign_performance", "campaign_name": "...",
     "date_from": "YYYY-MM-DD", "date_to": "YYYY-MM-DD"}}
3. compare_periods:
   {{"operation": "compare_periods", "date_from": "YYYY-MM-DD", "date_to": "YYYY-MM-DD",
     "comparison_date_from": "YYYY-MM-DD", "comparison_date_to": "YYYY-MM-DD"}}

Métricas permitidas: {", ".join(metric.value for metric in MetricName)}.

Reglas:
- Usa fechas ISO inclusivas y date_from <= date_to.
- limit debe estar entre 1 y 20; si no se indica, usa 5.
- No ordenes top_ads_by_metric por reach ni frequency.
- No incluyas organization_id, SQL, IDs de organización ni campos extra.
- Si falta información para construir un plan, devuelve {{"error": "motivo breve"}}.
"""


class OpenAICompatibleProvider(LLMProvider):
    """Cliente mínimo para la API de chat completions compatible con OpenAI.

    Args:
        api_key: Clave del proveedor; nunca se registra.
        model: Modelo que se enviará en la petición.
        base_url: Raíz de la API, por ejemplo ``https://api.openai.com/v1``.
        timeout: Segundos máximos de espera.
        transport: Transporte HTTP alternativo para tests; no se usa en producción.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("LLM_API_KEY is required for the OpenAI provider")
        self._api_key = api_key
        self._model = model
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self._timeout = timeout
        self._transport = transport

    async def generate(
        self,
        prompt: str,
        *,
        context: LLMContext | None = None,
    ) -> str:
        """Pide al modelo un plan JSON y devuelve su contenido sin interpretarlo."""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": self._build_messages(prompt, context),
            "temperature": 0,
            "max_tokens": 600,
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    self._endpoint,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("OpenAI request timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMConnectionError("OpenAI connection failed") from exc

        if response.status_code >= 400:
            raise LLMError(f"OpenAI request failed with status {response.status_code}")

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("OpenAI response did not include message content") from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMNoResponseError("OpenAI returned an empty message")
        return content

    @staticmethod
    def _build_messages(
        prompt: str,
        context: LLMContext | None,
    ) -> list[dict[str, str]]:
        """Combina instrucciones, contexto acotado y mensaje actual."""
        system_parts = [
            _SYSTEM_PROMPT,
            f"Fecha de referencia: {date.today().isoformat()}.",
        ]
        if context is not None:
            if context.last_plan is not None:
                system_parts.append(
                    "Último plan válido: "
                    + json.dumps(plan_to_dict(context.last_plan), ensure_ascii=False)
                )
            if context.messages:
                system_parts.append(_format_context(context.messages))
        return [
            {"role": "system", "content": "\n\n".join(system_parts)},
            {"role": "user", "content": prompt},
        ]


def _format_context(messages: tuple[ContextMessage, ...]) -> str:
    """Presenta el transcript reciente como texto, no como turnos del asistente."""
    lines = ["Contexto reciente (del más antiguo al más nuevo):"]
    lines.extend(f"{message.role}: {message.content}" for message in messages)
    return "\n".join(lines)
