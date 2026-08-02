"""Documento OpenAPI 3.0 servido en /openapi/openapi.json.

Se mantiene a mano en vez de generarse con cornice-swagger: cornice-swagger
1.0.1 (ultima version, 2021) produce Swagger 2.0, y openapi-client-axios
(la libreria documentada para el frontend/juegos) requiere OpenAPI 3.x
explicitamente, sin conversion automatica.
"""

USER_SCHEMA = {
    "type": "object",
    "properties": {
        "userid": {"type": "string"},
        "displayname": {"type": "string"},
        "username": {"type": "string"},
        "icon": {"type": "string", "nullable": True},
        "background": {"type": "string", "nullable": True},
    },
}

SIPPING_SCHEMA = {
    "type": "object",
    "properties": {
        "userid": {"type": "string"},
        "nodeid": {"type": "string"},
        "interactions": {"type": "integer", "readOnly": True},
        "stats": {"type": "object"},
        "preferences": {"type": "object"},
        "badges": {"type": "array", "items": {"type": "object"}},
        "first_seen": {"type": "string", "format": "date-time"},
        "last_seen": {"type": "string", "format": "date-time"},
    },
}

ERROR_SCHEMA = {
    "type": "object",
    "properties": {"error": {"type": "string"}},
}

UNAUTHORIZED = {
    "description": "No hay sesion autenticada",
    "content": {"application/json": {"schema": ERROR_SCHEMA, "example": {"error": "Unauthorized"}}},
}


def build_openapi_spec(base_url):
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Honeycomb API",
            "version": "1.0.0",
            "description": "API homologada de comunicacion entre los videojuegos de Convida y el backend Honeycomb.",
        },
        "servers": [{"url": base_url}],
        "paths": {
            "/api/v1/honeycombs": {
                "get": {
                    "operationId": "listHoneycombs",
                    "summary": "Lista los honeycombs disponibles",
                    "responses": {
                        "200": {
                            "description": "Lista de honeycombs",
                            "content": {"application/json": {"schema": {
                                "type": "object",
                                "properties": {"honeycombs": {"type": "array", "items": {"type": "object"}}},
                            }}},
                        },
                    },
                },
            },
            "/api/v1/honeycombs/{name}": {
                "get": {
                    "operationId": "getHoneycomb",
                    "summary": "Obtiene un honeycomb como grafo (nodo raiz, hijos y aristas)",
                    "parameters": [{"name": "name", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {
                        "200": {"description": "Grafo del honeycomb", "content": {"application/json": {"schema": {"type": "object"}}}},
                        "404": {"description": "Honeycomb no encontrado", "content": {"application/json": {"schema": ERROR_SCHEMA}}},
                    },
                },
            },
            "/api/v1/node/{node_id}": {
                "get": {
                    "operationId": "getNode",
                    "summary": "Obtiene los datos de un nodo por su id",
                    "parameters": [{"name": "node_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {
                        "200": {"description": "Datos del nodo", "content": {"application/json": {"schema": {"type": "object"}}}},
                        "404": {"description": "Nodo no encontrado", "content": {"application/json": {"schema": ERROR_SCHEMA}}},
                    },
                },
            },
            "/api/v1/me": {
                "get": {
                    "operationId": "getMe",
                    "summary": "Datos de solo lectura del usuario autenticado",
                    "responses": {
                        "200": {"description": "Perfil del usuario", "content": {"application/json": {"schema": USER_SCHEMA}}},
                        "401": UNAUTHORIZED,
                    },
                },
            },
            "/api/v1/drones/{userid}": {
                "get": {
                    "operationId": "getDrone",
                    "summary": "Datos del usuario autenticado (requiere que userid coincida con la sesion)",
                    "parameters": [{"name": "userid", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {
                        "200": {"description": "Perfil del usuario", "content": {"application/json": {"schema": USER_SCHEMA}}},
                        "401": UNAUTHORIZED,
                        "403": {"description": "userid no coincide con la sesion", "content": {"application/json": {"schema": ERROR_SCHEMA}}},
                    },
                },
            },
            "/api/v1/userid": {
                "get": {
                    "operationId": "getUserId",
                    "summary": "userid del usuario autenticado",
                    "responses": {
                        "200": {"description": "userid", "content": {"application/json": {"schema": {
                            "type": "object", "properties": {"userid": {"type": "string"}},
                        }}}},
                        "401": UNAUTHORIZED,
                    },
                },
            },
            "/api/v1/sipping/{nodeid}": {
                "get": {
                    "operationId": "getSippingData",
                    "summary": "Datos homologados del videojuego para el usuario autenticado y un nodo",
                    "parameters": [{"name": "nodeid", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {
                        "200": {"description": "Registro de interaccion", "content": {"application/json": {"schema": SIPPING_SCHEMA}}},
                        "401": UNAUTHORIZED,
                    },
                },
                "post": {
                    "operationId": "saveSippingData",
                    "summary": "Guarda stats/preferences del usuario para un nodo; cuenta una interaccion mas",
                    "parameters": [{"name": "nodeid", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "requestBody": {
                        "content": {"application/json": {"schema": {
                            "type": "object",
                            "properties": {
                                "stats": {"type": "object"},
                                "preferences": {"type": "object"},
                                "replace": {"type": "boolean", "default": False},
                            },
                        }}},
                    },
                    "responses": {
                        "200": {"description": "Registro actualizado", "content": {"application/json": {"schema": SIPPING_SCHEMA}}},
                        "400": {"description": "JSON invalido o stats/preferences no son objetos", "content": {"application/json": {"schema": ERROR_SCHEMA}}},
                        "401": UNAUTHORIZED,
                    },
                },
            },
        },
    }
