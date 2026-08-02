import socket

import pytest

from honeycomb.security import fediverse


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
    assert fediverse.choose_scope({'scopes_supported': ['read', 'profile']}) == 'profile'


def test_choose_scope_falls_back_without_profile():
    assert fediverse.choose_scope({'scopes_supported': ['read']}) == 'read:accounts'


def test_choose_scope_falls_back_without_metadata():
    assert fediverse.choose_scope(None) == 'read:accounts'


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
    limiter = fediverse._RegistrationRateLimiter(window_seconds=600, max_per_domain=2, max_global=100)
    monkeypatch.setattr(fediverse, '_registration_rate_limiter', limiter)
    _stub_network(monkeypatch)

    fediverse.register_app('example.social', 'https://honeycomb.example/callback', 'read:accounts')
    fediverse.register_app('example.social', 'https://honeycomb.example/callback', 'read:accounts')
    with pytest.raises(fediverse.FediverseError):
        fediverse.register_app('example.social', 'https://honeycomb.example/callback', 'read:accounts')


def test_register_app_per_domain_limit_does_not_affect_other_domains(monkeypatch):
    limiter = fediverse._RegistrationRateLimiter(window_seconds=600, max_per_domain=1, max_global=100)
    monkeypatch.setattr(fediverse, '_registration_rate_limiter', limiter)
    _stub_network(monkeypatch)

    fediverse.register_app('example.social', 'https://honeycomb.example/callback', 'read:accounts')
    fediverse.register_app('other.social', 'https://honeycomb.example/callback', 'read:accounts')


def test_register_app_enforces_global_rate_limit_across_domains(monkeypatch):
    limiter = fediverse._RegistrationRateLimiter(window_seconds=600, max_per_domain=100, max_global=2)
    monkeypatch.setattr(fediverse, '_registration_rate_limiter', limiter)
    _stub_network(monkeypatch)

    fediverse.register_app('a.example', 'https://honeycomb.example/callback', 'read:accounts')
    fediverse.register_app('b.example', 'https://honeycomb.example/callback', 'read:accounts')
    with pytest.raises(fediverse.FediverseError):
        fediverse.register_app('c.example', 'https://honeycomb.example/callback', 'read:accounts')
