"""The session card (1.10040, #151): one Rhino session as a picture, for a
stream or a Discord channel.

Built in two steps, like the map picture it borrows from (mapimage.py):

  card_facts    what the card says about a session - whose, where, when,
                tonnes by commodity, credits, credits an hour, merits and
                time mined - from the session's row and what the app has
                worked out about it. No imaging library.
  render_card   paints those facts with Pillow: the map picture of the
                session as a thumbnail when there is one, and the EDSMT badge
                small in a corner. It answers the texts it wrote as well as
                the picture, so what a card says is checked without reading
                pixels.

Pillow is optional, as for map pictures: mapimage.pillow_status() says why a
card cannot be made, and the button says it.
"""
import calendar
import os
import re
import time

import mapimage as MI
import survey as SV

SS = 2                                  # drawn at twice the size, then shrunk
SIZE = (1200, 675)                      # 16:9 - a stream, a Discord preview
MAP_BOX = (820, 132, 1176, 488)         # the map thumbnail, square
BADGE_PX = 56
TONNES_SHOWN = 8
SITE = MI.SITE

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
           "Oct", "Nov", "Dec")


def _whole(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    return 0 if number != number else int(round(number))


def _hours_text(hours):
    minutes = max(0, int(round(float(hours or 0) * 60)))
    if minutes < 60:
        return "%dm" % minutes
    return "%dh %02dm" % divmod(minutes, 60)


def _span(first, last):
    """"02:48 to 05:18 UTC", with the dates when it ran past midnight."""
    if not first or not last or last < first:
        return ""
    a, b = time.gmtime(first), time.gmtime(last)
    if (a.tm_year, a.tm_yday) == (b.tm_year, b.tm_yday):
        return "%02d:%02d to %02d:%02d UTC" % (a.tm_hour, a.tm_min, b.tm_hour, b.tm_min)
    return "%d %s %02d:%02d to %d %s %02d:%02d UTC" % (
        a.tm_mday, _MONTHS[a.tm_mon - 1], a.tm_hour, a.tm_min,
        b.tm_mday, _MONTHS[b.tm_mon - 1], b.tm_hour, b.tm_min)


def card_facts(row, cmdr="", estimate=None, merits=None, merits_estimated=False, hide=None):
    """What the card says about one session. `row` is the session as the
    books keep it; `estimate` what the app worked out it is worth (its
    "value" counts what is still unsold at the best price known); `merits`
    the merits it earned; `hide` streamer mode's rule for a line of text,
    which the system and body pass through. Never raises."""
    row = dict(row or {})
    hide = hide or (lambda text: text)
    mined = SV.unpack_counts(row.get("mined"))
    tonnes = sorted(((SV.canonical(name) or name, int(count)) for name, count in mined.items()
                     if int(count) > 0), key=lambda pair: (-pair[1], pair[0]))
    hours = SV.session_hours(row)
    sold = float(SV.earned(row) or 0)
    value = float((estimate or {}).get("value") or 0)
    estimated = value > sold + 0.5
    credits = value if estimated else sold
    first = SV._epoch(row.get("started"))
    last = SV._epoch(row.get("ended") or row.get("closed"))
    moment = time.gmtime(first) if first else None
    earned = _whole(merits) if merits is not None else 0
    return {
        "cmdr": str(cmdr or row.get("cmdr") or "").strip(),
        "system": str(hide(str(row.get("system") or "").strip()) or ""),
        "body": str(hide(str(row.get("body") or "").strip()) or ""),
        "started": first,
        "date": ("%d %s %d" % (moment.tm_mday, _MONTHS[moment.tm_mon - 1], moment.tm_year))
        if moment else "",
        "span": _span(first, last),
        "tonnes": tonnes,
        "tonnes_total": sum(count for _name, count in tonnes),
        "credits": _whole(credits),
        "credits_estimated": bool(estimated),
        "cr_hr": _whole(credits / hours) if hours > 0 else 0,
        "merits": earned or None,
        "merits_estimated": bool(merits_estimated) if earned else False,
        "hours": hours,
        "time_mined": _hours_text(hours),
    }


def card_name(row):
    """card_<system>_<body>_<yyyymmdd-hhmm>.png from the session's row, safe
    on Windows, and named like a map picture so the same tidying keeps them
    in check. The real names, whatever the card shows."""
    row = row or {}
    first = SV._epoch(row.get("started"))
    moment = time.gmtime(first or time.time())
    return "card_%s_%s_%s.png" % (MI._clean(row.get("system")), MI._clean(row.get("body")),
                                  time.strftime("%Y%m%d-%H%M", moment))


def find_map(folder, system, body, first, last=0):
    """The map picture of `body` saved while a session ran - the last one,
    by the time in its name - or "". `last` of 0 is a session still running.
    A session card is never mistaken for a map. Never raises."""
    if not first:
        return ""
    pattern = re.compile(r"^%s_%s_[A-Za-z0-9_]{1,8}_(\d{8}-\d{4})\.png$"
                         % (re.escape(MI._clean(system)), re.escape(MI._clean(body))))
    low, high = float(first) - 60, float(last or time.time()) + 120
    best = None
    try:
        names = os.listdir(folder)
    except OSError:
        return ""
    for name in names:
        found = pattern.match(name)
        if not found or name.startswith("card_"):
            continue
        try:
            at = calendar.timegm(time.strptime(found.group(1), "%Y%m%d-%H%M"))
        except ValueError:
            continue
        if low <= at <= high and (best is None or at > best[0]):
            best = (at, os.path.join(folder, name))
    return best[1] if best else ""


def map_plot(image):
    """The map itself out of a map picture: the square plot, without the
    title over it or the legend beside it - the names are in the title, and
    the card says those itself. A picture of another shape is used whole."""
    width, height = image.size
    full_w, full_h = MI.SIZE
    if not width or abs(height / float(width) - full_h / float(full_w)) > 0.01:
        return image
    scale = width / float(full_w)
    side = full_h - 150
    box = (24, 96, 24 + side, 96 + side)
    return image.crop(tuple(int(round(v * scale)) for v in box))


def load_badge(path):
    """The EDSMT badge as a Pillow picture, or None when it is missing or
    will not load - a card without its badge is still a card."""
    try:
        from PIL import Image
        with Image.open(path) as source:
            source.load()
            return source.convert("RGBA")
    except Exception:
        return None


def _cmdr(name):
    name = str(name or "").strip()
    if not name:
        return ""
    return name if name.lower().startswith("cmdr ") else "CMDR " + name


def _stats(facts):
    """The boxes along the foot: (label, value)."""
    credits = "{:,} Cr".format(facts["credits"])
    out = [("CREDITS", ("est. " + credits) if facts["credits_estimated"] else credits),
           ("CR/HR", ("est. " if facts["credits_estimated"] else "") + "{:,}".format(facts["cr_hr"]))]
    if facts.get("merits"):
        out.append(("MERITS", ("est. " if facts["merits_estimated"] else "") + "{:,}".format(facts["merits"])))
    out.append(("TIME MINED", facts["time_mined"]))
    return out


def render_card(facts, map_image=None, colour=None, badge=None):
    """The card as a Pillow RGB image, and the texts on it. `map_image` is
    a map picture to show as a thumbnail; `colour` gives a commodity's
    colour; `badge` the EDSMT badge. Raises ImportError without Pillow."""
    from PIL import Image, ImageDraw

    width, height = SIZE
    big = Image.new("RGB", (width * SS, height * SS), MI.BACKGROUND)
    draw = ImageDraw.Draw(big)
    written = []

    def s(value):
        return int(round(value * SS))

    def text(x, y, value, size=18, fill=MI.TEXT, bold=False, anchor="la", room=None, least=None):
        value = str(value)
        if room and least:
            # A figure is never cut: its type gets smaller until it fits.
            while size > least and MI._measure(value, size, bold)[0] > room:
                size -= 1
        if room:
            while len(value) > 4 and MI._measure(value, size, bold)[0] > room:
                value = value[:-2].rstrip() + "~"
        written.append(value)
        font = MI._font(s(size), bold)
        try:
            draw.text((s(x), s(y)), value, font=font, fill=fill, anchor=anchor)
        except ValueError:
            draw.text((s(x), s(y)), value, font=font, fill=fill)

    def tint(name):
        if colour is not None:
            try:
                return colour(name)
            except Exception:
                pass
        return MI.DEFAULT_COLOUR

    draw.rectangle([0, 0, s(width) - 1, s(8)], fill=MI.DEFAULT_COLOUR)
    has_map = map_image is not None
    right = (MAP_BOX[0] - 32) if has_map else (width - 24)

    # Whose, where, when.
    text(24, 26, _cmdr(facts.get("cmdr")) or "Rhino session", 40, MI.TEXT, True,
         room=width - 330)
    if facts.get("body"):
        text(24, 78, facts["body"], 24, MI.AMBER, room=width - 330)
    if facts.get("system"):
        text(24, 108, facts["system"], 18, MI.DIM, room=width - 330)
    if facts.get("date"):
        text(width - 24, 30, facts["date"], 22, MI.TEXT, False, "ra")
    if facts.get("span"):
        text(width - 24, 62, facts["span"], 16, MI.DIM, False, "ra")
    draw.line([(s(24), s(138)), (s(right), s(138))], fill=MI.RULE, width=s(1))

    # Tonnes by commodity.
    y = 152
    text(24, y, "MINED", 18, MI.AMBER, True)
    text(right, y, "%d t" % facts["tonnes_total"], 18, MI.AMBER, True, "ra")
    y += 36
    for name, count in facts["tonnes"][:TONNES_SHOWN]:
        r = 7
        draw.ellipse([s(32 - r), s(y + 12 - r), s(32 + r), s(y + 12 + r)], fill=tint(name))
        text(50, y, name, 22, MI.TEXT, room=right - 150)
        text(right, y, "%d t" % count, 22, MI.TEXT, False, "ra")
        y += 34
    hidden = len(facts["tonnes"]) - TONNES_SHOWN
    if hidden > 0:
        text(50, y, "+ %d more" % hidden, 18, MI.DIM)

    # The map, as it stood, kept to its own shape inside its box.
    if has_map:
        x0, y0, x1, y1 = MAP_BOX
        draw.rectangle([s(x0) - s(1), s(y0) - s(1), s(x1) + s(1), s(y1) + s(1)],
                       fill=MI.PLOT, outline=MI.RULE, width=s(1))
        room_w, room_h = s(x1 - x0), s(y1 - y0)
        picture = map_plot(map_image.convert("RGB"))
        scale = min(room_w / float(picture.size[0]), room_h / float(picture.size[1]))
        fitted = picture.resize((max(1, int(picture.size[0] * scale)),
                                 max(1, int(picture.size[1] * scale))), Image.LANCZOS)
        big.paste(fitted, (s(x0) + (room_w - fitted.size[0]) // 2,
                           s(y0) + (room_h - fitted.size[1]) // 2))

    # The figures, along the foot.
    stats = _stats(facts)
    top = 512
    draw.line([(s(24), s(top - 14)), (s(width - 24), s(top - 14))], fill=MI.RULE, width=s(1))
    step = (width - 48) / float(len(stats))
    for index, (label, value) in enumerate(stats):
        x = 24 + index * step
        text(x, top, label, 16, MI.DIM, True)
        text(x, top + 26, value, 30, MI.GOLD if label == "CREDITS" else MI.TEXT, True,
             room=step - 16, least=16)
    text(24, height - 40, "EDSMT  %s" % SITE, 16, MI.DIM)

    # The badge, small, in the corner the footer leaves free.
    if badge is not None:
        mark = badge.convert("RGBA").resize((s(BADGE_PX), s(BADGE_PX)), Image.LANCZOS)
        big.paste(mark, (s(width - 24 - BADGE_PX), s(height - 16 - BADGE_PX)), mark)
    return big.resize((width, height), Image.LANCZOS), written
