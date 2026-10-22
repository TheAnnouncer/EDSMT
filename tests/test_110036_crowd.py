"""1.10036: what the community has measured - how long a worked-out deposit
takes to come back (#156) and how close working rigs have gone (#157).

The words and the report are checked as plain functions first (crowd.py),
then the community client, then the app on the real toolkit: REGROWN and
the first tonne refined at a worked-out deposit each send one report, the
card says what the reports say, the figures are asked for every few hours,
and a shared layout carries the body's radius. Every place is made up.

    python tests/test_110036_crowd.py
"""
import os, sys, json, time, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-crowd-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import crowd as CR        # noqa: E402
import regrowth as RG     # noqa: E402
import edonline as EDO    # noqa: E402

fails = []
DAY = 86400.0
NOW = time.time()


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
            traceback.print_exc(limit=4)
        return fn
    return wrap


MEASURED = {"reports": 12, "commanders": 5, "low_days": 16.0, "high_days": 28.4,
            "fastest_days": 15.2, "measured": True}


def worked(**extra):
    row = {"id": "d1", "system": "Ega", "body": "Ega 1", "location": "2",
           "commodity": "platinum", "amount": "Depleted",
           "depleted_at": RG.stamp(NOW - 30 * DAY), "rechecks": RG.stamp(NOW - 12 * DAY),
           "mined": ""}
    row.update(extra)
    return row


@section("crowd: the words")
def _words():
    check("a measured range", CR.regrowth_words(MEASURED) == "reports say 16-28 d (12 reports)",
          CR.regrowth_words(MEASURED))
    few = dict(MEASURED, reports=2, commanders=1, measured=False)
    check("too few reports say so", CR.regrowth_words(few) == "reports say 16-28 d (2 reports, not measured yet)",
          CR.regrowth_words(few))
    check("short times keep a decimal", CR.regrowth_words(dict(MEASURED, low_days=0.5, high_days=1.5))
          == "reports say 0.5-1.5 d (12 reports)")
    check("one end only", CR.regrowth_words(dict(MEASURED, low_days=28.4)) == "reports say 28 d (12 reports)")
    check("no reports, no words", CR.regrowth_words({"reports": 0}) == "" and CR.regrowth_words(None) == "")
    spacing = {"layouts": 37, "commanders": 12, "closest_m": 61.5, "median_m": 79.2, "measured": True}
    check("spacing in a sentence", CR.spacing_words(spacing) ==
          "Commanders have put working rigs as close as 61.5 m apart (median closest pair 79 m, "
          "37 layouts by 12 commanders).", CR.spacing_words(spacing))
    check("whole metres without a point", "as close as 62 m apart" in CR.spacing_words(dict(spacing, closest_m=62.0)))
    check("not measured yet says so", CR.spacing_words(dict(spacing, measured=False)).endswith("not measured yet)."))
    check("nothing shared, nothing said", CR.spacing_words({"layouts": 0}) == "")


@section("crowd: the report for a deposit seen full again")
def _report():
    message = CR.regrowth_message(worked(), "seen", NOW)
    check("first empty, last look, back, and how", message and message["depleted_at"] == RG.stamp(NOW - 30 * DAY)
          and message["last_empty"] == RG.stamp(NOW - 12 * DAY) and message["regrown_at"] == RG.stamp(NOW)
          and message["how"] == "seen", message)
    check("where, with the signal and the commodity spelled properly",
          (message["system"], message["planet"], message["spot"], message["commodity"])
          == ("Ega", "Ega 1", "2", "Platinum"), message)
    check("no looks: no last look", CR.regrowth_message(worked(rechecks=""), "refined", NOW)["last_empty"] == "")
    check("a look after it came back is not a look before it",
          CR.regrowth_message(worked(), "seen", NOW - 20 * DAY)["last_empty"] == "")
    check("not depleted: no report", CR.regrowth_message(worked(amount="High"), "seen", NOW) is None)
    check("no date it was worked out: no report",
          CR.regrowth_message(worked(depleted_at="", notes=""), "seen", NOW) is None)
    check("back before it was worked out: no report", CR.regrowth_message(worked(), "seen", NOW - 40 * DAY) is None)
    check("the first own tonne is the moment it came back",
          CR.first_tonne_back(worked(mined="Platinum:1"), "Platinum"))
    check("not the second", not CR.first_tonne_back(worked(mined="Platinum:2"), "Platinum"))
    check("not a by-product", not CR.first_tonne_back(worked(mined="Platinum:0,Gold:1"), "Gold"))
    check("not on an intact deposit", not CR.first_tonne_back(worked(amount="High", mined="Platinum:1"), "Platinum"))


@section("crowd: the figures kept, and which one a deposit gets")
def _keep():
    crowd = CR.Crowd()
    check("due at once, then not for hours", crowd.due(NOW) and (setattr(crowd, "asked_at", NOW) or True)
          and not crowd.due(NOW + 3600) and crowd.due(NOW + CR.REFRESH_S))
    data = {"all": dict(MEASURED), "by_commodity": [
        dict(MEASURED, name="Platinum", reports=4, low_days=20.0, high_days=25.0),
        dict(MEASURED, name="Osmium", reports=2, low_days=1.0, high_days=2.0)]}
    check("takes the regrowth answer", crowd.take(CR.REGROWTH_TAG, data))
    check("a commodity with three or more reports gets its own",
          crowd.card_line(worked()) == "reports say 20-25 d (4 reports)", crowd.card_line(worked()))
    check("fewer: everyone's", crowd.card_line(worked(commodity="Osmium")) == "reports say 16-28 d (12 reports)")
    check("an intact deposit gets nothing", crowd.card_line(worked(amount="High")) == "")
    check("takes the spacing answer", crowd.take(CR.SPACING_TAG, {"layouts": 3}) and crowd.spacing == {"layouts": 3})
    check("junk is not taken", not crowd.take(CR.SPACING_TAG, [1]) and not crowd.take("other", {}))
    message = CR.regrowth_message(worked(), "seen", NOW)
    check("each report goes once", crowd.once(message) and not crowd.once(dict(message)))


@section("the community client: the addresses and the report")
def _client():
    seen = []
    real_get, real_post = EDO.get_json, EDO.post_json
    EDO.get_json = lambda url, headers=None, **kw: seen.append(("GET", url)) or {"all": MEASURED}
    EDO.post_json = lambda url, payload, headers=None, **kw: seen.append(("POST", url, payload)) or \
        {"ok": True, "accepted": 1, "days": 28.0, "regrowth": MEASURED}
    try:
        client = EDO.CommunityClient(EDO.Worker())
        client.configure("", "", True, True)
        check("asks for regrowth and spacing",
              client.crowd("regrowth", tag="r") and client.crowd("rig-spacing", tag="s"))
        check("nothing else", client.crowd("deposits") is False)
        message = CR.regrowth_message(worked(), "seen", NOW)
        check("sends a report", client.report_regrowth("CMDR Cee", message, tag="g"))
        done = []
        for _ in range(100):
            done += client.worker.drain()
            if len(done) >= 3:
                break
            time.sleep(0.05)
        check("all three answered", {t for t, ok, _m in done if ok} == {"r", "s", "g"}, done)
        gets = sorted(s[1].rsplit("/", 1)[-1] for s in seen if s[0] == "GET")
        posts = [s[1].rsplit("/", 1)[-1] for s in seen if s[0] == "POST"]
        check("the two figures from their own addresses, the report to its own",
              gets == ["regrowth", "rig-spacing"] and posts == ["regrowth"], (gets, posts))
        post = [s for s in seen if s[0] == "POST"][0]
        check("the report is signed with the schema, name and version",
              post[2]["$schema"] == EDO.REGROWTH_SCHEMA and post[2]["header"]["uploaderID"] == "CMDR Cee"
              and post[2]["message"] == message, post[2])
        client.configure("", "", True, False)
        client.report_regrowth("CMDR Cee", message, tag="anon")
        for _ in range(100):
            if any(s[0] == "POST" and s[2]["header"]["uploaderID"] == "" for s in seen):
                break
            time.sleep(0.05)
        check("anonymous when the name is not shared",
              any(s[0] == "POST" and s[2]["header"]["uploaderID"] == "" for s in seen))
        for _ in range(100):
            if any(t == "anon" for t, _ok, _m in client.worker.drain()):
                break
            time.sleep(0.05)
        client.configure("", "", False, True)
        check("no sharing, no report", client.report_regrowth("CMDR Cee", message) is False)
        client.configure("", "", True, True)
        EDO.get_json = lambda url, headers=None, **kw: (_ for _ in ()).throw(RuntimeError("HTTP 404 Not Found"))
        client.crowd("rig-spacing", tag="old")
        got = []
        for _ in range(100):
            got = client.worker.drain()
            if got:
                break
            time.sleep(0.05)
        check("an older server is nothing measured yet, not an error",
              got and got[0][1] and json.loads(got[0][2]) == {"layouts": 0}, got)
    finally:
        EDO.get_json, EDO.post_json = real_get, real_post


# ---------------------------------------------------------------------------
HAVE_DISPLAY = True
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    HAVE_DISPLAY = False
    print("\n  SKIP  the toolkit half of this file - no display (%s). "
          "Run it under xvfb-run." % _exc)


def on_screen(title):
    def wrap(fn):
        if not HAVE_DISPLAY:
            print("== %s ==\n  SKIP  needs a display" % title)
            return fn
        return section(title)(fn)
    return wrap


class FakeCommunity:
    ready = can_read = True

    def __init__(self):
        self.asked, self.reports, self.layouts = [], [], []

    def crowd(self, what, tag=""):
        self.asked.append((what, tag))
        return True

    def report_regrowth(self, cmdr, message, tag="regrowth-share"):
        self.reports.append((cmdr, message, tag))
        return True

    def share_layout(self, cmdr, layout):
        self.layouts.append(layout)
        return True

    def __getattr__(self, name):
        return lambda *args, **kwargs: True


if HAVE_DISPLAY:
    import overlay as OV    # noqa: E402
    OV.foreground_is_game = lambda: None
    import edsmt as A       # noqa: E402
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
        json.dump({"asked_to_share": True, "journal_dir": JOURNALS}, _f)
    app = A.EDSMT()
    app.geometry("1400x900+0+0")
    app.updates.check = lambda *args, **kwargs: None
    real_community = app.community

    def pump(times=4):
        for _ in range(times):
            app.update_idletasks()
            app.update()

    pump()


@on_screen("the app asks for the figures every few hours and keeps them")
def _follow():
    fake = app.community = FakeCommunity()
    app.crowd = None
    check("asks for both at once", app.follow_crowd(NOW) and sorted(fake.asked) ==
          [("regrowth", CR.REGROWTH_TAG), ("rig-spacing", CR.SPACING_TAG)], fake.asked)
    check("not again an hour later", not app.follow_crowd(NOW + 3600) and len(fake.asked) == 2)
    app.take_board  # noqa - the router is shared with the leaderboard
    app.take_crowd(CR.REGROWTH_TAG, True, json.dumps({"all": MEASURED, "by_commodity": []}))
    app.take_crowd(CR.SPACING_TAG, True, json.dumps({"layouts": 6, "commanders": 3, "closest_m": 61.5,
                                                     "median_m": 79.0, "measured": True}))
    check("kept", app.crowd_figures().regrowth["all"]["reports"] == 12
          and app.crowd_figures().spacing["layouts"] == 6)
    check("a failed ask is quiet", app.take_crowd(CR.SPACING_TAG, False, "HTTP 500") is False
          and app.crowd_figures().spacing["layouts"] == 6)


@on_screen("REGROWN and the first tonne back each tell the community map once")
def _report_app():
    fake = app.community = FakeCommunity()
    app.crowd_figures().sent = set()
    app.crowd_figures().take(CR.REGROWTH_TAG, {"all": MEASURED, "by_commodity": []})
    app.watcher.cmdr = "CMDR Cee"
    store = app.store
    app.here = lambda: ("Ega", "Ega 1")
    store.set_location("Ega", "Ega 1", "2", lat=10.0, lon=20.0, radius_m=1500000.0)
    store.add_deposit(system="Ega", body="Ega 1", location="2", commodity="Platinum", rigs="4",
                      amount="Depleted", density="Medium", lat="10.000000", lon="20.000000",
                      depleted_at=RG.stamp(NOW - 30 * DAY), rechecks=RG.stamp(NOW - 12 * DAY))
    row = [d for d in store.deposits if d["body"] == "Ega 1" and d["commodity"] == "Platinum"][-1]
    app.on_pick(row)
    pump()
    card = app.detail.cget("text")
    check("the card of a worked-out deposit says what the reports say",
          "reports say 16-28 d (12 reports)" in card, card)
    app.selected = row
    app.set_active()
    check("REGROWN sends one report, with the first date and the last look",
          len(fake.reports) == 1 and fake.reports[0][0] == "CMDR Cee"
          and fake.reports[0][1]["how"] == "seen"
          and fake.reports[0][1]["depleted_at"] == RG.stamp(NOW - 30 * DAY)
          and fake.reports[0][1]["last_empty"] == RG.stamp(NOW - 12 * DAY)
          and fake.reports[0][2] == CR.REGROWTH_SHARE_TAG, fake.reports)
    app.take_crowd(CR.REGROWTH_SHARE_TAG, True, json.dumps({"ok": True, "accepted": 1, "days": 29.6,
                                                            "regrowth": MEASURED}))
    check("and says thanks with the time", "came back after 30 days" in app.status.cget("text"),
          app.status.cget("text"))
    store.update_deposit(row["id"], amount="Depleted", depleted_at=RG.stamp(NOW - 20 * DAY),
                         rechecks="", mined="")
    note = {"in_srv": True, "lat": 10.0, "lon": 20.0, "radius_m": 1500000.0,
            "system": "Ega", "body": "Ega 1", "commodity": "Platinum",
            "when": RG.stamp(NOW - 60)}
    app.credit_refined(note)
    check("the first tonne refined at a worked-out deposit is a report, timed by the journal",
          len(fake.reports) == 2 and fake.reports[1][1]["how"] == "refined"
          and fake.reports[1][1]["regrown_at"] == RG.stamp(NOW - 60), fake.reports[1:])
    app.credit_refined(dict(note, when=RG.stamp(NOW - 30)))
    check("the second is not", len(fake.reports) == 2)
    app.take_crowd(CR.REGROWTH_SHARE_TAG, False, "HTTP 503")
    check("a refused report is said, not hidden", "Regrowth report" in app.status.cget("text"))


@on_screen("a shared rig layout carries the body's radius")
def _layout():
    app.game = app.watcher
    app.watcher.radius_m = 1500000.0
    rigs = [{"lat": 10.0, "lon": 20.0, "n": 1}, {"lat": 10.001, "lon": 20.0, "n": 2}]
    layout = app.rig_layout(rigs, "Ega", "Ega 1", "2")
    check("radius in metres", layout and layout["radius_m"] == 1500000.0, layout)
    app.watcher.radius_m = 0
    check("unknown: left out as None", app.rig_layout(rigs, "Ega", "Ega 1", "2")["radius_m"] is None)


@on_screen("Settings: the measured spacing under the rig spacing box")
def _settings():
    # The app asked the real server when it started; on a machine that can
    # reach it, that answer arrives late and would replace these figures.
    real_take = app.take_crowd
    app.take_crowd = lambda *args, **kwargs: None
    app.crowd_figures().take(CR.SPACING_TAG, {"layouts": 6, "commanders": 3, "closest_m": 61.5,
                                              "median_m": 79.0, "measured": True})
    win = A.SettingsWindow(app)
    pump(4)
    try:
        texts = []

        def walk(widget):
            for child in widget.winfo_children():
                try:
                    texts.append(str(child.cget("text")))
                except Exception:
                    pass
                walk(child)
        walk(win)
        check("it says what commanders have measured", any(
            t.startswith("From the community map: Commanders have put working rigs as close as 61.5 m")
            for t in texts), [t for t in texts if "community map" in t][:3])
    finally:
        win.destroy()
        pump()
        app.take_crowd = real_take
    app.community = real_community


if __name__ == "__main__":
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    sys.exit(1 if fails else 0)
