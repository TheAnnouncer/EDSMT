"""1.10040: the welcome window, on the first start of each new version.

What it says and does, in two halves. The first needs no display: whether
it is due, how big it may be on a given screen, which buttons it offers,
and the HOW IT WORKS diagram, drawn here on a recorder with every theme.
The second drives the real window on the real toolkit under xvfb: it opens
on a new version, stays shut once ticked, opens again from Settings > About
and from Help, and fits a small screen and a large one.

    python tests/test_110040_welcome.py
"""
import os, sys, json, glob, re, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-welcome-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def section(title):
    def wrap(fn):
        print("== " + title + " ==")
        try:
            fn()
        except Exception as exc:
            import traceback
            check(title + " (ran to the end)", False, "%s: %s" % (type(exc).__name__, exc))
            traceback.print_exc(limit=8)
        return fn
    return wrap


import welcome as WL      # noqa: E402
import edonline as EDO    # noqa: E402
import overlay as OV      # noqa: E402

PAYPAL = "https://www.paypal.com/donate/?hosted_button_id=UQJQ955Z7AA68"


class Recorder:
    """A canvas that remembers what was drawn on it."""

    def __init__(self):
        self.items = []

    def _add(self, kind, coords, kw):
        flat = []
        for c in coords:
            if isinstance(c, (tuple, list)):
                flat.extend(float(v) for v in c)
            else:
                flat.append(float(c))
        self.items.append({"kind": kind, "coords": flat, "kw": dict(kw)})
        return len(self.items)

    def create_rectangle(self, *coords, **kw):
        return self._add("rectangle", coords, kw)

    def create_line(self, *coords, **kw):
        return self._add("line", coords, kw)

    def create_polygon(self, *coords, **kw):
        return self._add("polygon", coords, kw)

    def create_text(self, *coords, **kw):
        return self._add("text", coords, kw)

    def delete(self, *tags):
        self.items = [i for i in self.items
                      if not (set(tags) & set(_tags(i)) or "all" in tags)]


def _tags(item):
    tags = item["kw"].get("tags", ())
    return (tags,) if isinstance(tags, str) else tuple(tags)


@section("due on the first start of each new version, until ticked")
def _due():
    check("a new install has never seen it", WL.welcome_due({}, "1.10040"))
    check("nor has a commander who never had the key", WL.welcome_due(
        {"asked_to_share": True, "tour_done": True}, "1.10040"))
    check("a file from an older version shows it again",
          WL.welcome_due({"welcome_seen_version": "1.10039"}, "1.10040"))
    check("ticked on this version, it stays shut",
          not WL.welcome_due({"welcome_seen_version": "1.10040"}, "1.10040"))
    check("no settings at all is a first start", WL.welcome_due(None, "1.10040"))


@section("the window's size on a small screen and a large one")
def _size():
    w, h = WL.welcome_size(2560, 1440)
    check("on 2560x1440 it is the full 900 x 1000", (w, h) == (900, 1000), (w, h))
    w, h = WL.welcome_size(1280, 720)
    check("on 1280x720 it fits the screen, with room for the taskbar",
          w <= 1280 - 40 and h <= 720 - 60 and w >= 560 and h >= 400, (w, h))
    check("and it is shorter than the full height, so the middle scrolls", h < 1000, h)
    w, h = WL.welcome_size(800, 480)
    check("even a tiny screen is never overrun", w <= 800 and h <= 480, (w, h))
    check("a screen the toolkit cannot measure gets the full size",
          WL.welcome_size(None, None) == (900, 1000), WL.welcome_size(None, None))
    x, y = WL.place_over((100, 50, 1240, 780), (900, 640), (1280, 720))
    check("centred over the app, across", x == 270, x)
    check("and pulled back on to the screen where centring would push it off",
          y == 720 - 640, y)
    x, y = WL.place_over((2000, 900, 400, 300), (900, 1000), (2560, 1440))
    check("never off the right or the bottom", x + 900 <= 2560 and y + 1000 <= 1440, (x, y))
    x, y = WL.place_over((-500, -300, 400, 300), (900, 1000), (2560, 1440))
    check("nor off the left or the top", x >= 0 and y >= 0, (x, y))


@section("support: the PayPal link, and a blank link hides its button")
def _donate():
    check("the PayPal link is in edonline, where it is filled in once",
          EDO.DONATE_URL == PAYPAL, EDO.DONATE_URL)
    check("Ko-fi is blank until there is one", EDO.KOFI_URL == "", EDO.KOFI_URL)
    check("so one button: Donate with PayPal",
          WL.donate_buttons(PAYPAL, "") == [("Donate with PayPal", PAYPAL)],
          WL.donate_buttons(PAYPAL, ""))
    check("both blank: no buttons at all", WL.donate_buttons("", "  ") == [])
    both = WL.donate_buttons(PAYPAL, "https://ko-fi.com/example")
    check("both filled in: two, PayPal first",
          [label for label, _url in both] == ["Donate with PayPal", "Ko-fi"], both)
    check("a link that is not https is not offered",
          WL.donate_buttons("javascript:alert(1)", "http://example.com") == [])


@section("useful links: every button has a link or an action")
def _links():
    labels = [label for label, _target, _note in WL.USEFUL_LINKS]
    check("User guide, Report a bug, Changelog, Quick start",
          labels == ["User guide", "Report a bug", "Changelog", "Quick start"], labels)
    for label, target, note in WL.USEFUL_LINKS:
        ok = target == WL.TOUR or str(target).startswith(
            "https://github.com/TheAnnouncer/EDSMT")
        check("%s goes somewhere: %s" % (label, target), ok and note, (target, note))
    targets = dict((label, target) for label, target, _n in WL.USEFUL_LINKS)
    check("the guide is docs/GUIDE.md and the changelog CHANGELOG.md",
          targets["User guide"].endswith("/docs/GUIDE.md")
          and targets["Changelog"].endswith("/CHANGELOG.md"), targets)
    check("a bug goes to the issues page", targets["Report a bug"].endswith("/issues"))
    check("Quick start is the tour", targets["Quick start"] == WL.TOUR)


@section("the community: the Discord, the website and the member portal")
def _community():
    links = dict((label, url) for label, url, _note in WL.COMMUNITY_LINKS)
    check("Join the Discord, radioraxxla.com, Sign in to the site - in that order",
          [label for label, _u, _n in WL.COMMUNITY_LINKS]
          == ["Join the Discord", "radioraxxla.com", "Sign in to the site"], links)
    check("the Discord is the Radio Raxxla invite", links["Join the Discord"] == "https://discord.gg/DjH9uZabet")
    check("the website is the EDSMT page on radioraxxla.com",
          links["radioraxxla.com"] == "https://radioraxxla.com/EDSMT/")
    check("and signing in is the member portal, for everybody",
          links["Sign in to the site"] == "https://radioraxxla.com/portal.html")
    check("every one is https, with a note", all(u.startswith("https://") and n
                                                  for _l, u, n in WL.COMMUNITY_LINKS))
    check("the portal is offered to every commander, in the squadron or not",
          "squadron or not" in dict((l, n) for l, _u, n in WL.COMMUNITY_LINKS)["Sign in to the site"])


SAMPLE_NOTES = """# EDSMT - patch notes

## 1.10041

- **Something later** that is not this version.

## 1.10040

### New - first

- **A welcome window** on the first start.
  More words on the next line.
- **The EDSMT logo**, on the welcome window.
- A line with no bold lead is skipped.

### Fixed

- **A fix:** that matters.

## 1.10039

- **Something older**.
"""


@section("what's new: the headlines of this version's patch notes")
def _whats_new():
    got = WL.whats_new(SAMPLE_NOTES, "1.10040")
    check("each bold lead of this version, in order, and nothing from the others",
          got == ["A welcome window", "The EDSMT logo", "A fix"], got)
    check("at most the number asked for", WL.whats_new(SAMPLE_NOTES, "1.10040", most=2)
          == ["A welcome window", "The EDSMT logo"])
    check("a version that is not there: nothing", WL.whats_new(SAMPLE_NOTES, "1.20000") == [])
    check("nothing to read: nothing", WL.whats_new("", "1.10040") == []
          and WL.whats_new(None, "1.10040") == [])
    check("a file that is not there: nothing, never an error",
          WL.read_whats_new(os.path.join(TMP, "no-such-notes.md"), "1.10040") == [])
    real = WL.read_whats_new(os.path.join(REPO, "CHANGELOG.md"), EDO.APP_VERSION)
    check("the real patch notes have headlines for this version", len(real) >= 5, real)
    for spec in ("EDSMT.spec", "EDSMT-onefile.spec"):
        text = open(os.path.join(REPO, "build", spec), encoding="utf-8").read()
        check("%s ships CHANGELOG.md, so the built app can read it" % spec,
              re.search(r'os\.path\.join\(ROOT, "CHANGELOG\.md"\)', text) is not None)


@section("CHECK THE SETTINGS: said loudly, with a button to go there")
def _check_settings():
    check("the call-out says CHECK THE SETTINGS", WL.SETTINGS_CALL[0] == "CHECK THE SETTINGS")
    words = WL.SETTINGS_CALL[1]
    for thing in ("journal", "overlay", "hotkeys", "theme", "Discord"):
        check("and names %s" % thing, thing in words, words)
    check("the button is Open Settings", WL.SETTINGS_BUTTON == "Open Settings")


TITLES = ["ELITE DANGEROUS", "EDSMT", "COMMUNITY MAP", "OVERLAY", "MAP & TOOLS", "DISCORD"]
SUBTITLES = ["Journal.log + Status.json", "reads, maps, guides", "edsmt.radioraxxla.com",
             "compass, scope, targets", "Find, Where to land, Earnings", "session posts"]


def _diagram(theme_name, w=840, h=250):
    canvas = Recorder()
    palette = OV.theme_palette(theme_name)
    WL.welcome_diagram(canvas, w, h, palette)
    return canvas, palette


@section("HOW IT WORKS: three boxes over three, joined by arrows")
def _diagram_shape():
    canvas, palette = _diagram("gold")
    boxes = [i for i in canvas.items if i["kind"] == "rectangle" and "box" in _tags(i)]
    check("six boxes", len(boxes) == 6, len(boxes))
    top = sorted((b for b in boxes if b["coords"][1] < 125), key=lambda b: b["coords"][0])
    low = sorted((b for b in boxes if b["coords"][1] >= 125), key=lambda b: b["coords"][0])
    check("three in a row along the top, three under them", len(top) == 3 and len(low) == 3,
          (len(top), len(low)))
    words = [i["kw"].get("text") for i in canvas.items if i["kind"] == "text"]
    check("each box named, game to community map, then what it drives",
          [t for t in words if t in TITLES] == TITLES, words)
    check("and what each one is, in a line under its name",
          [t for t in words if t in SUBTITLES] == SUBTITLES, words)
    arrows = [i for i in canvas.items if i["kind"] == "line" and i["kw"].get("arrow")]
    check("five arrows", len(arrows) == 5, len(arrows))
    check("the community map's goes both ways - finds up, everyone's back",
          sum(1 for a in arrows if a["kw"]["arrow"] == "both") == 1,
          [a["kw"]["arrow"] for a in arrows])
    game, app, crowd = top
    first = [a for a in arrows if a["kw"]["arrow"] == "last"][0]["coords"]
    check("the game's arrow leaves the game box and ends at EDSMT's",
          abs(first[0] - game["coords"][2]) <= 6 and abs(first[-2] - app["coords"][0]) <= 6,
          (first, game["coords"], app["coords"]))
    down = [a for a in arrows if a["coords"][-1] > a["coords"][1] + 10]
    check("three arrows go down from EDSMT to the overlay, the map and Discord",
          len(down) == 3 and all(app["coords"][0] - 1 <= a["coords"][0] <= app["coords"][2] + 1
                                 for a in down), [a["coords"] for a in down])


@section("the diagram draws with every theme, in the theme's colours, inside the canvas")
def _diagram_themes():
    names = list(OV.THEME_ORDER)
    check("every theme is tried: the fourteen, the twelve Powers and the game's",
          len(names) == 27 and "game" in names
          and sum(1 for n in names if n.startswith("pp_")) == 12, len(names))
    for name in names:
        for w, h in ((840, 250), (520, 230)):
            canvas, palette = _diagram(name, w, h)
            colours = set(palette.values())
            used = set()
            for item in canvas.items:
                for key in ("fill", "outline"):
                    value = item["kw"].get(key)
                    if value:
                        used.add(value)
            outside = [i for i in canvas.items
                       if any(not (-0.5 <= v <= (w if n % 2 == 0 else h) + 0.5)
                              for n, v in enumerate(i["coords"]))]
            check("%s at %dx%d: drawn, every colour the theme's own, nothing off the edge"
                  % (name, w, h),
                  len(canvas.items) >= 23 and used <= colours and not outside,
                  (len(canvas.items), sorted(used - colours), outside[:2]))
    canvas = Recorder()
    WL.welcome_diagram(canvas, 840, 250, OV.theme_palette("gold"))
    count = len(canvas.items)
    WL.welcome_diagram(canvas, 840, 250, OV.theme_palette("gold"))
    check("drawing it again replaces it rather than piling up",
          len(canvas.items) == count, (count, len(canvas.items)))
    WL.welcome_diagram(canvas, 840, 250, {})
    check("a palette with nothing in it still draws, in the standard colours",
          len(canvas.items) == count)


import logo as LG          # noqa: E402

SMALL, LARGE = "edsmt-badge-256.png", "edsmt-badge-512.png"
# What this system wears: edsmt.ico through iconbitmap on Windows, the badge elsewhere.
WORN_HERE = os.path.join(REPO, "edsmt.ico") if sys.platform == "win32" else os.path.join(REPO, "images", SMALL)


@section("the logo: the badge's size for the screen, and the icon each system wears")
def _logo():
    from PIL import Image
    check("the welcome shows it about 160 pixels across", LG.WELCOME_PX == 160)
    check("at 100%, 125% and 150% scaling the 256 file does, shrunk",
          [LG.badge_file(160, s) for s in (1.0, 1.25, 1.5)] == [SMALL] * 3)
    check("at 175% and 200% the 512 file, so it stays sharp",
          [LG.badge_file(160, s) for s in (1.75, 2.0)] == [LARGE] * 2)
    check("a scaling that cannot be read is taken as 100%",
          LG.badge_file(160, None) == SMALL and LG.badge_file(160, "x") == SMALL)
    for name, size in ((SMALL, 256), (LARGE, 512)):
        with Image.open(os.path.join(REPO, "images", name)) as img:
            ok = img.size == (size, size) and img.mode == "RGBA" \
                and img.getpixel((0, 0))[3] == 0
        check("%s is shipped: round, %d px, with clear corners" % (name, size), ok)
    with Image.open(os.path.join(REPO, "edsmt.ico")) as ico:
        sizes = set(ico.info.get("sizes") or ())
    check("edsmt.ico carries 16 to 256 px",
          {(16, 16), (32, 32), (48, 48), (256, 256)} <= sizes, sorted(sizes))
    folder = os.path.join(TMP, "logo-both")
    os.makedirs(os.path.join(folder, "images"))
    for name in ("edsmt.ico", "radioraxxla.ico", "images/" + SMALL):
        open(os.path.join(folder, name), "wb").close()
    check("Windows: EDSMT's own .ico, the Radio Raxxla one only behind it",
          LG.icon_choices(folder, "win32") == [
              ("bitmap", os.path.join(folder, "edsmt.ico")),
              ("bitmap", os.path.join(folder, "radioraxxla.ico"))],
          LG.icon_choices(folder, "win32"))
    os.remove(os.path.join(folder, "edsmt.ico"))
    check("with edsmt.ico missing, the Radio Raxxla one",
          LG.icon_choices(folder, "win32") == [("bitmap", os.path.join(folder, "radioraxxla.ico"))])
    check("Linux: the badge, as a picture",
          LG.icon_choices(folder, "linux") == [("photo", os.path.join(folder, "images", SMALL))],
          LG.icon_choices(folder, "linux"))
    check("nothing there, nothing to wear",
          LG.icon_choices(os.path.join(TMP, "nowhere"), "win32") == []
          and LG.icon_choices(os.path.join(TMP, "nowhere"), "linux") == [])


# ---------------------------------------------------------------------------
# The real window
# ---------------------------------------------------------------------------

try:
    import tkinter
    tkinter.Tk().destroy()
    HAVE_DISPLAY = True
except Exception as _exc:
    HAVE_DISPLAY = False
    print("  SKIP  the welcome window needs a display (%s). Run it under xvfb-run." % _exc)

if HAVE_DISPLAY:
    OV.foreground_is_game = lambda: None
    import edsmt as A
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    OPENED = []
    A.open_link = lambda url, *a, **k: OPENED.append(url) or True
    STATE = {"app": None}

    def write_settings(**extra):
        data = {"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS}
        data.update(extra)
        with open(A.SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def saved():
        with open(A.SETTINGS_FILE, encoding="utf-8") as fh:
            return json.load(fh)

    def start():
        if STATE["app"] is not None:
            try:
                STATE["app"].destroy()
            except Exception:
                pass
        app = A.EDSMT()
        app.geometry("1400x900+0+0")
        app.updates.check = lambda *args, **kwargs: None
        STATE["app"] = app
        return app

    def pump(times=3):
        app = STATE["app"]
        for _ in range(times):
            try:
                app.update_idletasks()
                app.update()
            except Exception:
                pass

    def settle_until(cond, seconds=6.0):
        """Wait for what the check is about, not for a number of loops."""
        end = time.time() + seconds
        while time.time() < end:
            try:
                if cond():
                    return True
            except Exception:
                pass
            pump(1)
            time.sleep(0.02)
        return bool(cond())

    def welcomes():
        app = STATE["app"]
        return [w for w in app.winfo_children()
                if isinstance(w, A.WelcomeWindow) and w.winfo_exists()]

    def walk(widget):
        for child in widget.winfo_children():
            yield child
            yield from walk(child)

    def texts(widget):
        out = []
        for w in walk(widget):
            try:
                out.append(str(w.cget("text")))
            except Exception:
                pass
        return out

    def button(widget, text):
        return next((w for w in walk(widget) if isinstance(w, A.ctk.CTkButton)
                     and str(w.cget("text")) == text), None)

    @section("a new version: the welcome opens by itself, once, and holds the keyboard")
    def _opens():
        write_settings(welcome_seen_version="1.10000")
        app = start()
        check("it opens a moment after the window",
              settle_until(lambda: len(welcomes()) == 1), app.winfo_children())
        win = welcomes()[0]
        settle_until(lambda: app.grab_current() is win, 3)
        check("and nothing behind it can be typed into until it is closed",
              app.grab_current() is win, str(app.grab_current()))
        words = texts(win)
        check("it wears the EDSMT logo too, not the toolkit's",
              win.icon_worn == WORN_HERE, win.icon_worn)
        check("Welcome to EDSMT, with the version beside it",
              "Welcome to EDSMT" in words and A.APP_VERSION in words, words[:8])
        check("and what it is in one line",
              "Surface mining for the Rhino SRV, read from your journal" in words)
        check("the diagram is drawn on its canvas", len(win.diagram.find_all()) >= 23,
              len(win.diagram.find_all()))
        settle_until(lambda: win.diagram.winfo_width() > 300, 3)
        win._draw_diagram()
        pump(2)
        canvas = win.diagram
        boxes = [canvas.coords(i) for i in canvas.find_withtag("box")]
        spill = []
        for item in canvas.find_withtag("what") + canvas.find_withtag("name"):
            x0, y0, x1, y1 = canvas.bbox(item)
            if not any(b[0] <= x0 and x1 <= b[2] and b[1] <= y0 and y1 <= b[3] for b in boxes):
                spill.append(canvas.itemcget(item, "text"))
        check("every word of the diagram is inside its box, on the real toolkit",
              boxes and not spill, spill)
        image = win.badge.cget("image") if win.badge is not None else None
        check("the EDSMT badge at the top, about 160 pixels across",
              isinstance(image, A.ctk.CTkImage) and image.cget("size") == (160, 160)
              and win.scroll.winfo_children()[0] is win.badge,
              image.cget("size") if image is not None else None)
        check("the community map is said plainly",
              any("Every deposit you mark goes on the community map" in t for t in words))
        check("Support Radio Raxxla, and one button: Donate with PayPal",
              "SUPPORT RADIO RAXXLA" in words and button(win, "Donate with PayPal") is not None
              and button(win, "Ko-fi") is None, [t for t in words if "Donate" in t or "Ko" in t])
        button(win, "Donate with PayPal").invoke()
        check("which opens PayPal in the browser", OPENED[-1:] == [PAYPAL], OPENED)
        for label, target, _note in WL.USEFUL_LINKS:
            if target == WL.TOUR:
                continue
            found = button(win, label)
            check("%s is a button" % label, found is not None)
            if found is not None:
                found.invoke()
                check("and it opens %s" % target, OPENED[-1:] == [target], OPENED[-1:])
        check("CHECK THE SETTINGS stands out near the top",
              "CHECK THE SETTINGS" in words and words.index("CHECK THE SETTINGS")
              < words.index("ONE MAP, EVERYBODY'S"), words[:14])
        check("what's new in this version, from the patch notes",
              ("WHAT'S NEW IN " + A.APP_VERSION) in words
              and all(("\u2022  " + h) in words for h in win.headlines)
              and len(win.headlines) >= 5, (win.headlines, words[:30]))
        notes = button(win, "Full patch notes")
        check("with the full patch notes a click away", notes is not None)
        if notes is not None:
            notes.invoke()
            check("which open the changelog", OPENED[-1:] == [WL.CHANGELOG_URL], OPENED[-1:])
        check("JOIN THE COMMUNITY", "JOIN THE COMMUNITY" in words)
        for label, url, _note in WL.COMMUNITY_LINKS:
            found = button(win, label)
            check("%s is a button" % label, found is not None)
            if found is not None:
                found.invoke()
                check("and it opens %s" % url, OPENED[-1:] == [url], OPENED[-1:])
        check("a box to stop it, and Get Started",
              isinstance(win.never_box, A.ctk.CTkCheckBox)
              and button(win, "Get Started") is not None)
        check("the footer is laid out first, so the scroll gives way and never the button",
              win.pack_slaves()[0] is win.footer, win.pack_slaves())
        pump(2)
        before = time.time()
        win.answer(True)
        check("Get Started closes it",
              settle_until(lambda: not welcomes(), 3) and time.time() - before < 3)
        check("and gives the keyboard back", settle_until(lambda: app.grab_current() is None, 3),
              str(app.grab_current()))
        check("not ticked, so nothing is written: it comes back next start",
              saved().get("welcome_seen_version") == "1.10000", saved().get("welcome_seen_version"))

    @section("never over the game: with Elite in front it waits to be looked at")
    def _game_in_front():
        front = {"game": True}
        OV.foreground_is_game = lambda: front["game"]
        kept_wait = A.TOUR_WAIT_MS
        A.TOUR_WAIT_MS = 300
        try:
            app = start()
            end = time.time() + 2.0
            while time.time() < end:
                pump(1)
                time.sleep(0.02)
            check("due, but the game is in front: nothing opens", not welcomes(), welcomes())
            check("and nothing holds the keyboard", app.grab_current() is None)
            front["game"] = False
            check("EDSMT looked at, it opens", settle_until(lambda: len(welcomes()) == 1, 4))
            win = welcomes()[0]
            win.answer(True)
            settle_until(lambda: not welcomes(), 3)
            front["game"] = True
            win = app.show_welcome(force=True)
            check("asked for from Help, it opens whatever is in front",
                  settle_until(lambda: len(welcomes()) == 1, 3))
            win.answer(True)
            settle_until(lambda: not welcomes(), 3)
        finally:
            OV.foreground_is_game = lambda: None
            A.TOUR_WAIT_MS = kept_wait

    @section("ticked, it stays shut on this version")
    def _ticked():
        app = start()
        check("still due without the tick, so it opens again",
              settle_until(lambda: len(welcomes()) == 1))
        win = welcomes()[0]
        win.never_box.select()
        button(win, "Get Started").invoke()
        check("closed", settle_until(lambda: not welcomes(), 3))
        check("the tick is kept as this version",
              saved().get("welcome_seen_version") == A.APP_VERSION
              and app.settings.get("welcome_seen_version") == A.APP_VERSION,
              saved().get("welcome_seen_version"))
        app = start()
        end = time.time() + 2.5
        while time.time() < end:
            pump(1)
            time.sleep(0.02)
        check("the next start opens nothing", not welcomes(), welcomes())
        check("and nothing holds the keyboard", app.grab_current() is None)

    @section("Open Settings: the welcome goes and Settings opens")
    def _open_settings():
        app = STATE["app"]
        win = app.show_welcome(force=True)
        settle_until(lambda: len(welcomes()) == 1)
        go = button(win, WL.SETTINGS_BUTTON)
        check("the call-out has its button", go is not None)
        if go is None:
            return
        go.invoke()
        check("the welcome closes", settle_until(lambda: not welcomes(), 3))
        opened = []
        settle_until(lambda: opened.extend(w for w in app.winfo_children()
                                           if isinstance(w, A.SettingsWindow)
                                           and w.winfo_exists()) or opened, 4)
        check("and Settings is open", len(opened) >= 1, app.winfo_children())
        check("with the keyboard given back to the app first",
              app.grab_current() is not win, str(app.grab_current()))
        for w in opened:
            try:
                w.destroy()
            except Exception:
                pass
        pump(2)

    @section("again from Settings > About, and from Help")
    def _again():
        app = STATE["app"]
        win = A.SettingsWindow(app)
        pump(4)
        about = win.pages["About"]
        again = button(about, "Welcome again")
        check("About has Welcome again", again is not None, texts(about)[:20])
        check("and the same PayPal button", button(about, "Donate with PayPal") is not None)
        again.invoke()
        check("it opens the welcome, seen or not", settle_until(lambda: len(welcomes()) == 1))
        welcomes()[0].answer(True)
        settle_until(lambda: not welcomes(), 3)
        try:
            win.destroy()
        except Exception:
            pass
        check("the top bar has a Help button", isinstance(app.btn_help, A.ctk.CTkButton))
        labels = [app.help_menu.entrycget(i, "label")
                  for i in range(app.help_menu.index("end") + 1)]
        check("its menu: Welcome, Show me round, User guide, Report a bug, Changelog",
              labels == ["Welcome", "Show me round", "User guide", "Report a bug", "Changelog"],
              labels)
        app.help_menu.invoke(0)
        check("Welcome opens it", settle_until(lambda: len(welcomes()) == 1))
        check("only one at a time", (app.show_welcome(force=True) is welcomes()[0])
              and len(welcomes()) == 1, welcomes())
        welcomes()[0].answer(True)
        settle_until(lambda: not welcomes(), 3)
        OPENED.clear()
        app.help_menu.invoke(4)
        check("Changelog opens the changelog", OPENED == [dict(
            (l, t) for l, t, _n in WL.USEFUL_LINKS)["Changelog"]], OPENED)
        toured = []
        app.start_tour = lambda force=False: toured.append(force) or True
        app.help_menu.invoke(1)
        check("Show me round runs the tour", toured == [True], toured)
        win = app.show_welcome(force=True)
        settle_until(lambda: len(welcomes()) == 1)
        button(win, "Quick start").invoke()
        check("Quick start closes the welcome and runs the tour",
              settle_until(lambda: not welcomes(), 3) and toured[-1:] == [True], toured)
        del app.start_tour

    @section("it fits 1280x720, scrolling, and 2560x1440")
    def _fits():
        app = STATE["app"]
        for screen, scrolls in (((1280, 720), True), ((2560, 1440), None)):
            win = A.WelcomeWindow(app, screen=screen)
            settle_until(lambda: win.winfo_ismapped(), 3)
            pump(4)
            w, h = win.size_wanted
            check("on %dx%d the window is %dx%d, inside the screen"
                  % (screen + (w, h)), w <= screen[0] and h <= screen[1]
                  and (w, h) == WL.welcome_size(*screen), (w, h))
            inner = win.scroll.winfo_children()
            need = sum(c.winfo_reqheight() for c in inner)
            room = h - win.footer.winfo_reqheight()
            if scrolls:
                check("the middle is taller than the room left, so it scrolls",
                      need > room, (need, room))
            got = win.geometry().split("+")[0]
            check("the window really is that size", got == "%dx%d" % (w, h), got)
            win.answer(True)
            settle_until(lambda: not welcomes(), 3)

    class IconRecorder:
        """A window that remembers which icon it was asked to wear."""

        def __init__(self, refuse=()):
            self.calls, self.refuse = [], refuse

        def iconbitmap(self, path=None, **kw):
            if os.path.basename(str(path)) in self.refuse:
                raise RuntimeError("bitmap not defined")
            self.calls.append(("iconbitmap", path))

        def iconphoto(self, default, *images):
            self.calls.append(("iconphoto", default))

    @section("the main window wears the EDSMT logo")
    def _icon():
        app = STATE["app"]
        check("on this system, its own picture (edsmt.ico on Windows, the badge elsewhere)",
              app.icon_worn == WORN_HERE, app.icon_worn)
        win = IconRecorder()
        check("on Windows, edsmt.ico through iconbitmap",
              A.wear_icon(win, folder=REPO, platform="win32") == os.path.join(REPO, "edsmt.ico")
              and win.calls == [("iconbitmap", os.path.join(REPO, "edsmt.ico"))], win.calls)
        old = os.path.join(TMP, "old-icon")
        os.makedirs(old)
        with open(os.path.join(REPO, "radioraxxla.ico"), "rb") as src, \
                open(os.path.join(old, "radioraxxla.ico"), "wb") as dst:
            dst.write(src.read())
        win = IconRecorder()
        check("with edsmt.ico missing, the Radio Raxxla icon instead",
              A.wear_icon(win, folder=old, platform="win32") == os.path.join(old, "radioraxxla.ico"),
              win.calls)
        win = IconRecorder(refuse=("edsmt.ico",))
        check("and the same if Windows will not take edsmt.ico",
              A.wear_icon(win, folder=REPO, platform="win32")
              == os.path.join(REPO, "radioraxxla.ico"), win.calls)
        win = IconRecorder()
        check("nothing to wear: nothing worn, nothing raised",
              A.wear_icon(win, folder=os.path.join(TMP, "nowhere"), platform="win32") == ""
              and win.calls == [])

    @section("the badge on About; without the file the welcome still works")
    def _badge():
        app = STATE["app"]
        win = A.SettingsWindow(app)
        pump(4)
        about = win.pages["About"]
        images = [w.cget("image") for w in walk(about) if isinstance(w, A.ctk.CTkLabel)
                  and isinstance(w.cget("image"), A.ctk.CTkImage)]
        check("About shows the badge", len(images) == 1, images)
        win.destroy()
        pump(2)
        kept = A.IMAGES_DIR
        broken = os.path.join(TMP, "broken-images")
        os.makedirs(broken)
        try:
            for case, folder in (("missing", os.path.join(TMP, "no-images")), ("unreadable", broken)):
                if case == "unreadable":
                    for name in (SMALL, LARGE):
                        with open(os.path.join(broken, name), "wb") as handle:
                            handle.write(b"not a picture at all")
                A.IMAGES_DIR = folder
                win = app.show_welcome(force=True)
                settle_until(lambda: len(welcomes()) == 1)
                check("badge %s: no picture, and the rest of the window is there" % case,
                      win.badge is None and "Welcome to EDSMT" in texts(win)
                      and button(win, "Get Started") is not None
                      and len(win.diagram.find_all()) >= 23)
                button(win, "Get Started").invoke()
                check("and Get Started still closes it (%s)" % case,
                      settle_until(lambda: not welcomes(), 3))
        finally:
            A.IMAGES_DIR = kept

    @section("a brand-new install: one window, the map said, then the tour")
    def _first():
        with open(A.SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump({"journal_dir": JOURNALS}, fh)
        app = start()
        toured = []
        app.start_tour = lambda force=False: toured.append(force) or True
        check("one window opens", settle_until(lambda: len(welcomes()) == 1))
        pump(10)
        check("one, not the welcome and the share notice both", len(welcomes()) == 1)
        check("the first question is recorded as put", app.settings.get("asked_to_share") is True)
        win = welcomes()[0]
        check("it says the finds go on the map with the name on them",
              any("with your CMDR name on it" in t for t in texts(win)))
        win.answer(True)
        check("Get Started closes it and the tour follows, as before",
              settle_until(lambda: not welcomes() and toured, 4), toured)
        del app.start_tour

    @section("every check that builds the main window says the welcome was seen")
    def _guard():
        quiet = []
        for path in sorted(glob.glob(os.path.join(HERE, "test_*.py"))):
            text = open(path, encoding="utf-8").read()
            if re.search(r"\bA\.EDSMT\(\)", text) and "welcome_seen_version" not in text:
                quiet.append(os.path.basename(path))
        check("a check that does not open it on purpose writes welcome_seen_version,"
              " so the window cannot land in the middle of it", not quiet, quiet)

    try:
        STATE["app"].destroy()
    except Exception:
        pass

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
