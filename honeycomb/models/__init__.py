from .beehive import *
from .axes import *
from ZODB.blob import Blob

def appmaker(zodb_root):
    if 'app_root' not in zodb_root:
        app_root = BeeHive()
        
        builder = CellBuilder(default=1)
        app_root.__builder__ = builder


        abejas = Honeycomb('abejas', "Convida Abejas")

        with open("honeycomb/static/assets/paisaje_tematico_coords_icons.json") as f:
            mapa = HoneycombGraph.from_json(f.read(), name="mapa-sitio", title="Paisaje temático")

        mapa.__parent__ = abejas
        abejas[mapa.__name__] = mapa
        app_root.add_node(mapa)

        reproduccion = None
        # FIX: Se cambia el nodo de rescate de CellText a Honeycomb.
        # Si la ZODB está limpia, el código anterior creaba un CellText, lo cual
        # lanzaba un TypeError ('CellText' object does not support item assignment)
        # al intentar guardar el grafo dentro de él. Honeycomb actúa como un contenedor válido.
        for llave, nodo in mapa.items():
            titulo = getattr(nodo, 'title', '') or getattr(nodo, 'label', '')
            if titulo == 'Reproducción':
                reproduccion = nodo
                break
        
        if reproduccion is None:
            reproduccion = Honeycomb("reproduccion_emergencia", "Reproducción")
            mapa['reproduccion_emergencia'] = reproduccion

        with open("honeycomb/static/assets/grafo_reproduccion.json") as f:
            grafo = HoneycombGraph.from_json(f.read(), name="ciclo-reproductivo", title="Ciclo reproductivo")

        grafo.__parent__ = reproduccion
        grafo.icon = CellIcon.from_filesystem('honeycomb/static/assets/Ciclo Reproductivo.png')
        reproduccion[grafo.__name__] = grafo
        app_root.add_node(grafo)
        #abejas.toggle_featured(grafo)
        grafo._p_changed = True

        abejas.__parent__ = app_root
        abejas.__explorer__ = HoneycombExplorer(abejas)
        app_root['abejas'] = abejas

        mecanismos = mapa["mecanismos-de-libado"]
        libado = CellWebContent('libado', title="Libado", url="https://convida.cua.uam.mx/libado/")
        # libado debe pertenecer a abejas (contenedor) y no a mecanismos (hoja)
        libado.__parent__ = abejas
        libado.icon = CellIcon.from_filesystem('honeycomb/static/assets/Mecanismos de libado.png')
        abejas['libado'] = libado
        abejas.toggle_featured(libado)
        app_root.add_node(libado)

        abejopolis = CellWebContent('abejopolis', title="Abejópolis", url="https://convida.cua.uam.mx/abejopolis/")
        abejopolis.__parent__ = abejas
        abejopolis.icon = CellIcon.from_filesystem('honeycomb/static/assets/Abejopolis.png')
        abejas['abejopolis'] = abejopolis
        abejas.toggle_featured(abejopolis)
        app_root.add_node(abejopolis)


        zodb_root['app_root'] = app_root
        print("Nodos en índice:", list(app_root.__nodes__.keys()))
    return zodb_root['app_root']
