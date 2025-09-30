from zope.interface import Interface, implementer
from persistent import Persistent
from persistent.mapping import PersistentMapping
from BTrees._OOBTree import OOBTree
from persistent.list import PersistentList
import json, uuid

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
        node_id = str(getattr(node, "id", "")) or getattr(node, "__name__", None)
        #node.__parent__ = self
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

class HoneycombGraph(PersistentMapping):
    def __init__(self, name="", title="", *args, **kwargs):
        super().__init__()
        self.id = uuid.uuid4()
        self.__name__ = name
        self.title = title
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
    def from_json(self, json_data, name="graph", title="Honeycomb Graph"):
        graph_data = json.loads(json_data)
        # Diccionario para mapear ID de JSON a objeto de nodo de Python
        nodes_map = {}

        graph = HoneycombGraph(name, title)

        # 1. Crear todos los objetos de nodo
        for node_data in graph_data['nodes']:
            json_id = node_data['id']
            node_type = node_data.get("type", None)
            assert node_type in ['custom', None]
            if node_type == "custom":
                node_obj = CellNode(
                    name=node_data['data']['label'].lower().replace(" ", "-"),
                    title = node_data['data']['label'],
                )
            elif node_type == None:
                node_obj = CellText( #ToDo: Graphs can have different kinds of node, this should also be codified in the JSON
                    title=node_data['data']['label'],
                    name=node_data['data']['label'].lower().replace(" ", "-"), #ToDo: Nodes should have a name, if it is not provided, it could be a scrub from the title or label. Use id as name only if there is no other option.
                    contents=node_data['data']['label']
                )
            node_obj.id = json_id
            node_obj.__parent__ = graph

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
