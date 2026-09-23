"""
Reading what Elite Dangerous is writing, as it writes it.

The game leaves two things in its Saved Games folder: Status.json, rewritten
several times a second with where you are, and Journal.*.log, appended to as
things happen. Between them the commander never has to type a coordinate.

None of this is obvious, and most of it was learned the hard way - see
JOURNAL-NOTES.md. The four that cost a release each:

  the sticky EOF flag     a Python file object that has reached the end of a
                          file keeps returning nothing even as the game
                          appends to it. Track the offset, seek to the end
                          and back before every read, unbuffered.

  Status.json timestamps  never skip a read because mtime looks unchanged.
                          Windows does not reliably refresh a directory entry
                          while another process is rewriting the file.

  order of precedence     journal first, Status.json second. Status.json
                          carries the current body and is the fresher of the
                          two, so it gets the last word.

  torn lines              the game can be caught mid-write. Hold an
                          incomplete trailing line back and glue it to the
                          next read, or the event is lost when the rest of
                          it arrives.
"""
# ===========================================================================
#  Elite Dangerous journal reader
#
#  The game writes Status.json (position, several times a second) and
#  Journal.*.log (events, one JSON object per line) into the Saved Games
#  folder. Reading them means the commander never types a coordinate.
# ===========================================================================


import os
import re
import json
import ctypes
from pathlib import Path

import edonline as EDO

# Frontier's own list, owned by edonline so the app, the uploader and the
# server cannot drift apart.
DEPOSIT_TYPES = list(EDO.SURFACE_COMMODITIES)

ED_SUBPATH = os.path.join("Frontier Developments", "Elite Dangerous")

FLAG_LANDED = 1 << 1
FLAG_HAS_LATLONG = 1 << 21
FLAG_IN_SRV = 1 << 26

# Odyssey moved the on-foot state out of Flags and into a second word. A
# tool that reads only Flags cannot tell a commander standing on a planet
# from one who is not there at all.
FLAG2_ON_FOOT = 1 << 0
FLAG2_ON_FOOT_PLANET = 1 << 4
FLAG2_GLIDE = 1 << 12
FLAG2_ON_FOOT_EXTERIOR = 1 << 15
# What the commander is told when the folder is there and cannot be read.
NO_ACCESS = ("Cannot read the Elite Dangerous folder in Saved Games - Windows "
             "is refusing access. If it or anything in it is marked Hidden, "
             "or its permissions were changed, put that right, or pick the "
             "folder in Settings.")
JOURNAL_PATTERN = re.compile(r"^Journal\..*\.log$", re.IGNORECASE)
IDENTITY_EVENTS = {"Commander", "LoadGame"}

# Events carrying facts about the body itself rather than where we are.
BODY_EVENTS = {"Scan", "SAASignalsFound", "SAAScanComplete", "FSSBodySignals"}

# The DSS reports what it finds as a list of signal types. 4.4.1.0 added
# Planetary Mining Locations to what the DSS detects, and the exact Type
# string is not documented anywhere yet, so match on the shape of it and
# keep whatever else turns up.
MINING_SIGNAL = re.compile(r"mining|deposit|resource", re.I)
SYSTEM_EVENTS = {"Location", "FSDJump", "CarrierJump", "SupercruiseExit",
                 "ApproachBody", "Touchdown", "Liftoff", "Embark", "Disembark",
                 "LeaveBody", "SupercruiseEntry"}

# What a mining run's takings are worked out from. Verified against the
# journal reference rather than assumed: MarketSell carries Count, SellPrice,
# TotalSale and AvgPricePaid; Docked carries StationName and StarSystem;
# Touchdown and Liftoff carry OnStation and PlayerControlled; CargoTransfer
# carries a Transfers array of Type / Count / Direction. Shutdown is the one
# here the reference does not document - it is harmless if it never arrives.
RUN_EVENTS = {"MarketSell", "Docked", "Undocked", "Shutdown", "CargoTransfer",
              "Touchdown", "Liftoff"}

# Nothing guarantees this queue is drained. A build that reads the journal
# before the bookkeeping is wired to it would otherwise grow a list all
# session, so the oldest fall off the front rather than the newest being
# refused - eight hours in, what matters is the sale, not the landing.
RUN_QUEUE_MAX = 500

# Surface mining shipped on 2 Sep 2026 and Frontier has not yet published the
# journal schema for it. Rather than guess event names, anything that looks
# mining-related is captured to a log and scanned for a commodity name. If the
# game does name the deposit, the type fills itself in. If it does not, nothing
# breaks, and the log tells us exactly what the game is writing.
MINING_HINT = re.compile(r"rig|deposit|mining|mineral|refin|extract|prospect", re.I)
EVENT_LOG = "journal-mining-events.log"   # set by the app to a real path

# Frontier writes some names as symbols such as "$magnesite_name;"
SYMBOL_PATTERN = re.compile(r"\$?([A-Za-z0-9_\- ]+?)(?:_name)?;?$")


def whole(value):
    """An integer out of the journal, or 0. Never an exception.

    Every number here is somebody else's optional field, and a run's takings
    are not worth losing over a null where a count should have been.
    """
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def number(value):
    """A float out of the journal, or None. Never an exception.

    None and "the field was not written" are the same answer here, which is
    what lets a caller tell a real coordinate from a missing one without
    having to trust a flag bit alongside it.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out else out      # NaN is not a coordinate


def normalise_commodity(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


COMMODITY_LOOKUP = {normalise_commodity(name): name for name in DEPOSIT_TYPES}


def commodity_in(value):
    """Return a known deposit type if this value names one."""
    if not isinstance(value, str) or not value.strip():
        return None
    match = SYMBOL_PATTERN.match(value.strip())
    candidate = match.group(1) if match else value
    return COMMODITY_LOOKUP.get(normalise_commodity(candidate))


def find_commodity(event):
    """Walk an event looking for anything that names a mining commodity."""
    stack = [event]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, (dict, list)):
                    stack.append(value)
                elif key.lower() in ("name", "type", "commodity", "material",
                                     "resource", "name_localised",
                                     "type_localised", "mineral"):
                    hit = commodity_in(value)
                    if hit:
                        return hit
        elif isinstance(node, list):
            stack.extend(node)
    return None


# 4.4.1.0 balances "deposit capacity per density level" and rig "efficiency
# based on deposit density", so density is worth as much as the commodity
# name. The field it arrives in is undocumented, so look for the idea rather
# than a fixed key, the same way commodities are found.
DENSITY_KEYS = ("density", "richness", "quality", "grade", "concentration",
                "abundance", "density_localised", "size")


def find_density(event):
    """Walk an event looking for anything that names a deposit density."""
    stack = [event]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, (dict, list)):
                    stack.append(value)
                    continue
                if key.lower() not in DENSITY_KEYS:
                    continue
                if isinstance(value, str):
                    match = SYMBOL_PATTERN.match(value.strip())
                    candidate = match.group(1) if match else value
                    if EDO.density_rank(candidate) >= 0:
                        return EDO.DENSITY_TIERS[EDO.density_rank(candidate)]
                elif isinstance(value, (int, float)) and key.lower() == "density":
                    # A bare number is a 0-1 or 0-100 scale; bucket it.
                    scale = float(value)
                    if scale > 1.0:
                        scale = scale / 100.0
                    step = min(4, max(0, int(round(scale * 4))))
                    return EDO.DENSITY_TIERS[step]
        elif isinstance(node, list):
            stack.extend(node)
    return None


def _known_saved_games():
    """Ask Windows where Saved Games really is - it can be redirected."""
    if os.name != "nt":
        return None
    try:
        class GUID(ctypes.Structure):
            _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                        ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]
        text = "4C5C32FF-BB9D-43B0-B5B4-2D72E54EAAA4"
        guid = GUID()
        guid.Data1 = int(text[0:8], 16)
        guid.Data2 = int(text[9:13], 16)
        guid.Data3 = int(text[14:18], 16)
        guid.Data4 = (ctypes.c_ubyte * 8)(*bytes.fromhex(text[19:23] + text[24:36]))
        out = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(
                ctypes.byref(guid), 0, None, ctypes.byref(out)) != 0:
            return None
        path = out.value
        ctypes.windll.ole32.CoTaskMemFree(out)
        return path
    except Exception:
        return None


def find_journal_dir(override=None):
    if override and os.path.isdir(override):
        return override
    home = str(Path.home())
    tries = []
    known = _known_saved_games()
    if known:
        tries.append(os.path.join(known, ED_SUBPATH))
    tries.append(os.path.join(home, "Saved Games", ED_SUBPATH))
    tries.append(os.path.join(home, "OneDrive", "Saved Games", ED_SUBPATH))
    for prefix in (".steam/steam", ".local/share/Steam"):
        tries.append(os.path.join(home, prefix, "steamapps/compatdata/359320/pfx",
                                  "drive_c/users/steamuser/Saved Games", ED_SUBPATH))
    for path in tries:
        if os.path.isdir(path):
            return path
    return None


class JournalWatcher:
    """Polled reader. Cheap enough to call straight off the Tk event loop."""

    def __init__(self, override=None):
        self.directory = find_journal_dir(override)
        self.running = False
        self.system = ""
        # Where that system is, and Frontier's own 64-bit id for it. The
        # journal hands both over on every jump and this used to throw them
        # away. Without them the only question worth asking of a database
        # of 400 billion systems - "what is near me" - cannot be asked at
        # all, and names are a bad key: case drifts, spelling drifts, and
        # two commanders typing the same system do not always agree.
        self.star_pos = None           # (x, y, z) in light years
        self.system_address = None     # int, stable, Frontier's own
        self.body = ""
        self.lat = None
        self.lon = None
        self.heading = None
        self.radius_m = None
        self.in_srv = False
        self.landed = False
        # Set when the folder is there but Windows will not let us read it.
        # Said out loud rather than shown as "Elite Dangerous not running",
        # which is what it used to look like - a beta tester lost an evening
        # to a Saved Games folder whose permissions had been changed.
        self.problem = ""
        self.on_foot = False           # Odyssey, from Flags2 - not Flags
        self.gliding = False
        self.game_version = ""         # from Fileheader, e.g. "4.4.1.0"
        self.journal_part = 1
        self.body_signals = {}         # body -> [{Type, Count}] from the DSS
        # Bodies the DSS has actually mapped. An FSS signal list can leave a
        # kind of signal out, so only a DSS map makes "none here" an answer.
        self.body_mapped = set()
        self.body_facts = {}           # body -> radius / temperature / gravity
        self.cmdr = ""                 # from Commander / LoadGame, never typed
        self.fid = ""                  # Frontier ID, needed by Inara
        self.pending_land = None       # a Touchdown waiting to be reported
        self.detected_type = None      # deposit type the game named, if any
        self.detected_density = None   # deposit density the game named, if any
        self.last_event = ""           # newest mining-ish event name seen
        self.unknown_events = set()    # every mining-ish event name this session
        self.pending_market = None     # a Market.json waiting to be shared
        self.market = None             # and the last one seen, kept not drained
        self.docked = False
        self.station = ""              # where you are docked, for the sale
        self.cargo = {}                # what the current vessel is carrying
        self.cargo_vessel = ""         # "Ship" or "SRV" - which hold that is
        self.pending_runs = []         # earnings notes waiting to be taken
        self._journal = None
        self._handle = None
        self._pos = 0
        self._tail = ""
        self._roll_over = False
        self._market_stamp = ""
        self._cargo_seen = {}          # vessel -> last hold, for spotting gains
        self._transfer_credit = {}     # vessel -> counts that arrived by transfer

    @property
    def has_position(self):
        return self.lat is not None and self.lon is not None

    @property
    def where(self):
        if not self.directory:
            return "journal folder not found"
        if self.problem:
            return self.problem
        if not self.running:
            return "Elite Dangerous not running"
        if not self.system:
            return "waiting for the game"
        return f"{self.system} / {self.body}" if self.body else self.system

    def diagnosis(self):
        """One line saying exactly what the reader can and cannot see.

        Written for a beta report. "It isn't detecting me on the surface"
        is not something anyone can act on; this turns it into a line a
        commander can paste, and it names the three things that have each
        been the cause at least once - the folder, whether Status.json is
        being read at all, and what the game is actually saying about where
        the commander is.
        """
        if not self.directory:
            return ("journal folder: NOT FOUND - set it in Settings, it is "
                    "the Elite Dangerous folder inside Saved Games")
        bits = ["folder: %s" % self.directory]
        path = os.path.join(self.directory, "Status.json")
        try:
            raw = open(path, "rb").read().decode("utf-8", errors="replace")
        except FileNotFoundError:
            bits.append("Status.json: NOT IN THAT FOLDER - either it is the "
                        "wrong folder or the game has not been run yet")
            return "  |  ".join(bits)
        except PermissionError:
            bits.append("Status.json: NO ACCESS - Windows is refusing to let "
                        "EDSMT read it (hidden, or permissions changed)")
            return "  |  ".join(bits)
        except OSError as exc:
            bits.append("Status.json: CANNOT READ (%s)" % exc.__class__.__name__)
            return "  |  ".join(bits)
        if not raw.strip():
            bits.append("Status.json: empty this instant - normal if the game "
                        "is running, wrong folder if it stays that way")
            return "  |  ".join(bits)
        try:
            data = json.loads(raw.strip())
        except ValueError:
            bits.append("Status.json: unreadable this instant (normal, the "
                        "game rewrites it constantly)")
            return "  |  ".join(bits)
        flags = whole(data.get("Flags"))
        flags2 = whole(data.get("Flags2"))
        bits.append("Flags: %d / Flags2: %d" % (flags, flags2))
        where = []
        if flags & FLAG_LANDED: where.append("landed")
        if flags & FLAG_IN_SRV: where.append("in the SRV")
        if flags2 & (FLAG2_ON_FOOT | FLAG2_ON_FOOT_PLANET): where.append("on foot")
        if flags2 & FLAG2_GLIDE: where.append("gliding")
        bits.append("state: %s" % (", ".join(where) or "not on a surface"))
        bits.append("body: %s" % (data.get("BodyName") or "none"))
        lat = number(data.get("Latitude"))
        lon = number(data.get("Longitude"))
        bits.append("position: %s" % ("%.4f, %.4f" % (lat, lon)
                                      if lat is not None and lon is not None
                                      else "the game is not writing one"))
        return "  |  ".join(bits)

    def set_directory(self, path):
        """Point the reader at a different Saved Games folder.

        Wired to the Settings page. Everything that tracks position in the
        old file is reset, or the first read of the new one starts at an
        offset that means nothing.
        """
        self.close()
        self.directory = find_journal_dir(path)
        self._journal = None
        self._pos = 0
        self._tail = ""
        self._roll_over = False
        self._market_stamp = ""
        self._cargo_seen = {}
        self._transfer_credit = {}
        self.pending_runs = []
        self.cargo = {}
        self.cargo_vessel = ""
        self.docked = False
        self.station = ""
        self.market = None
        self.system = self.body = ""
        self.star_pos = None
        self.system_address = None
        self.lat = self.lon = self.heading = None
        return self.directory is not None

    def close(self):
        if self._handle:
            try:
                self._handle.close()
            except Exception:
                pass
            self._handle = None

    def poll(self):
        if not self.directory or not os.path.isdir(self.directory):
            self.running = False
            return self
        # Journal first, Status.json second. Status.json carries the current
        # BodyName and is the fresher of the two, so it must have the last
        # word - otherwise an FSDJump replayed from the journal wipes a body
        # the game has already told us we are back at.
        self._read_journal()
        self._read_status()
        self._read_market()
        # The hold last, and the journal first, for the same reason the order
        # matters everywhere else here: a CargoTransfer has to be seen before
        # the rise it causes shows up in Cargo.json, or ten tonnes moved out
        # of the SRV read as ten tonnes freshly dug up.
        self._read_cargo()
        return self

    def _read_status(self):
        path = os.path.join(self.directory, "Status.json")

        # The game rewrites this in place several times a second, so an
        # empty or half-written read is normal - just wait for the next
        # tick. Do NOT skip the read when mtime and size look unchanged:
        # Windows does not reliably refresh the directory entry while
        # another process holds the file, and the app then goes blind.
        try:
            with open(path, "rb") as fh:
                raw = fh.read().decode("utf-8", errors="replace").strip()
        except PermissionError:
            self.problem = NO_ACCESS
            self.running = False
            return
        except OSError:
            self.running = False
            return
        self.problem = ""
        if not raw:
            return
        try:
            data = json.loads(raw)
        except ValueError:
            return

        flags = whole(data.get("Flags"))
        flags2 = whole(data.get("Flags2"))
        self.running = True
        self.landed = bool(flags & FLAG_LANDED)
        self.in_srv = bool(flags & FLAG_IN_SRV)
        self.gliding = bool(flags2 & FLAG2_GLIDE)
        self.on_foot = bool(flags2 & (FLAG2_ON_FOOT | FLAG2_ON_FOOT_PLANET
                                      | FLAG2_ON_FOOT_EXTERIOR))

        # Trust the coordinates, not the flag.
        #
        # This used to refuse a position unless Flags bit 21 was set. Two
        # states on the surface do not satisfy that, and the app went blind
        # in both:
        #
        #   on foot   Odyssey moved that state into Flags2 and Flags can
        #             come through empty, bit 21 included.
        #   the SRV   the frames right after boarding carry the coordinates
        #             before the bit catches up.
        #
        # BodyName kept filling in either way, so the app LOOKED alive while
        # quietly refusing to mark anything - which is exactly how it was
        # reported: "still isn't detecting me on the surface".
        #
        # The game rewrites this file whole several times a second, so a
        # Latitude that is present is a Latitude that is current, and one
        # that is absent means off the surface. That is the signal. The flag
        # is a hint about it, and a hint is not worth going blind for.
        lat = number(data.get("Latitude"))
        lon = number(data.get("Longitude"))
        if lat is not None and lon is not None:
            self.lat, self.lon = lat, lon
            self.heading = number(data.get("Heading")) or 0.0
        else:
            self.lat = self.lon = self.heading = None

        if data.get("BodyName"):
            self.body = str(data["BodyName"])
        if data.get("PlanetRadius"):
            self.radius_m = float(data["PlanetRadius"])
        elif self.body in self.body_facts:
            self.radius_m = self.body_facts[self.body].get("radius_m") or self.radius_m
        if not self.has_position:
            self.detected_type = None
            self.detected_density = None

    def _read_journal(self):
        try:
            files = [os.path.join(self.directory, f)
                     for f in os.listdir(self.directory)
                     if JOURNAL_PATTERN.match(f)]
        except PermissionError:
            self.problem = NO_ACCESS
            return
        except OSError:
            return
        if not files:
            return
        # A journal can be rotated or removed between listing and stat, so a
        # missing file drops out of the running rather than killing the poll.
        stamped = []
        for path in files:
            try:
                stamped.append((os.stat(path).st_mtime, path))
            except OSError:
                continue
        if not stamped:
            return
        newest = max(stamped)[1]

        if self._roll_over and newest == self._journal:
            # The game told us it is starting a new part, but the new file
            # has not appeared yet. Wait for it rather than re-reading this
            # one from the top.
            return
        self._roll_over = False

        if newest != self._journal:
            self.close()
            self._journal = newest
            self._pos = 0
            self._tail = ""
            try:
                self._handle = open(newest, "rb", 0)     # unbuffered - see below
            except OSError:
                self._handle = None
                return

        if self._handle is None:
            return

        try:
            # Reset the sticky EOF flag. Without these two seeks a handle
            # that has once reached the end keeps returning b"" no matter
            # how much the game appends, and the location never updates.
            self._handle.seek(0, os.SEEK_END)
            self._handle.seek(self._pos, os.SEEK_SET)
            chunk = self._handle.read()
            self._pos = self._handle.tell()
        except (OSError, ValueError):
            return

        if not chunk:
            return

        # The game can be caught mid-write, leaving the last line
        # incomplete. Hold it back and glue it to the next read rather than
        # parsing half an event and losing it.
        text = self._tail + chunk.decode("utf-8", errors="replace")
        if text.endswith("\n"):
            self._tail = ""
        else:
            cut = text.rfind("\n")
            if cut == -1:
                self._tail = text
                return
            self._tail, text = text[cut + 1:], text[:cut + 1]
        self._consume(text)

    def _consume(self, text):
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            name = event.get("event")

            # Inara requires the in-game CMDR name, taken from the journal
            # rather than typed, so it always matches exactly.
            if name in IDENTITY_EVENTS:
                if event.get("Name"):
                    self.cmdr = str(event["Name"])
                if event.get("Commander"):
                    self.cmdr = str(event["Commander"])
                if event.get("FID"):
                    self.fid = str(event["FID"])
                continue

            if name == "Fileheader":
                self.game_version = str(event.get("gameversion") or "")
                self.journal_part = int(event.get("part") or 1)
                continue

            # At 500k lines the game closes the journal and opens the next
            # part. Reacting to this rather than waiting for a timestamp to
            # change means not missing the events either side of the split.
            if name == "Continued":
                self.journal_part = int(event.get("Part") or self.journal_part + 1)
                self._roll_over = True
                continue

            if name in BODY_EVENTS:
                self._record_body(name, event)
                continue

            # The sale, the pad and the shutdown are what a run's takings are
            # worked out from, and none of them say where you are - so they
            # are queued for the bookkeeping without touching the position
            # state. Touchdown and Liftoff do both, and are queued lower down,
            # once the position has been read off them.
            if name in RUN_EVENTS and name not in SYSTEM_EVENTS:
                self._note_run(name, event)
                continue

            if name not in SYSTEM_EVENTS:
                if name and MINING_HINT.search(name):
                    self._record_mining_event(name, line, event)
                continue
            if event.get("StarSystem"):
                self.system = str(event["StarSystem"])
            # Not every system event carries these - SupercruiseExit and
            # Touchdown do not - so they are only ever overwritten by an
            # event that actually has them, never blanked by one that
            # does not.
            pos = event.get("StarPos")
            if isinstance(pos, (list, tuple)) and len(pos) == 3:
                try:
                    self.star_pos = (float(pos[0]), float(pos[1]), float(pos[2]))
                except (TypeError, ValueError):
                    pass
            address = event.get("SystemAddress")
            if address is not None:
                try:
                    self.system_address = int(address)
                except (TypeError, ValueError):
                    pass
            body = event.get("Body") or event.get("BodyName")
            if body:
                self.body = str(body)
            if name == "Touchdown" and event.get("Latitude") is not None:
                self.pending_land = {
                    "system": self.system,
                    "body": event.get("Body") or self.body,
                    "lat": event.get("Latitude"),
                    "lon": event.get("Longitude"),
                    "when": event.get("timestamp"),
                }

            if name in RUN_EVENTS:
                self._note_run(name, event)

            if name in ("FSDJump", "CarrierJump", "SupercruiseEntry"):
                self.body = ""

    def _record_body(self, name, event):
        """Remember what the DSS and the scanner said about a body.

        Scan units are the journal's own, not the ones the game UI shows:
        Radius is in metres, SurfaceTemperature in kelvin.
        """
        body = str(event.get("BodyName") or event.get("Body") or "")
        if not body:
            return

        if name == "Scan":
            facts = self.body_facts.setdefault(body, {})
            # Which system it is in, whether you can land on it and how far
            # it is from the arrival star: what Where to land is built from.
            system = str(event.get("StarSystem") or self.system or "")
            if system:
                facts["system"] = system
            if "Landable" in event:
                facts["landable"] = bool(event.get("Landable"))
            if event.get("DistanceFromArrivalLS") is not None:
                try:
                    facts["distance_ls"] = float(event["DistanceFromArrivalLS"])
                except (TypeError, ValueError):
                    pass
            for key, field in (("radius_m", "Radius"),
                               ("temperature_k", "SurfaceTemperature"),
                               ("gravity", "SurfaceGravity")):
                if event.get(field) is not None:
                    try:
                        facts[key] = float(event[field])
                    except (TypeError, ValueError):
                        pass

            # What kind of world it is. Nobody has published which surface
            # deposits favour which bodies, because nobody has been
            # collecting both halves at once - so collect both halves.
            for key, field in (("planet_class", "PlanetClass"),
                               ("atmosphere", "AtmosphereType"),
                               ("volcanism", "Volcanism"),
                               ("terraform", "TerraformState")):
                value = event.get(field)
                if value not in (None, ""):
                    facts[key] = str(value).strip()

            # The journal writes "No volcanism" as an empty string on some
            # bodies and omits the key on others. Both mean the same thing,
            # and "unknown" and "none" are different answers to the question
            # "does volcanism matter", so say which this is.
            if "Volcanism" in event and not str(event.get("Volcanism") or "").strip():
                facts["volcanism"] = "None"

        elif name in ("SAASignalsFound", "FSSBodySignals"):
            signals = event.get("Signals") or []
            if name == "SAASignalsFound":
                self.body_mapped.add(body)
            if isinstance(signals, list):
                self.body_signals[body] = [
                    {"type": str(sig.get("Type_Localised") or sig.get("Type") or ""),
                     "count": int(sig.get("Count") or 0)}
                    for sig in signals if isinstance(sig, dict)]

    def mining_signals(self, body=None):
        """How many mining locations the DSS reported on this body, if any."""
        body = body or self.body
        total = 0
        for sig in self.body_signals.get(body, []):
            if MINING_SIGNAL.search(sig["type"]):
                total += sig["count"]
        return total

    def system_bodies(self, system=None):
        """Every body scanned in a system, landable or not, with what the
        scans said about it and how many mining locations it carries."""
        system = str(system or self.system or "")
        out = []
        for body, facts in self.body_facts.items():
            if str(facts.get("system") or "").lower() != system.lower():
                continue
            profile = self.body_profile(body)
            out.append({
                "body": body,
                "landable": facts.get("landable"),
                "distance_ls": facts.get("distance_ls"),
                "planet_class": profile["planet_class"],
                "volcanism": profile["volcanism"],
                "gravity_g": profile["gravity"],
                "temperature_k": profile["temperature_k"],
                "locations": self.mining_signals(body),
                # A count of 0 means "none" only once the DSS has mapped it.
                "mapped": body in self.body_mapped,
            })
        out.sort(key=lambda b: (b["distance_ls"] is None, b["distance_ls"] or 0))
        return out

    def body_temperature(self, body=None):
        """Surface temperature in kelvin. Rig efficiency depends on it."""
        return self.body_facts.get(body or self.body, {}).get("temperature_k")

    def body_profile(self, body=None):
        """Everything the scan said about this world, ready to file.

        Gravity is converted out of the journal's units into g, which is
        what the game shows you and what anybody comparing two bodies will
        actually mean.
        """
        facts = dict(self.body_facts.get(body or self.body, {}))
        gravity = facts.get("gravity")
        if gravity:
            try:
                # SurfaceGravity is plain m/s^2. Checked against the journal
                # manual's own example rather than assumed: a body of
                # Radius 2011975 m reports SurfaceGravity 2.495225, and
                # g = GM/r^2 for a rocky body that size works out at about
                # 2 m/s^2. So it is m/s^2, and dividing by g0 gives the
                # number the game actually shows you - 0.25g, not 250g.
                facts["gravity_g"] = round(float(gravity) / 9.80665, 3)
            except (TypeError, ValueError):
                pass
        return {
            "planet_class": facts.get("planet_class", ""),
            "gravity": facts.get("gravity_g", ""),
            "atmosphere": facts.get("atmosphere", ""),
            "volcanism": facts.get("volcanism", ""),
            "temperature_k": facts.get("temperature_k", ""),
        }

    def _read_market(self):
        """Pick up Market.json when the game writes a new one.

        The game rewrites this whenever the commodity screen is opened, so the
        timestamp inside it - not mtime - decides whether it is new. Same
        reasoning as Status.json: Windows will lie about the directory entry.
        """
        path = os.path.join(self.directory, "Market.json")
        try:
            with open(path, "rb") as fh:
                raw = fh.read().decode("utf-8", errors="replace").strip()
        except OSError:
            return
        if not raw:
            return
        try:
            data = json.loads(raw)
        except ValueError:
            return
        stamp = str(data.get("timestamp") or "")
        market_id = str(data.get("MarketID") or "")
        token = stamp + "|" + market_id
        if not stamp or token == self._market_stamp:
            return
        self._market_stamp = token
        parsed = EDO.parse_market(data)
        if parsed:
            self.pending_market = parsed
            # pending_market is taken and cleared by whoever shares it. A run
            # still has to be able to ask what the hold in front of it is
            # worth after that has happened, so the market itself is kept.
            self.market = parsed

    # -- what a run is worth -------------------------------------------------

    def drain_runs(self):
        """Hand over everything a run's takings depend on, once.

        Its own queue on purpose. pending_land and pending_market are each
        taken and cleared by a single consumer, so sharing one of those would
        mean whichever ran first starved the other.
        """
        notes, self.pending_runs = self.pending_runs, []
        return notes

    def _queue_run(self, note):
        self.pending_runs.append(note)
        if len(self.pending_runs) > RUN_QUEUE_MAX:
            del self.pending_runs[:-RUN_QUEUE_MAX]

    def _note_run(self, name, event):
        """Queue one thing that bears on what a run made.

        The reader's job is to say what the game did. Deciding where one run
        ends and the next begins belongs with the storage that has to live
        with the answer, so this extracts and queues, and judges nothing.
        """
        note = {"event": name,
                "when": str(event.get("timestamp") or ""),
                "system": self.system,
                "body": self.body,
                "cmdr": self.cmdr}

        if name == "MarketSell":
            count = whole(event.get("Count"))
            price = whole(event.get("SellPrice"))
            note.update({
                "commodity": str(event.get("Type_Localised")
                                 or event.get("Type") or ""),
                "count": count,
                "sell_price": price,
                # TotalSale is the figure the game actually moved, so it
                # wins; count x price only stands in when it is missing.
                "total": whole(event.get("TotalSale")) or count * price,
                # Nothing that came out of the ground was ever paid for, so
                # on a real haul this is zero. It is carried anyway, because
                # a hold of bought goods going over the same counter at the
                # end of the run must not report its purchase price as
                # profit.
                "avg_paid": whole(event.get("AvgPricePaid")),
                "station": self.station,
            })
        elif name == "Docked":
            self.docked = True
            self.station = str(event.get("StationName") or "")
            note["station"] = self.station
            note["system"] = str(event.get("StarSystem") or self.system)
        elif name == "Undocked":
            note["station"] = str(event.get("StationName") or self.station)
            self.docked = False
            self.station = ""
        elif name in ("Touchdown", "Liftoff"):
            note["on_station"] = bool(event.get("OnStation"))
            # Absent means you were flying it. Only an explicit false says
            # the ship put itself down with the commander somewhere else.
            note["player"] = event.get("PlayerControlled") is not False
        elif name == "CargoTransfer":
            self._credit_transfer(event)
            return

        self._queue_run(note)

    def _credit_transfer(self, event):
        """Remember cargo that moved rather than appeared.

        Cargo.json describes one vessel at a time. Move ten tonnes out of the
        SRV and the ship's hold goes up by ten, which on its own looks exactly
        like ten tonnes freshly dug up. CargoTransfer names the direction and
        the amount, so that much is spent against the next rise on the
        receiving side instead of being counted a second time.
        """
        for move in event.get("Transfers") or []:
            if not isinstance(move, dict):
                continue
            where = str(move.get("Direction") or "").strip().lower()
            # tocarrier leaves the ship - nothing arrives anywhere we watch.
            vessel = {"toship": "Ship", "tosrv": "SRV"}.get(where)
            count = whole(move.get("Count"))
            key = EDO.fold(move.get("Type") or "")
            if vessel and key and count > 0:
                owed = self._transfer_credit.setdefault(vessel, {})
                owed[key] = owed.get(key, 0) + count

    def _read_cargo(self):
        """Pick up what is in the hold, and work out what is new in it.

        Rewritten wholesale by the game rather than appended to, so it is read
        whole every tick - and, like Status.json, never skipped on the strength
        of mtime or size. Caught mid-write it either comes back empty or fails
        to parse, and both just mean waiting for the next tick.

        Freshness is decided by the contents, not the timestamp inside. The
        file is a few hundred bytes and the game can rewrite it twice inside
        the same second, which is the resolution that timestamp has.
        """
        path = os.path.join(self.directory, "Cargo.json")
        try:
            with open(path, "rb") as fh:
                raw = fh.read().decode("utf-8", errors="replace").strip()
        except OSError:
            return
        if not raw:
            return
        try:
            data = json.loads(raw)
        except ValueError:
            return
        if not isinstance(data, dict):
            return
        inventory = data.get("Inventory")
        if not isinstance(inventory, list):
            return

        vessel = str(data.get("Vessel") or "Ship")
        # Keyed on the folded symbol the journal itself uses, because that is
        # the vocabulary CargoTransfer speaks too, and the credit it leaves
        # has to find the rise it belongs to. The readable name is carried
        # alongside rather than used as the key.
        counts, labels = {}, {}
        for item in inventory:
            if not isinstance(item, dict):
                continue
            raw_name = str(item.get("Name") or "")
            if not raw_name:
                continue
            key = EDO.fold(raw_name)
            counts[key] = counts.get(key, 0) + whole(item.get("Count"))
            labels[key] = str(item.get("Name_Localised") or raw_name)

        previous = self._cargo_seen.get(vessel)
        self._cargo_seen[vessel] = counts
        self.cargo = {labels[key]: count for key, count in counts.items()}
        self.cargo_vessel = vessel
        if previous is None:
            # First sight of a vessel's hold is the baseline. Reading it as a
            # haul would credit a run with everything already aboard.
            return

        owed = self._transfer_credit.setdefault(vessel, {})
        gained = {}
        for key, count in counts.items():
            rise = count - previous.get(key, 0)
            if rise <= 0:
                continue
            spend = min(owed.get(key, 0), rise)
            if spend:
                owed[key] -= spend
                rise -= spend
            if rise > 0:
                gained[labels[key]] = rise
        if gained:
            self._queue_run({"event": "Cargo", "vessel": vessel,
                             "gained": gained,
                             "when": str(data.get("timestamp") or ""),
                             "system": self.system, "body": self.body,
                             "cmdr": self.cmdr})

    def _record_mining_event(self, name, line, event):
        """Log a surface-mining event and pull a commodity out of it if named.

        The schema is undocumented so far, so this keeps a copy of everything
        the game writes. If Frontier names the deposit, the type fills itself
        in; if not, the log shows exactly what is available to work with.
        """
        self.last_event = name
        if name not in self.unknown_events:
            self.unknown_events.add(name)
            try:
                with open(EVENT_LOG, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except OSError:
                pass

        found = find_commodity(event)
        if found:
            self.detected_type = found

        density = find_density(event)
        if density:
            self.detected_density = density


