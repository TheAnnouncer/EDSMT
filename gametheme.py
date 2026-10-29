"""The game's own HUD colours, read from disk and turned into a theme
(1.10039, #287: "if a user uses custom in-game colours I want an option to
match in-game theme").

Two places a commander's HUD colour can live, and this reads both:

  The HUD colour matrix   %LOCALAPPDATA%\\Frontier Developments\\Elite Dangerous\\
                          Options\\Graphics\\GraphicsConfigurationOverride.xml,
                          GraphicsConfig > GUIColour > Default > MatrixRed,
                          MatrixGreen, MatrixBlue: three numbers each. The
                          game multiplies every HUD colour through it. The
                          identity (1,0,0 / 0,1,0 / 0,0,1) is the standard
                          orange; a missing file means the same.
  EDHM                    the HUD mod. Its settings sit in <game folder>\\
                          EDHM-ini\\ as shader constants: Startup-Profile.ini
                          w75 says whether the main text is a custom colour
                          (100), the matrix above (199) or the game's own
                          (200); Advanced.ini x77 y77 z77 hold the custom
                          colour as linear floats; XML-Profile.ini x150..z152
                          hold EDHM's copy of the matrix. The mod's front end
                          also writes ThemeSettings.json beside them with the
                          same values as signed ARGB ints, which is read
                          first when it is there.

Everything here is plain functions on paths and dicts: no Tk, nothing of the
window, so every matrix and every broken file is driven in the checks
without a display. The palette that comes out carries the same keys as
overlay.PALETTES and is pushed to the same contrast rules every shipped
theme is held to, so "match my game" can never hand back text that cannot
be read. The reading is one-way: nothing here writes in the game's folders.
"""
import colorsys
import configparser
import io
import json
import math
import os
import xml.etree.ElementTree as ET

# The same keys as overlay.PALETTE_KEYS, repeated rather than imported: the
# overlay imports this module for its Powerplay palettes, and a module that
# imported it back would be a circle. tests/test_110039_theme.py holds the
# two to the letter.
PALETTE_KEYS = ("VOID", "PANEL", "RAIL", "STEEL", "RULE", "ORANGE", "AMBER",
                "TEXT", "MUTED", "DIM", "FAINT", "GRID", "GREEN", "SWEPT",
                "RED", "CYAN", "WARN", "DANGER")
# The game's standard HUD orange. Frontier has not published it; this is the
# value the app's Elite orange theme has always used for it.
HUD_ORANGE = "#ff7100"
IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
# A matrix value past this is a typo, not a colour scheme: the schemes people
# share run to about 2.
MATRIX_LIMIT = 4.0
OVERRIDE_FILE = "GraphicsConfigurationOverride.xml"
OVERRIDE_SUBPATH = os.path.join("Frontier Developments", "Elite Dangerous",
                                "Options", "Graphics")
# The folders the game executable lives in, as the mod's front end lists
# them (live first, then legacy).
GAME_FOLDERS = ("elite-dangerous-odyssey-64", "FORC-FDEV-DO-1000",
                "FORC-FDEV-DO-38-IN-40", "elite-dangerous-64",
                "FORC-FDEV-D-1013", "FORC-FDEV-D-1010", "FORC-FDEV-D-1012")
EDHM_INI = "EDHM-ini"
EDHM_THEME = "ThemeSettings.json"
EDHM_MODE_KEY = "w75"                       # Startup-Profile.ini: main text mode
EDHM_TEXT_KEYS = ("x77", "y77", "z77")      # Advanced.ini: main text colour
EDHM_MATRIX_KEYS = (("x150", "y150", "z150"), ("x151", "y151", "z151"),
                    ("x152", "y152", "z152"))
EDHM_CUSTOM, EDHM_XML, EDHM_DEFAULT = 100, 199, 200
# The settings file of the mod's front end, which knows where the game is.
EDHM_SETTINGS_SUBPATH = os.path.join("EDHM_UI", "Settings.json")

# What every theme is held to, (foreground, background, minimum contrast) -
# the list in tests/test_themes.py. Body text at AAA, every other word at
# AA, captions and red at the large-text line.
RULES = (("TEXT", "PANEL", 7.0), ("TEXT", "STEEL", 7.0), ("MUTED", "PANEL", 4.5),
         ("DIM", "PANEL", 3.0), ("ORANGE", "VOID", 4.5), ("ORANGE", "PANEL", 4.5),
         ("VOID", "ORANGE", 4.5), ("AMBER", "STEEL", 4.5), ("AMBER", "RAIL", 4.5),
         ("GREEN", "PANEL", 4.5), ("CYAN", "PANEL", 4.5), ("RED", "PANEL", 3.0),
         ("TEXT", "WARN", 4.5), ("TEXT", "DANGER", 4.5))
_GROUNDS = ("VOID", "PANEL", "RAIL", "STEEL", "WARN", "DANGER")
# The overlay's see-through colour: nothing may come out exactly this.
_CHROMA = "#010203"
# The OK, warning and telemetry colours a palette can wear, best first: the
# first one far enough in hue from the accent is used, so a green Power keeps
# a visible OK colour and a red one keeps a visible warning, while every
# other theme gets the plain green, red and cyan. Red is allowed closer to
# the accent than the others: red and orange are neighbours, and an orange
# HUD has always had a red warning beside it.
_GREENS = ("#35d07f", "#56f0c8", "#c8ff5c")
_REDS = ("#ff6b5b", "#ff9f43", "#ff5f7a")
_CYANS = ("#37c6d4", "#8fd4ff", "#ffd89a")
APART = {"GREEN": 30.0, "RED": 20.0, "CYAN": 25.0}


# ---------------------------------------------------------------------------
# Colours as numbers
# ---------------------------------------------------------------------------

def is_colour(text):
    """#rrggbb, and nothing else."""
    text = str(text or "").strip()
    return (len(text) == 7 and text.startswith("#")
            and all(c in "0123456789abcdefABCDEF" for c in text[1:]))


def _rgb(colour):
    colour = colour.lstrip("#")
    return tuple(int(colour[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _hex(parts):
    out = []
    for part in parts:
        part = 0.0 if part != part else max(0.0, min(1.0, float(part)))
        out.append(int(round(part * 255)))
    text = "#%02x%02x%02x" % tuple(out)
    # One step off the overlay's chroma key, which would make a see-through
    # hole wherever the colour was drawn.
    return "#020203" if text == _CHROMA else text


def _mix(a, b, share):
    """a, `share` of the way to b."""
    x, y = _rgb(a), _rgb(b)
    return _hex(x[i] + (y[i] - x[i]) * share for i in range(3))


def _luminance(colour):
    parts = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
             for c in _rgb(colour)]
    return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]


def contrast(a, b):
    """The WCAG contrast ratio between two #rrggbb colours."""
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def hue_apart(a, b):
    """How many degrees of hue separate two colours, 0 to 180."""
    ha = colorsys.rgb_to_hsv(*_rgb(a))[0] * 360.0
    hb = colorsys.rgb_to_hsv(*_rgb(b))[0] * 360.0
    gap = abs(ha - hb) % 360.0
    return min(gap, 360.0 - gap)


def linear_to_hex(components):
    """EDHM's linear floats (r, g, b[, a]) back to the sRGB #rrggbb they were
    made from: the sRGB transfer curve, exponent 2.4, as the mod's front end
    reverses it. A component outside 0..1 is read as 1, as it does."""
    out = []
    for part in list(components)[:3]:
        try:
            value = float(part)
        except (TypeError, ValueError):
            value = 1.0
        if not 0.0 <= value <= 1.0:
            value = 1.0
        out.append(value * 12.92 if value <= 0.0031308
                   else value ** (1.0 / 2.4) * 1.055 - 0.055)
    if len(out) != 3:
        return None
    return _hex(out)


def argb_to_hex(value):
    """EDHM's front end keeps a colour as one signed 32-bit int, ARGB."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    number &= 0xFFFFFFFF
    return "#%02x%02x%02x" % ((number >> 16) & 0xFF, (number >> 8) & 0xFF, number & 0xFF)


# ---------------------------------------------------------------------------
# The matrix
# ---------------------------------------------------------------------------

def _matrix(value):
    """Three rows of three numbers, or None."""
    try:
        rows = [tuple(float(x) for x in row) for row in value]
    except (TypeError, ValueError):
        return None
    if len(rows) != 3 or any(len(row) != 3 for row in rows):
        return None
    if any(not math.isfinite(x) for row in rows for x in row):
        return None
    return tuple(rows)


def is_identity(matrix):
    matrix = _matrix(matrix)
    return matrix is not None and all(
        abs(matrix[r][c] - (1.0 if r == c else 0.0)) < 1e-6
        for r in range(3) for c in range(3))


def recolour(colour, matrix):
    """One #rrggbb through the game's matrix.

    Each row says where that source channel goes: MatrixRed is the (r, g, b)
    the red channel becomes. So the result is R x MatrixRed + G x MatrixGreen
    + B x MatrixBlue, each channel clamped to 0..1. That reading is the one
    that turns the forum's worked example (MatrixRed 0, 0.25, 1) into the
    light blue it describes; the other reading gives a dark grey.
    """
    matrix = _matrix(matrix)
    if matrix is None or not is_colour(colour):
        return colour
    r, g, b = _rgb(colour)
    return _hex(r * matrix[0][c] + g * matrix[1][c] + b * matrix[2][c]
                for c in range(3))


def _parse_row(text):
    parts = [p.strip() for p in str(text or "").replace("\n", " ").split(",")]
    values = [float(p) for p in parts if p != ""]
    if len(values) != 3:
        raise ValueError("%d numbers, not three" % len(values))
    return values


def parse_matrix(text):
    """The Default GUIColour matrix out of the override XML's text.

    {"matrix": 3x3 or None, "identity": bool, "problem": ""}. No GUIColour
    block is the standard colours and no problem; a torn file or a row that
    is not three numbers is a problem and the standard colours; a value past
    MATRIX_LIMIT is clamped and said so.
    """
    out = {"matrix": None, "identity": True, "problem": ""}
    try:
        root = ET.fromstring(text)
    except (ET.ParseError, ValueError, TypeError) as exc:
        out["problem"] = "the file is not well-formed XML (%s)" % exc
        return out
    default = root.find("./GUIColour/Default")
    if default is None:
        return out
    rows, clamped = [], False
    for name in ("MatrixRed", "MatrixGreen", "MatrixBlue"):
        node = default.find(name)
        if node is None:
            out["problem"] = "%s is missing" % name
            return out
        try:
            row = _parse_row(node.text)
        except ValueError as exc:
            out["problem"] = "%s is not three numbers (%s)" % (name, exc)
            return out
        fixed = []
        for value in row:
            if not math.isfinite(value):
                value = 0.0
                clamped = True
            if abs(value) > MATRIX_LIMIT:
                value = math.copysign(MATRIX_LIMIT, value)
                clamped = True
            fixed.append(value)
        rows.append(tuple(fixed))
    out["matrix"] = tuple(rows)
    out["identity"] = is_identity(out["matrix"])
    if clamped:
        out["problem"] = ("a value was out of range and was held to +-%g"
                          % MATRIX_LIMIT)
    return out


def read_matrix(path):
    """parse_matrix on a file. "found" says whether there was a file at all."""
    out = {"found": False, "file": path, "matrix": None, "identity": True,
           "problem": ""}
    try:
        with io.open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        out["problem"] = "no override file"
        return out
    out["found"] = True
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    out.update(parse_matrix(text))
    return out


def override_path(localappdata=None):
    base = localappdata or os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, OVERRIDE_SUBPATH, OVERRIDE_FILE)


# ---------------------------------------------------------------------------
# A palette out of a colour, or a matrix
# ---------------------------------------------------------------------------

def _apart(candidates, accent, role):
    for candidate in candidates:
        if hue_apart(candidate, accent) >= APART[role]:
            return candidate
    return max(candidates, key=lambda c: hue_apart(c, accent))


def palette_from_accent(accent, **fixed):
    """A whole palette in the shades of one colour: the accent, a lighter
    highlight, near-white text with a hint of it, three ranks of dimmer
    text, a ground in five depths, and OK/warning colours kept apart from
    it in hue. Anything in `fixed` overrides the derived value. Pushed to
    the contrast rules before it is handed back."""
    accent = accent if is_colour(accent) else HUD_ORANGE
    black, white = "#000000", "#ffffff"
    green = fixed.pop("GREEN", None) or _apart(_GREENS, accent, "GREEN")
    red = fixed.pop("RED", None) or _apart(_REDS, accent, "RED")
    cyan = fixed.pop("CYAN", None) or _apart(_CYANS, accent, "CYAN")
    palette = {
        "ORANGE": accent,
        "AMBER": _mix(accent, white, 0.35),
        "TEXT": _mix(accent, white, 0.84),
        "MUTED": _mix(accent, "#c2c2c2", 0.66),
        "DIM": _mix(accent, "#777777", 0.40),
        "FAINT": _mix(accent, black, 0.52),
        "RULE": _mix(accent, black, 0.74),
        "GRID": _mix(accent, black, 0.88),
        "STEEL": _mix(accent, black, 0.855),
        "RAIL": _mix(accent, black, 0.895),
        "PANEL": _mix(accent, black, 0.915),
        "VOID": _mix(accent, black, 0.955),
        "WARN": _mix(accent, black, 0.62),
        "DANGER": _mix(red, black, 0.66),
        "GREEN": green,
        "RED": red,
        "CYAN": cyan,
        "SWEPT": _mix(cyan, black, 0.84),
    }
    palette.update({k: v for k, v in fixed.items() if k in PALETTE_KEYS and is_colour(v)})
    return make_readable(palette)


def make_readable(palette):
    """Push a palette until every pairing in RULES meets its contrast.

    A foreground that is too close to its ground is lifted towards white;
    once it is nearly white and still short, the ground is sunk towards
    black instead. The grounds are checked first so a bright matrix cannot
    leave a light panel under light text. Returns a new dict.
    """
    out = dict(palette)
    for key in _GROUNDS:
        # A ground is a ground: no lighter than a mid-dark grey.
        for _ in range(40):
            if _luminance(out[key]) <= (0.12 if key in ("WARN", "DANGER") else 0.03):
                break
            out[key] = _mix(out[key], "#000000", 0.15)
    for _ in range(80):
        short = [(fg, bg, need) for fg, bg, need in RULES
                 if contrast(out[fg], out[bg]) < need]
        if not short:
            break
        for fg, bg, need in short:
            if fg in _GROUNDS:
                fg, bg = bg, fg
            if _luminance(out[fg]) < 0.80:
                out[fg] = _mix(out[fg], "#ffffff", 0.07)
            else:
                out[bg] = _mix(out[bg], "#000000", 0.12)
    for key in PALETTE_KEYS:
        if out.get(key, "").lower() == _CHROMA:
            out[key] = "#020203"
    return out


def standard_palette():
    """What the game looks like on the identity matrix: the HUD orange."""
    return palette_from_accent(HUD_ORANGE)


def palette_from_matrix(matrix):
    """The standard palette with every orange-derived colour passed through
    the matrix, then made readable. The OK, warning and telemetry colours
    are not passed through: a warning that stops being red is not a warning."""
    base = standard_palette()
    matrix = _matrix(matrix)
    if matrix is None or is_identity(matrix):
        return base
    out = {}
    for key in PALETTE_KEYS:
        out[key] = base[key] if key in ("GREEN", "RED", "CYAN", "SWEPT", "DANGER") \
            else recolour(base[key], matrix)
    # The accent through the matrix picks its own OK and warning colours,
    # so a matrix that turns the HUD green does not put green text beside
    # a green OK.
    accent = out["ORANGE"] if contrast(out["ORANGE"], out["VOID"]) >= 1.5 else \
        _mix(out["ORANGE"], "#ffffff", 0.5)
    out["GREEN"] = _apart(_GREENS, accent, "GREEN")
    out["RED"] = _apart(_REDS, accent, "RED")
    out["CYAN"] = _apart(_CYANS, accent, "CYAN")
    out["SWEPT"] = _mix(out["CYAN"], "#000000", 0.84)
    out["DANGER"] = _mix(out["RED"], "#000000", 0.66)
    out["ORANGE"] = accent
    return make_readable(out)


# ---------------------------------------------------------------------------
# EDHM
# ---------------------------------------------------------------------------

def _ini(path):
    """[section][key] -> text, or None if the file is not there or not an ini."""
    parser = configparser.ConfigParser(interpolation=None, strict=False,
                                       inline_comment_prefixes=(";", "#"),
                                       comment_prefixes=(";", "#"))
    parser.optionxform = str
    try:
        with io.open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
            parser.read_file(fh)
    except (OSError, configparser.Error, UnicodeError):
        return None
    out = {}
    for section in parser.sections():
        out[section.lower()] = dict(parser.items(section))
    return out


def _constant(ini, key):
    for section in (ini or {}).values():
        if key in section:
            return section[key]
    return None


def _matrix_from(lookup):
    rows = []
    for names in EDHM_MATRIX_KEYS:
        row = []
        for name in names:
            value = lookup(name)
            if value is None:
                return None
            try:
                row.append(float(value))
            except (TypeError, ValueError):
                return None
        rows.append(tuple(row))
    return _matrix(rows)


def _read_edhm_json(path):
    """The mod front end's ThemeSettings.json: the elements by key."""
    try:
        with io.open(path, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, ValueError, UnicodeError):
        return None
    if not isinstance(data, dict):
        return None
    by_key = {}
    for group in data.get("ui_groups") or []:
        for element in (group or {}).get("Elements") or []:
            if isinstance(element, dict) and element.get("Key"):
                by_key[str(element["Key"])] = element.get("Value")
    xml = {}
    for element in data.get("xml_profile") or []:
        if isinstance(element, dict) and element.get("key"):
            xml[str(element["key"])] = element.get("value")
    return by_key, xml


def read_edhm(folder):
    """EDHM's main text colour, its mode and its matrix out of an EDHM-ini
    folder. {"found", "file", "mode", "accent", "matrix", "problem"}. Never
    raises; no folder is simply not found."""
    out = {"found": False, "file": "", "mode": None, "accent": None,
           "matrix": None, "problem": ""}
    if not folder or not os.path.isdir(folder):
        return out
    theme = os.path.join(folder, EDHM_THEME)
    loaded = _read_edhm_json(theme) if os.path.isfile(theme) else None
    if loaded is not None:
        by_key, xml = loaded
        colour = next((v for k, v in by_key.items()
                       if k.split("|")[0] == EDHM_TEXT_KEYS[0]), None)
        accent = argb_to_hex(colour) if colour is not None else None
        try:
            mode = int(float(by_key.get(EDHM_MODE_KEY)))
        except (TypeError, ValueError):
            mode = None
        if accent is not None:
            out.update(found=True, file=theme, mode=mode, accent=accent,
                       matrix=_matrix_from(xml.get))
            return out
    startup = _ini(os.path.join(folder, "Startup-Profile.ini"))
    advanced = _ini(os.path.join(folder, "Advanced.ini"))
    if startup is None and advanced is None:
        out["problem"] = "no readable EDHM settings in %s" % folder
        return out
    try:
        mode = int(float(_constant(startup, EDHM_MODE_KEY)))
    except (TypeError, ValueError):
        mode = None
    parts = [_constant(advanced, key) for key in EDHM_TEXT_KEYS]
    accent = linear_to_hex(parts) if None not in parts else None
    out.update(found=True, mode=mode, accent=accent,
               file=os.path.join(folder, "Advanced.ini" if accent else "Startup-Profile.ini"),
               matrix=_matrix_from(lambda k: _constant(
                   _ini(os.path.join(folder, "XML-Profile.ini")), k)))
    return out


def _edhm_pointer(settings_json):
    """The game folders the mod's front end was told about, active first."""
    try:
        with io.open(settings_json, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, ValueError, UnicodeError, TypeError):
        return []
    if not isinstance(data, dict):
        return []
    active = str(data.get("ActiveInstance") or "")
    found = []
    for publisher in data.get("GameInstances") or []:
        for game in (publisher or {}).get("games") or []:
            if not isinstance(game, dict):
                continue
            path = str(game.get("path") or "").strip()
            if path:
                found.append((0 if str(game.get("instance")) == active else 1, path))
    return [path for _rank, path in sorted(found, key=lambda pair: pair[0])]


def default_game_roots():
    """Where the game is usually installed on Windows: the launcher's own
    Products folder, Steam's and Epic's."""
    roots = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        roots.append(os.path.join(local, "Frontier_Developments", "Products"))
    for env in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
        base = os.environ.get(env)
        if base:
            roots.append(os.path.join(base, "Frontier", "Products"))
            roots.append(os.path.join(base, "Steam", "steamapps", "common",
                                      "Elite Dangerous", "Products"))
            roots.append(os.path.join(base, "Epic Games", "EliteDangerous", "Products"))
    return roots


def edhm_folders(roots=None, settings_json=None):
    """Every EDHM-ini folder under the given roots, each root taken as the
    game's exe folder, a Products folder, or a folder that holds EDHM-ini
    itself. The mod front end's pointer, when given, is looked at first."""
    if settings_json is None:
        settings_json = os.path.join(
            os.environ.get("USERPROFILE") or os.path.expanduser("~"), EDHM_SETTINGS_SUBPATH)
    candidates = _edhm_pointer(settings_json) if settings_json else []
    candidates += list(roots if roots is not None else default_game_roots())
    found = []
    for root in candidates:
        tries = [root] + [os.path.join(root, name) for name in GAME_FOLDERS]
        for folder in tries:
            ini = os.path.join(folder, EDHM_INI)
            if os.path.isdir(ini) and ini not in found:
                found.append(ini)
    return found


# ---------------------------------------------------------------------------
# The whole read
# ---------------------------------------------------------------------------

def _found(source, palette, words, file="", matrix=None, accent=None):
    return {"source": source, "file": file, "matrix": matrix, "accent": accent,
            "palette": palette, "words": words}


def read_game_theme(localappdata=None, game_roots=None, settings_json=None):
    """What the game's HUD is coloured right now, and a palette to match.

    {"source": "edhm" | "matrix" | "standard", "file", "matrix", "accent",
    "palette", "words"} - words being the one line the Theme tab shows. EDHM
    with a custom main text colour wins; EDHM set to the matrix uses its own
    copy of it; otherwise the override XML's matrix; otherwise the standard
    orange. Never raises.
    """
    note = ""
    try:
        for folder in edhm_folders(game_roots, settings_json):
            edhm = read_edhm(folder)
            if not edhm["found"]:
                continue
            name = os.path.join(EDHM_INI, os.path.basename(edhm["file"]))
            if edhm["mode"] == EDHM_XML and edhm["matrix"] is not None:
                palette = palette_from_matrix(edhm["matrix"])
                return _found("edhm", palette,
                              "From EDHM (%s): the HUD is on EDHM's own colour matrix, "
                              "which makes the orange %s." % (name, palette["ORANGE"]),
                              edhm["file"], edhm["matrix"], palette["ORANGE"])
            if edhm["mode"] != EDHM_DEFAULT and edhm["accent"]:
                palette = palette_from_accent(edhm["accent"])
                return _found("edhm", palette,
                              "From EDHM (%s): the main text colour is %s."
                              % (name, edhm["accent"]), edhm["file"], None, edhm["accent"])
            note = " EDHM is installed but leaves the main text on the game's own colour."
            break
    except Exception as exc:       # a broken mod folder must never stop a start
        note = " EDHM's settings could not be read (%s)." % exc
    try:
        path = override_path(localappdata)
        read = read_matrix(path)
    except Exception as exc:
        read = {"found": False, "file": "", "matrix": None, "identity": True,
                "problem": "could not be read (%s)" % exc}
        path = ""
    if read["matrix"] is not None and not read["identity"]:
        palette = palette_from_matrix(read["matrix"])
        tail = (" (%s)" % read["problem"]) if read["problem"] else ""
        return _found("matrix", palette,
                      "From the HUD colour matrix in %s: it makes the orange %s.%s%s"
                      % (OVERRIDE_FILE, palette["ORANGE"], tail, note),
                      path, read["matrix"], palette["ORANGE"])
    palette = standard_palette()
    if not read["found"]:
        why = "no override file"
    elif read["problem"]:
        why = "%s could not be read: %s" % (OVERRIDE_FILE, read["problem"])
    elif read["matrix"] is None:
        why = "%s has no colour block" % OVERRIDE_FILE
    else:
        why = "the identity matrix in %s" % OVERRIDE_FILE
    return _found("standard", palette,
                  "The game is on its standard colours (%s).%s" % (why, note),
                  path if read["found"] else "", read["matrix"], palette["ORANGE"])
