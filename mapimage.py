"""Map pictures (1.10035, #237): the plan view as a PNG.

The picture is built in two steps so that each can be checked on its own:

  build_scene   works out WHERE everything goes - deposits, rigs, the swept
                ground, the trail, the scale bar - and WHAT is written, as
                plain data. It reuses planview's own Viewport, layout and
                swept_shapes, so a picture and the map on screen cannot
                disagree about where a deposit is. No imaging library.
  draw_scene    paints that data with Pillow. Pillow needs no Ghostscript
                and no display, which is why a Tk canvas postscript dump
                (the old plan, #87) was not used.

Pillow is the one dependency this adds. If it is missing the app still runs;
pillow_status() says why a picture is unavailable and the buttons say it.
The commander's name is drawn only when the caller passes one - the app does
that only when name sharing is on.
"""

import importlib
import io
import math
import os
import re
import struct
import time

import planview as PV

SS = 2                                  # drawn at twice the size, then shrunk
SIZE = (1280, 900)
MAX_BYTES = 8 * 1024 * 1024             # Discord's own limit for a file
PICTURES_KEPT = 300
SITE = "radioraxxla.com/EDSMT"

BACKGROUND = "#0b0d12"
PLOT = "#10141c"
RULE = "#2a3140"
GRID = "#1b2230"
TEXT = "#e9dccd"
DIM = "#9a8f84"
AMBER = "#ffb545"
GOLD = "#f2c94c"
CYAN = "#37c6d4"
RED = "#d1483a"
SWEPT = "#1f3a46"
DEFAULT_COLOUR = "#ff7a18"

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
           "Oct", "Nov", "Dec")


def pillow_status():
    """(True, "") when pictures can be made, else (False, why in a sentence)."""
    try:
        for name in ("PIL.Image", "PIL.ImageDraw", "PIL.ImageFont"):
            importlib.import_module(name)
    except Exception as exc:
        return False, ("Map pictures are off: the Pillow image library is not "
                       "installed here (%s). Reinstall EDSMT, or from source "
                       "run  pip install Pillow." % type(exc).__name__)
    return True, ""


# -- fonts and measuring ---------------------------------------------------

_FONTS = {}
_FONT_NAMES = ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf")
_BOLD_NAMES = ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf")


def _font(size, bold=False):
    key = (int(size), bool(bold))
    if key in _FONTS:
        return _FONTS[key]
    from PIL import ImageFont
    found = None
    for name in (_BOLD_NAMES if bold else _FONT_NAMES):
        try:
            found = ImageFont.truetype(name, int(size))
            break
        except (OSError, ValueError):
            continue
    if found is None:
        try:
            found = ImageFont.load_default(int(size))
        except TypeError:
            found = ImageFont.load_default()
    _FONTS[key] = found
    return found


def _measure(text, size, bold=False):
    """(width, height) of `text` at `size` pixels, without a canvas."""
    text = str(text)
    try:
        font = _font(size, bold)
        box = font.getbbox(text)
        return float(box[2] - box[0]), float(max(box[3] - box[1], size * 0.8))
    except Exception:
        return len(text) * size * 0.58, float(size)


def metres_text(value):
    try:
        metres = float(value)
    except (TypeError, ValueError):
        return "-"
    if metres >= 10000:
        return "{:,.0f} km".format(metres / 1000.0)
    if metres >= 1000:
        return "%.2f km" % (metres / 1000.0)
    return "%.0f m" % metres


def stamp_text(when=None):
    moment = time.gmtime(when if when is not None else time.time())
    return "%d %s %d %02d:%02d UTC" % (moment.tm_mday, _MONTHS[moment.tm_mon - 1],
                                       moment.tm_year, moment.tm_hour, moment.tm_min)


# -- what the picture shows --------------------------------------------------

def fit_view(rows, signal="", anchor=None, survey=None, rigs=None, trail=None):
    """Which finds a picture holds, where it is centred and how far it
    reaches - worked out the way the map on screen opens on a signal, but
    measured from the signal and not from where the commander happens to be
    standing when the picture is taken. East and north are metres from the
    commander, as in every row."""
    view = PV.signal_focus(rows, signal, anchor, near_m=None)
    centre = view["centre"]
    shown = list(view["here"])
    points = [PV.to_offset(r.get("range_m"), r.get("bearing")) for r in shown]
    survey = survey if isinstance(survey, dict) else None
    if survey and survey.get("centre") and survey.get("border_m"):
        ce, cn = survey["centre"]
        reach = float(survey["border_m"])
        points += [(ce + reach, cn), (ce - reach, cn), (ce, cn + reach), (ce, cn - reach)]
        if view["how"] == "commander":
            centre = (float(ce), float(cn))
    rigs = rigs if isinstance(rigs, dict) else None
    if rigs:
        points += [(m["east"], m["north"]) for m in rigs.get("rigs") or []]
    if trail:
        points += [(float(p[0]), float(p[1])) for p in trail]
    if not shown and not points:
        centre = (0.0, 0.0)
    elif view["how"] == "commander" and points:
        centre = PV.midpoint(points) if len(points) > 1 else points[0]
    relative = [(e - centre[0], n - centre[1]) for e, n in points
                if math.hypot(e - centre[0], n - centre[1]) <= PV.SIGNAL_NAMED_REACH_M]
    floor = PV.SIGNAL_VIEW_FLOOR_M if relative else PV.SIGNAL_VIEW_EMPTY_M
    extent = PV.extent_for(relative, floor_m=floor, headroom=1.3,
                           cap_m=PV.SIGNAL_VIEW_CAP_M)
    return {"rows": shown, "centre": centre, "extent_m": extent,
            "away": len(view["away"])}


def _deposit_facts(item):
    deposit = item.get("deposit") or {}
    depleted = str(deposit.get("amount") or "").strip().lower() in ("depleted", "exhausted", "empty")
    rigs = str(deposit.get("rigs") or "").strip()
    return {"depleted": depleted, "rigs": rigs,
            "amount": str(deposit.get("amount") or "").strip(),
            "density": str(deposit.get("density") or "").strip()}


def build_scene(rows, system="", body="", signal="", anchor=None, survey=None,
                rigs=None, trail=None, cmdr="", when=None, version="",
                colour=None, size=SIZE, note=""):
    """Everything a picture draws, as data. See the module note."""
    colour = colour or (lambda name: DEFAULT_COLOUR)
    width, height = int(size[0]), int(size[1])
    side = height - 150
    x0, y0 = 24, 96
    fit = fit_view(rows, signal, anchor, survey, rigs, trail)
    centre, extent = fit["centre"], fit["extent_m"]
    viewport = PV.Viewport(side, side, extent, margin=30)
    plan = PV.layout(fit["rows"], viewport, origin=centre)

    def put(x, y):
        return x + x0, y + y0

    def spot(east, north):
        return put(*viewport.to_canvas(east - centre[0], north - centre[1]))

    scene = {"size": (width, height), "plot": (x0, y0, x0 + side, y0 + side),
             "extent_m": extent, "centre": centre, "markers": [], "rig_marks": [],
             "swept": [], "rings": [], "ring_labels": [], "border": None,
             "trail": [], "patch": None, "texts": [], "legend": [],
             "taken": [], "beyond": 0}
    cx, cy = put(*viewport.centre)
    scene["middle"] = (cx, cy)

    # The swept ground, inside the survey border, under everything.
    if isinstance(survey, dict) and survey.get("scan_m"):
        for shape in PV.swept_shapes(survey.get("points"), survey.get("scan_m"),
                                     survey.get("centre"), survey.get("border_m")):
            if shape[0] == "disc":
                px, py = spot(shape[1], shape[2])
                scene["swept"].append(("disc", px, py, viewport.radius_px(shape[3])))
            else:
                scene["swept"].append(("poly", [spot(e, n) for e, n in shape[1]]))
    percent = None
    if isinstance(survey, dict) and survey.get("centre") and survey.get("border_m"):
        bx, by = spot(*survey["centre"])
        scene["border"] = (bx, by, viewport.radius_px(float(survey["border_m"])))
        percent = survey.get("percent")
        scene["rings"] += [(bx, by, viewport.radius_px(r))
                           for r in survey.get("rings") or []]
    for ring in plan["rings"]:
        scene["ring_labels"].append((ring["radius"], ring["metres"]))
    if trail:
        scene["trail"] = [spot(float(p[0]), float(p[1])) for p in trail]

    # Deposits.
    shown = []
    for item in plan["items"]:
        if item["offscreen"] or not viewport.within(item["east_m"], item["north_m"]):
            scene["beyond"] += 1
            continue
        facts = _deposit_facts(item)
        px, py = put(item["x"], item["y"])
        shown.append(dict(item, x=px - x0, y=py - y0))   # patch maths stays local
        scene["markers"].append({
            "id": item["id"], "x": px, "y": py, "r": item["radius"],
            "commodity": item["commodity"], "colour": colour(item["commodity"]),
            "hollow": facts["depleted"], "rigs": facts["rigs"],
            "range_m": item["range_m"], "amount": facts["amount"],
            "density": facts["density"],
            "from_centre_m": math.hypot(item["east_m"], item["north_m"]),
            "compass": PV.compass_point(PV.to_polar(item["east_m"], item["north_m"])[1])})
    # The rigs, numbered.
    rig_list = (rigs.get("rigs") or []) if isinstance(rigs, dict) else []
    limit = float(rigs.get("limit_m") or 0) if isinstance(rigs, dict) else 0
    for mark in rig_list:
        px, py = spot(mark["east"], mark["north"])
        if not (x0 <= px <= x0 + side and y0 <= py <= y0 + side):
            continue
        what = str(mark.get("commodity") or "")
        scene["rig_marks"].append({
            "n": mark.get("n"), "x": px, "y": py, "commodity": what,
            "colour": colour(what) if what else AMBER,
            "far": bool(limit and float(mark.get("range_m") or 0) > limit)})
    # Best patch: the knot with the most rigs.
    patch = PV.best_patch(shown)
    if patch:
        scene["patch"] = {"x": patch["x"] + x0, "y": patch["y"] + y0,
                          "r": patch["radius"] + 8, "rigs": patch["rigs"],
                          "count": patch["count"],
                          "commodities": patch["commodities"]}

    # Scale bar: the ring step, in pixels.
    step = plan["ring_step_m"]
    scene["scale"] = {"metres": step, "px": viewport.radius_px(step)}

    # What is written.
    title = " / ".join(p for p in (system, body) if p) or "Mining map"
    if signal:
        title += "   signal %s" % signal
    sub = []
    sub.append("%d deposit%s" % (len(scene["markers"]), "" if len(scene["markers"]) == 1 else "s"))
    total_rigs = sum(int(m["rigs"]) for m in scene["markers"] if str(m["rigs"]).isdigit())
    if total_rigs:
        sub.append("%d rigs" % total_rigs)
    if percent is not None:
        sub.append("swept %d%%" % percent)
    if cmdr:
        sub.append("CMDR %s" % cmdr)
    scene["title"], scene["sub"] = title, "   ".join(sub)
    scene["stamp"] = stamp_text(when)
    scene["footer"] = "EDSMT %s - %s" % (version, SITE) if version else "EDSMT - %s" % SITE
    scene["note"] = note
    # The deposits themselves, for the text that goes with a shared picture.
    scene["deposits"] = [item["deposit"] for item in shown if item.get("deposit")]
    scene["patch_deposits"] = ([item["deposit"] for item in patch["items"]
                                if item.get("deposit")] if patch else [])

    groups = {}
    for marker in scene["markers"]:
        name = marker["commodity"] or "Unknown"
        entry = groups.setdefault(name, {"colour": marker["colour"], "finds": 0,
                                         "rigs": 0, "depleted": 0})
        entry["finds"] += 1
        entry["depleted"] += 1 if marker["hollow"] else 0
        entry["rigs"] += int(marker["rigs"]) if str(marker["rigs"]).isdigit() else 0
    scene["legend"] = sorted(((n, e) for n, e in groups.items()),
                             key=lambda kv: (-kv[1]["rigs"], -kv[1]["finds"], kv[0]))
    texts = [scene["title"], scene["sub"], scene["stamp"], scene["footer"],
             "SCALE %s" % metres_text(step)]
    texts += ["%s  %d finds  %dR" % (n, e["finds"], e["rigs"]) for n, e in scene["legend"]]
    if scene["patch"]:
        texts.append("BEST PATCH  %dR  %s" % (scene["patch"]["rigs"],
                                              ", ".join(scene["patch"]["commodities"])))
    if note:
        texts.append(note)
    scene["texts"] = texts
    return scene


# -- painting ----------------------------------------------------------------

def draw_scene(scene):
    """The scene as a Pillow RGB image. Raises ImportError without Pillow."""
    from PIL import Image, ImageDraw

    width, height = scene["size"]
    big = Image.new("RGB", (width * SS, height * SS), BACKGROUND)
    draw = ImageDraw.Draw(big)

    def s(value):
        return value * SS

    def circle(x, y, r, fill=None, outline=None, line=1):
        draw.ellipse([s(x - r), s(y - r), s(x + r), s(y + r)], fill=fill,
                     outline=outline, width=max(1, int(s(line))))

    def text(x, y, value, size=14, fill=TEXT, bold=False, anchor="la"):
        font = _font(s(size), bold)
        try:
            draw.text((s(x), s(y)), str(value), font=font, fill=fill, anchor=anchor)
        except ValueError:
            # A bitmap font cannot be anchored; the text goes where it is put.
            draw.text((s(x), s(y)), str(value), font=font, fill=fill)

    x0, y0, x1, y1 = scene["plot"]
    draw.rectangle([s(x0), s(y0), s(x1), s(y1)], fill=PLOT, outline=RULE,
                   width=s(1))
    cx, cy = scene["middle"]

    # The plot is painted on its own layer and pasted, so nothing drawn for
    # the ground can spill over the header or the legend.
    layer = Image.new("RGB", (int(s(x1 - x0)), int(s(y1 - y0))), PLOT)
    pen = ImageDraw.Draw(layer)

    def local(x, y):
        return s(x - x0), s(y - y0)

    for kind, *shape in scene["swept"]:
        if kind == "disc":
            px, py, r = shape
            lx, ly = local(px, py)
            pen.ellipse([lx - s(r), ly - s(r), lx + s(r), ly + s(r)], fill=SWEPT)
        else:
            pen.polygon([local(x, y) for x, y in shape[0]], fill=SWEPT)
    mx, my = local(cx, cy)
    for radius, _metres in scene["ring_labels"]:
        pen.ellipse([mx - s(radius), my - s(radius), mx + s(radius), my + s(radius)],
                    outline=GRID, width=s(1))
    pen.line([(0, my), (layer.size[0], my)], fill=GRID, width=s(1))
    pen.line([(mx, 0), (mx, layer.size[1])], fill=GRID, width=s(1))
    for bx, by, br in scene["rings"]:
        lx, ly = local(bx, by)
        pen.ellipse([lx - s(br), ly - s(br), lx + s(br), ly + s(br)], outline=CYAN,
                    width=s(1))
    if scene["border"]:
        bx, by, br = scene["border"]
        lx, ly = local(bx, by)
        pen.ellipse([lx - s(br), ly - s(br), lx + s(br), ly + s(br)], outline=AMBER,
                    width=s(2))
        pen.line([(lx - s(7), ly), (lx + s(7), ly)], fill=AMBER, width=s(2))
        pen.line([(lx, ly - s(7)), (lx, ly + s(7))], fill=AMBER, width=s(2))
    if len(scene["trail"]) > 1:
        pen.line([local(x, y) for x, y in scene["trail"]], fill="#5b6f86", width=s(2),
                 joint="curve")
    big.paste(layer, (int(s(x0)), int(s(y0))))

    if scene["patch"]:
        p = scene["patch"]
        circle(p["x"], p["y"], p["r"], outline=GOLD, line=2)
    for marker in scene["markers"]:
        r = marker["r"]
        if marker["hollow"]:
            circle(marker["x"], marker["y"], r, fill=PLOT, outline=marker["colour"], line=2)
        else:
            circle(marker["x"], marker["y"], r, fill=marker["colour"], outline=BACKGROUND)
    for mark in scene["rig_marks"]:
        tint = RED if mark["far"] else mark["colour"]
        draw.rectangle([s(mark["x"] - 8), s(mark["y"] - 8), s(mark["x"] + 8), s(mark["y"] + 8)],
                       fill=BACKGROUND, outline=tint, width=s(2))
        text(mark["x"], mark["y"], mark["n"], 11, tint, True, "mm")
    # You, in the middle of the picture's own frame, are not drawn: the
    # picture is of the patch, not of where the SRV was parked.

    # Labels, each in the first free spot beside its dot.
    taken = [(x - r, y - r, x + r, y + r)
             for x, y, r in ((m["x"], m["y"], m["r"] + 2) for m in scene["markers"])]
    bounds = (x0 + 2, y0 + 2, x1 - 2, y1 - 2)
    ordered = sorted(scene["markers"], key=lambda m: (-(int(m["rigs"]) if str(m["rigs"]).isdigit() else 0),
                                                     m["range_m"]))
    for marker in ordered:
        label = marker["commodity"] or "Unknown"
        if marker["rigs"]:
            label += "  %sR" % marker["rigs"]
        if marker["hollow"]:
            label += "  (depleted)"
        w, h = _measure(label, 13)
        gap = marker["r"] + 6
        spots = [(marker["x"] + gap, marker["y"] - h / 2.0),
                 (marker["x"] - gap - w, marker["y"] - h / 2.0),
                 (marker["x"] - w / 2.0, marker["y"] + marker["r"] + 3),
                 (marker["x"] - w / 2.0, marker["y"] - marker["r"] - 3 - h)]
        boxes = [(sx, sy, sx + w, sy + h) for sx, sy in spots]
        free = PV.label_spot(boxes, taken, bounds=bounds)
        if free is None:
            continue
        taken.append(free)
        text(free[0], free[1] - 2, label, 13, DIM if marker["hollow"] else TEXT)

    # Scale bar, bottom left of the plot.
    bar = scene["scale"]
    by = y1 - 22
    draw.line([(s(x0 + 16), s(by)), (s(x0 + 16 + bar["px"]), s(by))], fill=TEXT, width=s(2))
    for tick in (x0 + 16, x0 + 16 + bar["px"]):
        draw.line([(s(tick), s(by - 5)), (s(tick), s(by + 5))], fill=TEXT, width=s(2))
    text(x0 + 16, by - 9, metres_text(bar["metres"]), 12, DIM, False, "ls")
    text(x0 + 10, y0 + 8, "N", 13, DIM, True)
    if scene["beyond"]:
        text(x1 - 8, y1 - 8, "%d beyond the edge" % scene["beyond"], 12, DIM, False, "rs")

    # Header. A long system and body name is cut to the width, not drawn
    # over the date.
    title = scene["title"]
    room = scene["size"][0] - 48
    while len(title) > 8 and _measure(title, 30, True)[0] > room:
        title = title[:-2].rstrip() + "~" if not title.endswith("~") else title[:-2] + "~"
    text(24, 18, title, 30, TEXT, True)
    text(24, 58, scene["sub"], 17, AMBER)
    text(scene["size"][0] - 24, 58, scene["stamp"], 17, DIM, False, "ra")

    # Legend, right of the plot.
    lx = x1 + 28
    ly = y0 + 2
    text(lx, ly, "DEPOSITS", 15, AMBER, True)
    ly += 30
    for name, entry in scene["legend"][:12]:
        circle(lx + 8, ly + 11, 7, fill=entry["colour"])
        text(lx + 26, ly, name, 17, TEXT)
        detail = "%d find%s" % (entry["finds"], "" if entry["finds"] == 1 else "s")
        if entry["rigs"]:
            detail += "  %dR" % entry["rigs"]
        if entry["depleted"]:
            detail += "  %d depleted" % entry["depleted"]
        text(scene["size"][0] - 24, ly + 1, detail, 14, DIM, False, "ra")
        ly += 30
    if scene["patch"]:
        ly += 12
        circle(lx + 8, ly + 11, 8, outline=GOLD, line=2)
        text(lx + 26, ly, "BEST PATCH", 17, GOLD, True)
        patch = scene["patch"]
        text(scene["size"][0] - 24, ly + 1, "%dR  %d finds" % (patch["rigs"], patch["count"]),
             14, DIM, False, "ra")
        ly += 26
        text(lx + 26, ly, ", ".join(patch["commodities"])[:44], 14, DIM)
        ly += 30
    # Each deposit: what, how many rigs, how much is left, and where from the
    # middle of the patch.
    ly += 8
    text(lx, ly, "FINDS", 15, AMBER, True)
    ly += 28
    rows_left = max(0, int((y1 - 40 - ly) // 24))
    for marker in sorted(scene["markers"], key=lambda m: m["from_centre_m"])[:rows_left]:
        left = marker["commodity"] or "Unknown"
        if marker["rigs"]:
            left += "  %sR" % marker["rigs"]
        state = " ".join(p for p in (marker["amount"], marker["density"]) if p)
        circle(lx + 8, ly + 10, 6, fill=PLOT if marker["hollow"] else marker["colour"],
               outline=marker["colour"], line=2 if marker["hollow"] else 1)
        text(lx + 24, ly, left, 14, DIM if marker["hollow"] else TEXT)
        text(scene["size"][0] - 24, ly, "%s  %s  %s" % (state.replace(" ", " / ") if state.count(" ") == 1 else state,
                                                       metres_text(marker["from_centre_m"]),
                                                       marker["compass"]), 13, DIM, False, "ra")
        ly += 24
    if scene["note"]:
        text(lx, y1 - 22, scene["note"], 14, DIM)

    text(24, scene["size"][1] - 30, scene["footer"], 14, DIM)
    return big.resize((width, height), Image.LANCZOS)


def render_map(rows, **kwargs):
    """The picture for these rows. Returns (image, scene)."""
    scene = build_scene(rows, **kwargs)
    return draw_scene(scene), scene


# -- files, clipboard ---------------------------------------------------------

def _clean(text, limit=40):
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(text or "")).strip("_")
    return text[:limit] or "x"


def picture_name(system, body, signal="", when=None):
    """maps\\<system>_<body>_<signal>_<yyyymmdd-hhmm>.png, safe on Windows."""
    moment = time.gmtime(when if when is not None else time.time())
    return "%s_%s_%s_%s.png" % (_clean(system), _clean(body), _clean(signal or "0", 8),
                                time.strftime("%Y%m%d-%H%M", moment))


def pictures_dir(data_dir):
    return os.path.join(data_dir, "pictures")


def png_bytes(image, limit=MAX_BYTES):
    """The picture as PNG bytes, shrunk until it fits `limit`."""
    from PIL import Image
    while True:
        buf = io.BytesIO()
        image.save(buf, "PNG", optimize=True)
        data = buf.getvalue()
        if len(data) <= limit or min(image.size) <= 160:
            return data
        image = image.resize((int(image.size[0] * 0.8), int(image.size[1] * 0.8)),
                             Image.LANCZOS)


def save_picture(image, path):
    """Write the PNG. The path is returned; OSError is the caller's."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = png_bytes(image)
    temp = path + ".tmp"
    with open(temp, "wb") as handle:
        handle.write(data)
    os.replace(temp, path)
    return path


def tidy_pictures(folder, keep=PICTURES_KEPT):
    """Keep the newest `keep` pictures. Only files named like ours go."""
    try:
        mine = sorted((n for n in os.listdir(folder)
                       if re.match(r".+_\d{8}-\d{4}\.png$", n)),
                      key=lambda n: os.path.getmtime(os.path.join(folder, n)))
    except OSError:
        return 0
    gone = 0
    for name in mine[:max(0, len(mine) - keep)]:
        try:
            os.remove(os.path.join(folder, name))
            gone += 1
        except OSError:
            pass
    return gone


def dib_bytes(image):
    """The picture as a Windows DIB - a BMP without its 14-byte file header,
    which is what the clipboard's CF_DIB format holds."""
    buf = io.BytesIO()
    image.convert("RGB").save(buf, "BMP")
    data = buf.getvalue()
    if len(data) < 54 or struct.unpack("<I", data[14:18])[0] < 40:
        raise ValueError("not a DIB")
    return data[14:]


def copy_to_clipboard(image, tries=10, wait_s=0.03):
    """Put the picture on the Windows clipboard. (True, "") when it went,
    else (False, why). Windows only: elsewhere there is no clipboard format
    every program reads, and the saved file is the answer."""
    if os.name != "nt":
        return False, "Copying a picture needs Windows. It is saved - use the file."
    try:
        import ctypes
        from ctypes import wintypes
        data = dib_bytes(image)
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.OpenClipboard.argtypes = (wintypes.HWND,)
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.EmptyClipboard.restype = wintypes.BOOL
        user32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
        user32.SetClipboardData.restype = wintypes.HANDLE
        user32.CloseClipboard.restype = wintypes.BOOL
        kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
        kernel32.GlobalFree.argtypes = (wintypes.HGLOBAL,)
        cf_dib, gmem_moveable = 8, 0x0002
        for _attempt in range(tries):
            if user32.OpenClipboard(None):
                break
            time.sleep(wait_s)
        else:
            return False, "Another program has the clipboard open. Try again."
        try:
            user32.EmptyClipboard()
            handle = kernel32.GlobalAlloc(gmem_moveable, len(data))
            if not handle:
                return False, "Windows would not give memory for the picture."
            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                kernel32.GlobalFree(handle)
                return False, "Windows would not lock memory for the picture."
            ctypes.memmove(pointer, data, len(data))
            kernel32.GlobalUnlock(handle)
            if not user32.SetClipboardData(cf_dib, handle):
                kernel32.GlobalFree(handle)
                return False, "Windows would not take the picture."
            return True, ""
        finally:
            user32.CloseClipboard()
    except Exception as exc:
        return False, "The clipboard would not take the picture (%s)." % type(exc).__name__
