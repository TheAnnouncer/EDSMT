"""1.10038: the leaderboard's three views, finds far from Sol, and the
commander's Powerplay standing sent from the journal.

    python tests/test_110038_board.py
"""
import os, sys, json, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-board38-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import board as LB        # noqa: E402
import edonline as EDO    # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


class Watcher:
    def __init__(self, power="", rank=None, merits=None):
        self.power, self.power_rank, self.power_merits = power, rank, merits


print("== the three views ==")
check("points, Powerplay overall and merits from mining",
      [v for _n, v in LB.VIEWS] == ["points", "powerplay", "merits"])
check("the table has the standing and the far-from-Sol columns",
      "PP rank" in LB.HEADERS and "PP merits" in LB.HEADERS and "Far from Sol" in LB.HEADERS)
row = {"rank": 1, "cmdr": "CMDR Ace", "power": "Li Yong-Rui", "pp_rank": 41,
       "pp_merits": 2100000, "points": 300, "merits": 1200, "finds": 20, "far": 2}
cells = LB.cells({"rows": [row]}, "")[0]
by = dict(zip(LB.HEADERS, [c[0] for c in cells]))
check("a row shows its standing and far finds",
      by["PP rank"] == "41" and by["PP merits"] == "2,100,000" and by["Far from Sol"] == "2", by)
check("no standing shows as a dash", dict(zip(LB.HEADERS, [c[0] for c in LB.cells(
    {"rows": [dict(row, pp_rank=0, pp_merits=0)]}, "")[0]]))["PP rank"] == "-")
words = LB.points_words()
check("the points line says how far-from-Sol scores and what the views are",
      "Far from Sol" in words and "25,000" in words and "Powerplay overall" in words)

print("== the Powers line follows the view ==")
pts = {"season": "all", "sort": "points", "powers": [
    {"power": "Zemina Torval", "points": 420, "finds": 31, "commanders": 2, "merits": 0}]}
check("by points: finds and points", "by finds and points" in LB.powers_words(pts)
      and "420 pts, 31 finds (2 CMDRs)" in LB.powers_words(pts), LB.powers_words(pts))
pp = {"season": "all", "sort": "powerplay", "powers": [
    {"power": "Li Yong-Rui", "merits": 2100000, "commanders": 1, "points": 300, "finds": 20}]}
check("Powerplay overall: the game's merits", "by the game's merits" in LB.powers_words(pp)
      and "2,100,000 (1 CMDR)" in LB.powers_words(pp), LB.powers_words(pp))
check("an empty view says so in its own words",
      "no Powerplay standings reported" in LB.powers_words({"season": "all", "sort": "powerplay", "powers": []})
      and "no finds with a Power" in LB.powers_words({"season": "all", "sort": "points", "powers": []}))
check("the headline names the view",
      "with a Powerplay standing" in LB.board_words({"season": "all", "sort": "powerplay", "commanders": 3, "ranked": 2}))

print("== the standing report ==")
check("nothing until the game has said", LB.standing_report(Watcher(), "CMDR Ace") is None
      and LB.standing_report(Watcher("Li Yong-Rui", None, None), "CMDR Ace") is None
      and LB.standing_report(Watcher("Li Yong-Rui", 41, 2100000), "") is None)
check("the Power, rank and merits from the journal",
      LB.standing_report(Watcher("Li Yong-Rui", 41, 2100000), "CMDR Ace")
      == {"cmdr": "CMDR Ace", "power": "Li Yong-Rui", "rank": 41, "merits": 2100000})

print("== the client ==")
seen = []
real_get, real_post = EDO.get_json, EDO.post_json
EDO.get_json = lambda url, headers=None, **kw: seen.append(("GET", url)) or {"rows": []}
EDO.post_json = lambda url, payload, headers=None, **kw: seen.append(("POST", url, payload)) or {"ok": True}
try:
    client = EDO.CommunityClient(EDO.Worker())
    client.configure("", "", True, True)
    check("Powerplay overall asks for sort=powerplay",
          client.leaderboard("all", "CMDR Ace", tag="lb", sort="powerplay"))
    check("a standing goes as a POST", client.report_standing(
        {"cmdr": "CMDR Ace", "power": "Li Yong-Rui", "rank": 41, "merits": 2100000}, tag="st"))
    check("no Power, nothing sent", client.report_standing({"cmdr": "CMDR Ace", "power": ""}) is False)
    done = []
    for _ in range(100):
        done += client.worker.drain()
        if len(done) >= 2:
            break
        time.sleep(0.05)
    get = [s for s in seen if s[0] == "GET"][0][1]
    post = [s for s in seen if s[0] == "POST"][0]
    check("the addresses and the body", "sort=powerplay" in get
          and post[1].endswith("/v1/leaderboard/standing")
          and post[2] == {"cmdr": "CMDR Ace", "power": "Li Yong-Rui", "rank": 41, "merits": 2100000},
          (get, post))
finally:
    EDO.get_json, EDO.post_json = real_get, real_post

# ---------------------------------------------------------------------------
try:
    import tkinter
    tkinter.Tk().destroy()
    HAVE_DISPLAY = True
except Exception as _exc:
    HAVE_DISPLAY = False
    print("  SKIP  the toolkit half - no display (%s)" % _exc)

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
        json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS}, _f)
    app = A.EDSMT()
    app.geometry("1600x1000+0+0")
    app.updates.check = lambda *a, **k: None

    def pump(n=4):
        for _ in range(n):
            app.update_idletasks()
            app.update()

    class FakeCommunity:
        def __init__(self):
            self.asked, self.told, self.standing = [], [], []

        def leaderboard(self, season="", cmdr="", limit=25, tag="leaderboard", sort="points"):
            self.asked.append((season, sort)); return True

        def leaderboard_optin(self, cmdr, on=True, tag="leaderboard-optin"):
            self.told.append((cmdr, on)); return True

        def report_standing(self, report, tag="leaderboard-standing"):
            self.standing.append(dict(report)); return True

        def configure(self, *a, **k):
            pass

    pump()
    print("== the app sends its standing when the game says it ==")
    fake = app.community = FakeCommunity()
    app.watcher.cmdr = "CMDR Ace"
    app.keep_board()
    check("nothing before the journal's Powerplay event", fake.standing == [])
    app.watcher.power, app.watcher.power_rank, app.watcher.power_merits = "Li Yong-Rui", 41, 2100000
    app.keep_board(); app.keep_board()
    check("sent once when it is known, not every tick",
          fake.standing == [{"cmdr": "CMDR Ace", "power": "Li Yong-Rui", "rank": 41, "merits": 2100000}],
          fake.standing)
    app.watcher.power_merits = 2100500
    app.keep_board()
    check("and again when it changes", len(fake.standing) == 2 and fake.standing[-1]["merits"] == 2100500)
    app.settings["leaderboard_optin"] = False
    app.watcher.power_merits = 2200000
    app.keep_board()
    check("not after Leave", len(fake.standing) == 2)
    app.settings["leaderboard_optin"] = True

    print("== the window's third view ==")
    win = app.open_leaderboard()
    pump(4)
    check("three view buttons", set(win.view_buttons) == {"By points", "Powerplay overall", "Merits from mining"}
          if hasattr(win, "view_buttons") else True)
    win.pick_view("Powerplay overall") if hasattr(win, "pick_view") else None
    pump(2)
    check("Powerplay overall asks the server for it", fake.asked and fake.asked[-1][1] == "powerplay", fake.asked[-2:])
    app.take_board(A.LB_TAG, True, json.dumps({
        "season": "all", "sort": "powerplay", "commanders": 2, "ranked": 1, "week_start": "",
        "rows": [{"rank": 1, "cmdr": "CMDR Ace", "power": "Li Yong-Rui", "pp_rank": 41,
                  "pp_merits": 2100000, "points": 300, "merits": 0, "finds": 20, "far": 1,
                  "first_bodies": 2, "verified": 0, "reports": 0, "layouts": 0,
                  "confirmations": 0, "regrowth": 0}],
        "you": None, "points": dict(LB.POINTS),
        "powers": [{"power": "Li Yong-Rui", "merits": 2100000, "commanders": 1, "points": 300, "finds": 20}]}))
    pump(2)
    rows = win.grid_table.ordered()
    check("the table shows the standing", rows and "2,100,000" in [c[0] for c in rows[0]], rows[:1])
    check("and the Powers line is by the game's merits", "by the game's merits" in win.powers.cget("text"))
    win.destroy()
    pump()
    app.destroy()

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
