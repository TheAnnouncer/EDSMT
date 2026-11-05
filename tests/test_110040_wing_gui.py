"""1.10040 (#170, #171, #172): the wing on the real toolkit.

- Settings -> Rigs -> Wing link has "Link with my in-game wing by itself"
  and "Split the rig plan's pins between the wing", each with its note.
- A WingJoin in the journal and the app beats to the in-game wing link by
  itself; the answer puts the wingmate on the main map and the overlay's
  scope - their Rhino, rigs, sweep and finds - in that wingmate's colour,
  and their share of the rig plan's pins in it too.
- A WingLeave and the link is gone: a goodbye, and nothing of theirs left.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_wing_gui.py
"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-winggui-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

fails = []


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
            traceback.print_exc(limit=8)
        return fn
    return wrap


try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    print("  SKIP  the app needs a display (%s). Run it under xvfb-run." % _exc)
    raise SystemExit(0)

import socket            # noqa: E402

_real_connect = socket.socket.connect


def _refuse(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        raise OSError("this check runs offline")
    return _real_connect(self, address)


socket.socket.connect = _refuse
socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(OSError("offline"))

import overlay as OV     # noqa: E402
OV.foreground_is_game = lambda: None
import edsmt as A        # noqa: E402
import rigplan as RP     # noqa: E402
import wingmates as WM   # noqa: E402
A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
    json.dump({"asked_to_share": True, "welcome_seen_version": A.APP_VERSION, "tour_done": True,
               "journal_dir": JOURNALS, "find_unlocked": True}, _f)

SYSTEM, BODY = "Ega", "Ega 1"
RADIUS = 1800000.0
HOME = (12.5, -45.5)
JOURNAL = os.path.join(JOURNALS, "Journal.2026-11-04T120000.01.log")
STAMP = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def spot(east, north):
    return RP.from_local(HOME, east, north, RADIUS)


def emit(*events):
    with open(JOURNAL, "a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")


def status(lat, lon):
    with open(os.path.join(JOURNALS, "Status.json"), "w", encoding="utf-8") as handle:
        json.dump({"timestamp": STAMP, "event": "Status", "Flags": (1 << 21) | (1 << 26),
                   "Latitude": lat, "Longitude": lon, "Heading": 90, "Altitude": 0,
                   "BodyName": BODY, "PlanetRadius": RADIUS}, handle)


class Link:
    """Stands in for the community link: records the wing's beats, sends nothing."""
    ready = False
    can_read = True
    can_verify = False
    share_name = True
    enabled = True

    def __init__(self):
        self.auto, self.coded = [], []

    def wing_auto(self, beat):
        self.auto.append(beat)
        return True

    def wing(self, code, beat):
        self.coded.append((code, beat))
        return True

    def __getattr__(self, name):
        return lambda *args, **kwargs: False


app = A.EDSMT()
app.geometry("1600x1000+0+0")
app.updates.check = lambda *args, **kwargs: None
app.community.enabled = False
app.community = Link()


def pump(times=3):
    for _ in range(times):
        app.update_idletasks()
        app.update()


def settle_until(test, seconds=6.0):
    """Tick and pump until `test()` holds, or the time is up."""
    until = time.time() + seconds
    while time.time() < until:
        app.tick()
        pump(2)
        try:
            if test():
                return True
        except Exception:
            pass
        time.sleep(0.05)
    return bool(test())


def walk(widget):
    out = [widget]
    for child in widget.winfo_children():
        out += walk(child)
    return out


def texts_in(widget):
    found = []
    for w in walk(widget):
        try:
            text = w.cget("text")
        except Exception:
            continue
        if isinstance(text, str) and text:
            found.append(text)
    return found


def items(canvas, tag):
    return list(canvas.find_withtag(tag)) if canvas is not None else []


def colours_of(canvas, tag):
    out = set()
    for item in items(canvas, tag):
        for option in ("fill", "outline"):
            try:
                value = canvas.itemcget(item, option)
            except Exception:
                continue
            if value:
                out.add(value.lower())
    return out


pump()
emit({"timestamp": STAMP, "event": "Fileheader", "gameversion": "4.4.2.1", "part": 1},
     {"timestamp": STAMP, "event": "Commander", "Name": "Jameson", "FID": "F1"},
     {"timestamp": STAMP, "event": "LoadGame", "Commander": "Jameson", "FID": "F1"},
     {"timestamp": STAMP, "event": "FSDJump", "StarSystem": SYSTEM, "SystemAddress": 77,
      "StarPos": [-171.0, 230.9, 0.5]},
     {"timestamp": STAMP, "event": "ApproachBody", "StarSystem": SYSTEM, "Body": BODY},
     {"timestamp": STAMP, "event": "Touchdown", "Latitude": HOME[0], "Longitude": HOME[1],
      "StarSystem": SYSTEM, "Body": BODY, "PlayerControlled": True},
     {"timestamp": STAMP, "event": "LaunchSRV", "SRVType": "mev_rhino",
      "SRVType_Localised": "SRV Rhino", "Loadout": "default", "ID": 53, "PlayerControlled": True})
status(*HOME)
app.tick()
pump(2)


@section("Settings -> Rigs -> Wing link")
def _settings():
    win = A.SettingsWindow(app)
    pump(4)
    try:
        check("a switch to link with the in-game wing by itself, and one to split the pins",
              "wing_auto" in win.toggles and "wing_split_pins" in win.toggles)
        texts = texts_in(win.pages["Rigs"])
        check("in plain words", "Link with my in-game wing by itself" in texts
              and "Split the rig plan's pins between the wing" in texts)
        check("both on for a new install, as the switches show",
              win.toggles["wing_auto"].get() is True and win.toggles["wing_split_pins"].get() is True)
        saved = []
        real_apply = app.apply_settings
        app.apply_settings = lambda data: saved.append(dict(data))
        try:
            win.toggles["wing_split_pins"].set(False)
            win.save()
        finally:
            app.apply_settings = real_apply
        check("switched off and saved, it is kept off - with no wing code needed",
              saved and saved[-1].get("wing_split_pins") is False and saved[-1].get("wing_auto") is True,
              saved and {k: saved[-1].get(k) for k in ("wing_split_pins", "wing_auto")})
    finally:
        win.destroy()
        pump(2)


BEE = None


@section("a WingJoin, and the link goes up by itself")
def _join():
    global BEE
    check("no beat before the journal says there is a wing", app.community.auto == [])
    emit({"timestamp": STAMP, "event": "WingJoin", "Others": ["Bee"]})
    check("the journal's WingJoin: a beat to the in-game wing link, with no code typed",
          settle_until(lambda: app.community.auto), app.community.auto[-1:])
    beat = app.community.auto[-1]
    check("who you are and who is in your wing, from the journal",
          beat["cmdr"] == "Jameson" and beat["wing"] == ["Bee"] and beat["body"] == BODY, beat)
    app.rig_plan = {"system": SYSTEM.lower(), "body": BODY.lower(), "spacing": 78.0, "outline": [],
                    "at": time.time(),
                    "pins": [{"n": i + 1, "lat": spot(80.0 * i, 0.0)[0], "lon": spot(80.0 * i, 0.0)[1]}
                             for i in range(6)]}
    app.settings["wing_split_pins"] = True
    BEE = {"name": "Bee", "system": SYSTEM, "body": BODY, "lat": spot(200.0, 0.0)[0],
           "lon": spot(200.0, 0.0)[1], "heading": 90.0, "in_srv": True, "age_s": 0.5,
           "rigs": [{"n": 1, "lat": spot(240.0, 40.0)[0], "lon": spot(240.0, 40.0)[1]}],
           "scan_m": 2000.0, "sweep": [list(spot(0.0, 300.0 * k)) for k in range(6)],
           "finds": [{"c": "Painite", "lat": spot(-150.0, 0.0)[0], "lon": spot(-150.0, 0.0)[1],
                      "d": False}]}
    app.take_wing_auto(True, json.dumps({"members": [BEE]}))
    check("the answer: Bee is on the link, and it is said",
          [m["name"] for m in app.wing_auto_mates] == ["Bee"]
          and "Bee" in app.status.cget("text"), app.status.cget("text"))


@section("the main map: Bee's Rhino, rigs, sweep and finds, in Bee's colour")
def _map():
    colour = A.WM.colours(["Jameson", "Bee"])[WM.fold("Bee")].lower()
    app.redraw()
    pump(2)
    canvas = app.plan
    check("Bee's Rhino and name", items(canvas, "wingmate"), canvas.find_all()[:5])
    check("Bee's rig", items(canvas, "wingrig"))
    check("the ground Bee has swept", items(canvas, "wingswept") and items(canvas, "wingtrail"))
    check("the find Bee marked", items(canvas, "wingfind"))
    check("every one of them in Bee's colour", colours_of(canvas, "wing") == {colour},
          (colours_of(canvas, "wing"), colour))


@section("the overlay's scope: Bee in Bee's colour, and the pins split")
def _scope():
    colour = A.WM.colours(["Jameson", "Bee"])[WM.fold("Bee")].lower()
    overlay = app.overlay
    check("the overlay is on, as for a new install", overlay.showing)
    app.redraw()
    pump(3)
    panel = (getattr(overlay, "panels", None) or {}).get(OV.RADAR)
    canvas = getattr(panel, "canvas", None)
    check("the scope is up", canvas is not None, getattr(overlay, "panels", None))
    if canvas is None:
        return
    check("Bee's Rhino, rig, sweep line and find on the scope",
          items(canvas, "wingmark") and items(canvas, "wingtrail") and items(canvas, "wingfind"))
    check("all in Bee's colour", colours_of(canvas, "wingmark") == {colour},
          (colours_of(canvas, "wingmark"), colour))
    marks = app.plan_marks()
    check("Bee takes P1-P3 of the plan (by name), you P4-P6, and P4 is next",
          [p.get("mine") for p in marks["pins"]] == [False] * 3 + [True] * 3 and marks["next"] == 4,
          [(p["n"], p.get("mine")) for p in marks["pins"]])
    pins = [canvas.itemcget(i, "text") for i in items(canvas, "planmark")
            if canvas.type(i) == "text"]
    check("Bee's pins carry Bee's initial on the scope", "P1B" in pins and "P4" in pins, pins)
    check("and Bee's colour", colour in colours_of(canvas, "planmark"), colours_of(canvas, "planmark"))


@section("a WingLeave, and the link is gone")
def _leave():
    before = len(app.community.auto)
    emit({"timestamp": STAMP, "event": "WingLeave"})
    check("a goodbye goes out", settle_until(lambda: len(app.community.auto) > before
                                             and app.community.auto[-1].get("leave") is True))
    app.redraw()
    pump(2)
    check("and nothing of Bee's is left on the map", not items(app.plan, "wing"))
    check("nor any pin of Bee's", all(p.get("mine", True) for p in (app.plan_marks() or {}).get("pins") or []))


if __name__ == "__main__":
    print()
    print("FAILURES:", len(fails))
    for f in fails:
        print("  -", f)
    try:
        app.destroy()
    except Exception:
        pass
    sys.exit(1 if fails else 0)
