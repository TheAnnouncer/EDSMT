"""1.10040: "Overlay uses the app theme" (#316).

Settings > Theme gets one switch, overlay_follows_app. While it is on the
overlay always wears the app theme: its own picker is greyed out with a note
saying why, and a new app theme reaches the overlay as soon as it is saved -
the overlay does not wait for the restart the main window needs.

On for a new install. A settings file from before the switch existed gets
it on only where its overlay theme is already its app theme, so nobody's
overlay changes colour under them.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_overlay_theme.py
"""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-follow-")
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


try:
    import tkinter
    tkinter.Tk().destroy()
    HAVE_DISPLAY = True
except Exception as _exc:
    HAVE_DISPLAY = False
    print("  SKIP  the Settings window needs a display (%s). Run it under xvfb-run." % _exc)

if HAVE_DISPLAY:
    import overlay as OV
    OV.foreground_is_game = lambda: None
    import edsmt as A
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    BASE = {"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS,
            "welcome_seen_version": A.APP_VERSION}

    def loaded(**saved):
        if saved.pop("_none", False):
            if os.path.exists(A.SETTINGS_FILE):
                os.remove(A.SETTINGS_FILE)
            return A.load_settings()
        with open(A.SETTINGS_FILE, "w", encoding="utf-8") as handle:
            json.dump(dict(BASE, **saved), handle)
        return A.load_settings()

    @section("on for a new install; an older file keeps the overlay it had")
    def _upgrade():
        check("on out of the box", A.DEFAULT_SETTINGS["overlay_follows_app"] is True
              and "overlay_follows_app" in A.SETTING_TIPS)
        first = loaded(_none=True)
        check("a new install: on", first["overlay_follows_app"] is True)
        same = loaded(app_theme="ice", overlay_theme="ice")
        check("an older file whose overlay already wears the app theme: on",
              same["overlay_follows_app"] is True and same["overlay_theme"] == "ice", same.get("overlay_theme"))
        apart = loaded(app_theme="ice", overlay_theme="crimson")
        check("one whose overlay wears a theme of its own: off, and that theme kept",
              apart["overlay_follows_app"] is False and apart["overlay_theme"] == "crimson"
              and apart["app_theme"] == "ice", (apart["overlay_follows_app"], apart["overlay_theme"]))
        plain = loaded()
        check("one that never chose either: both the default, so on",
              plain["overlay_follows_app"] is True)
        kept = loaded(app_theme="ice", overlay_theme="ice", overlay_follows_app=False)
        check("switched off by hand, it stays off", kept["overlay_follows_app"] is False)
        forced = loaded(app_theme="fleet", overlay_theme="gold", overlay_follows_app=True)
        check("switched on, the overlay wears the app theme whatever the file says",
              OV.worn_theme(forced) == "fleet", OV.worn_theme(forced))
        check("and off, its own", OV.worn_theme(apart) == "crimson")
        check("Settings applied write it down that way, so the file tells the truth",
              A.follow_app_theme(dict(forced))["overlay_theme"] == "fleet")

    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
        json.dump(dict(BASE, app_theme="gold", overlay_theme="gold"), _f)
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

    def box(win, key):
        return win.choices[key][0]

    @section("Settings > Theme: the switch, and the overlay picker greyed out while it is on")
    def _switch():
        win = A.SettingsWindow(app)
        pump(4)
        try:
            page = win.pages["Theme"]
            check("the switch is on the Theme tab, named plainly",
                  "overlay_follows_app" in win.toggles
                  and "Overlay uses the app theme" in texts(page), texts(page)[:12])
            check("on, as the file has both the same", win.toggles["overlay_follows_app"].get() is True)
            check("the overlay picker is greyed out", box(win, "overlay_theme").cget("state") == "disabled",
                  box(win, "overlay_theme").cget("state"))
            check("with a note saying why", "app theme" in str(win.follow_note.cget("text")).lower(),
                  win.follow_note.cget("text"))
            box(win, "app_theme").set(A.OV.THEME_NAMES["ice"])
            win.theme_picked("app_theme")
            pump(2)
            check("picking an app theme moves the overlay picker with it",
                  box(win, "overlay_theme").get() == A.OV.THEME_NAMES["ice"]
                  and win.swatches["overlay_theme"]["ORANGE"].cget("fg_color")
                  == A.OV.PALETTES["ice"]["ORANGE"], box(win, "overlay_theme").get())
            win.save()
            pump(2)
            check("Save: the overlay wears it now - no restart for the overlay",
                  app.settings["overlay_theme"] == "ice" == app.settings["app_theme"]
                  and app.overlay.theme()["ORANGE"] == A.OV.PALETTES["ice"]["ORANGE"],
                  (app.settings["overlay_theme"], app.overlay.theme()["ORANGE"]))
            check("and Save says so", "overlay" in str(win.status.cget("text")).lower(),
                  win.status.cget("text"))
            win.toggles["overlay_follows_app"].set(False)
            win.follow_switched()
            pump(2)
            check("switched off, the overlay picker is free again with no note",
                  box(win, "overlay_theme").cget("state") == "normal"
                  and not str(win.follow_note.cget("text")), box(win, "overlay_theme").cget("state"))
            box(win, "overlay_theme").set(A.OV.THEME_NAMES["crimson"])
            win.theme_picked("overlay_theme")
            box(win, "app_theme").set(A.OV.THEME_NAMES["fleet"])
            win.theme_picked("app_theme")
            pump(2)
            check("and an app theme picked leaves the overlay's alone",
                  box(win, "overlay_theme").get() == A.OV.THEME_NAMES["crimson"])
            win.save()
            pump(2)
            check("saved off, each keeps its own",
                  app.settings["overlay_follows_app"] is False
                  and app.settings["overlay_theme"] == "crimson" and app.settings["app_theme"] == "fleet",
                  (app.settings["overlay_theme"], app.settings["app_theme"]))
            win.toggles["overlay_follows_app"].set(True)
            win.follow_switched()
            pump(2)
            check("switched back on, the overlay picker takes the app theme at once",
                  box(win, "overlay_theme").get() == A.OV.THEME_NAMES["fleet"]
                  and box(win, "overlay_theme").cget("state") == "disabled")
            win.save()
            pump(2)
            check("and Save puts the overlay in it",
                  app.settings["overlay_theme"] == "fleet"
                  and app.overlay.theme()["ORANGE"] == A.OV.PALETTES["fleet"]["ORANGE"])
        finally:
            win.destroy()
            pump()

    @section("a Power or the game match, picked while it is on, sets both")
    def _power():
        win = A.SettingsWindow(app)
        pump(4)
        try:
            win.power_picked("Edmund Mahon")
            pump(2)
            check("both pickers on the Power",
                  box(win, "app_theme").get() == "Powerplay - Edmund Mahon"
                  == box(win, "overlay_theme").get())
            win.save()
            pump(2)
            check("and both saved", app.settings["app_theme"] == "pp_mahon"
                  == app.settings["overlay_theme"])
        finally:
            app.settings["app_theme"] = app.settings["overlay_theme"] = "gold"
            A.apply_app_theme("gold")
            OV.apply_theme("gold")
            win.destroy()
            pump()

    try:
        app.destroy()
    except Exception:
        pass

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
