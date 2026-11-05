"""Mining locations to the shared player data network, EDDN (1.10040, #159).

When the FSS reports a body with Planetary Mining Locations, its signal
list goes to EDDN as one fssbodysignals/1 message, so every tool that reads
the network learns the body has them. Nothing else is sent.

The network's rules, followed here:

- live events only: an event read back from an old journal never goes;
- StarSystem and StarPos are added only from a Location, FSDJump or
  CarrierJump whose SystemAddress matches the event's own - otherwise the
  message is not sent at all;
- nothing whose name ends _Localised, and nothing about the commander but
  the uploader name and the horizons / odyssey flags, which come only from
  LoadGame and only when LoadGame carries them;
- gameversion and gamebuild come from Fileheader and are passed through
  exactly as the game wrote them; a beta client's messages go to the /test
  schema, and a 3.x client sends nothing;
- a message refused as wrong (400, 413, 426) is never sent again; any other
  failure waits at least a minute, and nothing is retried for ever.

Plain functions, a Tracker the journal reader feeds every event it reads,
and an Outbox the app sends from, one message at a time.
"""
import calendar
import json
import re
import ssl
import time
import urllib.error
import urllib.request

TAG = "eddn"
SETTING = "eddn_upload"
DEFAULT = True
UPLOAD_URL = "https://eddn.edcd.io:4430/upload/"
SCHEMA = "https://eddn.edcd.io/schemas/fssbodysignals/1"
TEST_SCHEMA = SCHEMA + "/test"
SOFTWARE = "EDSMT"
FRESH_S = 300.0       # an event older than this was read back, not seen live
RETRY_S = 60.0        # the network asks for at least a minute between tries
MAX_TRIES = 5
MOST = 100
NOTICE = ("When the FSS finds Planetary Mining Locations on a body, that body's "
          "signal counts go to EDDN, the network other Elite tools read, with your "
          "CMDR name as the uploader. Nothing else: no finds, no position on the "
          "body, no credits.")

LOCATION_EVENTS = ("Location", "FSDJump", "CarrierJump")
EVENTS = {"Fileheader", "LoadGame", "FSSBodySignals"} | set(LOCATION_EVENTS)
MINING = re.compile(r"PlanetaryMiningLocation", re.I)
DROP_CODES = (400, 413, 426)

# The network's gateway sends its certificate chain through ISRG Root X2's
# cross-signature, which expired in September 2025. A Windows PC whose
# certificate store has never fetched ISRG Root X2 itself then refuses the
# connection with "certificate has expired" (seen on a real PC, 5 Nov 2026).
# The root is trusted here, for this connection only. SHA-256
# 69729b8e15a86efc177a57afb7171dfc64add28c2fca8cf1507e34453ccb1470.
ISRG_ROOT_X2 = """-----BEGIN CERTIFICATE-----
MIICGzCCAaGgAwIBAgIQQdKd0XLq7qeAwSxs6S+HUjAKBggqhkjOPQQDAzBPMQsw
CQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJuZXQgU2VjdXJpdHkgUmVzZWFyY2gg
R3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBYMjAeFw0yMDA5MDQwMDAwMDBaFw00
MDA5MTcxNjAwMDBaME8xCzAJBgNVBAYTAlVTMSkwJwYDVQQKEyBJbnRlcm5ldCBT
ZWN1cml0eSBSZXNlYXJjaCBHcm91cDEVMBMGA1UEAxMMSVNSRyBSb290IFgyMHYw
EAYHKoZIzj0CAQYFK4EEACIDYgAEzZvVn4CDCuwJSvMWSj5cz3es3mcFDR0HttwW
+1qLFNvicWDEukWVEYmO6gbf9yoWHKS5xcUy4APgHoIYOIvXRdgKam7mAHf7AlF9
ItgKbppbd9/w+kHsOdx1ymgHDB/qo0IwQDAOBgNVHQ8BAf8EBAMCAQYwDwYDVR0T
AQH/BAUwAwEB/zAdBgNVHQ4EFgQUfEKWrt5LSDv6kviejM9ti6lyN5UwCgYIKoZI
zj0EAwMDaAAwZQIwe3lORlCEwkSHRhtFcP9Ymd70/aTSVaYgLXTWNLxBo1BfASdW
tL4ndQavEi51mI38AjEAi/V3bNTIZargCyzuFJ0nN6T5U6VR5CmD1/iQMVtCnwr1
/q4AaOeMSQ+2b1tbFfLn
-----END CERTIFICATE-----
"""


def context():
    """The system's trusted roots, plus ISRG Root X2."""
    ctx = ssl.create_default_context()
    try:
        ctx.load_verify_locations(cadata=ISRG_ROOT_X2)
    except ssl.SSLError:
        pass
    return ctx


def _epoch(text):
    try:
        return float(calendar.timegm(time.strptime(str(text), "%Y-%m-%dT%H:%M:%SZ")))
    except (TypeError, ValueError):
        return None


def _major(version):
    found = re.match(r"\s*(\d+)\.", str(version or ""))
    return int(found.group(1)) if found else 0


def _is_test(version, build):
    words = ("%s %s" % (version or "", build or "")).lower()
    return "beta" in words or "alpha" in words


def _position(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        return [float(value[0]), float(value[1]), float(value[2])]
    except (TypeError, ValueError):
        return None


def _signals(value):
    out = []
    for sig in value if isinstance(value, list) else []:
        if not isinstance(sig, dict):
            continue
        kind, count = sig.get("Type"), sig.get("Count")
        if isinstance(kind, str) and kind and isinstance(count, int) and not isinstance(count, bool):
            out.append({"Type": kind, "Count": count})
    return out


class Tracker:
    """Fed every event the reader parses, in order; hands back a message
    ready for the outbox, or None."""

    def __init__(self):
        self.gameversion = ""
        self.gamebuild = ""
        self.horizons = None
        self.odyssey = None
        self.located = None            # (SystemAddress, StarSystem, StarPos)
        self.done = set()

    def see(self, event, now=None):
        if not isinstance(event, dict):
            return None
        name = event.get("event")
        if name == "Fileheader":
            self.gameversion = str(event.get("gameversion") or "")
            self.gamebuild = str(event.get("build") or "")
            # Part 1 is a new game session; a later part of the same
            # journal carries on with what LoadGame and the jump said.
            if int(event.get("part") or 1) <= 1:
                self.horizons = self.odyssey = None
                self.located = None
            return None
        if name == "LoadGame":
            self.horizons = event["Horizons"] if isinstance(event.get("Horizons"), bool) else None
            self.odyssey = event["Odyssey"] if isinstance(event.get("Odyssey"), bool) else None
            if not self.gameversion and event.get("gameversion"):
                self.gameversion = str(event.get("gameversion"))
                self.gamebuild = str(event.get("build") or "")
            return None
        if name in LOCATION_EVENTS:
            pos = _position(event.get("StarPos"))
            address = event.get("SystemAddress")
            system = event.get("StarSystem")
            if pos and isinstance(address, int) and isinstance(system, str) and system:
                self.located = (address, system, pos)
            else:
                self.located = None
            return None
        if name == "FSSBodySignals":
            return self._message(event, now)
        return None

    def _message(self, event, now):
        now = time.time() if now is None else now
        when = _epoch(event.get("timestamp"))
        if when is None or abs(now - when) > FRESH_S:
            return None
        if _major(self.gameversion) < 4:
            return None
        address, body_id = event.get("SystemAddress"), event.get("BodyID")
        if not isinstance(address, int) or not isinstance(body_id, int) or isinstance(body_id, bool):
            return None
        if not self.located or self.located[0] != address:
            return None
        signals = _signals(event.get("Signals"))
        if not any(MINING.search(sig["Type"]) for sig in signals):
            return None
        key = (address, body_id)
        if key in self.done:
            return None
        self.done.add(key)
        message = {"timestamp": str(event["timestamp"]), "event": "FSSBodySignals",
                   "StarSystem": self.located[1], "StarPos": list(self.located[2]),
                   "SystemAddress": address, "BodyID": body_id, "Signals": signals}
        if isinstance(event.get("BodyName"), str) and event["BodyName"]:
            message["BodyName"] = event["BodyName"]
        if self.horizons is not None:
            message["horizons"] = self.horizons
        if self.odyssey is not None:
            message["odyssey"] = self.odyssey
        test = _is_test(self.gameversion, self.gamebuild)
        return {"schema": TEST_SCHEMA if test else SCHEMA, "gameversion": self.gameversion,
                "gamebuild": self.gamebuild, "message": message, "key": key}


def envelope(item, cmdr, version):
    """The message as the network takes it."""
    return {"$schemaRef": item["schema"],
            "header": {"uploaderID": str(cmdr or ""), "softwareName": SOFTWARE,
                       "softwareVersion": str(version or ""),
                       "gameversion": item.get("gameversion", ""),
                       "gamebuild": item.get("gamebuild", "")},
            "message": item["message"]}


def upload(env, opener=None, timeout=20.0):
    """POST one message: (HTTP code, what came back). 0 when there was no
    answer at all. Never raises."""
    opener = opener or urllib.request.urlopen
    request = urllib.request.Request(UPLOAD_URL, data=json.dumps(env).encode("utf-8"), method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("User-Agent", "%s/%s" % (SOFTWARE, env.get("header", {}).get("softwareVersion", "")))
    try:
        with opener(request, timeout=timeout, context=context()) as reply:
            body = reply.read().decode("utf-8", errors="replace")
            return int(getattr(reply, "status", 200) or 200), body.strip()[:200]
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except (OSError, ValueError, AttributeError):
            body = ""
        return int(exc.code), (body or str(exc.reason or "")).strip()[:200]
    except urllib.error.URLError as exc:
        return 0, str(exc.reason)[:200]
    except (OSError, ValueError) as exc:
        return 0, str(exc)[:200]


def verdict(code):
    """"sent", "drop" (never again) or "retry" (in a minute)."""
    if 200 <= int(code or 0) < 300:
        return "sent"
    if int(code or 0) in DROP_CODES:
        return "drop"
    return "retry"


class Outbox:
    """Messages waiting to go, one at a time, oldest first."""

    def __init__(self):
        self.items = []
        self.next_at = 0.0
        self.sent = 0
        self.dropped = 0
        self.last = ""

    def add(self, item, now=None):
        if not item:
            return False
        key = item.get("key")
        if key is not None and any(i.get("key") == key for i in self.items):
            return False
        item.setdefault("tries", 0)
        self.items.append(item)
        if len(self.items) > MOST:
            self.items = self.items[-MOST:]
        return True

    def due(self, now=None):
        now = time.time() if now is None else now
        return bool(self.items) and now >= self.next_at

    def take(self, now=None):
        if not self.due(now):
            return None
        return self.items.pop(0)

    def result(self, item, code, now=None, text=""):
        """What the network said about item: counted, dropped or kept."""
        now = time.time() if now is None else now
        said = verdict(code)
        self.last = "%s %s" % (code, text) if text else str(code)
        if said == "sent":
            self.sent += 1
            return said
        if said == "retry":
            item["tries"] = int(item.get("tries", 0)) + 1
            if item["tries"] < MAX_TRIES:
                self.items.insert(0, item)
                self.items = self.items[:MOST]
                self.next_at = now + RETRY_S
                return said
        self.dropped += 1
        return "drop"
