"""Las vistas de juegos contra la app completa.

Usan un ZODB en disco y no el testapp de conftest, porque ese aborta la transaccion
de cada peticion y lo creado en una no lo ve la siguiente.
"""

import uuid

import pytest
import webtest
from slugify import slugify

from honeycomb import main

CHOICE = {
    "title": "Que es el pecoreo",
    "interaction": "choice",
    "prompt": "Que es el pecoreo?",
    "choices": [{"id": "casa", "text": "Buscar casa"},
                {"id": "nectar", "text": "Ir por nectar"}],
    "correct_response": "nectar",
    "badges": [{"name": "primer-pecoreo", "title": "Primer pecoreo", "icon": "abeja"}],
}

PUBLIC_CHALLENGE_KEYS = {"id", "name", "title", "description", "interaction",
                         "cardinality", "prompt", "choices", "assets", "badges"}


@pytest.fixture(scope="module")
def live_app(app_settings, tmp_path_factory):
    folder = tmp_path_factory.mktemp("zodb")
    settings = {**app_settings, "auth.secret": "x" * 32,
                "zodbconn.uri": f"file://{folder}/Data.fs?blobstorage_dir={folder}/blobs"}
    app = main({}, **settings)
    yield app
    for db in app.registry._zodb_databases.values():
        db.close()


@pytest.fixture
def anonymous(live_app):
    return webtest.TestApp(live_app)


@pytest.fixture
def client(live_app):
    """Un cliente con sesion: /login entra como el usuario de prueba."""
    client = webtest.TestApp(live_app)
    client.get("/login", status=303)
    return client


@pytest.fixture
def csrf(client):
    return {"X-CSRF-Token": client.cookies["csrf_token"]}


def _title():
    return f"Quiz {uuid.uuid4().hex[:8]}"


@pytest.fixture
def game(client, csrf):
    payload = {"type": "PixiGame", "kind": "quiz", "title": _title()}
    return client.post_json("/abejas/@@juego", payload, headers=csrf, status=201).json


def _challenge(client, csrf, game, **fields):
    return client.post_json(game["url"] + "@@reto", {**CHOICE, **fields},
                            headers=csrf, status=201).json


def _prove(client, csrf, game, challenge, proof):
    payload = {"challenge_id": challenge["id"], "proof": proof}
    return client.post_json(game["proof_url"], payload, headers=csrf, status=200).json


def _in_database(app, *path):
    """El nodo que esta en `path` desde la raiz, abierto en una conexion aparte."""
    connection = app.registry._zodb_databases[""].open()
    try:
        node = connection.root()["app_root"]
        for name in path:
            node = node[name]
        return node
    finally:
        connection.close()


def _node_id(app, *path):
    return str(_in_database(app, *path).id)


def _is_indexed(app, node_id):
    return node_id in _in_database(app).__nodes__


# ---------- crear un juego ----------

def test_create_a_pixi_game(client, csrf):
    title = _title()
    payload = {"type": "PixiGame", "kind": "quiz", "title": title,
               "description": "Preguntas", "params": {"rounds": 5},
               "assets": {"fondo": "fondo.png"}}
    body = client.post_json("/abejas/@@juego", payload, headers=csrf, status=201).json
    assert body["status"] == "creado"
    assert body["type"] == "PixiGame"
    assert body["kind"] == "quiz"
    assert body["name"] == slugify(title)
    assert body["title"] == title
    assert body["description"] == "Preguntas"
    assert body["params"] == {"rounds": 5}
    assert body["assets"] == {"fondo": "fondo.png"}
    assert body["challenges"] == []
    assert body["url"].endswith(f"/abejas/{body['name']}/")


def test_create_a_unity_game(client, csrf):
    payload = {"type": "UnityGame", "kind": "abejopolis", "title": _title()}
    body = client.post_json("/abejas/@@juego", payload, headers=csrf, status=201).json
    assert body["type"] == "UnityGame"
    assert body["kind"] == "abejopolis"


def test_a_created_game_is_there_for_everyone(anonymous, game):
    assert anonymous.get(game["url"], status=200).json["id"] == game["id"]


def test_create_slugifies_the_name(client, csrf):
    name = f"Mi Quiz {uuid.uuid4().hex[:8]}!"
    payload = {"type": "PixiGame", "kind": "quiz", "title": "Titulo", "name": name}
    body = client.post_json("/abejas/@@juego", payload, headers=csrf, status=201).json
    assert body["name"] == slugify(name)
    assert "!" not in body["url"]


def test_create_refuses_to_overwrite_an_existing_node(client, csrf, game, anonymous):
    payload = {"type": "UnityGame", "kind": "otro", "title": "Otro", "name": game["name"]}
    client.post_json("/abejas/@@juego", payload, headers=csrf, status=409)
    assert anonymous.get(game["url"]).json["title"] == game["title"]


BAD_GAMES = [
    {"kind": "quiz", "title": "T"},
    {"type": "NoExiste", "kind": "quiz", "title": "T"},
    {"type": ["PixiGame"], "kind": "quiz", "title": "T"},
    {"type": "PixiGame", "title": "T"},
    {"type": "PixiGame", "kind": "   ", "title": "T"},
    {"type": "PixiGame", "kind": 3, "title": "T"},
    {"type": "PixiGame", "kind": "quiz"},
    {"type": "PixiGame", "kind": "quiz", "title": "T", "params": [1]},
    {"type": "PixiGame", "kind": "quiz", "title": "T", "assets": "x"},
    {"type": "PixiGame", "kind": "quiz", "title": "T", "description": 5},
    {"type": "PixiGame", "kind": "quiz", "title": "???"},
    {"type": "PixiGame", "kind": "quiz", "title": "T", "parent": ["x"]},
]


@pytest.mark.parametrize("payload", BAD_GAMES)
def test_create_rejects_bad_input(client, csrf, payload):
    assert "error" in client.post_json("/abejas/@@juego", payload, headers=csrf, status=400).json


def test_create_rejects_a_body_that_is_not_json(client, csrf):
    client.post("/abejas/@@juego", params="no es json", content_type="application/json",
                headers=csrf, status=400)


def test_create_rejects_json_that_is_not_an_object(client, csrf):
    client.post_json("/abejas/@@juego", ["PixiGame"], headers=csrf, status=400)


def test_create_needs_the_csrf_token(client):
    payload = {"type": "PixiGame", "kind": "quiz", "title": _title()}
    client.post_json("/abejas/@@juego", payload, status=400)


def test_create_needs_a_session(anonymous):
    title = _title()
    payload = {"type": "PixiGame", "kind": "quiz", "title": title}
    anonymous.post_json("/abejas/@@juego", payload, status=303)
    anonymous.get(f"/abejas/{slugify(title)}", status=404)


def test_create_under_a_parent_node(client, csrf, live_app):
    payload = {"type": "PixiGame", "kind": "quiz", "title": _title(),
               "parent": _node_id(live_app, "abejas", "mapa-sitio")}
    body = client.post_json("/abejas/@@juego", payload, headers=csrf, status=201).json
    assert "/abejas/mapa-sitio/" in body["url"]
    client.get(body["url"], status=200)


def test_create_under_an_unknown_parent(client, csrf):
    payload = {"type": "PixiGame", "kind": "quiz", "title": _title(),
               "parent": str(uuid.uuid4())}
    client.post_json("/abejas/@@juego", payload, headers=csrf, status=404)


def test_create_under_a_parent_that_cannot_hold_nodes(client, csrf, live_app):
    payload = {"type": "PixiGame", "kind": "quiz", "title": _title(),
               "parent": _node_id(live_app, "abejas", "abejopolis")}
    client.post_json("/abejas/@@juego", payload, headers=csrf, status=400)


# ---------- leer un juego ----------

def test_get_the_game(anonymous, game):
    body = anonymous.get(game["url"], status=200).json
    assert body["id"] == game["id"]
    assert body["kind"] == "quiz"
    assert body["type"] == "PixiGame"
    assert body["challenges"] == []
    assert body["url"] == game["url"]
    assert body["proof_url"] == game["url"] + "@@prueba"


def test_get_an_unknown_game(anonymous):
    anonymous.get("/abejas/no-existe", status=404)


def test_the_honeycomb_page_still_renders_with_a_game(client, game):
    client.get("/abejas/", status=200)


def test_the_honeycomb_api_lists_the_game(anonymous, game):
    body = anonymous.get("/api/v1/honeycombs/abejas", status=200).json
    assert game["id"] in [node["id"] for node in body["nodes"]]


def test_the_node_api_knows_the_game_but_not_its_challenges(client, csrf, game, anonymous):
    """La otra puerta a los mismos datos: la API de nodos que usa el frontend."""
    _challenge(client, csrf, game)
    res = anonymous.get(f"/api/v1/node/{game['id']}", status=200)
    assert res.json["url"] == game["url"]
    assert res.json["type"] == "leaf"
    assert "challenge" not in res.text
    assert "correct_response" not in res.text


def test_a_challenge_never_shows_its_correct_response(client, csrf, game, anonymous):
    created = _challenge(client, csrf, game)
    listed = anonymous.get(game["url"], status=200)
    assert "correct_response" not in listed.text
    assert set(created) == PUBLIC_CHALLENGE_KEYS | {"status"}
    assert set(listed.json["challenges"][0]) == PUBLIC_CHALLENGE_KEYS


# ---------- agregar retos ----------

def test_add_a_challenge(client, csrf, game, anonymous):
    created = _challenge(client, csrf, game)
    assert created["status"] == "creado"
    assert created["interaction"] == "choice"
    assert created["cardinality"] == "single"
    assert created["choices"] == CHOICE["choices"]
    assert [badge["name"] for badge in created["badges"]] == ["primer-pecoreo"]
    listed = anonymous.get(game["url"]).json["challenges"]
    assert listed == [{key: value for key, value in created.items() if key != "status"}]


def test_challenges_keep_the_order_they_were_added(client, csrf, game, anonymous):
    ids = [_challenge(client, csrf, game, title=f"Reto {n}")["id"] for n in range(3)]
    assert [c["id"] for c in anonymous.get(game["url"]).json["challenges"]] == ids


def test_add_a_challenge_the_game_reports_itself(client, csrf, game):
    payload = {"title": "Tu primera combinacion",
               "badges": [{"name": "primera-combinacion", "title": "Primera combinacion"}]}
    body = client.post_json(game["url"] + "@@reto", payload, headers=csrf, status=201).json
    assert body["interaction"] is None
    assert body["cardinality"] is None


BAD_CHALLENGES = [
    {},
    {"title": 5},
    {"title": "T", "interaction": "no-existe"},
    {"title": "T", "interaction": ["choice"]},
    {"title": "T", "interaction": "choice", "cardinality": "ordered"},
    {"title": "T", "interaction": "choice", "correct_response": {"id": "a"}},
    {"title": "T", "interaction": "associate", "correct_response": [["a"]]},
    {"title": "T", "interaction": "order", "correct_response": "abc"},
    {"title": "T", "choices": "abc"},
    {"title": "T", "badges": {"name": "x"}},
    {"title": "T", "badges": ["x"]},
    {"title": "T", "badges": [{"name": "x"}]},
    {"title": "T", "assets": [1]},
]


@pytest.mark.parametrize("payload", BAD_CHALLENGES)
def test_add_challenge_rejects_bad_input(client, csrf, game, anonymous, payload):
    client.post_json(game["url"] + "@@reto", payload, headers=csrf, status=400)
    assert anonymous.get(game["url"]).json["challenges"] == []


def test_add_challenge_needs_the_csrf_token(client, game):
    client.post_json(game["url"] + "@@reto", CHOICE, status=400)


def test_add_challenge_needs_a_session(anonymous, game):
    anonymous.post_json(game["url"] + "@@reto", CHOICE, status=303)
    assert anonymous.get(game["url"]).json["challenges"] == []


# ---------- mandar la prueba ----------

def test_the_right_proof_is_correct_and_earns_the_badges(client, csrf, game):
    challenge = _challenge(client, csrf, game)
    body = _prove(client, csrf, game, challenge, "nectar")
    assert body["challenge_id"] == challenge["id"]
    assert body["correct"] is True
    assert [badge["name"] for badge in body["badges"]] == ["primer-pecoreo"]


def test_a_wrong_proof_is_incorrect_and_earns_nothing(client, csrf, game):
    challenge = _challenge(client, csrf, game)
    body = _prove(client, csrf, game, challenge, "casa")
    assert body == {"challenge_id": challenge["id"], "correct": False, "badges": []}


def test_a_correct_proof_without_badges_is_still_correct(client, csrf, game):
    challenge = _challenge(client, csrf, game, badges=[])
    body = _prove(client, csrf, game, challenge, "nectar")
    assert body["correct"] is True
    assert body["badges"] == []


@pytest.mark.parametrize("proof", [["nectar"], {"id": "nectar"}, 2, True, "", "NECTAR"])
def test_a_malformed_proof_is_just_incorrect(client, csrf, game, proof):
    challenge = _challenge(client, csrf, game)
    assert _prove(client, csrf, game, challenge, proof)["correct"] is False


def test_order_and_associate_proofs_travel_as_json_lists(client, csrf, game):
    order = _challenge(client, csrf, game, interaction="order",
                       choices=[{"id": "a"}, {"id": "b"}, {"id": "c"}],
                       correct_response=["a", "b", "c"])
    assert _prove(client, csrf, game, order, ["a", "b", "c"])["correct"] is True
    assert _prove(client, csrf, game, order, ["c", "b", "a"])["correct"] is False
    pairs = _challenge(client, csrf, game, interaction="associate",
                       correct_response=[["a", "x"], ["b", "y"]])
    assert _prove(client, csrf, game, pairs, [["y", "b"], ["x", "a"]])["correct"] is True
    assert _prove(client, csrf, game, pairs, [["a", "y"], ["b", "x"]])["correct"] is False


def test_the_proof_stores_nothing(client, csrf, game, anonymous):
    challenge = _challenge(client, csrf, game)
    before = anonymous.get(game["url"]).json
    _prove(client, csrf, game, challenge, "nectar")
    assert anonymous.get(game["url"]).json == before


def test_a_proof_for_an_unknown_challenge(client, csrf, game):
    payload = {"challenge_id": "no-existe", "proof": "nectar"}
    client.post_json(game["proof_url"], payload, headers=csrf, status=404)


def test_a_challenge_the_game_reports_cannot_be_proven(client, csrf, game):
    reported = client.post_json(game["url"] + "@@reto", {"title": "Reportado"},
                                headers=csrf, status=201).json
    payload = {"challenge_id": reported["id"], "proof": "lo que sea"}
    client.post_json(game["proof_url"], payload, headers=csrf, status=400)


def test_a_proof_needs_the_challenge_and_the_proof(client, csrf, game):
    challenge = _challenge(client, csrf, game)
    for payload in ({}, {"challenge_id": challenge["id"]}, {"proof": "nectar"},
                    {"challenge_id": challenge["id"], "proof": None}):
        client.post_json(game["proof_url"], payload, headers=csrf, status=400)


def test_a_proof_needs_the_csrf_token(client, csrf, game):
    challenge = _challenge(client, csrf, game)
    client.post_json(game["proof_url"], {"challenge_id": challenge["id"], "proof": "nectar"},
                     status=400)


def test_anyone_with_a_token_can_send_a_proof(live_app, client, csrf, game):
    challenge = _challenge(client, csrf, game)
    player = webtest.TestApp(live_app)
    player.get("/login", status=303)
    headers = {"X-CSRF-Token": player.cookies["csrf_token"]}
    assert _prove(player, headers, game, challenge, "nectar")["correct"] is True


# ---------- actualizar un juego ----------

def test_update_a_game(client, csrf, game, anonymous):
    payload = {"title": "Otro titulo", "description": "d", "kind": "combiner",
               "params": {"a": 1}, "assets": {"b": "2"}}
    res = client.put_json(game["url"] + "@@admin", payload, headers=csrf, status=200)
    assert res.json == {"status": "actualizado", "id": game["id"]}
    body = anonymous.get(game["url"]).json
    assert (body["title"], body["description"], body["kind"]) == ("Otro titulo", "d", "combiner")
    assert body["params"] == {"a": 1}
    assert body["assets"] == {"b": "2"}
    assert body["name"] == game["name"]


def test_update_keeps_the_challenges(client, csrf, game, anonymous):
    challenge = _challenge(client, csrf, game)
    client.put_json(game["url"] + "@@admin", {"title": "Otro titulo"}, headers=csrf, status=200)
    assert [c["id"] for c in anonymous.get(game["url"]).json["challenges"]] == [challenge["id"]]


@pytest.mark.parametrize("payload", [
    {"kind": "   "},
    {"title": 3},
    {"params": [1]},
    {"assets": "x"},
    {"title": "Nuevo", "kind": ""},
])
def test_update_rejects_bad_input_and_changes_nothing(client, csrf, game, anonymous, payload):
    client.put_json(game["url"] + "@@admin", payload, headers=csrf, status=400)
    body = anonymous.get(game["url"]).json
    assert (body["title"], body["kind"]) == (game["title"], game["kind"])


def test_update_needs_the_csrf_token(client, game):
    client.put_json(game["url"] + "@@admin", {"title": "Nuevo"}, status=400)


def test_update_needs_a_session(anonymous, game):
    anonymous.put_json(game["url"] + "@@admin", {"title": "Nuevo"}, status=303)
    assert anonymous.get(game["url"]).json["title"] == game["title"]


# ---------- eliminar un juego ----------

def test_delete_a_game(client, csrf, game, anonymous, live_app):
    assert _is_indexed(live_app, game["id"])
    res = client.delete(game["url"] + "@@admin", headers=csrf, status=200)
    assert res.json == {"status": "eliminado", "id": game["id"]}
    anonymous.get(game["url"], status=404)
    assert not _is_indexed(live_app, game["id"])


def test_delete_needs_the_csrf_token(client, game):
    client.delete(game["url"] + "@@admin", status=400)


def test_delete_needs_a_session(anonymous, game):
    anonymous.delete(game["url"] + "@@admin", status=303)
    anonymous.get(game["url"], status=200)
