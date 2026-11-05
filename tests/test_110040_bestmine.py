"""1.10040 (#303, #305): best to mine, the Value sort, and the ground odds.

- bestmine.py says what a find, a site and a commodity are worth to mine:
  the best price known for it times what a rig typically brings back.
- Where to land: a Best to mine panel above the body table - the five
  commodities worth most here, each with the best price known near here,
  the bodies in this system with an intact shared site carrying it, and
  the ground odds.
- Find, Mode = Sites: a Value column, sortable, most valuable first.
- Where to land: a "By ground" fold, shut to begin with, listing each kind
  of ground in the system with the share of shared sites on it carrying
  each commodity. One ground open at a time.
- The line said on entering a mining location names its finds most
  valuable first, not in the order they were shared.

Pure parts run anywhere; the app on the real toolkit under xvfb:

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_bestmine.py
"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-bestmine-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import bestmine as BM      # noqa: E402
import survey as SV        # noqa: E402
import zone as ZN          # noqa: E402

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


# Prices as the app knows them: credits a tonne and where.
PRICES = {"iridium": (200000, "at Hub (Ega)"), "sapphire": (130000, "at Hub (Ega)"),
          "gold": (50000, "galactic average"), "monazite": (300000, "at Far Port (Col 1)"),
          "haematite": (3000, "galactic average")}


def price_of(name):
    return PRICES.get(SV.fold(name), (0, ""))


@section("what a rig, a find and a site are worth")
def _values():
    check("a rig of a commodity: its best price times what a rig brings back",
          BM.rig_value("Iridium", price_of) == 200000 * BM.TONNES_PER_RIG,
          BM.rig_value("Iridium", price_of))
    check("a plain number from the price source works as well as a pair",
          BM.rig_value("Gold", lambda _n: 42) == 42 * BM.TONNES_PER_RIG)
    check("nothing priced is worth nothing, never an invented number",
          BM.rig_value("Unobtainium", price_of) == 0
          and BM.rig_value("Gold", lambda _n: None) == 0)

    def broken(_name):
        raise RuntimeError("no prices")
    check("a price source that fails is worth nothing, it does not raise",
          BM.rig_value("Gold", broken) == 0)
    check("a find: its rigs at that value",
          BM.find_value({"commodity": "Sapphire", "rigs": "3"}, price_of) == 3 * 130000)
    check("rigs not counted yet count as one rig",
          BM.find_value({"commodity": "Sapphire", "rigs": ""}, price_of) == 130000)
    check("a find worked out is worth nothing today",
          BM.find_value({"commodity": "Sapphire", "rigs": 3, "amount": "Depleted"}, price_of) == 0)
    site = {"rigs": 6, "types": ["Iridium", "Gold"]}
    check("a shared site: its rigs at the average value of what it carries",
          BM.site_value(site, price_of) == 6 * (200000 + 50000) / 2.0, BM.site_value(site, price_of))
    check("a site reported worked out is worth nothing",
          BM.site_value(dict(site, worked_out=True), price_of) == 0)
    check("a site with nothing named on it is worth nothing",
          BM.site_value({"rigs": 4, "types": []}, price_of) == 0)
    check("the price and where, as a pair",
          BM.price("Monazite", price_of) == (300000.0, "at Far Port (Col 1)")
          and BM.price("Gold", lambda _n: 7) == (7.0, ""))


SITES = [
    {"system": "Ega", "planet": "Ega A 1", "spot": "1", "rigs": 6, "types": ["Iridium", "Sapphire"],
     "worked_out": False},
    {"system": "Ega", "planet": "Ega A 2", "spot": "3", "rigs": 2, "types": ["Iridium"],
     "worked_out": False},
    {"system": "Ega", "planet": "Ega A 3", "spot": "1", "rigs": 5, "types": ["Monazite"],
     "worked_out": True},
    {"system": "Other", "planet": "Other 1", "spot": "1", "rigs": 6, "types": ["Monazite"]},
]
GROUNDS = {"grounds": [
    {"ground": "Rocky body", "sites": 9, "commodities": [
        {"name": "Monazite", "share": 0.25}, {"name": "Haematite", "share": 0.77},
        {"name": "Gold", "share": 0.4}]},
    {"ground": "High metal content body", "sites": 3, "commodities": [
        {"name": "Gold", "share": 0.5}]},
    {"ground": "Icy body", "sites": 1, "commodities": [{"name": "Water", "share": 1.0}]}]}
BODIES = [
    {"body": "Ega A 1", "landable": True, "planet_class": "Rocky body", "locations": 3, "mapped": True},
    {"body": "Ega A 2", "landable": True, "planet_class": "Rocky body", "locations": 1, "mapped": True},
    {"body": "Ega A 3", "landable": True, "planet_class": "High metal content body",
     "locations": 2, "mapped": True},
    {"body": "Ega A 4", "landable": False, "planet_class": "Icy body"},
    {"body": "Ega A 5", "landable": True, "planet_class": "Rocky ice world", "locations": 0,
     "mapped": True},
]


@section("best to mine in a system: the five worth most, with where, which bodies and the odds")
def _best():
    rows = SV.rank_bodies("Ega", BODIES, GROUNDS, SITES, {}, [], [], {})
    best = BM.best_to_mine(SITES, rows, price_of, GROUNDS, system="Ega")
    names = [item["commodity"] for item in best]
    check("at most five", 0 < len(best) <= BM.TOP and BM.TOP == 5, names)
    check("a commodity an intact shared site here carries comes ahead of one the ground "
          "only might: Iridium and Sapphire first", names[:2] == ["Iridium", "Sapphire"], names)
    check("then what the ground here is likely to carry, worth most first - Monazite at 25% "
          "beats Gold at 50%", names[2:4] == ["Monazite", "Gold"], names)
    iridium = best[0]
    check("each carries the best price known and where",
          iridium["price"] == 200000 and iridium["where"] == "at Hub (Ega)", iridium)
    check("and the bodies here with an intact shared site carrying it, short names, once each",
          iridium["bodies"] == ["A 1", "A 2"], iridium["bodies"])
    monazite = next(item for item in best if item["commodity"] == "Monazite")
    check("a worked-out site does not count, nor a site in another system",
          monazite["bodies"] == [], monazite)
    check("the ground odds: the best share of shared sites on any ground here",
          abs(monazite["odds"] - 0.25) < 1e-9 and monazite["ground"] == "Rocky body", monazite)
    gold = next(item for item in best if item["commodity"] == "Gold")
    check("the better of two grounds is the one given",
          abs(gold["odds"] - 0.5) < 1e-9 and gold["ground"] == "High metal content body", gold)
    line = BM.best_line(iridium)
    check("one line for each: name, price, where, bodies",
          line.startswith("Iridium  200,000 Cr at Hub (Ega)") and "A 1, A 2" in line, line)
    line = BM.best_line(monazite)
    check("a commodity with no site here yet gives its odds",
          "25% of shared sites on Rocky body" in line and "Monazite" in line, line)
    check("nothing known: an empty list, never a raise",
          BM.best_to_mine([], [], price_of, None) == [] and BM.best_to_mine(None, None, price_of) == [])
    unpriced = BM.best_to_mine(SITES, rows, lambda _n: 0, GROUNDS, system="Ega")
    check("with no prices at all nothing is worth driving to, and nothing is listed",
          unpriced == [], unpriced)


@section("by ground: each kind of ground here, with the share of its shared sites carrying each")
def _grounds():
    rows = SV.rank_bodies("Ega", BODIES, GROUNDS, SITES, {}, [], [], {}, landable_only=False)
    folds = BM.by_ground(rows, GROUNDS)
    check("one entry per kind of ground in the system, most shared sites first",
          [f["ground"] for f in folds] == ["Rocky body", "High metal content body", "Icy body",
                                           "Rocky ice world"],
          [f["ground"] for f in folds])
    rocky = folds[0]
    check("with the bodies on it and how many shared sites the share rests on",
          rocky["bodies"] == ["A 1", "A 2"] and rocky["sites"] == 9 and not rocky["few"], rocky)
    check("and each commodity's share, highest first",
          [(n, round(s, 2)) for n, s in rocky["shares"]]
          == [("Haematite", 0.77), ("Gold", 0.4), ("Monazite", 0.25)], rocky["shares"])
    check("fewer than %d shared sites is said to be few" % SV.LAND_MIN_SITES,
          folds[2]["few"] and folds[2]["sites"] == 1 and not folds[1]["few"], folds[2])
    check("a ground nobody has shared a site on yet has no shares", folds[3]["shares"] == []
          and folds[3]["sites"] == 0 and folds[3]["ground"] == "Rocky ice world", folds[3])
    check("its heading in words", BM.ground_heading(rocky) == "Rocky body - 9 shared sites (A 1, A 2)",
          BM.ground_heading(rocky))
    check("and the share per material as a percentage",
          BM.share_words(rocky) == "Haematite 77%, Gold 40%, Monazite 25%", BM.share_words(rocky))
    check("nothing shared on it says so",
          BM.share_words(folds[3]) == "No shared sites on this kind of ground yet.")
    check("no rows is no folds", BM.by_ground([], GROUNDS) == [] and BM.by_ground(None, None) == [])


@section("the location line: the finds worth most first")
def _zone():
    finds = [{"commodity": "Gold", "rigs": "6", "amount": "High"},
             {"commodity": "Monazite", "rigs": "1", "amount": "High"},
             {"commodity": "Sapphire", "rigs": "2", "amount": "High"},
             {"commodity": "Iridium", "rigs": "", "amount": "Depleted"}]
    check("without prices, most rigs first as before",
          ZN.summary(finds) == "Gold 6R, Sapphire 2R, Monazite 1R +1 more", ZN.summary(finds))
    text = ZN.summary(finds, price_of=price_of)
    check("with prices, most valuable first: rigs at the best price known "
          "(Gold 6 x 50k beats Monazite 1 x 300k beats Sapphire 2 x 130k)",
          text == "Gold 6R, Monazite 1R, Sapphire 2R +1 more", text)
    zone = {"signal": "7", "source": "shared", "metres": 100.0, "reach_m": 5000.0}
    line = ZN.zone_line(zone, [], finds[:3], price_of=price_of)
    check("and the line says them in that order",
          line.startswith("Mining location 7 - Gold 6R, Monazite 1R, Sapphire 2R ("), line)
    worked = ZN.summary([{"commodity": "Monazite", "rigs": "6", "amount": "Depleted"},
                         {"commodity": "Gold", "rigs": "1"}], price_of=price_of)
    check("a commodity worked out everywhere goes last, whatever it is worth",
          worked == "Gold 1R, Monazite 6R (worked out)", worked)


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

import overlay as OV     # noqa: E402
OV.foreground_is_game = lambda: None
import edsmt as A        # noqa: E402
A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
    json.dump({"asked_to_share": True, "welcome_seen_version": A.APP_VERSION, "tour_done": True,
               "journal_dir": JOURNALS, "find_unlocked": True}, _f)


class Link:
    """Stands in for the community link: nothing leaves the machine."""
    ready = True
    can_read = True
    can_verify = False
    share_name = True
    enabled = True

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


def settle(seconds=2.0):
    until = time.time() + seconds
    while time.time() < until:
        pump(1)
        time.sleep(0.02)


def words_in(widget):
    out = []
    try:
        out.append(str(widget.cget("text")))
    except Exception:
        pass
    for child in widget.winfo_children():
        out.extend(words_in(child))
    return out


settle(3.0)
# The app's prices: what the commander's market book and the server know.
app.best_price = lambda name: {
    "iridium": (200000, {"station": "Hub", "system": "Ega", "sell": 200000}, "fresh"),
    "sapphire": (130000, {"station": "Hub", "system": "Ega", "sell": 130000}, "stale"),
    "gold": (50000, None, "average"), "monazite": (300000, None, "average"),
    "haematite": (3000, None, "average")}.get(SV.fold(name), (0, None, ""))
app.watcher.system = "Ega"
app.watcher.system_bodies = lambda system: [dict(b) for b in BODIES] if system == "Ega" else []


@section("the app: where to land shows the best to mine above the body table")
def _land():
    lander = app.open_land()
    settle(1.0)
    app.take_grounds(True, json.dumps(GROUNDS))
    app.take_landing(True, json.dumps({"system": "Ega", "sites": SITES[:3]}))
    settle(1.0)
    lines = app.best_to_mine("Ega")
    check("the app's best to mine for the system: Iridium first",
          lines and lines[0]["commodity"] == "Iridium", [l["commodity"] for l in lines])
    check("priced from the app's own best prices, with where they are from",
          lines[0]["where"] == "at Hub (Ega)" and lines[0]["price"] == 200000, lines[0])
    sapphire = next(l for l in lines if l["commodity"] == "Sapphire")
    check("an older price says it is older; the galactic average says so",
          "older" in sapphire["where"]
          and next(l for l in lines if l["commodity"] == "Gold")["where"] == "galactic average",
          (sapphire["where"],))
    text = " ".join(words_in(lander.best_box))
    check("the panel is headed Best to mine and lists them",
          "Best to mine" in text and "Iridium  200,000 Cr at Hub (Ega)" in text, text[:300])
    check("it sits above the body table",
          lander.best_box.winfo_rooty() < lander.scroller.winfo_rooty(),
          (lander.best_box.winfo_rooty(), lander.scroller.winfo_rooty()))


@section("the app: the By ground fold, shut to begin with, one ground open at a time")
def _fold():
    lander = app.lander
    check("shut to begin with", not lander.grounds.expanded
          and "By ground  +" == str(lander.grounds.toggle_button.cget("text")),
          lander.grounds.toggle_button.cget("text"))
    lander.grounds.toggle()
    settle(0.6)
    heads = [str(b.cget("text")) for b in lander.grounds.heads]
    check("open: one button per kind of ground in the system",
          any(h.startswith("Rocky body - 9 shared sites") for h in heads)
          and any(h.startswith("High metal content body") for h in heads), heads)
    lander.grounds.open_ground("Rocky body")
    settle(0.4)
    shown = " ".join(words_in(lander.grounds.detail))
    check("a ground opened shows the share per material",
          "Haematite 77%, Gold 40%, Monazite 25%" in shown, shown[:200])
    lander.grounds.open_ground("High metal content body")
    settle(0.4)
    check("opening another closes the first: one open at a time",
          lander.grounds.open == "High metal content body"
          and "Haematite 77%" not in " ".join(words_in(lander.grounds.detail)),
          lander.grounds.open)
    lander.grounds.open_ground("High metal content body")
    check("pressed again, it shuts", lander.grounds.open is None)
    lander.grounds.toggle()
    settle(0.4)
    check("and the fold shuts", not lander.grounds.expanded)


@section("the app: Find's sites table has a Value column, most valuable first on one click")
def _find():
    app.open_find()
    settle(1.0)
    finder = app.finder
    finder.results("sites", json.dumps({"sites": [
        dict(SITES[1], score=9.0, intact_confidence=1.0, age_days=1),
        dict(SITES[0], score=4.0, intact_confidence=1.0, age_days=1),
        dict(SITES[3], score=1.0, intact_confidence=1.0, age_days=1, rigs=1)]}), True)
    settle(1.0)
    check("the sites table has a Value heading", "Value" in finder._headers, finder._headers)
    column = finder._headers.index("Value")
    finder.sort_by(column)
    order = [r["planet"] for r in finder._sorted(finder._visible())]
    check("sorted on it: the most valuable first - 6 rigs of Iridium and Sapphire, "
          "then 2 of Iridium, then 1 of Monazite",
          order == ["Ega A 1", "Ega A 2", "Other 1"], order)
    cells = [finder._cell(c) for c in finder._builder(SITES[0])]
    check("the cell reads as credits", cells[column][0] == "990,000 Cr", cells[column])
    finder.sort_by(column)
    order = [r["planet"] for r in finder._sorted(finder._visible())]
    check("and clicked again, turned round", order == ["Other 1", "Ega A 2", "Ega A 1"], order)
    finder.results("intact", json.dumps({"sites": [dict(SITES[0], intact_confidence=1.0)]}), True)
    settle(0.5)
    check("the other tables are not given one", "Value" not in finder._headers, finder._headers)


@section("the app: the location line names the finds worth most first")
def _line():
    seen = []
    app.say = lambda text, colour=None: seen.append(text)
    rows = [{"id": "s1", "system": "Ega", "body": "Ega A 1", "location": "7", "commodity": "Gold",
             "rigs": "6", "amount": "High", "lat": "1.0", "lon": "1.0", "cmdr": "X", "shared": True},
            {"id": "s2", "system": "Ega", "body": "Ega A 1", "location": "7", "commodity": "Monazite",
             "rigs": "1", "amount": "High", "lat": "1.0001", "lon": "1.0", "cmdr": "X", "shared": True},
            {"id": "s3", "system": "Ega", "body": "Ega A 1", "location": "7", "commodity": "Haematite",
             "rigs": "3", "amount": "High", "lat": "1.0002", "lon": "1.0", "cmdr": "X", "shared": True}]
    mine, theirs = [], rows
    line = ZN.zone_line({"signal": "7"}, mine, theirs, price_of=app.mine_price)
    check("the app hands the location line its best prices",
          line.startswith("Mining location 7 - Gold 6R, Monazite 1R, Haematite 3R"), line)
    source = open(A.__file__, encoding="utf-8").read()
    check("and the line it says is made with them",
          "ZN.zone_line(zone, mine, theirs, price_of=self.mine_price)" in source)
    check("the overlay's card too",
          "ZN.status_card(signal, mine, theirs, price_of=self.mine_price)" in source)


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
