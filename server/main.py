"""
Radio Raxxla surface mining deposit API - reference server.

The app posts deposits here and searches other commanders' finds. Inara has
no endpoint for surface mining deposits and EDDN has no schema for them, so
this fills the gap until one exists. The wire format deliberately mirrors an
EDDN envelope, so migrating later is a transport change, not a rewrite.

Run it:

    pip install fastapi uvicorn
    python main.py

Then point the app at http://your-host:8080

Storage is SQLite - one file, no database server, fine into the millions of
rows for this shape of data.

What this is FOR, which is narrower than it started out:

  depletion    The point. Deposit positions are generated offline - a
               deterministic sequence seeded on the body address - so a
               database of where the patches are has a shelf life measured
               in however long it takes somebody to publish the algorithm.
               Whether a patch has been stripped is the one value held on
               Frontier's servers and observable only by driving there. It
               is also the only thing anybody has an incentive to share,
               because the patch you are reporting is already gone.
  confidence   Not decay. Sites have been watched persisting unchanged,
               including across a hotfix, so age is not evidence a deposit
               vanished - it is our own uncertainty, and it is reported as
               that. Independent confirmations reduce it; independent
               depletion reports are what raise belief the patch is gone.
  density      4.4.1.0 balances rig efficiency and deposit capacity on it,
               so it is worth as much as the commodity name.

Nothing here presents a reformation countdown, because nobody has measured
one. Elapsed time since a site was reported stripped is a fact and is what
gets returned; the estimate that keeps a March crater from sitting at the
bottom of the list forever is a dial, and every response that leans on it
carries reformation_measured: false.

Prices are collected from users' own Market.json as well, and /v1/sell can
add a configured public market index on top of that - see the note above
SELL_UPSTREAM_BASE.
"""

import math
import os
import re
import sqlite3
import threading
import time
import unicodedata
import datetime as dt
from contextlib import closing

from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator
import uvicorn

DB_PATH = os.environ.get("RR_DB", "deposits.db")
WRITE_TOKEN = os.environ.get("RR_WRITE_TOKEN", "")     # empty = open submissions

# Who may mark a find verified. RR_STAFF="CMDR Jameson:sometoken,CMDR X:other"
# - a name against a secret, so the database records WHO confirmed a site and
# not merely that somebody did. Without that the badge is unaccountable, and
# an unaccountable badge is worth less than no badge.
def _staff_from_env(raw):
    people = {}
    for entry in str(raw or "").split(","):
        name, _, secret = entry.partition(":")
        name, secret = name.strip(), secret.strip()
        if name and secret:
            people[secret] = name
    return people


STAFF = _staff_from_env(os.environ.get("RR_STAFF", ""))
APP_VERSION = "1.10032"
SCHEMA_ID = "radioraxxla/surfacemining/1"
DEPLETION_SCHEMA = "radioraxxla/surfacemining-depletion/1"
MARKET_SCHEMA = "radioraxxla/surfacemining-market/1"
VERIFY_SCHEMA = "radioraxxla/surfacemining-verify/1"

# The thirteen from Frontier's 4.4.1.0 notes plus the ones actually seen
# coming out of the ground. The notes only listed what was NEW: surface
# mining also yields long-standing commodities, which is why a location can
# offer copper, haematite, lithium, palladium and uranium without any of them
# appearing in the update.
#
# These are the names we tidy TOWARDS, not a gate. Rejecting an unknown
# commodity would mean refusing a real find because the list was written by
# somebody who had not seen it yet - and this database exists precisely
# because nobody has seen it all yet.
COMMODITY_NAMES = [
    "Bastn\u00e4site", "Deuterium", "Diamond", "Helium", "Helium-3", "Iridium",
    "Magnesite", "Olivine", "Periclase dunite", "Quartz pyroxenite",
    "Ruby", "Sapphire", "Thortveitite",
    "Copper", "Haematite", "Lithium", "Palladium", "Uranium",
    "Alexandrite", "Aluminium", "Bauxite", "Benitoite", "Bertrandite",
    "Bismuth", "Bromellite", "Cobalt", "Coltan", "Gallite", "Gold",
    "Grandidierite", "Indite", "Lanthanum", "Lepidolite",
    "Low Temperature Diamonds", "Moissanite", "Monazite", "Musgravite",
    "Osmium", "Painite", "Platinum", "Praseodymium", "Rhodplumsite",
    "Rutile", "Samarium", "Serendibite", "Silver", "Thallium", "Thorium",
    "Titanium", "Tritium", "Uraninite", "Void Opals",
]

# How long a name may be before it is obviously not a commodity.
MAX_COMMODITY = 60


def fold(text) -> str:
    """Match commodity names loosely, so Bastn\u00e4site and Bastnasite are one
    commodity rather than two rows nobody can join up."""
    raw = unicodedata.normalize("NFKD", str(text))
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return "".join(c for c in raw.lower() if c.isalnum())


COMMODITIES = {fold(name): name for name in COMMODITY_NAMES}


def tidy_name(value: str) -> str:
    """Frontier's spelling where we know it, a cleaned-up one where we don't."""
    text = str(value or "").strip().strip("$;").replace("_name", "")
    if not text:
        raise ValueError("a commodity needs a name")
    if len(text) > MAX_COMMODITY:
        raise ValueError("that is not a commodity name")
    return COMMODITIES.get(fold(text)) or text.replace("_", " ").strip().title()

# Density tiers, kept in step with the app. Unknown labels are stored as
# given rather than rejected: Frontier have not published the real ones.
DENSITY_TIERS = ["Depleted", "Low", "Medium", "High", "Pristine"]
DENSITY_RANK = {fold(n): i for i, n in enumerate(DENSITY_TIERS)}
DENSITY_RANK.update({fold("very low"): 1, fold("moderate"): 2,
                     fold("very high"): 4, fold("rich"): 4, fold("major"): 4,
                     fold("minor"): 1, fold("common"): 2,
                     fold("exhausted"): 0, fold("empty"): 0})

# How fast confidence in a REPORT decays - not belief that the deposit went
# away. The distinction is the whole point: the community field guide has
# sites persisting unchanged, including across a hotfix, so a three-month-old
# sighting is almost certainly still true. What ages is our right to state it
# as fact. Halving every three weeks is a statement about the report.
HALF_LIFE_DAYS = float(os.environ.get("RR_HALF_LIFE_DAYS", "21"))

# How much doubt survives one commander saying a site is stripped. Two
# independent commanders is far stronger evidence than one, so the doubt is
# raised to the power of the number of reporters: one report leaves 1%
# doubt, two leaves 0.01%.
#
# 1%, not 5%, and the reason is arithmetic rather than taste. The score is
# raw size multiplied by this, so at 5% a SIX-COMMODITY TWENTY-RIG site
# somebody has stood on and found empty still outscored a small site nobody
# had visited in a month. Size was rescuing a known crater. A commander
# standing on the thing reporting it empty is strong evidence, and the
# whole premise of this database is that the depletion answer outranks the
# size answer - so it has to actually outrank it.
UNCORROBORATED_DOUBT = float(os.environ.get("RR_DEPLETION_DOUBT", "0.01"))

# How long a stripped site MIGHT take to be worth the trip again.
#
# This is a guess and the API says so. The field guide is flat about it -
# the reformation timer is "Not established", one site has been under timed
# watch since 6 September and nothing has been measured. So this number
# exists only to stop a site that was emptied in March outranking nothing
# forever; it is never presented as a countdown, and every response that
# leans on it carries reformation_measured: false beside it. What the API
# reports as fact is the elapsed time since the site was reported stripped.
#
# RR_REGEN_DAYS is still read so an existing box's environment keeps working.
REFORMATION_ESTIMATE_DAYS = float(
    os.environ.get("RR_REFORMATION_ESTIMATE_DAYS")
    or os.environ.get("RR_REGEN_DAYS", "60"))

# Nobody has watched a stripped site come back. Until somebody has, this
# stays False and travels with every figure derived from the estimate above.
REFORMATION_MEASURED = False

# Version tracks the app it serves - EDSMT 1.0 - so /v1/health answers
# "which build is this" without anyone having to guess.
app = FastAPI(title="EDSMT community API", version=APP_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


# ---------------------------------------------------------------- models

class Deposit(BaseModel):
    system: str = Field(min_length=1, max_length=120)
    planet: str = Field(min_length=1, max_length=120)
    spot: str = Field(default="1", max_length=40)
    type: str = Field(min_length=1, max_length=60)
    # Zero means "not counted yet" - you cannot know how many rigs a deposit
    # takes until you have driven to it, and a find is worth sharing before
    # then.
    rigs: int = Field(default=0, ge=0, le=6)
    # Where it is. The app takes these from the game, so they are the
    # identity of a deposit and everything else is description.
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    # Bearing and range from a spot centre. The app no longer works that
    # way - there is no centre to measure from - but rows uploaded by the
    # older build carry them, so they are still accepted and still stored.
    # Optional, and never used to decide whether two finds are the same.
    direction: float | None = Field(default=None, ge=0, lt=360)
    distance: float | None = Field(default=None, ge=0, le=1000)
    density: str = Field(default="", max_length=40)
    # How much is LEFT, as opposed to how rich it is. Different questions,
    # and a site can be High density and Depleted at once.
    amount: str = Field(default="", max_length=40)
    temperature_k: float | None = Field(default=None, ge=0, le=100000)

    # What kind of world it is. Nobody has published which surface deposits
    # favour which bodies, because nobody has been collecting both halves at
    # once. These are what make that answerable.
    planet_class: str = Field(default="", max_length=80)
    gravity: float | None = Field(default=None, ge=0, le=100)
    atmosphere: str = Field(default="", max_length=80)
    volcanism: str = Field(default="", max_length=80)

    # Where the system is, and Frontier's own id for it. The galaxy has
    # 400 billion systems, so "the best site anywhere" is never the
    # question - it is 40,000 Ly away and nobody is going. Without these
    # the database cannot answer the only question that matters, which is
    # what is near me. Optional: rows from older builds have neither.
    system_address: int | None = Field(default=None, ge=0)
    x: float | None = Field(default=None, ge=-100000, le=100000)
    y: float | None = Field(default=None, ge=-100000, le=100000)
    z: float | None = Field(default=None, ge=-100000, le=100000)

    # Who stands behind it. Set by the server on verification, never by the
    # uploader - an app that could mark its own rows verified would make the
    # word worthless.
    status: str = Field(default="reported", max_length=20)
    notes: str = Field(default="", max_length=280)

    @field_validator("type")
    @classmethod
    def tidy_commodity(cls, v):
        """Tidy the spelling. Never refuse a find over an unknown name.

        The fold matters: without it "Bastnasite" typed by hand and
        "Bastn\u00e4site" from the journal become two commodities and every
        search returns half the data. But an unrecognised name is stored as
        given - the alternative is throwing away the first sighting of
        something Frontier added and nobody has catalogued yet.
        """
        return tidy_name(v)


class Header_(BaseModel):
    uploaderID: str = ""
    softwareName: str = ""
    softwareVersion: str = ""
    gatewayTimestamp: str = ""
    # Which build of Elite Dangerous the commander was running, straight off
    # the journal Fileheader. The field guide asks for this explicitly and it
    # is the cheapest insurance this database can buy: when a hotfix changes
    # how deposits behave, every row collected before it is still readable
    # because it says which game it came from. 4.4.1.1 raised chunks per rig
    # from 9 to 12 one day after launch, and nothing recorded on 2 September
    # can be compared with anything recorded on 3 September without it.
    #
    # Optional, and it has to stay optional: every client shipped so far
    # sends a header without it, and an upload that 422s because the app is
    # a build behind is worse than an upload with a blank version.
    gameVersion: str = Field(default="", max_length=40)


class Message(BaseModel):
    deposits: list[Deposit] = Field(min_length=1, max_length=500)


class Upload(BaseModel):
    schema_: str = Field(alias="$schema", default=SCHEMA_ID)
    header: Header_ = Header_()
    message: Message


class DepletionMessage(BaseModel):
    system: str = Field(min_length=1, max_length=120)
    planet: str = Field(min_length=1, max_length=120)
    spot: str = Field(default="1", max_length=40)
    worked_out: bool = True


class DepletionUpload(BaseModel):
    schema_: str = Field(alias="$schema", default=DEPLETION_SCHEMA)
    header: Header_ = Header_()
    message: DepletionMessage


class PriceItem(BaseModel):
    commodity: str = Field(min_length=1, max_length=60)
    sell: int = Field(default=0, ge=0, le=100_000_000)
    buy: int = Field(default=0, ge=0, le=100_000_000)
    demand: int = Field(default=0, ge=0)
    stock: int = Field(default=0, ge=0)
    demand_bracket: int | None = None

    @field_validator("commodity")
    @classmethod
    def tidy_commodity(cls, v):
        return tidy_name(v)


class MarketMessage(BaseModel):
    market_id: int | None = None
    station: str = Field(default="", max_length=120)
    system: str = Field(default="", max_length=120)
    station_type: str = Field(default="", max_length=60)
    when: str = Field(default="", max_length=40)
    items: list[PriceItem] = Field(min_length=1, max_length=200)


class MarketUpload(BaseModel):
    schema_: str = Field(alias="$schema", default=MARKET_SCHEMA)
    header: Header_ = Header_()
    message: MarketMessage


# ------------------------------------------------------------- storage

DDL = """
CREATE TABLE IF NOT EXISTS deposits (
    id         INTEGER PRIMARY KEY,
    system     TEXT NOT NULL COLLATE NOCASE,
    planet     TEXT NOT NULL COLLATE NOCASE,
    spot       TEXT NOT NULL COLLATE NOCASE,
    type       TEXT NOT NULL COLLATE NOCASE,
    rigs       INTEGER NOT NULL,
    direction  REAL NOT NULL,
    distance   REAL NOT NULL,
    lat        REAL,
    lon        REAL,
    notes      TEXT DEFAULT '',
    uploader   TEXT DEFAULT '',
    software   TEXT DEFAULT '',
    created    TEXT NOT NULL,
    fingerprint TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS ix_type   ON deposits(type);
CREATE INDEX IF NOT EXISTS ix_system ON deposits(system);
CREATE INDEX IF NOT EXISTS ix_body   ON deposits(system, planet, spot);

CREATE TABLE IF NOT EXISTS sites (
    system     TEXT NOT NULL COLLATE NOCASE,
    planet     TEXT NOT NULL COLLATE NOCASE,
    spot       TEXT NOT NULL COLLATE NOCASE,
    last_seen  TEXT NOT NULL,
    depleted   TEXT DEFAULT '',
    reports    INTEGER DEFAULT 0,
    PRIMARY KEY (system, planet, spot)
);

-- Who says a site is stripped. One row per commander per site, so that the
-- second commander to report it is real corroboration and the same commander
-- reporting it twice is not.
--
-- Anonymous reporters all share the empty name and therefore collapse to a
-- single row. That is deliberate and conservative: two anonymous reports
-- cannot be shown to be two different people, so they are not counted as
-- two. Sharing a CMDR name is optional and must stay optional, and the price
-- of staying anonymous is that you cannot corroborate yourself.
CREATE TABLE IF NOT EXISTS depletion_reports (
    system     TEXT NOT NULL COLLATE NOCASE,
    planet     TEXT NOT NULL COLLATE NOCASE,
    spot       TEXT NOT NULL COLLATE NOCASE,
    uploader   TEXT NOT NULL DEFAULT '' COLLATE NOCASE,
    reported   TEXT NOT NULL,
    game_version TEXT DEFAULT '',
    PRIMARY KEY (system, planet, spot, uploader)
);

CREATE TABLE IF NOT EXISTS prices (
    market_id  INTEGER NOT NULL,
    commodity  TEXT NOT NULL COLLATE NOCASE,
    station    TEXT DEFAULT '',
    system     TEXT DEFAULT '' COLLATE NOCASE,
    sell       INTEGER NOT NULL,
    buy        INTEGER DEFAULT 0,
    demand     INTEGER DEFAULT 0,
    seen       TEXT NOT NULL,
    uploader   TEXT DEFAULT '',
    PRIMARY KEY (market_id, commodity)
);
CREATE INDEX IF NOT EXISTS ix_price_commodity ON prices(commodity, sell DESC);

-- Where every system anyone has uploaded from actually is. Keyed on
-- Frontier's address rather than the name: names collide on case and
-- spelling, the address never does.
CREATE TABLE IF NOT EXISTS systems (
    address    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL COLLATE NOCASE,
    x          REAL NOT NULL,
    y          REAL NOT NULL,
    z          REAL NOT NULL,
    seen       TEXT NOT NULL
);
-- A proximity search is a cube first and a sphere afterwards. The cube is
-- what an index can serve, and x alone cuts the galaxy down far enough
-- that the other two are cheap.
CREATE INDEX IF NOT EXISTS ix_systems_x    ON systems(x);
CREATE INDEX IF NOT EXISTS ix_systems_name ON systems(name);
"""

# Columns added after the first release. SQLite has no "ADD COLUMN IF NOT
# EXISTS", and an existing box must not need its database thrown away.
ADDED_COLUMNS = [
    ("deposits", "density", "TEXT DEFAULT ''"),
    ("deposits", "temperature_k", "REAL"),
    ("deposits", "amount", "TEXT DEFAULT ''"),
    ("deposits", "planet_class", "TEXT DEFAULT '' COLLATE NOCASE"),
    ("deposits", "gravity", "REAL"),
    ("deposits", "atmosphere", "TEXT DEFAULT ''"),
    ("deposits", "volcanism", "TEXT DEFAULT ''"),
    ("deposits", "status", "TEXT DEFAULT 'reported'"),
    ("deposits", "verified_by", "TEXT DEFAULT ''"),
    ("deposits", "verified_at", "TEXT DEFAULT ''"),
    # Ranked once on the way in rather than on every single search. The
    # ranking used to happen in Python, per row, per query, which is why
    # the score could not be computed in SQL and the search could not be
    # bounded by it.
    ("deposits", "density_rank", "REAL"),
    ("deposits", "system_address", "INTEGER"),
    # Which build of the game the find came from. Blank on every row
    # collected before this existed, which is honest - we genuinely do not
    # know - and blank on any client that does not send it.
    ("deposits", "game_version", "TEXT DEFAULT ''"),
    ("sites", "status", "TEXT DEFAULT 'reported'"),
    ("sites", "verified_by", "TEXT DEFAULT ''"),
    ("sites", "verified_at", "TEXT DEFAULT ''"),
    ("sites", "game_version", "TEXT DEFAULT ''"),
    # The depletion episode currently running at this site. `depleted` was
    # already the flag; these say how well attested it is and how long it has
    # been going, which is the only thing anybody can honestly state about a
    # stripped patch while the reformation timer is unmeasured.
    ("sites", "depleted_last", "TEXT DEFAULT ''"),
    ("sites", "depleted_reporters", "INTEGER DEFAULT 0"),
    ("prices", "game_version", "TEXT DEFAULT ''"),
]


def migrate(conn):
    # Per table, not one snapshot of `deposits`. The old version read the
    # column list of `deposits` once and tested every entry against it, so a
    # column added to `sites` was skipped whenever `deposits` happened to
    # have one of the same name - which is how game_version, depleted_last
    # and depleted_reporters would all have been missed on a box that had
    # already taken the deposits half of this migration.
    have: dict[str, set] = {}
    for table, column, spec in ADDED_COLUMNS:
        if table not in have:
            have[table] = {row["name"]
                           for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in have[table]:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {spec}")
            have[table].add(column)
    # Sites that predate the sites table still deserve a last_seen, taken
    # from the newest deposit anyone logged there.
    conn.execute("""INSERT OR IGNORE INTO sites (system, planet, spot, last_seen)
                    SELECT system, planet, spot, MAX(created)
                    FROM deposits GROUP BY system, planet, spot""")

    # Rank every density that predates the column, once. NULL means "never
    # ranked"; a deposit with no density recorded gets the neutral 2.0 the
    # Python scorer used to substitute, so old and new rows score alike.
    for text, rank in DENSITY_RANK.items():
        conn.execute("UPDATE deposits SET density_rank = ? "
                     "WHERE density_rank IS NULL AND lower(trim(density)) = ?",
                     (float(rank), text))
    # Deliberately NOT backfilled to a neutral value: AVG() skips NULLs,
    # and the scorer's fallback applies to a site with no densities at all,
    # not to every individual deposit that is missing one.

    # Indexes that were missing. Every one of these backs a query that was
    # scanning the whole table: the site roll-up, the deposit search's sort,
    # and the age filter.
    for statement in (
        "CREATE INDEX IF NOT EXISTS ix_dep_addr ON deposits(system_address)",
        "CREATE INDEX IF NOT EXISTS ix_dep_type_rigs ON deposits(type, rigs DESC)",
        "CREATE INDEX IF NOT EXISTS ix_dep_created ON deposits(created DESC)",
        "CREATE INDEX IF NOT EXISTS ix_sites_seen ON sites(last_seen DESC)",
        "CREATE INDEX IF NOT EXISTS ix_sites_depleted ON sites(depleted)",
        # Backs the "verified only" filter. The site keys are carried in the
        # index itself so the filter can be answered by reading the verified
        # rows alone, instead of rolling up every deposit in the galaxy and
        # then throwing almost all of it away. Verification is a staff
        # action, so that set stays small however big the table gets.
        "CREATE INDEX IF NOT EXISTS ix_dep_status "
        "ON deposits(status, system, planet, spot)",
        # Backs the proximity price search. Without it, "where does this
        # sell near me" had no key to search on but the commodity, so a
        # commodity nobody has priced still read the whole price table.
        "CREATE INDEX IF NOT EXISTS ix_price_system ON prices(system, sell DESC)",
        # Bodies, on their own. ix_body starts with the system, so it cannot
        # serve "which sites are on a body called Ega 1" - and without an
        # index on planet alone, SQLite gives up on the whole OR below and
        # reads every deposit in the galaxy. With both indexes present it
        # takes the OR apart and searches each half. See /v1/sites.
        "CREATE INDEX IF NOT EXISTS ix_dep_planet ON deposits(planet)",
    ):
        conn.execute(statement)

    # Sites that were already flagged stripped before anybody was counting
    # reporters. One report is what we can honestly claim - we know somebody
    # said so, we no longer know who - so it goes in under the anonymous
    # name and the site scores as singly-attested rather than as corroborated.
    conn.execute("""INSERT OR IGNORE INTO depletion_reports
                      (system, planet, spot, uploader, reported)
                    SELECT system, planet, spot, '', depleted FROM sites
                    WHERE COALESCE(depleted, '') <> ''""")
    conn.execute("""UPDATE sites SET depleted_last = depleted
                    WHERE COALESCE(depleted, '') <> ''
                      AND COALESCE(depleted_last, '') = ''""")
    conn.execute("""UPDATE sites SET depleted_reporters = (
                        SELECT COUNT(*) FROM depletion_reports r
                        WHERE r.system = sites.system AND r.planet = sites.planet
                          AND r.spot = sites.spot)""")
    conn.commit()


def remember_system(conn, address, name, x, y, z, now):
    """File where a system is, the first time anybody uploads from it.

    Re-stating it is cheap and self-healing: if a row ever went in with bad
    coordinates, the next upload from that system corrects it.
    """
    if address is None or x is None or y is None or z is None:
        return
    conn.execute(
        """INSERT INTO systems (address, name, x, y, z, seen)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(address) DO UPDATE SET
               name = excluded.name, x = excluded.x,
               y = excluded.y, z = excluded.z, seen = excluded.seen""",
        (int(address), str(name), float(x), float(y), float(z), now))


def density_rank(value):
    return DENSITY_RANK.get(fold(value or ""), None)


# How many candidate rows the ranked search considers before the Python
# decay runs. The decay only ever multiplies a score DOWN (freshness and
# regen are both <= 1), so anything outside the top N by raw score can
# never beat the worst row inside it. The pool is therefore not an
# approximation - it is the smallest set that provably contains the answer.
POOL_MULTIPLIER = 20
POOL_FLOOR = 500


def near_clause(x, y, z, within_ly, column="d.system_address", key="address"):
    """SQL that keeps only systems inside a cube around a point.

    A cube, not a sphere, because a cube is what an index can serve. The
    sphere is applied afterwards on a handful of rows. Without this every
    search reads the whole galaxy; with it, the database getting bigger
    does not make the search slower, because the search was never looking
    outside the box.

    `key` is what the calling table stores. Deposits carry Frontier's system
    address and match on that, which is exact. A market reading carries only
    the system NAME - the journal's Market event has no address in it - so
    prices match on `name` instead. Name is the weaker key of the two, and
    it is the only one those rows have; the alternative was to make the
    price search impossible, which is the bug this argument exists to fix.
    """
    if x is None or y is None or z is None or not within_ly:
        return "", []
    r = float(within_ly)
    sql = (f" AND {column} IN (SELECT {key} FROM systems"
           "  WHERE x BETWEEN ? AND ? AND y BETWEEN ? AND ? AND z BETWEEN ? AND ?)")
    return sql, [x - r, x + r, y - r, y + r, z - r, z + r]


def light_years(a, b):
    """Straight-line distance between two galactic positions."""
    if not a or not b:
        return None
    return math.sqrt(sum((p - q) ** 2 for p, q in zip(a, b)))


def positions_by_name(conn, names) -> dict:
    """Where each of these systems is, keyed by the folded name.

    Chunked at 400 because SQLite's default parameter ceiling is 999 and a
    busy market upload can easily name more stations than that. Folded on
    both sides so that "shinrarta dezhra" off a price row still finds the
    "Shinrarta Dezhra" somebody uploaded a deposit from - the columns are
    COLLATE NOCASE but a dict lookup in Python is not.
    """
    wanted = sorted({str(n) for n in names if n})
    found = {}
    for i in range(0, len(wanted), 400):
        chunk = wanted[i:i + 400]
        marks = ",".join("?" * len(chunk))
        for r in conn.execute("SELECT name, x, y, z FROM systems "
                              "WHERE name IN (%s)" % marks, chunk):
            found[fold(r["name"])] = (r["x"], r["y"], r["z"])
    return found


def price_distances(conn, rows, here, within_ly):
    """How far each priced station is, and the cube's corners thrown away.

    The cube an index can serve is 1.9x the volume of the sphere somebody
    actually asked for, so without this a "within 50 Ly" price search
    quietly answers with stations 86 Ly out - the same trap /v1/sites
    already guards against.

    A station whose system nobody has uploaded a position for gets a null
    distance and is dropped from a proximity search. That is the honest
    outcome: we do not know where it is, so we cannot claim it is near you.
    Ask without a position and it comes back like any other row.
    """
    if not here:
        for r in rows:
            r.setdefault("distance_ly", None)
        return rows
    where = positions_by_name(conn, (r.get("system") for r in rows))
    kept = []
    for r in rows:
        distance = light_years(here, where.get(fold(r.get("system") or "")))
        if distance is None or (within_ly and distance > within_ly):
            continue
        r["distance_ly"] = round(distance, 2)
        kept.append(r)
    return kept


def prefix_pattern(value: str) -> str:
    """A LIKE pattern for "starts with this", that an index can still serve.

    Three things have to be true at once and all three are load-bearing:

      * the pattern is built HERE and bound whole. `system LIKE ? || '%'` is
        an expression rather than a bound string, and SQLite will not use an
        index for it - EXPLAIN QUERY PLAN drops straight to SCAN.
      * the column is COLLATE NOCASE and so is its index, which is what lets
        a case-insensitive LIKE use it at all.
      * there is no leading wildcard. A pattern that starts with % or _ turns
        the search box into a full table scan of the whole galaxy, so leading
        wildcards are stripped. Nobody types one on purpose, and no Elite
        system name contains either character.
    """
    return str(value or "").lstrip("%_") + "%"


def report_confidence(last_confirmed: str, now: float | None = None,
                      corroboration: int = 1) -> float:
    """How far to trust the REPORT that this site is there. Not whether it is.

    The difference is not pedantry. The old reading of this number was that a
    deposit decays away, so a three-month-old find is probably gone. The
    community field guide says the opposite: sites have been watched
    persisting unchanged, including across a hotfix. What actually ages is
    our right to state it - nobody has looked since, so we say so, and we say
    it with a number rather than a shrug.

    Independent confirmations halve the doubt rather than resetting the
    clock. Two commanders who both logged deposits at a site leave half as
    much room to be wrong as one did, however old the sighting is.
    """
    stamp = to_epoch(last_confirmed)
    if not stamp:
        return 1.0
    now = now if now is not None else dt.datetime.now(dt.timezone.utc).timestamp()
    age_days = max(0.0, (now - stamp) / 86400.0)
    confidence = 0.5 ** (age_days / HALF_LIFE_DAYS)
    extra = max(0, int(corroboration or 1) - 1)
    return 1.0 - (1.0 - confidence) * (0.5 ** extra)


def freshness(last_seen: str, now: float | None = None) -> float:
    """Kept under the old name for anything still calling it.

    It never meant what it said. It is confidence in a single uncorroborated
    report, which is why it is now spelled that way everywhere else.
    """
    return report_confidence(last_seen, now)


def stripped_belief(reporters: int) -> float:
    """How sure we are a site has been worked out, given who said so.

    u/zeek215 named the problem this database exists for: one player mining
    a patch empties it for everyone, so nobody wants to share a good one.
    Nobody minds sharing a dead one - the patch is already gone - which is
    why this is the number the community will actually feed.

    One report is an observation, two is a fact. The doubt is compounded, so
    corroboration bites hard rather than nudging a rank.
    """
    n = max(0, int(reporters or 0))
    if not n:
        return 0.0
    return 1.0 - UNCORROBORATED_DOUBT ** n


def assumed_recovery(depleted_at: str, now: float | None = None) -> float:
    """The guess, kept in one place and labelled.

    Fraction of the UNMEASURED reformation estimate that has elapsed since a
    site was reported stripped. It exists so a patch emptied in March does
    not sit at the bottom of the list forever, and for nothing else. It is
    never returned without reformation_measured: false beside it, and the
    elapsed days are returned as well so a reader can ignore this entirely.
    """
    stamp = to_epoch(depleted_at)
    if not stamp or REFORMATION_ESTIMATE_DAYS <= 0:
        return 0.0
    now = now if now is not None else dt.datetime.now(dt.timezone.utc).timestamp()
    elapsed = max(0.0, (now - stamp) / 86400.0)
    return min(1.0, elapsed / REFORMATION_ESTIMATE_DAYS)


def intact_confidence(last_confirmed: str, depleted_at: str,
                      reporters: int = 0, corroboration: int = 1,
                      now: float | None = None) -> float:
    """Is this patch still worth the trip? One number, 0 to 1.

    A mixture of the two things we actually know about a site:

      * with probability (1 - stripped_belief) nobody has reported it
        emptied, and then all that is in question is how old the sighting
        is - report_confidence;
      * with probability stripped_belief somebody has, and then the only
        thing that can put it back is reformation, which nobody has
        measured. assumed_recovery is that guess, and it is a guess.

    Which means a freshly stripped site scores near zero, a site stripped
    long ago climbs slowly back towards its confirmed value, and a site
    nobody has touched keeps its value and simply gets less certain.
    """
    belief = stripped_belief(reporters) if depleted_at else 0.0
    present = report_confidence(last_confirmed, now, corroboration)
    if not belief:
        return present
    return belief * assumed_recovery(depleted_at, now) + (1.0 - belief) * present


def to_epoch(text: str) -> float:
    text = (text or "").strip()
    if not text:
        return 0.0
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def connect():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    except sqlite3.OperationalError as problem:
        # Almost always the same thing, and "unable to open database file"
        # says none of it: Docker created the mounted folder as root, the
        # container runs as an unprivileged user, and SQLite cannot write
        # there. Say so
        # rather than leaving somebody to guess at 2am.
        folder = os.path.dirname(os.path.abspath(DB_PATH)) or "."
        raise RuntimeError(
            "cannot open the database at %s (%s).\n"
            "If this is the container: the mounted folder has to be writable "
            "by the user the container runs as.\n"
            "    sudo chown -R <that uid>:<that gid> %s\n"
            "then bring it up again."
            % (DB_PATH, problem, folder)) from problem


def fingerprint(d: Deposit) -> str:
    """Identity of a deposit, so the same find is not stored twice.

    Coordinates are bucketed before hashing, because two commanders logging
    the same deposit never stand in the same place - they park where they
    park. Three decimal places is roughly 35 m of latitude on a small rocky
    body, which comfortably absorbs that while staying far below the spacing
    between real deposits: the ones in a live site sat 896 m, 1.26 km and
    1.47 km apart.

    Getting this wrong in the other direction is the expensive mistake. An
    earlier build sent a bearing and a range from a spot centre it no longer
    computes, so every deposit arrived as 0/0 - which made every find of the
    same commodity at the same site look like the same deposit, and the
    second one onwards was silently discarded as a duplicate.
    """
    key = [d.system.lower().strip(), d.planet.lower().strip(),
           d.spot.lower().strip(), d.type.lower().strip()]
    if d.lat is not None and d.lon is not None:
        key += [f"{d.lat:.3f}", f"{d.lon:.3f}"]
    elif d.direction is not None and d.distance is not None:
        # a row from the older build, kept working
        key += [f"{round(d.direction / 5) * 5:.0f}", f"{d.distance:.1f}"]
    else:
        # No position at all. One such row per commodity per site, which is
        # all the information there is in it.
        key += ["nopos"]
    return "|".join(key)


with closing(connect()) as _c:
    _c.executescript(DDL)
    migrate(_c)
    _c.commit()


# -------------------------------------------------------------- routes

LANDING = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EDSMT Community Map &mdash; Radio Raxxla</title>
<meta name="description" content="The shared surface mining deposit map for Elite Dangerous, collected by commanders running EDSMT.">
<meta name="theme-color" content="#050505">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&amp;family=Share+Tech+Mono&amp;display=swap">
<style>
:root{--void:#050505;--hull:#0a0908;--panel:#100e0b;--signal:#ff7a18;
--paper:#ffb56a;--mute:#c46e28;--faint:#7a4518;--line:rgba(255,122,24,.38);
--ok:#4ad991;--display:'Rajdhani',system-ui,sans-serif;
--mono:'Share Tech Mono',ui-monospace,Consolas,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--void);color:var(--paper);font-family:var(--display);
font-size:17px;line-height:1.6;padding-inline:20px;overflow-x:hidden}
.scan{pointer-events:none;position:fixed;inset:0;z-index:40;opacity:.45;
background:repeating-linear-gradient(to bottom,rgba(5,5,5,.22) 0,rgba(5,5,5,.22) 1px,transparent 1px,transparent 3px)}
.vig{pointer-events:none;position:fixed;inset:0;z-index:39;
background:radial-gradient(ellipse at center,transparent 38%,rgba(5,5,5,.72) 100%)}
.wrap{max-width:960px;margin:0 auto}
h1{font-size:clamp(2.2rem,1.4rem+3vw,3.6rem);letter-spacing:.05em;text-transform:uppercase;
margin:10px 0 14px;color:var(--paper);text-shadow:0 0 18px rgba(255,122,24,.5);line-height:1}
h2{font-size:1.25rem;letter-spacing:.1em;text-transform:uppercase;color:var(--signal);margin:0 0 6px}
p{max-width:66ch;margin:0 0 14px}
a{color:var(--signal)}
.lab{font-family:var(--mono);font-size:.7rem;letter-spacing:.22em;text-transform:uppercase;color:var(--mute)}
nav,.strip{max-width:960px;margin:0 auto;border-bottom:1px solid var(--line)}
nav{padding:16px 0 14px;display:flex;gap:22px;align-items:center;flex-wrap:wrap}
nav b{letter-spacing:.16em;text-transform:uppercase;font-size:15px}
nav a{font-family:var(--mono);font-size:11px;letter-spacing:.2em;text-transform:uppercase;
color:var(--mute);text-decoration:none}
nav a:hover{color:var(--signal)}
.strip{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:8px 0;
font-family:var(--mono);font-size:10.5px;letter-spacing:.2em;color:var(--faint);text-transform:uppercase}
section{border-top:1px solid var(--line);padding:44px 0}
section:first-of-type{border-top:none}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1px;
background:var(--line);border:1px solid var(--line);margin:24px 0}
.stats div{background:var(--hull);padding:20px 22px}
.stats .n{font-family:var(--mono);font-size:2rem;color:var(--signal);display:block;line-height:1}
.stats .k{font-family:var(--mono);font-size:10.5px;letter-spacing:.2em;color:var(--faint);
text-transform:uppercase;display:block;margin-top:8px}
table{border-collapse:collapse;width:100%;font-family:var(--mono);font-size:13px;
border:1px solid var(--line);margin-top:10px}
td{padding:10px 14px;border-bottom:1px solid var(--line);color:var(--paper)}
tr:last-child td{border-bottom:none}
td.m{color:var(--signal);white-space:nowrap;width:1%}
td.d{color:var(--faint)}
.cta{font-family:var(--mono);font-size:12.5px;letter-spacing:.18em;text-transform:uppercase;
text-decoration:none;padding:14px 24px;border:1px solid var(--signal);color:var(--paper);
display:inline-block;margin:6px 8px 6px 0;
background:linear-gradient(180deg,rgba(255,122,24,.22),rgba(255,122,24,.08))}
.cta.ghost{background:transparent;border-color:var(--line);color:var(--mute)}
footer{border-top:1px solid var(--line);padding:24px 0 60px;max-width:960px;margin:0 auto;
font-family:var(--mono);font-size:11px;letter-spacing:.14em;color:var(--faint);text-transform:uppercase}
@media(max-width:600px){section{padding:34px 0}}
</style></head><body>
<div class="scan"></div><div class="vig"></div>
<nav><b>Radio Raxxla</b>
<a href="https://radioraxxla.com/">Relay</a>
<a href="https://radioraxxla.com/EDSMT/">Mining Map</a>
<a href="/docs">API docs</a></nav>
<div class="strip"><span>Community map</span><span>Schema __SCHEMA__</span><span>v__VERSION__</span></div>
<div class="wrap">
<section>
  <span class="lab">Uplink &middot; open</span>
  <h1>EDSMT<br>Community Map</h1>
  <p>The shared record of surface mining deposits in Elite Dangerous, built by
  commanders running <a href="https://radioraxxla.com/EDSMT/">EDSMT</a>. Nobody
  else is collecting this &mdash; ring hotspots have been mapped to death,
  surface mining has nothing.</p>
  <div class="stats">
    <div><span class="n">__DEPOSITS__</span><span class="k">Deposits</span></div>
    <div><span class="n">__SITES__</span><span class="k">Sites</span></div>
    <div><span class="n">__PRICES__</span><span class="k">Market prices</span></div>
  </div>
  <a class="cta" href="https://radioraxxla.com/EDSMT/">Get EDSMT</a>
  <a class="cta ghost" href="/docs">API documentation</a>
</section>
<section>
  <h2>Using the data</h2>
  <p class="lab" style="margin-bottom:18px">Open, no key, no sign-up</p>
  <p>Reading is open to anyone &mdash; build against it, mirror it, or run your
  own copy. Submissions are open too: there is no write token, because a
  community map that gatekeeps contributions does not get any.</p>
  <table>
    <tr><td class="m">GET /v1/health</td><td class="d">Up, which build, and row counts</td></tr>
    <tr><td class="m">GET /v1/commodities</td><td class="d">Every commodity, priced, by body class</td></tr>
    <tr><td class="m">GET /v1/deposits</td><td class="d">Individual finds &mdash; filter by commodity and system</td></tr>
    <tr><td class="m">GET /v1/sites</td><td class="d">Ranked sites, confidence priced in</td></tr>
    <tr><td class="m">GET /v1/intact</td><td class="d">Which patches are most likely still there</td></tr>
    <tr><td class="m">GET /v1/sell</td><td class="d">Where it sells highest, near you</td></tr>
    <tr><td class="m">GET /v1/prices</td><td class="d">Commander market reads, unblended</td></tr>
    <tr><td class="m">POST /v1/deposits</td><td class="d">Share what you mapped</td></tr>
    <tr><td class="m">POST /v1/depletion</td><td class="d">Say a patch is stripped &mdash; the useful one</td></tr>
    <tr><td class="m">POST /v1/wing/{code}</td><td class="d">Wing link (beta) &mdash; see each other&rsquo;s Rhinos and rigs; nothing kept</td></tr>
  </table>
</section>
<section>
  <h2>Is it still there</h2>
  <p class="lab" style="margin-bottom:18px">The only question worth a server</p>
  <p>Where a patch is can be worked out. Whether the last commander through
  took the lot cannot - the only way to know is that somebody drove there
  and said so.</p>
  <p>That is what this collects. Reporting a patch you emptied costs you
  nothing &mdash; it is already gone &mdash; which is why it is the one thing
  people will actually share.</p>
  <p>Two commanders reporting a site stripped is a different claim from one,
  so the count travels with the flag. Nobody has measured how long a
  stripped patch takes to come back, so there is no countdown anywhere in
  this API. You get the elapsed time since it was reported
  emptied, and a flag saying the reformation timer is unmeasured.</p>
  <p>Age decays confidence in the <em>report</em>, not belief that the
  deposit vanished.</p>
  <p>Verification cannot be self-awarded. An upload claiming to be verified is
  stored as reported regardless; the badge is granted server-side to a named
  person holding a staff key, and the database records who. An unaccountable
  badge is worth less than no badge.</p>
</section>
</div>
<footer>Radio Raxxla &middot; EDSMT community map &middot; GPL-3.0 &mdash;
Not affiliated with Frontier Developments. Elite Dangerous is a trademark of
Frontier Developments plc.</footer>
</body></html>"""


@app.get("/", response_model=None)
def index(accept: str = Header(default="")):
    """What this is.

    A browser gets a page; anything else gets JSON. Content negotiation
    rather than two URLs, because the address people will type, paste into
    Discord and see in their firewall log is this one - and answering it
    with a wall of raw JSON tells a human nothing about what the traffic
    from EDSMT actually is.
    """
    with closing(connect()) as c:
        counts = {
            "deposits": c.execute("SELECT COUNT(*) AS n FROM deposits").fetchone()["n"],
            "sites": c.execute("SELECT COUNT(*) AS n FROM sites").fetchone()["n"],
            "prices": c.execute("SELECT COUNT(*) AS n FROM prices").fetchone()["n"],
        }
    # Vary: Accept is NOT optional here. One URL with two representations
    # may sit behind a cache; without this it is free to store whichever
    # it saw first and hand JSON to browsers, or a web page to EDSMT, for as
    # long as it likes.
    vary = {"Vary": "Accept"}
    if "text/html" in (accept or "").lower():
        page = LANDING
        for token, value in (("__VERSION__", app.version),
                             ("__SCHEMA__", SCHEMA_ID),
                             ("__DEPOSITS__", "{:,}".format(counts["deposits"])),
                             ("__SITES__", "{:,}".format(counts["sites"])),
                             ("__PRICES__", "{:,}".format(counts["prices"]))):
            page = page.replace(token, str(value))
        return HTMLResponse(page, headers=vary)
    return JSONResponse({
        "service": "EDSMT community API",
        "what": "Shared surface mining deposits for Elite Dangerous, "
                "collected by commanders running EDSMT.",
        "app": "https://radioraxxla.com/EDSMT/",
        "by": "Radio Raxxla",
        "version": app.version,
        "schema": SCHEMA_ID,
        "docs": "/docs",
        "counts": counts,
        "endpoints": {
            "health":      "GET  /v1/health",
            "commodities": "GET  /v1/commodities",
            "deposits":    "GET  /v1/deposits?commodity=&system=",
            "sites":       "GET  /v1/sites?limit=",
            "intact":      "GET  /v1/intact?min_confidence=",
            "sell":        "GET  /v1/sell?commodity=&near=&within_ly=",
            "prices":      "GET  /v1/prices?commodity=",
            "submit":      "POST /v1/deposits",
            "depletion":   "POST /v1/depletion",
            "wing":        "POST /v1/wing/{code}",
        },
        "answers": "Is this patch still worth the trip.",
        "reformation_measured": REFORMATION_MEASURED,
        "submissions": "Open. No key needed - EDSMT uploads what you map, "
                       "if you switch sharing on.",
        "verification": "Staff only. An upload cannot mark itself verified.",
    }, headers=vary)


@app.get("/v1/health")
def health():
    """Is it up, which build, and how much is in it.

    Deliberately nothing about how it is tuned or where else it gets data
    from: that is operating detail, and this answer is public.
    """
    with closing(connect()) as c:
        total = c.execute("SELECT COUNT(*) AS n FROM deposits").fetchone()["n"]
        site_count = c.execute("SELECT COUNT(*) AS n FROM sites").fetchone()["n"]
        price_count = c.execute("SELECT COUNT(*) AS n FROM prices").fetchone()["n"]
    return {"ok": True, "schema": SCHEMA_ID, "version": app.version,
            "deposits": total, "sites": site_count, "prices": price_count,
            "reformation_measured": REFORMATION_MEASURED}


@app.post("/v1/deposits")
def upload(payload: Upload, authorization: str = Header(default="")):
    if WRITE_TOKEN and authorization != f"Bearer {WRITE_TOKEN}":
        raise HTTPException(401, "bad or missing token")

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    accepted = duplicates = updated = 0
    with closing(connect()) as c:
        for d in payload.message.deposits:
            try:
                c.execute(
                    """INSERT INTO deposits
                       (system,planet,spot,type,rigs,direction,distance,lat,lon,
                        notes,uploader,software,created,fingerprint,
                        density,temperature_k,amount,planet_class,gravity,
                        atmosphere,volcanism,status,density_rank,system_address,
                        game_version)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (d.system, d.planet, d.spot, d.type, d.rigs,
                     d.direction if d.direction is not None else 0.0,
                     d.distance if d.distance is not None else 0.0,
                     d.lat, d.lon, d.notes,
                     payload.header.uploaderID, payload.header.softwareName,
                     now, fingerprint(d), d.density, d.temperature_k,
                     d.amount, d.planet_class, d.gravity, d.atmosphere,
                     d.volcanism,
                     # Uploads are always "reported". Verified is something
                     # the server grants, through /v1/verify, to somebody
                     # holding a staff token.
                     "reported",
                     # Ranked here, once, instead of on every search.
                     # 2.0 is the neutral the scorer used to substitute
                     # for a deposit nobody recorded a density for.
                     density_rank(d.density),
                     d.system_address,
                     # Which game build this was seen in. Blank from any
                     # client that does not send it, which is all of them
                     # until the next app release.
                     payload.header.gameVersion))
                accepted += 1
            except sqlite3.IntegrityError:
                duplicates += 1
                # The same deposit again is how the app says it has CHANGED:
                # its Amount goes down as it is worked, and a rig count gets
                # corrected once somebody is standing on it. A blank field
                # never overwrites a filled one - a commander who did not
                # read the Density has not said it is gone.
                changed = c.execute(
                    """UPDATE deposits SET
                         amount  = CASE WHEN COALESCE(?, '') <> '' THEN ? ELSE amount END,
                         density = CASE WHEN COALESCE(?, '') <> '' THEN ? ELSE density END,
                         density_rank = CASE WHEN COALESCE(?, '') <> '' THEN ? ELSE density_rank END,
                         rigs    = CASE WHEN ? > 0 THEN ? ELSE rigs END
                       WHERE fingerprint = ?
                         AND (COALESCE(amount, '') <> COALESCE(NULLIF(?, ''), amount, '')
                           OR COALESCE(density, '') <> COALESCE(NULLIF(?, ''), density, '')
                           OR (? > 0 AND rigs <> ?))""",
                    (d.amount, d.amount, d.density, d.density,
                     d.density, density_rank(d.density), d.rigs or 0, d.rigs,
                     fingerprint(d), d.amount, d.density, d.rigs or 0,
                     d.rigs)).rowcount
                updated += 1 if changed else 0
            # Even a duplicate is a sighting: somebody was standing there
            # today, which is exactly what makes a site worth trusting.
            touch_site(c, d.system, d.planet, d.spot, now,
                       payload.header.gameVersion)
            remember_system(c, d.system_address, d.system, d.x, d.y, d.z, now)
        c.commit()
    return {"accepted": accepted, "duplicates": duplicates, "updated": updated}


def touch_site(conn, system: str, planet: str, spot: str, now: str,
               game_version: str = "") -> None:
    """Record that a site was confirmed as still there, just now.

    Somebody standing on a patch beats every stale report about it, so a
    sighting ends whatever depletion episode was running - flag, reporters
    and all. Leaving the reporter rows behind would let a report from August
    corroborate a report from November about a patch that was confirmed full
    in between.
    """
    conn.execute(
        """INSERT INTO sites (system, planet, spot, last_seen, depleted, reports,
                              depleted_last, depleted_reporters, game_version)
           VALUES (?,?,?,?, '', 1, '', 0, ?)
           ON CONFLICT(system, planet, spot) DO UPDATE SET
               last_seen = excluded.last_seen,
               depleted  = '',
               depleted_last = '',
               depleted_reporters = 0,
               game_version = CASE WHEN excluded.game_version <> ''
                                   THEN excluded.game_version
                                   ELSE sites.game_version END,
               reports   = sites.reports + 1""",
        (system, planet, spot, now, game_version))
    conn.execute("""DELETE FROM depletion_reports
                    WHERE system = ? AND planet = ? AND spot = ?""",
                 (system, planet, spot))


@app.post("/v1/depletion")
def depletion(payload: DepletionUpload, authorization: str = Header(default="")):
    """A commander says a site is stripped. The most valuable row we take.

    Deposit POSITIONS are computable offline - the generator is a
    deterministic PRNG seeded on the body address, and somebody is
    reconstructing it for the whole galaxy. Depletion is the one value that
    lives on Frontier's servers and can only be observed, one commander at a
    time, by driving there. It is also the only thing anybody has an
    incentive to share, because reporting a patch you emptied costs you
    nothing: it is already gone.

    So this endpoint does not set a flag. It records WHO said it and WHEN,
    keyed on the commander so the same person cannot corroborate themselves,
    and the site carries the count from then on. Two independent reports is
    a different claim from one, and the ranking is allowed to know that.
    """
    if WRITE_TOKEN and authorization != f"Bearer {WRITE_TOKEN}":
        raise HTTPException(401, "bad or missing token")
    m = payload.message
    who = (payload.header.uploaderID or "").strip()
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    with closing(connect()) as c:
        if m.worked_out:
            c.execute(
                """INSERT INTO depletion_reports
                     (system, planet, spot, uploader, reported, game_version)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(system, planet, spot, uploader) DO UPDATE SET
                       reported = excluded.reported,
                       game_version = CASE WHEN excluded.game_version <> ''
                                           THEN excluded.game_version
                                           ELSE depletion_reports.game_version END""",
                (m.system, m.planet, m.spot, who, now, payload.header.gameVersion))
            reporters, first = c.execute(
                """SELECT COUNT(*), MIN(reported) FROM depletion_reports
                   WHERE system = ? AND planet = ? AND spot = ?""",
                (m.system, m.planet, m.spot)).fetchone()
            # A depletion report is NOT a sighting of deposits, so it must
            # never move last_seen. Conflating the two is what made a site
            # look freshly confirmed at the moment somebody said it was
            # empty. last_seen is set on INSERT only, because hearing about
            # a site for the first time is genuinely all we know about it.
            c.execute(
                """INSERT INTO sites (system, planet, spot, last_seen, depleted,
                                      reports, depleted_last, depleted_reporters,
                                      game_version)
                   VALUES (?,?,?,?,?,0,?,?,?)
                   ON CONFLICT(system, planet, spot) DO UPDATE SET
                       depleted  = excluded.depleted,
                       depleted_last = excluded.depleted_last,
                       depleted_reporters = excluded.depleted_reporters,
                       game_version = CASE WHEN excluded.game_version <> ''
                                           THEN excluded.game_version
                                           ELSE sites.game_version END""",
                (m.system, m.planet, m.spot, now, first or now, now,
                 reporters, payload.header.gameVersion))
        else:
            # Taking it back. The whole episode goes, not just this
            # commander's line in it - somebody is standing there saying the
            # patch is not empty, and that outranks every stale report.
            c.execute("""DELETE FROM depletion_reports
                         WHERE system = ? AND planet = ? AND spot = ?""",
                      (m.system, m.planet, m.spot))
            c.execute(
                """INSERT INTO sites (system, planet, spot, last_seen, depleted,
                                      reports, depleted_last, depleted_reporters)
                   VALUES (?,?,?,?,'',0,'',0)
                   ON CONFLICT(system, planet, spot) DO UPDATE SET
                       depleted  = '',
                       depleted_last = '',
                       depleted_reporters = 0""",
                (m.system, m.planet, m.spot, now))
            reporters, first = 0, ""
        c.commit()
    return {"ok": True, "worked_out": m.worked_out,
            # What the database now believes, so the app can say "you are the
            # second commander to report this" rather than "sent".
            "reporters": reporters,
            "worked_out_first": first or "",
            "confidence": round(stripped_belief(reporters), 4),
            # Never a countdown. Nobody has measured one.
            "reformation_measured": REFORMATION_MEASURED}


@app.post("/v1/market")
def market(payload: MarketUpload, authorization: str = Header(default="")):
    """Commodity prices, collected from the people running the app.

    The 4.4.1.0 commodities are missing from the community commodity-ID
    list, and the public galaxy-data APIs offer only per-system lookups, no
    commodity search. So nothing out there can answer "where does Magnesite
    sell". This can, because every user's own journal already knows.
    """
    if WRITE_TOKEN and authorization != f"Bearer {WRITE_TOKEN}":
        raise HTTPException(401, "bad or missing token")
    m = payload.message
    if not m.market_id:
        raise HTTPException(422, "market_id is required")
    seen = m.when or dt.datetime.now(dt.timezone.utc).isoformat()
    accepted = 0
    with closing(connect()) as c:
        for item in m.items:
            # Newest reading for a station wins; an older one is ignored
            # rather than overwriting what somebody saw more recently.
            c.execute(
                """INSERT INTO prices
                     (market_id, commodity, station, system, sell, buy, demand,
                      seen, uploader, game_version)
                   VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(market_id, commodity) DO UPDATE SET
                       sell = excluded.sell, buy = excluded.buy,
                       demand = excluded.demand, seen = excluded.seen,
                       station = excluded.station, system = excluded.system,
                       uploader = excluded.uploader,
                       game_version = excluded.game_version
                   WHERE excluded.seen > prices.seen""",
                (m.market_id, item.commodity, m.station, m.system,
                 item.sell, item.buy, item.demand, seen,
                 payload.header.uploaderID, payload.header.gameVersion))
            accepted += 1
        c.commit()
    return {"accepted": accepted}


@app.get("/v1/prices")
def prices(commodity: str = "", near: str = "",
           near_x: float | None = None, near_y: float | None = None,
           near_z: float | None = None,
           within_ly: float = Query(default=0, ge=0, le=20000),
           limit: int = Query(default=20, ge=1, le=200)):
    """Best sell prices seen for a commodity, optionally near a position.

    This used to take `near` and nothing else, and match it with
    `system = ?`. You ask it from a planet surface in the middle of
    nowhere, where by definition nobody has ever sold anything, so it
    returned nothing every single time - which reads as a broken feature
    rather than as an empty system. Position and a radius are what the
    question actually was: not "what sells HERE" but "what sells NEAR here".

    `near` still works, still as an exact system name, for anything already
    calling it that way. It is just no longer the only way to ask.
    """
    sql = "SELECT commodity, station, system, sell, demand, seen FROM prices WHERE sell > 0"
    args: list = []
    if commodity:
        known = COMMODITIES.get(fold(commodity))
        sql += " AND commodity = ?"
        args.append(known or commodity)
    if near:
        sql += " AND system = ?"
        args.append(near)

    # A price row carries the system name and no address, so the cube is
    # keyed on the name. See near_clause.
    cube, cube_args = near_clause(near_x, near_y, near_z, within_ly,
                                  column="system", key="name")
    sql += cube
    args += cube_args

    here = None if None in (near_x, near_y, near_z) else (near_x, near_y, near_z)
    sql += " ORDER BY sell DESC, seen DESC LIMIT ?"
    # Take a pool when the corners still have to come off, so that trimming
    # them cannot hand back half a page. The cube is 1.9x the sphere, and
    # the pool is twenty times the page, so it cannot run short.
    args.append(max(POOL_FLOOR, limit * POOL_MULTIPLIER) if here else limit)
    with closing(connect()) as c:
        rows = [dict(r) for r in c.execute(sql, args).fetchall()]
        rows = price_distances(c, rows, here, within_ly)[:limit]
    return {"count": len(rows), "prices": rows}


# ------------------------------------------------- best sell prices
#
# /v1/sell can add a public market index on top of what our own users read
# out of their own Market.json. Which index is configuration, not code:
# RR_SELL_API is its base URL and RR_SELL_API_NAME is what the answer calls
# it. The index has to answer
#
#   GET {RR_SELL_API}/v2/commodity/name/{slug}/imports
#       ?systemName=&maxDistance=&minVolume=&maxDaysAgo=
#
# with a JSON list of stations buying the commodity, each carrying
# sellPrice, demand, stationName, stationType, maxLandingPadSize,
# distanceToArrival, systemName, updatedAt and `distance` in light years
# from systemName. The slug is lowercase alphanumeric with accents stripped,
# which is what fold() produces. It is not sorted by price; that happens here.
#
# Unset, /v1/sell answers from our own users' reads alone and says so in
# upstream_status, rather than failing.

SELL_UPSTREAM_BASE = os.environ.get("RR_SELL_API", "").strip().rstrip("/")
SELL_UPSTREAM_NAME = (os.environ.get("RR_SELL_API_NAME", "").strip()
                      or ("market index" if SELL_UPSTREAM_BASE else ""))
# Prices move slowly and nobody is arbitraging to the credit here. Fifteen
# minutes of cache turns a room full of commanders into one request.
SELL_CACHE_SECONDS = float(os.environ.get("RR_SELL_CACHE", "900"))
# Be a good neighbour to whoever runs the index. One call a second is the
# floor, and the cache above is what actually keeps the traffic down.
SELL_MIN_INTERVAL = float(os.environ.get("RR_SELL_MIN_INTERVAL", "1.0"))
SELL_TIMEOUT = float(os.environ.get("RR_SELL_TIMEOUT", "8"))

# Where our spelling and the upstream's slug genuinely differ. Only entries
# that have been checked against the live service go in here.
SELL_SLUGS = {"lowtemperaturediamonds": "lowtemperaturediamond"}

_sell_cache: dict = {}
_sell_last_call = [0.0]

# A market reading demand 999,999 is not a market: it is the placeholder a
# Community Goal station carries. The Ega CG's 1,038,104 Cr stood as "the
# best price" for three surface commodities under exactly that number, and
# nobody could sell a hold there once it closed. Such rows are left out.
PLACEHOLDER_DEMAND = 999999


def sell_slug(commodity: str) -> str:
    """Our commodity name as the upstream spells it."""
    folded = fold(commodity)
    return SELL_SLUGS.get(folded, folded)


def fetch_upstream_sell(commodity: str, near_system: str = "",
                        within_ly: float = 0, limit: int = 20) -> list:
    """One upstream call. Separated out so it can be replaced or stubbed.

    Raises on anything at all - the caller degrades to our own data rather
    than failing the request, because a community map that goes down when
    somebody else's API does is worse than one that answers with less.
    """
    import json as _json
    import urllib.parse as _parse
    import urllib.request as _request

    params = {"minVolume": 1, "maxDaysAgo": 30}
    if near_system:
        params["systemName"] = near_system
        if within_ly:
            params["maxDistance"] = int(within_ly)
    url = "%s/v2/commodity/name/%s/imports?%s" % (
        SELL_UPSTREAM_BASE, _parse.quote(sell_slug(commodity)),
        _parse.urlencode(params))
    req = _request.Request(url, headers={
        "User-Agent": "EDSMT-community-api/%s (+https://radioraxxla.com/EDSMT/)"
                      % APP_VERSION,
        "Accept": "application/json"})
    with _request.urlopen(req, timeout=SELL_TIMEOUT) as reply:
        raw = _json.loads(reply.read().decode("utf-8", "replace"))
    if not isinstance(raw, list):
        return []

    rows = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        sell = int(item.get("sellPrice") or 0)
        if sell <= 0:
            continue
        if int(item.get("demand") or 0) == PLACEHOLDER_DEMAND:
            continue
        rows.append({
            "commodity": COMMODITIES.get(fold(item.get("commodityName")))
                         or str(item.get("commodityName") or commodity),
            "station": item.get("stationName") or "",
            "station_type": item.get("stationType") or "",
            "system": item.get("systemName") or "",
            "sell": sell,
            "demand": int(item.get("demand") or 0),
            "pad": item.get("maxLandingPadSize"),
            "distance_to_arrival": item.get("distanceToArrival"),
            "distance_ly": item.get("distance"),
            "seen": item.get("updatedAt") or "",
            "source": SELL_UPSTREAM_NAME,
        })
    # The upstream does not sort by price, so we do.
    rows.sort(key=lambda r: (-r["sell"], -(r["demand"] or 0)))
    top = rows[:limit]
    # The best price in the system asked from goes in whatever it is. Cut at
    # `limit` by price, the station next door fell off the end whenever
    # twenty better ones were in range - and "is the drive worth it" is a
    # question about the price here as much as the price there.
    if near_system:
        here = fold(near_system)
        if not any(fold(r["system"]) == here for r in top):
            top += [r for r in rows[limit:] if fold(r["system"]) == here][:1]
    return top


def upstream_sell(commodity: str, near_system: str, within_ly: float,
                  limit: int) -> tuple:
    """Cached, rate-limited wrapper. Returns (rows, status)."""
    import time as _time

    if not SELL_UPSTREAM_BASE:
        return [], "not configured"

    key = (fold(commodity), (near_system or "").strip().lower(),
           float(within_ly or 0), int(limit))
    hit = _sell_cache.get(key)
    nowish = _time.time()
    if hit and nowish - hit[0] < SELL_CACHE_SECONDS:
        return hit[1], "cached"
    if nowish - _sell_last_call[0] < SELL_MIN_INTERVAL:
        # Somebody else is mid-call. Serve a stale cache if there is one and
        # our own data if there is not, rather than queueing up on them.
        return (hit[1] if hit else []), "rate-limited"
    _sell_last_call[0] = nowish
    try:
        rows = fetch_upstream_sell(commodity, near_system, within_ly, limit)
    except Exception:
        # Upstream down, slow, or renamed something. Not our outage.
        return (hit[1] if hit else []), "unavailable"
    _sell_cache[key] = (nowish, rows)
    return rows, "live"


@app.get("/v1/sell")
def sell(commodity: str = "", near: str = "",
         near_x: float | None = None, near_y: float | None = None,
         near_z: float | None = None,
         within_ly: float = Query(default=0, ge=0, le=20000),
         limit: int = Query(default=20, ge=1, le=200),
         upstream: bool = True):
    """Where a surface-mined commodity sells highest, optionally near a system.

    The app asks us rather than the upstream directly, so that one cache and
    one rate limiter cover every commander running EDSMT instead of each of
    them hammering somebody else's service on their own.

    Two sources, kept apart in the answer rather than blended. `community`
    is what our own users read out of their own Market.json, which is the
    only source that is definitely current for a commodity nobody else has
    got round to indexing. `market` is the upstream. Each row says which it
    came from, because they are not equally fresh and pretending otherwise
    would be the sort of thing this API is trying not to do.

    The community half can be asked by position as well as by name, for the
    same reason /v1/prices can: standing on a body in the middle of nowhere,
    a name match is a question with no answer. `near` is unchanged - still a
    prefix on the system name, and still what gets handed to the upstream,
    which takes a name and not coordinates.
    """
    if not commodity:
        raise HTTPException(422, "commodity is required")
    known = COMMODITIES.get(fold(commodity)) or commodity

    sql = ("SELECT commodity, station, system, sell, demand, seen "
           "FROM prices WHERE sell > 0 AND commodity = ? "
           "AND (demand IS NULL OR demand != %d)" % PLACEHOLDER_DEMAND)
    args: list = [known]
    here = None if None in (near_x, near_y, near_z) else (near_x, near_y, near_z)
    # With a position, `near` is only the centre the upstream measures from.
    # Used as a name filter as well, asking from HR 7280 with a position
    # threw away every price our own users had read anywhere but HR 7280 -
    # the one answer the question was not about.
    if near and here is None:
        sql += " AND system LIKE ?"
        args.append(prefix_pattern(near))

    cube, cube_args = near_clause(near_x, near_y, near_z, within_ly,
                                  column="system", key="name")
    sql += cube
    args += cube_args

    sql += " ORDER BY sell DESC, seen DESC LIMIT ?"
    args.append(max(POOL_FLOOR, limit * POOL_MULTIPLIER) if here else limit)
    with closing(connect()) as c:
        mine = [dict(r) for r in c.execute(sql, args).fetchall()]
        mine = price_distances(c, mine, here, within_ly)[:limit]
    for row in mine:
        row["source"] = "community"

    rows, status = ([], "off")
    if upstream:
        rows, status = upstream_sell(known, near, within_ly, limit)

    best = max([r["sell"] for r in rows + mine] or [0])
    return {"commodity": known, "upstream": SELL_UPSTREAM_NAME or "",
            "upstream_status": status, "best_sell": best,
            "count": len(rows) + len(mine),
            "market": rows, "community": mine}


@app.get("/v1/deposits")
def search(commodity: str = "", system: str = "", planet: str = "",
           body: str = "", name: str = "",
           min_rigs: int = Query(default=0, ge=0, le=6),
           near_x: float | None = None, near_y: float | None = None,
           near_z: float | None = None,
           within_ly: float = Query(default=0, ge=0, le=20000),
           limit: int = Query(default=50, ge=1, le=500)):
    # The site's depletion state, carried on every deposit row. Depletion is
    # tracked per site - one patch, one state - so without this join a
    # deposit row physically cannot say whether it is still there, and the
    # app's "hide worked out" filter reads a field that is never present and
    # silently keeps everything.
    sql = """SELECT d.*, COALESCE(s.depleted, '') AS depleted,
                    COALESCE(s.depleted_reporters, 0) AS depleted_reporters,
                    COALESCE(s.depleted_last, '') AS depleted_last,
                    COALESCE(s.last_seen, '') AS site_last_seen
             FROM deposits d
             LEFT JOIN sites s
               ON s.system = d.system AND s.planet = d.planet AND s.spot = d.spot
             WHERE 1=1"""
    args: list = []
    if commodity:
        sql += " AND d.type = ?"
        args.append(COMMODITIES.get(fold(commodity)) or commodity)
    if system:
        # Prefix, not equality. Somebody typing "Col 285" is looking for
        # "Col 285 Sector ZL-K b22-2", and an exact match answered that with
        # nothing at all - which reads as "no data here" rather than "not
        # what you typed". Still index-served; see prefix_pattern.
        sql += " AND d.system LIKE ?"
        args.append(prefix_pattern(system))
    if body:
        sql += " AND d.planet LIKE ?"
        args.append(prefix_pattern(body))
    if name:
        # One box, either answer. SQLite only takes an OR apart into two
        # index searches when BOTH sides have an index of their own, which
        # is what ix_dep_planet is for - without it this reads every deposit
        # in the database and the whole point of the other filters is lost.
        sql += " AND (d.system LIKE ? OR d.planet LIKE ?)"
        args.extend([prefix_pattern(name), prefix_pattern(name)])
    if planet:
        sql += " AND d.planet = ?"
        args.append(planet)
    if min_rigs:
        sql += " AND d.rigs >= ?"
        args.append(min_rigs)

    cube, cube_args = near_clause(near_x, near_y, near_z, within_ly,
                                  column="d.system_address")
    sql += cube
    args += cube_args

    sql += " ORDER BY d.rigs DESC, d.created DESC LIMIT ?"
    args.append(limit)

    here = None if None in (near_x, near_y, near_z) else (near_x, near_y, near_z)
    with closing(connect()) as c:
        rows = [dict(r) for r in c.execute(sql, args).fetchall()]
        if here:
            wanted = sorted({r["system_address"] for r in rows
                             if r.get("system_address") is not None})
            where = {}
            for chunk in (wanted[i:i + 400] for i in range(0, len(wanted), 400)):
                marks = ",".join("?" * len(chunk))
                for r in c.execute("SELECT address, x, y, z FROM systems "
                                   "WHERE address IN (%s)" % marks, chunk):
                    where[r["address"]] = (r["x"], r["y"], r["z"])
            kept = []
            for r in rows:
                distance = light_years(here, where.get(r.get("system_address")))
                if distance is None or distance > within_ly:
                    continue
                r["distance_ly"] = round(distance, 2)
                kept.append(r)
            rows = kept

    now = dt.datetime.now(dt.timezone.utc).timestamp()
    for r in rows:
        emptied = r.pop("depleted", "") or ""
        reporters = r.pop("depleted_reporters", 0) or 0
        r.pop("depleted_last", None)
        # When anyone last reported this patch - the find itself, or any
        # later sighting of its site. The Find window's Last seen column.
        site_seen = r.pop("site_last_seen", "") or ""
        r["last_seen"] = max((stamp for stamp in (r.get("created"), site_seen)
                              if stamp), key=to_epoch, default="")
        r["worked_out"] = bool(emptied)
        r["worked_out_reports"] = reporters
        # The honest figure, and only the honest figure: how long it has
        # been since somebody said this was stripped. Not how long until it
        # comes back - nobody knows that.
        r["days_since_worked_out"] = (
            round(max(0.0, (now - to_epoch(emptied)) / 86400.0), 2)
            if emptied else None)
        r["reformation_measured"] = REFORMATION_MEASURED
    return {"count": len(rows), "deposits": rows,
            "reformation_measured": REFORMATION_MEASURED}


@app.get("/v1/sites")
def sites(commodity: str = "", system: str = "", body: str = "",
          name: str = "",
          min_rigs: int = Query(default=0, ge=0, le=200),
          min_types: int = Query(default=0, ge=0, le=13),
          max_age_days: int = Query(default=0, ge=0, le=3650),
          include_depleted: bool = False, verified_only: bool = False,
          near_x: float | None = None, near_y: float | None = None,
          near_z: float | None = None,
          within_ly: float = Query(default=0, ge=0, le=20000),
          limit: int = Query(default=50, ge=1, le=500)):
    """Sites ranked by whether the patch is still worth the trip.

    Rigs first - six down is the point of the Rhino. Then overlap: several
    commodities inside one patch is the surface equivalent of a triple
    hotspot, and it beats a richer single-commodity site. Then density.

    That raw figure is then multiplied by intact_confidence, which is the
    question this database exists to answer. Deposit positions are
    computable offline from the body address; whether a patch has been
    stripped is not, and never will be. So the ranking is not "biggest
    site", it is "biggest site that is probably still there".

    `system`, `verified_only` and `include_depleted` are the Find window's
    three filters. They are answered HERE, against the database, because the
    app used to apply them to whatever page it had already been handed - so
    "verified only" sifted 500 rows that were chosen without reference to
    it, and the boxes read as broken on a galaxy this size.

    `system` and `body` are separate prefix filters, and `name` is either.
    The app's box is labelled "System / body" and a commander types whichever
    one they have - "Ega" or "Ega 1" - with no way for the app to tell which
    it got. Splitting that into two parameters and asking the app to guess
    would just move the guess; `name` answers the question actually being
    asked, which is "sites whose system OR body starts with this".
    """
    sql = """SELECT d.system, d.planet, d.spot, d.system_address,
                    COUNT(*)                      AS deposits,
                    SUM(d.rigs)                   AS rigs,
                    COUNT(DISTINCT d.type)        AS distinct_types,
                    GROUP_CONCAT(DISTINCT d.type) AS types,
                    AVG(d.density_rank)           AS density,
                    AVG(d.temperature_k)          AS temperature_k,
                    MAX(d.created)                AS created,
                    COALESCE(s.last_seen, MAX(d.created)) AS updated,
                    COALESCE(s.depleted, '')      AS depleted,
                    COALESCE(s.depleted_last, '') AS depleted_last,
                    COALESCE(s.depleted_reporters, 0) AS depleted_reporters,
                    -- Whether somebody from Radio Raxxla has stood on it.
                    -- The app ships a "verified only" filter; without this
                    -- column it matched nothing, because a GROUP BY that
                    -- selects neither status nor uploader cannot return
                    -- either of them.
                    COALESCE(s.status, 'reported') AS status,
                    COALESCE(s.verified_by, '')   AS verified_by,
                    COALESCE(s.game_version, '')  AS game_version,
                    -- Who found it. A site has no single uploader, so this
                    -- picks one and says which: the commander whose upload
                    -- created the earliest deposit here. First reporter is
                    -- the only honest answer - everybody after them
                    -- confirmed a site that already existed.
                    (SELECT f.uploader FROM deposits f
                      WHERE f.system = d.system AND f.planet = d.planet
                        AND f.spot = d.spot
                      ORDER BY f.created ASC, f.id ASC LIMIT 1) AS uploader,
                    -- How many different commanders have logged deposits
                    -- here. Anonymous uploads carry no name and so cannot
                    -- corroborate; that is the cost of staying anonymous,
                    -- not a fault in the data.
                    COUNT(DISTINCT CASE WHEN TRIM(d.uploader) <> ''
                                        THEN LOWER(TRIM(d.uploader)) END)
                                                  AS confirmed_by,
                    SUM(d.rigs)
                      + COUNT(DISTINCT d.type) * 2.5
                      -- Density is NOT weighted. The community field
                      -- guide is explicit that its effect on yield is
                      -- unproven and the observed trend runs INVERSE
                      -- (high density, smaller footprint). It is still
                      -- averaged and returned, because a commander
                      -- wants to see it - it just does not move the
                      -- ranking on evidence nobody has.
                      + 0.0 AS raw
             FROM deposits d
             LEFT JOIN sites s
               ON s.system = d.system AND s.planet = d.planet AND s.spot = d.spot
             WHERE 1=1"""
    args: list = []
    if commodity:
        known = COMMODITIES.get(fold(commodity)) or commodity
        # EXISTS on the indexed columns. This used to concatenate the three
        # key columns into a string and compare that, which no index can
        # serve, so a commodity filter read every row in the table.
        sql += (" AND EXISTS (SELECT 1 FROM deposits t"
                "  WHERE t.system = d.system AND t.planet = d.planet"
                "    AND t.spot = d.spot AND t.type = ?)")
        args.append(known)
    if system:
        # Prefix, not equality, exactly as /v1/deposits does it. Somebody
        # typing "Col 285" wants "Col 285 Sector ZL-K b22-2", and an exact
        # match answers that with nothing at all - which reads as "no data
        # here" rather than "not what you typed". Index-served; see
        # prefix_pattern for the three things that keep it that way.
        sql += " AND d.system LIKE ?"
        args.append(prefix_pattern(system))
    if body:
        sql += " AND d.planet LIKE ?"
        args.append(prefix_pattern(body))
    if name:
        # One box, either answer. SQLite only takes an OR apart into two
        # index searches when BOTH sides have an index of their own, which
        # is what ix_dep_planet is for - without it this reads every deposit
        # in the database and the whole point of the other filters is lost.
        sql += " AND (d.system LIKE ? OR d.planet LIKE ?)"
        args.extend([prefix_pattern(name), prefix_pattern(name)])
    if verified_only:
        # Driven off the verified rows rather than filtered onto them. An
        # EXISTS here reads every deposit in the table and asks each one
        # whether it qualifies; this hands the planner the small set first,
        # so ix_dep_status picks out the verified site keys and the roll-up
        # only ever touches those sites. EXPLAIN QUERY PLAN is the
        # difference between SCAN deposits and SEARCH deposits.
        sql += (" AND (d.system, d.planet, d.spot) IN"
                "  (SELECT v.system, v.planet, v.spot FROM deposits v"
                "    WHERE v.status = 'verified')")

    cube, cube_args = near_clause(near_x, near_y, near_z, within_ly)
    sql += cube
    args += cube_args

    sql += " GROUP BY d.system, d.planet, d.spot"
    having = []
    if min_rigs:
        having.append("SUM(d.rigs) >= ?")
        args.append(min_rigs)
    if min_types:
        having.append("COUNT(DISTINCT d.type) >= ?")
        args.append(min_types)
    if having:
        sql += " HAVING " + " AND ".join(having)

    # The whole point. This used to group the entire galaxy, hand every
    # site to Python and only then apply the limit, which is a full table
    # scan on every search. Ordering and bounding in SQL is safe because
    # the Python decay can only ever lower a score.
    sql += " ORDER BY raw DESC LIMIT ?"
    args.append(max(POOL_FLOOR, limit * POOL_MULTIPLIER))

    here = None if None in (near_x, near_y, near_z) else (near_x, near_y, near_z)
    with closing(connect()) as c:
        rows = [dict(r) for r in c.execute(sql, args).fetchall()]
        # Exact distance for the rows that survived the cube. Only these,
        # and only when somebody asked where they were.
        where = {}
        if here:
            wanted = sorted({r["system_address"] for r in rows
                             if r["system_address"] is not None})
            for chunk in (wanted[i:i + 400] for i in range(0, len(wanted), 400)):
                marks = ",".join("?" * len(chunk))
                for r in c.execute("SELECT address, x, y, z FROM systems "
                                   "WHERE address IN (%s)" % marks, chunk):
                    where[r["address"]] = (r["x"], r["y"], r["z"])

    now = dt.datetime.now(dt.timezone.utc).timestamp()
    out = []
    for r in rows:
        r["types"] = sorted(set((r.pop("types") or "").split(","))) if r.get("types") else []
        # Averaged in SQL now, from the rank stored at upload time.
        r["density"] = round(r["density"], 2) if r.get("density") is not None else None

        r["raw"] = round(r.get("raw") or 0.0, 3)
        if here:
            # The cube is a box; this is the sphere inside it. A corner of
            # the box is 1.7x the radius away, so without this a "within
            # 50 Ly" search quietly answers with things 86 Ly out.
            distance = light_years(here, where.get(r["system_address"]))
            if distance is None or distance > within_ly:
                continue
            r["distance_ly"] = round(distance, 2)

        age_days = max(0.0, (now - to_epoch(r["updated"])) / 86400.0) if r["updated"] else 0.0
        # age_days is kept under its old name because the app renders it, but
        # it is days since anybody CONFIRMED the site, not the deposit's age.
        r["age_days"] = round(age_days, 2)
        r["days_since_confirmed"] = r["age_days"]
        r["last_confirmed_present"] = r["updated"]
        emptied_at = r.pop("depleted", "") or ""
        r["worked_out"] = bool(emptied_at)
        r["worked_out_first"] = emptied_at
        r["worked_out_last"] = r.pop("depleted_last", "") or emptied_at
        reporters = r.pop("depleted_reporters", 0) or 0
        r["worked_out_reports"] = reporters
        r["uploader"] = (r.get("uploader") or "").strip()
        # Sharing a CMDR name is a switch in the app, so blank is normal and
        # has to read as an answer rather than as a column that failed to
        # load. The flag is what lets a UI print "anonymous" with confidence.
        r["uploader_known"] = bool(r["uploader"])
        confirmed_by = int(r.get("confirmed_by") or 0)

        if max_age_days and age_days > max_age_days:
            continue
        if r["worked_out"] and not include_depleted:
            continue

        raw = r["raw"]

        # How long since somebody said it was stripped. A fact, and the only
        # one available: the field guide is explicit that the reformation
        # timer is Not established - a site has been under timed watch since
        # 6 September and nothing has been measured. So no countdown, no
        # "back in N days", just elapsed time and a flag saying nobody knows.
        r["days_since_worked_out"] = (
            round(max(0.0, (now - to_epoch(emptied_at)) / 86400.0), 2)
            if emptied_at else None)
        r["reformation_measured"] = REFORMATION_MEASURED
        r["reformation_estimate_days"] = REFORMATION_ESTIMATE_DAYS

        # Confidence in the REPORT, decayed by its age and raised by how
        # many different commanders have stood there. It is not a claim
        # about the deposit: sites have been watched persisting unchanged
        # across a hotfix, so age is our uncertainty, not their decay.
        r["confidence"] = round(
            report_confidence(r["updated"], now, max(1, confirmed_by)), 3)
        r["depletion_confidence"] = round(stripped_belief(reporters), 4)
        r["recovery_assumed"] = (round(assumed_recovery(emptied_at, now), 3)
                                 if emptied_at else None)

        factor = intact_confidence(r["updated"], emptied_at, reporters,
                                   max(1, confirmed_by), now)
        r["intact_confidence"] = round(factor, 4)
        # freshness kept as the old spelling of confidence, so nothing that
        # already reads it breaks on the rename.
        r["freshness"] = r["confidence"]
        r["score"] = round(raw * factor, 3)
        out.append(r)

    out.sort(key=lambda x: -x["score"])
    return {"count": len(out[:limit]), "sites": out[:limit],
            # Said once per response as well as per row, so a client that
            # renders a summary line cannot present the estimate as a fact.
            "reformation_measured": REFORMATION_MEASURED,
            "reformation_estimate_days": REFORMATION_ESTIMATE_DAYS,
            "confidence_half_life_days": HALF_LIFE_DAYS}


@app.get("/v1/intact")
def intact(commodity: str = "", system: str = "", body: str = "",
           name: str = "", verified_only: bool = False,
           min_rigs: int = Query(default=0, ge=0, le=200),
           min_types: int = Query(default=0, ge=0, le=13),
           min_confidence: float = Query(default=0.5, ge=0.0, le=1.0),
           near_x: float | None = None, near_y: float | None = None,
           near_z: float | None = None,
           within_ly: float = Query(default=0, ge=0, le=20000),
           limit: int = Query(default=50, ge=1, le=500)):
    """Of these sites, which are most likely STILL THERE right now.

    The one question a generated position database can never answer. Deposit
    positions come out of a deterministic PRNG seeded on the body address -
    anybody with the algorithm has every site in the galaxy without ever
    leaving the dock. What none of them has is whether the last commander
    through took the lot, because that value lives on Frontier's servers.

    So this is /v1/sites turned the other way up. /v1/sites ranks by size,
    discounted by confidence. This ranks by confidence, and size is the
    tie-break. Worked-out sites are not hidden - they are ranked on the same
    scale as everything else and fall below min_confidence on their own
    evidence, which is the honest way to drop them.
    """
    # Every filter /v1/sites takes is forwarded. The "Still there" table in
    # the app carries the same boxes as the sites table, and a filter that
    # is accepted by one and dropped by the other is a filter the commander
    # watches stop working when they change tab.
    found = sites(commodity=commodity, system=system, body=body, name=name,
                  verified_only=verified_only,
                  min_rigs=min_rigs, min_types=min_types,
                  max_age_days=0, include_depleted=True,
                  near_x=near_x, near_y=near_y, near_z=near_z,
                  within_ly=within_ly,
                  # A wider net than the caller asked for, because the order
                  # here is not the order sites() bounded by.
                  limit=min(500, max(limit * 4, 100)))
    rows = [r for r in found["sites"]
            if r.get("intact_confidence", 0.0) >= min_confidence]
    rows.sort(key=lambda r: (-r.get("intact_confidence", 0.0), -(r.get("raw") or 0.0)))
    rows = rows[:limit]
    return {"count": len(rows), "sites": rows,
            "min_confidence": min_confidence,
            "ranked_by": "intact_confidence",
            "reformation_measured": REFORMATION_MEASURED,
            "reformation_estimate_days": REFORMATION_ESTIMATE_DAYS,
            "confidence_half_life_days": HALF_LIFE_DAYS,
            "note": "intact_confidence mixes how old the last confirmation is "
                    "with how many independent commanders have reported the "
                    "site stripped. The reformation timer is unmeasured - "
                    "days_since_worked_out is the fact, and "
                    "reformation_estimate_days is a dial, not a countdown."}


class VerifyMessage(BaseModel):
    system: str = Field(min_length=1, max_length=120)
    planet: str = Field(min_length=1, max_length=120)
    spot: str = Field(default="1", max_length=40)
    verified: bool = True


class VerifyUpload(BaseModel):
    schema_: str = Field(alias="$schema", default=VERIFY_SCHEMA)
    header: Header_ = Header_()
    message: VerifyMessage


@app.post("/v1/verify")
def verify(payload: VerifyUpload, authorization: str = Header(default="")):
    """Mark a site as confirmed by somebody from Radio Raxxla.

    Verification is a multiplier on trust, never an exemption from age. A
    site verified in March is still an empty crater in September, so the
    freshness decay applies to verified rows exactly as it does to any
    other. Anything else would make the most trusted rows the most
    misleading ones.
    """
    secret = authorization.replace("Bearer ", "").strip()
    who = STAFF.get(secret)
    if not who:
        raise HTTPException(403, "that token is not on the staff list")

    m = payload.message
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    status = "verified" if m.verified else "reported"
    with closing(connect()) as c:
        cur = c.execute(
            """UPDATE sites SET status = ?, verified_by = ?, verified_at = ?
               WHERE system = ? AND planet = ? AND spot = ?""",
            (status, who if m.verified else "", now if m.verified else "",
             m.system, m.planet, m.spot))
        if not cur.rowcount:
            raise HTTPException(404, "no such site")
        c.execute(
            """UPDATE deposits SET status = ?, verified_by = ?, verified_at = ?
               WHERE system = ? AND planet = ? AND spot = ?""",
            (status, who if m.verified else "", now if m.verified else "",
             m.system, m.planet, m.spot))
        c.commit()
    return {"ok": True, "status": status, "by": who if m.verified else ""}


def ground_of(planet_class: str, volcanism: str) -> str:
    """One name for a kind of ground: the body class, plus its volcanism
    when it has any. "Rocky body" and "Rocky body, major silicate vapour
    geysers" carry different things, so they are counted apart."""
    kind = " ".join(str(planet_class or "").split())
    volc = " ".join(str(volcanism or "").lower().replace("volcanism", "").split())
    if volc in ("", "none", "no"):
        return kind
    return "%s, %s" % (kind, volc) if kind else volc


_grounds_cache: dict = {}


@app.get("/v1/grounds")
def grounds():
    """What each kind of ground has carried, from every site anybody shared.

    For each ground: how many mining sites have been logged on it, and for
    each commodity, on how many of those sites it turned up and how many
    rigs it came to. Built from commanders' own finds, so it says where to
    PROSPECT, not what any one site will hold. Worked out at most once every
    ten minutes - it reads every deposit.
    """
    now = dt.datetime.now(dt.timezone.utc).timestamp()
    hit = _grounds_cache.get("all")
    if hit and now - hit[0] < 600:
        return hit[1]
    # Counted in SQL, not by pulling every deposit into Python: the table
    # is the one that grows with the galaxy. Grouped by the raw class and
    # volcanism strings, then folded into grounds here - a few hundred rows,
    # whatever the size of the database.
    site_key = "lower(system) || '|' || lower(planet) || '|' || lower(spot)"
    # The same normalising ground_of does, in SQL, so that "", "None" and
    # "No volcanism" are grouped together BEFORE sites are counted - summing
    # counts made per spelling afterwards would count one site twice.
    volc = ("trim(replace(lower(COALESCE(volcanism, '')), 'volcanism', ''))")
    norm = ("trim(COALESCE(planet_class, '')) AS pc, "
            "CASE WHEN %s IN ('', 'none', 'no') THEN '' ELSE %s END AS volc"
            % (volc, volc))
    sites_on: dict = {}
    found: dict = {}
    with closing(connect()) as c:
        for r in c.execute(
                """SELECT %s, COUNT(DISTINCT %s) AS sites
                   FROM deposits WHERE trim(COALESCE(planet_class, '')) <> ''
                   GROUP BY pc, volc""" % (norm, site_key)):
            ground = ground_of(r["pc"], r["volc"])
            sites_on[ground] = sites_on.get(ground, 0) + int(r["sites"] or 0)
        for r in c.execute(
                """SELECT %s, type, COUNT(DISTINCT %s) AS sites,
                          COALESCE(SUM(rigs), 0) AS rigs
                   FROM deposits WHERE trim(COALESCE(planet_class, '')) <> ''
                   GROUP BY pc, volc, type""" % (norm, site_key)):
            ground = ground_of(r["pc"], r["volc"])
            entry = found.setdefault(ground, {}).setdefault(
                r["type"], {"sites": 0, "rigs": 0})
            entry["sites"] += int(r["sites"] or 0)
            entry["rigs"] += int(r["rigs"] or 0)
    out = []
    for ground, total in sorted(sites_on.items(), key=lambda kv: -kv[1]):
        if not total:
            continue
        rows = [{"name": name, "sites": v["sites"],
                 "share": round(min(1.0, v["sites"] / total), 4),
                 "rigs": v["rigs"]}
                for name, v in found.get(ground, {}).items()]
        rows.sort(key=lambda r: (-r["share"], r["name"]))
        out.append({"ground": ground, "sites": total, "commodities": rows})
    answer = {"count": len(out), "grounds": out,
              "note": "Where to prospect, not what a site will hold."}
    _grounds_cache["all"] = (now, answer)
    return answer


@app.get("/v1/commodities")
def commodities():
    return {"commodities": COMMODITY_NAMES,
            "densities": DENSITY_TIERS}


# ------------------------------------------------------ wing link (beta)
#
# Commanders mining one body together see each other's Rhinos and rigs on
# their scopes, so nobody drops a rig on top of somebody else's. Nothing is
# written to disk: a wing is a handful of positions held in memory, and a
# member is forgotten WING_TTL_S after their last beat. The code is the only
# key - six characters one commander reads out to the rest - and each beat
# answers with everybody else's last one. The server is one process, so one
# dictionary is the whole of it.

WING_CODE = re.compile(r"^[A-Z2-9]{6}$")
WING_TTL_S = 120.0
WING_MAX_MEMBERS = 8
WING_MAX_WINGS = 5000
# A member beating faster than this is answered without being re-stored.
WING_MIN_GAP_S = 1.5
_wings: dict = {}
_wings_lock = threading.Lock()


class WingRig(BaseModel):
    n: int = Field(ge=1, le=12)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class WingBeat(BaseModel):
    member: str = Field(pattern=r"^[A-Za-z0-9]{8,32}$")
    name: str = Field(default="", max_length=40)
    system: str = Field(default="", max_length=120)
    body: str = Field(default="", max_length=120)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    heading: float | None = Field(default=None, ge=0, le=360)
    in_srv: bool = False
    rigs: list[WingRig] = Field(default_factory=list, max_length=12)
    leave: bool = False


def _wing_sweep(now: float) -> None:
    for code in list(_wings):
        wing = _wings[code]
        for member in [m for m, d in wing.items() if now - d["at"] > WING_TTL_S]:
            del wing[member]
        if not wing:
            del _wings[code]


@app.post("/v1/wing/{code}")
def wing_beat(code: str, beat: WingBeat, authorization: str = Header(default="")):
    """One beat: where this member is, and back, where the rest are."""
    if WRITE_TOKEN and authorization != f"Bearer {WRITE_TOKEN}":
        raise HTTPException(401, "bad or missing token")
    code = (code or "").strip().upper()
    if not WING_CODE.match(code):
        raise HTTPException(422, "a wing code is six letters and digits")
    now = time.time()
    with _wings_lock:
        _wing_sweep(now)
        wing = _wings.get(code)
        if beat.leave:
            if wing is not None:
                wing.pop(beat.member, None)
                if not wing:
                    _wings.pop(code, None)
            return {"code": code, "members": [], "ttl_s": WING_TTL_S}
        if wing is None:
            if len(_wings) >= WING_MAX_WINGS:
                raise HTTPException(503, "too many wings open - try again shortly")
            wing = _wings[code] = {}
        last = wing.get(beat.member)
        if last is None and len(wing) >= WING_MAX_MEMBERS:
            raise HTTPException(409, "that wing is full - %d is the most"
                                % WING_MAX_MEMBERS)
        if last is None or now - last["at"] >= WING_MIN_GAP_S:
            data = beat.model_dump(exclude={"member", "leave"})
            data["at"] = now
            wing[beat.member] = data
        others = [dict({k: v for k, v in data.items() if k != "at"},
                       age_s=round(now - data["at"], 1))
                  for member, data in wing.items() if member != beat.member]
    return {"code": code, "members": others, "ttl_s": WING_TTL_S}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
