"""1.10036: mining bodies near me, galaxy-wide (#200), with the ground odds
and the sample they rest on (#133), and Powerplay systems near a point (#230).

The table's working-out is checked as plain functions first (galaxy.py),
then the community client, then the Find window on the real toolkit with
a canned answer. The bodies are real ones the game's public data network
carried on 21 October 2026; the figures beside them are made up.

    python tests/test_110036_galaxy.py
"""
import os, sys, json, tempfile, time
import datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-galaxy-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import galaxy as GX       # noqa: E402
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


NOW = dt.datetime(2026, 10, 22, 12, 0, tzinfo=dt.timezone.utc).timestamp()


def stamp(days_ago):
    return dt.datetime.fromtimestamp(NOW - days_ago * 86400, dt.timezone.utc).isoformat()


# Shaped the way /v1/mining-bodies answers.
ANSWER = {
    "count": 4, "within_ly": 100.0, "offset": 0, "more": False, "next_offset": None,
    "centre": {"system": "Col 285 Sector FD-F b26-4", "x": 1.0, "y": 2.0, "z": 3.0},
    "commodity": "Sapphire", "as_of": stamp(0),
    "source": "the game's public data network (EDDN)",
    "bodies": [
        {"system": "Col 285 Sector FD-F b26-4", "body": "Col 285 Sector FD-F b26-4 A 7 c",
         "system_address": 9465821570449, "body_id": 31, "distance_ly": 0.0,
         "locations": 22, "dss": True, "seen": stamp(0.1), "first_seen": stamp(3),
         "ground": "Rocky body, major silicate vapour geysers",
         "odds": {"commodity": "Sapphire", "share": 0.75, "sites": 9, "of": 12},
         "mapped": 3, "mapped_deposits": 14},
        {"system": "Synuefe UW-O b53-5", "body": "Synuefe UW-O b53-5 A 5",
         "system_address": 11666339570, "body_id": 12, "distance_ly": 18.456,
         "locations": 11, "dss": False, "seen": stamp(1.2), "first_seen": stamp(1.2),
         "ground": "Rocky body",
         "odds": {"commodity": "Sapphire", "share": 0.5, "sites": 2, "of": 4},
         "mapped": 0, "mapped_deposits": 0},
        {"system": "HIP 108158", "body": "HIP 108158 3 a",
         "system_address": 2557887812314, "body_id": 7, "distance_ly": 42.1,
         "locations": 28, "dss": True, "seen": stamp(9), "first_seen": stamp(20),
         "ground": "Icy body",
         "odds": {"commodity": "Sapphire", "share": None, "sites": 0, "of": 0},
         "mapped": 1, "mapped_deposits": 2},
        {"system": "Oochost RX-S b23-0", "body": "Oochost RX-S b23-0 A 2",
         "system_address": 721151862209, "body_id": 4, "distance_ly": 96.0,
         "locations": 9, "dss": False, "seen": stamp(40), "first_seen": stamp(40),
         "ground": "", "odds": None, "mapped": 0, "mapped_deposits": 0},
    ],
}


def texts(row):
    return [cell[0] for cell in GX.cells(row, NOW)]


@section("galaxy: one body, one row of cells")
def _cells():
    check("nine columns, headed as asked", GX.HEADERS ==
          ("Body", "System", "Distance", "Locations", "DSS mapped", "Ground",
           "Odds (with n)", "Mapped by commanders", "Seen"), GX.HEADERS)
    first, second, third, fourth = ANSWER["bodies"]
    row = GX.cells(first, NOW)
    check("every cell is (text, colour key, sort key)",
          len(row) == len(GX.HEADERS) and all(len(c) == 3 for c in row), row)
    check("body, system and distance as a commander reads them",
          texts(first)[:3] == ["Col 285 Sector FD-F b26-4 A 7 c",
                               "Col 285 Sector FD-F b26-4", "0.0 Ly"], texts(first))
    check("distance sorts as a number", GX.cells(second, NOW)[2][2] == 18.456
          and texts(second)[2] == "18.5 Ly")
    check("how many locations, sorted as a number",
          texts(first)[3] == "22" and row[3][2] == 22)
    check("DSS mapped: yes, or FSS only", texts(first)[4] == "yes"
          and texts(second)[4] == "FSS scan only")
    check("the ground as the server names it, or a dash",
          texts(first)[5] == "Rocky body, major silicate vapour geysers"
          and texts(fourth)[5] == "-" and GX.cells(fourth, NOW)[5][1] == "dim")
    check("odds with the sample they rest on", texts(first)[6] == "75% (9 of 12)",
          texts(first)[6])
    check("a share sorts as a number", row[6][2] == 0.75)
    check("a big enough sample is good news", row[6][1] == "good")
    check("a small sample says so in its colour",
          texts(second)[6] == "50% (2 of 4)" and GX.cells(second, NOW)[6][1] == "warn")
    check("a ground nobody has mapped yet: no share, a sample of none",
          texts(third)[6] == "no sample yet" and GX.cells(third, NOW)[6][1] == "dim")
    check("no ground at all: no odds", texts(fourth)[6] == "-")
    check("what commanders have mapped there already",
          texts(first)[7] == "3 sites, 14 finds" and texts(third)[7] == "1 site, 2 finds"
          and texts(second)[7] == "none yet", [texts(r)[7] for r in ANSWER["bodies"]])
    check("an unmapped body is the first-find chance", GX.cells(second, NOW)[7][1] == "good")
    check("seen: today, yesterday, days ago",
          [texts(r)[8] for r in ANSWER["bodies"]] == ["today", "yesterday", "9 days ago", "40 days ago"],
          [texts(r)[8] for r in ANSWER["bodies"]])
    check("seen sorts most recent first", GX.cells(first, NOW)[8][2] < GX.cells(third, NOW)[8][2])
    commonest = dict(first, odds={"commodity": "Bastnasite", "share": 0.4, "sites": 4,
                                  "of": 10, "commonest": True})
    check("no commodity asked: the commonest there, named",
          texts(commonest)[6] == "Bastnasite 40% (4 of 10)", texts(commonest)[6])
    junk = {"system": None, "distance_ly": "far", "locations": "x", "seen": "yesterday-ish",
            "odds": "nonsense"}
    check("a row that does not hold together still draws",
          len(GX.cells(junk, NOW)) == len(GX.HEADERS) and texts(junk)[2] == "-", texts(junk))
    check("an endless distance is no distance",
          texts({"distance_ly": float("inf")})[2] == "-")


@section("galaxy: the headline")
def _headline():
    words = GX.headline(ANSWER)
    check("how many, how far, how many mapped by DSS and how many nobody has mapped",
          words.startswith("4 bodies with mining locations within 100 Ly of Col 285 Sector FD-F b26-4: "
                           "2 DSS-mapped, 2 with nothing on the community map yet."), words)
    check("the odds are said to be for the commodity asked", "Odds are for Sapphire" in words, words)
    check("the source named the way the public is told it",
          "the game's public data network (EDDN)" in words, words)
    one = dict(ANSWER, count=1, bodies=ANSWER["bodies"][:1], commodity="")
    check("one body is one body, and no commodity means the commonest",
          GX.headline(one).startswith("1 body with mining locations")
          and "commonest" in GX.headline(one), GX.headline(one))
    more = dict(ANSWER, more=True, next_offset=4)
    check("a cut list says it is the nearest ones", GX.headline(more).startswith("The nearest 4 bodies"),
          GX.headline(more))
    check("an older server, or one without the listener, says so",
          "not on the community server yet" in GX.headline({"bodies": [], "missing": "x"}))
    check("a system nobody has placed says so",
          "No position is known for Nowhere Near yet" in
          GX.headline({"bodies": [], "unplaced": "Nowhere Near"}), GX.headline({"bodies": [], "unplaced": "Nowhere Near"}))
    check("nothing near says how far it looked",
          GX.headline({"bodies": [], "count": 0, "within_ly": 25}) ==
          "Nobody has reported a body with mining locations within 25 Ly yet.",
          GX.headline({"bodies": [], "count": 0, "within_ly": 25}))
    check("an unreadable answer is None, and its headline says so",
          GX.parse("not json") is None and GX.parse("[1]") is None
          and "unreadable" in GX.headline(None))
    check("the tone of each: good, warn or dim",
          GX.tone(ANSWER) == "good" and GX.tone({"missing": "x"}) == "warn"
          and GX.tone({"bodies": []}) == "warn")


def drained(client, want):
    done = []
    for _ in range(100):
        done += client.worker.drain()
        if len(done) >= want:
            break
        time.sleep(0.05)
    return {t: (ok, m) for t, ok, m in done}


@section("the community client asks the right address")
def _client():
    seen = []
    real_get = EDO.get_json
    EDO.get_json = lambda url, headers=None, **kw: seen.append(url) or dict(ANSWER)
    try:
        client = EDO.CommunityClient(EDO.Worker())
        client.configure("", "", True, True)
        check("asks from where the commander is",
              client.mining_bodies(near=(1.5, -2.0, 30.25), within_ly=250,
                                   commodity="Sapphire", tag="mb"))
        check("or from a system by name", client.mining_bodies(near="Sol", tag="mb2"))
        check("nowhere at all is not asked", client.mining_bodies(near=None) is False
              and client.mining_bodies(near="  ") is False)
        check("Powerplay systems near a point",
              client.powerplay_systems(near=(1.0, 2.0, 3.0), within_ly=500,
                                       power="Aisling Duval", state="Fortified", tag="pp"))
        tags = drained(client, 3)
        check("all three answered", set(tags) == {"mb", "mb2", "pp"}
              and all(ok for ok, _m in tags.values()), tags)
        first = [u for u in seen if "near_x" in u and "/v1/mining-bodies?" in u][0]
        check("position, radius, commodity and a full page",
              "near_x=1.5" in first and "near_y=-2.0" in first and "near_z=30.25" in first
              and "within_ly=250" in first and "commodity=Sapphire" in first
              and "limit=500" in first, first)
        by_name = [u for u in seen if "near=Sol" in u][0]
        check("by name, the server's default radius", "/v1/mining-bodies?" in by_name
              and "within_ly=100" in by_name and "near_x" not in by_name, by_name)
        power = [u for u in seen if "/v1/powerplay/systems?" in u][0]
        check("Powerplay with power and state, and no further than the server goes",
              "power=Aisling+Duval" in power and "state=Fortified" in power
              and "within_ly=200" in power, power)
        seen[:] = []
        client.mining_bodies(near=(0, 0, 0), within_ly=50000, tag="far")
        drained(client, 1)
        check("no further than the server goes", seen and "within_ly=1000" in seen[0], seen)
        EDO.get_json = lambda url, headers=None, **kw: (_ for _ in ()).throw(
            RuntimeError("HTTP 404 Not Found"))
        client.mining_bodies(near="Sol", tag="old")
        client.powerplay_systems(near="Sol", tag="oldpp")
        got = drained(client, 2)
        bodies, systems = json.loads(got["old"][1]), json.loads(got["oldpp"][1])
        check("an older server is an empty list saying so, not an error",
              got["old"][0] and bodies["bodies"] == [] and bodies["missing"]
              and got["oldpp"][0] and systems["systems"] == [] and systems["missing"], got)
        check("and the headline reads it", "not on the community server yet" in GX.headline(bodies))
        EDO.get_json = lambda url, headers=None, **kw: (_ for _ in ()).throw(
            RuntimeError("HTTP 500 Server Error"))
        client.mining_bodies(near="Sol", tag="broken")
        got = drained(client, 1)
        check("any other failure is a failure", got["broken"][0] is False, got)
        offline = EDO.CommunityClient(EDO.Worker())
        offline.base_url = ""
        check("not connected: nothing is sent", offline.mining_bodies(near="Sol") is False
              and offline.powerplay_systems(near="Sol") is False)
    finally:
        EDO.get_json = real_get


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
    ready, can_read, can_verify = True, True, False

    def __init__(self):
        self.asked = []

    def mining_bodies(self, near=None, within_ly=100, commodity="", tag=GX.TAG):
        self.asked.append({"near": near, "within_ly": within_ly,
                           "commodity": commodity, "tag": tag})
        return True

    def commodities(self):
        return True

    def configure(self, *args, **kwargs):
        pass


if HAVE_DISPLAY:
    # Nothing in here may reach the real community server.
    def _offline(*_args, **_kwargs):
        raise RuntimeError("offline in tests")
    EDO.get_json = EDO.post_json = _offline
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


def buttons_of(widget):
    found = []
    for child in widget.winfo_children():
        if isinstance(child, A.ctk.CTkButton):
            found.append(child)
        found.extend(buttons_of(child))
    return found


@on_screen("the Find window: Mining bodies near where you are")
def _find():
    fake = app.community = FakeCommunity()
    app.watcher.star_pos = [1.0, 2.0, 3.0]
    app.watcher.system = "Col 285 Sector FD-F b26-4"
    win = app.open_find()
    pump(4)
    try:
        # 1.10038: the searches are segments of one switch at the top of
        # Find, Mining bodies the last of them, after Sell prices.
        labels = [b.cget("text") for b in buttons_of(win.mode_switch)]
        check("a Mining bodies segment beside Sell prices",
              "Mining bodies" in labels and labels.index("Mining bodies")
              == labels.index("Sell prices") + 1, labels)
        check("its answers are routed to the window", GX.TAG in A.FIND_TAGS)
        win.within.set("250 Ly")
        win.commodity.set("Sapphire, Ruby")
        win.search_bodies()
        check("asks from where you are, within the window's distance, for the first ticked",
              fake.asked and fake.asked[-1] == {"near": (1.0, 2.0, 3.0), "within_ly": 250,
                                                "commodity": "Sapphire", "tag": GX.TAG},
              fake.asked)
        check("and says it is looking", "Looking for mining bodies within 250 Ly"
              in win.status.cget("text"), win.status.cget("text"))
        win.within.set("Anywhere")
        win.commodity.set("Any")
        win.search_bodies()
        check("Anywhere is as far as the server goes, and Any asks no commodity",
              fake.asked[-1]["within_ly"] == GX.MOST_LY and fake.asked[-1]["commodity"] == "",
              fake.asked[-1])
        app.watcher.star_pos = None
        win.within.set("100 Ly")
        win.search_bodies()
        check("no position yet: from the system the game has you in, by name",
              fake.asked[-1]["near"] == "Col 285 Sector FD-F b26-4", fake.asked[-1])
        app.watcher.system = ""
        count = len(fake.asked)
        win.search_bodies()
        check("nowhere yet: nothing sent, and it says why", len(fake.asked) == count
              and "has not said where you are" in win.status.cget("text"),
              win.status.cget("text"))
        app.watcher.star_pos = [1.0, 2.0, 3.0]
        app.watcher.system = "Col 285 Sector FD-F b26-4"

        app.worker.submit(GX.TAG, lambda: json.dumps(ANSWER))
        for _ in range(100):
            time.sleep(0.05)
            app.collect_results()
            if win._kind == "bodies":
                break
        pump(2)
        check("the answer is drawn as the mining bodies table",
              win._kind == "bodies" and win._headers[:len(GX.HEADERS)] == list(GX.HEADERS)
              and len(win._rows) == 4, (win._kind, win._headers, len(win._rows)))
        check("the headline goes over it", win.status.cget("text") == GX.headline(ANSWER),
              win.status.cget("text"))
        cells = [win._cell(c) for c in win._builder(ANSWER["bodies"][0])]
        check("each row from the same cells, in the window's colours",
              [c[0] for c in cells][:9] == [c[0] for c in GX.cells(ANSWER["bodies"][0])]
              and cells[4][1] == A.GREEN, cells)
        check("the system name can be copied off a row",
              any(w == "the system name" for _l, w, _t in win._copies(ANSWER["bodies"][1])))
        win.sort_by(GX.HEADERS.index("Locations"))
        order = [r["locations"] for r in win._sorted(win._visible())]
        check("the columns sort as numbers", order == [9, 11, 22, 28], order)
        win.query.delete(0, "end")
        win.query.insert(0, "HIP 108158")
        win._paint()
        check("the system/body box narrows what is on screen",
              [r["body"] for r in win._visible()] == ["HIP 108158 3 a"], win._visible())
        win.query.delete(0, "end")
        win._paint()
        win.results(GX.TAG, json.dumps({"count": 0, "bodies": [], "missing": "x"}))
        pump(1)
        check("an older server says so, in amber",
              "not on the community server yet" in win.status.cget("text")
              and win.status.cget("text_color") == A.AMBER, win.status.cget("text"))
        win.results(GX.TAG, "HTTP 500", ok=False)
        check("a failure is said", "The server said" in win.status.cget("text"))
    finally:
        win.destroy()
        pump()
        app.community = real_community


if __name__ == "__main__":
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    sys.exit(1 if fails else 0)
