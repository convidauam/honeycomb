def includeme(config):
    # Escanea todas las vistas de la carpeta
    config.scan(__name__)

def add_cors_headers_tween_factory(handler, registry):
    def cors_tween(request):
        response = handler(request)
        response.headers.update({
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
            'Access-Control-Allow-Headers': 'Origin, Content-Type, Accept, Authorization'
        })
        return response
    return cors_tween
