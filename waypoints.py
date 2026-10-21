"""Guided survey: numbered waypoints to drive, one at a time.

The survey area already has a centre and a border. This turns them into a
list of places to drive to: the centre first, then rings going outward, no
two rings and no two waypoints on a ring more than about two kilometres
apart, so the scanner's reach overlaps from one waypoint to the next. Ground
the scanner has already swept is left out. Only one waypoint is shown at a
time ("WP 3/12"); reaching it moves on to the next, and the commander can
step forward, step back or pause with a key.

Pure geometry and a small file on disk, no window and no game, so all of it
can be tested from a list of positions. Progress is kept per body, so it is
there again after a restart.
"""

import os
import json
import math
import time

import survey as SV

# No two rings, and no two waypoints on a ring, further apart than this.
SPACING_M = 2000.0
# Arrival: within this of a waypoint counts as being there. A setting, held
# to the range below.
ARRIVE_M = 250.0
ARRIVE_MIN_M = 50.0
ARRIVE_MAX_M = 1000.0
# A waypoint counts as swept only when the ground round it is too, to this
# distance: standing at the centre sweeps the centre, not the ring beyond.
SWEPT_MARGIN_M = 500.0
# More than this and the outer rings are left off: a border that big is not
# a survey anybody drives in one go.
MAX_WAYPOINTS = 600
FILE_NAME = "waypoints.json"
FILE_VERSION = 1


def arrive_radius(value=None):
    """The arrival radius in metres from a setting, kept to something sane."""
    try:
        metres = float(value)
    except (TypeError, ValueError):
        return ARRIVE_M
    if not math.isfinite(metres):
        return ARRIVE_M
    return max(ARRIVE_MIN_M, min(ARRIVE_MAX_M, metres))


def ring_radii(border_m, scan_m, step_m=SPACING_M):
    """Radii of the rings to drive, nearest first. The centre covers one
    scan; each ring out covers to its radius plus one scan; the last is
    pulled in so its sweep ends on the border."""
    try:
        border, scan = float(border_m), float(scan_m)
        step = max(100.0, min(float(step_m), scan if scan > 0 else float(step_m)))
    except (TypeError, ValueError):
        return []
    if not (math.isfinite(border) and math.isfinite(scan)) or border <= 0 or scan <= 0:
        return []
    radii, reach, radius = [], scan, 0.0
    while reach < border and len(radii) < 500:
        radius += step
        if radius + scan >= border:
            radius = max(border - scan, radii[-1] if radii else 0.0, 1.0)
        radii.append(radius)
        reach = radius + scan
    return radii


def build(centre, border_m, radius_m, scan_m, swept=None, step_m=SPACING_M,
          start_bearing=0.0, margin_m=SWEPT_MARGIN_M):
    """The waypoints for an area: [{"n", "lat", "lon", "ring", "radius_m",
    "bearing"}, ...], the centre first, then the rings outward. `swept` is
    a function (lat, lon, margin_m) -> bool; a waypoint it calls swept is
    left out and the rest are numbered on from 1. Each ring starts where the
    one before it ended, so the drive is a spiral and not a zigzag."""
    if not centre or not radius_m or not border_m:
        return []
    try:
        clat, clon = float(centre[0]), float(centre[1])
        radius = float(radius_m)
    except (TypeError, ValueError, IndexError):
        return []
    if radius <= 0 or not (math.isfinite(clat) and math.isfinite(clon)):
        return []
    step = max(100.0, min(float(step_m), float(scan_m)))
    wanted = [(0, 0.0, 0.0)]
    bearing = float(start_bearing or 0.0) % 360.0
    for index, ring in enumerate(ring_radii(border_m, scan_m, step), start=1):
        count = max(3, int(math.ceil(2.0 * math.pi * ring / step - 1e-9)))
        for k in range(count):
            wanted.append((index, ring, (bearing + 360.0 * k / count) % 360.0))
        bearing = (bearing + 360.0 * (count - 1) / count) % 360.0
    found = []
    for index, ring, at in wanted:
        if ring == 0.0:
            lat, lon = clat, clon
        else:
            lat, lon = SV.destination(clat, clon, at, ring, radius)
        if swept is not None and swept(lat, lon, margin_m):
            continue
        found.append({"n": len(found) + 1, "lat": round(lat, 6), "lon": round(lon, 6),
                      "ring": index, "radius_m": round(ring, 1), "bearing": round(at, 1)})
        if len(found) >= MAX_WAYPOINTS:
            break
    return found


class Guide:
    """Where the commander is in the waypoints of one body's survey."""

    def __init__(self, system, body, key, waypoints=None, index=0,
                 paused=False, done=False, skipped=None):
        self.system = str(system or "")
        self.body = str(body or "")
        self.key = key
        self.waypoints = list(waypoints or [])
        self.index = max(0, int(index))
        self.paused = bool(paused)
        self.done = bool(done) or not self.waypoints
        # Numbers of the waypoints left out with the skip key, not driven to.
        self.skipped = sorted(set(int(n) for n in skipped or []))
        self.updated = time.time()

    # -- where it is ---------------------------------------------------------

    @property
    def total(self):
        return len(self.waypoints)

    def current(self):
        """The waypoint being driven to, or None when finished or empty."""
        if self.done or not 0 <= self.index < len(self.waypoints):
            return None
        return self.waypoints[self.index]

    def label(self):
        """"WP 3/12" for the current waypoint."""
        point = self.current()
        return "WP %d/%d" % (point["n"], self.total) if point else ""

    # -- moving on and back --------------------------------------------------

    def advance(self, swept=None, margin_m=SWEPT_MARGIN_M):
        """Step to the next waypoint, passing over any that the scanner has
        swept since. Finishes the survey after the last. False when there
        was nothing to step to."""
        if self.done:
            return False
        self.updated = time.time()
        self.index += 1
        while self.index < len(self.waypoints):
            point = self.waypoints[self.index]
            if swept is None or not swept(point["lat"], point["lon"], margin_m):
                return True
            self.index += 1
        self.index = len(self.waypoints)
        self.done = True
        return True

    def skip(self, swept=None, margin_m=SWEPT_MARGIN_M):
        """Leave the current waypoint out - it is not driven to, and the
        survey remembers that it was not - and step to the next. False when
        there was nothing to skip."""
        point = self.current()
        if point is None:
            return False
        if point["n"] not in self.skipped:
            self.skipped = sorted(self.skipped + [point["n"]])
        return self.advance(swept, margin_m)

    def back(self):
        """Step to the one before, or out of "complete" onto the last. A
        waypoint stepped back onto is to be driven to, so it is no longer
        one that was skipped."""
        self.updated = time.time()
        if self.done:
            if not self.waypoints:
                return False
            self.done = False
            self.index = len(self.waypoints) - 1
        elif self.index <= 0:
            return False
        else:
            self.index -= 1
        point = self.current()
        if point is not None and point["n"] in self.skipped:
            self.skipped = [n for n in self.skipped if n != point["n"]]
        return True

    def toggle_pause(self):
        self.paused = not self.paused
        self.updated = time.time()
        return self.paused

    def arrived(self, lat, lon, radius_m, arrive_m=ARRIVE_M):
        """True when this position is within the arrival radius of the
        current waypoint."""
        point = self.current()
        if point is None or not radius_m:
            return False
        try:
            return SV.surface_range_m(lat, lon, point["lat"], point["lon"],
                                      radius_m) <= arrive_radius(arrive_m)
        except (TypeError, ValueError):
            return False

    def update(self, lat, lon, radius_m, arrive_m=ARRIVE_M, swept=None):
        """Feed a position. Moves on, and says so, when it is within the
        arrival radius of the current waypoint and the guide is not paused."""
        if self.paused or not self.arrived(lat, lon, radius_m, arrive_m):
            return False
        return self.advance(swept)

    # -- on disk -------------------------------------------------------------

    def to_dict(self):
        return {"system": self.system, "body": self.body, "key": list(self.key),
                "waypoints": self.waypoints, "index": self.index,
                "paused": self.paused, "done": self.done, "skipped": self.skipped,
                "updated": self.updated}

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            return None
        points = []
        for item in data.get("waypoints") or []:
            try:
                points.append({"n": int(item["n"]), "lat": float(item["lat"]),
                               "lon": float(item["lon"]),
                               "ring": int(item.get("ring", 0)),
                               "radius_m": float(item.get("radius_m", 0.0)),
                               "bearing": float(item.get("bearing", 0.0))})
            except (KeyError, TypeError, ValueError):
                continue
        try:
            key = tuple(float(x) for x in data.get("key") or ())
            index = int(data.get("index") or 0)
        except (TypeError, ValueError):
            return None
        try:
            skipped = [int(n) for n in data.get("skipped") or []]
        except (TypeError, ValueError):
            skipped = []
        guide = cls(data.get("system"), data.get("body"), key, points, index,
                    data.get("paused"), data.get("done"), skipped)
        guide.index = min(guide.index, len(points))
        try:
            guide.updated = float(data.get("updated") or guide.updated)
        except (TypeError, ValueError):
            pass
        return guide


def area_key(centre, border_m, scan_m, step_m=SPACING_M):
    """What a waypoint list was built from. A different key is a different
    survey, and its progress does not carry over."""
    return (round(float(centre[0]), 5), round(float(centre[1]), 5),
            round(float(border_m)), round(float(scan_m)), round(float(step_m)))


class WaypointBook:
    """Every body's guide, in one small file in the data folder."""

    def __init__(self, folder):
        self.path = os.path.join(folder, FILE_NAME) if folder else ""
        self._guides = {}
        self.load()

    @staticmethod
    def _name(system, body):
        return "%s|%s" % (SV.fold(system), SV.fold(body))

    def load(self):
        self._guides = {}
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        bodies = data.get("bodies") if isinstance(data, dict) else None
        for name, item in (bodies or {}).items():
            guide = Guide.from_dict(item)
            if guide is not None:
                self._guides[str(name)] = guide

    def get(self, system, body):
        return self._guides.get(self._name(system, body))

    def put(self, guide):
        self._guides[self._name(guide.system, guide.body)] = guide

    def drop(self, system, body):
        return self._guides.pop(self._name(system, body), None)

    def save(self):
        if not self.path:
            return False
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            temp = self.path + ".tmp"
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump({"version": FILE_VERSION,
                           "bodies": {n: g.to_dict() for n, g in self._guides.items()}},
                          handle)
            os.replace(temp, self.path)
            return True
        except OSError:
            return False
