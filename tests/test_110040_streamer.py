"""1.10040: streamer mode, the app's half (#312).

Asked on 28 Oct: "Maybe a streamer mode."

- Settings > Sharing > Streamer mode: a switch (off), a delay of 0, 5, 10,
  15 or 30 minutes (15), and bigger text (on). One line under the switch
  says exactly what is hidden and what is not.
- While it is on: a STREAMER badge in the top bar, and the system and body
  NAMES the stream can see - the overlay boxes, the map's title, the status
  line, the readouts at the top - read "a system N Ly from Sol" and "a body"
  until the commander has been in that system for the delay.
- The commander's own Discord posts wait the same delay, in a queue that
  survives nothing: a restart drops it and says so. Finds still go to the
  community map at once.
- Bigger text: each overlay box's text two steps up the sizes it offers.
- Turned off, the names show at once and the queue is sent.

Pure parts run anywhere; the app on the real toolkit under xvfb:

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_streamer.py
"""
import os, sys, json, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-streamer40-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import streamer as ST        # noqa: E402

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


SYSTEM, BODY = "Col 285 Sector KZ-C b14-1", "Col 285 Sector KZ-C b14-1 A 3"
T0 = 1_800_000_000.0
FIFTEEN = 15 * 60


@section("a name, before and after the delay")
def _names():
    check("before the delay a system is only how far it is from Sol",
          ST.visible_name(SYSTEM, "system", T0, T0 + 60, FIFTEEN, ly=287.4) == "a system 290 Ly from Sol",
          ST.visible_name(SYSTEM, "system", T0, T0 + 60, FIFTEEN, ly=287.4))
    check("and a body is a body", ST.visible_name(BODY, "body", T0, T0 + 60, FIFTEEN) == "a body")
    check("a long way out reads in thousands",
          ST.visible_name(SYSTEM, "system", T0, T0 + 1, FIFTEEN, ly=22003.6) == "a system 22,000 Ly from Sol")
    check("next door to Sol says so", ST.visible_name("Alpha Centauri", "system", T0, T0 + 1, FIFTEEN, ly=4.38)
          == "a system near Sol")
    check("light years from Sol, from the star's position",
          abs(ST.from_sol((-171.0, 230.9, 0.5)) - 287.33) < 0.01 and ST.from_sol(None) is None)
    check("with no position known it is just a system",
          ST.visible_name(SYSTEM, "system", T0, T0 + 1, FIFTEEN) == "a system")
    check("one second short of the delay it is still hidden",
          ST.visible_name(SYSTEM, "system", T0, T0 + FIFTEEN - 1, FIFTEEN, ly=287.4) != SYSTEM)
    check("once the delay has passed, the real names",
          ST.visible_name(SYSTEM, "system", T0, T0 + FIFTEEN, FIFTEEN, ly=287.4) == SYSTEM
          and ST.visible_name(BODY, "body", T0, T0 + FIFTEEN + 5, FIFTEEN) == BODY)
    check("a delay of 0 shows them at once",
          ST.visible_name(SYSTEM, "system", T0, T0, 0, ly=287.4) == SYSTEM
          and ST.visible_name(BODY, "body", None, T0, 0) == BODY)
    check("not knowing when you arrived is not knowing it is safe: hidden",
          ST.visible_name(SYSTEM, "system", None, T0, FIFTEEN) == "a system")
    check("nothing to hide is nothing", ST.visible_name("", "system", T0, T0, FIFTEEN) == "")


@section("names taken out of a line of text")
def _hide():
    names = [(BODY, "a body"), (SYSTEM, "a system 290 Ly from Sol")]
    check("the body first, so its system's name inside it goes with it",
          ST.hide("%s / %s" % (SYSTEM, BODY), names) == "a system 290 Ly from Sol / a body",
          ST.hide("%s / %s" % (SYSTEM, BODY), names))
    check("whatever the case it is written in",
          ST.hide("ARRIVED AT %s" % BODY.upper(), names) == "ARRIVED AT a body")
    check("another body of the same system keeps only its own letters",
          ST.hide("%s B 1" % SYSTEM, names) == "a system 290 Ly from Sol B 1")
    check("nothing to hide leaves the text alone", ST.hide("Marked Painite", []) == "Marked Painite")


@section("posts held back for the delay")
def _queue():
    held = ST.DelayQueue()
    held.put("find", T0)
    held.put("session", T0 + 120)
    check("two waiting", len(held) == 2)
    check("nothing before its time", held.due(T0 + FIFTEEN - 1, FIFTEEN) == [] and len(held) == 2)
    check("the first goes when its delay has passed", held.due(T0 + FIFTEEN, FIFTEEN) == ["find"]
          and len(held) == 1)
    check("a shorter delay picked meanwhile lets the next go sooner", held.due(T0 + 420, 5 * 60) == ["session"])
    held.put("a", T0)
    held.put("b", T0 + 1)
    check("drain hands back everything, in order, at once", held.drain() == ["a", "b"] and len(held) == 0)


@section("the settings, read safely")
def _settings():
    check("the delays offered", ST.DELAYS_MIN == (0, 5, 10, 15, 30) and ST.DEFAULT_DELAY_MIN == 15)
    check("a delay as it is saved, as text or a number",
          ST.delay_minutes("30") == 30 and ST.delay_minutes(5) == 5 and ST.delay_minutes(0) == 0)
    check("anything else is the default", ST.delay_minutes("soon") == 15 and ST.delay_minutes(None) == 15
          and ST.delay_minutes(7) == 15)
    sizes = (80, 90, 100, 115, 130, 150, 175, 200)
    check("bigger text is two steps up the sizes offered",
          ST.step_up(100, sizes) == 130 and ST.step_up(80, sizes) == 100 and ST.step_up("115", sizes) == 150)
    check("never past the largest", ST.step_up(175, sizes) == 200 and ST.step_up(200, sizes) == 200)
    check("a size not on the list steps from the nearest", ST.step_up(105, sizes) == 130)


# ---------------------------------------------------------------------------
# The app, on the real toolkit
# ---------------------------------------------------------------------------
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    print("  SKIP  the app needs a display (%s). Run it under xvfb-run." % _exc)
    print("\nFAILURES:", len(fails))
    sys.exit(1 if fails else 0)

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
import edonline as EDO   # noqa: E402
import webhooks as WH    # noqa: E402
import survey as SV      # noqa: E402
import sessionledger as SL  # noqa: E402
A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)
HOOK = "https://discord.com/api/webhooks/556677889900112233/" + "s" * 6 + "Zq-9_" + "s" * 57
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
    json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS,
               "welcome_seen_version": A.APP_VERSION,
               "discord_webhooks": [WH.entry("My stream", HOOK, finds=True, sessions=True)]}, _f)

app = A.EDSMT()
app.geometry("1600x1000+0+0")
app.updates.check = lambda *args, **kwargs: None


def pump(times=3):
    for _ in range(times):
        app.update_idletasks()
        app.update()


def walk(widget):
    out = [widget]
    for child in widget.winfo_children():
        out += walk(child)
    return out


def texts_in(widget):
    found = []
    for w in walk(widget):
        try:
            text = w.cget("text")
        except Exception:
            continue
        if isinstance(text, str) and text:
            found.append(text)
    return found


def shown(widget):
    try:
        return bool(widget.winfo_manager()) and bool(widget.winfo_ismapped())
    except Exception:
        return False


class Worker:
    def __init__(self):
        self.jobs = []

    def submit(self, tag, fn):
        self.jobs.append((tag, fn))


JOURNAL = os.path.join(JOURNALS, "Journal.2026-10-29T120000.01.log")
STAMP = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def emit(*events):
    with open(JOURNAL, "a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")


def status(lat, lon):
    with open(os.path.join(JOURNALS, "Status.json"), "w", encoding="utf-8") as handle:
        json.dump({"timestamp": STAMP, "event": "Status", "Flags": (1 << 21) | (1 << 26),
                   "Latitude": lat, "Longitude": lon, "Heading": 90, "Altitude": 0,
                   "BodyName": BODY, "PlanetRadius": 1800000.0}, handle)


def tick(times=1):
    for _ in range(times):
        app.tick()
    pump(2)


def on(**changes):
    data = dict(app.settings)
    data.update(changes)
    app.apply_settings(data)
    pump(2)


pump()
emit({"timestamp": STAMP, "event": "Fileheader", "gameversion": "4.4.2.1", "part": 1},
     {"timestamp": STAMP, "event": "Commander", "Name": "Jameson", "FID": "F1"},
     {"timestamp": STAMP, "event": "FSDJump", "StarSystem": SYSTEM, "SystemAddress": 77,
      "StarPos": [-171.0, 230.9, 0.5]},
     {"timestamp": STAMP, "event": "ApproachBody", "StarSystem": SYSTEM, "Body": BODY},
     {"timestamp": STAMP, "event": "Touchdown", "Latitude": 12.5, "Longitude": -45.5,
      "StarSystem": SYSTEM, "Body": BODY, "PlayerControlled": True})
status(12.5, -45.5)
tick(2)


@section("Settings > Sharing > Streamer mode")
def _settings_rows():
    check("off by default, a delay of 15 minutes, bigger text on",
          A.DEFAULT_SETTINGS.get("streamer_mode") is False and A.DEFAULT_SETTINGS.get("streamer_delay_min") == 15
          and A.DEFAULT_SETTINGS.get("streamer_big_text") is True)
    win = A.SettingsWindow(app)
    pump(4)
    try:
        check("a switch for it and for bigger text",
              "streamer_mode" in win.toggles and "streamer_big_text" in win.toggles)
        box, options = win.choices.get("streamer_delay_min", (None, []))
        check("and the delay, from 0 to 30 minutes", [int(v) for _n, v in options] == [0, 5, 10, 15, 30]
              and box is not None and box.get() == "15 minutes", (options, box and box.get()))
        texts = texts_in(win.pages["Sharing"])
        check("one line says exactly what is hidden and what is not", A.STREAMER_NOTE in texts
              and "hidden" in A.STREAMER_NOTE.lower() and "not hidden" in A.STREAMER_NOTE.lower(),
              A.STREAMER_NOTE)
        check("and every one of them has its note",
              all(k in A.SETTING_TIPS for k in ("streamer_mode", "streamer_delay_min", "streamer_big_text")))
        saved = []
        real_apply = app.apply_settings
        app.apply_settings = lambda data: saved.append(dict(data))
        try:
            box.set("5 minutes")
            win.save()
        finally:
            app.apply_settings = real_apply
        check("the delay is saved as minutes", saved and saved[-1].get("streamer_delay_min") == 5,
              saved and saved[-1].get("streamer_delay_min"))
    finally:
        win.destroy()
        pump(2)


@section("off: the names are there, and no badge")
def _off():
    check("the top readout names the system and the body", SYSTEM in app.t_where.cget("text")
          and BODY in app.t_where.cget("text"), app.t_where.cget("text"))
    check("no STREAMER badge", not shown(app.streamer_badge))


@section("on: STREAMER, and the names hidden until the delay has passed")
def _on():
    on(streamer_mode=True, streamer_delay_min=15)
    tick()
    check("the STREAMER badge is in the top bar", shown(app.streamer_badge)
          and app.streamer_badge.cget("text") == "STREAMER")
    where = app.t_where.cget("text")
    check("the readout says how far out, not where", where == "a system 290 Ly from Sol / a body", where)
    check("the map's title has no name in it", SYSTEM not in app.plan.caption and BODY not in app.plan.caption
          and "a body" in app.plan.caption, app.plan.caption)
    app.say("Arrived at %s - 3 mining locations" % BODY)
    pump(1)
    check("nor the status line", app.status.cget("text") == "Arrived at a body - 3 mining locations",
          app.status.cget("text"))

    class Overlay:
        showing = True

        def __init__(self):
            self.drawn, self.flashed = {}, []

        def draw(self, *args, **kwargs):
            self.drawn.update(kwargs)

        def flash(self, title, detail="", colour=None):
            self.flashed.append((title, detail))
            return True
    real, app.overlay = app.overlay, Overlay()
    try:
        app.draw_overlay([], 0.0)
        app.flash("ARRIVED  %s" % BODY.upper(), "on %s" % SYSTEM)
        fake = app.overlay
    finally:
        app.overlay = real
    check("nor the overlay's boxes", fake.drawn.get("body") == "a body", fake.drawn.get("body"))
    check("nor what flashes over the game", fake.flashed == [("ARRIVED  a body", "on a system 290 Ly from Sol")],
          fake.flashed)
    later = time.time() + 15 * 60 + 1
    check("once he has been in the system for the delay, the real names",
          app.hide_names("%s / %s" % (SYSTEM, BODY), now=later) == "%s / %s" % (SYSTEM, BODY))
    on(streamer_delay_min=0)
    tick()
    check("and with no delay, at once", app.t_where.cget("text") == "%s / %s" % (SYSTEM, BODY),
          app.t_where.cget("text"))
    on(streamer_delay_min=15)
    tick()


@section("bigger text over the game")
def _big_text():
    check("each box's text is two steps up while streaming", abs(app.overlay.text_scale(OV.RADAR) - 1.30) < 1e-9,
          app.overlay.text_scale(OV.RADAR))
    on(streamer_big_text=False)
    check("as it was set with bigger text off", abs(app.overlay.text_scale(OV.RADAR) - 1.0) < 1e-9)
    on(streamer_big_text=True)


@section("the commander's own Discord posts wait the delay; the community map does not")
def _held():
    app.worker = Worker()
    uploads = []

    class Link:
        ready = True

        def upload(self, cmdr, rows, *a, **k):
            uploads.append(rows)
            return True
    real_link, app.community = app.community, Link()
    record = {"commodity": "Monazite", "rigs": "4", "system": SYSTEM, "body": BODY, "location": "3",
              "amount": "High", "density": "Medium", "lat": "12.5", "lon": "-45.5", "status": "reported"}
    try:
        app.share(record)
        posted = app.post_discord_find(record)
    finally:
        app.community = real_link
    check("the find goes to the community map at once", len(uploads) == 1, uploads)
    check("the Discord post does not go yet", posted and app.worker.jobs == [] and len(app.discord_hold) == 1,
          (posted, app.worker.jobs, len(app.discord_hold)))
    check("and the status line says it is held, and that closing EDSMT drops it",
          "held" in app.status.cget("text").lower() and "15 min" in app.status.cget("text"),
          app.status.cget("text"))
    check("before the delay, nothing is sent",
          app.follow_streamer(now=time.time() + 60) == 0 and app.worker.jobs == [])
    check("once it has passed, the post goes",
          app.follow_streamer(now=time.time() + 15 * 60 + 1) == 1 and len(app.worker.jobs) == 1
          and app.worker.jobs[0][0] == EDO.DISCORD_TAG and len(app.discord_hold) == 0)
    app.worker.jobs = []
    # A session summary waits too.
    folder = os.path.join(TMP, "sessions")
    os.makedirs(folder)
    app.earnings, app.post_book, app.extras = SV.Earnings(folder), SL.PostBook(folder), SL.SessionLedger(folder)
    app._discord_seen = None
    app.post_discord_sessions()
    run = app.earnings.start(SYSTEM, BODY, "Jameson",
                             when=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3600)))
    ended = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 30))
    run.update({"mined": "Monazite:120", "ended": ended, "closed": ended})
    app.post_discord_sessions()
    check("a session summary waits as well", app.worker.jobs == [] and len(app.discord_hold) == 1,
          (app.worker.jobs, len(app.discord_hold)))


@section("a restart drops what is held, and says so")
def _restart():
    check("something is held", len(app.discord_hold) == 1)
    app._save_on_exit()
    check("closing writes down how many were dropped", A.load_settings().get("discord_held_dropped") == 1)
    app.settings["discord_held_dropped"] = 1
    app.streamer_restart_note()
    check("the next start says so", "dropped" in app.status.cget("text").lower()
          and "1 Discord post" in app.status.cget("text"), app.status.cget("text"))
    check("once", "discord_held_dropped" not in app.settings)


@section("off again: the names at once, and what was held is sent")
def _off_again():
    app.worker = Worker()
    on(streamer_mode=False)
    tick()
    check("the badge goes", not shown(app.streamer_badge))
    check("the real names are back at once", app.t_where.cget("text") == "%s / %s" % (SYSTEM, BODY),
          app.t_where.cget("text"))
    check("and the held summary is sent", len(app.discord_hold) == 0
          and [t for t, _f in app.worker.jobs] == [EDO.DISCORD_TAG], app.worker.jobs)
    app.worker.jobs = []
    app.post_discord_find({"commodity": "Gold", "system": SYSTEM, "body": BODY})
    check("and a post goes straight out again", len(app.worker.jobs) == 1)


print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
