"""1.10037: the results box no longer loops itself to death (reported on
22 Oct: "the box that the results come in flashes and then it hangs then
crashes", on the Find tab).

At some window sizes a table needs its vertical scrollbar only while the
bar is hidden: showing it narrows the table, the table then fits, hiding it
widens the table, and it needs the bar again. customtkinter's scrollbar
redraws inside set() (update_idletasks), so each decision fired the next one
from inside itself - on Windows the stack ran out and the app died with no
Python error; under X it hung for good. Reproduced on a copy of a real data
folder at 1240 x 780, scaling 1.33.

    python tests/test_110037_scroll.py
"""
import os, sys, json, tempfile, time, random, faulthandler
# A hang is a failure, not a frozen suite.
faulthandler.dump_traceback_later(90, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-scroll-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    print("  SKIP  needs a display (%s). Run it under xvfb-run." % _exc)
    raise SystemExit(0)

import overlay as OV    # noqa: E402
OV.foreground_is_game = lambda: None
import edsmt as A       # noqa: E402


class Bar:
    """A scrollbar stand-in. `echo` is what a redraw inside set() reports
    back through the table's scroll command, as customtkinter's does."""
    def __init__(self, managed=False, echo=None):
        self.managed = self.mapped = managed
        self.calls, self.depth, self.most = [], 0, 0
        self.echo = echo

    def set(self, low, high):
        self.calls.append(("set", low, high))
        self.depth += 1
        self.most = max(self.most, self.depth)
        try:
            if self.echo is not None and self.depth < 60:
                # Showing the bar makes it unneeded; hiding it makes it needed.
                nxt = ("0.0", "1.0") if self.managed else ("0.0", "0.8")
                self.echo(self, *nxt)
        finally:
            self.depth -= 1

    def winfo_manager(self): return "grid" if self.managed else ""
    def winfo_ismapped(self): return self.mapped
    def grid(self, **kw): self.calls.append("grid"); self.managed = self.mapped = True
    def grid_forget(self): self.calls.append("grid_forget"); self.managed = self.mapped = False
    def place(self, **kw): self.calls.append("place")
    def place_forget(self): self.calls.append("place_forget"); self.mapped = False


print("== a decision cannot fire itself from inside itself ==")
bar = Bar()
bar.echo = lambda b, lo, hi: A.ScrollTable._toggle(b, lo, hi, {"row": 0})
A.ScrollTable._toggle(bar, "0.0", "0.8", {"row": 0})
check("a redraw that reports back does not start another decision inside the first",
      bar.most <= 3, bar.most)
check("and the table settles on a bar it can use", bar.managed, bar.calls[-4:])

print("== a bar that keeps flipping stays shown ==")
flip = Bar()
for i in range(12):
    A.ScrollTable._toggle(flip, "0.0", "0.8" if i % 2 == 0 else "1.0", {"row": 0})
shows = flip.calls.count("grid")
check("it is shown, hidden and shown again at most a couple of times",
      shows <= 2 and flip.calls.count("grid_forget") <= 2, (shows, flip.calls.count("grid_forget")))
check("and then left showing - an unused bar is harmless, a flashing one is not",
      flip.managed)
A.ScrollTable.settle(flip)
A.ScrollTable._toggle(flip, "0.0", "1.0", {"row": 0})
check("a fresh result set lets it go again", not flip.managed, flip.calls[-3:])

print("== the reported window: Find as a tab at 1240 x 780, scaling 1.33 ==")
A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
    json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS}, _f)
app = A.EDSMT()
app.updates.check = lambda *a, **k: None
app.geometry("1240x780+0+0")
app.tk.call("tk", "scaling", 1.3333)


def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        app.update_idletasks()
        app.update()


random.seed(1)
kinds = ["Platinum", "Osmium", "Iridium, Sapphire", "Rhodplumsite", "Ruby, Gold, Monazite"]
SITES = [{"system": "Col 285 Sector ZL-K b22-%d" % i, "distance_ly": random.uniform(0, 500),
          "planet": "Col 285 Sector ZL-K b22-%d A %d" % (i, i % 7), "spot": str(1 + i % 3),
          "rigs": random.randint(1, 6), "types": kinds[i % 5],
          "commodities": kinds[i % 5].split(", "),
          "last_seen": "2026-10-%02dT10:00:00+00:00" % (1 + i % 22),
          "uploader": "CMDR Long Name %d" % i, "score": random.random(),
          "intact_confidence": random.random()} for i in range(339)]
pump(1)
started = time.time()
find = app.open_find()
find = app.docked_tools.get("find") or find
pump(1)
find.results("sites", json.dumps({"sites": SITES, "count": len(SITES), "complete": True}), True)
pump(3)
took = time.time() - started
check("Find opens, draws 339 sites and the app is still answering", took < 20, "%.1f s" % took)
vflips = len(getattr(find.scroller.vbar, "_edsmt_flips", []))
check("and the scrollbars have stopped changing their minds", vflips <= 4, vflips)
app.destroy()

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
