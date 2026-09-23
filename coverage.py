"""
Coverage: how much of a mining area the scanner has actually swept.

The Rhino's scanner only sees deposits within a fixed range of the vehicle,
so an area is only surveyed once every part of it has been inside that range
at some point. Nobody can hold that in their head while driving. This module
remembers where the SRV has been, treats every stored position as a disc of
scanner range, and answers three questions from that:

    how much ground has been swept at all
    how much of the area inside the border has been swept, as a percentage
    where the unswept patches inside the border are, largest first

It also works out the drive circles that would cover a centre and border
with a sensible overlap, so there is a plan to follow rather than a guess.

The ground is modelled as a flat grid of square cells laid out around the
map's anchor. Over the tens of kilometres a mining area spans that is
accurate to well under a cell, and it turns "the union of hundreds of
overlapping circles" into counting cells in a set, which is fast enough to
run on every position update.

No UI in here. Everything is plain data and plain functions, so it can be
tested without a display.
"""

import os
import json
import math
import time
import hashlib
import functools

import survey as SV

# The scanner's reach, and so the radius of every painted disc.
SCAN_RADIUS_M = 2000.0

# How much neighbouring drive circles overlap. A little overlap means a
# commander who drifts off the ideal line does not leave a sliver unscanned.
OVERLAP_M = 250.0

# A new position is only stored once the SRV has moved this far from the last
# stored one. Positions arrive several times a second, and storing every one
# would bloat the file without changing the painted area by a single cell.
PAINT_STEP_M = 100.0

# A position this close to an existing map's anchor on the same body carries
# on that map rather than starting a new one.
SAME_MAP_M = 10000.0

# The most cells the area of interest may be cut into. Cells get bigger for
# larger areas so memory and time stay bounded however big the border is.
MAX_CELLS = 160000

# The smallest cell ever used. Below this the extra precision buys nothing
# the SRV's own position noise has not already blurred away.
MIN_CELL_M = 50.0

# Cell size when there is no border to size against.
FREE_CELL_M = 100.0

FILE_VERSION = 1

# Cells are stored as one integer each, row * _ROW + column, rather than as
# (column, row) tuples. That lets a whole row of a painted disc go into the
# set with a single set.update(range(...)), which runs at C speed. The stride
# only has to be more than twice the widest column index, and half a large
# planet's circumference in 50 m cells is far below it.
_ROW = 1 << 32
_HALF_ROW = _ROW // 2

# Windows virus scanners and cloud sync clients hold a freshly written file
# open for a moment, and the rename fails while they do. A few short retries
# get past that without freezing the window for long.
_REPLACE_TRIES = 5
_REPLACE_WAIT_S = 0.05


# ---------------------------------------------------------------------------
# Reading values that may be junk
# ---------------------------------------------------------------------------

def _number(value):
    """A finite float, or None.

    Strings and booleans are refused on purpose. The game sends positions as
    real numbers, so anything else means the read went wrong, and guessing
    at it would paint the wrong ground.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _positive(value):
    value = _number(value)
    return value if value is not None and value > 0 else None


def _fix(lat, lon):
    """A usable (lat, lon) pair, or None if either half is junk."""
    lat, lon = _number(lat), _number(lon)
    if lat is None or lon is None or abs(lat) > 90.0 or abs(lon) > 360.0:
        return None
    return (lat, lon)


def _pair(value):
    """A (lat, lon) pair from whatever a saved file happens to hold."""
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return _fix(value[0], value[1])
    return None


def _text(value):
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    return ""


@functools.lru_cache(maxsize=64)
def _disc_rows(radius_m, cell_m):
    """The cells of a disc, as (row offset, half width) pairs.

    A cell belongs to the disc when its centre is within radius_m of the
    centre of cell (0, 0). Each row of a disc is one unbroken run of cells,
    so a row offset and a half width describe it completely, and painting a
    disc anywhere on the grid becomes a handful of range additions. It is
    worked out once per radius and cell size and then reused.
    """
    reach = int(math.floor(radius_m / cell_m + 1e-9))
    rows = []
    for dj in range(-reach, reach + 1):
        across = radius_m * radius_m - (dj * cell_m) ** 2
        if across < 0:
            continue
        rows.append((dj, int(math.floor(math.sqrt(across) / cell_m + 1e-9))))
    return tuple(rows)


# ---------------------------------------------------------------------------
# One survey area on one body
# ---------------------------------------------------------------------------

class CoverageMap:
    """Where the SRV has driven on one body, and how much that has swept."""

    def __init__(self, system, body, radius_m, scan_m=SCAN_RADIUS_M,
                 overlap_m=OVERLAP_M, step_m=PAINT_STEP_M):
        self.system = _text(system)
        self.body = _text(body)
        # The body's radius can be unknown for a moment after touchdown.
        # Zero means "cannot measure yet", and every method copes with it.
        self.radius_m = _positive(radius_m) or 0.0
        self.scan_m = _positive(scan_m) or SCAN_RADIUS_M
        overlap = _number(overlap_m)
        self.overlap_m = overlap if overlap is not None and overlap >= 0 else OVERLAP_M
        self.step_m = _positive(step_m) or PAINT_STEP_M
        self.points = []
        self.centre = None
        self.border_m = None
        self.created = SV.utc_now()
        self.updated = self.created
        self.signal = ""
        self._version = 0
        self._reset_raster()

    # -- where things are ---------------------------------------------------

    @property
    def anchor(self):
        """The origin everything is measured from.

        The centre when the commander has set one, because that is what the
        border and the drive circles are drawn around. Before that, the first
        place painted, so the map still has somewhere to hang from.
        """
        if self.centre is not None:
            return self.centre
        if self.points:
            return self.points[0]
        return None

    def distance_from(self, lat, lon):
        anchor, fix = self.anchor, _fix(lat, lon)
        if anchor is None or fix is None or not self.radius_m:
            return None
        return SV.surface_range_m(anchor[0], anchor[1], fix[0], fix[1], self.radius_m)

    def local(self, lat, lon):
        anchor, fix = self.anchor, _fix(lat, lon)
        if anchor is None or fix is None or not self.radius_m:
            return None
        return SV.local_offset(anchor[0], anchor[1], fix[0], fix[1], self.radius_m)

    # -- painting -------------------------------------------------------------

    def add_fix(self, lat, lon):
        """Record a position if it has moved far enough to matter.

        Called on every position update, so the common case - the SRV has
        barely moved - must cost one distance check and nothing more.
        """
        fix = _fix(lat, lon)
        if fix is None or not self.radius_m:
            return False
        radius = self.radius_m
        if self.points:
            last = self.points[-1]
            # The millimetre of slack stops a step of exactly step_m being
            # refused because of rounding in the trigonometry.
            if SV.surface_range_m(last[0], last[1], fix[0], fix[1], radius) + 1e-3 < self.step_m:
                return False
        if self.border_m is not None and self.centre is not None:
            # A disc painted from further out than this cannot reach inside
            # the border, so storing it would only grow the file.
            reach = SV.surface_range_m(self.centre[0], self.centre[1], fix[0], fix[1], radius)
            if reach > self.border_m + self.scan_m:
                return False
        self.points.append(fix)
        self.updated = SV.utc_now()
        # Paint straight into the grid when it is current. When it is not -
        # never built, or the anchor has just moved - the next read rebuilds
        # it from every point, this one included, so nothing is lost.
        if self._grid_key is not None and self._grid_key == self._wanted_key():
            self._paint(fix[0], fix[1])
        return True

    # -- centre and border ----------------------------------------------------

    def set_centre(self, lat, lon):
        fix = _fix(lat, lon)
        if fix is None:
            return None
        self.centre = fix
        self._drop_unreachable()
        self.updated = SV.utc_now()
        # The anchor has moved, so the grid is stale and the next read lays
        # it out again around the new centre.
        return None

    def set_border(self, lat, lon):
        """Set the border to pass through where the commander is now.

        Taking it from a position rather than a typed number means the
        commander drives to the edge of what they want surveyed and presses
        a key, which is how the centre is set as well.
        """
        fix = _fix(lat, lon)
        if fix is None or self.centre is None or not self.radius_m:
            return None
        border = SV.surface_range_m(self.centre[0], self.centre[1], fix[0], fix[1], self.radius_m)
        # A border well inside a single scan is almost certainly the key being
        # pressed twice at the centre, not a real survey area.
        if not math.isfinite(border) or border < self.scan_m / 4.0:
            return None
        self.border_m = border
        self._drop_unreachable()
        self.updated = SV.utc_now()
        return border

    def clear_border(self):
        if self.border_m is None:
            return None
        self.border_m = None
        self.updated = SV.utc_now()
        return None

    def _drop_unreachable(self):
        if self.border_m is None or self.centre is None or not self.radius_m:
            return
        limit = self.border_m + self.scan_m
        clat, clon, radius = self.centre[0], self.centre[1], self.radius_m
        self.points = [p for p in self.points
                       if SV.surface_range_m(clat, clon, p[0], p[1], radius) <= limit]

    # -- the drive plan -------------------------------------------------------

    def rings(self):
        """Radii of the circles to drive around the centre to cover the area.

        Parked at the centre the scanner already covers out to scan_m. Each
        circle driven at radius r sweeps from r - scan_m to r + scan_m, so
        circles one full scan width apart, less the overlap, leave no gap.
        The last circle is pulled in so its sweep ends at the border instead
        of wasting fuel and time on ground nobody asked to have surveyed.
        """
        if self.centre is None:
            return []
        scan = self.scan_m
        # An overlap wider than the scan itself would stall the loop, so the
        # spacing never drops below a twentieth of a scan.
        spacing = max(2.0 * scan - self.overlap_m, scan * 0.05)
        if self.border_m is None:
            return [spacing, 2.0 * spacing]
        border = self.border_m
        rings, previous = [], 0.0
        while previous + scan < border and len(rings) < 1000:
            radius = (len(rings) + 1) * spacing
            if radius + scan >= border:
                radius = max(border - scan, previous)
            rings.append(radius)
            previous = radius
        return rings

    # -- how much is covered --------------------------------------------------

    def coverage(self):
        built = self._ensure_raster()
        cell_km2 = self._cell * self._cell / 1e6
        painted = (len(self._inside) + len(self._outside)) * cell_km2 if built else 0.0
        result = {"painted_km2": round(painted, 2), "border_km2": None,
                  "covered_km2": None, "fraction": None, "percent": None}
        if self.border_m is None or self.centre is None:
            return result
        border_km2 = math.pi * self.border_m * self.border_m / 1e6
        fraction = 0.0
        if built and self._border_total:
            fraction = min(1.0, max(0.0, len(self._inside) / self._border_total))
        # Covered area is derived from the fraction, not from its own cell
        # count, so it can never read as more than the border holds.
        result.update(border_km2=round(border_km2, 2),
                      covered_km2=round(border_km2 * fraction, 2),
                      fraction=fraction,
                      # Never rounded UP to 100. "100%" is the promise that
                      # the whole area has been swept, so 99.6% reads 99.
                      percent=100 if fraction >= 0.999
                      else min(99, int(fraction * 100)))
        return result

    def gaps(self, limit=3):
        """The unswept patches inside the border, largest first.

        Patches are groups of unswept cells touching along an edge or at a
        corner (8-connectivity). Two cells that meet only at a corner are one
        patch of ground on the surface; splitting them would be an artefact
        of the grid, and would send the commander to the same place twice.
        """
        if self.border_m is None or self.centre is None:
            return []
        if not self._ensure_raster():
            return []
        if self._gap_cache is None or self._gap_cache[0] != self._version:
            self._gap_cache = (self._version, self._find_gaps())
        try:
            limit = max(0, int(limit))
        except (TypeError, ValueError, OverflowError):
            limit = 3
        return [dict(gap) for gap in self._gap_cache[1][:limit]]

    def _find_gaps(self):
        # Rather than flood-fill cell by cell, each row of the border disc is
        # cut into runs of unswept cells, and runs in neighbouring rows that
        # touch are joined. There are far fewer runs than cells, and a run's
        # area and centroid are simple sums.
        inside, cell = self._inside, self._cell
        parent, stats = [], []

        def root(node):
            while parent[node] != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node

        previous, previous_row = [], None
        for j, half in self._border_rows:
            base = j * _ROW
            runs, start = [], None
            for i in range(-half, half + 1):
                if (base + i) in inside:
                    if start is not None:
                        runs.append((start, i - 1))
                        start = None
                elif start is None:
                    start = i
            if start is not None:
                runs.append((start, half))
            current = []
            for a, b in runs:
                node = len(parent)
                parent.append(node)
                length = b - a + 1
                stats.append([length, (a + b) * length / 2.0, float(j * length)])
                current.append((a, b, node))
            if previous and previous_row == j - 1:
                p = q = 0
                while p < len(previous) and q < len(current):
                    pa, pb, pnode = previous[p]
                    ca, cb, cnode = current[q]
                    # One cell of slack either side is what joins corners.
                    if pa - 1 <= cb and ca <= pb + 1:
                        ra, rb = root(pnode), root(cnode)
                        if ra != rb:
                            parent[rb] = ra
                    if pb + 1 < cb:
                        p += 1
                    else:
                        q += 1
            previous, previous_row = current, j

        totals = {}
        for node, (count, sum_i, sum_j) in enumerate(stats):
            top = root(node)
            if top in totals:
                entry = totals[top]
                entry[0] += count
                entry[1] += sum_i
                entry[2] += sum_j
            else:
                totals[top] = [count, sum_i, sum_j]

        # Slivers under one percent of the area are the edges of discs not
        # quite meeting on the grid, not ground worth driving back for.
        smallest = 0.01 * self._border_total
        found = []
        for count, sum_i, sum_j in totals.values():
            if count < smallest:
                continue
            east = sum_i / count * cell
            north = sum_j / count * cell
            found.append({
                "bearing": round((math.degrees(math.atan2(east, north)) + 360.0) % 360.0, 1),
                "distance_m": round(math.hypot(east, north), 1),
                "area_km2": round(count * cell * cell / 1e6, 2),
                "east_m": round(east, 1),
                "north_m": round(north, 1),
                "_cells": count,
            })
        found.sort(key=lambda gap: -gap["_cells"])
        for gap in found:
            del gap["_cells"]
        return found

    # -- the grid -------------------------------------------------------------

    def _reset_raster(self):
        self._grid_key = None
        self._ref = None
        self._cell = FREE_CELL_M
        self._mask = ()
        self._border_rows = ()
        self._border_half = {}
        self._border_total = 0
        self._inside = set()
        self._outside = set()
        self._gap_cache = None
        self._version += 1

    def _cell_size(self):
        cap = math.sqrt(max(1, int(MAX_CELLS)))
        if self.border_m is not None and self.centre is not None:
            # The area of interest is every cell a stored point can paint,
            # which is the border plus one scan. Its bounding square must fit
            # under the cap, and whole metres keep the size stable.
            reach = self.border_m + self.scan_m
            size = max(MIN_CELL_M, float(math.ceil(2.0 * reach / cap)))
        else:
            size = FREE_CELL_M
        # A single painted disc must fit under the cap too, whatever scan
        # range a caller has chosen, or one position could stall the loop.
        return max(size, float(math.ceil(2.0 * self.scan_m / cap)))

    def _wanted_key(self):
        anchor = self.anchor
        if anchor is None or not self.radius_m:
            return None
        return (anchor, self._cell_size(), self.border_m, self.radius_m, self.scan_m)

    def _ensure_raster(self):
        wanted = self._wanted_key()
        if wanted is None:
            if self._grid_key is not None or self._inside or self._outside:
                self._reset_raster()
            return False
        if wanted != self._grid_key:
            self._rebuild(wanted)
        return True

    def _rebuild(self, key):
        anchor, cell, border = key[0], key[1], key[2]
        self._reset_raster()
        self._ref = anchor
        self._cell = cell
        self._mask = _disc_rows(self.scan_m, cell)
        if border is not None and self.centre is not None:
            # The grid is anchored on the centre whenever there is a border,
            # so cell (0, 0) is the centre and the border is a fixed mask.
            self._border_rows = _disc_rows(border, cell)
            self._border_half = dict(self._border_rows)
            self._border_total = sum(2 * half + 1 for _, half in self._border_rows)
        self._grid_key = key
        for lat, lon in self.points:
            self._paint(lat, lon)

    def _paint(self, lat, lon):
        east, north = SV.local_offset(self._ref[0], self._ref[1], lat, lon, self.radius_m)
        cell = self._cell
        i0, j0 = int(round(east / cell)), int(round(north / cell))
        inside, outside, border_half = self._inside, self._outside, self._border_half
        before = len(inside) + len(outside)
        for dj, half in self._mask:
            j = j0 + dj
            base = j * _ROW
            a, b = i0 - half, i0 + half
            limit = border_half.get(j)
            if limit is None:
                outside.update(range(base + a, base + b + 1))
                continue
            # Split the row where it crosses the border, so the count of
            # swept cells inside the border is simply the size of one set.
            lo, hi = max(a, -limit), min(b, limit)
            if lo > hi:
                outside.update(range(base + a, base + b + 1))
                continue
            if a < lo:
                outside.update(range(base + a, base + lo))
            inside.update(range(base + lo, base + hi + 1))
            if hi < b:
                outside.update(range(base + hi + 1, base + b + 1))
        if len(inside) + len(outside) != before:
            self._version += 1

    # -- saving ---------------------------------------------------------------

    def to_dict(self):
        """Everything needed to bring the map back. The grid is not saved;
        it is rebuilt from the points, so it can never disagree with them."""
        return {
            "version": FILE_VERSION,
            "system": self.system,
            "body": self.body,
            "radius_m": self.radius_m,
            "scan_m": self.scan_m,
            "overlap_m": self.overlap_m,
            "step_m": self.step_m,
            "points": [[lat, lon] for lat, lon in self.points],
            "centre": list(self.centre) if self.centre is not None else None,
            "border_m": self.border_m,
            "created": self.created,
            "updated": self.updated,
            "signal": self.signal,
        }

    @classmethod
    def from_dict(cls, data):
        """Rebuild a map from saved data, skipping anything that is junk.

        A hand-edited or half-written file should cost the bad entries, not
        the whole map, so every field is checked on its own.
        """
        if not isinstance(data, dict):
            data = {}
        cmap = cls(data.get("system"), data.get("body"), data.get("radius_m"),
                   data.get("scan_m"), data.get("overlap_m"), data.get("step_m"))
        raw = data.get("points")
        if isinstance(raw, list):
            for item in raw:
                pair = _pair(item)
                if pair is not None:
                    cmap.points.append(pair)
        cmap.centre = _pair(data.get("centre"))
        border = _positive(data.get("border_m"))
        cmap.border_m = border if cmap.centre is not None else None
        for field in ("created", "updated"):
            stamp = data.get(field)
            if isinstance(stamp, str) and stamp.strip():
                setattr(cmap, field, stamp.strip())
        cmap.signal = _text(data.get("signal"))
        return cmap


# ---------------------------------------------------------------------------
# Every map, kept on disk one file per body
# ---------------------------------------------------------------------------

class CoverageBook:
    """The coverage maps on disk, one JSON file per body.

    One file per body keeps each write small, and means a damaged file costs
    one body's coverage rather than everything the commander has driven.
    """

    def __init__(self, folder):
        self.folder = os.path.join(str(folder or "."), "coverage")
        self._bodies = {}

    @staticmethod
    def _key(system, body):
        return (_text(system), _text(body))

    def path_for(self, system, body):
        """Where a body's maps live.

        The readable part is for a person looking in the folder. The hash of
        the exact names is what makes it unique: two bodies whose names only
        differ in characters a file name cannot hold would otherwise share a
        file and overwrite each other.
        """
        system, body = self._key(system, body)
        exact = system + "|" + body
        safe = "".join(ch if ch.isascii() and (ch.isalnum() or ch in " -_") else "_"
                       for ch in exact)
        slug = "_".join(part for part in safe.split(" ") if part)[:120] or "body"
        digest = hashlib.sha1(exact.encode("utf-8")).hexdigest()[:10]
        return os.path.join(self.folder, "%s-%s.json" % (slug, digest))

    def _maps(self, key):
        """The maps on one body, loading them the first time they are asked for.

        None means the file is there but could not be read safely right now.
        That is not cached, so the next call tries again, and save() refuses
        to write over a file it has not been able to read.
        """
        if key in self._bodies:
            return self._bodies[key]
        loaded = self._load(key)
        if loaded is not None:
            self._bodies[key] = loaded
        return loaded

    def _load(self, key):
        path = self.path_for(*key)
        try:
            with open(path, "rb") as handle:
                raw = handle.read()
        except FileNotFoundError:
            return []
        except OSError:
            # Locked or refused is not the same as damaged. Leave it alone.
            return None
        try:
            data = json.loads(raw.decode("utf-8-sig"))
            if not isinstance(data, dict) or not isinstance(data.get("maps"), list):
                raise ValueError("not a coverage file")
        except (ValueError, RecursionError):
            # Never delete or overwrite a file that will not parse. Moving it
            # aside keeps it for a person to look at, and lets this body start
            # again with a clean file.
            return [] if self._set_aside(path) else None
        version = _number(data.get("version"))
        if version is not None and version > FILE_VERSION:
            # Written by a newer version of the app. Reading it is guesswork
            # and saving over it would throw away whatever that version added.
            return None
        maps = []
        for item in data["maps"]:
            if not isinstance(item, dict):
                continue
            cmap = CoverageMap.from_dict(item)
            if not cmap.system and not cmap.body:
                cmap.system, cmap.body = key
            maps.append(cmap)
        return maps

    @staticmethod
    def _set_aside(path):
        stamp = time.strftime("%Y%m%d-%H%M%S")
        target = "%s.unreadable-%s" % (path, stamp)
        counter = 1
        while os.path.exists(target):
            target = "%s.unreadable-%s-%d" % (path, stamp, counter)
            counter += 1
        for attempt in range(_REPLACE_TRIES):
            try:
                os.rename(path, target)
                return True
            except PermissionError:
                if attempt + 1 < _REPLACE_TRIES:
                    time.sleep(_REPLACE_WAIT_S * (attempt + 1))
            except OSError:
                return False
        return False

    def map_for(self, system, body, lat, lon, radius_m):
        """The map to carry on painting at this position.

        The nearest map on the body whose anchor is within SAME_MAP_M, so
        coming back to an area picks up where the last session left off.
        Otherwise a new map, which is only written to disk by save().
        """
        key = self._key(system, body)
        maps = self._maps(key)
        known = maps is not None
        if maps is None:
            maps = []
        fix = _fix(lat, lon)
        radius = _positive(radius_m)
        best, best_range = None, None
        if fix is not None:
            for cmap in maps:
                anchor = cmap.anchor
                measure = radius or cmap.radius_m
                if anchor is None or not measure:
                    continue
                reach = SV.surface_range_m(anchor[0], anchor[1], fix[0], fix[1], measure)
                if reach <= SAME_MAP_M and (best_range is None or reach < best_range):
                    best, best_range = cmap, reach
        if best is not None:
            if radius and not best.radius_m:
                best.radius_m = radius
            return best
        # A map handed out earlier that has not painted anything yet is reused,
        # so asking twice before the first position arrives does not leave a
        # trail of empty maps behind.
        for cmap in maps:
            if cmap.anchor is None:
                if radius:
                    cmap.radius_m = radius
                return cmap
        cmap = CoverageMap(key[0], key[1], radius_m)
        if known:
            maps.append(cmap)
        return cmap

    def maps_on(self, system, body):
        return list(self._maps(self._key(system, body)) or [])

    def save(self, cmap):
        """Write every map on the map's body to that body's file. Never raises."""
        if not isinstance(cmap, CoverageMap):
            return False
        try:
            key = self._key(cmap.system, cmap.body)
            maps = self._maps(key)
            if maps is None:
                return False
            if not any(item is cmap for item in maps):
                maps.append(cmap)
            payload = {
                "version": FILE_VERSION,
                "system": key[0],
                "body": key[1],
                "saved": SV.utc_now(),
                # A map with no anchor has nothing in it and could never be
                # found again by position, so it is not worth a place in the file.
                "maps": [item.to_dict() for item in maps if item.anchor is not None],
            }
            return _write_json(self.path_for(*key), payload)
        except Exception:
            # save() is called from the UI loop on a timer. A surprise here
            # must cost one save, not the session.
            return False


def _write_json(path, payload):
    """Write through a temporary file, so a crash cannot leave half a file."""
    temp = path + ".tmp"
    try:
        text = json.dumps(payload, allow_nan=False, separators=(",", ":"))
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(temp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(_REPLACE_TRIES):
            try:
                os.replace(temp, path)
                return True
            except PermissionError:
                if attempt + 1 < _REPLACE_TRIES:
                    time.sleep(_REPLACE_WAIT_S * (attempt + 1))
    except (OSError, ValueError, TypeError):
        pass
    try:
        os.remove(temp)
    except OSError:
        pass
    return False
