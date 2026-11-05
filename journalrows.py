"""What the journal itself says about a Rhino session (1.10040).

Six small readings, each from events the game writes, each a plain function:

  session_tonnes / hold_check   a session's tonnes are what crossed to the
                                ship (CargoTransfer, toship); the ship's own
                                hold, stated after the Rhino comes aboard,
                                checks them. Tonnes refined stay the live
                                count while the Rhino is out (#256).
  mining_stats / statistics_audit
                                the game's own mining statistics at each
                                login, against the sessions in between (#257).
  cargo_tick                    what a Cargo event says a hold has in it - the
                                Rhino's tonnes as they arrive (#266).
  ejected                       cargo thrown out, booked as tonnes lost (#267).
  trace_entry                   one line a time the game rewrites Status.json
                                or Cargo.json during a session, for the
                                support bundle, when trace mode is on (#273).
  sale_mark / after_read        the price at a station before each of your own
                                sales there, and at your next read of it (#274).

No files, no widgets, nothing remembered between calls.
"""

import hashlib
import json

# A session row's ship_hold: the ship's tonnes when the Rhino went out and
# after it came aboard, "before>after"; either side blank when not seen.
HOLD_SEP = ">"
# The Mining block of a Statistics event, and what each figure is called here.
STAT_FIELDS = (("Quantity_Mined", "mined"), ("Mining_Profits", "profits"),
               ("Materials_Collected", "materials"))
# Trace mode keeps only these. Each settles a question about what the game
# writes while a Rhino works; nothing else in the files is kept, so nothing
# personal - no position, no credits, no names - goes into a bundle.
TRACE_FIELDS = {"Status.json": ("Flags", "Flags2", "GuiFocus", "FireGroup", "Cargo"),
                "Cargo.json": ("Vessel", "Count")}
TRACE_ITEMS = 40               # commodities kept from one Cargo.json


def _whole(value):
    """A whole number out of the journal, or 0 - as the reader reads one."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _counts(packed):
    """"Iridium:40;Platinum:2" as {name: count}."""
    out = {}
    for part in str(packed or "").split(";"):
        name, _, count = part.rpartition(":")
        name = name.strip()
        if name and _whole(count) > 0:
            out[name] = out.get(name, 0) + _whole(count)
    return out


def _text(number):
    return "{:,}".format(int(number))


# -- #256: tonnes that crossed to the ship -------------------------------------

def session_tonnes(row):
    """(tonnes, "to ship" or "refined") for a session row: what crossed to the
    ship when anything did, otherwise what was refined."""
    row = row or {}
    moved = sum(_counts(row.get("transferred")).values())
    if moved > 0:
        return moved, "to ship"
    return sum(_counts(row.get("mined")).values()), "refined"


def hold_sides(value):
    """(before, after) of a ship_hold, each a whole number or None."""
    before, sep, after = str(value or "").partition(HOLD_SEP)
    def side(text):
        text = text.strip()
        return _whole(text) if text.lstrip("-").isdigit() else None
    return side(before), (side(after) if sep else None)


def hold_value(before=None, after=None):
    """A ship_hold from its two sides."""
    return "%s%s%s" % ("" if before is None else int(before), HOLD_SEP,
                       "" if after is None else int(after))


def hold_check(row):
    """Whether the ship's hold after the Rhino came aboard agrees with the
    tonnes moved across: True, False, or None while either end is unseen."""
    before, after = hold_sides((row or {}).get("ship_hold"))
    if before is None or after is None:
        return None
    return after - before == sum(_counts((row or {}).get("transferred")).values())


def hold_words(row):
    """(short, whole) words on the check, for the To ship cell. ("", "")
    when there is nothing to say."""
    agrees = hold_check(row)
    if agrees is None:
        return "", ""
    before, after = hold_sides(row.get("ship_hold"))
    if agrees:
        return ("hold agrees",
                "The ship's own hold after the Rhino came aboard (%s t, from %s t) "
                "agrees with the tonnes moved across." % (_text(after), _text(before)))
    return ("hold differs",
            "The ship's own hold after the Rhino came aboard went from %s t to %s t, "
            "which is not the tonnes moved across - something else came aboard or "
            "went, such as a sale or cargo thrown out." % (_text(before), _text(after)))


# -- #257: the game's own count at the next login ------------------------------

def mining_stats(event):
    """The Mining block of a Statistics event as {"when", "mined", "profits",
    "materials"}, or None."""
    if not isinstance(event, dict):
        return None
    block = event.get("Mining")
    if not isinstance(block, dict) or not any(k in block for k, _ in STAT_FIELDS):
        return None
    out = {"when": str(event.get("timestamp") or "")}
    for key, name in STAT_FIELDS:
        out[name] = _whole(block.get(key))
    return out


def statistics_audit(before, after, sessions, lost=None):
    """The game's own count between two logins against the books.

    `before` and `after` are mining_stats() of two logins; `sessions` the
    Rhino session rows started between them. The game counts every tonne
    mined and every mining sale - a ring as well as a Rhino - so a
    difference is not an error in itself. None when the two do not follow
    one another."""
    if not before or not after or str(after.get("when")) <= str(before.get("when")):
        return None
    game = {name: _whole(after.get(name)) - _whole(before.get(name)) for _key, name in STAT_FIELDS}
    if game["mined"] < 0 or game["profits"] < 0:
        return None
    rows = list(sessions or ())
    tonnes = sum(session_tonnes(row)[0] for row in rows)
    thrown = sum(sum(_counts(row.get("lost")).values()) for row in rows)
    credits = sum(_whole(row.get("credits")) for row in rows)
    booked = {"mined": tonnes, "lost": thrown, "profits": credits}
    return {"from": str(before.get("when")), "to": str(after.get("when")),
            "sessions": len(rows), "game": game, "booked": booked,
            "agrees": {"mined": game["mined"] == tonnes + thrown,
                       "profits": game["profits"] == credits}}


def audit_words(audit):
    """One plain line on an audit, or ""."""
    if not audit:
        return ""
    game, booked = audit["game"], audit["booked"]
    when = str(audit.get("from") or "")[:16].replace("T", " ")
    line = ("The game's own count from your login of %s to the next: %s t mined, %s Cr "
            "from mining. The %d session(s) here: %s t" % (
                when, _text(game["mined"]), _text(game["profits"]), audit["sessions"],
                _text(booked["mined"])))
    if booked["lost"]:
        line += " and %s t thrown out" % _text(booked["lost"])
    line += ", %s Cr." % _text(booked["profits"])
    if audit["agrees"]["mined"] and audit["agrees"]["profits"]:
        return line + " They agree."
    return line + " The game also counts mining outside a Rhino session."


# -- #266: the Rhino's tonnes as they arrive -----------------------------------

def cargo_tick(event):
    """(vessel, tonnes) a Cargo event states - vessel "Ship" or "SRV" - or
    None. Count is on every one; an Inventory, when there is one, adds up to
    it."""
    if not isinstance(event, dict):
        return None
    vessel = str(event.get("Vessel") or "Ship")
    count = event.get("Count")
    if count is None and isinstance(event.get("Inventory"), list):
        count = sum(_whole(item.get("Count")) for item in event["Inventory"]
                    if isinstance(item, dict))
    if count is None:
        return None
    return vessel, max(0, _whole(count))


def rhino_words(tonnes):
    """The live line for what is in the Rhino, or ""."""
    if tonnes is None:
        return ""
    return "In the Rhino now: %s t." % _text(max(0, _whole(tonnes)))


# -- #267: cargo thrown out ----------------------------------------------------

def ejected(event):
    """What an EjectCargo threw out: {"type", "localised", "count",
    "abandoned"}, or None for nothing."""
    if not isinstance(event, dict):
        return None
    count = _whole(event.get("Count"))
    kind = str(event.get("Type") or "").strip()
    if count <= 0 or not kind:
        return None
    return {"type": kind, "localised": str(event.get("Type_Localised") or ""),
            "count": count, "abandoned": bool(event.get("Abandoned"))}


def lost_words(row):
    """The line for tonnes thrown out in a session, or ""."""
    lost = _counts((row or {}).get("lost"))
    if not lost:
        return ""
    return "Thrown out: %s t (%s)" % (_text(sum(lost.values())), ", ".join(
        "%s %s" % (name, _text(count)) for name, count in sorted(lost.items())))


# -- #273: trace mode ----------------------------------------------------------

def trace_entry(name, raw, last=None, now=""):
    """One trace line for a file the game rewrote: (entry, digest). The
    entry is None when the file says what it said last time (`last` is that
    digest) or cannot be read. Only TRACE_FIELDS are kept."""
    keep = TRACE_FIELDS.get(name)
    if keep is None:
        return None, last
    try:
        data = json.loads(str(raw or ""))
    except ValueError:
        return None, last
    if not isinstance(data, dict):
        return None, last
    fields = {key: data[key] for key in keep if key in data}
    if name == "Cargo.json" and isinstance(data.get("Inventory"), list):
        fields["Inventory"] = [{"Name": str(item.get("Name") or ""), "Count": _whole(item.get("Count"))}
                               for item in data["Inventory"][:TRACE_ITEMS] if isinstance(item, dict)]
    digest = hashlib.sha1(json.dumps(fields, sort_keys=True).encode("utf-8")).hexdigest()
    if digest == last:
        return None, last
    return {"at": str(now or ""), "file": name, "timestamp": str(data.get("timestamp") or ""),
            "fields": fields}, digest


# -- #274: the price before and after your own sale ----------------------------

def sale_mark(station_key, system, station, commodity, sold_at, when, before=None):
    """A record of one of your own sales, to be told the station's next price.
    `before` is the last price known there for it: {"sell", "seen"} or None."""
    before = before or {}
    return {"key": str(station_key), "system": str(system or ""), "station": str(station or ""),
            "commodity": str(commodity or ""), "sold_at": _whole(sold_at), "when": str(when or ""),
            "before": _whole(before.get("sell")) or None, "before_seen": str(before.get("seen") or ""),
            "after": None, "after_seen": ""}


def after_read(marks, station_key, prices, when):
    """A market read at a station: each sale there still waiting is given the
    price the read shows for what was sold. `prices` maps a commodity's
    folded name to its sell price, and each mark carries its own commodity
    folded the same way ("folded"). How many marks were told."""
    told = 0
    for mark in marks or ():
        if mark.get("key") != station_key or mark.get("after") is not None:
            continue
        if not str(when or "") > str(mark.get("when") or ""):
            continue
        price = prices.get(mark.get("folded") or mark.get("commodity"))
        if price:
            mark["after"], mark["after_seen"] = _whole(price), str(when)
            told += 1
    return told


def price_change(mark):
    """How the price moved from your sale to your next read, in percent, or
    None while there is no next read."""
    sold = _whole((mark or {}).get("sold_at"))
    after = (mark or {}).get("after")
    if not sold or after is None:
        return None
    return 100.0 * (_whole(after) - sold) / sold


def mark_words(mark):
    """(short, whole) words on one sale's prices."""
    change = price_change(mark)
    name = mark.get("commodity") or "it"
    whole = "%s sold at %s Cr" % (name, _text(mark.get("sold_at") or 0))
    if mark.get("before"):
        whole += " (the board said %s Cr before the sale)" % _text(mark["before"])
    if change is None:
        return "", whole + "; no read of this market since."
    whole += "; %s Cr at your next read, %s (%+.0f%%)." % (
        _text(mark["after"]), str(mark.get("after_seen"))[:16].replace("T", " "), change)
    return "next read %+.0f%%" % change, whole
