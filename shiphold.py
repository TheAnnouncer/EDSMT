"""The ship's hold while the commander is out in the Rhino (1.10035, #240).

What the journal says, checked against real sessions:

  * The ship's hold is stated only when the Rhino docks: Cargo, Vessel Ship,
    Count N, five or six seconds after DockSRV. In between it is that figure
    plus what CargoTransfer has moved since, which the reader keeps in
    ship_total (journal.py). Never seen this session means not known.
  * Loadout.CargoCapacity changes every time the racks do - five values in
    five days on one hull - so it is kept per ship ID, from the newest
    Loadout, and not per hull type.
  * The Rhino's hold is not in the journal at all. Its peak Cargo tick in
    real sessions is 72 t, so a "load" is counted at 72 t.

Nothing here draws or touches a widget: the app and the overlay ask for a
card and show what is in it.
"""

import json
import math
import os
import threading

CAPACITY_FILE = "ship_capacity.json"
RHINO_HOLD_T = 72                       # the largest Rhino tick seen, WATCH
_LOADOUT = b'"Loadout"'


def _whole(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class CapacityBook:
    """Each ship's cargo capacity as its newest Loadout stated it, kept in
    ship_capacity.json so a restart on the surface, or a journal that has no
    Loadout in it, still knows the hold."""

    def __init__(self, folder=None):
        self.path = os.path.join(folder, CAPACITY_FILE) if folder else ""
        self.ships = {}          # "5" -> {"capacity": 1239, "when": ..., "ship": ...}
        self.files = {}          # older journals already read -> size
        self.last = None         # the ship ID of the newest Loadout
        self.dirty = False
        self._lock = threading.Lock()
        self.load()

    def load(self):
        if not self.path or not os.path.exists(self.path):
            return False
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return False
        if not isinstance(data, dict):
            return False
        ships = data.get("ships")
        if isinstance(ships, dict):
            self.ships = {str(k): dict(v) for k, v in ships.items()
                          if isinstance(v, dict) and _whole(v.get("capacity")) > 0}
        files = data.get("files")
        self.files = dict(files) if isinstance(files, dict) else {}
        self._newest()
        return True

    def save(self):
        if not self.path:
            return False
        with self._lock:
            data = {"ships": dict(self.ships), "files": dict(self.files)}
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            # One temp file per thread: the older-journal pass and the live
            # tick can both save, and must not write into each other's.
            temp = "%s.%d.tmp" % (self.path, threading.get_ident())
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump(data, handle)
            os.replace(temp, self.path)
            self.dirty = False
            return True
        except OSError:
            return False

    def _newest(self):
        with self._lock:
            if self.ships:
                self.last = int(max(self.ships, key=lambda k: str(self.ships[k].get("when") or "")))
            else:
                self.last = None

    def note(self, ship_id, capacity, when="", ship=""):
        """One Loadout. The newest by its own timestamp wins, whatever order
        files are read in. True when the book changed."""
        try:
            key = str(int(ship_id))
        except (TypeError, ValueError):
            return False
        capacity = _whole(capacity)
        if capacity <= 0:
            return False
        when = str(when or "")
        with self._lock:
            have = self.ships.get(key)
            if have and str(have.get("when") or "") > when:
                return False
            if have and have.get("capacity") == capacity and have.get("when") == when:
                return False
            self.ships[key] = {"capacity": capacity, "when": when, "ship": str(ship or "")}
            self.dirty = True
        self._newest()
        return True

    def capacity_for(self, ship_id=None):
        """The capacity of one ship, or of the one last fitted when none is
        named. None when the book has never seen a Loadout for it."""
        with self._lock:
            key = str(ship_id) if ship_id is not None else (
                str(self.last) if self.last is not None else None)
            have = self.ships.get(key) if key is not None else None
        return _whole(have.get("capacity")) or None if have else None

    def observe(self, reader):
        """Take what the live reader has seen. True when anything changed."""
        changed = False
        for ship_id, (capacity, when) in dict(getattr(reader, "capacities", None) or {}).items():
            if self.note(ship_id, capacity, when, getattr(reader, "ship_type", "")):
                changed = True
        return changed

    # -- the older journals -------------------------------------------------

    def learn_file(self, path):
        """Every Loadout in one journal file. How many were new."""
        with open(path, "rb") as handle:
            data = handle.read()
        if _LOADOUT not in data:
            return 0
        learnt = 0
        for raw in data.split(b"\n"):
            if _LOADOUT not in raw:
                continue
            try:
                event = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            if isinstance(event, dict) and event.get("event") == "Loadout" \
                    and event.get("ShipID") is not None \
                    and event.get("CargoCapacity") is not None:
                if self.note(event.get("ShipID"), event.get("CargoCapacity"),
                             event.get("timestamp"), event.get("Ship")):
                    learnt += 1
        return learnt

    def learn_folder(self, folder, stop=None):
        """Every journal in the folder not read for Loadouts yet. Never raises."""
        learnt = 0
        try:
            names = sorted(n for n in os.listdir(folder)
                           if n.startswith("Journal.") and n.endswith(".log"))
        except OSError:
            return 0
        for name in names:
            if stop is not None and stop.is_set():
                break
            path = os.path.join(folder, name)
            try:
                size = os.path.getsize(path)
                if self.files.get(name) == size:
                    continue
                learnt += self.learn_file(path)
            except OSError:
                continue
            with self._lock:
                self.files[name] = size
        self.save()
        return learnt


def capacity_of(reader, book=None):
    """(capacity, where it came from) for the ship the reader is in."""
    ship_id = getattr(reader, "ship_id", None)
    seen = dict(getattr(reader, "capacities", None) or {})
    if ship_id is not None and ship_id in seen and _whole(seen[ship_id][0]) > 0:
        return _whole(seen[ship_id][0]), "this journal"
    fitted = _whole(getattr(reader, "cargo_capacity", None))
    if fitted > 0:
        return fitted, "this journal"
    if book is not None:
        have = book.capacity_for(ship_id)
        if have:
            return have, "an earlier journal"
    return None, ""


def hold_card(reader, book=None):
    """What to show about the ship's hold, or None for a reader that does not
    track it. A dict:

      known      the ship's total has been stated or counted this session
      tonnes     what is in the ship, only when known
      capacity   its hold, only when known and not contradicted by tonnes
      free, full, fraction, loads_left
      trip_t     tonnes the Rhino has unloaded since it was launched
      rhino_t    what the Rhino holds now, when the journal says
      title, detail, line   the words, ready to show
      state      "ok", "near", "full" or "unknown" - for a colour
    Unknown stays unknown: a total that has not been seen is never guessed
    from the transfers alone."""
    if not hasattr(reader, "ship_total"):
        return None
    total = reader.ship_total
    known = total is not None
    tonnes = max(0, _whole(total)) if known else None
    trip = max(0, _whole(getattr(reader, "trip_unloaded", 0)))
    rhino = getattr(reader, "srv_total", None)
    rhino = None if rhino is None else max(0, _whole(rhino))
    capacity, source = capacity_of(reader, book)
    stale = bool(known and capacity and tonnes > capacity)
    if stale:
        capacity = None
    card = {"known": known, "tonnes": tonnes, "capacity": capacity,
            "free": None, "full": False, "fraction": None, "loads_left": None,
            "trip_t": trip, "rhino_t": rhino, "stale": stale, "source": source}
    if known and capacity:
        free = capacity - tonnes
        card.update(free=free, full=free <= 0,
                    fraction=max(0.0, min(1.0, tonnes / float(capacity))),
                    loads_left=0 if free <= 0 else int(math.ceil(free / float(RHINO_HOLD_T))))
    if known and capacity:
        card["title"] = "SHIP %d/%d t" % (tonnes, capacity)
        if card["full"]:
            card["detail"] = "HOLD FULL"
            card["state"] = "full"
        else:
            card["detail"] = "%d t free - %d load%s left" % (
                card["free"], card["loads_left"], "" if card["loads_left"] == 1 else "s")
            card["state"] = "near" if card["fraction"] >= 0.9 else "ok"
    elif known:
        card["title"] = "SHIP %d t" % tonnes
        card["detail"] = ("capacity out of date - board the ship" if stale
                          else "capacity not known yet")
        card["state"] = "ok"
    else:
        card["title"] = ("SHIP +%d t this trip" % trip) if trip else "SHIP hold not seen"
        card["detail"] = "BOARD SHIP FOR FULL HOLD"
        card["state"] = "unknown"
    bits = [card["title"], card["detail"]]
    if known and trip:
        bits.append("%d t unloaded this trip" % trip)
    if rhino is not None:
        bits.append("RHINO %d/%d t" % (rhino, RHINO_HOLD_T))
    card["line"] = " - ".join(bits)
    return card
