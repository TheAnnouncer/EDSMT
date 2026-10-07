"""Themes: at least ten, readable in every one, worn by the app and the
overlay alike - without a display.

Asked for: "work on way better theme colours, a minimum of ten, and this
should change the overlays - and we also need an app theme as well." Every
palette is held to contrast ratios worked out the WCAG way, so no theme can
ship with text you have to squint at.
"""
import os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "stubs"))
import _ctkstub  # noqa
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="edsmt-themes-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
import edsmt as A, overlay as OV  # noqa

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)


def luminance(colour):
    colour = colour.lstrip("#")
    parts = [int(colour[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    parts = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in parts]
    return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


# (foreground, background, minimum) - body text at AAA, everything else that
# is a word at AA, captions and red at the large-text line.
RULES = [("TEXT", "PANEL", 7.0), ("TEXT", "STEEL", 7.0), ("MUTED", "PANEL", 4.5),
         ("DIM", "PANEL", 3.0), ("ORANGE", "VOID", 4.5), ("ORANGE", "PANEL", 4.5),
         ("VOID", "ORANGE", 4.5), ("AMBER", "STEEL", 4.5), ("AMBER", "RAIL", 4.5),
         ("GREEN", "PANEL", 4.5), ("CYAN", "PANEL", 4.5), ("RED", "PANEL", 3.0),
         ("TEXT", "WARN", 4.5), ("TEXT", "DANGER", 4.5)]

print("== ten or more, all complete ==")
check("at least ten themes", len(OV.PALETTES) >= 10, len(OV.PALETTES))
check("every one has every colour the app uses",
      all(set(OV.PALETTE_KEYS) <= set(p) for p in OV.PALETTES.values()),
      [n for n, p in OV.PALETTES.items() if not set(OV.PALETTE_KEYS) <= set(p)])
check("every one has a name to pick it by",
      set(OV.THEME_NAMES) == set(OV.PALETTES) and len(set(OV.THEME_NAMES.values()))
      == len(OV.THEME_NAMES))
check("no two are the same",
      len({tuple(sorted(p.items())) for p in OV.PALETTES.values()}) == len(OV.PALETTES))
check("every value is a #rrggbb colour",
      all(OV.is_colour(v) for p in OV.PALETTES.values() for v in p.values()))
check("and none of them is the overlay's see-through colour",
      all(v.lower() != OV.CHROMA for p in OV.PALETTES.values() for v in p.values()))
check("the cockpit is still the Radio Raxxla cockpit",
      OV.PALETTES["cockpit"]["ORANGE"] == "#ff7a18"
      and OV.PALETTES["cockpit"]["VOID"] == "#0b0705")

print("== readable in every one ==")
for name, palette in OV.PALETTES.items():
    low = ["%s on %s %.2f < %s" % (fg, bg, contrast(palette[fg], palette[bg]), need)
           for fg, bg, need in RULES if contrast(palette[fg], palette[bg]) < need]
    check("%s: every pairing meets its contrast" % OV.THEME_NAMES[name], not low, low)

print("== the overlay wears them ==")
for name in OV.PALETTES:
    applied = OV.apply_theme(name)
    check("%s re-points the overlay" % name,
          OV.ORANGE == applied["ORANGE"] == OV.PALETTES[name]["ORANGE"]
          and OV.VOID == OV.PALETTES[name]["VOID"], (OV.ORANGE, applied["ORANGE"]))
OV.apply_theme("no such theme")
check("an unknown name falls back to the cockpit", OV.ORANGE == "#ff7a18", OV.ORANGE)
OV.apply_theme("cockpit")

print("== and so does the app ==")
worn = A.apply_app_theme("violet")
check("the app theme re-points the window's colours",
      worn == "violet" and A.ORANGE == OV.PALETTES["violet"]["ORANGE"]
      and A.PANEL == OV.PALETTES["violet"]["PANEL"], (worn, A.ORANGE))
check("and every button and box follows",
      A.BTN_PRIMARY["fg_color"] == A.ORANGE and A.BTN_SECONDARY["fg_color"] == A.STEEL
      and A.BOX["fg_color"] == A.VOID and A.LIST["fg_color"] == A.PANEL
      and A.BTN_DANGER["hover_color"] == A.RED, A.BTN_PRIMARY)
same = A.BTN_PRIMARY
A.apply_app_theme("fleet")
check("in place - anything holding a style holds the new one", same is A.BTN_PRIMARY
      and same["fg_color"] == OV.PALETTES["fleet"]["ORANGE"])
check("an unknown theme is worn as the cockpit",
      A.apply_app_theme("nonsense") == "cockpit" and A.ORANGE == "#ff7a18")
check("the app starts in the cockpit unless told otherwise",
      A.DEFAULT_SETTINGS["app_theme"] == "cockpit"
      and A.DEFAULT_SETTINGS["overlay_theme"] == "cockpit")

print("== Settings offers them ==")
src = open(A.__file__, encoding="utf-8").read()
check("a Basic settings section comes first",
      src.index('"Basic settings"') < src.index('"The community map"'))
check("and says everything can be changed",
      "can be changed" in src.split('"Basic settings"')[1][:400])
check("the app theme and the overlay theme are both there, with every theme",
      '"app_theme", "App theme", themes' in src
      and '"overlay_theme", "Overlay theme", themes' in src
      and "OV.THEME_ORDER" in src)
check("each setting is built once - two copies would save whichever came last",
      all(src.count('self._switch(body, "%s"' % key) == 1 for key in
          ("overlay_enabled", "overlay_show_guide", "rig_sound_profane"))
      and src.count('self._choice(body, "overlay_theme"') == 1)
check("a new app theme can be worn at once",
      "def save_and_restart" in src and "def restart_app" in src
      and "release_single_instance()" in src.split("def restart_app")[1][:1500])
_restart = src.split("    def restart_app(self):")[1].split("\n    def ")[0]
check("and the restart runs this program, nothing downloaded",
      "relaunch = [sys.executable]" in _restart
      and "subprocess.Popen(relaunch" in _restart and "path" not in _restart.split(
          "subprocess.Popen(relaunch")[1][:40])
check("the box count text no longer says four",
      "none of the four boxes" not in src)

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
