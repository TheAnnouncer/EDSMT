"""1.10040: EDSMT tells a launcher it is running (#323).

At start-up EDSMT writes one small file - EDSMT.json - into a folder every
Radio Raxxla tool shares, under the per-user data folder:

    Windows  %LOCALAPPDATA%\\RadioRaxxla\\Hub\\apps\\EDSMT.json
    Linux    $XDG_DATA_HOME (or ~/.local/share)/RadioRaxxla/Hub/apps/EDSMT.json

and removes it on a clean exit. It says which tool, which version, which
process, when it started and where its picture is - never anything about the
commander. A file that cannot be written is logged and ignored.

The pure parts run anywhere; the app on the real toolkit under xvfb:

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_hub.py
"""
import os, sys, json, re, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-hub-")
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


import hubmanifest as HM   # noqa: E402

KEYS = {"schema", "name", "title", "version", "pid", "started", "icon", "web", "health"}


@section("the shared folder, on Windows and on Linux")
def _folder():
    win = HM.apps_folder(platform="win32", environ={"LOCALAPPDATA": r"C:\Users\cmdr\AppData\Local"},
                         home=r"C:\Users\cmdr")
    check("Windows: under %LOCALAPPDATA%",
          win.replace("\\", "/") == "C:/Users/cmdr/AppData/Local/RadioRaxxla/Hub/apps", win)
    win = HM.apps_folder(platform="win32", environ={}, home=r"C:\Users\cmdr")
    check("Windows with no LOCALAPPDATA: the usual place under the profile",
          win.replace("\\", "/") == "C:/Users/cmdr/AppData/Local/RadioRaxxla/Hub/apps", win)
    lin = HM.apps_folder(platform="linux", environ={"XDG_DATA_HOME": "/home/cmdr/data"},
                         home="/home/cmdr")
    check("Linux: under $XDG_DATA_HOME", lin == "/home/cmdr/data/RadioRaxxla/Hub/apps", lin)
    lin = HM.apps_folder(platform="linux", environ={"XDG_DATA_HOME": ""}, home="/home/cmdr")
    check("Linux with it blank or unset: ~/.local/share",
          lin == "/home/cmdr/.local/share/RadioRaxxla/Hub/apps", lin)
    check("and the file is EDSMT.json in it", HM.FILE_NAME == "EDSMT.json")


@section("what the file says - and nothing about the commander")
def _what():
    folder = os.path.join(TMP, "one")
    icon = os.path.join(REPO, "images", "edsmt-badge-256.png")
    path = HM.announce("1.10040", icon, folder=folder, pid=4242,
                       now=1793262896.0)
    check("it is written where asked", path == os.path.join(folder, "EDSMT.json")
          and os.path.isfile(path), path)
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    check("exactly these keys", set(data) == KEYS, sorted(data))
    check("schema 1, name EDSMT, its title",
          data["schema"] == 1 and data["name"] == "EDSMT"
          and data["title"] == "EDSMT - Surface Mining Tool", data)
    check("the version and the process", data["version"] == "1.10040" and data["pid"] == 4242)
    check("started in UTC, ISO 8601", data["started"] == "2026-10-29T08:34:56Z", data["started"])
    check("the icon as an absolute path", data["icon"] == os.path.abspath(icon)
          and os.path.isabs(data["icon"]), data["icon"])
    check("no web page, and healthy", data["web"] is None and data["health"] == "ok")
    check("plain UTF-8 JSON a launcher in any language can read",
          open(path, "rb").read().decode("utf-8").lstrip().startswith("{"))
    words = json.dumps(data).lower()
    check("nothing about the commander in it",
          not any(w in words for w in ("cmdr", "commander", "fid", "journal", "token")), data)
    again = HM.announce("1.10041", icon, folder=folder, pid=4343, now=1793262900.0)
    with open(again, encoding="utf-8") as handle:
        check("a file left by a run that crashed is written over",
              json.load(handle)["pid"] == 4343)
    check("and no temporary file is left beside it",
          sorted(os.listdir(folder)) == ["EDSMT.json"], os.listdir(folder))


@section("a clean exit removes it - its own, and nobody else's")
def _gone():
    folder = os.path.join(TMP, "two")
    path = HM.announce("1.10040", "x.png", folder=folder, pid=os.getpid())
    check("removed on a clean exit", HM.withdraw(path) and not os.path.exists(path))
    check("removing it twice is no fault", HM.withdraw(path) is False)
    check("nor is removing nothing", HM.withdraw(None) is False and HM.withdraw("") is False)
    path = HM.announce("1.10040", "x.png", folder=folder, pid=os.getpid() + 1)
    check("a file another process wrote is left where it is",
          HM.withdraw(path) is False and os.path.exists(path))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("{not json")
    check("and so is one that cannot be read", HM.withdraw(path) is False and os.path.exists(path))


@section("a failure to write is logged and ignored")
def _fails():
    blocked = os.path.join(TMP, "blocked")
    with open(blocked, "w", encoding="utf-8") as handle:
        handle.write("a file where the folder should be")
    said = []
    path = HM.announce("1.10040", "x.png", folder=os.path.join(blocked, "apps"),
                       log=said.append)
    check("nothing written, nothing raised", path is None)
    check("and the reason is logged", said and "hub" in said[0].lower(), said)
    check("a log that itself fails does not raise either",
          HM.announce("1.10040", "x.png", folder=os.path.join(blocked, "apps"),
                      log=lambda text: 1 / 0) is None)


# ---------------------------------------------------------------------------
# The app
# ---------------------------------------------------------------------------

try:
    import tkinter
    tkinter.Tk().destroy()
    HAVE_DISPLAY = True
except Exception as _exc:
    HAVE_DISPLAY = False
    print("  SKIP  the app needs a display (%s). Run it under xvfb-run." % _exc)

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
                   "welcome_seen_version": A.APP_VERSION}, _f)

    @section("the app announces itself at start and withdraws on a clean exit")
    def _app():
        expected = os.path.join(HM.apps_folder(), "EDSMT.json")
        check("the folder follows this machine's data folder",
              expected.startswith(TMP), expected)
        app = A.EDSMT()
        app.updates.check = lambda *args, **kwargs: None
        try:
            app.update_idletasks()
            check("written at start", os.path.isfile(expected), expected)
            with open(expected, encoding="utf-8") as handle:
                data = json.load(handle)
            check("with this version and this process",
                  data["version"] == A.APP_VERSION and data["pid"] == os.getpid(), data)
            check("and the badge beside the app as its picture",
                  data["icon"] == os.path.join(REPO, "images", "edsmt-badge-256.png")
                  and os.path.isfile(data["icon"]), data["icon"])
            check("in UTC", re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", data["started"]),
                  data["started"])
        finally:
            app.on_close()
        check("gone after a clean exit", not os.path.exists(expected))

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
