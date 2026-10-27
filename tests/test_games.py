from honeycomb.models.axes import JellyPack
from honeycomb.models.games import Badge, Challenge, Reward
from honeycomb.models.users import DroneUser


def _badge():
    return Badge(name="first-avatar", title="Tu primer avatar", icon="abeja")


def _user(userid="local:levi"):
    return DroneUser(userid, "Levi", "levi")


def _reported():
    """El primer reto del combinabejas: obtener tu primera combinacion.
    No tiene interaccion, lo reporta el juego."""
    return Challenge(name="first-combination", title="Tu primera combinacion",
                     badges=[_badge()])


# ---------- Badge ----------

def test_badge_has_its_own_id():
    assert _badge().id != _badge().id


def test_badge_accepts_an_explicit_id():
    assert Badge(name="x", title="X", id="fijo").id == "fijo"


def test_badge_to_dict():
    assert set(_badge().to_dict()) == {"id", "name", "title", "icon", "description"}


def test_grant_creates_the_reward_for_the_user():
    badge, challenge = _badge(), _reported()
    reward = badge.grant(_user(), challenge=challenge, source="combinabejas")
    assert isinstance(reward, Reward)
    assert reward.userid == "local:levi"
    assert reward.badge is badge
    assert reward.challenge is challenge
    assert reward.source == "combinabejas"


def test_grant_starts_at_zero():
    """Lo que pidio el profesor: la recompensa existe aunque este en ceros."""
    assert _badge().grant(_user()).grants == JellyPack()
