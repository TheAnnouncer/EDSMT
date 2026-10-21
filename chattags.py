"""Survey tags typed in the game's own chat, and deposits marked from range.

Two things that share one need: turning a few typed words into a deposit.

Chat tags (#127, #244). The game writes every message the commander sends
to the journal as a SendText event - To (the channel), Message, and Sent
(false when the game did not send it). A message that starts with EDSMT's
own prefix ("!rr" unless changed in Settings) is read as a command:

    !rr alexandrite h/m 4     mark Alexandrite here, High amount, Medium density, 4 rigs
    !rr 135 1.2km alex       mark Alexandrite 1.2 km away on a bearing of 135
    !rr rig down 3             rig 3 down here ("rig down" alone: the next free one)
    !rr rig up 3               rig 3 up ("rigs up": every rig)
    !rr centre                 move the survey centre here
    !rr undo                   take back the last deposit marked

Only the commander's own messages are ever read (SendText, never the
messages other commanders send), only when the switch in Settings is on,
and only while they are fresh - the journal is read from the top when EDSMT
starts, and a command typed yesterday must not run again today.

From range (#197). A deposit seen from the Rhino can be marked where it is
rather than where the Rhino is: a bearing and a distance from here, and the
point is worked out across the body's own curve. It is marked "placed from
range" in its notes, kept on this machine, and UPDATE pressed at the spot
puts it exactly where it is and sends it on like any other find.
"""
import re
import time

import survey as SV

# What a command starts with, unless Settings says otherwise. Short, easy to
# type in the chat box, and unlike anything a commander says to another.
DEFAULT_PREFIX = "!rr"
# A SendText this much older than now was typed before EDSMT was looking -
# it is history being read back, not a command.
CHAT_FRESH_S = 120.0
# The furthest a deposit can be marked from range. Further than this it is
# a guess, not a reading - drive closer.
MAX_RANGE_M = 10000.0
# How far UPDATE looks for a deposit placed from range. A bearing judged by
# eye and a distance read off the scanner can be a few hundred metres out at
# two or three kilometres, so this is wider than the usual "standing on it".
REFINE_M = 1000.0
# Closer than this, a second deposit of the same commodity is the first one
# again (the app's own "standing on it" distance).
SAME_SPOT_M = 100.0

RANGED_NOTE = "Placed from range"
REFINED_NOTE = "Refined at the spot"

_AMOUNT_WORDS = {"d": "Depleted", "l": "Low", "m": "Medium", "h": "High"}
_DENSITY_WORDS = {"l": "Low", "m": "Medium", "h": "High"}


# ---------------------------------------------------------------------------
# Bearings and distances as a person types them
# ---------------------------------------------------------------------------

def parse_bearing(text):
    """A compass bearing in degrees, 0 to under 360, or None.

    "135", "135.5", "135deg" and "135°" all work; 360 is north again.
    A negative number, or one past 360, is not a bearing anybody meant."""
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        value = float(text)
    else:
        raw = str(text if text is not None else "").strip().lower()
        for unit in ("degrees", "degree", "deg", "°"):
            if raw.endswith(unit):
                raw = raw[:-len(unit)].strip()
                break
        if not raw:
            return None
        try:
            value = float(raw)
        except ValueError:
            return None
    if value != value or value < 0 or value > 360:
        return None
    return 0.0 if value == 360 else value


def parse_distance(text, default_unit=None):
    """A distance in metres, or None.

    "850", "850m", "850 m", "1.2km" and "1,200" all work. A unit typed with
    the number wins. A bare number is in `default_unit` ("m" or "km") when
    one is given - the unit box in the window - and otherwise a number under
    20 is kilometres: nobody marks a deposit 3 m away from range, and "1.5"
    is somebody reading the scanner in km. Zero, or anything further than
    MAX_RANGE_M, is refused rather than guessed at."""
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        raw, scale = str(float(text)), None
    else:
        raw = str(text if text is not None else "").strip().lower().replace(" ", "")
        scale = None
        for unit, factor in (("km", 1000.0), ("metres", 1.0), ("metre", 1.0),
                             ("meters", 1.0), ("m", 1.0)):
            if raw.endswith(unit):
                raw, scale = raw[:-len(unit)], factor
                break
        raw = raw.replace(",", "")
    try:
        value = float(raw)
    except ValueError:
        return None
    if value != value or value <= 0:
        return None
    if scale is None:
        unit = str(default_unit or "").strip().lower()
        if unit in ("km", "kilometres", "kilometers"):
            scale = 1000.0
        elif unit in ("m", "metres", "meters"):
            scale = 1.0
        else:
            scale = 1000.0 if value < 20 else 1.0
    metres = value * scale
    if metres > MAX_RANGE_M:
        return None
    return metres


def distance_words(metres):
    """850 m, 1.20 km - the way the rest of the app says a distance."""
    metres = float(metres)
    if metres >= 1000:
        return "%.2f km" % (metres / 1000.0)
    return "%.0f m" % metres


def place(lat, lon, bearing, metres, radius_m):
    """Where a deposit `metres` away on `bearing` really is: the great-circle
    destination across a body of `radius_m`, longitude kept in -180 to 180
    so a deposit over the date line or past a pole lands on the right side."""
    return SV.destination(float(lat), float(lon), float(bearing),
                          float(metres), float(radius_m))


# ---------------------------------------------------------------------------
# "Placed from range", in the deposit's own notes
# ---------------------------------------------------------------------------

def ranged_note(existing, bearing, metres, when=None):
    """The dated line that says a deposit was placed from range."""
    return SV.stamp_note(existing, "%s (%s at %03.0f°)"
                         % (RANGED_NOTE, distance_words(metres), bearing), when)


def refined_note(existing, moved_m, when=None):
    """The dated line that says UPDATE put it where it really is."""
    return SV.stamp_note(existing, "%s (moved %s)"
                         % (REFINED_NOTE, distance_words(moved_m)), when)


def is_ranged(row):
    """True while a deposit is still where a reading from range put it.

    The notes are read in order: the last of "placed from range" and
    "refined at the spot" says which it is."""
    ranged = False
    for line in str((row or {}).get("notes") or "").splitlines():
        line = line.strip()
        if line.startswith(RANGED_NOTE):
            ranged = True
        elif line.startswith(REFINED_NOTE):
            ranged = False
    return ranged


# ---------------------------------------------------------------------------
# Commodity names, short and long
# ---------------------------------------------------------------------------

def resolve_commodity(text):
    """(name, why): the commodity typed, or ("", the reason it was refused).

    The full name in any spelling ("bastnasite"), or the start of one long
    enough to be only one ("alex"). Anything else is refused and said - a
    deposit filed under a misspelt name is a deposit nobody finds again."""
    typed = str(text or "").strip()
    if not typed:
        return "", "No commodity named."
    known = SV.known_commodity(typed)
    if known:
        return known, ""
    needle = SV.fold(typed)
    if len(needle) >= 3:
        names = list(SV.KNOWN_COMMODITIES)
        starts = [n for n in names if SV.fold(n).startswith(needle)]
        if len(starts) == 1:
            return starts[0], ""
        if len(starts) > 1:
            return "", ("%s could be %s - type more of it."
                        % (typed, ", ".join(starts[:3])))
    return "", "%s is not a commodity EDSMT knows." % typed


# ---------------------------------------------------------------------------
# Chat commands
# ---------------------------------------------------------------------------

def clean_prefix(prefix):
    """The prefix as it is matched: trimmed, no spaces, never blank."""
    text = re.sub(r"\s+", "", str(prefix or ""))
    return text or DEFAULT_PREFIX


def note_from_event(event):
    """The parts of a SendText event that matter, or None for anything else."""
    if not isinstance(event, dict) or event.get("event") != "SendText":
        return None
    return {"to": str(event.get("To") or ""),
            "message": str(event.get("Message") or ""),
            # Older journals have no Sent field; a message there was sent.
            "sent": event.get("Sent") is not False,
            "when": str(event.get("timestamp") or "")}


def is_fresh(note, now=None, within_s=CHAT_FRESH_S, since=None):
    """Typed while EDSMT was watching, not read back from the journal's past.

    `since` is when EDSMT began looking: a message older than that was typed
    before - the journal is read from its top on every start - and is never
    a command, however recently, so a restart cannot run it a second time."""
    stamp = SV._epoch((note or {}).get("when"))
    if not stamp:
        return False
    if since is not None and stamp < since:
        return False
    now = time.time() if now is None else now
    return -within_s <= now - stamp <= within_s


def addressed(message, prefix):
    """The words after the prefix, or None when the message is not for EDSMT.

    The prefix must be a word of its own: with "!rr", "!rr rig down" is a
    command and "!rrr" is not."""
    text = str(message or "").strip()
    prefix = clean_prefix(prefix)
    if text.lower().startswith(prefix.lower()):
        rest = text[len(prefix):]
        if not rest or rest[0].isspace():
            return rest.strip()
    return None


def _tier(word, table):
    """The tier a typed word means - "h", "High", "HIGH" - or "".

    A single letter picks by its first letter; a longer word must be a whole
    tier name, so "hx" and "hello" are refused and not read as High."""
    typed = SV.fold(word)
    if len(typed) == 1:
        return table.get(typed, "")
    for name in table.values():
        if SV.fold(name) == typed:
            return name
    return ""


def _deposit_words(tokens):
    """{commodity, amount, density, rigs} from "<commodity> [amount]/[density]
    [rigs]", or {"why": ...} when something in it cannot be used."""
    amount = density = rigs = ""
    words = []
    for token in tokens:
        if "/" in token:
            left, _slash, right = token.partition("/")
            if left:
                amount = _tier(left, _AMOUNT_WORDS)
                if not amount:
                    return {"why": "%s is not an amount - High, Medium, Low "
                                   "or Depleted (h, m, l, d)." % left}
            if right:
                density = _tier(right, _DENSITY_WORDS)
                if not density:
                    return {"why": "%s is not a density - High, Medium or Low "
                                   "(h, m, l)." % right}
            continue
        if re.fullmatch(r"\d+", token):
            if rigs:
                return {"why": "Two rig counts: %s and %s." % (rigs, token)}
            if not 1 <= int(token) <= 6:
                return {"why": "The Rhino carries 6 rigs, so 1 to 6."}
            rigs = str(int(token))
            continue
        words.append(token)
    name, why = resolve_commodity(" ".join(words))
    if not name:
        return {"why": why}
    return {"commodity": name, "amount": amount, "density": density,
            "rigs": rigs}


HELP = ("Try: <commodity> h/m 4, <bearing> <distance> <commodity>, "
        "rig down 3, rig up 3, rigs up, centre, undo.")


def parse_command(message, prefix=DEFAULT_PREFIX):
    """What a chat message asks for, or None when it is not addressed to EDSMT.

    {"action": "mark", commodity, amount, density, rigs}
    {"action": "range", bearing, metres, commodity, amount, density, rigs}
    {"action": "rig_down", "rig": n or None}   {"action": "rig_up", "rig": n}
    {"action": "all_up"}   {"action": "centre"}   {"action": "undo"}
    {"action": "error", "why": "..."} - addressed to EDSMT but not understood.
    """
    rest = addressed(message, prefix)
    if rest is None:
        return None
    tokens = rest.split()
    if not tokens:
        return {"action": "error", "why": "Nothing after %s. %s"
                % (clean_prefix(prefix), HELP)}
    # "mark painite h/m 4" and "range 135 1.2km painite" are the same commands
    # as without the first word.
    if tokens[0].lower() in ("mark", "range") and len(tokens) > 1:
        tokens = tokens[1:]
    first = tokens[0].lower()
    if first == "undo":
        return {"action": "undo"}
    if first in ("centre", "center"):
        return {"action": "centre"}
    if first in ("rig", "rigs"):
        words = [t.lower() for t in tokens[1:]]
        numbers = [w for w in words if re.fullmatch(r"\d+", w)]
        if len(numbers) > 1:
            return {"action": "error", "why": "One rig at a time."}
        rig = int(numbers[0]) if numbers else None
        if rig is not None and not 1 <= rig <= 6:
            return {"action": "error", "why": "No rig %d - the Rhino carries 6." % rig}
        if "down" in words:
            return {"action": "rig_down", "rig": rig}
        if "up" in words:
            if rig is not None:
                return {"action": "rig_up", "rig": rig}
            if first == "rigs" or "all" in words:
                return {"action": "all_up"}
            return {"action": "error",
                    "why": "Which rig? rig up 1 to 6, or rigs up for all of them."}
        return {"action": "error", "why": "Rig down or rig up? %s" % HELP}
    if len(tokens) >= 2 and parse_bearing(tokens[0]) is not None \
            and re.match(r"^[\d.,]+", tokens[0]):
        metres = parse_distance(tokens[1])
        if metres is None and re.match(r"^[\d.,]+", tokens[1]):
            return {"action": "error",
                    "why": "%s is not a distance EDSMT can use - 850, 850m or "
                           "1.2km, up to %s." % (tokens[1], distance_words(MAX_RANGE_M))}
        if metres is not None:
            found = _deposit_words(tokens[2:])
            if "why" in found:
                return {"action": "error", "why": found["why"]}
            return dict(found, action="range", bearing=parse_bearing(tokens[0]),
                        metres=metres)
    if re.fullmatch(r"-?[\d.,]+", tokens[0]):
        return {"action": "error",
                "why": "%s is not a bearing - 0 to 359, then a distance." % tokens[0]}
    found = _deposit_words(tokens)
    if "why" in found:
        return {"action": "error", "why": found["why"]}
    return dict(found, action="mark")
