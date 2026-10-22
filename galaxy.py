"""Mining bodies near the commander, galaxy-wide (1.10036, #200, #133).

What the Find window's "Mining bodies" table shows, worked out from the
community server's answer. The server hears every FSS scan and DSS map
that commanders' tools publish to the game's public data network (EDDN)
and keeps the bodies that carry mining locations; it adds the kind of
ground, how often a commodity has turned up on that kind of ground in
what commanders shared - with the size of that sample - and how many
sites are already on the community map there.

Pure logic: no Tk, no network. Every cell is (text, colour key, sort key);
the colour keys are "" (plain), "good", "warn" and "dim".
"""
import datetime as dt
import json
import math
import time

HEADERS = ("Body", "System", "Distance", "Locations", "DSS mapped", "Ground",
           "Odds (with n)", "Mapped by commanders", "Seen")

# The Find window's own tag for this search; the app routes on it.
TAG = "mining-bodies"

# A share resting on fewer sites than this is shown, but in amber: four
# sites are a hint, not a pattern.
SMALL_SAMPLE = 5

# The furthest out the server looks, and how far when not told.
MOST_LY = 1000
DEFAULT_LY = 100

SOURCE = "the game's public data network (EDDN)"


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _whole(value):
    number = _number(value)
    return int(number) if number is not None else 0


def _epoch(stamp):
    """Seconds since 1970 from the server's ISO time, or None."""
    text = str(stamp or "").strip()
    if not text:
        return None
    try:
        when = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return when.timestamp()


def _plural(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


def parse(message):
    """The server's answer as a dict, or None when it is not one."""
    if isinstance(message, dict):
        return message
    try:
        data = json.loads(message)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def rows(answer):
    """The body rows of an answer, nearest first as the server sent them."""
    answer = answer if isinstance(answer, dict) else {}
    return [r for r in answer.get("bodies") or () if isinstance(r, dict)]


def odds_cell(odds):
    """How often the commodity turned up on this kind of ground, and in how
    many sites: "75% (9 of 12)". With no commodity asked, the commonest
    one there is named in front."""
    if not isinstance(odds, dict):
        return ("-", "dim", None)
    share = _number(odds.get("share"))
    of = _whole(odds.get("of"))
    if share is None or of <= 0:
        return ("no sample yet", "dim", None)
    text = "%d%% (%d of %d)" % (round(share * 100), _whole(odds.get("sites")), of)
    if odds.get("commonest") and odds.get("commodity"):
        text = "%s %s" % (odds["commodity"], text)
    return (text, "warn" if of < SMALL_SAMPLE else "good", share)


def seen_cell(stamp, now=None):
    at = _epoch(stamp)
    if at is None:
        return ("-", "dim", None)
    age = max(0.0, (time.time() if now is None else now) - at)
    days = int(age // 86400)
    text = "today" if days < 1 else "yesterday" if days < 2 else "%d days ago" % days
    return (text, "" if days <= 30 else "dim", age)


def mapped_cell(row):
    sites = _whole(row.get("mapped"))
    if sites <= 0:
        return ("none yet", "good", 0)
    finds = _whole(row.get("mapped_deposits"))
    text = _plural(sites, "site") + (", " + _plural(finds, "find") if finds else "")
    return (text, "", sites)


def cells(row, now=None):
    """One body as a row of cells, in HEADERS order."""
    row = row if isinstance(row, dict) else {}
    body = str(row.get("body") or "")
    system = str(row.get("system") or "")
    far = _number(row.get("distance_ly"))
    count = _number(row.get("locations"))
    ground = " ".join(str(row.get("ground") or "").split())
    return [
        (body, "", body.lower()),
        (system, "", system.lower()),
        ("%.1f Ly" % far, "", far) if far is not None else ("-", "dim", None),
        ("%d" % count, "", int(count)) if count is not None else ("-", "dim", None),
        ("yes", "good", 1) if row.get("dss") is True else ("FSS scan only", "", 0),
        (ground, "", ground.lower()) if ground else ("-", "dim", None),
        odds_cell(row.get("odds")),
        mapped_cell(row),
        seen_cell(row.get("seen"), now),
    ]


def headline(answer):
    """The sentence over the table: how many bodies, how far out, how many a
    DSS map counted, how many nobody has mapped yet - or why there are none."""
    if not isinstance(answer, dict):
        return "The community server sent something unreadable."
    if answer.get("missing"):
        return ("Mining bodies from %s are not on the community server yet - "
                "they arrive with its next update." % SOURCE)
    if answer.get("unplaced"):
        return ("No position is known for %s yet - try again once the game has "
                "said where you are." % " ".join(str(answer["unplaced"]).split()))
    found = rows(answer)
    within = _number(answer.get("within_ly")) or DEFAULT_LY
    if not found:
        return ("Nobody has reported a body with mining locations within %d Ly yet."
                % round(within))
    centre = str((answer.get("centre") or {}).get("system") or "").strip()
    dss = sum(1 for r in found if r.get("dss") is True)
    fresh = sum(1 for r in found if _whole(r.get("mapped")) <= 0)
    count = len(found)
    lead = ("the nearest %d" % count) if answer.get("more") else "%d" % count
    words = "%s %s with mining locations within %d Ly%s: %d DSS-mapped, %d with " \
            "nothing on the community map yet." % (
                lead, "body" if count == 1 else "bodies", round(within),
                (" of " + centre) if centre else "", dss, fresh)
    words = words[:1].upper() + words[1:]
    commodity = str(answer.get("commodity") or "").strip()
    odds = ("Odds are for %s" % commodity) if commodity else \
        "Odds are for the commonest commodity on each kind of ground"
    return ("%s %s, from what commanders shared - where to prospect, not what a "
            "body holds. Bodies from %s." % (words, odds, SOURCE))


def tone(answer):
    """The headline's colour key: "good" with bodies to show, else "warn"."""
    if isinstance(answer, dict) and not answer.get("missing") and rows(answer):
        return "good"
    return "warn"
