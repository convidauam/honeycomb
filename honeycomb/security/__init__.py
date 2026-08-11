from pyramid.csrf import CookieCSRFStoragePolicy
from .policy import SecurityPolicy
from . import fediverse, local_accounts

def includeme(config):
    settings = config.get_settings()

    config.set_csrf_storage_policy(CookieCSRFStoragePolicy())
    config.set_default_csrf_options(require_csrf=True)

    config.set_security_policy(SecurityPolicy(settings['auth.secret']))
    fediverse.configure_registration_rate_limiter(settings)
    local_accounts.configure_rate_limiters(settings)
