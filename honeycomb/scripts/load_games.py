"""Carga en un servidor de honeycomb los juegos de prueba: el quiz y el combinabejas.

Usa la API HTTP de los juegos, asi que el servidor tiene que estar corriendo. Entra
con GET /login, que hoy inicia sesion sin contrasena, y manda el token CSRF en cada
POST. Se puede correr varias veces: un juego que ya existe no se vuelve a crear, y
un reto que el juego ya tiene, segun su name, no se vuelve a agregar.

    uv run python -m honeycomb.scripts.load_games
    uv run python -m honeycomb.scripts.load_games --url http://localhost:6543 --quiz otro.json

El quiz se lee en el formato que Alma usa en sus pruebas: una lista `questions` con
`id`, `question`, `options` y `answer`, que es la posicion de la opcion correcta.
"""

import argparse
import http.cookiejar
import json
import string
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from slugify import slugify

DEFAULT_QUIZ = Path(__file__).with_name("quiz_de_prueba.json")

LETTERS = string.ascii_lowercase

QUIZ = {"type": "PixiGame", "kind": "quiz", "name": "quiz", "title": "Quiz de abejas",
        "description": "Preguntas de prueba"}

COMBINER = {"type": "PixiGame", "kind": "combiner", "name": "combinabejas",
            "title": "Combinabejas", "description": "Arma una abeja con tres partes"}

# Lo detecta el propio juego, por eso no lleva interaction. El titulo de la insignia
# es provisional y falta su icono.
COMBINER_CHALLENGES = [{
    "name": "primera-abeja",
    "title": "Tu primera abeja",
    "description": "Crear el primer avatar",
    "badges": [{"name": "primera-abeja", "title": "Tu primera abeja"}],
}]


class LoadError(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Una redireccion llega como respuesta, para no confundir un 303 con un exito."""

    def redirect_request(self, *args, **kwargs):
        return None


class _SingleServerPolicy(http.cookiejar.DefaultCookiePolicy):
    """Regresa las cookies sin revisar su dominio, porque el script habla con un solo servidor.

    La cookie de sesion llega con Domain=localhost, y CookieJar no se la regresa a localhost.
    """

    def domain_return_ok(self, domain, request):
        return True

    def return_ok_domain(self, cookie, request):
        return True


class Client:
    """Cliente HTTP que guarda la sesion y el token CSRF de honeycomb."""

    def __init__(self, url):
        self.url = url.rstrip("/")
        parts = urllib.parse.urlsplit(self.url)
        # Pyramid revisa Origin cuando el servidor va por HTTPS.
        self.origin = f"{parts.scheme}://{parts.netloc}"
        self.cookies = http.cookiejar.CookieJar(_SingleServerPolicy())
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies), _NoRedirect)
        self.token = None

    def login(self):
        status, _ = self.send("GET", "/login")
        self.token = next((c.value for c in self.cookies if c.name == "csrf_token"), None)
        if status != 303 or self.token is None:
            raise LoadError(f"GET /login respondio {status} sin dar el token CSRF")

    def send(self, method, path, data=None):
        """El codigo de la respuesta y su cuerpo como JSON, o None si no es JSON."""
        body = None if data is None else json.dumps(data).encode()
        request = urllib.request.Request(
            self.url + path, data=body, method=method,
            headers={"Accept": "application/json", "Origin": self.origin})
        if body is not None:
            request.add_header("Content-Type", "application/json")
            request.add_header("X-CSRF-Token", self.token)
        try:
            with self.opener.open(request, timeout=30) as response:
                return response.status, _json(response.read())
        except urllib.error.HTTPError as error:
            return error.code, _json(error.read())
        except urllib.error.URLError as error:
            raise LoadError(f"No se pudo conectar con {self.url}: {error.reason}") from None


def _json(raw):
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _check(condition, message):
    if not condition:
        raise ValueError(message)


def quiz_challenges(quiz):
    """Los retos de tipo choice que salen del JSON del quiz.

    Cada opcion recibe una letra como id, y la respuesta correcta es la letra de la
    opcion que esta en la posicion `answer`.
    """
    questions = quiz.get("questions") if isinstance(quiz, dict) else None
    _check(isinstance(questions, list) and questions, "El quiz necesita una lista 'questions'")
    challenges = []
    for position, question in enumerate(questions, start=1):
        _check(isinstance(question, dict), f"La pregunta {position} no es un objeto")
        number = question.get("id", position)
        prompt, options, answer = (question.get(k) for k in ("question", "options", "answer"))
        _check(isinstance(prompt, str) and prompt.strip(), f"La pregunta {number} no tiene texto")
        _check(isinstance(options, list) and 2 <= len(options) <= len(LETTERS)
               and all(isinstance(option, str) for option in options),
               f"La pregunta {number} necesita entre 2 y {len(LETTERS)} opciones de texto")
        # bool queda fuera porque en Python True == 1.
        _check(isinstance(answer, int) and not isinstance(answer, bool)
               and 0 <= answer < len(options),
               f"La respuesta de la pregunta {number} no es la posicion de una opcion")
        choices = [{"id": letter, "text": text} for letter, text in zip(LETTERS, options)]
        challenges.append({
            "name": slugify(f"pregunta-{number}"),
            "title": f"Pregunta {number}",
            "prompt": prompt,
            "interaction": "choice",
            "choices": choices,
            "correct_response": choices[answer]["id"],
        })
    names = [challenge["name"] for challenge in challenges]
    _check(len(set(names)) == len(names), "Hay preguntas con el mismo id")
    return challenges


def _failure(action, status, body):
    detail = body.get("error") if isinstance(body, dict) else None
    return f"No se pudo {action}: respondio {status} {detail or ''}".strip()


def _game(client, path):
    status, body = client.send("GET", path)
    if status != 200 or not isinstance(body, dict) or "challenges" not in body:
        raise LoadError(f"'{path}' existe pero no es un juego")
    return body


def load_game(client, honeycomb, game, challenges):
    """Crea el juego si hace falta y le agrega los retos que no tenga.

    Devuelve el juego como estaba antes de agregar retos, si se creo y cuantos retos
    se agregaron.
    """
    status, body = client.send("POST", f"/{honeycomb}/@@juego", game)
    if status not in (201, 409):
        raise LoadError(_failure(f"crear '{game['name']}'", status, body))
    created = status == 201
    path = f"/{honeycomb}/{game['name']}/"
    current = _game(client, path)
    if current.get("kind") != game["kind"]:
        raise LoadError(f"'{path}' ya existe con kind {current.get('kind')!r}")

    existing = {challenge["name"] for challenge in current["challenges"]}
    added = 0
    for challenge in challenges:
        if challenge["name"] in existing:
            continue
        status, body = client.send("POST", path + "@@reto", challenge)
        if status != 201:
            raise LoadError(_failure(f"agregar '{challenge['name']}'", status, body))
        added += 1
    return current, created, added


def main(argv=None):
    parser = argparse.ArgumentParser(description="Carga los juegos de prueba en honeycomb.")
    parser.add_argument("--url", default="http://localhost:6543", help="donde corre honeycomb")
    parser.add_argument("--honeycomb", default="abejas", help="panal donde quedan los juegos")
    parser.add_argument("--quiz", type=Path, default=DEFAULT_QUIZ, help="JSON con las preguntas")
    args = parser.parse_args(argv)

    try:
        quiz = quiz_challenges(json.loads(args.quiz.read_text(encoding="utf-8")))
        client = Client(args.url)
        client.login()
        for game, challenges in ((QUIZ, quiz), (COMBINER, COMBINER_CHALLENGES)):
            current, created, added = load_game(client, args.honeycomb, game, challenges)
            state = "creado" if created else "ya existia"
            total = len(current["challenges"]) + added
            print(f"{game['name']}: {state}. Retos agregados: {added}. Total: {total}.")
            print(f"  id {current['id']}  {client.url}/{args.honeycomb}/{game['name']}/")
    except (LoadError, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
