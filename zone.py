"""Which mining location you are at, without targeting it (1.10038).

Asked in these words: "when I select the signal site it shows me what's in
that zone - why can't you auto detect this when they are in atmosphere".

The game names a location only while the commander has it targeted, and
tells nobody where a location is or what it holds. What is known about one
comes from finds: the commander's own logged centres and marked deposits,
and the finds other commanders have shared on the body. So "which location
am I in" is answered from those - the nearest known one within reach - and
"what is in it" from the finds filed under its number.

Pure logic, no toolkit. The app hands in what it has and gets back the
location to show and the words to say about it; every rule is a plain
function that can be checked on its own.
"""
import datetime
import time

import survey as SV

# A known location this close is the one you are at, on the ground or low
# over it. The same reach as being "at" a signal on the map.
ZONE_APPROACH_M = 5000.0
# Above this height you are still coming down - gliding in, or in orbital
# cruise just above the atmosphere - and want to know what is below, so the
# net is wider.
ZONE_GLIDE_ALT_M = 2000.0
ZONE_GLIDE_M = 15000.0
# Your own logged centre this close wins outright over anything shared: it
# is where you stood and pressed the key. Beyond it the nearest known
# location wins, yours or theirs. The app's SAME_SIGNAL_M is this figure.
ZONE_OWN_M = 1500.0
# How many commodities the one line and the overlay name before "+N more".
TOP_COMMODITIES = 3


def reach_m(altitude_m):
    """How far a known location may be and still count as here."""
    try:
        high = altitude_m is not None and float(altitude_m) > ZONE_GLIDE_ALT_M
    except (TypeError, ValueError):
        high = False
    return ZONE_GLIDE_M if high else ZONE_APPROACH_M


def _apart(row, lat, lon, radius_m):
    """Metres from (lat, lon) to a row's position, or None without one."""
    try:
        return SV.surface_range_m(float(lat), float(lon), float(row["lat"]),
                                  float(row["lon"]), float(radius_m))
    except (TypeError, ValueError, KeyError):
        return None


def _signal_of(row):
    return str((row or {}).get("location") or "").strip()


def zone_here(own_locations, shared_finds, lat, lon, radius_m, altitude_m=None):
    """The mining location you are in, or None.

    own_locations  your logged centres on this body (Survey location rows)
    shared_finds   other commanders' finds on it, as the app files them:
                   location (the number), lat, lon, commodity, rigs, amount,
                   density, cmdr, when
    altitude_m     metres above the ground, or None when the game gives none

    Your own centre within ZONE_OWN_M wins. Otherwise the nearest known
    location within reach - yours by its centre, theirs by their nearest
    find - and None when nothing known is that close. A centre or a find
    with no position cannot be stood in and is passed over.

    Returns {"signal", "source" ("own" or "shared"), "metres", "reach_m"}.
    """
    if lat is None or lon is None or not radius_m:
        return None
    reach = reach_m(altitude_m)
    own = SV.nearest_signal(own_locations, lat, lon, radius_m, ZONE_OWN_M)
    if own is not None:
        return {"signal": _signal_of(own), "source": "own",
                "metres": _apart(own, lat, lon, radius_m), "reach_m": reach}
    best = None
    for source, rows in (("own", own_locations), ("shared", shared_finds)):
        for row in rows or []:
            signal = _signal_of(row)
            if not signal:
                continue
            apart = _apart(row, lat, lon, radius_m)
            if apart is None or apart > reach:
                continue
            if best is None or apart < best["metres"]:
                best = {"signal": signal, "source": source, "metres": apart,
                        "reach_m": reach}
    return best


def finds_in(signal, finds):
    """The finds filed under one location number."""
    wanted = str(signal).strip()
    return [row for row in finds or [] if _signal_of(row) == wanted]


def others(shared_finds, own_deposits, radius_m, same_m=40.0):
    """Shared finds that are not your own come back from the server: a
    shared find of the same commodity within `same_m` of one of yours is
    yours, and is left out so it is not listed twice."""
    out = []
    for theirs in shared_finds or []:
        duplicate = False
        for mine in own_deposits or []:
            if SV.fold(mine.get("commodity")) != SV.fold(theirs.get("commodity")):
                continue
            try:
                apart = SV.surface_range_m(float(mine["lat"]), float(mine["lon"]),
                                           float(theirs["lat"]), float(theirs["lon"]),
                                           float(radius_m or 1e6))
            except (TypeError, ValueError, KeyError):
                continue
            if apart <= same_m:
                duplicate = True
                break
        if not duplicate:
            out.append(theirs)
    return out


def _rigs(row):
    try:
        return int(float(str(row.get("rigs") or "").strip() or 0))
    except (TypeError, ValueError):
        return 0


def summary(finds, limit=TOP_COMMODITIES):
    """The commodities in a location, most rigs first: "Iridium 4R,
    Sapphire 2R +2 more". Each commodity once, with the most rigs anyone
    has had down on it; one worked out everywhere it was found says so."""
    best = {}
    for row in finds or []:
        name = str(row.get("commodity") or "").strip()
        if not name:
            continue
        key = SV.fold(name)
        if key not in best:
            best[key] = {"name": name, "rigs": 0, "worked": True, "seen": len(best)}
        best[key]["rigs"] = max(best[key]["rigs"], _rigs(row))
        if not SV.is_depleted(row.get("amount")):
            best[key]["worked"] = False
    ranked = sorted(best.values(), key=lambda item: (-item["rigs"], item["seen"]))
    parts = []
    for item in ranked[:limit]:
        text = item["name"] + (" %dR" % item["rigs"] if item["rigs"] else "")
        if item["worked"]:
            text += " (worked out)"
        parts.append(text)
    text = ", ".join(parts)
    if len(ranked) > limit:
        text += " +%d more" % (len(ranked) - limit)
    return text


def _epoch(stamp):
    """Seconds for a server or journal timestamp, or 0."""
    text = str(stamp or "").strip()
    if not text:
        return 0
    found = SV._epoch(text)
    if found:
        return found
    try:
        return datetime.datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0


def _days_words(then, now=None):
    now = time.time() if now is None else now
    days = int(max(0.0, (now - then) / 86400.0))
    return "today" if days == 0 else "yesterday" if days == 1 else "%d days ago" % days


def age_words(stamp, now=None):
    """"today", "yesterday", "9 days ago" - or "" for no usable time."""
    then = _epoch(stamp)
    return _days_words(then, now) if then else ""


def _cmdr(name):
    name = str(name or "").strip()
    if not name:
        return ""
    return name if name.lower().startswith("cmdr") else "CMDR " + name


def shared_note(finds, now=None, verb="shared by"):
    """"3 finds shared by CMDR X and 1 other, 9 days ago" - the count, who
    (the commander with most of them), and when the newest was seen."""
    finds = list(finds or [])
    count = len(finds)
    text = "%d find%s" % (count, "" if count == 1 else "s")
    names = {}
    for row in finds:
        who = str(row.get("cmdr") or "").strip()
        if who:
            names[who.lower()] = names.get(who.lower(), 0) + 1
    if names:
        lead = max(names, key=lambda key: (names[key], -list(names).index(key)))
        shown = next(str(row.get("cmdr")).strip() for row in finds
                     if str(row.get("cmdr") or "").strip().lower() == lead)
        text += " %s %s" % (verb, _cmdr(shown))
        extra = len(names) - 1
        if extra:
            text += " and %d other%s" % (extra, "" if extra == 1 else "s")
    elif verb.startswith("shared"):
        text += " shared"
    newest = max((_epoch(row.get("when")) for row in finds), default=0)
    if newest:
        text += ", " + _days_words(newest, now)
    return text


def zone_line(zone, own_deposits, shared_finds, now=None):
    """The one line said on entering a location.

    "Mining location 7 - Iridium 4R, Sapphire 2R (3 finds shared by CMDR X,
    9 days ago)" for a shared one, "Mining location 7 - yours: Platinum 4R"
    for your own, and both halves when both have something there.
    """
    signal = str((zone or {}).get("signal") or "").strip()
    head = "Mining location %s - " % signal
    mine = list(own_deposits or [])
    theirs = list(shared_finds or [])
    if mine and theirs:
        return head + "yours: %s; shared: %s (%s)" % (
            summary(mine), summary(theirs), shared_note(theirs, now, verb="by"))
    if theirs:
        return head + "%s (%s)" % (summary(theirs), shared_note(theirs, now))
    if mine:
        return head + "yours: " + summary(mine)
    return head + "yours, nothing marked in it yet"


def nothing_line(reach, count):
    """The dim line when nothing known is within reach: how far was looked,
    and what the game's own signal list says about this body."""
    try:
        km = float(reach) / 1000.0
    except (TypeError, ValueError):
        km = ZONE_APPROACH_M / 1000.0
    far = ("%d" % km) if km == int(km) else ("%.1f" % km)
    try:
        count = int(count or 0)
    except (TypeError, ValueError):
        count = 0
    head = "No finds shared within %s km - the game's signal list " % far
    if count <= 0:
        return head + "has no mining locations for this body yet"
    return head + "says %d mining location%s on this body" % (count, "" if count == 1 else "s")


def status_card(signal, own_deposits, shared_finds):
    """What the overlay's STATUS box shows while you are in a location:
    the number and the top finds, yours first."""
    rows = list(own_deposits or []) + list(shared_finds or [])
    return {"signal": str(signal).strip(), "summary": summary(rows)}
