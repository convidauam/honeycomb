import pytest

from honeycomb.models import BeeHive
from honeycomb.models.users import DroneUser
from honeycomb.security import local_accounts

ENABLED = {'honeycomb.local_accounts': 'true'}
DISABLED = {'honeycomb.local_accounts': ''}


@pytest.fixture(autouse=True)
def restore_rate_limiters():
    original_login = local_accounts._login_rate_limiter
    original_registration = local_accounts._registration_rate_limiter
    yield
    local_accounts._login_rate_limiter = original_login
    local_accounts._registration_rate_limiter = original_registration


def test_register_creates_a_local_user():
    hive = BeeHive()
    user = local_accounts.register(hive, ENABLED, 'alice', 'correct horse battery staple')
    assert user.userid.startswith('local:')
    assert user.username == 'alice'
    assert user.password_hash is not None


def test_register_links_the_password_identity():
    hive = BeeHive()
    user = local_accounts.register(hive, ENABLED, 'alice', 'correct horse battery staple')
    assert hive.resolve_identity('password:alice') == user.userid


def test_register_raises_when_local_accounts_disabled():
    hive = BeeHive()
    with pytest.raises(local_accounts.LocalAuthError):
        local_accounts.register(hive, DISABLED, 'alice', 'correct horse battery staple')


def test_register_rejects_invalid_username():
    hive = BeeHive()
    with pytest.raises(local_accounts.LocalAuthError):
        local_accounts.register(hive, ENABLED, 'a', 'correct horse battery staple')


def test_register_rejects_short_password():
    hive = BeeHive()
    with pytest.raises(local_accounts.LocalAuthError):
        local_accounts.register(hive, ENABLED, 'alice', 'short')


def test_register_rejects_duplicate_username():
    hive = BeeHive()
    local_accounts.register(hive, ENABLED, 'alice', 'correct horse battery staple')
    with pytest.raises(local_accounts.LocalAuthError):
        local_accounts.register(hive, ENABLED, 'alice', 'a different password entirely')


def test_register_username_is_case_insensitive_for_uniqueness():
    hive = BeeHive()
    local_accounts.register(hive, ENABLED, 'Alice', 'correct horse battery staple')
    with pytest.raises(local_accounts.LocalAuthError):
        local_accounts.register(hive, ENABLED, 'ALICE', 'a different password entirely')


def test_authenticate_succeeds_with_correct_password():
    hive = BeeHive()
    created = local_accounts.register(hive, ENABLED, 'alice', 'correct horse battery staple')
    authenticated = local_accounts.authenticate(hive, ENABLED, 'alice', 'correct horse battery staple')
    assert authenticated.userid == created.userid


def test_authenticate_raises_generic_error_for_unknown_user():
    hive = BeeHive()
    with pytest.raises(local_accounts.LocalAuthError):
        local_accounts.authenticate(hive, ENABLED, 'nobody', 'whatever password')


def test_authenticate_raises_generic_error_for_wrong_password():
    hive = BeeHive()
    local_accounts.register(hive, ENABLED, 'alice', 'correct horse battery staple')
    with pytest.raises(local_accounts.LocalAuthError):
        local_accounts.authenticate(hive, ENABLED, 'alice', 'wrong password entirely')


def test_authenticate_unknown_user_and_wrong_password_give_the_same_message():
    hive = BeeHive()
    local_accounts.register(hive, ENABLED, 'alice', 'correct horse battery staple')

    unknown_message = None
    wrong_password_message = None
    try:
        local_accounts.authenticate(hive, ENABLED, 'nobody', 'whatever password')
    except local_accounts.LocalAuthError as exc:
        unknown_message = str(exc)
    try:
        local_accounts.authenticate(hive, ENABLED, 'alice', 'wrong password entirely')
    except local_accounts.LocalAuthError as exc:
        wrong_password_message = str(exc)

    assert unknown_message == wrong_password_message


def test_authenticate_raises_when_local_accounts_disabled():
    hive = BeeHive()
    local_accounts.register(hive, ENABLED, 'alice', 'correct horse battery staple')
    with pytest.raises(local_accounts.LocalAuthError):
        local_accounts.authenticate(hive, DISABLED, 'alice', 'correct horse battery staple')


def test_link_password_adds_a_credential_to_an_existing_account():
    hive = BeeHive()
    fediverse_user = hive.upsert_user(DroneUser(
        userid='https://unam.social/users/alice', display_name='Alice', username='alice@unam.social',
    ))
    local_accounts.link_password(hive, ENABLED, fediverse_user, 'alice', 'correct horse battery staple')

    assert hive.resolve_identity('password:alice') == fediverse_user.userid
    assert fediverse_user.password_hash is not None
    assert local_accounts.authenticate(hive, ENABLED, 'alice', 'correct horse battery staple').userid == fediverse_user.userid


def test_link_password_does_not_touch_the_display_username():
    hive = BeeHive()
    fediverse_user = hive.upsert_user(DroneUser(
        userid='https://unam.social/users/alice', display_name='Alice', username='alice@unam.social',
    ))
    local_accounts.link_password(hive, ENABLED, fediverse_user, 'alicelocal', 'correct horse battery staple')
    assert fediverse_user.username == 'alice@unam.social'


def test_link_password_rejects_username_already_used_by_someone_else():
    hive = BeeHive()
    local_accounts.register(hive, ENABLED, 'alice', 'correct horse battery staple')
    other_user = hive.upsert_user(DroneUser(userid='https://unam.social/users/bob', display_name='Bob', username='bob'))
    with pytest.raises(local_accounts.LocalAuthError):
        local_accounts.link_password(hive, ENABLED, other_user, 'alice', 'a different password entirely')


def test_unlink_refuses_to_remove_the_last_credential():
    hive = BeeHive()
    user = local_accounts.register(hive, ENABLED, 'alice', 'correct horse battery staple')
    with pytest.raises(local_accounts.LocalAuthError):
        local_accounts.unlink(hive, user.userid, 'password:alice')


def test_unlink_removes_a_non_last_credential_and_clears_the_password_hash():
    hive = BeeHive()
    user = local_accounts.register(hive, ENABLED, 'alice', 'correct horse battery staple')
    hive.link_identity('fediverse:https://unam.social/users/alice', user.userid)

    local_accounts.unlink(hive, user.userid, 'password:alice')

    assert hive.resolve_identity('password:alice') is None
    assert user.password_hash is None


def test_unlink_raises_when_credential_not_linked_to_this_account():
    hive = BeeHive()
    user = local_accounts.register(hive, ENABLED, 'alice', 'correct horse battery staple')
    with pytest.raises(local_accounts.LocalAuthError):
        local_accounts.unlink(hive, user.userid, 'password:someone-else')


def test_configure_rate_limiters_blank_settings_means_no_limit():
    local_accounts.configure_rate_limiters({
        'honeycomb.login_rate_window_seconds': '',
        'honeycomb.login_rate_max_per_user': '',
        'honeycomb.login_rate_max_global': '',
        'honeycomb.registration_rate_max_global': '',
    })
    assert local_accounts._login_rate_limiter.max_per_key is None
    assert local_accounts._login_rate_limiter.max_global is None
    assert local_accounts._registration_rate_limiter.max_global is None


def test_configure_rate_limiters_reads_explicit_values():
    local_accounts.configure_rate_limiters({
        'honeycomb.login_rate_window_seconds': '60',
        'honeycomb.login_rate_max_per_user': '3',
        'honeycomb.login_rate_max_global': '20',
        'honeycomb.registration_rate_max_global': '5',
    })
    assert local_accounts._login_rate_limiter.window_seconds == 60
    assert local_accounts._login_rate_limiter.max_per_key == 3
    assert local_accounts._login_rate_limiter.max_global == 20
    assert local_accounts._registration_rate_limiter.max_global == 5


def test_login_rate_limit_blocks_after_max_attempts():
    local_accounts.configure_rate_limiters({
        'honeycomb.login_rate_window_seconds': '600',
        'honeycomb.login_rate_max_per_user': '2',
    })
    hive = BeeHive()
    local_accounts.register(hive, ENABLED, 'alice', 'correct horse battery staple')

    for _ in range(2):
        with pytest.raises(local_accounts.LocalAuthError):
            local_accounts.authenticate(hive, ENABLED, 'alice', 'wrong password entirely')
    with pytest.raises(local_accounts.LocalAuthError):
        local_accounts.authenticate(hive, ENABLED, 'alice', 'correct horse battery staple')
