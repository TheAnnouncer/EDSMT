"""1.10039: the overlay boxes change shape (#286).

Asked for on the Frontier forum: "would it be possible for the map overlay to
change shape using, for example, corner controls? So that it could be adjusted
more immersively to the shape of the cockpit, or the curvature of the helmet?"

Every box can be given a keystone - its four corners moved - and a bend, the
box's centre line following an arc. warp.py is the maths; the overlay draws
each box through it. What is checked here:

  * the transform: corners map to corners, flat is no change at all, a
    keystone keeps straight lines straight, a bend puts the centre line on a
    circle;
  * a box with no shape set draws EXACTLY what 1.10038 drew - the same canvas
    calls, in the same order, fingerprinted from the released code;
  * a shaped box draws through a recording canvas stand-in, every mark moved
    and every word placed at its moved anchor, never rotated;
  * unlock mode: the SHAPE button, the four corner handles that drag, the
    bend slider, Flat again, and the shape stored as fractions of the box so
    it follows the box when it is moved or resized.

    python tests/test_110039_warp.py
    python tests/test_110039_warp.py --record    (prints the fingerprints)
"""
import hashlib
import io
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import overlay as OV    # noqa: E402
# What a box draws, not which window is in front of the machine running this.
OV.foreground_is_game = lambda: None

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


# ---------------------------------------------------------------------------
# Stand-ins: a canvas that writes down every mark, and a window to hold it
# ---------------------------------------------------------------------------

class Recorder:
    """A canvas that records every mark instead of making one."""

    def __init__(self):
        self.calls = []
        self._made = 0

    def _make(self, kind, args, kw):
        self.calls.append((kind, args, kw))
        self._made += 1
        return self._made

    def delete(self, *args):
        self.calls.append(("delete", args, {}))

    def winfo_exists(self):
        return 1

    def create_line(self, *a, **k):
        return self._make("create_line", a, k)

    def create_polygon(self, *a, **k):
        return self._make("create_polygon", a, k)

    def create_oval(self, *a, **k):
        return self._make("create_oval", a, k)

    def create_rectangle(self, *a, **k):
        return self._make("create_rectangle", a, k)

    def create_arc(self, *a, **k):
        return self._make("create_arc", a, k)

    def create_text(self, *a, **k):
        return self._make("create_text", a, k)


class Win:
    """A box's window: where it is and how big, on a 1920x1080 screen."""

    def __init__(self, w, h, x=0, y=0):
        self.w, self.h, self.x, self.y = int(w), int(h), int(x), int(y)

    def winfo_width(self): return self.w
    def winfo_height(self): return self.h
    def winfo_x(self): return self.x
    def winfo_y(self): return self.y
    def winfo_screenwidth(self): return 1920
    def winfo_screenheight(self): return 1080
    def winfo_viewable(self): return 1
    def deiconify(self): pass
    def lift(self): pass
    def withdraw(self): pass

    def geometry(self, spec):
        match = re.match(r"^(?:(\d+)x(\d+))?\+(-?\d+)\+(-?\d+)$", spec)
        if match:
            if match.group(1):
                self.w, self.h = int(match.group(1)), int(match.group(2))
            self.x, self.y = int(match.group(3)), int(match.group(4))


class StubApp:
    def __init__(self):
        self.saved = 0

    def colour_for(self, name):
        return {"Haematite": "#c0392b", "Samarium": "#8e44ad",
                "Thortveitite": "#27ae60", "Copper": "#d35400"}.get(name, "#9c6a3c")

    def market_prices(self):
        return {"Haematite": 120000, "Samarium": 450000, "Thortveitite": 900000}

    def save_settings(self):
        self.saved += 1


def dep(**kw):
    row = {"id": kw.get("id", ""), "system": "Ega", "body": "Ega 3 a",
           "location": "2", "commodity": "", "rigs": "", "amount": ""}
    row.update(kw)
    return row


def row(range_m, bearing, **kw):
    return {"range_m": float(range_m), "bearing": float(bearing),
            "commodity": kw.get("commodity", ""), "deposit": dep(**kw)}


ROWS = [
    row(896, 350, id="h", commodity="Haematite", rigs="6"),
    row(940, 5, id="s", commodity="Samarium", rigs="4"),
    row(1010, 358, id="t", commodity="Thortveitite", rigs="1", shared=True),
    row(400, 120, id="c", commodity="Copper", rigs="2", amount="Depleted"),
]
RIGS = {"rigs": [{"n": 1, "label": "1", "bearing": 30.0, "range_m": 650.0,
                  "east": 325.0, "north": 563.0, "commodity": "Haematite"},
                 {"n": 2, "label": "2", "bearing": 200.0, "range_m": 1400.0,
                  "east": -479.0, "north": -1316.0, "commodity": "Samarium"}],
        "limit_m": 1200.0, "far": True, "n": 2, "label": "2",
        "offset": -172.0, "range_m": 1400.0, "count": 2}
SURVEY = {"centre": (60.0, 650.0), "border_m": 1500.0, "scan_m": 500.0,
          "points": [(0.0, 0.0), (200.0, 300.0)], "rings": [500.0, 1000.0],
          "gaps": [{"east": 800.0, "north": 900.0}], "percent": 42,
          "trail": [(0.0, 0.0), (100.0, 150.0), (200.0, 300.0)]}
GUIDE = {"step": 4, "total": 11, "title": "MARK THE DEPOSIT  Alt+3",
         "detail": "Drive onto the deposit and press Alt+3 while the scanner "
                   "names it.", "next": "PLACE RIGS"}
CARGO = {"ship_t": 120, "capacity": 256, "rhino_t": 12}
HAZARD = {"text": "HIGH GRAVITY 2.40 g", "gravity": 2.4}
ZONE = {"signal": "2", "summary": "Haematite 6R, Samarium 4R", "source": "shared",
        "metres": 1200.0, "reach_m": 5000.0}


def overlay_with_boxes(locked=True, settings=None, sizes=None):
    """An overlay with all six boxes open on stand-ins, at the default
    layout of a 1920x1080 screen. Returns (overlay, app)."""
    options = {"overlay_click_through": locked, "overlay_theme": "cockpit",
               "overlay_guide": True}
    options.update({"overlay_show_%s" % key: True for key in OV.PANEL_ORDER})
    options.update(settings or {})
    app = StubApp()
    over = OV.Overlay(app=app, tk_module=None, settings=options)
    for key in OV.PANEL_ORDER:
        panel = OV.Panel(over, key)
        w, h, x, y = OV.panel_pixels(OV.DEFAULT_LAYOUT[key], 1920, 1080, key)
        if sizes and key in sizes:
            w, h = sizes[key]
        panel.window = Win(w, h, x, y)
        panel.canvas = Recorder()
        over.panels[key] = panel
    over.map_prefs = {"lines": True, "trail": True}
    return over, app


def draw_scene(over, only=None):
    over.draw(ROWS, 12.0, "", body="Ega 3 a", location="2", survey=SURVEY,
              rigs=RIGS, guide=GUIDE, cargo=CARGO, hazard=HAZARD, zone=ZONE,
              only=only)


def scene(locked=True, settings=None):
    """Every box drawn once, the way the app draws them. {box: calls}"""
    over, _app = overlay_with_boxes(locked, settings)
    draw_scene(over)
    return {key: list(over.panels[key].canvas.calls) for key in OV.PANEL_ORDER}


_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _plain(value):
    """A call's arguments as plain JSON, rounded past any rounding noise.

    Colours are written as "#colour": the themes are reworked separately,
    and what is proved here is where and what is drawn, not in which shade."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float):
        value = round(value, 3)
        return 0.0 if value == 0 else value
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _plain(value[k]) for k in sorted(value)}
    if isinstance(value, str) and _HEX.match(value):
        return "#colour"
    return value


def fingerprint(calls):
    text = json.dumps([[name, _plain(args), _plain(kw)] for name, args, kw in calls],
                      sort_keys=True)
    return "%s/%d" % (hashlib.sha256(text.encode("utf-8")).hexdigest()[:20], len(calls))


def shape_calls(calls):
    """The unlock-mode furniture this release adds, by its tag."""
    return [c for c in calls if "shapectl" in (c[2].get("tags") or ())]


def without_shape_calls(calls):
    return [c for c in calls if "shapectl" not in (c[2].get("tags") or ())]


if "--record" in sys.argv[1:]:
    # Run against a tree to fingerprint what it draws with no shape set.
    out = {}
    for locked in (True, False):
        for key, calls in scene(locked).items():
            out["%s %s" % (key, "locked" if locked else "unlocked")] = \
                fingerprint(without_shape_calls(calls))
    print(json.dumps(out, indent=1, sort_keys=True))
    raise SystemExit(0)

import warp as WP    # noqa: E402


def near(a, b, tol=1e-6):
    return all(abs(p - q) <= tol for p, q in zip(a, b))


def circle(p, q, r):
    """The centre and radius of the circle through three points."""
    (ax, ay), (bx, by), (cx, cy) = p, q, r
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay)
          + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx)
          + (cx * cx + cy * cy) * (bx - ax)) / d
    return (ux, uy), math.hypot(ax - ux, ay - uy)


print("== the transform ==")
W, H = 400.0, 200.0
LEAN = WP.make([(0.1, 0.05), (0.9, 0.0), (1.0, 1.0), (0.0, 0.95)])
lean = WP.Warp(LEAN, W, H)
check("a box's four corners land on the shape's four corners",
      near(lean.point(0, 0), (40, 10)) and near(lean.point(W, 0), (360, 0))
      and near(lean.point(W, H), (400, 200)) and near(lean.point(0, H), (0, 190)),
      [lean.point(*p) for p in ((0, 0), (W, 0), (W, H), (0, H))])

flat = WP.Warp(None, W, H)
check("with no shape every point stays exactly where it is",
      all(flat.point(x, y) == (x, y) for x, y in
          ((0, 0), (W, H), (123.5, 67.25), (399, 1), (-5, 250))))
check("and nothing is scaled", abs(flat.scale(200, 100) - 1.0) < 1e-9,
      flat.scale(200, 100))

# A keystone narrowed at the top: the middle of the box goes where the
# diagonals of the trapezium cross, 3/8 of the way down - a perspective, not
# a squash, which would put it half way.
KEY = WP.make([(0.2, 0.0), (0.8, 0.0), (1.0, 1.0), (0.0, 1.0)])
key = WP.Warp(KEY, W, H)
check("a keystone puts the middle of the box where the diagonals cross",
      near(key.point(200, 100), (200, 75), 1e-6), key.point(200, 100))
_line = [key.point(x, 40 + x * 0.3) for x in range(0, 401, 50)]
_cross = [(b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
          for a, b, c in zip(_line, _line[1:], _line[2:])]
check("and keeps a straight line straight",
      max(abs(v) for v in _cross) < 1e-6, max(abs(v) for v in _cross))
check("words near the narrow top are drawn smaller than near the wide bottom",
      key.scale(200, 10) < 0.8 < 1.0 < key.scale(200, 190) * 1.05,
      (key.scale(200, 10), key.scale(200, 190)))

UP = WP.make(bend=1.0)
up = WP.Warp(UP, W, H)
_mid = [up.point(x, H / 2) for x in (0, 50, 100, 200, 300, 350, W)]
(_cx, _cy), _r = circle(_mid[0], _mid[3], _mid[-1])
check("a bend puts the box's centre line on an arc",
      all(abs(math.hypot(x - _cx, y - _cy) - _r) < 1e-6 for x, y in _mid),
      [round(math.hypot(x - _cx, y - _cy) - _r, 6) for x, y in _mid])
check("bent up, the middle of the line rises above its ends",
      _mid[3][1] < _mid[0][1] - 40 and abs(_mid[0][1] - _mid[-1][1]) < 1e-9,
      _mid)
down = WP.Warp(WP.make(bend=-1.0), W, H)
check("and bent down, it drops below them",
      down.point(200, H / 2)[1] > down.point(0, H / 2)[1] + 40,
      (down.point(200, H / 2), down.point(0, H / 2)))
_edge = [(x, 0.0) for x in range(0, 401, 20)] + [(x, H) for x in range(0, 401, 20)] \
    + [(0.0, y) for y in range(0, 201, 20)] + [(W, y) for y in range(0, 201, 20)]
check("a bent box never draws past the edge of its own window",
      all(-1e-6 <= x <= W + 1e-6 and -1e-6 <= y <= H + 1e-6
          for bend in (-1.0, -0.4, 0.3, 1.0)
          for x, y in (WP.Warp(WP.make(bend=bend), W, H).point(*p) for p in _edge)))
_long = up.path([(0, 100), (400, 100)])
check("a long line is cut into short pieces before it is bent, so it curves",
      len(_long) >= 400 / WP.STEP_PX and near(_long[0], up.point(0, 100))
      and near(_long[-1], up.point(400, 100)), len(_long))
check("and a keystone alone leaves a line as its two ends",
      len(key.path([(0, 100), (400, 100)])) == 2)

print("== a shape as settings.json keeps it ==")
check("a box nobody has shaped is no shape at all",
      WP.make() is None and WP.parse(None) is None and WP.stored(None) is None)
check("corners in their own places and no bend is flat too",
      WP.parse({"corners": [[0, 0], [1, 0], [1, 1], [0, 1]], "bend": 0}) is None)
_kept = WP.stored(LEAN)
check("kept as fractions of the box, plain JSON",
      json.loads(json.dumps(_kept)) == _kept
      and all(0 <= v <= 1 for c in _kept["corners"] for v in c), _kept)
check("and read back as the same shape", WP.parse(_kept) == LEAN,
      (WP.parse(_kept), LEAN))
check("a bend is kept too",
      WP.parse(WP.stored(WP.make(bend=-0.35))).bend == -0.35)
for _label, _bad in (
        ("a list", [1, 2, 3]), ("a word", "bent"),
        ("three corners", {"corners": [[0, 0], [1, 0], [1, 1]]}),
        ("corners that cross", {"corners": [[0, 0], [1, 1], [1, 0], [0, 1]]}),
        ("two corners on one spot", {"corners": [[0, 0], [0.02, 0.01], [1, 1], [0, 1]]}),
        ("not numbers", {"corners": [["a", 0], [1, 0], [1, 1], [0, 1]], "bend": 0.5}),
        ("corners in the wrong order", {"corners": [[0, 1], [1, 1], [1, 0], [0, 0]]})):
    check("a broken shape (%s) is a flat box, never an error" % _label,
          WP.parse(_bad) is None, WP.parse(_bad))
check("a bend past the end of the slider is the end of it",
      WP.parse({"bend": 7}).bend == 1.0 and WP.parse({"bend": "-3"}).bend == -1.0)
check("a bend that is not a number is no bend", WP.parse({"bend": float("nan")}) is None)

print("== drawing through a shape ==")
_raw = Recorder()
check("a box with no shape is drawn on its own canvas, not a stand-in for it",
      WP.wrap(_raw, None, W, H) is _raw
      and WP.wrap(_raw, WP.parse({"bend": 0}), W, H) is _raw)
_raw = Recorder()
_shaped = WP.wrap(_raw, KEY, W, H)
_shaped.create_rectangle(100, 50, 300, 150, outline="#ff7a18", dash=(4, 3))
_shaped.create_oval(150, 50, 250, 150, fill="#0a0704")
_shaped.create_arc(0, 0, 40, 40, start=90, extent=90, style="arc", outline="#3d2404")
_shaped.create_line(0, 100, 400, 100, fill="#ffb545", width=2)
_shaped.create_text(200, 10, text="NEAREST", anchor="n", fill="#e9dccd",
                    font=("Consolas", 10, "bold"))
_shaped.create_text(200, 190, text="FAR", anchor="s", font=("Consolas", 10))
_shaped.delete("all")
_kinds = [c[0] for c in _raw.calls]
check("rectangles, ovals and arcs come out as polygons and lines through the "
      "shape", _kinds == ["create_polygon", "create_polygon", "create_line",
                          "create_line", "create_text", "create_text", "delete"],
      _kinds)
_rect = _raw.calls[0]
check("a rectangle keeps its own look: its outline, its dash, no fill",
      _rect[2] == {"outline": "#ff7a18", "dash": (4, 3), "fill": ""}, _rect[2])
_pts = list(zip(_rect[1][0::2], _rect[1][1::2]))
check("and its corners are where the keystone puts them",
      len(_pts) == 4 and all(near(p, key.point(*q)) for p, q in
                             zip(_pts, [(100, 50), (300, 50), (300, 150), (100, 150)])),
      _pts)
check("an oval keeps its fill and gets the oval's black edge",
      _raw.calls[1][2] == {"fill": "#0a0704", "outline": "black"}
      and len(_raw.calls[1][1]) >= 24, _raw.calls[1][2])
check("an arc drawn as an arc is a line in its outline colour",
      _raw.calls[2][2] == {"fill": "#3d2404"}, _raw.calls[2][2])
_top, _bottom = _raw.calls[4], _raw.calls[5]
check("a word goes to where the shape puts its anchor",
      near(_top[1], key.point(200, 10)) and near(_bottom[1], key.point(200, 190)),
      (_top[1], _bottom[1]))
check("is never turned (Tk cannot draw text at an angle everywhere)",
      all("angle" not in c[2] for c in _raw.calls))
check("and is drawn smaller where the shape narrows",
      _top[2]["font"] == ("Consolas", int(round(10 * key.scale(200, 10))), "bold")
      and _top[2]["font"][1] < 10, _top[2]["font"])
check("keeping its anchor, colour and words",
      (_top[2]["anchor"], _top[2]["fill"], _top[2]["text"]) == ("n", "#e9dccd", "NEAREST"))
check("anything that is not drawing goes straight to the canvas",
      _raw.calls[-1] == ("delete", ("all",), {}))
_raw = Recorder()
WP.wrap(_raw, UP, W, H).create_polygon([(0, 100), (400, 100), (400, 120)], fill="#5fd068")
check("a polygon's long edges are cut up so a bend curves them, and Tk is "
      "left to close it", len(_raw.calls[0][1]) // 2 > 30
      and not near(_raw.calls[0][1][-2:], _raw.calls[0][1][:2]), len(_raw.calls[0][1]))

print("== no shape: exactly what 1.10038 drew ==")
# Fingerprinted from the released 1.10038 overlay with --record: every call
# on every box, its arguments rounded to a thousandth of a pixel and its
# colours written as #colour (the themes are reworked on their own). With
# no shape set, this release must draw the same marks, in the same order.
FLAT_1_10038 = {
    "deposit locked": "59b9e705165ee6310944/61",
    "deposit unlocked": "0de1cec16ce12224aac5/68",
    "guide locked": "a4000a57e1baee0472bb/21",
    "guide unlocked": "d7c3349cd219719969a4/28",
    "radar locked": "3cbb2dbfc388b9a37360/56",
    "radar unlocked": "92d2de393cfda7367e5e/63",
    "status locked": "3d277aa62b142048f927/37",
    "status unlocked": "bf5d0f2fe66effa81e02/41",
    "strip locked": "bb034b37f3cbc48db4fa/27",
    "strip unlocked": "06c74e831b63589be55d/35",
    "targets locked": "4265df40758b9aa9dd8d/43",
    "targets unlocked": "29de01032e7e9678056a/50",
}
FLAT_SCENES = {True: scene(True), False: scene(False)}
for _locked in (True, False):
    for _key in OV.PANEL_ORDER:
        _name = "%s %s" % (_key, "locked" if _locked else "unlocked")
        _calls = FLAT_SCENES[_locked][_key]
        check("%s: the same marks as 1.10038, call for call" % _name,
              fingerprint(without_shape_calls(_calls)) == FLAT_1_10038[_name],
              fingerprint(without_shape_calls(_calls)))
check("locked, a box carries nothing new at all - not even a SHAPE button",
      not any(shape_calls(c) for c in FLAT_SCENES[True].values()))
_junk = {"overlay_shape_%s" % k: v for k, v in zip(
    OV.PANEL_ORDER, ({"corners": [[0, 0], [1, 0], [1, 1], [0, 1]], "bend": 0},
                     "bent", [1, 2], {"corners": [[0, 0], [1, 1], [1, 0], [0, 1]]},
                     None, {"bend": "x"}))}
check("a flat or broken shape in settings draws exactly the same as none",
      all(fingerprint(c) == fingerprint(FLAT_SCENES[True][k])
          for k, c in scene(True, _junk).items()))

print("== a shaped box ==")
BOXES = dict(zip(OV.PANEL_ORDER, (
    {"corners": [[0.04, 0.0], [0.96, 0.0], [1.0, 1.0], [0.0, 1.0]], "bend": 0.6},
    {"corners": [[0.0, 0.08], [1.0, 0.0], [1.0, 1.0], [0.0, 0.92]], "bend": 0.0},
    {"corners": [[0.0, 0.0], [0.9, 0.05], [0.95, 0.95], [0.0, 1.0]], "bend": -0.3},
    {"corners": [[0.1, 0.0], [0.9, 0.0], [1.0, 1.0], [0.0, 1.0]], "bend": 0.25},
    {"corners": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], "bend": -0.5},
    {"corners": [[0.05, 0.05], [1.0, 0.0], [0.97, 1.0], [0.0, 0.95]], "bend": 0.0})))
SHAPED = scene(True, {"overlay_shape_%s" % k: v for k, v in BOXES.items()})
_sizes = {key: OV.panel_pixels(OV.DEFAULT_LAYOUT[key], 1920, 1080, key)[:2]
          for key in OV.PANEL_ORDER}


def _texts(calls):
    return [c for c in calls if c[0] == "create_text"]


def _points(calls):
    out = []
    for name, args, _kw in calls:
        if name in ("create_line", "create_polygon"):
            nums = WP._flat_numbers(args)
            out.extend(zip(nums[0::2], nums[1::2]))
    return out


for _key in OV.PANEL_ORDER:
    _flat, _bent = FLAT_SCENES[True][_key], SHAPED[_key]
    _w, _h = _sizes[_key]
    _warp = WP.Warp(WP.parse(BOXES[_key]), _w, _h)
    _ft, _bt = _texts(_flat), _texts(_bent)
    check("%s: every word is still drawn, in the same order" % _key,
          [c[2].get("text") for c in _ft] == [c[2].get("text") for c in _bt]
          and len(_ft) > 0, (len(_ft), len(_bt)))
    check("%s: each one at its anchor moved by the shape" % _key,
          all(near(b[1], _warp.point(*f[1][:2]), 1e-6) for f, b in zip(_ft, _bt)),
          [(f[1], b[1]) for f, b in zip(_ft, _bt) if not
           near(b[1], _warp.point(*f[1][:2]), 1e-6)][:2])
    check("%s: and none of them turned" % _key,
          all("angle" not in c[2] for c in _bt))
    check("%s: no rectangle, oval or arc is drawn square any more" % _key,
          not [c for c in _bent if c[0] in ("create_rectangle", "create_oval",
                                            "create_arc")])
    _pts = _points(_bent)
    _out = [p for p in _pts if not (-3 <= p[0] <= _w + 3 and -3 <= p[1] <= _h + 3)]
    check("%s: and nothing is drawn outside the box's own window" % _key,
          _pts and not _out, _out[:3])
_scope_fonts = [(f[2]["font"], b[2]["font"]) for f, b in
                zip(_texts(FLAT_SCENES[True][OV.STATUS]), _texts(SHAPED[OV.STATUS]))
                if "font" in f[2]]
check("words in the narrowed top of a keystoned box are drawn smaller",
      any(b[1] < f[1] for f, b in _scope_fonts), _scope_fonts[:4])

print("== shaping a box by hand, in unlock mode ==")


class Event:
    """A mouse event: where on the box, and where on the screen."""

    def __init__(self, x, y, root):
        self.x, self.y = x, y
        self.x_root, self.y_root = root[0] + x, root[1] + y


def frame(calls):
    """What a box shows now: the calls since it was last cleared."""
    start = max([i for i, c in enumerate(calls) if c[:2] == ("delete", ("all",))] or [-1])
    return calls[start + 1:]


def tagged(calls, tag):
    return [c for c in calls if tag in (c[2].get("tags") or ())]


def centre(box):
    return (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0


def pull(panel, start, end, steps=4):
    """Press at `start` on the box, drag to `end`, let go. The screen
    position comes from where the box was when it was pressed, as a real
    pointer's does."""
    root = (panel.window.winfo_x(), panel.window.winfo_y())
    panel._grab(Event(start[0], start[1], root))
    for k in range(1, steps + 1):
        t = k / float(steps)
        panel._move(Event(start[0] + (end[0] - start[0]) * t,
                          start[1] + (end[1] - start[1]) * t, root))
    panel._drop(Event(end[0], end[1], root))


def click(panel, x, y):
    pull(panel, (x, y), (x, y), steps=0)


SHAPE_KEY = "overlay_shape_%s" % OV.TARGETS
over, app = overlay_with_boxes(locked=False)
draw_scene(over)
box = over.panels[OV.TARGETS]
canvas, win = box.canvas, box.window
bw, bh = win.w, win.h
place = (win.x, win.y)
_now = frame(canvas.calls)
_toggle = [c for c in tagged(_now, "shapectl") if c[0] == "create_text"]
check("unlocked, every box has a SHAPE button",
      all([c for c in tagged(frame(p.canvas.calls), "shapectl")
           if c[0] == "create_text" and c[2].get("text") == "SHAPE"]
          for p in over.panels.values()))
check("in its title bar", _toggle and _toggle[0][1][1] <= OV.HANDLE_PX, _toggle[:1])
check("and no corner handles until it is pressed", not tagged(_now, "handle"))
_found = box.shape_controls(bw, bh)
click(box, *centre(_found["toggle"]))
_now = frame(canvas.calls)
check("pressing SHAPE does not move the box",
      (win.x, win.y, win.w, win.h) == place + (bw, bh), (win.x, win.y))
check("and shows four corner handles at once, without waiting for a redraw",
      len(tagged(_now, "handle")) == 4, len(tagged(_now, "handle")))
_words = [c[2].get("text") for c in tagged(_now, "shapectl") if c[0] == "create_text"]
check("a BEND slider and a button to make it flat again",
      "BEND" in _words and any(str(w).startswith("FLAT") for w in _words), _words)
check("pressing it changes nothing about the box's shape", SHAPE_KEY not in over.settings)

_found = box.shape_controls(bw, bh)
_saved = app.saved
pull(box, _found["handles"][0], (bw * 0.15, bh * 0.1))
_kept = over.settings.get(SHAPE_KEY)
check("dragging the top-left handle moves that corner of the shape",
      _kept and near(_kept["corners"][0], (0.15, 0.1), 0.002)
      and _kept["corners"][1:] == [[1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], _kept)
check("kept as fractions of the box",
      _kept and all(0 <= v <= 1 for c in _kept["corners"] for v in c), _kept)
check("the box itself stays where it was",
      (win.x, win.y, win.w, win.h) == place + (bw, bh), (win.x, win.y, win.w, win.h))
check("and the app is told to save once it is let go", app.saved == _saved + 1,
      (app.saved, _saved))
_now = frame(canvas.calls)
_marks = tagged(_now, "handle")
check("the handle is drawn where it was dropped",
      _marks and near(centre(WP._flat_numbers(_marks[0][1])),
                      (bw * 0.15, bh * 0.1), 1.0), _marks[:1])
_flat_texts = _texts(without_shape_calls(frame(FLAT_SCENES[False][OV.TARGETS])))
_bent_texts = _texts(without_shape_calls(_now))
_warp = WP.Warp(over.shape(OV.TARGETS), bw, bh)
check("and what the box shows is drawn through the new shape straight away",
      len(_bent_texts) > 2
      and near(_bent_texts[1][1], _warp.point(*_flat_texts[1][1][:2]), 1e-6)
      and not near(_bent_texts[1][1], _flat_texts[1][1]),
      (_flat_texts[1][1], _bent_texts[1][1]))
check("while the dashed edge and the title bar stay square: the window is "
      "still a rectangle",
      [c for c in _now if c[0] == "create_rectangle" and c[1] == (1, 1, bw - 2, bh - 2)]
      and [c for c in _now if c[0] == "create_text" and c[2].get("text") == "drag to move"
           and c[1] == (bw - 6, OV.HANDLE_PX / 2 + 1)])

_before = over.settings.get(SHAPE_KEY)
_found = box.shape_controls(bw, bh)
pull(box, _found["handles"][0], (bw - 4, bh - 4))
check("a corner dragged across the box, folding it over, stays where it was",
      over.settings.get(SHAPE_KEY) == _before, over.settings.get(SHAPE_KEY))
_found = box.shape_controls(bw, bh)
pull(box, _found["handles"][2], (bw * 0.8, bh * 0.85))
_found = box.shape_controls(bw, bh)
pull(box, _found["handles"][2], (bw - 2, bh - 2))
check("one dropped back near where it started goes back exactly there",
      over.settings[SHAPE_KEY]["corners"][2] == [1.0, 1.0], over.settings[SHAPE_KEY])

_found = box.shape_controls(bw, bh)
_x0, _x1, _mid = _found["track"]
pull(box, _found["knob"], (_x1 + 30, _mid))
check("the bend slider, pulled to its end, bends the box all the way",
      over.settings[SHAPE_KEY]["bend"] == 1.0, over.settings[SHAPE_KEY])
_found = box.shape_controls(bw, bh)
pull(box, _found["knob"], ((_x0 + _x1) / 2.0 + 2, _mid))
check("and pulled back to the middle, not at all",
      over.settings[SHAPE_KEY]["bend"] == 0.0, over.settings[SHAPE_KEY])
_found = box.shape_controls(bw, bh)
pull(box, _found["knob"], (_x0 + (_x1 - _x0) * 0.2, _mid + 3))
check("in between, in between",
      abs(over.settings[SHAPE_KEY]["bend"] + 0.6) < 0.02, over.settings[SHAPE_KEY])

print("== it follows the box ==")
_kept = dict(over.settings[SHAPE_KEY])
pull(box, (40, 8), (140, 108))
check("the box is still moved by its bar, shape and all",
      (win.x, win.y) == (place[0] + 100, place[1] + 100)
      and over.settings[SHAPE_KEY] == _kept, (win.x, win.y))
win.w, win.h = bw * 2, bh * 2
draw_scene(over)
_marks = tagged(frame(canvas.calls), "handle")
check("made twice the size, its corners are at the same share of it",
      _marks and near(centre(WP._flat_numbers(_marks[0][1])),
                      (bw * 2 * 0.15, bh * 2 * 0.1), 1.0)
      and over.settings[SHAPE_KEY] == _kept, _marks[:1])
win.w, win.h = bw, bh
draw_scene(over)

print("== flat again ==")
_saved = app.saved
_found = box.shape_controls(bw, bh)
click(box, *centre(_found["flat"]))
check("Flat again takes the shape away",
      SHAPE_KEY not in over.settings and over.shape(OV.TARGETS) is None,
      over.settings.get(SHAPE_KEY))
check("and is saved", app.saved == _saved + 1, (app.saved, _saved))
check("leaving the box drawing exactly what it drew before it was shaped",
      fingerprint(without_shape_calls(frame(canvas.calls)))
      == fingerprint(without_shape_calls(frame(FLAT_SCENES[False][OV.TARGETS]))))
_found = box.shape_controls(bw, bh)
click(box, *centre(_found["toggle"]))
check("SHAPE again puts the handles away",
      not tagged(frame(canvas.calls), "handle")
      and [c for c in tagged(frame(canvas.calls), "shapectl")
           if c[2].get("text") == "SHAPE"])
pull(box, (bw - 3, bh - 3), (bw + 37, bh + 23))
check("and the corner grip resizes the box again",
      (win.w, win.h) == (bw + 40, bh + 26), (win.w, win.h))
win.w, win.h = bw, bh

over.settings["overlay_click_through"] = True
over.settings[SHAPE_KEY] = WP.stored(LEAN)
box.shaping = True
draw_scene(over)
check("locked, there is not a handle or a button on any box",
      not any(tagged(frame(p.canvas.calls), "shapectl") for p in over.panels.values()))
pull(box, (5, 5), (60, 60))
check("and a click on one shapes nothing",
      over.settings.get(SHAPE_KEY) == WP.stored(LEAN), over.settings.get(SHAPE_KEY))

print("== reset puts the shapes away too ==")
over.settings["overlay_click_through"] = False
over.settings[SHAPE_KEY] = WP.stored(LEAN)
over.settings["overlay_shape_%s" % OV.STRIP] = WP.stored(UP)
over.reset_layout()
check("Reset box positions makes every box flat again",
      not [k for k in over.settings if k.startswith("overlay_shape_")],
      [k for k in over.settings if k.startswith("overlay_shape_")])

print("== loose ends ==")
over, app = overlay_with_boxes(locked=False)
box = over.panels[OV.TARGETS]
win = box.window
bw, bh = win.w, win.h
_found = box.shape_controls(bw, bh)
click(box, *centre(_found["toggle"]))
check("SHAPE pressed before the box has ever been drawn is simply remembered",
      box.shaping and not box.canvas.calls, len(box.canvas.calls))
draw_scene(over)
check("and the handles are up at the first draw",
      len(tagged(frame(box.canvas.calls), "handle")) == 4)
_found = box.shape_controls(bw, bh)
_root = (win.winfo_x(), win.winfo_y())
box._grab(Event(_found["handles"][1][0], _found["handles"][1][1], _root))
box._move(Event(bw * 0.8, bh * 0.12, _root))
box._drop(None)
_kept = over.settings.get(SHAPE_KEY)
check("a handle let go with no place given lands where it was last seen",
      _kept and near(_kept["corners"][1], (0.8, 0.12), 0.002), _kept)
over.set_locked(True)
check("locking the overlay puts the handles away for next time",
      not box.shaping and box._shape_drag is None)
check("but keeps the shape", over.settings.get(SHAPE_KEY) == _kept)
_blank = OV.Overlay(app=StubApp(), tk_module=None, settings={})
_blank.redraw(OV.TARGETS)
check("a redraw before anything was ever drawn does nothing at all",
      _blank.canvas is None)

print("== on the real toolkit ==")
try:
    import tkinter as tk
    _tkroot = tk.Tk()
    _tkroot.withdraw()
except Exception as exc:                        # no Tk, or no display
    _tkroot = None
    print("  SKIP  no display to run the real toolkit on (%s)" % exc.__class__.__name__)
if _tkroot is not None:
    # The recorder above takes any call; Tk does not. Every shaped box,
    # handles and all, drawn on a real canvas: every mark the shape turns
    # into - polygons for rectangles and ovals, lines for arcs, scaled
    # fonts - has to be one Tk accepts.
    over, app = overlay_with_boxes(
        locked=False, settings={"overlay_shape_%s" % k: v for k, v in BOXES.items()})
    for _key, _panel in over.panels.items():
        _panel.canvas = tk.Canvas(_tkroot, width=_panel.window.w,
                                  height=_panel.window.h)
        _panel.shaping = True
    try:
        draw_scene(over)
        _drawn = {k: len(p.canvas.find_all()) for k, p in over.panels.items()}
        _trouble = None
    except Exception as exc:
        _drawn, _trouble = {}, exc
    check("every shaped box is drawn on a real canvas, handles and all, "
          "without a word from Tk",
          _trouble is None and len(_drawn) == 6 and all(n > 10 for n in _drawn.values()),
          (repr(_trouble), _drawn))
    _box = over.panels[OV.STATUS]
    _bbox = _box.canvas.bbox("all") if _trouble is None else None
    check("and what it draws stays inside the box's own window",
          _bbox and _bbox[0] >= -3 and _bbox[1] >= -3
          and _bbox[2] <= _box.window.w + 3 and _bbox[3] <= _box.window.h + 3,
          (_bbox, _box.window.w, _box.window.h))
    _tkroot.destroy()

print("== the app side ==")
_src = io.open(os.path.join(REPO, "edsmt.py"), encoding="utf-8").read()
check("unlocking the overlay says where the SHAPE button is",
      "SHAPE" in _src[_src.find("Overlay unlocked."):_src.find("Overlay unlocked.") + 400])
_guide = io.open(os.path.join(REPO, "docs", "GUIDE.md"), encoding="utf-8").read()
check("and the guide explains shaping a box",
      "SHAPE" in _guide and "Flat again" in _guide)

if fails:
    print("\n%d failure(s): %s" % (len(fails), "; ".join(fails[:6])))
else:
    print("\nall passed")
sys.exit(1 if fails else 0)
