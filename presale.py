"""What selling the mined hold here would pay, said at the dock (1.10036, #260).

The game writes Market.json when the commodities screen opens, and the
board in it is what the sale will pay - to the credit, in every session
checked. So the moment a market is read with mined cargo aboard, the app
can say what selling here comes to: the credits, the crew's cut (learnt
from this commander's own past sales, never assumed), and the merits when
selling here counts for the pledged Power. Pure logic: no Tk, no files.
"""
import survey as SV

# Too few sales with a wage in them and the share is not a figure yet.
WAGE_MIN_SALES = 2


def _whole(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def wage_share(ledger_sessions, book_rows):
    """The crew's share of what this commander's sales paid, as a fraction,
    or None until WAGE_MIN_SALES sessions carry a wage. `ledger_sessions`
    is the session ledger's {id: {"wages", "wage_events"}}; `book_rows` the
    sessions the books keep, for what each one earned."""
    earned = {str(r.get("id")): float(SV.earned(r) or 0) for r in book_rows or ()}
    wages = credits = 0.0
    count = 0
    for sid, have in dict(ledger_sessions or {}).items():
        if not isinstance(have, dict) or not _whole(have.get("wage_events")):
            continue
        made = earned.get(str(sid), 0.0)
        if made <= 0:
            continue
        wages += _whole(have.get("wages"))
        credits += made
        count += 1
    if count < WAGE_MIN_SALES or credits <= 0:
        return None
    return wages / credits


def merits_count(pledged, here):
    """Whether a merit figure should be shown for selling in this system
    (#261): pledged, and the system is the pledged Power's own. Returns
    (show, note) - note names a state nobody has measured yet."""
    pledged = str(pledged or "").strip()
    here = dict(here or {})
    if not pledged:
        return False, ""
    if SV.fold(here.get("ControllingPower")) != SV.fold(pledged):
        return False, ""
    state = str(here.get("PowerplayState") or "")
    if SV.fold(state) in ("fortified", "stronghold"):
        return True, "%s - merit rate here not yet measured" % state
    return True, ""


def quote(hold, market, merit_rate=None, wages=None, show_merits=False):
    """What the mined hold fetches on this board.

    `hold` is {commodity: tonnes} of mined goods aboard; `market` the
    parsed Market.json (items with sell and demand). Demand caps what one
    sale takes. Returns None when nothing aboard is bought here, else:

      {"station", "system", "tonnes", "of", "credits", "parts": [...],
       "unsold": [names], "wages", "net", "merits"}
    """
    if not isinstance(market, dict):
        return None
    board = {}
    for item in market.get("items") or ():
        if isinstance(item, dict) and _whole(item.get("sell")) > 0:
            board[SV.fold(SV.canonical(item.get("commodity") or ""))] = item
    parts, unsold, held = [], [], 0
    for name, count in sorted(dict(hold or {}).items()):
        count = _whole(count)
        if count <= 0:
            continue
        held += count
        item = board.get(SV.fold(SV.canonical(name)))
        if item is None:
            unsold.append(SV.canonical(name) or name)
            continue
        demand = item.get("demand")
        take = count if demand in (None, "") else min(count, max(0, _whole(demand)))
        if take <= 0:
            unsold.append(SV.canonical(name) or name)
            continue
        sell = _whole(item.get("sell"))
        parts.append({"commodity": SV.canonical(name) or name, "tonnes": take,
                      "aboard": count, "sell": sell, "value": sell * take})
    if not parts:
        return None
    credits = sum(p["value"] for p in parts)
    cut = int(round(credits * wages)) if wages else None
    merits = None
    if show_merits and merit_rate:
        merits = int(round(credits * merit_rate))
    return {"station": market.get("station"), "system": market.get("system"),
            "tonnes": sum(p["tonnes"] for p in parts), "of": held,
            "credits": credits, "parts": sorted(parts, key=lambda p: -p["value"]),
            "unsold": unsold, "wages": cut,
            "net": credits - cut if cut is not None else None, "merits": merits}


def money(value):
    """12,345,678 as "12.3 M", 845,000 as "845 k"."""
    value = float(value or 0)
    if abs(value) >= 1e9:
        return "%.2f bn" % (value / 1e9)
    if abs(value) >= 1e6:
        return "%.1f M" % (value / 1e6)
    if abs(value) >= 1e4:
        return "%d k" % round(value / 1e3)
    return "{:,}".format(int(round(value)))


def words(found, note=""):
    """The line for the status bar and the flash over the game."""
    if not found:
        return ""
    line = "Selling here: %d t for %s cr" % (found["tonnes"], money(found["credits"]))
    if found["tonnes"] < found["of"]:
        line += " (%d of %d t aboard)" % (found["tonnes"], found["of"])
    if found.get("wages") is not None:
        line += ", crew ~%s, net ~%s" % (money(found["wages"]), money(found["net"]))
    if found.get("merits") is not None:
        line += ", ~{:,} merits".format(found["merits"])
        if note:
            line += " (%s)" % note
    if found.get("unsold"):
        line += ". Not bought here: %s" % ", ".join(found["unsold"])
    return line + "."
