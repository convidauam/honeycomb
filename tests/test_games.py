import json

import pytest

from honeycomb.models.axes import JellyPack
from honeycomb.models.beehive import CellLeaf, InteractiveCell
from honeycomb.models.games import (
    Badge,
    Challenge,
    GameCell,
    PixiGame,
    Reward,
    UnityGame,
)
from honeycomb.models.users import DroneUser


def _badge():
    return Badge(name="first-avatar", title="Tu primer avatar", icon="abeja")


def _user(userid="local:levi"):
    return DroneUser(userid, "Levi", "levi")


def _choice(badges=None):
    """La pregunta real del QuizTemplate, con las opciones identificadas por id."""
    return Challenge(
        name="pecoreo", title="Que es el pecoreo",
        badges=badges if badges is not None else [_badge()],
        interaction="choice",
        prompt="Que es el pecoreo?",
        choices=[
            {"id": "casa", "text": "Buscar casa"},
            {"id": "limpiar", "text": "Limpiar la colmena"},
            {"id": "nectar", "text": "Ir por nectar"},
            {"id": "miel", "text": "Retirar la miel"},
        ],
        correct_response="nectar",
    )


def _reported():
    """El primer reto del combinabejas: obtener tu primera combinacion.
    No tiene interaccion, lo reporta el juego."""
    return Challenge(name="first-combination", title="Tu primera combinacion",
                     badges=[_badge()])


def _challenge(interaction, correct_response, cardinality=None):
    return Challenge(name="r", title="R", badges=[_badge()], interaction=interaction,
                     cardinality=cardinality, correct_response=correct_response)


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


# ---------- Challenge: choice ----------

def test_choice_accepts_the_right_option():
    challenge = _choice()
    assert challenge.check_proof("nectar") == list(challenge.badges)


def test_choice_rejects_the_wrong_ones():
    challenge = _choice()
    for wrong in ("casa", "limpiar", "miel"):
        assert challenge.check_proof(wrong) == []


def test_check_proof_returns_every_badge():
    first, second = _badge(), Badge(name="b2", title="Segunda")
    assert _choice(badges=[first, second]).check_proof("nectar") == [first, second]


def test_options_are_identified_not_positional():
    """La respuesta ya no es un indice: barajar las opciones no la rompe."""
    assert _choice().check_proof(2) == []


def test_choice_multiple_ignores_order_but_not_content():
    challenge = _challenge("choice", ["a", "c"], cardinality="multiple")
    assert challenge.check_proof(["c", "a"])
    assert challenge.check_proof(["a"]) == []
    assert challenge.check_proof(["a", "b", "c"]) == []


# ---------- Challenge: las demas interacciones simples ----------

def test_order_needs_the_exact_sequence():
    challenge = _challenge("order", ["huevo", "larva", "pupa", "adulta"])
    assert challenge.check_proof(["huevo", "larva", "pupa", "adulta"])
    assert challenge.check_proof(["larva", "huevo", "pupa", "adulta"]) == []


def test_associate_pairs_have_no_direction():
    challenge = _challenge("associate", [["ala", "vuelo"], ["antena", "olfato"]])
    assert challenge.check_proof([["olfato", "antena"], ["vuelo", "ala"]])
    assert challenge.check_proof([["ala", "olfato"], ["antena", "vuelo"]]) == []


def test_match_pairs_have_direction():
    challenge = _challenge("match", [["obrera", "pecorea"], ["reina", "pone"]])
    assert challenge.check_proof([["reina", "pone"], ["obrera", "pecorea"]])
    assert challenge.check_proof([["pecorea", "obrera"], ["pone", "reina"]]) == []


def test_gap_match_is_checked_like_match():
    challenge = _challenge("gapMatch", [["nectar", "hueco1"]])
    assert challenge.check_proof([["nectar", "hueco1"]])
    assert challenge.check_proof([["hueco1", "nectar"]]) == []


# ---------- Challenge: pruebas tramposas o mal formadas ----------

def test_a_string_is_not_a_list():
    """Sin esta regla, "ac" pasaria por ["a", "c"] al iterarse letra por letra."""
    assert _challenge("choice", ["a", "c"], cardinality="multiple").check_proof("ac") == []


def test_true_is_not_option_one():
    assert _challenge("choice", 1).check_proof(True) == []


def test_malformed_proofs_fail_instead_of_crashing():
    challenge = _challenge("match", [["a", "b"]])
    for proof in (None, {}, "ab", 3.5, [["a"]], [["a", "b", "c"]], [[{}, "b"]]):
        assert challenge.check_proof(proof) == []


def test_reported_challenge_never_passes_check_proof():
    challenge = _reported()
    assert challenge.is_verifiable() is False
    for proof in (None, 0, "cualquier", ["a"]):
        assert challenge.check_proof(proof) == []


def test_is_verifiable_needs_interaction_and_response():
    assert _choice().is_verifiable() is True
    assert Challenge(name="a", title="A", badges=[], interaction="choice").is_verifiable() is False


# ---------- Challenge: catalogo mal cargado ----------

def test_unknown_interaction_is_rejected():
    with pytest.raises(ValueError):
        _challenge("hotspot", "x")


def test_cardinality_must_be_allowed_by_qti():
    with pytest.raises(ValueError):
        _challenge("order", "a", cardinality="single")


def test_default_cardinality():
    assert _challenge("choice", "a").cardinality == "single"
    assert _challenge("order", ["a", "b"]).cardinality == "ordered"
    assert _challenge("match", [["a", "b"]]).cardinality == "multiple"


def test_bad_catalog_fails_when_loaded():
    with pytest.raises(ValueError):
        _challenge("choice", "a", cardinality="multiple")


# ---------- Challenge: lo que sale hacia el cliente ----------

def test_challenge_to_dict_does_not_expose_the_answer():
    """La razon de ser del antitrampas: el cliente nunca debe recibir la respuesta."""
    assert "correct_response" not in json.dumps(_choice().to_dict())


def test_challenge_to_dict_exposes_what_the_player_needs():
    data = _choice().to_dict()
    assert data["interaction"] == "choice"
    assert data["cardinality"] == "single"
    assert data["prompt"] == "Que es el pecoreo?"
    assert len(data["choices"]) == 4
    assert data["badges"][0]["name"] == "first-avatar"


def test_challenge_can_carry_its_own_assets():
    challenge = Challenge(name="r", title="R", badges=[], assets={"imagen": "flor.png"})
    assert challenge.to_dict()["assets"] == {"imagen": "flor.png"}


# ---------- Los nodos de juego ----------

def test_a_game_is_a_node():
    """Lo que pidio el profesor: los juegos descienden de InteractiveCell."""
    game = PixiGame(name="quiz-abejas", title="Quiz de abejas", kind="quiz")
    assert isinstance(game, InteractiveCell)
    assert isinstance(game, CellLeaf)


def test_the_node_inherits_id_and_name_from_cellleaf():
    game = PixiGame(name="quiz-abejas", title="Quiz de abejas", kind="quiz")
    assert game.id is not None
    assert game.__name__ == "quiz-abejas"
    assert game.title == "Quiz de abejas"
    assert game.icon is None
    assert game.is_featured is False


def test_one_subclass_per_technology():
    pixi = PixiGame(name="p", title="P", kind="quiz")
    unity = UnityGame(name="u", title="U", kind="abejopolis")
    assert isinstance(pixi, GameCell)
    assert isinstance(unity, GameCell)
    assert not isinstance(pixi, UnityGame)
    assert not isinstance(unity, PixiGame)


def test_params_and_assets_live_in_the_base():
    game = UnityGame(name="abejopolis", title="Abejopolis", kind="abejopolis",
                     params={"productName": "Abejopolis"},
                     assets={"dataUrl": "Build/Abejopolis.data.gz"})
    assert game.params["productName"] == "Abejopolis"
    assert game.assets["dataUrl"] == "Build/Abejopolis.data.gz"


def test_a_game_starts_with_no_challenges():
    assert PixiGame(name="q", title="Q", kind="quiz").challenges == []


def test_add_challenge_is_idempotent():
    game = PixiGame(name="q", title="Q", kind="quiz")
    challenge = _choice()
    assert game.add_challenge(challenge) is game.add_challenge(challenge)
    assert len(game.challenges) == 1


def test_get_challenge():
    game = PixiGame(name="q", title="Q", kind="quiz")
    challenge = game.add_challenge(_choice())
    assert game.get_challenge(challenge.id) is challenge
    assert game.get_challenge("no-existe") is None


def test_game_to_dict_does_not_leak_its_challenges_answers():
    """El riesgo real: serializar el nodo completo y arrastrar la respuesta."""
    game = PixiGame(name="q", title="Q", kind="quiz")
    game.add_challenge(_choice())
    assert "correct_response" not in json.dumps(game.to_dict())


def test_game_to_dict_reports_its_type():
    assert PixiGame(name="q", title="Q", kind="quiz").to_dict()["type"] == "PixiGame"
    assert UnityGame(name="u", title="U", kind="abejopolis").to_dict()["type"] == "UnityGame"


def test_game_to_dict_can_omit_the_challenges():
    game = PixiGame(name="q", title="Q", kind="quiz")
    game.add_challenge(_choice())
    assert "challenges" not in game.to_dict(include_challenges=False)


def test_the_combinabejas_is_a_pixi_game_with_a_spritesheet():
    sheet = {
        "frames": {"ala-1.png": {"frame": {"x": 0, "y": 0, "w": 64, "h": 64},
                                 "spriteSourceSize": {"x": 0, "y": 0, "w": 64, "h": 64},
                                 "sourceSize": {"w": 64, "h": 64}}},
        "meta": {"image": "combinabejas.png", "format": "RGBA8888",
                 "size": {"w": 64, "h": 64}, "scale": "1"},
    }
    combinabejas = PixiGame(name="combinabejas", title="Combina Abejas",
                            kind="combiner",
                            params={"orientation": "vertical"},
                            assets={"partes": sheet})
    data = combinabejas.to_dict()
    assert data["kind"] == "combiner"
    assert data["params"] == {"orientation": "vertical"}
    assert data["assets"]["partes"]["meta"]["image"] == "combinabejas.png"
