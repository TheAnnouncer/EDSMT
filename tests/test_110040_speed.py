"""1.10040: the journal read faster, a chunk at a time, off the window's
thread (#254, #276) - and nothing it reads any different.

Measured first: on a 500,000-line journal the first read spent a quarter of
its time tidying the same few commodity names over and over, another
quarter parsing lines nothing reads (chat, music, signals), and held the
whole file in memory. Now names are remembered, those lines are skipped on
their name, and a long journal is read on a thread a few megabytes at a
time while the window says how far it has got. The older journals are read
a chunk at a time too. This checks that every one of those reads the same
as before, then times them against budgets.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_speed.py
"""
import faulthandler
import json
import os
import re
import sys
import tempfile
import time
import tracemalloc

faulthandler.dump_traceback_later(300, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-speed-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import catchup as CU    # noqa: E402
import journal as JN    # noqa: E402
import survey as SV     # noqa: E402
import shiphold as SH   # noqa: E402

JN.EVENT_LOG = None
fails = []

# The budgets, each several times what it measures here, for a slow machine.
READ_100K_BUDGET_S = 3.0        # 100,000 lines read in one go (measured ~0.5 s)
FOLD_BUDGET_S = 0.5             # 200,000 names folded (measured ~0.05 s)
GAP_BUDGET_S = 1.0              # the longest the window stands still meanwhile
# When the app's reader takes over the journal the thread read, once: 1.13 s
# on a Windows desktop for an 8 MB journal (5 Nov 2026), 0.2 s in the cloud.
HANDOVER_BUDGET_S = 2.0


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


def stamp(i, start=1791478800):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start + i))


def line(event):
    return json.dumps(event, separators=(", ", ":"), ensure_ascii=False) + "\r\n"


def session_lines(t, system="Col 285 Sector KB-W c2-14", body="Col 285 Sector KB-W c2-14 A 1"):
    """A Rhino session in the shapes the game writes: launch, tonnes, two
    transfers, the dock and the ship's hold after it."""
    out = [{"timestamp": stamp(t), "event": "Location", "StarSystem": system,
            "SystemAddress": 77, "StarPos": [1.0, 2.0, 3.0], "Body": body, "BodyType": "Planet",
            "Docked": False, "Latitude": 1.0, "Longitude": 2.0},
           {"timestamp": stamp(t + 1), "event": "Cargo", "Vessel": "Ship", "Count": 0},
           {"timestamp": stamp(t + 2), "event": "LaunchSRV", "SRVType": "mev_rhino",
            "SRVType_Localised": "SRV Rhino", "Loadout": "galactic", "ID": 98, "PlayerControlled": True}]
    for k in range(40):
        out.append({"timestamp": stamp(t + 10 + k), "event": "MiningRefined", "Type": "$iridium_name;",
                    "Type_Localised": "Iridium"})
        out.append({"timestamp": stamp(t + 10 + k), "event": "Cargo", "Vessel": "SRV", "Count": k + 1})
    out.append({"timestamp": stamp(t + 60), "event": "CargoTransfer", "Transfers": [
        {"Type": "iridium", "Type_Localised": "Iridium", "Count": 40, "Direction": "toship"}]})
    out.append({"timestamp": stamp(t + 70), "event": "DockSRV", "SRVType": "mev_rhino",
                "SRVType_Localised": "SRV Rhino", "ID": 98})
    out.append({"timestamp": stamp(t + 76), "event": "Cargo", "Vessel": "Ship", "Count": 40})
    return out


def write_journal(folder, lines, name="Journal.2026-10-08T170000.01.log", session=True):
    """A journal of about `lines` lines: mostly what nothing reads, some of
    everything that is read, names with accents, and a session at the end."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    head = [{"timestamp": stamp(0), "event": "Fileheader", "part": 1, "language": "English/UK",
             "Odyssey": True, "gameversion": "4.4.1.1", "build": "r1 "},
            {"timestamp": stamp(0), "event": "Commander", "FID": "F123", "Name": "Test Pilot"},
            {"timestamp": stamp(0), "event": "LoadGame", "FID": "F123", "Commander": "Test Pilot",
             "Ship": "panthermkii", "ShipID": 7, "GameMode": "Solo"},
            {"timestamp": stamp(0), "event": "Loadout", "Ship": "panthermkii", "ShipID": 7,
             "CargoCapacity": 1239, "MaxJumpRange": 20.5, "Modules": []},
            {"timestamp": stamp(0), "event": "Powerplay", "Power": "Nakato Kaine", "Rank": 300,
             "Merits": 10, "TimePledged": 100}]
    filler = [
        lambda i: {"timestamp": stamp(i), "event": "ReceiveText", "From": "Ünal %d" % (i % 9),
                   "Message": "o7 – nice day for it " * 2, "Channel": "local"},
        lambda i: {"timestamp": stamp(i), "event": "Music", "MusicTrack": "Exploration"},
        lambda i: {"timestamp": stamp(i), "event": "FSSSignalDiscovered", "SystemAddress": 5,
                   "SignalName": "Carrier X%d" % (i % 99), "IsStation": True},
        lambda i: {"timestamp": stamp(i), "event": "MiningRefined", "Type": "$platinum_name;",
                   "Type_Localised": "Platine"},
        lambda i: {"timestamp": stamp(i), "event": "FSDJump", "StarSystem": "Sÿs %d" % (i % 300),
                   "SystemAddress": 1000 + i % 300, "StarPos": [i % 97 * 1.0, 2.0, 3.0],
                   "Body": "Sÿs %d" % (i % 300), "BodyType": "Star", "ControllingPower": "Nakato Kaine",
                   "Powers": ["Nakato Kaine"], "PowerplayState": "Exploited"},
        lambda i: {"timestamp": stamp(i), "event": "Scan", "ScanType": "Detailed",
                   "BodyName": "Sÿs %d A %d" % (i % 300, i % 5), "StarSystem": "Sÿs %d" % (i % 300),
                   "PlanetClass": "Rocky body", "Radius": 1500000.0, "SurfaceGravity": 1.2,
                   "SurfaceTemperature": 180.0, "Landable": True},
        lambda i: {"timestamp": stamp(i), "event": "ProspectedAsteroid", "Materials": [
            {"Name": "Platinum", "Proportion": 30.0}], "Content": "$AsteroidMaterialContent_High;"},
        lambda i: {"timestamp": stamp(i), "event": "SendText", "To": "local", "Message": "#rr hello"},
        lambda i: {"timestamp": stamp(i), "event": "ShipTargeted", "TargetLocked": False},
        lambda i: {"timestamp": stamp(i), "event": "Docked", "StationName": "Ørsted Hub",
                   "StarSystem": "Sÿs %d" % (i % 300), "MarketID": 9, "StationType": "Coriolis"},
        lambda i: {"timestamp": stamp(i), "event": "MarketSell", "MarketID": 9, "Type": "platinum",
                   "Type_Localised": "Platine", "Count": 3, "SellPrice": 200000, "TotalSale": 600000,
                   "AvgPricePaid": 0},
        lambda i: {"timestamp": stamp(i), "event": "Undocked", "StationName": "Ørsted Hub"},
    ]
    weights = [30, 8, 12, 10, 2, 3, 3, 1, 4, 1, 1, 1]
    order = [k for k, w in enumerate(weights) for _ in range(w)]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        for event in head:
            handle.write(line(event))
        count = len(head)
        i = 10
        while count < lines:
            handle.write(line(filler[order[i % len(order)]](i)))
            i += 1
            count += 1
        if session:
            for event in session_lines(i + 100):
                handle.write(line(event))
    return path


def state_of(reader):
    """Everything a read of the journal leaves in a reader, for comparing."""
    names = ("system", "body", "star_pos", "system_address", "cmdr", "fid", "game_version",
             "journal_part", "ship_id", "ship_type", "capacities", "cargo_capacity",
             "max_jump_ly", "ship_total", "srv_total", "rhino_out", "trip_unloaded", "honked",
             "body_counts", "body_signals", "body_facts", "power", "power_rank", "power_merits",
             "power_here", "station", "docked", "wing", "approached", "vehicle_id",
             "vehicle_kinds", "pending_runs", "pending_power", "pending_chat", "unknown_events",
             "last_event", "_tail")
    return {name: json.dumps(getattr(reader, name, None), sort_keys=True, default=str)
            for name in names}


def differences(a, b):
    return [name for name in a if a[name] != b[name]]


print("== names remembered, read the same ==")


def old_fold(text):
    import unicodedata
    raw = unicodedata.normalize("NFKD", str(text or ""))
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return "".join(c for c in raw.lower() if c.isalnum())


SAMPLES = ["Bastnäsite", "$bastnasite_name;", "BASTNASITE", "Low Temperature Diamonds", "", None,
           "lowtemperaturediamond", "Platine", 12, "Ørsted", "Rhodplumsite "]
check("a remembered fold folds as the old one did", all(SV.fold(t) == old_fold(t) for t in SAMPLES),
      [(t, SV.fold(t), old_fold(t)) for t in SAMPLES if SV.fold(t) != old_fold(t)])
started = time.perf_counter()
for _ in range(20000):
    for text in ("$iridium_name;", "Iridium", "Platinum", "Bastnäsite", "rhodplumsite",
                 "$platinum_name;", "Platine", "Osmium", "Haematite", "Serendibite"):
        SV.fold(text)
took = time.perf_counter() - started
print("        200,000 names folded in %.3f s" % took)
check("200,000 names fold within %.1f s" % FOLD_BUDGET_S, took < FOLD_BUDGET_S, "%.3f s" % took)
check("a hold's name is the same remembered", all(
    JN.hold_label(sym, loc) == (SV.english_name(sym, loc) or str(loc or sym or ""))
    for sym, loc in (("$iridium_name;", "Iridium"), ("$platinum_name;", "Platine"), ("water", "Eau"),
                     (None, "Gold"), ("", None), ("$zzqbar_name;", "Zzqbar"))))
before = JN.hold_label("$zzqfoo_name;", "Zzqfoo")
SV.remember("zzq_foo")
check("and asked again once a new commodity is learnt",
      before == "Zzqfoo" and JN.hold_label("$zzqfoo_name;", "Zzqfoo") == "Zzq Foo",
      (before, JN.hold_label("$zzqfoo_name;", "Zzqfoo")))

print("== lines nothing reads are skipped, and nothing else is ==")
MIXED = os.path.join(TMP, "mixed")
write_journal(MIXED, 3000)
one = JN.JournalWatcher(MIXED)
one._read_journal()
every = JN.JournalWatcher(MIXED)
every.PARSE_ALL = True
every._read_journal()
check("skipping them reads the same as parsing every line",
      not differences(state_of(one), state_of(every)), differences(state_of(one), state_of(every)))
check("and the journal was really read", one.cmdr == "Test Pilot" and one.power == "Nakato Kaine"
      and one.capacities.get(7, (0,))[0] == 1239 and one.pending_chat and one.honked is not None,
      (one.cmdr, one.power, one.capacities))
source = open(os.path.join(REPO, "journal.py"), encoding="utf-8").read()
body = source[source.index("    def _consume(self, text):"):source.index("    def _record_body(")]
named = set(re.findall(r'name == "(\w+)"', body))
for group in re.findall(r"name in \(([^)]*)\)", body):
    named |= set(re.findall(r'"(\w+)"', group))
missing = sorted(n for n in named if JN.skipped(n))
check("every event the reader acts on is one it parses", not missing and len(named) > 10, missing)
check("chat, music and signals are not", all(JN.skipped(n) for n in (
    "ReceiveText", "Music", "FSSSignalDiscovered", "ShipTargeted", "Friends")))
check("an event the mining hint would log is parsed", not JN.skipped("ProspectedAsteroid")
      and not JN.skipped("SomeNewDepositEvent"))


class Counting:
    """json, counting loads()."""

    def __init__(self):
        self.calls = 0

    def loads(self, text):
        self.calls += 1
        return json.loads(text)

    def __getattr__(self, name):
        return getattr(json, name)


counter = Counting()
JN.json = counter
try:
    JN.JournalWatcher(MIXED)._read_journal()
finally:
    JN.json = json
lines_in = sum(1 for _ in open(os.path.join(MIXED, os.listdir(MIXED)[0]), encoding="utf-8"))
print("        %d of %d lines parsed" % (counter.calls, lines_in))
check("about half the lines of a journal like this are never parsed",
      0 < counter.calls < lines_in * 0.6, (counter.calls, lines_in))

print("== a chunk at a time reads the same as all at once ==")
chunked = JN.JournalWatcher(MIXED)
steps = 0
while True:
    read, size, moved = chunked.catch_up_step(97)
    steps += 1
    if not moved:
        break
check("in 97-byte chunks - lines and accents cut in half - the reader ends the same",
      not differences(state_of(one), state_of(chunked)), differences(state_of(one), state_of(chunked)))
check("and it took many steps, ending at the end", steps > 1000 and read == size, (steps, read, size))
data = open(os.path.join(MIXED, os.listdir(MIXED)[0]), "rb").read()
want = data.split(b"\n")
want = want[:-1] if want and want[-1] == b"" else want
check("lines_of gives the file's lines, a chunk at a time",
      list(CU.lines_of(os.path.join(MIXED, os.listdir(MIXED)[0]), chunk=101)) == want)
check("contains finds what is there across a chunk's edge, and not what is not",
      CU.contains(os.path.join(MIXED, os.listdir(MIXED)[0]), b'"DockSRV"', chunk=300)
      and CU.contains(os.path.join(MIXED, os.listdir(MIXED)[0]), re.compile(rb'"Statistic|"Loadout"'), chunk=300)
      and not CU.contains(os.path.join(MIXED, os.listdir(MIXED)[0]), b"nowhere-at-all", chunk=300))
check("the progress words", CU.progress_note(45, 100).startswith("Reading your journal from the top: 45%")
      and CU.progress_note(0, 0).startswith("Reading your journal from the top: 0%"))

print("== 100,000 lines, timed ==")
BIG = os.path.join(TMP, "big")
path = write_journal(BIG, 100000)
size = os.path.getsize(path)
print("        a %.1f MB journal" % (size / 1e6))
reader = JN.JournalWatcher(BIG)
tracemalloc.start()
started = time.perf_counter()
reader._read_journal()
took = time.perf_counter() - started
whole_peak = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
print("        read in one go in %.2f s, %.0f MB at the most" % (took, whole_peak / 1e6))
check("100,000 lines read within %.1f s" % READ_100K_BUDGET_S, took < READ_100K_BUDGET_S, "%.2f s" % took)
check("the session at the end is in what the books are given",
      any(n.get("event") == "SRVDock" for n in reader.pending_runs))
job = CU.CatchUp(JN.JournalWatcher(BIG), chunk=1024 * 1024)
tracemalloc.start()
job.start()
seen = []
until = time.time() + 60
while not job.done() and time.time() < until:
    seen.append(job.progress()[0])
    time.sleep(0.005)
chunk_peak = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
print("        on its own thread, 1 MB at a time: %.0f MB at the most" % (chunk_peak / 1e6))
check("on its own thread it finishes, with no fault", job.done() and job.error is None, job.error)
check("its progress only goes up, and ends at the whole file",
      seen == sorted(seen) and job.progress() == (size, size), (job.progress(), size))
check("it read the same as all at once", not differences(state_of(reader), state_of(job.reader)),
      differences(state_of(reader), state_of(job.reader)))
check("holding a fraction of the memory: a quarter of what all at once takes, and less than the file",
      chunk_peak < whole_peak / 4 and chunk_peak < size, (chunk_peak, whole_peak, size))
quitter = CU.CatchUp(JN.JournalWatcher(BIG), chunk=4096)
quitter.start()
quitter.stop()
check("stopped, it ends after the chunk it is on", quitter.wait(5) and quitter.progress()[0] < size,
      quitter.progress())

live = JN.JournalWatcher(BIG)
live.adopt(job.reader)
check("the app's reader takes over all it read", not differences(state_of(live), state_of(reader))
      and live._pos == size and job.reader._handle is None)
with open(path, "a", encoding="utf-8", newline="") as handle:
    handle.write(line({"timestamp": stamp(999999), "event": "FSDJump", "StarSystem": "After The Read",
                       "SystemAddress": 4, "StarPos": [0.0, 0.0, 0.0]}))
live.poll()
check("and goes on from where it got to", live.system == "After The Read", live.system)

print("== the older journals, a chunk at a time ==")
book = SH.CapacityBook(os.path.join(TMP, "holds"))
CU.CHUNK_BYTES = 1024 * 1024
tracemalloc.start()
learnt = book.learn_file(path)
older_peak = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
print("        a ship's holds learnt from it with %.0f MB at the most" % (older_peak / 1e6))
check("a ship's hold is learnt from an older journal without holding it whole",
      learnt == 1 and older_peak < size / 2, (learnt, older_peak, size))
CU.CHUNK_BYTES = 4 * 1024 * 1024

try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as exc:
    print("  SKIP  the rest needs a display (%s). Run it under xvfb-run." % exc)
    print()
    print("FAILURES:", len(fails))
    sys.exit(1 if fails else 0)

print("== the window, while a long journal is read ==")
import overlay as OV  # noqa: E402
OV.foreground_is_game = lambda: None
import edsmt as A     # noqa: E402

A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
GAME = os.path.join(TMP, "game")
write_journal(GAME, 60000)
CU.THREAD_FROM_BYTES = 1024 * 1024
CU.CHUNK_BYTES = 512 * 1024
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as handle:
    json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": GAME,
               "welcome_seen_version": A.APP_VERSION}, handle)
said = []
real_say = A.EDSMT.say


def say(self, text, colour=None):
    said.append(str(text))
    return real_say(self, text, colour)


A.EDSMT.say = say
app = A.EDSMT()
app.geometry("1200x800+0+0")
app.updates.check = lambda *args, **kwargs: None
beats = []


after = []


def beat():
    # Counted while the journal is being read on its thread, and for a few
    # seconds after, which takes in the reader taking over what it read.
    if getattr(app, "_catch_up", None) is not None:
        beats.append(time.perf_counter())
    elif beats and time.perf_counter() - beats[-1] < 4.0:
        after.append(time.perf_counter())
    app.after(20, beat)


app.after(20, beat)
until = time.time() + 120
while time.time() < until:
    app.update_idletasks()
    app.update()
    if getattr(app, "_catch_up", None) is None and app.watcher._journal is not None \
            and app.watcher.cmdr:
        break
    time.sleep(0.005)
until = time.time() + 4.5
while time.time() < until:
    app.update_idletasks()
    app.update()
    time.sleep(0.005)
gaps = [b - a for a, b in zip(beats, beats[1:])]
gap = max(gaps) if gaps else 99.0
print("        the longest the window stood still: %.2f s, over %d beats (%s)" % (
    gap, len(beats), ", ".join("%.2f" % g for g in sorted(gaps)[-4:])))
check("the journal was read on its own thread, and the window said how far it had got",
      any(t.startswith("Reading your journal from the top") for t in said), said[:5])
check("the window kept going: never still for %.1f s" % GAP_BUDGET_S, gap < GAP_BUDGET_S and len(beats) > 20,
      (gap, len(beats)))
handover = max([b - a for a, b in zip(beats[-1:] + after, after)] or [99.0])
print("        and when the app's reader took over: %.2f s" % handover)
check("nor, beyond a moment, when the app's reader takes over what it read", handover < HANDOVER_BUDGET_S, handover)
check("once read, the app's reader has the journal's commander and ship",
      app.watcher.cmdr == "Test Pilot" and app.watcher.capacities.get(7, (0,))[0] == 1239,
      (app.watcher.cmdr, app.watcher.capacities))
check("and the session in it is in the books",
      any("Iridium" in str(row.get("mined")) for row in app.earnings.sessions),
      [(r.get("mined"), r.get("transferred")) for r in app.earnings.sessions])
check("and it says it is up to date", any(t.startswith("Journal read from the top") for t in said))
app.destroy()
A.EDSMT.say = real_say

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
