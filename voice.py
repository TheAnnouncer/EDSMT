"""
Voice Mode (1.10040, #145, #146, #292): EDSMT says what it just did.

The words are the Basic voice line pack: one line for each thing the app
does, in three voices - Ship computer, Flight controller and Radio Raxxla
on-air. A recording wins when there is one: voice/<theme>/<id>.wav beside
the app or in the data folder. Without one the line is spoken by Windows'
own speech, through ONE PowerShell process kept for the whole run: started
the first time something is said, every line written to it, never a
process a line, and stopped when EDSMT closes. Anywhere but Windows nothing
is spoken.

Spoken directions are for a headset, where the overlay cannot be seen:
how far and which way, on a clock face, to the target - "Platinum, 340
metres, two o'clock" - every so often while moving and whenever the target
changes, never more than one line every three seconds.

The lines, the words for a direction and when to say them are plain logic
and need no window. The speaker takes whatever starts its process as an
argument, so the checks hand it a stand-in.
"""

import atexit
import base64
import math
import os
import queue
import re
import threading

PACK_NAME = "Basic voice line pack"

# (key, name). The key is the recordings' folder: voice/<key>/<id>.wav.
THEMES = (("ship_computer", "Ship computer"),
          ("flight_controller", "Flight controller"),
          ("on_air", "Radio Raxxla on-air"))
THEME_KEYS = tuple(key for key, _name in THEMES)
DEFAULT_THEME = "ship_computer"

_NUMBERS = ("one", "two", "three", "four", "five", "six")

# The Basic voice line pack. Each line: (Ship computer, Flight controller,
# Radio Raxxla on-air). A few are the start or the end of a sentence the
# app finishes with a number.
_TABLE = {
    "online": ("Survey systems online.",
               "EDSMT online. Standing by.",
               "Radio Raxxla here. Let's go find something worth digging."),
    "voice_test": ("Voice guidance active.",
                   "Radio check. Loud and clear.",
                   "Testing, testing. You're hearing Radio Raxxla."),
    "update_ready": ("A software update is ready to install.",
                     "Update downloaded and verified. Install when ready.",
                     "Fresh update's in the hangar. Install it when you're done out there."),
    "backup_done": ("Backup complete.",
                    "Backup written.",
                    "Your finds are backed up. Safe as houses."),
    "signal_logged": ("Signal logged. Survey centre set.",
                      "Signal marked. Centre locked.",
                      "Signal's in the book. That's our centre."),
    "border_set": ("Survey border set.",
                   "Border marked.",
                   "Edge of the patch marked. Now we sweep."),
    "deposit_marked": ("Deposit recorded.",
                       "Deposit logged.",
                       "Got it. Deposit's on the map."),
    "deposit_updated": ("Deposit updated.",
                        "Deposit amended.",
                        "Updated. Map's current."),
    "deposit_incomplete": ("Unable to record. Deposit details incomplete.",
                           "Negative. All four fields required.",
                           "Hold on. I need all four details before that goes on the map."),
    "deposit_already": ("Deposit already recorded at this position.",
                        "Already logged at this position.",
                        "That one's already on the map."),
    "mined_out": ("Deposit marked as depleted.",
                  "Deposit depleted. Logged.",
                  "Mined out. We'll check back on that one."),
    "rigs_full": ("All six rigs deployed.",
                  "Six rigs down. Full spread.",
                  "Full spread. Six rigs working."),
    "rigs_all_up": ("All rigs recovered.",
                    "All rigs up. Clear to move.",
                    "That's every rig home."),
    "rig_limit_warning": ("Warning. Approaching rig range limit.",
                          "Warning. Rig range limit.",
                          "Easy, Commander. You're nearly out of rig range."),
    "rig_lost": ("Rig signal lost.",
                 "Rig contact lost.",
                 "We've lost touch with a rig."),
    "rigs_cleared_relog": ("Rigs from the last session have been cleared.",
                           "Previous rigs cleared from the board.",
                           "Cleared the old rigs off the map. Fresh start."),
    "plan_trace_start": ("Tracing deposit edge. Return to your start point.",
                         "Tracing. Drive the edge back to start.",
                         "Drive the edge for me and bring it back round."),
    "plan_ready": ("Rig plan ready.",
                   "Plan ready. Pins set.",
                   "Pins are down. Here's your plan."),
    "pin_reached": ("On the pin. Deploy rig.",
                    "On mark. Drop the rig.",
                    "Right there. Drop a rig."),
    "next_pin": ("Next pin.",
                 "Next mark.",
                 "Next pin."),
    "plan_cancelled": ("Rig plan cancelled.",
                       "Plan scrubbed.",
                       "Plan's off."),
    "swept_half": ("Half the survey area swept.",
                   "Sweep fifty percent.",
                   "Halfway round the patch."),
    "swept_done": ("Survey area complete.",
                   "Sweep complete.",
                   "That's the whole patch swept. Nice driving."),
    "session_start": ("Mining session started.",
                      "Session running. Clock's on.",
                      "Session's on the clock. Happy mining."),
    "session_paused": ("Session paused.",
                       "Clock stopped.",
                       "Taking five. Clock's paused."),
    "session_resumed": ("Session resumed.",
                        "Clock running.",
                        "Back to work."),
    "session_end": ("Mining session complete.",
                    "Session closed. Numbers logged.",
                    "That's a wrap on this session. Check your earnings."),
    "nearest": ("Nearest deposit.",
                "Nearest.",
                "Closest one's"),
    "arrived": ("Deposit reached.",
                "On target.",
                "You're on it."),
    "none_in_range": ("No recorded deposits in range.",
                      "No contacts in range.",
                      "Nothing on the map near you yet."),
    "touchdown_hint": ("Nearest mining location:",
                       "Nearest location:",
                       "Closest mining location is number"),
    "locations_on_body": ("mining locations detected.",
                          "mining locations.",
                          "mining locations on this one."),
    "bodies_ranked": ("Landing targets ranked.",
                      "Landing list updated.",
                      "Where to land is sorted. Best first."),
    "high_gravity": ("Caution. High gravity world.",
                     "Caution. High G.",
                     "Heavy one, Commander. Watch your descent."),
    "deploy_clear": ("Clear to deploy the Rhino.",
                     "Clear to deploy.",
                     "Nice and low. Send the Rhino out."),
    "wing_linked": ("Wing link established.",
                    "Wing link up.",
                    "You're linked with the wing."),
    "wing_mate_joined": ("Wingmate connected.",
                         "Wingmate on the net.",
                         "Someone's joined the wing."),
    "wing_mate_left": ("Wingmate disconnected.",
                       "Wingmate off the net.",
                       "Wingmate's dropped off."),
    "wing_clash": ("Caution. Rig too close to a wingmate's rig.",
                   "Rig conflict with wingmate.",
                   "Careful, that's crowding a wingmate's rig."),
    "chat_ok": ("Command accepted.",
                "Copy.",
                "Heard you."),
    "chat_unknown": ("Command not recognised.",
                     "Say again. Command unknown.",
                     "Didn't catch that one."),
}
for _n, _word in enumerate(_NUMBERS, 1):
    _TABLE["rig_down_%d" % _n] = ("Rig %s deployed." % _word,
                                  "Rig %s down." % _word,
                                  "Rig %s's down." % _word)
    _TABLE["rig_up_%d" % _n] = ("Rig %s recovered." % _word,
                                "Rig %s up." % _word,
                                "Rig %s picked up." % _word)
LINES = {line_id: dict(zip(THEME_KEYS, words)) for line_id, words in _TABLE.items()}
del _TABLE


def clean_theme(theme):
    """A theme key, whatever was saved: its key or its name, else the
    Ship computer."""
    text = str(theme or "").strip()
    for key, name in THEMES:
        if text in (key, name):
            return key
    return DEFAULT_THEME


def line_text(line_id, theme=DEFAULT_THEME):
    """The words of one line in one theme, or "" for a line not in the
    pack."""
    return LINES.get(str(line_id), {}).get(clean_theme(theme), "")


def rig_line(kind, n):
    """The line for rig n going down ("down") or coming up ("up"), or ""
    for a rig the pack has no line for."""
    line_id = "rig_%s_%s" % ("up" if kind == "up" else "down", n)
    return line_id if line_id in LINES else ""


def recording(line_id, theme, folders):
    """The recording of this line in this theme - voice/<theme>/<id>.wav in
    the first folder that has one - or ""."""
    theme = clean_theme(theme)
    for folder in folders or ():
        if not folder:
            continue
        path = os.path.join(folder, "voice", theme, "%s.wav" % line_id)
        if os.path.isfile(path):
            return path
    return ""


# The speaking rate: System.Speech's own scale, -10 to 10, 0 as it ships.
RATES = (("Slower", "-4"), ("Slow", "-2"), ("Normal", "0"),
         ("Quick", "2"), ("Quicker", "4"))
DEFAULT_RATE = "0"


def clean_rate(value):
    """The rate as a whole number from -10 to 10; 0 for anything else."""
    try:
        rate = int(round(float(str(value).strip())))
    except (TypeError, ValueError):
        return 0
    return max(-10, min(10, rate))


# -- spoken directions -------------------------------------------------------

CLOCK = ("dead ahead", "one o'clock", "two o'clock", "three o'clock",
         "four o'clock", "five o'clock", "behind you", "seven o'clock",
         "eight o'clock", "nine o'clock", "ten o'clock", "eleven o'clock")
# Never more than one line in this many seconds.
GAP_S = 3.0
DIRECTIONS_EVERY_S = 10
DIRECTIONS_MIN_S, DIRECTIONS_MAX_S = 5, 60
# Closer than this the target is reached: said when it changes, not again
# and again while a rig goes down beside it.
ARRIVED_M = 25.0
# Moving: at least this fast, in metres a second.
MOVING_MPS = 1.0


def clock_words(offset_deg):
    """A turn as a clock face: 0 is dead ahead, +60 (to the right) two
    o'clock, 180 behind you, -90 nine o'clock."""
    try:
        hour = int(math.floor(float(offset_deg) / 30.0 + 0.5)) % 12
    except (TypeError, ValueError):
        hour = 0
    return CLOCK[hour]


def distance_words(metres):
    """"340 metres" to the nearest ten under a kilometre, "1.2 kilometres"
    beyond it, "1 metre" for one."""
    try:
        value = max(0.0, float(metres))
    except (TypeError, ValueError):
        return ""
    if value < 10:
        whole = max(1, int(round(value)))
        return "%d metre%s" % (whole, "" if whole == 1 else "s")
    tens = int(round(value / 10.0)) * 10
    if tens < 1000:
        return "%d metres" % tens
    km = round(value / 1000.0, 1)
    if float(km).is_integer():
        whole = int(km)
        return "%d kilometre%s" % (whole, "" if whole == 1 else "s")
    return "%.1f kilometres" % km


def direction_words(name, metres, offset_deg):
    """"Platinum, 340 metres, two o'clock"."""
    name = re.sub(r"\s+", " ", str(name or "")).strip() or "Unknown deposit"
    return "%s, %s, %s" % (name, distance_words(metres), clock_words(offset_deg))


def spoken_target(pin=None, waypoint=None, deposit=None, rig=None):
    """What the directions are about: the rig plan's next pin, else the
    guided survey's waypoint, else the target deposit, else the nearest rig.
    Each is {"key", "name", "range_m", "offset"} or None."""
    for found in (pin, waypoint, deposit, rig):
        if found and found.get("key") is not None:
            return found
    return None


def is_moving(metres, seconds):
    """Moved `metres` in `seconds` - fast enough to count as driving."""
    try:
        return float(seconds) > 0 and float(metres) / float(seconds) >= MOVING_MPS
    except (TypeError, ValueError):
        return False


def directions_every(value):
    """The repeat as saved, in whole seconds, held to 5 to 60; 10 for
    anything that is not a number."""
    try:
        seconds = int(round(float(str(value).strip())))
    except (TypeError, ValueError):
        return DIRECTIONS_EVERY_S
    return max(DIRECTIONS_MIN_S, min(DIRECTIONS_MAX_S, seconds))


class DirectionsTimer:
    """When a direction is said: at once when the target changes, every
    `every_s` while moving, and never within GAP_S of the last line."""

    def __init__(self, every_s=DIRECTIONS_EVERY_S, gap_s=GAP_S):
        self.every_s = float(every_s)
        self.gap_s = float(gap_s)
        self.last_at = None
        self.last_key = None

    def due(self, now, key, moving, metres=None):
        if key is None:
            return False
        if self.last_at is not None and now - self.last_at < self.gap_s:
            return False
        if key != self.last_key:
            return True
        if metres is not None and float(metres) <= ARRIVED_M:
            return False
        return bool(moving) and now - self.last_at >= self.every_s

    def said(self, now, key):
        self.last_at, self.last_key = now, key


# -- the session's clock -------------------------------------------------------

def session_state(books):
    """"off", "running" or "paused", from the Earnings books."""
    if books is None or getattr(books, "current", None) is None:
        return "off"
    return "paused" if getattr(books, "paused", False) else "running"


def session_line(was, now):
    """The line for a session starting, pausing, resuming or ending, or
    None when nothing changed."""
    if was == now or was is None:
        return None
    if now == "off":
        return "session_end"
    if was == "off":
        return "session_start"
    return "session_paused" if now == "paused" else "session_resumed"


# -- the survey and the wing ---------------------------------------------------

# The swept figure's marks, the higher first: passing both at once is "all".
SWEEP_MARKS = ((100, "swept_done"), (50, "swept_half"))
SWEEP_LINES = tuple(line for _mark, line in SWEEP_MARKS)


def sweep_line(was, now):
    """The line for the swept figure passing half or all of the survey
    area, or None. The first look at an area (`was` None) says nothing, so
    an area already half swept is not announced as it opens."""
    try:
        was, now = float(was), float(now)
    except (TypeError, ValueError):
        return None
    for mark, line in SWEEP_MARKS:
        if was < mark <= now:
            return line
    return None


def wing_line(first, joined, left):
    """One line for one answer from the wing link: the link up on the first
    answer, else a wingmate joining, else one leaving; None when nobody came
    or went."""
    if first:
        return "wing_linked"
    if joined:
        return "wing_mate_joined"
    if left:
        return "wing_mate_left"
    return None


# -- speaking --------------------------------------------------------------------

# One PowerShell process reads lines from its input and acts on each:
#   R <n>     the speaking rate, -10 to 10
#   S <text>  say this
#   W <path>  play this .wav to its end
# One line at a time, in order, so nothing talks over anything else.
SPEECH_SCRIPT = "\n".join((
    "$ErrorActionPreference = 'Stop'",
    "Add-Type -AssemblyName System.Speech",
    "$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer",
    "$lines = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), "
    "[System.Text.Encoding]::UTF8)",
    "while ($true) {",
    "  $line = $lines.ReadLine()",
    "  if ($line -eq $null) { break }",
    "  if ($line.Length -lt 3) { continue }",
    "  $what = $line.Substring(0, 1)",
    "  $rest = $line.Substring(2)",
    "  try {",
    "    if ($what -eq 'R') { $voice.Rate = [int]$rest }",
    "    elseif ($what -eq 'S') { $voice.Speak($rest) }",
    "    elseif ($what -eq 'W') { (New-Object System.Media.SoundPlayer $rest).PlaySync() }",
    "  } catch { }",
    "}",
))
# A window of its own would flash up over the game.
CREATE_NO_WINDOW = 0x08000000
# Lines waiting for the process; past this they are dropped - a line that
# late is no use to anybody.
QUEUE_MAX = 8
# A process that keeps dying is not started for ever.
MAX_STARTS = 3
LINE_MAX = 300


def speakable(text):
    """One line of plain text, no control characters, at most LINE_MAX."""
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(text or ""))
    return re.sub(r"\s+", " ", text).strip()[:LINE_MAX]


def powershell_command(script=SPEECH_SCRIPT, root=None):
    """The command line that runs the speech script: Windows PowerShell,
    the script handed over encoded, so no quoting can break it."""
    root = root or os.environ.get("SystemRoot") or r"C:\Windows"
    exe = os.path.join(root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    if not os.path.isfile(exe):
        exe = "powershell.exe"
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return [exe, "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]


def windows_spawn():
    """What starts the speech process on Windows; None anywhere else."""
    if os.name != "nt":
        return None

    def spawn():
        import subprocess
        return subprocess.Popen(powershell_command(), stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=CREATE_NO_WINDOW)
    return spawn


class Speaker:
    """Says lines through one process for the whole run.

    `spawn()` starts the process (a Popen, or anything with stdin, poll and
    kill); the default is Windows PowerShell, and with none nothing is said.
    The process is started the first time something is said, every line is
    written to it from a worker thread - so the window never waits - and it
    is killed by close(), which also runs at exit."""

    def __init__(self, spawn=None, folders=(), rate=0):
        self.spawn = spawn if spawn is not None else windows_spawn()
        self.folders = list(folders)
        self.rate = clean_rate(rate)
        self.proc = None
        self.starts = 0
        self.sent = 0
        self.closed = False
        self._sent_rate = None
        self._queue = queue.Queue(maxsize=QUEUE_MAX)
        self._thread = None
        self._lock = threading.Lock()
        self._atexit = False

    @property
    def available(self):
        return self.spawn is not None and not self.closed

    def set_rate(self, rate):
        self.rate = clean_rate(rate)

    def say_line(self, line_id, theme=DEFAULT_THEME):
        """One line of the pack: its recording if there is one, else its
        words. False when nothing will be said."""
        if not self.available:
            return False
        theme = clean_theme(theme)
        found = recording(line_id, theme, self.folders)
        if found:
            return self._send("W " + found)
        return self.say_text(line_text(line_id, theme))

    def say_text(self, text):
        """Any words, spoken. False when nothing will be said."""
        words = speakable(text)
        if not words or not self.available:
            return False
        return self._send("S " + words)

    def _send(self, line):
        try:
            self._queue.put_nowait((self.rate, line))
        except queue.Full:
            return False
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, name="EDSMT voice",
                                                daemon=True)
                self._thread.start()
        return True

    def _run(self):
        while True:
            item = self._queue.get()
            if item is None or self.closed:
                return
            rate, line = item
            with self._lock:
                proc = self._process()
                if proc is None:
                    continue
                try:
                    if rate != self._sent_rate:
                        self._write(proc, "R %d" % rate)
                        self._sent_rate = rate
                    self._write(proc, line)
                    self.sent += 1
                except (OSError, ValueError, AttributeError):
                    # The process has gone. The next line starts another,
                    # up to MAX_STARTS in a run.
                    self._end(proc)

    @staticmethod
    def _write(proc, line):
        proc.stdin.write((line + "\n").encode("utf-8"))
        proc.stdin.flush()

    def _process(self):
        """The running process, started if there is none. Under the lock."""
        proc = self.proc
        if proc is not None and proc.poll() is None:
            return proc
        if proc is not None:
            self._end(proc)
        if self.closed or self.starts >= MAX_STARTS:
            return None
        self.starts += 1
        try:
            self.proc = self.spawn()
        except Exception:
            # No PowerShell, or it would not start: nothing is said, and
            # nothing in the window is the worse for it.
            self.proc = None
            return None
        if self.closed:
            # Closed while it was starting: it goes at once.
            self._end(self.proc)
            return None
        self._sent_rate = None
        if not self._atexit:
            atexit.register(self.close)
            self._atexit = True
        return self.proc

    def _end(self, proc):
        """Kill it first: a write stuck on a full pipe is let go by that,
        and closing its input after cannot then wait on the writer."""
        if proc is self.proc:
            self.proc = None
        for step in ("kill", "close_stdin", "wait"):
            try:
                if step == "kill":
                    if proc.poll() is None:
                        proc.kill()
                elif step == "close_stdin":
                    proc.stdin.close()
                else:
                    proc.wait(timeout=2)
            except Exception:
                pass

    def close(self):
        """Stop speaking for good: the process is killed, the thread ends.
        Never waits on the worker's lock - the kill is what frees it."""
        self.closed = True
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        proc = self.proc
        if proc is not None:
            self._end(proc)
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
