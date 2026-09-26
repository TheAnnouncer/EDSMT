"""The map and the overlay open on the signal being worked, and the keys
say what they did over the game.

Reported with a screenshot: the map opened 1,300 km wide with fifty ring
labels stacked in one column and every find a dot, because one body held
finds thousands of kilometres apart and the view was sized to hold them all.
The scope in the game did the same at its 50 km cap. This file holds the
maths that fixes it, the key defaults, the rig distance a person types, and
the words the overlay flashes - all without a display.
"""
import os, sys, math, json, tempfile, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "stubs"))
import _ctkstub  # noqa
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="edsmt-signal-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
import edsmt as A  # noqa
import overlay as OV  # noqa
import planview as PV  # noqa

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)


def row(range_m, bearing, location="5", commodity="Haematite", **kw):
    deposit = {"id": kw.pop("id", "%s-%s" % (range_m, bearing)),
               "location": location, "commodity": commodity}
    deposit.update(kw)
    return {"range_m": float(range_m), "bearing": float(bearing),
            "deposit": deposit}


# His body, roughly: signal 5 around the SRV, a signal 2 at 3,700 km and a
# spread of other people's finds at 9,800 km.
HERE_ROWS = [row(536, 40), row(620, 55, commodity="Sapphire"),
             row(1400, 300, commodity="Thorium"), row(2100, 200, location="")]
FAR_ROWS = [row(3_732_000, 300, location="2", commodity="Platinum"),
            row(9_840_000, 330, location="7", commodity="Rhodplumsite"),
            row(9_844_000, 331, location="7", commodity="Iridium")]
ALL = HERE_ROWS + FAR_ROWS

print("== which finds belong to the signal ==")
view = PV.signal_focus(ALL, "5")
check("its own finds, and the unnumbered one standing among them",
      len(view["here"]) == 4, [r["deposit"]["commodity"] for r in view["here"]])
check("and the other signals' finds are elsewhere, not dropped",
      len(view["away"]) == 3)
check("it says it found the signal from its finds", view["how"] == "finds")
logged = PV.signal_focus(ALL, "5", anchor=(300.0, 400.0))
check("a logged position wins over working it out", logged["how"] == "logged"
      and logged["centre"] == (300.0, 400.0))
typo = PV.signal_focus([row(500, 10), row(4_000_000, 90)], "5")
check("one typo on the far side of the body is not the middle of the map",
      typo["centre"][1] > 0 and math.hypot(*typo["centre"]) < 1000,
      typo["centre"])
nothing = PV.signal_focus(FAR_ROWS, "9")
check("a signal with nothing logged opens on the commander",
      nothing["how"] == "commander" and not nothing["here"]
      and len(nothing["away"]) == 3)

print("== the rings ==")
check("steps run out to planet scale", PV.NICE_STEPS_M[-1] >= 5_000_000)
for extent in (300.0, 2500.0, 12_000.0, 1_300_000.0, 12_800_000.0):
    rings = PV.layout([], PV.Viewport(600, 600, extent))["rings"]
    check("never more than five rings at %s" % A._metres(extent),
          1 <= len(rings) <= 5, len(rings))
check("ten thousand km reads with a separator", A._metres(9_848_000) == "9,848 km",
      A._metres(9_848_000))

print("== labels that do not print on top of each other ==")
check("two boxes that overlap touch", PV.boxes_touch((0, 0, 10, 10), (5, 5, 15, 15)))
check("two apart do not", not PV.boxes_touch((0, 0, 10, 10), (20, 0, 30, 10)))
taken = [(100, 100, 160, 112)]
spot = PV.label_spot([(100, 100, 160, 112), (30, 100, 90, 112)], taken)
check("a label taken on one side goes to the other", spot == (30, 100, 90, 112), spot)
check("with every side taken it is left off, not printed over",
      PV.label_spot([(100, 100, 160, 112)], taken) is None)
check("a label that would run off the canvas is not used",
      PV.label_spot([(590, 0, 650, 12)], [], bounds=(0, 0, 600, 600)) is None)

print("== one arrow per direction ==")
viewport = PV.Viewport(600, 600, 2500.0)
plan = PV.layout(ALL, viewport)
groups = PV.group_offscreen(plan["items"])
check("the two 9,840 km finds that way are one arrow",
      any(g["count"] == 2 for g in groups), [(g["count"], g["range_m"]) for g in groups])
check("and it carries the nearest distance",
      all(g["range_m"] == min(i["range_m"] for i in g["items"]) for g in groups))

print("== the ground swept stays inside the border ==")
points = [(0.0, 0.0), (3000.0, 0.0), (9000.0, 0.0)]
shapes = PV.swept_shapes(points, 2000.0, centre=(0.0, 0.0), border_m=4000.0)
kinds = [s[0] for s in shapes]
check("a disc inside is a disc, one across is cut, one outside is gone",
      kinds == ["disc", "poly"], kinds)
cut = shapes[1][1]
check("and nothing of the cut one is past the border",
      max(math.hypot(e, n) for e, n in cut) <= 4000.0 + 1e-6)
check("without a border every disc is whole",
      [s[0] for s in PV.swept_shapes(points, 2000.0)] == ["disc"] * 3)
check("a round scope is a second fence",
      all(s[0] == "poly" or math.hypot(s[1], s[2]) + s[3] <= 1500
          for s in PV.swept_shapes([(0, 0), (1000, 0)], 800.0,
                                   view=((0.0, 0.0), 1500.0))))

print("== the overlay boxes follow the signal too ==")
class _Canvas:
    def __init__(self): self.calls = []
    def delete(self, *_a): self.calls = []
    def __getattr__(self, name):
        def record(*a, **kw): self.calls.append((name, a, kw))
        return record
class _Win:
    def winfo_width(self): return 420
    def winfo_height(self): return 420
    def winfo_screenwidth(self): return 1920
    def winfo_screenheight(self): return 1080
class _App:
    def colour_for(self, name): return "#ff7a18"
def texts(canvas):
    return [str(kw.get("text", "")) for n, _a, kw in canvas.calls if n == "create_text"]
for mode in ("radar", "strip"):
    ov = OV.Overlay(app=_App(), tk_module=None,
                    settings={"overlay_mode": mode, "overlay_click_through": True})
    ov.window, ov.canvas = _Win(), _Canvas()
    ov.draw(ALL, 0.0, location="5")
    said = " ".join(texts(ov.canvas))
    check("%s: no 3,732 km or 9,840 km find on it" % mode,
          "3,732" not in said and "9,84" not in said and "Platinum" not in said,
          said[:200])
    check("%s: and the three are counted as elsewhere" % mode, ov._elsewhere == 3,
          ov._elsewhere)
empty = OV.Overlay(app=_App(), tk_module=None, settings={"overlay_mode": "strip"})
empty.window, empty.canvas = _Win(), _Canvas()
empty.draw(FAR_ROWS, 0.0, note="nothing recorded on this body yet", location="5")
check("with nothing at the signal it says how many are elsewhere",
      any("3 elsewhere on this body" in t for t in texts(empty.canvas)),
      texts(empty.canvas))

print("== rigs on the compass ==")
rigs = {"limit_m": 3500, "rigs": [
    {"n": 1, "range_m": 1200.0, "bearing": 10.0},
    {"n": 2, "range_m": 3100.0, "bearing": 12.0},
    {"n": 3, "range_m": 4000.0, "bearing": 200.0}]}
marks = OV.rig_tape_marks(rigs, 0.0, 800)
check("every rig is on the tape", sorted(m["n"] for m in marks) == [1, 2, 3])
check("two rigs the same way are nudged apart",
      abs([m for m in marks if m["n"] == 1][0]["x"]
          - [m for m in marks if m["n"] == 2][0]["x"]) >= 30)
behind = [m for m in marks if m["n"] == 3][0]
check("a rig behind you is pinned to the end", behind["offscreen"]
      and behind["x"] in (16.0, 800 - 16.0), behind)
check("past the warning it is marked far", behind["far"])
check("past 2.9 km it is off the Contacts panel",
      [m for m in marks if m["n"] == 2][0]["off_contacts"])
strip = OV.Overlay(app=_App(), tk_module=None, settings={"overlay_mode": "strip"})
strip.window, strip.canvas = _Win(), _Canvas()
strip.draw(HERE_ROWS, 0.0, location="5", rigs=dict(rigs, far=False))
check("and they are drawn on the strip, numbered",
      sum(1 for n, a, kw in strip.canvas.calls
          if n == "create_rectangle" and "rigtape" in kw.get("tags", ())) == 3)

print("== the boxes only over the game ==")
real_front = OV.foreground_is_game
class _Panel:
    def __init__(self): self.window = self; self.shown = True
    def withdraw(self): self.shown = False
    def deiconify(self): self.shown = True
    def lift(self): pass
ov = OV.Overlay(app=_App(), tk_module=None, settings={"overlay_click_through": True})
ov.panels = {"strip": _Panel()}
OV.foreground_is_game = lambda: False
check("locked, with something else in front, they come down",
      ov.follow_game() is False and not ov.panels["strip"].shown)
OV.foreground_is_game = lambda: True
check("the game in front puts them back", ov.follow_game() is True
      and ov.panels["strip"].shown)
OV.foreground_is_game = lambda: False
ov.settings["overlay_click_through"] = False
check("unlocked they stay up whatever is in front - that is arranging",
      ov.follow_game() is True and ov.panels["strip"].shown)
ov.settings["overlay_click_through"] = True
OV.foreground_is_game = lambda: None
check("where Windows cannot be asked they stay up", ov.follow_game() is True)
OV.foreground_is_game = lambda: False
ov.settings["overlay_only_over_game"] = False
check("and the switch in Settings keeps them up", ov.follow_game() is True)
OV.foreground_is_game = real_front

print("== what a key says over the game ==")
check("a short sentence is the whole heading",
      A.flash_lines("No surface position from the game yet.")
      == ("NO SURFACE POSITION FROM THE", "game yet"),
      A.flash_lines("No surface position from the game yet."))
check("only the first sentence", A.flash_lines("Rig 2 down. More.")[0] == "RIG 2 DOWN")
check("nothing to say is nothing flashed", A.flash_lines("  ") == ("", ""))
flashes = []
app = A.EDSMT.__new__(A.EDSMT)
app.overlay = type("O", (), {"flash": lambda self, t, d="", c=None:
                             flashes.append((t, d)) or True})()
app._last_said = ("Rig 3 is already marked here.", A.AMBER)
app.flash_said()
check("a key that only said something has that flashed",
      flashes and flashes[-1][0] == "RIG 3 IS ALREADY MARKED HERE", flashes)
sent = []
ov = OV.Overlay(app=_App(), tk_module=None, settings={"overlay_flash": False})
check("the flash can be switched off", ov.flash("RIG 1 DOWN") is False)
OV.foreground_is_game = lambda: False
ov = OV.Overlay(app=_App(), tk_module=None, settings={})
check("and says nothing with the game not in front", ov.flash("RIG 1 DOWN") is False)
OV.foreground_is_game = real_front

print("== a distance as a person types it ==")
for typed, metres in (("3950", 3950.0), ("3950.00", 3950.0), ("3,950", 3950.0),
                      (" 3950 ", 3950.0), ("3950m", 3950.0), ("3950 m", 3950.0),
                      ("3.95 km", 3950.0), ("3.95", 3950.0), ("4", 4000.0),
                      ("", 0.0), ("0", 0.0)):
    got = A.parse_metres(typed)
    check("%r is %s" % (typed, A._metres(metres)), got is not None
          and abs(got - metres) < 0.01, got)
for junk in ("a long way", "-5", "nan"):
    check("%r is refused" % junk, A.parse_metres(junk) is None, A.parse_metres(junk))

print("== keys for the SRV, and a settings file from before them ==")
# His request: Left Alt and the number row, in the order a signal is worked -
# centre, border, deposit, rig down, rigs up, update - so step 3 is Alt+3.
# ("Lets do alt 1 alt2 etc as the fbuttons can get confusion")
NEW = ["ALT+1", "ALT+2", "ALT+3", "ALT+4", "ALT+5", "ALT+6"]
WORK = ("hotkey_location", "hotkey_border", "hotkey_deposit", "hotkey_rigs",
        "hotkey_allup", "hotkey_update")
order = [A.DEFAULT_SETTINGS[name] for name in WORK]
check("the keys go Alt+1 to Alt+6 in the order the work is done",
      order == NEW, order)
check("the app, Settings' Reset and the overlay all read one table",
      [A.OV.WORK_KEYS[n] for n in WORK] == NEW
      and [key for _n, key in A.KEY_ORDER] == NEW)
check("no function key is a default any more", not any(
      str(v).upper().startswith(("F", "ALT+F")) for k, v in A.DEFAULT_SETTINGS.items()
      if k.startswith("hotkey_") and isinstance(v, str)))
check("every one of them is a key Windows can register, on the number row",
      all(A.parse_binding(key) == (A.MOD_ALT, 0x30 + n)
          for n, key in enumerate(order, start=1)),
      [A.parse_binding(k) for k in order])
check("each is written the way a person reads it", A.key_text("ALT+1") == "Alt+1"
      and A.key_text("") == "" and A.key_text("F9") == "F9")
check("rigs up has a key, and the key does rigs up, not mark a deposit",
      A.EDSMT.wanted_hotkeys(A.DEFAULT_SETTINGS).get("allup") == "ALT+5"
      and '"allup": ("Rigs up", self.rigs_up)' in open(A.__file__,
                                                        encoding="utf-8").read())
old = {"hotkey_deposit": "F10", "hotkey_location": "F9", "hotkey_rigs": "",
       "hotkey_border": "", "rig_warn_m": 1000}
del A.SETTINGS_NOTICE[:]
merged = A.upgrade_hotkeys({**A.DEFAULT_SETTINGS, **old}, old)
check("a file from 1.10028 moves to the new keys",
      [merged[n] for n in WORK] == NEW, merged)
check("and the guessed 1 km rig warning becomes the measured one",
      merged["rig_warn_m"] == A.DEFAULT_SETTINGS["rig_warn_m"])
check("and says which layout it has", merged["hotkey_defaults"] == A.KEYS_LEVEL == 4)
check("and the commander is told once, at start-up",
      any("Alt+1" in note and "Alt+6" in note for note in A.SETTINGS_NOTICE),
      A.SETTINGS_NOTICE)
test_build = dict(old, hotkey_border="F8", hotkey_rigs="F7", hotkey_defaults=2)
merged = A.upgrade_hotkeys({**A.DEFAULT_SETTINGS, **test_build}, test_build)
check("a test build's F8 and F7 move too",
      (merged["hotkey_border"], merged["hotkey_rigs"]) == ("ALT+2", "ALT+4"),
      (merged["hotkey_border"], merged["hotkey_rigs"]))
alt_f = {"hotkey_location": "ALT+F1", "hotkey_border": "ALT+F2",
         "hotkey_deposit": "ALT+F3", "hotkey_rigs": "ALT+F5",
         "hotkey_allup": "ALT+F6", "hotkey_update": "ALT+F7",
         "hotkey_defaults": 3, "rig_warn_m": 3500}
merged = A.upgrade_hotkeys({**A.DEFAULT_SETTINGS, **alt_f}, alt_f)
check("a file on the Alt+F test layout moves to Alt+1 onwards",
      [merged[n] for n in WORK] == NEW, [merged[n] for n in WORK])
cleared = dict(alt_f, hotkey_update="", hotkey_allup="CTRL+U")
merged = A.upgrade_hotkeys({**A.DEFAULT_SETTINGS, **cleared}, cleared)
check("on the Alt+F layout, a key somebody cleared stays cleared",
      merged["hotkey_update"] == "", merged["hotkey_update"])
check("and one somebody moved stays moved",
      merged["hotkey_allup"] == "CTRL+U", merged["hotkey_allup"])
check("while the rest still move",
      merged["hotkey_location"] == "ALT+1" and merged["hotkey_rigs"] == "ALT+4")
own = dict(old, hotkey_location="CTRL+L")
merged = A.upgrade_hotkeys({**A.DEFAULT_SETTINGS, **own}, own)
check("a key set by hand is left where it was put",
      merged["hotkey_location"] == "CTRL+L", merged["hotkey_location"])
clash = dict(old, hotkey_lock="ALT+2")
merged = A.upgrade_hotkeys({**A.DEFAULT_SETTINGS, **clash}, clash)
check("a new key already taken by hand is not given twice",
      merged["hotkey_border"] == "" and merged["hotkey_lock"] == "ALT+2",
      (merged["hotkey_border"], merged["hotkey_lock"]))
mine = dict(old, rig_warn_m=3950)
merged = A.upgrade_hotkeys({**A.DEFAULT_SETTINGS, **mine}, mine)
check("a rig distance someone chose is left alone", merged["rig_warn_m"] == 3950)
done = dict(old, hotkey_defaults=A.KEYS_LEVEL, hotkey_rigs="", hotkey_border="")
merged = A.upgrade_hotkeys({**A.DEFAULT_SETTINGS, **done}, done)
check("once moved, a key cleared later stays cleared",
      merged["hotkey_rigs"] == "" and merged["hotkey_border"] == "")
src = open(A.__file__, encoding="utf-8").read()
check("the Settings rows are numbered in the order the work is done",
      src.index('"1  Log the signal and set the centre"')
      < src.index('"2  Survey border here"') < src.index('"3  Mark the deposit"')
      < src.index('"4  A rig is down here"'))
check("no message still tells anyone to press F9 or F10",
      not re.search(r'press F(9|10)\b|\(F9\)|F10 again', src))

print("== the rig warning sounds ==")
clean, rude = A.warning_sound(False), A.warning_sound(True)
check("the clean one is found", clean.endswith("rig-warning.wav"), clean)
check("and the profane one", rude.endswith("rig-warning-profane.wav"), rude)
for path in (clean, rude):
    raw = open(path, "rb").read()
    check("%s is plain PCM with nothing else in it" % os.path.basename(path),
          raw[:4] == b"RIFF" and raw[12:16] == b"fmt " and raw[36:40] == b"data"
          and b"Users" not in raw and b"Voicemeeter" not in raw)
spec = open(os.path.join(os.path.dirname(HERE), "build", "EDSMT.spec")).read()
check("both go into the build", "rig-warning.wav" in spec
      and "rig-warning-profane.wav" in spec)
check("and there is a switch for which", "rig_sound_profane" in A.DEFAULT_SETTINGS
      and A.DEFAULT_SETTINGS["rig_sound_profane"] is False)

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
