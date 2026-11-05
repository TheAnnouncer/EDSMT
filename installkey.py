"""This copy of EDSMT's own key for the community map (1.10040).

The map gives each copy of EDSMT a key of its own and knows EDSMT by it,
rather than by a User-Agent any script can copy. The app asks for one once
(POST /v1/install, which asks for nothing in return), keeps it in a file of
its own in the data folder and sends it as X-EDSMT-Key with every request to
the map. It is never shown, never logged and never in settings.json - so a
settings file passed on, or made into a new install's defaults, never
carries it.

Plain logic and one small file: no window, no network here.
"""
import json
import os
import re

FILE_NAME = "install.key"
TAG = "install-key"
HEADER = "X-EDSMT-Key"
# After the map says no (busy, too many keys from one address today), wait
# this long before asking again.
RETRY_S = 6 * 3600
_SHAPE = re.compile(r"[A-Za-z0-9_-]{20,128}")


def valid(key):
    """True for something shaped like a key the map makes."""
    return isinstance(key, str) and bool(_SHAPE.fullmatch(key))


def load(folder):
    """The key kept in `folder`, or "" when there is none (or only rubbish)."""
    try:
        with open(os.path.join(folder, FILE_NAME), encoding="utf-8") as handle:
            key = handle.read().strip()
    except (OSError, UnicodeDecodeError):
        return ""
    return key if valid(key) else ""


def save(folder, key):
    """Keep `key` in `folder`, readable by this user only where the system
    allows it. True when it was written; a bad key is never written."""
    if not valid(key):
        return False
    path = os.path.join(folder, FILE_NAME)
    temp = path + ".tmp"
    try:
        os.makedirs(folder, exist_ok=True)
        handle = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(key + "\n")
        os.replace(temp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return True
    except OSError:
        return False


def from_reply(text):
    """The key in the map's answer to POST /v1/install, or ""."""
    try:
        key = json.loads(text).get("key")
    except (TypeError, ValueError, AttributeError):
        return ""
    return key if valid(key) else ""


def due(have, asked_at, now):
    """Whether to ask the map for a key now: when there is none, and not
    within RETRY_S of the last time it said no."""
    if have:
        return False
    return asked_at is None or now - asked_at >= RETRY_S
