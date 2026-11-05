"""1.10040: the app polls the game on one chain, however often tick() is called.

tick() schedules the next tick when it finishes. The app only ever calls it
from that schedule, but a check that calls it directly started a second
chain each time, and with the overlay on for a new install (1.10040) a few
dozen chains were enough for update() never to finish. Now a tick that is
called early takes the place of the one that was waiting.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_tick.py
"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-tick-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as exc:
    print("  SKIP  needs a display (%s). Run it under xvfb-run." % exc)
    sys.exit(0)

import overlay as OV  # noqa: E402
OV.foreground_is_game = lambda: None
import edsmt as A     # noqa: E402

A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as handle:
    json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS,
               "welcome_seen_version": A.APP_VERSION}, handle)

app = A.EDSMT()
app.geometry("1400x900+0+0")
app.updates.check = lambda *args, **kwargs: None


def waiting_ticks():
    """The scheduled calls of tick itself (not fast_tick) Tk is holding."""
    out = []
    for job in app.tk.splitlist(app.tk.call("after", "info")):
        try:
            script = str(app.tk.call("after", "info", job)[0])
        except Exception:
            continue
        if script.endswith("tick") and not script.endswith("fast_tick"):
            out.append(job)
    return out


for _ in range(20):
    app.update_idletasks()
    app.update()
    time.sleep(0.02)
check("a new install has the overlay on", app.settings.get("overlay_enabled") is True)
check("one tick is waiting after the start", len(waiting_ticks()) == 1, waiting_ticks())
for _ in range(40):
    app.tick()
check("called forty times, still one waiting", len(waiting_ticks()) == 1, len(waiting_ticks()))
started = time.time()
for _ in range(3):
    app.update_idletasks()
    app.update()
check("and the window's events are done in moments", time.time() - started < 5, time.time() - started)
time.sleep(0.8)
app.update()
check("it keeps polling by itself", len(waiting_ticks()) == 1, waiting_ticks())
try:
    app.destroy()
except Exception:
    pass

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
