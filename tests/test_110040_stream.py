"""1.10040: the session on a stream - an OBS browser source served on this
PC (#149), the session card (#151), the Twitch viewer card (#307) and the
overlay made for a stream (#148).

- Settings > Overlay > Streaming: "Serve an OBS browser source on this PC"
  (off), the port (8765), Copy buttons for the /overlay and /viewer
  addresses, and "Text shadow for streaming" (off).
- The pages are served on 127.0.0.1 only and fetch nothing but their own
  /state.json - no font, script or picture from anywhere. The state holds
  the CMDR name and nothing else about the commander, and no position on a
  body. Streamer mode hides the system and body on them as it does on
  screen - the app's own rule, not a copy of it.
- A Session card button on Earnings (and a card button on each session's
  row) saves the session as a picture in the pictures folder; /card.png is
  the latest. Each Discord webhook has a Session card switch (off) to send
  it with the summary; a settings file from before keeps working.
- The streamer layout raises its boxes' text to 130% so nothing on a 1080p
  capture is under 10 pt, and the text shadow draws a solid dark outline
  behind the overlay's words.

The state, the server and the card are checked as plain code first, then
the app on the real toolkit. Every place and commander is made up, and
nothing leaves this machine: the only connections are to 127.0.0.1.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_stream.py
"""
import os, sys, json, time, re, tempfile, socket, collections, urllib.request, urllib.error
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-stream40-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

# Loopback only, from the first line: the server is checked over 127.0.0.1
# and nothing else may be reached.
_real_connect = socket.socket.connect


def _loopback_only(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6) and \
            not str(address[0]).startswith(("127.", "::1", "localhost")):
        raise OSError("this check stays on this machine")
    return _real_connect(self, address)


socket.socket.connect = _loopback_only

import streamout as SO     # noqa: E402
import streamer as ST      # noqa: E402

fails = []
NOW = 1792540800.0         # 21 Oct 2026 00:00 UTC


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def section(title):
    def wrap(fn):
        print("== " + title + " ==")
        try:
            fn()
        except Exception as exc:
            import traceback
            check(title + " (ran to the end)", False, "%s: %s" % (type(exc).__name__, exc))
            traceback.print_exc(limit=6)
        return fn
    return wrap


NEAR = [
    {"range_m": 896.0, "bearing": 350.0, "lat": 10.25, "lon": 20.5,
     "deposit": {"id": "a", "commodity": "Platinum", "amount": "High", "lat": 10.25,
                 "lon": 20.5, "cmdr": "CMDR Other", "found_by": "CMDR Other"}},
    {"range_m": 120.0, "bearing": 90.0, "lat": 10.2, "lon": 20.4,
     "deposit": {"id": "b", "commodity": "Gold", "amount": "Depleted", "lat": 10.2, "lon": 20.4}},
    {"range_m": 420.4, "bearing": 33.0, "lat": 10.1, "lon": 20.3,
     "deposit": {"id": "c", "commodity": "osmium", "amount": "Medium", "lat": 10.1, "lon": 20.3,
                 "cmdr": "CMDR Other"}},
]
FINDS = [
    {"commodity": "Gold", "amount": "Low", "rigs": "2", "system": "Ega", "body": "Ega 2",
     "lat": "1.11", "lon": "2.22", "recorded": "2026-10-20T22:00:00Z", "cmdr": "Cee"},
    {"commodity": "platinum", "amount": "High", "rigs": "4", "system": "Ega", "body": "Ega 1",
     "lat": "3.33", "lon": "4.44", "recorded": "2026-10-20T23:48:00Z", "cmdr": "Cee"},
    {"commodity": "Osmium", "recorded": "", "lat": "5.55", "lon": "6.66"},
]


def full_state(**extra):
    args = dict(cmdr="CMDR Cee", system="Ega", body="Ega 1",
                mined={"Platinum": 34, "Osmium": 6, "Gold": 0}, seconds=3723,
                running=True, paused=False, cr_hr=12345678.4, merits=1200,
                merits_estimated=False, rigs_down=4, near=NEAR,
                find=SO.last_find(FINDS, now=NOW), now=NOW)
    args.update(extra)
    return SO.stream_state(**args)


@section("streamout: the state the pages show")
def _state():
    state = full_state()
    check("whose, and where", (state["cmdr"], state["system"], state["body"]) == ("CMDR Cee", "Ega", "Ega 1"),
          state)
    check("tonnes this session by commodity, the most first, nothing for none",
          state["tonnes"] == [{"commodity": "Platinum", "tonnes": 34}, {"commodity": "Osmium", "tonnes": 6}]
          and state["tonnes_total"] == 40, state["tonnes"])
    check("what is being mined, for the viewer card", state["mining"] == ["Platinum", "Osmium"], state["mining"])
    check("the session clock, running", state["session"] == {"running": True, "paused": False,
                                                             "seconds": 3723, "clock": "1:02:03"},
          state["session"])
    check("credits an hour, whole, and as it reads",
          state["cr_hr"] == 12345678 and state["cr_hr_text"] == "12,345,678", state)
    check("merits earned this session", state["merits"] == 1200 and state["merits_estimated"] is False)
    check("rigs down", state["rigs_down"] == 4)
    check("the nearest deposit that is not worked out, with distance and bearing",
          state["nearest"] == {"commodity": "Osmium", "distance_m": 420, "distance": "420 m",
                               "bearing": 33, "compass": "NNE"}, state["nearest"])
    check("the last find: the newest, what it was, where and how long ago",
          state["last_find"] == {"commodity": "Platinum", "amount": "High", "rigs": 4, "where": "Ega 1",
                                 "ago_s": 720, "ago": "12 min ago"}, state["last_find"])
    check("stamped", state["updated"] == "2026-10-21T00:00:00Z", state["updated"])
    words = json.dumps(state)
    check("no position on the body anywhere in it", not re.search(r'"(lat|lon|latitude|longitude)"', words)
          and not any(n in words for n in ("10.1", "20.3", "10.25", "3.33", "4.44", "1.11")), words)
    check("nothing about another commander", "CMDR Other" not in words)
    check("and nothing about this one but the name", set(state) == {
        "app", "cmdr", "system", "body", "session", "tonnes", "tonnes_total", "mining", "cr_hr",
        "cr_hr_text", "merits", "merits_estimated", "rigs_down", "nearest", "last_find", "colours",
        "updated", "schema", "version"}, sorted(state))


@section("streamout: when there is less to show")
def _less():
    quiet = SO.stream_state(now=NOW)
    check("no session: nothing running, nothing mined, a zero clock",
          quiet["session"] == {"running": False, "paused": False, "seconds": 0, "clock": "0:00:00"}
          and quiet["tonnes"] == [] and quiet["tonnes_total"] == 0 and quiet["mining"] == [], quiet)
    check("no merits is None, not 0, so the page can leave the line out",
          quiet["merits"] is None and full_state(merits=0)["merits"] is None)
    check("estimated merits say so", full_state(merits=900.6, merits_estimated=True)["merits"] == 901
          and full_state(merits=900.6, merits_estimated=True)["merits_estimated"] is True)
    check("no deposits near: no nearest", quiet["nearest"] is None
          and full_state(near=[NEAR[1]])["nearest"] is None)
    check("no finds: no last find", quiet["last_find"] is None and SO.last_find([]) is None
          and SO.last_find([{"commodity": "Gold"}]) is None)
    check("a paused clock says so", full_state(paused=True)["session"]["paused"] is True)
    junk = SO.stream_state(mined={"Platinum": "x", "Gold": -3, "": 5, "Osmium": "7"}, seconds=-40,
                           cr_hr="lots", rigs_down="9", near=[{"range_m": "far"}, None, 5], now=NOW)
    check("junk in, nothing silly out", junk["tonnes"] == [{"commodity": "Osmium", "tonnes": 7}]
          and junk["session"]["seconds"] == 0 and junk["cr_hr"] == 0 and junk["rigs_down"] == 9
          and junk["nearest"] is None, junk)
    check("a long day keeps counting hours", full_state(seconds=36 * 3600 + 61)["session"]["clock"] == "36:01:01")
    check("kilometres past a kilometre", SO.nearest_deposit([{"range_m": 1263.0, "bearing": 359.6,
                                                              "deposit": {"commodity": "Gold"}}])
          == {"commodity": "Gold", "distance_m": 1263, "distance": "1.26 km", "bearing": 0, "compass": "N"})
    check("how long ago, in a few words", [SO.ago_text(s) for s in (5, 61, 3 * 3600 + 5, 5 * 86400)]
          == ["just now", "1 min ago", "3 h ago", "5 days ago"])


@section("streamout: streamer mode hides the names the app hides, by the app's rule")
def _hidden():
    names = [("Ega 1", ST.cover("body")), ("Ega", ST.cover("system", 287.4))]

    def hide(text):
        return ST.hide(text, names)
    state = full_state(hide=hide)
    check("the system and body read as streamer mode has them",
          state["system"] == "a system 290 Ly from Sol" and state["body"] == "a body",
          (state["system"], state["body"]))
    check("and so does where the last find was", state["last_find"]["where"] == "a body",
          state["last_find"])
    check("nowhere in the JSON is either name", not re.search(r"\bEga\b", json.dumps(state)),
          json.dumps(state)[:300])
    check("the find on another body of the system keeps only its own letters",
          SO.last_find(FINDS[:1], hide=hide, now=NOW)["where"] == "a system 290 Ly from Sol 2")
    check("with nothing hidden, the names are there", full_state(hide=lambda t: t)["body"] == "Ega 1")


@section("streamout: the theme's colours, and only colours")
def _colours():
    state = full_state(colours={"ORANGE": "#4fe3d0", "TEXT": "#d8f3ef", "AMBER": "not a colour",
                                "VOID": "#03100f", "EVIL": "#ffffff", "DIM": "url(x)"})
    colours = state["colours"]
    check("the theme's own where given", colours["orange"] == "#4fe3d0" and colours["text"] == "#d8f3ef"
          and colours["void"] == "#03100f", colours)
    check("the cockpit's where not, or where it is not a colour",
          colours["amber"] == "#ffb545" and colours["dim"] == "#9c6a3c", colours)
    check("nothing else gets in", "evil" not in colours and all(
        re.fullmatch(r"#[0-9a-f]{6}", v) for v in colours.values()), colours)


@section("streamout: the port")
def _port():
    check("the default", SO.DEFAULT_PORT == 8765 and SO.parse_port("") == 8765 and SO.parse_port(None) == 8765)
    check("a number in range", SO.parse_port("9000") == 9000 and SO.parse_port(" 8766 ") == 8766
          and SO.parse_port(49152) == 49152)
    check("not below 1024, not above 65535, not words",
          SO.parse_port("80") is None and SO.parse_port("70000") is None and SO.parse_port("abc") is None
          and SO.parse_port("8765.5") is None)
    check("the addresses for OBS", SO.page_url(8765) == "http://127.0.0.1:8765/overlay"
          and SO.page_url(8765, "/viewer") == "http://127.0.0.1:8765/viewer")


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def fetch(port, path, host=None, method="GET"):
    """(status, headers, body) for one request to the server."""
    request = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path), method=method)
    if host:
        request.add_header("Host", host)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=5) as answer:
            return answer.status, dict(answer.headers), answer.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def outside_address():
    """This machine's own address on a network, or None when it has only
    the loopback. Nothing is sent: a UDP socket only picks a route."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            _real_connect(probe, ("10.255.255.255", 1))
            address = probe.getsockname()[0]
    except OSError:
        return None
    return None if address.startswith("127.") or address == "0.0.0.0" else address


# Anything a page could fetch from somewhere else: an address, a font, a
# script, a picture, a style sheet or a frame.
EXTERNAL = re.compile(r"https?:|//[a-z0-9]|\bsrc\s*=|\bhref\s*=|@import|url\(|<link|<iframe|<img"
                      r"|@font-face", re.I)


@section("streamout: the web server, on this PC only")
def _server():
    for host in ("0.0.0.0", "", "192.168.1.5", "localhost", "::"):
        try:
            SO.StreamServer(host=host, port=free_port())
            refused = False
        except ValueError:
            refused = True
        check("refuses to listen on %r" % host, refused)
    server = SO.StreamServer(port=0)
    port = 0
    try:
        ok, why = server.start()
        check("starts on a free port", ok and why == "" and server.running and server.port > 0, (ok, why))
        check("bound to 127.0.0.1 and nothing else", server.address()[0] == "127.0.0.1", server.address())
        port = server.port
        outside = outside_address()
        if outside:
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            probe.settimeout(2)
            try:
                _real_connect(probe, (outside, port))
                reached = True
            except OSError:
                reached = False
            finally:
                probe.close()
            check("not reachable on this machine's network address", not reached, outside)
        status, headers, body = fetch(port, "/state.json")
        quiet = json.loads(body)
        check("the state before anything is published: an empty session",
              status == 200 and headers.get("Content-Type", "").startswith("application/json")
              and quiet["app"] == "EDSMT" and quiet["tonnes"] == [] and quiet["session"]["running"] is False,
              (status, headers, body[:200]))
        state = full_state()
        server.publish(state)
        status, headers, body = fetch(port, "/state.json")
        check("then exactly what was published", status == 200 and json.loads(body) == state, body[:200])
        check("never cached", "no-store" in headers.get("Cache-Control", ""), headers)
        for path in ("/overlay", "/viewer"):
            status, headers, page = fetch(port, path)
            page = page.decode("utf-8")
            check("%s is a page" % path, status == 200 and headers.get("Content-Type", "").startswith("text/html")
                  and page.lstrip().lower().startswith("<!doctype html>"), (status, headers))
            check("%s reads the state once a second" % path, '"state.json"' in page and "1000" in page)
            check("%s makes no external request of any kind - no address, font, script or picture" % path,
                  not EXTERNAL.findall(page), EXTERNAL.findall(page)[:5])
            policy = headers.get("Content-Security-Policy", "")
            check("%s: and the browser is told so" % path, "default-src 'none'" in policy
                  and "connect-src 'self'" in policy, headers)
            check("%s is on a transparent background" % path,
                  re.search(r"html, body \{[^}]*background\s*:\s*transparent", page) is not None)
            check("%s wears the theme's colours, set from the state" % path,
                  "--orange" in page and "s.colours" in page)
            sizes = [int(n) for n in re.findall(r"font-size\s*:\s*(\d+)px", page)]
            check("%s is big enough to read on a 1080p capture (%s)" % (path, sorted(set(sizes))),
                  sizes and min(sizes) >= (22 if path == "/overlay" else 20))
            check("%s writes what it is sent as text, never as markup" % path,
                  "innerHTML" not in page and "textContent" in page and "insertAdjacent" not in page)
            check("%s names no position either" % path, not re.search(r"\b(lat|lon)\b", page))
        _s, _h, viewer = fetch(port, "/viewer")
        viewer = viewer.decode("utf-8")
        check("the viewer card: CMDR, what is mined and where, tonnes, Cr/hr and the last find",
              all(w in viewer for w in ("cmdr(s)", "s.mining", "s.body", "s.system", "s.tonnes_total",
                                        "s.cr_hr_text", "s.last_find")))
        _s, _h, overlay = fetch(port, "/overlay")
        overlay = overlay.decode("utf-8")
        check("the overlay page: body and system, tonnes, Cr/hr, merits, rigs down, nearest, the clock",
              all(w in overlay for w in ("s.body", "s.system", "s.tonnes", "s.cr_hr_text", "s.merits",
                                         "s.rigs_down", "s.nearest", "session.clock")))
        status, _headers, _body = fetch(port, "/card.png")
        check("no card yet: not found", status == 404, status)
        png = b"\x89PNG\r\n\x1a\n" + b"card" * 10
        server.publish_card(png)
        status, headers, body = fetch(port, "/card.png")
        check("then the card", status == 200 and headers.get("Content-Type") == "image/png" and body == png,
              (status, headers))
        check("anything else is not found", fetch(port, "/settings.json")[0] == 404
              and fetch(port, "/../edsmt.py")[0] == 404)
        check("only GET and HEAD", fetch(port, "/state.json", method="POST")[0] == 405
              and fetch(port, "/state.json", method="HEAD")[0] == 200)
        check("another site's address pointed at this PC is turned away",
              fetch(port, "/state.json", host="evil.example:%d" % port)[0] == 403)
        check("localhost by name is fine", fetch(port, "/state.json", host="localhost:%d" % port)[0] == 200)
        import io, contextlib
        spoken = io.StringIO()
        with contextlib.redirect_stderr(spoken):
            server._listener.handle_error(None, ("127.0.0.1", 1))
        check("a browser going away mid-answer prints nothing - a windowed exe has nowhere to",
              spoken.getvalue() == "", spoken.getvalue()[:200])
        other = SO.StreamServer(port=port)
        ok2, why2 = other.start()
        check("a port already taken says so, and does not raise", not ok2 and str(port) in why2
              and "in use" in why2 and not other.running, (ok2, why2))
    finally:
        server.stop()
    check("stopped: gone", not server.running)
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.settimeout(2)
    try:
        probe.connect(("127.0.0.1", port))
        still = True
    except OSError:
        still = False
    finally:
        probe.close()
    check("and nothing answers on its port", not still)


@section("streamout: following the switch and the port")
def _follow():
    server = SO.StreamServer()
    port = free_port()
    try:
        said = server.follow(True, port, now=NOW)
        check("on: starts, and says where", server.running and server.port == port
              and SO.page_url(port) in said, said)
        check("nothing changed: nothing said", server.follow(True, port, now=NOW + 1) == "")
        port2 = free_port()
        said = server.follow(True, port2, now=NOW + 2)
        check("a new port: moves to it", server.running and server.port == port2 and str(port2) in said, said)
        said = server.follow(False, port2, now=NOW + 3)
        check("off: stops, and says so", not server.running and "off" in said.lower(), said)
        check("off and off: nothing", server.follow(False, port2, now=NOW + 4) == "")
        blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        taken = blocker.getsockname()[1]
        try:
            said = server.follow(True, taken, now=NOW + 5)
            check("a port in use: says so once", not server.running and "in use" in said, said)
            check("and does not try again every tick", server.follow(True, taken, now=NOW + 6) == ""
                  and server.follow(True, taken, now=NOW + 5 + SO.RETRY_S - 1) == "")
        finally:
            blocker.close()
        said = server.follow(True, taken, now=NOW + 5 + SO.RETRY_S)
        check("once it is free, the next quiet try takes it", server.running and server.port == taken
              and str(taken) in said, said)
        check("a bad port is not tried", server.follow(True, None, now=NOW + 99) != "" and not server.running)
    finally:
        server.stop()


import sessioncard as SC  # noqa: E402
import mapimage as MI     # noqa: E402

ROW = {"id": "s1", "system": "Ega", "body": "Ega 1", "cmdr": "Cee",
       "started": "2026-10-21T02:48:00Z", "ended": "2026-10-21T05:18:00Z",
       "closed": "2026-10-21T05:18:00Z", "mined": "Platinum:34;Osmium:6", "credits": "0"}


@section("sessioncard: what a session card says")
def _facts():
    facts = SC.card_facts(ROW, "Cee", estimate={"value": 25000000.0}, merits=1200)
    check("whose, where and when", (facts["cmdr"], facts["body"], facts["system"], facts["date"])
          == ("Cee", "Ega 1", "Ega", "21 Oct 2026") and facts["span"] == "02:48 to 05:18 UTC", facts)
    check("tonnes by commodity, the most first", facts["tonnes"] == [("Platinum", 34), ("Osmium", 6)]
          and facts["tonnes_total"] == 40, facts["tonnes"])
    check("not sold yet: the estimate, said to be one", facts["credits"] == 25000000
          and facts["credits_estimated"] is True and facts["cr_hr"] == 10000000, facts)
    check("time mined", facts["time_mined"] == "2h 30m" and facts["merits"] == 1200)
    sold = SC.card_facts(dict(ROW, credits="30000000"), "Cee", estimate={"value": 30000000.0})
    check("sold: what it sold for, no estimate", sold["credits"] == 30000000
          and sold["credits_estimated"] is False and sold["cr_hr"] == 12000000, sold)
    check("no merits: none", sold["merits"] is None)
    check("a row on its own still makes a card", SC.card_facts({"mined": "Gold:3"})["tonnes"] == [("Gold", 3)])
    hidden = SC.card_facts(ROW, "Cee", hide=lambda t: ST.hide(t, [("Ega 1", "a body"), ("Ega", "a system")]))
    check("with streamer mode's rule, the names it hides", (hidden["body"], hidden["system"])
          == ("a body", "a system"), hidden)
    texts = SC.render_card(facts)[1]
    for words in ("CMDR Cee", "Ega 1", "Ega", "21 Oct 2026", "Platinum", "34 t", "40 t",
                  "est. 25,000,000 Cr", "est. 10,000,000", "1,200", "2h 30m"):
        check("the card writes %r" % words, words in texts, texts)
    check("no merits, no merits box", "MERITS" not in SC.render_card(sold)[1] and "MERITS" in texts)
    check("named like a picture, so it is tidied with them - by the real names",
          re.match(r".+_\d{8}-\d{4}\.png$", SC.card_name(ROW))
          and SC.card_name(ROW) == "card_Ega_Ega_1_20261021-0248.png", SC.card_name(ROW))


def fake_map(size=MI.SIZE):
    """A map picture: green where the title and legend go, red plot."""
    from PIL import Image, ImageDraw
    image = Image.new("RGB", size, (0, 255, 0))
    scale = size[0] / float(MI.SIZE[0])
    side = MI.SIZE[1] - 150
    ImageDraw.Draw(image).rectangle([int(24 * scale), int(96 * scale),
                                     int((24 + side) * scale) - 1, int((96 + side) * scale) - 1],
                                    fill=(255, 0, 0))
    return image


def colours_in(image, box):
    return {colour for _n, colour in image.crop(box).getcolors(1 << 22)}


@section("sessioncard: the picture")
def _picture():
    ok, why = MI.pillow_status()
    check("Pillow is here (it ships with the app)", ok, why)
    facts = SC.card_facts(ROW, "Cee", estimate={"value": 25000000.0}, merits=1200)
    with_map, _texts = SC.render_card(facts, fake_map())
    plain, _texts = SC.render_card(facts)
    check("the size a stream or Discord shows well", with_map.size == SC.SIZE == plain.size == (1200, 675),
          (with_map.size, plain.size))
    x0, y0, x1, y1 = SC.MAP_BOX
    inside = colours_in(with_map, (x0 + 20, y0 + 20, x1 - 20, y1 - 20))
    check("the map is drawn in as a thumbnail when there is one", inside == {(255, 0, 0)}, inside)
    check("only the map itself - not the title with the names, nor the legend",
          not any(c[1] > 200 and c[0] < 80 for c in colours_in(with_map, (0, 0) + SC.SIZE)))
    check("and nothing of it when there is none",
          not any(c == (255, 0, 0) for c in colours_in(plain, (0, 0) + SC.SIZE)))
    framed, _t = SC.render_card(facts, fake_map((300, 900)))
    raw = framed.tobytes()
    reds = [i // 3 for i in range(0, len(raw), 3) if raw[i:i + 3] == b"\xff\x00\x00"]
    xs = {i % SC.SIZE[0] for i in reds}
    ys = {i // SC.SIZE[0] for i in reds}
    check("a picture of another shape keeps its shape and stays in its box",
          reds and min(xs) >= x0 and max(xs) <= x1 and min(ys) >= y0 and max(ys) <= y1
          and (max(xs) - min(xs)) < (max(ys) - min(ys)), (min(xs), max(xs), min(ys), max(ys)))
    badge = SC.load_badge(os.path.join(REPO, "images", "edsmt-badge-256.png"))
    check("the EDSMT badge loads", badge is not None and badge.size == (256, 256))
    check("and a badge that is not there is none, not a fault",
          SC.load_badge(os.path.join(TMP, "no-badge.png")) is None)
    marked, _t = SC.render_card(facts, badge=badge)
    corner = (SC.SIZE[0] - 24 - SC.BADGE_PX, SC.SIZE[1] - 16 - SC.BADGE_PX, SC.SIZE[0] - 24, SC.SIZE[1] - 16)
    check("the badge, small, in the bottom corner", colours_in(marked, corner) != colours_in(plain, corner)
          and marked.crop((0, 0, 900, 400)).tobytes() == plain.crop((0, 0, 900, 400)).tobytes())
    many = SC.card_facts(dict(ROW, mined=";".join("Thing%d:%d" % (i, 20 - i) for i in range(14))), "Cee")
    _img, many_texts = SC.render_card(many)
    check("a long list is cut, and says how many more", "+ 6 more" in many_texts, many_texts)
    long = SC.card_facts(dict(ROW, body="Col 285 Sector ZL-K b22-2 A 1 a very long body name indeed",
                              system="Col 285 Sector ZL-K b22-2"), "A Commander With A Long Name")
    image, _t = SC.render_card(long, fake_map(), badge=badge)
    check("long names draw without trouble", image.size == SC.SIZE)


@section("sessioncard: the session's own map picture, from the pictures folder")
def _find_map():
    folder = os.path.join(TMP, "pictures-find")
    os.makedirs(folder, exist_ok=True)
    first, last = SC.SV._epoch(ROW["started"]), SC.SV._epoch(ROW["ended"])

    def made(name):
        path = os.path.join(folder, name)
        with open(path, "wb") as handle:
            handle.write(b"png")
        return path

    check("an empty folder: none", SC.find_map(folder, "Ega", "Ega 1", first, last) == "")
    check("no folder at all: none", SC.find_map(os.path.join(TMP, "nowhere"), "Ega", "Ega 1",
                                                first, last) == "")
    made("Ega_Ega_1_0_20261020-2200.png")
    made("Ega_Ega_2_0_20261021-0400.png")
    made("card_Ega_Ega_1_20261021-0448.png")
    check("another day, another body or a card is not the map",
          SC.find_map(folder, "Ega", "Ega 1", first, last) == "")
    early = made("Ega_Ega_1_0_20261021-0330.png")
    late = made("Ega_Ega_1_A_20261021-0518.png")
    check("the last one taken on that body while the session ran",
          SC.find_map(folder, "Ega", "Ega 1", first, last) == late)
    check("a session still running looks up to now", SC.find_map(folder, "Ega", "Ega 1", first, 0) == late)
    os.remove(late)
    check("or the one before it", SC.find_map(folder, "Ega", "Ega 1", first, last) == early)
    check("no start: none", SC.find_map(folder, "Ega", "Ega 1", 0, last) == "")


import edonline as EDO    # noqa: E402
import webhooks as WH     # noqa: E402

HOOK = "https://discord.com/api/webhooks/%s/%s" % ("123456789012345678", "T0ken" + "x" * 63)


@section("Discord: the card goes up beside the map, in the same message")
def _discord_files():
    sent = []
    real = EDO.post_multipart
    EDO.post_multipart = lambda url, payload, files, timeout=40.0, method="POST": (
        sent.append((url, payload, files)) or {"id": "1", "attachments": []})
    try:
        EDO.discord_post_file(HOOK, {"content": "x"}, "map.png", b"m")
        check("one picture, as before", sent[-1][1]["attachments"] == [{"id": 0, "filename": "map.png"}]
              and [f[0] for f in sent[-1][2]] == ["map.png"], sent[-1])
        EDO.discord_post_file(HOOK, {"content": "x"}, "map.png", b"m", more=[("card.png", b"c")])
        url, payload, files = sent[-1]
        check("and a second, numbered after it", payload["attachments"] == [
            {"id": 0, "filename": "map.png"}, {"id": 1, "filename": "card.png"}]
            and files == [("map.png", b"m", "image/png"), ("card.png", b"c", "image/png")], sent[-1])
        check("to the same webhook, waiting for the message", url == HOOK + "?wait=true")
    finally:
        EDO.post_multipart = real
    check("each webhook has a Session card switch, off for a new one",
          "card" in WH.KINDS and WH.NEW_ROW["card"] is False and WH.entry("x", HOOK)["card"] is False)
    old = [{"name": "Radio Raxxla", "url": HOOK, "finds": False, "sessions": True, "map": True}]
    check("a webhook saved before the switch existed reads with it off, the rest as it was",
          WH.clean(old) == [dict(old[0], card=False)], WH.clean(old))
    check("the card goes only to the webhooks with it on",
          [r["name"] for r in WH.wanted([WH.entry("A", HOOK, card=True), WH.entry("B", HOOK)], "card",
                                        lambda u: True)] == ["A"])


import overlay as OV      # noqa: E402


class FakeCanvas:
    def __init__(self):
        self.texts, self.n = [], 0

    def create_text(self, *args, **kwargs):
        self.n += 1
        self.texts.append((self.n, args, kwargs))
        return self.n

    def create_line(self, *args, **kwargs):
        return "line"


@section("overlay: a dark outline behind the words, for a stream (#148)")
def _shadow():
    canvas = FakeCanvas()
    check("off and at 100%: the canvas itself, as before",
          OV.scaled_canvas(canvas, 1.0) is canvas and OV.scaled_canvas(canvas, 1.0, shadow=False) is canvas)
    shaded = OV.scaled_canvas(canvas, 1.0, shadow=True)
    got = shaded.create_text(100, 50, text="IRIDIUM 420m", fill="#ff7a18", anchor="w",
                             font=("Consolas", 10, "bold"), tags=("tape",))
    behind, words = canvas.texts[:-1], canvas.texts[-1]
    check("the words are drawn last, as asked, and theirs is the item answered",
          got == words[0] and words[1] == (100, 50) and words[2]["fill"] == "#ff7a18"
          and words[2]["tags"] == ("tape",), words)
    check("with a copy behind them a pixel off on every side",
          len(behind) == len(OV.SHADOW_OFFSETS) == 4
          and {(a[0] - 100, a[1] - 50) for _n, a, _k in behind} == {(-1, 0), (1, 0), (0, -1), (0, 1)},
          [a for _n, a, _k in behind])
    check("solid and dark, never the see-through colour, with the same words and font",
          all(k["fill"] == OV.SHADOW and k["text"] == "IRIDIUM 420m" and k["font"] == ("Consolas", 10, "bold")
              and k["anchor"] == "w" for _n, _a, k in behind)
          and OV.SHADOW.lower() != OV.CHROMA.lower() and re.fullmatch(r"#[0-9a-f]{6}", OV.SHADOW),
          behind[:1])
    check("tagged as a shadow, not as the words", all(k["tags"] == (OV.SHADOW_TAG,) for _n, _a, k in behind))
    check("everything else goes straight through", shaded.create_line(0, 0, 1, 1) == "line")
    canvas = FakeCanvas()
    both = OV.scaled_canvas(canvas, 1.5, shadow=True)
    both.create_text(0, 0, text="x", fill="#ffffff", font=("Consolas", 10))
    check("with a bigger text size too: every copy at the new size",
          len(canvas.texts) == 5 and {k["font"] for _n, _a, k in canvas.texts} == {("Consolas", 15)},
          canvas.texts)
    canvas = FakeCanvas()
    shaded = OV.scaled_canvas(canvas, 1.0, shadow=True)
    shaded.create_text(0, 0, text="   ", fill="#ffffff", font=("Consolas", 10))
    shaded.create_text(0, 0, text="hole", fill=OV.CHROMA, font=("Consolas", 10))
    shaded.create_text(0, 0, text="none", fill="", font=("Consolas", 10))
    check("nothing to read, a see-through word or no colour at all: no shadow", len(canvas.texts) == 3)
    check("the preset made for a stream raises its text to %d%%" % OV.PRESET_TEXT["streamer"],
          OV.PRESET_TEXT == {"streamer": 130} and 130 in OV.TEXT_SIZES)


# ---------------------------------------------------------------------------
# The app, on the real toolkit.
HAVE_DISPLAY = True
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    HAVE_DISPLAY = False
    print("\n  SKIP  the toolkit half of this file - no display (%s). "
          "Run it under xvfb-run." % _exc)
    print("\nFAILURES:", len(fails))
    for f in fails:
        print("  -", f)
    sys.exit(1 if fails else 0)

OV.foreground_is_game = lambda: None
import edsmt as A          # noqa: E402
# Tk's own clipboard, as the other GUI tests have it: on Windows the app
# writes through Win32 so a copy outlives EDSMT, and Tk in the same
# process does not read that back.
A._windows_clipboard = lambda *args, **kwargs: False
import survey as SV        # noqa: E402
import sessionledger as SL  # noqa: E402
A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)
SYSTEM, BODY = "Col 285 Sector KZ-C b14-1", "Col 285 Sector KZ-C b14-1 A 3"
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
    json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS,
               "welcome_seen_version": A.APP_VERSION}, _f)
app = A.EDSMT()
app.geometry("1600x1000+0+0")
app.updates.check = lambda *args, **kwargs: None


def pump(times=3):
    for _ in range(times):
        app.update_idletasks()
        app.update()


def clip():
    """What is on the clipboard, or "" while nobody holds it (Windows hands
    it from Tk to the Win32 copy between two events)."""
    try:
        return STATE_CLIP["app"].clipboard_get()
    except Exception:
        return ""


STATE_CLIP = {}


def settle_until(cond, seconds=5.0):
    """Pump until `cond` holds or the time is up - never a set number of
    rounds."""
    end = time.time() + seconds
    while time.time() < end:
        if cond():
            return True
        pump(1)
        time.sleep(0.02)
    return bool(cond())


def walk(widget):
    out = [widget]
    for child in widget.winfo_children():
        out += walk(child)
    return out


def shown(widget):
    try:
        return bool(widget.winfo_manager()) and bool(widget.winfo_ismapped())
    except Exception:
        return False


STAMP = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
JOURNAL = os.path.join(JOURNALS, "Journal.2026-10-29T120000.01.log")


def emit(*events):
    with open(JOURNAL, "a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")


def tick(times=1):
    for _ in range(times):
        app.tick()
    pump(2)


def on(**changes):
    data = dict(app.settings)
    data.update(changes)
    app.apply_settings(data)
    pump(2)


def stamp(when):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(when))


def publish(now=None):
    """The state on the page now, not when it is next due."""
    server = app.stream_server()
    server.published_at = 0.0
    app.follow_stream(now=now)
    return server


pump()
emit({"timestamp": STAMP, "event": "Fileheader", "gameversion": "4.4.2.1", "part": 1},
     {"timestamp": STAMP, "event": "Commander", "Name": "Jameson", "FID": "F1"},
     {"timestamp": STAMP, "event": "FSDJump", "StarSystem": SYSTEM, "SystemAddress": 77,
      "StarPos": [-171.0, 230.9, 0.5]},
     {"timestamp": STAMP, "event": "ApproachBody", "StarSystem": SYSTEM, "Body": BODY},
     {"timestamp": STAMP, "event": "Touchdown", "Latitude": 12.5, "Longitude": -45.5,
      "StarSystem": SYSTEM, "Body": BODY, "PlayerControlled": True})
with open(os.path.join(JOURNALS, "Status.json"), "w", encoding="utf-8") as _f:
    json.dump({"timestamp": STAMP, "event": "Status", "Flags": (1 << 21) | (1 << 26),
               "Latitude": 12.5, "Longitude": -45.5, "Heading": 90, "Altitude": 0,
               "BodyName": BODY, "PlanetRadius": 1800000.0}, _f)
tick(2)


@section("Settings > Overlay > Streaming")
def _settings():
    check("off out of the box, on 8765, no shadow - each with its note",
          A.DEFAULT_SETTINGS["stream_enabled"] is False and A.DEFAULT_SETTINGS["stream_port"] == 8765
          and A.DEFAULT_SETTINGS["overlay_text_shadow"] is False
          and all(A.SETTING_TIPS.get(k) for k in ("stream_enabled", "stream_port", "overlay_text_shadow")))
    win = A.SettingsWindow(app)
    pump(4)
    saved, said = [], []
    real_apply = app.apply_settings
    app.apply_settings = lambda data: saved.append(json.loads(json.dumps(data)))
    win.say = lambda text, colour=None: said.append(str(text))
    try:
        page = win.pages["Overlay"]
        inside = set(walk(page))
        check("a switch for the page and one for the text shadow, on the Overlay page",
              "stream_enabled" in win.toggles and "overlay_text_shadow" in win.toggles
              and all(any(isinstance(w, A.ctk.CTkSwitch) and w.cget("variable") is win.toggles[k]
                          for w in inside) for k in ("stream_enabled", "overlay_text_shadow")))
        check("the switches read as asked",
              any(isinstance(w, A.ctk.CTkSwitch) and w.cget("text") == "Serve an OBS browser source on this PC"
                  for w in inside)
              and any(isinstance(w, A.ctk.CTkSwitch) and w.cget("text") == "Text shadow for streaming"
                      for w in inside))
        box = win.fields.get("stream_port")
        check("the port, as saved", box is not None and box in inside and box.get() == "8765",
              box and box.get())
        buttons = getattr(win, "stream_copy", {})
        check("and a Copy button for each address", sorted(buttons) == ["/overlay", "/viewer"]
              and all(b in inside for b in buttons.values()), sorted(buttons))
        check("every one of them has its note", all(getattr(w, "_edsmt_tip", "") for w in
                                                    list(buttons.values()) + [box]))
        box.delete(0, "end")
        box.insert(0, "9123")
        STATE_CLIP["app"] = app
        app.clipboard_clear()
        buttons["/overlay"].invoke()
        check("Copy puts the overlay's address on the clipboard, on the port in the box",
              settle_until(lambda: clip() == "http://127.0.0.1:9123/overlay"), clip())
        buttons["/viewer"].invoke()
        check("and the viewer card's", settle_until(lambda: clip() == "http://127.0.0.1:9123/viewer"))
        check("and says what to do with it, and that the page is off",
              said and "OBS Browser Source" in said[-1] and "Switch the page on" in said[-1], said[-1:])
        box.delete(0, "end")
        box.insert(0, "80")
        buttons["/overlay"].invoke()
        check("a port it may not use is not copied", clip().endswith(":9123/viewer")
              and said[-1] == A.STREAM_PORT_WRONG, said[-1:])
        win.save()
        check("nor saved", not saved and said[-1] == A.STREAM_PORT_WRONG, said[-1:])
        box.delete(0, "end")
        box.insert(0, "9123")
        win.toggles["stream_enabled"].set(True)
        win.toggles["overlay_text_shadow"].set(True)
        win.save()
        check("a good one is saved as a number, with both switches",
              saved and saved[-1]["stream_port"] == 9123 and saved[-1]["stream_enabled"] is True
              and saved[-1]["overlay_text_shadow"] is True, saved[-1:] and
              {k: saved[-1].get(k) for k in ("stream_port", "stream_enabled", "overlay_text_shadow")})
        # Each webhook's own Session card switch.
        hook = "https://discord.com/api/webhooks/%s/%s" % ("556677889900112233", "c" * 6 + "Zq-9_" + "c" * 57)
        app.settings["discord_webhooks"] = [{"name": "Old", "url": hook, "finds": False, "sessions": True,
                                             "map": True}]
        win.load()
        win.tabs.set("Sharing")
        pump(4)
        row = win.hook_rows[0]
        check("each webhook row has a Session card switch, with its note, off on a row saved before it",
              "card" in row["switches"] and row["switches"]["card"].cget("text") == "Session card"
              and getattr(row["switches"]["card"], "_edsmt_tip", "") and row["vars"]["card"].get() is False)
        frame = row["frame"]
        pump(2)
        check("and the row still has room for Test and Remove",
              all(shown(row[k]) and row[k].winfo_rootx() + row[k].winfo_width()
                  <= frame.winfo_rootx() + frame.winfo_width() for k in ("test", "remove")),
              [(row[k].winfo_rootx(), row[k].winfo_width()) for k in ("test", "remove")])
        row["vars"]["card"].set(True)
        win.save()
        check("switched on, it is saved with the row", saved[-1]["discord_webhooks"][0]["card"] is True
              and saved[-1]["discord_webhooks"][0]["map"] is True, saved[-1]["discord_webhooks"])
    finally:
        app.apply_settings = real_apply
        app.settings["discord_webhooks"] = []
        win.destroy()
        pump(2)


@section("the app: the OBS page, on only when switched on, on the port asked for")
def _app_server():
    app.stop_stream()
    on(stream_enabled=False)
    app.follow_stream()
    check("off: nothing listens", not app.stream_server().running)
    port = free_port()
    # What the main window said, not only the line it shows now: on a
    # machine with no network another notice (the leaderboard, unreachable)
    # can take the status line a moment later (GitHub's Windows runner).
    heard = []
    real_say = app.say

    def say(text, *args, **kwargs):
        heard.append(str(text))
        return real_say(text, *args, **kwargs)
    app.say = say
    try:
        on(stream_enabled=True, stream_port=port)
        app.follow_stream()
        check("on: listening on 127.0.0.1 at that port", app.stream_server().running
              and app.stream_server().address() == ("127.0.0.1", port), app.stream_server().address())
        check("and the main window says where to point OBS",
              any(SO.page_url(port) in line for line in heard + [app.status.cget("text")]), heard[-3:])
        publish()
        status, _h, body = fetch(port, "/state.json")
        check("the page's state is the app's", status == 200 and json.loads(body)["cmdr"] == "Jameson"
              and json.loads(body)["body"] == BODY, body[:200])
        check("both pages are there", fetch(port, "/overlay")[0] == 200 and fetch(port, "/viewer")[0] == 200)
        check("in the app theme's colours", json.loads(body)["colours"]["orange"] == A.ORANGE.lower()
              and json.loads(body)["colours"]["void"] == A.VOID.lower())
        check("the tick keeps it going", "self.follow_stream()" in
              __import__("inspect").getsource(A.EDSMT.tick))
        app.settings["stream_port"] = "80"
        app.follow_stream()
        check("a port it may not use: stopped, and says what it needs", not app.stream_server().running
              and any("1024" in line for line in heard[-3:] + [app.status.cget("text")]), heard[-3:])
        port2 = free_port()
        app.settings["stream_port"] = port2
        app.follow_stream()
        check("a new port: moved to it", app.stream_server().running and app.stream_server().port == port2)
        app.settings["stream_enabled"] = False
        app.follow_stream()
        check("switched off: stopped", not app.stream_server().running)
        app.settings["stream_enabled"] = True
        app.follow_stream()
        check("on again", app.stream_server().running)
        app._save_on_exit()
        check("and the port is let go first when the app closes or restarts", not app.stream_server().running)
    finally:
        app.say = real_say
        app.settings["stream_enabled"] = False
        app.stop_stream()


@section("the app: what the page shows of a live Rhino session")
def _app_state():
    folder = os.path.join(TMP, "books")
    os.makedirs(folder, exist_ok=True)
    app.earnings, app.extras, app.post_book = SV.Earnings(folder), SL.SessionLedger(folder), SL.PostBook(folder)
    # Settings saved above point the reader at the folder again; where the
    # SRV is comes back with the next reading of Status.json.
    settle_until(lambda: app.watcher.poll_status() or app.watcher.has_position)
    tick()
    now = time.time()
    quiet = app.stream_now(now=now)
    check("no session yet: nothing running, nothing mined, and where you are",
          quiet["session"]["running"] is False and quiet["tonnes"] == [] and quiet["system"] == SYSTEM
          and quiet["body"] == BODY, quiet)
    books = app.earnings
    row = books.start_now(SYSTEM, BODY, "Jameson", when=stamp(now - 3723))
    row["mined"] = "Platinum:34;Osmium:6"
    app.rigs_at = {"system": SYSTEM, "body": BODY,
                   "rigs": [{"n": 1, "lat": 12.501, "lon": -45.5}, {"n": 2, "lat": 12.5, "lon": -45.499}]}
    app.store.add_deposit(system=SYSTEM, body=BODY, lat=12.5027, lon=-45.5, commodity="Platinum",
                          amount="High", rigs="4")
    state = app.stream_now(now=now)
    check("whose and where", (state["cmdr"], state["system"], state["body"]) == ("Jameson", SYSTEM, BODY),
          (state["cmdr"], state["system"], state["body"]))
    check("tonnes this session by commodity", state["tonnes"] == [
        {"commodity": "Platinum", "tonnes": 34}, {"commodity": "Osmium", "tonnes": 6}], state["tonnes"])
    check("the clock runs to now, not to the last thing the journal said",
          state["session"]["running"] is True and 3720 <= state["session"]["seconds"] <= 3726,
          state["session"])
    check("rigs down", state["rigs_down"] == 2, state["rigs_down"])
    nearest = state["nearest"] or {}
    check("the nearest deposit, how far and which way", nearest.get("commodity") == "Platinum"
          and 70 <= nearest.get("distance_m", 0) <= 95 and nearest.get("compass") == "N", nearest)
    check("the last find, just marked", (state["last_find"] or {}).get("commodity") == "Platinum"
          and state["last_find"]["rigs"] == 4 and state["last_find"]["where"] == BODY, state["last_find"])
    check("credits an hour is a whole number", isinstance(state["cr_hr"], int) and state["cr_hr"] >= 0)
    words = json.dumps(state)
    check("no position on the body in it - not the Rhino's, not a rig's, not a deposit's",
          '"lat"' not in words and '"lon"' not in words and "12.50" not in words
          and "45.49" not in words and "1800000" not in words, words)
    books.pause(when=stamp(now - 600))
    paused = app.stream_now(now=now)
    check("paused: says so, and the clock stops where it was paused",
          paused["session"]["paused"] is True and paused["session"]["seconds"] <= 3723 - 590,
          paused["session"])
    books.resume()
    books.finish(None, "ended by hand", by="button")
    after = app.stream_now(now=time.time())
    check("just ended: the last session is still shown, not running",
          after["session"]["running"] is False and after["tonnes_total"] == 40, after["session"])
    later = app.stream_now(now=time.time() + A.STREAM_LAST_S + 60)
    check("long after: nothing", later["tonnes"] == [] and later["session"]["seconds"] == 0, later["session"])


@section("the app: streamer mode on the page - the names hidden exactly as on screen")
def _app_streamer():
    port = free_port()
    on(stream_enabled=True, stream_port=port, streamer_mode=True, streamer_delay_min=15)
    tick()
    try:
        server = publish()
        check("listening", server.running)
        _s, _h, body = fetch(port, "/state.json")
        state = json.loads(body)
        check("the body and system read as the readout at the top does",
              "%s / %s" % (state["system"], state["body"]) == app.t_where.cget("text")
              == "a system 290 Ly from Sol / a body", (state["system"], state["body"], app.t_where.cget("text")))
        check("the last find's place too", state["last_find"]["where"] == "a body", state["last_find"])
        check("neither name anywhere on the page's state", SYSTEM not in body.decode("utf-8")
              and "KZ-C" not in body.decode("utf-8"), body[:300])
        check("and Settings' line on streamer mode says the OBS page is covered",
              "the OBS page" in A.STREAMER_NOTE and "hidden" in A.STREAMER_NOTE.lower())
        later = time.time() + 15 * 60 + 5
        publish(now=later)
        _s, _h, body = fetch(port, "/state.json")
        check("once he has been in the system for the delay, the real names - as on screen",
              json.loads(body)["body"] == BODY == app.hide_names(BODY, now=later))
        on(streamer_mode=False)
        publish()
        _s, _h, body = fetch(port, "/state.json")
        check("streamer mode off: the names at once", json.loads(body)["system"] == SYSTEM)
    finally:
        on(stream_enabled=False, streamer_mode=False)
        app.stop_stream()


def map_picture(at):
    """A real map picture of the session's body in the pictures folder."""
    folder = MI.pictures_dir(A.DATA_DIR)
    path = os.path.join(folder, MI.picture_name(SYSTEM, BODY, "1", at))
    MI.save_picture(fake_map(), path)
    return path


@section("Earnings: the Session card button, and a card on each session's row")
def _earnings():
    folder = os.path.join(TMP, "books-card")
    os.makedirs(folder, exist_ok=True)
    app.earnings, app.extras, app.post_book = SV.Earnings(folder), SL.SessionLedger(folder), SL.PostBook(folder)
    app._pictures = []
    now = time.time()
    run = app.earnings.start(SYSTEM, BODY, "Jameson", when=stamp(now - 7200))
    run.update({"mined": "Painite:120;Platinum:20", "ended": stamp(now - 60), "closed": stamp(now - 60)})
    app.earnings.save()
    map_picture(now - 1800)
    port = free_port()
    on(stream_enabled=True, stream_port=port)
    win = app.open_earnings()
    pump(6)
    try:
        win.show_page("This session")
        pump(4)
        button = getattr(win, "card_button", None)
        check("a Session card button on This session, with its note",
              button is not None and button.cget("text") == "Session card" and shown(button)
              and getattr(button, "_edsmt_tip", ""))
        pictures = MI.pictures_dir(A.DATA_DIR)
        name = SC.card_name(run)
        button.invoke()
        path = os.path.join(pictures, name)
        check("it saves the session's card in the pictures folder",
              settle_until(lambda: os.path.isfile(path)), sorted(os.listdir(pictures)))
        check("and says so", name in str(win.status.cget("text")), win.status.cget("text"))
        from PIL import Image
        with Image.open(path) as card:
            card.load()
            size = card.size
            inside = colours_in(card.convert("RGB"), (SC.MAP_BOX[0] + 20, SC.MAP_BOX[1] + 20,
                                                      SC.MAP_BOX[2] - 20, SC.MAP_BOX[3] - 20))
        check("a 1200 x 675 picture", size == SC.SIZE, size)
        check("with the session's map in it", (255, 0, 0) in inside and len(inside) <= 3, inside)
        _s, headers, served = fetch(port, "/card.png")
        check("and the OBS page serves it as /card.png", served == open(path, "rb").read()
              and headers.get("Content-Type") == "image/png")
        win.show_page("Sessions")
        pump(6)
        os.remove(path)
        cards = [w for w in walk(win.table) if isinstance(w, A.tk.Label) and w.cget("text") == "card"]
        check("each session's row has a card button", len(cards) == 1, len(cards))
        if cards:
            cards[0].event_generate("<Button-1>")
            check("which makes that session's card", settle_until(lambda: os.path.isfile(path)))
        # Streamer mode: the stream's copy has no names in it; the file does.
        on(streamer_mode=True, streamer_delay_min=15)
        tick()
        made = app.session_card(app.earnings.recent()[0])
        _s, _h, served = fetch(port, "/card.png")
        check("in streamer mode the copy on the OBS page is drawn without the names",
              made["png"] and served and served != made["png"], (len(made["png"]), len(served)))
        texts = SC.render_card(SC.card_facts(run, "Jameson", hide=app.hide_names))[1]
        check("by the app's own rule", "a body" in texts and not any(SYSTEM in t for t in texts), texts)
        on(streamer_mode=False)
        app.earnings = SV.Earnings(os.path.join(TMP, "books-none"))
        made = app.session_card()
        check("no session at all: says so, and makes nothing", not made["path"] and "no Rhino session"
              in made["why"], made)
    finally:
        on(stream_enabled=False, streamer_mode=False)
        app.stop_stream()
        try:
            win.destroy()
        except Exception:
            pass
        pump(2)


class Worker:
    def __init__(self):
        self.jobs = []

    def submit(self, tag, fn):
        self.jobs.append((tag, fn))

    def run(self):
        out = []
        for tag, fn in self.jobs:
            try:
                out.append((tag, True, fn() or ""))
            except Exception as exc:
                out.append((tag, False, str(exc)))
        self.jobs = []
        return out


def hook(ident, letter):
    return "https://discord.com/api/webhooks/%s/%s" % (ident, letter * 6 + "Zq-9_" + letter * 57)


@section("Discord: the card with the session summary, only where it is switched on")
def _discord():
    folder = os.path.join(TMP, "books-discord")
    os.makedirs(folder, exist_ok=True)
    app.earnings, app.extras, app.post_book = SV.Earnings(folder), SL.SessionLedger(folder), SL.PostBook(folder)
    app.worker, app._discord_seen = Worker(), None
    a, b, c = hook("112233445566778899", "a"), hook("223344556677889900", "b"), hook("334455667788990011", "c")
    app.settings["discord_webhooks"] = [WH.entry("Both", a, map=True, card=True),
                                        WH.entry("Card", b, map=False, card=True),
                                        WH.entry("Map", c, map=True)]
    sent = []
    real = (EDO.discord_post_file, EDO.post_json)

    def post_file(url, payload, filename, data, timeout=40.0, more=()):
        sent.append((url.split("?")[0], [filename] + [n for n, _d in more], payload))
        return {"id": str(900000 + len(sent)), "attachments": [{"id": str(i)} for i in range(1 + len(more))]}

    def post_json(url, payload, timeout=20.0, headers=None):
        sent.append((url.split("?")[0], [], payload))
        return {"id": str(900000 + len(sent)), "attachments": []}
    EDO.discord_post_file, EDO.post_json = post_file, post_json
    try:
        app.post_discord_sessions()
        now = time.time()
        run = app.earnings.start(SYSTEM, BODY, "Jameson", when=stamp(now - 3600))
        run.update({"mined": "Painite:200", "ended": stamp(now - 30), "closed": stamp(now - 30)})
        app.earnings.save()
        app._pictures = [(now - 40, map_picture(now - 40))]
        app.post_discord_sessions()
        for tag, ok, message in app.worker.run():
            app.take_discord(tag, ok, message)
        files = {url: names for url, names, _p in sent}
        card = SC.card_name(run)
        check("map and card on: the map picture and the card, in one message",
              len(files.get(a, [])) == 2 and files[a][1] == card, files.get(a))
        check("card on, map off: the card alone", files.get(b) == [card], files.get(b))
        check("card off: no card", card not in files.get(c, []) and len(files.get(c, [])) == 1, files.get(c))
        check("the card is in the pictures folder too",
              os.path.isfile(os.path.join(MI.pictures_dir(A.DATA_DIR), card)))
        key = SL.post_key(str(run["id"]), WH.hook_key(a))
        check("and both attachments are kept when the message is edited after the sale",
              app.post_book.posted.get(key, {}).get("attachments") == ["0", "1"],
              app.post_book.posted.get(key))
    finally:
        EDO.discord_post_file, EDO.post_json = real
        app.settings["discord_webhooks"] = []


KEYS = (OV.RADAR, OV.STRIP, OV.STATUS, OV.TARGETS, OV.GUIDE, OV.DEPOSIT)
OV_ROWS = [{"commodity": "Iridium", "range_m": 420.0, "bearing": 30.0, "rigs": 3,
            "east": 200.0, "north": 350.0, "id": 1},
           {"commodity": "Haematite", "range_m": 896.0, "bearing": 300.0, "rigs": 2,
            "east": -500.0, "north": 700.0, "id": 2}]


def words_on(canvas, shadows=False):
    """(item, text, font size, box) of every word on a canvas - its shadow
    copies only when asked for."""
    out = []
    for item in canvas.find_all():
        if canvas.type(item) != "text" or not canvas.itemcget(item, "text").strip():
            continue
        if (OV.SHADOW_TAG in canvas.gettags(item)) != shadows:
            continue
        found = re.search(r"(-?\d+)", str(canvas.itemcget(item, "font")))
        out.append((item, canvas.itemcget(item, "text"), abs(int(found.group(1))) if found else 0,
                    canvas.bbox(item)))
    return out


def screen_overlay(settings, size=(1920, 1080)):
    over = OV.Overlay(app, tkinter, settings)
    over.screen = lambda _win, size=size: size
    over.show()
    over.draw(OV_ROWS, 10.0, body="Col 285 Sector ZL-K b22-2 A 1")
    pump()
    return over


@section("overlay: the shadow on the real boxes, and the streamer layout on a 1080p capture")
def _overlay():
    layout, shown_keys = OV.preset_layout("streamer", 1920, 1080)
    base = {"overlay_layout": layout}
    for key in KEYS:
        base["overlay_show_%s" % key] = key in shown_keys
    plain = screen_overlay(dict(base))
    try:
        check("shadow off: none drawn on any box", plain.panels and not any(
            words_on(p.canvas, shadows=True) for p in plain.panels.values()))
    finally:
        plain.hide()
        pump()
    shaded = screen_overlay(dict(base, overlay_text_shadow=True))
    try:
        for key, panel in sorted(shaded.panels.items()):
            canvas = panel.canvas
            words, behind = words_on(canvas), words_on(canvas, shadows=True)
            copies = collections.defaultdict(list)
            for item, text, _size, _box in behind:
                copies[text].append(item)
            check("shadow on: %s has an outline behind every word" % key,
                  words and all(len(copies[t]) >= 4 for _i, t, _s, _b in words)
                  and len(behind) == 4 * len(words), (len(words), len(behind)))
            check("shadow on: %s draws each word over its outline" % key,
                  all(min(copies[t]) < i for i, t, _s, _b in words))
            check("shadow on: %s's outline is solid and dark" % key,
                  {canvas.itemcget(i, "fill").lower() for i, _t, _s, _b in behind} == {OV.SHADOW})
    finally:
        shaded.hide()
        pump()

    over = OV.Overlay(app, tkinter, dict(base, overlay_text_status=175))
    applied = over.apply_preset("streamer")
    check("the streamer layout raises its boxes' words to %d%%" % OV.PRESET_TEXT["streamer"],
          applied and all(int(over.settings["overlay_text_%s" % k]) >= 130 for k in applied)
          and all(int(over.settings["overlay_text_%s" % k]) == 130 for k in applied if k != OV.STATUS),
          {k: over.settings.get("overlay_text_%s" % k) for k in KEYS})
    check("but never makes words someone set bigger smaller", int(over.settings["overlay_text_status"]) == 175)
    check("and leaves the boxes it does not show alone",
          "overlay_text_%s" % OV.DEPOSIT not in over.settings)
    big = dict(base, overlay_text_shadow=True,
               **{"overlay_text_%s" % k: OV.PRESET_TEXT["streamer"] for k in shown_keys})
    lay = screen_overlay(big)
    try:
        for key, panel in sorted(lay.panels.items()):
            words = words_on(panel.canvas)
            w, h = int(panel.canvas.winfo_width()), int(panel.canvas.winfo_height())
            check("streamer on 1920x1080: %s writes nothing under 10 pt (%s)"
                  % (key, sorted({size for _i, _t, size, _b in words})),
                  words and min(size for _i, _t, size, _b in words) >= 10)
            outside = [t for _i, t, _s, b in words if b and (b[0] < -2 or b[1] < -2 or b[2] > w + 2
                                                             or b[3] > h + 2)]
            crossed = [(a[1], b[1]) for n, a in enumerate(words) for b in words[n + 1:]
                       if a[3] and b[3] and min(a[3][2], b[3][2]) - max(a[3][0], b[3][0]) > 3
                       and min(a[3][3], b[3][3]) - max(a[3][1], b[3][1]) > 3]
            check("streamer on 1920x1080: %s keeps every word inside it, none on another" % key,
                  not outside and not crossed, (outside[:3], crossed[:3]))
    finally:
        lay.hide()
        pump()
    win = A.SettingsWindow(app)
    pump(4)
    try:
        box, _options = win.choices["overlay_preset"]
        box.set("Streamer")
        real = app.apply_overlay_preset
        app.apply_overlay_preset = lambda name: (app.settings.update(
            {"overlay_text_%s" % k: 130 for k in shown_keys}) or set(shown_keys))
        try:
            win.apply_preset()
        finally:
            app.apply_overlay_preset = real
        check("Settings shows the raised sizes after Apply layout, so Save keeps them",
              all(win.choices["overlay_text_%s" % k][0].get() == "130%" for k in shown_keys),
              {k: win.choices["overlay_text_%s" % k][0].get() for k in shown_keys})
    finally:
        win.destroy()
        pump(2)


print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
