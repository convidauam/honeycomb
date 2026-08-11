import urllib.parse

from cornice.resource import resource
from pyramid import traversal
from pyramid.csrf import new_csrf_token, get_csrf_token
from pyramid.httpexceptions import HTTPSeeOther
from pyramid.security import remember, forget

from pyramid.view import (
    forbidden_view_config,
    view_config,
)

from .. import models
from ..security import fediverse, tokenstore


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
    next_url = "/"
    if not request.identity:
        return HTTPSeeOther(location=next_url)
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
        # Si ya hay sesion, este login no crea una cuenta nueva: vincula el
        # Fediverso resuelto a la cuenta actual (ver FediverseCallbackResource).
        link_to = request.identity.userid if request.identity else None

        try:
            username, domain = fediverse.parse_handle(handle)
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
            # ActivityPub C2S primero: WebFinger -> Actor -> endpoints que el propio
            # Actor declare (extension de Mastodon/Pleroma). Si la instancia no los
            # declara (p.ej. mastodon.social), se cae a las rutas de la API de Mastodon.
            actor_url = fediverse.discover_actor_url(username, domain)
            actor = fediverse.fetch_actor(actor_url) if actor_url else None
            actor_endpoints = fediverse.actor_oauth_endpoints(actor)

            oauth_metadata = fediverse.discover_oauth_metadata(domain)
            scope = fediverse.choose_scope(oauth_metadata)

            cached_app = root.get_oauth_app(domain)
            if cached_app is None:
                # Si ya resolvimos el Actor, eso ya confirma que hay un servidor AP real;
                # si no, confirma con nodeinfo antes de gastar un registro de app.
                if actor is None and fediverse.discover_nodeinfo(domain) is None:
                    raise fediverse.FediverseError(f"No encontramos un servidor del Fediverso en '{domain}'")
                client_id, client_secret = fediverse.register_app(
                    domain, redirect_uri, scope, endpoint=actor_endpoints.get('registration'),
                )
                root.set_oauth_app(domain, client_id, client_secret)
            else:
                client_id, client_secret = cached_app['client_id'], cached_app['client_secret']

            code_verifier = code_challenge = None
            if fediverse.supports_pkce(oauth_metadata):
                code_verifier, code_challenge = fediverse.generate_pkce_pair()

            state = fediverse.new_state()
            authorize_url = fediverse.build_authorize_url(
                domain, client_id, redirect_uri, state, scope, code_challenge,
                endpoint=actor_endpoints.get('authorization'),
            )
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
        request.session['oauth_token_endpoint'] = actor_endpoints.get('token')
        request.session['oauth_actor'] = actor
        request.session['oauth_link_to'] = link_to

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
        token_endpoint = request.session.pop('oauth_token_endpoint', None)
        actor = request.session.pop('oauth_actor', None)
        link_to = request.session.pop('oauth_link_to', None)

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
                endpoint=token_endpoint,
            )
            # El Actor ya resuelto por WebFinger (antes de la aprobacion) es la fuente
            # primaria del perfil; verify_credentials solo si no trajo un `id` usable.
            if actor and actor.get('id'):
                drone_user = fediverse.actor_to_drone_user(domain, actor)
            else:
                account = fediverse.fetch_account(domain, access_token)
                drone_user = fediverse.account_to_drone_user(domain, account)

            if link_to is not None and root.get_user(link_to) is None:
                raise fediverse.FediverseError('Tu sesion expiro, intenta vincular de nuevo')

            existing_link = root.resolve_identity(f'fediverse:{drone_user.userid}')
            if link_to is not None and existing_link is not None and existing_link != link_to:
                raise fediverse.FediverseError('Esa cuenta del Fediverso ya esta vinculada a otra cuenta de Honeycomb')
        except fediverse.FediverseError as exc:
            return HTTPSeeOther(location='/login?error=' + urllib.parse.quote(str(exc)))

        # Sin honeycomb.token_encryption_key configurada, encrypt_token regresa None:
        # el token nunca se guarda en claro, y publicar al Fediverso queda deshabilitado
        # hasta que el administrador de la instancia provea una clave.
        encrypted_token = tokenstore.encrypt_token(request.registry.settings, access_token)

        # userid primario de la cuenta: el que ya tenia esta credencial vinculada
        # (si la vinculacion ya existia), o al que se esta vinculando ahora, o el
        # propio del Actor si es la primera vez que se ve (login normal, sin
        # vinculacion -- el caso de siempre, cero migracion para cuentas viejas).
        primary_userid = link_to or existing_link or drone_user.userid
        identity_key = f'fediverse:{drone_user.userid}'

        existing = root.get_user(primary_userid)
        if existing is None:
            drone_user.userid = primary_userid
            drone_user.access_token_encrypted = encrypted_token
            root.upsert_user(drone_user)
        else:
            # Nunca reemplazar al usuario existente entero: perderia password_hash
            # u otras credenciales ya vinculadas (ver update_profile en users.py).
            existing.update_profile(
                display_name=drone_user.display_name, username=drone_user.username,
                icon=drone_user.icon, background=drone_user.background,
                actor_url=drone_user.actor_url, inbox=drone_user.inbox, outbox=drone_user.outbox,
            )
            existing.access_token_encrypted = encrypted_token

        root.link_identity(identity_key, primary_userid)
        if link_to is not None and existing_link is None:
            # Primera vez que se vincula este Actor: si ya tenia progreso propio
            # (jugo antes de vincular), se funde con el de la cuenta primaria.
            root.merge_game_data(drone_user.userid, primary_userid)

        new_csrf_token(request)
        if link_to is not None:
            # Ya habia sesion iniciada como link_to; no hace falta remember() de
            # nuevo, el principal de la cookie no cambia.
            return HTTPSeeOther(location=_safe_next(next_url))
        headers = remember(request, primary_userid)
        return HTTPSeeOther(location=_safe_next(next_url), headers=headers)
