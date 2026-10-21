"""What 1.10035 adds to searching: Find's filters and saved searches, body
and signal search in Where to land and My sites, the best five places to
sell, and the Powerplay window.

The rules are checked as plain functions first (finder.py, powerplay.py),
then the journal reader is driven through a synthetic session and its
Powerplay notes fed to the record the app keeps, then every window is
opened on the real toolkit and its filters are worked the way a commander
works them. Every commander, station and system here is made up.

It needs a display (xvfb will do) for the last half and says SKIP, out
loud, for that half without one.

    python tests/test_110035_search.py
"""
import os, sys, json, re, time, tempfile, inspect
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-search-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import survey as SV      # noqa: E402
import finder as FD      # noqa: E402
import powerplay as PW   # noqa: E402
import journal as JN     # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def section(title):
    """Run the function under it; an exception is one failure, named."""
    def wrap(fn):
        print("== " + title + " ==")
        try:
            fn()
        except Exception as exc:                       # a missing feature
            import traceback
            check(title + " (ran to the end)", False, "%s: %s" % (type(exc).__name__, exc))
            traceback.print_exc(limit=4)
        return fn
    return wrap


NOW = time.time()


def stamp(ago_s=0):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(NOW - ago_s))


def at(minute, second=0, hour=8):
    return "2026-10-14T%02d:%02d:%02dZ" % (hour, minute, second)


def write_journal(folder, name, events, mode="w"):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), mode, encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")


# ---------------------------------------------------------------------------
# A made-up corner of the galaxy. The commander is pledged to POWER; RIVAL
# holds two systems near and far. Positions are in light years.
# ---------------------------------------------------------------------------
POWER, RIVAL = "Nakato Kaine", "Zemina Torval"
SYSTEMS = {
    "Kaine Hold":    ((0.0, 0.0, 0.0), POWER, "Stronghold"),
    "Kaine Fort":    ((100.0, 0.0, 0.0), POWER, "Fortified"),
    "Kaine Mine":    ((0.0, 50.0, 0.0), POWER, "Exploited"),
    "Open Near":     ((24.0, 0.0, 0.0), "", "Unoccupied"),
    "Open Edge":     ((0.0, -30.0, 0.0), "", "Unoccupied"),
    "Open Far":      ((0.0, 0.0, 40.0), "", "Unoccupied"),
    "Open Fort":     ((100.0, 15.0, 0.0), "", "Unoccupied"),
    "Open Fort Far": ((100.0, 0.0, 25.0), "", "Unoccupied"),
    "Torval Near":   ((0.0, 0.0, -12.0), RIVAL, "Exploited"),
    "Torval Far":    ((0.0, 0.0, -300.0), RIVAL, "Fortified"),
}


def arrive(name, when, event="FSDJump", **extra):
    pos, power, state = SYSTEMS[name]
    out = {"timestamp": when, "event": event, "StarSystem": name,
           "SystemAddress": 7000 + sorted(SYSTEMS).index(name), "StarPos": list(pos),
           "PowerplayState": state,
           "Powers": [power] if power else [POWER, RIVAL],
           "PowerplayStateControlProgress": 0.5}
    if power:
        out["ControllingPower"] = power
    out.update(extra)
    return out


def refined(when, commodity="platinum", label="Platinum"):
    return {"timestamp": when, "event": "MiningRefined", "Type": "$%s_name;" % commodity,
            "Type_Localised": label}


def transfer(when, tonnes, direction, commodity="platinum", label="Platinum"):
    return {"timestamp": when, "event": "CargoTransfer", "Transfers": [
        {"Type": commodity, "Type_Localised": label, "Count": tonnes, "Direction": direction}]}


def docked(when, station, system, kind):
    return {"timestamp": when, "event": "Docked", "StationName": station, "StationType": kind,
            "StarSystem": system, "MarketID": 3700000 + len(station)}


SESSION = [
    {"timestamp": at(0), "event": "Fileheader", "part": 1, "gameversion": "4.4.1.1"},
    {"timestamp": at(0), "event": "Commander", "Name": "Jameson", "FID": "F1"},
    {"timestamp": at(0, 1), "event": "Powerplay", "Power": POWER, "Rank": 120,
     "Merits": 50000, "TimePledged": 864000},
    arrive("Kaine Hold", at(0, 2), "Location", Docked=False),
]
for _n, _name in enumerate(["Open Near", "Open Edge", "Open Far", "Torval Near", "Kaine Fort",
                            "Open Fort", "Open Fort Far", "Torval Far", "Kaine Mine"]):
    SESSION.append(arrive(_name, at(1 + _n)))
# A system that says nothing about Powerplay.
SESSION.append({"timestamp": at(11), "event": "FSDJump", "StarSystem": "Quiet Rock",
                "SystemAddress": 6999, "StarPos": [5.0, 5.0, 5.0]})
SESSION.append(arrive("Kaine Hold", at(12)))
# Twenty tonnes mined in Kaine Hold, two of them in the same second.
SESSION += [refined(at(20, s)) for s in range(19)] + [refined(at(20, 18))]
SESSION += [
    docked(at(30), "K7Q-1HT", "Kaine Hold", "FleetCarrier"),
    transfer(at(31), 8, "tocarrier"),          # 8 t into carrier storage
    transfer(at(32), 3, "toship"),             # 3 t back off it
    {"timestamp": at(33), "event": "Undocked", "StationName": "K7Q-1HT"},
    docked(at(35), "Alpha Port", "Kaine Hold", "Coriolis"),
    {"timestamp": at(36), "event": "MarketBuy", "Type": "gold", "Type_Localised": "Gold",
     "Count": 5, "BuyPrice": 9000, "TotalCost": 45000},
    {"timestamp": at(37), "event": "MarketSell", "Type": "platinum", "Type_Localised": "Platinum",
     "Count": 4, "SellPrice": 260000, "TotalSale": 1040000, "AvgPricePaid": 0},
    {"timestamp": at(37, 6), "event": "PowerplayMerits", "Power": POWER, "MeritsGained": 100,
     "TotalMerits": 50100},
    {"timestamp": at(38), "event": "Undocked", "StationName": "Alpha Port"},
    arrive("Torval Near", at(40)),
]
SESSION += [refined(at(45, s), "osmium", "Osmium") for s in range(6)]

GAME = os.path.join(TMP, "game")
JOURNAL = "Journal.2026-10-14T080000.01.log"
write_journal(GAME, JOURNAL, SESSION)
STORE = {}


# ---------------------------------------------------------------------------
@section("the journal reader hands Powerplay over through drain_power")
def _reader():
    reader = JN.JournalWatcher(GAME)
    reader.poll()
    notes = reader.drain_power()
    kinds = {}
    for note in notes:
        kinds[note["kind"]] = kinds.get(note["kind"], 0) + 1
    check("the pledge, every system with Powerplay in it, every tonne, both transfers, the "
          "purchase and the sale are handed over",
          kinds == {"pledge": 2, "system": 12, "mined": 26, "transfer": 2, "buy": 1, "sale": 1}, kinds)
    check("and handed over once: a second drain is empty", reader.drain_power() == [])
    check("the reader knows the pledge, the rank and the merits from the journal alone",
          reader.power == POWER and reader.power_rank == 120 and reader.power_merits == 50100,
          (reader.power, reader.power_rank, reader.power_merits))
    check("and the Powerplay of the system it is in now",
          reader.power_here.get("system") == "Torval Near"
          and reader.power_here.get("power") == RIVAL and reader.power_here.get("state") == "Exploited",
          reader.power_here)
    systems = [n for n in notes if n["kind"] == "system"]
    check("a system note carries its position, power, state and the Powers present",
          systems[0]["system"] == "Kaine Hold" and systems[0]["pos"] == [0.0, 0.0, 0.0]
          and systems[0]["state"] == "Stronghold" and systems[0]["power"] == POWER
          and systems[0]["progress"] == 0.5, systems[0])
    check("a system that says nothing about Powerplay is not handed over",
          not any(n["system"] == "Quiet Rock" for n in systems))
    mined = [n for n in notes if n["kind"] == "mined"]
    check("a tonne mined is filed under the system it was mined in, by its plain name",
          mined[0]["system"] == "Kaine Hold" and mined[0]["commodity"] == "Platinum"
          and mined[-1]["system"] == "Torval Near" and mined[-1]["commodity"] == "Osmium",
          (mined[0], mined[-1]))
    same = [n["seq"] for n in mined if n["when"] == at(20, 18)]
    check("two tonnes in one second are told apart", sorted(same) == [1, 2], same)
    moves = [n for n in notes if n["kind"] == "transfer"]
    check("a transfer says which way and that it was made docked",
          [(n["direction"], n["count"], n["docked"]) for n in moves]
          == [("tocarrier", 8, True), ("toship", 3, True)], moves)
    sale = next(n for n in notes if n["kind"] == "sale")
    check("a sale says where it was made and what was paid for the goods",
          sale["system"] == "Kaine Hold" and sale["station"] == "Alpha Port" and sale["count"] == 4
          and sale["avg_paid"] == 0 and sale["total"] == 1040000, sale)
    check("the reader says what it is docked at, and forgets it on leaving",
          reader.station_type == "" and not reader.docked)
    write_journal(GAME, JOURNAL, [arrive("Kaine Hold", at(50))], mode="a")
    reader.poll()
    later = reader.drain_power()
    check("what the game appends arrives on the next read, and only that",
          [n["kind"] for n in later] == ["system"] and later[0]["system"] == "Kaine Hold", later)
    again = JN.JournalWatcher(GAME)
    again.poll()
    STORE["notes"] = again.drain_power()
    check("the same file read again by a new reader gives the same notes",
          [(n["kind"], n.get("when"), n.get("seq")) for n in STORE["notes"]]
          == [(n["kind"], n.get("when"), n.get("seq")) for n in notes + later])


# ---------------------------------------------------------------------------
def make_book(folder=None):
    book = PW.PowerBook(folder)
    for note in STORE.get("notes") or []:
        book.observe(note)
    return book


@section("the Powerplay record: the pledge, the systems, where the goods came from")
def _book():
    folder = os.path.join(TMP, "record")
    book = make_book(folder)
    STORE["book"] = book
    check("the pledge is the journal's", book.power == POWER and book.me["rank"] == 120
          and book.me["merits"] == 50100, book.me)
    check("every system with Powerplay in it is in the record, and nothing else",
          sorted(e["system"] for e in book.all_systems()) == sorted(SYSTEMS), sorted(book.systems))
    check("with where it is, so the ranges can be measured offline",
          book.position("Kaine Fort") == (100.0, 0.0, 0.0)
          and abs(book.ly("Kaine Hold", "Open Near") - 24.0) < 1e-9)
    check("the anchors of the Power are its Stronghold and Fortified systems",
          sorted(e["system"] for e in book.anchors()) == ["Kaine Fort", "Kaine Hold"])
    check("an unoccupied system has a state and no Power",
          book.entry("open near")["state"] == "Unoccupied" and book.entry("Open Near")["power"] == "")
    check("mined tonnes are queued by system: 20 mined, 8 into carrier storage, 4 sold",
          book.mined.get("platinum") == [["Kaine Hold", 8]] and book.mined.get("osmium")
          == [["Torval Near", 6]], book.mined)
    check("3 t came back off the carrier, 5 t were bought",
          book.carrier == {"platinum": 3} and book.bought == {"gold": 5}, (book.carrier, book.bought))
    hold = {"Platinum": 11, "Gold": 5, "Osmium": 6}
    check("most of the mined hold came from Kaine Hold", book.hold_origin(hold) == "Kaine Hold"
          and book.mined_where(hold) == {"Kaine Hold": 8, "Torval Near": 6}, book.mined_where(hold))
    risk = book.provenance(hold)
    check("the carrier tonnes and the bought ones are named as not earning merits",
          sorted((r["commodity"], r["tonnes"], r["why"]) for r in risk)
          == [("Gold", 5, "bought"), ("Platinum", 3, "carrier")], risk)
    check("what can earn is the hold less those", PW.counted_hold(hold, risk)
          == {"Platinum": 8, "Osmium": 6})
    check("the same notes again change nothing", not any(book.observe(n) for n in STORE["notes"]
                                                         if n["kind"] != "pledge")
          and book.mined.get("platinum") == [["Kaine Hold", 8]])
    check("a sale of mined cargo counts; one of bought stock is flagged",
          [s["counts"] for s in book.sale_flags()] == [True])
    other = PW.PowerBook()
    other.observe({"kind": "sale", "when": at(5, hour=9), "seq": 1, "commodity": "Gold",
                   "name": "Gold", "count": 5, "avg_paid": 9000, "total": 60000})
    check("a sale with something paid for the goods earns nothing, and says why",
          other.sale_flags()[0]["counts"] is False and "bought stock" in other.sale_flags()[0]["note"])
    check("the record is kept on disk", book.save() and os.path.isfile(
        os.path.join(folder, PW.POWERPLAY_FILE)))
    back = PW.PowerBook(folder)
    check("and read back whole after a restart",
          back.power == POWER and len(back.systems) == len(SYSTEMS) and back.mined == book.mined
          and back.carrier == book.carrier and back.bought == book.bought and back.range_rule is True)
    back.range_rule = False
    back.save()
    check("the Undermine range switch is kept with it", PW.PowerBook(folder).range_rule is False)
    check("selling the hold down forgets what is no longer aboard",
          back.trim_to_hold({"Platinum": 5}) and back.mined == {"platinum": [["Kaine Hold", 5]]}
          and back.carrier == {"platinum": 3} and back.bought == {}, (back.mined, back.carrier, back.bought))
    learnt = PW.PowerBook(os.path.join(TMP, "older"))
    check("the older journals give the pledge and the systems, not the ledger",
          learnt.learn_folder(GAME) > 0 and learnt.power == POWER
          and len(learnt.systems) == len(SYSTEMS) and learnt.mined == {})
    check("and a journal already read is not read again", learnt.learn_folder(GAME) == 0)
    left = PW.PowerBook()
    left.observe(PW.pledge_note({"event": "Powerplay", "Power": POWER, "Rank": 3,
                                 "timestamp": at(1)}))
    left.observe(PW.pledge_note({"event": "PowerplayLeave", "Power": POWER, "timestamp": at(2)}))
    check("leaving a Power ends the pledge", left.power == "")
    left.observe(PW.pledge_note({"event": "PowerplayDefect", "FromPower": POWER,
                                 "ToPower": RIVAL, "timestamp": at(3)}))
    check("defecting pledges to the new one, rank and merits not carried over",
          left.power == RIVAL and left.me["rank"] is None)


# ---------------------------------------------------------------------------
@section("the rules: Expand, Reinforce, Undermine - and Nothing")
def _rules():
    book = STORE["book"]

    def goal(mine, sell, rule=None):
        return book.verdict(mine, sell, rule)["goal"]

    for system in ("Kaine Hold", "Kaine Fort", "Kaine Mine"):
        check("Reinforce: mined and sold in %s, which the Power holds (%s)"
              % (system, SYSTEMS[system][2]), goal(system, system) == PW.REINFORCE)
    near = book.verdict("Kaine Hold", "Open Near")
    check("Expand: mined in the Stronghold, sold in an unoccupied system 24 Ly away (reach 30)",
          near["goal"] == PW.EXPAND and abs(near["ly"] - 24.0) < 1e-9 and near["reach"] == 30.0, near)
    check("Expand: exactly 30 Ly from a Stronghold is inside its reach",
          goal("Kaine Hold", "Open Edge") == PW.EXPAND)
    check("but 40 Ly from it is not", goal("Kaine Hold", "Open Far") == PW.NOTHING)
    check("Expand from a Fortified system: 15 Ly is inside its 20",
          goal("Kaine Fort", "Open Fort") == PW.EXPAND)
    check("and 25 Ly is not", goal("Kaine Fort", "Open Fort Far") == PW.NOTHING)
    check("an Exploited system expands nothing", goal("Kaine Mine", "Open Near") == PW.NOTHING)
    check("nor does a rival's system", goal("Torval Near", "Open Near") == PW.NOTHING)
    under = book.verdict("Torval Near", "Torval Near")
    check("Undermine: mined and sold in a rival system 12 Ly from your Stronghold",
          under["goal"] == PW.UNDERMINE and "Kaine Hold" in under["why"], under)
    check("a rival system out of range of every Stronghold and Fortified one: nothing",
          goal("Torval Far", "Torval Far") == PW.NOTHING)
    check("with the range switch off any rival system counts",
          goal("Torval Far", "Torval Far", False) == PW.UNDERMINE)
    check("Reinforce needs the same system: mined in one, sold in another of yours is nothing",
          goal("Kaine Hold", "Kaine Fort") == PW.NOTHING)
    check("Undermine needs the same system too", goal("Torval Near", "Kaine Hold") == PW.NOTHING)
    check("mined and sold in an unoccupied system earns nothing",
          goal("Open Near", "Open Near") == PW.NOTHING)
    lost = book.verdict("Kaine Hold", "Somewhere New")
    check("a system you have not been to is Unknown, and says so",
          lost["goal"] == PW.UNKNOWN and "Somewhere New" in lost["why"], lost)
    check("so is goods from a system not in the record",
          goal("Somewhere Else", "Kaine Hold") == PW.UNKNOWN)
    free = PW.PowerBook()
    for note in STORE["notes"]:
        if note["kind"] == "system":
            free.observe(note)
    check("no pledge: Unknown, and it says the pledge is missing",
          free.verdict("Kaine Hold", "Kaine Hold")["goal"] == PW.UNKNOWN
          and "pledge" in free.verdict("Kaine Hold", "Kaine Hold")["why"])
    rows = PW.system_rows(book, "Kaine Hold", (0.0, 0.0, 0.0))
    counting = [r["system"] for r in rows if r["goal"] in PW.COUNTS]
    check("the system list puts the ones that count first, nearest first",
          [r["system"] for r in rows[:3]] == ["Kaine Hold", "Open Near", "Open Edge"]
          and counting == ["Kaine Hold", "Open Near", "Open Edge"], [(r["system"], r["goal"]) for r in rows])
    priced = PW.annotate(book, [{"system": "Open Near", "sell": 1}, {"system": "Open Far", "sell": 2},
                                {"system": "", "sell": 3}], "Kaine Hold")
    check("a price row is told what selling there does", [r["goal"] for r in priced]
          == [PW.EXPAND, PW.NOTHING, PW.UNKNOWN], priced)


# ---------------------------------------------------------------------------
def learnt_rate():
    """A merit rate that has seen two sales and the merits that followed."""
    rate = SV.MeritRate()
    total = 70000
    for day, sale, gained in ((9, 6000000, 900), (10, 9000000, 1300)):
        when = "2026-10-%02dT10:00:00Z" % day
        total += gained
        rate.observe(SV.merit_note({"timestamp": when, "event": "MarketSell", "Type": "platinum",
                                    "Type_Localised": "Platinum", "Count": 30,
                                    "SellPrice": sale // 30, "TotalSale": sale, "AvgPricePaid": 0}))
        rate.observe(SV.merit_note({"timestamp": "2026-10-%02dT10:00:07Z" % day,
                                    "event": "PowerplayMerits", "Power": POWER,
                                    "MeritsGained": gained, "TotalMerits": total}))
    return rate


@section("will it count: bought and carrier goods are Nothing; merits only once learnt")
def _assess():
    book = STORE["book"]
    prices = {"Platinum": 260000, "Osmium": 90000, "Gold": 60000}
    hold = {"Platinum": 11, "Gold": 5, "Osmium": 6}
    early = PW.assess(book, SV.MeritRate(), hold, "Kaine Hold", prices=prices)
    check("in Kaine Hold the hold reinforces, mined there as the record says",
          early["goal"] == PW.REINFORCE and early["origin"] == "Kaine Hold" and early["origin_known"])
    check("with no rate learnt there is no merit estimate, and the headline says when there will be",
          early["merits"]["merits"] is None and "Estimated merits appear" in early["headline"],
          early["headline"])
    check("and it names the carrier tonnes and the bought ones",
          "came off a fleet carrier" in early["headline"] and "was bought" in early["headline"])
    rate = learnt_rate()
    check("two sales and their merits teach the rate", rate.per_credit() is not None)
    STORE["rate"] = rate
    full = PW.assess(book, rate, hold, "Kaine Hold", prices=prices)
    estimate = full["merits"]
    check("once learnt the estimate is a whole number of merits",
          isinstance(estimate["merits"], int) and estimate["merits"] > 0, estimate)
    check("for the tonnes that earn only: the 8 t Platinum mined here - not the carrier's 3, "
          "the bought Gold, or the Osmium mined in Torval Near",
          [(l["commodity"], l["tonnes"]) for l in estimate["lines"]] == [("Platinum", 8)]
          and full["earning"] == {"Platinum": 8}, estimate["lines"])
    check("and the Osmium is named as mined where selling here earns nothing",
          [(e["commodity"], e["tonnes"], e["system"]) for e in full["elsewhere"]]
          == [("Osmium", 6, "Torval Near")] and "6 t of Osmium was mined in Torval Near" in full["headline"],
          full["elsewhere"])
    away = PW.assess(book, rate, {"Osmium": 6}, "Kaine Hold", prices=prices)
    check("Osmium alone, mined in Torval Near and sold in Kaine Hold: Nothing",
          away["goal"] == PW.NOTHING and not away["counts"], away["headline"])
    more = PW.hold_merits(rate, {"Platinum": 11}, prices)["merits"]
    less = PW.hold_merits(rate, {"Platinum": 11}, prices, risky={"Platinum": 3})["merits"]
    check("tonnes that will not count are left out of the estimate", less < more, (less, more))
    check("a commodity with no price to go by is listed, not guessed",
          PW.hold_merits(rate, {"Painite": 4}, prices)["missing"] == ["Painite"])
    check("and no rate means no estimate at all", PW.hold_merits(None, hold, prices)["merits"] is None
          and PW.hold_merits(SV.MeritRate(), hold, prices)["merits"] is None)
    check("the headline gives the estimate and nothing about how it is reached",
          "about %s merits" % "{:,}".format(estimate["merits"]) in full["headline"]
          and "per credit" not in full["headline"] and "rate" not in full["headline"], full["headline"])
    bought = PW.assess(book, rate, {"Gold": 5}, "Kaine Hold", prices=prices)
    check("goods that were bought: Nothing, wherever they are sold",
          bought["goal"] == PW.NOTHING and not bought["counts"] and "bought" in bought["headline"],
          bought["headline"])
    carried = PW.assess(book, rate, {"Platinum": 3}, "Kaine Hold", prices=prices)
    check("goods that went through a fleet carrier: Nothing, though the system would reinforce",
          carried["goal"] == PW.NOTHING and carried["verdict"]["rule"] == PW.REINFORCE
          and "fleet carrier" in carried["headline"], carried["headline"])
    check("and no merits are estimated for either", not bought["merits"]["merits"]
          and not carried["merits"]["merits"])
    expand = PW.assess(book, rate, {"Platinum": 8}, "Open Near", prices=prices)
    check("mined in the Stronghold, sold 24 Ly away in Open Near: Expand",
          expand["goal"] == PW.EXPAND and expand["counts"], expand["headline"])
    under = PW.assess(book, rate, {"Osmium": 6}, "Torval Near", prices=prices)
    check("Osmium mined in Torval Near and sold there: Undermine",
          under["goal"] == PW.UNDERMINE and under["origin"] == "Torval Near", under["headline"])
    told = PW.assess(book, rate, {"Osmium": 6}, "Kaine Hold", sell="Kaine Hold", origin="Kaine Hold")
    check("where the goods were mined can be said outright", told["goal"] == PW.REINFORCE
          and told["origin"] == "Kaine Hold")
    empty = PW.assess(book, rate, {}, "Kaine Hold", prices=prices)
    check("nothing aboard says so, with what selling there would do",
          empty["headline"].startswith("Nothing aboard") and "Reinforce" in empty["headline"],
          empty["headline"])


# ---------------------------------------------------------------------------
def price(station, system, sell, demand, far, pad, kind, seen, commodity="Platinum"):
    return {"commodity": commodity, "station": station, "system": system, "sell": sell,
            "demand": demand, "distance_ly": far, "pad": pad, "station_type": kind, "seen": seen}


ROWS = [
    price("Alpha Port", "Kaine Hold", 260000, 400, 0.0, "L", "Coriolis", stamp(3600)),
    price("Bravo Outpost", "Open Near", 240000, 50, 24.0, "M", "Outpost", stamp(7200)),
    price("K7Q-1HT", "Kaine Hold", 280000, 900, 0.0, "L", "FleetCarrier", stamp(600)),
    price("Delta Works", "Torval Near", 250000, 0, 12.0, "L", "Coriolis", stamp(600)),
    price("Echo Base", "Open Far", 230000, 2000, 40.0, "", "CraterPort", stamp(5 * 86400)),
    price("Foxtrot Ring", "Far Away", 300000, 30, 600.0, "L", "Orbis Starport", stamp(3600)),
    price("Golf Hub", "No Record", 200000, 10, None, "S", "Outpost", ""),
    price("Hotel Dock", "Kaine Fort", 270000, 700, 100.0, "L", "Ocellus", stamp(1800)),
    price("India Yard", "Torval Far", 275000, 300, 300.0, "M", "AsteroidBase", stamp(1800)),
    price("Juliet Pad", "Kaine Mine", 210000, 150, 50.0, "M", "Outpost", stamp(1800)),
    price("Kilo Quay", "Open Near", 90000, 500, 24.0, "L", "Coriolis", stamp(1800), "Osmium"),
]


# One letter a row, A to K in the order above (the carrier is C).
LETTER = {r["station"]: "ABCDEFGHIJK"[n] for n, r in enumerate(ROWS)}


def first_letters(rows):
    return "".join(LETTER.get(r.get("station"), str(r.get("station") or r.get("planet") or "")[:1])
                   for r in rows)


def narrow(rows, kind="sell", **changes):
    """(kept stations as first letters, {reason: count}) - what Find does."""
    spec = FD.find_spec(**changes)
    book = STORE["book"]
    kept, counts = [], {}
    for row in rows:
        why = FD.why_hidden(row, spec, kind, NOW, book.entry, book.power)
        if why:
            counts[why] = counts.get(why, 0) + 1
        else:
            kept.append(row)
    return first_letters(kept), counts


@section("Find's filters, one at a time, and the reason for every row hidden")
def _filters():
    check("stations are known by what they are, however the type is spelt",
          [FD.station_group(k) for k in ("Coriolis", "Orbis Starport", "Outpost", "CraterPort",
                                         "OnFootSettlement", "FleetCarrier", "Fleet Carrier",
                                         "AsteroidBase", "MegaShip")]
          == ["starport", "starport", "outpost", "planetary", "settlement", "carrier",
              "carrier", "asteroid", "megaship"])
    check("a carrier with no type is known by its callsign; a name is not a type",
          FD.station_group("", "K7Q-1HT") == "carrier" and FD.station_group("", "Ray Gateway") == "")
    check("pads: L, M, Large, 3 and nothing",
          [FD.pad_rank(p) for p in ("L", "M", "Large", 3, "3", None, True, "")] == [3, 2, 3, 3, 3, 0, 0, 0])
    check("numbers typed as people type them",
          (FD.parse_number("1,500"), FD.parse_number("100k"), FD.parse_number("2.5m"),
           FD.parse_number(" 40 Ly ")) == (1500.0, 100000.0, 2500000.0, 40.0)
          and FD.parse_number("lots") is None and FD.parse_number("", 7) == 7
          and FD.parse_number("nan") is None and FD.whole_number("2.6") == 3)
    shown, why = narrow(ROWS)
    check("as the window opens: fleet carriers and Demand 0 are hidden, nothing else",
          shown == "ABEFGHIJK" and why == {"carrier": 1, "no_demand": 1}, (shown, why))
    shown, why = narrow(ROWS, no_carriers=False)
    check("carriers back on: the carrier shows, and Demand 0 still never does",
          shown == "ABCEFGHIJK" and why == {"no_demand": 1}, (shown, why))
    check("nor does the placeholder demand of a community goal",
          narrow([dict(ROWS[0], demand=999999)])[1] == {"no_demand": 1})
    shown, why = narrow(ROWS, from_ly=25)
    check("At least 25 Ly away: the near ones and the one nobody can place are hidden",
          shown == "EFHIJ" and why == {"no_demand": 1, "distance": 5}, (shown, why))
    shown, why = narrow(ROWS, to_ly=100)
    check("Within 100 Ly of me: 300 and 600 Ly are hidden, 100 Ly exactly is not",
          shown == "ABEGHJK" and why == {"no_demand": 1, "distance": 2, "carrier": 1}, (shown, why))
    shown, why = narrow(ROWS, from_ly=25, to_ly=100)
    check("both ends of the window at once: 25 to 100 Ly", shown == "EHJ", (shown, why))
    shown, why = narrow(ROWS, pad="M")
    check("Pad M or larger: a small pad and an unknown one are hidden",
          shown == "ABFHIJK" and why.get("pad") == 2, (shown, why))
    shown, why = narrow(ROWS, pad="L")
    check("Pad L only", shown == "AFHK" and why.get("pad") == 5, (shown, why))
    shown, why = narrow(ROWS, station="outpost")
    check("Station type Outposts", shown == "BGJ" and why.get("type") == 6, (shown, why))
    check("Station type Starports", narrow(ROWS, station="starport")[0] == "AFHK")
    check("Station type Planetary ports and Asteroid bases",
          narrow(ROWS, station="planetary")[0] == "E" and narrow(ROWS, station="asteroid")[0] == "I")
    shown, why = narrow(ROWS, age_s=86400)
    check("Price age 24 hours: the 5-day-old price and the undated one are hidden",
          shown == "ABFHIJK" and why.get("age") == 2, (shown, why))
    shown, why = narrow(ROWS, min_demand=100)
    check("Demand at least 100", shown == "AEHIJK" and why.get("demand") == 3, (shown, why))
    shown, why = narrow(ROWS, max_demand=1000)
    check("Demand at most 1,000", shown == "ABFGHIJK" and why.get("demand") == 1, (shown, why))
    check("Demand 100 to 1,000", narrow(ROWS, min_demand=100, max_demand=1000)[0] == "AHIJK")
    shown, why = narrow(ROWS, min_price=250000)
    check("Minimum price 250,000", shown == "AFHI" and why.get("price") == 5, (shown, why))
    shown, why = narrow(ROWS, state="Stronghold")
    check("Powerplay state Stronghold, from the commander's own record",
          shown == "A" and why.get("state") == 8, (shown, why))
    check("Powerplay state Unoccupied", narrow(ROWS, state="Unoccupied")[0] == "BEK")
    shown, why = narrow(ROWS, power="mine")
    check("My power's systems", shown == "AHJ" and why.get("power") == 6, (shown, why))
    check("Another power's", narrow(ROWS, power="other")[0] == "I")
    shown, why = narrow(ROWS, power="none")
    check("Nobody's - and a system not in the record is not taken to be nobody's",
          shown == "BEK" and why.get("power") == 6, (shown, why))
    sites = [{"system": "Kaine Hold", "planet": "Kaine Hold A 1", "distance_ly": 0.0},
             {"system": "Open Far", "planet": "Open Far 2", "distance_ly": 40.0, "pad": "S"}]
    check("on finds the price filters stand aside; distance and Powerplay do not",
          narrow(sites, "sites", pad="L", min_price=1, age_s=60)[0] == "KO"
          and narrow(sites, "sites", from_ly=10)[0] == "O"
          and narrow(sites, "sites", power="mine")[0] == "K")
    check("the published figures are never filtered",
          narrow([{"commodity": "Platinum", "station": "P"}], "published", from_ly=50, power="mine")[0] == "P")
    check("the filters that are on, in plain words",
          FD.active_filters(FD.find_spec(from_ly=25, to_ly=100, pad="L", age_s=86400, min_demand=1,
                                         max_demand=9, min_price=5, station="outpost",
                                         state="Fortified", power="mine"))
          == ["From 25 Ly", "Within 100 Ly", "Pad L", "Price age 24 hours", "Demand at least 1",
              "Demand at most 9", "Price at least 5", "Station Outposts", "No fleet carriers",
              "State Fortified", "Power My power"])
    check("nothing on but the carrier switch as the window opens",
          FD.active_filters(FD.find_spec()) == ["No fleet carriers"])
    check("a spec takes only the filters it knows", "bogus" not in FD.find_spec(bogus=1))
    line = FD.count_line(9, 11, {"carrier": 1, "no_demand": 1})
    check("the count line says how many were hidden and why",
          line.startswith("9 of 11 shown - 2 hidden by your filters: ")
          and "1 fleet carriers" in line and "1 nobody buying (Demand 0)" in line, line)
    line = FD.count_line(3, 11, {"distance": 5, "no_demand": 1, "carrier": 1, "top": 1})
    check("biggest reason first, every reason named",
          line.index("5 outside your distance window") < line.index("1 nobody buying")
          and "beyond the best five of their commodity" in line, line)
    check("nothing hidden is just the count", FD.count_line(4, 4, {}) == "4 result(s)."
          and FD.count_line(0, 0, {}) == "0 result(s).")


@section("the best five: payers most expensive first, and the five nearest")
def _best_five():
    shown = narrow(ROWS)[0]
    kept = [r for r in ROWS if LETTER[r["station"]] in shown]
    best = FD.top_per_commodity(kept, 5, "price")
    check("best five payers per commodity: Platinum by price, highest first, then Osmium",
          first_letters(best) == "FIHABK", first_letters(best))
    check("each commodity's prices go down the list",
          [r["sell"] for r in best if r["commodity"] == "Platinum"]
          == sorted((r["sell"] for r in best if r["commodity"] == "Platinum"), reverse=True))
    near = FD.top_per_commodity(kept, 5, "distance")
    check("five nearest per commodity: nearest first, the unplaced one last and out",
          first_letters(near) == "ABEJHK", first_letters(near))
    five = FD.best_five([r for r in ROWS if r["commodity"] == "Platinum"])
    check("the sell side's best five payers: most expensive first, Demand 0 never",
          first_letters(five["payers"]) == "FCIHA" and "D" not in first_letters(five["payers"]),
          first_letters(five["payers"]))
    check("its five nearest: nearest first, a tie on distance to the better price",
          first_letters(five["nearest"]) == "CABEJ", first_letters(five["nearest"]))
    check("a buyer nobody can place is never one of the nearest",
          "G" not in first_letters(five["nearest"]))
    check("a row with no price is not a payer",
          FD.best_five([dict(ROWS[0], sell=0)])["payers"] == [])


@section("saved searches, by name, on disk")
def _saved():
    folder = os.path.join(TMP, "saved")
    fav = FD.Favourites(folder)
    state = {"pad": "L only", "far": "25 Ly", "commodity": ["Platinum", "Osmium"],
             "carriers_off": True, "sort": ["Sell", True]}
    check("a search is saved under a name", fav.put("  Big   pads  ", state, "find", "2026-10-14T10:00:00Z"))
    path = os.path.join(folder, FD.SEARCHES_FILE)
    on_disk = json.load(open(path, encoding="utf-8"))
    check("in searches.json, under the tidied name, with the window it belongs to",
          on_disk["searches"]["Big pads"]["state"]["pad"] == "L only"
          and on_disk["searches"]["Big pads"]["window"] == "find", on_disk)
    back = FD.Favourites(folder)
    check("and comes back whole after a restart", back.get("Big pads") == state, back.get("Big pads"))
    fav.put("Low g", {"g_high": "1"}, "land", "2026-10-14T11:00:00Z")
    fav.put("Near", {"far": "Any"}, "find", "2026-10-14T12:00:00Z")
    check("listed newest first, each window its own",
          fav.names("find") == ["Near", "Big pads"] and fav.names("land") == ["Low g"]
          and fav.names() == ["Near", "Low g", "Big pads"], fav.names())
    check("a blank name is refused", not fav.put("   ", state))
    check("saving under a name again replaces it",
          fav.put("Near", {"far": "50 Ly"}) and fav.get("Near") == {"far": "50 Ly"})
    for n in range(FD.SEARCHES_MAX):
        fav.put("Fill %d" % n, {"n": n})
    check("there is a limit to how many are kept", len(fav.items) == FD.SEARCHES_MAX
          and not fav.put("One more", {"n": 0}) and fav.put("Near", {"far": "Any"}))
    check("deleting one takes it off the disk too",
          fav.delete("near") is False and fav.delete("Near") and "Near" not in FD.Favourites(folder).items)
    odd = fav.put("Odd", {"t": (1, 2), "nan": float("nan"), "long": "x" * 500})
    check("odd values are stored plainly", odd and fav.get("Odd") == {"t": [1, 2], "nan": None,
                                                                       "long": "x" * 200})
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("{not json")
    check("a damaged file is an empty list, not a crash", FD.Favourites(folder).items == {})
    check("with nowhere to keep them, nothing is pretended", FD.Favourites(None).save() is False)


# ---------------------------------------------------------------------------
def body(name, cls, g=None, k=None, volc="", signals=None, mapped=False, landable=True, ls=100.0,
         system="Kaine Hold", pos=(0.0, 0.0, 0.0), here=(0.0, 0.0, 0.0), raw_gravity=None):
    facts = {"planet_class": cls, "volcanism": volc, "landable": landable, "distance_ls": ls,
             "temperature_k": k}
    if raw_gravity is not None:
        facts["gravity"] = raw_gravity
    else:
        facts["gravity_g"] = g
    return FD.body_row(system, "%s %s" % (system, name), facts, signals, mapped, "", pos, here)


BODIES = [
    body("A 1", SV.HMC, 0.26, 180, "None", [{"type": "Planetary Mining Location", "count": 3},
                                            {"type": "Geological", "count": 2}], True),
    body("A 2", SV.ROCKY, 2.5, 650, "Minor Silicate Magma Volcanism",
         [{"type": "$SAA_SignalType_Geological;", "count": 1}], True, ls=900.0),
    body("A 3", SV.ICY, None, 60, "", None, False, ls=3000.0),
    body("B 1", SV.RICH, 0.9, 300, "None", [{"type": "Biological", "count": 4}], True,
         landable=False, ls=12.0),
    body("1", SV.HMC, 0.4, 210, "Metallic Magma Volcanism",
         [{"type": "Planetary Mining Location", "count": 1}], True, system="Far Rock",
         pos=(0.0, 0.0, 80.0)),
]


def bodies_left(rows=BODIES, **spec):
    kept, counts = FD.filter_bodies(rows, FD.body_spec(**spec))
    return [r["short"] if r["system"] == "Kaine Hold" else r["body"] for r in kept], counts


@section("body and signal search: type, volcanism, gravity, temperature, signals, distance")
def _bodies():
    check("gravity in the journal's m/s2 is filed in g",
          body("Z", SV.ICY, raw_gravity=9.80665)["gravity_g"] == 1.0)
    check("signals are counted by kind, whatever the game calls them",
          FD.signal_counts([{"type": "Planetary Mining Location", "count": 3},
                            {"type": "$SAA_SignalType_Biological;", "count": 2},
                            {"type": "Geological", "count": 1}, {"type": "Odd", "count": 1}])
          == {"mining": 3, "biological": 2, "geological": 1, "other": 1})
    check("and how far each body's system is from you",
          BODIES[-1]["distance_ly"] == 80.0 and BODIES[0]["distance_ly"] == 0.0)
    shown, why = bodies_left(classes=[SV.HMC])
    check("Type HMC", shown == ["A 1", "Far Rock 1"] and why == {"class": 3}, (shown, why))
    shown, why = bodies_left(volcanism=["None"])
    check("Volcanism None: a body described as having none - not one never described",
          shown == ["A 1", "B 1"] and why == {"volcanism": 3}, (shown, why))
    check("Any volcanism", bodies_left(volcanism=["Any volcanism"])[0] == ["A 2", "Far Rock 1"])
    check("Silicate magma, however the journal words it",
          bodies_left(volcanism=["Silicate magma"])[0] == ["A 2"])
    shown, why = bodies_left(g_max=1.0)
    check("Gravity up to 1 g: the heavy body and the unmeasured one are hidden",
          shown == ["A 1", "B 1", "Far Rock 1"] and why == {"gravity": 2}, (shown, why))
    check("Gravity from 0.5 g", bodies_left(g_min=0.5)[0] == ["A 2", "B 1"])
    shown, why = bodies_left(k_min=150, k_max=400)
    check("Temperature 150 to 400 K", shown == ["A 1", "B 1", "Far Rock 1"]
          and why == {"temperature": 2}, (shown, why))
    shown, why = bodies_left(signals=["Mining locations"], signal_min=2)
    check("Mining locations, at least 2", shown == ["A 1"] and why == {"signals": 4}, (shown, why))
    check("every ticked kind of signal is needed",
          bodies_left(signals=["Mining locations", "Geological"])[0] == ["A 1"]
          and bodies_left(signals=["Biological"])[0] == ["B 1"])
    check("Landable and Mapped", bodies_left(landable=True)[0] == ["A 1", "A 2", "A 3", "Far Rock 1"]
          and bodies_left(mapped=True)[0] == ["A 1", "A 2", "B 1", "Far Rock 1"])
    check("Up to 1,000 Ls from the star", bodies_left(ls_max=1000)[0] == ["A 1", "A 2", "B 1", "Far Rock 1"])
    shown, why = bodies_left(scope="here", system="Kaine Hold")
    check("This system", shown == ["A 1", "A 2", "A 3", "B 1"] and why == {"system": 1}, (shown, why))
    shown, why = bodies_left(scope="near", within_ly=50)
    check("Near here, within 50 Ly", "Far Rock 1" not in shown and why == {"distance": 1}, (shown, why))
    check("and within 100 Ly", "Far Rock 1" in bodies_left(scope="near", within_ly=100)[0])
    kept, counts = FD.filter_bodies(BODIES, FD.body_spec(g_max=0.5, classes=[SV.HMC, SV.RICH]))
    line = FD.body_count_line(len(kept), len(BODIES), counts)
    check("the line under the table says how many and why",
          line.startswith("2 of 5 bodies match - 3 hidden: 2 other kind of body, 1 gravity")
          and "gravity outside the range or unmeasured" in line, line)
    check("and with nothing hidden, just the count", FD.body_count_line(5, 5, {}) == "5 bodies.")
    check("the body filters that are on, in plain words",
          FD.body_filters_on(FD.body_spec(classes=[SV.HMC], volcanism=["None"], g_max=1.0,
                                          k_min=150, signals=["Biological"], signal_min=2,
                                          landable=True, mapped=True, ls_max=500))
          == ["Type HMC", "Volcanism None", "Gravity -1 g", "Temperature 150- K",
              "Biological at least 2", "Landable", "Mapped", "Within 500 Ls"])


@section("no rate, no formula and no private word in what this ships")
def _hygiene():
    for name in ("finder.py", "powerplay.py"):
        src = open(os.path.join(REPO, name), encoding="utf-8").read()
        check("%s has no bare except and no bind_all" % name,
              not re.search(r"^\s*except\s*:", src, re.M) and "bind_all" not in src)
    src = open(os.path.join(REPO, "powerplay.py"), encoding="utf-8").read()
    check("powerplay.py says what the estimate is, never how it is reached",
          "times the rate" not in src and "merits per credit" not in src.lower())
    leak = os.path.join(os.path.dirname(REPO), "EDSMT-Private", "LEAK-TERMS.txt")
    if os.path.exists(leak):
        terms = [t.strip().lower() for t in open(leak, encoding="utf-8")
                 if t.strip() and not t.startswith("#")]
        texts = [open(os.path.join(REPO, n), encoding="utf-8").read().lower()
                 for n in ("finder.py", "powerplay.py", "tests/test_110035_search.py")]
        hits = []
        for term in terms:
            pattern = (r"\b%s\b" % re.escape(term)) if re.fullmatch(r"[a-z]+", term) else re.escape(term)
            hits += [term for text in texts if re.search(pattern, text)]
        check("no word the public must not see is in the new search code", not hits, hits[:5])
    else:
        print("  (the private word list is not beside this checkout - nothing to check)")
    for spec in ("EDSMT.spec", "EDSMT-onefile.spec"):
        text = open(os.path.join(REPO, "build", spec), encoding="utf-8").read()
        check("%s bundles finder and powerplay" % spec,
              '"finder"' in text and '"powerplay"' in text)
    runner = open(os.path.join(HERE, "run_all.py"), encoding="utf-8").read()
    check("run_all.py runs this file, straight after the output checks",
          '("1.10035: Find filters, body search and Powerplay", "test_110035_search.py")' in runner
          and runner.index("test_110035_output.py") < runner.index("test_110035_search.py")
          < runner.index("test_gui.py"))


# ---------------------------------------------------------------------------
# The toolkit half: the real windows, driven through a synthetic journal
# ---------------------------------------------------------------------------
HAVE_DISPLAY = False
try:
    import tkinter as tk
    _probe = tk.Tk()
    _probe.destroy()
    HAVE_DISPLAY = True
except Exception as _exc:             # no display: say so, loudly
    print("\n  SKIP  the toolkit half of this file - no display (%s). "
          "Run it under xvfb-run." % _exc)


def on_screen(title):
    """Like section(), for checks that need a display."""
    def wrap(fn):
        if not HAVE_DISPLAY:
            print("== %s ==\n  SKIP  needs a display" % title)
            return fn
        return section(title)(fn)
    return wrap


def texts_in(widget):
    out = []
    for child in widget.winfo_children():
        try:
            out.append(str(child.cget("text")))
        except Exception:
            pass
        out.extend(texts_in(child))
    return out


def find_button(widget, text):
    for child in widget.winfo_children():
        try:
            if child.cget("text") == text and hasattr(child, "invoke"):
                return child
        except Exception:
            pass
        found = find_button(child, text)
        if found is not None:
            return found
    return None


if HAVE_DISPLAY:
    import customtkinter  # noqa: F401
    import overlay as OV    # noqa: E402
    OV.foreground_is_game = lambda: None
    import edsmt as A       # noqa: E402
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
        json.dump({"asked_to_share": True, "journal_dir": JOURNALS, "find_unlocked": True}, _f)
    app = A.EDSMT()
    app.geometry("1400x900+0+0")
    app.updates.check = lambda *args, **kwargs: None

    def pump(times=4):
        for _ in range(times):
            app.update_idletasks()
            app.update()

    pump()

    def scan(name, cls, gravity, kelvin, volcanism, ls):
        return {"timestamp": at(13, hour=9), "event": "Scan", "BodyName": "Kaine Hold %s" % name,
                "StarSystem": "Kaine Hold", "Landable": True, "PlanetClass": cls,
                "SurfaceGravity": gravity, "SurfaceTemperature": kelvin, "Volcanism": volcanism,
                "DistanceFromArrivalLS": ls, "Radius": 1500000.0}

    LIVE = [dict(e, timestamp=e["timestamp"].replace("T08:", "T09:")) for e in SESSION[:16]]
    LIVE += [
        scan("A 1", SV.HMC, 2.5, 180.0, "", 120.0),
        scan("A 2", SV.ROCKY, 24.5, 650.0, "minor silicate magma volcanism", 900.0),
        scan("A 3", SV.ICY, 1.0, 60.0, "", 3000.0),
        {"timestamp": at(14, hour=9), "event": "SAASignalsFound", "BodyName": "Kaine Hold A 1",
         "Signals": [{"Type": "$SAA_SignalType_PlanetaryMiningLocation;",
                      "Type_Localised": "Planetary Mining Location", "Count": 3}]},
        {"timestamp": at(14, 30, hour=9), "event": "SAASignalsFound", "BodyName": "Kaine Hold A 2",
         "Signals": [{"Type": "$SAA_SignalType_Geological;", "Type_Localised": "Geological",
                      "Count": 1}]},
    ]
    LIVE += [refined(at(20, s, hour=9)) for s in range(12)]
    LIVE += [docked(at(35, hour=9), "Hold Port", "Kaine Hold", "Coriolis"),
             {"timestamp": at(36, hour=9), "event": "MarketBuy", "Type": "gold",
              "Type_Localised": "Gold", "Count": 5, "BuyPrice": 9000, "TotalCost": 45000}]
    write_journal(JOURNALS, "Journal.2026-10-14T090000.01.log", LIVE)
    with open(os.path.join(JOURNALS, "Cargo.json"), "w", encoding="utf-8") as _f:
        json.dump({"timestamp": at(37, hour=9), "event": "Cargo", "Vessel": "Ship", "Count": 17,
                   "Inventory": [{"Name": "platinum", "Name_Localised": "Platinum", "Count": 12},
                                 {"Name": "gold", "Name_Localised": "Gold", "Count": 5}]}, _f)
    app.watcher.poll()
    app.follow_power()
    pump()


# ---------------------------------------------------------------------------
@on_screen("the app keeps the Powerplay record from the live journal")
def _live_record():
    book = app.powerbook
    check("the pledge and every system arrive through the app's own reader",
          book.power == POWER and len(book.systems) == len(SYSTEMS), (book.power, len(book.systems)))
    check("the hold aboard is the ship's: 12 t Platinum mined here, 5 t Gold bought",
          app.hold_now() == {"Platinum": 12, "Gold": 5}, app.hold_now())
    check("and the record says where the Platinum came from",
          book.hold_origin(app.hold_now()) == "Kaine Hold" and book.bought == {"gold": 5})
    check("the app's poll feeds it", "self.follow_power()" in inspect.getsource(A.EDSMT.tick))
    check("and the older journals feed it too",
          "power.learn_folder(folder" in inspect.getsource(A.EDSMT._start_backfill))
    check("the app's position of a system comes from the record when it has no other",
          app.system_position("Kaine Fort") == (100.0, 0.0, 0.0))
    app.follow_power(now=time.time() + 3600)
    on_disk = PW.PowerBook(A.DATA_DIR)
    check("it is saved beside the other records", on_disk.power == POWER
          and len(on_disk.systems) == len(SYSTEMS))


@on_screen("Find: every filter changes the table and the count line says why")
def _find_window():
    finder = app.open_find()
    pump()
    filters = finder._filters
    finder.results("sell", json.dumps({"commodity": "Platinum", "market": ROWS, "community": []}), True)
    pump()

    def line():
        return str(finder.status.cget("text"))

    def stations():
        shown = texts_in(finder.table)
        return "".join(LETTER[r["station"]] for r in ROWS if r["station"] in shown)

    check("the extra columns are there: pad, station type, price age and Powerplay",
          all(h in finder._headers for h in ("Pad", "Station type", "Price age", "Powerplay")),
          finder._headers)
    check("as it opens: carriers, Demand 0 and the 600 Ly market (Within 500 Ly) are hidden",
          stations() == "ABEGHIJK" and line().startswith("8 of 11 shown - 3 hidden by your filters")
          and "fleet carriers" in line() and "nobody buying (Demand 0)" in line()
          and "outside your distance window" in line(), (stations(), line()))
    finder.within.suggest.pick("Anywhere")
    pump()
    check("Within is live: Anywhere brings the 600 Ly market back without a new search",
          stations() == "ABEFGHIJK" and line().startswith("9 of 11 shown"), (stations(), line()))
    finder.within.suggest.pick("50 Ly")
    pump()
    check("and 50 Ly takes the far ones away again", stations() == "ABEGJK", (stations(), line()))
    finder.within.suggest.pick("Anywhere")

    def pick(box, value):
        box.suggest.pick(value)
        pump(2)

    pick(filters.far_box, "25 Ly")
    check("From 25 Ly: at least that far away", stations() == "EFHIJ"
          and "5 outside your distance window" in line(), (stations(), line()))
    pick(filters.far_box, "Any")
    pick(filters.pad_box, "L only")
    check("Pad L only", stations() == "AFHK" and "pad too small or unknown" in line(), line())
    pick(filters.pad_box, "Any")
    pick(filters.station_box, "Outposts")
    check("Station type Outposts", stations() == "BGJ" and "other kind of station" in line(), line())
    pick(filters.station_box, "Any")
    pick(filters.age_box, "24 hours")
    check("Price age 24 hours", stations() == "ABFHIJK" and "price too old or undated" in line(), line())
    pick(filters.age_box, "Any age")
    A.set_entry(filters.demand_low, "100")
    A.set_entry(filters.demand_high, "1,000")
    filters.changed()
    pump(2)
    check("Demand 100 to 1,000, typed as people type it", stations() == "AHIJK"
          and "demand outside your window" in line(), (stations(), line()))
    A.set_entry(filters.demand_low, "")
    A.set_entry(filters.demand_high, "")
    A.set_entry(filters.price_box, "250k")
    filters.changed()
    pump(2)
    check("Minimum price 250k", stations() == "AFHI" and "price under your minimum" in line(), line())
    A.set_entry(filters.price_box, "")
    filters.carriers_off.set(False)
    filters.changed()
    pump(2)
    check("No fleet carriers unticked: the carrier shows; Demand 0 still does not",
          "K7Q-1HT" in texts_in(finder.table) and "Delta Works" not in texts_in(finder.table))
    filters.carriers_off.set(True)
    filters.changed()                 # what a click on the box does
    pump(2)
    check("ticked again: the carrier goes", "K7Q-1HT" not in texts_in(finder.table),
          (stations(), line()))
    pick(filters.power_state_box, "Stronghold")
    check("Powerplay state Stronghold", stations() == "A", (stations(), line()))
    pick(filters.power_state_box, "Any")
    pick(filters.power_side_box, "My power")
    check("Side: my power", stations() == "AHJ" and "not that side of Powerplay" in line(), line())
    pick(filters.power_side_box, "Any")
    pick(filters.show_box, "Best five payers per commodity")
    shown = texts_in(finder.table)
    order = [r["station"] for r in sorted(ROWS, key=lambda r: shown.index(r["station"])
                                          if r["station"] in shown else 99) if r["station"] in shown]
    check("Best five payers: Platinum's five, most expensive first, then Osmium",
          order == ["Foxtrot Ring", "India Yard", "Hotel Dock", "Alpha Port", "Bravo Outpost",
                    "Kilo Quay"] and "beyond the best five of their commodity" in line(), (order, line()))
    pick(filters.show_box, "Five nearest per commodity")
    check("Five nearest", stations() == "ABEHJK", (stations(), line()))
    pick(filters.show_box, "All rows")
    check("the Powerplay column says what each system is",
          "Stronghold - %s" % POWER in texts_in(finder.table)
          and "Unoccupied - no Power" in texts_in(finder.table))

    # Saved searches: save, reset, load, and on disk.
    pick(filters.pad_box, "L only")
    pick(filters.far_box, "25 Ly")
    filters.saved.name_box.insert(0, "Big pads far off")
    filters.saved.save()
    pump(2)
    check("Save keeps the filters under the name, and says so",
          "Big pads far off" in app.searches.names("find")
          and 'Saved "Big pads far off"' in filters.saved.message.cget("text"))
    saved = json.load(open(os.path.join(A.DATA_DIR, FD.SEARCHES_FILE), encoding="utf-8"))
    check("in searches.json beside the other records",
          saved["searches"]["Big pads far off"]["state"]["pad"] == "L only"
          and saved["searches"]["Big pads far off"]["state"]["far"] == "25 Ly")
    filters.reset()
    pump(2)
    check("Reset puts every filter back as the window opens, Within 500 Ly included",
          filters.pad_box.get() == "Any" and filters.far_box.get() == "Any"
          and finder.within.get() == A.DEFAULT_DISTANCE
          and filters.carriers_off.get() and stations() == "ABEGHIJK", (filters.pad_box.get(), stations()))
    filters.saved.load("Big pads far off")
    pump(2)
    check("loading it puts them back, and the table with them",
          filters.pad_box.get() == "L only" and stations() == "FH", (filters.pad_box.get(), stations()))
    check("a saved search survives a restart", FD.Favourites(A.DATA_DIR).get("Big pads far off")["pad"]
          == "L only")
    filters.saved.pick_box.set("Big pads far off")
    filters.saved.delete()
    check("and Delete takes it away", "Big pads far off" not in FD.Favourites(A.DATA_DIR).items)
    filters.reset()
    finder.destroy()
    pump()


@on_screen("Where to land and My sites: the body filter bars narrow the rows")
def _bodies_windows():
    land = app.open_land()
    pump(4)
    bar = land._bodies
    check("Where to land lists the three bodies scanned here",
          sorted(r["short"] for r in land._rows) == ["A 1", "A 2", "A 3"], [r["short"] for r in land._rows])
    bar.toggle()
    pump(2)
    A.set_entry(bar.g_high, "1")
    bar.changed()
    pump(2)
    check("Gravity up to 1 g: the 2.5 g body goes, and the line says why",
          sorted(r["short"] for r in land._rows) == ["A 1", "A 3"]
          and "1 hidden" in bar.line.cget("text") and "gravity" in bar.line.cget("text"),
          ([r["short"] for r in land._rows], bar.line.cget("text")))
    A.set_entry(bar.g_high, "")
    A.set_picks(bar.signal_box, ["Mining locations"])
    bar.signal_min_box.set("2")
    bar.changed()
    pump(2)
    check("Mining locations, at least 2: only the body the DSS found three on",
          [r["short"] for r in land._rows] == ["A 1"] and "signals" in bar.line.cget("text"),
          ([r["short"] for r in land._rows], bar.line.cget("text")))
    A.set_picks(bar.signal_box, [])
    A.set_picks(bar.type_box, ["Icy"])
    bar.changed()
    pump(2)
    check("Type Icy", [r["short"] for r in land._rows] == ["A 3"])
    A.set_picks(bar.type_box, [])
    A.set_picks(bar.volc_box, ["Silicate magma"])
    bar.changed()
    pump(2)
    check("Volcanism Silicate magma", [r["short"] for r in land._rows] == ["A 2"])
    A.set_picks(bar.volc_box, [])
    bar.changed()
    # Further than this system: what the journals remember.
    book = app.bodybook
    book.put("Far Rock", "Far Rock 1", {"planet_class": SV.HMC, "gravity": 3.0, "landable": True,
                                        "temperature_k": 200.0, "volcanism": "None",
                                        "distance_ls": 40.0},
             signals=[{"type": "Planetary Mining Location", "count": 2}], mapped=True)
    book.set_position("Far Rock", (0.0, 0.0, 20.0))
    book.put("Remote Rock", "Remote Rock 1", {"planet_class": SV.ICY, "gravity": 1.0,
                                              "landable": True, "distance_ls": 10.0})
    book.set_position("Remote Rock", (900.0, 0.0, 0.0))
    bar.scope_box.suggest.pick("Anywhere remembered")
    pump(3)
    far = [r["body"] for r in land._far_rows]
    check("Anywhere remembered: a table of remembered bodies, nearest first, with its own columns",
          "Far Rock 1" in far and "Remote Rock 1" in far and far.index("Far Rock 1") < far.index("Remote Rock 1")
          and all(h in texts_in(land.table) for h in ("System", "Volcanism", "Signals")), far)
    bar.scope_box.suggest.pick("Near here (remembered)")
    bar.within_box.suggest.pick("25 Ly")
    pump(3)
    far = [r["body"] for r in land._far_rows]
    check("Near here, within 25 Ly: the system 900 Ly off is not listed",
          "Far Rock 1" in far and "Remote Rock 1" not in far, far)
    A.set_picks(bar.type_box, ["Icy"])
    bar.changed()
    pump(2)
    check("and the body filters work on remembered bodies too",
          "Far Rock 1" not in [r["body"] for r in land._far_rows])
    A.set_picks(bar.type_box, [])
    bar.scope_box.suggest.pick("This system")
    A.set_entry(bar.g_high, "1")
    bar.changed()
    bar.saved.name_box.insert(0, "Low g")
    bar.saved.save()
    check("Where to land saves its own searches", "Low g" in FD.Favourites(A.DATA_DIR).names("land")
          and "Low g" not in FD.Favourites(A.DATA_DIR).names("find"))
    bar.reset()
    pump(2)
    check("and Reset clears its filters", sorted(r["short"] for r in land._rows) == ["A 1", "A 2", "A 3"])
    land.destroy()
    pump()

    for body_name, commodity in (("Kaine Hold A 1", "Platinum"), ("Kaine Hold A 2", "Osmium")):
        app.store.add_deposit(system="Kaine Hold", body=body_name, location="1", commodity=commodity,
                              rigs="3", amount="High", lat=1.0, lon=2.0)
    sites = app.open_sites()
    pump(4)
    sbar = sites._bodies
    check("My sites lists both sites with no body filter on",
          sorted(s["body"] for s in sites._rows) == ["Kaine Hold A 1", "Kaine Hold A 2"],
          [s["body"] for s in sites._rows])
    sbar.toggle()
    A.set_entry(sbar.g_high, "1")
    sbar.changed()
    pump(2)
    check("Gravity up to 1 g: the site on the 2.5 g body is hidden, and the line says so",
          [s["body"] for s in sites._rows] == ["Kaine Hold A 1"]
          and "1 hidden" in sbar.line.cget("text"), ([s["body"] for s in sites._rows], sbar.line.cget("text")))
    A.set_entry(sbar.g_high, "")
    A.set_picks(sbar.signal_box, ["Geological"])
    sbar.changed()
    pump(2)
    check("Signals Geological: only the site on the body that has one",
          [s["body"] for s in sites._rows] == ["Kaine Hold A 2"])
    sbar.reset()
    pump(2)
    check("Reset shows both again", len(sites._rows) == 2)
    sites.destroy()
    pump()


@on_screen("Powerplay: the window opens from its button and lists where it counts")
def _powerplay_window():
    button = find_button(app, "Powerplay")
    check("there is a Powerplay button on the main window", button is not None)
    button.invoke()
    pump(4)
    win = app.power_window
    check("pressing it opens the Powerplay window", win is not None and win.winfo_exists()
          and win.title() == "EDSMT - Powerplay")
    check("it says the pledge, from the journal",
          "Pledged to %s" % POWER in win.pledge.cget("text"), win.pledge.cget("text"))
    rows = {r[0][0]: r[4][0] for r in win.count_grid.rows}
    check("every system in the record is listed with what selling there would do",
          len(rows) == len(SYSTEMS) and rows["Kaine Hold"] == "Reinforce"
          and rows["Open Near"] == "Expand" and rows["Open Edge"] == "Expand"
          and rows["Open Far"] == "Nothing" and rows["Torval Near"] == "Nothing", rows)
    check("and drawn on the table", "Expand" in texts_in(win.count_grid.table)
          and "Reinforce" in texts_in(win.count_grid.table))
    check("it says where the goods were mined, from the record",
          win.hold_line.cget("text").startswith("Mined in Kaine Hold."), win.hold_line.cget("text"))
    check("and warns about the bought Gold", "was bought" in win.warning.cget("text"),
          win.warning.cget("text"))
    check("no merit estimate before the rate is learnt",
          "Estimated merits appear" in win.headline.cget("text")
          and "about" not in win.headline.cget("text"), win.headline.cget("text"))
    win.only_counts.set(True)
    win.repaint()
    pump(2)
    check("Only where it counts", sorted(r[0][0] for r in win.count_grid.rows)
          == ["Kaine Hold", "Open Edge", "Open Near"])
    win.only_counts.set(False)
    A.set_entry(win.mined_box, "Torval Near")
    win.repaint()
    pump(2)
    rows = {r[0][0]: r[4][0] for r in win.count_grid.rows}
    check("goods said to be mined in Torval Near undermine there", rows["Torval Near"] == "Undermine", rows)
    A.set_entry(win.mined_box, "")
    win.repaint()

    # The sell side: prices the app already has, best five and nearest five.
    app.sell_quotes = {"platinum": {"commodity": "Platinum", "at": time.time(), "rows": [
        price("Hold Port", "Kaine Hold", 210000, 500, 0.0, "L", "Coriolis", stamp(600)),
        price("Near Port", "Open Near", 260000, 300, 24.0, "L", "Coriolis", stamp(600)),
        price("Far Port", "Open Far", 300000, 100, 40.0, "L", "Coriolis", stamp(600)),
        price("Dead Port", "Torval Near", 400000, 0, 12.0, "L", "Coriolis", stamp(600)),
        price("Rich Port", "Kaine Fort", 280000, 50, 100.0, "L", "Ocellus", stamp(600)),
        price("Mid Port", "Kaine Mine", 230000, 80, 50.0, "M", "Outpost", stamp(600)),
        price("Low Port", "Open Fort", 150000, 999, 101.0, "L", "Coriolis", stamp(600))]}}
    SELL_COLUMN_SELL = A.SELL_HEADERS.index("Sell")
    win.show_page(1)
    pump(3)
    listed = [r[2][0] for r in win.sell_grid.ordered()]
    check("Where to sell, best price: the five best payers, most expensive first",
          listed[:5] == ["Far Port", "Rich Port", "Near Port", "Mid Port", "Hold Port"], listed)
    check("and the commodity with no price known is a line below them, not among them",
          len(listed) == 6 and listed[5].startswith("no price known"), listed)
    win.sell_grid.sort_by(SELL_COLUMN_SELL)
    listed = [r[2][0] for r in win.sell_grid.ordered()]
    check("sorted by a column, the prices move and that line stays last",
          listed[0] == "Hold Port" and listed[5].startswith("no price known"), listed)
    win.sell_grid.sort_by(SELL_COLUMN_SELL)
    listed = [r[2][0] for r in win.sell_grid.ordered()]
    check("and turned round, still last", listed[0] == "Far Port"
          and listed[5].startswith("no price known"), listed)
    check("Demand 0 is never listed", "Dead Port" not in listed)
    goals = {r[2][0]: r[10][0] for r in win.sell_grid.rows}
    check("each says what selling there does for goods mined in Kaine Hold",
          goals["Near Port"] == "Expand" and goals["Hold Port"] == "Reinforce"
          and goals["Far Port"] == "Nothing", goals)
    win.order_box.suggest.pick("Nearest")
    pump(3)
    listed = [r[2][0] for r in win.sell_grid.ordered()]
    check("Nearest: the five nearest buyers, nearest first, the unpriced line last",
          listed[:5] == ["Hold Port", "Near Port", "Far Port", "Mid Port", "Rich Port"]
          and listed[5].startswith("no price known"), listed)
    check("the Gold aboard, priced nowhere, says so",
          any(r[0][0] == "Gold" and "no price known" in r[2][0] for r in win.sell_grid.rows))

    # Merits, once the rate is learnt - and never the rate itself.
    rate = learnt_rate()
    app.merits.pairs = list(rate.pairs)
    win.show_page(0)
    pump(3)
    headline = win.headline.cget("text")
    check("with the rate learnt the window gives the hold's merit estimate",
          headline.startswith("Reinforce in Kaine Hold: about ") and "merits" in headline, headline)
    shown = " ".join(texts_in(win))
    figure = app.merits.per_credit()
    check("and nowhere in the window is the rate or how it is reached",
          "per credit" not in shown.lower() and ("%g" % figure) not in shown
          and ("%.6f" % figure) not in shown and " Cr = " not in shown, shown[:300])
    check("the window's code never asks for the rate itself",
          "per_credit" not in inspect.getsource(A.PowerplayWindow))
    win.range_on.set(False)
    win.range_changed()
    app.follow_power(now=time.time() + 7200)
    check("the Undermine range switch is saved with the record",
          PW.PowerBook(A.DATA_DIR).range_rule is False)
    win.range_on.set(True)
    win.range_changed()
    again = app.open_powerplay()
    check("asking again brings the same window to the front", again is win)
    win.destroy()
    pump()


if __name__ == "__main__":
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    sys.exit(1 if fails else 0)
