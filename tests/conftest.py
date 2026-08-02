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
def fediverse_stub(monkeypatch):
    """Monkeypatches el modulo fediverse con una instancia fake bien portada, sin red real.

    Tambien puentea BeeHive.upsert_user/SecurityPolicy.load_identity por fuera de ZODB:
    el fixture testapp aborta cada request en su propia transaccion (ver nota en
    docs/comunicacion-videojuegos-api.md), asi que sin este puente un usuario logueado
    en un request no existiria todavia para el siguiente. Es solo para pruebas; el
    codigo de produccion sigue usando ZODB en todo momento.
    """
    from honeycomb.models.beehive import BeeHive
    from honeycomb.security import fediverse

    test_users = {}
    test_oauth_apps = {}

    monkeypatch.setattr(fediverse, 'discover_nodeinfo', lambda domain: {'software': {'name': 'testodon'}})
    monkeypatch.setattr(fediverse, 'discover_oauth_metadata', lambda domain: {
        'scopes_supported': ['read:accounts'],
        'code_challenge_methods_supported': ['S256'],
    })
    monkeypatch.setattr(
        fediverse, 'register_app',
        lambda domain, redirect_uri, scope, client_name='Honeycomb': ('fake-client-id', 'fake-client-secret'),
    )
    monkeypatch.setattr(
        fediverse, 'exchange_code',
        lambda domain, client_id, client_secret, redirect_uri, code, scope, code_verifier=None: 'fake-access-token',
    )
    monkeypatch.setattr(fediverse, 'fetch_account', lambda domain, access_token: dict(FAKE_FEDIVERSE_ACCOUNT))

    original_upsert_user = BeeHive.upsert_user

    def patched_upsert_user(self, drone_user):
        test_users[drone_user.userid] = drone_user
        return original_upsert_user(self, drone_user)

    original_get_user = BeeHive.get_user

    def patched_get_user(self, userid):
        if userid in test_users:
            return test_users[userid]
        return original_get_user(self, userid)

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

    monkeypatch.setattr(BeeHive, 'upsert_user', patched_upsert_user)
    monkeypatch.setattr(BeeHive, 'get_user', patched_get_user)
    monkeypatch.setattr(BeeHive, 'set_oauth_app', patched_set_oauth_app)
    monkeypatch.setattr(BeeHive, 'get_oauth_app', patched_get_oauth_app)

    return {
        'domain': FAKE_FEDIVERSE_DOMAIN,
        'userid': FAKE_FEDIVERSE_ACCOUNT['uri'],
        'handle': f"tester@{FAKE_FEDIVERSE_DOMAIN}",
    }


@pytest.fixture
def login_as_fediverse_user(testapp, fediverse_stub):
    """Corre el flujo real de login (POST /api/v1/auth/login -> GET /api/v1/auth/callback) contra la instancia fake."""
    def _login(next_url='/'):
        login_page = testapp.get('/login', status=200)
        csrf_token = login_page.form['csrf_token'].value
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
def dummy_config(dummy_request):
    """
    A dummy :class:`pyramid.config.Configurator` object.  This allows for
    mock configuration, including configuration for ``dummy_request``, as well
    as pushing the appropriate threadlocals.

    """
    with testConfig(request=dummy_request) as config:
        yield config
