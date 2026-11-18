"""El script que carga los juegos de prueba, contra un servidor de verdad.

El script habla HTTP, asi que aqui la app corre en waitress dentro de un hilo, con un
ZODB en disco como en test_game_views.
"""

import json
import socket
import threading

import pytest
import waitress
import webtest

from honeycomb import main
from honeycomb.scripts import load_games

QUIZ = {"questions": [
    {"id": 1, "question": "Que es el pecoreo?", "options": ["Buscar casa", "Ir por nectar"],
     "answer": 1},
    {"id": 2, "question": "Que producen?", "options": ["Miel", "Leche", "Seda"], "answer": 0},
]}


def _bundled_quiz():
    return json.loads(load_games.DEFAULT_QUIZ.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def live_app(app_settings, tmp_path_factory):
    folder = tmp_path_factory.mktemp("zodb")
    settings = {**app_settings, "auth.secret": "x" * 32,
                "zodbconn.uri": f"file://{folder}/Data.fs?blobstorage_dir={folder}/blobs"}
    app = main({}, **settings)
    yield app
    for db in app.registry._zodb_databases.values():
        db.close()


@pytest.fixture(scope="module")
def server(live_app):
    server = waitress.create_server(live_app, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    # localhost como en el uso normal, que es donde las cookies tienen mas detalles.
    yield f"http://localhost:{server.effective_port}"
    server.close()
    thread.join(timeout=5)


@pytest.fixture(scope="module")
def loaded(server):
    assert load_games.main(["--url", server]) == 0
    return server


@pytest.fixture
def anonymous(live_app):
    return webtest.TestApp(live_app)


# ---------- convertir el quiz ----------

def test_each_question_becomes_a_choice_challenge():
    first, second = load_games.quiz_challenges(QUIZ)
    assert first == {
        "name": "pregunta-1",
        "title": "Pregunta 1",
        "prompt": "Que es el pecoreo?",
        "interaction": "choice",
        "choices": [{"id": "a", "text": "Buscar casa"}, {"id": "b", "text": "Ir por nectar"}],
        "correct_response": "b",
    }
    assert second["correct_response"] == "a"


def test_a_question_without_id_uses_its_position():
    quiz = {"questions": [{"question": "P", "options": ["x", "y"], "answer": 0}]}
    assert load_games.quiz_challenges(quiz)[0]["name"] == "pregunta-1"


def test_the_bundled_quiz_has_five_questions():
    assert len(load_games.quiz_challenges(_bundled_quiz())) == 5


def _question(**fields):
    return {"questions": [{"id": 1, "question": "P", "options": ["x", "y"], "answer": 0,
                           **fields}]}


@pytest.mark.parametrize("quiz", [
    {},
    [],
    {"questions": []},
    {"questions": ["P"]},
    _question(question=""),
    _question(options=["x"]),
    _question(options=["x", 2]),
    _question(options=list("abcdefghijklmnopqrstuvwxyz") + ["otra"]),
    _question(answer=2),
    _question(answer=-1),
    _question(answer=True),
    _question(answer="0"),
    {"questions": [_question()["questions"][0], _question()["questions"][0]]},
])
def test_a_malformed_quiz_is_rejected(quiz):
    with pytest.raises(ValueError):
        load_games.quiz_challenges(quiz)


# ---------- cargar en el servidor ----------

def test_loads_the_quiz(loaded, anonymous):
    quiz = anonymous.get("/abejas/quiz/", status=200).json
    assert quiz["kind"] == "quiz"
    assert [c["name"] for c in quiz["challenges"]] == [f"pregunta-{n}" for n in range(1, 6)]
    assert all(c["interaction"] == "choice" for c in quiz["challenges"])


def test_loads_the_combiner(loaded, anonymous):
    combiner = anonymous.get("/abejas/combinabejas/", status=200).json
    assert combiner["kind"] == "combiner"
    [challenge] = combiner["challenges"]
    assert challenge["name"] == "primera-abeja"
    assert challenge["interaction"] is None
    assert [badge["name"] for badge in challenge["badges"]] == ["primera-abeja"]


def test_the_loaded_answers_are_the_ones_of_the_quiz(loaded, live_app):
    client = webtest.TestApp(live_app)
    client.get("/login", status=303)
    csrf = {"X-CSRF-Token": client.cookies["csrf_token"]}
    quiz = client.get("/abejas/quiz/").json
    for question, challenge in zip(_bundled_quiz()["questions"], quiz["challenges"]):
        right = "abcd"[question["answer"]]
        wrong = "abcd"[(question["answer"] + 1) % 4]
        for proof, expected in ((right, True), (wrong, False)):
            payload = {"challenge_id": challenge["id"], "proof": proof}
            body = client.post_json(quiz["proof_url"], payload, headers=csrf).json
            assert body["correct"] is expected


def test_running_it_again_adds_nothing(loaded, anonymous, capsys):
    assert load_games.main(["--url", loaded]) == 0
    assert "quiz: ya existia. Retos agregados: 0. Total: 5." in capsys.readouterr().out
    assert len(anonymous.get("/abejas/quiz/").json["challenges"]) == 5
    assert len(anonymous.get("/abejas/combinabejas/").json["challenges"]) == 1


def test_a_node_with_the_name_and_another_kind_is_an_error(loaded, monkeypatch, capsys):
    monkeypatch.setattr(load_games, "COMBINER", {**load_games.COMBINER, "name": "quiz"})
    assert load_games.main(["--url", loaded]) == 1
    assert "ya existe con kind 'quiz'" in capsys.readouterr().err


def test_a_stopped_server_is_an_error(capsys):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    assert load_games.main(["--url", f"http://127.0.0.1:{port}"]) == 1
    assert "No se pudo conectar" in capsys.readouterr().err


def test_a_malformed_quiz_file_is_an_error(tmp_path, capsys):
    quiz = tmp_path / "quiz.json"
    quiz.write_text(json.dumps(_question(answer=5)), encoding="utf-8")
    assert load_games.main(["--quiz", str(quiz)]) == 1
    assert "no es la posicion de una opcion" in capsys.readouterr().err
