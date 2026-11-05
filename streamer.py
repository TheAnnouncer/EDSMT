"""
Streamer mode (1.10040, #312): what a stream can see of where you are.

While it is on, the system and body names on everything a stream shows -
the overlay boxes, the map's title, the status line, the readouts at the
top of the window - read "a system N Ly from Sol" and "a body" until the
commander has been in that system for the delay. Then the real names. The
distance is rounded to tens of light years, so it says roughly how far out
and not which star.

The commander's own Discord posts wait the same delay in a DelayQueue. It
lives in memory and nowhere else: a restart drops it, and the app says so.
Finds still go to the community map at once - the map is not the stream.

Bigger text is each overlay box's text two steps up the sizes it offers.

Plain logic, no Tk, so all of it is checked without a display.
"""

import re

DELAYS_MIN = (0, 5, 10, 15, 30)
DEFAULT_DELAY_MIN = 15
BIG_TEXT_STEPS = 2
# Distances are told to the nearest this many light years.
LY_STEP = 10


def delay_minutes(value):
    """The delay as saved - a number, or text from the Settings choice - in
    whole minutes; one of DELAYS_MIN, else the default."""
    try:
        minutes = int(float(value))
    except (TypeError, ValueError):
        return DEFAULT_DELAY_MIN
    return minutes if minutes in DELAYS_MIN else DEFAULT_DELAY_MIN


def cover(kind, ly=None):
    """What stands in for a name: "a body", or "a system N Ly from Sol"
    ("a system near Sol" close in, "a system" with no position known)."""
    if kind != "system":
        return "a body"
    try:
        ly = float(ly)
    except (TypeError, ValueError):
        return "a system"
    rounded = int(round(abs(ly) / LY_STEP)) * LY_STEP
    if rounded <= 0:
        return "a system near Sol"
    return "a system {:,} Ly from Sol".format(rounded)


def visible_name(name, kind, arrived_at, now, delay, ly=None):
    """`name` as the stream may see it. `kind` is "system" or "body" (a
    body goes with its system), `arrived_at` when the commander arrived in
    the system - None if not known - and `delay` in seconds. The real name
    once the delay has passed since arriving, and at once with no delay;
    cover(kind, ly) until then. Not knowing when you arrived is not knowing
    that it is safe to show, so that is hidden too."""
    if not name:
        return name
    try:
        delay = float(delay or 0)
    except (TypeError, ValueError):
        delay = 0.0
    if delay <= 0:
        return name
    if arrived_at is not None and float(now) - float(arrived_at) >= delay:
        return name
    return cover(kind, ly)


def hide(text, names):
    """`text` with each (real, shown) pair in `names` swapped, whatever the
    case it is written in. Give the body before its system: a body's name
    usually holds its system's."""
    text = str(text)
    for real, shown in names or ():
        if real:
            text = re.sub(re.escape(str(real)), lambda _m, s=str(shown): s, text,
                          flags=re.IGNORECASE)
    return text


def step_up(percent, sizes, steps=BIG_TEXT_STEPS):
    """The text size `steps` places up `sizes` from `percent` (or from the
    size nearest it), never past the largest."""
    sizes = sorted(sizes)
    try:
        percent = float(percent)
    except (TypeError, ValueError):
        percent = 100.0
    nearest = min(range(len(sizes)), key=lambda i: abs(sizes[i] - percent))
    return sizes[min(len(sizes) - 1, nearest + int(steps))]


class DelayQueue:
    """Things held back until a delay has passed since each was put in.
    Memory only: a restart drops what is waiting."""

    def __init__(self):
        self._items = []

    def __len__(self):
        return len(self._items)

    def put(self, item, now):
        self._items.append((float(now), item))

    def due(self, now, delay):
        """Take out and hand back, oldest first, what has waited `delay`
        seconds by `now`."""
        ready = [item for at, item in self._items if float(now) - at >= float(delay)]
        self._items = [(at, item) for at, item in self._items
                       if float(now) - at < float(delay)]
        return ready

    def drain(self):
        """Everything, oldest first, at once."""
        ready = [item for _at, item in self._items]
        self._items = []
        return ready


def from_sol(position):
    """Light years from Sol of a star position (x, y, z), or None."""
    try:
        x, y, z = (float(v) for v in position)
    except (TypeError, ValueError):
        return None
    return (x * x + y * y + z * z) ** 0.5
