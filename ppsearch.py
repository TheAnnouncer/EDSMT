"""Find's Powerplay search (1.10040): where to mine and where to sell for a
Powerplay goal, as rows of the community map.

Pure logic: no Tk, no network. The window reads its boxes into a spec(),
query() turns that into what the community server is asked, and rows() and
cells() turn the answer into the table. Which pairs of systems count for a
goal is the server's decision; this module never second-guesses it, except
that a fleet carrier is never shown whatever comes back.

Merits an hour are the community map's own figure. Where it has not
measured enough to give one, the column says "-": a number that is wrong
once is worse than no number.
"""
import datetime as dt
import statistics
import time

import finder as FD
import powerplay as PW
import survey as SV

TAG = "powerplay-search"
NOT_ASKED = "Powerplay state: press Search to see how fresh it is."

AUTO, NO_POWER = "Auto (journal)", "None"
POWER_CHOICES = (AUTO,) + tuple(PW.POWERS) + (NO_POWER,)
GOALS = (("Reinforce", "reinforce"), ("Acquire", "acquire"),
         ("Undermine", "undermine"))
# For Undermine, the rival whose systems are hit; for the other two, how
# many other Powers are present - in the sell system for Acquire, the
# mining system otherwise. Multiple is three or more.
CONTESTED = (("Any", ""), ("None", "none"), ("One", "one"), ("Two", "two"),
             ("Multiple", "multiple")) + tuple((p, p) for p in PW.POWERS)
STATES = ("Any", "Stronghold", "Fortified", "Exploited", "Unoccupied", "Contested")
SHOW = ("10", "30", "50", "100", "200")
DEFAULT_SHOW, MOST_ROWS = "30", 200

DEFAULT_SPEC = {"power": AUTO, "goal": "Reinforce", "contested": "Any",
                "state": "Any", "show": DEFAULT_SHOW, "commodities": [],
                "pad": "", "min_demand": None, "max_demand": None, "age_s": 0,
                "range_rule": True, "tonnes_hr": 0.0}

HEADERS = ("System", "Distance", "Power", "State", "Contested by", "Body",
           "Signal", "Commodity", "Rigs", "Amount / Density", "Still there",
           "Last seen", "Found by", "Sell station", "Pad", "Ls", "Sell price",
           "Demand", "Price age", "Mine-to-sell Ly", "Est. Cr/hr",
           "Est. merits/hr")
SELL_SYSTEM = "Sell system"


def spec(**changes):
    """What the Powerplay filters say, as query() takes it."""
    out = dict(DEFAULT_SPEC)
    out.update({k: v for k, v in changes.items() if k in DEFAULT_SPEC})
    return out


def my_power(choice, pledge):
    """The Power a search is for: the journal's pledge for Auto, nothing for
    None, otherwise the Power picked."""
    choice = str(choice or "").strip()
    if not choice or choice == AUTO:
        return str(pledge or "").strip()
    if choice == NO_POWER:
        return ""
    return choice


def _key(choices, label, default=""):
    for name, key in choices:
        if name == label or key == label:
            return key
    return default


def query(filters, pledge=""):
    """The parameters the community server is asked with. Only what is set:
    every default is the server's own."""
    filters = spec(**(filters or {}))
    out = {"goal": _key(GOALS, filters["goal"], "reinforce")}
    power = my_power(filters["power"], pledge)
    if power:
        out["power"] = power
    opposing = _key(CONTESTED, filters["contested"])
    if opposing:
        out["opposing"] = opposing
    if filters["state"] and filters["state"] != "Any":
        out["state"] = filters["state"]
    try:
        limit = int(str(filters["show"]).strip())
    except ValueError:
        limit = int(DEFAULT_SHOW)
    out["limit"] = max(1, min(limit, MOST_ROWS))
    names = [n for n in filters["commodities"] or () if n]
    if names:
        out["commodity"] = ",".join(names)
    if filters["pad"]:
        out["pad"] = filters["pad"]
    for key in ("min_demand", "max_demand"):
        if filters[key] is not None:
            out[key] = int(filters[key])
    if filters["age_s"]:
        out["price_age_h"] = round(filters["age_s"] / 3600.0, 2)
        if out["price_age_h"] == int(out["price_age_h"]):
            out["price_age_h"] = int(out["price_age_h"])
    if not filters["range_rule"]:
        out["range_rule"] = "false"
    if filters["tonnes_hr"] and filters["tonnes_hr"] > 0:
        out["tonnes_hr"] = round(float(filters["tonnes_hr"]), 1)
    return out


def own_rate(sessions):
    """The commander's own tonnes an hour: the median over the sessions
    that dug something. 0 until there is one."""
    rates = []
    for row in sessions or ():
        try:
            rate = SV.tonnes_per_hour(row)
        except (TypeError, ValueError, AttributeError):
            continue
        if rate > 0:
            rates.append(rate)
    return float(statistics.median(rates)) if rates else 0.0


# -- the answer ----------------------------------------------------------------

def older(data):
    """True when the answer came from a server that has no Powerplay search
    at all - the edonline client says so on its 404."""
    return isinstance(data, dict) and bool(data.get("older"))


def freshness(data):
    """The line saying how fresh the Powerplay state is."""
    fresh = (data or {}).get("freshness") if isinstance(data, dict) else None
    line = str((fresh or {}).get("line") or "").strip()
    return line or "Powerplay state: none on the community map yet."


def empty_text(data):
    """What an empty table says."""
    data = data if isinstance(data, dict) else {}
    if data.get("unplaced"):
        return "The community map does not know where %s is yet." % data["unplaced"]
    if data.get("missing"):
        return "No Powerplay rows yet: %s" % data["missing"]
    return ("No place to mine and sell matched - nobody has shared a site in "
            "a system that counts for that goal yet.")


def pledge_note(data):
    """A word when the rows earn nothing because no Power was given."""
    found = (data or {}).get("rows") or [] if isinstance(data, dict) else []
    if found and not any(r.get("eligible") for r in found if isinstance(r, dict)):
        return ("No Power pledged - these would earn merits only once you "
                "pledge. Set My power, or pledge in the game.")
    return ""


def _carrier(sell):
    return FD.station_group(sell.get("station_type"), sell.get("station")) == "carrier"


def rows(data):
    """The answer's rows flattened for the table, one per place to mine and
    place to sell. A fleet carrier is never one of them."""
    out = []
    for item in (data or {}).get("rows") or [] if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        mine, sell = item.get("mine") or {}, item.get("sell") or {}
        est = item.get("est") or {}
        if not isinstance(mine, dict) or not isinstance(sell, dict) or _carrier(sell):
            continue
        out.append({
            "system": mine.get("system") or "", "distance_ly": mine.get("distance_ly"),
            "power": mine.get("power") or "", "state": mine.get("state") or "",
            "contested_by": list(mine.get("contested_by") or []),
            "body": mine.get("body") or "", "planet": mine.get("body") or "",
            "spot": str(mine.get("spot") or ""), "commodity": mine.get("commodity") or "",
            "rigs": mine.get("rigs"), "amount": mine.get("amount") or "",
            "density": mine.get("density") or "", "intact": mine.get("intact"),
            "worked_out": bool(mine.get("worked_out")),
            "last_seen": mine.get("last_seen") or "",
            "found_by": mine.get("found_by") or "",
            "station": sell.get("station") or "", "sell_system": sell.get("system") or "",
            "pad": sell.get("pad"), "ls": sell.get("ls"), "sell": sell.get("price"),
            "demand": sell.get("demand"), "seen": sell.get("seen") or "",
            "station_type": sell.get("station_type") or "",
            "mine_sell_ly": item.get("mine_sell_ly"),
            "cr_hr": est.get("cr_hr"), "merits_hr": est.get("merits_hr"),
            "eligible": bool(item.get("eligible")), "why": item.get("why") or ""})
    return out


def headers(goal=""):
    """The columns. The sell system only for Acquire: for the other two it
    is the system mined in."""
    heads = list(HEADERS)
    if str(goal or "").lower() == "acquire":
        heads.insert(heads.index("Sell station") + 1, SELL_SYSTEM)
    return tuple(heads)


def _num(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out else out


def _epoch(stamp):
    """A server time, "Z" or "+00:00", as seconds - or 0 when it is not one."""
    text = str(stamp or "").strip()
    if not text:
        return 0
    try:
        when = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return 0
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return when.timestamp()


def _ago(stamp, now):
    at = _epoch(stamp)
    if not at:
        return None
    return max(0.0, now - at)


def _days_words(age):
    if age is None:
        return "-"
    days = age / 86400.0
    if days < 1:
        return "today"
    if days < 2:
        return "yesterday"
    return "%d days ago" % days


def _age_words(age):
    if age is None:
        return "-"
    hours = age / 3600.0
    if hours < 1:
        return "<1 h"
    if hours < 48:
        return "%d h" % hours
    return "%d d" % (hours / 24)


def _whole(value):
    number = _num(value)
    return "-" if number is None else "{:,}".format(int(round(number)))


def cells(row, now=None, goal=""):
    """(text, shade, sort key) for every column of one row. Shades are
    "good", "warn", "dim" or None."""
    now = time.time() if now is None else now
    far = _num(row.get("distance_ly"))
    intact = _num(row.get("intact"))
    seen_age = _ago(row.get("last_seen"), now)
    price_age = _ago(row.get("seen"), now)
    apart = _num(row.get("mine_sell_ly"))
    ls = _num(row.get("ls"))
    price, demand = _num(row.get("sell")), _num(row.get("demand"))
    cr, merits = _num(row.get("cr_hr")), _num(row.get("merits_hr"))
    others = ", ".join(row.get("contested_by") or []) or "-"
    stock = " / ".join(t for t in (row.get("amount"), row.get("density")) if t) or "-"
    out = [
        (row.get("system") or "-", None, None),
        ("%.1f Ly" % far if far is not None else "-", None, far if far is not None else 1e12),
        (row.get("power") or "-", None, None),
        (row.get("state") or "-", None, None),
        (others, "warn" if others != "-" else "dim", None),
        (row.get("body") or "-", None, None),
        (row.get("spot") or "-", None, None),
        (row.get("commodity") or "-", None, None),
        (str(row.get("rigs")) if row.get("rigs") is not None else "-", None,
         _num(row.get("rigs")) or 0),
        (stock, None, None),
        ("%d%%" % round(intact * 100) if intact is not None else "-",
         None if intact is None else "good" if intact >= 0.8 else "warn",
         intact if intact is not None else -1.0),
        (_days_words(seen_age), None, seen_age if seen_age is not None else 1e12),
        (row.get("found_by") or "-", None, None),
        (row.get("station") or "-", None, None),
        (str(row.get("pad") or "-"), None, FD.pad_rank(row.get("pad"))),
        ("%d Ls" % ls if ls is not None else "-", None, ls if ls is not None else 1e12),
        ("{:,} Cr".format(int(price)) if price is not None else "-", None,
         price if price is not None else -1.0),
        (_whole(demand), None, demand if demand is not None else -1.0),
        (_age_words(price_age), None if price_age is None or price_age < 86400 else "warn",
         price_age if price_age is not None else 1e12),
        ("same system" if apart == 0 else "%.1f Ly" % apart if apart is not None else "-",
         None, apart if apart is not None else 1e12),
        (_whole(cr), None if cr is not None else "dim", cr if cr is not None else -1.0),
        (_whole(merits), "good" if merits is not None else "dim",
         merits if merits is not None else -1.0),
    ]
    if str(goal or "").lower() == "acquire":
        out.insert(HEADERS.index("Sell station") + 1,
                   (row.get("sell_system") or "-", None, None))
    return out
