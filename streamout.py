"""The Rhino session on a stream (1.10040, #149 and #307).

A small web server on this PC for an OBS Browser Source. It answers on
127.0.0.1 only - the PC it runs on, never the network - and only while the
commander has it switched on in Settings > Overlay > Streaming.

    /overlay      a page made to sit over a capture of the game
    /viewer       a small card for a corner of the stream or a panel picture
    /state.json   what both of them show
    /card.png     the latest session card (sessioncard.py)

What the pages show is built by stream_state from plain values, so it is
checked without the app: whose session and where, tonnes by commodity,
credits an hour, merits, rigs down, the nearest deposit, the last find and
the clock. The CMDR name is the only thing about the commander in it, and
no position on a body - no latitude, no longitude - is ever put in a page or
the JSON. Streamer mode is the app's own rule, handed in as `hide`: the
names it would hide on screen are hidden here the same way.

Pure logic and the standard library: no Tk.
"""
import http.server
import json
import os
import re
import socketserver
import threading
import time
import urllib.parse

import mapimage as MI
import planview as PV
import survey as SV

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
PORT_MIN, PORT_MAX = 1024, 65535
# The pages ask for the state once a second; the app need not build it
# more often than that.
STATE_EVERY_S = 1.0
# A port another program holds is tried again this often, quietly.
RETRY_S = 30.0
MINING_SHOWN = 3

# The theme colours the pages wear, by palette name. The cockpit's own
# where the app gives none.
COLOURS = {"orange": "#ff7a18", "amber": "#ffb545", "text": "#e9dccd",
           "dim": "#9c6a3c", "void": "#0b0705", "green": "#35d07f",
           "red": "#d1483a", "cyan": "#37c6d4"}
_HEX = re.compile(r"#[0-9a-fA-F]{6}")


# The shape of /state.json, for the tools that read it (docs/LOCAL-DATA.md).
SCHEMA = 1


def _whole(value, low=0):
    """A whole number not below `low`, or `low` for anything that is not one."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return low
    if number != number:
        return low
    return max(low, int(round(number)))


def parse_port(value):
    """The port from a setting: blank is the default, a whole number from
    1024 to 65535 is itself, anything else is None."""
    text = str(value if value is not None else "").strip()
    if not text:
        return DEFAULT_PORT
    if not text.isdigit():
        return None
    port = int(text)
    return port if PORT_MIN <= port <= PORT_MAX else None


def page_url(port, path="/overlay"):
    """The address to paste into OBS."""
    return "http://%s:%d%s" % (HOST, int(port), path)


def clock_text(seconds):
    """"1:02:03" - hours carry on past a day rather than wrapping."""
    seconds = _whole(seconds)
    return "%d:%02d:%02d" % (seconds // 3600, seconds % 3600 // 60, seconds % 60)


def ago_text(seconds):
    """How long ago, in a few words."""
    seconds = _whole(seconds)
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return "%d min ago" % (seconds // 60)
    if seconds < 2 * 86400:
        return "%d h ago" % (seconds // 3600)
    return "%d days ago" % (seconds // 86400)


def _same(text):
    return text


def nearest_deposit(rows):
    """The nearest deposit not worked out, as commodity, distance and
    bearing - and nothing else. `rows` are the survey's near rows; their
    positions and whoever found each one stay behind."""
    best = None
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        deposit = row.get("deposit") if isinstance(row.get("deposit"), dict) else {}
        try:
            metres = float(row.get("range_m"))
            bearing = float(row.get("bearing"))
        except (TypeError, ValueError):
            continue
        if metres != metres or bearing != bearing or metres < 0:
            continue
        if SV.is_depleted(deposit.get("amount")):
            continue
        if best is None or metres < best[0]:
            best = (metres, bearing, SV.canonical(deposit.get("commodity") or "") or "Unknown")
    if best is None:
        return None
    metres, bearing, commodity = best
    return {"commodity": commodity, "distance_m": int(round(metres)),
            "distance": MI.metres_text(metres), "bearing": int(round(bearing)) % 360,
            "compass": PV.compass_point(bearing)}


def last_find(deposits, hide=None, now=None):
    """The newest of `deposits` (the commander's own finds) as what it was,
    where and how long ago - its position and anything else left behind.
    `hide` is streamer mode's say on the place. None when there is none."""
    hide = hide or _same
    newest = None
    for deposit in deposits or ():
        if not isinstance(deposit, dict):
            continue
        at = SV._epoch(deposit.get("recorded"))
        if at and (newest is None or at > newest[0]):
            newest = (at, deposit)
    if newest is None:
        return None
    at, deposit = newest
    now = time.time() if now is None else now
    rigs = str(deposit.get("rigs") or "").strip()
    place = str(deposit.get("body") or deposit.get("system") or "").strip()
    return {"commodity": SV.canonical(deposit.get("commodity") or "") or "Unknown",
            "amount": str(deposit.get("amount") or "").strip(),
            "rigs": int(rigs) if rigs.isdigit() else None,
            "where": str(hide(place) or "") if place else "",
            "ago_s": _whole(now - at), "ago": ago_text(now - at)}


def _colours(given):
    out = dict(COLOURS)
    for key, value in dict(given or {}).items():
        name = str(key).strip().lower()
        if name in out and isinstance(value, str) and _HEX.fullmatch(value.strip()):
            out[name] = value.strip().lower()
    return out


def stream_state(cmdr="", system="", body="", mined=None, seconds=0, running=False,
                 paused=False, cr_hr=0, merits=None, merits_estimated=False,
                 rigs_down=0, near=None, find=None, colours=None, hide=None, now=None,
                 version=""):
    """What /state.json says, from plain values. Never raises.

    `mined` is {commodity: tonnes} this session, `seconds` the session's
    time so far, `near` the survey's near rows (only the nearest deposit's
    commodity, distance and bearing are taken from them), `find` what
    last_find made of the commander's newest find, `colours` the theme's
    palette by name, and `hide` streamer mode's rule for a line of text - the
    system and body pass through it. `merits` of 0 or None is None, so the
    page leaves the line out."""
    hide = hide or _same
    tonnes = []
    for name, count in dict(mined or {}).items():
        name = SV.canonical(name or "")
        count = _whole(count)
        if name and count > 0:
            tonnes.append({"commodity": name, "tonnes": count})
    tonnes.sort(key=lambda row: (-row["tonnes"], row["commodity"]))
    rate = _whole(cr_hr)
    earned = _whole(merits) if merits is not None else 0
    seconds = _whole(seconds)
    found = None
    if isinstance(find, dict):
        found = {key: find.get(key) for key in ("commodity", "amount", "rigs", "where",
                                                "ago_s", "ago")}
        found["where"] = str(hide(str(found["where"] or "")) or "")
    return {
        "app": "EDSMT",
        # Other tools read this too (docs/LOCAL-DATA.md): what changes the
        # meaning of a field changes the schema number; a new field does not.
        "schema": SCHEMA,
        "version": str(version or ""),
        "cmdr": str(cmdr or "").strip(),
        "system": str(hide(str(system or "").strip()) or ""),
        "body": str(hide(str(body or "").strip()) or ""),
        "session": {"running": bool(running), "paused": bool(paused),
                    "seconds": seconds, "clock": clock_text(seconds)},
        "tonnes": tonnes,
        "tonnes_total": sum(row["tonnes"] for row in tonnes),
        "mining": [row["commodity"] for row in tonnes[:MINING_SHOWN]],
        "cr_hr": rate,
        "cr_hr_text": "{:,}".format(rate),
        "merits": earned or None,
        "merits_estimated": bool(merits_estimated) if earned else False,
        "rigs_down": _whole(rigs_down),
        "nearest": nearest_deposit(near),
        "last_find": found,
        "colours": _colours(colours),
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                 time.gmtime(time.time() if now is None else now)),
    }


# -- the pages ---------------------------------------------------------------
#
# Each page is one file, and nothing is fetched but its own state: no web
# font, no script from anywhere, no picture. The words are written as text,
# never as markup - a commodity or a body name is whatever the game said.
# Sized for a 1080p canvas at 1:1; OBS scales the source from there.

_HEAD = """<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<style>
:root { --orange: #ff7a18; --amber: #ffb545; --text: #e9dccd; --dim: #9c6a3c;
        --void: #0b0705; --green: #35d07f; --red: #d1483a; --cyan: #37c6d4;
        --panel: rgba(11, 7, 5, 0.62); }
html, body { margin: 0; padding: 0; background: transparent; overflow: hidden; }
body { font-family: Consolas, "Cascadia Mono", "DejaVu Sans Mono", monospace;
       line-height: 1.3; color: var(--text);
       text-shadow: 0 0 3px #000, 0 2px 4px #000; }
.gone { opacity: 0; }
.row { display: flex; justify-content: space-between; gap: 28px; }
.label { color: var(--dim); letter-spacing: 1px; padding-top: 3px; }
.value { font-weight: bold; text-align: right; }
.good { color: var(--green); }
%s
</style>
</head>
<body>
<div id="hud" class="gone"></div>
<script>
(function () {
  var hud = document.getElementById("hud");
  var misses = 0;
  function el(tag, cls, words) {
    var node = document.createElement(tag);
    if (cls) { node.className = cls; }
    if (words !== undefined) { node.textContent = String(words); }
    return node;
  }
  function row(label, value, cls) {
    var line = el("div", "row");
    line.appendChild(el("span", "label", label));
    line.appendChild(el("span", "value" + (cls ? " " + cls : ""), value));
    return line;
  }
  function wash(hex, alpha) {
    var n = parseInt(hex.slice(1), 16);
    return "rgba(" + (n >> 16 & 255) + ", " + (n >> 8 & 255) + ", " + (n & 255) + ", " + alpha + ")";
  }
  function number(n) { return Number(n || 0).toLocaleString("en-GB"); }
  function cmdr(s) {
    var name = String(s.cmdr || "");
    return !name || /^cmdr /i.test(name) ? name : "CMDR " + name;
  }
  function theme(s, alpha) {
    var colours = s.colours || {}, sheet = document.documentElement.style, key;
    for (key in colours) {
      if (/^#[0-9a-f]{6}$/.test(colours[key])) { sheet.setProperty("--" + key, colours[key]); }
    }
    if (/^#[0-9a-f]{6}$/.test(colours.void || "")) { sheet.setProperty("--panel", wash(colours.void, alpha)); }
    while (hud.firstChild) { hud.removeChild(hud.firstChild); }
  }
%s
  function ask() {
    fetch("state.json", { cache: "no-store" })
      .then(function (answer) { if (!answer.ok) { throw new Error(answer.status); } return answer.json(); })
      .then(function (s) { misses = 0; paint(s); hud.className = ""; })
      .catch(function () { misses += 1; if (misses >= 5) { hud.className = "gone"; } })
      .then(function () { setTimeout(ask, 1000); });
  }
  ask();
}());
</script>
</body>
</html>
"""

_OVERLAY_STYLE = """body { font-size: 28px; }
#hud { display: inline-block; box-sizing: border-box; min-width: 540px; margin: 12px;
       padding: 14px 22px 16px; background: var(--panel);
       border-left: 6px solid var(--orange); border-radius: 4px; transition: opacity 0.6s; }
.cmdr { font-size: 34px; font-weight: bold; color: var(--orange); letter-spacing: 1px; }
.where { font-size: 28px; color: var(--amber); }
.system { font-size: 24px; color: var(--dim); margin-bottom: 8px; }
.label { font-size: 24px; }
.item { display: flex; justify-content: space-between; gap: 28px; font-size: 26px; padding-left: 22px; }
.note { font-size: 24px; color: var(--dim); }"""

_OVERLAY_PAINT = """  function paint(s) {
    theme(s, 0.62);
    if (s.cmdr) { hud.appendChild(el("div", "cmdr", cmdr(s))); }
    hud.appendChild(el("div", "where", s.body || s.system || "Not on a body"));
    if (s.system && s.body) { hud.appendChild(el("div", "system", s.system)); }
    var session = s.session || {};
    var title = session.running ? (session.paused ? "SESSION - PAUSED" : "SESSION") : "LAST SESSION";
    if (!session.running && !session.seconds) { title = "NO SESSION RUNNING"; }
    hud.appendChild(row(title, session.seconds ? session.clock : ""));
    if (s.tonnes_total) {
      hud.appendChild(row("MINED", number(s.tonnes_total) + " t"));
      (s.tonnes || []).slice(0, 6).forEach(function (t) {
        var line = el("div", "item");
        line.appendChild(el("span", "", t.commodity));
        line.appendChild(el("span", "", number(t.tonnes) + " t"));
        hud.appendChild(line);
      });
    }
    if (s.cr_hr) { hud.appendChild(row("CR/HR", s.cr_hr_text, "good")); }
    if (s.merits) { hud.appendChild(row("MERITS", (s.merits_estimated ? "est. " : "") + number(s.merits))); }
    if (s.rigs_down) { hud.appendChild(row("RIGS DOWN", s.rigs_down)); }
    if (s.nearest) {
      var n = s.nearest;
      hud.appendChild(row("NEAREST", n.commodity));
      hud.appendChild(el("div", "item note", n.distance + "   " + ("00" + n.bearing).slice(-3) + "\\u00b0 " + n.compass));
    }
  }"""

_VIEWER_STYLE = """body { font-size: 22px; }
#hud { box-sizing: border-box; width: 420px; margin: 8px; padding: 14px 18px 16px;
       background: var(--panel); border-top: 5px solid var(--orange); border-radius: 4px;
       transition: opacity 0.6s; }
.cmdr { font-size: 28px; font-weight: bold; color: var(--orange); letter-spacing: 1px; }
.what { font-size: 24px; color: var(--amber); margin-top: 4px; }
.where { font-size: 22px; color: var(--dim); margin-bottom: 8px; }
.label { font-size: 20px; }
.ago { font-size: 20px; color: var(--dim); }"""

_VIEWER_PAINT = """  function paint(s) {
    theme(s, 0.85);
    hud.appendChild(el("div", "cmdr", cmdr(s) || "EDSMT"));
    var mining = (s.mining || []).join(", ");
    hud.appendChild(el("div", "what", mining ? "Mining " + mining : "Not mining yet"));
    var body = String(s.body || ""), system = String(s.system || "");
    var where = body || system;
    if (body && system && body.toLowerCase().indexOf(system.toLowerCase()) !== 0) { where = body + " / " + system; }
    if (where) { hud.appendChild(el("div", "where", where)); }
    hud.appendChild(row("THIS SESSION", number(s.tonnes_total) + " t"));
    if (s.cr_hr) { hud.appendChild(row("CR/HR", s.cr_hr_text, "good")); }
    var f = s.last_find;
    if (f) {
      var bits = [f.commodity];
      if (f.amount) { bits.push(f.amount); }
      if (f.rigs) { bits.push(f.rigs + "R"); }
      hud.appendChild(row("LAST FIND", bits.join("  ")));
      hud.appendChild(el("div", "ago", [f.where, f.ago].filter(function (w) { return w; }).join(" - ")));
    }
  }"""

OVERLAY_PAGE = _HEAD % ("EDSMT - Rhino session", _OVERLAY_STYLE, _OVERLAY_PAINT)
VIEWER_PAGE = _HEAD % ("EDSMT - viewer card", _VIEWER_STYLE, _VIEWER_PAINT)

# The browser is told the same thing the pages promise: their own address
# and nothing else.
PAGE_POLICY = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
               "connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'")


# -- the server ----------------------------------------------------------------

class _Handler(http.server.BaseHTTPRequestHandler):
    """Four addresses, GET and HEAD only, nothing written to a console."""

    server_version = "EDSMT"
    sys_version = ""
    timeout = 5

    def log_message(self, *_args):
        # A windowed exe has no console to write to; nothing is logged.
        return

    def _send(self, status, kind, data, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _host_ok(self):
        """Only this PC's own names for itself. A web page elsewhere that
        points its own name at 127.0.0.1 is still another site."""
        host = str(self.headers.get("Host") or "").strip().lower()
        port = self.server.server_address[1]
        return host in ("127.0.0.1", "localhost", "127.0.0.1:%d" % port,
                        "localhost:%d" % port)

    def do_GET(self):
        stream = self.server.stream
        if not self._host_ok():
            return self._send(403, "text/plain; charset=utf-8", b"Not from here.")
        path = urllib.parse.urlsplit(self.path).path
        if path in ("/", "/overlay", "/viewer"):
            page = VIEWER_PAGE if path == "/viewer" else OVERLAY_PAGE
            return self._send(200, "text/html; charset=utf-8", page.encode("utf-8"),
                              {"Content-Security-Policy": PAGE_POLICY})
        if path == "/state.json":
            return self._send(200, "application/json; charset=utf-8", stream.state_bytes())
        if path == "/card.png":
            card = stream.card_bytes()
            if card:
                return self._send(200, "image/png", card)
        return self._send(404, "text/plain; charset=utf-8", b"Not found.")

    # HEAD is GET without the body; _send leaves it out.
    do_HEAD = do_GET

    def _refuse(self):
        return self._send(405, "text/plain; charset=utf-8", b"GET only.", {"Allow": "GET, HEAD"})

    do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _refuse


class _Listener(http.server.ThreadingHTTPServer):
    daemon_threads = True
    # On Windows the reuse flag lets a second program bind a port that is
    # already in use, silently; elsewhere it only lets a port be used again
    # straight after it was let go.
    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        # The standard one looks this PC's name up, which can wait on the
        # network; the name is known.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = HOST, self.server_address[1]

    def handle_error(self, request, client_address):
        # A browser that goes away mid-answer is not news, and a windowed
        # exe has nowhere to print it.
        return


class StreamServer:
    """The web server for OBS: on 127.0.0.1 and nowhere else, in a daemon
    thread, holding the latest state and card the app has handed it. The
    app publishes from its own thread; the server never reaches into it."""

    def __init__(self, host=HOST, port=DEFAULT_PORT):
        if host != HOST:
            raise ValueError("The OBS page is served on %s only, never on %r." % (HOST, host))
        self.host = host
        self.port = int(port or 0)
        self._lock = threading.Lock()
        self._state = json.dumps(stream_state()).encode("utf-8")
        self._card = b""
        self._listener = None
        self._thread = None
        self._wanted = None
        self._failed_at = 0.0
        self.published_at = 0.0

    @property
    def running(self):
        return self._listener is not None

    def address(self):
        """(host, port) the server is listening on, or None."""
        listener = self._listener
        return tuple(listener.server_address[:2]) if listener is not None else None

    def url(self, path="/overlay"):
        return page_url(self.port, path)

    def start(self):
        """Listen. (True, "") when it is up, (False, why) when not. Never raises."""
        if self.running:
            return True, ""
        try:
            listener = _Listener((self.host, self.port), _Handler)
        except OSError as exc:
            if getattr(exc, "errno", None) in (98, 48, 10048) or getattr(exc, "winerror", None) == 10048:
                return False, ("port %d is in use by another program - pick another "
                               "in Settings > Overlay." % self.port)
            return False, "port %d could not be opened: %s" % (self.port, exc)
        listener.stream = self
        self._listener = listener
        self.port = int(listener.server_address[1])
        self._thread = threading.Thread(target=listener.serve_forever,
                                        kwargs={"poll_interval": 0.2},
                                        name="edsmt-stream", daemon=True)
        self._thread.start()
        return True, ""

    def stop(self):
        """Stop listening and let the port go. Safe to call at any time."""
        listener, self._listener = self._listener, None
        if listener is None:
            return
        try:
            listener.shutdown()
        finally:
            listener.server_close()
            self._thread = None

    def follow(self, on, port, now=None):
        """Make the server match the settings: started, stopped or moved to
        another port. Returns a sentence when something changed (or could
        not), "" when nothing did. A port that will not open is said once,
        then tried again quietly every RETRY_S - never on every tick."""
        now = time.time() if now is None else now
        wanted = (bool(on), port)
        if wanted == self._wanted:
            if not (on and port is not None and not self.running and self._failed_at
                    and now - self._failed_at >= RETRY_S):
                return ""
            self.port = int(port)
            ok, _why = self.start()
            if not ok:
                self._failed_at = now
                return ""
            self._failed_at = 0.0
            return "OBS browser source on: %s" % self.url()
        self._wanted = wanted
        self._failed_at = 0.0
        if not on:
            if not self.running:
                return ""
            self.stop()
            return "OBS browser source off."
        if port is None:
            self.stop()
            return "The OBS browser source needs a port from %d to %d." % (PORT_MIN, PORT_MAX)
        if self.running and self.port == port:
            return ""
        self.stop()
        self.port = int(port)
        ok, why = self.start()
        if not ok:
            self._failed_at = now
            return "OBS browser source could not start: %s" % why
        return "OBS browser source on: %s" % self.url()

    def publish(self, state, now=None):
        """Hand the server the state to show."""
        data = json.dumps(state).encode("utf-8")
        with self._lock:
            self._state = data
        self.published_at = time.time() if now is None else now

    def publish_card(self, data):
        """Hand the server the latest session card, as PNG bytes."""
        with self._lock:
            self._card = bytes(data or b"")

    def state_bytes(self):
        with self._lock:
            return self._state

    def card_bytes(self):
        with self._lock:
            return self._card

    def due(self, now=None):
        """True when the state is worth building again."""
        now = time.time() if now is None else now
        return now - self.published_at >= STATE_EVERY_S
