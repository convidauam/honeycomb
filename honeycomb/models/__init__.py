from .beehive import *

def appmaker(zodb_root):
    if 'app_root' not in zodb_root:
        app_root = BeeHive()
        
        # --- Creación del Honeycomb por defecto ---
        hc = Honeycomb('default', "Convida Abejas")
        hc.__parent__ = app_root
        app_root['default'] = hc

        # --- Creación del grafo principal ---
        graph = HoneycombGraph(name="grafo-principal", title="Mapa de Conexiones")
        graph.__parent__ = app_root
        app_root['grafo-principal'] = graph

        nodo_a = CellText('nodo-a', "Contenido A", title="Nodo A")
        nodo_a.__name__ = 'nodo-a'
        nodo_a.__parent__ = graph

        nodo_b = CellText('nodo-b', "Contenido B", title="Nodo B")
        nodo_b.__name__ = 'nodo-b'
        nodo_b.__parent__ = graph

        graph.add_node(nodo_a)
        graph.add_node(nodo_b)


        # Relación entre nodos
        edge_ab = CellEdge(name="relacion-ab", title="A → B", from_node=nodo_a, to_node=nodo_b, kind="link")
        graph.add_edge(edge_ab)

        print("Nodo A:", nodo_a.title)
        print("Nodo B:", nodo_b.title)
        print("Edge from:", edge_ab.from_node.title)
        print("Edge to:", edge_ab.to_node.title)
        print("Nodos en grafo-principal:", [n.__name__ for n in graph.nodes])

        cell1 = CellText('intro', "Welcome text", title="Introduction")
        cell1.__parent__ = hc
        hc['intro'] = cell1

        icon = CellIcon('logo', title="Bee Logo", icon="🐝")
        icon.__parent__ = hc
        hc['logo'] = icon

        web = CellWebContent('link', title="Website", url="https://www.wikipedia.org")
        web.__parent__ = hc
        hc['link'] = web

        animation = CellAnimation('bee-dance', url="/static/bee-dance.gif", title="Bee Dance", icon="🐝")
        animation.__parent__ = hc
        hc['bee-dance'] = animation

        # --- Creación de juegos ---
        games_hc = Honeycomb('panal-de-juegos', "Panal de Juegos")
        games_hc.__parent__ = app_root
        app_root['panal-de-juegos'] = games_hc

        game_url = '/static/serpiente/index.html'
        game_cell = CellWebContent(
            name='juego-de-serpiente',
            title='Juego de la Serpiente',
            url=game_url
        )
        game_cell.__parent__ = games_hc
        games_hc['juego-de-serpiente'] = game_cell

        unity_game_name = 'juego-unity'
        if unity_game_name not in games_hc:
            unity_game_url = '/static/WEB/index.html'

            unity_game_cell = CellWebContent(
                name=unity_game_name,
                title='Juego de Unity',
                url=unity_game_url
            )
            unity_game_cell.__parent__ = games_hc
            games_hc[unity_game_name] = unity_game_cell
            print(f"Se agregó el juego '{unity_game_name}'")
        
        zodb_root['app_root'] = app_root
    return zodb_root['app_root']