import pytest
from honeycomb.models.beehive import BeeHive, HoneycombGraph, CellEdge, CellText
from persistent.list import PersistentList

def test_add_and_remove_nodes():
    beehive = BeeHive()
    nodo1 = CellText(name="nodo1", contents="contenido1")
    nodo2 = CellText(name="nodo2", contents="contenido2")
    edge = CellEdge(name="edge1", title="conexión", from_node=nodo1, to_node=nodo2)

    graph = HoneycombGraph(name="grafo1")
    graph.add_node(nodo1)
    graph.add_node(nodo2)
    graph.add_edge(edge)

    beehive.add_node(nodo1)
    beehive.add_node(graph)

    print("Antes de eliminar:")
    print("NODOS:", list(beehive.__nodes__.keys()))
    print("EDGES:", {k: [e.title for e in v] for k, v in beehive.__edges__.items()})

    # Elimina solo el hijo (nodo1)
    beehive.remove_node_recursively("nodo1")
    print("\nDespués de eliminar nodo1:")
    print("NODOS:", list(beehive.__nodes__.keys()))
    print("EDGES:", {k: [e.title for e in v] for k, v in beehive.__edges__.items()})
    assert "nodo1" not in beehive.__nodes__
    assert "grafo1" in beehive.__nodes__
    assert "grafo1" in beehive.__edges__

    # Vuelve a agregar nodo1 para probar la eliminación del padre
    beehive.add_node(nodo1)
    print("\nAntes de eliminar grafo1:")
    print("NODOS:", list(beehive.__nodes__.keys()))
    print("EDGES:", {k: [e.title for e in v] for k, v in beehive.__edges__.items()})

    # Elimina el padre (grafo1)
    beehive.remove_node_recursively("grafo1")
    print("\nDespués de eliminar grafo1:")
    print("NODOS:", list(beehive.__nodes__.keys()))
    print("EDGES:", {k: [e.title for e in v] for k, v in beehive.__edges__.items()})
    assert "grafo1" not in beehive.__nodes__
    assert "nodo1" not in beehive.__nodes__
    assert "grafo1" not in beehive.__edges__

def test_add_node_with_uuid_key():
    beehive = BeeHive()
    
    # Crear un nodo sin __name__ (o con None)
    nodo1 = CellText(name=None, contents="contenido1")
    nodo2 = CellText(name=None, contents="contenido2")
    edge = CellEdge(name=None, title="conexión-uuid", from_node=nodo1, to_node=nodo2)

    graph = HoneycombGraph(name=None)
    graph.add_node(nodo1)
    graph.add_node(nodo2)
    graph.add_edge(edge)

    beehive.add_node(graph)

    print("\nNODOS EN __nodes__ (UUID):")
    for k, v in beehive.__nodes__.items():
        print(f"  clave: {k}, tipo: {type(v).__name__}")

    print("\nEDGES EN __edges__ (UUID):")
    for k, v in beehive.__edges__.items():
        print(f"  clave: {k}, edges: {[e.title for e in v]}")

    # Verifica que la clave es un UUID (no None ni string vacía)
    assert all(k is not None and str(k) != '' for k in beehive.__nodes__.keys())
    # Verifica que la arista está en el índice de edges
    found = False
    for edges in beehive.__edges__.values():
        if isinstance(edges, PersistentList):
            if any(e.title == "conexión-uuid" for e in edges):
                found = True
    assert found, "La arista con UUID no fue agregada al índice de edges"


def test_sync_graph_edges():
    beehive = BeeHive()
    nodo1 = CellText(name="n1", contents="c1")
    nodo2 = CellText(name="n2", contents="c2")
    edge1 = CellEdge(name="e1", title="A", from_node=nodo1, to_node=nodo2)

    graph = HoneycombGraph(name="g1")
    graph.add_node(nodo1)
    graph.add_node(nodo2)
    graph.add_edge(edge1)

    beehive.add_node(graph)
    # Verifica que la arista está en el índice global
    assert "g1" in beehive.__edges__
    assert any(e.title == "A" for e in beehive.__edges__["g1"])

    print("Antes de sync_graph_edges:", [e.title for e in beehive.__edges__["g1"]])

    # Modifica las aristas internas del grafo
    edge2 = CellEdge(name="e2", title="B", from_node=nodo2, to_node=nodo1)
    graph.edges.append(edge2)

    # Sincroniza el índice global
    beehive.sync_graph_edges(graph)

    print("Después de sync_graph_edges:", [e.title for e in beehive.__edges__["g1"]])

    # Ahora debe contener ambas aristas
    titles = [e.title for e in beehive.__edges__["g1"]]
    assert "A" in titles and "B" in titles
