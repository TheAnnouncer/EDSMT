"""The community API.

Skipped, not failed, when FastAPI is not installed. The API is a separate
thing that runs on the server and has its own server/requirements.txt; a
machine building the Windows app has no reason to carry it, and failing the
build over a library the app does not use would be nonsense.

    pip install -r server/requirements.txt     to run these
"""
import os, sys, json, sqlite3, tempfile, time, datetime as dt

try:
    import fastapi  # noqa
    import httpx    # noqa  - the test client needs it
except ImportError as missing:
    print("  SKIP  the API tests need FastAPI, which is not installed here")
    print("        (%s)" % missing)
    print("        pip install -r server/requirements.txt")
    raise SystemExit(0)

TMP = tempfile.mkdtemp(prefix="rrsrv-")
DB = os.path.join(TMP, "deposits.db")

# --- build an older database first, to prove migration works --------------
old = sqlite3.connect(DB)
old.executescript("""
CREATE TABLE deposits (
    id INTEGER PRIMARY KEY, system TEXT NOT NULL COLLATE NOCASE,
    planet TEXT NOT NULL COLLATE NOCASE, spot TEXT NOT NULL COLLATE NOCASE,
    type TEXT NOT NULL COLLATE NOCASE, rigs INTEGER NOT NULL,
    direction REAL NOT NULL, distance REAL NOT NULL, lat REAL, lon REAL,
    notes TEXT DEFAULT '', uploader TEXT DEFAULT '', software TEXT DEFAULT '',
    created TEXT NOT NULL, fingerprint TEXT NOT NULL UNIQUE);
""")
LEGACY_AGE_DAYS = 38
_legacy_stamp = (dt.datetime.now(dt.timezone.utc)
                 - dt.timedelta(days=LEGACY_AGE_DAYS)).isoformat()
old.execute("""INSERT INTO deposits (system,planet,spot,type,rigs,direction,distance,
               created,fingerprint) VALUES ('Legacy','L 1','1','Ruby',3,10,0.4,
               ?,'legacy|1')""", (_legacy_stamp,))
old.commit(); old.close()

os.environ["RR_DB"] = DB
os.environ["RR_WRITE_TOKEN"] = ""
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server"))
import main  # noqa
from fastapi.testclient import TestClient
client = TestClient(main.app)

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)

def iso(days_ago=0):
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_ago)).isoformat()

print("== migration from an older database ==")
cols = {r[1] for r in sqlite3.connect(DB).execute("PRAGMA table_info(deposits)")}
check("density column added", "density" in cols)
check("temperature_k column added", "temperature_k" in cols)
check("legacy row survived",
      sqlite3.connect(DB).execute("SELECT COUNT(*) FROM deposits").fetchone()[0] == 1)
check("legacy site backfilled into sites",
      sqlite3.connect(DB).execute("SELECT COUNT(*) FROM sites").fetchone()[0] == 1)

print("== health ==")
h = client.get("/v1/health").json()
check("ok", h["ok"] is True)
# Pinned to the module rather than a literal: a version bump is not
# a test failure, but a version the API does not report is.
check("reports its own version", h["version"] == main.APP_VERSION,
      h.get("version"))
# Health is public. It says it is up, which build, and how much is in it -
# not how the ranking is tuned or where else the server gets data from.
check("health says nothing about how the server is tuned",
      not [k for k in h if "half_life" in k or "doubt" in k
           or "sell" in k or "estimate" in k], sorted(h))

print("== upload ==")
def env(deposits):
    return {"$schema": "radioraxxla/surfacemining/1",
            "header": {"uploaderID": "Jameson", "softwareName": "EDSMT",
                       "softwareVersion": main.APP_VERSION, "gatewayTimestamp": iso()},
            "message": {"deposits": deposits}}

base = {"system": "Col 285", "planet": "A 3", "spot": "1", "rigs": 4,
        "direction": 12.0, "distance": 0.30, "lat": 1.0, "lon": 2.0}
r = client.post("/v1/deposits", json=env([
    {**base, "type": "Magnesite", "density": "High", "temperature_k": 214.5},
    {**base, "type": "Olivine", "direction": 100.0, "distance": 0.31, "density": "Pristine"},
    {**base, "type": "Bastnasite", "direction": 200.0, "distance": 0.32, "density": "Low"},
]))
check("accepted 3", r.json()["accepted"] == 3, r.json())
r2 = client.post("/v1/deposits", json=env([{**base, "type": "Magnesite", "density": "High"}]))
check("duplicate detected", r2.json()["duplicates"] == 1, r2.json())

print("== the Bastnasite fold ==")
row = sqlite3.connect(DB).execute(
    "SELECT type FROM deposits WHERE direction=200.0").fetchone()[0]
check("stored under Frontier's spelling", row == "Bastnäsite", row)
found = client.get("/v1/deposits", params={"commodity": "Bastnäsite"}).json()
check("searchable by umlaut spelling", found["count"] == 1, found["count"])
found2 = client.get("/v1/deposits", params={"commodity": "bastnasite"}).json()
check("searchable by plain spelling too", found2["count"] == 1, found2["count"])
check("density returned", found["deposits"][0]["density"] == "Low")

print("== validation ==")
ok = client.post("/v1/deposits", json=env([{**base, "type": "Haematite",
                                            "direction": 33.0}]))
check("a commodity the patch notes never listed is accepted",
      ok.status_code == 200 and ok.json()["accepted"] == 1, ok.json())
ok2 = client.post("/v1/deposits", json=env([{**base, "type": "unobtainium",
                                             "direction": 44.0}]))
check("something nobody has catalogued is accepted and tidied",
      ok2.status_code == 200, ok2.status_code)
import sqlite3 as _s3
check("stored title-cased",
      _s3.connect(DB).execute(
          "SELECT type FROM deposits WHERE direction=44.0").fetchone()[0] == "Unobtainium")
bad = client.post("/v1/deposits", json=env([{**base, "type": "x" * 80}]))
check("obvious rubbish is still refused", bad.status_code == 422, bad.status_code)
bad2 = client.post("/v1/deposits", json=env([{**base, "type": "Ruby", "rigs": 9}]))
check("7+ rigs rejected (Rhino carries 6)", bad2.status_code == 422, bad2.status_code)
zero = client.post("/v1/deposits", json=env([{**base, "type": "Ruby", "rigs": 0,
                                              "direction": 55.0}]))
check("rigs 0 accepted - unknown until you get there",
      zero.status_code == 200, zero.status_code)
bad3 = client.post("/v1/deposits", json=env([{**base, "type": "Ruby", "direction": 400}]))
check("bearing over 360 rejected", bad3.status_code == 422, bad3.status_code)

print("== sites ranking ==")
s = client.get("/v1/sites").json()["sites"]
check("both sites listed", len(s) == 2, len(s))
top = s[0]
check("overlap site ranks first", top["system"] == "Col 285", top["system"])
check("distinct types counted", top["distinct_types"] == 6, top["distinct_types"])
check("types deduped and tidied",
      sorted(top["types"]) == ["Bastnäsite", "Haematite", "Magnesite",
                               "Olivine", "Ruby", "Unobtainium"], top["types"])
check("mean density computed", top["density"] is not None, top["density"])
check("temperature averaged", top["temperature_k"] == 214.5, top["temperature_k"])
check("fresh site keeps its value", top["freshness"] > 0.99, top["freshness"])
legacy = [x for x in s if x["system"] == "Legacy"][0]
check("%d-day-old legacy site decayed" % LEGACY_AGE_DAYS,
      legacy["freshness"] < 0.35, legacy["freshness"])
check("fresh overlap beats stale single", top["score"] > legacy["score"])

print("== filters ==")
check("min_types=3 keeps only the overlap site",
      client.get("/v1/sites", params={"min_types": 3}).json()["count"] == 1)
check("overlap counting survives uncatalogued commodities",
      "Unobtainium" in client.get("/v1/sites").json()["sites"][0]["types"])
check("min_types=7 keeps none",
      client.get("/v1/sites", params={"min_types": 7}).json()["count"] == 0)
check("min_rigs filter works",
      client.get("/v1/sites", params={"min_rigs": 12}).json()["count"] == 1)
check("max_age_days drops the stale one",
      client.get("/v1/sites", params={"max_age_days": 7}).json()["count"] == 1)
check("commodity filter",
      client.get("/v1/sites", params={"commodity": "Olivine"}).json()["count"] == 1)

print("== identity is the position, not a centre ==")
# The bug this exists to stop: the app used to send direction 0 / distance 0
# because there is no spot centre any more, so two different deposits of the
# same commodity at the same site hashed identically and the second was
# thrown away as a duplicate.
site = {"system": "Ega", "planet": "Ega 1", "spot": "3", "type": "Haematite",
        "rigs": 6}
r = client.post("/v1/deposits", json=env([
    dict(site, lat=12.5000, lon=-45.5000),
    dict(site, lat=12.5080, lon=-45.4900),      # ~900 m away, a real second find
    dict(site, lat=12.5210, lon=-45.4700)]))
check("three deposits of one commodity at one site all stored",
      r.json()["accepted"] == 3, r.json())

r = client.post("/v1/deposits", json=env([dict(site, lat=12.5001, lon=-45.5002)]))
check("the same deposit reported again is a duplicate",
      r.json()["duplicates"] == 1, r.json())

r = client.post("/v1/deposits", json=env([
    dict(site, type="Copper", lat=12.5000, lon=-45.5000)]))
check("a different commodity in the same spot is its own deposit",
      r.json()["accepted"] == 1, r.json())

r = client.post("/v1/deposits", json=env([
    {"system": "Ega", "planet": "Ega 1", "spot": "4", "type": "Ruby",
     "rigs": 2, "direction": 40.0, "distance": 0.9}]))
check("an older build's bearing-and-range row is still accepted",
      r.json()["accepted"] == 1, r.json())

r = client.post("/v1/deposits", json=env([
    {"system": "Ega", "planet": "Ega 1", "spot": "5", "type": "Lithium"}]))
check("a find with no position at all is still accepted",
      r.json()["accepted"] == 1, r.json())
check("rigs may be left uncounted",
      client.get("/v1/deposits", params={"commodity": "Lithium"}
                 ).json()["deposits"][0]["rigs"] == 0)

print("== the world a deposit sits on ==")
r = client.post("/v1/deposits", json=env([
    {"system": "Ega", "planet": "Ega 1", "spot": "9", "type": "Haematite",
     "rigs": 6, "lat": 30.0, "lon": 30.0, "amount": "High",
     "density": "High", "planet_class": "High metal content body",
     "gravity": 0.254, "atmosphere": "None", "volcanism": "Silicate vapour"}]))
check("a deposit with a world profile is accepted", r.json()["accepted"] == 1,
      r.json())
row = client.get("/v1/deposits", params={"commodity": "Haematite",
                                         "system": "Ega"}).json()["deposits"][0]
check("the planet class came back", row.get("planet_class") == "High metal content body",
      row.get("planet_class"))
check("gravity came back in g", abs(float(row.get("gravity") or 0) - 0.254) < 1e-6,
      row.get("gravity"))
check("volcanism came back", row.get("volcanism") == "Silicate vapour")
check("amount came back", row.get("amount") == "High", row.get("amount"))
check("and it is reported, not verified", row.get("status") == "reported",
      row.get("status"))

print("== verification ==")
# The badge only means something if it cannot be self-awarded.
main.STAFF = {"staff-secret": "CMDR Jameson"}
body = {"$schema": "radioraxxla/surfacemining-verify/1",
        "header": {"uploaderID": "x", "softwareName": "t",
                   "softwareVersion": "1", "gatewayTimestamp": iso()},
        "message": {"system": "Ega", "planet": "Ega 1", "spot": "9"}}

r = client.post("/v1/verify", json=body)
check("no token, no verification", r.status_code == 403, r.status_code)
r = client.post("/v1/verify", json=body,
                headers={"Authorization": "Bearer not-on-the-list"})
check("a wrong token is refused", r.status_code == 403, r.status_code)

r = client.post("/v1/verify", json=body,
                headers={"Authorization": "Bearer staff-secret"})
check("a staff token verifies it", r.status_code == 200, r.text[:200])
check("and the database records WHO", r.json().get("by") == "CMDR Jameson", r.json())

row = client.get("/v1/deposits", params={"commodity": "Haematite",
                                         "system": "Ega"}).json()["deposits"][0]
check("the deposit is now verified", row.get("status") == "verified", row.get("status"))

# An upload must never be able to claim the badge for itself.
r = client.post("/v1/deposits", json=env([
    {"system": "Liar", "planet": "L 1", "spot": "1", "type": "Painite",
     "rigs": 6, "lat": 1.0, "lon": 1.0, "status": "verified"}]))
check("an upload claiming to be verified is stored as reported anyway",
      client.get("/v1/deposits", params={"commodity": "Painite", "system": "Liar"}
                 ).json()["deposits"][0]["status"] == "reported")

r = client.post("/v1/verify",
                json={**body, "message": {**body["message"], "verified": False}},
                headers={"Authorization": "Bearer staff-secret"})
check("verification can be taken back", r.json().get("status") == "reported", r.json())

r = client.post("/v1/verify",
                json={**body, "message": {"system": "Nowhere", "planet": "N 1",
                                          "spot": "1"}},
                headers={"Authorization": "Bearer staff-secret"})
check("verifying a site that does not exist is a 404", r.status_code == 404,
      r.status_code)

print("== depletion ==")
d = client.post("/v1/depletion", json={
    "$schema": "radioraxxla/surfacemining-depletion/1",
    "header": {"uploaderID": "Jameson"},
    "message": {"system": "Col 285", "planet": "A 3", "spot": "1", "worked_out": True}})
check("depletion accepted", d.json()["ok"] is True, d.json())
after = client.get("/v1/sites").json()["sites"]
check("worked-out site hidden by default",
      all(x["system"] != "Col 285" for x in after), [x["system"] for x in after])
withdep = client.get("/v1/sites", params={"include_depleted": True}).json()["sites"]
shown = [x for x in withdep if x["system"] == "Col 285"]
# Asserted before it is indexed. This used to go straight to [0], so a
# broken include_depleted killed the run with an IndexError instead of
# naming the filter that stopped working.
check("shown when asked for", len(shown) == 1, [x["system"] for x in withdep])
flagged = shown[0] if shown else {}
check("and flagged as worked out", flagged.get("worked_out") is True)
stale = [x for x in withdep if x["system"] == "Legacy"]
check("worked-out site ranks below the stale one",
      bool(shown and stale) and flagged["score"] < stale[0]["score"],
      (flagged.get("score"), [x["system"] for x in withdep]))
# a new sighting clears it
client.post("/v1/deposits", json=env([{**base, "type": "Ruby", "direction": 300.0, "distance": 0.5}]))
check("a fresh sighting un-depletes the site",
      any(x["system"] == "Col 285" for x in client.get("/v1/sites").json()["sites"]))

print("== market prices ==")
def market(mid, station, system, items, when=None):
    return {"$schema": "radioraxxla/surfacemining-market/1",
            "header": {"uploaderID": "Jameson"},
            "message": {"market_id": mid, "station": station, "system": system,
                        "when": when or iso(), "items": items}}
m = client.post("/v1/market", json=market(1001, "Jameson Memorial", "Shinrarta Dezhra",
    [{"commodity": "Magnesite", "sell": 41234, "demand": 2500},
     {"commodity": "Bastnäsite", "sell": 88900, "demand": 900}]))
check("prices accepted", m.json()["accepted"] == 2, m.json())
client.post("/v1/market", json=market(1002, "Ray Gateway", "Diaguandri",
    [{"commodity": "Magnesite", "sell": 52000, "demand": 4000}]))
p = client.get("/v1/prices", params={"commodity": "Magnesite"}).json()
check("best price first", p["prices"][0]["sell"] == 52000, p["prices"])
check("both stations listed", p["count"] == 2, p["count"])
check("umlaut lookup works",
      client.get("/v1/prices", params={"commodity": "bastnasite"}).json()["count"] == 1)
check("a price for an uncatalogued commodity is accepted",
      client.post("/v1/market", json=market(1003, "X", "Y",
                  [{"commodity": "Haematite", "sell": 900}])).status_code == 200)

# older reading must not overwrite a newer one
client.post("/v1/market", json=market(1002, "Ray Gateway", "Diaguandri",
    [{"commodity": "Magnesite", "sell": 999, "demand": 1}], when=iso(30)))
p2 = client.get("/v1/prices", params={"commodity": "Magnesite"}).json()
check("stale price does not overwrite a newer one",
      p2["prices"][0]["sell"] == 52000, p2["prices"][0])

print("== commodities endpoint ==")
c = client.get("/v1/commodities").json()
check("the list has grown well past thirteen",
      len(c["commodities"]) > 30, len(c["commodities"]))
check("and includes what the game actually shows",
      "Haematite" in c["commodities"] and "Copper" in c["commodities"])
check("umlaut preserved", "Bastnäsite" in c["commodities"])
check("density tiers exposed", c["densities"][0] == "Depleted", c["densities"])

print("== the front door ==")
# api.radioraxxla.com is an address people type, paste into Discord and see
# in their firewall log. Answering it with a wall of raw JSON tells a human
# nothing about what the traffic from EDSMT is.
html = client.get("/", headers={"Accept": "text/html,application/xhtml+xml"})
check("a browser gets a page", html.status_code == 200
      and "text/html" in html.headers.get("content-type", ""))
check("it is a real document", html.text.strip().startswith("<!DOCTYPE"))
check("no template tokens survived",
      not [t for t in ("__VERSION__", "__SCHEMA__", "__DEPOSITS__",
                       "__SITES__", "__PRICES__") if t in html.text],
      [t for t in ("__VERSION__", "__SCHEMA__", "__DEPOSITS__") if t in html.text])
check("it says where to get the app",
      "radioraxxla.com/EDSMT/" in html.text)
check("and points at the generated docs", "/docs" in html.text)

api = client.get("/", headers={"Accept": "*/*"})
check("a client still gets JSON", api.status_code == 200
      and "application/json" in api.headers.get("content-type", ""))
body = api.json()
check("the JSON says what this is", body.get("service"))
check("and carries live counts", isinstance(body.get("counts"), dict)
      and "deposits" in body["counts"], body.get("counts"))
check("an explicit json accept is not fooled by the html branch",
      "application/json" in client.get(
          "/", headers={"Accept": "application/json"}
      ).headers.get("content-type", ""))
# One URL, two representations, possibly behind a cache. Without Vary a
# cache is free to store whichever it saw first and then hand JSON to
# browsers - or a web page to EDSMT - for as long as it likes.
check("both representations tell caches they vary on Accept",
      # Accept among whatever else is listed: newer Starlette's CORS layer
      # adds Origin to the same header, which is right and changes nothing.
      "accept" in [v.strip().lower() for v in (html.headers.get("vary") or "").split(",")]
      and "accept" in [v.strip().lower() for v in (api.headers.get("vary") or "").split(",")],
      (html.headers.get("vary"), api.headers.get("vary")))

print("== where a system is, and what is near me ==")
# The galaxy has 400 billion systems. A search that reads all of them is
# not a slow search, it is a broken one - and "the best site anywhere" is
# not a question anybody wants answered. These prove both halves: that
# the coordinates survive the round trip, and that the search is bounded
# by them.

SOL = {"system_address": 10477373803, "x": 0.0, "y": 0.0, "z": 0.0}
FAR = {"system_address": 22780229213, "x": 300.0, "y": 0.0, "z": 0.0}

client.post("/v1/deposits", json=env([
    {"system": "Sol", "planet": "Sol 4", "spot": "1", "type": "Gold",
     "rigs": 5, "lat": 3.0, "lon": 4.0, "density": "High", **SOL}]))
client.post("/v1/deposits", json=env([
    {"system": "Faraway", "planet": "F 1", "spot": "1", "type": "Gold",
     "rigs": 6, "lat": 3.0, "lon": 4.0, "density": "Pristine", **FAR}]))

row = sqlite3.connect(DB).execute(
    "SELECT name, x, y, z FROM systems WHERE address = ?",
    (SOL["system_address"],)).fetchone()
check("a system's position is remembered", row is not None and row[0] == "Sol", row)
check("and it is the position that was uploaded", row and row[1:] == (0.0, 0.0, 0.0), row)

near = client.get("/v1/sites", params={"near_x": 0, "near_y": 0, "near_z": 0,
                                       "within_ly": 50}).json()
names = [s["system"] for s in near["sites"]]
check("a site 300 Ly away is not 'near me'", "Faraway" not in names, names)
check("the one under my feet is", "Sol" in names, names)
check("and it is told how far away it is",
      near["sites"] and near["sites"][0].get("distance_ly") == 0.0,
      near["sites"][:1])

wide = client.get("/v1/sites", params={"near_x": 0, "near_y": 0, "near_z": 0,
                                       "within_ly": 500}).json()
check("widen the radius and it comes back",
      "Faraway" in [s["system"] for s in wide["sites"]],
      [s["system"] for s in wide["sites"]])

# The index can only serve a box, so the query asks for a box and then
# throws away the corners. A system at (40,40,40) is inside a 50 Ly cube
# and 69 Ly away - if the sphere is ever dropped, this is what catches it.
CORNER = {"system_address": 99999999901, "x": 40.0, "y": 40.0, "z": 40.0}
client.post("/v1/deposits", json=env([
    {"system": "Corner", "planet": "C 1", "spot": "1", "type": "Gold",
     "rigs": 6, "lat": 9.0, "lon": 9.0, **CORNER}]))
corner = client.get("/v1/sites", params={"near_x": 0, "near_y": 0, "near_z": 0,
                                         "within_ly": 50}).json()
check("a cube corner is not inside the sphere",
      "Corner" not in [s["system"] for s in corner["sites"]],
      [s["system"] for s in corner["sites"]])
check("the maths agrees it is 69 Ly out",
      round(main.light_years((0, 0, 0), (40, 40, 40)), 1) == 69.3,
      main.light_years((0, 0, 0), (40, 40, 40)))
check("individual deposits can be bounded too",
      "Faraway" not in [d["system"] for d in client.get(
          "/v1/deposits", params={"near_x": 0, "near_y": 0, "near_z": 0,
                                  "within_ly": 50}).json()["deposits"]])
check("a search with no position still answers",
      client.get("/v1/sites").json()["count"] > 0)

print("== the search is bounded, not scanned ==")
conn = sqlite3.connect(DB)
plan = " ".join(str(r) for r in conn.execute(
    "EXPLAIN QUERY PLAN SELECT 1 FROM deposits d WHERE EXISTS "
    "(SELECT 1 FROM deposits t WHERE t.system = d.system AND t.planet = d.planet "
    "  AND t.spot = d.spot AND t.type = ?)", ("Gold",)).fetchall())
# The old filter concatenated the key columns into a string and compared
# that, which no index can serve. This is the regression test for it.
check("the commodity filter uses an index", "USING INDEX" in plan.upper(), plan)

indexes = {r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type = 'index'")}
for needed in ("ix_systems_x", "ix_dep_addr", "ix_dep_created",
               "ix_sites_seen", "ix_dep_type_rigs"):
    check("index %s exists" % needed, needed in indexes, sorted(indexes))

source = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "server", "main.py"), encoding="utf-8").read()
check("the site roll-up has a LIMIT in SQL, not just in Python",
      "ORDER BY raw DESC LIMIT ?" in source)
check("density is ranked once on the way in, not per search",
      "AVG(d.density_rank)" in source and "density_rank(d.density)" in source)
# Density is averaged and RETURNED, so a commander can see it, and is
# deliberately absent from `raw`. The field guide: its effect on yield is
# unproven and the observed trend runs inverse, so weighting it ranks on
# a belief the project's own research does not hold.
check("density is still averaged and returned",
      "AVG(d.density_rank)" in source)
check("but it is not weighted into the score",
      "density_rank), 2.0) * 1.5" not in source
      and "density_rank) * 1.5" not in source)
check("and the code says why", "runs INVERSE" in source)

# Every density the server RECOGNISES must have been ranked by the
# migration. A deposit with no density recorded stays NULL on purpose:
# AVG() skips NULLs, so a site's density is the average of the densities
# it actually has - which is what the Python scorer used to do, and
# backfilling a neutral value silently changed every ranking.
check("recognised densities were ranked by the migration",
      conn.execute("SELECT COUNT(*) FROM deposits WHERE density_rank IS NULL "
                   "AND lower(trim(density)) IN ('low','medium','high',"
                   "'pristine')").fetchone()[0] == 0)
check("and a deposit with no density stays unranked",
      conn.execute("SELECT COUNT(*) FROM deposits WHERE density_rank IS NULL"
                   ).fetchone()[0] > 0)
conn.close()

print("== ranking survived being bounded ==")
# The pool is only safe because the decay can never raise a score. If
# freshness or regen ever returns more than 1, the top of the list can
# come from outside the pool and the bound becomes a bug.
check("freshness never exceeds 1", main.freshness(iso(0)) <= 1.0)
check("and falls with age", main.freshness(iso(60)) < main.freshness(iso(1)))
check("the pool is far larger than the page it serves",
      main.POOL_MULTIPLIER >= 10 and main.POOL_FLOOR >= 100)

print("== a site says who found it and whether anyone stands behind it ==")
# Three shipped UI filters were no-ops because /v1/sites is a GROUP BY that
# selected neither column: "verified only" matched nothing, and every find on
# the map was anonymous whether or not the commander asked to be credited.
def named(who, deposits):
    return {"$schema": "radioraxxla/surfacemining/1",
            "header": {"uploaderID": who, "softwareName": "EDSMT",
                       "softwareVersion": main.APP_VERSION,
                       "gatewayTimestamp": iso()},
            "message": {"deposits": deposits}}

FIRST = {"system": "Attribution", "planet": "A 1", "spot": "1",
         "type": "Olivine", "rigs": 5, "lat": 5.0, "lon": 5.0}
client.post("/v1/deposits", json=named("CMDR First", [FIRST]))
client.post("/v1/deposits", json=named("CMDR Second",
            [dict(FIRST, type="Magnesite", lat=5.02, lon=5.02)]))

def site_named(system):
    hits = [s for s in client.get("/v1/sites", params={"limit": 500,
                                                       "include_depleted": True}
                                  ).json()["sites"] if s["system"] == system]
    return hits[0] if hits else None

attribution = site_named("Attribution")
check("a site carries a status", attribution.get("status") == "reported",
      attribution.get("status"))
check("and the commander who first reported it",
      attribution.get("uploader") == "CMDR First", attribution.get("uploader"))
check("later commanders do not overwrite the finder",
      attribution.get("uploader") != "CMDR Second", attribution.get("uploader"))
check("and it says the name is real rather than missing",
      attribution.get("uploader_known") is True, attribution.get("uploader_known"))
check("independent confirmations are counted",
      attribution.get("confirmed_by") == 2, attribution.get("confirmed_by"))

# Sharing a CMDR name is a switch in Settings, so blank is normal and must
# not read as a column that failed to load.
client.post("/v1/deposits", json=named("", [
    {"system": "Unsigned", "planet": "U 1", "spot": "1", "type": "Ruby",
     "rigs": 4, "lat": 1.0, "lon": 1.0}]))
unsigned = site_named("Unsigned")
check("an anonymous find comes back with an empty uploader, not a null",
      unsigned.get("uploader") == "", repr(unsigned.get("uploader")))
check("flagged as anonymous rather than as broken",
      unsigned.get("uploader_known") is False, unsigned.get("uploader_known"))
check("and anonymous uploads cannot corroborate themselves",
      unsigned.get("confirmed_by") == 0, unsigned.get("confirmed_by"))

main.STAFF = {"staff-secret": "CMDR Jameson"}
client.post("/v1/verify", json={
    "$schema": "radioraxxla/surfacemining-verify/1",
    "header": {"uploaderID": "x"},
    "message": {"system": "Attribution", "planet": "A 1", "spot": "1"}},
    headers={"Authorization": "Bearer staff-secret"})
# This used to be called "so the 'verified only' filter can work" and was
# the only thing standing behind that filter. It never touched a filter:
# site_named() asks for include_depleted and limit=500 and then sifts the
# page in Python, which is precisely the bug. All it proves is that the
# column survives the GROUP BY, so that is now all it claims. The filter
# itself is proved against the database further down.
check("a verified site carries the status through the roll-up",
      site_named("Attribution").get("status") == "verified",
      site_named("Attribution").get("status"))
check("and names who stood behind it",
      site_named("Attribution").get("verified_by") == "CMDR Jameson",
      site_named("Attribution").get("verified_by"))

print("== a deposit knows its site was stripped ==")
# Depletion is tracked per site, so without the join a deposit row physically
# cannot answer it - and the app's "hide worked out" box kept everything.
client.post("/v1/deposits", json=named("CMDR First", [
    {"system": "Strippedville", "planet": "S 1", "spot": "1", "type": "Ruby",
     "rigs": 6, "lat": 2.0, "lon": 2.0}]))
row = client.get("/v1/deposits", params={"system": "Strippedville"}).json()
check("a deposit carries worked_out at all", "worked_out" in row["deposits"][0],
      sorted(row["deposits"][0])[:12])
check("and it is false while nobody has said otherwise",
      row["deposits"][0]["worked_out"] is False)

def deplete(who, system, planet="S 1", spot="1", worked_out=True,
            game_version=""):
    return client.post("/v1/depletion", json={
        "$schema": "radioraxxla/surfacemining-depletion/1",
        "header": {"uploaderID": who, "softwareName": "EDSMT",
                   "softwareVersion": main.APP_VERSION,
                   "gameVersion": game_version},
        "message": {"system": system, "planet": planet, "spot": spot,
                    "worked_out": worked_out}})

deplete("CMDR First", "Strippedville")
row = client.get("/v1/deposits", params={"system": "Strippedville"}).json()
check("a stripped site marks every deposit on it",
      row["deposits"][0]["worked_out"] is True, row["deposits"][0])
check("with the elapsed time, which is the part anyone actually knows",
      row["deposits"][0]["days_since_worked_out"] is not None
      and row["deposits"][0]["days_since_worked_out"] < 1,
      row["deposits"][0].get("days_since_worked_out"))
check("and no implied countdown anywhere on it",
      row["deposits"][0]["reformation_measured"] is False)

print("== a partial system name finds something ==")
# "Col 285" is what a commander types; "Col 285 Sector ZL-K b22-2" is what
# the game calls the place. Exact match answered that with nothing at all,
# which reads as "no data here" rather than "not what you typed".
client.post("/v1/deposits", json=named("CMDR First", [
    {"system": "Col 285 Sector ZL-K b22-2", "planet": "B 4", "spot": "1",
     "type": "Magnesite", "rigs": 4, "lat": 7.0, "lon": 7.0}]))
partial = client.get("/v1/deposits", params={"system": "Col 285 Sector"}).json()
check("a prefix finds the full system name", partial["count"] >= 1,
      partial["count"])
check("and it really is the long one",
      any(d["system"] == "Col 285 Sector ZL-K b22-2" for d in partial["deposits"]),
      [d["system"] for d in partial["deposits"]])
check("case does not matter either",
      client.get("/v1/deposits",
                 params={"system": "col 285 sector"}).json()["count"] >= 1)
check("an exact name still works",
      client.get("/v1/deposits",
                 params={"system": "Col 285 Sector ZL-K b22-2"}
                 ).json()["count"] >= 1)
check("and a prefix that matches nothing still returns nothing",
      client.get("/v1/deposits", params={"system": "Zzzz"}).json()["count"] == 0)

conn = sqlite3.connect(DB)
JOINED = ("EXPLAIN QUERY PLAN SELECT d.* FROM deposits d LEFT JOIN sites s "
          "ON s.system = d.system AND s.planet = d.planet AND s.spot = d.spot "
          "WHERE 1=1 AND d.system LIKE ?")
plan = " ".join(str(r) for r in conn.execute(JOINED, ("Col 285%",)).fetchall())
# A prefix LIKE can use an index; a leading-wildcard one cannot. If this
# ever says SCAN, the search box has become a full read of the galaxy.
check("the prefix search is still served by an index",
      "SEARCH d USING INDEX ix_system" in plan, plan)
scan = " ".join(str(r) for r in conn.execute(
    "EXPLAIN QUERY PLAN SELECT * FROM deposits WHERE system LIKE ?",
    ("%Col 285%",)).fetchall())
check("and a leading wildcard is exactly what would have scanned it",
      "SCAN" in scan.upper() and "USING INDEX ix_system" not in scan, scan)
# The other way to get this wrong: building the pattern in SQL. SQLite only
# takes the index when the whole pattern arrives as one bound string, so
# `LIKE ? || '%'` is an expression and plans as a full scan of the galaxy.
concat = " ".join(str(r) for r in conn.execute(
    "EXPLAIN QUERY PLAN SELECT * FROM deposits WHERE system LIKE ? || '%'",
    ("Col 285",)).fetchall())
check("and so is concatenating the pattern in SQL instead of binding it",
      "SCAN" in concat.upper() and "USING INDEX ix_system" not in concat, concat)
conn.close()
check("so leading wildcards are stripped before the pattern is built",
      main.prefix_pattern("%Col") == "Col%"
      and main.prefix_pattern("_Col") == "Col%", main.prefix_pattern("%Col"))
# The plan above is only worth anything if it is the shape the endpoint
# actually issues - a bound pattern against the indexed column.
check("and the deposit search is the query that plan belongs to",
      '" AND d.system LIKE ?"' in source and "prefix_pattern(system)" in source)

print("== depletion is corroborated, not just flagged ==")
# Two commanders reporting a site stripped is a far stronger claim than one.
# A flag cannot say that, so the reporters are counted.
client.post("/v1/deposits", json=named("CMDR First", [
    {"system": "Corroborate", "planet": "C 1", "spot": "1", "type": "Ruby",
     "rigs": 6, "lat": 4.0, "lon": 4.0}]))
one = deplete("CMDR One", "Corroborate", "C 1").json()
check("the first report says it is the first", one["reporters"] == 1, one)
again = deplete("CMDR One", "Corroborate", "C 1").json()
check("the same commander saying it twice is still one report",
      again["reporters"] == 1, again)
two = deplete("CMDR Two", "Corroborate", "C 1").json()
check("a second commander is real corroboration", two["reporters"] == 2, two)
check("and the API is more certain because of it",
      two["confidence"] > one["confidence"], (one["confidence"], two["confidence"]))
anon = deplete("", "Corroborate", "C 1").json()
check("anonymous reports collapse together rather than inflating the count",
      deplete("", "Corroborate", "C 1").json()["reporters"] == anon["reporters"],
      anon)

corr = site_named("Corroborate")
check("the site carries the reporter count",
      corr["worked_out_reports"] >= 2, corr.get("worked_out_reports"))
check("and when the episode started", corr["worked_out_first"], corr)
check("and when it was last confirmed stripped",
      corr["worked_out_last"] >= corr["worked_out_first"], corr)
check("a corroborated site is trusted less than a singly-reported one",
      corr["intact_confidence"] < site_named("Strippedville")["intact_confidence"],
      (corr["intact_confidence"],
       site_named("Strippedville")["intact_confidence"]))

print("== no countdown is presented as knowledge ==")
# The field guide is flat about it: the reformation timer is Not established.
# One site has been under timed watch since 6 September with nothing measured.
check("health says the reformation timer is unmeasured",
      client.get("/v1/health").json()["reformation_measured"] is False)
check("and does not publish a regen_days that reads like a fact",
      "regen_days" not in client.get("/v1/health").json(),
      sorted(client.get("/v1/health").json()))
check("the estimate is still a dial, named as one, in the server",
      main.REFORMATION_ESTIMATE_DAYS == 60.0)
sites_body = client.get("/v1/sites", params={"include_depleted": True}).json()
check("every sites response repeats it",
      sites_body["reformation_measured"] is False)
check("and the row carries elapsed days, not days remaining",
      corr["days_since_worked_out"] is not None
      and "days_until" not in corr and "recovered" not in corr, sorted(corr))
check("the guess it does use is labelled a guess",
      "recovery_assumed" in corr, sorted(corr))
# Sites have been watched persisting unchanged across a hotfix. Age is our
# uncertainty about the report, not evidence the deposit went away.
check("a site's decay is named confidence now",
      "confidence" in attribution and attribution["confidence"] > 0.99,
      attribution.get("confidence"))
check("and freshness survives as the old spelling of it",
      site_named("Attribution")["freshness"]
      == site_named("Attribution")["confidence"])
check("a second independent confirmation raises confidence in a report",
      main.report_confidence(iso(40), corroboration=2)
      > main.report_confidence(iso(40), corroboration=1),
      (main.report_confidence(iso(40), corroboration=2),
       main.report_confidence(iso(40), corroboration=1)))
check("but it can never exceed 1, which is what keeps the pool honest",
      main.report_confidence(iso(0), corroboration=9) <= 1.0)
check("corroborated depletion beats a lone report",
      main.stripped_belief(2) > main.stripped_belief(1) > 0.9,
      (main.stripped_belief(1), main.stripped_belief(2)))
check("and nobody has reported it means nobody believes it is stripped",
      main.stripped_belief(0) == 0.0)

print("== a depletion report is not a sighting ==")
# It used to bump last_seen, so the moment somebody said a site was empty it
# looked freshly confirmed. Those are opposite claims.
seen_before = site_named("Corroborate")["last_confirmed_present"]
deplete("CMDR Three", "Corroborate", "C 1")
check("saying a site is empty does not count as seeing deposits there",
      site_named("Corroborate")["last_confirmed_present"] == seen_before,
      (seen_before, site_named("Corroborate")["last_confirmed_present"]))
deplete("CMDR One", "Corroborate", "C 1", worked_out=False)
back = site_named("Corroborate")
check("taking it back clears the whole episode, not one line of it",
      back["worked_out"] is False and back["worked_out_reports"] == 0, back)
deplete("CMDR One", "Corroborate", "C 1")
client.post("/v1/deposits", json=named("CMDR First", [
    {"system": "Corroborate", "planet": "C 1", "spot": "1", "type": "Ruby",
     "rigs": 6, "lat": 4.5, "lon": 4.5}]))
check("and somebody standing there outranks every stale report",
      site_named("Corroborate")["worked_out_reports"] == 0,
      site_named("Corroborate"))

print("== which patches are probably still there ==")
still = client.get("/v1/intact").json()
check("the endpoint answers", still["count"] > 0, still.get("count"))
check("it says what it ranked by", still["ranked_by"] == "intact_confidence")
check("ranked by confidence, not by size",
      all(a["intact_confidence"] >= b["intact_confidence"]
          for a, b in zip(still["sites"], still["sites"][1:])),
      [s["intact_confidence"] for s in still["sites"]])
check("a freshly stripped site is not in the answer",
      all(s["system"] != "Strippedville" for s in still["sites"]),
      [s["system"] for s in still["sites"]])
check("but it is not hidden by a flag - it fails on its own evidence",
      any(s["system"] == "Strippedville" for s in
          client.get("/v1/intact", params={"min_confidence": 0}).json()["sites"]))
check("the threshold is reported back", still["min_confidence"] == 0.5)
check("and the honesty marker travels with it",
      still["reformation_measured"] is False
      and "unmeasured" in still["note"].lower(), still.get("note"))

print("== the game build every record came from ==")
# 4.4.1.1 raised chunks per rig from 9 to 12 one day after launch. Nothing
# recorded on 2 September can be compared with anything recorded on the 3rd
# without knowing which build it was.
stamped = {"$schema": "radioraxxla/surfacemining/1",
           "header": {"uploaderID": "CMDR First", "softwareName": "EDSMT",
                      "softwareVersion": main.APP_VERSION,
                      "gameVersion": "4.4.1.1"},
           "message": {"deposits": [
               {"system": "Stamped", "planet": "S 9", "spot": "1",
                "type": "Iridium", "rigs": 5, "lat": 8.0, "lon": 8.0}]}}
r = client.post("/v1/deposits", json=stamped)
check("a game version is accepted", r.status_code == 200 and
      r.json()["accepted"] == 1, r.json())
stored = client.get("/v1/deposits", params={"system": "Stamped"}).json()
check("and stored against the find",
      stored["deposits"][0]["game_version"] == "4.4.1.1",
      stored["deposits"][0].get("game_version"))
check("the site records it too", site_named("Stamped")["game_version"] == "4.4.1.1",
      site_named("Stamped").get("game_version"))
# Every client shipped so far sends a header without it. A 422 because the
# app is one build behind is worse than a blank version.
old_client = client.post("/v1/deposits", json=named("CMDR First", [
    {"system": "Unstamped", "planet": "U 9", "spot": "1", "type": "Iridium",
     "rigs": 5, "lat": 9.0, "lon": 9.0}]))
check("a client that does not send one is not broken by it",
      old_client.status_code == 200 and old_client.json()["accepted"] == 1,
      old_client.json())
check("it just comes back blank, which is the truth",
      client.get("/v1/deposits", params={"system": "Unstamped"}
                 ).json()["deposits"][0]["game_version"] == "",
      client.get("/v1/deposits", params={"system": "Unstamped"}
                 ).json()["deposits"][0].get("game_version"))
deplete("CMDR Nine", "Stamped", "S 9", game_version="4.4.1.1")
check("a depletion report carries the build as well",
      sqlite3.connect(DB).execute(
          "SELECT game_version FROM depletion_reports WHERE system='Stamped'"
      ).fetchone()[0] == "4.4.1.1")
client.post("/v1/market", json={
    "$schema": "radioraxxla/surfacemining-market/1",
    "header": {"uploaderID": "CMDR First", "gameVersion": "4.4.1.1"},
    "message": {"market_id": 2001, "station": "Stamp Hub", "system": "Stamped",
                "when": iso(), "items": [{"commodity": "Iridium", "sell": 1234}]}})
check("and so does a price",
      sqlite3.connect(DB).execute(
          "SELECT game_version FROM prices WHERE market_id=2001").fetchone()[0]
      == "4.4.1.1")
check("a version longer than any real one is refused",
      client.post("/v1/deposits", json={
          **stamped,
          "header": {**stamped["header"], "gameVersion": "x" * 90}}
      ).status_code == 422)

print("== an existing database is never thrown away ==")
# ADDED_COLUMNS used one snapshot of `deposits` and tested every entry
# against it, so a column added to `sites` was skipped whenever `deposits`
# happened to have one of the same name.
DRIFT = os.path.join(TMP, "drift.db")
drift = sqlite3.connect(DRIFT)
drift.executescript(main.DDL)
drift.execute("ALTER TABLE deposits ADD COLUMN status TEXT DEFAULT 'reported'")
drift.execute("ALTER TABLE deposits ADD COLUMN game_version TEXT DEFAULT ''")
drift.execute("""INSERT INTO deposits (system,planet,spot,type,rigs,direction,
                 distance,created,fingerprint) VALUES
                 ('Drift','D 1','1','Ruby',3,0,0,?,'drift|1')""", (iso(),))
drift.commit()
drift.row_factory = sqlite3.Row
main.migrate(drift)
site_cols = {r[1] for r in drift.execute("PRAGMA table_info(sites)")}
for column in ("status", "game_version", "depleted_last", "depleted_reporters"):
    check("sites.%s survives a database that already had deposits.%s"
          % (column, column), column in site_cols, sorted(site_cols))
check("and the row that was already there is still there",
      drift.execute("SELECT COUNT(*) FROM deposits").fetchone()[0] == 1)
check("the old site was backfilled",
      drift.execute("SELECT COUNT(*) FROM sites").fetchone()[0] == 1)

# A box that was already flagging sites stripped before anybody counted
# reporters must not come back reading zero - that would quietly un-deplete
# every site on it.
drift.execute("UPDATE sites SET depleted = ?", (iso(3),))
drift.execute("UPDATE sites SET depleted_reporters = 0, depleted_last = ''")
main.migrate(drift)
check("an old depletion flag becomes one attested report, not none",
      drift.execute("SELECT depleted_reporters FROM sites").fetchone()[0] == 1,
      drift.execute("SELECT depleted_reporters FROM sites").fetchone()[0])
check("and it is filed as anonymous, because we no longer know who",
      drift.execute("SELECT uploader FROM depletion_reports").fetchone()[0] == "")
drift.close()

print("== where it sells, proxied so nobody hammers the upstream ==")
# The app asks us rather than the upstream directly, so one cache and one
# rate limiter cover everybody running EDSMT.
calls = []
def fake_upstream(commodity, near_system="", within_ly=0, limit=20):
    calls.append((commodity, near_system, within_ly))
    return [{"commodity": commodity, "station": "Upstream Hub",
             "system": "Somewhere", "sell": 999999, "demand": 50000,
             "distance_ly": 12, "seen": iso(), "source": "test"}]
real_fetch, main.fetch_upstream_sell = main.fetch_upstream_sell, fake_upstream
main._sell_cache.clear(); main._sell_last_call[0] = 0.0

# Which index is configuration. With none configured the endpoint answers
# from our own users' reads and says why there is nothing else.
real_base = main.SELL_UPSTREAM_BASE
main.SELL_UPSTREAM_BASE = ""
bare = client.get("/v1/sell", params={"commodity": "Magnesite"})
check("no index configured is an answer, not an error",
      bare.status_code == 200 and bare.json()["upstream_status"] == "not configured",
      (bare.status_code, bare.json().get("upstream_status")))
check("and nothing is fetched from anywhere", not calls, calls)
main.SELL_UPSTREAM_BASE = "https://index.example"
main._sell_cache.clear(); main._sell_last_call[0] = 0.0

s = client.get("/v1/sell", params={"commodity": "Magnesite"}).json()
check("it answers with the upstream's best", s["best_sell"] == 999999, s)
check("upstream rows are labelled as upstream",
      s["market"][0]["source"] == "test", s["market"][:1])
check("and our own commanders' reads are kept separate, not blended",
      s["community"] and all(r["source"] == "community" for r in s["community"]),
      s["community"][:1])
check("the commodity name is folded to Frontier's spelling",
      client.get("/v1/sell", params={"commodity": "bastnasite"}
                 ).json()["commodity"] == "Bastnäsite")
check("asking without one is refused rather than answered wrongly",
      client.get("/v1/sell").status_code == 422)

before = len(calls)
client.get("/v1/sell", params={"commodity": "Magnesite"})
check("a second identical question does not hit the upstream again",
      len(calls) == before, len(calls) - before)
check("and says so", client.get("/v1/sell", params={"commodity": "Magnesite"}
                                ).json()["upstream_status"] == "cached")

main._sell_cache.clear()
main._sell_last_call[0] = time.time()
throttled = client.get("/v1/sell", params={"commodity": "Olivine"}).json()
check("a cache miss inside the rate limit does not queue up on them",
      throttled["upstream_status"] == "rate-limited", throttled["upstream_status"])
check("and still answers from our own data rather than failing",
      "community" in throttled and throttled["market"] == [], throttled)

def broken(*a, **k):
    raise RuntimeError("upstream is on fire")
main.fetch_upstream_sell = broken
main._sell_cache.clear(); main._sell_last_call[0] = 0.0
down = client.get("/v1/sell", params={"commodity": "Magnesite"}).json()
check("somebody else's outage is not ours",
      down["upstream_status"] == "unavailable", down["upstream_status"])
check("and our own prices still come back",
      any(r["source"] == "community" for r in down["community"]), down)
main.fetch_upstream_sell = real_fetch

# The upstream slug is lowercase, accent-stripped and unspaced - which is
# exactly what fold() already produces. Checked against the live service.
check("the umlaut is stripped for the upstream",
      main.sell_slug("Bastnäsite") == "bastnasite", main.sell_slug("Bastnäsite"))
check("and spaces go too", main.sell_slug("Periclase dunite") == "periclasedunite")
check("the one checked spelling difference is mapped, not guessed",
      main.sell_slug("Low Temperature Diamonds") == "lowtemperaturediamond")
main.SELL_UPSTREAM_BASE = real_base
check("the index is configuration, read from RR_SELL_API",
      "RR_SELL_API" in source)
check("and the public source names no index at all by default",
      real_base == "" or os.environ.get("RR_SELL_API"), real_base)
check("the shape it expects is written down beside the code",
      "/v2/commodity/name/{slug}/imports" in source)

print("== the same deposit sent again carries its changes ==")
# UPDATE in the app re-sends a deposit with its new Amount. The server used
# to treat that as a duplicate and drop it, so the map went on saying High
# long after the patch had been worked down.
UPD = {"system": "Update Town", "planet": "U 1", "spot": "2", "type": "Ruby",
       "rigs": 3, "lat": 5.0, "lon": 5.0, "amount": "High", "density": "Low"}
client.post("/v1/deposits", json=env([UPD]))
r = client.post("/v1/deposits", json=env([dict(UPD, amount="Low", density="")])).json()
check("a changed Amount is reported as an update", r.get("updated") == 1, r)
row = [d for d in client.get("/v1/deposits", params={"system": "Update Town"}).json()["deposits"]]
check("and it is stored", row and row[0]["amount"] == "Low", row)
check("a blank Density did not wipe the one already there",
      row and row[0]["density"] == "Low", row)
r = client.post("/v1/deposits", json=env([dict(UPD, amount="Low", density="")])).json()
check("sending it again unchanged is a duplicate and not an update",
      r.get("updated") == 0 and r.get("duplicates") == 1, r)
r = client.post("/v1/deposits", json=env([dict(UPD, amount="Low", rigs=4)])).json()
row = client.get("/v1/deposits", params={"system": "Update Town"}).json()["deposits"]
check("a corrected rig count is taken", row[0]["rigs"] == 4 and r.get("updated") == 1, (row, r))
r = client.post("/v1/deposits", json=env([dict(UPD, amount="Low", rigs=0)])).json()
row = client.get("/v1/deposits", params={"system": "Update Town"}).json()["deposits"]
check("but no rig count at all does not zero it", row[0]["rigs"] == 4, row)

print("== what each kind of ground has carried ==")
main._grounds_cache.clear()
for i, (typ, rigs) in enumerate((("Jadeite", 4), ("Olivine", 2), ("Jadeite", 3))):
    client.post("/v1/deposits", json=env([{
        "system": "Ground Town", "planet": "G 4", "spot": str(i // 2 + 1),
        "type": typ, "rigs": rigs, "lat": 1.0 + i * 0.05, "lon": 1.0,
        "planet_class": "Rocky body",
        "volcanism": "major silicate vapour geysers volcanism"}]))
client.post("/v1/deposits", json=env([{
    "system": "Ground Town", "planet": "G 5", "spot": "1", "type": "Iridium",
    "rigs": 2, "lat": 3.0, "lon": 3.0, "planet_class": "Metal rich body",
    "volcanism": ""}]))
g = client.get("/v1/grounds").json()
geyser = next(x for x in g["grounds"]
              if x["ground"] == "Rocky body, major silicate vapour geysers")
check("a ground is its body class and its volcanism", geyser["sites"] == 2, geyser)
jade = next(c for c in geyser["commodities"] if c["name"] == "Jadeite")
check("a commodity's share is the sites it turned up on", jade["share"] == 1.0
      and jade["rigs"] == 7, jade)
oli = next(c for c in geyser["commodities"] if c["name"] == "Olivine")
check("and one on half of them reads a half", oli["share"] == 0.5, oli)
check("a body with no volcanism is its class alone",
      any(x["ground"] == "Metal rich body" for x in g["grounds"]), [x["ground"] for x in g["grounds"]])
check("and a bare request answers", client.get("/v1/grounds").status_code == 200)
# The same kind of ground written two ways by two commanders' games - an
# empty volcanism and "No volcanism" - is one ground, and the same site
# typed in a different case is one site.
main._grounds_cache.clear()
client.post("/v1/deposits", json=env([{
    "system": "ground town", "planet": "g 5", "spot": "1", "type": "Platinum",
    "rigs": 1, "lat": 3.2, "lon": 3.2, "planet_class": "Metal rich body",
    "volcanism": "No volcanism"}]))
g = client.get("/v1/grounds").json()
rich = [x for x in g["grounds"] if x["ground"] == "Metal rich body"]
check("two spellings of no volcanism are one ground", len(rich) == 1, rich)
check("and a site typed in another case is still one site",
      rich and rich[0]["sites"] == 1, rich)
check("the table is counted by the database, not row by row in Python",
      "GROUP BY pc, volc" in open(os.path.join(os.path.dirname(os.path.dirname(
          os.path.abspath(__file__))), "server", "main.py"), encoding="utf-8").read())

print("== the Find window's filters are answered by the database ==")
# The app shipped a system box, a "hide worked-out" tick and a "verified
# only" tick, and /v1/sites accepted none of them. So the app sifted the
# page it had already been handed: ticking "verified only" filtered 500 rows
# that were chosen without reference to it. On a galaxy of 400 billion
# systems that is not a filter, it is a coincidence.
import inspect
takes = inspect.signature(main.sites).parameters
check("the site search accepts a system name at all", "system" in takes,
      sorted(takes))
check("and a verified-only switch", "verified_only" in takes, sorted(takes))
check("the switch defaults to off, so nothing is hidden by surprise",
      takes["verified_only"].default is False, takes["verified_only"].default)
check("and the system box defaults to empty, meaning no filter",
      takes["system"].default == "", repr(takes["system"].default))

FINDBOX = {"planet": "F 1", "spot": "1", "type": "Olivine", "rigs": 5,
           "lat": 7.0, "lon": 7.0}
for name in ("Findbox Alpha", "Findbox Beta", "Elsewhere Entirely"):
    client.post("/v1/deposits", json=env([dict(FINDBOX, system=name)]))
client.post("/v1/verify", json={
    "$schema": "radioraxxla/surfacemining-verify/1",
    "header": {"uploaderID": "x"},
    "message": {"system": "Findbox Alpha", "planet": "F 1", "spot": "1"}},
    headers={"Authorization": "Bearer staff-secret"})
client.post("/v1/depletion", json={
    "$schema": "radioraxxla/surfacemining-depletion/1",
    "header": {"uploaderID": "CMDR Someone"},
    "message": {"system": "Findbox Beta", "planet": "F 1", "spot": "1",
                "worked_out": True}})

def found(**params):
    return [s["system"] for s in client.get(
        "/v1/sites", params=dict({"limit": 500}, **params)).json()["sites"]]

check("a system name narrows the search to that system",
      found(system="Findbox Alpha") == ["Findbox Alpha"],
      found(system="Findbox Alpha"))
check("it is a prefix, so half a name finds the whole one",
      sorted(found(system="Findbox", include_depleted=True))
      == ["Findbox Alpha", "Findbox Beta"],
      found(system="Findbox", include_depleted=True))
check("and case is not something a commander should have to get right",
      found(system="fINDBOX aLPHA") == ["Findbox Alpha"],
      found(system="fINDBOX aLPHA"))
# The one that catches a parameter the server quietly ignores: FastAPI drops
# an unknown query parameter without a word, so a filter that is not
# implemented looks exactly like a filter that matched everything.
check("a system nobody has surveyed comes back empty, not full",
      found(system="Nobody Has Ever Been Here") == [],
      found(system="Nobody Has Ever Been Here"))
check("and asking for no system still answers with the galaxy",
      len(found()) > 1, found())

check("verified only means verified only",
      found(system="Findbox", verified_only=True, include_depleted=True)
      == ["Findbox Alpha"],
      found(system="Findbox", verified_only=True, include_depleted=True))
check("a merely reported site is not in it",
      "Findbox Beta" not in found(verified_only=True, include_depleted=True),
      found(verified_only=True, include_depleted=True))
check("and leaving the switch alone keeps both",
      sorted(found(system="Findbox", include_depleted=True))
      == ["Findbox Alpha", "Findbox Beta"],
      found(system="Findbox", include_depleted=True))

check("a worked-out site is hidden unless it is asked for",
      found(system="Findbox") == ["Findbox Alpha"], found(system="Findbox"))
check("and asking brings it back",
      "Findbox Beta" in found(system="Findbox", include_depleted=True),
      found(system="Findbox", include_depleted=True))
# Two filters at once, because one narrowing the other is the case the app
# actually sends and the case a client-side sift gets wrong.
check("the filters compose rather than fighting each other",
      found(system="Findbox Beta", verified_only=True, include_depleted=True)
      == [], found(system="Findbox Beta", verified_only=True,
                   include_depleted=True))

print("== the Find window's filters search, they do not scan ==")
# These EXPLAIN the query the ENDPOINT builds, caught on its way to SQLite,
# rather than a copy of it typed out here. A plan test that explains its own
# copy proves the copy is fast and keeps passing while the endpoint quietly
# stops using an index - which is the shape of test this file was sent to
# get rid of, so it is not one to write on the way past.
class SpyConnection:
    """Passes everything through and keeps the SQL."""
    def __init__(self, conn, log):
        self._conn, self._log = conn, log
    def execute(self, sql, args=()):
        self._log.append((sql, list(args)))
        return self._conn.execute(sql, args)
    def __getattr__(self, name):
        return getattr(self._conn, name)

def plan_of(path, params, table):
    """The real query plan for the statement that reads `table`."""
    log, real = [], main.connect
    main.connect = lambda: SpyConnection(real(), log)
    try:
        client.get(path, params=dict({"limit": 50}, **params))
    finally:
        main.connect = real
    hits = [(s, a) for s, a in log if ("FROM %s" % table) in s]
    if not hits:
        return "no statement read %s at all" % table
    conn = sqlite3.connect(DB)
    sql, args = hits[0]
    try:
        return " | ".join(str(r[-1]) for r in
                          conn.execute("EXPLAIN QUERY PLAN " + sql, args))
    finally:
        conn.close()

prefix_plan = plan_of("/v1/sites", {"system": "Findbox"}, "deposits d")
check("the system box is served by an index, not by reading the galaxy",
      "SEARCH d USING" in prefix_plan and "SCAN d" not in prefix_plan,
      prefix_plan)
# The pattern is built in Python and bound whole for this exact reason. If
# it is ever inlined as `system LIKE ? || '%'` the plan drops to SCAN.
check("and only because the pattern is bound whole",
      main.prefix_pattern("Findbox") == "Findbox%",
      main.prefix_pattern("Findbox"))
check("a leading wildcard, which no index can serve, is stripped",
      main.prefix_pattern("%Findbox") == "Findbox%",
      main.prefix_pattern("%Findbox"))

verified_plan = plan_of("/v1/sites", {"verified_only": True}, "deposits d")
# The obvious spelling of this filter is EXISTS, and EXISTS plans as
# SCAN d: it reads every deposit in the galaxy and asks each one whether it
# is verified. Driving off the verified set instead reads only those, which
# is why the endpoint spells it as a row-value IN.
check("verified only is driven off the verified rows, not filtered onto them",
      "SEARCH d USING" in verified_plan and "SCAN d" not in verified_plan,
      verified_plan)
check("and it is the status index that picks them out",
      "ix_dep_status" in verified_plan, verified_plan)

cube_plan = plan_of("/v1/sites", {"near_x": 0, "near_y": 0, "near_z": 0,
                                  "within_ly": 50}, "deposits d")
check("and a proximity search is still a cube served by the position index",
      "ix_systems_x" in cube_plan and "SCAN d" not in cube_plan, cube_plan)

print("== best sell prices work on a planet in the middle of nowhere ==")
# /v1/prices matched the commander's system with `system = ?`. You ask it
# standing on a body nobody has ever sold anything on, so it returned zero
# rows every single time - which reads as a broken feature, not as an empty
# system. The question was never "what sells HERE".
CRATER = {"system_address": 77777777701, "x": 10.0, "y": 0.0, "z": 0.0}
client.post("/v1/deposits", json=env([
    {"system": "Craterville", "planet": "C 9", "spot": "1", "type": "Olivine",
     "rigs": 6, "lat": 1.0, "lon": 1.0, **CRATER}]))
# Stations at the three positions the proximity tests above already pinned:
# Sol at the origin, Corner 69 Ly out through a cube corner, Faraway at 300.
client.post("/v1/market", json=market(2001, "Galileo", "Sol",
            [{"commodity": "Olivine", "sell": 40000, "demand": 800}]))
client.post("/v1/market", json=market(2002, "Corner Depot", "Corner",
            [{"commodity": "Olivine", "sell": 90000, "demand": 900}]))
client.post("/v1/market", json=market(2003, "Far Station", "Faraway",
            [{"commodity": "Olivine", "sell": 99000, "demand": 999}]))

takes = inspect.signature(main.prices).parameters
for axis in ("near_x", "near_y", "near_z", "within_ly"):
    check("the price search accepts %s" % axis, axis in takes, sorted(takes))
check("and still accepts the old exact-system parameter", "near" in takes,
      sorted(takes))

def priced(**params):
    body = client.get("/v1/prices", params=dict({"commodity": "Olivine"},
                                                **params)).json()
    return body["prices"]

standing_here = priced(near="Craterville")
check("asking by system name from an empty system answers with nothing",
      standing_here == [], standing_here)
# The fix, and the whole point of it: the same commander, the same spot,
# asking the question that has an answer.
nearby = priced(near_x=10, near_y=0, near_z=0, within_ly=50)
check("but asking by position finds the market 10 Ly away",
      [p["system"] for p in nearby] == ["Sol"], [p["system"] for p in nearby])
check("and says how far away it is",
      bool(nearby) and nearby[0].get("distance_ly") == 10.0, nearby[:1])
check("a station 300 Ly out is not near me",
      "Faraway" not in [p["system"] for p in nearby],
      [p["system"] for p in nearby])
# Corner is at (40,40,40): inside a 50 Ly cube and 69 Ly away. If the sphere
# is ever dropped and the cube shipped as the answer, this is what catches
# it - and it is the highest-priced row, so it would be at the top.
corner_reach = priced(near_x=0, near_y=0, near_z=0, within_ly=50)
check("a cube corner is not inside the sphere for prices either",
      "Corner" not in [p["system"] for p in corner_reach],
      [p["system"] for p in corner_reach])
wide = priced(near_x=0, near_y=0, near_z=0, within_ly=500)
check("widen the radius and the far markets come back",
      {"Corner", "Faraway"} <= set(p["system"] for p in wide),
      [p["system"] for p in wide])
check("and the best price is still first",
      [p["sell"] for p in wide] == sorted((p["sell"] for p in wide),
                                          reverse=True),
      [p["sell"] for p in wide])
check("the old exact-system question still gets its old answer",
      [p["system"] for p in priced(near="Sol")] == ["Sol"],
      [p["system"] for p in priced(near="Sol")])
check("asking with no position at all still answers",
      len(priced()) >= 3, len(priced()))
check("and those rows carry a null distance rather than a missing key",
      all("distance_ly" in p and p["distance_ly"] is None for p in priced()),
      priced()[:1])

print("== and so does /v1/sell ==")
takes = inspect.signature(main.sell).parameters
for axis in ("near_x", "near_y", "near_z"):
    check("the sell search accepts %s" % axis, axis in takes, sorted(takes))

def sold(**params):
    return client.get("/v1/sell", params=dict(
        {"commodity": "Olivine", "upstream": False}, **params)).json()

here_only = sold(near="Craterville")
check("our own prices from an empty system are empty too",
      here_only["community"] == [], here_only["community"])
by_position = sold(near_x=10, near_y=0, near_z=0, within_ly=50)
check("by position it finds the market 10 Ly away",
      [p["system"] for p in by_position["community"]] == ["Sol"],
      [p["system"] for p in by_position["community"]])
check("and carries the distance, so the app can sort on it",
      bool(by_position["community"])
      and by_position["community"][0].get("distance_ly") == 10.0,
      by_position["community"][:1])
check("the cube's corners are dropped here as well",
      "Corner" not in [p["system"] for p in
                       sold(near_x=0, near_y=0, near_z=0,
                            within_ly=50)["community"]],
      sold(near_x=0, near_y=0, near_z=0, within_ly=50)["community"])
check("a name prefix still works, because that is what it always did",
      [p["system"] for p in sold(near="Sol")["community"]] == ["Sol"],
      [p["system"] for p in sold(near="Sol")["community"]])

AT_ORIGIN = {"commodity": "Olivine", "near_x": 0, "near_y": 0, "near_z": 0,
             "within_ly": 50}
price_plan = plan_of("/v1/prices", AT_ORIGIN, "prices")
# A price row carries the system name and no address - the journal's Market
# event has none - so the cube is keyed on the name, and it needs an index
# on prices(system) or the search reads every price in the galaxy.
check("the price proximity search is bounded by an index",
      "SCAN prices" not in price_plan and "SEARCH prices" in price_plan,
      price_plan)
# Catches the cube being dropped altogether. It cannot be caught by asking
# the endpoint a question: the sphere pass in Python returns the right rows
# with or without it, just after reading every price ever uploaded.
check("the cube itself is served by the position index",
      "ix_systems_x" in price_plan, price_plan)
sell_plan = plan_of("/v1/sell", dict(AT_ORIGIN, upstream=False), "prices")
check("and /v1/sell asks the same bounded question",
      "ix_systems_x" in sell_plan and "SCAN prices" not in sell_plan, sell_plan)

conn = sqlite3.connect(DB)
indexes = {r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type = 'index'")}
for needed in ("ix_price_system", "ix_dep_status"):
    check("index %s exists" % needed, needed in indexes, sorted(indexes))
conn.close()

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
import shutil; shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fails else 0)
