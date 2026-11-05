"""1.10040: the main window's chrome (#310).

Asked on 28 Oct: "UI needs to be improved". EDSMT keeps its own look - HUD
amber on navy, brackets - and its own words:

- a status strip under the top bar: CMDR, SHIP, SYSTEM, BODY, what you are
  in (DOCKED, LANDED, IN SRV...) and the overlay, each with a small glyph;
- the tool tabs as a chevron strip drawn on a canvas, the lit tab in the
  accent and F2-F8 on the tabs (tabstrip.py: the geometry and which tab a
  click lands on);
- a shortcut bar along the bottom: the F-keys and the rig keys on the left;
  SPACING Comfortable | Compact (ui_spacing - paddings and row heights from
  one table) and the theme name with < > arrows on the right;
- stat cards over the map: the session's tonnes, Cr/hr, rigs down and how
  much of the survey area has been swept.

The pure parts (tabstrip.py, uichrome.py) run anywhere; the window on the
real toolkit under xvfb:

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_chrome.py
"""
import os, sys, json, tempfile, time, types
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-chrome-")
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


import tabstrip as TS      # noqa: E402
import uichrome as UC      # noqa: E402


def mono(text):
    """Eight pixels a character, as a monospaced font measures."""
    return 8 * len(str(text))


def middle(tab):
    """A point well inside a tab's body: half way down, at its text."""
    return tab.text_x, TS_HEIGHT / 2.0


TS_HEIGHT = 32


@section("tabstrip: seven tabs, Map to Leaderboard, F2 to F8")
def _tabs():
    keys = [k for k, _l, _f in TS.TABS]
    check("the map then the six tools, in the top bar's order",
          keys == ["map", "find", "sites", "land", "earnings", "powerplay", "leaderboard"], keys)
    check("labelled as they always were",
          [l for _k, l, _f in TS.TABS] == ["Map", "Find", "My sites", "Where to land",
                                            "Earnings", "Powerplay", "Leaderboard"])
    check("F2 to F8, one each", [f for _k, _l, f in TS.TABS] == ["F2", "F3", "F4", "F5", "F6", "F7", "F8"])


@section("tabstrip: chevrons that interlock, inside the width they are given")
def _geometry():
    tabs = TS.layout(1600, TS_HEIGHT, mono)
    check("one chevron per tab", [t.key for t in tabs] == [k for k, _l, _f in TS.TABS])
    check("with room, every tab shows its F-key", all(t.keys_shown for t in tabs))
    check("the first starts at the left edge, square", tabs[0].x0 == 0
          and min(x for x, _y in tabs[0].points) == 0
          and sum(1 for x, _y in tabs[0].points if x == 0) == 2, tabs[0].points)
    check("the strip never runs past the width it is given",
          max(x for t in tabs for x, _y in t.points) <= 1600)
    point = TS.POINT
    ok = True
    for before, after in zip(tabs, tabs[1:]):
        ok &= after.x0 == before.x1 + TS.GAP
        ok &= (before.x1 + point, TS_HEIGHT / 2.0) in before.points
        ok &= (after.x0 + point, TS_HEIGHT / 2.0) in after.points
    check("each tab points right into the notch of the next, a seam apart", ok)
    widest = max(tabs, key=lambda t: t.x1 - t.x0)
    check("Where to land is the widest: a tab is as wide as its words",
          widest.key == "land", widest.key)
    check("the words sit in the middle of the tab's body",
          all(t.x0 < t.text_x < t.x1 for t in tabs))


@section("tabstrip: narrower, the F-keys go first, then the padding - never a tab")
def _narrow():
    wide = TS.layout(1600, TS_HEIGHT, mono)
    full = max(x for t in wide for x, _y in t.points)
    tabs = TS.layout(full - 10, TS_HEIGHT, mono)
    check("just too narrow for the F-keys: the keys go, the tabs stay",
          len(tabs) == 7 and not any(t.keys_shown for t in tabs))
    check("and it fits", max(x for t in tabs for x, _y in t.points) <= full - 10)
    short = TS.layout(1600, TS_HEIGHT, mono, keys=False)
    bare = max(x for t in short for x, _y in t.points)
    tabs = TS.layout(bare - 20, TS_HEIGHT, mono)
    check("tighter still: the padding shrinks and it still fits",
          max(x for t in tabs for x, _y in t.points) <= bare - 20, tabs[-1].x1)
    tabs = TS.layout(120, TS_HEIGHT, mono)
    check("a silly width still gives seven tabs and raises nothing", len(tabs) == 7)


@section("tabstrip: a click lands on the tab under it, or on nothing")
def _hit():
    tabs = TS.layout(1600, TS_HEIGHT, mono)
    for tab in tabs:
        x, y = middle(tab)
        check("the middle of %s is %s" % (tab.label, tab.key), TS.hit(tabs, x, y) == tab.key)
    first, second = tabs[0], tabs[1]
    tip_x = first.x1 + TS.POINT - 3
    check("the point of a tab belongs to it, even inside the next one's notch",
          TS.hit(tabs, tip_x, TS_HEIGHT / 2.0) == first.key, TS.hit(tabs, tip_x, TS_HEIGHT / 2.0))
    seam = second.x0 + TS.POINT - TS.GAP / 2.0
    check("the seam between a point and the next tab's notch belongs to neither",
          TS.hit(tabs, seam, TS_HEIGHT / 2.0) is None, TS.hit(tabs, seam, TS_HEIGHT / 2.0))
    check("above, below and past the end: nothing",
          TS.hit(tabs, 10, -2) is None and TS.hit(tabs, 10, TS_HEIGHT + 2) is None
          and TS.hit(tabs, 1599, TS_HEIGHT / 2.0) is None)
    check("an empty strip: nothing", TS.hit([], 5, 5) is None)


class State:
    """The journal reader's state, as far as the strip needs it."""

    def __init__(self, **kw):
        self.running = True
        self.cmdr, self.ship_type, self.system, self.body = "", "", "", ""
        self.docked = self.landed = self.in_srv = self.on_foot = False
        self.__dict__.update(kw)


@section("uichrome: the status strip's readouts follow the state")
def _cells():
    state = State(cmdr="Jameson", ship_type="type9", system="Ega", body="Ega 1", in_srv=True)
    cells = dict(UC.status_cells(state, overlay_on=True, overlay_locked=True))
    check("the six readouts, in order",
          [label for label, _v in UC.status_cells(state, True, True)]
          == ["CMDR", "SHIP", "SYSTEM", "BODY", "STATE", "OVERLAY"])
    check("the commander and system as the journal has them",
          cells["CMDR"] == "Jameson" and cells["SYSTEM"] == "Ega" and cells["BODY"] == "Ega 1")
    check("the ship by its name, not its symbol", cells["SHIP"] == "Type-9 Heavy", cells["SHIP"])
    check("an unknown ship as the journal names it",
          UC.ship_name("someshipnobodyhas") == "someshipnobodyhas"
          and UC.ship_name("") == "" and UC.ship_name("Python_NX") == "Python Mk II")
    check("in the SRV", cells["STATE"] == "IN SRV", cells["STATE"])
    check("the overlay up and locked", cells["OVERLAY"] == "ON", cells["OVERLAY"])
    words = {}
    for name, kw in (("DOCKED", {"docked": True}), ("LANDED", {"landed": True}),
                     ("ON FOOT", {"on_foot": True}), ("IN FLIGHT", {})):
        words[name] = dict(UC.status_cells(State(system="Ega", **kw), False, True))["STATE"]
    check("docked, landed, on foot or flying", all(k == v for k, v in words.items()), words)
    check("docked wins over landed: a pad is on the ground too",
          dict(UC.status_cells(State(docked=True, landed=True), False, True))["STATE"] == "DOCKED")
    check("the SRV wins over landed", dict(UC.status_cells(
        State(in_srv=True, landed=True), False, True))["STATE"] == "IN SRV")
    off = dict(UC.status_cells(State(running=False), overlay_on=False, overlay_locked=True))
    check("the game shut: a dash for each, and the overlay off",
          all(off[k] == "-" for k in ("CMDR", "SHIP", "SYSTEM", "BODY", "STATE"))
          and off["OVERLAY"] == "OFF", off)
    check("nothing at all is no fault either",
          dict(UC.status_cells(None, False, True))["SYSTEM"] == "-")
    check("unlocked to arrange the boxes, it says so",
          dict(UC.status_cells(state, True, False))["OVERLAY"] == "UNLOCKED")


@section("uichrome: a long system name is shortened, the rest keep their room")
def _fit():
    cells = [("CMDR", "Jameson"), ("SHIP", "Type-9 Heavy"),
             ("SYSTEM", "Col 285 Sector ZL-K b22-2"), ("BODY", "Col 285 Sector ZL-K b22-2 A 1"),
             ("STATE", "IN SRV"), ("OVERLAY", "ON")]
    roomy = UC.fit_cells(cells, 2000, mono)
    check("with room, every word whole", [c.value for c in roomy] == [v for _l, v in cells])
    check("each cell after the one before it", all(b.x0 >= a.x1 for a, b in zip(roomy, roomy[1:])))
    tight = UC.fit_cells(cells, 760, mono)
    check("squeezed, it fits", tight[-1].x1 <= 760, tight[-1].x1)
    check("the short readouts are kept whole",
          [c.value for c in tight if c.label in ("CMDR", "STATE", "OVERLAY")]
          == ["Jameson", "IN SRV", "ON"], [c.value for c in tight])
    check("the long ones end in dots",
          all(c.value.endswith("...") for c in tight if c.label in ("SYSTEM", "BODY")),
          [c.value for c in tight])
    check("but start the way they did", all(
        c.value[:-3] and dict(cells)[c.label].startswith(c.value[:-3])
        for c in tight if c.label in ("SYSTEM", "BODY")), [c.value for c in tight])
    check("a width with no room for anything raises nothing",
          len(UC.fit_cells(cells, 40, mono)) == 6)


@section("uichrome: Comfortable or Compact, from one table")
def _spacing():
    check("two spacings, Comfortable first", UC.SPACING_ORDER == ("comfortable", "compact")
          and UC.SPACING_NAMES == {"comfortable": "Comfortable", "compact": "Compact"})
    roomy, tight = UC.spacing("comfortable"), UC.spacing("compact")
    check("the same measures in both", set(roomy) == set(tight) and len(roomy) >= 5, sorted(roomy))
    check("Compact is tighter in every one",
          all(tight[k] < roomy[k] for k in roomy), {k: (roomy[k], tight[k]) for k in roomy})
    check("Comfortable is the window as it was: buttons 32 high, table rows padded 2",
          roomy["button_h"] == 32 and roomy["cell_pady"] == 2)
    check("anything else is Comfortable", UC.spacing("huge") == roomy and UC.spacing(None) == roomy)
    copy = UC.spacing("compact")
    copy["button_h"] = 999
    check("and the table cannot be changed by accident", UC.spacing("compact")["button_h"] != 999)


@section("uichrome: the theme arrows go round every theme")
def _arrows():
    order = ("cockpit", "elite", "gold", "pp_mahon", "game")
    check("> is the next", UC.next_theme(order, "elite", 1) == "gold")
    check("< is the one before", UC.next_theme(order, "elite", -1) == "cockpit")
    check("round from the last to the first", UC.next_theme(order, "game", 1) == "cockpit")
    check("and back", UC.next_theme(order, "cockpit", -1) == "game")
    check("a theme it does not know starts at the first", UC.next_theme(order, "gone", 1) == "cockpit")


@section("uichrome: the shortcut line, as much of it as fits")
def _shortcuts():
    items = UC.shortcut_items(TS.TABS, "Alt+4-9")
    check("an F-key for every tab, then the rig keys",
          items[:7] == ["F2 Map", "F3 Find", "F4 My sites", "F5 Where to land", "F6 Earnings",
                        "F7 Powerplay", "F8 Leaderboard"] and items[7] == "Alt+4-9 rig down", items)
    check("no rig keys bound, no rig item", len(UC.shortcut_items(TS.TABS, "")) == 7)
    line = UC.fit_line(items, 10000, mono)
    check("with room, all of it", all(item in line for item in items))
    line = UC.fit_line(items, 200, mono)
    check("short of room, whole items from the start, never half a word",
          mono(line) <= 200 and line.startswith("F2 Map") and all(
              part in items for part in line.split(UC.SEPARATOR)), line)
    check("no room at all: nothing", UC.fit_line(items, 10, mono) == "")


# ---------------------------------------------------------------------------
# The window
# ---------------------------------------------------------------------------

try:
    import tkinter
    tkinter.Tk().destroy()
    HAVE_DISPLAY = True
except Exception as _exc:
    HAVE_DISPLAY = False
    print("  SKIP  the window needs a display (%s). Run it under xvfb-run." % _exc)

if HAVE_DISPLAY:
    import overlay as OV
    OV.foreground_is_game = lambda: None
    import edsmt as A
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
        json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS,
                   "welcome_seen_version": A.APP_VERSION, "app_theme": "gold",
                   "overlay_theme": "gold"}, _f)
    app = A.EDSMT()
    app.geometry("1600x1000+0+0")
    app.updates.check = lambda *args, **kwargs: None

    def pump(times=3):
        for _ in range(times):
            try:
                app.update_idletasks()
                app.update()
            except Exception:
                pass

    def settle_until(cond, seconds=4.0):
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

    def walk(widget):
        for child in widget.winfo_children():
            yield child
            yield from walk(child)

    def inside(widget, window):
        wx, wy = widget.winfo_rootx(), widget.winfo_rooty()
        ox, oy = window.winfo_rootx(), window.winfo_rooty()
        return (wx >= ox and wy >= oy
                and wx + widget.winfo_width() <= ox + window.winfo_width() + 1
                and wy + widget.winfo_height() <= oy + window.winfo_height() + 1)

    def click(canvas, x, y):
        canvas.event_generate("<Button-1>", x=int(x), y=int(y))
        pump(3)

    settle_until(lambda: app.tab_strip.winfo_width() > 400)

    @section("the tab strip in the window: lit tab, clicks and F-keys")
    def _strip():
        strip = app.tab_strip
        check("it is a canvas under the status strip, across the window",
              isinstance(strip, A.tk.Canvas) and strip.winfo_width() >= app.winfo_width() - 40,
              (strip.winfo_width(), app.winfo_width()))
        check("seven chevrons are drawn", len(strip.find_withtag("tab")) == 7,
              len(strip.find_withtag("tab")))
        check("the map is lit, in the accent",
              strip.lit == "map" and strip.itemcget(strip.find_withtag("tab-map")[0], "fill") == A.ORANGE)
        check("the others are not",
              all(strip.itemcget(strip.find_withtag("tab-" + k)[0], "fill") != A.ORANGE
                  for k, _l, _f in TS.TABS if k != "map"))
        words = [strip.itemcget(i, "text") for i in strip.find_withtag("words")]
        check("each tab says its name and its key, at this width",
              "Where to land" in words and "F5" in words, words)
        tab = next(t for t in strip.tabs if t.key == "find")
        click(strip, tab.text_x, strip.winfo_height() / 2)
        check("clicking Find opens Find, lit", app.active_tab == "find" and strip.lit == "find"
              and strip.itemcget(strip.find_withtag("tab-find")[0], "fill") == A.ORANGE)
        app.event_generate("<F2>")
        pump(3)
        check("F2 brings the map back", app.active_tab == "map" and strip.lit == "map")
        app.event_generate("<F6>")
        pump(3)
        check("F6 is Earnings", app.active_tab == "earnings", app.active_tab)
        app.event_generate("<F2>")
        pump(3)
        seam = strip.tabs[1].x0 + TS.POINT - TS.GAP / 2.0
        click(strip, seam, strip.winfo_height() / 2)
        check("a click in the seam between two tabs changes nothing", app.active_tab == "map",
              app.active_tab)
        app.geometry("%dx900" % (A.RAIL_WIDTH + A.SCROLLBAR_W + 420))
        settle_until(lambda: app.winfo_width() < 900)
        pump(6)
        right = max(x for t in strip.tabs for x, _y in t.points)
        check("at the app's smallest width every tab is still on screen",
              right <= strip.winfo_width() and inside(strip, app), (right, strip.winfo_width()))
        app.geometry("1600x1000")
        settle_until(lambda: app.winfo_width() > 1500)

    @section("the status strip follows the game, and the overlay")
    def _status():
        state = State(cmdr="Jameson", ship_type="cutter", system="Ega", body="Ega 1",
                      landed=True)
        # The app's own tick redraws the strip from the real (empty) game
        # state; on a busy machine it landed inside the pump below and the
        # check read its dashes. Held off while this section looks.
        try:
            app.after_cancel(app._tick_job)
        except Exception:
            pass
        app.show_status_strip(state)
        pump(2)
        shown = app.status_strip.shown
        check("CMDR, SHIP, SYSTEM, BODY, STATE and OVERLAY",
              [c.label for c in shown] == ["CMDR", "SHIP", "SYSTEM", "BODY", "STATE", "OVERLAY"])
        values = dict((c.label, c.value) for c in shown)
        check("as the journal says them", values["CMDR"] == "Jameson"
              and values["SHIP"] == "Imperial Cutter" and values["STATE"] == "LANDED", values)
        drawn = [app.status_strip.itemcget(i, "text") for i in app.status_strip.find_withtag("value")]
        check("and drawn", "Jameson" in drawn and "LANDED" in drawn, drawn)
        check("each with its glyph", len(app.status_strip.find_withtag("glyph")) >= 6)
        app.settings["overlay_enabled"] = True
        app.show_overlay_state()
        pump(2)
        check("the overlay switched on shows at once",
              dict((c.label, c.value) for c in app.status_strip.shown)["OVERLAY"] in ("ON", "UNLOCKED"))
        app.settings["overlay_enabled"] = False
        app.show_overlay_state()
        pump(2)
        check("and off", dict((c.label, c.value) for c in app.status_strip.shown)["OVERLAY"] == "OFF")
        app._tick_job = app.after(400, app.tick)

    @section("the shortcut bar: F-keys, rig keys, spacing and the theme arrows")
    def _bar():
        line = str(app.shortcut_line.cget("text"))
        check("the F-keys are listed", line.startswith("F2 Map") and "F8 Leaderboard" in line, line)
        check("and the rig keys", "rig down" in line, line)
        check("SPACING: Comfortable or Compact, Comfortable to begin with",
              app.spacing_switch.cget("values") == ["Comfortable", "Compact"]
              and app.spacing_switch.get() == "Comfortable")
        check("the theme by name between its arrows",
              app.theme_name.cget("text") == A.OV.THEME_NAMES["gold"], app.theme_name.cget("text"))
        order = list(A.OV.THEME_ORDER)
        app.theme_step(1)
        pump(2)
        after = order[(order.index("gold") + 1) % len(order)]
        check("> picks the next theme, and keeps it",
              app.settings["app_theme"] == after
              and json.load(open(A.SETTINGS_FILE, encoding="utf-8"))["app_theme"] == after,
              app.settings["app_theme"])
        check("the overlay, following the app, wears it at once",
              app.settings["overlay_theme"] == after
              and app.overlay.theme()["ORANGE"] == A.OV.PALETTES[after]["ORANGE"])
        check("the name follows", app.theme_name.cget("text") == A.OV.THEME_NAMES[after])
        check("and the status line says the app wears it from the next start",
              "next start" in str(app.status.cget("text")), app.status.cget("text"))
        app.theme_step(-1)
        app.theme_step(-1)
        pump(2)
        check("< goes back past where it started",
              app.settings["app_theme"] == order[(order.index("gold") - 1) % len(order)])
        for _ in range(len(order)):
            app.theme_step(1)
        check("round every theme - the Powers and the game match among them - and back",
              app.settings["app_theme"] == order[(order.index("gold") - 1) % len(order)])
        app.theme_step(1)
        app.settings["overlay_follows_app"] = False
        app.settings["overlay_theme"] = "crimson"
        app.theme_step(1)
        check("not following, the overlay keeps its own", app.settings["overlay_theme"] == "crimson")
        app.settings["overlay_follows_app"] = True
        app.settings["app_theme"] = app.settings["overlay_theme"] = "gold"
        A.save_settings(app.settings)
        app.show_theme_name()

    @section("spacing: Compact tightens the chrome and the tables, Comfortable puts it back")
    def _spacing():
        before = app.btn_overlay.cget("height"), app.tab_strip.winfo_reqheight()
        app.spacing_switch.set("Compact")
        app.spacing_picked("Compact")
        pump(3)
        tight = A.UC.spacing("compact")
        check("kept as a setting", app.settings["ui_spacing"] == "compact"
              and json.load(open(A.SETTINGS_FILE, encoding="utf-8"))["ui_spacing"] == "compact")
        check("the top bar's buttons take the table's height",
              app.btn_overlay.cget("height") == tight["button_h"]
              and app.btn_help.cget("height") == tight["button_h"], app.btn_overlay.cget("height"))
        check("the tab strip too", app.tab_strip.winfo_reqheight() < before[1],
              (before[1], app.tab_strip.winfo_reqheight()))
        check("and a table row drawn now", A.SPACE["cell_pady"] == tight["cell_pady"])
        app.spacing_picked("Comfortable")
        pump(3)
        check("Comfortable puts every one back",
              (app.btn_overlay.cget("height"), app.tab_strip.winfo_reqheight()) == before
              and A.SPACE["cell_pady"] == A.UC.spacing("comfortable")["cell_pady"],
              ((app.btn_overlay.cget("height"), app.tab_strip.winfo_reqheight()), before))
        check("on for a new install: Comfortable, with a note on the switch",
              A.DEFAULT_SETTINGS["ui_spacing"] == "comfortable" and "spacing" in A.TIPS)

    @section("stat cards over the map: session, Cr/hr, rigs down, coverage")
    def _cards():
        names = list(app.map_cards)
        check("four cards, in that order", names == ["Session", "Cr/hr", "Rigs down", "Coverage"],
              names)
        check("each made by stat_card - a box and its number",
              all(isinstance(box, A.ctk.CTkFrame) and isinstance(value, A.ctk.CTkLabel)
                  for box, value in app.map_cards.values()))
        check("on show with the map", all(box.winfo_ismapped() for box, _v in app.map_cards.values()))
        app.open_find()
        pump(3)
        check("and out of the way while a tool tab is on show",
              not any(box.winfo_ismapped() for box, _v in app.map_cards.values()))
        app.show_map()
        pump(3)
        app.rigs_at = {"rigs": [{"n": 1, "lat": 1.0, "lon": 2.0, "at": time.time(), "body": "Ega 1"},
                                {"n": 2, "lat": 1.0, "lon": 2.1, "at": time.time(), "body": "Ega 1"}],
                       "rhinos": [None]}
        app.show_map_cards()
        pump(2)
        check("rigs down counts the rigs out", app.map_cards["Rigs down"][1].cget("text") == "2",
              app.map_cards["Rigs down"][1].cget("text"))
        check("no survey area: coverage is a dash",
              app.map_cards["Coverage"][1].cget("text") == A.CARD_NONE,
              app.map_cards["Coverage"][1].cget("text"))
        check("no session yet: a dash for its tonnes",
              app.map_cards["Session"][1].cget("text") == A.CARD_NONE,
              app.map_cards["Session"][1].cget("text"))

    @section("the top bar keeps room for the readouts without the tab buttons")
    def _top():
        check("no tool buttons left in the top bar - they are the tab strip now",
              not [w for w in walk(app._top_bar) if isinstance(w, A.ctk.CTkButton)
                   and str(w.cget("text")) in ("Find", "My sites", "Where to land", "Earnings")])
        check("Overlay, Unlock, Settings and Help are there",
              all(any(isinstance(w, A.ctk.CTkButton) and str(w.cget("text")).startswith(t)
                      for w in walk(app._top_bar)) for t in ("Overlay", "Unlock", "Settings", "Help")))
        check("the tour points at the tab strip for the tools", app.tour_find is app.tab_strip)

    try:
        app.destroy()
    except Exception:
        pass

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
