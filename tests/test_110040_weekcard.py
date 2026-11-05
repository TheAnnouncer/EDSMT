"""1.10040: Share my week - your week on the surface as a card.

The Leaderboard window's Share my week fetches your week's card from the
community map (drawn there from what you shared: finds, sites, best patch,
furthest, your place on the board), saves it in the pictures folder and
opens it, ready to post. The same card is on the weekly page and the member
page. The commander name is the journal's, never typed.

Pure parts run anywhere; the app on the real toolkit under xvfb:

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_weekcard.py
"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-weekcard-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import weekcard as WC  # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


print("== the addresses ==")
check("the card is on EDSMT's own host, the name quoted, this week so far",
      WC.card_url("CMDR Bob & Co") == "https://edsmt.radioraxxla.com/v1/public/cmdrs/CMDR%20Bob%20%26%20Co/week.png?current=1",
      WC.card_url("CMDR Bob & Co"))
check("the last complete week when asked", WC.card_url("Bob", current=False).endswith("/week.png"), WC.card_url("Bob", current=False))
check("the page to share is the weekly page's own",
      WC.page_url("CMDR Bob") == "https://edsmt.radioraxxla.com/weekly/cmdr?cmdr=CMDR%20Bob&current=1", WC.page_url("CMDR Bob"))
check("the picture's name is the commander and the day",
      WC.picture_name("CMDR Bob", 1762300000.0).startswith("week_cmdr_bob_20251104") and WC.picture_name("CMDR Bob", 1762300000.0).endswith(".png"),
      WC.picture_name("CMDR Bob", 1762300000.0))
check("no name, no address", WC.card_url("") == "" and WC.page_url("  ") == "")

print("== the words ==")
check("not on the map yet is said plainly", "not on the map" in WC.explain("HTTP 404").lower(), WC.explain("HTTP 404"))
check("no connection is said plainly", "reach" in WC.explain("no connection (timed out)").lower(), WC.explain("no connection (timed out)"))
check("anything else is passed on", "boom" in WC.explain("boom"))

print("== the job ==")
calls = []


def fake_get(url, timeout=20.0, headers=None):
    calls.append(url)
    return b"\x89PNG\r\n\x1a\n" + b"x" * 100


folder = os.path.join(TMP, "pictures")
job = WC.fetch_job("CMDR Bob", folder, getter=fake_get, now=1762300000.0)
path = job()
check("the job fetches the card and saves it in the pictures folder",
      calls == [WC.card_url("CMDR Bob")] and os.path.isfile(path) and path.startswith(folder), (calls, path))
check("what it answers is the path, nothing else", path.endswith(WC.picture_name("CMDR Bob", 1762300000.0)), path)


def not_png(url, timeout=20.0, headers=None):
    return b"<html>nope</html>"


try:
    WC.fetch_job("CMDR Bob", folder, getter=not_png)()
    check("something that is not a picture is refused, not saved", False)
except Exception as exc:
    check("something that is not a picture is refused, not saved", "picture" in str(exc).lower(), exc)

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
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as handle:
        json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS,
                   "welcome_seen_version": A.APP_VERSION, "overlay_enabled": False}, handle)
    print("== in the app ==")
    app = A.EDSMT()
    app.geometry("1400x900+0+0")
    app.updates.check = lambda *a, **k: None
    opened = []
    A.open_path = lambda p: opened.append(p)
    said = []
    real_say = app.say
    app.say = lambda text, colour=None: (said.append(str(text)), real_say(text, colour))[1]

    def pump(times=3):
        for _ in range(times):
            app.update_idletasks()
            app.update()

    def settle_until(cond, seconds=4.0):
        end = time.time() + seconds
        while time.time() < end:
            pump(1)
            if cond():
                return True
            time.sleep(0.02)
        return cond()

    pump(5)
    app.board_cmdr = lambda: ""
    app.share_my_week()
    check("with no commander name from the journal yet, it says so", "commander name" in (said[-1] if said else ""), said[-1:])
    app.board_cmdr = lambda: "CMDR Bob"
    submitted = []
    app.worker.submit = lambda tag, fn: submitted.append((tag, fn))
    app.share_my_week()
    check("with a name, the card is asked for off the UI thread, tagged as its own",
          submitted and submitted[-1][0] == WC.TAG, submitted[-1:])
    app.take_weekcard(True, os.path.join(folder, "week_cmdr_bob_20261105-0000.png"))
    check("the picture is opened and said", opened and "week_cmdr_bob" in opened[-1] and "saved" in said[-1].lower(),
          (opened[-1:], said[-1:]))
    app.take_weekcard(False, "HTTP 404")
    check("a commander not on the map yet is told so", "not on the map" in said[-1].lower(), said[-1:])
    win = A.LeaderboardWindow(app)
    pump(4)
    check("the Leaderboard window has Share my week", hasattr(win, "share_week"))
    win.share_week()
    check("and it asks the same way", submitted[-1][0] == WC.TAG)
    try:
        win.destroy()
        app.destroy()
    except Exception:
        pass

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
