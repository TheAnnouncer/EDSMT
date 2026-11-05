"""The wing (1.10040): your wing in the game, one shared survey, and a rig
plan's pins split between the wing.

- Who is in your wing in the game, from the journal's own wing events. The
  wing link pairs you with a wingmate by itself only when each of you has
  the other in your wing: the server answers a commander with the ones they
  list who list them back, and the app shows nobody it does not list.
- What one beat of the wing link carries for the shared survey: the ground
  your scanner has swept on this body, the finds you have marked there and
  the pins of your own rig plan - each kept small, with a fixed most.
- A colour for each wingmate: the same one for a name every time, and no
  two alike in one wing.
- One plan for a deposit the whole wing follows, and its pins divided
  between the wingmates working that deposit, in turn by name, so each of
  you knows which are yours.

Pure logic: no toolkit, no network, no files.
"""
import zlib

import survey as SV

# The journal's wing events, as the game writes them. WingJoin lists the
# others already in the wing you joined (Others); WingAdd names one more
# (Name); WingLeave is you leaving. A new game, or the game shut, is out of
# any wing until the journal says otherwise.
JOIN, ADD, LEAVE = "WingJoin", "WingAdd", "WingLeave"
WING_EVENTS = (JOIN, ADD, LEAVE)
RESET_EVENTS = ("LoadGame", "Shutdown")
# A wing in the game is four commanders; the wing link holds eight. Never
# more names than the link could pair with.
MAX_MATES = 7
NAME_MAX = 40

# What one beat carries for the shared survey. The server holds the same
# limits and refuses a beat over them.
SWEEP_MAX = 120          # places swept, newest kept
SWEEP_GAP_M = 400.0      # no two closer than this - each one is a scanner disc
FINDS_MAX = 40           # finds marked, newest first
FINDS_REACH_M = 10000.0  # only finds this close to you
PINS_MAX = 12            # a rig plan's pins

# A wingmate within this of one of a plan's pins is working that deposit;
# a plan with a pin within PLAN_REACH_M of you is the one for where you are.
DEPOSIT_REACH_M = 1000.0
PLAN_REACH_M = 1500.0
# Two plans are for the same deposit when a pin of one is this close to a
# pin of the other: traced twice, a deposit's pins land within a spacing.
SAME_DEPOSIT_M = 150.0

# One colour each, none of them an instrument colour: violets, pinks and
# blues, which nothing else on the map or the scope is drawn in. The first
# is the colour the wing link has always used.
PALETTE = ("#c77dff", "#ff79c6", "#7f9cff", "#e9b8ff",
           "#ff4f8b", "#4f6bff", "#c252d6", "#9aa0c8")


def fold(name):
    """A commander's name as it is matched: no CMDR in front, single spaces,
    any case. "" for nothing."""
    text = " ".join(str(name or "").split())
    if text[:5].lower() == "cmdr ":
        text = text[5:].strip()
    return text.casefold()


def _name_of(entry):
    if isinstance(entry, dict):
        entry = entry.get("Name") or entry.get("name") or ""
    if entry is None:
        return ""
    return " ".join(str(entry).split())[:NAME_MAX]


def _unique(names):
    out, seen = [], set()
    for name in names:
        key = fold(name)
        if key and key not in seen:
            seen.add(key)
            out.append(name)
    return out[:MAX_MATES]


def roster_after(roster, event):
    """Who is in your wing after one journal event: the names as the game
    gives them, as a new list - the one passed in is never changed."""
    roster = list(roster or [])
    if not isinstance(event, dict):
        return roster
    name = event.get("event")
    if name == JOIN:
        others = event.get("Others")
        return _unique([_name_of(o) for o in others]) if isinstance(others, list) else []
    if name == ADD:
        return _unique(roster + [_name_of(event.get("Name"))])
    if name == LEAVE or name in RESET_EVENTS:
        return []
    return roster


def listed(mates, roster):
    """Only the wingmates whose name is in `roster` - an in-game link never
    shows a commander who is not in your own wing."""
    keys = {fold(name) for name in roster or []} - {""}
    return [mate for mate in mates or []
            if isinstance(mate, dict) and fold(mate.get("name")) in keys]


def colours(names):
    """{folded name: colour} for everyone in the wing, yourself included so
    every one of you works out the same answer. A name keeps its colour
    from one day to the next; two names that would share one are moved
    apart, in alphabetical order."""
    out, used = {}, set()
    size = len(PALETTE)
    for key in sorted({fold(n) for n in names or []} - {""}):
        start = zlib.crc32(key.encode("utf-8")) % size
        colour = PALETTE[start]
        if len(used) < size:
            for step in range(size):
                colour = PALETTE[(start + step) % size]
                if colour not in used:
                    break
        out[key] = colour
        used.add(colour)
    return out


# -- one beat ---------------------------------------------------------------

def sweep_for_beat(points, radius_m, gap_m=SWEEP_GAP_M, cap=SWEEP_MAX):
    """The ground swept on this body, for one beat: (lat, lon) places no two
    closer than gap_m along the way, the newest kept when there are more
    than cap, rounded to five places - about a metre. Oldest first."""
    points = list(points or [])
    if not points:
        return []
    kept = []
    for lat, lon in reversed(points):
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            continue
        if kept and radius_m and SV.surface_range_m(
                kept[-1][0], kept[-1][1], lat, lon, radius_m) < gap_m:
            continue
        kept.append((lat, lon))
        if len(kept) >= cap:
            break
    return [(round(lat, 5), round(lon, 5)) for lat, lon in reversed(kept)]


def finds_for_beat(rows, lat, lon, radius_m, reach_m=FINDS_REACH_M, cap=FINDS_MAX):
    """Your finds on this body within reach of you, newest first, for one
    beat: {"c": commodity, "lat", "lon", "d": worked out}."""
    out = []
    ordered = sorted((r for r in rows or [] if isinstance(r, dict)),
                     key=lambda r: str(r.get("recorded") or ""), reverse=True)
    for row in ordered:
        what = str(row.get("commodity") or "").strip()[:NAME_MAX]
        try:
            flat, flon = float(row["lat"]), float(row["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not what or not (-90.0 <= flat <= 90.0 and -180.0 <= flon <= 180.0):
            continue
        if lat is not None and lon is not None and radius_m and SV.surface_range_m(
                lat, lon, flat, flon, radius_m) > reach_m:
            continue
        out.append({"c": what, "lat": round(flat, 6), "lon": round(flon, 6),
                    "d": bool(SV.is_depleted(row.get("amount")))})
        if len(out) >= cap:
            break
    return out


def pins_for_beat(plan, system, body):
    """Your own rig plan's pins on this body, for one beat - never a layout
    somebody shared, and never the wing's plan coming back as yours."""
    if not isinstance(plan, dict) or plan.get("shared") or plan.get("wing"):
        return []
    if (str(plan.get("system") or "").lower(), str(plan.get("body") or "").lower()) != \
            (str(system or "").lower(), str(body or "").lower()):
        return []
    out = []
    for pin in plan.get("pins") or []:
        try:
            out.append({"n": int(pin["n"]), "lat": round(float(pin["lat"]), 6),
                        "lon": round(float(pin["lon"]), 6)})
        except (KeyError, TypeError, ValueError):
            continue
    return out[:PINS_MAX]


def find_key(find):
    """One find, as the same key every beat it comes in."""
    return (SV.fold(find.get("c")), round(float(find["lat"]), 5),
            round(float(find["lon"]), 5))


def new_finds(seen, finds):
    """(the finds not seen before, every key now seen). With nothing seen
    yet - the first beat from a wingmate - nothing is new: that is what
    they had, not what they have just marked."""
    keys, fresh = set(), []
    for find in finds or []:
        try:
            key = find_key(find)
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
        keys.add(key)
        if seen is not None and key not in seen:
            fresh.append(find)
    return fresh, keys


# -- the pins of one plan, split between the wing ---------------------------

def pick_plan(candidates):
    """The one plan a wing follows on a deposit, from [(name, pins)]: the one
    with the most pins, and between equals the first name in alphabetical
    order. (name, pins), or None."""
    good = [(name, pins) for name, pins in candidates or [] if pins]
    if not good:
        return None
    return min(good, key=lambda c: (-len(c[1]), fold(c[0])))


def split_pins(numbers, names):
    """{pin number: folded name}: the pins in plan order, cut into one run
    for each name in alphabetical order; any left over go one each to the
    first names. Everyone working it out gets the same answer."""
    crew = sorted({fold(n) for n in names or []} - {""})
    numbers = list(numbers or [])
    if not crew:
        return {}
    share, extra = divmod(len(numbers), len(crew))
    out, at = {}, 0
    for index, key in enumerate(crew):
        take = share + (1 if index < extra else 0)
        for number in numbers[at:at + take]:
            out[number] = key
        at += take
    return out


def crew_after(crew, near, present):
    """Who is working a deposit, as folded names: those already counted who
    are still on the link and on the body, and anyone newly near its pins.
    Somebody driving off to the ship and back keeps their pins."""
    return (({fold(n) for n in crew or []} | {fold(n) for n in near or []})
            & {fold(n) for n in present or []}) - {""}
