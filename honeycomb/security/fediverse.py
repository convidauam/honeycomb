"""Cliente OAuth2 identity-only contra instancias del Fediverso, via ActivityPub C2S.

El descubrimiento va primero por el estandar: WebFinger (RFC 7033) resuelve el
handle al Actor de ActivityPub, y el propio documento del Actor puede declarar
sus endpoints OAuth (extension de Mastodon/Pleroma: endpoints.oauth*). Cuando
una instancia no los declara (p.ej. mastodon.social), se cae a las rutas
conocidas de la API de Mastodon (/api/v1/apps, /oauth/authorize, /oauth/token).
No implementa federacion completa (inbox/outbox de escritura, firmas HTTP) mas
alla de leer el perfil. Como el acceso es de entrada abierta (cualquier dominio
que el usuario escriba), todas las llamadas salientes pasan por un guard anti-SSRF.
"""

import base64
import hashlib
import hmac
import ipaddress
import secrets
import socket
import urllib.parse

import requests

from . import ratelimit
from ..models.users import DroneUser

REQUEST_TIMEOUT = (3.05, 8)
MAX_REDIRECTS = 3
SCOPE_PROFILE_MODERN = 'profile'
SCOPE_PROFILE_FALLBACK = 'read:accounts'
SCOPE_PUBLISH = 'write:statuses'
AS2_CONTENT_TYPES = (
    'application/activity+json',
    'application/ld+json; profile="https://www.w3.org/ns/activitystreams"',
)

# Defaults usados solo si nadie llama a configure_registration_rate_limiter (p.ej.
# scripts sueltos via pshell). La app real los reemplaza en el arranque leyendo
# settings del .ini -- ver security/__init__.py:includeme.
DEFAULT_REGISTRATION_RATE_WINDOW_SECONDS = 600
DEFAULT_REGISTRATION_RATE_MAX_PER_DOMAIN = 5
DEFAULT_REGISTRATION_RATE_MAX_GLOBAL = 30


class FediverseError(Exception):
    """Error de usuario al resolver/hablar con una instancia del Fediverso."""


_registration_rate_limiter = ratelimit.SlidingWindowLimiter(
    DEFAULT_REGISTRATION_RATE_WINDOW_SECONDS,
    DEFAULT_REGISTRATION_RATE_MAX_PER_DOMAIN,
    DEFAULT_REGISTRATION_RATE_MAX_GLOBAL,
)


def configure_registration_rate_limiter(settings):
    """Llamado una vez al arrancar la app (security/__init__.py:includeme) para que
    el rate limiter de register_app refleje lo configurado en el .ini."""
    global _registration_rate_limiter
    window = ratelimit.positive_int_setting(
        settings, 'fediverse.registration_rate_window_seconds', DEFAULT_REGISTRATION_RATE_WINDOW_SECONDS,
    )
    max_per_domain = ratelimit.limit_setting_or_none(settings, 'fediverse.registration_rate_max_per_domain')
    max_global = ratelimit.limit_setting_or_none(settings, 'fediverse.registration_rate_max_global')
    _registration_rate_limiter = ratelimit.SlidingWindowLimiter(window, max_per_domain, max_global)


def _is_public_ip(ip_text):
    ip = ipaddress.ip_address(ip_text)
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_multicast or ip.is_reserved or ip.is_unspecified
    )


def _assert_public_host(hostname):
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise FediverseError(f"No se pudo resolver el dominio '{hostname}'") from exc
    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise FediverseError(f"No se pudo resolver el dominio '{hostname}'")
    for address in addresses:
        if not _is_public_ip(address):
            raise FediverseError(f"El dominio '{hostname}' resuelve a una direccion no publica")


def _safe_request(method, url, **kwargs):
    """https-only, resuelve y valida el host antes de cada intento, sigue redirects a mano revalidando cada salto."""
    for _ in range(MAX_REDIRECTS + 1):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != 'https':
            raise FediverseError('Solo se permiten URLs https')
        _assert_public_host(parsed.hostname)
        response = requests.request(method, url, timeout=REQUEST_TIMEOUT, allow_redirects=False, **kwargs)
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get('Location')
            if not location:
                raise FediverseError('Redireccion sin Location')
            url = urllib.parse.urljoin(url, location)
            continue
        return response
    raise FediverseError('Demasiadas redirecciones')


def parse_handle(handle):
    """'@usuario@instancia' o 'usuario@instancia' -> (username, domain). Lanza FediverseError si es invalido."""
    if not handle:
        raise FediverseError('Escribe tu handle, por ejemplo usuario@instancia.social')
    handle = handle.strip()
    if handle.startswith('@'):
        handle = handle[1:]
    if '@' not in handle:
        raise FediverseError('El handle debe tener la forma usuario@instancia')
    username, _, domain = handle.partition('@')
    username = username.strip()
    domain = domain.strip().lower()
    if not username or not domain or '.' not in domain or any(c.isspace() for c in domain):
        raise FediverseError('El handle debe tener la forma usuario@instancia')
    return username, domain


def discover_actor_url(username, domain):
    """WebFinger (RFC 7033): handle -> URL del Actor de ActivityPub. Requiere Accept:
    application/jrd+json (algunas instancias, p.ej. unam.social/Pleroma, dan 400 sin
    ese header). None si falla; nunca bloquea el login por si solo."""
    try:
        response = _safe_request(
            'GET', f'https://{domain}/.well-known/webfinger',
            params={'resource': f'acct:{username}@{domain}'},
            headers={'Accept': 'application/jrd+json'},
        )
        if response.status_code != 200:
            return None
        for link in response.json().get('links', []):
            if link.get('rel') == 'self' and link.get('type') in AS2_CONTENT_TYPES:
                href = link.get('href')
                if href:
                    return href
        return None
    except (FediverseError, ValueError, requests.RequestException):
        return None


def fetch_actor(actor_url):
    """GET del documento del Actor (perfil nativo de ActivityPub). None si falla."""
    try:
        response = _safe_request('GET', actor_url, headers={'Accept': 'application/activity+json'})
        if response.status_code != 200:
            return None
        return response.json()
    except (FediverseError, ValueError, requests.RequestException):
        return None


def actor_oauth_endpoints(actor):
    """Endpoints OAuth que el propio Actor declara (extension de Mastodon/Pleroma en
    `endpoints`). Diccionario vacio si el Actor no los expone (p.ej. mastodon.social,
    que solo declara sharedInbox) -- el llamador cae a las rutas conocidas."""
    endpoints = (actor or {}).get('endpoints') or {}
    result = {}
    if endpoints.get('oauthRegistrationEndpoint'):
        result['registration'] = endpoints['oauthRegistrationEndpoint']
    if endpoints.get('oauthAuthorizationEndpoint'):
        result['authorization'] = endpoints['oauthAuthorizationEndpoint']
    if endpoints.get('oauthTokenEndpoint'):
        result['token'] = endpoints['oauthTokenEndpoint']
    return result


def discover_nodeinfo(domain):
    """Best-effort: confirma que el dominio responde como servidor real. Nunca bloquea el login."""
    try:
        response = _safe_request('GET', f'https://{domain}/.well-known/nodeinfo', headers={'Accept': 'application/json'})
        if response.status_code != 200:
            return None
        links = response.json().get('links', [])
        href = links[0].get('href') if links else None
        if not href:
            return None
        info_response = _safe_request('GET', href, headers={'Accept': 'application/json'})
        if info_response.status_code != 200:
            return None
        return info_response.json()
    except (FediverseError, ValueError, requests.RequestException):
        return None


def discover_oauth_metadata(domain):
    """RFC 8414. None en instancias que no lo exponen (comun en Pleroma/instancias viejas)."""
    try:
        response = _safe_request(
            'GET', f'https://{domain}/.well-known/oauth-authorization-server',
            headers={'Accept': 'application/json'},
        )
        if response.status_code != 200:
            return None
        return response.json()
    except (FediverseError, ValueError, requests.RequestException):
        return None


def choose_scope(oauth_metadata):
    """Scope pedido al iniciar sesion: lectura de perfil + capacidad de publicar
    (para compartir logros). scopes_supported suele faltar en instancias viejas
    (p.ej. Pleroma no expone RFC 8414); en ese caso se pide igual, ya que
    write:statuses/profile son estandar en cualquier instancia compatible con
    la API de Mastodon."""
    supported = (oauth_metadata or {}).get('scopes_supported') or []
    profile_scope = SCOPE_PROFILE_MODERN if SCOPE_PROFILE_MODERN in supported else SCOPE_PROFILE_FALLBACK
    return f'{profile_scope} {SCOPE_PUBLISH}'


def supports_pkce(oauth_metadata):
    methods = (oauth_metadata or {}).get('code_challenge_methods_supported') or []
    return 'S256' in methods


def register_app(domain, redirect_uri, scope, client_name='Honeycomb', endpoint=None):
    """endpoint: URL de registro descubierta en el Actor (AP C2S); si falta, cae a
    la ruta de la API de Mastodon (/api/v1/apps), que Pleroma/Akkoma tambien implementan."""
    url = endpoint or f'https://{domain}/api/v1/apps'
    try:
        _registration_rate_limiter.check_and_record(domain)
    except ratelimit.RateLimitError as exc:
        if exc.scope == 'global':
            raise FediverseError('Demasiados registros de apps en este momento, intenta mas tarde') from exc
        raise FediverseError(f"Demasiados intentos de registro para '{domain}', intenta mas tarde") from exc
    try:
        response = _safe_request('POST', url, data={
            'client_name': client_name,
            'redirect_uris': redirect_uri,
            'scopes': scope,
            'website': redirect_uri,
        })
    except requests.RequestException as exc:
        raise FediverseError(f"No se pudo registrar la app en {domain}") from exc
    if response.status_code >= 400:
        raise FediverseError(f"{domain} rechazo el registro de la app")
    payload = response.json()
    client_id = payload.get('client_id')
    client_secret = payload.get('client_secret')
    if not client_id or not client_secret:
        raise FediverseError(f"{domain} no devolvio credenciales de app validas")
    return client_id, client_secret


def generate_pkce_pair():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b'=').decode('ascii')
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')
    return verifier, challenge


def new_state():
    return secrets.token_urlsafe(32)


def states_match(expected, received):
    if not expected or not received:
        return False
    return hmac.compare_digest(expected, received)


def build_authorize_url(domain, client_id, redirect_uri, state, scope, code_challenge=None, endpoint=None):
    """endpoint: URL de autorizacion descubierta en el Actor (AP C2S); si falta, cae
    a la ruta de la API de Mastodon (/oauth/authorize)."""
    base = endpoint or f'https://{domain}/oauth/authorize'
    params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': scope,
        'state': state,
    }
    if code_challenge:
        params['code_challenge'] = code_challenge
        params['code_challenge_method'] = 'S256'
    return base + '?' + urllib.parse.urlencode(params)


def exchange_code(domain, client_id, client_secret, redirect_uri, code, scope, code_verifier=None, endpoint=None):
    """endpoint: URL de intercambio de token descubierta en el Actor (AP C2S); si
    falta, cae a la ruta de la API de Mastodon (/oauth/token)."""
    url = endpoint or f'https://{domain}/oauth/token'
    data = {
        'grant_type': 'authorization_code',
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'code': code,
        'scope': scope,
    }
    if code_verifier:
        data['code_verifier'] = code_verifier
    try:
        response = _safe_request('POST', url, data=data)
    except requests.RequestException as exc:
        raise FediverseError(f"No se pudo intercambiar el codigo con {domain}") from exc
    if response.status_code >= 400:
        raise FediverseError(f"{domain} rechazo el intercambio de codigo")
    token = response.json().get('access_token')
    if not token:
        raise FediverseError(f"{domain} no devolvio un access_token")
    return token


def fetch_account(domain, access_token):
    try:
        response = _safe_request(
            'GET', f'https://{domain}/api/v1/accounts/verify_credentials',
            headers={'Authorization': f'Bearer {access_token}'},
        )
    except requests.RequestException as exc:
        raise FediverseError(f"No se pudo obtener el perfil desde {domain}") from exc
    if response.status_code >= 400:
        raise FediverseError(f"{domain} rechazo verify_credentials")
    return response.json()


def _image_url(value):
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        return _image_url(value.get('url'))
    if isinstance(value, list) and value:
        return _image_url(value[0])
    return None


def canonical_userid(domain, account):
    """Actor URI si esta disponible (identidad ActivityPub nativa); si no, host+id como respaldo estable."""
    actor_uri = account.get('uri')
    if actor_uri:
        return actor_uri
    return f"{domain}#{account.get('id')}"


def account_to_drone_user(domain, account):
    userid = canonical_userid(domain, account)
    username = account.get('username') or account.get('acct') or ''
    handle = account.get('acct') or username
    if handle and '@' not in handle:
        handle = f'{handle}@{domain}'
    display_name = account.get('display_name') or username
    icon = _image_url(account.get('avatar') or account.get('avatar_static') or account.get('icon'))
    background = _image_url(account.get('header') or account.get('header_static') or account.get('image'))
    return DroneUser(userid=userid, display_name=display_name, username=handle, icon=icon, background=background)


def actor_to_drone_user(domain, actor):
    """Mapea el documento del Actor (AS2) a DroneUser. Fuente primaria del perfil en
    el flujo AP C2S; verify_credentials (account_to_drone_user) queda como respaldo
    para instancias donde el Actor no trae `id` usable."""
    userid = actor.get('id') or f"{domain}#{actor.get('preferredUsername', '')}"
    username = actor.get('preferredUsername') or ''
    handle = f'{username}@{domain}' if username else domain
    display_name = actor.get('name') or username or handle
    icon = _image_url(actor.get('icon'))
    background = _image_url(actor.get('image'))
    return DroneUser(
        userid=userid, display_name=display_name, username=handle, icon=icon, background=background,
        actor_url=actor.get('id'), inbox=actor.get('inbox'), outbox=actor.get('outbox'),
    )
