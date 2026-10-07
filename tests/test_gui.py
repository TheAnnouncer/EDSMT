"""The real toolkit, on a real display. Everything else here runs on stubs.

Stubs prove the logic. They cannot prove that a window is laid out so its
text fits, that Tab goes where the eye expects, that a list appears while
you type, or that a destroyed window really is gone - those are things only
Tk itself can answer. This file asks it.

It needs tkinter, customtkinter and a display. On the machine that builds
the release all three are there, so BUILD.bat runs it for real. Anywhere
without them it says SKIP, out loud, rather than pretending to have passed.

    python tests/test_gui.py
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)

try:
    import tkinter as tk
    root = tk.Tk()
except Exception as exc:                        # no Tk, or no display
    print("  SKIP  no display to run the real toolkit on (%s)"
          % exc.__class__.__name__)
    sys.exit(0)
root.withdraw()

import overlay as OV  # noqa: E402
# These checks are about what the boxes draw, not about which window happens
# to be in front of the machine running them. On Windows that is the console
# or the test window, never the game, so the boxes would stand down and draw
# nothing - which is right in play and meaningless here. "Cannot tell"
# (None) is the one answer that leaves them up; the checks that are about
# standing down set their own answer.
OV.foreground_is_game = lambda: None


def pump(times=3):
    for _ in range(times):
        root.update_idletasks()
        root.update()


print("== a box destroyed out from under the overlay is put back ==")
# Two crash logs from two machines, same line: "invalid command name
# .!toplevel2.!canvas". The overlay kept a canvas whose window had gone and
# drew into it on every tick.
ov = OV.Overlay(root, tk, {"overlay_show_strip": True,
                           "overlay_show_radar": True,
                           "overlay_show_status": True})
ov.show()
pump()
ROWS = [{"commodity": "Iridium", "range_m": 420.0, "bearing": 30.0, "rigs": 3,
         "east": 200.0, "north": 350.0, "id": 1}]
ov.draw(ROWS, 10.0, body="Ega 1")
check("three boxes are open", len(ov.panels) == 3, list(ov.panels))
ov.panels[OV.RADAR].window.destroy()
pump()
try:
    ov.draw(ROWS, 10.0, body="Ega 1")
    pump()
    survived = True
except tk.TclError as exc:
    survived = False
    print("        ", exc)
check("the next redraw does not raise", survived)
check("the destroyed box is rebuilt, not dropped",
      ov.panels[OV.RADAR].alive())
check("and it has something drawn in it",
      len(ov.panels[OV.RADAR].canvas.find_all()) > 0)
check("a close request on a box is ignored rather than obeyed",
      ov.panels[OV.STRIP].window.protocol("WM_DELETE_WINDOW") != "")
print("== TOO FAR FROM RIG is on every box that is open ==")
_RIGS = [{"n": 1, "range_m": 1450.0, "east": -1400.0, "north": -300.0, "bearing": 258.0},
         {"n": 2, "range_m": 120.0, "east": 100.0, "north": 60.0, "bearing": 59.0}]
ov.draw(ROWS, 10.0, body="Ega 1",
        rigs={"rigs": _RIGS, "count": 2, "n": 1, "range_m": 1450.0,
              "bearing": 258.0, "offset": 170.0, "far": True, "limit_m": 1000.0})
pump()
_banners = {key: len(panel.canvas.find_withtag("rigs"))
            for key, panel in ov.panels.items() if panel.alive()}
check("every open box carries the banner",
      _banners and all(n >= 2 for n in _banners.values()), _banners)
_status_text = [ov.panels[OV.STATUS].canvas.itemcget(i, "text")
                for i in ov.panels[OV.STATUS].canvas.find_all()
                if ov.panels[OV.STATUS].canvas.type(i) == "text"]
check("the banner names the rig, how far and which way",
      any("TOO FAR FROM RIG 1" in t and "1.45km" in t for t in _status_text), _status_text)
check("the scope draws the rig that is in range",
      len(ov.panels[OV.RADAR].canvas.find_withtag("rigmark")) >= 2)
ov.draw(ROWS, 10.0, body="Ega 1",
        rigs={"rigs": [dict(_RIGS[1], range_m=300.0)], "count": 1, "n": 2,
              "range_m": 300.0, "bearing": 20.0, "offset": 10.0,
              "far": False, "limit_m": 1000.0})
pump()
_status_text = [ov.panels[OV.STATUS].canvas.itemcget(i, "text")
                for i in ov.panels[OV.STATUS].canvas.find_all()
                if ov.panels[OV.STATUS].canvas.type(i) == "text"]
check("inside the limit there is no banner, just the distance on STATUS",
      not any(p.canvas.find_withtag("rigs") for p in ov.panels.values() if p.alive())
      and any(t.startswith("1R") and "300m" in t for t in _status_text), _status_text)
ov.draw(ROWS, 10.0, body="Ega 1")
pump()
check("with no rigs down, nothing about rigs at all",
      not any(p.canvas.find_withtag("rigs") for p in ov.panels.values() if p.alive()))

print("== 1.10031: the rig planner, the wing and text size on the real scope ==")
_PLAN = {"tracing": False, "near": True, "spacing": 78.0, "done": 1, "next": 2,
         "next_pin": {"n": 2, "range_m": 64.0, "offset": 30.0},
         "outline": [(-120.0, -120.0), (120.0, -120.0), (120.0, 120.0),
                     (-120.0, 120.0)],
         "pins": [{"n": 1, "east": 0.0, "north": 0.0, "done": True, "range_m": 0.0},
                  {"n": 2, "east": 40.0, "north": 50.0, "done": False,
                   "range_m": 64.0}]}
_WING = {"mates": [{"name": "CMDR Bee", "east": -60.0, "north": 20.0,
                    "heading": 90.0, "in_srv": True,
                    "rigs": [{"n": 1, "east": -70.0, "north": 30.0}]}]}
ov.show()
ov.draw(ROWS, 10.0, body="Ega 1", rigplan=_PLAN, wing=_WING)
pump()
_scope = ov.panels[OV.RADAR].canvas
check("the plan's pins and traced edge are on the scope",
      len(_scope.find_withtag("planmark")) >= 5, len(_scope.find_withtag("planmark")))
check("and the wingmate's Rhino and rig, in their own colour",
      len(_scope.find_withtag("wingmark")) >= 4
      and any(_scope.itemcget(i, "text") == "CMDR Bee"
              for i in _scope.find_withtag("wingmark")
              if _scope.type(i) == "text"))
_status_text = [ov.panels[OV.STATUS].canvas.itemcget(i, "text")
                for i in ov.panels[OV.STATUS].canvas.find_all()
                if ov.panels[OV.STATUS].canvas.type(i) == "text"]
check("the compass tape points at the next pin too",
      any(ov.panels[OV.STRIP].canvas.itemcget(i, "text").startswith("P2 64m")
          for i in ov.panels[OV.STRIP].canvas.find_withtag("pintape")
          if ov.panels[OV.STRIP].canvas.type(i) == "text"))
check("STATUS names the next pin, how far and how many are done",
      any(t.startswith("PIN 2") and "64m" in t and "(1/2)" in t
          for t in _status_text), _status_text)


def _sizes(panel):
    canvas = ov.panels[panel].canvas
    out = []
    for item in canvas.find_all():
        if canvas.type(item) == "text":
            font = canvas.itemcget(item, "font")
            try:
                out.append(abs(int(str(font).split()[1])))
            except (IndexError, ValueError):
                pass
    return out


_before = max(_sizes(OV.STATUS) or [0])
ov.settings["overlay_text_status"] = 150
ov.draw(ROWS, 10.0, body="Ega 1")
pump()
check("STATUS at 150% draws its words half as big again, the box unchanged",
      max(_sizes(OV.STATUS) or [0]) >= round(_before * 1.5) - 1,
      (_before, max(_sizes(OV.STATUS) or [0])))
ov.settings["overlay_text_status"] = 100


def _overlaps(over, panel):
    """Pairs of words on a box drawn over each other, by Tk's own boxes."""
    canvas = over.panels[panel].canvas
    boxes = []
    for item in canvas.find_all():
        if canvas.type(item) != "text" or not canvas.itemcget(item, "text").strip():
            continue
        box = canvas.bbox(item)
        if box:
            boxes.append((canvas.itemcget(item, "text")[:24], box))
    out = []
    for i, (ta, a) in enumerate(boxes):
        for tb, b in boxes[i + 1:]:
            w = min(a[2], b[2]) - max(a[0], b[0])
            h = min(a[3], b[3]) - max(a[1], b[1])
            if w > 3 and h > 3:
                out.append((ta, tb))
    return out


print("== 1.10033: every layout, every screen, every text size ==")
# #169: on the standard layout the compass letters were cut off by the top
# of the box - on every screen, at 100%. At a large text size words ran off
# the side of a box, or under the next row. A long body name and a long
# guide sentence, because those are the two that run out of room.
#
# Every common screen, not just the one running the tests. The boxes are a
# share of the screen, so a check passed on a 1600x1000 test display said
# nothing about a 1080-line monitor - where DEPOSIT at 200% wrote RANGE over
# SIGNAL POINT - or a 768-line one, where it wrote the telemetry over it at
# 100%, or the 1024x768 the build server has. 4K and the ultrawides are in
# it on purpose: a 32:9 screen makes a compass four times wider than it is
# tall and a status strip barely two lines high.
#
# And Windows scaling. Today Tk starts before the app is made DPI-aware, so
# a 4K screen at 150% draws the overlay's words at the 96 dpi size. The
# scaled cases are what happens if Windows or a later Tk ever hands Tk the
# real DPI: every font grows by it, and the rows have to grow with them.
_KEYS = (OV.RADAR, OV.STRIP, OV.STATUS, OV.TARGETS, OV.GUIDE, OV.DEPOSIT)
_GUIDE = {"step": 10, "total": 11, "title": "PLACE RIGS  Alt+4-9",
          "detail": "One key per rig as it goes down: Alt+4-9 is rigs 1 to 6.",
          "next": "NEXT DEPOSIT"}
_LONG = "Col 285 Sector ZL-K b22-2 A 1"
_LONGUIDE = dict(_GUIDE, detail="One key per rig as it goes down: Alt+4-9 is "
                 "rigs 1 to 6. Press the next rig key as each rig lands and "
                 "the scope counts them.")
SCREENS = ((1024, 768), (1366, 768), (1600, 1000), (1920, 1080),
           (2560, 1080), (2560, 1440), (3440, 1440), (3840, 1080),
           (3840, 2160), (5120, 1440), (7680, 2160))
# (width, height, Windows scaling): 1080p at 125%, 1440p at 125%, 4K at
# 150% and 200% - the scalings Windows picks for those screens itself.
SCALED = ((1920, 1080, 1.25), (2560, 1440, 1.25), (3840, 2160, 1.5),
          (3840, 2160, 2.0))
_SIX = dict({"overlay_show_%s" % k: True for k in _KEYS}, overlay_guide=True)


def on_screen(over, size):
    """Lay `over` out for a screen of `size`, whatever this one is."""
    over.screen = lambda _win, size=size: size
    return over


def _outside(over, panel):
    """Words drawn past the edge of their own box, by Tk's own boxes."""
    canvas = over.panels[panel].canvas
    w, h = int(canvas.winfo_width()), int(canvas.winfo_height())
    out = []
    for item in canvas.find_all():
        if canvas.type(item) != "text" or not canvas.itemcget(item, "text").strip():
            continue
        box = canvas.bbox(item)
        if box and (box[0] < -2 or box[1] < -2 or box[2] > w + 2 or box[3] > h + 2):
            out.append((canvas.itemcget(item, "text")[:24], box, (w, h)))
    return out


_sw, _sh = root.winfo_screenwidth(), root.winfo_screenheight()
_tk_scaling = float(root.tk.call("tk", "scaling"))
_seen, _six_drawn = [], 0
_layouts = list(OV.LAYOUT_PRESETS) + [("All six boxes", None)]
_cases = [(w, h, 1.0) for w, h in SCREENS] + list(SCALED)
for _w, _h, _dpi in _cases:
    root.tk.call("tk", "scaling", (96.0 / 72.0) * _dpi if _dpi != 1.0 else _tk_scaling)
    for (_title, _key), _pct in [(lay, pct) for lay in _layouts
                                 for pct in (80, 100, 150, 200)]:
        if _key:
            _layout, _shown = OV.preset_layout(_key, _w, _h)
            _set = {"overlay_layout": _layout, "overlay_guide": True}
            for _k in _KEYS:
                _set["overlay_show_%s" % _k] = _k in _shown
        else:
            _set = dict(_SIX)
        for _k in _KEYS:
            _set["overlay_text_%s" % _k] = _pct
        _name = "%s on %dx%d%s" % (_title, _w, _h,
                                   "" if _dpi == 1.0 else " at %d%% scaling" % (_dpi * 100))
        _lay = on_screen(OV.Overlay(root, tk, _set), (_w, _h))
        _lay.show()
        _lay.draw(ROWS + [{"commodity": "Haematite", "range_m": 896.0,
                           "bearing": 300.0, "rigs": 2, "east": -500.0,
                           "north": 700.0, "id": 2}],
                  10.0, body=_LONG, guide=_LONGUIDE)
        pump()
        if not _key:
            if all(k in _lay.panels and _lay.panels[k].alive() for k in _KEYS):
                _six_drawn += 1
            else:
                check("all six boxes were drawn: %s at %d%%" % (_name, _pct), False,
                      [k for k in _KEYS if not (k in _lay.panels
                                                and _lay.panels[k].alive())])
        for _k in sorted(_lay.panels):
            if not _lay.panels[_k].alive():
                continue
            _seen.append(_k)
            _bad = _overlaps(_lay, _k) + _outside(_lay, _k)
            if _bad:
                check("%s, %s at %d%%: every word inside its box, none on "
                      "another" % (_name, _k, _pct), False, _bad[:3])
        _lay.hide()
        pump()
root.tk.call("tk", "scaling", _tk_scaling)
check("%d screens and %d Windows scalings, every layout, 80-200%%: %d boxes "
      "drawn, every word inside its box and none on another"
      % (len(SCREENS), len(SCALED), len(_seen)),
      len(_seen) >= 600 and not [f for f in fails if "every word inside" in f],
      [f for f in fails if "every word inside" in f][:4])
check("all six boxes came up every time they were asked for",
      _six_drawn == len(_cases) * 4, (_six_drawn, len(_cases) * 4))
check("and the text scale is back to 100% once drawing is done",
      OV._TEXT_SCALE == 1.0, OV._TEXT_SCALE)
check("the screen's scaling is back to 1 too", OV._DPI == 1.0, OV._DPI)
check("and text is measured off the table again outside a draw",
      OV._MEASURE is None, OV._MEASURE)
check("Windows scaling below 120% is left alone; above it, the rows follow it",
      OV.set_dpi(1.04) == 1.0 and OV.set_dpi(1.5) == 1.5 and OV.set_dpi(9) == 4.0
      and OV.set_dpi("x") == 1.0)
OV.set_dpi(1.0)
_std = OV.Overlay(root, tk, {"overlay_layout": OV.preset_layout("standard", _sw, _sh)[0],
                             "overlay_show_strip": True})
_std.show()
_std.draw(ROWS, 0.0, body="Ega 1")
pump()
_c = _std.panels[OV.STRIP].canvas
_letters = [_c.bbox(i) for i in _c.find_all()
            if _c.type(i) == "text" and _c.itemcget(i, "text") in ("N", "E", "S", "W")]
check("#169: the compass letters sit inside the top of the box",
      _letters and all(b[1] >= 0 for b in _letters), _letters)
_std.hide()
ov.hide()
pump()

# ---------------------------------------------------------------------------
# The app's own windows
# ---------------------------------------------------------------------------
import json, tempfile, shutil, time
_HOME = tempfile.mkdtemp(prefix="edsmt-gui-")
os.environ["HOME"] = _HOME
os.environ["LOCALAPPDATA"] = _HOME
root.destroy()                      # the app brings its own root
import edsmt as A                   # noqa: E402
from survey import fold as SV_fold  # noqa: E402
import survey as SV  # noqa: E402
A.DATA_DIR = _HOME
A.SETTINGS_FILE = os.path.join(_HOME, "settings.json")
# An empty settings folder is a first run, and a first run puts the sharing
# question up 900 ms in: a modal window that takes the keyboard. On a quick
# machine the typing checks below finished before it arrived; on a slower
# one it landed in the middle of them and every key went to it - six false
# failures on Windows in 1.10028, with the type-ahead itself working. Here
# the question has been answered; it gets its own checks at the end.
#
# And the journal folder is an empty one of the test's own. On Windows the
# app asks Windows where Saved Games is, not HOME, so on a machine that plays
# Elite this window read the commander's real journals: his real hold landed
# in the Earnings checks, and a real station's price on the strip.
_JOURNALS = os.path.join(_HOME, "journals")
os.makedirs(_JOURNALS, exist_ok=True)
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
    json.dump({"asked_to_share": True, "journal_dir": _JOURNALS}, _f)
app = A.EDSMT()
check("the window reads the test's own empty journal folder, never a real one",
      os.path.normcase(os.path.abspath(str(getattr(app.watcher, "directory", "") or "")))
      == os.path.normcase(os.path.abspath(_JOURNALS)),
      getattr(app.watcher, "directory", None))
app.geometry("1400x900+0+0")
root = app
# Nothing in here asks the live site whether there is a newer version.
app.updates.check = lambda *args, **kwargs: None

def settle(times=4):
    for _ in range(times):
        app.update_idletasks()
        app.update()


# GitHub's Windows runner has a 1024x768 desktop. A check about what fits in
# a 1400-pixel window cannot be answered on a screen that cannot hold one,
# and failing it there reported a layout bug that did not exist - the red X
# on 1.10028. On a screen too small it says SKIP and why, out loud, like
# every other check here that cannot run.
WIDE_SCREEN = 1440


def check_wide(label, cond_fn, extra_fn=lambda: ""):
    width, height = app.winfo_screenwidth(), app.winfo_screenheight()
    if width < WIDE_SCREEN:
        print("  SKIP  %s   (this screen is %dx%d - too small for a "
              "1400-pixel window)" % (label, width, height))
        return
    ok = bool(cond_fn())
    check(label, ok, "" if ok else extra_fn())

def inside(widget, window):
    """Is the whole of `widget` inside `window`'s visible area?"""
    wx, wy = widget.winfo_rootx(), widget.winfo_rooty()
    ox, oy = window.winfo_rootx(), window.winfo_rooty()
    return (wx >= ox and wy >= oy
            and wx + widget.winfo_width() <= ox + window.winfo_width() + 1
            and wy + widget.winfo_height() <= oy + window.winfo_height() + 1)

def A_walk(widget):
    """Every widget under `widget`, all the way down."""
    for child in widget.winfo_children():
        yield child
        yield from A_walk(child)


def texts_in(widget):
    out = []
    for child in widget.winfo_children():
        try:
            out.append(str(child.cget("text")))
        except Exception:
            pass
        out.extend(texts_in(child))
    return out

settle()

print("== the Find table shows every column, Found by included ==")
# Reported: "the find box does not show all the information properly. Not
# even the commander name." Every heading was a 140-pixel button, the table
# was forced to the window's width, and the last two columns were cut off.
SITES = {"count": 2, "sites": [
    {"system": "Col 285 Sector ZL-K b22-2", "planet": "Col 285 Sector ZL-K b22-2 A 1",
     "spot": "3", "rigs": 11, "distinct_types": 4,
     "types": ["Ruby", "Iridium", "Platinum", "Rhodplumsite"],
     "updated": "2026-09-19T21:48:00Z", "age_days": 1.0,
     "uploader": "CMDR Konstantin Vasquez-Delacroix", "status": "reported",
     "worked_out": False, "score": 19.0, "intact_confidence": 1.0},
    {"system": "Ega", "planet": "Ega 1", "spot": "1", "rigs": 6,
     "distinct_types": 1, "types": ["Haematite"], "updated": "2026-09-09T10:00:00Z",
     "age_days": 14.0, "uploader": "", "status": "reported", "worked_out": False,
     "score": 4.5, "intact_confidence": 1.0}]}
# 1.10031: Find opens once the commander has shared a deposit of their own.
# That gate has its own checks (test_110031); here it is open.
app.settings["find_unlocked"] = True
app.open_find()
settle()
finder = app.finder
finder.results("sites", json.dumps(SITES), True)
settle(6)
shown = texts_in(finder.table)
check("the Found by heading is drawn", any(t.startswith("Found by") for t in shown), shown[:20])
check("and the Score heading", any(t.startswith("Score") for t in shown), shown[:20])
check("the commander's name is in the table",
      "CMDR Konstantin Vasquez-Delacroix" in shown, shown)
check("the whole commodity list, not the first 34 letters of it",
      "Ruby, Iridium, Platinum, Rhodplumsite" in shown, shown)
_heads = [w for w in finder.table.winfo_children()
          if isinstance(w, A.ctk.CTkButton)]
check("headings are sized to their words, not 140 pixels each",
      _heads and max(h.winfo_width() for h in _heads) < 140,
      [h.winfo_width() for h in _heads])
def _text_of(w):
    try:
        return str(w.cget("text"))
    except Exception:
        return ""
_score = [w for w in finder.table.winfo_children()
          if _text_of(w).startswith("Score")]
check_wide("on a 1400-pixel window every column is on screen without scrolling",
           lambda: _score and inside(_score[0], finder.scroller.canvas),
           lambda: "Score is off the edge")
finder.geometry("820x600")
settle(6)
check("squeezed narrow, the table scrolls sideways instead of losing columns",
      finder.scroller.hbar.winfo_ismapped()
      and finder.scroller.inner.winfo_reqwidth() > finder.scroller.canvas.winfo_width(),
      (finder.scroller.inner.winfo_reqwidth(), finder.scroller.canvas.winfo_width()))
finder.destroy()
settle()

print("== the editors always show their Save button ==")
DEP = {"id": "x1", "system": "Col 285 Sector ZL-K b22-2",
       "body": "Col 285 Sector ZL-K b22-2 A 1 Ring Something Long",
       "location": "22", "commodity": "Low Temperature Diamonds", "rigs": "4",
       "amount": "High", "density": "Medium", "lat": "12.401233",
       "lon": "-98.712001", "notes": "Mined 10/09/2026 01:05\nMined 11/09/2026 22:40\nthird\nfourth",
       "recorded": "2026-09-14T19:12:00Z"}
ed = A.EditWindow(app, DEP)
settle(6)
_save_btn = next(b for w in ed.winfo_children() for b in w.winfo_children()
                 if isinstance(b, A.ctk.CTkButton) and b.cget("text") == "Save")
check("the deposit editor's Save is inside the window", inside(_save_btn, ed),
      (_save_btn.winfo_rooty(), ed.winfo_rooty(), ed.winfo_height()))
check("and the body name is shown whole",
      "Col 285 Sector ZL-K b22-2 A 1 Ring Something Long" in " ".join(texts_in(ed)))
ed.geometry("%dx%d" % (ed.winfo_width(), 300))
settle(6)
check("even squeezed short, Save stays on screen",
      inside(_save_btn, ed), (ed.winfo_height(),))
ed.destroy()
LOC = {"id": "L1", "system": DEP["system"], "body": DEP["body"], "location": "22"}
le = A.EditLocationWindow(app, LOC)
settle(6)
_lsave = next(b for w in le.winfo_children() for b in w.winfo_children()
              if isinstance(b, A.ctk.CTkButton) and b.cget("text") == "Save")
check("the signal editor's Save is inside the window", inside(_lsave, le))
le.destroy()
settle()

print("== boxes open their list as you click or type, and Tab goes down ==")
# Reported: "when selecting or typing it should auto show and you should be
# able to click tab". The toolkit's dropdown only opened from its arrow, and
# the rail's boxes were built bottom-up so Tab ran through them backwards.
def entry_of(box):
    return getattr(box, "_entry", box)

def press(widget, keysym, _char=""):
    # The key press itself types the character, exactly as a real one does.
    widget.event_generate("<KeyPress>", keysym=keysym, when="now")
    widget.event_generate("<KeyRelease>", keysym=keysym, when="now")
    settle(2)

app.deiconify(); app.lift(); app.focus_force(); settle(4)
# If another window has the keyboard, every check below fails for a reason
# that has nothing to do with the boxes. Say so first, in one line.
check("nothing else has hold of the keyboard - no dialog, no grab",
      app.grab_current() is None and app.focus_get() is not None,
      (str(app.grab_current()), str(app.focus_get())))
com = app.fields["commodity"]
ce = entry_of(com)
ce.focus_force(); settle(4)
sugg = app._suggest_commodity
check("clicking into the commodity box opens its list", sugg.visible())
for ch in "bast":
    press(ce, ch, ch)
names = [sugg.listbox.get(i).strip() for i in range(sugg.listbox.size())]
check("typing narrows it as you go - 'bast' finds Bastnasite",
      names and SV_fold(names[0]).startswith("bast"), names[:5])
check("and the list is under the box, not somewhere else",
      abs(sugg.popup.winfo_rooty() - (com.winfo_rooty() + com.winfo_height())) < 4
      or sugg.popup.winfo_rooty() < com.winfo_rooty(),
      (sugg.popup.winfo_rooty(), com.winfo_rooty(), com.winfo_height()))
press(ce, "Return")
check("Enter takes the highlighted one", com.get() == names[0], com.get())
check("and closes the list", not sugg.visible())

# Tab order: Commodity -> Rigs -> Amount -> Density -> Commodity
order = [entry_of(app.fields[k]) for k in ("commodity", "rigs", "amount", "density")]
seen = []
here = order[0]
here.focus_force(); settle(3)
for _ in range(4):
    here.event_generate("<Tab>", when="now"); settle(3)
    here = app.focus_get()
    seen.append(here)
check("Tab goes Commodity, Rigs, Amount, Density and back round",
      seen == order[1:] + order[:1], [str(w) for w in seen])
check("and tabbing through a box without typing leaves it as it was",
      [app.fields[k].get() for k in ("rigs", "amount", "density")] == ["", "", ""],
      [app.fields[k].get() for k in ("rigs", "amount", "density")])
order[2].focus_force(); settle(3)
order[2].event_generate("<Shift-Tab>", when="now"); settle(3)
check("and Shift-Tab goes back up", app.focus_get() == order[1], str(app.focus_get()))

rigs = app.fields["rigs"]
entry_of(rigs).focus_force(); settle(4)
check("a box with a fixed list opens it on focus too",
      rigs.suggest.visible())
_rows = [rigs.suggest.listbox.get(i).strip() for i in range(rigs.suggest.listbox.size())]
check("showing every choice it has", _rows == [str(n) for n in range(1, A.MAX_RIGS + 1)], _rows)
entry_of(rigs).delete(0, "end")
press(entry_of(rigs), "4", "4")
press(entry_of(rigs), "Tab")
check("Tab with a list open takes the choice and moves on",
      rigs.get() == "4" and app.focus_get() == order[2], (rigs.get(), str(app.focus_get())))

print("== pick with the mouse, then Tab: the keyboard stays with the boxes ==")
# Reported: "When selecting the deposit stuff I need to be able to click it
# and tab as well". Picking from a box's arrow list left the keyboard
# nowhere, so the next Tab went off the rail instead of to the next box.
amount = app.fields["amount"]
order[0].focus_force(); settle(3)
amount._dropdown_callback("High")
settle(4)
check("a value picked from the arrow list goes in",
      amount.get() == "High", amount.get())
check("and the keyboard is in that box straight after",
      app.focus_get() == order[2], str(app.focus_get()))
check("with its type-ahead list shut, so the next key is not swallowed",
      not amount.suggest.visible())
app.focus_get().event_generate("<Tab>", when="now"); settle(3)
check("so Tab goes on to Density", app.focus_get() == order[3], str(app.focus_get()))
for _k in ("amount", "rigs"):
    entry_of(app.fields[_k]).delete(0, "end")
settle(2)

print("== Settings: the rig warning distance is a number or it is refused ==")
_sw = A.SettingsWindow(app)
settle(4)
_about_pics = [w for w in A_walk(_sw) if isinstance(w, tk.Label) and str(w.cget("image"))]
check("Settings ends with About EDSMT: the Rhino, the build and the small print",
      "ABOUT EDSMT" in " ".join(texts_in(_sw)).upper() and _about_pics
      and any(A.APP_VERSION in t and "Frontier Developments" in t
              for t in texts_in(_sw)),
      ("ABOUT EDSMT" in " ".join(texts_in(_sw)).upper(), len(_about_pics),
       [t for t in texts_in(_sw) if "Frontier" in t or "About" in t][:3]))
settle(4)
_said = []
_sw.say = lambda text, colour=None: _said.append(text)
_saved = []
_real_apply = app.apply_settings
app.apply_settings = lambda data: _saved.append(data)
_sw.fields["rig_warn_m"].delete(0, "end"); _sw.fields["rig_warn_m"].insert(0, "a long way")
_sw.save(); settle(2)
check("a distance that is not a number is refused with a reason",
      not _saved and _said and "3.5 km" in _said[-1], _said[-1:])
_sw.fields["rig_warn_m"].delete(0, "end"); _sw.fields["rig_warn_m"].insert(0, "1,500")
_sw.save(); settle(2)
check("1,500 is saved as 1500 metres",
      _saved and _saved[-1].get("rig_warn_m") == 1500.0, _saved[-1:] and _saved[-1].get("rig_warn_m"))
# Reported: "it didnt save unless he put .00 at the end".
for _typed, _metres_ in (("3950", 3950.0), ("3950 m", 3950.0), ("3.95 km", 3950.0)):
    _sw.fields["rig_warn_m"].delete(0, "end"); _sw.fields["rig_warn_m"].insert(0, _typed)
    _sw.save(); settle(2)
    check("%r saves as %d m" % (_typed, _metres_),
          _saved and _saved[-1].get("rig_warn_m") == _metres_,
          _saved[-1:] and _saved[-1].get("rig_warn_m"))
check("and the box shows it back as whole metres",
      _sw.fields["rig_warn_m"].get() == "3950", _sw.fields["rig_warn_m"].get())
check("and the status line says what was understood",
      _said and "3.95 km" in _said[-1], _said[-1:])
app.apply_settings = _real_apply

print("== Settings: the key boxes are dots until Show, safe on stream ==")
_FAKE = "not-a-real-key-0123456789"
for _k in ("inara_api_key", "community_token"):
    _box = _sw.fields[_k]
    _box.delete(0, "end"); _box.insert(0, _FAKE); settle(2)
    check("%s is dots" % _k, entry_of(_box).cget("show") == A.MASK,
          repr(entry_of(_box).cget("show")))
    check("%s still holds the real text underneath" % _k, _box.get() == _FAKE)
    check("%s has a Show button beside it" % _k,
          _sw.secrets[_k].cget("text") == "Show" and _sw.secrets[_k].winfo_ismapped())
    _sw.secrets[_k].invoke(); settle(2)
    check("%s: Show shows it" % _k,
          entry_of(_box).cget("show") == "" and _sw.secrets[_k].cget("text") == "Hide")
    _sw.secrets[_k].invoke(); settle(2)
    check("%s: Hide hides it again" % _k,
          entry_of(_box).cget("show") == A.MASK and _sw.secrets[_k].cget("text") == "Show")
check("the other boxes are left as plain text",
      entry_of(_sw.fields["rig_warn_m"]).cget("show") == "")
_real_reveal = A.REVEAL_S
A.REVEAL_S = 0.3
_sw.secrets["inara_api_key"].invoke(); settle(2)
check("shown...", entry_of(_sw.fields["inara_api_key"]).cget("show") == "")
_t_end = time.time() + 2.0
while time.time() < _t_end and entry_of(_sw.fields["inara_api_key"]).cget("show") != A.MASK:
    settle(1); time.sleep(0.05)
check("...and back to dots by itself, nobody has to remember",
      entry_of(_sw.fields["inara_api_key"]).cget("show") == A.MASK
      and _sw.secrets["inara_api_key"].cget("text") == "Show")
A.REVEAL_S = _real_reveal
_sw.secrets["community_token"].invoke(); settle(2)
_sw.load(); settle(2)
check("reloading Settings puts a shown box back to dots",
      entry_of(_sw.fields["community_token"]).cget("show") == A.MASK)
_sw.secrets["community_token"].invoke(); settle(2)

print("== a find copied as a line, and pasted back in ==")
_share = ("EDSMT find | Synuefe XR-H d11-102 | Synuefe XR-H d11-102 2 b | "
          "signal 4 | Bromellite | rigs 3 | amount High | density ? | 12.34567, 45.67891")
# 1.10032: the lines go into a box you can see, not straight off the
# clipboard - whatever was copied last is never read unasked.
app.clipboard_clear(); app.clipboard_append("my password, copied by mistake"); settle(2)
_said.clear()
_before = len(app.store.deposits)
_sw.paste_shared(); settle(2)
check("Import with the box empty reads nothing off the clipboard",
      len(app.store.deposits) == _before and _said and "box first" in _said[-1],
      _said[-1:])
_sw.paste_box.insert("1.0", "from my mate:\n" + _share); settle(2)
_pasted = _sw.paste_shared(); settle(2)
check("the lines pasted into the box are added",
      _pasted and _pasted["taken"] == 1 and len(app.store.deposits) == _before + 1, _pasted)
check("and says so", _said and _said[-1].startswith("Added 1 find"), _said[-1:])
check("and the box is emptied for the next lot",
      _sw.paste_box.get("1.0", "end").strip() == "")
_sw.paste_box.insert("1.0", _share); settle(1)
_sw._paste_enter(type("E", (), {"state": 0})()); settle(2)
check("Enter in the box imports too - the same line again is a duplicate, "
      "not a second find", len(app.store.deposits) == _before + 1
      and "already" in _said[-1].lower(), _said[-1:])
app.selected = app.store.deposits[-1]
_copied = app.copy_selected(); settle(2)
check("Copy to share puts that find back on the clipboard as the same line",
      _copied == _share and app.clipboard_get() == _share, (_copied, app.clipboard_get()))
try:
    _sw.destroy()
except Exception as _e:
    check("closing Settings with a box shown is not an error", False, _e)
settle(2)

print("== each rig is on the map, numbered, red past the limit ==")
app.plan.show([], caption="rigs", rigs={
    "rigs": [{"n": 1, "range_m": 1200.0, "east": -1150.0, "north": 300.0},
             {"n": 2, "range_m": 150.0, "east": 120.0, "north": 90.0}],
    "count": 2, "n": 1, "range_m": 1200.0, "limit_m": 1000.0, "far": True})
# Idle tasks only: a full update would let the app's own poll redraw the map
# from the (empty) game state before the check looks at it.
app.plan.update_idletasks()
_rig_items = app.plan.find_withtag("rig")
_rig_text = sorted(app.plan.itemcget(i, "text") for i in _rig_items
                   if app.plan.type(i) == "text")
check("both rigs are drawn with their numbers", _rig_text == ["1", "2"], _rig_text)
_rig_cols = {app.plan.itemcget(i, "text"): app.plan.itemcget(i, "fill")
             for i in _rig_items if app.plan.type(i) == "text"}
check("the far one is red and the near one is not",
      _rig_cols.get("1") == A.RED and _rig_cols.get("2") != A.RED, _rig_cols)
_inside = all(0 <= app.plan.coords(i)[0] <= app.plan.winfo_width()
              for i in _rig_items if app.plan.type(i) == "text")
check("and the map zooms out far enough to show the far one", _inside)
app.plan.show([], caption="")
settle(2)

print("== 1.10033: dragged off centre, the notice clears the footer ==")
# A tester's screenshot: "dragged off centre - right-click to recentre" was
# printed through the legend and the body's facts on the footer line.
app.plan._pan = [80.0, -60.0]
app.plan.show([], caption="Signal 3   Rocky body   0.185g   237K   minor "
              "metallic magma volcanism")
app.plan.update_idletasks()
_words = [(app.plan.itemcget(i, "text")[:20], app.plan.bbox(i))
          for i in app.plan.find_all()
          if app.plan.type(i) == "text" and app.plan.itemcget(i, "text").strip()]
_note = [w for w in _words if w[0].startswith("dragged off centre")]
_over = [w[0] for w in _words if _note and w is not _note[0] and w[1]
         and min(w[1][2], _note[0][1][2]) - max(w[1][0], _note[0][1][0]) > 2
         and min(w[1][3], _note[0][1][3]) - max(w[1][1], _note[0][1][1]) > 2]
check("the notice is drawn, and over nothing else", _note and not _over,
      (_note, _over))
app.plan._pan = [0.0, 0.0]
app.plan.show([], caption="")
settle(2)

print("== the map is the signal you are at, not the one the box was left on ==")
def _drow(r, b, i, what, loc):
    return {"range_m": float(r), "bearing": float(b),
            "deposit": {"id": i, "commodity": what, "rigs": "2", "location": loc,
                        "system": "S", "body": "B"}}
_old = [_drow(36055, 56.3, "o%d" % n, "Gold", "1") for n in range(3)]
_mine = [_drow(420, 200, "m1", "Haematite", "5"), _drow(610, 240, "m2", "Samarium", "5")]
app.plan.show(_old + _mine, caption="stale", signal="1", anchor=(30000.0, 20000.0))
app.plan.update_idletasks()
_map_text = [app.plan.itemcget(i, "text") for i in app.plan.find_all()
             if app.plan.type(i) == "text"]
check("the footer says where the signal in the box is",
      any("signal 1 is 36 km ENE" in t for t in _map_text), _map_text)
check("and the view is the ground round you, not 15 km of nothing",
      app.plan._auto_extent < 2000, app.plan._auto_extent)
app.plan.show(_mine, caption="at it", signal="5", anchor=(-300.0, -400.0))
app.plan.update_idletasks()
_map_text = [app.plan.itemcget(i, "text") for i in app.plan.find_all()
             if app.plan.type(i) == "text"]
check("at the signal, no such line",
      not any("signal 5 is" in t for t in _map_text), _map_text)
app.plan.show([], caption="")
settle(2)

print("== the deposit UPDATE button and the new-build button are two buttons ==")
# They shared the name btn_update, so an update announcement relabelled the
# deposit button UPDATE AVAILABLE and moved it.
check("the top bar's button is the new-build one",
      app.btn_update.cget("text") == "UPDATE AVAILABLE", app.btn_update.cget("text"))
check("the rail's is the deposit one, with its key under it",
      app.btn_update_deposit.cget("text") == "UPDATE\n" + A.key_text("CTRL+ALT+3"),
      app.btn_update_deposit.cget("text"))
app.announce_update("EDSMT 9.99999 is out.")
settle(3)
check("announcing a build leaves the deposit button alone",
      app.btn_update_deposit.cget("text") == "UPDATE\n" + A.key_text("CTRL+ALT+3")
      and app.btn_update.winfo_ismapped(), app.btn_update_deposit.cget("text"))
app.btn_update.pack_forget()
settle(2)

print("== Where to land ranks this system's bodies and keeps up ==")
_SYS = "Col 285 Sector ZL-K b22-2"
_BODIES = [
    {"body": _SYS + " A 1", "landable": True, "distance_ls": 412.5,
     "planet_class": "Rocky body", "volcanism": "", "gravity_g": 0.24,
     "temperature_k": 180.0, "locations": 4, "mapped": True},
    {"body": _SYS + " A 2", "landable": True, "distance_ls": 96.0,
     "planet_class": "High metal content body",
     "volcanism": "minor metallic magma volcanism", "gravity_g": 0.61,
     "temperature_k": 402.0, "locations": 0, "mapped": False},
    {"body": _SYS + " A 4", "landable": False, "distance_ls": 60.0,
     "planet_class": "Water world", "volcanism": "", "gravity_g": 1.1,
     "temperature_k": 290.0, "locations": 0, "mapped": False}]
app.watcher.system_bodies = lambda system=None: [dict(b) for b in _BODIES] \
    if str(system or "").lower() == _SYS.lower() else []
app.watcher.system = _SYS
# No network in a test: the answers are handed in below, by hand.
_asked = []
app.community.grounds = lambda: _asked.append("grounds") or True
app.community.system_sites = lambda system: _asked.append(system) or True
_btn = [w for w in texts_in(app) if w == "Where to land"]
check("there is a Where to land button", "Where to land" in _btn, _btn)
_land_btn = None
def _find_button(widget, text):
    for child in widget.winfo_children():
        try:
            if isinstance(child, A.ctk.CTkButton) and child.cget("text") == text:
                return child
        except Exception:
            pass
        hit = _find_button(child, text)
        if hit is not None:
            return hit
_land_btn = _find_button(app, "Where to land")
_least = A.RAIL_WIDTH + A.SCROLLBAR_W + 420
app.geometry("%dx900" % _least); settle(6)
check("and it is on screen at the app's smallest width",
      inside(_land_btn, app), (_least, _land_btn.winfo_rootx(),
                               _land_btn.winfo_width(), app.winfo_width()))
_settings_btn = _find_button(app, "Settings")
check("so is everything to its right, Settings included",
      inside(_settings_btn, app), (_settings_btn.winfo_rootx(), app.winfo_width()))
app.watcher.system = _SYS
app.t_where.configure(text=_SYS + "  /  " + _SYS + " A 1"); settle(6)
check("and the readout still has room for a long system and body",
      app.t_where.winfo_width() >= app.t_where.winfo_reqwidth() - 2,
      (app.t_where.winfo_width(), app.t_where.winfo_reqwidth()))
check("because the buttons went under the readouts, not over them",
      app._top_stacked is True)
app.geometry("1400x900+0+0"); settle(6)
check_wide("given the width back, the buttons go back beside the readouts",
           lambda: app._top_stacked is False)
# 1.10033: a tester's screenshot - "mined aboard 59t worth ... Rhino session
# 8m ..." ran to 130 characters, the label asked for all of it, and the
# buttons shrank until Where to land read "re to l" and Earnings was gone.
app.t_earnings.configure(text="mined aboard 59t worth 12,272,059 Cr at Kassovitz "
                         "Point, up to 28,382,540 Cr within 100 Ly   Rhino "
                         "session 8m - 59 t mined, 45 t to the ship")
app.t_detail.configure(text="-37.94006, -143.44643   hdg 158 SSE   DSS: 7 "
                       "mining location(s)   238 K")
settle(8)
_squeezed = [b.cget("text") for b in (_find_button(app, t) for t in
             ("Find", "My sites", "Where to land", "Earnings", "Settings"))
             if b is not None and (b.winfo_width() < b.winfo_reqwidth() - 2
                                   or not inside(b, app))]
check_wide("a long earnings line wraps; every button keeps its whole width",
           lambda: not _squeezed and _find_button(app, "Earnings") is not None,
           lambda: _squeezed)
check_wide("and the earnings line stays inside the room left of the buttons",
           lambda: app.t_earnings.winfo_rootx() + app.t_earnings.winfo_width()
           <= _find_button(app, "Find").winfo_rootx() + 2,
           lambda: (app.t_earnings.winfo_width(), _find_button(app, "Find").winfo_rootx()))
lander = app.open_land()
settle(6)
check("the window opens on the system you are in",
      _SYS in lander.heading.cget("text"), lander.heading.cget("text"))
check("and asks the server for the grounds and this system's sites",
      "grounds" in _asked and _SYS in _asked, _asked)
app.take_grounds(True, json.dumps({"count": 1, "grounds": [
    {"ground": "Rocky body", "sites": 9, "commodities": [
        {"name": "Monazite", "sites": 5, "share": 0.55, "rigs": 20},
        {"name": "Haematite", "sites": 7, "share": 0.77, "rigs": 25}]}]}))
app.take_landing(True, json.dumps({"system": _SYS, "count": 1, "sites": [
    {"system": _SYS, "planet": _SYS + " A 1", "spot": "1", "rigs": 6,
     "types": ["Monazite", "Haematite"], "worked_out": False,
     "status": "verified", "uploader": "CMDR Somebody"}]}))
settle(6)
shown = texts_in(lander.table)
check("every heading is drawn", all(any(t.startswith(h) for t in shown)
                                    for h in A.LAND_HEADERS), shown[:16])
check("A 1 is at the top: a known intact site and three more locations",
      lander._rows and lander._rows[0]["short"] == "A 1",
      [r["short"] for r in lander._rows])
check("the ground's mix is named with its basis",
      any("(9 shared sites)" in t for t in shown), [t for t in shown if "(" in t][:4])
check("the body you cannot land on is not listed by default",
      "A 4" not in shown)
check("the status line names the best bet",
      lander.status.cget("text").startswith("Best bet: A 1"), lander.status.cget("text"))
check("asking again brings the same window forward", app.open_land() is lander)
lander.show_all.set(True); lander._paint(); settle(4)
check("the switch brings the others in", "A 4" in texts_in(lander.table))
lander.show_all.set(False); lander._paint(); settle(4)
lander.sort_by(A.LAND_HEADERS.index("Ls")); settle(4)
check("sorting on Ls puts the nearest first",
      [r["short"] for r in lander._sorted(list(lander._rows))][0] == "A 2")
check_wide("on a 1400-pixel window the whole table fits without scrolling sideways",
           lambda: lander.scroller.inner.winfo_reqwidth()
           <= lander.scroller.canvas.winfo_width(),
           lambda: str((lander.scroller.inner.winfo_reqwidth(),
                        lander.scroller.canvas.winfo_width())))
check_wide("and no empty sideways scrollbar is left drawn under it",
           lambda: not lander.scroller.hbar.winfo_ismapped()
           and not lander.scroller.hbar.winfo_manager())
check("and what it is worth and why are the first things after the body",
      A.LAND_HEADERS[:3] == ("Body", "Est. value", "Why"), A.LAND_HEADERS)
lander.geometry("820x500"); settle(6)
check("squeezed, the table scrolls sideways rather than losing columns",
      lander.scroller.hbar.winfo_ismapped(), lander.scroller.inner.winfo_reqwidth())
check("and the footnote is still on screen",
      inside(lander.footnote, lander), lander.footnote.winfo_rooty())
lander.geometry("1400x600"); settle(8)
check_wide("given the width back, the sideways scrollbar goes",
           lambda: not lander.scroller.hbar.winfo_ismapped())
# The toolkit re-applies a widget's last grid() whenever it rescales, which
# Windows makes it do at start-up. With grid_remove that brought back a
# full-width scrollbar with nothing to scroll, on every table.
lander.scroller.hbar._set_scaling(1.0, 1.0); settle(4)
check_wide("and a rescale does not bring it back",
           lambda: not lander.scroller.hbar.winfo_ismapped())
check("Copy all gives a block with a header line",
      lander.as_text().splitlines()[1].startswith("Body | Est. value | Why"), lander.as_text()[:80])
_BODIES.append({"body": _SYS + " A 7", "landable": True, "distance_ls": 5.0,
                "planet_class": "Rocky body", "volcanism": "", "gravity_g": 0.1,
                "temperature_k": 150.0, "locations": 9, "mapped": True})
import time as _time
_until = _time.time() + 2.5          # the app polls every 700 ms
while _time.time() < _until:
    settle(1); _time.sleep(0.05)
check("a body the DSS maps while it is open appears without a click",
      "A 7" in [r["short"] for r in lander._rows], [r["short"] for r in lander._rows])
lander.destroy(); settle(4)
check("closing it is noticed and nothing keeps polling a dead window",
      (app.follow_land(), app.lander)[1] is None)

print("== My sites: every place logged, on every body ==")
# "how to find a list of the planets and spots I've logged ... so I can
# return to them?"
_R = 1_800_000.0
app.store.set_location("Col 285 Sector AB-C d1-2", "Col 285 Sector AB-C d1-2 4 a",
                       "3", lat=4.0, lon=5.0, radius_m=_R,
                       commodities=["Bromellite", "Tellurium"])
app.store.add_deposit(system="Col 285 Sector AB-C d1-2",
                      body="Col 285 Sector AB-C d1-2 4 a", location="3",
                      commodity="Bromellite", rigs="5", amount="High",
                      lat="4.001", lon="5.001")
check("the button is in the top bar", _find_button(app, "My sites") is not None)
_sites = app.open_sites(); settle(6)
_cells = texts_in(_sites.table)
check("it lists a body that is not the one you are on",
      any("Col 285 Sector AB-C d1-2 4 a" in t for t in _cells), _cells[:12])
check("with what is there and what is still offered",
      any("Bromellite" in t and "offers Tellurium" in t for t in _cells), _cells[:20])
check("asking again brings the same window forward, re-read",
      app.open_sites() is _sites)
_sites.filter_box.insert(0, "col 285"); _sites._paint(); settle(4)
check("the filter narrows it to that system",
      len(_sites._rows) == 1 and _sites._rows[0]["signal"] == "3",
      [r["body"] for r in _sites._rows])
_sites.filter_box.delete(0, "end"); _sites._paint(); settle(4)
check_wide("on a 1400-pixel window the table fits without scrolling sideways",
           lambda: _sites.scroller.inner.winfo_reqwidth()
           <= _sites.scroller.canvas.winfo_width(),
           lambda: str((_sites.scroller.inner.winfo_reqwidth(),
                        _sites.scroller.canvas.winfo_width())))
check("the footnote says how to get back there",
      "galaxy map" in _sites.footnote.cget("text"))
_sites.destroy(); settle(4)

print("== Earnings: both holds, and where to take them from here ==")
# Reported: the earnings showed nothing with ore already in the ship or the
# SRV, and "Sapphire is showing 127k - is this average galactic price? Call
# up the system someone is in to show the real sale price."
import time as _time


class _Asks:
    """The real client, except that asking for a price is recorded."""
    can_read = True

    def __init__(self, real):
        self._real, self.calls = real, []

    def sell(self, **k):
        self.calls.append(k)
        return True

    def __getattr__(self, name):
        return getattr(self._real, name)


_real_comm = app.community
app.community = _Asks(_real_comm)
# 1.10031: the tab is about what the Rhino dug up. Five Tea bought at a
# station are in the ship too, and must not be priced here.
app.watcher.holds = {"Ship": {"Haematite": 30, "Tea": 5}, "SRV": {"Sapphire": 2}}
app.watcher.cargo = {"Sapphire": 2}
app.watcher.system = "HR 7280"
app.watcher.star_pos = (1.0, 2.0, 3.0)
_run = app.earnings.start("HR 7280", "HR 7280 A 1", "Jameson")
_run["mined"] = "Rhodplumsite:61;Ruby:11"
_run["transferred"] = "Rhodplumsite:61;Ruby:11"
_run["trips"] = "2"
app.earnings.save()
# A run an older build wrote - a landing and a sale of Tea - sits in the same
# file and must not be on the tab.
_old = {k: "" for k in SV.SESSION_FIELDS}
_old.update({"id": "old1", "started": "2026-09-20T10:00:00Z",
             "ended": "2026-09-20T11:00:00Z", "closed": "2026-09-20T11:00:00Z",
             "system": "Trade Hub", "body": "", "sold": "Tea:40",
             "credits": "40000"})
app.earnings.sessions.insert(0, _old)
# The session this afternoon that dug up what is aboard now.
_dug = {k: "" for k in SV.SESSION_FIELDS}
_dug.update({"id": "dug1", "kind": SV.RHINO, "started": SV.utc_now(),
             "ended": SV.utc_now(), "closed": SV.utc_now(),
             "system": "HR 7280", "body": "HR 7280 A 3",
             "mined": "Haematite:30;Sapphire:2"})
app.earnings.sessions.insert(1, _dug)
app.earnings.save()
app.open_earnings()
_end = _time.time() + 2.0
while _time.time() < _end:
    settle(1); _time.sleep(0.05)
ledger = app.ledger
_holding = ledger.holding.cget("text")
check("the hold line names the SRV and the ship, each with its tonnes",
      "SRV 2t" in _holding and "ship 30t" in _holding, _holding)
check("and leaves the Tea out - it was bought, not mined",
      "Tea" not in _holding, _holding)
check("with an estimate at the galactic average",
      "galactic average" in _holding, _holding)
check("opening it with ore aboard asks where to sell it, most valuable first",
      [k.get("commodity") for k in app.community.calls] == ["Sapphire", "Haematite"],
      app.community.calls)
check("asked from the system I am in",
      all(k.get("near_system") == "HR 7280" for k in app.community.calls),
      app.community.calls)
app.take_quote(True, json.dumps({"commodity": "Sapphire", "market": [
    {"station": "Mandi Port", "system": "Ten Mandi", "sell": 648000,
     "distance_ly": 8.2, "seen": "2026-09-23T10:00:00Z"}], "community": [
    {"station": "Home Dock", "system": "HR 7280", "sell": 301000,
     "seen": "2026-09-24T09:00:00Z"}]}))
settle(4)
_cells = texts_in(ledger.quote_table)
check("the best price is drawn, with where and how far",
      "648,000" in _cells and "Mandi Port, Ten Mandi (8.2 Ly)" in _cells, _cells)
check("beside what this system pays", "301,000" in _cells, _cells)
check("and what the hold's worth of it fetches there", "1,296,000 Cr" in _cells, _cells)
check("the main strip quotes it too, and says what is not priced yet",
      "up to 1,296,000 Cr within 100 Ly (1 of 2 priced)"
      in app.t_earnings.cget("text"), app.t_earnings.cget("text"))
_ledger_text = " ".join(texts_in(ledger.table))
check("the session says what the Rhino mined and what went to the ship",
      "72t: Rhodplumsite 61, Ruby 11" in _ledger_text
      and "(2 trips)" in _ledger_text, _ledger_text[:400])
check("and only Rhino sessions are on the tab - not an older build's Tea run",
      "Trade Hub" not in _ledger_text and "Tea" not in _ledger_text,
      _ledger_text[:400])
check("Start session and Pause are on the window, next to End session",
      "Start session" in texts_in(ledger) and "Pause" in texts_in(ledger),
      texts_in(ledger)[:30])
check("the multi-session box and End session are on the window",
      "End session" in texts_in(ledger)
      and any("Multi-session" in t for t in texts_in(ledger)),
      texts_in(ledger)[:30])
_check_btn = next((b for b in texts_in(ledger) if b == "Check prices"), None)
check("Check prices is on the window", _check_btn == "Check prices")
# 1.10032: "we need to be able to delete entries from the earnings section".
check("every session row has a delete button",
      texts_in(ledger.table).count("delete") == len(ledger._rows) >= 2,
      (texts_in(ledger.table).count("delete"), len(ledger._rows)))
_victim = next(r for r in ledger._rows if r.get("id") == "dug1")
_before = len(app.earnings.sessions)
ledger.delete_session(_victim); settle(2)
check("one press only asks - nothing is deleted yet",
      len(app.earnings.sessions) == _before
      and "again" in ledger.status.cget("text"), ledger.status.cget("text"))
ledger.delete_session(_victim); settle(2)
check("the second press on the same row deletes it, from the tab and the file",
      len(app.earnings.sessions) == _before - 1
      and not any(r.get("id") == "dug1" for r in ledger._rows)
      and "dug1" not in open(app.earnings.path, encoding="utf-8").read())
check("and the file before it is kept beside it",
      "dug1" in open(app.earnings.path + ".bak", encoding="utf-8").read())
app.earnings.finish()
ledger.destroy()
app.community = _real_comm
app.watcher.holds, app.watcher.cargo = {}, {}
settle()

print("== 1.10033: prices in a system, and several commodities ticked ==")
# "on the earnings tab can we have a search system price that checks the last
# known price for the commodities etc. also when searching on any thing that
# has a find feature we must be able to click muiltiple"


class _Rec:
    """The real client, with every search recorded instead of sent."""
    can_read = True

    def __init__(self, real):
        self._real, self.calls = real, []

    def _note(self, name):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return True
        return call

    def __getattr__(self, name):
        if name in ("system_prices", "sites", "intact", "search", "sell",
                    "best_prices"):
            return self._note(name)
        return getattr(self._real, name)


def wait(seconds):
    end = _time.time() + seconds
    while _time.time() < end:
        settle(1); _time.sleep(0.05)


def list_rows(sugg):
    return [sugg.listbox.get(i) for i in range(sugg.listbox.size())]


def click_row(sugg, name):
    """Click a row of a list the way a mouse does: on the row, then let go."""
    if not sugg.visible():
        # The list is the thing under test here, not the desktop's focus -
        # on the build server a new window does not always get it.
        sugg.show(); settle(3)
    index = sugg._shown.index(name)
    box = None
    for _ in range(20):
        # A list just redrawn has no row boxes until Tk has laid it out.
        sugg.listbox.see(index); settle(2)
        box = sugg.listbox.bbox(index)
        if box is not None:
            break
        _time.sleep(0.02)
    sugg.listbox.event_generate("<ButtonRelease-1>", x=box[0] + 4,
                                y=box[1] + box[3] // 2, when="now")
    settle(4)


_real_comm = app.community
app.community = _Rec(_real_comm)
app.watcher.system = "HR 7280"
app.open_earnings()
wait(1.0)
ledger = app.ledger
pick = ledger.system_pick
ledger.deiconify(); ledger.lift(); ledger.focus_force(); settle(4)


def click_into(box):
    """Click into a box the way the mouse does - which also gives it the
    keyboard, whatever window the desktop thinks is in front."""
    entry = entry_of(box)
    entry.focus_force()
    entry.event_generate("<Button-1>", x=6, y=6, when="now")
    entry.event_generate("<ButtonRelease-1>", x=6, y=6, when="now")
    settle(4)


click_into(pick)
ps = pick.suggest
check("the commodity box under Prices in a system opens its list on click",
      ps.visible() and ps.multi, (ps.visible(), ps.multi))
check("and the list is a list of tick boxes",
      any(r.strip().startswith("[ ]") for r in list_rows(ps)), list_rows(ps)[:3])
click_row(ps, "Magnesite")
check("clicking one ticks it", pick.get() == "Magnesite", pick.get())
check("and the list stays open for the next", ps.visible())
click_row(ps, "Bastnäsite")
check("clicking another ticks that as well", pick.get() == "Magnesite, Bastnäsite",
      pick.get())
check("both are shown ticked",
      sum(1 for r in list_rows(ps) if r.strip().startswith("[x]")) == 2,
      list_rows(ps))
click_row(ps, "Magnesite")
check("clicking a ticked one again unticks it", pick.get() == "Bastnäsite", pick.get())
click_row(ps, "Magnesite")
pick._dropdown_callback("Sapphire"); settle(3)
check("the box's own arrow list ticks too, instead of throwing the others away",
      pick.get() == "Bastnäsite, Magnesite, Sapphire", pick.get())
pick._dropdown_callback("Sapphire"); settle(3)
ledger.system_box.delete(0, "end")
ledger.system_box.insert(0, "Wyrd")
ledger.search_system(); settle(3)
_asked = [c for c in app.community.calls if c[0] == "system_prices"]
check("Search system asks for that system and the ticked commodities, in one go",
      len(_asked) == 1 and _asked[0][1][:2] == ("Wyrd", ["Bastnäsite", "Magnesite"])
      and _asked[0][2].get("tag") == A.SYSTEM_PRICE_TAG, _asked)
ledger.system_box.delete(0, "end")
ledger.search_system(); settle(2)
_asked = [c for c in app.community.calls if c[0] == "system_prices"]
check("left blank, it is the system the game has us in",
      len(_asked) == 2 and _asked[1][1][0] == "HR 7280", _asked[-1:])
_ANSWER = {"system": "Wyrd", "upstream": "index", "upstream_status": "live",
           "commodities": ["Bastnäsite", "Magnesite"], "count": 4, "prices": [
    {"commodity": "Bastnäsite", "station": "Black Hide", "station_type": "CraterOutpost",
     "pad": 2, "sell": 49538, "demand": 3, "seen": "2026-10-07T00:41:01.000Z",
     "source": "index"},
    {"commodity": "Magnesite", "station": "Vonarburg Co-operative",
     "station_type": "Orbis", "pad": 3, "sell": 120500, "demand": 40,
     "seen": SV.utc_now(), "source": "community"},
    {"commodity": "Magnesite", "station": "Bokeili Station", "station_type": "Orbis",
     "pad": 3, "sell": 41239, "demand": 0, "seen": "2026-10-06T22:59:24.000Z",
     "source": "index"},
    {"commodity": "Magnesite", "station": "Black Hide", "station_type": "CraterOutpost",
     "pad": 2, "sell": 22911, "demand": 0, "seen": "2026-08-01T00:41:01.000Z",
     "source": "index"}]}
app.worker.results.put((A.SYSTEM_PRICE_TAG, True, json.dumps(_ANSWER)))
app.collect_results(); settle(6)
_cells = texts_in(ledger.table)
check("the answer lands in the Earnings window, on the System prices view",
      ledger._view == "prices" and "Commodity" in " ".join(_cells), _cells[:12])
check("best market only: one row a commodity, the best one",
      "120,500" in _cells and "41,239" not in _cells and "49,538" in _cells, _cells)
check("with the station, its pad and how many markets buy it",
      "Vonarburg Co-operative" in _cells and "L" in _cells and "3" in _cells, _cells)
check("and when that price was last known, and whose it is",
      any(c.startswith("today") for c in _cells) and "community" in _cells, _cells)
check("the status line says what came back",
      "Wyrd: 2 commodities priced at 3 markets." in ledger.status.cget("text"),
      ledger.status.cget("text"))
ledger.system_best.set(False); ledger._paint(); settle(6)
_cells = texts_in(ledger.table)
check("unticked, every market is listed", "41,239" in _cells and "22,911" in _cells,
      _cells)
_sell_head = next(w for w in ledger.table.winfo_children()
                  if isinstance(w, A.ctk.CTkButton) and _text_of(w).startswith("Sell"))
_sell_head.invoke(); settle(6)
_sorted_sells = [int(c.replace(",", "")) for c in texts_in(ledger.table)
                 if c.replace(",", "").isdigit() and len(c) > 4]
check("click Sell to sort on it", _sorted_sells == sorted(_sorted_sells), _sorted_sells)
ledger.copy_all(); settle(2)
_clip = app.clipboard_get()
check("Copy all copies the prices while they are showing",
      _clip.startswith("Wyrd - last known prices") and "Vonarburg Co-operative" in _clip,
      _clip[:120])
check_wide("Search system is inside the window",
           lambda: inside(next(w for w in A_walk(ledger)
                               if _text_of(w) == "Search system"), ledger),
           lambda: "Search system is off the edge")
ledger.show_view("sessions"); settle(6)
check("the Rhino sessions button puts the sessions back",
      "Copy / delete" in texts_in(ledger.table) or
      any("No Rhino sessions" in t or "Rhino" in t for t in texts_in(ledger.table)),
      texts_in(ledger.table)[:6])
ledger.destroy(); settle()

app.open_find(); settle(6)
finder = app.finder
fc = finder.commodity
finder.deiconify(); finder.lift(); finder.focus_force(); settle(4)
click_into(fc)
click_row(fc.suggest, "Monazite"); click_row(fc.suggest, "Ruby")
check("Find: tick two commodities", finder._commodities() == ["Monazite", "Ruby"],
      finder._commodities())
fe = entry_of(fc)
fe.focus_force(); settle(3)
fe.icursor("end")
for ch, sym in ((",", "comma"), (" ", "space"), ("s", "s"), ("a", "a"), ("p", "p")):
    press(fe, sym, ch)
check("typing after a comma filters on the new word only",
      fc.suggest._shown and fc.suggest._shown[0] == "Sapphire", fc.suggest._shown[:3])
press(fe, "Return")
check("and Enter adds it to the two already ticked",
      fc.get() == "Monazite, Ruby, Sapphire", fc.get())
click_row(fc.suggest, "Sapphire")
check("a click takes it off again", fc.get() == "Monazite, Ruby", fc.get())
for ch, sym in ((",", "comma"), ("q", "q"), ("q", "q")):
    press(fe, sym, ch)
check("a word that matches nothing shows nothing - not a lone Any",
      not fc.suggest.visible(), fc.suggest._shown)
press(fe, "Return")
check("so Enter on a typo cannot wipe what is ticked",
      fc.suggest.picked() == ["Monazite", "Ruby"], fc.get())
press(fe, "Tab")
check("and leaving the box tidies the typo away",
      fc.get() == "Monazite, Ruby", fc.get())
app.community.calls.clear()
finder.search_sites(); settle(2)
_s = [c for c in app.community.calls if c[0] == "sites"]
check("Search sites asks for either of them, in one request",
      _s and _s[0][2].get("commodity") == "Monazite,Ruby", _s)
finder.results("sites", json.dumps({"sites": []}), True); settle(4)
check("a server that does not understand two is said so, not shown as nothing found",
      "updated" in finder.status.cget("text"), finder.status.cget("text"))
finder.results("sites", json.dumps(dict(SITES, commodities=["Monazite", "Ruby"])), True)
settle(4)
check("and a server that does gets its table drawn",
      "Col 285 Sector ZL-K b22-2" in texts_in(finder.table))
app.community.calls.clear()
finder.search_prices(); settle(2)
_sells = [c for c in app.community.calls if c[0] == "sell"]
check("Best sell prices for two: the first goes straight away",
      [c[2].get("commodity") for c in _sells] == ["Monazite"], _sells)
wait(A.QUOTE_GAP_MS / 1000.0 + 0.6)
_sells = [c for c in app.community.calls if c[0] == "sell"]
check("and the second a moment after, so the market index is not hammered",
      [c[2].get("commodity") for c in _sells] == ["Monazite", "Ruby"], _sells)
finder.results("sell", json.dumps({"commodity": "Monazite", "market": [
    {"commodity": "Monazite", "station": "Port A", "system": "Sys A", "sell": 300000,
     "distance_ly": 5, "seen": "2026-10-06", "source": "index"}], "community": []}), True)
settle(4)
check("the first answer is shown at once, and it says the other is coming",
      "300,000" in texts_in(finder.table) and "1 of 2" in finder.status.cget("text"),
      finder.status.cget("text"))
finder.results("sell", json.dumps({"commodity": "Ruby", "market": [
    {"commodity": "Ruby", "station": "Port B", "system": "Sys B", "sell": 90000,
     "distance_ly": 9, "seen": "2026-10-06", "source": "index"}], "community": []}), True)
settle(4)
check("and the second joins it in the same table",
      "300,000" in texts_in(finder.table) and "90,000" in texts_in(finder.table),
      texts_in(finder.table)[:20])
finder.destroy(); settle()
app.community = _real_comm

print("== first run: the community-map notice holds the keyboard until answered ==")
app.settings["asked_to_share"] = False
app.ask_to_share(); settle(6)
_welcome = [w for w in app.winfo_children() if isinstance(w, A.WelcomeWindow)]
check("the question opens", len(_welcome) == 1, app.winfo_children())
check("and nothing behind it can be typed into until it is answered",
      _welcome and app.grab_current() is _welcome[0], str(app.grab_current()))
check("it has been recorded as asked", app.settings.get("asked_to_share") is True)
# The Rhino across the top of it, and the answer buttons still in the window.
# Asked of what the window NEEDS rather than where it is drawn: on the build
# server a window that has the grab is not always on screen yet when this
# runs, and an undrawn window reports one pixel for everything.
_pics = [w for w in A_walk(_welcome[0]) if isinstance(w, tk.Label)
         and str(w.cget("image"))]
check("the Rhino is across the top of the first-run window",
      _pics and _pics[0].winfo_reqwidth() >= 500, [p.winfo_reqwidth() for p in _pics])
_body_needs = _pics[0].master.winfo_reqheight() if _pics else 10 ** 6
_given = A.WELCOME_SIZE[1]
check("with the two answers still inside the window under it",
      _body_needs + 24 <= _given, (_body_needs, _given))
_welcome[0].answer(False); settle(6)
check("answering closes it", not _welcome[0].winfo_exists())
check("and gives the keyboard back", app.grab_current() is None, str(app.grab_current()))
check("Stay anonymous takes the name off, and the finds are still shared",
      app.settings.get("community_share_cmdr_name") is False
      and app.settings.get("community_enabled") is True)
entry_of(app.fields["commodity"]).focus_force(); settle(4)
press(entry_of(app.fields["commodity"]), "Escape")
app.fields["commodity"].set("")
for ch in "iri":
    press(entry_of(app.fields["commodity"]), ch, ch)
check("and typing in the boxes works again straight after",
      app.fields["commodity"].get() == "iri", app.fields["commodity"].get())

app.destroy()
shutil.rmtree(_HOME, ignore_errors=True)
print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
