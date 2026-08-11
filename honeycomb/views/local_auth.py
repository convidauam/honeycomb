import urllib.parse

from cornice.resource import resource
from pyramid import traversal
from pyramid.csrf import new_csrf_token, get_csrf_token
from pyramid.httpexceptions import HTTPSeeOther
from pyramid.security import remember
from pyramid.view import view_config

from .. import models
from ..security import local_accounts
from .auth import _safe_next


@view_config(name='register', context=models.BeeHive, renderer='templates/register.jinja2')
def register_view(context, request):
    next_url = _safe_next(request.params.get('next', request.referrer))

    if request.identity:
        return HTTPSeeOther(location=next_url)

    return {
        'next_url': next_url,
        'csrf_token': get_csrf_token(request),
        'error': request.params.get('error'),
        'enabled': local_accounts.is_enabled(request.registry.settings),
    }


@view_config(name='cuenta', context=models.BeeHive, renderer='templates/cuenta.jinja2')
def account_view(context, request):
    """Muestra las credenciales vinculadas a la cuenta y permite vincular o
    desvincular. Es donde el encargo de dejar la separacion de identidades
    visible (no solo documentada) se hace concreto en la interfaz."""
    if not request.identity:
        return HTTPSeeOther(location='/login?next=' + urllib.parse.quote('/cuenta'))

    root = traversal.find_root(resource=context)
    identities = sorted(root.iter_identities(request.identity.userid))
    return {
        'identities': identities,
        'has_password': bool(request.identity.password_hash),
        'error': request.params.get('error'),
        'csrf_token': get_csrf_token(request),
        'local_accounts_enabled': local_accounts.is_enabled(request.registry.settings),
    }


@resource(path='/api/v1/auth/register', cors_origins=('*',), factory='honeycomb.root_factory')
class RegisterResource:
    """Registro abierto de una cuenta local nueva (usuario + contrasena)."""

    def __init__(self, request, context=None):
        self.request = request
        self.context = context

    def post(self):
        request = self.request
        next_url = _safe_next(request.params.get('next'))
        root = traversal.find_root(resource=self.context)

        try:
            user = local_accounts.register(
                root, request.registry.settings,
                request.params.get('username', ''), request.params.get('password', ''),
            )
        except local_accounts.LocalAuthError as exc:
            return HTTPSeeOther(location=f"/register?error={urllib.parse.quote(str(exc))}")

        new_csrf_token(request)
        headers = remember(request, user.userid)
        return HTTPSeeOther(location=next_url, headers=headers)


@resource(path='/api/v1/auth/local', cors_origins=('*',), factory='honeycomb.root_factory')
class LocalLoginResource:
    """Login con una cuenta local ya existente."""

    def __init__(self, request, context=None):
        self.request = request
        self.context = context

    def post(self):
        request = self.request
        next_url = _safe_next(request.params.get('next'))
        root = traversal.find_root(resource=self.context)

        try:
            user = local_accounts.authenticate(
                root, request.registry.settings,
                request.params.get('username', ''), request.params.get('password', ''),
            )
        except local_accounts.LocalAuthError as exc:
            return HTTPSeeOther(location=f"/login?error={urllib.parse.quote(str(exc))}")

        new_csrf_token(request)
        headers = remember(request, user.userid)
        return HTTPSeeOther(location=next_url, headers=headers)


@resource(path='/api/v1/auth/link/password', cors_origins=('*',), factory='honeycomb.root_factory')
class LinkPasswordResource:
    """Le agrega una credencial de contrasena a la cuenta ya autenticada."""

    def __init__(self, request, context=None):
        self.request = request
        self.context = context

    def post(self):
        request = self.request
        if not request.identity:
            request.response.status = 401
            return {'error': 'Unauthorized'}

        root = traversal.find_root(resource=self.context)
        try:
            local_accounts.link_password(
                root, request.registry.settings, request.identity,
                request.params.get('username', ''), request.params.get('password', ''),
            )
        except local_accounts.LocalAuthError as exc:
            return HTTPSeeOther(location=f"/cuenta?error={urllib.parse.quote(str(exc))}")

        new_csrf_token(request)
        return HTTPSeeOther(location='/cuenta')


@resource(path='/api/v1/auth/unlink', cors_origins=('*',), factory='honeycomb.root_factory')
class UnlinkResource:
    """Quita una credencial de la cuenta autenticada. Se niega a quitar la ultima."""

    def __init__(self, request, context=None):
        self.request = request
        self.context = context

    def post(self):
        request = self.request
        if not request.identity:
            request.response.status = 401
            return {'error': 'Unauthorized'}

        root = traversal.find_root(resource=self.context)
        try:
            local_accounts.unlink(root, request.identity.userid, request.params.get('identity_key', ''))
        except local_accounts.LocalAuthError as exc:
            return HTTPSeeOther(location=f"/cuenta?error={urllib.parse.quote(str(exc))}")

        new_csrf_token(request)
        return HTTPSeeOther(location='/cuenta')
