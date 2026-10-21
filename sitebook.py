"""What My sites keeps beside the finds themselves (1.10035).

  * favourites  - a star on a site; the list can be narrowed to the starred;
  * the bin     - a site you remove goes here, with every find and signal it
                  held, and stays for a number of days (Settings: "Keep the
                  bin for") before it goes for good; Restore puts it back;
  * the best three commodities a location line names, by best known Cr/t;
  * the arrival line ("2 of your sites here, 3 shared");
  * the prompt for a tonne refined where nothing is marked.

All of it is plain data and plain functions: no window code, so every rule can
be checked without a display. The favourites and the bin live in one small
file beside the finds (sitebook.json), which a backup already includes.
"""

import json
import os
import time

import survey as SV

FILE = "sitebook.json"
TRASH_DAYS = 30
TRASH_DAYS_MAX = 365
DAY = 86400.0

# The most a location line names.
BEST_COMMODITIES = 3


def site_key(system, body, signal=""):
    """One site, as a string that does not care about case or accents."""
    return "%s|%s|%s" % (SV.fold(system), SV.fold(body), str(signal or "").strip())


def key_of(site):
    return site_key(site.get("system"), site.get("body"), site.get("signal"))


def retention_days(value):
    """The bin's retention from a settings value: whole days, 1 to a year,
    30 where it is missing or nonsense."""
    try:
        days = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return TRASH_DAYS
    return max(1, min(TRASH_DAYS_MAX, days))


class SiteBook:
    """Favourites and the bin for one commander's records."""

    def __init__(self, folder):
        self.folder = folder
        self.path = os.path.join(folder, FILE)

    # -- the file --------------------------------------------------------

    def _read(self):
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        favourites = data.get("favourites")
        trash = data.get("trash")
        return {"favourites": [str(k) for k in favourites] if isinstance(favourites, list) else [],
                "trash": [t for t in trash if isinstance(t, dict)] if isinstance(trash, list) else []}

    def _write(self, data):
        try:
            os.makedirs(self.folder, exist_ok=True)
            temp = self.path + ".tmp"
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=1)
            os.replace(temp, self.path)
            return True
        except OSError:
            return False

    # -- favourites ------------------------------------------------------

    def favourites(self):
        return set(self._read()["favourites"])

    def is_favourite(self, key):
        return key in self.favourites()

    def set_favourite(self, key, on):
        """Star or unstar a site. The new state."""
        data = self._read()
        keys = [k for k in data["favourites"] if k != key]
        if on:
            keys.append(key)
        data["favourites"] = keys
        self._write(data)
        return bool(on)

    def toggle_favourite(self, key):
        return self.set_favourite(key, not self.is_favourite(key))

    # -- the bin ---------------------------------------------------------

    def bin(self):
        """What is in the bin, newest first."""
        return sorted(self._read()["trash"], key=lambda t: t.get("binned", ""),
                      reverse=True)

    def binned(self):
        return len(self._read()["trash"])

    @staticmethod
    def _rows_of(store, system, body, signal):
        want = (SV.fold(system), SV.fold(body), str(signal or "").strip())

        def same(row, field):
            return (SV.fold(row.get("system")), SV.fold(row.get("body")),
                    str(row.get(field) or "").strip()) == want
        return ([d for d in store.deposits if same(d, "location")],
                [r for r in store.locations if same(r, "location")])

    def remove_site(self, store, system, body, signal, now=None):
        """Put a site in the bin: its finds and signal leave the records and
        wait here. The bin entry, or None when there was nothing to remove."""
        deposits, locations = self._rows_of(store, system, body, signal)
        if not deposits and not locations:
            return None
        now = time.time() if now is None else now
        entry = {"id": SV.new_id(), "binned": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                            time.gmtime(now)),
                 "system": str(system or ""), "body": str(body or ""),
                 "signal": str(signal or "").strip(),
                 "deposits": [dict(d) for d in deposits],
                 "locations": [dict(r) for r in locations]}
        data = self._read()
        data["trash"].append(entry)
        if not self._write(data):
            return None
        gone_d, gone_l = {id(d) for d in deposits}, {id(r) for r in locations}
        store.deposits = [d for d in store.deposits if id(d) not in gone_d]
        store.locations = [r for r in store.locations if id(r) not in gone_l]
        store.save_deposits()
        store.save_locations()
        return entry

    def restore(self, store, entry_id):
        """Put a binned site back. (finds restored, signals restored), or None
        when it is not in the bin. Anything already back under the same id
        is left alone, so restoring twice cannot double a find."""
        data = self._read()
        entry = next((t for t in data["trash"] if t.get("id") == entry_id), None)
        if entry is None:
            return None
        have_d = {d.get("id") for d in store.deposits}
        have_l = {r.get("id") for r in store.locations}
        back_d = back_l = 0
        for row in entry.get("deposits") or []:
            if isinstance(row, dict) and row.get("id") not in have_d:
                store.deposits.append({key: str(row.get(key, "")) for key in SV.DEPOSIT_FIELDS})
                back_d += 1
        for row in entry.get("locations") or []:
            if isinstance(row, dict) and row.get("id") not in have_l:
                store.locations.append({key: str(row.get(key, "")) for key in SV.LOCATION_FIELDS})
                back_l += 1
        data["trash"] = [t for t in data["trash"] if t.get("id") != entry_id]
        self._write(data)
        store.save_deposits()
        store.save_locations()
        return back_d, back_l

    def purge(self, days, now=None):
        """Let go of what has been in the bin longer than `days`. How many
        entries went for good."""
        now = time.time() if now is None else now
        limit = retention_days(days) * DAY
        data = self._read()
        keep, dropped = [], 0
        for entry in data["trash"]:
            when = SV._epoch(entry.get("binned"))
            if when and now - when >= limit:
                dropped += 1
            else:
                keep.append(entry)
        if dropped:
            data["trash"] = keep
            self._write(data)
        return dropped

    def empty(self):
        """Empty the bin. How many entries went."""
        data = self._read()
        count = len(data["trash"])
        if count:
            data["trash"] = []
            self._write(data)
        return count

    @staticmethod
    def days_left(entry, days, now=None):
        """Whole days before an entry goes for good, 0 or more."""
        now = time.time() if now is None else now
        when = SV._epoch(entry.get("binned"))
        if not when:
            return 0
        left = retention_days(days) * DAY - (now - when)
        return max(0, int(-(-left // DAY)))


# -- a location line's best three ---------------------------------------

def best_commodities(names, prices=None, count=BEST_COMMODITIES):
    """The `count` most valuable of `names` by best known Cr/t, each once.

    What a market showed beats the published average; a commodity with no
    price at all goes last, alphabetically. The spelling is the list's own,
    and two spellings of one commodity are one."""
    seen, unique = set(), []
    for name in names or ():
        tidy = SV.canonical(name)
        if tidy and tidy.lower() != "unknown" and SV.fold(tidy) not in seen:
            seen.add(SV.fold(tidy))
            unique.append(tidy)
    folded = {SV.fold(k): v for k, v in (prices or {}).items()}
    unique.sort(key=lambda n: (-SV.price_of(n, folded), n.lower()))
    return unique[:count]


def location_names(offered, marked):
    """Everything a location can be said to hold: what the signal offers and
    what has been marked in it."""
    return list(offered or ()) + list(marked or ())


# -- arriving ----------------------------------------------------------

def arrival_counts(store, system, shared_rows=(), own_sites=None):
    """(your sites in this system, sites others have shared here).

    A shared site that is also one of yours is yours, once. `shared_rows` is
    what the community listed for the system: dicts with the body and spot
    under whichever names the server used."""
    mine = {}
    for site in (own_sites if own_sites is not None else store.sites()):
        if SV.fold(site.get("system")) == SV.fold(system):
            mine[(SV.fold(site.get("body")), str(site.get("signal") or "").strip())] = 1
    others = set()
    for row in shared_rows or ():
        if not isinstance(row, dict):
            continue
        body = SV.fold(row.get("planet") or row.get("body"))
        spot = str(row.get("spot") if row.get("spot") is not None
                   else row.get("location") or "").strip()
        if (body, spot) not in mine:
            others.add((body, spot))
    return len(mine), len(others)


def arrival_line(mine, shared):
    """"2 of your sites here, 3 shared", or "" when both are nothing."""
    if mine <= 0 and shared <= 0:
        return ""
    return "%d of your sites here, %d shared" % (mine, shared)


# -- a tonne refined where nothing is marked ----------------------------

def unmarked_refine(store, note, within_m, spots):
    """The prompt for a tonne refined with nothing marked there, or None.

    `note` is the journal's refined tonne as the app queues it. Nothing is
    asked unless the commander was in the Rhino with a position, and no
    deposit of that commodity is marked within `within_m` - nor any other
    commodity's within the same distance, because the by-products of a
    marked deposit are refined standing at it and are not a new find.
    `spots` is the list of places already asked about; the same place and
    commodity is asked once."""
    if not note.get("in_srv"):
        return None
    try:
        lat, lon = float(note.get("lat")), float(note.get("lon"))
        radius = float(note.get("radius_m"))
    except (TypeError, ValueError):
        return None
    system, body = str(note.get("system") or ""), str(note.get("body") or "")
    commodity = SV.canonical(note.get("commodity") or "")
    if not (radius and system and body and commodity):
        return None
    for row in store.at(system, body):
        try:
            metres = SV.surface_range_m(lat, lon, float(row["lat"]),
                                        float(row["lon"]), radius)
        except (KeyError, TypeError, ValueError):
            continue
        if metres <= within_m:
            return None
    for old in spots:
        if (SV.fold(old["system"]), SV.fold(old["body"]), SV.fold(old["commodity"])) == \
                (SV.fold(system), SV.fold(body), SV.fold(commodity)) \
                and SV.surface_range_m(lat, lon, old["lat"], old["lon"], radius) <= within_m:
            return None
    found = {"system": system, "body": body, "commodity": commodity,
             "lat": lat, "lon": lon, "radius_m": radius}
    spots.append(dict(found))
    return found


def refine_line(commodity, key=""):
    """The one line the prompt shows."""
    line = "Refined %s here, nothing marked - mark it?" % commodity
    return line + (" (%s)" % key if key else "")
