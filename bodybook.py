"""Every body EDSMT has been told about, per system, kept on disk.

Where to land used to know only what the journal file being read had said.
A system honked last week, in an earlier game session, came up as "0 bodies
scanned" (7 Oct 2026, in the commander's own carrier system, which he had
scanned twice). Bodies are now remembered three ways:

  - as the journal describes them, the moment it does;
  - from every older journal on the PC, read once in the background;
  - from the public body database, through the EDSMT server, for systems
    other commanders have scanned.

The journal always wins: a body it has described is never overwritten by
the public database, only filled in where the journal said nothing.

SQLite, because the older journals alone can describe tens of thousands of
bodies and Where to land wants one system's worth at a time. The file is a
cache - everything in it can be read again from the journals - so it is
left out of backups.
"""
import json
import os
import re
import sqlite3
import threading
import time

import journal as JN

FILE_NAME = "bodies.db"
SOURCE_JOURNAL = "journal"
SOURCE_PUBLIC = "public"
# The events a body is read from. The game writes "event":"Scan" with no
# space; anything else that writes a journal may not, so either is taken.
BODY_EVENTS = re.compile(
    rb'"event"\s*:\s*"(?:Scan|SAASignalsFound|FSSBodySignals|FSSDiscoveryScan)"')
SYSTEM_EVENTS = ("FSDJump", "Location", "CarrierJump")
JOURNAL_NAME = re.compile(r"^Journal\..*\.log$", re.I)
# Older journals read between commits.
BACKFILL_BATCH = 25


def system_key(system):
    return str(system or "").strip().lower()


class BodyBook:
    """The bodies of every system seen, on disk. Safe across threads."""

    def __init__(self, folder, name=FILE_NAME):
        self.path = os.path.join(str(folder or "."), name)
        self._lock = threading.RLock()
        self._conn = None
        # Moves on every write, so a window can tell when to redraw.
        self.revision = 0

    # -- storage -------------------------------------------------------

    def _db(self):
        if self._conn is None:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            conn = sqlite3.connect(self.path, timeout=10,
                                   check_same_thread=False)
            # A cache, written in bursts by the older-journal read: WAL and
            # NORMAL sync keep a thousand small commits from each waiting on
            # the disk. Nothing here is the only copy of anything.
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
            except sqlite3.Error:
                pass
            conn.execute("""CREATE TABLE IF NOT EXISTS bodies (
                system_key TEXT NOT NULL, system TEXT NOT NULL,
                body TEXT NOT NULL, facts TEXT NOT NULL DEFAULT '{}',
                signals TEXT, mapped INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT 'journal',
                updated REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (system_key, body))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS systems (
                system_key TEXT PRIMARY KEY, system TEXT NOT NULL,
                address INTEGER, body_count INTEGER, public_at REAL,
                updated REAL NOT NULL DEFAULT 0)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS files (
                name TEXT PRIMARY KEY, size INTEGER NOT NULL,
                done REAL NOT NULL)""")
            conn.commit()
            self._conn = conn
        return self._conn

    def close(self):
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except sqlite3.Error:
                    pass
                self._conn = None

    # -- writing -------------------------------------------------------

    def put(self, system, body, facts=None, signals=None, mapped=False,
            source=SOURCE_JOURNAL, when=None, commit=True):
        """Lay what is known about one body over what was known before.

        A journal row is never overwritten by a public one: the public
        facts only fill keys the journal left empty. True if anything
        changed.
        """
        system, body = str(system or "").strip(), str(body or "").strip()
        if not system or not body:
            return False
        when = time.time() if when is None else when
        facts = {k: v for k, v in (facts or {}).items()
                 if k not in ("system", "source") and v is not None}
        with self._lock:
            db = self._db()
            row = db.execute("SELECT facts, signals, mapped, source FROM bodies "
                             "WHERE system_key = ? AND body = ?",
                             (system_key(system), body)).fetchone()
            if row is None:
                merged, old_signals, old_mapped, old_source = {}, None, 0, source
            else:
                merged = _loads(row[0], {})
                old_signals, old_mapped, old_source = row[1], row[2], row[3]
            before = (json.dumps(merged, sort_keys=True), old_signals,
                      int(old_mapped or 0), old_source)
            if source == SOURCE_PUBLIC and old_source == SOURCE_JOURNAL and row is not None:
                for key, value in facts.items():
                    merged.setdefault(key, value)
                kept_source = SOURCE_JOURNAL
            else:
                merged.update(facts)
                kept_source = source if row is None or source == SOURCE_JOURNAL \
                    else old_source
            new_signals = old_signals
            if signals is not None and (source == SOURCE_JOURNAL
                                        or old_signals is None
                                        or kept_source != SOURCE_JOURNAL):
                new_signals = json.dumps(signals)
            new_mapped = 1 if (mapped or old_mapped) else 0
            after = (json.dumps(merged, sort_keys=True), new_signals,
                     new_mapped, kept_source)
            if after == before and row is not None:
                return False
            db.execute("""INSERT INTO bodies
                (system_key, system, body, facts, signals, mapped, source, updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(system_key, body) DO UPDATE SET
                    system = excluded.system, facts = excluded.facts,
                    signals = excluded.signals, mapped = excluded.mapped,
                    source = excluded.source, updated = excluded.updated""",
                       (system_key(system), system, body, after[0], new_signals,
                        new_mapped, kept_source, when))
            self._touch_system(db, system, when=when)
            if commit:
                db.commit()
            self.revision += 1
            return True

    def _touch_system(self, db, system, address=None, body_count=None,
                      public_at=None, when=None):
        when = time.time() if when is None else when
        db.execute("""INSERT INTO systems (system_key, system, address,
                          body_count, public_at, updated)
                      VALUES (?, ?, ?, ?, ?, ?)
                      ON CONFLICT(system_key) DO UPDATE SET
                          system = excluded.system,
                          address = COALESCE(excluded.address, systems.address),
                          body_count = COALESCE(excluded.body_count, systems.body_count),
                          public_at = COALESCE(excluded.public_at, systems.public_at),
                          updated = excluded.updated""",
                   (system_key(system), system, address, body_count, public_at, when))

    def note_system(self, system, address=None, body_count=None,
                    public_at=None, when=None):
        """What is known about a system as a whole: its address, how many
        bodies the honk counted, when the public database was last asked."""
        if not str(system or "").strip():
            return
        with self._lock:
            db = self._db()
            self._touch_system(db, str(system).strip(), address, body_count,
                               public_at, when)
            db.commit()
            self.revision += 1

    def commit(self):
        with self._lock:
            if self._conn is not None:
                self._conn.commit()

    # -- reading -------------------------------------------------------

    def bodies(self, system):
        """{body: {"facts", "signals", "mapped", "source"}} for one system."""
        with self._lock:
            rows = self._db().execute(
                "SELECT body, facts, signals, mapped, source FROM bodies "
                "WHERE system_key = ?", (system_key(system),)).fetchall()
        out = {}
        for body, facts, signals, mapped, source in rows:
            out[body] = {"facts": _loads(facts, {}),
                         "signals": _loads(signals, None),
                         "mapped": bool(mapped), "source": source}
        return out

    def system(self, system):
        """{"address", "body_count", "public_at"} or None."""
        with self._lock:
            row = self._db().execute(
                "SELECT address, body_count, public_at FROM systems "
                "WHERE system_key = ?", (system_key(system),)).fetchone()
        if row is None:
            return None
        return {"address": row[0], "body_count": row[1], "public_at": row[2]}

    def counts(self):
        """(systems, bodies) remembered."""
        with self._lock:
            db = self._db()
            bodies = db.execute("SELECT COUNT(*) FROM bodies").fetchone()[0]
            systems = db.execute("SELECT COUNT(DISTINCT system_key) FROM bodies"
                                 ).fetchone()[0]
        return systems, bodies

    # -- the older journals --------------------------------------------

    def file_done(self, name, size):
        with self._lock:
            row = self._db().execute("SELECT size FROM files WHERE name = ?",
                                     (name,)).fetchone()
        return row is not None and row[0] == size

    def mark_file(self, name, size, when=None, commit=True):
        with self._lock:
            db = self._db()
            db.execute("INSERT OR REPLACE INTO files (name, size, done) "
                       "VALUES (?, ?, ?)",
                       (name, size, time.time() if when is None else when))
            if commit:
                db.commit()


def _loads(text, default):
    if text in (None, ""):
        return default
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return default


def journal_files(folder):
    """The journal files in a folder, newest first, as (path, name, size)."""
    try:
        names = [n for n in os.listdir(folder) if JOURNAL_NAME.match(n)]
    except OSError:
        return []
    found = []
    for name in names:
        path = os.path.join(folder, name)
        try:
            st = os.stat(path)
        except OSError:
            continue
        found.append((st.st_mtime, path, name, st.st_size))
    found.sort(reverse=True)
    return [(path, name, size) for _mtime, path, name, size in found]


def read_journal_file(book, path, name=None, size=None, when=None, commit=True):
    """File every body one journal describes. How many bodies were written.

    Which system a body is in comes from the event itself where it says so,
    and otherwise from the last jump or location before it - older journals
    did not put the system on a Scan. A file without a single body event in
    it is skipped without parsing a line.
    """
    with open(path, "rb") as handle:
        data = handle.read()
    wrote = 0
    if BODY_EVENTS.search(data):
        system = ""
        for raw in data.splitlines():
            if b'"event"' not in raw:
                continue
            try:
                event = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            kind = event.get("event")
            if kind in SYSTEM_EVENTS:
                system = str(event.get("StarSystem") or system)
                continue
            if kind == "FSSDiscoveryScan":
                where = str(event.get("SystemName") or system)
                count = event.get("BodyCount")
                if where and isinstance(count, int):
                    book.note_system(where, address=event.get("SystemAddress"),
                                     body_count=count, when=when)
                continue
            if kind == "Scan":
                body, facts = JN.scan_facts(event, system)
                where = facts.get("system") or system
                if body and where and book.put(where, body, facts, commit=False,
                                               when=when):
                    wrote += 1
            elif kind in ("SAASignalsFound", "FSSBodySignals"):
                body = str(event.get("BodyName") or "")
                rows = JN.signal_rows(event)
                where = str(event.get("StarSystem") or system)
                if body and where and book.put(
                        where, body, None, signals=rows,
                        mapped=(kind == "SAASignalsFound"), commit=False,
                        when=when):
                    wrote += 1
    book.mark_file(name or os.path.basename(path),
                   os.path.getsize(path) if size is None else size, when=when,
                   commit=False)
    if commit:
        book.commit()
    return wrote


def backfill(book, folder, skip=(), stop=None, progress=None):
    """Read every older journal not read before, newest first.

    A file is read again only when its size has changed. `stop` is a
    threading.Event that ends the run between files; `progress(done,
    total)` is told as it goes. (files read, bodies filed). Never raises.
    """
    files = journal_files(folder)
    todo = [(path, name, size) for path, name, size in files
            if name not in skip and not book.file_done(name, size)]
    read = filed = 0
    for path, name, size in todo:
        if stop is not None and stop.is_set():
            break
        try:
            filed += read_journal_file(book, path, name, size, commit=False)
            read += 1
        except Exception:
            continue
        if read % BACKFILL_BATCH == 0:
            book.commit()
        if progress is not None:
            try:
                progress(read, len(todo))
            except Exception:
                pass
    book.commit()
    return read, filed


def seed_watcher(watcher, book, system):
    """Put what is remembered about a system into the journal watcher, under
    what the journal itself has said. How many bodies were added or filled."""
    if not system:
        return 0
    added = 0
    for body, known in book.bodies(system).items():
        facts = watcher.body_facts.get(body)
        if facts is None:
            facts = dict(known["facts"])
            facts["system"] = system
            if known["source"] != SOURCE_JOURNAL:
                facts["source"] = known["source"]
            watcher.body_facts[body] = facts
            added += 1
        else:
            for key, value in known["facts"].items():
                facts.setdefault(key, value)
        if known["signals"] is not None and body not in watcher.body_signals:
            watcher.body_signals[body] = list(known["signals"])
        if known["mapped"]:
            watcher.body_mapped.add(body)
    return added


def remember_watcher(watcher, book, system, seen=None):
    """File what the journal has said about this system's bodies. `seen`
    is a dict this keeps, so an unchanged body is not written again.
    How many were written."""
    if not system:
        return 0
    seen = {} if seen is None else seen
    wrote = 0
    for body, facts in list(watcher.body_facts.items()):
        if system_key(facts.get("system")) != system_key(system):
            continue
        signals = watcher.body_signals.get(body)
        mapped = body in watcher.body_mapped
        source = facts.get("source") or SOURCE_JOURNAL
        stamp = json.dumps([facts, signals, mapped], sort_keys=True, default=str)
        if seen.get(body) == stamp:
            continue
        seen[body] = stamp
        if book.put(system, body, facts, signals=signals, mapped=mapped,
                    source=source, commit=False):
            wrote += 1
    if wrote:
        book.commit()
    return wrote


def public_rows_to_facts(row):
    """One body from the server's /v1/bodies answer, as watcher facts."""
    facts = {}
    for key, field in (("landable", "landable"), ("distance_ls", "distance_ls"),
                       ("planet_class", "planet_class"), ("volcanism", "volcanism"),
                       ("temperature_k", "temperature_k"), ("atmosphere", "atmosphere"),
                       ("terraform", "terraform")):
        value = row.get(field)
        if value not in (None, ""):
            facts[key] = value
    # The watcher keeps the journal's units: gravity in m/s2, radius in m.
    try:
        if row.get("gravity_g") is not None:
            facts["gravity"] = float(row["gravity_g"]) * 9.80665
    except (TypeError, ValueError):
        pass
    try:
        if row.get("radius_km") is not None:
            facts["radius_m"] = float(row["radius_km"]) * 1000.0
    except (TypeError, ValueError):
        pass
    signals = None
    if row.get("mining_locations") is not None:
        try:
            signals = [{"type": "Planetary mining location",
                        "count": int(row["mining_locations"])}]
        except (TypeError, ValueError):
            signals = None
    return facts, signals
