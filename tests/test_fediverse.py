import socket

import pytest

from honeycomb.security import fediverse, ratelimit


def _fake_getaddrinfo(ip):
    def _impl(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 0))]
    return _impl


def test_is_public_ip_accepts_public():
    assert fediverse._is_public_ip('8.8.8.8') is True


def test_is_public_ip_rejects_private_ranges():
    assert fediverse._is_public_ip('10.0.0.1') is False
    assert fediverse._is_public_ip('127.0.0.1') is False
    assert fediverse._is_public_ip('169.254.169.254') is False
    assert fediverse._is_public_ip('0.0.0.0') is False


def test_assert_public_host_allows_public_ip(monkeypatch):
    monkeypatch.setattr(socket, 'getaddrinfo', _fake_getaddrinfo('93.184.216.34'))
    fediverse._assert_public_host('example.com')


def test_assert_public_host_rejects_private_ip(monkeypatch):
    monkeypatch.setattr(socket, 'getaddrinfo', _fake_getaddrinfo('127.0.0.1'))
    with pytest.raises(fediverse.FediverseError):
        fediverse._assert_public_host('evil.example')


def test_assert_public_host_rejects_link_local_metadata_ip(monkeypatch):
    monkeypatch.setattr(socket, 'getaddrinfo', _fake_getaddrinfo('169.254.169.254'))
    with pytest.raises(fediverse.FediverseError):
        fediverse._assert_public_host('evil.example')


def test_assert_public_host_rejects_dns_failure(monkeypatch):
    def _raise(*args, **kwargs):
        raise socket.gaierror('nope')
    monkeypatch.setattr(socket, 'getaddrinfo', _raise)
    with pytest.raises(fediverse.FediverseError):
        fediverse._assert_public_host('doesnotexist.invalid')


def test_parse_handle_accepts_at_prefix():
    assert fediverse.parse_handle('@user@example.social') == ('user', 'example.social')


def test_parse_handle_accepts_without_at_prefix():
    assert fediverse.parse_handle('user@example.social') == ('user', 'example.social')


def test_parse_handle_lowercases_domain():
    _username, domain = fediverse.parse_handle('User@Example.Social')
    assert domain == 'example.social'


def test_parse_handle_rejects_missing_at():
    with pytest.raises(fediverse.FediverseError):
        fediverse.parse_handle('notahandle')


def test_parse_handle_rejects_empty():
    with pytest.raises(fediverse.FediverseError):
        fediverse.parse_handle('')


def test_parse_handle_rejects_domain_without_dot():
    with pytest.raises(fediverse.FediverseError):
        fediverse.parse_handle('user@localhost')


def test_generate_pkce_pair_shapes():
    verifier, challenge = fediverse.generate_pkce_pair()
    assert 43 <= len(verifier) <= 128
    assert len(challenge) > 0
    assert verifier != challenge


def test_states_match_true_for_equal():
    assert fediverse.states_match('abc', 'abc') is True


def test_states_match_false_for_different():
    assert fediverse.states_match('abc', 'xyz') is False


def test_states_match_false_for_missing():
    assert fediverse.states_match(None, 'abc') is False
    assert fediverse.states_match('abc', None) is False


def test_choose_scope_prefers_profile_when_supported():
    assert fediverse.choose_scope({'scopes_supported': ['read', 'profile']}) == 'profile write:statuses'


def test_choose_scope_falls_back_without_profile():
    assert fediverse.choose_scope({'scopes_supported': ['read']}) == 'read:accounts write:statuses'


def test_choose_scope_falls_back_without_metadata():
    assert fediverse.choose_scope(None) == 'read:accounts write:statuses'


def test_supports_pkce_true_when_s256_listed():
    assert fediverse.supports_pkce({'code_challenge_methods_supported': ['S256']}) is True


def test_supports_pkce_false_without_metadata():
    assert fediverse.supports_pkce(None) is False


def test_canonical_userid_prefers_actor_uri():
    account = {'uri': 'https://example.social/users/alice', 'id': '42'}
    assert fediverse.canonical_userid('example.social', account) == 'https://example.social/users/alice'


def test_canonical_userid_falls_back_to_host_and_id():
    account = {'id': '42'}
    assert fediverse.canonical_userid('example.social', account) == 'example.social#42'


def test_account_to_drone_user_maps_fields():
    account = {
        'uri': 'https://example.social/users/alice',
        'id': '42',
        'username': 'alice',
        'acct': 'alice',
        'display_name': 'Alice',
        'avatar': 'https://example.social/avatar.png',
        'header': 'https://example.social/header.png',
    }
    user = fediverse.account_to_drone_user('example.social', account)
    assert user.userid == 'https://example.social/users/alice'
    assert user.display_name == 'Alice'
    assert user.username == 'alice@example.social'
    assert user.icon == 'https://example.social/avatar.png'
    assert user.background == 'https://example.social/header.png'


def test_account_to_drone_user_handles_nested_image_objects():
    account = {
        'id': '7',
        'username': 'bob',
        'avatar': {'url': 'https://example.social/bob-avatar.png'},
        'header': None,
    }
    user = fediverse.account_to_drone_user('example.social', account)
    assert user.icon == 'https://example.social/bob-avatar.png'
    assert user.background is None


class _FakeJSONResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.is_redirect = False
        self.is_permanent_redirect = False

    def json(self):
        return self._payload


def _stub_request(monkeypatch, response):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured['method'] = method
        captured['url'] = url
        captured['kwargs'] = kwargs
        return response

    monkeypatch.setattr(fediverse.requests, 'request', fake_request)
    monkeypatch.setattr(fediverse, '_assert_public_host', lambda host: None)
    return captured


def test_discover_actor_url_sends_jrd_accept_header(monkeypatch):
    """unam.social (Pleroma) da 400 sin este header exacto -- verificado en vivo."""
    jrd = {
        'subject': 'acct:tester@example.social',
        'links': [
            {'rel': 'self', 'type': 'application/activity+json', 'href': 'https://example.social/users/tester'},
        ],
    }
    captured = _stub_request(monkeypatch, _FakeJSONResponse(200, jrd))
    url = fediverse.discover_actor_url('tester', 'example.social')
    assert url == 'https://example.social/users/tester'
    assert captured['kwargs']['headers']['Accept'] == 'application/jrd+json'
    assert captured['kwargs']['params'] == {'resource': 'acct:tester@example.social'}


def test_discover_actor_url_returns_none_without_matching_link(monkeypatch):
    jrd = {'links': [{'rel': 'self', 'type': 'text/html', 'href': 'https://example.social/@tester'}]}
    _stub_request(monkeypatch, _FakeJSONResponse(200, jrd))
    assert fediverse.discover_actor_url('tester', 'example.social') is None


def test_discover_actor_url_returns_none_on_non_200(monkeypatch):
    _stub_request(monkeypatch, _FakeJSONResponse(400, {}))
    assert fediverse.discover_actor_url('tester', 'example.social') is None


def test_discover_actor_url_returns_none_on_network_error(monkeypatch):
    def fail(*a, **k):
        raise fediverse.requests.RequestException('boom')
    monkeypatch.setattr(fediverse.requests, 'request', fail)
    monkeypatch.setattr(fediverse, '_assert_public_host', lambda host: None)
    assert fediverse.discover_actor_url('tester', 'example.social') is None


def test_fetch_actor_sends_activity_json_accept_header(monkeypatch):
    actor = {'id': 'https://example.social/users/tester', 'preferredUsername': 'tester'}
    captured = _stub_request(monkeypatch, _FakeJSONResponse(200, actor))
    result = fediverse.fetch_actor('https://example.social/users/tester')
    assert result == actor
    assert captured['kwargs']['headers']['Accept'] == 'application/activity+json'


def test_fetch_actor_returns_none_on_non_200(monkeypatch):
    _stub_request(monkeypatch, _FakeJSONResponse(404, {}))
    assert fediverse.fetch_actor('https://example.social/users/ghost') is None


def test_actor_oauth_endpoints_reads_declared_endpoints():
    actor = {
        'endpoints': {
            'oauthRegistrationEndpoint': 'https://example.social/apps',
            'oauthAuthorizationEndpoint': 'https://example.social/authorize',
            'oauthTokenEndpoint': 'https://example.social/token',
            'sharedInbox': 'https://example.social/inbox',
        },
    }
    assert fediverse.actor_oauth_endpoints(actor) == {
        'registration': 'https://example.social/apps',
        'authorization': 'https://example.social/authorize',
        'token': 'https://example.social/token',
    }


def test_actor_oauth_endpoints_empty_when_actor_lacks_them():
    """Caso mastodon.social: solo declara sharedInbox, sin extension oauth*."""
    assert fediverse.actor_oauth_endpoints({'endpoints': {'sharedInbox': 'https://example.social/inbox'}}) == {}
    assert fediverse.actor_oauth_endpoints(None) == {}
    assert fediverse.actor_oauth_endpoints({}) == {}


def test_actor_to_drone_user_maps_fields():
    actor = {
        'id': 'https://example.social/users/alice',
        'preferredUsername': 'alice',
        'name': 'Alice',
        'icon': {'url': 'https://example.social/avatar.png'},
        'image': {'url': 'https://example.social/header.png'},
        'inbox': 'https://example.social/users/alice/inbox',
        'outbox': 'https://example.social/users/alice/outbox',
    }
    user = fediverse.actor_to_drone_user('example.social', actor)
    assert user.userid == 'https://example.social/users/alice'
    assert user.display_name == 'Alice'
    assert user.username == 'alice@example.social'
    assert user.icon == 'https://example.social/avatar.png'
    assert user.background == 'https://example.social/header.png'
    assert user.actor_url == 'https://example.social/users/alice'
    assert user.inbox == 'https://example.social/users/alice/inbox'
    assert user.outbox == 'https://example.social/users/alice/outbox'


def test_actor_to_drone_user_handles_null_icon_and_image():
    """Caso real verificado en vivo: unam.social devuelve icon/image en null."""
    actor = {
        'id': 'https://unam.social/users/convida',
        'preferredUsername': 'convida',
        'name': 'Proyecto Convida',
        'icon': None,
        'image': None,
        'inbox': 'https://unam.social/users/convida/inbox',
        'outbox': 'https://unam.social/users/convida/outbox',
    }
    user = fediverse.actor_to_drone_user('unam.social', actor)
    assert user.icon is None
    assert user.background is None
    assert user.display_name == 'Proyecto Convida'


def test_actor_to_drone_user_falls_back_without_preferred_username():
    actor = {'id': 'https://example.social/users/1'}
    user = fediverse.actor_to_drone_user('example.social', actor)
    assert user.username == 'example.social'
    assert user.display_name == 'example.social'


def test_register_app_uses_endpoint_override_when_given(monkeypatch):
    captured = _stub_request(monkeypatch, _FakeJSONResponse(200, {'client_id': 'id', 'client_secret': 'secret'}))
    fediverse.register_app(
        'example.social', 'https://honeycomb.example/callback', 'read:accounts',
        endpoint='https://example.social/custom/apps',
    )
    assert captured['url'] == 'https://example.social/custom/apps'


def test_register_app_falls_back_to_mastodon_path_without_endpoint(monkeypatch):
    captured = _stub_request(monkeypatch, _FakeJSONResponse(200, {'client_id': 'id', 'client_secret': 'secret'}))
    fediverse.register_app('example.social', 'https://honeycomb.example/callback', 'read:accounts')
    assert captured['url'] == 'https://example.social/api/v1/apps'


def test_build_authorize_url_uses_endpoint_override_when_given():
    url = fediverse.build_authorize_url(
        'example.social', 'client-id', 'https://honeycomb.example/callback', 'state123', 'read:accounts',
        endpoint='https://example.social/custom/authorize',
    )
    assert url.startswith('https://example.social/custom/authorize?')


def test_build_authorize_url_falls_back_to_mastodon_path_without_endpoint():
    url = fediverse.build_authorize_url(
        'example.social', 'client-id', 'https://honeycomb.example/callback', 'state123', 'read:accounts',
    )
    assert url.startswith('https://example.social/oauth/authorize?')


def test_exchange_code_uses_endpoint_override_when_given(monkeypatch):
    captured = _stub_request(monkeypatch, _FakeJSONResponse(200, {'access_token': 'tok'}))
    fediverse.exchange_code(
        'example.social', 'client-id', 'secret', 'https://honeycomb.example/callback',
        'code123', 'read:accounts', endpoint='https://example.social/custom/token',
    )
    assert captured['url'] == 'https://example.social/custom/token'


def test_exchange_code_falls_back_to_mastodon_path_without_endpoint(monkeypatch):
    captured = _stub_request(monkeypatch, _FakeJSONResponse(200, {'access_token': 'tok'}))
    fediverse.exchange_code(
        'example.social', 'client-id', 'secret', 'https://honeycomb.example/callback',
        'code123', 'read:accounts',
    )
    assert captured['url'] == 'https://example.social/oauth/token'


class _FakeAppResponse:
    status_code = 200
    is_redirect = False
    is_permanent_redirect = False

    def json(self):
        return {'client_id': 'id', 'client_secret': 'secret'}


def _stub_network(monkeypatch):
    monkeypatch.setattr(fediverse.requests, 'request', lambda *a, **k: _FakeAppResponse())
    monkeypatch.setattr(fediverse, '_assert_public_host', lambda host: None)


def test_register_app_enforces_per_domain_rate_limit(monkeypatch):
    limiter = ratelimit.SlidingWindowLimiter(window_seconds=600, max_per_key=2, max_global=100)
    monkeypatch.setattr(fediverse, '_registration_rate_limiter', limiter)
    _stub_network(monkeypatch)

    fediverse.register_app('example.social', 'https://honeycomb.example/callback', 'read:accounts')
    fediverse.register_app('example.social', 'https://honeycomb.example/callback', 'read:accounts')
    with pytest.raises(fediverse.FediverseError):
        fediverse.register_app('example.social', 'https://honeycomb.example/callback', 'read:accounts')


def test_register_app_per_domain_limit_does_not_affect_other_domains(monkeypatch):
    limiter = ratelimit.SlidingWindowLimiter(window_seconds=600, max_per_key=1, max_global=100)
    monkeypatch.setattr(fediverse, '_registration_rate_limiter', limiter)
    _stub_network(monkeypatch)

    fediverse.register_app('example.social', 'https://honeycomb.example/callback', 'read:accounts')
    fediverse.register_app('other.social', 'https://honeycomb.example/callback', 'read:accounts')


def test_register_app_enforces_global_rate_limit_across_domains(monkeypatch):
    limiter = ratelimit.SlidingWindowLimiter(window_seconds=600, max_per_key=100, max_global=2)
    monkeypatch.setattr(fediverse, '_registration_rate_limiter', limiter)
    _stub_network(monkeypatch)

    fediverse.register_app('a.example', 'https://honeycomb.example/callback', 'read:accounts')
    fediverse.register_app('b.example', 'https://honeycomb.example/callback', 'read:accounts')
    with pytest.raises(fediverse.FediverseError):
        fediverse.register_app('c.example', 'https://honeycomb.example/callback', 'read:accounts')


def test_registration_rate_limiter_with_none_limits_never_blocks(monkeypatch):
    """max_per_key/max_global en None (sin limite) -- el default cuando el .ini los deja en blanco."""
    limiter = ratelimit.SlidingWindowLimiter(window_seconds=600, max_per_key=None, max_global=None)
    monkeypatch.setattr(fediverse, '_registration_rate_limiter', limiter)
    _stub_network(monkeypatch)

    for _ in range(50):
        fediverse.register_app('example.social', 'https://honeycomb.example/callback', 'read:accounts')


@pytest.fixture
def restore_rate_limiter():
    """configure_registration_rate_limiter reasigna el modulo global de verdad
    (no via monkeypatch); hay que devolverlo a como estaba para no filtrar
    estado a otros tests."""
    original = fediverse._registration_rate_limiter
    yield
    fediverse._registration_rate_limiter = original


def test_configure_registration_rate_limiter_blank_settings_means_no_limit(restore_rate_limiter):
    fediverse.configure_registration_rate_limiter({
        'fediverse.registration_rate_window_seconds': '',
        'fediverse.registration_rate_max_per_domain': '',
        'fediverse.registration_rate_max_global': '',
    })
    limiter = fediverse._registration_rate_limiter
    assert limiter.max_per_key is None
    assert limiter.max_global is None
    assert limiter.window_seconds == fediverse.DEFAULT_REGISTRATION_RATE_WINDOW_SECONDS


def test_configure_registration_rate_limiter_reads_explicit_values(restore_rate_limiter):
    fediverse.configure_registration_rate_limiter({
        'fediverse.registration_rate_window_seconds': '120',
        'fediverse.registration_rate_max_per_domain': '3',
        'fediverse.registration_rate_max_global': '10',
    })
    limiter = fediverse._registration_rate_limiter
    assert limiter.window_seconds == 120
    assert limiter.max_per_key == 3
    assert limiter.max_global == 10


def test_configure_registration_rate_limiter_zero_means_no_limit(restore_rate_limiter):
    fediverse.configure_registration_rate_limiter({
        'fediverse.registration_rate_max_per_domain': '0',
        'fediverse.registration_rate_max_global': '0',
    })
    limiter = fediverse._registration_rate_limiter
    assert limiter.max_per_key is None
    assert limiter.max_global is None
