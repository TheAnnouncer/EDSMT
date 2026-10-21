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
# rather than on a third of whatever the extent happens to be. The list runs
# out to planet scale: it used to stop at 25 km, so a view zoomed out over a
# whole body drew a ring every 25 km - fifty-odd rings with their labels
# stacked into one unreadable column.
NICE_STEPS_M = [10, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000, 10000,
                25000, 50000, 100000, 250000, 500000, 1000000, 2500000,
                5000000, 10000000]

# The Rhino's scanner reaches this far. Community field testing puts it at
# 2 km MEASURED FROM THE VEHICLE - contacts drop out of the list by distance
# from where you are, not by distance from the signal - so anything drawing
# this ring must draw it around the commander or it is telling a lie.
SCANNER_RANGE_M = 2000.0

# How far out a view is ever allowed to zoom. Past this the deposits are a
# single dot and the picture stops being navigation.
MAX_MAP_RADIUS_M = 50000.0

# The map opens on the signal being worked, not on the whole body. One body
# can carry mining locations thousands of kilometres apart, and a view sized
# to hold every one of them draws the patch under the wheels as one dot.
#
# SIGNAL_REACH_M: anything this close to the signal belongs to it, whatever
# number it was logged under - a find is where it is, not what it was
# called. A worked signal runs to 7-8 km across (measured: a 4.5 km survey
# border with finds out to 7.7 km). SIGNAL_NAMED_REACH_M: a find logged
# under the signal's own number belongs to it out to here; past it, it is a
# typo or another body's row, not part of the patch. SIGNAL_VIEW_CAP_M: the
# widest the opening view goes; past it a find is an arrow at the edge.
# SIGNAL_VIEW_EMPTY_M: with nothing recorded at the signal yet, the view
# shows the ground the scanner can reach, and a little more.
SIGNAL_REACH_M = 8000.0
SIGNAL_NAMED_REACH_M = 25000.0
# SIGNAL_AT_M: you are AT a logged signal when you are this close to where
# it was logged - the measured survey border was 4.5 km. Drive into one and
# it becomes the signal being worked; be further than SIGNAL_REACH_M from the
# one picked and the views stop pretending you are at it.
SIGNAL_AT_M = 5000.0
SIGNAL_VIEW_CAP_M = 15000.0
SIGNAL_VIEW_FLOOR_M = 250.0
SIGNAL_VIEW_EMPTY_M = SCANNER_RANGE_M * 1.25

# Scroll zoom, in metres of view radius. Absolute, not a multiple of the
# opening view: a multiple could never get closer than a tenth of whatever
# the furthest find dragged the view out to.
ZOOM_CLOSEST_M = 100.0


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


def compass_point(bearing):
    """A bearing as one of the sixteen points: 0 is N, 45 is NE."""
    points = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")
    return points[int((float(bearing) % 360) / 22.5 + 0.5) % 16]


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


def signal_focus(rows, signal="", anchor=None, reach_m=SIGNAL_REACH_M,
                 named_reach_m=SIGNAL_NAMED_REACH_M, near_m=None):
    """Which finds belong to the signal being worked, and where it is.

    Where the signal is, best first:
      1. `anchor` - the spot the signal was logged at (F9), as metres
         east/north of the commander. It is a reading, not a guess.
      2. The finds logged under the signal's number: the middle of them
         with any wild one thrown out, or with only one or two, the one
         nearest the commander - a typo on the far side of the body must
         not become the middle of the map.
      3. The commander. Nothing is known about the signal yet, so the view
         is the ground around the SRV.

    `here` is every row within `reach_m` of that spot whatever number it
    carries, and every row logged under the signal's number within
    `named_reach_m`; `away` is the rest of the body. The map draws `here`
    until it is zoomed out past the signal.

    `near_m`: when the signal's spot is further than this from the
    commander, the commander is not at it - the box still names the last
    signal, or the one being driven to - and the view is the ground around
    the SRV instead, with `far` saying where the signal is. A scope sized to
    hold a signal 40 km away is a scope with nothing on it but one dot.
    """
    wanted = str(signal or "").strip()
    placed = []
    for row in rows or []:
        placed.append((row, to_offset(row.get("range_m"), row.get("bearing"))))

    how = "commander"
    centre = (0.0, 0.0)
    named = []
    if wanted:
        named = [point for row, point in placed
                 if str((row.get("deposit") or {}).get("location") or "")
                 .strip() == wanted]
    if anchor is not None:
        try:
            centre = (float(anchor[0]), float(anchor[1]))
            how = "logged"
        except (TypeError, ValueError, IndexError):
            anchor = None
    if anchor is None and named:
        if len(named) >= 3:
            centre = midpoint(named)
        else:
            centre = min(named, key=lambda p: math.hypot(p[0], p[1]))
        how = "finds"

    far = None
    if near_m is not None and how != "commander":
        apart = math.hypot(centre[0], centre[1])
        if apart > float(near_m):
            far = {"signal": wanted, "range_m": apart,
                   "bearing": (math.degrees(math.atan2(centre[0], centre[1]))
                               + 360.0) % 360.0}
            centre, how, wanted = (0.0, 0.0), "commander", ""

    here, away = [], []
    for row, (east, north) in placed:
        apart = math.hypot(east - centre[0], north - centre[1])
        mine = bool(wanted) and str((row.get("deposit") or {}).get("location")
                                    or "").strip() == wanted
        close = apart <= reach_m or (mine and apart <= named_reach_m)
        (here if close else away).append(row)
    return {"centre": centre, "how": how, "signal": wanted,
            "here": here, "away": away, "far": far}


def group_offscreen(items, sector_deg=20.0):
    """One arrow per direction, not one per find.

    Finds beyond the edge in much the same direction are one destination as
    far as the driver is concerned. Drawn one each, their arrows and
    distances land on top of each other at the rim; grouped, each direction
    gets one arrow, the nearest distance and how many lie that way.
    """
    groups = {}
    for item in items:
        if not item.get("offscreen"):
            continue
        sector = int((float(item.get("view_bearing", item.get("bearing", 0.0)))
                      % 360.0) // sector_deg)
        groups.setdefault(sector, []).append(item)
    out = []
    for sector in sorted(groups):
        members = sorted(groups[sector], key=lambda i: i.get("range_m", 0.0))
        nearest = members[0]
        out.append({"edge": nearest["edge"], "bearing": nearest["bearing"],
                    "range_m": nearest.get("range_m", 0.0),
                    "commodity": nearest.get("commodity", ""),
                    "count": len(members), "items": members})
    return out


def swept_shapes(points, scan_m, centre=None, border_m=None, sides=28,
                 view=None):
    """The ground swept, as shapes to fill, kept inside the survey border.

    Each position the SRV has been is a disc of scanner range. With a border
    set, the survey area is the inside of that circle and nothing painted
    outside it means anything, so:
      - a disc wholly inside the border is returned as ("disc", e, n, r);
      - a disc wholly outside it is dropped;
      - a disc across it is returned as ("poly", [(e, n), ...]) - the disc
        with every point outside the border pulled in onto the border line,
        which is the part of the disc that lies inside.
    Without a border every disc is returned whole. `view` is a second
    circle, ((e, n), radius), for a round scope: nothing is painted past its
    rim either. Metres, east/north.
    """
    try:
        scan = float(scan_m or 0.0)
    except (TypeError, ValueError):
        scan = 0.0
    if scan <= 0:
        return []
    fences = []
    if centre is not None and border_m:
        fences.append((float(centre[0]), float(centre[1]), float(border_m)))
    if view is not None:
        fences.append((float(view[0][0]), float(view[0][1]), float(view[1])))
    out = []
    for point in points or []:
        east, north = float(point[0]), float(point[1])
        inside, outside = True, False
        for fe, fn, radius in fences:
            apart = math.hypot(east - fe, north - fn)
            if apart - scan >= radius:
                outside = True
            if apart + scan > radius:
                inside = False
        if outside:
            continue
        if inside:
            out.append(("disc", east, north, scan))
            continue
        shape = []
        for step in range(sides):
            angle = 2.0 * math.pi * step / sides
            pe, pn = east + scan * math.sin(angle), north + scan * math.cos(angle)
            for fe, fn, radius in fences:
                reach = math.hypot(pe - fe, pn - fn)
                if reach > radius:
                    pe = fe + (pe - fe) * radius / reach
                    pn = fn + (pn - fn) * radius / reach
            shape.append((pe, pn))
        out.append(("poly", shape))
    return out


def boxes_touch(a, b, pad=2.0):
    """Do two (x0, y0, x1, y1) boxes overlap, with a little breathing room?"""
    return not (a[2] + pad <= b[0] or b[2] + pad <= a[0]
                or a[3] + pad <= b[1] or b[3] + pad <= a[1])


def label_spot(candidates, taken, pad=2.0, bounds=None):
    """The first candidate box that overlaps nothing already placed.

    Candidates are tried in order of preference - beside the dot, then the
    other side, then below and above. None if every one is taken: a label
    that can only be printed over another one is left off, and the map says
    how many it left off, rather than printing two into one smudge.
    `bounds` (x0, y0, x1, y1) keeps a label on the canvas.
    """
    for box in candidates:
        if bounds is not None and (box[0] < bounds[0] or box[1] < bounds[1]
                                   or box[2] > bounds[2] or box[3] > bounds[3]):
            continue
        if not any(boxes_touch(box, other, pad) for other in taken):
            return box
    return None


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


# ---------------------------------------------------------------------------
# 1.10035: lines to the nearest deposit, golden groups, the trail on a scope
# ---------------------------------------------------------------------------
# Pure geometry on the items `layout` returns, like everything above: the
# main map and the scope both draw from these, so they cannot disagree.

# A deposit this close is the one you are standing on, not somewhere to go.
LINE_SKIP_M = 20.0

# A golden group: a knot of deposits close enough together to work from one
# parked ship. The radius is a setting; it is only ever held to this range.
GOLDEN_RADIUS_M = 1250.0
GOLDEN_RADIUS_MIN_M = 500.0
GOLDEN_RADIUS_MAX_M = 2500.0
# Rigs a group has to hold to count, and the lower bar used when no group on
# the picture reaches the first one.
GOLDEN_RIGS = 5
GOLDEN_RIGS_FALLBACK = 4
# How many are shown, and how Cr/h is worked out: this long at each spot,
# and the driving between them at this speed. The speed is an assumption
# until one is measured; nothing in the journal says how fast the Rhino went.
GOLDEN_SHOWN = 3
GOLDEN_SPOT_S = 300.0
GOLDEN_DRIVE_KMH = 25.0
# A deposit's rigs are counted up to this many: a Rhino carries six.
RIGS_PER_RHINO = 6
# More sites than this and only the nearest are grouped, so a body with a
# thousand shared finds cannot make the map stall.
GOLDEN_MAX_SITES = 600


def golden_radius(value=None):
    """The group radius in metres, held to 500-2,500. Junk is the default."""
    try:
        radius = float(value)
    except (TypeError, ValueError):
        return GOLDEN_RADIUS_M
    if not math.isfinite(radius):
        return GOLDEN_RADIUS_M
    return max(GOLDEN_RADIUS_MIN_M, min(GOLDEN_RADIUS_MAX_M, radius))


def _is_spent(item):
    return str((item.get("deposit") or {}).get("amount")
               or "").strip().lower() == "depleted"


def _is_live(item):
    return (item.get("east_m") is not None and item.get("north_m") is not None
            and not _is_spent(item))


def _rigs_of(item):
    """A site's rigs, 0 to six. Blank and junk are none."""
    try:
        return max(0, min(RIGS_PER_RHINO,
                          int(float((item.get("deposit") or {}).get("rigs") or 0))))
    except (TypeError, ValueError):
        return 0


def _price_book(prices):
    """{flattened name: price} for every price that is a positive number."""
    book = {}
    for name, value in (prices or {}).items():
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if value > 0 and math.isfinite(value):
            book.setdefault(_flatten(name), value)
    return book


def nearest_lines(items, prices, focus="", skip_m=LINE_SKIP_M):
    """The two lines drawn from you: to the nearest deposit of the same
    commodity as `focus` (solid), and to the nearest deposit of the next
    cheaper commodity in view (dotted).

    `focus` is the commodity of the deposit being driven to, or the one
    marked last; blank means the best-paying commodity in view. "Cheaper" is
    by `prices`, the live table the app already prices everything with: the
    commodity paying the most that is still below the focus. With no price
    for the focus there is no way to say what is cheaper, so no dotted line.
    A deposit closer than `skip_m` is the one you are on and is passed over.

    Returns {"commodity", "same", "cheaper"}; each of the two is None or
    {"item", "range_m", "commodity"}.
    """
    out = {"commodity": "", "same": None, "cheaper": None}
    live = [i for i in items or [] if _is_live(i)
            and str(i.get("commodity") or "").strip()]
    if not live:
        return out
    book = _price_book(prices)
    names = {}
    for item in live:
        names.setdefault(_flatten(item["commodity"]), str(item["commodity"]).strip())
    wanted = _flatten(focus)
    if not wanted:
        best = max(names, key=lambda flat: (book.get(flat, 0.0), flat))
        wanted = best if book.get(best) else ""
    if not wanted:
        return out
    out["commodity"] = names.get(wanted) or str(focus).strip()

    def nearest_of(flat):
        pool = [i for i in live if _flatten(i["commodity"]) == flat
                and float(i.get("range_m") or 0.0) >= skip_m]
        return min(pool, key=lambda i: float(i.get("range_m") or 0.0)) if pool else None

    def entry(item, flat):
        return {"item": item, "range_m": float(item.get("range_m") or 0.0),
                "commodity": names[flat]}

    same = nearest_of(wanted)
    if same is not None:
        out["same"] = entry(same, wanted)
    base = book.get(wanted)
    if base:
        cheaper = sorted(((book[flat], flat) for flat in names
                          if flat != wanted and 0 < book.get(flat, 0.0) < base),
                         reverse=True)
        for _price, flat in cheaper:
            item = nearest_of(flat)
            if item is not None:
                out["cheaper"] = entry(item, flat)
                break
    return out


def _partition(sites, radius, floor):
    """Greedy golden groups. `sites` is [(east, north, rigs)]. Returns
    [(centre index, [member indexes])], richest first: each round takes the
    site with the most rigs within `radius` of it among the sites not yet
    taken (the tighter one on a tie), and its neighbours leave the pool.
    Stops when the best left holds fewer than `floor` rigs, because every
    later one can only hold fewer."""
    count = len(sites)
    near = [[(i, 0.0)] for i in range(count)]
    for i in range(count):
        xi, yi = sites[i][0], sites[i][1]
        for j in range(i + 1, count):
            apart = math.hypot(sites[j][0] - xi, sites[j][1] - yi)
            if apart <= radius:
                near[i].append((j, apart))
                near[j].append((i, apart))
    left = set(range(count))
    groups = []
    while left:
        best = None
        for i in sorted(left):
            members = [(j, apart) for j, apart in near[i] if j in left]
            rigs = sum(sites[j][2] for j, _apart in members)
            key = (-rigs, max(apart for _j, apart in members), i)
            if best is None or key < best[0]:
                best = (key, i, members, rigs)
        if best[3] < floor:
            break
        groups.append((best[1], [j for j, _apart in best[2]]))
        left -= {j for j, _apart in best[2]}
    return groups


_GOLDEN_MEMO = {"key": None, "groups": None}


def _site_key(item):
    deposit = item.get("deposit") or {}
    ident = str(deposit.get("id") or "").strip()
    if ident:
        return ident
    lat, lon = deposit.get("lat"), deposit.get("lon")
    if lat not in (None, "") and lon not in (None, ""):
        return "%s,%s" % (lat, lon)
    return ""


def golden_groups(items, prices, radius_m=GOLDEN_RADIUS_M, start=(0.0, 0.0),
                  limit=GOLDEN_SHOWN, speed_kmh=GOLDEN_DRIVE_KMH,
                  spot_s=GOLDEN_SPOT_S):
    """The best golden groups on the picture: up to `limit` knots of intact
    deposits with at least five rigs' worth within `radius_m` of one of
    them (four, when no group reaches five), listed most rigs first.

    Only live deposits count, a site's rigs are capped at six, and a site
    belongs to one group. Each group says what it is worth at `prices`
    (rigs x 1 t x price, an estimate) and what that comes to an hour:
    `spot_s` at every deposit plus the drive from `start` through them all
    at `speed_kmh`. Of the groups that qualify the `limit` with the best
    Cr/h are kept (the most rigs, where nothing is priced), then listed most
    rigs first.

    The grouping is remembered while the same deposits are on the picture,
    because the scope asks ten times a second; the values and times, which
    move with you, are worked out each time.
    """
    radius = golden_radius(radius_m)
    live = [i for i in items or [] if _is_live(i) and _rigs_of(i) > 0]
    if len(live) > GOLDEN_MAX_SITES:
        live = sorted(live, key=lambda i: float(i.get("range_m") or 0.0))[:GOLDEN_MAX_SITES]
    if not live:
        return []
    keys = [_site_key(i) for i in live]
    named = all(keys) and len(set(keys)) == len(keys)
    ids = keys if named else list(range(len(live)))
    by_id = dict(zip(ids, live))
    # What the grouping depends on: who is there, their rigs, and where they
    # are to each other. Not where they are to you - that moves every tick -
    # so positions are taken from one site and rounded to the metre.
    signature = None
    if named:
        anchor = min(zip(keys, live), key=lambda pair: pair[0])[1]
        ae, an = anchor["east_m"], anchor["north_m"]
        signature = (round(radius, 1), tuple(sorted(
            (k, _rigs_of(i), round(i["east_m"] - ae), round(i["north_m"] - an))
            for k, i in zip(keys, live))))
    groups = _GOLDEN_MEMO["groups"] if (
        signature is not None and _GOLDEN_MEMO["key"] == signature) else None
    if groups is None:
        sites = [(i["east_m"], i["north_m"], _rigs_of(i)) for i in live]
        groups = [(ids[c], [ids[m] for m in members])
                  for c, members in _partition(sites, radius, GOLDEN_RIGS_FALLBACK)]
        if signature is not None:
            _GOLDEN_MEMO["key"], _GOLDEN_MEMO["groups"] = signature, groups

    totals = [sum(_rigs_of(by_id[m]) for m in members) for _c, members in groups]
    floor = GOLDEN_RIGS if any(t >= GOLDEN_RIGS for t in totals) else GOLDEN_RIGS_FALLBACK
    per_second = max(0.1, float(speed_kmh) / 3.6)
    start = (float(start[0]), float(start[1]))
    found = []
    for (centre_id, member_ids), rigs in zip(groups, totals):
        if rigs < floor:
            continue
        members = [by_id[m] for m in member_ids]
        centre = by_id[centre_id]
        worth = value_of(members, prices)
        route = drive_route(members, prices, start=start)
        seconds = float(spot_s) * len(members) + route["total_m"] / per_second
        rate = (worth["credits"] * 3600.0 / seconds
                if worth["credits"] > 0 and seconds > 0 else None)
        away, bearing = to_polar(centre["east_m"] - start[0],
                                 centre["north_m"] - start[1])
        found.append({
            "centre": centre, "east_m": centre["east_m"], "north_m": centre["north_m"],
            "radius_m": radius, "items": members, "rigs": rigs,
            "count": len(members), "credits": worth["credits"],
            "unpriced": worth["unpriced"], "drive_m": route["total_m"],
            "seconds": seconds, "cr_per_h": rate,
            "range_m": away, "bearing": bearing,
            "commodities": sorted({str(m["commodity"]).strip() for m in members
                                   if str(m.get("commodity") or "").strip()}),
        })
    if any(g["cr_per_h"] for g in found):
        found.sort(key=lambda g: (-(g["cr_per_h"] or 0.0), -g["rigs"], g["range_m"]))
    else:
        found.sort(key=lambda g: (-g["rigs"], g["range_m"]))
    found = found[:max(0, int(limit))]
    found.sort(key=lambda g: (-g["rigs"], -(g["cr_per_h"] or 0.0), g["range_m"]))
    for number, group in enumerate(found, 1):
        group["n"] = number
    return found


# -- drawing helpers for a round scope -----------------------------------------

def circle_points(east, north, radius, sides=72):
    """A closed ring of points round (east, north)."""
    return [(east + radius * math.sin(2.0 * math.pi * k / sides),
             north + radius * math.cos(2.0 * math.pi * k / sides))
            for k in range(sides + 1)]


def _circle_cross(a, b, centre, radius):
    """Where the segment a-b crosses the circle, or None."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    fx, fy = a[0] - centre[0], a[1] - centre[1]
    quad = dx * dx + dy * dy
    if quad == 0:
        return None
    half = fx * dx + fy * dy
    disc = half * half - quad * (fx * fx + fy * fy - radius * radius)
    if disc < 0:
        return None
    root = math.sqrt(disc)
    for t in ((-half - root) / quad, (-half + root) / quad):
        if 0.0 <= t <= 1.0:
            return (a[0] + t * dx, a[1] + t * dy)
    return None


def clip_polyline(points, centre, radius):
    """The parts of a polyline that lie inside a circle, as a list of runs
    of points. A segment that crosses the rim is cut at it. For a scope,
    which is round: a line past its rim is not on it."""
    runs, run = [], []
    inside_before = None
    previous = None
    r2 = float(radius) ** 2
    for point in points or []:
        inside = (point[0] - centre[0]) ** 2 + (point[1] - centre[1]) ** 2 <= r2
        if previous is not None and inside != inside_before:
            cross = _circle_cross(previous, point, centre, radius)
            if inside:
                run = [cross] if cross else []
                run.append(point)
            else:
                if cross:
                    run.append(cross)
                if len(run) >= 2:
                    runs.append(run)
                run = []
        elif inside:
            run.append(point)
        previous, inside_before = point, inside
    if len(run) >= 2:
        runs.append(run)
    return runs


def thin_points(points, gap_m):
    """Keep the first point, then each one at least `gap_m` from the last
    kept, and the final point. How many discs a scope paints for a trail."""
    points = list(points or [])
    if len(points) <= 2 or gap_m <= 0:
        return points
    kept = [points[0]]
    for point in points[1:-1]:
        if math.hypot(point[0] - kept[-1][0], point[1] - kept[-1][1]) >= gap_m:
            kept.append(point)
    kept.append(points[-1])
    return kept


def focus_commodity(items, target_id="", last=""):
    """The commodity the map's lines are for: that of the deposit being
    driven to when it is on the picture, otherwise the one marked last,
    otherwise "" (nearest_lines then takes the best paying in view)."""
    wanted = str(target_id or "").strip()
    if wanted:
        for item in items or []:
            if str((item.get("deposit") or {}).get("id") or "") == wanted \
                    and str(item.get("commodity") or "").strip():
                return str(item["commodity"]).strip()
    return str(last or "").strip()
