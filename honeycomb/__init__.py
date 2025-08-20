from pyramid.config import Configurator
from pyramid_zodbconn import get_connection

from .models import appmaker


def root_factory(request):
    conn = get_connection(request)
    return appmaker(conn.root())


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    with Configurator(settings=settings) as config:
        config.include('pyramid_jinja2')
        config.include('pyramid_tm')
        config.include('pyramid_retry')
        config.include('pyramid_zodbconn')

        # rutas que ya tenemos
        config.include('.routes')

        # incluir a cornice
        config.include('cornice')

        # incluir vistas incluyendo la prueba hello.py
        config.include('.views')


        config.add_tween('honeycomb.views.add_cors_headers_tween_factory')
        
        config.set_root_factory(root_factory)
        config.scan()
    return config.make_wsgi_app()
