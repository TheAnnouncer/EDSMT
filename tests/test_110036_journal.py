"""1.10036: the journal-check fixes and the pre-sale line, each with a check.

Every commander, station and figure here is made up.

    python tests/test_110036_journal.py
"""
import os, sys, json, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-jfix-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import journal as JN      # noqa: E402
import survey as SV       # noqa: E402
import finder as FD       # noqa: E402
import presale as PS      # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def at(minute):
    return "2026-10-20T10:%02d:00Z" % minute


print("== #263 signals and sales read in any language ==")
french = JN.signal_rows({"event": "SAASignalsFound", "BodyName": "Ega 1", "Signals": [
    {"Type": "$SAA_SignalType_PlanetaryMiningLocation;",
     "Type_Localised": "Site d'extraction planétaire", "Count": 4},
    {"Type": "$SAA_SignalType_Geological;", "Type_Localised": "Géologique", "Count": 3}]})
check("a French client's mining signal is a mining signal",
      [JN.is_mining_signal(s) for s in french] == [True, False], french)
check("the symbol is kept with each row", french and french[0].get("symbol", "").startswith("$SAA"))
check("a row kept before the symbol was still reads by its English words",
      JN.is_mining_signal({"type": "Planetary mining location"})
      and not JN.is_mining_signal({"type": "Biological"}))
check("Find counts the French rows by the symbol",
      FD.signal_counts([{"symbol": "$SAA_SignalType_Geological;", "type": "Géologique", "count": 3},
                        {"symbol": "$SAA_SignalType_Biological;", "type": "Biologique", "count": 2}])
      == {"geological": 3, "biological": 2})
sale = SV.merit_note({"event": "MarketSell", "timestamp": at(1), "Type": "platinum",
                      "Type_Localised": "Platine", "Count": 10, "SellPrice": 200000,
                      "TotalSale": 2000000, "AvgPricePaid": 0})
check("a sale on a French client is Platinum, not Platine", sale["commodity"] == "Platinum", sale)

print("== #264 a line cut mid-character or holding U+2028 is read whole ==")
JD = os.path.join(TMP, "journals")
os.makedirs(JD)
log = os.path.join(JD, "Journal.2026-10-20T100000.01.log")
line = json.dumps({"timestamp": at(0), "event": "Commander", "FID": "F1",
                   "Name": "Zoë"}, ensure_ascii=False).encode("utf-8") + b"\n"
cut = line.index("ë".encode("utf-8")) + 1          # half of the two bytes
with open(log, "wb") as fh:
    fh.write(line[:cut])
jw = JN.JournalWatcher(JD)
jw.poll()
with open(log, "ab") as fh:
    fh.write(line[cut:])
jw.poll()
check("a name the read cut in half arrives whole", jw.cmdr == "Zoë", repr(jw.cmdr))
odd = json.dumps({"timestamp": at(1), "event": "Commander", "FID": "F1",
                  "Name": "Odd Name"}, ensure_ascii=False).encode("utf-8") + b"\n"
with open(log, "ab") as fh:
    fh.write(odd)
jw.poll()
check("a line separator inside an event does not split it", jw.cmdr == "Odd Name", repr(jw.cmdr))

print("== #265 #270 #277 the session books ==")
eb = SV.Earnings(os.path.join(TMP, "books"))
eb.observe({"event": "RigDown", "when": at(0), "system": "Ega", "body": "Ega 1",
            "cmdr": "CMDR Cee"})
row = eb.current
eb._in_rhino, eb._out = False, set()
eb.observe({"event": "CargoTransfer", "when": at(2), "moved": {"Platinum": 20}})
check("toship with no Rhino out is a carrier, not the Rhino's hold",
      SV.unpack_counts(row.get("transferred")) == {}, row.get("transferred"))
eb._in_rhino = True
eb.observe({"event": "CargoTransfer", "when": at(3), "moved": {"Platinum": 20}})
check("with the Rhino out it counts", SV.unpack_counts(eb.current.get("transferred")) == {"Platinum": 20},
      eb.current.get("transferred"))
eb.observe({"event": "Refined", "when": at(4), "commodity": "Platinum", "cmdr": "CMDR Alt"})
check("another commander logging in closes the open run",
      str(row.get("closed") or "").strip() != "" and "CMDR Alt" in str(row.get("notes") or "")
      + str(row.get("closed") or ""), (row.get("closed"), row.get("notes")))
eb.sessions[0]["mined"] = "Platinum:5"
dup = dict(eb.sessions[0])
eb.sessions.append(dict(dup))
eb.sessions.append(dict(dup, id="other-id"))
check("the same session written twice, or under two ids, is one",
      eb._dedupe() and len([r for r in eb.sessions if r.get("started") == dup["started"]]) == 1)
check("a sale with nothing mined or carried is not a session",
      SV.Earnings.sale_only({"mined": "", "transferred": "", "credits": "500"})
      and not SV.Earnings.sale_only({"mined": "Platinum:3", "credits": "500"}))

print("== #268 a price the game gives three commodities is not an average ==")
means = JN.market_means({"Items": [
    {"Name": "$iridium_name;", "Name_Localised": "Iridium", "MeanPrice": 129763},
    {"Name": "$thortveitite_name;", "Name_Localised": "Thortveitite", "MeanPrice": 129763},
    {"Name": "$pericladunite_name;", "Name_Localised": "Periclase Dunite", "MeanPrice": 129763},
    {"Name": "$platinum_name;", "Name_Localised": "Platinum", "MeanPrice": 210000},
    {"Name": "$gold_name;", "Name_Localised": "Gold", "MeanPrice": 47000}]})
check("the shared figure is dropped, the real ones kept",
      set(means.values()) == {210000, 47000} and len(means) == 2, means)

print("== #275 numbers with a decimal comma ==")
try:
    import edsmt as A   # noqa: E402
    num = A.local_number
except Exception as exc:     # no display: the function is pure, read it out
    num = None
    print("  SKIP  edsmt would not import here (%s)" % exc)
if num is not None:
    check("3,95 is 3.95 and 1.234,5 is 1234.5", num("3,95") == 3.95 and num("1.234,5") == 1234.5)
    check("3,950 and 1,234.5 are what they always were", num("3,950") == 3950 and num("1,234.5") == 1234.5)

print("== #260 #261 what selling here pays ==")
market = {"station": "Hub", "system": "Ega", "items": [
    {"commodity": "Platinum", "sell": 200000, "demand": 15},
    {"commodity": "Gold", "sell": 40000, "demand": ""}]}
found = PS.quote({"Platinum": 20, "Gold": 5, "Painite": 2}, market, merit_rate=0.001,
                 wages=0.1, show_merits=True)
check("demand caps the tonnes a sale takes", found["tonnes"] == 20 and found["of"] == 27
      and found["credits"] == 15 * 200000 + 5 * 40000, found)
check("the crew's cut and the net", found["wages"] == 320000 and found["net"] == 2880000)
check("what is not bought here is named", found["unsold"] == ["Painite"])
check("merits only when asked to show them",
      found["merits"] == 3200 and PS.quote({"Gold": 1}, market, 0.001)["merits"] is None)
check("merits shown only in the pledged Power's own system",
      PS.merits_count("Aisling Duval", {"ControllingPower": "Aisling Duval"}) == (True, "")
      and PS.merits_count("Aisling Duval", {"ControllingPower": "Zemina Torval"})[0] is False
      and PS.merits_count("", {"ControllingPower": "Aisling Duval"})[0] is False)
check("Fortified and Stronghold are said to be unmeasured",
      "not yet measured" in PS.merits_count("Aisling Duval", {
          "ControllingPower": "Aisling Duval", "PowerplayState": "Stronghold"})[1])
check("no wage share until two sessions carried one",
      PS.wage_share({"a": {"wages": 10, "wage_events": 1}}, [{"id": "a", "credits": "100"}]) is None)
line = PS.words(found)
check("one line for the status bar", line.startswith("Selling here: 20 t for 3.2 M cr (20 of 27 t aboard)")
      and "Not bought here: Painite" in line, line)
check("nothing bought here is nothing to say", PS.quote({"Painite": 2}, market) is None)

if __name__ == "__main__":
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    sys.exit(1 if fails else 0)
