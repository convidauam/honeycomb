"""Cliente OAuth2 identity-only contra instancias del Fediverso (API estilo Mastodon).

No implementa federacion ActivityPub (inbox/outbox, firmas HTTP): solo resuelve
la instancia de un handle, registra una app OAuth por dominio, corre el flujo
de authorization code, y lee el perfil via verify_credentials. Como el acceso
es de entrada abierta (cualquier dominio que el usuario escriba), todas las
llamadas salientes pasan por un guard anti-SSRF.
"""

import base64
import hashlib
import hmac
import ipaddress
import secrets
import socket
import threading
import time
import urllib.parse

import requests

from ..models.users import DroneUser

REQUEST_TIMEOUT = (3.05, 8)
MAX_REDIRECTS = 3
SCOPE_MODERN = 'profile'
SCOPE_FALLBACK = 'read:accounts'

REGISTRATION_RATE_WINDOW_SECONDS = 600
REGISTRATION_RATE_MAX_PER_DOMAIN = 5
REGISTRATION_RATE_MAX_GLOBAL = 30


class FediverseError(Exception):
    """Error de usuario al resolver/hablar con una instancia del Fediverso."""


class _RegistrationRateLimiter:
    """Limita cuantas veces se puede llamar a register_app: por dominio y en total.

    En memoria de proceso (un solo worker via waitress); si el registro de apps
    empieza a fallar mucho o se despliega con varios workers, mover esto a un
    almacen compartido (p.ej. la misma ZODB, o un cache externo).
    """

    def __init__(self, window_seconds, max_per_domain, max_global):
        self.window_seconds = window_seconds
        self.max_per_domain = max_per_domain
        self.max_global = max_global
        self._lock = threading.Lock()
        self._by_domain = {}
        self._global = []

    def check_and_record(self, domain):
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            self._global = [t for t in self._global if t > cutoff]
            if len(self._global) >= self.max_global:
                raise FediverseError('Demasiados registros de apps en este momento, intenta mas tarde')

            domain_attempts = [t for t in self._by_domain.get(domain, []) if t > cutoff]
            if len(domain_attempts) >= self.max_per_domain:
                raise FediverseError(f"Demasiados intentos de registro para '{domain}', intenta mas tarde")

            domain_attempts.append(now)
            self._by_domain[domain] = domain_attempts
            self._global.append(now)


_registration_rate_limiter = _RegistrationRateLimiter(
    REGISTRATION_RATE_WINDOW_SECONDS, REGISTRATION_RATE_MAX_PER_DOMAIN, REGISTRATION_RATE_MAX_GLOBAL,
)


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
    supported = (oauth_metadata or {}).get('scopes_supported') or []
    return SCOPE_MODERN if SCOPE_MODERN in supported else SCOPE_FALLBACK


def supports_pkce(oauth_metadata):
    methods = (oauth_metadata or {}).get('code_challenge_methods_supported') or []
    return 'S256' in methods


def register_app(domain, redirect_uri, scope, client_name='Honeycomb'):
    _registration_rate_limiter.check_and_record(domain)
    try:
        response = _safe_request('POST', f'https://{domain}/api/v1/apps', data={
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


def build_authorize_url(domain, client_id, redirect_uri, state, scope, code_challenge=None):
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
    return f'https://{domain}/oauth/authorize?' + urllib.parse.urlencode(params)


def exchange_code(domain, client_id, client_secret, redirect_uri, code, scope, code_verifier=None):
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
        response = _safe_request('POST', f'https://{domain}/oauth/token', data=data)
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
