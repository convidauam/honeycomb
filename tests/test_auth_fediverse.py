import urllib.parse


def _redirects_to_login_error(location):
    parts = urllib.parse.urlsplit(location)
    return parts.path == '/login' and 'error' in urllib.parse.parse_qs(parts.query)


def test_login_page_renders_form(testapp):
    page = testapp.get('/login', status=200)
    fediverse_form = page.forms['fediverse-login-form']
    assert 'csrf_token' in fediverse_form.fields
    assert 'handle' in fediverse_form.fields
    local_form = page.forms['local-login-form']
    assert 'username' in local_form.fields
    assert 'password' in local_form.fields


def test_login_page_csrf_token_stable_across_reloads(testapp):
    first = testapp.get('/login', status=200).forms['fediverse-login-form']['csrf_token'].value
    second = testapp.get('/login', status=200).forms['fediverse-login-form']['csrf_token'].value
    assert first == second


def test_login_start_rejects_malformed_handle(testapp):
    login_page = testapp.get('/login', status=200)
    csrf_token = login_page.forms['fediverse-login-form']['csrf_token'].value
    resp = testapp.post('/api/v1/auth/login', {'handle': 'not-a-handle', 'csrf_token': csrf_token}, status=303)
    assert _redirects_to_login_error(resp.headers['Location'])


def test_login_start_redirects_to_authorize_url(testapp, fediverse_stub):
    login_page = testapp.get('/login', status=200)
    csrf_token = login_page.forms['fediverse-login-form']['csrf_token'].value
    resp = testapp.post('/api/v1/auth/login', {
        'handle': fediverse_stub['handle'],
        'csrf_token': csrf_token,
    }, status=303)
    location = resp.headers['Location']
    assert location.startswith(f"https://{fediverse_stub['domain']}/oauth/authorize?")
    params = urllib.parse.parse_qs(urllib.parse.urlsplit(location).query)
    assert params['client_id'] == ['fake-client-id']
    assert params['response_type'] == ['code']
    assert 'state' in params
    assert 'code_challenge' in params  # el stub declara soporte S256


def test_login_start_uses_actor_declared_oauth_endpoints(testapp, fediverse_stub, monkeypatch):
    """Cuando el Actor si declara endpoints.oauth* (caso unam.social/Pleroma), se usan
    esos en vez de las rutas hardcodeadas de la API de Mastodon."""
    from honeycomb.security import fediverse

    actor_with_endpoints = {
        'id': f"https://{fediverse_stub['domain']}/users/tester",
        'preferredUsername': 'tester',
        'name': 'Test User',
        'inbox': f"https://{fediverse_stub['domain']}/users/tester/inbox",
        'outbox': f"https://{fediverse_stub['domain']}/users/tester/outbox",
        'endpoints': {
            'oauthRegistrationEndpoint': f"https://{fediverse_stub['domain']}/custom/apps",
            'oauthAuthorizationEndpoint': f"https://{fediverse_stub['domain']}/custom/authorize",
            'oauthTokenEndpoint': f"https://{fediverse_stub['domain']}/custom/token",
        },
    }
    monkeypatch.setattr(fediverse, 'fetch_actor', lambda actor_url: dict(actor_with_endpoints))

    login_page = testapp.get('/login', status=200)
    csrf_token = login_page.forms['fediverse-login-form']['csrf_token'].value
    resp = testapp.post('/api/v1/auth/login', {
        'handle': fediverse_stub['handle'],
        'csrf_token': csrf_token,
    }, status=303)
    location = resp.headers['Location']
    assert location.startswith(f"https://{fediverse_stub['domain']}/custom/authorize?")


def test_login_start_rejects_denylisted_domain(testapp, fediverse_stub, monkeypatch):
    monkeypatch.setitem(testapp.app.registry.settings, 'fediverse.denylist', fediverse_stub['domain'])

    login_page = testapp.get('/login', status=200)
    csrf_token = login_page.forms['fediverse-login-form']['csrf_token'].value
    resp = testapp.post('/api/v1/auth/login', {
        'handle': fediverse_stub['handle'],
        'csrf_token': csrf_token,
    }, status=303)
    assert 'no esta permitido' in urllib.parse.unquote(resp.headers['Location'])


def test_login_start_rejects_domain_without_nodeinfo(testapp, fediverse_stub, monkeypatch):
    from honeycomb.security import fediverse
    # Simula que TAMPOCO se pudo resolver el Actor via WebFinger: sin eso, el actor ya
    # no sirve como confirmacion de que hay un servidor real, y se cae al chequeo de nodeinfo.
    monkeypatch.setattr(fediverse, 'discover_actor_url', lambda username, domain: None)
    monkeypatch.setattr(fediverse, 'discover_nodeinfo', lambda domain: None)

    login_page = testapp.get('/login', status=200)
    csrf_token = login_page.forms['fediverse-login-form']['csrf_token'].value
    resp = testapp.post('/api/v1/auth/login', {
        'handle': f"user@{fediverse_stub['domain']}",
        'csrf_token': csrf_token,
    }, status=303)
    assert 'No encontramos un servidor' in urllib.parse.unquote(resp.headers['Location'])


def test_callback_rejects_missing_state(testapp):
    resp = testapp.get('/api/v1/auth/callback', {'code': 'whatever'}, status=303)
    assert _redirects_to_login_error(resp.headers['Location'])


def test_callback_rejects_mismatched_state(testapp, fediverse_stub):
    login_page = testapp.get('/login', status=200)
    csrf_token = login_page.forms['fediverse-login-form']['csrf_token'].value
    testapp.post('/api/v1/auth/login', {
        'handle': fediverse_stub['handle'],
        'csrf_token': csrf_token,
    }, status=303)

    resp = testapp.get('/api/v1/auth/callback', {'code': 'fake-code', 'state': 'wrong-state'}, status=303)
    assert _redirects_to_login_error(resp.headers['Location'])


def test_callback_rejects_missing_code(testapp, fediverse_stub):
    login_page = testapp.get('/login', status=200)
    csrf_token = login_page.forms['fediverse-login-form']['csrf_token'].value
    start_resp = testapp.post('/api/v1/auth/login', {
        'handle': fediverse_stub['handle'],
        'csrf_token': csrf_token,
    }, status=303)
    state = urllib.parse.parse_qs(urllib.parse.urlsplit(start_resp.headers['Location']).query)['state'][0]

    resp = testapp.get('/api/v1/auth/callback', {'state': state}, status=303)
    assert _redirects_to_login_error(resp.headers['Location'])


def test_full_login_flow_sets_identity(testapp, login_as_fediverse_user, fediverse_stub):
    login_as_fediverse_user()
    body = testapp.get('/api/v1/me', status=200).json
    assert body['userid'] == fediverse_stub['userid']
    assert body['username'] == fediverse_stub['handle']


def test_full_login_flow_encrypts_and_stores_access_token(testapp, login_as_fediverse_user, fediverse_stub):
    """testing.ini trae una clave real, asi que el flujo completo debe cifrar y
    guardar el token (fake-access-token, del stub de exchange_code)."""
    from honeycomb.security import tokenstore

    login_as_fediverse_user()
    stored_user = fediverse_stub['get_stored_user']()
    assert stored_user.access_token_encrypted is not None
    assert stored_user.access_token_encrypted != 'fake-access-token'

    settings = testapp.app.registry.settings
    assert tokenstore.decrypt_token(settings, stored_user.access_token_encrypted) == 'fake-access-token'


def test_me_endpoint_never_exposes_the_access_token(testapp, login_as_fediverse_user):
    login_as_fediverse_user()
    body = testapp.get('/api/v1/me', status=200).json
    assert 'access_token' not in body
    assert 'access_token_encrypted' not in body


def test_second_login_to_same_domain_reuses_cached_app(testapp, fediverse_stub, monkeypatch):
    from honeycomb.security import fediverse

    calls = []
    original_register_app = fediverse.register_app

    def counting_register_app(*args, **kwargs):
        calls.append(1)
        return original_register_app(*args, **kwargs)

    monkeypatch.setattr(fediverse, 'register_app', counting_register_app)

    for _ in range(2):
        login_page = testapp.get('/login', status=200)
        csrf_token = login_page.forms['fediverse-login-form']['csrf_token'].value
        testapp.post('/api/v1/auth/login', {
            'handle': fediverse_stub['handle'],
            'csrf_token': csrf_token,
        }, status=303)

    assert len(calls) == 1


def test_relogin_via_fediverse_does_not_wipe_a_linked_password_hash(testapp, login_as_fediverse_user, fediverse_stub):
    """Regresion: el callback reemplazaba el DroneUser entero en cada login, lo que
    habria borrado un password_hash vinculado. Ahora usa update_profile.

    testapp.reset() simula volver en una sesion nueva (cerrar el navegador y
    entrar otro dia) -- si no se limpian las cookies, la segunda llamada a
    login_as_fediverse_user ya estaria autenticada y /login la redirigiria de
    entrada (ese es justamente el caso de vincular, no de volver a entrar)."""
    login_as_fediverse_user()
    stored_user = fediverse_stub['get_stored_user']()
    stored_user.password_hash = 'scrypt$n=16384,r=8,p=1$fake-salt$fake-digest'

    testapp.reset()
    login_as_fediverse_user()

    stored_user_again = fediverse_stub['get_stored_user']()
    assert stored_user_again.password_hash == 'scrypt$n=16384,r=8,p=1$fake-salt$fake-digest'


def test_relogin_via_fediverse_still_refreshes_the_access_token(testapp, login_as_fediverse_user, fediverse_stub):
    """El arreglo de la trampa 1 no debe dejar de refrescar el token en cada login."""
    from honeycomb.security import tokenstore

    login_as_fediverse_user()
    first_token = fediverse_stub['get_stored_user']().access_token_encrypted

    testapp.reset()
    login_as_fediverse_user()
    second_token = fediverse_stub['get_stored_user']().access_token_encrypted

    settings = testapp.app.registry.settings
    assert tokenstore.decrypt_token(settings, second_token) == 'fake-access-token'
    assert first_token is not None and second_token is not None
