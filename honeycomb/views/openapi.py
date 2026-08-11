from cornice.resource import resource

from ..openapi import build_openapi_spec


@resource(path='/openapi/openapi.json', cors_origins=('*',))
class OpenAPISpecResource:
    def __init__(self, request, context=None):
        self.request = request

    def get(self):
        return build_openapi_spec(self.request.application_url)
