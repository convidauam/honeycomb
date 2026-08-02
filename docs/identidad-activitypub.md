# Identidad de usuario vía ActivityPub (Fediverso)

Segundo hilo relacionado con el issue #15: el usuario se autentica con la red social del Fediverso que elija ("Inicia sesión con el Fediverso"), en vez de un usuario fijo. Referencia de diseño: `docs/comunicacion-videojuegos-api.md` (hilo del contrato de endpoints) y la wiki [convidauam/wikiabeja](https://github.com/convidauam/wikiabeja).

## Qué es y qué no es

Esto es un **cliente OAuth 2.0 identity-only** contra la API estilo Mastodon que exponen la mayoría de los servidores del Fediverso. Honeycomb **no** implementa federación ActivityPub (no hay inbox/outbox, firmas HTTP, entrega asíncrona): solo resuelve una instancia, registra una app OAuth ahí, corre el flujo de `authorization_code`, y lee el perfil vía `verify_credentials`.

En la práctica, "la red social que el usuario elija" significa **cualquier instancia compatible con la API de cliente de Mastodon** (Mastodon, Pleroma/Akkoma, GoToSocial, Pixelfed). Misskey/Firefish usan otro mecanismo (MiAuth) y no funcionan sin trabajo adicional; servidores que solo federan sin exponer esa API tampoco.

Se eligió **entrada abierta**: cualquier dominio que el usuario escriba, no una lista blanca. Esto obliga a que el guard anti-SSRF sea estricto desde el día uno (ver abajo), ya que el backend hace peticiones salientes a un host arbitrario elegido por el usuario.

## Flujo de login

1. `GET /login` — renderiza el formulario (`login.jinja2`), pide el handle (`usuario@instancia`).
2. `POST /api/v1/auth/login` (requiere CSRF, igual que el resto de la app):
   - Parsea el handle → `(username, domain)`.
   - Si el dominio nunca se ha visto: confirma con `/.well-known/nodeinfo` que hay un servidor real ahí (evita gastar un registro de app contra cualquier dominio).
   - Intenta `/.well-known/oauth-authorization-server` (RFC 8414) para saber si la instancia soporta el scope `profile` (Mastodon 4.3+) y PKCE S256; si no, cae a `read:accounts` sin PKCE.
   - Registra la app vía `POST /api/v1/apps` (o reusa la registrada antes para ese dominio, cacheada en ZODB) y genera un `state` de un solo uso.
   - Redirige (303) a `https://<dominio>/oauth/authorize?...`.
3. El usuario aprueba en **su propia instancia** (fuera de Honeycomb).
4. `GET /api/v1/auth/callback`:
   - Valida `state` (comparación timing-safe, un solo uso).
   - Intercambia el `code` por un `access_token` en `POST /oauth/token`.
   - Lee el perfil con `GET /api/v1/accounts/verify_credentials`.
   - Mapea el perfil a `DroneUser`, lo guarda/actualiza en ZODB, y crea la sesión (`remember()`, misma cookie firmada de siempre).
   - El `access_token` se descarta (no se persiste): login-only, no se guardan credenciales de terceros.

`client_id`/`client_secret` de la instancia viajan también en la sesión (de un solo uso, se limpian en el callback) para que este flujo específico no dependa de releer la caché de ZODB en el siguiente request; la caché en ZODB solo acelera futuros logins al mismo dominio.

## Mapeo a DroneUser

| Campo DroneUser | Origen |
|---|---|
| `userid` | `account.uri` (Actor URI de ActivityPub) si está presente; si no, `"{dominio}#{account.id}"`. Nunca el handle: los usernames se pueden reciclar. |
| `display_name` | `account.display_name` |
| `username` | handle completo (`usuario@dominio`) |
| `icon` | `account.avatar` |
| `background` | `account.header` |

`DroneUser` es ahora `Persistent` (antes era un objeto plano guardado en un dict hardcodeado en memoria) y vive en `BeeHive.__users__` (ZODB), indexado por `userid`. `BeeHive.__oauth_apps__` cachea `{client_id, client_secret}` por dominio.

## Seguridad

- **Guard anti-SSRF en toda llamada saliente** (nodeinfo, oauth metadata, registro de app, intercambio de token, verify_credentials): solo https, se resuelve el host y se rechaza si cualquier IP resuelta es privada/loopback/link-local/multicast/reservada, sin seguir redirects automáticos (se revalida cada salto a mano, hasta 3), con timeout. Ver `honeycomb/security/fediverse.py`.
- `state` aleatorio de un solo uso, comparación timing-safe.
- PKCE S256 cuando la instancia lo soporta.
- `next` (a dónde redirigir tras login) se sanitiza: solo rutas relativas de un segmento, nunca `//host` (anti open-redirect).
- El límite de confianza es la **instancia**, no el usuario individual: una instancia hostil podría afirmar cualquier username local suyo. Esto es inherente al modelo, no algo que este código pueda resolver.
- El registro de app por dominio se cachea (no se re-registra en cada login al mismo dominio).
- **Rate limit en `register_app`**: máximo 5 registros por dominio y 30 en total cada 10 minutos (en memoria de proceso, `honeycomb/security/fediverse.py:_RegistrationRateLimiter`). Evita que alguien haga un loop registrando apps contra muchos dominios distintos o reintentando el mismo.
- **Denylist configurable**: `fediverse.denylist` en el `.ini` (espacio-separado). Un dominio en la lista nunca llega a registrar una app ni a redirigir — se corta justo después de parsear el handle, antes de cualquier llamada de red.

## `redirect_uri` detrás del reverse proxy

El `redirect_uri` que se registra con la instancia remota se construye con `request.application_url` (no `request.host_url`), porque en producción el backend queda montado bajo un prefijo (`/backend/`, según `reverse_proxy/conf.d/nginx.conf` de `convida_deployment`) que nginx quita antes de reenviar la petición al contenedor. `host_url` solo trae `scheme://host:puerto`; `application_url` además incluye ese prefijo (via `SCRIPT_NAME`, que `ForwardedHeadersMiddleware` en `honeycomb/__init__.py` arma a partir del header `X-Forwarded-Prefix` que sí manda ese nginx). Se verificó simulando el prefijo `/backend` en un request de prueba: tanto el `redirect_uri` del login como el `servers[0].url` de `/openapi/openapi.json` quedan correctos (`https://convida.cua.uam.mx/backend/...`). Depende de que `honeycomb.use_proxy_headers = true` esté activo en `production.ini` (ya lo está) y de que el proxy real siga mandando esos headers tal como los manda el `nginx.conf` revisado.

## Verificado en vivo contra unam.social

`convida@unam.social` es una instancia real: **Pleroma 2.9.1** (no Mastodon), cuenta "Proyecto Convida". Se verificó en vivo, sin mocks:

- `discover_nodeinfo('unam.social')` → responde con software Pleroma 2.9.1 real, confirma que expone `mastodon_api`.
- `discover_oauth_metadata('unam.social')` → `None` (Pleroma 2.9.1 no expone RFC 8414), cae correctamente a scope `read:accounts` sin PKCE.
- `register_app` → registro real contra unam.social, devolvió `client_id`/`client_secret` reales.
- La `authorize_url` construida devuelve `200` con el login real de unam.social.
- El guard SSRF rechaza correctamente `localhost`.

No se completó el último tramo (aprobar el login como `convida@unam.social` y terminar el intercambio de código) porque requiere credenciales reales de esa cuenta, que no están disponibles aquí; ese tramo sí está cubierto por pruebas automatizadas contra una instancia fake (ver abajo).

## Pruebas

- `tests/test_fediverse.py`: funciones puras de `honeycomb/security/fediverse.py` (parseo de handle, guard SSRF con `socket.getaddrinfo` mockeado, PKCE, elección de scope, mapeo a `DroneUser`).
- `tests/test_auth_fediverse.py`: las vistas completas (`/login`, `/api/v1/auth/login`, `/api/v1/auth/callback`) contra una instancia fake monkeypatcheada — handle inválido, dominio sin nodeinfo, `state` faltante/incorrecto, `code` faltante, flujo completo exitoso, reuso de la app cacheada en el segundo login al mismo dominio.
- El fixture `fediverse_stub` (en `tests/conftest.py`) además puentea `BeeHive.get_user`/`upsert_user`/`get_oauth_app`/`set_oauth_app` por fuera de ZODB, **solo para pruebas**: el fixture `testapp` aborta cada request en su propia transacción (ver nota en `docs/comunicacion-videojuegos-api.md`), así que sin este puente un usuario logueado en un request no existiría todavía para el siguiente. El código de producción usa ZODB en todo momento; esto se confirmó con la verificación en vivo de arriba.

## Pendiente / fuera de alcance

- Verificación inversa de WebFinger contra suplantación (queda como hardening de fase 2; el token OAuth de la instancia ya es el ancla de confianza del MVP).
- Refresco de perfil (hoy se sobrescribe en cada login; no hay política de "cada cuánto" releer avatar/display_name).
- Manejo especial de instancias que limitan o deniegan el registro de apps.
- Cualquier forma de federación ActivityPub real (inbox/outbox, firmas HTTP, publicar/seguir en nombre del usuario).
- Soporte para Misskey/Firefish (MiAuth) u otros protocolos de login no compatibles con la API de Mastodon.
