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

        # Featured: nodos resaltados en la vista de catálogo
        featured = []

        for cell in hc.__featured__.values():
            featured.append({
                "id": cell.id.hex,
                "data": {
                    "label": cell.title,
                    "themeColor": "default",
                    "url": self.request.resource_url(cell),
                    "icon": cell.icon,
                },
            })

        return {
            "id": hc_node["id"],
            "title": hc.title,
            "nodes": [hc_node] + child_nodes,
            "edges": edges,
            "featured": featured,
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
            "featured": [],
            "type": None,
            "href": None,
            "src": None,
        }

        if isinstance(node, CellNode):
            data["type"] = "node"
        elif isinstance(node, CellLeaf):
            data["type"] = "leaf"
            if isinstance(node, CellWebContent):
                data["type"] = "webcontent"
                data["href"] = node.href
        else:
            data["type"] = "custom"

        if hasattr(node, "nodes") and hasattr(node, "edges"):
            for child in node.nodes:
                if hasattr(child, "__axes__"):
                    position = dict(zip(('x', 'y', 'z'), child.__axes__))
                else:
                    position = dict(zip(('x', 'y'), (0,0)))

                data["nodes"].append({
                    'id': str(child.id),
                    'data': {'label': getattr(child, 'title', '')},
                    'label': getattr(child, 'title', ''),
                    'url': self.request.resource_url(child),
                    'position': position,
                })
            # data["nodes"] = [{'id': str(child.id), 'label': getattr(child, 'title', ''), 'url': self.request.resource_url(child)} for child in node.nodes]
            data["edges"] = [{'source': str(edge.from_node.id), 'target': str(edge.to_node.id), 'id': getattr(edge, 'id', uuid.uuid4().hex), 'label': edge.title, 'type': "custom-label", 'data': {'hasArrow': False}} for edge in node.edges]

        elif hasattr(node, "values"):
            for child in node.values():
                if hasattr(child, "__axes__"):
                    position = dict(zip(('x', 'y', 'z'), child.__axes__))
                else:
                    position = dict(zip(('x', 'y'), (0,0)))

                data["nodes"].append({
                    "id": str(child.id),
                    "data": {"label": getattr(child, "title", "")},
                    "label": getattr(child, "title", ""),
                    "url": self.request.resource_url(child),
                    "iconUrl": getattr(child, "icon", None),
                    "position": position,
                })

                if child.is_featured:
                    data["featured"].append(child.id.hex)

            edges = root.__edges__.get(node_id, [])
            data["edges"] = [edge for edge in edges]
            
        return data
    
@resource(path='/api/v1/drones/{userid}', cors_origins=('*',), factory='honeycomb.root_factory')
class DroneResource:
    def __init__(self, request, context=None):
        self.request = request
        self.context = context

    def get(self):
        user = getattr(self.request, 'identity', None)
        url_userid = self.request.matchdict.get('userid')
        if not user:
            self.request.response.status = 401
            return {'error': 'Unauthorized'}
        if url_userid != user.userid:
            self.request.response.status = 403
            return {'error': 'Forbidden: userid mismatch'}
        return {
            'userid': user.userid,
            'displayname': user.display_name,
            'username': user.username,
            'icon': user.icon,
            'background': user.background,
        }
    
@resource(path='/api/v1/userid', cors_origins=('*',), factory='honeycomb.root_factory')
class UserIDResource:
    def __init__(self, request, context=None):
        self.request = request
        self.context = context

    def get(self):
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Unauthorized'}
        return {
            'userid': getattr(user, 'userid'),
        }


@resource(path='/api/v1/me', cors_origins=('*',), factory='honeycomb.root_factory')
class MeResource:
    """Datos de solo lectura del usuario autenticado. Contrato homologado (a)."""

    def __init__(self, request, context=None):
        self.request = request
        self.context = context

    def get(self):
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Unauthorized'}
        return {
            'userid': user.userid,
            'displayname': user.display_name,
            'username': user.username,
            'icon': user.icon,
            'background': user.background,
        }


MAX_GAME_PAYLOAD_KEYS = 100


def _validate_game_payload(mapping, field_name):
    if not isinstance(mapping, dict):
        return f"'{field_name}' must be an object"
    if len(mapping) > MAX_GAME_PAYLOAD_KEYS:
        return f"'{field_name}' has too many keys (max {MAX_GAME_PAYLOAD_KEYS})"
    return None


@resource(path='/api/v1/sipping/{nodeid}', cors_origins=('*',), factory='honeycomb.root_factory', require_csrf=False)
class GameDataResource:
    """Datos homologados de un videojuego para el usuario autenticado y un nodo (b). Ruta documentada: sipping."""

    def __init__(self, request, context=None):
        self.request = request
        self.context = context

    def get(self):
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Unauthorized'}

        nodeid = self.request.matchdict['nodeid']
        root = traversal.find_root(resource=self.context)
        record = root.get_game_data(user.userid, nodeid, create=False)
        if record is None:
            return GameData(user.userid, nodeid).to_dict()
        return record.to_dict()

    def post(self):
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Unauthorized'}

        nodeid = self.request.matchdict['nodeid']
        try:
            payload = self.request.json_body
        except Exception:
            self.request.response.status = 400
            return {'error': 'Invalid JSON'}
        if not isinstance(payload, dict):
            self.request.response.status = 400
            return {'error': "Request body must be a JSON object"}

        stats = payload.get('stats', {})
        preferences = payload.get('preferences', {})
        replace = bool(payload.get('replace', False))

        error = _validate_game_payload(stats, 'stats') or _validate_game_payload(preferences, 'preferences')
        if error:
            self.request.response.status = 400
            return {'error': error}

        root = traversal.find_root(resource=self.context)
        record = root.get_game_data(user.userid, nodeid, create=True)
        # interactions y badges no se aceptan del cliente: los controla el servidor
        record.merge_stats(stats, replace=replace)
        record.merge_preferences(preferences, replace=replace)
        record.register_interaction()
        return record.to_dict()
