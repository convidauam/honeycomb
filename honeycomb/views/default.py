from pyramid.view import view_config
from pyramid.httpexceptions import HTTPSeeOther, HTTPFound
from pyramid_storage.exceptions import FileNotAllowed
from pyramid_storage import extensions

from ..models import *


@view_config(context=BeeHive, renderer='templates/beehive.jinja2')
def beehive_view(context, request):
    honeycombs = []
    for name, hc in context.items():
        hc_url = request.resource_url(hc)
        cells = [(cell, request.resource_url(cell)) for cell in hc.values()]
        honeycombs.append((hc, hc_url, cells))
    return {
        'project': 'BeeHive Project',
        'title': context.__name__,
        'honeycombs': honeycombs,
        'request': request,      
    }


@view_config(context=Honeycomb, renderer='honeycomb:templates/honeycomb.jinja2')
def honeycomb(request):
    if hasattr(request.context, 'title'):
        honeycomb_title = request.context.title
    else:
        honeycomb_title = "Wild honeycomb"
    if hasattr(request.context, 'map'):
        map = request.context.map
    else:
        map = None
    cells = [(request.context[cell], request.resource_url(request.context, cell)) for cell in request.context]
    return {'project': 'Honeycomb', 'title': honeycomb_title, 'map': map, 'cells': cells}


@view_config(context=Honeycomb, request_method='POST')
def honeycomb_update(request):
    filename = None
    try:
        filename = request.storage.save(request.POST['honeycomb_map'], folder="maps", randomize=True, extensions=extensions.DATA+extensions.IMAGES)
    except FileNotAllowed:
        request.session.flash('Sorry, this file is not allowed')
    if filename:
        prev_filename = request.context.map and request.context.map.filename
        request.context.set_map(HoneyStaticMap(request.storage.url(filename)))
        if prev_filename:
            request.storage.delete(prev_filename)
    return HTTPSeeOther(request.resource_url(request.context))

@view_config(context=CellText, renderer='honeycomb:templates/cell.jinja2')
def textcell(request):
    if hasattr(request.context, 'title'):
        cell_title = request.context.title
    else:
        cell_title = "Wild cell"
    return {'project': 'Honeycomb', 'title': cell_title, 'contents': request.context.contents}

@view_config(context=CellText, name='CreateNew', renderer='templates/view_cell_text.jinja2')
def view_cell_text(context, request):
    return {"cell": context}


@view_config(context=CellText, name='edit', renderer='templates/edit_cell_text.jinja2')
def edit_cell_text(context, request):
    if 'form.submitted' in request.params:
        context.title = request.params['title']
        context.contents = request.params['contents']
        return HTTPFound(location=request.resource_url(context))
    return {"cell": context}


@view_config(context=CellRichText, renderer='honeycomb:templates/cell.jinja2')
def richtextcell(request):
    title = getattr(request.context, 'title', "Wild cell")
    return {'project': 'Honeycomb', 'title': title, 'contents': request.context.source}


@view_config(context=CellRichText, name='CreateNew', renderer='templates/view_cell_richtext.jinja2')
def view_cell_richtext(context, request):
    return {"cell": context}


@view_config(context=CellRichText, name='edit', renderer='templates/edit_cell_richtext.jinja2')
def edit_cell_richtext(context, request):
    if 'form.submitted' in request.params:
        context.title = request.params['title']
        context.source = request.params['contents']
        return HTTPFound(location=request.resource_url(context))
    return {"cell": context}


@view_config(context=CellAnimation, name='CreateNew', renderer='honeycomb:templates/cell.jinja2')
def animationcell(request):
    title = getattr(request.context, 'title', "Wild cell")
    return {'project': 'Honeycomb', 'title': title, 'contents': request.context.href}


@view_config(context=CellAnimation, renderer='templates/view_cell_animation.jinja2')
def view_cell_animation(context, request):
    return {"cell": context}


@view_config(context=CellAnimation, name='edit', renderer='honeycomb:templates/edit_cell_animation.jinja2')
def edit_cell_animation(context, request):
    if 'form.submitted' in request.params:
        context.title = request.params.get('title', context.title)
        context.href = request.params.get('href', context.href)
        context.icon = request.params.get('icon', context.icon)
        return HTTPFound(location=request.resource_url(context))
    return {"cell": context}

@view_config(context=CellWebContent, renderer='honeycomb:templates/view_cell_webcontent.jinja2')
def webcell(context, request):
    return {'cell': context}


@view_config(context=CellWebContent, name='CreateNew', renderer='templates/view_cell_webcontent.jinja2')
def view_cell_webcontent(context, request):
    return {"cell": context}


@view_config(context=CellWebContent, name='edit', renderer='templates/edit_cell_webcontent.jinja2')
def edit_cell_webcontent(context, request):
    if 'form.submitted' in request.params:
        context.title = request.params['title']
        context.href = request.params['contents']
        return HTTPFound(location=request.resource_url(context))
    return {"cell": context}

@view_config(context=CellIcon, renderer='honeycomb:templates/cell.jinja2')
def iconcell(request):
    title = getattr(request.context, 'title', "Wild cell")
    return {'project': 'Honeycomb', 'title': title, 'contents': request.context.icon}


@view_config(context=CellIcon, name='CreateNew', renderer='templates/view_cell_icon.jinja2')
def view_cell_icon(context, request):
    return {"cell": context}


@view_config(context=CellIcon, name='edit', renderer='honeycomb:templates/edit_cell_icon.jinja2')
def edit_cell_icon(context, request):
    if 'form.submitted' in request.params:
        context.title = request.params.get('title', context.title)
        context.icon = request.params.get('icon', context.icon)
        return HTTPFound(location=request.resource_url(context))
    return {"cell": context}

@view_config(context=HoneycombGraph, renderer='templates/honeycombgraph.jinja2')
def honeycombgraph_view(context, request):
    # Construcción de nodos con sus URLs
    nodes = [(node, request.resource_url(node)) for node in context.nodes]

    edges = []
    for edge in context.edges:
        from_node = edge.from_node
        to_node = edge.to_node

        from_title = getattr(from_node, 'title', getattr(from_node, '__name__', str(from_node)))
        to_title = getattr(to_node, 'title', getattr(to_node, '__name__', str(to_node)))

        from_url = request.resource_url(from_node) if hasattr(from_node, '__name__') else None
        to_url = request.resource_url(to_node) if hasattr(to_node, '__name__') else None

        edge_dict = {
            'title': edge.title,
            'from': from_title,
            'from_url': from_url,
            'to': to_title,
            'to_url': to_url,
            'kind': edge.kind
        }

        edges.append(edge_dict)

    nodes_json = [{
        'id': getattr(node, '__name__', f'node-{i}'),
        'title': getattr(node, 'title', getattr(node, '__name__', f'node-{i}')),
        'url': url
    } for i, (node, url) in enumerate(nodes)]

    edges_json = [{
        'source': getattr(e.from_node, '__name__', str(e.from_node)),
        'target': getattr(e.to_node, '__name__', str(e.to_node)),
        'source_title': getattr(e.from_node, 'title', getattr(e.from_node, '__name__', '')),
        'target_title': getattr(e.to_node, 'title', getattr(e.to_node, '__name__', '')),
        'source_url': request.resource_url(e.from_node) if hasattr(e.from_node, '__name__') else None,
        'target_url': request.resource_url(e.to_node) if hasattr(e.to_node, '__name__') else None,
        'kind': e.kind
    } for e in context.edges]

    return {
        'project': 'Honeycomb Graph',
        'title': context.title,
        'nodes': nodes,
        'edges': edges,
        'nodes_json': nodes_json,
        'edges_json': edges_json,
        'request': request
    }

@view_config(route_name='grafo-principal-json', renderer='json')
def grafo_principal_json(request):
    graph = request.root['grafo-principal']
    return graph.to_dict()

@view_config(route_name='edit_node', renderer='templates/edit_node.jinja2', request_method='GET')
def edit_node_view(request):
    node_id = request.matchdict['id']
    graph = request.root['grafo-principal']
    node = graph.get_node_by_name(node_id)

    if node is None:
        raise HTTPNotFound(f"No se encontró el nodo '{node_id}'")

    return {'node': node}

@view_config(route_name='edit_node', request_method='POST')
def update_node_view(request):
    node_id = request.matchdict['id']
    graph = request.root['grafo-principal']
    node = graph.get_node_by_name(node_id)

    if node is None:
        raise HTTPNotFound(f"No se encontró el nodo '{node_id}'")

    node.title = request.POST.get('title', node.title)
    if hasattr(node, 'contents'):
        node.contents = request.POST.get('contents', node.contents)

    connect_to = request.POST.get('connect_to')
    if connect_to:
        target_node = graph.get_node_by_name(connect_to)
        if target_node:
            edge_name = f"{node.__name__}-{target_node.__name__}"
            edge = CellEdge(name=edge_name, title="Conexión creada", from_node=node, to_node=target_node, kind="default")
            graph.add_edge(edge)

    return HTTPFound(location=request.resource_url(graph))


@view_config(route_name='create_node', request_method='GET')
def create_node_view(request):
    graph = request.root['grafo-principal']

    base_name = "nuevo-nodo"
    i = 1
    while graph.get_node_by_name(f"{base_name}-{i}"):
        i += 1
    node_name = f"{base_name}-{i}"

    node = CellText(name=node_name, contents="", title="Nuevo nodo")
    graph.add_node(node)

    return HTTPFound(location=request.route_url('edit_node', id=node.__name__))

from pyramid.view import view_config
from pyramid.response import Response
from pyramid.httpexceptions import HTTPFound
import json

MAX_BYTES = 2 * 1024 * 1024 

@view_config(route_name='import_json', request_method='POST')
def import_json_view(request):
    upload = request.POST.get('json_file')
    if upload is None or getattr(upload, 'file', None) is None:
        return Response("Error: No se recibió el archivo", status=400)

    ctype = getattr(upload, 'type', '') or ''
    if ctype and ctype not in ('application/json', 'text/json', 'application/octet-stream'):
        return Response(f"Tipo no soportado: {ctype}. Sube un archivo .json", status=415)

    f = upload.file
    try:
        try:
            f.seek(0, 2)
            size = f.tell()
            f.seek(0)
        except Exception:
            size = None 

        if size is not None and size > MAX_BYTES:
            return Response(f"Archivo demasiado grande (> {MAX_BYTES} bytes)", status=413)

        data_bytes = f.read(MAX_BYTES + 1)
        if not data_bytes:
            return Response("El archivo está vacío", status=400)
        if len(data_bytes) > MAX_BYTES:
            return Response(f"Archivo demasiado grande (> {MAX_BYTES} bytes)", status=413)

        data = json.loads(data_bytes)
    except json.JSONDecodeError as e:
        return Response(f"Error al parsear JSON: línea {e.lineno}, col {e.colno}: {e.msg}", status=400)
    except Exception as e:
        return Response(f"Error al leer JSON: {e}", status=400)

    if not isinstance(data, dict):
        return Response("JSON raíz debe ser un objeto", status=400)

    nodes_in = data.get("nodes", [])
    edges_in = data.get("edges", [])
    if not isinstance(nodes_in, list) or not isinstance(edges_in, list):
        return Response("Estructura inválida: 'nodes' y 'edges' deben ser listas", status=400)

    try:
        graph = request.root['grafo-principal']
    except KeyError:
        return Response("No se encontró el recurso 'grafo-principal'", status=404)

    try:
        graph.nodes[:] = []
    except Exception:
        graph.nodes = []
    try:
        graph.edges[:] = []
    except Exception:
        graph.edges = []

    name_index = set()
    for i, node_data in enumerate(nodes_in, 1):
        if not isinstance(node_data, dict):
            return Response(f"Node #{i} inválido: debe ser objeto", status=400)
        nid = node_data.get("id")
        if not isinstance(nid, str) or not nid.strip():
            return Response(f"Node #{i} inválido: 'id' requerido (string no vacío)", status=400)

        title = node_data.get("title") or ""
        contents = node_data.get("content") or ""

        if nid in name_index:
            return Response(f"ID de nodo duplicado: '{nid}'", status=400)
        name_index.add(nid)

        node = CellText(
            name=nid,
            title=title,
            contents=contents,
        )
        graph.add_node(node)

    existing_names = {n.__name__ for n in getattr(graph, 'nodes', [])}
    edge_names = set()

    for j, edge_data in enumerate(edges_in, 1):
        if not isinstance(edge_data, dict):
            return Response(f"Edge #{j} inválido: debe ser objeto", status=400)

        src = edge_data.get("source")
        tgt = edge_data.get("target")
        if not isinstance(src, str) or not isinstance(tgt, str):
            return Response(f"Edge #{j} inválido: 'source' y 'target' deben ser strings", status=400)

        if src not in existing_names or tgt not in existing_names:
            continue

        from_node = graph.get_node_by_name(src)
        to_node = graph.get_node_by_name(tgt)
        if not from_node or not to_node:
            continue

        title = edge_data.get("label") or ""
        kind = edge_data.get("kind") or ""

        base_name = f"{from_node.__name__}-{to_node.__name__}"
        name = base_name
        k = 2
        while name in edge_names:
            name = f"{base_name}-{k}"
            k += 1
        edge_names.add(name)

        edge = CellEdge(
            name=name,
            title=title,
            from_node=from_node,
            to_node=to_node,
            kind=kind,
        )
        graph.add_edge(edge)

    return HTTPFound(location=request.resource_url(graph))
