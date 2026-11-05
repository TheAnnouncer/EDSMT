"""1.10040: the scope comes back once every pin has a rig on it.

Reported on Discord, 2 Nov: "after I've placed rigs, it doesn't go back to
the radar scope." The planner's close-up stayed on while any pin was within
600 m - done or not - so with every rig down the scope sat zoomed on the
finished pins. The close-up is for pins still to drive to; with none left
the scope is the scope again.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_plan_done.py
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-plandone-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as exc:
    print("  SKIP  needs a display (%s). Run it under xvfb-run." % exc)
    sys.exit(0)

import overlay as OV  # noqa: E402
OV.foreground_is_game = lambda: None
import edsmt as A     # noqa: E402
import survey as SV   # noqa: E402

A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as handle:
    json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS,
               "welcome_seen_version": A.APP_VERSION}, handle)
app = A.EDSMT()
app.updates.check = lambda *a, **k: None
for _ in range(5):
    app.update()

R = 2.0e6
HOME = (10.0, 20.0)


def at(bearing, metres):
    return SV.destination(HOME[0], HOME[1], bearing, metres, R)


class State:
    """The game as the planner sees it: a position on a body, in the Rhino."""
    has_position, radius_m, lat, lon, heading = True, R, HOME[0], HOME[1], 0.0
    in_srv, in_rhino, in_ship, on_foot, landed = True, True, False, False, False
    rhino_parked = None


state = State()
app.game = state
app.here = lambda: ("Ega", "Ega 1")
app._trace = None
pins = [dict(n=i + 1, lat=at(90, 80 * (i + 1))[0], lon=at(90, 80 * (i + 1))[1]) for i in range(3)]
app.rig_plan = {"system": "ega", "body": "ega 1", "spot": "1", "spacing": 78.0, "pins": pins,
                "outline": [at(0, 300), at(90, 300), at(180, 300)]}
app.restore_plan = lambda: None
app.shared_plan = lambda: None
app.wing_plan = lambda plan, where: plan
app.wing_rigs_here = lambda: []
app.wing_active = lambda: False
app.pin_owners = lambda plan, pins: {}

print("== pins still to drive to ==")
app._rigs_here = lambda: []
marks = app._plan_marks()
check("a plan with no rigs down yet: the close-up, pin 1 next",
      marks and marks["near"] is True and marks["next"] == 1 and marks["done"] == 0, marks)

print("== two of three down ==")
app._rigs_here = lambda: [{"lat": p["lat"], "lon": p["lon"]} for p in pins[:2]]
marks = app._plan_marks()
check("still the close-up, pin 3 next", marks["near"] is True and marks["next"] == 3 and marks["done"] == 2, marks)

print("== every rig down ==")
app._rigs_here = lambda: [{"lat": p["lat"], "lon": p["lon"]} for p in pins]
marks = app._plan_marks()
check("every pin done: nothing next", marks["done"] == 3 and marks["next"] is None and marks["next_pin"] is None, marks)
check("and the scope is the scope again - no close-up", marks["near"] is False, marks)
check("the pins are still drawn, as done", len(marks["pins"]) == 3 and all(p["done"] for p in marks["pins"]))

print("== pins far away ==")
far = [dict(n=1, lat=at(90, 5000)[0], lon=at(90, 5000)[1])]
app.rig_plan = dict(app.rig_plan, pins=far)
app._rigs_here = lambda: []
marks = app._plan_marks()
check("a pin 5 km off: no close-up until it is near", marks["near"] is False and marks["next"] == 1, marks)

try:
    app.destroy()
except Exception:
    pass
print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
