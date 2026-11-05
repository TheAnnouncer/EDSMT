"""1.10040: Find's Powerplay search - mine-to-sell rows for a goal (#231, #232).

Find has a sixth search, Powerplay. Its filters are My power (Auto from the
journal, one of the twelve Powers, or None), Goal (Reinforce, Acquire,
Undermine), Contested by, Commodity, Within, Pad, Demand, Price age, State
and Show. One row per place to mine and place to sell: the site, its
system's Power and state, the station, its pad, demand and price age, how
far apart the two are, and an estimate an hour - "-" for merits an hour
whenever the community map has not measured enough to say. A line says how
fresh the Powerplay state is. A server too old to have the search hides it.

The answers come from a stub server on this machine: 20 systems across
every state and two Powers, three stations and a fleet carrier.

    python tests/test_110040_powerplay.py
"""
import os, sys, json, tempfile, threading, time, urllib.parse
import datetime as dt
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-pp40-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import ppsearch as PPS    # noqa: E402
import finder as FD       # noqa: E402

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


NOW = dt.datetime(2026, 10, 29, 16, 0, tzinfo=dt.timezone.utc).timestamp()


def zstamp(hours):
    """A journal time: the shape a session row keeps."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(NOW - hours * 3600))


def stamp(days=0.0, hours=0.0):
    return dt.datetime.fromtimestamp(NOW - days * 86400 - hours * 3600,
                                     dt.timezone.utc).isoformat()


P1, P2 = "Aisling Duval", "Zemina Torval"
# The stub's galaxy: 20 systems across every state and two Powers.
SYSTEMS = {
    "Alpha Strong": (P1, "Stronghold", [P1]), "Alpha Fort": (P1, "Fortified", [P1, P2]),
    "Alpha Exploit": (P1, "Exploited", [P1]), "Near Unocc": ("", "Unoccupied", [P1, P2]),
    "Far Unocc": ("", "Unoccupied", [P1]), "Fort Unocc": ("", "Unoccupied", [P2]),
    "Fort Edge": ("", "Unoccupied", [P1]), "Beta Strong": (P2, "Stronghold", [P2]),
    "Beta Fort": (P2, "Fortified", [P2, P1]), "Beta Exploit": (P2, "Exploited", [P2]),
    "Beta Far Exploit": (P2, "Exploited", [P2]), "Gamma Quiet": ("", "", []),
    "Gamma Unocc": ("", "Unoccupied", [P2]), "Filler Strong": (P2, "Stronghold", [P2]),
    "Filler Fort": (P1, "Fortified", [P1]), "Filler Exploit": (P1, "Exploited", [P1, P2]),
    "Filler Unocc": ("", "Unoccupied", [P1, P2]), "Filler Unocc Two": ("", "Unoccupied", [P1]),
    "Filler Exploit Two": (P2, "Exploited", [P2]), "Filler Fort Two": (P2, "Fortified", [P2, P1]),
}
# Three stations, and a fleet carrier that pays best of all.
STATIONS = {
    "Alpha Port": {"system": "Alpha Strong", "pad": "L", "ls": 500, "price": 300000,
                   "demand": 500, "seen": stamp(hours=1), "station_type": "Coriolis"},
    "Near Hub": {"system": "Near Unocc", "pad": "M", "ls": 1200, "price": 280000,
                 "demand": 1000, "seen": stamp(days=2), "station_type": "Outpost"},
    "Beta Dock": {"system": "Beta Fort", "pad": None, "ls": None, "price": 260000,
                  "demand": 20, "seen": stamp(days=10), "station_type": "CraterPort"},
    "K7Q-12Z": {"system": "Alpha Strong", "pad": "L", "ls": 10, "price": 900000,
                "demand": 2000, "seen": stamp(hours=1), "station_type": "FleetCarrier"},
}


def row(system, body, station, distance, apart=0.0, merits=None, cr=None, intact=0.97,
        commodity="Platinum", eligible=True):
    power, state, powers = SYSTEMS[system]
    sell = dict(STATIONS[station], station=station)
    sell_system = SYSTEMS[sell["system"]]
    return {"mine": {"system": system, "body": body, "spot": "1", "commodity": commodity,
                     "rigs": 6, "amount": "Major", "density": "High", "intact": intact,
                     "worked_out": False, "last_seen": stamp(days=1), "found_by": "CMDR One",
                     "verified": False, "power": power, "state": state,
                     "contested_by": [p for p in powers if p != power],
                     "distance_ly": distance},
            "sell": dict(sell, power=sell_system[0], state=sell_system[1],
                         contested_by=[p for p in sell_system[2] if p != sell_system[0]],
                         source="community"),
            "mine_sell_ly": apart, "eligible": eligible,
            "why": "made up for the test",
            "est": {"tonnes_hr": 100.0 if cr else None, "cr_hr": cr, "merits_hr": merits,
                    "basis": {"n": 7 if merits else 2, "commanders": 3 if merits else 1,
                              "published": merits is not None}}}


FRESH = {"as_of": stamp(hours=2), "systems": 19,
         "line": "Powerplay state as of 14:00, 19 systems"}


def answer(goal, rows, **extra):
    return dict({"count": len(rows), "rows": rows, "goal": goal, "power": P1,
                 "freshness": FRESH, "more": False, "limit": 30}, **extra)


ANSWERS = {
    "reinforce": answer("reinforce", [
        row("Alpha Strong", "Alpha Strong 1 a", "Alpha Port", 0.0, merits=13200, cr=30000000),
        # A carrier the server should never send. If one ever comes, it is
        # still not shown.
        row("Alpha Strong", "Alpha Strong 1 a", "K7Q-12Z", 0.0)]),
    "acquire": answer("acquire", [
        row("Alpha Strong", "Alpha Strong 1 a", "Near Hub", 0.0, apart=25.0)]),
    "undermine": answer("undermine", [
        row("Beta Fort", "Beta Fort 1", "Beta Dock", 25.0, intact=0.4)]),
}


@section("the query each goal sends")
def _query():
    spec = PPS.spec(power=PPS.AUTO, goal="Reinforce")
    check("Reinforce, my Power from the journal, nothing else set",
          PPS.query(spec, pledge=P1) == {"goal": "reinforce", "power": P1, "limit": 30},
          PPS.query(spec, pledge=P1))
    check("Auto with no pledge in the journal sends no Power",
          PPS.query(spec, pledge="") == {"goal": "reinforce", "limit": 30})
    check("None is no Power, whatever the journal says",
          "power" not in PPS.query(PPS.spec(power="None"), pledge=P1))
    check("a Power picked is sent as picked", PPS.query(
        PPS.spec(power=P2), pledge=P1)["power"] == P2)
    full = PPS.spec(power=PPS.AUTO, goal="Acquire", contested="Two", state="Fortified",
                    show="100", commodities=["Platinum", "Monazite"], pad="L",
                    min_demand=50, max_demand=5000, age_s=86400, tonnes_hr=123.44)
    check("Acquire with every filter set",
          PPS.query(full, pledge=P1) == {
              "goal": "acquire", "power": P1, "opposing": "two", "state": "Fortified",
              "limit": 100, "commodity": "Platinum,Monazite", "pad": "L", "min_demand": 50,
              "max_demand": 5000, "price_age_h": 24, "tonnes_hr": 123.4},
          PPS.query(full, pledge=P1))
    under = PPS.spec(power=PPS.AUTO, goal="Undermine", contested=P2, range_rule=False)
    check("Undermine against a named Power, the range switch off",
          PPS.query(under, pledge=P1) == {"goal": "undermine", "power": P1, "opposing": P2,
                                          "range_rule": "false", "limit": 30},
          PPS.query(under, pledge=P1))
    check("the range switch on is the server's own default, so it is not sent",
          "range_rule" not in PPS.query(PPS.spec(goal="Undermine"), pledge=P1))
    check("Show is capped at the server's 200", PPS.query(PPS.spec(show="5000"), P1)["limit"] == 200
          and PPS.query(PPS.spec(show="nonsense"), P1)["limit"] == 30)
    check("the choices are the ticket's",
          PPS.POWER_CHOICES[0] == PPS.AUTO and PPS.POWER_CHOICES[-1] == "None"
          and len(PPS.POWER_CHOICES) == 14
          and [g for g, _k in PPS.GOALS] == ["Reinforce", "Acquire", "Undermine"]
          and PPS.GOALS[0][0] == PPS.spec()["goal"]
          and [c for c, _k in PPS.CONTESTED[:5]] == ["Any", "None", "One", "Two", "Multiple"]
          and len(PPS.CONTESTED) == 17
          and list(PPS.STATES) == ["Any", "Stronghold", "Fortified", "Exploited",
                                   "Unoccupied", "Contested"]
          and list(PPS.SHOW) == ["10", "30", "50", "100", "200"])


@section("the rows and the columns")
def _rows():
    flat = PPS.rows(ANSWERS["reinforce"])
    check("a carrier the server sent anyway is not a row",
          [r["station"] for r in flat] == ["Alpha Port"], [r["station"] for r in flat])
    heads = PPS.headers("reinforce")
    check("the columns 3.1 lists, the sell system only for Acquire",
          list(heads) == ["System", "Distance", "Power", "State", "Contested by", "Body",
                          "Signal", "Commodity", "Rigs", "Amount / Density", "Still there",
                          "Last seen", "Found by", "Sell station", "Pad", "Ls", "Sell price",
                          "Demand", "Price age", "Mine-to-sell Ly", "Est. Cr/hr",
                          "Est. merits/hr"]
          and PPS.headers("acquire")[14] == "Sell system"
          and len(PPS.headers("acquire")) == len(heads) + 1, heads)
    cells = dict(zip(heads, [c[0] for c in PPS.cells(flat[0], now=NOW)]))
    check("the mine half", cells["System"] == "Alpha Strong" and cells["Distance"] == "0.0 Ly"
          and cells["Power"] == P1 and cells["State"] == "Stronghold"
          and cells["Contested by"] == "-" and cells["Body"] == "Alpha Strong 1 a"
          and cells["Signal"] == "1" and cells["Commodity"] == "Platinum" and cells["Rigs"] == "6"
          and cells["Amount / Density"] == "Major / High" and cells["Still there"] == "97%"
          and cells["Last seen"] == "yesterday" and cells["Found by"] == "CMDR One", cells)
    check("the sell half", cells["Sell station"] == "Alpha Port" and cells["Pad"] == "L"
          and cells["Ls"] == "500 Ls" and cells["Sell price"] == "300,000 Cr"
          and cells["Demand"] == "500" and cells["Price age"] == "1 h"
          and cells["Mine-to-sell Ly"] == "same system", cells)
    check("and the estimate, with merits an hour when the community has measured it",
          cells["Est. Cr/hr"] == "30,000,000" and cells["Est. merits/hr"] == "13,200", cells)
    under = PPS.rows(ANSWERS["undermine"])[0]
    cells = dict(zip(heads, [c[0] for c in PPS.cells(under, now=NOW)]))
    check("merits an hour is a dash when nobody has measured enough", cells["Est. merits/hr"] == "-"
          and cells["Est. Cr/hr"] == "-", cells)
    check("an unknown pad and Ls are dashes, not guesses", cells["Pad"] == "-" and cells["Ls"] == "-")
    check("who else is in the system is named", cells["Contested by"] == P1, cells)
    check("an old price says how old", cells["Price age"] == "10 d", cells)
    acq = PPS.rows(ANSWERS["acquire"])[0]
    cells = dict(zip(PPS.headers("acquire"), [c[0] for c in PPS.cells(acq, now=NOW, goal="acquire")]))
    check("Acquire shows where it is sold and how far that is",
          cells["Sell system"] == "Near Unocc" and cells["Mine-to-sell Ly"] == "25.0 Ly", cells)
    sorts = [c[2] for c in PPS.cells(flat[0], now=NOW)]
    check("numbers sort as numbers", sorts[heads.index("Sell price")] == 300000
          and sorts[heads.index("Est. merits/hr")] == 13200
          and sorts[heads.index("Distance")] == 0.0, sorts)
    dash = [c[2] for c in PPS.cells(under, now=NOW)][heads.index("Est. merits/hr")]
    check("and a dash sorts below every number", dash < 0, dash)
    shades = [c[1] for c in PPS.cells(under, now=NOW)]
    check("a site less likely to be there is shaded", shades[heads.index("Still there")] == "warn",
          shades)


@section("the freshness line, and the older server")
def _fresh():
    check("the server's own line", PPS.freshness(ANSWERS["reinforce"])
          == "Powerplay state as of 14:00, 19 systems")
    check("nothing heard yet says so", PPS.freshness({"rows": [], "missing": "x"})
          == "Powerplay state: none on the community map yet.")
    check("an answer from a server without the search is the older-server tell",
          PPS.older({"rows": [], "older": True}) and not PPS.older(ANSWERS["acquire"])
          and not PPS.older({"rows": [], "missing": "listener not set up"}))
    check("a server's word for itself is the empty-table line",
          "nobody" in PPS.empty_text(ANSWERS["acquire"]).lower()
          or "no " in PPS.empty_text(ANSWERS["acquire"]).lower())
    check("no pledge says the rows earn nothing until one is made",
          PPS.pledge_note({"rows": [{"eligible": False}]}) != ""
          and PPS.pledge_note(ANSWERS["reinforce"]) == "")


@section("my own rate of mining goes with the search")
def _rate():
    runs = [{"started": zstamp(3), "ended": zstamp(2), "mined": "Platinum:120"},
            {"started": zstamp(6), "ended": zstamp(4), "mined": "Platinum:100;Monazite:60"},
            {"started": zstamp(9), "ended": zstamp(8), "mined": "Platinum:100"},
            {"started": zstamp(10), "ended": zstamp(10), "mined": ""}]
    check("the median of the sessions that dug something", PPS.own_rate(runs) == 100.0,
          PPS.own_rate(runs))
    check("none yet is none", PPS.own_rate([]) == 0.0 and PPS.own_rate(None) == 0.0)


# -- the stub server -------------------------------------------------------------

class Stub(BaseHTTPRequestHandler):
    """The community server, as far as this search goes. `old` makes it a
    server from before the search existed: 404, as FastAPI says it."""
    asked = []
    old = False

    def do_GET(self):
        parts = urllib.parse.urlsplit(self.path)
        query = dict(urllib.parse.parse_qsl(parts.query))
        Stub.asked.append((parts.path, query))
        if parts.path != "/v1/powerplay/search" or Stub.old:
            return self._send(404, {"detail": "Not Found"})
        return self._send(200, ANSWERS.get(query.get("goal", "reinforce"),
                                           answer("reinforce", [])))

    def _send(self, code, body):
        raw = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_args):
        pass


SERVER = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
threading.Thread(target=SERVER.serve_forever, daemon=True).start()
STUB_URL = "http://127.0.0.1:%d" % SERVER.server_address[1]

import edonline as EDO   # noqa: E402


def drained(worker, tag, seconds=10.0):
    end = time.time() + seconds
    while time.time() < end:
        for got in worker.drain():
            if got[0] == tag:
                return got
        time.sleep(0.02)
    return None


@section("the community client: the query string, and an older server told apart")
def _client():
    worker = EDO.Worker()
    client = EDO.CommunityClient(worker)
    client.base_url = STUB_URL
    for goal, extra, wanted in (
            ("Reinforce", {}, {"goal": "reinforce", "power": P1, "limit": "30"}),
            ("Acquire", {"contested": "Two", "pad": "L"},
             {"goal": "acquire", "power": P1, "opposing": "two", "pad": "L", "limit": "30"}),
            ("Undermine", {"contested": P2, "range_rule": False},
             {"goal": "undermine", "power": P1, "opposing": P2, "range_rule": "false",
              "limit": "30"})):
        Stub.asked.clear()
        sent = client.powerplay_search(near=(1.0, 2.0, 3.0), within_ly=50, tag=PPS.TAG,
                                       **PPS.query(PPS.spec(goal=goal, **extra), P1))
        got = drained(worker, PPS.TAG)
        check("%s: sent, and answered" % goal, sent and got and got[1], got)
        check("%s: the query string" % goal, Stub.asked and Stub.asked[0] == (
            "/v1/powerplay/search", dict(wanted, near_x="1.0", near_y="2.0", near_z="3.0",
                                         within_ly="50.0")), Stub.asked)
        check("%s: the server's rows come back as they were sent" % goal,
              json.loads(got[2])["rows"] == ANSWERS[goal.lower()]["rows"])
    Stub.asked.clear()
    client.powerplay_search(near="Alpha Strong", within_ly=0, tag=PPS.TAG, goal="reinforce")
    drained(worker, PPS.TAG)
    check("near a system by name, and Anywhere sends no radius",
          Stub.asked and Stub.asked[0][1] == {"near": "Alpha Strong", "goal": "reinforce"},
          Stub.asked)
    Stub.asked.clear()
    check("a radius with nowhere to measure it from is not sent at all",
          client.powerplay_search(near=None, within_ly=50, tag=PPS.TAG) is False
          and not Stub.asked)
    check("a parameter the server does not take is not sent",
          client.powerplay_search(near="Alpha Strong", tag=PPS.TAG, nonsense="x")
          and drained(worker, PPS.TAG) and "nonsense" not in Stub.asked[-1][1], Stub.asked[-1:])
    Stub.old = True
    try:
        client.powerplay_search(near="Alpha Strong", tag=PPS.TAG, goal="reinforce")
        got = drained(worker, PPS.TAG)
    finally:
        Stub.old = False
    data = json.loads(got[2]) if got and got[1] else {}
    check("an older server's 404 is an answer that says so, not an error",
          got and got[1] and PPS.older(data) and data.get("rows") == [], got)
    offline = EDO.CommunityClient(worker)
    offline.base_url = ""
    check("nothing is sent without a server", offline.powerplay_search(near="Alpha Strong") is False)


# -- the Find window, on the real toolkit -------------------------------------------

HAVE_DISPLAY = True
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    HAVE_DISPLAY = False
    print("\n  SKIP  the window half of this file - no display (%s)." % _exc)


def on_screen(title):
    def wrap(fn):
        if not HAVE_DISPLAY:
            print("== %s ==\n  SKIP  needs a display" % title)
            return fn
        return section(title)(fn)
    return wrap


class FakeCommunity:
    """Records what Find asks for; never goes near a server."""
    ready, can_read, can_verify = True, True, False

    def __init__(self):
        self.calls = []

    def powerplay_search(self, **kwargs):
        self.calls.append(("powerplay_search", kwargs))
        return True

    def sites(self, **kwargs):
        self.calls.append(("sites", kwargs))
        return True

    def commodities(self):
        return True

    def configure(self, *args, **kwargs):
        pass


if HAVE_DISPLAY:
    _real_get = EDO.get_json

    def _local_only(url, *args, **kwargs):
        if not str(url).startswith(STUB_URL):
            raise RuntimeError("offline in tests")
        return _real_get(url, *args, **kwargs)
    EDO.get_json = _local_only
    EDO.post_json = lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("offline in tests"))
    import overlay as OV    # noqa: E402
    OV.foreground_is_game = lambda: None
    import edsmt as A       # noqa: E402
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
        json.dump({"asked_to_share": True, "welcome_seen_version": A.APP_VERSION,
                   "tour_done": True, "journal_dir": JOURNALS}, _f)
    app = A.EDSMT()
    app.geometry("1600x1000+0+0")
    app.updates.check = lambda *args, **kwargs: None
    real_community = app.community
    fake = app.community = FakeCommunity()
    app.watcher.star_pos = [1.0, 2.0, 3.0]
    app.watcher.system = "Alpha Strong"
    app.powerbook.me["power"] = P1

    def pump(times=4):
        for _ in range(times):
            app.update_idletasks()
            app.update()

    def settle_until(cond, seconds=15.0):
        end = time.time() + seconds
        while time.time() < end:
            if cond():
                return True
            pump(1)
            time.sleep(0.02)
        return bool(cond())

    pump()


def walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from walk(child)


def shown(widget):
    try:
        return bool(widget.winfo_viewable())
    except Exception:
        return False


def texts(widget):
    out = []
    for child in walk(widget):
        # A table on the tree view (1.10040) says what its rows show.
        if callable(getattr(child, "texts", None)):
            out.extend(child.texts())
        try:
            out.append(str(child.cget("text")))
        except Exception:
            pass
    return out


def segments(win):
    return [str(b.cget("text")) for b in walk(win.mode_switch)
            if isinstance(b, A.ctk.CTkButton)]


def pick_mode(win, label):
    segment = [b for b in walk(win.mode_switch) if isinstance(b, A.ctk.CTkButton)
               and str(b.cget("text")) == label]
    segment[0].invoke()
    pump(3)


def parts(win):
    """Every filter of the Find window, by the name the tickets give it."""
    f = win._filters
    return {"commodity": [win.commodity], "min_rigs": [win.min_rigs],
            "min_types": [win.min_types], "seen": [win.max_age], "within": [win.within],
            "place": [win.query], "hide_worked": [win.hide_worked_box],
            "verified": [win.verified_box], "from": [f.far_box], "pad": [f.pad_box],
            "station": [f.station_box], "carriers": [f.carriers_box],
            "price_age": [f.age_box], "min_price": [f.price_box],
            "demand": [f.demand_low, f.demand_high], "power_state": [f.power_state_box],
            "power_side": [f.power_side_box], "show": [f.show_box],
            "pp_power": [win.pp_power_box], "pp_goal": [win.pp_goal_box],
            "pp_contested": [win.pp_contested_box], "pp_state": [win.pp_state_box],
            "pp_show": [win.pp_show_box], "pp_note": [win.pp_note]}


POWERPLAY_FILTERS = ["commodity", "demand", "pad", "pp_contested", "pp_goal", "pp_note",
                     "pp_power", "pp_show", "pp_state", "price_age", "within"]


@on_screen("Find: Powerplay is the sixth search, with its own filters")
def _mode():
    win = app.open_find()
    pump(4)
    check("six searches on the switch, Powerplay last",
          segments(win) == ["Sites", "Still there", "Deposits", "Sell prices",
                            "Mining bodies", "Powerplay"], segments(win))
    check("finder knows it as the sixth mode", [k for k, _l in FD.MODES][5] == "powerplay"
          and FD.mode_of_kind("powerplay") == "powerplay")
    pick_mode(win, "Powerplay")
    every = parts(win)
    on = sorted(k for k, ws in every.items() if all(shown(w) for w in ws))
    check("exactly its own filters are on screen", on == POWERPLAY_FILTERS, on)
    check("and finder lists the same ones",
          sorted(FD.mode_filters("powerplay")) == sorted(set(POWERPLAY_FILTERS) - {"pp_note"}),
          FD.mode_filters("powerplay"))
    check("it opens on Auto, Reinforce, Any, Any and 30",
          (win.pp_power_box.get(), win.pp_goal_box.get(), win.pp_contested_box.get(),
           win.pp_state_box.get(), win.pp_show_box.get())
          == (PPS.AUTO, "Reinforce", "Any", "Any", "30"))
    check("My power offers Auto, the twelve Powers and None",
          list(win.pp_power_box.cget("values")) == list(PPS.POWER_CHOICES))
    check("the freshness line says nothing has been asked yet",
          "Powerplay state" in win.pp_note.cget("text"), win.pp_note.cget("text"))
    check("the filter rows fit an 820-wide window",
          max(r.winfo_reqwidth() for r in (win._row_pp, win._row_pp2)) <= 800,
          [r.winfo_reqwidth() for r in (win._row_pp, win._row_pp2)])
    pick_mode(win, "Sites")
    on = [k for k in ("pp_power", "pp_goal", "pp_note") if all(shown(w) for w in every[k])]
    check("and none of them on Sites", not on, on)


@on_screen("Find: Search asks for that goal, near where I am")
def _search():
    win = app.open_find()
    pick_mode(win, "Sites")
    win.min_rigs.set("4")
    win.only_verified.set(True)
    pick_mode(win, "Powerplay")
    win.commodity.set("Platinum")
    for goal, call_goal in (("Reinforce", "reinforce"), ("Acquire", "acquire"),
                            ("Undermine", "undermine")):
        win.pp_goal_box.set(goal)
        fake.calls.clear()
        win.search_button.invoke()
        pump(2)
        check("%s: one Powerplay search, and nothing else" % goal,
              [c[0] for c in fake.calls] == ["powerplay_search"], fake.calls)
        kwargs = fake.calls[0][1] if fake.calls else {}
        check("%s: the goal, my Power from the journal, the commodity" % goal,
              kwargs.get("goal") == call_goal and kwargs.get("power") == P1
              and kwargs.get("commodity") == "Platinum" and kwargs.get("tag") == PPS.TAG, kwargs)
        check("%s: near where I am, within the window's distance" % goal,
              list(kwargs.get("near") or []) == [1.0, 2.0, 3.0]
              and kwargs.get("within_ly") == A.DISTANCE_CHOICES[A.DEFAULT_DISTANCE], kwargs)
        check("%s: filters out of sight do not go with it" % goal,
              not {"min_rigs", "verified", "min_types"} & set(kwargs), kwargs)
    win.pp_contested_box.set(P2)
    win.pp_state_box.set("Fortified")
    win.pp_show_box.set("100")
    win._filters.pad_box.set("L only")
    A.set_entry(win._filters.demand_low, "50")
    win._filters.age_box.set("24 hours")
    win.pp_power_box.set(P2)
    fake.calls.clear()
    win.search_button.invoke()
    pump(2)
    kwargs = fake.calls[0][1] if fake.calls else {}
    check("every Powerplay filter goes as the server takes it",
          kwargs.get("opposing") == P2 and kwargs.get("state") == "Fortified"
          and kwargs.get("limit") == 100 and kwargs.get("pad") == "L"
          and kwargs.get("min_demand") == 50 and kwargs.get("price_age_h") == 24
          and kwargs.get("power") == P2, kwargs)
    win.pp_power_box.set("None")
    fake.calls.clear()
    win.search_button.invoke()
    pump(2)
    check("None sends no Power", fake.calls and "power" not in fake.calls[0][1], fake.calls)
    win._filters.reset()
    pump(2)
    check("Reset puts the Powerplay filters back as well",
          (win.pp_power_box.get(), win.pp_goal_box.get(), win.pp_contested_box.get(),
           win.pp_state_box.get(), win.pp_show_box.get())
          == (PPS.AUTO, "Reinforce", "Any", "Any", "30"))
    win.min_rigs.set("0")
    win.only_verified.set(False)


@on_screen("Find: the answer, drawn - never a carrier, a dash where nobody knows")
def _drawn():
    win = app.open_find()
    app.community = real_community
    real_community.base_url = STUB_URL
    pick_mode(win, "Powerplay")
    win.commodity.set("Any")
    win.pp_goal_box.set("Reinforce")
    win.search_button.invoke()
    check("the stub's Reinforce rows arrive", settle_until(
        lambda: "Alpha Port" in texts(win.table)), win.status.cget("text"))
    words = texts(win.table)
    check("under the columns 3.1 lists", all(h in words for h in PPS.headers("reinforce")),
          [h for h in PPS.headers("reinforce") if h not in words])
    check("never the fleet carrier", "K7Q-12Z" not in words and "900,000 Cr" not in words)
    check("merits an hour the community has measured", "13,200" in words)
    check("the freshness line", win.pp_note.cget("text") == FRESH["line"]
          and shown(win.pp_note), win.pp_note.cget("text"))
    check("and the count", win.status.cget("text").startswith("1 result"),
          win.status.cget("text"))
    win.pp_goal_box.set("Undermine")
    win.search_button.invoke()
    check("Undermine's row arrives", settle_until(lambda: "Beta Dock" in texts(win.table)))
    row = win._rows[0] if win._rows else {}
    cells = [c[0] for c in win._builder(row)] if row else []
    heads = list(win._headers)
    check("merits an hour is a dash when nobody has measured enough",
          cells and cells[heads.index("Est. merits/hr")] == "-", cells)
    win.pp_goal_box.set("Acquire")
    win.search_button.invoke()
    check("Acquire's row arrives, with where it is sold",
          settle_until(lambda: "Near Hub" in texts(win.table))
          and "Sell system" in texts(win.table) and "Near Unocc" in texts(win.table))
    check("Copy all carries the rows", "Near Hub" in win.as_text())
    win.query.delete(0, "end")
    win.query.insert(0, "Zzz not a system")
    win._paint()
    check("the system box, out of sight here, does not narrow the table",
          "Near Hub" in texts(win.table))
    win.query.delete(0, "end")
    saved = win._filters.snapshot()
    win.pp_goal_box.set("Reinforce")
    win._filters.restore(saved)
    check("a saved search keeps the Powerplay filters", win.pp_goal_box.get() == "Acquire"
          and saved.get("mode") == "powerplay", saved.get("pp"))


@on_screen("Find: a server without the search hides it")
def _older():
    win = app.open_find()
    pick_mode(win, "Powerplay")
    Stub.old = True
    try:
        win.search_button.invoke()
        check("the switch loses Powerplay", settle_until(
            lambda: "Powerplay" not in segments(win)), segments(win))
    finally:
        Stub.old = False
    check("Find goes back to Sites, and says why", win.mode == "sites"
          and "Powerplay" in win.status.cget("text"), (win.mode, win.status.cget("text")))
    check("the other five are still there", segments(win) == [
        "Sites", "Still there", "Deposits", "Sell prices", "Mining bodies"], segments(win))
    win.set_mode("powerplay")
    check("and it cannot be chosen while hidden", win.mode == "sites", win.mode)
    win.destroy()
    pump(2)
    again = app.open_find()
    pump(3)
    check("a Find opened later knows too", "Powerplay" not in segments(again), segments(again))


if HAVE_DISPLAY:
    try:
        app.destroy()
    except Exception:
        pass

print("\n%d failure(s)" % len(fails) if fails else "\nFAILURES: 0")
sys.exit(1 if fails else 0)
