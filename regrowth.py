"""Depleted deposits and when to look at them again (1.10035).

How fast a deposit grows back is not published, and measurements differ from
ground to ground, so nothing here assumes a number it can act on silently.
What it keeps is a short, honest record on each deposit:

    depleted_at   when it was FIRST marked depleted (UTC)
    rechecks      each time you went back, found it still empty and said so

and a few rules over those two dates:

  * a deposit marked depleted stays depleted for HOLD_DAYS (14);
  * after that its card says "depleted 14 days - recheck due";
  * if you look, and mark it still depleted with nothing refined there since,
    the FIRST date is kept, the look is added to the list, and the card says
    "depleted 15 days - recheck in 7 days" - the mark comes off
    RECHECK_DAYS (7) after that look;
  * tonnes refined at it since it was marked mean it has grown back, so the
    next time it is worked out that is a new depletion, with a new first date.

No window code in here: everything is a function of a deposit row and a
clock, so the whole timeline can be checked day by day.
"""

import calendar
import math
import re
import time

import survey as SV

HOLD_DAYS = 14
RECHECK_DAYS = 7
DAY = 86400.0

# How close counts as having arrived at a deposit, for "it is due a look".
ARRIVED_M = 100.0

_NOTE_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{2}):(\d{2}))?")


def stamp(epoch):
    """Seconds as the UTC stamp the records use."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def when_of(text):
    """A stored date as seconds, or None. UTC stamps, plain dates, and the
    local dd/mm/yyyy a note line carries."""
    text = str(text or "").strip()
    if not text:
        return None
    found = SV._epoch(text)
    if found:
        return float(found)
    try:
        return float(calendar.timegm(time.strptime(text[:10], "%Y-%m-%d")))
    except (ValueError, OverflowError):
        return None


def depleted(deposit):
    """True while the deposit is marked depleted."""
    return SV.is_depleted((deposit or {}).get("amount"))


def first_date(deposit):
    """When it was first marked depleted, as seconds, or None.

    The stored first date where there is one; otherwise the last "Mined"
    line in its notes, which is what every deposit worked out before this
    version carries."""
    stored = when_of((deposit or {}).get("depleted_at"))
    if stored:
        return stored
    found = None
    for line in str((deposit or {}).get("notes") or "").splitlines():
        if line.strip().lower().startswith("mined"):
            match = _NOTE_DATE.search(line)
            if match:
                found = match
    if not found:
        return None
    day, month, year, hour, minute = found.groups()
    try:
        return float(time.mktime((int(year), int(month), int(day),
                                  int(hour or 12), int(minute or 0), 0, 0, 0, -1)))
    except (OverflowError, ValueError):
        return None


def looks(deposit):
    """Each look that found it still depleted, oldest first, as seconds."""
    out = []
    for part in str((deposit or {}).get("rechecks") or "").split(";"):
        found = when_of(part)
        if found:
            out.append(found)
    return sorted(out)


def refined_since(deposit):
    """True if its own commodity has been refined at it since it was marked.

    Its own commodity only: a by-product refined at a neighbour is credited
    to the nearest deposit, and that must not make an empty one look grown."""
    own, _others = SV.own_tonnes(deposit or {})
    return own > 0


def standing(deposit, now=None):
    """Where a deposit is in its timeline.

    state is one of
      intact   - not marked depleted
      unknown  - depleted, but nothing says since when
      fresh    - depleted less than HOLD_DAYS ago
      look     - HOLD_DAYS or more, not looked at: "recheck due"
      waiting  - looked at, still depleted, the mark comes off later
      expired  - looked at, and RECHECK_DAYS have passed: the mark is due off
      regrown  - tonnes refined at it since it was marked

    `due` is True when a look is what it needs. `text` is the card's line.
    """
    now = time.time() if now is None else now
    out = {"state": "intact", "age_days": None, "due": False, "text": "",
           "off_in_days": None, "look_age_days": None, "looks": 0}
    if not depleted(deposit):
        return out
    first = first_date(deposit)
    if first is None:
        out.update(state="unknown", text="depleted - since when is not known")
        return out
    age = max(0, int((now - first) // DAY))
    out["age_days"] = age
    seen = [at for at in looks(deposit) if at >= first]
    out["looks"] = len(seen)
    if refined_since(deposit):
        out.update(state="regrown", text="depleted %d d ago, but tonnes have been "
                   "refined here since - it has grown back" % age)
        return out
    if seen:
        last = seen[-1]
        at = max(0, int((last - first) // DAY))
        out["look_age_days"] = at
        left = last + RECHECK_DAYS * DAY - now
        if left <= 0:
            out.update(state="expired", text="confirmed depleted at %d days; the mark "
                       "is due to come off" % at)
        else:
            days = int(math.ceil(left / DAY))
            out.update(state="waiting", off_in_days=days,
                       text="depleted %d days - recheck in %d days"
                       % (at, days))
        return out
    if age >= HOLD_DAYS:
        out.update(state="look", due=True,
                   text="depleted %d days - recheck due" % age)
        return out
    out.update(state="fresh",
               text="depleted today" if age == 0 else "depleted %d d ago" % age)
    return out


def card_lines(deposit, now=None):
    """The lines a deposit's card adds, [] for one that is not depleted."""
    info = standing(deposit, now)
    return [info["text"]] if info["text"] else []


def mark_changes(deposit, now=None):
    """The fields to write when a deposit is marked depleted, and what that was.

    Returns (changes, kind). kind is
      "new"     - first depletion, or tonnes were refined since the last one:
                  the first date is now and the looks start again;
      "recheck" - it was due a look and is still empty: the first date is
                  kept and this look is added;
      "same"    - marked again before it was due a look, or inside the week
                  after a look: nothing moves.
    """
    now = time.time() if now is None else now
    first = first_date(deposit) if depleted(deposit) else None
    if first is not None and not refined_since(deposit):
        seen = [at for at in looks(deposit) if at >= first]
        age = int((now - first) // DAY)
        # A look already made and still inside its week is not a new look:
        # marking it again must not push the mark's expiry further out.
        due = (seen[-1] + RECHECK_DAYS * DAY <= now) if seen else age >= HOLD_DAYS
        if due:
            seen.append(now)
        return ({"amount": "Depleted", "depleted_at": stamp(first),
                 "rechecks": ";".join(stamp(at) for at in seen)},
                "recheck" if due else "same")
    return {"amount": "Depleted", "depleted_at": stamp(now), "rechecks": ""}, "new"


def still_depleted_changes(deposit, now=None):
    """What the card's "still depleted" button writes: a look, with its note."""
    now = time.time() if now is None else now
    changes, kind = mark_changes(deposit, now)
    if kind == "recheck":
        first = first_date(deposit)
        age = int((now - first) // DAY) if first else 0
        changes["notes"] = SV.stamp_note(
            (deposit or {}).get("notes"),
            "Rechecked: still depleted at %d days" % age)
    return changes, kind


def set_active_changes(deposit, now=None):
    """Regrown: the depleted mark off, the amount unread (blank) until it
    is read again, the dates cleared. The note keeps what it was."""
    info = standing(deposit, now)
    was = "" if info["age_days"] is None else " (depleted %d d)" % info["age_days"]
    return {"amount": "", "depleted_at": "", "rechecks": "",
            "notes": SV.stamp_note((deposit or {}).get("notes"),
                                   "Regrown" + was)}


def expiry_changes(deposit, now=None):
    """The fields to write when a looked-at deposit's mark comes off, or None.

    The amount goes back to unread. The first date and the looks stay, so
    the history is not lost."""
    info = standing(deposit, now)
    if info["state"] != "expired":
        return None
    return {"amount": "",
            "notes": SV.stamp_note((deposit or {}).get("notes"),
                                   "Depleted mark came off after the look at "
                                   "%d d" % info["look_age_days"])}


def expire_marks(store, now=None):
    """Take the mark off every deposit that is due it. How many came off."""
    count = 0
    for row in list(getattr(store, "deposits", None) or []):
        changes = expiry_changes(row, now)
        if changes:
            row.update(changes)
            count += 1
    if count:
        store.save_deposits()
    return count


def due_near(store, system, body, lat, lon, radius_m, now=None,
             within_m=ARRIVED_M):
    """The deposits on this body that need a look and are within reach of
    (lat, lon), nearest first, as (deposit, metres)."""
    try:
        lat, lon, radius = float(lat), float(lon), float(radius_m)
    except (TypeError, ValueError):
        return []
    if not radius:
        return []
    out = []
    for row in store.at(system, body):
        if not standing(row, now)["due"]:
            continue
        try:
            metres = SV.surface_range_m(lat, lon, float(row["lat"]),
                                        float(row["lon"]), radius)
        except (KeyError, TypeError, ValueError):
            continue
        if metres <= within_m:
            out.append((row, metres))
    return sorted(out, key=lambda pair: pair[1])
