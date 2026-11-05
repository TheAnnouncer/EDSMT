"""Telling a launcher that EDSMT is running (1.10040, #323).

At start-up EDSMT writes one small file into a folder every Radio Raxxla
tool shares - <per-user data>/RadioRaxxla/Hub/apps/EDSMT.json - and removes
it again on a clean exit. A launcher reads the folder to see which tools are
open, which versions they are, and what picture to show for each.

The file holds what a launcher needs and nothing else: the tool, its
version, its process, when it started and where its picture is. Never
anything about the commander. A file that cannot be written is logged and
ignored - the app runs the same either way.
"""
import json
import ntpath
import os
import posixpath
import sys
import time

SCHEMA = 1
NAME = "EDSMT"
TITLE = "EDSMT - Surface Mining Tool"
FILE_NAME = NAME + ".json"


def apps_folder(platform=None, environ=None, home=None):
    """The folder the tools announce themselves in, for this user: under
    %LOCALAPPDATA% on Windows, and $XDG_DATA_HOME (~/.local/share when it is
    blank or unset) everywhere else."""
    platform = sys.platform if platform is None else platform
    environ = os.environ if environ is None else environ
    home = os.path.expanduser("~") if home is None else home
    # That platform's own path rules, so the answer is the same whichever
    # system asks (a Linux path built on Windows had backslashes in it).
    if str(platform).startswith("win"):
        join = ntpath.join
        root = environ.get("LOCALAPPDATA") or join(home, "AppData", "Local")
    else:
        join = posixpath.join
        root = environ.get("XDG_DATA_HOME") or join(home, ".local", "share")
    return join(root, "RadioRaxxla", "Hub", "apps")


def manifest(version, pid, started, icon):
    """The file's contents: which tool, which version, which process, when
    it started (UTC) and the absolute path of its picture."""
    return {"schema": SCHEMA, "name": NAME, "title": TITLE,
            "version": str(version), "pid": int(pid),
            "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
            "icon": os.path.abspath(icon) if icon else None,
            "web": None, "health": "ok"}


def _say(log, text):
    if log is None:
        return
    try:
        log(text)
    except Exception:
        pass        # a log that fails is not a reason to stop either


def announce(version, icon, folder=None, pid=None, now=None, log=None):
    """Write EDSMT.json into `folder` (the shared one when not given). The
    path written, or None when it could not be - which is logged through
    `log`, never raised."""
    folder = folder or apps_folder()
    path = os.path.join(folder, FILE_NAME)
    data = manifest(version, os.getpid() if pid is None else pid,
                    time.time() if now is None else now, icon)
    spare = path + ".tmp"
    try:
        os.makedirs(folder, exist_ok=True)
        with open(spare, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        os.replace(spare, path)
        return path
    except (OSError, ValueError, TypeError) as exc:
        _say(log, "Could not tell the hub EDSMT is running (%s): %s" % (path, exc))
        try:
            os.remove(spare)
        except OSError:
            pass
        return None


def withdraw(path, pid=None):
    """Remove the file this process wrote. A file another process wrote, or
    one that cannot be read, is left where it is. True if it was removed."""
    if not path:
        return False
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict) or data.get("pid") != (os.getpid() if pid is None else pid):
            return False
        os.remove(path)
        return True
    except (OSError, ValueError):
        return False
