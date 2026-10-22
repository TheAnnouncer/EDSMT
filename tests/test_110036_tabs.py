"""1.10036: Find, My sites, Where to land, Earnings, Powerplay and Leaderboard
open as tabs of the main window (#147) - or, with the setting off, as windows
of their own the way they were.

Driven on the real toolkit under xvfb. A tab is the tool's frame shown in
the map's place; the Map tab brings the map back; the top bar's buttons are
the tabs and the one on show is lit.

    python tests/test_110036_tabs.py
"""
import os, sys, json, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-tabs-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
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
            traceback.print_exc(limit=6)
        return fn
    return wrap


try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    print("  SKIP  needs a display (%s). Run it under xvfb-run." % _exc)
    raise SystemExit(0)

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


def pump(times=4):
    for _ in range(times):
        app.update_idletasks()
        app.update()


pump()

OPENERS = (("find", "open_find", A.FindWindow), ("sites", "open_sites", A.SitesWindow),
           ("land", "open_land", A.LandWindow), ("earnings", "open_earnings", A.EarningsWindow),
           ("powerplay", "open_powerplay", A.PowerplayWindow),
           ("leaderboard", "open_leaderboard", A.LeaderboardWindow))


def shells():
    return [w for w in app.winfo_children() if isinstance(w, A.ToolShell)]


def opened(name):
    getattr(app, name)()
    pump(3)
    return app.docked_tools.get(dict((o, k) for k, o, _c in OPENERS)[name])


@section("tabs are the default, and every tool opens as one")
def _tabs():
    check("on out of the box, with a tip", A.DEFAULT_SETTINGS["tools_as_tabs"] is True
          and "tools_as_tabs" in A.SETTING_TIPS)
    check("the map is on show to begin with", app.active_tab == "map"
          and app.plan.winfo_manager() == "grid")
    check("the top bar has a Map tab beside the six", set(app.tab_buttons) ==
          {"map", "find", "sites", "land", "earnings", "powerplay", "leaderboard"})
    for key, opener, cls in OPENERS:
        tool = opened(opener)
        check("%s opens as a tab of the main window, not a window" % key,
              isinstance(tool, cls) and tool.docked and tool.master is app.tool_area
              and not shells(), (type(tool).__name__, shells()))
        check("%s is on show in the map's place, and its button is lit" % key,
              app.active_tab == key and tool.winfo_manager() == "grid"
              and app.plan.winfo_manager() == ""
              and app.tab_buttons[key].cget("fg_color") == A.BTN_PRIMARY["fg_color"])
        check("and the tab has the window's width: the rail steps aside (%s)" % key,
              app.rail_frame.winfo_manager() == "")
        others = [k for k, t in app.docked_tools.items() if k != key and t.winfo_manager()]
        check("and no other tab is on show with it (%s)" % key, not others, others)


@section("switching, coming back, and the map")
def _switch():
    find = app.docked_tools["find"]
    app.show_map()
    pump(2)
    check("Map brings the map back and hides the tabs", app.active_tab == "map"
          and app.plan.winfo_manager() == "grid" and find.winfo_manager() == "")
    check("and the rail with it", app.rail_frame.winfo_manager() == "grid")
    again = opened("open_find")
    check("Find again is the same tab, not a second one", again is find
          and app.active_tab == "find")
    sites = app.docked_tools["sites"]
    app.open_sites()
    pump(2)
    check("My sites again brings its tab forward", app.active_tab == "sites"
          and app.docked_tools["sites"] is sites)
    sites.destroy()
    pump(2)
    check("a tab that is closed goes, and the map comes back",
          "sites" not in app.docked_tools and app.active_tab == "map"
          and app.plan.winfo_manager() == "grid")
    check("and it opens again as a fresh tab", opened("open_sites") is not sites)


@section("the window calls the tools make still work as a tab")
def _calls():
    tool = app.docked_tools["powerplay"]
    check("a title is kept for the tab", tool.title() == "EDSMT - Powerplay")
    check("geometry, minsize and transient do no harm",
          tool.geometry("800x600") == "" and tool.minsize(800, 600) is None
          and tool.transient(app) is None)
    tool.withdraw()
    pump(2)
    check("withdraw goes back to the map", app.active_tab == "map")
    tool.deiconify()
    pump(2)
    check("deiconify shows the tab", app.active_tab == "powerplay")
    closed = []
    tool.protocol("WM_DELETE_WINDOW", lambda: closed.append(1))
    check("a close handler is kept for the window form", tool._on_close is not None)


@section("with the setting off, each is a window of its own again")
def _windows():
    for key in list(app.docked_tools):
        app.docked_tools[key].destroy()
    pump(2)
    app.settings["tools_as_tabs"] = False
    tool = opened("open_powerplay") or app.power_window
    pump(2)
    check("Powerplay opens in its own window", not tool.docked and len(shells()) == 1
          and shells()[0].title() == "EDSMT - Powerplay", (tool.docked, shells()))
    check("and the map stays on show", app.active_tab == "map")
    shells()[0]._close()
    pump(3)
    check("closing the window closes the tool", not shells() and not tool.winfo_exists())
    app.settings["tools_as_tabs"] = True


@section("Settings has the switch")
def _settings():
    win = A.SettingsWindow(app)
    pump(4)
    try:
        check("the switch is there", "tools_as_tabs" in win.toggles)
    finally:
        win.destroy()
        pump()


if __name__ == "__main__":
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    sys.exit(1 if fails else 0)
