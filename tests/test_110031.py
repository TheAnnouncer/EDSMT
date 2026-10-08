"""What 1.10031 adds, each piece held down so it stays built.

Driven without a display, like the other suites: the toolkit is stubbed,
positions are synthetic, and the server is FastAPI's own test client.

    python tests/test_110031.py
"""
import os, sys, json, math, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "stubs"))
import _ctkstub  # noqa
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="edsmt-110031-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
import edsmt as A, survey as SV, overlay as OV, journal as JN  # noqa
import rigplan as RP  # noqa
import edonline as EDO  # noqa

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)


SRC = open(A.__file__, encoding="utf-8").read()
R = 2_000_000.0
HOME = (10.0, 20.0)


def spot(east, north, origin=HOME):
    return RP.from_local(origin, east, north, R)


# ---------------------------------------------------------------------------
print("== the rig planner: geometry ==")
circle = [(120 * math.sin(2 * math.pi * k / 60), 120 * math.cos(2 * math.pi * k / 60))
          for k in range(60)]
pins = RP.plan(circle, 78.0)
check("six rigs fit in a 240 m circle at 78 m", len(pins) == 6, len(pins))
gaps = [math.hypot(a[0] - b[0], a[1] - b[1]) for i, a in enumerate(pins)
        for b in pins[i + 1:]]
check("and no two are closer than the spacing", min(gaps) >= 78.0 - 1e-6, min(gaps))
check("every pin is inside what was traced",
      all(RP.usable(circle, x, y) for x, y in pins))
small = [(20 * math.sin(2 * math.pi * k / 30), 20 * math.cos(2 * math.pi * k / 30))
         for k in range(30)]
check("a patch too small for two gets one, in the middle",
      len(RP.plan(small, 78.0)) == 1)
check("never more than six", len(RP.plan([(0, 0), (2000, 0), (2000, 2000),
                                          (0, 2000)], 78.0)) == 6)
check("nothing for a line that is not a shape", RP.plan([(0, 0), (10, 0)]) == [])
back = RP.to_local(HOME, spot(55.0, -32.0), R)
check("east/north and lat/lon go there and back to the centimetre",
      abs(back[0] - 55.0) < 0.01 and abs(back[1] + 32.0) < 0.01, back)
order = RP.drive_order([(100, 0), (10, 0), (50, 0)], (0, 0))
check("pins are driven nearest first", order == [(10, 0), (50, 0), (100, 0)], order)

print("== the rig planner: tracing from Status.json positions ==")
trace = RP.Trace(HOME[0], HOME[1], R)
check("on a big body the loop closes further out than 15 m - Status.json "
      "steps are that coarse", trace.close_m > RP.TRACE_CLOSE_M, trace.close_m)
closed_at = None
for k in range(1, 400):
    a = 2 * math.pi * k / 200
    lat, lon = spot(120 * math.sin(a), 120 * math.cos(a) - 120)
    # Status.json moves in 0.0005 degree steps in the SRV.
    lat, lon = round(lat / 0.0005) * 0.0005, round(lon / 0.0005) * 0.0005
    if trace.add(lat, lon):
        closed_at = k
        break
check("driving back round to the start closes the loop by itself",
      closed_at is not None and trace.closed, closed_at)
check("the pins come out as latitude and longitude, six of them",
      len(trace.pins(78.0)) == 6)
wobble = RP.Trace(HOME[0], HOME[1], R)
for k in range(20):
    wobble.add(*spot(3.0 * (k % 2), 0.0))
check("wobbling on the spot is not a loop", not wobble.closed)
far = RP.Trace(HOME[0], HOME[1], R)
far.add(*spot(4000.0, 0.0))
check("four kilometres off is a drive, not a trace", far.too_big)

print("== the rig planner in the app ==")


class _State:
    def __init__(self, lat, lon, heading=0.0):
        self.lat, self.lon, self.heading = lat, lon, heading
        self.radius_m = R
        self.has_position = True
        self.in_srv = True


def plan_app():
    papp = A.EDSMT.__new__(A.EDSMT)
    papp.settings = dict(A.DEFAULT_SETTINGS)
    papp.here = lambda: ("Ega", "Ega 1")
    papp.game = _State(*HOME)
    papp.said, papp.flashed = [], []
    papp.say = lambda text, colour=None: papp.said.append(text)
    papp.flash = lambda title, detail="", colour=None: papp.flashed.append(title)
    papp.redraw = lambda: None
    papp.key = lambda action, fallback="": "AltGr+2"
    papp.trouble = lambda stage, exc: papp.said.append("TROUBLE %s %s" % (stage, exc))
    papp.rigs_at = None
    return papp


check("the planner ships switched off - it is a beta",
      A.DEFAULT_SETTINGS["rig_planner"] is False)
check("its key is not even registered while it is off",
      "trace" not in A.EDSMT.wanted_hotkeys(A.DEFAULT_SETTINGS))
check("switched on, it is", A.EDSMT.wanted_hotkeys(
    dict(A.DEFAULT_SETTINGS, rig_planner=True)).get("trace") == "CTRL+ALT+2")
papp = plan_app()
papp.planner_trace()
check("pressed while it is off, it says how to switch it on, and starts nothing",
      papp.said and "Settings" in papp.said[-1]
      and papp.__dict__.get("_trace") is None, papp.said[-1:])
papp.settings["rig_planner"] = True
papp.planner_trace()
check("switched on, the key starts a trace", getattr(papp, "_trace", None)
      is not None and "TRACING" in papp.flashed[-1], papp.flashed[-1:])
marks = papp.plan_marks()
check("and the scope is told a trace is running",
      marks and marks["tracing"] and marks["near"], marks)
for k in range(1, 400):
    a = 2 * math.pi * k / 200
    papp.game = _State(*spot(120 * math.sin(a), 120 * math.cos(a) - 120))
    if papp.follow_trace(papp.game):
        break
plan = getattr(papp, "rig_plan", None)
check("driving the loop puts out the pins", plan and len(plan["pins"]) == 6,
      papp.said[-2:])
check("and says so over the game", any("RIG PLAN" in f for f in papp.flashed),
      papp.flashed[-2:])
marks = papp.plan_marks()
check("the scope gets the pins as metres from the commander, the next one "
      "named", marks and len(marks["pins"]) == 6 and marks["next"] == 1
      and marks["next_pin"]["n"] == 1 and marks["near"], marks and marks.get("next_pin"))
first = plan["pins"][0]
papp.game = _State(first["lat"], first["lon"])
papp.rigs_at = {"system": "Ega", "body": "Ega 1",
                "rigs": [{"n": 1, "lat": first["lat"], "lon": first["lon"]}]}
marks = papp.plan_marks()
check("a rig down on a pin marks it done, and the next pin is next",
      marks["pins"][0]["done"] and marks["done"] == 1 and marks["next"] == 2,
      (marks["done"], marks["next"]))
check("the rig's own message says which pin it went on",
      papp.plan_pin_at(first["lat"], first["lon"]) == 1)
papp.here = lambda: ("Ega", "Ega 2")
check("on another body the plan is not drawn", papp.plan_marks() is None)
papp.here = lambda: ("Ega", "Ega 1")
papp.planner_trace()
papp.game = _State(*spot(8.0, 0.0))
papp.planner_trace()
check("closing a trace by hand with too little driven cancels it, and says so",
      getattr(papp, "_trace", None) is None and "cancelled" in papp.said[-1],
      papp.said[-1:])
check("the spacing is a setting, kept to something sane",
      plan_app().planner_spacing() == 78.0
      and A.EDSMT.planner_spacing(type("X", (), {"settings": {"rig_spacing_m": 5}})())
      == A.PLAN_SPACING_MIN_M)
check("rigplan is in both PyInstaller specs",
      all('"rigplan"' in open(os.path.join(os.path.dirname(HERE), "build", s),
                              encoding="utf-8").read()
          for s in ("EDSMT.spec", "EDSMT-onefile.spec")))

# ---------------------------------------------------------------------------
print("== Earnings: a session is mining, not the Rhino being out ==")
books = SV.Earnings(os.path.join(TMP, "books"))


def saw(event, **note):
    return books.observe(dict(note, event=event))


def at(minutes):
    return "2026-09-30T%02d:%02d:00Z" % (10 + minutes // 60, minutes % 60)


saw("SRVLaunch", when=at(0), rhino=True, player=True, srv_id=7,
    system="Ega", body="Ega 1")
check("the Rhino going out opens nothing - it goes out to haul and to look too",
      books.current is None)
check("the first rig down opens the session",
      saw("RigDown", when=at(2), rig=1, system="Ega", body="Ega 1")
      == "Rhino session started - first rig down"
      and books.current["started_by"] == "rigs")
saw("Refined", when=at(5), commodity="Painite")
check("a crewmate's Rhino launching from the same ship is not this "
      "commander's trip", saw("SRVLaunch", when=at(6), rhino=True,
                              player=False, srv_id=8, system="Ega",
                              body="Ega 1") is None
      and books.current["trips"] == "1", books.current["trips"])
saw("SRVDock", when=at(7), srv_id=8)
check("and it coming back aboard does not end this one",
      books.current is not None and books._in_rhino)
check("every rig up ends it",
      saw("RigsUp", when=at(20), system="Ega", body="Ega 1")
      == "Rhino session done - every rig up" and books.current is None)
check("rigs down again on the same body soon after carry the same session on",
      saw("RigDown", when=at(25), rig=1, system="Ega", body="Ega 1")
      == "Rhino session carries on - rigs down again"
      and len(books.sessions) == 1)
saw("RigsUp", when=at(30), system="Ega", body="Ega 1")
saw("RigDown", when=at(50), rig=1, system="Ega", body="Ega 1")
check("but after ten minutes it is a new session", len(books.sessions) == 2)
check("the Start session button opens one only when none is running",
      books.start_now("Ega", "Ega 1") is None)
books.finish(at(55), by="button")
row = books.start_now("Ega", "Ega 1", when=at(60))
check("and says it opened it", row is not None and row["started_by"] == "button")

print("== Earnings: pause ==")
pb = SV.Earnings(os.path.join(TMP, "pause"))
pb._in_rhino = True
pb.observe({"event": "RigDown", "when": at(0), "system": "Ega", "body": "Ega 1"})
pb.observe({"event": "Refined", "when": at(5), "commodity": "Painite"})
pb.pause(at(10))
check("paused, the session says so", pb.paused)
pb.observe({"event": "MarketSell", "when": at(40), "commodity": "painite",
            "count": 1, "total": 100})
check("time paused is not mining time",
      abs(SV.session_hours(pb.current) - 10 / 60.0) < 1e-6,
      SV.session_hours(pb.current))
check("a rig down picks it up again by itself",
      pb.observe({"event": "RigDown", "when": at(70), "system": "Ega",
                  "body": "Ega 1"}) == "Session running again - rig down"
      and not pb.paused and pb.current["paused"] == "3600", pb.current)
pb.pause(at(80))
pb.finish(at(90), by="button")
last = pb.sessions[-1]
check("ended while paused, the pause runs to the end and is left out",
      last["paused_at"] == "" and last["paused"] == "4200"
      and abs(SV.session_hours(last) - 20 / 60.0) < 1e-6,
      (last["paused"], SV.session_hours(last)))
check("the rate is over the running time",
      SV.earned(last) == 100
      and abs(SV.credits_per_hour(last) - 100 / (20 / 60.0)) < 1e-6,
      (SV.earned(last), SV.credits_per_hour(last)))

print("== Earnings: only what was mined is priced ==")
mb = SV.Earnings(os.path.join(TMP, "mined"))
mb._in_rhino = True
_now = SV.utc_now()
mb.observe({"event": "Refined", "when": _now, "commodity": "Ruby", "n": 1,
            "system": "Ega", "body": "Ega 1"})
mb.observe({"event": "Refined", "when": _now, "commodity": "Ruby", "n": 2})
check("what recent sessions dug up and nobody sold",
      mb.unsold() == {"Ruby": 2}, mb.unsold())
happ = A.EDSMT.__new__(A.EDSMT)
happ.earnings = mb
happ.watcher = type("W", (), {"holds": {"Ship": {"Ruby": 5, "Tea": 40}},
                              "cargo": {}, "means": {"ruby": 150000}})()
check("the hold as the Earnings tab sees it: two Ruby, no Tea",
      happ.mined_aboard() == {"Ruby": 2}, happ.mined_aboard())
check("priced at the game's own galactic average when a market has shown it",
      happ.galactic_average("Ruby") == (150000, "game"))
happ.watcher.means = {}
check("and at EDSMT's table figure until then, marked as such",
      happ.galactic_average("Ruby")[1] == "table"
      and happ.galactic_average("Ruby")[0] == SV.published_price("Ruby"))
check("the estimate adds up", happ.hold_estimate({"Ruby": 2})
      == 2 * SV.published_price("Ruby"))
check("the window has Start, Pause and a galactic average column",
      'text="Start session"' in SRC and 'text="Pause"' in SRC
      and '"Galactic avg (est.)"' in SRC)
means = JN.market_means({"Items": [
    {"Name": "$ruby_name;", "Name_Localised": "Rubis", "MeanPrice": 123456},
    {"Name": "$tea_name;", "MeanPrice": 1500}, {"Name": "$x;", "MeanPrice": "?"}]})
check("the galactic average is read off Market.json's MeanPrice, in English "
      "whatever the language", means.get("ruby") == 123456
      and means.get("tea") == 1500 and len(means) == 2, means)
check("and an odd file gives nothing rather than a crash",
      JN.market_means({"Items": "nonsense"}) == {} and JN.market_means(None) == {})

print("== the journal: whose SRV it is ==")
JD = os.path.join(TMP, "journal"); os.makedirs(JD)
with open(os.path.join(JD, "Journal.2026-09-30T100000.01.log"), "w",
          encoding="utf-8") as fh:
    for ev in ({"timestamp": "2026-09-30T10:00:00Z", "event": "LaunchSRV",
                "SRVType": "mev_rhino", "SRVType_Localised": "SRV Rhino",
                "Loadout": "default", "ID": 53, "PlayerControlled": False},
               {"timestamp": "2026-09-30T10:01:00Z", "event": "LaunchSRV",
                "SRVType": "mev_rhino", "SRVType_Localised": "SRV Rhino",
                "Loadout": "default", "ID": 54, "PlayerControlled": True},
               {"timestamp": "2026-09-30T10:05:00Z", "event": "DockSRV",
                "SRVType": "mev_rhino", "ID": 53}):
        fh.write(json.dumps(ev) + "\n")
jw = JN.JournalWatcher(JD)
jw.poll()
notes = jw.drain_runs()
check("PlayerControlled and the SRV's ID come through from the journal",
      [(n.get("player"), n.get("srv_id")) for n in notes]
      == [(False, 53), (True, 54), (True, 53)], notes)

# ---------------------------------------------------------------------------
print("== the wing link ==")
check("ships switched off", A.DEFAULT_SETTINGS["wing_link"] is False)
check("codes are read the way the server takes them",
      A.clean_wing_code(" abc 234 ") == "ABC234" and A.clean_wing_code("ABC23") == ""
      and A.clean_wing_code("ABC2340") == "")
made = {A.new_wing_code() for _ in range(50)}
check("a made-up code has none of I, O, 0 or 1 to be misread",
      all(A.WING_CODE_RE.match(c) and not set(c) & set("IO01") for c in made)
      and len(made) > 45)


class _Comm:
    can_read = True
    share_name = True
    def __init__(self): self.beats = []
    def wing(self, code, beat): self.beats.append((code, beat)); return True


wapp = plan_app()
wapp.community = _Comm()
wapp.watcher = type("W", (), {"cmdr": "Jameson"})()
wapp.settings.update(wing_link=True, wing_code="ABC234")
A.save_settings = lambda settings: None
wapp.rigs_at = {"system": "Ega", "body": "Ega 1",
                "rigs": [{"n": 1, "lat": HOME[0], "lon": HOME[1]}]}
check("a beat goes out when the link is on", wapp.wing_tick(now=1000.0))
code, beat = wapp.community.beats[-1]
check("to the code typed, with where, which way and the rigs",
      code == "ABC234" and beat["system"] == "Ega" and beat["lat"] == HOME[0]
      and beat["rigs"] == [{"n": 1, "lat": HOME[0], "lon": HOME[1]}]
      and beat["name"] == "Jameson", beat)
check("its slot is made up once and kept",
      len(beat["member"]) >= 8 and wapp.settings["wing_member"] == beat["member"])
check("one beat in flight at a time", not wapp.wing_tick(now=1005.0))
mate = {"name": "CMDR Bee", "system": "Ega", "body": "Ega 1",
        "lat": spot(30.0, 0.0)[0], "lon": spot(30.0, 0.0)[1], "heading": 90.0,
        "in_srv": True, "rigs": [{"n": 2, "lat": spot(40.0, 0.0)[0],
                                  "lon": spot(40.0, 0.0)[1]}], "age_s": 1.0}
wapp.take_wing(True, json.dumps({"members": [mate]}))
check("the answer puts the wingmate on the link, and says so",
      wapp.wing_mates and "CMDR Bee" in wapp.said[-1], wapp.said[-1:])
marks = wapp.wing_marks()
check("and on the scope, 30 m east with a rig 40 m east",
      marks and abs(marks["mates"][0]["east"] - 30.0) < 0.5
      and abs(marks["mates"][0]["rigs"][0]["east"] - 40.0) < 0.5, marks)
clash = wapp.wing_clash(HOME[0], HOME[1])
check("a rig going down within the spacing of theirs is caught",
      clash and clash[0] == "CMDR Bee" and clash[1] == 2
      and abs(clash[2] - 40.0) < 0.5, clash)
check("the next beat goes after the gap", wapp.wing_tick(now=1005.0))
wapp.here = lambda: ("Ega", "Ega 2")
check("a wingmate on another body is not drawn", wapp.wing_marks() is None)
wapp.settings["wing_link"] = False
wapp.wing_tick(now=1100.0)
check("switched off, it says goodbye once and forgets the wing",
      wapp.community.beats[-1][1]["leave"] is True and wapp.wing_mates == []
      and wapp.wing_tick(now=1200.0) is False)

# The server half of the wing link and of the price in your own
# system is checked beside the server's source, which is private.

# ---------------------------------------------------------------------------
print("== text size per box, apart from the box ==")


class _Canvas:
    def __init__(self): self.fonts = []
    def create_text(self, *a, **k): self.fonts.append(k.get("font")); return 1
    def create_line(self, *a, **k): return 2


canvas = _Canvas()
big = OV.scaled_canvas(canvas, 1.5)
big.create_text(0, 0, text="x", font=("Consolas", 10, "bold"))
check("text drawn through a box set to 150% is half as big again",
      canvas.fonts[-1] == ("Consolas", 15, "bold"), canvas.fonts[-1])
check("and everything else goes straight through", big.create_line(0, 0, 1, 1) == 2)
check("at 100% the canvas is the canvas itself", OV.scaled_canvas(canvas, 1.0) is canvas)
check("every box has its own setting, at 100 to start",
      all(A.DEFAULT_SETTINGS["overlay_text_%s" % k] == 100 for k in
          (OV.STRIP, OV.RADAR, OV.TARGETS, OV.STATUS, OV.DEPOSIT, OV.GUIDE)))
check("and Settings has a size for each", SRC.count('"Text size: %s" % name') == 1
      and all('"%s"' % n in SRC for n in ("COMPASS", "SCOPE", "TARGETS",
                                          "MINERAL DEPOSIT", "GUIDE")))

# ---------------------------------------------------------------------------
print("== the first find of your own on the map is noticed ==")
# 1.10033: Find is open to everybody (sharing is always on); the first find
# the server takes is still noted, and still thanked for.
fapp = A.EDSMT.__new__(A.EDSMT)
fapp.settings = dict(A.DEFAULT_SETTINGS)
fapp.store = SV.Survey(os.path.join(TMP, "find"))
fapp.said = []
fapp.say = lambda text, colour=None: fapp.said.append(text)
check("the server taking one is remembered",
      fapp.note_shared("1 shared, 0 already known") and fapp.settings["find_unlocked"])
check("an answer that took nothing does not",
      A.EDSMT.note_shared(type("X", (), {"settings": {}, "say": lambda *a: None})(),
                          "0 shared, 0 already known") is False)

print("== the tables draw fast ==")
check("row buttons are plain Tk labels, not a toolkit button each",
      "def mini_button(" in SRC and "row_buttons(self.table, index" in SRC
      and 'ctk.CTkButton(box, text=label, width=58' not in SRC)
check("My sites draws a page at a time", SRC.count("def _draw_page(self):") >= 2)
check("finished searches are picked up on the fast tick",
      SRC.split("    def fast_tick(self):")[1].split("\n    def ")[0]
      .count("self.collect_results()") == 1)

print("== the guide goes away after the first full run ==")
check("the guide retires itself once, and can be switched back on",
      A.DEFAULT_SETTINGS["guide_done"] is False and "def retire_guide" in SRC
      and 'self._switch(body, "overlay_show_guide"' in SRC)

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
