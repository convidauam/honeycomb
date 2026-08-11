import pytest

from honeycomb.security import passwords


def test_hash_then_verify_roundtrip():
    stored = passwords.hash_password('correct horse battery staple')
    assert passwords.verify_password('correct horse battery staple', stored) is True


def test_verify_rejects_wrong_password():
    stored = passwords.hash_password('correct horse battery staple')
    assert passwords.verify_password('wrong password', stored) is False


def test_hash_is_salted_differently_each_time():
    a = passwords.hash_password('same password')
    b = passwords.hash_password('same password')
    assert a != b
    assert passwords.verify_password('same password', a) is True
    assert passwords.verify_password('same password', b) is True


def test_stored_hash_is_self_describing():
    stored = passwords.hash_password('correct horse battery staple')
    scheme, params, salt_b64, digest_b64 = stored.split('$')
    assert scheme == 'scrypt'
    assert 'n=' in params and 'r=' in params and 'p=' in params


def test_verify_returns_false_on_garbage_input():
    assert passwords.verify_password('anything', 'not-a-valid-hash') is False
    assert passwords.verify_password('anything', '') is False
    assert passwords.verify_password('anything', 'scrypt$garbage$x$y') is False


def test_verify_returns_false_for_unknown_scheme():
    stored = passwords.hash_password('correct horse battery staple')
    fake = stored.replace('scrypt$', 'md5$')
    assert passwords.verify_password('correct horse battery staple', fake) is False


def test_validate_password_accepts_long_enough():
    passwords.validate_password('correct horse battery staple')


def test_validate_password_rejects_short():
    with pytest.raises(passwords.CredentialError):
        passwords.validate_password('short')


def test_validate_password_respects_custom_min_length():
    passwords.validate_password('12345', min_length=5)
    with pytest.raises(passwords.CredentialError):
        passwords.validate_password('1234', min_length=5)


def test_validate_password_rejects_empty():
    with pytest.raises(passwords.CredentialError):
        passwords.validate_password('')
    with pytest.raises(passwords.CredentialError):
        passwords.validate_password(None)


def test_normalize_username_lowercases_and_trims():
    assert passwords.normalize_username('  Levi_Iparrea  ') == 'levi_iparrea'


def test_normalize_username_rejects_too_short():
    with pytest.raises(passwords.CredentialError):
        passwords.normalize_username('ab')


def test_normalize_username_rejects_too_long():
    with pytest.raises(passwords.CredentialError):
        passwords.normalize_username('a' * 33)


def test_normalize_username_rejects_at_sign():
    with pytest.raises(passwords.CredentialError):
        passwords.normalize_username('levi@unam.social')


def test_normalize_username_rejects_colon():
    with pytest.raises(passwords.CredentialError):
        passwords.normalize_username('fediverse:levi')


def test_normalize_username_rejects_slash():
    with pytest.raises(passwords.CredentialError):
        passwords.normalize_username('https://unam.social/users/levi')


def test_normalize_username_rejects_blank():
    with pytest.raises(passwords.CredentialError):
        passwords.normalize_username('')
    with pytest.raises(passwords.CredentialError):
        passwords.normalize_username(None)


def test_normalize_username_accepts_hyphen_and_underscore():
    assert passwords.normalize_username('levi-iparrea_2') == 'levi-iparrea_2'
