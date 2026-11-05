"""1.10040: mining locations to the community network (#159).

When the FSS reports a body with Planetary Mining Locations, EDSMT sends
that body's signal list to the shared player data network (EDDN), so every
tool that reads it learns the body has them. One schema only -
fssbodysignals/1 - and only what that schema allows. The rules, from the
network's own developer notes and the schema:

- live events only, never an old journal replayed;
- StarSystem and StarPos added only from a Location, FSDJump or CarrierJump
  whose SystemAddress matches the event's own, else nothing is sent;
- nothing with a _Localised name, nothing about the commander but the
  uploader name and the horizons / odyssey flags, those only from LoadGame
  and only when LoadGame carries them;
- gameversion and gamebuild from Fileheader, passed through as they are;
  a beta goes to the /test schema, an old (3.x) client sends nothing;
- a refused message (400, 426, 413) is never sent again; anything else
  waits at least a minute and is not retried for ever.

A switch in Settings > Sharing, on by default.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_eddn.py
"""
import io
import json
import os
import sys
import tempfile
import time
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-eddn-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import eddnsend as ED    # noqa: E402
import journal as J      # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


def stamp(when):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(when))


NOW = time.time()
T = stamp(NOW - 30)
OLD = stamp(NOW - 3600)

# What fssbodysignals/1 allows in a message, from the schema itself
# (additionalProperties false at the top and in each signal).
ALLOWED = {"timestamp", "event", "horizons", "odyssey", "StarSystem", "StarPos", "SystemAddress",
           "BodyID", "BodyName", "Signals"}
REQUIRED = {"timestamp", "event", "StarSystem", "StarPos", "SystemAddress", "BodyID", "Signals"}

header = {"timestamp": T, "event": "Fileheader", "part": 1, "language": "English/UK",
          "Odyssey": True, "gameversion": "4.2.1.0", "build": "r312345/r0 "}
load = {"timestamp": T, "event": "LoadGame", "FID": "F123456", "Commander": "The Announcer",
        "Horizons": True, "Odyssey": True, "Ship": "Krait_MkII", "Credits": 987654321}
jump = {"timestamp": T, "event": "FSDJump", "StarSystem": "Ega", "SystemAddress": 11,
        "StarPos": [12.5, -3.25, 40.0], "Population": 0, "FuelUsed": 2.1, "JumpDist": 20.5}
signals = {"timestamp": T, "event": "FSSBodySignals", "BodyName": "Ega 1", "BodyID": 1, "SystemAddress": 11,
           "Signals": [{"Type": "$PlanetaryMiningLocation_Name;", "Type_Localised": "Planetary Mining Location",
                        "Count": 19},
                       {"Type": "$SAA_SignalType_Geological;", "Type_Localised": "Geological", "Count": 3}]}


def fresh_tracker():
    t = ED.Tracker()
    for event in (header, load, jump):
        check_none = t.see(event, now=NOW)
        if check_none is not None:
            fails.append("a location event made a message")
    return t


print("== the message ==")
t = fresh_tracker()
item = t.see(signals, now=NOW)
check("a body with mining locations makes one message", item is not None, item)
item = item or {}
msg = item.get("message", {})
check("for the fssbodysignals/1 schema, live", item.get("schema") == "https://eddn.edcd.io/schemas/fssbodysignals/1",
      item.get("schema"))
check("with every key the schema requires", REQUIRED <= set(msg), sorted(msg))
check("and only keys the schema allows", set(msg) <= ALLOWED, sorted(set(msg) - ALLOWED))
check("StarSystem and StarPos from the jump, the address cross-checked",
      msg.get("StarSystem") == "Ega" and msg.get("StarPos") == [12.5, -3.25, 40.0] and msg.get("SystemAddress") == 11,
      msg)
check("the body, by ID and name", msg.get("BodyID") == 1 and msg.get("BodyName") == "Ega 1", msg)
check("every signal the FSS reported, Type and Count only",
      msg.get("Signals") == [{"Type": "$PlanetaryMiningLocation_Name;", "Count": 19},
                             {"Type": "$SAA_SignalType_Geological;", "Count": 3}], msg.get("Signals"))
check("nothing _Localised anywhere", "_Localised" not in json.dumps(item))
check("the event's own timestamp and name", msg.get("timestamp") == T and msg.get("event") == "FSSBodySignals")
check("horizons and odyssey from LoadGame", msg.get("horizons") is True and msg.get("odyssey") is True, msg)
check("gameversion and gamebuild from Fileheader, passed through as they are (the space kept)",
      item.get("gameversion") == "4.2.1.0" and item.get("gamebuild") == "r312345/r0 ", item)
check("no FID, credits, ship or commander in the message",
      all(word not in json.dumps(msg) for word in ("F123456", "987654321", "Krait", "Announcer")))
check("the same body again is not sent twice", t.see(dict(signals), now=NOW) is None)

print("== when nothing goes ==")
t = fresh_tracker()
plain = dict(signals, Signals=[{"Type": "$SAA_SignalType_Geological;", "Type_Localised": "Geological", "Count": 3}])
check("a body with no mining locations", t.see(plain, now=NOW) is None)
t = fresh_tracker()
check("a body in another system than the last jump says", t.see(dict(signals, SystemAddress=12), now=NOW) is None)
t = fresh_tracker()
t.see({"timestamp": T, "event": "Location", "StarSystem": "Ega", "SystemAddress": 11}, now=NOW)
check("a location without StarPos leaves the place unknown", t.see(signals, now=NOW) is None)
t = fresh_tracker()
check("an old event, read back from a journal", t.see(dict(signals, timestamp=OLD), now=NOW) is None)
check("an event from the future (a clock far out)", t.see(dict(signals, timestamp=stamp(NOW + 3600)), now=NOW) is None)
t = ED.Tracker()
t.see(load, now=NOW)
t.see(jump, now=NOW)
check("no Fileheader seen, so no game version", t.see(signals, now=NOW) is None)
t = ED.Tracker()
t.see(dict(header, gameversion="3.8.0.407", build="r262829/r0 "), now=NOW)
t.see(load, now=NOW)
t.see(jump, now=NOW)
check("an old 3.x client sends nothing", t.see(signals, now=NOW) is None)
t = ED.Tracker()
t.see(dict(header, part=1), now=NOW)
t.see(jump, now=NOW)
check("a BodyID that is not a number", t.see(dict(signals, BodyID="one"), now=NOW) is None)

print("== the flags and the version ==")
t = ED.Tracker()
t.see(dict(header, gameversion="4.3.0.1 Beta"), now=NOW)
t.see(load, now=NOW)
t.see(jump, now=NOW)
item = t.see(signals, now=NOW) or {}
check("a beta goes to the /test schema", item.get("schema") == "https://eddn.edcd.io/schemas/fssbodysignals/1/test",
      item.get("schema"))
t = ED.Tracker()
t.see(header, now=NOW)
t.see({"timestamp": T, "event": "LoadGame", "Commander": "X", "Horizons": True}, now=NOW)
t.see(jump, now=NOW)
msg = (t.see(signals, now=NOW) or {}).get("message", {})
check("no Odyssey in LoadGame: no odyssey key at all, not false", "odyssey" not in msg and msg.get("horizons") is True, msg)
t = ED.Tracker()
t.see(header, now=NOW)
t.see(jump, now=NOW)
msg = (t.see(signals, now=NOW) or {}).get("message", {})
check("no LoadGame: neither flag", "odyssey" not in msg and "horizons" not in msg, msg)
t = fresh_tracker()
t.see(dict(header, part=2), now=NOW)
item = t.see(signals, now=NOW) or {}
check("a journal's next part keeps the flags and the place", item.get("message", {}).get("odyssey") is True
      and item.get("message", {}).get("StarSystem") == "Ega", item)
t = fresh_tracker()
t.see(dict(header, part=1), now=NOW)
check("a new game session forgets the place until the game says it again", t.see(signals, now=NOW) is None)
t = fresh_tracker()
t.see({"timestamp": T, "event": "CarrierJump", "StarSystem": "Hun", "SystemAddress": 12,
       "StarPos": [1.0, 2.0, 3.0], "Docked": True}, now=NOW)
msg = (t.see(dict(signals, SystemAddress=12, BodyName="Hun 1"), now=NOW) or {}).get("message", {})
check("a carrier jump moves you", msg.get("StarSystem") == "Hun" and msg.get("StarPos") == [1.0, 2.0, 3.0], msg)

print("== the envelope ==")
t = fresh_tracker()
item = t.see(signals, now=NOW)
env = ED.envelope(item, "The Announcer", "1.10040")
check("$schemaRef, header and message", set(env) == {"$schemaRef", "header", "message"} and
      env["$schemaRef"] == item["schema"] and env["message"] == item["message"], sorted(env))
check("the header: commander as uploader, our name and version, the game's version and build",
      env["header"] == {"uploaderID": "The Announcer", "softwareName": "EDSMT", "softwareVersion": "1.10040",
                        "gameversion": "4.2.1.0", "gamebuild": "r312345/r0 "}, env["header"])

print("== sending ==")


class Reply:
    def __init__(self, body=b"OK", code=200):
        self.body, self.status = body, code

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


seen = []
contexts = []


def opener_ok(request, timeout=None, context=None):
    seen.append(request)
    contexts.append(context)
    return Reply()


code, text = ED.upload(env, opener=opener_ok)
req = seen[-1]
check("POST to the upload address, with the trailing slash", req.get_method() == "POST"
      and req.full_url == "https://eddn.edcd.io:4430/upload/", (req.get_method(), req.full_url))
check("as JSON", req.get_header("Content-type") == "application/json", req.header_items())
check("the body is the envelope", json.loads(req.data.decode("utf-8")) == env)
check("200 OK", (code, text) == (200, "OK"), (code, text))
import ssl  # noqa: E402
roots = [dict(x[0] for x in c.get("subject", ())).get("commonName") for c in
         (contexts[-1].get_ca_certs() if isinstance(contexts[-1], ssl.SSLContext) else [])]
check("over TLS that verifies, trusting ISRG Root X2 as well (the gateway's chain needs it)",
      isinstance(contexts[-1], ssl.SSLContext) and contexts[-1].verify_mode == ssl.CERT_REQUIRED
      and contexts[-1].check_hostname and "ISRG Root X2" in roots, roots[-3:])


def opener_refused(request, timeout=None, context=None):
    raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", {},
                                 io.BytesIO(b"FAIL: Schema validation failed"))


def opener_down(request, timeout=None, context=None):
    raise urllib.error.URLError("timed out")


code, text = ED.upload(env, opener=opener_refused)
check("a refusal comes back as its code and what it said", code == 400 and "Schema" in text, (code, text))
code, text = ED.upload(env, opener=opener_down)
check("no connection comes back as 0, never raised", code == 0 and "timed out" in text, (code, text))
check("200 is sent; 400, 413 and 426 are dropped; anything else waits",
      ED.verdict(200) == "sent" and ED.verdict(400) == "drop" and ED.verdict(426) == "drop"
      and ED.verdict(413) == "drop" and ED.verdict(0) == "retry" and ED.verdict(503) == "retry"
      and ED.verdict(429) == "retry", [ED.verdict(c) for c in (200, 400, 426, 413, 0, 503, 429)])

print("== the outbox ==")
box = ED.Outbox()
box.add(item, now=1000.0)
check("one waiting is due at once", box.due(1000.0))
got = box.take(now=1000.0)
check("take() hands it over", got is item and not box.due(1000.0))
box.result(got, 0, now=1000.0)
check("no connection: back in the box, and not tried again for a minute",
      len(box.items) == 1 and not box.due(1059.0) and box.due(1060.0), (len(box.items), box.next_at))
for i in range(ED.MAX_TRIES):
    got = box.take(now=2000.0 + i * 100)
    if got is None:
        break
    box.result(got, 503, now=2000.0 + i * 100)
check("and not for ever: dropped after %d tries" % ED.MAX_TRIES, box.items == [], len(box.items))
box = ED.Outbox()
box.add(item, now=1000.0)
got = box.take(now=1000.0)
box.result(got, 400, now=1000.0)
check("a refused message is never sent again", box.items == [] and box.dropped == 1)
box.add(item, now=1000.0)
got = box.take(now=1000.0)
box.result(got, 200, now=1000.0)
check("a sent one is counted", box.sent == 1 and box.items == [])
for i in range(ED.MOST + 20):
    box.add(dict(item, key=("x", i)), now=1000.0)
check("never more than MOST waiting, the newest kept", len(box.items) == ED.MOST
      and box.items[-1]["key"] == ("x", ED.MOST + 19), len(box.items))

print("== the journal reader ==")
JDIR = os.path.join(TMP, "journals")
os.makedirs(JDIR)
lines = [header, load, jump, signals, plain, dict(signals, BodyName="Ega 2", BodyID=2, timestamp=OLD)]
with open(os.path.join(JDIR, "Journal.2026-11-05T010000.01.log"), "w", encoding="utf-8") as handle:
    handle.write("\n".join(json.dumps(e) for e in lines) + "\n")
w = J.JournalWatcher(JDIR)
w.poll()
items = w.take_eddn()
check("the reader keeps one message: the fresh mining body, not the plain one or the old one",
      [i["message"]["BodyName"] for i in items] == ["Ega 1"], [i.get("message", {}).get("BodyName") for i in items])
check("and the app empties it by taking", w.take_eddn() == [])
check("the reader still knows the commander for the uploader name", w.cmdr == "The Announcer", w.cmdr)

try:
    import tkinter
    tkinter.Tk().destroy()
    HAVE_DISPLAY = True
except Exception as _exc:
    HAVE_DISPLAY = False
    print("  SKIP  the app needs a display (%s). Run it under xvfb-run." % _exc)

if HAVE_DISPLAY:
    import overlay as OV
    OV.foreground_is_game = lambda: None
    import edsmt as A
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    # A journal folder of its own, with nothing in it to send: the app's
    # reader makes no message of its own while the checks below put theirs
    # in by hand (on a slow desktop it read the folder above part-way
    # through and added a second).
    APP_JDIR = os.path.join(TMP, "app-journals")
    os.makedirs(APP_JDIR)
    with open(os.path.join(APP_JDIR, "Journal.2026-11-05T010000.01.log"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(json.dumps(e) for e in (header, load)) + "\n")
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as handle:
        json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": APP_JDIR,
                   "welcome_seen_version": A.APP_VERSION, "overlay_enabled": False}, handle)
    print("== in the app ==")
    check("a new install has it on", A.DEFAULT_SETTINGS.get("eddn_upload") is True)
    app = A.EDSMT()
    app.geometry("1400x900+0+0")
    app.updates.check = lambda *a, **k: None
    sent = []
    app.worker.submit = lambda tag, fn: sent.append((tag, fn))

    def pump(times=3):
        for _ in range(times):
            app.update_idletasks()
            app.update()

    pump(5)
    t = fresh_tracker()
    item = t.see(signals, now=NOW)
    app.settings["eddn_upload"] = False
    app.watcher.eddn_items = [item]
    app.eddn_sweep(now=NOW)
    check("switched off: nothing sent, nothing kept", not [s for s in sent if s[0] == ED.TAG]
          and app.eddn_box.items == [] and app.watcher.eddn_items == [])
    app.settings["eddn_upload"] = True
    app.watcher.cmdr = "The Announcer"
    app.watcher.eddn_items = [item]
    app.eddn_sweep(now=NOW)
    mine = [s for s in sent if s[0] == ED.TAG]
    check("switched on: it goes, tagged as its own, off the UI thread", len(mine) == 1, len(mine))
    posted = []
    real_upload = ED.upload
    ED.upload = lambda env, **k: (posted.append(env), (200, "OK"))[1]
    try:
        answer = mine[0][1]() if mine else ""
    finally:
        ED.upload = real_upload
    check("the job sends the envelope with the commander as uploader",
          posted and posted[0]["header"]["uploaderID"] == "The Announcer"
          and posted[0]["message"]["BodyName"] == "Ega 1", posted)
    app.eddn_sweep(now=NOW + 1)
    check("one at a time: nothing more while it is out", len([s for s in sent if s[0] == ED.TAG]) == 1)
    app.take_eddn(True, answer)
    check("200: counted as sent", app.eddn_box.sent == 1, app.eddn_box.sent)
    app.eddn_box.add(dict(item, key=("y", 1)), now=NOW)
    app.eddn_sweep(now=NOW + 2)
    app.take_eddn(True, json.dumps({"code": 0, "text": "no connection"}))
    check("no connection: kept for a minute later", len(app.eddn_box.items) == 1
          and not app.eddn_box.due(NOW + 30), len(app.eddn_box.items))
    app.eddn_sweep(now=NOW + 100)
    check("a minute on, it is tried again", app._eddn_busy is True)
    app.take_eddn(False, "boom")
    check("a job that failed outright clears the busy flag and keeps the message",
          app._eddn_busy is False and len(app.eddn_box.items) == 1, len(app.eddn_box.items))
    win = A.SettingsWindow(app)
    pump(4)
    check("Settings > Sharing has the switch", "eddn_upload" in win.toggles)
    check("and its tip says what goes", A.SETTING_TIPS.get("eddn_upload") == ED.NOTICE)
    win.destroy()
    try:
        app.destroy()
    except Exception:
        pass

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
