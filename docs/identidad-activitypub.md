# Identidad de usuario: Fediverso (ActivityPub) y cuentas locales

Segundo hilo relacionado con el issue #15: el usuario se autentica con la red social del Fediverso que elija ("Inicia sesión con el Fediverso"), o con una cuenta local (usuario/contraseña) si no tiene una. Referencia de diseño: `docs/comunicacion-videojuegos-api.md` (hilo del contrato de endpoints) y la wiki [convidauam/wikiabeja](https://github.com/convidauam/wikiabeja).

## Qué es y qué no es

Un **cliente OAuth 2.0 identity-only** contra el Fediverso, más un login local opcional para quien no tiene cuenta ahí. El descubrimiento va primero por el estándar: **WebFinger resuelve el handle al Actor de ActivityPub**, y si el propio Actor declara sus endpoints OAuth (`endpoints.oauth*`, extensión de Mastodon/Pleroma), el registro de app, la autorización y el intercambio de token corren por esas rutas — es decir, **ActivityPub Client-to-Server (C2S)**, no la API específica de Mastodon. Cuando una instancia no las declara (p. ej. mastodon.social), se cae a las rutas conocidas de la API de Mastodon (`/api/v1/apps`, `/oauth/authorize`, `/oauth/token`), que Pleroma/Akkoma también implementan por compatibilidad.

Honeycomb sí toca ActivityPub C2S más allá del login: publica notas en el outbox del usuario (`security/activitypub.py`) cuando decide compartir un logro — siempre opt-in, nunca automático. No implementa federación servidor-a-servidor (firmas HTTP, entrega asíncrona, `inbox` de recepción) ni lee el timeline del usuario.

En la práctica, "la red social que el usuario elija" significa **cualquier instancia ActivityPub, con o sin las extensiones de Mastodon**: Mastodon, Pleroma/Akkoma, GoToSocial, Pixelfed. Misskey/Firefish usan otro mecanismo (MiAuth) y no funcionan sin trabajo adicional.

Se eligió **entrada abierta**: cualquier dominio que el usuario escriba, no una lista blanca. Esto obliga a que el guard anti-SSRF sea estricto desde el día uno (ver abajo), ya que el backend hace peticiones salientes a un host arbitrario elegido por el usuario.

## Flujo de login por Fediverso

1. `GET /login` — renderiza el formulario (`login.jinja2`), pide el handle (`usuario@instancia`) o, alternativamente, usuario/contraseña de una cuenta local (ver más abajo).
2. `POST /api/v1/auth/login` (requiere CSRF, igual que el resto de la app):
   - Parsea el handle → `(username, domain)`; si el dominio está en `fediverse.denylist`, se corta aquí.
   - **WebFinger** (`GET /.well-known/webfinger`, con `Accept: application/jrd+json` — algunas instancias, p. ej. Pleroma, dan 400 sin ese header) resuelve la URL del Actor.
   - Si se resolvió, **`GET` al documento del Actor** (`Accept: application/activity+json`) y se leen sus `endpoints.oauth*`. Si no se resolvió, se confirma con `/.well-known/nodeinfo` que hay un servidor real ahí (evita gastar un registro de app contra cualquier dominio).
   - `/.well-known/oauth-authorization-server` (RFC 8414) para saber si la instancia soporta PKCE S256; se pide scope de perfil (`profile`, o `read:accounts` si la instancia no anuncia soporte de `profile`) más `write:statuses` (necesario para poder publicar logros más adelante).
   - Registra la app vía el endpoint de registro descubierto en el Actor, o `POST /api/v1/apps` si no lo declaró (o reusa la app ya registrada antes para ese dominio, cacheada en ZODB) y genera un `state` de un solo uso.
   - Redirige (303) al endpoint de autorización descubierto (o `https://<dominio>/oauth/authorize` de fallback).
3. El usuario aprueba en **su propia instancia** (fuera de Honeycomb).
4. `GET /api/v1/auth/callback`:
   - Valida `state` (comparación timing-safe, un solo uso).
   - Intercambia el `code` por un `access_token` en el endpoint de token descubierto (o el de fallback).
   - El perfil sale del **documento del Actor** ya resuelto en el paso 2 (`actor_to_drone_user`); solo si no trajo un `id` usable se cae a `GET /api/v1/accounts/verify_credentials`.
   - El `access_token` se **cifra (Fernet) y se guarda** en `DroneUser.access_token_encrypted` — hace falta conservarlo para poder publicar logros al outbox más adelante. Sin `honeycomb.token_encryption_key` configurada en el servidor, `encrypt_token` regresa `None`: el token nunca se persiste, ni en claro ni de ninguna otra forma, y publicar queda deshabilitado hasta que el administrador de la instancia provea una clave.
   - Si ya había sesión iniciada (el usuario estaba **vinculando** un Fediverso a una cuenta existente, no iniciando sesión de cero), no se crea una cuenta nueva: se vincula la credencial a la cuenta actual y se funde el progreso si el Actor ya tenía uno propio (ver "Cuentas locales y vinculación").
   - Si no, se busca o crea el `DroneUser`, se actualiza su perfil (`update_profile`, nunca reemplazando el objeto completo — así no se pierde un `password_hash` u otra credencial ya vinculada) y se crea la sesión (`remember()`).

`client_id`/`client_secret` de la instancia viajan también en la sesión (de un solo uso, se limpian en el callback) para que este flujo específico no dependa de releer la caché de ZODB en el siguiente request; la caché en ZODB solo acelera futuros logins al mismo dominio.

## Cuentas locales y vinculación

No todo jugador tiene o quiere una cuenta del Fediverso. `honeycomb.local_accounts` (vacío = deshabilitado, es el valor de fábrica) habilita un segundo método de login: usuario + contraseña, con **registro abierto** (self-service, sin invitación).

- Contraseñas hasheadas con `hashlib.scrypt` (stdlib, sin dependencias nuevas) — `security/passwords.py`. Formato autodescriptivo (`scrypt$n=...,r=...,p=...$salt$hash`) para poder subir el costo después sin invalidar los hashes ya guardados.
- **Sin correo en el proyecto**: no hay verificación de cuenta ni recuperación de contraseña. Quien pierde su contraseña pierde esa credencial — puede seguir entrando por cualquier otra que tenga vinculada, pero no hay forma de recuperarla. Se avisa en la pantalla de registro, no solo aquí.
- Login/registro dan siempre el **mismo mensaje genérico** ante "usuario no existe" y "contraseña incorrecta", para no confirmar por esa vía si un nombre está en uso.
- Límite de intentos configurable (`honeycomb.login_rate_window_seconds`/`login_rate_max_per_user`/`login_rate_max_global`/`registration_rate_max_global`), mismo mecanismo de ventana deslizante que ya usaba el registro de apps OAuth (`security/ratelimit.py`, extraído de `security/fediverse.py` para reusarlo aquí).

### El problema: dos métodos, ¿una cuenta o dos?

El progreso (`GameData`, logros) se guarda por `userid`. Si alguien entra a veces por Fediverso y a veces con su cuenta local **sin vincularlas**, son dos cuentas distintas con dos historiales separados — se avisa explícitamente en `/login`, `/register` y `/cuenta` para que nadie lo suponga por accidente.

Para quien sí quiere una sola cuenta con ambos métodos, `BeeHive.__identities__` mapea credenciales a un userid primario:

- Credencial de Fediverso: clave `fediverse:<url del actor>`.
- Credencial local: clave `password:<username>`.

El userid primario de una cuenta nacida en el Fediverso sigue siendo la URL del Actor (cero migración: una cuenta ya guardada antes de este índice existir se sigue resolviendo igual, porque el login cae al userid natural cuando la credencial todavía no está en el índice). Una cuenta nacida local usa un userid opaco `local:<uuid>` — el nombre de usuario no es la llave de la base de datos, así se puede cambiar después sin romper el progreso.

Vincular reutiliza el mismo baile OAuth del login: `POST /api/v1/auth/login` con sesión ya iniciada guarda a qué cuenta vincular (`oauth_link_to` en la sesión), y el callback, en vez de crear una sesión nueva, ata la credencial a la cuenta actual. Se niega a vincular un Actor que ya esté vinculado a **otra** cuenta.

**Regla de fusión de progreso** (`BeeHive.merge_game_data`, por nodo, al vincular una credencial con progreso propio):

| Campo | Regla |
|---|---|
| Nodo que solo tenía la cuenta que se vincula | Se copia a la cuenta primaria |
| `badges` | Unión por `id`, conservando el `awarded_at` original de quien ya lo tenía |
| `interactions` | Suma |
| `first_seen` / `last_seen` | Mínimo / máximo |
| `stats` y `preferences` | Gana la cuenta primaria (único campo genuinamente ambiguo: no hay forma correcta de sumarlos o elegir uno sin contexto del juego) |

No se borra nada: el bucket original de la cuenta que se vincula se deja intacto (queda inalcanzable por la API, recuperable a mano si alguien se equivoca).

Se puede desvincular una credencial desde `/cuenta` (`BeeHive.unlink_identity`), salvo la última: una cuenta nunca puede quedar sin ninguna forma de entrar.

## Mapeo a DroneUser

| Campo DroneUser | Origen |
|---|---|
| `userid` | Fediverso: `id` del Actor (URL), o `"{dominio}#{account.id}"` de `verify_credentials` si el Actor no trajo uno usable. Local: `local:<uuid>`. Nunca el handle: los usernames se pueden reciclar. |
| `display_name` | `actor.name` (o `account.display_name` en el fallback) |
| `username` | Fediverso: handle completo (`usuario@dominio`). Local: el nombre elegido al registrarse. |
| `icon` / `background` | `actor.icon.url` / `actor.image.url` (defensivo: pueden venir como objeto, arreglo o `null`) |
| `actor_url`, `inbox`, `outbox` | Del documento del Actor; necesarios para C2S (publicar logros) |
| `access_token_encrypted` | Token OAuth cifrado (Fernet); `None` sin `honeycomb.token_encryption_key` configurada |
| `password_hash` | Hash scrypt de la cuenta local; `None` si esta cuenta nunca vinculó una contraseña |

`DroneUser` es `Persistent` y vive en `BeeHive.__users__` (ZODB), indexado por `userid`. `BeeHive.__oauth_apps__` cachea `{client_id, client_secret}` por dominio; `BeeHive.__identities__` mapea credenciales al userid primario (ver arriba).

## Seguridad

- **Guard anti-SSRF en toda llamada saliente** (WebFinger, Actor, nodeinfo, oauth metadata, registro de app, intercambio de token, verify_credentials, publicar al outbox): solo https, se resuelve el host y se rechaza si cualquier IP resuelta es privada/loopback/link-local/multicast/reservada, sin seguir redirects automáticos (se revalida cada salto a mano, hasta 3), con timeout. Ver `honeycomb/security/fediverse.py`.
- `state` aleatorio de un solo uso, comparación timing-safe. PKCE S256 cuando la instancia lo soporta.
- `next` (a dónde redirigir tras login) se sanitiza: solo rutas relativas de un segmento, nunca `//host` (anti open-redirect).
- El límite de confianza del login por Fediverso es la **instancia**, no el usuario individual: una instancia hostil podría afirmar cualquier username local suyo. Esto es inherente al modelo, no algo que este código pueda resolver. El login local traslada esa confianza a Honeycomb mismo: es la contrapartida de no depender de una instancia externa.
- El registro de app por dominio se cachea (no se re-registra en cada login al mismo dominio). **Rate limit** en registro de apps y en login/registro local (`security/ratelimit.py`, en memoria de proceso — con varios workers cada uno lleva su propia cuenta).
- **Denylist configurable**: `fediverse.denylist` en el `.ini` (espacio-separado). Un dominio en la lista nunca llega a registrar una app ni a redirigir — se corta justo después de parsear el handle, antes de cualquier llamada de red.
- Ningún límite (payload de juego, rate limits, `min_password_length`) está hardcodeado: todos se leen de settings, vacío/0 = sin límite, lo activa quien administra la instancia. Mismo criterio que `auth.secret`, que debe quedar vacío en el `.ini` versionado — cada despliegue pone el suyo, o el servidor no arranca.

## `redirect_uri` detrás del reverse proxy

El `redirect_uri` que se registra con la instancia remota se construye con `request.application_url` (no `request.host_url`), porque en producción el backend queda montado bajo un prefijo (`/backend/`, según `reverse_proxy/conf.d/nginx.conf` de `convida_deployment`) que nginx quita antes de reenviar la petición al contenedor. `host_url` solo trae `scheme://host:puerto`; `application_url` además incluye ese prefijo (via `SCRIPT_NAME`, que `ForwardedHeadersMiddleware` en `honeycomb/__init__.py` arma a partir del header `X-Forwarded-Prefix` que sí manda ese nginx). Depende de que `honeycomb.use_proxy_headers = true` esté activo en `production.ini` (ya lo está) y de que el proxy real siga mandando esos headers tal como los manda el `nginx.conf` revisado.

## Verificado en vivo

Contra dos instancias reales, sin mocks, usando las funciones de producción de `honeycomb/security/fediverse.py`:

| Verificación | unam.social (Pleroma 2.9.1) | mastodon.social |
|---|---|---|
| WebFinger | 200 con el Actor — requiere `Accept: application/jrd+json`, sin ese header da 400 | 200, sin ese requisito |
| `endpoints.oauth*` en el Actor | Declara `oauthRegistrationEndpoint`/`oauthAuthorizationEndpoint`/`oauthTokenEndpoint`: descubrimiento AP C2S completo | No los declara (solo `sharedInbox`): cae al fallback de rutas Mastodon |
| Mapeo Actor → `DroneUser` | `icon`/`image` como objeto `{url: ...}`, mapeados correctamente | `icon` ausente (`None`), manejado sin error |

No se completó el intercambio de código con una cuenta real (requiere aprobar el login en el navegador con una cuenta existente); ese tramo sí está cubierto por pruebas automatizadas contra una instancia fake.

## Pruebas

- `tests/test_fediverse.py`: funciones puras de `honeycomb/security/fediverse.py` (parseo de handle, WebFinger, Actor, endpoints declarados con fallback, guard SSRF, PKCE, elección de scope, mapeo a `DroneUser`, rate limiter).
- `tests/test_passwords.py`, `tests/test_local_accounts.py`: hasheo/verificación de contraseñas, registro/login/vinculación/desvinculación a nivel de modelo (sin HTTP).
- `tests/test_tokenstore.py`: cifrado/descifrado del `access_token`.
- `tests/test_models.py`: `BeeHive.merge_game_data` (fusión de progreso al vincular) y el índice de identidades, directamente sobre el modelo.
- `tests/test_auth_fediverse.py`, `tests/test_local_auth.py`: las vistas completas (`/login`, `/register`, `/cuenta`, `/api/v1/auth/*`) contra una instancia fake monkeypatcheada — handle inválido, dominio sin nodeinfo/actor, `state` faltante/incorrecto, flujo completo exitoso, reuso de la app cacheada, cuenta local duplicada, vincular Fediverso a una cuenta local con fusión de progreso, vincular un Actor ya vinculado a otra cuenta (rechazado).
- Los fixtures `identity_bridge`/`game_data_bridge` (en `tests/conftest.py`) puentean `BeeHive.get_user`/`upsert_user`/`resolve_identity`/`link_identity`/`get_game_data`/`merge_game_data` por fuera de ZODB, **solo para pruebas**: el fixture `testapp` aborta cada request en su propia transacción (ver nota en `docs/comunicacion-videojuegos-api.md`), así que sin este puente una cuenta creada en un request no existiría todavía para el siguiente. El código de producción usa ZODB en todo momento; esto se confirmó con la verificación en vivo de arriba.

## Pendiente / fuera de alcance

- Verificación inversa de WebFinger contra suplantación (el token OAuth de la instancia sigue siendo el ancla de confianza).
- Refresco de perfil (hoy se actualiza en cada login; no hay política de "cada cuánto" releer avatar/display_name si el usuario no vuelve a entrar).
- Manejo especial de instancias que limitan o deniegan el registro de apps.
- Federación servidor-a-servidor (firmas HTTP, entrega asíncrona, `inbox` de recepción), lectura del timeline del usuario.
- Soporte para Misskey/Firefish (MiAuth) u otros protocolos de login no compatibles con WebFinger + Actor AS2.
- Verificación de correo y recuperación de contraseña para cuentas locales (requeriría infraestructura de correo, que el proyecto no tiene).
- Si una cuenta tiene más de una identidad de Fediverso vinculada, solo la última usada actualiza `actor_url`/`inbox`/`outbox`/`access_token_encrypted` (campos únicos en `DroneUser`, no una lista) — publicar logros usa siempre esa última.
