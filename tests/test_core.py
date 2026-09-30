"""The survey model and the plan view, driven without a display.

The scenario is the one from a real session: Ega 1, a mining location signal
offering copper, haematite, lithium, palladium, uranium and a depleted
sapphire, with haematite deposits found at 896m, 1.26km and 1.47km.
"""
import os, sys, csv, math, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import survey as S, planview as P

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)

R = 2_100_000.0
TMP = tempfile.mkdtemp(prefix="edsmt-")

print("== geometry ==")
one_degree = 2 * math.pi * R / 360.0
check("a degree of longitude at the equator",
      abs(S.surface_range_m(0, 0, 0, 1, R) - one_degree) < 1.0)
check("no distance to yourself", S.surface_range_m(5, 5, 5, 5, R) == 0.0)
check("north is 0", abs(S.bearing_deg(0, 0, 1, 0)) < 1e-9)
check("east is 90", abs(S.bearing_deg(0, 0, 0, 1) - 90) < 1e-9)
east, north = S.local_offset(0, 0, 0, 0.01, R)
check("east offset is east", east > 100 and abs(north) < 0.01, (east, north))
east, north = S.local_offset(0, 0, 0.01, 0, R)
check("north offset is north", north > 100 and abs(east) < 0.01, (east, north))

print("== driving directions ==")
check("straight on", S.turn_hint(90, 92) == "straight ahead")
check("right", S.turn_hint(0, 90) == "right")
check("left", S.turn_hint(90, 0) == "left")
check("about turn", S.turn_hint(0, 180) == "turn around")
check("wraps past north", S.relative_bearing(350, 10) == 20)
check("compass", S.compass(0) == "N" and S.compass(90) == "E" and S.compass(200) == "SSW")

print("== commodities are suggestions, not a whitelist ==")
check("the 4.4.1.0 thirteen are known", S.canonical("magnesite") == "Magnesite")
check("umlaut folds", S.canonical("bastnasite") == "Bastnäsite")
check("symbol form folds", S.canonical("$bastnasite_name;") == "Bastnäsite")
for seen in ("Copper", "Haematite", "Lithium", "Palladium", "Uranium"):
    check("%s is known" % seen, S.canonical(seen.lower()) == seen)
check("something brand new is still accepted",
      S.canonical("unobtainium") == "Unobtainium", S.canonical("unobtainium"))
check("and remembered once seen", S.remember("$flurbium_name;") == "Flurbium")
check("so it turns up as a suggestion next time", "Flurbium" in S.KNOWN_COMMODITIES)
check("blank is blank", S.canonical("") == "" and S.canonical(None) == "")

print("== a mining location signal ==")
store = S.Survey(TMP)
check("starts empty", store.deposits == [] and store.locations == [])
loc = store.set_location(
    "Ega", "Ega 1", "1", lat=12.5, lon=-45.5, radius_m=R,
    commodities=["Copper", "Haematite", "Lithium", "Palladium", "Uranium", "Sapphire"],
    depleted=["Sapphire"], temperature_k=214.5, cmdr="Jameson")
check("recorded", store.location("Ega", "Ega 1", "1") is not None)
check("six commodities offered", len(store.offered(loc)) == 6, store.offered(loc))
check("haematite is on offer", "Haematite" in store.offered(loc))
check("sapphire is flagged worked out", store.worked_out(loc) == ["Sapphire"])
check("temperature kept", loc["temperature_k"] == "214.5")

print("== updating a location does not wipe what it already knew ==")
store.set_location("Ega", "Ega 1", "1", lat=12.6, lon=-45.6)
again = store.location("Ega", "Ega 1", "1")
check("position updated", again["lat"] == "12.600000")
check("commodity list survived", len(store.offered(again)) == 6, store.offered(again))
check("depleted list survived", store.worked_out(again) == ["Sapphire"])

print("== marking deposits, with no centre to set first ==")
# the three haematite pings from the screenshot, plus the copper
here = (12.5, -45.5)
for commodity, metres, bearing in (("Haematite", 896, 30), ("Haematite", 1260, 110),
                                   ("Haematite", 1470, 250), ("Copper", 2700, 340)):
    theta = math.radians(bearing)
    dlat = here[0] + math.degrees(metres * math.cos(theta) / R)
    dlon = here[1] + math.degrees(metres * math.sin(theta) / (R * math.cos(math.radians(here[0]))))
    store.add_deposit(system="Ega", body="Ega 1", location="1",
                      commodity=commodity, lat="%.6f" % dlat, lon="%.6f" % dlon,
                      cmdr="Jameson")
check("four deposits", len(store.deposits) == 4)
check("no bearing column exists at all", "bearing" not in S.DEPOSIT_FIELDS)
check("no range column either", "range_m" not in S.DEPOSIT_FIELDS)
check("ids unique", len({d["id"] for d in store.deposits}) == 4)
check("rigs may be blank - you do not know until you get there",
      store.deposits[0]["rigs"] == "")

print("== what is near me, worked out live ==")
near = store.near("Ega", "Ega 1", here[0], here[1], R)
check("all four found", len(near) == 4, len(near))
check("nearest first", near[0]["range_m"] < near[-1]["range_m"])
check("the 896m ping is about 896m away", abs(near[0]["range_m"] - 896) < 5,
      near[0]["range_m"])
check("the copper is furthest", near[-1]["deposit"]["commodity"] == "Copper")
check("bearing to the first is about 30", abs(near[0]["bearing"] - 30) < 1,
      near[0]["bearing"])
check("limit works", len(store.near("Ega", "Ega 1", *here, R, limit=2)) == 2)

print("== rig count filled in when you get there ==")
first = near[0]["deposit"]
store.update_deposit(first["id"], rigs="4", density="High")
check("rigs updated", store.at("Ega", "Ega 1")[0]["rigs"] == "4")
check("density updated", store.at("Ega", "Ega 1")[0]["density"] == "High")
check("updating something that is not there is not an error",
      store.update_deposit("nope", rigs="9") is None)

print("== it survives a restart ==")
reopened = S.Survey(TMP)
check("deposits reloaded", len(reopened.deposits) == 4)
check("locations reloaded", len(reopened.locations) == 1)
check("the commodity list came back",
      len(reopened.offered(reopened.location("Ega", "Ega 1", "1"))) == 6)
check("a backup is kept", os.path.exists(store.deposits_path + ".bak"))
check("deleting works", reopened.remove_deposit(first["id"]))
check("and it is gone", len(reopened.deposits) == 3)

print("== the store has exactly one way in, and it is not its own ==")
# adopt_legacy() used to live here: a private second importer that refused
# the moment the commander had a single find of their own, returned 0
# whether it had worked or been refused, and read density and recorded
# columns the imported layouts have never carried. edsmt.py's import_finds
# does the same job properly for every format, so the store must not grow
# a rival back.
check("the store no longer carries a second importer",
      not hasattr(S.Survey, "adopt_legacy"))
check("and nothing in survey.py reads columns only that one invented",
      "surfaceminingmap" not in open(
          os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "survey.py"), encoding="utf-8").read())

print("== a signal can say where it came from ==")
# notes is a column LOCATION_FIELDS has always carried and set_location had
# no parameter for, so set_location(..., notes=...) was a TypeError waiting
# for its first caller - the exact shape of the bug that broke the first F10
# on every new body.
noted = S.Survey(os.path.join(TMP, "noted"))
import inspect as _inspect
check("set_location takes a notes keyword at all",
      "notes" in _inspect.signature(S.Survey.set_location).parameters)
noted.set_location("Ega", "Ega 9", "1", notes="imported from another tool")
_row = noted.location("Ega", "Ega 9", "1")
check("and it lands in the notes column",
      "imported from another tool" in _row["notes"], _row["notes"])
check("dated, the way a deposit note is",
      len(_row["notes"].split()) > 4, _row["notes"])
noted.set_location("Ega", "Ega 9", "1", notes="stood on it myself")
_row = noted.location("Ega", "Ega 9", "1")
check("a second note is added, not swapped in",
      "imported from another tool" in _row["notes"]
      and "stood on it myself" in _row["notes"], _row["notes"])
check("and it survives the trip through the CSV",
      "stood on it myself" in
      S.Survey(os.path.join(TMP, "noted")).location("Ega", "Ega 9", "1")["notes"])
noted.set_location("Ega", "Ega 9", "1", lat=1.0, lon=2.0)
check("logging a position later does not wipe the note",
      "stood on it myself" in
      noted.location("Ega", "Ega 9", "1")["notes"])
check("and passing no note at all leaves the column alone",
      noted.location("Ega", "Ega 9", "1")["notes"].count("stood on it") == 1)

print("== the plan view, centred on you ==")
vp = P.Viewport(800, 600, extent_m=2000)
cx, cy = vp.centre
check("you are in the middle", vp.to_canvas(0, 0) == (400.0, 300.0))
check("north goes up", vp.to_canvas(0, 1000)[1] < cy)
check("east goes right", vp.to_canvas(1000, 0)[0] > cx)
back = vp.to_metres(*vp.to_canvas(321.0, -123.0))
check("pixels map back to metres",
      abs(back[0] - 321) < 0.01 and abs(back[1] + 123) < 0.01, back)

plan = P.layout(store.near("Ega", "Ega 1", *here, R), vp, heading=45)
check("everything laid out", len(plan["items"]) == 4, len(plan["items"]))
check("rings drawn", len(plan["rings"]) >= 2)
check("ring step is a round number", plan["ring_step_m"] in P.NICE_STEPS_M)
check("the copper is beyond the edge", 
      [i for i in plan["items"] if i["commodity"] == "Copper"][0]["offscreen"] is True)
check("and gets an edge marker to point at",
      [i for i in plan["items"] if i["commodity"] == "Copper"][0]["edge"] is not None)
check("the near haematite is on screen",
      plan["items"][0]["offscreen"] is False)

print("== marker size follows rigs, and copes without one ==")
check("unknown rigs still get a marker", P.marker_radius("") > 0)
check("more rigs, bigger", P.marker_radius("6") > P.marker_radius("1"))
check("capped", P.marker_radius("999") <= 17.0)

print("== clicking ==")
target = plan["items"][0]
check("a click on it finds it", P.hit_test(plan["items"], target["x"], target["y"])["id"] == target["id"])
check("a near miss still finds it", P.hit_test(plan["items"], target["x"] + 5, target["y"]) is not None)
check("empty space finds nothing", P.hit_test(plan["items"], 5, 5) is None)

print("== dragging the map ==")
plain = P.Viewport(400, 300, 1000)
moved = P.Viewport(400, 300, 1000, pan=(60, -40))
check("no pan means you are still in the middle", not plain.panned)
check("a pan shifts the centre", moved.centre == (260.0, 110.0), moved.centre)
check("and it knows it has been moved", moved.panned)
check("the scale is untouched by panning", plain.scale == moved.scale)
# The transform has to stay reversible or clicking a pin after a drag picks
# the wrong deposit - which is the bug panning usually introduces.
x, y = moved.to_canvas(300, -150)
east, north = moved.to_metres(x, y)
check("panned pixels still map back to the same metres",
      abs(east - 300) < 1e-6 and abs(north + 150) < 1e-6, (east, north))
check("a tiny pan does not count as moved", not P.Viewport(400, 300, 1000,
                                                           pan=(0.2, -0.3)).panned)

print("== the heading arrow ==")
check("facing north the nose is up", P.arrow_points(100, 100, 0)[0][1] < 100)
check("facing east the nose is right", P.arrow_points(100, 100, 90)[0][0] > 100)

print("== best patch, clustered on coordinates ==")
import edonline as EO
# Three haematite deposits close together and one a long way off. This is
# what "overlapping hotspots" means on a surface: rigs down once, work the
# lot without driving.
PATCH = [
    {"type": "Haematite", "rigs": 6, "density": "High",  "lat": 12.5000, "lon": -45.5000},
    {"type": "Copper",    "rigs": 4, "density": "Medium","lat": 12.5008, "lon": -45.4995},
    {"type": "Haematite", "rigs": 3, "density": "Low",   "lat": 12.5012, "lon": -45.5003},
    {"type": "Lithium",   "rigs": 2, "density": "Low",   "lat": 12.5300, "lon": -45.4000},
]
groups = EO.cluster_deposits(PATCH, 0.35, R)
check("the tight three group together", sorted(groups[0]) == [0, 1, 2], groups)
check("the far one is on its own", [g for g in groups if g != groups[0]] == [[3]], groups)

best = EO.rank_clusters(PATCH, 0.35, R)[0]
check("the patch is ranked first", best["deposits"] == 3, best["deposits"])
check("its rigs are added up", best["rigs"] == 13, best["rigs"])
check("two commodities in reach", best["distinct_types"] == 2, best["types"])
check("and it is tight", best["spread_km"] < 0.2, best["spread_km"])

# The body's radius is not decoration: a degree is 36 km on a small moon and
# 110 km on a large world, so clustering with the wrong scale groups things
# that are nowhere near each other.
check("scale matters - a tiny body spreads the same coordinates out",
      len(EO.cluster_deposits(PATCH, 0.02, R)) > len(EO.cluster_deposits(PATCH, 0.35, R)))
check("no coordinates, no cluster",
      EO.cluster_deposits([{"type": "Ruby"}], 0.35, R) == [])
check("an older bearing-and-range row still places",
      EO.cluster_deposits([{"direction": 90, "distance": 0.1},
                           {"direction": 92, "distance": 0.11}], 0.35, R) == [[0, 1]])
check("no deposits, no patches", EO.rank_clusters([], 0.35, R) == [])

print("== a signal logged wrongly can be put right ==")
# F9 is pressed with the game in front of you and the number comes off a
# dropdown, so logging 2 when you meant 3 is a one-key mistake. Until this
# existed there was no way back from it.
import tempfile as _tf
_dir = _tf.mkdtemp(dir=TMP)
fix = S.Survey(_dir)
fix.set_location("HR 7280", "A 4 b", "2", commodities=["Copper"])
fix.set_location("HR 7280", "A 4 b", "3", commodities=["Haematite", "Copper"])
for n in range(4):
    fix.add_deposit(system="HR 7280", body="A 4 b", location="3",
                    commodity="Haematite", lat=1.0 + n, lon=2.0)

check("both signals are on the body",
      [r["location"] for r in fix.locations_on("HR 7280", "A 4 b")] == ["2", "3"])
moved = fix.renumber_location("HR 7280", "A 4 b", "3", "7")
check("renumbering carries the deposits with it", moved == 4, moved)
check("the signal is renumbered",
      [r["location"] for r in fix.locations_on("HR 7280", "A 4 b")] == ["2", "7"])
check("the deposits went with it",
      len(fix.at("HR 7280", "A 4 b", "7")) == 4)
check("and none were left behind on the old number",
      fix.at("HR 7280", "A 4 b", "3") == [])

clashed = False
try:
    fix.renumber_location("HR 7280", "A 4 b", "7", "2")
except ValueError:
    clashed = True
check("renumbering onto an existing signal is refused", clashed)
check("and the refusal changed nothing",
      len(fix.at("HR 7280", "A 4 b", "7")) == 4)

check("renumbering to the same number is a no-op",
      fix.renumber_location("HR 7280", "A 4 b", "7", "7") == 0)
check("renumbering a signal that is not there is a no-op",
      fix.renumber_location("HR 7280", "A 4 b", "99", "100") == 0)

fix.set_offered(fix.location("HR 7280", "A 4 b", "7")["id"], ["Copper", "Lithium"])
check("what a signal offers can be rewritten",
      fix.offered(fix.location("HR 7280", "A 4 b", "7")) == ["Copper", "Lithium"])

empty = fix.location("HR 7280", "A 4 b", "2")
check("deleting an empty signal reports no orphans",
      fix.remove_location(empty["id"]) == 0)
full = fix.location("HR 7280", "A 4 b", "7")
check("deleting a signal reports what it leaves behind",
      fix.remove_location(full["id"]) == 4)
check("but the deposits themselves survive - they were real places",
      len(fix.at("HR 7280", "A 4 b", "7")) == 4)
check("deleting a signal twice is not an error",
      fix.remove_location(full["id"]) is None)

again = S.Survey(_dir)
check("all of it survived being written to disk",
      again.locations_on("HR 7280", "A 4 b") == []
      and len(again.at("HR 7280", "A 4 b")) == 4)

print("== what things are actually worth ==")
# The bands here were guessed and were wrong: Magnesite was ranked above
# Periclase Dunite, which is worth five times as much. These are Inara's
# published averages now.
check("Periclase dunite outranks Magnesite, as it should",
      S.published_price("Periclase dunite") > S.published_price("Magnesite"))
check("the whole surface table is priced, not just the thirteen Inara flags",
      len(S.COMMODITIES) >= 37, len(S.COMMODITIES))
check("Water is in the list - it was missing, and it is real",
      S.published_price("Water") > 0)
for _name in ("Tantalum", "Jadeite", "Methanol Crystals", "Monazite"):
    check("%s is priced" % _name, S.published_price(_name) > 0)
check("every commodity carries a body class",
      all(S.bodies_for(n) for n in S.COMMODITIES),
      [n for n in S.COMMODITIES if not S.bodies_for(n)])
check("ordering uses the average, not the community-goal ceiling",
      S.by_value(["Iridium", "Monazite"])[0] == "Monazite")
check("water only comes off ice",
      S.on_body("Water", "Icy body") and not S.on_body("Water", "Rocky body"))
check("iridium never does",
      not S.on_body("Iridium", "Icy body") and S.on_body("Iridium", "Rocky body"))
check("an unknown body hides nothing", S.on_body("Water", ""))
check("an unknown commodity hides nothing", S.on_body("Unobtainium", "Icy body"))
_here, _rest = S.for_body(["Iridium", "Water", "Helium-3"], "Icy body")
check("the box splits by what can be underneath you",
      _here == ["Water", "Helium-3"] and _rest == ["Iridium"], (_here, _rest))
check("the umlaut form is priced too", S.published_price("Bastnasite") > 0)
order = S.by_value(["Magnesite", "Periclase dunite", "Olivine", "Iridium",
                     "Copper", "Diamond", "Unobtainium"])
check("ordered by real money", order[:4] ==
      ["Iridium", "Periclase dunite", "Diamond", "Magnesite"], order)
check("a commodity nobody has priced sorts last, not cheapest",
      order[-1] == "Unobtainium", order)
check("a live community price beats the published one",
      S.by_value(["Iridium", "Olivine"],
                  {S.fold("Olivine"): 999999})[0] == "Olivine")
check("every priced commodity is in the known list",
      all(any(S.fold(n) == S.fold(k) for k in S.KNOWN_COMMODITIES)
          for n in S.SURFACE_PRICES),
      [n for n in S.SURFACE_PRICES
       if not any(S.fold(n) == S.fold(k) for k in S.KNOWN_COMMODITIES)])

print("== telling people about a new build ==")
import edonline as _EDO
check("a later build is newer", _EDO.is_newer("1.10002", "1.10001"))
check("an earlier one is not", not _EDO.is_newer("1.10001", "1.10002"))
check("the same one is not", not _EDO.is_newer("1.10002", "1.10002"))
# The classic: string comparison says "1.9" > "1.10002" and everybody is
# told they are up to date for ever.
check("1.9 is not newer than 1.10002", not _EDO.is_newer("1.9", "1.10002"))
check("1.10010 is newer than 1.1001", _EDO.is_newer("1.10010", "1.1001"))
check("nonsense is never newer", not _EDO.is_newer("", "1.1")
      and not _EDO.is_newer("banana", "1.1"))
check("a shorter version still compares", _EDO.is_newer("2", "1.99999"))

print("== the community client can reach every endpoint the server serves ==")
# Four of them had no client method at all. The server computed the single
# most useful thing in the project - which patches are probably still there
# - and the app physically could not ask the question.
import urllib.parse as _up

class _Spy:
    """Stands in for the worker thread. Runs the job, keeps the URL."""
    def __init__(self): self.jobs = []
    def submit(self, tag, fn): self.jobs.append((tag, fn))

def _client(token=""):
    spy = _Spy()
    client = _EDO.CommunityClient(spy)
    client.configure("https://api.radioraxxla.com", token=token, enabled=False)
    return client, spy

def _sent(spy, index=-1):
    """(tag, path, parameters) of a queued request, without any network."""
    tag, fn = spy.jobs[index]
    seen = {}
    real_get, real_post = _EDO.get_json, _EDO.post_json
    _EDO.get_json = lambda url, **k: seen.update(url=url) or {}
    _EDO.post_json = lambda url, payload, **k: (
        seen.update(url=url, payload=payload) or {"ok": True})
    try:
        fn()
    finally:
        _EDO.get_json, _EDO.post_json = real_get, real_post
    split = _up.urlsplit(seen["url"])
    return (tag, split.path,
            dict(_up.parse_qsl(split.query)), seen.get("payload"))

HERE = (1.0, 2.0, 3.0)

c, spy = _client()
check("intact is a method now", callable(getattr(c, "intact", None)))
check("and so is the commodity list", callable(getattr(c, "commodities", None)))
check("and the sell lookup", callable(getattr(c, "sell", None)))
check("and verifying a site", callable(getattr(c, "verify", None)))

check("intact goes out", c.intact(commodity="Ruby", near=HERE, within_ly=500))
tag, path, q, _ = _sent(spy)
check("to /v1/intact, under its own tag",
      (tag, path) == ("intact", "/v1/intact"), (tag, path))
check("carrying the commodity", q.get("commodity") == "Ruby", q)
check("and the same position parameters the site search uses",
      (q.get("near_x"), q.get("within_ly")) == ("1.0", "500.0"), q)

# min_confidence is the one number here with a non-zero default at the far
# end. Dropped for being falsy, "show me everything" silently became 0.5.
c.intact(min_confidence=0.0)
check("asking for no confidence floor says so rather than being dropped",
      _sent(spy)[2].get("min_confidence") == "0.0", _sent(spy)[2])

c.commodities()
check("the commodity list is fetched under its own tag",
      _sent(spy)[:2] == ("commodities", "/v1/commodities"), _sent(spy)[:2])

print("== the site search passes the three filters the server grew ==")
c, spy = _client()
c.sites(system="Ega", verified_only=True, include_depleted=True)
q = _sent(spy)[2]
check("the typed system reaches the server", q.get("system") == "Ega", q)
check("verified only reaches it as a flag HTTP agrees on",
      q.get("verified_only") == "true", q)
check("and so does include depleted", q.get("include_depleted") == "true", q)

c.sites()
q = _sent(spy)[2]
check("a flag that is off is left off the wire entirely",
      "verified_only" not in q and "include_depleted" not in q, q)
# str(False) is "False", which an older server that has not grown the flag
# rejects rather than ignores - and sending a default means nothing anyway.
c.sites(verified_only=True, include_depleted=True)
check("so nothing ever sends Python's own spelling of a boolean",
      all(v not in ("False", "True") for v in _sent(spy)[2].values()),
      _sent(spy)[2])

print("== best sell prices asks where the commander is, not what it is called ==")
# It matched the commander's current system by name. You are on a planet
# surface. Nobody has ever sold anything there, so it answered with nothing
# every single time, for everybody, since the button was added.
c, spy = _client()
c.best_prices(commodity="Ruby", near=HERE, within_ly=100)
tag, path, q, _ = _sent(spy)
check("the price lookup carries a position", q.get("near_x") == "1.0", q)
check("and a radius", q.get("within_ly") == "100.0", q)
check("still on /v1/prices", (tag, path) == ("market", "/v1/prices"), (tag, path))

c.best_prices(commodity="Ruby", near_system="Sol")
q = _sent(spy)[2]
check("asking by name still works, for anything that already did",
      q.get("near") == "Sol" and "near_x" not in q, q)

c, spy = _client()
check("a named commodity goes to the richer endpoint",
      c.sell(commodity="Ruby", near=HERE, within_ly=100))
tag, path, q, _ = _sent(spy)
check("which is /v1/sell, under its own tag",
      (tag, path) == ("sell", "/v1/sell"), (tag, path))
check("with the position on it too", q.get("near_z") == "3.0", q)
check("a sell lookup with no commodity is refused here rather than by the "
      "server, which answers 422", not c.sell(""))
check("and nothing was queued for it", len(spy.jobs) == 1, spy.jobs)

print("== verifying a site needs a staff token, and reading never does ==")
c, spy = _client()
check("reading is not sharing and never needed permission", c.can_read)
check("but verifying without a token is not offered", not c.can_verify)
check("and is refused rather than sent", not c.verify("CMDR Jameson", "Ega", "Ega 1"))
check("nothing was queued", not spy.jobs, spy.jobs)

c, spy = _client(token="staff-token")
check("with a token it goes", c.verify("CMDR Jameson", "Ega", "Ega 1", "2"))
tag, path, _q, payload = _sent(spy)
check("to /v1/verify", (tag, path) == ("verify", "/v1/verify"), (tag, path))
check("naming the site it means",
      payload["message"] == {"system": "Ega", "planet": "Ega 1",
                             "spot": "2", "verified": True}, payload)
check("in the same envelope as every other upload",
      payload["$schema"] == _EDO.VERIFY_SCHEMA
      and payload["header"]["softwareName"] == _EDO.APP_NAME, payload)
check("crediting the commander the journal named",
      payload["header"]["uploaderID"] == "CMDR Jameson", payload["header"])
check("a site with no body is refused", not c.verify("CMDR Jameson", "Ega", ""))

c.share_name = False
c.verify("CMDR Jameson", "Ega", "Ega 1")
check("and a commander who shares no name verifies anonymously",
      _sent(spy)[3]["header"]["uploaderID"] == "", _sent(spy)[3]["header"])

check("a spot nobody filled in becomes the first one, not an empty string",
      (c.verify("CMDR Jameson", "Ega", "Ega 1", "")
       and _sent(spy)[3]["message"]["spot"] == "1"), _sent(spy)[3])

# The reply is one sentence for a status line, not a dict for a table.
check("a verified reply reads as one",
      _EDO.CommunityClient._verified(
          {"ok": True, "status": "verified", "by": "CMDR Jameson"})
      == "site verified by CMDR Jameson")
check("a withdrawal is not reported as a verification",
      _EDO.CommunityClient._verified({"ok": True, "status": "reported"})
      == "verification withdrawn")
check("and a refusal says so",
      _EDO.CommunityClient._verified({}) == "not recorded")

print("== nothing reads the community map before there is one to read ==")
blind = _EDO.CommunityClient(_Spy())
blind.configure("")
blind.base_url = ""
for name, call in (("intact", lambda: blind.intact()),
                   ("commodities", lambda: blind.commodities()),
                   ("sell", lambda: blind.sell("Ruby")),
                   ("prices", lambda: blind.best_prices()),
                   ("verify", lambda: blind.verify("x", "Ega", "Ega 1"))):
    check("%s refuses with no URL configured" % name, not call())

print("== a run's tally packs into one cell and comes back out ==")
check("largest first, because that is what the run was about",
      S.pack_counts({"Copper": 6, "Haematite": 44}) == "Haematite:44;Copper:6",
      S.pack_counts({"Copper": 6, "Haematite": 44}))
check("and it reads back the same",
      S.unpack_counts("Haematite:44;Copper:6") == {"Haematite": 44, "Copper": 6})
check("nothing mined is not a column of zeroes",
      S.pack_counts({"Copper": 0}) == "")
check("a chunk with no count is dropped rather than guessed at",
      S.unpack_counts("Haematite;Copper:6") == {"Copper": 6},
      S.unpack_counts("Haematite;Copper:6"))
check("and so is one with a count that is not a number",
      S.unpack_counts("Haematite:lots") == {})
check("an empty cell is an empty tally",
      S.unpack_counts("") == {} and S.unpack_counts(None) == {})
check("the same commodity twice adds up",
      S.unpack_counts("Copper:2;Copper:3") == {"Copper": 5})
_tally = {"Copper": 2}
S.add_counts(_tally, {"Copper": 3, "Ruby": 1})
check("tallies fold together", _tally == {"Copper": 5, "Ruby": 1}, _tally)

print("== what a run was worth an hour ==")
check("an hour is an hour",
      S.hours_between("2026-09-17T18:00:00Z", "2026-09-17T19:00:00Z") == 1.0)
check("fractional seconds do not cost the whole duration",
      S.hours_between("2026-09-17T18:00:00.417Z", "2026-09-17T19:00:00Z") == 1.0)
check("a timestamp that is not one answers nothing, not a wrong number",
      S.hours_between("yesterday", "2026-09-17T19:00:00Z") == 0.0)
check("time does not run backwards",
      S.hours_between("2026-09-17T19:00:00Z", "2026-09-17T18:00:00Z") == 0.0)
_run = {"started": "2026-09-17T18:00:00Z", "ended": "2026-09-17T20:00:00Z",
        "credits": "200000", "cost": "0"}
check("mined cargo cost nothing, so the sale is the profit",
      S.earned(_run) == 200000)
check("two hundred thousand in two hours is a hundred thousand an hour",
      S.credits_per_hour(_run) == 100000.0, S.credits_per_hour(_run))
_bought = dict(_run, cost="60000")
check("what the cargo cost comes off the top",
      S.earned(_bought) == 140000 and S.credits_per_hour(_bought) == 70000.0)
check("a run with no length answers zero, not infinity",
      S.credits_per_hour({"started": "2026-09-17T18:00:00Z",
                          "ended": "2026-09-17T18:00:00Z",
                          "credits": "5000"}) == 0.0)

print("== what the hold in front of you is worth ==")
check("priced at what this station pays",
      S.hold_value({"Haematite": 44, "Copper": 6},
                   {S.fold("Haematite"): 2800, S.fold("Copper"): 774}) == 127844.0,
      S.hold_value({"Haematite": 44, "Copper": 6},
                   {S.fold("Haematite"): 2800, S.fold("Copper"): 774}))
check("a spelling the market localised still prices",
      S.hold_value({"Bastnasite": 2}, {S.fold("Bastnäsite"): 1000}) == 2000.0)
check("what this station does not buy counts as nothing, not as a guess",
      S.hold_value({"Haematite": 44, "Unobtainium": 10},
                   {S.fold("Haematite"): 2800}) == 123200.0)
check("an empty hold is worth nothing", S.hold_value({}, {"x": 1}) == 0.0)

print("== a Rhino session, off synthetic files shaped like a real 4.4.1.1 one ==")
# Every event here is the shape it has in real 4.4.1.1 journals, read (and
# never written) from the author's own game: LaunchSRV and DockSRV carry
# SRVType "mev_rhino"; MiningRefined is one tonne; CargoTransfer "toship"
# moves the Rhino's hold across without boarding; Cargo carries a Vessel.
import json as _json
import journal as JN
import time
import edonline as EDO

GAME = os.path.join(TMP, "game"); os.makedirs(GAME)
JN.EVENT_LOG = os.path.join(GAME, "events.log")
JOURNAL = os.path.join(GAME, "Journal.2026-09-17T180000.01.log")


def log(*events):
    """Append events the way the game does - one JSON object per line."""
    with open(JOURNAL, "a", encoding="utf-8") as fh:
        for event in events:
            fh.write(_json.dumps(event) + "\n")


def put(name, payload):
    """Rewrite one of the files the game replaces wholesale."""
    with open(os.path.join(GAME, name), "w", encoding="utf-8") as fh:
        fh.write(payload if isinstance(payload, str) else _json.dumps(payload))


def hold(vessel, when, **counts):
    put("Cargo.json", {"timestamp": when, "event": "Cargo", "Vessel": vessel,
                       "Count": sum(counts.values()),
                       "Inventory": [{"Name": name, "Count": count, "Stolen": 0}
                                     for name, count in counts.items()]})


def at(minute, second=0):
    return "2026-09-17T%02d:%02d:%02dZ" % (18 + minute // 60, minute % 60, second)


def refined(minute, second, name, times=1):
    return [{"timestamp": at(minute, second), "event": "MiningRefined",
             "Type": "$%s_name;" % name.lower(), "Type_Localised": name}
            for _ in range(times)]


RHINO_OUT = {"event": "LaunchSRV", "SRVType": "mev_rhino",
             "SRVType_Localised": "SRV Rhino", "Loadout": "galactic", "ID": 103,
             "PlayerControlled": True}
RHINO_IN = {"event": "DockSRV", "SRVType": "mev_rhino",
            "SRVType_Localised": "SRV Rhino", "ID": 103}

put("Status.json", {"timestamp": at(0), "event": "Status", "Flags": 1 << 1 | 1 << 21,
                    "Latitude": 12.5, "Longitude": -45.5, "BodyName": "Ega 1",
                    "PlanetRadius": R})
log({"timestamp": at(0), "event": "Fileheader", "part": 1, "gameversion": "4.4.1.1"},
    {"timestamp": at(0), "event": "Commander", "Name": "Jameson", "FID": "F1"},
    {"timestamp": at(0), "event": "Location", "StarSystem": "Ega",
     "SystemAddress": 1234, "StarPos": [1.0, 2.0, 3.0], "Body": "Ega 1"},
    {"timestamp": at(0), "event": "Loadout", "Ship": "panthermkii",
     "CargoCapacity": 256},
    {"timestamp": at(0), "event": "Cargo", "Vessel": "Ship", "Count": 0,
     "Inventory": []})

watcher = JN.JournalWatcher(GAME)
books = S.Earnings(os.path.join(TMP, "books"))


def tick():
    """One pass of the app's poll, with the bookkeeping wired to it."""
    watcher.poll()
    return [books.observe(note) for note in watcher.drain_runs()]


tick()
check("nothing has happened yet, so there is no session", books.current is None)
check("the ship's cargo capacity is read off Loadout",
      watcher.cargo_capacity == 256, watcher.cargo_capacity)

log({"timestamp": at(2), "event": "Touchdown", "StarSystem": "Ega",
     "Body": "Ega 1", "PlayerControlled": True, "OnPlanet": True,
     "OnStation": False, "Latitude": 12.5, "Longitude": -45.5})
tick()
check("touching down is not a session - landing to scan or to look is not "
      "mining", books.current is None, books.current)
log(*refined(3, 0, "Painite", 4))
tick()
check("and a tonne refined with the Rhino still aboard - the ship mining "
      "asteroids writes the same event - is not booked anywhere",
      books.current is None and books.sessions == [], books.sessions)

log(dict(RHINO_OUT, timestamp=at(5)))
lines = tick()
# 1.10031: "The earnings tab is picking up stuff to do with normal hauling
# lets not do that lets have a start session button or a auto start on
# first rig deployment." The Rhino goes out to look and to fetch cargo too.
check("the Rhino leaving the ship is not a session on its own",
      books.current is None and not any(lines), (books.sessions, lines))

log(*(refined(10, 1, "Rhodplumsite", 3) + refined(10, 2, "Ruby", 2)
      + refined(11, 0, "Rhodplumsite", 1)))
lines = tick()
check("the first tonne refined in the Rhino starts the session",
      "Rhino session started - first tonne refined" in lines, lines)
check("on the body the journal named",
      (books.current["system"], books.current["body"]) == ("Ega", "Ega 1"),
      books.current)
check("crediting the commander the journal named, never one typed in",
      books.current["cmdr"] == "Jameson")
check("it is a Rhino session", books.current["kind"] == S.RHINO)
check("and it is on disk the moment it opens, not when it closes",
      os.path.exists(books.path))
check("every tonne refined in the Rhino is counted, three in one second "
      "included", S.unpack_counts(books.current["mined"])
      == {"Rhodplumsite": 4, "Ruby": 2}, books.current["mined"])
check("and none but the first puts a line on screen",
      len([line for line in lines if line]) == 1, lines)
check("it says what opened it, and the Rhino being out is its first trip",
      books.current["started_by"] == "refined" and books.current["trips"] == "1",
      books.current)

log({"timestamp": at(20), "event": "CargoTransfer", "Transfers": [
    {"Type": "rhodplumsite", "Count": 4, "Direction": "toship"},
    {"Type": "ruby", "Count": 2, "Direction": "toship"}]})
lines = tick()
check("a transfer to the ship is counted as moved, not mined again",
      S.unpack_counts(books.current["transferred"])
      == {"Rhodplumsite": 4, "Ruby": 2}
      and S.unpack_counts(books.current["mined"])
      == {"Rhodplumsite": 4, "Ruby": 2}, books.current)
check("and says so, for the ship's hold to be flashed",
      any(line and line.startswith("to ship") for line in lines), lines)
check("the reader moved it into the ship's hold",
      watcher.holds.get("Ship") == {"Rhodplumsite": 4, "Ruby": 2},
      watcher.holds)

log(*refined(25, 0, "Rhodplumsite", 5))
tick()
log(dict(RHINO_IN, timestamp=at(30)))
lines = tick()
check("the Rhino coming back aboard ends the session",
      "Rhino session done" in lines and books.current is None, lines)
done = books.sessions[-1]
check("it ran from the first tonne to the dock",
      (done["started"][:16], done["ended"]) == (at(10)[:16], at(30)),
      (done["started"], done["ended"]))
check("with every tonne in it",
      S.unpack_counts(done["mined"]) == {"Rhodplumsite": 9, "Ruby": 2},
      done["mined"])

log({"timestamp": at(50), "event": "Docked", "StationName": "Reilly Terminal",
     "StationType": "Coriolis", "StarSystem": "Ega", "SystemAddress": 1234,
     "MarketID": 3228883456})
tick()
put("Market.json", {"timestamp": at(50, 5), "event": "Market",
                    "MarketID": 3228883456, "StationName": "Reilly Terminal",
                    "StarSystem": "Ega", "Items": [
                        {"id": 1, "Name": "$magnesite_name;",
                         "Name_Localised": "Magnesite", "BuyPrice": 0,
                         "SellPrice": 38198, "MeanPrice": 38000,
                         "Stock": 0, "Demand": 900, "DemandBracket": 3}]})
tick()
check("the market is picked up for sharing", watcher.pending_market is not None)
watcher.pending_market = None
check("and kept afterwards, so a hold can still be priced against it",
      watcher.market and watcher.market["items"][0]["commodity"] == "Magnesite",
      watcher.market)

log({"timestamp": at(51), "event": "MarketSell", "MarketID": 3228883456,
     "Type": "rhodplumsite", "Count": 9, "SellPrice": 100000,
     "TotalSale": 900000, "AvgPricePaid": 0},
    {"timestamp": at(51), "event": "MarketSell", "MarketID": 3228883456,
     "Type": "ruby", "Count": 2, "SellPrice": 50000,
     "TotalSale": 100000, "AvgPricePaid": 0},
    {"timestamp": at(52), "event": "MarketSell", "MarketID": 3228883456,
     "Type": "tea", "Count": 40, "SellPrice": 1000,
     "TotalSale": 40000, "AvgPricePaid": 900})
tick()
check("what the Rhino dug up, sold, is credited to its session",
      done["credits"] == "1000000", done["credits"])
check("both sales, in one second",
      S.unpack_counts(done["sold"]) == {"Rhodplumsite": 9, "Ruby": 2},
      done["sold"])
check("a trader's Tea is not - it came out of no Rhino session",
      "Tea" not in done["sold"] and len(books.sessions) == 1, books.sessions)
check("and no session opened for it", books.current is None)
check("the station it sold at is on the row",
      (done["station"], done["sold_in"]) == ("Reilly Terminal", "Ega"), done)
check("the drive to the station is not mining time: it still ended at the "
      "dock", done["ended"] == at(30), done["ended"])
check("so the rate is over the mining, ready to read in a spreadsheet",
      abs(int(done["cr_hr"]) - 1000000 / ((20 * 60 - 1) / 3600.0)) <= 1,
      done["cr_hr"])

print("== the files the game rewrites can be caught half-written ==")
hold("Ship", at(54), rhodplumsite=4, ruby=2)
tick()
put("Cargo.json", '{"timestamp": "%s", "event": "Cargo", "Vessel": "Ship", "Inv'
    % at(55))
tick()
# Named in English off the symbol, not left as the raw symbol - and never
# the localised text, which is in whatever language the client runs in.
check("a torn Cargo.json is not an error, it is just this tick",
      watcher.cargo == {"Rhodplumsite": 4, "Ruby": 2}, watcher.cargo)
put("Market.json", '{"timestamp": "x", "Items": [{"Name": "$magn')
tick()
check("and neither is a torn Market.json",
      watcher.market["station"] == "Reilly Terminal", watcher.market)
put("Cargo.json", "")
tick()
check("an empty one is the same story", watcher.cargo != {})


def now_at(minutes_ago):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ",
                         time.gmtime(time.time() - minutes_ago * 60))


print("== a restart replays the journal, and the books must not pay twice ==")
# Every start of the app reads the current journal from the top. Without
# remembering how far they had got, the books booked a sale twice and the
# three tonnes refined inside one second came back as three more.
AGAIN = os.path.join(TMP, "again"); os.makedirs(AGAIN)
AGAIN_BOOKS = os.path.join(TMP, "againbooks")
_same_second = now_at(25)
with open(os.path.join(AGAIN, "Journal.2026-09-17T180000.01.log"), "w",
          encoding="utf-8") as fh:
    for _event in ([dict(RHINO_OUT, timestamp=now_at(40))]
                   + [{"timestamp": _same_second, "event": "MiningRefined",
                       "Type": "$gold_name;", "Type_Localised": "Gold"}] * 3
                   + [{"timestamp": now_at(24), "event": "MiningRefined",
                       "Type": "$silver_name;", "Type_Localised": "Silver"}] * 2
                   + [dict(RHINO_IN, timestamp=now_at(22)),
                      {"timestamp": now_at(20), "event": "Docked",
                       "StationName": "Reilly", "StarSystem": "Ega"},
                      {"timestamp": now_at(15), "event": "MarketSell",
                       "Type": "gold", "Count": 3, "SellPrice": 1000,
                       "TotalSale": 3000, "AvgPricePaid": 0},
                      {"timestamp": now_at(15), "event": "MarketSell",
                       "Type": "silver", "Count": 2, "SellPrice": 500,
                       "TotalSale": 1000, "AvgPricePaid": 0}]):
        fh.write(_json.dumps(_event) + "\n")


def restart():
    reader = JN.JournalWatcher(AGAIN)
    ledger = S.Earnings(AGAIN_BOOKS)
    reader.poll()
    for _note in reader.drain_runs():
        ledger.observe(_note)
    return reader, ledger


_reader, first = restart()
check("three tonnes in one second are three tonnes",
      (first.sessions[-1]["mined"], first.sessions[-1]["credits"])
      == ("Gold:3;Silver:2", "4000"),
      (first.sessions[-1]["mined"], first.sessions[-1]["credits"]))
_reader, second = restart()
check("restarting the app books none of it again",
      [(r["mined"], r["credits"]) for r in second.sessions]
      == [("Gold:3;Silver:2", "4000")],
      [(r["mined"], r["credits"]) for r in second.sessions])
check("and still knows the ship is on the pad", second._docked)
check("and that the Rhino is aboard", second._in_rhino is False)
os.makedirs(os.path.join(TMP, "future"))
_future = S.Earnings(os.path.join(TMP, "future"))
with open(_future.seen_path, "w", encoding="utf-8") as fh:
    _json.dump({"at": S._epoch("2099-01-01T00:00:00Z"), "keys": []}, fh)
_future = S.Earnings(os.path.join(TMP, "future"))
check("a mark from the future is ignored rather than stopping the books",
      _future._seen_at == 0, _future._seen_at)

print("== logging in sitting in the Rhino carries the session on ==")
# His own journal: a relog halfway through a session starts a new journal
# with a Location that says InSRV. The launch is in the last file, which a
# freshly started app never reads.
RELOG = os.path.join(TMP, "relog"); os.makedirs(RELOG)
with open(os.path.join(RELOG, "Journal.2026-09-17T190000.01.log"), "w",
          encoding="utf-8") as fh:
    for _event in [{"timestamp": now_at(30), "event": "Location",
                    "StarSystem": "Ega", "Body": "Ega 1", "Docked": False,
                    "Latitude": 12.5, "Longitude": -45.5, "InSRV": True}] + \
            [{"timestamp": now_at(29), "event": "MiningRefined",
              "Type": "$ruby_name;", "Type_Localised": "Ruby"}] * 2:
        fh.write(_json.dumps(_event) + "\n")
relog_reader = JN.JournalWatcher(RELOG)
relog_books = S.Earnings(os.path.join(TMP, "relog-books"))
relog_reader.poll()
relog_lines = [relog_books.observe(n) for n in relog_reader.drain_runs()]
check("a session is picked up from the login",
      relog_books.current is not None and relog_books.current["kind"] == S.RHINO,
      relog_books.sessions)
check("and the tonnes after it are counted",
      relog_books.current["mined"] == "Ruby:2", relog_books.current)
_login_elsewhere = S.Earnings(os.path.join(TMP, "relog-ship"))
_login_elsewhere.observe({"event": "Location", "when": now_at(5),
                          "landed": True, "in_srv": False, "system": "Ega",
                          "body": "Ega 1"})
check("logging in in the ship on the ground is not a session",
      _login_elsewhere.current is None)

print("== multi-session: one session across trips to a station ==")
multi = S.Earnings(os.path.join(TMP, "multi"))
multi.multi = True


def saw(ledger, event, **note):
    return ledger.observe(dict(note, event=event))


saw(multi, "SRVLaunch", when=at(0), rhino=True, system="Ega", body="Ega 1")
saw(multi, "Refined", when=at(1), commodity="Painite", n=1, system="Ega",
    body="Ega 1")
saw(multi, "SRVDock", when=at(10))
check("with the box ticked, the Rhino coming aboard does not end it",
      multi.current is not None, multi.sessions)
saw(multi, "Docked", when=at(40), station="Reilly", system="Ega")
saw(multi, "MarketSell", when=at(41), commodity="painite", count=1,
    total=500000, station="Reilly", system="Ega")
saw(multi, "SRVLaunch", when=at(70), rhino=True, system="Ega", body="Ega 1")
saw(multi, "Refined", when=at(71), commodity="Painite", n=1)
check("the flight, the sale and the next trip are all one session",
      len(multi.sessions) == 1 and multi.current["trips"] == "2"
      and multi.current["mined"] == "Painite:2"
      and multi.current["credits"] == "500000", multi.sessions)
check("and its time runs across the lot",
      multi.current["ended"] == at(71), multi.current["ended"])
multi.multi = False
saw(multi, "SRVDock", when=at(80))
check("unticked, the next time the Rhino comes aboard ends it",
      multi.current is None and len(multi.sessions) == 1, multi.sessions)

print("== what starts a session, and what only looks like it does ==")
policy = S.Earnings(os.path.join(TMP, "policy"))
saw(policy, "SRVLaunch", when=at(0), rhino=False, system="Ega", body="Ega 1")
check("a Scarab going out is not a Rhino session", policy.current is None)
saw(policy, "SRVLaunch", when=at(1), rhino=True, system="Ega", body="Ega 1")
check("nor is the Rhino going out, on its own", policy.current is None)
check("the first rig down is", saw(policy, "RigDown", when=at(1), rig=1,
                                   system="Ega", body="Ega 1")
      == "Rhino session started - first rig down"
      and policy.current["started_by"] == "rigs")
first = policy.current
saw(policy, "SRVLaunch", when=at(2), rhino=True, system="Ega", body="Ega 1")
check("a second launch on the same body with the first still open carries "
      "it on", policy.current is first and first["trips"] == "2", first)
saw(policy, "SRVLaunch", when=at(3), rhino=True, system="Ega", body="Ega 5")
check("out on another body it banks the last one and waits for the next "
      "rig or tonne", policy.current is None and first["closed"]
      and first["ended_by"] == "moved", policy.sessions)
saw(policy, "RigDown", when=at(3), rig=1, system="Ega", body="Ega 5")
check("which opens the next",
      len(policy.sessions) == 2 and policy.current is not first, policy.sessions)
saw(policy, "SRVLost", when=at(4))
check("losing the Rhino ends it too, and says so",
      policy.current is None and "lost" in policy.sessions[-1]["notes"],
      policy.sessions[-1])
saw(policy, "MarketSell", when=at(5), commodity="gold", count=5, total=5)
check("a sale of something no session dug up opens nothing",
      policy.current is None and len(policy.sessions) == 2)

print("== a sale goes against the session that dug it up, newest first ==")
split = S.Earnings(os.path.join(TMP, "split"))
saw(split, "SRVLaunch", when=at(0), rhino=True, system="Ega", body="Ega 1")
for _n in range(3):
    saw(split, "Refined", when=at(1), commodity="Gold", n=_n + 1)
saw(split, "SRVDock", when=at(5))
saw(split, "SRVLaunch", when=at(10), rhino=True, system="Ega", body="Ega 1")
for _n in range(2):
    saw(split, "Refined", when=at(11), commodity="Gold", n=_n + 1)
saw(split, "SRVDock", when=at(15))
saw(split, "MarketSell", when=at(30), commodity="gold", count=4, total=4000)
check("the newest session is filled first, the rest goes to the one before",
      [r["sold"] for r in split.sessions] == ["Gold:2", "Gold:2"]
      and [r["credits"] for r in split.sessions] == ["2000", "2000"],
      [(r["sold"], r["credits"]) for r in split.sessions])
saw(split, "MarketSell", when=at(31), commodity="gold", count=9, total=9000)
check("and nothing is sold twice: only the one tonne left is booked",
      [r["sold"] for r in split.sessions] == ["Gold:3", "Gold:2"],
      [r["sold"] for r in split.sessions])

print("== a session that goes quiet is over, and ended when it went quiet ==")
quiet = S.Earnings(os.path.join(TMP, "quiet"))
saw(quiet, "RigDown", when="2026-09-10T10:00:00Z", rig=1,
    system="Ega", body="Ega 1")
abandoned = quiet.current
saw(quiet, "RigDown", when="2026-09-17T10:00:00Z", rig=1,
    system="Ega", body="Ega 1")
check("a week later, the old session is not still collecting",
      abandoned["closed"] != "" and quiet.current is not abandoned)
check("and it ended when it last did something, not a week afterwards",
      abandoned["ended"] == "2026-09-10T10:00:00Z", abandoned["ended"])
check("with a note saying why", "quiet" in abandoned["notes"], abandoned["notes"])
saw(quiet, "Shutdown", when="2026-09-17T11:00:00Z")
check("quitting the game does not end a session - a relog carries it on",
      quiet.current is not None)

print("== it survives a restart, and an older file ==")
again = S.Earnings(books.folder)
check("every session came back", len(again.sessions) == len(books.sessions))
check("with the credits intact",
      [r["credits"] for r in again.sessions] == [r["credits"] for r in books.sessions])
check("and the rate still agrees with the timestamps it was worked out from",
      all(int(r["cr_hr"]) == round(S.credits_per_hour(r)) for r in again.sessions),
      [(r["cr_hr"], S.credits_per_hour(r)) for r in again.sessions])
check("a backup of the previous file is kept, as everywhere else here",
      os.path.exists(books.path + ".bak"))
check("and they add up", again.totals(again.recent())["credits"] == 1000000.0,
      again.totals())
check("totalling what came out of the ground across every session",
      again.totals(again.recent())["mined"] == {"Rhodplumsite": 9, "Ruby": 2},
      again.totals()["mined"])

# The realistic migration: rows an older build wrote, a run for every
# landing and every sale. Kept in the file, never shown or added up.
thin = os.path.join(TMP, "thin"); os.makedirs(thin)
with open(os.path.join(thin, "sessions.csv"), "w", encoding="utf-8", newline="") as fh:
    _w = csv.writer(fh)
    _w.writerow(["id", "started", "ended", "closed", "system", "body", "credits"])
    _w.writerow(["abc", at(0), at(60), at(60), "Ega", "Ega 1", "50000"])
older = S.Earnings(thin)
check("a file written before the later columns existed still loads",
      len(older.sessions) == 1 and older.sessions[0]["credits"] == "50000")
check("the missing columns read as blank rather than missing",
      set(older.sessions[0]) == set(S.SESSION_FIELDS))
check("and nothing in it looks live", older.current is None)
check("its old runs are kept but not shown - the tab is Rhino sessions only",
      older.recent() == [] and len(older.recent(rhino_only=False)) == 1)
older.save()
check("saving it back gives it the full set of columns",
      open(os.path.join(thin, "sessions.csv"), encoding="utf-8"
           ).readline().strip().split(",") == S.SESSION_FIELDS)

# Two rows left open at once cannot both be current, and the older one would
# otherwise sit there looking live for the rest of the file's life.
stranded = os.path.join(TMP, "stranded"); os.makedirs(stranded)
with open(os.path.join(stranded, "sessions.csv"), "w", encoding="utf-8", newline="") as fh:
    _w = csv.DictWriter(fh, fieldnames=S.SESSION_FIELDS)
    _w.writeheader()
    for _n in (1, 2):
        _row = {k: "" for k in S.SESSION_FIELDS}
        _row.update({"id": "row%d" % _n, "started": S.utc_now(),
                     "ended": S.utc_now(), "credits": "10"})
        _w.writerow(_row)
tidied = S.Earnings(stranded)
check("only the last run can still be running",
      [bool(r["closed"]) for r in tidied.sessions] == [True, False],
      [r["closed"] for r in tidied.sessions])
saw(tidied, "RigDown", when=S.utc_now(), rig=1, system="Ega",
    body="Ega 1")
check("and a run an older build left open is closed, not carried on, when "
      "the Rhino next goes out", tidied.sessions[1]["closed"]
      and tidied.current["kind"] == S.RHINO, tidied.sessions)

print("== the reader still keeps both holds, in English ==")


def holds_case(folder, events, cargo_json):
    os.makedirs(folder)
    with open(os.path.join(folder, "Journal.2026-09-17T180000.01.log"), "w",
              encoding="utf-8") as fh:
        for _event in events:
            fh.write(_json.dumps(_event) + "\n")
    if cargo_json is not None:
        with open(os.path.join(folder, "Cargo.json"), "w",
                  encoding="utf-8") as fh:
            fh.write(_json.dumps(cargo_json))
    reader = JN.JournalWatcher(folder)
    reader.poll()
    return reader


reader = holds_case(
    os.path.join(TMP, "aboard"),
    [{"timestamp": now_at(30), "event": "Fileheader", "part": 1},
     {"timestamp": now_at(30), "event": "Location", "StarSystem": "Ega",
      "Body": "Ega 1", "Docked": False, "Latitude": 12.5, "Longitude": -45.5,
      "InSRV": True},
     {"timestamp": now_at(29), "event": "Cargo", "Vessel": "Ship", "Count": 32,
      "Inventory": [{"Name": "haematite", "Name_Localised": "Hématite",
                     "Count": 30, "Stolen": 0},
                    {"Name": "tea", "Name_Localised": "Thé", "Count": 2,
                     "Stolen": 0}]},
     {"timestamp": now_at(10), "event": "CargoTransfer", "Transfers": [
         {"Type": "water", "Count": 4, "Direction": "toship"}]}],
    {"timestamp": now_at(5), "event": "Cargo", "Vessel": "SRV", "Count": 6,
     "Inventory": [{"Name": "water", "Name_Localised": "Eau", "Count": 6,
                    "Stolen": 0}]})
check("both holds are known, the ship's from the journal and the SRV's from "
      "Cargo.json", reader.holds == {"Ship": {"Haematite": 30, "Tea": 2,
                                              "Water": 4},
                                     "SRV": {"Water": 6}}, reader.holds)
check("and named in English whatever the client's language",
      reader.cargo == {"Water": 6}, reader.cargo)

print("== a transfer banked while catching up cannot swallow a real gain ==")
STALE = os.path.join(TMP, "stale"); os.makedirs(STALE)
with open(os.path.join(STALE, "Journal.2026-09-17T180000.01.log"), "w",
          encoding="utf-8") as fh:
    fh.write(_json.dumps({"timestamp": now_at(20), "event": "CargoTransfer",
                          "Transfers": [{"Type": "haematite", "Count": 20,
                                         "Direction": "tosrv"}]}) + "\n")


def srv_hold(count, minutes_ago):
    with open(os.path.join(STALE, "Cargo.json"), "w", encoding="utf-8") as fh:
        fh.write(_json.dumps({"timestamp": now_at(minutes_ago), "event": "Cargo",
                              "Vessel": "SRV", "Count": count,
                              "Inventory": [{"Name": "haematite",
                                             "Count": count, "Stolen": 0}]}))


srv_hold(20, 15)
stale_reader = JN.JournalWatcher(STALE)
stale_reader.poll()
stale_reader.drain_runs()
srv_hold(32, 1)
stale_reader.poll()
_gains = [n.get("gained") for n in stale_reader.drain_runs()
          if n.get("event") == "Cargo"]
check("twelve tonnes arriving after the app started are twelve tonnes",
      _gains == [{"Haematite": 12}], _gains)

print("== a market in any language prices the hold ==")
FRENCH_MARKET = {"timestamp": at(1), "event": "Market", "MarketID": 1,
                 "StationName": "Reilly", "StarSystem": "Ega", "Items": [
                     {"Name": "$sapphire_name;", "Name_Localised": "Saphir",
                      "SellPrice": 127000, "BuyPrice": 0, "Demand": 50,
                      "Stock": 0},
                     {"Name": "$haematite_name;",
                      "Name_Localised": "Hématite", "SellPrice": 2800,
                      "BuyPrice": 0, "Demand": 50, "Stock": 0},
                     {"Name": "$water_name;", "Name_Localised": "Eau",
                      "SellPrice": 500, "BuyPrice": 0, "Demand": 50,
                      "Stock": 0}]}
shared = EDO.parse_market(FRENCH_MARKET)
check("a French client's Sapphire is shared as Sapphire",
      [row["commodity"] for row in shared.get("items", [])] == ["Sapphire"],
      shared)
whole_market = EDO.parse_market(FRENCH_MARKET, only_surface=False,
                                namer=S.english_name)
check("and the whole market is kept in English for pricing the hold",
      sorted(row["commodity"] for row in whole_market["items"])
      == ["Haematite", "Sapphire", "Water"], whole_market)
check("so a hold of Haematite and Water is worth something",
      S.hold_value({"Haematite": 10, "Water": 4},
                   {row["commodity"]: row["sell"]
                    for row in whole_market["items"]}) == 30000.0)
_sale = JN.JournalWatcher(os.path.join(TMP, "books"))
_sale._note_run("MarketSell", {"timestamp": at(0), "Type": "water",
                               "Type_Localised": "Eau", "Count": 1,
                               "SellPrice": 500, "TotalSale": 500})
check("and a sale off a French client is booked as Water, not Eau",
      _sale.pending_runs[-1]["commodity"] == "Water", _sale.pending_runs[-1])


print("== the reader's queue cannot grow without bound ==")
# Nothing in the app drains this yet. An unbounded list in a process that
# runs for an eight-hour session is a leak, not a detail.
flood = JN.JournalWatcher(GAME)
for _n in range(JN.RUN_QUEUE_MAX + 50):
    flood._queue_run({"event": "Docked", "when": at(0), "n": _n})
check("it is capped", len(flood.pending_runs) == JN.RUN_QUEUE_MAX,
      len(flood.pending_runs))
check("and it is the oldest that go, not the newest",
      flood.pending_runs[-1]["n"] == JN.RUN_QUEUE_MAX + 49)
check("draining it hands everything over exactly once",
      len(flood.drain_runs()) == JN.RUN_QUEUE_MAX and flood.pending_runs == [])

print("== moving cargo to a carrier is not moving it to the ship ==")
carrier = JN.JournalWatcher(GAME)
carrier._credit_transfer({"Transfers": [
    {"Type": "gold", "Count": 5, "Direction": "tocarrier"},
    {"Type": "silver", "Count": 7, "Direction": "toship"},
    {"Type": "iron", "Count": 2, "Direction": "TOSRV"}]})
check("only what arrives somewhere we watch is credited",
      carrier._transfer_credit == {"Ship": {"silver": 7}, "SRV": {"iron": 2}},
      carrier._transfer_credit)

print("== the reader says what the game did and judges none of it ==")
land = JN.JournalWatcher(GAME)
land._note_run("Touchdown", {"timestamp": at(0), "PlayerControlled": False,
                             "OnStation": True})
check("a landing on a pad is passed on as one",
      land.pending_runs[-1]["on_station"] is True, land.pending_runs[-1])
check("and so is a ship that put itself down",
      land.pending_runs[-1]["player"] is False, land.pending_runs[-1])
land._note_run("Touchdown", {"timestamp": at(0), "Latitude": 1.0})
check("a touchdown that says neither was flown by the commander onto a body",
      land.pending_runs[-1]["player"] is True
      and land.pending_runs[-1]["on_station"] is False, land.pending_runs[-1])

land._note_run("Docked", {"timestamp": at(0), "StationName": "Reilly Terminal",
                          "StarSystem": "Ega"})
check("docking remembers the station, so a sale knows where it happened",
      (land.docked, land.station) == (True, "Reilly Terminal"))
land._note_run("MarketSell", {"timestamp": at(0), "Type": "gold", "Count": 1,
                              "TotalSale": 9})
check("and the sale carries it", land.pending_runs[-1]["station"] == "Reilly Terminal")
land._note_run("Undocked", {"timestamp": at(0), "StationName": "Reilly Terminal"})
check("leaving forgets it again", (land.docked, land.station) == (False, ""))

print("== a sale with no total still counts ==")
sale = JN.JournalWatcher(GAME)
sale._note_run("MarketSell", {"timestamp": at(0), "Type": "gold",
                              "Count": 4, "SellPrice": 50})
check("count times price stands in when TotalSale is missing",
      sale.pending_runs[-1]["total"] == 200, sale.pending_runs[-1])
sale._note_run("MarketSell", {"timestamp": at(0), "Type": "gold", "Count": 4,
                              "SellPrice": 50, "TotalSale": 210})
check("but the game's own figure wins where there is one",
      sale.pending_runs[-1]["total"] == 210)
check("a localised name is preferred to the symbol",
      (sale._note_run("MarketSell", {"Type": "lowtemperaturediamond",
                                     "Type_Localised": "Low Temperature Diamonds",
                                     "Count": 1, "TotalSale": 1})
       or sale.pending_runs[-1]["commodity"]) == "Low Temperature Diamonds")
check("and either spelling lands on the same commodity",
      S.canonical("lowtemperaturediamond") == "Low Temperature Diamonds",
      S.canonical("lowtemperaturediamond"))
check("nulls where numbers should be do not lose the sale",
      JN.whole(None) == 0 and JN.whole("12") == 12 and JN.whole("x") == 0)


print("== a browser-check page is named, not reported as a broken server ==")
import edonline as EDO
# A web front end can answer with an "are you a browser?" page instead of the
# API. A desktop app has no JavaScript, so it can never pass one - it just gets
# a 403 or a page of HTML. Without this the commander sees "HTTP 403" or a
# JSON parse error and reports "Find is broken".
import io as _io, urllib.error as _uerr
_CHALLENGE = ("<!DOCTYPE html><html><head><title>Just a moment...</title>"
              "<script>window._cf_chl_opt={cType:'managed'};</script>"
              "<script src='https://challenges.example/x'></script>")

check("the interstitial is recognised", EDO._challenged(_CHALLENGE))
check("and so is the header form", EDO._challenged("cf-mitigated: challenge"))
check("an ordinary page is not mistaken for one",
      not EDO._challenged("<html><body>404 not found</body></html>"))
check("nor is real JSON", not EDO._challenged('{"count": 0, "sites": []}'))
check("nor an empty body", not EDO._challenged("") and not EDO._challenged(None))

def _message(fn):
    """What the commander would actually see on the status line."""
    try:
        fn()
    except Exception as exc:
        return "%s: %s" % (type(exc).__name__, exc) if not isinstance(
            exc, RuntimeError) else str(exc)
    return ""


def _raises_challenge(fn):
    try:
        fn()
    except RuntimeError as exc:
        return str(exc) == EDO.CHALLENGE_SAYS
    except Exception:
        return False
    return False

_real_open = EDO.urllib.request.urlopen
def _serve(status, body, as_error=True):
    def opener(request, timeout=None):
        if as_error:
            raise _uerr.HTTPError(request.full_url, status, "blocked", {},
                                  _io.BytesIO(body.encode()))
        class R:
            def read(self_inner): return body.encode()
            def __enter__(self_inner): return self_inner
            def __exit__(self_inner, *a): return False
        return R()
    return opener

try:
    EDO.urllib.request.urlopen = _serve(403, _CHALLENGE)
    check("a challenged 403 says what happened, not 'HTTP 403'",
          _raises_challenge(lambda: EDO.get_json("https://example.invalid/x")))
    EDO.urllib.request.urlopen = _serve(503, _CHALLENGE)
    check("and so does a challenged 503",
          _raises_challenge(lambda: EDO.get_json("https://example.invalid/x")))
    # A challenge can arrive 200 OK with a page of HTML, where json.loads
    # would call it malformed data from the server.
    EDO.urllib.request.urlopen = _serve(200, _CHALLENGE, as_error=False)
    check("a challenge served as 200 HTML is caught before the JSON parser",
          _raises_challenge(lambda: EDO.get_json("https://example.invalid/x")))
    # An ordinary failure must still read as an ordinary failure - and as a
    # sentence. A bare HTTPError used to escape to the status line as
    # "HTTP 500", which is a number, not an answer.
    EDO.urllib.request.urlopen = _serve(500, "upstream exploded")
    _said = _message(lambda: EDO.get_json("https://example.invalid/x"))
    check("a real server error is still a real server error, not a check page",
          "500" in _said and _said != EDO.CHALLENGE_SAYS, _said)
    check("and it says whose end the trouble is at", "EDSMT" in _said, _said)
    EDO.urllib.request.urlopen = _serve(200, '{"ok": true}', as_error=False)
    check("and a good answer still comes back parsed",
          EDO.get_json("https://example.invalid/x") == {"ok": True})
finally:
    EDO.urllib.request.urlopen = _real_open

print("== no reply ever reaches the commander as a parser error ==")
# "Inara key: Expecting value: line 1 column 1 (char 0)" - reported against
# 1.10025, on the status line, reading exactly like a bad key. It was
# json.loads on a body that was not JSON. post_json had none of the
# body-reading get_json had been given, so every non-JSON reply from Inara
# arrived as a sentence about a parser.
_BAD = [
    ("an empty body", 200, "", ("nothing back",)),
    ("a maintenance page", 200, "<html><body>back soon</body></html>",
     ("web page",)),
    ("a body that is not JSON at all", 200, "upstream exploded",
     ("not JSON",)),
    ("a top-level array", 200, "[1,2,3]", ("object was expected",)),
    ("a 503", 503, "<html>down</html>", ("503",)),
    ("a 403", 403, "no", ("403",)),
    ("an Inara refusal with a reason", 400,
     '{"header": {"eventStatus": 400, "eventStatusText": "Invalid API key"}}',
     ("Invalid API key",)),
]
try:
    for _label, _status, _body, _wanted in _BAD:
        EDO.urllib.request.urlopen = _serve(_status, _body,
                                            as_error=_status >= 400)
        for _fn, _name in ((lambda: EDO.post_json("https://inara.cz/inapi/v1", {}),
                            "post_json"),
                           (lambda: EDO.get_json("https://inara.cz/inapi/v1"),
                            "get_json")):
            _said = _message(_fn)
            check("%s turns %s into a sentence" % (_name, _label),
                  all(w in _said for w in _wanted), _said)
            check("%s never leaks the parser for %s" % (_name, _label),
                  "line 1 column 1" not in _said
                  and "Expecting value" not in _said, _said)
            check("%s names the host for %s" % (_name, _label),
                  "inara.cz" in _said or _said == EDO.CHALLENGE_SAYS, _said)
    # And the good case is untouched.
    EDO.urllib.request.urlopen = _serve(
        200, '{"header": {"eventStatus": 200}, "events": []}', as_error=False)
    check("a good POST still comes back parsed",
          EDO.post_json("https://inara.cz/inapi/v1", {})
          == {"header": {"eventStatus": 200}, "events": []})
    # A host that will not resolve is not a parser problem either.
    def _unreachable(request, timeout=None):
        raise _uerr.URLError("nodename nor servname provided")
    EDO.urllib.request.urlopen = _unreachable
    for _fn, _name in ((lambda: EDO.post_json("https://inara.cz/inapi/v1", {}),
                        "post_json"),
                       (lambda: EDO.get_json("https://inara.cz/inapi/v1"),
                        "get_json")):
        _said = _message(_fn)
        check("%s says it could not reach the host" % _name,
              "could not reach" in _said and "inara.cz" in _said, _said)
finally:
    EDO.urllib.request.urlopen = _real_open

check("the message tells them it is not their settings and not the app",
      "nothing is wrong" in EDO.CHALLENGE_SAYS.lower())
# It is shown to every commander. It says what to do, and nothing about how
# any server is set up or which company's product is in front of it.
check("and names no vendor or setting",
      not [w for w in ("fight mode", "waf", "origin")
           if w in EDO.CHALLENGE_SAYS.lower()], EDO.CHALLENGE_SAYS)
check("and names who has to fix it",
      "server" in EDO.CHALLENGE_SAYS.lower())

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fails else 0)
