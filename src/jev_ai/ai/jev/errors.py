"""Errores de dominio del cliente de decisiones TypeSafe JEV."""


class JevError(Exception):
    """Error genérico del motor de decisiones."""


class JevConnectionError(JevError):
    """No se pudo conectar con TypeSafe."""


class JevTimeoutError(JevError):
    """TypeSafe agotó el tiempo de espera."""


class JevRequestError(JevError):
    """La petición local no cumple las reglas de TypeSafe."""


class JevResponseError(JevError):
    """La respuesta no es JSON válido o no cumple el contrato."""


class JevAPIError(JevError):
    """TypeSafe rechazó la petición o devolvió un error HTTP."""

    def __init__(
        self,
        *,
        status_code: int,
        detail: str,
        request_id: str | None = None,
        retry_after: str | None = None,
    ) -> None:
        super().__init__(f"TypeSafe JEV request failed with status {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail
        self.request_id = request_id
        self.retry_after = retry_after
