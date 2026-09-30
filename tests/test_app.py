"""The window, driven by a synthetic journal. No display, no Tk, no game."""
import os, sys, json, time, tempfile, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "stubs"))
import _ctkstub  # noqa
sys.path.insert(0, os.path.dirname(HERE))

TMP = tempfile.mkdtemp(prefix="edsmt-app-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
import edsmt as A, survey as SV, journal as JN  # noqa
# Copies go to the Windows clipboard directly on Windows. These checks
# read what a window put on ITS clipboard, so they take the Tk path
# everywhere - and never touch the real clipboard on the machine running them.
A._windows_clipboard = lambda *args, **kwargs: False
A.DATA_DIR = os.path.join(TMP, "data"); os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JN.EVENT_LOG = os.path.join(A.DATA_DIR, "events.log")

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)

# ---- a synthetic Ega 1 session ----
JD = os.path.join(TMP, "journals"); os.makedirs(JD)
J = os.path.join(JD, "Journal.2026-09-09T100000.01.log")
def emit(*events):
    with open(J, "a", encoding="utf-8") as fh:
        for e in events: fh.write(json.dumps(e) + "\n")
def status(flags, **kw):
    d = {"timestamp": "2026-09-09T10:00:00Z", "event": "Status", "Flags": flags}
    d.update(kw)
    open(os.path.join(JD, "Status.json"), "w", encoding="utf-8").write(json.dumps(d))

R = 2_100_000.0
emit({"timestamp":"2026-09-09T09:59:00Z","event":"Fileheader","gameversion":"4.4.1.1","part":1},
     {"timestamp":"2026-09-09T09:59:01Z","event":"Commander","Name":"Jameson","FID":"F1"},
     {"timestamp":"2026-09-09T09:59:30Z","event":"ApproachBody","StarSystem":"Ega","Body":"Ega 1"},
     {"timestamp":"2026-09-09T09:59:31Z","event":"Scan","BodyName":"Ega 1","Radius":R,
      "SurfaceTemperature":214.5},
     {"timestamp":"2026-09-09T09:59:40Z","event":"SAASignalsFound","BodyName":"Ega 1",
      "Signals":[{"Type":"$SAA_SignalType_PlanetaryMining;",
                  "Type_Localised":"Planetary Mining Locations","Count":6}]})
status(A.VK and 2 | (1 << 21) | (1 << 26), Latitude=12.5, Longitude=-45.5,
       Heading=30, BodyName="Ega 1", PlanetRadius=R)

app = A.EDSMT.__new__(A.EDSMT)          # no Tk window
app.settings = dict(A.DEFAULT_SETTINGS)
app.store = SV.Survey(A.DATA_DIR)
app.watcher = JN.JournalWatcher(JD)
app.game = None
app.selected = None
app._known_body = None

print("== the journal fills everything in ==")
state = app.watcher.poll()
app.game = state
check("system picked up", state.system == "Ega", state.system)
check("body picked up", state.body == "Ega 1", state.body)
check("position picked up", (state.lat, state.lon) == (12.5, -45.5))
check("heading picked up", state.heading == 30)
check("radius picked up", state.radius_m == R)
check("temperature picked up", state.body_temperature() == 214.5)
check("DSS says six mining locations", state.mining_signals() == 6,
      state.mining_signals())
check("cmdr from the journal", state.cmdr == "Jameson")
check("the app knows where it is", app.here() == ("Ega", "Ega 1"), app.here())

print("== logging a mining location signal ==")
app.location_box = _ctkstub.ctk.CTkComboBox(None, values=["1"]); app.location_box.set("1")
app.fields = {k: _ctkstub.ctk.CTkComboBox(None, values=[]) for k in
              ("commodity", "rigs", "density", "amount")}
for box in app.fields.values(): box.set("")
messages = []
app.say = lambda text, colour=None: messages.append(text)
app.refresh_locations = lambda: None
app.refresh_deposits = lambda: None
app.refresh_commodities = lambda: None
app.redraw = lambda: None
app.share = lambda record: None

app.log_location()
loc = app.store.location("Ega", "Ega 1", "1")
check("signal 1 recorded", loc is not None)
check("its position is where you stood", loc["lat"] == "12.500000", loc["lat"])
check("body radius kept for distance maths", loc["radius_m"] == "2100000")
check("temperature kept", loc["temperature_k"] == "214.5")

print("== recording what the signal offers ==")
app.store.set_location("Ega", "Ega 1", "1",
                       commodities=["Copper", "Haematite", "Lithium",
                                    "Palladium", "Uranium", "Sapphire"],
                       depleted=["Sapphire"])
loc = app.store.location("Ega", "Ega 1", "1")
check("six offered", len(app.store.offered(loc)) == 6)
check("sapphire flagged depleted", app.store.worked_out(loc) == ["Sapphire"])
check("commodities the patch notes never mentioned are accepted",
      "Haematite" in app.store.offered(loc) and "Copper" in app.store.offered(loc))

print("== marking a deposit: one key, nothing set up first ==")
# 1.10031: "you must fill all the information in to do a deposit as we been
# getting people forgetting the density and amount". Without them it is
# refused - and then with them it goes in.
app.fields["commodity"].set("Haematite")
app.mark_deposit()
check("with rigs, amount and density blank, nothing is marked",
      app.store.at("Ega", "Ega 1", "1") == [])
app.fields["rigs"].set("3")
app.fields["amount"].set("High")
app.fields["density"].set("Medium")
# After a mark the three boxes are cleared for the next deposit (checked in
# test_field). The rest of this session marks deposit after deposit with
# the same three, so they are left filled here.
app.clear_deposit_boxes = lambda: None
app.mark_deposit()
found = app.store.at("Ega", "Ega 1", "1")
check("one deposit", len(found) == 1, len(found))
check("commodity recorded", found[0]["commodity"] == "Haematite")
check("position is absolute, not a bearing", found[0]["lat"] == "12.500000")
check("no centre was ever needed",
      "bearing" not in found[0] and "range_m" not in found[0])
check("rigs recorded as typed", found[0]["rigs"] == "3", found[0]["rigs"])
check("temperature carried", found[0]["temperature_k"] == "214.5")
check("cmdr carried", found[0]["cmdr"] == "Jameson")
check("it says what it did", any("Haematite" in m for m in messages), messages[-1:])

print("== drive 896m and mark another ==")
import math
lat2 = 12.5 + math.degrees(896 * math.cos(math.radians(30)) / R)
lon2 = -45.5 + math.degrees(896 * math.sin(math.radians(30)) / (R * math.cos(math.radians(12.5))))
status(2 | (1 << 21) | (1 << 26), Latitude=lat2, Longitude=lon2, Heading=95,
       BodyName="Ega 1", PlanetRadius=R)
app.game = app.watcher.poll()
app.fields["commodity"].set("Haematite")
app.fields["rigs"].set("4")
app.mark_deposit()
check("two deposits", len(app.store.at("Ega", "Ega 1", "1")) == 2)
check("rigs recorded when you know them",
      app.store.at("Ega", "Ega 1", "1")[1]["rigs"] == "4")

print("== distances are worked out from where you are, live ==")
near = app.store.near("Ega", "Ega 1", 12.5, -45.5, R)
check("nearest first", near[0]["range_m"] < near[1]["range_m"])
check("the first is on top of you", near[0]["range_m"] < 1.0, near[0]["range_m"])
check("the second is about 896m", abs(near[1]["range_m"] - 896) < 5,
      near[1]["range_m"])
check("bearing to it is about 30", abs(near[1]["bearing"] - 30) < 1,
      near[1]["bearing"])
# and from the other end
near2 = app.store.near("Ega", "Ega 1", lat2, lon2, R)
check("from the far end the order flips", near2[0]["range_m"] < 1.0)
check("looking back is about 210 degrees", abs(near2[1]["bearing"] - 210) < 1,
      near2[1]["bearing"])

print("== the scanner naming a commodity fills the box ==")
# Haematite used to stand in here, and it is not one of the 4.4.1.0 thirteen
# - so find_commodity could never return it, detected_type was always None,
# and the assertion "in (Haematite, None)" passed for ever no matter what
# the reader did. It certified nothing. Olivine is a commodity the game
# really names, so this one can fail.
check("Olivine is a commodity 4.4.1.0 actually has",
      "Olivine" in A.EDO.SURFACE_COMMODITIES)
check("and Haematite, which used to stand here, is not",
      "Haematite" not in A.EDO.SURFACE_COMMODITIES)
emit({"timestamp":"2026-09-09T10:05:00Z","event":"SurfaceDepositProspected",
      "Deposit":{"Type":"$olivine_name;","Type_Localised":"Olivine"}})
app.game = app.watcher.poll()
check("scanner reading picked up", app.game.detected_type == "Olivine",
      app.game.detected_type)
app._autofilled = {}
app.fields["commodity"].set("")
A.EDSMT._autofill(app, "commodity", app.game.detected_type)
check("and it reaches the box without anybody typing it",
      app.fields["commodity"].get() == "Olivine",
      app.fields["commodity"].get())
app.fields["commodity"].set("")

print("== a commodity nobody listed is still recorded ==")
app.fields["commodity"].set("")
app.fields["rigs"].set("2")
app.fields["commodity"].set("Unobtainium")
app.mark_deposit()
# Standing on the Olivine just marked: another commodity on the same spot
# is asked about first - UPDATE renames, MARK again adds one of its own.
check("another commodity on the same spot is asked about, not added",
      not any(d["commodity"] == "Unobtainium"
              for d in app.store.at("Ega", "Ega 1"))
      and "rename" in messages[-1], messages[-1:])
app.mark_deposit()
check("recorded anyway",
      any(d["commodity"] == "Unobtainium" for d in app.store.at("Ega", "Ega 1")))
check("and remembered for next time", "Unobtainium" in SV.KNOWN_COMMODITIES)

print("== fixing one you got wrong ==")
# The real case: F10 was pressed while the signal box still said 1, and the
# commodity was whatever the box happened to hold. Both have to be
# correctable after the fact, without going near a CSV.
target = app.store.at("Ega", "Ega 1", "1")[0]
app.selected = target
app.on_pick = lambda d: None
app.refresh_locations = lambda: None
app.refresh_deposits = lambda: None
app.redraw = lambda: None
fixed = app.deposit_edited(target["id"], {
    "location": "3", "commodity": "Monazite", "rigs": "6",
    "density": "High", "notes": "was logged under signal 1"})
check("it moved to the right signal", fixed["location"] == "3", fixed["location"])
check("the commodity was corrected", fixed["commodity"] == "Monazite")
check("rigs set", fixed["rigs"] == "6", fixed["rigs"])
check("density set", fixed["density"] == "High")
check("the note stuck", fixed["notes"].startswith("was logged"))
check("its position was not touched", fixed["lat"] == target["lat"])
check("and its id did not change", fixed["id"] == target["id"])
check("it is no longer in signal 1",
      all(d["id"] != target["id"] for d in app.store.at("Ega", "Ega 1", "1")))
check("it is in signal 3 now",
      any(d["id"] == target["id"] for d in app.store.at("Ega", "Ega 1", "3")))
check("the edit survives on disk",
      [d for d in SV.Survey(A.DATA_DIR).deposits
       if d["id"] == target["id"]][0]["commodity"] == "Monazite")
check("editing something already deleted says so rather than crashing",
      app.deposit_edited("no-such-id", {"rigs": "2"}) is None)

again = fixed

print("== deleting ==")
before = len(app.store.deposits)
app.selected = again
app.delete_selected()
check("one fewer", len(app.store.deposits) == before - 1)
check("deleting it twice is not an error",
      app.delete_deposit(again["id"]) is False)

print("== the signal picker goes as high as the game does ==")
choices = app.signal_choices()
check("forty signals offered as standard", len(choices) >= 40, len(choices))
check("numbered from one", choices[0] == "1")
check("no gaps", choices == [str(n) for n in range(1, len(choices) + 1)])

# A body with more signals than the standard list: the picker has to grow,
# because a number that cannot be selected is a find that cannot be recorded.
app.store.set_location("Ega", "Ega 1", "47", lat=12.4, lon=-45.6,
                       commodities=["Haematite"], cmdr="Jameson")
grown = app.signal_choices()
check("a signal numbered 47 extends the list", "47" in grown, len(grown))
check("and nothing below it went missing",
      grown[:40] == [str(n) for n in range(1, 41)])

print("== best patch, and telling everyone a site is stripped ==")
class _Plan:
    picked = None
    def select(self, deposit_id): _Plan.picked = deposit_id
app.plan = _Plan()
app.on_pick = lambda d: None
app.signal = lambda: "1"
messages.clear()
app.show_best_patch()
check("it names a patch", any("Best patch" in m for m in messages), messages[-1:])
check("and points the map at one of its deposits", _Plan.picked is not None)

sent = []
class _Comm:
    ready = True
    def report_depletion(self, cmdr, system, planet, spot, worked_out=True):
        sent.append((cmdr, system, planet, spot)); return True
app.community = _Comm()
messages.clear()
app.mark_worked_out()
check("depletion reported", sent == [("Jameson", "Ega", "Ega 1", "1")], sent)
check("and it says so", any("worked out" in m for m in messages), messages[-1:])

app.community = type("Off", (), {"ready": False})()
messages.clear()
app.mark_worked_out()
check("with sharing off it says so rather than failing silently",
      any("Settings" in m for m in messages), messages[-1:])

print("== what gets shared carries no invented centre ==")
shared = []
app.community = type("Cap", (), {
    "ready": True,
    "upload": lambda self, cmdr, rows: shared.extend(rows) or True})()
app.settings["community_auto_share"] = True
del app.share
record = app.store.at("Ega", "Ega 1", "1")[0]
app.share(record)
check("something was shared", len(shared) == 1, shared)
check("no direction", "direction" not in shared[0], sorted(shared[0]))
check("no distance", "distance" not in shared[0], sorted(shared[0]))
check("the position went instead",
      shared[0]["lat"] == float(record["lat"])
      and shared[0]["lon"] == float(record["lon"]), shared[0].get("lat"))
check("uncounted rigs stay uncounted rather than becoming one",
      shared[0]["rigs"] == int(float(record["rigs"] or 0)), shared[0]["rigs"])

print("== you can still tidy up with the game shut ==")
# Marking a deposit happens in the SRV. Correcting one happens later, at the
# desk, with Elite closed - and if the map goes blank there is nothing to
# double-click and nothing can be fixed.
app.game = None
check("it still knows the last body", app.here() == ("Ega", "Ega 1"), app.here())
check("and that was written to settings",
      app.settings.get("last_body") == "Ega 1", app.settings.get("last_body"))
centre = app.centre_of_record("Ega", "Ega 1")
check("the map has something to centre on", centre is not None, centre)
check("which is on the body, not at zero",
      centre is not None and abs(centre[0] - 12.5) < 0.2, centre)
check("a body with nothing recorded has no centre",
      app.centre_of_record("Ega", "Ega 9") is None)
check("and neither has nowhere at all", app.centre_of_record("", "") is None)

drawn = []
app.plan = type("P", (), {"show": lambda self, rows=None, **kw: drawn.append(rows),
                          "select": lambda self, i: None})()
app.draw_overlay = lambda rows, heading, **kw: None
app.refresh_location_note = lambda: None
del app.redraw
app.redraw()
check("deposits are still drawn with the game shut", drawn and drawn[0], drawn[:1])

print("== it all survives a restart ==")
reopened = SV.Survey(A.DATA_DIR)
check("deposits persisted", len(reopened.deposits) == before - 1)
check("the signal persisted", reopened.location("Ega", "Ega 1", "1") is not None)
check("its commodity list persisted",
      len(reopened.offered(reopened.location("Ega", "Ega 1", "1"))) == 6)

print("== search results arrive even when the journal is broken ==")
# The Find window came back empty for ever, and nothing was wrong with the
# server, the network or the search. The worker queue was drained inside
# report_online - a function about the GAME - so the moment watcher.poll()
# raised, tick jumped to its except block and the answer already sitting in
# the queue was never collected. Searching a shared map has nothing to do
# with whether Elite is running.
class _Q:
    """A worker that has one finished search waiting to be picked up."""
    def __init__(self, payload):
        self.payload = payload
        self.drained = 0
    def drain(self):
        self.drained += 1
        out, self.payload = self.payload, []
        return out

class _Finder:
    def __init__(self): self.got = []
    def winfo_exists(self): return True
    def results(self, tag, payload, ok=True): self.got.append((tag, payload, ok))

class _BrokenWatcher:
    cmdr = ""
    def poll(self): raise IOError("journal folder has gone")
    def set_directory(self, *a, **k): pass

app = A.EDSMT.__new__(A.EDSMT)          # no Tk, no window, just the methods
app.worker = _Q([("sites", True, '{"sites": []}')])
app.finder = _Finder()
app.settings = dict(A.DEFAULT_SETTINGS)
said = []
app.say = lambda text, colour=None: said.append(text)

app.collect_results()
check("a finished search is handed to the Find window",
      app.finder.got and app.finder.got[0][0] == "sites", app.finder.got)

# and now the part that actually broke: the journal blowing up mid-tick
app.worker = _Q([("search", True, '{"deposits": []}')])
app.finder = _Finder()
app.watcher = _BrokenWatcher()
app.game = None
app.update_telemetry = lambda *a, **k: None
app.report_online = lambda *a, **k: None
app.hotkeys = type("H", (), {"drain": staticmethod(lambda: [])})()
scheduled = []
app.after = lambda ms, fn: scheduled.append(ms)

app.tick()
check("a journal that raises does not swallow the results",
      app.finder.got and app.finder.got[0][0] == "search", app.finder.got)
check("and the app said so rather than failing silently",
      any("Journal problem" in t for t in said), said)
check("and the next tick is still scheduled", scheduled == [700], scheduled)

# a Find window closed while its answer was in flight
class _Dead(_Finder):
    def winfo_exists(self): return False
app.worker = _Q([("sites", True, '{"sites": []}'),
                 ("share", True, "1 deposit shared")])
app.finder = _Dead()
said.clear()
app.collect_results()
check("a closed Find window is skipped, not crashed into",
      app.finder.got == [], app.finder.got)
check("and the rest of the queue is still delivered",
      any("Shared" in t for t in said), said)

with open(os.path.join(os.path.dirname(HERE), "edsmt.py"),
          encoding="utf-8") as _fh:
    src = _fh.read()
body = src.split("def report_online")[1].split("\n    def ")[0]
check("the drain is no longer buried inside report_online",
      "worker.drain" not in body)
check("tick collects results in its finally block",
      "self.collect_results()" in src.split("def tick")[1].split("\n    def ")[0])

print("== every signal row has an edit button, including the empty ones ==")
# It vanished on any row whose text was long. "Signal 2  nothing marked yet
# no list recorded" is wider than "Signal 3  4 deposits  Magnesite", and an
# expanding label packed BEFORE the button pushed it off the edge - so the
# rows that most needed editing, the ones logged by mistake with nothing in
# them, were the only rows without a way to fix them.
block = src.split("def refresh_locations")[1].split("\n    def ")[0]
edit_at = block.find('text="edit"')
label_at = block.find('command=lambda n=number: self.choose_signal(n)')
check("the row has an edit button at all", edit_at > 0)
check("it is packed before the label that expands", 0 < edit_at < label_at,
      (edit_at, label_at))
check("and anchored right, so it keeps its width",
      'side="right"' in block[edit_at:edit_at + 400], block[edit_at:edit_at + 400])
check("it is built for every row, not just the selected one",
      block.count('text="edit"') == 1 and "for row in rows:" in block)

print("== Find always says what happened ==")
# "Searching..." and then silence, for ever. Every one of these calls returns
# False when the client cannot send, and that return value was thrown away -
# so a request that never left the machine looked exactly like one in flight.
# A raise inside a Tk button command is swallowed by Tk too, which makes a
# dead button look like a slow one.
class _Comm:
    """A client that takes anything. Records what the window asked it for."""
    def __init__(self, ok=True, boom=False, staff=False):
        self.ok, self.boom, self.can_read = ok, boom, True
        self.can_verify = staff
        self.calls = []
    def sites(self, **k):
        self.calls.append(("sites", k))
        if self.boom:
            raise IOError("no route to host")
        return self.ok
    def search(self, **k):
        self.calls.append(("search", k)); return self.ok
    def intact(self, **k):
        self.calls.append(("intact", k)); return self.ok
    def best_prices(self, **k):
        self.calls.append(("prices", k)); return self.ok
    def sell(self, **k):
        self.calls.append(("sell", k)); return self.ok
    def commodities(self, **k):
        self.calls.append(("commodities", k)); return self.ok
    def verify(self, *a, **k):
        self.calls.append(("verify", a, k)); return self.ok

class _Narrow:
    """The client as edonline actually declares it - named parameters only.

    The window must not hand this one a keyword it has never heard of: a
    TypeError inside a Tk button command is swallowed, and the button
    stops working with nothing said anywhere.
    """
    can_read = True
    can_verify = False
    def __init__(self): self.calls = []
    def sites(self, commodity="", min_rigs=0, min_types=0, max_age_days=0,
              limit=50, near=None, within_ly=0, system="",
              verified_only=False, include_depleted=False, body="", name=""):
        self.calls.append(("sites", dict(commodity=commodity, near=near,
                                         within_ly=within_ly, system=system,
                                         verified_only=verified_only,
                                         include_depleted=include_depleted,
                                         body=body, name=name)))
        return True
    def search(self, commodity="", system="", limit=50, near=None, within_ly=0):
        self.calls.append(("search", dict(commodity=commodity, system=system,
                                          near=near, within_ly=within_ly)))
        return True
    def intact(self, commodity="", min_rigs=0, min_types=0,
               min_confidence=0.5, limit=50, near=None, within_ly=0):
        self.calls.append(("intact", dict(commodity=commodity, near=near,
                                          within_ly=within_ly)))
        return True
    def commodities(self):
        self.calls.append(("commodities", {}))
        return True
    def best_prices(self, commodity="", near_system="", limit=20,
                    near=None, within_ly=0):
        self.calls.append(("prices", dict(commodity=commodity,
                                          near_system=near_system,
                                          near=near, within_ly=within_ly)))
        return True
    def sell(self, commodity, near_system="", limit=20, near=None, within_ly=0):
        self.calls.append(("sell", dict(commodity=commodity,
                                        near_system=near_system,
                                        near=near, within_ly=within_ly)))
        return True

class _Find(A.FindWindow):
    def __init__(self, comm):
        import _ctkstub as C
        self.app = type("App", (), {})()
        self.app.community = comm
        self.app.settings = dict(A.DEFAULT_SETTINGS)
        self.app.game = None
        self.table = C.ctk.CTkFrame(None)
        self.status = C.ctk.CTkLabel(None)
        self.commodity = C.ctk.CTkComboBox(None); self.commodity.set("Any")
        self.min_rigs = C.ctk.CTkComboBox(None); self.min_rigs.set("0")
        self.min_types = C.ctk.CTkComboBox(None); self.min_types.set("0")
        self.within = C.ctk.CTkComboBox(None); self.within.set("500 Ly")
        # The filter row. Everything the real __init__ builds has to exist
        # here too, or a fixture that bypasses it tests a window nobody
        # will ever open.
        self.query = C.ctk.CTkEntry(None)
        self.hide_worked = C.ctk.BooleanVar(value=True)
        self.only_verified = C.ctk.BooleanVar(value=False)
        self._rows, self._headers, self._empty = [], [], ""
        self._builder, self._kind = None, ""
        self._sort_column, self._sort_reverse = None, False
        self._awaiting = None
        self._verifying = None
        # Where the commander is. None means the game has not said yet,
        # which is the state the app starts in and must still search from.
        self.app.star_position = lambda: (0.0, 0.0, 0.0)
        self.said, self.timers = [], []
    def say(self, text, colour=None): self.said.append(text)
    def after(self, ms, fn): self.timers.append((ms, fn))
    def _age(self): return 0

w = _Find(_Comm(ok=True)); w.search_sites()
check("a sent request says so", "Searching sites" in w.said[-1], w.said)
check("and arms a watchdog", bool(w.timers))

w = _Find(_Comm(ok=False)); w.search_sites()
check("a request that never left says so, and says why",
      "not sent" in w.said[-1] and "URL" in w.said[-1], w.said)

w = _Find(_Comm(boom=True)); w.search_sites()
check("a raise becomes a message instead of a dead button",
      "no route to host" in w.said[-1], w.said)

w = _Find(_Comm()); w.search_sites(); w.timers[0][1]()
check("silence eventually times out rather than hanging for ever",
      "timed out" in w.said[-1], w.said)

w = _Find(_Comm()); w.search_sites()
w.results("sites", json.dumps({"sites": []}), True)
_n = len(w.said); w.timers[0][1]()
check("an answered search does not then claim it timed out",
      len(w.said) == _n, w.said[_n:])

w = _Find(_Comm()); w.results("market", json.dumps({"prices": []}), True)
check("an empty price table falls back to the published figures",
      "Published figures" in w.said[-1], w.said)

w = _Find(_Comm()); w.results("sites", "HTTP 502", False)
check("a server error is labelled as one", "server said" in w.said[-1], w.said)

# ---------------------------------------------------------------------------
# The Find window's table: who found it, copying it, sorting it, filtering it
# ---------------------------------------------------------------------------

def _shown(w):
    """The rows the window would actually draw, as their cell text."""
    kept = [r for r in w._rows if w._keep(r)]
    return [[w._cell(c)[0] for c in w._builder(r)] for r in w._sorted(kept)]

def _col(w, name):
    return w._headers.index(name)

DEPOSITS = json.dumps({"deposits": [
    {"system": "Ega", "planet": "Ega 1", "spot": "1", "type": "Ruby",
     "rigs": 6, "density": "High", "lat": 12.5, "lon": -45.5,
     "uploader": "CMDR Jameson", "status": "verified"},
    {"system": "Col 285 Sector", "planet": "AB-C d1", "spot": "2",
     "type": "Olivine", "rigs": 2, "density": "Low", "lat": -3.25,
     "lon": 100.125, "uploader": "", "status": "reported"},
]})

SITES = json.dumps({"sites": [
    {"system": "Arietis", "planet": "Arietis 3", "spot": "1", "rigs": 4,
     "types": ["Ruby"], "age_days": 9, "score": 5.0},
    {"system": "Bhritzameno", "planet": "B 1 a", "spot": "1", "rigs": 2,
     "types": ["Olivine"], "age_days": 0, "score": 3.0},
    {"system": "Cubeo", "planet": "Cubeo 2", "spot": "3", "rigs": 9,
     "types": ["Quartz pyroxenite"], "age_days": 40, "score": 9.0,
     "worked_out": True},
]})

print("== a shared find says who found it ==")
# Reported as a bug, and it was one: the server has stored and returned
# uploader since the first version of the API and no column ever showed it,
# so every find on the map was anonymous whether the commander had asked to
# be credited or not.
w = _Find(_Comm()); w.results("search", DEPOSITS, True)
check("the deposit table has a Found by column", "Found by" in w._headers,
      w._headers)
rows = _shown(w)
found = _col(w, "Found by")
check("a commander who shared their name is named",
      rows[0][found] == "CMDR Jameson", rows[0])
check("and one who did not is anonymous, not blank",
      rows[1][found] == A.ANONYMOUS, rows[1])
check("anonymous is a word, not an empty cell", bool(A.ANONYMOUS.strip()))
check("a missing uploader key reads the same way",
      A.FindWindow._found_by({}) == A.ANONYMOUS)
check("and so does whitespace somebody typed by accident",
      A.FindWindow._found_by({"uploader": "   "}) == A.ANONYMOUS)

print("== one click puts it on the clipboard ==")
# The competing tool's headline feature is that clicking a deposit copies
# its lat/long. Retyping "12.5000, -45.5000" off a screen while driving is
# how a decimal point ends up in the wrong place.
w = _Find(_Comm()); w.results("search", DEPOSITS, True)
offers = {label: text for label, _what, text in w._copies(w._rows[0])}
check("a row offers to copy the system name", offers.get("system") == "Ega",
      offers)
check("and the coordinates as one pasteable pair",
      offers.get("lat/lon") == "12.5000, -45.5000", offers)
w.copy_text("the coordinates", offers["lat/lon"])
check("copying really reaches the clipboard",
      w.clipboard == "12.5000, -45.5000", getattr(w, "clipboard", None))
check("and the window says what went there",
      "12.5000, -45.5000" in w.said[-1] and "Copied" in w.said[-1], w.said)

w = _Find(_Comm()); w.results("sites", SITES, True)
site_offers = {label for label, _w, _t in w._copies(w._rows[0])}
check("a site row copies its system too", "system" in site_offers, site_offers)
check("but offers no coordinates, because a site has none",
      "lat/lon" not in site_offers, site_offers)

print("== copy all produces something you can paste into Discord ==")
w = _Find(_Comm()); w.results("search", DEPOSITS, True)
w.copy_all()
block = w.clipboard.splitlines()
check("the block leads with the headings",
      block[0].startswith("System | Body"), block[0])
check("and carries every row on screen", len(block) == 3, block)
check("including who found each one",
      "CMDR Jameson" in block[1] and A.ANONYMOUS in block[2], block)
check("and it says how many it copied", "2 row(s)" in w.said[-1], w.said)

w = _Find(_Comm()); w.copy_all()
check("copying an empty table says so instead of copying nothing",
      "Nothing to copy" in w.said[-1], w.said)

print("== clicking a heading sorts, clicking it again turns it round ==")
w = _Find(_Comm()); w.results("search", DEPOSITS, True)
system = _col(w, "System")
w.sort_by(system)
check("a column sorts", [r[system] for r in _shown(w)] == ["Col 285 Sector", "Ega"],
      [r[system] for r in _shown(w)])
w.sort_by(system)
check("the same column again reverses it",
      [r[system] for r in _shown(w)] == ["Ega", "Col 285 Sector"],
      [r[system] for r in _shown(w)])
rigs = _col(w, "Rigs")
w.sort_by(rigs)
check("a numeric column sorts as numbers, not as text",
      [r[rigs] for r in _shown(w)] == ["2", "6"], [r[rigs] for r in _shown(w)])
check("and a new column starts the right way up again", not w._sort_reverse)

# "today" sorts before "9 days ago" only if the number behind the sentence
# is what gets compared. Alphabetically "today" is last.
w = _Find(_Comm()); w.results("sites", SITES, True)
w.hide_worked.set(False)
seen = _col(w, "Last seen")
w.sort_by(seen)
check("a column whose text does not sort the way it reads still does",
      [r[seen] for r in _shown(w)] == ["today", "9 days ago", "40 days ago"],
      [r[seen] for r in _shown(w)])
check("sorting draws the arrow on the heading it sorted",
      w._sort_column == seen and not w._sort_reverse)

w.sort_by(99)
check("a heading click on a column that is not there does not crash",
      len(_shown(w)) == 3, w.said[-1])

print("== every filter on the Find window does something ==")
# The free-text box, hide worked-out and verified only. Each one either
# reaches the request or removes rows from the answer - a filter that does
# neither is a control that lies.
w = _Find(_Comm()); w.results("search", DEPOSITS, True)
w.query.set("col 285"); w._paint()
check("the system/body box narrows what is on screen",
      [r[0] for r in _shown(w)] == ["Col 285 Sector"], _shown(w))
check("and it is not case-sensitive, because nobody types Col 285 Sector",
      len(_shown(w)) == 1)
check("the window says how many it hid",
      "1 of 2 shown" in w.said[-1], w.said)
w.query.set(""); w._paint()
check("clearing it puts them back", len(_shown(w)) == 2, _shown(w))

w.only_verified.set(True); w._paint()
check("verified only keeps the verified row",
      [r[0] for r in _shown(w)] == ["Ega"], _shown(w))
w.only_verified.set(False)

w = _Find(_Comm()); w.results("sites", SITES, True)
check("hide worked-out is on to start with, and hides one",
      [r[0] for r in _shown(w)] == ["Arietis", "Bhritzameno"], _shown(w))
w.hide_worked.set(False); w._paint()
check("unticking it brings the stripped site back",
      len(_shown(w)) == 3, _shown(w))

# A price is not a find. Neither toggle means anything there, and applying
# them would empty a table that has nothing to do with the question.
w = _Find(_Comm())
w.only_verified.set(True)
w.results("market", json.dumps({"prices": [
    {"commodity": "Ruby", "station": "Jameson Memorial", "system": "Shinrarta",
     "sell": 91000, "demand": 400, "seen": "2026-09-14T00:00:00Z"}]}), True)
check("the toggles do not empty the price table", len(_shown(w)) == 1, _shown(w))

print("== a finished search never still says it is searching ==")
# The status line is the only thing that distinguishes a search that came
# back empty from one that hung. It said "Searching sites..." next to a
# finished, empty table.
w = _Find(_Comm()); w.search_sites()
check("firing one says so", "Searching sites" in w.said[-1], w.said)
w.results("sites", json.dumps({"sites": []}), True)
check("and an empty answer replaces that rather than leaving it up",
      "Searching" not in w.said[-1] and "0 result(s)" in w.said[-1], w.said)

# A refused search used to clear the widgets and keep the rows, so ticking
# a filter afterwards redrew the results from before it went wrong.
w = _Find(_Comm()); w.results("sites", SITES, True)
w.results("sites", "HTTP 502", False)
check("a refused search is reported", "server said" in w.said[-1], w.said)
check("and it drops the results it is no longer showing", not w._rows, w._rows)
w.hide_worked.set(False); w._paint()
check("so a filter cannot resurrect them",
      "server said" in w.said[-1], w.said)

print("== and every filter reaches the outgoing request ==")
c = _Comm(); w = _Find(c)
w.query.set("Ega"); w.only_verified.set(True); w.hide_worked.set(True)
w.search_deposits()
sent = c.calls[-1][1]
# The box is labelled "System / body" and it has to mean either. A client
# that takes `name` gets `name`, which the server matches against a system
# OR a body; typing "Ega 1" into a search that only knows how to narrow by
# system came back empty, and empty reads as "nobody has been there".
check("what was typed goes out with the deposit search",
      sent.get("name") == "Ega", sent)
check("and never as both at once - that would search for a SYSTEM called "
      "'Ega 1'", "system" not in sent, sent)
check("verified only goes out with it", sent.get("verified_only") is True, sent)
check("and hide worked-out goes out as the server's own name for it",
      sent.get("include_depleted") is False, sent)
w.search_sites()
sent = c.calls[-1][1]
check("the site search carries them too",
      sent.get("name") == "Ega" and sent.get("verified_only") is True, sent)
# A body, not a system. This is the search that came back empty.
cb = _Comm(); wb = _Find(cb)
wb.query.set("Ega 1"); wb.search_sites()
check("a body name reaches the server instead of being dropped on the floor",
      cb.calls[-1][1].get("name") == "Ega 1", cb.calls[-1])
check("along with the filters that were always there",
      sent.get("within_ly") == 500 and sent.get("near") == (0.0, 0.0, 0.0), sent)
w.search_prices()
check("and the box steers the price lookup rather than being dropped",
      c.calls[-1][1].get("near_system") == "Ega", c.calls[-1])

# edonline is written by other hands. A keyword it has not grown yet is a
# TypeError, and Tk swallows one raised inside a button command - the button
# simply stops working and says nothing anywhere.
n = _Narrow(); w = _Find(n)
w.query.set("Ega"); w.only_verified.set(True)
w.search_deposits(); w.search_sites(); w.search_prices()
check("a client with named parameters only is not handed a keyword it "
      "cannot take", len(n.calls) == 3, n.calls)
check("it still gets the one it does declare",
      n.calls[0][1].get("system") == "Ega", n.calls[0])
check("and the window reported a sent request, not a dead button",
      "Searching" in w.said[0] or "Looking" in w.said[0], w.said)

print("== the distance filter reaches the server at all ==")
# It never has. EDSMT.here() was written twice - once returning the
# commander's position as a triple and once returning (system, body) - and
# Python kept the second. CommunityClient._near wants three numbers, got
# two strings, and silently applied no radius at all.
check("the position method has a name of its own now",
      "def star_position" in src)
check("and only one here() is left", src.count("    def here(self):") == 1,
      src.count("    def here(self):"))
check("Find asks for the position, not for the body name",
      "self.app.star_position()" in src)
probe = A.EDSMT.__new__(A.EDSMT)
probe.watcher = type("W", (), {"star_pos": [1.0, 2.0, 3.0]})()
check("and it answers with three numbers",
      probe.star_position() == (1.0, 2.0, 3.0), probe.star_position())
probe.watcher = type("W", (), {"star_pos": None})()
check("or with nothing at all before the game has said",
      probe.star_position() is None)

print("== an empty table says what to do next ==")
w = _Find(_Comm()); w.results("sites", SITES, True)
w.query.set("nowhere at all"); w._paint()
advice = w._advice()
check("it says the filters did it, not the galaxy",
      "hid all of them" in advice, advice)
check("and names the one that is doing it",
      "nowhere at all" in advice, advice)
w = _Find(_Comm()); w.results("sites", json.dumps({"sites": []}), True)
advice = w._advice()
check("a genuinely empty answer suggests widening the search",
      "Try again wider" in advice and "Anywhere" in advice, advice)
w.within.set(A.NO_DISTANCE_LIMIT)
check("and when there is nothing left to widen it says so instead",
      "nobody has shared one yet" in w._advice(), w._advice())

print("== the window can ask for what is still there ==")
# /v1/intact is the one question a position generator can never answer, and
# the app had no method to ask it with. The button did not exist either.
check("there is a button for it", 'text="Still there"' in src)
check("wired to the search, not to nothing",
      "command=self.search_intact" in src)

c = _Comm(); w = _Find(c)
w.min_rigs.set("4"); w.commodity.set("Ruby")
w.search_intact()
kind, sent = c.calls[-1][0], c.calls[-1][1]
check("pressing it asks the intact endpoint", kind == "intact", c.calls[-1])
check("with the filters that are on screen",
      sent.get("commodity") == "Ruby" and sent.get("min_rigs") == 4, sent)
check("and the radius, like every other search here",
      sent.get("within_ly") == 500 and sent.get("near") == (0.0, 0.0, 0.0), sent)
check("and it says a request went", "still there" in w.said[-1].lower(), w.said)

INTACT = json.dumps({"sites": [
    {"system": "Sure", "planet": "Sure 1", "spot": "1", "rigs": 6,
     "types": ["Ruby"], "age_days": 2, "intact_confidence": 0.94,
     "score": 20.0, "status": "reported"},
    {"system": "Doubtful", "planet": "D 2", "spot": "1", "rigs": 12,
     "types": ["Olivine"], "age_days": 200, "intact_confidence": 0.11,
     "score": 1.0, "status": "reported"},
    {"system": "Stripped", "planet": "S 3", "spot": "1", "rigs": 20,
     "types": ["Helium"], "age_days": 1, "intact_confidence": 0.02,
     "score": 0.4, "worked_out": True, "status": "reported"},
]})
w = _Find(_Comm()); w.results("intact", INTACT, True)
check("the answer draws a table", bool(w._rows), w._rows)
check("led by how sure we are it is still there",
      w._headers[3] == "Still there", w._headers)
rows = _shown(w)
check("shown as a percentage a person can read",
      rows[0][3] == "94%", rows[0])
check("the server's own ordering is not second-guessed",
      [r[0] for r in rows] == ["Sure", "Doubtful"], rows)
check("and hide worked-out still does its job on the way in, because this "
      "endpoint deliberately returns them", "Stripped" not in
      [r[0] for r in rows], rows)
w.hide_worked.set(False); w._paint()
check("unticking it brings the stripped one back", len(_shown(w)) == 3, _shown(w))
# Sorts on the number behind the sentence, not on "94%" as text.
w.sort_by(3)
check("the confidence column sorts as a number",
      [r[3] for r in _shown(w)] == ["2%", "11%", "94%"], _shown(w))

print("== best sell prices asks near where you are, not what it is called ==")
# A15. It sent the commander's current system, matched exactly. You are
# standing on a rock in it. The table was empty every time, for everybody.
c = _Comm(); w = _Find(c)
w.commodity.set("Ruby")
w.search_prices()
kind, sent = c.calls[-1][0], c.calls[-1][1]
check("a named commodity goes to the richer sell endpoint",
      kind == "sell", c.calls[-1])
check("carrying where the commander actually is",
      sent.get("near") == (0.0, 0.0, 0.0), sent)
check("and how far they are willing to go",
      sent.get("within_ly") == 500, sent)
check("and the window says how wide it looked",
      "within 500 Ly" in w.said[-1], w.said)

c = _Comm(); w = _Find(c)
w.search_prices()
check("with no commodity chosen it falls back to the plain price table, "
      "which is the one that does not require one",
      c.calls[-1][0] == "prices", c.calls[-1])
check("and that one gets the position too",
      c.calls[-1][1].get("near") == (0.0, 0.0, 0.0), c.calls[-1])

c = _Comm(); w = _Find(c)
w.query.set("Sol"); w.commodity.set("Ruby"); w.search_prices()
check("typing a system still means near there instead of near me",
      c.calls[-1][1].get("near_system") == "Sol", c.calls[-1])
check("and near there is not measured from where I am",
      c.calls[-1][1].get("near") is None, c.calls[-1])

# E4. Nothing typed used to send no system name at all, and the market index
# only measures distance from a name - so the answer was the best price in
# the galaxy, hundreds of light years off, with no distance on it.
c = _Comm(); w = _Find(c)
w.app.watcher = type("W", (), {"system": "HR 7280"})()
w.commodity.set("Sapphire"); w.search_prices()
check("with nothing typed, prices are asked for near the system I am in, "
      "by name", c.calls[-1][1].get("near_system") == "HR 7280", c.calls[-1])
check("and by position as well",
      c.calls[-1][1].get("near") == (0.0, 0.0, 0.0), c.calls[-1])

PRICES = json.dumps({"prices": [
    {"commodity": "Ruby", "station": "Far Money", "system": "Distant",
     "sell": 900000, "demand": 400, "seen": "2026-09-14T00:00:00Z",
     "distance_ly": 480.0},
    {"commodity": "Ruby", "station": "Local", "system": "Nearby",
     "sell": 400000, "demand": 900, "seen": "2026-09-15T00:00:00Z",
     "distance_ly": 11.5},
    {"commodity": "Ruby", "station": "Nowhere Known", "system": "Unplaced",
     "sell": 500000, "demand": 100, "seen": "2026-09-15T00:00:00Z",
     "distance_ly": None},
]})
w = _Find(_Comm()); w.results("market", PRICES, True)
check("the price table shows the distance", "Distance" in w._headers, w._headers)
rows = _shown(w)
far, shop = _col(w, "Distance"), _col(w, "Station")
check("nearest first, rather than the server's price order",
      [r[shop] for r in rows] == ["Local", "Far Money", "Nowhere Known"],
      [r[shop] for r in rows])
check("in light years, so the column reads as one",
      rows[0][far] == "11.5 Ly", rows[0])
# A station whose system nobody has placed is not at 0 Ly, which would put
# it at the top of a nearest-first table as the closest thing in the galaxy.
check("a station nobody can place says so rather than claiming to be here",
      rows[-1][far] == "-", rows[-1])

SELL = json.dumps({"commodity": "Ruby", "best_sell": 900000,
                   "market": [{"commodity": "Ruby", "station": "Indexed",
                               "system": "Far", "sell": 900000, "demand": 5,
                               "seen": "2026-09-01", "distance_ly": 300.0,
                               "source": "market index"}],
                   "community": [{"commodity": "Ruby", "station": "Ours",
                                  "system": "Near", "sell": 200000,
                                  "demand": 9, "seen": "2026-09-16",
                                  "distance_ly": 8.0, "source": "community"}]})
w = _Find(_Comm()); w.results("sell", SELL, True)
rows = _shown(w)
check("both sources land in one table", len(rows) == 2, rows)
check("nearest first here too",
      rows[0][_col(w, "Station")] == "Ours", rows)
check("and each row says which index said so",
      [r[_col(w, "Source")] for r in rows] == ["community", "market index"],
      rows)
# Neither toggle means anything to a station, and the box went out as
# "near here" - so filtering the answer by it would empty the screen.
w.only_verified.set(True); w.hide_worked.set(True); w.query.set("Ega")
w._paint()
check("the find filters leave a sell table alone", len(_shown(w)) == 2, _shown(w))

w = _Find(_Comm())
w.results("sell", json.dumps({"market": [], "community": []}), True)
check("and an empty one still falls back to the published figures",
      "Published figures" in w.said[-1], w.said)

print("== the server does the filtering, and _keep does not undo it ==")
# _extra hands a filter to the server when the client has grown a parameter
# for it, and _keep applies it here when it has not. The two have to agree:
# a row the server kept that _keep then drops is a filter that empties the
# table it was supposed to narrow, and nothing would say why.
c = _Comm(); w = _Find(c)
w.query.set("Ega"); w.only_verified.set(True); w.hide_worked.set(True)
w.search_sites()
sent = c.calls[-1][1]
check("the site search now carries what was typed in the box",
      sent.get("name") == "Ega", sent)
check("and verified only", sent.get("verified_only") is True, sent)
check("and hide worked-out, under the server's name for it",
      sent.get("include_depleted") is False, sent)

# What that request comes back with: verified, not worked out, system
# matching the prefix. Every one of them has to survive _keep.
SERVER_FILTERED = json.dumps({"sites": [
    {"system": "Ega", "planet": "Ega 1", "spot": "1", "rigs": 6,
     "types": ["Ruby"], "age_days": 1, "score": 9.0, "status": "verified",
     "worked_out": False, "intact_confidence": 0.9},
    {"system": "Egaeus", "planet": "Egaeus 2", "spot": "3", "rigs": 4,
     "types": ["Olivine"], "age_days": 3, "score": 6.0, "status": "verified",
     "worked_out": False, "intact_confidence": 0.8},
]})
w.results("sites", SERVER_FILTERED, True)
check("every row the server returned is still on screen afterwards",
      len(_shown(w)) == 2, (_shown(w), w.said[-1]))
check("so the three filters together hide nothing the server already applied",
      "hidden by your filters" not in w.said[-1], w.said)

# The same three, one at a time, so a failure names which one did it.
for label, setup in (
        ("the typed system", lambda: w.query.set("Ega")),
        ("verified only", lambda: w.only_verified.set(True)),
        ("hide worked-out", lambda: w.hide_worked.set(True))):
    w = _Find(_Comm())
    w.query.set(""); w.only_verified.set(False); w.hide_worked.set(False)
    setup()
    w.results("sites", SERVER_FILTERED, True)
    check("%s alone keeps what the server sent" % label,
          len(_shown(w)) == 2, _shown(w))

# And the reverse: a client that has NOT grown the parameter must still get
# the filter, applied here. That is the whole point of _extra.
n = _Narrow(); w = _Find(n)
w.only_verified.set(True)
w.search_deposits()
check("a client without verified_only is not handed it",
      "verified_only" not in n.calls[-1][1], n.calls[-1])
w.results("search", DEPOSITS, True)
check("so this end applies it instead, and it still narrows",
      [r[0] for r in _shown(w)] == ["Ega"], _shown(w))

print("== every tag the client can produce has somewhere to go ==")
# A tag the app does not route is answered by the server, collected off the
# worker queue and dropped on the floor, and the window sits on
# "Searching..." for ever with nothing wrong anywhere. That has happened.
import ast as _ast_tags, io as _io_tags
_edo_src = _io_tags.open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "edonline.py"), encoding="utf-8").read()
_community = _ast_tags.parse(_edo_src)
_cls = next(n for n in _ast_tags.walk(_community)
            if isinstance(n, _ast_tags.ClassDef) and n.name == "CommunityClient")
_tags = {a.args[0].value for a in _ast_tags.walk(_cls)
         if isinstance(a, _ast_tags.Call)
         and getattr(a.func, "attr", "") == "submit"
         and a.args and isinstance(a.args[0], _ast_tags.Constant)}
_routed = set(A.FIND_TAGS) | {"share", "deplete", "prices"}
# "body" is answered by the map, not by a window: collect_results hands it
# to take_shared by name.
_app_src = _io_tags.open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "edsmt.py"), encoding="utf-8").read()
if 'if tag == "body":' in _app_src and "self.take_shared(ok, message)" in _app_src:
    _routed.add("body")
# Where to land's two answers go to the app, which repaints the window.
if 'if tag == "grounds":' in _app_src and "self.take_grounds(ok, message)" in _app_src:
    _routed.add("grounds")
if 'if tag == "landing":' in _app_src and "self.take_landing(ok, message)" in _app_src:
    _routed.add("landing")
# The wing link's beats come back to the app, which puts the wing on the scope.
if 'if tag == "wing":' in _app_src and "self.take_wing(ok, message)" in _app_src:
    _routed.add("wing")
check("no community client tag goes unrouted", not (_tags - _routed),
      sorted(_tags - _routed))
check("and the window switches on the same list the app routes on",
      set(A.FIND_TAGS) >= {"sites", "search", "intact", "market", "sell",
                           "commodities", "verify"}, A.FIND_TAGS)

print("== a site can be marked as one somebody has stood on ==")
# "Verified only" has shipped since the first Find window and has never had
# a row to match, because nothing in the app could set the flag.
w = _Find(_Comm(staff=False)); w.results("sites", SITES, True)
check("an ordinary commander is offered no verify button",
      not w._verifiable(w._rows[0]), w._rows[0])

c = _Comm(staff=True); w = _Find(c); w.results("sites", SITES, True)
check("somebody carrying a staff token is", w._verifiable(w._rows[0]))
check("but not on a site the server already believes",
      not w._verifiable({"system": "Ega", "planet": "Ega 1",
                         "status": "verified"}))
check("and not on a row with no body to name",
      not w._verifiable({"system": "Ega", "planet": ""}))

w2 = _Find(_Comm(staff=True))
w2.results("market", PRICES, True)
check("a station is not a site, so it is not verifiable either",
      not w2._verifiable(w2._rows[0]), w2._rows[0])

w.app.game = type("G", (), {"cmdr": "CMDR Jameson"})()
w.verify_site(w._rows[0])
kind, args, _kw = c.calls[-1]
check("pressing it sends the site", kind == "verify", c.calls[-1])
check("naming the commander out of the journal, not out of a box",
      args[0] == "CMDR Jameson", args)
check("and the system, body and signal it means",
      args[1:] == ("Arietis", "Arietis 3", "1"), args)
check("the window says it went", "Verifying" in w.said[-1], w.said)

w.results("verify", "site verified by CMDR Jameson", True)
check("the answer is reported", "site verified" in w.said[-1], w.said)
check("and the row it was sent for stops offering the button",
      not w._verifiable(w._rows[0]), w._rows[0])
check("because the table was told, rather than waiting for a new search",
      w._rows[0].get("status") == "verified", w._rows[0])

w = _Find(_Comm(staff=True)); w.results("sites", SITES, True)
w.verify_site(w._rows[0])
w.results("verify", "HTTP 403", False)
check("a refusal says so instead of pretending", "Could not verify" in w.said[-1],
      w.said)
check("and it does not throw the results away with it", len(w._rows) == 3,
      w._rows)

print("== the commodity dropdown can learn a fourteenth ==")
# The app ships the thirteen from 4.4.1.0. The server is the end that gets
# updated, so it is asked - quietly, and never fatally.
w = _Find(_Comm())
w.commodity.set("Ruby")
w.results("commodities", json.dumps(
    {"commodities": ["Ruby", "Voidstone"]}), True)
values = w.commodity.cget("values")
check("a commodity the build has never heard of joins the list",
      "Voidstone" in values, values)
check("without taking away the ones it ships with",
      all(n in values for n in SV.KNOWN_COMMODITIES), values)
check("Any is still the first entry", values[0] == "Any", values[:2])
check("and what was already chosen stays chosen",
      w.commodity.get() == "Ruby", w.commodity.get())

w = _Find(_Comm()); w.results("sites", SITES, True)
before = len(w._rows)
w.results("commodities", "not json at all", True)
check("a commodity list that will not parse does not wipe the results",
      len(w._rows) == before, w._rows)
w.results("commodities", "HTTP 500", False)
check("and a server that refuses it says nothing about it either",
      "server said" not in w.said[-1], w.said)

print("== the empty table admits what the search box does at the server ==")
w = _Find(_Comm()); w.results("sites", json.dumps({"sites": []}), True)
w.query.set("Ega 1")
check("it says the box goes out as a system name",
      "system name" in w._advice(), w._advice())
w2 = _Find(_Comm()); w2.results("market", json.dumps({"prices": []}), True)

print("== the rail stays usable in a small window ==")
# "when people move the window its dynamic as you can not see the fill in
# mineral details if its a small window" - the MARK DEPOSIT block and the
# four fields under it fell off the bottom of a packed column, which cannot
# give them back at any size.
rail = src.split("def _rail")[1].split("\n    def ")[0]
check("the rail scrolls rather than clipping",
      "CTkScrollableFrame" in rail, rail[:200])
check("the fields are built inside the scroller, not beside it",
      rail.find("CTkScrollableFrame(frame") < rail.find('"MARK DEPOSIT'),
      (rail.find("CTkScrollableFrame(frame"), rail.find('"MARK DEPOSIT')))
check("the fixed width is still enforced on the column itself",
      "grid_propagate(False)" in rail)
# The floor has to actually hold the rail plus a map worth looking at.
# Pinned to the constants rather than a literal so widening the rail
# cannot silently leave the minimum too small for it.
check("the window's minimum width holds the rail and a usable map",
      "self.minsize(RAIL_WIDTH + SCROLLBAR_W + 420, 560)" in src)
check("and the rail is wide enough that its buttons are not clipped",
      A.RAIL_WIDTH >= 370, A.RAIL_WIDTH)
check("with the scrollbar's pixels on top, not taken out of the controls",
      "width=RAIL_WIDTH + SCROLLBAR_W" in src and "width=RAIL_WIDTH," in src)

print("== the people who broke it first are credited ==")
check("there is a list, and it is a constant",
      isinstance(A.BETA_TESTERS, list) and len(A.BETA_TESTERS) == 5,
      A.BETA_TESTERS)
for name in ("CMDR MJH430", "CMDR StarTopaz", "CMDR Flossy", "CMDR Gamer Joe",
             "CMDR Rumphrend"):
    check("%s is on it" % name, name in A.BETA_TESTERS)
settings = src.split("class SettingsWindow")[1].split("\nclass ")[0]
check("Settings has a beta testers section", '"Beta testers"' in settings)
check("and it reads the constant rather than repeating the names",
      "BETA_TESTERS" in settings)
check("no name is hard-coded into the window",
      "MJH430" not in settings)


print("== the rail follows the order of operations ==")
# You drive into a signal and press F9 BEFORE you ping anything, so the
# signal list belongs above the deposit button rather than under it.
rail = src.split("def _rail")[1].split("\n    def ")[0]
# Case-insensitive: the section headings go through hud_header now, which
# puts them in caps at render time rather than in the source.
locs_at = rail.lower().find('"mining locations"')
mark_at = rail.find('"MARK DEPOSIT')
check("mining locations come before mark deposit",
      0 < locs_at < mark_at, (locs_at, mark_at))

# Amount before Density, and the SAME order in the editor - two screens that
# ask the same questions in different orders is how a wrong value ends up
# typed into a right-looking box.
amount_at = rail.find('"amount", [""] + AMOUNT_LEVELS')
density_at = rail.find('"density", [""] + DENSITY_LEVELS')
check("amount is asked before density on the rail",
      0 < amount_at < density_at, (amount_at, density_at))
edit = src.split("class EditWindow")[1].split("\nclass ")[0]
e_amount = edit.find('"amount", "Amount"')
e_density = edit.find('"density", "Density"')
check("and in the same order when correcting one",
      0 < e_amount < e_density, (e_amount, e_density))
check("the hint text was updated to match",
      "Amount is how much is left" in rail)

print("== deposits are editable from the rail, not just the map ==")
# Editing one meant finding its pin on the map and double-clicking it -
# fine when you know, invisible when you do not.
rail = src.split("def _rail")[1].split("\n    def ")[0]
check("the rail has a deposit list", "self.deposit_list" in rail)
check("with its own heading", 'hud_header(rail, "Deposits"' in rail)
body = src.split("def refresh_deposits")[1].split("\n    def ")[0]
check("each row carries an edit button", 'text="edit"' in body)
check("the button is packed right, before the label that expands",
      body.find('text="edit"') < body.find("pick_deposit"), body[:0])
check("clicking a row selects it", "def pick_deposit" in src)
# This asserted on "EditWindow(self, row)" and passed - against the DEAD
# copy of edit_deposit. There were two, Python kept the second, and the
# test string-matched the one that never ran. A duplicate-method check now
# lives in test_wiring.py so this class of bug cannot come back.
_editor_body = src.split("def edit_deposit")[1].split("\n    def ")[0]
check("and the editor opens on that deposit",
      "EditWindow(self, deposit)" in _editor_body)
check("and a failure opening it is reported, not swallowed by Tk",
      "Could not open that deposit" in _editor_body)
check("with nothing selected it says so rather than doing nothing",
      "Pick a deposit first" in _editor_body)
check("the list refreshes wherever the signal list does",
      src.count("self.refresh_deposits()") >= src.count("self.refresh_locations()"),
      (src.count("self.refresh_deposits()"), src.count("self.refresh_locations()")))
check("the widget is declared before _build, not assumed into existence",
      "self.deposit_list = None" in src)

print("== the update check can be seen to work ==")
# Reported as "not working" while doing exactly its job. Saying nothing when
# you are up to date is right on launch and indistinguishable from a broken
# check, a missing file or no connection. There has to be a way to ask.
import edonline as _EDO

_served = {}
_real_get = _EDO.get_json
def _fake_get(url, timeout=10.0, headers=None):
    if "boom" in url:
        raise IOError("no connection (timed out)")
    return _served
_EDO.get_json = _fake_get

class _Q:
    def __init__(self): self.jobs = []
    def submit(self, tag, fn): self.jobs.append((tag, fn))

def _drive(current, latest, force, url=_EDO.VERSION_URL):
    global _served
    _served = {"version": latest, "url": "https://radioraxxla.com/EDSMT/",
               "headline": "something changed"}
    q = _Q(); _EDO.UpdateCheck(q).check(current, url, force=force)
    done = []
    for tag, fn in q.jobs:
        try:
            done.append((tag, True, fn() or ""))
        except Exception as exc:
            done.append((tag, False, str(exc)))
    shown = []
    probe = A.EDSMT.__new__(A.EDSMT)
    probe.say = lambda t, c=None: shown.append(t)
    probe.announce_update = lambda m: shown.append("BANNER " + m)
    probe.finder = None
    probe.worker = type("W", (), {"drain": staticmethod(lambda: done)})()
    probe.collect_results()
    return shown[-1] if shown else ""

check("a newer build is announced on launch",
      _drive("1.10006", "1.10008", False).startswith("BANNER"))
check("being up to date says NOTHING on launch",
      _drive("1.10008", "1.10008", False) == "",
      _drive("1.10008", "1.10008", False))
check("but the button says so out loud",
      "up to date" in _drive("1.10008", "1.10008", True))
check("the button announces a newer build too",
      _drive("1.10006", "1.10008", True).startswith("BANNER"))
check("and a failed check is reported rather than swallowed",
      "Could not check" in _drive("1.10008", "1.10008", True, url="boom"),
      _drive("1.10008", "1.10008", True, url="boom"))

_q = _Q(); _u = _EDO.UpdateCheck(_q)
check("the launch check runs once, not on every tick",
      _u.check("1.1") and not _u.check("1.1"))
check("the button still works after it", _u.check("1.1", force=True))

_served = {"url": "x"}
_q2 = _Q(); _EDO.UpdateCheck(_q2).check("1.1")
_raised = False
try:
    _q2.jobs[0][1]()
except Exception:
    _raised = True
check("a version.json with no version is an error, not a silent pass", _raised)

_EDO.get_json = _real_get
check("the Settings window has the button",
      "Check for updates" in src and "def check_updates" in src)

print("== the copy buttons are somewhere you can actually see them ==")
# They were built in the last column of an eight-column table. On any
# window narrower than the table they rendered off the right edge, so the
# reported bug was "there is no copy button" and the bug was real - just
# not the one it looked like.
check("copy is the first column, not the last", A.COPY_COLUMN == 0)
check("and the data starts after it", A.DATA_COLUMN_0 == 1)
import io as _io
src_find = _io.open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "edsmt.py"), encoding="utf-8").read()
check("nothing grids itself at len(self._headers) any more",
      "column=len(self._headers)" not in src_find)
check("every data cell is offset past the copy column",
      "column=DATA_COLUMN_0 + column" in src_find)

print("== the page cap is admitted, not hidden ==")
check("the app asks for more than fifty", A.SEARCH_LIMIT >= 200, A.SEARCH_LIMIT)
check("and says so when the page is full",
      "the most this asks for at" in src_find)
check("both searches send the limit",
      src_find.count("limit=SEARCH_LIMIT") >= 2)

print("== the server's depletion ranking survives the trip to the screen ==")
# The client re-ranked every /v1/sites response through a local scorer
# that knows only rigs, types and density - overwriting the server's
# score and age_days, and discarding intact_confidence, confirmed_by and
# worked_out_reports entirely. A site three commanders had reported
# stripped came out ABOVE an untouched one, because the number that says
# so was deleted before anything could read it.
_ranker = src.split("def _render")[1].split("\n    def ")[0]
check("rank_sites only runs when the server did not rank them",
      "intact_confidence" in _ranker and "if not any(" in _ranker)
check("and the server's own ordering is left alone otherwise",
      _ranker.find("if not any(") < _ranker.find("EDO.rank_sites"))

class _Render(_Find):
    def __init__(self):
        _Find.__init__(self, _Comm())
        self.painted = []
    def _paint(self):
        self.painted = list(self._rows)

SERVER_ROWS = [
    {"system": "Stripped", "planet": "S 1", "spot": "1", "rigs": 24,
     "distinct_types": 4, "density": 3.0, "score": 0.14, "age_days": 0,
     "intact_confidence": 0.002, "worked_out_reports": 3, "worked_out": True},
    {"system": "Intact", "planet": "I 1", "spot": "1", "rigs": 6,
     "distinct_types": 1, "density": 2.0, "score": 27.1, "age_days": 0,
     "intact_confidence": 0.98, "worked_out_reports": 0, "worked_out": False},
]
r = _Render()
r._render(SERVER_ROWS, ["System"], r._site_row, "none", kind="sites")
check("a ranked server response is passed through untouched",
      [x["system"] for x in r.painted] == ["Stripped", "Intact"],
      [x["system"] for x in r.painted])
check("and its scores are not overwritten",
      [x["score"] for x in r.painted] == [0.14, 27.1],
      [x["score"] for x in r.painted])
check("intact_confidence survives to the screen",
      all("intact_confidence" in x for x in r.painted))

OLD_ROWS = [dict(x) for x in SERVER_ROWS]
for x in OLD_ROWS:
    x.pop("intact_confidence")
r2 = _Render()
r2._render(OLD_ROWS, ["System"], r2._site_row, "none", kind="sites")
check("an older server that ranks nothing is still ranked here",
      all("score" in x for x in r2.painted))

print("== a broken callback is logged and reported, never swallowed ==")
# Tk prints callback exceptions to a console that does not exist in an
# installed build, then carries on. Every silent failure this app has
# shipped went out through that hole: the missing _rewrap that emptied
# Find, the duplicated edit_deposit whose error handler was in the dead
# copy, the TypeError that broke MARK DEPOSIT on every new body.
check("the hook is installed on the main window",
      "self.report_callback_exception = self._callback_failed" in src)
check("and it is installed before anything else can raise",
      src.find("report_callback_exception = self._callback_failed")
      < src.find('self.title(APP_TITLE)'))
_hook = src.split("def _callback_failed")[1].split("\n    def ")[0]
check("it writes a traceback to crash.log", "crash.log" in _hook
      and "format_exception" in _hook)
check("it stamps the version, so a report can be placed",
      "APP_VERSION" in _hook)
check("and it tells the commander on screen", "self.say(" in _hook
      and "crash.log" in _hook)
check("the reporter cannot itself take the app down",
      _hook.count("except") >= 2)

# ===========================================================================
# The audit findings, and the cockpit restyle
# ===========================================================================

print("== a cold start with Elite shut shows what is on disk ==")
# update_telemetry returned early when the game was not running, and _build
# never called the four refreshers itself - so they were reachable only PAST
# that return. With Elite closed the signal list, the deposit list, the
# commodity box and the map were all empty, and every fallback written for
# exactly that case (here()'s settings fallback, centre_of_record, redraw's
# "not in an SRV" branch) was unreachable at launch. Tidying up finds with
# the game shut is a thing people do.
cold = A.EDSMT.__new__(A.EDSMT)
cold.settings = dict(A.DEFAULT_SETTINGS)
cold.settings["last_system"], cold.settings["last_body"] = "Ega", "Ega 1"
cold.store = SV.Survey(A.DATA_DIR)
cold.game = None                        # Elite is not running
cold.selected = None
cold._known_body = None
cold.prices = {}
cold.overlay = type("O", (), {"showing": False})()
cold.location_box = _ctkstub.ctk.CTkComboBox(None, values=["1"])
cold.location_box.set("1")
cold.location_box_list = _ctkstub.ctk.CTkScrollableFrame(None)
cold.deposit_list = _ctkstub.ctk.CTkScrollableFrame(None)
cold.deposit_header = _ctkstub.ctk.CTkLabel(None)
cold.location_note = _ctkstub.ctk.CTkLabel(None)
cold.fields = {k: _ctkstub.ctk.CTkComboBox(None, values=[]) for k in
               ("commodity", "rigs", "density", "amount")}
for _b in cold.fields.values():
    _b.set("")
cold_drawn = []
cold.plan = type("P", (), {"show": lambda self, rows=None, **kw: cold_drawn.append(rows),
                           "select": lambda self, i: None})()
cold.say = lambda text, colour=None: None

check("_build fills the window in rather than leaving it blank",
      "self.show_records()" in src.split("def _build")[1].split("\n    def ")[0])
cold.show_records()
check("the signal list has rows on it with the game shut",
      len(cold.location_box_list.winfo_children()) > 0,
      len(cold.location_box_list.winfo_children()))
check("so does the deposit list",
      len(cold.deposit_list.winfo_children()) > 0,
      len(cold.deposit_list.winfo_children()))
check("the commodity box is offering something",
      len(cold.fields["commodity"]._values) > 0,
      len(cold.fields["commodity"]._values))
check("and the map drew the deposits recorded here",
      cold_drawn and cold_drawn[-1], cold_drawn[-1:])
check("the body it picked is the one settings remembered",
      cold._known_body == ("Ega", "Ega 1"), cold._known_body)

# ...and the same when tick runs with the game still shut.
cold_drawn.clear()
cold._known_body = None
cold.t_where = _ctkstub.ctk.CTkLabel(None)
cold.t_detail = _ctkstub.ctk.CTkLabel(None)
cold.btn_mark = _ctkstub.ctk.CTkButton(None)
cold.update_telemetry(type("S", (), {"running": False, "where": "not running"})())
check("a tick with no game still follows the disk instead of returning blind",
      cold_drawn and cold_drawn[-1], cold_drawn[-1:])
check("and it worked out which body that is",
      cold._known_body == ("Ega", "Ega 1"), cold._known_body)
check("MARK DEPOSIT is still disabled, because you cannot mark one",
      cold.btn_mark.cget("state") == "disabled", cold.btn_mark.cget("state"))
# Proved on the parse tree, not by searching the text: the word "return"
# appears in the comment that explains this branch, so a string search for
# it lands before the code and the check passes or fails on prose.
import ast as _ast_t
_tele_fn = next(n for n in _ast_t.walk(_ast_t.parse(src))
                if isinstance(n, _ast_t.FunctionDef)
                and n.name == "update_telemetry")
_guard = next(n for n in _tele_fn.body
              if isinstance(n, _ast_t.If) and "running" in _ast_t.dump(n.test))
_calls = [n.value.func.attr for n in _guard.body
          if isinstance(n, _ast_t.Expr) and isinstance(n.value, _ast_t.Call)
          and isinstance(n.value.func, _ast_t.Attribute)]
check("the not-running branch refreshes before it returns",
      "follow_body" in _calls and "redraw" in _calls
      and isinstance(_guard.body[-1], _ast_t.Return), _calls)

print("== the first-run share question cannot be lost in silence ==")
# asked_to_share was written and saved BEFORE WelcomeWindow was constructed,
# and the construction was wrapped in "except Exception: pass". One failure
# and the only place the community database is ever offered was gone for
# good, with nothing said.
asker = A.EDSMT.__new__(A.EDSMT)
asker.settings = dict(A.DEFAULT_SETTINGS)
asked_said = []
asker.say = lambda text, colour=None: asked_said.append(text)
_real_welcome = A.WelcomeWindow
A.WelcomeWindow = lambda app: (_ for _ in ()).throw(RuntimeError("no display"))
asker.ask_to_share()
check("a prompt that fails to open leaves the question open",
      asker.settings.get("asked_to_share") is False,
      asker.settings.get("asked_to_share"))
check("and the commander is told instead of nothing happening",
      any("sharing question" in t for t in asked_said), asked_said)
A.WelcomeWindow = lambda app: object()
asker.ask_to_share()
check("a prompt that does open is never put twice",
      asker.settings.get("asked_to_share") is True)
A.WelcomeWindow = _real_welcome
_ask = src.split("def ask_to_share")[1].split("\n    def ")[0]
check("the flag follows the window, it does not lead it",
      _ask.find("WelcomeWindow(self)") < _ask.find('"asked_to_share"'),
      (_ask.find("WelcomeWindow(self)"), _ask.find('"asked_to_share"')))

print("== restoring a backup puts every view back in step ==")
import tkinter as _tk
_tk.filedialog.askopenfilename = lambda *a, **k: "/tmp/does-not-matter.zip"
_restored = []
_sw = A.SettingsWindow.__new__(A.SettingsWindow)
_sw.status = _ctkstub.ctk.CTkLabel(None)
_sw.app = type("App", (), {
    "store": type("S", (), {"restore_from": staticmethod(lambda p: 3)})(),
    "refresh_locations": staticmethod(lambda: _restored.append("locations")),
    "refresh_deposits": staticmethod(lambda: _restored.append("deposits")),
    "refresh_commodities": staticmethod(lambda: _restored.append("commodities")),
    "redraw": staticmethod(lambda: _restored.append("map"))})()
_sw.restore_now()
check("the deposit list is refreshed, not left showing the old database",
      "deposits" in _restored, _restored)
check("and so is everything else",
      set(_restored) == {"locations", "deposits", "commodities", "map"}, _restored)

print("== a corrected deposit goes back up, not just a mined-out one ==")
# EditWindow.save -> deposit_edited never re-uploaded, while mark_mined did.
# Fixing a wrong commodity locally left it wrong in the community database
# for ever.
_reshared = []
_ed = A.EDSMT.__new__(A.EDSMT)
_ed.store = SV.Survey(A.DATA_DIR)
_ed.settings = dict(A.DEFAULT_SETTINGS)
_ed.selected = None
_ed.say = lambda text, colour=None: None
for _name in ("refresh_locations", "refresh_deposits", "redraw", "on_pick"):
    setattr(_ed, _name, lambda *a, **k: None)
_ed.share = lambda row: _reshared.append(row)
check("there is a deposit to correct", len(_ed.store.deposits) > 0,
      len(_ed.store.deposits))
_victim = _ed.store.deposits[0]
_ed.deposit_edited(_victim["id"], {"commodity": "Bromellite"})
check("the correction was uploaded", len(_reshared) == 1, _reshared)
check("and it carries the corrected value, not the old one",
      _reshared and _reshared[0].get("commodity") == "Bromellite",
      _reshared[:1])
_reshared.clear()
_ed.deposit_edited("no-such-id", {"commodity": "Gold"})
check("a deposit that is gone uploads nothing", _reshared == [], _reshared)
_mm = src.split("def mark_mined")[1].split("\n    def ")[0]
check("and mark_mined does not now send it a second time",
      "self.share(" not in _mm, _mm)
_de = src.split("def deposit_edited")[1].split("\n    def ")[0]
check("the one door they both go through is deposit_edited",
      "self.share(row)" in _de)

print("== tick names what actually failed ==")
# Every failure in all four stages came out as "Journal problem: ..." - which
# is how a TypeError in the data store was blamed on the journal reader for
# weeks.
class _Idle:
    running = False
    where = "Elite is not running"

def _boom(message, kind=RuntimeError):
    def raiser(*a, **k):
        raise kind(message)
    return raiser

def _ticked(fail):
    app = A.EDSMT.__new__(A.EDSMT)
    app.settings = dict(A.DEFAULT_SETTINGS)
    app._seen_trouble = set()
    app.said = []
    app.say = lambda text, colour=None: app.said.append(text)
    app.collect_results = lambda: None
    app.after = lambda ms, fn: None
    app.log_location = lambda: None
    app.watcher = type("W", (), {
        "poll": staticmethod(
            _boom("journal folder has gone", IOError) if fail == "journal"
            else (lambda: _Idle())),
        # One note every tick, so the books are always given something to
        # do and a failure in them has somewhere to come from.
        "drain_runs": staticmethod(lambda: [{"event": "Docked"}]),
        "poll_status": staticmethod(lambda: False),
    })()
    app.earnings = type("E", (), {"observe": staticmethod(
        _boom("sessions.csv is read-only", OSError) if fail == "earnings"
        else (lambda note: None))})()
    app.earnings_note = lambda line: None
    app.update_earnings = (_boom("the hold is not a number", TypeError)
                           if fail == "hold" else (lambda: None))
    app.update_telemetry = (_boom("store said no", TypeError)
                            if fail == "display" else (lambda *a: None))
    app.report_online = (_boom("inara refused", RuntimeError)
                         if fail == "online" else (lambda *a: None))
    app.hotkeys = type("H", (), {"drain": staticmethod(
        _boom("hotkey thread died", OSError) if fail == "hotkey"
        else (lambda: ["deposit"]))})()
    app.marked = []
    app.mark_deposit = (_boom("rigs is not a number", ValueError)
                        if fail == "mark" else (lambda: app.marked.append(1)))
    app.flash_said = lambda: None
    # The keys live on the fast loop now, not at the end of tick.
    if fail in ("hotkey", "mark", "keys-after-journal"):
        if fail == "keys-after-journal":
            app.watcher.poll = staticmethod(_boom("journal folder has gone",
                                                  IOError))
            app.tick()
        app.fast_tick()
        if fail == "keys-after-journal":
            return app.marked
    else:
        app.tick()
    return app.said[-1] if app.said else ""

check("a journal failure is still called a journal failure",
      _ticked("journal").startswith("Journal problem"), _ticked("journal"))
check("a failure drawing the screen is not blamed on the journal",
      _ticked("display").startswith("Display problem"), _ticked("display"))
check("nor is a failure reporting to Inara",
      _ticked("online").startswith("Online reporting problem"), _ticked("online"))
check("nor the hotkey thread",
      _ticked("hotkey").startswith("Hotkey problem"), _ticked("hotkey"))
check("and F10 blowing up says F10, not the journal",
      _ticked("mark").startswith("Mark deposit problem"), _ticked("mark"))
check("a journal failing every tick no longer silences the keys - they are "
      "read on their own loop", _ticked("keys-after-journal") == [1])
_fast = src.split("def fast_tick")[1].split("\n    def ")[0]
check("that loop runs every FAST_TICK_MS, a tenth of a second",
      "self.after(FAST_TICK_MS, self.fast_tick)" in _fast
      and A.FAST_TICK_MS <= 100, A.FAST_TICK_MS)
_tick = src.split("    def tick(self)")[1].split("\n    def ")[0]
check("and tick itself no longer drains them",
      "hotkeys.drain" not in _tick)
# The books are the newest thing in tick and the first thing that would
# have been blamed on the reader, because the reader is what runs before
# them. Both halves - the bookkeeping and the readout it feeds - say
# earnings.
check("a failure in the books says earnings, not journal",
      _ticked("earnings").startswith("Earnings problem"), _ticked("earnings"))
check("and so does a failure drawing what the hold is worth",
      _ticked("hold").startswith("Earnings problem"), _ticked("hold"))
check("the message still carries the reason",
      "store said no" in _ticked("display"), _ticked("display"))
check("and it does for earnings too",
      "sessions.csv is read-only" in _ticked("earnings"), _ticked("earnings"))

_crash = os.path.join(A.DATA_DIR, "crash.log")
_noisy = A.EDSMT.__new__(A.EDSMT)
_noisy.settings = dict(A.DEFAULT_SETTINGS)
_noisy._seen_trouble = set()
_noisy.say = lambda text, colour=None: None
_noisy.collect_results = lambda: None
_noisy.after = lambda ms, fn: None
_noisy.log_location = _noisy.mark_deposit = lambda: None
_noisy.watcher = type("W", (), {"poll": staticmethod(
    _boom("folder gone", IOError)),
    "drain_runs": staticmethod(lambda: [])})()
_noisy.earnings = type("E", (), {"observe": staticmethod(lambda note: None)})()
_noisy.earnings_note = lambda line: None
_noisy.update_earnings = lambda: None
_noisy.update_telemetry = _noisy.report_online = lambda *a: None
_noisy.hotkeys = type("H", (), {"drain": staticmethod(lambda: [])})()
for _ in range(5):
    _noisy.tick()
_after = open(_crash, encoding="utf-8").read() if os.path.exists(_crash) else ""
check("the fault is written to crash.log", "folder gone" in _after, _after[-200:])
check("once, not eighty times a minute",
      _after.count("folder gone") == 1, _after.count("folder gone"))

print("== the overlay colour has a control, like everything else in settings ==")
_cs = A.SettingsWindow.__new__(A.SettingsWindow)
_cs.status = _ctkstub.ctk.CTkLabel(None)
_cs.fields, _cs.toggles, _cs.choices = {}, {}, {}
_cs.binders, _cs.bindings, _cs.colours = {}, {}, {}
_cs.secrets, _cs._hide_timers = {}, {}
_cs.app = type("App", (), {"settings": dict(A.DEFAULT_SETTINGS)})()
_cs._colour(_ctkstub.ctk.CTkFrame(None), "overlay_colour", "Overlay colour",
            [("Orange", A.ORANGE), ("Cyan", A.CYAN)], "pick or type one")
_cbox, _copts, _cpatch = _cs.colours["overlay_colour"]
_saved = {}
_cs.app.apply_settings = lambda data: _saved.update(data)

check("DEFAULT_SETTINGS still promises every key has a control",
      "Settings window" in A.DEFAULT_SETTINGS["_readme"])
# A21 was "overlay_colour is read and has no control". The answer then was a
# colour picker. The answer now is the theme picker, which sets the whole
# palette - and a theme row AND a colour row are two controls doing one job,
# which is the pair the commander bounced off. overlay_colour survives as a
# declared advanced hand-edit in PENDING_SETTINGS, which is what it is.
check("the instrument colour has a control - the theme picker",
      '"overlay_theme"' in src and "Overlay theme" in src)
check("and there is no second control competing with it",
      "Overlay colour" not in src, "two rows, one job")
check("the raw colour is declared as an advanced key, not silently read",
      "overlay_colour" in _io.open(os.path.join(os.path.dirname(
          os.path.dirname(os.path.abspath(__file__))), "overlay.py"),
          encoding="utf-8").read())
_cbox.set("Cyan")
_cs.save()
check("picking a name saves its hex, not its name",
      _saved.get("overlay_colour") == A.CYAN, _saved.get("overlay_colour"))
_saved.clear(); _cbox.set("#123456"); _cs.save()
check("a hand-typed hex survives the round trip",
      _saved.get("overlay_colour") == "#123456", _saved.get("overlay_colour"))
_saved.clear(); _cbox.set("puce"); _cs.save()
check("and something that is not a colour is refused, not stored",
      not _saved, _saved)
_cs.app.settings = {**A.DEFAULT_SETTINGS, "overlay_colour": "#abcdef"}
_cs.load()
check("a colour hand-edited into settings.json is shown, not thrown away",
      _cbox.get() == "#abcdef", _cbox.get())
check("the swatch follows it",
      _cpatch.cget("fg_color") == "#abcdef", _cpatch.cget("fg_color"))
check("is_colour knows a hex from a word",
      A.is_colour("#ff7a18") and not A.is_colour("orange")
      and not A.is_colour("#ff7a1") and not A.is_colour(""))

# ---------------------------------------------------------------------------
# The cockpit restyle
# ---------------------------------------------------------------------------
import ast as _ast, re as _re
_tree = _ast.parse(src)

print("== the palette is the only place a colour is written down ==")
PALETTE = ("VOID", "PANEL", "RAIL", "STEEL", "RULE", "ORANGE", "AMBER", "TEXT",
           "MUTED", "DIM", "FAINT", "GRID", "GREEN", "RED", "CYAN", "WARN",
           "DANGER", "SWEPT")
check("every named colour exists and is a hex",
      all(A.is_colour(getattr(A, name, "")) for name in PALETTE),
      [n for n in PALETTE if not A.is_colour(getattr(A, n, ""))])

_colour_kw = []
for _n in _ast.walk(_tree):
    if not isinstance(_n, _ast.Call):
        continue
    for _kw in _n.keywords:
        if not _kw.arg:
            continue
        if _kw.arg.endswith(("_color", "_colour")) or _kw.arg in ("fill", "outline"):
            for _c in _ast.walk(_kw.value):
                if isinstance(_c, _ast.Constant) and isinstance(_c.value, str) \
                        and _c.value.startswith("#"):
                    _colour_kw.append("line %d %s=%r" % (_n.lineno, _kw.arg, _c.value))
check("no widget is handed a colour typed in place", not _colour_kw, _colour_kw[:6])

# ...and nowhere else in the file either, bar the palette itself and the
# commodity wheel, which IS a palette.
_allowed_lines = set()
for _n in _tree.body:
    if isinstance(_n, _ast.Assign) and getattr(_n.targets[0], "id", "") in \
            PALETTE + ("COMMODITY_COLOURS",):
        for _s in _ast.walk(_n):
            if isinstance(_s, _ast.Constant):
                _allowed_lines.add(_s.lineno)
_stray = [(n.lineno, n.value) for n in _ast.walk(_tree)
          if isinstance(n, _ast.Constant) and isinstance(n.value, str)
          and _re.fullmatch(r"#[0-9a-fA-F]{6}", n.value)
          and n.lineno not in _allowed_lines]
check("and no loose hex is left anywhere in the file", not _stray, _stray)

print("== one type scale, not twelve ad-hoc font tuples ==")
SCALE = ("F_TITLE", "F_HEAD", "F_ACTION", "F_SECTION", "F_READOUT", "F_STRONG",
         "F_BODY", "F_SMALL", "F_SMALL_B", "F_MICRO")
check("every step of the scale exists", all(hasattr(A, n) for n in SCALE),
      [n for n in SCALE if not hasattr(A, n)])
check("and every one of them is the same face",
      all(getattr(A, n)[0] == A.FONT for n in SCALE))
check("nothing on it is smaller than 9pt",
      min(getattr(A, n)[1] for n in SCALE) >= 9,
      min(getattr(A, n)[1] for n in SCALE))
check("no font tuple is typed into a widget call any more",
      not _re.search(r'\("Consolas",\s*\d', src),
      _re.findall(r'\("Consolas",\s*\d+[^)]*\)', src)[:4])
_offscale = ["line %d" % n.lineno for n in _ast.walk(_tree)
             if isinstance(n, _ast.Call)
             for kw in n.keywords
             if kw.arg == "font" and not (
                 isinstance(kw.value, _ast.Name) and kw.value.id in SCALE
                 or isinstance(kw.value, _ast.Tuple))]
check("every font= on screen names a step of the scale", not _offscale, _offscale)

print("== every section heading goes through the one helper ==")
check("there is a shared helper", callable(A.hud_header))
_hh = [n for n in _ast.walk(_tree)
       if isinstance(n, _ast.FunctionDef) and n.name == "hud_header"][0]
_inside = range(_hh.lineno, _hh.end_lineno + 1)
_handmade = ["line %d" % n.lineno for n in _ast.walk(_tree)
             if isinstance(n, _ast.Call)
             and getattr(n.func, "attr", "") == "CTkLabel"
             and any(kw.arg == "font" and getattr(kw.value, "id", "") == "F_SECTION"
                     for kw in n.keywords)
             and n.lineno not in _inside]
check("no heading is built by hand beside it", not _handmade, _handmade)
_calls = [n for n in _ast.walk(_tree) if isinstance(n, _ast.Call)
          and getattr(n.func, "id", "") == "hud_header"]
check("and it is used across the app, not in one window",
      len(_calls) >= 8, len(_calls))
_section = src.split("def _section")[1].split("\n    def ")[0]
check("Settings' own section helper delegates to it too",
      "hud_header(" in _section, _section[:120])
_helper = src.split("def hud_header")[1].split("\ndef ")[0]
check("a control on the heading line takes its width before the rule expands",
      0 < _helper.find("trailing(bar)") < _helper.find("expand=True"),
      (_helper.find("trailing(bar)"), _helper.find("expand=True")))

print("== one visual language for buttons ==")
ROLES = {"BTN_PRIMARY", "BTN_SECONDARY", "BTN_WARN", "BTN_DANGER",
         "BTN_ROW", "BTN_GHOST", "BTN_HEADING"}
check("the roles are declared once, at the top",
      all(isinstance(getattr(A, r, None), dict) for r in ROLES),
      [r for r in ROLES if not isinstance(getattr(A, r, None), dict)])
_roleless, _mixed = [], []
for _n in _ast.walk(_tree):
    if not (isinstance(_n, _ast.Call)
            and getattr(_n.func, "attr", "") == "CTkButton"):
        continue
    _used = {x.id for kw in _n.keywords if kw.arg is None
             for x in _ast.walk(kw.value) if isinstance(x, _ast.Name)} & ROLES
    if not _used:
        _roleless.append("line %d" % _n.lineno)
    if any(kw.arg and kw.arg.endswith("_color") for kw in _n.keywords):
        _mixed.append("line %d" % _n.lineno)
check("every button on screen wears one of them", not _roleless, _roleless)
check("and none of them also carries a colour of its own", not _mixed, _mixed)
check("the destructive one is the only one that is red",
      A.BTN_DANGER["hover_color"] == A.RED
      and A.BTN_PRIMARY["fg_color"] == A.ORANGE
      and A.BTN_SECONDARY["fg_color"] == A.STEEL)

print("== the widget styles pass only keywords customtkinter accepts ==")
# A ** unpack is invisible to the static check in test_ctk_api, which reads
# kw.arg and finds None. Without this, the seven button roles and the five
# field styles could hand a widget a keyword it has never heard of and
# nothing would say so until a commander double-clicked the exe.
# The library is found on sys.path by hand. find_spec() consults
# sys.modules first, where this test has already put a stub whose
# __spec__ is None, and raises ValueError on it.
_ctk_root = next((os.path.join(_p, "customtkinter") for _p in sys.path
                  if os.path.isdir(os.path.join(_p, "customtkinter"))), None)
_params = {}
if _ctk_root:
    for _dp, _ds, _fs in os.walk(_ctk_root):
        for _f in _fs:
            if not _f.endswith(".py"):
                continue
            try:
                _t = _ast.parse(open(os.path.join(_dp, _f), encoding="utf-8").read())
            except SyntaxError:
                continue
            for _c in _ast.walk(_t):
                if isinstance(_c, _ast.ClassDef) and _c.name.startswith("CTk"):
                    for _it in _c.body:
                        if isinstance(_it, _ast.FunctionDef) and _it.name == "__init__":
                            _params[_c.name] = {
                                a.arg for a in list(_it.args.args)
                                + list(_it.args.kwonlyargs)} - {"self"}
# Pinned, so a machine without the library still checks something real.
FALLBACK = {
    "CTkButton": {"fg_color", "hover_color", "text_color", "border_width",
                  "border_color", "corner_radius"},
    "CTkComboBox": {"fg_color", "border_color", "button_color", "text_color",
                    "button_hover_color", "dropdown_fg_color", "corner_radius",
                    "dropdown_hover_color", "dropdown_text_color"},
    "CTkEntry": {"fg_color", "border_color", "text_color", "corner_radius",
                 "placeholder_text_color"},
    "CTkSwitch": {"fg_color", "progress_color", "button_color", "text_color",
                  "button_hover_color"},
    "CTkTextbox": {"fg_color", "border_color", "text_color", "border_width",
                   "corner_radius"},
    "CTkScrollableFrame": {"fg_color", "border_color", "border_width",
                           "corner_radius", "scrollbar_button_color",
                           "scrollbar_button_hover_color"},
}
STYLE_OWNER = [("CTkButton", r) for r in sorted(ROLES)] + [
    ("CTkComboBox", "BOX"), ("CTkEntry", "ENTRY"), ("CTkSwitch", "SWITCH"),
    ("CTkTextbox", "TEXTBOX"), ("CTkScrollableFrame", "LIST")]
_wrong = []
for _widget, _style in STYLE_OWNER:
    _ok = _params.get(_widget) or FALLBACK[_widget]
    _wrong += ["%s.%s" % (_style, k) for k in getattr(A, _style) if k not in _ok]
check("every style dict is made of real parameters", not _wrong, _wrong)
check("the library was actually read, not just the pinned list",
      len(_params) > 10 or not _ctk_root, (len(_params), _ctk_root))

print("== nothing on screen got smaller ==")
# The restyle is a restyle. A control that shrank is a control that became
# harder to hit, and that is the complaint this app gets most.
WAS = {"Overlay": 30, "Find": 30, "Settings": 30, "UPDATE AVAILABLE": 30,
       "log this one  F9": 24, "Best patch": 26, "Worked out": 26,
       "MARK DEPOSIT   F10": 52, "MINED OUT": 30, "Delete": 28,
       "Edit  (or double-click it)": 28, "edit": 26, "Reset": 26,
       "Share my finds": 38, "Not now": 38, "Save": 28, "Cancel": 28,
       "Back up now": 28, "Restore from a backup": 28,
       "Open my data folder": 28, "Check for updates": 28,
       "Test connection": 28, "Close": 28, "Copy all": 28,
       "Search sites": 28, "Individual deposits": 28, "Best sell prices": 28}
_shrunk, _measured = [], 0
for _n in _ast.walk(_tree):
    if not (isinstance(_n, _ast.Call)
            and getattr(_n.func, "attr", "") in ("CTkButton", "CTkComboBox")):
        continue
    _text = next((kw.value.value for kw in _n.keywords if kw.arg == "text"
                  and isinstance(kw.value, _ast.Constant)), None)
    _height = next((kw.value.value for kw in _n.keywords if kw.arg == "height"
                    and isinstance(kw.value, _ast.Constant)), None)
    if _height is None:
        continue
    _measured += 1
    _floor = WAS.get(_text, 26 if _n.func.attr == "CTkComboBox" else 20)
    if _height < _floor:
        _shrunk.append("%r %s < %s" % (_text, _height, _floor))
check("controls were actually measured", _measured >= 20, _measured)
check("not one of them is shorter than it was", not _shrunk, _shrunk)
check("MARK DEPOSIT is still the biggest thing in the rail",
      "height=54" in src.split("btn_mark = ")[1][:200], src.split("btn_mark = ")[1][:200])
check("the rail is no narrower than it was", A.RAIL_WIDTH >= 384, A.RAIL_WIDTH)

print("== the panels are framed, and the status line is an instrument ==")
check("there is a shared bracket helper", callable(A.bracket))
check("the map is framed", "bracket(centre" in src)
check("and so is every dialog panel it can be put on",
      src.count("bracket(") >= 7, src.count("bracket("))
# Per function, not per file: "body" is a CTkFrame in one window and a
# CTkScrollableFrame in another, and matching bare names across the whole
# module convicts the innocent one.
_slid = []
for _fn in [n for n in _ast.walk(_tree) if isinstance(n, _ast.FunctionDef)]:
    _local = {t.id for n in _ast.walk(_fn)
              if isinstance(n, _ast.Assign) and isinstance(n.value, _ast.Call)
              and getattr(n.value.func, "attr", "") == "CTkScrollableFrame"
              for t in n.targets if isinstance(t, _ast.Name)}
    if not _local:
        continue
    _slid += ["%s:%d" % (_fn.name, n.lineno) for n in _ast.walk(_fn)
              if isinstance(n, _ast.Call) and getattr(n.func, "id", "") == "bracket"
              and n.args and getattr(n.args[0], "id", "") in _local]
check("and never on a scroller, where the corners would slide away",
      not _slid, _slid)
_build = src.split("def _build")[1].split("\n    def ")[0]
check("the status line is labelled like a readout", 'text="STATUS"' in _build)
check("its label is fixed width and packed before the readout that expands",
      0 < _build.find('text="STATUS"') < _build.find("self.status.pack"),
      (_build.find('text="STATUS"'), _build.find("self.status.pack")))
check("and the readout is on the scale, not at body size",
      "font=F_READOUT" in _build)
_top = src.split("def _telemetry")[1].split("\n    def ")[0]
check("the header strip is ruled off from the rail and the map",
      "fg_color=RULE" in _top and "columnspan=4" in _top)
check("the rail and the map are still side by side under it",
      "centre.grid(row=1, column=1" in src and "frame.grid(row=1, column=0" in src)
check("bind_all is still nowhere near this file",
      "bind_" + "all" not in src)

# ===========================================================================
# Backlog #24 - every auto-fill, driven end to end
# ===========================================================================
# "Make sure the auto fills work properly and recheck everything." Each one
# below is driven through real journal state rather than asserted against a
# fixture, because the two failures this area has already shipped both
# passed a fixture: A6 (planet_class read a dict keyed by body name, so it
# was always None) and A11 (the code that fills the window sat past an early
# return, so a cold start with Elite shut drew nothing).

AFD = os.path.join(TMP, "autofill"); os.makedirs(AFD)
AFJ = os.path.join(AFD, "Journal.2026-09-14T090000.01.log")
def af_emit(*events):
    with open(AFJ, "a", encoding="utf-8") as fh:
        for e in events: fh.write(json.dumps(e) + "\n")
def af_status(**kw):
    d = {"timestamp": "2026-09-14T09:00:00Z", "event": "Status",
         "Flags": 2 | (1 << 21) | (1 << 26)}
    d.update(kw)
    open(os.path.join(AFD, "Status.json"), "w", encoding="utf-8").write(json.dumps(d))

AFR = 1_800_000.0
af_emit({"timestamp":"2026-09-14T08:59:00Z","event":"Fileheader",
         "gameversion":"4.4.1.1","part":1},
        {"timestamp":"2026-09-14T08:59:01Z","event":"Commander","Name":"Flossy","FID":"F9"},
        {"timestamp":"2026-09-14T08:59:20Z","event":"Location","StarSystem":"Hyades Sector DB-X d1-112",
         "StarPos":[12.0,-3.0,44.0],"SystemAddress":1234567})

AFDATA = os.path.join(TMP, "autofill-data"); os.makedirs(AFDATA)

def af_app(settings=None):
    """A window with nothing but the parts the auto-fills touch."""
    it = A.EDSMT.__new__(A.EDSMT)
    it.settings = dict(A.DEFAULT_SETTINGS)
    it.settings.update(settings or {})
    it.store = SV.Survey(AFDATA)
    it.watcher = JN.JournalWatcher(AFD)
    it.game = None
    it.selected = None
    it._known_body = None
    it._known_world = None
    it._autofilled = {}
    it.prices = {}
    it.overlay = type("O", (), {"showing": False})()
    it.location_box = _ctkstub.ctk.CTkComboBox(None, values=["1"])
    it.location_box.set("1")
    it.location_box_list = _ctkstub.ctk.CTkScrollableFrame(None)
    it.deposit_list = _ctkstub.ctk.CTkScrollableFrame(None)
    it.deposit_header = _ctkstub.ctk.CTkLabel(None)
    it.location_note = _ctkstub.ctk.CTkLabel(None)
    it.t_where = _ctkstub.ctk.CTkLabel(None)
    it.t_detail = _ctkstub.ctk.CTkLabel(None)
    it.btn_mark = _ctkstub.ctk.CTkButton(None)
    it.fields = {k: _ctkstub.ctk.CTkComboBox(None, values=[])
                 for k in ("commodity", "rigs", "density", "amount")}
    for b in it.fields.values(): b.set("")
    it.plan = type("P", (), {"show": lambda s, rows=None, **kw: None,
                             "select": lambda s, i: None})()
    it.say = lambda text, colour=None: None
    it.share = lambda record: None
    it.draw_overlay = lambda rows, heading, **kw: None
    return it

print("== the system and the body fill themselves in while you play ==")
af = af_app()
af.game = af.watcher.poll()
check("the system arrived without anybody typing it",
      af.game.system == "Hyades Sector DB-X d1-112", af.game.system)
check("and no body yet, because we are not at one",
      not af.game.body, af.game.body)
af_emit({"timestamp":"2026-09-14T08:59:40Z","event":"ApproachBody",
         "StarSystem":"Hyades Sector DB-X d1-112","Body":"Hyades Sector DB-X d1-112 3 a"})
af_status(Latitude=-8.25, Longitude=140.75, Heading=270,
          BodyName="Hyades Sector DB-X d1-112 3 a", PlanetRadius=AFR)
af.game = af.watcher.poll()
af.update_telemetry(af.game)
check("the body filled itself in too",
      af.here() == ("Hyades Sector DB-X d1-112",
                    "Hyades Sector DB-X d1-112 3 a"), af.here())
check("and the readout is showing it, not a placeholder",
      "Hyades Sector DB-X d1-112 3 a" in af.t_where.cget("text"),
      af.t_where.cget("text"))
check("the position is on the readout as well",
      "-8.25" in af.t_detail.cget("text"), af.t_detail.cget("text"))
check("the body it now follows is the one under us",
      af._known_body == ("Hyades Sector DB-X d1-112",
                         "Hyades Sector DB-X d1-112 3 a"), af._known_body)
check("and it was written to settings, for the next time the game is shut",
      af.settings.get("last_body") == "Hyades Sector DB-X d1-112 3 a",
      af.settings.get("last_body"))

print("== the commodity list re-sorts when the scan lands after the body ==")
# The Scan is not synchronised with anything. You drop in, you land, and
# PlanetClass turns up whenever it turns up - which is normally after the
# body is already known. follow_body only ever watched (system, body), so
# the list built at touchdown was the one you kept all session: an icy body
# offering the rocky order, with Low Temperature Diamonds forty rows down.
before = list(af.fields["commodity"]._values)
check("with no scan yet, the list is the generic order",
      before[:3] == SV.by_value([c for c in SV.KNOWN_COMMODITIES], {})[:3],
      before[:3])
af_emit({"timestamp":"2026-09-14T08:59:45Z","event":"Scan",
         "BodyName":"Hyades Sector DB-X d1-112 3 a","Radius":AFR,
         "PlanetClass":"Icy body","SurfaceTemperature":61.0,
         "SurfaceGravity":1.62,"Volcanism":"minor water geysers volcanism"})
af.game = af.watcher.poll()
check("planet_class reads the body we are standing on",
      af.planet_class() == "Icy body", af.planet_class())
af.update_telemetry(af.game)
after = list(af.fields["commodity"]._values)
check("the same body, but the list moved when the class arrived",
      after[:3] != before[:3], (before[:3], after[:3]))
icy = SV.for_body(list(SV.KNOWN_COMMODITIES), "Icy body")[0]
check("and what an icy body can hold is now at the top",
      after[0] in icy and after[1] in icy and after[2] in icy, after[:3])
check("nothing was dropped from the list to do it",
      sorted(after) == sorted(before), len(after) - len(before))

print("== planet_class comes from the body, not from a dict keyed by name ==")
# A6: body_facts is {body_name: {...}}, so .get("planet_class") on it was
# always None and the ordering above could never once have happened.
_pc = src.split("def planet_class")[1].split("\n    def ")[0]
check("it asks body_profile(), the accessor that resolves the body",
      "body_profile()" in _pc, _pc[:120])
# On the parse tree, not in the text: the comment above the fix names
# body_facts, so a string search lands on the prose that explains the bug
# rather than on the bug.
_pc_fn = next(n for n in _ast.walk(_ast.parse(src))
              if isinstance(n, _ast.FunctionDef) and n.name == "planet_class")
check("and never reads body_facts as if it were one body's facts",
      not [n for n in _ast.walk(_pc_fn) if isinstance(n, _ast.Attribute)
           and n.attr == "body_facts"], "body_facts is read directly")

print("== the scanner naming a commodity fills the box, every time ==")
af_emit({"timestamp":"2026-09-14T09:01:00Z","event":"SurfaceDepositProspected",
         "Deposit":{"Type":"$magnesite_name;","Type_Localised":"Magnesite",
                    "Density":"Medium"}})
af.game = af.watcher.poll()
af.update_telemetry(af.game)
check("the scanner's reading is in the commodity box",
      af.fields["commodity"].get() == "Magnesite", af.fields["commodity"].get())
check("and its density too", af.fields["density"].get() == "Medium",
      af.fields["density"].get())
# The one that actually cost data: the old rule was "fill it only if the box
# is empty", and nothing empties it. So the SECOND deposit of the session
# was filed under the first one's name - into the community database, with
# nothing on screen saying so.
af_emit({"timestamp":"2026-09-14T09:03:00Z","event":"SurfaceDepositProspected",
         "Deposit":{"Type":"$olivine_name;","Type_Localised":"Olivine",
                    "Density":"High"}})
af.game = af.watcher.poll()
af.update_telemetry(af.game)
check("drive to the next deposit and the box follows the scanner",
      af.fields["commodity"].get() == "Olivine", af.fields["commodity"].get())
check("so does the density", af.fields["density"].get() == "High",
      af.fields["density"].get())
check("and F10 would now record what is actually under you",
      af.fields["commodity"].get() == af.game.detected_type,
      (af.fields["commodity"].get(), af.game.detected_type))

print("== but what the commander typed is theirs ==")
af.fields["commodity"].set("Bromellite")
af.fields["density"].set("Low")
af_emit({"timestamp":"2026-09-14T09:05:00Z","event":"SurfaceDepositProspected",
         "Deposit":{"Type":"$ruby_name;","Type_Localised":"Ruby","Density":"Medium"}})
af.game = af.watcher.poll()
af.update_telemetry(af.game)
check("a typed commodity is not overwritten by the scanner",
      af.fields["commodity"].get() == "Bromellite", af.fields["commodity"].get())
check("nor a typed density", af.fields["density"].get() == "Low",
      af.fields["density"].get())

print("== the signal picker follows the body, not the last one you were on ==")
af.store.set_location("Hyades Sector DB-X d1-112",
                      "Hyades Sector DB-X d1-112 3 a", "3",
                      lat=-8.25, lon=140.75, radius_m=AFR,
                      commodities=["Magnesite", "Olivine"], cmdr="Flossy")
af.refresh_locations()
check("the picker is offering the numbers the body has",
      "3" in af.location_box._values, af.location_box._values[:5])
# customtkinter's configure(values=...) only swaps the dropdown's list; it
# never touches the entry text (ctk_combobox.py, configure()). So the thing
# worth asserting is not that the text survives - it always does - but that
# the number showing is still one the list OFFERS. A picker displaying a
# signal it no longer lists is a signal you cannot get back to after
# clicking away from it.
af.store.set_location("Hyades Sector DB-X d1-112",
                      "Hyades Sector DB-X d1-112 3 a", "61",
                      lat=-8.2, lon=140.7, cmdr="Flossy")
af.location_box.set("61")
af.refresh_signal_box()
check("a signal past the standard forty is offered because it was logged",
      "61" in af.location_box._values, af.location_box._values[-3:])
check("and what is showing is still something the list offers",
      af.location_box.get() in af.location_box._values,
      (af.location_box.get(), af.location_box._values[-3:]))
af.location_box.set("3")
af.refresh_signal_box()
check("the signal list on the rail has the row on it",
      len(af.location_box_list.winfo_children()) > 0)

print("== what the signal offers feeds the commodity box first ==")
af.refresh_commodities()
offered = list(af.fields["commodity"]._values)
check("what this body's own signal listed is at the top",
      set(offered[:2]) == {"Magnesite", "Olivine"}, offered[:4])
check("with everything else still underneath it",
      len(offered) > 10, len(offered))

print("== typing in the commodity box narrows the list without losing it ==")
af.fields["commodity"].set("oli")
af.commodity_typed()
narrowed = list(af.fields["commodity"]._values)
check("the list narrowed to what was typed",
      narrowed and all("oli" in n.lower() for n in narrowed), narrowed[:4])
af.fields["commodity"].set("")
af.refresh_commodities()
check("and clearing it puts the whole list back",
      len(af.fields["commodity"]._values) == len(offered),
      len(af.fields["commodity"]._values))

print("== the picker grows to whatever the DSS counted ==")
# The standard list is forty. A body the DSS says has more than that has to
# extend it, or a signal the game will happily drop you into is one this
# app cannot record a find in.
_many = af_app()
_many.game = type("S", (), {"system": "", "body": "",
                            "mining_signals": lambda s: 44})()
check("a DSS count past the standard list extends it",
      "44" in _many.signal_choices(), len(_many.signal_choices()))
check("and the standard forty are all still there",
      _many.signal_choices()[:40] == [str(n) for n in range(1, 41)])
_few = af_app()
_few.game = type("S", (), {"system": "", "body": "",
                           "mining_signals": lambda s: 3})()
check("a body with only three still offers the full list, because a signal "
      "the DSS missed is still a signal you can drive into",
      len(_few.signal_choices()) >= 40, len(_few.signal_choices()))

print("== the note under the picker follows the signal, unasked ==")
_note = af_app()
_note.game = None
_note.settings["last_system"] = "Hyades Sector DB-X d1-112"
_note.settings["last_body"] = "Hyades Sector DB-X d1-112 3 a"
_note.location_box.set("3")
_note.refresh_location_note()
check("it lists what that signal offers",
      "Magnesite" in _note.location_note.cget("text"),
      _note.location_note.cget("text"))
_note.location_box.set("29")
_note.refresh_location_note()
check("and a signal never logged says how to log it, with the key it has",
      A.key_text(A.DEFAULT_SETTINGS["hotkey_location"])
      in _note.location_note.cget("text"),
      _note.location_note.cget("text"))

print("== F9 puts what the scanner named into the signal's own list ==")
_f9 = af_app()
af_status(Latitude=-8.25, Longitude=140.75, Heading=270,
          BodyName="Hyades Sector DB-X d1-112 3 a", PlanetRadius=AFR)
af_emit({"timestamp":"2026-09-14T09:40:00Z","event":"SurfaceDepositProspected",
         "Deposit":{"Type":"$thortveitite_name;","Type_Localised":"Thortveitite"}})
_f9.game = _f9.watcher.poll()
_f9.location_box.set("11")
_f9.refresh_locations = lambda: None
_f9.refresh_deposits = lambda: None
_f9.redraw = lambda: None
_f9.log_location()
_sig = _f9.store.location("Hyades Sector DB-X d1-112",
                         "Hyades Sector DB-X d1-112 3 a", "11")
check("the signal was recorded where we stood", _sig is not None)
check("with the scanner's commodity already on its list",
      "Thortveitite" in _f9.store.offered(_sig), _sig and _sig["commodities"])
check("and the body radius, for the distance maths",
      _sig["radius_m"] == "1800000", _sig["radius_m"])

print("== F10 fills in everything the game knows, unasked ==")
af.fields["commodity"].set("Magnesite")
af.fields["rigs"].set("2")
af.fields["amount"].set("High")
af.fields["density"].set("Low")
af.refresh_locations = lambda: None
af.refresh_deposits = lambda: None
af.refresh_commodities = lambda: None
af.redraw = lambda: None
af.mark_deposit()
rec = af.store.at("Hyades Sector DB-X d1-112",
                  "Hyades Sector DB-X d1-112 3 a", "3")[-1]
check("the world class went onto the record without being typed",
      rec["planet_class"] == "Icy body", rec["planet_class"])
check("so did gravity", rec["gravity"], rec["gravity"])
check("and volcanism", "geysers" in rec["volcanism"].lower(), rec["volcanism"])
check("and the surface temperature", rec["temperature_k"] == "61.0",
      rec["temperature_k"])
check("the commander came from the journal, never a box",
      rec["cmdr"] == "Flossy", rec["cmdr"])
check("and the position is where the game said we were",
      rec["lat"].startswith("-8.25"), rec["lat"])

print("== with the game shut it all still fills in, from disk ==")
# A11 in its own right: every fallback written for a shut game used to sit
# past update_telemetry's early return.
shut = af_app({"last_system": "Hyades Sector DB-X d1-112",
               "last_body": "Hyades Sector DB-X d1-112 3 a"})
shut.game = None
shut.show_records()
check("it knows which body to show without a journal",
      shut.here() == ("Hyades Sector DB-X d1-112",
                      "Hyades Sector DB-X d1-112 3 a"), shut.here())
check("the commodity box is filled from what is recorded there",
      "Magnesite" in shut.fields["commodity"]._values[:4],
      shut.fields["commodity"]._values[:4])
check("and it is ordered by the world, read back off the deposits",
      shut.planet_class() == "Icy body", shut.planet_class())
check("the signal list drew its rows", 
      len(shut.location_box_list.winfo_children()) > 0)
check("and so did the deposit list",
      len(shut.deposit_list.winfo_children()) > 0)
# The tick a shut game produces must not undo any of it.
drawn_shut = []
shut.plan = type("P", (), {"show": lambda s, rows=None, **kw: drawn_shut.append(rows),
                           "select": lambda s, i: None})()
shut.update_telemetry(type("S", (), {"running": False, "where": "not running"})())
check("a tick with no game still draws what is on disk",
      drawn_shut and drawn_shut[-1], drawn_shut[-1:])
check("and the commodity box survived it",
      len(shut.fields["commodity"]._values) > 10,
      len(shut.fields["commodity"]._values))

print("== changing body re-reads everything for the new one ==")
moved = af_app()
af_emit({"timestamp":"2026-09-14T09:20:00Z","event":"ApproachBody",
         "StarSystem":"Hyades Sector DB-X d1-112","Body":"Hyades Sector DB-X d1-112 3 b"},
        {"timestamp":"2026-09-14T09:20:01Z","event":"Scan",
         "BodyName":"Hyades Sector DB-X d1-112 3 b","Radius":AFR,
         "PlanetClass":"Metal rich body","SurfaceTemperature":402.0})
af_status(Latitude=1.5, Longitude=2.5, Heading=10,
          BodyName="Hyades Sector DB-X d1-112 3 b", PlanetRadius=AFR)
moved.game = moved.watcher.poll()
moved.update_telemetry(moved.game)
check("the new body is the one being followed",
      moved._known_body[1].endswith("3 b"), moved._known_body)
check("and the commodity list is ordered for THAT world",
      moved.fields["commodity"]._values[0]
      in SV.for_body(list(SV.KNOWN_COMMODITIES), "Metal rich body")[0],
      moved.fields["commodity"]._values[:3])
check("the signal list is the new body's, not the old body's",
      all("3 a" not in _lbl.cget("text")
          for _lbl in moved.location_box_list.winfo_children()
          if isinstance(_lbl.cget("text"), str)), "old body's rows left behind")

# ===========================================================================
# Backlog #29 - taking another tool's CSV
# ===========================================================================
# The two header rows below are the ones those files really carry, copied
# exactly - the tests assert against them, not against anything this repo
# made up. Both layouts are written to a file called surfaceminingmap.csv,
# which is exactly why the header has to decide and the commander must never
# be asked.
BEARING_HEADER = ("system,planet,mining_spot_number,type,rigs,direction,"
                 "distance,lat,long")
CENTRES_HEADER = "System,Planet,SpotNum,Type,Rigs,Lat,Long,IsCenter"

IMPD = os.path.join(TMP, "imports"); os.makedirs(IMPD)
def wrote(name, text, encoding="utf-8"):
    path = os.path.join(IMPD, name)
    with open(path, "w", encoding=encoding, newline="") as fh:
        fh.write(text)
    return path

print("== the file says which tool wrote it, so nobody is asked ==")
check("the bearing-and-range layout is recognised",
      A.detect_import_format(BEARING_HEADER.split(",")) == "bearing",
      A.detect_import_format(BEARING_HEADER.split(",")))
check("so is the signal-centres layout, capitals and all",
      A.detect_import_format(CENTRES_HEADER.split(",")) == "centres",
      A.detect_import_format(CENTRES_HEADER.split(",")))
check("the two are told apart by the header, not the filename",
      A.detect_import_format(BEARING_HEADER.split(","))
      != A.detect_import_format(CENTRES_HEADER.split(",")))
check("a column order nobody promised still works",
      A.detect_import_format(list(reversed(CENTRES_HEADER.split(",")))) == "centres")
check("and a column somebody added of their own does not lock them out",
      A.detect_import_format(BEARING_HEADER.split(",") + ["notes"]) == "bearing")
check("something else entirely is not recognised",
      A.detect_import_format(["date", "amount", "payee"]) is None)
check("nor is a header that is only half of one",
      A.detect_import_format(["system", "planet", "type"]) is None)
check("the app can say what it expected",
      "mining_spot_number" in A.import_expectations()
      and "iscenter" in A.import_expectations(), A.import_expectations())

print("== the columns land on this app's own fields ==")
_real_data = A.DATA_DIR
IMP_DATA = os.path.join(TMP, "import-data"); os.makedirs(IMP_DATA)
A.DATA_DIR = IMP_DATA
imp_store = SV.Survey(IMP_DATA)
bearing_file = wrote("surfaceminingmap.csv",
               BEARING_HEADER + "\n"
               "Ega,Ega 1,3,Magnesite,4,215.0,1.26,12.501000,-45.502000\n"
               "Ega,Ega 1,3,Olivine,2,35.0,0.90,12.507000,-45.499000\n")
got = A.import_finds(imp_store, bearing_file)
check("it read the file", got["ok"], got["reason"])
check("and named the layout it came from", got["format"] == "bearing",
      got["format"])
check("both finds arrived", got["taken"] == 2, got)
row = [d for d in imp_store.deposits if d["commodity"] == "Magnesite"][0]
check("system -> system", row["system"] == "Ega", row["system"])
check("planet -> body", row["body"] == "Ega 1", row["body"])
check("mining_spot_number -> location", row["location"] == "3", row["location"])
check("type -> commodity", row["commodity"] == "Magnesite", row["commodity"])
check("rigs -> rigs", row["rigs"] == "4", row["rigs"])
check("lat -> lat", row["lat"] == "12.501000", row["lat"])
check("long -> lon", row["lon"] == "-45.502000", row["lon"])
check("and the row says where it came from",
      "with bearing and range" in row["notes"], row["notes"])
check("a signal row exists so the body knows the finds are in one",
      imp_store.location("Ega", "Ega 1", "3") is not None)

print("== a centre row in the signal-centres layout is a signal, not a deposit ==")
# IsCenter is the one column this app has no column for. It marks the row
# that IS the mining location signal. Filing it as a deposit would invent a
# find nobody ever made.
centres_file = wrote("centres.csv",
               CENTRES_HEADER + "\n"
               "Ega,Ega 2,7,,0,3.500000,88.250000,True\n"
               "Ega,Ega 2,7,Sapphire,5,3.510000,88.260000,False\n"
               "Ega,Ega 2,7,Ruby,3,3.520000,88.270000,False\n")
got2 = A.import_finds(imp_store, centres_file)
check("the panel's file is read too", got2["ok"], got2["reason"])
check("two deposits, not three", got2["taken"] == 2, got2)
check("and the centre became a signal", got2["signals"] == 1, got2)
sig = imp_store.location("Ega", "Ega 2", "7")
check("the signal is where their centre row said",
      sig and sig["lat"] == "3.500000", sig and sig["lat"])
check("no deposit was invented from the centre row",
      not [d for d in imp_store.deposits
           if d["body"] == "Ega 2" and not d["commodity"]])
check("SpotNum -> location", 
      all(d["location"] == "7" for d in imp_store.deposits if d["body"] == "Ega 2"))

# And a centre somebody already stood on and logged is not moved by
# somebody else's file saying it is somewhere slightly different.
moved_centre = wrote("centres-2.csv",
                     CENTRES_HEADER + "\n"
                     "Ega,Ega 2,7,,0,9.999000,11.111000,True\n"
                     "Ega,Ega 2,7,Iridium,2,9.998000,11.112000,False\n")
got2b = A.import_finds(imp_store, moved_centre)
check("the deposit in the second file still came in", got2b["taken"] == 1, got2b)
check("but the signal already logged was not moved",
      imp_store.location("Ega", "Ega 2", "7")["lat"] == "3.500000",
      imp_store.location("Ega", "Ega 2", "7")["lat"])
check("and it was counted as left alone, not silently dropped",
      got2b["duplicates"] == 1, got2b)

print("== the same file cannot be imported twice ==")
again = A.import_finds(imp_store, bearing_file)
check("a second run is refused", not again["ok"], again)
check("and it says why", "already been imported" in again["reason"],
      again["reason"])
check("nothing was added", len(imp_store.deposits) == 5,
      len(imp_store.deposits))
# By content, not by name: the file people actually hand you is a copy with
# a different name on it.
copied = wrote("their-finds-final-v2.csv", open(bearing_file, encoding="utf-8").read())
renamed = A.import_finds(imp_store, copied)
check("a renamed copy is caught as the same file", not renamed["ok"], renamed)
check("still nothing added", len(imp_store.deposits) == 5,
      len(imp_store.deposits))

print("== and nothing already here is ever overwritten ==")
before_rows = [dict(d) for d in imp_store.deposits]
overlap = wrote("overlap.csv",
                BEARING_HEADER + "\n"
                "Ega,Ega 1,3,Magnesite,6,215.0,1.26,12.501000,-45.502000\n"
                "Ega,Ega 1,3,Bromellite,1,10.0,3.00,12.600000,-45.400000\n")
got3 = A.import_finds(imp_store, overlap)
check("the one already here was left alone", got3["duplicates"] == 1, got3)
check("the new one came in", got3["taken"] == 1, got3)
kept = [d for d in imp_store.deposits if d["commodity"] == "Magnesite"][0]
check("their rig count did not overwrite ours",
      kept["rigs"] == "4", kept["rigs"])
check("the existing row is byte for byte what it was",
      kept == [d for d in before_rows if d["commodity"] == "Magnesite"][0],
      kept)
check("the duplicate rule is the server's own, to three places",
      A.deposit_fingerprint("Ega", "Ega 1", "3", "Magnesite", 12.5014, -45.5016)
      == A.deposit_fingerprint("Ega", "Ega 1", "3", "Magnesite", 12.5011, -45.5019))
check("but two real deposits a kilometre apart are still two",
      A.deposit_fingerprint("Ega", "Ega 1", "3", "Magnesite", 12.501, -45.502)
      != A.deposit_fingerprint("Ega", "Ega 1", "3", "Magnesite", 12.507, -45.499))
check("and a row with no position at all is not everybody else's twin",
      A.deposit_fingerprint("Ega", "Ega 1", "3", "Magnesite", "", "")
      .endswith("nopos"))

print("== a file it does not know is refused, by name ==")
junk = wrote("bank.csv", "date,amount,payee\n2026-01-01,5,x\n")
refused = A.import_finds(imp_store, junk)
check("refused", not refused["ok"])
check("it names the bearing-and-range header it wanted",
      "mining_spot_number" in refused["reason"], refused["reason"])
check("and the signal-centres one", "iscenter" in refused["reason"],
      refused["reason"])
check("nothing was imported from it", len(imp_store.deposits) == 6,
      len(imp_store.deposits))
check("a file that is not there says so, rather than throwing",
      not A.import_finds(imp_store, os.path.join(IMPD, "nope.csv"))["ok"])

print("== rubbish in a row is skipped and counted, never stored as a find ==")
messy = wrote("messy.csv",
              BEARING_HEADER + "\n"
              ",,,,,,,,\n"
              "Ega,,3,Magnesite,4,215.0,1.26,12.9,-45.9\n"
              "Ega,Ega 3,3,,4,215.0,1.26,12.9,-45.9\n"
              "Ega,Ega 3,3,Ruby,99,215.0,1.26,12.900000,-45.900000\n"
              "Ega,Ega 3,3,Olivine,2,,,notanumber,alsonot\n")
got4 = A.import_finds(imp_store, messy)
check("the rows with no body or no commodity were skipped",
      got4["unusable"] == 2, got4)
check("and the usable ones still came in", got4["taken"] == 2, got4)
ruby = [d for d in imp_store.deposits if d["commodity"] == "Ruby"
        and d["body"] == "Ega 3"][0]
check("99 rigs is not a rig count this game can produce, so it is blank",
      ruby["rigs"] == "", ruby["rigs"])
noplace = [d for d in imp_store.deposits if d["commodity"] == "Olivine"
           and d["body"] == "Ega 3"][0]
check("a row with no usable position is still kept for what it does say",
      noplace["lat"] == "" and noplace["commodity"] == "Olivine",
      (noplace["lat"], noplace["commodity"]))

print("== the database is backed up before an import touches it ==")
check("the run that had something to lose wrote a zip", got3["backup"],
      got3["backup"])
check("the zip is really there", os.path.exists(got3["backup"] or ""),
      got3["backup"])
check("and the report says so, by name",
      os.path.basename(got3["backup"]) in A.import_summary(got3),
      A.import_summary(got3))
# A backup that could not be written does not block the import - somebody
# with a full disk still wants their finds - but it is never silent, or
# "you can undo this" becomes a promise nobody kept.
_broke = dict(got3)
_broke["backup"], _broke["backup_failed"] = "", "No space left on device"
check("a backup that failed is said out loud, not swallowed",
      "could not be written" in A.import_summary(_broke),
      A.import_summary(_broke))
check("and the import still counts as done",
      A.import_summary(_broke).startswith("Imported"), A.import_summary(_broke))

print("== the report says what it took and what it skipped ==")
line = A.import_summary(got3)
check("how many it took", "1 find" in line, line)
check("which layout", "with bearing and range" in line, line)
check("and what it left alone", "already here" in line, line)
check("a refusal reports itself the same way",
      A.import_summary(refused) == refused["reason"])

print("== a CSV that has been through Windows still reads ==")
cp = wrote("german.csv",
           BEARING_HEADER + "\nEga,Ega 4,1,Bastnäsite,3,10.0,1.0,1.0,2.0\n",
           encoding="cp1252")
got5 = A.import_finds(imp_store, cp)
check("cp1252 is not a reason to lose somebody's finds", got5["taken"] == 1,
      got5)
check("and the accent survived",
      any(d["commodity"] == "Bastnäsite" for d in imp_store.deposits))
bom = wrote("bom.csv", "﻿" + BEARING_HEADER +
            "\nEga,Ega 5,1,Ruby,3,10.0,1.0,1.0,2.0\n")
check("a byte order mark does not hide the header",
      A.import_finds(imp_store, bom)["taken"] == 1)

print("== and it is a button in Settings, next to the backup controls ==")
_finds = src.split('self._section(body, "Your finds"')[1].split("self._section")[0]
check("the import button is in the same section as Back up now",
      "self.import_now" in _finds and "self.backup_now" in _finds)
check("the button says what it does",
      "Import another tool's CSV" in _finds, _finds[:200])
check("SettingsWindow really has the method the button names",
      callable(getattr(A.SettingsWindow, "import_now", None)))
_imp_now = src.split("def import_now")[1].split("\n    def ")[0]
check("it puts every view back in step afterwards, not just the map",
      all(name in _imp_now for name in ("refresh_locations", "refresh_deposits",
                                        "refresh_commodities", "redraw")))
check("and it never asks which tool wrote the file",
      "askopenfilename" in _imp_now and "detect_import_format" not in _imp_now)
A.DATA_DIR = _real_data

print("== the commander who first mapped it, on every table that lists one ==")
# Reported three times. It was on the deposits table only, so the commander
# who first mapped a site was invisible on "Search sites" - which is the
# search people actually use - and on "Still there". _found_by existed and
# exactly one caller used it.
_tables = src.split("def _render")[0]
check("the sites table has a Found by column",
      '"Last seen", "Found by"' in src, "sites headers")
check("the Still there table has one too",
      '"Last seen", "Found by"' in src and src.count('"Found by"') >= 3,
      src.count('"Found by"'))
check("and every one of those tables actually fills it in",
      src.count("self._found_by(row)") >= 3, src.count("self._found_by(row)"))
_rowfns = [n for n in _ast.walk(_ast.parse(src))
           if isinstance(n, _ast.FunctionDef)
           and n.name in ("_site_row", "_deposit_row", "_intact_row")]
check("all three row builders exist", len(_rowfns) == 3,
      [n.name for n in _rowfns])
_missing = [n.name for n in _rowfns
            if "_found_by" not in _ast.dump(n)]
check("and not one of them leaves the commander out", not _missing, _missing)
# The header count and the row length have to agree or the column silently
# shifts - which is how a table ends up showing the score under "Found by".
for _name, _head in (("_site_row", ["System", "Body", "Signal", "Rigs", "Types",
                                    "Last seen", "Found by", "Score"]),
                     ("_intact_row", ["System", "Body", "Signal", "Still there",
                                      "Rigs", "Types", "Last seen", "Found by"])):
    _fn = next(n for n in _rowfns if n.name == _name)
    _ret = next(n for n in _ast.walk(_fn) if isinstance(n, _ast.Return))
    check("%s returns one cell per heading" % _name,
          isinstance(_ret.value, _ast.List)
          and len(_ret.value.elts) == len(_head),
          (len(_ret.value.elts) if isinstance(_ret.value, _ast.List) else "?",
           len(_head)))
check("an unnamed uploader reads as an answer, not a blank cell",
      "ANONYMOUS" in src)

print("== the surface is detected in every state a commander can be in ==")
# "Still isn't detecting me on the surface" - a beta report against 1.10025.
# The reader gated position on Flags bit 21. Two real states on a planet do
# not set it, and in both the body name still filled in, so the app looked
# alive while refusing to mark anything.
_F_LANDED, _F_LATLONG, _F_SHIP, _F_SRV = 1 << 1, 1 << 21, 1 << 24, 1 << 26
_F2_FOOT, _F2_PLANET, _F2_GLIDE, _F2_EXT = 1 << 0, 1 << 4, 1 << 12, 1 << 15
_SURFACE = os.path.join(TMP, "surface")
os.makedirs(_SURFACE, exist_ok=True)

def _status_file(**kw):
    with open(os.path.join(_SURFACE, "Status.json"), "w") as fh:
        json.dump(kw, fh)

_POS = dict(Latitude=12.3456, Longitude=-45.6789, Heading=270,
            BodyName="Ega 1", PlanetRadius=2100000.0)
for _label, _flags, _flags2 in (
        ("a ship landed on the surface", _F_LANDED | _F_LATLONG | _F_SHIP, 0),
        ("driving the SRV", _F_LATLONG | _F_SRV, 0),
        ("on foot with Flags still set", _F_LATLONG,
         _F2_FOOT | _F2_PLANET | _F2_EXT),
        ("on foot with Flags emptied", 0, _F2_FOOT | _F2_PLANET | _F2_EXT),
        ("gliding in", _F_LATLONG | _F_SHIP, _F2_GLIDE),
        ("in the SRV before bit 21 catches up", _F_SRV, 0)):
    _w = JN.JournalWatcher(_SURFACE)
    _w.directory = _SURFACE
    _status_file(Flags=_flags, Flags2=_flags2, **_POS)
    _w.poll()
    check("position is seen while %s" % _label, _w.has_position,
          (_w.lat, _w.lon))
    check("and the body with it while %s" % _label, _w.body == "Ega 1", _w.body)

# The other half: leaving the surface must still clear it, or the map keeps
# drawing a commander standing somewhere they left three jumps ago.
_w = JN.JournalWatcher(_SURFACE); _w.directory = _SURFACE
_status_file(Flags=_F_LANDED | _F_LATLONG | _F_SHIP, Flags2=0, **_POS)
_w.poll()
check("landed, so there is a position to lose", _w.has_position)
_status_file(Flags=1 << 4, Flags2=0)          # supercruise, no coordinates
_w.poll()
check("supercruise clears the position", not _w.has_position,
      (_w.lat, _w.lon))
check("and clears the heading with it", _w.heading is None, _w.heading)

# Flags2 is read, not ignored.
_w = JN.JournalWatcher(_SURFACE); _w.directory = _SURFACE
_status_file(Flags=0, Flags2=_F2_FOOT | _F2_PLANET, **_POS); _w.poll()
check("on foot is known to the reader", _w.on_foot)
_status_file(Flags=_F_LATLONG | _F_SRV, Flags2=0, **_POS); _w.poll()
check("and cleared again once back in the SRV", not _w.on_foot and _w.in_srv)

# A coordinate that is not a number must not become one.
_w = JN.JournalWatcher(_SURFACE); _w.directory = _SURFACE
_status_file(Flags=_F_LATLONG, Flags2=0, Latitude="north", Longitude=None,
             BodyName="Ega 1")
_w.poll()
check("junk coordinates are refused, not coerced", not _w.has_position,
      (_w.lat, _w.lon))

print("== a folder Windows will not let us read says so ==")
# A tester's Saved Games folder had been hidden and locked down, and the app
# simply looked like the game was not running. Root ignores file permissions
# here, so the refusal is simulated where Windows would raise it.
import builtins as _bi
_w = JN.JournalWatcher(_SURFACE); _w.directory = _SURFACE
_status_file(Flags=_F_LATLONG | _F_SRV, Flags2=0, **_POS)
_real_open, _real_listdir = _bi.open, os.listdir
def _refuse_open(path, *a, **k):
    if str(path).endswith("Status.json"):
        raise PermissionError(13, "Access is denied", path)
    return _real_open(path, *a, **k)
def _refuse_listdir(path):
    raise PermissionError(13, "Access is denied", path)
try:
    _bi.open, os.listdir = _refuse_open, _refuse_listdir
    _w.poll()
    _said_where = _w.where
    _said_diag = _w.diagnosis()
finally:
    _bi.open, os.listdir = _real_open, _real_listdir
check("it says it cannot read the folder, not that the game is off",
      "Cannot read" in _said_where and "not running" not in _said_where, _said_where)
check("and says what to do about it", "Hidden" in _said_where and "Settings" in _said_where)
check("the test line names it too", "NO ACCESS" in _said_diag, _said_diag)
_w.poll()
check("once it can read again, the complaint goes away",
      _w.problem == "" and _w.has_position, (_w.problem, _w.has_position))

print("== the reader can say what it can and cannot see ==")
_w = JN.JournalWatcher(_SURFACE); _w.directory = None
check("no folder is reported as no folder", "NOT FOUND" in _w.diagnosis())
_w.directory = os.path.join(TMP, "nothing-here")
os.makedirs(_w.directory, exist_ok=True)
check("a folder without Status.json says so",
      "NOT IN THAT FOLDER" in _w.diagnosis())
_w.directory = _SURFACE
_status_file(Flags=0, Flags2=_F2_FOOT | _F2_PLANET, **_POS)
_said = _w.diagnosis()
check("on foot is named in the diagnosis", "on foot" in _said, _said)
check("and the position is quoted back", "12.3456" in _said, _said)
check("and the flags, because that is what a report needs",
      "Flags2: %d" % (_F2_FOOT | _F2_PLANET) in _said, _said)
_status_file(Flags=1 << 4, Flags2=0)
check("no position is stated plainly, not left blank",
      "not writing one" in _w.diagnosis(), _w.diagnosis())

print("== UPDATE writes the Amount onto the deposit you are standing on ==")
# Asked for directly: a button that updates a deposit as it is worked, rather
# than marking it a second time. The Amount is what goes down; Density is
# the deposit's own and does not.
_UD = os.path.join(TMP, "update-deposit"); os.makedirs(_UD, exist_ok=True)
_UJ = os.path.join(_UD, "journal"); os.makedirs(_UJ, exist_ok=True)
with open(os.path.join(_UJ, "Journal.2026-09-23T100000.01.log"), "w") as _fh:
    for _e in ({"timestamp": "2026-09-23T10:00:00Z", "event": "Fileheader", "part": 1},
               {"timestamp": "2026-09-23T10:00:01Z", "event": "Commander", "Name": "Jameson"},
               {"timestamp": "2026-09-23T10:00:02Z", "event": "Location",
                "StarSystem": "HR 7280", "Body": "HR 7280 A 3", "BodyType": "Planet"}):
        _fh.write(json.dumps(_e) + "\n")
def _ustatus(lat, lon):
    open(os.path.join(_UJ, "Status.json"), "w").write(json.dumps(
        {"timestamp": "2026-09-23T10:00:05Z", "event": "Status",
         "Flags": (1 << 21) | (1 << 26), "Latitude": lat, "Longitude": lon,
         "Heading": 10, "BodyName": "HR 7280 A 3", "PlanetRadius": R}))
_ustatus(37.2, -44.6)
up = A.EDSMT.__new__(A.EDSMT)
up.settings = dict(A.DEFAULT_SETTINGS)
up.store = SV.Survey(os.path.join(_UD, "data"))
up.watcher = JN.JournalWatcher(_UJ)
up.selected = None
up._known_body = None
up.game = up.watcher.poll()
up.location_box = _ctkstub.ctk.CTkComboBox(None, values=["1"]); up.location_box.set("3")
up.fields = {k: _ctkstub.ctk.CTkComboBox(None, values=[]) for k in
             ("commodity", "rigs", "density", "amount")}
for _b in up.fields.values(): _b.set("")
said = []
up.say = lambda text, colour=None: said.append(text)
shared = []
for _name in ("refresh_locations", "refresh_deposits", "refresh_commodities",
              "redraw", "on_pick"):
    setattr(up, _name, lambda *a, **k: None)
up.share = lambda record: shared.append(dict(record))

up.fields["commodity"].set("Ruby"); up.fields["rigs"].set("3")
up.fields["amount"].set("High"); up.fields["density"].set("Low")
up.mark_deposit()
check("a Ruby deposit is marked to start with",
      len(up.store.at("HR 7280", "HR 7280 A 3")) == 1)

# Twelve metres away, the Amount has dropped.
_ustatus(37.2 + 12.0 / R * 57.29578, -44.6)
up.game = up.watcher.poll()
up.fields["amount"].set("Low"); up.fields["density"].set(""); up.fields["rigs"].set("")
shared.clear()
up.update_deposit_here()
_rows = up.store.at("HR 7280", "HR 7280 A 3")
check("UPDATE changed the one that was there - no second copy", len(_rows) == 1, len(_rows))
check("its Amount is now Low", _rows[0]["amount"] == "Low", _rows[0]["amount"])
check("its Density is untouched by a blank box", _rows[0]["density"] == "Low",
      _rows[0]["density"])
check("and so are its rigs", _rows[0]["rigs"] == "3", _rows[0]["rigs"])
check("the notes keep a dated line saying what changed",
      "Updated (Amount Low)" in _rows[0]["notes"], _rows[0]["notes"])
check("the update is shared, like any correction",
      shared and shared[-1]["amount"] == "Low", shared)
check("and it says which deposit and how far", said and "Ruby" in said[-1]
      and "12 m" in said[-1], said[-1:])

said.clear()
up.update_deposit_here()
check("pressing it again with nothing new says so, and changes nothing",
      said and "already says" in said[-1]
      and up.store.at("HR 7280", "HR 7280 A 3")[0]["notes"].count("Updated") == 1,
      said[-1:])

# MARK on top of it asks first.
said.clear()
up.fields["amount"].set("Medium"); up.fields["density"].set("Low")
up.fields["rigs"].set("3")
up.clear_deposit_boxes = lambda: None
up.mark_deposit()
check("MARK on a deposit already marked asks rather than duplicating",
      len(up.store.at("HR 7280", "HR 7280 A 3")) == 1
      and said and "UPDATE" in said[-1], said[-1:])
up.mark_deposit()
check("and a second press means a genuinely separate deposit",
      len(up.store.at("HR 7280", "HR 7280 A 3")) == 2)

# Nowhere near anything.
_ustatus(37.3, -44.6)
up.game = up.watcher.poll()
said.clear()
up.update_deposit_here()
check("UPDATE with nothing close says so and points at MARK",
      said and "no deposit of yours" in said[-1].lower(), said[-1:])

print("== other commanders' finds are on the map, not only under Find ==")
# Reported three times: "the app is not showing any other sites", and other
# people "not able to see the data on the map if someone else has mapped it
# on the compass or radar". The map and every overlay box drew only the
# commander's own finds.
asks = []
class _Reader:
    can_read = True
    def body_deposits(self, system, body):
        asks.append((system, body)); return True
up.community = _Reader()
up.settings["show_shared_finds"] = True
_ustatus(37.2, -44.6)
up.game = up.watcher.poll()
up.shared, up._shared_asked = {}, {}
check("arriving on a body asks for its shared finds", up.want_shared("HR 7280", "HR 7280 A 3"))
check("and does not ask again while that is in flight",
      not up.want_shared("HR 7280", "HR 7280 A 3") and len(asks) == 1, asks)
mine = up.store.at("HR 7280", "HR 7280 A 3")[0]
answer = {"system": "HR 7280", "body": "HR 7280 A 3", "deposits": [
    # the commander's own Ruby, back from the server: must not draw twice
    {"id": 1, "system": "HR 7280", "planet": "HR 7280 A 3", "spot": "3",
     "type": "Ruby", "rigs": 3, "lat": float(mine["lat"]) + 0.0001,
     "lon": float(mine["lon"]), "uploader": "CMDR Jameson"},
    # somebody else's Iridium 600 m away
    {"id": 2, "system": "HR 7280", "planet": "HR 7280 A 3", "spot": "3",
     "type": "Iridium", "rigs": 2, "lat": 37.2 + 600.0 / R * 57.29578,
     "lon": -44.6, "uploader": "CMDR Somebody Else", "status": "verified"},
    # and one they reported stripped
    {"id": 3, "system": "HR 7280", "planet": "HR 7280 A 3", "spot": "4",
     "type": "Platinum", "rigs": 1, "lat": 37.19, "lon": -44.6,
     "uploader": "", "worked_out": True}]}
up.take_shared(True, json.dumps(answer))
_rows = up.store.near("HR 7280", "HR 7280 A 3", 37.2, -44.6, R)
_theirs = up.shared_near("HR 7280", "HR 7280 A 3", (37.2, -44.6), R, _rows)
_names = sorted(r["deposit"]["commodity"] for r in _theirs)
check("somebody else's finds come through", "Iridium" in _names, _names)
check("your own find coming back from the server is not drawn twice",
      "Ruby" not in _names, _names)
check("a find reported stripped comes through as worked out, not hidden",
      any(r["deposit"]["commodity"] == "Platinum"
          and r["deposit"]["amount"] == "Depleted" for r in _theirs), _theirs)
check("each carries who found it",
      any(r["deposit"]["cmdr"] == "CMDR Somebody Else" for r in _theirs))
check("and is marked as not yours", all(r["deposit"]["shared"] for r in _theirs))
check("the distance to it is worked out like your own",
      any(abs(r["range_m"] - 600) < 5 for r in _theirs if r["deposit"]["commodity"] == "Iridium"),
      [(r["deposit"]["commodity"], round(r["range_m"])) for r in _theirs])
said.clear()
up.edit_deposit(next(r["deposit"] for r in _theirs if r["deposit"]["commodity"] == "Iridium"))
check("a shared find cannot be opened for editing as if it were yours",
      said and "shared by CMDR Somebody Else" in said[-1], said[-1:])
up.settings["show_shared_finds"] = False
check("with the switch off, none of them are drawn",
      up.shared_near("HR 7280", "HR 7280 A 3", (37.2, -44.6), R, _rows) == [])
up.settings["show_shared_finds"] = True
up.shared[("hr 7280", "hr 7280 a 3")]["at"] -= A.SHARED_REFRESH_S + 1
check("they are asked for again once they are stale",
      up.want_shared("HR 7280", "HR 7280 A 3") and len(asks) == 2, asks)
_redraw_src = open(os.path.join(os.path.dirname(HERE), "edsmt.py"),
                      encoding="utf-8").read()
check("the map and the overlay are both handed the merged list",
      "rows = rows + self.shared_near(" in _redraw_src
      and _redraw_src.index("rows = rows + self.shared_near(")
          < _redraw_src.index("self.plan.show(rows, heading=heading, caption=caption,"))

print("== the survey area: know when the whole of it has been swept ==")
# Asked for: a boundary, "so people know they have scanned the whole area".
import coverage as CV
up.survey_book = CV.CoverageBook(os.path.join(_UD, "survey"))
up.cmap, up._cmap_saved = None, 0.0
said.clear()
g = up.game
g.lat, g.lon, g.in_srv = 37.2, -44.6, True
_deg = 57.29577951308232 / R            # degrees per metre of latitude
# Pressed out of order - at the edge first - the point is kept, not refused,
# and becomes the border the moment there is a centre to measure it from.
g.lat = 37.2 + 5000 * _deg
up.set_survey_border()
check("BORDER before CENTRE keeps the point and says what to do next",
      said and "border point kept" in said[-1].lower() and "Alt+1" in said[-1],
      said[-1:])
check("and sets no border yet", up.cmap.border_m in (None, 0), up.cmap.border_m)
g.lat = 37.2
up.set_survey_centre()
check("CENTRE takes where you are standing",
      up.cmap.centre == (37.2, -44.6), up.cmap.centre)
check("and the border pressed first is measured from it",
      up.cmap.border_m and abs(up.cmap.border_m - 5000) < 5, up.cmap.border_m)
check("and it says so", said and "border you pressed first" in said[-1]
      and "5.00 km" in said[-1], said[-1:])
check("a kept border is used once, not again",
      up._border_after_centre(up.cmap) is None)
up._border_waiting = ("somewhere", "else", 37.3, -44.6)
check("a border kept on another body is not used on this one",
      up._border_after_centre(up.cmap) is None and up._border_waiting is not None)
up._border_waiting = None
g.lat = 37.2 + 6000 * _deg
up.set_survey_border()
check("BORDER is the distance driven out from the centre",
      abs(up.cmap.border_m - 6000) < 5, up.cmap.border_m)
check("and it says which circles to drive",
      said and "3.75 km" in said[-1] and "4.00 km" in said[-1], said[-1:])
_part = up.survey_summary()
check("half-way through it says how much is left and where",
      "Swept" in _part and "%" in _part, _part)
# Drive the centre and the circles it gave.
import math as _m
g.lat, g.lon = 37.2, -44.6
up.track_survey(g)
for ring in up.cmap.rings():
    for step in range(0, 360, 2):
        a = _m.radians(step)
        g.lat = 37.2 + ring * _m.cos(a) * _deg
        g.lon = -44.6 + ring * _m.sin(a) * _deg / _m.cos(_m.radians(37.2))
        up.track_survey(g)
_done = up.survey_summary()
check("driving the circles it gave covers the whole area",
      "100%" in _done and "nothing left" in _done, _done)
_view = up.survey_view("HR 7280", "HR 7280 A 3", (37.2, -44.6), R)
check("the map is handed the border, the circles and the percentage",
      _view and _view["border_m"] and _view["rings"] and _view["percent"] == 100,
      _view and {k: _view[k] for k in ("border_m", "rings", "percent")})
check("positions are handed over relative to the commander",
      _view and abs(_view["centre"][0]) < 1 and abs(_view["centre"][1]) < 1,
      _view and _view["centre"])
# Out of the SRV nothing is painted: the scanner is on the SRV.
g.in_srv = False
_before = len(up.cmap.points)
g.lat = 37.2 + 9000 * _deg
up.track_survey(g)
check("ground crossed on foot or in the ship is not counted as swept",
      len(up.cmap.points) == _before)
g.in_srv = True
# It survives a restart.
up.survey_book.save(up.cmap)
_again = CV.CoverageBook(os.path.join(_UD, "survey")).map_for(
    "HR 7280", "HR 7280 A 3", 37.2, -44.6, R)
check("the swept ground and the area come back after a restart",
      _again.border_m and abs(_again.border_m - 6000) < 5
      and _again.coverage()["percent"] == 100)
up.clear_survey()
check("CLEAR forgets the area but keeps the ground swept",
      up.cmap.centre is None and up.cmap.border_m is None and up.cmap.points)
check("the keys for centre and border are real keys",
      set(("centre", "border")) <= set(A.EDSMT.wanted_hotkeys(
          dict(A.DEFAULT_SETTINGS, hotkey_centre="F6", hotkey_border="F7"))))

print("== a staff commander's finds go up verified ==")
# Asked for: "Any that I find are to be automatically verified." The server
# already grants the badge to a named staff token; the app just never asked.
class _Staff:
    ready = True
    can_verify = True
    def __init__(self): self.calls = []
    def upload(self, cmdr, deposits): self.calls.append(("upload", deposits[0]["type"]))
    def verify(self, cmdr, system, planet, spot="1", verified=True):
        self.calls.append(("verify", system, planet, spot)); return True
_st = A.EDSMT.__new__(A.EDSMT)
_st.settings = dict(A.DEFAULT_SETTINGS)
_st.community = _Staff()
_st.watcher = up.watcher
_st.galactic_position = lambda: {}
_rec = dict(up.store.at("HR 7280", "HR 7280 A 3")[0])
A.EDSMT.share(_st, _rec)
check("the find is uploaded, then verified, in that order",
      [c[0] for c in _st.community.calls] == ["upload", "verify"], _st.community.calls)
check("verified at the site it was marked in",
      _st.community.calls[-1][1:] == ("HR 7280", "HR 7280 A 3", "3"), _st.community.calls)
_st.community = _Staff(); _st.community.can_verify = False
A.EDSMT.share(_st, _rec)
check("without a staff token it is only uploaded",
      [c[0] for c in _st.community.calls] == ["upload"], _st.community.calls)
_st.community = _Staff(); _st.settings["verify_my_finds"] = False
A.EDSMT.share(_st, _rec)
check("and the switch in Settings turns it off",
      [c[0] for c in _st.community.calls] == ["upload"], _st.community.calls)
_st.community = _Staff(); _st.settings["verify_my_finds"] = True
_st.settings["community_auto_share"] = False
A.EDSMT.share(_st, _rec)
check("nothing is verified that was not shared", _st.community.calls == [],
      _st.community.calls)

print("== an update can never wipe the settings again ==")
# The commander's settings.json came back as the factory defaults after an
# update: every overlay box, the theme, the Inara key. The loader answered
# ANY trouble reading the file by saving the defaults over it, and the saver
# truncated the file before writing it - so an app closed part way through a
# save left an empty file, and the next launch destroyed what was left.
_S = os.path.join(TMP, "settings-safety")
os.makedirs(_S, exist_ok=True)
_real_file = A.SETTINGS_FILE
A.SETTINGS_FILE = os.path.join(_S, "settings.json")
_mine = dict(A.DEFAULT_SETTINGS)
_mine.update({"overlay_enabled": True, "overlay_theme": "ice",
              "overlay_show_radar": True, "inara_api_key": "abc123",
              "overlay_layout": {"radar": {"x": 0.7, "y": 0.1,
                                           "w": 0.2, "h": 0.3}}})

def _reset_notice():
    del A.SETTINGS_NOTICE[:]
    A.SETTINGS_READ_ONLY["on"] = False

_reset_notice()
check("a save reports success", A.save_settings(_mine))
check("and what comes back is what went in",
      A.load_settings()["overlay_layout"] == _mine["overlay_layout"])
check("no temp file is left lying about",
      not os.path.exists(A.SETTINGS_FILE + ".tmp"))

# A second save puts the first one behind it.
_mine2 = dict(_mine, overlay_theme="phosphor")
A.save_settings(_mine2)
check("the file being replaced becomes the backup",
      json.load(open(A.settings_backup_path()))["overlay_theme"] == "ice")

for _label, _junk in (("an empty file - an app closed mid-save", b""),
                      ("half a file", b'{"overlay_theme": "pho'),
                      ("a list instead of settings", b"[1, 2, 3]")):
    _reset_notice()
    with open(A.SETTINGS_FILE, "wb") as _fh:
        _fh.write(_junk)
    _got = A.load_settings()
    check("%s: the last good settings come back" % _label,
          _got.get("overlay_theme") == "ice"
          and _got.get("inara_api_key") == "abc123", _got.get("overlay_theme"))
    _aside = [f for f in os.listdir(_S) if ".unreadable-" in f]
    check("%s: the bad file is kept, not destroyed" % _label, _aside, os.listdir(_S))
    check("%s: and the commander is told" % _label,
          A.SETTINGS_NOTICE and "last good copy" in A.SETTINGS_NOTICE[0],
          A.SETTINGS_NOTICE)
    for _f in _aside:
        os.remove(os.path.join(_S, _f))
    A.save_settings(_mine2)          # put a good file back for the next case

# The loader must never write. A bad file and NO backup is exactly the case
# that used to end with the defaults saved over the only copy there was.
_reset_notice()
os.remove(A.settings_backup_path())
with open(A.SETTINGS_FILE, "wb") as _fh:
    _fh.write(b'{"overlay_theme": "pho')
_before = os.listdir(_S)
_got = A.load_settings()
check("with no backup it starts from defaults for this session",
      _got["overlay_theme"] == A.DEFAULT_SETTINGS["overlay_theme"])
check("but the broken file is still there to recover by hand",
      any(".unreadable-" in f for f in os.listdir(_S)), os.listdir(_S))
check("and nothing was saved over anything",
      not os.path.exists(A.SETTINGS_FILE), os.listdir(_S))
check("the commander is told it started from defaults",
      any("defaults" in n for n in A.SETTINGS_NOTICE), A.SETTINGS_NOTICE)

# A byte-order mark is what Notepad on older Windows saves, and the old
# loader treated it as a corrupt file - which meant defaults over the top.
_reset_notice()
with open(A.SETTINGS_FILE, "wb") as _fh:
    _fh.write(b"\xef\xbb\xbf" + json.dumps(_mine).encode("utf-8"))
check("a byte-order mark is read, not treated as damage",
      A.load_settings()["overlay_theme"] == "ice" and not A.SETTINGS_NOTICE,
      A.SETTINGS_NOTICE)

# Something JSON cannot hold must fail the save, not half-write the file.
_reset_notice()
A.save_settings(_mine)
_weird = dict(_mine, overlay_layout={"x": {1, 2}})    # a set
A.save_settings(_weird)
check("an unserialisable value never leaves a half-written file",
      A._read_settings_file(A.SETTINGS_FILE)[0] is not None)

# A missing settings.json with a backup beside it is something having
# removed it, not a first run.
_reset_notice()
A.save_settings(_mine)
A.save_settings(_mine2)
os.remove(A.SETTINGS_FILE)
check("a missing file with a backup beside it is restored from the backup",
      A.load_settings()["overlay_theme"] == "ice", A.SETTINGS_NOTICE)
_reset_notice()
shutil.rmtree(_S); os.makedirs(_S)
check("a genuine first run says nothing at all",
      A.load_settings()["overlay_theme"] == A.DEFAULT_SETTINGS["overlay_theme"]
      and not A.SETTINGS_NOTICE, A.SETTINGS_NOTICE)

# The loader is not allowed to call the saver, ever.
import ast as _ast2, io
_load = next(n for n in _ast2.walk(_ast2.parse(io.open(os.path.join(
    os.path.dirname(HERE), "edsmt.py"), encoding="utf-8").read()))
    if isinstance(n, _ast2.FunctionDef) and n.name == "load_settings")
check("load_settings never writes the settings file",
      "save_settings" not in _ast2.dump(_load)
      and "_atomic_write" not in _ast2.dump(_load))

# A dragged overlay box asks the app to save by name. It asked for years and
# nothing answered, so positions only survived a clean close.
check("the app answers the overlay's save request",
      callable(getattr(A.EDSMT, "save_settings", None)))
_ovsrc = io.open(os.path.join(os.path.dirname(HERE), "overlay.py"),
                 encoding="utf-8").read()
check("and the overlay really does ask for it by that name",
      'getattr(self.app, "save_settings"' in _ovsrc)

print("== only one copy runs, and the installer waits for it ==")
_appsrc = io.open(os.path.join(os.path.dirname(HERE), "edsmt.py"),
                  encoding="utf-8").read()
_iss = io.open(os.path.join(os.path.dirname(HERE), "build", "installer.iss"),
               encoding="utf-8").read()
check("the app holds a named mutex while it runs", "CreateMutexW" in _appsrc)
check("the installer waits on that same name",
      "AppMutex=%s" % A.INSTANCE_NAME in _iss, A.INSTANCE_NAME)
check("a second copy is turned away before any window is built",
      _appsrc.index("claim_single_instance()", _appsrc.index('if __name__'))
      < _appsrc.index("EDSMT()", _appsrc.index('if __name__')))
_reset_notice()
A.SETTINGS_FILE = _real_file

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fails else 0)
