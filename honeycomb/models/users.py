from persistent import Persistent


class DroneUser(Persistent):
    def __init__(self, userid, display_name, username, icon=None, background=None,
                 actor_url=None, inbox=None, outbox=None, access_token_encrypted=None,
                 password_hash=None):
        self.userid = userid
        self.display_name = display_name
        self.username = username
        self.icon = icon
        self.background = background
        # Identidad y buzones nativos de ActivityPub (AP C2S); necesarios para
        # publicar/leer del Fediverso a nombre del usuario.
        self.actor_url = actor_url
        self.inbox = inbox
        self.outbox = outbox
        # Token de acceso OAuth, SIEMPRE cifrado (ver security/tokenstore.py). Sin
        # una clave de cifrado configurada en el servidor, queda en None: el
        # token nunca se persiste en claro.
        self.access_token_encrypted = access_token_encrypted
        # Hash de contrasena para el login local (ver security/passwords.py). None
        # si esta cuenta nunca vinculo una contrasena (solo entra por Fediverso).
        self.password_hash = password_hash

    def update_profile(self, display_name=None, username=None, icon=None, background=None,
                        actor_url=None, inbox=None, outbox=None):
        if display_name is not None:
            self.display_name = display_name
        if username is not None:
            self.username = username
        if icon is not None:
            self.icon = icon
        if background is not None:
            self.background = background
        if actor_url is not None:
            self.actor_url = actor_url
        if inbox is not None:
            self.inbox = inbox
        if outbox is not None:
            self.outbox = outbox

    def has_fediverse_identity(self):
        """Si esta cuenta tiene un outbox del Fediverso vinculado (via login o
        vinculacion). No implica que tenga un token utilizable -- ver can_share."""
        return bool(self.outbox)

    def can_share(self):
        """Si hay suficiente (outbox + token cifrado) para publicar al Fediverso
        a nombre de este usuario ahora mismo. Ver security/activitypub.py."""
        return bool(self.outbox) and bool(self.access_token_encrypted)

    def get_stats(self, key=None):
        if hasattr(self, "__stats__"):
            if key:
                return getattr(self.__stats__, key, None)
            else:
                return self.__stats__._asdict()
        return None
