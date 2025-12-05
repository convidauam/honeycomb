from pyramid.authentication import AuthTktCookieHelper
from pyramid.request import RequestLocalCache
from pyramid.security import Allowed, Denied

from ..models.axes import CellBuilder
from ..models.users import DroneUser


USERS = {
    'convida@unam.social': DroneUser('convida@unam.social', 'Convida UNAM', 'convida@unam.social', '/static/convida-icon.png', '/static/convida-bg.png'),
}

class SecurityPolicy:
    def __init__(self, secret):
        self.authtkt = AuthTktCookieHelper(secret)
        self.identity_cache = RequestLocalCache(self.load_identity)

    def load_identity(self, request):
        identity = self.authtkt.identify(request)
        
        if identity is None:
            return None

        userid = identity['userid']

        if userid not in USERS:
            return None

        identity = USERS[userid]

        return identity

    def identity(self, request):
        return self.identity_cache.get_or_create(request)

    def authenticated_userid(self, request):
        user = self.identity(request)
        if user is not None:
            return user.userid
        return None

    def remember(self, request, userid, **kw):
        return self.authtkt.remember(request, userid, **kw)

    def forget(self, request, **kw):
        return self.authtkt.forget(request, **kw)

    def permits(self, request, context, permission):
        identity = self.identity(request)

        if identity is None:
            return Denied("You need to sign in to view this contents")
        elif permission == 'read':
            if CellBuilder.has_access(context, identity):
                return Allowed('Access granted for user %s', identity['username'])
            else:
                return Denied("You are not allowed to access this resource")
        else:
            return Denied("You are not allowed to access this resource")
