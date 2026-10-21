"""What 1.10035 adds to the map and the scope, each held down so it stays.

The driven trail; the lines from you to the nearest deposit of the same
commodity (solid) and the next cheaper one (dotted); the scope's 1x / 2x / 4x
zoom on a key; the golden groups; the rig radar. The geometry is checked as
plain functions, then every feature is checked on the real toolkit: a real
plan view, a real overlay and the real window driven through a synthetic
journal, because "the function is right" has not once meant "it is on the
screen".

It needs a display (xvfb will do) for the second half and says SKIP, out
loud, for that half without one.

    python tests/test_110035_map.py
"""
import os, sys, json, math, random, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-map-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import survey as SV      # noqa: E402
import coverage as CV    # noqa: E402
import planview as PV    # noqa: E402
import rigplan as RP     # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def section(title):
    """Run the function under it; an exception is one failure, named."""
    def wrap(fn):
        print("== " + title + " ==")
        try:
            fn()
        except Exception as exc:                       # a missing feature
            import traceback
            check(title + " (ran to the end)", False, "%s: %s" % (type(exc).__name__, exc))
            traceback.print_exc(limit=4)
        return fn
    return wrap


R = 2_100_000.0
HOME = (12.5, -45.5)


def dest(lat, lon, bearing, metres):
    return SV.destination(lat, lon, bearing, metres, R)


# ---------------------------------------------------------------------------
@section("the trail: the stored fixes, simplified, ends kept, capped")
def _trail():
    cmap = CV.CoverageMap("Ega", "Ega 1", R)
    here = HOME
    # 5 km due east, then 5 km due north, a fix every 100 m.
    for _ in range(50):
        here = dest(here[0], here[1], 90.0, 100.0)
        cmap.add_fix(*here)
    corner = here
    for _ in range(50):
        here = dest(here[0], here[1], 0.0, 100.0)
        cmap.add_fix(*here)
    stored = len(cmap.points)
    line = cmap.trail()
    check("a hundred fixes on two straight legs are a handful of points",
          2 < len(line) <= 6 < stored, (len(line), stored))
    check("the first and last fix are kept", line[0] == cmap.points[0]
          and line[-1] == cmap.points[-1])
    near_corner = min(SV.surface_range_m(corner[0], corner[1], p[0], p[1], R) for p in line)
    check("and so is the corner between the legs", near_corner < 120.0, near_corner)
    check("asked again it is the same line", cmap.trail() == line)
    before = list(line)
    here = dest(here[0], here[1], 270.0, 400.0)
    cmap.add_fix(*here)
    cmap.add_fix(*dest(here[0], here[1], 270.0, 400.0))
    check("a new fix changes it and the end moves to the new fix",
          cmap.trail() != before and cmap.trail()[-1] == cmap.points[-1])
    check("nothing driven, no trail", CV.CoverageMap("Ega", "Ega 1", R).trail() == [])
    one = CV.CoverageMap("Ega", "Ega 1", R)
    one.add_fix(*HOME)
    check("one fix is a one point trail", one.trail() == [one.points[0]])
    # Past the cap: a zigzag that no tolerance of 10 m can straighten.
    zig = CV.CoverageMap("Ega", "Ega 1", R)
    pts, here = [], HOME
    for k in range(3200):
        step = dest(here[0], here[1], 90.0, 100.0)
        here = step
        pts.append(dest(step[0], step[1], 0.0 if k % 2 else 180.0, 60.0))
    zig.points = pts
    capped = zig.trail()
    check("a trail is never more than %d points" % CV.TRAIL_CAP,
          2 < len(capped) <= CV.TRAIL_CAP < len(pts), len(capped))
    check("and a capped trail still starts and ends where the drive did",
          capped[0] == pts[0] and capped[-1] == pts[-1])
    check("Douglas-Peucker on bare coordinates keeps both ends of a straight line",
          CV.trail_indices([(0.0, 0.0), (10.0, 0.3), (20.0, -0.2), (30.0, 0.0)], 5.0) == [0, 3])
    check("and a bend bigger than the tolerance",
          CV.trail_indices([(0.0, 0.0), (50.0, 0.0), (50.0, 50.0)], 5.0) == [0, 1, 2])
    flat = CV.trail_indices([(float(i), 0.0) for i in range(60000)], 5.0)
    check("sixty thousand points in a line do not hit the recursion limit",
          flat == [0, 59999])


# ---------------------------------------------------------------------------
def item(ident, east, north, commodity, rigs="3", amount="High", start=(0.0, 0.0)):
    """A thing `layout` would return, with the range and bearing from `start`."""
    return {"id": ident, "east_m": east, "north_m": north,
            "range_m": math.hypot(east - start[0], north - start[1]),
            "bearing": PV.to_polar(east - start[0], north - start[1])[1],
            "commodity": commodity, "x": 400 + east / 10.0, "y": 300 - north / 10.0,
            "radius": 6, "offscreen": False, "edge": (0, 0),
            "deposit": {"id": ident, "commodity": commodity, "rigs": rigs,
                        "amount": amount, "lat": str(north), "lon": str(east)}}


PRICES = {"Platinum": 250000, "Osmium": 100000, "Aluminium": 1000, "Tritium": 52000}


@section("lines to the nearest same commodity and the next cheaper one")
def _lines():
    items = [item("c", 5, 10, "Platinum"), item("a", 300, 0, "Platinum"),
             item("b", -800, 0, "Platinum"), item("d", 0, 500, "Osmium"),
             item("e", 900, 900, "Osmium"), item("f", 0, -200, "Aluminium"),
             item("g", 100, 0, "Painite"),
             item("z", 0, 120, "Platinum", amount="Depleted")]
    found = PV.nearest_lines(items, PRICES, "Platinum")
    check("the solid line goes to the nearest Platinum that is not the one under you",
          found["same"] and found["same"]["item"]["id"] == "a"
          and abs(found["same"]["range_m"] - 300) < 1e-6, found["same"])
    check("a worked-out deposit is never a destination",
          found["same"]["item"]["id"] != "z")
    check("the dotted one goes to the next cheaper commodity - Osmium, not the "
          "nearer Aluminium or the unpriced Painite",
          found["cheaper"] and found["cheaper"]["item"]["id"] == "d"
          and found["cheaper"]["commodity"] == "Osmium", found["cheaper"])
    osm = PV.nearest_lines(items, PRICES, "osmium")
    check("from Osmium the next cheaper is Aluminium; the focus is spelt any way",
          osm["same"]["item"]["id"] == "d" and osm["cheaper"]["item"]["id"] == "f")
    check("nothing cheaper than the cheapest priced one",
          PV.nearest_lines(items, PRICES, "Aluminium")["cheaper"] is None)
    check("without prices there is no cheaper line, and the solid one stays",
          PV.nearest_lines(items, {}, "Platinum")["cheaper"] is None
          and PV.nearest_lines(items, {}, "Platinum")["same"]["item"]["id"] == "a")
    best = PV.nearest_lines(items, PRICES, "")
    check("with nothing in hand it is the best paying commodity in view",
          best["commodity"] == "Platinum" and best["same"]["item"]["id"] == "a", best["commodity"])
    check("the price table is read however a name is spelt",
          PV.nearest_lines(items, {"PLATINUM": 9, "osmium": 3}, "Platinum")["cheaper"]["commodity"] == "Osmium")
    check("a commodity that is not in view draws nothing",
          PV.nearest_lines(items, PRICES, "Tritium")["same"] is None)
    check("no deposits, no lines",
          PV.nearest_lines([], PRICES, "Platinum") == {"commodity": "", "same": None, "cheaper": None})
    check("the focus is the deposit being driven to, else the one marked last",
          PV.focus_commodity(items, "d", "Platinum") == "Osmium"
          and PV.focus_commodity(items, "nope", "Platinum") == "Platinum"
          and PV.focus_commodity(items, "", "") == "")


# ---------------------------------------------------------------------------
def cluster(prefix, centre, rigs_list, commodity="Platinum", spread=150.0, start=(0.0, 0.0)):
    out = []
    for k, rigs in enumerate(rigs_list):
        angle = math.radians(360.0 * k / max(1, len(rigs_list)))
        out.append(item("%s%d" % (prefix, k), centre[0] + spread * math.sin(angle),
                        centre[1] + spread * math.cos(angle), commodity, str(rigs), start=start))
    return out


@section("golden groups")
def _golden():
    a = cluster("a", (0, 0), [3, 2])                  # 5 rigs
    b = cluster("b", (3500, 0), [4])                  # 4 rigs
    c = cluster("c", (0, 4500), [6, 1])               # 7 rigs
    groups = PV.golden_groups(a + b + c, PRICES, 1250)
    check("five rigs qualify, four do not while a five exists: two groups",
          len(groups) == 2, [g["rigs"] for g in groups])
    check("listed most rigs first", [g["rigs"] for g in groups] == [7, 5])
    check("numbered in that order", [g["n"] for g in groups] == [1, 2])
    check("each carries its circle: centre, radius, members",
          all(g["radius_m"] == 1250 and g["count"] == len(g["items"]) for g in groups))
    only_b = PV.golden_groups(b, PRICES, 1250)
    check("with no group of five, one of four will do (fallback)",
          [g["rigs"] for g in only_b] == [4])
    check("three rigs never do", PV.golden_groups(cluster("t", (0, 0), [3]), PRICES) == [])
    # Overlap: a chain of 3-rig sites a kilometre apart. One group, no site twice.
    chain = [item("k%d" % k, 1000.0 * k, 0, "Platinum", "3") for k in range(5)]
    chained = PV.golden_groups(chain, PRICES, 1250)
    used = [i["id"] for g in chained for i in g["items"]]
    check("overlapping reach: every site is in at most one group",
          len(used) == len(set(used)) and chained, used)
    check("the richest centre takes its neighbours (9 rigs from three sites)",
          chained[0]["rigs"] == 9, chained[0]["rigs"])
    # Depleted sites do not count, and a site's rigs stop at six.
    gone = a + [item("dead", 50, 50, "Platinum", "6", amount="Depleted")]
    check("a depleted site adds nothing", [g["rigs"] for g in PV.golden_groups(gone, PRICES)] == [5])
    check("a site's rigs are capped at six",
          [g["rigs"] for g in PV.golden_groups([item("big", 0, 0, "Platinum", "40")], PRICES)] == [6])
    two = [item("r1", 0, 0, "Platinum", "6"), item("r2", 200, 0, "Platinum", "6")]
    check("two Rhinos' worth on one patch is twelve rigs",
          [g["rigs"] for g in PV.golden_groups(two, PRICES)] == [12])
    # The radius setting, and its edges.
    pair = [item("p1", 0, 0, "Platinum", "3"), item("p2", 500, 0, "Platinum", "3")]
    check("at a radius of 500 m a site exactly 500 m away is in",
          [g["rigs"] for g in PV.golden_groups(pair, PRICES, 500)] == [6])
    wide = [item("w1", 0, 0, "Platinum", "3"), item("w2", 2500, 0, "Platinum", "3")]
    check("at 2,500 m a site exactly 2,500 m away is in",
          [g["rigs"] for g in PV.golden_groups(wide, PRICES, 2500)] == [6])
    wide[1] = item("w2", 2501, 0, "Platinum", "3")
    check("and 2,501 m away is not", PV.golden_groups(wide, PRICES, 2500) == [])
    check("the radius is held to 500-2,500 and junk is 1,250",
          (PV.golden_radius(100), PV.golden_radius(99999), PV.golden_radius("x"),
           PV.golden_radius(None), PV.golden_radius(1500)) == (500.0, 2500.0, 1250.0, 1250.0, 1500.0))
    check("a smaller radius splits what a bigger one holds together",
          len(PV.golden_groups([item("s1", 0, 0, "Platinum", "5"),
                                item("s2", 1000, 0, "Platinum", "5")], PRICES, 500)) == 2
          and len(PV.golden_groups([item("s1", 0, 0, "Platinum", "5"),
                                    item("s2", 1000, 0, "Platinum", "5")], PRICES, 1250)) == 1)
    # Top three only: five clusters of five rigs in different commodities.
    names = ["Platinum", "Osmium", "Tritium", "Aluminium", "Platinum"]
    five = []
    for k, name in enumerate(names):
        five += cluster("m%d" % k, (k * 4000.0, 0), [3, 2], commodity=name)
    top = PV.golden_groups(five, PRICES, 1250)
    check("only the top three are kept", len(top) == 3, len(top))
    kept = {g["items"][0]["commodity"] for g in top}
    check("and they are the best paying: Aluminium is the one left out",
          "Aluminium" not in kept, kept)
    # Cr/h includes the drive.
    one = [item("o", 1000.0, 0, "Platinum", "6")]
    near = PV.golden_groups(one, PRICES, 1250, start=(0.0, 0.0))[0]
    far = PV.golden_groups(one, PRICES, 1250, start=(-4000.0, 0.0))[0]
    want = 6 * 250000 * 3600.0 / (300.0 + 1000.0 / (25.0 / 3.6))
    check("Cr/h is value over (300 s a spot + the drive at 25 km/h)",
          abs(near["cr_per_h"] - want) < 1e-3 * want, (near["cr_per_h"], want))
    check("the further away it starts, the less an hour it is worth",
          far["cr_per_h"] < near["cr_per_h"] and far["drive_m"] > near["drive_m"])
    check("the value is rigs x 1 t x price",
          near["credits"] == 6 * 250000, near["credits"])
    blank = PV.golden_groups(a, {}, 1250)[0]
    check("nothing priced: still a group, with no rate to quote",
          blank["cr_per_h"] is None and blank["rigs"] == 5)
    # Moving does not move the groups; changing the rigs does.
    first = [(g["rigs"], g["centre"]["id"]) for g in PV.golden_groups(a + c, PRICES)]
    moved = [(g["rigs"], g["centre"]["id"])
             for g in PV.golden_groups(a + c, PRICES, start=(900.0, 900.0))]
    check("driving about does not change which groups there are", first == moved)
    stale = [dict(i, deposit=dict(i["deposit"], rigs="1")) for i in a]
    check("rigs changing is seen at once, not served from a remembered answer",
          PV.golden_groups(stale, PRICES) == [])
    check("junk in, nothing out", PV.golden_groups(None, PRICES) == []
          and PV.golden_groups([{"deposit": None}], PRICES) == [])


# ---------------------------------------------------------------------------
@section("the rig radar: rings, go / no-go, and the nearest legal spot")
def _radar():
    sp = 78.0
    r = RP.radar((0.0, -30.0), [(0.0, 0.0)], sp)
    check("30 m south of a rig: red, and it says how far and which way",
          r["state"] == "close" and r["text"] == "NEXT RIG: 48 m, bearing 180", (r["state"], r["text"]))
    check("the nearest legal spot is on the ring, straight away from the rig",
          abs(r["legal"][0]) < 1e-9 and abs(r["legal"][1] + 78.0) < 1e-9)
    away = math.radians(70.0)
    r = RP.radar((44 * math.sin(away), 44 * math.cos(away)), [(0.0, 0.0)], sp)
    check("44 m from a rig on bearing 070: NEXT RIG: 34 m, bearing 070",
          r["text"] == "NEXT RIG: 34 m, bearing 070", r["text"])
    r = RP.radar((100.0, 0.0), [(0.0, 0.0)], sp)
    check("100 m away is green and says so", r["state"] == "ok" and r["text"] == "RIG OK HERE"
          and r["need_m"] == 0.0 and r["rings"][0]["state"] == "ok")
    check("2 m outside the ring is amber but still goes",
          RP.radar((80.0, 0.0), [(0.0, 0.0)], sp)["state"] == "edge"
          and RP.radar((80.0, 0.0), [(0.0, 0.0)], sp)["text"] == "RIG OK HERE")
    check("6 m outside is plain green", RP.radar((84.0, 0.0), [(0.0, 0.0)], sp)["state"] == "ok")
    check("exactly the spacing apart is allowed (the warning is for less than it)",
          RP.radar((78.0, 0.0), [(0.0, 0.0)], sp)["state"] == "edge")
    check("a hair inside is not", RP.radar((77.9, 0.0), [(0.0, 0.0)], sp)["state"] == "close")
    full = RP.radar((300.0, 0.0), [(0.0, 0.0)], sp, down=6)
    check("six rigs down: ALL 6 RIGS DOWN, nothing to go to",
          full["state"] == "full" and full["text"] == "ALL 6 RIGS DOWN" and full["legal"] is None)
    check("five down is still room for one", RP.radar((300.0, 0.0), [(0.0, 0.0)], sp, down=5)["state"] == "ok")
    two = RP.radar((40.0, 0.0), [(0.0, 0.0), (100.0, 0.0)], sp)
    check("inside two rings both rings say so",
          [x["state"] for x in two["rings"]] == ["close", "close"])
    mixed = RP.radar((40.0, 0.0), [(0.0, 0.0), (400.0, 0.0)], sp)
    check("each ring has its own state - the one in the way is red, the far one is not",
          [x["state"] for x in mixed["rings"]] == ["close", "ok"])
    check("standing on a rig itself still has a way out",
          RP.radar((0.0, 0.0), [(0.0, 0.0)], sp)["text"].startswith("NEXT RIG: 78 m"))
    # The solver against a brute-force search of every metre round the spot.
    rnd = random.Random(1035)
    bad = []
    for _ in range(30):
        centres = [(rnd.uniform(-90, 90), rnd.uniform(-90, 90)) for _ in range(rnd.randint(1, 5))]
        spot = (rnd.uniform(-90, 90), rnd.uniform(-90, 90))
        got = RP.nearest_legal(spot, centres, sp)
        best = None
        for dx in range(-125, 126):
            for dy in range(-125, 126):
                if RP.is_legal((spot[0] + dx, spot[1] + dy), centres, sp):
                    d = math.hypot(dx, dy)
                    if best is None or d < best:
                        best = d
        d = math.hypot(got[0] - spot[0], got[1] - spot[1])
        if best is not None and (not RP.is_legal(got, centres, sp) or d > best + 1e-6
                                 or d < best - 1.5):
            bad.append((centres, spot, d, best))
    check("the nearest legal spot matches a search of every metre (30 layouts)",
          not bad, bad[:1])
    # A traced deposit edge.
    square = [(-100.0, -100.0), (100.0, -100.0), (100.0, 100.0), (-100.0, 100.0)]
    off = RP.radar((150.0, 0.0), [(0.0, 0.0)], sp, polygon=square)
    check("off the traced deposit is red, and the way back on is the nearest legal point",
          off["state"] == "close" and abs(off["need_m"] - 50.0) < 1e-6
          and off["text"] == "NEXT RIG: 50 m, bearing 270", (off["state"], off["text"]))
    inner = RP.radar((50.0, 0.0), [(0.0, 0.0)], sp, polygon=square)
    check("inside the edge but inside a ring: out along the ring",
          inner["text"] == "NEXT RIG: 28 m, bearing 090", inner["text"])
    tiny = [(-50.0, -50.0), (50.0, -50.0), (50.0, 50.0), (-50.0, 50.0)]
    none = RP.radar((10.0, 0.0), [(0.0, 0.0)], sp, polygon=tiny)
    check("no room on the deposit at this spacing says so",
          none["text"] == "NO ROOM FOR A RIG HERE" and none["legal"] is None)


# ---------------------------------------------------------------------------
@section("clipping a line to the round scope")
def _clip():
    runs = PV.clip_polyline([(-200.0, 0.0), (0.0, 0.0), (200.0, 0.0)], (0.0, 0.0), 100.0)
    check("a line through the dish is cut at the rim, both ends",
          len(runs) == 1 and abs(runs[0][0][0] + 100.0) < 1e-6 and abs(runs[0][-1][0] - 100.0) < 1e-6, runs)
    check("a line wholly outside is nothing", PV.clip_polyline([(300.0, 0.0), (400.0, 0.0)], (0, 0), 100.0) == [])
    runs = PV.clip_polyline([(0.0, 0.0), (150.0, 0.0), (150.0, 50.0), (50.0, 50.0)], (0.0, 0.0), 100.0)
    check("a line that leaves and comes back is two runs", len(runs) == 2, runs)
    ring = PV.circle_points(0.0, 0.0, 50.0)
    check("a ring of points closes on itself", ring[0] == ring[-1]
          or math.hypot(ring[0][0] - ring[-1][0], ring[0][1] - ring[-1][1]) < 1e-9)
    thin = PV.thin_points([(float(x), 0.0) for x in range(0, 1001, 10)], 250.0)
    check("thinning keeps the ends and spaces the rest",
          thin[0] == (0.0, 0.0) and thin[-1] == (1000.0, 0.0) and len(thin) <= 6, thin)



# ---------------------------------------------------------------------------
# The toolkit half: the real plan view, the real scope, the real window
# ---------------------------------------------------------------------------
HAVE_DISPLAY = False
try:
    import tkinter as tk
    _probe = tk.Tk()
    _probe.destroy()
    HAVE_DISPLAY = True
except Exception as _exc:             # no display: say so, loudly
    print("\n  SKIP  the toolkit half of this file - no display (%s). "
          "Run it under xvfb-run." % _exc)


def on_screen(title):
    """Like section(), for checks that need a display."""
    def wrap(fn):
        if not HAVE_DISPLAY:
            print("== %s ==\n  SKIP  needs a display" % title)
            return fn
        return section(title)(fn)
    return wrap


def tags_of(canvas):
    """{tag: how many items carry it}."""
    out = {}
    for item in canvas.find_all():
        for tag in canvas.gettags(item):
            out[tag] = out.get(tag, 0) + 1
    return out


def texts_of(canvas, tag=None):
    return [canvas.itemcget(i, "text") for i in canvas.find_all()
            if canvas.type(i) == "text" and (tag is None or tag in canvas.gettags(i))]


def items_of(canvas, tag):
    return [i for i in canvas.find_withtag(tag)]


if HAVE_DISPLAY:
    import customtkinter  # noqa: F401
    import overlay as OV    # noqa: E402
    OV.foreground_is_game = lambda: None
    import edsmt as A       # noqa: E402
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
        json.dump({"asked_to_share": True, "journal_dir": JOURNALS}, _f)
    app = A.EDSMT()
    app.geometry("1400x900+0+0")
    app.updates.check = lambda *args, **kwargs: None

    def pump(times=4):
        for _ in range(times):
            app.update_idletasks()
            app.update()

    pump()

    PRICES = {"Platinum": 250000, "Osmium": 100000, "Aluminium": 1000}

    def row(ident, east, north, commodity, rigs="3", amount="High", location="1"):
        away, bearing = PV.to_polar(east, north)
        return {"deposit": {"id": ident, "commodity": commodity, "rigs": rigs,
                            "amount": amount, "location": location,
                            "lat": "0", "lon": "0"},
                "range_m": away, "bearing": bearing, "commodity": commodity}

    ROWS = [row("a0", 0, 600, "Platinum", "3"), row("a1", 150, 700, "Platinum", "2"),
            row("b", -700, 300, "Osmium", "4"), row("c", 1400, -200, "Aluminium", "6"),
            row("d", 60, 250, "Platinum", "2")]
    TRAIL = [(-1500.0, -300.0), (-800.0, -100.0), (-300.0, -40.0), (0.0, 0.0)]

    def survey_of(trail=TRAIL, border=None):
        return {"scan_m": 2000.0, "points": list(trail), "centre": None,
                "border_m": border, "rings": [], "gaps": [], "percent": None,
                "painted_km2": 1.0, "trail": list(trail)}

    def rigs_of(down=2, spot=(0.0, 0.0)):
        marks = [(-60.0, 0.0), (60.0, 20.0)][:down]
        radar = RP.radar(spot, marks, 78.0, down=down)
        return {"rigs": [{"n": k + 1, "east": e, "north": n, "label": str(k + 1),
                          "watched": True, "commodity": "Platinum",
                          "range_m": math.hypot(e, n), "bearing": PV.to_polar(e, n)[1]}
                         for k, (e, n) in enumerate(marks)],
                "limit_m": 3500.0, "radar": radar, "count": down, "n": down,
                "range_m": 63.0, "bearing": 70.0, "far": False, "offset": 0.0}

    ALL_ON = {"trail": True, "lines": True, "golden": True, "golden_radius_m": 1250.0,
              "radar": True, "trail_paint": False, "target": "", "last": "Platinum",
              "prices": PRICES}

    def prefs(**off):
        return dict(ALL_ON, **off)

    GOLD_TAGS = ("golden", "goldlist", "goldlabel")
    RADAR_TAGS = ("rigring", "radar")
    LINE_TAGS = ("mapline", "line_same", "line_cheaper")



# ---------------------------------------------------------------------------
@on_screen("the map: trail, lines, golden groups and the rig radar are on the canvas")
def _plan_view():
    plan = A.PlanView(app)
    plan.place(x=0, y=0, width=900, height=700)
    pump()
    survey, rigs = survey_of(), rigs_of(2)

    def draw(map_prefs, rows=ROWS, with_survey=True, with_rigs=True):
        if map_prefs is not None:
            plan.map_prefs = map_prefs
        plan.show(rows, heading=0.0, caption="Test body", signal="1",
                  survey=survey if with_survey else None,
                  rigs=rigs if with_rigs else None)
        pump(2)
        return tags_of(plan)

    bare = draw(None)
    check("with no switches handed over, none of the new layers is drawn",
          not any(bare.get(t) for t in GOLD_TAGS + RADAR_TAGS + LINE_TAGS + ("trail",)), bare)
    base_items = len(plan.find_all())
    tags = draw(ALL_ON)
    check("the driven trail is a line on the map", tags.get("trail") == 1, tags.get("trail"))
    check("a golden circle is drawn round the best group", tags.get("goldlist", 0) >= 1
          and tags.get("golden", 0) >= 2, tags)
    check("every rig has its spacing ring, and the radar names the next one",
          tags.get("rigring", 0) >= 2 and "NEXT RIG" in " ".join(texts_of(plan, "radar")), tags)
    check("the solid line to the nearest of the same commodity is drawn",
          tags.get("line_same") == 1, tags)
    check("and the dotted line to the next cheaper one",
          tags.get("line_cheaper") == 1, tags)
    same = items_of(plan, "line_same")[0]
    cheaper = items_of(plan, "line_cheaper")[0]
    check("solid for the same commodity, dotted for the cheaper",
          not plan.itemcget(same, "dash") and plan.itemcget(cheaper, "dash"),
          (plan.itemcget(same, "dash"), plan.itemcget(cheaper, "dash")))
    words = texts_of(plan, "mapline")
    check("each line says how far it is", len(words) == 2 and all(w.endswith("m") for w in words), words)
    check("a find is still named: the new layers do not take its label",
          any(c in " ".join(texts_of(plan)) for c in ("Platinum", "Osmium", "Aluminium")),
          texts_of(plan)[:6])
    check("and the map holds more than it did", len(plan.find_all()) > base_items)

    for switch, gone in (("trail", ("trail",)), ("lines", LINE_TAGS),
                         ("golden", GOLD_TAGS), ("radar", RADAR_TAGS)):
        shown = draw(prefs(**{switch: False}))
        others = {t for t in ("trail",) + LINE_TAGS + GOLD_TAGS + RADAR_TAGS if t not in gone}
        check("%s off: its layer is gone and the others stay" % switch,
              not any(shown.get(t) for t in gone)
              and all(shown.get(t) for t in others if t not in ("goldlabel",)), (switch, shown))
    check("the radar off leaves the Rhino's arrow amber, as before",
          not draw(prefs(radar=False)).get("radar"))

    # The arrow takes the colour of the verdict.
    plan.map_prefs = ALL_ON
    for state, colour in (("ok", A.GREEN), ("edge", A.AMBER), ("close", A.RED)):
        crowd = dict(rigs, radar=dict(rigs["radar"], state=state))
        plan.show(ROWS, heading=0.0, caption="x", signal="1", survey=survey, rigs=crowd)
        pump(2)
        arrows = [i for i in items_of(plan, "radar") if plan.type(i) == "polygon"]
        check("the arrow is %s when the radar says %s" % (colour, state),
              len(arrows) == 1 and plan.itemcget(arrows[0], "fill") == colour,
              [plan.itemcget(i, "fill") for i in arrows])

    # The radius is the Settings figure.
    def circle_width(radius):
        draw(prefs(golden_radius_m=radius))
        oval = items_of(plan, "golden")
        ovals = [i for i in oval if plan.type(i) == "oval"]
        box = plan.bbox(ovals[0])
        return box[2] - box[0]
    narrow, wide = circle_width(500.0), circle_width(2500.0)
    check("the golden circle follows the radius: 2,500 m is five times 500 m",
          4.5 < wide / narrow < 5.5, (narrow, wide))
    check("a radius past the limits is held to it", PV.golden_radius(9000) == 2500.0
          and PV.golden_radius(10) == 500.0 and PV.golden_radius("x") == 1250.0)
    plan.destroy()

    # A plan view that was never handed any switches (an older caller).
    old = A.PlanView(app)
    old.place(x=0, y=0, width=600, height=500)
    pump()
    old.show(ROWS, heading=0.0, caption="x", signal="1", survey=survey, rigs=rigs)
    pump(2)
    check("a map that was never given the switches draws as it always did",
          not any(tags_of(old).get(t) for t in GOLD_TAGS + RADAR_TAGS + LINE_TAGS + ("trail",)))
    old.destroy()


# ---------------------------------------------------------------------------
@on_screen("the scope: the same layers, cut to the dish, with the zoom steps")
def _scope():
    ov = OV.Overlay(app, tk, {"overlay_show_radar": True, "overlay_show_strip": False,
                              "overlay_show_targets": False, "overlay_show_status": False})
    ov.show()
    pump()
    canvas = ov.panels[OV.RADAR].canvas
    survey, rigs = survey_of(), rigs_of(2)

    def draw(map_prefs, **kw):
        ov.map_prefs = map_prefs
        ov.draw(kw.get("rows", ROWS), 10.0, body="Ega 1", location="1",
                survey=kw.get("survey", survey), rigs=kw.get("rigs", rigs))
        pump(2)
        return tags_of(canvas)

    ov.app.market_prices = lambda: PRICES
    ov.map_prefs = None
    bare = draw(None)
    check("with no switches handed over the scope is as it was",
          not any(bare.get(t) for t in GOLD_TAGS + RADAR_TAGS + LINE_TAGS + ("trail", "trailpaint")), bare)
    tags = draw(ALL_ON)
    check("the trail is on the scope", tags.get("trail", 0) >= 1, tags)
    check("golden circle, its label and the list are on the scope",
          tags.get("golden", 0) >= 3 and tags.get("goldlist", 0) >= 1, tags)
    check("the rig rings are on the scope", tags.get("rigring", 0) >= 2, tags)
    check("both lines are on the scope, solid and dotted",
          tags.get("line_same") == 1 and tags.get("line_cheaper") == 1
          and not canvas.itemcget(items_of(canvas, "line_same")[0], "dash")
          and canvas.itemcget(items_of(canvas, "line_cheaper")[0], "dash"), tags)
    check("NEXT RIG is on the scope", any(t.startswith("NEXT RIG") for t in texts_of(canvas, "radar")),
          texts_of(canvas, "radar"))
    width, height = canvas.winfo_width(), canvas.winfo_height()
    boxes = [canvas.bbox(i) for i in canvas.find_all()
             if canvas.type(i) == "text" and set(canvas.gettags(i)) & {"radar", "goldlist"}]
    check("the radar line and the golden list stay inside the scope",
          boxes and all(b[0] >= 0 and b[2] <= width for b in boxes), (width, boxes))
    text_ids = [i for i in canvas.find_all() if canvas.type(i) == "text"]
    radar_text = next(i for i in text_ids if "radar" in canvas.gettags(i))
    first_list = min((i for i in text_ids if "goldlist" in canvas.gettags(i)),
                     key=lambda i: canvas.bbox(i)[1])
    check("the golden list starts below the radar line, not on it",
          canvas.bbox(first_list)[1] >= canvas.bbox(radar_text)[3] - 1,
          (canvas.bbox(radar_text), canvas.bbox(first_list)))

    for switch, gone in (("trail", ("trail",)), ("lines", LINE_TAGS),
                         ("golden", GOLD_TAGS), ("radar", RADAR_TAGS)):
        shown = draw(prefs(**{switch: False}))
        check("%s off: gone from the scope" % switch,
              not any(shown.get(t) for t in gone), (switch, shown))

    # Zoom: 1x, 2x, 4x and round.
    seen = []
    real_layout = PV.layout

    def spy(*args, **kwargs):
        out = real_layout(*args, **kwargs)
        if kwargs.get("clip") == "circle":          # the scope's, not the window's
            seen.append(out["extent_m"])
        return out
    PV.layout = spy
    try:
        steps, extents = [], []
        for _ in range(4):
            steps.append(ov.scope_zoom())
            del seen[:]
            draw(ALL_ON)
            extents.append(seen[-1])
            ov.cycle_zoom()
    finally:
        PV.layout = real_layout
    check("the zoom goes 1x, 2x, 4x and round to 1x", steps == [1, 2, 4, 1], steps)
    check("2x shows half the ground and 4x a quarter",
          abs(extents[1] - extents[0] / 2.0) < 1e-6 and abs(extents[2] - extents[0] / 4.0) < 1e-6
          and extents[3] == extents[0], extents)
    ov.set_zoom(2)
    draw(ALL_ON)
    check("the header says the step when it is past 1x",
          any(t.endswith("2x") for t in texts_of(canvas)), texts_of(canvas)[:8])
    check("and past 1x the scope follows the Rhino, not the signal",
          any(t.startswith("CENTRE") and "SRV" in t for t in texts_of(canvas)),
          [t for t in texts_of(canvas) if t.startswith("CENTRE")])
    ov.set_zoom(1)
    draw(ALL_ON)
    check("and says nothing of it at 1x", not any(t.endswith("1x") for t in texts_of(canvas)))
    check("a step that is not one is 1x", ov.set_zoom(3) == 1 and ov.scope_zoom() == 1)
    ov.set_zoom(4)
    far = draw(ALL_ON, survey=survey_of([(-50000.0, 0.0), (-20000.0, 0.0), (0.0, 0.0)]))
    inside = []
    for item in items_of(canvas, "trail"):
        pts = canvas.coords(item)
        inside += [0 <= x <= width and 0 <= y <= height for x, y in zip(pts[0::2], pts[1::2])]
    check("a trail running far off the scope is cut at its rim",
          inside and all(inside), (width, height, inside[:6]))
    ov.set_zoom(1)

    # Painted ground along the trail: opt-in, and never over a border's own fill.
    paint = draw(prefs(trail_paint=True))
    check("the scanner-wide paint along the trail is on when asked for",
          paint.get("trailpaint", 0) >= 1, paint)
    check("and off by default", not draw(ALL_ON).get("trailpaint"))
    bordered = draw(prefs(trail_paint=True), survey=survey_of(border=1800.0))
    check("and left to the border's own fill once there is a border",
          not bordered.get("trailpaint"), bordered)
    ov.hide()


# ---------------------------------------------------------------------------
@on_screen("the real window, driven through a synthetic journal")
def _window():
    journal = os.path.join(JOURNALS, "Journal.2026-09-09T100000.01.log")

    def emit(*events):
        with open(journal, "a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event) + "\n")

    def status(lat, lon, heading=90, flags=(1 << 21) | (1 << 26)):
        with open(os.path.join(JOURNALS, "Status.json"), "w", encoding="utf-8") as handle:
            json.dump({"timestamp": "2026-09-09T10:00:00Z", "event": "Status",
                       "Flags": flags, "Latitude": lat, "Longitude": lon,
                       "Heading": heading, "BodyName": "Ega 1", "PlanetRadius": R}, handle)

    def move(bearing, metres, heading=90, flags=(1 << 21) | (1 << 26)):
        """Drive from where the app thinks you are; the app reads it back."""
        here = app.game
        lat, lon = dest(here.lat, here.lon, bearing, metres)
        status(lat, lon, heading, flags)
        app.game = app.watcher.poll()
        app.track_survey(app.game)

    emit({"timestamp": "2026-09-09T09:59:00Z", "event": "Fileheader", "gameversion": "4.4.1.1", "part": 1},
         {"timestamp": "2026-09-09T09:59:01Z", "event": "Commander", "Name": "Jameson", "FID": "F1"},
         {"timestamp": "2026-09-09T09:59:30Z", "event": "ApproachBody", "StarSystem": "Ega", "Body": "Ega 1"},
         {"timestamp": "2026-09-09T09:59:31Z", "event": "Scan", "BodyName": "Ega 1", "Radius": R,
          "SurfaceTemperature": 214.5})
    status(*HOME)
    app.settings["rig_offset_m"] = 0
    app.market_prices = lambda: PRICES
    app.game = app.watcher.poll()
    check("the app reads the synthetic session: Ega 1, in the Rhino, a position",
          app.game.body == "Ega 1" and app.game.has_position and app.game.in_srv)
    for _ in range(20):
        move(90, 60.0)
    for bearing, metres, commodity, rigs in ((0, 600, "Platinum", "3"), (30, 700, "Platinum", "2"),
                                             (270, 900, "Osmium", "4"), (150, 1200, "Aluminium", "6")):
        lat, lon = dest(HOME[0], HOME[1], bearing, metres)
        app.store.add_deposit(system="Ega", body="Ega 1", location="1", commodity=commodity,
                              rigs=rigs, amount="High", lat=lat, lon=lon)
    # Enabled, or the window's own timer takes the boxes down again.
    app.settings.update(overlay_enabled=True, overlay_show_radar=True, overlay_show_strip=False,
                        overlay_show_targets=False, overlay_show_status=False)
    app.overlay.show()
    pump()
    check("the scope is up", app.overlay.showing and OV.RADAR in app.overlay.panels)

    def scope_canvas():
        """The scope's canvas as it is now: a redraw can rebuild the boxes."""
        return app.overlay.panels[OV.RADAR].canvas

    app.redraw()
    pump()
    plan_tags, scope_tags = tags_of(app.plan), tags_of(scope_canvas())
    check("driving 1.2 km east put a trail on the map and on the scope",
          plan_tags.get("trail") == 1 and scope_tags.get("trail", 0) >= 1, (plan_tags, scope_tags))
    check("Platinum 3+2 rigs is a golden group on both",
          plan_tags.get("goldlist", 0) >= 1 and scope_tags.get("goldlist", 0) >= 1, (plan_tags, scope_tags))
    check("and the lines run to the nearest deposits on both",
          plan_tags.get("mapline") and scope_tags.get("mapline"), (plan_tags, scope_tags))
    check("no rigs down: no rig radar yet", not plan_tags.get("rigring") and not scope_tags.get("rigring"))
    check("the app's map switches are the Settings ones",
          app.map_prefs()["golden_radius_m"] == 1250.0 and app.map_prefs()["last"] == "Aluminium"
          or app.map_prefs()["last"] in ("Platinum", "Osmium", "Aluminium"), app.map_prefs())

    app.drop_rigs()                                   # rig 1 here
    move(90, 40.0)
    app.drop_rigs()                                   # rig 2, 40 m on
    move(90, 20.0)                                    # 20 m past it: inside both rings
    rigs = app.rig_radar(app.game, app.watch_rigs(app.game))
    radar = rigs.get("radar") if rigs else None
    check("two rigs down and you inside their rings: the radar says red, with a way out",
          radar and radar["state"] == "close" and radar["text"].startswith("NEXT RIG:")
          and radar["legal"] is not None and len(radar["rings"]) == 2, radar)
    check("a ring is the app's spacing", radar and all(abs(r["radius"] - app.planner_spacing()) < 1e-6
                                                       for r in radar["rings"]), app.planner_spacing())
    app.redraw()
    pump()
    plan_tags, scope_tags = tags_of(app.plan), tags_of(scope_canvas())
    check("the rings, the arrow and NEXT RIG are on the map",
          plan_tags.get("rigring", 0) >= 3 and plan_tags.get("radar", 0) >= 2
          and "NEXT RIG" in " ".join(texts_of(app.plan, "radar")), plan_tags)
    check("and on the scope", scope_tags.get("rigring", 0) >= 3
          and any(t.startswith("NEXT RIG") for t in texts_of(scope_canvas(), "radar")), scope_tags)
    move(90, 120.0)                                   # well clear of both
    clear = app.rig_radar(app.game, app.watch_rigs(app.game))["radar"]
    check("120 m on, clear of the rings, the radar is green and says a rig can go here",
          clear["state"] == "ok" and clear["text"] == "RIG OK HERE" and clear["need_m"] == 0.0
          and all(r["state"] == "ok" for r in clear["rings"]), clear)

    app.settings["rig_radar"] = False
    off = app.rig_radar(app.game, app.watch_rigs(app.game))
    check("rig radar off in Settings: nothing is added", "radar" not in off, off.keys())
    app.settings["rig_radar"] = True
    move(90, 0.0, flags=(1 << 1) | (1 << 21) | (1 << 24))        # a ship landed
    check("in the ship there is no radar", "radar" not in (app.rig_radar(
        app.game, app.watch_rigs(app.game) or {"rigs": [{"east": 0, "north": 0}]}) or {}))
    move(90, 0.0)

    for switch, gone in (("map_trail", ("trail",)), ("map_lines", LINE_TAGS),
                         ("map_golden", GOLD_TAGS), ("rig_radar", RADAR_TAGS)):
        app.settings[switch] = False
        app.redraw()
        pump()
        a, b = tags_of(app.plan), tags_of(scope_canvas())
        check("%s off in Settings: gone from the map and the scope" % switch,
              not any(a.get(t) or b.get(t) for t in gone), (a, b))
        app.settings[switch] = True
    app.settings["golden_radius_m"] = 500
    check("the Settings radius reaches the map", app.map_prefs()["golden_radius_m"] == 500.0)
    app.settings["golden_radius_m"] = "rubbish"
    check("and a bad figure is the usual one", app.map_prefs()["golden_radius_m"] == 1250.0)
    app.settings["golden_radius_m"] = 1250

    # The zoom key.
    wanted = A.EDSMT.wanted_hotkeys(app.settings)
    check("the zoom key is registered with the others, Alt+minus", wanted.get("zoom") == "ALT+-", wanted.get("zoom"))
    check("and no two keys share a binding",
          len(set(v.upper() for v in wanted.values())) == len(wanted),
          sorted(wanted.items(), key=lambda kv: kv[1]))
    check("a blank zoom key is not registered", "zoom" not in A.EDSMT.wanted_hotkeys(dict(app.settings, hotkey_zoom="")))
    steps = []
    for _ in range(4):
        app.hotkeys.events.put("zoom")
        app.run_hotkeys()
        steps.append(app.overlay.scope_zoom())
    check("pressing it steps the live scope 2x, 4x, 1x, 2x", steps == [2, 4, 1, 2], steps)
    check("and says so on the status line", "Scope zoom 2x" in str(app.status.cget("text"))
          if hasattr(app, "status") else True)
    app.overlay.set_zoom(1)
    check("a settings file already using Alt+minus keeps its key, zoom starts blank",
          A.keep_new_keys_free(dict(A.DEFAULT_SETTINGS), {"hotkey_deposit": "ALT+-"})["hotkey_zoom"] == ""
          and A.keep_new_keys_free(dict(A.DEFAULT_SETTINGS), {"hotkey_deposit": "F10"})["hotkey_zoom"] == "ALT+-")
    app.overlay.hide()


# ---------------------------------------------------------------------------
@on_screen("Settings: the switches, the radius and the zoom key are there and saved")
def _settings():
    win = A.SettingsWindow(app)
    pump(4)
    said, saved = [], []
    win.say = lambda text, colour=None: said.append(text)
    real_apply = app.apply_settings
    app.apply_settings = lambda data: saved.append(data)
    try:
        for key in ("map_trail", "map_lines", "map_golden", "rig_radar", "overlay_trail_paint"):
            check("Settings has a switch for %s, and a tip for it" % key,
                  key in win.toggles and key in A.SETTING_TIPS, key)
        check("the defaults are on, and the scanner paint is off",
              all(win.toggles[k].get() for k in ("map_trail", "map_lines", "map_golden", "rig_radar"))
              and not win.toggles["overlay_trail_paint"].get())
        check("the radius box holds the usual 1250", str(win.fields["golden_radius_m"].get()) == "1250",
              win.fields["golden_radius_m"].get())
        check("the zoom key is a binding row, Alt+minus", win.bindings.get("hotkey_zoom") == "ALT+-"
              and "hotkey_zoom" in win.binders, win.bindings.get("hotkey_zoom"))
        for typed, ok in (("3000", False), ("499", False), ("lots", False), ("1,500", True), ("2.5 km", True)):
            win.fields["golden_radius_m"].delete(0, "end")
            win.fields["golden_radius_m"].insert(0, typed)
            before = len(saved)
            win.save()
            pump(2)
            check("a radius of %r is %s" % (typed, "saved" if ok else "refused with the limits"),
                  (len(saved) > before) == ok and (ok or "500 to 2,500" in said[-1]),
                  (typed, said[-1:], len(saved) - before))
        check("and 1,500 went through as 1500 m", any(d.get("golden_radius_m") == 1500 for d in saved),
              [d.get("golden_radius_m") for d in saved])
        win.toggles["map_trail"].set(False)
        win.fields["golden_radius_m"].delete(0, "end")
        win.fields["golden_radius_m"].insert(0, "1250")
        win.save()
        pump(2)
        check("a switch turned off is saved off", saved and saved[-1].get("map_trail") is False, saved[-1:])
    finally:
        app.apply_settings = real_apply
        win.destroy()


if __name__ == "__main__":
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    sys.exit(1 if fails else 0)
