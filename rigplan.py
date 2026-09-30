"""Where to put the rigs on a deposit - the rig planner (beta).

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
    if best is None:
        # Too small for even one at the spacing asked: one rig, in the middle.
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        middle = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)
        return [middle] if usable(polygon, *middle) else [polygon[0]]
    return best[1]


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
