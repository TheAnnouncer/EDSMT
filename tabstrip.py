"""The main window's tool tabs as a strip of chevrons (1.10040, #310).

Pure geometry, no toolkit: where each tab goes for a given width, and which
tab a click lands on. The window draws the polygons on a canvas and asks
hit() where a click went.

Each tab is a chevron: a point on its right, and - after the first - a notch
on its left that the tab before it points into, a seam apart. A tab is as
wide as its words, so Where to land is wider than Map. Short of room, the
F-keys come off the tabs first, then the padding narrows; a tab is never
dropped.
"""
from collections import namedtuple

# (key, label, the key that opens it)
TABS = (("map", "Map", "F2"), ("find", "Find", "F3"), ("sites", "My sites", "F4"),
        ("land", "Where to land", "F5"), ("earnings", "Earnings", "F6"),
        ("powerplay", "Powerplay", "F7"), ("leaderboard", "Leaderboard", "F8"))
# How far a point sticks out, the seam between two tabs, and the padding
# either side of the words - roomy and as tight as it goes. Pixels.
POINT = 12
GAP = 3
PAD = 14
PAD_LEAST = 5
# Between a tab's name and its F-key.
KEY_SPACE = "  "

Tab = namedtuple("Tab", "key label fkey x0 x1 points text_x key_x keys_shown")


def _widths(tabs, measure, keys, pad):
    out = []
    for index, (_key, label, fkey) in enumerate(tabs):
        words = measure(label) + (measure(KEY_SPACE + fkey) if keys else 0)
        out.append((POINT if index else 0) + 2 * pad + words)
    return out


def _span(widths):
    """How far the strip reaches with these tab widths, the last point in."""
    return sum(widths) + GAP * max(0, len(widths) - 1) + POINT


def layout(width, height, measure, tabs=TABS, keys=True):
    """The tabs laid out from the left in `width` x `height` pixels. `measure`
    says how many pixels a piece of text takes. [Tab]: the polygon's points,
    where the name and the key are centred, and whether the key is shown."""
    height = max(1, int(height))
    tries = ([(True, PAD)] if keys else []) + [(False, PAD), (False, PAD_LEAST)]
    shown, pad = tries[-1]
    for shown, pad in tries:
        if _span(_widths(tabs, measure, shown, pad)) <= width:
            break
    widths = _widths(tabs, measure, shown, pad)
    middle = height / 2.0
    out, x0 = [], 0
    for index, ((key, label, fkey), wide) in enumerate(zip(tabs, widths)):
        x1 = x0 + wide
        notch = POINT if index else 0
        points = [(x0, 0), (x1, 0), (x1 + POINT, middle), (x1, height), (x0, height)]
        if notch:
            points.append((x0 + notch, middle))
        left = x0 + notch + pad
        name_w = measure(label)
        if shown:
            whole = name_w + measure(KEY_SPACE + fkey)
            text_x = left + name_w / 2.0
            key_x = left + whole - measure(fkey) / 2.0
        else:
            text_x = (x0 + notch + x1) / 2.0
            key_x = None
        out.append(Tab(key, label, fkey, x0, x1, tuple(points), text_x, key_x, shown))
        x0 = x1 + GAP
    return out


def _inside(points, x, y):
    """Ray casting: is (x, y) inside the polygon?"""
    hit = False
    j = len(points) - 1
    for i in range(len(points)):
        xi, yi = points[i]
        xj, yj = points[j]
        if (yi > y) != (yj > y):
            cross = xj + (y - yj) * (xi - xj) / float(yi - yj)
            if x < cross:
                hit = not hit
        j = i
    return hit


def hit(tabs, x, y):
    """The key of the tab under (x, y), or None - between two tabs, above,
    below or past the end of the strip."""
    for tab in tabs:
        if _inside(tab.points, x, y):
            return tab.key
    return None
