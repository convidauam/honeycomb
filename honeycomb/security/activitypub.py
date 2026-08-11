"""Publicacion y lectura via ActivityPub C2S (cliente-servidor), sobre el
outbox del propio usuario. No implementa federacion S2S (firmas HTTP, entrega
a otros servidores): eso lo hace la instancia del usuario al recibir el POST,
igual que si el usuario hubiera publicado desde su propio cliente.
"""

import requests

from .fediverse import FediverseError, _safe_request

AS2_CONTEXT = 'https://www.w3.org/ns/activitystreams'
C2S_CONTENT_TYPE = 'application/ld+json; profile="https://www.w3.org/ns/activitystreams"'


def publish_note(outbox_url, access_token, content, to_public=True):
    """POST un objeto Note al outbox del usuario, autenticado con su propio
    access_token (Bearer) -- asi es como Mastodon/Pleroma reconocen que el
    dueno del outbox autorizo la publicacion. El servidor la envuelve en una
    actividad Create y le asigna id; no inventamos IDs propios (el spec no
    lo permite para actividades generadas por el servidor)."""
    if not outbox_url:
        raise FediverseError('El usuario no tiene un outbox de ActivityPub conocido')
    if not access_token:
        raise FediverseError('No hay un token de acceso disponible para publicar')
    note = {
        '@context': AS2_CONTEXT,
        'type': 'Note',
        'content': content,
    }
    if to_public:
        note['to'] = ['https://www.w3.org/ns/activitystreams#Public']
    try:
        response = _safe_request(
            'POST', outbox_url, json=note,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': C2S_CONTENT_TYPE,
                'Accept': C2S_CONTENT_TYPE,
            },
        )
    except requests.RequestException as exc:
        raise FediverseError('No se pudo publicar en el Fediverso') from exc
    if response.status_code >= 400:
        raise FediverseError(f'La instancia rechazo la publicacion (HTTP {response.status_code})')
    try:
        return response.json()
    except ValueError:
        return {}


def read_outbox(outbox_url, access_token=None):
    """GET el outbox del usuario. Si es una OrderedCollection resumen (sin
    items directos), sigue la pagina `first`."""
    if not outbox_url:
        raise FediverseError('El usuario no tiene un outbox de ActivityPub conocido')
    headers = {'Accept': C2S_CONTENT_TYPE}
    if access_token:
        headers['Authorization'] = f'Bearer {access_token}'

    collection = _get_json_or_raise(outbox_url, headers, 'No se pudo leer el outbox')
    if 'orderedItems' in collection or 'items' in collection:
        return collection

    first = collection.get('first')
    first_url = first if isinstance(first, str) else (first or {}).get('id')
    if not first_url:
        return collection
    return _get_json_or_raise(first_url, headers, 'No se pudo leer la pagina del outbox')


def _get_json_or_raise(url, headers, error_message):
    try:
        response = _safe_request('GET', url, headers=headers)
    except requests.RequestException as exc:
        raise FediverseError(error_message) from exc
    if response.status_code >= 400:
        raise FediverseError(f'{error_message} (HTTP {response.status_code})')
    return response.json()
