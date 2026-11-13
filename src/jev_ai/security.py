"""Utilidades de seguridad independientes de la capa HTTP."""

import hashlib


def hash_api_key(api_key: str) -> str:
    """Calcula el hash SHA-256 hexadecimal de una API key.

    Args:
        api_key: Clave en texto plano recibida o generada.

    Returns:
        Digest hexadecimal de 64 caracteres. Solo este valor se persiste.
    """
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()
