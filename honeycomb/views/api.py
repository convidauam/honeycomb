import uuid
import math
from cornice.resource import resource
from pyramid import traversal
from ..models import *
from ..models.beehive import CellWebContent, CellIcon, CellAnimation, CellText
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

sipping_data_store = {}

@resource(path='/api/v1/sipping/{nodeid}', cors_origins=('*',))
class SippingResource:
    def __init__(self, request, context=None):
        self.request = request
        self.context = context

    def get(self):
        nodeid = self.request.matchdict['nodeid']
        user = getattr(self.request, 'identity', None)
        userid = getattr(user, 'userid', getattr(user, 'id', 'anon'))
        key = f"{userid}:{nodeid}"
        data = sipping_data_store.get(key, {
            'interacciones_previas': [],
            'estadisticas': {},
            'logros': []
        })
        return data

    def post(self):
        nodeid = self.request.matchdict['nodeid']
        user = getattr(self.request, 'identity', None)
        userid = getattr(user, 'userid', getattr(user, 'id', 'anon'))
        key = f"{userid}:{nodeid}"
        try:
            payload = self.request.json_body
        except Exception:
            self.request.response.status = 400
            return {'error': 'Invalid JSON'}
        # Solo permite modificar datos de este nodo
        sipping_data_store[key] = payload
        return {'status': 'ok', 'saved': payload}



#CRUD Audio

@resource(collection_path='/api/v1/admin/audios',
          path='/api/v1/admin/audios/{node_id}',
          cors_origins=('*',),
          factory='honeycomb.root_factory')
class AudioAdminResource:
    """Administración para audio"""

    def __init__(self, request, context=None):
        self.request = request
        self.request = context
        root = transversal.find_root(resource=self.context)
        if not hasattr(root, "__nodes__"):
            root.__nodes__ = OOBTree()


    def collection_post(self):

        """CREATE - agregar un audio"""
        #Autenticacion
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Se requiere iniciar sesión'}

        root = transversal.find_root(resource=self.context)

        try :
            data = self.request.json_body
        except:
            self.request.response.status = 400
            return {'error': 'Se requiere JSON valido'}

        #Validacion de campos
        required = ['nombre', 'titulo', 'url_audio']
        for campo in required:
            if campo not in data:
                self.request.response.status = 400
                return {'error': f'El campo "{campo}" es requerido'}

        #Crear objeto
        nuevo_audio = CellWebContent(
            name=data['nombre'],
            url=data['url_audio'],
            title=data['titulo'],
            icon=data.get('icono')
        )

        nuevo_audio.id = str(uuid.uuid4())
        root.__nodes__[str(nuevo_audio.id)] = nuevo_audio

        self.request.response.status = 201
        return {
            'status': 'creado',
            'id': str(nuevo_audio.id),
            'mensaje': 'Audio creado'
        }

    def put(self):

        """UPDATE - actualizar un audio existente"""
        #Autenticacion
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Se requiere iniciar sesión'}

        root = transversal.find_root(resource=self.context)
        node_id = self.request.matchdict['node_id']

        node = root.__nodes__.get(node_id)
        if not node or not isinstance(node, CellWebContent):
            self.request.response.status = 404
            return {'error': 'Audio no encontrado'}

        try:
            data = self.request.json_body
        except:
            self.request.response.status = 400
            return {'error': 'Se requiere JSON valido'}

        
        #Actualizacion de los campos
        if 'titulo' in data:
            node.title = data['titulo']
        if 'url_audio' in data:
            node.href = data['url.audio']
        if 'icono' in data:
            node.icon = data['icono']

        return {
            'status': 'actualizado',
            'id': node_id,
            'mensaje': 'Audio actualizado'
        }


    def delete(self):

        """DELETE - eliminar un audio"""
        #Autenticacion
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Se requiere iniciar sesión'}

        root = transversal.find_root(resource=self.context)
        node_id = self.request.matchdict['node_id']

        node = root.__nodes__.get(node_id)
        if not node or not isinstance(node, CellWebContent):
            self.request.response.status = 404
            return {'error': 'Audio no encontrado'}

        del root.__nodes__[node_id]

        return {
            'status': 'eliminado',
            'id': node_id,
            'mensaje': 'Audio eliminado'
        }


#CRUD Imagenes

@resource(collection_path='/api/v1/admin/imagenes',
          path='/api/v1/admin/imagenes/{node_id}',
          cors_origins=('*',),
          factory='honeycomb.root_factory')
class ImagenesAdminResource:
    """Administración para imagenes"""

    def __init__(self, request, context=None):
        self.request = request
        self.request = context
        root = transversal.find_root(resource=self.context)
        if not hasattr(root, "__nodes__"):
            root.__nodes__ = OOBTree()


    def collection_post(self):

        """CREATE - agregar una imagen"""
        #Autenticacion
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Se requiere iniciar sesión'}

        root = transversal.find_root(resource=self.context)

        try :
            data = self.request.json_body
        except:
            self.request.response.status = 400
            return {'error': 'Se requiere JSON valido'}

        #Validacion de campos
        if 'nombre' not in data:
            return {'error': 'Debes agregar un "nombre"'}
        if 'titulo' not in data:
            return {'error': 'Debes agregar un "titulo"'}

        #Crear objeto
        nueva_imagen = CellIcon(
            name=data['nombre'],
            title=data['titulo'],
            icon=data.get('icono')
        )

        nueva_imagen.id = str(uuid.uuid4())
        root.__nodes__[str(nueva_imagen.id)] = nueva_imagen

        self.request.response.status = 201
        return {
            'status': 'creado',
            'id': str(nueva_imagen.id),
            'tipo': 'imagen',
            'mensaje': 'Imagen creada'
        }

    def put(self):

        """UPDATE - actualizar una imagen """
        #Autenticacion
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Se requiere iniciar sesión'}

        root = transversal.find_root(resource=self.context)
        node_id = self.request.matchdict['node_id']

        node = root.__nodes__.get(node_id)
        if not node or not isinstance(node, CellIcon):
            self.request.response.status = 404
            return {'error': 'Imagen no encontrada'}

        try:
            data = self.request.json_body
        except:
            self.request.response.status = 400
            return {'error': 'Se requiere JSON valido'}

        
        #Actualizacion de los campos
        if 'titulo' in data:
            node.title = data['titulo']
        if 'icono' in data:
            node.icon = data['icono']

        return {
            'status': 'actualizado',
            'id': node_id,
            'mensaje': 'Imagen actualizada'
        }


    def delete(self):

        """DELETE - eliminar un audio"""
        #Autenticacion
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Se requiere iniciar sesión'}

        root = transversal.find_root(resource=self.context)
        node_id = self.request.matchdict['node_id']

        node = root.__nodes__.get(node_id)
        if not node or not isinstance(node, CellIcon):
            self.request.response.status = 404
            return {'error': 'Imagen no encontrada'}

        del root.__nodes__[node_id]

        return {
            'status': 'eliminado',
            'id': node_id,
            'mensaje': 'Imagen eliminada'
        }


#CRUD Video

@resource(collection_path='/api/v1/admin/videos',
          path='/api/v1/admin/videos/{node_id}',
          cors_origins=('*',),
          factory='honeycomb.root_factory')
class VideoAdminResource:
    """Administración para video"""

    def __init__(self, request, context=None):
        self.request = request
        self.request = context
        root = transversal.find_root(resource=self.context)
        if not hasattr(root, "__nodes__"):
            root.__nodes__ = OOBTree()


    def collection_post(self):

        """CREATE - agregar un video"""
        #Autenticacion
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Se requiere iniciar sesión'}

        root = transversal.find_root(resource=self.context)

        try :
            data = self.request.json_body
        except:
            self.request.response.status = 400
            return {'error': 'Se requiere JSON valido'}

        #Validacion de campos
        required = ['nombre', 'titulo', 'url_video']
        for campo in required:
            if campo not in data:
                self.request.response.status = 400
                return {'error': f'El campo "{campo}" es requerido'}

        #Crear objeto
        nuevo_video = CellWebContent(
            name=data['nombre'],
            url=data['url_video'],
            title=data['titulo'],
            icon=data.get('icono')
        )

        nuevo_video.id = str(uuid.uuid4())
        root.__nodes__[str(nuevo_video.id)] = nuevo_video

        self.request.response.status = 201
        return {
            'status': 'creado',
            'id': str(nuevo_video.id),
            'tipo': 'video',
            'mensaje': 'Video creado'
        }

    def put(self):

        """UPDATE - actualizar un video existente"""
        #Autenticacion
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Se requiere iniciar sesión'}

        root = transversal.find_root(resource=self.context)
        node_id = self.request.matchdict['node_id']

        node = root.__nodes__.get(node_id)
        if not node or not isinstance(node, CellWebContent):
            self.request.response.status = 404
            return {'error': 'Video no encontrado'}

        try:
            data = self.request.json_body
        except:
            self.request.response.status = 400
            return {'error': 'Se requiere JSON valido'}

        
        #Actualizacion de los campos
        if 'titulo' in data:
            node.title = data['titulo']
        if 'url_video' in data:
            node.href = data['url_video']
        if 'icono' in data:
            node.icon = data['icono']

        return {
            'status': 'actualizado',
            'id': node_id,
            'mensaje': 'Video actualizado'
        }


    def delete(self):

        """DELETE - eliminar un video"""
        #Autenticacion
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Se requiere iniciar sesión'}

        root = transversal.find_root(resource=self.context)
        node_id = self.request.matchdict['node_id']

        node = root.__nodes__.get(node_id)
        if not node or not isinstance(node, CellWebContent):
            self.request.response.status = 404
            return {'error': 'Video no encontrado'}

        del root.__nodes__[node_id]

        return {
            'status': 'eliminado',
            'id': node_id,
            'mensaje': 'Video eliminado'
        }


#CRUD Animacion

@resource(collection_path='/api/v1/admin/animaciones',
          path='/api/v1/admin/animaciones/{node_id}',
          cors_origins=('*',),
          factory='honeycomb.root_factory')
class AnimacionAdminResource:
    """Administración para animaciones"""

    def __init__(self, request, context=None):
        self.request = request
        self.request = context
        root = transversal.find_root(resource=self.context)
        if not hasattr(root, "__nodes__"):
            root.__nodes__ = OOBTree()


    def collection_post(self):

        """CREATE - agregar una animacion"""
        #Autenticacion
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Se requiere iniciar sesión'}

        root = transversal.find_root(resource=self.context)

        try :
            data = self.request.json_body
        except:
            self.request.response.status = 400
            return {'error': 'Se requiere JSON valido'}

        #Validacion de campos
        required = ['nombre', 'titulo', 'url_animacion']
        for campo in required:
            if campo not in data:
                self.request.response.status = 400
                return {'error': f'El campo "{campo}" es requerido'}

        #Crear objeto
        nueva_animacion = CellAnimation(
            name=data['nombre'],
            url=data['url_animacion'],
            title=data['titulo'],
            icon=data.get('icono')
        )

        nueva_animacion.id = str(uuid.uuid4())
        root.__nodes__[str(nueva_animacion.id)] = nueva_animacion

        self.request.response.status = 201
        return {
            'status': 'creado',
            'id': str(nueva_animacion.id),
            'tipo': 'animacion',
            'mensaje': 'Animacion creada'
        }

    def put(self):

        """UPDATE - actualizar una animacion existente"""
        #Autenticacion
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Se requiere iniciar sesión'}

        root = transversal.find_root(resource=self.context)
        node_id = self.request.matchdict['node_id']

        node = root.__nodes__.get(node_id)
        if not node or not isinstance(node, CellAnimation):
            self.request.response.status = 404
            return {'error': 'Animacion no encontrado'}

        try:
            data = self.request.json_body
        except:
            self.request.response.status = 400
            return {'error': 'Se requiere JSON valido'}

        
        #Actualizacion de los campos
        if 'titulo' in data:
            node.title = data['titulo']
        if 'url_animacion' in data:
            node.href = data['url_animacion']
        if 'icono' in data:
            node.icon = data['icono']

        return {
            'status': 'actualizado',
            'id': node_id,
            'mensaje': 'Animacion actualizada'
        }


    def delete(self):

        """DELETE - eliminar una animacion"""
        #Autenticacion
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Se requiere iniciar sesión'}

        root = transversal.find_root(resource=self.context)
        node_id = self.request.matchdict['node_id']

        node = root.__nodes__.get(node_id)
        if not node or not isinstance(node, CellAnimation):
            self.request.response.status = 404
            return {'error': 'Animacion no encontrada'}

        del root.__nodes__[node_id]

        return {
            'status': 'eliminado',
            'id': node_id,
            'mensaje': 'Animacion eliminada'
        }


#CRUD Texto

@resource(collection_path='/api/v1/admin/textos',
          path='/api/v1/admin/textos/{node_id}',
          cors_origins=('*',),
          factory='honeycomb.root_factory')
class TextoAdminResource:
    """Administración para textos"""

    def __init__(self, request, context=None):
        self.request = request
        self.request = context
        root = transversal.find_root(resource=self.context)
        if not hasattr(root, "__nodes__"):
            root.__nodes__ = OOBTree()


    def collection_post(self):

        """CREATE - agregar un texto"""
        #Autenticacion
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Se requiere iniciar sesión'}

        root = transversal.find_root(resource=self.context)

        try :
            data = self.request.json_body
        except:
            self.request.response.status = 400
            return {'error': 'Se requiere JSON valido'}

        #Validacion de campos
        if 'nombre' not in data or 'titulo' not in data:
            return {'error': 'Falta nombre o titulo'}

        #Crear objeto
        nuevo_texto = CellText(
            name=data['nombre'],
            contents=data.get('contenido', '')
            title=data['titulo'],
            icon=data.get('icono')
        )

        nuevo_texto.id = str(uuid.uuid4())
        root.__nodes__[str(nuevo_texto.id)] = nuevo_texto

        self.request.response.status = 201
        return {
            'status': 'creado',
            'id': str(nuevo_texto.id),
            'tipo': 'texto',
            'mensaje': 'Texto creado'
        }

    def put(self):

        """UPDATE - actualizar un texto existente"""
        #Autenticacion
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Se requiere iniciar sesión'}

        root = transversal.find_root(resource=self.context)
        node_id = self.request.matchdict['node_id']

        node = root.__nodes__.get(node_id)
        if not node or not isinstance(node, CellText):
            self.request.response.status = 404
            return {'error': 'Texto no encontrado'}

        try:
            data = self.request.json_body
        except:
            self.request.response.status = 400
            return {'error': 'Se requiere JSON valido'}

        
        #Actualizacion de los campos
        if 'titulo' in data:
            node.title = data['titulo']
        if 'contenido' in data:
            node.href = data['contenido']
        if 'icono' in data:
            node.icon = data['icono']

        return {
            'status': 'actualizado',
            'id': node_id,
            'mensaje': 'Texto actualizado'
        }


    def delete(self):

        """DELETE - eliminar una animacion"""
        #Autenticacion
        user = getattr(self.request, 'identity', None)
        if not user:
            self.request.response.status = 401
            return {'error': 'Se requiere iniciar sesión'}

        root = transversal.find_root(resource=self.context)
        node_id = self.request.matchdict['node_id']

        node = root.__nodes__.get(node_id)
        if not node or not isinstance(node, CellText):
            self.request.response.status = 404
            return {'error': 'Texto no encontrado'}

        del root.__nodes__[node_id]

        return {
            'status': 'eliminado',
            'id': node_id,
            'mensaje': 'Texto eliminado'
        }






    


          