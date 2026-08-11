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

IDENTITY_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["fediverse", "password"], "description": "Tipo de credencial vinculada"},
        "value": {"type": "string", "description": "URL del actor (fediverse) o nombre de usuario (password)"},
    },
}

ME_SCHEMA = {
    "allOf": [USER_SCHEMA, {
        "type": "object",
        "properties": {
            "identities": {
                "type": "array", "items": IDENTITY_SCHEMA,
                "description": "Credenciales vinculadas a esta cuenta (Fediverso y/o usuario+contrasena)",
            },
            "can_share": {
                "type": "boolean",
                "description": "Si hay lo necesario (identidad del Fediverso + token) para publicar logros ahora mismo",
            },
        },
    }],
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

BADGE_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "title": {"type": "string"},
        "icon": {"type": "string", "nullable": True},
        "awarded_at": {"type": "string", "format": "date-time"},
    },
}

ACHIEVEMENT_SCHEMA = {
    "allOf": [BADGE_SCHEMA, {"type": "object", "properties": {"nodeid": {"type": "string"}}}],
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
                    "summary": "Datos de solo lectura del usuario autenticado, incluyendo sus credenciales vinculadas",
                    "responses": {
                        "200": {"description": "Perfil del usuario", "content": {"application/json": {"schema": ME_SCHEMA}}},
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
            "/api/v1/sipping/{nodeid}/badges": {
                "post": {
                    "operationId": "awardBadge",
                    "summary": "Otorga un logro al usuario autenticado para un nodo (controlado por el juego)",
                    "parameters": [{"name": "nodeid", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {
                            "type": "object",
                            "required": ["id", "title"],
                            "properties": {
                                "id": {"type": "string", "description": "Identificador del logro, elegido por el juego"},
                                "title": {"type": "string"},
                                "icon": {"type": "string", "nullable": True},
                            },
                        }}},
                    },
                    "responses": {
                        "200": {"description": "Registro actualizado con el logro otorgado", "content": {"application/json": {"schema": SIPPING_SCHEMA}}},
                        "400": {"description": "id/title faltantes o invalidos", "content": {"application/json": {"schema": ERROR_SCHEMA}}},
                        "401": UNAUTHORIZED,
                    },
                },
            },
            "/api/v1/achievements": {
                "get": {
                    "operationId": "getAchievements",
                    "summary": "Todos los logros del usuario autenticado, en cualquier nodo",
                    "responses": {
                        "200": {"description": "Lista de logros", "content": {"application/json": {"schema": {
                            "type": "object",
                            "properties": {"achievements": {"type": "array", "items": ACHIEVEMENT_SCHEMA}},
                        }}}},
                        "401": UNAUTHORIZED,
                    },
                },
            },
            "/api/v1/share": {
                "post": {
                    "operationId": "shareAchievement",
                    "summary": "Publica un logro ya otorgado como una nota en el Fediverso del usuario (ActivityPub C2S)",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {
                            "type": "object",
                            "required": ["nodeid", "badge_id"],
                            "properties": {
                                "nodeid": {"type": "string"},
                                "badge_id": {"type": "string"},
                                "message": {"type": "string", "description": "Mensaje personalizado; si falta, se genera uno automatico"},
                            },
                        }}},
                    },
                    "responses": {
                        "200": {"description": "Publicado", "content": {"application/json": {"schema": {
                            "type": "object",
                            "properties": {"status": {"type": "string"}, "activity": {"type": "object"}},
                        }}}},
                        "400": {"description": "Datos invalidos o no hay token de publicacion disponible", "content": {"application/json": {"schema": ERROR_SCHEMA}}},
                        "401": UNAUTHORIZED,
                        "404": {"description": "El usuario no tiene ese logro en ese nodo", "content": {"application/json": {"schema": ERROR_SCHEMA}}},
                        "502": {"description": "La instancia del Fediverso rechazo la publicacion", "content": {"application/json": {"schema": ERROR_SCHEMA}}},
                    },
                },
            },
        },
    }
