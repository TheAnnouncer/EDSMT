"""Squadron share (1.10040, #301): carriers, orders, Powerplay and hauling
to your squadron's site - off by default.

This is commander data, not deposit finds, so it has its own switch, off
until you turn it on, and it is only offered once the journal has named a
squadron. What goes is a whitelist: a handful of events, and inside each
only the fields named here. Everything else - credits, carrier finance,
what a carrier cost, the FID, what other people said in squadron chat -
never leaves the PC because this never reads it.

Plain functions and one small box. The journal reader picks events with
pick() and keeps them for the app; the app puts them in a Box and sends a
batch at most once a minute.
"""
import time

TAG = "squadron"
SETTING = "squadron_share"
DEFAULT = False
EVERY_S = 60.0
MOST = 400
NOTICE = ("Shares, with your squadron's site only: your carrier's location and jumps, "
          "its buy and sell orders, your Powerplay rank and merits, and the hauling "
          "tonnage you deliver to builds. Never credits, carrier finance, prices paid, "
          "your FID or anything anyone said in chat. Off unless you turn it on.")

# The events and, inside each, the fields that go. A field not named here
# is dropped before the event leaves the reader.
EVENTS = {
    "SquadronStartup": ("SquadronID", "SquadronName", "CurrentRank", "CurrentRankName"),
    "SquadronCreated": ("SquadronName",),
    "SquadronPromotion": ("SquadronName", "OldRankName", "NewRankName"),
    "CarrierStats": ("CarrierID", "CarrierType", "Callsign", "Name", "DockingAccess", "FuelLevel",
                     "JumpRangeCurr", "SpaceUsage"),
    "CarrierLocation": ("CarrierType", "CarrierID", "StarSystem", "SystemAddress", "BodyID"),
    "CarrierJumpRequest": ("CarrierID", "SystemName", "Body", "SystemAddress", "DepartureTime"),
    "CarrierJumpCancelled": ("CarrierID",),
    "CarrierJump": ("StarSystem", "SystemAddress", "MarketID", "StationName"),
    "CarrierTradeOrder": ("CarrierID", "Commodity", "Commodity_Localised", "PurchaseOrder", "SaleOrder",
                          "CancelTrade", "Price"),
    "CarrierBuy": ("CarrierType", "CarrierID", "Location", "Callsign", "Variant"),
    "CarrierNameChange": ("CarrierID", "Name", "Callsign"),
    "CarrierCrewServices": ("CarrierID", "CrewRole", "Operation"),
    "Powerplay": ("Power", "Rank", "Merits", "TimePledged"),
    "PowerplayMerits": ("Power", "MeritsGained", "TotalMerits"),
    "PowerplayRank": ("Power", "Rank"),
    "PowerplayJoin": ("Power",),
    "PowerplayLeave": ("Power",),
    "ColonisationContribution": ("MarketID", "Contributions"),
    "ColonisationConstructionDepot": ("MarketID", "ConstructionProgress", "ConstructionComplete",
                                      "ResourcesRequired"),
    "ColonisationSystemClaim": ("StarSystem", "SystemAddress"),
}
# Inside a nested field, the same rule.
_INSIDE = {
    "SpaceUsage": ("Cargo", "FreeSpace"),
    "Contributions": ("Name", "Name_Localised", "Amount"),
    "ResourcesRequired": ("Name", "Name_Localised", "RequiredAmount", "ProvidedAmount"),
}
# One of these a minute is the latest state, not a history: a batch keeps
# the last one per key.
_LATEST = {"ColonisationConstructionDepot": "MarketID", "CarrierStats": "CarrierID",
           "CarrierLocation": "CarrierID", "Powerplay": "Power"}


def _inside(name, value):
    keep = _INSIDE.get(name)
    if keep is None:
        return value
    if isinstance(value, dict):
        return {k: value[k] for k in keep if k in value}
    if isinstance(value, list):
        return [{k: item[k] for k in keep if k in item} for item in value if isinstance(item, dict)]
    return value


def pick(event):
    """The whitelisted copy of a journal event, or None for one that does
    not go. Only named fields; nothing else is read."""
    if not isinstance(event, dict):
        return None
    name = event.get("event")
    keep = EVENTS.get(name)
    when = event.get("timestamp")
    if keep is None or not when:
        return None
    out = {"timestamp": str(when), "event": name}
    for key in keep:
        if key in event:
            out[key] = _inside(key, event[key])
    return out


def squadron_after(squadron, event):
    """The squadron the journal names, kept across events."""
    name = event.get("event") if isinstance(event, dict) else None
    if name == "SquadronStartup" and event.get("SquadronID"):
        return {"id": int(event["SquadronID"]), "name": str(event.get("SquadronName") or ""),
                "rank": str(event.get("CurrentRankName") or "")}
    if name == "SquadronPromotion" and squadron:
        return dict(squadron, rank=str(event.get("NewRankName") or squadron.get("rank") or ""))
    return squadron


def wanted(settings, squadron):
    """On, and a squadron known: the only time anything is sent."""
    return bool((settings or {}).get(SETTING, DEFAULT)) and bool(squadron and squadron.get("id"))


class Box:
    """Picked events waiting to go, sent at most once a minute, never more
    than MOST held: the newest win, and a depot's progress is one entry."""

    def __init__(self, now=None):
        self.events = []
        self.sent_at = now if now is not None else time.time()

    def add(self, event, now=None):
        if not event:
            return False
        key = _LATEST.get(event.get("event"))
        if key is not None and key in event:
            self.events = [e for e in self.events
                           if not (e.get("event") == event["event"] and e.get(key) == event[key])]
        self.events.append(event)
        if len(self.events) > MOST:
            self.events = self.events[-MOST:]
        return True

    def due(self, now=None):
        now = now if now is not None else time.time()
        return bool(self.events) and now - self.sent_at >= EVERY_S

    def take(self, squadron_id, cmdr, now=None):
        """The batch to send; the box is emptied. give_back() on failure."""
        self.sent_at = now if now is not None else time.time()
        events, self.events = self.events, []
        return {"squadronId": int(squadron_id), "cmdr": str(cmdr or ""), "events": events}

    def give_back(self, events):
        self.events = (list(events or []) + self.events)[-MOST:]
