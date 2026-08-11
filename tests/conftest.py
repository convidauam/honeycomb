import os
import urllib.parse
from pyramid.paster import get_appsettings
from pyramid.scripting import prepare
from pyramid.testing import DummyRequest, testConfig
import pytest
import transaction
import webtest

from honeycomb import main

FAKE_FEDIVERSE_DOMAIN = 'fake.fediverse.test'
FAKE_FEDIVERSE_ACCOUNT = {
    'id': '1',
    'uri': 'https://fake.fediverse.test/users/tester',
    'username': 'tester',
    'acct': 'tester',
    'display_name': 'Test User',
    'avatar': 'https://fake.fediverse.test/avatar.png',
    'header': 'https://fake.fediverse.test/header.png',
}
# Actor AS2 sin endpoints.oauth* -- ejercita el fallback a las rutas de la API de
# Mastodon, igual que mastodon.social en la verificacion en vivo.
FAKE_ACTOR = {
    'id': 'https://fake.fediverse.test/users/tester',
    'type': 'Person',
    'preferredUsername': 'tester',
    'name': 'Test User',
    'icon': {'url': 'https://fake.fediverse.test/avatar.png'},
    'image': {'url': 'https://fake.fediverse.test/header.png'},
    'inbox': 'https://fake.fediverse.test/users/tester/inbox',
    'outbox': 'https://fake.fediverse.test/users/tester/outbox',
    'endpoints': {},
}


def pytest_addoption(parser):
    parser.addoption('--ini', action='store', metavar='INI_FILE')

@pytest.fixture(scope='session')
def ini_file(request):
    # potentially grab this path from a pytest option
    return os.path.abspath(request.config.option.ini or 'testing.ini')

@pytest.fixture(scope='session')
def app_settings(ini_file):
    return get_appsettings(ini_file)

@pytest.fixture(scope='session')
def app(app_settings):
    return main({}, **app_settings)

@pytest.fixture
def tm():
    tm = transaction.manager
    tm.begin()
    tm.doom()

    yield tm

    tm.abort()

@pytest.fixture
def testapp(app, tm):
    testapp = webtest.TestApp(app, extra_environ={
        'HTTP_HOST': 'example.com',
        'tm.active': True,
        'tm.manager': tm,
    })

    return testapp

@pytest.fixture
def app_request(app, tm):
    """
    A real request.

    This request is almost identical to a real request but it has some
    drawbacks in tests as it's harder to mock data and is heavier.

    """
    with prepare(registry=app.registry) as env:
        request = env['request']
        request.host = 'example.com'
        yield request

@pytest.fixture
def dummy_request(tm):
    """
    A lightweight dummy request.

    This request is ultra-lightweight and should be used only when the request
    itself is not a large focus in the call-stack.  It is much easier to mock
    and control side-effects using this object, however:

    - It does not have request extensions applied.
    - Threadlocals are not properly pushed.

    """
    request = DummyRequest()
    request.host = 'example.com'
    request.tm = tm

    return request

@pytest.fixture
def identity_bridge(monkeypatch):
    """Puentea BeeHive.get_user/upsert_user/resolve_identity/link_identity/
    unlink_identity/iter_identities por fuera de ZODB: el fixture testapp aborta
    cada request en su propia transaccion (ver nota en
    docs/comunicacion-videojuegos-api.md), asi que sin este puente una cuenta
    creada en un request no existiria todavia para el siguiente. Compartido por
    cualquier flujo de mas de un request, sea login por Fediverso, registro
    local, o vincular ambos. Es solo para pruebas; el codigo de produccion
    sigue usando ZODB en todo momento.
    """
    from honeycomb.models.beehive import BeeHive

    users = {}
    identities = {}

    original_upsert_user = BeeHive.upsert_user

    def patched_upsert_user(self, drone_user):
        users[drone_user.userid] = drone_user
        return original_upsert_user(self, drone_user)

    original_get_user = BeeHive.get_user

    def patched_get_user(self, userid):
        if userid in users:
            return users[userid]
        return original_get_user(self, userid)

    original_resolve_identity = BeeHive.resolve_identity

    def patched_resolve_identity(self, key):
        if key in identities:
            return identities[key]
        return original_resolve_identity(self, key)

    original_link_identity = BeeHive.link_identity

    def patched_link_identity(self, key, userid):
        identities[key] = userid
        return original_link_identity(self, key, userid)

    original_unlink_identity = BeeHive.unlink_identity

    def patched_unlink_identity(self, key):
        identities.pop(key, None)
        return original_unlink_identity(self, key)

    def patched_iter_identities(self, userid):
        for key, linked_userid in identities.items():
            if linked_userid == userid:
                yield key

    monkeypatch.setattr(BeeHive, 'upsert_user', patched_upsert_user)
    monkeypatch.setattr(BeeHive, 'get_user', patched_get_user)
    monkeypatch.setattr(BeeHive, 'resolve_identity', patched_resolve_identity)
    monkeypatch.setattr(BeeHive, 'link_identity', patched_link_identity)
    monkeypatch.setattr(BeeHive, 'unlink_identity', patched_unlink_identity)
    monkeypatch.setattr(BeeHive, 'iter_identities', patched_iter_identities)

    return {'users': users, 'identities': identities}


@pytest.fixture
def fediverse_stub(monkeypatch, identity_bridge):
    """Monkeypatches el modulo fediverse con una instancia fake bien portada, sin
    red real. La persistencia entre requests la da identity_bridge; aqui solo se
    puentea lo especifico del OAuth del Fediverso (set_oauth_app/get_oauth_app).
    """
    from honeycomb.models.beehive import BeeHive
    from honeycomb.security import fediverse

    test_oauth_apps = {}

    monkeypatch.setattr(fediverse, 'discover_actor_url', lambda username, domain: FAKE_ACTOR['id'])
    monkeypatch.setattr(fediverse, 'fetch_actor', lambda actor_url: dict(FAKE_ACTOR))
    monkeypatch.setattr(fediverse, 'discover_nodeinfo', lambda domain: {'software': {'name': 'testodon'}})
    monkeypatch.setattr(fediverse, 'discover_oauth_metadata', lambda domain: {
        'scopes_supported': ['read:accounts'],
        'code_challenge_methods_supported': ['S256'],
    })
    monkeypatch.setattr(
        fediverse, 'register_app',
        lambda domain, redirect_uri, scope, client_name='Honeycomb', endpoint=None: ('fake-client-id', 'fake-client-secret'),
    )
    monkeypatch.setattr(
        fediverse, 'exchange_code',
        lambda domain, client_id, client_secret, redirect_uri, code, scope, code_verifier=None, endpoint=None: 'fake-access-token',
    )
    monkeypatch.setattr(fediverse, 'fetch_account', lambda domain, access_token: dict(FAKE_FEDIVERSE_ACCOUNT))

    original_set_oauth_app = BeeHive.set_oauth_app

    def patched_set_oauth_app(self, domain, client_id, client_secret):
        result = original_set_oauth_app(self, domain, client_id, client_secret)
        test_oauth_apps[domain] = result
        return result

    original_get_oauth_app = BeeHive.get_oauth_app

    def patched_get_oauth_app(self, domain):
        if domain in test_oauth_apps:
            return test_oauth_apps[domain]
        return original_get_oauth_app(self, domain)

    monkeypatch.setattr(BeeHive, 'set_oauth_app', patched_set_oauth_app)
    monkeypatch.setattr(BeeHive, 'get_oauth_app', patched_get_oauth_app)

    return {
        'domain': FAKE_FEDIVERSE_DOMAIN,
        'userid': FAKE_FEDIVERSE_ACCOUNT['uri'],
        'handle': f"tester@{FAKE_FEDIVERSE_DOMAIN}",
        # Puente directo al DroneUser persistido (ver identity_bridge); util para
        # que los tests inspeccionen campos que no se exponen via API (p.ej. el
        # token cifrado) sin tener que abrir una ruta de depuracion insegura.
        'get_stored_user': lambda: identity_bridge['users'].get(FAKE_FEDIVERSE_ACCOUNT['uri']),
    }


@pytest.fixture
def login_as_fediverse_user(testapp, fediverse_stub):
    """Corre el flujo real de login (POST /api/v1/auth/login -> GET /api/v1/auth/callback) contra la instancia fake."""
    def _login(next_url='/'):
        login_page = testapp.get('/login', status=200)
        csrf_token = login_page.forms['fediverse-login-form']['csrf_token'].value
        start_resp = testapp.post('/api/v1/auth/login', {
            'handle': fediverse_stub['handle'],
            'csrf_token': csrf_token,
            'next': next_url,
        }, status=303)
        authorize_url = start_resp.headers['Location']
        state = urllib.parse.parse_qs(urllib.parse.urlsplit(authorize_url).query)['state'][0]
        testapp.get('/api/v1/auth/callback', {'code': 'fake-code', 'state': state}, status=303)
        return fediverse_stub
    return _login


@pytest.fixture
def register_as_local_user(testapp, identity_bridge):
    """Corre el registro real (GET /register -> POST /api/v1/auth/register) y deja
    la sesion autenticada como esa cuenta nueva."""
    def _register(username='alice', password='correct horse battery staple', next_url='/'):
        page = testapp.get('/register', status=200)
        csrf_token = page.forms['register-form']['csrf_token'].value
        testapp.post('/api/v1/auth/register', {
            'username': username, 'password': password, 'csrf_token': csrf_token, 'next': next_url,
        }, status=303)
        return {'username': username, 'password': password}
    return _register


@pytest.fixture
def login_as_local_user(testapp):
    """Corre el login local real (GET /login -> POST /api/v1/auth/local)."""
    def _login(username, password, next_url='/'):
        page = testapp.get('/login', status=200)
        csrf_token = page.forms['local-login-form']['csrf_token'].value
        return testapp.post('/api/v1/auth/local', {
            'username': username, 'password': password, 'csrf_token': csrf_token, 'next': next_url,
        }, status=303)
    return _login


@pytest.fixture
def game_data_bridge(monkeypatch):
    """Puentea BeeHive.get_game_data/merge_game_data por fuera de ZODB, igual que
    identity_bridge hace con los usuarios: necesario para probar flujos que
    abarcan mas de un request (otorgar un logro y despues compartirlo, o jugar
    y despues vincular la cuenta a otra)."""
    from honeycomb.models.beehive import BeeHive

    store = {}
    original_get_game_data = BeeHive.get_game_data
    original_merge_game_data = BeeHive.merge_game_data

    def patched_get_game_data(self, userid, nodeid, create=False):
        key = (userid, nodeid)
        if key in store:
            return store[key]
        if not create:
            return None
        record = original_get_game_data(self, userid, nodeid, create=True)
        store[key] = record
        return record

    class _FakeGameDataHost:
        def __init__(self, buckets):
            self.__game_data__ = buckets

    def patched_merge_game_data(self, from_userid, into_userid):
        # Reusa la logica real de fusion operando sobre un host de mentiras cuyo
        # __game_data__ refleja el store del bridge, y despues aplana el
        # resultado de vuelta -- asi la regla de fusion no se duplica aqui.
        buckets = {}
        for (userid, nodeid), record in store.items():
            buckets.setdefault(userid, {})[nodeid] = record
        original_merge_game_data(_FakeGameDataHost(buckets), from_userid, into_userid)
        store.clear()
        for userid, bucket in buckets.items():
            for nodeid, record in bucket.items():
                store[(userid, nodeid)] = record

    monkeypatch.setattr(BeeHive, 'get_game_data', patched_get_game_data)
    monkeypatch.setattr(BeeHive, 'merge_game_data', patched_merge_game_data)
    return store


@pytest.fixture
def dummy_config(dummy_request):
    """
    A dummy :class:`pyramid.config.Configurator` object.  This allows for
    mock configuration, including configuration for ``dummy_request``, as well
    as pushing the appropriate threadlocals.

    """
    with testConfig(request=dummy_request) as config:
        yield config
