from pyramid.view import view_config
from pyramid.httpexceptions import HTTPSeeOther, HTTPFound
from pyramid_storage.exceptions import FileNotAllowed
from pyramid_storage import extensions

from ..models import *

import math
from pyramid.view import view_config
import uuid


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

@view_config(context=Honeycomb, name='api', renderer='json')
def honeycomb_api(request):
    """Devuelve un grafo con nodos y aristas de un Honeycomb."""
    honeycomb = request.context
    honeycomb_title = getattr(honeycomb, 'title', "Wild honeycomb")

    # Nodo raíz (el Honeycomb mismo)
    root_node = {
        "id": getattr(honeycomb, "id", str(uuid.uuid4())),
        "data": {
            "label": honeycomb_title,
            "themeColor": "root",
            "url": request.resource_url(honeycomb),
            "icon": getattr(honeycomb, "icon", None),
        },
        "position": {"x": 0, "y": 0},  # en el centro
        "type": "custom",
        "width": 200,
        "height": 80,
    }

    # Nodos hijos distribuidos en círculo
    cells = list(honeycomb.values())
    n = len(cells)
    radius = 300
    child_nodes = []
    for i, cell in enumerate(cells):
        angle = 2 * math.pi * i / n if n > 0 else 0
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)

        child_nodes.append({
            "id": getattr(cell, "id", str(uuid.uuid4())),
            "data": {
                "label": getattr(cell, "title", ""),
                "themeColor": getattr(cell, "themeColor", "default"),
                "url": request.resource_url(cell),
                "icon": getattr(cell, "icon", None),
            },
            "position": {"x": x, "y": y},
            "type": "custom",
            "width": 152,
            "height": 58,
        })

    # Edges: del root hacia cada hijo
    edges = [
        {
            "id": f"edge-{root_node['id']}-{child['id']}",
            "source": root_node["id"],
            "target": child["id"],
            "type": "custom-label",
        }
        for child in child_nodes
    ]

    return {
        "id": root_node["id"],
        "title": honeycomb_title,
        "nodes": [root_node] + child_nodes,
        "edges": edges,
    }


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