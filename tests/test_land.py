"""Where to land: which body in a system is worth putting the ship down on.

Driven from a synthetic journal - FSS scans, one DSS map, one body mapped
and found empty - plus a server answer for what each kind of ground carries
and which sites are already shared. No display, no network.
"""
import json, os, sys, shutil, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import survey as S
import journal as JN

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)

TMP = tempfile.mkdtemp(prefix="edsmt-land-")
SYSTEM = "Col 285 Sector ZL-K b22-2"
ROCKY, HMC, ICY = S.ROCKY, S.HMC, S.ICY

print("== a kind of ground is named one way ==")
# The API counts sites per ground and the app looks them up by name; the
# two are compared beside the API's source. These are the app's half.
check("no volcanism is just the body class",
      S.ground_of(ROCKY, "No volcanism") == ROCKY == S.ground_of(ROCKY, ""))
check("volcanism is kept, without the word itself",
      S.ground_of(ROCKY, "Major silicate vapour geysers volcanism")
      == "Rocky body, major silicate vapour geysers")

print("== the journal knows every body it scanned, and which the DSS mapped ==")
GAME = os.path.join(TMP, "game"); os.makedirs(GAME)
JN.EVENT_LOG = os.path.join(GAME, "events.log")
JOURNAL = os.path.join(GAME, "Journal.2026-09-23T180000.01.log")
T = "2026-09-23T18:00:%02dZ"
def scan(n, name, cls, ls, landable=True, volc="", grav=2.4, temp=180.0):
    ev = {"timestamp": T % n, "event": "Scan", "ScanType": "Detailed",
          "StarSystem": SYSTEM, "BodyName": name, "DistanceFromArrivalLS": ls,
          "PlanetClass": cls, "Landable": landable, "Volcanism": volc,
          "SurfaceGravity": grav, "SurfaceTemperature": temp, "Radius": 1.8e6}
    return ev
events = [
    {"timestamp": T % 0, "event": "Fileheader", "part": 1, "gameversion": "4.4.1.1"},
    {"timestamp": T % 0, "event": "Commander", "Name": "Jameson", "FID": "F1"},
    {"timestamp": T % 1, "event": "FSDJump", "StarSystem": SYSTEM,
     "SystemAddress": 99, "StarPos": [1.0, 2.0, 3.0]},
    {"timestamp": T % 2, "event": "Scan", "StarSystem": SYSTEM,
     "BodyName": SYSTEM + " A", "StarType": "M", "DistanceFromArrivalLS": 0.0},
    scan(3, SYSTEM + " A 1", ROCKY, 412.5),
    scan(4, SYSTEM + " A 2", HMC, 96.0, volc="minor metallic magma volcanism"),
    scan(5, SYSTEM + " A 3", ICY, 1840.0),
    scan(6, SYSTEM + " A 4", "Water world", 60.0, landable=False),
    scan(7, SYSTEM + " A 5", ROCKY, 3010.0),
    {"timestamp": T % 8, "event": "SAASignalsFound", "BodyName": SYSTEM + " A 1",
     "Signals": [{"Type": "$SAA_SignalType_Geological;", "Type_Localised": "Geological", "Count": 2},
                 {"Type": "$SAA_SignalType_MiningSite;", "Type_Localised": "Mining site", "Count": 4}]},
    # The FSS can list a body's signals without the kind that matters, so an
    # FSS list alone must not turn "not looked" into "nothing here".
    {"timestamp": T % 8, "event": "FSSBodySignals", "BodyName": SYSTEM + " A 2",
     "Signals": [{"Type": "$SAA_SignalType_Geological;", "Type_Localised": "Geological", "Count": 3}]},
    {"timestamp": T % 9, "event": "SAASignalsFound", "BodyName": SYSTEM + " A 3",
     "Signals": [{"Type": "$SAA_SignalType_Geological;", "Type_Localised": "Geological", "Count": 1}]},
]
with open(JOURNAL, "w", encoding="utf-8") as fh:
    for ev in events:
        fh.write(json.dumps(ev) + "\n")
watcher = JN.JournalWatcher(GAME)
watcher.poll()
bodies = watcher.system_bodies(SYSTEM)
by = {b["body"]: b for b in bodies}
check("every scanned body is there, the star included",
      len(bodies) == 6, [b["body"] for b in bodies])
check("nearest the arrival star first",
      [b["distance_ls"] for b in bodies] == sorted(b["distance_ls"] for b in bodies))
check("landable is what the scan said",
      by[SYSTEM + " A 1"]["landable"] is True and by[SYSTEM + " A 4"]["landable"] is False)
check("a star has no landable answer at all", by[SYSTEM + " A"]["landable"] is None)
check("the DSS count is read off the map", by[SYSTEM + " A 1"]["locations"] == 4)
check("mapped is set for a DSS map only",
      by[SYSTEM + " A 1"]["mapped"] and by[SYSTEM + " A 3"]["mapped"]
      and not by[SYSTEM + " A 2"]["mapped"])
check("gravity comes out in g",
      abs(float(by[SYSTEM + " A 1"]["gravity_g"]) - 0.245) < 0.01, by[SYSTEM + " A 1"]["gravity_g"])
check("another system's bodies are not listed", watcher.system_bodies("Ega") == [])

print("== ranking: known intact sites, then unshared locations, then unmapped ==")
GROUNDS = {"count": 2, "grounds": [
    {"ground": ROCKY, "sites": 12, "commodities": [
        {"name": "Monazite", "sites": 6, "share": 0.5, "rigs": 22},
        {"name": "Haematite", "sites": 9, "share": 0.75, "rigs": 30},
        {"name": "Jadeite", "sites": 3, "share": 0.25, "rigs": 7}]},
    # Two sites is an anecdote - this ground must NOT be trusted yet.
    {"ground": "High metal content body, minor metallic magma", "sites": 2,
     "commodities": [{"name": "Copper", "sites": 2, "share": 1.0, "rigs": 4}]}]}
SITES = [
    {"system": SYSTEM, "planet": SYSTEM + " A 1", "spot": "1", "rigs": 6,
     "types": ["Monazite", "Haematite"], "worked_out": False, "status": "verified"},
    {"system": SYSTEM, "planet": SYSTEM + " A 1", "spot": "2", "rigs": 3,
     "types": ["Haematite"], "worked_out": True, "status": "reported"},
    # Nobody here scanned A 6, but somebody has stood on it.
    {"system": SYSTEM, "planet": SYSTEM + " A 6", "spot": "1", "rigs": 2,
     "types": ["Jadeite"], "worked_out": False, "status": "reported"},
]
MINE = [{"system": SYSTEM, "body": SYSTEM + " A 5", "commodity": "Olivine",
         "amount": "Depleted", "planet_class": ROCKY}]
PLACES = [{"system": SYSTEM, "body": SYSTEM + " A 5", "location": "1"}]
ranked = S.rank_bodies(SYSTEM, bodies, GROUNDS, SITES, {}, MINE, PLACES,
                       {(SYSTEM + " A 5").lower(): 64})
names = [r["short"] for r in ranked]
row = {r["short"]: r for r in ranked}
check("names are shortened to the body's own part", "A 1" in names, names)
check("each body says everything it carries: its ground's whole mix and what "
      "was found there, not only the few bets shown",
      {"monazite", "haematite", "jadeite"} <= set(row["A 1"]["carries"]),
      row["A 1"]["carries"])
check("your own finds count as carried", "olivine" in row["A 5"]["carries"],
      row["A 5"]["carries"])
check("not landable and the star are left out by default",
      "A 4" not in names and "A" not in names, names)
check("A 1 leads: a verified intact site plus two locations nobody shared",
      names[0] == "A 1", names)
check("A 1 counts 1 intact and 1 worked out",
      (row["A 1"]["known"], row["A 1"]["intact"], row["A 1"]["worked"],
       row["A 1"]["verified"], row["A 1"]["known_rigs"]) == (2, 1, 1, 1, 6),
      row["A 1"])
m, h, j = (S.published_price(n) for n in ("Monazite", "Haematite", "Jadeite"))
per_site = 0.5 * m + 0.75 * h + 0.25 * j
check("the ground's mix is trusted once 12 sites are behind it",
      row["A 1"]["basis"] == "12 shared sites" and row["A 1"]["per_site"] == round(per_site),
      (row["A 1"]["basis"], row["A 1"]["per_site"], per_site))
check("value = the intact site at what it carries + 2 unshared locations",
      row["A 1"]["value"] == round(m + h + 2 * per_site), (row["A 1"]["value"], m + h + 2 * per_site))
check("best bets lead with what is worth most on average",
      [n for n, _ in row["A 1"]["bets"]][0] == "Monazite", row["A 1"]["bets"])
check("a site nobody here scanned is still listed - somebody stood on it",
      "A 6" in row and row["A 6"]["landable"] is True and row["A 6"]["intact"] == 1)
check("a ground with only two sites falls back to the tables",
      row["A 2"]["basis"] == "tables", row["A 2"]["basis"])
check("the tables only offer what turns up on that body class",
      all(S.on_body(n, HMC) for n, _ in row["A 2"]["bets"])
      and "Monazite" not in [n for n, _ in row["A 2"]["bets"]], row["A 2"]["bets"])
check("an unmapped body is not a zero - its locations are unknown",
      row["A 2"]["locations"] is None and "DSS" in row["A 2"]["note"], row["A 2"])
check("a mapped body with no mining signals says so",
      row["A 3"]["locations"] == 0 and "no mining" in row["A 3"]["note"], row["A 3"])
check("mapped-empty sorts below unmapped, which sorts below known value",
      names.index("A 3") > names.index("A 2") > names.index("A 1"), names)
check("your own locations and finds are counted",
      (row["A 5"]["yours"], row["A 5"]["your_deposits"], row["A 5"]["your_worked"]) == (1, 1, 1))
check("how much of it you have swept is carried through", row["A 5"]["swept"] == 64)
everything = S.rank_bodies(SYSTEM, bodies, GROUNDS, SITES, landable_only=False)
check("show-all includes the ones you cannot land on",
      "A 4" in [r["short"] for r in everything])
check("a live market price beats the published one",
      S.rank_bodies(SYSTEM, bodies, GROUNDS, SITES,
                    {S.fold("Monazite"): 900000})[0]["value"] > row["A 1"]["value"])

print("== offline, and with nothing at all ==")
offline = S.rank_bodies(SYSTEM, bodies)
check("with no server every basis is the tables",
      all(r["basis"] in ("tables", "") for r in offline), [(r["short"], r["basis"]) for r in offline])
check("DSS locations still rank first offline",
      offline[0]["short"] == "A 1" and offline[0]["value"] > 0)
check("nothing in, nothing out, no exception", S.rank_bodies("", []) == [])
check("junk rows are skipped, not fatal",
      S.rank_bodies(SYSTEM, [None, {}, {"body": ""}], {"grounds": [None, {}]},
                    [None, {"planet": ""}], None, [None], [None], {}) == [])
check("short_body leaves a body that is not in the system alone",
      S.short_body("Ega", "Col 285 A 1") == "Col 285 A 1"
      and S.short_body("Ega", "Ega") == "Ega")

shutil.rmtree(TMP, ignore_errors=True)
print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
