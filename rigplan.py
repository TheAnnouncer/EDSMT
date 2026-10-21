"""Where to put the rigs on a deposit - the rig planner.

Drive the edge of a deposit once with the planner tracing, and this works
out where up to six rigs fit inside what was driven, each at least a set
spacing from the next. The spacing is a setting, not a constant: it is the
community's working figure for how close two rigs can go down, measured in
the field and never published by Frontier, and a better number must not
need a new build.

Pure geometry, no game and no window, so all of it can be tested from a
list of points. Positions come in and go out as latitude and longitude on a
body of known radius; the working is done on a flat local plane in metres,
which over a deposit a couple of hundred metres across is accurate to far
less than the width of the Rhino.
"""

import math

# The community's working minimum between two rigs, centre to centre.
RIG_SPACING_M = 78.0
MAX_PINS = 6

# A trace is a loop driven round the deposit's edge. It closes itself when
# the Rhino comes back near where it started, having gone far enough and
# round enough corners for that to be a loop and not a wobble on the spot.
TRACE_STEP_M = 5.0          # a new point every 5 m of driving
TRACE_CLOSE_M = 15.0        # back within 15 m of the start closes it...
TRACE_CLOSE_MAX_M = 60.0    # ...or further on a big body, never past this
# Status.json only moves the Rhino's latitude and longitude on in steps of
# about this much, so on a big body the positions come metres apart and
# "back within 15 m" can be stepped straight over. The closing distance
# grows to half again one step.
STATUS_STEP_DEG = 0.0005
TRACE_MIN_POINTS = 10
TRACE_MIN_PATH_M = 60.0
TRACE_MAX_SPAN_M = 3000.0   # bigger than any deposit: that was a drive, not a trace
ON_EDGE_M = 1.0             # a pin this close outside the line still counts
MAX_CORNERS = 48            # the traced edge is thinned to this many points
# The exact pass tries a fine grid of places, no more than this many of them,
# and tests the last few against every corner of the line as it was driven.
EXACT_CELLS = 2500
EXACT_CORNERS = 120
FIT_MOST = 12               # how many rigs "fit" is counted up to

# How finely each packing is tried: lattice turns in degrees, and how many
# shifts of the lattice per spacing in each direction.
_TURNS = tuple(range(0, 60, 10))
_SHIFTS = 4


# -- latitude/longitude and the local plane -----------------------------------

def to_local(origin, point, radius_m):
    """(east, north) metres of `point` from `origin`, both (lat, lon)."""
    lat0, lon0 = math.radians(origin[0]), math.radians(origin[1])
    lat1, lon1 = math.radians(point[0]), math.radians(point[1])
    a = (math.sin((lat1 - lat0) / 2) ** 2 + math.cos(lat0) * math.cos(lat1)
         * math.sin((lon1 - lon0) / 2) ** 2)
    metres = 2 * math.asin(min(1.0, math.sqrt(a))) * float(radius_m)
    y = math.sin(lon1 - lon0) * math.cos(lat1)
    x = (math.cos(lat0) * math.sin(lat1)
         - math.sin(lat0) * math.cos(lat1) * math.cos(lon1 - lon0))
    theta = math.atan2(y, x)
    return metres * math.sin(theta), metres * math.cos(theta)


def from_local(origin, east, north, radius_m):
    """(lat, lon) of the point `east`, `north` metres from `origin`."""
    distance = math.hypot(east, north)
    if distance == 0:
        return float(origin[0]), float(origin[1])
    bearing = math.atan2(east, north)
    delta = distance / float(radius_m)
    lat0, lon0 = math.radians(origin[0]), math.radians(origin[1])
    lat1 = math.asin(math.sin(lat0) * math.cos(delta)
                     + math.cos(lat0) * math.sin(delta) * math.cos(bearing))
    lon1 = lon0 + math.atan2(math.sin(bearing) * math.sin(delta) * math.cos(lat0),
                             math.cos(delta) - math.sin(lat0) * math.sin(lat1))
    lon = (math.degrees(lon1) + 540.0) % 360.0 - 180.0
    return math.degrees(lat1), lon


# -- the polygon ----------------------------------------------------------------

def inside(polygon, x, y):
    """Whether (x, y) is inside the closed polygon, by ray casting."""
    hit = False
    count = len(polygon)
    for i in range(count):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % count]
        if (y1 > y) != (y2 > y):
            cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < cross:
                hit = not hit
    return hit


def edge_distance(polygon, x, y):
    """How far (x, y) is from the nearest edge of the polygon."""
    best = float("inf")
    count = len(polygon)
    for i in range(count):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % count]
        dx, dy = x2 - x1, y2 - y1
        length = dx * dx + dy * dy
        t = 0.0 if length == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy)
                                             / length))
        best = min(best, math.hypot(x - (x1 + t * dx), y - (y1 + t * dy)))
    return best


def area(polygon):
    """The polygon's area in square metres (shoelace)."""
    total = 0.0
    count = len(polygon)
    for i in range(count):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % count]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def usable(polygon, x, y):
    """Inside, or on the line to within ON_EDGE_M: the driven line is where
    the edge was seen, not a wall a metre past it."""
    return inside(polygon, x, y) or edge_distance(polygon, x, y) <= ON_EDGE_M


# -- packing ------------------------------------------------------------------

def _lattice(polygon, spacing, turn_deg, shift_x, shift_y):
    """Every point of one triangular lattice that falls in the polygon."""
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
    reach = math.hypot(max(xs) - min(xs), max(ys) - min(ys)) / 2.0 + spacing
    turn = math.radians(turn_deg)
    cos_t, sin_t = math.cos(turn), math.sin(turn)
    row_step = spacing * math.sqrt(3) / 2.0
    rows = int(reach / row_step) + 2
    cols = int(reach / spacing) + 2
    found = []
    for r in range(-rows, rows + 1):
        for c in range(-cols, cols + 1):
            u = c * spacing + (spacing / 2.0 if r % 2 else 0.0) + shift_x
            v = r * row_step + shift_y
            x = cx + u * cos_t - v * sin_t
            y = cy + u * sin_t + v * cos_t
            if usable(polygon, x, y):
                found.append((x, y))
    return found


def _choose(points, polygon, want):
    """The best `want` of a lattice's points: the most compact group, and
    of those the one sitting furthest in from the edge."""
    if len(points) <= want:
        return list(points)
    best = None
    for anchor in points:
        group = sorted(points, key=lambda p: (p[0] - anchor[0]) ** 2
                       + (p[1] - anchor[1]) ** 2)[:want]
        spread = max(math.hypot(p[0] - anchor[0], p[1] - anchor[1]) for p in group)
        margin = min(edge_distance(polygon, p[0], p[1]) for p in group)
        score = (spread - margin * 0.5)
        if best is None or score < best[0]:
            best = (score, group)
    return best[1]


def _greedy(polygon, spacing, want):
    """A second opinion for awkward shapes a lattice fits badly: take the
    point deepest inside, then the next deepest at least a spacing from
    everything taken, and so on."""
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    step = max(2.0, spacing / 8.0)
    candidates = []
    y = min(ys)
    while y <= max(ys):
        x = min(xs)
        while x <= max(xs):
            if usable(polygon, x, y):
                candidates.append((edge_distance(polygon, x, y)
                                   if inside(polygon, x, y) else 0.0, x, y))
            x += step
        y += step
    candidates.sort(reverse=True)
    taken = []
    for _depth, x, y in candidates:
        if all(math.hypot(x - a, y - b) >= spacing - 1e-6 for a, b in taken):
            taken.append((x, y))
            if len(taken) >= want:
                break
    return taken


def plan(polygon, spacing=RIG_SPACING_M, most=MAX_PINS):
    """Up to `most` rig positions inside the polygon, each at least
    `spacing` from every other. [(east, north), ...] on the polygon's own
    plane. The most rigs wins; between layouts with as many, the one that
    keeps its rigs furthest in from the edge.
    """
    polygon = [(float(x), float(y)) for x, y in polygon or []]
    if len(polygon) < 3 or area(polygon) < 1.0 or spacing <= 0:
        return []
    driven = list(polygon)
    # A point every 5 m round a big deposit is a couple of hundred corners,
    # and every one is measured against every candidate. Forty-eight evenly
    # spaced ones follow the same edge to within a metre or two, and keep
    # the planning well under a second on the window's own thread.
    if len(polygon) > MAX_CORNERS:
        step = len(polygon) / float(MAX_CORNERS)
        polygon = [polygon[int(i * step)] for i in range(MAX_CORNERS)]
    best = None

    def consider(points):
        nonlocal best
        if not points:
            return
        margin = min(edge_distance(polygon, x, y) for x, y in points)
        key = (len(points), margin)
        if best is None or key > best[0]:
            best = (key, points)

    for turn in _TURNS:
        for i in range(_SHIFTS):
            for j in range(_SHIFTS):
                found = _lattice(polygon, spacing, turn, spacing * i / _SHIFTS,
                                 spacing * math.sqrt(3) / 2.0 * j / _SHIFTS)
                consider(_choose(found, polygon, most))
    consider(_greedy(polygon, spacing, most))
    # The exact pass has the last word on how many, and is checked against
    # the line as driven. Its places count only when they beat the lattices.
    exact = pack_exact(driven, spacing, most)
    if exact and (best is None or len(exact) > best[0][0]):
        best = ((len(exact), 0.0), exact)
    if best is None:
        # Too small for even one at the spacing asked: one rig, in the middle.
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        middle = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)
        return [middle] if usable(polygon, *middle) else [polygon[0]]
    return best[1]


# -- the exact pass -----------------------------------------------------------

def _far_enough(point, others, spacing):
    limit = (spacing - 1e-6) ** 2
    px, py = point
    for ox, oy in others:
        if (px - ox) ** 2 + (py - oy) ** 2 < limit:
            return False
    return True


def _thin(polygon, corners):
    if len(polygon) <= corners:
        return list(polygon)
    step = len(polygon) / float(corners)
    return [polygon[int(i * step)] for i in range(corners)]


_SWEEPS = (
    lambda p: (p[0], p[1]), lambda p: (p[1], p[0]),
    lambda p: (-p[0], p[1]), lambda p: (p[1], -p[0]),
    lambda p: (p[0], -p[1]), lambda p: (-p[1], p[0]),
    lambda p: (-p[0], -p[1]), lambda p: (-p[1], -p[0]),
)


def pack_exact(polygon, spacing=RIG_SPACING_M, most=MAX_PINS):
    """The most rigs that can be got into the polygon, each at least
    `spacing` from every other and inside the edge as it was driven.

    The lattices in `plan` are neat and miss tight shapes: a deposit 160 m
    by 80 m takes six rigs in two rows of three, and no triangular lattice
    finds them. This tries the ground itself - a fine grid of places, the
    corners of the line among them - taken in eight sweeps from every side,
    then looks for a rig it can swap for two. Every place in the answer has
    been tested against the full line, not the thinned one the lattices
    use, so a pin is never outside the edge the commander drove.

    Returns a list of (east, north); [] when nothing fits.
    """
    full = [(float(x), float(y)) for x, y in polygon or []]
    if len(full) < 3 or area(full) < 1.0 or spacing <= 0:
        return []
    thin = _thin(full, EXACT_CORNERS)
    xs = [p[0] for p in full]
    ys = [p[1] for p in full]
    width, height = max(xs) - min(xs), max(ys) - min(ys)
    step = max(spacing / 6.0, math.sqrt(max(width * height, 1.0) / EXACT_CELLS))
    candidates = list(full[:: max(1, len(full) // EXACT_CORNERS)])
    i = 0
    while min(xs) + i * step <= max(xs) + 1e-9:
        j = 0
        while min(ys) + j * step <= max(ys) + 1e-9:
            candidates.append((min(xs) + i * step, min(ys) + j * step))
            j += 1
        i += 1
    candidates = [c for c in candidates if usable(thin, c[0], c[1])]
    seen = {}

    def fits(point):
        if point not in seen:
            seen[point] = usable(full, point[0], point[1])
        return seen[point]

    def sweep(key):
        taken = []
        for point in sorted(candidates, key=key):
            if len(taken) >= most:
                break
            if _far_enough(point, taken, spacing) and fits(point):
                taken.append(point)
        return taken

    def margin(points):
        return min(edge_distance(full, x, y) for x, y in points) if points else 0.0

    best = max((sweep(key) for key in _SWEEPS), key=lambda pts: (len(pts), margin(pts)))
    depth = sorted(candidates, key=lambda c: -edge_distance(thin, c[0], c[1]))[:400]
    for _ in range(most):
        if len(best) >= most:
            break
        grown = None
        for point in depth:
            if _far_enough(point, best, spacing) and fits(point):
                grown = best + [point]
                break
        if grown is None:
            for k in range(len(best)):
                rest = best[:k] + best[k + 1:]
                free = [c for c in depth if _far_enough(c, rest, spacing) and fits(c)]
                pair = next(((a, b) for n, a in enumerate(free) for b in free[n + 1:]
                             if _far_enough(a, [b], spacing)), None)
                if pair:
                    grown = rest + list(pair)
                    break
        if grown is None:
            break
        best = grown
    return best[:most]


def fit_count(polygon, spacing=RIG_SPACING_M, most=FIT_MOST, pins=None):
    """How many rigs fit in the polygon at this spacing, up to `most`
    (more than the six a Rhino carries: the figure kept with the deposit).
    `pins` is a plan already worked out for it, which can only add to it."""
    return max(len(pack_exact(polygon, spacing, most)), len(pins or ()))


def drive_order(pins, start=(0.0, 0.0)):
    """The pins in the order to drive them: nearest first, then nearest to
    that. Not the shortest tour there is; six stops do not need one."""
    left = list(pins)
    here = start
    order = []
    while left:
        nearest = min(left, key=lambda p: math.hypot(p[0] - here[0], p[1] - here[1]))
        left.remove(nearest)
        order.append(nearest)
        here = nearest
    return order


# -- tracing ------------------------------------------------------------------

class Trace:
    """A deposit's edge, as the Rhino drives it.

    `add` takes each position as it comes from the game. A point is kept
    every TRACE_STEP_M of driving. The loop is closed when the Rhino is back
    within its closing distance (TRACE_CLOSE_M, more on a big body) of the
    start after at least TRACE_MIN_POINTS points
    and TRACE_MIN_PATH_M of driving, or by hand with `close`.
    """

    def __init__(self, lat, lon, radius_m, deposit=None):
        self.origin = (float(lat), float(lon))
        self.radius_m = float(radius_m)
        self.deposit = deposit
        self.points = [(0.0, 0.0)]
        self.path_m = 0.0
        self.close_m = min(TRACE_CLOSE_MAX_M, max(
            TRACE_CLOSE_M, 1.5 * math.radians(STATUS_STEP_DEG) * self.radius_m))
        self.closed = False
        self.too_big = False

    def add(self, lat, lon):
        """Take one position. True when this one closed the loop."""
        if self.closed:
            return False
        x, y = to_local(self.origin, (lat, lon), self.radius_m)
        last = self.points[-1]
        step = math.hypot(x - last[0], y - last[1])
        if step < TRACE_STEP_M:
            return False
        if math.hypot(x, y) > TRACE_MAX_SPAN_M:
            self.too_big = True
            return False
        self.points.append((x, y))
        self.path_m += step
        if (len(self.points) >= TRACE_MIN_POINTS and self.path_m >= TRACE_MIN_PATH_M
                and math.hypot(x, y) <= self.close_m):
            self.closed = True
            return True
        return False

    def close(self):
        """Close it by hand. False when there is not enough of it to be a
        shape yet."""
        if len(self.points) < 3 or area(self.points) < 1.0:
            return False
        self.closed = True
        return True

    def pins(self, spacing=RIG_SPACING_M, start=None, most=MAX_PINS):
        """The rig positions for what was traced, as (lat, lon), in driving
        order from `start` (lat, lon), or from where the trace began."""
        chosen = plan(self.points, spacing, most)
        here = (0.0, 0.0) if start is None else to_local(self.origin, start,
                                                          self.radius_m)
        return [from_local(self.origin, x, y, self.radius_m)
                for x, y in drive_order(chosen, here)]

    def outline(self):
        """The traced edge as (lat, lon) points, for drawing."""
        return [from_local(self.origin, x, y, self.radius_m) for x, y in self.points]


# -- the rig radar (1.10035) ----------------------------------------------------
# A ring of the spacing round every rig that is down, and a verdict on the
# spot the next rig would land on: can it go here, and if not, how far to
# the nearest place it can. All on the flat plane in metres east and north,
# like the rest of this module; the app turns rigs and positions into that.

RADAR_BAND_M = 2.0          # each rig's band runs from 2 m inside the spacing to 2 m outside
RADAR_EDGE_M = RADAR_BAND_M  # within the band's outer half is "nearly too close"
_LEGAL_EPS = 1e-6           # float slack on "at least the spacing away"


def is_legal(point, centres, spacing, polygon=None):
    """Can a rig land on `point`: at least `spacing` from every rig at
    `centres`, and - when the edge of the deposit has been traced and is
    given as `polygon` - on it (`usable`)."""
    x, y = point
    for cx, cy in centres:
        if math.hypot(x - cx, y - cy) < spacing - _LEGAL_EPS:
            return False
    return polygon is None or usable(polygon, x, y)


def _circles_cross(a, b, radius):
    """Where two circles of one radius, centred at a and b, cross."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    apart = math.hypot(dx, dy)
    if apart == 0 or apart > 2.0 * radius:
        return []
    half = math.sqrt(max(0.0, radius * radius - (apart / 2.0) ** 2))
    mx, my = a[0] + dx / 2.0, a[1] + dy / 2.0
    ox, oy = -dy / apart * half, dx / apart * half
    return [(mx + ox, my + oy), (mx - ox, my - oy)]


def _segment_circle(p, q, centre, radius):
    """Where the segment p-q crosses a circle."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    fx, fy = p[0] - centre[0], p[1] - centre[1]
    quad = dx * dx + dy * dy
    if quad == 0:
        return []
    half = fx * dx + fy * dy
    disc = half * half - quad * (fx * fx + fy * fy - radius * radius)
    if disc < 0:
        return []
    root = math.sqrt(disc)
    return [(p[0] + t * dx, p[1] + t * dy)
            for t in ((-half - root) / quad, (-half + root) / quad)
            if 0.0 <= t <= 1.0]


def _segment_foot(p, q, point):
    """The point of the segment p-q nearest `point`."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    quad = dx * dx + dy * dy
    t = 0.0 if quad == 0 else max(0.0, min(1.0, ((point[0] - p[0]) * dx
                                                 + (point[1] - p[1]) * dy) / quad))
    return (p[0] + t * dx, p[1] + t * dy)


def nearest_legal(point, centres, spacing, polygon=None):
    """(x, y) of the nearest spot a rig can land on, or None when there is
    no room anywhere. The point itself when it is legal.

    Exact, not searched for: the nearest legal spot to a point outside the
    legal ground lies on its boundary, and that boundary is arcs of the
    rings and edges of the polygon. The nearest point of each arc is where
    the point projects onto its circle, or one of the places two pieces of
    boundary meet - so those are the candidates, and the nearest legal one
    wins."""
    point = (float(point[0]), float(point[1]))
    centres = [(float(a), float(b)) for a, b in centres]
    spacing = float(spacing)
    if is_legal(point, centres, spacing, polygon):
        return point
    candidates = []
    for cx, cy in centres:
        apart = math.hypot(point[0] - cx, point[1] - cy)
        if apart == 0:
            # Exactly on a rig: every way out is as near as any other.
            candidates += [(cx + spacing * math.sin(math.radians(a)),
                            cy + spacing * math.cos(math.radians(a)))
                           for a in range(0, 360, 45)]
        else:
            candidates.append((cx + (point[0] - cx) * spacing / apart,
                               cy + (point[1] - cy) * spacing / apart))
    for i, first in enumerate(centres):
        for second in centres[i + 1:]:
            candidates += _circles_cross(first, second, spacing)
    if polygon:
        corners = [(float(x), float(y)) for x, y in polygon]
        for k, p in enumerate(corners):
            q = corners[(k + 1) % len(corners)]
            candidates.append(p)
            candidates.append(_segment_foot(p, q, point))
            for centre in centres:
                candidates += _segment_circle(p, q, centre, spacing)
    best = None
    for candidate in candidates:
        if not is_legal(candidate, centres, spacing, corners if polygon else None):
            continue
        apart = math.hypot(candidate[0] - point[0], candidate[1] - point[1])
        if best is None or apart < best[1]:
            best = (candidate, apart)
    return best[0] if best else None


def radar(spot, centres, spacing=RIG_SPACING_M, polygon=None, down=0,
          most=MAX_PINS, edge_m=RADAR_EDGE_M):
    """The rig radar's verdict for a rig landing at `spot` (east, north).

    `centres` are the rigs already down, `spacing` the setting, `polygon`
    the traced edge of the deposit if there is one, `down` how many rigs
    this Rhino has down of the `most` it carries.

    Returns {"state", "text", "need_m", "bearing", "legal", "rings", ...}.
    state is "full" with every rig down, "close" inside a ring (or off the
    traced deposit), "edge" when it can go but is within `edge_m` of a ring,
    and "ok" otherwise. need_m and bearing are how far, and which way, to the
    nearest spot it can go; legal is that spot. Each ring says its own
    state, so the one in the way can be picked out.
    """
    spacing = float(spacing)
    spot = (float(spot[0]), float(spot[1]))
    centres = [(float(a), float(b)) for a, b in centres]
    rings = []
    inside = near = False
    for cx, cy in centres:
        gap = math.hypot(spot[0] - cx, spot[1] - cy) - spacing
        if gap < -_LEGAL_EPS:
            state, inside = "close", True
        elif gap <= edge_m + _LEGAL_EPS:
            state, near = "edge", True
        else:
            state = "ok"
        # The band: red while the Rhino is in it or inside it, green once
        # clear of the rig. The spacing setting is its middle.
        rings.append({"east": cx, "north": cy, "radius": spacing,
                      "inner": max(0.0, spacing - RADAR_BAND_M),
                      "outer": spacing + RADAR_BAND_M,
                      "state": state, "gap_m": gap,
                      "band": "green" if state == "ok" else "red"})
    off_deposit = bool(polygon) and not usable(polygon, spot[0], spot[1])
    out = {"state": "ok", "text": "RIG OK HERE", "need_m": 0.0, "bearing": None,
           "legal": spot, "rings": rings, "spacing": spacing, "spot": spot,
           "down": int(down), "most": int(most),
           "band": "green" if all(r["band"] == "green" for r in rings) else "red"}
    if int(down) >= int(most):
        out.update(state="full", text="ALL %d RIGS DOWN" % int(most),
                   need_m=None, legal=None)
        return out
    if inside or off_deposit:
        out["state"] = "close"
        found = nearest_legal(spot, centres, spacing, polygon)
        if found is None:
            out.update(text="NO ROOM FOR A RIG HERE", need_m=None, legal=None)
            return out
        east, north = found[0] - spot[0], found[1] - spot[1]
        need = math.hypot(east, north)
        bearing = math.degrees(math.atan2(east, north)) % 360.0
        out.update(legal=found, need_m=need, bearing=bearing,
                   text="NEXT RIG: %d m, bearing %03d" % (
                       max(1, int(math.ceil(need - 1e-9))), int(round(bearing)) % 360))
        return out
    if near:
        out["state"] = "edge"
    return out


# -- plans kept with the deposit ------------------------------------------------
# The pins and the traced edge are worth keeping: driving a deposit's edge
# again every visit is the chore the planner exists to remove. One small file,
# a plan per deposit, found again by where you are standing.

import json
import os
import time

PLAN_FILE = "rig_plans.json"
PLAN_KEEP = 300             # plans kept; the oldest go first
PLAN_SAME_M = 60.0          # a trace this close to a kept plan's middle replaces it


def plan_centre(record):
    """The middle of a kept plan as (lat, lon): its pins, else its edge."""
    points = [(p["lat"], p["lon"]) for p in record.get("pins") or []] or \
        [tuple(p) for p in record.get("outline") or []]
    if not points:
        return None
    return (sum(p[0] for p in points) / len(points),
            sum(p[1] for p in points) / len(points))


class PlanBook:
    """Every rig plan the commander has made, on disk."""

    def __init__(self, folder):
        self.path = os.path.join(folder, PLAN_FILE) if folder else ""
        self.plans = []
        self.load()

    def load(self):
        self.plans = []
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        for item in (data.get("plans") if isinstance(data, dict) else None) or []:
            try:
                record = {"system": str(item["system"]).lower(), "body": str(item["body"]).lower(),
                          "radius_m": float(item.get("radius_m") or 0.0),
                          "spacing": float(item["spacing"]),
                          "pins": [{"n": int(p["n"]), "lat": float(p["lat"]), "lon": float(p["lon"])}
                                   for p in item["pins"]],
                          "outline": [(float(a), float(b)) for a, b in item.get("outline") or []],
                          "area_m2": float(item.get("area_m2") or 0.0),
                          "fit": int(item.get("fit") or len(item["pins"])),
                          "deposit": str(item.get("deposit") or ""),
                          "at": float(item.get("at") or 0.0)}
            except (KeyError, TypeError, ValueError):
                continue
            self.plans.append(record)

    def save(self):
        if not self.path:
            return False
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            temp = self.path + ".tmp"
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump({"version": 1, "plans": self.plans[-PLAN_KEEP:]}, handle)
            os.replace(temp, self.path)
            return True
        except OSError:
            return False

    def put(self, record):
        """Keep a plan, in place of any kept for the same ground."""
        record = dict(record, system=str(record["system"]).lower(),
                      body=str(record["body"]).lower(), at=record.get("at") or time.time())
        middle = plan_centre(record)
        radius = float(record.get("radius_m") or 0.0)
        if middle and radius:
            self.plans = [
                p for p in self.plans
                if not (p["system"] == record["system"] and p["body"] == record["body"]
                        and plan_centre(p)
                        and math.hypot(*to_local(middle, plan_centre(p), radius)) <= PLAN_SAME_M)]
        self.plans.append(record)
        self.plans = self.plans[-PLAN_KEEP:]
        return self.save()

    def nearest(self, system, body, lat, lon, radius_m, within_m):
        """The kept plan on this body whose middle is nearest (lat, lon) and
        within `within_m` of it, or None."""
        best = None
        for record in self.plans:
            if record["system"] != str(system).lower() or record["body"] != str(body).lower():
                continue
            middle = plan_centre(record)
            if not middle or not radius_m:
                continue
            away = math.hypot(*to_local((lat, lon), middle, radius_m))
            if away <= within_m and (best is None or away < best[0]):
                best = (away, record)
        return best[1] if best else None

    def link(self, record, deposit_id):
        """Say which deposit a kept plan belongs to."""
        record["deposit"] = str(deposit_id or "")
        return self.save()
