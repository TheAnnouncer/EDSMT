"""
The plan view: a top-down picture of what is around you, drawn to scale.

Centred on the SRV, not on a marker the commander had to stop and place.
North is up, so a deposit drawn up and to the left is up and to the left out
of the canopy, and the ring labels say how far in metres.

Only the maths lives here - what to put where, given a viewport. That means
the layout can be checked without ever opening a window, which is the only
way any of this gets tested.

The in-game radar overlay draws from these same functions. It centres on a
mining location signal rather than on the SRV, which is a different origin
and nothing else, so `layout` takes one instead of growing a second copy of
the geometry that would drift away from this one within a week.
"""

import math

# Rings land on numbers a person can hold in their head while driving,
# rather than on a third of whatever the extent happens to be.
NICE_STEPS_M = [10, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000, 10000, 25000]

# The Rhino's scanner reaches this far. Community field testing puts it at
# 2 km MEASURED FROM THE VEHICLE - contacts drop out of the list by distance
# from where you are, not by distance from the signal - so anything drawing
# this ring must draw it around the commander or it is telling a lie.
SCANNER_RANGE_M = 2000.0

# How far out a view is ever allowed to zoom. Past this the deposits are a
# single dot and the picture stops being navigation.
MAX_MAP_RADIUS_M = 50000.0


def to_offset(range_m, bearing_deg):
    """A range and bearing as metres east and north. Junk reads as origin.

    Every row that arrives here has come off a CSV at some point, so a blank
    or a string is the normal case rather than the exceptional one.
    """
    try:
        metres = float(range_m or 0.0)
    except (TypeError, ValueError):
        metres = 0.0
    try:
        theta = math.radians(float(bearing_deg or 0.0))
    except (TypeError, ValueError):
        theta = 0.0
    return metres * math.sin(theta), metres * math.cos(theta)


def to_polar(east_m, north_m):
    """The other way: metres east/north back to (range, bearing)."""
    return (math.hypot(east_m, north_m),
            math.degrees(math.atan2(east_m, north_m)) % 360.0)


def centroid(points):
    """The middle of a handful of offsets. (0, 0) for nothing at all."""
    points = list(points)
    if not points:
        return 0.0, 0.0
    return (sum(p[0] for p in points) / len(points),
            sum(p[1] for p in points) / len(points))


def _median(values):
    values = sorted(values)
    if not values:
        return 0.0
    middle = len(values) // 2
    if len(values) % 2:
        return float(values[middle])
    return (float(values[middle - 1]) + float(values[middle])) / 2.0


# How far from the median a deposit may sit before it stops counting as
# part of the same signal. Generous on purpose: a real mining location is
# a few kilometres across, so this only ever catches something that is
# plainly not in it.
OUTLIER_FACTOR = 6.0
OUTLIER_FLOOR_M = 2000.0


def midpoint(points):
    """The middle of a signal's deposits, with one wild one thrown out.

    The mean is the right centre for a knot of deposits and the wrong one
    the moment a single bad row appears. Log one find on the far side of
    the body - a typo, a stale row, a deposit that belongs to another
    signal - and the mean drags the centre of the map hundreds of
    kilometres from the patch you are standing in. Every real deposit then
    falls outside the scope, pins to the edge, and the overlay goes blank
    while reporting no error whatsoever.

    So: find the median, which one outlier cannot move; measure how spread
    out the deposits are around it; discard anything absurdly beyond that;
    and take the mean of what is left. A normal signal loses nothing and
    keeps exactly the centre it always had.
    """
    points = list(points)
    if len(points) < 3:
        return centroid(points)

    heart = (_median([p[0] for p in points]), _median([p[1] for p in points]))
    spread = _median([math.hypot(e - heart[0], n - heart[1])
                      for e, n in points])
    limit = max(OUTLIER_FLOOR_M, spread * OUTLIER_FACTOR)
    kept = [p for p in points
            if math.hypot(p[0] - heart[0], p[1] - heart[1]) <= limit]
    return centroid(kept or points)


def ring_step(extent_m, wanted=4):
    extent_m = max(1.0, float(extent_m))
    target = extent_m / max(1, wanted)
    for step in NICE_STEPS_M:
        if step >= target:
            return step
    return NICE_STEPS_M[-1]


class Viewport:
    """Maps metres around the view centre onto canvas pixels.

    One object because the same transform is needed for drawing, for
    hit-testing a click and for the tests, and three copies would drift
    apart inside a week.
    """

    def __init__(self, width, height, extent_m, margin=30, pan=(0.0, 0.0)):
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self.margin = margin
        self.extent_m = max(1.0, float(extent_m))
        usable = max(1, min(self.width, self.height) - margin * 2)
        self.scale = (usable / 2.0) / self.extent_m       # pixels per metre
        # How far the view has been dragged from "you in the middle", in
        # pixels. Panning shifts where the transform puts its origin and
        # nothing else, so drawing, clicking and the tests all stay in
        # agreement without any of them knowing panning exists.
        self.pan_x, self.pan_y = float(pan[0]), float(pan[1])

    @property
    def centre(self):
        return self.width / 2.0 + self.pan_x, self.height / 2.0 + self.pan_y

    @property
    def panned(self):
        return abs(self.pan_x) > 0.5 or abs(self.pan_y) > 0.5

    def to_canvas(self, east_m, north_m):
        cx, cy = self.centre
        return cx + east_m * self.scale, cy - north_m * self.scale

    def to_metres(self, x, y):
        cx, cy = self.centre
        return (x - cx) / self.scale, (cy - y) / self.scale

    def radius_px(self, metres):
        return float(metres) * self.scale

    def visible(self, east_m, north_m, slack=14):
        x, y = self.to_canvas(east_m, north_m)
        return (-slack <= x <= self.width + slack
                and -slack <= y <= self.height + slack)

    def within(self, east_m, north_m):
        """Inside the outer ring.

        A round scope clips in metres, not in pixels: on the overlay the
        corners of the window are header and footer text, so a deposit that
        is technically on the canvas but outside the outermost ring has to
        count as off the edge or it is drawn over the readout.
        """
        return math.hypot(east_m, north_m) <= self.extent_m

    def edge_toward(self, east_m, north_m, inset=18, reach=None):
        """Where to draw an arrow for something beyond the edge.

        `reach` overrides how far out the arrow sits, so a round scope can
        pin its arrows onto the outer ring rather than onto the corners of
        a rectangle nobody drew.
        """
        cx, cy = self.centre
        angle = math.atan2(east_m, north_m)
        if reach is None:
            reach = min(cx, cy) - inset
        return cx + math.sin(angle) * reach, cy - math.cos(angle) * reach


def extent_for(points, floor_m=150.0, headroom=1.3, cap_m=None):
    """How far the view must reach to hold everything comfortably.

    `cap_m` stops one deposit logged on the far side of the body dragging
    the whole picture out to a radius where the patch you are working is a
    single pixel. Past the cap the far one is pinned to the edge instead.
    """
    furthest = 0.0
    for east, north in points:
        furthest = max(furthest, math.hypot(east, north))
    extent = max(floor_m, furthest * headroom)
    if cap_m:
        extent = min(extent, max(float(cap_m), floor_m))
    return extent


def site_centre(rows, location=None):
    """Where the mining location signal is, worked out from its deposits.

    Nobody should have to stop and drop a marker before the radar will
    centre on anything. The deposits already recorded in a signal say where
    that signal is, so nothing has to be placed by hand: this takes the
    middle of them.

    `location` picks one signal by name. Without it the busiest signal on
    the body wins, and of equally busy ones the nearest - which is the one
    you are standing in.
    """
    groups = {}
    for row in rows or []:
        deposit = row.get("deposit", {}) or {}
        key = str(deposit.get("location") or "").strip()
        groups.setdefault(key, []).append(
            to_offset(row.get("range_m"), row.get("bearing")))

    if not groups:
        return {"east_m": 0.0, "north_m": 0.0, "label": "",
                "location": "", "count": 0}

    wanted = str(location or "").strip()
    if wanted and wanted in groups:
        key = wanted
    else:
        def rank(pair):
            name, points = pair
            return (-len(points), min(math.hypot(e, n) for e, n in points))
        key = sorted(groups.items(), key=rank)[0][0]

    east, north = midpoint(groups[key])
    return {"east_m": east, "north_m": north,
            "label": ("LOCATION %s" % key) if key else "SITE",
            "location": key, "count": len(groups[key])}


def marker_radius(rigs, base=5.0, per_rig=1.7, cap=17.0):
    """Bigger dot, more rigs. Unknown rig counts get the base size."""
    try:
        count = max(1, int(float(rigs)))
    except (TypeError, ValueError):
        return base
    return min(cap, base + per_rig * (count - 1))


def hit_test(items, x, y, tolerance=7.0):
    """Which marker is under the pointer. None if the click missed."""
    best, best_gap = None, None
    for item in items:
        reach = item.get("radius", 6.0) + tolerance
        gap = math.hypot(item["x"] - x, item["y"] - y)
        if gap <= reach and (best_gap is None or gap < best_gap):
            best, best_gap = item, gap
    return best


def layout(rows, viewport, heading=0.0, origin=(0.0, 0.0), clip="box"):
    """Position everything for drawing.

    `rows` are what Survey.near returns - each already carrying its range and
    bearing from the commander - so this does no geometry of its own beyond
    turning that into pixels.

    `origin` is where the middle of the view sits, in metres east/north of
    the commander. (0, 0) is the plan view's "you in the middle". Handing it
    a mining location signal instead gives the site-centred radar, and the
    commander then becomes a thing on the map like everything else - which
    is why `commander` comes back in the result.

    `clip` is "box" for a rectangular canvas and "circle" for a round scope,
    where anything outside the outermost ring counts as off the edge.

    east_m/north_m on each item are measured FROM THE VIEW CENTRE, so with
    the default origin they mean exactly what they always did. range_m and
    bearing stay measured from the commander, because those are the numbers
    you drive by; view_range_m and view_bearing are the same pair measured
    from the centre, which is what decides where the mark lands.
    """
    origin_e, origin_n = float(origin[0]), float(origin[1])
    circular = str(clip) == "circle"
    # On a round scope the arrows belong on the outer ring, just inside it.
    reach = viewport.radius_px(viewport.extent_m) - 6.0 if circular else None

    def place(east, north):
        off = (not viewport.within(east, north)) if circular \
            else (not viewport.visible(east, north))
        return off, viewport.edge_toward(east, north, reach=reach)

    items = []
    for row in rows:
        east, north = to_offset(row.get("range_m"), row.get("bearing"))
        east, north = east - origin_e, north - origin_n
        x, y = viewport.to_canvas(east, north)
        view_range, view_bearing = to_polar(east, north)
        offscreen, edge = place(east, north)
        deposit = row.get("deposit", {})
        items.append({
            "id": deposit.get("id", ""),
            "deposit": deposit,
            "east_m": east, "north_m": north,
            "x": x, "y": y,
            "radius": marker_radius(deposit.get("rigs")),
            "commodity": str(deposit.get("commodity") or ""),
            "range_m": float(row.get("range_m") or 0.0),
            "bearing": float(row.get("bearing") or 0.0),
            "view_range_m": view_range, "view_bearing": view_bearing,
            "offscreen": offscreen,
            "edge": edge,
        })

    # The commander, in the same coordinates as everything else.
    cmdr_e, cmdr_n = -origin_e, -origin_n
    cmdr_x, cmdr_y = viewport.to_canvas(cmdr_e, cmdr_n)
    cmdr_off, cmdr_edge = place(cmdr_e, cmdr_n)
    cmdr_range, cmdr_bearing = to_polar(cmdr_e, cmdr_n)
    commander = {"east_m": cmdr_e, "north_m": cmdr_n,
                 "x": cmdr_x, "y": cmdr_y,
                 "view_range_m": cmdr_range, "view_bearing": cmdr_bearing,
                 "offscreen": cmdr_off, "edge": cmdr_edge}

    rings, step = [], ring_step(viewport.extent_m)
    distance = step
    while distance <= viewport.extent_m * 1.02:
        rings.append({"metres": distance, "radius": viewport.radius_px(distance)})
        distance += step

    return {"items": items, "rings": rings, "ring_step_m": step,
            "extent_m": viewport.extent_m, "heading": float(heading or 0.0),
            "origin": (origin_e, origin_n), "commander": commander}


def total_rigs(items):
    """How many rigs are on this picture. Blank rig counts count as none."""
    total = 0
    for item in items:
        try:
            total += max(0, int(float((item.get("deposit") or {}).get("rigs") or 0)))
        except (TypeError, ValueError):
            continue
    return total


def next_target(items):
    """The nearest deposit still worth driving to.

    Anything marked Depleted is skipped: it is still drawn, because it is
    still a fact about the body, but it is not where you are going next.
    """
    live = [item for item in items
            if str((item.get("deposit") or {}).get("amount") or "").strip().lower()
            != "depleted"]
    if not live:
        return None
    return min(live, key=lambda item: float(item.get("range_m") or 0.0))


def best_patch(items, radius_m=350.0):
    """The tightest richest knot of deposits on the picture, or None.

    The surface equivalent of overlapping hotspots. The grouping itself is
    edonline.cluster_deposits - the same rule the site ranking and the
    community search already use - rather than a second implementation here
    that would slowly disagree with it. Imported where it is used so this
    module still loads on its own.
    """
    placed = [item for item in items if item.get("range_m") is not None]
    if len(placed) < 2:
        return None
    try:
        import edonline as EDO
    except Exception:
        return None

    rows = [{"direction": item["bearing"],
             "distance": float(item["range_m"]) / 1000.0} for item in placed]
    best, best_key = None, None
    for group in EDO.cluster_deposits(rows, radius_km=float(radius_m) / 1000.0):
        if len(group) < 2:
            continue
        members = [placed[n] for n in group]
        spread = max(math.hypot(a["east_m"] - b["east_m"],
                                a["north_m"] - b["north_m"])
                     for a in members for b in members)
        kinds = {m["commodity"].strip().lower() for m in members if m["commodity"].strip()}
        key = (-total_rigs(members), -len(kinds), spread)
        if best_key is None or key < best_key:
            best, best_key = members, key

    if not best:
        return None
    mid_x = sum(m["x"] for m in best) / len(best)
    mid_y = sum(m["y"] for m in best) / len(best)
    return {
        "items": best,
        "x": mid_x, "y": mid_y,
        "radius": max(math.hypot(m["x"] - mid_x, m["y"] - mid_y) + m["radius"]
                      for m in best),
        "rigs": total_rigs(best),
        "count": len(best),
        "commodities": sorted({m["commodity"] for m in best if m["commodity"]}),
    }



# ---------------------------------------------------------------------------
# What a patch is worth, and the order to drive it in
# ---------------------------------------------------------------------------
# A patch is not the number of dots on it.
# Dots are not the thing anybody is out there for. Six rigs of Aluminium and
# six rigs of Void Opals draw the same picture and are not the same trip, and
# nothing in Elite Dangerous tells you the difference on the ground.
#
# The prices come from the caller rather than from here: the app has the
# published table AND whatever the community has actually seen at a market
# this week, and a live price beats a published one. planview.py stays a
# geometry module and does not grow a price list of its own to disagree with.

# The Rhino brings back one tonne per rig. Everything below is that times a
# price, and it is stated as an estimate everywhere it is shown, because the
# price is the part nobody can promise.
TONNES_PER_RIG = 1.0


def _flatten(text):
    """Case, punctuation and accents off, so two spellings can be compared."""
    import unicodedata
    raw = unicodedata.normalize("NFKD", str(text or ""))
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return "".join(c for c in raw.lower() if c.isalnum())


def deposit_value(item, prices):
    """What one deposit is worth, in credits. 0 when nothing prices it.

    Zero and not None: a deposit of something nobody has priced is worth an
    unknown amount, and an unknown amount added to a total has to be nothing
    rather than an invented number. The caller is the one that knows to say
    "and two more nobody has priced".
    """
    deposit = item.get("deposit") or {}
    if str(deposit.get("amount") or "").strip().lower() == "depleted":
        return 0
    name = str(item.get("commodity") or deposit.get("commodity") or "").strip()
    if not name:
        return 0
    try:
        rigs = max(0, int(float(deposit.get("rigs") or 0)))
    except (TypeError, ValueError):
        rigs = 0
    if not rigs:
        return 0
    lookup = prices or {}
    price = lookup.get(name)
    if price is None:
        # Fold the name the way the rest of the app does, so Bastnasite,
        # Bastn\u00e4site and BASTNASITE all find the same price. The diacritic
        # has to be stripped, not just the case: "\u00e4" is alphanumeric, so a
        # plain isalnum() filter keeps it and the two spellings never meet.
        # Done against the caller's own keys rather than by importing the
        # commodity table, which would make a geometry module depend on it.
        flat = _flatten(name)
        for key, value in lookup.items():
            if _flatten(key) == flat:
                price = value
                break
    try:
        return int(round(rigs * TONNES_PER_RIG * float(price or 0)))
    except (TypeError, ValueError):
        return 0


def value_of(items, prices):
    """What the whole picture is worth, and how much of it is guesswork.

    Returns credits, the number of deposits that priced, and the number that
    did not - so a total can be shown honestly as "about 4.2M, and 3 more
    nobody has priced" instead of quietly under-reporting.
    """
    credits = priced = unpriced = 0
    for item in items:
        deposit = item.get("deposit") or {}
        if str(deposit.get("amount") or "").strip().lower() == "depleted":
            continue
        worth = deposit_value(item, prices)
        if worth > 0:
            credits += worth
            priced += 1
        else:
            unpriced += 1
    return {"credits": credits, "priced": priced, "unpriced": unpriced}


def value_patch(items, prices, radius_m=350.0):
    """The most VALUABLE knot on the picture, which is rarely the biggest.

    best_patch answers "where are the most rigs". This answers "where is the
    most money", and the two disagree exactly when it matters - a tight pair
    of Void Opals against a wide spread of Bauxite. Both are offered rather
    than one replacing the other: on a single-commodity body they are the
    same answer, and the rig count is the one people already trust.

    Same grouping rule as best_patch, for the same reason - edonline's
    cluster_deposits is what the site ranking and the community search use,
    and a second implementation here would slowly come to disagree with it.
    """
    placed = [item for item in items if item.get("range_m") is not None
              and str((item.get("deposit") or {}).get("amount")
                      or "").strip().lower() != "depleted"]
    if len(placed) < 2:
        return None
    try:
        import edonline as EDO
    except Exception:
        return None

    rows = [{"direction": item["bearing"],
             "distance": float(item["range_m"]) / 1000.0} for item in placed]
    best, best_worth = None, 0
    for group in EDO.cluster_deposits(rows, radius_km=float(radius_m) / 1000.0):
        if len(group) < 2:
            continue
        members = [placed[n] for n in group]
        worth = value_of(members, prices)["credits"]
        if worth > best_worth:
            best, best_worth = members, worth
    if not best:
        return None
    mid_x = sum(m["x"] for m in best) / len(best)
    mid_y = sum(m["y"] for m in best) / len(best)
    return {
        "items": best,
        "x": mid_x, "y": mid_y,
        "radius": max(math.hypot(m["x"] - mid_x, m["y"] - mid_y) + m["radius"]
                      for m in best),
        "rigs": total_rigs(best),
        "count": len(best),
        "credits": best_worth,
        "commodities": sorted({m["commodity"] for m in best if m["commodity"]}),
    }


def drive_route(items, prices=None, start=(0.0, 0.0)):
    """The order to drive them in, and how far that is in total.

    Nearest-next from where you are. It is not the shortest possible route -
    that is the travelling salesman and nobody needs it solved to two metres
    in an SRV - but it is the order a person would drive anyway, and having
    it numbered on the map means not stopping at every dot to work out which
    is closest.

    Worked-out deposits are left out of the route and stay on the map. The
    route is what to drive; the map is what is there.
    """
    live = [item for item in items
            if item.get("east_m") is not None and item.get("north_m") is not None
            and str((item.get("deposit") or {}).get("amount")
                    or "").strip().lower() != "depleted"]
    order, total, here = [], 0.0, (float(start[0]), float(start[1]))
    remaining = list(live)
    while remaining:
        nearest = min(remaining, key=lambda item: math.hypot(
            item["east_m"] - here[0], item["north_m"] - here[1]))
        leg = math.hypot(nearest["east_m"] - here[0],
                         nearest["north_m"] - here[1])
        total += leg
        here = (nearest["east_m"], nearest["north_m"])
        remaining.remove(nearest)
        order.append({"stop": len(order) + 1, "item": nearest, "leg_m": leg,
                      "run_m": total,
                      "credits": deposit_value(nearest, prices or {})})
    return {"stops": order, "total_m": total,
            "credits": sum(stop["credits"] for stop in order)}

def arrow_points(x, y, heading_deg, size=12.0):
    """A chevron pointing where the commander is facing."""
    theta = math.radians(float(heading_deg))
    def at(distance, offset):
        angle = theta + offset
        return (x + distance * math.sin(angle), y - distance * math.cos(angle))
    return [at(size, 0.0), at(size * 0.72, math.radians(140)),
            (x, y), at(size * 0.72, math.radians(-140))]
