"""1.10040: squadron share (#301) - carriers, orders, Powerplay and hauling
to your squadron's site, off by default.

A separate switch from sharing finds: "Share my squadron stats with my
squadron's site", off until turned on, shown only once the journal has
named a squadron. What goes: carrier location and jumps, carrier buy and
sell orders, Powerplay rank and merits, hauling tonnage to builds. What
never goes: credits, carrier finance, prices paid for a carrier, the FID,
other people's chat. Whitelisted events, whitelisted fields, batched and
sent at most once a minute to the community map with the install key.

Pure parts run anywhere; the journal reader on a fixture; the app under xvfb:

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_squadron.py
"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-squad-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import squadshare as SQ  # noqa: E402
import journal as J      # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


T = "2026-10-28T02:21:10Z"
print("== what is picked, and what never goes ==")
stats = {"timestamp": T, "event": "CarrierStats", "CarrierID": 3708130560, "CarrierType": "SquadronCarrier",
         "Callsign": "RRAX", "Name": "RAXXLA HQ", "DockingAccess": "all", "AllowNotorious": False,
         "FuelLevel": 900, "JumpRangeCurr": 500.0, "JumpRangeMax": 500.0, "PendingDecommission": False,
         "SpaceUsage": {"TotalCapacity": 25000, "Crew": 1000, "Cargo": 163, "CargoSpaceReserved": 0,
                        "ShipPacks": 0, "ModulePacks": 0, "FreeSpace": 23837},
         "Finance": {"CarrierBalance": 123456789, "ReserveBalance": 1, "AvailableBalance": 2, "TaxRate": 10},
         "Crew": [{"CrewRole": "Refuel", "Activated": True, "Enabled": True}], "ShipPacks": [], "ModulePacks": []}
got = SQ.pick(stats)
check("CarrierStats keeps the carrier, its callsign, name, access, fuel, range and space",
      got and got["event"] == "CarrierStats" and got["CarrierID"] == 3708130560 and got["Callsign"] == "RRAX"
      and got["SpaceUsage"] == {"Cargo": 163, "FreeSpace": 23837} and got["timestamp"] == T, got)
check("and drops Finance, every balance and the tax rate", "Finance" not in got and "Balance" not in json.dumps(got)
      and "TaxRate" not in json.dumps(got), got)
buy = {"timestamp": T, "event": "CarrierBuy", "CarrierType": "FleetCarrier", "CarrierID": 3711837440,
       "BoughtAtMarket": 3223, "Location": "HIP 1", "SystemAddress": 1, "Price": 5000000000, "Variant": "CarrierDockB",
       "Callsign": "K8W-2TF"}
got = SQ.pick(buy)
check("CarrierBuy goes without its price", got and "Price" not in got and got["Callsign"] == "K8W-2TF", got)
order = {"timestamp": T, "event": "CarrierTradeOrder", "CarrierID": 3708130560, "BlackMarket": False,
         "Commodity": "steel", "Commodity_Localised": "Steel", "PurchaseOrder": 13, "Price": 2944}
got = SQ.pick(order)
check("a trade order keeps the commodity, the order and the price", got and got["PurchaseOrder"] == 13
      and got["Price"] == 2944 and got["Commodity_Localised"] == "Steel", got)
check("a cancelled order is an event too", SQ.pick({"timestamp": T, "event": "CarrierTradeOrder", "CarrierID": 1,
                                                    "CancelTrade": True, "Commodity": "steel"})["CancelTrade"] is True)
pp = {"timestamp": T, "event": "Powerplay", "Power": "Li Yong-Rui", "Rank": 341, "Merits": 2710036, "TimePledged": 1000}
check("Powerplay keeps power, rank, merits", SQ.pick(pp) == dict(pp))
haul = {"timestamp": T, "event": "ColonisationContribution", "MarketID": 3955,
        "Contributions": [{"Name": "$Steel_name;", "Name_Localised": "Steel", "Amount": 120}]}
check("a colonisation contribution keeps the tonnes by commodity", SQ.pick(haul)["Contributions"][0]["Amount"] == 120)
for name, extra in (("LoadGame", {"Commander": "Me", "FID": "F123", "Credits": 1}),
                    ("ReceiveText", {"From": "Someone", "Message": "hi", "Channel": "squadron"}),
                    ("Commander", {"Name": "Me", "FID": "F123"}), ("CarrierFinance", {"CarrierBalance": 1}),
                    ("CarrierBankTransfer", {"Deposit": 1}), ("MarketSell", {"TotalSale": 1})):
    check("%s never goes" % name, SQ.pick(dict({"timestamp": T, "event": name}, **extra)) is None)
check("a whitelisted event with a surprise field keeps only the known ones",
      "Finance" not in SQ.pick(dict(stats, Finance={"x": 1}, Surprise=1)) and "Surprise" not in SQ.pick(dict(stats, Surprise=1)))
check("no event is picked without its time", SQ.pick({"event": "Powerplay", "Power": "x"}) is None)

print("== the squadron, from the journal ==")
start = {"timestamp": T, "event": "SquadronStartup", "SquadronID": 40261, "SquadronName": "RADIO RAXXLA",
         "CurrentRank": 5, "CurrentRankName": "Elite Founder"}
sq = SQ.squadron_after(None, start)
check("SquadronStartup names the squadron", sq == {"id": 40261, "name": "RADIO RAXXLA", "rank": "Elite Founder"}, sq)
check("a promotion keeps the id and updates the rank",
      SQ.squadron_after(sq, {"timestamp": T, "event": "SquadronPromotion", "SquadronName": "RADIO RAXXLA",
                             "OldRankName": "Elite Founder", "NewRankName": "Leader"})["rank"] == "Leader")
check("anything else leaves it alone", SQ.squadron_after(sq, pp) == sq)

print("== the switch ==")
check("off by default, and only offered once a squadron is known",
      not SQ.wanted({}, sq) and not SQ.wanted({"squadron_share": True}, None) and SQ.wanted({"squadron_share": True}, sq))
check("the setting's default is off", SQ.SETTING == "squadron_share" and SQ.DEFAULT is False)
check("the notice names the four things and nothing else",
      all(w in SQ.NOTICE for w in ("location", "jumps", "orders", "Powerplay", "merits", "hauling"))
      and "credits" in SQ.NOTICE.lower() and "never" in SQ.NOTICE.lower(), SQ.NOTICE)

print("== the box: batched, once a minute, bounded ==")
box = SQ.Box(now=1000.0)
check("nothing to send with nothing in it", not box.due(1100.0))
box.add(SQ.pick(pp), now=1000.0)
box.add(SQ.pick(order), now=1001.0)
check("not due inside the minute", not box.due(1030.0))
check("due once the minute is up", box.due(1061.0))
body = box.take(40261, "The Announcer", now=1061.0)
check("the body is the squadron, the commander and the events, in order",
      body["squadronId"] == 40261 and body["cmdr"] == "The Announcer"
      and [e["event"] for e in body["events"]] == ["Powerplay", "CarrierTradeOrder"], body)
check("and the box is empty after", not box.events and not box.due(2000.0))
depot = {"timestamp": T, "event": "ColonisationConstructionDepot", "MarketID": 3955, "ConstructionProgress": 0.5,
         "ConstructionComplete": False, "ConstructionFailed": False, "ResourcesRequired": [{"Name": "$Steel_name;", "RequiredAmount": 100}]}
for i in range(5):
    box.add(SQ.pick(dict(depot, ConstructionProgress=0.5 + i * 0.1)), now=1100.0 + i)
check("a depot's progress is the latest per depot, not five copies",
      len(box.events) == 1 and box.events[0]["ConstructionProgress"] == 0.9, box.events)
for i in range(SQ.MOST + 50):
    box.add(SQ.pick(dict(order, Price=i)), now=1200.0 + i)
check("the box never holds more than MOST, the newest kept", len(box.events) == SQ.MOST and box.events[-1]["Price"] == SQ.MOST + 49,
      (len(box.events), box.events[-1]))
check("a Powerplay standing is the latest, not a history", sum(1 for e in box.events if e["event"] == "Powerplay") <= 1)
box.give_back(body["events"])
check("with the box full, events a failed send gives back are the oldest, so they are the ones that go",
      len(box.events) == SQ.MOST and box.events[0]["event"] == "CarrierTradeOrder" and box.events[0]["Price"] == 50)
box = SQ.Box(now=1000.0)
box.add(SQ.pick(haul), now=1000.0)
box.give_back(body["events"])
check("with room, they go to the front, in their order",
      [e["event"] for e in box.events] == ["Powerplay", "CarrierTradeOrder", "ColonisationContribution"], box.events)
check("nothing is picked up until the switch is on: add() refuses None", box.add(None) is False)

print("== the journal reader ==")
JDIR = os.path.join(TMP, "journals")
os.makedirs(JDIR)
lines = [json.dumps({"timestamp": T, "event": "Fileheader", "part": 1, "gameversion": "4.1"}),
         json.dumps({"timestamp": T, "event": "Commander", "FID": "F123", "Name": "The Announcer"}),
         json.dumps(start), json.dumps(stats), json.dumps(order), json.dumps(pp), json.dumps(haul),
         json.dumps({"timestamp": T, "event": "ReceiveText", "From": "X", "Message": "secret", "Channel": "squadron"})]
with open(os.path.join(JDIR, "Journal.2026-10-28T020000.01.log"), "w", encoding="utf-8") as handle:
    handle.write("\n".join(lines) + "\n")
w = J.JournalWatcher(JDIR)
w.poll()
check("the reader names the squadron", w.squadron == {"id": 40261, "name": "RADIO RAXXLA", "rank": "Elite Founder"}, w.squadron)
check("and keeps the picked events for the app, in order, nothing else",
      [e["event"] for e in w.squad_events] == ["SquadronStartup", "CarrierStats", "CarrierTradeOrder", "Powerplay",
                                                "ColonisationContribution"],
      [e.get("event") for e in w.squad_events])
check("none of them carries the FID or a balance", "F123" not in json.dumps(w.squad_events) and "Balance" not in json.dumps(w.squad_events))
taken = w.take_squad_events()
check("the app takes them and the reader's list is empty", len(taken) == 5 and w.squad_events == [])
check("the squadron events are read, not skipped", not J.skipped("CarrierTradeOrder") and not J.skipped("SquadronStartup")
      and not J.skipped("ColonisationContribution"))

try:
    import tkinter
    tkinter.Tk().destroy()
    HAVE_DISPLAY = True
except Exception as _exc:
    HAVE_DISPLAY = False
    print("  SKIP  the app needs a display (%s). Run it under xvfb-run." % _exc)

if HAVE_DISPLAY:
    import overlay as OV
    OV.foreground_is_game = lambda: None
    import edsmt as A
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as handle:
        json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JDIR,
                   "welcome_seen_version": A.APP_VERSION, "overlay_enabled": False}, handle)
    print("== in the app ==")
    check("a new install has the share off", A.DEFAULT_SETTINGS.get("squadron_share") is False)
    app = A.EDSMT()
    app.geometry("1400x900+0+0")
    app.updates.check = lambda *a, **k: None
    sent = []
    app.worker.submit = lambda tag, fn: sent.append((tag, fn))

    def pump(times=3):
        for _ in range(times):
            app.update_idletasks()
            app.update()

    def settle_until(cond, seconds=6.0):
        end = time.time() + seconds
        while time.time() < end:
            pump(1)
            if cond():
                return True
            time.sleep(0.02)
        return cond()

    pump(5)
    settle_until(lambda: getattr(app.watcher, "squadron", None) is not None)
    check("the reader in the app has read the squadron", app.watcher.squadron and app.watcher.squadron["id"] == 40261,
          getattr(app.watcher, "squadron", None))
    app.squad_sweep(now=time.time() + 120)
    check("with the switch off, nothing is sent and nothing is kept", not [s for s in sent if s[0] == SQ.TAG]
          and not app.squad_box.events, (len(sent), len(app.squad_box.events)))
    app.settings["squadron_share"] = True
    app.watcher.squad_events = [SQ.pick(pp), SQ.pick(order)]
    app.community.enabled = True
    app.community.base_url = app.community.DEFAULT_URL
    app.squad_sweep(now=time.time())
    check("switched on, the events go into the box", len(app.squad_box.events) == 2, app.squad_box.events)
    app.squad_sweep(now=time.time() + 120)
    mine = [s for s in sent if s[0] == SQ.TAG]
    check("and a minute later they are sent, tagged as their own, off the UI thread", len(mine) == 1, len(mine))
    app.take_squadron(False, "no connection (down)")
    check("a failed send keeps them for next time", len(app.squad_box.events) == 2, len(app.squad_box.events))
    app.take_squadron(True, json.dumps({"ok": True, "kept": 2}))
    win = A.SettingsWindow(app)
    pump(4)
    check("Settings > Sharing has the switch, named for what it does", "squadron_share" in win.toggles)
    win.destroy()
    try:
        app.destroy()
    except Exception:
        pass

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
