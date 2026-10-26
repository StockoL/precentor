"""
Counting attempts, to limit how often something can be tried: signing in
to one address, or registering from one network address. The counts live
in the cache (a database table), under a fingerprint of what's counted,
so the table never holds an email address in plain text.
"""

import hashlib

from django.core.cache import cache


def _key(kind, value):
    return f"throttle:{kind}:{hashlib.sha256(value.encode()).hexdigest()}"


def limit_reached(kind, value, limit):
    return cache.get(_key(kind, value), 0) >= limit


def record_attempt(kind, value, window):
    """Count one more attempt. Each count lasts window seconds from the
    latest attempt: set() is given the window itself, as cache.incr()
    would keep the cache's default timeout instead."""
    key = _key(kind, value)
    cache.set(key, cache.get(key, 0) + 1, window)


def clear_attempts(kind, value):
    cache.delete(_key(kind, value))
