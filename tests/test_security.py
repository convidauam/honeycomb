from pyramid.security import Allowed, Denied
from pyramid.testing import DummyRequest

from honeycomb.models.beehive import Honeycomb
from honeycomb.security.policy import USERS, SecurityPolicy


def _permits(user, permission):
    policy = SecurityPolicy("x" * 32)
    policy.identity = lambda request: user
    return policy.permits(DummyRequest(), Honeycomb("abejas"), permission)


def test_anonymous_users_are_denied():
    assert isinstance(_permits(None, "read"), Denied)


def test_a_signed_in_user_can_read():
    """Regresion: permits leia identity['username'] de un DroneUser y tronaba con TypeError."""
    user = USERS["convida@unam.social"]
    result = _permits(user, "read")
    assert isinstance(result, Allowed)
    assert user.username in str(result)


def test_read_is_the_only_permission_there_is():
    assert isinstance(_permits(USERS["convida@unam.social"], "no-such-permission"), Denied)
