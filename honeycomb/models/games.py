"""Nodos de videojuego, con sus retos, insignias y recompensas.

Los juegos son nodos: descienden de InteractiveCell, que ya vive en beehive.py.
GameCell es la base compartida por los juegos de Pixi.js y de Unity, y hay una
subclase por tecnologia para que cada una pueda registrar su propia vista y
entregar sus assets en el formato que necesita. El quiz y el combinabejas son
instancias de PixiGame.

Catalogo y asignacion son cosas distintas. El catalogo (el nodo, sus Challenge y
sus Badge) se define una vez y es igual para todos. La asignacion (Reward) se crea
una vez por cada logro conseguido por cada jugador.

La respuesta correcta de un Challenge nunca sale hacia el cliente: to_dict() no la
incluye y la unica forma de usarla es check_answer(), que corre en el servidor.
"""

from persistent import Persistent
from persistent.list import PersistentList
from persistent.mapping import PersistentMapping
from .axes import JellyPack
from .beehive import InteractiveCell
import datetime
import uuid


def _now():
    """Marca de tiempo UTC en ISO-8601, serializable a JSON."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class Badge(Persistent):
    """Lo que se otorga al superar un reto, y lo que el jugador comparte.

    Existe una sola vez en el catalogo aunque la ganen muchas personas. Reemplaza
    a PollenBadge, que quedo sin usarse en beehive.py con estos mismos campos.
    """

    def __init__(self, name, title, icon=None, description="", id=None):
        self.id = id or str(uuid.uuid4())
        self.name = name
        self.title = title
        self.icon = icon
        self.description = description

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "title": self.title,
            "icon": self.icon,
            "description": self.description,
        }


class Challenge(Persistent):
    """Un reto dentro de un juego. Al superarlo se otorga su insignia.

    Cuando el reto es una pregunta, `options` son las que ve el jugador y `answer`
    es el indice de la correcta. Ese indice se queda en el servidor. Un reto sin
    `answer` configurada no se puede superar por esta via: lo reporta el juego,
    como el de obtener la primera combinacion.
    """

    def __init__(self, name, title, badge, description="",
                 question="", options=None, answer=None, id=None):
        self.id = id or str(uuid.uuid4())
        self.name = name
        self.title = title
        self.description = description
        self.badge = badge
        self.question = question
        self.options = PersistentList(options or [])
        # Indice de la opcion correcta. Privado a proposito.
        self.answer = answer

    def is_question(self):
        return bool(self.question) and self.answer is not None

    def check_answer(self, answer):
        """Unica forma de usar la respuesta correcta. Solo corre en el servidor."""
        if self.answer is None:
            return False
        return answer == self.answer

    def to_dict(self):
        """Vista publica. No incluye `answer` ni debe incluirla nunca."""
        return {
            "id": self.id,
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "question": self.question,
            "options": list(self.options),
            "badge": self.badge.to_dict() if self.badge else None,
        }


class Reward(Persistent):
    """El registro de que un jugador supero un reto. Es la micro verificacion.

    A diferencia de la insignia, que es una sola en el catalogo, aqui hay una por
    cada persona que la consiguio, con su marca de tiempo.

    `grants` es lo que ese logro suma a las estadisticas del jugador, en los ejes
    de axes.py. Nace en ceros. Queda pendiente confirmar con el profesor si las
    estadisticas del usuario son efectivamente ese JellyPack.
    """

    def __init__(self, userid, badge, challenge, source=None, grants=None):
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

    def __init__(self, name, title="", description="", params=None, assets=None):
        super().__init__(name=name, title=title)
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
