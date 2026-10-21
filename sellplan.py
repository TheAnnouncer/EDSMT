"""One stop for the whole hold, sell within N jumps, and how a price moved.

Pure logic: no Tk, no network. The windows hand in what is aboard and the
judged price rows the app already has (Demand 0 gone, every row aged and
marked stale past a day); this module answers three questions:

  - which one station takes the most of the hold, for the most credits;
  - how many jumps away a station is, at the commander's jump range;
  - whether a station's price and demand have moved since it was last seen.

A station only counts for a commodity it has a fresh price for. Demand is a
cap: a market that wants 300 t of a 500 t load takes 300 t, and the rest is
said to be left over rather than counted at that price.
"""
import json
import math
import os
import tempfile
import threading

import survey as SV

TRENDS_FILE = "price-trends.json"
TRENDS_MAX = 4000            # station x commodity pairs kept on disk
TREND_SPAN_S = 24 * 3600     # an older reading is history, not a trend
JUMP_FALLBACK_LY = 20.0      # used, and said, until the ship's range is known
JUMP_CHOICES = (("1 jump", 1), ("2 jumps", 2), ("4 jumps", 4), ("8 jumps", 8))


def _number(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out else out


def _distance(row):
    for key in ("distance_ly", "distance"):
        far = _number(row.get(key))
        if far is not None:
            return far
    return None


def _carrier(row):
    kind = SV.fold(row.get("station_type"))
    if "carrier" in kind:
        return True
    name = str(row.get("station") or "").strip()
    return len(name) == 7 and name[3] == "-" and name.replace("-", "").isalnum()


def jumps_for(ly, jump_ly):
    """Jumps to cover `ly` at `jump_ly` a jump: 0 in the same system, None
    when either is unknown."""
    ly, jump_ly = _number(ly), _number(jump_ly)
    if ly is None or not jump_ly or jump_ly <= 0:
        return None
    if ly <= 0.05:
        return 0
    return int(math.ceil(ly / jump_ly - 1e-9))


def radius_for(choice, jump_ly):
    """(light years, jump range used, guessed) for a "N jumps" choice."""
    jumps = dict(JUMP_CHOICES).get(str(choice or "").strip())
    if jumps is None:
        return None
    guessed = not (_number(jump_ly) and _number(jump_ly) > 0)
    reach = JUMP_FALLBACK_LY if guessed else float(jump_ly)
    return (round(jumps * reach, 1), reach, guessed)


def whole_hold(hold, rows_for, within_ly=None, no_carriers=True, top=3,
               trends=None):
    """The stations that take the most of what is aboard, best first.

    `hold` is {commodity: tonnes}; `rows_for(name)` gives that commodity's
    judged price rows. Stale rows are left out: a station is not the answer
    on a price nobody has seen for a day. Each answer:

      {"station", "system", "distance_ly", "total", "tonnes", "of",
       "parts": [{"commodity", "tonnes", "aboard", "sell", "value",
                  "seen", "age_s", "trend"}...],
       "missing": [commodity...], "oldest_s"}

    `tonnes` is what the station takes, `of` what is aboard. Sorted by
    credits, then by how much of the hold it takes, then nearest first.
    """
    aboard = {str(k): int(v) for k, v in dict(hold or {}).items()
              if _number(v) and int(v) > 0}
    if not aboard:
        return []
    stations = {}
    for name, count in aboard.items():
        try:
            rows = list(rows_for(name) or ())
        except Exception:
            rows = []
        for row in rows:
            if not isinstance(row, dict) or row.get("stale"):
                continue
            sell = _number(row.get("sell"))
            if not sell or sell <= 0:
                continue
            if no_carriers and _carrier(row):
                continue
            far = _distance(row)
            if within_ly is not None and far is not None and far > float(within_ly) + 1e-6:
                continue
            key = (SV.fold(row.get("system")), SV.fold(row.get("station")))
            if not all(key):
                continue
            demand = _number(row.get("demand"))
            take = count if demand is None else int(min(count, max(0, demand)))
            if take <= 0:
                continue
            spot = stations.setdefault(key, {
                "station": row.get("station"), "system": row.get("system"),
                "distance_ly": far, "parts": {}})
            if spot["distance_ly"] is None:
                spot["distance_ly"] = far
            have = spot["parts"].get(name)
            if have is None or sell > have["sell"]:
                spot["parts"][name] = {
                    "commodity": name, "tonnes": take, "aboard": count,
                    "sell": int(sell), "value": int(sell) * take,
                    "seen": row.get("seen"), "age_s": row.get("age_s"),
                    "trend": trends.trend(row, name) if trends is not None else None}
    out = []
    held = sum(aboard.values())
    for spot in stations.values():
        parts = sorted(spot["parts"].values(), key=lambda p: -p["value"])
        ages = [p["age_s"] for p in parts if _number(p["age_s"]) is not None]
        out.append({
            "station": spot["station"], "system": spot["system"],
            "distance_ly": spot["distance_ly"],
            "total": sum(p["value"] for p in parts),
            "tonnes": sum(p["tonnes"] for p in parts), "of": held,
            "parts": parts,
            "missing": sorted(n for n in aboard if n not in spot["parts"]),
            "oldest_s": max(ages) if ages else None})
    out.sort(key=lambda s: (-s["total"], -s["tonnes"],
                            s["distance_ly"] is None, s["distance_ly"] or 0.0))
    return out[:max(0, int(top))] if top else out


def age_words(seconds):
    """"3 h 00 min", "32 min", "just now" - for an age in seconds."""
    seconds = _number(seconds)
    if seconds is None:
        return "age unknown"
    seconds = max(0, int(seconds))
    if seconds < 90:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return "%d min" % minutes
    hours, minutes = divmod(minutes, 60)
    if hours < 48:
        return "%d h %02d min" % (hours, minutes)
    return "%d days" % (hours // 24)


def trend_words(trend):
    """"demand 16,234 -> 15,352, price 845,417 -> 824,191 in 1 h 28 min"."""
    if not trend:
        return ""
    bits = []
    if trend.get("demand_from") is not None and trend.get("demand_to") is not None \
            and trend["demand_from"] != trend["demand_to"]:
        bits.append("demand {:,} → {:,}".format(trend["demand_from"], trend["demand_to"]))
    if trend.get("price_from") != trend.get("price_to"):
        bits.append("price {:,} → {:,}".format(trend["price_from"], trend["price_to"]))
    if not bits:
        return ""
    return ", ".join(bits) + " in " + age_words(trend.get("span_s"))


def _clean_int(value):
    value = _number(value)
    return None if value is None else int(round(value))


class Trends:
    """The last two different readings of each station's price for each
    commodity, so a station can say which way it is moving. Fed with every
    judged row the app sees; kept on disk, trimmed to the newest pairs.
    Never raises."""

    def __init__(self, folder=None):
        self.path = os.path.join(folder, TRENDS_FILE) if folder else ""
        self.pairs = {}          # "system|station|commodity" -> [older, newer]
        self.dirty = False
        self._lock = threading.Lock()
        self.load()

    @staticmethod
    def key(row, commodity=None):
        name = commodity or row.get("commodity")
        parts = (SV.fold(row.get("system")), SV.fold(row.get("station")), SV.fold(name))
        return "|".join(parts) if all(parts) else ""

    def load(self):
        if not self.path:
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        pairs = data.get("pairs") if isinstance(data, dict) else None
        if isinstance(pairs, dict):
            self.pairs = {str(k): [dict(x) for x in v if isinstance(x, dict)][-2:]
                          for k, v in pairs.items() if isinstance(v, list)}

    def save(self):
        if not self.path or not self.dirty:
            return False
        with self._lock:
            newest = sorted(self.pairs.items(), key=lambda kv: -(kv[1][-1].get("at") or 0))
            self.pairs = dict(newest[:TRENDS_MAX])
            data = {"pairs": self.pairs}
            self.dirty = False
        try:
            folder = os.path.dirname(self.path) or "."
            os.makedirs(folder, exist_ok=True)
            handle, temp = tempfile.mkstemp(dir=folder, suffix=".tmp")
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                json.dump(data, out)
            os.replace(temp, self.path)
            return True
        except OSError:
            return False

    def note(self, rows, commodity=None):
        """Remember each row's reading. How many readings were new."""
        new = 0
        for row in rows or ():
            if not isinstance(row, dict):
                continue
            key = self.key(row, commodity)
            at = SV._epoch(row.get("seen"))
            sell = _clean_int(row.get("sell"))
            if not key or not at or not sell:
                continue
            reading = {"at": at, "sell": sell, "demand": _clean_int(row.get("demand"))}
            with self._lock:
                have = self.pairs.get(key) or []
                if have and at <= have[-1]["at"]:
                    continue
                if have and (have[-1]["sell"], have[-1].get("demand")) == \
                        (reading["sell"], reading["demand"]):
                    continue
                self.pairs[key] = (have + [reading])[-2:]
                self.dirty = True
            new += 1
        return new

    def trend(self, row, commodity=None):
        """{"price_from", "price_to", "demand_from", "demand_to", "span_s"}
        when this station has an earlier, different reading within a day of
        the one in `row`; else None."""
        key = self.key(row, commodity)
        with self._lock:
            have = list(self.pairs.get(key) or [])
        if len(have) < 2:
            return None
        older, newer = have[-2], have[-1]
        at = SV._epoch(row.get("seen"))
        if at and abs(at - newer["at"]) > 1:
            return None
        span = newer["at"] - older["at"]
        if span <= 0 or span > TREND_SPAN_S:
            return None
        return {"price_from": older["sell"], "price_to": newer["sell"],
                "demand_from": older.get("demand"), "demand_to": newer.get("demand"),
                "span_s": span}
