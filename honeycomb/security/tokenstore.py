"""Cifrado en reposo del access_token de OAuth del Fediverso.

Sin honeycomb.token_encryption_key configurada, el token nunca se guarda -- ni
en claro ni de ninguna otra forma. Publicar al Fediverso a nombre del usuario
queda deshabilitado hasta que quien administra la instancia provea una clave.
"""

from cryptography.fernet import Fernet, InvalidToken


class TokenStoreError(Exception):
    """Clave mal configurada, o token guardado que ya no se puede descifrar."""


def _fernet(settings):
    raw_key = (settings.get('honeycomb.token_encryption_key') or '').strip()
    if not raw_key:
        return None
    try:
        return Fernet(raw_key.encode('ascii'))
    except (ValueError, TypeError) as exc:
        raise TokenStoreError(
            "honeycomb.token_encryption_key no es una clave Fernet valida "
            "(genera una con tokenstore.generate_key())"
        ) from exc


def is_configured(settings):
    return _fernet(settings) is not None


def encrypt_token(settings, access_token):
    """None si no hay clave configurada: el llamador decide si eso bloquea la accion."""
    if not access_token:
        return None
    fernet = _fernet(settings)
    if fernet is None:
        return None
    return fernet.encrypt(access_token.encode('utf-8')).decode('ascii')


def decrypt_token(settings, encrypted_token):
    if not encrypted_token:
        return None
    fernet = _fernet(settings)
    if fernet is None:
        raise TokenStoreError('No hay honeycomb.token_encryption_key configurada en este servidor')
    try:
        return fernet.decrypt(encrypted_token.encode('ascii')).decode('utf-8')
    except InvalidToken as exc:
        raise TokenStoreError('El token guardado no se pudo descifrar (se roto la clave?)') from exc


def generate_key():
    """Utilidad para el administrador de la instancia: genera una clave Fernet nueva."""
    return Fernet.generate_key().decode('ascii')
