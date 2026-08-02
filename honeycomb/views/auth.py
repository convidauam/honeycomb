import urllib.parse

from cornice.resource import resource
from pyramid import traversal
from pyramid.csrf import new_csrf_token, get_csrf_token
from pyramid.httpexceptions import HTTPSeeOther, HTTPNotFound
from pyramid.security import (
    remember,
    forget,
    NO_PERMISSION_REQUIRED,
)

from pyramid.view import (
    forbidden_view_config,
    view_config,
)

from deform import Form, ValidationFailure, Button

from .. import security
from .. import models
from ..security import fediverse


def _safe_next(raw_next):
    """Solo permite rutas relativas de un segmento inicial ('/algo'), nunca '//host' ni URLs absolutas."""
    if not raw_next or not raw_next.startswith('/') or raw_next.startswith('//'):
        return '/'
    return raw_next


def _denylisted_domains(settings):
    raw = settings.get('fediverse.denylist', '') or ''
    return {d.strip().lower() for d in raw.split() if d.strip()}


@view_config(name="login", context=models.BeeHive, renderer='templates/login.jinja2')
@forbidden_view_config(renderer='templates/login.jinja2')
def login_view(context, request):
    next_url = _safe_next(request.params.get('next', request.referrer))

    if request.identity:
        return HTTPSeeOther(location=next_url)

    # get_csrf_token reusa el token vigente; new_csrf_token lo invalidaba en cada render.
    return {
        'next_url': next_url,
        'csrf_token': get_csrf_token(request),
        'error': request.params.get('error'),
    }


@view_config(name='logout', context=models.BeeHive)
def logout_view(context, request):
    assert request.identity
    next_url = "/"
    new_csrf_token(request)
    headers = forget(request)
    return HTTPSeeOther(location=next_url, headers=headers)


@resource(path='/api/v1/auth/login', cors_origins=('*',), factory='honeycomb.root_factory')
class FediverseLoginResource:
    """Inicia el login: resuelve el handle, registra/reusa la app OAuth de esa instancia y redirige a ella."""

    def __init__(self, request, context=None):
        self.request = request
        self.context = context

    def post(self):
        request = self.request
        handle = request.params.get('handle', '')
        next_url = _safe_next(request.params.get('next'))

        try:
            _username, domain = fediverse.parse_handle(handle)
        except fediverse.FediverseError as exc:
            return HTTPSeeOther(location=f"/login?error={urllib.parse.quote(str(exc))}")

        if domain in _denylisted_domains(request.registry.settings):
            error = f"'{domain}' no esta permitido en este servidor"
            return HTTPSeeOther(location=f"/login?error={urllib.parse.quote(error)}")

        # application_url incluye el prefijo de montaje (p.ej. /backend detras del
        # reverse proxy), a diferencia de host_url que solo trae scheme+host+puerto.
        redirect_uri = request.application_url + '/api/v1/auth/callback'
        root = traversal.find_root(resource=self.context)

        try:
            oauth_metadata = fediverse.discover_oauth_metadata(domain)
            scope = fediverse.choose_scope(oauth_metadata)

            cached_app = root.get_oauth_app(domain)
            if cached_app is None:
                # dominio nunca visto: confirma que hay un servidor real antes de gastar el registro de app
                if fediverse.discover_nodeinfo(domain) is None:
                    raise fediverse.FediverseError(f"No encontramos un servidor del Fediverso en '{domain}'")
                client_id, client_secret = fediverse.register_app(domain, redirect_uri, scope)
                root.set_oauth_app(domain, client_id, client_secret)
            else:
                client_id, client_secret = cached_app['client_id'], cached_app['client_secret']

            code_verifier = code_challenge = None
            if fediverse.supports_pkce(oauth_metadata):
                code_verifier, code_challenge = fediverse.generate_pkce_pair()

            state = fediverse.new_state()
            authorize_url = fediverse.build_authorize_url(domain, client_id, redirect_uri, state, scope, code_challenge)
        except fediverse.FediverseError as exc:
            return HTTPSeeOther(location=f"/login?error={urllib.parse.quote(str(exc))}")

        # client_id/secret tambien viajan en la sesion (de un solo uso, se limpian en el
        # callback) para que ESTE flujo no dependa de releer la cache de ZODB en el
        # siguiente request; la cache en ZODB solo acelera logins FUTUROS al mismo dominio.
        request.session['oauth_state'] = state
        request.session['oauth_domain'] = domain
        request.session['oauth_scope'] = scope
        request.session['oauth_code_verifier'] = code_verifier
        request.session['oauth_next'] = next_url
        request.session['oauth_client_id'] = client_id
        request.session['oauth_client_secret'] = client_secret

        return HTTPSeeOther(location=authorize_url)


@resource(path='/api/v1/auth/callback', cors_origins=('*',), factory='honeycomb.root_factory')
class FediverseCallbackResource:
    """Completa el login: valida state, intercambia el code, lee el perfil y crea la sesion."""

    def __init__(self, request, context=None):
        self.request = request
        self.context = context

    def get(self):
        request = self.request
        received_state = request.params.get('state')
        expected_state = request.session.pop('oauth_state', None)
        domain = request.session.pop('oauth_domain', None)
        scope = request.session.pop('oauth_scope', None)
        code_verifier = request.session.pop('oauth_code_verifier', None)
        next_url = request.session.pop('oauth_next', None) or '/'
        client_id = request.session.pop('oauth_client_id', None)
        client_secret = request.session.pop('oauth_client_secret', None)

        if not fediverse.states_match(expected_state, received_state) or not domain or not client_id:
            return HTTPSeeOther(location='/login?error=' + urllib.parse.quote('Sesion de login invalida o expirada'))

        code = request.params.get('code')
        if not code:
            return HTTPSeeOther(location='/login?error=' + urllib.parse.quote('El login fue cancelado'))

        root = traversal.find_root(resource=self.context)
        # application_url incluye el prefijo de montaje (p.ej. /backend detras del
        # reverse proxy), a diferencia de host_url que solo trae scheme+host+puerto.
        redirect_uri = request.application_url + '/api/v1/auth/callback'

        try:
            access_token = fediverse.exchange_code(
                domain, client_id, client_secret,
                redirect_uri, code, scope, code_verifier,
            )
            account = fediverse.fetch_account(domain, access_token)
        except fediverse.FediverseError as exc:
            return HTTPSeeOther(location='/login?error=' + urllib.parse.quote(str(exc)))

        drone_user = fediverse.account_to_drone_user(domain, account)
        root.upsert_user(drone_user)

        new_csrf_token(request)
        headers = remember(request, drone_user.userid)
        return HTTPSeeOther(location=_safe_next(next_url), headers=headers)
