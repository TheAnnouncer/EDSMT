"""What Celestia says on her own (1.10040), from the journal and Status.json.

Voice-pack reminders. Many commanders drive the game by voice through a
VoiceAttack voice pack. At the moment the journal shows, she reminds them of
the phrase to say - "Deploy the SRV" after landing, "Dismiss the ship" once
the Rhino is out and the ship still sits there, "Recall the ship" when every
rig is up, "Transfer cargo" with a full Rhino by the ship, "Board the ship"
when it is all done, "Apply handbrake" on a rig pin. Each waits a few
seconds first and is dropped if the journal shows it done in that time; none
comes again inside ten minutes.

With Chatty: reactions to what the journal and Status.json show - the Rhino
going out and coming home, a touchdown, a big sale, mining locations found,
heat, low fuel - and now and then, when nothing is going on and nothing is
dangerous, a lore aside.

Pure logic: events, flags and the app's own cues in; at most one line id
out per call to due(). No window, no sound.
"""
import calendar
import random
import time

# Status.json Flags (Frontier's Status file documentation).
FLAG_LANDED = 1 << 1
FLAG_SCOOPING = 1 << 11
FLAG_HANDBRAKE = 1 << 12
FLAG_NEAR_SHIP = 1 << 14       # "Srv Turret retracted (close to ship)"
FLAG_LOW_FUEL = 1 << 19
FLAG_OVERHEAT = 1 << 20
FLAG_IN_DANGER = 1 << 22
FLAG_IN_SRV = 1 << 26

# How long a reminder waits for the journal to show it done.
HINT_GRACE_S = {"hint_deploy_srv": 20, "hint_dismiss_ship": 40, "hint_recall_ship": 30,
                "hint_transfer_cargo": 30, "hint_board_ship": 30, "hint_handbrake": 4}
HINT_EVERY_S = 600
# The same reaction not again inside this; her own lines never closer than
# OWN_GAP_S; a reaction waits a moment so the app's own line goes first.
REACT_EVERY_S = 180
REACT_DELAY_S = 2
OWN_GAP_S = 8
# Lore: after this long with nothing said and nothing happening, and never
# sooner than LORE_EVERY_S after the last.
LORE_IDLE_S = 240
LORE_EVERY_S = 480
BIG_SALE = 50000000
SRV_HOLD_T = 72

# Journal events and the reaction each brings (Chatty).
REACTIONS = {"LaunchSRV": "react_launch_srv", "DockSRV": "react_dock_srv",
             "SRVDestroyed": "react_srv_destroyed", "Touchdown": "react_touchdown",
             "Liftoff": "react_liftoff", "FSDJump": "react_jump", "Died": "react_died",
             "WingJoin": "react_wing_join"}
# Status flags whose start brings a reaction (Chatty).
FLAG_REACTIONS = {FLAG_OVERHEAT: "react_overheat", FLAG_LOW_FUEL: "react_low_fuel",
                  FLAG_SCOOPING: "react_scooping"}
EVENTS = set(REACTIONS) | {"Cargo", "CargoTransfer", "Disembark", "MarketSell",
                           "FSSBodySignals", "SAASignalsFound"}

LORE = ("lore_raxxla", "lore_dark_wheel", "lore_void", "lore_thargoids", "lore_guardians",
        "lore_rocks", "lore_bubble", "lore_signal", "lore_rhino", "lore_stars",
        "lore_patience", "lore_company", "lore_radio_quiet", "lore_radio_drive",
        "lore_radio_humming", "lore_radio_rocks")


# An event older than this by its own timestamp was read back from earlier
# in the journal when the app started, not seen as it happened.
FRESH_S = 120.0


def fresh(event, now):
    """True for an event the game wrote in the last FRESH_S seconds."""
    try:
        when = float(calendar.timegm(time.strptime(str(event.get("timestamp")), "%Y-%m-%dT%H:%M:%SZ")))
    except (AttributeError, TypeError, ValueError, OverflowError):
        return False
    return abs(now - when) <= FRESH_S


def hints_wanted(setting, found):
    """The reminders switch: left alone (None) it follows whether a voice
    pack was found; once set, it is what was set."""
    return bool(found) if setting is None else bool(setting)


def kept_auto(before, picked, found):
    """What Settings saves for the switch: still None (following what is
    found) when it was left alone and saved as shown, else what was picked."""
    if before is None and bool(picked) == bool(found):
        return None
    return bool(picked)


def _yours(event):
    """A launch or landing the commander made: PlayerControlled true or
    absent (a single-SRV journal leaves it out)."""
    return event.get("PlayerControlled", True) is not False


class Cues:
    def __init__(self, seed=None):
        self.ship_landed = False      # your ship is down on this body
        self.ship_away = False        # dismissed from the Rhino
        self.srv_out = False
        self.srv_cargo = 0
        self.rigs_up = False          # every rig back aboard since the last went down
        self.flags = 0
        self.pending = {}             # hint id -> when it is due
        self.reaction = None          # (id, due)
        self.said_at = {}             # line id -> when last said
        self.last_own = None          # when she last said a line of her own
        self.last_activity = None     # an event or any line
        self.last_lore = None
        self.lore_last_id = ""
        self._random = random.Random(seed)

    # -- what comes in ---------------------------------------------------------

    def _schedule(self, hint, now):
        self.pending[hint] = now + HINT_GRACE_S[hint]

    def _drop(self, *hints):
        for hint in hints:
            self.pending.pop(hint, None)

    def _react(self, line_id, now):
        if self.reaction is None:
            self.reaction = (line_id, now + REACT_DELAY_S)

    def see(self, event, now):
        """One journal event, as the reader parsed it."""
        if not isinstance(event, dict):
            return
        name = event.get("event")
        if name not in EVENTS:
            return
        self.last_activity = now
        if name == "Touchdown":
            if _yours(event):
                self.ship_landed, self.ship_away = True, False
                self._schedule("hint_deploy_srv", now)
                self._react("react_touchdown", now)
            else:
                self.ship_landed, self.ship_away = True, False
                self._drop("hint_recall_ship")
        elif name == "Liftoff":
            self._drop("hint_deploy_srv")
            if _yours(event):
                self.ship_landed, self.ship_away = False, False
                self._react("react_liftoff", now)
            else:
                self.ship_landed, self.ship_away = False, True
                self._drop("hint_dismiss_ship")
        elif name == "LaunchSRV":
            if not _yours(event):
                return
            self.srv_out, self.rigs_up = True, False
            self._drop("hint_deploy_srv")
            if self.ship_landed and not self.ship_away:
                self._schedule("hint_dismiss_ship", now)
            self._react("react_launch_srv", now)
        elif name == "Disembark":
            self._drop("hint_deploy_srv")
        elif name == "DockSRV":
            self.srv_out = False
            self._drop("hint_dismiss_ship", "hint_recall_ship", "hint_board_ship",
                       "hint_transfer_cargo", "hint_handbrake")
            self._react("react_dock_srv", now)
        elif name == "SRVDestroyed":
            self.srv_out = False
            self._drop("hint_dismiss_ship", "hint_recall_ship", "hint_board_ship",
                       "hint_transfer_cargo", "hint_handbrake")
            self._react("react_srv_destroyed", now)
        elif name == "Cargo":
            if str(event.get("Vessel") or "") == "SRV":
                try:
                    count = int(event.get("Count") or 0)
                except (TypeError, ValueError):
                    count = 0
                full_before = self.srv_cargo >= SRV_HOLD_T
                self.srv_cargo = count
                if count >= SRV_HOLD_T and not full_before:
                    self._react("react_hold_full", now)
                    if self.flags & FLAG_NEAR_SHIP:
                        self._schedule("hint_transfer_cargo", now)
        elif name == "CargoTransfer":
            moved = any(str(t.get("Direction") or "") == "toship"
                        for t in event.get("Transfers") or [] if isinstance(t, dict))
            if moved:
                self.srv_cargo = 0
                self._drop("hint_transfer_cargo")
        elif name == "MarketSell":
            try:
                total = int(event.get("TotalSale") or 0)
            except (TypeError, ValueError):
                total = 0
            if total >= BIG_SALE:
                self._react("react_big_sale", now)
        elif name in ("FSSBodySignals", "SAASignalsFound"):
            if any("PlanetaryMiningLocation" in str(s.get("Type") or "")
                   for s in event.get("Signals") or [] if isinstance(s, dict)):
                self._react("react_mining_body", now)
        elif name in REACTIONS:
            self._react(REACTIONS[name], now)

    def status(self, flags, now):
        """Status.json's Flags, each time it is read."""
        try:
            flags = int(flags or 0)
        except (TypeError, ValueError):
            flags = 0
        rose = flags & ~self.flags
        self.flags = flags
        for bit, line_id in FLAG_REACTIONS.items():
            if rose & bit:
                self.last_activity = now
                self._react(line_id, now)
        if flags & FLAG_HANDBRAKE:
            self._drop("hint_handbrake")
        if rose & FLAG_NEAR_SHIP and flags & FLAG_IN_SRV:
            if self.srv_cargo >= SRV_HOLD_T:
                self._schedule("hint_transfer_cargo", now)
            elif self.rigs_up and self.ship_landed and not self.ship_away:
                self._schedule("hint_board_ship", now)

    def app(self, cue, now):
        """Something the app did: "rigs_all_up", "rig_down", "pin_reached"."""
        if cue == "rigs_all_up":
            self.rigs_up = True
            if self.ship_away:
                self._schedule("hint_recall_ship", now)
            elif self.ship_landed and self.flags & FLAG_NEAR_SHIP and self.srv_cargo < SRV_HOLD_T:
                self._schedule("hint_board_ship", now)
        elif cue == "rig_down":
            self.rigs_up = False
        elif cue == "pin_reached":
            if not self.flags & FLAG_HANDBRAKE:
                self._schedule("hint_handbrake", now)

    def spoke(self, now):
        """A line was said - hers or the app's - so the quiet starts again."""
        self.last_activity = now

    # -- what goes out ---------------------------------------------------------

    def due(self, now, hints=True, chatty=False, busy=False):
        """The one line of her own to say now, or ""."""
        if self.last_activity is None:
            self.last_activity = now
        if self.last_own is not None and now - self.last_own < OWN_GAP_S:
            return ""
        if hints:
            for hint, when in sorted(self.pending.items(), key=lambda kv: kv[1]):
                if now >= when:
                    del self.pending[hint]
                    last = self.said_at.get(hint)
                    if last is not None and now - last < HINT_EVERY_S:
                        continue
                    return self._said(hint, now)
        else:
            self.pending.clear()
        if not chatty:
            self.reaction = None
            return ""
        if self.reaction is not None and now >= self.reaction[1]:
            line_id, _due = self.reaction
            self.reaction = None
            last = self.said_at.get(line_id)
            if last is None or now - last >= REACT_EVERY_S:
                return self._said(line_id, now)
        if busy or self.flags & FLAG_IN_DANGER:
            return ""
        if now - self.last_activity >= LORE_IDLE_S and (
                self.last_lore is None or now - self.last_lore >= LORE_EVERY_S):
            choices = [i for i in LORE if i != self.lore_last_id]
            line_id = self._random.choice(choices)
            self.lore_last_id, self.last_lore = line_id, now
            return self._said(line_id, now)
        return ""

    def _said(self, line_id, now):
        self.said_at[line_id] = now
        self.last_own = now
        self.last_activity = now
        return line_id
