import json
import uuid
from .beehive import *

# Contenido del JSON para la carga inicial
initial_graph_json = """
{
  "nodes": [
    { "id": "node-4d550c14-aa4f-47f2-af71-5b850f76f48d", "data": { "label": "Huevo (2n) fecundado" } },
    { "id": "node-dd5892f6-fee6-4ee2-a835-6e63c79dd16c", "data": { "label": "Reina inseminada y con óvulos" } },
    { "id": "node-f38869ef-a442-472e-b012-4a47f6dc9412", "data": { "label": "Huevo (n) no fecundado" } },
    { "id": "node-90aeec3c-a481-4f5b-95ec-22436264629d", "data": { "label": "Zángano (n) haploide" } },
    { "id": "node-395a0990-408a-4459-a8e2-b74100a3f295", "data": { "label": "Espermatozoides" } },
    { "id": "node-9cb93970-e971-4530-949e-b3d94802f1b5", "data": { "label": "reina (2n) diploide" } },
    { "id": "node-ac79e039-af75-42c8-8c26-ada689894dfc", "data": { "label": "Obrera (2n) diploide" } },
    { "id": "node-142e860a-4c6d-4d41-a2d6-422f2e384fa3", "data": { "label": "Óvulos" } },
    { "id": "node-4c9a3ad4-c66b-44ac-a141-04ad6ee2d8ff", "data": { "label": "Acoplamiento" } }
  ],
  "edges": [
    { "source": "node-f38869ef-a442-472e-b012-4a47f6dc9412", "target": "node-90aeec3c-a481-4f5b-95ec-22436264629d", "label": "desarrollo por partenogénesis arrenotóquica / alimentación: para zángano" },
    { "source": "node-90aeec3c-a481-4f5b-95ec-22436264629d", "target": "node-395a0990-408a-4459-a8e2-b74100a3f295", "label": "gametogénesis" },
    { "source": "node-4d550c14-aa4f-47f2-af71-5b850f76f48d", "target": "node-9cb93970-e971-4530-949e-b3d94802f1b5", "label": "desarrollo/alimentación: jalea real" },
    { "source": "node-4d550c14-aa4f-47f2-af71-5b850f76f48d", "target": "node-ac79e039-af75-42c8-8c26-ada689894dfc", "label": "desarrollo/ alimentación: pan de abeja" },
    { "source": "node-9cb93970-e971-4530-949e-b3d94802f1b5", "target": "node-142e860a-4c6d-4d41-a2d6-422f2e384fa3", "label": "gametogénesis" },
    { "source": "node-142e860a-4c6d-4d41-a2d6-422f2e384fa3", "target": "node-4c9a3ad4-c66b-44ac-a141-04ad6ee2d8ff", "label": null },
    { "source": "node-395a0990-408a-4459-a8e2-b74100a3f295", "target": "node-4c9a3ad4-c66b-44ac-a141-04ad6ee2d8ff", "label": null },
    { "source": "node-9cb93970-e971-4530-949e-b3d94802f1b5", "target": "node-4c9a3ad4-c66b-44ac-a141-04ad6ee2d8ff", "label": null },
    { "source": "node-90aeec3c-a481-4f5b-95ec-22436264629d", "target": "node-4c9a3ad4-c66b-44ac-a141-04ad6ee2d8ff", "label": null },
    { "source": "node-4c9a3ad4-c66b-44ac-a141-04ad6ee2d8ff", "target": "node-dd5892f6-fee6-4ee2-a835-6e63c79dd16c", "label": null },
    { "source": "node-dd5892f6-fee6-4ee2-a835-6e63c79dd16c", "target": "node-4d550c14-aa4f-47f2-af71-5b850f76f48d", "label": "postura con fecundación" },
    { "source": "node-dd5892f6-fee6-4ee2-a835-6e63c79dd16c", "target": "node-f38869ef-a442-472e-b012-4a47f6dc9412", "label": "postura sin fecundación" }
  ]
}
"""

def appmaker(zodb_root):
    if 'app_root' not in zodb_root:
        app_root = BeeHive()

        # --- Crear y configurar el grafo principal ---
        grafo_principal = HoneycombGraph(
            name='panal-de-juegos',
            title="Ciclo Biológico de las Abejas"
        )

        # --- Cargar datos desde el JSON ---
        graph_data = json.loads(initial_graph_json)
        
        # Diccionario para mapear ID de JSON a objeto de nodo de Python
        nodes_map = {}

        # 1. Crear todos los objetos de nodo
        for node_data in graph_data['nodes']:
            json_id = node_data['id']
            node_obj = CellText(
                name=json_id,
                title=node_data['data']['label'],
                contents=node_data['data']['label'] 
            )
            node_obj.__parent__ = grafo_principal 
            
            # Añadir al grafo principal y al mapa temporal
            grafo_principal.add_node(node_obj)
            nodes_map[json_id] = node_obj

        # 2. Crear todos los objetos de arista (edge)
        for edge_data in graph_data['edges']:
            source_id = edge_data['source']
            target_id = edge_data['target']
            
            from_node = nodes_map.get(source_id)
            to_node = nodes_map.get(target_id)
            
            if from_node and to_node:
                edge_obj = CellEdge(
                    name=f"edge-{uuid.uuid4()}", 
                    title=edge_data.get('label', ''), 
                    from_node=from_node,
                    to_node=to_node,
                    kind="default"
                )
                grafo_principal.add_edge(edge_obj)

        # --- Asignar el padre al grafo y luego añadir al root ---
        grafo_principal.__parent__ = app_root
        app_root['panal-de-juegos'] = grafo_principal
        
        print(f"DEBUG - Grafo '{grafo_principal.title}' cargado con {len(grafo_principal.nodes)} nodos y {len(grafo_principal.edges)} aristas.")

        zodb_root['app_root'] = app_root
        
    return zodb_root['app_root']
