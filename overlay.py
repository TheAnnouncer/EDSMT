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
    "GLASS": "#081311",
}
THEMES = {
    # The Radio Raxxla cockpit. What the app has always been.
    "cockpit": {},
    # The concept screenshot: cyan on near-black, everything cool.
    "signal": {
        "VOID": "#03100f", "SCOPE": "#04120f", "RULE": "#1d4f4a",
        "ORANGE": "#4fe3d0", "AMBER": "#7ff2e2", "TEXT": "#cfeeea",
        "DIM": "#5fa39b", "FAINT": "#3d716c", "CYAN": "#4fe3d0",
        "SCAN_RING": "#1d5f58", "GLASS": "#04120f",
    },
    # Frontier's own orange, harder and less amber than the cockpit.
    "elite": {
        "ORANGE": "#ff7100", "AMBER": "#ffa030", "TEXT": "#ffdcb0",
        "DIM": "#b07028", "FAINT": "#7a4a18", "RULE": "#4a2a06",
    },
    # For a bright room, or a monitor that eats dark reds.
    "ice": {
        "VOID": "#05080d", "SCOPE": "#060a10", "RULE": "#20364f",
        "ORANGE": "#79b8ff", "AMBER": "#a8d4ff", "TEXT": "#dbe8f7",
        "DIM": "#6c8aab", "FAINT": "#47617d", "CYAN": "#79ffe1",
        "SCAN_RING": "#24506b", "GLASS": "#060a10",
    },
    # Green phosphor. Somebody always wants it.
    "phosphor": {
        "VOID": "#040a04", "SCOPE": "#050d05", "RULE": "#1e4a1e",
        "ORANGE": "#5cff8f", "AMBER": "#9dffbc", "TEXT": "#d2ffdd",
        "DIM": "#5aa46e", "FAINT": "#3a6b48", "CYAN": "#5cffd6",
        "SCAN_RING": "#1f5a3a", "GLASS": "#050d05",
    },
}
THEME_NAMES = {"cockpit": "Radio Raxxla cockpit", "signal": "Signal (the concept)",
               "elite": "Elite orange", "ice": "Ice blue", "phosphor": "Green phosphor"}


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
    palette.update(THEMES.get(str(name or "cockpit").strip().lower(), {}))
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
PANEL_ORDER = (STRIP, RADAR, TARGETS, STATUS, DEPOSIT)
PANEL_TITLE = {STRIP: "COMPASS", RADAR: "SCOPE",
               TARGETS: "TARGETS", STATUS: "STATUS",
               DEPOSIT: "MINERAL DEPOSIT"}
PANEL_WHAT = {
    STRIP: "the compass tape - which way to turn",
    RADAR: "the scope - the patch from above",
    TARGETS: "the nearest finds, in order",
    STATUS: "body, count, and what is next",
    DEPOSIT: "one card: the deposit you are on, and a signal radar",
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
DEFAULT_LAYOUT = {
    STRIP:   {"x": 0.225, "y": 0.030, "w": 0.550, "h": 0.078},
    RADAR:   {"x": 0.020, "y": 0.060, "w": 0.220, "h": 0.390},
    TARGETS: {"x": 0.798, "y": 0.300, "w": 0.185, "h": 0.300},
    STATUS:  {"x": 0.355, "y": 0.905, "w": 0.290, "h": 0.058},
    DEPOSIT: {"x": 0.300, "y": 0.640, "w": 0.400, "h": 0.230},
}

# Below these a panel has nothing left to say, so a slip of the mouse on the
# resize grip cannot turn one into a sliver you then cannot grab again.
MIN_PANEL = {STRIP: (260, 74), RADAR: (200, 200),
             TARGETS: (180, 96), STATUS: (220, 48),
             DEPOSIT: (420, 170)}

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
        if self.window is not None:
            try:
                self.remember()
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
            screen_w, screen_h = self.overlay.screen(self.window)
            spec = panel_fractions(self.window.winfo_width(),
                                   self.window.winfo_height(),
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
        chosen = [key for key in PANEL_ORDER
                  if self.settings.get("overlay_show_%s" % key)]
        return chosen or [self.mode()]

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

    def hide(self):
        for panel in list(self.panels.values()):
            panel.close()
        if self.panels:
            self.save_layout()
        self.panels = {}
        if self.window is not None:
            try:
                self.remember_position()
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
             survey=None, rigs=None):
        """Redraw. Called from the same poll that moves the map.

        `rows` are Survey.near rows, measured from the commander. The three
        optional arguments are what the app knows and the rows do not:
        `body` the body name for the header, `location` which mining signal
        to centre on, and `site` that signal's own position as (east, north)
        metres from the commander. All three are optional on purpose - with
        none of them the radar works out the site centre from the deposits
        themselves, which is one fewer thing a commander has to place.
        """
        # The survey area, if one is set: drawn by the scope and summed up
        # by STATUS. Kept rather than threaded through every draw call.
        self._survey = survey if isinstance(survey, dict) else None
        # Where the rigs are from here. When "far" is set, every box carries
        # the warning - whichever boxes a commander has on, they see it.
        self._rigs = rigs if isinstance(rigs, dict) else None
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

        if note:
            canvas.create_text(6, height - 8, text=note, fill=dim, anchor="sw",
                               font=("Consolas", 9))
        if not self.locked:
            canvas.create_text(width - 6, height - 8, text=self.key_hint(),
                               fill=dim, anchor="se", font=("Consolas", 9))

    # -- the two list panels ---------------------------------------------

    def ranked(self, rows, heading, limit=12):
        """The finds, nearest first, with the turn worked out.

        Worked-out deposits sort after live ones rather than disappearing:
        knowing a patch is stripped is worth knowing, and driving back to
        one you already mined is the mistake this tool exists to stop.
        """
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
            })
        ranked.sort(key=lambda item: (item["spent"], item["range_m"]))
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
                               text="NEXT %s %s %s" % (
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
        self._brackets(width, height)

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
        nearest = self.ranked(rows, heading, limit=1)
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
        return "%s SITE  %s %s" % (
            str(self.settings.get("hotkey_location", "F9") or "F9"),
            str(self.settings.get("hotkey_deposit", "F10") or "F10"),
            "DEP" if short else "DEPOSIT")

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

        # Auto-zoom: wide enough to hold every deposit AND the commander, so
        # driving away from the site widens the picture instead of leaving
        # you on an empty scope wondering which way is back.
        points = [(east - origin[0], north - origin[1])
                  for east, north in (PV.to_offset(row.get("range_m"),
                                                   row.get("bearing"))
                                      for row in rows)]
        points.append((-origin[0], -origin[1]))
        try:
            cap = float(self.settings.get("overlay_max_radius_m",
                                          DEFAULT_MAX_RADIUS_M)
                        or DEFAULT_MAX_RADIUS_M)
        except (TypeError, ValueError):
            cap = DEFAULT_MAX_RADIUS_M
        extent = PV.extent_for(points, floor_m=MIN_RADIUS_M, headroom=1.25,
                               cap_m=cap)

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
            colour = RED if limit and mark["range_m"] > limit else AMBER
            canvas.create_rectangle(x - 5, y - 5, x + 5, y + 5, outline=colour,
                                    tags=("rigmark",))
            canvas.create_text(x, y, text=str(mark["n"]), fill=colour,
                               font=("Consolas", 7, "bold"), tags=("rigmark",))

    def _survey_marks(self, viewport, origin):
        """The survey area on the scope: the border, the circles still to
        drive, and where the gaps are - all as lines, never filled, so the
        scope stays something you look THROUGH. The swept ground itself is
        on the main map; here it is summed up as a percentage."""
        survey = getattr(self, "_survey", None)
        if not survey or not survey.get("centre"):
            return
        canvas = self.canvas
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
            canvas.create_text(cx + 4, cy - radius + 8, anchor="w", fill=FAINT,
                               font=("Consolas", 8),
                               text=format_range(ring["metres"]))
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
        canvas.create_text(x, y - radius - 7, fill=CYAN, font=("Consolas", 8),
                           text="SCAN %s" % format_range(PV.SCANNER_RANGE_M))

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
        canvas.create_text(x, y - reach - 7, fill=AMBER,
                           font=("Consolas", 8, "bold"),
                           text="BEST PATCH  %dR" % patch["rigs"])

    def _rich(self, patch):
        """The most valuable knot, when it is not also the biggest."""
        canvas = self.canvas
        x, y, reach = patch["x"], patch["y"], patch["radius"] + 9
        canvas.create_oval(x - reach, y - reach, x + reach, y + reach,
                           outline=CYAN, dash=(2, 4))
        canvas.create_text(x, y + reach + 8, fill=CYAN,
                           font=("Consolas", 8, "bold"),
                           text="BEST VALUE  %s Cr" % money(patch["credits"]))

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
            label = item["commodity"][:16] or "deposit"
            rigs = str(deposit.get("rigs") or "").strip()
            if rigs:
                label += " (%sR)" % rigs
            canvas.create_text(x + radius + 5, y, text=label, anchor="w",
                               fill=FAINT if spent else colour,
                               font=("Consolas", 9, "bold"))

    def _centre_mark(self, viewport, found):
        """The mining location signal the scope is centred on."""
        canvas = self.canvas
        cx, cy = viewport.centre
        canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill=RED, outline=VOID)
        canvas.create_text(cx + 8, cy - 9, anchor="w", fill=RED,
                           font=("Consolas", 8, "bold"),
                           text=found.get("label") or "SITE")

    def _commander(self, viewport, plan):
        """You.

        On the scope while you are on it. Off it - drive far enough and you
        will be - a chevron on the rim points back at where you really are,
        with the range, so the picture never silently stops including you.
        """
        canvas = self.canvas
        me = plan["commander"]
        if me["offscreen"]:
            x, y = me["edge"]
            canvas.create_polygon(PV.arrow_points(x, y, me["view_bearing"], 11),
                                  fill=AMBER, outline=VOID)
            canvas.create_text(x, y + 14, fill=AMBER,
                               font=("Consolas", 8, "bold"),
                               text=format_range(me["view_range_m"]))
            return
        canvas.create_polygon(
            PV.arrow_points(me["x"], me["y"], plan["heading"], 11),
            fill=AMBER, outline=VOID)

    def _body_of(self, rows):
        """The body name, taken off the finds when the app did not say."""
        for row in rows:
            name = str((row.get("deposit") or {}).get("body") or "").strip()
            if name:
                return name
        return ""

    def _header(self, width, plan, found, centred, body, rows):
        canvas = self.canvas
        canvas.create_text(8, 11, anchor="w", fill=TEXT,
                           font=("Consolas", 10, "bold"),
                           text="BODY  %s" % (body or self._body_of(rows) or "-"))
        canvas.create_text(width - 8, 11, anchor="e", fill=AMBER,
                           font=("Consolas", 10, "bold"),
                           text="MAP RADIUS  %s" % format_range(plan["extent_m"]))
        canvas.create_text(8, 26, anchor="w", fill=DIM, font=("Consolas", 9),
                           text="CENTRE  %s" % ((found.get("label") or "SITE")
                                                if centred else "SRV"))
        canvas.create_text(width - 8, 26, anchor="e", fill=DIM,
                           font=("Consolas", 9),
                           text="%d DEP  %dR" % (len(plan["items"]),
                                                 PV.total_rigs(plan["items"])))
        canvas.create_line(0, 34, width, 34, fill=RULE)

    def _footer(self, width, height, plan, note):
        """Where to go next, and how to record it without alt-tabbing."""
        canvas = self.canvas
        canvas.create_line(0, height - 26, width, height - 26, fill=RULE)
        worth = PV.value_of(plan["items"], self.prices())
        if worth["credits"]:
            canvas.create_text(width / 2.0, height - 13, fill=AMBER,
                               font=("Consolas", 9, "bold"),
                               text="~%s Cr" % money(worth["credits"]))
        target = PV.next_target(plan["items"])
        if target is not None:
            offset = relative_bearing(plan["heading"], target["bearing"])
            canvas.create_text(8, height - 13, anchor="w",
                               fill=self.colour(target["commodity"]),
                               font=("Consolas", 10, "bold"),
                               text="NEXT %s %s %s %03d" % (
                                   turn_arrow(offset),
                                   target["commodity"][:13] or "deposit",
                                   format_range(target["range_m"]),
                                   int(round(target["bearing"])) % 360))
        elif note:
            canvas.create_text(8, height - 13, anchor="w", fill=DIM,
                               font=("Consolas", 9), text=note[:44])
        canvas.create_text(width - 8, height - 13, anchor="e", fill=FAINT,
                           font=("Consolas", 9), text=self.key_hint())

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
