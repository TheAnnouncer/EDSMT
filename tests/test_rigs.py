"""Rigs down, and a warning when the SRV wanders too far from them.

Driven on a stubbed app: a state object stands in for the game, positions
are worked out on a 1,800 km body, and the sound is recorded rather than
played. What has to hold: the warning fires once per excursion, re-arms
only after coming back well inside the limit, is off at 0, and the rigs are
forgotten on leaving the body.
"""
import os, sys, math, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "stubs"))
import _ctkstub  # noqa
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="edsmt-rigs-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
import edsmt as A, survey as SV  # noqa

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)

R = 1_800_000.0
HOME = (12.5, -45.5)


def dest(lat, lon, bearing, metres):
    p1, l1, th, d = math.radians(lat), math.radians(lon), math.radians(bearing), metres / R
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(th))
    l2 = l1 + math.atan2(math.sin(th) * math.sin(d) * math.cos(p1),
                         math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), math.degrees(l2)


class State:
    def __init__(self, lat, lon, heading=0.0):
        self.lat, self.lon, self.heading = lat, lon, heading
        self.radius_m = R
        self.has_position = True


def probe(limit=1000, sound=True):
    app = A.EDSMT.__new__(A.EDSMT)
    app.said, app.sounds, app.redraws = [], [], []
    app.say = lambda t, c=None: app.said.append((t, c))
    app.settings = dict(A.DEFAULT_SETTINGS, rig_warn_m=limit, rig_warn_sound=sound)
    app.where = ("Ega", "Ega 1")
    app.here = lambda: app.where
    app.redraw = lambda: app.redraws.append(True)
    app.sound_alarm = lambda: app.sounds.append(True)
    app.rigs_at, app._rigs_warned = None, False
    app.game = State(*HOME)
    return app


print("== marking each rig as it goes down ==")
app = probe()
app.game = None
app.drop_rigs()
check("with no position from the game it says so and marks nothing",
      app.rigs_at is None and "No surface position" in app.said[-1][0])
app.game = State(*HOME)
app.drop_rigs()
check("the first press is rig 1, on this body",
      app.rigs_at and (app.rigs_at["system"], app.rigs_at["body"]) == ("Ega", "Ega 1")
      and [r["n"] for r in app.rigs_at["rigs"]] == [1], app.rigs_at)
check("and says which rig and how far the warning is",
      app.said[-1][0].startswith("Rig 1 down") and "1.00 km" in app.said[-1][0], app.said[-1][0])
check("and redraws so the map and overlay show it at once", app.redraws)
app.drop_rigs()
check("pressing again on the same spot is not a second rig",
      len(app.rigs_at["rigs"]) == 1 and "already marked" in app.said[-1][0])
for step in range(1, 6):
    app.game = State(*dest(HOME[0], HOME[1], 60 * step, 60))
    app.drop_rigs()
check("each press further on is the next rig, numbered for you",
      [r["n"] for r in app.rigs_at["rigs"]] == [1, 2, 3, 4, 5, 6])
app.game = State(*dest(HOME[0], HOME[1], 200, 90))
app.drop_rigs()
check("a seventh is refused - the Rhino carries six",
      len(app.rigs_at["rigs"]) == A.MAX_RIGS and "All 6" in app.said[-1][0])

print("== driving away, and back ==")
app = probe()
app.drop_rigs()                                   # rig 1 at HOME
app.game = State(*dest(HOME[0], HOME[1], 90, 300))
app.drop_rigs()                                   # rig 2, 300 m east
near = app.watch_rigs(State(*dest(HOME[0], HOME[1], 90, 700)))
check("700 m east: rig 1 is the farthest at 700 m, no warning",
      near and near["n"] == 1 and abs(near["range_m"] - 700) < 3
      and not near["far"] and not app.sounds, near)
check("every rig comes back with where it is from here",
      near["count"] == 2 and sorted(m["n"] for m in near["rigs"]) == [1, 2]
      and abs(next(m for m in near["rigs"] if m["n"] == 2)["range_m"] - 400) < 3)
check("the offsets put rig 1 to the west",
      next(m for m in near["rigs"] if m["n"] == 1)["east"] < -650)
far = app.watch_rigs(State(*dest(HOME[0], HOME[1], 90, 1100)))
check("1,100 m east: too far from rig 1, and the sound plays",
      far["far"] and far["n"] == 1 and app.sounds == [True], far)
check("the status line names the rig, in red",
      app.said[-1][0].startswith("TOO FAR FROM RIG 1") and app.said[-1][1] == A.RED,
      app.said[-1])
app.watch_rigs(State(*dest(HOME[0], HOME[1], 90, 1300)))
app.watch_rigs(State(*dest(HOME[0], HOME[1], 90, 1250)))
check("staying out there does not sound again every poll", app.sounds == [True])
app.watch_rigs(State(*dest(HOME[0], HOME[1], 90, 950)))
app.watch_rigs(State(*dest(HOME[0], HOME[1], 90, 1050)))
check("dithering on the line does not re-arm it", app.sounds == [True])
app.watch_rigs(State(*dest(HOME[0], HOME[1], 90, 800)))
app.watch_rigs(State(*dest(HOME[0], HOME[1], 90, 1100)))
check("back well inside, then out again: a second warning", app.sounds == [True, True])

print("== off, silent, collected, left behind ==")
quiet = probe(sound=False)
quiet.drop_rigs()
out = quiet.watch_rigs(State(*dest(HOME[0], HOME[1], 0, 1500)))
check("with the sound off it still warns, silently",
      out["far"] and not quiet.sounds and quiet.said[-1][0].startswith("TOO FAR"))
off = probe(limit=0)
off.drop_rigs()
out = off.watch_rigs(State(*dest(HOME[0], HOME[1], 0, 5000)))
check("a limit of 0 never warns, but still says where they are",
      out and not out["far"] and not off.sounds and abs(out["range_m"] - 5000) < 5)
check("and the hint says the warning is off", "off" in off.rigs_hint())
junk = probe(limit="lots")
check("a limit that is not a number is off, not a crash", junk.rig_limit() == 0.0)
app.rigs_up()
check("ALL UP forgets every rig and stops watching", app.rigs_at is None
      and app.watch_rigs(State(*HOME)) is None and "2 rig(s) up" in app.said[-1][0])
check("ALL UP with nothing down says so", (app.rigs_up(), "No rigs" in app.said[-1][0])[1])
gone = probe()
gone.drop_rigs()
gone.where = ("Ega", "Ega 2")
check("leaving the body forgets the rigs",
      gone.watch_rigs(State(*HOME)) is None and gone.rigs_at is None)
gone.where = ("Ega", "Ega 1")
gone.drop_rigs()
check("and a new first rig on the next body is rig 1 again",
      [r["n"] for r in gone.rigs_at["rigs"]] == [1])

print("== wired in ==")
src = open(os.path.join(os.path.dirname(HERE), "edsmt.py"), encoding="utf-8").read()
check("the key is registered from settings", A.EDSMT.wanted_hotkeys(
      dict(A.DEFAULT_SETTINGS, hotkey_rigs="F8")).get("rigs") == "F8")
check("and the poll acts on it", 'elif action == "rigs":' in src and "self.drop_rigs()" in src)
check("redraw hands the rigs to the map and the overlay",
      "rigs = self.watch_rigs(state) if live else None" in src
      and src.count("rigs=rigs") >= 2)
check("Settings has the distance, the sound switch and the key",
      '"rig_warn_m"' in src and '"rig_warn_sound"' in src and '"hotkey_rigs"' in src)

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
