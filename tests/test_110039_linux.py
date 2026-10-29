"""1.10039: EDSMT on Linux, from the same code (#288).

Elite Dangerous runs on Linux through Proton and a handful of launchers,
each with its own place for the Windows "Saved Games" folder. Everything
Windows-only in the app already went through an object a check can replace;
this release puts a Linux side behind the same seams, and says plainly in
Settings what Linux cannot do.

- journal.find_journal_dir: every known prefix location, the folder with
  the newest journal wins, and a hint for Settings.
- The data folder follows $XDG_DATA_HOME.
- inputdev.JsReader: joystick buttons from /dev/input/js*, behind the
  interface the JoystickWatcher already uses.
- x11keys: global hotkeys through XGrabKey, with a stand-in for the X
  server; quietly off without python-xlib or on Wayland.
- overlay.WindowPlatform: the window attributes chosen per platform.
- build_kind refuses to offer a Windows package on Linux.
- The Linux-only notes in Settings, RUN.sh, the workflow and the docs.

Pure parts run anywhere; the app on the real toolkit under xvfb:

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110039_linux.py
"""
import io, os, sys, json, re, struct, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-linux39-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import journal as JN       # noqa: E402

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


def read(*parts):
    return io.open(os.path.join(REPO, *parts), encoding="utf-8").read()


ED = os.path.join("Frontier Developments", "Elite Dangerous")
SAVED = os.path.join("drive_c", "users", "steamuser", "Saved Games", ED)


def make_home(name, *folders, journal_at=None):
    """A fake home with the Elite folder at each relative path given.
    journal_at: {relative folder: age in seconds} for a Journal file."""
    home = os.path.join(TMP, name)
    for rel in folders:
        os.makedirs(os.path.join(home, rel), exist_ok=True)
    for rel, age in (journal_at or {}).items():
        path = os.path.join(home, rel, "Journal.2026-10-28T120000.01.log")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('{"event": "Fileheader"}\n')
        stamp = time.time() - age
        os.utime(path, (stamp, stamp))
    return home


@section("journal: every place a Linux launcher puts the Saved Games folder")
def _places():
    layouts = {
        "steam": os.path.join(".steam", "steam", "steamapps", "compatdata", "359320", "pfx", SAVED),
        "steam-root": os.path.join(".steam", "root", "steamapps", "compatdata", "359320", "pfx", SAVED),
        "steam-debian": os.path.join(".steam", "debian-installation", "steamapps", "compatdata", "359320", "pfx", SAVED),
        "steam-local": os.path.join(".local", "share", "Steam", "steamapps", "compatdata", "359320", "pfx", SAVED),
        "steam-flatpak": os.path.join(".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam",
                                      "steamapps", "compatdata", "359320", "pfx", SAVED),
        "lutris": os.path.join("Games", "elite-dangerous", "drive_c", "users", "cmdr", "Saved Games", ED),
        "heroic": os.path.join("Games", "Heroic", "Prefixes", "default", "Elite Dangerous", "pfx", SAVED),
        "heroic-wine": os.path.join("Games", "Heroic", "Prefixes", "default", "drive_c", "users", "cmdr",
                                    "Saved Games", ED),
        "bottles": os.path.join(".local", "share", "bottles", "bottles", "Elite", "drive_c", "users", "cmdr",
                                "Saved Games", ED),
        "bottles-flatpak": os.path.join(".var", "app", "com.usebottles.bottles", "data", "bottles", "bottles",
                                        "Elite", "drive_c", "users", "cmdr", "Saved Games", ED),
        "wine": os.path.join(".wine", "drive_c", "users", "cmdr", "Saved Games", ED),
    }
    for name, rel in layouts.items():
        home = make_home("home-" + name, rel)
        found = JN.find_journal_dir(home=home, platform="posix", environ={})
        check("%s: %s" % (name, rel.split(os.sep)[0]),
              found == os.path.join(home, rel), found)
    home = make_home("home-none")
    check("nothing anywhere is None, not a crash",
          JN.find_journal_dir(home=home, platform="posix", environ={}) is None)
    # A library on another drive, named in Steam's libraryfolders.vdf.
    home = make_home("home-vdf", os.path.join(".local", "share", "Steam", "steamapps"))
    library = os.path.join(TMP, "games-drive", "SteamLibrary")
    pfx = os.path.join(library, "steamapps", "compatdata", "359320", "pfx", SAVED)
    os.makedirs(pfx)
    with open(os.path.join(home, ".local", "share", "Steam", "steamapps", "libraryfolders.vdf"), "w",
              encoding="utf-8") as handle:
        handle.write('"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n\t"1"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n}\n'
                     % (os.path.join(home, ".local", "share", "Steam"), library.replace("\\", "\\\\")))
    check("a Steam library on another drive is read from libraryfolders.vdf",
          JN.find_journal_dir(home=home, platform="posix", environ={}) == pfx)
    # The environment Proton and Wine hand a game.
    home = make_home("home-env")
    compat = os.path.join(TMP, "compat-env")
    os.makedirs(os.path.join(compat, "pfx", SAVED))
    check("STEAM_COMPAT_DATA_PATH is looked in",
          JN.find_journal_dir(home=home, platform="posix",
                              environ={"STEAM_COMPAT_DATA_PATH": compat})
          == os.path.join(compat, "pfx", SAVED))
    prefix = os.path.join(TMP, "wine-env")
    os.makedirs(os.path.join(prefix, "drive_c", "users", "cmdr", "Saved Games", ED))
    check("and so is WINEPREFIX",
          JN.find_journal_dir(home=home, platform="posix", environ={"WINEPREFIX": prefix})
          == os.path.join(prefix, "drive_c", "users", "cmdr", "Saved Games", ED))


@section("journal: the folder with the newest journal wins; an override still wins over all")
def _newest():
    steam = os.path.join(".steam", "steam", "steamapps", "compatdata", "359320", "pfx", SAVED)
    lutris = os.path.join("Games", "elite-dangerous", "drive_c", "users", "cmdr", "Saved Games", ED)
    home = make_home("home-two", steam, lutris, journal_at={steam: 3600.0, lutris: 60.0})
    check("two installs: the one played most recently is chosen",
          JN.find_journal_dir(home=home, platform="posix", environ={}) == os.path.join(home, lutris))
    home = make_home("home-two-b", steam, lutris, journal_at={steam: 60.0, lutris: 3600.0})
    check("whichever it is",
          JN.find_journal_dir(home=home, platform="posix", environ={}) == os.path.join(home, steam))
    home = make_home("home-two-c", steam, lutris, journal_at={lutris: 60.0})
    check("a folder with a journal beats one that has never been played in",
          JN.find_journal_dir(home=home, platform="posix", environ={}) == os.path.join(home, lutris))
    home = make_home("home-two-d", steam, lutris)
    check("with no journal anywhere the first known place is taken",
          JN.find_journal_dir(home=home, platform="posix", environ={}) == os.path.join(home, steam))
    over = make_home("home-over", "elsewhere")
    check("the folder set in Settings wins over every one of them",
          JN.find_journal_dir(os.path.join(over, "elsewhere"), home=home, platform="posix", environ={})
          == os.path.join(over, "elsewhere"))
    windows = make_home("home-win", os.path.join("Saved Games", ED), os.path.join("OneDrive", "Saved Games", ED))
    check("on Windows the order is what it always was: Saved Games before OneDrive",
          JN.find_journal_dir(home=windows, platform="nt", environ={})
          == os.path.join(windows, "Saved Games", ED))
    check("the places looked in are listed for Settings, as a sentence",
          "compatdata/359320" in JN.journal_hint("posix") and "Lutris" in JN.journal_hint("posix")
          and "Flatpak" in JN.journal_hint("posix"), JN.journal_hint("posix"))
    check("and Windows has no such sentence", JN.journal_hint("nt") == "")
    check("the real call still takes no arguments",
          JN.find_journal_dir() is None or os.path.isdir(JN.find_journal_dir()))


import inputdev as IND     # noqa: E402

JS_BUTTON, JS_AXIS, JS_INIT = 0x01, 0x02, 0x80


def js_event(kind, number, value, when=1000):
    """One struct js_event as the kernel writes it: u32 time, s16 value,
    u8 type, u8 number - eight bytes."""
    return struct.pack("@IhBB", when, value, kind, number)


def js_device(folder, number, *events):
    path = os.path.join(folder, "js%d" % number)
    with open(path, "wb") as handle:
        handle.write(b"".join(events))
    return path


@section("inputdev.JsReader: joystick buttons from /dev/input/js*, behind the watcher's interface")
def _js():
    folder = os.path.join(TMP, "input")
    os.makedirs(folder, exist_ok=True)
    reader = IND.JsReader(folder)
    check("an empty folder has no devices and answers None for every number",
          reader.devices() == 0 and reader(0) is None and reader(3) is None)
    # On open the driver sends the initial state as synthetic events: two
    # buttons held, one axis - the axis is not a button.
    js_device(folder, 0, js_event(JS_INIT | JS_BUTTON, 0, 1), js_event(JS_INIT | JS_BUTTON, 1, 0),
              js_event(JS_INIT | JS_BUTTON, 6, 1), js_event(JS_INIT | JS_AXIS, 0, -32767))
    check("js0 present: one device number to ask", reader.devices() == 1)
    mask = reader(0)
    check("the initial state is the buttons held: 1 and 7, counted from 1 as on screen",
          mask == (1 << 0) | (1 << 6), mask)
    check("asked again with nothing new, the same answer", reader(0) == mask)
    # Events arrive: button 7 let go, button 3 pressed, and a button past 32.
    with open(os.path.join(folder, "js0"), "ab") as handle:
        handle.write(js_event(JS_BUTTON, 6, 0) + js_event(JS_BUTTON, 2, 1) + js_event(JS_BUTTON, 40, 1))
    mask = reader(0)
    check("a release clears the bit, a press sets it, a button past 32 is ignored",
          mask == (1 << 0) | (1 << 2), mask)
    # A torn record at the end of the queue is held back, not misread.
    with open(os.path.join(folder, "js0"), "ab") as handle:
        handle.write(js_event(JS_BUTTON, 2, 0)[:5])
    check("a torn event is held back", reader(0) == (1 << 0) | (1 << 2))
    with open(os.path.join(folder, "js0"), "ab") as handle:
        handle.write(js_event(JS_BUTTON, 2, 0)[5:])
    check("and read whole once the rest arrives", reader(0) == 1 << 0)
    js_device(folder, 2, js_event(JS_INIT | JS_BUTTON, 3, 1))
    check("js0 and js2: three numbers to ask, js1 answers None",
          reader.devices() == 3 and reader(1) is None and reader(2) == 1 << 3)
    if os.name == "nt":
        # Windows will not delete a file something holds open; the kernel
        # on Linux pulls the device from under the reader. Stand in for it.
        reader._drop(2)
    os.remove(os.path.join(folder, "js2"))
    check("a device unplugged answers None from then on, quietly", reader(2) is None)
    check("and the other is unaffected", reader(0) == 1 << 0)
    check("more devices than the watcher knows are capped", IND.JsReader(folder).devices() <= IND.MAX_DEVICES)
    check("a folder that does not exist is no joystick, not a crash",
          IND.JsReader(os.path.join(TMP, "no-such")).devices() == 0
          and IND.JsReader(os.path.join(TMP, "no-such"))(0) is None)
    # Behind the watcher: a press is the moment the button goes down.
    folder2 = os.path.join(TMP, "input2")
    os.makedirs(folder2, exist_ok=True)
    js_device(folder2, 0, js_event(JS_INIT | JS_BUTTON, 4, 1))
    watcher = IND.JoystickWatcher(IND.JsReader(folder2))
    check("the watcher sees the device", watcher.available() and watcher.rebase() == 1)
    check("a button held when first seen is not a press", watcher.new_presses() == [])
    with open(os.path.join(folder2, "js0"), "ab") as handle:
        handle.write(js_event(JS_BUTTON, 7, 1))
    check("a button going down is: JOY1 B8", watcher.new_presses() == [(1, 8)])
    if sys.platform.startswith("linux"):
        check("on Linux the machine's own reader is the js reader",
              isinstance(IND.default_reader(), IND.JsReader) and IND.JoystickWatcher().available())
        check("looking in /dev/input", IND.default_reader().folder == "/dev/input")
    check("the reader writes nothing and imports no logging",
          "logging" not in read("inputdev.py") and 'open(' not in read("inputdev.py").split("class JsReader")[1].split("\nclass ")[0].replace("os.open(", ""))


import x11keys as XK       # noqa: E402


class FakeXServer:
    """Stands in for the X server behind x11keys: grabs are recorded, key
    presses are injected, and one combination can be 'already grabbed'."""

    def __init__(self, taken=(), keycodes=None):
        self.grabbed = []            # (keycode, mask) grabbed right now
        self.taken = set(taken)      # (keycode, mask) another program holds
        self.keycodes = keycodes or {}
        self.events = []             # (kind, keycode, state, time) waiting
        self.closed = False

    def keycode(self, keysym):
        return self.keycodes.get(keysym, 0)

    def grab(self, keycode, mask):
        if (keycode, mask) in self.taken:
            return False
        self.grabbed.append((keycode, mask))
        return True

    def ungrab(self, keycode, mask):
        if (keycode, mask) in self.grabbed:
            self.grabbed.remove((keycode, mask))

    def presses(self):
        out, self.events = self.events, []
        return out

    def close(self):
        self.closed = True


KEYCODES = {"1": 10, "2": 11, "F5": 71, "a": 38, "KP_Add": 86, "Return": 36}


def wait_for(fn, seconds=2.0):
    end = time.time() + seconds
    while time.time() < end:
        if fn():
            return True
        time.sleep(0.01)
    return fn()


@section("x11keys: a binding becomes a keycode and an X modifier mask")
def _parse():
    check("ALT+1 is Mod1 and the keysym 1", XK.parse("ALT+1") == (XK.MOD1, "1"))
    check("CTRL+SHIFT+F5", XK.parse("CTRL+SHIFT+F5") == (XK.CONTROL | XK.SHIFT, "F5"))
    check("a letter is its lower-case keysym", XK.parse("ALT+A") == (XK.MOD1, "a"))
    check("WIN is Mod4 (Super)", XK.parse("WIN+K") == (XK.MOD4, "k"))
    check("NUMPAD+ is KP_Add, the + survives", XK.parse("CTRL+NUMPAD+") == (XK.CONTROL, "KP_Add"))
    check("a bare + is plus", XK.parse("+") == (0, "plus"))
    check("ENTER, ESC, PAGEUP are Return, Escape, Prior",
          [XK.parse(k)[1] for k in ("ENTER", "ESC", "PAGEUP")] == ["Return", "Escape", "Prior"])
    check("two real keys is not a binding", XK.parse("A+B") is None and XK.parse("") is None)


@section("x11keys: grabs on the root window, Caps Lock and Num Lock ignored, presses drained")
def _grab():
    server = FakeXServer(keycodes=KEYCODES)
    keys = XK.X11Hotkeys(server=server, environ={"DISPLAY": ":0"})
    keys.start({"location": "ALT+1", "border": "ALT+2", "trace": "CTRL+NUMPAD+"})
    check("every key took", keys.bound == {"location": "ALT+1", "border": "ALT+2", "trace": "CTRL+NUMPAD+"}
          and keys.problem == "" and keys.active, (keys.bound, keys.problem, keys.active))
    check("each is grabbed four times: plain, with Caps Lock, Num Lock, both",
          sorted(m for k, m in server.grabbed if k == 10)
          == sorted([XK.MOD1, XK.MOD1 | XK.LOCK, XK.MOD1 | XK.MOD2, XK.MOD1 | XK.LOCK | XK.MOD2]),
          server.grabbed)
    server.events.append(("press", 10, XK.MOD1, 1000))
    check("Alt+1 pressed is the action", wait_for(lambda: keys.drain() == ["location"]))
    server.events.append(("press", 11, XK.MOD1 | XK.MOD2, 1100))
    check("with Num Lock on, still", wait_for(lambda: keys.drain() == ["border"]))
    server.events.append(("press", 86, XK.CONTROL | XK.LOCK, 1200))
    check("Ctrl+numpad plus with Caps Lock on", wait_for(lambda: keys.drain() == ["trace"]))
    # Auto-repeat: the server sends release+press pairs with one timestamp.
    server.events.extend([("press", 10, XK.MOD1, 2000), ("release", 10, XK.MOD1, 2050),
                          ("press", 10, XK.MOD1, 2050), ("release", 10, XK.MOD1, 2080),
                          ("press", 10, XK.MOD1, 2080), ("release", 10, XK.MOD1, 2200)])
    time.sleep(0.1)
    check("a key held is one press, not a stream", wait_for(lambda: keys.drain() == ["location"]))
    server.events.append(("press", 10, XK.MOD1, 3000))
    check("and the next real press counts", wait_for(lambda: keys.drain() == ["location"]))
    server.events.append(("press", 10, XK.SHIFT | XK.MOD1, 3100))
    time.sleep(0.1)
    check("Shift+Alt+1 is not Alt+1", keys.drain() == [])
    keys.stop()
    check("stop lets every key go and closes the connection",
          server.grabbed == [] and server.closed and not keys.active, server.grabbed)
    server = FakeXServer(keycodes=KEYCODES, taken={(71, 0)})
    keys = XK.X11Hotkeys(server=server, environ={"DISPLAY": ":0"})
    keys.start({"location": "F5", "border": "ALT+2", "zoom": "CTRL+ZZZ"})
    check("a key another program holds is reported by name, and the rest still take",
          "F5" in keys.problem and "another program" in keys.problem
          and keys.bound == {"border": "ALT+2"}, (keys.problem, keys.bound))
    check("a key the app cannot bind is said too", "ZZZ" in keys.problem, keys.problem)
    check("nothing of a refused key stays grabbed", not [g for g in server.grabbed if g[0] == 71], server.grabbed)
    keys.stop()
    keys = XK.X11Hotkeys(server=FakeXServer(), environ={"DISPLAY": ":0"})
    keys.start({"location": "ALT+1"})
    check("a key the server has no keycode for is reported", "ALT+1" in keys.problem and not keys.active)
    keys.stop()


@section("x11keys: quietly off without python-xlib, on Wayland, or with no display")
def _off():
    check("no DISPLAY: off, and says so", "display" in XK.why_not({}, have_xlib=True).lower())
    check("Wayland: off, and says so",
          "wayland" in XK.why_not({"DISPLAY": ":0", "WAYLAND_DISPLAY": "wayland-0"}, have_xlib=True).lower()
          and "wayland" in XK.why_not({"DISPLAY": ":0", "XDG_SESSION_TYPE": "wayland"}, have_xlib=True).lower())
    check("no python-xlib: off, and names it",
          "python-xlib" in XK.why_not({"DISPLAY": ":0"}, have_xlib=False))
    check("X11 with the library: on", XK.why_not({"DISPLAY": ":0", "XDG_SESSION_TYPE": "x11"}, have_xlib=True) == "")
    keys = XK.X11Hotkeys(server=FakeXServer(keycodes=KEYCODES), environ={"DISPLAY": ":0", "WAYLAND_DISPLAY": "w"})
    keys.start({"location": "ALT+1"})
    check("start on Wayland binds nothing, runs no thread, and problem says why",
          keys.bound == {} and not keys.active and "wayland" in keys.problem.lower())
    keys.stop()
    try:
        import Xlib                                   # noqa: F401
        have = True
    except ImportError:
        have = False
    check("the real server adapter is only made when the library is there",
          (XK.XServer.available() is have))
    if not have:
        keys = XK.X11Hotkeys(environ={"DISPLAY": ":0"})
        keys.start({"location": "ALT+1"})
        check("without it, start is a no-op that names the library",
              "python-xlib" in keys.problem and not keys.active, keys.problem)
        keys.stop()


# ---------------------------------------------------------------------------
# The app's module: no window yet. Nothing leaves the machine.
import socket            # noqa: E402


def _refuse(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        raise OSError("this check runs offline")
    return _real_connect(self, address)


_real_connect = socket.socket.connect
socket.socket.connect = _refuse
socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(OSError("offline"))

import overlay as OV     # noqa: E402
OV.foreground_is_game = lambda: None
import edsmt as A        # noqa: E402


class FakeWindow:
    def __init__(self):
        self.attrs = []

    def winfo_id(self):
        return 12345

    def attributes(self, name, value=None):
        if name == "-transparentcolor" and not hasattr(__import__("ctypes"), "windll"):
            raise RuntimeError('bad attribute "-transparentcolor"')     # what X11 Tk says
        self.attrs.append((name, value))


@section("overlay: the window attributes chosen per platform")
def _platform():
    windows = OV.WindowPlatform(windows=True)
    check("Windows: the colour key, then the opacity",
          windows.attributes(0.9) == [("-transparentcolor", OV.CHROMA), ("-alpha", 0.9)])
    check("click-through through the window style", windows.click_through)
    check("and nothing to say in Settings", windows.note() == "")
    linux = OV.WindowPlatform(windows=False)
    check("Linux: the opacity only - -transparentcolor raises on X11",
          linux.attributes(0.9) == [("-alpha", 0.9)])
    check("no click-through", not linux.click_through)
    note = linux.note()
    check("and Settings is told so in words, Linux named",
          "Linux" in note and "click" in note.lower() and "lock" in note.lower(), note)
    import ctypes
    check("this machine is judged by whether user32 is there",
          OV.PLATFORM.windows() is hasattr(ctypes, "windll"))
    strip = OV.Overlay(app=None, tk_module=None, settings={"overlay_opacity": 0.7, "overlay_click_through": True})
    strip.window = FakeWindow()
    strip.apply_click_through()
    wanted = [("-alpha", 0.7)] if os.name != "nt" else [("-transparentcolor", OV.CHROMA), ("-alpha", 0.7)]
    check("the overlay applies what the platform chose, and nothing that would raise",
          strip.window.attrs[-len(wanted):] == wanted, strip.window.attrs)
    src = read("overlay.py")
    for name in ("apply_transparency", "apply_click_through", "_hud_window"):
        body = src.split("    def %s(" % name)[1].split("\n    def ")[0]
        check("%s asks the platform object" % name, "PLATFORM." in body)
    src = read("edsmt.py")
    check("the note is in Settings, on Linux only",
          "here.note()" in src.split("def linux_notes(")[1].split("\ndef ")[0]
          and 'linux_notes().get(key, "")' in src)


@section("the data folder on Linux follows $XDG_DATA_HOME")
def _xdg():
    if os.name == "nt":
        check("(Windows: %LOCALAPPDATA% as before)", A.DATA_DIR.startswith(os.environ["LOCALAPPDATA"]))
        return
    check("settings and everything else go under $XDG_DATA_HOME/RadioRaxxla/EDSMT",
          A.DATA_DIR == os.path.join(TMP, "xdg", "RadioRaxxla", "EDSMT"), A.DATA_DIR)
    check("and the settings file is in it", A.SETTINGS_FILE.startswith(A.DATA_DIR))
    saved = os.environ.pop("XDG_DATA_HOME")
    try:
        check("unset, it is ~/.local/share, as the specification says",
              A.data_dir() == os.path.join(TMP, ".local", "share", "RadioRaxxla", "EDSMT"), A.data_dir())
        os.environ["XDG_DATA_HOME"] = ""
        check("and so is an empty one", A.data_dir().endswith(os.path.join(".local", "share", "RadioRaxxla", "EDSMT")))
    finally:
        os.environ["XDG_DATA_HOME"] = saved
    runner = read("tests", "run_all.py")
    check("run_all gives every check a sandbox $XDG_DATA_HOME, as it does %LOCALAPPDATA%",
          'os.environ["XDG_DATA_HOME"]' in runner
          and runner.find('os.environ["XDG_DATA_HOME"]') < runner.find("subprocess.run("))


@section("the app's Hotkeys use the X server on Linux, the same shape as on Windows")
def _wired():
    check("every key the app can bind has an X keysym",
          not [k for k in A.VK if XK.parse("CTRL+" + k) is None],
          [k for k in A.VK if XK.parse("CTRL+" + k) is None])
    if os.name == "nt":
        check("(Windows: RegisterHotKey, untouched)", "RegisterHotKey" in read("edsmt.py"))
        return
    server = FakeXServer(keycodes=KEYCODES)
    real = XK.X11Hotkeys
    made = []

    def stand_in(**kwargs):
        keys = real(server=server, environ={"DISPLAY": ":0"}, **kwargs)
        made.append(keys)
        return keys
    A.XK.X11Hotkeys = stand_in
    try:
        hotkeys = A.Hotkeys()
        hotkeys.start({"location": "ALT+1", "border": "ALT+2"})
        check("start binds through the X side", hotkeys.bound == {"location": "ALT+1", "border": "ALT+2"}
              and hotkeys.active and hotkeys.problem == "", (hotkeys.bound, hotkeys.problem))
        check("and shares the app's own queue", made and made[0].events is hotkeys.events)
        server.events.append(("press", 11, XK.MOD1, 500))
        check("a press reaches the app's drain", wait_for(lambda: hotkeys.drain() == ["border"]))
        hotkeys.stop()
        check("stop lets go", server.grabbed == [] and not hotkeys.active)
    finally:
        A.XK.X11Hotkeys = real
    hotkeys = A.Hotkeys()
    hotkeys.start({"location": "ALT+1"})
    try:
        import Xlib                                   # noqa: F401
        check("on this machine, with the library, the keys are live or a key is named",
              hotkeys.active or hotkeys.problem, hotkeys.problem)
    except ImportError:
        check("on this machine, without the library, Settings is told which to install",
              "python-xlib" in hotkeys.problem and not hotkeys.active, hotkeys.problem)
    hotkeys.stop()


@section("the updater never offers a Windows exe on Linux")
def _updater():
    frozen = getattr(sys, "frozen", None)
    here = os.path.join(TMP, "frozen-portable")
    os.makedirs(here, exist_ok=True)
    real_dir = A.app_dir
    sys.frozen = True
    A.app_dir = lambda: here
    try:
        check("a frozen single file on Windows is the portable build, as before",
              A.build_kind("nt") == "portable")
        os.makedirs(os.path.join(here, "_internal"), exist_ok=True)
        with open(os.path.join(here, "unins000.exe"), "w") as handle:
            handle.write("x")
        check("and Setup's folder build is the installed one", A.build_kind("nt") == "installed")
        check("the same frozen file on Linux is neither: there is no Windows package for it",
              A.build_kind("posix") == "")
        check("so the button goes to the download page, never to an exe",
              {"installed": "installer", "portable": "portable"}.get(A.build_kind("posix")) is None)
    finally:
        A.app_dir = real_dir
        if frozen is None:
            del sys.frozen
        else:
            sys.frozen = frozen
    check("from source it is nothing, on every platform",
          A.build_kind("nt") == "" and A.build_kind("posix") == "")
    check("the real call still takes no arguments", A.build_kind() == "")


@section("the Linux-only notes: one per thing Linux does differently, none on Windows")
def _notes():
    none = A.linux_notes("nt")
    check("Windows has none", none == {}, none)
    notes = A.linux_notes("posix")
    check("Linux: overlay, long press, joystick, hotkeys and the game folder",
          set(notes) == {"overlay", "long_press", "joystick", "hotkeys", "journal"}
          and all(notes.values()), notes)
    check("the overlay note is the platform object's", notes["overlay"] == OV.WindowPlatform(windows=False).note())
    check("the long press is said to be Windows only", "Linux" in notes["long_press"]
          and "not" in notes["long_press"])
    check("the joystick note names /dev/input", "/dev/input" in notes["joystick"])
    check("the hotkey note names Wayland and the library",
          "Wayland" in notes["hotkeys"] and "python-xlib" in notes["hotkeys"])
    check("the game folder note is the journal hint", notes["journal"] == JN.journal_hint("posix"))
    for text in notes.values():
        check("in plain words, under 400 characters: %s..." % text[:40], 40 < len(text) < 400, len(text))


@section("packaging: RUN.sh, requirements, the one-file spec, the workflow and the docs")
def _packaging():
    raw = io.open(os.path.join(REPO, "RUN.sh"), "rb").read()
    check("RUN.sh exists and is LF throughout", raw and b"\r" not in raw)
    run = raw.decode("utf-8")
    check("it starts with a shebang for bash", run.startswith("#!/usr/bin/env bash") or run.startswith("#!/bin/bash"))
    check("it makes the .venv, installs requirements.txt and starts edsmt.py",
          "venv" in run and "requirements.txt" in run and "edsmt.py" in run)
    check("it refuses a Python under 3.10 and says where to get one",
          "3, 10" in run or "3.10" in run)
    check("it checks tkinter is there, which Linux packages apart",
          "tkinter" in run and "python3-tk" in run)
    check("it is executable", os.access(os.path.join(REPO, "RUN.sh"), os.X_OK))
    req = read("requirements.txt")
    check("python-xlib is a Linux-only line of requirements.txt",
          re.search(r'^python-xlib[^\n]*sys_platform\s*==\s*"linux"', req, re.M), req)
    spec = read("build", "EDSMT-onefile.spec")
    check("the one-file spec builds on Linux: no Windows version resource or .ico there",
          "sys.platform" in spec and "version_info.txt" in spec and "optimize=2" in spec)
    check("and carries python-xlib and x11keys into the Linux file",
          "x11keys" in spec and "Xlib" in spec)
    yml = read(".github", "workflows", "build.yml")
    jobs = yml.split("\njobs:\n")[1]
    check("a separate linux job on ubuntu", "\n  linux:\n" in jobs and "ubuntu-latest" in jobs.split("\n  linux:\n")[1])
    linux = jobs.split("\n  linux:\n")[1].split("\n  release:\n")[0]
    check("it runs the tests under xvfb", "xvfb-run" in linux and "tests/run_all.py" in linux)
    check("builds the one-file spec", "build/EDSMT-onefile.spec" in linux)
    check("and uploads EDSMT-linux-x86_64.tar.gz", "EDSMT-linux-x86_64.tar.gz" in linux
          and "upload-artifact" in linux)
    release = jobs.split("\n  release:\n")[1]
    check("the release waits for both builds", re.search(r"needs:\s*\[\s*windows\s*,\s*linux\s*\]", release), release[:80])
    check("and attaches the Linux file beside the Windows ones",
          "upload/EDSMT-linux-x86_64.tar.gz" in release and "upload/EDSMT-Setup.exe" in release)
    windows = jobs.split("\n  linux:\n")[0]
    check("the Windows job still runs on windows-latest with the same steps",
          "windows-latest" in windows and "build/EDSMT.spec" in windows and "innosetup" in windows)
    readme = read("README.md")
    check("README has a short Linux section", "## Linux" in readme or "### Linux" in readme)
    section_text = readme.split("Linux\n")[1].split("\n## ")[0] if "Linux\n" in readme else ""
    check("that names RUN.sh and the download", "RUN.sh" in section_text and "EDSMT-linux-x86_64.tar.gz" in section_text)
    check("and is short: the README is the front page", section_text.count("\n") < 30, section_text.count("\n"))
    guide = read("docs", "GUIDE.md")
    check("the guide has a Linux section", "## Linux" in guide or "# Linux" in guide)
    linux_section = guide.split("## Linux")[1].split("\n## ")[0] if "## Linux" in guide else ""
    for word in ("Proton", "Wayland", "click", "joystick", "XDG_DATA_HOME", "RUN.sh"):
        check("which covers: %s" % word, word in linux_section)
    notes = read("docs", "LINUX.md")
    check("docs/LINUX.md holds the research, with its sources", "http" in notes and notes.count("http") >= 6)
    for word in ("compatdata", "js_event", "XGrabKey", "-transparentcolor", "XDG_DATA_HOME", "Wayland"):
        check("and covers: %s" % word, word in notes)
    runner = read("tests", "run_all.py")
    check("the check is in run_all, after the last 1.10038 line",
          "test_110039_linux.py" in runner
          and runner.find("test_110039_linux.py") > runner.rfind("test_110038_"))
    check("x11keys is a shipped module to the packaging check and the spelling check",
          '"x11keys.py"' in read("tests", "test_packaging.py") and '"x11keys.py"' in read("tests", "test_spelling.py"))


# ---------------------------------------------------------------------------
# The app on the real toolkit. Nothing leaves the machine.
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    print("  SKIP  the app needs a display (%s). Run it under xvfb-run." % _exc)
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    raise SystemExit(1 if fails else 0)

A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
    json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS}, _f)


class Link:
    """Stands in for the community link: nothing leaves the machine."""
    ready = True
    can_read = True
    can_verify = False
    share_name = True
    enabled = True

    def __init__(self):
        self.asked = []

    def __getattr__(self, name):
        return lambda *args, **kwargs: False


app = A.EDSMT()
app.geometry("1600x1000+0+0")
app.updates.check = lambda *args, **kwargs: None
app.community.enabled = False
app.community = Link()


def pump(times=3):
    for _ in range(times):
        app.update_idletasks()
        app.update()


def words_in(widget):
    out = []
    try:
        out.append(str(widget.cget("text")))
    except Exception:
        pass
    for child in widget.winfo_children():
        out.extend(words_in(child))
    return out


@section("Settings on this machine: the notes are on the right pages")
def _settings():
    pump()
    win = A.SettingsWindow(app)
    pump()
    try:
        notes = A.linux_notes()
        pages = {name: " ".join(words_in(page)) for name, page in win.pages.items()}
        if os.name == "nt":
            check("Windows: no note anywhere",
                  not any("On Linux" in text for text in pages.values()))
            return
        check("Overlay: the click-through note", notes["overlay"] in pages["Overlay"])
        check("Rigs: the long press note", notes["long_press"] in pages["Rigs"])
        check("Keys: the joystick and hotkey notes",
              notes["joystick"] in pages["Keys"] and notes["hotkeys"] in pages["Keys"])
        check("Your data: where the game folder is looked for", notes["journal"] in pages["Your data"])
        check("the overlay switch is still there to lock the boxes", "overlay_click_through" in win.toggles)
        check("the hotkey line says what the keys are doing on this machine",
              str(win.hotkey_note.cget("text")) != "" or getattr(app.hotkeys, "active", False),
              win.hotkey_note.cget("text"))
    finally:
        win.destroy()
        pump()


@section("the app starts and runs a tick on Linux without a fault")
def _runs():
    pump()
    faults = []
    real = app.trouble
    app.trouble = lambda stage, exc: faults.append((stage, exc))
    try:
        for _ in range(3):
            app.tick()
            pump(2)
    finally:
        app.trouble = real
    check("three ticks, no trouble", faults == [], faults)
    check("the overlay object has a platform", OV.PLATFORM.windows() is (os.name == "nt"))
    check("the joystick is available here, as the js reader",
          os.name == "nt" or A.IM.state(app).joystick.available())
    check("the long press is not: Windows only", os.name == "nt" or not A.IM.state(app).mouse.available())


if __name__ == "__main__":
    try:
        app.destroy()
    except Exception:
        pass
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    sys.exit(1 if fails else 0)
