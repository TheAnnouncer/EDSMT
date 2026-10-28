"""1.10036: the community leaderboard (#158).

The window's working-out is checked as plain functions first (board.py),
then the community client, then the app and the window on the real
toolkit. Everyone who shares a find is on the board until they press Leave.
Seasons: the week since the Powerplay tick (Thursday 07:00 UTC), this month,
last month, all time; Powerplay merits from mined cargo sit beside the
points, with totals per Power. Every commander here is made up.

    python tests/test_110036_leaderboard.py
"""
import os, sys, json, tempfile
import datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-board-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import board as LB        # noqa: E402
import edonline as EDO    # noqa: E402

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
            traceback.print_exc(limit=4)
        return fn
    return wrap


ANSWER = {"season": "2026-10", "now": "2026-10", "previous": "2026-09",
          "commanders": 4, "ranked": 3,
          "rows": [{"rank": 1, "cmdr": "CMDR Bee", "points": 1240, "finds": 96,
                    "first_bodies": 9, "verified": 4, "reports": 12, "layouts": 2,
                    "power": "Aisling Duval", "merits": 5400},
                   {"rank": 2, "cmdr": "CMDR Ace", "points": 310, "finds": 22,
                    "first_bodies": 2, "verified": 0, "reports": 3, "layouts": 1}],
          "you": {"rank": 3, "cmdr": "CMDR Cee", "points": 27, "finds": 2,
                  "first_bodies": 0, "verified": 0, "reports": 1, "layouts": 0},
          "points": dict(LB.POINTS),
          "powers": [{"power": "Aisling Duval", "merits": 5400, "commanders": 1},
                     {"power": "Zemina Torval", "merits": 800, "commanders": 2}]}


@section("board: seasons")
def _seasons():
    october = dt.datetime(2026, 10, 21, tzinfo=dt.timezone.utc)
    january = dt.datetime(2027, 1, 3, tzinfo=dt.timezone.utc)
    check("this month asks the server's default", LB.season_for("This month", october) == "")
    check("last month is the one before", LB.season_for("Last month", october) == "2026-09"
          and LB.season_for("Last month", january) == "2026-12")
    check("all time is all", LB.season_for("All time") == "all")
    check("four seasons, this week first", [n for n, _v in LB.SEASONS] ==
          ["This week", "This month", "Last month", "All time"]
          and LB.season_for("This week") == "week")
    U = dt.timezone.utc
    check("the week turns at the Powerplay tick, Thursday 07:00 UTC",
          LB.week_start(dt.datetime(2026, 10, 22, 7, 0, tzinfo=U)) == dt.datetime(2026, 10, 22, 7, 0, tzinfo=U)
          and LB.week_start(dt.datetime(2026, 10, 22, 6, 59, tzinfo=U)) == dt.datetime(2026, 10, 15, 7, 0, tzinfo=U)
          and LB.week_start(dt.datetime(2026, 10, 21, 12, 0, tzinfo=U)) == dt.datetime(2026, 10, 15, 7, 0, tzinfo=U))
    check("said from the tick", LB.season_words("week", dt.datetime(2026, 10, 23, tzinfo=U))
          == "the week since the tick on Thursday 22 October"
          and LB.season_words("week", None, "2026-10-15T07:00:00+00:00")
          == "the week since the tick on Thursday 15 October")
    check("said as a month and a year", LB.season_words("2026-10") == "October 2026"
          and LB.season_words("all") == "all time"
          and LB.season_words("", october) == "October 2026")
    check("the app's points match the server's", LB.POINTS ==
          {"find": 10, "complete": 2, "first_body": 15, "verified": 5,
           "report": 3, "agreed": 2, "layout": 5, "confirmed_old": 3, "regrowth": 5})
    words = LB.points_words({"find": 12})
    check("how points are given, from the answer when it has them",
          words.startswith("Points: 12 a find") and "+15 for the first find on a body" in words, words)


@section("board: the table and your line")
def _table():
    rows = LB.cells(ANSWER, "CMDR Cee")
    check("the top rows and then you, from outside them",
          [r[1][0] for r in rows] == ["CMDR Bee", "CMDR Ace", "CMDR Cee"], rows)
    check("your row is marked", [r[0][1] for r in rows] == ["", "", "you"])
    check("points with thousands commas, sorted as numbers",
          rows[0][5][0] == "1,240" and rows[0][5][2] == 1240)
    check("the Power and its merits beside the points",
          rows[0][2][0] == "Aisling Duval" and rows[0][6][0] == "5,400"
          and rows[1][2][0] == "-" and rows[1][6][0] == "0")
    inside = LB.cells(ANSWER, "cmdr ace")
    check("inside the top you are not listed twice, whatever the case",
          [r[1][0] for r in inside] == ["CMDR Bee", "CMDR Ace"] and inside[1][0][1] == "you", inside)
    check("someone else's `you` is never shown",
          [r[1][0] for r in LB.cells(ANSWER, "CMDR Dee")] == ["CMDR Bee", "CMDR Ace"])
    check("fifteen columns, as headed", len(LB.HEADERS) == 15
          and all(len(r) == len(LB.HEADERS) for r in rows))
    check("Power and Merits after the name, old sites seen and regrowth their own",
          LB.HEADERS[2:7] == ("Power", "PP rank", "PP merits", "Points", "Merits")
          and LB.HEADERS[11] == "Old sites seen" and LB.HEADERS[13] == "Regrowth")
    check("your merits are in your line when you have some",
          LB.you_words(dict(ANSWER, you=dict(ANSWER["you"], merits=1200, power="Zemina Torval")),
                       "CMDR Cee", True, True)
          == "CMDR Cee: number 3 of 3 this season, 27 points, 1,200 merits for Zemina Torval.")
    check("the Powers line, most merits first as the server sent them",
          LB.powers_words(dict(ANSWER, sort="merits")) == "Powers, October 2026, merits from mining: "
          "Aisling Duval 5,400 (1 CMDR)  |  Zemina Torval 800 (2 CMDRs).",
          LB.powers_words(dict(ANSWER, sort="merits")))
    check("no merits yet says so", "no merits from mining for all time yet"
          in LB.powers_words({"season": "all", "sort": "merits", "powers": []}))
    check("by merits, the headline counts those with merits",
          LB.board_words(dict(ANSWER, sort="merits")).endswith("3 with merits from mining."))
    paid = {"event": "PowerplayMerits", "merits": 800, "when": "2026-10-22T09:00:00Z"}
    check("merits for a sale become a report with the Power and the time",
          LB.merits_report(paid, "Aisling Duval", "CMDR Cee") ==
          {"cmdr": "CMDR Cee", "power": "Aisling Duval", "merits": 800,
           "when": "2026-10-22T09:00:00Z"})
    check("no Power, no name or no merits: nothing to send",
          LB.merits_report(paid, "", "CMDR Cee") is None
          and LB.merits_report(paid, "Aisling Duval", "") is None
          and LB.merits_report(dict(paid, merits=0), "Aisling Duval", "CMDR Cee") is None)
    check("no name yet: start the game", "journal" in LB.you_words(ANSWER, "", True, True))
    check("left the board: Join puts you back", "Join puts CMDR Cee back on it"
          in LB.you_words(ANSWER, "CMDR Cee", False, True))
    check("joined: your place", LB.you_words(ANSWER, "CMDR Cee", True, True)
          == "CMDR Cee: number 3 of 3 this season, 27 points.")
    check("joined with nothing yet", "no points this season yet" in
          LB.you_words(dict(ANSWER, you=None), "CMDR Cee", True, True))
    check("the headline", LB.board_words(ANSWER) ==
          "October 2026: 4 commanders on the board, 3 with points.", LB.board_words(ANSWER))
    check("an older server says so",
          "no leaderboard yet" in LB.board_words({"missing": "x", "rows": []}))
    check("an empty board says so", LB.board_words({"season": "all", "commanders": 0})
          == "Nobody has joined the board yet - all time.")
    check("an unreadable answer is None", LB.parse("not json") is None and LB.parse("[1]") is None
          and LB.parse(json.dumps(ANSWER))["ranked"] == 3)


@section("board: who is told what, and when")
def _sending():
    on = {"leaderboard_optin": True}
    off = {"leaderboard_optin": False}
    check("everyone is on the board unless they left", LB.should_send({}, "CMDR Cee", {}) == (True, True))
    check("on, with a name: send on", LB.should_send(on, "CMDR Cee", {}) == (True, True))
    check("once a session", LB.should_send(on, "CMDR Cee", {"cmdr cee": True})[0] is False)
    check("an alt seen later is told too", LB.should_send(on, "CMDR Alt", {"cmdr cee": True}) == (True, True))
    check("no name yet: nothing", LB.should_send(on, "", {}) == (False, False))
    check("never joined, never told off", LB.should_send(off, "CMDR Cee", {}) == (False, False))
    check("after the switch went off: told off once",
          LB.should_send(off, "CMDR Cee", {}, tell_off=True) == (True, False)
          and LB.should_send(off, "CMDR Cee", {"cmdr cee": False}, tell_off=True)[0] is False)
    check("a change is a change of what is wanted",
          LB.changed(off, on) and LB.changed(on, off) and not LB.changed({}, on)
          and LB.changed({}, off))


@section("the community client asks the right address")
def _client():
    seen = []
    real_get, real_post = EDO.get_json, EDO.post_json
    EDO.get_json = lambda url, headers=None, **kw: seen.append(("GET", url)) or dict(ANSWER)
    EDO.post_json = lambda url, payload, headers=None, **kw: seen.append(("POST", url, payload)) or \
        {"ok": True, "cmdr": payload["cmdr"], "on": payload.get("on")}
    try:
        client = EDO.CommunityClient(EDO.Worker())
        client.configure("", "", True, True)
        check("asks for a season with your name", client.leaderboard("all", "CMDR Cee", 50, tag="lb"))
        check("and by merits", client.leaderboard("week", "CMDR Cee", 50, tag="lbm", sort="merits"))
        check("merits go as a POST", client.report_merits(
            {"cmdr": "CMDR Cee", "power": "Aisling Duval", "merits": 800,
             "when": "2026-10-22T09:00:00Z"}, tag="mer"))
        check("an empty report is not sent", client.report_merits({}) is False)
        check("opt-in goes as a POST", client.leaderboard_optin("CMDR Cee", False, tag="lbo"))
        check("no name, no opt-in", client.leaderboard_optin("  ") is False)
        done = []
        for _ in range(100):
            done += client.worker.drain()
            if len(done) >= 4:
                break
            import time
            time.sleep(0.05)
        tags = {t: (ok, m) for t, ok, m in done}
        check("all answered", set(tags) == {"lb", "lbm", "lbo", "mer"}
              and all(ok for ok, _m in tags.values()), done)
        get = [s for s in seen if s[0] == "GET"][0][1]
        weekly = [s for s in seen if s[0] == "GET"][1][1]
        check("the weekly board by merits asks for both", "season=week" in weekly
              and "sort=merits" in weekly and "sort=" not in get, (get, weekly))
        mer = [s for s in seen if s[0] == "POST" and s[1].endswith("/v1/leaderboard/merits")]
        check("the merits go to their own address", mer and mer[0][2] ==
              {"cmdr": "CMDR Cee", "power": "Aisling Duval", "merits": 800,
               "when": "2026-10-22T09:00:00Z"}, mer)
        check("the address carries season, name and limit",
              "/v1/leaderboard?" in get and "season=all" in get and "cmdr=CMDR+Cee" in get
              and "limit=50" in get, get)
        post = [s for s in seen if s[0] == "POST" and s[1].endswith("/optin")][0]
        check("and the opt-in its own", post[1].endswith("/v1/leaderboard/optin")
              and post[2] == {"cmdr": "CMDR Cee", "on": False}, post)
        EDO.get_json = lambda url, headers=None, **kw: (_ for _ in ()).throw(RuntimeError("HTTP 404 Not Found"))
        client.leaderboard("", "CMDR Cee", tag="old")
        for _ in range(100):
            got = client.worker.drain()
            if got:
                break
            import time
            time.sleep(0.05)
        data = json.loads(got[0][2])
        check("an older server is an empty board saying so, not an error",
              got[0][1] and data["rows"] == [] and "no leaderboard" in data["missing"], got)
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
    def __init__(self):
        self.asked, self.told, self.sorts, self.merits = [], [], [], []

    def leaderboard(self, season="", cmdr="", limit=25, tag="leaderboard", sort="points"):
        self.asked.append((season, cmdr, limit, tag))
        self.sorts.append(sort)
        return True

    def report_merits(self, report, tag="leaderboard-merits"):
        self.merits.append((report, tag))
        return True

    def leaderboard_optin(self, cmdr, on=True, tag="leaderboard-optin"):
        self.told.append((cmdr, on, tag))
        return True

    def configure(self, *args, **kwargs):
        pass


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


@on_screen("the app: off by default, on only when asked, once a session")
def _app():
    fake = app.community = FakeCommunity()
    check("everyone is on the board out of the box", A.DEFAULT_SETTINGS["leaderboard_optin"] is True
          and app.settings.get("leaderboard_optin") is True)
    check("there is a tip for it", "leaderboard_optin" in A.SETTING_TIPS)
    app.watcher.cmdr = "CMDR Cee"
    app.keep_board()
    check("the commander in the journal is put on the board, once",
          fake.told == [("CMDR Cee", True, A.LB_OPTIN_TAG)], fake.told)
    app.keep_board()
    app.keep_board()
    check("and not again every tick", len(fake.told) == 1)
    app.take_board(A.LB_OPTIN_TAG, True, json.dumps({"ok": True, "cmdr": "CMDR Cee", "on": True}))
    check("the status line says so", "on the community leaderboard as CMDR Cee"
          in app.status.cget("text"), app.status.cget("text"))
    app.take_board(A.LB_OPTIN_TAG, False, "HTTP 503")
    app.keep_board()
    check("a refusal is tried again", fake.told[-1] == ("CMDR Cee", True, A.LB_OPTIN_TAG) and len(fake.told) == 2)
    data = dict(app.settings)
    data["community_share_cmdr_name"] = False
    app.apply_settings(data)
    check("a settings file cannot take the name off the finds any more",
          app.settings["community_share_cmdr_name"] is True and len(fake.told) == 2, fake.told)
    app.set_board(False)
    check("Leave sends off", fake.told[-1] == ("CMDR Cee", False, A.LB_OPTIN_TAG))
    count = len(fake.told)
    app.watcher.cmdr = "CMDR Alt"
    app.keep_board()
    check("an alt played after leaving is told off as well, once",
          fake.told[count:] == [("CMDR Alt", False, A.LB_OPTIN_TAG)], fake.told[count:])
    app.watcher.cmdr = "CMDR Cee"
    app.set_board(True)
    check("Join puts you back", fake.told[-1] == ("CMDR Cee", True, A.LB_OPTIN_TAG), fake.told[-1:])
    app.watcher.power = "Aisling Duval"
    paid = {"event": "PowerplayMerits", "merits": 800, "when": "2026-10-22T09:00:00Z"}
    check("merits paid for a sale go to the board with your Power",
          app.board_merits(paid) and fake.merits[-1] == (
              {"cmdr": "CMDR Cee", "power": "Aisling Duval", "merits": 800,
               "when": "2026-10-22T09:00:00Z"}, A.LB_MERITS_TAG), fake.merits)
    app.settings["leaderboard_optin"] = False
    check("not after Leave", app.board_merits(paid) is False and len(fake.merits) == 1)
    app.settings["leaderboard_optin"] = True
    app.watcher.power = ""
    check("not when pledged to nobody", app.board_merits(paid) is False and len(fake.merits) == 1)
    import inspect
    seen = inspect.getsource(A.EDSMT.extras_seen)
    check("only merits the ledger tied to a mining sale are sent",
          'if changed and note.get("event") == "PowerplayMerits":' in seen
          and "self.board_merits(note)" in seen)


@on_screen("the leaderboard window")
def _window():
    fake = app.community = FakeCommunity()
    app.settings["leaderboard_optin"] = True
    app.settings["community_share_cmdr_name"] = True
    win = app.open_leaderboard()
    pump(4)
    check("a Leaderboard button on the main window", "leaderboard" in A.TIPS)
    check("it asks for this week, by points, with your name", fake.asked and fake.asked[-1] ==
          ("week", "CMDR Cee", LB.ROW_LIMIT, A.LB_TAG) and fake.sorts[-1] == "points", fake.asked)
    app.take_board(A.LB_TAG, True, json.dumps(ANSWER))
    pump(2)
    check("the headline", win.headline.cget("text").startswith("October 2026: 4 commanders"))
    check("your place", win.you.cget("text") == "CMDR Cee: number 3 of 3 this season, 27 points.",
          win.you.cget("text"))
    check("the button offers to leave", win.join.cget("text") == "Leave")
    rows = win.grid_table.ordered()
    check("three rows, yours in orange", len(rows) == 3 and rows[2][1][1] == A.ORANGE
          and rows[0][1][1] == A.TEXT, rows)
    block = win.grid_table.as_text()
    check("Copy all is a plain table", block.splitlines()[0].startswith("Rank | Commander | Power | PP rank")
          and "CMDR Bee | Aisling Duval | - | 0 | 1,240 | 5,400" in block, block)
    check("the Powers line is under the table", win.powers.cget("text").startswith("Powers"))
    win.pick_view("Merits from mining")
    check("Merits from mining asks the same season by merits",
          fake.sorts[-1] == "merits" and fake.asked[-1][0] == "week")
    win.pick_view("By points")
    win.pick("This month")
    check("This month asks the server's default", fake.asked[-1][0] == "" and fake.sorts[-1] == "points")
    win.pick("All time")
    check("All time asks for all", fake.asked[-1][0] == "all")
    win.pick("Last month")
    check("Last month asks for the month before", fake.asked[-1][0] == LB.previous_season(LB.season_now()))
    app.take_board(A.LB_TAG, False, "HTTP 500")
    check("a failure is said, and the table kept", "did not come" in win.status.cget("text")
          and len(win.grid_table.ordered()) == 3)
    app.take_board(A.LB_TAG, True, json.dumps({"season": "2026-09", "commanders": 1, "ranked": 0,
                                               "rows": [], "you": None}))
    pump(2)
    check("an empty season says how points come", win.grid_table.rows == []
          and "no points this season yet" in win.you.cget("text"))
    told = len(fake.told)
    win.toggle()
    check("Leave from the window turns the switch off and tells the server",
          app.settings["leaderboard_optin"] is False and fake.told[told:] ==
          [("CMDR Cee", False, A.LB_OPTIN_TAG)] and win.join.cget("text") == "Join", fake.told[told:])
    win.toggle()
    check("and Join from the window puts you back", app.settings["leaderboard_optin"] is True
          and win.join.cget("text") == "Leave")
    opened = []
    import webbrowser
    real_open = webbrowser.open
    webbrowser.open = lambda url: opened.append(url) or True
    try:
        win.open_web()
    finally:
        webbrowser.open = real_open
    check("On the web opens the board's page", opened == [LB.WEB_PAGE]
          and LB.WEB_PAGE.endswith("/leaderboard"), opened)
    again = app.open_leaderboard()
    check("asking again brings the same window forward", again is win)
    win.destroy()
    pump()
    app.take_board(A.LB_TAG, True, json.dumps(ANSWER))
    check("an answer for a closed window is no trouble", True)
    app.community = real_community


@on_screen("Settings: no community map section, no switch to take names off")
def _settings():
    win = A.SettingsWindow(app)
    pump(4)
    try:
        check("none of the community map switches is in Settings",
              not {"leaderboard_optin", "community_share_cmdr_name", "show_shared_finds",
                   "verify_my_finds"} & set(win.toggles), sorted(win.toggles))
        check("the staff token box is still there, on its own", "community_token" in win.fields)
    finally:
        win.destroy()
        pump()


if __name__ == "__main__":
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    sys.exit(1 if fails else 0)
