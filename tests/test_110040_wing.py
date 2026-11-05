"""1.10040 (#170, #171, #172): the wing link grows up.

- #170 Linked with your in-game wing by itself: the journal's own wing
  events say who is in your wing; with "Link with my in-game wing by
  itself" on (it starts on), two commanders who are both running EDSMT and
  each have the other in their wing are linked with no code to type. The
  server pairs only commanders who list each other. Leaving the wing in
  the game drops the link. A typed code still works as before.
- #171 One shared survey: over the link go the ground your scanner has
  swept on this body, the finds you have marked there, and your rig plan's
  pins - each small, with a fixed most - so the map and the scope show the
  wing's sweep and finds, each wingmate in a colour of their own. A find a
  wingmate marks is said as it arrives.
- #172 A rig plan's pins split between the wingmates on that deposit, in
  turn by name; each of you is guided only to your own, and a switch turns
  the split off.

Driven without a display, like the other suites: the toolkit is stubbed and
positions are synthetic.

    python tests/test_110040_wing.py
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "stubs"))
import _ctkstub  # noqa: E402,F401
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-wing-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import wingmates as WM     # noqa: E402
import survey as SV        # noqa: E402
import rigplan as RP       # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def section(title):
    def wrap(fn):
        print("== " + title + " ==")
        try:
            fn()
        except Exception as exc:
            import traceback
            check(title + " (ran to the end)", False, "%s: %s" % (type(exc).__name__, exc))
            traceback.print_exc(limit=8)
        return fn
    return wrap


R = 2_000_000.0
HOME = (10.0, 20.0)


def spot(east, north, origin=HOME):
    return RP.from_local(origin, east, north, R)


@section("who is in your wing, from the journal's own events")
def _roster():
    after = WM.roster_after
    joined = after([], {"event": "WingJoin", "Others": ["Bee", "Cee"]})
    check("WingJoin: the others already in the wing", joined == ["Bee", "Cee"], joined)
    added = after(joined, {"event": "WingAdd", "Name": "Dee"})
    check("WingAdd: one more", added == ["Bee", "Cee", "Dee"] and joined == ["Bee", "Cee"], added)
    check("the same commander twice is one, whatever the case or a CMDR in front",
          after(added, {"event": "WingAdd", "Name": "CMDR  bee"}) == added)
    check("WingLeave: nobody", after(added, {"event": "WingLeave"}) == [])
    check("a new game, or the game shut: nobody",
          after(added, {"event": "LoadGame", "Commander": "Jameson"}) == []
          and after(added, {"event": "Shutdown"}) == [])
    check("anything else leaves it as it was",
          after(added, {"event": "WingInvite", "Name": "Eee"}) == added
          and after(added, {"event": "Music", "MusicTrack": "x"}) == added)
    check("names given as objects are read too",
          after([], {"event": "WingJoin", "Others": [{"Name": "Bee"}, {"name": "Cee"}]})
          == ["Bee", "Cee"])
    check("rubbish is nobody, not a crash",
          after([], {"event": "WingJoin", "Others": "Bee"}) == []
          and after([], {"event": "WingJoin", "Others": [None, 3, ""]}) == ["3"]
          and after(["Bee"], "nonsense") == ["Bee"])
    many = after([], {"event": "WingJoin", "Others": ["N%d" % i for i in range(20)]})
    check("never more than a wing can hold", len(many) == WM.MAX_MATES, len(many))
    check("a name is matched without CMDR, spacing or case",
          WM.fold(" CMDR  Bee  Bop ") == WM.fold("bee bop") and WM.fold("") == "")


@section("a colour for each wingmate")
def _colours():
    names = ["Jameson", "Bee", "Cee", "Dee"]
    got = WM.colours(names)
    check("one for each name", sorted(got) == sorted(WM.fold(n) for n in names), got)
    check("no two alike in one wing", len(set(got.values())) == len(names), got)
    check("the same name gets the same colour every time, whoever else is there",
          WM.colours(["Bee"])[WM.fold("Bee")] == WM.colours(["Bee", "Zed"])[WM.fold("Bee")]
          or len(WM.PALETTE) < 2)
    check("and the same whichever order they come in",
          WM.colours(list(reversed(names))) == got)
    eight = WM.colours(["N%d" % i for i in range(len(WM.PALETTE))])
    check("a full wing of eight still has eight colours", len(set(eight.values())) == len(WM.PALETTE))

    def rgb(c):
        return tuple(int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    apart = min(sum((a - b) ** 2 for a, b in zip(rgb(x), rgb(y))) ** 0.5
                for i, x in enumerate(WM.PALETTE) for y in WM.PALETTE[i + 1:])
    check("the colours are far enough apart to tell at a glance", apart >= 55, apart)
    import overlay as OV
    used = {c.lower() for c in (OV.ORANGE, OV.AMBER, OV.CYAN, OV.RED, OV.GREEN_OK, OV.DIM, OV.TEXT)}
    check("and none of them is an instrument colour", not used & {c.lower() for c in WM.PALETTE})


@section("what one beat carries for the shared survey")
def _beat():
    path = [spot(0.0, 50.0 * k) for k in range(400)]       # 20 km north, a fix every 50 m
    sweep = WM.sweep_for_beat(path, R)
    check("the ground swept: at most the most", 0 < len(sweep) <= WM.SWEEP_MAX, len(sweep))
    gaps = [SV.surface_range_m(a[0], a[1], b[0], b[1], R) for a, b in zip(sweep, sweep[1:])]
    check("each kept point at least the gap from the one before",
          min(gaps) >= WM.SWEEP_GAP_M - 1.0, min(gaps))
    check("the newest kept: the last place driven is in it",
          SV.surface_range_m(sweep[-1][0], sweep[-1][1], path[-1][0], path[-1][1], R) < 1.0)
    check("rounded to about a metre", all(len(("%r" % p[0]).split(".")[-1]) <= 5 for p in sweep))
    check("nothing swept, nothing sent", WM.sweep_for_beat([], R) == [])
    rows = [{"commodity": "Painite", "lat": "%.6f" % spot(10, 0)[0], "lon": "%.6f" % spot(10, 0)[1],
             "amount": "High", "recorded": "2026-11-04T10:00:00Z"},
            {"commodity": "Gold", "lat": "%.6f" % spot(20, 0)[0], "lon": "%.6f" % spot(20, 0)[1],
             "amount": "Depleted", "recorded": "2026-11-04T11:00:00Z"},
            {"commodity": "Silver", "lat": "%.6f" % spot(50000, 0)[0], "lon": "%.6f" % spot(50000, 0)[1],
             "amount": "High", "recorded": "2026-11-04T12:00:00Z"},
            {"commodity": "", "lat": "1", "lon": "1"},
            {"commodity": "Gold", "lat": "x", "lon": "1"}]
    finds = WM.finds_for_beat(rows, HOME[0], HOME[1], R)
    check("the finds near you, newest first, with what and where",
          [f["c"] for f in finds] == ["Gold", "Painite"], finds)
    check("a worked-out one says so", finds[0]["d"] is True and finds[1]["d"] is False, finds)
    many = [dict(rows[0], recorded="2026-11-04T10:%02d:00Z" % i) for i in range(60)]
    check("never more than the most", len(WM.finds_for_beat(many, HOME[0], HOME[1], R)) == WM.FINDS_MAX)
    plan = {"system": "ega", "body": "ega 1", "spacing": 78.0,
            "pins": [{"n": i + 1, "lat": spot(80 * i, 0)[0], "lon": spot(80 * i, 0)[1]}
                     for i in range(6)]}
    pins = WM.pins_for_beat(plan, "Ega", "Ega 1")
    check("your rig plan's pins, numbered", [p["n"] for p in pins] == [1, 2, 3, 4, 5, 6], pins)
    check("only on its own body", WM.pins_for_beat(plan, "Ega", "Ega 2") == [])
    check("never a layout somebody else shared",
          WM.pins_for_beat(dict(plan, shared=True), "Ega", "Ega 1") == []
          and WM.pins_for_beat(dict(plan, wing=True), "Ega", "Ega 1") == [])
    check("no plan, no pins", WM.pins_for_beat(None, "Ega", "Ega 1") == [])


@section("finds that are new since the last beat (marked live)")
def _live():
    one = {"c": "Painite", "lat": 1.0, "lon": 2.0}
    two = {"c": "Gold", "lat": 1.001, "lon": 2.0}
    fresh, seen = WM.new_finds(None, [one])
    check("the first beat from a wingmate is what they had, not news", fresh == [] and len(seen) == 1)
    fresh, seen = WM.new_finds(seen, [one, two])
    check("the next one with a find in it is news", fresh == [two], fresh)
    fresh, seen = WM.new_finds(seen, [one, two])
    check("and only once", fresh == [])
    check("rubbish is skipped", WM.new_finds(seen, [{"c": "x"}, "y", None])[0] == [])


@section("one plan a wing follows, and its pins split between the wing")
def _split():
    pick = WM.pick_plan
    check("nobody's plan: none", pick([]) is None and pick([("Bee", [])]) is None)
    check("the plan with the most pins", pick([("Bee", [1, 2]), ("Cee", [1, 2, 3])])[0] == "Cee")
    check("between equals, the first name", pick([("Cee", [1, 2]), ("bee", [1, 2])])[0] == "bee")
    split = WM.split_pins([1, 2, 3, 4, 5, 6], ["Jameson", "Bee"])
    check("six pins, two of you: three each, in runs, the first name first",
          split == {1: "bee", 2: "bee", 3: "bee", 4: "jameson", 5: "jameson", 6: "jameson"}, split)
    split = WM.split_pins([1, 2, 3, 4, 5], ["Cee", "Bee", "Dee"])
    check("five between three: the spare ones go to the first names",
          [split[n] for n in range(1, 6)] == ["bee", "bee", "cee", "cee", "dee"], split)
    check("every observer works out the same split",
          WM.split_pins([1, 2, 3], ["Bee", "Cee"]) == WM.split_pins([1, 2, 3], ["cee", "CMDR Bee"]))
    check("nobody, nothing", WM.split_pins([1, 2], []) == {})
    crew = WM.crew_after({"bee"}, ["Cee"], ["Bee", "Cee", "Dee"])
    check("the crew of a deposit: still there, and newly near its pins", crew == {"bee", "cee"}, crew)
    check("off the link, or off the body: out", WM.crew_after({"bee", "cee"}, [], ["Cee"]) == {"cee"})
    mates = [{"name": "Bee"}, {"name": "Zed"}]
    check("an in-game link shows only the commanders in your own wing",
          [m["name"] for m in WM.listed(mates, ["CMDR bee"])] == ["Bee"])


# ---------------------------------------------------------------------------
import journal as JN       # noqa: E402


@section("the journal reader keeps the wing")
def _journal():
    folder = os.path.join(TMP, "journals")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "Journal.2026-11-04T100000.01.log")
    lines = [{"timestamp": "2026-11-04T10:00:00Z", "event": "Fileheader", "part": 1,
              "gameversion": "4.4.1.1"},
             {"timestamp": "2026-11-04T10:00:01Z", "event": "Commander", "FID": "F1", "Name": "Jameson"},
             {"timestamp": "2026-11-04T10:00:02Z", "event": "LoadGame", "Commander": "Jameson"},
             {"timestamp": "2026-11-04T10:05:00Z", "event": "WingJoin", "Others": ["Bee"]},
             {"timestamp": "2026-11-04T10:06:00Z", "event": "WingAdd", "Name": "Cee"}]
    with open(path, "w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(json.dumps(line) + "\n")
    watcher = JN.JournalWatcher(folder)
    watcher.poll()
    check("the reader has the wing: Bee, then Cee", watcher.wing == ["Bee", "Cee"], watcher.wing)
    check("and who you are, from the journal", watcher.cmdr == "Jameson")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"timestamp": "2026-11-04T10:07:00Z", "event": "WingLeave"}) + "\n")
    watcher.poll()
    check("left in the game: nobody", watcher.wing == [], watcher.wing)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"timestamp": "2026-11-04T10:08:00Z", "event": "WingJoin",
                                 "Others": ["Dee"]}) + "\n")
        handle.write(json.dumps({"timestamp": "2026-11-04T10:09:00Z", "event": "Shutdown"}) + "\n")
    watcher.poll()
    check("the game shut: nobody", watcher.wing == [], watcher.wing)


# ---------------------------------------------------------------------------
import edonline as EDO     # noqa: E402


@section("the client: one beat to the in-game wing link")
def _client():
    client = EDO.CommunityClient.__new__(EDO.CommunityClient)
    sent = []

    class _Worker:
        def submit(self, tag, fn):
            sent.append((tag, fn))
    client.worker = _Worker()
    client.base_url = "https://example.invalid"
    client._headers = lambda: {}
    reading = EDO.CommunityClient.can_read
    EDO.CommunityClient.can_read = property(lambda self: True)
    beat = {"member": "aaaaaaaa11", "cmdr": "Jameson", "wing": ["Bee"]}
    posted = []
    real = EDO.post_json
    EDO.post_json = lambda url, payload, **kw: posted.append((url, payload)) or {"members": []}
    try:
        check("a beat goes out", client.wing_auto(beat) is True and sent
              and sent[-1][0] == EDO.WING_AUTO_TAG)
        answer = sent[-1][1]()
        check("nothing to send without a beat", client.wing_auto({}) is False)
    finally:
        EDO.post_json = real
        EDO.CommunityClient.can_read = reading
    check("to the in-game wing link, with the commander and the wing",
          posted and posted[-1][0].endswith("/v1/wing/auto") and posted[-1][1]["wing"] == ["Bee"]
          and json.loads(answer) == {"members": []}, posted)


# ---------------------------------------------------------------------------
import edsmt as A          # noqa: E402

A.save_settings = lambda settings: None


class _State:
    def __init__(self, lat, lon, heading=0.0):
        self.lat, self.lon, self.heading = lat, lon, heading
        self.radius_m = R
        self.has_position = True
        self.in_srv = True
        self.in_rhino = True
        self.altitude = None


class _Comm:
    can_read = True
    share_name = True

    def __init__(self):
        self.beats, self.auto = [], []

    def wing(self, code, beat):
        self.beats.append((code, beat))
        return True

    def wing_auto(self, beat):
        self.auto.append(beat)
        return True


class _Store:
    def __init__(self, rows=None):
        self.rows = rows or []

    def at(self, system, body, location=None):
        return [r for r in self.rows if r["system"] == system and r["body"] == body]


def stub_app():
    app = A.EDSMT.__new__(A.EDSMT)
    app.settings = dict(A.DEFAULT_SETTINGS)
    app.here = lambda: ("Ega", "Ega 1")
    app.signal = lambda: "1"
    app.game = _State(*HOME)
    app.said, app.flashed = [], []
    app.say = lambda text, colour=None: app.said.append(text)
    app.flash = lambda title, detail="", colour=None: app.flashed.append(title)
    app.redraw = lambda: None
    app.key = lambda action, fallback="": "AltGr+2"
    app.trouble = lambda stage, exc: app.said.append("TROUBLE %s %s" % (stage, exc))
    app.rigs_at = None
    app.rig_plan = None
    app._trace = None
    app.restore_plan = lambda: None
    app.layouts = {}
    app.community = _Comm()
    app.watcher = type("W", (), {"cmdr": "Jameson", "wing": []})()
    app.store = _Store()
    return app


@section("the switches a new install starts with")
def _defaults():
    D = A.DEFAULT_SETTINGS
    check("Link with my in-game wing by itself: on", D.get("wing_auto") is True)
    check("Split the rig plan's pins between the wing: on", D.get("wing_split_pins") is True)
    check("the typed-code link still starts off", D.get("wing_link") is False)
    check("each has a note in Settings", all(A.SETTING_TIPS.get(k) for k in ("wing_auto", "wing_split_pins")))


@section("#170: linked with your in-game wing, no code")
def _auto():
    app = stub_app()
    check("nobody in your wing in the game: nothing is sent", app.wing_auto_tick(now=1000.0) is False
          and app.community.auto == [])
    app.watcher.wing = ["Bee"]
    check("in a wing: a beat goes out with no code typed", app.wing_auto_tick(now=1000.0) is True)
    beat = app.community.auto[-1]
    check("it carries who you are, from the journal, and who is in your wing",
          beat["cmdr"] == "Jameson" and beat["wing"] == ["Bee"] and beat["leave"] is False
          and len(beat["member"]) >= 8, beat)
    check("one beat in flight at a time", app.wing_auto_tick(now=1001.0) is False)
    mate = {"name": "Bee", "system": "Ega", "body": "Ega 1",
            "lat": spot(30.0, 0.0)[0], "lon": spot(30.0, 0.0)[1], "heading": 90.0, "in_srv": True,
            "rigs": [], "age_s": 1.0}
    stranger = dict(mate, name="Zed")
    app.take_wing_auto(True, json.dumps({"members": [mate, stranger]}))
    check("the answer puts the wingmate on the link, and says so",
          [m["name"] for m in app.wing_auto_mates] == ["Bee"] and "Bee" in app.said[-1], app.said[-1:])
    check("a commander not in your own wing is never shown, whatever the answer says",
          all(m["name"] != "Zed" for m in app.wing_auto_mates))
    check("the link is on without the typed-code switch", app.wing_active() and not app.wing_on())
    marks = app.wing_marks()
    check("and the wingmate is on the scope, 30 m east",
          marks and abs(marks["mates"][0]["east"] - 30.0) < 0.5, marks)
    check("in a colour of their own", marks["mates"][0]["colour"] in WM.PALETTE, marks)
    check("the next beat goes after the gap", app.wing_auto_tick(now=1000.0 + A.WING_BEAT_S + 0.1))
    app.watcher.wing = []
    app.wing_auto_tick(now=1020.0)
    check("left the wing in the game: it says goodbye once and the wingmate goes",
          app.community.auto[-1]["leave"] is True and app.wing_auto_mates == []
          and app.wing_marks() is None and app.wing_auto_tick(now=1030.0) is False)
    app.watcher.wing = ["Bee"]
    app.settings["wing_auto"] = False
    check("switched off: nothing goes, wing or no wing", app.wing_auto_tick(now=1040.0) is False)
    app.settings["wing_auto"] = True
    app.watcher.cmdr = ""
    check("no commander name from the journal yet: nothing goes", app.wing_auto_tick(now=1050.0) is False)
    app.watcher.cmdr = "Jameson"
    app.wing_auto_tick(now=1060.0)
    app.take_wing_auto(False, "could not reach the server")
    check("a failure is said once", sum("could not reach" in s for s in app.said) == 1)
    app._wing_auto_busy = False
    check("and the next try waits longer than a beat", not app.wing_auto_tick(now=1061.0 + A.WING_BEAT_S))
    # A typed code still works beside it, and the two lists are one wing.
    app = stub_app()
    app.settings.update(wing_link=True, wing_code="ABC234")
    app.watcher.wing = ["Bee"]
    check("a typed code still beats as before", app.wing_tick(now=1000.0)
          and app.community.beats[-1][0] == "ABC234")
    app.take_wing(True, json.dumps({"members": [dict(mate, name="Cee")]}))
    app.take_wing_auto(True, json.dumps({"members": [mate]}))
    names = sorted(m["name"] for m in app.wing_mates_all())
    check("both links' wingmates are one wing", names == ["Bee", "Cee"], names)
    app.take_wing(True, json.dumps({"members": [dict(mate, name="CMDR Bee"), dict(mate, name="Cee")]}))
    names = sorted(m["name"] for m in app.wing_mates_all())
    check("somebody on both links is there once", len(names) == 2, names)


@section("#171: the shared survey goes out with every beat")
def _survey_out():
    app = stub_app()
    app.settings.update(wing_link=True, wing_code="ABC234")

    class _Map:
        system, body, scan_m = "Ega", "Ega 1", 2000.0
        points = [spot(0.0, 100.0 * k) for k in range(50)]
    app.cmap = _Map()
    app._survey_map = lambda: app.cmap
    app.store = _Store([{"system": "Ega", "body": "Ega 1", "commodity": "Painite",
                         "lat": "%.6f" % spot(10, 0)[0], "lon": "%.6f" % spot(10, 0)[1],
                         "amount": "High", "recorded": "2026-11-04T10:00:00Z"}])
    app.rig_plan = {"system": "ega", "body": "ega 1", "spacing": 78.0, "outline": [],
                    "pins": [{"n": i + 1, "lat": spot(80 * i, 0)[0], "lon": spot(80 * i, 0)[1]}
                             for i in range(4)]}
    beat = app.wing_beat()
    check("the ground swept on this body", 2 <= len(beat["sweep"]) <= WM.SWEEP_MAX
          and beat["scan_m"] == 2000.0, len(beat.get("sweep") or []))
    check("the finds marked here", [f["c"] for f in beat["finds"]] == ["Painite"], beat.get("finds"))
    check("and the rig plan's pins and spacing", [p["n"] for p in beat["pins"]] == [1, 2, 3, 4]
          and beat["spacing"] == 78.0, beat.get("pins"))
    check("small: under 8 KB as sent", len(json.dumps(beat)) < 8192, len(json.dumps(beat)))
    app.cmap.body = "Ega 2"
    check("a sweep on another body is not sent", app.wing_beat()["sweep"] == [])
    check("a goodbye carries nothing but itself",
          app.wing_beat(leave=True).get("sweep", []) == [] and app.wing_beat(leave=True).get("finds", []) == [])


@section("#171: the wing's sweep and finds come back, each in its colour; new finds said")
def _survey_in():
    app = stub_app()
    app.settings.update(wing_link=True, wing_code="ABC234")
    sweep = [list(spot(0.0, 400.0 * k)) for k in range(5)]
    mate = {"name": "Bee", "system": "Ega", "body": "Ega 1",
            "lat": spot(30.0, 0.0)[0], "lon": spot(30.0, 0.0)[1], "in_srv": True, "rigs": [],
            "age_s": 1.0, "scan_m": 2000.0, "sweep": sweep,
            "finds": [{"c": "Painite", "lat": spot(0, 60)[0], "lon": spot(0, 60)[1], "d": False}]}
    app.take_wing(True, json.dumps({"members": [mate]}))
    marks = app.wing_marks()
    got = marks["mates"][0]
    check("their sweep, as metres from you", len(got["sweep"]) == 5
          and abs(got["sweep"][-1][1] - 1600.0) < 1.0 and got["scan_m"] == 2000.0, got.get("sweep"))
    check("their finds, with what each is", got["finds"][0]["commodity"] == "Painite"
          and abs(got["finds"][0]["north"] - 60.0) < 0.5, got.get("finds"))
    check("all in their colour", got["colour"] in WM.PALETTE)
    check("what they had already is not news", not any("marked" in s for s in app.said), app.said)
    mate2 = dict(mate, finds=mate["finds"] + [{"c": "Gold", "lat": spot(0, -90)[0],
                                               "lon": spot(0, -90)[1], "d": False}])
    app.take_wing(True, json.dumps({"members": [mate2]}))
    check("a find they mark now is said as it comes in, with where",
          any("Bee marked Gold" in s and "90 m" in s for s in app.said), app.said[-2:])
    other = dict(mate, body="Ega 2")
    app.take_wing(True, json.dumps({"members": [other]}))
    check("a wingmate on another body draws nothing", app.wing_marks() is None)
    said = len(app.said)
    back = dict(mate2, finds=mate2["finds"] + [{"c": "Silver", "lat": spot(0, 30)[0],
                                               "lon": spot(0, 30)[1], "d": False}])
    app.take_wing(True, json.dumps({"members": [back]}))
    check("arriving on your body, what they had is not news either",
          not any("marked" in s for s in app.said[said:]), app.said[said:])


@section("#171: one shared survey - the wing's sweep counts in the swept figure")
def _survey_percent():
    import coverage as CV
    cmap = CV.CoverageMap("Ega", "Ega 1", R, scan_m=500.0)
    cmap.set_centre(*HOME)
    cmap.set_border(*spot(2000.0, 0.0))
    for k in range(5):
        cmap.add_fix(*spot(-1500.0 + 100.0 * k, 0.0))
    alone = cmap.coverage()["percent"]
    version = cmap._version
    extra = [spot(1500.0, 0.0), spot(0.0, 1500.0), spot(0.0, -1500.0), spot(0.0, 0.0)]
    both = cmap.coverage_with(extra)
    check("your sweep and the wing's together cover more", both["percent"] > alone, (alone, both))
    check("and the map itself is untouched - nothing of theirs is kept",
          cmap.coverage()["percent"] == alone and cmap._version == version
          and len(cmap.points) == 5)
    check("the gaps are what neither of you has swept",
          len(both["gaps"]) >= 1 and all(g["area_km2"] > 0 for g in both["gaps"]), both.get("gaps"))
    check("nothing extra is the map's own answer", cmap.coverage_with([])["percent"] == alone)


@section("#172: the pins split between the wing on that deposit")
def _pins():
    app = stub_app()
    app.settings.update(wing_link=True, wing_code="ABC234")
    app.rig_plan = {"system": "ega", "body": "ega 1", "spacing": 78.0, "outline": [],
                    "pins": [{"n": i + 1, "lat": spot(80 * i, 0)[0], "lon": spot(80 * i, 0)[1]}
                             for i in range(6)]}
    alone = app.plan_marks()
    check("alone: every pin is yours, P1 first", alone["next"] == 1
          and all(p.get("mine", True) for p in alone["pins"]), alone)
    mate = {"name": "Bee", "system": "Ega", "body": "Ega 1",
            "lat": spot(200.0, 0.0)[0], "lon": spot(200.0, 0.0)[1], "in_srv": True, "rigs": [],
            "age_s": 1.0}
    app.take_wing(True, json.dumps({"members": [mate]}))
    split = app.plan_marks()
    owners = [(p["n"], p.get("mine")) for p in split["pins"]]
    check("with Bee on the deposit: Bee takes P1-P3, you P4-P6 (by name)",
          owners == [(1, False), (2, False), (3, False), (4, True), (5, True), (6, True)], owners)
    check("and you are guided to your own first pin", split["next"] == 4, split.get("next"))
    check("Bee's pins carry Bee's name and colour",
          split["pins"][0]["owner"] == "Bee" and split["pins"][0]["colour"] in WM.PALETTE, split["pins"][0])
    mate_rigs = dict(mate, rigs=[{"n": 1, "lat": spot(0, 0)[0], "lon": spot(0, 0)[1]}])
    app.take_wing(True, json.dumps({"members": [mate_rigs]}))
    check("a rig of Bee's on a pin counts it as done for you too", app.plan_marks()["pins"][0]["done"])
    app.settings["wing_split_pins"] = False
    off = app.plan_marks()
    check("the split switched off: every pin yours again, P2 next",
          all(p.get("mine", True) for p in off["pins"]) and off["next"] == 2, off.get("next"))
    app.settings["wing_split_pins"] = True
    far = dict(mate, lat=spot(5000.0, 0.0)[0], lon=spot(5000.0, 0.0)[1])
    app2 = stub_app()
    app2.settings.update(wing_link=True, wing_code="ABC234")
    app2.rig_plan = app.rig_plan
    app2.take_wing(True, json.dumps({"members": [far]}))
    check("a wingmate on the body but nowhere near the deposit takes no pins",
          all(p.get("mine", True) for p in app2.plan_marks()["pins"]))
    # No plan of your own: the wing's plan is followed, and split.
    app3 = stub_app()
    app3.settings.update(wing_link=True, wing_code="ABC234")
    planner = dict(mate, name="Cee", pins=[{"n": i + 1, "lat": spot(80 * i, 0)[0],
                                             "lon": spot(80 * i, 0)[1]} for i in range(4)],
                   spacing=80.0)
    app3.take_wing(True, json.dumps({"members": [planner]}))
    marks = app3.plan_marks()
    check("no plan of your own: Cee's pins on your scope too",
          marks and len(marks["pins"]) == 4 and marks.get("wing") and marks.get("by") == "Cee", marks)
    check("split with Cee: P1-P2 Cee's, P3-P4 yours (Cee before Jameson)",
          [p.get("mine") for p in marks["pins"]] == [False, False, True, True] and marks["next"] == 3,
          [(p["n"], p.get("mine")) for p in marks["pins"]])
    check("your own beat never sends somebody else's plan as yours", app3.wing_beat()["pins"] == [])
    # Your own plan, and a wingmate's bigger one on the next deposit along.
    app4 = stub_app()
    app4.settings.update(wing_link=True, wing_code="ABC234")
    app4.rig_plan = dict(app.rig_plan, pins=app.rig_plan["pins"][:3])
    elsewhere = dict(planner, name="Abe", lat=spot(900.0, 0.0)[0], lon=spot(900.0, 0.0)[1],
                     pins=[{"n": i + 1, "lat": spot(800.0 + 80 * i, 0)[0],
                            "lon": spot(800.0 + 80 * i, 0)[1]} for i in range(6)])
    app4.take_wing(True, json.dumps({"members": [elsewhere]}))
    marks = app4.plan_marks()
    check("a wingmate's plan for another deposit never takes the place of yours",
          marks and len(marks["pins"]) == 3 and not marks.get("wing"), marks and len(marks["pins"]))
    same = dict(elsewhere, lat=spot(100.0, 0.0)[0], lon=spot(100.0, 0.0)[1],
                pins=[{"n": i + 1, "lat": spot(10.0 + 80 * i, 0)[0], "lon": spot(10.0 + 80 * i, 0)[1]}
                      for i in range(6)])
    app4.take_wing(True, json.dumps({"members": [same]}))
    marks = app4.plan_marks()
    check("but theirs for the same deposit, with more pins, is the one the wing follows",
          marks and len(marks["pins"]) == 6 and marks.get("wing") and marks.get("by") == "Abe",
          marks and (len(marks["pins"]), marks.get("by")))


@section("#171: the shared figure only with a survey border")
def _cover_border():
    import coverage as CV
    app = stub_app()
    app.settings.update(wing_link=True, wing_code="ABC234")
    mate = {"name": "Bee", "system": "Ega", "body": "Ega 1", "lat": HOME[0], "lon": HOME[1],
            "age_s": 1.0, "rigs": [], "sweep": [list(spot(0.0, 500.0 * k)) for k in range(4)]}
    app.take_wing(True, json.dumps({"members": [mate]}))
    cmap = CV.CoverageMap("Ega", "Ega 1", R, scan_m=500.0)
    cmap.add_fix(*HOME)
    check("no border yet: your own figure, nothing worked out for the wing",
          "gaps" not in app.survey_cover(cmap))
    cmap.set_centre(*HOME)
    cmap.set_border(*spot(1500.0, 0.0))
    cover = app.survey_cover(cmap)
    check("with a border: the wing's swept ground counts in", "gaps" in cover
          and cover["percent"] > cmap.coverage()["percent"], (cover.get("percent"), cmap.coverage()))
    app.cmap = cmap
    line = app.survey_summary()
    check("and the line under the survey says so", "with your wing" in line, line)


if __name__ == "__main__":
    print()
    print("FAILURES:", len(fails))
    for f in fails:
        print("  -", f)
    sys.exit(1 if fails else 0)
