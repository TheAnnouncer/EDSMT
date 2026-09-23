"""Coverage painting, drive circles and gaps, driven without a display.

The scenario is a commander surveying a mining area on a 2,100 km body: set a
centre, drive to the edge and set the border, then drive the circles the map
suggests and check the map agrees the whole area has been swept.
"""
import os, sys, math, json, glob, time, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import coverage as C

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)

R = 2_100_000.0
TMP = tempfile.mkdtemp(prefix="edsmt-coverage-")
HOME = (12.5, -45.5)


def dest(lat, lon, bearing, metres):
    """Where you end up driving this far on this bearing, on a sphere."""
    p1, l1, th, d = math.radians(lat), math.radians(lon), math.radians(bearing), metres / R
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(th))
    l2 = l1 + math.atan2(math.sin(th) * math.sin(d) * math.cos(p1),
                         math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), math.degrees(l2)


def near(a, b, tol):
    return a is not None and b is not None and abs(a - b) <= tol


def drive_circle(cmap, centre, radius, keep=None, step=100.0):
    """Drive once round a circle, with a position every `step` metres."""
    count = max(8, int(math.ceil(2 * math.pi * radius / step)))
    for k in range(count + 1):
        bearing = 360.0 * k / count
        if keep is None or keep(bearing):
            cmap.add_fix(*dest(centre[0], centre[1], bearing, radius))


def surveyed(border, keep=None):
    """A map with a centre and border, driven round the suggested circles."""
    cmap = C.CoverageMap("Ega", "Ega 1", R)
    cmap.set_centre(*HOME)
    got = cmap.set_border(*dest(HOME[0], HOME[1], 90, border))
    cmap.add_fix(*HOME)
    for radius in cmap.rings():
        drive_circle(cmap, HOME, radius, keep)
    return cmap, got


print("== a single position paints one scanner disc ==")
m = C.CoverageMap("Ega", "Ega 1", R)
check("starts with no anchor", m.anchor is None and m.coverage()["painted_km2"] == 0.0)
check("first fix is stored", m.add_fix(*HOME) is True)
check("the first point becomes the anchor", m.anchor == HOME, m.anchor)
area = m.coverage()["painted_km2"]
check("one disc is about pi * 2km^2 = 12.57 km2 (within 3%)",
      abs(area - math.pi * 4) / (math.pi * 4) < 0.03, area)
check("no border means no percentage",
      m.coverage()["fraction"] is None and m.coverage()["percent"] is None
      and m.coverage()["border_km2"] is None and m.coverage()["covered_km2"] is None)

print("== positions closer than the step are not stored ==")
check("50 m on is ignored", m.add_fix(*dest(HOME[0], HOME[1], 0, 50)) is False)
check("99 m on is ignored", m.add_fix(*dest(HOME[0], HOME[1], 0, 99)) is False)
check("still one point", len(m.points) == 1, len(m.points))
check("exactly the step is stored", m.add_fix(*dest(HOME[0], HOME[1], 0, 100)) is True)
check("now two points", len(m.points) == 2, len(m.points))
check("distance_from measures from the anchor",
      near(m.distance_from(*dest(HOME[0], HOME[1], 45, 1234)), 1234, 0.5))
east, north = m.local(*dest(HOME[0], HOME[1], 90, 1000))
check("local is metres east and north of the anchor", near(east, 1000, 0.5) and abs(north) < 1,
      (east, north))

print("== junk from the game is ignored, never raised on ==")
before = list(m.points)
junk_ok = True
try:
    for lat, lon in ((None, None), ("x", 5), (5, "x"), (float("nan"), 5), (5, float("nan")),
                     (float("inf"), 0), (True, False), ("12.5", "-45.5"), (95, 0), ([], {})):
        junk_ok &= m.add_fix(lat, lon) is False
        junk_ok &= m.distance_from(lat, lon) is None
        junk_ok &= m.local(lat, lon) is None
        m.set_centre(lat, lon)
        junk_ok &= m.set_border(lat, lon) is None
    raised = None
except Exception as exc:
    raised = exc
check("no exception from junk", raised is None, repr(raised))
check("every junk fix refused", junk_ok)
check("points unchanged", m.points == before)
check("centre not set by junk", m.centre is None)
nobody = C.CoverageMap(None, None, "not a radius", scan_m="x", overlap_m=None, step_m=float("nan"))
check("junk constructor arguments fall back to defaults",
      nobody.radius_m == 0.0 and nobody.scan_m == C.SCAN_RADIUS_M
      and nobody.overlap_m == C.OVERLAP_M and nobody.step_m == C.PAINT_STEP_M)
check("with no known radius nothing is painted, and nothing raises",
      nobody.add_fix(*HOME) is False and nobody.coverage()["painted_km2"] == 0.0
      and nobody.gaps() == [] and nobody.rings() == [])

print("== a straight 10 km drive paints a 4 km wide strip with round ends ==")
line = C.CoverageMap("Ega", "Ega 1", R)
start = (0.0, 10.0)
for k in range(101):
    line.add_fix(*dest(start[0], start[1], 90, 100.0 * k))
expected = 4 * 10 + math.pi * 4
area = line.coverage()["painted_km2"]
check("101 points stored", len(line.points) == 101, len(line.points))
check("about 40 + 12.57 = 52.57 km2 (within 5%)", abs(area - expected) / expected < 0.05, area)

print("== drive circles ==")
r = C.CoverageMap("Ega", "Ega 1", R)
check("no centre, no circles", r.rings() == [])
r.set_centre(*HOME)
check("centre set", r.centre == HOME)
check("no border gives the first two circles, 3750 m apart", r.rings() == [3750.0, 7500.0],
      r.rings())
got = r.set_border(*dest(HOME[0], HOME[1], 90, 6000))
check("border of 6000 m", near(got, 6000, 0.5), got)
rings = r.rings()
check("6 km border: first circle at the spacing", near(rings[0], 3750, 1e-6), rings)
check("6 km border: last circle pulled in to 4000 m", near(rings[-1], 4000, 0.5), rings)
check("6 km border: the last circle's scan reaches the border exactly",
      near(rings[-1] + r.scan_m, r.border_m, 1e-6))
r.set_border(*dest(HOME[0], HOME[1], 90, 20000))
rings = r.rings()
check("20 km border: spacing respected",
      all(near(b - a, 3750, 1e-6) for a, b in zip(rings[:-2], rings[1:-1])), rings)
check("20 km border: last circle at 18000 m", near(rings[-1], 18000, 0.5), rings)
check("20 km border: nothing drawn outside the border",
      all(x + r.scan_m <= r.border_m + 1e-6 for x in rings))
r.clear_border()
check("clearing the border goes back to two circles", r.rings() == [3750.0, 7500.0])
q = C.CoverageMap("Ega", "Ega 1", R, scan_m=2000, overlap_m=500)
q.set_centre(*HOME)
check("overlap changes the spacing", q.rings() == [3500.0, 7000.0], q.rings())

print("== setting a border ==")
b = C.CoverageMap("Ega", "Ega 1", R)
check("no border without a centre", b.set_border(*dest(HOME[0], HOME[1], 90, 6000)) is None)
check("still no border", b.border_m is None)
b.set_centre(*HOME)
check("a border inside a quarter scan is refused",
      b.set_border(*dest(HOME[0], HOME[1], 90, 300)) is None and b.border_m is None)

print("== coverage from a single position at the centre ==")
one = C.CoverageMap("Ega", "Ega 1", R)
one.set_centre(*HOME)
one.set_border(*dest(HOME[0], HOME[1], 0, 6000))
one.add_fix(*HOME)
cov = one.coverage()
check("fraction is about (2000/6000)^2 = 0.111", near(cov["fraction"], (2000 / 6000) ** 2, 0.02),
      cov)
check("percent is 11", cov["percent"] == 11, cov)
check("border area is pi * 6^2 km2", near(cov["border_km2"], math.pi * 36, 0.01), cov)
check("covered area is inside the border area", cov["covered_km2"] <= cov["border_km2"], cov)

print("== driving the suggested circles sweeps the whole area ==")
for border in (6000, 10000):
    full, got = surveyed(border)
    cov = full.coverage()
    check("%d m border: fraction >= 0.99" % border, cov["fraction"] >= 0.99, cov)
    check("%d m border: reads as 100 percent" % border, cov["percent"] == 100, cov)
    check("%d m border: no gaps left" % border, full.gaps() == [], full.gaps())

print("== gaps ==")
g = C.CoverageMap("Ega", "Ega 1", R)
g.set_centre(*HOME)
g.set_border(*dest(HOME[0], HOME[1], 180, 6000))
check("no fixes, one gap the size of the whole area",
      len(g.gaps()) == 1 and near(g.gaps()[0]["area_km2"], math.pi * 36, 1.5), g.gaps())
g.add_fix(*HOME)
gaps = g.gaps()
ring_area = math.pi * (36 - 4)
check("centre only: one gap", len(gaps) == 1, gaps)
check("centre only: the gap is the ring from 2 km to 6 km (about 100.5 km2)",
      gaps and abs(gaps[0]["area_km2"] - ring_area) / ring_area < 0.05, gaps)
check("gaps carry bearing, distance and area",
      gaps and all(k in gaps[0] for k in ("bearing", "distance_m", "area_km2")), gaps)
check("a limit of zero gives nothing", g.gaps(0) == [])
check("a junk limit falls back to the default", isinstance(g.gaps("x"), list))
west, _ = surveyed(6000, keep=lambda bearing: 180 <= bearing <= 360)
gaps = west.gaps()
check("west half driven: at least one gap", len(gaps) >= 1, gaps)
check("west half driven: the biggest gap is to the east",
      gaps and 45 <= gaps[0]["bearing"] <= 135, gaps)
check("west half driven: gaps are sorted largest first",
      all(a["area_km2"] >= b["area_km2"] for a, b in zip(gaps, gaps[1:])), gaps)
check("west half driven: the gap is well out from the centre",
      gaps and gaps[0]["distance_m"] > 2000, gaps)
check("no border, no gaps", m.gaps() == [])

print("== positions that cannot reach inside the border ==")
o = C.CoverageMap("Ega", "Ega 1", R)
o.add_fix(*HOME)
o.add_fix(*dest(HOME[0], HOME[1], 90, 7000))      # 7 km: inside 6 + 2
o.add_fix(*dest(HOME[0], HOME[1], 90, 9000))      # 9 km: past the reach
check("three points before a border", len(o.points) == 3, len(o.points))
o.set_centre(*HOME)
check("a centre alone drops nothing", len(o.points) == 3, len(o.points))
o.set_border(*dest(HOME[0], HOME[1], 0, 6000))
check("set_border drops the point 9 km out", len(o.points) == 2, len(o.points))
check("add_fix refuses a point 8.5 km out",
      o.add_fix(*dest(HOME[0], HOME[1], 270, 8500)) is False and len(o.points) == 2)
check("add_fix accepts a point 7.5 km out",
      o.add_fix(*dest(HOME[0], HOME[1], 270, 7500)) is True and len(o.points) == 3)
o.set_centre(*dest(HOME[0], HOME[1], 270, 3000))
check("moving the centre keeps the border radius", near(o.border_m, 6000, 0.5), o.border_m)
check("moving the centre drops points now out of reach (the one 7 km east)",
      len(o.points) == 2, len(o.points))
check("the anchor follows the centre", o.anchor == o.centre)

print("== saving and loading a map ==")
src, _ = surveyed(6000, keep=lambda bearing: bearing <= 180)
src.signal = "PLANETARY MINING LOCATION SIGNAL (3)"
wire = json.loads(json.dumps(src.to_dict()))
back = C.CoverageMap.from_dict(wire)
check("points survive", back.points == src.points, (len(back.points), len(src.points)))
check("centre survives", back.centre == src.centre)
check("border survives", back.border_m == src.border_m)
check("signal and names survive",
      back.signal == src.signal and back.system == "Ega" and back.body == "Ega 1")
check("coverage survives", back.coverage() == src.coverage(), (back.coverage(), src.coverage()))
check("gaps survive", back.gaps() == src.gaps())
check("rings survive", back.rings() == src.rings())
junk_ok = True
try:
    for data in (None, "x", [], {}, {"points": "x", "centre": [1], "border_m": "big"},
                 {"points": [[1, 2], ["a", 3], None, [float("nan"), 1], [1, 2, 3], {"a": 1}],
                  "centre": None, "border_m": 5000, "radius_m": -4, "created": 7}):
        loaded = C.CoverageMap.from_dict(data)
        loaded.coverage(); loaded.gaps(); loaded.rings()
    raised = None
except Exception as exc:
    raised = exc
check("junk saved data never raises", raised is None, repr(raised))
check("junk saved data keeps only the good point", loaded.points == [(1.0, 2.0)], loaded.points)
check("a border with no centre is dropped", loaded.border_m is None)
check("a bad timestamp is replaced", isinstance(loaded.created, str) and loaded.created != "7")

print("== the book finds a map again by position ==")
book = C.CoverageBook(TMP)
first = book.map_for("Ega", "Ega 1", HOME[0], HOME[1], R)
check("a new map is empty", first.points == [] and first.anchor is None)
check("asking again before any fix gives the same map",
      book.map_for("Ega", "Ega 1", HOME[0], HOME[1], R) is first)
for k in range(20):
    first.add_fix(*dest(HOME[0], HOME[1], 45, 100.0 * k))
first.set_centre(*HOME)
first.set_border(*dest(HOME[0], HOME[1], 90, 6000))
check("save works", book.save(first) is True)
path = book.path_for("Ega", "Ega 1")
check("the file is there", os.path.exists(path), path)
check("no temporary file left behind", not os.path.exists(path + ".tmp"))
again = C.CoverageBook(TMP)
found = again.map_for("Ega", "Ega 1", *dest(HOME[0], HOME[1], 200, 8000), R)
check("a new book finds it 8 km away", found.points == first.points, len(found.points))
check("with its centre and border", found.centre == first.centre and found.border_m == first.border_m)
check("and the same coverage", found.coverage() == first.coverage())
fresh = again.map_for("Ega", "Ega 1", *dest(HOME[0], HOME[1], 200, 25000), R)
check("25 km away is a fresh map", fresh is not found and fresh.points == [] and fresh.centre is None)
check("the fresh map is on the same body", fresh.system == "Ega" and fresh.body == "Ega 1")
check("maps_on lists both, only one saved",
      len(again.maps_on("Ega", "Ega 1")) == 2 and len(C.CoverageBook(TMP).maps_on("Ega", "Ega 1")) == 1)
fresh.add_fix(*dest(HOME[0], HOME[1], 200, 25000))
check("saving the second map keeps the first", again.save(fresh) is True
      and len(C.CoverageBook(TMP).maps_on("Ega", "Ega 1")) == 2)
nearest = C.CoverageBook(TMP).map_for("Ega", "Ega 1", *dest(HOME[0], HOME[1], 200, 24000), R)
check("the nearest map wins", nearest.anchor == fresh.anchor)
check("another body has nothing", C.CoverageBook(TMP).maps_on("Ega", "Ega 2") == [])

print("== file names ==")
x = "Col 285 Sector AB-C d1/2"
y = "Col 285 Sector AB-C d1?2"
px, py = book.path_for("Col 285", x), book.path_for("Col 285", y)
check("names that slug the same get different files", px != py, (px, py))
name = os.path.basename(px)
check("the file name is safe",
      all(ch.isascii() and (ch.isalnum() or ch in "-_.") for ch in name), name)
check("spaces are collapsed", "Col_285_Col_285_Sector_AB-C_d1_2" in name, name)
check("the name is stable", book.path_for("Col 285", x) == C.CoverageBook(TMP).path_for("Col 285", x))
longest = os.path.basename(book.path_for("S" * 300, "B" * 300))
check("long names are capped", len(longest) <= 120 + 1 + 10 + 5, len(longest))
mx = C.CoverageMap("Col 285", x, R); mx.add_fix(1.0, 1.0)
my = C.CoverageMap("Col 285", y, R); my.add_fix(2.0, 2.0)
check("both save", book.save(mx) and book.save(my))
bx, by = C.CoverageBook(TMP).maps_on("Col 285", x), C.CoverageBook(TMP).maps_on("Col 285", y)
check("and do not overwrite each other",
      len(bx) == 1 and len(by) == 1 and bx[0].points == [(1.0, 1.0)] and by[0].points == [(2.0, 2.0)],
      (bx, by))

print("== a damaged file is set aside, not deleted ==")
bad = book.path_for("Ega", "Ega 3")
os.makedirs(os.path.dirname(bad), exist_ok=True)
with open(bad, "wb") as handle:
    handle.write(b'{"maps": [ this is not json')
try:
    hurt = C.CoverageBook(TMP)
    got = hurt.map_for("Ega", "Ega 3", HOME[0], HOME[1], R)
    raised = None
except Exception as exc:
    raised = exc
check("loading it does not raise", raised is None, repr(raised))
check("a fresh map comes back", raised is None and got.points == [])
aside = glob.glob(bad + ".unreadable-*")
check("the damaged file is renamed aside", len(aside) == 1 and not os.path.exists(bad), aside)
check("with its contents intact",
      aside and open(aside[0], "rb").read() == b'{"maps": [ this is not json')
got.add_fix(*HOME)
check("the body can be saved again", hurt.save(got) and os.path.exists(bad))
check("and the damaged copy is still there", len(glob.glob(bad + ".unreadable-*")) == 1)
wrong = book.path_for("Ega", "Ega 4")
with open(wrong, "w", encoding="utf-8") as handle:
    json.dump([1, 2, 3], handle)
check("valid JSON of the wrong shape is set aside too",
      C.CoverageBook(TMP).maps_on("Ega", "Ega 4") == [] and glob.glob(wrong + ".unreadable-*"))
check("save of something that is not a map is refused", book.save("nope") is False)
blocked = C.CoverageBook(os.path.join(TMP, "a-file"))
open(os.path.join(TMP, "a-file"), "w").close()
check("save into a folder that cannot exist returns False", blocked.save(C.CoverageMap("A", "B", R)) is False)

print("== fast enough for every position update ==")
p = C.CoverageMap("Ega", "Ega 1", R)
p.set_centre(*HOME)
p.set_border(*dest(HOME[0], HOME[1], 90, 10000))
p.coverage()
started = time.perf_counter()
stored = 0
for k in range(300):
    # A spiral out from the centre, so every point paints fresh ground.
    spot = dest(HOME[0], HOME[1], (k * 37.0) % 360.0, 150.0 + 30.0 * k)
    stored += p.add_fix(*spot)
    p.coverage()
p.gaps()
painting = time.perf_counter() - started
check("300 points stored", stored == 300, stored)
check("300 points painted, with coverage after each, under 2 s", painting < 2.0, "%.3fs" % painting)
standing = dest(HOME[0], HOME[1], 0, 20)
started = time.perf_counter()
for k in range(10000):
    p.add_fix(standing[0] + (k % 3) * 1e-7, standing[1])
idle = time.perf_counter() - started
check("10,000 fixes that do not move far enough, under 2 s", idle < 2.0, "%.3fs" % idle)
check("and none of them were stored", len(p.points) == 301, len(p.points))
print("  (painting %.3fs, standing still %.3fs)" % (painting, idle))

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fails else 0)
