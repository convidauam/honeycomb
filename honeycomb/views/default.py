from pyramid.view import view_config
from pyramid.httpexceptions import HTTPSeeOther, HTTPFound, HTTPBadRequest, HTTPNotFound
from pyramid_storage.exceptions import FileNotAllowed
from pyramid_storage import extensions
from pyramid import traversal
import uuid
from pyramid.response import FileIter
from pyramid.httpexceptions import HTTPBadRequest

from ZODB.blob import Blob
import os.path

from ..models import *
from ..forms import *


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


@view_config(context=Honeycomb, name='matrix', renderer='json')
def honeycomb_matrix(request):
    "This view returns a copy of the honeycomb distance matrix triggering its calculation if it isn't already available."
    if hasattr(request.context, '__explorer__'):
        matrix = request.context.__explorer__.matrix
        if not matrix:
            request.context.__explorer__.update_matrix()
            matrix = request.context.__explorer__.matrix
        return matrix.tolist()

# Vista crear audio
@view_config(context=Honeycomb, name="audio", renderer='json', request_method="POST", require_csrf=True)
def audio_create_view(request):
    schema = AudioCellSchema()
    try:
        fields = schema.deserialize(request.POST)
    except colander.Invalid as err:
        request.response.status = 400
        return err.asdict()

    source = request.POST['data'].file

    max_size = int(request.registry.settings.get('beehive_max_audio_size', 104857600))

    parent_uuid = fields['parent']
    title = fields['title']
    duracion = fields.get('length', 0)

    # Improve this by adding both node and edge indexes to each Honeycomb instance
    root = request.context.__parent__
    parent = root.__nodes__.get(parent_uuid, None)
    if parent:
        path = traversal.resource_path_tuple(parent)

        if not path or path[1] != request.context.__name__:
            raise HTTPBadRequest("Parent ID does not belong to this Honeycomb")
    else:
        parent = request.context

    audio = Blob()
    length = 0

    with audio.open('w') as target:
        while True:
            b = source.read(4096)
            if b:
                length += target.write(b)
                if length > max_size:
                    request.response.status = 400
                    max_size_mb = max_size // (1024 * 1024)
                    return {'error': f'El archivo debe ser de maximo {max_size_mb} mb'}
            else:
                break

    cell = CellAudio(name="", data=audio, title=fields['title'], mime=fields['mimetype'], length=duracion)
    cell.__parent__ = parent
    parent[cell.__name__] = cell

    beehive = traversal.find_root(request.context)
    if hasattr(beehive, 'add_node'):
        beehive.add_node(cell)

    request.response.status_int = 201
    return {
        'status': 'creado',
        'id': str(cell.id),
        'title': cell.title,
        'url': request.resource_url(cell)
    }


@view_config(context=CellText, renderer='honeycomb:templates/cell.jinja2')
def textcell(request):
    if hasattr(request.context, 'title'):
        cell_title = request.context.title
    else:
        cell_title = "Wild cell"
    return {'project': 'Honeycomb', 'title': cell_title, 'contents': request.context.contents}


@view_config(context=CellNode, renderer='templates/view_cell_node.jinja2')
def view_cell_node(context, request):
    children = []
    for name, node in context.items():
        node_url = request.resource_url(node)
        children.append((node, node_url))
    return {
        'project': 'BeeHive Project',
        'title': context.__name__,
        'children': children,
        'request': request,
    }


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

#@view_config(context=CellIcon, renderer='honeycomb:templates/cell.jinja2')
#def iconcell(request):
#    title = getattr(request.context, 'title', "Wild cell")
#    return {'project': 'Honeycomb', 'title': title, 'contents': request.context.icon}

@view_config(context=Persistent, name="icon")
def icon_view(request):
    icon = request.context.icon
    if not icon:
        return HTTPNotFound()
    response = request.response
    response.content_type = "image/png"
    response.app_iter = FileIter(icon.blob.open("r"))
    return response

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


@view_config(context=CellAudio, renderer='json', request_method="GET")
def audio_metadata_view(request):
    """Obtener metadatos del audio"""
    cell = request.context
    if not cell.title:
        title = cell.__name__.title() if cell.__name__ else "Audio"
    else:
        title = cell.title

    duracion = getattr(cell, 'length', 0.0)

    return {
        'title': title,
        'id': cell.id.hex if hasattr(cell.id, 'hex') else str(cell.id),
        'length': duracion,
        'mime-type': cell.mime,
        'stream_url': request.resource_url(cell, '@@stream')
    }

@view_config(context=CellAudio, name="stream", request_method="GET")
def audio_stream_view(request):
    """Reproducir audio"""
    cell = request.context
    response = request.response
    response.content_type = cell.mime
    response.app_iter = FileIter(cell.data.open("r"))
    return response


@view_config(context=CellIcon, renderer='json', request_method="GET")
def image_metadata_view(request):
    """Obtener metadatos de imagen"""
    cell = request.context
    return {
        'id': str(cell.id),
        'titulo': cell.title or cell.__name__,
        'icono': getattr(cell, 'icon', ''),
        'mime-type': getattr(cell, 'mime', 'image/jpeg'),
        'image_url': request.resource_url(cell, '@@stream'),
        'tipo': 'imagen'
    }


@view_config(context=CellText, renderer='json', request_method="GET")
def text_metadata_view(request):
    """Obtener metadatos de texto"""
    cell = request.context
    return {
        'id': str(cell.id),
        'titulo': cell.title or cell.__name__,
        'contenido': cell.contents,
        'tipo': 'texto'
    }


@view_config(context=CellIcon, name="stream", request_method="GET")
def image_stream_view(request):
    """Enviar el archivo físico de la imagen"""
    cell = request.context
    response = request.response
    response.content_type = getattr(cell, 'mime', 'image/jpeg')
    response.app_iter = FileIter(cell.blob.open("r"))
    return response


@view_config(context=CellAnimation, renderer='json', request_method="GET")
def animation_metadata_view(request):
    """Obtener metadatos de animación"""
    cell = request.context
    return {
'id': str(cell.id),
        'titulo': cell.title or cell.__name__,
        'mime-type': getattr(cell, 'mime', 'image/gif'),
        'stream_url': request.resource_url(cell, '@@stream'),
        'tipo': 'animacion'
    }


@view_config(context=CellAnimation, name="stream", request_method="GET")
def animation_stream_view(request):
    """Enviar el archivo físico del GIF"""
    cell = request.context
    response = request.response
    response.content_type = getattr(cell, 'mime', 'image/gif')
    response.app_iter = FileIter(cell.data.open("r"))
    return response


@view_config(context=CellWebContent, renderer='json', request_method="GET")
def webcontent_metadata_view(request):
    """Obtener metadatos de contenido web"""
    cell = request.context
    return {
        'id': str(cell.id),
        'titulo': cell.title or cell.__name__,
        'url': cell.href,
        'tipo': 'webcontent'
    }


#Crear
@view_config(context=Honeycomb, name="video", renderer='json', request_method="POST", require_csrf=True)
def video_create_view(request):
    """Video"""
    try:
        title = request.POST['title']
        url = request.POST['url']
        parent_uuid = request.POST.get('parent')
        
        root = request.context.__parent__
        parent = root.__nodes__.get(parent_uuid, request.context)

        cell = CellWebContent(name="", url=url, title=title)
        cell.__parent__ = parent
        parent[cell.__name__] = cell

        beehive = traversal.find_root(request.context)
        if hasattr(beehive, 'add_node'):
            beehive.add_node(cell)

        request.response.status_int = 201
        return {'status': 'creado', 'id': str(cell.id), 'title': cell.title, 'url': request.resource_url(cell)}
    except KeyError as e:
        request.response.status = 400
        return {'error': f'Falta el campo obligatorio: {str(e)}'}
    

@view_config(context=Honeycomb, name="texto", renderer='json', request_method="POST", require_csrf=True)
def text_create_view(request):
    """Texto"""
    try:
        title = request.POST['title']
        contenido = request.POST.get('contents', '')
        parent_uuid = request.POST.get('parent')
        
        root = request.context.__parent__
        parent = root.__nodes__.get(parent_uuid, request.context)

        cell = CellText(name="", contents=contenido, title=title)
        cell.__parent__ = parent
        parent[cell.__name__] = cell

        beehive = traversal.find_root(request.context)
        if hasattr(beehive, 'add_node'):
            beehive.add_node(cell)

        request.response.status_int = 201
        return {'status': 'creado', 'id': str(cell.id), 'title': cell.title, 'url': request.resource_url(cell)}
    except KeyError as e:
        request.response.status = 400
        return {'error': f'Falta el campo obligatorio: {str(e)}'}
    

@view_config(context=Honeycomb, name="imagen", renderer='json', request_method="POST", require_csrf=True)
def image_create_view(request):
    """Imagen"""
    try:
        source = request.POST['data'].file
        title = request.POST['title']
        mimetype = request.POST.get('mimetype', 'image/jpeg')
        parent_uuid = request.POST.get('parent')

        max_size = int(request.registry.settings.get('beehive_max_image_size', 10485760))

        root = request.context.__parent__
        parent = root.__nodes__.get(parent_uuid, request.context)

        archivo_blob = Blob()
        length = 0
        with archivo_blob.open('w') as target:
            while True:
                b = source.read(4096)
                if not b: 
                    break
                length += target.write(b)

                if length > max_size:
                    request.response.status = 400
                    max_size_mb = max_size // (1024 * 1024)
                    return {'error': f'La imagen debe ser de máximo {max_size_mb} MB'}

        cell = CellIcon(archivo_blob)
        cell.id = uuid.uuid4()
        cell.__name__ = str(cell.id)
        cell.title = title
        cell.mimetype = mimetype
        cell.__parent__ = parent
        parent[cell.__name__] = cell

        beehive = traversal.find_root(request.context)
        if hasattr(beehive, 'add_node'):
            beehive.add_node(cell)

        request.response.status_int = 201
        return {'status': 'creado', 'id': str(cell.id), 'title': cell.title, 'url': request.resource_url(cell)}
    except Exception as e:
        request.response.status = 400
        return {'error': f'Error al procesar la imagen: {str(e)}'}
    

@view_config(context=Honeycomb, name="animacion", renderer='json', request_method="POST", require_csrf=True)
def animation_create_view(request):
    """Animación"""
    try:
        source = request.POST['data'].file
        title = request.POST['title']
        mimetype = request.POST.get('mimetype', 'image/gif')
        parent_uuid = request.POST.get('parent')

        max_size = int(request.registry.settings.get('beehive_max_animation_size', 20971520))

        root = request.context.__parent__
        parent = root.__nodes__.get(parent_uuid, request.context)

        archivo_blob = Blob()
        length = 0
        with archivo_blob.open('w') as target:
            while True:
                b = source.read(4096)
                if not b: 
                    break
                length += target.write(b)

                if length > max_size:
                    request.response.status = 400
                    max_size_mb = max_size // (1024 * 1024)
                    return {'error': f'El gif debe ser de máximo {max_size_mb} MB'}

        cell = CellAnimation(name="", data=archivo_blob, mime=mimetype, title=title)
        cell.__parent__ = parent
        parent[cell.__name__] = cell

        beehive = traversal.find_root(request.context)
        if hasattr(beehive, 'add_node'):
            beehive.add_node(cell)

        request.response.status_int = 201
        return {'status': 'creado', 'id': str(cell.id), 'title': cell.title, 'url': request.resource_url(cell)}
    except Exception as e:
        request.response.status = 400
        return {'error': f'Error al procesar la animación: {str(e)}'}


#Actualizar
@view_config(context=CellAudio, name='admin', permission='read', renderer='json', request_method='PUT')
def admin_update_audio(context, request):
    """Actualizar metadatos de audio"""
    data = request.POST if request.POST else getattr(request, 'json_body', {})
    
    if 'titulo' in data or 'title' in data:
        context.title = data.get('title', data.get('titulo', context.title))
        
    if 'data' in request.POST and hasattr(request.POST['data'], 'file'):
        source = request.POST['data'].file
        context.mime = request.POST.get('mimetype', context.mime)

        max_size = int(request.registry.settings.get('beehive_max_audio_size', 104857600))
        archivo_blob = Blob()
        length = 0

        with archivo_blob.open('w') as target:
            while True:
                b = source.read(4096)
                if not b: 
                    break
                length += target.write(b)

                if length > max_size:
                    request.response.status = 400
                    max_size_mb = max_size // (1024 * 1024)
                    return {'error': f'El archivo debe ser de máximo {max_size_mb} MB'}
        context.data = archivo_blob

    return {'status': 'actualizado', 'id': str(context.id)}

@view_config(context=CellWebContent, name='admin', permission='read', renderer='json', request_method='PUT')
def admin_update_webcontent(context, request):
    """Actualizar video"""
    data = request.POST if request.POST else getattr(request, 'json_body', {})
    if 'titulo' in data or 'title' in data:
        context.title = data.get('title', data.get('titulo', context.title))
    if 'url' in data:
        context.href = data['url']
    return {'status': 'actualizado', 'id': str(context.id)}

@view_config(context=CellIcon, name='admin', permission='read', renderer='json', request_method='PUT')
def admin_update_icon(context, request):
    """Actualizar imagen"""
    data = request.POST if request.POST else getattr(request, 'json_body', {})
    if 'titulo' in data or 'title' in data:
        context.title = data.get('title', data.get('titulo', context.title))
    if 'data' in request.POST and hasattr(request.POST['data'], 'file'):
        source = request.POST['data'].file
        mimetype = request.POST.get('mimetype', context.mime)

        max_size = int(request.registry.settings.get('beehive_max_image_size', 10485760))
        archivo_blob = Blob()
        length = 0

        with archivo_blob.open('w') as target:
            while True:
                b = source.read(4096)
                if not b: 
                    break
                length += target.write(b)
                
                if length > max_size:
                    request.response.status = 400
                    max_size_mb = max_size // (1024 * 1024)
                    return {'error': f'La imagen debe ser de máximo {max_size_mb} MB'}
                
        context.blob = archivo_blob
        context.mime = mimetype
        
    return {'status': 'actualizado', 'id': str(context.id)}

@view_config(context=CellText, name='admin', permission='read', renderer='json', request_method='PUT')
def admin_update_text(context, request):
    """Actualizar texto"""
    data = request.json_body
    if 'titulo' in data:
        context.title = data['titulo']
    if 'contenido' in data:
        context.contents = data['contenido']
    return {'status': 'actualizado', 'id': str(context.id)}

@view_config(context=CellAnimation, name='admin', permission='read', renderer='json', request_method='PUT')
def admin_update_animation(context, request):
    """Actualizar animación"""
    data = request.POST if request.POST else getattr(request, 'json_body', {})
    
    if 'titulo' in data or 'title' in data:
        context.title = data.get('title', data.get('titulo', context.title))
        
    # Si viene un archivo nuevo (gif), lo actualizamos
    if 'data' in request.POST and hasattr(request.POST['data'], 'file'):
        source = request.POST['data'].file
        mimetype = request.POST.get('mimetype', context.mime)
        
        max_size = int(request.registry.settings.get('beehive_max_animation_size', 20971520))
        archivo_blob = Blob()
        length = 0

        with archivo_blob.open('w') as target:
            while True:
                b = source.read(4096)
                if not b: 
                    break
                length += target.write(b)

                if length > max_size:
                    request.response.status = 400
                    max_size_mb = max_size // (1024 * 1024)
                    return {'error': f'El gif debe ser de máximo {max_size_mb} MB'}
                
        context.data = archivo_blob
        context.mime = mimetype
        
    return {'status': 'actualizado', 'id': str(context.id)}

#Eliminar
@view_config(context=CellLeaf, name='admin', permission='read', renderer='json', request_method='DELETE')
def admin_delete_node(context, request):
    """Eliminar cualquier tipo de nodo"""
    parent = context.__parent__
    name = context.__name__
    
    if parent and name in parent:
        beehive = traversal.find_root(context)
        if hasattr(beehive, 'remove_node'):
            node_id = str(getattr(context, "id", "")) or name
            beehive.remove_node(node_id)
            
        del parent[name]
        return {'status': 'eliminado', 'id': str(context.id)}
    
    request.response.status_int = 404
    return {'error': 'No se pudo eliminar el nodo o ya no existe'}


