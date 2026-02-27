from pyramid.view import view_config
from pyramid.httpexceptions import HTTPSeeOther, HTTPFound
from pyramid_storage.exceptions import FileNotAllowed
from pyramid_storage import extensions
from pyramid import traversal

from ..models import *
from ..models.beehive import ViewProxy


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
    return {'project': 'Honeycomb', 'title': honeycomb_title, 'map': map, 'cells': cells, 'context': request.context}


# Vista para manejar sub-vistas de Honeycomb (como crear, editar, etc.)

# Vista por defecto para ViewProxy - dispatcher base
@view_config(context=ViewProxy, request_method='GET')
def viewproxy_default_get(context, request):
    """Renderiza la vista nombrada correspondiente basada en __name__"""
    view_name = context.__name__
    
    if not view_name.startswith('create_'):
        from pyramid.httpexceptions import HTTPNotFound
        raise HTTPNotFound(f"Unknown view: {view_name}")
    
    content_type = view_name.replace('create_', '')
    
    # Map templates
    templates = {
        'cell_text': 'honeycomb:templates/create_cell_text.jinja2',
        'cell_richtext': 'honeycomb:templates/create_cell_richtext.jinja2',
        'cell_animation': 'honeycomb:templates/create_cell_animation.jinja2',
        'cell_webcontent': 'honeycomb:templates/create_cell_webcontent.jinja2',
        'cell_icon': 'honeycomb:templates/create_cell_icon.jinja2',
    }
    
    template_path = templates.get(content_type)
    if not template_path:
        from pyramid.httpexceptions import HTTPNotFound
        raise HTTPNotFound(f"Unknown content type: {content_type}")
    
    from pyramid.renderers import render
    from pyramid.response import Response
    
    html = render(template_path, {'honeycomb': context.__parent__}, request=request)
    return Response(html, content_type='text/html')


# Vista para POST en ViewProxy
@view_config(context=ViewProxy, request_method='POST')
def viewproxy_post(context, request):
    """Crea el contenido basado en el tipo en __name__"""
    honeycomb = context.__parent__
    view_name = context.__name__
    
    if not view_name.startswith('create_'):
        from pyramid.httpexceptions import HTTPNotFound
        raise HTTPNotFound()
    
    content_type = view_name.replace('create_', '')
    
    title = request.POST.get('title', 'Sin título')
    icon = request.POST.get('icon', '')
    
    if content_type == 'cell_text':
        contents = request.POST.get('contents', '')
        nuevo_nodo = CellText(name=title, contents=contents, title=title, icon=icon)
    elif content_type == 'cell_richtext':
        contents = request.POST.get('contents', '')
        nuevo_nodo = CellRichText(name=title, source=contents, title=title, icon=icon)
    elif content_type == 'cell_animation':
        href = request.POST.get('href', '')
        nuevo_nodo = CellAnimation(name=title, href=href, title=title, icon=icon)
    elif content_type == 'cell_webcontent':
        href = request.POST.get('href', '')
        nuevo_nodo = CellWebContent(name=title, href=href, title=title, icon=icon)
    elif content_type == 'cell_icon':
        nuevo_nodo = CellIcon(name=title, icon=icon, title=title)
    else:
        from pyramid.httpexceptions import HTTPBadRequest
        raise HTTPBadRequest()
    
    # Add to honeycomb
    honeycomb[nuevo_nodo.__name__] = nuevo_nodo
    honeycomb._p_changed = True
    
    # Asegurar que el nodo tiene referencia correcta al padre
    nuevo_nodo.__parent__ = honeycomb
    
    # Add to global index
    beehive_root = traversal.find_root(resource=honeycomb)
    beehive_root.add_node(nuevo_nodo)
    
    return HTTPFound(location=request.resource_url(nuevo_nodo))


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
    return {'project': 'Honeycomb', 'title': cell_title, 'contents': request.context.contents, 'cell': request.context}


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


@view_config(context=CellText, name='edit', renderer='templates/edit_cell_text.jinja2', request_method='GET')
def edit_cell_text_get(context, request):
    return {"cell": context}


@view_config(context=CellText, name='edit', renderer='string', request_method='POST')
def edit_cell_text_post(context, request):
    context.title = request.params.get('title', context.title)
    context.contents = request.params.get('contents', context.contents)
    context.icon = request.params.get('icon', context.icon or '')
    context._p_changed = True
    return HTTPFound(location=request.resource_url(context))


# DELETE CELL TEXT
@view_config(context=CellText, name='delete', renderer='string', request_method='POST')
def delete_cell_text(context, request):
    honeycomb = request.context.__parent__
    beehive = traversal.find_root(resource=request.context)
    cell_name = request.context.__name__
    
    del honeycomb[cell_name]
    honeycomb._p_changed = True
    
    # Intentar remover del índice
    try:
        beehive.index.remove(request.context)
    except:
        pass
    
    return HTTPFound(location=request.resource_url(honeycomb))


@view_config(context=CellRichText, renderer='honeycomb:templates/cell.jinja2')
def richtextcell(request):
    title = getattr(request.context, 'title', "Wild cell")
    return {'project': 'Honeycomb', 'title': title, 'contents': request.context.source}


@view_config(context=CellRichText, name='CreateNew', renderer='templates/view_cell_richtext.jinja2')
def view_cell_richtext(context, request):
    return {"cell": context}


@view_config(context=CellRichText, name='edit', renderer='templates/edit_cell_richtext.jinja2', request_method='GET')
def edit_cell_richtext_get(context, request):
    return {"cell": context}


@view_config(context=CellRichText, name='edit', renderer='string', request_method='POST')
def edit_cell_richtext_post(context, request):
    context.title = request.params.get('title', context.title)
    context.source = request.params.get('contents', context.source)
    context.icon = request.params.get('icon', context.icon or '')
    context._p_changed = True
    return HTTPFound(location=request.resource_url(context))


# DELETE CELL RICHTEXT
@view_config(context=CellRichText, name='delete', renderer='string', request_method='POST')
def delete_cell_richtext(context, request):
    honeycomb = request.context.__parent__
    beehive = traversal.find_root(resource=request.context)
    cell_name = request.context.__name__
    
    del honeycomb[cell_name]
    honeycomb._p_changed = True
    
    try:
        beehive.index.remove(request.context)
    except:
        pass
    
    return HTTPFound(location=request.resource_url(honeycomb))


@view_config(context=CellAnimation, name='edit', renderer='templates/edit_cell_animation.jinja2', request_method='GET')
def edit_cell_webcontent_get(context, request):
    return {"cell": context}


@view_config(context=CellWebContent, name='edit', renderer='string', request_method='POST')
def edit_cell_webcontent_post(context, request):
    context.title = request.params.get('title', context.title)
    context.href = request.params.get('href', context.href or '')
    context.icon = request.params.get('icon', context.icon or '')
    context._p_changed = True
    return HTTPFound(location=request.resource_url(context))


# DELETE CELL WEBCONTENT
@view_config(context=CellWebContent, name='delete', renderer='string', request_method='POST')
def delete_cell_webcontent(context, request):
    honeycomb = request.context.__parent__
    beehive = traversal.find_root(resource=request.context)
    cell_name = request.context.__name__
    
    del honeycomb[cell_name]
    honeycomb._p_changed = True
    
    try:
        beehive.index.remove(request.context)
    except:
        pass
    
    return HTTPFound(location=request.resource_url(honeycomb))


@view_config(context=CellIcon, name='edit', renderer='templates/edit_cell_icon.jinja2', request_method='GET')
def edit_cell_icon_get(context, request):
    return {"cell": context}


@view_config(context=CellIcon, name='edit', renderer='string', request_method='POST')
def edit_cell_icon_post(context, request):
    context.title = request.params.get('title', context.title)
    context.icon = request.params.get('icon', context.icon or '')
    context._p_changed = True
    return HTTPFound(location=request.resource_url(context))


# DELETE CELL ICON
@view_config(context=CellIcon, name='delete', renderer='string', request_method='POST')
def delete_cell_icon(context, request):
    honeycomb = request.context.__parent__
    beehive = traversal.find_root(resource=request.context)
    cell_name = request.context.__name__
    
    del honeycomb[cell_name]
    honeycomb._p_changed = True
    
    try:
        beehive.index.remove(request.context)
    except:
        pass
    
    return HTTPFound(location=request.resource_url(honeycomb))


@view_config(context=CellAnimation, renderer='honeycomb:templates/cell.jinja2')
def animationcell(request):
    title = getattr(request.context, 'title', "Wild cell")
    return {'project': 'Honeycomb', 'title': title, 'contents': request.context.href, 'cell': request.context}


@view_config(context=CellAnimation, name='view', renderer='templates/view_cell_animation.jinja2')
def view_cell_animation(context, request):
    return {"cell": context}


@view_config(context=CellWebContent, renderer='honeycomb:templates/view_cell_webcontent.jinja2')
def webcell(context, request):
    return {'cell': context}


@view_config(context=CellWebContent, name='CreateNew', renderer='templates/view_cell_webcontent.jinja2')
def view_cell_webcontent(context, request):
    return {"cell": context}

@view_config(context=CellIcon, renderer='honeycomb:templates/cell.jinja2')
def iconcell(request):
    title = getattr(request.context, 'title', "Wild cell")
    return {'project': 'Honeycomb', 'title': title, 'contents': request.context.icon, 'cell': request.context}


@view_config(context=CellIcon, name='CreateNew', renderer='templates/view_cell_icon.jinja2')
def view_cell_icon(context, request):
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