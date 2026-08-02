import urllib.parse


def _redirects_to_login_error(location):
    parts = urllib.parse.urlsplit(location)
    return parts.path == '/login' and 'error' in urllib.parse.parse_qs(parts.query)


def test_login_page_renders_form(testapp):
    page = testapp.get('/login', status=200)
    assert 'csrf_token' in page.form.fields
    assert 'handle' in page.form.fields


def test_login_page_csrf_token_stable_across_reloads(testapp):
    first = testapp.get('/login', status=200).form['csrf_token'].value
    second = testapp.get('/login', status=200).form['csrf_token'].value
    assert first == second


def test_login_start_rejects_malformed_handle(testapp):
    login_page = testapp.get('/login', status=200)
    csrf_token = login_page.form['csrf_token'].value
    resp = testapp.post('/api/v1/auth/login', {'handle': 'not-a-handle', 'csrf_token': csrf_token}, status=303)
    assert _redirects_to_login_error(resp.headers['Location'])


def test_login_start_redirects_to_authorize_url(testapp, fediverse_stub):
    login_page = testapp.get('/login', status=200)
    csrf_token = login_page.form['csrf_token'].value
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


def test_login_start_rejects_denylisted_domain(testapp, fediverse_stub, monkeypatch):
    monkeypatch.setitem(testapp.app.registry.settings, 'fediverse.denylist', fediverse_stub['domain'])

    login_page = testapp.get('/login', status=200)
    csrf_token = login_page.form['csrf_token'].value
    resp = testapp.post('/api/v1/auth/login', {
        'handle': fediverse_stub['handle'],
        'csrf_token': csrf_token,
    }, status=303)
    assert 'no esta permitido' in urllib.parse.unquote(resp.headers['Location'])


def test_login_start_rejects_domain_without_nodeinfo(testapp, fediverse_stub, monkeypatch):
    from honeycomb.security import fediverse
    monkeypatch.setattr(fediverse, 'discover_nodeinfo', lambda domain: None)

    login_page = testapp.get('/login', status=200)
    csrf_token = login_page.form['csrf_token'].value
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
    csrf_token = login_page.form['csrf_token'].value
    testapp.post('/api/v1/auth/login', {
        'handle': fediverse_stub['handle'],
        'csrf_token': csrf_token,
    }, status=303)

    resp = testapp.get('/api/v1/auth/callback', {'code': 'fake-code', 'state': 'wrong-state'}, status=303)
    assert _redirects_to_login_error(resp.headers['Location'])


def test_callback_rejects_missing_code(testapp, fediverse_stub):
    login_page = testapp.get('/login', status=200)
    csrf_token = login_page.form['csrf_token'].value
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
        csrf_token = login_page.form['csrf_token'].value
        testapp.post('/api/v1/auth/login', {
            'handle': fediverse_stub['handle'],
            'csrf_token': csrf_token,
        }, status=303)

    assert len(calls) == 1
