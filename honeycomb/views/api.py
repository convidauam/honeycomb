import uuid
import math
from cornice.resource import resource
from pyramid import traversal
from ..models import *
import logging

log = logging.getLogger(__name__)


@resource(collection_path='/api/v1/honeycombs', path='/api/v1/honeycombs/{name}', cors_origins=('*',), factory='honeycomb.root_factory')
class HoneycombResource:
    def __init__(self, request, context=None):
        self.request = request
        self.context = context

    def collection_get(self):
        """Get the list of honeycombs"""
        honeycombs = []
        root = traversal.find_root(resource=self.context)
        for hc in self.request.root.values():
            honeycombs.append({
                'id': hc.__name__,
                'title': hc.title,
                'icon': hc.icon,
            })
        return {'honeycombs': honeycombs}

    def get(self):
        """Get a honeycomb's children nodes by name"""
        hc = self.request.root[self.request.matchdict['name']]
        if not hc:
            self.request.response.status = 404
            return {'error': 'Honeycomb with that name was not found'}

        # Nodo raíz (el Honeycomb mismo)
        hc_node = {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, self.request.resource_url(hc))),
            "data": {
                "label": hc.title,
                "themeColor": "root",
                "url": self.request.resource_url(hc),
                "icon": hc.icon,
            },
            "position": {"x": 0, "y": 0},  # en el centro
            "type": "custom",
            "width": 200,
            "height": 80,
        }

        # Nodos hijos distribuidos en círculo
        cells = hc.values()
        n = len(cells)
        radius = 300
        child_nodes = []
        for i, cell in enumerate(cells):
            angle = 2 * math.pi * i / n if n > 0 else 0
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)

            child_nodes.append({
                "id": str(cell.id),
                "data": {
                    "label": cell.title,
                    "themeColor": "default",
                    "url": self.request.resource_url(cell),
                    "icon": getattr(cell, 'icon', None),
                },
                "position": {"x": x, "y": y},
                "type": "custom",
                "width": 152,
                "height": 58,
            })

        # Edges: del root hacia cada hijo
        edges = [
            {
                "id": f"edge-{hc_node['id'].replace("-", "")}-{child['id'].replace("-", "")}",
                "source": hc_node["id"],
                "target": child["id"],
                "type": "custom-label",
            }
            for child in child_nodes
        ]

        return {
            "id": hc_node["id"],
            "title": hc.title,
            "nodes": [hc_node] + child_nodes,
            "edges": edges,
        }

@resource(path='/api/v1/node/{node_id}', cors_origins=('*',), factory='honeycomb.root_factory')
class NodeResource:
    def __init__(self, request, context=None):
        self.request = request
        self.context = context

    def get(self):
        root = traversal.find_root(resource=self.context)
        log.debug("Nodos en índice: %s", list(root.__nodes__.keys()))
        if not hasattr(root, "__nodes__"):
            root.__nodes__ = OOBTree()
        if not hasattr(root, "__edges__"):
            root.__edges__ = OOBTree()

        node_id = self.request.matchdict['node_id']
        node = root.__nodes__.get(node_id)

        if node is None:
            self.request.response.status = 404
            return {'error': 'Node not found'}

        data = {
            "id": str(node.id),
            "label": getattr(node, "title", ""),
            "contents": getattr(node, "contents", ""),
            "url": self.request.resource_url(node),
            "iconUrl": getattr(node, "icon", None),
            "nodes": [],
            "edges": [],
        }


        if hasattr(node, "nodes") and hasattr(node, "edges"):
            data["nodes"] = [{'id': str(child.id), 'label': getattr(child, 'title', ''), 'url': self.request.resource_url(child)} for child in node.nodes]
            data["edges"] = [{'source': str(edge.from_node.id), 'target': str(edge.to_node.id), 'id': getattr(edge, 'id', uuid.uuid4().hex), 'label': edge.title, 'type': "custom-label", 'data': {'hasArrow': False}} for edge in node.edges]

        elif hasattr(node, "values"):
            for child in node.values():
                data["nodes"].append({
                    "id": str(child.id),
                    "label": getattr(child, "title", ""),
                    "url": self.request.resource_url(child),
                    "iconUrl": getattr(child, "icon", None),
                })

            edges = root.__edges__.get(node_id, [])
            data["edges"] = [edge for edge in edges]
            
        return data
