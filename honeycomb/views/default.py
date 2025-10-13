from pyramid.view import view_config
from pyramid.httpexceptions import HTTPSeeOther, HTTPFound
from pyramid_storage.exceptions import FileNotAllowed
from pyramid_storage import extensions
from pyramid import traversal

from ..models import *


@view_config(context=BeeHive, renderer='templates/beehive.jinja2')
def beehive_view(context, request):
    # La vista ahora está limpia y solo prepara los datos para la plantilla.
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
    # Ejemplo de creación de un nuevo nodo
    if 'form.submitted' in request.params:
        title = request.params.get('title', '')
        contents = request.params.get('contents', '')
        nuevo_nodo = CellText(name=title, contents=contents, title=title)
        # Agregar el nodo al Honeycomb actual
        request.context[nuevo_nodo.__name__] = nuevo_nodo
        # Agregar el nodo al índice de BeeHive
        beehive = traversal.find_root(resource=request.context)
        beehive.add_node(nuevo_nodo)
        return HTTPFound(location=request.resource_url(nuevo_nodo))
    return {"cell": context}


@view_config(context=CellText, name='edit', renderer='templates/edit_cell_text.jinja2')
def edit_cell_text(context, request):
    if 'form.submitted' in request.params:
        context.title = request.params['title']
        context.contents = request.params['contents']
        return HTTPFound(location=request.resource_url(context))
    return {"cell": context}


# Vistas Nuevas
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
def honeycomb_graph_view(context, request):
    # Prepara la lista de nodos y sus URLs
    print("DEBUG - Nodos en grafo:", context.nodes)
    print("DEBUG - Aristas en grafo:", context.edges)
    nodes = [(node, request.resource_url(node)) for node in context.nodes]

    # Prepara la lista de aristas (edges)
    edges = []
    for edge in context.edges:
        from_node = edge.from_node
        to_node = edge.to_node
        edges.append({
            "title": getattr(edge, "title", ""),
            "from": getattr(from_node, 'title', getattr(from_node, '__name__', str(from_node))),
            "from_url": request.resource_url(from_node) if hasattr(from_node, '__name__') else "#",
            "to": getattr(to_node, 'title', getattr(to_node, '__name__', str(to_node))),
            "to_url": request.resource_url(to_node) if hasattr(to_node, '__name__') else "#",
            "kind": getattr(edge, "kind", "")
        })
    return {
        "title": context.title,
        "nodes": nodes,
        "edges": edges
    }