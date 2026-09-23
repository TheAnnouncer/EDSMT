"""
The survey: what has been found and where.

The model follows what the game actually does, which is three levels deep:

    body                 you fly to it and run the DSS
      location           "PLANETARY MINING LOCATION SIGNAL (3)" - the DSS
                         finds several per body and lists which commodities
                         might be inside, some already marked depleted
        deposit          "PLANETARY MINING DEPOSIT (HAEMATITE)" - what the
                         Rhino's scanner actually pings once you drive in

Two things follow from that and shape everything here.

First, a location is a promise, not an inventory: it says haematite is
somewhere in this circle, and you still have to drive around to find it. So
locations and deposits are stored separately and a location is useful even
before a single deposit under it has been found.

Second, positions are absolute. The game hands over latitude and longitude,
so a deposit records where it is - not a bearing and a range from some
centre the commander had to stop and set first. Distances are worked out
against wherever you happen to be standing, which is the number you actually
want while driving.

No UI in here. Everything is a plain function or a small holder, so the whole
model is testable without a display.
"""

import os
import csv
import math
import time
import shutil
import calendar
import itertools

DEPOSIT_FIELDS = [
    "id",
    "system",
    "body",
    "location",        # which mining location signal it sits in
    "commodity",
    "rigs",            # unknown until you get there, so often blank
    "density",         # how concentrated it is: Low / Medium / High
    "amount",          # how much is left: Depleted / Low / Medium / High
    "lat",
    "lon",
    "temperature_k",
    "planet_class",    # what kind of body it is, from the journal scan
    "gravity",
    "atmosphere",
    "volcanism",
    "status",          # reported, or verified by staff
    "verified_by",
    "verified_at",
    "recorded",
    "cmdr",
    "notes",
]

LOCATION_FIELDS = [
    "id",
    "system",
    "body",
    "location",        # the number the game gave the signal
    "lat",             # where you were when you logged it
    "lon",
    "radius_m",        # the body's radius, for distance maths
    "commodities",     # what the signal says might be inside, semicolon list
    "depleted",        # which of those it says are already worked out
    "temperature_k",
    "planet_class",
    "gravity",
    "atmosphere",
    "volcanism",
    "recorded",
    "cmdr",
    "notes",
]

# Who says so. A find from any commander is worth having; a find somebody
# from Radio Raxxla has stood on and confirmed is worth more. Verification
# is a multiplier on trust, not an exemption from age - a site verified in
# March is still an empty crater in September.
STATUS_REPORTED = "reported"
STATUS_VERIFIED = "verified"

_counter = itertools.count()


def stamp_note(existing, text, when=None):
    """Add a dated line to a deposit's notes.

    Local time on purpose. Everything stored for the community is UTC so
    that rows from different commanders can be compared, but a note is for
    the person who wrote it, and "Mined 10/09/2026 01:05" should say the
    time they remember rather than an hour they were not awake for.
    """
    when = when or time.localtime()
    line = "%s %s" % (text, time.strftime("%d/%m/%Y %H:%M", when))
    existing = str(existing or "").strip()
    return (existing + "\n" + line).strip() if existing else line


def rows_near(deposits, lat, lon, radius_m, limit=None):
    """Any deposits, nearest first, with range and bearing from (lat, lon).

    One function for the commander's own finds and for everyone else's, so
    the two can never disagree about how far away something is.
    """
    out = []
    for deposit in deposits:
        try:
            dlat, dlon = float(deposit["lat"]), float(deposit["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        metres = surface_range_m(lat, lon, dlat, dlon, radius_m)
        out.append({
            "deposit": deposit,
            "range_m": metres,
            "bearing": bearing_deg(lat, lon, dlat, dlon),
            "lat": dlat, "lon": dlon,
        })
    out.sort(key=lambda row: row["range_m"])
    return out[:limit] if limit else out


def new_id():
    """Short and actually unique.

    A timestamp alone is not: mark two deposits inside the same millisecond,
    which happens the moment anyone leans on the key, and both rows share an
    id - so deleting one deletes the other.
    """
    return "%011x%03x" % (int(time.time() * 1000), next(_counter) % 0xfff)


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# Surface geometry
# ---------------------------------------------------------------------------

def surface_range_m(lat1, lon1, lat2, lon2, radius_m):
    """Great-circle distance across a body's surface, in metres.

    Metres, not kilometres: a mining location is a couple of kilometres
    across and the deposits inside it are hundreds of metres apart, so
    "0.31 km" is a worse way of saying "310 m" when you are driving to it.
    """
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * math.asin(min(1.0, math.sqrt(a))) * float(radius_m)


def bearing_deg(lat1, lon1, lat2, lon2):
    """Which way to point to get from the first place to the second."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def local_offset(from_lat, from_lon, to_lat, to_lon, radius_m):
    """Metres east and north of one point to another.

    This is what the plan view is drawn from. Over the few kilometres a
    mining location spans, treating the surface as flat is accurate to well
    under the width of the SRV, and it means the picture can be drawn with
    straight lines and no projection.
    """
    metres = surface_range_m(from_lat, from_lon, to_lat, to_lon, radius_m)
    theta = math.radians(bearing_deg(from_lat, from_lon, to_lat, to_lon))
    return metres * math.sin(theta), metres * math.cos(theta)


def relative_bearing(heading, bearing):
    """Which way to turn: -180 hard left, 0 straight on, +180 hard right."""
    return ((float(bearing) - float(heading) + 540.0) % 360.0) - 180.0


def compass(bearing):
    """A bearing as something you can say out loud."""
    points = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return points[int((float(bearing) % 360) / 22.5 + 0.5) % 16]


def turn_hint(heading, bearing):
    """Plain words for which way to swing the wheel."""
    offset = relative_bearing(heading, bearing)
    if abs(offset) < 8:
        return "straight ahead"
    if abs(offset) > 165:
        return "turn around"
    side = "right" if offset > 0 else "left"
    if abs(offset) < 45:
        return "slightly %s" % side
    if abs(offset) < 120:
        return "%s" % side
    return "hard %s" % side


# ---------------------------------------------------------------------------
# Commodities
# ---------------------------------------------------------------------------

# The thirteen named in Frontier's 4.4.1.0 notes, plus the ones actually seen
# coming out of the ground since. The patch notes only listed what was NEW -
# surface mining also yields commodities that already existed, which is why
# a location can offer copper, haematite, lithium, palladium and uranium
# without any of them appearing in the update.
#
# This list is SUGGESTIONS, not a rulebook. Anything the game names is
# accepted and remembered, because the alternative is silently refusing to
# record a real find on the grounds that it was not in a list written by
# somebody who had not seen it yet.
# Every commodity a surface deposit is known to yield, with what it sells for
# and which body classes it turns up on.
#
# This came off a commander's own tabulation of the 4.4.1.0 surface mining
# tables, and it replaces a thirteen-entry list I built from Inara's
# "Mining (surface)" flag. That list was wrong twice over: it MISSED things
# the game actually gives you - Water, Tantalum, Jadeite, Methanol Crystals -
# and it had no idea which bodies anything appears on.
#
#   name: (avg_sell, max_sell, category, body classes)
#
# Body classes are the journal's own PlanetClass strings, so they can be
# matched straight against a Scan event without translation.
HMC   = "High metal content body"
RICH  = "Metal rich body"
ROCKY = "Rocky body"
RICE  = "Rocky ice world"
ICY   = "Icy body"

COMMODITIES = {
    # -- chemicals ----------------------------------------------------------
    "Helium":             (102861,  591360, "Chemicals", (HMC, RICH, ROCKY, RICE)),
    "Helium-3":           ( 96223,  553040, "Chemicals", (ICY,)),
    "Tritium":            ( 53311,   61894, "Chemicals", (ICY,)),
    "Water":              (   496,    2964, "Chemicals", (RICE, ICY)),
    # -- metals -------------------------------------------------------------
    "Iridium":            (208463, 1038104, "Metals", (HMC, RICH, ROCKY)),
    "Platinum":           ( 70998,  333030, "Metals", (HMC, RICH, ROCKY)),
    "Palladium":          ( 52167,  302138, "Metals", (HMC, RICH, ROCKY, RICE)),
    "Gold":               ( 48005,  282678, "Metals", (HMC, RICH, ROCKY)),
    "Osmium":             ( 56471,  273000, "Metals", (HMC, RICH, ROCKY)),
    "Silver":             ( 37743,  219318, "Metals", (HMC, RICH, ROCKY)),
    "Samarium":           ( 28362,  154266, "Metals", (HMC, RICH, ROCKY)),
    "Tantalum":           ( 14360,   15582, "Metals", (HMC, RICH, ROCKY)),
    "Thorium":            ( 12297,   12917, "Metals", (HMC, RICH, ROCKY)),
    "Uranium":            (  7599,    8587, "Metals", (HMC, RICH, ROCKY)),
    "Titanium":           (  4800,    5865, "Metals", (HMC, RICH, ROCKY)),
    "Lithium":            (  2099,    2892, "Metals", (HMC, RICH, ROCKY)),
    "Copper":             (   774,    1931, "Metals", (HMC, RICH, ROCKY, RICE)),
    # -- minerals -----------------------------------------------------------
    "Monazite":           (268661,  865908, "Minerals", (ROCKY,)),
    "Alexandrite":        (229207,  714088, "Minerals", (ROCKY,)),
    "Grandidierite":      (213547,  571800, "Minerals", (ROCKY,)),
    "Periclase dunite":   (204168, 1038104, "Minerals", (ROCKY,)),
    "Thortveitite":       (203892, 1038104, "Minerals", (ROCKY,)),
    "Serendibite":        (188438,  570948, "Minerals", (ROCKY,)),
    "Rhodplumsite":       (187921,  826249, "Minerals", (HMC, ROCKY)),
    "Diamond":            (134784,  720648, "Minerals", (HMC, RICH, ROCKY)),
    "Low Temperature Diamonds": (130184, 384562, "Minerals", (ROCKY, RICE, ICY)),
    "Sapphire":           (128050,  648352, "Minerals", (HMC, RICH, ROCKY)),
    "Ruby":               (110381,  589240, "Minerals", (HMC, RICH, ROCKY)),
    "Bastn\u00e4site":     ( 78583,  531208, "Minerals", (ROCKY,)),
    "Quartz pyroxenite":  ( 46469,  312072, "Minerals", (ROCKY, RICE)),
    "Jadeite":            ( 42770,  179421, "Minerals", (ROCKY,)),
    "Deuterium":          ( 40762,  273368, "Minerals", (ROCKY, RICE, ICY)),
    "Magnesite":          ( 38198,  255880, "Minerals", (ROCKY,)),
    "Olivine":            ( 31417,  209938, "Minerals", (ROCKY, RICE)),
    "Uraninite":          (  3006,   17166, "Minerals", (ROCKY,)),
    "Haematite":          (  2800,   10044, "Minerals", (HMC, RICH, ROCKY, RICE)),
    "Methanol Crystals":  (  2525,    3794, "Minerals", (ICY,)),
}

# The list is SUGGESTIONS, not a rulebook. Anything the game names is
# accepted and remembered, because the alternative is silently refusing to
# record a real find on the grounds that it was not in a list written by
# somebody who had not seen it yet.
KNOWN_COMMODITIES = sorted(COMMODITIES, key=lambda n: -COMMODITIES[n][0])


def fold(text):
    """Compare commodity names loosely.

    Bastnäsite, Bastnasite, BASTNASITE and $bastnasite_name; all have to land
    on the same commodity, or half a shared database files under a second
    name and no search ever finds it.
    """
    import unicodedata
    raw = unicodedata.normalize("NFKD", str(text or ""))
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return "".join(c for c in raw.lower() if c.isalnum())


_LOOKUP = {fold(name): name for name in KNOWN_COMMODITIES}

# The journal does not always spell a commodity the way the market does, and
# folding alone cannot close the gap where the difference is a plural. A
# MarketSell says "lowtemperaturediamond"; everything else in the game, and
# this whole file, says "Low Temperature Diamonds". Without this the same
# commodity files under two names and the sold column stops matching the
# deposits column. Anything else found to differ belongs here rather than in
# a second lookup somewhere else.
_JOURNAL_SPELLINGS = {
    "lowtemperaturediamond": "Low Temperature Diamonds",
}
_LOOKUP.update({fold(k): v for k, v in _JOURNAL_SPELLINGS.items()})


def canonical(name):
    """The tidiest spelling of a commodity - the known one where there is
    one, otherwise a cleaned-up version of whatever the game said."""
    text = str(name or "").strip().strip("$;").replace("_name", "")
    if not text:
        return ""
    known = _LOOKUP.get(fold(text))
    if known:
        return known
    return text.replace("_", " ").strip().title()


def remember(name):
    """Add something the game named to the suggestions, for next time."""
    tidy = canonical(name)
    if tidy and fold(tidy) not in _LOOKUP:
        _LOOKUP[fold(tidy)] = tidy
        KNOWN_COMMODITIES.append(tidy)
    return tidy


# Two different things, and conflating them loses information the game
# gives you for free. DENSITY is how concentrated the deposit is and never
# changes. AMOUNT is how much is left, and walks down to Depleted as it is
# worked. A site can be High density and Depleted at the same time - worth
# coming back to, nothing there today.
#
# These are the game's own words. Frontier have not published either list,
# so anything else seen in the wild is still accepted and stored as given;
# these are what the boxes offer, not a gate.
# Sorting the commodity box: what a commander sold it for beats what the
# tables say, and both beat nothing. The maximum column is deliberately NOT
# used for ordering - Iridium, Periclase Dunite and Thortveitite all cap at
# exactly 1,038,104, which is the Metz Enterprise community goal rate, not
# what they are worth. Averages survive the CG ending; ceilings do not.
SURFACE_PRICES = {name: data[0] for name, data in COMMODITIES.items()}
_PUBLISHED = {fold(name): data[0] for name, data in COMMODITIES.items()}
_CEILING = {fold(name): data[1] for name, data in COMMODITIES.items()}
_BODIES = {fold(name): data[3] for name, data in COMMODITIES.items()}
_CATEGORY = {fold(name): data[2] for name, data in COMMODITIES.items()}

# Anything outside the table still needs an order. Ring and laser commodities
# that are not known to surface get a coarse band so they sort sensibly if a
# commander records one anyway.
VALUE_BANDS = {
    5: ["Void Opals", "Painite", "Musgravite", "Benitoite"],
    4: ["Praseodymium", "Bromellite", "Bertrandite", "Indite", "Gallite",
        "Moissanite"],
    3: ["Coltan", "Lepidolite", "Lanthanum"],
    2: ["Bauxite", "Rutile", "Cobalt", "Bismuth", "Thallium"],
    1: ["Aluminium"],
}
_VALUE = {}
for _band, _names in VALUE_BANDS.items():
    for _name in _names:
        _VALUE[fold(_name)] = _band


def published_price(name):
    """Average galactic sell price, for anything in the surface table."""
    return _PUBLISHED.get(fold(name), 0)


def ceiling_price(name):
    """The best price anybody has seen. Inflated by a running CG - see above."""
    return _CEILING.get(fold(name), 0)


def category(name):
    """Chemicals, Metals or Minerals. The market screen groups by these."""
    return _CATEGORY.get(fold(name), "")


def bodies_for(name):
    """Which body classes this commodity turns up on."""
    return _BODIES.get(fold(name), ())


def on_body(name, planet_class):
    """Could this commodity be here?

    Unknown commodities and unknown bodies both answer True. A tool that
    hides a real find because its own table had not heard of the body is
    worse than one that shows a commodity you will not find.
    """
    wanted = fold(planet_class or "")
    if not wanted:
        return True
    classes = bodies_for(name)
    if not classes:
        return True
    return any(fold(c) == wanted for c in classes)


def for_body(names, planet_class):
    """Split a commodity list into (possible here, everything else)."""
    here, rest = [], []
    for name in names:
        (here if on_body(name, planet_class) else rest).append(name)
    return here, rest


def value_band(name):
    """Roughly how much it is worth, 5 high to 1 low, 0 for unknown.

    Unknown scores 0 rather than guessing, and sorts below everything
    priced - a commodity nobody has sold yet is not the same as a cheap
    one, and pretending otherwise would bury the new finds this whole
    database exists to catalogue.
    """
    return _VALUE.get(fold(name), 0)


def by_value(names, prices=None):
    """Commodity names, best first.

    Live prices win where we have them, the coarse bands fill in the rest,
    and anything still unknown goes last in alphabetical order so it can at
    least be found.
    """
    prices = prices or {}

    def key(name):
        # Four tiers, best evidence first. What a commander actually sold it
        # for beats what Inara publishes, which beats a band somebody wrote
        # down, which beats nothing.
        live = prices.get(fold(name))
        if live:
            return (0, -float(live), name.lower())
        listed = published_price(name)
        if listed:
            return (1, -listed, name.lower())
        band = value_band(name)
        if band:
            return (2, -band, name.lower())
        return (3, 0, name.lower())

    return sorted(names, key=key)


def matches(names, typed):
    """Filter a commodity list as somebody types.

    Names that START with what was typed come first, because that is what
    typing three letters means; names that merely contain it follow. The
    fold means "bastna" finds Bastn\u00e4site without the umlaut.
    """
    needle = fold(typed)
    if not needle:
        return list(names)
    starts = [n for n in names if fold(n).startswith(needle)]
    inside = [n for n in names if needle in fold(n) and n not in starts]
    return starts + inside


DENSITY_TIERS = ["Low", "Medium", "High"]
AMOUNT_TIERS = ["Depleted", "Low", "Medium", "High"]

# Ranking treats "gone" as worse than "a little", which needs an order.
_AMOUNT = {fold(n): i for i, n in enumerate(AMOUNT_TIERS)}


def amount_rank(name):
    """Where an amount sits on the scale, or -1 if it is not one we know."""
    return _AMOUNT.get(fold(name), -1)


def is_depleted(name):
    return fold(name) in (fold("depleted"), fold("exhausted"), fold("empty"))


# Older files, and anyone who typed one of these, still resolve.
_LEGACY_DENSITY = ["Depleted", "Low", "Medium", "High", "Pristine"]
_DENSITY = {fold(n): i for i, n in enumerate(_LEGACY_DENSITY)}
_DENSITY.update({fold("very low"): 1, fold("moderate"): 2, fold("very high"): 4,
                 fold("rich"): 4, fold("major"): 4, fold("minor"): 1,
                 fold("common"): 2, fold("exhausted"): 0, fold("empty"): 0})


def density_rank(value):
    """0-4 for a density label, or -1 when it is not one we recognise."""
    if value in (None, ""):
        return -1
    return _DENSITY.get(fold(value), -1)


# ---------------------------------------------------------------------------
# Where to land
# ---------------------------------------------------------------------------
#
# Which body in this system is worth putting the ship down on. Built from
# four things, each shown in its own column so nothing is taken on trust:
#
#   what the game said    - landable, distance, body class, volcanism, and
#                           how many mining locations the DSS counted
#   what everyone shared  - the sites already logged on each body, and what
#                           sites on the same kind of ground have carried
#   what you have done    - your own locations there, and how much of each
#                           survey area you have swept
#   what it is worth      - the best price known for each commodity
#
# The value is an ESTIMATE and the window says so. It is the known sites
# still intact at what they carry, plus each location nobody has shared yet
# at what a site on that ground usually carries.

# A kind of ground needs this many shared sites before its mix of
# commodities is trusted over the tables. Two sites are an anecdote.
LAND_MIN_SITES = 3

# How many commodities the Best bets column names.
LAND_BETS = 3


def ground_of(planet_class, volcanism):
    """One name for a kind of ground: body class, plus volcanism if any.

    MUST give exactly what the community map's ground_of gives - the grounds
    it counts are looked up by this string.
    """
    kind = " ".join(str(planet_class or "").split())
    volc = " ".join(str(volcanism or "").lower().replace("volcanism", "").split())
    if volc in ("", "none", "no"):
        return kind
    return "%s, %s" % (kind, volc) if kind else volc


def short_body(system, body):
    """"Col 285 Sector ZL-K b22-2 A 1" in that system is just "A 1"."""
    system, body = str(system or "").strip(), str(body or "").strip()
    if system and len(body) > len(system) and body.lower().startswith(system.lower()):
        return body[len(system):].strip() or body
    return body


def price_of(name, prices=None):
    """Best price known: what a market showed, else the published average."""
    live = (prices or {}).get(fold(name))
    try:
        if live:
            return float(live)
    except (TypeError, ValueError):
        pass
    return float(published_price(name) or 0)


def grounds_by_name(grounds):
    """The server's /v1/grounds answer as {ground, lower-cased: entry}."""
    if isinstance(grounds, dict):
        grounds = grounds.get("grounds") or []
    out = {}
    for entry in grounds or []:
        if isinstance(entry, dict) and entry.get("ground"):
            out[str(entry["ground"]).lower()] = entry
    return out


def ground_mix(ground, planet_class, grounds=None):
    """What a site on this ground tends to carry: (basis, [(name, share)]).

    From everyone's shared sites once there are LAND_MIN_SITES of them on
    this ground; otherwise from the tables - every commodity known to turn
    up on this body class, weighted evenly, which is honest about knowing
    nothing more than that. Basis is what the window prints, so which of
    the two it was is never hidden.
    """
    entry = grounds_by_name(grounds).get(str(ground or "").lower())
    if entry and int(entry.get("sites") or 0) >= LAND_MIN_SITES:
        mix = []
        for item in entry.get("commodities") or []:
            try:
                share = float(item.get("share") or 0)
            except (TypeError, ValueError):
                share = 0.0
            if item.get("name") and share > 0:
                mix.append((str(item["name"]), min(1.0, share)))
        if mix:
            return "%d shared sites" % int(entry["sites"]), mix
    if not planet_class:
        return "", []
    possible = [name for name in KNOWN_COMMODITIES
                if bodies_for(name) and on_body(name, planet_class)]
    if not possible:
        return "", []
    even = 1.0 / len(possible)
    return "tables", [(name, even) for name in possible]


def rank_bodies(system, bodies, grounds=None, sites=None, prices=None,
                deposits=None, locations=None, swept=None,
                landable_only=True):
    """Every body in a system worth landing on, best first.

    bodies     the journal's system_bodies() rows
    grounds    the server's /v1/grounds answer (or None, offline)
    sites      the server's /v1/sites rows for this system (or None)
    prices     {fold(name): price} from markets seen
    deposits   your own deposit rows; locations: your own location rows
    swept      {body, lower-cased: best percent swept} from the survey maps

    A body nobody scanned but somebody shared a site on, or you mined, is
    still listed: somebody has stood on it.
    """
    prices = prices or {}
    system_l = str(system or "").strip().lower()

    def mine(row):
        return str(row.get("system") or "").strip().lower() == system_l

    rows = {}

    def entry(body):
        key = str(body or "").strip().lower()
        if key not in rows:
            rows[key] = {
                "body": str(body).strip(), "short": short_body(system, body),
                "landable": None, "distance_ls": None, "planet_class": "",
                "volcanism": "", "ground": "", "gravity_g": None,
                "temperature_k": None, "locations": None, "mapped": False,
                "known": 0, "intact": 0, "worked": 0, "verified": 0,
                "known_rigs": 0, "known_types": [], "known_value": 0.0,
                "yours": 0, "your_deposits": 0, "your_worked": 0,
                "swept": None, "basis": "", "bets": [], "per_site": 0.0,
                "value": 0.0, "tier": 3, "note": "",
            }
        return rows[key]

    for body in bodies or []:
        if not isinstance(body, dict) or not body.get("body"):
            continue
        row = entry(body["body"])
        row["landable"] = body.get("landable")
        row["distance_ls"] = body.get("distance_ls")
        row["planet_class"] = str(body.get("planet_class") or "")
        row["volcanism"] = str(body.get("volcanism") or "")
        row["gravity_g"] = _number(body.get("gravity_g"))
        row["temperature_k"] = _number(body.get("temperature_k"))
        row["mapped"] = bool(body.get("mapped"))
        count = int(body.get("locations") or 0)
        # Zero from a body the DSS never mapped is "not looked", not "none".
        row["locations"] = count if (count or row["mapped"]) else None

    for site in sites or []:
        if not isinstance(site, dict) or not site.get("planet"):
            continue
        if str(site.get("system") or system).strip().lower() != system_l:
            continue
        row = entry(site["planet"])
        row["known"] += 1
        if site.get("worked_out"):
            row["worked"] += 1
            continue
        row["intact"] += 1
        if str(site.get("status") or "") == "verified":
            row["verified"] += 1
        rigs = int(_number(site.get("rigs")) or 0)
        row["known_rigs"] += rigs
        types = [str(t) for t in (site.get("types") or []) if str(t).strip()]
        row["known_types"] = sorted(set(row["known_types"]) | set(types),
                                    key=lambda n: -price_of(n, prices))
        row["known_value"] += sum(price_of(t, prices) for t in set(types))

    for place in locations or []:
        if isinstance(place, dict) and mine(place) and place.get("body"):
            entry(place["body"])["yours"] += 1
    for found in deposits or []:
        if isinstance(found, dict) and mine(found) and found.get("body"):
            row = entry(found["body"])
            row["your_deposits"] += 1
            if is_depleted(found.get("amount")):
                row["your_worked"] += 1
            if not row["planet_class"] and found.get("planet_class"):
                row["planet_class"] = str(found["planet_class"])
                row["volcanism"] = str(found.get("volcanism") or "")

    for key, percent in (swept or {}).items():
        if str(key).strip().lower() in rows and percent is not None:
            rows[str(key).strip().lower()]["swept"] = int(percent)

    out = []
    for row in rows.values():
        stood_on = row["known"] or row["yours"] or row["your_deposits"]
        if row["landable"] is None and stood_on:
            row["landable"] = True
        if landable_only and not row["landable"]:
            continue
        row["ground"] = ground_of(row["planet_class"], row["volcanism"])
        basis, mix = ground_mix(row["ground"], row["planet_class"], grounds)
        row["basis"] = basis
        row["per_site"] = round(sum(share * price_of(name, prices)
                                    for name, share in mix), 0)
        row["bets"] = sorted(mix, key=lambda pair: -pair[1] * price_of(pair[0], prices))[:LAND_BETS]
        unshared = 0
        if row["locations"] is not None:
            unshared = max(0, row["locations"] - row["known"])
        row["value"] = round(row["known_value"] + unshared * row["per_site"], 0)
        row["tier"], row["note"] = _land_verdict(row, unshared)
        out.append(row)

    out.sort(key=lambda r: (r["tier"], -r["value"],
                            r["distance_ls"] is None, r["distance_ls"] or 0,
                            r["short"].lower()))
    return out


def _land_verdict(row, unshared):
    """(tier, one line saying why), tier 0 best. Must not raise."""
    if not row["landable"]:
        return 3, "Not landable."
    if row["intact"]:
        extra = ("; %d more location(s) nobody has shared" % unshared
                 if unshared else "")
        return 0, ("%d known site(s) still intact, %d rig(s)%s."
                   % (row["intact"], row["known_rigs"], extra))
    if unshared:
        return 0, ("DSS: %d location(s) nobody has shared - first look is yours."
                   % unshared)
    if row["locations"] is None:
        return 1, "Not mapped - map it with the DSS to count its locations."
    if row["known"] and row["worked"] == row["known"]:
        return 2, "Every known site here has been reported worked out."
    return 2, "The DSS found no mining locations here."


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

class Survey:
    """Every location and deposit this commander has recorded.

    Held in memory and written through on every change. One commander's file
    is a few thousand rows at the very most, so there is no reason to be
    cleverer, and every reason not to be: a crash mid-session must never cost
    a find.
    """

    def __init__(self, folder):
        self.folder = folder
        self.deposits_path = os.path.join(folder, "deposits.csv")
        self.locations_path = os.path.join(folder, "locations.csv")
        self.deposits = []
        self.locations = []
        self.load()

    def load(self):
        self.deposits = _read(self.deposits_path, DEPOSIT_FIELDS)
        self.locations = _read(self.locations_path, LOCATION_FIELDS)
        for row in self.deposits:
            if row.get("commodity"):
                remember(row["commodity"])

    def save_deposits(self):
        _write(self.deposits_path, DEPOSIT_FIELDS, self.deposits)

    def save_locations(self):
        _write(self.locations_path, LOCATION_FIELDS, self.locations)

    # -- locations -------------------------------------------------------

    def location(self, system, body, number):
        for row in self.locations:
            if (_same(row["system"], system) and _same(row["body"], body)
                    and _same(row["location"], number)):
                return row
        return None

    def locations_on(self, system, body):
        out = [r for r in self.locations
               if _same(r["system"], system) and _same(r["body"], body)]
        return sorted(out, key=lambda r: _natural(r["location"]))

    def set_location(self, system, body, number, lat=None, lon=None,
                     radius_m=None, commodities=None, depleted=None,
                     temperature_k=None, cmdr="",
                     planet_class=None, gravity=None, atmosphere=None,
                     volcanism=None, notes=None):
        """Record or update a mining location signal.

        Only the fields actually supplied are touched, so logging a position
        later does not wipe the commodity list read off the signal earlier,
        and vice versa.

        planet_class / gravity / atmosphere / volcanism describe the world
        the signal is on. LOCATION_FIELDS has carried those four columns
        since they were added, and this signature did not - so mark_deposit
        raised TypeError every time it created a signal row, which is the
        FIRST F10 on every new body. The deposit was already written to the
        CSV by then, so it survived; everything after the raise did not.
        Nothing was shared, nothing was redrawn, and from the button Tk
        swallowed the error entirely.

        notes was the last column left in that same trap: carried by
        LOCATION_FIELDS, absent from here, so set_location(..., notes=...)
        was a TypeError waiting for the first caller that wanted to say
        where a signal came from. It is APPENDED rather than assigned -
        alone among these fields it is prose somebody may have written, and
        "imported from another tool" is not worth losing a commander's own
        note over.
        """
        row = self.location(system, body, number)
        if row is None:
            row = {key: "" for key in LOCATION_FIELDS}
            row.update({"id": new_id(), "system": system, "body": body,
                        "location": str(number)})
            self.locations.append(row)
        if lat is not None and lon is not None:
            row["lat"] = "%.6f" % float(lat)
            row["lon"] = "%.6f" % float(lon)
        if radius_m:
            row["radius_m"] = "%.0f" % float(radius_m)
        if commodities is not None:
            row["commodities"] = ";".join(canonical(c) for c in commodities if c)
        if depleted is not None:
            row["depleted"] = ";".join(canonical(c) for c in depleted if c)
        if temperature_k is not None:
            row["temperature_k"] = "%.1f" % float(temperature_k)
        for key, value in (("planet_class", planet_class), ("gravity", gravity),
                           ("atmosphere", atmosphere), ("volcanism", volcanism)):
            if value not in (None, ""):
                row[key] = str(value)
        if cmdr:
            row["cmdr"] = cmdr
        if notes:
            row["notes"] = stamp_note(row.get("notes"), notes)
        row["recorded"] = utc_now()
        self.save_locations()
        return row

    @staticmethod
    def offered(row):
        """What a location says might be inside it."""
        if not row:
            return []
        return [c for c in str(row.get("commodities") or "").split(";") if c]

    @staticmethod
    def worked_out(row):
        """Which of those the game has already marked depleted."""
        if not row:
            return []
        return [c for c in str(row.get("depleted") or "").split(";") if c]

    # -- deposits --------------------------------------------------------

    def add_deposit(self, **row):
        entry = {key: "" for key in DEPOSIT_FIELDS}
        entry.update({k: v for k, v in row.items() if k in DEPOSIT_FIELDS})
        entry["id"] = entry["id"] or new_id()
        entry["recorded"] = entry["recorded"] or utc_now()
        if entry["commodity"]:
            entry["commodity"] = remember(entry["commodity"])
        self.deposits.append(entry)
        self.save_deposits()
        return entry

    def update_deposit(self, deposit_id, **changes):
        for row in self.deposits:
            if row["id"] == deposit_id:
                for key, value in changes.items():
                    if key in DEPOSIT_FIELDS and key != "id":
                        row[key] = value
                self.save_deposits()
                return row
        return None

    def backup_to(self, folder):
        """Copy everything worth keeping into one dated zip.

        A zip rather than loose files, because the thing that actually
        loses somebody's finds is not a disk failure - it is copying half
        the files, or copying them somewhere they forget, or a rebuild that
        wipes %LOCALAPPDATA%. One file with a date on it survives all
        three, and can be mailed to somebody who can read it.
        """
        import zipfile
        os.makedirs(folder, exist_ok=True)
        name = "EDSMT-backup-%s.zip" % time.strftime("%Y%m%d-%H%M%S")
        target = os.path.join(folder, name)
        wrote = 0
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as bundle:
            for filename in sorted(os.listdir(self.folder)):
                path = os.path.join(self.folder, filename)
                if not os.path.isfile(path):
                    continue
                if filename.endswith((".csv", ".json", ".log")):
                    bundle.write(path, filename)
                    wrote += 1
        if not wrote:
            os.remove(target)
            return None, 0
        return target, wrote

    def restore_from(self, zip_path):
        """Put a backup back, keeping what is already here out of the way.

        The current files are moved aside rather than overwritten. Somebody
        restoring a backup is already having a bad day; taking their last
        session away as the price of getting the rest back would make it
        worse.
        """
        import zipfile
        stamp = time.strftime("%Y%m%d-%H%M%S")
        restored = 0
        with zipfile.ZipFile(zip_path) as bundle:
            names = [n for n in bundle.namelist()
                     if not n.endswith("/") and "/" not in n and "\\" not in n]
            if not names:
                return 0
            for filename in names:
                current = os.path.join(self.folder, filename)
                if os.path.exists(current):
                    shutil.move(current, current + ".before-restore-" + stamp)
                bundle.extract(filename, self.folder)
                restored += 1
        self.load()
        return restored

    def remove_deposit(self, deposit_id):
        before = len(self.deposits)
        self.deposits = [d for d in self.deposits if d["id"] != deposit_id]
        if len(self.deposits) != before:
            self.save_deposits()
            return True
        return False

    def remove_location(self, location_id):
        """Forget a mining location signal.

        Deposits recorded under it are deliberately NOT deleted. A signal
        logged against the wrong number is a bookkeeping mistake; the
        deposits were still real places somebody drove to. They keep their
        signal number and stay on the map, and the caller is told how many
        are now unattached so it can say so rather than quietly orphaning
        them.
        """
        before = len(self.locations)
        row = None
        for candidate in self.locations:
            if candidate["id"] == location_id:
                row = candidate
                break
        if row is None:
            return None
        orphans = len(self.at(row["system"], row["body"], row["location"]))
        self.locations = [r for r in self.locations if r["id"] != location_id]
        if len(self.locations) != before:
            self.save_locations()
        return orphans

    def renumber_location(self, system, body, old, new):
        """Change a signal's number, and carry its deposits with it.

        Renumbering the signal alone would strand every deposit under a
        number that no longer exists, which is worse than the wrong number
        it started with.
        """
        old, new = str(old).strip(), str(new).strip()
        if not new or _same(old, new):
            return 0
        if self.location(system, body, new) is not None:
            raise ValueError("Signal %s already exists on this body." % new)
        row = self.location(system, body, old)
        if row is None:
            return 0
        row["location"] = new
        moved = 0
        for deposit in self.at(system, body, old):
            deposit["location"] = new
            moved += 1
        self.save_locations()
        if moved:
            self.save_deposits()
        return moved

    def set_offered(self, location_id, commodities):
        """Replace what a location says might be inside it."""
        for row in self.locations:
            if row["id"] == location_id:
                row["commodities"] = ";".join(
                    canonical(c) for c in commodities if str(c).strip())
                self.save_locations()
                return True
        return False

    def at(self, system, body, location=None):
        out = [d for d in self.deposits
               if _same(d["system"], system) and _same(d["body"], body)]
        if location is not None:
            out = [d for d in out if _same(d["location"], location)]
        return out

    # -- what is near you ------------------------------------------------

    def near(self, system, body, lat, lon, radius_m, limit=None):
        """Deposits on this body, nearest first, with range and bearing.

        Worked out from where you are standing rather than from a centre you
        had to set: that is the number that helps while driving, and it means
        nothing has to be pressed before a deposit can be marked.
        """
        return rows_near(self.at(system, body), lat, lon, radius_m, limit)

    # Bringing an older file forward used to live here, as adopt_legacy().
    # It was a second, worse importer: it refused outright the moment this
    # commander had a single find of their own ("or self.deposits"), it
    # returned 0 whether it had worked or been refused, and it read density
    # and recorded columns the imported layouts have never had. edsmt.py's
    # import_finds does the same job against every format the app reads,
    # keyed on file contents rather than on an empty database, so one file
    # cannot arrive twice and a commander with finds can still migrate.


# ---------------------------------------------------------------------------
# What a run was worth
# ---------------------------------------------------------------------------

# A mining run is one shape: drop to the surface, fill the hold, fly somewhere
# that buys it, sell. The money only exists at the far end of that, an hour and
# often a system away from the hole it came out of, so the two halves have to
# be held together by something.
SESSION_FIELDS = [
    "id",
    "started",         # UTC, off the journal's own clock where there is one
    "ended",           # the last thing that happened in it - see Earnings
    "closed",          # blank while the run is still live
    "system",          # where it was dug up
    "body",
    "station",         # where it was sold
    "sold_in",         # and the system that station is in
    "mined",           # "Haematite:112;Copper:40" - what came out of the ground
    "sold",            # same shape, but what actually crossed the counter
    "credits",         # every TotalSale added up
    "cost",            # what was paid for any of it in the first place
    "cr_hr",
    "sales",           # how many times the sell button was pressed
    "cmdr",
    "notes",
]

# How long a live run may go quiet before it is written off as over.
#
# Nothing else is guaranteed to end one. The sale normally does, but a
# commander who lands, fills the hold and then stops playing leaves a run with
# no ending at all - and a run that never ends is a run that quietly swallows
# the takings of the next three. Six hours is well past any single sitting and
# nowhere near a break for a cup of tea.
RUN_IDLE_S = 6 * 3600


def pack_counts(counts):
    """A commodity tally as one CSV cell: "Haematite:112;Copper:40".

    Largest first, because what you want from a glance at a row is what the
    run was mostly about. Colons and semicolons are safe separators here for
    the same reason the location commodity list already uses one - no
    commodity name has ever contained either.
    """
    rows = []
    for name, count in dict(counts or {}).items():
        try:
            count = int(count)
        except (TypeError, ValueError):
            continue
        if count and str(name).strip():
            rows.append((str(name).strip(), count))
    rows.sort(key=lambda row: (-row[1], row[0].lower()))
    return ";".join("%s:%d" % row for row in rows)


def unpack_counts(text):
    """Read one back. Anything malformed is skipped rather than guessed at."""
    out = {}
    for chunk in str(text or "").split(";"):
        name, _, count = chunk.rpartition(":")
        name = name.strip()
        if not name:
            continue
        try:
            out[name] = out.get(name, 0) + int(count.strip())
        except ValueError:
            continue
    return out


def add_counts(into, more):
    """Fold one tally into another, in place."""
    for name, count in dict(more or {}).items():
        try:
            count = int(count)
        except (TypeError, ValueError):
            continue
        name = str(name).strip()
        if name and count:
            into[name] = into.get(name, 0) + count
    return into


def _epoch(stamp):
    """A journal timestamp as seconds, or 0 when it is not one.

    Fractional seconds are trimmed rather than rejected. The journal writes
    whole seconds today, but a row that fails to parse takes the run's whole
    duration with it, and losing an hourly rate over three digits would be a
    stupid way to lose it.
    """
    text = str(stamp or "").strip()
    if "." in text:
        text = text.split(".", 1)[0] + "Z"
    try:
        return calendar.timegm(time.strptime(text, "%Y-%m-%dT%H:%M:%SZ"))
    except (ValueError, TypeError):
        return 0


def _later(first, second):
    """Whichever of two timestamps is the later one, ignoring nonsense."""
    if not _epoch(second):
        return first
    if not _epoch(first):
        return second
    return first if _epoch(first) >= _epoch(second) else second


def hours_between(start, end):
    """How long a run lasted, in hours. Zero when it cannot be worked out."""
    first, last = _epoch(start), _epoch(end)
    if not first or not last or last <= first:
        return 0.0
    return (last - first) / 3600.0


def _number(value):
    try:
        return float(str(value).strip() or 0)
    except (TypeError, ValueError):
        return 0.0


def earned(row):
    """What was actually kept: the sale total, less what the cargo cost.

    Mined cargo costs nothing, so for a mining run this is simply the sale.
    The subtraction is there for the run that ends at a station where the
    commander also shifts something they bought earlier - without it, a
    hundred tonnes of tea bought at 200 and sold at 300 would report as
    thirty thousand credits of mining.
    """
    return _number(row.get("credits")) - _number(row.get("cost"))


def credits_per_hour(row):
    """What the run was worth an hour.

    A run with no measurable length answers 0 rather than dividing by it. A
    sale the app only caught after the fact starts and ends in the same
    second, and "infinity credits an hour" is not a number anybody can use.
    """
    hours = hours_between(row.get("started"), row.get("ended"))
    return earned(row) / hours if hours > 0 else 0.0


def hold_value(counts, prices):
    """What a hold would fetch at the prices in front of you.

    prices is keyed the way fold() keys everything else, so a Market.json
    that spells it "$bastnasite_name;" still prices a hold that says
    Bastnasite. A commodity with no price here contributes nothing rather
    than a guess - the figure is meant to be a floor you can trust, not an
    estimate you have to caveat.
    """
    prices = {fold(k): v for k, v in dict(prices or {}).items()}
    total = 0.0
    for name, count in dict(counts or {}).items():
        total += _number(prices.get(fold(name))) * _number(count)
    return total


class Earnings:
    """Every mining run this commander has banked, and what it paid.

    One row per run, written through on every change - and for a stronger
    reason than the survey has. A run is only finished when the cargo is
    sold, which is an hour and a system away from where it was dug up, so
    the row is kept complete the whole way rather than assembled at the end.

    That is what "ended" means here: the last thing that happened in the
    run, not the moment it was closed. It is rewritten on every event, so a
    crash, a kill or a power cut costs the closing flag and nothing else -
    the credits, the hours and the rate on disk are already right.

    All of the policy about what starts and ends a run lives in observe(),
    so the whole thing can be driven by a list of dictionaries with no game,
    no files and no display.
    """

    def __init__(self, folder):
        self.folder = folder
        self.path = os.path.join(folder, "sessions.csv")
        self.sessions = []
        # Whether the ship is sitting on a pad. Not stored: it is only used
        # to stop a cargo load at a station reading as ore, and after a
        # restart the next Docked or Undocked says which it is.
        self._docked = False
        self.load()

    def load(self):
        self.sessions = _read(self.path, SESSION_FIELDS)
        changed = False
        # Only the last row can still be in progress. An earlier one left
        # open - by two copies of the app running at once, or by a file
        # written before this column existed - can never become current
        # again, so it is closed rather than left looking live for ever.
        live = [row for row in self.sessions
                if not str(row.get("closed") or "").strip()]
        for row in live[:-1]:
            self._close(row, row.get("ended") or row.get("started"))
            changed = True
        # And a run left open days ago is not this evening's. Close it on the
        # way in, before it can collect somebody else's credits.
        row = self.current
        if row is not None:
            stale = _epoch(row.get("ended")) or _epoch(row.get("started"))
            if stale and (_epoch(utc_now()) - stale) > RUN_IDLE_S:
                self._close(row, row.get("ended") or row.get("started"))
                changed = True
        if changed:
            self.save()

    def save(self):
        _write(self.path, SESSION_FIELDS, self.sessions)

    @property
    def current(self):
        """The run still in progress, if there is one."""
        for row in reversed(self.sessions):
            if not str(row.get("closed") or "").strip():
                return row
        return None

    def recent(self, limit=None):
        """Runs newest first, which is the order anybody wants to read them."""
        rows = sorted(self.sessions,
                      key=lambda row: _epoch(row.get("started")), reverse=True)
        return rows[:limit] if limit else rows

    # -- keeping the books -----------------------------------------------

    def start(self, system="", body="", cmdr="", when=None):
        when = str(when or "").strip() or utc_now()
        row = {key: "" for key in SESSION_FIELDS}
        row.update({"id": new_id(), "started": when, "ended": when,
                    "system": str(system or ""), "body": str(body or ""),
                    "cmdr": str(cmdr or ""),
                    "credits": "0", "cost": "0", "sales": "0", "cr_hr": "0"})
        self.sessions.append(row)
        self.save()
        return row

    def note_mined(self, gains, when=None):
        """Add what just came out of the ground to the run in progress."""
        row = self.current
        if row is None or not gains:
            return None
        tally = unpack_counts(row.get("mined"))
        add_counts(tally, {canonical(name): count
                           for name, count in dict(gains).items()})
        row["mined"] = pack_counts(tally)
        for name in tally:
            remember(name)
        self._touch(row, when)
        self.save()
        return row

    def note_sale(self, commodity, count, total, avg_paid=0, station="",
                  system="", when=None):
        """Credit a sale to the run in progress."""
        row = self.current
        if row is None:
            return None
        name = canonical(commodity)
        try:
            count = int(count or 0)
        except (TypeError, ValueError):
            count = 0
        if name and count:
            tally = unpack_counts(row.get("sold"))
            add_counts(tally, {name: count})
            row["sold"] = pack_counts(tally)
            remember(name)
        row["credits"] = "%d" % (_number(row.get("credits")) + _number(total))
        row["cost"] = "%d" % (_number(row.get("cost"))
                              + _number(avg_paid) * count)
        row["sales"] = "%d" % (_number(row.get("sales")) + 1)
        if station:
            row["station"] = str(station)
        if system:
            row["sold_in"] = str(system)
        self._touch(row, when)
        self.save()
        return row

    def finish(self, when=None, notes=""):
        """Bank the run in progress."""
        row = self.current
        if row is None:
            return None
        self._close(row, when, notes)
        self.save()
        return row

    def _close(self, row, when=None, notes=""):
        stamp = str(when or "").strip()
        if stamp:
            row["ended"] = _later(row.get("ended") or stamp, stamp)
        row["closed"] = row["ended"] or utc_now()
        if notes:
            row["notes"] = (str(row.get("notes") or "") + "\n" + notes).strip()
        self._rate(row)

    def _touch(self, row, when=None):
        stamp = str(when or "").strip() or utc_now()
        row["ended"] = _later(row.get("ended") or stamp, stamp)
        self._rate(row)

    def _rate(self, row):
        """Keep the hourly rate on the row rather than only in the app.

        It is derived, and normally a derived column is a liability. This one
        earns its place: sessions.csv is the file somebody opens in a
        spreadsheet to compare last night against last week, and a column of
        raw timestamps does not answer that question without arithmetic.
        """
        row["cr_hr"] = "%d" % round(credits_per_hour(row))

    # -- driving it from the journal --------------------------------------

    def observe(self, note):
        """Take one thing the reader saw and do the bookkeeping for it.

        Returns a short line worth putting on screen when something changed,
        and None when nothing did.
        """
        if not isinstance(note, dict):
            return None
        name = str(note.get("event") or "")
        when = str(note.get("when") or "").strip() or utc_now()

        # Whatever arrives next, a run that has been silent for hours is
        # over, and it ended when it went silent - not now.
        row = self.current
        if row is not None:
            last = _epoch(row.get("ended")) or _epoch(row.get("started"))
            if last and (_epoch(when) - last) > RUN_IDLE_S:
                self.finish(row.get("ended"), "closed - the run went quiet")
                row = None

        if name == "Touchdown":
            # Putting the ship on a landing pad is not the start of a mining
            # run, and neither is a ship that landed without you in it.
            if note.get("on_station") or note.get("player") is False:
                return None
            body = str(note.get("body") or "")
            if row is not None and not _same(row.get("body"), body):
                self.finish(when)
                row = None
            if row is None:
                self.start(note.get("system"), body, note.get("cmdr"), when)
                return "run started"
            self._touch(row, when)
            self.save()
            return None

        if name == "Cargo":
            # A hold that fills at a station is a purchase, not a haul.
            if row is None or self._docked:
                return None
            gained = note.get("gained") or {}
            if not gained:
                return None
            self.note_mined(gained, when)
            return "mined " + pack_counts(gained)

        if name == "Docked":
            self._docked = True
            if row is None:
                return None
            row["station"] = str(note.get("station") or "")
            row["sold_in"] = str(note.get("system") or "")
            self._touch(row, when)
            self.save()
            return None

        if name == "MarketSell":
            # Credits with nowhere to go are credits lost. A sale that turns
            # up with no run open - the app was started after the mining was
            # done - opens one at the moment of the sale rather than being
            # dropped on the floor.
            if row is None:
                self.start(note.get("system"), note.get("body"),
                           note.get("cmdr"), when)
            self.note_sale(note.get("commodity"), note.get("count"),
                           note.get("total"), note.get("avg_paid") or 0,
                           note.get("station") or "",
                           note.get("system") or "", when)
            return "sold " + str(note.get("commodity") or "")

        if name == "Undocked":
            self._docked = False
            # Sold up and leaving: that is the run finished. Undocking with
            # nothing sold is just a stop on the way, so it is left running.
            if row is not None and _number(row.get("sales")) > 0:
                self.finish(when)
                return "run banked"
            return None

        if name == "Shutdown":
            if row is not None:
                self.finish(when)
                return "run banked"
            return None

        if name == "Liftoff":
            if row is not None:
                self._touch(row, when)
                self.save()
            return None

        return None

    # -- adding it up -----------------------------------------------------

    def totals(self, rows=None):
        """Lifetime figures, or those of whichever rows are handed in."""
        rows = self.sessions if rows is None else rows
        mined, sold = {}, {}
        credits_ = cost = hours = 0.0
        for row in rows:
            add_counts(mined, unpack_counts(row.get("mined")))
            add_counts(sold, unpack_counts(row.get("sold")))
            credits_ += _number(row.get("credits"))
            cost += _number(row.get("cost"))
            hours += hours_between(row.get("started"), row.get("ended"))
        return {
            "runs": len(rows),
            "credits": credits_,
            "cost": cost,
            "earned": credits_ - cost,
            "hours": hours,
            "cr_hr": (credits_ - cost) / hours if hours > 0 else 0.0,
            "mined": mined,
            "sold": sold,
        }


def _same(a, b):
    return str(a or "").strip().lower() == str(b or "").strip().lower()


def _natural(value):
    text = str(value).strip()
    try:
        return (0, float(text), "")
    except ValueError:
        return (1, 0.0, text.lower())


def _read(path, fields):
    """Read a CSV, tolerating whatever Windows did to it."""
    if not os.path.exists(path):
        return []
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with open(path, "r", encoding=encoding, newline="") as handle:
                return [{key: (row.get(key) or "") for key in fields}
                        for row in csv.DictReader(handle)]
        except (UnicodeDecodeError, LookupError):
            continue
        except OSError:
            return []
    return []


def _write(path, fields, rows):
    """Write via a temporary file, so a crash cannot truncate the real one."""
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        temp = path + ".tmp"
        with open(temp, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in fields})
        if os.path.exists(path):
            shutil.copy2(path, path + ".bak")
        os.replace(temp, path)
        return True
    except OSError:
        return False
