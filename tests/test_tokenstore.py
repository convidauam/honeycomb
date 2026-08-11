import pytest

from honeycomb.security import tokenstore

REAL_KEY = tokenstore.generate_key()


def test_generate_key_produces_valid_fernet_key():
    key = tokenstore.generate_key()
    # No debe tronar al usarse para construir un Fernet real.
    tokenstore.encrypt_token({'honeycomb.token_encryption_key': key}, 'sometoken')


def test_is_configured_false_when_key_blank():
    assert tokenstore.is_configured({'honeycomb.token_encryption_key': ''}) is False
    assert tokenstore.is_configured({}) is False


def test_is_configured_true_when_key_present():
    assert tokenstore.is_configured({'honeycomb.token_encryption_key': REAL_KEY}) is True


def test_encrypt_token_returns_none_without_key():
    settings = {'honeycomb.token_encryption_key': ''}
    assert tokenstore.encrypt_token(settings, 'my-access-token') is None


def test_encrypt_token_returns_none_for_empty_token():
    settings = {'honeycomb.token_encryption_key': REAL_KEY}
    assert tokenstore.encrypt_token(settings, '') is None
    assert tokenstore.encrypt_token(settings, None) is None


def test_encrypt_then_decrypt_roundtrip():
    settings = {'honeycomb.token_encryption_key': REAL_KEY}
    encrypted = tokenstore.encrypt_token(settings, 'my-access-token')
    assert encrypted is not None
    assert encrypted != 'my-access-token'
    assert tokenstore.decrypt_token(settings, encrypted) == 'my-access-token'


def test_decrypt_token_returns_none_for_empty_input():
    settings = {'honeycomb.token_encryption_key': REAL_KEY}
    assert tokenstore.decrypt_token(settings, None) is None
    assert tokenstore.decrypt_token(settings, '') is None


def test_decrypt_token_raises_without_key_configured():
    settings = {'honeycomb.token_encryption_key': ''}
    with pytest.raises(tokenstore.TokenStoreError):
        tokenstore.decrypt_token(settings, 'gAAAAA-some-fake-ciphertext')


def test_decrypt_token_raises_on_invalid_ciphertext():
    settings = {'honeycomb.token_encryption_key': REAL_KEY}
    with pytest.raises(tokenstore.TokenStoreError):
        tokenstore.decrypt_token(settings, 'not-a-real-fernet-token')


def test_decrypt_token_raises_when_key_rotated():
    original_settings = {'honeycomb.token_encryption_key': REAL_KEY}
    encrypted = tokenstore.encrypt_token(original_settings, 'my-access-token')

    rotated_settings = {'honeycomb.token_encryption_key': tokenstore.generate_key()}
    with pytest.raises(tokenstore.TokenStoreError):
        tokenstore.decrypt_token(rotated_settings, encrypted)


def test_fernet_raises_clear_error_on_malformed_key():
    settings = {'honeycomb.token_encryption_key': 'not-a-valid-fernet-key'}
    with pytest.raises(tokenstore.TokenStoreError):
        tokenstore.encrypt_token(settings, 'my-access-token')
