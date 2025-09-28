from zope.interface import Interface, implementer
from persistent import Persistent
from persistent.mapping import PersistentMapping
from BTrees._OOBTree import OOBTree
from persistent.list import PersistentList
import uuid

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

    # gestión de nodos y aristas
    def add_node(self, node):
        node_id = str(getattr(node, "__name__", None) or getattr(node, "id", None))
        node.__parent__ = self
        self.__nodes__[node_id] = node

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

class HoneycombGraph(Honeycomb): 
    def __init__(self, name="", title="", *args, **kwargs):
        super().__init__(name, title)  
        self.nodes = PersistentList()
        self.edges = PersistentList()

    def add_node(self, node):
        self.nodes.append(node)
        # También agregar al mapping para compatibilidad con Honeycomb
        if hasattr(node, '__name__') and node.__name__:
            self[node.__name__] = node
        self._p_changed = True

    def add_edge(self, edge):
        self.edges.append(edge)
        self._p_changed = True

    def get_node_by_name(self, name):
        for node in self.nodes:
            if getattr(node, '__name__', None) == name:
                return node
        return None

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


class CellNode(Persistent):
    """A node in the honeycomb structure, it can contain children nodes or be alone, it can also be static or interactive."""
    def __init__(self, name="", parent=None):
        super().__init__()
        self.__name__ = name
        self.__parent__ = parent
        self.title = ""
        self.icon = None
        # Cada nodo tiene un ID único y persistente
        self.id = uuid.uuid4()

    def set_icon(self, icon):
        self.icon = icon

    def get_icon(self):
        return self.icon


class HoneyStaticMap(CellNode):
    """A graphical representation of the Honeycomb structure."""
    def __init__(self, url, filename=None):
        CellNode.__init__(self)
        self.href = url
        self.filename = filename

    def render(self):
        return f'<img src="{self.href}">'

    def update(self, url, filename=None):
        self.href = url
        self.filename = filename

class HoneyDynamicMap(CellNode):
    """A complex representation of the Honeycomb structure."""
    def __init__(self, structure):
        CellNode.__init__(self)
        self.structure = structure


class InteractiveCell(CellNode):
    """A BeeHive cell containing an interactive element"""
    def __init__(self, name, title=""):
        CellNode.__init__(self)
        self.__name__ = name
        self.title = title
        self.icon = None


class StaticCell(CellNode):
    """A BeeHive cell containing static elements"""
    def __init__(self, name, title=""):
        CellNode.__init__(self)
        self.__name__ = name
        self.title = title
        self.icon = None


class CellIcon(CellNode):
    """A BeeHive cell icon."""
    def __init__(self, name, title="", icon=None):
        CellNode.__init__(self)
        self.__name__ = name
        self.title = title
        self.icon = icon

    def set_icon(self, icon):
        self.icon = icon

    def get_icon(self):
        return self.icon
    

class CellText(CellNode):
    def __init__(self, name, contents, title="", icon=None):
        CellNode.__init__(self)
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


class CellRichText(CellNode):
    def __init__(self, name, contents, title="", icon=None):
        CellNode.__init__(self)
        self.__name__ = name
        self.title = title
        self.source = contents
        self.icon = icon

    def set_icon(self, icon):
        self.icon = icon

    def get_icon(self):
        return self.icon


class CellAnimation(CellNode):
    def __init__(self, name, url, title="", icon=None):
        CellNode.__init__(self)
        self.__name__ = name
        self.href = url
        self.title = title
        self.icon = icon

    def set_icon(self, icon):
        self.icon = icon

    def get_icon(self):
        return self.icon


class CellWebContent(CellNode):
    def __init__(self, name, url, title="", icon=None):
        CellNode.__init__(self)
        self.__name__ = name
        self.href = url
        self.title = title
        self.icon = icon

    def set_icon(self, icon):
        self.icon = icon

    def get_icon(self):
        return self.icon