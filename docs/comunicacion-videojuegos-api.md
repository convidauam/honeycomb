# Comunicación de los videojuegos con la API

Referencia: issue #15 "Comunicación de los videojuegos con la API". Los nombres de endpoint aquí están alineados al contrato ya documentado en [convidauam/wikiabeja](https://github.com/convidauam/wikiabeja) (`componentes/API.md`).

Este documento describe el contrato homologado con el que cualquier videojuego de la plataforma se comunica con el backend de Honeycomb. Es el mismo contrato para todos los juegos: mismos endpoints, mismo formato de respuesta, mismo SDK.

Este es el primero de tres hilos de trabajo relacionados: (A, este documento) contrato de endpoints, (B) capa OpenAPI/Swagger para que los juegos generen su cliente automáticamente, (C) login de identidad vía ActivityPub. B y C se documentan por separado cuando se implementen.

## Resumen

| Necesidad | Endpoint | Método | Acceso |
|---|---|---|---|
| Datos del usuario | `/api/v1/me` | GET | solo lectura |
| Interacciones previas con un contenido | `/api/v1/sipping/{nodeid}` | GET | solo lectura (campo `interactions`) |
| Estadísticas del usuario en ese contenido | `/api/v1/sipping/{nodeid}` | GET/POST | lectura/escritura (campo `stats`) |
| Preferencias del usuario en ese contenido | `/api/v1/sipping/{nodeid}` | GET/POST | lectura/escritura (campo `preferences`) |
| Otorgar un logro (lo decide el juego, lo controla el servidor) | `/api/v1/sipping/{nodeid}/badges` | POST | escritura |
| Logros del usuario en cualquier nodo | `/api/v1/achievements` | GET | solo lectura |
| Publicar un logro al Fediverso del usuario | `/api/v1/share` | POST | escritura, opt-in explícito |

Nombre de ruta alineado al contrato ya documentado en la wiki del proyecto ([convidauam/wikiabeja](https://github.com/convidauam/wikiabeja), `componentes/API.md`): `sipping`, no `games`.

`nodeid` es el `uuid` del nodo/celda que representa al videojuego dentro de un Honeycomb (el mismo id que ya expone `GET /api/v1/node/{node_id}`).

Todos los endpoints requieren sesión autenticada (cookie de sesión de Honeycomb). Sin sesión, responden `401`.

## Endpoints

### GET /api/v1/me

Información de solo lectura del usuario autenticado.

Respuesta 200:
```json
{
  "userid": "https://unam.social/users/convida",
  "displayname": "Convida UNAM",
  "username": "convida@unam.social",
  "icon": "/static/bumblebee-512x512.png",
  "background": "/static/honeycomb.png",
  "identities": [{"kind": "fediverse", "value": "https://unam.social/users/convida"}],
  "can_share": true
}
```

- `userid` **no** es el handle: es el identificador canónico de la cuenta (URL del actor de ActivityPub si nació en el Fediverso, o un id opaco `local:<uuid>` si nació como cuenta local). Ver `docs/identidad-activitypub.md` para el modelo completo de identidad.
- `identities`: credenciales vinculadas a esta cuenta (puede tener una de Fediverso, una de usuario/contraseña, o ambas si se vincularon desde `/cuenta`).
- `can_share`: si hay lo necesario (identidad del Fediverso + token de publicación guardado) para que `POST /api/v1/share` funcione ahora mismo.

Sin sesión: `401 {"error": "Unauthorized"}`.

Un videojuego nunca puede modificar estos datos: no existe verbo de escritura para este recurso.

### GET /api/v1/sipping/{nodeid}

Devuelve el registro homologado del usuario autenticado para ese contenido. Si el usuario nunca ha interactuado con el nodo, devuelve valores por defecto (no crea nada).

Respuesta 200:
```json
{
  "userid": "convida@unam.social",
  "nodeid": "juego-de-serpiente",
  "interactions": 3,
  "stats": {"highscore": 950, "level": 4},
  "preferences": {"difficulty": "hard"},
  "badges": [],
  "first_seen": "2026-07-10T18:03:11.482+00:00",
  "last_seen": "2026-07-17T20:11:02.009+00:00"
}
```

- `interactions`: solo lectura. Cuenta cuántas veces el usuario ha hecho POST a este endpoint para este nodo. El servidor lo calcula; el cliente no puede fijarlo.
- `stats`: lectura/escritura libre para el juego (puntajes, niveles, lo que necesite).
- `preferences`: lectura/escritura libre (p. ej. dificultad). Versión mínima: se guarda igual que `stats`, sin validación de esquema todavía. Pensado para ligarse más adelante al sistema de rutas de interacción (`BeePath`); eso queda fuera de este alcance.
- `badges`: logros otorgados en este nodo (`[{id, title, icon, awarded_at}, ...]`). Solo lectura para el juego: se otorgan vía `POST /api/v1/sipping/{nodeid}/badges`, nunca desde este endpoint.

Sin sesión: `401`.

### POST /api/v1/sipping/{nodeid}/badges

Otorga un logro al usuario autenticado para ese nodo. Es el juego quien decide *cuándo* otorgarlo (p. ej. al llegar a cierto puntaje), pero el otorgamiento en sí lo registra el servidor.

Body:
```json
{"id": "high-score-100", "title": "Cien puntos", "icon": "🏆"}
```

`id` lo elige el juego (no es un UUID generado por el servidor: son los juegos los que saben qué logros existen). `title` es obligatorio; `icon` es opcional. Idempotente: otorgar el mismo `id` dos veces no lo duplica ni cambia su `awarded_at` original.

Respuesta 200: el registro `sipping` completo, con el badge ya incluido en `badges` (mismo formato que `GET /api/v1/sipping/{nodeid}`).

Errores: `401` sin sesión, `400` si falta `id`/`title` o `icon` no es texto.

### GET /api/v1/achievements

Todos los logros del usuario autenticado, en cualquier nodo (su vitrina).

Respuesta 200:
```json
{"achievements": [{"id": "high-score-100", "title": "Cien puntos", "icon": "🏆", "awarded_at": "...", "nodeid": "juego-de-serpiente"}]}
```

### POST /api/v1/share

Publica un logro ya otorgado como una nota en el Fediverso del usuario, vía ActivityPub C2S (su propio outbox) — nunca automático, siempre una acción explícita (del usuario o disparada por el juego con confirmación del usuario).

Body:
```json
{"nodeid": "juego-de-serpiente", "badge_id": "high-score-100", "message": "opcional"}
```

Si `message` falta, se genera uno automático. Errores: `401` sin sesión, `400` si faltan campos o la cuenta no tiene forma de publicar (ver `can_share` en `/api/v1/me` para saber de antemano si conviene ofrecer este botón), `404` si el usuario nunca tiene ese logro en ese nodo, `502` si la instancia del Fediverso rechaza la publicación.

### POST /api/v1/sipping/{nodeid}

Guarda `stats` y/o `preferences` del usuario autenticado para ese nodo, y cuenta una interacción más.

Body:
```json
{
  "stats": {"highscore": 950},
  "preferences": {"difficulty": "hard"},
  "replace": false
}
```

Todos los campos son opcionales. `stats`/`preferences`, si vienen, deben ser objetos JSON (no listas ni escalares).

- Por defecto (`replace` ausente o `false`) el servidor fusiona: las claves nuevas se agregan o sobrescriben, las claves existentes que no se mencionan se conservan.
- Con `"replace": true`, `stats`/`preferences` se reemplazan por completo con lo enviado (aplica a ambos campos juntos).
- El servidor incrementa `interactions` en 1 en cada POST exitoso, sin importar qué mande el cliente. Si el body incluye `"interactions": 999` o cualquier otro campo no reconocido, se ignora.
- `userid` y `nodeid` los determina el servidor (sesión + URL), nunca el body: un usuario no puede leer ni escribir datos de otro usuario.

Respuesta 200: el registro completo actualizado (mismo formato que el GET).

Errores:
- `401` sin sesión.
- `400` si el body no es JSON válido, o si `stats`/`preferences` no son objetos.

No requiere CSRF token (`require_csrf=False`): es una API JSON same-origin protegida por cookie de sesión más el gate de autenticación, no un formulario HTML.

### Endpoints previos (compatibilidad)

`GET /api/v1/drones/{userid}` y `GET /api/v1/userid` ya estaban documentados en la wiki del proyecto y se dejan intactos; `/api/v1/me` se agrega como alias de conveniencia (mismo dato, sin tener que mandar el `userid` en la URL, sin riesgo de 403 por mismatch). Cualquiera de los dos sirve para el contrato homologado.

Nota sobre `sipping`: la ruta ya estaba documentada en la wiki, pero el borrador original ahí descrito usaba un diccionario en memoria (se perdía al reiniciar el servidor). Esta implementación mantiene la misma ruta y el mismo propósito, pero con persistencia real en ZODB y separación explícita de solo lectura/lectura-escritura (ver más abajo).

## Seguridad

- Autenticación obligatoria: todos los endpoints de esta sección devuelven `401` sin sesión válida.
- Los datos de juego se leen/escriben siempre con el `userid` de la sesión, nunca con un `userid` de la URL o del body: no hay forma de leer o modificar datos de otro usuario (sin IDOR).
- `interactions` y `badges` los controla exclusivamente el servidor.
- `cors_origins=('*',)` se mantiene igual que en los endpoints existentes, asumiendo que los juegos se sirven desde el mismo origen (`/static/...`). Si algún juego se sirve desde otro dominio, hay que cambiar esto por una lista explícita de orígenes y habilitar credenciales en CORS; no está resuelto en este alcance.
- Límite de tamaño: `stats`/`preferences` aceptan como máximo `honeycomb.max_game_payload_keys` claves por objeto (configurable por quien administra la instancia; vacío/0 = sin límite, que es el valor de fábrica).

## Persistencia

Los registros (`GameData`) se guardan en ZODB, dentro de la raíz (`BeeHive.__game_data__`), indexados por `userid` y luego por `nodeid`. Sobreviven reinicios del servidor (a diferencia del borrador anterior, que usaba un diccionario en memoria).

## SDK para videojuegos

`honeycomb/static/sdk/honeycomb.js` es la forma homologada de hablar con estos endpoints: mismo código para todos los juegos.

```html
<script src="/static/sdk/honeycomb.js"></script>
<script>
  Honeycomb.connect().then(function (hc) {
    console.log(hc.user.displayname);

    hc.load('juego-de-serpiente').then(function (data) {
      console.log('highscore previo:', data.stats.highscore);
    });

    hc.save('juego-de-serpiente', { stats: { highscore: 950 } });
  });
</script>
```

- `Honeycomb.connect(nodeId?)`: llama a `/me`, devuelve una sesión con `.user` (incluye `identities`/`can_share`, ver arriba). Si no se pasa `nodeId`, intenta detectarlo de `?nodeid=` en la URL del juego o de `data-node-id` en su propio `<script>` tag.
- `hc.load(nodeId?)`: GET de `/sipping/{nodeid}`. Usa el `nodeId` de conexión si no se pasa uno explícito.
- `hc.save(nodeId?, data)`: POST a `/sipping/{nodeid}`. También acepta `hc.save(data)` usando el `nodeId` de conexión.
- `hc.awardBadge(nodeId?, badge)`: POST a `/sipping/{nodeid}/badges`, otorga un logro.
- `hc.achievements()`: GET de `/achievements`, todos los logros del usuario en cualquier nodo.
- `hc.share(nodeId, badgeId, message?)`: POST a `/share`, publica un logro al Fediverso. Revisar `hc.user.can_share` antes de mostrar el botón.

Pendiente (fuera de este alcance): la plataforma todavía no inyecta automáticamente `?nodeid=` en la URL de cada juego embebido; por ahora el `nodeId` debe pasarse explícitamente a `connect`/`load`/`save`, o el juego debe construirse conociendo su propio nodeid.

## Descubrimiento automático (OpenAPI + openapi-client-axios)

Además del SDK, la API se describe en `GET /openapi/openapi.json` (OpenAPI 3.0.3), tal como lo documenta la wiki del proyecto en `Conexión_Cliente_Servidor.md`. Cualquier juego puede generar un cliente tipado con [openapi-client-axios](https://openapistack.co/docs/openapi-client-axios/intro/) y llamar por `operationId` en vez de armar URLs a mano:

```js
const OpenAPIClientAxios = require('openapi-client-axios').default;

const api = new OpenAPIClientAxios({
  definition: 'http://localhost:6543/openapi/openapi.json',
  axiosConfigDefaults: { baseURL: 'http://localhost:6543', withCredentials: true },
});
const client = await api.init();

const { data } = await client.getSippingData({ nodeid: 'juego-de-serpiente' });
await client.saveSippingData({ nodeid: 'juego-de-serpiente' }, { stats: { highscore: 950 } });
```

`operationId` por endpoint: `listHoneycombs`, `getHoneycomb`, `getNode`, `getMe`, `getDrone`, `getUserId`, `getSippingData`, `saveSippingData`, `awardBadge`, `getAchievements`, `shareAchievement`.

Nota: el login (Fediverso, usuario/contraseña, registro, vincular/desvincular credenciales) **no** está en este spec a propósito — son formularios HTML con redirección (`303`), no una API JSON pensada para clientes programáticos. Un juego nunca inicia sesión por sí mismo: el jugador ya llega autenticado por haber entrado a la plataforma en el navegador. Ver `docs/identidad-activitypub.md`.

**Nota de implementación:** el spec se mantiene a mano en `honeycomb/openapi.py`, no se genera con `cornice-swagger`. Se probó `cornice-swagger` (única versión existente, 1.0.1 de 2021) y sí corre con cornice 6.1/Python 3.12, pero genera **Swagger 2.0**, y `openapi-client-axios` requiere **OpenAPI 3.x** explícitamente (sin conversión automática). Mantener el spec a mano también evita depender de un paquete sin mantenimiento desde 2021 y da control total sobre los ejemplos de respuesta (cornice-swagger, sin esquemas `colander` en cada recurso, solo documenta `"UNDOCUMENTED RESPONSE"`). Verificado end-to-end con `openapi-client-axios` real contra el servidor local: generación del cliente, 401 sin sesión, y el flujo completo de `sipping` (GET default → POST → interactions incrementado).

## Nota sobre las pruebas

`tests/test_api_games.py` usa el fixture `testapp` (ver `tests/conftest.py`). Ese fixture pasa `tm.active: True` en el entorno de cada request, lo cual hace que `pyramid_tm` no gestione la transacción de esa request; quien la cierra es el callback de cierre de conexión de `pyramid_zodbconn`, que siempre hace `abort()`. Consecuencia: cada request HTTP dentro de un test corre sobre ZODB en un estado vacío, y ninguna escritura sobrevive de un request al siguiente, ni dentro del mismo test. Por eso las pruebas HTTP en `test_api_games.py` solo verifican lo que un único request/response puede demostrar (autenticación, forma de la respuesta, que un POST cuenta como 1a interacción, validación de payload). El comportamiento que depende de varias llamadas (fusión de `stats` entre POSTs sucesivos, conteo acumulado de `interactions`) está cubierto en `tests/test_models.py`, probando `GameData`/`BeeHive.get_game_data` directamente sin pasar por HTTP.

## Pendiente / fuera de alcance

- Preferencias ligadas al sistema de rutas de interacción (`BeePath`): quedó como versión mínima (campo libre `preferences`), sin modelar `sequence`/`required`/`granted` todavía.
- Inyección automática del `nodeid` del juego embebido desde la plataforma.
- Integrar el SDK en un juego real de ejemplo (p. ej. Serpiente).
