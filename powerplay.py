"""Powerplay from the commander's own journal. No server needed.

What the journal says, kept:

  - the pledge: Powerplay (written at login), PowerplayJoin / Leave / Defect,
    and the Power on every PowerplayMerits;
  - the Powerplay fields of every system the commander has been in -
    ControllingPower, PowerplayState, Powers, the progress and the cycle's
    reinforcement and undermining - with where the system is, so the 20 and
    30 light year ranges can be measured offline;
  - where mined goods came from, and whether they went through a fleet
    carrier or were bought, because merits are paid on mined cargo only.

The rules:

  Expand      mine in a Stronghold or Fortified system of your Power and
              sell in an UNOCCUPIED system within its reach: 30 Ly from a
              Stronghold, 20 Ly from a Fortified system.
  Reinforce   mine in a system your Power controls and sell in that same
              system.
  Undermine   mine in a rival Power's system that is within range of your
              Fortified or Stronghold systems, and sell in that same system.
              Range is a switch: with it off, any rival system counts.
  Nothing     anything else - and always for goods that were bought, or that
              passed through a fleet carrier.

Frontier publish no formula for merits, so this module never invents one:
the estimate comes from what survey.MeritRate has learnt from the
commander's own sales, and says nothing until it has learnt enough.
"""
import json
import math
import os
import tempfile
import threading

import survey as SV

POWERPLAY_FILE = "powerplay.json"

POWERS = ("Aisling Duval", "Archon Delaine", "A. Lavigny-Duval",
          "Denton Patreus", "Edmund Mahon", "Felicia Winters", "Jerome Archer",
          "Li Yong-Rui", "Nakato Kaine", "Pranav Antal", "Yuri Grom",
          "Zemina Torval")
STATES = ("Unoccupied", "Exploited", "Fortified", "Stronghold")
# Light years: from a Stronghold, and from a Fortified system.
REACH_LY = {"Stronghold": 30.0, "Fortified": 20.0}
CONTROLLED = ("Exploited", "Fortified", "Stronghold")

EXPAND, REINFORCE, UNDERMINE = "Expand", "Reinforce", "Undermine"
NOTHING, UNKNOWN = "Nothing", "Unknown"
COUNTS = (EXPAND, REINFORCE, UNDERMINE)

LEDGER_MAX_RUNS = 400           # entries kept per commodity's mined queue
SYSTEMS_MAX = 6000

# Journal events the reader hands over, and what each is for.
PLEDGE_EVENTS = ("Powerplay", "PowerplayJoin", "PowerplayLeave",
                 "PowerplayDefect", "PowerplayMerits", "PowerplayRank")
SYSTEM_EVENTS = ("FSDJump", "Location", "CarrierJump")
LEDGER_EVENTS = ("MiningRefined", "CargoTransfer", "MarketBuy", "MarketSell")
POWER_EVENTS = frozenset(PLEDGE_EVENTS + SYSTEM_EVENTS + LEDGER_EVENTS
                         + ("Docked", "Undocked"))


def key_of(system):
    return " ".join(str(system or "").lower().split())


def _whole(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _float(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out else out


def distance(a, b):
    """Light years between two (x, y, z) points, or None."""
    if not a or not b or len(a) != 3 or len(b) != 3:
        return None
    try:
        return math.sqrt(sum((float(p) - float(q)) ** 2 for p, q in zip(a, b)))
    except (TypeError, ValueError):
        return None


def clean_state(text):
    """The game's PowerplayState as one of STATES, or "" when it is not."""
    word = str(text or "").strip().lower()
    for state in STATES:
        if word == state.lower():
            return state
    return ""


# -- reading a journal event ---------------------------------------------------------

def system_note(event, system=""):
    """A FSDJump / Location / CarrierJump as a Powerplay system note, or
    None when it says nothing about Powerplay. The position is kept either
    way: it is what the ranges are measured from."""
    if not isinstance(event, dict):
        return None
    name = str(event.get("StarSystem") or system or "").strip()
    if not name:
        return None
    state = clean_state(event.get("PowerplayState"))
    power = str(event.get("ControllingPower") or "").strip()
    powers = [str(p) for p in event.get("Powers") or [] if p]
    if not (state or power or powers):
        return None
    pos = event.get("StarPos")
    where = None
    if isinstance(pos, (list, tuple)) and len(pos) == 3:
        try:
            where = [float(pos[0]), float(pos[1]), float(pos[2])]
        except (TypeError, ValueError):
            where = None
    return {"kind": "system", "system": name,
            "address": event.get("SystemAddress"), "pos": where,
            "power": power, "state": state, "powers": powers,
            "progress": _float(event.get("PowerplayStateControlProgress")),
            "reinforcement": _whole(event.get("PowerplayStateReinforcement"))
            if event.get("PowerplayStateReinforcement") is not None else None,
            "undermining": _whole(event.get("PowerplayStateUndermining"))
            if event.get("PowerplayStateUndermining") is not None else None,
            "when": str(event.get("timestamp") or "")}


def pledge_note(event):
    """Powerplay / Join / Leave / Defect / Merits / Rank as a pledge note."""
    name = event.get("event")
    when = str(event.get("timestamp") or "")
    if name == "PowerplayLeave":
        return {"kind": "pledge", "event": name, "power": "", "left": True,
                "when": when}
    power = str(event.get("Power") or event.get("ToPower") or "").strip()
    note = {"kind": "pledge", "event": name, "power": power, "when": when}
    if name == "Powerplay":
        note["rank"] = event.get("Rank")
        note["merits"] = event.get("Merits")
    elif name == "PowerplayMerits":
        note["merits"] = event.get("TotalMerits")
        note["gained"] = event.get("MeritsGained")
    elif name == "PowerplayRank":
        note["rank"] = event.get("Rank")
    return note


# -- the book --------------------------------------------------------------------------

class PowerBook:
    """The pledge, the Powerplay record of every system seen, and where mined
    goods came from. Kept on disk. Safe across threads. Never raises."""

    def __init__(self, folder=None):
        self.path = os.path.join(folder, POWERPLAY_FILE) if folder else ""
        self._lock = threading.RLock()
        self.me = {"power": "", "rank": None, "merits": None, "when": ""}
        self.systems = {}
        self.files = {}
        # Per commodity (folded): a queue of [system, tonnes] mined, oldest
        # first; tonnes that came off a fleet carrier; tonnes bought.
        self.mined = {}
        self.carrier = {}
        self.bought = {}
        self.sales = []
        self.mark = [0.0, 0]
        self.range_rule = True
        self.dirty = False
        self.revision = 0
        self.load()

    # -- storage -------------------------------------------------------

    def load(self):
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        with self._lock:
            me = data.get("me")
            if isinstance(me, dict):
                self.me.update({k: me.get(k) for k in self.me if k in me})
            systems = data.get("systems")
            if isinstance(systems, dict):
                self.systems = {str(k): v for k, v in systems.items()
                                if isinstance(v, dict) and v.get("system")}
            files = data.get("files")
            self.files = dict(files) if isinstance(files, dict) else {}
            ledger = data.get("ledger")
            if isinstance(ledger, dict):
                for field in ("mined", "carrier", "bought"):
                    value = ledger.get(field)
                    if isinstance(value, dict):
                        setattr(self, field, value)
                sales = ledger.get("sales")
                self.sales = [s for s in sales if isinstance(s, dict)][-40:] \
                    if isinstance(sales, list) else []
                mark = ledger.get("mark")
                if isinstance(mark, list) and len(mark) == 2:
                    self.mark = [float(mark[0] or 0), int(mark[1] or 0)]
            if isinstance(data.get("range_rule"), bool):
                self.range_rule = data["range_rule"]

    def save(self):
        if not self.path:
            return False
        with self._lock:
            data = {"me": dict(self.me), "systems": dict(self.systems),
                    "files": dict(self.files), "range_rule": self.range_rule,
                    "ledger": {"mined": self.mined, "carrier": self.carrier,
                               "bought": self.bought, "sales": self.sales[-40:],
                               "mark": list(self.mark)}}
            self.dirty = False
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            handle, temp = tempfile.mkstemp(dir=os.path.dirname(self.path) or ".",
                                            prefix="powerplay-", suffix=".tmp")
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                json.dump(data, out)
            os.replace(temp, self.path)
            return True
        except (OSError, TypeError, ValueError):
            self.dirty = True
            return False

    # -- taking notes in ---------------------------------------------------

    def observe(self, note):
        """One note from the journal reader. True when it changed anything."""
        if not isinstance(note, dict):
            return False
        kind = note.get("kind")
        try:
            with self._lock:
                if kind == "system":
                    changed = self._system(note)
                elif kind == "pledge":
                    changed = self._pledge(note)
                elif kind in ("mined", "transfer", "buy", "sale"):
                    changed = self._ledger(note)
                else:
                    changed = False
                if changed:
                    self.dirty = True
                    self.revision += 1
                return changed
        except (TypeError, ValueError, KeyError):
            return False

    def _system(self, note):
        name = str(note.get("system") or "").strip()
        if not name:
            return False
        key = key_of(name)
        old = self.systems.get(key)
        at = SV._epoch(note.get("when")) or 0
        if old is not None and at and at < (SV._epoch(old.get("seen")) or 0):
            return False
        entry = {"system": name, "address": note.get("address"),
                 "power": str(note.get("power") or ""),
                 "state": clean_state(note.get("state")),
                 "powers": list(note.get("powers") or []),
                 "progress": note.get("progress"),
                 "reinforcement": note.get("reinforcement"),
                 "undermining": note.get("undermining"),
                 "seen": str(note.get("when") or "")}
        pos = note.get("pos")
        if pos and len(pos) == 3:
            entry["x"], entry["y"], entry["z"] = (float(v) for v in pos)
        elif old is not None:
            for axis in ("x", "y", "z"):
                if old.get(axis) is not None:
                    entry[axis] = old[axis]
        if old == entry:
            return False
        if old is None and len(self.systems) >= SYSTEMS_MAX:
            oldest = sorted(self.systems, key=lambda k: SV._epoch(
                self.systems[k].get("seen")) or 0)[:len(self.systems) - SYSTEMS_MAX + 1]
            for stale in oldest:
                del self.systems[stale]
        self.systems[key] = entry
        return True

    def _pledge(self, note):
        at = SV._epoch(note.get("when")) or 0
        if at and at < (SV._epoch(self.me.get("when")) or 0):
            return False
        before = dict(self.me)
        if note.get("left"):
            self.me = {"power": "", "rank": None, "merits": None,
                       "when": str(note.get("when") or "")}
            return self.me != before
        power = str(note.get("power") or "")
        if power and power != self.me.get("power"):
            # A different Power is a different pledge: the old rank and merits
            # were the other one's.
            self.me = {"power": power, "rank": None, "merits": None, "when": ""}
        if power:
            for field in ("rank", "merits"):
                if note.get(field) is not None:
                    self.me[field] = note[field]
            self.me["when"] = str(note.get("when") or self.me.get("when") or "")
        return self.me != before

    # -- the ledger: where mined goods came from ----------------------------

    def _ledger(self, note):
        stamp = SV._epoch(note.get("when")) or 0.0
        seq = _whole(note.get("seq"))
        if (stamp, seq) <= (self.mark[0], self.mark[1]):
            return False
        self.mark = [stamp, seq]
        comm = SV.fold(note.get("commodity"))
        kind = note.get("kind")
        count = _whole(note.get("count"))
        if not comm:
            return True
        if kind == "mined":
            queue = self.mined.setdefault(comm, [])
            system = str(note.get("system") or "")
            if queue and queue[-1][0] == system:
                queue[-1][1] += 1
            else:
                queue.append([system, 1])
            del queue[:-LEDGER_MAX_RUNS]
        elif kind == "transfer":
            # Cargo moves only at a carrier when docked; the Rhino's own
            # tonnes come aboard from the SRV with the ship in flight or
            # landed. tocarrier takes it off; toship while docked brings it
            # back - and a tonne that has been through a carrier is no longer
            # a mined tonne.
            way = str(note.get("direction") or "").lower()
            if way == "toship" and note.get("docked") and count > 0:
                self.carrier[comm] = self.carrier.get(comm, 0) + count
            elif way == "tocarrier" and count > 0:
                self._take_off_queue(comm, count)
        elif kind == "buy":
            if count > 0:
                self.bought[comm] = self.bought.get(comm, 0) + count
        elif kind == "sale":
            if _whole(note.get("avg_paid")) > 0:
                self.bought[comm] = max(0, self.bought.get(comm, 0) - count)
            else:
                self._take_off_queue(comm, count)
            self.sales.append({
                "when": str(note.get("when") or ""), "commodity": comm,
                "name": str(note.get("name") or ""), "count": count,
                "avg_paid": _whole(note.get("avg_paid")),
                "total": _whole(note.get("total")),
                "system": str(note.get("system") or ""),
                "station": str(note.get("station") or "")})
            del self.sales[:-40]
        return True

    def _take_off_queue(self, comm, count):
        """Sold or stored tonnes leave the oldest mined ones first."""
        queue = self.mined.get(comm) or []
        while count > 0 and queue:
            take = min(count, queue[0][1])
            queue[0][1] -= take
            count -= take
            if queue[0][1] <= 0:
                queue.pop(0)

    def trim_to_hold(self, hold):
        """Forget what is no longer aboard. `hold` is {commodity: tonnes};
        a commodity not in it at all has been sold, dumped or lost."""
        have = {SV.fold(n): _whole(c) for n, c in dict(hold or {}).items()}
        changed = False
        with self._lock:
            for comm in list(self.mined):
                left = have.get(comm, 0)
                queue = self.mined[comm]
                total = sum(t for _s, t in queue)
                if total > left:
                    self._take_off_queue(comm, total - left)
                    changed = True
                if not self.mined[comm]:
                    del self.mined[comm]
            for table in (self.carrier, self.bought):
                for comm in list(table):
                    left = have.get(comm, 0)
                    if table[comm] > left:
                        table[comm] = left
                        changed = True
                    if table[comm] <= 0:
                        del table[comm]
                        changed = True
            if changed:
                self.dirty = True
                self.revision += 1
        return changed

    # -- asking ----------------------------------------------------------------

    @property
    def power(self):
        return str(self.me.get("power") or "")

    def entry(self, system):
        """The record of one system, or None."""
        with self._lock:
            found = self.systems.get(key_of(system))
            return dict(found) if found else None

    def position(self, system):
        entry = self.entry(system)
        if entry and all(entry.get(a) is not None for a in ("x", "y", "z")):
            return (entry["x"], entry["y"], entry["z"])
        return None

    def ly(self, a, b):
        return distance(self.position(a), self.position(b))

    def all_systems(self):
        with self._lock:
            return [dict(v) for v in self.systems.values()]

    def anchors(self, power=None):
        """The remembered Stronghold and Fortified systems of a Power."""
        power = str(power if power is not None else self.power).lower()
        if not power:
            return []
        return [e for e in self.all_systems()
                if str(e.get("power") or "").lower() == power
                and e.get("state") in REACH_LY]

    def nearest_anchor(self, system, power=None):
        """(entry, light years, reach) of the closest anchor of the pledged
        Power whose reach covers `system` - or the closest anchor at all
        with covered False. (None, None, False) with none remembered."""
        here = self.position(system)
        best = None
        for entry in self.anchors(power):
            where = (entry.get("x"), entry.get("y"), entry.get("z"))
            gap = distance(here, where if None not in where else None)
            if gap is None:
                continue
            covered = gap <= REACH_LY[entry["state"]]
            rank = (not covered, gap)
            if best is None or rank < best[0]:
                best = (rank, entry, gap)
        if best is None:
            return None, None, False
        return best[1], best[2], not best[0][0]

    # -- the rules ----------------------------------------------------------

    def verdict(self, mine, sell, range_rule=None):
        """What selling goods mined in `mine` in `sell` does for the pledged
        Power: a dict with goal (Expand / Reinforce / Undermine / Nothing /
        Unknown), why (a sentence), and the numbers it used."""
        rule = self.range_rule if range_rule is None else bool(range_rule)
        out = {"goal": UNKNOWN, "why": "", "ly": None, "reach": None,
               "mine": str(mine or ""), "sell": str(sell or "")}
        power = self.power
        if not power:
            out["why"] = ("No pledge in your journal yet. The game writes it "
                          "at login - or you are not pledged, and no merits "
                          "are paid.")
            return out
        seller = self.entry(sell)
        miner = self.entry(mine)
        if seller is None:
            out["why"] = ("%s is not in your Powerplay record - you have not "
                          "been there with this build." % (sell or "That system"))
            return out
        if miner is None:
            out["why"] = ("Where the goods were mined (%s) is not in your "
                          "Powerplay record." % (mine or "unknown"))
            return out
        if not seller.get("state") or not miner.get("state"):
            out["why"] = "The journal gave no Powerplay state for one of them."
            return out
        same = key_of(mine) == key_of(sell)
        m_power = str(miner.get("power") or "")
        m_mine = m_power.lower() == power.lower()
        if same:
            if m_mine and miner["state"] in CONTROLLED:
                out.update(goal=REINFORCE, why=(
                    "Mined and sold in %s, which your Power (%s) controls - "
                    "that reinforces it." % (sell, miner["state"])))
                return out
            if m_power and not m_mine and miner["state"] in CONTROLLED:
                anchor, gap, covered = self.nearest_anchor(sell)
                out["ly"] = gap
                if not rule or covered:
                    reach = REACH_LY[anchor["state"]] if anchor else None
                    out.update(goal=UNDERMINE, reach=reach, why=(
                        "Mined and sold in %s, held by %s (%s)%s."
                        % (sell, m_power, miner["state"],
                           (" - %.1f Ly from your %s %s, inside its %g Ly"
                            % (gap, anchor["state"], anchor["system"], reach))
                           if anchor and covered else
                           " - range rule off")))
                    return out
                nearest = ("nearest is %s at %.1f Ly, reach %g Ly"
                           % (anchor["system"], gap, REACH_LY[anchor["state"]])
                           if anchor else "none remembered")
                out.update(goal=NOTHING, why=(
                    "%s is %s's, but none of your Stronghold or Fortified "
                    "systems is in range (%s)." % (sell, m_power, nearest)))
                return out
            out.update(goal=NOTHING, why=(
                "%s is %s - mined and sold there earns nothing for you." % (
                    sell, ("unoccupied" if miner["state"] == "Unoccupied"
                           else "not in your Power's hands"))))
            return out
        # Different systems: the only thing that counts is Expand.
        if seller["state"] == "Unoccupied":
            if not (m_mine and miner["state"] in REACH_LY):
                out.update(goal=NOTHING, why=(
                    "To expand, mine in a Stronghold or Fortified system of "
                    "your Power. %s is %s."
                    % (mine, "not yours" if not m_mine else
                       "only %s" % miner["state"])))
                return out
            gap = self.ly(mine, sell)
            reach = REACH_LY[miner["state"]]
            out.update(ly=gap, reach=reach)
            if gap is None:
                out["why"] = "The distance cannot be measured: no position."
                out["goal"] = UNKNOWN
            elif gap <= reach:
                out.update(goal=EXPAND, why=(
                    "%s is %.1f Ly from your %s %s - inside its %g Ly. Selling "
                    "there expands your Power." % (sell, gap, miner["state"],
                                                   mine, reach)))
            else:
                out.update(goal=NOTHING, why=(
                    "%s is %.1f Ly from %s; a %s reaches %g Ly."
                    % (sell, gap, mine, miner["state"], reach)))
            return out
        out.update(goal=NOTHING, why=(
            "Reinforce and undermine need the system you mined in; selling in "
            "%s (%s) does not count." % (sell, seller["state"].lower())))
        return out

    # -- provenance: will it count --------------------------------------------

    def provenance(self, hold):
        """What of the hold may not earn merits, and why.

        `hold` is {commodity: tonnes aboard}. Returns a list of dicts, one
        per commodity with a problem: name, tonnes aboard, tonnes at risk,
        reason. A tonne that went through a fleet carrier, or was bought,
        is paid no merits."""
        out = []
        with self._lock:
            for name, aboard in sorted(dict(hold or {}).items()):
                comm = SV.fold(name)
                aboard = _whole(aboard)
                if aboard <= 0:
                    continue
                carrier = min(aboard, self.carrier.get(comm, 0))
                bought = min(aboard, self.bought.get(comm, 0))
                if carrier:
                    out.append({"commodity": name, "aboard": aboard,
                                "tonnes": carrier, "why": "carrier",
                                "text": "%d t of %s came off a fleet carrier "
                                        "- merits are not paid on it."
                                        % (carrier, name)})
                if bought:
                    out.append({"commodity": name, "aboard": aboard,
                                "tonnes": bought, "why": "bought",
                                "text": "%d t of %s was bought - merits are "
                                        "paid on mined cargo only."
                                        % (bought, name)})
        return out

    def mined_where(self, hold):
        """{system: tonnes} of the mined goods still aboard, newest first
        taken - the most recent tonnes are the ones that are aboard."""
        out = {}
        with self._lock:
            for name, aboard in dict(hold or {}).items():
                comm = SV.fold(name)
                left = _whole(aboard)
                for system, tonnes in reversed(self.mined.get(comm) or []):
                    if left <= 0:
                        break
                    take = min(left, tonnes)
                    out[system] = out.get(system, 0) + take
                    left -= take
        return out

    def hold_origin(self, hold):
        """The system most of the mined hold came from, or ""."""
        where = self.mined_where(hold)
        if not where:
            return ""
        return max(where.items(), key=lambda kv: (kv[1], kv[0]))[0]

    def sale_flags(self):
        """The recent sales, each said to have counted or not by what the
        sale itself shows: a sale with AvgPricePaid over 0 was bought stock."""
        out = []
        for sale in self.sales:
            bought = sale.get("avg_paid", 0) > 0
            out.append(dict(sale, counts=not bought,
                            note=("bought stock (AvgPricePaid %s Cr) - no "
                                  "merits" % "{:,}".format(sale["avg_paid"]))
                            if bought else ""))
        return out

    # -- learning from the older journals ---------------------------------------

    def learn_file(self, path):
        """Read the pledge and the systems out of one journal. How many
        notes changed anything."""
        with open(path, "rb") as handle:
            data = handle.read()
        if b'"Power' not in data:
            return 0
        changed = 0
        for raw in data.splitlines():
            if b'"event"' not in raw:
                continue
            if not (b'"PowerplayState"' in raw or b'"ControllingPower"' in raw
                    or b'"Powers"' in raw or b'"event":"Powerplay' in raw
                    or b'"event": "Powerplay' in raw):
                continue
            try:
                event = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            name = event.get("event")
            if name in SYSTEM_EVENTS:
                note = system_note(event)
            elif name in PLEDGE_EVENTS:
                note = pledge_note(event)
            else:
                continue
            if note and self.observe(note):
                changed += 1
        return changed

    def learn_folder(self, folder, stop=None):
        """Every journal in the folder not read before. Never raises."""
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


# -- merits for the hold -----------------------------------------------------------

def hold_merits(rate, aboard, prices, risky=None):
    """Merits the hold is estimated to earn at `prices`, from what
    MeritRate has learnt from the commander's own sales. A dict:

      merits   int or None (None until a rate has been learnt)
      lines    [{commodity, tonnes, price, merits}]
      missing  commodities with no price to go by

    `aboard` is {commodity: tonnes that count}; `risky` is the tonnes that
    will not count per commodity, which are left out of the estimate."""
    out = {"merits": None, "lines": [], "missing": []}
    if rate is None:
        return out
    base = rate.per_credit()
    if not base:
        return out
    total = 0.0
    prices = {SV.fold(k): _whole(v) for k, v in dict(prices or {}).items()}
    risky = {SV.fold(k): _whole(v) for k, v in dict(risky or {}).items()}
    for name, tonnes in sorted(dict(aboard or {}).items()):
        tonnes = max(0, _whole(tonnes) - risky.get(SV.fold(name), 0))
        if tonnes <= 0:
            continue
        price = prices.get(SV.fold(name), 0)
        if price <= 0:
            out["missing"].append(name)
            continue
        per = rate.per_credit(name) or base
        earned = tonnes * price * per
        total += earned
        out["lines"].append({"commodity": name, "tonnes": tonnes,
                             "price": price, "merits": int(round(earned))})
    out["merits"] = int(round(total))
    return out


# -- putting it together for the windows -----------------------------------------------

def counted_hold(hold, risk):
    """{commodity: tonnes} of the hold that can earn merits: the hold less the
    tonnes that went through a carrier or were bought."""
    gone = {}
    for item in risk or ():
        gone[SV.fold(item["commodity"])] = gone.get(SV.fold(item["commodity"]), 0) \
            + item["tonnes"]
    out = {}
    for name, tonnes in dict(hold or {}).items():
        left = _whole(tonnes) - gone.get(SV.fold(name), 0)
        if left > 0:
            out[name] = left
    return out


def earning_tonnes(book, counted, sell, origin, told=False):
    """({commodity: tonnes that earn when sold in `sell`}, [the rest]).

    Every tonne is judged by the system it was mined in: the record's word
    for it, or `origin` for a tonne the record has no word on - and for every
    tonne when the commander has said where they came from (`told`). Each
    tonne mined where selling in `sell` does not count is in the second
    list, said in a sentence."""
    earning, elsewhere, cache = {}, [], {}
    for name, tonnes in sorted(dict(counted or {}).items()):
        tonnes = _whole(tonnes)
        where = {} if told else book.mined_where({name: tonnes})
        known = sum(where.values())
        if tonnes > known and origin:
            where[origin] = where.get(origin, 0) + tonnes - known
        for system, part in sorted(where.items()):
            key = key_of(system)
            if key not in cache:
                cache[key] = book.verdict(system, sell)
            if cache[key]["goal"] in COUNTS:
                earning[name] = earning.get(name, 0) + part
            else:
                elsewhere.append({
                    "commodity": name, "aboard": tonnes, "tonnes": part,
                    "why": "elsewhere", "system": system,
                    "text": "%d t of %s was mined in %s - selling it in %s "
                            "earns nothing." % (part, name, system,
                                                sell or "this system")})
    return earning, elsewhere


def assess(book, rate, hold, here, sell=None, prices=None, origin=None):
    """What selling `hold` in `sell` (default: where the commander is) does
    for his Power: the rule that applies, whether the cargo will count, and
    the merits it is estimated to earn.

    `here` is the system the commander is in, `origin` where the goods were
    mined (default: where most of the mined hold came from, else `here`),
    `prices` {commodity: credits a tonne} at the system sold in. The rule
    in the headline is the one for where most of the hold was mined; the
    estimate counts only the tonnes that earn - mined, never bought or
    through a carrier, and mined where selling in `sell` counts. Never
    raises; every part says what it does not know."""
    hold = {n: _whole(t) for n, t in dict(hold or {}).items() if _whole(t) > 0}
    sell = str(sell or here or "")
    told = bool(origin)
    known = book.hold_origin(hold) if hold else ""
    origin = str(origin or known or here or "")
    verdict = book.verdict(origin, sell)
    risk = book.provenance(hold)
    counted = counted_hold(hold, risk)
    earning, elsewhere = earning_tonnes(book, counted, sell, origin, told)
    if hold and not earning and verdict["goal"] in COUNTS:
        # The rule would pay for mined goods, and none aboard earn: every
        # tonne was bought, has been through a fleet carrier, or was mined
        # somewhere selling here does not count for.
        verdict = dict(verdict, goal=NOTHING, rule=verdict["goal"], why=(
            "everything aboard was bought or has been through a fleet "
            "carrier, and merits are paid on mined cargo only." if not counted
            else "none of what is aboard was mined where selling in %s "
                 "counts." % sell))
    counts = verdict["goal"] in COUNTS
    if not counts:
        elsewhere = []
    merits = hold_merits(rate, earning if counts else {}, prices)
    out = {"pledge": book.power, "origin": origin, "origin_known": bool(known),
           "sell": sell, "verdict": verdict, "goal": verdict["goal"],
           "counts": counts, "risk": risk, "counted": counted, "hold": hold,
           "earning": earning, "elsewhere": elsewhere,
           "merits": merits, "headline": ""}
    if not hold:
        out["headline"] = "Nothing aboard yet. Mined in %s, sold in %s: %s. %s" % (
            origin or "an unknown system", sell or "this system",
            verdict["goal"], verdict["why"])
    elif not counts:
        out["headline"] = "Selling in %s earns no merits: %s" % (
            sell or "this system", verdict["why"])
    elif merits["merits"] is None:
        out["headline"] = ("%s in %s. Estimated merits appear once you have "
                           "sold a few loads of mined cargo while pledged."
                           % (verdict["goal"], sell))
    else:
        out["headline"] = "%s in %s: about %s merits for what counts of the hold." % (
            verdict["goal"], sell, "{:,}".format(merits["merits"]))
    if risk or elsewhere:
        out["headline"] += " " + " ".join(item["text"] for item in risk + elsewhere)
    return out


def annotate(book, rows, origin, range_rule=None):
    """Price rows, each with the Powerplay result of selling there for goods
    mined in `origin`: goal and goal_why. Rows are copied, not changed."""
    out = []
    cache = {}
    for row in rows or ():
        system = str(row.get("system") or "")
        key = key_of(system)
        if key not in cache:
            cache[key] = book.verdict(origin, system, range_rule) if system else \
                {"goal": UNKNOWN, "why": "No system on that row."}
        out.append(dict(row, goal=cache[key]["goal"], goal_why=cache[key]["why"]))
    return out


def system_rows(book, origin, here=None, limit=300):
    """The remembered systems as rows for the Powerplay table: what selling
    in each would do for goods mined in `origin`. Systems that count come
    first, then the nearest. `here` is the commander's (x, y, z)."""
    out = []
    for entry in book.all_systems():
        name = entry.get("system") or ""
        where = (entry.get("x"), entry.get("y"), entry.get("z"))
        gap = distance(here, where if None not in where else None)
        verdict = book.verdict(origin, name)
        out.append({"system": name, "ly": gap, "power": entry.get("power") or "",
                    "state": entry.get("state") or "", "goal": verdict["goal"],
                    "why": verdict["why"], "gap": verdict.get("ly"),
                    "progress": entry.get("progress"),
                    "seen": entry.get("seen") or ""})
    out.sort(key=lambda r: (r["goal"] not in COUNTS, r["ly"] is None, r["ly"] or 0.0,
                            r["system"].lower()))
    return out[:limit]
