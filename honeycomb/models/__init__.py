from .beehive import *
from .axes import *

def appmaker(zodb_root):
    if 'app_root' not in zodb_root:
        app_root = BeeHive()
        
        builder = CellBuilder(default=1)
        app_root.__builder__ = builder

        # # --- Creación del Honeycomb por defecto ---
        # hc = Honeycomb('demo', "Demo Convida")
        # hc.__parent__ = app_root
        # app_root['demo'] = hc
        # hc.__explorer__ = HoneycombExplorer(hc)
        #
        # cell1 = CellText('intro', "Welcome text", title="Introduction")
        # cell1.__parent__ = hc
        # hc['intro'] = cell1
        # print("Agregando nodo:", repr(cell1), type(cell1))
        # print("cell1.title:", getattr(cell1, "title", None))
        # print("cell1.contents:", getattr(cell1, "contents", None))
        #
        # app_root.add_node(cell1)
        # app_root.add_edge(
        #     str(cell1.__parent__.id),
        #     {
        #         "source": str(cell1.__parent__.id),
        #         "target": str(cell1.id),
        #         "id": str(uuid.uuid4()),
        #         "type": "custom-label",
        #         "label": "",
        #         "data": {"hasArrow": False}
        #     }
        # )
        #
        #  # Nodo de Rich Text
        #
        # icon = CellIcon('logo', title="Bee Logo", icon="🐝")
        # icon.__parent__ = hc
        # hc['logo'] = icon
        #
        # app_root.add_node(icon)
        # app_root.add_edge(
        #     str(icon.__parent__.id),
        #     {
        #         "source": str(icon.__parent__.id),
        #         "target": str(icon.id),
        #         "id": str(uuid.uuid4()),
        #         "type": "custom-label",
        #         "label": "",
        #         "data": {"hasArrow": False}
        #     }
        # )
        #
        # web = CellWebContent('link', title="Website", url="https://www.wikipedia.org")
        # web.__parent__ = hc
        # hc['link'] = web
        #
        # app_root.add_node(web)
        # app_root.add_edge(
        #     str(web.__parent__.id),
        #     {
        #         "source": str(web.__parent__.id),
        #         "target": str(web.id),
        #         "id": str(uuid.uuid4()),
        #         "type": "custom-label",
        #         "label": "",
        #         "data": {"hasArrow": False}
        #     }
        # )
        #
        #  # Nodo de Animación
        #
        # animation = CellAnimation('bee-dance', url="/static/bee-dance.gif", title="Bee Dance", icon="🐝")
        # animation.__parent__ = hc
        # hc['bee-dance'] = animation
        #
        # app_root.add_node(animation)
        # app_root.add_edge(
        #     str(animation.__parent__.id),
        #     {
        #         "source": str(animation.__parent__.id),
        #         "target": str(animation.id),
        #         "id": str(uuid.uuid4()),
        #         "type": "custom-label",
        #         "label": "",
        #         "data": {"hasArrow": False}
        #     }
        # )
        #
        # # --- Creación de juegos ---
        # games_hc = Honeycomb('panal-de-juegos', "Panal de Juegos")
        # games_hc.__parent__ = app_root
        # games_hc.__explorer__ = HoneycombExplorer(games_hc)
        # app_root['panal-de-juegos'] = games_hc
        #
        # game_url = '/static/serpiente/index.html'
        # game_cell = CellWebContent(
        #     name='juego-de-serpiente',
        #     title='Juego de la Serpiente',
        #     url=game_url
        # )
        # game_cell.__parent__ = games_hc
        # games_hc['juego-de-serpiente'] = game_cell
        #
        # builder.fill_cell(game_cell)
        #
        # app_root.add_node(game_cell)
        # app_root.add_edge(
        #     str(game_cell.__parent__.id),
        #     {
        #         "source": str(game_cell.__parent__.id),
        #         "target": str(game_cell.id),
        #         "id": str(uuid.uuid4()),
        #         "type": "custom-label",
        #         "label": "",
        #         "data": {"hasArrow": False}
        #     }
        # )
        #
        #  # Nodo del juego de Unity si no existe
        #
        # unity_game_name = 'juego-unity'
        # if unity_game_name not in games_hc:
        #     unity_game_url = '/static/WEB/index.html'
        #
        #     unity_game_cell = CellWebContent(
        #         name=unity_game_name,
        #         title='Juego de Unity',
        #         url=unity_game_url
        #     )
        #     unity_game_cell.__parent__ = games_hc
        #     games_hc[unity_game_name] = unity_game_cell
        #
        #     builder.fill_cell(unity_game_cell)
        #
        #     app_root.add_node(unity_game_cell)
        #     app_root.add_edge(
        #         str(unity_game_cell.__parent__.id),
        #         {
        #             "source": str(unity_game_cell.__parent__.id),
        #             "target": str(unity_game_cell.id),
        #             "id": str(uuid.uuid4()),
        #             "type": "custom-label",
        #             "label": "",
        #             "data": {"hasArrow": False}
        #         }
        #     )
        #     print(f"Se agregó el juego '{unity_game_name}'")
        #
        #Importando grafos desde JSON

        abejas = Honeycomb('abejas', "Convida Abejas")

        with open("honeycomb/static/assets/paisaje_tematico_coords_icons.json") as f:
            mapa = HoneycombGraph.from_json(f.read(), name="mapa-sitio", title="Paisaje temático")

        mapa.__parent__ = abejas
        abejas[mapa.__name__] = mapa
        app_root.add_node(mapa, recurse=True)

        reproduccion = mapa['reproducción']

        with open("honeycomb/static/assets/grafo_reproduccion.json") as f:
            grafo = HoneycombGraph.from_json(f.read(), name="ciclo-reproductivo", title="Ciclo reproductivo")

        grafo.__parent__ = reproduccion
        grafo.icon = CellIcon.from_filesystem('honeycomb/static/assets/Ciclo Reproductivo.png')
        reproduccion[grafo.__name__] = grafo
        app_root.add_node(grafo, recurse=True)
        abejas.toggle_featured(grafo)
        grafo._p_changed = True

        abejas.__parent__ = app_root
        abejas.__explorer__ = HoneycombExplorer(abejas)
        app_root['abejas'] = abejas

        mecanismos = mapa["mecanismos-de-libado"]
        libado = CellWebContent('libado', title="Libado", url="https://convida.cua.uam.mx/libado/")
        libado.__parent__ = mecanismos
        libado.icon = CellIcon.from_filesystem('honeycomb/static/assets/Mecanismos de libado.png')
        mecanismos['libado'] = libado
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
