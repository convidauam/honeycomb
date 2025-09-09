def includeme(config):
    config.add_static_view('static', 'static', cache_max_age=3600)
    config.add_route('grafo-principal-json', '/grafo-principal/json')
    config.add_route('edit_node', '/nodo/{id}/edit')
    config.add_route('import_json', '/import-json')
    config.add_route('create_node', '/nodo/nuevo')
