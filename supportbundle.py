"""The support bundle (1.10035, #241): one zip to send when something is wrong.

What goes in it, and what never does:

  in      the app version and build, the operating system, the settings with
          every secret taken out, crash.log, journal-mining-events.log, the
          newest lines of the app log, a list of the files in the data
          folder with their sizes, and the trace when trace mode wrote one.
  never   the Inara key, the community token, every Discord webhook, the
          wing code or member ID - removed from the settings by name, and the
          same values (and any webhook address or its token, and any
          "apiKey" field) removed from every text file as well, in case one
          was ever written into a log. The home folder's name is replaced
          by "~". A webhook in the list keeps its name and switches; its
          address reads "[removed]".

Nothing here touches a widget. The app writes the zip and opens its folder.
"""

import json
import os
import platform
import re
import sys
import threading
import time
import zipfile

APP_LOG = "app.log"
APP_LOG_MAX_BYTES = 256 * 1024
APP_LOG_KEEP_LINES = 1500
LOG_LINES = 400                 # of the app log, in a bundle
TEXT_TAIL_BYTES = 200 * 1024    # of crash.log and the event log
REMOVED = "[removed]"
# Trace mode (1.10040, #273): what the game wrote to Status.json and
# Cargo.json during a Rhino session, the few fields that settle how it marks
# a Rhino at work. In the bundle only when trace mode has written it.
TRACE_LOG = "file-trace.log"
TRACE_MAX_BYTES = 2 * 1024 * 1024

# Settings named outright, whatever they are called by the time a new one is
# added: the pattern below catches the rest.
SECRET_KEYS = {"inara_api_key", "community_token", "discord_webhook",
               "discord_webhooks", "wing_code", "wing_member"}
_SECRET_NAME = re.compile(r"(token|secret|password|webhook|api_?key|_key$|^key$)", re.I)
_WEBHOOK = re.compile(r"https?://(?:[\w.-]+\.)?discord(?:app)?\.com/api/webhooks/\S+", re.I)
_API_KEY_FIELD = re.compile(r'("?(?:apiKey|api_key|token|Authorization)"?\s*[:=]\s*)"?[^"\s,}]+"?', re.I)
# Long runs of letters and digits that follow "key=", "token=" and the like in
# a URL query.
_QUERY_SECRET = re.compile(r"([?&](?:key|token|apikey|api_key)=)[^&\s]+", re.I)
# A webhook's token, the part of its address that is the password, so it is
# searched for on its own as well (1.10040).
_WEBHOOK_TOKEN = re.compile(r"/api/webhooks/\d+/([A-Za-z0-9_\-]{20,})", re.I)


def is_secret_key(name):
    name = str(name)
    if name.lower().startswith("hotkey"):
        return False
    return name in SECRET_KEYS or bool(_SECRET_NAME.search(name))


def _hidden(name):
    """Whether a value inside a secret list or row is itself secret: the
    address of a webhook row is; its name and switches are not."""
    return str(name).lower() == "url" or is_secret_key(name)


def _secret_strings(value):
    """Every string a secret setting holds - inside a list of rows too."""
    if isinstance(value, str):
        if value.strip():
            yield value.strip()
    elif isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, dict):
                for name, inner in item.items():
                    if _hidden(name):
                        yield from _secret_strings(inner)
            else:
                yield from _secret_strings(item)


def secret_values(settings):
    """Every non-empty value a secret setting holds, and the token of any
    webhook among them, longest first."""
    found = set()
    for key, value in dict(settings or {}).items():
        if is_secret_key(key):
            for text in _secret_strings(value):
                found.add(text)
                found.update(_WEBHOOK_TOKEN.findall(text))
    return sorted(found, key=len, reverse=True)


def _clean_value(value):
    """A secret value as it goes in the bundle: "[removed]" if it is set,
    as it is if not; a list of rows keeps each row with only its secret
    parts removed."""
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            if isinstance(item, dict):
                out.append({name: _clean_value(inner) if _hidden(name) else inner
                            for name, inner in item.items()})
            else:
                out.append(_clean_value(item))
        return out
    return REMOVED if (value not in (None, "", False, 0)) else value


def clean_settings(settings):
    """The settings as they go in the bundle: a secret that is set reads
    "[removed]", one that is empty stays empty - which tells the person
    reading it whether a key was ever entered, and nothing else."""
    out = {}
    for key, value in dict(settings or {}).items():
        out[key] = _clean_value(value) if is_secret_key(key) else value
    return out


def scrub(text, secrets=(), home=None):
    """`text` with every secret value, webhook address and key field removed,
    and the home folder's name shortened to ~."""
    text = str(text)
    for value in secrets:
        if len(value) >= 4:
            text = text.replace(value, REMOVED)
    text = _WEBHOOK.sub(REMOVED, text)
    text = _QUERY_SECRET.sub(lambda m: m.group(1) + REMOVED, text)
    text = _API_KEY_FIELD.sub(lambda m: m.group(1) + '"' + REMOVED + '"', text)
    home = home if home is not None else os.path.expanduser("~")
    if home and len(home) > 3:
        for form in {home, home.replace("\\", "/"), home.replace("/", "\\")}:
            text = re.sub(re.escape(form), "~", text, flags=re.I)
    return text


class AppLog:
    """A small rolling log of what the app told the commander - the lines on
    the status line - so a bundle can say what happened before the problem.
    Never raises: a log that cannot be written is not worth a fault."""

    def __init__(self, folder):
        self.path = os.path.join(folder, APP_LOG) if folder else ""
        self._last = ""
        self._lock = threading.Lock()

    def write(self, text):
        text = " ".join(str(text or "").split())
        if not self.path or not text or text == self._last:
            return False
        self._last = text
        line = "%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), text[:600])
        with self._lock:
            try:
                os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as handle:
                    handle.write(line)
                if os.path.getsize(self.path) > APP_LOG_MAX_BYTES:
                    self._trim()
            except OSError:
                return False
        return True

    def _trim(self):
        try:
            with open(self.path, "r", encoding="utf-8", errors="replace") as handle:
                lines = handle.readlines()[-APP_LOG_KEEP_LINES:]
            with open(self.path, "w", encoding="utf-8") as handle:
                handle.writelines(lines)
        except OSError:
            pass


def _tail_text(path, limit=TEXT_TAIL_BYTES):
    """The last `limit` bytes of a text file, from a whole line, or ""."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            if size > limit:
                handle.seek(size - limit)
                handle.readline()
            data = handle.read()
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def _last_lines(path, count=LOG_LINES):
    text = _tail_text(path)
    return "\n".join(text.splitlines()[-count:]) + ("\n" if text else "")


def describe(version, build=""):
    """The first page of the bundle."""
    return "\n".join([
        "EDSMT support bundle",
        "made (UTC)   %s" % time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        "version      %s" % version,
        "build        %s" % (build or "-"),
        "system       %s" % platform.platform(),
        "python       %s" % sys.version.split()[0],
        "",
        "Settings have every secret removed. Nothing else is hidden: read "
        "the files before you send them.",
        ""])


def bundle_name(version, when=None):
    return "EDSMT-support-%s-%s.zip" % (str(version).replace(" ", ""),
                                        time.strftime("%Y%m%d-%H%M%S", time.gmtime(when)))


def make_bundle(dest_dir, data_dir, settings, version, build="", when=None):
    """Write the zip into `dest_dir` and return its path. OSError is the
    caller's to report."""
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, bundle_name(version, when))
    secrets = secret_values(settings)
    listing = []
    try:
        for name in sorted(os.listdir(data_dir)):
            full = os.path.join(data_dir, name)
            if os.path.isfile(full):
                listing.append("%10d  %s" % (os.path.getsize(full), name))
    except OSError:
        pass
    parts = {
        "about.txt": describe(version, build),
        "settings.json": json.dumps(clean_settings(settings), indent=2,
                                    sort_keys=True, default=str),
        "crash.log": _tail_text(os.path.join(data_dir, "crash.log"))
                     or "(no crash.log - nothing has crashed)\n",
        "journal-mining-events.log":
            _tail_text(os.path.join(data_dir, "journal-mining-events.log"))
            or "(no journal-mining-events.log yet)\n",
        APP_LOG: _last_lines(os.path.join(data_dir, APP_LOG))
                 or "(no app log yet)\n",
        "data-folder.txt": "\n".join(listing) + "\n",
    }
    trace = _tail_text(os.path.join(data_dir, TRACE_LOG), TRACE_MAX_BYTES)
    if trace:
        parts[TRACE_LOG] = trace
    temp = path + ".tmp"
    with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, body in parts.items():
            bundle.writestr(name, scrub(body, secrets))
    os.replace(temp, path)
    return path


def open_folder(path):
    """Show the folder holding `path` - with the file picked on Windows.
    True if something was asked to open."""
    folder = os.path.dirname(os.path.abspath(path))
    try:
        if os.name == "nt":
            import subprocess
            subprocess.Popen(["explorer", "/select,", os.path.abspath(path)])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", folder])
        return True
    except Exception:
        return False
