"""The arithmetic behind the tables on the toolkit's own tree view (1.10040, #308).

The big tables - Find, Sessions, My sites, Where to land - used to be grids
of labels: every cell a widget of its own, a thousand rows ten thousand
widgets, built again on every sort. That is what made them slow to draw and
what let the scrollbar argue with itself in 1.10037. They now sit on the
toolkit's tree view, and only the rows on screen are in it: scrolling moves
which rows those are, so drawing two rows costs the same as drawing twenty
thousand.

Nothing here touches a widget. The table in edsmt.py asks these how many
rows fit, which rows are on screen, what the scrollbar should say, what
colour a row is and how wide a column wants to be.
"""

# A row takes its colour from its cells: the strongest of these wins. The
# label grids coloured single cells; a tree view colours whole rows, so a
# row with a red cell reads red, then amber, then green.
TONES = ("bad", "caution", "good")
# A cell's lines on one row: a tree view row is one line high.
LINE_JOIN = " · "
# How many rows are looked at to size the columns. The longest texts in the
# whole set are added to those, so a long name further down is not cut off.
WIDTH_SAMPLE = 300
WIDTH_LONGEST = 12


def _whole(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def visible_rows(height_px, heading_px, row_px):
    """How many whole rows fit under the headings. At least one."""
    row_px = max(1, _whole(row_px, 1))
    room = _whole(height_px) - max(0, _whole(heading_px))
    return max(1, room // row_px)


def clamp_offset(offset, visible, total):
    """The first row on screen, kept inside the rows there are."""
    visible = max(1, _whole(visible, 1))
    total = max(0, _whole(total))
    return max(0, min(_whole(offset), max(0, total - visible)))


def fractions(offset, visible, total):
    """What the scrollbar says: (first, last) as shares of every row."""
    total = max(0, _whole(total))
    if total <= 0:
        return 0.0, 1.0
    offset = clamp_offset(offset, visible, total)
    last = min(total, offset + max(1, _whole(visible, 1)))
    return offset / float(total), last / float(total)


def offset_at(fraction, visible, total):
    """The first row for a scrollbar dragged to `fraction`."""
    try:
        share = float(fraction)
    except (TypeError, ValueError):
        share = 0.0
    return clamp_offset(int(round(share * max(0, _whole(total)))), visible, total)


def scrolled(offset, amount, what, visible, total):
    """The first row after scrolling `amount` units (rows) or pages."""
    step = _whole(amount)
    if str(what or "").startswith("page"):
        step *= max(1, _whole(visible, 1) - 1)
    return clamp_offset(_whole(offset) + step, visible, total)


def into_view(index, offset, visible, total):
    """The first row that puts row `index` on screen, moving as little as
    it can."""
    index = max(0, min(_whole(index), max(0, _whole(total) - 1)))
    visible = max(1, _whole(visible, 1))
    offset = _whole(offset)
    if index < offset:
        offset = index
    elif index >= offset + visible:
        offset = index - visible + 1
    return clamp_offset(offset, visible, total)


def window(offset, visible, total):
    """range() of the rows on screen."""
    offset = clamp_offset(offset, visible, total)
    return range(offset, min(max(0, _whole(total)), offset + max(1, _whole(visible, 1))))


def row_tone(colours, roles):
    """The row's colour by name - "bad", "caution", "good" or "" - from its
    cells' colours. `roles` maps each name to the palette colour that means
    it."""
    have = {str(colour).lower() for colour in colours if colour}
    for name in TONES:
        colour = roles.get(name)
        if colour and str(colour).lower() in have:
            return name
    return ""


def one_line(text):
    """A cell's text as a tree view row shows it: its lines side by side."""
    lines = [part.strip() for part in str(text if text is not None else "").split("\n")]
    return LINE_JOIN.join(part for part in lines if part)


def line_of(texts):
    """One row as Copy takes it: every cell's whole text, on one line."""
    return " | ".join(str(text).replace("\n", " ") for text in texts)


def block_of(headers, rows):
    """Rows as Copy takes them: the headings, then a line a row."""
    return "\n".join([" | ".join(str(name) for name in headers)]
                     + [line_of(texts) for texts in rows])


def sample(total, longest=()):
    """Which rows to size the columns by: the first WIDTH_SAMPLE, and the
    indexes in `longest`."""
    picked = list(range(min(max(0, _whole(total)), WIDTH_SAMPLE)))
    seen = set(picked)
    for index in longest:
        if 0 <= index < total and index not in seen:
            picked.append(index)
            seen.add(index)
    return picked


def longest_texts(texts, count=WIDTH_LONGEST):
    """The `count` longest of a column's texts, longest first - the only
    ones worth measuring in pixels."""
    unique = sorted({str(text) for text in texts}, key=len, reverse=True)
    return unique[:max(1, count)]


def column_width(heading, texts, measure, least=40, most=420, pad=18):
    """A column's width in pixels: its heading or its longest cell, whichever
    is wider, between `least` and `most`. `measure(text)` is the font's."""
    widest = measure(str(heading))
    for text in longest_texts(texts):
        widest = max(widest, measure(text))
    return max(int(least), min(int(most), int(widest) + int(pad)))


def picked_after(picked, index, anchor, shift=False, ctrl=False):
    """The rows picked after a click on row `index`: on its own, added or
    taken away with Ctrl, or a run from the anchor with Shift.
    (picked, anchor)."""
    picked = set(picked)
    if shift and anchor is not None:
        low, high = sorted((anchor, index))
        return picked | set(range(low, high + 1)) if ctrl else set(range(low, high + 1)), anchor
    if ctrl:
        if index in picked:
            picked.discard(index)
        else:
            picked.add(index)
        return picked, index
    return {index}, index
