"""1.10039: themes reworked - twelve Powerplay themes, "Match my in-game HUD
colours", and a Theme tab in Settings (#287).

- gametheme.py reads the game's HUD colour matrix (GraphicsConfigurationOverride
  .xml) and EDHM's colours, and builds a readable palette out of either. Pure:
  no Tk, so every matrix and every broken file is driven here without a
  display.
- overlay.py carries a palette per Power and a "game" palette the app
  re-points at start.
- Settings has a Theme tab, second from the left, with both pickers, a swatch
  row each, the Match button and the Powerplay picker that sets app and overlay
  together.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110039_theme.py
"""
import io, json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-theme39-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP
os.environ["USERPROFILE"] = TMP

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def section(title):
    def wrap(fn):
        print("== " + title + " ==")
        try:
            fn()
        except Exception as exc:
            import traceback
            check(title + " (ran to the end)", False, "%s: %s" % (type(exc).__name__, exc))
            traceback.print_exc(limit=6)
        return fn
    return wrap


def write(path, text, mode="w"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as fh:
        fh.write(text)
    return path


# The same contrast rules tests/test_themes.py holds every shipped theme to.
def luminance(colour):
    colour = colour.lstrip("#")
    parts = [int(colour[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    parts = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in parts]
    return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


RULES = [("TEXT", "PANEL", 7.0), ("TEXT", "STEEL", 7.0), ("MUTED", "PANEL", 4.5),
         ("DIM", "PANEL", 3.0), ("ORANGE", "VOID", 4.5), ("ORANGE", "PANEL", 4.5),
         ("VOID", "ORANGE", 4.5), ("AMBER", "STEEL", 4.5), ("AMBER", "RAIL", 4.5),
         ("GREEN", "PANEL", 4.5), ("CYAN", "PANEL", 4.5), ("RED", "PANEL", 3.0),
         ("TEXT", "WARN", 4.5), ("TEXT", "DANGER", 4.5)]


def unreadable(palette):
    return ["%s on %s %.2f < %s" % (fg, bg, contrast(palette[fg], palette[bg]), need)
            for fg, bg, need in RULES if contrast(palette[fg], palette[bg]) < need]


import gametheme as GT      # noqa: E402
import overlay as OV        # noqa: E402

IDENTITY_XML = """<?xml version="1.0" encoding="UTF-8" ?>
<GraphicsConfig>
  <GUIColour>
    <Default>
      <LocalisationName>Standard</LocalisationName>
      <MatrixRed> 1, 0, 0 </MatrixRed>
      <MatrixGreen> 0, 1, 0 </MatrixGreen>
      <MatrixBlue> 0, 0, 1 </MatrixBlue>
    </Default>
  </GUIColour>
</GraphicsConfig>
"""
SWAP_XML = IDENTITY_XML.replace("<MatrixRed> 1, 0, 0 </MatrixRed>", "<MatrixRed>0, 0, 1</MatrixRed>") \
    .replace("<MatrixBlue> 0, 0, 1 </MatrixBlue>", "<MatrixBlue>\n 1, 0, 0\n</MatrixBlue>")
# The Frontier forums' worked example: "light blue, white and yellow panels".
FORUM_XML = IDENTITY_XML.replace("1, 0, 0 </MatrixRed>", "0, 0.25, 1</MatrixRed>") \
    .replace("0, 1, 0 </MatrixGreen>", "0, 0.5, 0</MatrixGreen>") \
    .replace("0, 0, 1 </MatrixBlue>", "0.25, 0, 0</MatrixBlue>")
SWAP = ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0))


@section("the matrix maths, on known matrices")
def _maths():
    check("the standard HUD orange is the Elite orange the app has always used",
          GT.HUD_ORANGE == "#ff7100" == OV.PALETTES["elite"]["ORANGE"])
    check("the identity leaves a colour alone",
          GT.recolour("#ff7100", GT.IDENTITY) == "#ff7100" and GT.is_identity(GT.IDENTITY))
    check("a red/blue swap turns the HUD orange into a blue",
          GT.recolour("#ff7100", SWAP) == "#0071ff", GT.recolour("#ff7100", SWAP))
    forum = ((0, 0.25, 1), (0, 0.5, 0), (0.25, 0, 0))
    got = GT.recolour("#ff7100", forum)
    check("the forum's example matrix gives the light blue it describes",
          got == "#0078ff", got)
    check("a channel never leaves 0..255, whatever the matrix",
          GT.recolour("#ff7100", ((2, 2, 2), (2, 2, 2), (2, 2, 2))) == "#ffffff"
          and GT.recolour("#ff7100", ((-1, 0, 0), (0, -1, 0), (0, 0, -1))) == "#000000")
    check("a matrix of lists, strings or ints is read as numbers",
          GT.recolour("#ff7100", [["0", "0", "1"], [0, 1, 0], ("1", 0, 0)]) == "#0071ff")
    check("and nonsense is not a matrix", not GT.is_identity(None) and not GT.is_identity("x")
          and GT.recolour("#ff7100", None) == "#ff7100")


@section("reading GraphicsConfigurationOverride.xml")
def _read():
    path = write(os.path.join(TMP, "a", "GraphicsConfigurationOverride.xml"), IDENTITY_XML)
    got = GT.read_matrix(path)
    check("the identity file is found and is the identity",
          got["found"] and got["identity"] and got["matrix"] == GT.IDENTITY and not got["problem"],
          got)
    got = GT.read_matrix(write(os.path.join(TMP, "b", "GraphicsConfigurationOverride.xml"), SWAP_XML))
    check("a swap is read, with newlines and spaces inside the numbers",
          got["found"] and not got["identity"] and got["matrix"] == SWAP, got)
    got = GT.read_matrix(os.path.join(TMP, "nowhere", "GraphicsConfigurationOverride.xml"))
    check("a missing file is not found, says so, and is no matrix",
          not got["found"] and got["matrix"] is None and "no " in got["problem"].lower()
          and got["identity"], got)
    got = GT.read_matrix(write(os.path.join(TMP, "c", "GraphicsConfigurationOverride.xml"),
                               "<GraphicsConfig><GUIColour><Default><MatrixRed>1,0,0"))
    check("a torn file is found but unreadable, and read as the standard colours",
          got["found"] and got["matrix"] is None and got["problem"] and got["identity"], got)
    got = GT.read_matrix(write(os.path.join(TMP, "d", "GraphicsConfigurationOverride.xml"),
                               "<GraphicsConfig><Display>1</Display></GraphicsConfig>"))
    check("an override with no colour block is the standard colours, with no problem",
          got["found"] and got["matrix"] is None and got["identity"] and not got["problem"], got)
    bad = IDENTITY_XML.replace("1, 0, 0 </MatrixRed>", "40, nan, -99</MatrixRed>")
    got = GT.read_matrix(write(os.path.join(TMP, "e", "GraphicsConfigurationOverride.xml"), bad))
    check("out-of-range values are clamped to +-%s and said so" % GT.MATRIX_LIMIT,
          got["found"] and got["matrix"] is not None
          and got["matrix"][0] == (GT.MATRIX_LIMIT, 0.0, -GT.MATRIX_LIMIT)
          and "range" in got["problem"].lower(), got)
    got = GT.read_matrix(write(os.path.join(TMP, "f", "GraphicsConfigurationOverride.xml"),
                               IDENTITY_XML.replace("0, 1, 0", "0, 1")))
    check("a row of two numbers is malformed, not guessed at",
          got["found"] and got["matrix"] is None and got["problem"], got)
    got = GT.read_matrix(write(os.path.join(TMP, "g", "GraphicsConfigurationOverride.xml"),
                               b"\x00\xff\xfe binary", "wb"))
    check("binary rubbish never raises", got["found"] and got["matrix"] is None and got["problem"])
    check("the override lives under the game's Options folder",
          GT.override_path(r"C:\Users\cmdr\AppData\Local").replace("/", "\\") ==
          r"C:\Users\cmdr\AppData\Local\Frontier Developments\Elite Dangerous\Options\Graphics\GraphicsConfigurationOverride.xml")


@section("a palette out of a matrix, readable whatever the matrix")
def _palette():
    check("the palette keys are the overlay's, to the letter",
          tuple(GT.PALETTE_KEYS) == tuple(OV.PALETTE_KEYS))
    standard = GT.standard_palette()
    check("the standard palette is the HUD orange on a dark ground",
          standard["ORANGE"] == "#ff7100" and luminance(standard["VOID"]) < 0.01
          and set(standard) == set(OV.PALETTE_KEYS), standard)
    check("and reads", not unreadable(standard), unreadable(standard))
    check("it is not the hand-made Elite theme, so the two can be told apart",
          standard != OV.PALETTES["elite"])
    swapped = GT.palette_from_matrix(SWAP)
    check("a swapped matrix gives a blue accent", swapped["ORANGE"] == "#0071ff"
          or (int(swapped["ORANGE"][5:7], 16) > 200 and int(swapped["ORANGE"][1:3], 16) < 60),
          swapped["ORANGE"])
    check("and the whole of it reads", not unreadable(swapped), unreadable(swapped))
    for name, matrix in (("the forum example", ((0, 0.25, 1), (0, 0.5, 0), (0.25, 0, 0))),
                         ("a dim matrix", ((0.2, 0.1, 0.1), (0.1, 0.2, 0.1), (0.1, 0.1, 0.2))),
                         ("a blown-out matrix", ((3, 3, 3), (3, 3, 3), (3, 3, 3))),
                         ("a negative matrix", ((-1, 0, 0), (0, -1, 0), (0, 0, -1))),
                         ("the identity", GT.IDENTITY)):
        palette = GT.palette_from_matrix(matrix)
        check("%s: every colour is a #rrggbb and every pairing reads" % name,
              all(OV.is_colour(v) for v in palette.values()) and not unreadable(palette)
              and all(v.lower() != OV.CHROMA for v in palette.values()),
              unreadable(palette))
    check("the warning colours are not passed through the matrix - red stays red",
          swapped["RED"] == standard["RED"] and swapped["GREEN"] == standard["GREEN"])
    check("an unreadable palette is pushed until it reads, in place of nothing",
          not unreadable(GT.make_readable(dict(standard, TEXT="#101010", ORANGE="#050505"))))


@section("the twelve Powerplay themes")
def _powerplay():
    powers = ["Aisling Duval", "Arissa Lavigny-Duval", "Archon Delaine", "Denton Patreus",
              "Edmund Mahon", "Felicia Winters", "Jerome Archer", "Li Yong-Rui",
              "Nakato Kaine", "Pranav Antal", "Yuri Grom", "Zemina Torval"]
    keys = [k for k in OV.THEME_ORDER if k.startswith("pp_")]
    check("twelve of them, one per Power, named after the Power",
          len(keys) == 12 and [OV.THEME_NAMES[k] for k in keys] ==
          ["Powerplay - " + p for p in powers], [OV.THEME_NAMES[k] for k in keys])
    check("each is a whole palette, readable, and in POWERPLAY by name",
          all(set(OV.PALETTES[k]) == set(OV.PALETTE_KEYS) and not unreadable(OV.PALETTES[k])
              for k in keys)
          and [p for _k, p, _a in OV.POWERPLAY] == powers,
          [(k, unreadable(OV.PALETTES[k])) for k in keys if unreadable(OV.PALETTES[k])])
    check("twelve different accents", len({OV.PALETTES[k]["ORANGE"] for k in keys}) == 12)
    check("the old themes are all still there, first, with their keys",
          OV.THEME_ORDER[:14] == ("cockpit", "elite", "signal", "ice", "phosphor", "amber",
                                  "crimson", "violet", "gold", "fleet", "xeno", "nebula",
                                  "contrast", "colourblind"), OV.THEME_ORDER[:14])
    check("then the game match, then the Powers",
          OV.THEME_ORDER[14] == "game" and OV.THEME_ORDER[15:] == tuple(keys), OV.THEME_ORDER)
    check("the game theme is named for what it does",
          "in-game" in OV.THEME_NAMES["game"].lower(), OV.THEME_NAMES["game"])
    check("a Power's OK colour is kept apart from its accent (Mahon is green)",
          contrast(OV.PALETTES["pp_mahon"]["GREEN"], OV.PALETTES["pp_mahon"]["ORANGE"]) > 1.0
          and OV.PALETTES["pp_mahon"]["GREEN"] != OV.PALETTES["pp_mahon"]["ORANGE"]
          and GT.hue_apart(OV.PALETTES["pp_mahon"]["GREEN"], OV.PALETTES["pp_mahon"]["ORANGE"]) > 20)
    check("and Delaine's warning red is not his red",
          GT.hue_apart(OV.PALETTES["pp_delaine"]["RED"], OV.PALETTES["pp_delaine"]["ORANGE"]) > 20)


@section("the game palette is re-pointed in place")
def _game():
    before = OV.PALETTES["game"]
    held = OV.THEMES["game"]
    worn = OV.set_game_palette(GT.palette_from_matrix(SWAP))
    check("set_game_palette changes PALETTES['game'] in place and the overlay's copy",
          OV.PALETTES["game"] is before and before["ORANGE"] == "#0071ff"
          and OV.THEMES["game"] is held and held["ORANGE"] == "#0071ff" and worn is before)
    OV.apply_theme("game")
    check("the overlay wears it", OV.ORANGE == "#0071ff", OV.ORANGE)
    kept = OV.set_game_palette({"ORANGE": "#123456"})
    check("a half palette is refused and the last one kept",
          kept["ORANGE"] == "#0071ff" and OV.PALETTES["game"]["ORANGE"] == "#0071ff")
    kept = OV.set_game_palette(dict(before, TEXT="not a colour"))
    check("and so is one with a value that is not a colour", kept["TEXT"] == before["TEXT"])
    OV.set_game_palette(GT.standard_palette())
    OV.apply_theme("cockpit")


@section("EDHM's colours, from its own files")
def _edhm():
    check("EDHM's ini floats come back to the sRGB they were made from (EDHM_UI's own example)",
          GT.linear_to_hex(["0.082", "0.716", "1.0"]) == "#51dcff", GT.linear_to_hex(["0.082", "0.716", "1.0"]))
    check("a component outside 0..1 is read as 1, as EDHM_UI does",
          GT.linear_to_hex([1.5, -0.2, 0.0]) == "#ffff00")
    check("EDHM_UI's signed ARGB int is RGB", GT.argb_to_hex(-1579033) == "#e7e7e7"
          and GT.argb_to_hex(-16776961) == "#0000ff" and GT.argb_to_hex("x") is None)
    game = os.path.join(TMP, "steam", "Elite Dangerous", "Products", "elite-dangerous-odyssey-64")
    ini = os.path.join(game, "EDHM-ini")
    write(os.path.join(ini, "Startup-Profile.ini"),
          "; EDHM\n[Constants]\nw75 = 100 ; main text mode\nx137 = 100\n")
    write(os.path.join(ini, "Advanced.ini"),
          "[Constants]\nx77 = 0.082\ny77 = 0.716\nz77 = 1.0\nw77 = 1\n")
    write(os.path.join(ini, "XML-Profile.ini"),
          "[Constants]\nx150 = 0\ny150 = 0\nz150 = 1\nx151 = 0\ny151 = 1\nz151 = 0\n"
          "x152 = 1\ny152 = 0\nz152 = 0\n")
    got = GT.read_edhm(ini)
    check("the ini files give the main text colour, its mode and EDHM's own matrix",
          got["found"] and got["mode"] == 100 and got["accent"] == "#51dcff"
          and got["matrix"] == SWAP and got["file"].endswith("Advanced.ini"), got)
    theme = {"ui_groups": [{"Name": "Settings", "Elements": [
        {"Title": "Main Text Mode", "File": "Startup-Profile", "Section": "Constants",
         "Key": "w75", "Value": 100},
        {"Title": "Main Text", "File": "Advanced", "Section": "Constants",
         "Key": "x77|y77|z77|w77", "Value": -16776961}]}],
        "xml_profile": [{"key": "x150", "value": 1}, {"key": "y150", "value": 0},
                        {"key": "z150", "value": 0}, {"key": "x151", "value": 0},
                        {"key": "y151", "value": 1}, {"key": "z151", "value": 0},
                        {"key": "x152", "value": 0}, {"key": "y152", "value": 0},
                        {"key": "z152", "value": 1}]}
    write(os.path.join(ini, "ThemeSettings.json"), json.dumps(theme))
    got = GT.read_edhm(ini)
    check("ThemeSettings.json, when it is there, is what EDHM_UI applied last and wins",
          got["found"] and got["accent"] == "#0000ff" and got["mode"] == 100
          and got["matrix"] == GT.IDENTITY and got["file"].endswith("ThemeSettings.json"), got)
    check("the game folders are searched for EDHM-ini, Products or the exe folder",
          GT.edhm_folders([os.path.join(TMP, "steam", "Elite Dangerous", "Products"),
                           game, os.path.join(TMP, "nowhere")]) == [ini])
    pointer = write(os.path.join(TMP, "pointer", "Settings.json"), json.dumps({
        "ActiveInstance": "Steam (Odyssey (Live))",
        "GameInstances": [{"instance": "Steam", "games": [
            {"instance": "Steam (Horizons (Legacy))", "key": "ED_Horizons", "path": os.path.join(TMP, "gone")},
            {"instance": "Steam (Odyssey (Live))", "key": "ED_Odissey", "path": game}]}]}))
    check("EDHM_UI's own Settings.json points straight at the game",
          GT.edhm_folders([], settings_json=pointer) == [ini])
    check("and a broken Settings.json is just no pointer",
          GT.edhm_folders([], settings_json=write(os.path.join(TMP, "x.json"), "{nope")) == [])
    got = GT.read_edhm(os.path.join(TMP, "no-such-folder"))
    check("no EDHM is not found and never raises", not got["found"] and got["accent"] is None)


@section("what the whole read says it found")
def _found():
    local = os.path.join(TMP, "local-a")
    got = GT.read_game_theme(localappdata=local, game_roots=[], settings_json="")
    check("nothing anywhere: the standard colours, and it says why",
          got["source"] == "standard" and got["palette"] == GT.standard_palette()
          and "standard colours" in got["words"] and "no override" in got["words"].lower(), got["words"])
    write(GT.override_path(local), IDENTITY_XML)
    got = GT.read_game_theme(localappdata=local, game_roots=[], settings_json="")
    check("an identity override: still the standard colours, naming the file",
          got["source"] == "standard" and "GraphicsConfigurationOverride.xml" in got["words"]
          and got["file"].endswith("GraphicsConfigurationOverride.xml"), got["words"])
    write(GT.override_path(local), SWAP_XML)
    got = GT.read_game_theme(localappdata=local, game_roots=[], settings_json="")
    check("a real matrix: the palette comes from it and the words say so",
          got["source"] == "matrix" and got["palette"]["ORANGE"] == "#0071ff"
          and "matrix" in got["words"].lower() and "#0071ff" in got["words"], got["words"])
    write(GT.override_path(local), "<GraphicsConfig><GUIColour><Default><MatrixRed>1,0")
    got = GT.read_game_theme(localappdata=local, game_roots=[], settings_json="")
    check("a broken override: the standard colours, and the words say it could not be read",
          got["source"] == "standard" and "could not be read" in got["words"].lower()
          and not unreadable(got["palette"]), got["words"])
    game = os.path.join(TMP, "steam", "Elite Dangerous", "Products", "elite-dangerous-odyssey-64")
    ini = os.path.join(game, "EDHM-ini")
    write(GT.override_path(local), SWAP_XML)
    got = GT.read_game_theme(localappdata=local, game_roots=[game], settings_json="")
    check("EDHM with a custom main text colour beats the matrix",
          got["source"] == "edhm" and got["palette"]["ORANGE"] == "#0000ff"
          or (got["source"] == "edhm" and got["palette"]["ORANGE"] != "#0071ff"
              and int(got["palette"]["ORANGE"][5:7], 16) == 255), (got["source"], got["palette"]["ORANGE"]))
    check("and names EDHM and the file", "EDHM" in got["words"] and "ThemeSettings.json" in got["words"],
          got["words"])
    theme = json.load(open(os.path.join(ini, "ThemeSettings.json"), encoding="utf-8"))
    theme["ui_groups"][0]["Elements"][0]["Value"] = 200
    write(os.path.join(ini, "ThemeSettings.json"), json.dumps(theme))
    got = GT.read_game_theme(localappdata=local, game_roots=[game], settings_json="")
    check("EDHM on 'Elite Default' text hands over to the game's matrix",
          got["source"] == "matrix" and got["palette"]["ORANGE"] == "#0071ff"
          and "EDHM" in got["words"], got["words"])
    theme["ui_groups"][0]["Elements"][0]["Value"] = 199
    theme["xml_profile"] = [{"key": k, "value": v} for k, v in
                            (("x150", 0), ("y150", 1), ("z150", 0), ("x151", 1), ("y151", 0),
                             ("z151", 0), ("x152", 0), ("y152", 0), ("z152", 1))]
    write(os.path.join(ini, "ThemeSettings.json"), json.dumps(theme))
    got = GT.read_game_theme(localappdata=local, game_roots=[game], settings_json="")
    check("EDHM on 'XML (User Defined)' uses EDHM's own copy of the matrix",
          got["source"] == "edhm" and got["palette"]["ORANGE"] == GT.recolour("#ff7100", ((0, 1, 0), (1, 0, 0), (0, 0, 1)))
          and "matrix" in got["words"].lower(), (got["source"], got["palette"]["ORANGE"], got["words"]))
    write(os.path.join(ini, "ThemeSettings.json"), b"\x00\x01garbage", "wb")
    got = GT.read_game_theme(localappdata=local, game_roots=[game], settings_json="")
    check("a broken ThemeSettings.json falls back to the ini files",
          got["source"] == "edhm" and got["palette"]["ORANGE"] == "#51dcff", (got["source"], got["words"]))
    check("every result carries the keys the app reads",
          all(k in got for k in ("source", "file", "matrix", "accent", "palette", "words")))


@section("the app re-reads the game's colours at start and offers them as a theme")
def _app():
    import edsmt as A
    src = io.open(A.__file__, encoding="utf-8").read()
    start = src.split("    def __init__(self):\n        # The theme first")[1][:900]
    check("the game theme is read before the window is dressed",
          "refresh_game_theme(" in start and start.index("refresh_game_theme(") <
          start.index("apply_app_theme("), start[:300])
    local = os.path.join(TMP, "local-b")
    write(GT.override_path(local), SWAP_XML)
    found = A.refresh_game_theme(localappdata=local, game_roots=[], settings_json="")
    check("refresh_game_theme re-points the game palette and hands back what it found",
          found["source"] == "matrix" and OV.PALETTES["game"]["ORANGE"] == "#0071ff")
    worn = A.apply_app_theme("game")
    check("the app can wear it", worn == "game" and A.ORANGE == "#0071ff", (worn, A.ORANGE))
    A.apply_app_theme("cockpit")
    write(GT.override_path(local), b"\xff\xfe", "wb")
    found = A.refresh_game_theme(localappdata=local, game_roots=[], settings_json="")
    check("a broken file never stops the app starting",
          found["source"] == "standard" and OV.PALETTES["game"] == GT.standard_palette())
    check("the Theme tab is second", A.SETTINGS_TABS[1] == "Theme", A.SETTINGS_TABS)
    built = src.split("class SettingsWindow(")[1].split("\n    def show_binds")[0]
    basics = built.split('body = self.pages["Basics"]')[1].split('body = self.pages["')[0]
    check("the theme controls have left Basics",
          '"app_theme"' not in basics and '"overlay_theme"' not in basics and
          "save_and_restart" not in basics)
    check("every new section is put in a tab the 1.10034 way",
          built.count("self._section(body,") == built.count('body = self.pages["'))


try:
    import tkinter
    tkinter.Tk().destroy()
    HAVE_DISPLAY = True
except Exception as _exc:
    HAVE_DISPLAY = False
    print("  SKIP  the Settings window needs a display (%s). Run it under xvfb-run." % _exc)

if HAVE_DISPLAY:
    OV.foreground_is_game = lambda: None
    import edsmt as A
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
        json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS,
                   "app_theme": "gold", "overlay_theme": "gold"}, _f)
    app = A.EDSMT()
    app.geometry("1600x1000+0+0")
    app.updates.check = lambda *args, **kwargs: None

    def pump(times=3):
        for _ in range(times):
            try:
                app.update_idletasks()
                app.update()
            except Exception:
                pass

    def walk(widget):
        out = []
        for child in widget.winfo_children():
            out.append(child)
            out.extend(walk(child))
        return out

    def texts(widget):
        found = []
        for w in walk(widget):
            try:
                text = str(w.cget("text"))
            except Exception:
                continue
            if text:
                found.append(text)
        return found

    def box_of(win, key):
        return win.choices[key][0]

    @section("Settings: the Theme tab, second, with both pickers, swatches and the big button")
    def _tab():
        win = A.SettingsWindow(app)
        pump(4)
        try:
            check("tabs: Basics, Theme, then the rest",
                  list(win.pages)[:2] == ["Basics", "Theme"], list(win.pages))
            page = win.pages["Theme"]
            words = texts(page)
            check("both pickers are on it", "app_theme" in win.choices and "overlay_theme" in win.choices
                  and any(t == "App theme" for t in words) and any(t == "Overlay theme" for t in words))
            check("the Powerplay heading, and the Match button in big letters",
                  any("POWERPLAY" in t.upper() for t in words)
                  and any(t == "Match my in-game HUD colours" for t in words), words)
            button = next(w for w in walk(page) if isinstance(w, A.ctk.CTkButton)
                          and str(w.cget("text")) == "Match my in-game HUD colours")
            check("it is a primary button, taller than the rest",
                  int(button.cget("height")) >= 40 and button.cget("fg_color") == A.BTN_PRIMARY["fg_color"],
                  (button.cget("height"), button.cget("fg_color")))
            check("every theme is offered in both, the game match and the Powers among them",
                  box_of(win, "app_theme").cget("values") == [OV.THEME_NAMES[k] for k in OV.THEME_ORDER]
                  == box_of(win, "overlay_theme").cget("values"))
            check("a swatch row sits under each picker, painted with the chosen theme",
                  len(win.swatches) == 2
                  and win.swatches["app_theme"]["ORANGE"].cget("fg_color") == OV.PALETTES["gold"]["ORANGE"]
                  and win.swatches["overlay_theme"]["TEXT"].cget("fg_color") == OV.PALETTES["gold"]["TEXT"],
                  {k: v["ORANGE"].cget("fg_color") for k, v in win.swatches.items()})
            box_of(win, "app_theme").set(OV.THEME_NAMES["ice"])
            win.theme_picked("app_theme")
            pump(2)
            check("picking a theme repaints its swatches",
                  win.swatches["app_theme"]["ORANGE"].cget("fg_color") == OV.PALETTES["ice"]["ORANGE"]
                  and win.swatches["overlay_theme"]["ORANGE"].cget("fg_color") == OV.PALETTES["gold"]["ORANGE"])
            box_of(win, "app_theme").suggest.pick(OV.THEME_NAMES["fleet"])
            pump(2)
            check("and so does a pick from the type-ahead list under it",
                  box_of(win, "app_theme").get() == OV.THEME_NAMES["fleet"]
                  and win.swatches["app_theme"]["ORANGE"].cget("fg_color") == OV.PALETTES["fleet"]["ORANGE"],
                  (box_of(win, "app_theme").get(), win.swatches["app_theme"]["ORANGE"].cget("fg_color")))
            check("the game line says what was found at start",
                  "standard colours" in str(win.game_line.cget("text")), win.game_line.cget("text"))
            check("the restart button moved with the app theme",
                  any(t == "Save and restart now" for t in words))
        finally:
            win.destroy()
            pump()

    @section("Settings: a Power sets both, and Match reads the game")
    def _pick():
        win = A.SettingsWindow(app)
        pump(4)
        try:
            win.power_box.set("Edmund Mahon")
            win.power_picked("Edmund Mahon")
            pump(2)
            check("picking a Power puts its theme in both pickers",
                  box_of(win, "app_theme").get() == "Powerplay - Edmund Mahon"
                  == box_of(win, "overlay_theme").get(),
                  (box_of(win, "app_theme").get(), box_of(win, "overlay_theme").get()))
            check("and paints both swatch rows with it",
                  win.swatches["app_theme"]["ORANGE"].cget("fg_color") == OV.PALETTES["pp_mahon"]["ORANGE"]
                  == win.swatches["overlay_theme"]["ORANGE"].cget("fg_color"))
            local = os.path.join(TMP, "local-c")
            write(GT.override_path(local), SWAP_XML)
            win.match_game_theme(localappdata=local, game_roots=[], settings_json="")
            pump(2)
            check("Match reads the stand-in file and picks the game theme for both",
                  box_of(win, "app_theme").get() == OV.THEME_NAMES["game"]
                  == box_of(win, "overlay_theme").get()
                  and win.swatches["app_theme"]["ORANGE"].cget("fg_color") == "#0071ff")
            check("and says what it found", "#0071ff" in str(win.game_line.cget("text"))
                  and "matrix" in str(win.game_line.cget("text")).lower(), win.game_line.cget("text"))
            win.save()
            pump(2)
            check("Save keeps both as the game theme and asks for the restart the app theme needs",
                  app.settings["app_theme"] == "game" == app.settings["overlay_theme"]
                  and "restart" in str(win.status.cget("text")).lower(), win.status.cget("text"))
            check("the overlay would wear it on its next redraw",
                  OV.apply_theme(app.settings["overlay_theme"])["ORANGE"] == "#0071ff")
            write(GT.override_path(local), IDENTITY_XML)
            win.match_game_theme(localappdata=local, game_roots=[], settings_json="")
            pump(2)
            check("on the standard colours it says so, and the theme still applies",
                  "standard colours" in str(win.game_line.cget("text"))
                  and box_of(win, "app_theme").get() == OV.THEME_NAMES["game"], win.game_line.cget("text"))
        finally:
            app.settings["app_theme"] = "gold"
            app.settings["overlay_theme"] = "gold"
            A.apply_app_theme("gold")
            OV.apply_theme("gold")
            win.destroy()
            pump()

    try:
        app.destroy()
    except Exception:
        pass

if __name__ == "__main__":
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    sys.exit(1 if fails else 0)
