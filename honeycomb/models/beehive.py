from persistent import Persistent
from persistent.mapping import PersistentMapping
from persistent.list import PersistentList
import uuid

class BeeHive(PersistentMapping):
    __name__ = None
    __parent__ = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = "BeeHive Root"

    def set_name(self, name, title=""):
        self.__name__ = name
        self.title = title

    def set_icon(self, icon):
        self.icon = icon

class Honeycomb(PersistentMapping):
    def __init__(self, name, title=""):
        super().__init__()
        self.__name__ = name
        self.title = title
        self.icon = None
        self.map = None

    def set_map(self, honeycombmap):
        self.map = honeycombmap

    def get_map(self):
        return self.map

class HoneycombGraph(PersistentMapping):
    def __init__(self, name="", title="", parent=None):
        super().__init__()
        self.__name__ = name
        self.__parent__ = parent
        self.name = name
        self.title = title
        self.collapsed = False
        self.nodes = PersistentList()
        self.edges = PersistentList()

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.nodes[key]
        for node in self.nodes:
            if node.__name__ == key:
                return node
        raise KeyError(key)

    def get_node_by_name(self, name):
        for node in self.nodes:
            if node.__name__ == name:
                return node
        return None

    def add_node(self, node):
        existing_names = {n.__name__ for n in self.nodes}
        if node.__name__ not in existing_names:
            node.__parent__ = self
            node.__name__ = node.__name__ or node.name
            self.nodes.append(node)

    def del_node(self, node):
        self.nodes.remove(node)

    def add_edge(self, edge):
        node_names = {n.__name__ for n in self.nodes}
        if edge.from_node.__name__ in node_names and edge.to_node.__name__ in node_names:
            edge.__parent__ = self
            self.edges.append(edge)

    def del_edge(self, edge):
        self.edges.remove(edge)

    def to_dict(self):
        return {
            "name": self.name,
            "title": self.title,
            "nodes": [n.to_dict() for n in self.nodes if hasattr(n, 'to_dict')],
            "edges": [e.to_dict() for e in self.edges if hasattr(e, 'to_dict')]
        }

    def validate(self):
        node_names = {n.__name__ for n in self.nodes}
        return [e for e in self.edges if e.from_node.__name__ not in node_names or e.to_node.__name__ not in node_names]

class CellNode(PersistentMapping):
    def __init__(self, name="", parent=None):
        super().__init__()
        self.__name__ = name
        self.__parent__ = parent
        self.title = ""
        self.icon = None
        self.id = uuid.uuid4()

    def set_icon(self, icon):
        self.icon = icon

    def get_icon(self):
        return self.icon

class HoneyStaticMap(CellNode):
    def __init__(self, url, filename=None):
        super().__init__()
        self.href = url
        self.filename = filename

    def render(self):
        return f'<img src="{self.href}">'

    def update(self, url, filename=None):
        self.href = url
        self.filename = filename

class HoneyDynamicMap(CellNode):
    def __init__(self, structure):
        super().__init__()
        self.structure = structure

class CellEdge(Persistent):
    def __init__(self, name, title="", from_node=None, to_node=None, kind=""):
        self.name = name
        self.title = title
        self.__parent__ = None
        self.from_node = from_node
        self.to_node = to_node
        self.kind = kind

    def to_dict(self):
        return {
            "source": self.from_node.__name__,
            "target": self.to_node.__name__,
            "label": self.title,
            "kind": self.kind
        }

class InteractiveCell(CellNode):
    def __init__(self, name, title=""):
        super().__init__()
        self.__name__ = name
        self.title = title

class StaticCell(CellNode):
    def __init__(self, name, title=""):
        super().__init__()
        self.__name__ = name
        self.title = title

class CellIcon(CellNode):
    def __init__(self, name, title="", icon=None):
        super().__init__()
        self.__name__ = name
        self.title = title
        self.icon = icon

    def to_dict(self):
        return {
            "id": self.__name__,
            "title": self.title,
            "icon": self.icon
        }

class CellText(CellNode):
    def __init__(self, name, contents, title="", icon=None):
        super().__init__()
        self.__name__ = name
        self.title = title
        self.contents = contents
        self.icon = icon

    def to_dict(self):
        return {
            "id": self.__name__,
            "title": self.title,
            "content": self.contents
        }

class CellRichText(CellNode):
    def __init__(self, name, contents, title="", icon=None):
        super().__init__()
        self.__name__ = name
        self.title = title
        self.source = contents
        self.icon = icon

class CellAnimation(CellNode):
    def __init__(self, name, url, title="", icon=None):
        super().__init__()
        self.__name__ = name
        self.href = url
        self.title = title
        self.icon = icon

    def to_dict(self):
        return {
            "id": self.__name__,
            "title": self.title,
            "href": self.href,
            "icon": self.icon
        }

class CellWebContent(CellNode):
    def __init__(self, name, url, title="", icon=None):
        super().__init__()
        self.__name__ = name
        self.href = url
        self.title = title
        self.icon = icon

    def to_dict(self):
        return {
            "id": self.__name__,
            "title": self.title,
            "href": self.href,
            "icon": self.icon
        }
