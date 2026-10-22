"""What the community has measured, in the app's words (1.10036).

Two things nobody publishes and every commander would like to know:

  * how long a worked-out deposit takes to come back (#156) - from reports
    of deposits seen full again, each one bracketing the time between the
    last look that found it empty and the look that found it full;
  * how close two rigs can go (#157) - from the closest pair of rigs in
    every rig layout commanders have shared.

The community map does the counting. This module says what it found, and
builds the report the app sends when one of the commander's own worked-out
deposits comes back. Pure logic: no Tk, no network.
"""
import time

import regrowth as RG
import survey as SV

REFRESH_S = 6 * 3600
REGROWTH_TAG = "regrowth"
SPACING_TAG = "rig-spacing"
REGROWTH_SHARE_TAG = "regrowth-share"


def _number(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out else out


def _days(value):
    value = _number(value)
    if value is None:
        return ""
    return "%d" % round(value) if value >= 3 else "%.1f" % value


def regrowth_words(summary):
    """"reports say 16-28 d (12 reports)", with "not measured yet" while
    there are too few; "" with none at all."""
    if not isinstance(summary, dict) or not summary.get("reports"):
        return ""
    low, high = _days(summary.get("low_days")), _days(summary.get("high_days"))
    if not high:
        return ""
    span = high if low in ("", high) else "%s-%s" % (low, high)
    count = int(summary.get("reports") or 0)
    words = "reports say %s d (%d report%s" % (span, count, "" if count == 1 else "s")
    if not summary.get("measured"):
        words += ", not measured yet"
    return words + ")"


def spacing_words(summary):
    """"Commanders have put working rigs as close as 61.5 m apart (median
    closest pair 79 m, 37 layouts by 12 commanders)", or ""."""
    if not isinstance(summary, dict) or not summary.get("layouts"):
        return ""
    closest, median = _number(summary.get("closest_m")), _number(summary.get("median_m"))
    if closest is None:
        return ""
    layouts, who = int(summary.get("layouts") or 0), int(summary.get("commanders") or 0)
    words = ("Commanders have put working rigs as close as %s m apart (median closest "
             "pair %s m, %d layout%s by %d commander%s" % (
                 ("%.1f" % closest).rstrip("0").rstrip("."),
                 ("%.0f" % median) if median is not None else "?",
                 layouts, "" if layouts == 1 else "s", who, "" if who == 1 else "s"))
    if not summary.get("measured"):
        words += ", not measured yet"
    return words + ")."


def regrowth_message(deposit, how, regrown_at=None, system=None, body=None):
    """The report for a deposit seen full again, or None when it cannot say
    when it was worked out. `how` is "seen" (the REGROWN button) or
    "refined" (tonnes refined at it since it was marked)."""
    deposit = deposit or {}
    if not RG.depleted(deposit):
        return None
    first = RG.first_date(deposit)
    if not first:
        return None
    back = float(regrown_at if regrown_at is not None else time.time())
    if back <= first:
        return None
    looks = [at for at in RG.looks(deposit) if first <= at <= back]
    system = system or deposit.get("system")
    body = body or deposit.get("body") or deposit.get("planet")
    if not (system and body):
        return None
    return {"system": str(system), "planet": str(body),
            "spot": str(deposit.get("location") or deposit.get("spot") or "1"),
            "commodity": SV.canonical(deposit.get("commodity") or ""),
            "depleted_at": RG.stamp(first),
            "last_empty": RG.stamp(looks[-1]) if looks else "",
            "regrown_at": RG.stamp(back),
            "how": "refined" if how == "refined" else "seen"}


def first_tonne_back(deposit, commodity):
    """True when the tonne just refined at a depleted deposit is the first
    of its own commodity since it was marked: the moment it came back."""
    if not RG.depleted(deposit):
        return False
    if SV.fold(SV.canonical(commodity or "")) != SV.fold(SV.canonical(deposit.get("commodity") or "")):
        return False
    own, _others = SV.own_tonnes(deposit)
    return own == 1


class Crowd:
    """The latest of both measurements, and when to ask again."""

    def __init__(self):
        self.regrowth = None
        self.spacing = None
        self.asked_at = 0.0
        self.sent = set()

    def due(self, now=None):
        now = time.time() if now is None else now
        return now - self.asked_at >= REFRESH_S

    def take(self, tag, data):
        if not isinstance(data, dict):
            return False
        if tag == REGROWTH_TAG and isinstance(data.get("all"), dict):
            self.regrowth = data
            return True
        if tag == SPACING_TAG and "layouts" in data:
            self.spacing = data
            return True
        if tag == REGROWTH_SHARE_TAG and isinstance(data.get("regrowth"), dict):
            # The answer to a report carries the overall figure as it now is.
            whole = dict(self.regrowth or {})
            if not whole.get("commodity"):
                whole["all"] = data["regrowth"]
            self.regrowth = whole
            return True
        return False

    def regrowth_for(self, commodity=""):
        """The best figure for a commodity: its own once it has three
        reports, else everyone's."""
        data = self.regrowth or {}
        wanted = SV.fold(SV.canonical(commodity or ""))
        for row in data.get("by_commodity") or ():
            if isinstance(row, dict) and SV.fold(row.get("name")) == wanted \
                    and int(row.get("reports") or 0) >= 3:
                return row
        return data.get("all")

    def card_line(self, deposit):
        """The line a depleted deposit's card adds, or ""."""
        if not RG.depleted(deposit):
            return ""
        return regrowth_words(self.regrowth_for((deposit or {}).get("commodity")))

    def once(self, message):
        """True the first time this report is seen this run."""
        key = (message or {}).get("planet"), (message or {}).get("commodity"), \
            (message or {}).get("depleted_at"), (message or {}).get("spot")
        if key in self.sent:
            return False
        self.sent.add(key)
        return True
