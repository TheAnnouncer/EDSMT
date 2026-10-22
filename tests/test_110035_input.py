"""What 1.10035 adds to how you work the Rhino: a deposit marked from range,
commands typed in the game's chat, joystick and HOTAS buttons, and a long
press of the mouse for a rig.

The maths and the logic are checked as plain functions with every call into
Windows replaced by a stand-in; then each feature is checked on the real
window, driven through a synthetic Status.json and Journal. Every check here
fails if the feature behind it is taken out.

It needs a display (xvfb will do) for the second half and says SKIP, out
loud, for that half without one.

    python tests/test_110035_input.py
"""
import builtins, json, math, os, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-input-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import survey as SV      # noqa: E402
import chattags as CT    # noqa: E402
import inputdev as IND   # noqa: E402
import journal as JN     # noqa: E402

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


def near(a, b, tol):
    return abs(a - b) <= tol


def stamp(offset=0.0):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + offset))


# ---------------------------------------------------------------------------
@section("a bearing as it is typed")
def _bearing():
    cases = {"0": 0.0, "359.9": 359.9, "135": 135.0, "135deg": 135.0, "135°": 135.0,
             "360": 0.0, "90.5": 90.5}
    for text, want in cases.items():
        got = CT.parse_bearing(text)
        check("bearing %r is %s" % (text, want), got is not None and near(got, want, 1e-9), got)
    for text in ("-1", "361", "north", "", None, "1,5", "nan"):
        check("bearing %r is not a bearing" % (text,), CT.parse_bearing(text) is None)
    check("a number is a bearing too", CT.parse_bearing(45) == 45.0 and CT.parse_bearing(True) is None)


@section("a distance as it is typed, in metres or kilometres")
def _distance():
    cases = {"850": 850.0, "850m": 850.0, "850 m": 850.0, "1.2km": 1200.0, "1.2 km": 1200.0,
             "1,200": 1200.0, "1.5": 1500.0, "2KM": 2000.0, "20": 20.0, "3000": 3000.0}
    for text, want in cases.items():
        got = CT.parse_distance(text)
        check("distance %r is %s m" % (text, want), got is not None and near(got, want, 1e-6), got)
    check("a unit typed with the number wins over the unit box",
          CT.parse_distance("5km", "m") == 5000.0 and CT.parse_distance("500m", "km") == 500.0)
    check("a bare number follows the unit box",
          CT.parse_distance("5", "m") == 5.0 and CT.parse_distance("5", "km") == 5000.0
          and CT.parse_distance("5", "auto") == 5000.0 and CT.parse_distance("500", "auto") == 500.0)
    for text in ("0", "-5", "abc", "", None, "10.5km", "10001", "km"):
        check("distance %r is refused" % (text,), CT.parse_distance(text) is None)
    check("10 km exactly is the furthest", CT.parse_distance("10km") == 10000.0)
    check("distances are said the way the app says them",
          CT.distance_words(850) == "850 m" and CT.distance_words(1200) == "1.20 km")


@section("the place: a great-circle destination, across a pole and the date line")
def _place():
    lat, lon = CT.place(0.0, 0.0, 0.0, 1000.0, R)
    check("1 km due north on the equator is 1 km of latitude and no longitude",
          near(lat, math.degrees(1000.0 / R), 1e-7) and near(lon, 0.0, 1e-9), (lat, lon))
    lat, lon = CT.place(0.0, 0.0, 90.0, 1000.0, R)
    check("1 km due east is 1 km of longitude", near(lon, math.degrees(1000.0 / R), 1e-7)
          and near(lat, 0.0, 1e-9), (lat, lon))
    north, west = CT.place(10.0, 20.0, 0.0, 1000.0, R), CT.place(10.0, 20.0, 359.9, 1000.0, R)
    check("bearing 359.9 is a hair west of north, not east of it",
          west[1] < 20.0 < west[1] + 1e-3 and near(west[0], north[0], 1e-6), (north, west))
    check("and 0 and 360 are the same place",
          CT.place(10.0, 20.0, CT.parse_bearing("360"), 800.0, R) == CT.place(10.0, 20.0, 0.0, 800.0, R))
    for bearing in (0.0, 45.0, 90.0, 180.0, 270.0, 359.9):
        point = CT.place(33.0, -120.0, bearing, 2500.0, R)
        back = SV.surface_range_m(33.0, -120.0, point[0], point[1], R)
        away = SV.bearing_deg(33.0, -120.0, point[0], point[1])
        diff = min(abs(away - bearing), 360.0 - abs(away - bearing))
        check("%.1f for 2.5 km lands 2.5 km away on that bearing" % bearing,
              near(back, 2500.0, 0.5) and diff < 0.05, (back, away))
    lat, lon = CT.place(89.999, 10.0, 0.0, 500.0, R)
    check("500 m north from 36 m short of the pole comes out the far side",
          -90.0 < lat < 90.0 and near(lon, -170.0, 0.5)
          and near(SV.surface_range_m(89.999, 10.0, lat, lon, R), 500.0, 0.5), (lat, lon))
    lat, lon = CT.place(-89.999, -30.0, 180.0, 500.0, R)
    check("and over the south pole", -90.0 < lat < 90.0 and near(lon, 150.0, 0.5), (lat, lon))
    lat, lon = CT.place(0.0, 179.9999, 90.0, 1000.0, R)
    check("1 km east across the date line is -179.97, not 180.03",
          -180.0 <= lon <= 180.0 and near(lon, -179.9999 + math.degrees(1000.0 / R) - 0.0002 + 0.0001, 1e-3)
          and lon < 0, (lat, lon))
    lat, lon = CT.place(0.0, -179.9999, 270.0, 1000.0, R)
    check("and west across it is +179.97", lon > 179.0, (lat, lon))
    check("a body with no radius cannot be placed on - the point comes back unchanged, so the app refuses",
          CT.place(5.0, 6.0, 90.0, 1000.0, 0.0) == (5.0, 6.0))


@section("the words after the prefix")
def _words():
    def cmd(text):
        return CT.parse_command(text)
    mark = cmd("!rr alexandrite h/m 4")
    check("a commodity, amount / density and rigs is a mark",
          mark and mark["action"] == "mark" and mark["commodity"] == "Alexandrite"
          and (mark["amount"], mark["density"], mark["rigs"]) == ("High", "Medium", "4"), mark)
    check("and so is the same with the word mark in front",
          cmd("!rr mark alexandrite h/m 4") == mark)
    check("a part of a name long enough to be one commodity will do",
          cmd("!rr alex h/m 4")["commodity"] == "Alexandrite"
          and cmd("!rr bastnasite h/m 4")["commodity"] == "Bastnäsite")
    check("amount alone, or density alone",
          cmd("!rr alex h/")["amount"] == "High" and cmd("!rr alex h/")["density"] == ""
          and cmd("!rr alex /l")["density"] == "Low" and cmd("!rr alex /l")["amount"] == "")
    check("whole words and capitals work", cmd("!RR Alexandrite HIGH/medium 2")["amount"] == "High"
          and cmd("!rr Alexandrite high/medium 2")["density"] == "Medium")
    check("depleted is an amount and not a density",
          cmd("!rr alex d/l")["amount"] == "Depleted" and cmd("!rr alex l/d")["action"] == "error")
    for text, why in (("!rr painite h/m 4", "not a commodity"), ("!rr alex x/m 4", "not an amount"),
                      ("!rr alex h/x 4", "not a density"), ("!rr alex h/m 7", "6 rigs"),
                      ("!rr alex h/m 0", "6 rigs"), ("!rr alex h/m 2 3", "Two rig counts"),
                      ("!rr", "Nothing after"), ("!rr 400 1km alex", "not a bearing"),
                      ("!rr 135 20km alex", "not a distance"), ("!rr rig down 1 2", "One rig"),
                      ("!rr rig down 9", "No rig 9"), ("!rr rig up", "Which rig"), ("!rr rig", "Rig down or rig up")):
        got = cmd(text)
        check("%r is refused: %s" % (text, why), got and got["action"] == "error" and why in got["why"], got)
    check("an unknown commodity is refused, not filed under a made-up name",
          cmd("!rr 90 1km painite h/m 3")["action"] == "error")
    check("a name that could be two is refused and says which",
          "could be" in cmd("!rr hel h/m 4")["why"] and "Helium" in cmd("!rr hel h/m 4")["why"])
    rng = cmd("!rr 135 1.2km alexandrite h/m 4")
    check("a bearing, a distance and a deposit is a range mark",
          rng["action"] == "range" and rng["bearing"] == 135.0 and rng["metres"] == 1200.0
          and rng["commodity"] == "Alexandrite" and rng["rigs"] == "4", rng)
    check("bearing 359.9 and 0 and 360 are all bearings",
          cmd("!rr 359.9 850 alex l/h 2")["bearing"] == 359.9 and cmd("!rr 0 850 alex l/h 2")["bearing"] == 0.0
          and cmd("!rr 360 850 alex l/h 2")["bearing"] == 0.0)
    check("and so is the same with the word range in front",
          cmd("!rr range 135 1.2km alexandrite h/m 4") == rng)
    check("km and m in the message", cmd("!rr 90 850m alex l/l 1")["metres"] == 850.0
          and cmd("!rr 90 1,2km alex l/l 1")["action"] == "error")
    check("rig down 3, rig down, rig up 3, rigs up, centre, undo",
          cmd("!rr rig down 3") == {"action": "rig_down", "rig": 3}
          and cmd("!rr rig down") == {"action": "rig_down", "rig": None}
          and cmd("!rr rig up 3") == {"action": "rig_up", "rig": 3}
          and cmd("!rr rigs up") == {"action": "all_up"}
          and cmd("!rr rig up all") == {"action": "all_up"}
          and cmd("!rr centre") == {"action": "centre"} and cmd("!rr center") == {"action": "centre"}
          and cmd("!rr undo") == {"action": "undo"})
    check("a message that does not start with the prefix is nothing",
          cmd("hello") is None and cmd("o7 !rr undo") is None and cmd("") is None and cmd(None) is None)
    check("the prefix has to be a word of its own", cmd("!rrr undo") is None and cmd("!rrundo") is None)
    check("another prefix, and a blank one falls back to !rr",
          CT.parse_command("!zz undo", "!zz") == {"action": "undo"} and CT.parse_command("!rr undo", "!zz") is None
          and CT.clean_prefix("  ") == "!rr" and CT.clean_prefix("! z z") == "!zz")


@section("a command is fresh, and is not read back from the past")
def _fresh():
    now = 1_800_000_000.0
    note = {"when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 10))}
    check("ten seconds old is fresh", CT.is_fresh(note, now))
    note["when"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 600))
    check("ten minutes old is history", not CT.is_fresh(note, now))
    note["when"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 10))
    check("typed before EDSMT began looking is history however recent",
          not CT.is_fresh(note, now, since=now - 5) and CT.is_fresh(note, now, since=now - 30))
    check("no time on it, no command", not CT.is_fresh({"when": ""}, now) and not CT.is_fresh(None, now))
    check("a SendText becomes a note, anything else does not",
          CT.note_from_event({"event": "SendText", "To": "local", "Message": "x", "Sent": True,
                              "timestamp": "2026-10-01T10:00:00Z"})["sent"] is True
          and CT.note_from_event({"event": "SendText", "Message": "x", "Sent": False})["sent"] is False
          and CT.note_from_event({"event": "SendText", "Message": "x"})["sent"] is True
          and CT.note_from_event({"event": "ReceiveText", "Message": "x"}) is None)


@section("a deposit placed from range says so, and is refined when the spot is reached")
def _notes():
    note = CT.ranged_note("", 135.0, 1200.0)
    check("the note says how far and which way", "Placed from range" in note and "1.20 km" in note
          and "135" in note, note)
    row = {"notes": note}
    check("it is ranged", CT.is_ranged(row) and not CT.is_ranged({"notes": ""}) and not CT.is_ranged(None))
    refined = CT.refined_note(note, 240.0)
    check("and refined once it has been put right", not CT.is_ranged({"notes": refined})
          and "Refined at the spot" in refined and "240 m" in refined, refined)
    again = CT.ranged_note(refined, 10.0, 500.0)
    check("placed from range again after that is ranged again", CT.is_ranged({"notes": again}))


@section("the journal reader keeps only the commander's own chat")
def _journal_chat():
    folder = os.path.join(TMP, "chatlog")
    os.makedirs(folder, exist_ok=True)
    events = [{"timestamp": "2026-10-01T10:00:00Z", "event": "Fileheader", "part": 1, "gameversion": "4.4.1.1"},
              {"timestamp": "2026-10-01T10:00:01Z", "event": "Commander", "Name": "Jameson", "FID": "F1"},
              {"timestamp": "2026-10-01T10:00:02Z", "event": "SendText", "To": "local",
               "Message": "!rr undo", "Sent": True},
              {"timestamp": "2026-10-01T10:00:03Z", "event": "ReceiveText", "From": "CMDR Other",
               "Message": "!rr undo", "Channel": "local"},
              {"timestamp": "2026-10-01T10:00:04Z", "event": "SendText", "To": "wing",
               "Message": "o7", "Sent": False},
              {"timestamp": "2026-10-01T10:00:05Z", "event": "SendText", "To": "squadron", "Message": "hello"}]
    with open(os.path.join(folder, "Journal.2026-10-01T100000.01.log"), "w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")
    watcher = JN.JournalWatcher(folder)
    watcher.poll()
    notes = watcher.drain_chat()
    check("three of the commander's own messages, none of the other commander's",
          [n["message"] for n in notes] == ["!rr undo", "o7", "hello"], notes)
    check("with who it went to, whether it was sent and when",
          [n["to"] for n in notes] == ["local", "wing", "squadron"]
          and [n["sent"] for n in notes] == [True, False, True]
          and notes[0]["when"] == "2026-10-01T10:00:02Z", notes)
    check("taken once", watcher.drain_chat() == [])
    with open(os.path.join(folder, "Journal.2026-10-01T100000.01.log"), "a", encoding="utf-8") as fh:
        for n in range(JN.CHAT_QUEUE_MAX + 40):
            fh.write(json.dumps({"timestamp": "2026-10-01T10:01:00Z", "event": "SendText",
                                 "To": "local", "Message": "m%d" % n}) + "\n")
    watcher.poll()
    got = watcher.drain_chat()
    check("a reader nobody drains cannot grow without end, and keeps the newest",
          len(got) == JN.CHAT_QUEUE_MAX and got[-1]["message"] == "m%d" % (JN.CHAT_QUEUE_MAX + 39), len(got))


# ---------------------------------------------------------------------------
# Joystick buttons
# ---------------------------------------------------------------------------
class FakeReader:
    """The winmm reader's stand-in: a mask per device number (from 0), or None."""
    def __init__(self, masks=None):
        self.masks = dict(masks or {})
        self.calls = []

    def devices(self):
        return IND.MAX_DEVICES

    def __call__(self, device):
        self.calls.append(device)
        return self.masks.get(device)


class FakeWinmm:
    """winmm itself: joyGetNumDevs and joyGetPosEx filling a JOYINFOEX."""
    def __init__(self, buttons):
        self.buttons = dict(buttons)
        self.asked = []

    def joyGetNumDevs(self):
        return 16

    def joyGetPosEx(self, device, ref):
        info = ref._obj
        self.asked.append((device, info.dwSize, info.dwFlags))
        if device not in self.buttons:
            return 167            # JOYERR_UNPLUGGED
        info.dwButtons = self.buttons[device]
        return 0


@section("a joystick button as it is stored")
def _joy_names():
    for text, want in (("JOY1 B7", (1, 7)), ("joy1 b7", (1, 7)), ("Joy16_B32", (16, 32)),
                       (" JOY2   B1 ", (2, 1)), ("JOY3-B12", (3, 12))):
        check("%r is device %d button %d" % (text, want[0], want[1]), IND.parse_joy(text) == want, IND.parse_joy(text))
    for text in ("JOY0 B1", "JOY17 B1", "JOY1 B0", "JOY1 B33", "B7", "ALT+1", "", None, "JOY1", "JOY1 B"):
        check("%r is no button" % (text,), IND.parse_joy(text) is None)
    check("they are stored in one spelling", IND.joy_text(1, 7) == "JOY1 B7"
          and IND.clean_joy("joy1_b7") == "JOY1 B7" and IND.clean_joy("nonsense") == "")
    check("a hotkey has a joystick setting of the same name, hotkey_defaults has none",
          IND.joy_setting("hotkey_rig3") == "joy_rig3" and IND.joy_setting("hotkey_deposit") == "joy_deposit"
          and IND.joy_setting("hotkey_defaults") == "" and IND.joy_setting("nothing") == "")
    check("no action is listed twice", len(set(IND.JOY_ACTIONS)) == len(IND.JOY_ACTIONS))


@section("a press is the moment a button goes down")
def _joy_edges():
    reader = FakeReader({0: 0})
    watcher = IND.JoystickWatcher(reader)
    check("a watcher with a reader is available, without one it is not",
          watcher.available() and not IND.JoystickWatcher.__new__(IND.JoystickWatcher).__dict__.get("reader"))
    check("the first look is the baseline", watcher.new_presses() == [])
    reader.masks[0] = 1 << 6
    check("button 7 goes down: one press", watcher.new_presses() == [(1, 7)])
    check("held, it does not repeat", all(watcher.new_presses() == [] for _ in range(20)))
    reader.masks[0] = 0
    check("let go is not a press", watcher.new_presses() == [])
    reader.masks[0] = 1 << 6
    check("pressed again is another", watcher.new_presses() == [(1, 7)])
    reader.masks[0] = (1 << 6) | (1 << 0) | (1 << 31)
    check("two more at once, in order, button 32 included",
          watcher.new_presses() == [(1, 1), (1, 32)], watcher.new_presses())
    reader.masks[0] = 0xFFFFFFFF
    check("all 32 are readable", len(watcher.new_presses()) == 29)


@section("up to sixteen devices, and one plugged in later")
def _joy_devices():
    reader = FakeReader({0: 0, 15: 0})
    watcher = IND.JoystickWatcher(reader)
    watcher.new_presses()
    reader.masks[15] = 1 << 2
    check("device 16 button 3", watcher.new_presses() == [(16, 3)])
    reader.masks[3] = 1 << 4          # plugged in now, with a button already held
    check("a device that appears holding a button gives no press: it is the baseline",
          watcher.new_presses() == [])
    for _ in range(IND.JoystickWatcher.RESCAN + 2):
        watcher.new_presses()
    reader.masks[3] = (1 << 4) | (1 << 5)
    check("and its next button is one", watcher.new_presses() == [(4, 6)])
    reader.masks.pop(0)
    watcher.new_presses()
    reader.masks[0] = 1 << 1
    for _ in range(IND.JoystickWatcher.RESCAN + 2):
        got = watcher.new_presses()
    check("unplugged and plugged back in holding a button, it is not a press", got == [] or got == [])
    reader.calls.clear()
    for _ in range(40):
        watcher.new_presses()
    absent = [c for c in reader.calls if c in (7, 8, 9)]
    check("an empty slot is asked again every %d looks, not every look" % IND.JoystickWatcher.RESCAN,
          0 < len(absent) < 40 * 3 / 5, len(absent))
    check("none of the sixteen is beyond the list", max(reader.calls) < IND.MAX_DEVICES)


@section("bound buttons run their actions, the rest do nothing")
def _joy_poll():
    reader = FakeReader({0: 0, 1: 0})
    watcher = IND.JoystickWatcher(reader)
    watcher.new_presses()
    bindings = {(1, 7): "deposit", (2, 3): "rig1"}
    reader.masks[0] = 1 << 6
    reader.masks[1] = (1 << 2) | (1 << 8)
    check("the bound ones, by device and button", sorted(watcher.poll(bindings)) == ["deposit", "rig1"])
    reader.masks[0] = 1 << 7
    check("an unbound button is nothing", watcher.poll(bindings) == [])
    watcher.muted = True
    reader.masks[0] = (1 << 7) | (1 << 6)
    check("while Settings listens, nothing runs", watcher.poll(bindings) == [])
    watcher.muted = False
    reader.masks[0] = 1 << 7
    watcher.poll(bindings)
    reader.masks[0] = (1 << 7) | (1 << 6)
    check("and the press that was listened for is gone after", watcher.poll(bindings) == ["deposit"])
    check("a machine with no winmm has no joystick and says so, quietly",
          IND.JoystickWatcher(None).available() is (IND.default_reader() is not None)
          and (os.name == "nt" or IND.default_reader() is None))
    gone = IND.JoystickWatcher(); gone.reader = None
    check("and reads nothing", gone.read() == {} and gone.new_presses() == [] and gone.poll({(1, 1): "x"}) == [])


@section("winmm itself: JOYINFOEX in, buttons out")
def _winmm():
    check("the structure is the 52 bytes winmm expects", __import__("ctypes").sizeof(IND.JOYINFOEX) == 52)
    winmm = FakeWinmm({0: 0b1000001, 2: 1 << 31})
    reader = IND.WinmmReader(winmm)
    check("how many device numbers", reader.devices() == 16)
    check("a device's buttons as a mask", reader(0) == 0b1000001 and reader(2) == 1 << 31)
    check("unplugged is None, not zero", reader(1) is None and reader(15) is None)
    check("asked with the size and the flag for buttons",
          all(size == 52 and flags & IND.JOY_RETURNBUTTONS for _d, size, flags in winmm.asked))
    watcher = IND.JoystickWatcher(reader)
    watcher.new_presses()
    winmm.buttons[0] = 0b1000011
    check("end to end through winmm: button 2 on device 1", watcher.new_presses() == [(1, 2)])

    class Broken:
        def joyGetNumDevs(self):
            raise OSError("no")

        def joyGetPosEx(self, *args):
            raise OSError("no")
    check("a broken winmm is no devices and no buttons, not a crash",
          IND.WinmmReader(Broken()).devices() == 0 and IND.WinmmReader(Broken())(0) is None)


# ---------------------------------------------------------------------------
# A long press of the mouse
# ---------------------------------------------------------------------------
def hold(lp, seconds, button="left", start_ms=0, active=True, mode=None):
    """A press of `seconds`, looked at every 50 ms, then let go. The events
    seen, and the time after the release in ms."""
    if mode:
        lp.mode = mode
    events = []
    lp.step(False, False, active, start_ms / 1000.0)
    ticks = int(round(seconds * 20))
    for i in range(1, ticks + 1):
        ev = lp.step(button == "left", button == "right", active, (start_ms + i * 50) / 1000.0)
        if ev:
            events.append(ev)
    end = start_ms + (ticks + 1) * 50
    lp.step(False, False, active, end / 1000.0)
    return events, end


@section("a long press is a rig, a click is not")
def _longpress():
    check("what each length is: 0.2 s click, 1 s neither, 2.0 s a rig",
          IND.press_kind(0.2) == "click" and IND.press_kind(0.49) == "click"
          and IND.press_kind(0.5) == "between" and IND.press_kind(1.99) == "between"
          and IND.press_kind(2.0) == "rig" and IND.press_kind(9) == "rig")
    check("the figures are the ones asked for", IND.LONG_PRESS_S == 2.0 and IND.CLICK_MAX_S == 0.5)
    lp = IND.LongPress("left")
    seen = {}
    for seconds in (0.1, 0.2, 0.45, 0.5, 0.6, 1.0, 1.5, 1.9):
        events, _ = hold(lp, seconds)
        seen[seconds] = events
    check("a scan click (0.1 to 0.45 s) is never a rig", not any(seen[s] for s in (0.1, 0.2, 0.45)))
    check("0.5 to 1.9 s is neither", not any(seen[s] for s in (0.5, 0.6, 1.0, 1.5, 1.9)), seen)
    events, _ = hold(lp, 2.1)
    check("2.1 s is a rig", events == [("left", False)], events)
    events, _ = hold(lp, 6.0)
    check("held for six seconds it is still one rig, not one every two", events == [("left", False)], events)
    events, _ = hold(lp, 2.1, "right")
    check("the other button is not the rig button", events == [])
    events, end = hold(lp, 2.1, "left", start_ms=0)
    events2, _ = hold(lp, 2.1, "left", start_ms=end)
    check("a second long press is a second rig", len(events) == 1 and len(events2) == 1)


@section("only when the game is in front and the Rhino is out")
def _active():
    lp = IND.LongPress("left")
    events, _ = hold(lp, 3.0, active=False)
    check("not in front, not in the Rhino: nothing", events == [])
    lp = IND.LongPress("left")
    lp.step(False, False, False, 0.0)
    out = []
    for i in range(1, 81):                       # held 4 s, active only from 1.0 s
        out.append(lp.step(True, False, i * 0.05 >= 1.0, i * 0.05))
    check("a press that began while it did not count does not count when it starts to",
          not any(out), out)
    lp = IND.LongPress("left")
    out = []
    lp.step(False, False, True, 0.0)
    for i in range(1, 80):                       # the game loses the front at 1.0 s
        out.append(lp.step(True, False, i * 0.05 < 1.0, i * 0.05))
    check("and one that loses the front part way is dropped", not any(out), out)
    lp = IND.LongPress("left")
    lp.step(False, False, True, 0.0)
    lp.step(True, False, True, 0.05)
    ev = lp.step(True, False, True, 3.0)          # the window was stalled for 3 s
    check("a press across a stall is not trusted: it may have been a different one", ev is None)
    check("the press that follows the stall counts from its own start",
          hold(lp, 2.1, start_ms=4000)[0] == [("left", False)])


@section("which button: left, right, or the first one held")
def _which():
    lp = IND.LongPress("right")
    check("right mode takes the right button", hold(lp, 2.1, "right")[0] == [("right", False)]
          and hold(lp, 2.1, "left", start_ms=10000)[0] == [])
    lp = IND.LongPress("learn")
    check("learn mode watches both until it knows", lp.watching() == ["left", "right"])
    events, end = hold(lp, 2.1, "right")
    check("the first long press is the rig button, and counts as a rig",
          events == [("right", True)] and lp.learned == "right", events)
    check("after that only it counts", hold(lp, 2.1, "left", start_ms=end)[0] == []
          and hold(lp, 2.1, "right", start_ms=end + 5000)[0] == [("right", False)])
    lp = IND.LongPress("learn", "left")
    check("a learned button is kept", lp.watching() == ["left"] and hold(lp, 2.1, "left")[0] == [("left", False)])
    check("a click in learn mode teaches it nothing", IND.LongPress("learn").learned == ""
          and not hold(IND.LongPress("learn"), 0.3)[0])
    check("a stored name that is not a button is ignored", IND.LongPress("learn", "middle").learned == "")


@section("the mouse and the game's window (class and program, never the title) through user32")
def _winmouse():
    class FakeUser32:
        def __init__(self):
            self.down = set()
            self.cls = IND.GAME_WINDOW_CLASS
            self.title = "Elite - Dangerous (CLIENT)"
            self.pid = 777
            self.hwnd = 4242
            self.title_asked = 0

        def GetAsyncKeyState(self, vk):
            return -32768 if vk in self.down else 1       # the low bit alone is "pressed since"

        def GetForegroundWindow(self):
            return self.hwnd

        def GetClassNameW(self, hwnd, buf, size):
            buf.value = self.cls[:size - 1]
            return len(buf.value)

        def GetWindowTextW(self, hwnd, buf, size):
            self.title_asked += 1
            buf.value = self.title[:size - 1]
            return len(buf.value)

        def GetWindowThreadProcessId(self, hwnd, pid_ref):
            pid_ref._obj.value = self.pid
            return 1

    class FakeKernel32:
        def __init__(self):
            self.path = "C:\\Games\\Elite Dangerous\\Products\\elite-dangerous-odyssey-64\\EliteDangerous64.exe"
            self.opened, self.closed, self.deny = [], [], False

        def OpenProcess(self, access, inherit, pid):
            self.opened.append((access, pid))
            return 0 if self.deny else 9000 + pid

        def QueryFullProcessImageNameW(self, handle, flags, buf, size_ref):
            buf.value = self.path
            size_ref._obj.value = len(self.path)
            return 1

        def CloseHandle(self, handle):
            self.closed.append(handle)
            return 1
    fake, kern = FakeUser32(), FakeKernel32()
    mouse = IND.WinMouse(fake, kern)
    check("it is available with a library", mouse.available() and not IND.WinMouse(None, None).available() or os.name == "nt")
    check("neither button down", mouse.buttons() == (False, False))
    fake.down = {IND.VK_LBUTTON}
    check("left down", mouse.buttons() == (True, False))
    fake.down = {IND.VK_RBUTTON}
    check("right down", mouse.buttons() == (False, True))
    fake.down = {IND.VK_LBUTTON, IND.VK_RBUTTON}
    check("both", mouse.buttons() == (True, True))
    check("the game's window class is the game", mouse.elite_in_front())
    check("and it needed no look at a program", not kern.opened)
    fake.title = "Notepad"
    check("whatever the title says", mouse.elite_in_front())
    fake.cls, fake.title = "Notepad", "Elite - Dangerous (CLIENT)"
    kern.path = "C:\\Windows\\notepad.exe"
    check("a window titled like the game, of another class and program, is not the game",
          not mouse.elite_in_front())
    check("the title is never even asked for", fake.title_asked == 0)
    kern.path = "D:\\SteamLibrary\\steamapps\\common\\Elite Dangerous\\Products\\elite-dangerous-odyssey-64\\EliteDangerous64.exe"
    check("the game's program is the game, whatever class the window reports", mouse.elite_in_front())
    kern.path = "C:\\x\\ELITEDANGEROUS32.EXE"
    check("in any case", mouse.elite_in_front())
    kern.path = "C:\\x\\EliteDangerous64.exe.bak"
    check("a file that only starts like it is not", not mouse.elite_in_front())
    kern.path = "C:\\x\\NotEliteDangerous64.exe"
    check("and neither is one that ends like it", not mouse.elite_in_front())
    check("every process handle it opened was closed", len(kern.opened) >= 3 and len(kern.closed) == len(kern.opened))
    kern.path = IND.GAME_PROGRAMS[0]
    kern.deny = True
    check("a program it may not look at is not the game", not mouse.elite_in_front())
    kern.deny = False
    fake.pid = 0
    check("a window with no process is not the game", not mouse.elite_in_front())
    fake.pid = 777
    fake.hwnd = 0
    fake.cls = IND.GAME_WINDOW_CLASS
    check("no window in front is not", not mouse.elite_in_front())
    fake.hwnd = 4242
    nokernel = IND.WinMouse(fake, None) if os.name != "nt" else None
    if nokernel is not None:
        fake.cls = "Notepad"
        check("with no way to ask about programs, the class alone decides", not nokernel.elite_in_front())
        fake.cls = IND.GAME_WINDOW_CLASS
        check("and still finds the game", nokernel.elite_in_front())
    none = IND.WinMouse(None, None)
    if os.name != "nt":
        check("with no user32 nothing is down and the game is never in front",
              none.buttons() == (False, False) and not none.elite_in_front())
    src = open(os.path.join(REPO, "inputdev.py"), encoding="utf-8").read()
    check("the module has no way of reading a window's title",
          "GetWindowText" not in src and "GAME_TITLE" not in src)
    check("nothing about a press is ever written: the module opens no file and imports no logging",
          "open(" not in src.replace("opens no file", "") and "import logging" not in src
          and "write(" not in src and "print(" not in src)


# ---------------------------------------------------------------------------
# The toolkit half: the real window
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
    def wrap(fn):
        if not HAVE_DISPLAY:
            print("== %s ==\n  SKIP  needs a display" % title)
            return fn
        return section(title)(fn)
    return wrap


if HAVE_DISPLAY:
    import customtkinter  # noqa: F401
    import overlay as OV    # noqa: E402
    OV.foreground_is_game = lambda: None
    import edsmt as A       # noqa: E402
    import inputmix as IM   # noqa: E402
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
    app.update_idletasks()

    JOURNAL = os.path.join(JOURNALS, "Journal.2026-10-01T100000.01.log")
    UPLOADS, SAID, FLASHES = [], [], []

    def emit(*events):
        with open(JOURNAL, "a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event) + "\n")

    def status(lat, lon, heading=90, flags=(1 << 21) | (1 << 26)):
        with open(os.path.join(JOURNALS, "Status.json"), "w", encoding="utf-8") as handle:
            json.dump({"timestamp": "2026-10-01T10:00:00Z", "event": "Status",
                       "Flags": flags, "Latitude": lat, "Longitude": lon,
                       "Heading": heading, "BodyName": "Ega 1", "PlanetRadius": R}, handle)

    def move_to(lat, lon):
        status(lat, lon)
        app.game = app.watcher.poll()

    def dest(lat, lon, bearing, metres):
        return SV.destination(lat, lon, bearing, metres, R)

    CLOCK = [-29.0]

    def tell(message, offset=None, sent=True, to="local", event="SendText", **more):
        """The commander types in the game's chat; EDSMT looks. Each message
        gets a second of its own, as typed messages do."""
        if offset is None:
            CLOCK[0] += 1.0
            offset = CLOCK[0]
        row = {"timestamp": stamp(offset), "event": event, "Message": message}
        if event == "SendText":
            row.update(To=to, Sent=sent)
        else:
            row.update(From="CMDR Other", Channel="local")
        row.update(more)
        emit(row)
        app.game = app.watcher.poll()
        app.follow_input()

    def mine():
        return [d for d in app.store.deposits if d["body"] == "Ega 1"]

    def last_said():
        return SAID[-1][0] if SAID else ""

    _real_say, _real_flash = app.say, app.flash

    def _say(text, colour=None):
        SAID.append((text, colour))
        return _real_say(text, colour)

    def _flash(title, detail="", colour=None):
        FLASHES.append((title, detail))
        return _real_flash(title, detail, colour)

    app.say, app.flash = _say, _flash
    app.community.enabled = True
    app.community.base_url = app.community.DEFAULT_URL
    app.community.upload = lambda cmdr, rows: UPLOADS.extend(rows) or True

    emit({"timestamp": stamp(-60), "event": "Fileheader", "gameversion": "4.4.1.1", "part": 1},
         {"timestamp": stamp(-59), "event": "Commander", "Name": "Jameson", "FID": "F1"},
         {"timestamp": stamp(-58), "event": "ApproachBody", "StarSystem": "Ega", "Body": "Ega 1"},
         {"timestamp": stamp(-57), "event": "Scan", "BodyName": "Ega 1", "Radius": R,
          "SurfaceTemperature": 214.5},
         {"timestamp": stamp(-56), "event": "LaunchSRV", "SRVType": "mev_rhino",
          "SRVType_Localised": "SRV Rhino", "ID": 7, "PlayerControlled": True})
    status(*HOME)
    app.settings["rig_offset_m"] = 0
    app.game = app.watcher.poll()
    # Looking began half a minute ago, so a message from the last half minute is live.
    IM.state(app).started_at = time.time() - 30.0


@on_screen("the session the rest of this file runs in")
def _session():
    check("Ega 1, in the Rhino, a position and a radius",
          app.game.body == "Ega 1" and app.game.has_position and app.game.in_rhino
          and app.game.radius_m == R)
    check("a CMDR name from the journal", app.game.cmdr == "Jameson")
    check("the window has the FROM RANGE button, and it has a note", hasattr(app, "btn_range")
          and getattr(app.btn_range, "_edsmt_tip", "") == A.TIPS["range_mark"])
    check("chat commands are off, the prefix is !rr, a long press is off",
          A.DEFAULT_SETTINGS["chat_tags"] is False and A.DEFAULT_SETTINGS["chat_prefix"] == "!rr"
          and A.DEFAULT_SETTINGS["long_press_rig"] is False and A.DEFAULT_SETTINGS["long_press_button"] == "primary")
    check("every key has a joystick setting, blank",
          all(A.DEFAULT_SETTINGS.get(IND.joy_key(a)) == "" for a in IND.JOY_ACTIONS))
    keys = {k[len("hotkey_"):] for k in A.DEFAULT_SETTINGS if k.startswith("hotkey_") and k != "hotkey_defaults"}
    check("the joystick covers every action a hotkey can run, and no other",
          keys == set(IND.JOY_ACTIONS), sorted(keys ^ set(IND.JOY_ACTIONS)))
    wanted = {a for a in A.EDSMT.wanted_hotkeys(dict(A.DEFAULT_SETTINGS, rig_planner=True))}
    check("and the run_hotkeys table runs them all", wanted <= set(IND.JOY_ACTIONS), wanted - set(IND.JOY_ACTIONS))


@on_screen("chat tags: off means nothing, and others' messages are never read")
def _chat_off():
    tell("!rr alexandrite h/m 4")
    check("switched off (the default), a command in the chat does nothing", mine() == [], mine())
    app.settings["chat_tags"] = True
    app.follow_input()
    check("and switching on does not replay what was typed while it was off", mine() == [], mine())
    tell("hello there o7")
    tell("o7 !rr alexandrite h/m 4")
    tell("!rrr alexandrite h/m 4")
    tell("!rr alexandrite h/m 4", sent=False)
    check("a message without the prefix as its own first word, or one the game did not send, is nothing",
          mine() == [], mine())
    tell("!rr alexandrite h/m 4", event="ReceiveText")
    tell("!rr undo", event="ReceiveText")
    check("what another commander types is never read, even word for word", mine() == [], mine())
    check("it is not even queued", app.watcher.pending_chat == [])
    tell("!rr alexandrite h/m 4", offset=-600)
    check("a command from ten minutes ago is history", mine() == [], mine())
    tell("!rr alexandrite h/m 4", offset=-45)
    check("and so is one typed before EDSMT was looking (it started 30 s ago)", mine() == [], mine())
    check("none of that said anything on the status line", not any("Chat tag" in s for s, _c in SAID), SAID[-3:])


@on_screen("chat tags: a deposit marked here")
def _chat_mark():
    before = len(UPLOADS)
    tell("!rr alexandrite h/m 4")
    rows = mine()
    check("the commander's own message marks it", len(rows) == 1, rows)
    row = rows[0] if rows else {}
    check("commodity, rigs, amount and density as typed",
          (row.get("commodity"), row.get("rigs"), row.get("amount"), row.get("density"))
          == ("Alexandrite", "4", "High", "Medium"), row)
    check("where the Rhino is", near(float(row.get("lat") or 0), HOME[0], 1e-5)
          and near(float(row.get("lon") or 0), HOME[1], 1e-5), row)
    check("with the CMDR name from the journal", row.get("cmdr") == "Jameson")
    check("and shared like any mark", len(UPLOADS) == before + 1 and UPLOADS[-1]["type"] == "Alexandrite", UPLOADS[-1:])
    check("a line on the status bar says so, a flash over the game too",
          last_said().startswith("Chat tag: Marked Alexandrite") and FLASHES and "MARKED" in FLASHES[-1][0],
          (last_said(), FLASHES[-1:]))
    tell("!rr alexandrite h/m 4")
    check("the same words again at the same spot is the same deposit, not a second",
          len(mine()) == 1 and "already marked" in last_said(), (len(mine()), last_said()))
    tell("!rr painite h/m 3")
    check("a commodity EDSMT does not know is refused, and nothing is filed under it",
          len(mine()) == 1 and "not a commodity" in last_said(), last_said())
    move_to(*dest(HOME[0], HOME[1], 0, 3000))
    tell("!rr monazite")
    check("with nothing in the message or the boxes, it says what is missing",
          len(mine()) == 1 and "rigs and amount and density" in last_said(), last_said())
    app.fields["rigs"].set("2")
    app.fields["amount"].set("Low")
    app.fields["density"].set("High")
    tell("!rr monazite")
    row = next((d for d in mine() if d["commodity"] == "Monazite"), {})
    check("what the message leaves out is read off the boxes on the rail",
          (row.get("rigs"), row.get("amount"), row.get("density")) == ("2", "Low", "High"), row)
    check("and the boxes it used are emptied for the next one",
          app.fields["rigs"].get() == "" and app.fields["amount"].get() == "")
    tell("!rr diamond h/m 9")
    check("seven rigs do not fit a Rhino", "6 rigs" in last_said() and len(mine()) == 2, last_said())


@on_screen("chat tags: a deposit marked from range")
def _chat_range():
    start = (HOME[0], HOME[1])
    move_to(*dest(HOME[0], HOME[1], 180, 5000))
    here = (app.game.lat, app.game.lon)
    uploads = len(UPLOADS)
    tell("!rr 90 1.2km monazite h/m 3")
    ranged = [d for d in mine() if CT.is_ranged(d)]
    check("a bearing, a distance and a deposit marks one", len(ranged) == 1, [d["notes"] for d in mine()])
    row = ranged[0] if ranged else {"lat": "0", "lon": "0", "notes": ""}
    lat, lon = float(row["lat"]), float(row["lon"])
    check("1.2 km away", near(SV.surface_range_m(here[0], here[1], lat, lon, R), 1200.0, 1.5),
          SV.surface_range_m(here[0], here[1], lat, lon, R))
    check("on a bearing of 90", near(SV.bearing_deg(here[0], here[1], lat, lon), 90.0, 0.05),
          SV.bearing_deg(here[0], here[1], lat, lon))
    check("not where the Rhino is", SV.surface_range_m(here[0], here[1], lat, lon, R) > 1000.0)
    check("it says it was placed from range, in its notes", "Placed from range" in row.get("notes", "")
          and "1.20 km" in row.get("notes", "") and "090" in row.get("notes", ""), row.get("notes"))
    check("and is kept on this machine: nothing was shared", len(UPLOADS) == uploads, UPLOADS[uploads:])
    check("the status line and the overlay say so",
          "placed from range" in last_said() and "FROM RANGE" in FLASHES[-1][0], (last_said(), FLASHES[-1:]))
    check("the signal list was not given a spot it was never at",
          app.store.location("Ega", "Ega 1", app.signal()) is not None)   # from the first mark
    # Bearing 0 / 359.9 / an edge of the maths through the real command.
    for text, bearing in (("0", 0.0), ("359.9", 359.9)):
        before = len(mine())
        move_to(*dest(start[0], start[1], 270, 9000 + int(bearing)))
        here = (app.game.lat, app.game.lon)
        tell("!rr %s 850m ruby l/h 1" % text)
        new = mine()[before:]
        got = SV.bearing_deg(here[0], here[1], float(new[0]["lat"]), float(new[0]["lon"])) if new else -1
        diff = min(abs(got - bearing), 360.0 - abs(got - bearing))
        check("bearing %s: 850 m, and the right way" % text,
              len(new) == 1 and diff < 0.05
              and near(SV.surface_range_m(here[0], here[1], float(new[0]["lat"]), float(new[0]["lon"]), R), 850.0, 1.0),
              (new, got))
        check("it is noted as 0 degrees and 359.9 degrees' own bearing", "%03.0f" % bearing in new[0]["notes"]
              if new else False, new[0]["notes"] if new else "")
    before = len(mine())
    tell("!rr 90 1km painite h/m 3")
    check("an unknown commodity from range is refused too", len(mine()) == before and "not a commodity" in last_said())
    tell("!rr 359.9 850m ruby l/h 1")
    check("the same range mark again is the same deposit, not a second",
          len(mine()) == before and "already marked" in last_said(), (len(mine()) - before, last_said()))
    real_poll = app.watcher.poll
    app.watcher.poll = lambda: (real_poll(), setattr(app.watcher, "radius_m", None))[0]
    try:
        tell("!rr 45 1km osmium h/m 3")
    finally:
        app.watcher.poll = real_poll
        app.game = app.watcher.poll()
    check("a body the game has not sized cannot be placed on, and says so",
          len(mine()) == before and "how big" in last_said(), last_said())
    tell("!rr 45 11km osmium h/m 3")
    check("further than 10 km is a guess, not a reading", len(mine()) == before and "not a distance" in last_said(),
          last_said())


@on_screen("a deposit placed from range is refined by MARK or UPDATE at the spot")
def _refine():
    far = dest(HOME[0], HOME[1], 270, 12000)
    move_to(*far)
    app.fields["commodity"].set("Platinum")
    app.fields["rigs"].set("3")
    app.fields["amount"].set("High")
    app.fields["density"].set("Medium")
    uploads = len(UPLOADS)
    app.mark_from_range(45.0, 900.0)
    ranged = [d for d in mine() if CT.is_ranged(d) and d["commodity"] == "Platinum"]
    check("FROM RANGE marks it with the boxes on the rail", len(ranged) == 1 and ranged[0]["rigs"] == "3"
          and ranged[0]["amount"] == "High", ranged)
    check("and keeps it here", len(UPLOADS) == uploads)
    where = (float(ranged[0]["lat"]), float(ranged[0]["lon"]))
    count = len(mine())
    spot = dest(where[0], where[1], 200, 300)         # drive up: 300 m from where range put it
    move_to(*spot)
    app.fields["commodity"].set("Platinum")
    app.fields["rigs"].set("")
    app.fields["amount"].set("Medium")
    app.fields["density"].set("")
    app.mark_deposit()
    rows = [d for d in mine() if d["commodity"] == "Platinum"]
    check("MARK DEPOSIT 300 m from it refines it: still one Platinum", len(rows) == 1 and len(mine()) == count, rows)
    row = rows[0] if rows else {}
    check("it is now where the Rhino is", near(float(row.get("lat") or 0), spot[0], 1e-5)
          and near(float(row.get("lon") or 0), spot[1], 1e-5), row)
    check("no longer ranged, and the notes keep both lines",
          not CT.is_ranged(row) and "Placed from range" in row["notes"] and "Refined at the spot" in row["notes"]
          and "300 m" in row["notes"], row.get("notes"))
    check("what the boxes said went onto it, what they left blank did not",
          row.get("amount") == "Medium" and row.get("rigs") == "3" and row.get("density") == "Medium", row)
    check("and only now was it shared", len(UPLOADS) == uploads + 1 and UPLOADS[-1]["type"] == "Platinum"
          and near(UPLOADS[-1]["lat"], spot[0], 1e-5), UPLOADS[uploads:])
    check("the status line says it was refined", "now where you are" in last_said() and "REFINED" in FLASHES[-1][0],
          (last_said(), FLASHES[-1:]))
    app.mark_deposit()
    check("MARK again there is the ordinary 'already marked' question, not a second refinement",
          "already marked" in last_said() or "UPDATE" in last_said(), last_said())
    # The same through UPDATE.
    far2 = dest(HOME[0], HOME[1], 90, 14000)
    move_to(*far2)
    app.fields["commodity"].set("Gold")
    app.fields["rigs"].set("2")
    app.fields["amount"].set("High")
    app.fields["density"].set("High")
    app.mark_from_range(0.0, 700.0)
    gold = [d for d in mine() if d["commodity"] == "Gold"][0]
    spot = dest(float(gold["lat"]), float(gold["lon"]), 90, 150)
    move_to(*spot)
    app.fields["commodity"].set("Gold")
    app.fields["amount"].set("Low")
    uploads = len(UPLOADS)
    app.update_deposit_here()
    gold = [d for d in mine() if d["commodity"] == "Gold"]
    check("UPDATE 150 m from it refines it as well", len(gold) == 1 and not CT.is_ranged(gold[0])
          and near(float(gold[0]["lat"]), spot[0], 1e-5) and gold[0]["amount"] == "Low", gold)
    check("and shares it", len(UPLOADS) == uploads + 1)
    # More than a kilometre away it is somebody else's deposit.
    far3 = dest(HOME[0], HOME[1], 0, 16000)
    move_to(*far3)
    for name, value in (("commodity", "Ruby"), ("rigs", "2"), ("amount", "High"), ("density", "High")):
        app.fields[name].set(value)
    app.mark_from_range(180.0, 800.0)
    ruby = [d for d in mine() if d["commodity"] == "Ruby" and CT.is_ranged(d)]
    drive = dest(float(ruby[0]["lat"]), float(ruby[0]["lon"]), 90, 1500)
    move_to(*drive)
    for name, value in (("commodity", "Ruby"), ("rigs", "2"), ("amount", "High"), ("density", "High")):
        app.fields[name].set(value)
    count = len(mine())
    app.mark_deposit()
    check("1.5 km from it, MARK is a new deposit and the ranged one stays where it was",
          len(mine()) == count + 1 and any(CT.is_ranged(d) for d in mine() if d["commodity"] == "Ruby"),
          [(d["commodity"], CT.is_ranged(d)) for d in mine() if d["commodity"] == "Ruby"])
    # Standing on a deposit that was marked at its spot is the deposit being talked about.
    base = dest(HOME[0], HOME[1], 135, 18000)
    move_to(*base)
    for name, value in (("commodity", "Silver"), ("rigs", "2"), ("amount", "High"), ("density", "High")):
        app.fields[name].set(value)
    app.mark_deposit()
    for name, value in (("commodity", "Silver"), ("rigs", "2"), ("amount", "High"), ("density", "High")):
        app.fields[name].set(value)
    app.mark_from_range(0.0, 600.0)
    for name, value in (("commodity", "Silver"), ("rigs", "2"), ("amount", "High"), ("density", "High")):
        app.fields[name].set(value)
    app.fields["amount"].set("Low")
    app.update_deposit_here()
    silver = [d for d in mine() if d["commodity"] == "Silver"]
    check("UPDATE on a deposit marked at its spot updates that one and leaves the ranged one alone",
          len(silver) == 2 and sum(1 for d in silver if CT.is_ranged(d)) == 1
          and [d["amount"] for d in silver if not CT.is_ranged(d)] == ["Low"], silver)


@on_screen("a command that fails does not take the next one with it")
def _isolated():
    base = dest(HOME[0], HOME[1], 100, 21000)
    move_to(*base)
    real = app.drop_rigs
    broke = []
    app.trouble = lambda stage, exc: broke.append((stage, str(exc)))

    def boom(n=None):
        raise RuntimeError("rig trouble")
    app.drop_rigs = boom
    try:
        app.settings["chat_tags"] = True
        emit({"timestamp": stamp(70), "event": "SendText", "To": "local", "Message": "!rr rig down 1", "Sent": True},
             {"timestamp": stamp(71), "event": "SendText", "To": "local", "Message": "!rr diamond h/m 2", "Sent": True})
        app.game = app.watcher.poll()
        app.follow_input()
    finally:
        app.drop_rigs = real
        del app.trouble
    check("the failure is named, and the next command still ran",
          broke == [("Chat command", "rig trouble")] and any(d["commodity"] == "Diamond" for d in mine()), broke)


@on_screen("a deposit placed from range is never shared by an edit either")
def _no_share():
    row = [d for d in mine() if CT.is_ranged(d)][0]
    uploads = len(UPLOADS)
    app.share(row)
    check("share() will not send a deposit that is still ranged", len(UPLOADS) == uploads)
    app.deposit_edited(row["id"], {"amount": "Low"})
    check("nor will correcting it", len(UPLOADS) == uploads)
    plain = dict(row, notes="")
    app.share(plain)
    check("the same row without the note goes", len(UPLOADS) == uploads + 1)


@on_screen("chat tags: rigs, the centre, and undo")
def _chat_rigs():
    base = dest(HOME[0], HOME[1], 45, 20000)
    move_to(*base)
    tell("!rr rig down 3")
    check("rig down 3 puts rig 3 down", [r["n"] for r in app._rigs_here()] == [3], app._rigs_here())
    check("with the usual line", "Rig 3" in last_said(), last_said())
    move_to(*dest(base[0], base[1], 90, 100))
    tell("!rr rig down")
    check("rig down alone is the next free one", sorted(r["n"] for r in app._rigs_here()) == [1, 3],
          app._rigs_here())
    tell("!rr rig up 3")
    check("rig up 3 takes it up", sorted(r["n"] for r in app._rigs_here()) == [1], app._rigs_here())
    tell("!rr rigs up")
    check("rigs up takes them all", app._rigs_here() == [])
    tell("!rr rig down 9")
    check("a rig that does not exist is said, not done", "No rig 9" in last_said() and app._rigs_here() == [])
    cmap = app.track_survey(app.game)
    tell("!rr centre")
    check("centre sets the survey centre here", cmap.centre and near(cmap.centre[0], app.game.lat, 1e-6), cmap.centre)
    flashed = len(FLASHES)
    tell("!rr rig down 2")
    check("and what a rig key would flash, this flashes", len(FLASHES) > flashed)
    for row in list(mine()):
        app.store.remove_deposit(row["id"])
    old = app.store.add_deposit(system="Ega", body="Ega 1", location="1", commodity="Water", rigs="1",
                                amount="High", density="High", lat="1", lon="1",
                                recorded=stamp(-7200), cmdr="Jameson")
    tell("!rr undo")
    check("undo will not reach back to a deposit marked two hours ago",
          any(d["id"] == old["id"] for d in mine()) and "last 10 minutes" in last_said(), last_said())
    move_to(*dest(base[0], base[1], 0, 3000))
    tell("!rr alexandrite h/m 4")
    move_to(*dest(base[0], base[1], 0, 6000))
    tell("!rr monazite h/m 4")
    names = sorted(d["commodity"] for d in mine())
    check("two deposits marked, and the old one", names == ["Alexandrite", "Monazite", "Water"], names)
    tell("!rr undo")
    names = sorted(d["commodity"] for d in mine())
    check("undo takes back the last one marked, and only that one",
          names == ["Alexandrite", "Water"] and "Took back Monazite" in last_said(), (names, last_said()))
    tell("!rr undo")
    names = sorted(d["commodity"] for d in mine())
    check("undo again takes back the one before, and then there is nothing recent to take",
          names == ["Water"] and "Took back Alexandrite" in last_said(), (names, last_said()))
    tell("!rr undo")
    check("and the two-hour-old one is still there", [d["commodity"] for d in mine()] == ["Water"]
          and "last 10 minutes" in last_said(), last_said())
    app.store.remove_deposit(old["id"])


@on_screen("chat tags: the prefix is the commander's to change")
def _prefix():
    base = dest(HOME[0], HOME[1], 225, 22000)
    move_to(*base)
    app.settings["chat_prefix"] = "!zz"
    tell("!rr sapphire h/m 2")
    check("the old prefix does nothing now", not any(d["commodity"] == "Sapphire" for d in mine()))
    tell("!zz sapphire h/m 2")
    check("the new one marks", any(d["commodity"] == "Sapphire" for d in mine()))
    app.settings["chat_prefix"] = "  "
    tell("!rr ruby h/m 2")
    check("a blank prefix falls back to the default", any(d["commodity"] == "Ruby" for d in mine()
                                                           if SV.surface_range_m(base[0], base[1], float(d["lat"]),
                                                                                 float(d["lon"]), R) < 5))
    app.settings["chat_prefix"] = "!rr"
    note = {"when": stamp(+90), "message": "!rr centre", "sent": True}
    first = IM.handle_chat(app, note)
    second = IM.handle_chat(app, dict(note))
    check("a line the journal hands over twice (a re-read after Save) runs once",
          first == "centre" and second is None, (first, second))
    check("the dedupe list is capped", len(IM.state(app).seen) <= IM.SEEN_MAX)


@on_screen("FROM RANGE: the window")
def _window():
    base = dest(HOME[0], HOME[1], 315, 24000)
    move_to(*base)
    for name in ("commodity", "rigs", "amount", "density"):
        app.fields[name].set("")
    win = A.RangeMarkWindow(app)
    app.update_idletasks()
    check("it opens, and says what the boxes hold", "Fill in the boxes" in win.summary.cget("text"),
          win.summary.cget("text"))
    for name, value in (("commodity", "Titanium"), ("rigs", "5"), ("amount", "Medium"), ("density", "Low")):
        app.fields[name].set(value)
    win.destroy()
    win = A.RangeMarkWindow(app)
    check("with the boxes full it lists them",
          "Titanium" in win.summary.cget("text") and "5 rigs" in win.summary.cget("text"), win.summary.cget("text"))
    count = len(mine())
    for bearing, distance in (("400", "850"), ("abc", "850"), ("90", "0"), ("90", "far"), ("90", "11 km"), ("", "")):
        win.bearing.delete(0, "end"); win.bearing.insert(0, bearing)
        win.distance.delete(0, "end"); win.distance.insert(0, distance)
        win.place()
        check("bearing %r distance %r marks nothing, and the window says why" % (bearing, distance),
              len(mine()) == count and win.status.cget("text") != "", win.status.cget("text"))
    win.bearing.delete(0, "end"); win.bearing.insert(0, "359.9")
    win.distance.delete(0, "end"); win.distance.insert(0, "1.2")
    win.unit.set("km")
    win.place()
    row = (mine()[count:] or [{}])[0]
    check("359.9 and 1.2 km marks one", len(mine()) == count + 1 and row.get("commodity") == "Titanium", row)
    check("1.2 km away", near(SV.surface_range_m(base[0], base[1], float(row.get("lat") or 0),
                                                 float(row.get("lon") or 0), R), 1200.0, 1.5))
    check("and the window has closed", not win.winfo_exists())
    for name, value in (("commodity", "Titanium"), ("rigs", "5"), ("amount", "Medium"), ("density", "Low")):
        app.fields[name].set(value)
    win = A.RangeMarkWindow(app)
    win.bearing.insert(0, "90")
    win.distance.insert(0, "850")
    win.unit.set("m")
    win.place()
    row = (mine()[count + 1:] or [{}])[0]
    check("850 with the unit box on m is 850 m", near(SV.surface_range_m(
        base[0], base[1], float(row.get("lat") or 0), float(row.get("lon") or 0), R), 850.0, 1.5), row)
    app._range_window = None
    app.btn_range.invoke()
    check("the button on the rail opens the window",
          app._range_window is not None and app._range_window.winfo_exists())
    first = app._range_window
    app.open_range_window()
    check("pressing it twice leaves one window", not first.winfo_exists() and app._range_window.winfo_exists())
    app._range_window.destroy()


class FakeMouse:
    """The mouse and the game's window, as WinMouse would answer."""
    def __init__(self):
        self.left = self.right = False
        self.front = True

    def available(self):
        return True

    def buttons(self):
        return self.left, self.right

    def elite_in_front(self):
        return self.front


@on_screen("joystick buttons run the actions the keys run")
def _joy_app():
    st = IM.state(app)
    reader = FakeReader({0: 0, 1: 0})
    st.joystick = IND.JoystickWatcher(reader)
    scheduled = []
    app.after = lambda ms, fn=None, *rest: scheduled.append((ms, fn)) or "id%d" % len(scheduled)
    try:
        app.settings.update({IND.joy_key(a): "" for a in IND.JOY_ACTIONS})
        st.joy_after = None
        app.follow_input()
        check("with no button bound there is no timer at all", st.joy_after is None and not scheduled, scheduled)
        app.settings["joy_rigs"] = "JOY1 B7"
        app.settings["joy_allup"] = "JOY2 B3"
        app.settings["joy_trace"] = "JOY1 B9"
        app.follow_input()
        check("with one bound, a timer every %d ms" % IND.POLL_MS, len(scheduled) == 1 and scheduled[0][0] == IND.POLL_MS,
              scheduled)
        app.follow_input()
        check("and only the one, however often the tick asks", len(scheduled) == 1)
        check("every bound button is live, the rig planner's too (it is out of beta)",
              IM.joystick_bindings(app) == {(1, 7): "rigs", (2, 3): "allup", (1, 9): "trace"},
              IM.joystick_bindings(app))
        app.hotkeys.drain()
        move_to(*dest(HOME[0], HOME[1], 45, 26000))
        IM.joystick_tick(app)                  # the baseline look
        reader.masks[0] = 1 << 6
        IM.joystick_tick(app)
        check("button 7 on device 1 is the next-free-rig key", app.hotkeys.drain() == ["rigs"])
        for _ in range(30):
            IM.joystick_tick(app)
        check("held for 30 looks (1.5 s) it does not repeat", app.hotkeys.drain() == [])
        reader.masks[0] = 0
        IM.joystick_tick(app)
        reader.masks[0] = 1 << 6
        IM.joystick_tick(app)
        check("let go and pressed again is another", app.hotkeys.drain() == ["rigs"])
        reader.masks[0] = (1 << 6) | (1 << 5)
        reader.masks[1] = 1 << 2
        IM.joystick_tick(app)
        check("another device's bound button runs its own", app.hotkeys.drain() == ["allup"])
        check("it keeps asking to be called again while a button is bound", scheduled[-1][0] == IND.POLL_MS
              and st.joy_after is not None)
        reader.masks[0] = 0
        IM.joystick_tick(app)
        reader.masks[0] = 1 << 6
        IM.joystick_tick(app)
        before = len(app._rigs_here())
        app.run_hotkeys()
        check("and the key's own code runs it: a rig is down where the Rhino is",
              len(app._rigs_here()) == before + 1, app._rigs_here())
        app.settings["joy_rigs"] = app.settings["joy_allup"] = app.settings["joy_trace"] = ""
        IM.joystick_tick(app)
        check("take the buttons away and the timer stops", st.joy_after is None)
        st.joystick.muted = True
        app.settings["joy_rigs"] = "JOY1 B7"
        app.follow_input()
        reader.masks[0] = 0
        IM.joystick_tick(app)
        reader.masks[0] = 1 << 6
        IM.joystick_tick(app)
        check("while Settings is listening, the timer runs but nothing is pressed", app.hotkeys.drain() == []
              and st.joy_after is not None)
        st.joystick.muted = False
        app.settings["joy_rigs"] = ""
    finally:
        del app.after


@on_screen("a long press of the fire button is a rig")
def _mouse_app():
    # 1.10036: the button is the game's own SRV fire binding (gamebinds.py),
    # here the game's defaults - Primary fire the left mouse button,
    # Secondary fire the right - read through a stand-in for Windows.
    st = IM.state(app)
    mouse = FakeMouse()
    st.mouse = mouse

    class Keys:
        def key_down(self, vk):
            return (vk == 0x01 and mouse.left) or (vk == 0x02 and mouse.right)

        def joy_mask(self, index):
            return None

        def joy_ids(self, index):
            return None
    st.reader = IM.GB.BindReader(Keys())
    st.binds = {"file": "Custom.4.2.binds", "preset": "Custom", "why": "",
                "primary": [{"device": "Mouse", "key": "Mouse_1", "modifiers": []}],
                "secondary": [{"device": "Mouse", "key": "Mouse_2", "modifiers": []}]}
    clock = [1000.0]
    st.clock = lambda: clock[0]
    st.binds_at = clock[0] + 10 ** 6       # read once; not again during the test
    scheduled = []
    app.after = lambda ms, fn=None, *rest: scheduled.append((ms, fn)) or "id%d" % len(scheduled)
    app.settings.update(long_press_rig=False, long_press_button="primary", long_press_learned="")

    def look():
        IM.mouse_tick(app)

    def press_for(seconds, left=True, right=False):
        mouse.left, mouse.right = False, False
        clock[0] += 0.05
        look()
        mouse.left, mouse.right = left, right
        for _ in range(int(round(seconds * 20))):
            clock[0] += 0.05
            look()
        mouse.left, mouse.right = False, False
        clock[0] += 0.05
        look()
        return app.hotkeys.drain()
    try:
        st.mouse_after = None
        app.follow_input()
        check("with the switch off there is no timer", not scheduled and st.mouse_after is None)
        app.settings["long_press_rig"] = True
        game_flag, app.game.in_srv = app.game.in_srv, False
        app.follow_input()
        app.game.in_srv = game_flag
        check("on with the switch but not in the Rhino there is none either", not scheduled and st.mouse_after is None)
        app.follow_input()
        st.mouse_after = None
        del scheduled[:]
        mouse.left = True
        app.follow_input()
        look()
        held_in = st.hold._ignore and st.hold._since is None
        mouse.left = False
        look()
        check("fire already held on the way into the Rhino is not the start of a press", held_in,
              (st.hold._ignore, st.hold._since))
        st.mouse_after = None
        del scheduled[:]
        app.follow_input()
        check("in the Rhino with it on, a timer every %d ms" % IND.POLL_MS,
              len(scheduled) == 1 and scheduled[0][0] == IND.POLL_MS, scheduled)
        app.follow_input()
        check("only one", len(scheduled) == 1)
        check("a click does not place a rig", press_for(0.2) == [])
        check("0.4 s does not", press_for(0.4) == [])
        check("1 s is neither", press_for(1.0) == [])
        check("1.9 s is not a rig", press_for(1.9) == [])
        check("2.1 s is a rig, the same as the rig-down key (the next free rig)", press_for(2.1) == ["rigs"])
        mouse.left = True
        events = []
        for _ in range(100):
            clock[0] += 0.05
            look()
            events += app.hotkeys.drain()
        mouse.left = False
        clock[0] += 0.05
        look()
        check("held for five seconds it is one rig and does not repeat", events == ["rigs"], events)
        check("Secondary fire, with Primary chosen, is not the rig button",
              press_for(2.5, left=False, right=True) == [])
        mouse.front = False
        check("with the game not in front, a long press is nothing", press_for(3.0) == [])
        mouse.front = True
        mouse.left = True
        clock[0] += 0.05
        look()
        mouse.front = False
        for _ in range(10):
            clock[0] += 0.05
            look()
        mouse.front = True
        out = []
        for _ in range(60):
            clock[0] += 0.05
            look()
            out += app.hotkeys.drain()
        mouse.left = False
        clock[0] += 0.05
        look()
        check("a press that began behind another window does not count when the game comes back", out == [], out)
        app.settings["long_press_button"] = "secondary"
        check("Secondary fire chosen: its binding places a rig", press_for(2.1, left=False, right=True) == ["rigs"]
              and press_for(2.1) == [])
        app.settings["long_press_button"] = "right"
        check("an older 'right' reads as Secondary fire", press_for(2.1, left=False, right=True) == ["rigs"])
        app.settings["long_press_button"] = "primary"
        st.binds = dict(st.binds, primary=[{"device": "Keyboard", "key": "Key_K", "modifiers": []}])
        check("bound to a key in the game, the mouse is not the rig button", press_for(2.1) == [])
        st.binds = {"file": "", "preset": "", "why": "The game's binds were not found on this PC.",
                    "primary": [], "secondary": []}
        check("no binds on this PC: the game's default, the left button", press_for(2.1) == ["rigs"])
        # Nothing is written down.
        written = []
        real_open = builtins.open

        def spy(path, mode="r", *a, **k):
            if any(c in str(mode) for c in "wax+"):
                written.append(str(path))
            return real_open(path, mode, *a, **k)
        builtins.open = spy
        try:
            press_for(2.6)
            press_for(0.3)
        finally:
            builtins.open = real_open
        check("not one file is opened for writing while a press is timed", written == [], written)
        app.settings["long_press_rig"] = False
        look()
        check("switch it off and the timer stops", st.mouse_after is None)
        app.settings["long_press_rig"] = True
        app.game.in_srv = False
        look()
        check("leave the Rhino and it stops", st.mouse_after is None)
        placed = press_for(2.1)
        app.game.in_srv = game_flag
        check("a press after that, out of the Rhino, is nothing", placed == [])
    finally:
        del app.after
        app.settings["long_press_rig"] = False
        app.settings.update(long_press_button="primary", long_press_learned="")
        st.binds = None


@on_screen("Settings: the chat switch, the prefix, the long press and a Joystick button on every key")
def _settings():
    win = A.SettingsWindow(app)
    app.update_idletasks()
    said, saved = [], []
    win.say = lambda text, colour=None: said.append(text)
    real_apply = app.apply_settings
    app.apply_settings = lambda data: saved.append(dict(data))
    try:
        for key in ("chat_tags", "long_press_rig"):
            check("a switch for %s, with its note" % key, key in win.toggles and key in A.SETTING_TIPS, key)
        check("a box for the prefix, holding !rr", "chat_prefix" in win.fields
              and win.fields["chat_prefix"].get() == "!rr", win.fields.get("chat_prefix"))
        check("and a choice of rig button: the game's Primary or Secondary fire, nothing else",
              "long_press_button" in win.choices and [n for n, _v in win.choices["long_press_button"][1]]
              == ["Primary fire", "Secondary fire"])
        check("with a line saying what the binds make it", win.binds_line.cget("text").startswith(
            ("From your binds", "The game's binds")), win.binds_line.cget("text"))
        check("a Joystick button beside every key, for every action",
              set(win.joy_binders) == {IND.joy_key(a) for a in IND.JOY_ACTIONS}
              and set(win.joy_binders) == {IND.joy_setting(k) for k in win.binders if IND.joy_setting(k)},
              set(win.joy_binders) ^ {IND.joy_key(a) for a in IND.JOY_ACTIONS})
        check("each with a note", all(getattr(b, "_edsmt_tip", "") for b in win.joy_binders.values()))
        # Capture, with a stand-in stick.
        st = IM.state(app)
        reader = FakeReader({0: 0})
        st.joystick = IND.JoystickWatcher(reader)
        win._capture_joy("joy_deposit")
        check("click: it listens, says so, and holds the app's own timer",
              win._joy_capturing == "joy_deposit" and st.joystick.muted
              and win.joy_binders["joy_deposit"].cget("text") == "press a button...", win.joy_binders["joy_deposit"].cget("text"))
        reader.masks[0] = 1 << 6
        win._joy_poll()
        check("press button 7: it is bound, and the app's timer is released",
              win.joy_bindings["joy_deposit"] == "JOY1 B7" and not st.joystick.muted
              and win.joy_binders["joy_deposit"].cget("text") == "JOY1 B7" and win._joy_capturing is None,
              win.joy_bindings["joy_deposit"])
        reader.masks[0] = 0
        win._capture_joy("joy_update")
        reader.masks[0] = 1 << 6
        win._joy_poll()
        check("the same button for a second action is refused",
              win.joy_bindings["joy_update"] == "" and "already doing something else" in said[-1], said[-1])
        win._capture_joy("joy_update")
        reader.masks[0] = (1 << 6) | (1 << 31)
        win._joy_poll()
        check("a button already held when the click came is not the one: the new press is",
              win.joy_bindings["joy_update"] == "JOY1 B32", win.joy_bindings["joy_update"])
        win._capture_joy("joy_rig1")
        win._joy_done(None)
        check("Escape cancels and leaves it as it was", win.joy_bindings["joy_rig1"] == ""
              and win._joy_capturing is None and not st.joystick.muted and "as it was" in said[-1])
        win._capture_joy("joy_rig1")
        win._joy_ticks = IND.JOY_CAPTURE_S * 1000 // IND.POLL_MS
        win._joy_poll()
        check("and so does ten seconds of nothing", win._joy_capturing is None and not st.joystick.muted
              and win.joy_bindings["joy_rig1"] == "")
        st.joystick = IND.JoystickWatcher(FakeReader({}))
        win._capture_joy("joy_rig1")
        check("no stick plugged in: it says so and listens to nothing", win._joy_capturing is None
              and "No joystick" in said[-1], said[-1])
        st.joystick = IND.JoystickWatcher(None)
        st.joystick.reader = None
        win._capture_joy("joy_rig1")
        check("no winmm (not Windows): clean refusal", win._joy_capturing is None and "Windows only" in said[-1], said[-1])
        # Save.
        win.save()
        check("Save keeps the joystick buttons in settings, in the stored spelling",
              saved and saved[-1]["joy_deposit"] == "JOY1 B7" and saved[-1]["joy_update"] == "JOY1 B32"
              and saved[-1]["joy_rig1"] == "", saved[-1:] and {k: v for k, v in saved[-1].items() if k.startswith("joy_") and v})
        win._set_joy("joy_rig1", "JOY1 B7")
        n = len(saved)
        win.save()
        check("two actions on one button are refused at Save", len(saved) == n and "two things at once" in said[-1], said[-1])
        win._set_joy("joy_rig1", "")
        # Reset clears the button along with the key.
        win._reset_binding("hotkey_deposit", A.DEFAULT_SETTINGS["hotkey_deposit"])
        check("Reset on a key row clears its joystick button too", win.joy_bindings["joy_deposit"] == ""
              and win.joy_binders["joy_deposit"].cget("text") == "Joystick")
        # The chat prefix.
        for typed, ok, kept in (("!zz", True, "!zz"), ("x", False, None), ("a" * 13, False, None),
                                ("! q", True, "!q"), ("", True, "!rr")):
            win.fields["chat_prefix"].delete(0, "end")
            win.fields["chat_prefix"].insert(0, typed)
            n = len(saved)
            win.save()
            check("a prefix of %r is %s" % (typed, "saved as %r" % kept if ok else "refused"),
                  (len(saved) > n) == ok and (not ok or saved[-1]["chat_prefix"] == kept)
                  and (ok or "2 to 12 characters" in said[-1]), (typed, said[-1], saved[-1]["chat_prefix"]))
        win.choices["long_press_button"][0].set("Secondary fire")
        win.save()
        check("Secondary fire is saved as such, and nothing is learned",
              saved[-1]["long_press_button"] == "secondary" and saved[-1]["long_press_learned"] == "")
        win.choices["long_press_button"][0].set("Primary fire")
        win.save()
        check("and Primary fire", saved[-1]["long_press_button"] == "primary")
        win.toggles["chat_tags"].set(True)
        win.toggles["long_press_rig"].set(True)
        win.save()
        check("the switches are saved", saved[-1]["chat_tags"] is True and saved[-1]["long_press_rig"] is True)
    finally:
        app.apply_settings = real_apply
        win.destroy()
        app.settings.update(chat_tags=False, chat_prefix="!rr", long_press_rig=False)


@on_screen("the pieces are wired, not just written")
def _wired():
    src = open(os.path.join(REPO, "edsmt.py"), encoding="utf-8").read()

    def method(cls, name):
        body = src.split("class %s(" % cls, 1)[1]
        body = body.split("\n    def %s(" % name, 1)[1]
        return body.split("\n    def ", 1)[0]
    check("MARK DEPOSIT tries to refine first", "self.refine_ranged(commodity)" in method("EDSMT", "mark_deposit"))
    check("so does UPDATE", "self.refine_ranged(commodity)" in method("EDSMT", "update_deposit_here"))
    check("share() will not send a ranged deposit", "CT.is_ranged(record)" in method("EDSMT", "share"))
    check("the tick looks at the input every time", "self.follow_input()" in method("EDSMT", "tick"))
    check("the journal reader queues SendText and nothing else of the chat",
          'name == "SendText"' in open(os.path.join(REPO, "journal.py"), encoding="utf-8").read()
          and '"ReceiveText"' not in open(os.path.join(REPO, "journal.py"), encoding="utf-8").read())
    check("the joystick and the long press queue the hotkeys' own action names, so one table runs them",
          "events.put(action)" in open(os.path.join(REPO, "inputmix.py"), encoding="utf-8").read()
          and 'press(app, "rigs")' in open(os.path.join(REPO, "inputmix.py"), encoding="utf-8").read())
    check("the specs name the modules",
          all(all(m in open(os.path.join(REPO, "build", f), encoding="utf-8").read()
                  for m in ('"chattags"', '"inputdev"', '"inputmix"'))
              for f in ("EDSMT.spec", "EDSMT-onefile.spec")))
    check("no clash between an action and a hotkey nobody can bind: every joy_ key is blank in a fresh file",
          not [k for k, v in A.DEFAULT_SETTINGS.items() if k.startswith("joy_") and v])


if HAVE_DISPLAY:
    try:
        app.destroy()
    except Exception:
        pass

if __name__ == "__main__":
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    sys.exit(1 if fails else 0)
