"""What 1.10033 adds, each piece held down so it stays built.

Driven without a display, like the other suites. The multi-Rhino journal is
the shape of a real evening on a Panther Clipper (two Rhinos, a Nomad),
rebuilt with made-up names: no commander, no system of anybody's.

    python tests/test_110033.py
"""
import os, sys, json, math, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "stubs"))
import _ctkstub  # noqa
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="edsmt-110033-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
import edsmt as A, survey as SV, overlay as OV, journal as JN  # noqa

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)


SRC = open(A.__file__, encoding="utf-8").read()
R = 1_800_000.0
HOME = (30.24, -172.67)


def dest(lat, lon, bearing, metres):
    p1, l1, th, d = math.radians(lat), math.radians(lon), math.radians(bearing), metres / R
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(th))
    l2 = l1 + math.atan2(math.sin(th) * math.sin(d) * math.cos(p1),
                         math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), math.degrees(l2)


def journal(folder, events, name="Journal.2026-10-01T003000.01.log"):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")
    reader = JN.JournalWatcher(folder)
    reader.poll()
    return reader


def at(minute, second=0):
    return "2026-10-01T%02d:%02d:%02dZ" % (minute // 60, minute % 60, second)


SYS, BODY = "Test Sector AB-C d1", "Test Sector AB-C d1 2 e"
PLACE = {"StarSystem": SYS, "SystemAddress": 12345, "Body": BODY, "BodyID": 30,
         "OnStation": False, "OnPlanet": True, "Taxi": False, "Multicrew": False}


def refined(minute, what="$silver_name;"):
    return {"timestamp": at(minute), "event": "MiningRefined", "Type": what}


EVENING = [
    {"timestamp": at(30), "event": "Fileheader", "gameversion": "4.4.1.1", "part": 1},
    {"timestamp": at(30), "event": "LoadGame", "Commander": "Tester", "FID": "F1"},
    {"timestamp": at(31), "event": "Location", "StarSystem": SYS, "Body": BODY,
     "Docked": False},
    {"timestamp": at(35), "event": "SupercruiseExit", "StarSystem": SYS,
     "Body": BODY, "BodyType": "Planet", "BodyID": 30},
    {"timestamp": at(37), "event": "LaunchSRV", "SRVType": "mev_rhino",
     "SRVType_Localised": "SRV Rhino", "Loadout": "galactic", "ID": 98,
     "PlayerControlled": True},
    refined(40), refined(41),
    dict(PLACE, timestamp=at(60), event="Disembark", SRV=True, ID=98),
    dict(PLACE, timestamp=at(62), event="Embark", SRV=False, ID=94),
    dict(PLACE, timestamp=at(62, 30), event="Liftoff", PlayerControlled=True,
         Latitude=30.23, Longitude=-172.67,
         NearestDestination="$SAA_Unknown_Signal:#type=$PlanetaryMiningLocation_Name;:#index=4;"),
    {"timestamp": at(63), "event": "LaunchSRV", "SRVType": "mev_rhino",
     "SRVType_Localised": "SRV Rhino", "Loadout": "galactic", "ID": 99,
     "PlayerControlled": True},
    refined(78), refined(79), refined(80, "$gold_name;"),
    dict(PLACE, timestamp=at(142), event="Disembark", SRV=True, ID=99),
    dict(PLACE, timestamp=at(145), event="Embark", SRV=False, ID=94),
    {"timestamp": at(146), "event": "LaunchVessel", "VesselType": "lander01",
     "VesselType_Localised": "Nomad", "Loadout": "galactic", "ID": 100,
     "PlayerControlled": True},
]
LATER = [
    dict(PLACE, timestamp=at(147), event="Disembark", SRV=True, ID=100),
    dict(PLACE, timestamp=at(148), event="Embark", SRV=True, ID=98),
    refined(149), refined(150, "$gold_name;"),
    {"timestamp": at(154), "event": "DockSRV", "SRVType": "mev_rhino", "ID": 98},
    dict(PLACE, timestamp=at(158), event="Embark", SRV=True, ID=99),
    refined(160),
    {"timestamp": at(170), "event": "DockSRV", "SRVType": "mev_rhino", "ID": 99},
]


# ---------------------------------------------------------------------------
print("== the journal follows the commander from vehicle to vehicle ==")
FOLDER = os.path.join(TMP, "evening")
jw = journal(FOLDER, EVENING)
check("the ship, both Rhinos and the Nomad each keep their own ID",
      jw.vehicle_kinds.get(94) == "ship" and jw.vehicle_kinds.get(98) == "rhino"
      and jw.vehicle_kinds.get(99) == "rhino"
      and jw.vehicle_kinds.get(100) == "nomad", jw.vehicle_kinds)
check("in the Nomad, the vehicle is the Nomad", jw.vehicle_id == 100, jw.vehicle_id)
jw.in_srv = True        # Status.json: the Nomad sets the same In SRV flag
check("and the Nomad is not a Rhino, whatever the flag says",
      jw.in_rhino is False)
check("the rig keys then act on the last Rhino driven",
      jw.current_rhino() == 99, jw.current_rhino())
check("the touchdown's nearest mining location is read: 4",
      jw.touchdown_signal == "4", jw.touchdown_signal)
check("dropping out at a planet counts as arriving there (no ApproachBody)",
      jw.approached == (SYS, BODY), jw.approached)
notes = jw.drain_runs()
with open(os.path.join(FOLDER, "Journal.2026-10-01T003000.01.log"), "a",
          encoding="utf-8") as fh:
    for ev in LATER:
        fh.write(json.dumps(ev) + "\n")
jw.poll()
check("climbing into the parked Rhino makes it the one being driven",
      jw.last_rhino == 99 and jw.vehicle_id is None, (jw.last_rhino, jw.vehicle_id))
notes += jw.drain_runs()
kinds = [n["event"] for n in notes]
check("Embark and Disembark from an SRV go to the books",
      "SRVEmbark" in kinds and "SRVDisembark" in kinds, kinds)
check("and every tonne says which Rhino dug it up",
      [n.get("srv_id") for n in notes if n["event"] == "Refined"]
      == [98, 98, 99, 99, 99, 98, 98, 99],
      [n.get("srv_id") for n in notes if n["event"] == "Refined"])

print("== the books: one session, split per Rhino ==")
books = SV.Earnings(os.path.join(TMP, "books"))
lines = [books.observe(n) for n in notes]
rows = books.sessions
check("one session for the evening", len(rows) == 1, len(rows))
row = rows[0]
check("all eight tonnes in it", sum(SV.unpack_counts(row["mined"]).values()) == 8,
      row["mined"])
split = SV.rhino_split(row)
check("split per Rhino, lettered in the order they were driven",
      [(p["id"], p["label"], p["tonnes"]) for p in split]
      == [("98", "A", 4), ("99", "B", 4)], split)
check("the first Rhino coming aboard does not end it - the second is still out",
      any(line and "still out" in line for line in lines), [l for l in lines if l])
check("the last one aboard does", str(row.get("closed") or "") != ""
      and row.get("ended_by") == "docked", (row.get("closed"), row.get("ended_by")))
check("an old row with no split reads as none", SV.rhino_split({}) == []
      and SV.rhino_split({"rhinos": "not json"}) == [])
check("the column is new and at the end", SV.SESSION_FIELDS[-1] == "rhinos")

print("== a crewmate's Rhino still does not end yours ==")
crew = SV.Earnings(os.path.join(TMP, "crew"))
for n in ({"event": "SRVLaunch", "when": at(10), "rhino": True, "player": True,
           "srv_id": 7, "system": SYS, "body": BODY},
          {"event": "Refined", "when": at(11), "commodity": "Silver", "srv_id": 7,
           "system": SYS, "body": BODY, "in_srv": True},
          {"event": "SRVLaunch", "when": at(12), "rhino": True, "player": False,
           "srv_id": 8, "system": SYS, "body": BODY},
          {"event": "SRVDock", "when": at(13), "srv_id": 8}):
    crew.observe(n)
check("the crewmate's dock leaves the session open",
      not str(crew.sessions[0].get("closed") or ""), crew.sessions[0])


# ---------------------------------------------------------------------------
print("== rigs: six per Rhino, twelve from two ==")


class State:
    def __init__(self, lat, lon, rhino=98, in_rhino=True, heading=0.0):
        self.lat, self.lon, self.heading = lat, lon, heading
        self.radius_m = R
        self.has_position = True
        self.rhino = rhino
        self.in_rhino = in_rhino
        self.in_srv = in_rhino
        self.game_started = None

    def current_rhino(self):
        return self.rhino


def probe(limit=1000):
    app = A.EDSMT.__new__(A.EDSMT)
    app.said, app.flashed, app.events = [], [], []
    app.say = lambda t, c=None: app.said.append((t, c))
    app.flash = lambda *a, **k: app.flashed.append(a)
    app.settings = dict(A.DEFAULT_SETTINGS, rig_warn_m=limit, rig_warn_sound=False)
    app.where = (SYS, BODY)
    app.here = lambda: app.where
    app.redraw = lambda: None
    app.sound_alarm = lambda: None
    app.rig_event = lambda what, n=None: app.events.append((what, n))
    app.rigs_at, app._rigs_warned = None, False
    app.game = State(*HOME)
    return app


app = probe()
for n in range(1, 7):
    app.game = State(*dest(HOME[0], HOME[1], 0, 60 * n), rhino=98)
    app.drop_rigs(n)
check("Rhino A: six rigs down", len(app.rigs_at["rigs"]) == 6)
check("labelled plain 1-6 while only one Rhino has rigs down",
      [app.rig_label(r) for r in app.rigs_at["rigs"]] == ["1", "2", "3", "4", "5", "6"])
for n in range(1, 7):
    app.game = State(*dest(HOME[0], HOME[1], 180, 60 * n), rhino=99)
    app.drop_rigs(n)
check("Rhino B: six more - twelve down, none of A's moved",
      len(app.rigs_at["rigs"]) == 12, len(app.rigs_at["rigs"]))
labels = [app.rig_label(r) for r in app.rigs_at["rigs"]]
check("now lettered A1-A6 and B1-B6",
      labels == ["A%d" % n for n in range(1, 7)] + ["B%d" % n for n in range(1, 7)],
      labels)
check("the count is per Rhino: 6 of 6", "(6 of 6)" in app.said[-1][0], app.said[-1])
app.game = State(*dest(HOME[0], HOME[1], 90, 900), rhino=99)
app.drop_rigs()
check("a seventh from Rhino B is refused", "All 6 rigs of this Rhino" in app.said[-1][0],
      app.said[-1])
app.rig_up(2)
check("rig 2 up from Rhino B takes B2, not A2",
      [app.rig_label(r) for r in app.rigs_at["rigs"]].count("A2") == 1
      and "B2" not in [app.rig_label(r) for r in app.rigs_at["rigs"]],
      [app.rig_label(r) for r in app.rigs_at["rigs"]])

print("== only the Rhino being driven is warned about ==")
app.game = State(*dest(HOME[0], HOME[1], 0, 4000), rhino=99)
view = app.watch_rigs(app.game)
check("driving B 4 km north: B's rigs are far, A's are not watched",
      view and view["far"] and view["label"].startswith("B"), view and view.get("label"))
watched = {m["label"]: m["watched"] for m in view["rigs"]}
check("A's rigs are drawn but not watched", watched.get("A1") is False
      and watched.get("B1") is True, watched)
app.game = State(*dest(HOME[0], HOME[1], 0, 5600), rhino=99)
app.watch_rigs(app.game)
left = [app.rig_label(r) for r in (app.rigs_at or {}).get("rigs", [])]
check("past 5 km B's rigs are lost - A's, parked by their own Rhino, are not",
      all(l.startswith("A") for l in left) and len(left) == 6, left)
app.game = State(*dest(HOME[0], HOME[1], 0, 5600), rhino=100, in_rhino=False)
app.game.in_srv = True
before = len(app.rigs_at["rigs"])
app.watch_rigs(app.game)
check("in the Nomad nothing is ever marked lost", len(app.rigs_at["rigs"]) == before)

print("== rigs up with two Rhinos' rigs down ==")
app = probe()
for rhino, bearing in ((98, 0), (99, 180)):
    for n in (1, 2):
        app.game = State(*dest(HOME[0], HOME[1], bearing, 60 * n), rhino=rhino)
        app.drop_rigs(n)
app.game = State(*HOME, rhino=98)
app.rigs_up()
check("the first press takes up the Rhino you are in",
      [app.rig_label(r) for r in app.rigs_at["rigs"]] == ["B1", "B2"] or
      [r.get("srv") for r in app.rigs_at["rigs"]] == ["99", "99"],
      app.rigs_at and app.rigs_at["rigs"])
check("and says a second press clears the other Rhino's",
      "again within" in app.said[-1][0], app.said[-1])
app.rigs_up()
check("the second press inside the time clears the rest", app.rigs_at is None)
check("and only then is it every rig up for the books",
      ("RigsUp", None) in app.events, app.events)

print("== rigs from before a relog ==")
app = probe()
app.game = State(*HOME, rhino=98)
app.drop_rigs(1)
app.rigs_at["rigs"][0]["at"] = time.time() - 3600
app.game.game_started = time.time() - 60
spoke = app.rigs_after_relog(app.game, app._rigs_here())
check("rigs marked before the game was logged into again: it asks",
      spoke and "before you logged back in" in app.said[-1][0], app.said[-1])
check("once per game session, not every poll",
      app.rigs_after_relog(app.game, app._rigs_here()) is False)
check("and it clears nothing by itself", len(app.rigs_at["rigs"]) == 1)
fresh = probe()
fresh.game = State(*HOME, rhino=98)
fresh.game.game_started = time.time() - 60
fresh.drop_rigs(1)
check("rigs marked since the login are not asked about",
      fresh.rigs_after_relog(fresh.game, fresh._rigs_here()) is False)

print("== the overlay draws the letters and warns only for the watched ==")
marks = OV.rig_tape_marks({"rigs": [
    {"n": 1, "label": "A1", "watched": False, "bearing": 10, "range_m": 3000},
    {"n": 1, "label": "B1", "watched": True, "bearing": 20, "range_m": 3000}],
    "limit_m": 1000}, 0.0, 600, 120)
check("tape marks carry the label",
      sorted(m["label"] for m in marks) == ["A1", "B1"], marks)
check("and only the watched one is red",
      [m["label"] for m in marks if m["far"]] == ["B1"], marks)

print("== the guide: arriving at a body without orbital cruise ==")
G = os.path.join(TMP, "guide")
star = journal(G, [{"timestamp": at(1), "event": "SupercruiseExit",
                    "StarSystem": SYS, "Body": SYS + " C", "BodyType": "Star"}],
               name="Journal.2026-10-01T000100.01.log")
check("dropping out at a star is not arriving at a body",
      star.approached == ("", ""), star.approached)
G2 = os.path.join(TMP, "guide2")
ring = journal(G2, [{"timestamp": at(1), "event": "SupercruiseExit",
                     "StarSystem": SYS, "Body": BODY + " A Ring",
                     "BodyType": "PlanetaryRing"}],
               name="Journal.2026-10-01T000100.01.log")
check("nor is a ring", ring.approached == ("", ""), ring.approached)

print("== the touchdown hint sets the Signal box on a fresh body ==")


class Store:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def locations_on(self, system, body):
        return self.rows


hint = A.EDSMT.__new__(A.EDSMT)
hint.said = []
hint.say = lambda t, c=None: hint.said.append((t, c))
hint.here = lambda: (SYS, BODY)
hint.store = Store()
hint.picked = []
hint.choose_signal = lambda n: hint.picked.append(n)
hint.signal = lambda: "1"
st = State(*HOME)
st.touchdown_signal, st.target_signal = "4", ""
hint.follow_touchdown(st)
check("nothing logged here yet: the box goes to 4", hint.picked == ["4"], hint.picked)
hint.follow_touchdown(st)
check("once per touchdown", hint.picked == ["4"], hint.picked)
hint2 = A.EDSMT.__new__(A.EDSMT)
hint2.said, hint2.picked = [], []
hint2.say = lambda t, c=None: hint2.said.append((t, c))
hint2.here = lambda: (SYS, BODY)
hint2.store = Store([{"location": "2"}])
hint2.choose_signal = lambda n: hint2.picked.append(n)
hint2.signal = lambda: "2"
hint2.follow_touchdown(st)
check("signals already logged: only said, the box left alone",
      hint2.picked == [] and "location 4" in hint2.said[-1][0], hint2.said)
st.target_signal = "7"
hint3 = A.EDSMT.__new__(A.EDSMT)
hint3.said, hint3.picked = [], []
hint3.say = lambda t, c=None: hint3.said.append((t, c))
hint3.here = lambda: (SYS, BODY)
hint3.store = Store()
hint3.choose_signal = lambda n: hint3.picked.append(n)
hint3.signal = lambda: "1"
hint3.follow_touchdown(st)
check("a signal targeted in the game wins over the hint", hint3.picked == [])

# ---------------------------------------------------------------------------
print("== #143: a backup before every update ==")
BK = os.path.join(TMP, "Documents", "EDSMT backups")
os.makedirs(os.path.join(TMP, "bk-data"), exist_ok=True)
store = SV.Survey(os.path.join(TMP, "bk-data"))
with open(os.path.join(store.folder, "deposits.csv"), "w") as fh:
    fh.write("id,commodity\n1,Gold\n")
with open(os.path.join(store.folder, "settings.json"), "w") as fh:
    fh.write("{}")
bk = A.EDSMT.__new__(A.EDSMT)
bk.store = store
bk.said = []
bk.say = lambda text, colour=None: bk.said.append(text)
check("the backup is written before the update and named for it",
      bk.backup_before_update("1.10099", folder=BK, now=1000.0)
      and any(n.startswith("EDSMT-before-update-1.10099-") and n.endswith(".zip")
              for n in os.listdir(BK)), os.listdir(BK) if os.path.isdir(BK) else None)
import zipfile as _zf
_zip = [n for n in os.listdir(BK) if n.startswith(A.AUTO_BACKUP_PREFIX)][0]
check("and holds the finds and the settings",
      {"deposits.csv", "settings.json"} <= set(_zf.ZipFile(os.path.join(BK, _zip)).namelist()))
check("and says where it went", "Backed up 2 file(s)" in bk.said[-1]
      and BK in bk.said[-1], bk.said[-1:])
check("into Documents > EDSMT backups by default",
      A.backups_dir().endswith(os.path.join("Documents", "EDSMT backups")), A.backups_dir())
for _i in range(14):
    _n = os.path.join(BK, "%s1.1000%d-x.zip" % (A.AUTO_BACKUP_PREFIX, _i))
    open(_n, "w").close()
    os.utime(_n, (2000 + _i, 2000 + _i))
_mine = os.path.join(BK, "EDSMT-backup-by-hand.zip")
open(_mine, "w").close()
os.utime(_mine, (1, 1))
A.tidy_auto_backups(BK)
_left = os.listdir(BK)
check("only the newest ten automatic backups are kept",
      len([n for n in _left if n.startswith(A.AUTO_BACKUP_PREFIX)]) == A.AUTO_BACKUPS_KEPT,
      sorted(_left))
check("and one made by hand is never touched", "EDSMT-backup-by-hand.zip" in _left)

class _Broken:
    def backup_to(self, folder):
        raise OSError("disk full")
bk.store = _Broken()
check("a backup that cannot be written stops the update",
      bk.backup_before_update("1.10099", folder=BK, now=5000.0) is False
      and "was not started" in bk.said[-1] and "disk full" in bk.said[-1], bk.said[-1:])
check("pressing again within 30 s installs without one, and says so",
      bk.backup_before_update("1.10099", folder=BK, now=5020.0) is True
      and "without a backup" in bk.said[-1], bk.said[-1:])
check("but a press minutes later is asked again",
      bk.backup_before_update("1.10099", folder=BK, now=9000.0) is False)
check("no store, nothing to back up: the update goes ahead",
      A.EDSMT.backup_before_update(type("X", (), {"say": lambda *a: None})(), "1") is True)
_iu = SRC.split("    def install_update(self):")[1].split("\n    def ")[0]
check("INSTALL UPDATE saves, backs up, and only then works out what to run",
      _iu.index("self._save_on_exit()") < _iu.index("self.backup_before_update(")
      < _iu.index("kind = build_kind()"))
check("and the message before it says the backup comes first",
      "backs up your finds and settings to" in SRC
      and "Documents > EDSMT backups first" in SRC)

print("== #182: one community map ==")
import edonline as EDO  # noqa
_c = EDO.CommunityClient(worker=None)
_c.configure("https://somebody-elses.example", "", True)
check("an address left in settings.json is not followed",
      _c.base_url == "https://api.radioraxxla.com", _c.base_url)
_c.configure("", "", False)
check("and a blank one is the map too", _c.base_url == "https://api.radioraxxla.com")
_settings_src = SRC.split("class SettingsWindow")[1].split("\nclass ")[0]
check("Settings has no box for an address",
      '"community_url"' not in _settings_src.split("def save(self)")[0]
      and "running your own server" not in SRC)

print("== #184: a key for the overlay, and only in the Rhino ==")
check("Alt+0 turns the overlay on and off, by default",
      A.DEFAULT_SETTINGS["hotkey_overlay"] == "ALT+0"
      and A.EDSMT.wanted_hotkeys(dict(A.DEFAULT_SETTINGS)).get("overlay") == "ALT+0")
check("and nothing else is on that key", not A.key_clash("ALT+0")
      and [k for k, v in A.DEFAULT_SETTINGS.items()
           if k.startswith("hotkey_") and str(v).upper() == "ALT+0"] == ["hotkey_overlay"])
check("an older file with Alt+0 on something else keeps it, the new key starts blank",
      A.keep_new_keys_free(dict(A.DEFAULT_SETTINGS, hotkey_lock="ALT+0"),
                           {"hotkey_lock": "alt+0"})["hotkey_overlay"] == ""
      and A.keep_new_keys_free(dict(A.DEFAULT_SETTINGS), {"hotkey_lock": ""})
      ["hotkey_overlay"] == "ALT+0")
check("Settings has a row for it", '"hotkey_overlay", "Overlay on / off"' in SRC)
_rh = SRC.split("    def run_hotkeys(self):")[1].split("\n    def ")[0]
check("and the key runs the Overlay button's own action",
      '"overlay": ("Overlay", self.toggle_overlay)' in _rh)


class _Ov:
    def __init__(self):
        self.up, self.settings, self.lock = False, {}, True
    showing = property(lambda self: self.up)
    locked = property(lambda self: self.lock)
    def show(self): self.up = True
    def hide(self): self.up = False
    def refresh_settings(self, settings): pass


def _ov_app(**settings):
    app = A.EDSMT.__new__(A.EDSMT)
    app.settings = dict(A.DEFAULT_SETTINGS)
    app.settings.update(dict({"overlay_enabled": True}, **settings))
    app.overlay = _Ov()
    app.redraw = lambda *a, **k: None
    app.said = []
    app.say = lambda text, colour=None: app.said.append(text)
    app.show_overlay_state = lambda: None
    app.game = type("G", (), {"in_rhino": False})()
    return app


ova = _ov_app()
check("only in the Rhino is the default", A.DEFAULT_SETTINGS["overlay_rhino_only"] is True)
check("in the ship the boxes stay down", not ova.follow_vehicle_overlay()
      and not ova.overlay.showing)
ova.game.in_rhino = True
check("in the Rhino they come up", ova.follow_vehicle_overlay() and ova.overlay.showing)
ova.game.in_rhino = False
check("back aboard, or into the Nomad, they go down again",
      ova.follow_vehicle_overlay() and not ova.overlay.showing)
ova.overlay.lock = False
check("unlocked to be arranged, they stay up wherever you are",
      ova.follow_vehicle_overlay() and ova.overlay.showing)
ova.overlay.lock = True
ova.follow_vehicle_overlay()
everywhere = _ov_app(overlay_rhino_only=False)
check("switched to everywhere, they are up in the ship too",
      everywhere.follow_vehicle_overlay() and everywhere.overlay.showing)
off = _ov_app(overlay_enabled=False)
off.game.in_rhino = True
check("and switched off they are never up", not off.follow_vehicle_overlay()
      and not off.overlay.showing)
tog = _ov_app(overlay_enabled=False)
tog.toggle_overlay()
check("Alt+0 in the ship turns it on and says it waits for the Rhino",
      tog.settings["overlay_enabled"] and not tog.overlay.showing
      and "driving a Rhino" in tog.said[-1], tog.said[-1:])
tog.game.in_rhino = True
tog.toggle_overlay()
check("and in the Rhino it goes off at once", not tog.settings["overlay_enabled"]
      and tog.said[-1] == "Overlay off.")
tog.toggle_overlay()
check("and on again, up at once", tog.overlay.showing)
check("the tick follows the Rhino", "self.follow_vehicle_overlay()"
      in SRC.split("    def tick(self):")[1].split("\n    def ")[0])

print("== #185: a survey area outlives a trip to the ship ==")
import coverage as CV  # noqa


class _At:
    has_position, radius_m, heading = True, R, 0.0

    def __init__(self, lat, lon, in_srv=True, body="HIP 1 3 a"):
        self.lat, self.lon, self.in_srv = lat, lon, in_srv
        self.system, self.body = "HIP 1", body


sv = A.EDSMT.__new__(A.EDSMT)
sv.settings = dict(A.DEFAULT_SETTINGS)
sv.survey_book = CV.CoverageBook(os.path.join(TMP, "survey"))
sv.cmap = None
sv.said = []
sv.say = lambda text, colour=None: sv.said.append(text)
sv.flash = lambda *a, **k: None
sv.redraw = lambda *a, **k: None
sv.refresh_survey_note = lambda: None
sv.key = lambda action, fallback: fallback


def _go(at):
    sv.game = at
    return sv.track_survey(at)


_c = (-37.94006, -143.44643)
_go(_At(*_c))
sv.set_survey_centre()
_go(_At(*dest(_c[0], _c[1], 90, 1500)))
sv.set_survey_border()
for _i in range(4):
    _go(_At(*dest(_c[0], _c[1], 45, 200 * _i)))
_before = (sv.cmap.centre, sv.cmap.border_m)
_go(_At(*dest(_c[0], _c[1], 0, 30000), in_srv=False))
_go(_At(*dest(_c[0], _c[1], 0, 60000), in_srv=False, body=""))
_go(_At(*dest(_c[0], _c[1], 180, 500)))
check("centre and border are still there when the Rhino comes back down",
      sv.cmap.centre == _before[0] and sv.cmap.border_m == _before[1]
      and _before[0] is not None, (sv.cmap.centre, sv.cmap.border_m))
check("and the ground swept before the trip is still swept",
      len(sv.cmap.points) >= 4, len(sv.cmap.points))

print("== #186: every find is shared, and Find is everybody's ==")
check("sharing, uploading each find and prices are always on",
      all(A.DEFAULT_SETTINGS[k] is True for k in A.ALWAYS_SHARED)
      and set(A.ALWAYS_SHARED) == {"community_enabled", "community_auto_share",
                                   "share_market_prices"})
_off = os.path.join(os.environ["LOCALAPPDATA"], "RadioRaxxla", "EDSMT")
os.makedirs(_off, exist_ok=True)
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _fh:
    json.dump({"community_enabled": False, "community_auto_share": False,
               "share_market_prices": False, "community_share_cmdr_name": False},
              _fh)
del A.SETTINGS_NOTICE[:]
_loaded = A.load_settings()
check("an older file with sharing off is shared from now on",
      all(_loaded[k] is True for k in A.ALWAYS_SHARED), _loaded)
check("and is told so, once, on the status line",
      any("Sharing is always on" in n for n in A.SETTINGS_NOTICE), A.SETTINGS_NOTICE)
check("but a commander who kept their name off keeps it off",
      _loaded["community_share_cmdr_name"] is False)
del A.SETTINGS_NOTICE[:]
_sw = SRC.split("class SettingsWindow")[1].split("\nclass ")[0]
check("Settings has no switch to stop sharing any more",
      '"community_enabled", "Share' not in _sw and '"community_auto_share"' not in _sw
      and '"share_market_prices"' not in _sw
      and '"community_share_cmdr_name", "Credit finds to my CMDR name"' in _sw)
_of = SRC.split("    def open_find(self):")[1].split("\n    def ")[0]
check("Find opens for everybody, no find of your own needed",
      "find_unlocked" not in _of and "FindWindow(self)" in _of)
_wel = SRC.split("class WelcomeWindow")[1].split("\nclass ")[0]
check("the first-run window says every find is shared and asks only about the name",
      "Every deposit you mark goes on the community map" in _wel
      and "Stay anonymous" in _wel and "Not now" not in _wel)

print("== #188: tick several commodities in every search ==")
_K = ["Bastnäsite", "Helium", "Helium-3", "Monazite", "Ruby", "Sapphire"]
check("a box of several reads back as a list, in Frontier's spelling",
      A.parse_picks("ruby, bastnasite ,SAPPHIRE", _K) == ["Ruby", "Bastnäsite", "Sapphire"],
      A.parse_picks("ruby, bastnasite ,SAPPHIRE", _K))
check("the start of exactly one name is that name", A.parse_picks("Mona", _K) == ["Monazite"])
check("Helium is Helium, not Helium-3 as well",
      A.parse_picks("Helium", _K) == ["Helium"], A.parse_picks("Helium", _K))
check("a start that fits two is not guessed at", A.parse_picks("Heli", _K) == [])
check("nothing a commodity is called is left out, not sent to the server",
      A.parse_picks("Ruby, Unobtainium", _K) == ["Ruby"])
check("Any, blank and a ticked name twice",
      A.parse_picks("Any", _K) == [] and A.parse_picks("", _K) == []
      and A.parse_picks("Ruby, ruby", _K) == ["Ruby"])
check("clicking a name ticks it, clicking it again unticks it",
      A.toggle_pick(["Ruby"], "Sapphire") == ["Ruby", "Sapphire"]
      and A.toggle_pick(["Ruby", "Sapphire"], "ruby") == ["Sapphire"])
check("and Any clears the lot", A.toggle_pick(["Ruby", "Sapphire"], "Any") == [])
check("the box says what is ticked, or Any",
      A.pick_text(["Ruby", "Sapphire"]) == "Ruby, Sapphire" and A.pick_text([]) == "Any")


class _Box:
    """Just enough of a combo box for the list's own logic."""
    def __init__(self, text="Any", command=None):
        self.text, self.command = text, command
    def get(self): return self.text
    def set(self, value): self.text = value
    def cget(self, key): return self.command if key == "command" else None
    def configure(self, **kw):
        if "command" in kw:
            self.command = kw["command"]
    def bind(self, *a, **k): return None
    def after(self, *a, **k): return None


_painted = []
_mb = _Box(command=lambda value: _painted.append(value))
_sg = A.Suggest(_mb, lambda typed: ["Any"] + SV.matches(_K, typed), multi=True)
_sg.pick("Ruby"); _sg.pick("Sapphire")
check("ticked one after another, both are in the box",
      _mb.get() == "Ruby, Sapphire" and _sg.picked() == ["Ruby", "Sapphire"], _mb.get())
_sg.pick("Ruby")
check("and a second click takes one off", _mb.get() == "Sapphire", _mb.get())
_mb.command("Monazite")  # the toolkit's arrow list: it has already overwritten the box
check("a pick from the box's own arrow list ticks as well, rather than replacing",
      _mb.get() == "Sapphire, Monazite", _mb.get())
check("and whatever the box did on a pick still happens, with the whole list",
      _painted == ["Sapphire, Monazite"], _painted)
_mb.set("Sapphire, Monazite, rub"); _sg._engaged = True
_sg.pick("Ruby")
check("typed and taken: 'rub' and Enter on Ruby ADDS Ruby",
      _mb.get() == "Sapphire, Monazite, Ruby", _mb.get())
_mb.set("Sapphire, rubbish"); _sg._engaged = False
_sg.tidy()
check("leaving the box tidies what cannot be a commodity out of it",
      _mb.get() == "Sapphire", _mb.get())
check("a box without the list is one name or none",
      A.picks_of(_Box("Ruby")) == ["Ruby"] and A.picks_of(_Box("Any")) == [])
check("and one with it is every name ticked", A.picks_of(_mb) == ["Sapphire"])
_one = _Box("Any")
A.Suggest(_one, _K)
_one.suggest.pick("Ruby"); _one.suggest.pick("Sapphire")
check("a single-pick list still replaces - the rail's commodity is one name",
      _one.get() == "Sapphire", _one.get())

for _cls in ("class FindWindow", "class LandWindow", "class SitesWindow",
             "class EarningsWindow"):
    _body = SRC.split(_cls)[1].split("\nclass ")[0]
    check("%s ticks several commodities" % _cls.split()[1],
          "multi=True" in _body, _cls)

check("the community client sends several as one parameter",
      EDO.commodity_param(["Monazite", "Bastnäsite", "monazite", ""]) ==
      "Monazite,Bastnäsite" and EDO.commodity_param("Ruby") == "Ruby"
      and EDO.commodity_param("") == "" and EDO.commodity_param(None) == "")


class _Jobs:
    def __init__(self): self.jobs = []
    def submit(self, tag, fn): self.jobs.append((tag, fn))


_w = _Jobs()
_cc = EDO.CommunityClient(worker=_w)
_cc.configure("", enabled=True)
_cc.sites(commodity="Monazite,Bastnäsite")
_cc.search(commodity=["Ruby", "Sapphire"])
_cc.intact(commodity=("Olivine",))
_cc.best_prices(commodity=["Ruby", "Sapphire"])
_urls = []
_real_get = EDO.get_json
EDO.get_json = lambda url, **k: (_urls.append(url), {"sites": [], "deposits": [], "prices": []})[1]
try:
    for _tag, _fn in _w.jobs:
        _fn()
finally:
    EDO.get_json = _real_get
check("sites, deposits, still there and prices all take several",
      "commodity=Monazite%2CBastn%C3%A4site" in _urls[0]
      and "commodity=Ruby%2CSapphire" in _urls[1]
      and "commodity=Olivine" in _urls[2]
      and "commodity=Ruby%2CSapphire" in _urls[3], _urls)


class _FindStub:
    """The bits of the Find window its several-commodity logic touches."""
    def __init__(self):
        self.said, self._sell_batch, self._asked = [], None, []
    def say(self, text, colour=None): self.said.append(text)


_fs = _FindStub()
_fs._asked = ["Ruby", "Sapphire"]
check("an older server, asked for two, is told apart from finding nothing",
      A.FindWindow._older_server(_fs, {"sites": []}) is True
      and "updated" in _fs.said[-1], _fs.said)
check("a server that says what it filtered on is believed",
      A.FindWindow._older_server(_fs, {"sites": [], "commodities": ["Ruby", "Sapphire"]})
      is False)
_fs._asked = ["Ruby"]
check("and one commodity never trips it",
      A.FindWindow._older_server(_fs, {"sites": []}) is False)
_fs._sell_batch = {"want": 3, "got": 0, "rows": []}
A.FindWindow._batch_reply(_fs, [{"commodity": "Ruby", "sell": 1}])
A.FindWindow._batch_reply(_fs, [], ok=False)
_so_far = A.FindWindow._batch_reply(_fs, [{"commodity": "Sapphire", "sell": 2}])
check("best sell prices for several: every answer is added to the one table",
      [r["commodity"] for r in _so_far] == ["Ruby", "Sapphire"], _so_far)
A.FindWindow._batch_note(_fs)
check("and one that did not answer is owned up to, not hidden",
      "1 of 3 commodities could not be priced" in _fs.said[-1], _fs.said[-1:])
_fs._sell_batch = {"want": 3, "got": 1, "rows": []}
A.FindWindow._batch_note(_fs)
check("while answers are still coming, it says how many so far",
      "1 of 3" in _fs.said[-1] and "on their way" in _fs.said[-1], _fs.said[-1:])
_sp = SRC.split("    def search_prices(self):")[1].split("\n    def say")[0]
check("several commodities go to the market index one at a time, spaced",
      "_sell_several(names" in _sp and "QUOTE_GAP_MS" in _sp)

_LANDROWS = [{"short": "A 1", "carries": ["monazite"]},
             {"short": "A 2", "carries": ["ruby", "sapphire"]},
             {"short": "A 3", "carries": ["olivine"]}]
check("Where to land: a body carrying either of two ticked stays",
      [r["short"] for r in A.land_carrying(_LANDROWS, ["Monazite", "Ruby"])] == ["A 1", "A 2"])
check("and one name, or a list written out, works the same",
      [r["short"] for r in A.land_carrying(_LANDROWS, "Olivine")] == ["A 3"]
      and [r["short"] for r in A.land_carrying(_LANDROWS, "Olivine, Sapphire")] == ["A 2", "A 3"]
      and len(A.land_carrying(_LANDROWS, [])) == 3)
_SITES = [{"system": "Ega", "body": "Ega 1", "signal": "1", "types": ["Ruby"], "offers": []},
          {"system": "Col 285", "body": "Col 285 A 1", "signal": "2", "types": [],
           "offers": ["Monazite"]},
          {"system": "Wyrd", "body": "Wyrd 3", "signal": "1", "types": ["Olivine"], "offers": []}]
check("My sites: commas in the filter are alternatives",
      [x["system"] for x in A.sites_matching(_SITES, "ega, wyrd")] == ["Ega", "Wyrd"])
check("and the commodity ticks keep sites carrying any of them, found or offered",
      [x["system"] for x in A.sites_matching(_SITES, "", ["Monazite", "Ruby"])] == ["Ega", "Col 285"])
check("both together narrow both ways",
      [x["system"] for x in A.sites_matching(_SITES, "col", ["Monazite", "Ruby"])] == ["Col 285"])

print("== #187: the last known prices in a system ==")
_ROWS = [
    {"commodity": "Magnesite", "station": "Vonarburg", "sell": 120500, "demand": 40,
     "seen": "2026-10-07T00:00:00Z", "source": "community", "pad": 3,
     "station_type": "Orbis"},
    {"commodity": "Magnesite", "station": "Black Hide", "sell": 22911, "demand": 0,
     "seen": "2026-10-07T00:41:01.000Z", "source": "index", "pad": 2,
     "station_type": "CraterOutpost"},
    {"commodity": "Magnesite", "station": "Bokeili", "sell": 41239, "demand": 0,
     "seen": "2026-10-06T22:59:24.000Z", "source": "index", "pad": 3},
    {"commodity": "Bastnäsite", "station": "Black Hide", "sell": 49538, "demand": 3,
     "seen": "2026-10-07T00:41:01.000Z", "source": "index"},
    {"commodity": "Olivine", "station": "Nowhere", "sell": 0},
]
_best = A.system_price_rows(_ROWS, best_only=True)
check("best market only: one row a commodity, the best of them",
      [(r["commodity"], r["station"]) for r in _best]
      == [("Magnesite", "Vonarburg"), ("Bastnäsite", "Black Hide")], _best)
check("each row says how many markets there buy it",
      [r["markets"] for r in _best] == [3, 1], [r["markets"] for r in _best])
_all = A.system_price_rows(_ROWS, best_only=False)
check("every market: all of them, best first within each commodity",
      [r["station"] for r in _all if r["commodity"] == "Magnesite"]
      == ["Vonarburg", "Bokeili", "Black Hide"], _all)
check("a zero price is not a price", all(r["commodity"] != "Olivine" for r in _all))
check("pads and station types read the way the game says them",
      A.pad_size(3) == "L" and A.pad_size(2) == "M" and A.pad_size("s") == "S"
      and A.pad_size(None) == "-"
      and A.station_kind("CraterOutpost") == "Crater outpost"
      and A.station_kind("OnFootSettlement") == "Settlement"
      and A.station_kind("Orbis") == "Orbis" and A.station_kind("") == "-")
_ans = {"system": "Wyrd", "rows": _ROWS, "status": "live", "picked": []}
check("the status line counts commodities and markets",
      A.system_price_status(_ans, _best) == "Wyrd: 2 commodities priced at 4 markets.",
      A.system_price_status(_ans, _best))
check("and owns up when the market index did not answer",
      "did not answer" in A.system_price_status(dict(_ans, status="unavailable"), _best))
check("or the server is older than the app",
      "has not been updated" in A.system_price_status(
          dict(_ans, status="server not updated"), _best))
check("a misspelt system is told so, not shown an empty table",
      "Check the spelling" in A.system_price_empty(
          {"system": "Wird", "status": "unknown system"}))
check("and an unpriced one says what would fix it",
      "open the commodity market" in A.system_price_empty(
          {"system": "Wyrd", "status": "live", "picked": ["Ruby"]})
      and "for Ruby" in A.system_price_empty(
          {"system": "Wyrd", "status": "live", "picked": ["Ruby"]}))

_w2 = _Jobs()
_cc2 = EDO.CommunityClient(worker=_w2)
_cc2.configure("", enabled=True)
check("asked for no system, nothing is sent", _cc2.system_prices("") is False and not _w2.jobs)
_cc2.system_prices("Wyrd", ["Magnesite", "Bastnäsite"], max_days=30)
_tag, _ask = _w2.jobs[-1]
check("it goes out under its own tag, for the Earnings window",
      _tag == A.SYSTEM_PRICE_TAG == "system-prices", _tag)
_seen = []
def _new_server(url, **k):
    _seen.append(url)
    return {"system": "Wyrd", "prices": [{"commodity": "Magnesite"}],
            "upstream_status": "live", "commodities": ["Magnesite"]}
EDO.get_json = _new_server
try:
    _got = json.loads(_ask())
finally:
    EDO.get_json = _real_get
check("one request for the whole system, with what was ticked",
      len(_seen) == 1 and "/v1/system-prices?" in _seen[0] and "system=Wyrd" in _seen[0]
      and "commodity=Magnesite%2CBastn%C3%A4site" in _seen[0] and "max_days=30" in _seen[0],
      _seen)
check("and the answer comes straight back", _got["upstream_status"] == "live")
_seen = []
def _old_server(url, **k):
    _seen.append(url)
    if "/v1/system-prices" in url:
        raise RuntimeError("api.radioraxxla.com refused it (HTTP 404): Not Found")
    return {"count": 3, "prices": [
        {"commodity": "Magnesite", "station": "A", "system": "Wyrd", "sell": 5},
        {"commodity": "Bastnäsite", "station": "B", "system": "Wyrd", "sell": 6},
        {"commodity": "Ruby", "station": "C", "system": "Wyrd", "sell": 7}]}
EDO.get_json = _old_server
try:
    _got = json.loads(_ask())
finally:
    EDO.get_json = _real_get
check("a server from before this build: the plain price table for that system",
      len(_seen) == 2 and "/v1/prices?" in _seen[1] and "near=Wyrd" in _seen[1]
      and "commodity=" not in _seen[1], _seen)
check("cut down here to what was ticked, and labelled as commanders' own",
      [r["commodity"] for r in _got["prices"]] == ["Magnesite", "Bastnäsite"]
      and all(r["source"] == "community" for r in _got["prices"]), _got)
check("and it says the server is the older one",
      _got["upstream_status"] == "server not updated")
def _down(url, **k):
    raise RuntimeError("api.radioraxxla.com is having trouble at its end (HTTP 503).")
EDO.get_json = _down
try:
    _raised = None
    try:
        _ask()
    except RuntimeError as exc:
        _raised = exc
finally:
    EDO.get_json = _real_get
check("any other failure is reported, not papered over with the fallback",
      _raised is not None and "503" in str(_raised))
_cr = SRC.split("    def collect_results(self):")[1].split("\n    def ")[0]
check("the app hands the answer to the Earnings window",
      "SYSTEM_PRICE_TAG" in _cr and "system_results(ok, message)" in _cr)
_ew = SRC.split("class EarningsWindow")[1].split("\nclass ")[0]
check("the Earnings window has the search, the ticks and both views",
      '"Search system"' in _ew and '"Best market only"' in _ew
      and '"System prices"' in _ew and '"Rhino sessions"' in _ew
      and "system_prices(system, picked" in _ew)

print("== #192: the Rhino on the page, on GitHub and in the app ==")
_REPO = os.path.dirname(HERE)
def _png_size(path):
    with open(path, "rb") as fh:
        head = fh.read(24)
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
for _name, _size in ((A.WELCOME_PICTURE, (512, 210)), (A.ABOUT_PICTURE, (540, 300))):
    _path = os.path.join(_REPO, "images", _name)
    check("images/%s is there, %dx%d" % ((_name,) + _size),
          os.path.isfile(_path) and _png_size(_path) == _size,
          os.path.isfile(_path) and _png_size(_path))
    for _spec in ("EDSMT.spec", "EDSMT-onefile.spec"):
        _text = open(os.path.join(_REPO, "build", _spec), encoding="utf-8").read()
        check("and %s ships it" % _spec, '"%s"' % _name in _text and '"images"' in _text)
check("a picture that is not there is no picture, not an error",
      A.picture("no-such-picture.png") is None)
_about = A.about_text()
check("About says which build, whose, the licence and Frontier's",
      A.APP_VERSION in _about and "Radio Raxxla" in _about and "GPL-3.0-only" in _about
      and "Frontier Developments" in _about and "not affiliated" in _about)
_site = open(os.path.join(_REPO, "site", "index.html"), encoding="utf-8").read()
for _jpg in ("rhino-1600.jpg", "rhino-800.jpg", "rhino-card.jpg"):
    check("the download page's %s is in site/" % _jpg,
          _jpg in _site and os.path.isfile(os.path.join(_REPO, "site", _jpg)))
check("link previews show the Rhino, large",
      'og:image" content="https://radioraxxla.com/EDSMT/rhino-card.jpg"' in _site
      and 'twitter:card" content="summary_large_image"' in _site)
check("and the page credits the screenshot and Frontier under it",
      "screenshot by CMDR TheAnnouncer" in _site and "Frontier Developments plc" in _site)
check("so do About and the README",
      "screenshot by CMDR TheAnnouncer" in A.about_text()
      and "screenshot by CMDR TheAnnouncer" in open(os.path.join(_REPO, "README.md"),
                                                    encoding="utf-8").read())
_bat = open(os.path.join(_REPO, "BUILD.bat"), encoding="utf-8").read()
_yml = open(os.path.join(_REPO, ".github", "workflows", "build.yml"), encoding="utf-8").read()
check("BUILD.bat and the Actions build both put the page's pictures with it",
      "site\\*.jpg" in _bat and "site\\*.jpg" in _yml)
_readme = open(os.path.join(_REPO, "README.md"), encoding="utf-8").read()
check("the README opens on the Rhino, credited",
      "](docs/images/rhino.jpg)" in _readme.split("## Get it")[0]
      and os.path.isfile(os.path.join(_REPO, "docs", "images", "rhino.jpg"))
      and "Frontier Developments plc" in _readme.split("## Get it")[0])

print("== #168: credited ==")
check("CMDR Todd Jenkins is credited as a tester", "CMDR Todd Jenkins" in A.BETA_TESTERS)

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
