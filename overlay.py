"""
The in-game overlay: a scope over the cockpit, in two shapes.

RADAR is the one to use. A round top-down scope centred on a mining location
signal, with the deposits on it as coloured pins sized by rig count, the
commander as an arrow that moves, range rings labelled in metres and the
Rhino's scanner range drawn around the vehicle. It is the picture you plan a
patch from without alt-tabbing.

STRIP is the original: a compass tape across the top of the screen showing
which way the recorded deposits are, which is the better shape when all you
want is "which way do I turn".

The idea is the same one the exobiology tools use - you should not have to
alt-tab to know which way to drive. A frameless, always-on-top, click-through
window sits over the game and draws one or the other.

One thing worth knowing up front, and the app says so rather than leaving
anyone to guess: no overlay of any kind can appear over a game running in
EXCLUSIVE FULLSCREEN. That is how DirectX works, not something a tool can
work around. Borderless or windowed and it appears; true fullscreen and it
never will.

The layout maths is kept as plain functions so it can be checked without a
display - the window itself cannot be, but where every mark lands can.
"""


import json
import math

import planview as PV

# The window is filled with this colour and Windows is told to treat it as
# transparent, which is how a rectangular window becomes a floating HUD.
CHROMA = "#010203"

# The game's own window, as Windows names it. The class is what the
# community's own key scripts match on; the title is the fallback.
GAME_WINDOW_CLASS = "FrontierDevelopmentsAppWinClass"
GAME_WINDOW_TITLE = "Elite - Dangerous"

# A rig drops off the SRV's Contacts panel at about this range, measured in
# the game - past it the compass is the only way back to it.
RIG_CONTACTS_M = 2900.0

# How long a confirmation stays up over the game.
FLASH_SECONDS = 3.0


def foreground_is_game():
    """Is Elite the window in front? None where that cannot be asked.

    The overlay is for the game. Left up over everything, it sat on top of
    EDSMT's own Find and Earnings windows and whatever else was in front,
    so it only shows while the game has the front of the screen.
    """
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
    except Exception:
        return None
    try:
        user32.GetForegroundWindow.restype = wintypes.HWND
        handle = user32.GetForegroundWindow()
        if not handle:
            return False
        buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(handle, buffer, 256)
        if buffer.value == GAME_WINDOW_CLASS:
            return True
        user32.GetWindowTextW(handle, buffer, 256)
        return buffer.value.startswith(GAME_WINDOW_TITLE)
    except Exception:
        return None

# How much of the horizon the tape shows either side of straight ahead.
# Wide enough to see something you are not pointed at, narrow enough that
# the marks are not squashed together.
DEFAULT_SPAN_DEG = 120.0

# The two shapes. Radar is the default: it is what the tool is for.
RADAR = "radar"
STRIP = "strip"
# The strip is the default and stays the default. It is the one that
# works with the game in front of you without asking anything of you,
# and two other tools already do the scope better. The scope is an
# option you turn on, not the thing you get handed.
DEFAULT_MODE = STRIP

# Radar zoom. It sizes itself to hold the deposits and the commander, but
# not tighter than this (a single deposit two metres away should not fill
# the scope) and not wider than the cap, past which this stops being a map.
MIN_RADIUS_M = 250.0
DEFAULT_MAX_RADIUS_M = PV.MAX_MAP_RADIUS_M

# Cockpit palette, the same one edsmt.py draws the main window with. It is
# repeated rather than imported because importing the application from the
# overlay it owns is a circle - colour_for() goes through the app for the
# same reason.
VOID = "#0b0705"
SCOPE = "#0a0704"
RULE = "#3d2404"
ORANGE = "#ff7a18"
AMBER = "#ffb545"
TEXT = "#e9dccd"
DIM = "#9c6a3c"
FAINT = "#6d4826"
CYAN = "#37c6d4"
SCAN_RING = "#2a5f66"
# The glass the concept panels sit on. Deliberately close to the background:
# furniture must never read as a contact.
GLASS = "#081311"
RED = "#d1483a"
# The rig about to be lost. Not in any theme: a warning that goes pastel on
# the ice theme is not a warning.
ALARM_RED = "#ff2a1a"
# The ship's hold with room in it. Fixed for the same reason.
GREEN_OK = "#5fd068"
# Ground the scanner has already been over, on the scope. The same dark teal
# as the main map, so the part of the survey area still dark is the part
# still to drive.
SWEPT_SCOPE = "#10282a"

# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------
# The colours above are the defaults, not the values. THEMES re-points them
# at runtime, because "pick a colour" that only tinted one line of the tape
# was the whole of the theming this app had - everything else was a hex
# constant baked in at import, so choosing a colour visibly did nothing.
#
# Each theme names only what differs. Anything it leaves out keeps the
# cockpit value, so a theme is a short readable dict rather than a wall of
# hexes nobody can check.
BASE_THEME = {
    "VOID": "#0b0705", "SCOPE": "#0a0704", "RULE": "#3d2404",
    "ORANGE": "#ff7a18", "AMBER": "#ffb545", "TEXT": "#e9dccd",
    "DIM": "#9c6a3c", "FAINT": "#6d4826", "CYAN": "#37c6d4",
    "SCAN_RING": "#2a5f66", "RED": "#d1483a",
    "GLASS": "#081311", "SWEPT_SCOPE": "#10282a",
}
# Every theme is a whole palette, the app's and the overlay's, so the main
# window and the boxes over the game can wear the same one. Fourteen, all on
# a dark ground - the overlay sits over a cockpit and the app beside one.
# tests/test_themes.py holds every one of them to contrast ratios worked out
# the WCAG way, so no theme can ship with text you have to squint at.
PALETTE_KEYS = ("VOID", "PANEL", "RAIL", "STEEL", "RULE", "ORANGE", "AMBER",
                "TEXT", "MUTED", "DIM", "FAINT", "GRID", "GREEN", "SWEPT",
                "RED", "CYAN", "WARN", "DANGER")
PALETTES = {
    "cockpit": {
        "VOID": "#0b0705", "PANEL": "#15100b", "RAIL": "#1b130c", "STEEL": "#241a10", "RULE": "#3d2404", "ORANGE": "#ff7a18",
        "AMBER": "#ffb545", "TEXT": "#e9dccd", "MUTED": "#b49b80", "DIM": "#9c6a3c", "FAINT": "#6d4826", "GRID": "#1e1409",
        "GREEN": "#35d07f", "SWEPT": "#12292b", "RED": "#d1483a", "CYAN": "#37c6d4", "WARN": "#6b4a1f", "DANGER": "#5a3330",
    },
    "elite": {
        "VOID": "#080604", "PANEL": "#130d07", "RAIL": "#1a1109", "STEEL": "#26190c", "RULE": "#4a2a06", "ORANGE": "#ff7100",
        "AMBER": "#ffa030", "TEXT": "#ffe2c2", "MUTED": "#c9a47a", "DIM": "#b07028", "FAINT": "#7a4a18", "GRID": "#1f1307",
        "GREEN": "#3ddc84", "SWEPT": "#14292a", "RED": "#e0503f", "CYAN": "#40c8d8", "WARN": "#6e4512", "DANGER": "#5c2e28",
    },
    "signal": {
        "VOID": "#03100f", "PANEL": "#071816", "RAIL": "#0a1e1c", "STEEL": "#0f2a27", "RULE": "#1d4f4a", "ORANGE": "#4fe3d0",
        "AMBER": "#7ff2e2", "TEXT": "#d8f3ef", "MUTED": "#96c9c2", "DIM": "#5fa39b", "FAINT": "#3d716c", "GRID": "#0b2220",
        "GREEN": "#8be36b", "SWEPT": "#123a36", "RED": "#ff6b5b", "CYAN": "#9fd8ff", "WARN": "#1f5048", "DANGER": "#4f2c2a",
    },
    "ice": {
        "VOID": "#05080d", "PANEL": "#0b111a", "RAIL": "#0e1621", "STEEL": "#14202f", "RULE": "#20364f", "ORANGE": "#79b8ff",
        "AMBER": "#a8d4ff", "TEXT": "#e1ecf9", "MUTED": "#a3b8cf", "DIM": "#6c8aab", "FAINT": "#47617d", "GRID": "#0d1826",
        "GREEN": "#4fe0a0", "SWEPT": "#12283a", "RED": "#ff6f61", "CYAN": "#79ffe1", "WARN": "#28476a", "DANGER": "#51303a",
    },
    "phosphor": {
        "VOID": "#040a04", "PANEL": "#081208", "RAIL": "#0a170a", "STEEL": "#0f210f", "RULE": "#1e4a1e", "ORANGE": "#5cff8f",
        "AMBER": "#9dffbc", "TEXT": "#d8ffe2", "MUTED": "#9fd6ae", "DIM": "#5aa46e", "FAINT": "#3a6b48", "GRID": "#0c1d0c",
        "GREEN": "#c8ff5c", "SWEPT": "#103a24", "RED": "#ff6b5b", "CYAN": "#5cffd6", "WARN": "#245a2c", "DANGER": "#4d2a24",
    },
    "amber": {
        "VOID": "#0a0600", "PANEL": "#140c02", "RAIL": "#1a1003", "STEEL": "#241604", "RULE": "#4a2e05", "ORANGE": "#ffb000",
        "AMBER": "#ffd060", "TEXT": "#ffe9bf", "MUTED": "#d6b87a", "DIM": "#b8862e", "FAINT": "#7c5a1c", "GRID": "#1e1403",
        "GREEN": "#ffd060", "SWEPT": "#2a2208", "RED": "#ff6a3d", "CYAN": "#ffd89a", "WARN": "#6a4a0e", "DANGER": "#5a2a14",
    },
    "crimson": {
        "VOID": "#0c0506", "PANEL": "#170a0c", "RAIL": "#1d0d10", "STEEL": "#281216", "RULE": "#4e1e25", "ORANGE": "#ff4d5e",
        "AMBER": "#ff8a95", "TEXT": "#f4dfe1", "MUTED": "#c9a3a8", "DIM": "#b0636d", "FAINT": "#7a3f47", "GRID": "#1f0b0e",
        "GREEN": "#48d38a", "SWEPT": "#122628", "RED": "#ff9f43", "CYAN": "#5ccfe6", "WARN": "#6a2830", "DANGER": "#3a1f24",
    },
    "violet": {
        "VOID": "#08050e", "PANEL": "#110c1c", "RAIL": "#161024", "STEEL": "#1f1732", "RULE": "#3a2a5c", "ORANGE": "#b98bff",
        "AMBER": "#d8bfff", "TEXT": "#ece4fb", "MUTED": "#b7a8d4", "DIM": "#8b75b8", "FAINT": "#5e4d80", "GRID": "#150f24",
        "GREEN": "#5fe0a8", "SWEPT": "#1a2438", "RED": "#ff6b8b", "CYAN": "#7fd8ff", "WARN": "#46306e", "DANGER": "#4a2438",
    },
    "gold": {
        "VOID": "#070810", "PANEL": "#0e1120", "RAIL": "#121629", "STEEL": "#1a1f38", "RULE": "#353c63", "ORANGE": "#f5c542",
        "AMBER": "#ffe08a", "TEXT": "#f3efe2", "MUTED": "#c7c0a3", "DIM": "#a8974f", "FAINT": "#6f6536", "GRID": "#12162a",
        "GREEN": "#5fe0a0", "SWEPT": "#172a38", "RED": "#ff6f5e", "CYAN": "#8fd4ff", "WARN": "#4d4424", "DANGER": "#4a2a30",
    },
    "fleet": {
        "VOID": "#04070c", "PANEL": "#0a1119", "RAIL": "#0d1620", "STEEL": "#122030", "RULE": "#23405e", "ORANGE": "#4aa3ff",
        "AMBER": "#8ec5ff", "TEXT": "#e2edf8", "MUTED": "#a6b9cc", "DIM": "#6b8eb0", "FAINT": "#48617c", "GRID": "#0c1724",
        "GREEN": "#43d18c", "SWEPT": "#10283a", "RED": "#ff6b57", "CYAN": "#6fe8ff", "WARN": "#27496e", "DANGER": "#4a2c33",
    },
    "xeno": {
        "VOID": "#040806", "PANEL": "#09110d", "RAIL": "#0c1611", "STEEL": "#111f18", "RULE": "#244232", "ORANGE": "#9dff3c",
        "AMBER": "#c8ff8a", "TEXT": "#e4f7df", "MUTED": "#a8c9a2", "DIM": "#72a066", "FAINT": "#4a6e45", "GRID": "#0c1a12",
        "GREEN": "#56f0c8", "SWEPT": "#10302a", "RED": "#ff5f7a", "CYAN": "#3cf0ff", "WARN": "#2e5222", "DANGER": "#4a2430",
    },
    "nebula": {
        "VOID": "#0b0510", "PANEL": "#150a1d", "RAIL": "#1b0d25", "STEEL": "#261333", "RULE": "#4b2463", "ORANGE": "#ff5fb4",
        "AMBER": "#ff9ad2", "TEXT": "#f7e3f0", "MUTED": "#cfa6c3", "DIM": "#b36b9e", "FAINT": "#7a4570", "GRID": "#1c0c24",
        "GREEN": "#6be3b0", "SWEPT": "#1e2240", "RED": "#ffb347", "CYAN": "#8ad8ff", "WARN": "#5a2856", "DANGER": "#4a2233",
    },
    "contrast": {
        "VOID": "#000000", "PANEL": "#0b0b0b", "RAIL": "#111111", "STEEL": "#1a1a1a", "RULE": "#5a5a5a", "ORANGE": "#ffd400",
        "AMBER": "#fff27a", "TEXT": "#ffffff", "MUTED": "#d8d8d8", "DIM": "#b0b0b0", "FAINT": "#7a7a7a", "GRID": "#161616",
        "GREEN": "#3dff8f", "SWEPT": "#0e2a2e", "RED": "#ff5a4a", "CYAN": "#4ae8ff", "WARN": "#5c5200", "DANGER": "#5a1f1a",
    },
    "colourblind": {
        "VOID": "#05070b", "PANEL": "#0c1118", "RAIL": "#10161f", "STEEL": "#172030", "RULE": "#2d4460", "ORANGE": "#56b4e9",
        "AMBER": "#9fd3f2", "TEXT": "#eef3f8", "MUTED": "#b3c1cf", "DIM": "#7d93aa", "FAINT": "#526577", "GRID": "#0f1824",
        "GREEN": "#009e73", "SWEPT": "#0f2833", "RED": "#e69f00", "CYAN": "#cc79a7", "WARN": "#5a4a10", "DANGER": "#4a3020",
    },
}
THEME_NAMES = {"cockpit": "Radio Raxxla cockpit", "elite": "Elite orange", "signal": "Signal teal", "ice": "Ice blue", "phosphor": "Green phosphor", "amber": "Amber terminal", "crimson": "Crimson alert", "violet": "Deep space violet", "gold": "Imperial gold", "fleet": "Fleet blue", "xeno": "Xeno green", "nebula": "Nebula pink", "contrast": "High contrast", "colourblind": "Colour-safe (blue/orange)"}
THEME_ORDER = tuple(PALETTES)


def _mix(a, b, share):
    """a, `share` of the way to b, as #rrggbb."""
    a, b = a.lstrip("#"), b.lstrip("#")
    out = []
    for i in (0, 2, 4):
        x, y = int(a[i:i + 2], 16), int(b[i:i + 2], 16)
        out.append(round(x + (y - x) * share))
    return "#%02x%02x%02x" % tuple(out)


def overlay_palette(full):
    """The overlay's colours out of a whole palette.

    The scope's dish and the glass behind the cards are the ground; the
    scanner ring is the telemetry colour sunk most of the way into it, so
    it reads as furniture and never as a contact.
    """
    return {
        "VOID": full["VOID"], "SCOPE": full["VOID"], "RULE": full["RULE"],
        "ORANGE": full["ORANGE"], "AMBER": full["AMBER"], "TEXT": full["TEXT"],
        "DIM": full["DIM"], "FAINT": full["FAINT"], "CYAN": full["CYAN"],
        "SCAN_RING": _mix(full["CYAN"], full["VOID"], 0.6), "RED": full["RED"],
        "GLASS": _mix(full["PANEL"], full["VOID"], 0.5),
        "SWEPT_SCOPE": full["SWEPT"],
    }


def theme_palette(name):
    """The whole palette for a theme name; the cockpit for anything unknown."""
    return dict(PALETTES.get(str(name or "cockpit").strip().lower(),
                             PALETTES["cockpit"]))


# What each theme changes on the overlay. Kept under the old name because
# the overlay has always asked THEMES for it.
THEMES = {name: overlay_palette(full) for name, full in PALETTES.items()}


def dot(canvas, x, y, radius, fill, outline, shared=False):
    """One deposit on a map. Yours are round; another commander's are a
    diamond, so the two are told apart at a glance whatever the colour -
    a difference of shape survives every theme, a difference of shade
    does not."""
    if shared:
        r = radius * 1.25
        return canvas.create_polygon(x, y - r, x + r, y, x, y + r, x - r, y,
                                     fill=fill, outline=outline or fill)
    return canvas.create_oval(x - radius, y - radius, x + radius, y + radius,
                              fill=fill, outline=outline)


def apply_theme(name, accent=None):
    """Re-point every colour in this module. Returns the palette applied.

    Module globals rather than a dict every drawing call has to thread
    through: the drawing code is forty functions deep in `fill=ORANGE`, and
    rewriting all of it to carry a palette argument would be the ground-up
    rewrite this project has already been burned by once.

    `accent` overrides the theme's instrument colour, so "pick any #rrggbb"
    still works and now actually re-tints the whole overlay instead of one
    line of the tape.
    """
    palette = dict(BASE_THEME)
    palette.update(THEMES.get(str(name or "cockpit").strip().lower(),
                              THEMES["cockpit"]))
    if accent and is_colour(accent):
        palette["ORANGE"] = accent
    globals().update(palette)
    return palette


def is_colour(text):
    """#rrggbb, and nothing else. Repeated from edsmt.py rather than
    imported, because importing the app from the overlay it owns is a
    circle."""
    text = str(text or "").strip()
    return (len(text) == 7 and text.startswith("#")
            and all(c in "0123456789abcdefABCDEF" for c in text[1:]))

# Settings keys the radar understands that DEFAULT_SETTINGS in edsmt.py does
# not carry yet. Every one of them is read with an inline fallback, so the
# overlay behaves correctly on a settings file that has never heard of them;
# this list is what says so out loud, and tests/test_overlay.py fails if an
# entry here is ever added to DEFAULT_SETTINGS without being deleted from
# here. Remove an entry the moment edsmt.py grows the key.
# Keys the overlay reads that DEFAULT_SETTINGS does not carry yet. Every
# one must be read with its fallback spelled out, so a settings file that
# has never heard of it still opens a working overlay. overlay_mode and
# overlay_centre have graduated: they are in DEFAULT_SETTINGS and pickable
# in Settings, because a mode nobody can select is a mode nobody has.
PENDING_SETTINGS = {
    "overlay_radar_size": 0,               # pixels square, 0 = fit my screen
    "overlay_max_radius_m": DEFAULT_MAX_RADIUS_M,
    "overlay_scope_fill": False,           # a filled dish hides the ground
    # Overrides the theme's instrument colour with any #rrggbb. There is no
    # control for it on purpose: a theme picker AND a colour picker are two
    # rows doing one job, and the second one is the one people bounce off.
    # Hand-edit settings.json if you want a colour no theme offers.
    "overlay_colour": "",
}

# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------
# The overlay is not one window any more. It is a set of small windows, each
# placed where its owner wants it, because no two commanders have the same
# screen, the same resolution, or the same idea of what the cockpit already
# covers. Unlock, drag each one where it belongs, resize it by its corner,
# lock. That is the whole workflow, and it never goes near settings.json.
TARGETS = "targets"
STATUS = "status"
DEPOSIT = "deposit"
GUIDE = "guide"

# The work keys as they ship: Left Alt and the number row, numbered in the
# order a signal is worked, so the key for step 3 is Alt+3. The one table -
# the app's defaults, its buttons, Settings' Reset and this overlay's hints
# all read it, so no screen can go on naming a key that moved.
WORK_KEYS = {
    "hotkey_location": "ALT+1",    # log the signal and set the centre
    "hotkey_border": "ALT+2",      # the survey border, at the edge
    "hotkey_deposit": "ALT+3",     # mark the deposit
    "hotkey_rigs": "ALT+4",        # a rig is down here, one press per rig
    "hotkey_allup": "ALT+5",       # all rigs up
    "hotkey_update": "ALT+6",      # update the deposit you are on
}
PANEL_ORDER = (STRIP, RADAR, TARGETS, STATUS, DEPOSIT, GUIDE)
PANEL_TITLE = {STRIP: "COMPASS", RADAR: "SCOPE",
               TARGETS: "TARGETS", STATUS: "STATUS",
               DEPOSIT: "MINERAL DEPOSIT", GUIDE: "GUIDE"}
PANEL_WHAT = {
    STRIP: "the compass tape - which way to turn",
    RADAR: "the scope - the patch from above",
    TARGETS: "the nearest finds, in order",
    STATUS: "body, count, and what is next",
    DEPOSIT: "one card: the deposit you are on, and a signal radar",
    GUIDE: "step by step: what to do next, and the key for it",
}

# WHERE PANELS LIVE, AND WHY IT IS A FRACTION AND NOT A PIXEL.
#
# A position saved in pixels is a position saved for one monitor. Drag the
# targets box to the right-hand edge of a 3840-wide screen, save 3600, then
# play on the 1920-wide laptop - and it is off the side. Worse, it comes
# back off the side, so the overlay looks broken rather than misplaced.
#
# Every panel is therefore stored as a fraction of the screen it was placed
# on: x, y, w and h, each 0..1. 0.8 across is 0.8 across on any monitor, and
# a box sized to hold six lines on a 4K screen is still sized to hold six
# lines on a 1080p one. Pixels are worked out at the moment the window is
# built, against the screen it is actually being built on.
#
# The default is the layout the author plays with, measured off his own
# screen: the compass across the top of the canopy, the scope and the guide
# down the left edge, the targets on the right, the status along the bottom
# under the console - every box clear of the middle of the screen, where the
# game is flown.
DEFAULT_LAYOUT = {
    STRIP:   {"x": 0.3165, "y": 0.1113, "w": 0.3465, "h": 0.0590},
    RADAR:   {"x": 0.0034, "y": 0.3650, "w": 0.0990, "h": 0.1720},
    TARGETS: {"x": 0.8165, "y": 0.2665, "w": 0.1835, "h": 0.2975},
    STATUS:  {"x": 0.3564, "y": 0.9294, "w": 0.2896, "h": 0.0686},
    DEPOSIT: {"x": 0.3000, "y": 0.6400, "w": 0.4000, "h": 0.2300},
    GUIDE:   {"x": 0.0034, "y": 0.5380, "w": 0.2186, "h": 0.1625},
}

# Below these a panel has nothing left to say, so a slip of the mouse on the
# resize grip cannot turn one into a sliver you then cannot grab again.
MIN_PANEL = {STRIP: (260, 74), RADAR: (200, 200),
             TARGETS: (180, 96), STATUS: (220, 48),
             DEPOSIT: (420, 170), GUIDE: (240, 128)}

# The resize corner, and the bar you drag to move. Both only exist while the
# overlay is unlocked; locked, a panel is scenery and clicks go to the game.
GRIP_PX = 18
HANDLE_PX = 18


def clamp(value, low, high):
    return low if value < low else (high if value > high else value)


def panel_pixels(spec, screen_w, screen_h, key=STRIP):
    """A stored fraction, turned into a rectangle on THIS screen.

    Clamped twice: to something big enough to read, and to somewhere you
    can still reach with a mouse. A panel dragged onto a second monitor
    that has since been unplugged comes back on the monitor that is left,
    not to the coordinates it was saved at.
    """
    spec = dict(spec or {})
    fallback = DEFAULT_LAYOUT.get(key, DEFAULT_LAYOUT[STRIP])
    def part(name):
        try:
            return float(spec.get(name, fallback[name]))
        except (TypeError, ValueError):
            return float(fallback[name])
    min_w, min_h = MIN_PANEL.get(key, (180, 60))
    width = int(round(clamp(part("w"), 0.0, 1.0) * screen_w))
    height = int(round(clamp(part("h"), 0.0, 1.0) * screen_h))
    width = int(clamp(width, min(min_w, screen_w), screen_w))
    height = int(clamp(height, min(min_h, screen_h), screen_h))
    x = int(round(part("x") * screen_w))
    y = int(round(part("y") * screen_h))
    # Leave a grabbable strip on screen whatever was saved.
    x = int(clamp(x, -width + 120, screen_w - 120))
    y = int(clamp(y, 0, max(0, screen_h - 40)))
    return width, height, x, y


def panel_fractions(width, height, x, y, screen_w, screen_h):
    """The other direction: what to write down after a drag."""
    screen_w = max(1, int(screen_w))
    screen_h = max(1, int(screen_h))
    return {"x": round(float(x) / screen_w, 5),
            "y": round(float(y) / screen_h, 5),
            "w": round(float(width) / screen_w, 5),
            "h": round(float(height) / screen_h, 5)}


def relative_bearing(heading, bearing):
    """-180 hard left, 0 dead ahead, +180 behind you."""
    return ((float(bearing) - float(heading) + 540.0) % 360.0) - 180.0


def tape_x(heading, bearing, width, span_deg=DEFAULT_SPAN_DEG):
    """Where along the tape a bearing sits, in pixels. None if off the ends."""
    offset = relative_bearing(heading, bearing)
    half = span_deg / 2.0
    if abs(offset) > half:
        return None
    return (width / 2.0) + (offset / half) * (width / 2.0)


def money(credits):
    """Credits at a glance. 4.2M beats 4,183,000 on a HUD you read at speed."""
    try:
        value = float(credits or 0)
    except (TypeError, ValueError):
        return "0"
    if value >= 1e9:
        return "%.2fB" % (value / 1e9)
    if value >= 1e6:
        return "%.2fM" % (value / 1e6)
    if value >= 1e3:
        return "%.0fk" % (value / 1e3)
    return "%d" % int(value)


def edge_x(heading, bearing, width):
    """Which end to pin an off-tape marker to."""
    return width - 8.0 if relative_bearing(heading, bearing) > 0 else 8.0


def cardinal_marks(heading, width, span_deg=DEFAULT_SPAN_DEG, step=15):
    """The degree ticks along the tape, so it reads like a real compass."""
    marks = []
    half = span_deg / 2.0
    base = int(heading // step) * step
    for offset in range(-int(half // step) - 1, int(half // step) + 2):
        bearing = (base + offset * step) % 360
        x = tape_x(heading, bearing, width, span_deg)
        if x is None:
            continue
        major = bearing % 90 == 0
        label = {0: "N", 90: "E", 180: "S", 270: "W"}.get(bearing)
        if label is None and bearing % 45 == 0:
            label = {45: "NE", 135: "SE", 225: "SW", 315: "NW"}[bearing]
        marks.append({"bearing": bearing, "x": x, "major": major,
                      "label": label, "text": "%03d" % bearing})
    return marks


def target_marks(rows, heading, width, span_deg=DEFAULT_SPAN_DEG, limit=6):
    """Where each deposit sits on the tape, nearest first.

    Anything outside the tape is pinned to the near end with an arrow, so a
    deposit behind you is still visible as "turn round, 400 m" rather than
    silently vanishing - which is the failure that makes an overlay useless
    the moment you drive past something.
    """
    marks = []
    for row in sorted(rows, key=lambda r: float(r.get("range_m") or 0))[:limit]:
        bearing = float(row.get("bearing") or 0.0)
        deposit = row.get("deposit", {})
        x = tape_x(heading, bearing, width, span_deg)
        offscreen = x is None
        marks.append({
            "commodity": str(deposit.get("commodity") or ""),
            "rigs": str(deposit.get("rigs") or ""),
            "range_m": float(row.get("range_m") or 0.0),
            "bearing": bearing,
            "offset": relative_bearing(heading, bearing),
            "x": edge_x(heading, bearing, width) if offscreen else x,
            "offscreen": offscreen,
            "id": deposit.get("id", ""),
        })
    return marks


# Consolas is fixed-pitch, so a label's width is its length times the width
# of one character at that size - near enough to keep labels apart without
# asking Tk to draw each one first to measure it.
CHAR_PX = {7: 5.6, 8: 6.2, 9: 7.0, 10: 7.7, 11: 8.4, 13: 10.0, 17: 13.0}


def text_box(text, size=9):
    """(width, height) in pixels of one line of Consolas at `size`."""
    per = CHAR_PX.get(int(size), size * 0.78)
    return len(str(text)) * per, size + 5


def free_spot(x, y, text, size, gap, taken, bounds=None, measure=None):
    """Where `text` can sit beside (x, y) touching nothing already placed:
    right, left, below, above. The box, or None when every side is taken -
    a label that could only go over another one is left off. `measure`
    gives (width, height) from the real font when there is one."""
    w, h = (measure or text_box)(text, size)
    spots = [(x + gap, y - h / 2.0), (x - gap - w, y - h / 2.0),
             (x - w / 2.0, y + gap - 2), (x - w / 2.0, y - gap - h + 2)]
    for sx, sy in spots:
        box = (sx, sy, sx + w, sy + h)
        if bounds is not None and (box[0] < bounds[0] or box[1] < bounds[1]
                                   or box[2] > bounds[2] or box[3] > bounds[3]):
            continue
        if not any(PV.boxes_touch(box, other, 1.0) for other in taken):
            return box
    return None


def fit_text(text, width_px, size=9):
    """`text` cut to what fits in `width_px`, with a mark where it was cut."""
    per = CHAR_PX.get(int(size), size * 0.78)
    room = int(max(0, width_px) // per)
    text = str(text)
    if len(text) <= room:
        return text
    return text[:max(0, room - 1)] + "~" if room > 1 else ""


def rig_tape_marks(rigs, heading, width, span_deg=DEFAULT_SPAN_DEG, gap=30.0):
    """Where each rig sits on the compass tape.

    `rigs` is what the app's watch_rigs hands the overlay. A rig behind you
    is pinned to the near end with an arrow, like a deposit. Two rigs in the
    same direction are nudged apart rather than printed into one square.
    """
    if not isinstance(rigs, dict):
        return []
    try:
        limit = float(rigs.get("limit_m") or 0)
    except (TypeError, ValueError):
        limit = 0.0
    marks = []
    for rig in rigs.get("rigs") or []:
        try:
            bearing = float(rig["bearing"])
            metres = float(rig["range_m"])
        except (KeyError, TypeError, ValueError):
            continue
        x = tape_x(heading, bearing, width, span_deg)
        offscreen = x is None
        offset = relative_bearing(heading, bearing)
        if offscreen:
            # Far enough in from the end for the whole square to show.
            x = 16.0 if offset < 0 else width - 16.0
        marks.append({
            "n": rig.get("n"),
            "commodity": str(rig.get("commodity") or ""),
            "range_m": metres,
            "offset": offset,
            "x": x,
            "offscreen": offscreen,
            "far": bool(limit) and metres > limit,
            "off_contacts": metres > RIG_CONTACTS_M,
        })
    marks.sort(key=lambda m: m["x"])
    for before, after in zip(marks, marks[1:]):
        if after["x"] - before["x"] < gap:
            after["x"] = min(width - 16.0, before["x"] + gap)
    return marks


def stack(marks, min_gap=74.0):
    """Push overlapping labels onto separate rows instead of over each other.

    Deposits cluster - that is the whole point of a mining location - so
    without this the labels pile into an unreadable smear exactly when there
    is most to read.
    """
    rows = []
    for mark in sorted(marks, key=lambda m: m["x"]):
        placed = False
        for index, row in enumerate(rows):
            if all(abs(mark["x"] - other["x"]) >= min_gap for other in row):
                row.append(mark)
                mark["row"] = index
                placed = True
                break
        if not placed:
            mark["row"] = len(rows)
            rows.append([mark])
    return marks


def format_range(metres):
    try:
        value = float(metres)
    except (TypeError, ValueError):
        return "-"
    # Matches _metres() in edsmt.py deliberately: the same distance must
    # read the same on the map, on the rail and on the overlay, and two
    # decimal places on a 50 km number is false precision nobody drives by.
    if value >= 10000:
        return "%.0f km" % (value / 1000.0)
    if value >= 1000:
        return "%.2fkm" % (value / 1000.0)
    return "%.0fm" % value


def turn_arrow(offset):
    """A glyph for which way to swing, readable at a glance in the dark."""
    if abs(offset) < 6:
        return "^"
    if abs(offset) > 150:
        return "v"
    return ">" if offset > 0 else "<"


# ---------------------------------------------------------------------------
# The window
# ---------------------------------------------------------------------------

def rounded_frame(canvas, width, height, colour, radius=14, glow=True):
    """The concept's outer shell: a rounded rectangle with a soft edge.

    Tk canvases have no rounded rectangle and no blur. The corners are arcs,
    the sides are lines, and the "glow" is two more outlines drawn a pixel or
    two out in a dimmer colour - which is all a glow is at this size, and it
    costs nothing next to compositing a real one every frame.
    """
    def shell(inset, shade):
        left, top = inset, inset
        right, bottom = width - inset - 1, height - inset - 1
        if right - left < radius * 2 or bottom - top < radius * 2:
            return
        for x0, y0, start in ((left, top, 90), (right - radius * 2, top, 0),
                              (right - radius * 2, bottom - radius * 2, 270),
                              (left, bottom - radius * 2, 180)):
            canvas.create_arc(x0, y0, x0 + radius * 2, y0 + radius * 2,
                              start=start, extent=90, style="arc",
                              outline=shade)
        canvas.create_line(left + radius, top, right - radius, top, fill=shade)
        canvas.create_line(left + radius, bottom, right - radius, bottom, fill=shade)
        canvas.create_line(left, top + radius, left, bottom - radius, fill=shade)
        canvas.create_line(right, top + radius, right, bottom - radius, fill=shade)

    if glow:
        shell(0, RULE)
        shell(1, RULE)
    shell(2, colour)


def readout_rows(canvas, x, y, width, rows, gap=17, label_colour=None,
                 value_colour=None):
    """Label left, value hard right, one per line.

    The shape every cockpit readout in this game uses, and the reason it is a
    helper rather than four create_texts each time: the values have to align
    on their right edge across every row or the panel reads as a list of
    unrelated facts instead of a table.
    """
    label_colour = label_colour or TEXT
    value_colour = value_colour or AMBER
    for index, (label, value) in enumerate(rows):
        line = y + index * gap
        canvas.create_text(x, line, anchor="w", fill=label_colour,
                           font=("Consolas", 10), text=str(label).upper())
        canvas.create_text(x + width, line, anchor="e", fill=value_colour,
                           font=("Consolas", 10, "bold"), text=str(value))
    return y + max(0, len(rows) - 1) * gap


def value_bars(canvas, x, y, width, height, bars, colour=None):
    """The histogram along the bottom of the concept.

    Each bar is one commodity on this body and its height is what it is
    worth, so the shape of the strip is the shape of the money. Labelled
    underneath in whatever room there is, and unlabelled rather than
    overlapping when there is not.
    """
    if not bars or width < 20 or height < 8:
        return
    top = max(1, max(value for _name, value in bars))
    step = width / float(len(bars))
    pitch = max(2.0, min(step - 2.0, 9.0))
    for index, (name, value) in enumerate(bars):
        left = x + index * step
        tall = max(1.0, (float(value) / top) * height)
        canvas.create_rectangle(left, y + height - tall, left + pitch, y + height,
                                fill=colour or ORANGE, outline="")
        if step >= 26:
            canvas.create_text(left + pitch / 2.0, y + height + 6, anchor="n",
                               fill=FAINT, font=("Consolas", 7),
                               text=str(name)[:6].upper())


class Panel:
    """One box on the screen: its own window, its own place, its own size.

    Drag it anywhere while the overlay is unlocked, pull the bottom-right
    corner to resize it, and the fractions it is stored as mean it lands in
    the same relative place on any monitor. Locked, it stops taking clicks
    at all and the game gets them instead.
    """

    def __init__(self, overlay, key):
        self.overlay = overlay
        self.key = key
        self.window = None
        self.canvas = None
        self._drag = None

    # -- lifecycle -------------------------------------------------------

    def open(self, tk, parent):
        if self.window is not None:
            return
        win = tk.Toplevel(parent)
        win.title("EDSMT %s" % PANEL_TITLE.get(self.key, self.key))
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        width, height, x, y = self.overlay.panel_geometry(self.key, win)
        win.geometry("%dx%d+%d+%d" % (width, height, x, y))

        canvas = tk.Canvas(win, bg=CHROMA, highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        canvas.bind("<Button-1>", self._grab)
        canvas.bind("<B1-Motion>", self._move)
        canvas.bind("<ButtonRelease-1>", self._drop)
        # A box is closed by the app, never by Alt+F4. An unlocked box takes
        # focus while it is being dragged, and a close request landing on it
        # then used to destroy the window out from under the overlay - which
        # went on trying to draw into it, and logged a TclError on every
        # redraw from then on.
        try:
            win.protocol("WM_DELETE_WINDOW", lambda: None)
        except Exception:
            pass

        try:
            win.update_idletasks()
            win.deiconify()
            win.lift()
        except Exception:
            pass
        self.window, self.canvas = win, canvas

    def close(self):
        # Not remembered on the way out - see Overlay.hide. A box's place is
        # written when it is dropped, and only then.
        if self.window is not None:
            try:
                self.window.destroy()
            except Exception:
                pass
        self.window = self.canvas = None

    def alive(self):
        """Is this box's window still a real window?

        Something other than this code can destroy it - a close request, a
        display change, the parent going away - and a canvas reference that
        outlives its window fails every redraw with "invalid command name".
        Asked of Tk itself, not of our own bookkeeping, because our
        bookkeeping is exactly what was out of date.
        """
        if self.window is None or self.canvas is None:
            return False
        probe = getattr(self.canvas, "winfo_exists", None)
        if not callable(probe):
            return True
        try:
            answer = probe()
        except Exception:
            return False
        # A stand-in canvas with nothing to say is not a dead one.
        if answer is None:
            return True
        try:
            return bool(int(answer))
        except (TypeError, ValueError):
            return True

    def size(self):
        """Real pixels, or the pixels it is about to be.

        An unmapped window answers 1 to winfo_width, and 1 is truthy - which
        is how a whole compass tape once got drawn into a single pixel.
        """
        width = height = 0
        try:
            width = int(self.window.winfo_width())
            height = int(self.window.winfo_height())
        except Exception:
            pass
        if width > 1 and height > 1:
            return width, height
        try:
            planned_w, planned_h, _x, _y = self.overlay.panel_geometry(
                self.key, self.window)
            return planned_w, planned_h
        except Exception:
            return MIN_PANEL.get(self.key, (300, 120))

    # -- being moved -----------------------------------------------------

    def _grab(self, event):
        if self.overlay.locked:
            return
        width, height = self.size()
        corner = (event.x >= width - GRIP_PX and event.y >= height - GRIP_PX)
        self._drag = ("resize" if corner else "move", event.x_root, event.y_root,
                      self.window.winfo_x(), self.window.winfo_y(), width, height)

    def _move(self, event):
        if not self._drag:
            return
        how, sx, sy, wx, wy, ww, wh = self._drag
        dx, dy = event.x_root - sx, event.y_root - sy
        if how == "move":
            self.window.geometry("+%d+%d" % (wx + dx, wy + dy))
            return
        min_w, min_h = MIN_PANEL.get(self.key, (180, 60))
        self.window.geometry("%dx%d+%d+%d" % (max(min_w, ww + dx),
                                              max(min_h, wh + dy), wx, wy))

    def _drop(self, _event):
        if not self._drag:
            return
        self._drag = None
        self.remember()
        self.overlay.save_layout()

    def remember(self):
        """Write this panel's place down, as fractions of this screen."""
        if self.window is None:
            return
        try:
            # A withdrawn or never-drawn window measures as 1x1 at 0,0, and
            # writing that down is how a layout got scrambled. Only a box
            # that is actually on screen is measured.
            viewable = getattr(self.window, "winfo_viewable", None)
            if callable(viewable) and not int(viewable() or 0):
                return
            width = int(self.window.winfo_width())
            height = int(self.window.winfo_height())
            if width <= 1 or height <= 1:
                return
            screen_w, screen_h = self.overlay.screen(self.window)
            spec = panel_fractions(width, height,
                                   self.window.winfo_x(), self.window.winfo_y(),
                                   screen_w, screen_h)
        except Exception:
            return
        layout = dict(self.overlay.layout())
        layout[self.key] = spec
        self.overlay.settings["overlay_layout"] = layout

    # -- the furniture that only exists while it is unlocked -------------

    def chrome(self, width, height):
        """Say which box this is, where to grab it, and where to resize it.

        Drawn last, over the panel's own contents, and only while unlocked -
        a locked panel is a HUD, and a HUD with handles on it is a mess.
        """
        canvas = self.canvas
        canvas.create_rectangle(1, 1, width - 2, height - 2,
                                outline=CYAN, dash=(4, 3))
        canvas.create_rectangle(1, 1, width - 2, HANDLE_PX,
                                fill=VOID, outline="")
        canvas.create_text(6, HANDLE_PX / 2 + 1, anchor="w", fill=CYAN,
                           font=("Consolas", 9, "bold"),
                           text=PANEL_TITLE.get(self.key, self.key))
        canvas.create_text(width - 6, HANDLE_PX / 2 + 1, anchor="e", fill=DIM,
                           font=("Consolas", 8), text="drag to move")
        for step in range(3):
            offset = 4 + step * 5
            canvas.create_line(width - 3, height - offset,
                               width - offset, height - 3, fill=CYAN)


class Overlay:
    """A frameless strip that floats over the game.

    Built lazily and destroyed when switched off, so a commander who never
    turns it on never pays for it. Everything Windows-specific is wrapped:
    on anything else the window still appears, just without transparency or
    click-through, which is enough to develop against.
    """

    def __init__(self, app, tk_module, settings):
        self.app = app
        self.tk = tk_module
        self.settings = settings
        self.window = None
        self.canvas = None
        self._drag = None
        self.panels = {}
        self._drawing = None
        self._survey = None
        self._rigs = None
        # Whether the boxes are up right now; None until first decided.
        self._shown = None
        # How many finds on this body are away from the signal being worked,
        # and so left off the boxes.
        self._elsewhere = 0
        self._flash_win = None
        self._flash_canvas = None
        self._flash_job = None
        self._alarm_win = None
        self._alarm_canvas = None
        self._alarm_up = False
        self._guide = None

    # -- lifecycle -------------------------------------------------------

    @property
    def showing(self):
        return bool(self.panels) or self.window is not None

    @property
    def locked(self):
        """Locked means clicks go to the game, not to the overlay.

        One key, not two. The lock and the click-through are the same fact
        about the window, and storing it twice is how they end up
        disagreeing - a HUD you can see but not drag, or one you can drag
        but that eats your shots.
        """
        return bool(self.settings.get("overlay_click_through", True))

    def set_locked(self, value):
        """Lock or unlock every panel at once."""
        self.settings["overlay_click_through"] = bool(value)
        self.apply_click_through()
        return bool(value)

    def layout(self):
        """Where each panel sits, as fractions. Defaults filled in."""
        stored = self._stored_layout()
        merged = {}
        for key in PANEL_ORDER:
            spec = stored.get(key)
            merged[key] = (dict(spec) if isinstance(spec, dict)
                           else dict(DEFAULT_LAYOUT[key]))
        return merged

    def _stored_layout(self):
        """Whatever is in settings, believed only if it is a dict."""
        stored = self.settings.get("overlay_layout") or {}
        if isinstance(stored, str):
            try:
                stored = json.loads(stored)
            except Exception:
                stored = {}
        return stored if isinstance(stored, dict) else {}

    def save_layout(self):
        """Hand the layout back to the app so it reaches settings.json.

        Dragging a panel is a settings change like any other; it just does
        not come from the settings window.
        """
        saver = getattr(self.app, "save_settings", None)
        if callable(saver):
            try:
                saver()
            except Exception:
                pass

    def reset_layout(self):
        """Put every panel back where it started.

        The escape hatch for a panel dragged somewhere unreachable, and the
        reason a bad drag is never something you edit JSON to undo.
        """
        self.settings["overlay_layout"] = {key: dict(spec)
                                           for key, spec in DEFAULT_LAYOUT.items()}
        for key in ("overlay_x", "overlay_y"):
            self.settings.pop(key, None)
        self.save_layout()
        self.reposition()

    def active(self):
        """Which panels are switched on.

        With none of them switched on the old single-shape setting still
        decides, so a settings.json written before panels existed opens
        exactly what it always opened.
        """
        chosen = [key for key in PANEL_ORDER if key != GUIDE
                  and self.settings.get("overlay_show_%s" % key)]
        chosen = chosen or [self.mode()]
        # The guide rides along with whichever boxes are up. Counted with
        # them, it would be the one box "switched on", and a new commander
        # would get a guide and no compass.
        if self.settings.get("overlay_show_guide"):
            chosen.append(GUIDE)
        return chosen

    def screen(self, win):
        """The screen this window is actually on, in pixels."""
        try:
            return int(win.winfo_screenwidth()), int(win.winfo_screenheight())
        except Exception:
            return 1920, 1080

    def panel_geometry(self, key, win):
        """Size and position for one panel, on this screen.

        A panel with nothing saved for it falls back to the old
        single-window placement when it is the shape that used to BE the
        overlay, so a commander who had dragged the strip somewhere keeps it
        there. Every other panel starts from the default layout.
        """
        saved = self._stored_layout().get(key)
        if not isinstance(saved, dict):
            if key in (STRIP, RADAR) and key == self.mode():
                return self.placement(win)
            saved = DEFAULT_LAYOUT[key]
        screen_w, screen_h = self.screen(win)
        return panel_pixels(saved, screen_w, screen_h, key)

    def show(self):
        """Open every panel that is switched on."""
        if self.panels:
            return
        tk = self.tk
        for key in self.active():
            panel = Panel(self, key)
            panel.open(tk, self.app)
            self.panels[key] = panel
        if not self.panels:
            return
        # The first panel is also the "the overlay" of the old single-window
        # code: the update check, the click-through tests and anything else
        # that reached for .window still find one.
        primary = self.panels[self.active()[0]]
        self.window, self.canvas = primary.window, primary.canvas
        self.apply_click_through()
        self.apply_transparency()
        self.draw([], 0.0, "overlay on - waiting for the game")

    def reposition(self):
        """Put every open panel back on the geometry the settings describe.

        Used after a layout reset and after Save in settings, so a change
        lands on the screen instead of at the next restart.
        """
        for key, panel in self.panels.items():
            if panel.window is None:
                continue
            try:
                panel.window.geometry("%dx%d+%d+%d"
                                      % self.panel_geometry(key, panel.window))
            except Exception:
                pass

    def windows(self):
        """Every real window this overlay owns.

        Panels when there are panels, and the bare .window when there are
        not - which is how the Windows plumbing is exercised in tests that
        never open a Toplevel.
        """
        found = [panel.window for panel in self.panels.values()
                 if panel.window is not None]
        if found:
            return found
        return [self.window] if self.window is not None else []

    def mode(self):
        """Which shape is on screen. Anything unrecognised means radar.

        Read with an inline default rather than from DEFAULT_SETTINGS, so a
        settings.json written before the radar existed still opens one.
        """
        wanted = str(self.settings.get("overlay_mode", DEFAULT_MODE) or "").strip().lower()
        return STRIP if wanted == STRIP else RADAR

    def placement(self, win):
        """Size and position, kept on a screen that actually exists.

        Sized from the screen rather than fixed pixels: 900 wide is most of
        a 1080p monitor and a postage stamp on a 4K one. A saved position is
        honoured, but only if it still lands somewhere visible - unplug the
        monitor the overlay was dragged onto and it would otherwise come
        back off-screen and look broken.

        The radar is square and sits top-left, where nothing in the cockpit
        lives. The strip is wide and sits
        top-centre. They keep their own size but share one position, because
        a remembered position is a preference and not worth a settings row
        per shape.
        """
        try:
            screen_w = int(win.winfo_screenwidth())
            screen_h = int(win.winfo_screenheight())
        except Exception:
            screen_w, screen_h = 1920, 1080

        if self.mode() == RADAR:
            side = int(float(self.settings.get("overlay_radar_size", 0) or 0))
            if not side:
                side = max(260, min(int(min(screen_w, screen_h) * 0.34), 900))
            side = max(200, min(side, min(screen_w, screen_h)))
            width = height = side
            home = (int(screen_w * 0.02), int(screen_h * 0.05))
        else:
            default_w = max(640, min(int(screen_w * 0.55), 2200))
            default_h = max(110, int(default_w * 0.14))
            width = int(self.settings.get("overlay_width") or 0) or default_w
            height = int(self.settings.get("overlay_height") or 0) or default_h
            width = max(240, min(width, screen_w))
            height = max(70, min(height, screen_h))
            home = ((screen_w - width) // 2, int(screen_h * 0.04))

        saved_x = self.settings.get("overlay_x")
        saved_y = self.settings.get("overlay_y")
        if saved_x in (None, "") or saved_y in (None, ""):
            x, y = home
        else:
            x, y = int(saved_x), int(saved_y)
        # Keep at least a strip of it on screen.
        x = max(-width + 120, min(x, screen_w - 120))
        y = max(0, min(y, screen_h - 60))
        return width, height, x, y

    def apply_transparency(self):
        """Colour key and opacity, applied AFTER any ex-style change.

        Order matters and getting it wrong is invisible rather than loud.
        Windows drops a layered window's colour key and alpha whenever the
        WS_EX_LAYERED bit is written through SetWindowLongW, so these have
        to be (re)asserted afterwards or the window renders as nothing at
        all - no error, no clue, just an empty screen.
        """
        try:
            opacity = float(self.settings.get("overlay_opacity", 0.9))
        except (TypeError, ValueError):
            opacity = 0.9
        for win in self.windows():
            try:
                win.attributes("-transparentcolor", CHROMA)
            except Exception:
                pass                              # not Windows; still usable
            try:
                win.attributes("-alpha", opacity)
            except Exception:
                pass

    def follow_game(self):
        """Put the boxes up while the game is in front, take them down when
        it is not. True if they are up.

        Unlocked, they stay up whatever is in front: that is when they are
        being arranged, from EDSMT's own window. Where Windows cannot be
        asked, they stay up, as they always did.
        """
        wanted = True
        if self.locked and self.settings.get("overlay_only_over_game", True):
            front = foreground_is_game()
            wanted = True if front is None else front
        if wanted != self._shown:
            for panel in self.panels.values():
                if panel.window is None:
                    continue
                try:
                    if wanted:
                        # Tk shows an override-redirect window without
                        # activating it, so the game keeps the keyboard.
                        panel.window.deiconify()
                        panel.window.lift()
                    else:
                        panel.window.withdraw()
                except Exception:
                    pass
            self._shown = wanted
        return wanted

    # -- a word over the game, when a key is pressed -----------------------

    def flash(self, title, detail="", colour=None, seconds=FLASH_SECONDS):
        """Say what a key just did, over the game, for a few seconds.

        With the game in front, EDSMT's own status line cannot be seen, so a
        key pressed in the SRV used to do its work in silence. This is its
        answer: RIG 2 DOWN, SIGNAL 5 LOGGED, and the reason when it could
        not. Its own small window, so it shows whichever boxes are on -
        or none. Only over the game; with anything else in front it says
        nothing, and the app's status line has it.
        """
        if not self.settings.get("overlay_flash", True):
            return False
        if foreground_is_game() is False:
            return False
        win = self._flash_window()
        if win is None:
            return False
        canvas = self._flash_canvas
        width, height = 560, 74
        try:
            screen_w = int(win.winfo_screenwidth())
            screen_h = int(win.winfo_screenheight())
        except Exception:
            screen_w, screen_h = 1920, 1080
        win.geometry("%dx%d+%d+%d" % (width, height, (screen_w - width) // 2,
                                      int(screen_h * 0.16)))
        self.theme()
        colour = colour or ORANGE
        canvas.delete("all")
        canvas.create_rectangle(2, 2, width - 2, height - 2, fill=GLASS,
                                outline=colour, width=2)
        canvas.create_rectangle(2, 2, 10, height - 2, fill=colour, outline="")
        canvas.create_text(24, 24, anchor="w", fill=colour,
                           font=("Consolas", 17, "bold"), text=str(title)[:40])
        if detail:
            canvas.create_text(24, 52, anchor="w", fill=TEXT,
                               font=("Consolas", 11), text=str(detail)[:64])
        try:
            win.deiconify()
            win.lift()
        except Exception:
            return False
        if self._flash_job is not None:
            try:
                self.app.after_cancel(self._flash_job)
            except Exception:
                pass
        try:
            self._flash_job = self.app.after(int(seconds * 1000),
                                             self.end_flash)
        except Exception:
            self._flash_job = None
        return True

    def end_flash(self):
        self._flash_job = None
        if self._flash_win is not None:
            try:
                self._flash_win.withdraw()
            except Exception:
                self._flash_win = self._flash_canvas = None

    def _flash_window(self):
        """The flash's window, built once and kept, click-through."""
        win = self._flash_win
        try:
            if win is not None and win.winfo_exists():
                return win
        except Exception:
            pass
        win, canvas = self._hud_window()
        if win is None:
            return None
        self._flash_win, self._flash_canvas = win, canvas
        return win

    # -- the last rig warning, in the middle of the screen ---------------

    def alarm(self, title, detail=""):
        """A big warning triangle in the middle of the screen, over the game.

        For the one thing worth taking the middle of the screen for: a rig
        about to be destroyed. It stays up for as long as the app keeps
        asking - the app asks every tick while the danger lasts, and calls
        end_alarm the moment it is over, the rig is lost, or ALL UP is
        pressed. Over the game only, like the flash; red whatever the theme.
        """
        if foreground_is_game() is False:
            self.end_alarm()
            return False
        win = getattr(self, "_alarm_win", None)
        try:
            alive = win is not None and win.winfo_exists()
        except Exception:
            alive = False
        if not alive:
            win, canvas = self._hud_window()
            if win is None:
                return False
            self._alarm_win, self._alarm_canvas = win, canvas
        canvas = self._alarm_canvas
        width, height = 560, 430
        try:
            screen_w = int(win.winfo_screenwidth())
            screen_h = int(win.winfo_screenheight())
        except Exception:
            screen_w, screen_h = 1920, 1080
        win.geometry("%dx%d+%d+%d" % (width, height, (screen_w - width) // 2,
                                      (screen_h - height) // 2))
        canvas.delete("all")
        top, left, right, base = (width / 2.0, 12), (70, 300), (width - 70, 300), 300
        canvas.create_polygon(top[0], top[1], right[0], right[1], left[0], left[1],
                              fill=ALARM_RED, outline="#ffffff", width=4)
        canvas.create_text(width / 2.0, 200, text="!", fill="#ffffff",
                           font=("Consolas", 110, "bold"))
        canvas.create_rectangle(10, base + 14, width - 10, height - 8,
                                fill=GLASS, outline=ALARM_RED, width=3)
        canvas.create_text(width / 2.0, base + 48, text=str(title)[:26],
                           fill=ALARM_RED, font=("Consolas", 26, "bold"))
        if detail:
            canvas.create_text(width / 2.0, base + 92, text=str(detail)[:44],
                               fill="#ffffff", font=("Consolas", 14, "bold"))
        try:
            win.deiconify()
            win.lift()
        except Exception:
            return False
        self._alarm_up = True
        return True

    def end_alarm(self):
        """Take the warning triangle down. Safe to call when it is not up."""
        self._alarm_up = False
        win = getattr(self, "_alarm_win", None)
        if win is not None:
            try:
                win.withdraw()
            except Exception:
                self._alarm_win = self._alarm_canvas = None

    def _hud_window(self):
        """A frameless, click-through, see-through window over the game.

        (window, canvas), or (None, None) where Tk will not make one. Shared
        by the flash and the rig alarm, which need exactly the same plumbing:
        topmost, never takes focus, never takes a click, and the chroma
        colour shows the game through it."""
        try:
            win = self.tk.Toplevel(self.app)
            win.withdraw()
            win.title("EDSMT")
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            canvas = self.tk.Canvas(win, bg=CHROMA, highlightthickness=0, bd=0)
            canvas.pack(fill="both", expand=True)
        except Exception:
            return None, None
        try:
            win.attributes("-transparentcolor", CHROMA)
        except Exception:
            pass
        try:
            import ctypes
            GWL_EXSTYLE, WS_EX_TRANSPARENT = -20, 0x20
            WS_EX_NOACTIVATE = 0x08000000
            user32 = ctypes.windll.user32
            win.update_idletasks()
            handle = self.handle(win)
            if handle:
                style = user32.GetWindowLongW(handle, GWL_EXSTYLE)
                user32.SetWindowLongW(handle, GWL_EXSTYLE,
                                      style | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE)
            # The colour key again, after the style write - see
            # apply_transparency for why the order matters.
            win.attributes("-transparentcolor", CHROMA)
        except Exception:
            pass
        return win, canvas

    def hide(self):
        """Close every box. Where they were is NOT written down here.

        It used to be: each box measured itself on the way out and saved
        that. But the boxes are withdrawn whenever the game is not in front
        - which is exactly when Overlay off, Save, or Save and restart get
        pressed, from EDSMT's own window - and a withdrawn window measures
        as nonsense. Every theme change went through here and scrambled the
        layout people had spent time on. A box's place is saved when it is
        dropped after a drag, and nowhere else."""
        self.end_alarm()
        for panel in list(self.panels.values()):
            panel.close()
        self.panels = {}
        self._shown = None
        if self.window is not None:
            try:
                self.window.destroy()
            except Exception:
                pass
        self.window = None
        self.canvas = None
        self._drawing = None

    def theme(self):
        """Apply the commander's theme to this module's palette.

        Called before every redraw rather than once at startup: the theme
        can change while the overlay is up, and a HUD that needs a restart
        to change colour is a HUD that looks like the setting did nothing.
        """
        return apply_theme(self.settings.get("overlay_theme", "cockpit"),
                           self.settings.get("overlay_colour", ""))

    def refresh_settings(self, settings):
        """Take a changed settings dict, and act on it now.

        A panel switched on or off in Settings has to appear or disappear on
        Save, not at the next restart - "I ticked it and nothing happened"
        is indistinguishable from "it is broken".
        """
        self.settings = settings
        if not self.panels:
            if self.window is None:
                return
            try:
                self.window.geometry("%dx%d+%d+%d" % self.placement(self.window))
            except Exception:
                pass
            return self.apply_click_through()

        wanted = self.active()
        for key in [k for k in self.panels if k not in wanted]:
            self.panels.pop(key).close()
        for key in wanted:
            if key not in self.panels:
                panel = Panel(self, key)
                try:
                    panel.open(self.tk, self.app)
                except Exception:
                    continue
                self.panels[key] = panel
        # Keep the panels in a fixed order, so "the first one" is a stable
        # thing to mean by "the overlay window".
        self.panels = {key: self.panels[key] for key in PANEL_ORDER
                       if key in self.panels}
        primary = next(iter(self.panels.values()), None)
        self.window = primary.window if primary else None
        self.canvas = primary.canvas if primary else None
        self.reposition()
        self.apply_click_through()

    def remember_position(self):
        """Keep where everything was put, so it comes back the same.

        Panels write fractions. The legacy overlay_x/overlay_y are still
        written for the primary window so a downgrade is not a disaster.
        """
        for panel in self.panels.values():
            panel.remember()
        if self.window is None:
            return
        try:
            self.settings["overlay_x"] = self.window.winfo_x()
            self.settings["overlay_y"] = self.window.winfo_y()
        except Exception:
            pass

    # -- windows plumbing ------------------------------------------------

    def apply_click_through(self):
        """Let clicks fall through to the game, or not.

        With this on the strip is scenery: you cannot drag it, but you also
        cannot accidentally click it instead of the game, which is what you
        want once it is positioned.

        WS_EX_LAYERED IS DELIBERATELY NOT TOUCHED. Tk sets it itself when
        -transparentcolor is applied, and owns the colour key that goes with
        it. Writing that bit again through SetWindowLongW invalidates the
        layered attributes, and a layered window with no colour key and no
        alpha draws nothing whatsoever. That is what made the overlay
        invisible on every machine it was tried on: the window was there,
        on top, the right size, drawing correctly - and completely
        transparent. Only WS_EX_TRANSPARENT gets flipped here.
        """
        windows = self.windows()
        if not windows:
            return
        wanted = self.locked
        try:
            import ctypes
            GWL_EXSTYLE, WS_EX_TRANSPARENT = -20, 0x20
            user32 = ctypes.windll.user32
            for win in windows:
                handle = self.handle(win)
                if not handle:
                    continue
                style = user32.GetWindowLongW(handle, GWL_EXSTYLE)
                if wanted:
                    style |= WS_EX_TRANSPARENT
                else:
                    style &= ~WS_EX_TRANSPARENT
                user32.SetWindowLongW(handle, GWL_EXSTYLE, style)
        except Exception:
            pass          # not Windows, or the window is not realised yet
        # Belt and braces: even though the layered bit is untouched now,
        # re-asserting costs nothing and the failure it prevents is silent.
        self.apply_transparency()

    def handle(self, win=None):
        """The real top-level window handle.

        Tk's winfo_id() gives the frame it draws into, whose parent is the
        actual top-level window on Windows - but for an overrideredirect
        window GetParent can also answer 0 or the desktop, and setting
        styles on the desktop is a bad afternoon.
        """
        win = win if win is not None else self.window
        if win is None:
            return 0
        try:
            import ctypes
            user32 = ctypes.windll.user32
            child = win.winfo_id()
            parent = user32.GetParent(child)
            desktop = user32.GetDesktopWindow()
            if parent and parent != desktop:
                return parent
            return child
        except Exception:
            return 0

    def _grab(self, event):
        if self.settings.get("overlay_click_through", True):
            return
        self._drag = (event.x_root, event.y_root,
                      self.window.winfo_x(), self.window.winfo_y())

    def _move(self, event):
        if not self._drag:
            return
        sx, sy, wx, wy = self._drag
        self.window.geometry("+%d+%d" % (wx + event.x_root - sx,
                                         wy + event.y_root - sy))

    def _drop(self, _event):
        if self._drag:
            self._drag = None
            self.remember_position()

    # -- drawing ---------------------------------------------------------

    def panel_size(self):
        """How big the window really is, in pixels.

        "or default" is wrong here: an unmapped window answers 1, and 1 is
        truthy, so the whole tape used to be drawn into a single pixel. The
        planned size is the right answer while it is still coming up,
        because that is the size it is about to be.
        """
        if self._drawing is not None:
            return self._drawing.size()
        width = height = 0
        try:
            width = int(self.window.winfo_width())
            height = int(self.window.winfo_height())
        except Exception:
            pass
        if width > 1 and height > 1:
            return width, height
        try:
            planned_w, planned_h, _x, _y = self.placement(self.window)
        except Exception:
            planned_w, planned_h = (380, 380) if self.mode() == RADAR else (900, 120)
        return (width if width > 1 else planned_w,
                height if height > 1 else planned_h)

    def colour(self, commodity):
        """A commodity's colour, asked of the app.

        So a commodity is the same colour on the map and on the overlay.
        overlay.py cannot import edsmt.py - that would be a circle - so it
        goes through the window instead, and falls back to the accent colour
        when there is no window (the tests) or the app is older.
        """
        if hasattr(self.app, "colour_for"):
            try:
                return self.app.colour_for(commodity)
            except Exception:
                pass
        # ORANGE, not the raw setting: apply_theme has already folded any
        # hand-set overlay_colour into it, so reading the setting again here
        # is how a commodity ends up the one thing on screen still wearing
        # the old palette.
        return ORANGE

    def draw(self, rows, heading, note="", body="", location="", site=None,
             survey=None, rigs=None, guide=None, target=None, only=None,
             cargo=None, hazard=None):
        """Redraw. Called from the same poll that moves the map.

        `rows` are Survey.near rows, measured from the commander. The three
        optional arguments are what the app knows and the rows do not:
        `body` the body name for the header, `location` which mining signal
        to centre on, and `site` that signal's own position as (east, north)
        metres from the commander. All three are optional on purpose - with
        none of them the radar works out the site centre from the deposits
        themselves, which is one fewer thing a commander has to place.

        `only` names the boxes to redraw and leaves the rest as they are -
        the app's fast loop redraws the compass and the scope ten times a
        second and everything else at its own pace.
        """
        # The survey area, if one is set: drawn by the scope and summed up
        # by STATUS. Kept rather than threaded through every draw call.
        self._survey = survey if isinstance(survey, dict) else None
        # A deposit picked in the app to be guided to: GO instead of NEXT on
        # the scope and STATUS, and first in TARGETS. None is nearest-first.
        self._target_id = str(target) if target else None
        # Where the rigs are from here. When "far" is set, every box carries
        # the warning - whichever boxes a commander has on, they see it.
        self._rigs = rigs if isinstance(rigs, dict) else None
        # The step the guide is on, worked out by the app - it is the one
        # that knows what has been logged, marked and sold.
        self._guide = guide if isinstance(guide, dict) else None
        # What is in the ship and the Rhino, during a session - STATUS shows
        # it so "is the ship full yet" is answered without leaving the SRV.
        self._cargo = cargo if isinstance(cargo, dict) else None
        # A reason to be careful on this body - high gravity - said on the
        # GUIDE and STATUS boxes for as long as you are on it.
        self._hazard = hazard if isinstance(hazard, dict) else None
        # The signal being worked, and nothing else. A body can hold finds
        # thousands of kilometres apart, and the boxes used to list and point
        # at all of them: a scope sized to 50 km with 9,698 km arrows at its
        # rim, a NEAREST list of finds three thousand kilometres away. They
        # are counted, and the note says so.
        #
        # And only the signal you are AT. "RADAR ZOOM - only focus on the
        # signal source we are at": with the box still on a signal 40 km
        # back, the scope stretched to hold it and you, and read MAP RADIUS
        # 50 km. A signal further off than SIGNAL_REACH_M is not the one
        # being worked; the scope shows the ground round the SRV instead,
        # and says where that signal is.
        view = PV.signal_focus(rows, location, anchor=site,
                               near_m=PV.SIGNAL_REACH_M)
        self._elsewhere = len(view["away"])
        # Where the signal in the box is, when it is not the one you are at.
        # The scope's header says so; nothing else about it is drawn.
        self._far = view["far"]
        rows = view["here"]
        if view["far"]:
            site, location = None, ""
        if not rows and self._elsewhere and not view["far"]:
            note = ("nothing at signal %s yet - %d elsewhere on this body"
                    % (location, self._elsewhere)) if location else \
                   ("nothing here yet - %d elsewhere on this body"
                    % self._elsewhere)
        if self.panels and not self.follow_game():
            return
        if not self.panels:
            # The single-window path, still here because the overlay can be
            # driven without ever opening a Panel - that is how it is tested.
            if self.canvas is None:
                return
            self.theme()
            self.canvas.delete("all")
            width, height = self.panel_size()
            if self.mode() == RADAR:
                self.draw_radar(rows, heading, note, width, height,
                                body=body, location=location, site=site)
            else:
                self.draw_strip(rows, heading, note, width, height)
            self._rig_banner(width, height)
            return

        self.theme()
        gone = getattr(self.tk, "TclError", None)
        rebuilt = False
        for key, panel in list(self.panels.items()):
            if only is not None and key not in only:
                continue
            if not panel.alive():
                # Put it back rather than skip it. A box that vanished is a
                # box the commander switched on and still wants, and the
                # alternative is a HUD that silently loses a panel for the
                # rest of the session.
                panel.window = panel.canvas = None
                try:
                    panel.open(self.tk, self.app)
                except Exception:
                    continue
                if not panel.alive():
                    continue
                rebuilt = True
            self._drawing = panel
            self.canvas = panel.canvas
            try:
                self.canvas.delete("all")
                width, height = panel.size()
                if key == RADAR:
                    self.draw_radar(rows, heading, note, width, height,
                                    body=body, location=location, site=site)
                elif key == STRIP:
                    self.draw_strip(rows, heading, note, width, height)
                elif key == TARGETS:
                    self.draw_targets(rows, heading, width, height, body)
                elif key == STATUS:
                    self.draw_status(rows, heading, width, height, body,
                                     location, note, site)
                elif key == DEPOSIT:
                    self.draw_deposit(rows, heading, width, height, body,
                                      location, site)
                elif key == GUIDE:
                    self.draw_guide(width, height)
                self._rig_banner(width, height)
                if not self.locked:
                    panel.chrome(width, height)
            except Exception as exc:
                # Only a window dying mid-draw is forgiven here, and only
                # for this box: it is dropped and rebuilt on the next tick.
                # Anything else is a real bug and goes to crash.log as before.
                if gone is None or not isinstance(exc, gone):
                    self._drawing = None
                    raise
                panel.window = panel.canvas = None
        self._drawing = None
        if rebuilt:
            self.apply_click_through()
            self.apply_transparency()
        primary = next((p for p in self.panels.values() if p.canvas), None)
        self.window = primary.window if primary else None
        self.canvas = primary.canvas if primary else None

    def draw_strip(self, rows, heading, note, width, height):
        """The compass tape: which way to turn, and how far."""
        canvas = self.canvas
        span = float(self.settings.get("overlay_span_deg", DEFAULT_SPAN_DEG))
        limit = int(self.settings.get("overlay_targets", 6))
        accent = ORANGE
        dim = "#8a5a2c"

        baseline = 26
        canvas.create_line(0, baseline, width, baseline, fill=dim)

        for mark in cardinal_marks(heading, width, span):
            tall = 12 if mark["major"] else 6
            canvas.create_line(mark["x"], baseline - tall, mark["x"], baseline,
                               fill=accent if mark["major"] else dim)
            if mark["label"]:
                canvas.create_text(mark["x"], baseline - tall - 8,
                                   text=mark["label"], fill=accent,
                                   font=("Consolas", 11, "bold"))

        # where you are pointing
        centre = width / 2.0
        canvas.create_polygon(centre, baseline + 9, centre - 7, baseline + 1,
                              centre + 7, baseline + 1, fill="#37c6d4", outline="")

        marks = stack(target_marks(rows, heading, width, span, limit))
        for mark in marks:
            row = mark.get("row", 0)
            y = baseline + 22 + row * 20
            if y > height - 6:
                continue
            colour = self.colour(mark["commodity"])
            label = "%s %s %s" % (turn_arrow(mark["offset"]),
                                  mark["commodity"][:14],
                                  format_range(mark["range_m"]))
            if mark["rigs"]:
                label += " %sR" % mark["rigs"]
            if not mark["offscreen"]:
                canvas.create_line(mark["x"], baseline + 2, mark["x"], y - 8,
                                   fill=colour)
            anchor = "w" if mark["x"] < width / 2 else "e"
            canvas.create_text(mark["x"], y, text=label, fill=colour,
                               anchor=anchor, font=("Consolas", 11, "bold"))

        # The rigs, on the tape itself: numbered squares where they are,
        # amber, red past the warning distance. Past the Contacts panel's
        # reach the tape is the only thing still pointing at them.
        for mark in rig_tape_marks(self._rigs, heading, width, span):
            # In the colour of what it is mining, so the tape says which rig
            # is on which deposit; red round the edge past the warning.
            what = mark.get("commodity") or ""
            tint = self.colour(what) if what else AMBER
            colour = RED if mark["far"] else tint
            x, y = mark["x"], baseline
            canvas.create_rectangle(x - 7, y - 7, x + 7, y + 7, fill=GLASS,
                                    outline=colour, width=2, tags=("rigtape",))
            canvas.create_text(x, y, text=str(mark["n"]), fill=colour,
                               font=("Consolas", 8, "bold"), tags=("rigtape",))
            label = format_range(mark["range_m"])
            if what:
                label = "%s %s" % (what[:8], label)
            if mark["offscreen"]:
                label = ("< " + label) if mark["offset"] < 0 else (label + " >")
            right = x < width / 2.0
            canvas.create_text(x + (10 if right else -10), y - 11,
                               anchor="w" if right else "e", text=label,
                               fill=colour, font=("Consolas", 8, "bold"),
                               tags=("rigtape",))

        if note:
            canvas.create_text(6, height - 8, text=note, fill=dim, anchor="sw",
                               font=("Consolas", 9))
        if not self.locked:
            canvas.create_text(width - 6, height - 8, text=self.key_hint(),
                               fill=dim, anchor="se", font=("Consolas", 9))

    # -- the two list panels ---------------------------------------------

    def ranked(self, rows, heading, limit=12, guided=True):
        """The finds, nearest first, with the turn worked out.

        Worked-out deposits sort after live ones rather than disappearing:
        knowing a patch is stripped is worth knowing, and driving back to
        one you already mined is the mistake this tool exists to stop.
        With `guided`, the deposit picked to be guided to comes first.
        """
        wanted = getattr(self, "_target_id", None) if guided else None
        ranked = []
        for row in rows or []:
            deposit = row.get("deposit") or {}
            try:
                range_m = float(row.get("range_m") or 0.0)
                bearing = float(row.get("bearing") or 0.0)
            except (TypeError, ValueError):
                continue
            spent = str(deposit.get("amount") or "").strip().lower() == "depleted"
            ranked.append({
                "commodity": str(row.get("commodity")
                                 or deposit.get("commodity") or "deposit"),
                "range_m": range_m,
                "bearing": bearing,
                "offset": relative_bearing(heading, bearing),
                "rigs": str(deposit.get("rigs") or "").strip(),
                "spent": spent,
                "target": bool(wanted) and str(deposit.get("id") or "") == wanted,
            })
        ranked.sort(key=lambda item: (not item["target"], item["spent"],
                                      item["range_m"]))
        return ranked[:max(0, int(limit))]

    def draw_targets(self, rows, heading, width, height, body=""):
        """A plain list: what is near, which way, how far, how many rigs.

        The scope shows a patch and the tape shows a heading. Neither of
        them answers "what is the next thing worth driving to" without
        being read, and that is the question being asked.
        """
        canvas = self.canvas
        top = HANDLE_PX + 2 if not self.locked else 4
        canvas.create_text(6, top + 6, anchor="w", fill=TEXT,
                           font=("Consolas", 10, "bold"),
                           text="NEAREST  %s" % (body or "")[:18])
        canvas.create_line(4, top + 16, width - 4, top + 16, fill=RULE)

        # The strip along the bottom is the shape of the money on this body -
        # one bar per commodity, height by what it is worth. A count of dots
        # says nothing about that: six rigs of a cheap metal draw the same
        # picture as six rigs of a gemstone.
        prices = self.prices()
        bar_h = 22 if height >= 190 else 0
        line_h = 16
        room = max(0, int((height - (top + 26) - bar_h) // line_h))
        found = self.ranked(rows, heading, limit=room)
        if not found:
            canvas.create_text(6, top + 30, anchor="w", fill=DIM,
                               font=("Consolas", 9),
                               text="nothing logged here yet")
            return
        if bar_h:
            worth = {}
            for row in rows or []:
                name = str(row.get("commodity")
                           or (row.get("deposit") or {}).get("commodity") or "")
                if name:
                    worth[name] = worth.get(name, 0) + PV.deposit_value(row, prices)
            bars = sorted(((n, v) for n, v in worth.items() if v > 0),
                          key=lambda pair: -pair[1])[:8]
            if bars:
                value_bars(canvas, 6, height - bar_h - 10, width - 12,
                           bar_h - 8, bars, colour=ORANGE)
        for index, item in enumerate(found):
            y = top + 26 + index * line_h
            colour = FAINT if item["spent"] else self.colour(item["commodity"])
            canvas.create_text(6, y, anchor="w", fill=colour,
                               font=("Consolas", 10, "bold"),
                               text="%s %s" % (turn_arrow(item["offset"]),
                                               item["commodity"][:13]))
            tail = format_range(item["range_m"])
            if item["rigs"]:
                tail += "  %sR" % item["rigs"]
            if item["spent"]:
                tail = "mined"
            canvas.create_text(width - 6, y, anchor="e", fill=colour,
                               font=("Consolas", 10), text=tail)
        self._brackets(width, height)

    def draw_guide(self, width, height):
        """What to do next, the key that does it, and how far along you are.

        The app decides the step from what it can see - the DSS, the ground,
        a logged signal, a border, a marked deposit, rigs, the hold, a sale -
        so the guide moves on by itself as the work gets done, and a step
        already done is never asked for.
        """
        canvas = self.canvas
        guide = getattr(self, "_guide", None) or {}
        top = HANDLE_PX + 4 if not self.locked else 6
        total = int(guide.get("total") or 0)
        step = int(guide.get("step") or 0)
        canvas.create_text(8, top + 8, anchor="w", fill=DIM,
                           font=("Consolas", 9, "bold"),
                           text=("EDSMT GUIDE  %d/%d" % (step, total)
                                 if total else "EDSMT GUIDE"))
        # Progress as pips: how much is left is a shape, not a sum.
        if total:
            pip = 7
            x = width - 8 - total * (pip + 4)
            for index in range(total):
                colour = ORANGE if index < step - 1 else (
                    AMBER if index == step - 1 else RULE)
                canvas.create_rectangle(x, top + 5, x + pip, top + 5 + pip,
                                        fill=colour, outline="", tags=("pip",))
                x += pip + 4
        canvas.create_line(6, top + 18, width - 6, top + 18, fill=RULE)
        self._hazard_bar(width, height)
        title = str(guide.get("title") or "Waiting for the game")
        canvas.create_text(8, top + 34, anchor="w", fill=ORANGE,
                           font=("Consolas", 13, "bold"), text=title[:30],
                           tags=("guide-title",))
        detail = str(guide.get("detail") or "")
        if detail:
            canvas.create_text(8, top + 50, anchor="nw", fill=TEXT,
                               font=("Consolas", 10), width=max(60, width - 16),
                               text=detail[:160], tags=("guide-detail",))
        following = str(guide.get("next") or "")
        if following and height >= top + 118:
            canvas.create_text(8, height - 8, anchor="sw", fill=DIM,
                               font=("Consolas", 9),
                               text=("then: " + following)[:48],
                               tags=("guide-next",))

    def _hazard_bar(self, width, height):
        """HIGH GRAVITY across the foot of a box, in the alarm red.

        Over the bottom of the box rather than beside anything, so it
        cannot be missed and cannot be printed over."""
        hazard = getattr(self, "_hazard", None)
        if not hazard or not hazard.get("text"):
            return False
        canvas = self.canvas
        tall = 18
        canvas.create_rectangle(2, height - tall - 2, width - 2, height - 2,
                                fill=ALARM_RED, outline=ALARM_RED,
                                tags=("hazard",))
        canvas.create_text(width / 2.0, height - 2 - tall / 2.0, fill="#ffffff",
                           font=("Consolas", 10, "bold"), tags=("hazard",),
                           text=fit_text("/!\\ " + str(hazard["text"]),
                                         width - 12, 10))
        return True

    def _cargo_text(self):
        """"SHIP 233/256t  RHINO 12t", or "" outside a session."""
        cargo = getattr(self, "_cargo", None)
        if not cargo:
            return ""
        bits = []
        ship = cargo.get("ship_t")
        if ship is not None:
            capacity = cargo.get("capacity")
            bits.append("SHIP %d%st" % (int(ship), "/%d" % int(capacity)
                                        if capacity else ""))
        rhino = cargo.get("rhino_t")
        if rhino is not None:
            bits.append("RHINO %dt" % int(rhino))
        return "  ".join(bits)

    def draw_status(self, rows, heading, width, height, body="", location="",
                    note="", site=None):
        """One line of context, and one line of what to do next.

        Small enough to tuck under the radar in the cockpit, and the only
        panel that says which keys log a site and a deposit - the two
        things a new commander cannot guess.
        """
        canvas = self.canvas
        rows = list(rows or [])
        top = HANDLE_PX + 2 if not self.locked else 3
        found = PV.site_centre(rows, location or None)
        rigs = 0
        for row in rows:
            try:
                rigs += int(str((row.get("deposit") or {}).get("rigs") or 0))
            except (TypeError, ValueError):
                pass
        canvas.create_text(6, top + 8, anchor="w", fill=TEXT,
                           font=("Consolas", 10, "bold"),
                           text="%s" % (body or self._body_of(rows) or "-")[:24])
        canvas.create_text(width - 6, top + 8, anchor="e", fill=AMBER,
                           font=("Consolas", 10, "bold"),
                           text="%d DEP  %dR" % (len(rows), rigs))
        canvas.create_line(4, top + 18, width - 4, top + 18, fill=RULE)
        # What the patch is worth, stated as an estimate, because the price
        # is the part nobody can promise. A tall STATUS box gets the full
        # readout; a short one keeps the line that answers "is this trip
        # worth making" and drops the rest.
        if height >= top + 78:
            worth = PV.value_of(rows, self.prices())
            tail = ("" if not worth["unpriced"]
                    else "  +%d unpriced" % worth["unpriced"])
            readout_rows(canvas, 6, top + 48, width - 12, [
                ("est. value", "%s Cr%s" % (money(worth["credits"]), tail)),
                ("route", format_range(PV.drive_route(rows)["total_m"])),
            ])

        nearest = self.ranked(rows, heading, limit=1)
        if nearest:
            item = nearest[0]
            canvas.create_text(6, top + 30, anchor="w",
                               fill=self.colour(item["commodity"]),
                               font=("Consolas", 10, "bold"),
                               text="%s %s %s %s" % (
                                   "GO" if item["target"] else "NEXT",
                                   turn_arrow(item["offset"]),
                                   item["commodity"][:12],
                                   format_range(item["range_m"])))
        elif note:
            canvas.create_text(6, top + 30, anchor="w", fill=DIM,
                               font=("Consolas", 9), text=note[:40])
        rigs = getattr(self, "_rigs", None)
        if rigs:
            # How many rigs are down and how far the farthest is, instead of
            # the key hint, while any are down.
            canvas.create_text(width - 6, top + 30, anchor="e",
                               fill=RED if rigs.get("far") else AMBER,
                               font=("Consolas", 9, "bold"),
                               text="%dR  FAR %s %s" % (
                                   int(rigs.get("count") or 0),
                                   turn_arrow(float(rigs.get("offset") or 0)),
                                   format_range(rigs.get("range_m"))))
        else:
            canvas.create_text(width - 6, top + 30, anchor="e", fill=FAINT,
                               font=("Consolas", 9), text=self.key_hint(short=True))
        if found.get("label") and len(rows):
            canvas.create_text(6, height - 6, anchor="sw", fill=DIM,
                               font=("Consolas", 8),
                               text="SITE %s" % str(found["label"])[:16])
        survey = getattr(self, "_survey", None)
        if survey and survey.get("percent") is not None:
            done = survey["percent"]
            canvas.create_text(width - 6, height - 6, anchor="se",
                               fill=AMBER if done < 100 else CYAN,
                               font=("Consolas", 8, "bold"),
                               text="AREA SWEPT %d%%" % done)
        cargo = self._cargo_text()
        if cargo:
            full = self._cargo or {}
            capacity = full.get("capacity")
            canvas.create_text(width / 2.0, height - 6, anchor="s",
                               fill=AMBER if capacity and full.get("ship_t", 0)
                               >= capacity else GREEN_OK,
                               font=("Consolas", 9, "bold"), text=cargo,
                               tags=("cargo",))
        self._brackets(width, height)
        self._hazard_bar(width, height)

    def draw_deposit(self, rows, heading, width, height, body="", location="",
                     site=None):
        """One card: what you are standing on, and a small signal radar.

        The readout on the left is the deposit under you - what the scanner
        named, how much of it, how dense, how many rigs. The radar on the
        right is the rest of the signal, so the card answers "what is this"
        and "what else is here" without being two panels.

        Everything on it comes from a find already logged or from the
        scanner. Nothing is invented to fill a row: a field the game has
        not named reads "-", because a HUD that guesses is a HUD you stop
        trusting the moment you catch it.
        """
        canvas = self.canvas
        rows = list(rows or [])
        prices = self.prices()
        top = HANDLE_PX + 4 if not self.locked else 8
        split = int(width * 0.54)

        # -- header
        canvas.create_polygon(16, top + 9, 23, top + 2, 30, top + 9, 23, top + 16,
                              fill="", outline=ORANGE)
        canvas.create_text(40, top + 9, anchor="w", fill=TEXT,
                           font=("Consolas", 14, "bold"), text="MINERAL DEPOSIT")
        canvas.create_text(split + 12, top + 6, anchor="w", fill=DIM,
                           font=("Consolas", 9), text="SIGNAL RADAR")
        canvas.create_line(12, top + 24, width - 12, top + 24, fill=RULE)

        # -- the readout, left
        # The card is the deposit you are nearest, whatever you are being
        # guided to - it is the one you are standing on.
        nearest = self.ranked(rows, heading, limit=1, guided=False)
        here = nearest[0] if nearest else None
        deposit = {}
        if here:
            for row in rows:
                name = str(row.get("commodity")
                           or (row.get("deposit") or {}).get("commodity") or "")
                if name == here["commodity"]:
                    deposit = row.get("deposit") or {}
                    break
        worth = PV.value_of(rows, prices)
        readout_rows(canvas, 16, top + 40, split - 30, [
            ("mineral", (here["commodity"] if here else "-")[:18]),
            ("range", format_range(here["range_m"]) if here else "-"),
            ("rigs", str(deposit.get("rigs") or "-")),
            ("density", str(deposit.get("density") or "-")),
            ("amount", str(deposit.get("amount") or "-")),
        ], gap=18)

        # -- telemetry, under a rule, the way the card does it
        foot = top + 40 + 4 * 18 + 16
        if foot + 34 < height:
            canvas.create_line(12, foot - 8, split - 8, foot - 8, fill=RULE)
            canvas.create_text(16, foot + 4, anchor="w", fill=DIM,
                               font=("Consolas", 9), text="TELEMETRY")
            canvas.create_text(16, foot + 20, anchor="w", fill=AMBER,
                               font=("Consolas", 10, "bold"),
                               text="ON THIS SIGNAL: %d DEP   ~%s Cr"
                                    % (len(rows), money(worth["credits"])))

        # -- the radar, right
        scope_r = min((width - split) / 2.0 - 16, (height - top - 54) / 2.0)
        if scope_r >= 26:
            cx = split + (width - split) / 2.0
            cy = top + 34 + scope_r
            for step in (0.33, 0.66, 1.0):
                r = scope_r * step
                canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                   outline=RULE if step == 1.0 else "#1d4f4a")
            canvas.create_line(cx, cy - scope_r, cx, cy + scope_r, fill="#1d4f4a")
            canvas.create_line(cx - scope_r, cy, cx + scope_r, cy, fill="#1d4f4a")
            reach = max((r.get("range_m") or 0) for r in rows) if rows else 1.0
            for row in rows:
                try:
                    rng, brg = float(row.get("range_m") or 0), float(row.get("bearing") or 0)
                except (TypeError, ValueError):
                    continue
                offset = math.radians(brg - heading)
                pull = (rng / reach) * scope_r * 0.92 if reach else 0
                px = cx + math.sin(offset) * pull
                py = cy - math.cos(offset) * pull
                shade = self.colour(str(row.get("commodity") or ""))
                theirs = bool((row.get("deposit") or {}).get("shared")
                              or row.get("shared"))
                dot(canvas, px, py, 3 if not theirs else 4, shade, "",
                    shared=theirs)
            canvas.create_polygon(PV.arrow_points(cx, cy, 0, 8),
                                  fill=AMBER, outline="")

        # -- the value strip along the bottom right, and the signal name
        bars = {}
        for row in rows:
            name = str(row.get("commodity")
                       or (row.get("deposit") or {}).get("commodity") or "")
            if name:
                bars[name] = bars.get(name, 0) + PV.deposit_value(row, prices)
        bars = sorted(((n, v) for n, v in bars.items() if v > 0),
                      key=lambda pair: -pair[1])[:8]
        if bars and height - (top + 40) > 90:
            value_bars(canvas, split + 10, height - 34, width - split - 22, 18,
                       bars, colour=ORANGE)
        canvas.create_text(16, height - 12, anchor="w", fill=CYAN,
                           font=("Consolas", 10, "bold"),
                           text="\u25b2 SIGNAL POINT %s" % (location or "-"))
        self._brackets(width, height)

    def key_hint(self, short=False):
        """What to press, in the keys this commander actually bound.

        Short on the status strip, which is narrow by design; spelled out
        everywhere there is room for it.
        """
        if not self.locked:
            return "unlocked - drag me"

        def key(name):
            value = str(self.settings.get(name, WORK_KEYS[name]) or "").strip()
            parts = [p for p in value.split("+") if p]
            if not parts:
                return ""
            mods = {"ALT": "Alt", "CTRL": "Ctrl", "SHIFT": "Shift", "WIN": "Win"}
            return "+".join(mods.get(p.upper(), p) for p in parts)

        # In the order a signal is worked: centre, border, deposit, rig.
        wanted = [(key("hotkey_location"), "SITE"),
                  (key("hotkey_border"), "BORDER"),
                  (key("hotkey_deposit"), "DEP" if short else "DEPOSIT"),
                  (key("hotkey_rigs"), "RIG")]
        if short:
            wanted = [pair for pair in wanted if pair[1] != "BORDER"]
        return "  ".join("%s %s" % (bound, what) for bound, what in wanted if bound)

    # -- the radar -------------------------------------------------------
    #
    # A round scope centred on a mining location signal, which is the shape
    # this tool wanted from the start: the deposits are a patch on the
    # ground, and a patch is a picture, not a list of bearings. All of the
    # geometry is planview.py - the same functions the main window's plan
    # view is drawn from - so the overlay and the map can never disagree
    # about where something is.

    def draw_radar(self, rows, heading, note, width, height,
                   body="", location="", site=None):
        rows = list(rows or [])
        heading = float(heading or 0.0)
        head, foot = 38, 30

        # Centred on the signal for planning, on the SRV for driving. With
        # nothing recorded there is no signal to centre on, so it says SRV
        # rather than drawing a marker for a site it invented.
        centred = str(self.settings.get("overlay_centre", "site")
                      or "").strip().lower() != "srv"
        found = PV.site_centre(rows, location or None)
        placed = found["count"] > 0
        if site is not None:
            try:
                found = dict(found, east_m=float(site[0]), north_m=float(site[1]))
                placed = True
            except (TypeError, ValueError, IndexError, KeyError):
                pass
        centred = centred and placed
        origin = (found["east_m"], found["north_m"]) if centred else (0.0, 0.0)

        # Auto-zoom: the signal being worked and nothing else - its finds,
        # its survey border and the rigs on it. You are in the picture while
        # you are at the signal; further out you are a chevron on the rim
        # with the range, which says which way is back without shrinking the
        # patch to a dot. It used to hold you wherever you were, capped at
        # 50 km, and that was the MAP RADIUS 50 km scope.
        points = [(east - origin[0], north - origin[1])
                  for east, north in (PV.to_offset(row.get("range_m"),
                                                   row.get("bearing"))
                                      for row in rows)]
        extra = []
        survey = getattr(self, "_survey", None) or {}
        if survey.get("centre") and survey.get("border_m"):
            ce, cn = survey["centre"]
            reach = float(survey["border_m"])
            extra += [(ce - origin[0] + de, cn - origin[1] + dn)
                      for de, dn in ((reach, 0), (-reach, 0), (0, reach), (0, -reach))]
        rigs = getattr(self, "_rigs", None) or {}
        extra += [(m["east"] - origin[0], m["north"] - origin[1])
                  for m in rigs.get("rigs") or []
                  if isinstance(m, dict) and "east" in m and "north" in m]
        # A border or a rig left at some other signal is not this one's.
        points += [p for p in extra
                   if math.hypot(p[0], p[1]) <= PV.SIGNAL_REACH_M]
        # You, for as long as this is the signal being worked - out to
        # SIGNAL_REACH_M, the same reach that decides which signal that is.
        # It used to stop at SIGNAL_AT_M, 5 km, and setting a border is
        # exactly the job that takes you past that: the scope froze at
        # 1.5 km round the centre with the Rhino pinned to the rim at
        # 5.91 km, pointing nowhere.
        if math.hypot(origin[0], origin[1]) <= PV.SIGNAL_REACH_M:
            points.append((-origin[0], -origin[1]))
        try:
            cap = float(self.settings.get("overlay_max_radius_m",
                                          DEFAULT_MAX_RADIUS_M)
                        or DEFAULT_MAX_RADIUS_M)
        except (TypeError, ValueError):
            cap = DEFAULT_MAX_RADIUS_M
        cap = min(cap, PV.SIGNAL_VIEW_CAP_M)
        floor = MIN_RADIUS_M if rows else PV.SIGNAL_VIEW_EMPTY_M
        extent = PV.extent_for(points, floor_m=floor, headroom=1.25, cap_m=cap)

        # The header and footer eat into the window, so the scope is nudged
        # down between them rather than centred on a window it does not own
        # all of.
        viewport = PV.Viewport(width, height, extent,
                               margin=max(head, foot) + 10,
                               pan=(0.0, (head - foot) / 2.0))
        plan = PV.layout(rows, viewport, heading=heading, origin=origin,
                         clip="circle")

        patch = PV.best_patch(plan["items"])
        prices = self.prices()
        # Two patches, not one. best_patch is where the most rigs are;
        # value_patch is where the most money is. They are the same answer on
        # a single-commodity body and disagree exactly when it matters.
        rich = PV.value_patch(plan["items"], prices) if prices else None
        route = PV.drive_route(plan["items"], prices)
        # Everything that is a word goes through one list of what is already
        # on the scope, so nothing prints over anything else: the header and
        # footer strips, every dot and the commander first, then the labels
        # in order of how much they matter. A label with nowhere to go is
        # left off and counted, not printed into somebody else's.
        self._scope_taken = [(0, 0, width, head), (0, height - foot, width, height)]
        self._scope_bounds = (0, head, width, height - foot)
        self._scope_hidden = 0
        self._scope_queue = []
        self._scope(viewport, plan)
        self._survey_marks(viewport, origin)
        self._rig_marks(viewport, origin)
        self._scanner(viewport, plan)
        if patch:
            self._patch(patch)
        if rich and (not patch or (rich["x"], rich["y"]) != (patch["x"], patch["y"])):
            self._rich(rich)
        self._pins(plan, route)
        if centred:
            self._centre_mark(viewport, found)
        self._commander(viewport, plan)
        self._scope_labels(plan)
        self._header(width, plan, found, centred, body, rows)
        self._footer(width, height, plan, note)
        self._brackets(width, height)

    def _rig_marks(self, viewport, origin):
        """Each rig on the scope: a small numbered square, red past the limit."""
        rigs = getattr(self, "_rigs", None)
        if not rigs:
            return
        canvas = self.canvas
        limit = float(rigs.get("limit_m") or 0)
        for mark in rigs.get("rigs") or []:
            x, y = viewport.to_canvas(mark["east"] - origin[0],
                                      mark["north"] - origin[1])
            if not (0 <= x <= viewport.width and 0 <= y <= viewport.height):
                continue
            what = str(mark.get("commodity") or "")
            tint = self.colour(what) if what else AMBER
            colour = RED if limit and mark["range_m"] > limit else tint
            canvas.create_rectangle(x - 5, y - 5, x + 5, y + 5, outline=colour,
                                    width=2, tags=("rigmark",))
            canvas.create_text(x, y, text=str(mark["n"]), fill=colour,
                               font=("Consolas", 7, "bold"), tags=("rigmark",))
            self._taken().append((x - 6, y - 6, x + 6, y + 6))
            if what:
                self._later(5, x, y, what[:8], tint, 7, 8, False,
                            ("rigmark", "rigtype"))

    def _survey_marks(self, viewport, origin):
        """The survey area on the scope: the ground already swept, the
        border, the circles still to drive, and where the gaps are.

        The swept ground is a dim fill, kept inside the border exactly as on
        the main map, so the patch not yet driven shows as the dark part of
        the circle - that is what you steer for. Everything else is lines."""
        survey = getattr(self, "_survey", None)
        if not survey:
            return
        canvas = self.canvas
        # The swept ground only means something inside a border: it is how
        # the part of the area still to drive shows up. Before there is a
        # border it was a solid teal plate over most of the scope - the
        # scanner reaches 2 km, so a few hundred metres of driving painted
        # the whole 1.5 km view - and it hid the game. Now it waits for the
        # border, and it is a see-through mesh, not a plate.
        shapes = PV.swept_shapes(survey.get("points"), survey.get("scan_m"),
                                 survey.get("centre"), survey.get("border_m"),
                                 view=(origin, viewport.extent_m)) \
            if survey.get("border_m") else []
        for shape in shapes:
            if shape[0] == "disc":
                east, north = shape[1] - origin[0], shape[2] - origin[1]
                x, y = viewport.to_canvas(east, north)
                r = viewport.radius_px(shape[3])
                canvas.create_oval(x - r, y - r, x + r, y + r, fill=SWEPT_SCOPE,
                                   outline="", stipple="gray25",
                                   tags=("swept",))
            else:
                flat = []
                for east, north in shape[1]:
                    flat.extend(viewport.to_canvas(east - origin[0],
                                                   north - origin[1]))
                canvas.create_polygon(flat, fill=SWEPT_SCOPE, outline="",
                                      stipple="gray25", tags=("swept",))
        if not survey.get("centre"):
            return
        ce, cn = survey["centre"]
        cx, cy = viewport.to_canvas(ce - origin[0], cn - origin[1])
        for ring in survey.get("rings") or []:
            r = viewport.radius_px(ring)
            canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                               outline=SCAN_RING, dash=(4, 6))
        border = survey.get("border_m")
        if border:
            r = viewport.radius_px(border)
            canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                               outline=AMBER, width=2)
        canvas.create_line(cx - 5, cy, cx + 5, cy, fill=AMBER)
        canvas.create_line(cx, cy - 5, cx, cy + 5, fill=AMBER)
        for gap in survey.get("gaps") or []:
            gx, gy = viewport.to_canvas(gap["east"] - origin[0],
                                        gap["north"] - origin[1])
            canvas.create_text(gx, gy, fill=RED, font=("Consolas", 8, "bold"),
                               text="GAP")
        done = survey.get("percent")
        if done is not None:
            canvas.create_text(viewport.width - 8, viewport.height - 44,
                               anchor="e", font=("Consolas", 9, "bold"),
                               fill=AMBER if done < 100 else CYAN,
                               text="SWEPT %d%%" % done)

    def framed(self):
        """Whether the panel being drawn wears a border.

        Off for the scope, on for the cards, and overridable - some people
        want the edges marked on a dark cockpit and some want nothing on
        screen that is not information.
        """
        key = self._drawing.key if self._drawing is not None else self.mode()
        wanted = str(self.settings.get("overlay_frame", "cards")
                     or "cards").strip().lower()
        if wanted == "none":
            return False
        if wanted == "all":
            return True
        return key not in (RADAR,)

    def prices(self):
        """What the app knows a commodity sells for, or nothing.

        Asked of the window for the same reason colour() is: overlay.py
        cannot import edsmt.py, and the app is the end that has both the
        published table and whatever the community has seen this week.
        """
        getter = getattr(self.app, "market_prices", None)
        if callable(getter):
            try:
                return getter() or {}
            except Exception:
                pass
        return {}

    def _scope(self, viewport, plan):
        """The dish: a dark disc, range rings in metres, crosshair, north."""
        canvas = self.canvas
        cx, cy = viewport.centre
        outer = viewport.radius_px(plan["extent_m"])
        # Unfilled when the scope is meant to be looked THROUGH. A filled
        # disc is a dark plate over the ground; the rings and the contacts
        # are the only things that have to be visible.
        canvas.create_oval(cx - outer, cy - outer, cx + outer, cy + outer,
                           fill=SCOPE if self.settings.get("overlay_scope_fill",
                                                           False) else "",
                           outline=RULE)
        canvas.create_line(cx, cy - outer, cx, cy + outer, fill="#241706")
        canvas.create_line(cx - outer, cy, cx + outer, cy, fill="#241706")
        for ring in plan["rings"]:
            radius = ring["radius"]
            if radius > outer + 1:
                continue
            canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                               outline="#2b1b0d", dash=(2, 5))
            # Last in line for a spot: a ring's distance is the first thing
            # to give way to a find's name.
            self._later(6, cx - 2, cy - radius + 7, format_range(ring["metres"]),
                        FAINT, 8, 2, False)
        canvas.create_text(cx, cy - outer - 8, text="N", fill=DIM,
                           font=("Consolas", 9, "bold"))

    def _scanner(self, viewport, plan):
        """The Rhino's scanner range, drawn round the VEHICLE.

        Not round the site centre. Contacts drop out of the list by distance
        from where you are, so a ring anywhere else is a ring that tells you
        a deposit is in range when it is not.
        """
        canvas = self.canvas
        me = plan["commander"]
        if me["offscreen"]:
            return
        radius = viewport.radius_px(PV.SCANNER_RANGE_M)
        if radius < 8 or radius > viewport.radius_px(plan["extent_m"]) * 4:
            return
        x, y = me["x"], me["y"]
        canvas.create_oval(x - radius, y - radius, x + radius, y + radius,
                           outline=SCAN_RING, dash=(3, 4))
        # On the ring, wherever the ring is on the scope: its top first, then
        # round it - a ring bigger than the view still gets its label on the
        # part of it you can see.
        import math as _math
        around = [(x + radius * _math.cos(_math.radians(a)),
                   y + radius * _math.sin(_math.radians(a)))
                  for a in (-60, -120, -30, -150, 0, 180, 30, 150, 60, 120)]
        self._later(4, x, y - radius + 2, "SCAN %s" % format_range(PV.SCANNER_RANGE_M),
                    CYAN, 8, 6, False, points=around)

    def _patch(self, patch):
        """Bracket the richest tight knot - the surface triple hotspot."""
        canvas = self.canvas
        x, y = patch["x"], patch["y"]
        reach = patch["radius"] + 9
        for step_x in (-1, 1):
            for step_y in (-1, 1):
                corner_x, corner_y = x + step_x * reach, y + step_y * reach
                canvas.create_line(corner_x, corner_y,
                                   corner_x - step_x * 8, corner_y, fill=AMBER)
                canvas.create_line(corner_x, corner_y,
                                   corner_x, corner_y - step_y * 8, fill=AMBER)
        self._later(2, x, y - reach + 2, "BEST PATCH  %dR" % patch["rigs"],
                    AMBER, 8, 6, True)

    def _rich(self, patch):
        """The most valuable knot, when it is not also the biggest."""
        canvas = self.canvas
        x, y, reach = patch["x"], patch["y"], patch["radius"] + 9
        canvas.create_oval(x - reach, y - reach, x + reach, y + reach,
                           outline=CYAN, dash=(2, 4))
        self._later(3, x, y + reach - 2, "BEST VALUE  %s Cr" % money(patch["credits"]),
                    CYAN, 8, 6, True)

    def _pins(self, plan, route=None):
        """Every deposit: colour by commodity, size by rigs, named.

        A worked-out deposit is drawn hollow rather than hidden. It is still
        a fact about the body, and driving to one you already stripped is
        exactly the mistake the overlay exists to stop.
        """
        canvas = self.canvas
        stops = {id(stop["item"]): stop["stop"]
                 for stop in (route or {}).get("stops", [])}
        for item in plan["items"]:
            colour = self.colour(item["commodity"])
            deposit = item["deposit"] or {}
            spent = str(deposit.get("amount") or "").strip().lower() == "depleted"
            if item["offscreen"]:
                x, y = item["edge"]
                canvas.create_polygon(
                    PV.arrow_points(x, y, item["view_bearing"], 9),
                    fill="" if spent else colour, outline=colour)
                canvas.create_text(x, y + 13, fill=colour, font=("Consolas", 8),
                                   text=format_range(item["range_m"]))
                continue
            radius, x, y = item["radius"], item["x"], item["y"]
            dot(canvas, x, y, radius, "" if spent else colour, colour,
                shared=bool(deposit.get("shared")))
            # The order to drive them in, on the dot. Without it you stop at
            # every one to work out which is nearest; with it the route is
            # just a number to follow.
            stop = (stops or {}).get(id(item))
            if stop:
                canvas.create_text(x, y, fill=VOID if not spent else colour,
                                   font=("Consolas", 8, "bold"), text=str(stop))
            self._taken().append((x - radius - 1, y - radius - 1,
                                  x + radius + 1, y + radius + 1))

    def _taken(self):
        taken = getattr(self, "_scope_taken", None)
        if not isinstance(taken, list):
            taken = self._scope_taken = []
        return taken

    def _put(self, x, y, text, colour, size=9, gap=8, bold=True, tags=(),
             points=None, find=False):
        """One label beside (x, y) - or beside the first of `points` that
        has room - where it touches nothing. False if it had nowhere to go
        and was left off. Only a find's name left off is counted: "2
        unlabelled" under two named finds meant a ring distance and the
        scanner's label, and read as two finds nobody could see."""
        box = None
        measure = lambda t, z: self._measure(t, z, bold)  # noqa: E731
        for px, py in ([(x, y)] + list(points or [])):
            box = free_spot(px, py, text, size, gap, self._taken(),
                            getattr(self, "_scope_bounds", None), measure)
            if box is not None:
                break
        if box is None:
            if find:
                self._scope_hidden = getattr(self, "_scope_hidden", 0) + 1
            return False
        self._taken().append(box)
        self.canvas.create_text(box[0], box[1], anchor="nw", text=text,
                                fill=colour, tags=tags,
                                font=("Consolas", size, "bold" if bold else "normal"))
        return True

    def _measure(self, text, size, bold=True):
        """(width, height) of `text` in the font it will be drawn in.

        From Tk's own font metrics when there is a real canvas - Consolas is
        not on every machine, and whatever stands in for it is wider - and
        from the character-width table when there is not.
        """
        fonts = getattr(self, "_fonts", None)
        if not isinstance(fonts, dict):
            fonts = self._fonts = {}
        key = (int(size), bool(bold))
        font = fonts.get(key)
        if font is None and key not in fonts:
            try:
                import tkinter.font as tkfont
                font = tkfont.Font(root=self.canvas, family="Consolas",
                                   size=int(size),
                                   weight="bold" if bold else "normal")
                font.measure("M")
            except Exception:
                font = None
            fonts[key] = font
        if font is not None:
            try:
                return float(font.measure(str(text))), \
                    float(font.metrics("linespace"))
            except Exception:
                pass
        return text_box(text, size)

    def _later(self, rank, x, y, text, colour, size, gap, bold, tags=(),
               points=None):
        """Queue a label to be placed once every mark is on the scope."""
        queue = getattr(self, "_scope_queue", None)
        if not isinstance(queue, list):
            queue = self._scope_queue = []
        queue.append((rank, len(queue), x, y, text, colour, size, gap, bold,
                      tags, tuple(points or ())))

    def _scope_labels(self, plan):
        """Every word on the scope, in order of how much it matters.

        The signal's own name, then the finds nearest first - the one you
        are driving to is the one that must never be left off - then the
        best patch, the best value, the scanner ring and the rigs' types.
        """
        queue = sorted(getattr(self, "_scope_queue", None) or [])
        self._scope_queue = []
        first = [entry for entry in queue if entry[0] == 0]
        rest = [entry for entry in queue if entry[0] != 0]
        for _rank, _order, x, y, text, colour, size, gap, bold, tags, points in first:
            self._put(x, y, text, colour, size=size, gap=gap, bold=bold, tags=tags,
                      points=points)
        items = [i for i in plan["items"] if not i["offscreen"]]
        items.sort(key=lambda i: float(i.get("range_m") or 0))
        self._name_finds(items)
        for _rank, _order, x, y, text, colour, size, gap, bold, tags, points in rest:
            self._put(x, y, text, colour, size=size, gap=gap, bold=bold, tags=tags,
                      points=points)

    def _name_finds(self, items):
        for item in items:
            deposit = item["deposit"] or {}
            spent = str(deposit.get("amount") or "").strip().lower() == "depleted"
            label = item["commodity"][:16] or "deposit"
            rigs = str(deposit.get("rigs") or "").strip()
            if rigs:
                label += " (%sR)" % rigs
            colour = FAINT if spent else self.colour(item["commodity"])
            self._put(item["x"], item["y"], label, colour, size=9,
                      gap=item["radius"] + 4, find=True)

    def _centre_mark(self, viewport, found):
        """The mining location signal the scope is centred on."""
        canvas = self.canvas
        cx, cy = viewport.centre
        canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill=RED, outline=VOID)
        self._taken().append((cx - 5, cy - 5, cx + 5, cy + 5))
        self._later(0, cx, cy, found.get("label") or "SITE", RED, 8, 7, True)

    def _commander(self, viewport, plan):
        """You.

        On the scope while you are on it. Off it - drive far enough and you
        will be - a chevron on the rim points back at where you really are,
        with the range, so the picture never silently stops including you.
        """
        canvas = self.canvas
        me = plan["commander"]
        if me["offscreen"]:
            # On the rim, in the direction you are - but pointing the way
            # the Rhino is pointing. It used to point along the bearing from
            # the centre, so it never turned when the Rhino did.
            x, y = me["edge"]
            canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill=AMBER,
                               outline="")
            canvas.create_polygon(PV.arrow_points(x, y, plan["heading"], 11),
                                  fill=AMBER, outline=VOID)
            canvas.create_text(x, y + 14, fill=AMBER,
                               font=("Consolas", 8, "bold"),
                               text=format_range(me["view_range_m"]))
            return
        canvas.create_polygon(
            PV.arrow_points(me["x"], me["y"], plan["heading"], 11),
            fill=AMBER, outline=VOID)
        self._taken().append((me["x"] - 12, me["y"] - 12, me["x"] + 12, me["y"] + 12))

    def _body_of(self, rows):
        """The body name, taken off the finds when the app did not say."""
        for row in rows:
            name = str((row.get("deposit") or {}).get("body") or "").strip()
            if name:
                return name
        return ""

    def _header(self, width, plan, found, centred, body, rows):
        canvas = self.canvas
        radius = "MAP RADIUS  %s" % format_range(plan["extent_m"])
        room = width - 16 - self._measure(radius, 10)[0] - 12
        name = "BODY  %s" % (body or self._body_of(rows) or "-")
        # Cut to the room there is, in the font it is drawn in, so a long
        # body name stops short of the radius instead of running under it.
        while len(name) > 6 and self._measure(name, 10)[0] > room:
            name = name[:-2] + "~"
        canvas.create_text(8, 11, anchor="w", fill=TEXT,
                           font=("Consolas", 10, "bold"), text=name)
        canvas.create_text(width - 8, 11, anchor="e", fill=AMBER,
                           font=("Consolas", 10, "bold"), text=radius)
        count = "%d DEP  %dR" % (len(plan["items"]), PV.total_rigs(plan["items"]))
        centre = "CENTRE  %s" % ((found.get("label") or "SITE")
                                 if centred else "SRV")
        far = getattr(self, "_far", None)
        if far:
            # The box names a signal you are not at: say where it is, so a
            # stale box is seen at a glance rather than trusted.
            centre = "CENTRE  SRV   SIGNAL %s  %s %s" % (
                far["signal"], format_range(far["range_m"]),
                PV.compass_point(far["bearing"]))
        room = width - 16 - self._measure(count, 9)[0] - 12
        while len(centre) > 8 and self._measure(centre, 9)[0] > room:
            centre = centre[:-2] + "~"
        canvas.create_text(8, 26, anchor="w", fill=AMBER if far else DIM,
                           font=("Consolas", 9), text=centre)
        canvas.create_text(width - 8, 26, anchor="e", fill=DIM,
                           font=("Consolas", 9), text=count)
        canvas.create_line(0, 34, width, 34, fill=RULE)

    def _footer(self, width, height, plan, note):
        """Where to go next, and how to record it without alt-tabbing."""
        canvas = self.canvas
        canvas.create_line(0, height - 26, width, height - 26, fill=RULE)
        # Left to right, each only if it fits beside what is already there:
        # where to go next, what the patch is worth, the keys. Squeezed, the
        # keys go first - the GUIDE and STATUS boxes carry them too.
        used = 8.0
        wanted = getattr(self, "_target_id", None)
        chosen = [item for item in plan["items"] if wanted
                  and str((item.get("deposit") or {}).get("id") or "") == wanted]
        target = chosen[0] if chosen else PV.next_target(plan["items"])
        if target is not None:
            offset = relative_bearing(plan["heading"], target["bearing"])
            text = fit_text("%s %s %s %s %03d" % (
                "GO" if chosen else "NEXT",
                turn_arrow(offset), target["commodity"][:13] or "deposit",
                format_range(target["range_m"]),
                int(round(target["bearing"])) % 360), width - 16, 10)
            canvas.create_text(8, height - 13, anchor="w",
                               fill=self.colour(target["commodity"]),
                               font=("Consolas", 10, "bold"), text=text)
            used += text_box(text, 10)[0]
        elif note:
            text = fit_text(note, width - 16, 9)
            canvas.create_text(8, height - 13, anchor="w", fill=DIM,
                               font=("Consolas", 9), text=text)
            used += text_box(text, 9)[0]
        worth = PV.value_of(plan["items"], self.prices())
        if worth["credits"]:
            text = "~%s Cr" % money(worth["credits"])
            if used + 14 + text_box(text, 9)[0] <= width - 8:
                canvas.create_text(used + 14, height - 13, anchor="w", fill=AMBER,
                                   font=("Consolas", 9, "bold"), text=text)
                used += 14 + text_box(text, 9)[0]
        hint = self.key_hint()
        if hint and used + 14 + text_box(hint, 9)[0] <= width - 8:
            canvas.create_text(width - 8, height - 13, anchor="e", fill=FAINT,
                               font=("Consolas", 9), text=hint)
        hidden = getattr(self, "_scope_hidden", 0)
        if hidden:
            # Bottom left, clear of the survey readout on the right.
            canvas.create_text(8, height - 34, anchor="w", fill=FAINT,
                               font=("Consolas", 8),
                               text="%d unlabelled" % hidden)

    def _rig_banner(self, width, height):
        """TOO FAR FROM RIG n, across the foot of the box, naming the rig
        that is farthest. Red whatever the theme: it is the one thing on the
        HUD that is a warning."""
        rigs = getattr(self, "_rigs", None)
        if not (rigs and rigs.get("far")):
            return
        canvas = self.canvas
        tall = 20 if height >= 60 else 16
        canvas.create_rectangle(2, height - tall - 2, width - 2, height - 2,
                                fill=RED, outline=RED, tags=("rigs",))
        canvas.create_text(width / 2.0, height - 2 - tall / 2.0, fill="#ffffff",
                           font=("Consolas", 10 if tall == 20 else 8, "bold"),
                           tags=("rigs",),
                           text="TOO FAR FROM RIG %s  %s %s" % (
                               rigs.get("n", ""),
                               turn_arrow(float(rigs.get("offset") or 0)),
                               format_range(rigs.get("range_m"))))

    def _brackets(self, width, height):
        """The panel shell, and the clock.

        A rounded frame rather than four corner brackets: the brackets were
        the only thing marking the edges of a window that is otherwise mostly
        hole, and at a glance four disconnected right angles read as four
        things rather than one panel.

        The clock is the concept's, and it is not decoration. It is how you
        tell at a glance that the overlay is still being fed - a frozen HUD
        and a working one look identical until something on it moves.
        """
        canvas = self.canvas
        # THE SCOPE GETS NO FRAME. It is a hole you look through at the
        # ground, and a bright rounded box round it is a bright rounded box
        # sitting in the middle of the cockpit whether or not you are
        # looking at it. Everything else is a card and reads better framed.
        if self.framed():
            rounded_frame(canvas, width, height, ORANGE)
