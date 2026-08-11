"""Limitador de tasa de ventana deslizante, en memoria de proceso.

Reusado por el registro de apps OAuth por dominio (security/fediverse.py) y
por los intentos de login/registro de cuentas locales (views/local_auth.py).
En memoria de un solo proceso (un worker via waitress); si el proyecto llega a
desplegarse con varios workers, esto debe moverse a un almacen compartido
(p.ej. la misma ZODB, o un cache externo).
"""

import threading
import time


class RateLimitError(Exception):
    """Se alcanzo el limite configurado. scope es 'global' o 'key' segun cual."""

    def __init__(self, scope):
        self.scope = scope
        super().__init__(scope)


class SlidingWindowLimiter:
    """Limita cuantas veces se puede llamar check_and_record: por clave y en total.

    max_per_key/max_global en None desactiva ese eje (sin limite).
    """

    def __init__(self, window_seconds, max_per_key, max_global):
        self.window_seconds = window_seconds
        self.max_per_key = max_per_key
        self.max_global = max_global
        self._lock = threading.Lock()
        self._by_key = {}
        self._global = []

    def check_and_record(self, key):
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            self._global = [t for t in self._global if t > cutoff]
            if self.max_global is not None and len(self._global) >= self.max_global:
                raise RateLimitError('global')

            key_attempts = [t for t in self._by_key.get(key, []) if t > cutoff]
            if self.max_per_key is not None and len(key_attempts) >= self.max_per_key:
                raise RateLimitError('key')

            key_attempts.append(now)
            self._by_key[key] = key_attempts
            self._global.append(now)


def positive_int_setting(settings, key, default):
    """Para valores que siempre necesitan un numero (p.ej. una ventana de tiempo)."""
    raw = (settings.get(key) or '').strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def limit_setting_or_none(settings, key):
    """Para topes configurables: vacio/ausente/<=0 = sin limite. Por defecto (sin
    configurar) el tope esta desactivado -- lo activa quien administra la instancia."""
    raw = (settings.get(key) or '').strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None
