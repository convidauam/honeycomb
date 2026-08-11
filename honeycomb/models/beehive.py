from zope.interface import Interface, implementer
from persistent import Persistent
from persistent.mapping import PersistentMapping
from BTrees._OOBTree import OOBTree
from persistent.list import PersistentList
from .axes import CellBuilder
import datetime
import json, uuid


def _utcnow_iso():
    """Marca de tiempo UTC en formato ISO-8601 (serializable a JSON)."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class GameData(Persistent):
    """Datos persistentes de un videojuego para un usuario y un nodo.

    interactions y badges: solo lectura para el juego (los controla el servidor).
    stats y preferences: lectura/escritura.
    """

    def __init__(self, userid, nodeid):
        self.userid = userid
        self.nodeid = nodeid
        self.interactions = 0
        self.stats = PersistentMapping()
        self.preferences = PersistentMapping()
        self.badges = PersistentList()
        now = _utcnow_iso()
        self.first_seen = now
        self.last_seen = now

    def register_interaction(self):
        """Suma una interacción (uso exclusivo del servidor) y refresca ``last_seen``."""
        self.interactions += 1
        self.last_seen = _utcnow_iso()

    def merge_stats(self, stats, replace=False):
        if replace:
            self.stats.clear()
        for key, value in stats.items():
            self.stats[key] = value

    def merge_preferences(self, preferences, replace=False):
        if replace:
            self.preferences.clear()
        for key, value in preferences.items():
            self.preferences[key] = value

    def award_badge(self, badge_id, title, icon=None):
        """Otorga un logro (controlado por el servidor). Idempotente: si el
        usuario ya tiene este badge_id en este nodo, no lo duplica."""
        for badge in self.badges:
            if badge.id == badge_id:
                return badge
        badge = PollenBadge(badge_id, title, icon)
        self.badges.append(badge)
        self.last_seen = _utcnow_iso()
        return badge

    def to_dict(self):
        return {
            "userid": self.userid,
            "nodeid": self.nodeid,
            "interactions": self.interactions,
            "stats": dict(self.stats),
            "preferences": dict(self.preferences),
            "badges": [badge.to_dict() for badge in self.badges],
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
        }

class BeeHive(PersistentMapping):
    """A container of Honeycombs. This represents the top-level hierarchy which gives entry to honeycombs. It should
    display the user a mosaic view of available honeycombs, highlighting already completed and recently visited ones,
    as well as those featured by creators and managers."""
    __name__ = None
    __parent__ = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = str(uuid.uuid4())
        self.title = "BeeHive Root"
        self.__nodes__ = OOBTree()
        self.__edges__ = OOBTree()
        self.__game_data__ = OOBTree()
        self.__users__ = OOBTree()
        self.__oauth_apps__ = OOBTree()
        self.__identities__ = OOBTree()

    # datos de videojuegos (GameData): acceso homologado por usuario + nodo
    def get_game_data(self, userid, nodeid, create=False):
        """Obtiene el GameData de (userid, nodeid). Si no existe y create=True, lo crea."""
        if not hasattr(self, "__game_data__"):
            # BeeHive persistido antes de añadir este atributo.
            self.__game_data__ = OOBTree()
        user_bucket = self.__game_data__.get(userid)
        if user_bucket is None:
            if not create:
                return None
            user_bucket = OOBTree()
            self.__game_data__[userid] = user_bucket
        record = user_bucket.get(nodeid)
        if record is None and create:
            record = GameData(userid, nodeid)
            user_bucket[nodeid] = record
        return record

    def iter_user_badges(self, userid):
        """Genera (nodeid, PollenBadge) para cada logro del usuario, en cualquier nodo."""
        if not hasattr(self, "__game_data__"):
            return
        user_bucket = self.__game_data__.get(userid)
        if not user_bucket:
            return
        for nodeid, record in user_bucket.items():
            for badge in record.badges:
                yield nodeid, badge

    # usuarios autenticados vía identidad del Fediverso, keyed por userid canónico
    def get_user(self, userid):
        if not hasattr(self, "__users__"):
            self.__users__ = OOBTree()
        return self.__users__.get(userid)

    def upsert_user(self, drone_user):
        """Guarda o actualiza un DroneUser ya construido, indexado por su userid."""
        if not hasattr(self, "__users__"):
            self.__users__ = OOBTree()
        self.__users__[drone_user.userid] = drone_user
        return drone_user

    # credenciales OAuth registradas por instancia (dominio del Fediverso)
    def get_oauth_app(self, domain):
        if not hasattr(self, "__oauth_apps__"):
            self.__oauth_apps__ = OOBTree()
        return self.__oauth_apps__.get(domain)

    def set_oauth_app(self, domain, client_id, client_secret):
        if not hasattr(self, "__oauth_apps__"):
            self.__oauth_apps__ = OOBTree()
        self.__oauth_apps__[domain] = PersistentMapping({"client_id": client_id, "client_secret": client_secret})
        return self.__oauth_apps__[domain]

    # identidades: varias credenciales (Fediverso, contraseña local) pueden
    # apuntar a la misma cuenta. Clave con namespace explicito: 'fediverse:<actor_url>'
    # o 'password:<username>'. El userid primario de la cuenta no cambia por esto;
    # este indice solo dice a que userid resolver cada credencial.
    def resolve_identity(self, key):
        if not hasattr(self, "__identities__"):
            self.__identities__ = OOBTree()
        return self.__identities__.get(key)

    def link_identity(self, key, userid):
        if not hasattr(self, "__identities__"):
            self.__identities__ = OOBTree()
        self.__identities__[key] = userid

    def unlink_identity(self, key):
        if not hasattr(self, "__identities__"):
            self.__identities__ = OOBTree()
        if key in self.__identities__:
            del self.__identities__[key]

    def iter_identities(self, userid):
        if not hasattr(self, "__identities__"):
            return
        for key, linked_userid in self.__identities__.items():
            if linked_userid == userid:
                yield key

    def merge_game_data(self, from_userid, into_userid):
        """Fusiona el progreso de from_userid dentro de into_userid al vincular dos
        credenciales de la misma persona. Regla por nodo: si into_userid no tiene
        registro para ese nodo, se copia el de from_userid (con record.userid
        reescrito); si ambos tienen registro, los badges se unen por id
        conservando su awarded_at original, interactions se suma, first_seen/
        last_seen toman el minimo/maximo, y stats/preferences los conserva
        into_userid tal cual (son el unico campo ambiguo: no hay forma correcta
        de sumarlos o elegir uno sin contexto del juego).

        No borra nada: el bucket original de from_userid se deja intacto, solo
        queda inalcanzable por la API. El llamador debe invocar esto una sola
        vez por vinculacion nueva -- no es idempotente (llamarlo dos veces para
        el mismo par sumaria interactions dos veces).
        """
        if from_userid == into_userid:
            return
        if not hasattr(self, "__game_data__"):
            return
        from_bucket = self.__game_data__.get(from_userid)
        if not from_bucket:
            return
        into_bucket = self.__game_data__.get(into_userid)
        if into_bucket is None:
            into_bucket = OOBTree()
            self.__game_data__[into_userid] = into_bucket

        for nodeid, source in from_bucket.items():
            target = into_bucket.get(nodeid)
            if target is None:
                copy = GameData(into_userid, nodeid)
                copy.interactions = source.interactions
                copy.stats.update(source.stats)
                copy.preferences.update(source.preferences)
                for badge in source.badges:
                    clone = PollenBadge(badge.id, badge.title, badge.icon)
                    clone.awarded_at = badge.awarded_at
                    copy.badges.append(clone)
                copy.first_seen = source.first_seen
                copy.last_seen = source.last_seen
                into_bucket[nodeid] = copy
            else:
                existing_ids = {badge.id for badge in target.badges}
                for badge in source.badges:
                    if badge.id not in existing_ids:
                        clone = PollenBadge(badge.id, badge.title, badge.icon)
                        clone.awarded_at = badge.awarded_at
                        target.badges.append(clone)
                target.interactions += source.interactions
                target.first_seen = min(target.first_seen, source.first_seen)
                target.last_seen = max(target.last_seen, source.last_seen)

    # gestión de nodos y aristas
    def add_node(self, node, recurse=False):
        node_id = str(getattr(node, "id", "")) or getattr(node, "__name__", None)
        self.__nodes__[node_id] = node
        self._add_node_edges(node)
        if recurse:
            if hasattr(node, "nodes"):
                for child in node.nodes:
                    self.add_node(child)
            elif isinstance(node, PersistentMapping):
                for child in node.values():
                    self.add_node(child)

    def _add_node_edges(self, node):
        """
        Agrega las conexiones (edges) del nodo al índice global __edges__.
        Si el nodo es un grafo o contenedor, agrega recursivamente las conexiones de sus hijos.
        """
        node_id = str(getattr(node, "id", "")) or getattr(node, "__name__", None)
        # Si el nodo tiene 'edges' (como HoneycombGraph), agrégalas al índice global
        if hasattr(node, "edges") and isinstance(node.edges, (list, PersistentList)):
            if node_id not in self.__edges__:
                self.__edges__[node_id] = PersistentList()
            for edge in node.edges:
                self.__edges__[node_id].append(edge)
        # Si el nodo tiene hijos (por ejemplo, en HoneycombGraph o CellNode), agrega recursivamente
        if hasattr(node, "nodes") and isinstance(node.nodes, (list, PersistentList)):
            for child in node.nodes:
                self._add_node_edges(child)
        if isinstance(node, PersistentMapping):
            for child in node.values():
                self._add_node_edges(child)

    def get_node_by_name(self, name):
        """Obtiene el nodo por su nombre único (__name__)."""
        return self.__nodes__.get(name)

    def remove_node(self, node_id):
        if node_id in self.__nodes__:
            del self.__nodes__[node_id]
        if node_id in self.__edges__:
            del self.__edges__[node_id]

    def add_edge(self, source_id, edge):
        if source_id not in self.__edges__:
            self.__edges__[source_id] = PersistentList()
        # Solo asigna __parent__ si el edge es un objeto con ese atributo
        if hasattr(edge, "__parent__"):
            edge.__parent__ = self
        self.__edges__[source_id].append(edge)

    def remove_node_recursively(self, node_id):
        """
        Elimina el nodo, todos sus hijos y todas las conexiones asociadas (edges) del índice global.
        """
        node = self.__nodes__.get(node_id)
        if not node:
            return

        # Recolecta todos los IDs a eliminar (nodo y descendientes)
        ids_to_remove = set()

        def collect_ids(n):
            nid = str(getattr(n, "id", "")) or getattr(n, "__name__", None)
            ids_to_remove.add(nid)

            # Si el nodo tiene hijos (por ejemplo, en un grafo o contenedor), recorre recursivamente
            if hasattr(n, "nodes") and isinstance(getattr(n, "nodes", None), (list, PersistentList)):
                for child in n.nodes:
                    collect_ids(child)
            if isinstance(n, PersistentMapping):
                for child in n.values():
                    collect_ids(child)

        collect_ids(node)

        # Elimina todos los nodos recolectados del índice global
        for nid in ids_to_remove:
            if nid in self.__nodes__:
                del self.__nodes__[nid]

        # Elimina todas las conexiones donde cualquier nodo recolectado sea fuente
        for nid in ids_to_remove:
            if nid in self.__edges__:
                del self.__edges__[nid]

        # Elimina todas las conexiones donde cualquier nodo recolectado sea destino
        for src, edges in list(self.__edges__.items()):
            new_edges = PersistentList([e for e in edges if (getattr(e, "to_node", None) and ((getattr(e.to_node, '__name__', None) or str(getattr(e.to_node, 'id', ''))) not in ids_to_remove))])
            if new_edges:
                self.__edges__[src] = new_edges
            else:
                del self.__edges__[src]

    def sync_graph_edges(self, graph_node):
        """
        Sincroniza las conexiones (edges) de un HoneycombGraph con el índice global __edges__.
        Elimina las aristas previas del grafo en __edges__ y agrega las actuales.
        """
        node_id = str(getattr(graph_node, "id", "")) or getattr(graph_node, "__name__", None)
        # Elimina las aristas previas del grafo en el índice global
        if node_id in self.__edges__:
            del self.__edges__[node_id]
        # Agrega las aristas actuales del grafo
        if hasattr(graph_node, "edges") and isinstance(graph_node.edges, (list, PersistentList)):
            self.__edges__[node_id] = PersistentList()
            for edge in graph_node.edges:
                self.__edges__[node_id].append(edge)

    def set_name(self, name, title=""):
        self.__name__ = name
        self.title = title

    def set_icon(self, icon):
        self.icon = icon

    def to_dict(self):
        """Exporta el estado actual a JSON usando identificadores únicos."""
        return {
            "name": self.__name__,
            "title": self.title,
            "nodes": [
                {
                    "id": node.__name__,
                    "title": getattr(node, "title", node.__name__),
                    "content": getattr(node, "contents", "")
                } for node in self.__nodes__.values()
            ],
            "edges": [
                {
                    "source": src,
                    "targets": [
                        {
                            "target": getattr(edge, "to_node", None).__name__ if getattr(edge, "to_node", None) else "",
                            "label": getattr(edge, "title", ""),
                            "kind": getattr(edge, "kind", "")
                        } for edge in edges
                    ]
                } for src, edges in self.__edges__.items()
            ]
        }

class Honeycomb(PersistentMapping):
    """A collection of interactive and non-interactive cells. It must have an associated map (either static or dynamic) which will be displayed when the honeycomb is opened."""

    def __init__(self, name, title=""):
        PersistentMapping.__init__(self)
        self.id = str(uuid.uuid4())
        self.__name__ = name
        self.title = title
        self.icon = None
        self.map = None
        self.__featured__ = OOBTree()

    def toggle_featured(self, node):
        if self.__featured__.has_key(node.id.hex):
            del self.__featured__[node.id.hex]
            is_featured = False
        else:
            self.__featured__[node.id.hex] = node
            is_featured = True
        node.is_featured = is_featured
        self._p_changed = True
        return is_featured

    def set_map(self, honeycombmap):
        self.map = honeycombmap

    def get_map(self):
        return self.map

class CellEdge(Persistent):
    def __init__(self, name, title, from_node, to_node, kind="default"):
        self.name = name
        self.title = title
        self.from_node = from_node
        self.to_node = to_node
        self.kind = kind

class HoneycombGraph(PersistentMapping):
    def __init__(self, name="", title="", *args, **kwargs):
        super().__init__()
        self.id = uuid.uuid4()
        self.__name__ = name
        self.title = title
        self.icon = None
        self.nodes = PersistentList()
        self.edges = PersistentList()

    def add_node(self, node):
        self.nodes.append(node)
        # También agregar al mapping para compatibilidad con Honeycomb
        node_name = getattr(node, '__name__', None)
        if node_name:
            self[node_name] = node
        else:
            self[str(node.id)] = node
        self._p_changed = True

    def add_edge(self, edge):
        self.edges.append(edge)
        self._p_changed = True

    def get_node_by_name(self, name):
        for node in self.nodes:
            if getattr(node, '__name__', None) == name:
                return node
        return None

    @classmethod
    def from_json(cls, json_data, name="graph", title="Honeycomb Graph"):
        graph_data = json.loads(json_data)
        # Diccionario para mapear ID de JSON a objeto de nodo de Python
        nodes_map = {}

        graph = cls(name, title)
        builder = CellBuilder()

        # 1. Crear todos los objetos de nodo
        for node_data in graph_data['nodes']:
            json_id = node_data['id']
            node_type = node_data["data"].get("type", None)
            assert node_type in ['custom', None]
            if node_type == "custom":
                node_obj = CellNode(
                    name=node_data['data']['label'].lower().replace(" ", "-"),
                    title = node_data['data']['label'],
                )
            else:
                node_obj = CellLeaf( #ToDo: Graphs can have different kinds of node, this should also be codified in the JSON
                    title=node_data['data']['label'],
                    name=node_data['data']['label'].lower().replace(" ", "-"), #ToDo: Nodes should have a name, if it is not provided, it could be a scrub from the title or label. Use id as name only if there is no other option.
                    #contents=node_data['data']['label']
                )
            assert type(node_obj) is CellNode or not node_type
            node_obj.id = json_id
            node_obj.__parent__ = graph

            node_coordinates = node_data.get("coordinates", None)
            if node_coordinates:
                builder.fill_cell(node_obj, **node_coordinates)

            # Añadir al grafo principal y al mapa temporal
            graph.add_node(node_obj)
            nodes_map[json_id] = node_obj

        # 2. Crear todos los objetos de arista (edge)
        for edge_data in graph_data['edges']:
            source_id = edge_data['source']
            target_id = edge_data['target']
            
            from_node = nodes_map.get(source_id)
            to_node = nodes_map.get(target_id)
            
            if from_node and to_node:
                edge_obj = CellEdge(
                    name=f"edge-{uuid.uuid4()}",
                    title=edge_data.get('label', ''),
                    from_node=from_node,
                    to_node=to_node,
                    kind="default"
                )
                graph.add_edge(edge_obj)

        print(f"DEBUG - Grafo '{graph.title}' generado con {len(graph.nodes)} nodos y {len(graph.edges)} aristas.")

        return graph


    def to_dict(self):
        """
        Genera una representación de diccionario (JSON-friendly) del grafo,
        cumpliendo con la sugerencia de usar IDs para las relaciones.
        """
        nodes_dict = {
            str(node.id): {
                "id": str(node.id),
                "name": getattr(node, '__name__', ''),
                "title": getattr(node, 'title', ''),
                "contents": getattr(node, 'contents', ''),
            } for node in self.nodes
        }

        edges_list = [
            {
                "title": getattr(edge, 'title', ''),
                "from_node_id": str(edge.from_node.id) if hasattr(edge, 'from_node') and hasattr(edge.from_node, 'id') else None,
                "to_node_id": str(edge.to_node.id) if hasattr(edge, 'to_node') and hasattr(edge.to_node, 'id') else None,
                "kind": getattr(edge, 'kind', '')
            } for edge in self.edges
        ]

        return {
            "title": self.title,
            "nodes": nodes_dict,
            "edges": edges_list
        }


class CellLeaf(Persistent):
    """A terminal node in the honeycomb structure, it cannot have children nodes."""
    def __init__(self, name="", parent=None, title=""):
        super().__init__()
        self.__name__ = name
        self.__parent__ = parent
        self.is_featured = False
        self.title = title
        self.icon = None
        # Cada nodo tiene un ID único y persistente
        self.id = uuid.uuid4()


class CellNode(PersistentMapping):
    """A node in the honeycomb structure, it can contain children nodes or be alone, it can also be static or interactive."""
    def __init__(self, name="", parent=None, title=""):
        super().__init__()
        self.__name__ = name
        self.__parent__ = parent
        self.is_featured = False
        self.title = title
        self.icon = None
        # Cada nodo tiene un ID único y persistente
        self.id = uuid.uuid4()

    def set_icon(self, icon):
        self.icon = icon

    def get_icon(self):
        return self.icon


class HoneyStaticMap(CellLeaf):
    """A graphical representation of the Honeycomb structure."""
    def __init__(self, url, filename=None):
        super().__init__(self)
        self.href = url
        self.filename = filename

    def render(self):
        return f'<img src="{self.href}">'

    def update(self, url, filename=None):
        self.href = url
        self.filename = filename

class HoneyDynamicMap(CellLeaf):
    """A complex representation of the Honeycomb structure."""
    def __init__(self, structure):
        super().__init__(self)
        self.structure = structure


class InteractiveCell(CellLeaf):
    """A BeeHive cell containing an interactive element"""
    def __init__(self, name, title=""):
        super().__init__(self)
        self.__name__ = name
        self.title = title
        self.icon = None


class StaticCell(CellLeaf):
    """A BeeHive cell containing static elements"""
    def __init__(self, name, title=""):
        super().__init__(self)
        self.__name__ = name
        self.title = title
        self.icon = None


class CellIcon(CellLeaf):
    """A BeeHive cell icon."""
    def __init__(self, name, title="", icon=None):
        super().__init__(self)
        self.__name__ = name
        self.title = title
        self.icon = icon

    def set_icon(self, icon):
        self.icon = icon

    def get_icon(self):
        return self.icon
    

class CellText(CellLeaf):
    def __init__(self, name, contents, title="", icon=None):
        super().__init__(self)
        self.__name__ = name
        self.title = title
        self.contents = contents
        self.icon = icon
        
        # Propiedades para el editor
        self.position = {}
        self.themeColor = "default"
        self.iconUrl = ""
        self.width = 168
        self.height = 78
        self.node_type = "custom"

    def set_icon(self, icon):
        self.icon = icon

    def get_icon(self):
        return self.icon


class CellRichText(CellLeaf):
    def __init__(self, name, contents, title="", icon=None):
        super().__init__(self)
        self.__name__ = name
        self.title = title
        self.source = contents
        self.icon = icon

    def set_icon(self, icon):
        self.icon = icon

    def get_icon(self):
        return self.icon


class CellAnimation(CellLeaf):
    def __init__(self, name, url, title="", icon=None):
        super().__init__(self)
        self.__name__ = name
        self.href = url
        self.title = title
        self.icon = icon

    def set_icon(self, icon):
        self.icon = icon

    def get_icon(self):
        return self.icon


class CellWebContent(CellLeaf):
    def __init__(self, name, url, title="", icon=None):
        super().__init__(self)
        self.__name__ = name
        self.href = url
        self.title = title
        self.icon = icon

    def set_icon(self, icon):
        self.icon = icon

    def get_icon(self):
        return self.icon


class PollenBadge(Persistent):
    """Un logro otorgado a un usuario para un nodo especifico. `id` lo elige el
    juego (p.ej. 'high-score-100'), no es un UUID generado por el servidor:
    son los juegos los que saben que logros existen."""

    def __init__(self, badge_id, title, icon=None):
        self.id = badge_id
        self.title = title
        self.icon = icon
        self.awarded_at = _utcnow_iso()

    def to_dict(self):
        return {"id": self.id, "title": self.title, "icon": self.icon, "awarded_at": self.awarded_at}


class BeePath:
    def __init__(self, sequence=None, required=None, granted=None):
        self.sequence = PersistentList(sequence if sequence is not None else [])
        self.required = set(required if required is not None else [])
        self.granted = set(granted if granted is not None else [])

