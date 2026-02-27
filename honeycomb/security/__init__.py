from pyramid.csrf import CookieCSRFStoragePolicy
from .policy import SecurityPolicy

def includeme(config):
    settings = config.get_settings()

    config.set_csrf_storage_policy(CookieCSRFStoragePolicy())
    config.set_default_csrf_options(require_csrf=True)

    config.set_security_policy(SecurityPolicy(settings['auth.secret']))
