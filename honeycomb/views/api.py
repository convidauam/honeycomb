import uuid
import math
from cornice.resource import resource
from pyramid import traversal
from ..models import *
from ..security import activitypub, fediverse, ratelimit, tokenstore
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


def _identity_to_dict(identity_key):
    """'fediverse:<actor_url>' / 'password:<username>' -> {'kind', 'value'};
    partition corta solo en el primer ':', asi que una URL de actor con sus
    propios ':' (https://...) se conserva entera en value."""
    kind, _, value = identity_key.partition(':')
    return {'kind': kind, 'value': value}


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
        root = traversal.find_root(resource=self.context)
        identities = [_identity_to_dict(key) for key in root.iter_identities(user.userid)]
        return {
            'userid': user.userid,
            'displayname': user.display_name,
            'username': user.username,
            'icon': user.icon,
            'background': user.background,
            # Credenciales vinculadas a esta cuenta (Fediverso y/o contrasena) y
            # si hay lo necesario para publicar logros al Fediverso ahora mismo.
            'identities': identities,
            'can_share': user.can_share(),
        }


def _max_game_payload_keys(settings):
    """Vacio/ausente/<=0 = sin limite; lo activa quien administra la instancia
    poniendo un entero positivo en honeycomb.max_game_payload_keys."""
    return ratelimit.limit_setting_or_none(settings, 'honeycomb.max_game_payload_keys')


def _validate_game_payload(mapping, field_name, max_keys):
    if not isinstance(mapping, dict):
        return f"'{field_name}' must be an object"
    if max_keys is not None and len(mapping) > max_keys:
        return f"'{field_name}' has too many keys (max {max_keys})"
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

        max_keys = _max_game_payload_keys(self.request.registry.settings)
        error = _validate_game_payload(stats, 'stats', max_keys) or _validate_game_payload(preferences, 'preferences', max_keys)
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


@resource(path='/api/v1/sipping/{nodeid}/badges', cors_origins=('*',), factory='honeycomb.root_factory', require_csrf=False)
class GameBadgeResource:
    """Otorga logros (badges) al usuario autenticado para un nodo. Solo escritura
    controlada por el juego que llama; el cliente del juego decide que logro
    otorgar y con que datos, igual que con `stats`."""

    def __init__(self, request, context=None):
        self.request = request
        self.context = context

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
            return {'error': 'Request body must be a JSON object'}

        badge_id = payload.get('id')
        title = payload.get('title')
        icon = payload.get('icon')
        if not badge_id or not isinstance(badge_id, str):
            self.request.response.status = 400
            return {'error': "'id' is required and must be a string"}
        if not title or not isinstance(title, str):
            self.request.response.status = 400
            return {'error': "'title' is required and must be a string"}
        if icon is not None and not isinstance(icon, str):
            self.request.response.status = 400
            return {'error': "'icon' must be a string"}

        root = traversal.find_root(resource=self.context)
        record = root.get_game_data(user.userid, nodeid, create=True)
        record.award_badge(badge_id, title, icon)
        return record.to_dict()


@resource(path='/api/v1/achievements', cors_origins=('*',), factory='honeycomb.root_factory')
class AchievementsResource:
    """Todos los logros del usuario autenticado, en cualquier nodo (su vitrina)."""

    def __init__(self, request, context=None):
        self.request = request
        self.context = context

    def get(self):
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Unauthorized'}

        root = traversal.find_root(resource=self.context)
        achievements = []
        for nodeid, badge in root.iter_user_badges(user.userid):
            entry = badge.to_dict()
            entry['nodeid'] = nodeid
            achievements.append(entry)
        return {'achievements': achievements}


@resource(path='/api/v1/share', cors_origins=('*',), factory='honeycomb.root_factory', require_csrf=False)
class ShareResource:
    """Publica un logro ya otorgado como una nota en el Fediverso, a nombre del
    usuario autenticado (via ActivityPub C2S, su propio outbox). Dos formas de
    fallar que se distinguen en el mensaje: la cuenta nunca vinculo un
    Fediverso (invita a vincularlo desde /cuenta), o si vinculo pero no hay
    token utilizable -- honeycomb.token_encryption_key no esta configurada, o
    hay que volver a iniciar sesion para refrescarlo."""

    def __init__(self, request, context=None):
        self.request = request
        self.context = context

    def post(self):
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Unauthorized'}

        try:
            payload = self.request.json_body
        except Exception:
            self.request.response.status = 400
            return {'error': 'Invalid JSON'}
        if not isinstance(payload, dict):
            self.request.response.status = 400
            return {'error': 'Request body must be a JSON object'}

        nodeid = payload.get('nodeid')
        badge_id = payload.get('badge_id')
        if not nodeid or not badge_id:
            self.request.response.status = 400
            return {'error': "'nodeid' and 'badge_id' are required"}

        root = traversal.find_root(resource=self.context)
        record = root.get_game_data(user.userid, nodeid, create=False)
        badge = next((b for b in (record.badges if record else []) if b.id == badge_id), None)
        if badge is None:
            self.request.response.status = 404
            return {'error': 'Badge not found for this user/node'}

        if not user.has_fediverse_identity():
            self.request.response.status = 400
            return {'error': 'Tu cuenta no tiene una identidad del Fediverso vinculada; vinculala desde /cuenta'}

        settings = self.request.registry.settings
        try:
            access_token = tokenstore.decrypt_token(settings, user.access_token_encrypted)
        except tokenstore.TokenStoreError as exc:
            self.request.response.status = 400
            return {'error': str(exc)}
        if not access_token:
            self.request.response.status = 400
            return {'error': 'No hay un token de publicacion disponible; vuelve a iniciar sesion'}

        message = payload.get('message') or f'Consegui el logro "{badge.title}" en Convida!'
        try:
            activity = activitypub.publish_note(user.outbox, access_token, message)
        except fediverse.FediverseError as exc:
            self.request.response.status = 502
            return {'error': str(exc)}

        return {'status': 'ok', 'activity': activity}
