"""Cliente HTTP mínimo para el endpoint nativo ``POST /v1/systemone``."""

import asyncio
import json
import math
from typing import Any

import httpx
from pydantic import ValidationError

from jev_ai.ai.jev.contracts import (
    DEFAULT_JEV_MODEL,
    DecisionProvider,
    DecisionRequest,
    DecisionResponse,
    DecisionResult,
)
from jev_ai.ai.jev.errors import (
    JevAPIError,
    JevConnectionError,
    JevRequestError,
    JevResponseError,
    JevTimeoutError,
)

MAX_REQUEST_BYTES = 32 * 1024 * 1024
MAX_NESTING = 64
_RETRY_STATUSES = frozenset({429, 529})


class TypeSafeJevProvider(DecisionProvider):
    """Cliente de decisiones TypeSafe sin SDK y con transporte inyectable.

    Args:
        api_key: Clave de TypeSafe; nunca se registra.
        model: Modelo por defecto cuando la petición no indica uno.
        base_url: Raíz de la API; el endpoint se añade internamente.
        timeout: Segundos máximos de espera por intento.
        max_retries: Reintentos adicionales para 429/529.
        retry_backoff: Segundos base del backoff exponencial.
        transport: Transporte HTTP alternativo para tests.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_JEV_MODEL,
        base_url: str = "https://api.typesafe.ai",
        timeout: float = 120.0,
        max_retries: int = 2,
        retry_backoff: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("TYPESAFE_API_KEY is required for the TypeSafe JEV provider")
        if not model.strip():
            raise ValueError("A JEV model is required")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if retry_backoff < 0:
            raise ValueError("retry_backoff cannot be negative")
        self._api_key = api_key
        self._model = model
        self._endpoint = f"{base_url.rstrip('/')}/v1/systemone"
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._transport = transport

    @property
    def provider_name(self) -> str:
        """Identidad usada en las métricas de observabilidad."""
        return "typesafe"

    @property
    def model_name(self) -> str:
        """Modelo configurado por defecto."""
        return self._model

    async def decide(self, request: DecisionRequest) -> DecisionResult:
        """Envía las preguntas y valida la respuesta antes de devolverla."""
        payload = request.model_dump(mode="json", exclude_none=True)
        payload["model"] = request.model or self._model
        body = _encode_request(payload, state=request.state)

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = await self._post_with_retries(client, body)
        except httpx.TimeoutException as exc:
            raise JevTimeoutError("TypeSafe JEV request timed out") from exc
        except httpx.HTTPError as exc:
            raise JevConnectionError("TypeSafe JEV connection failed") from exc

        request_id = response.headers.get("x-typesafe-request-id")
        if response.status_code >= 400:
            raise JevAPIError(
                status_code=response.status_code,
                detail=_error_detail(response),
                request_id=request_id,
                retry_after=response.headers.get("retry-after"),
            )

        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise JevResponseError("TypeSafe JEV returned invalid JSON") from exc

        try:
            decision = DecisionResponse.model_validate(data)
        except ValidationError as exc:
            raise JevResponseError("TypeSafe JEV response did not match the contract") from exc
        return DecisionResult(response=decision, request_id=request_id)

    async def _post_with_retries(
        self,
        client: httpx.AsyncClient,
        body: bytes,
    ) -> httpx.Response:
        """Reintenta solo 429/529 con backoff exponencial y ``Retry-After``."""
        response: httpx.Response | None = None
        for attempt in range(self._max_retries + 1):
            response = await client.post(
                self._endpoint,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                content=body,
            )
            if response.status_code not in _RETRY_STATUSES or attempt >= self._max_retries:
                return response
            await asyncio.sleep(_retry_delay(response, attempt, self._retry_backoff))

        assert response is not None
        return response


def _retry_delay(response: httpx.Response, attempt: int, backoff: float) -> float:
    """Respeta ``Retry-After`` en segundos o aplica backoff exponencial."""
    retry_after = response.headers.get("retry-after")
    if retry_after is not None:
        try:
            seconds = float(retry_after)
        except ValueError:
            seconds = -1
        if seconds >= 0:
            return seconds
    return backoff * (2**attempt)


def _encode_request(payload: dict[str, Any], *, state: object) -> bytes:
    """Serializa, valida anidación/límite y evita números no finitos."""
    _ensure_finite(state, "state")
    _validate_nesting(payload.get("state"), "state")
    questions = payload.get("questions")
    if isinstance(questions, dict):
        for name, question in questions.items():
            if isinstance(question, dict):
                _validate_nesting(question.get("criteria"), f"questions.{name}.criteria")

    try:
        body = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise JevRequestError("request contains values that cannot be encoded as JSON") from exc
    if len(body) > MAX_REQUEST_BYTES:
        raise JevRequestError(f"request body exceeds {MAX_REQUEST_BYTES} bytes")
    return body


def _ensure_finite(value: Any, field: str) -> None:
    """Pydantic convierte NaN/Infinity a null en JSON; hay que detectarlos antes."""
    if isinstance(value, float) and not math.isfinite(value):
        raise JevRequestError(f"{field} contains a non-finite number")
    if isinstance(value, dict):
        for key, item in value.items():
            _ensure_finite(item, f"{field}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _ensure_finite(item, f"{field}[{index}]")


def _validate_nesting(value: Any, field: str) -> None:
    """Comprueba el límite de 64 niveles de la API."""
    if _depth(value) > MAX_NESTING:
        raise JevRequestError(f"{field} exceeds the maximum nesting of {MAX_NESTING} levels")


def _depth(value: Any) -> int:
    """Calcula la profundidad de diccionarios y listas."""
    if isinstance(value, dict):
        return 1 + max((_depth(item) for item in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_depth(item) for item in value), default=0)
    return 0


def _error_detail(response: httpx.Response) -> str:
    """Extrae ``detail`` del cuerpo sin asumir una forma única de error."""
    try:
        data: Any = response.json()
    except ValueError:
        text = response.text.strip()
        return text[:500] if text else "no detail provided"

    if isinstance(data, dict):
        detail = data.get("detail")
        if detail is None:
            detail = data.get("error")
        if detail is None:
            detail = data.get("message")
        if isinstance(detail, str):
            return detail
        if detail is not None:
            return json.dumps(detail, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False)
