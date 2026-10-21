"""What 1.10035 adds to where you go next, each held down so it stays.

The guided survey (numbered waypoints on the compass, the scope and the map),
the rig radar drawn as a band, the rig planner out of beta with an exact
packing pass and the plan kept with the deposit, how many rigs fit, the
pointer to the parked Rhino and to the ship, the line from orbit, and three
overlay faults: the status box printing through the hold card, the targets
strip cutting its labels, and an arrow's distance printed over the map's
footer.

The geometry is checked as plain functions, then every feature is checked on
the real toolkit - a real overlay, a real plan view and the real window driven
through a synthetic Status.json and journal - because "the function is right"
has not once meant "it is on the screen".

It needs a display (xvfb will do) for the second half and says SKIP, out
loud, for that half without one.

    python tests/test_110035_survey.py
"""
import os, sys, json, math, random, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-survey-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import survey as SV       # noqa: E402
import coverage as CV     # noqa: E402
import planview as PV     # noqa: E402
import rigplan as RP      # noqa: E402
import waypoints as WP    # noqa: E402
import journal as JN      # noqa: E402

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


def GD_distance(metres):
    import guidance
    return guidance.distance_text(metres)


def metres_between(a, b):
    return SV.surface_range_m(a[0], a[1], b[0], b[1], R)


# ---------------------------------------------------------------------------
@section("ground already swept is known to the coverage map")
def _swept():
    cmap = CV.CoverageMap("Ega", "Ega 1", R)
    cmap.set_centre(*HOME)
    cmap.set_border(*dest(*HOME, 90.0, 5000.0))
    check("nothing driven: nothing is swept", not cmap.swept_at(*HOME))
    cmap.add_fix(*HOME)
    check("at the fix it is swept, with 500 m of margin round it",
          cmap.swept_at(*HOME, margin_m=500.0))
    check("800 m out is swept, with its margin",
          cmap.swept_at(*dest(*HOME, 0.0, 800.0), margin_m=500.0))
    check("2 km out is the edge of the scan: the ground beyond it is not",
          not cmap.swept_at(*dest(*HOME, 0.0, 2000.0), margin_m=500.0))
    check("4 km out is not swept at all", not cmap.swept_at(*dest(*HOME, 90.0, 4000.0)))
    check("a map with no radius answers no rather than raising",
          CV.CoverageMap("Ega", "Ega 1", 0).swept_at(*HOME) is False)


# ---------------------------------------------------------------------------
@section("the waypoints: centre first, rings out, 2 km at the most apart")
def _build():
    cmap = CV.CoverageMap("Ega", "Ega 1", R)
    cmap.set_centre(*HOME)
    cmap.set_border(*dest(*HOME, 90.0, 6000.0))
    points = WP.build(cmap.centre, cmap.border_m, R, cmap.scan_m)
    check("the centre is waypoint 1", points and points[0]["n"] == 1
          and points[0]["ring"] == 0 and metres_between(HOME, (points[0]["lat"], points[0]["lon"])) < 1.0,
          points[:1])
    check("they are numbered 1 to N with no gaps", [p["n"] for p in points] == list(range(1, len(points) + 1)))
    radii = sorted({p["radius_m"] for p in points if p["ring"]})
    gaps = [b - a for a, b in zip([0.0] + radii, radii)]
    check("rings go outward no more than 2 km apart", radii and max(gaps) <= WP.SPACING_M + 1.0, (radii, gaps))
    check("and the last ring's scan reaches the border", radii and radii[-1] + cmap.scan_m >= cmap.border_m - 1.0,
          (radii, cmap.border_m))
    worst = 0.0
    for ring in sorted({p["ring"] for p in points if p["ring"]}):
        on = [p for p in points if p["ring"] == ring]
        for a, b in zip(on, on[1:] + on[:1]):
            worst = max(worst, metres_between((a["lat"], a["lon"]), (b["lat"], b["lon"])))
    check("neighbours on a ring are no more than 2 km apart", worst <= WP.SPACING_M + 5.0, worst)
    check("every waypoint is inside the border plus one scan",
          all(metres_between(HOME, (p["lat"], p["lon"])) <= cmap.border_m + 1.0 for p in points))
    check("a start bearing starts the first ring there",
          metres_between((WP.build(cmap.centre, cmap.border_m, R, cmap.scan_m, start_bearing=90.0)[1]["lat"],
                          WP.build(cmap.centre, cmap.border_m, R, cmap.scan_m, start_bearing=90.0)[1]["lon"]),
                         dest(*HOME, 90.0, 2000.0)) < 5.0)
    small = CV.CoverageMap("Ega", "Ega 1", R)
    small.set_centre(*HOME)
    small.border_m = 1500.0
    check("a border inside one scan is the centre alone",
          len(WP.build(small.centre, small.border_m, R, small.scan_m)) == 1)
    # Swept ground is skipped.
    cmap.add_fix(*HOME)
    after = WP.build(cmap.centre, cmap.border_m, R, cmap.scan_m, swept=cmap.swept_at)
    check("standing at the centre sweeps the centre: waypoint 1 is on the first ring",
          len(after) == len(points) - 1 and after[0]["ring"] == 1 and after[0]["n"] == 1,
          (len(after), len(points), after[:1]))
    for step in range(1, 7):
        cmap.add_fix(*dest(*HOME, 90.0, 1000.0 * step))
    wide = WP.build(cmap.centre, cmap.border_m, R, cmap.scan_m, swept=cmap.swept_at)
    check("driving a line east sweeps more of them off the list",
          len(wide) < len(after) and all(not cmap.swept_at(p["lat"], p["lon"], 500.0) for p in wide),
          (len(wide), len(after)))
    check("a huge border is held to the cap",
          len(WP.build(HOME, 400000.0, R, 2000.0)) <= WP.MAX_WAYPOINTS)
    check("no centre, no border or no radius: nothing", WP.build(None, 5000, R, 2000) == []
          and WP.build(HOME, 0, R, 2000) == [] and WP.build(HOME, 5000, 0, 2000) == [])


@section("the guide: arrival moves on, next, back, pause, complete, saved")
def _guide():
    cmap = CV.CoverageMap("Ega", "Ega 1", R)
    cmap.set_centre(*HOME)
    cmap.set_border(*dest(*HOME, 90.0, 5000.0))
    points = WP.build(cmap.centre, cmap.border_m, R, cmap.scan_m)
    key = WP.area_key(cmap.centre, cmap.border_m, cmap.scan_m)
    guide = WP.Guide("Ega", "Ega 1", key, points)
    check("it starts on waypoint 1 of N", guide.current()["n"] == 1 and guide.label() == "WP 1/%d" % len(points))
    far = dest(*HOME, 270.0, 1000.0)
    check("1 km away is not there", not guide.update(far[0], far[1], R, 250.0) and guide.index == 0)
    close = dest(*HOME, 270.0, 200.0)
    check("200 m away is, at the usual radius, and it moves on to 2",
          guide.update(close[0], close[1], R, 250.0) and guide.current()["n"] == 2)
    check("a radius of 50 m would not have counted 200 m",
          not WP.Guide("Ega", "Ega 1", key, points).update(close[0], close[1], R, 50.0))
    check("the radius is held to 50 to 1,000 m",
          WP.arrive_radius(5) == 50.0 and WP.arrive_radius(99999) == 1000.0 and WP.arrive_radius("x") == 250.0)
    guide.toggle_pause()
    here = (points[1]["lat"], points[1]["lon"])
    check("paused, standing on the waypoint does not move it on",
          not guide.update(here[0], here[1], R, 250.0) and guide.current()["n"] == 2 and guide.paused)
    guide.toggle_pause()
    check("resumed, it does", guide.update(here[0], here[1], R, 250.0) and guide.current()["n"] == 3)
    check("back goes to 2", guide.back() and guide.current()["n"] == 2)
    first = WP.Guide("Ega", "Ega 1", key, points)
    check("back at the first one stays there", first.back() is False and first.index == 0)
    # Skipping what has been swept in the meantime.
    swept_all = lambda lat, lon, margin: True       # noqa: E731
    skipper = WP.Guide("Ega", "Ega 1", key, points)
    skipper.advance(swept_all)
    check("everything ahead already swept: next finishes the survey", skipper.done and skipper.current() is None)
    check("and back from complete is the last waypoint", skipper.back() and skipper.current()["n"] == len(points))
    run = WP.Guide("Ega", "Ega 1", key, points)
    for _ in range(len(points)):
        run.advance()
    check("after the last waypoint it is complete", run.done and run.label() == "")
    check("next when complete does nothing", run.advance() is False)
    # On disk.
    folder = tempfile.mkdtemp(prefix="wp-")
    book = WP.WaypointBook(folder)
    guide.index = 4
    book.put(guide)
    check("it saves", book.save() and os.path.exists(os.path.join(folder, WP.FILE_NAME)))
    again = WP.WaypointBook(folder).get("EGA", "ega 1")
    check("and a new run of the program finds it, on the same waypoint, whatever the case",
          again and again.index == 4 and again.total == len(points) and again.key == key, again and again.index)
    bad = os.path.join(folder, WP.FILE_NAME)
    open(bad, "w").write("{not json")
    check("a damaged file is an empty book, not a crash", WP.WaypointBook(folder).get("Ega", "Ega 1") is None)
    check("a different centre or border is a different survey",
          WP.area_key(cmap.centre, cmap.border_m, 2000) != WP.area_key(cmap.centre, cmap.border_m + 500, 2000))


# ---------------------------------------------------------------------------
@section("the rig radar band: 76 m to 80 m, red in it, green clear")
def _band():
    sp = 78.0
    inside = RP.radar((0.0, 77.0), [(0.0, 0.0)], sp)
    ring = inside["rings"][0]
    check("each ring carries its band: 76 m to 80 m at 78 m",
          (ring["inner"], ring["outer"]) == (76.0, 80.0), (ring.get("inner"), ring.get("outer")))
    check("the Rhino inside the spacing: the band is red", ring["band"] == "red" and inside["band"] == "red")
    check("in the band, at 79 m: red",
          RP.radar((79.0, 0.0), [(0.0, 0.0)], sp)["rings"][0]["band"] == "red")
    check("on its outer edge, 80 m: still red", RP.radar((80.0, 0.0), [(0.0, 0.0)], sp)["rings"][0]["band"] == "red")
    clear = RP.radar((81.0, 0.0), [(0.0, 0.0)], sp)
    check("clear of it, 81 m: green", clear["rings"][0]["band"] == "green" and clear["band"] == "green"
          and clear["state"] == "ok" and clear["text"] == "RIG OK HERE")
    two = RP.radar((40.0, 0.0), [(0.0, 0.0), (400.0, 0.0)], sp)
    check("two rigs: the one in the way is red, the far one green, and the whole radar is red",
          [r["band"] for r in two["rings"]] == ["red", "green"] and two["band"] == "red")
    check("the NEXT RIG words are the ones they were",
          RP.radar((0.0, -30.0), [(0.0, 0.0)], sp)["text"] == "NEXT RIG: 48 m, bearing 180")
    wide = RP.radar((0.0, 100.0), [(0.0, 0.0)], 120.0)["rings"][0]
    check("the band follows the spacing setting", (wide["inner"], wide["outer"]) == (118.0, 122.0))


# ---------------------------------------------------------------------------
@section("the rig planner: an exact packing pass")
def _packing():
    rect = [(0.0, 0.0), (160.0, 0.0), (160.0, 80.0), (0.0, 80.0)]
    pins = RP.plan(rect, 78.0)
    check("a deposit 160 m by 80 m takes six rigs in two rows of three", len(pins) == 6, len(pins))
    worst = min(math.hypot(a[0] - b[0], a[1] - b[1]) for i, a in enumerate(pins) for b in pins[i + 1:])
    check("every pair is at least the spacing apart", worst >= 78.0 - 1e-6, worst)
    check("and every pin is inside the traced edge",
          all(RP.usable(rect, x, y) for x, y in pins))
    real = RP.pack_exact
    RP.pack_exact = lambda *a, **k: []
    try:
        without = len(RP.plan(rect, 78.0))
    finally:
        RP.pack_exact = real
    check("the lattices alone find fewer there (the pass is what finds six)", without < 6, without)
    rnd = random.Random(1035)
    bad = []
    for _ in range(8):
        n = rnd.randint(5, 14)
        cx, cy = rnd.uniform(-20, 20), rnd.uniform(-20, 20)
        shape = [(cx + rnd.uniform(70, 160) * math.cos(2 * math.pi * k / n),
                  cy + rnd.uniform(70, 160) * math.sin(2 * math.pi * k / n)) for k in range(n)]
        spacing = rnd.choice([60.0, 78.0, 90.0])
        got = RP.pack_exact(shape, spacing, 12)
        gaps = [math.hypot(a[0] - b[0], a[1] - b[1]) for i, a in enumerate(got) for b in got[i + 1:]]
        if (gaps and min(gaps) < spacing - 1e-6) or not all(RP.usable(shape, x, y) for x, y in got):
            bad.append((shape, spacing))
        if len(got) < len(RP.plan(shape, spacing, 12)) - 0:
            bad.append(("fewer", shape, spacing))
    check("eight random deposits: never closer than the spacing, never outside the edge, never fewer than the lattices",
          not bad, bad[:1])
    circle = [(100 * math.cos(2 * math.pi * k / 24), 100 * math.sin(2 * math.pi * k / 24)) for k in range(24)]
    pins = RP.plan(circle, 78.0)
    check("a round deposit 200 m across still gets its six pins", len(pins) == 6, len(pins))
    check("and the room it has is more than the six, and is the figure kept",
          RP.fit_count(circle, 78.0, pins=pins) > RP.MAX_PINS, RP.fit_count(circle, 78.0, pins=pins))
    check("a deposit with no room fits none", RP.fit_count([(0, 0), (20, 0), (20, 20), (0, 20)], 78.0) == 1
          or RP.fit_count([(0, 0), (20, 0), (20, 20), (0, 20)], 78.0) == 0)
    check("fit is counted past the six a Rhino carries",
          RP.fit_count([(0, 0), (400, 0), (400, 300), (0, 300)], 78.0) > RP.MAX_PINS)
    check("a degenerate shape plans nothing", RP.plan([(0, 0), (1, 1)], 78.0) == [] and RP.pack_exact([], 78.0) == [])


@section("plans kept with the deposit")
def _plan_book():
    folder = tempfile.mkdtemp(prefix="plans-")
    book = RP.PlanBook(folder)
    pins = [{"n": 1, "lat": 12.5, "lon": -45.5}, {"n": 2, "lat": 12.5005, "lon": -45.5}]
    rec = {"system": "Ega", "body": "Ega 1", "radius_m": R, "spacing": 78.0, "pins": pins,
           "outline": [(12.5, -45.5), (12.501, -45.5), (12.501, -45.499)], "area_m2": 9000.0,
           "fit": 8, "deposit": "d1"}
    check("a plan is kept", book.put(rec) and os.path.exists(os.path.join(folder, RP.PLAN_FILE)))
    again = RP.PlanBook(folder)
    found = again.nearest("EGA", "ega 1", 12.5002, -45.5, R, 600.0)
    check("a new run finds it by where you stand, whatever the case",
          found and found["fit"] == 8 and found["deposit"] == "d1" and len(found["pins"]) == 2
          and len(found["outline"]) == 3, found)
    check("a body away, or a long way off, finds nothing",
          again.nearest("Ega", "Ega 2", 12.5, -45.5, R, 600.0) is None
          and again.nearest("Ega", "Ega 1", 13.5, -45.5, R, 600.0) is None)
    again.put(dict(rec, fit=9))
    check("the same ground again replaces the plan rather than doubling it",
          len(again.plans) == 1 and again.plans[0]["fit"] == 9)
    open(os.path.join(folder, RP.PLAN_FILE), "w").write("[[[")
    check("a damaged file is an empty book", RP.PlanBook(folder).plans == [])
    many = RP.PlanBook(tempfile.mkdtemp(prefix="plans-"))
    for k in range(RP.PLAN_KEEP + 20):
        many.put(dict(rec, lon_shift=k, pins=[{"n": 1, "lat": 12.5, "lon": -45.5 + 0.01 * k}],
                      outline=[(12.5, -45.5 + 0.01 * k)], deposit="d%d" % k))
    check("the book keeps %d plans at the most, the newest" % RP.PLAN_KEEP,
          len(many.plans) == RP.PLAN_KEEP and many.plans[-1]["deposit"] == "d%d" % (RP.PLAN_KEEP + 19),
          len(many.plans))


# ---------------------------------------------------------------------------
@section("the journal: where the Rhino was left and where the ship came down")
def _journal():
    folder = tempfile.mkdtemp(prefix="journal-")
    stamp = "2026-10-20T10:%02d:00Z"
    log = os.path.join(folder, "Journal.2026-10-20T100000.01.log")

    def emit(*events):
        with open(log, "a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event) + "\n")

    def status(lat, lon, flags, flags2=0, body="Ega 1"):
        with open(os.path.join(folder, "Status.json"), "w", encoding="utf-8") as handle:
            json.dump({"timestamp": "2026-10-20T10:00:00Z", "event": "Status", "Flags": flags,
                       "Flags2": flags2, "Latitude": lat, "Longitude": lon, "Heading": 90,
                       "BodyName": body, "PlanetRadius": R}, handle)

    emit({"timestamp": stamp % 0, "event": "Fileheader", "gameversion": "4.4.1.1", "part": 1},
         {"timestamp": stamp % 1, "event": "Commander", "Name": "Jameson", "FID": "F1"},
         {"timestamp": stamp % 2, "event": "Location", "StarSystem": "Ega", "Body": "Ega 1"})
    watcher = JN.JournalWatcher(folder)
    landed = (1 << 1) | (1 << 21) | (1 << 24)
    status(*HOME, landed)
    emit({"timestamp": stamp % 3, "event": "Touchdown", "Latitude": HOME[0], "Longitude": HOME[1],
          "Body": "Ega 1", "PlayerControlled": True})
    watcher.poll()
    check("a Touchdown is where the ship is", watcher.ship_down
          and abs(watcher.ship_down["lat"] - HOME[0]) < 1e-9, watcher.ship_down)
    emit({"timestamp": stamp % 4, "event": "LaunchSRV", "SRVType": "mev_rhino",
          "SRVType_Localised": "SRV Rhino", "ID": 7, "PlayerControlled": True})
    out = dest(*HOME, 0.0, 600.0)
    status(*out, (1 << 21) | (1 << 26))
    watcher.poll()
    check("in the Rhino nothing is parked, and the ship stays where it was",
          watcher.rhino_parked is None and watcher.srv_last and abs(watcher.srv_last["lat"] - out[0]) < 1e-9
          and abs(watcher.ship_down["lat"] - HOME[0]) < 1e-9)
    emit({"timestamp": stamp % 5, "event": "Disembark", "SRV": True, "Taxi": False, "Multicrew": False,
          "ID": 7, "StarSystem": "Ega", "Body": "Ega 1", "OnPlanet": True})
    foot = dest(*out, 90.0, 3.0)
    status(*foot, (1 << 21), 1 | (1 << 4))
    watcher.poll()
    check("leaving the Rhino on foot parks it where it was last driven",
          watcher.rhino_parked and abs(watcher.rhino_parked["lat"] - out[0]) < 1e-9
          and watcher.rhino_parked["body"] == "Ega 1", watcher.rhino_parked)
    emit({"timestamp": stamp % 6, "event": "Embark", "SRV": True, "Taxi": False, "ID": 7})
    status(*out, (1 << 21) | (1 << 26))
    watcher.poll()
    check("boarding it again clears that", watcher.rhino_parked is None)
    emit({"timestamp": stamp % 7, "event": "Disembark", "SRV": True, "Taxi": False, "ID": 7})
    status(*foot, (1 << 21), 1 | (1 << 4))
    watcher.poll()
    emit({"timestamp": stamp % 8, "event": "DockSRV", "SRVType": "mev_rhino", "ID": 7})
    watcher.poll()
    check("docking it clears that too", watcher.rhino_parked is None)
    # A journal read from the top, with the position only coming afterwards.
    fresh = tempfile.mkdtemp(prefix="journal-")
    log2 = os.path.join(fresh, "Journal.2026-10-20T100000.01.log")
    with open(log2, "w", encoding="utf-8") as handle:
        for event in ({"timestamp": stamp % 0, "event": "Fileheader", "gameversion": "4.4.1.1", "part": 1},
                      {"timestamp": stamp % 2, "event": "Location", "StarSystem": "Ega", "Body": "Ega 1"},
                      {"timestamp": stamp % 5, "event": "Disembark", "SRV": True, "ID": 7}):
            handle.write(json.dumps(event) + "\n")
    with open(os.path.join(fresh, "Status.json"), "w", encoding="utf-8") as handle:
        json.dump({"Flags": 1 << 21, "Flags2": 1, "Latitude": foot[0], "Longitude": foot[1],
                   "Heading": 0, "BodyName": "Ega 1", "PlanetRadius": R}, handle)
    late = JN.JournalWatcher(fresh)
    late.poll()
    check("a Disembark read before any position takes the first one on foot",
          late.rhino_parked and abs(late.rhino_parked["lat"] - foot[0]) < 1e-9, late.rhino_parked)


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
    out = {}
    for item in canvas.find_all():
        for tag in canvas.gettags(item):
            out[tag] = out.get(tag, 0) + 1
    return out


def texts_of(canvas, tag=None):
    return [canvas.itemcget(i, "text") for i in canvas.find_all()
            if canvas.type(i) == "text" and (tag is None or tag in canvas.gettags(i))]


def text_boxes(canvas):
    """[(text, (x0, y0, x1, y1), tags)] for every text item on a canvas."""
    out = []
    for item in canvas.find_all():
        if canvas.type(item) == "text":
            box = canvas.bbox(item)
            if box:
                out.append((canvas.itemcget(item, "text"), box, canvas.gettags(item)))
    return out


def touch(a, b, pad=0):
    return a[0] < b[2] + pad and b[0] < a[2] + pad and a[1] < b[3] + pad and b[1] < a[3] + pad


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

    PRICES = {"Platinum": 250000, "Osmium": 100000, "Aluminium": 1000, "Iridium": 200000,
              "Painite": 400000}

    def row(ident, east, north, commodity, rigs="3", amount="High", location="1"):
        away, bearing = PV.to_polar(east, north)
        return {"deposit": {"id": ident, "commodity": commodity, "rigs": rigs,
                            "amount": amount, "location": location,
                            "lat": "0", "lon": "0"},
                "range_m": away, "bearing": bearing, "commodity": commodity}


# ---------------------------------------------------------------------------
@on_screen("overlay fault: SITE and AREA SWEPT no longer print through the hold card")
def _status_hold():
    app.settings.update(overlay_enabled=True, overlay_show_status=True, overlay_show_radar=False,
                        overlay_show_strip=False, overlay_show_targets=False,
                        overlay_rhino_only=False)
    app.overlay.show()
    pump()
    rows = [row("a", 100, 200, "Platinum"), row("b", -300, 80, "Osmium", "4")]
    card = {"title": "SHIP 790/1298 t", "detail": "508 t free  2 loads left", "state": "ok",
            "known": True, "fraction": 0.61, "trip_t": 31, "rhino_t": 12}
    survey = {"percent": 42, "scan_m": 2000.0, "points": [], "centre": None, "border_m": None,
              "rings": [], "gaps": []}
    seen_site = seen_area = drawn = 0
    for width, height in ((560, 120), (560, 100), (420, 110), (300, 130), (700, 160), (240, 120),
                          (560, 90), (360, 150), (480, 200)):
        panel = app.overlay.panels[OV.STATUS]           # the app may have rebuilt the box
        panel.window.geometry("%dx%d+10+10" % (width, height))
        pump()
        app.overlay.draw(rows, 0.0, body="Ega 3 a", location="1", survey=survey,
                         cargo={"ship_t": 790, "capacity": 1298, "rhino_t": 12, "hold": card})
        canvas = panel.canvas
        boxes = text_boxes(canvas)
        hold = [b for t, b, tg in boxes if "hold" in tg]
        side = [(t, b) for t, b, tg in boxes if t.startswith("SITE ") or t.startswith("AREA SWEPT")]
        seen_site += any(t.startswith("SITE ") for t, _ in side)
        seen_area += any(t.startswith("AREA SWEPT") for t, _ in side)
        clash = [(t, b, h) for t, b in side for h in hold if touch(b, h)]
        drawn += bool(hold)
        check("%dx%d: nothing printed through the hold card" % (width, height), not clash,
              (clash[:1], hold))
    check("the card was drawn at most of the sizes", drawn >= 6, drawn)
    check("where there is room the two lines are still shown, above the card",
          seen_site >= 2 and seen_area >= 2, (seen_site, seen_area))
    app.overlay.hide()


@on_screen("overlay fault: TARGETS value-bar labels are whole")
def _bar_labels():
    app.settings.update(overlay_enabled=True, overlay_show_targets=True, overlay_show_status=False,
                        overlay_show_radar=False, overlay_show_strip=False,
                        overlay_rhino_only=False)
    app.overlay.show()
    pump()
    app.market_prices = lambda: PRICES
    rows = [row("i", 100, 200, "Iridium", "6"), row("p", 0, 400, "Painite", "2"),
            row("o", -300, 80, "Osmium", "4"), row("a", 600, 600, "Aluminium", "1"),
            row("pl", 20, -400, "Platinum", "3")]
    for width, height in ((560, 260), (420, 300), (300, 240), (640, 400)):
        panel = app.overlay.panels[OV.TARGETS]          # the app may have rebuilt the box
        panel.window.geometry("%dx%d+10+10" % (width, height))
        pump()
        app.overlay.draw(rows, 0.0, body="Ega 3 a", location="1")
        canvas = panel.canvas
        labels = [(canvas.itemcget(i, "text"), canvas.bbox(i)) for i in canvas.find_withtag("barlabel")]
        names = [t for t, _ in labels]
        check("%dx%d: the strip is labelled, IRIDIU in full" % (width, height),
              "IRIDIU" in names and len(labels) >= 3, names)
        out = [(t, b) for t, b in labels if b and (b[0] < 0 or b[2] > width)]
        check("%dx%d: no label is cut by an edge of the box" % (width, height), not out, out[:2])
        pairs = [(a, b) for i, a in enumerate(labels) for b in labels[i + 1:] if a[1] and b[1] and touch(a[1], b[1])]
        check("%dx%d: and no two labels run into each other" % (width, height), not pairs, pairs[:1])
    app.overlay.hide()


@on_screen("map fault: an arrow's distance label is never printed over the footer")
def _footer_labels():
    plan = A.PlanView(app)
    plan.place(x=0, y=0, width=900, height=700)
    pump()
    plan.map_prefs = {}
    plan._extent = 400.0                       # zoomed in: the far finds are arrows at the edge
    found = 0
    for bearing in (180, 160, 200, 175, 190, 225, 135):
        east = 1500 * math.sin(math.radians(bearing))
        north = 1500 * math.cos(math.radians(bearing))
        rows = [row("far", east, north, "Platinum"), row("near", 20, 30, "Osmium")]
        plan.show(rows, heading=0.0, caption="Test body", signal="1", anchor=(0.0, 0.0),
                  place=("Ega", "Ega 1", "1"))
        pump(2)
        footer = [box for text, box, tags in text_boxes(plan) if text.startswith("rings ")]
        edge = [(text, box) for text, box, tags in text_boxes(plan) if "edge" in tags]
        found += len(edge)
        check("arrow due %d: its label clears the footer line" % bearing,
              footer and edge and not any(touch(box, footer[0]) for _t, box in edge),
              (footer, edge))
    check("the arrows were there to test", found >= 7, found)
    plan.destroy()


# ---------------------------------------------------------------------------
if HAVE_DISPLAY:
    journal = os.path.join(JOURNALS, "Journal.2026-10-20T100000.01.log")
    EVENTS = []

    def emit(*events):
        with open(journal, "a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event) + "\n")

    RHINO = (1 << 21) | (1 << 26)
    SHIP_LOW = (1 << 21) | (1 << 24)
    SHIP_DOWN = (1 << 1) | (1 << 21) | (1 << 24)
    FOOT = (1 << 21)

    def status(lat, lon, heading=90, flags=RHINO, flags2=0, altitude=None):
        data = {"timestamp": "2026-10-20T10:00:00Z", "event": "Status", "Flags": flags,
                "Flags2": flags2, "Latitude": lat, "Longitude": lon, "Heading": heading,
                "BodyName": "Ega 1", "PlanetRadius": R}
        if altitude is not None:
            data["Altitude"] = altitude
        with open(os.path.join(JOURNALS, "Status.json"), "w", encoding="utf-8") as handle:
            json.dump(data, handle)

    def at(lat, lon, **kwargs):
        """Put the commander there and let the app read it, the way a tick does."""
        status(lat, lon, **kwargs)
        app.game = app.watcher.poll()
        app.track_survey(app.game)

    def scope_canvas():
        return app.overlay.panels[OV.RADAR].canvas

    def strip_canvas():
        return app.overlay.panels[OV.STRIP].canvas

    def look():
        """Redraw everything with the compass and the scope big enough to read."""
        for name, size in ((OV.RADAR, "460x460+600+200"), (OV.STRIP, "760x110+10+760")):
            panel = app.overlay.panels.get(name)
            if panel is not None:
                panel.window.geometry(size)
        pump(2)
        app.redraw()
        pump(2)

    def all_text():
        return {"compass": texts_of(strip_canvas()), "scope": texts_of(scope_canvas()),
                "map": texts_of(app.plan)}

    def has(prefix):
        return {name: any(t.startswith(prefix) for t in texts) for name, texts in all_text().items()}

    def on_all(prefix):
        return all(has(prefix).values())

    def on_none(prefix):
        return not any(has(prefix).values())


@on_screen("the real window: a session on Ega 1, the survey area set")
def _session():
    emit({"timestamp": "2026-10-20T09:59:00Z", "event": "Fileheader", "gameversion": "4.4.1.1", "part": 1},
         {"timestamp": "2026-10-20T09:59:01Z", "event": "Commander", "Name": "Jameson", "FID": "F1"},
         {"timestamp": "2026-10-20T09:59:30Z", "event": "ApproachBody", "StarSystem": "Ega", "Body": "Ega 1"},
         {"timestamp": "2026-10-20T09:59:31Z", "event": "Scan", "BodyName": "Ega 1", "Radius": R,
          "SurfaceTemperature": 214.5})
    status(*HOME)
    app.settings["rig_offset_m"] = 0
    app.market_prices = lambda: PRICES
    app.game = app.watcher.poll()
    check("the app reads the synthetic session: Ega 1, in the Rhino, a position",
          app.game.body == "Ega 1" and app.game.has_position and app.game.in_srv)
    app.settings.update(overlay_enabled=True, overlay_show_radar=True, overlay_show_strip=True,
                        overlay_show_status=False, overlay_show_targets=False)
    app.overlay.show()
    pump()
    check("the compass and the scope are up", OV.STRIP in app.overlay.panels and OV.RADAR in app.overlay.panels)
    look()
    check("no survey area yet: no waypoints on any of the three", on_none("WP "))
    app.set_survey_centre()
    check("a centre alone is not enough", on_none("WP ") and app.wp_guide(app._survey_map(), app.game, create=False) is None)
    # Drive 5 km east to the edge, then set the border.
    for k in range(1, 6):
        at(*dest(HOME[0], HOME[1], 90.0, 1000.0 * k))
    app.set_survey_border()
    cmap = app._survey_map()
    check("the area is set: centre and a border near 5 km", cmap.centre is not None and abs(cmap.border_m - 5000) < 50,
          cmap.border_m)
    app.track_survey(app.game)
    guide = app.wp_guide(cmap, app.game, create=False)
    check("the waypoints were built the first time the Rhino ticked with an area set",
          guide is not None and guide.total >= 5, guide and guide.total)
    expected_total = guide.total
    check("none of them is ground already swept",
          all(not cmap.swept_at(p["lat"], p["lon"], 500.0) for p in guide.waypoints[guide.index:guide.index + 1]))
    look()
    texts = all_text()
    word = "WP %d/%d: " % (guide.current()["n"], guide.total)
    check("WP n/N with distance and bearing is on the compass, the scope and the map",
          on_all(word), {k: [t for t in v if t.startswith("WP")] for k, v in texts.items()})
    shown = [t for t in texts["compass"] if t.startswith("WP ")][0]
    here = (app.game.lat, app.game.lon)
    now = guide.current()
    away = metres_between(here, (now["lat"], now["lon"]))
    bearing = SV.bearing_deg(here[0], here[1], now["lat"], now["lon"])
    check("and it is the right distance and bearing",
          shown == "%s%s, bearing %03d" % (word, GD_distance(away), int(round(bearing)) % 360), (shown, away, bearing))
    check("only the one waypoint is named, not the whole list",
          sum(1 for t in texts["compass"] if t.startswith("WP ")) == 1)
    tags = {"scope": tags_of(scope_canvas()), "map": tags_of(app.plan), "compass": tags_of(strip_canvas())}
    check("the waypoints are dots on the scope and the map, the current one ringed",
          tags["scope"].get("wp", 0) >= 2 and tags["map"].get("wp", 0) >= 2
          and tags["scope"].get("wpnow") and tags["map"].get("wpnow"), tags)
    check("and a chevron on the compass", tags["compass"].get("chevron"), tags["compass"])
    check("and a chevron beside you on the scope and the map", tags["scope"].get("chevron") and tags["map"].get("chevron"))

    # Arrival.
    first = guide.index
    near = dest(now["lat"], now["lon"], 0.0, 600.0)
    at(*near)
    check("600 m short of it, at 250 m, is not there", guide.index == first)
    at(*dest(now["lat"], now["lon"], 0.0, 120.0))
    check("within 250 m of it moves on to the next", guide.index > first and not guide.done, guide.index)
    look()
    nxt = guide.current()
    check("and every surface now names that one",
          on_all("WP %d/%d: " % (nxt["n"], expected_total)), all_text()["compass"])
    check("the survey is saved per body for the next run", os.path.exists(os.path.join(A.DATA_DIR, WP.FILE_NAME))
          and WP.WaypointBook(A.DATA_DIR).get("Ega", "Ega 1").index == guide.index)

    # The three keys.
    def key(name):
        app.hotkeys.events.put(name)
        app.run_hotkeys()
        pump(2)

    wanted = A.EDSMT.wanted_hotkeys(app.settings)
    check("next, back, skip and pause start unbound: no key is taken for them",
          not any(a in wanted for a in ("wp_next", "wp_back", "wp_skip", "wp_pause")), sorted(wanted.items()))
    picked = dict(app.settings, hotkey_wp_next="ALT+=", hotkey_wp_back="ALT+[",
                  hotkey_wp_skip="ALT+\\", hotkey_wp_pause="ALT+]")
    wanted = A.EDSMT.wanted_hotkeys(picked)
    check("keys picked in Settings register all four actions, each on its own key",
          all(wanted.get(a) for a in ("wp_next", "wp_back", "wp_skip", "wp_pause"))
          and len({v.upper() for v in wanted.values()}) == len(wanted), sorted(wanted.items()))
    before = guide.index
    key("wp_next")
    stepped = guide.index
    check("next moves on", stepped > before or guide.done, (before, guide.index))
    key("wp_back")
    check("back returns one", guide.index == stepped - 1 and not guide.done, (before, stepped, guide.index))
    key("wp_pause")
    check("pause holds it: the words say so", guide.paused and on_all("WP %d/%d (paused): " % (
        guide.current()["n"], expected_total)), all_text()["compass"])
    held = guide.index
    cur = guide.current()
    at(cur["lat"], cur["lon"])
    check("paused, standing on the waypoint does not advance it", guide.index == held)
    key("wp_pause")
    at(cur["lat"], cur["lon"])
    check("resumed, it does", guide.index > held or guide.done, (held, guide.index))
    if guide.done:
        key("wp_back")
    leave = guide.current()
    after = guide.index
    key("wp_skip")
    check("skip leaves this waypoint out and goes on to the next",
          leave["n"] in guide.skipped and (guide.index > after or guide.done), (leave["n"], guide.skipped))
    look()
    if not guide.done:
        check("and every surface now names the next one",
              on_all("WP %d/%d: " % (guide.current()["n"], expected_total)), all_text()["compass"])
    key("wp_back")
    check("back onto a skipped waypoint takes it off the skipped list: it is to be driven",
          guide.current()["n"] == leave["n"] and not guide.skipped, (guide.skipped, guide.index, after))
    check("skipped ones are saved with the survey",
          WP.Guide.from_dict(dict(guide.to_dict(), skipped=[3, 5])).skipped == [3, 5]
          and WP.Guide.from_dict(dict(guide.to_dict(), skipped="x")).skipped == [])

    # A new run finds the progress.
    saved_index = guide.index
    app.guide_init(A.DATA_DIR)
    look()
    again = app.wp_guide(app._survey_map(), app.game, create=False)
    check("after a restart the survey resumes on the same waypoint", again is not None
          and again.index == saved_index and again.total == expected_total, again and again.index)
    check("and it is drawn", on_all("WP %d/%d: " % (again.current()["n"], expected_total)))

    # Settings: the radius, and the switch.
    app.settings["waypoint_radius_m"] = 1000
    far_off = again.current()
    at(*dest(far_off["lat"], far_off["lon"], 0.0, 900.0))
    check("a bigger radius in Settings counts 900 m as there", again.index > saved_index or again.done)
    app.settings["waypoint_radius_m"] = 250
    app.settings["survey_guide"] = False
    look()
    check("the switch off: no waypoints on any surface", on_none("WP ") and not has("SURVEY COMPLETE")["map"])
    app.settings["survey_guide"] = True

    # Run to the end.
    guide = again                                    # the restart made a new one
    for _ in range(guide.total + 2):
        key("wp_next")
    look()
    check("after the last: SURVEY COMPLETE on the compass, the scope and the map", guide.done
          and on_all("SURVEY COMPLETE"), all_text()["compass"])
    check("and no waypoint is named any more", on_none("WP "))
    key("wp_back")
    check("back out of complete is the last waypoint", not guide.done and guide.current()["n"] == guide.total)
    key("wp_skip")
    look()
    check("skipping the last one finishes the survey, and says how many were left out",
          guide.done and guide.skipped == [guide.total] and on_all("SURVEY COMPLETE (1 skipped)"),
          (guide.skipped, all_text()["compass"]))
    key("wp_back")
    check("back onto it is to be driven: not skipped any more",
          not guide.done and not guide.skipped and guide.current()["n"] == guide.total)
    # Restore the position for the sections below.
    at(*HOME)


@on_screen("the rig radar band is drawn on the map and the scope, red in it and green clear")
def _band_drawn():
    app.settings.update(map_trail=True, rig_radar=True)
    app.settings["survey_guide"] = False
    at(*HOME)
    app.drop_rigs()                                   # rig 1 here
    look()

    def bands(canvas):
        out = []
        for item in canvas.find_withtag("rigband"):
            out.append((canvas.itemcget(item, "outline") if canvas.type(item) == "oval"
                        else canvas.itemcget(item, "fill"), canvas.itemcget(item, "width")))
        return out

    at(*dest(HOME[0], HOME[1], 0.0, 30.0))
    look()
    red, green = A.PlanView._radar_colour("close").lower(), A.PlanView._radar_colour("ok").lower()
    scope_red, scope_green = OV.RADAR_COLOURS["close"].lower(), OV.RADAR_COLOURS["ok"].lower()
    plan_bands, scope_bands = bands(app.plan), bands(scope_canvas())
    check("30 m from the rig: the band is three lines on the map and on the scope, all red",
          len(plan_bands) == 3 and len(scope_bands) >= 3
          and all(c.lower() == red for c, _w in plan_bands)
          and all(c.lower() == scope_red for c, _w in scope_bands), (plan_bands, scope_bands))
    check("the middle line is the thick one: a band, not a ring",
          max(float(w) for _c, w in plan_bands) > 1.0 and min(float(w) for _c, w in plan_bands) == 1.0, plan_bands)
    at(*dest(HOME[0], HOME[1], 0.0, 79.0))
    look()
    check("79 m, inside the band: still red", all(c.lower() == red for c, _w in bands(app.plan)), bands(app.plan))
    at(*dest(HOME[0], HOME[1], 0.0, 95.0))
    look()
    check("95 m, clear of every rig: green on both",
          all(c.lower() == green for c, _w in bands(app.plan))
          and all(c.lower() == scope_green for c, _w in bands(scope_canvas())), bands(app.plan))
    check("NEXT RIG's words are unchanged below 78 m",
          RP.radar((0.0, 10.0), [(0.0, 0.0)], 78.0)["text"].startswith("NEXT RIG: 68 m"))
    # Two rigs, the Rhino inside 80 m of one: every band is red, the far
    # rig's included; clear of both and every band is green.
    at(*dest(HOME[0], HOME[1], 0.0, 300.0))
    app.drop_rigs()                                   # rig 2, 300 m north of rig 1
    at(*dest(HOME[0], HOME[1], 180.0, 30.0))
    look()
    plan_bands, scope_bands = bands(app.plan), bands(scope_canvas())
    check("two rigs, inside 80 m of one: both rigs' bands are red, on the map and the scope",
          len(plan_bands) == 6 and len(scope_bands) >= 6
          and all(c.lower() == red for c, _w in plan_bands)
          and all(c.lower() == scope_red for c, _w in scope_bands), (plan_bands, scope_bands))
    at(*dest(HOME[0], HOME[1], 90.0, 200.0))
    look()
    check("clear of both: every band is green",
          len(bands(app.plan)) == 6 and all(c.lower() == green for c, _w in bands(app.plan))
          and all(c.lower() == scope_green for c, _w in bands(scope_canvas())), bands(app.plan))
    app.rigs_up()
    at(*HOME)
    app.settings["survey_guide"] = True


@on_screen("the pointer to the parked Rhino, and to the ship from the Rhino")
def _pointers():
    app.settings["survey_guide"] = False
    out = dest(*HOME, 0.0, 600.0)
    emit({"timestamp": "2026-10-20T10:01:00Z", "event": "Touchdown", "Latitude": HOME[0],
          "Longitude": HOME[1], "Body": "Ega 1", "PlayerControlled": True},
         {"timestamp": "2026-10-20T10:01:30Z", "event": "LaunchSRV", "SRVType": "mev_rhino",
          "SRVType_Localised": "SRV Rhino", "ID": 7, "PlayerControlled": True})
    at(*out)
    look()
    ship = "SHIP: 600 m, bearing 180"
    check("in the Rhino: a pointer to where the ship came down, on all three",
          on_all("SHIP: "), all_text())
    check("with the right distance and bearing", all(ship in texts for texts in all_text().values()),
          {k: [t for t in v if t.startswith("SHIP")] for k, v in all_text().items()})
    tags = {"scope": tags_of(scope_canvas()), "map": tags_of(app.plan), "compass": tags_of(strip_canvas())}
    check("and a chevron on each", all(t.get("chevron") for t in tags.values()), tags)
    check("and none to a Rhino: it is the one you are in", on_none("RHINO: "))
    emit({"timestamp": "2026-10-20T10:02:00Z", "event": "Disembark", "SRV": True, "Taxi": False,
          "Multicrew": False, "ID": 7, "StarSystem": "Ega", "Body": "Ega 1", "OnPlanet": True})
    walked = dest(*out, 270.0, 640.0)
    at(*walked, flags=FOOT, flags2=1 | (1 << 4))
    look()
    rhino = "RHINO: %s, bearing 090" % GD_distance(metres_between(walked, out))
    check("on foot: where the Rhino was left, with distance and bearing, on all three",
          all(rhino in texts for texts in all_text().values()),
          {k: [t for t in v if t.startswith("RHINO")] for k, v in all_text().items()})
    tags = {"scope": tags_of(scope_canvas()), "map": tags_of(app.plan), "compass": tags_of(strip_canvas())}
    check("with a chevron on each", all(t.get("chevron") for t in tags.values()), tags)
    check("and no pointer to the ship while on foot", on_none("SHIP: "))
    was_locked, was_only = app.settings.get("overlay_click_through", True), app.settings.get("overlay_rhino_only")
    app.settings["overlay_click_through"] = True
    app.overlay.settings["overlay_click_through"] = True
    app.settings["overlay_rhino_only"] = True
    check("on foot with the Rhino left behind, 'only in the Rhino' still keeps the boxes up",
          app.overlay_wanted_now() and not app.game.in_rhino)
    app.settings["rhino_pointer"] = False
    check("with the pointer switched off it takes them down, as before", not app.overlay_wanted_now())
    app.settings["rhino_pointer"] = True
    at(*walked, flags=SHIP_LOW, altitude=500)
    look()
    check("in the ship near the ground: the Rhino is still pointed to", on_all("RHINO: "), all_text())
    check("and the boxes stay up for it", app.overlay_wanted_now())
    app.settings["overlay_click_through"] = app.overlay.settings["overlay_click_through"] = was_locked
    app.settings["overlay_rhino_only"] = was_only
    app.settings["rhino_pointer"] = False
    look()
    check("the switch off: neither pointer is drawn", on_none("RHINO: ") and on_none("SHIP: "))
    app.settings["rhino_pointer"] = True
    emit({"timestamp": "2026-10-20T10:03:00Z", "event": "Embark", "SRV": True, "Taxi": False, "ID": 7})
    at(*out)
    look()
    check("back in the Rhino it is no longer parked", on_none("RHINO: ") and on_all("SHIP: "))
    emit({"timestamp": "2026-10-20T10:04:00Z", "event": "DockSRV", "SRVType": "mev_rhino", "ID": 7})
    at(*HOME, flags=SHIP_DOWN)
    app.settings["survey_guide"] = True


@on_screen("guidance from orbit: one line to the deposit or the signal")
def _orbit():
    app.settings["survey_guide"] = False
    # A signal logged here, and a deposit 700 m north of it.
    app.store.set_location("Ega", "Ega 1", "1", lat=HOME[0], lon=HOME[1], radius_m=R)
    lat, lon = dest(*HOME, 0.0, 700.0)
    app.store.add_deposit(system="Ega", body="Ega 1", location="1", commodity="Painite",
                          rigs="3", amount="High", lat=lat, lon=lon)
    deposit = [r for r in app.store.at("Ega", "Ega 1") if r["commodity"] == "Painite"][0]
    high = dest(*HOME, 45.0, 300000.0)
    at(*high, flags=SHIP_LOW, altitude=85000)
    app._guide_to = None
    look()
    away = metres_between(high, HOME)
    bearing = SV.bearing_deg(high[0], high[1], HOME[0], HOME[1])
    line = "TO SIGNAL 1: %s, bearing %03d, alt 85 km" % (GD_distance(away), int(round(bearing)) % 360)
    was_locked, was_only = app.settings.get("overlay_click_through", True), app.settings.get("overlay_rhino_only")
    app.settings["overlay_click_through"] = True
    app.overlay.settings["overlay_click_through"] = True
    app.settings["overlay_rhino_only"] = True
    check("coming down in the ship, 'only in the Rhino' keeps the boxes up for the line", app.overlay_wanted_now())
    app.settings["orbit_guide"] = False
    check("with the orbit line switched off it does not", not app.overlay_wanted_now())
    app.settings["orbit_guide"] = True
    app.settings["overlay_click_through"] = app.overlay.settings["overlay_click_through"] = was_locked
    app.settings["overlay_rhino_only"] = was_only
    check("in the ship, coming down: how far and which way to the signal, with the altitude",
          line in all_text()["compass"] and line in all_text()["scope"], {k: [t for t in v if t.startswith("TO ")]
                                                                       for k, v in all_text().items()})
    check("and on the map", on_all("TO "), all_text()["map"])
    app._guide_to = deposit["id"]
    look()
    away = metres_between(high, (lat, lon))
    bearing = SV.bearing_deg(high[0], high[1], lat, lon)
    line = "TO PAINITE: %s, bearing %03d, alt 85 km" % (GD_distance(away), int(round(bearing)) % 360)
    check("with a deposit selected it is to the deposit instead", line in all_text()["compass"]
          and line in all_text()["scope"] and line in all_text()["map"],
          [t for t in all_text()["compass"] if t.startswith("TO ")])
    check("one line, not two", sum(1 for t in all_text()["compass"] if t.startswith("TO ")) == 1)
    app.settings["orbit_guide"] = False
    look()
    check("the switch off: no line", on_none("TO "))
    app.settings["orbit_guide"] = True
    at(*high, flags=SHIP_LOW)
    look()
    check("with no altitude given the line has none", any(t.startswith("TO PAINITE: ") and "alt" not in t
                                                         for t in all_text()["compass"]))
    at(*HOME, flags=RHINO)
    look()
    check("in the Rhino there is no orbit line", on_none("TO "))
    app._guide_to = None
    app.settings["survey_guide"] = True


@on_screen("the rig planner: out of beta, the plan kept with the deposit, rigs that fit")
def _planner():
    app.settings["survey_guide"] = False
    check("no switch for it in the defaults", "rig_planner" not in A.DEFAULT_SETTINGS)
    check("its key is registered like the others", A.EDSMT.wanted_hotkeys(app.settings).get("trace"))
    # A deposit marked on the spot first.
    spot = dest(*HOME, 90.0, 3000.0)
    at(*spot)
    app.store.add_deposit(system="Ega", body="Ega 1", location="1", commodity="Platinum",
                          rigs="3", amount="High", lat=spot[0], lon=spot[1])
    deposit = [r for r in app.store.at("Ega", "Ega 1") if r["commodity"] == "Platinum"][0]
    check("a deposit marked before there is any plan records nothing for fit yet", not deposit["rigs_fit"])
    app.planner_trace()
    check("the key starts a trace with the planner no longer behind a switch",
          getattr(app, "_trace", None) is not None)
    middle = dest(spot[0], spot[1], 0.0, 100.0)
    for k in range(1, 61):
        # a loop of radius 100 m that starts and ends where the key was pressed
        at(*dest(middle[0], middle[1], (180.0 + 6.0 * k) % 360.0, 100.0))
        app.follow_trace(app.game)
        if getattr(app, "_trace", None) is None or app.__dict__.get("_trace") is None:
            break
    plan = getattr(app, "rig_plan", None)
    check("driving round it puts the pins out", plan and len(plan["pins"]) == 6, plan and len(plan["pins"]))
    check("the plan records how many fit - more than a Rhino carries", plan and plan["fit"] >= 7, plan and plan.get("fit"))
    fit = str(plan["fit"])
    book = app.plan_book
    check("the plan and the traced edge are kept on disk",
          len(book.plans) == 1 and len(book.plans[0]["outline"]) >= 10
          and os.path.exists(os.path.join(A.DATA_DIR, RP.PLAN_FILE)), len(book.plans))
    row_now = [r for r in app.store.at("Ega", "Ega 1") if r["commodity"] == "Platinum"][0]
    check("the deposit nearby was given its rigs-that-fit", row_now["rigs_fit"] == fit, row_now["rigs_fit"])
    check("and the plan knows the deposit", book.plans[0]["deposit"] == row_now["id"], book.plans[0]["deposit"])
    check("the rigs a Rhino carries are still six", A.MAX_RIGS == 6 and len(plan["pins"]) <= 6)
    # Detail and My sites.
    app.on_pick(dict(row_now))
    shown = str(app.detail.cget("text"))
    check("deposit details say how many rigs fit", "rigs that fit: %s (a Rhino carries 6)" % fit in shown, shown)
    sites = [s for s in app.store.sites() if s["body"] == "Ega 1"]
    cells = A.site_cells(sites[0], ("", ""))
    check("My sites shows it beside the rigs", sites and sites[0]["fit"] >= 7
          and "(fit %s)" % fit in cells[5][0], cells[5])
    check("under a Rigs column that still counts only what the Rhino carries per deposit",
          sites[0]["rigs"] >= 3)
    # Restart: the plan comes back when you return.
    app.rig_plan = None
    app._plan_looked = (None, 0.0)
    at(*dest(spot[0], spot[1], 0.0, 150.0), flags=RHINO)
    marks = app.plan_marks()
    check("back on the deposit after a restart, the plan is restored",
          getattr(app, "rig_plan", None) and app.rig_plan.get("restored") and marks and len(marks["pins"]) == 6,
          marks and len(marks["pins"]))
    app.rig_plan = None
    app._plan_looked = (None, 0.0)
    at(*dest(*HOME, 270.0, 8000.0), flags=RHINO)
    app.plan_marks()
    check("a long way from it, nothing is restored", getattr(app, "rig_plan", None) is None)
    # A deposit marked after the plan.
    app._plan_looked = (None, 0.0)
    at(*dest(spot[0], spot[1], 0.0, 40.0), flags=RHINO)
    state = app.game
    check("a deposit marked on ground with a plan takes the plan's fit", app.rigs_fit_here(state, "3") == fit)
    at(*dest(*HOME, 180.0, 9000.0))
    check("with no plan it takes the commander's own entry", app.rigs_fit_here(app.game, "5") == "5")
    app.settings["survey_guide"] = True


@on_screen("Settings: the switches, the radius and the three keys are there and saved")
def _settings():
    win = A.SettingsWindow(app)
    pump(4)
    said, saved = [], []
    win.say = lambda text, colour=None: said.append(text)
    real_apply = app.apply_settings
    app.apply_settings = lambda data: saved.append(data)
    try:
        for name in ("survey_guide", "rhino_pointer", "orbit_guide"):
            check("Settings has a switch for %s, and a tip for it, on by default" % name,
                  name in win.toggles and name in A.SETTING_TIPS and win.toggles[name].get(), name)
        check("the waypoint radius is a box, 250 m", "waypoint_radius_m" in win.fields
              and str(win.fields["waypoint_radius_m"].get()) == "250", win.fields.get("waypoint_radius_m"))
        for name in ("hotkey_wp_next", "hotkey_wp_back", "hotkey_wp_skip", "hotkey_wp_pause"):
            check("%s is a key row, unbound until a key is picked" % name,
                  name in win.binders and win.bindings.get(name) == "" == A.DEFAULT_SETTINGS[name], win.bindings.get(name))
        check("the planner has no beta switch any more", "rig_planner" not in win.toggles
              and "rig_planner" not in A.SETTING_TIPS)
        check("and its key is not labelled a beta", "beta" not in " ".join(
            str(w.cget("text")).lower() for w in win.binders.values()))
        for typed, ok in (("49", False), ("1001", False), ("lots", False), ("400", True), ("1,000 m", True)):
            win.fields["waypoint_radius_m"].delete(0, "end")
            win.fields["waypoint_radius_m"].insert(0, typed)
            before = len(saved)
            win.save()
            pump(2)
            check("a waypoint radius of %r is %s" % (typed, "saved" if ok else "refused with the limits"),
                  (len(saved) > before) == ok and (ok or "50 to 1,000" in said[-1]), (typed, said[-1:]))
        check("400 went through as a whole number", any(d.get("waypoint_radius_m") == 400 for d in saved),
              [d.get("waypoint_radius_m") for d in saved])
        win.toggles["orbit_guide"].set(False)
        win.fields["waypoint_radius_m"].delete(0, "end")
        win.fields["waypoint_radius_m"].insert(0, "250")
        win.save()
        pump(2)
        check("a switch turned off is saved off", saved and saved[-1].get("orbit_guide") is False, saved[-1:])
    finally:
        app.apply_settings = real_apply
        win.destroy()
    defaults = {k: v for k, v in A.DEFAULT_SETTINGS.items() if k.startswith("hotkey_") and isinstance(v, str) and v}
    check("no two default keys are the same", len(set(v.upper() for v in defaults.values())) == len(defaults),
          sorted(defaults.items()))
    names = ("hotkey_wp_next", "hotkey_wp_back", "hotkey_wp_skip", "hotkey_wp_pause")
    check("the four waypoint keys ship unbound, so they cannot clash with a key already in use",
          all(A.DEFAULT_SETTINGS.get(n) == "" for n in names))
    taken = A.keep_new_keys_free(dict(A.DEFAULT_SETTINGS), {"hotkey_deposit": "ALT+="})
    check("a settings file that predates them reads them as blank", all(taken[n] == "" for n in names))
    check("a blank key is not registered", "wp_next" not in A.EDSMT.wanted_hotkeys(dict(app.settings, hotkey_wp_next="")))
    check("a key picked for skip is registered under its own action",
          A.EDSMT.wanted_hotkeys(dict(app.settings, hotkey_wp_skip="ALT+\\")).get("wp_skip") == "ALT+\\")


if __name__ == "__main__":
    if HAVE_DISPLAY:
        try:
            app.destroy()
        except Exception:
            pass
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    sys.exit(1 if fails else 0)
