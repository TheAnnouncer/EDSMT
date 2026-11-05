"""1.10040: Celestia, the main voice, with comms that follow where you are.

Celestia - the Celestial Event Liaison & Tactical Information Algorithm,
Radio Raxxla's voice of the Void - is the first theme of the Basic voice
line pack, and the one a new install uses. Every line comes in three recordings, one for
each place the commander can be: in the ship, in the Rhino SRV or on foot,
each with its own comm sound. The app picks the one for where the game says
the commander is; with none for that place it falls back to the ship's,
then to a plain recording. The Ship computer and the other themes stay.

Her lines carry acting directions in square brackets - [sighs], [scoffs] -
for the recording; Windows' own voice, when there is no recording, never
reads them out.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_celestia.py
"""
import math
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-celestia-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import commfx as CFX   # noqa: E402
import voice as VO      # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


print("== Celestia is the main voice ==")
check("she is the first theme", VO.THEMES[0] == ("celestia", "Celestia"), VO.THEMES[:2])
check("and a new install's", VO.DEFAULT_THEME == "celestia")
check("the Ship computer and the others are still there",
      [k for k, _n in VO.THEMES[1:]] == ["ship_computer", "flight_controller", "on_air"], VO.THEMES)
check("a theme that is not one is Celestia", VO.clean_theme("bogus") == "celestia")
missing = [i for i in VO.LINES if not VO.line_text(i, "celestia")]
check("every line has her words", not missing, missing[:5])
check("she says Commander, never CMDR",
      not any("CMDR" in VO.line_text(i, "celestia") for i in VO.LINES)
      and any("Commander" in VO.line_text(i, "celestia") for i in VO.LINES))
check("the line Windows would read has no acting directions in it",
      not any("[" in VO.line_text(i, "celestia") or "]" in VO.line_text(i, "celestia") for i in VO.LINES))
check("the recording script keeps them", "[sighs]" in VO.script("deposit_incomplete", "celestia")
      and VO.line_text("deposit_incomplete", "celestia").startswith("I need all four"),
      (VO.script("deposit_incomplete", "celestia"), VO.line_text("deposit_incomplete", "celestia")))
check("a theme without directions: its script is its words",
      VO.script("online", "ship_computer") == VO.line_text("online", "ship_computer"))
check("rig three, down and up, in her words",
      VO.line_text("rig_down_3", "celestia") == "Rig three, down."
      and VO.line_text("rig_up_3", "celestia") == "Rig three, back aboard.",
      (VO.line_text("rig_down_3", "celestia"), VO.line_text("rig_up_3", "celestia")))

print("== where the commander is ==")
check("in the SRV", VO.place_of(in_srv=True, on_foot=False) == "srv")
check("on foot", VO.place_of(in_srv=False, on_foot=True) == "foot")
check("otherwise the ship", VO.place_of(in_srv=False, on_foot=False) == "ship"
      and VO.place_of() == "ship")
check("the SRV wins if both flags are up", VO.place_of(in_srv=True, on_foot=True) == "srv")


class Game:
    def __init__(self, in_srv=False, on_foot=False):
        self.in_srv, self.on_foot = in_srv, on_foot


check("from the game's state", VO.place_from(Game(in_srv=True)) == "srv"
      and VO.place_from(Game(on_foot=True)) == "foot" and VO.place_from(None) == "ship"
      and VO.place_from(object()) == "ship")

print("== the recording to play ==")
root = os.path.join(TMP, "app")


def make(*parts, data=None):
    path = os.path.join(root, "voice", *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if data is None:
        open(path, "wb").close()
    else:
        CFX.write_wav(path, data)
    return path


SPEECH = [0.4 * math.sin(2 * math.pi * 300 * i / 22050) * (0.6 + 0.4 * math.sin(i / 700.0))
          for i in range(22050)]
clean = make("celestia", "rigs_full.wav", data=SPEECH)
made_for_srv = make("celestia", "srv", "rigs_full.wav")
short = make("celestia", "short", "online.wav")
normal_online = make("celestia", "online.wav")
take2 = make("celestia", "chatty", "online-2.wav")
check("the clean recording, wherever the commander is",
      VO.recording("rigs_full", "celestia", [root], place="foot") == clean)
check("one made for the place wins, played as it is",
      VO.recording("rigs_full", "celestia", [root], place="srv") == made_for_srv
      and not VO.needs_comms(made_for_srv, "celestia"))
check("a clean one gets the comm sound", VO.needs_comms(clean, "celestia")
      and not VO.needs_comms(clean, "ship_computer"))
check("Short plays the short recording", VO.recording("online", "celestia", [root], detail="short") == short)
check("a later Chatty take plays its own", VO.recording("online", "celestia", [root], take=2) == take2)
check("a take with no recording of its own falls back to the line's",
      VO.recording("online", "celestia", [root], take=3) == normal_online)
check("a theme without comms still finds its plain recordings",
      VO.recording("online", "ship_computer", [REPO], place="srv").endswith(
          os.path.join("voice", "ship_computer", "online.wav")))
check("a place that is not one cannot reach outside the voice folder",
      VO.recording("rigs_full", "celestia", [root], place="../../x") == clean)

print("== Short, Normal, Chatty ==")
check("three lengths, Normal to begin with", [k for k, _n in VO.DETAILS] == ["short", "normal", "chatty"]
      and VO.DEFAULT_DETAIL == "normal" and VO.clean_detail("CHATTY") == "chatty"
      and VO.clean_detail("bogus") == "normal")
check("Short says the brief line", VO.line_text("deposit_incomplete", "celestia", "short")
      == "All four details, please.")
check("a line with no short form says its Normal one",
      VO.line_text("nearest", "celestia", "short") == VO.line_text("nearest", "celestia"))
check("Chatty lines have more than one take", VO.take_count("online", "celestia") == 3
      and VO.take_count("rig_limit_warning", "celestia") == 1 and VO.take_count("online", "ship_computer") == 1)
check("the reminders, reactions and asides are hers",
      len(VO.HINT_IDS) == 6 and len(VO.REACTION_IDS) >= 10 and len(VO.LORE_IDS) >= 10
      and all(VO.line_text(i, "celestia") for i in VO.HINT_IDS + VO.REACTION_IDS + VO.LORE_IDS))
check("no pack is named in a reminder",
      not any(word in VO.script(i, "celestia", take=t).lower() for i in VO.HINT_IDS
              for t in (1, 2) for word in ("hcs", "voicepack", "voice pack")))
check("no line names CMDR",
      not any("CMDR" in VO.script(i, "celestia", take=t) for i in VO.TAKES for t in range(1, 4)))

print("== the comm sound ==")
check("three places", CFX.PLACES == ("ship", "srv", "foot") and CFX.clean_place("x") == "ship")
for place in CFX.PLACES:
    out = CFX.apply(SPEECH, 22050, place, seed=1)
    rms, peak = CFX.level(out)
    lead = int(CFX.PRE_S * CFX.OUT_RATE)
    check("%s: levelled, with a tone before the voice, longer than the line" % place,
          abs(20 * math.log10(rms) - CFX.TARGET_RMS_DB) < 1.5 and peak <= 10 ** (CFX.PEAK_DB / 20) + 1e-6
          and max(abs(v) for v in out[:int(0.03 * CFX.OUT_RATE)]) > 0.02
          and len(out) > len(SPEECH) + lead, (rms, peak, len(out)))
band = CFX.lowpass(CFX.highpass([math.sin(2 * math.pi * 8000 * i / 22050) for i in range(4410)], 380, 22050),
                   3100, 22050)
check("the SRV's band cuts what the Rhino's set cannot carry", CFX.level(band[2000:])[0] < 0.1,
      CFX.level(band[2000:]))
cache = os.path.join(TMP, "cache")
first = CFX.cached(clean, "srv", cache)
check("worked out once into the cache", first != clean and os.path.isfile(first)
      and first.startswith(os.path.join(cache, "srv")))
before = os.path.getmtime(first)
check("and taken from it the next time", CFX.cached(clean, "srv", cache) == first
      and os.path.getmtime(first) == before)
samples, rate = CFX.read_wav(first)
check("what it writes is what the Windows player plays: mono, 22 kHz, 16-bit",
      rate == 22050 and len(samples) > 0)
broken = make("celestia", "broken.wav")
check("a recording it cannot read is played as it is", CFX.cached(broken, "ship", cache) == broken)


class Spawner:
    def __init__(self):
        self.written = []

    def __call__(self):
        outer = self

        class Proc:
            class stdin:
                @staticmethod
                def write(data):
                    outer.written.append(data)

                @staticmethod
                def flush():
                    pass

            @staticmethod
            def poll():
                return None

            @staticmethod
            def kill():
                pass

        return Proc()


print("== the speaker ==")
spawn = Spawner()
speaker = VO.Speaker(spawn=spawn, folders=[root], cache_dir=cache)
said = []
real_send = speaker._send
speaker._send = lambda line: said.append(line) or True
speaker.say_line("rigs_full", "celestia", place="srv")
speaker.say_line("rigs_full", "celestia", place="foot")
speaker.say_line("deposit_incomplete", "celestia", place="foot")
check("one made for the SRV is played as it is", said and said[0] == "W " + made_for_srv, said[:1])
check("on foot, the clean one goes for its comm sound", len(said) > 1 and said[1] == ("FX", clean, "foot"),
      said[1:2])
check("with no recording, her words without the directions",
      len(said) > 2 and said[2].startswith("S I need all four") and "[" not in said[2], said[2:3])
speaker._send = real_send
speaker.say_line("rigs_full", "celestia", place="ship")
wrote = []
for _ in range(100):
    wrote = [w.decode("utf-8") for w in spawn.written]
    if any(w.startswith("W ") for w in wrote):
        break
    time.sleep(0.05)
played = [w.strip()[2:] for w in wrote if w.startswith("W ")]
check("the worker plays the ship's comm version from the cache",
      played and played[0].startswith(os.path.join(cache, "ship")) and os.path.isfile(played[0]), wrote)
speaker.close()
chatty = VO.Speaker(spawn=Spawner(), folders=[root])
picks = [chatty.pick_take("online", "celestia", "chatty") for _ in range(30)]
check("Chatty picks among the takes, never the same twice running",
      set(picks) <= {1, 2, 3} and len(set(picks)) > 1 and all(a != b for a, b in zip(picks, picks[1:])), picks)
check("Normal always says take one", {chatty.pick_take("online", "celestia", "normal") for _ in range(5)} == {1})

print("== the bundle ==")
pack = os.path.join(REPO, "voice", "celestia")
for spec_name in ("EDSMT.spec", "EDSMT-onefile.spec"):
    spec = open(os.path.join(REPO, "build", spec_name), encoding="utf-8").read()
    check("%s bundles every voice folder under voice/" % spec_name,
          'os.path.join(ROOT, "voice", "**", "*.wav")' in spec and "recursive=True" in spec)
if os.path.isdir(pack):
    have = sorted(n[:-4] for n in os.listdir(pack) if n.endswith(".wav"))
    check("Celestia: every line and every one of her own recorded", have == sorted(VO.TAKES),
          (sorted(set(VO.TAKES) - set(have))[:5], sorted(set(have) - set(VO.TAKES))[:5]))
    want = {os.path.join("chatty", "%s-%d.wav" % (line_id, n))
            for line_id, takes in VO.TAKES.items() for n in range(2, len(takes) + 1)}
    want |= {os.path.join("short", "%s.wav" % line_id) for line_id, words in VO.SHORT.items()
             if words != VO.TAKES[line_id][0]}
    found = {os.path.join(sub, n) for sub in ("chatty", "short") if os.path.isdir(os.path.join(pack, sub))
             for n in os.listdir(os.path.join(pack, sub)) if n.endswith(".wav")}
    check("Celestia: every Chatty take and every Short line that differs recorded, nothing spare",
          found == want, (sorted(want - found)[:5], sorted(found - want)[:5]))
    import wave
    bad = []
    for folder, _dirs, files in os.walk(pack):
        for n in files:
            if n.endswith(".wav"):
                with wave.open(os.path.join(folder, n), "rb") as w:
                    if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, 22050) \
                            or not 0.3 < w.getnframes() / 22050.0 < 12.0:
                        bad.append(n)
    check("Celestia: every recording 22,050 Hz mono 16-bit, a sensible length", not bad, bad[:5])
else:
    print("  NOTE  voice/celestia not recorded yet - Windows' voice reads her words until it is")

print("== in the app ==")
try:
    import edsmt as A
except Exception as exc:   # noqa: BLE001 - a missing display is reported, not raised
    A = None
    print("  SKIP  the app did not load: %s" % exc)
if A is not None:
    class FakeSpeaker:
        def __init__(self):
            self.lines, self.rates, self.folders = [], [], []

        def set_rate(self, rate):
            self.rates.append(rate)

        def say_line(self, line_id, theme=None, place=None, detail=None):
            self.lines.append((line_id, theme, place))
            self.details = getattr(self, "details", []) + [detail]
            return True

    app = A.EDSMT.__new__(A.EDSMT)
    app.settings = dict(A.DEFAULT_SETTINGS)
    app.settings.update(voice_mode=True)
    app.voice = FakeSpeaker()
    check("a new install speaks as Celestia", A.DEFAULT_SETTINGS["voice_theme"] == "celestia")
    app.game = Game(in_srv=True)
    app.speak("rigs_full")
    check("in the SRV, the line goes with the SRV's place",
          app.voice.lines[-1] == ("rigs_full", "celestia", "srv"), app.voice.lines)
    app.game = Game(on_foot=True)
    app.speak("deposit_marked")
    check("on foot, on foot's", app.voice.lines[-1] == ("deposit_marked", "celestia", "foot"))
    del app.game
    app.speak("online")
    check("before the game says anything, the ship's", app.voice.lines[-1] == ("online", "celestia", "ship"))
    check("a new install: Normal length, reminders left to follow what is found",
          A.DEFAULT_SETTINGS["voice_detail"] == "normal" and A.DEFAULT_SETTINGS["voice_pack_hints"] is None)
    app.settings["voice_detail"] = "short"
    app.speak("deposit_marked")
    check("the answer length goes to the speaker", app.voice.details[-1] == "short", app.voice.details)
    app.settings["voice_detail"] = "normal"

    print("== her cues, from the journal ==")
    import time as _time
    import voicecues as VC

    def stamp(when):
        return _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(when))

    class Reader:
        def __init__(self, events, flags=0):
            self.events, self.flags = list(events), flags

        def take_voice_events(self):
            out, self.events = self.events, []
            return out

    def run_cues(app, start, seconds):
        said = []
        for t in range(seconds):
            line = app.follow_cues(start + t)
            if line:
                said.append(line)
        return said

    T0 = 1793860000.0
    app.voice = FakeSpeaker()
    app.cues, app.pack_hints_found = VC.Cues(), True
    app.watcher = Reader([{"event": "Touchdown", "PlayerControlled": True, "timestamp": stamp(T0)}])
    said = run_cues(app, T0, 40)
    check("a touchdown just now: Deploy the SRV, after its grace, said by Celestia",
          said == ["hint_deploy_srv"] and app.voice.lines[-1][0] == "hint_deploy_srv", (said, app.voice.lines[-3:]))
    app.cues, app.voice = VC.Cues(), FakeSpeaker()
    app.watcher = Reader([{"event": "Touchdown", "PlayerControlled": True, "timestamp": stamp(T0 - 3600)}])
    check("one read back from an hour ago: nothing", run_cues(app, T0, 40) == [] and app.voice.lines == [])
    app.cues = VC.Cues()
    app.pack_hints_found = False
    app.watcher = Reader([{"event": "Touchdown", "PlayerControlled": True, "timestamp": stamp(T0)}])
    check("no voice pack found, switch left alone: no reminder", run_cues(app, T0, 40) == [])
    app.cues, app.pack_hints_found = VC.Cues(), True
    app.settings["voice_theme"] = "ship_computer"
    app.watcher = Reader([{"event": "Touchdown", "PlayerControlled": True, "timestamp": stamp(T0)}])
    check("another voice: no reminder (they are Celestia's)", run_cues(app, T0, 40) == [])
    app.settings["voice_theme"] = "celestia"
    app.cues = VC.Cues()
    app.settings["voice_mode"] = False
    app.watcher = Reader([{"event": "Touchdown", "PlayerControlled": True, "timestamp": stamp(T0)}])
    check("Voice Mode off: nothing", run_cues(app, T0, 40) == [])
    app.settings["voice_mode"] = True
    app.cues = VC.Cues()
    app.settings["voice_detail"] = "chatty"
    app.watcher = Reader([{"event": "LaunchSRV", "PlayerControlled": True, "timestamp": stamp(T0)}])
    said = run_cues(app, T0, 10)
    check("Chatty: she reacts to the Rhino going out", said[:1] == ["react_launch_srv"], said)
    app.settings["voice_detail"] = "normal"
    app.cues = VC.Cues()
    app.rig_event("RigDown", 1)
    app.rig_event("RigsUp")
    check("the last rig up is a cue for her", app.cues.rigs_up is True)

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
