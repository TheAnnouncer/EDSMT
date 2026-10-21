"""Bringing finds in from other tools (1.10035). Inbound only.

Four kinds of source, each recognised by what is inside it and never by what
it is called:

    Bookmark database (.db)   a database of bookmarks with one JSON record each
    Share lines               a short code per find, pasted from a chat
    Survey CSV                one row per marked deposit, 38 columns
    Map JSON                  one surveyed body, its deposits in a list

Every reader here was written from the layouts the other tools document or
write; none of their code is used. Where a layout does not say something - the
Survey CSV does not say how it spells an amount, the Map JSON does not carry a
commodity - the reader says so in the preview rather than guessing.

An import never changes a find that is already here. It reads, works out what
is new (same commodity within the duplicate distance of a find already held is
the same find), shows the count, makes a dated backup, and only then adds.

No window code, so every path can be driven by a test.
"""

import base64
import csv
import io
import json
import math
import os
import re
import sqlite3
import time
import zlib
from pathlib import Path

import survey as SV

KIND_BOOKMARKS = "bookmarks"
KIND_LINES = "lines"
KIND_CSV = "csv"
KIND_MAP = "map"

LABELS = {
    KIND_BOOKMARKS: "Bookmark database (.db)",
    KIND_LINES: "Share lines",
    KIND_CSV: "Survey CSV",
    KIND_MAP: "Map JSON",
}

# What the Survey CSV's first row has to contain for it to be that file. The
# file has 38 columns; these are the ones an import reads.
CSV_COLUMNS = ("system", "body", "locationsignalnumber", "planetradiuskm",
               "centerlatitude", "centerlongitude", "commodity",
               "mineralamount", "density", "rigcount", "markerlatitude",
               "markerlongitude", "markercreatedutc")
CSV_REQUIRED = ("system", "body", "commodity", "markerlatitude",
                "markerlongitude")

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TEXT_BYTES = 8 * 1024 * 1024
MAX_CODE = 4000
MAX_NAME = 120

_CODE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9_]{1,31}:"
                   r"([A-Za-z0-9_-]{20,%d}={0,2})" % MAX_CODE)

SKIP_NO_NAME = "no system or body"
SKIP_NO_POSITION = "no position"
SKIP_NO_COMMODITY = "commodity not named"
SKIP_CODE = "commodity given as a code this cannot read"
SKIP_EMPTY_MAP = "map with no deposits"
SKIP_UNREADABLE = "could not be read"
SKIP_LONG = "name too long"


class Source:
    """What was read from a file or a paste, before anything is decided."""

    def __init__(self, kind="", label=""):
        self.kind = kind
        self.label = label
        self.finds = []          # normalised dicts, see _find()
        self.skipped = {}        # reason -> how many
        self.signals = {}        # (system, body, number) -> centre / radius
        self.rows = 0
        self.error = ""
        self.notes = []          # things the format does not say

    def skip(self, reason, count=1):
        self.skipped[reason] = self.skipped.get(reason, 0) + count


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        found = float(str(value).strip()) if not isinstance(value, (int, float)) else float(value)
    except (TypeError, ValueError):
        return None
    return found if math.isfinite(found) else None


def _text(value):
    text = str(value if value is not None else "").strip()
    # A leading apostrophe is how a spreadsheet export keeps a cell that
    # starts with = + - or @ from being read as a formula.
    if len(text) > 1 and text[0] == "'" and text[1] in "=+-@":
        text = text[1:]
    return text


def _label_of(value, labels):
    """The spelling in `labels` that `value` folds to, else ""."""
    wanted = SV.fold(value)
    for label in labels:
        if SV.fold(label) == wanted:
            return label
    return ""


def _amount(value):
    return _label_of(value, SV.AMOUNT_TIERS)


def _density(value):
    return _label_of(value, ("Low", "Medium", "High"))


def _rigs(value, max_rigs):
    found = _number(value)
    if found is None or not 1 <= found <= max_rigs or found != int(found):
        return ""
    return str(int(found))


def _location(value):
    found = _number(value)
    if found is None or found != int(found) or not 1 <= found <= 999:
        return "1"
    return str(int(found))


def _stamp(value):
    """A date from a file as the UTC stamp the records use, or ""."""
    text = _text(value)
    if not text:
        return ""
    cut = text.replace(" ", "T")
    if cut.endswith("Z"):
        cut = cut[:-1]
    for tail in ("+00:00", "-00:00"):
        if cut.endswith(tail):
            cut = cut[:-len(tail)]
    cut = cut.split(".", 1)[0]
    found = SV._epoch(cut + "Z")
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(found)) if found else ""


def _commodity(value):
    """(name, reason): the list's own spelling, or why it was not usable."""
    text = _text(value)
    if not text:
        return "", SKIP_NO_COMMODITY
    known = SV.known_commodity(text)
    if known:
        return known, ""
    if len(text) <= 3 and text.isalpha():
        return "", SKIP_CODE
    if len(text) > 60 or not any(c.isalpha() for c in text):
        return "", SKIP_NO_COMMODITY
    return SV.canonical(text), ""


def _find(source, system, body, commodity, lat, lon, location="1", rigs="",
          amount="", density="", radius_m=None, recorded="", depleted_at="",
          max_rigs=6, default=""):
    """Normalise one find into the source, or count why not."""
    system, body = _text(system), _text(body)
    if not (system and body):
        return source.skip(SKIP_NO_NAME)
    if len(system) > MAX_NAME or len(body) > MAX_NAME:
        return source.skip(SKIP_LONG)
    lat, lon = _number(lat), _number(lon)
    if lat is None or lon is None or not -90.0 <= lat <= 90.0 \
            or not -180.0 <= lon <= 180.0:
        return source.skip(SKIP_NO_POSITION)
    name, reason = _commodity(commodity) if str(commodity or "").strip() \
        else ("", SKIP_NO_COMMODITY)
    radius = _number(radius_m)
    entry = {"system": system, "body": body, "location": _location(location),
             "commodity": name, "rigs": _rigs(rigs, max_rigs),
             "amount": _amount(amount), "density": _density(density),
             "lat": "%.6f" % lat, "lon": "%.6f" % lon,
             "radius_m": radius if radius and radius > 0 else None,
             "recorded": _stamp(recorded), "depleted_at": _stamp(depleted_at),
             "reason": reason}
    source.finds.append(entry)
    return entry


# ---------------------------------------------------------------------------
# Share lines
# ---------------------------------------------------------------------------

def decode_code(code):
    """The record inside one share code, or None.

    A code is URL-safe base64 of zlib-compressed JSON. The size it may
    inflate to is capped, so a crafted code cannot be used to fill memory."""
    try:
        raw = base64.urlsafe_b64decode(code + "=" * (-len(code) % 4))
        data = json.loads(zlib.decompressobj().decompress(raw, 16384).decode("utf-8"))
    except (ValueError, zlib.error, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    for key in ("system", "planet_name", "commodity"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            return None
    if _number(data.get("latitude")) is None or _number(data.get("longitude")) is None:
        return None
    return data


def read_lines(text, max_rigs=6):
    """Every find in pasted text. Chat around the codes is ignored; a code
    that does not decode is counted."""
    source = Source(KIND_LINES, LABELS[KIND_LINES])
    for match in _CODE.finditer(str(text or "")):
        source.rows += 1
        record = decode_code(match.group(1))
        if record is None:
            source.skip(SKIP_UNREADABLE)
            continue
        _find(source, record.get("system"), record.get("planet_name"),
              record.get("commodity"), record.get("latitude"),
              record.get("longitude"), record.get("location_index"),
              record.get("rigs"), record.get("amount"), record.get("density"),
              record.get("planet_radius"), max_rigs=max_rigs)
    if not source.rows:
        source.error = "No share lines found in that text."
    return source


# ---------------------------------------------------------------------------
# Bookmark database
# ---------------------------------------------------------------------------

def read_bookmarks(path, max_rigs=6):
    """The bookmarks in a database file. Opened read-only: nothing in it is
    changed, and a file that is not a database of bookmarks is said so."""
    source = Source(KIND_BOOKMARKS, LABELS[KIND_BOOKMARKS])
    conn = None
    try:
        uri = Path(os.path.abspath(path)).as_uri() + "?mode=ro"
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=5.0)
            conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchall()
        except sqlite3.Error:
            if conn is not None:
                conn.close()
            conn = sqlite3.connect(uri.replace("mode=ro", "immutable=1"),
                                   uri=True, timeout=5.0)
        columns = [r[1] for r in conn.execute("PRAGMA table_info(bookmarks)")]
        if not columns or "data" not in columns:
            source.error = "That database has no bookmarks table this can read."
            return source
        wanted = [c for c in ("system", "planet_name", "commodity",
                              "location_index", "rigs", "depleted_at")
                  if c in columns]
        rows = conn.execute("SELECT %s, data FROM bookmarks ORDER BY rowid"
                            % ", ".join(wanted)).fetchall()
    except (sqlite3.Error, OSError) as problem:
        source.error = "Could not read that database: %s" % problem
        return source
    finally:
        if conn is not None:
            conn.close()
    for row in rows:
        source.rows += 1
        columns_part, blob = dict(zip(wanted, row[:-1])), row[-1]
        try:
            record = json.loads(blob)
        except (TypeError, ValueError):
            record = None
        if not isinstance(record, dict):
            source.skip(SKIP_UNREADABLE)
            continue

        def pick(key, column=None):
            value = record.get(key)
            return columns_part.get(column or key) if value in (None, "") else value
        depleted_at = pick("depleted_at")
        amount = pick("amount")
        if depleted_at:
            amount = "Depleted"
        _find(source, pick("system"), pick("planet_name"), pick("commodity"),
              record.get("latitude"), record.get("longitude"),
              pick("location_index"), pick("rigs"), amount,
              record.get("density"), record.get("planet_radius"),
              recorded=record.get("marked_at"), depleted_at=depleted_at,
              max_rigs=max_rigs)
    if not source.rows:
        source.error = "That database holds no bookmarks."
    return source


# ---------------------------------------------------------------------------
# Survey CSV
# ---------------------------------------------------------------------------

def _head(cell):
    """A header cell folded to letters and digits, so System, system and
    marker_latitude or Marker Latitude all read the same."""
    return re.sub(r"[^a-z0-9]", "", _text(cell).lstrip("\ufeff").lower())


def looks_like_csv(header):
    seen = {_head(cell) for cell in header or ()}
    return all(name in seen for name in CSV_REQUIRED)


def read_csv_text(text, max_rigs=6):
    source = Source(KIND_CSV, LABELS[KIND_CSV])
    reader = csv.reader(io.StringIO(text))
    header = next(reader, [])
    if not looks_like_csv(header):
        source.error = "That is not a survey CSV: its first row lacks " \
                       "System, Body, Commodity and the marker position."
        return source
    names = [_head(cell) for cell in header]
    source.notes.append("The CSV does not say how it spells an amount or a "
                        "density; ones this does not recognise are left blank.")
    for line in reader:
        if not any(cell.strip() for cell in line):
            continue
        source.rows += 1
        row = dict(zip(names, line))
        radius = _number(row.get("planetradiuskm"))
        radius_m = radius * 1000.0 if radius and radius > 0 else None
        commodity = _text(row.get("commodity"))
        lat, lon = row.get("markerlatitude"), row.get("markerlongitude")
        if not commodity and not _text(lat) and not _text(lon):
            source.skip(SKIP_EMPTY_MAP)
            continue
        entry = _find(source, row.get("system"), row.get("body"), commodity,
                      lat, lon, row.get("locationsignalnumber"),
                      row.get("rigcount"), row.get("mineralamount"),
                      row.get("density"), radius_m,
                      recorded=row.get("markercreatedutc"), max_rigs=max_rigs)
        if entry is not None:
            centre = (_number(row.get("centerlatitude")),
                      _number(row.get("centerlongitude")))
            key = (entry["system"], entry["body"], entry["location"])
            if None not in centre and -90 <= centre[0] <= 90 and -180 <= centre[1] <= 180:
                source.signals.setdefault(key, {"lat": centre[0], "lon": centre[1],
                                                "radius_m": radius_m})
    if not source.rows:
        source.error = "That CSV has a header and no rows."
    return source


# ---------------------------------------------------------------------------
# Map JSON
# ---------------------------------------------------------------------------

def read_map_text(text, default_commodity="", max_rigs=6):
    source = Source(KIND_MAP, LABELS[KIND_MAP])
    try:
        data = json.loads(text)
    except ValueError:
        source.error = "That is not valid JSON."
        return source
    if not isinstance(data, dict) or not isinstance(data.get("deposits"), list) \
            or not (data.get("system") or data.get("body")):
        source.error = "That JSON is not a surveyed-body map: it has no " \
                       "system, body and list of deposits."
        return source
    source.notes.append("A map file records where each deposit is and how many "
                        "rigs, not what it is: a deposit is taken as its name "
                        "when that is a commodity, and otherwise as the "
                        "commodity you pick.")
    system, body = data.get("system"), data.get("body")
    radius = _number(data.get("planet_radius"))
    number = _text(data.get("pml_id"))
    number = number if number.isdigit() else "1"
    if not data["deposits"]:
        source.skip(SKIP_EMPTY_MAP)
    for item in data["deposits"]:
        source.rows += 1
        if not isinstance(item, dict):
            source.skip(SKIP_UNREADABLE)
            continue
        named = SV.known_commodity(_text(item.get("name")))
        _find(source, system, body, named or default_commodity,
              item.get("lat"), item.get("lon"), number,
              item.get("rigs"), "", "", radius, max_rigs=max_rigs)
    centre = (_number(data.get("pml_center_lat")), _number(data.get("pml_center_lon")))
    if source.finds and None not in centre and -90 <= centre[0] <= 90 \
            and -180 <= centre[1] <= 180:
        first = source.finds[0]
        source.signals[(first["system"], first["body"], first["location"])] = {
            "lat": centre[0], "lon": centre[1],
            "radius_m": radius if radius and radius > 0 else None}
    return source


# ---------------------------------------------------------------------------
# Reading whatever it is
# ---------------------------------------------------------------------------

EXPECTED = ("a bookmark database (.db), share lines pasted from a chat, a "
            "survey CSV, or a surveyed-body map (.json)")


def _decode(raw):
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return ""


def read_text(text, default_commodity="", max_rigs=6):
    """Pasted or loaded text: Map JSON, a survey CSV or share lines, by what
    it holds."""
    text = str(text or "")
    head = text.lstrip("﻿ \t\r\n")
    if head.startswith("{"):
        return read_map_text(head, default_commodity, max_rigs)
    first = head.split("\n", 1)[0]
    if "," in first and looks_like_csv(next(csv.reader([first]), [])):
        return read_csv_text(head, max_rigs)
    if _CODE.search(text):
        return read_lines(text, max_rigs)
    source = Source("", "")
    source.error = "Not recognised. This reads %s." % EXPECTED
    return source


def read_path(path, default_commodity="", max_rigs=6):
    """A file, by its contents."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            head = handle.read(16)
    except OSError as problem:
        source = Source()
        source.error = "Could not read that file: %s" % problem
        return source
    if head.startswith(b"SQLite format 3\x00"):
        if size > MAX_FILE_BYTES:
            source = Source()
            source.error = "That database is too large to import."
            return source
        return read_bookmarks(path, max_rigs)
    if size > MAX_TEXT_BYTES:
        source = Source()
        source.error = "That file is too large to be one this reads."
        return source
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as problem:
        source = Source()
        source.error = "Could not read that file: %s" % problem
        return source
    return read_text(_decode(raw), default_commodity, max_rigs)


# ---------------------------------------------------------------------------
# Deciding what is new
# ---------------------------------------------------------------------------

def fingerprint(find):
    """The server's own duplicate rule: body, commodity and the position to
    three places."""
    return "|".join([SV.fold(find["system"]), SV.fold(find["body"]),
                     SV.fold(find["commodity"]),
                     "%.3f" % float(find["lat"]), "%.3f" % float(find["lon"])])


class Plan:
    """What an import would do, worked out against the records as they are."""

    def __init__(self, source, label=""):
        self.source = source
        self.label = label or source.label
        self.new = []
        self.known = []
        self.skipped = dict(source.skipped)

    @property
    def counts(self):
        return len(self.new), len(self.known), sum(self.skipped.values())

    def preview(self):
        """"12 new, 3 already known, 2 skipped: no position (1), ..."."""
        new, known, skipped = self.counts
        text = "%d new, %d already known, %d skipped" % (new, known, skipped)
        if skipped:
            text += ": " + ", ".join("%s (%d)" % (reason, count) for reason, count
                                     in sorted(self.skipped.items(),
                                               key=lambda kv: (-kv[1], kv[0])))
        return text + "."


def _radius_for(find, store, held):
    if find["radius_m"]:
        return find["radius_m"]
    for row in store.locations_on(find["system"], find["body"]):
        try:
            found = float(row.get("radius_m") or 0)
        except (TypeError, ValueError):
            found = 0.0
        if found:
            return found
    for other in held:
        if other["radius_m"] and SV.fold(other["system"]) == SV.fold(find["system"]) \
                and SV.fold(other["body"]) == SV.fold(find["body"]):
            return other["radius_m"]
    return None


def _same_find(find, other, radius, within_m):
    """Same commodity, and within the duplicate distance - or, with no size
    for the body, the same to three places."""
    if SV.fold(other["commodity"]) != SV.fold(find["commodity"]):
        return False
    if fingerprint(find) == fingerprint(other):
        return True
    if not radius:
        return False
    try:
        return SV.surface_range_m(float(find["lat"]), float(find["lon"]),
                                  float(other["lat"]), float(other["lon"]),
                                  radius) <= within_m
    except (TypeError, ValueError, KeyError):
        return False


def make_plan(source, store, within_m=100.0, default_commodity=""):
    """Sort a source's finds into new, already known and skipped."""
    plan = Plan(source)
    for find in source.finds:
        find = dict(find)
        if not find["commodity"] and find["reason"] == SKIP_NO_COMMODITY:
            tidy = SV.known_commodity(default_commodity) if default_commodity else ""
            if tidy:
                find["commodity"], find["reason"] = tidy, ""
        if find["reason"] or not find["commodity"]:
            plan.skipped[find["reason"] or SKIP_NO_COMMODITY] = \
                plan.skipped.get(find["reason"] or SKIP_NO_COMMODITY, 0) + 1
            continue
        radius = _radius_for(find, store, plan.new)
        held = (d for d in store.at(find["system"], find["body"]))
        if any(_same_find(find, other, radius, within_m) for other in held) \
                or any(_same_find(find, other, radius, within_m) for other in plan.new):
            plan.known.append(find)
        else:
            plan.new.append(find)
    return plan


def sharing_line(settings, community, always=()):
    """What the preview says about sharing, from the settings that decide it.

    `always` is the app's list of settings that are on whatever a file says.
    Sharing is on when community_auto_share is one of those or is set, and
    only goes anywhere when the link is ready."""
    on = "community_auto_share" in always or bool(
        (settings or {}).get("community_auto_share", True))
    if not on:
        return "These finds will stay on this PC: sharing is off."
    if community is None or not getattr(community, "ready", False):
        return ("These finds will stay on this PC for now: the community link "
                "is not ready.")
    named = bool(getattr(community, "share_name", True))
    return ("These finds will be shared with the community map, as sharing "
            "is always on - %s." % ("under your CMDR name" if named
                                    else "without your name"))


def apply(plan, store, backup_folder, within_m=100.0):
    """Add a plan's new finds, after a dated backup of everything held.

    Returns a result dict: ok, reason, backup (the zip's path), taken,
    signals and records (the deposit rows added, for sharing). If the backup
    cannot be written nothing is imported: the one moment somebody else's
    file is allowed to change yours is the moment you must be able to undo
    it."""
    result = {"ok": False, "reason": "", "backup": "", "taken": 0,
              "signals": 0, "records": []}
    if not plan.new:
        result["ok"] = True
        result["reason"] = "Nothing new to add."
        return result
    try:
        backup, _count = store.backup_to(backup_folder)
    except (OSError, ValueError) as problem:
        result["reason"] = ("Nothing was imported: the backup that comes "
                            "first could not be written (%s)." % problem)
        return result
    result["backup"] = backup or ""
    note = SV.stamp_note("", "Imported from %s" % plan.label)
    made = set()
    for find in plan.new:
        depleted = SV.is_depleted(find["amount"])
        stored = store.add_deposit(
            system=find["system"], body=find["body"], location=find["location"],
            commodity=find["commodity"], rigs=find["rigs"], density=find["density"],
            amount=find["amount"], lat=find["lat"], lon=find["lon"],
            status=SV.STATUS_REPORTED, notes=note,
            recorded=find["recorded"],
            depleted_at=(find["depleted_at"] or find["recorded"] or SV.utc_now())
            if depleted else "")
        result["records"].append(stored)
        result["taken"] += 1
        made.add((find["system"], find["body"], find["location"]))
    # A signal row so the body remembers the finds are in one. An existing
    # signal is never touched: an import must not move a centre somebody
    # stood on and logged themselves.
    for system, body, number in sorted(made):
        if store.location(system, body, number) is not None:
            continue
        centre = plan.source.signals.get((system, body, number)) or {}
        radius = centre.get("radius_m") or next(
            (f["radius_m"] for f in plan.new if f["radius_m"]
             and (f["system"], f["body"]) == (system, body)), None)
        store.set_location(system, body, number, lat=centre.get("lat"),
                           lon=centre.get("lon"), radius_m=radius, notes=note)
        result["signals"] += 1
    result["ok"] = True
    return result


def community_rows(records):
    """Deposit rows as the community upload takes them, for finds that have a
    position. The galactic position is left off: it describes where the
    commander is, not where an imported find is."""
    out = []
    for record in records:
        try:
            lat, lon = float(record["lat"]), float(record["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        out.append({
            "system": record["system"], "planet": record["body"],
            "spot": record["location"], "type": record["commodity"],
            "rigs": int(float(record.get("rigs") or 0)), "lat": lat, "lon": lon,
            "density": record.get("density") or "",
            "amount": record.get("amount") or "",
            "status": record.get("status") or SV.STATUS_REPORTED,
            "planet_class": "", "gravity": None, "atmosphere": "",
            "volcanism": "", "temperature_k": None, "notes": ""})
    return out


def summary(result, plan):
    """The one line said after an import."""
    if not result["ok"]:
        return result["reason"]
    if not result["taken"]:
        return "Nothing new to add - %s" % plan.preview()
    bits = ["Imported %d find(s) from %s" % (result["taken"], plan.label)]
    if result["signals"]:
        bits.append("%d mining location(s)" % result["signals"])
    new, known, skipped = plan.counts
    if known:
        bits.append("%d already known, left alone" % known)
    if skipped:
        bits.append("%d skipped" % skipped)
    if result["backup"]:
        bits.append("your records were backed up to %s first"
                    % os.path.basename(result["backup"]))
    return ". ".join(bits) + "."
