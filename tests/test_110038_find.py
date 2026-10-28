"""1.10038: Find shows one search at a time, and any tool tab pops out.

Find had five search buttons and every filter for every one of them on
screen at once. Now a switch at the top chooses the search - Sites, Still
there, Deposits, Sell prices or Mining bodies - only that search's filters
are on screen, and one Search button (or Enter in any box) runs it. Saved
searches are one Saved menu beside Reset, and they keep their search.

Every tool tab has a Pop out button at the right of its header; the window
it pops out to has Dock, which puts it back as a tab. Neither rebuilds the
tool, so what was typed, ticked and found stays. Settings -> Basics has the
tabs-or-windows switch first, in words that say what it does.

    python tests/test_110038_find.py
"""
import os, sys, json, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-find38-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import finder as FD     # noqa: E402

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
            traceback.print_exc(limit=6)
        return fn
    return wrap


# The ticket's own lists (ui-cleanup, 28 Oct), written out here rather than
# read from the code, so the check cannot agree with a mistake. The system
# box also shows for Sell prices, as "Near system" - a price search goes out
# near what is typed there - and for Mining bodies, where it narrows the
# bodies by name (1.10036). Hidden, it would still act, which is worse.
FINDS = ["commodity", "min_rigs", "min_types", "seen", "within", "place",
         "hide_worked", "verified"]
WANTED = {
    "sites": FINDS, "intact": FINDS, "deposits": FINDS,
    "prices": ["commodity", "from", "within", "place", "pad", "station", "carriers",
               "price_age", "min_price", "demand", "power_state", "power_side", "show"],
    "bodies": ["commodity", "within", "place"],
}
LABELS = ["Sites", "Still there", "Deposits", "Sell prices", "Mining bodies"]


@section("the five searches, and the filters each one has")
def _modes():
    check("five modes, in the order the switch shows them",
          [label for _key, label in FD.MODES] == LABELS, FD.MODES)
    check("a label or a key gives the mode; anything else is Sites",
          FD.mode_key("Sell prices") == "prices" and FD.mode_key("bodies") == "bodies"
          and FD.mode_key("nonsense") == "sites" and FD.mode_key(None) == "sites")
    check("and back to its label", FD.mode_label("intact") == "Still there")
    for mode, wanted in WANTED.items():
        check("%s shows exactly its own filters" % mode,
              list(FD.mode_filters(mode)) == wanted, FD.mode_filters(mode))
    check("each table belongs to its search",
          [FD.mode_of_kind(k) for k in ("sites", "intact", "search", "sell", "market",
                                        "published", "bodies", "")]
          == ["sites", "intact", "deposits", "prices", "prices", "prices", "bodies", ""])
    spec = FD.find_spec(from_ly=25.0, to_ly=100.0, pad="L", age_s=86400, min_price=1000,
                        min_demand=5, max_demand=50, station="outpost", no_carriers=True,
                        state="Stronghold", power="mine", show="price")
    sites = FD.mode_spec(spec, "sites")
    check("on Sites the price and Powerplay filters do nothing; Within still does",
          sites["to_ly"] == 100.0 and sites["from_ly"] is None and not sites["pad"]
          and not sites["age_s"] and sites["min_price"] is None and sites["min_demand"] is None
          and sites["max_demand"] is None and not sites["station"] and not sites["no_carriers"]
          and not sites["state"] and not sites["power"] and not sites["show"], sites)
    check("and the switches-off are not listed as narrowing anything",
          FD.active_filters(sites) == ["Within 100 Ly"], FD.active_filters(sites))
    check("on Sell prices every one of them counts", FD.mode_spec(spec, "prices") == spec)
    check("the spec handed in is not changed", spec["pad"] == "L" and spec["from_ly"] == 25.0)


HAVE_DISPLAY = True
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    HAVE_DISPLAY = False
    print("\n  SKIP  the window half of this file - no display (%s)." % _exc)


def on_screen(title):
    def wrap(fn):
        if not HAVE_DISPLAY:
            print("== %s ==\n  SKIP  needs a display" % title)
            return fn
        return section(title)(fn)
    return wrap


class FakeCommunity:
    """Records what Find asks for; never goes near a server."""
    ready, can_read, can_verify = True, True, False

    def __init__(self):
        self.calls = []

    def _note(self, name, **kwargs):
        self.calls.append((name, kwargs))
        return True

    def sites(self, **kwargs): return self._note("sites", **kwargs)
    def intact(self, **kwargs): return self._note("intact", **kwargs)
    def search(self, **kwargs): return self._note("search", **kwargs)
    def sell(self, **kwargs): return self._note("sell", **kwargs)
    def best_prices(self, **kwargs): return self._note("prices", **kwargs)
    def mining_bodies(self, **kwargs): return self._note("mining_bodies", **kwargs)
    def commodities(self): return True
    def configure(self, *args, **kwargs): pass


if HAVE_DISPLAY:
    import edonline as EDO  # noqa: E402

    def _offline(*_args, **_kwargs):
        raise RuntimeError("offline in tests")
    EDO.get_json = EDO.post_json = _offline
    import overlay as OV    # noqa: E402
    OV.foreground_is_game = lambda: None
    import edsmt as A       # noqa: E402
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
        json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS}, _f)
    app = A.EDSMT()
    app.geometry("1600x1000+0+0")
    app.updates.check = lambda *args, **kwargs: None
    real_community = app.community
    fake = app.community = FakeCommunity()
    app.watcher.star_pos = [1.0, 2.0, 3.0]
    app.watcher.system = "Col 285 Sector FD-F b26-4"

    def pump(times=4):
        for _ in range(times):
            app.update_idletasks()
            app.update()

    def settle_until(cond, tries=30):
        for _ in range(tries):
            if cond():
                return True
            pump(1)
        return bool(cond())

    pump()


def walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from walk(child)


def shown(widget):
    try:
        return bool(widget.winfo_viewable())
    except Exception:
        return False


def buttons(widget, text):
    return [w for w in walk(widget) if isinstance(w, A.ctk.CTkButton)
            and str(w.cget("text")) == text]


def labels_on_show(widget):
    return [str(w.cget("text")) for w in walk(widget)
            if isinstance(w, A.ctk.CTkLabel) and shown(w)]


def parts(win):
    """Every filter of the Find window, by the name the ticket gives it."""
    f = win._filters
    return {"commodity": [win.commodity], "min_rigs": [win.min_rigs],
            "min_types": [win.min_types], "seen": [win.max_age], "within": [win.within],
            "place": [win.query], "hide_worked": [win.hide_worked_box],
            "verified": [win.verified_box], "from": [f.far_box], "pad": [f.pad_box],
            "station": [f.station_box], "carriers": [f.carriers_box],
            "price_age": [f.age_box], "min_price": [f.price_box],
            "demand": [f.demand_low, f.demand_high], "power_state": [f.power_state_box],
            "power_side": [f.power_side_box], "show": [f.show_box]}


def A_texts(widget):
    out = []
    for child in walk(widget):
        try:
            out.append(str(child.cget("text")))
        except Exception:
            pass
    return out


def cells(widget, text):
    """The widgets under `widget` whose text is exactly `text`."""
    found = []
    for child in walk(widget):
        try:
            if str(child.cget("text")) == text:
                found.append(child)
        except Exception:
            pass
    return found


def pick_mode(win, label):
    """Press a segment of the mode switch, the way a click does."""
    segment = [b for b in walk(win.mode_switch) if isinstance(b, A.ctk.CTkButton)
               and str(b.cget("text")) == label]
    segment[0].invoke()
    pump(3)


NOW = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
SITES = {"count": 3, "commodities": [], "sites": [
    {"system": "Near %d" % i, "planet": "Near %d 1" % i, "spot": "1", "rigs": 6,
     "distinct_types": 2, "types": ["Ruby", "Platinum"], "updated": NOW, "age_days": 1.0,
     "uploader": "CMDR Tester", "status": "reported", "worked_out": False,
     "score": 10.0 - i, "intact_confidence": 1.0, "distance_ly": 5.0 + i} for i in range(3)]}
MANY = {"count": 120, "commodities": [], "sites": [
    dict(SITES["sites"][0], system="Row %03d" % i, planet="Row %03d 1" % i, score=200.0 - i)
    for i in range(120)]}


@on_screen("Find: a mode switch at the top, one Search, and only that mode's filters")
def _layout():
    win = app.open_find()
    pump(4)
    labels = [str(b.cget("text")) for b in walk(win.mode_switch)
              if isinstance(b, A.ctk.CTkButton)]
    check("a segmented switch with the five searches", isinstance(win.mode_switch,
          A.ctk.CTkSegmentedButton) and labels == LABELS, labels)
    check("it opens on Sites, the first time", win.mode == "sites"
          and win.mode_switch.get() == "Sites", win.mode)
    check("the switch sits above every filter, under the header",
          win.mode_switch.winfo_rooty() < win.commodity.winfo_rooty()
          and win.mode_switch.winfo_rooty() > win.winfo_rooty())
    check("one Search button", len(buttons(win, "Search")) == 1)
    old = [t for t in ("Search sites", "Individual deposits", "Best sell prices")
           if buttons(win, t)]
    check("and the five search buttons are gone", not old, old)
    check("the intro is one line", "\n" not in win.blurb.cget("text")
          and len(win.blurb.cget("text")) <= 110, win.blurb.cget("text"))
    everything = parts(win)
    for label in LABELS:
        mode = FD.mode_key(label)
        pick_mode(win, label)
        on = sorted(k for k, ws in everything.items() if all(shown(w) for w in ws))
        off = sorted(k for k, ws in everything.items() if not any(shown(w) for w in ws))
        check("%s: exactly its own filters are on screen" % label,
              on == sorted(WANTED[mode]) and len(on) + len(off) == len(everything),
              (on, off))
        check("%s: the switch says so, and it is remembered" % label,
              win.mode == mode and win.mode_switch.get() == label
              and app.settings.get("find_mode") == mode)
    pick_mode(win, "Sell prices")
    words = labels_on_show(win)
    check("Sell prices: no Min rigs, Types in patch or Seen within on screen",
          not {"Min rigs", "Types in patch", "Seen within"} & set(words), words)
    check("and the system box says what it means there",
          "Near system" in words and "System / body" not in words, words)
    pick_mode(win, "Sites")
    words = labels_on_show(win)
    check("Sites: no Pad, Price age, Demand or Powerplay state on screen",
          not {"Pad", "Price age", "Demand", "Powerplay state", "From"} & set(words), words)
    pick_mode(win, "Mining bodies")
    check("Mining bodies has its own note on how many sites the odds rest on",
          shown(win.bodies_note) and str(A.GX.SMALL_SAMPLE) in win.bodies_note.cget("text"),
          win.bodies_note.cget("text"))
    pick_mode(win, "Sites")
    check("and nobody else has it", not shown(win.bodies_note))
    on_disk = json.load(open(A.SETTINGS_FILE, encoding="utf-8"))
    check("the mode is kept in settings.json", on_disk.get("find_mode") == "sites", on_disk.get("find_mode"))


@on_screen("Find: hidden filters keep their values, and do not act")
def _hidden():
    win = app.open_find()
    pick_mode(win, "Sites")
    win.min_rigs.set("4")
    pick_mode(win, "Sell prices")
    win._filters.far_box.set("25 Ly")
    win._filters.power_state_box.set("Stronghold")
    win._filters.pad_box.set("L only")
    pick_mode(win, "Sites")
    check("a hidden filter keeps its value", win.min_rigs.get() == "4"
          and win._filters.far_box.get() == "25 Ly")
    win.min_rigs.set("0")
    win.results("sites", json.dumps(SITES), True)
    pump(4)
    found = [t for t in A_texts(win.table) if t in ("Near 0", "Near 1", "Near 2")]
    check("From 25 Ly, Pad and Powerplay state, set for prices, hide no site",
          len(found) == 3 and win.status.cget("text").startswith("3 result"),
          (found, win.status.cget("text")))
    advice = "; ".join(win._active())
    check("and are not named as narrowing the sites", "From" not in advice
          and "Pad" not in advice and "State" not in advice, advice)
    win._filters.reset()
    pump(2)


@on_screen("Find: Search runs the mode on show, and so does Enter")
def _search():
    win = app.open_find()
    wanted = {"Sites": "sites", "Still there": "intact", "Deposits": "search",
              "Sell prices": "sell", "Mining bodies": "mining_bodies"}
    win.commodity.set("Ruby")
    for label, call in wanted.items():
        pick_mode(win, label)
        fake.calls.clear()
        buttons(win, "Search")[0].invoke()
        pump(2)
        check("%s: Search asks for %s, and nothing else" % (label, call),
              [c[0] for c in fake.calls] == [call], fake.calls)
    pick_mode(win, "Sites")
    fake.calls.clear()
    entry = win.query._entry
    entry.focus_force()
    settle_until(lambda: app.focus_get() == entry)
    entry.event_generate("<Return>", when="now")
    settle_until(lambda: fake.calls)
    check("Enter in the system box searches", [c[0] for c in fake.calls] == ["sites"], fake.calls)
    pick_mode(win, "Sell prices")
    fake.calls.clear()
    price = win._filters.price_box._entry
    price.focus_force()
    settle_until(lambda: app.focus_get() == price)
    price.event_generate("<Return>", when="now")
    settle_until(lambda: fake.calls)
    check("and in a price box", [c[0] for c in fake.calls] == ["sell"], fake.calls)
    win.commodity.set("Any")
    pick_mode(win, "Sites")


@on_screen("Find: each mode keeps its own table, and an answer shows its own mode")
def _tables():
    win = app.open_find()
    pick_mode(win, "Sites")
    win.results("sites", json.dumps(SITES), True)
    pump(4)
    check("the sites are drawn", "Near 0" in A_texts(win.table))
    pick_mode(win, "Sell prices")
    check("Sell prices does not show the sites under its own filters",
          "Near 0" not in A_texts(win.table) and not win._rows, A_texts(win.table)[:5])
    check("and says what to do", "Search" in win.status.cget("text"), win.status.cget("text"))
    pick_mode(win, "Sites")
    check("back on Sites, the sites are still there", "Near 0" in A_texts(win.table)
          and len(win._rows) == 3)
    win.results("market", json.dumps({"prices": [
        {"commodity": "Ruby", "station": "Port A", "system": "Sys A", "sell": 300000,
         "demand": 50, "distance_ly": 5, "seen": NOW}]}), True)
    pump(4)
    check("a price answer brings Sell prices up with it", win.mode == "prices"
          and win.mode_switch.get() == "Sell prices" and "Port A" in A_texts(win.table))
    pick_mode(win, "Sites")


@on_screen("Find: the Saved menu beside Reset, and saved searches keep their mode")
def _saved():
    win = app.open_find()
    saved = win._filters.saved
    check("one Saved button, on the row with Search and Reset",
          len(buttons(win, "Saved")) == 1 and len(buttons(win, "Reset")) == 1
          and buttons(win, "Saved")[0].master is buttons(win, "Search")[0].master
          and buttons(win, "Reset")[0].master is buttons(win, "Search")[0].master)
    check("and the full Saved row is gone: no name box, no Save, no Delete",
          not buttons(win, "Save") and not buttons(win, "Delete")
          and A.SAVED_PLACEHOLDER not in A_texts(win))
    pick_mode(win, "Sell prices")
    win._filters.pad_box.set("L only")
    saved.ask = lambda: "Big pads"
    menu = saved.build_menu()
    check("the menu offers to save these filters", menu.entrycget(0, "label").startswith("Save"))
    menu.invoke(0)
    pump(2)
    stored = app.searches.get("Big pads") or {}
    check("Save asks for a name and keeps the search with its mode",
          stored.get("mode") == "prices" and stored.get("pad") == "L only", stored)
    check("and says so on the status line", 'Saved "Big pads"' in win.status.cget("text"),
          win.status.cget("text"))
    pick_mode(win, "Sites")
    win._filters.reset()
    pump(2)
    menu = saved.build_menu()
    names = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)
             if menu.type(i) == "command"]
    check("the menu lists it", "Big pads" in names, names)
    menu.invoke([i for i in range(menu.index("end") + 1) if menu.type(i) == "command"
                 and menu.entrycget(i, "label") == "Big pads"][0])
    pump(3)
    check("loading it brings its mode back with its filters", win.mode == "prices"
          and win.mode_switch.get() == "Sell prices" and win._filters.pad_box.get() == "L only",
          (win.mode, win._filters.pad_box.get()))
    app.searches.put("Old one", {"pad": "M or larger"}, window="find")
    pick_mode(win, "Deposits")
    saved.load("Old one")
    pump(2)
    check("a search saved before modes leaves the mode as it is", win.mode == "deposits")
    pick_mode(win, "Sites")
    win._filters.reset()
    pump(2)
    check("Reset puts the filters back and leaves the mode alone",
          win._filters.pad_box.get() == "Any" and win.mode == "sites")
    saved.build_menu()
    deletes = saved.delete_menu
    labels = [deletes.entrycget(i, "label") for i in range(deletes.index("end") + 1)]
    check("Delete is in the menu too, one entry per saved search",
          sorted(labels) == ["Big pads", "Old one"], labels)
    deletes.invoke(labels.index("Old one"))
    pump(2)
    check("and takes it away", "Old one" not in app.searches.names("find")
          and "Big pads" in app.searches.names("find"))
    saved.delete("Big pads")
    check("so does delete by name", not app.searches.names("find"))


@on_screen("Find: remembered across opening it again")
def _remembered():
    win = app.open_find()
    pick_mode(win, "Still there")
    win.destroy()
    pump(3)
    again = app.open_find()
    pump(3)
    check("Find opens again on the search it was left on",
          again is not win and again.mode == "intact"
          and again.mode_switch.get() == "Still there" and shown(again.min_rigs)
          and not shown(again._filters.pad_box))
    pick_mode(again, "Sites")


# ---------------------------------------------------------------------------
# Tabs or windows
# ---------------------------------------------------------------------------

TOOLS = (("find", "open_find"), ("sites", "open_sites"), ("land", "open_land"),
         ("earnings", "open_earnings"), ("powerplay", "open_powerplay"),
         ("leaderboard", "open_leaderboard"))


def is_window(tool):
    return str(tool.tk.call("winfo", "toplevel", tool._w)) == str(tool)


@on_screen("every tool tab has Pop out at the right of its header")
def _pop_buttons():
    app.settings["tools_as_tabs"] = True
    for key, opener in TOOLS:
        getattr(app, opener)()
        pump(4)
        tool = app.docked_tools.get(key)
        button = getattr(tool, "dock_button", None)
        check("%s: a Pop out button" % key, button is not None and button.cget("text") == "Pop out"
              and shown(button), getattr(button, "cget", lambda _k: None)("text"))
        if button is None:
            continue
        right = tool.winfo_rootx() + tool.winfo_width()
        check("%s: at the right of the header, near the top" % key,
              right - 60 <= button.winfo_rootx() + button.winfo_width() <= right
              and button.winfo_rooty() - tool.winfo_rooty() <= 40,
              (button.winfo_rootx(), button.winfo_width(), right,
               button.winfo_rooty() - tool.winfo_rooty()))
        x = button.winfo_rootx() + button.winfo_width() // 2
        y = button.winfo_rooty() + button.winfo_height() // 2
        top = app.winfo_containing(x, y)
        check("%s: drawn over the header, not behind it" % key,
              top is not None and (top is button or str(top).startswith(str(button))), str(top))


@on_screen("Pop out and Dock: the same tool, everything in it kept")
def _pop_and_dock():
    find = app.open_find()
    pump(3)
    pick_mode(find, "Sites")
    find.min_rigs.set("3")
    find.results("sites", json.dumps(MANY), True)
    pump(6)
    rows = len(find._rows)
    entered = []
    real_show = app.show_tab
    app.show_tab = lambda tool: (entered.append(1), real_show(tool))[1]
    app.show_map()
    app.open_find()
    app.show_tab = real_show
    check("a tab comes up in one go, not a few hundred", len(entered) == 1, len(entered))
    pump(3)
    find.dock_button.invoke()
    pump(6)
    check("Pop out makes the tab a window of its own", is_window(find) and shown(find)
          and not find.docked, (is_window(find), shown(find)))
    check("with the tool's title", find.title() == "EDSMT - Find deposits", find.title())
    check("the main window goes back to the map", app.active_tab == "map"
          and app.plan.winfo_manager() == "grid")
    check("everything in it is as it was", find.min_rigs.get() == "3" and len(find._rows) == rows
          and find.mode == "sites" and "Row 000" in A_texts(find.table))
    check("the button now says Dock", find.dock_button.cget("text") == "Dock")
    before = find.scroller.canvas.yview()[0]
    cell = cells(find.table, "Row 005")
    for _ in range(3):
        cell[0].event_generate("<Button-5>", when="now")
    pump(2)
    check("the wheel scrolls the table in its own window",
          find.scroller.canvas.yview()[0] > before, (before, find.scroller.canvas.yview()))
    count = len([w for w in walk(app) if isinstance(w, A.FindWindow)])
    app.open_find()
    pump(3)
    check("the Find tab button brings that window forward instead of opening another",
          len([w for w in walk(app) if isinstance(w, A.FindWindow)]) == count
          and app.docked_tools.get("find") is find and app.active_tab == "map")
    find.dock_button.invoke()
    pump(6)
    check("Dock puts it back as the tab on show", find.docked and not is_window(find)
          and app.active_tab == "find" and find.winfo_manager() == "grid"
          and find.master is app.tool_area)
    check("still the same search, the same rows", find.min_rigs.get() == "3"
          and len(find._rows) == rows and find.dock_button.cget("text") == "Pop out")
    find.scroller.top()
    pump(2)
    cell = cells(find.table, "Row 005")
    for _ in range(3):
        cell[0].event_generate("<Button-5>", when="now")
    pump(2)
    check("and the wheel works in the tab again", find.scroller.canvas.yview()[0] > 0,
          find.scroller.canvas.yview())
    for key, opener in TOOLS:
        tool = getattr(app, opener)() or app.docked_tools.get(key)
        pump(3)
        tool = app.docked_tools.get(key)
        tool.pop_out()
        pump(4)
        ok = is_window(tool) and shown(tool)
        tool.dock()
        pump(4)
        check("%s pops out and docks back" % key, ok and tool.docked and app.active_tab == key
              and app.docked_tools.get(key) is tool)
    land = app.docked_tools["land"]
    land.pop_out()
    pump(4)
    land._shell._close()
    pump(4)
    check("closing a popped-out window closes the tool", not land.winfo_exists()
          and "land" not in app.docked_tools)


@on_screen("with tools as windows, a window of its own has no Pop out")
def _windows():
    for key in list(app.docked_tools):
        app.docked_tools[key].destroy()
    pump(3)
    app.settings["tools_as_tabs"] = False
    try:
        win = A.FindWindow(app)
        pump(4)
        check("no Pop out or Dock on a window opened as a window",
              not win.docked and win.dock_button.winfo_manager() == "", win.dock_button.winfo_manager())
        win.destroy()
        pump(2)
    finally:
        app.settings["tools_as_tabs"] = True


@on_screen("Settings: the tabs-or-windows switch first in Basics, in plain words")
def _settings():
    win = A.SettingsWindow(app)
    pump(4)
    try:
        page = win.pages["Basics"]
        inner = getattr(page, "_parent_frame", None)
        slaves = page.pack_slaves()
        switches = [w for w in slaves if isinstance(w, A.ctk.CTkSwitch)]
        first = switches[0] if switches else None
        check("the first switch on Basics is the tabs one",
              first is not None and str(first.cget("text")) ==
              "Open Find, Earnings and the other tools as tabs (off: each in its own window)",
              first.cget("text") if first is not None else None)
        index = slaves.index(first) if first in slaves else 99
        before = [w for w in slaves[:index] if not isinstance(w, (A.ctk.CTkLabel, A.ctk.CTkFrame))
                  or isinstance(w, A.ctk.CTkFrame) and any(isinstance(c, (A.ctk.CTkComboBox,
                                                                           A.ctk.CTkEntry,
                                                                           A.ctk.CTkButton))
                                                          for c in walk(w))]
        check("above every other control on the page, under the heading", not before, before)
        check("and the switch still saves the setting", "tools_as_tabs" in win.toggles)
    finally:
        win.destroy()
        pump()


if HAVE_DISPLAY:
    app.community = real_community
    app.destroy()

if __name__ == "__main__":
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    sys.exit(1 if fails else 0)
