"""1.10040 (#145, #146, #152, #153, #292): Voice Mode, spoken directions,
the proximity sonar and a VoiceAttack profile.

The first half needs no display: the sonar's curve and its player, the
target the scope already points at, the line table, the words for a
direction and when they are said, the speaker driven by a stand-in process
(one process for every line, killed at exit), a recording before the spoken
line, the VoiceAttack profile for the default keys and for keys of the
commander's own, and the app saying its events. The second half drives the
Settings controls on the real toolkit under xvfb.

    python tests/test_110040_voice.py
"""
import os, sys, json, re, subprocess, tempfile, threading, time, types
import xml.etree.ElementTree as ET
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-voice-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

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


def wait_for(cond, seconds=5.0):
    """Wait for what the check is about, not for a number of loops."""
    end = time.time() + seconds
    while time.time() < end:
        try:
            if cond():
                return True
        except Exception:
            pass
        time.sleep(0.02)
    return bool(cond())


import sonar as SN         # noqa: E402
import voice as VO         # noqa: E402
import voiceattack as VA   # noqa: E402
import planview as PV      # noqa: E402
import survey as SV        # noqa: E402
import edsmt as A          # noqa: E402

A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")


def source(name):
    with open(os.path.join(REPO, name), encoding="utf-8") as fh:
        return fh.read()


SRC = source("edsmt.py")


def method(cls, name, text=SRC):
    start = text.index("class %s(" % cls)
    body = text[start:]
    at = body.index("    def %s(" % name)
    rest = body[at + 10:]
    ends = [rest.find(m) for m in ("\n    def ", "\n    @", "\nclass ", "\n# ----")]
    ends = [e for e in ends if e >= 0]
    return body[at:at + 10 + (min(ends) if ends else len(rest))]


# ---------------------------------------------------------------------------
# The sonar (#153)
# ---------------------------------------------------------------------------

@section("the sonar: every 2 s at 1,500 m down to 0.2 s inside 25 m, nothing past 2 km")
def _curve():
    check("every 2 s at 1,500 m", abs(SN.interval_s(1500) - 2.0) < 1e-9, SN.interval_s(1500))
    check("and no slower out to 2,000 m", SN.interval_s(1800) == 2.0 and SN.interval_s(2000) == 2.0)
    check("nothing at all past 2,000 m", SN.interval_s(2000.5) is None and SN.interval_s(5000) is None
          and SN.tone(2500) is None)
    check("every 0.2 s at 25 m", abs(SN.interval_s(25) - 0.2) < 1e-9, SN.interval_s(25))
    check("and inside it", SN.interval_s(10) == 0.2 and SN.interval_s(0) == 0.2)
    distances = [1500, 1200, 900, 600, 400, 250, 150, 100, 60, 40, 30, 25]
    gaps = [SN.interval_s(m) for m in distances]
    check("faster all the way in", all(a > b for a, b in zip(gaps, gaps[1:])), gaps)
    pitches = [SN.pitch_hz(m) for m in distances]
    check("and higher all the way in", all(a < b for a, b in zip(pitches, pitches[1:])), pitches)
    check("low far off, high close by", SN.pitch_hz(1500) == SN.LOW_HZ
          and SN.pitch_hz(25) == SN.HIGH_HZ, (SN.pitch_hz(1500), SN.pitch_hz(25)))
    check("every pitch one winsound can play", all(37 <= p <= 32767 for p in pitches))
    every = [SN.interval_s(m) for m in range(0, 2001, 5)]
    check("a tone is always shorter than the gap to the next", all(
        SN.TONE_MS / 1000.0 < gap for gap in every), min(every))
    check("even steps on a log scale: 100 m is halfway between 25 m and 1,500 m in neither",
          0.2 < SN.interval_s(100) < 1.1, SN.interval_s(100))
    check("rubbish in, nothing out", SN.tone(None) is None and SN.tone("far") is None
          and SN.tone(-5) is None and SN.tone(float("nan")) is None)
    hertz, millis, gap = SN.tone(340)
    check("tone() is pitch, length and gap together",
          (hertz, millis, gap) == (SN.pitch_hz(340), SN.TONE_MS, SN.interval_s(340)))


class Beeps:
    """A stand-in for winsound.Beep: remembers each tone and when."""

    def __init__(self, hold=0.0):
        self.calls, self.hold = [], hold
        self.lock = threading.Lock()

    def __call__(self, hertz, millis):
        with self.lock:
            self.calls.append((time.monotonic(), hertz, millis))
        if self.hold:
            time.sleep(self.hold)

    def since(self, when):
        with self.lock:
            return [c for c in self.calls if c[0] >= when]


@section("the sonar player: tones on a worker thread, through an object the checks replace")
def _player():
    check("off Windows there is nothing to play with", os.name == "nt"
          or SN.windows_beep() is None)
    quiet = SN.Sonar(beep=None) if os.name != "nt" else None
    if quiet is not None:
        check("so the player starts nothing", quiet.follow(20) is False and not quiet.running)
    beeps = Beeps(hold=0.05)
    sonar = SN.Sonar(beep=beeps)
    check("no thread until there is something to play", not sonar.running)
    sonar.follow(5000)
    check("a target past 2 km starts nothing", not sonar.running and not beeps.calls)
    started = time.monotonic()
    took = time.monotonic()
    sonar.follow(20)
    took = time.monotonic() - took
    check("follow() never waits for a tone", took < 0.05, took)
    check("inside 25 m the tones come quickly",
          wait_for(lambda: len(beeps.since(started)) >= 5, 4.0), len(beeps.calls))
    near = beeps.since(started)
    spacing = [b[0] - a[0] for a, b in zip(near, near[1:])]
    check("about 0.2 s apart", spacing and all(0.15 <= s <= 0.45 for s in spacing), spacing)
    check("high and short", all(c[1] == SN.HIGH_HZ and c[2] == SN.TONE_MS for c in near))
    check("on a thread of its own", sonar.running)
    sonar.follow(1500)
    far_from = time.monotonic() + 0.3
    time.sleep(2.6)
    far = beeps.since(far_from)
    check("at 1,500 m: about one every 2 s, and low", 1 <= len(far) <= 2
          and all(c[1] == SN.LOW_HZ for c in far), [(round(c[0] - far_from, 2), c[1]) for c in far])
    sonar.follow(None)
    time.sleep(0.4)
    hushed = time.monotonic()
    time.sleep(0.8)
    check("no target: quiet", not beeps.since(hushed), beeps.since(hushed))
    sonar.follow(15)
    again = time.monotonic()
    check("and back again the moment there is one", wait_for(lambda: beeps.since(again), 1.0))
    sonar.close()
    check("close() ends the thread", wait_for(lambda: not sonar.running, 2.0))
    gone = time.monotonic()
    time.sleep(0.5)
    check("and nothing plays after it", not beeps.since(gone + 0.1))
    check("nor can it be started again", sonar.follow(10) is False)

    class Broken:
        def __call__(self, hertz, millis):
            raise RuntimeError("no sound device")
    bad = SN.Sonar(beep=Broken())
    bad.follow(10)
    time.sleep(0.4)
    check("a sound device that refuses a tone stops nothing", bad.running and bad.played == 0)
    bad.close()


@section("the target: the one the scope and the compass already point at")
def _target():
    def row(id_, metres, amount="High", commodity="Platinum"):
        return {"deposit": {"id": id_, "amount": amount, "commodity": commodity},
                "range_m": metres, "bearing": 10.0}
    rows = [row("a", 300), row("b", 120), row("c", 40, amount="Depleted")]
    check("nearest still worth driving to", PV.guided_target(rows)["deposit"]["id"] == "b")
    check("the one picked to be guided to comes first", PV.guided_target(rows, "a")["deposit"]["id"] == "a")
    check("a guided id not on the picture falls back to the nearest",
          PV.guided_target(rows, "zz")["deposit"]["id"] == "b")
    check("worked out is never the target unless guided to",
          PV.guided_target([row("c", 40, amount="Depleted")]) is None
          and PV.guided_target(rows, "c")["deposit"]["id"] == "c")
    check("nothing on the picture, no target", PV.guided_target([]) is None
          and PV.guided_target(None) is None)
    overlay = source("overlay.py")
    footer = overlay[overlay.index("    def _footer("):]
    footer = footer[:footer.index("\n    def ", 10)]
    check("the scope's GO / NEXT line picks it the same way", "PV.guided_target(plan[\"items\"], wanted)"
          in footer, footer[:400])
    check("and so do the sonar and the directions",
          "PV.guided_target(rows, attr(self, \"_guide_to\", None))" in method("EDSMT", "voice_view"))


# ---------------------------------------------------------------------------
# The Basic voice line pack (#145, #292)
# ---------------------------------------------------------------------------

FIXED = ["online", "voice_test", "update_ready", "backup_done", "signal_logged", "border_set",
         "deposit_marked", "deposit_updated", "deposit_incomplete", "deposit_already",
         "mined_out", "rigs_full", "rigs_all_up", "rig_limit_warning", "rig_lost",
         "rigs_cleared_relog", "plan_trace_start", "plan_ready", "pin_reached", "next_pin",
         "plan_cancelled", "swept_half", "swept_done", "session_start", "session_paused",
         "session_resumed", "session_end", "nearest", "arrived", "none_in_range",
         "touchdown_hint", "locations_on_body", "bodies_ranked", "high_gravity",
         "deploy_clear", "wing_linked", "wing_mate_joined", "wing_mate_left", "wing_clash",
         "chat_ok", "chat_unknown"]
RIGS = ["rig_%s_%d" % (kind, n) for kind in ("down", "up") for n in range(1, 7)]


@section("the line table: every line in all three voices")
def _lines():
    check("it is the Basic voice line pack", VO.PACK_NAME == "Basic voice line pack")
    check("four voices: Celestia, Ship computer, Flight controller, Radio Raxxla on-air",
          [name for _k, name in VO.THEMES] == ["Celestia", "Ship computer", "Flight controller",
                                                "Radio Raxxla on-air"], VO.THEMES)
    check("every approved line is there, and nothing else",
          sorted(VO.LINES) == sorted(FIXED + RIGS), sorted(set(VO.LINES) ^ set(FIXED + RIGS)))
    short = [(line_id, theme) for line_id, words in VO.LINES.items()
             for theme in VO.THEME_KEYS if not str(words.get(theme) or "").strip()]
    check("every line has all four voices", not short and all(
        set(words) == set(VO.THEME_KEYS) for words in VO.LINES.values()), short[:6])
    check("the words as approved, in each voice",
          [VO.line_text("signal_logged", t) for t in VO.THEME_KEYS]
          == ["Signal logged. That's our centre, Commander. Don't wander off.",
              "Signal logged. Survey centre set.", "Signal marked. Centre locked.",
              "Signal's in the book. That's our centre."])
    check("rig three, down and up",
          [VO.line_text("rig_down_3", t) for t in VO.THEME_KEYS]
          == ["Rig three, down.", "Rig three deployed.", "Rig three down.", "Rig three's down."]
          and [VO.line_text("rig_up_3", t) for t in VO.THEME_KEYS]
          == ["Rig three, back aboard.", "Rig three recovered.", "Rig three up.", "Rig three picked up."])
    check("the test line, for the button", VO.line_text("voice_test", "flight_controller")
          == "Radio check. Loud and clear.")
    check("a theme by its name reads the same as by its key",
          VO.line_text("online", "Radio Raxxla on-air") == VO.line_text("online", "on_air"))
    check("a theme that is not one is Celestia, the main voice (5 Nov 2026)",
          VO.clean_theme("bogus") == "celestia" and VO.clean_theme(None) == "celestia")
    check("a line not in the pack says nothing", VO.line_text("nope") == "")
    check("rig lines by number, and none past six",
          VO.rig_line("down", 4) == "rig_down_4" and VO.rig_line("up", 6) == "rig_up_6"
          and VO.rig_line("down", 7) == "" and VO.rig_line("up", "A3") == "")
    check("the rate: -10 to 10, Normal is 0", VO.clean_rate("4") == 4 and VO.clean_rate(99) == 10
          and VO.clean_rate("x") == 0 and dict(VO.RATES)["Normal"] == "0")


@section("the lines are in UK English and name nothing private")
def _lines_words():
    text = " ".join(w for words in VO.LINES.values() for w in words.values()).lower()
    for word in ("color", "center", "recognized", "meter "):
        check("no %r" % word.strip(), word not in text)
    check("recognised, the UK way", "recognised" in text)


# ---------------------------------------------------------------------------
# Spoken directions (#146)
# ---------------------------------------------------------------------------

@section("the direction words: \"Platinum, 340 metres, two o'clock\"")
def _words():
    check("the example", VO.direction_words("Platinum", 340, 60) == "Platinum, 340 metres, two o'clock",
          VO.direction_words("Platinum", 340, 60))
    faces = [VO.clock_words(o) for o in (0, 30, 90, 179, -179, -90, -30, 14.9, 15.1, 340)]
    check("a clock face: ahead, right, behind, left",
          faces == ["dead ahead", "one o'clock", "three o'clock", "behind you", "behind you",
                    "nine o'clock", "eleven o'clock", "dead ahead", "one o'clock",
                    "eleven o'clock"], faces)
    check("all twelve hours", sorted(set(VO.clock_words(h * 30) for h in range(12)))
          == sorted(VO.CLOCK))
    words = [VO.distance_words(m) for m in (1, 7.4, 44, 344, 995, 1000, 1240, 2000, 12345)]
    check("metres to the nearest ten, then kilometres",
          words == ["1 metre", "7 metres", "40 metres", "340 metres", "1 kilometre",
                    "1 kilometre", "1.2 kilometres", "2 kilometres", "12.3 kilometres"], words)
    check("no name: an unknown deposit", VO.direction_words("", 50, 0)
          == "Unknown deposit, 50 metres, dead ahead")
    check("a rig and a waypoint read the same way",
          VO.direction_words("Rig 2", 1500, 180) == "Rig 2, 1.5 kilometres, behind you"
          and VO.direction_words("Waypoint 3", 250, -60) == "Waypoint 3, 250 metres, ten o'clock")
    pin = {"key": "pin:1", "name": "Pin 1", "range_m": 30, "offset": 0}
    wp = {"key": "wp:2", "name": "Waypoint 2", "range_m": 300, "offset": 0}
    dep = {"key": "deposit:x", "name": "Platinum", "range_m": 200, "offset": 0}
    rig = {"key": "rig:1", "name": "Rig 1", "range_m": 900, "offset": 0}
    check("the next pin first, then the waypoint, the deposit, the nearest rig",
          VO.spoken_target(pin, wp, dep, rig) is pin and VO.spoken_target(None, wp, dep, rig) is wp
          and VO.spoken_target(None, None, dep, rig) is dep
          and VO.spoken_target(None, None, None, rig) is rig
          and VO.spoken_target() is None)
    check("moving is a metre a second or more", VO.is_moving(1.0, 0.7) and not VO.is_moving(0.3, 0.7)
          and not VO.is_moving(5, 0))
    check("the repeat is 5 to 60 seconds, 10 to begin with",
          (VO.directions_every("10"), VO.directions_every(2), VO.directions_every(900),
           VO.directions_every("x")) == (10, 5, 60, 10))


@section("when the directions are said: a new target at once, every N s moving, never twice in 3 s")
def _timer():
    timer = VO.DirectionsTimer(every_s=10)
    check("the first target is said at once", timer.due(100.0, "deposit:a", moving=False))
    timer.said(100.0, "deposit:a")
    check("not again while still", not timer.due(115.0, "deposit:a", moving=False))
    check("not again within 10 s while moving", not timer.due(109.0, "deposit:a", moving=True))
    check("again at 10 s while moving", timer.due(110.0, "deposit:a", moving=True))
    timer.said(110.0, "deposit:a")
    check("a new target inside 3 s waits", not timer.due(111.5, "wp:2", moving=True))
    check("and is said once 3 s have gone, moving or not", timer.due(113.0, "wp:2", moving=False))
    timer.said(113.0, "wp:2")
    check("on the target, it is not said over and over",
          not timer.due(130.0, "wp:2", moving=True, metres=12))
    check("no target, nothing", not timer.due(200.0, None, moving=True))
    quick = VO.DirectionsTimer(every_s=1)
    quick.said(0.0, "x")
    check("never more than one line in 3 s, whatever the setting",
          not quick.due(2.9, "x", moving=True) and quick.due(3.0, "x", moving=True))


@section("the session's clock, said as it starts, pauses, resumes and ends")
def _session():
    check("start", VO.session_line("off", "running") == "session_start")
    check("pause", VO.session_line("running", "paused") == "session_paused")
    check("resume", VO.session_line("paused", "running") == "session_resumed")
    check("end, running or paused", VO.session_line("running", "off") == "session_end"
          and VO.session_line("paused", "off") == "session_end")
    check("nothing changed, nothing said", VO.session_line("running", "running") is None)
    check("the first look says nothing", VO.session_line(None, "running") is None)
    books = types.SimpleNamespace(current=None, paused=False)
    check("off with no session", VO.session_state(books) == "off" and VO.session_state(None) == "off")
    books.current = {"id": "1"}
    check("running", VO.session_state(books) == "running")
    books.paused = True
    check("paused", VO.session_state(books) == "paused")


@section("the swept figure: half the survey area, and all of it")
def _sweep_words():
    check("passing half", VO.sweep_line(40, 50) == "swept_half" and VO.sweep_line(49, 73) == "swept_half")
    check("passing all of it", VO.sweep_line(97, 100) == "swept_done")
    check("both at once: all of it", VO.sweep_line(30, 100) == "swept_done")
    check("nothing passed, nothing said", VO.sweep_line(50, 60) is None
          and VO.sweep_line(60, 40) is None and VO.sweep_line(100, 100) is None)
    check("the first look says nothing", VO.sweep_line(None, 80) is None
          and VO.sweep_line(20, None) is None)


@section("the wing link: up, a wingmate joining, one leaving")
def _wing_words():
    check("the first answer: the link is up, whoever is on it",
          VO.wing_line(True, ["Alpha"], []) == "wing_linked" and VO.wing_line(True, [], []) == "wing_linked")
    check("then a wingmate joining", VO.wing_line(False, ["Alpha"], []) == "wing_mate_joined")
    check("or one leaving", VO.wing_line(False, [], ["Alpha"]) == "wing_mate_left")
    check("both in one answer: one line, the one who joined",
          VO.wing_line(False, ["Alpha"], ["Bravo"]) == "wing_mate_joined")
    check("nobody came or went: nothing", VO.wing_line(False, [], []) is None)


# ---------------------------------------------------------------------------
# Speaking: one process, a recording before a spoken line
# ---------------------------------------------------------------------------

STANDIN = os.path.join(TMP, "standin.py")
with open(STANDIN, "w", encoding="utf-8") as _fh:
    _fh.write("import sys\n"
              "out = open(sys.argv[1], 'ab', buffering=0)\n"
              "while True:\n"
              "    line = sys.stdin.buffer.readline()\n"
              "    if not line:\n"
              "        break\n"
              "    out.write(line)\n")


class Spawner:
    """Starts the stand-in for PowerShell: a small Python process that
    writes down every line it is sent."""

    def __init__(self, name):
        self.heard = os.path.join(TMP, name + ".txt")
        open(self.heard, "wb").close()
        self.started = []

    def __call__(self):
        proc = subprocess.Popen([sys.executable, "-u", STANDIN, self.heard],
                                stdin=subprocess.PIPE)
        self.started.append(proc)
        return proc

    def lines(self):
        with open(self.heard, "rb") as fh:
            return [line.decode("utf-8").rstrip("\n") for line in fh]


@section("the speaker: one process for many lines, started on first use, killed at exit")
def _speaker():
    spawn = Spawner("one")
    speaker = VO.Speaker(spawn=spawn, rate=2)
    check("nothing started until something is said", not spawn.started and speaker.proc is None)
    took = time.monotonic()
    for line_id in ("online", "signal_logged", "border_set", "deposit_marked", "rig_down_1"):
        speaker.say_line(line_id, "flight_controller")
    took = time.monotonic() - took
    check("saying never waits for the process", took < 0.2, took)
    check("every line arrives", wait_for(lambda: len(spawn.lines()) >= 6, 10.0), spawn.lines())
    check("through one process", len(spawn.started) == 1, len(spawn.started))
    got = spawn.lines()
    check("the rate first, then each line, in order",
          got[:6] == ["R 2", "S EDSMT online. Standing by.", "S Signal marked. Centre locked.",
                      "S Border marked.", "S Deposit logged.", "S Rig one down."], got)
    speaker.set_rate("-4")
    speaker.say_text("Platinum, 340 metres, two o'clock")
    check("a new rate goes ahead of the next line, still the one process",
          wait_for(lambda: spawn.lines()[-2:] == ["R -4", "S Platinum, 340 metres, two o'clock"], 5)
          and len(spawn.started) == 1, spawn.lines()[-3:])
    speaker.say_text("Two lines\nin one\x07 go")
    check("a line is one line: no newline or control character gets through",
          wait_for(lambda: spawn.lines()[-1:] == ["S Two lines in one go"], 5), spawn.lines()[-1:])
    speaker.say_text("Bastnäsite")
    check("in UTF-8, as the script reads it",
          wait_for(lambda: spawn.lines()[-1:] == ["S Bastnäsite"], 5), spawn.lines()[-1:])
    proc = spawn.started[0]
    check("it is still running between lines", proc.poll() is None)
    speaker.close()
    check("close() kills it", wait_for(lambda: proc.poll() is not None, 5.0), proc.poll())
    check("and nothing more is said", speaker.say_line("online") is False
          and speaker.say_text("hello") is False and len(spawn.started) == 1)
    check("close() runs at exit too", speaker._atexit)

    spawn2 = Spawner("dies")
    speaker2 = VO.Speaker(spawn=spawn2)
    speaker2.say_text("first")
    wait_for(lambda: spawn2.lines(), 5.0)
    spawn2.started[0].kill()
    spawn2.started[0].wait()
    speaker2.say_text("second")
    check("a process that died is started again for the next line",
          wait_for(lambda: "S second" in spawn2.lines(), 5.0) and len(spawn2.started) == 2,
          (spawn2.lines(), len(spawn2.started)))
    speaker2.close()

    def never():
        raise OSError("no PowerShell here")
    tries = []
    speaker3 = VO.Speaker(spawn=lambda: tries.append(1) or never())
    for _ in range(6):
        speaker3.say_text("anything")
        time.sleep(0.05)
    wait_for(lambda: len(tries) >= VO.MAX_STARTS, 2.0)
    time.sleep(0.2)
    check("one that will not start is tried a few times, not for ever",
          len(tries) == VO.MAX_STARTS, len(tries))
    speaker3.close()
    if os.name != "nt":
        check("off Windows the speaker has nothing to start, and says nothing",
              VO.windows_spawn() is None and VO.Speaker().available is False
              and VO.Speaker().say_line("online") is False)


@section("the speech script: Windows' own speech, one PowerShell, the script encoded")
def _script():
    import base64
    command = VO.powershell_command(root=os.path.join(TMP, "nowhere"))
    check("PowerShell, no profile, nothing interactive",
          command[0].lower().endswith("powershell.exe") and "-NoProfile" in command
          and "-NonInteractive" in command, command[:5])
    check("the script handed over encoded, so no quoting can break it",
          command[-2] == "-EncodedCommand"
          and base64.b64decode(command[-1]).decode("utf-16-le") == VO.SPEECH_SCRIPT)
    script = VO.SPEECH_SCRIPT
    check("System.Speech, one synthesiser for the whole run",
          "System.Speech" in script and script.count("New-Object System.Speech") == 1)
    check("lines read one at a time from its input, as UTF-8",
          "ReadLine()" in script and "UTF8" in script and "while ($true)" in script)
    check("R sets the rate, S speaks, W plays a recording to its end",
          "$voice.Rate" in script and "$voice.Speak(" in script and "PlaySync()" in script)
    check("its window never shows over the game", VO.CREATE_NO_WINDOW == 0x08000000
          and "creationflags=CREATE_NO_WINDOW" in source("voice.py"))


@section("a recording wins: voice/<theme>/<id>.wav beside the app or in the data folder")
def _wav():
    beside, data = os.path.join(TMP, "app"), os.path.join(TMP, "datafolder")
    for folder in (beside, data):
        os.makedirs(os.path.join(folder, "voice", "on_air"), exist_ok=True)
    in_data = os.path.join(data, "voice", "on_air", "rigs_full.wav")
    open(in_data, "wb").close()
    check("found in the data folder", VO.recording("rigs_full", "on_air", [beside, data]) == in_data)
    in_app = os.path.join(beside, "voice", "on_air", "rigs_full.wav")
    open(in_app, "wb").close()
    check("beside the app comes first", VO.recording("rigs_full", "on_air", [beside, data]) == in_app)
    check("only in its own voice", VO.recording("rigs_full", "ship_computer", [beside, data]) == "")
    check("none: nothing", VO.recording("online", "on_air", [beside, data]) == ""
          and VO.recording("online", "on_air", []) == "")
    spawn = Spawner("wav")
    speaker = VO.Speaker(spawn=spawn, folders=[beside, data])
    speaker.say_line("rigs_full", "Radio Raxxla on-air")
    speaker.say_line("online", "on_air")
    check("the recording is played, and a line without one is spoken",
          wait_for(lambda: len(spawn.lines()) >= 3, 5.0)
          and spawn.lines()[1:3] == ["W " + in_app, "S Radio Raxxla here. Let's go find "
                                                    "something worth digging."], spawn.lines())
    speaker.close()
    check("the app looks in its bundle, beside itself, then in the data folder",
          A.voice_folders() == [A.shipped_file(), A.app_dir(), A.DATA_DIR]
          or A.voice_folders() == [A.app_dir(), A.DATA_DIR] and A.shipped_file() == A.app_dir(),
          A.voice_folders())
    # The installed build: PyInstaller puts bundled files in its own folder
    # (sys._MEIPASS), not beside the exe. A pack shipped in the bundle must be
    # found there, ahead of anything beside the app or in the data folder.
    import sys as _sys
    _sys._MEIPASS = os.path.join(TMP, "bundle")
    try:
        folders = A.voice_folders()
        check("frozen, the bundle is looked in first", folders[0] == _sys._MEIPASS, folders)
        check("and nothing is listed twice", len(folders) == len(set(folders)), folders)
    finally:
        del _sys._MEIPASS

    print("== the Basic voice line pack, Ship computer (recorded 5 Nov 2026) ==")
    pack = os.path.join(os.path.dirname(HERE), "voice", "ship_computer")
    ids = sorted(VO.LINES)
    have = sorted(n[:-4] for n in os.listdir(pack) if n.endswith(".wav")) if os.path.isdir(pack) else []
    check("every line has a recording, and nothing else is there", have == ids,
          (sorted(set(ids) - set(have)), sorted(set(have) - set(ids))))
    bad = []
    for name in have:
        raw = open(os.path.join(pack, name + ".wav"), "rb").read(44)
        channels = int.from_bytes(raw[22:24], "little")
        rate = int.from_bytes(raw[24:28], "little")
        bits = int.from_bytes(raw[34:36], "little")
        if not (raw[:4] == b"RIFF" and raw[8:12] == b"WAVE" and raw[20:22] == b"\x01\x00"
                and channels == 1 and rate == 22050 and bits == 16):
            bad.append(name)
    check("each is plain PCM, mono, 22 kHz, 16-bit - what the Windows player plays", not bad, bad[:5])
    check("the pack is found for every line through the app's own folders",
          all(VO.recording(i, "ship_computer", [os.path.dirname(HERE)]) for i in ids))
    for spec_name in ("EDSMT.spec", "EDSMT-onefile.spec"):
        spec = open(os.path.join(os.path.dirname(HERE), "build", spec_name), encoding="utf-8").read()
        check("%s bundles voice/ship_computer" % spec_name,
              "voice" in spec and "ship_computer" in spec and ".wav" in spec)


# ---------------------------------------------------------------------------
# The VoiceAttack profile (#152)
# ---------------------------------------------------------------------------

LALT, LCTRL, LSHIFT = 0xA4, 0xA2, 0xA0


def commands_in(path):
    tree = ET.parse(path)
    root = tree.getroot()
    out = {}
    for command in root.iter("Command"):
        phrase = command.findtext("CommandString")
        codes = [int(c.text) for c in command.iter("unsignedShort")]
        out[phrase] = {"codes": codes, "type": command.findtext(".//ActionType"),
                       "enabled": command.findtext("Enabled"),
                       "spoken": command.findtext("UseSpokenPhrase")}
    return root, out


@section("the VoiceAttack profile: well-formed, the default keys")
def _profile_default():
    folder = os.path.join(TMP, "va-default")
    path, made, missing = VA.write_profile(folder, dict(A.DEFAULT_SETTINGS), A.parse_binding,
                                           A.DEFAULT_SETTINGS)
    check("saved as Radio Raxxla EDSMT.vap", os.path.basename(path) == "Radio Raxxla EDSMT.vap"
          and os.path.isfile(path), path)
    root, commands = commands_in(path)
    check("well-formed XML, a Profile named Radio Raxxla EDSMT",
          root.tag == "Profile" and root.findtext("Name") == "Radio Raxxla EDSMT")
    check("left unlocked, so it can be edited and exported again: CR and BE on the profile, "
          "right above its closing tag", [child.tag for child in root][-2:] == ["CR", "BE"]
          and [root.findtext(f) for f in ("CR", "BE")] == ["0", "0"],
          [child.tag for child in root][-3:])
    check("and CL, the command lock, 0 on every command and not on the profile",
          root.find("CL") is None and all(c.findtext("CL") == "0" for c in root.iter("Command"))
          and len(list(root.iter("Command"))) == len(commands))
    expect = {"mark signal": [LALT, 0x31], "set border": [LALT, 0x32],
              "mark deposit": [LALT, 0x33], "rigs up": [LCTRL, LALT, 0x30],
              "update deposit": [LCTRL, LALT, 0x33], "overlay": [LALT, 0x30]}
    expect.update({"rig %s down" % w: [LALT, 0x33 + n]
                   for n, w in enumerate(("one", "two", "three", "four", "five", "six"), 1)})
    got = {p: c["codes"] for p, c in commands.items()}
    check("every command presses the key EDSMT ships with: Alt+1, Alt+2, Alt+3, Alt+4 to "
          "Alt+9, AltGr+0, AltGr+3, Alt+0", got == expect, got)
    check("blank keys are left out and said: next waypoint and lock overlay",
          missing == ["next waypoint", "lock overlay"], missing)
    check("each is a spoken command that presses keys",
          all(c["type"] == "PressKey" and c["enabled"] == "true" and c["spoken"] == "true"
              for c in commands.values()))
    ids = [e.text for e in root.iter("Id")]
    check("every id its own", len(ids) == len(set(ids)) == 1 + 2 * len(commands), len(ids))
    text = open(path, encoding="utf-8").read()
    check("written as UTF-8 with its declaration", text.startswith('<?xml version="1.0" '
                                                                  'encoding="utf-8"?>'))
    low = text.lower()
    check("branded Radio Raxxla EDSMT, and naming nobody else",
          low.count("radio raxxla edsmt") >= 2 and not re.search(
              r"hcs|voicepack|voice pack|elevenlabs|frontier", low))


@section("the VoiceAttack profile: the commander's own keys")
def _profile_custom():
    mine = dict(A.DEFAULT_SETTINGS)
    mine.update({"hotkey_location": "CTRL+SHIFT+K", "hotkey_rig3": "F7",
                 "hotkey_wp_next": "ALT+N", "hotkey_lock": "NUMPAD5",
                 "hotkey_allup": "", "hotkey_overlay": "SHIFT+F12"})
    path, made, missing = VA.write_profile(os.path.join(TMP, "va-mine"), mine, A.parse_binding,
                                           A.DEFAULT_SETTINGS)
    _root, commands = commands_in(path)
    got = {p: c["codes"] for p, c in commands.items()}
    check("a key of his own, modifiers and all", got.get("mark signal") == [LCTRL, LSHIFT, 0x4B],
          got.get("mark signal"))
    check("a function key on its own", got.get("rig three down") == [0x76], got.get("rig three down"))
    check("next waypoint and lock overlay are in once they have keys",
          got.get("next waypoint") == [LALT, 0x4E] and got.get("lock overlay") == [0x65],
          (got.get("next waypoint"), got.get("lock overlay")))
    check("a key cleared is a command left out", "rigs up" not in got and missing == ["rigs up"],
          missing)
    check("and the rest are still the defaults", got.get("rig one down") == [LALT, 0x34]
          and got.get("overlay") == [LSHIFT, 0x7B])
    made_words = [c[0] for c in made]
    check("made again, it follows the keys as they are now", made_words == [
        p for p, _n in VA.COMMANDS if p != "rigs up"], made_words)
    check("a binding EDSMT cannot read is left out, not guessed",
          VA.profile_commands({"hotkey_location": "CTRL+NOTAKEY"}, A.parse_binding,
                              A.DEFAULT_SETTINGS)[1][:1] == ["mark signal"])
    check("the keys from parse_binding's own numbers",
          VA.key_codes((A.MOD_CONTROL | A.MOD_ALT, 0x34)) == [LCTRL, LALT, 0x34]
          and VA.key_codes((A.MOD_WIN, 0x41)) == [0x5B, 0x41] and VA.key_codes(None) is None)
    odd = VA.profile_xml([("rig <one> & \"two\"", "ALT+1", [LALT, 0x31], "Left Alt+1")])
    check("text that means something in XML is escaped", ET.fromstring(odd).findtext(
        ".//CommandString") == "rig <one> & \"two\"")


@section("docs/VOICEATTACK.md: what was found, with where it was found")
def _doc():
    text = source(os.path.join("docs", "VOICEATTACK.md"))
    check("it cites the VoiceAttack help and site", "voiceattack.com" in text
          and text.count("https://") >= 3)
    check("and says plainly what is not confirmed", "not confirmed" in text.lower()
          or "unconfirmed" in text.lower())
    low = text.lower()
    check("naming no other voice pack or profile maker", not re.search(
        r"hcs|voicepack|elevenlabs|eddi|covas", low))


# ---------------------------------------------------------------------------
# The app says its events
# ---------------------------------------------------------------------------

class FakeSpeaker:
    def __init__(self):
        self.lines, self.texts, self.rates, self.folders = [], [], [], []
        self.closed = False

    def set_rate(self, rate):
        self.rates.append(rate)

    def say_line(self, line_id, theme=None, place=None, detail=None):
        self.lines.append((line_id, theme))
        self.details = getattr(self, "details", []) + [detail]
        return True

    def say_text(self, text):
        self.texts.append(text)
        return True

    def close(self):
        self.closed = True


class FakeSonar:
    def __init__(self):
        self.followed, self.closed = [], False

    def follow(self, metres):
        self.followed.append(metres)

    def close(self):
        self.closed = True


def headless_app(**settings):
    app = A.EDSMT.__new__(A.EDSMT)
    app.settings = dict(A.DEFAULT_SETTINGS)
    app.settings.update(settings)
    app.voice = FakeSpeaker()
    app.sonar = FakeSonar()
    app.troubles = []
    app.trouble = lambda stage, exc: app.troubles.append((stage, str(exc)))
    return app


@section("speak(): only with Voice Mode on, in the voice picked")
def _speak():
    app = headless_app()
    check("Voice Mode is off as it ships", A.DEFAULT_SETTINGS["voice_mode"] is False
          and A.DEFAULT_SETTINGS["voice_directions"] is False and A.DEFAULT_SETTINGS["sonar"] is False)
    check("off, nothing is said", app.speak("signal_logged") is False and not app.voice.lines)
    app.settings.update(voice_mode=True, voice_theme="flight_controller", voice_rate="2")
    check("on, the line goes to the speaker in the voice picked",
          app.speak("signal_logged") and app.voice.lines == [("signal_logged", "flight_controller")]
          and app.voice.rates[-1] == "2")
    app.settings["voice_mode"] = False
    check("Test voice says its line with the mode off, in the voice in the box",
          app.speak("voice_test", force=True, theme="on_air", rate="-2")
          and app.voice.lines[-1] == ("voice_test", "on_air") and app.voice.rates[-1] == "-2")
    del app.voice
    check("no speaker yet: nothing, and no fault", app.speak("online", force=True) is False)


SPOKEN = [("log_location", "signal_logged"), ("set_survey_border", "border_set"),
          ("mark_deposit", "deposit_marked"), ("mark_deposit", "deposit_incomplete"),
          ("mark_deposit", "deposit_already"), ("update_deposit_here", "deposit_updated"),
          ("mark_mined", "mined_out"), ("drop_rigs", "rigs_full"), ("drop_rigs", "wing_clash"),
          ("rigs_up", "rigs_all_up"), ("watch_rigs", "rig_limit_warning"),
          ("watch_rigs", "rig_lost"), ("planner_trace", "plan_trace_start"),
          ("finish_trace", "plan_ready"), ("cancel_trace", "plan_cancelled"),
          ("update_downloaded", "update_ready"), ("backup_before_update", "backup_done"),
          ("follow_deposit", "arrived"), ("follow_gravity", "high_gravity"),
          ("follow_voice", "pin_reached")]


@section("each event says its line")
def _events():
    for name, line_id in SPOKEN:
        check("%s says %s" % (name, line_id), 'self.speak("%s")' % line_id in method("EDSMT", name)
              or ('"%s"' % line_id in method("EDSMT", name) and "self.speak(" in method("EDSMT", name)))
    check("a rig down says its own number", 'self.speak("rigs_full" if down >= MAX_RIGS'
          in method("EDSMT", "drop_rigs") and 'VO.rig_line("down", n)' in method("EDSMT", "drop_rigs"))
    check("and a rig up", 'self.speak(VO.rig_line("up", n))' in method("EDSMT", "rig_up"))
    check("Back up now in Settings says it is done",
          'self.app.speak("backup_done")' in method("SettingsWindow", "backup_now"))
    check("the guided survey's end, once for its area", 'speak("swept_done")' in source("guidance.py")
          and '"speak_sweep"' in source("guidance.py"))
    chat = source("inputmix.py")
    check("a chat command not understood, and one taken", 'speak(app, "chat_unknown")' in chat
          and 'speak(app, "chat_ok")' in chat)
    check("EDSMT online, at start, with the mode on", 'self.speak("online")' in method("EDSMT", "__init__"))
    check("every tick follows the voice", "self.follow_voice()" in method("EDSMT", "tick"))
    named = set()
    for name in ("edsmt.py", "guidance.py", "inputmix.py"):
        named |= set(re.findall(r'speak\((?:app, )?"([a-z_0-9]+)"', source(name)))
    named |= set(re.findall(r'self\.speak\("([a-z_0-9]+)" if', SRC))
    check("every line the app names is in the pack", named and named <= set(VO.LINES),
          sorted(named - set(VO.LINES)))
    check("the rig warning is said only when its own spoken sound is off",
          method("EDSMT", "watch_rigs").count('self.speak("rig_limit_warning")') == 2
          and "else:" in method("EDSMT", "watch_rigs"))


R = 3_000_000.0
LAT, LON = 10.0, 20.0


def offset(east, north, lat=LAT, lon=LON):
    import math
    dlat = math.degrees(north / R)
    dlon = math.degrees(east / (R * math.cos(math.radians(lat))))
    return lat + dlat, lon + dlon


def state_at(lat=LAT, lon=LON, heading=0.0, rhino=True):
    return types.SimpleNamespace(system="Ega", body="Ega 1", has_position=True, radius_m=R,
                                 lat=lat, lon=lon, heading=heading, in_srv=rhino,
                                 in_rhino=rhino, in_ship=not rhino, on_foot=False)


def driving_app(**settings):
    app = headless_app(**settings)
    folder = os.path.join(TMP, "store-%d" % len(os.listdir(TMP)))
    os.makedirs(folder)
    app.store = SV.Survey(folder)
    app.game = state_at()
    app.plan_marks = lambda: None
    app.guidance_view = lambda *a, **k: None
    app.earnings = types.SimpleNamespace(current=None, paused=False)
    return app


@section("the sonar follows the target deposit in the Rhino, and only with its switch on")
def _app_sonar():
    app = driving_app()
    lat, lon = offset(0, 300)
    app.store.add_deposit(system="Ega", body="Ega 1", lat=lat, lon=lon, commodity="Platinum",
                          amount="High")
    app.follow_voice(now=1000.0)
    check("switched off: the sonar hears nothing", app.sonar.followed[-1:] == [None],
          app.sonar.followed)
    app.settings["sonar"] = True
    app.follow_voice(now=1001.0)
    got = app.sonar.followed[-1]
    check("switched on: the target's distance", got is not None and abs(got - 300) < 2, got)
    near_lat, near_lon = offset(50, 50)
    near = app.store.add_deposit(system="Ega", body="Ega 1", lat=near_lat, lon=near_lon,
                                 commodity="Gold", amount="Low")
    app.follow_voice(now=1002.0)
    check("the nearest live deposit", abs(app.sonar.followed[-1] - 70.7) < 2, app.sonar.followed[-1])
    app.store.update_deposit(near["id"], amount="Depleted")
    app.follow_voice(now=1003.0)
    check("not one that is worked out", abs(app.sonar.followed[-1] - 300) < 2, app.sonar.followed[-1])
    app._guide_to = near["id"]
    app.follow_voice(now=1004.0)
    check("the one picked to be guided to, as the scope does", abs(app.sonar.followed[-1] - 70.7) < 2)
    app.game = state_at(rhino=False)
    app.follow_voice(now=1005.0)
    check("out of the Rhino: quiet", app.sonar.followed[-1] is None)
    app.game = None
    app.follow_voice(now=1006.0)
    check("no game: quiet, no fault", app.sonar.followed[-1] is None and not app.troubles,
          app.troubles)


@section("spoken directions in the app: the target, every N s while moving, and on a change")
def _app_directions():
    app = driving_app(voice_directions=True, voice_directions_s=10)
    lat, lon = offset(300, 0)
    app.store.add_deposit(system="Ega", body="Ega 1", lat=lat, lon=lon, commodity="Platinum",
                          amount="High")
    said = app.follow_voice(now=100.0)
    check("said at once: name, distance, clock face", said == "Platinum, 300 metres, three o'clock",
          said)
    check("to the speaker as words", app.voice.texts == ["Platinum, 300 metres, three o'clock"])
    app.game = state_at(*offset(0, 4.0))
    check("moving, but not 10 s since: nothing", not app.follow_voice(now=104.0))
    check("standing still 12 s on, not again", not app.follow_voice(now=112.0))
    app.game = state_at(*offset(0, 6.0), heading=90.0)
    said = app.follow_voice(now=113.0)
    check("moving and 10 s gone: again, turned to the heading", said == "Platinum, 300 metres, "
          "dead ahead", said)
    app.settings["voice_directions_s"] = 30
    app.game = state_at(*offset(0, 20.0), heading=90.0)
    check("the setting is followed: moving, 12 s on, but every 30 s asked for",
          not app.follow_voice(now=125.0))
    app.rigs_at = {"system": "Ega", "body": "Ega 1",
                   "rigs": [{"n": 1, "lat": offset(-200, 0)[0], "lon": offset(-200, 0)[1],
                             "srv": None, "at": 0}]}
    app.plan_marks = lambda: {"next_pin": {"n": 2, "range_m": 60.0, "offset": -90.0}}
    app.rig_plan = {"spacing": 78}
    app.settings["voice_mode"] = True
    said = app.follow_voice(now=127.0)
    check("a rig plan's next pin comes before the deposit, and is said at once",
          said == "Pin 2, 60 metres, nine o'clock", said)
    app.plan_marks = lambda: {"next_pin": {"n": 2, "range_m": 10.0, "offset": 0.0}}
    app.voice.lines.clear()
    app.follow_voice(now=128.0)
    check("on the pin: on the pin, deploy rig - once", app.voice.lines == [
        ("pin_reached", app.settings["voice_theme"])], app.voice.lines)
    app.follow_voice(now=129.0)
    check("and not again for the same pin", len(app.voice.lines) == 1, app.voice.lines)
    app.plan_marks = lambda: None
    said = app.follow_voice(now=129.5)
    check("a change inside 3 s waits", not said)
    said = app.follow_voice(now=131.0)
    check("then the deposit again", said and said.startswith("Platinum"), said)
    app.store.deposits.clear()
    said = app.follow_voice(now=135.0)
    check("no deposit: the nearest rig", said and said.startswith("Rig 1, 200 metres"), said)
    app.settings["voice_directions"] = False
    check("switched off: nothing", not app.follow_voice(now=200.0))
    app.settings["voice_directions"] = True
    app.game = state_at(rhino=False)
    check("out of the Rhino: nothing", not app.follow_voice(now=210.0))


@section("the session's clock, said from the books")
def _app_session():
    app = driving_app(voice_mode=True)
    app.game = None
    app.follow_voice(now=1.0)
    check("the first look says nothing", not app.voice.lines)
    app.earnings.current = {"id": "s1"}
    app.follow_voice(now=2.0)
    app.earnings.paused = True
    app.follow_voice(now=3.0)
    app.earnings.paused = False
    app.follow_voice(now=4.0)
    app.earnings.current = None
    app.follow_voice(now=5.0)
    check("started, paused, resumed, ended", [l for l, _t in app.voice.lines] == [
        "session_start", "session_paused", "session_resumed", "session_end"], app.voice.lines)


@section("half swept and all of it: once each for a survey area, with the guided survey's end")
def _app_sweep():
    app = driving_app(voice_mode=True)
    app.game = None
    cmap = types.SimpleNamespace(system="Ega", body="Ega 1", centre=(LAT, LON), border_m=500.0)
    cover = {"percent": 10}
    app._survey_map = lambda: cmap
    app.survey_cover = lambda found: dict(cover)

    def said():
        return [line for line, _theme in app.voice.lines]
    app.follow_voice(now=1.0)
    check("the first look says nothing", not said(), said())
    for now, percent in ((2.0, 55), (3.0, 60)):
        cover["percent"] = percent
        app.follow_voice(now=now)
    check("half swept, said once", said() == ["swept_half"], said())
    cover["percent"] = 100
    app.follow_voice(now=4.0)
    check("all of it", said() == ["swept_half", "swept_done"], said())
    check("the guided survey ending after it says nothing more",
          app.speak_sweep("swept_done") is False and said() == ["swept_half", "swept_done"], said())
    app.voice.lines.clear()
    cmap.border_m = 800.0
    cover["percent"] = 40
    app.follow_voice(now=5.0)
    check("a new border is a new area, and its first look says nothing", not said(), said())
    check("the guided survey's end is said for it", app.speak_sweep("swept_done") is True
          and said() == ["swept_done"], said())
    cover["percent"] = 100
    app.follow_voice(now=6.0)
    check("and not again when the figure reaches 100%", said() == ["swept_done"], said())
    app.settings["voice_mode"] = False
    app.voice.lines.clear()

    def costly(found):
        raise AssertionError("worked out with Voice Mode off")
    app.survey_cover = costly
    app.follow_voice(now=7.0)
    check("Voice Mode off: the figure is not worked out for it, and nothing is said",
          not said() and not app.troubles, app.troubles)
    app.survey_cover = lambda found: dict(cover)
    cmap.border_m = 1000.0
    cover["percent"] = 30
    app.settings["voice_mode"] = True
    app.follow_voice(now=7.5)
    app.settings["voice_mode"] = False
    app.follow_voice(now=7.6)
    cover["percent"] = 60
    app.settings["voice_mode"] = True
    app.follow_voice(now=7.7)
    check("switched off and on again: a first look again, not old news",
          not said(), said())
    cmap.centre = None
    app.settings["voice_mode"] = True
    app.follow_voice(now=8.0)
    check("no survey area: nothing, and no fault", not said() and not app.troubles, app.troubles)


@section("the wing link said as it comes up, and wingmates as they come and go")
def _app_wing():
    app = headless_app(voice_mode=True)
    app.say = lambda *args, **kwargs: None
    app.wing_live_marks = lambda mates: None

    def answer(*names):
        return json.dumps({"members": [{"name": name} for name in names]})

    def said():
        lines = [line for line, _theme in app.voice.lines]
        app.voice.lines.clear()
        return lines
    app.take_wing(True, answer("Alpha"))
    check("the first answer: wing link established", said() == ["wing_linked"])
    app.take_wing(True, answer("Alpha"))
    check("nobody new: nothing", said() == [])
    app.take_wing(True, answer("Alpha", "Bravo"))
    check("a wingmate joins", said() == ["wing_mate_joined"])
    app.take_wing(True, answer("Bravo"))
    check("a wingmate leaves", said() == ["wing_mate_left"])
    app.take_wing(False, "the server did not answer")
    app.take_wing(True, answer("Bravo"))
    check("back after a failure: the link is up again", said() == ["wing_linked"])
    app.settings.update(wing_link=False)
    app.wing_leave()
    app.take_wing(True, answer("Bravo"))
    check("left and joined again: up again", said() == ["wing_linked"])
    app.watcher = types.SimpleNamespace(wing=["Alpha", "Bravo"], cmdr="Me")
    app.take_wing_auto(True, answer())
    check("your wing in the game, nobody linked yet: nothing", said() == [])
    app.take_wing_auto(True, answer("Alpha"))
    check("the first wingmate linked from it: wing link established", said() == ["wing_linked"])
    app.take_wing_auto(True, answer("Alpha", "Bravo"))
    check("another joins", said() == ["wing_mate_joined"])
    app.take_wing_auto(True, answer("Bravo"))
    check("one leaves", said() == ["wing_mate_left"])
    app.settings["voice_mode"] = False
    app.take_wing(True, answer("Charlie"))
    check("Voice Mode off: nothing", said() == [])


@section("the profile from the app: the data folder, and where it is said")
def _app_profile():
    app = headless_app()
    path, words = app.make_voiceattack_profile(dict(A.DEFAULT_SETTINGS))
    check("saved in the data folder", path == os.path.join(A.DATA_DIR, VA.FILE_NAME)
          and os.path.isfile(path), path)
    check("and it says where, and how to import it", A.DATA_DIR in words and VA.FILE_NAME in words
          and "Import Profile" in words, words)
    check("and which commands have no key", '"next waypoint" and "lock overlay"' in words, words)
    bad = os.path.join(TMP, "a-file")
    open(bad, "w").close()
    path, words = app.make_voiceattack_profile(dict(A.DEFAULT_SETTINGS), folder=bad)
    check("a folder it cannot write to is said, not raised", path == "" and "Could not" in words,
          words)


@section("closing EDSMT closes the speech process and the sonar")
def _close():
    text = method("EDSMT", "on_close")
    check("on_close closes both", 'attr(self, "voice", None)' in text
          and 'attr(self, "sonar", None)' in text and "player.close()" in text)
    check("built when the window is", "VO.Speaker(" in method("EDSMT", "__init__")
          and "SN.Sonar()" in method("EDSMT", "__init__"))


# ---------------------------------------------------------------------------
# The real window
# ---------------------------------------------------------------------------

try:
    import tkinter
    tkinter.Tk().destroy()
    HAVE_DISPLAY = True
except Exception as _exc:
    HAVE_DISPLAY = False
    print("  SKIP  the Settings controls need a display (%s). Run it under xvfb-run." % _exc)

if HAVE_DISPLAY:
    import overlay as OV
    OV.foreground_is_game = lambda: None
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _fh:
        json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS,
                   "welcome_seen_version": A.APP_VERSION}, _fh)
    # What VoiceAttack has on this machine is the test's to say, not the PC's:
    # the app looks 3 s after start, which on a slow machine lands mid-test.
    _PACKS = [False]
    A.VA.find_sound_packs = lambda *a, **k: _PACKS[0]
    APP = A.EDSMT()
    APP.geometry("1400x900+0+0")
    APP.updates.check = lambda *args, **kwargs: None

    def pump(times=3):
        for _ in range(times):
            try:
                APP.update_idletasks()
                APP.update()
            except Exception:
                pass

    def settle_until(cond, seconds=6.0):
        end = time.time() + seconds
        while time.time() < end:
            try:
                if cond():
                    return True
            except Exception:
                pass
            pump(1)
            time.sleep(0.02)
        return bool(cond())

    def walk(widget):
        for child in widget.winfo_children():
            yield child
            yield from walk(child)

    def button(widget, text):
        return next((w for w in walk(widget) if isinstance(w, A.ctk.CTkButton)
                     and str(w.cget("text")) == text), None)

    def saved():
        with open(A.SETTINGS_FILE, encoding="utf-8") as fh:
            return json.load(fh)

    @section("the app starts with a speaker and a sonar, and starts nothing")
    def _boot():
        pump(4)
        check("a speaker, nothing running", isinstance(APP.voice, VO.Speaker)
              and APP.voice.proc is None and APP.voice.starts == 0)
        check("a sonar, no thread", isinstance(APP.sonar, SN.Sonar) and not APP.sonar.running)

    @section("Settings > Basics > Voice: the switches, the voice, the rate and Test voice")
    def _settings():
        win = A.SettingsWindow(APP)
        pump(4)
        try:
            for key, label in (("voice_mode", "Voice Mode"), ("voice_directions", "Spoken directions"),
                               ("sonar", "Proximity sonar")):
                var = win.toggles.get(key)
                switch = next((w for w in walk(win.pages["Basics"])
                               if isinstance(w, A.ctk.CTkSwitch) and w.cget("text") == label), None)
                check("%s: a switch on Basics, off to begin with, with its note" % label,
                      var is not None and var.get() is False and switch is not None
                      and getattr(switch, "_edsmt_tip", ""), (var, switch))
            box, options = win.choices["voice_theme"]
            check("the voice: the four of the pack, Celestia first and picked",
                  [n for n, _v in options]
                  == ["Celestia", "Ship computer", "Flight controller", "Radio Raxxla on-air"]
                  and box.get() == "Celestia", (options, box.get()))
            rate, rates = win.choices["voice_rate"]
            check("the rate, Normal to begin with", rate.get() == "Normal" and len(rates) == 5)
            entry = win.fields["voice_directions_s"]
            check("the directions every 10 s to begin with", entry.get() == "10", entry.get())
            words = " ".join(str(w.cget("text")) for w in walk(win.pages["Basics"])
                             if isinstance(w, A.ctk.CTkLabel))
            check("the section names the Basic voice line pack", "Basic voice line pack" in words)
            test = button(win.pages["Basics"], "Test voice")
            check("Test voice, with its note", test is not None and getattr(test, "_edsmt_tip", ""))
            real = APP.voice
            APP.voice = FakeSpeaker()
            try:
                box.set("Flight controller")
                rate.set("Quick")
                test.invoke()
                check("it says the test line in the voice and rate in the boxes, saved or not",
                      APP.voice.lines == [("voice_test", "flight_controller")]
                      and APP.voice.rates[-1] == "2", (APP.voice.lines, APP.voice.rates))
                check("and says what it said", "Radio check. Loud and clear." in
                      str(win.status.cget("text")), win.status.cget("text"))
            finally:
                APP.voice = real
            win.toggles["voice_mode"].set(True)
            win.toggles["sonar"].set(True)
            entry.delete(0, "end")
            entry.insert(0, "900")
            win.save()
            check("directions every 900 s is refused, and said",
                  "5 to 60 seconds" in str(win.status.cget("text"))
                  and saved().get("voice_mode") is not True, win.status.cget("text"))
            entry.delete(0, "end")
            entry.insert(0, "15")
            win.save()
            data = saved()
            check("saved: Voice Mode on, the Flight controller, Quick, 15 s, the sonar",
                  data.get("voice_mode") is True and data.get("voice_theme") == "flight_controller"
                  and data.get("voice_rate") == "2" and data.get("voice_directions_s") == 15
                  and data.get("sonar") is True, {k: data.get(k) for k in A.DEFAULT_SETTINGS
                                                 if k.startswith(("voice", "sonar"))})
            win.load()
            check("and shown again as saved", box.get() == "Flight controller"
                  and rate.get() == "Quick" and win.toggles["sonar"].get() is True)
            detail, details = win.choices["voice_detail"]
            check("answer length: Short, Normal, Chatty, Normal to begin with",
                  [n for n, _v in details] == ["Short", "Normal", "Chatty"] and detail.get() == "Normal",
                  (details, detail.get()))
            hints = win.toggles.get("voice_pack_hints")
            switch = next((w for w in walk(win.pages["Basics"])
                           if isinstance(w, A.ctk.CTkSwitch) and w.cget("text") == "Voice-pack reminders"), None)
            note = getattr(switch, "_edsmt_tip", "") or ""
            check("voice-pack reminders: a switch with its note, naming no pack",
                  hints is not None and switch is not None and note
                  and not any(word in note.lower() for word in ("hcs", "hcspack")), note)
            _PACKS[0] = True
            APP.pack_hints_found = True
            win.load()
            check("left alone, the switch shows on when a voice pack was found", hints.get() is True)
            win.save()
            check("saved as shown, it keeps following what is found",
                  saved().get("voice_pack_hints", "absent") is None, saved().get("voice_pack_hints", "absent"))
            hints.set(False)
            detail.set("Chatty")
            win.save()
            data = saved()
            check("turned off, it stays off; Chatty saved",
                  data.get("voice_pack_hints") is False and data.get("voice_detail") == "chatty",
                  (data.get("voice_pack_hints"), data.get("voice_detail")))
        finally:
            win.destroy()
            pump(2)

    @section("Settings > Keys: Make a VoiceAttack profile, with the keys on the page")
    def _keys():
        win = A.SettingsWindow(APP)
        pump(4)
        try:
            make = button(win.pages["Keys"], "Make a VoiceAttack profile")
            check("the button is on the Keys page, with its note",
                  make is not None and getattr(make, "_edsmt_tip", ""))
            win._set_binding("hotkey_deposit", "CTRL+SHIFT+M")
            target = os.path.join(A.DATA_DIR, VA.FILE_NAME)
            if os.path.exists(target):
                os.remove(target)
            make.invoke()
            pump(2)
            check("it saves to the data folder", os.path.isfile(target))
            status = str(win.status.cget("text"))
            check("and says where", A.DATA_DIR in status and VA.FILE_NAME in status, status)
            _root, commands = commands_in(target)
            check("with the key on the page, saved or not",
                  commands["mark deposit"]["codes"] == [LCTRL, LSHIFT, 0x4D],
                  commands.get("mark deposit"))
            check("and the others as they are", commands["mark signal"]["codes"] == [LALT, 0x31])
        finally:
            win.destroy()
            pump(2)

    @section("closing the window kills the speech process")
    def _quit():
        spawn = Spawner("app")
        APP.voice = VO.Speaker(spawn=spawn)
        APP.settings["voice_mode"] = True
        APP.speak("online")
        check("the app's line reaches the process",
              wait_for(lambda: any(l.startswith("S ") for l in spawn.lines()), 10.0), spawn.lines())
        proc = spawn.started[0] if spawn.started else None
        sonar = APP.sonar
        APP.on_close()
        check("on_close kills it", proc is not None and wait_for(lambda: proc.poll() is not None, 5.0))
        check("and stops the sonar", wait_for(lambda: not sonar.running, 2.0))


print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
