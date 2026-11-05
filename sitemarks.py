"""Good and bad marks on shared sites (1.10040, #302).

A commander marks a shared site good or bad - one mark each, changed as
often as they like - and the community map counts everybody's marks into
how far it trusts each site. This keeps the commander's own marks, with
what is still to be sent, so a mark made with no connection goes when there
is one; and the counts the map last gave for each site, so they can be
shown beside the marks.

Pure logic and one JSON file; no toolkit, no network.
"""
import json
import os
import time

GOOD, BAD = "good", "bad"
MARKS = (GOOD, BAD)
# A mark that could not be sent is tried again after this long.
RETRY_S = 120.0
FILE_NAME = "site_marks.json"


def _tidy(text):
    return " ".join(str(text or "").split())


def site_key(system, planet, spot="1"):
    """One site, whatever the case or spacing it was written with."""
    return "|".join((_tidy(system).lower(), _tidy(planet).lower(),
                     (_tidy(spot) or "1").lower()))


def _count(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


class MarkBook:
    """The commander's own marks, and the map's counts, by site."""

    def __init__(self, path=None):
        self.path = path
        self.marks = {}
        self.counts = {}

    def load(self):
        """Read the file. True when it read; a missing or damaged file is an
        empty book."""
        if not self.path or not os.path.exists(self.path):
            return False
        try:
            with open(self.path, encoding="utf-8") as handle:
                data = json.load(handle)
            marks = data.get("marks") or {}
            counts = data.get("counts") or {}
            self.marks = {key: dict(entry) for key, entry in marks.items()
                          if isinstance(entry, dict) and entry.get("mark") in MARKS}
            self.counts = {key: (int(pair[0]), int(pair[1])) for key, pair in counts.items()
                           if isinstance(pair, (list, tuple)) and len(pair) == 2}
        except (OSError, ValueError, TypeError, AttributeError):
            self.marks, self.counts = {}, {}
            return False
        for entry in self.marks.values():
            # Whatever was on its way when the app closed goes again.
            entry["tried"] = 0.0
        return True

    def save(self):
        """Write the file, through a temporary one. False when it could not."""
        if not self.path:
            return False
        try:
            folder = os.path.dirname(self.path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            spare = self.path + ".tmp"
            with open(spare, "w", encoding="utf-8") as handle:
                json.dump({"marks": self.marks,
                           "counts": {k: list(v) for k, v in self.counts.items()}},
                          handle, indent=1)
            os.replace(spare, self.path)
            return True
        except OSError:
            return False

    def mine(self, system, planet, spot="1"):
        """"good", "bad", or "" for a site this commander has not marked."""
        entry = self.marks.get(site_key(system, planet, spot))
        return entry["mark"] if entry else ""

    def mark(self, system, planet, spot, mark, now=None):
        """Mark a site. False for anything but good or bad, and for the mark
        it already has - that is no change and nothing to send."""
        if mark not in MARKS or not _tidy(system) or not _tidy(planet):
            return False
        key = site_key(system, planet, spot)
        if self.marks.get(key, {}).get("mark") == mark:
            return False
        self.marks[key] = {"system": _tidy(system), "planet": _tidy(planet),
                           "spot": _tidy(spot) or "1", "mark": mark,
                           "at": float(time.time() if now is None else now),
                           "sent": False, "tried": 0.0}
        return True

    def due(self, now=None):
        """The marks still to send that are not already on their way."""
        now = time.time() if now is None else now
        return [entry for entry in self.marks.values()
                if not entry.get("sent")
                and (not entry.get("tried") or now - entry["tried"] >= RETRY_S)]

    def sending(self, entry, now=None):
        """Note a mark has gone to the worker, so it is not sent twice."""
        key = site_key(entry.get("system"), entry.get("planet"), entry.get("spot"))
        if key in self.marks:
            self.marks[key]["tried"] = float(time.time() if now is None else now)

    def answered(self, message):
        """The worker's answer to a mark: (status, words).

        status is "sent" (the map took it), "later" (no answer - kept, to go
        again after RETRY_S), "refused" (the map will never take it - the
        site is not there - so it is dropped), or "" for a message that is
        not an answer to a mark. An answer for an older mark than the one
        now kept ticks nothing off: the newer one still goes."""
        try:
            data = json.loads(message)
            system, planet, spot = data["site"]
            mark = data["mark"]
        except (TypeError, ValueError, KeyError):
            return "", ""
        key = site_key(system, planet, spot)
        entry = self.marks.get(key)
        current = entry is not None and entry.get("mark") == mark
        if "error" in data:
            if data.get("refused"):
                if current:
                    del self.marks[key]
                return "refused", "The community map would not take that mark: %s" % data["error"]
            return "later", ("Mark kept - it goes to the community map when it "
                             "answers (%s)." % data["error"])
        reply = data.get("reply") or {}
        good, bad = _count(reply.get("good")), _count(reply.get("bad"))
        if good is not None and bad is not None:
            self.counts[key] = (good, bad)
        if current:
            entry["sent"] = True
        words = "Marked %s %s %s." % (_tidy(planet), "signal " + _tidy(spot), mark)
        if good is not None and bad is not None:
            words += " The community map has %d good, %d bad on it now." % (good, bad)
        return "sent", words

    def take_rows(self, rows):
        """Learn each site's counts from an answer that lists sites or finds:
        rows carrying good_marks and bad_marks beside system, planet (or
        body) and spot (or location)."""
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            good, bad = _count(row.get("good_marks")), _count(row.get("bad_marks"))
            planet = row.get("planet") or row.get("body")
            spot = row.get("spot") if row.get("spot") not in (None, "") else row.get("location")
            if good is None or bad is None or not row.get("system") or not planet:
                continue
            self.counts[site_key(row["system"], planet, spot)] = (good, bad)

    def counts_for(self, system, planet, spot="1"):
        """(good, bad) the map last gave for a site, or None."""
        return self.counts.get(site_key(system, planet, spot))


def buttons(book, system, planet, spot="1"):
    """[(text, mark, lit)] for a site's two marks: "good 3", "bad 1" - the
    count beside each where the map has given one - with the commander's own
    mark lit."""
    mine = book.mine(system, planet, spot) if book is not None else ""
    counts = book.counts_for(system, planet, spot) if book is not None else None
    out = []
    for index, mark in enumerate(MARKS):
        text = mark if counts is None else "%s %d" % (mark, counts[index])
        out.append((text, mark, mine == mark))
    return out
