"""
The shape of an overlay box: a keystone and a bend.

Asked for on the Frontier forum: the compass, the map and the cards are flat
rectangles, and the cockpit and the helmet are not. So a box can be given a
shape. Its four corners can be moved - a keystone, so a box can lean the way
the canopy frame does - and it can be bent, its centre line following an
arc, for the curve of the helmet.

The window itself stays a rectangle; only what is drawn in it changes shape.
Everything a box draws goes through wrap(): lines and polygons have their
points moved (long ones cut into short pieces first, so a bend comes out
curved), rectangles, ovals and arcs become polygons and lines through the
same points, and a word is put at its moved anchor with its font scaled by
how much the shape grows or shrinks the box there. Words are never turned:
Tk cannot draw text at an angle on every machine, and a word that leans is
harder to read at speed than one that does not.

A box with no shape set is drawn through nothing at all: wrap() hands back
the very canvas it was given, so the drawing is the one it always was.

A shape is stored as fractions of its box - the corners as shares of the
box's width and height, the bend from -1 to 1 - so it follows the box when
it is moved or resized, and fits every screen.

Plain maths, no Tk, so all of it is checked without a display.
"""

import math

# The corners in order round the box: top left, top right, bottom right,
# bottom left. A box with them here and no bend is flat.
FLAT_CORNERS = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))

# A full bend lifts (or drops) the middle of the box by this share of its
# height. What is drawn is squeezed into the rest of the height, so a bent
# box never draws past the edge of its own window.
MAX_SAG = 0.5

# A line or an edge longer than this many pixels is cut into pieces before a
# bend moves it, or a bent box would be drawn with straight lines.
STEP_PX = 12.0

# No side of the shape shorter than this share of the box: a corner dragged
# on top of another one would leave nothing to draw into.
MIN_SIDE = 0.12

# A corner dropped this close to where it started, in pixels, goes back
# exactly there, and a bend this close to nothing is no bend.
SNAP_PX = 6.0
SNAP_BEND = 0.05

# Unlock-mode furniture, in pixels.
HANDLE_PX = 10.0
HIT_PX = 11.0
TOGGLE_LABEL = "SHAPE"
CONTROL_PX = 6.2          # one character of the controls' 8-point labels


def _clamp(value, low, high):
    return low if value < low else (high if value > high else value)


def _number(value, default=0.0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(value) or math.isinf(value):
        return default
    return value


class Shape:
    """Four corners as fractions of the box, and a bend from -1 to 1.

    Made through make() or parse(), which keep every value in range and
    answer None for a box that is flat."""

    __slots__ = ("corners", "bend")

    def __init__(self, corners=FLAT_CORNERS, bend=0.0):
        self.corners = tuple((float(x), float(y)) for x, y in corners)
        self.bend = float(bend)

    def __eq__(self, other):
        return isinstance(other, Shape) and self.corners == other.corners \
            and self.bend == other.bend

    def __repr__(self):
        return "Shape(%r, %r)" % (self.corners, self.bend)


def is_flat(shape):
    """No shape at all, or one that changes nothing."""
    if shape is None:
        return True
    return shape.bend == 0.0 and all(
        abs(x - fx) < 1e-9 and abs(y - fy) < 1e-9
        for (x, y), (fx, fy) in zip(shape.corners, FLAT_CORNERS))


def _convex(corners):
    """Do the four corners go round one way, never crossing or folding?"""
    signs = []
    for i in range(4):
        ax, ay = corners[i]
        bx, by = corners[(i + 1) % 4]
        cx, cy = corners[(i + 2) % 4]
        signs.append((bx - ax) * (cy - by) - (by - ay) * (cx - bx))
    return all(s > 1e-9 for s in signs) or all(s < -1e-9 for s in signs)


def usable(corners):
    """Four corners a box can be drawn into: inside the box, going round
    the right way, and no side too short to hold anything."""
    if len(corners) != 4:
        return False
    if any(not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0) for x, y in corners):
        return False
    for i in range(4):
        (ax, ay), (bx, by) = corners[i], corners[(i + 1) % 4]
        if math.hypot(bx - ax, by - ay) < MIN_SIDE:
            return False
    # Clockwise on the screen, as FLAT_CORNERS are: y grows downwards.
    signs = []
    for i in range(4):
        ax, ay = corners[i]
        bx, by = corners[(i + 1) % 4]
        cx, cy = corners[(i + 2) % 4]
        signs.append((bx - ax) * (cy - by) - (by - ay) * (cx - bx))
    return _convex(corners) and all(s > 0 for s in signs)


def make(corners=FLAT_CORNERS, bend=0.0):
    """A Shape, or None when it is flat or the corners cannot be drawn into."""
    try:
        points = tuple((_clamp(_number(x, None), 0.0, 1.0),
                        _clamp(_number(y, None), 0.0, 1.0)) for x, y in corners)
    except (TypeError, ValueError):
        # A corner that is not a number is not guessed at.
        return None
    if not usable(points):
        return None
    bend = _clamp(_number(bend), -1.0, 1.0)
    shape = Shape(points, bend)
    return None if is_flat(shape) else shape


def parse(value):
    """A shape as settings.json keeps it, or None for a flat box.

    {"corners": [[x, y], [x, y], [x, y], [x, y]], "bend": b}. Anything else -
    nothing stored, a hand edit gone wrong, corners that fold over - is a
    flat box, never an error: a broken shape must not cost anyone the box."""
    if not isinstance(value, dict):
        return None
    corners = value.get("corners", FLAT_CORNERS)
    try:
        corners = [(c[0], c[1]) for c in corners]
    except (TypeError, IndexError, KeyError):
        return None
    if len(corners) != 4:
        return None
    return make(corners, value.get("bend", 0.0))


def stored(shape):
    """What settings.json keeps for a shape: None for a flat box, so a box
    nobody has shaped writes nothing at all."""
    if is_flat(shape):
        return None
    return {"corners": [[round(x, 4), round(y, 4)] for x, y in shape.corners],
            "bend": round(shape.bend, 3)}


# ---------------------------------------------------------------------------
# The transform
# ---------------------------------------------------------------------------

class Warp:
    """Where a point of a box `width` x `height` lands once it is shaped.

    The bend comes first, in the box's own frame: the box's centre line is
    put on a circular arc that rises (bend > 0) or falls (bend < 0) by up to
    MAX_SAG of the box's height in the middle, and everything else in the
    box moves with it, squeezed into what is left of the height. Then the
    keystone: the one projective transform that takes the box's corners to
    the four corners of the shape."""

    def __init__(self, shape, width, height):
        self.width = max(1.0, float(width))
        self.height = max(1.0, float(height))
        # Flat is no arithmetic at all, not arithmetic that comes out the
        # same give or take the last bit of a float.
        self.flat = is_flat(shape)
        corners = shape.corners if shape is not None else FLAT_CORNERS
        self.bend = shape.bend if shape is not None else 0.0
        self.sag = abs(self.bend) * MAX_SAG
        sag_px = self.sag * self.height
        half = self.width / 2.0
        # The arc through both ends of the centre line and sag_px above (or
        # below) its middle has this radius.
        self._radius = (sag_px * sag_px + half * half) / (2.0 * sag_px) \
            if sag_px > 1e-9 else 0.0
        self._sag_px = sag_px
        self._keystone = _square_to_quad(corners)

    @property
    def bends(self):
        return self._sag_px > 1e-9

    def _lift(self, u):
        """How far up the arc is at u (0..1 across the box), as a share of
        the full sag: 0 at both ends, 1 in the middle."""
        if not self.bends:
            return 0.0
        d = (u - 0.5) * self.width
        r = self._radius
        return (math.sqrt(max(0.0, r * r - d * d)) - (r - self._sag_px)) / self._sag_px

    def point(self, x, y):
        """(x, y) in the box, where it is drawn once the box is shaped."""
        if self.flat:
            return float(x), float(y)
        u = float(x) / self.width
        v = float(y) / self.height
        if self.bends:
            lift = self._lift(u)
            if self.bend > 0:
                v = self.sag * (1.0 - lift) + v * (1.0 - self.sag)
            else:
                v = self.sag * lift + v * (1.0 - self.sag)
        a, b, c, d, e, f, g, h = self._keystone
        w = g * u + h * v + 1.0
        if abs(w) < 1e-12:
            w = 1e-12
        return ((a * u + b * v + c) / w * self.width,
                (d * u + e * v + f) / w * self.height)

    def scale(self, x, y):
        """How much bigger (over 1) or smaller (under 1) the shape draws
        things at (x, y): the square root of the area a small square there
        is drawn with."""
        step = 1.0
        x0, y0 = self.point(x - step, y)
        x1, y1 = self.point(x + step, y)
        x2, y2 = self.point(x, y - step)
        x3, y3 = self.point(x, y + step)
        jx = ((x1 - x0) / (2 * step), (y1 - y0) / (2 * step))
        jy = ((x3 - x2) / (2 * step), (y3 - y2) / (2 * step))
        return math.sqrt(abs(jx[0] * jy[1] - jx[1] * jy[0]))

    def path(self, points, closed=False):
        """A run of points, cut into short pieces when the box is bent, and
        moved. Closed paths are not given their first point again at the
        end: Tk closes a polygon itself."""
        points = list(points)
        if not points:
            return []
        if not self.bends:
            return [self.point(x, y) for x, y in points]
        out = []
        ends = points + [points[0]] if closed and len(points) > 2 else points
        for (ax, ay), (bx, by) in zip(ends, ends[1:]):
            pieces = max(1, int(math.ceil(math.hypot(bx - ax, by - ay) / STEP_PX)))
            for k in range(pieces):
                t = k / float(pieces)
                out.append(self.point(ax + (bx - ax) * t, ay + (by - ay) * t))
        if not (closed and len(points) > 2):
            out.append(self.point(*ends[-1]))
        return out


def _square_to_quad(corners):
    """The projective transform from the unit square to four corners, as
    (a, b, c, d, e, f, g, h): x = (au + bv + c) / (gu + hv + 1), and y
    likewise with d, e, f. The square's corners (0,0), (1,0), (1,1), (0,1)
    go to corners[0..3]."""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = corners
    dx1, dx2, dx3 = x1 - x2, x3 - x2, x0 - x1 + x2 - x3
    dy1, dy2, dy3 = y1 - y2, y3 - y2, y0 - y1 + y2 - y3
    if abs(dx3) < 1e-12 and abs(dy3) < 1e-12:
        # A parallelogram: nothing projective about it.
        return (x1 - x0, x3 - x0, x0, y1 - y0, y3 - y0, y0, 0.0, 0.0)
    den = dx1 * dy2 - dx2 * dy1
    if abs(den) < 1e-12:
        return (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)
    g = (dx3 * dy2 - dx2 * dy3) / den
    h = (dx1 * dy3 - dx3 * dy1) / den
    return (x1 - x0 + g * x1, x3 - x0 + h * x3, x0,
            y1 - y0 + g * y1, y3 - y0 + h * y3, y0, g, h)


# ---------------------------------------------------------------------------
# Drawing through it
# ---------------------------------------------------------------------------

def wrap(canvas, shape, width, height):
    """The canvas a box is drawn on: the one given, untouched, when the box
    has no shape - so a flat box draws exactly what it always drew - and a
    shaping stand-in for it otherwise."""
    if canvas is None or is_flat(shape):
        return canvas
    return WarpedCanvas(canvas, Warp(shape, width, height))


def _flat_numbers(args):
    """Tk takes points as numbers, pairs or lists of either; all of it as
    one list of numbers."""
    out = []
    for item in args:
        if isinstance(item, (list, tuple)):
            out.extend(_flat_numbers(item))
        else:
            out.append(float(item))
    return out


def _pairs(numbers):
    return [(numbers[i], numbers[i + 1]) for i in range(0, len(numbers) - 1, 2)]


def _unpair(points):
    out = []
    for x, y in points:
        out.extend((x, y))
    return out


def _ellipse(x0, y0, x1, y1, start=0.0, extent=360.0):
    """Points round an oval's box, or along part of it; Tk's angles, in
    degrees anticlockwise from three o'clock."""
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    rx, ry = abs(x1 - x0) / 2.0, abs(y1 - y0) / 2.0
    reach = math.pi * (rx + ry) * abs(extent) / 360.0
    count = int(_clamp(reach / 6.0, 12, 72)) if abs(extent) >= 360 else \
        int(_clamp(reach / 6.0, 3, 72))
    whole = abs(extent) >= 360
    steps = count if whole else count + 1
    out = []
    for k in range(steps):
        angle = math.radians(start + extent * k / float(count))
        out.append((cx + rx * math.cos(angle), cy - ry * math.sin(angle)))
    return out


class WarpedCanvas:
    """A box's canvas with everything drawn on it shaped. Anything that is
    not drawing goes straight through to the canvas underneath."""

    def __init__(self, canvas, warp):
        self._canvas = canvas
        self._warp = warp

    def __getattr__(self, name):
        return getattr(self._canvas, name)

    def create_line(self, *args, **kw):
        points = self._warp.path(_pairs(_flat_numbers(args)))
        return self._canvas.create_line(*_unpair(points), **kw)

    def create_polygon(self, *args, **kw):
        points = self._warp.path(_pairs(_flat_numbers(args)), closed=True)
        return self._canvas.create_polygon(*_unpair(points), **kw)

    def _outlined(self, points, kw):
        # A rectangle's and an oval's own defaults, not a polygon's: no fill
        # and a black edge unless told otherwise.
        kw = dict(kw)
        kw.setdefault("fill", "")
        kw.setdefault("outline", "black")
        return self._canvas.create_polygon(
            *_unpair(self._warp.path(points, closed=True)), **kw)

    def create_rectangle(self, *args, **kw):
        x0, y0, x1, y1 = _flat_numbers(args)[:4]
        return self._outlined([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], kw)

    def create_oval(self, *args, **kw):
        x0, y0, x1, y1 = _flat_numbers(args)[:4]
        return self._outlined(_ellipse(x0, y0, x1, y1), kw)

    def create_arc(self, *args, **kw):
        x0, y0, x1, y1 = _flat_numbers(args)[:4]
        kw = dict(kw)
        style = str(kw.pop("style", "pieslice"))
        start = _number(kw.pop("start", 0.0))
        extent = _number(kw.pop("extent", 90.0), 90.0)
        points = _ellipse(x0, y0, x1, y1, start, extent)
        if style == "arc":
            # An arc is a line, in the arc's outline colour.
            kw.pop("fill", None)
            kw["fill"] = kw.pop("outline", "black")
            kw.pop("outlinestipple", None)
            return self._canvas.create_line(*_unpair(self._warp.path(points)), **kw)
        if style != "chord":
            points = [((x0 + x1) / 2.0, (y0 + y1) / 2.0)] + points
        return self._outlined(points, kw)

    def create_text(self, *args, **kw):
        numbers = _flat_numbers(args)
        x, y = numbers[0], numbers[1]
        scale = self._warp.scale(x, y)
        kw = dict(kw)
        if abs(scale - 1.0) >= 0.01:
            font = kw.get("font")
            if isinstance(font, tuple) and len(font) >= 2:
                try:
                    size = int(font[1])
                    grown = max(6, int(round(abs(size) * scale)))
                    kw["font"] = (font[0], grown if size >= 0 else -grown) + tuple(font[2:])
                except (TypeError, ValueError):
                    pass
            if isinstance(kw.get("width"), (int, float)):
                kw["width"] = max(20, int(round(kw["width"] * scale)))
        return self._canvas.create_text(*self._warp.point(x, y), **kw)


# ---------------------------------------------------------------------------
# Shaping a box by hand, in unlock mode
# ---------------------------------------------------------------------------

def _label_px(text):
    return len(text) * CONTROL_PX


def controls(width, height, shape, editing, gap=None, bar=18.0):
    """Where the shaping controls go on a box `width` x `height`.

    The SHAPE button sits in the gap left in the box's title bar, `gap`
    being (left, right) in pixels. While `editing`, there are also a handle
    on each corner of the shape, and across the middle of the box a BEND
    slider and the button that makes the box flat again. One answer, used to
    draw the controls and to tell what a click landed on, so the two can
    never disagree. Pixels throughout; nothing here is drawn."""
    width, height = float(width), float(height)
    left, right = gap if gap else (6.0, width - 6.0)
    toggle_w = _label_px(TOGGLE_LABEL) + 10.0
    centre = (left + right) / 2.0
    out = {"editing": bool(editing),
           "toggle": (centre - toggle_w / 2.0, 3.0, centre + toggle_w / 2.0, bar - 3.0)}
    if not editing:
        return out
    corners = shape.corners if shape is not None else FLAT_CORNERS
    edge = HANDLE_PX / 2.0
    out["quad"] = [(x * width, y * height) for x, y in corners]
    out["handles"] = [(_clamp(x, edge, width - edge), _clamp(y, edge, height - edge))
                      for x, y in out["quad"]]
    middle = bar + (height - bar) / 2.0
    flat = "FLAT AGAIN" if width >= 300 else "FLAT"
    flat_w = _label_px(flat) + 10.0
    label_w = _label_px("BEND") + 6.0
    track = _clamp(width * 0.4, 50.0, 240.0)
    start = (width - (label_w + track + 10.0 + flat_w)) / 2.0
    out["bend_label"] = (start, middle)
    x0 = start + label_w
    out["track"] = (x0, x0 + track, middle)
    bend = shape.bend if shape is not None else 0.0
    out["knob"] = (x0 + (bend + 1.0) / 2.0 * track, middle)
    fx = x0 + track + 10.0
    out["flat"] = (fx, middle - 7.0, fx + flat_w, middle + 7.0)
    out["flat_label"] = flat
    return out


def _inside(box, x, y):
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def hit(found, x, y):
    """What a click at (x, y) is on: "toggle", "flat", ("corner", n),
    "bend", or None for the box itself (move it, or resize it)."""
    if _inside(found["toggle"], x, y):
        return "toggle"
    if not found.get("editing"):
        return None
    if _inside(found["flat"], x, y):
        return "flat"
    near = [(math.hypot(hx - x, hy - y), n)
            for n, (hx, hy) in enumerate(found["handles"])]
    best = min(near)
    if best[0] <= HIT_PX:
        return ("corner", best[1])
    x0, x1, middle = found["track"]
    if x0 - 8 <= x <= x1 + 8 and abs(y - middle) <= 9:
        return "bend"
    return None


def drag(shape, target, x, y, width, height, found):
    """The shape after `target` is dragged to (x, y) - a corner, or the
    bend slider's knob. A corner that would fold the shape over, or squash a
    side to nothing, stays where it was. None when the result is flat."""
    corners = list(shape.corners if shape is not None else FLAT_CORNERS)
    bend = shape.bend if shape is not None else 0.0
    width, height = max(1.0, float(width)), max(1.0, float(height))
    if target == "bend":
        x0, x1, _middle = found["track"]
        bend = _clamp((float(x) - x0) / max(1.0, x1 - x0) * 2.0 - 1.0, -1.0, 1.0)
        if abs(bend) < SNAP_BEND:
            bend = 0.0
        return make(corners, bend)
    if isinstance(target, tuple) and target[0] == "corner":
        n = int(target[1])
        fx = _clamp(float(x) / width, 0.0, 1.0)
        fy = _clamp(float(y) / height, 0.0, 1.0)
        home = FLAT_CORNERS[n]
        if math.hypot((fx - home[0]) * width, (fy - home[1]) * height) <= SNAP_PX:
            fx, fy = home
        moved = list(corners)
        moved[n] = (fx, fy)
        if usable(moved):
            corners = moved
        return make(corners, bend)
    return shape
