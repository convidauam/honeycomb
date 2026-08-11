"""Registro y login de cuentas locales (usuario + contrasena): alternativa al
login por Fediverso para quien no tiene cuenta en ninguna instancia. Deshabilitado
por defecto -- lo activa quien administra la instancia con honeycomb.local_accounts.

Sin correo en el proyecto no hay verificacion de cuenta ni recuperacion de
contrasena: quien pierde su contrasena pierde el acceso a esa credencial (puede
seguir entrando por cualquier otra que tenga vinculada). Es responsabilidad de
la pantalla de registro dejarlo claro, no solo de este modulo.

Ver security/passwords.py para el hasheo y security/ratelimit.py para los limites.
"""

import uuid

from . import ratelimit
from .passwords import CredentialError, hash_password, normalize_username, validate_password, verify_password
from ..models.users import DroneUser

DEFAULT_MIN_PASSWORD_LENGTH = 10
DEFAULT_LOGIN_RATE_WINDOW_SECONDS = 300
DEFAULT_LOGIN_RATE_MAX_PER_USER = 10
DEFAULT_LOGIN_RATE_MAX_GLOBAL = 100


class LocalAuthError(Exception):
    """Cuentas locales deshabilitadas, credenciales invalidas, o demasiados
    intentos. El mensaje es siempre generico en login para no revelar si un
    nombre de usuario existe (ver authenticate)."""


_login_rate_limiter = ratelimit.SlidingWindowLimiter(
    DEFAULT_LOGIN_RATE_WINDOW_SECONDS, DEFAULT_LOGIN_RATE_MAX_PER_USER, DEFAULT_LOGIN_RATE_MAX_GLOBAL,
)
_registration_rate_limiter = ratelimit.SlidingWindowLimiter(
    DEFAULT_LOGIN_RATE_WINDOW_SECONDS, None, DEFAULT_LOGIN_RATE_MAX_GLOBAL,
)


def configure_rate_limiters(settings):
    """Llamado una vez al arrancar la app (security/__init__.py:includeme) para
    que los limites de login/registro local reflejen lo configurado en el .ini."""
    global _login_rate_limiter, _registration_rate_limiter
    window = ratelimit.positive_int_setting(
        settings, 'honeycomb.login_rate_window_seconds', DEFAULT_LOGIN_RATE_WINDOW_SECONDS,
    )
    login_max_per_user = ratelimit.limit_setting_or_none(settings, 'honeycomb.login_rate_max_per_user')
    login_max_global = ratelimit.limit_setting_or_none(settings, 'honeycomb.login_rate_max_global')
    _login_rate_limiter = ratelimit.SlidingWindowLimiter(window, login_max_per_user, login_max_global)

    registration_max_global = ratelimit.limit_setting_or_none(settings, 'honeycomb.registration_rate_max_global')
    _registration_rate_limiter = ratelimit.SlidingWindowLimiter(window, None, registration_max_global)


def is_enabled(settings):
    return (settings.get('honeycomb.local_accounts') or '').strip().lower() in ('1', 'true', 'yes', 'on')


def _min_password_length(settings):
    return ratelimit.positive_int_setting(settings, 'honeycomb.min_password_length', DEFAULT_MIN_PASSWORD_LENGTH)


def register(root, settings, raw_username, password):
    """Crea una cuenta local nueva. userid opaco (local:<uuid>): el nombre de
    usuario no es la llave de la base de datos, se puede cambiar despues sin
    romper el progreso."""
    if not is_enabled(settings):
        raise LocalAuthError('El registro de cuentas locales no esta habilitado en este servidor')

    try:
        username = normalize_username(raw_username)
        validate_password(password, min_length=_min_password_length(settings))
    except CredentialError as exc:
        raise LocalAuthError(str(exc)) from exc

    try:
        _registration_rate_limiter.check_and_record('register')
    except ratelimit.RateLimitError as exc:
        raise LocalAuthError('Demasiados registros en este momento, intenta mas tarde') from exc

    identity_key = f'password:{username}'
    if root.resolve_identity(identity_key) is not None:
        # Mismo mensaje generico que un login fallido: no confirmar si el
        # nombre esta tomado desde una respuesta que un bot pueda automatizar
        # seria mejor, pero en registro el usuario ya eligio el nombre a
        # proposito, asi que aqui si tiene sentido decirlo con claridad.
        raise LocalAuthError('Ese nombre de usuario ya esta en uso')

    userid = f'local:{uuid.uuid4()}'
    user = DroneUser(
        userid=userid, display_name=username, username=username,
        password_hash=hash_password(password),
    )
    root.upsert_user(user)
    root.link_identity(identity_key, userid)
    return user


def authenticate(root, settings, raw_username, password):
    """None de los caminos de fallo revela si el usuario existe: 'no existe' y
    'contrasena incorrecta' dan exactamente el mismo error."""
    if not is_enabled(settings):
        raise LocalAuthError('El login local no esta habilitado en este servidor')

    username = (raw_username or '').strip().lower()
    try:
        _login_rate_limiter.check_and_record(username or '(en blanco)')
    except ratelimit.RateLimitError as exc:
        raise LocalAuthError('Demasiados intentos, espera un momento e intenta de nuevo') from exc

    generic_error = LocalAuthError('Usuario o contrasena incorrectos')
    userid = root.resolve_identity(f'password:{username}')
    if userid is None:
        raise generic_error
    user = root.get_user(userid)
    if user is None or not user.password_hash:
        raise generic_error
    if not verify_password(password, user.password_hash):
        raise generic_error
    return user


def link_password(root, settings, existing_user, raw_username, password):
    """Le agrega una credencial de contrasena a una cuenta ya autenticada (p.ej.
    una que empezo por Fediverso). No toca el username de perfil del usuario --
    el nombre local es solo la llave de login, no reemplaza el nombre mostrado."""
    if not is_enabled(settings):
        raise LocalAuthError('El registro de cuentas locales no esta habilitado en este servidor')

    try:
        username = normalize_username(raw_username)
        validate_password(password, min_length=_min_password_length(settings))
    except CredentialError as exc:
        raise LocalAuthError(str(exc)) from exc

    identity_key = f'password:{username}'
    existing_link = root.resolve_identity(identity_key)
    if existing_link is not None and existing_link != existing_user.userid:
        raise LocalAuthError('Ese nombre de usuario ya esta en uso')

    existing_user.password_hash = hash_password(password)
    root.link_identity(identity_key, existing_user.userid)
    return existing_user


def unlink(root, userid, identity_key):
    """Se niega a quitar la ultima credencial de la cuenta: sin eso, la cuenta
    quedaria sin ninguna forma de volver a entrar."""
    linked_keys = list(root.iter_identities(userid))
    if identity_key not in linked_keys:
        raise LocalAuthError('Esa credencial no esta vinculada a tu cuenta')
    if len(linked_keys) <= 1:
        raise LocalAuthError('No puedes desvincular tu unica credencial de acceso')

    root.unlink_identity(identity_key)
    if identity_key.startswith('password:'):
        user = root.get_user(userid)
        if user is not None:
            user.password_hash = None
