"""Find filters, saved searches, body and signal search, and the best five.

Pure logic: no Tk, no network, no files except the saved searches. The
windows ask this module whether a row stays; they never decide it
themselves, so one set of rules and one set of tests cover Find, Where to
land and My sites.

Every filter that needs a fact a row does not carry hides the row and says
so. A price with no pad on it is not a price for a large ship, and a body
nobody has measured is not a body under 1.5 g - a filter that kept them
would be a filter that lies. The count line gives the reasons, so "37 of
212 shown" is never a mystery.
"""
import json
import math
import os
import re
import tempfile
import time

import survey as SV

SEARCHES_FILE = "searches.json"
SEARCHES_MAX = 40
NAME_MAX = 40

# -- a number typed in a box ---------------------------------------------------

_SUFFIX = {"k": 1e3, "m": 1e6}


def parse_number(text, default=None):
    """A number out of what somebody typed: "1,500", "100k", "2.5m", " 40 ".
    `default` for blank or nonsense. Never raises."""
    raw = str(text if text is not None else "").strip().lower().replace(",", "")
    raw = raw.replace(" ", "").rstrip("lyt")
    if not raw:
        return default
    scale = 1.0
    if raw[-1] in _SUFFIX:
        scale, raw = _SUFFIX[raw[-1]], raw[:-1]
    try:
        value = float(raw) * scale
    except ValueError:
        return default
    return default if (value != value or value in (math.inf, -math.inf)) else value


def whole_number(text, default=None):
    value = parse_number(text, None)
    return default if value is None else int(round(value))


# -- stations ------------------------------------------------------------------

# A fleet carrier's callsign is the name its market is filed under. Used only
# when the row says nothing about what kind of station it is.
CARRIER_CALLSIGN = re.compile(r"^[A-Za-z0-9]{3}-[A-Za-z0-9]{3}$")

STATION_CHOICES = (("Any", ""), ("Starports", "starport"),
                   ("Outposts", "outpost"), ("Planetary ports", "planetary"),
                   ("Asteroid bases", "asteroid"))
PAD_CHOICES = (("Any", ""), ("M or larger", "M"), ("L only", "L"))
PRICE_AGES = (("Any age", 0), ("6 hours", 6 * 3600), ("24 hours", 86400),
              ("3 days", 3 * 86400), ("7 days", 7 * 86400),
              ("30 days", 30 * 86400))
POWER_STATES = ("Any", "Stronghold", "Fortified", "Exploited", "Unoccupied")
POWER_SIDES = (("Any", ""), ("My power", "mine"), ("Another power", "other"),
               ("No power", "none"))
SHOW_CHOICES = (("All rows", ""), ("Best five payers per commodity", "price"),
                ("Five nearest per commodity", "distance"))


def station_group(kind, name=""):
    """One word for a kind of station: starport, outpost, planetary,
    asteroid, megaship, settlement, carrier - or "" when it is not known.

    The type is the game's or the index's own word ("Coriolis", "Orbis
    Starport", "CraterPort", "Fleet Carrier", "FleetCarrier"), so it is
    matched on what it contains, not on one spelling."""
    text = SV.fold(kind)
    if text:
        if "carrier" in text:
            return "carrier"
        if "settlement" in text or "onfoot" in text:
            return "settlement"
        if "mega" in text:
            return "megaship"
        if "asteroid" in text:
            return "asteroid"
        if "crater" in text or "planetary" in text or "surface" in text:
            return "planetary"
        if "outpost" in text:
            return "outpost"
        if any(word in text for word in ("coriolis", "orbis", "ocellus",
                                         "starport", "bernal")):
            return "starport"
        return ""
    if CARRIER_CALLSIGN.match(str(name or "").strip()):
        return "carrier"
    return ""


def pad_rank(pad):
    """0 unknown, 1 small, 2 medium, 3 large - from "L", 3, "Large"."""
    if isinstance(pad, bool) or pad in (None, ""):
        return 0
    if isinstance(pad, (int, float)):
        return int(pad) if 1 <= int(pad) <= 3 else 0
    text = str(pad).strip().upper()
    if text in ("S", "M", "L", "SMALL", "MEDIUM", "LARGE"):
        return {"S": 1, "M": 2, "L": 3}[text[:1]]
    try:
        return pad_rank(int(text))
    except ValueError:
        return 0


def _epoch(stamp):
    return SV._epoch(stamp) or 0


def _number(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out else out


def row_distance(row):
    """Light years from the commander, off a Find row, or None."""
    for key in ("distance_ly", "distance"):
        far = _number(row.get(key))
        if far is not None:
            return far
    return None


# -- the Find filters ------------------------------------------------------------

DEFAULT_FIND = {
    "from_ly": None, "to_ly": None, "pad": "", "age_s": 0, "min_demand": None,
    "max_demand": None, "min_price": None, "station": "",
    "no_carriers": True, "state": "", "power": "", "show": "",
}

# What a hidden row is counted under, in the words the count line uses.
REASONS = {
    "no_demand": "nobody buying (Demand 0)",
    "pad": "pad too small or unknown",
    "age": "price too old or undated",
    "demand": "demand outside your window",
    "price": "price under your minimum",
    "type": "other kind of station",
    "carrier": "fleet carriers",
    "distance": "outside your distance window",
    "state": "not that Powerplay state (or not known)",
    "power": "not that side of Powerplay (or not known)",
    "top": "beyond the best five of their commodity",
}


def find_spec(**changes):
    spec = dict(DEFAULT_FIND)
    spec.update({k: v for k, v in changes.items() if k in DEFAULT_FIND})
    return spec


def active_filters(spec):
    """The extra Find filters that are on, as plain words."""
    spec = spec or {}
    on = []
    if spec.get("from_ly"):
        on.append("From %g Ly" % spec["from_ly"])
    if spec.get("to_ly"):
        on.append("Within %g Ly" % spec["to_ly"])
    if spec.get("pad"):
        on.append("Pad %s" % spec["pad"])
    if spec.get("age_s"):
        on.append("Price age %s" % _name_of(PRICE_AGES, spec["age_s"]))
    if spec.get("min_demand") is not None:
        on.append("Demand at least %d" % spec["min_demand"])
    if spec.get("max_demand") is not None:
        on.append("Demand at most %d" % spec["max_demand"])
    if spec.get("min_price"):
        on.append("Price at least %d" % spec["min_price"])
    if spec.get("station"):
        on.append("Station %s" % _name_of(STATION_CHOICES, spec["station"]))
    if spec.get("no_carriers"):
        on.append("No fleet carriers")
    if spec.get("state"):
        on.append("State %s" % spec["state"])
    if spec.get("power"):
        on.append("Power %s" % _name_of(POWER_SIDES, spec["power"]))
    return on


def _name_of(choices, value):
    for name, key in choices:
        if key == value:
            return name
    return str(value)


def why_hidden(row, spec, kind="", now=None, power_of=None, mine=""):
    """Why the extra Find filters hide this row - a key of REASONS - or "".

    kind is the Find table: sites / intact / search for finds, sell / market
    for prices. A price never shows with Demand 0, whatever the filters.
    `power_of(system)` is the commander's Powerplay record of a system (or
    None) and `mine` his pledged power.
    """
    spec = spec or DEFAULT_FIND
    if kind == "published":
        # The published figures are one line per commodity, with no station,
        # system or distance to filter on.
        return ""
    prices = kind in ("sell", "market")
    if prices:
        demand = _number(row.get("demand"))
        if demand is not None and (demand <= 0 or demand == 999999):
            return "no_demand"
    far = row_distance(row)
    low = spec.get("from_ly")
    if low:
        if far is None or far < low:
            return "distance"
    # The other end of the window. A row whose distance nobody knows stays:
    # a search sent with a radius only answers with what it could measure,
    # and without a position there is nothing to measure from.
    high = spec.get("to_ly")
    if high and far is not None and far > high:
        return "distance"
    if prices:
        group = station_group(row.get("station_type"), row.get("station"))
        if spec.get("no_carriers") and group == "carrier":
            return "carrier"
        if spec.get("station") and group != spec["station"]:
            return "type"
        if spec.get("pad") and pad_rank(row.get("pad")) < pad_rank(spec["pad"]):
            return "pad"
        if spec.get("age_s"):
            at = _epoch(row.get("seen"))
            current = time.time() if now is None else now
            if not at or current - at > spec["age_s"]:
                return "age"
        low_d, high_d = spec.get("min_demand"), spec.get("max_demand")
        if low_d is not None or high_d is not None:
            demand = _number(row.get("demand"))
            if demand is None or (low_d is not None and demand < low_d) \
                    or (high_d is not None and demand > high_d):
                return "demand"
        if spec.get("min_price"):
            price = _number(row.get("sell"))
            if price is None or price < spec["min_price"]:
                return "price"
    if (spec.get("state") or spec.get("power")) and kind != "published":
        entry = power_of(row.get("system")) if power_of else None
        state = str((entry or {}).get("state") or "")
        owner = str((entry or {}).get("power") or "")
        if spec.get("state") and state.lower() != spec["state"].lower():
            return "state"
        side = spec.get("power")
        if side:
            if entry is None:
                return "power"
            if side == "mine" and not (mine and owner.lower() == mine.lower()):
                return "power"
            if side == "other" and (not owner or owner.lower() == str(mine).lower()):
                return "power"
            if side == "none" and owner:
                return "power"
    return ""


def count_line(shown, total, counts, kept_note=""):
    """The sentence under the table. "37 result(s)." when nothing is hidden.
    With rows hidden: how many, and exactly why."""
    counts = {k: n for k, n in (counts or {}).items() if n}
    if not total:
        return "0 result(s)."
    if shown == total:
        return "%d result(s)." % total
    why = ", ".join("%d %s" % (n, REASONS.get(k, k))
                    for k, n in sorted(counts.items(), key=lambda kv: -kv[1]))
    return "%d of %d shown - %d hidden by your filters%s%s." % (
        shown, total, total - shown, (": " + why) if why else "", kept_note)


# -- best five ---------------------------------------------------------------------

def _price_key(row):
    far = row_distance(row)
    return (-(_number(row.get("sell")) or 0), far is None, far or 0.0)


def _distance_key(row):
    far = row_distance(row)
    return (far is None, far or 0.0, -(_number(row.get("sell")) or 0))


def top_per_commodity(rows, n=5, by="price"):
    """The best `n` rows of each commodity - by price, or nearest first -
    grouped in the order the commodities first appear."""
    key = _distance_key if by == "distance" else _price_key
    groups, order = {}, []
    for row in rows:
        name = SV.fold(row.get("commodity"))
        if name not in groups:
            groups[name] = []
            order.append(name)
        groups[name].append(row)
    out = []
    for name in order:
        out.extend(sorted(groups[name], key=key)[:n])
    return out


def best_five(rows, n=5):
    """{"payers": [...], "nearest": [...]} for one commodity's price rows.

    Rows with no price or no buyers are dropped - the caller has normally
    judged them already, this is the belt to that pair of braces. Nearest
    leaves out rows whose distance nobody knows: a blank is not a zero."""
    live = [r for r in rows if (_number(r.get("sell")) or 0) > 0
            and (_number(r.get("demand")) is None or _number(r.get("demand")) > 0)
            and _number(r.get("demand")) != 999999]
    payers = sorted(live, key=_price_key)[:n]
    near = sorted((r for r in live if row_distance(r) is not None),
                  key=_distance_key)[:n]
    return {"payers": payers, "nearest": near}


# -- saved searches ----------------------------------------------------------------

def _clean(value, depth=0):
    """A value fit for the saved file: plain strings, numbers, bools, lists."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value if value == value else None
    if isinstance(value, str):
        return value[:200]
    if isinstance(value, (list, tuple)) and depth < 2:
        return [_clean(v, depth + 1) for v in list(value)[:60]]
    if isinstance(value, dict) and depth < 2:
        return {str(k)[:40]: _clean(v, depth + 1)
                for k, v in list(value.items())[:60]}
    return str(value)[:200]


class Favourites:
    """The searches a commander saved by name: every filter in the window as
    it stood. A file of their own beside the other records, so a backup
    carries it. Never raises."""

    def __init__(self, folder=None, name=SEARCHES_FILE):
        self.path = os.path.join(folder, name) if folder else ""
        self.items = {}
        self.load()

    def load(self):
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        rows = data.get("searches") if isinstance(data, dict) else None
        if isinstance(rows, dict):
            self.items = {str(k)[:NAME_MAX]: v for k, v in rows.items()
                          if isinstance(v, dict) and isinstance(v.get("state"), dict)}

    def save(self):
        if not self.path:
            return False
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            handle, temp = tempfile.mkstemp(dir=os.path.dirname(self.path) or ".",
                                            prefix="searches-", suffix=".tmp")
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                json.dump({"searches": self.items}, out)
            os.replace(temp, self.path)
            return True
        except OSError:
            return False

    @staticmethod
    def tidy(name):
        return " ".join(str(name or "").split())[:NAME_MAX]

    def names(self, window=""):
        """Saved names, newest first. `window` keeps one window's own."""
        rows = [(v.get("saved") or "", k) for k, v in self.items.items()
                if not window or v.get("window", "find") == window]
        return [k for _when, k in sorted(rows, reverse=True)]

    def get(self, name):
        entry = self.items.get(self.tidy(name))
        return dict(entry["state"]) if entry else None

    def put(self, name, state, window="find", when=None):
        """Save (or replace) a search. False for a blank name, or when the
        list is full and this would be a new one."""
        name = self.tidy(name)
        if not name or not isinstance(state, dict):
            return False
        if name not in self.items and len(self.items) >= SEARCHES_MAX:
            return False
        self.items[name] = {"state": _clean(state), "window": window,
                            "saved": SV.utc_now() if when is None else when}
        self.save()
        return True

    def delete(self, name):
        gone = self.items.pop(self.tidy(name), None) is not None
        if gone:
            self.save()
        return gone


# -- bodies and signals --------------------------------------------------------------

BODY_SHORT = (("HMC", SV.HMC), ("Rich", SV.RICH), ("Rocky", SV.ROCKY),
              ("Rocky ice", SV.RICE), ("Icy", SV.ICY))
VOLCANISM_CHOICES = ("Any", "None", "Any volcanism", "Silicate magma",
                     "Metallic magma", "Rocky magma", "Water", "Carbon dioxide",
                     "Methane", "Nitrogen", "Ammonia", "Sulphur dioxide",
                     "Silicate vapour", "Helium")
SIGNAL_CHOICES = ("Any", "Mining locations", "Geological", "Biological",
                  "Human", "Guardian", "Thargoid")
SIGNAL_KIND = {"Mining locations": "mining", "Geological": "geological",
               "Biological": "biological", "Human": "human",
               "Guardian": "guardian", "Thargoid": "thargoid"}
SCOPES = (("This system", "here"), ("Near here (remembered)", "near"),
          ("Anywhere remembered", "all"))
SITE_SCOPES = (("All my sites", "all"), ("This system", "here"),
               ("Near here", "near"))
NEAR_LY = {"25 Ly": 25, "50 Ly": 50, "100 Ly": 100, "250 Ly": 250,
           "500 Ly": 500, "1000 Ly": 1000}
BODY_ROW_CAP = 400

DEFAULT_BODY = {
    "scope": "here", "within_ly": 100.0, "classes": [], "volcanism": [],
    "g_min": None, "g_max": None, "k_min": None, "k_max": None,
    "signals": [], "signal_min": 1, "landable": False, "mapped": False,
    "ls_max": None, "system": "",
}

BODY_REASONS = {
    "class": "other kind of body", "volcanism": "other volcanism",
    "gravity": "gravity outside the range or unmeasured",
    "temperature": "temperature outside the range or unmeasured",
    "signals": "too few of those signals (or not mapped)",
    "landable": "not landable", "mapped": "not mapped with the DSS",
    "ls": "too far from the star", "distance": "too far away or position unknown",
    "system": "in another system",
}


def body_spec(**changes):
    spec = dict(DEFAULT_BODY)
    spec.update({k: v for k, v in changes.items() if k in DEFAULT_BODY})
    return spec


def signal_kind(text):
    """"Biological" / "$SAA_SignalType_Geological;" / "Planetary mining
    location" -> biological / geological / mining ... or "other"."""
    low = str(text or "").lower()
    if re.search(r"mining|deposit|resource", low):
        return "mining"
    if "saa_signaltype_" in low:
        low = low.split("saa_signaltype_", 1)[1]
    for word in ("geological", "biological", "human", "guardian", "thargoid"):
        if word in low:
            return word
    return "other"


def signal_counts(signals):
    """{kind: count} for a body's [{"type", "count"}] list."""
    out = {}
    for sig in signals or ():
        if not isinstance(sig, dict):
            continue
        # The language-free symbol first (#263): a French or German client
        # writes the words in its own language.
        kind = signal_kind(sig.get("symbol")) if sig.get("symbol") else "other"
        if kind == "other":
            kind = signal_kind(sig.get("type"))
        try:
            out[kind] = out.get(kind, 0) + int(sig.get("count") or 0)
        except (TypeError, ValueError):
            continue
    return out


def light_years(a, b):
    if not a or not b or len(a) != 3 or len(b) != 3:
        return None
    try:
        return math.sqrt(sum((float(p) - float(q)) ** 2 for p, q in zip(a, b)))
    except (TypeError, ValueError):
        return None


def body_row(system, body, facts=None, signals=None, mapped=False,
             source="", position=None, here=None):
    """One remembered body as a row the body filters and the tables use.

    `facts` is the bodybook's own (gravity in m/s2, as the journal has it);
    the row carries g. `position` is the system's, `here` the commander's."""
    facts = facts or {}
    gravity = _number(facts.get("gravity_g"))
    if gravity is None:
        raw = _number(facts.get("gravity"))
        gravity = round(raw / 9.80665, 3) if raw else None
    counts = signal_counts(signals)
    planet_class = str(facts.get("planet_class") or "")
    # Blank says "never described"; the journal writes "None" for a body
    # that was described and has no volcanism.
    volcanism = str(facts.get("volcanism") or "")
    mining = counts.get("mining")
    return {
        "system": str(system or ""), "body": str(body or ""),
        "short": SV.short_body(system, body), "planet_class": planet_class,
        "volcanism": volcanism,
        "ground": SV.ground_of(planet_class, volcanism),
        "gravity_g": gravity, "temperature_k": _number(facts.get("temperature_k")),
        "distance_ls": _number(facts.get("distance_ls")),
        "landable": facts.get("landable"), "mapped": bool(mapped),
        "signals": list(signals) if isinstance(signals, list) else None,
        "counts": counts, "locations": mining, "source": source,
        "distance_ly": light_years(position, here),
        "atmosphere": str(facts.get("atmosphere") or ""),
    }


def _volcanism_ok(text, wanted):
    """Whether a body's volcanism is one of the ticked kinds. A blank is a
    body whose volcanism was never described - the journal's own "None" is
    how a described body with no volcanism arrives - and it matches none of
    them."""
    if not text:
        return False
    low = SV.fold(text)
    none = low in ("none", "novolcanism")
    for choice in wanted:
        word = SV.fold(choice)
        if word == "any":
            return True
        if word == "none" and none:
            return True
        if word == "anyvolcanism" and not none:
            return True
        if word not in ("none", "anyvolcanism") and word in low:
            return True
    return False


def why_body_hidden(row, spec):
    """Why a body filter hides this body - a key of BODY_REASONS - or ""."""
    spec = spec or DEFAULT_BODY
    classes = [SV.fold(c) for c in spec.get("classes") or ()]
    if classes and SV.fold(row.get("planet_class")) not in classes:
        return "class"
    if spec.get("volcanism") and not _volcanism_ok(row.get("volcanism"),
                                                   spec["volcanism"]):
        return "volcanism"
    low, high = spec.get("g_min"), spec.get("g_max")
    if low is not None or high is not None:
        value = _number(row.get("gravity_g"))
        if value is None or (low is not None and value < low) \
                or (high is not None and value > high):
            return "gravity"
    low, high = spec.get("k_min"), spec.get("k_max")
    if low is not None or high is not None:
        value = _number(row.get("temperature_k"))
        if value is None or (low is not None and value < low) \
                or (high is not None and value > high):
            return "temperature"
    if spec.get("signals"):
        counts = row.get("counts")
        if counts is None:
            counts = signal_counts(row.get("signals"))
        need = max(1, int(spec.get("signal_min") or 1))
        for choice in spec["signals"]:
            kind = SIGNAL_KIND.get(choice, choice)
            if counts.get(kind, 0) < need:
                return "signals"
    if spec.get("landable") and not row.get("landable"):
        return "landable"
    if spec.get("mapped") and not row.get("mapped"):
        return "mapped"
    if spec.get("ls_max") is not None:
        ls = _number(row.get("distance_ls"))
        if ls is None or ls > spec["ls_max"]:
            return "ls"
    if spec.get("scope") == "here" and spec.get("system") and \
            SV.fold(row.get("system")) != SV.fold(spec["system"]):
        return "system"
    if spec.get("scope") == "near":
        far = _number(row.get("distance_ly"))
        limit = spec.get("within_ly")
        if limit and (far is None or far > limit):
            return "distance"
    return ""


def filter_bodies(rows, spec):
    """(kept, {reason: how many}) - the bodies that pass every filter."""
    kept, counts = [], {}
    for row in rows:
        reason = why_body_hidden(row, spec)
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
        else:
            kept.append(row)
    return kept, counts


def body_filters_on(spec):
    """The body filters that are on, in plain words."""
    spec = spec or {}
    on = []
    if spec.get("classes"):
        short = {full: name for name, full in BODY_SHORT}
        on.append("Type " + ", ".join(short.get(c, c) for c in spec["classes"]))
    if spec.get("volcanism"):
        on.append("Volcanism " + ", ".join(spec["volcanism"]))
    if spec.get("g_min") is not None or spec.get("g_max") is not None:
        on.append("Gravity %s-%s g" % (
            "" if spec.get("g_min") is None else "%g" % spec["g_min"],
            "" if spec.get("g_max") is None else "%g" % spec["g_max"]))
    if spec.get("k_min") is not None or spec.get("k_max") is not None:
        on.append("Temperature %s-%s K" % (
            "" if spec.get("k_min") is None else "%g" % spec["k_min"],
            "" if spec.get("k_max") is None else "%g" % spec["k_max"]))
    if spec.get("signals"):
        on.append("%s at least %d" % (", ".join(spec["signals"]),
                                      max(1, int(spec.get("signal_min") or 1))))
    if spec.get("landable"):
        on.append("Landable")
    if spec.get("mapped"):
        on.append("Mapped")
    if spec.get("ls_max") is not None:
        on.append("Within %g Ls" % spec["ls_max"])
    return on


def body_count_line(shown, total, counts):
    """The sentence under a body table, with the reasons for what is hidden."""
    if not total:
        return "No bodies to filter."
    if shown == total:
        return "%d bodies." % total
    why = ", ".join("%d %s" % (n, BODY_REASONS.get(k, k))
                    for k, n in sorted((counts or {}).items(), key=lambda kv: -kv[1]) if n)
    return "%d of %d bodies match - %d hidden%s." % (
        shown, total, total - shown, (": " + why) if why else "")


# -- Find's searches, one at a time (1.10038) -----------------------------------
#
# A switch at the top of Find chooses the search, and only that search's
# filters are on screen. One that is not on screen keeps its value but does
# not act: a filter nobody can see quietly emptying a table would be worse
# than the clutter this replaces.

MODES = (("sites", "Sites"), ("intact", "Still there"), ("deposits", "Deposits"),
         ("prices", "Sell prices"), ("bodies", "Mining bodies"))
DEFAULT_MODE = "sites"

_FIND_FILTERS = ("commodity", "min_rigs", "min_types", "seen", "within", "place",
                 "hide_worked", "verified")
MODE_FILTERS = {
    "sites": _FIND_FILTERS, "intact": _FIND_FILTERS, "deposits": _FIND_FILTERS,
    # "place" is the system box. For prices it means near which system:
    # prices near what is typed, or near where you are when it is blank.
    "prices": ("commodity", "from", "within", "place", "pad", "station", "carriers",
               "price_age", "min_price", "demand", "power_state", "power_side",
               "show"),
    # And for Mining bodies it narrows the bodies to a system or body name.
    "bodies": ("commodity", "within", "place"),
}

# Which search a table belongs to, by the kind of table the window draws.
KIND_MODES = {"sites": "sites", "intact": "intact", "search": "deposits",
              "sell": "prices", "market": "prices", "published": "prices",
              "bodies": "bodies"}

# The filter each part of a find_spec comes from, and that part switched off.
SPEC_FILTERS = {"from_ly": "from", "to_ly": "within", "pad": "pad",
                "age_s": "price_age", "min_demand": "demand", "max_demand": "demand",
                "min_price": "min_price", "station": "station",
                "no_carriers": "carriers", "state": "power_state",
                "power": "power_side", "show": "show"}
SPEC_OFF = dict(DEFAULT_FIND, no_carriers=False)


def mode_key(value):
    """A search's key from its key or its label. Anything else is Sites."""
    text = str(value or "").strip().lower()
    for key, label in MODES:
        if text in (key, label.lower()):
            return key
    return DEFAULT_MODE


def mode_label(mode):
    return dict(MODES)[mode_key(mode)]


def mode_filters(mode):
    """The filters on screen for this search, in the order they are shown."""
    return MODE_FILTERS[mode_key(mode)]


def mode_of_kind(kind):
    """The search a table of this kind belongs to, or "" for none."""
    return KIND_MODES.get(str(kind or ""), "")


def mode_spec(spec, mode):
    """A copy of the Find spec with every filter this search does not show
    switched off."""
    shown = set(mode_filters(mode))
    out = dict(DEFAULT_FIND if spec is None else spec)
    for key, name in SPEC_FILTERS.items():
        if name not in shown:
            out[key] = SPEC_OFF[key]
    return out
