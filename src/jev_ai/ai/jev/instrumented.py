"""Decorador de motores de decisión con trazas y coste estimado."""

from time import perf_counter

import structlog

from jev_ai.ai.jev.contracts import (
    DecisionProvider,
    DecisionRequest,
    DecisionResult,
)
from jev_ai.observability.context import record_model_call
from jev_ai.observability.pricing import estimate_cost

logger = structlog.get_logger(__name__)


class InstrumentedDecisionProvider(DecisionProvider):
    """Envuelve un motor de decisiones y registra cada llamada."""

    def __init__(self, delegate: DecisionProvider) -> None:
        self._delegate = delegate

    @property
    def provider_name(self) -> str:
        """Delega la identidad del proveedor real."""
        return self._delegate.provider_name

    @property
    def model_name(self) -> str:
        """Delega el modelo configurado."""
        return self._delegate.model_name

    async def decide(self, request: DecisionRequest) -> DecisionResult:
        """Ejecuta la decisión y registra su resultado o su error."""
        started = perf_counter()
        try:
            result = await self._delegate.decide(request)
        except Exception as exc:
            self._record(
                model=self.model_name,
                status="error",
                latency_ms=(perf_counter() - started) * 1000,
                error_type=type(exc).__name__,
            )
            raise

        self._record(
            model=result.response.model,
            status="ok",
            latency_ms=(perf_counter() - started) * 1000,
            result=result,
        )
        return result

    def _record(
        self,
        *,
        model: str,
        status: str,
        latency_ms: float,
        result: DecisionResult | None = None,
        error_type: str | None = None,
    ) -> None:
        """Registra la llamada sin romper la decisión si falla la telemetría."""
        usage = None if result is None else result.usage
        cost = estimate_cost(self.provider_name, model, usage)
        try:
            record_model_call(
                provider=self.provider_name,
                model=model,
                call_type="decision",
                status=status,
                latency_ms=latency_ms,
                usage=usage,
                estimated_cost_usd=None if cost is None else cost.amount_usd,
                price_version=None if cost is None else cost.price_version,
                service_tier="standard",
                error_type=error_type,
            )
        except Exception:
            logger.exception("model_call_record_failed", provider=self.provider_name)

        logger.info(
            "model_call",
            provider=self.provider_name,
            model=model,
            call_type="decision",
            status=status,
            latency_ms=round(latency_ms, 2),
            input_tokens=None if usage is None else usage.input_tokens,
            output_tokens=None if usage is None else usage.output_tokens,
            estimated_cost_usd=None if cost is None else str(cost.amount_usd),
            error_type=error_type,
        )
