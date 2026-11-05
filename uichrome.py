"""The main window's chrome, worked out without a window (1.10040, #310).

- The status strip under the top bar: CMDR, SHIP, SYSTEM, BODY, what the
  commander is in and the overlay - the facts the app already has, one line,
  with the long ones shortened to fit (fit_cells).
- Spacing: Comfortable or Compact, every padding and row height the chrome
  uses from one table (spacing).
- The theme arrows: the next theme, or the one before, round all of them.
- The shortcut bar's line: the F-keys and the rig keys, as many whole items
  as fit.

The window measures text with its own font and hands the measure in, so
everything here is plain arithmetic.
"""
from collections import namedtuple

# The game's ship symbols, lower-cased, and the names on the ship.
SHIP_NAMES = {
    "adder": "Adder", "anaconda": "Anaconda", "asp": "Asp Explorer",
    "asp_scout": "Asp Scout", "belugaliner": "Beluga Liner",
    "cobramkiii": "Cobra Mk III", "cobramkiv": "Cobra Mk IV",
    "cobramkv": "Cobra Mk V", "corsair": "Corsair",
    "cutter": "Imperial Cutter", "diamondback": "Diamondback Scout",
    "diamondbackxl": "Diamondback Explorer", "dolphin": "Dolphin",
    "eagle": "Eagle", "empire_courier": "Imperial Courier",
    "empire_eagle": "Imperial Eagle", "empire_trader": "Imperial Clipper",
    "federation_corvette": "Federal Corvette",
    "federation_dropship": "Federal Dropship",
    "federation_dropship_mkii": "Federal Assault Ship",
    "federation_gunship": "Federal Gunship", "ferdelance": "Fer-de-Lance",
    "hauler": "Hauler", "independant_trader": "Keelback",
    "krait_light": "Krait Phantom", "krait_mkii": "Krait Mk II",
    "mamba": "Mamba", "mandalay": "Mandalay", "orca": "Orca",
    "panthermkii": "Panther Clipper Mk II", "python": "Python",
    "python_nx": "Python Mk II", "sidewinder": "Sidewinder",
    "type6": "Type-6 Transporter", "type7": "Type-7 Transporter",
    "type8": "Type-8 Transporter", "type9": "Type-9 Heavy",
    "type9_military": "Type-10 Defender", "typex": "Alliance Chieftain",
    "typex_2": "Alliance Crusader", "typex_3": "Alliance Challenger",
    "viper": "Viper Mk III", "viper_mkiv": "Viper Mk IV", "vulture": "Vulture",
}
NONE = "-"
STATUS_LABELS = ("CMDR", "SHIP", "SYSTEM", "BODY", "STATE", "OVERLAY")
# Never shortened: short already, and the ones read at a glance.
KEEP_WHOLE = ("CMDR", "STATE", "OVERLAY")
DOTS = "..."

# Every padding and row height the chrome takes from the spacing, in pixels
# before the screen's scaling. Comfortable is the window as it always was.
SPACING_ORDER = ("comfortable", "compact")
SPACING_NAMES = {"comfortable": "Comfortable", "compact": "Compact"}
_SPACING = {
    "comfortable": {"bar_pady": 8, "button_h": 32, "tab_h": 32, "strip_h": 26,
                    "line_pady": 6, "cell_pady": 2, "keys_pady": 4},
    "compact": {"bar_pady": 3, "button_h": 26, "tab_h": 24, "strip_h": 20,
                "line_pady": 2, "cell_pady": 0, "keys_pady": 1},
}

# Between two items on the shortcut line.
SEPARATOR = "   "

Cell = namedtuple("Cell", "label value x0 value_x x1")


def ship_name(symbol):
    """A ship's name from the journal's symbol ("type9" is the Type-9 Heavy);
    one this does not know, as the journal gives it."""
    text = str(symbol or "").strip()
    return SHIP_NAMES.get(text.lower(), text)


def _state_words(state):
    if getattr(state, "docked", False):
        return "DOCKED"
    if getattr(state, "in_srv", False):
        return "IN SRV"
    if getattr(state, "on_foot", False):
        return "ON FOOT"
    if getattr(state, "landed", False):
        return "LANDED"
    return "IN FLIGHT"


def status_cells(state, overlay_on, overlay_locked):
    """[(label, value)] for the status strip, in STATUS_LABELS order. A dash
    for anything the game has not said - and for all of it with the game
    shut."""
    running = bool(getattr(state, "running", False)) if state is not None else False

    def said(name):
        text = str(getattr(state, name, "") or "").strip() if running else ""
        return text or NONE

    ship = ship_name(getattr(state, "ship_type", "")) if running else ""
    overlay = ("ON" if overlay_locked else "UNLOCKED") if overlay_on else "OFF"
    return [("CMDR", said("cmdr")), ("SHIP", ship or NONE),
            ("SYSTEM", said("system")), ("BODY", said("body")),
            ("STATE", _state_words(state) if running else NONE),
            ("OVERLAY", overlay)]


def _shorten(text, room, measure):
    """`text` cut to `room` pixels, with dots where it was cut."""
    if measure(text) <= room:
        return text
    cut = len(text)
    while cut > 1 and measure(text[:cut] + DOTS) > room:
        cut -= 1
    return text[:cut].rstrip() + DOTS


def fit_cells(cells, width, measure, glyph=16, gap=6, between=20):
    """Lay the strip's cells out left to right in `width` pixels: a glyph,
    the label, the value. Where they do not all fit, the long values are cut
    to an even share of what room there is and end in dots; CMDR, STATE and
    OVERLAY are kept whole. [Cell(label, value, x0, value_x, x1)]."""
    fixed = sum(glyph + measure(label) + 2 * gap for label, _v in cells)
    fixed += between * max(0, len(cells) - 1)
    whole = [measure(value) for _l, value in cells]
    room = width - fixed - sum(w for (label, _v), w in zip(cells, whole) if label in KEEP_WHOLE)
    long = [(index, w) for index, ((label, _v), w) in enumerate(zip(cells, whole))
            if label not in KEEP_WHOLE]
    cap = None
    if sum(w for _i, w in long) > room:
        # The most each long value may take: those under it keep their
        # whole width, and what they leave goes to the rest.
        left, count = max(0, room), len(long)
        for _index, w in sorted(long, key=lambda pair: pair[1]):
            if w * count <= left:
                left -= w
                count -= 1
            else:
                break
        cap = left / float(max(1, count))
    out, x = [], 0
    for (label, value), w in zip(cells, whole):
        if cap is not None and label not in KEEP_WHOLE and w > cap:
            value = _shorten(value, cap, measure)
        start = x
        value_x = start + glyph + gap + measure(label) + gap
        x = value_x + measure(value)
        out.append(Cell(label, value, start, value_x, x))
        x += between
    return out


def spacing(name):
    """The paddings and row heights for one spacing - a copy, so nothing
    that uses it can change the table. Anything unknown is Comfortable."""
    key = str(name or "").strip().lower()
    return dict(_SPACING.get(key, _SPACING["comfortable"]))


def next_theme(order, current, step):
    """The theme `step` along from `current` in `order`, round from the end
    to the start and back. One it does not know starts at the first."""
    order = list(order)
    if not order:
        return current
    if current not in order:
        return order[0]
    return order[(order.index(current) + step) % len(order)]


def shortcut_items(tabs, rig_words):
    """The shortcut bar's items: an F-key for every tab, then the rig keys
    when any are bound."""
    items = ["%s %s" % (fkey, label) for _key, label, fkey in tabs]
    if rig_words:
        items.append("%s rig down" % rig_words)
    return items


def fit_line(items, width, measure):
    """As many whole items from the start as fit in `width` pixels."""
    line = ""
    for item in items:
        longer = item if not line else line + SEPARATOR + item
        if measure(longer) > width:
            break
        line = longer
    return line
