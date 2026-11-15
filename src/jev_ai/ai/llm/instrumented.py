"""Decorador de proveedores que mide latencia, tokens y coste estimado."""

from time import perf_counter

import structlog

from jev_ai.ai.llm.base import LLMContext, LLMProvider, LLMResult
from jev_ai.observability.context import record_model_call
from jev_ai.observability.pricing import estimate_cost

logger = structlog.get_logger(__name__)


class InstrumentedLLMProvider(LLMProvider):
    """Envuelve otro proveedor y registra cada llamada sin alterar su contenido."""

    def __init__(self, delegate: LLMProvider) -> None:
        self._delegate = delegate

    @property
    def provider_name(self) -> str:
        """Delega la identidad del proveedor real."""
        return self._delegate.provider_name

    @property
    def model_name(self) -> str:
        """Delega el modelo del proveedor real."""
        return self._delegate.model_name

    async def generate(
        self,
        prompt: str,
        *,
        context: LLMContext | None = None,
    ) -> LLMResult:
        """Ejecuta la llamada y registra su resultado o su error."""
        started = perf_counter()
        try:
            result = await self._delegate.generate(prompt, context=context)
        except Exception as exc:
            self._record(
                status="error",
                latency_ms=(perf_counter() - started) * 1000,
                error_type=type(exc).__name__,
            )
            raise

        self._record(
            status="ok",
            latency_ms=(perf_counter() - started) * 1000,
            result=result,
        )
        return result

    def _record(
        self,
        *,
        status: str,
        latency_ms: float,
        result: LLMResult | None = None,
        error_type: str | None = None,
    ) -> None:
        """Registra la llamada sin permitir que un fallo de telemetría rompa el chat."""
        cost = (
            estimate_cost(
                self.provider_name,
                self.model_name,
                result.usage,
                service_tier=result.service_tier,
            )
            if result is not None
            else None
        )
        try:
            record_model_call(
                provider=self.provider_name,
                model=self.model_name,
                call_type="generation",
                status=status,
                latency_ms=latency_ms,
                usage=None if result is None else result.usage,
                estimated_cost_usd=None if cost is None else cost.amount_usd,
                price_version=None if cost is None else cost.price_version,
                service_tier=None if result is None else result.service_tier,
                error_type=error_type,
            )
        except Exception:
            logger.exception("model_call_record_failed", provider=self.provider_name)

        logger.info(
            "model_call",
            provider=self.provider_name,
            model=self.model_name,
            status=status,
            latency_ms=round(latency_ms, 2),
            input_tokens=(
                None if result is None or result.usage is None else result.usage.input_tokens
            ),
            output_tokens=(
                None if result is None or result.usage is None else result.usage.output_tokens
            ),
            estimated_cost_usd=None if cost is None else str(cost.amount_usd),
            error_type=error_type,
        )
