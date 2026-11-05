"""1.10040 (#215): the 4.5 km planning circle.

A right-click on the map offers "Planning circle here": a 4.5 km ring to
rig and drive inside without the game taking a rig (it destroys one left
5 km behind). It stays where it was put while you drive, is drawn on the map
and on the overlay's scope, says how much room is left, and is cleared from
the same menu. It is kept with the settings, so a restart keeps it.

    xvfb-run -a python tests/test_110040_planning_circle.py
"""
import math
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-ring-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import planring as PRG   # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


R = 1_200_000.0          # a body's radius in metres
LAT, LON = 12.5, -40.25

print("== where it is ==")
check("4.5 km: inside the 5 km at which the game takes a rig, with room to drive back",
      PRG.RADIUS_M == 4500.0)
ring = PRG.place_at("Ega", "Ega 1", 1200.0, -800.0, LAT, LON, R)
back = PRG.offset(ring, "Ega", "Ega 1", LAT, LON, R)
check("put where the click was, and found there again",
      back is not None and abs(back[0] - 1200.0) < 2 and abs(back[1] + 800.0) < 2, back)
moved = PRG.offset(ring, "Ega", "Ega 1", LAT + 0.01, LON, R)
check("a place on the body: drive north and it is further south of you",
      moved[1] < back[1] - 100, (back, moved))
check("on another body, or with no position, it is not drawn",
      PRG.offset(ring, "Ega", "Ega 2", LAT, LON, R) is None
      and PRG.offset(ring, "Ega", "Ega 1", None, None, R) is None)
check("nowhere to put it without a body or a position",
      PRG.make("", "Ega 1", 1, 2) is None and PRG.make("Ega", "Ega 1", None, 2) is None)
check("room to the edge: inside, and outside",
      PRG.room_m((0.0, 0.0)) == 4500.0 and round(PRG.room_m((3000.0, 4000.0))) == -500)
check("said in words", PRG.words((0.0, 1000.0)) == "Planning circle: 3.5 km to its edge"
      and PRG.words((0.0, 4800.0)) == "Outside the planning circle by 300 m"
      and PRG.words(None) == "", (PRG.words((0.0, 1000.0)), PRG.words((0.0, 4800.0))))

print("== on the overlay's scope ==")
import overlay as OV  # noqa: E402


class _Canvas:
    def __init__(self):
        self.calls = []

    def delete(self, *_a):
        self.calls = []

    def __getattr__(self, name):
        def record(*args, **kw):
            self.calls.append((name, args, kw))
        return record


class _Window:
    def winfo_width(self):
        return 420

    def winfo_height(self):
        return 420

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080


class _App:
    def colour_for(self, name):
        return "#ff7a18"


ROWS = [{"id": "1", "type": "Platinum", "range_m": 300.0, "bearing": 45.0, "rigs": 4, "location": "2"}]


def scope_with(ring):
    over = OV.Overlay(app=_App(), tk_module=None, settings={"overlay_mode": "radar"})
    over.window, over.canvas = _Window(), _Canvas()
    over.planning_ring = ring
    over.draw(ROWS, 0.0, body="Ega 1", location="2")
    return over.canvas


def texts(canvas):
    return [str(kw.get("text", "")) for name, _a, kw in canvas.calls if name == "create_text"]


def ring_marks(canvas):
    return [kw for name, _a, kw in canvas.calls
            if name in ("create_oval", "create_line") and "planring" in str(kw.get("tags", ""))]


plain = scope_with(None)
far_edge = scope_with((600.0, 0.0))
near_edge = scope_with((4350.0, 0.0))
check("no circle, nothing about one", not any("PLAN" in t for t in texts(plain)) and not ring_marks(plain))
check("with one, the scope says the room left to its edge",
      any("PLAN" in t and "3.9km" in t.replace(" ", "") for t in texts(far_edge)), texts(far_edge))
check("an edge further than the scope reaches is not drawn", not ring_marks(far_edge))
check("near the edge, the edge is drawn on the scope",
      ring_marks(near_edge) and any("PLAN" in t and "150m" in t.replace(" ", "") for t in texts(near_edge)),
      texts(near_edge))

print("== on the map, and in the app ==")
try:
    import tkinter
    tkinter.Tk().destroy()
    HAVE_DISPLAY = True
except Exception as exc:  # noqa: BLE001
    HAVE_DISPLAY = False
    print("  SKIP  the map needs a display (%s). Run it under xvfb-run." % exc)

if HAVE_DISPLAY:
    OV.foreground_is_game = lambda: None
    import edsmt as A
    root = tkinter.Tk()
    placed = []
    plan = A.PlanView(root, on_plan_ring=lambda where: placed.append(where))
    plan.place(x=0, y=0, width=800, height=600)
    for _ in range(4):
        root.update()
    plan.show(ROWS, heading=0.0, caption="Ega 1", signal="2")
    root.update()
    check("no circle: none drawn", not plan.find_withtag("planring"))
    plan.planning_ring = (500.0, 0.0)
    plan.redraw()
    root.update()
    check("with one: its ring on the map", len(plan.find_withtag("planring")) >= 1)
    footer = " ".join(plan.itemcget(i, "text") for i in plan.find_all() if plan.type(i) == "text")
    check("the footer says the room left to its edge", "planning circle 4.0 km to its edge" in footer, footer)
    plan._extent = 6000.0
    plan.redraw()
    root.update()
    words = " ".join(plan.itemcget(i, "text") for i in plan.find_withtag("planringlabel"))
    check("zoomed out to it, the ring is labelled with what it is", "Planning circle 4.5 km" in words, words)
    plan._extent = None
    plan.redraw()
    root.update()
    menu = plan.context_menu()
    entries = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)
               if menu.type(i) == "command"]
    check("right-click: Recentre, Planning circle here, Clear planning circle",
          entries == ["Recentre", "Planning circle here (4.5 km)", "Clear planning circle"], entries)
    viewport = plan.last_viewport
    x, y = viewport.to_canvas(1000.0, 250.0)
    plan.plan_ring_at(x, y)
    check("Planning circle here: the app is told where, in metres from you",
          placed and abs(placed[-1][0] - 1000.0) < 3 and abs(placed[-1][1] - 250.0) < 3, placed)
    plan.clear_plan_ring()
    check("Clear: the app is told to drop it", placed[-1] is None, placed)
    menu.destroy()
    plan.destroy()
    root.destroy()

    app = A.EDSMT.__new__(A.EDSMT)
    app.settings = dict(A.DEFAULT_SETTINGS)
    said = []
    app.say = lambda text, colour=None: said.append(str(text))
    app.redraw = lambda: None
    A.save_settings = lambda data: True
    app._map_here = ("Ega", "Ega 1", (LAT, LON), R)
    app.place_planning_ring((1000.0, 0.0))
    kept = app.settings.get("planning_ring")
    check("put down: kept with the settings as a place on the body",
          isinstance(kept, dict) and kept["body"] == "Ega 1" and "lat" in kept, kept)
    where = app.planning_offset("Ega", "Ega 1", (LAT, LON), R)
    check("and found again from where you are", where and abs(where[0] - 1000.0) < 3, where)
    check("and said", any("Planning circle" in s for s in said), said)
    app.place_planning_ring(None)
    check("cleared", app.settings.get("planning_ring") is None
          and app.planning_offset("Ega", "Ega 1", (LAT, LON), R) is None)
    app._map_here = None
    app.place_planning_ring((10.0, 10.0))
    check("with no position on a body, nothing is put down, and it says so",
          app.settings.get("planning_ring") is None and "surface" in said[-1].lower(), said[-1:])

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
