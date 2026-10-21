"""What 1.10035 fixes, each piece held down so it stays fixed.

Driven without a display, like the other suites. Every commander, station
and system here is made up; the numbers are the shape of a real report.

    python tests/test_110035.py
"""
import os, sys, json, re, time, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "stubs"))
import _ctkstub  # noqa
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="edsmt-110035-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
import edsmt as A, survey as SV, journal as JN, edonline as EDO  # noqa
import tkinter as tk, customtkinter as ctk  # noqa  (the stubs)

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)


SRC = open(A.__file__, encoding="utf-8").read()
NOW = time.time()
def stamp(ago_s):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(NOW - ago_s))

MINE = "Col 1 Sector AA-A c1-1"        # the system being mined, with a station
PORT = "Merit Port"
CARRIER, CARRIER_SYS = "QQQ-111", "Hadar Sector XX-Y d1-2"
HOOK = "https://discord.com/api/webhooks/123456789012345678/" + "b" * 68


def write_json(folder, name, data):
    with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
        json.dump(data, fh)


def journal(folder, events, name="Journal.2026-10-13T020859.01.log"):
    with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")


def market(system, station, when, items):
    return {"timestamp": when, "event": "Market", "MarketID": abs(hash(station)) % 10**9,
            "StationName": station, "StationType": "Coriolis", "StarSystem": system,
            "Items": [dict({"id": 1, "Category": "$MARKET_category_metals;",
                            "BuyPrice": 0, "Stock": 0, "StockBracket": 0,
                            "DemandBracket": 3, "Consumer": True}, **item)
                      for item in items]}


def iridium(sell, demand, mean=129763):
    return {"Name": "$iridium_name;", "Name_Localised": "Iridium",
            "SellPrice": sell, "Demand": demand, "MeanPrice": mean}


# ---------------------------------------------------------------------------
print("== 1. docked, the hold is priced at the station docked at ==")
GAME = os.path.join(TMP, "game")
os.makedirs(GAME)
# The carrier left this morning: its board was the last Market.json, and it
# buys no Iridium (listed at 0 - the galactic average is still on it).
write_json(GAME, "Market.json", market(CARRIER_SYS, CARRIER, stamp(5 * 3600), [
    iridium(0, 0), {"Name": "$tritium_name;", "Name_Localised": "Tritium",
                    "SellPrice": 51000, "Demand": 900, "MeanPrice": 48000}]))
journal(GAME, [
    {"timestamp": stamp(6 * 3600), "event": "Fileheader", "part": 1},
    {"timestamp": stamp(6 * 3600), "event": "Commander", "FID": "F1", "Name": "Jameson"},
    {"timestamp": stamp(6 * 3600), "event": "Location", "Docked": True,
     "StationName": CARRIER, "StarSystem": CARRIER_SYS, "StarPos": [0, 0, 0]},
    {"timestamp": stamp(5 * 3600), "event": "Undocked", "StationName": CARRIER},
    {"timestamp": stamp(4 * 3600), "event": "FSDJump", "StarSystem": MINE,
     "StarPos": [1, 2, 3], "SystemAddress": 42},
    {"timestamp": stamp(300), "event": "Docked", "StationName": PORT,
     "StarSystem": MINE, "MarketID": 7},
])
app = A.EDSMT.__new__(A.EDSMT)
app.watcher = JN.JournalWatcher(GAME)
for _ in range(3):
    app.watcher.poll()
app.watcher.holds = {"Ship": {"Iridium": 66, "Tea": 5}, "SRV": {"Iridium": 23}}
app.watcher.cargo = {"Iridium": 23}
app.market_book = SV.MarketBook(os.path.join(TMP, "data"))
app.merits = SV.MeritRate(os.path.join(TMP, "data"))
app.earnings = SV.Earnings(os.path.join(TMP, "data"))
# The books say only 33 t are mined and unsold - an earlier session's tonnes
# went in under a session the books never saw. The hold has 89.
_dug = app.earnings.start(MINE, MINE + " BC 2", "Jameson", when=stamp(3 * 3600))
_dug.update({"mined": "Iridium:33", "ended": stamp(600), "closed": stamp(600)})
app.earnings.save()
check("the reader has us docked at the station, not the carrier",
      app.watcher.docked and app.watcher.station == PORT and app.watcher.system == MINE,
      (app.watcher.docked, app.watcher.station, app.watcher.system))
check("the books alone would say 33 t (what 1.10034 priced)",
      app.mined_aboard() == {"Iridium": 33}, app.mined_aboard())
check("Aboard is the hold as it is: SRV 23 + ship 66 = 89 t, no Tea",
      app.aboard_for_sale() == {"Iridium": 89}, app.aboard_for_sale())
check("the carrier's board is not this station's: nothing priced here yet",
      app.market_prices() == {} and app.market_here()[1] == PORT, app.market_here())
ew = A.EarningsWindow.__new__(A.EarningsWindow)
ew.app = app
said = []
ew.say = lambda text, colour=None: said.append(text)
holding = ew._holding()
check("the hold line names both holds, 89 t between them",
      "SRV 23t - Iridium 23" in holding and "ship 66t - Iridium 66" in holding, holding)
check("and says the board here has not been read - not 'no prices seen'",
      "Merit Port's board has not been read yet" in holding, holding)

# He opens the commodity screen: the game writes this station's board.
write_json(GAME, "Market.json", market(MINE, PORT, stamp(120), [
    iridium(194540, 19034),
    {"Name": "$platinum_name;", "Name_Localised": "Platinum", "SellPrice": 62349,
     "Demand": 0, "MeanPrice": 55505}]))
app.watcher.poll()
app.book_market()
check("his own read of the board prices the hold at once",
      SV.fold("Iridium") in {SV.fold(k) for k in app.market_prices()}
      and app.market_prices().get("Iridium") == 194540, app.market_prices())
holding = ew._holding()
check("and the hold line says what 89 t fetch here, and how old the read is",
      "Worth 17,314,060 Cr at Merit Port, by your read 2 min ago." in holding, holding)
check("the read is kept, by station, on disk",
      os.path.exists(os.path.join(TMP, "data", SV.MARKET_BOOK_FILE))
      and SV.MarketBook(os.path.join(TMP, "data")).prices_at(MINE, PORT).get("Iridium") == 194540)

# ---------------------------------------------------------------------------
print("== 1b. on the surface, not docked - the moment of the real report ==")
# His journal puts the screenshot at about 03:02 on 13 October: in the SRV on
# the body, 23 t in it and 66 t in the ship. The last Market.json was a fleet
# carrier's, two systems away, read at 01:26 - and it buys no Iridium. His
# own reads of the station in this system were days old, and 1.10034 had
# thrown them away: it kept only the last Market.json.
FIELD = os.path.join(TMP, "field")
os.makedirs(FIELD)
write_json(FIELD, "Market.json", market(CARRIER_SYS, CARRIER, stamp(95 * 60), [
    {"Name": "$tritium_name;", "Name_Localised": "Tritium", "SellPrice": 51000,
     "Demand": 900, "MeanPrice": 48000}]))
journal(FIELD, [
    {"timestamp": stamp(3 * 3600), "event": "Commander", "FID": "F1", "Name": "Jameson"},
    {"timestamp": stamp(3 * 3600), "event": "Location", "Docked": True,
     "StationName": CARRIER, "StarSystem": CARRIER_SYS, "StarPos": [0, 0, 0]},
    {"timestamp": stamp(2 * 3600), "event": "Undocked", "StationName": CARRIER},
    {"timestamp": stamp(90 * 60), "event": "FSDJump", "StarSystem": MINE,
     "StarPos": [1, 2, 3], "SystemAddress": 42}])
out = A.EDSMT.__new__(A.EDSMT)
out.watcher = JN.JournalWatcher(FIELD)
for _ in range(3):
    out.watcher.poll()
out.watcher.holds = {"Ship": {"Iridium": 66}, "SRV": {"Iridium": 23}}
out.watcher.cargo = {"Iridium": 23}
out.market_book = SV.MarketBook(os.path.join(TMP, "fieldbook"))
out.merits = SV.MeritRate()
out.earnings = SV.Earnings(os.path.join(TMP, "fieldbooks"))
ow = A.EarningsWindow.__new__(A.EarningsWindow)
ow.app = out
check("undocked, in the system being mined; the last market is the carrier",
      not out.watcher.docked and out.watcher.system == MINE
      and (out.watcher.market or {}).get("station") == CARRIER,
      (out.watcher.docked, out.watcher.system, (out.watcher.market or {}).get("station")))
line = ow._holding()
check("with no read of his own here, it says the carrier buys none of it",
      "%s, the last market you read, buys none of it" % CARRIER in line, line)
check("never 'No market prices seen yet' over a sell table that has some",
      "No market prices seen yet" not in line, line)
# Two reads of his own in this system, kept by station: the one that pays
# more for what is aboard prices it, and says how old it is.
out.market_book.note_market({"system": MINE, "station": PORT, "when": stamp(3 * 86400 + 600),
                             "items": [{"commodity": "Iridium", "sell": 306005,
                                        "demand": 4000}]})
out.market_book.note_market({"system": MINE, "station": "Small Outpost", "when": stamp(86400 + 60),
                             "items": [{"commodity": "Iridium", "sell": 150000,
                                        "demand": 300}]})
check("undocked, his own read in this system that pays most is the one",
      out.market_here(out.aboard_for_sale())[1] == PORT,
      out.market_here(out.aboard_for_sale())[1:])
line = ow._holding()
check("and the hold line prices 89 t there, three days old and said to be stale",
      "Worth 27,234,445 Cr at %s, by your read 3 days ago (" % PORT in line
      and line.endswith(") - stale."), line)
check("a read elsewhere is never taken for this system's",
      out.market_book.best_in(CARRIER_SYS, {"Iridium": 89}) is None)

# ---------------------------------------------------------------------------
print("== 6. price rules: own read first, ages, stale, Demand 0, outliers ==")
app.quote_asked = {"system": MINE, "radius": 100, "at": NOW}
ANSWER = {"commodity": "Iridium", "market": [
    {"station": "Far Away Hub", "system": "Distant Sector", "sell": 579307,
     "demand": 4000, "distance_ly": 88.1, "seen": stamp(4 * 86400),
     "source": "Some-Provider-Index"},
    {"station": PORT, "system": MINE, "sell": 315689, "demand": 2000,
     "seen": stamp(4 * 86400), "source": "Some-Provider-Index"},
    {"station": "Mid Station", "system": "Next Door", "sell": 320000, "demand": 300,
     "distance_ly": 40.0, "seen": stamp(5 * 86400), "source": "Some-Provider-Index"},
    {"station": "Dead Dock", "system": "Close By", "sell": 900000, "demand": 0,
     "distance_ly": 30.0, "seen": stamp(3600), "source": "Some-Provider-Index"}],
    "community": []}
app.take_quote(True, json.dumps(ANSWER))
judged = app.price_rows_for("Iridium")
pick = A.pick_prices(judged, MINE)
check("Demand 0 is not a market, however fresh and however high",
      all(r["sell"] != 900000 for r in judged), [r["sell"] for r in judged])
check("in this system, his own fresh read - not the four-day-old upstream figure",
      pick["here"] and pick["here"]["sell"] == 194540
      and pick["here"]["source"] == "your market read" and not pick["here"]["stale"],
      pick["here"])
check("one station priced twice keeps his own read",
      not any(r["sell"] == 315689 for r in judged), [r["sell"] for r in judged])
check("best within range is the best FRESH price",
      pick["best"]["sell"] == 194540, pick["best"])
check("the higher price is four days old, and only mentioned",
      pick["higher_stale"] and pick["higher_stale"]["sell"] == 579307
      and pick["higher_stale"]["stale"], pick["higher_stale"])
check("a lone price far above every other is flagged",
      pick["higher_stale"]["outlier"] is True)
check("the estimate uses the credible one",
      app.best_price("Iridium")[0] == 194540 and app.best_price("Iridium")[2] == "fresh",
      app.best_price("Iridium"))
check("no row anywhere carries a provider's own name",
      {r["source"] for r in judged} <= {"your market read", "community", "market data"},
      {r["source"] for r in judged})
check("ages read the way people say them",
      A.price_age(stamp(600), NOW)[0] == "10 min ago"
      and A.price_age(stamp(5 * 3600), NOW)[0] == "5 h ago"
      and A.price_age(stamp(4 * 86400 + 60), NOW)[0].startswith("4 days ago (")
      and A.price_age("", NOW) == ("age unknown", None))
_same = A.judge_prices([
    {"station": PORT, "system": MINE, "sell": 194540, "demand": 19034,
     "seen": stamp(3 * 3600), "source": SV.OWN_SOURCE},
    {"station": PORT, "system": MINE, "sell": 201000, "demand": 19000,
     "seen": stamp(3600), "source": "community"},
    {"station": PORT, "system": MINE, "sell": 210000, "demand": 19000,
     "seen": stamp(1800), "source": "Some-Provider-Index"}], now=NOW)
check("one station, three fresh prices: his own read wins, even over newer ones",
      len(_same) == 1 and _same[0]["sell"] == 194540
      and _same[0]["source"] == "your market read", _same)
_theirs = A.judge_prices([
    {"station": PORT, "system": MINE, "sell": 201000, "demand": 19000,
     "seen": stamp(3600), "source": "community"},
    {"station": PORT, "system": MINE, "sell": 210000, "demand": 19000,
     "seen": stamp(1800), "source": "Some-Provider-Index"}], now=NOW)
check("without his, community before market data",
      len(_theirs) == 1 and _theirs[0]["source"] == "community", _theirs)
only_stale = A.pick_prices(A.judge_prices([dict(r) for r in ANSWER["market"]], now=NOW), MINE)
check("with nothing fresh, this system's price is shown stale - never as now",
      only_stale["here"]["sell"] == 315689 and only_stale["here"]["stale"]
      and only_stale["credible"] is None, only_stale["here"])
check("and the four-day-old 579,307 that is best is flagged both ways - old and alone",
      only_stale["best"]["sell"] == 579307
      and A.price_note(only_stale["best"]) == " - stale, unconfirmed"
      and only_stale["stale_pick"]["sell"] == 320000, (only_stale["best"], only_stale["stale_pick"]))

ew.quote_table = tk.Frame()
ew.sell_title = ctk.CTkLabel()
ew._radius = lambda: 100
ew.show_quotes()
cells = [w.cget("text") for w in ew.quote_table.winfo_children()]
check("Where to sell: Aboard is 89t", "89t" in cells, cells)
check("In this system is his read, and says how old it is",
      "194,540 - 2 min ago" in cells, cells)
check("Best within is the fresh price, Worth there = 89 x it",
      "17,314,060 Cr" in cells, cells)
check("Price seen says how old, and whose",
      any(c == "2 min ago - your market read" for c in cells), cells)
check("the stale higher price is mentioned, and said not to be used",
      any("579,307" in c and "older than a day, so not used" in c for c in cells), cells)
check("nothing shown names an upstream provider",
      not any("provider" in str(c).lower() for c in cells), cells)

# ---------------------------------------------------------------------------
print("== 5. the current session leads; merits learnt from his own sales ==")
SALES = os.path.join(TMP, "sales")
os.makedirs(SALES)
journal(SALES, [
    {"timestamp": "2026-10-08T15:11:04Z", "event": "PowerplayMerits", "Power": "A Power",
     "MeritsGained": 40, "TotalMerits": 1040},
    {"timestamp": "2026-10-08T16:47:55Z", "event": "MarketSell", "MarketID": 1,
     "Type": "superconductors", "Count": 1298, "SellPrice": 6941,
     "TotalSale": 9009418, "AvgPricePaid": 6755},
    {"timestamp": "2026-10-08T23:51:09Z", "event": "MarketSell", "MarketID": 2,
     "Type": "iridium", "Count": 1000, "SellPrice": 300000, "TotalSale": 300000000,
     "AvgPricePaid": 0},
    {"timestamp": "2026-10-08T23:51:22Z", "event": "PowerplayMerits", "Power": "A Power",
     "MeritsGained": 150000, "TotalMerits": 151040}],
    name="Journal.2026-10-08T134143.01.log")
rate = SV.MeritRate(os.path.join(TMP, "merits"))
check("one sale and its merits are paired; the rest is not",
      rate.learn_folder(SALES) == 1 and rate.pairs[0]["credits"] == 300000000
      and rate.pairs[0]["merits"] == 150000, rate.pairs)
check("one pair is not enough to estimate with", rate.per_credit() is None)
journal(SALES, [
    {"timestamp": "2026-10-13T05:33:10Z", "event": "MarketSell", "MarketID": 2,
     "Type": "iridium", "Count": 500, "SellPrice": 200000, "TotalSale": 100000000,
     "AvgPricePaid": 0},
    {"timestamp": "2026-10-13T05:33:15Z", "event": "PowerplayMerits", "Power": "A Power",
     "MeritsGained": 50000, "TotalMerits": 201040}],
    name="Journal.2026-10-13T020859.01.log")
check("the next journal adds the second, and files already read are not re-read",
      rate.learn_folder(SALES) == 1 and len(rate.pairs) == 2, rate.pairs)
per = rate.per_credit()
check("merits per credit of sale learnt from the two sales (a made-up rate)",
      per is not None and abs(1 / per - 2000.0) < 1e-6, per)
check("and it is remembered", SV.MeritRate(os.path.join(TMP, "merits")).per_credit() == per)
check("the ratio is kept per commodity, in the file as well",
      set(rate.rates()) == {"Iridium"} and rate.rates()["Iridium"]["pairs"] == 2
      and json.load(open(os.path.join(TMP, "merits", SV.MERITS_FILE)))["rates"]["Iridium"]["pairs"] == 2,
      rate.rates())

# Each commodity at its own rate, once it has its own two sales. One that
# pays merits at a different rate is not averaged into Iridium's.
mixed = SV.MeritRate()
for when, kind, total, gained in (("2026-10-09T10:00:00Z", "iridium", 100000000, 50000),
                                  ("2026-10-10T10:00:00Z", "iridium", 200000000, 100000),
                                  ("2026-10-11T10:00:00Z", "platinum", 10000000, 10000),
                                  ("2026-10-12T10:00:00Z", "platinum", 20000000, 20000)):
    mixed.observe(SV.merit_note({"timestamp": when, "event": "MarketSell", "Type": kind,
                                 "Count": 100, "SellPrice": total // 100, "TotalSale": total,
                                 "AvgPricePaid": 0}))
    mixed.observe(SV.merit_note({"timestamp": when[:-3] + "09Z", "event": "PowerplayMerits",
                                 "Power": "A Power", "MeritsGained": gained}))
check("Platinum at its own rate", abs(mixed.per_credit("Platinum") - 1e-3) < 1e-9,
      mixed.per_credit("Platinum"))
check("Iridium at its own", abs(mixed.per_credit("Iridium") - 5e-4) < 1e-9,
      mixed.per_credit("Iridium"))
check("a commodity not yet paired takes the rate over every sale",
      mixed.per_credit("Gold") == mixed.per_credit(), (mixed.per_credit("Gold"), mixed.per_credit()))
# Support missions pay merits too, and some merits lines pay nothing at all.
# Neither may be taken as what a sale earned.
def _ev(when, name, **kw):
    kw.update({"timestamp": when, "event": name})
    return SV.merit_note(kw)
side = SV.MeritRate()
side.observe(_ev("2026-10-12T10:00:00Z", "MarketSell", Type="iridium", Count=100,
                 SellPrice=200000, TotalSale=20000000, AvgPricePaid=0))
side.observe(_ev("2026-10-12T10:00:20Z", "MissionCompleted", Name="Mission_Delivery_name"))
check("merits paid for a support mission handed in after the sale are not the sale's",
      side.observe(_ev("2026-10-12T10:00:25Z", "PowerplayMerits", MeritsGained=400,
                       TotalMerits=1400)) is False and side.pairs == [], side.pairs)
check("and the sale's own merits that follow are still paired with it",
      side.observe(_ev("2026-10-12T10:00:31Z", "PowerplayMerits", MeritsGained=10000,
                       TotalMerits=11400)) is True and side.pairs[0]["merits"] == 10000, side.pairs)
side.observe(_ev("2026-10-12T11:00:00Z", "MarketSell", Type="iridium", Count=100,
                 SellPrice=200000, TotalSale=20000000, AvgPricePaid=0))
check("a merits line that leaves the total where it was is not a payment",
      side.observe(_ev("2026-10-12T11:00:08Z", "PowerplayMerits", MeritsGained=10000,
                       TotalMerits=11400)) is False and len(side.pairs) == 1, side.pairs)
bought = SV.MeritRate()
bought.observe(_ev("2026-10-12T12:00:00Z", "MarketSell", Type="gold", Count=700,
                   SellPrice=60000, TotalSale=42000000, AvgPricePaid=50000))
check("a load of bought goods is never paired with merits that arrive after it",
      bought.observe(_ev("2026-10-12T12:00:09Z", "PowerplayMerits", MeritsGained=300,
                         TotalMerits=5000)) is False and bought.pairs == [], bought.pairs)
_lines = [{"commodity": "Iridium", "worth": 10000000}, {"commodity": "Platinum", "worth": 1000000}]
check("a session's merits add each commodity at its own rate, sold and unsold",
      abs(A.session_merits(mixed, _lines, {"iridium": 50, "platinum": 50}, 2000000)
          - (5000 + 1000 + 1000000 * 5e-4 + 1000000 * 1e-3)) < 1e-6,
      A.session_merits(mixed, _lines, {"iridium": 50, "platinum": 50}, 2000000))
check("and nothing until a rate is learnt", A.session_merits(SV.MeritRate(), _lines, {}, 0) is None)
_unpledged = SV.MeritRate()
for _n in range(500):
    _unpledged.observe({"event": "MarketSell", "when": stamp(86400 - _n * 120),
                        "commodity": "Superconductors", "count": 1298,
                        "total": 85031980, "avg_paid": 0})
check("an evening of sales that pay no merits is not hoarded waiting for them",
      len(_unpledged._pending) == 1 and _unpledged.pairs == [], len(_unpledged._pending))

# The live path: the reader hands PowerplayMerits on with what was gained,
# and the app keeps it away from the books.
LIVE = os.path.join(TMP, "live")
os.makedirs(LIVE)
journal(LIVE, [
    {"timestamp": stamp(60), "event": "Commander", "FID": "F1", "Name": "Jameson"},
    {"timestamp": stamp(60), "event": "Location", "Docked": True, "StationName": PORT,
     "StarSystem": MINE, "StarPos": [1, 2, 3]},
    {"timestamp": stamp(30), "event": "MarketSell", "MarketID": 7, "Type": "iridium",
     "Count": 10, "SellPrice": 200000, "TotalSale": 2000000, "AvgPricePaid": 0},
    {"timestamp": stamp(25), "event": "PowerplayMerits", "Power": "A Power",
     "MeritsGained": 860, "TotalMerits": 9999}])
reader = JN.JournalWatcher(LIVE)
reader.poll()
notes = reader.drain_runs()
merit_notes = [n for n in notes if n.get("event") == "PowerplayMerits"]
check("the reader passes PowerplayMerits on, with MeritsGained",
      merit_notes and merit_notes[0]["merits"] == 860, notes)
live = A.EDSMT.__new__(A.EDSMT)
live.market_book = SV.MarketBook(os.path.join(TMP, "livebook"))
live.merits = SV.MeritRate(os.path.join(TMP, "livemerits"))
taken = [live.note_prices(n) for n in notes]
check("the merits note is the app's alone - the books never see it",
      [n["event"] for n, t in zip(notes, taken) if t] == ["PowerplayMerits"], taken)
check("the sale is a price at that station, in his own book",
      live.market_book.prices_at(MINE, PORT).get("Iridium") == 200000,
      live.market_book.stations)
check("and the sale and its merits are a pair", len(live.merits.pairs) == 1,
      live.merits.pairs)

app.merits = rate
started = stamp(2 * 3600)
run = app.earnings.start(MINE, MINE + " BC 2", "Jameson", when=started)
run.update({"mined": "Iridium:120", "ended": stamp(900)})
lines = A.current_session_lines(app, [], now=NOW)
check("the headline is the session in progress, to now",
      lines[0].startswith("CURRENT SESSION   2h 00m   120 t mined   60.0 t/hr   sold so far 0 Cr"),
      lines[0])
check("with what it is worth at the best credible price, and Cr/hr",
      lines[1].startswith("Estimated 23,344,800 Cr   11,672,400 Cr/hr")
      and "best price seen in the last day" in lines[1], lines[1])
_mph = 23344800 * per / 2.0
check("and Powerplay merits an hour from his own rate",
      lines[2] == "Powerplay merits/hr: ~%s (estimated from your own sales)"
      % "{:,}".format(int(round(_mph))), (lines[2], _mph))
app.merits = SV.MeritRate()
check("not learnt yet, merits read as a dash",
      A.current_session_lines(app, [], now=NOW)[2] == "Powerplay merits/hr: —")
check("the window builds the three lines at the top, merits with its note",
      "self.current = ctk.CTkLabel(top" in SRC and "MERITS_TIP)" in SRC
      and SRC.index("self.current = ctk.CTkLabel(top") < SRC.index("self.sell_title"))
check("and the all-time totals go under the table",
      'self.summary.pack(side="bottom"' in SRC
      and SRC.index('self.summary.pack(side="bottom"') < SRC.index(
          "self.scroller = ScrollTable(self)\n        self.scroller.pack(fill=\"both\", expand=True, padx=12, pady=(0, 4))"))

# Left open while he mines, the current session moves by itself - it was
# drawn once, when the window opened, and stood still after that.
class _Said:
    def __init__(self): self.text = None
    def configure(self, **kw): self.text = kw.get("text", self.text)
lw = A.EarningsWindow.__new__(A.EarningsWindow)
lw.app = app
lw.current, lw.current_value, lw.current_merits, lw.holding = _Said(), _Said(), _Said(), _Said()
app.merits = rate
# Opened, or after Refresh: the current session first, then the totals.
lw._rows, lw.summary, lw._session_buttons = [], _Said(), lambda: None
lw._summarise()
check("drawing the window puts the current session at the top, totals as all-time",
      str(lw.current.text).startswith("CURRENT SESSION")
      and str(lw.current_merits.text).startswith("Powerplay merits/hr: ~")
      and str(lw.summary.text).startswith("All time:"),
      (lw.current.text, lw.current_merits.text, lw.summary.text))
lw.current.text = None
lw.live()
check("the window's live redraw fills the current session and the hold",
      str(lw.current.text).startswith("CURRENT SESSION") and "t mined" in lw.current.text
      and str(lw.holding.text).startswith("Mined, in the hold"), (lw.current.text, lw.holding.text))
class _Ledger:
    def __init__(self): self.calls, self.alive = 0, True
    def winfo_exists(self): return self.alive
    def live(self): self.calls += 1
app.ledger, app._ledger_at = _Ledger(), 0.0
_ticks = [app.follow_ledger(now=NOW), app.follow_ledger(now=NOW + 2),
          app.follow_ledger(now=NOW + A.LEDGER_LIVE_S + 0.1)]
check("the app's tick redraws an open window every few seconds, not every tick",
      _ticks == [True, False, True] and app.ledger.calls == 2, (_ticks, app.ledger.calls))
app.ledger.alive = False
check("and lets go of it once it is closed",
      app.follow_ledger(now=NOW + 60) is False and A.attr(app, "ledger") is None)
import inspect
check("the tick calls it", "self.follow_ledger()" in inspect.getsource(A.EDSMT.tick))

# ---------------------------------------------------------------------------
print("== 4. Discord: one summary a session, finds only if asked ==")
check("per-find posts are off by default", A.DEFAULT_SETTINGS["discord_post_finds"] is False)
up = A.upgrade_discord(dict(A.DEFAULT_SETTINGS, discord_post_finds=True),
                       {"discord_post_finds": True})
check("a 1.10034 file that had it on (by default) is turned off, once",
      up["discord_post_finds"] is False and up["discord_finds_level"] == 1, up)
kept = A.upgrade_discord(dict(A.DEFAULT_SETTINGS, discord_post_finds=True),
                         {"discord_post_finds": True, "discord_finds_level": 1})
check("ticked again after that, it stays ticked", kept["discord_post_finds"] is True)

class _Worker:
    def __init__(self): self.jobs = []
    def submit(self, tag, fn): self.jobs.append((tag, fn))
sent = []
_real_post = EDO.post_json
EDO.post_json = lambda url, payload, timeout=20.0, headers=None: sent.append((url, payload)) or {"id": "1"}
d = app
d.worker = _Worker()
d.settings = dict(A.DEFAULT_SETTINGS, discord_webhook=HOOK)
d.watcher.cargo_capacity = 256
d.store = SV.Survey(os.path.join(TMP, "store"))
d.store.deposits = [{"recorded": stamp(5000)}, {"recorded": stamp(4000)},
                    {"recorded": stamp(9 * 3600)}]
check("a find marked is not posted on its own", d.post_discord_find({"commodity": "Iridium"}) is False
      and d.worker.jobs == [])
# Tonnes refined at three marked deposits: two in the session that ends,
# one the night before. The store credits each tonne to the deposit it came
# off; the app remembers when each one last gave a tonne.
_credited = iter(["dep-1", "dep-2", "dep-1", "dep-9"])
d.store.credit_refined = lambda *a, **k: {"id": next(_credited)}
for _ago in (5000, 4800, 4000, 9 * 3600):
    d.credit_refined({"in_srv": True, "lat": 1.0, "lon": 2.0, "radius_m": 1500000.0,
                      "system": MINE, "body": MINE + " BC 2", "commodity": "Iridium",
                      "when": stamp(_ago)})
check("each marked deposit worked is remembered, by the tonne's own time",
      set(d._worked) == {"dep-1", "dep-2", "dep-9"}, d._worked)
d.earnings.sessions = [dict(_dug, id="before")]
d.post_discord_sessions()
ended = dict(_dug, id="s1", started=stamp(6 * 3600), ended=stamp(3600), closed=stamp(3600),
             mined="Iridium:707", rhinos=json.dumps({"105": {"label": "A", "rigs": 3,
                                                             "mined": "Iridium:707"}}))
d.earnings.sessions.append(ended)
check("a session that ends is posted once", d.post_discord_sessions() == 1
      and len(d.worker.jobs) == 1)
check("and never again", d.post_discord_sessions() == 0 and len(d.worker.jobs) == 1)
d.worker.jobs[0][1]()
embed = sent[-1][1]["embeds"][0]
fields = {f["name"]: f["value"] for f in embed["fields"]}
check("titled with the commander", embed["title"] == "CMDR Jameson — Mining Summary",
      embed["title"])
check("where, how long, how much and how fast",
      fields.get("Location") == "%s / %s BC 2" % (MINE, MINE)
      and fields.get("Session") == "5h 00m - 707 t @ 141.4 t/hr", fields)
check("the ship's hold, used and capacity", fields.get("Hold") == "71 / 256 t", fields)
check("each commodity's tonnes, t/hr and estimated worth, and where",
      "Iridium: 707 t (141.4 t/hr) - est. 137,539,780 Cr at %s, %s" % (PORT, MINE)
      in embed["description"], embed["description"])
check("the estimated total, and Cr/hr marked as an estimate",
      fields.get("Est. value") == "137,539,780 Cr (estimated)"
      and fields.get("Cr/hr") == "est. 27,507,956", fields)
check("rigs placed and finds logged", fields.get("Rigs placed") == "3"
      and fields.get("Finds logged") == "2", fields)
check("deposits worked in that session - not the one from the night before",
      fields.get("Deposits worked") == "2", fields)
check("and Powerplay merits an hour, at the rate learnt from his sales",
      str(fields.get("Merits/hr") or "").startswith("est. "), fields)
check("the webhook address is in nothing posted",
      HOOK not in json.dumps(sent[-1][1]) and "123456789012345678" not in json.dumps(sent[-1][1]))
EDO.post_json = _real_post
# And when Discord refuses it, or cannot be reached, what comes back to the
# status line - and from there to any log - names the host, never the hook.
import urllib.error, io
_real_open = EDO.urllib.request.urlopen
_said_back = []
for _fault in (urllib.error.HTTPError(HOOK + "?wait=true", 404, "Not Found", {},
                                      io.BytesIO(b'{"message": "Unknown Webhook"}')),
               urllib.error.URLError("connection refused")):
    def _refuse(*a, _f=_fault, **k):
        raise _f
    EDO.urllib.request.urlopen = _refuse
    _w = EDO.Worker()
    _w.submit(EDO.DISCORD_TAG, lambda: json.dumps(EDO.discord_post(HOOK, embed and sent[-1][1])))
    for _ in range(200):
        _got = _w.drain()
        if _got:
            _said_back += _got
            break
        time.sleep(0.01)
EDO.urllib.request.urlopen = _real_open
check("a refused or failed post says why without the webhook or its token",
      len(_said_back) == 2 and all(not ok for _t, ok, _m in _said_back)
      and not any(HOOK in m or "123456789012345678" in m or "b" * 68 in m
                  for _t, _ok, m in _said_back), _said_back)

# ---------------------------------------------------------------------------
print("== 2. System prices: richest first, no dead rows, neutral sources ==")
ROWS = [
    {"commodity": "Alexandrite", "station": "A Port", "sell": 90000, "demand": 50,
     "seen": stamp(3600), "source": "Some-Provider-Index"},
    {"commodity": "Bromellite", "station": "B Port", "sell": 0, "demand": 50},
    {"commodity": "Grandidierite", "station": "G Port", "sell": 400000, "demand": 0,
     "seen": stamp(3600), "source": "Some-Provider-Index"},
    {"commodity": "Musgravite", "station": "M Port", "sell": 600000, "demand": 12,
     "seen": stamp(600), "source": "community"},
    {"commodity": "Monazite", "station": "Z Port", "sell": 300000, "demand": 3,
     "seen": stamp(3 * 86400), "source": "Some-Provider-Index"},
]
best = A.system_price_rows(ROWS, best_only=True)
check("the most expensive first, not alphabetical",
      [r["commodity"] for r in best] == ["Musgravite", "Monazite", "Alexandrite"], best)
check("Demand 0 is a dead row, not shown", all(r["commodity"] != "Grandidierite" for r in best))
pw = A.EarningsWindow.__new__(A.EarningsWindow)
src_col = A.PRICE_HEADERS.index("Source")
seen_col = A.PRICE_HEADERS.index("Last known")
cells = [pw._price_cells(r) for r in best]
check("Source is your market read / community / market data - never the name sent",
      [c[src_col][0] for c in cells] == ["community", "market data", "market data"],
      [c[src_col] for c in cells])
check("older than a day says stale", cells[1][seen_col][0].endswith(" - stale")
      and not cells[0][seen_col][0].endswith(" - stale"), [c[seen_col] for c in cells])
check("Find's sell table uses the same words",
      "(price_source(row.get(\"source\")), DIM)]" in SRC)

# ---------------------------------------------------------------------------
print("== 3. the commodity picker ticks with a tick ==")
class _List:
    def __init__(self): self.rows, self.colours = [], {}
    def insert(self, where, text): self.rows.append(text)
    def itemconfig(self, index, **kw):
        self.colours[len(self.rows) - 1 if index == "end" else index] = kw
    def __getattr__(self, name): return lambda *a, **k: 0
class _Any:
    def __getattr__(self, name): return lambda *a, **k: 0
sg = A.Suggest.__new__(A.Suggest)
sg.multi, sg.none, sg.popup, sg.box, sg.listbox = True, "Any", _Any(), _Any(), _List()
sg._alive = lambda: True
sg.choices = lambda: ["Any", "Alexandrite", "Benitoite", "Monazite"]
sg.picked = lambda: ["Monazite"]
sg.fragment = lambda: ""
sg.text = lambda: "Monazite"
sg.show()
check("a ticked row has a tick", sg.listbox.rows[3] == " ✓ Monazite", sg.listbox.rows)
check("an unticked row has no empty box", sg.listbox.rows[1] == "    Alexandrite"
      and not any("[" in r for r in sg.listbox.rows), sg.listbox.rows)
check("and the ticked row is coloured: green on the theme's own background",
      sg.listbox.colours == {3: {"fg": A.GREEN, "bg": A.SWEPT}}, sg.listbox.colours)
check("the Any row still clears", sg.listbox.rows[0] == " Any - clear")

# ---------------------------------------------------------------------------
print("== the server never sends a provider's name ==")
PRIV = os.path.join(os.path.dirname(os.path.dirname(HERE)), "EDSMT-Private", "server", "main.py")
if os.path.exists(PRIV):
    server = open(PRIV, encoding="utf-8").read()
    check("every upstream row goes out as market data",
          '"source": SELL_UPSTREAM_NAME' not in server
          and server.count("source=SELL_SOURCE_LABEL") == 2)
else:
    print("  (the private server is not beside this checkout - nothing to check)")

print()
print("FAILURES: %d" % len(fails))
for f in fails:
    print("  - " + f)
sys.exit(1 if fails else 0)
