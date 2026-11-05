"""1.10040 (#304): the marker for you - the Rhino, or the ship - in its own colour.

- Every theme gives the marker a cyan of its own, picked so it is none of
  the theme's instrument colours and reads on its ground.
- Settings -> Theme has a colour for it: "Theme's own" to begin with, or any
  colour picked or typed; a colour picked is kept.
- The map, the overlay's scope and the deposit card's little radar draw you
  in it.

Pure parts run anywhere; the app on the real toolkit under xvfb:

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_srv_colour.py
"""
import colorsys
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-srvcolour-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import overlay as OV       # noqa: E402

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


def rgb(colour):
    colour = colour.lstrip("#")
    return tuple(int(colour[i:i + 2], 16) for i in (0, 2, 4))


def luminance(colour):
    def chan(c):
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(c) for c in rgb(colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def apart(a, b):
    return sum((x - y) ** 2 for x, y in zip(rgb(a), rgb(b))) ** 0.5


@section("every theme gives the marker a cyan of its own")
def _themes():
    odd = []
    for name in OV.THEME_ORDER:
        full = OV.theme_palette(name)
        colour = OV.srv_colour(name)
        hue, _l, sat = colorsys.rgb_to_hls(*(c / 255.0 for c in rgb(colour)))
        near = min(apart(colour, full[k]) for k in ("ORANGE", "AMBER", "CYAN", "GREEN", "RED", "TEXT"))
        if not (OV.is_colour(colour) and 0.47 <= hue <= 0.56 and sat >= 0.6
                and contrast(colour, full["VOID"]) >= 4.5 and near >= OV.SRV_APART):
            odd.append((name, colour, round(hue * 360), round(near), round(contrast(colour, full["VOID"]), 1)))
    check("on all %d themes: a cyan, readable on the ground, none of the theme's own colours"
          % len(OV.THEME_ORDER), not odd, odd)
    check("the cockpit's is not its own telemetry cyan",
          OV.srv_colour("cockpit") != OV.theme_palette("cockpit")["CYAN"].lower())
    check("a theme that names one of its own keeps it",
          OV.srv_default(dict(OV.theme_palette("ice"), SRV="#12abcd")) == "#12abcd")
    check("an unknown theme is the cockpit's", OV.srv_colour("no such theme") == OV.srv_colour("cockpit"))


@section("the setting: the theme's own unless one is picked")
def _setting():
    check("nothing set: the worn theme's", OV.marker_colour({"overlay_theme": "ice"}) == OV.srv_colour("ice"))
    check("the overlay following the app wears the app theme's",
          OV.marker_colour({"overlay_follows_app": True, "app_theme": "gold", "overlay_theme": "ice"})
          == OV.srv_colour("gold"))
    check("a theme named outright wins over the settings' own",
          OV.marker_colour({"overlay_theme": "ice"}, "crimson") == OV.srv_colour("crimson"))
    check("a colour picked is kept, on every theme",
          OV.marker_colour({"srv_colour": "#FF00AA", "overlay_theme": "ice"}) == "#ff00aa"
          and OV.marker_colour({"srv_colour": "#ff00aa"}, "gold") == "#ff00aa")
    check("something that is not a colour is the theme's",
          OV.marker_colour({"srv_colour": "blue-ish"}, "gold") == OV.srv_colour("gold"))


class _Canvas:
    def __init__(self):
        self.calls = []

    def delete(self, *_a):
        self.calls = []

    def __getattr__(self, name):
        def record(*args, **kw):
            self.calls.append((name, args, kw))
            return len(self.calls)
        return record


class _Window:
    def __init__(self, w=380, h=380):
        self.w, self.h = w, h

    def winfo_width(self): return self.w
    def winfo_height(self): return self.h
    def winfo_screenwidth(self): return 1920
    def winfo_screenheight(self): return 1080
    def winfo_x(self): return 100
    def winfo_y(self): return 100


class _Saver:
    def save_settings(self): pass


ROWS = [{"range_m": 600.0, "bearing": 90.0,
         "deposit": {"id": "1", "system": "Ega", "body": "Ega 1", "location": "7",
                     "commodity": "Iridium", "rigs": "4", "amount": "High"}}]


def fills(key, settings, tag="me"):
    over = OV.Overlay(app=_Saver(), tk_module=None,
                      settings=dict({"overlay_click_through": True}, **settings))
    panel = OV.Panel(over, key)
    panel.window = _Window()
    panel.canvas = _Canvas()
    over.panels = {key: panel}
    over.draw(ROWS, 0.0, body="Ega 1", location="7")
    return [kw.get("fill") for name, _a, kw in panel.canvas.calls
            if name == "create_polygon" and tag in (kw.get("tags") or ())]


# On Windows the boxes are only drawn while the game is in front; there is no
# game here, so the question is not asked (None: "cannot tell", stay up).
OV.foreground_is_game = lambda: None


@section("the overlay draws you in it")
def _overlay():
    got = fills(OV.RADAR, {"overlay_theme": "ice"})
    check("the scope: your arrow in the theme's marker colour",
          got and set(got) == {OV.srv_colour("ice")}, got)
    got = fills(OV.RADAR, {"overlay_theme": "ice", "srv_colour": "#ff00aa"})
    check("and in the colour picked, when one is", got and set(got) == {"#ff00aa"}, got)
    got = fills(OV.DEPOSIT, {"overlay_theme": "gold", "srv_colour": "#ff00aa"})
    check("the deposit card's little radar too", got and set(got) == {"#ff00aa"}, got)


# ---------------------------------------------------------------------------
# The app on the real toolkit. Nothing leaves the machine.
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    print("  SKIP  the app needs a display (%s). Run it under xvfb-run." % _exc)
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    raise SystemExit(1 if fails else 0)

import socket            # noqa: E402


def _refuse(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        raise OSError("this check runs offline")
    return _real_connect(self, address)


_real_connect = socket.socket.connect
socket.socket.connect = _refuse
socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(OSError("offline"))

OV.foreground_is_game = lambda: None
import edsmt as A        # noqa: E402
A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
    json.dump({"asked_to_share": True, "welcome_seen_version": A.APP_VERSION, "tour_done": True,
               "journal_dir": JOURNALS, "overlay_enabled": False}, _f)

check("a new install takes the theme's own marker colour", A.DEFAULT_SETTINGS.get("srv_colour") == "")

app = A.EDSMT()
app.geometry("1600x1000+0+0")
app.updates.check = lambda *args, **kwargs: None
app.community.enabled = False


def pump(times=3):
    for _ in range(times):
        app.update_idletasks()
        app.update()


def settle(seconds=1.0):
    until = time.time() + seconds
    while time.time() < until:
        pump(1)
        time.sleep(0.02)


settle(3.0)


def map_fills():
    plan = app.plan
    plan.show([], heading=0.0, caption="x", signal="1")
    pump(2)
    return [plan.itemcget(i, "fill") for i in plan.find_withtag("me")]


@section("the app: the map draws you in the marker colour")
def _map():
    theme = app.settings.get("app_theme") or "cockpit"
    got = map_fills()
    check("the theme's own to begin with", got == [OV.srv_colour(theme)], (got, theme))


@section("the app: Settings -> Theme has the colour, and a pick is kept")
def _settings():
    app.open_settings()
    settle(1.0)
    window = [w for w in app.winfo_children() if isinstance(w, A.SettingsWindow)][-1]
    box, options, _patch = window.colours["srv_colour"]
    check("on the Theme tab, the theme's own first",
          options[0] == ("Theme's own", "") and str(box.get()) == "Theme's own", (options[:2], box.get()))
    box.set("#ff00aa")
    window.save()
    settle(0.6)
    check("a colour typed is saved", app.settings.get("srv_colour") == "#ff00aa", app.settings.get("srv_colour"))
    check("and the map wears it at once", map_fills() == ["#ff00aa"], map_fills())
    check("and so does the overlay", OV.marker_colour(app.overlay.settings) == "#ff00aa")
    window.load()
    check("opened again, it shows what was saved", str(window.colours["srv_colour"][0].get()) == "#ff00aa")
    window.colours["srv_colour"][0].set("not a colour")
    window.save()
    check("something that is not a colour is refused, and the last one kept",
          app.settings.get("srv_colour") == "#ff00aa")
    window.colours["srv_colour"][0].set("Theme's own")
    window.save()
    settle(0.6)
    theme = app.settings.get("app_theme") or "cockpit"
    check("back to the theme's own", app.settings.get("srv_colour") == ""
          and map_fills() == [OV.srv_colour(theme)], (app.settings.get("srv_colour"), map_fills()))


if __name__ == "__main__":
    print()
    print("FAILURES:", len(fails))
    for f in fails:
        print("  -", f)
    try:
        app.destroy()
    except Exception:
        pass
    sys.exit(1 if fails else 0)
