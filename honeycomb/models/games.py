"""Nodos de videojuego, con sus retos, insignias y recompensas.

Los juegos son nodos: descienden de InteractiveCell, que ya vive en beehive.py.
Hay una clase por tipo de interactivo para que cada una pueda registrar su propia
vista, igual que CellText o CellWebContent registran las suyas en views/default.py.
Una instancia de CellCombiner seria, por ejemplo, el combinabejas con sus assets
y parametros.

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


class CellGame(InteractiveCell):
    """Base de los nodos de videojuego. Lo que todos comparten son sus retos.

    No se instancia directamente: cada tipo de interactivo tiene su subclase, para
    que Pyramid pueda despachar una vista distinta por tipo.
    """

    def __init__(self, name, title="", description=""):
        super().__init__(name=name, title=title)
        self.description = description
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
        """Las celdas hermanas se serializan a mano en views/api.py. Aqui si hay
        to_dict porque es lo que garantiza que ningun reto filtre su respuesta."""
        data = {
            "id": str(self.id),
            "name": self.__name__,
            "title": self.title,
            "description": self.description,
            "type": self.__class__.__name__,
        }
        if include_challenges:
            data["challenges"] = [c.to_dict() for c in self.challenges]
        return data


class CellQuiz(CellGame):
    """Juego de preguntas. Las preguntas viven en sus Challenge.

    No agrega campos: existe para que el quiz tenga su propia vista y para poder
    distinguirlo por tipo desde el frontend.
    """


class CellCombiner(CellGame):
    """Juego de combinar piezas. Una instancia suya es el combinabejas.

    `assets` son las imagenes y piezas con las que se arma, y `params` lo que
    cambia entre un combinador y otro.
    """

    def __init__(self, name, title="", description="", assets=None, params=None):
        super().__init__(name, title=title, description=description)
        self.assets = PersistentList(assets or [])
        self.params = PersistentMapping(params or {})

    def to_dict(self, include_challenges=True):
        data = super().to_dict(include_challenges=include_challenges)
        data["assets"] = list(self.assets)
        data["params"] = dict(self.params)
        return data
