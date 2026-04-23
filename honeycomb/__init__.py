from pyramid.config import Configurator
from pyramid.session import SignedCookieSessionFactory
from pyramid_zodbconn import get_connection

from .models import appmaker


def _first_proxy_header(environ, name):
    value = environ.get(name, "")
    if not value:
        return None
    first = value.split(",")[0].strip()
    return first or None


def _normalize_prefix(prefix):
    if prefix is None:
        return None
    clean = prefix.strip()
    if not clean:
        return None
    clean = "/" + clean.strip("/")
    return "" if clean == "/" else clean


def _host_has_explicit_port(host):
    if host.startswith("["):
        return "]:" in host
    return ":" in host


def _server_name_from_host(host):
    if host.startswith("["):
        end = host.find("]")
        if end != -1:
            return host[1:end]
    return host.split(":", 1)[0]


class ForwardedHeadersMiddleware:
    """Apply proxy headers so Pyramid generates URLs with external prefix/scheme."""

    def __init__(self, app):
        self.app = app
        self.registry = getattr(app, "registry", None)

    def __call__(self, environ, start_response):
        proto = _first_proxy_header(environ, "HTTP_X_FORWARDED_PROTO")
        if proto:
            environ["wsgi.url_scheme"] = proto

        host = _first_proxy_header(environ, "HTTP_X_FORWARDED_HOST")
        port = _first_proxy_header(environ, "HTTP_X_FORWARDED_PORT")
        if host:
            host_value = host
            if port and not _host_has_explicit_port(host):
                is_default_port = (proto == "http" and port == "80") or (proto == "https" and port == "443")
                if not is_default_port:
                    host_value = f"{host}:{port}"
            environ["HTTP_HOST"] = host_value
            environ["SERVER_NAME"] = _server_name_from_host(host_value)
        if port:
            environ["SERVER_PORT"] = port

        prefix = _normalize_prefix(_first_proxy_header(environ, "HTTP_X_FORWARDED_PREFIX"))
        if prefix is not None:
            current_script = (environ.get("SCRIPT_NAME", "") or "").rstrip("/")
            if prefix and not current_script.endswith(prefix):
                script_name = f"{current_script}{prefix}" if current_script else prefix
            else:
                script_name = current_script
            environ["SCRIPT_NAME"] = script_name

            # Keep routing stable even if an upstream sends PATH_INFO with the prefix.
            path_info = environ.get("PATH_INFO", "") or ""
            if prefix and path_info.startswith(prefix):
                stripped = path_info[len(prefix):]
                environ["PATH_INFO"] = stripped if stripped.startswith("/") else f"/{stripped}" if stripped else "/"

        return self.app(environ, start_response)

    def __getattr__(self, name):
        return getattr(self.app, name)


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
    app = config.make_wsgi_app()

    use_proxy_headers = settings.get('honeycomb.use_proxy_headers', 'false').lower() == 'true'
    if use_proxy_headers:
        return ForwardedHeadersMiddleware(app)
    
    return app
