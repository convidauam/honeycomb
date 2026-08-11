"""Hasheo de contrasenas de cuentas locales, con hashlib.scrypt (stdlib).

No agrega dependencias: scrypt ya viene con Python via OpenSSL. El formato de
salida lleva sus propios parametros para poder subir el costo mas adelante sin
invalidar los hashes ya guardados.
"""

import base64
import hashlib
import hmac
import re
import secrets

SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16

USERNAME_RE = re.compile(r'^[a-z0-9_-]{3,32}$')


class CredentialError(Exception):
    """Nombre de usuario o contrasena que no cumple la politica de cuentas locales."""


def hash_password(password):
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    salt_b64 = base64.b64encode(salt).decode('ascii')
    digest_b64 = base64.b64encode(digest).decode('ascii')
    return f'scrypt$n={SCRYPT_N},r={SCRYPT_R},p={SCRYPT_P}${salt_b64}${digest_b64}'


def verify_password(password, stored):
    """Nunca lanza: un hash corrupto o de un formato distinto simplemente no verifica."""
    try:
        scheme, params, salt_b64, digest_b64 = stored.split('$')
        if scheme != 'scrypt':
            return False
        kwargs = {}
        for part in params.split(','):
            key, value = part.split('=')
            kwargs[key] = int(value)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        candidate = hashlib.scrypt(
            password.encode('utf-8'), salt=salt,
            n=kwargs['n'], r=kwargs['r'], p=kwargs['p'],
        )
        return hmac.compare_digest(candidate, expected)
    except Exception:
        return False


def validate_password(password, min_length=10):
    if not password or len(password) < min_length:
        raise CredentialError(f'La contrasena debe tener al menos {min_length} caracteres')


def normalize_username(raw):
    """Minusculas, sin espacios, charset limitado a letras/numeros/guion/guion bajo.

    Prohibe '@', ':' y '/' a proposito: un nombre local nunca debe poder
    confundirse con un handle del Fediverso (usuario@dominio) ni con una URL
    de actor, porque ambas formas conviven como claves en __identities__.
    """
    username = (raw or '').strip().lower()
    if not USERNAME_RE.match(username):
        raise CredentialError(
            'El nombre de usuario debe tener 3-32 caracteres: minusculas, numeros, guion o guion bajo'
        )
    return username
