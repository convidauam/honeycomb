from pyramid.config import Configurator
from pyramid.session import SignedCookieSessionFactory
from pyramid_zodbconn import get_connection

from .models import appmaker


def root_factory(request):
    conn = get_connection(request)
    return appmaker(conn.root())


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    with Configurator(settings=settings) as config:
        assert settings['auth.secret'], "Please make sure to provide a cryptographically strong secret to store session information"
        session_factory = SignedCookieSessionFactory(settings['auth.secret'],
                                   secure=False,
                                   httponly=True)
        config.set_session_factory(session_factory)
        # config.set_security_policy(SecurityPolicy(secret=settings['auth.secret']))
        config.include('pyramid_jinja2')
        config.include('pyramid_tm')
        config.include('pyramid_retry')
        config.include('pyramid_zodbconn')
        config.include('.routes')
        config.include('.security')
        config.include('cornice')
        config.set_root_factory(root_factory)
        config.scan()
    return config.make_wsgi_app()
