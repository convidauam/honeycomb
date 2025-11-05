from pyramid.authentication import AuthTktCookieHelper
from pyramid.request import RequestLocalCache
from pyramid.security import Allowed, Denied

from .. import models


class SecurityPolicy:
    def __init__(self, secret):
        self.authtkt = AuthTktCookieHelper(secret)
        self.identity_cache = RequestLocalCache(self.load_identity)

    def load_identity(self, request):
        identity = self.authtkt.identify(request)
        
        if identity is None:
            return None

        userid = identity['userid']
        
        if userid == 'convida@unam.social':
            user = {
                'userid': userid,
                'displayname': 'Convida UNAM',
                'username': 'convida',
                'icon': '/static/convida-icon.png',
                'background': '/static/convida-bg.png',
            }
        else:
            user = {
                'userid': userid,
                'displayname': 'Anonymous Bee',
                'username': 'queen_bee',
                'icon': '/static/bumblebee-16x16.png',
                'background': '',
            }
        return user

    def identity(self, request):
        return self.identity_cache.get_or_create(request)

    def authenticated_userid(self, request):
        user = self.identity(request)
        if user is not None:
            return user['userid']

    def remember(self, request, userid, **kw):
        return self.authtkt.remember(request, userid, **kw)

    def forget(self, request, **kw):
        return self.authtkt.forget(request, **kw)

    def permits(self, request, context, permission):
        identity = self.identity(request)

        if identity is None:
            return Denied("You need to sign in to view this contents")
        elif permission == 'read':
            return Allowed('Access granted for user %s', identity['username'])
        else:
            return Denied("You are not allowed to access this resource")
