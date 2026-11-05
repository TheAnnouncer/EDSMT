"""1.10040: what the journal itself says about a Rhino session (#256, #257,
#266, #267, #273, #274).

  #256  a session's tonnes are what crossed to the ship, and the ship's own
        hold after the Rhino comes aboard checks them
  #257  the game's own mining statistics at each login, against the sessions
        in between
  #266  the Rhino's tonnes from the journal's Cargo count, as they arrive
  #267  cargo thrown out is tonnes lost to the session
  #273  trace mode: what the game writes to Status.json and Cargo.json during
        a session, into the support bundle - off by default
  #274  the price at a station before each of your own sales, and at your
        next read of it

Each is a plain function in journalrows.py; then the reader and the books
are driven through a session in the shapes the game writes, then the
windows show it.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_journal_rows.py
"""
import faulthandler
import json
import os
import sys
import tempfile
import time
import types
import zipfile

faulthandler.dump_traceback_later(240, exit=True)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-journalrows-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import journalrows as JR    # noqa: E402
import journal as JN        # noqa: E402
import survey as SV         # noqa: E402
import supportbundle as SB  # noqa: E402

JN.EVENT_LOG = None
fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


print("== #256: tonnes that crossed to the ship, checked by the ship's hold ==")
check("a session's tonnes are its transfers when there are any",
      JR.session_tonnes({"transferred": "Iridium:1239", "mined": "Iridium:1249"}) == (1239, "to ship"))
check("and what was refined when nothing went across",
      JR.session_tonnes({"mined": "Iridium:12;Platinum:3"}) == (15, "refined")
      and JR.session_tonnes({}) == (0, "refined"))
check("the ship's hold, before and after, written and read back",
      JR.hold_sides(JR.hold_value(0, 1239)) == (0, 1239) and JR.hold_sides(JR.hold_value(12, None)) == (12, None)
      and JR.hold_sides("") == (None, None) and JR.hold_sides("x>y") == (None, None))
check("the hold agrees when it rose by the tonnes moved across",
      JR.hold_check({"ship_hold": "0>1239", "transferred": "Iridium:1239"}) is True
      and JR.hold_check({"ship_hold": "50>740", "transferred": "Iridium:690"}) is True)
check("and differs when it did not", JR.hold_check({"ship_hold": "0>1200", "transferred": "Iridium:1239"}) is False)
check("with either end unseen there is no answer",
      JR.hold_check({"ship_hold": "0>", "transferred": "Iridium:5"}) is None and JR.hold_check({}) is None)
short, whole = JR.hold_words({"ship_hold": "0>1239", "transferred": "Iridium:1239"})
check("said plainly", short == "hold agrees" and "1,239 t" in whole and JR.hold_words({}) == ("", ""),
      (short, whole))

print("== #257: the game's own count at the next login ==")
STATS = {"timestamp": "2026-10-08T17:00:00Z", "event": "Statistics",
         "Mining": {"Mining_Profits": 1000000, "Quantity_Mined": 5000, "Materials_Collected": 100},
         "Trading": {"Market_Profits": 5}}
first = JR.mining_stats(STATS)
check("the Mining block of a Statistics event",
      first == {"when": "2026-10-08T17:00:00Z", "mined": 5000, "profits": 1000000, "materials": 100}, first)
check("nothing without one", JR.mining_stats({"event": "Statistics", "Trading": {}}) is None
      and JR.mining_stats(None) is None)
later = {"when": "2026-10-09T09:00:00Z", "mined": 6240, "profits": 380140195, "materials": 198}
SESSION = {"transferred": "Iridium:1239", "mined": "Iridium:1249", "lost": "Iridium:1", "credits": "379140195"}
audit = JR.statistics_audit(first, later, [SESSION])
check("the game's deltas against the session: 1,239 t across and 1 t thrown out make the 1,240",
      audit and audit["game"] == {"mined": 1240, "profits": 379140195, "materials": 98}
      and audit["booked"] == {"mined": 1239, "lost": 1, "profits": 379140195}
      and audit["agrees"] == {"mined": True, "profits": True}, audit)
check("said plainly, and that they agree", JR.audit_words(audit).endswith("They agree.")
      and "1,240 t mined" in JR.audit_words(audit), JR.audit_words(audit))
ring = JR.statistics_audit(first, dict(later, mined=6500), [SESSION])
check("mining outside a session shows as a difference, without alarm",
      ring["agrees"]["mined"] is False and "also counts mining outside a Rhino session" in JR.audit_words(ring))
check("two logins out of order give nothing", JR.statistics_audit(later, first, []) is None
      and JR.statistics_audit(None, later, []) is None and JR.audit_words(None) == "")

print("== #266: the Rhino's tonnes, from the journal's Cargo count ==")
check("a Cargo event states one hold", JR.cargo_tick({"event": "Cargo", "Vessel": "SRV", "Count": 46}) == ("SRV", 46)
      and JR.cargo_tick({"event": "Cargo", "Vessel": "Ship", "Count": 690}) == ("Ship", 690))
check("an Inventory adds up when there is no Count", JR.cargo_tick(
    {"event": "Cargo", "Vessel": "Ship", "Inventory": [{"Name": "iridium", "Count": 3}, {"Name": "gold", "Count": 2}]})
      == ("Ship", 5))
check("and nothing without either", JR.cargo_tick({"event": "Cargo", "Vessel": "SRV"}) is None)
check("the live line", JR.rhino_words(46) == "In the Rhino now: 46 t." and JR.rhino_words(None) == "")

print("== #267: cargo thrown out ==")
check("an EjectCargo", JR.ejected({"event": "EjectCargo", "Type": "iridium", "Count": 1, "Abandoned": True})
      == {"type": "iridium", "localised": "", "count": 1, "abandoned": True})
check("nothing thrown is nothing", JR.ejected({"event": "EjectCargo", "Type": "iridium", "Count": 0}) is None)
check("the line for a session", JR.lost_words({"lost": "Iridium:1"}) == "Thrown out: 1 t (Iridium 1)"
      and JR.lost_words({}) == "")

print("== #273: trace mode keeps a few fields, once a change ==")
RAW = json.dumps({"timestamp": "2026-10-08T17:06:03Z", "event": "Status", "Flags": 69222408, "Flags2": 0,
                  "GuiFocus": 0, "FireGroup": 1, "Cargo": 12.0, "Balance": 987654321, "Latitude": 1.234,
                  "Longitude": 5.678, "BodyName": "Secret Rock"})
entry, digest = JR.trace_entry("Status.json", RAW, None, "2026-10-08T17:06:04Z")
check("a Status.json rewrite: the time and the flags, nothing else",
      entry["fields"] == {"Flags": 69222408, "Flags2": 0, "GuiFocus": 0, "FireGroup": 1, "Cargo": 12.0}
      and entry["timestamp"] == "2026-10-08T17:06:03Z" and entry["at"] == "2026-10-08T17:06:04Z", entry)
check("no credits, position or names", not any(w in json.dumps(entry) for w in ("Balance", "Latitude", "Secret Rock")))
check("the same again is not a new line", JR.trace_entry("Status.json", RAW, digest, "later")[0] is None)
moved = json.loads(RAW)
moved["Flags2"] = 4
check("a change is", JR.trace_entry("Status.json", json.dumps(moved), digest, "later")[0] is not None)
cargo, _d = JR.trace_entry("Cargo.json", json.dumps({"timestamp": "t", "Vessel": "SRV", "Count": 3,
                                                     "Inventory": [{"Name": "iridium", "Count": 3, "Stolen": 0}]}))
check("a Cargo.json rewrite says which vessel and what it holds",
      cargo["fields"] == {"Vessel": "SRV", "Count": 3, "Inventory": [{"Name": "iridium", "Count": 3}]}, cargo)
check("a torn read or another file is no line", JR.trace_entry("Status.json", "{\"Fla", None)[0] is None
      and JR.trace_entry("Market.json", RAW, None)[0] is None)

print("== #274: the price before and after your own sale ==")
mark = JR.sale_mark("k", "Col 285 Sector KB-W c2-14", "Hub", "Iridium", 306005, "2026-10-08T23:51:09Z",
                    before={"sell": 306005, "seen": "2026-10-08T23:51:01Z"})
mark["folded"] = "iridium"
check("a sale is kept with the price the board showed before it",
      mark["before"] == 306005 and mark["after"] is None and JR.price_change(mark) is None)
check("a read of another station tells it nothing",
      JR.after_read([mark], "other", {"iridium": 1}, "2026-10-13T05:33:02Z") == 0)
check("nor a read from before the sale", JR.after_read([mark], "k", {"iridium": 1}, "2026-10-08T23:00:00Z") == 0)
check("the next read there does", JR.after_read([mark], "k", {"iridium": 194540}, "2026-10-13T05:33:02Z") == 1
      and mark["after"] == 194540)
check("and only once", JR.after_read([mark], "k", {"iridium": 5}, "2026-10-14T05:33:02Z") == 0
      and mark["after"] == 194540)
check("306,005 to 194,540 is 36% down", round(JR.price_change(mark)) == -36, JR.price_change(mark))
short, whole = JR.mark_words(mark)
check("said plainly", short == "next read -36%" and "194,540 Cr" in whole and "306,005 Cr" in whole,
      (short, whole))

print("== the reader and the books, through a session ==")
GAME = os.path.join(TMP, "game")
os.makedirs(GAME)


def ts(seconds):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(1791478800 + seconds))


EVENTS = [
    {"timestamp": ts(0), "event": "Commander", "FID": "F1", "Name": "Test Pilot"},
    {"timestamp": ts(0), "event": "LoadGame", "FID": "F1", "Commander": "Test Pilot", "Ship": "panthermkii",
     "ShipID": 7},
    {"timestamp": ts(0), "event": "Statistics", "Mining": {"Mining_Profits": 1000, "Quantity_Mined": 50,
                                                           "Materials_Collected": 4}},
    {"timestamp": ts(1), "event": "Loadout", "Ship": "panthermkii", "ShipID": 7, "CargoCapacity": 5},
    {"timestamp": ts(2), "event": "Location", "StarSystem": "Wyrd", "Body": "Wyrd A 1", "BodyType": "Planet",
     "Docked": False, "Latitude": 1.0, "Longitude": 2.0},
    {"timestamp": ts(3), "event": "Cargo", "Vessel": "Ship", "Count": 0, "Inventory": []},
    {"timestamp": ts(10), "event": "LaunchSRV", "SRVType": "mev_rhino", "SRVType_Localised": "SRV Rhino",
     "Loadout": "galactic", "ID": 98, "PlayerControlled": True},
]
for k in range(6):
    EVENTS.append({"timestamp": ts(20 + k), "event": "MiningRefined", "Type": "$iridium_name;",
                   "Type_Localised": "Iridium"})
    EVENTS.append({"timestamp": ts(20 + k), "event": "Cargo", "Vessel": "SRV", "Count": k + 1})
EVENTS += [
    {"timestamp": ts(40), "event": "CargoTransfer", "Transfers": [
        {"Type": "iridium", "Type_Localised": "Iridium", "Count": 5, "Direction": "toship"}]},
    {"timestamp": ts(41), "event": "Cargo", "Vessel": "SRV", "Count": 1},
    {"timestamp": ts(50), "event": "EjectCargo", "Type": "iridium", "Type_Localised": "Iridium", "Count": 1,
     "Abandoned": True},
    {"timestamp": ts(72), "event": "DockSRV", "SRVType": "mev_rhino", "SRVType_Localised": "SRV Rhino", "ID": 98},
    {"timestamp": ts(78), "event": "Cargo", "Vessel": "Ship", "Count": 5},
]
with open(os.path.join(GAME, "Journal.2026-10-08T170000.01.log"), "w", encoding="utf-8", newline="") as handle:
    for event in EVENTS:
        handle.write(json.dumps(event) + "\r\n")
reader = JN.JournalWatcher(GAME)
told = []
reader.on_rewrite = lambda name, raw: told.append(name)
with open(os.path.join(GAME, "Status.json"), "w", encoding="utf-8") as handle:
    handle.write(RAW)
reader.poll()
notes = reader.drain_runs()
check("the Rhino's last tick is what the journal said", reader.srv_total == 1, reader.srv_total)
check("the launch carries the ship's hold as it went out",
      [n.get("ship_t") for n in notes if n["event"] == "SRVLaunch"] == [0])
check("the thrown-out tonne, the ship's hold after the dock and the login's statistics reach the books",
      [n["event"] for n in notes if n["event"] in ("Ejected", "ShipHold", "Statistics")]
      == ["Statistics", "Ejected", "ShipHold"], [n["event"] for n in notes])
check("the reader hands Status.json's text to trace mode when asked", "Status.json" in told, told)
BOOKS = os.path.join(TMP, "books")
books = SV.Earnings(BOOKS)
for note in notes:
    books.observe(note)
row = books.sessions[-1]
check("the session: 6 t refined, 5 t across, the hold 0 then 5, 1 t thrown out",
      row["mined"] == "Iridium:6" and row["transferred"] == "Iridium:5" and row["ship_hold"] == "0>5"
      and row["lost"] == "Iridium:1", {k: row[k] for k in ("mined", "transferred", "ship_hold", "lost")})
check("its tonnes are the 5 that went across, and the hold agrees",
      JR.session_tonnes(row) == (5, "to ship") and JR.hold_check(row) is True)
check("the login's statistics are kept for the next", books.stats_last["mined"] == 50 and not books.audits)
NEXT = {"event": "Statistics", "when": ts(3600), "cmdr": "Test Pilot",
        "mining": {"when": ts(3600), "mined": 56, "profits": 1000, "materials": 4}}
books.observe(NEXT)
check("at the next login the sessions between are put against them: 5 across and 1 thrown out make 6",
      len(books.audits) == 1 and books.audits[0]["agrees"]["mined"] is True
      and books.audits[0]["booked"]["mined"] == 5, books.audits)
again = SV.Earnings(BOOKS)
for note in notes + [NEXT]:
    again.observe(note)
row = again.sessions[-1]
check("read again from the top after a restart, nothing is booked twice",
      len(again.sessions) == 1 and row["lost"] == "Iridium:1" and row["ship_hold"] == "0>5"
      and len(again.audits) == 1, (len(again.sessions), row["lost"], len(again.audits)))
book2 = SV.Earnings(os.path.join(TMP, "books2"))
book2.observe({"event": "Ejected", "when": ts(5), "commodity": "Gold", "count": 3})
check("cargo thrown out with no session open is no session's", not book2.sessions)

caught = JN.JournalWatcher(GAME)
caught.catch_up_step(1 << 20)
live = JN.JournalWatcher(GAME)
mine = lambda name, raw: None  # noqa: E731
live.on_rewrite = mine
live.adopt(caught)
check("a reader taking over one that caught up keeps its own trace hook", live.on_rewrite is mine)

print("== the price book keeps your sales and the price after ==")
MB_DIR = os.path.join(TMP, "markets")
mb = SV.MarketBook(MB_DIR)
mb.note_market({"system": "Col 285", "station": "Hub", "when": "2026-10-08T23:51:01Z",
                "items": [{"commodity": "Iridium", "sell": 306005, "demand": 9000}]})
mb.note_sale("Col 285", "Hub", "Iridium", 306005, "2026-10-08T23:51:09Z")
mb.note_sale("Col 285", "Hub", "Iridium", 306005, "2026-10-08T23:51:09Z")
check("a sale is kept once, with the board's price before it",
      len(mb.sales) == 1 and mb.sales[0]["before"] == 306005 and mb.sales[0]["after"] is None, mb.sales)
mb.note_market({"system": "Col 285", "station": "Hub", "when": "2026-10-13T05:33:02Z",
                "items": [{"commodity": "Iridium", "sell": 194540, "demand": 19034}]})
check("the next read of that market gives the price after", mb.sales[0]["after"] == 194540)
mb.save()
check("and it is kept", SV.MarketBook(MB_DIR).sales[0]["after"] == 194540)
check("a station's sales over a session",
      len(mb.sales_at("hub", "2026-10-08T00:00:00Z", "2026-10-09T00:00:00Z")) == 1
      and not mb.sales_at("Hub", "2026-10-10T00:00:00Z"))

print("== trace mode writes only while a session is open, and the bundle carries it ==")
import edsmt as A  # noqa: E402

A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
check("trace mode is off for a new install", A.DEFAULT_SETTINGS.get("trace_files") is False)
check("and has its note in Settings", "support" in A.SETTING_TIPS.get("trace_files", ""))
fake = types.SimpleNamespace(settings={"trace_files": False}, earnings=types.SimpleNamespace(rhino={"id": 1}),
                             watcher=types.SimpleNamespace(rhino_out=True), _trace_last={})
trace = os.path.join(A.DATA_DIR, SB.TRACE_LOG)
check("off, nothing is written", A.EDSMT.trace_rewrite(fake, "Status.json", RAW) is False
      and not os.path.exists(trace))
fake.settings["trace_files"] = True
fake.earnings.rhino, fake.watcher.rhino_out = None, False
check("on, with no session open, nothing is written either",
      A.EDSMT.trace_rewrite(fake, "Status.json", RAW) is False and not os.path.exists(trace))
fake.earnings.rhino = {"id": 1}
wrote = [A.EDSMT.trace_rewrite(fake, "Status.json", RAW), A.EDSMT.trace_rewrite(fake, "Status.json", RAW),
         A.EDSMT.trace_rewrite(fake, "Status.json", json.dumps(moved))]
lines = open(trace, encoding="utf-8").read().splitlines()
check("on, during a session, a line for each change", wrote == [True, False, True] and len(lines) == 2, (wrote, lines))
check("with no credits, position or names in it",
      not any(w in open(trace, encoding="utf-8").read() for w in ("Balance", "Latitude", "Secret Rock")))
zipped = SB.make_bundle(os.path.join(TMP, "out"), A.DATA_DIR, {"trace_files": True}, "1.10040")
with zipfile.ZipFile(zipped) as bundle:
    check("the support bundle carries the trace", SB.TRACE_LOG in bundle.namelist()
          and "69222408" in bundle.read(SB.TRACE_LOG).decode("utf-8"), bundle.namelist())
os.remove(trace)
zipped = SB.make_bundle(os.path.join(TMP, "out2"), A.DATA_DIR, {}, "1.10040")
with zipfile.ZipFile(zipped) as bundle:
    check("and without one, the bundle is as it was", SB.TRACE_LOG not in bundle.namelist())

try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as exc:
    print("  SKIP  the rest needs a display (%s). Run it under xvfb-run." % exc)
    print()
    print("FAILURES:", len(fails))
    sys.exit(1 if fails else 0)

print("== the Earnings window shows it ==")
import overlay as OV  # noqa: E402
OV.foreground_is_game = lambda: None
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
EMPTY = os.path.join(TMP, "nojournal")
os.makedirs(EMPTY, exist_ok=True)
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as handle:
    json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": EMPTY,
               "welcome_seen_version": A.APP_VERSION}, handle)
app = A.EDSMT()
app.geometry("1400x900+0+0")
app.updates.check = lambda *args, **kwargs: None


def pump(seconds=0.3):
    until = time.time() + seconds
    while True:
        app.update_idletasks()
        app.update()
        if time.time() >= until:
            break
        time.sleep(0.01)


pump(0.6)
check("the app hangs trace mode on its reader", app.watcher.on_rewrite == app.trace_rewrite)
row = dict({k: "" for k in SV.SESSION_FIELDS}, id="done1", kind=SV.RHINO, started="2026-10-08T17:06:03Z",
           ended="2026-10-08T23:51:09Z", closed="2026-10-08T23:51:09Z", system="Col 285", body="Col 285 A 1",
           station="Hub", mined="Iridium:1249", transferred="Iridium:1239", ship_hold="0>1239",
           lost="Iridium:1", sold="Iridium:1239", credits="379140195", ended_by="docked")
app.earnings.sessions.append(row)
app.earnings.save()
app.earnings.audits = [audit]
app.market_book.sales = [dict(mark, station="Hub", when="2026-10-08T23:51:09Z")]
ledger = app.open_earnings() or app.ledger
ledger = app.docked_tools.get("earnings") or ledger
ledger.show_page("Sessions")
ledger.refresh()
pump(0.4)
index = next(i for i in range(ledger.scroller.row_count()) if ledger.scroller.payload(i).get("id") == "done1")
cells = [ledger.scroller.cell_text(index, c) for c in range(len(A.RUN_HEADERS))]
to_ship = cells[A.RUN_HEADERS.index("To ship")]
check("To ship says the ship's hold agrees, and why in full",
      "hold agrees" in to_ship[0] and "agrees with the tonnes moved across" in to_ship[1], to_ship)
check("Mined says what was thrown out", "Thrown out: 1 t" in cells[A.RUN_HEADERS.index("Mined")][0])
check("t/hr is from the tonnes that went across",
      cells[A.RUN_HEADERS.index("t/hr")][0] == "%.1f t" % (1239 / SV.session_hours(row)),
      cells[A.RUN_HEADERS.index("t/hr")])
sold_at = cells[A.RUN_HEADERS.index("Sold at")]
check("Sold at gives the price at your next read there",
      "next read -36%" in sold_at[0] and "194,540 Cr" in sold_at[1], sold_at)
check("the summary carries the game's own count at the last login",
      "They agree." in ledger.summary.cget("text"), ledger.summary.cget("text"))
app.watcher.rhino_out, app.watcher.srv_total = True, 46
live = A.current_session(app, ledger._rows)
check("with no session open, no Rhino line", app.earnings.rhino is None
      and "In the Rhino now" not in live["note"])
app.earnings.start("Wyrd", "Wyrd A 1", "Test Pilot", SV.utc_now(), by="button")
live = A.current_session(app, ledger._rows)
check("This session says what the Rhino holds now, from the journal",
      "In the Rhino now: 46 t." in live["note"], live["note"])
app.destroy()

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
