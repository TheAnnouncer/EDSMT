"""1.10038: the mining location you are at, without targeting it.

Asked on 28 Oct: "when I select the signal site it shows me what's in that
zone - why can't you auto detect this when they are in atmosphere".

- zone.py says which location you are in from your own logged centres and
  the finds other commanders have shared on the body, with a wider net
  while you are still high up and gliding in.
- Entering one sets the Signal box (unless the game has a location
  targeted, or you picked a number by hand while inside it) and says what
  is there, once. The deposit list shows the shared finds in that signal.
- Nothing known within reach: one dim line, once per body, with the
  game's own count of mining locations on it.
- The STATUS box of the overlay carries the location and its top finds.
- FSSBodySignals alone (4.4.2) is enough for Where to land to count a
  body's locations - no DSS needed.

Pure parts run anywhere; the app on the real toolkit under xvfb:

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110038_zone.py
"""
import os, sys, json, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-zone38-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import survey as SV        # noqa: E402
import journal as JN       # noqa: E402
import zone as ZN          # noqa: E402

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
            traceback.print_exc(limit=6)
        return fn
    return wrap


R = 2_100_000.0
HOME = (12.5, -45.5)
DAY = 86400.0


def at(bearing, metres, origin=HOME):
    return SV.destination(origin[0], origin[1], bearing, metres, R)


def stamp(ago_s=0.0):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - ago_s))


def own_location(signal, lat, lon):
    return {"system": "Ega", "body": "Ega 1", "location": str(signal),
            "lat": "%.6f" % lat, "lon": "%.6f" % lon}


def shared(signal, lat, lon, commodity, rigs="", cmdr="Raxxla One", ago=9 * DAY,
           amount="High", ident=None):
    """A shared find the way take_shared files it."""
    return {"id": "shared-%s" % (ident or "%s-%s" % (signal, commodity)),
            "system": "Ega", "body": "Ega 1", "location": str(signal),
            "commodity": commodity, "rigs": str(rigs), "amount": amount,
            "density": "Medium", "lat": "%.6f" % lat, "lon": "%.6f" % lon,
            "notes": "", "cmdr": cmdr, "status": "reported", "shared": True,
            "when": stamp(ago)}


# Signal 7, shared: three finds a few hundred metres apart, 30 km east of HOME.
SEVEN = at(90, 30000)
SHARED_SEVEN = [shared(7, *at(0, 200, SEVEN), "Iridium", 4),
                shared(7, *at(120, 300, SEVEN), "Sapphire", 2),
                shared(7, *at(240, 250, SEVEN), "Iridium", 1, ident="7-iridium-b")]
# Signal 3, shared by somebody else, 60 km south.
THREE = at(180, 60000)
SHARED_THREE = [shared(3, *THREE, "Gold", 3, cmdr="CMDR Other", ago=0.5 * DAY)]
SHARED = SHARED_SEVEN + SHARED_THREE


@section("zone_here: who wins, and how far the net reaches")
def _zone_here():
    own = [own_location(4, *HOME)]
    near_home = at(45, 800)
    rival = [shared(5, *at(45, 300), "Gold", 3)]
    zone = ZN.zone_here(own, rival, near_home[0], near_home[1], R, None)
    check("your own logged centre within %d m beats a shared find nearer still"
          % ZN.ZONE_OWN_M, zone and zone["signal"] == "4" and zone["source"] == "own", zone)
    here = at(90, 3000, SEVEN)
    zone = ZN.zone_here([], SHARED, here[0], here[1], R, 0.0)
    check("nothing of yours: the nearest shared location within %d m, with the distance"
          % ZN.ZONE_APPROACH_M, zone and zone["signal"] == "7" and zone["source"] == "shared"
          and 2500 < zone["metres"] < 3100 and zone["reach_m"] == ZN.ZONE_APPROACH_M, zone)
    far = at(90, 9000, SEVEN)
    low = ZN.zone_here([], SHARED, far[0], far[1], R, 500.0)
    high = ZN.zone_here([], SHARED, far[0], far[1], R, 3000.0)
    unknown = ZN.zone_here([], SHARED, far[0], far[1], R, None)
    check("9 km out and low: not in it", low is None, low)
    check("9 km out and above %d m: gliding in, so the net reaches %d m"
          % (ZN.ZONE_GLIDE_ALT_M, ZN.ZONE_GLIDE_M),
          high and high["signal"] == "7" and high["reach_m"] == ZN.ZONE_GLIDE_M, high)
    check("no height known: the ground net", unknown is None, unknown)
    away = at(0, 200000)
    check("nothing within reach is None", ZN.zone_here(own, SHARED, away[0], away[1], R, 3000.0) is None)
    blind = [dict(SHARED_THREE[0], lat=None, lon=None), {"location": "9", "lat": "", "lon": ""}]
    check("a find or a centre with no position is passed over, not guessed at",
          ZN.zone_here([{"location": "2", "lat": "", "lon": ""}], blind, THREE[0], THREE[1], R, 0.0) is None)
    three_km = at(0, 3000)
    zone = ZN.zone_here(own, [], three_km[0], three_km[1], R, 0.0)
    check("your own centre 3 km off with nothing shared is still the one you are at - as before",
          zone and zone["signal"] == "4" and zone["source"] == "own", zone)
    zone = ZN.zone_here(own, [shared(6, *at(0, 3800), "Gold", 2)], three_km[0], three_km[1], R, 0.0)
    check("beyond %d m from your centre, the nearer of yours and theirs wins - theirs at 800 m"
          % ZN.ZONE_OWN_M, zone and zone["signal"] == "6" and zone["source"] == "shared", zone)
    check("junk positions do not raise", ZN.zone_here(own, SHARED, None, None, R, 0.0) is None
          and ZN.zone_here(own, SHARED, 1.0, 1.0, None, 0.0) is None)
    check("the reach is one function of height",
          [ZN.reach_m(h) for h in (None, 0, 1999, 2000, 2001, 25000)]
          == [ZN.ZONE_APPROACH_M] * 4 + [ZN.ZONE_GLIDE_M] * 2)


@section("what is in the location, in one line")
def _lines():
    check("the finds filed under one number", [f["commodity"] for f in ZN.finds_in("7", SHARED)]
          == ["Iridium", "Sapphire", "Iridium"] and ZN.finds_in(3, SHARED) == SHARED_THREE)
    check("the top commodities, most rigs first, each named once",
          ZN.summary(SHARED_SEVEN) == "Iridium 4R, Sapphire 2R", ZN.summary(SHARED_SEVEN))
    many = [shared(1, *HOME, c, r) for c, r in (("Gold", 1), ("Silver", 6), ("Bauxite", ""),
                                                ("Iron", 3), ("Lead", 2))]
    check("at most three, then how many more",
          ZN.summary(many) == "Silver 6R, Iron 3R, Lead 2R +2 more", ZN.summary(many))
    check("a commodity worked out everywhere it was found says so",
          ZN.summary([shared(1, *HOME, "Gold", 2, amount="Depleted")]) == "Gold 2R (worked out)",
          ZN.summary([shared(1, *HOME, "Gold", 2, amount="Depleted")]))
    check("nothing is an empty string", ZN.summary([]) == "")
    zone = {"signal": "7", "source": "shared", "metres": 2800.0, "reach_m": 5000.0}
    line = ZN.zone_line(zone, [], ZN.finds_in("7", SHARED))
    check("a shared location: what it holds, how many finds, who shared them and when",
          line == "Mining location 7 - Iridium 4R, Sapphire 2R (3 finds shared by CMDR Raxxla One, 9 days ago)",
          line)
    line = ZN.zone_line(dict(zone, signal="3"), [], SHARED_THREE)
    check("one find, a name already carrying CMDR, shared today",
          line == "Mining location 3 - Gold 3R (1 find shared by CMDR Other, today)", line)
    mixed = SHARED_SEVEN + [dict(SHARED_SEVEN[0], cmdr="CMDR Two", id="shared-x")]
    line = ZN.zone_line(zone, [], mixed)
    check("several commanders: the one with most finds, and how many others",
          line.endswith("(4 finds shared by CMDR Raxxla One and 1 other, 9 days ago)"), line)
    nameless = [dict(f, cmdr="", when="") for f in SHARED_SEVEN]
    line = ZN.zone_line(zone, [], nameless)
    check("no names and no dates: still a sentence",
          line == "Mining location 7 - Iridium 4R, Sapphire 2R (3 finds shared)", line)
    mine = [{"commodity": "Platinum", "rigs": "4", "amount": "High", "location": "7",
             "lat": "%.6f" % SEVEN[0], "lon": "%.6f" % SEVEN[1]}]
    line = ZN.zone_line(dict(zone, source="own"), mine, [])
    check("your own: yours, and what you marked", line == "Mining location 7 - yours: Platinum 4R", line)
    line = ZN.zone_line(dict(zone, source="own"), [], [])
    check("your own with nothing marked yet says so",
          line == "Mining location 7 - yours, nothing marked in it yet", line)
    line = ZN.zone_line(zone, mine, ZN.finds_in("7", SHARED))
    check("yours and theirs together",
          line == "Mining location 7 - yours: Platinum 4R; shared: Iridium 4R, Sapphire 2R "
                  "(3 finds by CMDR Raxxla One, 9 days ago)", line)
    check("nothing within reach: the dim line, with the game's count",
          ZN.nothing_line(15000.0, 3) == "No finds shared within 15 km - the game's signal "
                                          "list says 3 mining locations on this body"
          and ZN.nothing_line(5000.0, 1) == "No finds shared within 5 km - the game's signal "
                                             "list says 1 mining location on this body",
          ZN.nothing_line(15000.0, 3))
    check("and without a count from the game, says that instead",
          ZN.nothing_line(5000.0, 0) == "No finds shared within 5 km - the game's signal list "
                                         "has no mining locations for this body yet",
          ZN.nothing_line(5000.0, 0))
    # A shared find that is one of yours come back from the server is not
    # listed twice.
    back = [dict(SHARED_SEVEN[0], commodity="Platinum", lat="%.6f" % SEVEN[0], lon="%.6f" % SEVEN[1])]
    check("a shared find on top of one of yours, same commodity, is yours - left out",
          ZN.others(back + SHARED_SEVEN[1:], mine, R) == SHARED_SEVEN[1:])
    card = ZN.status_card("7", mine, ZN.finds_in("7", SHARED))
    check("the overlay card: the number and the top finds, yours first",
          card == {"signal": "7", "summary": "Platinum 4R, Iridium 4R, Sapphire 2R"}, card)
    check("ages read as words", [ZN.age_words(stamp(x)) for x in (0, DAY + 60, 9 * DAY + 60)]
          == ["today", "yesterday", "9 days ago"] and ZN.age_words("") == ""
          and ZN.age_words("2026-10-19T12:00:00.123456+00:00", now=1793188800) == "9 days ago")


@section("journal: the live target beside the sticky one")
def _journal():
    reader = JN.JournalWatcher(TMP)
    check("nothing targeted to begin with", reader.destination_signal == "")
    reader._read_destination({"System": 1, "Body": 24, "Name": "$SAA_Unknown_Signal:#index=15;"})
    check("a targeted location is live and remembered",
          reader.destination_signal == "15" and reader.target_signal == "15")
    folder = os.path.join(TMP, "live")
    os.makedirs(folder, exist_ok=True)
    live = JN.JournalWatcher(folder)
    with open(os.path.join(folder, "Status.json"), "w", encoding="utf-8") as handle:
        json.dump({"timestamp": stamp(), "event": "Status", "Flags": (1 << 21) | (1 << 24),
                   "Latitude": 1.0, "Longitude": 2.0, "Heading": 0, "Altitude": 900,
                   "BodyName": "Ega 1", "PlanetRadius": R,
                   "Destination": {"System": 1, "Body": 2,
                                   "Name": "$SAA_Unknown_Signal:#index=7;"}}, handle)
    live.poll()
    check("read from Status.json: live and sticky both say 7",
          live.destination_signal == "7" and live.target_signal == "7" and live.altitude == 900,
          (live.destination_signal, live.target_signal))
    with open(os.path.join(folder, "Status.json"), "w", encoding="utf-8") as handle:
        json.dump({"timestamp": stamp(), "event": "Status", "Flags": (1 << 21) | (1 << 24),
                   "Latitude": 1.0, "Longitude": 2.0, "Heading": 0, "BodyName": "Ega 1",
                   "PlanetRadius": R}, handle)
    live.poll()
    check("the target dropped: nothing is live, the last one is still remembered",
          live.destination_signal == "" and live.target_signal == "7",
          (live.destination_signal, live.target_signal))
    with open(os.path.join(folder, "Status.json"), "w", encoding="utf-8") as handle:
        json.dump({"timestamp": stamp(), "event": "Status", "Flags": (1 << 21) | (1 << 24),
                   "Latitude": 1.0, "Longitude": 2.0, "Heading": 0, "BodyName": "Ega 1",
                   "PlanetRadius": R, "Destination": {"System": 1, "Body": 0, "Name": "Ega"}}, handle)
    live.poll()
    check("a destination that is not a location is not a live target",
          live.destination_signal == "" and live.target_signal == "7")


@section("FSSBodySignals alone counts a body's locations for Where to land")
def _fss_only():
    folder = os.path.join(TMP, "fss")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "Journal.2026-10-28T100000.01.log"), "w", encoding="utf-8") as handle:
        for event in (
            {"timestamp": "2026-10-28T10:00:01Z", "event": "Fileheader", "gameversion": "4.4.2.1", "part": 1},
            {"timestamp": "2026-10-28T10:00:02Z", "event": "Commander", "Name": "Jameson", "FID": "F1"},
            {"timestamp": "2026-10-28T10:00:03Z", "event": "FSDJump", "StarSystem": "Ega",
             "SystemAddress": 11, "StarPos": [1.0, 2.0, 3.0]},
            {"timestamp": "2026-10-28T10:00:04Z", "event": "FSSBodySignals", "BodyName": "Ega 1",
             "BodyID": 1, "SystemAddress": 11,
             "Signals": [{"Type": "$PlanetaryMiningLocation_Name;",
                          "Type_Localised": "Planetary Mining Location", "Count": 3}]},
            {"timestamp": "2026-10-28T10:00:05Z", "event": "Scan", "ScanType": "Detailed",
             "BodyName": "Ega 1", "BodyID": 1, "StarSystem": "Ega", "DistanceFromArrivalLS": 400.0,
             "Landable": True, "PlanetClass": "Rocky body", "Radius": R, "SurfaceGravity": 3.2},
        ):
            handle.write(json.dumps(event) + "\n")
    with open(os.path.join(folder, "Status.json"), "w", encoding="utf-8") as handle:
        json.dump({"timestamp": stamp(), "event": "Status", "Flags": 0}, handle)
    reader = JN.JournalWatcher(folder)
    reader.poll()
    check("the reader counts them with no DSS", reader.mining_signals("Ega 1") == 3
          and "Ega 1" not in reader.body_mapped, reader.body_signals)
    bodies = reader.system_bodies("Ega")
    check("the system's bodies carry the count, and say the DSS has not mapped it",
          bodies and bodies[0]["locations"] == 3 and bodies[0]["mapped"] is False, bodies)
    ranked = SV.rank_bodies("Ega", bodies, None, [], {}, [], [], {})
    check("Where to land ranks it on three locations nobody has shared",
          ranked and ranked[0]["locations"] == 3 and "3 locations nobody has shared" in ranked[0]["why"],
          [(r["locations"], r["why"]) for r in ranked])


# ---------------------------------------------------------------------------
# The app on the real toolkit. Nothing leaves the machine.
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    print("  SKIP  the app needs a display (%s). Run it under xvfb-run." % _exc)
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    raise SystemExit(1 if fails else 0)

import socket            # noqa: E402


def _refuse(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        raise OSError("this check runs offline")
    return _real_connect(self, address)


_real_connect = socket.socket.connect
socket.socket.connect = _refuse
socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(OSError("offline"))

import overlay as OV     # noqa: E402
OV.foreground_is_game = lambda: None
import edsmt as A        # noqa: E402
A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
    json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS}, _f)


class Link:
    """Stands in for the community link: nothing leaves the machine."""
    ready = True
    can_read = True
    can_verify = False
    share_name = True
    enabled = True

    def __init__(self):
        self.asked = []

    def system_sites(self, system):
        self.asked.append(system)
        return True

    def __getattr__(self, name):
        return lambda *args, **kwargs: False


app = A.EDSMT()
app.geometry("1600x1000+0+0")
app.updates.check = lambda *args, **kwargs: None
app.community.enabled = False
app.community = Link()


def pump(times=3):
    for _ in range(times):
        app.update_idletasks()
        app.update()


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


def words_in(widget):
    out = []
    try:
        out.append(str(widget.cget("text")))
    except Exception:
        pass
    for child in widget.winfo_children():
        out.extend(words_in(child))
    return out


JOURNAL = os.path.join(JOURNALS, "Journal.2026-10-28T120000.01.log")
SHIP = (1 << 21) | (1 << 24)


def emit(*events):
    with open(JOURNAL, "a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")


def status(lat, lon, altitude=400, flags=SHIP, target=None, body="Ega 1"):
    data = {"timestamp": stamp(), "event": "Status", "Flags": flags, "Latitude": lat,
            "Longitude": lon, "Heading": 90, "Altitude": altitude, "BodyName": body,
            "PlanetRadius": R}
    if target:
        data["Destination"] = {"System": 11, "Body": 1,
                               "Name": "$SAA_Unknown_Signal:#index=%s;" % target}
    with open(os.path.join(JOURNALS, "Status.json"), "w", encoding="utf-8") as handle:
        json.dump(data, handle)


def tick(times=1):
    for _ in range(times):
        app.tick()
    pump(2)


def said():
    return str(app.status.cget("text"))


pump()
emit({"timestamp": "2026-10-28T12:00:01Z", "event": "Fileheader", "gameversion": "4.4.2.1", "part": 1},
     {"timestamp": "2026-10-28T12:00:02Z", "event": "Commander", "Name": "Jameson", "FID": "F1"},
     {"timestamp": "2026-10-28T12:00:03Z", "event": "FSDJump", "StarSystem": "Ega", "SystemAddress": 11,
      "StarPos": [1.0, 2.0, 3.0]},
     {"timestamp": "2026-10-28T12:00:04Z", "event": "FSSBodySignals", "BodyName": "Ega 1", "BodyID": 1,
      "SystemAddress": 11, "Signals": [{"Type": "$PlanetaryMiningLocation_Name;",
                                        "Type_Localised": "Planetary Mining Location", "Count": 3}]},
     {"timestamp": "2026-10-28T12:00:05Z", "event": "Scan", "ScanType": "Detailed", "BodyName": "Ega 1",
      "BodyID": 1, "StarSystem": "Ega", "DistanceFromArrivalLS": 400.0, "Landable": True,
      "PlanetClass": "Rocky body", "Radius": R},
     {"timestamp": "2026-10-28T12:00:06Z", "event": "ApproachBody", "StarSystem": "Ega", "Body": "Ega 1"})
FAR = at(0, 200000)


@section("the app: entering a shared location sets the Signal box and says what is there, once")
def _enter_shared():
    status(FAR[0], FAR[1], altitude=12000)
    tick()
    # The system's shared sites answered empty, so the arrival line has
    # nothing to say and cannot talk over what is checked below.
    app.take_landing(True, json.dumps({"system": "Ega", "sites": []}))
    app.take_shared(True, json.dumps({"system": "Ega", "body": "Ega 1", "deposits": [
        {"id": 1, "system": "Ega", "planet": "Ega 1", "spot": "7", "type": "Iridium", "rigs": 4,
         "amount": "High", "density": "Medium", "lat": SHARED_SEVEN[0]["lat"], "lon": SHARED_SEVEN[0]["lon"],
         "uploader": "Raxxla One", "status": "reported", "created": stamp(9 * DAY + 60),
         "last_seen": stamp(9 * DAY + 60)},
        {"id": 2, "system": "Ega", "planet": "Ega 1", "spot": "7", "type": "Sapphire", "rigs": 2,
         "amount": "Medium", "lat": SHARED_SEVEN[1]["lat"], "lon": SHARED_SEVEN[1]["lon"],
         "uploader": "Raxxla One", "created": stamp(12 * DAY), "last_seen": stamp(9 * DAY + 60)},
        {"id": 3, "system": "Ega", "planet": "Ega 1", "spot": "7", "type": "Iridium", "rigs": 1,
         "amount": "Low", "lat": SHARED_SEVEN[2]["lat"], "lon": SHARED_SEVEN[2]["lon"],
         "uploader": "Raxxla One", "created": stamp(9 * DAY + 60)},
        {"id": 4, "system": "Ega", "planet": "Ega 1", "spot": "3", "type": "Gold", "rigs": 3,
         "amount": "High", "lat": SHARED_THREE[0]["lat"], "lon": SHARED_THREE[0]["lon"],
         "uploader": "CMDR Other", "created": stamp(0.5 * DAY)},
    ]}))
    filed = app.shared[("ega", "ega 1")]["rows"]
    check("the shared finds are filed with when they were last seen",
          len(filed) == 4 and filed[0]["when"] == stamp(9 * DAY + 60) and filed[3]["when"] == stamp(0.5 * DAY),
          [f.get("when") for f in filed])
    app.say("before", A.DIM)
    tick()
    check("the app reads the session: Ega 1, in the ship, high up, a position",
          app.game.body == "Ega 1" and app.game.has_position and app.game.in_ship
          and app.game.altitude == 12000 and app.signal() == "1",
          (app.game.body, app.game.altitude, app.signal()))
    check("high over nothing known, the shared finds in: one dim line with the game's count",
          said() == "No finds shared within 15 km - the game's signal list says 3 mining locations on this body",
          said())
    check("and no card", app.zone_card() is None, app.zone_card())
    app.say("before", A.DIM)
    tick()
    check("said once", said() == "before", said())
    here = at(90, 3000, SEVEN)
    status(here[0], here[1], altitude=400)
    tick()
    check("3 km from the shared finds: the Signal box is set to 7", app.signal() == "7", app.signal())
    check("and one line says what is there",
          said() == "Mining location 7 - Iridium 4R, Sapphire 2R (3 finds shared by CMDR Raxxla One, "
                    "9 days ago) - signal 7 picked for you.", said())
    app.say("quiet", A.DIM)
    tick(2)
    check("said once", said() == "quiet" and app.signal() == "7", said())
    listed = words_in(app.deposit_list)
    check("the deposit list shows the shared finds in signal 7",
          any("Iridium" in w and "4R" in w for w in listed) and any("Sapphire" in w for w in listed)
          and any("Raxxla One" in w for w in listed), listed)
    check("and the header counts them as shared, not yours",
          str(app.deposit_header.cget("text")) == "SIGNAL 7  (0)  +3 shared", app.deposit_header.cget("text"))
    card = app.zone_card()
    check("the overlay card carries the number and the top finds",
          card == {"signal": "7", "summary": "Iridium 4R, Sapphire 2R"}, card)
    # Picked in the list: the card on the right is that find's.
    button = next(w for w in _walk(app.deposit_list) if isinstance(w, A.ctk.CTkButton)
                  and "Sapphire" in str(w.cget("text")))
    button.invoke()
    pump(2)
    check("a shared find picked from the list opens its card",
          app.selected and app.selected.get("shared") and app.selected.get("commodity") == "Sapphire"
          and "shared by Raxxla One" in str(app.detail.cget("text")), str(app.detail.cget("text"))[:120])


@section("the app: a number picked by hand stays; another location switches; a target wins")
def _switching():
    app.location_box.set("2")
    app.redraw()
    pump()
    tick()
    check("a number picked by hand while inside the location is left alone", app.signal() == "2", app.signal())
    app.say("moving", A.DIM)
    there = at(0, 2000, THREE)
    status(there[0], there[1], altitude=300)
    tick()
    check("driving into another shared location switches to it", app.signal() == "3", app.signal())
    check("and says what is there",
          said() == "Mining location 3 - Gold 3R (1 find shared by CMDR Other, today) - signal 3 picked for you.",
          said())
    check("the card follows", app.zone_card() == {"signal": "3", "summary": "Gold 3R"}, app.zone_card())
    # Back to 7 with location 9 targeted in the game: the game's target wins.
    app.say("targeting", A.DIM)
    here = at(90, 3000, SEVEN)
    status(here[0], here[1], altitude=400, target="9")
    tick()
    check("with a location targeted in the game, the box follows the game, not the ground",
          app.signal() == "9", app.signal())
    check("the location you are in is still said, without taking the box",
          said() == "Mining location 7 - Iridium 4R, Sapphire 2R (3 finds shared by CMDR Raxxla One, "
                    "9 days ago)", said())
    status(FAR[0], FAR[1], altitude=400)
    tick(2)
    status(here[0], here[1], altitude=400)
    tick()
    check("the target gone, driving back in picks it", app.signal() == "7", app.signal())


@section("the app: your own logged centre beats a shared one; and the dim line when nothing is near")
def _own_and_nothing():
    mine = at(270, 50000)
    app.store.set_location("Ega", "Ega 1", "4", lat=mine[0], lon=mine[1], radius_m=R)
    app.store.add_deposit(system="Ega", body="Ega 1", location="4", commodity="Platinum", rigs="5",
                          amount="High", density="Medium", lat="%.6f" % mine[0], lon="%.6f" % mine[1])
    rows = list(app.shared[("ega", "ega 1")]["rows"])
    rival = at(45, 300, mine)
    rows.append(dict(SHARED_THREE[0], id="shared-rival", location="5", lat="%.6f" % rival[0],
                     lon="%.6f" % rival[1]))
    app.shared[("ega", "ega 1")]["rows"] = rows
    near = at(45, 500, mine)
    status(near[0], near[1], altitude=0)
    tick()
    check("your own centre 500 m off beats a shared find 200 m off", app.signal() == "4", app.signal())
    check("and the line is about yours",
          said() == "Mining location 4 - yours: Platinum 5R - signal 4 picked for you.", said())
    check("the card is yours too", app.zone_card() == {"signal": "4", "summary": "Platinum 5R"},
          app.zone_card())
    app.say("y", A.DIM)
    elsewhere = at(0, 150000)
    status(elsewhere[0], elsewhere[1], altitude=3000)
    tick(2)
    check("over nothing known again: the dim line was said once for this body, and that was it",
          said() == "y" and app.signal() == "4" and app.zone_card() is None, (said(), app.zone_card()))
    # Another body: said again there, once the shared finds are answered.
    app.say("z", A.DIM)
    emit({"timestamp": "2026-10-28T12:30:00Z", "event": "ApproachBody", "StarSystem": "Ega", "Body": "Ega 2"})
    status(elsewhere[0], elsewhere[1], altitude=100, body="Ega 2")
    tick()
    check("on a body whose shared finds have not been answered yet, nothing is said", said() == "z", said())
    app.take_shared(True, json.dumps({"system": "Ega", "body": "Ega 2", "deposits": []}))
    tick()
    check("answered with nothing: the dim line for this body, and the game knows of no locations here",
          said() == "No finds shared within 5 km - the game's signal list has no mining locations for "
                    "this body yet", said())


@section("the overlay: STATUS carries the location you are in")
def _overlay():
    class _Canvas:
        def __init__(self):
            self.calls = []

        def delete(self, *_a):
            self.calls = []

        def __getattr__(self, name):
            def record(*args, **kw):
                self.calls.append((name, args, kw))
            return record

    class _Window:
        def __init__(self, w=380, h=200):
            self.w, self.h = w, h

        def winfo_width(self): return self.w
        def winfo_height(self): return self.h
        def winfo_screenwidth(self): return 1920
        def winfo_screenheight(self): return 1080
        def winfo_x(self): return 100
        def winfo_y(self): return 100

    class _Saver:
        def save_settings(self): pass

    def drew(zone, rows):
        over = OV.Overlay(app=_Saver(), tk_module=None, settings={"overlay_click_through": True})
        panel = OV.Panel(over, OV.STATUS)
        panel.window = _Window()
        panel.canvas = _Canvas()
        over.panels = {OV.STATUS: panel}
        over.draw(rows, 0.0, body="Ega 1", location="7", zone=zone)
        return [str(kw.get("text", "")) for name, _a, kw in panel.canvas.calls if name == "create_text"]

    rows = [{"range_m": 600.0, "bearing": 90.0,
             "deposit": {"id": "shared-1", "system": "Ega", "body": "Ega 1", "location": "7",
                         "commodity": "Iridium", "rigs": "4", "amount": "High", "shared": True}}]
    texts = drew({"signal": "7", "summary": "Iridium 4R, Sapphire 2R"}, rows)
    check("inside one: the STATUS box says which location and its top finds",
          "LOC 7  Iridium 4R, Sapphire 2R" in texts, texts)
    check("in place of the SITE label, not beside it", not any(t.startswith("SITE ") for t in texts), texts)
    texts = drew(None, rows)
    check("outside one, the SITE label as before", any(t.startswith("SITE ") for t in texts)
          and not any(t.startswith("LOC ") for t in texts), texts)
    texts = drew({"signal": "7", "summary": ""}, [])
    check("a location with nothing marked yet is still named", "LOC 7" in texts, texts)
    check("the app hands the card to the overlay",
          "zone=self.zone_card()" in open(A.__file__, encoding="utf-8").read())


if __name__ == "__main__":
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    sys.exit(1 if fails else 0)
