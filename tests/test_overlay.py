"""The in-game overlay, checked without a screen.

The window itself cannot be created here - there is no display and no
Tkinter - but every number that decides where a mark lands is a plain
function, and those are what break. The scenario is the same Ega 1 session
the other suites use: haematite at 896m, 1.26km and 1.47km, plus one
deposit behind the commander, which is the case that made the overlay worth
building at all.
"""
import math
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import overlay as OV
# These checks are about what the boxes draw, not about which window happens
# to be in front of the machine running them. On Windows that is the console
# or the test window, never the game, so the boxes would stand down and draw
# nothing - which is right in play and meaningless here. "Cannot tell"
# (None) is the one answer that leaves them up; the checks that are about
# standing down set their own answer.
OV.foreground_is_game = lambda: None

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)

W = 900.0

print("== which way is it, relative to where I am pointing ==")
check("dead ahead is zero", OV.relative_bearing(90, 90) == 0)
check("to the right is positive", OV.relative_bearing(0, 90) == 90)
check("to the left is negative", OV.relative_bearing(90, 0) == -90)
check("wraps past north", OV.relative_bearing(350, 10) == 20)
check("wraps the other way", OV.relative_bearing(10, 350) == -20)
check("directly behind is a half turn, whichever way you read it",
      abs(OV.relative_bearing(0, 180)) == 180)
check("and always pins to the same edge rather than flickering",
      OV.edge_x(0, 180, W) == OV.edge_x(0, 180.0, W) < W / 2)

print("== where it lands on the tape ==")
check("ahead sits in the middle", abs(OV.tape_x(0, 0, W) - W / 2) < 1e-9)
check("hard right is the right edge", abs(OV.tape_x(0, 60, W) - W) < 1e-9)
check("hard left is the left edge", abs(OV.tape_x(0, 300, W)) < 1e-9)
check("halfway right is three quarters",
      abs(OV.tape_x(0, 30, W) - W * 0.75) < 1e-9)
check("outside the span falls off", OV.tape_x(0, 90, W) is None)
check("a wider span catches it", OV.tape_x(0, 90, W, span_deg=200) is not None)
check("off to the right pins right", OV.edge_x(0, 120, W) > W / 2)
check("off to the left pins left", OV.edge_x(0, 240, W) < W / 2)

print("== the compass ticks ==")
marks = OV.cardinal_marks(0, W)
check("every tick is on the tape", all(0 <= m["x"] <= W for m in marks))
check("north is drawn while facing north",
      any(m["label"] == "N" for m in marks))
check("north is a major tick",
      all(m["major"] for m in marks if m["bearing"] == 0))
check("the diagonals are named",
      any(m["label"] == "NE" for m in OV.cardinal_marks(30, W)))
check("facing south shows south",
      any(m["label"] == "S" for m in OV.cardinal_marks(180, W)))
check("ticks are unique", len({m["bearing"] for m in marks}) == len(marks))

print("== the deposits ==")
ROWS = [
    {"range_m": 1470.0, "bearing": 12.0,
     "deposit": {"id": "c", "commodity": "Haematite", "rigs": "4"}},
    {"range_m": 896.0, "bearing": 350.0,
     "deposit": {"id": "a", "commodity": "Haematite", "rigs": "6"}},
    {"range_m": 1260.0, "bearing": 185.0,
     "deposit": {"id": "b", "commodity": "Copper", "rigs": ""}},
]
marks = OV.target_marks(ROWS, 0.0, W)
check("nearest first", [m["id"] for m in marks] == ["a", "b", "c"], [m["id"] for m in marks])
check("the one behind is kept, not dropped",
      any(m["id"] == "b" for m in marks))
check("and is flagged as off the tape",
      [m for m in marks if m["id"] == "b"][0]["offscreen"] is True)
check("the ones in front are not",
      not any(m["offscreen"] for m in marks if m["id"] in ("a", "c")))
check("everything has an x on screen", all(0 <= m["x"] <= W for m in marks))
check("rigs carry through",
      [m for m in marks if m["id"] == "a"][0]["rigs"] == "6")
check("a missing rig count is blank, not None",
      [m for m in marks if m["id"] == "b"][0]["rigs"] == "")
check("the limit is honoured", len(OV.target_marks(ROWS, 0.0, W, limit=2)) == 2)
check("the limit keeps the nearest",
      [m["id"] for m in OV.target_marks(ROWS, 0.0, W, limit=2)] == ["a", "b"])
check("no deposits, no marks", OV.target_marks([], 0.0, W) == [])

print("== labels do not pile up ==")
close = [{"range_m": 100 + n, "bearing": n * 0.5,
          "deposit": {"id": str(n), "commodity": "Haematite", "rigs": "3"}}
         for n in range(6)]
stacked = OV.stack(OV.target_marks(close, 0.0, W))
check("every mark got a row", all("row" in m for m in stacked))
rows = {}
for m in stacked:
    rows.setdefault(m["row"], []).append(m["x"])
check("a cluster is spread over rows", len(rows) > 1, sorted(rows))
gaps_ok = all(abs(a - b) >= 74.0
              for xs in rows.values() for a in xs for b in xs if a is not b)
check("nothing overlaps within a row", gaps_ok)
spread = [{"range_m": 100, "bearing": 0,
           "deposit": {"id": "x", "commodity": "Copper", "rigs": ""}},
          {"range_m": 200, "bearing": 40,
           "deposit": {"id": "y", "commodity": "Copper", "rigs": ""}}]
one_row = OV.stack(OV.target_marks(spread, 0.0, W))
check("well separated marks share one row",
      {m["row"] for m in one_row} == {0})

print("== what it says ==")
check("metres under a kilometre", OV.format_range(896) == "896m")
check("kilometres above it", OV.format_range(1260) == "1.26km")
check("exactly a kilometre is km", OV.format_range(1000) == "1.00km")
check("nonsense does not crash", OV.format_range(None) == "-")
check("a string range still works", OV.format_range("450") == "450m")
check("straight on is up", OV.turn_arrow(2) == "^")
check("swing right", OV.turn_arrow(45) == ">")
check("swing left", OV.turn_arrow(-45) == "<")
check("turn round", OV.turn_arrow(178) == "v")

print("== settings the window reads ==")
import ast, io
src = io.open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "edsmt.py"), encoding="utf-8").read()
tree = ast.parse(src)
defaults = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Assign) and any(
            getattr(t, "id", "") == "DEFAULT_SETTINGS" for t in node.targets):
        defaults = {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
used = {n.args[0].value for n in ast.walk(ast.parse(io.open(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "overlay.py"), encoding="utf-8").read()))
    if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "get"
    and n.args and isinstance(n.args[0], ast.Constant)
    and str(n.args[0].value).startswith("overlay_")}
# A key the overlay reads that edsmt.py has no default for is how the
# overlay ends up silently reading None. Keys the radar has grown but
# DEFAULT_SETTINGS has not been given yet are declared in PENDING_SETTINGS,
# and every one of them has to be read with an inline fallback so a settings
# file that has never heard of it still opens a working scope.
pending = dict(getattr(OV, "PENDING_SETTINGS", {}))
defaults_mode = ""
for _node in ast.walk(tree):
    if isinstance(_node, ast.Assign) and any(
            getattr(t, "id", "") == "DEFAULT_SETTINGS" for t in _node.targets):
        for _k, _v in zip(_node.value.keys, _node.value.values):
            if isinstance(_k, ast.Constant) and _k.value == "overlay_mode":
                defaults_mode = getattr(_v, "value", "")
overlay_tree = ast.parse(io.open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "overlay.py"), encoding="utf-8").read())
check("every overlay setting the window reads has a default or a declared fallback",
      used <= (defaults | set(pending)), sorted(used - defaults - set(pending)))
check("nothing still declared pending has quietly been added to DEFAULT_SETTINGS",
      not (set(pending) & defaults), sorted(set(pending) & defaults))
bare = [n.args[0].value for n in ast.walk(overlay_tree)
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "get"
        and n.args and isinstance(n.args[0], ast.Constant)
        and n.args[0].value in pending and len(n.args) < 2]
check("every pending key is read with its fallback spelled out", not bare, bare)
# The strip is what you get handed. Two other tools do a scope
# better than we will, and the strip is the one that needs nothing
# from you to be useful. The scope is opt-in.
# overlay_mode has graduated out of PENDING_SETTINGS into
# DEFAULT_SETTINGS, because it is now pickable in Settings. A mode that
# cannot be selected is a mode nobody has - which is exactly how the radar
# came to be reported as "removed" the day after it was built.
check("the strip is the shape it opens in", defaults_mode == "strip",
      defaults_mode)
check("and the radar is selectable, not just present in the code",
      '"overlay_mode"' in src and "Radar scope" in src)
check("what the scope centres on is pickable too",
      '"overlay_centre"' in src and "My SRV" in src)
check("the settings screen exposes them all",
      all(('"%s"' % k) in src for k in sorted(defaults) if k.startswith("overlay_")
          and k not in ("overlay_x", "overlay_y")))
check("the overlay is off until asked for",
      '"overlay_enabled": False' in src)

print("== the window is actually visible ==")
# This exists because the overlay shipped invisible on every machine it was
# tried on. The window was created, sized, raised and drawn correctly - and
# then the click-through code wrote WS_EX_LAYERED onto it with
# SetWindowLongW. Windows drops a layered window's colour key AND its alpha
# the moment that bit is written that way, and Tk had already set both via
# -transparentcolor. Layered, no colour key, no alpha, renders as nothing.
# No error. No clue. Click-through defaults to on, so it hit every user.
import types

class _FakeUser32:
    WS_EX_LAYERED = 0x80000
    def __init__(self):
        self.style = 0
        self.writes = []
    def GetParent(self, hwnd): return 0
    def GetDesktopWindow(self): return 999
    def GetWindowLongW(self, hwnd, index): return self.style
    def SetWindowLongW(self, hwnd, index, value):
        self.writes.append(value); self.style = value; return 1

class _FakeWindow:
    def __init__(self): self.attrs = []
    def winfo_id(self): return 12345
    def attributes(self, name, value=None): self.attrs.append((name, value))

def with_fake_ctypes(settings):
    user32 = _FakeUser32()
    fake = types.ModuleType("ctypes")
    fake.windll = types.SimpleNamespace(user32=user32)
    real = sys.modules.get("ctypes")
    sys.modules["ctypes"] = fake
    try:
        strip = OV.Overlay(app=None, tk_module=None, settings=settings)
        strip.window = _FakeWindow()
        strip.apply_click_through()
        return user32, strip.window
    finally:
        if real is not None: sys.modules["ctypes"] = real
        else: del sys.modules["ctypes"]

user32, window = with_fake_ctypes({"overlay_click_through": True})
check("click-through was applied", user32.writes, user32.writes)
check("WS_EX_LAYERED is never written - that is what made it invisible",
      all(not (value & _FakeUser32.WS_EX_LAYERED) for value in user32.writes),
      [hex(v) for v in user32.writes])
check("WS_EX_TRANSPARENT is set when locked",
      all(value & 0x20 for value in user32.writes), [hex(v) for v in user32.writes])
check("transparency is re-asserted after the style is written",
      any(name == "-transparentcolor" for name, _ in window.attrs), window.attrs)
check("and so is opacity", any(name == "-alpha" for name, _ in window.attrs),
      window.attrs)

user32, window = with_fake_ctypes({"overlay_click_through": False})
check("unlocked clears WS_EX_TRANSPARENT so it can be dragged",
      all(not (value & 0x20) for value in user32.writes),
      [hex(v) for v in user32.writes])
check("and still never touches the layered bit",
      all(not (value & _FakeUser32.WS_EX_LAYERED) for value in user32.writes))

print("== it sizes itself to the screen it is on ==")
class _Screen:
    def __init__(self, w, h): self.w, self.h = w, h
    def winfo_screenwidth(self): return self.w
    def winfo_screenheight(self): return self.h

strip = OV.Overlay(app=None, tk_module=None, settings={"overlay_mode": "strip"})
w4k, h4k, x4k, y4k = strip.placement(_Screen(3840, 2160))
w1080, h1080, x1080, y1080 = strip.placement(_Screen(1920, 1080))
check("a 4K screen gets a wider strip than a 1080p one", w4k > w1080, (w4k, w1080))
check("it fits on the 4K screen", w4k <= 3840 and x4k + w4k <= 3840, (x4k, w4k))
check("it fits on the 1080p screen", w1080 <= 1920 and x1080 + w1080 <= 1920,
      (x1080, w1080))
check("it is centred when nothing was saved", abs(x4k - (3840 - w4k) // 2) <= 1)
check("and near the top", y4k < 2160 * 0.2, y4k)

# The saved-position trap: drag it onto a second monitor, unplug that
# monitor, and it must not come back somewhere you cannot see it.
off = OV.Overlay(app=None, tk_module=None,
                 settings={"overlay_mode": "strip",
                           "overlay_x": 5000, "overlay_y": 3000,
                           "overlay_width": 900, "overlay_height": 120})
w, h, x, y = off.placement(_Screen(1920, 1080))
check("a position from a monitor that is gone is pulled back on screen",
      x < 1920 and y < 1080, (x, y))
check("with enough of it showing to grab", x <= 1920 - 120, x)

huge = OV.Overlay(app=None, tk_module=None,
                  settings={"overlay_mode": "strip",
                            "overlay_width": 99999, "overlay_height": 99999})
w, h, _, _ = huge.placement(_Screen(1920, 1080))
check("a silly size is clamped to the screen", w <= 1920 and h <= 1080, (w, h))

# ---------------------------------------------------------------------------
# The radar
# ---------------------------------------------------------------------------
# The scope is a picture of a patch, and every number in it is a plain
# function in planview.py for exactly the reason the tape's are: the window
# cannot be opened here, but where each mark lands can be checked to the
# metre. The scenario is the Ega session again - one mining location signal
# with three deposits in a tight knot, one worked-out copper closer in than
# any of them, and one find logged on the far side of the body.

import planview as PV

print("== metres to bearings and back ==")
east, north = PV.to_offset(1000, 90)
check("due east is east", abs(east - 1000) < 1e-6 and abs(north) < 1e-6,
      (east, north))
east, north = PV.to_offset(1000, 180)
check("due south is negative north", abs(north + 1000) < 1e-6, (east, north))
check("a blank range is the origin", PV.to_offset("", None) == (0.0, 0.0))
check("junk is the origin too", PV.to_offset("nonsense", "rubbish") == (0.0, 0.0))
for metres, bearing in ((896, 350), (1260, 185), (40, 0), (2500, 91.5)):
    back_m, back_b = PV.to_polar(*PV.to_offset(metres, bearing))
    check("%dm on %03d survives the round trip" % (metres, bearing),
          abs(back_m - metres) < 1e-6 and abs(back_b - bearing) < 1e-6,
          (back_m, back_b))
check("the origin has no bearing rather than crashing",
      PV.to_polar(0.0, 0.0) == (0.0, 0.0))
check("the middle of nothing is the origin", PV.centroid([]) == (0.0, 0.0))
check("the middle of one point is that point", PV.centroid([(3.0, 4.0)]) == (3.0, 4.0))
check("the middle of two is between them",
      PV.centroid([(0.0, 0.0), (10.0, 20.0)]) == (5.0, 10.0))

print("== how far the view has to reach ==")
check("nothing to show still gives a usable radius",
      PV.extent_for([], floor_m=250.0) == 250.0)
check("close in, the floor wins",
      PV.extent_for([(10.0, 10.0)], floor_m=250.0) == 250.0)
check("further out, the content wins",
      PV.extent_for([(0.0, 1000.0)], floor_m=250.0, headroom=1.25) == 1250.0)
check("a find on the far side of the body does not empty the scope",
      PV.extent_for([(0.0, 3_000_000.0)], cap_m=50000.0) == 50000.0)
check("the cap can never cut below the floor",
      PV.extent_for([(0.0, 400.0)], floor_m=250.0, cap_m=100.0) == 250.0)
check("no cap means no cap",
      PV.extent_for([(0.0, 3_000_000.0)]) > 50000.0)

print("== where the mining location signal is ==")
def dep(**kw):
    row = {"id": kw.get("id", ""), "system": "Ega", "body": "Ega 3 a",
           "location": "2", "commodity": "", "rigs": "", "amount": ""}
    row.update(kw)
    return row

def row(range_m, bearing, **kw):
    return {"range_m": float(range_m), "bearing": float(bearing),
            "deposit": dep(**kw)}

RADAR_ROWS = [
    row(896, 350, id="h", commodity="Haematite", rigs="6"),
    row(940, 5, id="s", commodity="Samarium", rigs="4"),
    row(1010, 358, id="t", commodity="Thortveitite", rigs="1"),
    row(400, 120, id="c", commodity="Copper", rigs="2", amount="Depleted"),
]

found = PV.site_centre(RADAR_ROWS)
check("the signal is named from the deposits in it", found["label"] == "LOCATION 2",
      found["label"])
check("and it counted all of them", found["count"] == 4, found["count"])
check("its centre is the middle of them",
      abs(found["east_m"] - 59.4) < 1.0 and abs(found["north_m"] - 657.0) < 1.0,
      (found["east_m"], found["north_m"]))
check("nothing recorded means no signal to centre on",
      PV.site_centre([])["count"] == 0)
check("and no label to print either", PV.site_centre([])["label"] == "")

TWO_SIGNALS = RADAR_ROWS + [
    row(5000, 200, id="p", commodity="Palladium", rigs="3", location="7"),
    row(5100, 202, id="q", commodity="Gold", rigs="2", location="7"),
]
check("the busiest signal wins by default",
      PV.site_centre(TWO_SIGNALS)["location"] == "2")
check("but a named one is honoured",
      PV.site_centre(TWO_SIGNALS, "7")["location"] == "7")
check("a name nobody has heard of falls back rather than emptying the scope",
      PV.site_centre(TWO_SIGNALS, "99")["location"] == "2")
tie = [row(4000, 10, id="a", location="9"), row(80, 10, id="b", location="3")]
check("between two equally busy signals, the one you are standing in wins",
      PV.site_centre(tie)["location"] == "3")
check("a deposit with no signal recorded still places, unlabelled",
      PV.site_centre([row(100, 0, id="z", location="")])["label"] == "SITE")

print("== the scope clips in metres, not in pixels ==")
vp = PV.Viewport(420, 420, 1000.0, margin=48, pan=(0.0, 4.0))
check("inside the outer ring is on the scope", vp.within(0.0, 999.0))
check("outside it is not", not vp.within(0.0, 1001.0))
check("exactly on it counts as on", vp.within(1000.0, 0.0))
on_ring = vp.edge_toward(0.0, 5000.0, reach=vp.radius_px(1000.0))
check("an arrow pinned to the ring lands on the ring",
      abs(math.hypot(on_ring[0] - vp.centre[0], on_ring[1] - vp.centre[1])
          - vp.radius_px(1000.0)) < 1e-6, on_ring)
check("and due north pins straight up", abs(on_ring[0] - vp.centre[0]) < 1e-9)
check("the rectangular pin still behaves as it did",
      vp.edge_toward(0.0, 5000.0)[1] < vp.centre[1])

print("== centred on the signal, not on the commander ==")
plan = PV.layout(RADAR_ROWS, vp, heading=12.0,
                 origin=(found["east_m"], found["north_m"]), clip="circle")
check("every deposit is placed", len(plan["items"]) == 4)
check("the commander comes back as part of the picture", "commander" in plan)
me = plan["commander"]
check("and sits opposite the signal centre",
      abs(me["east_m"] + found["east_m"]) < 1e-9
      and abs(me["north_m"] + found["north_m"]) < 1e-9)
check("at the range the signal is from him",
      abs(me["view_range_m"] - math.hypot(found["east_m"], found["north_m"])) < 1e-9)
check("ranges stay measured from the commander, because that is what you drive",
      abs([i for i in plan["items"] if i["id"] == "h"][0]["range_m"] - 896.0) < 1e-9)
check("while the view bearing is measured from the centre",
      abs([i for i in plan["items"] if i["id"] == "h"][0]["view_bearing"] - 316.3)
      < 1.0, [i for i in plan["items"] if i["id"] == "h"][0]["view_bearing"])
check("the two disagree, which is the whole point of a site-centred scope",
      abs([i for i in plan["items"] if i["id"] == "h"][0]["bearing"]
          - [i for i in plan["items"] if i["id"] == "h"][0]["view_bearing"]) > 10)
check("nothing in the knot is off the scope",
      not any(i["offscreen"] for i in plan["items"]))
check("the rings are round numbers", plan["ring_step_m"] in PV.NICE_STEPS_M)
check("and none of them reaches past the outer one",
      all(r["metres"] <= plan["extent_m"] * 1.02 for r in plan["rings"]))

print("== centred on the commander instead ==")
driving = PV.layout(RADAR_ROWS, vp, heading=12.0, clip="circle")
check("he is dead centre", abs(driving["commander"]["x"] - vp.centre[0]) < 1e-9
      and abs(driving["commander"]["y"] - vp.centre[1]) < 1e-9)
check("and on the scope, not pinned to the rim",
      not driving["commander"]["offscreen"])
check("view bearing and bearing now agree",
      all(abs(i["bearing"] - i["view_bearing"]) < 1e-9 for i in driving["items"]))
check("the old default origin leaves east/north exactly as they were",
      abs(driving["items"][0]["east_m"]
          - PV.to_offset(driving["items"][0]["range_m"],
                         driving["items"][0]["bearing"])[0]) < 1e-9)

print("== a find on the far side of the body ==")
far = RADAR_ROWS + [row(3_000_000, 47, id="f", commodity="Gold", rigs="5")]
wide = PV.Viewport(420, 420, 50000.0, margin=48, pan=(0.0, 4.0))
plan_far = PV.layout(far, wide, origin=(0.0, 0.0), clip="circle")
pin = [i for i in plan_far["items"] if i["id"] == "f"][0]
check("it is off the scope rather than squashing everything else",
      pin["offscreen"] is True)
check("but it is still pinned on the rim, pointing its way",
      abs(math.hypot(pin["edge"][0] - wide.centre[0],
                     pin["edge"][1] - wide.centre[1])
          - (wide.radius_px(50000.0) - 6.0)) < 1e-6, pin["edge"])
check("and it keeps its real range for the label", pin["range_m"] == 3_000_000.0)
check("the near ones are still on", not any(i["offscreen"] for i in plan_far["items"]
                                            if i["id"] != "f"))

print("== drive away and the commander pins to the rim too ==")
gone = PV.layout([], PV.Viewport(420, 420, 500.0, margin=48),
                 origin=(0.0, 9000.0), clip="circle")
check("he is off the scope", gone["commander"]["offscreen"] is True)
check("the chevron points back the way he went",
      abs(gone["commander"]["view_bearing"] - 180.0) < 1e-9,
      gone["commander"]["view_bearing"])
check("and carries how far away he is",
      abs(gone["commander"]["view_range_m"] - 9000.0) < 1e-9)

print("== nothing at all, and one thing ==")
empty = PV.layout([], vp, clip="circle")
check("no deposits does not crash", empty["items"] == [])
check("and the commander is still drawn", empty["commander"]["offscreen"] is False)
check("one deposit still gets rings", len(PV.layout([RADAR_ROWS[0]], vp)["rings"]) > 0)
check("a deposit on top of the centre has no bearing rather than blowing up",
      PV.layout([row(0, 0, id="n")], vp, clip="circle")["items"][0]["view_bearing"] == 0.0)

print("== what is on the scope, totalled ==")
check("rigs are added up", PV.total_rigs(plan["items"]) == 13,
      PV.total_rigs(plan["items"]))
check("a blank rig count counts as none",
      PV.total_rigs([{"deposit": {"rigs": ""}}]) == 0)
check("so does a nonsense one", PV.total_rigs([{"deposit": {"rigs": "six"}}]) == 0)
check("nothing on screen is no rigs", PV.total_rigs([]) == 0)

print("== where to go next ==")
target = PV.next_target(plan["items"])
check("the nearest one you have not stripped",
      target["id"] == "h", target and target["id"])
check("the closer worked-out one is skipped, not chosen",
      target["range_m"] == 896.0)
check("everything depleted means nowhere to go",
      PV.next_target([i for i in plan["items"] if i["id"] == "c"]) is None)
check("no deposits, no target", PV.next_target([]) is None)

print("== the best patch ==")
patch = PV.best_patch(plan["items"])
check("the knot was found", patch is not None)
check("all three of it", patch and patch["count"] == 3, patch and patch["count"])
check("with their rigs added up", patch and patch["rigs"] == 11,
      patch and patch["rigs"])
check("the worked-out one two kilometres off is not in it",
      patch and "c" not in {i["id"] for i in patch["items"]})
check("three different commodities", patch and len(patch["commodities"]) == 3)
check("it has somewhere to draw the bracket",
      patch and patch["radius"] > 0 and patch["x"] > 0 and patch["y"] > 0)
check("one lonely deposit is not a patch",
      PV.best_patch(PV.layout([RADAR_ROWS[0]], vp)["items"]) is None)
check("nothing is not a patch", PV.best_patch([]) is None)
check("two deposits a kilometre apart are not a patch either",
      PV.best_patch(PV.layout([row(100, 0, id="a", rigs="3"),
                               row(1200, 0, id="b", rigs="3")], vp)["items"]) is None)

print("== the scanner ring belongs to the vehicle ==")
check("the Rhino's range is stated once, where the maths is",
      PV.SCANNER_RANGE_M == 2000.0)

# ---------------------------------------------------------------------------
# And the window that draws it
# ---------------------------------------------------------------------------

class _Canvas:
    """Records every mark instead of making one."""
    def __init__(self):
        self.calls = []
    def delete(self, *_a):
        self.calls = []
    def __getattr__(self, name):
        def record(*args, **kw):
            self.calls.append((name, args, kw))
        return record

class _Window:
    def __init__(self, w=420, h=420):
        self.w, self.h = w, h
    def winfo_width(self): return self.w
    def winfo_height(self): return self.h
    def winfo_screenwidth(self): return 1920
    def winfo_screenheight(self): return 1080

class _App:
    def colour_for(self, name):
        return "#ff7a18" if name else "#9c6a3c"

def drawn(rows, heading=0.0, settings=None, size=(420, 420), **kw):
    options = {"overlay_mode": "radar", "overlay_click_through": True}
    options.update(settings or {})
    scope = OV.Overlay(app=_App(), tk_module=None, settings=options)
    scope.window = _Window(*size)
    scope.canvas = _Canvas()
    scope.draw(rows, heading, **kw)
    return scope.canvas

def texts(canvas):
    return [str(kw.get("text", "")) for name, _a, kw in canvas.calls
            if name == "create_text"]

def said(canvas, fragment):
    return any(fragment in t for t in texts(canvas))

def shapes(canvas, kind):
    return [(a, kw) for name, a, kw in canvas.calls if name == kind]

print("== the radar draws ==")
scope = drawn(RADAR_ROWS, heading=12.0)
check("something was actually drawn", len(scope.calls) > 20, len(scope.calls))
check("the body is named", said(scope, "BODY  Ega 3 a"), texts(scope)[:4])
check("the map radius is stated",
      said(scope, "MAP RADIUS"), texts(scope)[:4])
check("centred on the signal, and it says which",
      said(scope, "CENTRE  LOCATION 2"), texts(scope)[:6])
check("north is marked", "N" in texts(scope))
check("the rings are labelled in metres",
      any(t.endswith("m") or t.endswith("km") for t in texts(scope)))
check("every deposit is named with its rig count",
      said(scope, "Haematite (6R)") and said(scope, "Samarium (4R)")
      and said(scope, "Thortveitite (1R)"), texts(scope))
check("the rig total is on the header", said(scope, "13R"), texts(scope))
check("four deposits are counted", said(scope, "4 DEP"), texts(scope))
check("the scanner ring is drawn and labelled with its range",
      said(scope, "SCAN 2.00km"), texts(scope))
check("the best patch is called out", said(scope, "BEST PATCH  11R"), texts(scope))
check("the next target is a heading and a range, not just a dot",
      said(scope, "NEXT") and said(scope, "Haematite"), texts(scope))
wide_scope = drawn(RADAR_ROWS, heading=12.0, size=(760, 420))
check("with room, the hotkeys that record one are on it, in the order the "
      "work is done",
      said(wide_scope, "Alt+1 SITE  Alt+2 BORDER  Alt+3 DEPOSIT  Alt+4 RIG"),
      texts(wide_scope))
check("squeezed, they give way to where to go next rather than print over it",
      said(scope, "NEXT") and not said(scope, "Alt+1 SITE"), texts(scope))
# Nothing prints over anything else. Every label placed beside a mark is
# drawn from its top-left corner; rebuild each box the way the scope sized it
# and make sure no two of them touch.
CROWD = [row(300.0 + 5 * i, (37 * i) % 360, id="crowd%d" % i,
             commodity=("Haematite", "Copper", "Thorium", "Samarium")[i % 4],
             rigs=str(1 + i % 3)) for i in range(24)]
crowd = drawn(CROWD, heading=0.0, size=(420, 420), location="2")
boxes = []
for name, _a, kw in crowd.calls:
    if name == "create_text" and kw.get("anchor") == "nw":
        size = kw["font"][1]
        w, h = OV.text_box(kw["text"], size)
        boxes.append((_a[0], _a[1], _a[0] + w, _a[1] + h, kw["text"]))
clashes = [(a[4], b[4]) for i, a in enumerate(boxes) for b in boxes[i + 1:]
           if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]]
check("a crowded scope names what it can and prints nothing over anything else",
      boxes and not clashes, clashes[:4])
check("and says how many it left unnamed",
      any("unlabelled" in str(kw.get("text", "")) for n, _a, kw in crowd.calls
          if n == "create_text"))
_named = sum(1 for t in texts(crowd)
             if t.split(" (")[0] in ("Haematite", "Copper", "Thorium", "Samarium"))
_unnamed = [t for t in texts(crowd) if t.endswith(" unlabelled")]
check("and the count is finds, not ring distances or the scanner's label",
      _unnamed == ["%d unlabelled" % (len(CROWD) - _named)], (_unnamed, _named))
_two = drawn([row(420, 200, id="u1", commodity="Haematite", rigs="6"),
              row(610, 240, id="u2", commodity="Samarium", rigs="4")])
check("two finds, both named, is not '2 unlabelled'",
      not any(t.endswith("unlabelled") for t in texts(_two)), texts(_two))
check("the commander is a chevron", len(shapes(scope, "create_polygon")) >= 1)
check("and it is amber, the Radio Raxxla colour",
      any(kw.get("fill") == OV.AMBER for _a, kw in shapes(scope, "create_polygon")))
check("nothing drawn is green",
      not any(str(kw.get("fill", "")).lower() in ("green", "#00ff00", "#0f0")
              for _n, _a, kw in scope.calls))
# THE SCOPE WEARS NO FRAME. It is a hole you look through at the ground,
# and a bright rounded box round it sits in the middle of the cockpit
# whether or not you are looking at it. The cards are framed; this is not.
def _framed(canvas):
    return sum(1 for _a, kw in shapes(canvas, "create_arc")
               if kw.get("style") == "arc" and kw.get("outline") == OV.ORANGE)
check("the scope has no border drawn round it", _framed(scope) == 0,
      _framed(scope))
check("and the dish is not filled in, so you can see the ground through it",
      all(kw.get("fill") in ("", None) for _a, kw in shapes(scope, "create_oval")
          if kw.get("outline") == OV.RULE),
      [kw.get("fill") for _a, kw in shapes(scope, "create_oval")])
def _panel_canvas_rows(key, rows, **settings):
    options = {"overlay_click_through": True}
    options.update(settings)
    over = OV.Overlay(app=_App(), tk_module=None, settings=options)
    panel = OV.Panel(over, key)
    panel.window = _Window(520, 240)
    panel.canvas = _Canvas()
    over.panels = {key: panel}
    over.draw(rows, 0.0, body="Ega 3 a", location="2")
    return panel.canvas

def _panel_canvas(key, **settings):
    return _panel_canvas_rows(key, RADAR_ROWS, **settings)


_card = _panel_canvas(OV.STATUS)
check("a card still is framed - it is a panel, not a hole",
      _framed(_card) >= 4, _framed(_card))
check("the frame has all four corners, not just the two that fit",
      sum(1 for _a, kw in shapes(_card, "create_arc")
          if kw.get("style") == "arc") >= 12,
      sum(1 for _a, kw in shapes(_card, "create_arc")
          if kw.get("style") == "arc"))
check("and it can be turned off entirely",
      _framed(_panel_canvas(OV.STATUS, overlay_frame="none")) == 0,
      _framed(_panel_canvas(OV.STATUS, overlay_frame="none")))
check("or turned on for the scope too, for a dark cockpit",
      _framed(_panel_canvas(OV.RADAR, overlay_frame="all")) >= 4,
      _framed(_panel_canvas(OV.RADAR, overlay_frame="all")))
# The sweep and the clock were mine, not asked for, and the commander's
# testers asked for the sweep to go. A HUD is for reading, and
# something moving on it that carries no information is something your eye
# goes to for nothing.
check("nothing on the scope is animated for the sake of it",
      not any(kw.get("style") == "pieslice"
              for _a, kw in shapes(scope, "create_arc")))
check("and there is no clock ticking in the corner",
      not any(t.count(":") == 2 and t.replace(":", "").isdigit()
              for t in texts(scope)), texts(scope))
check("the helper that drew it is gone too, not just unused",
      not hasattr(OV, "sweep_wedge"))

print("== the scanner ring is round the SRV, not round the site ==")
centre_x, centre_y = None, None
for args, kw in shapes(scope, "create_oval"):
    if kw.get("outline") == OV.SCAN_RING:
        centre_x = (args[0] + args[2]) / 2.0
        centre_y = (args[1] + args[3]) / 2.0
check("it was drawn", centre_x is not None)
# The commander sits below and slightly left of the signal centre in this
# scenario, so a ring drawn round the site would sit at the middle of the
# window and this is what catches it.
check("and it is centred on him, not on the middle of the scope",
      centre_x is not None and abs(centre_y - 214.0) > 40.0, centre_y)

print("== the commander-centred mode ==")
driving_scope = drawn(RADAR_ROWS, heading=12.0, settings={"overlay_centre": "srv"})
check("it says so", said(driving_scope, "CENTRE  SRV"), texts(driving_scope)[:6])
check("no signal marker is drawn, because the scope is not on one",
      not any(kw.get("fill") == OV.RED for _a, kw in shapes(driving_scope, "create_oval")))
check("the signal marker IS drawn in the site-centred mode",
      any(kw.get("fill") == OV.RED for _a, kw in shapes(scope, "create_oval")))

print("== the degenerate cases the window has to survive ==")
blank = drawn([], note="nothing recorded on this body yet")
check("no deposits does not crash the scope", len(blank.calls) > 5)
check("and it says what is missing",
      said(blank, "nothing recorded"), texts(blank))
check("with no invented site to centre on", said(blank, "CENTRE  SRV"),
      texts(blank)[:6])
one = drawn([RADAR_ROWS[0]])
check("one deposit draws", said(one, "Haematite (6R)"), texts(one))
check("and is its own centre", said(one, "CENTRE  LOCATION 2"), texts(one)[:6])
miles_overlay = OV.Overlay(app=_App(), tk_module=None,
                           settings={"overlay_mode": "radar",
                                     "overlay_click_through": True})
miles_overlay.window = _Window(420, 420)
miles_overlay.canvas = _Canvas()
miles_overlay.draw(RADAR_ROWS + [row(3_000_000, 47, id="f", commodity="Gold",
                                     rigs="5")], 0.0)
miles = miles_overlay.canvas
check("a find on the far side of the body does not blank the scope",
      said(miles, "Haematite (6R)"), texts(miles))
# It used to stop at the 50 km cap, which is what the scope in his 1.10028
# screenshot showed: MAP RADIUS 50 km, the patch a dot, 9,698 km arrows at
# the rim. A find that far off is on another signal; it is left off the
# boxes and counted, and the scope stays sized to the patch.
check("and it does not drag the scope out at all",
      not said(miles, "MAP RADIUS  50 km") and said(miles, "MAP RADIUS"),
      texts(miles)[:4])
check("the far find is not drawn, not even as an arrow",
      not said(miles, "Gold"), texts(miles))
check("it is counted as elsewhere on the body",
      miles_overlay._elsewhere == 1, miles_overlay._elsewhere)

print("== the scope is the signal you are AT, and nothing else ==")
# Reported as "only focus on the signal source we are at", with a
# screenshot: MAP RADIUS 50 km. The box still named the signal before, 36 km
# back, and the scope stretched to hold it and the SRV both.
def radius_of(canvas):
    for text in texts(canvas):
        if text.startswith("MAP RADIUS"):
            value = text.split("MAP RADIUS", 1)[1].strip().replace(",", "")
            if value.endswith("km"):
                return float(value[:-2].strip()) * 1000.0
            return float(value.rstrip("m").strip())
    return None

behind = [row(36055, 56.3, id="o%d" % n, commodity="Gold", rigs="3",
              location="1") for n in range(3)]
around_me = [row(420, 200, id="n1", commodity="Haematite", rigs="6",
                 location="5"),
             row(610, 240, id="n2", commodity="Samarium", rigs="4",
                 location="5")]
stale = drawn(behind + around_me, location="1", site=(30000.0, 20000.0))
check("a signal 36 km back does not size the scope",
      radius_of(stale) is not None and radius_of(stale) < 2000,
      radius_of(stale))
check("the finds round the SRV are what it shows",
      said(stale, "Haematite") and said(stale, "Samarium"), texts(stale))
check("and it says, up top, where the signal in the box is",
      said(stale, "CENTRE  SRV   SIGNAL 1  36 km ENE"), texts(stale))
check("the old signal's finds are not drawn", not said(stale, "Gold"),
      texts(stale))

stale_border = drawn(behind + around_me, location="1", site=(30000.0, 20000.0),
                     survey={"centre": (30000.0, 20000.0), "border_m": 4500.0,
                             "points": [], "scan_m": 500.0, "rings": []},
                     rigs={"rigs": [{"n": 1, "east": 29000.0, "north": 19500.0,
                                     "range_m": 34800.0, "commodity": "Gold"}],
                           "limit_m": 3500.0})
check("nor does the border and a rig left at it",
      radius_of(stale_border) is not None and radius_of(stale_border) < 2000,
      radius_of(stale_border))
nothing_here = drawn(behind, location="1", site=(30000.0, 20000.0))
check("with nothing near the SRV either, it is the scanner's reach, not 50 km",
      radius_of(nothing_here) is not None
      and radius_of(nothing_here) <= PV.SIGNAL_VIEW_EMPTY_M * 1.3,
      radius_of(nothing_here))

at_it = [row(1400 + 90 * n, 45 + 5 * n, id="a%d" % n, commodity="Haematite",
             rigs="2", location="5") for n in range(4)]
working = drawn(at_it, location="5", site=(900.0, 900.0))
check("at the signal, the scope holds the patch and you",
      radius_of(working) is not None and radius_of(working) < 3000,
      radius_of(working))
outside = drawn([row(6300 + 80 * n, 90, id="b%d" % n, commodity="Bromellite",
                     rigs="2", location="7") for n in range(3)],
                location="7", site=(6400.0, 0.0))
# Setting the border is driving out to the location's edge, and that can be
# 6 km. The scope used to stop at 5 km, freeze at 1.5 km round the centre
# and pin the Rhino to the rim at 5.91 km, pointing nowhere.
check("6 km out from it - out setting the border - the scope takes you in",
      radius_of(outside) is not None and 6400 < radius_of(outside) <= 10000,
      radius_of(outside))
check("so you are on it, not a chevron on the rim with the range",
      not said(outside, "6.40km"), texts(outside))


def _rim_chevron(heading):
    """Draw the commander off the edge of a scope and return the chevron."""
    scope = OV.Overlay(app=_App(), tk_module=None,
                       settings={"overlay_mode": "radar"})
    scope.canvas = _Canvas()
    view = PV.Viewport(420, 420, 1000.0, margin=40)
    plan = PV.layout([], view, heading=heading, origin=(9000.0, 0.0),
                     clip="circle")
    scope._commander(view, plan)
    return [a for name, a, kw in scope.canvas.calls if name == "create_polygon"]


_east, _south = _rim_chevron(90.0), _rim_chevron(180.0)
check("off the edge, the chevron turns with the Rhino, not with the bearing "
      "back to it", _east and _south and _east != _south, (_east, _south))
wide = drawn(at_it, location="5", site=(900.0, 900.0),
             settings={"overlay_max_radius_m": 50000},
             survey={"centre": (900.0, 900.0), "border_m": 4500.0,
                     "points": [], "scan_m": 500.0, "rings": []})
check("a survey border is in view, all of it",
      radius_of(wide) is not None and 4500 < radius_of(wide) < 8000,
      radius_of(wide))
check("and no hand-set cap lets the scope past the signal's own limit",
      radius_of(drawn(at_it + [row(14000, 45, id="z", commodity="Gold",
                                   location="5")],
                      location="5", site=(900.0, 900.0),
                      settings={"overlay_max_radius_m": 50000}))
      <= PV.SIGNAL_VIEW_CAP_M)

far = PV.signal_focus(behind + around_me, "1", anchor=(30000.0, 20000.0),
                      near_m=PV.SIGNAL_REACH_M)
check("planview says the signal is far, and where",
      far["far"] and far["far"]["signal"] == "1"
      and abs(far["far"]["range_m"] - 36056) < 5
      and PV.compass_point(far["far"]["bearing"]) == "ENE", far["far"])
check("and focuses on the SRV instead",
      far["how"] == "commander" and len(far["here"]) == 2, far["how"])
near = PV.signal_focus(at_it, "5", anchor=(900.0, 900.0),
                       near_m=PV.SIGNAL_REACH_M)
check("a signal you are at is not far", near["far"] is None
      and near["how"] == "logged", near["how"])

print("== the deposit picked in the app is the one the overlay guides to ==")
guided = drawn(RADAR_ROWS, heading=0.0, target="t")
check("the scope says GO to it, not NEXT to the nearest",
      any(t.startswith("GO ") and "Thortveitite" in t for t in texts(guided))
      and not any(t.startswith("NEXT") for t in texts(guided)), texts(guided))
unguided = drawn(RADAR_ROWS, heading=0.0)
check("with nothing picked it is NEXT, nearest first",
      any(t.startswith("NEXT") and "Haematite" in t for t in texts(unguided)),
      [t for t in texts(unguided) if t.startswith("NEXT")])
_ov = OV.Overlay(app=_App(), tk_module=None, settings={"overlay_mode": "radar"})
_ov._target_id = "t"
_first = _ov.ranked(RADAR_ROWS, 0.0)[0]
check("TARGETS lists it first, marked",
      _first["commodity"] == "Thortveitite" and _first["target"], _first)
check("but the deposit card stays on the nearest still worth working",
      _ov.ranked(RADAR_ROWS, 0.0, limit=1, guided=False)[0]["commodity"] == "Haematite")
_card = OV.Overlay(app=_App(), tk_module=None, settings={"overlay_mode": "radar"})
_card.window, _card.canvas, _card._target_id = _Window(420, 420), _Canvas(), "t"
_card.draw_deposit(RADAR_ROWS, 0.0, 420, 420)
_ct = texts(_card.canvas)
check("the MINERAL DEPOSIT card shows that one, not the one being guided to",
      "MINERAL" in _ct and _ct[_ct.index("MINERAL") + 1] == "Haematite", _ct[:6])

tiny = drawn(RADAR_ROWS, size=(200, 200))
check("a small scope still draws", len(tiny.calls) > 20)
check("junk rows do not crash it",
      len(drawn([{"range_m": None, "bearing": None,
                  "deposit": {"id": "x"}}]).calls) > 5)

print("== it is still the tape when you ask for the tape ==")
tape = drawn(RADAR_ROWS, heading=12.0, settings={"overlay_mode": "strip"})
check("the tape draws", len(tape.calls) > 10)
check("and is not the radar", not said(tape, "MAP RADIUS"), texts(tape))
check("the strip is what you get by default",
      OV.Overlay(app=None, tk_module=None, settings={}).mode() == OV.STRIP)
check("and the scope is still there when you choose it",
      OV.Overlay(app=None, tk_module=None,
                 settings={"overlay_mode": "radar"}).mode() == OV.RADAR)
check("an unrecognised mode is the radar rather than nothing",
      OV.Overlay(app=None, tk_module=None,
                 settings={"overlay_mode": "banana"}).mode() == OV.RADAR)
check("the tape is still reachable",
      OV.Overlay(app=None, tk_module=None,
                 settings={"overlay_mode": "strip"}).mode() == OV.STRIP)

print("== the radar sizes and sits where a radar should ==")
dial = OV.Overlay(app=None, tk_module=None, settings={"overlay_mode": "radar"})
w, h, x, y = dial.placement(_Screen(1920, 1080))
check("it is square", w == h, (w, h))
check("it fits on the screen", w <= 1080 and h <= 1080, (w, h))
check("and it is in the top-left corner, out of the cockpit",
      x < 1920 * 0.1 and y < 1080 * 0.1, (x, y))
big = OV.Overlay(app=None, tk_module=None,
                 settings={"overlay_mode": "radar", "overlay_radar_size": 3000})
w, h, _x, _y = big.placement(_Screen(1920, 1080))
check("a silly radar size is clamped to the screen", w <= 1080 and h <= 1080, (w, h))
small = OV.Overlay(app=None, tk_module=None,
                   settings={"overlay_mode": "radar", "overlay_radar_size": 10})
w, h, _x, _y = small.placement(_Screen(1920, 1080))
check("and a uselessly small one is pushed back up", w >= 200, w)
check("the strip's own size is left alone by the radar",
      OV.Overlay(app=None, tk_module=None,
                 settings={"overlay_mode": "strip", "overlay_width": 1400,
                           "overlay_height": 160}).placement(_Screen(1920, 1080))[:2]
      == (1400, 160))
check("an unmapped window draws at the size it is about to be, not at 1px",
      OV.Overlay(app=None, tk_module=None,
                 settings={"overlay_mode": "radar"}).panel_size.__name__
      == "panel_size")
unmapped = OV.Overlay(app=None, tk_module=None, settings={"overlay_mode": "radar"})
unmapped.window = _Window(1, 1)
check("and that size is square, not the tape's", unmapped.panel_size()[0]
      == unmapped.panel_size()[1], unmapped.panel_size())

# ---------------------------------------------------------------------------
# Panels: drag them where you want, then lock them
# ---------------------------------------------------------------------------
# The overlay is a set of boxes now, one window each, because nobody has the
# same screen and nobody's cockpit is covered in the same places. Every one
# of these checks exists because a position stored in pixels is a position
# stored for exactly one monitor.

print("== a position is a share of the screen, not a pixel ==")
spec = OV.panel_fractions(480, 300, 3072, 216, 3840, 2160)
check("dragged 80% across a 4K screen, that is what gets written down",
      abs(spec["x"] - 0.8) < 0.001 and abs(spec["y"] - 0.1) < 0.001, spec)
w, h, x, y = OV.panel_pixels(spec, 1920, 1080, OV.TARGETS)
check("and on a 1080p screen it lands 80% across, not off the side",
      abs(x - 1536) <= 2 and x + w <= 1920, (x, w))
check("it scaled down with the screen instead of staying 480 wide",
      abs(w - 240) <= 2, w)
back = OV.panel_fractions(w, h, x, y, 1920, 1080)
check("and the fractions survive the round trip",
      abs(back["x"] - spec["x"]) < 0.002 and abs(back["w"] - spec["w"]) < 0.002,
      (spec, back))

print("== a box cannot be lost off the edge of the screen ==")
w, h, x, y = OV.panel_pixels({"x": 2.4, "y": 1.9, "w": 0.2, "h": 0.2},
                             1920, 1080, OV.TARGETS)
check("a box saved on a monitor that is gone comes back on this one",
      x < 1920 and y < 1080, (x, y))
check("with enough of it left to grab", x <= 1920 - 120, x)
w, h, _x, _y = OV.panel_pixels({"x": 0.1, "y": 0.1, "w": 0.001, "h": 0.001},
                               1920, 1080, OV.TARGETS)
check("and it cannot be shrunk into a sliver you can never grab again",
      (w, h) >= OV.MIN_PANEL[OV.TARGETS], (w, h))
w, h, _x, _y = OV.panel_pixels({"x": 0, "y": 0, "w": 9.0, "h": 9.0},
                               1920, 1080, OV.STRIP)
check("nor blown up past the screen", w <= 1920 and h <= 1080, (w, h))
check("rubbish where a number should be does not take the overlay down",
      OV.panel_pixels({"x": "nope", "y": None, "w": [], "h": "x"},
                      1920, 1080, OV.STATUS)[0] > 0)

print("== which boxes are on screen ==")
def _ov(**settings):
    return OV.Overlay(app=None, tk_module=None, settings=dict(settings))

check("nothing switched on falls back to the old single-shape setting",
      _ov(overlay_mode="radar").active() == [OV.RADAR],
      _ov(overlay_mode="radar").active())
check("and a settings file that never heard of panels still opens the tape",
      _ov(overlay_mode="strip").active() == [OV.STRIP])
check("switching one on takes over from the mode",
      _ov(overlay_mode="radar", overlay_show_targets=True).active() == [OV.TARGETS])
check("and the answer people asked for three times - both at once - works",
      _ov(overlay_show_strip=True, overlay_show_radar=True).active()
      == [OV.STRIP, OV.RADAR],
      _ov(overlay_show_strip=True, overlay_show_radar=True).active())
check("every panel has a default place on screen",
      set(OV.DEFAULT_LAYOUT) == set(OV.PANEL_ORDER))
check("and none of them opens on top of another",
      len({(spec["x"], spec["y"]) for spec in OV.DEFAULT_LAYOUT.values()})
      == len(OV.PANEL_ORDER),
      len({(spec["x"], spec["y"]) for spec in OV.DEFAULT_LAYOUT.values()}))
check("every panel has a title and a description for the settings row",
      all(k in OV.PANEL_TITLE and k in OV.PANEL_WHAT for k in OV.PANEL_ORDER))

print("== the lock is one fact, not two ==")
locked = _ov(overlay_click_through=True)
check("locked by default - clicks reach the game", locked.locked)
locked.set_locked(False)
check("unlocking writes the one key the window plumbing reads",
      locked.settings["overlay_click_through"] is False)
check("and locking writes it back", locked.set_locked(True) is True
      and locked.settings["overlay_click_through"] is True)

print("== dragging a box, and resizing it by the corner ==")
class _MovableWindow(_Window):
    def __init__(self, w=300, h=200, x=100, y=100):
        _Window.__init__(self, w, h)
        self.x, self.y = x, y
        self.geoms = []
    def winfo_x(self): return self.x
    def winfo_y(self): return self.y
    def geometry(self, spec):
        self.geoms.append(spec)
        if "+" in spec:
            head, sx, sy = spec.split("+")
            self.x, self.y = int(sx), int(sy)
            if "x" in head:
                self.w, self.h = (int(v) for v in head.split("x"))

class _Event:
    def __init__(self, x, y, x_root, y_root):
        self.x, self.y, self.x_root, self.y_root = x, y, x_root, y_root

saved = []
class _Saver:
    def save_settings(self): saved.append(True)

def _panel(key=OV.TARGETS, locked=False, **settings):
    options = {"overlay_click_through": locked}
    options.update(settings)
    over = OV.Overlay(app=_Saver(), tk_module=None, settings=options)
    panel = OV.Panel(over, key)
    panel.window = _MovableWindow()
    panel.canvas = _Canvas()
    over.panels = {key: panel}
    return over, panel

over, panel = _panel()
panel._grab(_Event(40, 8, 500, 500))
panel._move(_Event(40, 8, 560, 530))
check("dragging the bar moves the box", (panel.window.x, panel.window.y)
      == (160, 130), (panel.window.x, panel.window.y))
panel._drop(None)
check("and letting go writes it down",
      OV.TARGETS in (over.settings.get("overlay_layout") or {}),
      over.settings.get("overlay_layout"))
check("as a fraction of the screen, not a pixel",
      0 < over.settings["overlay_layout"][OV.TARGETS]["x"] < 1,
      over.settings["overlay_layout"])
check("and the app is told to save, so it survives a restart", saved, saved)

over, panel = _panel()
panel._grab(_Event(295, 195, 500, 500))
panel._move(_Event(295, 195, 600, 560))
check("grabbing the bottom-right corner resizes instead of moving",
      (panel.window.w, panel.window.h) == (400, 260),
      (panel.window.w, panel.window.h))
check("and it did not wander while being resized",
      (panel.window.x, panel.window.y) == (100, 100))
panel._move(_Event(295, 195, 0, 0))
check("resizing cannot take it below the size it stops being readable at",
      (panel.window.w, panel.window.h) >= OV.MIN_PANEL[OV.TARGETS],
      (panel.window.w, panel.window.h))

over, panel = _panel(locked=True)
panel._grab(_Event(40, 8, 500, 500))
panel._move(_Event(40, 8, 900, 900))
check("a locked box cannot be dragged at all - that is the point of locking",
      (panel.window.x, panel.window.y) == (100, 100),
      (panel.window.x, panel.window.y))

print("== the handles only exist while it is unlocked ==")
over, panel = _panel(key=OV.STATUS, locked=False)
over.draw([], 0.0)
labels = [str(kw.get("text", "")) for name, _a, kw in panel.canvas.calls
          if name == "create_text"]
check("an unlocked box says which box it is", "STATUS" in labels, labels)
check("and says what to do with it", any("drag" in t for t in labels), labels)
over, panel = _panel(key=OV.STATUS, locked=True)
over.draw([], 0.0)
labels = [str(kw.get("text", "")) for name, _a, kw in panel.canvas.calls
          if name == "create_text"]
check("a locked box is a HUD again, with no handles on it",
      "STATUS" not in labels and not any("drag" in t for t in labels), labels)

print("== reset puts everything back ==")
over = _ov(overlay_layout={OV.STRIP: {"x": 9, "y": 9, "w": 9, "h": 9}},
           overlay_x=4000, overlay_y=3000)
over.app = _Saver()
over.reset_layout()
check("every box goes back to its default place",
      over.settings["overlay_layout"] == OV.DEFAULT_LAYOUT,
      over.settings["overlay_layout"])
check("and the old single-window pixels are dropped with it",
      "overlay_x" not in over.settings and "overlay_y" not in over.settings,
      sorted(over.settings))

print("== the new boxes draw something worth reading ==")
def _drew(key, rows, **settings):
    over, panel = _panel(key=key, locked=True, **settings)
    over.draw(rows, 0.0, body="Ega 3 a", location="2")
    return panel.canvas

tcanvas = _drew(OV.TARGETS, RADAR_ROWS)
tlabels = [str(kw.get("text", "")) for name, _a, kw in tcanvas.calls
           if name == "create_text"]
check("the targets box names the body", any("Ega 3 a" in t for t in tlabels),
      tlabels)
check("and lists the finds", any("Haematite" in t for t in tlabels), tlabels)
check("nearest first", next(i for i, t in enumerate(tlabels) if "Haematite" in t)
      < next(i for i, t in enumerate(tlabels) if "Thortveitite" in t), tlabels)
check("with the turn worked out for each one",
      any(t.startswith(("<", ">", "^")) for t in tlabels), tlabels)
check("a worked-out deposit is marked as such rather than hidden",
      any("mined" in t for t in tlabels), tlabels)
empty = [str(kw.get("text", "")) for name, _a, kw in _drew(OV.TARGETS, []).calls
         if name == "create_text"]
check("an empty body says so instead of drawing nothing",
      any("nothing logged" in t for t in empty), empty)

scanvas = _drew(OV.STATUS, RADAR_ROWS)
slabels = [str(kw.get("text", "")) for name, _a, kw in scanvas.calls
           if name == "create_text"]
check("the status box names the body", any("Ega 3 a" in t for t in slabels),
      slabels)
check("counts what is here", any("DEP" in t and "R" in t for t in slabels),
      slabels)
check("says what is next", any(t.startswith("NEXT") for t in slabels), slabels)
check("and tells you which keys log a find",
      any("SITE" in t and "DEP" in t for t in slabels), slabels)
bound = [str(kw.get("text", "")) for name, _a, kw in
         _drew(OV.STATUS, RADAR_ROWS, hotkey_location="CTRL+1",
               hotkey_deposit="CTRL+2").calls if name == "create_text"]
check("in the keys this commander actually bound, not the defaults",
      any("ctrl+1 site" in t.lower() and "ctrl+2 dep" in t.lower()
          for t in bound), bound)

print("== every box is locked and unlocked together ==")
class _StyleWindow(_FakeWindow):
    def __init__(self, ident):
        _FakeWindow.__init__(self)
        self.ident = ident
    def winfo_id(self): return self.ident

user32 = _FakeUser32()
fake = types.ModuleType("ctypes")
fake.windll = types.SimpleNamespace(user32=user32)
real = sys.modules.get("ctypes")
sys.modules["ctypes"] = fake
try:
    over = _ov(overlay_click_through=True)
    for index, key in enumerate(OV.PANEL_ORDER):
        panel = OV.Panel(over, key)
        panel.window = _StyleWindow(100 + index)
        over.panels[key] = panel
    over.apply_click_through()
    check("every box had the style written, not just the first",
          len(user32.writes) == len(OV.PANEL_ORDER), user32.writes)
    check("all of them click through while locked",
          all(value & 0x20 for value in user32.writes),
          [hex(v) for v in user32.writes])
    user32.writes = []
    over.set_locked(False)
    check("and none of them do once unlocked",
          len(user32.writes) == len(OV.PANEL_ORDER)
          and all(not (v & 0x20) for v in user32.writes),
          [hex(v) for v in user32.writes])
    check("the layered bit is still never touched, on any of them",
          all(not (v & _FakeUser32.WS_EX_LAYERED) for v in user32.writes))
finally:
    if real is not None: sys.modules["ctypes"] = real
    else: del sys.modules["ctypes"]

print("== ticking a box in settings takes effect on Save ==")
class _FakeTk:
    class Toplevel:
        def __init__(self, parent=None): pass
        def title(self, *a): pass
        def overrideredirect(self, *a): pass
        def attributes(self, *a): pass
        def geometry(self, *a): pass
        def update_idletasks(self): pass
        def deiconify(self): pass
        def lift(self): pass
        def destroy(self): pass
        def winfo_width(self): return 300
        def winfo_height(self): return 200
        def winfo_x(self): return 10
        def winfo_y(self): return 10
        def winfo_screenwidth(self): return 1920
        def winfo_screenheight(self): return 1080
    class Canvas:
        def __init__(self, *a, **kw): pass
        def pack(self, *a, **kw): pass
        def bind(self, *a, **kw): pass
        def delete(self, *a): pass
        def __getattr__(self, name):
            return lambda *a, **kw: None

live = OV.Overlay(app=_Saver(), tk_module=_FakeTk,
                  settings={"overlay_show_strip": True})
live.show()
check("the box that was switched on is the one that opened",
      list(live.panels) == [OV.STRIP], list(live.panels))
live.refresh_settings({"overlay_show_strip": True, "overlay_show_targets": True})
check("ticking another one opens it there and then, not at the next restart",
      list(live.panels) == [OV.STRIP, OV.TARGETS], list(live.panels))
live.refresh_settings({"overlay_show_targets": True})
check("and unticking one closes it", list(live.panels) == [OV.TARGETS],
      list(live.panels))
check("the window everything else reaches for follows the boxes",
      live.window is live.panels[OV.TARGETS].window)
live.hide()
check("switching the overlay off closes every box", not live.panels)
check("and it reports itself as gone", not live.showing)

print("== the app exposes all of it ==")
check("every box has its own switch in settings",
      all(('"overlay_show_%s"' % key) in src for key in OV.PANEL_ORDER),
      [k for k in OV.PANEL_ORDER if ('"overlay_show_%s"' % k) not in src])
check("the lock is a button on the window, not a settings row you hunt for",
      "toggle_overlay_lock" in src and "btn_lock" in src)
check("and it can be bound to a key like everything else",
      '"hotkey_lock"' in src and '"lock"' in src)
check("a box dragged somewhere unreachable is one button to undo",
      "reset_overlay_layout" in src and "Reset box positions" in src)
check("the layout is handed back to the app to save, not left in memory",
      "save_settings" in io.open(os.path.join(os.path.dirname(os.path.dirname(
          os.path.abspath(__file__))), "overlay.py"), encoding="utf-8").read())

# ---------------------------------------------------------------------------
# What it is worth, and the order to drive it in
# ---------------------------------------------------------------------------
# A patch is not the number of dots on it.
# Six rigs of Aluminium and six rigs of Void Opals draw the same picture and
# are not the same trip, and nothing in the game tells you which is which on
# the ground.

print("== a patch is worth money, not dots ==")
PRICES = {"Ruby": 1_000_000, "Olivine": 500_000, "Magnesite": 10_000}
def _dep(name, rigs, east, north, amount=""):
    import math as _m
    return {"commodity": name, "range_m": _m.hypot(east, north),
            "bearing": (_m.degrees(_m.atan2(east, north)) + 360) % 360,
            "east_m": east, "north_m": north,
            "x": 200 + east / 10.0, "y": 200 - north / 10.0, "radius": 6,
            "deposit": {"commodity": name, "rigs": str(rigs), "amount": amount}}

RICH = [_dep("Ruby", 4, 100, 0), _dep("Olivine", 2, 0, 300),
        _dep("Magnesite", 6, -200, 0)]
worth = PV.value_of(RICH, PRICES)
check("rigs times price, added up",
      worth["credits"] == 4_000_000 + 1_000_000 + 60_000, worth)
check("and everything on the picture priced", worth["unpriced"] == 0, worth)
check("one big deposit of something cheap loses to a small one of something "
      "dear", PV.deposit_value(RICH[0], PRICES)
      > PV.deposit_value(RICH[2], PRICES),
      (PV.deposit_value(RICH[0], PRICES), PV.deposit_value(RICH[2], PRICES)))

unknown = RICH + [_dep("Unobtainium", 6, 50, 50)]
worth = PV.value_of(unknown, PRICES)
check("a commodity nobody has priced adds nothing to the total",
      worth["credits"] == 5_060_000, worth)
check("but it is counted, so the total can say it is incomplete",
      worth["unpriced"] == 1, worth)
check("a worked-out deposit is worth nothing - you already took it",
      PV.deposit_value(_dep("Ruby", 6, 10, 10, amount="Depleted"), PRICES) == 0)
check("and is left out of the total rather than counted as unpriced",
      PV.value_of([_dep("Ruby", 6, 10, 10, amount="Depleted")],
                  PRICES)["unpriced"] == 0)
check("no rig count means no promise about what is in it",
      PV.deposit_value(_dep("Ruby", 0, 10, 10), PRICES) == 0)
# Both directions. The accent can be on the recorded find or on the price
# table, and a fold applied to only one side passes the first and fails the
# second - which is how half the finds once went in under a second name.
check("an unaccented find finds the accented price",
      PV.deposit_value(_dep("bastnasite", 2, 10, 10),
                       {"Bastn\u00e4site": 500_000}) == 1_000_000,
      PV.deposit_value(_dep("bastnasite", 2, 10, 10), {"Bastn\u00e4site": 500_000}))
check("and an accented find finds the unaccented price",
      PV.deposit_value(_dep("Bastn\u00e4site", 2, 10, 10),
                       {"BASTNASITE": 500_000}) == 1_000_000,
      PV.deposit_value(_dep("Bastn\u00e4site", 2, 10, 10), {"BASTNASITE": 500_000}))
check("no prices at all is nothing, not a crash",
      PV.value_of(RICH, {})["credits"] == 0)

print("== the richest knot is not always the biggest ==")
# A tight pair of Ruby against a wide spread of Magnesite: more rigs on the
# Magnesite, far more money on the Ruby.
MIXED = [_dep("Magnesite", 6, 0, 0), _dep("Magnesite", 6, 100, 100),
         _dep("Ruby", 2, 3000, 3000), _dep("Ruby", 2, 3100, 3100)]
big = PV.best_patch(MIXED)
rich = PV.value_patch(MIXED, PRICES)
check("both patches are found", big is not None and rich is not None,
      (big, rich))
check("the biggest is the one with the rigs on it", big["rigs"] == 12, big["rigs"])
check("the richest is the one with the money on it",
      rich["credits"] == 4_000_000, rich["credits"])
check("and they are not the same place - which is the whole point",
      (big["x"], big["y"]) != (rich["x"], rich["y"]),
      ((big["x"], big["y"]), (rich["x"], rich["y"])))
check("on a one-commodity body they agree rather than arguing",
      PV.value_patch([_dep("Ruby", 4, 0, 0), _dep("Ruby", 4, 100, 100)],
                     PRICES)["count"] == 2)
check("nothing to cluster is None, not an empty patch",
      PV.value_patch([_dep("Ruby", 4, 0, 0)], PRICES) is None)

print("== the order to drive them in ==")
route = PV.drive_route(RICH, PRICES)
check("every deposit is a stop", len(route["stops"]) == 3, route["stops"])
check("numbered from one, in order",
      [s["stop"] for s in route["stops"]] == [1, 2, 3])
check("nearest first, from where you are standing",
      route["stops"][0]["item"]["commodity"] == "Ruby",
      [s["item"]["commodity"] for s in route["stops"]])
# The difference between a route and a sorted list, in one scenario: the
# Olivine is further from the commander than the Magnesite, but it is right
# beside the Ruby, so a route picks it up on the way and a list sorted by
# range drives past it and comes back.
CHAIN = [_dep("Ruby", 1, 100, 0), _dep("Olivine", 1, 190, 0),
         _dep("Magnesite", 1, 0, 150)]
order = [s["item"]["commodity"] for s in PV.drive_route(CHAIN, PRICES)["stops"]]
check("then nearest to THAT, not nearest to you - which is the difference "
      "between a route and a sorted list",
      order == ["Ruby", "Olivine", "Magnesite"], order)
check("and that really is a different answer from sorting by range",
      order != [d["commodity"] for d in
                sorted(CHAIN, key=lambda d: d["range_m"])],
      (order, [d["commodity"] for d in sorted(CHAIN, key=lambda d: d["range_m"])]))
check("the route it picked is the shorter one",
      PV.drive_route(CHAIN, PRICES)["total_m"] < 100 + 150 + 240,
      PV.drive_route(CHAIN, PRICES)["total_m"])
check("the total is the legs added up, not the crow-flies distance",
      abs(route["total_m"] - sum(s["leg_m"] for s in route["stops"])) < 1e-6)
check("and it is longer than the furthest single deposit",
      route["total_m"] > max(d["range_m"] for d in RICH), route["total_m"])
check("the route carries what it is worth to drive it",
      route["credits"] == 5_060_000, route["credits"])
spent = RICH + [_dep("Ruby", 6, 5, 5, amount="Depleted")]
check("a worked-out deposit is not on the route - you have been",
      len(PV.drive_route(spent, PRICES)["stops"]) == 3,
      [s["item"]["commodity"] for s in PV.drive_route(spent, PRICES)["stops"]])
check("but it is still on the map, because it is still a fact about the body",
      len(spent) == 4)
check("nothing logged is an empty route, not a crash",
      PV.drive_route([], PRICES)["total_m"] == 0.0)

print("== and all of it reaches the screen ==")
class _Priced(_App):
    # The scope scenario is the Ega session, whose commodities are not the
    # three in PRICES. Pricing both is the point: a picture with nothing
    # priced on it must claim nothing, and this suite checks both halves.
    def market_prices(self):
        return dict(PRICES, Haematite=80_000, Samarium=300_000,
                    Thortveitite=600_000, Copper=8_000)

def _shown(key, rows, size=(420, 420), **settings):
    options = {"overlay_click_through": True}
    options.update(settings)
    over = OV.Overlay(app=_Priced(), tk_module=None, settings=options)
    panel = OV.Panel(over, key)
    panel.window = _Window(*size)
    panel.canvas = _Canvas()
    over.panels = {key: panel}
    over.draw(rows, 0.0, body="Ega 3 a", location="2")
    return panel.canvas

scope_v = _shown(OV.RADAR, RADAR_ROWS)
check("the scope says what the patch is worth",
      any("Cr" in t for t in texts(scope_v)), texts(scope_v))
check("and numbers the drive order on the deposits themselves",
      any(t == "1" for t in texts(scope_v)), texts(scope_v))
status_v = _shown(OV.STATUS, RADAR_ROWS, size=(300, 140))
check("the status box carries the estimate",
      any("EST. VALUE" in t.upper() for t in texts(status_v)), texts(status_v))
check("and how far driving the lot is",
      any("ROUTE" in t.upper() for t in texts(status_v)), texts(status_v))
check("the estimate is labelled as one - the price is the part nobody can "
      "promise", any("est" in t.lower() or "~" in t
                     for t in texts(status_v) + texts(scope_v)),
      texts(status_v))
targets_v = _shown(OV.TARGETS, RADAR_ROWS, size=(240, 260))
def _barsof(canvas):
    """Only the filled, outline-less rectangles - the bars themselves.

    Counting every rectangle the panel happens to draw would pass on the
    panel's own furniture, which is the shape of test that certifies a
    broken feature as working.
    """
    return [a for a, kw in shapes(canvas, "create_rectangle")
            if kw.get("outline") == "" and kw.get("fill")]
_bars = _barsof(targets_v)
check("the targets box draws the shape of the money - one bar a commodity",
      len(_bars) >= 3, len(_bars))
_heights = {round(a[3] - a[1]) for a in _bars}
check("and the bars differ in height, or the strip says nothing at all",
      len(_heights) > 1, sorted(_heights))
check("a box with no room drops the bars rather than sitting them on the list",
      not _barsof(_shown(OV.TARGETS, RADAR_ROWS, size=(240, 120))),
      len(_barsof(_shown(OV.TARGETS, RADAR_ROWS, size=(240, 120)))))

print("== credits read at a glance, not counted ==")
check("millions", OV.money(4_183_000) == "4.18M", OV.money(4_183_000))
check("billions", OV.money(2_500_000_000) == "2.50B", OV.money(2_500_000_000))
check("thousands", OV.money(45_600) == "46k", OV.money(45_600))
check("small change stays exact", OV.money(840) == "840")
check("nonsense is zero, not a crash", OV.money(None) == "0")

print("== the theme actually changes the colours ==")
# "Pick a colour" used to tint exactly one row of the compass tape. Every
# other colour in the overlay was a hex constant baked in at import, so
# choosing one visibly did nothing - which is what "themes don't work"
# meant.
_was = OV.ORANGE
OV.apply_theme("signal")
check("a theme repoints the instrument colour", OV.ORANGE != _was, OV.ORANGE)
check("and the background with it", OV.VOID == OV.THEMES["signal"]["VOID"],
      OV.VOID)
check("and the rule the panels are drawn with",
      OV.RULE == OV.THEMES["signal"]["RULE"], OV.RULE)
OV.apply_theme("cockpit")
check("cockpit puts every one of them back",
      (OV.ORANGE, OV.VOID, OV.RULE)
      == (OV.BASE_THEME["ORANGE"], OV.BASE_THEME["VOID"], OV.BASE_THEME["RULE"]),
      (OV.ORANGE, OV.VOID))
check("every theme is a whole palette, so nothing is left in the last one's colours",
      all(set(OV.BASE_THEME) <= set(t) for t in OV.THEMES.values())
      and OV.apply_theme("elite")["VOID"] == OV.PALETTES["elite"]["VOID"])
OV.apply_theme("ice", accent="#ff00ff")
check("a hand-picked colour overrides the theme's instrument colour",
      OV.ORANGE == "#ff00ff", OV.ORANGE)
check("but leaves the rest of the theme alone",
      OV.TEXT == OV.THEMES["ice"]["TEXT"], OV.TEXT)
OV.apply_theme("cockpit", accent="not a colour")
check("and rubbish where a colour should be is ignored, not drawn",
      OV.ORANGE == OV.BASE_THEME["ORANGE"], OV.ORANGE)
check("an unknown theme falls back rather than raising",
      OV.apply_theme("nonsense")["ORANGE"] == OV.BASE_THEME["ORANGE"])
OV.apply_theme("cockpit")
check("every theme is offered a name for the settings row",
      all(k in OV.THEME_NAMES for k in OV.THEMES), sorted(OV.THEMES))
_themed = OV.Overlay(app=None, tk_module=None,
                     settings={"overlay_theme": "phosphor"})
_themed.theme()
check("and the window applies the commander's theme, not the default",
      OV.ORANGE == OV.THEMES["phosphor"]["ORANGE"], OV.ORANGE)
OV.apply_theme("cockpit")

# Not just that apply_theme works - that a REDRAW applies it. The theme can
# change while the overlay is up, and a HUD needing a restart to change
# colour is a HUD that looks like the setting did nothing.
OV.apply_theme("cockpit")
_live = _panel_canvas_rows(OV.STATUS, RADAR_ROWS, overlay_theme="phosphor")
_fills = {str(kw.get("fill", "")) for _n, _a, kw in _live.calls}
check("a redraw applies the theme, it is not a restart-only setting",
      OV.THEMES["phosphor"]["AMBER"] in _fills
      or OV.THEMES["phosphor"]["TEXT"] in _fills, sorted(_fills))
check("and nothing on screen is still wearing the old palette",
      OV.BASE_THEME["AMBER"] not in _fills, sorted(_fills))
OV.apply_theme("cockpit")

print("== the MINERAL DEPOSIT card ==")
_card_c = _panel_canvas(OV.DEPOSIT, overlay_click_through=True)
_ct = [str(kw.get("text", "")) for _n, _a, kw in _card_c.calls
       if _n == "create_text"]
check("the card is titled", any("MINERAL DEPOSIT" in t for t in _ct), _ct)
check("it names the deposit you are nearest",
      any("Haematite" in t for t in _ct), _ct)
check("with its range", any("m" in t or "km" in t for t in _ct), _ct)
check("the readout is labelled like a cockpit readout, not a sentence",
      any(t == "RIGS" for t in _ct) and any(t == "DENSITY" for t in _ct), _ct)
check("telemetry is under its own rule", any("TELEMETRY" in t for t in _ct), _ct)
check("and says what is on this signal",
      any("ON THIS SIGNAL" in t for t in _ct), _ct)
check("the signal radar is labelled", any("SIGNAL RADAR" in t for t in _ct), _ct)
check("it draws range rings", len(shapes(_card_c, "create_oval")) >= 3,
      len(shapes(_card_c, "create_oval")))
check("a contact for every find, plus the commander",
      len([a for a, kw in shapes(_card_c, "create_oval")
           if kw.get("outline") == ""]) >= 3,
      len([a for a, kw in shapes(_card_c, "create_oval")
           if kw.get("outline") == ""]))
check("and nothing on it is animated for the sake of it either",
      not any(kw.get("style") == "pieslice"
              for _a, kw in shapes(_card_c, "create_arc")))
check("the signal it belongs to is named at the foot",
      any("SIGNAL POINT" in t for t in _ct), _ct)
_empty = [str(kw.get("text", "")) for _n, _a, kw in
          _panel_canvas_rows(OV.DEPOSIT, []).calls if _n == "create_text"]
check("a body with nothing logged reads '-' rather than inventing a mineral",
      any(t == "-" for t in _empty), _empty)
check("and the card still draws rather than going blank",
      any("MINERAL DEPOSIT" in t for t in _empty), _empty)

print("== the scope is something you look through ==")
check("the scope panel is in the default layout like the rest",
      OV.DEPOSIT in OV.DEFAULT_LAYOUT and OV.DEPOSIT in OV.MIN_PANEL)
check("and it has a switch of its own in settings",
      '"overlay_show_deposit"' in src, "not exposed")
check("the theme picker is in settings too",
      '"overlay_theme"' in src and "Overlay theme" in src)
check("and so is the border choice",
      '"overlay_frame"' in src and "Draw a border" in src)

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
