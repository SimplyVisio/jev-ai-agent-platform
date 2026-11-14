"""Errores comunes de los proveedores de lenguaje."""


class LLMError(Exception):
    """Error genérico del proveedor de lenguaje."""


class LLMConnectionError(LLMError):
    """El proveedor no pudo conectarse."""


class LLMTimeoutError(LLMError):
    """El proveedor agotó el tiempo de espera."""


class LLMNoResponseError(LLMError):
    """El proveedor no devolvió una respuesta utilizable."""
