"""What the testers hit on 1.10029, each one held down so it stays fixed.

Driven without a display: the toolkit is stubbed, the game is synthetic
Status.json and journal lines shaped like the author's own 4.4.1.1 journals
(read, never written), and anything Windows-only is exercised through the
logic that decides it rather than through Windows itself.
"""
import os, sys, json, math, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "stubs"))
import _ctkstub  # noqa
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="edsmt-field-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
import edsmt as A, survey as SV, overlay as OV, journal as JN, planview as PV  # noqa

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)


SRC = open(A.__file__, encoding="utf-8").read()
OVSRC = open(OV.__file__, encoding="utf-8").read()
R = 1_800_000.0
HOME = (12.5, -45.5)


def dest(lat, lon, bearing, metres):
    p1, l1, th, d = math.radians(lat), math.radians(lon), math.radians(bearing), metres / R
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(th))
    l2 = l1 + math.atan2(math.sin(th) * math.sin(d) * math.cos(p1),
                         math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), math.degrees(l2)


print("== the keys: Alt+1 to Alt+6 are heard, and any key can be bound ==")


class _Event:
    def __init__(self, keysym, state):
        self.keysym, self.state = keysym, state


_was = A.ALT_STATE
A.ALT_STATE = 0x20000          # as on Windows
check("on Windows, Num Lock is not Alt: F1 with Num Lock on is F1",
      A.binding_from_event(_Event("F1", 0x0008)) == "F1",
      A.binding_from_event(_Event("F1", 0x0008)))
check("and Alt is Alt", A.binding_from_event(_Event("1", 0x20000 | 0x0008))
      == "ALT+1", A.binding_from_event(_Event("1", 0x20000 | 0x0008)))
check("a plain key can be bound - nothing forces Alt on it",
      A.binding_from_event(_Event("k", 0)) == "K")
A.ALT_STATE = _was
check("off Windows, Alt is Mod1, which is how the tests drive it",
      A.ALT_STATE == (0x20000 if os.name == "nt" else 0x0008))


class _Thread:
    def __init__(self):
        self.joined = []
    def is_alive(self):
        return True
    def join(self, timeout=None):
        self.joined.append(timeout)


keys = A.Hotkeys()
fake = _Thread()
keys._thread, keys._thread_id = fake, 0
keys._ready.set()
keys.stop()
check("stopping WAITS for the old thread to let go of its keys, so the new "
      "one is not refused them after Save", fake.joined and fake.joined[0],
      fake.joined)
check("and forgets it", keys._thread is None and keys._thread_id == 0)
_stop = SRC.split("    def stop(self):")[1].split("\n    def ")[0]
check("the quit is posted before the wait", _stop.index("PostThreadMessageW")
      < _stop.index("thread.join"))
_run = SRC.split("    def _run(self):")[1].split("\n    def ")[0]
check("registration is retried rather than one refusal taken as final",
      "self._register(" in _run and "for attempt in range(3)" in SRC)
check("and start() waits for it, so Settings shows what really took",
      "self._ready.wait(1.0)" in SRC.split("    def start(self, bindings):")[1]
      .split("\n    def ")[0])

print("== keys other programs own are named when you pick them ==")
check("Alt+F1 is NVIDIA's screenshot", "NVIDIA" in A.key_clash("ALT+F1"))
check("Alt+F9 is NVIDIA's record", "NVIDIA" in A.key_clash("ALT+F9"))
check("Alt+Z and Alt+R are the overlays", A.key_clash("ALT+Z")
      and A.key_clash("ALT+R"))
check("Win keys are Windows and the Game Bar", "Windows" in A.key_clash("WIN+G"))
check("Shift+Tab is Steam's overlay", "Steam" in A.key_clash("SHIFT+TAB"))
check("a plain letter would fight the game's own controls",
      "game" in A.key_clash("K"))
check("the shipped keys clash with nothing",
      not any(A.key_clash(OV.WORK_KEYS[k]) for k in OV.WORK_KEYS),
      {k: A.key_clash(v) for k, v in OV.WORK_KEYS.items()})
check("and a plain F-key other than F10 and F12 is fine", A.key_clash("F7") == "")
_cap = SRC.split("    def _captured(self, event):")[1].split("\n    def ")[0]
check("Settings says so the moment the key is pressed, and still lets it "
      "be kept", "key_clash(chosen)" in _cap and "Save to keep it anyway" in _cap)

print("== the fast loop: keys, compass and scope ten times a second ==")


class _State:
    def __init__(self, lat, lon, heading=0.0, **kw):
        self.lat, self.lon, self.heading = lat, lon, heading
        self.radius_m = R
        self.has_position = True
        self.in_srv = True
        self.body = "Ega 1"
        self.__dict__.update(kw)
    def body_profile(self, body=None):
        return {"gravity": getattr(self, "g", ""), "planet_class": "",
                "atmosphere": "", "volcanism": "", "temperature_k": ""}


class _Watcher:
    def __init__(self, moved):
        self.moved, self.polls = moved, 0
    def poll_status(self):
        self.polls += 1
        return self.moved


class _Keys:
    def __init__(self, pressed):
        self.pressed = list(pressed)
    def drain(self):
        out, self.pressed = self.pressed, []
        return out


app = A.EDSMT.__new__(A.EDSMT)
app.settings = dict(A.DEFAULT_SETTINGS)
app._seen_trouble = set()
app.said = []
app.say = lambda text, colour=None: app.said.append(text)
app.after = lambda ms, fn: app.said.append(("after", ms))
app.flash_said = lambda: None
app.watcher = _Watcher(moved=True)
app.game = None
app.hotkeys = _Keys(["deposit", "border"])
ran = []
app.mark_deposit = lambda: ran.append("deposit")
app.set_survey_border = lambda: (_ for _ in ()).throw(ValueError("no centre"))
app.overlay_fast = lambda: ran.append("overlay")
app.fast_tick()
check("both keys pressed are run, in order, and a fault in one does not stop "
      "the other - or the redraw", ran == ["deposit", "overlay"], ran)
check("the fault says which key", any(str(s).startswith("Survey border problem")
                                      for s in app.said), app.said)
check("and it goes round again in a tenth of a second",
      ("after", A.FAST_TICK_MS) in app.said and A.FAST_TICK_MS <= 100)
app.watcher = _Watcher(moved=False)
ran.clear()
app.fast_tick()
check("standing still with nothing pressed, nothing is redrawn", ran == [], ran)

_ov = OV.Overlay(app=None, tk_module=None, settings={})


class _Panel:
    def __init__(self):
        self.drawn = 0
        self.window = self.canvas = self
    def alive(self):
        return True
    def size(self):
        return 300, 200
    def delete(self, *a):
        self.drawn += 1
    def __getattr__(self, name):
        return lambda *a, **k: None


_ov.panels = {key: _Panel() for key in OV.PANEL_ORDER}
_ov.follow_game = lambda: True
_ov.draw([], 45.0, only=[OV.STRIP, OV.RADAR])
check("the fast redraw touches the compass and the scope and nothing else",
      {k for k, p in _ov.panels.items() if p.drawn} == {OV.STRIP, OV.RADAR},
      {k: p.drawn for k, p in _ov.panels.items()})

print("== Status.json read on its own, and what it says about coming down ==")
GAME = os.path.join(TMP, "game"); os.makedirs(GAME)


def status(**kw):
    data = {"timestamp": "2026-09-25T20:00:00Z", "event": "Status",
            "Flags": kw.pop("Flags", 0), "Flags2": kw.pop("Flags2", 0)}
    data.update(kw)
    with open(os.path.join(GAME, "Status.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh)


watcher = JN.JournalWatcher(GAME)
status(Latitude=12.5, Longitude=-45.5, Heading=10, BodyName="Ega 1",
       PlanetRadius=R, Flags=1 << 21 | 1 << 26)
check("a first reading is a change", watcher.poll_status() is True)
check("the same reading again is not", watcher.poll_status() is False)
status(Latitude=12.5, Longitude=-45.5, Heading=40, BodyName="Ega 1",
       PlanetRadius=R, Flags=1 << 21 | 1 << 26)
check("turning is", watcher.poll_status() is True and watcher.heading == 40)
status(Latitude=12.5, Longitude=-45.5, Heading=40, BodyName="Ega 1",
       PlanetRadius=R, Altitude=212, Flags=1 << 24 | 1 << 21, Flags2=1 << 12)
watcher.poll_status()
check("gliding is read off Flags2, and the height off Altitude",
      watcher.gliding and watcher.altitude == 212 and watcher.in_ship,
      (watcher.gliding, watcher.altitude, watcher.in_ship))
status(Latitude=12.5, Longitude=-45.5, Heading=40, BodyName="Ega 1",
       PlanetRadius=R, Altitude=90000, Flags=1 << 24 | 1 << 21 | 1 << 29)
watcher.poll_status()
check("a height over the average radius is not a height over the ground",
      watcher.altitude is None, watcher.altitude)

print("== the guide: jump and honk, where to land, glide, under 30 m ==")
JOURNAL = os.path.join(GAME, "Journal.2026-09-25T200000.01.log")
with open(JOURNAL, "w", encoding="utf-8") as fh:
    for event in (
            {"timestamp": "2026-09-25T20:00:00Z", "event": "Fileheader",
             "gameversion": "4.4.1.1", "part": 1},
            {"timestamp": "2026-09-25T20:00:01Z", "event": "FSDJump",
             "StarSystem": "HR 7280", "SystemAddress": 1, "StarPos": [0, 0, 0]},
            {"timestamp": "2026-09-25T20:00:30Z", "event": "FSSDiscoveryScan",
             "Progress": 0.5, "BodyCount": 12, "NonBodyCount": 3,
             "SystemName": "HR 7280", "SystemAddress": 1},
            {"timestamp": "2026-09-25T20:05:00Z", "event": "ApproachBody",
             "StarSystem": "HR 7280", "SystemAddress": 1,
             "Body": "HR 7280 A 3", "BodyID": 5}):
        fh.write(json.dumps(event) + "\n")
watcher.poll()
check("the honk is remembered for the system it was fired in",
      "hr 7280" in watcher.honked, watcher.honked)
check("and the body headed for", watcher.approached == ("HR 7280", "HR 7280 A 3"),
      watcher.approached)
gapp = A.EDSMT.__new__(A.EDSMT)
gapp.settings = dict(A.DEFAULT_SETTINGS)
gapp.game = watcher
gapp.here = lambda: ("HR 7280", "HR 7280 A 3")
gapp.signal = lambda: "1"
gapp.store = SV.Survey(os.path.join(TMP, "gstore"))
facts = gapp.guide_facts()
check("the app sees the honk and the approach",
      facts["honked"] and facts["chosen"], facts)
check("so the guide is past them, on mapping the body",
      A.guide_step(facts)["title"] == "MAP THE BODY", A.guide_step(facts))
watcher.gliding, watcher.altitude, watcher.landed, watcher.in_srv = True, 900.0, False, False
check("gliding, it is not landed - even with a position",
      gapp.guide_facts()["landed"] is False)
watcher.gliding, watcher.altitude = False, 29.0
check("out of glide and under 30 m, it is", gapp.guide_facts()["landed"] is True)

print("== LOG SIGNAL picks the number, and no commodities are asked for ==")


def signal_app(box="1"):
    sapp = A.EDSMT.__new__(A.EDSMT)
    sapp.settings = dict(A.DEFAULT_SETTINGS)
    sapp.store = SV.Survey(os.path.join(TMP, "sig-%d" % time.time_ns()))
    sapp.here = lambda: ("Ega", "Ega 1")
    sapp.box = [box]
    sapp.signal = lambda: sapp.box[0]
    sapp.choose_signal = lambda n: sapp.box.__setitem__(0, n)
    sapp.game = _State(*HOME, target_signal="", detected_type=None, cmdr="J")
    sapp.game.body_temperature = lambda: None
    sapp.said, sapp.flashes = [], []
    sapp.say = lambda text, colour=None: sapp.said.append(text)
    sapp.flash = lambda *a, **k: sapp.flashes.append(a)
    sapp.refresh_locations = sapp.refresh_deposits = sapp.redraw = lambda: None
    sapp.centre_on_signal = lambda state: True
    sapp.key = lambda action, fallback="": {"border": "Alt+2",
                                            "location": "Alt+1"}.get(action, fallback)
    return sapp


s1 = signal_app("3")
s1.log_location()
check("the number in the box is used when it is not taken",
      s1.store.location("Ega", "Ega 1", "3") is not None, s1.store.locations)
check("and the message says hold the scanner to the border and while mapping, "
      "and that no commodities are needed",
      "hold the mineral scanner" in s1.said[-1]
      and "keep it held while you map the area" in s1.said[-1]
      and "No commodities needed" in s1.said[-1]
      and "Commodity box" not in s1.said[-1], s1.said[-1])
before = dict(s1.store.location("Ega", "Ega 1", "3"))
s1.game = _State(*dest(HOME[0], HOME[1], 90, 800), target_signal="",
                 detected_type=None, cmdr="J")
s1.game.body_temperature = lambda: None
s1.log_location()
check("pressed again inside the same signal, its centre stays put",
      s1.store.location("Ega", "Ega 1", "3")["lat"] == before["lat"]
      and "already logged" in s1.said[-1], s1.said[-1])
s1.game = _State(*dest(HOME[0], HOME[1], 90, 30000), target_signal="",
                 detected_type=None, cmdr="J")
s1.game.body_temperature = lambda: None
s1.log_location()
check("30 km away with the box still on 3, a NEW signal gets the next free "
      "number instead of moving 3", s1.box[0] == "1"
      and s1.store.location("Ega", "Ega 1", "1") is not None
      and s1.store.location("Ega", "Ega 1", "3")["lat"] == before["lat"],
      (s1.box, s1.store.locations))
s1.game = _State(*dest(HOME[0], HOME[1], 90, 30000), target_signal="7",
                 detected_type=None, cmdr="J")
s1.game.body_temperature = lambda: None
s1.log_location()
check("and the one the game has targeted wins over all of it",
      s1.box[0] == "7" and "targeted" in s1.said[-1], (s1.box, s1.said[-1]))

print("== the same spot, another commodity: rename, or add a second ==")


def mark_app():
    mapp = A.EDSMT.__new__(A.EDSMT)
    mapp.settings = dict(A.DEFAULT_SETTINGS)
    mapp.store = SV.Survey(os.path.join(TMP, "mark-%d" % time.time_ns()))
    mapp.here = lambda: ("Ega", "Ega 1")
    mapp.signal = lambda: "1"
    mapp.game = _State(*HOME, detected_type=None, detected_density=None,
                       cmdr="J")
    mapp.game.body_temperature = lambda: None
    mapp.game.body_profile = lambda body=None: {
        "planet_class": "", "gravity": "", "atmosphere": "", "volcanism": "",
        "temperature_k": ""}
    mapp.said = []
    mapp.say = lambda text, colour=None: mapp.said.append(text)
    mapp.flash = lambda *a, **k: None
    mapp.remember_body = lambda *a: None

    class _Box:
        def __init__(self, value=""):
            self.value = value
        def get(self):
            return self.value
        def set(self, value):
            self.value = value
    mapp.fields = {k: _Box() for k in ("commodity", "rigs", "amount", "density")}
    # 1.10031: a deposit is only marked with all four boxes filled in.
    mapp.fields["rigs"].set("3")
    mapp.fields["amount"].set("High")
    mapp.fields["density"].set("Medium")
    _clear = mapp.clear_deposit_boxes
    def _refill():
        _clear()
        mapp.fields["rigs"].set("3")
        mapp.fields["amount"].set("High")
        mapp.fields["density"].set("Medium")
    mapp.clear_deposit_boxes = _refill
    mapp.refresh_locations = mapp.refresh_deposits = mapp.redraw = lambda: None
    mapp.refresh_commodities = lambda *a: None
    mapp.share = lambda row: None
    mapp.on_pick = lambda row: None
    mapp.key = lambda action, fallback="": {"update": "AltGr+3",
                                            "deposit": "Alt+3"}.get(action, fallback)
    return mapp


m = mark_app()
m.fields["commodity"].set("Monazite")
m.mark_deposit()
m.fields["commodity"].set("Alexandrite")
m.mark_deposit()
check("MARK with a new commodity on the same spot asks, it does not add",
      len(m.store.deposits) == 1 and "rename it Alexandrite" in m.said[-1],
      m.said[-1])
m.update_deposit_here()
check("UPDATE after it renames the one there - no second find at 0 m",
      len(m.store.deposits) == 1
      and m.store.deposits[0]["commodity"] == "Alexandrite", m.store.deposits)
check("saying what it was", "was Monazite, now Alexandrite" in m.said[-1],
      m.said[-1])
check("and the history says so too",
      "was Monazite, now Alexandrite" in m.store.deposits[0]["notes"],
      m.store.deposits[0]["notes"])
m2 = mark_app()
m2.fields["commodity"].set("Monazite")
m2.mark_deposit()
m2.fields["commodity"].set("Alexandrite")
m2.mark_deposit()
m2.mark_deposit()
check("MARK twice adds the second commodity as its own deposit",
      sorted(d["commodity"] for d in m2.store.deposits)
      == ["Alexandrite", "Monazite"], m2.store.deposits)
m3 = mark_app()
m3.fields["commodity"].set("Monazite")
m3.mark_deposit()
m3.game = _State(*dest(HOME[0], HOME[1], 0, 60), detected_type=None,
                 detected_density=None, cmdr="J")
m3.game.body_temperature = lambda: None
m3.game.body_profile = m.game.body_profile
m3.fields["commodity"].set("Alexandrite")
m3.mark_deposit()
check("60 m away it is a different rock: marked straight away",
      len(m3.store.deposits) == 2, m3.store.deposits)

print("== finds filed under a mistyped signal still show at the signal ==")
st = mark_app()
st.store.set_location("Ega", "Ega 1", "1", lat=HOME[0], lon=HOME[1], radius_m=R)
st.store.add_deposit(system="Ega", body="Ega 1", location="11",
                     commodity="Painite", lat="%.6f" % dest(*HOME, 45, 300)[0],
                     lon="%.6f" % dest(*HOME, 45, 300)[1])
st.store.add_deposit(system="Ega", body="Ega 1", location="4",
                     commodity="Gold", lat="%.6f" % dest(*HOME, 45, 40000)[0],
                     lon="%.6f" % dest(*HOME, 45, 40000)[1])
strays = st.stray_deposits("Ega", "Ega 1", "1")
check("the Painite 300 m from signal 1, filed as 11, is listed under 1",
      [d["commodity"] for d in strays] == ["Painite"], strays)
check("the Gold 40 km away is not", all(d["commodity"] != "Gold" for d in strays))
st.deposit_edited = lambda i, ch: st.store.update_deposit(i, **ch)
st.refile_deposit(strays[0], "1")
check("one button puts its number right, and says where it came from",
      st.store.at("Ega", "Ega 1", "1")[0]["commodity"] == "Painite"
      and "Refiled from signal 11" in st.store.at("Ega", "Ega 1", "1")[0]["notes"],
      st.store.at("Ega", "Ega 1", "1"))

print("== high gravity: a big warning, once, and a red bar while you are there ==")
A.set_high_g({"high_g_warn": 2.0})
check("2.4 g is high", A.is_high_g(2.4) and not A.is_high_g(1.2))
A.set_high_g({"high_g_warn": 0})
check("0 turns it off", not A.is_high_g(9.0))
A.set_high_g({"high_g_warn": 2.0})


class _Alarm:
    def __init__(self):
        self.up = []
    def alarm(self, title, detail=""):
        self.up.append(title)
        return True
    def end_alarm(self):
        pass


gg = A.EDSMT.__new__(A.EDSMT)
gg.settings = dict(A.DEFAULT_SETTINGS)
gg.said = []
gg.say = lambda text, colour=None: gg.said.append(text)
gg.after = lambda ms, fn: None
gg.overlay = _Alarm()
heavy = _State(*HOME, g=2.41, gliding=True)
check("arriving at a 2.41 g body puts the triangle up",
      gg.follow_gravity(heavy) and gg.overlay.up == ["HIGH GRAVITY 2.41 g"],
      gg.overlay.up)
check("once - not every tick", not gg.follow_gravity(heavy)
      and len(gg.overlay.up) == 1)
gg.game = heavy
check("and the boxes carry a red bar for as long as you are there",
      gg.overlay_hazard() == {"text": "HIGH GRAVITY 2.41 g", "gravity": 2.41},
      gg.overlay_hazard())
check("a light body carries none",
      gg.follow_gravity(_State(*HOME, g=0.3, body="Ega 2")) is False)
row = {"tier": 0, "short": "A 3", "body": "X A 3", "value": 0, "gravity_g": 2.6,
       "ground": "Rocky body", "note": ""}
cells = A.LandWindow._land_row(row)
check("Where to land flags it in red",
      "HIGH G" in cells[-1][0] and cells[-1][1] == A.RED, cells[-1])

print("== the rig about to be lost, in the middle of the screen ==")
check("the warning triangle is its own click-through window",
      "def alarm(self, title" in OVSRC and "def end_alarm(self)" in OVSRC
      and "self._hud_window()" in OVSRC.split("def alarm(self")[1])
check("red whatever the theme", "ALARM_RED" in OVSRC.split("def alarm(self")[1]
      and "ALARM_RED" not in str(OV.PALETTE_KEYS))

print("== the overlay layout stays where people put it ==")
_hide = OVSRC.split("    def hide(self):")[1].split("\n    def ")[0]
check("closing the overlay no longer measures the boxes and saves that",
      "remember" not in _hide.split('"""')[-1], _hide[-400:])
_close = OVSRC.split("class Panel:")[1].split("    def close(self):")[1] \
    .split("\n    def ")[0]
check("nor does closing one box", "self.remember()" not in _close)


class _Hidden:
    def winfo_viewable(self):
        return 0
    def winfo_width(self):
        return 1
    def winfo_height(self):
        return 1
    def winfo_x(self):
        return 0
    def winfo_y(self):
        return 0


_lay = OV.Overlay(app=None, tk_module=None,
                  settings={"overlay_layout": {OV.STRIP: {"x": 0.3, "y": 0.1,
                                                          "w": 0.35, "h": 0.06}}})
_box = OV.Panel(_lay, OV.STRIP)
_box.window = _Hidden()
_box.remember()
check("and a box Windows has hidden is never measured",
      _lay.settings["overlay_layout"][OV.STRIP]["x"] == 0.3,
      _lay.settings["overlay_layout"])
A.SETTINGS_NOTICE[:] = []
up = A.upgrade_layout(dict(A.DEFAULT_SETTINGS, overlay_layout={
    OV.STRIP: {"x": 0.0, "y": 0.0, "w": 0.0001, "h": 0.0001}}),
    {"overlay_layout": {OV.STRIP: {"x": 0.0}}})
check("a layout from 1.10029 is put on the new default, once",
      up["overlay_layout"] == OV.DEFAULT_LAYOUT
      and up["overlay_layout_level"] == A.LAYOUT_LEVEL, up["overlay_layout"])
check("and the commander is told why", A.SETTINGS_NOTICE
      and "new default layout" in A.SETTINGS_NOTICE[-1])
kept = A.upgrade_layout(dict(A.DEFAULT_SETTINGS, overlay_layout={"x": 1}),
                        {"overlay_layout_level": A.LAYOUT_LEVEL,
                         "overlay_layout": {"x": 1}})
check("after that, a layout arranged by hand is left alone",
      kept["overlay_layout"] == {"x": 1})
D = OV.DEFAULT_LAYOUT
check("the default is the author's: compass across the top",
      0.30 < D[OV.STRIP]["x"] < 0.33 and D[OV.STRIP]["y"] < 0.12
      and D[OV.STRIP]["w"] > 0.3)
check("scope and guide down the left edge, one above the other",
      D[OV.RADAR]["x"] < 0.01 and D[OV.GUIDE]["x"] < 0.01
      and D[OV.RADAR]["y"] + D[OV.RADAR]["h"] <= D[OV.GUIDE]["y"] + 0.001)
check("targets on the right, status along the bottom",
      D[OV.TARGETS]["x"] > 0.8 and D[OV.STATUS]["y"] > 0.9)
check("and the five boxes of it are on for a new commander",
      all(A.DEFAULT_SETTINGS["overlay_show_%s" % k]
          for k in ("strip", "radar", "targets", "status"))
      and A.DEFAULT_SETTINGS["overlay_show_guide"])

print("== the scope while setting the border ==")
_sm = OVSRC.split("    def _survey_marks(self")[1].split("\n    def ")[0]
check("no swept-ground plate before there is a border to sweep inside",
      'if survey.get("border_m") else []' in _sm)
check("and when there is one, it is a see-through mesh",
      _sm.count("stipple=mesh") == 2
      and OV.swept_style("faint", "#ff7a18", "#ffb000")[1] == "gray25"
      and OV.swept_style("clear", "#ff7a18", "#ffb000")[1] == "gray50",
      _sm.count("stipple=mesh"))

print("== the top bar: where things are on the left, the overlay on the right ==")
_top = SRC.split("    def _telemetry(self):")[1].split("\n    def ")[0]
_nav, _side = _top.split("nav = ctk.CTkFrame")[1], _top.split("side = ctk.CTkFrame")[1]
check("Find, My sites, Where to land and Earnings are in the left group",
      all('ctk.CTkButton(nav, text="%s"' % t in _top
          for t in ("Find", "My sites", "Where to land", "Earnings")))
check("Overlay, Unlock and Settings in the right one",
      "ctk.CTkButton(side, text=\"Overlay\"" in _top
      and "ctk.CTkButton(side, text=\"Unlock\"" in _top
      and "ctk.CTkButton(side, text=\"Settings\"" in _top)

print("== the commodity list shuts when one is clicked ==")
_click = SRC.split("    def _list_clicked(self, event=None):")[1].split("\n    def ")[0]
check("a click picks it and keeps the list shut through the focus coming "
      "back", "self._hushed = True" in _click
      and _click.index("self.pick(name)") < _click.index("focus_set"))

print("== the ship's hold after every transfer ==")
sh = A.EDSMT.__new__(A.EDSMT)
sh.watcher = type("W", (), {"holds": {"Ship": {"Rhodplumsite": 161, "Ruby": 11}},
                            "cargo_capacity": 256, "in_srv": True})()
sh.earnings = type("E", (), {"rhino": {"kind": "rhino"}})()
sh.flashed = []
sh.flash = lambda title, detail="", colour=None: sh.flashed.append((title, detail))
sh.say = lambda *a, **k: None
sh.earnings_note("to ship: Rhodplumsite:61, Ruby:11")
check("a transfer flashes what is in the ship now, and the room left",
      sh.flashed and sh.flashed[-1][0] == "SHIP 172/256 t  84 t room"
      and "Rhodplumsite" in sh.flashed[-1][1], sh.flashed)
check("and STATUS carries it for the whole session",
      sh.overlay_cargo() == {"ship_t": 172, "capacity": 256, "rhino_t": 0},
      sh.overlay_cargo())

print("== the tester who spent two and a half hours on it ==")
check("CMDR Rumphrend is credited", "CMDR Rumphrend" in A.BETA_TESTERS)

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
