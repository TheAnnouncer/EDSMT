"""The welcome window's working parts that need no window (1.10040).

The welcome opens on the first start of each new version until "Don't show
this again" is ticked, and again from Settings > About and the Help menu.
Everything here is a plain function: whether it is due, how big the window
may be on a given screen and where it sits, which buttons it offers, what
is new in this version from the patch notes, and the HOW IT WORKS diagram -
drawn on anything that takes create_rectangle, create_line and create_text,
which is a Tk canvas in the app and a recorder in the checks. The window
itself is thin wiring in edsmt.py.
"""

# Where the useful links go. HEAD rather than a branch name, so a renamed
# branch never breaks the button.
REPO_URL = "https://github.com/TheAnnouncer/EDSMT"
GUIDE_URL = REPO_URL + "/blob/HEAD/docs/GUIDE.md"
ISSUES_URL = REPO_URL + "/issues"
CHANGELOG_URL = REPO_URL + "/blob/HEAD/CHANGELOG.md"
# Not a link: Quick start is the tour of the main window.
TOUR = "tour"

# (label, where it goes, the note when the mouse rests on it)
USEFUL_LINKS = (
    ("User guide", GUIDE_URL,
     "Every key, window and setting, in the order you meet them on a run."),
    ("Report a bug", ISSUES_URL,
     "Opens the issues page. Say which version, and what the status line said."),
    ("Changelog", CHANGELOG_URL, "What changed in each version."),
    ("Quick start", TOUR, "Closes this and shows you round the main window."),
)

# Where the community is. The Discord and the website for everybody; the
# member portal is the site's sign-in, open to every commander.
DISCORD_URL = "https://discord.gg/DjH9uZabet"
SITE_URL = "https://radioraxxla.com/EDSMT/"
PORTAL_URL = "https://radioraxxla.com/portal.html"
COMMUNITY_LINKS = (
    ("Join the Discord", DISCORD_URL,
     "The Radio Raxxla Discord: help, finds as they are made, and the "
     "patch notes the moment a version is out."),
    ("radioraxxla.com", SITE_URL,
     "The EDSMT page: downloads, the leaderboard, the weekly report and "
     "the live map."),
    ("Sign in to the site", PORTAL_URL,
     "Sign in with Discord for a member page of your own - any commander, "
     "in the squadron or not."),
)

# The call-out near the top. Most questions after an update are answered by
# a setting, so it is said loudly, once per version.
SETTINGS_CALL = (
    "CHECK THE SETTINGS",
    "Before your first run, look through Settings: your journal folder, the "
    "overlay and its backdrop, hotkeys and HOTAS buttons, voice, the theme "
    "and your Discord channels. New versions add new ones - each has a note "
    "when the mouse rests on it.")
SETTINGS_BUTTON = "Open Settings"
# The most headlines What's new lists; the rest are a click away.
WHATS_NEW_MOST = 8

# The window at its largest, and the screen it leaves free round it: the
# taskbar and the title bar have to fit as well.
MOST_W, MOST_H = 900, 1000
SCREEN_SPARE_W, SCREEN_SPARE_H = 80, 80
LEAST_W, LEAST_H = 560, 400
# A screen the toolkit cannot measure is taken to be a big one.
UNKNOWN_SCREEN = (2560, 1440)

# The diagram. The top row is where the facts come from and go to; the row
# under it is what EDSMT drives with them. (name, what it is)
TOP_ROW = (("ELITE DANGEROUS", "Journal.log + Status.json"),
           ("EDSMT", "reads, maps, guides"),
           ("COMMUNITY MAP", "edsmt.radioraxxla.com"))
LOW_ROW = (("OVERLAY", "compass, scope, targets"),
           ("MAP & TOOLS", "Find, Where to land, Earnings"),
           ("DISCORD", "session posts"))
DIAGRAM_TAG = "welcome"
# The colours the diagram uses when the palette handed in lacks one: the
# standard cockpit. Never what a theme wears - only what a broken one gets.
FALLBACK = {"PANEL": "#15100b", "RULE": "#3d2404", "ORANGE": "#ff7a18",
            "AMBER": "#ffb545", "MUTED": "#b49b80", "CYAN": "#37c6d4",
            "TEXT": "#e9dccd"}


def whats_new(notes, version, most=WHATS_NEW_MOST):
    """The headlines of `version` in the patch notes: the bold lead of each
    point under its "## version" heading, in order, at most `most`. A version
    that is not there, or no notes at all, is an empty list."""
    wanted = "## " + str(version or "").strip()
    found, inside = [], False
    for line in str(notes or "").splitlines():
        if line.startswith("## "):
            if inside:
                break
            inside = line.strip() == wanted
            continue
        if not inside or not line.startswith("- **"):
            continue
        lead = line[4:].split("**", 1)[0].strip().rstrip(".:;,").strip()
        if lead:
            found.append(lead)
        if len(found) >= max(0, int(most)):
            break
    return found


def read_whats_new(path, version, most=WHATS_NEW_MOST):
    """whats_new() from the patch notes file at `path`; nothing, never an
    error, when it cannot be read."""
    try:
        with open(path, encoding="utf-8") as handle:
            return whats_new(handle.read(), version, most)
    except (OSError, UnicodeDecodeError):
        return []


def welcome_due(settings, version):
    """Whether the welcome opens by itself at this start: on every start of a
    version until "Don't show this again" is ticked on it."""
    seen = ""
    if isinstance(settings, dict):
        seen = str(settings.get("welcome_seen_version") or "").strip()
    return seen != str(version or "").strip()


def _whole(value, fallback):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return number if number > 0 else fallback


def welcome_size(screen_w, screen_h):
    """(width, height) for the window on a screen this size: 900 x 1000 at
    most, less on a smaller screen, and never past its edges."""
    screen_w = _whole(screen_w, UNKNOWN_SCREEN[0])
    screen_h = _whole(screen_h, UNKNOWN_SCREEN[1])
    width = min(MOST_W, max(LEAST_W, screen_w - SCREEN_SPARE_W))
    height = min(MOST_H, max(LEAST_H, screen_h - SCREEN_SPARE_H))
    return min(width, screen_w), min(height, screen_h)


def place_over(app_box, size, screen):
    """(x, y) for a window of `size` centred over the app at `app_box`
    (x, y, width, height), moved back on to the screen where centring would
    put any of it off an edge."""
    ax, ay, aw, ah = (_whole(v, 0) if i >= 2 else int(v or 0)
                      for i, v in enumerate(app_box))
    width, height = size
    screen_w = _whole(screen[0], UNKNOWN_SCREEN[0])
    screen_h = _whole(screen[1], UNKNOWN_SCREEN[1])
    x = ax + (aw - width) // 2
    y = ay + (ah - height) // 2
    x = max(0, min(x, screen_w - width))
    y = max(0, min(y, screen_h - height))
    return x, y


def donate_buttons(donate_url, kofi_url):
    """[(label, link)] for the support buttons: one per link that is filled
    in, PayPal first. A blank link has no button - and so does anything
    that is not an https address."""
    out = []
    for label, url in (("Donate with PayPal", donate_url), ("Ko-fi", kofi_url)):
        url = str(url or "").strip()
        if url.lower().startswith("https://"):
            out.append((label, url))
    return out


def diagram_boxes(width, height):
    """The six boxes as {name: (x0, y0, x1, y1)}, top row left to right then
    the row under it, with gaps between the columns for the arrows."""
    margin = 6
    gap_x = max(20, min(64, int(width * 0.07)))
    box_w = max(60, (width - 2 * margin - 2 * gap_x) // 3)
    box_h = max(34, (height - 2 * margin) * 2 // 7)
    rows = ((margin, TOP_ROW), (height - margin - box_h, LOW_ROW))
    boxes = {}
    for top, row in rows:
        for column, (name, _what) in enumerate(row):
            x0 = margin + column * (box_w + gap_x)
            boxes[name] = (x0, top, x0 + box_w, top + box_h)
    return boxes


def diagram_arrows(boxes):
    """[(x0, y0, x1, y1, ends)] - ends is "last" or "both". The game into
    EDSMT; EDSMT to the community map and back; EDSMT down to each of the
    three things it drives."""
    gx0, gy0, gx1, gy1 = boxes["ELITE DANGEROUS"]
    ex0, ey0, ex1, ey1 = boxes["EDSMT"]
    cx0, cy0, cx1, cy1 = boxes["COMMUNITY MAP"]
    mid = (ey0 + ey1) / 2.0
    arrows = [(gx1 + 2, mid, ex0 - 2, mid, "last"),
              (ex1 + 2, mid, cx0 - 2, mid, "both")]
    width = ex1 - ex0
    for share, name in ((0.2, "OVERLAY"), (0.5, "MAP & TOOLS"), (0.8, "DISCORD")):
        bx0, by0, bx1, _by1 = boxes[name]
        arrows.append((ex0 + width * share, ey1 + 2, (bx0 + bx1) / 2.0, by0 - 2, "last"))
    return arrows


def _font_px(box_w, box_h, longest):
    """A size in pixels that gets the longest line across a box and both
    lines down it. In pixels, not points, so it measures the same as the
    boxes whatever the screen's scaling: a monospaced character runs a
    little under 0.62 of its size wide."""
    across = (box_w - 14) / (max(1, longest) * 0.62)
    return int(max(8, min(18, across, box_h * 0.26)))


def welcome_diagram(canvas, width, height, theme):
    """Draw HOW IT WORKS on `canvas`, `width` x `height`, in `theme` - a
    palette of the app's colour names (VOID, PANEL, RULE, ORANGE, AMBER,
    MUTED, CYAN...). Replaces what it drew last time. Returns the boxes."""
    colours = dict(FALLBACK)
    if isinstance(theme, dict):
        colours.update({k: v for k, v in theme.items() if k in FALLBACK and v})
    try:
        canvas.delete(DIAGRAM_TAG)
    except Exception:
        pass
    width, height = max(240, int(width)), max(120, int(height))
    boxes = diagram_boxes(width, height)
    names = dict(TOP_ROW + LOW_ROW)
    longest = max(len(text) for pair in TOP_ROW + LOW_ROW for text in pair)
    some_box = next(iter(boxes.values()))
    size = _font_px(some_box[2] - some_box[0], some_box[3] - some_box[1], longest)
    for x0, y0, x1, y1, ends in diagram_arrows(boxes):
        canvas.create_line(x0, y0, x1, y1, fill=colours["ORANGE"], width=2,
                           arrow=ends, arrowshape=(9, 11, 4),
                           tags=(DIAGRAM_TAG, "arrow"))
    for name, (x0, y0, x1, y1) in boxes.items():
        home = name == "EDSMT"
        canvas.create_rectangle(x0, y0, x1, y1, fill=colours["PANEL"],
                                outline=colours["ORANGE"] if home else colours["RULE"],
                                width=2 if home else 1, tags=(DIAGRAM_TAG, "box"))
        # The HUD's corner brackets, a short arm each way at every corner.
        arm = min(10, (x1 - x0) // 6, (y1 - y0) // 3)
        for cx, dx in ((x0, 1), (x1, -1)):
            for cy, dy in ((y0, 1), (y1, -1)):
                canvas.create_line(cx + dx * arm, cy, cx, cy, cx, cy + dy * arm,
                                   fill=colours["AMBER"], width=2,
                                   tags=(DIAGRAM_TAG, "bracket"))
        middle = (x0 + x1) / 2.0
        title = colours["CYAN"] if name == "ELITE DANGEROUS" else \
            colours["ORANGE"] if home else colours["AMBER"]
        canvas.create_text(middle, y0 + (y1 - y0) * 0.36, text=name, fill=title,
                           font=("Consolas", -size, "bold"), tags=(DIAGRAM_TAG, "name"))
        canvas.create_text(middle, y0 + (y1 - y0) * 0.70, text=names[name],
                           fill=colours["MUTED"], font=("Consolas", -max(7, size - 1)),
                           tags=(DIAGRAM_TAG, "what"))
    return boxes
