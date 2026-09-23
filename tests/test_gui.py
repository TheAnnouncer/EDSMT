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
ov.hide()
pump()

# ---------------------------------------------------------------------------
# The app's own windows
# ---------------------------------------------------------------------------
import json, tempfile, shutil
_HOME = tempfile.mkdtemp(prefix="edsmt-gui-")
os.environ["HOME"] = _HOME
os.environ["LOCALAPPDATA"] = _HOME
root.destroy()                      # the app brings its own root
import edsmt as A                   # noqa: E402
from survey import fold as SV_fold  # noqa: E402
A.DATA_DIR = _HOME
A.SETTINGS_FILE = os.path.join(_HOME, "settings.json")
# An empty settings folder is a first run, and a first run puts the sharing
# question up 900 ms in: a modal window that takes the keyboard. On a quick
# machine the typing checks below finished before it arrived; on a slower
# one it landed in the middle of them and every key went to it - six false
# failures on Windows in 1.10028, with the type-ahead itself working. Here
# the question has been answered; it gets its own checks at the end.
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
    json.dump({"asked_to_share": True}, _f)
app = A.EDSMT()
app.geometry("1400x900+0+0")
root = app
# Nothing in here asks the live site whether there is a newer version.
app.updates.check = lambda *args, **kwargs: None

def settle(times=4):
    for _ in range(times):
        app.update_idletasks()
        app.update()

def inside(widget, window):
    """Is the whole of `widget` inside `window`'s visible area?"""
    wx, wy = widget.winfo_rootx(), widget.winfo_rooty()
    ox, oy = window.winfo_rootx(), window.winfo_rooty()
    return (wx >= ox and wy >= oy
            and wx + widget.winfo_width() <= ox + window.winfo_width() + 1
            and wy + widget.winfo_height() <= oy + window.winfo_height() + 1)

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
check("on a 1400-pixel window every column is on screen without scrolling",
      _score and inside(_score[0], finder.scroller.canvas), "Score is off the edge")
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

print("== Settings: the rig warning distance is a number or it is refused ==")
_sw = A.SettingsWindow(app)
settle(4)
_said = []
_sw.say = lambda text, colour=None: _said.append(text)
_saved = []
_real_apply = app.apply_settings
app.apply_settings = lambda data: _saved.append(data)
_sw.fields["rig_warn_m"].delete(0, "end"); _sw.fields["rig_warn_m"].insert(0, "a long way")
_sw.save(); settle(2)
check("a distance that is not a number is refused with a reason",
      not _saved and _said and "metres" in _said[-1], _said[-1:])
_sw.fields["rig_warn_m"].delete(0, "end"); _sw.fields["rig_warn_m"].insert(0, "1,500")
_sw.save(); settle(2)
check("1,500 is saved as 1500 metres",
      _saved and _saved[-1].get("rig_warn_m") == 1500.0, _saved[-1:] and _saved[-1].get("rig_warn_m"))
app.apply_settings = _real_apply
try:
    _sw.destroy()
except Exception:
    pass
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

print("== the deposit UPDATE button and the new-build button are two buttons ==")
# They shared the name btn_update, so an update announcement relabelled the
# deposit button UPDATE AVAILABLE and moved it.
check("the top bar's button is the new-build one",
      app.btn_update.cget("text") == "UPDATE AVAILABLE", app.btn_update.cget("text"))
check("the rail's is the deposit one",
      app.btn_update_deposit.cget("text") == "UPDATE", app.btn_update_deposit.cget("text"))
app.announce_update("EDSMT 9.99999 is out.")
settle(3)
check("announcing a build leaves the deposit button alone",
      app.btn_update_deposit.cget("text") == "UPDATE"
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
check("given the width back, the buttons go back beside the readouts",
      app._top_stacked is False)
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
check("on a 1400-pixel window the whole table fits without scrolling sideways",
      lander.scroller.inner.winfo_reqwidth() <= lander.scroller.canvas.winfo_width(),
      (lander.scroller.inner.winfo_reqwidth(), lander.scroller.canvas.winfo_width()))
check("and what it is worth and why are the first things after the body",
      A.LAND_HEADERS[:3] == ("Body", "Est. value", "Why"), A.LAND_HEADERS)
lander.geometry("820x500"); settle(6)
check("squeezed, the table scrolls sideways rather than losing columns",
      lander.scroller.hbar.winfo_ismapped(), lander.scroller.inner.winfo_reqwidth())
check("and the footnote is still on screen",
      inside(lander.footnote, lander), lander.footnote.winfo_rooty())
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

print("== first run: the sharing question holds the keyboard until answered ==")
app.settings["asked_to_share"] = False
app.ask_to_share(); settle(6)
_welcome = [w for w in app.winfo_children() if isinstance(w, A.WelcomeWindow)]
check("the question opens", len(_welcome) == 1, app.winfo_children())
check("and nothing behind it can be typed into until it is answered",
      _welcome and app.grab_current() is _welcome[0], str(app.grab_current()))
check("it has been recorded as asked", app.settings.get("asked_to_share") is True)
_welcome[0].answer(False); settle(6)
check("answering closes it", not _welcome[0].winfo_exists())
check("and gives the keyboard back", app.grab_current() is None, str(app.grab_current()))
check("Not now leaves sharing off", app.settings.get("community_enabled") is False)
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
