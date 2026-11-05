"""1.10040: the ship minimap (#126).

Flying low over a body with finds on the community map, the scope comes up
by itself in the ship: the body's sites round the ship, you drawn as a
ship, the range widened to suit a ship's speed and height. It goes again
as you climb away or land. A switch, on to begin with. Nothing changes in
the Rhino, on foot, in orbit, or over a body with nothing on it.

Pure parts run anywhere; the app on the real toolkit under xvfb:

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_shipview.py
"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-shipview-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import shipview as SH  # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


class State:
    def __init__(self, **kw):
        self.in_ship = True
        self.in_srv = False
        self.on_foot = False
        self.landed = False
        self.has_position = True
        self.altitude = 4000.0
        self.altitude_from_average = False
        self.__dict__.update(kw)


print("== when the minimap is wanted ==")
on = {"ship_minimap": True}
check("low in the ship over a body with finds: wanted", SH.minimap_wanted(on, State(), True))
check("switched off: never", not SH.minimap_wanted({"ship_minimap": False}, State(), True))
check("nothing on the body: no", not SH.minimap_wanted(on, State(), False))
check("in the Rhino: no (the scope has its own rules there)",
      not SH.minimap_wanted(on, State(in_ship=False, in_srv=True), True))
check("on foot: no", not SH.minimap_wanted(on, State(on_foot=True), True))
check("landed: no", not SH.minimap_wanted(on, State(landed=True), True))
check("too high: no", not SH.minimap_wanted(on, State(altitude=SH.MINIMAP_ALTITUDE_M + 1), True))
check("in orbital cruise, where the height is from the body's average: no",
      not SH.minimap_wanted(on, State(altitude=500.0, altitude_from_average=True), True))
check("no height known: no", not SH.minimap_wanted(on, State(altitude=None), True))
check("no position: no", not SH.minimap_wanted(on, State(has_position=False), True))
check("no state at all: no", not SH.minimap_wanted(on, None, True))
check("the switch is on for everybody unless turned off", SH.minimap_wanted({}, State(), True))

print("== the range ==")
check("on the ground the floor is the scope's own", SH.range_floor_m(0.0, 250.0) == 250.0)
check("at 4 km up, a ship sees further: at least twice the height",
      SH.range_floor_m(4000.0, 250.0) == 8000.0, SH.range_floor_m(4000.0, 250.0))
check("never past the minimap's own cap", SH.range_floor_m(9000.0, 250.0) == SH.MINIMAP_RANGE_CAP_M)
check("a missing height is the floor", SH.range_floor_m(None, 250.0) == 250.0)

print("== the words ==")
check("the caption says the height", SH.caption(4000.0) == "ship · 4.0 km up")
check("and metres low down", SH.caption(320.0) == "ship · 320 m up")
check("nothing without a height", SH.caption(None) == "ship")

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
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as handle:
        json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS,
                   "welcome_seen_version": A.APP_VERSION, "overlay_enabled": True,
                   "overlay_rhino_only": True}, handle)
    check("a new install has the ship minimap on", A.DEFAULT_SETTINGS.get("ship_minimap") is True)
    app = A.EDSMT()
    app.geometry("1400x900+0+0")
    app.updates.check = lambda *a, **k: None

    def pump(times=3):
        for _ in range(times):
            app.update_idletasks()
            app.update()

    def settle_until(cond, seconds=4.0):
        end = time.time() + seconds
        while time.time() < end:
            pump(1)
            if cond():
                return True
            time.sleep(0.02)
        return cond()

    print("== in the app ==")
    pump(5)
    app.shared = {("ega", "ega 1"): {"at": time.time(), "rows": [
        {"id": "shared-1", "system": "Ega", "body": "Ega 1", "location": "3", "commodity": "Tritium",
         "rigs": "6", "amount": "High", "density": "Medium", "lat": "10.000000", "lon": "20.000000",
         "cmdr": "Rocky Miner", "shared": True, "when": "2026-11-01T10:00:00Z"}]}}
    # The game's state, as the journal reader hands it over once it has
    # read something: the reader itself, before any poll.
    state = app.watcher
    app.game = state
    check("the game state carries the height and where it is measured from",
          hasattr(state, "altitude") and hasattr(state, "altitude_from_average"))
    app.here = lambda: ("Ega", "Ega 1")
    for name, value in (("in_ship", True), ("in_srv", False), ("in_rhino", False), ("on_foot", False),
                        ("landed", False), ("has_position", True), ("lat", 10.02), ("lon", 20.02),
                        ("altitude", 3000.0), ("altitude_from_average", False), ("radius_m", 2.0e6),
                        ("heading", 90.0)):
        try:
            setattr(state, name, value)
        except Exception:
            pass
    check("low in the ship over Ega 1: the boxes are wanted", app.overlay_wanted_now(), app.overlay_wanted_now())
    app.settings["ship_minimap"] = False
    check("switched off in Settings: they are not", not app.overlay_wanted_now())
    app.settings["ship_minimap"] = True
    state.altitude = 50000.0
    check("climbing away: not", not app.overlay_wanted_now())
    state.altitude = 3000.0
    app.redraw()
    pump(2)
    check("the scope's floor widens with the height",
          app.overlay._radar_floor_m() >= 6000.0, app.overlay._radar_floor_m())
    win = A.SettingsWindow(app)
    pump(4)
    check("Settings > Overlay has the switch", "ship_minimap" in win.toggles)
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
