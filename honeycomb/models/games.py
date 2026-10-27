"""Nodos de videojuego, con sus retos, insignias y recompensas.

Los juegos son nodos: descienden de InteractiveCell, que ya vive en beehive.py.
GameCell es la base compartida por los juegos de Pixi.js y de Unity, y hay una
subclase por tecnologia para que cada una pueda registrar su propia vista y
entregar sus assets en el formato que necesita. El quiz y el combinabejas son
instancias de PixiGame.

Catalogo y asignacion son cosas distintas. El catalogo (el nodo, sus Challenge y
sus Badge) se define una vez y es igual para todos. La asignacion (Reward) se crea
una vez por cada logro conseguido por cada jugador, con Badge.grant().

Los retos siguen las interacciones simples de QTI 3.0, seccion 2.4.1:
https://www.imsglobal.org/sites/default/files/spec/qti/v3/info/imsqti_asi_v3p0p1_infomodel_v1p0.html#Main2p4

La respuesta correcta de un Challenge nunca sale hacia el cliente: to_dict() no la
incluye y la unica forma de usarla es check_proof(), que corre en el servidor.
"""

from persistent import Persistent
from persistent.list import PersistentList
from persistent.mapping import PersistentMapping
from .axes import JellyPack
from .beehive import InteractiveCell
import datetime
import uuid

# Interacciones simples de QTI con el tipo base y las cardinalidades que la
# especificacion permite para su respuesta. La primera es la de omision.
INTERACTIONS = {
    "choice": ("identifier", ("single", "multiple")),
    "order": ("identifier", ("ordered",)),
    "associate": ("pair", ("multiple", "single")),
    "match": ("directedPair", ("multiple", "single")),
    "gapMatch": ("directedPair", ("multiple", "single")),
}


def _now():
    """Marca de tiempo UTC en ISO-8601, serializable a JSON."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _identifier(value):
    # bool queda fuera porque en Python True == 1 y pasaria por la opcion 1.
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f"identificador invalido: {value!r}")
    return value


def _value(value, base_type):
    """Un valor de respuesta en forma comparable segun su tipo base QTI."""
    if base_type == "identifier":
        return _identifier(value)
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"se esperaba un par: {value!r}")
    first, second = _identifier(value[0]), _identifier(value[1])
    # En pair el orden no importa. En directedPair si.
    if base_type == "pair":
        return frozenset((first, second))
    return (first, second)


def _response(response, base_type, cardinality):
    """Una respuesta completa en forma comparable.

    Una cadena nunca cuenta como lista: "AB" no es ["A", "B"].
    """
    if cardinality == "single":
        return _value(response, base_type)
    if not isinstance(response, (list, tuple)):
        raise ValueError(f"se esperaba una lista: {response!r}")
    values = [_value(v, base_type) for v in response]
    return values if cardinality == "ordered" else frozenset(values)


class Badge(Persistent):
    """Lo que se otorga al superar un reto, y lo que el jugador comparte.

    Existe una sola vez en el catalogo aunque la ganen muchas personas. Reemplaza
    a PollenBadge, que quedo sin usarse en beehive.py y no es Persistent.
    """

    def __init__(self, name, title, icon=None, description="", id=None):
        self.id = id or str(uuid.uuid4())
        self.name = name
        self.title = title
        self.icon = icon
        self.description = description

    def grant(self, user, challenge=None, source=None, grants=None):
        """Otorga esta insignia a `user` y devuelve la Reward que lo registra.

        Todavia no la guarda en ningun lado: el lugar depende de como se
        resuelva la identidad del usuario.
        """
        return Reward(user.userid, self, challenge=challenge, source=source,
                      grants=grants)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "title": self.title,
            "icon": self.icon,
            "description": self.description,
        }


class Challenge(Persistent):
    """Un reto dentro de un juego. Al superarlo se otorgan sus insignias.

    No todos los retos son preguntas. `interaction` es una de las interacciones
    simples de QTI y la prueba que manda el jugador se compara con
    `correct_response` segun las reglas de esa interaccion. Las opciones se
    identifican por id y no por posicion, asi se pueden barajar sin romper la
    respuesta.

    Un reto sin interaccion lo reporta el propio juego, como el de obtener la
    primera combinacion. check_proof() lo rechaza siempre, y su insignia se
    otorga directo con Badge.grant().

    `assets` son los que el reto necesita aparte de los del juego, por ejemplo
    la imagen que hay que identificar.
    """

    def __init__(self, name, title, badges, description="", interaction=None,
                 cardinality=None, prompt="", choices=None, correct_response=None,
                 assets=None, id=None):
        if interaction is not None:
            if interaction not in INTERACTIONS:
                raise ValueError(f"interaccion desconocida: {interaction!r}")
            allowed = INTERACTIONS[interaction][1]
            cardinality = cardinality or allowed[0]
            if cardinality not in allowed:
                raise ValueError(f"{interaction} no admite cardinalidad {cardinality!r}")
        self.id = id or str(uuid.uuid4())
        self.name = name
        self.title = title
        self.description = description
        self.badges = PersistentList(badges)
        self.interaction = interaction
        self.cardinality = cardinality
        self.prompt = prompt
        self.choices = PersistentList(choices or [])
        self.assets = PersistentMapping(assets or {})
        # Privado a proposito. Se valida aqui para que un catalogo mal cargado
        # truene al crearlo y no en medio de una partida.
        self.correct_response = correct_response
        if self.is_verifiable():
            self._comparable(correct_response)

    def is_verifiable(self):
        """Si el servidor puede decidir por su cuenta que el reto se supero."""
        return self.interaction is not None and self.correct_response is not None

    def _comparable(self, response):
        base_type = INTERACTIONS[self.interaction][0]
        return _response(response, base_type, self.cardinality)

    def check_proof(self, proof):
        """Devuelve las insignias ganadas con esta prueba, o una lista vacia.

        Es la unica forma de usar la respuesta correcta y solo corre en el
        servidor. Una prueba mal formada cuenta como incorrecta, no truena.
        """
        if not self.is_verifiable():
            return []
        try:
            passed = self._comparable(proof) == self._comparable(self.correct_response)
        except ValueError:
            return []
        return list(self.badges) if passed else []

    def to_dict(self):
        """Vista publica. No incluye `correct_response` ni debe incluirla nunca."""
        return {
            "id": self.id,
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "interaction": self.interaction,
            "cardinality": self.cardinality,
            "prompt": self.prompt,
            "choices": list(self.choices),
            "assets": dict(self.assets),
            "badges": [badge.to_dict() for badge in self.badges],
        }


class Reward(Persistent):
    """El registro de que un jugador gano una insignia. Es la micro verificacion.

    A diferencia de la insignia, que es una sola en el catalogo, aqui hay una por
    cada persona que la consiguio, con su marca de tiempo. Se crea con
    Badge.grant().

    `grants` es lo que ese logro suma en los ejes de axes.py, codificado como
    JellyPack. Nace en ceros. Como se calcula para cada reto a partir del
    `__axes__` del juego sigue en discusion.
    """

    def __init__(self, userid, badge, challenge=None, source=None, grants=None):
        self.userid = userid
        self.badge = badge
        self.challenge = challenge
        self.source = source
        self.grants = grants or JellyPack()
        self.awarded_at = _now()

    def to_dict(self):
        return {
            "userid": self.userid,
            "badge": self.badge.to_dict() if self.badge else None,
            "challenge_id": self.challenge.id if self.challenge else None,
            "source": self.source,
            "grants": self.grants._asdict(),
            "awarded_at": self.awarded_at,
        }


class GameCell(InteractiveCell):
    """Base compartida por los juegos de Pixi.js y de Unity.

    Le da a cada juego sus parametros generales y pone a su disposicion los
    assets en el formato que pide su tecnologia. No se instancia directamente:
    cada tecnologia tiene su subclase, para que Pyramid despache una vista
    distinta por cada una.
    """

    def __init__(self, name, kind, title="", description="", params=None,
                 assets=None):
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError(f"kind invalido: {kind!r}")
        super().__init__(name=name, title=title)
        self.kind = kind
        self.description = description
        # Los valores de params y assets se reemplazan completos: ZODB no ve
        # los cambios hechos por dentro de un valor.
        self.params = PersistentMapping(params or {})
        self.assets = PersistentMapping(assets or {})
        self.challenges = PersistentList()

    def add_challenge(self, challenge):
        """Idempotente por id: agregar dos veces el mismo reto no lo duplica."""
        for existing in self.challenges:
            if existing.id == challenge.id:
                return existing
        self.challenges.append(challenge)
        return challenge

    def get_challenge(self, challenge_id):
        for challenge in self.challenges:
            if challenge.id == challenge_id:
                return challenge
        return None

    def to_dict(self, include_challenges=True):
        """Las celdas hermanas se serializan en sus vistas. Aqui si hay to_dict
        porque es lo que garantiza que ningun reto filtre su respuesta."""
        data = {
            "id": str(self.id),
            "name": self.__name__,
            "title": self.title,
            "description": self.description,
            "type": self.__class__.__name__,
            "kind": self.kind,
            "params": dict(self.params),
            "assets": dict(self.assets),
        }
        if include_challenges:
            data["challenges"] = [c.to_dict() for c in self.challenges]
        return data


class PixiGame(GameCell):
    """Juego hecho con Pixi.js, como el quiz y el combinabejas.

    Sus assets se entregan de preferencia como spritesheet JSON de Pixi, con
    `frames` y `meta`, donde `meta.image` apunta a la imagen que los contiene:
    https://pixijs.download/release/docs/assets.Spritesheet.html
    """


class UnityGame(GameCell):
    """Juego compilado con Unity para WebGL, como abejopolis y libado.

    El formato de sus assets esta por definirse. Lo que hoy recibe el cargador
    de Unity es dataUrl, frameworkUrl, codeUrl y streamingAssetsUrl.
    """
