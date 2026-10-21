"""What a Rhino session carried that its row does not (1.10035, #239).

The session row says what was mined and what was sold. Three more things
bear on the Discord summary, and the journal gives each of them seconds
away from the thing it belongs to:

  materials   MaterialCollected while the session was running.
  wages       NpcCrewPaidWage, in the same second as the sale it comes out
              of - the owner's 28 sales were each exactly 15.0% of profit.
              Net is the sale less these.
  merits      PowerplayMerits, up to a minute or so after the sale.

Each is attributed to the session or sessions the app's own books booked the
sale to, by the same rule the books use, and kept in session_extras.json so
a restart does not lose them. A journal read again from the top gives every
event a second time; each is remembered by its own timestamp and amount and
counted once.
"""

import json
import os
import threading
import time

FILE = "session_extras.json"
WAGE_PAIR_S = 3             # wages are written in the second of the sale
MERIT_PAIR_S = 90           # merits follow a sale by seconds, never minutes
LEAD_S = 30                 # a material can land just before the first tonne
KEEP_SEEN = 4000
SAVE_EVERY_S = 8.0


def _epoch(stamp):
    try:
        from survey import _epoch as epoch
        return epoch(stamp)
    except Exception:
        return 0


def _whole(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class SessionLedger:
    def __init__(self, folder=None):
        self.path = os.path.join(folder, FILE) if folder else ""
        self.sessions = {}        # session id -> {"materials", "wages", "wage_events", "merits"}
        self.seen = {}            # event key -> epoch, so a replay counts nothing twice
        self._sales = []          # recent sales the books took: {"at", "split", "merits_done"}
        self._wages = []          # wages not yet matched to a sale
        self._mission_at = 0
        self._last_total = None
        self._dirty = False
        self._saved_at = 0.0
        self._lock = threading.Lock()
        self.load()

    # -- storage -----------------------------------------------------------

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
        sessions = data.get("sessions")
        if isinstance(sessions, dict):
            self.sessions = {str(k): dict(v) for k, v in sessions.items()
                             if isinstance(v, dict)}
        seen = data.get("seen")
        if isinstance(seen, dict):
            self.seen = {str(k): float(v) for k, v in seen.items()}
        return True

    def save(self, force=False):
        if not self.path or not (self._dirty or force):
            return False
        if not force and time.time() - self._saved_at < SAVE_EVERY_S:
            return False
        with self._lock:
            if len(self.seen) > KEEP_SEEN:
                keep = sorted(self.seen.items(), key=lambda kv: kv[1])[-KEEP_SEEN:]
                self.seen = dict(keep)
            data = {"sessions": self.sessions, "seen": self.seen}
            try:
                os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
                temp = self.path + ".tmp"
                with open(temp, "w", encoding="utf-8") as handle:
                    json.dump(data, handle)
                os.replace(temp, self.path)
            except OSError:
                return False
        self._dirty = False
        self._saved_at = time.time()
        return True

    # -- reading it back ---------------------------------------------------

    def for_session(self, sid):
        """{"materials": {name: n}, "wages": int or None, "merits": int}.
        wages is None until a wage event has been seen: no crew, no wages."""
        have = self.sessions.get(str(sid)) or {}
        return {"materials": dict(have.get("materials") or {}),
                "wages": _whole(have.get("wages")) if have.get("wage_events") else None,
                "merits": _whole(have.get("merits"))}

    def state_of(self, sid):
        """What an edit of the Discord message would have to say: changes
        when a wage, a merit or a material arrives."""
        have = self.sessions.get(str(sid)) or {}
        return (_whole(have.get("wages")), _whole(have.get("wage_events")),
                _whole(have.get("merits")),
                sum(_whole(v) for v in (have.get("materials") or {}).values()))

    def _row(self, sid):
        return self.sessions.setdefault(str(sid), {"materials": {}, "wages": 0,
                                                   "wage_events": 0, "merits": 0})

    # -- taking notes --------------------------------------------------------

    def _fresh(self, key, at):
        """True the first time an event is seen."""
        if key in self.seen:
            return False
        self.seen[key] = float(at or time.time())
        self._dirty = True
        return True

    def note(self, note, sessions=()):
        """One reader note. `sessions` are the books' rows, for placing a
        material by its time. Returns True when the ledger changed."""
        if not isinstance(note, dict):
            return False
        name = note.get("event")
        at = _epoch(note.get("when"))
        if name == "MaterialCollected":
            return self._material(note, at, sessions)
        if name == "NpcCrewPaidWage":
            return self._wage(note, at)
        if name == "PowerplayMerits":
            return self._merits(note, at)
        if name == "MissionCompleted":
            self._mission_at = at or 0
        return False

    def _material(self, note, at, sessions):
        label = str(note.get("name") or "").strip()
        count = max(1, _whole(note.get("count")))
        if not label or not at:
            return False
        key = "m|%s|%s|%s|%s" % (note.get("when"), label, count, note.get("n"))
        mine = None
        for row in sessions or ():
            start = _epoch(row.get("started"))
            if not start or at < start - LEAD_S:
                continue
            end = _epoch(row.get("closed")) if str(row.get("closed") or "").strip() else None
            if end is not None and at > end + 5:
                continue
            if mine is None or start > _epoch(mine.get("started")):
                mine = row
        if mine is None or not self._fresh(key, at):
            return False
        have = self._row(mine.get("id"))["materials"]
        have[label] = have.get(label, 0) + count
        return True

    def _wage(self, note, at):
        amount = _whole(note.get("amount"))
        key = "w|%s|%s|%s|%s" % (note.get("when"), note.get("crew_id") or note.get("crew"),
                                 amount, note.get("n"))
        if not at or not self._fresh(key, at):
            return False
        for sale in self._sales:
            if abs(sale["at"] - at) <= WAGE_PAIR_S:
                self._pay(sale["split"], amount)
                return True
        self._wages = [w for w in self._wages if abs(w["at"] - at) <= 10]
        self._wages.append({"at": at, "amount": amount})
        return False

    def _pay(self, split, amount):
        """Share a wage between the sessions a sale was booked to, by what
        each was paid. Every one of them learns that a crew was aboard."""
        total = sum(split.values()) or 1
        for sid, credits in split.items():
            row = self._row(sid)
            row["wages"] = _whole(row.get("wages")) + int(round(amount * credits / float(total)))
            row["wage_events"] = _whole(row.get("wage_events")) + 1
        self._dirty = True

    def sale(self, note, split):
        """A MarketSell the books have just booked. `split` is
        {session id: credits it was booked for}. Wages that arrived first are
        paid now."""
        at = _epoch(note.get("when"))
        split = {str(k): v for k, v in dict(split or {}).items() if v and v > 0}
        if not at or not split:
            return False
        self._sales = [s for s in self._sales if at - s["at"] <= MERIT_PAIR_S][-20:]
        self._sales.append({"at": at, "split": split})
        waiting, self._wages = self._wages, []
        for wage in waiting:
            if abs(wage["at"] - at) <= WAGE_PAIR_S:
                self._pay(split, wage["amount"])
            else:
                self._wages.append(wage)
        return True

    def _merits(self, note, at):
        merits = _whole(note.get("merits"))
        total = note.get("total")
        key = "p|%s|%s|%s" % (note.get("when"), merits, total)
        if not at or not self._fresh(key, at):
            return False
        last = self._last_total
        if total is not None:
            self._last_total = _whole(total)
            # A merits line that leaves the total where it was paid nothing.
            if last is not None and _whole(total) == last:
                return False
        sales = [s for s in self._sales if 0 <= at - s["at"] <= MERIT_PAIR_S]
        latest = max((s["at"] for s in sales), default=0)
        if self._mission_at and latest <= self._mission_at <= at:
            # A mission handed in after the last sale: its merits, not ours.
            self._mission_at = 0
            return False
        if merits <= 0 or not sales:
            return False
        shared = {}
        for sale in sales:
            for sid, credits in sale["split"].items():
                shared[sid] = shared.get(sid, 0) + credits
        self._sales = [s for s in self._sales if s not in sales]
        total_credits = sum(shared.values()) or 1
        for sid, credits in shared.items():
            row = self._row(sid)
            row["merits"] = _whole(row.get("merits")) + int(round(merits * credits / float(total_credits)))
        self._dirty = True
        return True


# ---------------------------------------------------------------------------
# The Discord message each session was posted as
# ---------------------------------------------------------------------------

POSTS_FILE = "discord_posts.json"
EDIT_QUIET_S = 25.0         # a sale is several MarketSell lines: wait for the last
EDIT_EVERY_S = 20.0
EDITS_MAX = 8
POSTS_KEPT = 200


class PostBook:
    """The one message posted for each session, by its Discord id, so the
    same message can be edited when the sale arrives - and so a session is
    never posted twice, even across a restart.

    posted    sid -> {"id", "attachments", "when", "state", "seen_state",
                      "changed_at", "edited_at", "edits", "dead", "image"}
    """

    def __init__(self, folder=None):
        self.path = os.path.join(folder, POSTS_FILE) if folder else ""
        self.posted = {}
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
        if isinstance(data, dict):
            self.posted = {str(k): dict(v) for k, v in data.items() if isinstance(v, dict)}
        return True

    def save(self):
        if not self.path:
            return False
        with self._lock:
            if len(self.posted) > POSTS_KEPT:
                keep = sorted(self.posted.items(), key=lambda kv: kv[1].get("when") or 0)
                self.posted = dict(keep[-POSTS_KEPT:])
            data = dict(self.posted)
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            temp = self.path + ".tmp"
            with open(temp, "w", encoding="utf-8") as handle:
                json.dump(data, handle)
            os.replace(temp, self.path)
            return True
        except OSError:
            return False

    def has(self, sid):
        return str(sid) in self.posted

    def sent(self, sid, state, image=""):
        """A post has been handed to the worker: the session is spoken for,
        whether or not Discord answers."""
        self.posted[str(sid)] = {"id": "", "attachments": [], "when": time.time(),
                                 "state": list(state), "seen_state": list(state),
                                 "changed_at": time.time(), "edited_at": 0.0,
                                 "edits": 0, "dead": False, "image": image}
        self.save()

    def answered(self, sid, message):
        """Discord's answer to the post: keep the message id and the ids of
        the attachments it holds. False when there is no id in it."""
        entry = self.posted.get(str(sid))
        if entry is None or not isinstance(message, dict):
            return False
        ident = str(message.get("id") or "")
        if not ident.isdigit():
            return False
        entry["id"] = ident
        entry["attachments"] = [str(a.get("id")) for a in message.get("attachments") or []
                                if isinstance(a, dict) and a.get("id") is not None]
        self.save()
        return True

    def watch(self, sid, state, now=None):
        """Tell the book what the session's figures are now. Returns True
        when the message should be edited: the figures changed since the
        last post or edit, nothing has changed for EDIT_QUIET_S, edits are
        not too close together or too many, and the message is known."""
        entry = self.posted.get(str(sid))
        if entry is None or entry.get("dead") or not entry.get("id"):
            return False
        now = time.time() if now is None else now
        state = list(state)
        if state != entry.get("seen_state"):
            entry["seen_state"] = state
            entry["changed_at"] = now
        if state == entry.get("state"):
            return False
        if now - float(entry.get("changed_at") or 0) < EDIT_QUIET_S:
            return False
        if now - float(entry.get("edited_at") or 0) < EDIT_EVERY_S \
                or int(entry.get("edits") or 0) >= EDITS_MAX:
            return False
        return True

    def edited(self, sid, state, now=None):
        entry = self.posted.get(str(sid))
        if entry is None:
            return
        entry["state"] = list(state)
        entry["edited_at"] = time.time() if now is None else now
        entry["edits"] = int(entry.get("edits") or 0) + 1
        self.save()

    def gone(self, sid):
        """The message was deleted on Discord: stop editing it."""
        entry = self.posted.get(str(sid))
        if entry is not None:
            entry["dead"] = True
            self.save()
