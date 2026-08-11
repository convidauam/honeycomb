# Nota: igual que en test_api_games.py, cada request de `testapp` corre en su
# propia transaccion que se aborta al final (ver conftest.py). Los fixtures
# register_as_local_user/login_as_local_user/login_as_fediverse_user usan
# identity_bridge para simular persistencia entre requests; los flujos que
# ademas tocan progreso (vincular y fusionar) usan game_data_bridge tambien.

import urllib.parse


def _redirects_to_error(location, path):
    parts = urllib.parse.urlsplit(location)
    return parts.path == path and 'error' in urllib.parse.parse_qs(parts.query)


def test_register_page_renders_when_enabled(testapp):
    page = testapp.get('/register', status=200)
    form = page.forms['register-form']
    assert 'username' in form.fields
    assert 'password' in form.fields


def test_register_page_shows_disabled_message(testapp, monkeypatch):
    monkeypatch.setitem(testapp.app.registry.settings, 'honeycomb.local_accounts', '')
    page = testapp.get('/register', status=200)
    assert 'no esta habilitado' in page.text
    assert 'register-form' not in page.forms


def test_register_creates_account_and_logs_in(testapp, register_as_local_user):
    register_as_local_user('alice', 'correct horse battery staple')
    body = testapp.get('/api/v1/me', status=200).json
    assert body['username'] == 'alice'


def test_register_rejects_invalid_username(testapp):
    page = testapp.get('/register', status=200)
    csrf_token = page.forms['register-form']['csrf_token'].value
    resp = testapp.post('/api/v1/auth/register', {
        'username': 'a', 'password': 'correct horse battery staple', 'csrf_token': csrf_token,
    }, status=303)
    assert _redirects_to_error(resp.headers['Location'], '/register')


def test_register_rejects_short_password(testapp):
    page = testapp.get('/register', status=200)
    csrf_token = page.forms['register-form']['csrf_token'].value
    resp = testapp.post('/api/v1/auth/register', {
        'username': 'alice', 'password': 'short', 'csrf_token': csrf_token,
    }, status=303)
    assert _redirects_to_error(resp.headers['Location'], '/register')


def test_register_rejects_duplicate_username(testapp, register_as_local_user):
    register_as_local_user('alice', 'correct horse battery staple')
    testapp.reset()

    page = testapp.get('/register', status=200)
    csrf_token = page.forms['register-form']['csrf_token'].value
    resp = testapp.post('/api/v1/auth/register', {
        'username': 'alice', 'password': 'a different password entirely', 'csrf_token': csrf_token,
    }, status=303)
    assert _redirects_to_error(resp.headers['Location'], '/register')


def test_register_disabled_returns_error(testapp, monkeypatch):
    # csrf_token real (independiente de local_accounts) para que la peticion
    # llegue al cuerpo de la vista en vez de que la rechace el check de CSRF.
    csrf_token = testapp.get('/login', status=200).forms['fediverse-login-form']['csrf_token'].value
    monkeypatch.setitem(testapp.app.registry.settings, 'honeycomb.local_accounts', '')

    resp = testapp.post('/api/v1/auth/register', {
        'username': 'alice', 'password': 'correct horse battery staple', 'csrf_token': csrf_token,
    }, status=303)
    assert _redirects_to_error(resp.headers['Location'], '/register')


def test_local_login_succeeds_with_correct_credentials(testapp, register_as_local_user, login_as_local_user):
    register_as_local_user('alice', 'correct horse battery staple')
    testapp.reset()

    login_as_local_user('alice', 'correct horse battery staple')
    body = testapp.get('/api/v1/me', status=200).json
    assert body['username'] == 'alice'


def test_local_login_rejects_wrong_password(testapp, register_as_local_user, login_as_local_user):
    register_as_local_user('alice', 'correct horse battery staple')
    testapp.reset()

    resp = login_as_local_user('alice', 'wrong password entirely')
    assert _redirects_to_error(resp.headers['Location'], '/login')


def test_local_login_unknown_and_wrong_password_give_the_same_message(testapp, register_as_local_user, login_as_local_user):
    register_as_local_user('alice', 'correct horse battery staple')
    testapp.reset()

    unknown_resp = login_as_local_user('nobody', 'whatever password')
    testapp.reset()
    wrong_resp = login_as_local_user('alice', 'wrong password entirely')

    unknown_error = urllib.parse.parse_qs(urllib.parse.urlsplit(unknown_resp.headers['Location']).query)['error']
    wrong_error = urllib.parse.parse_qs(urllib.parse.urlsplit(wrong_resp.headers['Location']).query)['error']
    assert unknown_error == wrong_error


def test_account_page_requires_auth(testapp):
    resp = testapp.get('/cuenta', status=303)
    assert urllib.parse.urlsplit(resp.headers['Location']).path == '/login'


def test_account_page_lists_the_password_identity_after_registering(testapp, register_as_local_user):
    register_as_local_user('alice', 'correct horse battery staple')
    page = testapp.get('/cuenta', status=200)
    assert 'alice' in page.text
    # Unica credencial: no debe ofrecer desvincularla.
    assert 'unlink-form-1' not in page.forms


def test_unlink_requires_auth(testapp):
    csrf_token = testapp.get('/login', status=200).forms['fediverse-login-form']['csrf_token'].value
    testapp.post('/api/v1/auth/unlink', {'identity_key': 'password:alice', 'csrf_token': csrf_token}, status=401)


def test_unlink_refuses_to_remove_the_last_credential(testapp, register_as_local_user):
    register_as_local_user('alice', 'correct horse battery staple')
    page = testapp.get('/cuenta', status=200)
    csrf_token = page.forms['link-fediverse-form']['csrf_token'].value

    resp = testapp.post('/api/v1/auth/unlink', {
        'identity_key': 'password:alice', 'csrf_token': csrf_token,
    }, status=303)
    assert _redirects_to_error(resp.headers['Location'], '/cuenta')


def test_link_password_requires_auth(testapp):
    csrf_token = testapp.get('/login', status=200).forms['fediverse-login-form']['csrf_token'].value
    testapp.post('/api/v1/auth/link/password', {
        'username': 'alice', 'password': 'correct horse battery staple', 'csrf_token': csrf_token,
    }, status=401)


def test_link_fediverse_to_local_account_merges_progress_and_lists_both_identities(
    testapp, register_as_local_user, fediverse_stub, game_data_bridge,
):
    register_as_local_user('alice', 'correct horse battery staple')
    # Progreso jugado ANTES de vincular, con la cuenta local.
    testapp.post_json('/api/v1/sipping/node-a', {'stats': {'highscore': 5}}, status=200)

    account_page = testapp.get('/cuenta', status=200)
    csrf_token = account_page.forms['link-fediverse-form']['csrf_token'].value
    start_resp = testapp.post('/api/v1/auth/login', {
        'handle': fediverse_stub['handle'], 'csrf_token': csrf_token, 'next': '/cuenta',
    }, status=303)
    authorize_url = start_resp.headers['Location']
    state = urllib.parse.parse_qs(urllib.parse.urlsplit(authorize_url).query)['state'][0]
    callback_resp = testapp.get('/api/v1/auth/callback', {'code': 'fake-code', 'state': state}, status=303)
    assert urllib.parse.urlsplit(callback_resp.headers['Location']).path == '/cuenta'

    # El progreso jugado como cuenta local sigue disponible en la cuenta ya
    # vinculada (se fusiono, no se perdio).
    body = testapp.get('/api/v1/sipping/node-a', status=200).json
    assert body['stats'] == {'highscore': 5}

    account_page_after = testapp.get('/cuenta', status=200)
    assert 'alice' in account_page_after.text
    assert fediverse_stub['userid'] in account_page_after.text
    # Ahora si hay mas de una credencial: debe ofrecer desvincular.
    assert 'unlink-form-1' in account_page_after.forms


def test_link_fediverse_already_linked_to_another_account_is_rejected(
    testapp, register_as_local_user, login_as_fediverse_user, fediverse_stub,
):
    # La cuenta del Fediverso ya esta vinculada a si misma (login normal).
    login_as_fediverse_user()
    testapp.reset()

    # Otra cuenta local intenta vincular ese mismo Fediverso.
    register_as_local_user('bob', 'a different password entirely')
    account_page = testapp.get('/cuenta', status=200)
    csrf_token = account_page.forms['link-fediverse-form']['csrf_token'].value
    start_resp = testapp.post('/api/v1/auth/login', {
        'handle': fediverse_stub['handle'], 'csrf_token': csrf_token, 'next': '/cuenta',
    }, status=303)
    state = urllib.parse.parse_qs(urllib.parse.urlsplit(start_resp.headers['Location']).query)['state'][0]

    callback_resp = testapp.get('/api/v1/auth/callback', {'code': 'fake-code', 'state': state}, status=303)
    assert _redirects_to_error(callback_resp.headers['Location'], '/login')
    assert 'vinculada a otra cuenta' in urllib.parse.unquote(callback_resp.headers['Location'])
