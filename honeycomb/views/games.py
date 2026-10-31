"""Vistas de los juegos.

Siguen la convencion de default.py: GET con `renderer='json'` sobre la celda, POST de
creacion con `name` en espanol y PUT en `admin`. El DELETE de un juego ya lo cubre
admin_delete_node, que es generico sobre CellLeaf. Los cuerpos van en JSON y las
llaves en ingles, las mismas que devuelve to_dict().

Leer un juego y mandar la prueba de un reto es publico. Crear o cambiar el catalogo
pide sesion. Toda peticion que modifica datos pide el token CSRF.
"""

from persistent.mapping import PersistentMapping
from pyramid import traversal
from pyramid.view import view_config
from slugify import slugify

from ..models.beehive import Honeycomb
from ..models.games import GAME_TYPES, Badge, Challenge, GameCell


def _error(request, status, message):
    request.response.status_int = status
    return {'error': message}


def _json_object(request):
    try:
        data = request.json_body
    except ValueError:
        raise ValueError('El cuerpo debe ser JSON valido') from None
    if not isinstance(data, dict):
        raise ValueError('El cuerpo debe ser un objeto JSON')
    return data


def _field(data, key, kind, label, default):
    """Un campo del tipo pedido. Un null cuenta como ausente."""
    value = data.get(key)
    if value is None:
        return default
    if not isinstance(value, kind):
        raise ValueError(f"El campo '{key}' debe ser {label}")
    return value


def _text(data, key, default=''):
    return _field(data, key, str, 'texto', default)


def _object(data, key):
    return _field(data, key, dict, 'un objeto', None)


def _list(data, key):
    return _field(data, key, list, 'una lista', None)


def _required(data, key):
    if data.get(key) is None:
        raise ValueError(f"Falta el campo obligatorio: '{key}'")
    return data[key]


def _required_text(data, key):
    value = _text(data, key, default=None)
    if value is None or not value.strip():
        raise ValueError(f"Falta el campo obligatorio: '{key}'")
    return value


def _badge(item):
    if not isinstance(item, dict):
        raise ValueError('Cada insignia debe ser un objeto')
    return Badge(name=_required_text(item, 'name'), title=_required_text(item, 'title'),
                 icon=_text(item, 'icon', default=None),
                 description=_text(item, 'description'))


def _game_json(request, game):
    return {
        **game.to_dict(),
        'url': request.resource_url(game),
        'proof_url': request.resource_url(game, '@@prueba'),
    }


@view_config(context=GameCell, renderer='json', request_method="GET")
def game_view(context, request):
    """Obtener el juego con sus retos, sin las respuestas"""
    return _game_json(request, context)


#Crear
@view_config(context=Honeycomb, name="juego", permission='read', renderer='json', request_method="POST", require_csrf=True)
def game_create_view(context, request):
    """Juego"""
    try:
        data = _json_object(request)
        type_name = _required_text(data, 'type')
        if type_name not in GAME_TYPES:
            raise ValueError(f"type desconocido: {type_name!r}. Opciones: {', '.join(GAME_TYPES)}")
        title = _required_text(data, 'title')
        name = slugify(_text(data, 'name') or title)
        if not name:
            raise ValueError('No se pudo formar un name valido')
        game = GAME_TYPES[type_name](
            name=name, kind=_required_text(data, 'kind'), title=title,
            description=_text(data, 'description'),
            params=_object(data, 'params'), assets=_object(data, 'assets'))
        parent_id = _text(data, 'parent', default=None)
    except ValueError as e:
        return _error(request, 400, str(e))

    beehive = traversal.find_root(context)
    parent = context if parent_id is None else beehive.__nodes__.get(parent_id)
    if parent is None:
        return _error(request, 404, f"No existe el parent '{parent_id}'")
    if not isinstance(parent, PersistentMapping):
        return _error(request, 400, 'El parent no puede contener nodos')
    if name in parent:
        return _error(request, 409, f"Ya existe un nodo llamado '{name}'")

    game.__parent__ = parent
    parent[name] = game
    beehive.add_node(game)

    request.response.status_int = 201
    return {'status': 'creado', **_game_json(request, game)}


@view_config(context=GameCell, name="reto", permission='read', renderer='json', request_method="POST", require_csrf=True)
def challenge_create_view(context, request):
    """Reto"""
    try:
        data = _json_object(request)
        title = _required_text(data, 'title')
        challenge = Challenge(
            name=slugify(_text(data, 'name') or title), title=title,
            badges=[_badge(item) for item in _list(data, 'badges') or []],
            description=_text(data, 'description'),
            interaction=_text(data, 'interaction', default=None),
            cardinality=_text(data, 'cardinality', default=None),
            prompt=_text(data, 'prompt'),
            choices=_list(data, 'choices'),
            correct_response=data.get('correct_response'),
            assets=_object(data, 'assets'))
    except ValueError as e:
        return _error(request, 400, str(e))

    context.add_challenge(challenge)

    request.response.status_int = 201
    return {'status': 'creado', **challenge.to_dict()}


@view_config(context=GameCell, name="prueba", renderer='json', request_method="POST", require_csrf=True)
def proof_view(context, request):
    """Revisar la prueba de un reto, sin guardar nada ni dar la respuesta"""
    try:
        data = _json_object(request)
        challenge_id = _required(data, 'challenge_id')
        proof = _required(data, 'proof')
    except ValueError as e:
        return _error(request, 400, str(e))

    challenge = context.get_challenge(challenge_id)
    if challenge is None:
        return _error(request, 404, 'El reto no existe en este juego')
    if not challenge.is_verifiable():
        return _error(request, 400, 'Este reto no se verifica en el servidor')

    return {
        'challenge_id': challenge.id,
        'correct': challenge.is_correct(proof),
        'badges': [badge.to_dict() for badge in challenge.check_proof(proof)],
    }


#Actualizar
@view_config(context=GameCell, name='admin', permission='read', renderer='json', request_method='PUT', require_csrf=True)
def admin_update_game(context, request):
    """Actualizar juego"""
    try:
        data = _json_object(request)
        context.update(
            title=_text(data, 'title', default=None),
            description=_text(data, 'description', default=None),
            kind=_text(data, 'kind', default=None),
            params=_object(data, 'params'),
            assets=_object(data, 'assets'))
    except ValueError as e:
        return _error(request, 400, str(e))

    return {'status': 'actualizado', 'id': str(context.id)}
