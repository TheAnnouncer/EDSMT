"""The guide over the game, rigs that say what they are on, and the signal
the game has targeted - without a display.

Asked for in these words: "we scan with the DSS, select signal source
number, land on planet, launch rhino, then drive to the centre and Left
Alt+F1 to mark centre, ping along the way, drive to the edge of the border
and Left Alt+F2, find the deposit, fill the information, Left Alt+F3, place
the rigs and each time Left Alt+F5 (this marks on radar and compass what
type it is), then go round and repeat." This holds the app to that order.
The keys have since moved to the number row - "Lets do alt 1 alt2 etc as
the fbuttons can get confusion" - so the same steps are Alt+1 to Alt+4.
"""
import os, sys, math, json, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "stubs"))
import _ctkstub  # noqa
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="edsmt-guide-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
import edsmt as A, survey as SV, overlay as OV, journal as JN  # noqa

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)


KEYS = {a: A.key_text(A.DEFAULT_SETTINGS["hotkey_" + a])
        for a in ("location", "border", "deposit", "rigs", "allup")}

print("== the guide follows the work, step by step ==")
# And now from the very start: "the guide should say jump honk and then click
# where to land", and the Rhino step only once out of glide and under 30 m.
walk = [({}, "JUMP IN AND HONK"),
        ({"honked": True}, "CLICK WHERE TO LAND"),
        ({"honked": True, "chosen": True}, "MAP THE BODY"),
        ({"scanned": True}, "PICK A SIGNAL"),
        ({"scanned": True, "signal": True}, "LAND AT THE SIGNAL"),
        ({"landed": True}, "DEPLOY THE RHINO"),
        ({"landed": True, "rhino": True}, "LOG THE CENTRE  Alt+1"),
        ({"rhino": True, "centre": True}, "SET THE BORDER  Alt+2"),
        ({"centre": True, "border": True}, "MARK A DEPOSIT  Alt+3"),
        ({"border": True, "deposit": True}, "PLACE RIGS  Alt+4"),
        ({"deposit": True, "rigs": True, "marked": 2, "signal_no": "5"},
         "NEXT DEPOSIT")]
for number, (facts, title) in enumerate(walk, start=1):
    card = A.guide_step(facts, KEYS)
    check("step %d is %s" % (number, title),
          card["title"] == title and card["step"] == number, card)
card = A.guide_step({"deposit": True, "rigs": True, "marked": 2,
                     "signal_no": "5"}, KEYS)
check("the last step repeats: the next deposit, with its keys",
      "2 marked at signal 5" in card["detail"] and "Alt+3" in card["detail"]
      and "Alt+4" in card["detail"] and "Alt+5" in card["detail"], card)
card = A.guide_step({"centre": True, "deposit": True}, KEYS)
check("a skipped border does not hold the guide back",
      card["title"].startswith("PLACE RIGS"), card)
card = A.guide_step({"rhino": True}, {"location": ""})
check("with a key cleared it names the button instead",
      "LOG SIGNAL" in card["detail"], card)
check("each step says what comes after it",
      A.guide_step({}, KEYS)["next"] == "CLICK WHERE TO LAND")
check("eleven steps, and the count is on the card",
      A.guide_step({}, KEYS)["total"] == len(A.GUIDE_STEPS) == 11)

card = A.guide_step({"scanned": True, "signal": True, "gliding": True}, KEYS)
check("gliding in, it does not say DEPLOY - it says GLIDING and why",
      card["title"] == "GLIDING" and "30 m" in card["detail"]
      and "DEPLOY" not in card["title"], card)
card = A.guide_step({"scanned": True, "signal": True, "altitude": 212.0}, KEYS)
check("out of glide but high, it says how high and how low to get",
      "212 m" in card["detail"] and "30 m" in card["detail"], card)
card = A.guide_step({"centre": True, "rhino": True, "from_centre_m": 4210.0},
                    KEYS)
check("setting the border it says to hold the scanner, and how far out you are",
      "Hold the mineral scanner" in card["detail"]
      and "keep it held while you map" in card["detail"]
      and "4.21 km from the centre" in card["detail"], card)
check("and logging the centre needs no commodities",
      "No commodities needed" in A.guide_step({"rhino": True}, KEYS)["detail"])

print("== the guide box ==")


class _Canvas:
    def __init__(self):
        self.calls = []
    def __getattr__(self, name):
        def record(*a, **k):
            self.calls.append((name, a, k))
            return len(self.calls)
        return record


over = OV.Overlay(app=None, tk_module=None, settings={"overlay_show_guide": True})
check("the guide rides along with the default box, not instead of it",
      over.active() == [over.mode(), OV.GUIDE], over.active())
over = OV.Overlay(app=None, tk_module=None,
                  settings={"overlay_show_radar": True, "overlay_show_guide": True})
check("and with the boxes chosen", over.active() == [OV.RADAR, OV.GUIDE], over.active())
over = OV.Overlay(app=None, tk_module=None, settings={})
check("off, it is not opened", OV.GUIDE not in over.active())
check("it has a place, a size floor, a title and a line in Settings",
      OV.GUIDE in OV.DEFAULT_LAYOUT and OV.GUIDE in OV.MIN_PANEL
      and OV.GUIDE in OV.PANEL_TITLE and OV.GUIDE in OV.PANEL_WHAT
      and '"overlay_show_guide"' in open(A.__file__, encoding="utf-8").read())
over.canvas = _Canvas()
over._guide = A.guide_step({"rhino": True}, KEYS)
over.draw_guide(300, 170)
texts = [str(k.get("text", "")) for n, a, k in over.canvas.calls if n == "create_text"]
check("it draws the step, the title and what to do",
      "EDSMT GUIDE  7/11" in texts and "LOG THE CENTRE  Alt+1" in texts
      and any("press Alt+1" in t for t in texts), texts)
pips = [k for n, a, k in over.canvas.calls
        if n == "create_rectangle" and "pip" in (k.get("tags") or ())]
check("and how far along, as eleven pips", len(pips) == 11, len(pips))
check("then what comes next, when there is room",
      any(t.startswith("then: SET THE BORDER") for t in texts), texts)

print("== the app knows what has been done ==")
R = 1_800_000.0


class State:
    def __init__(self, **kw):
        self.lat, self.lon, self.heading = 12.5, -45.5, 0.0
        self.radius_m = R
        self.has_position = True
        self.landed = False
        self.in_srv = True
        self.target_signal = ""
        self.detected_type = None
        self.__dict__.update(kw)
    def mining_signals(self):
        return 21


def app_for(store_dir):
    app = A.EDSMT.__new__(A.EDSMT)
    app.said = []
    app.say = lambda t, c=None: app.said.append(t)
    app.settings = dict(A.DEFAULT_SETTINGS)
    app.here = lambda: ("Prae Drye JG-C c1-0", "Prae Drye JG-C c1-0 A 3 b")
    app.signal = lambda: "5"
    app.store = SV.Survey(store_dir)
    app.redraw = lambda: None
    app.flash = lambda *a, **k: True
    app.refresh_rigs_note = lambda: None
    app.rigs_at, app._rigs_warned = None, False
    app._survey_map = lambda: None
    app.game = State()
    return app


app = app_for(os.path.join(TMP, "store"))
facts = app.guide_facts()
check("DSS signals, the Rhino, nothing logged yet",
      facts["scanned"] and facts["rhino"] and not facts["centre"]
      and not facts["deposit"], facts)
check("so the guide says log the centre",
      app.guide_card()["title"] == "LOG THE CENTRE  Alt+1", app.guide_card())
SYS, BODY = app.here()
app.store.set_location(SYS, BODY, "5", lat=12.5, lon=-45.5, radius_m=R)
app.store.add_deposit(system=SYS, body=BODY, location="5", commodity="Rhodplumsite",
                      rigs="3", amount="High", density="Low",
                      lat="12.500100", lon="-45.500100")
check("logged and marked, the guide is on the rigs",
      app.guide_card()["title"] == "PLACE RIGS  Alt+4", app.guide_card())
app.settings["overlay_show_guide"] = False
check("switched off, there is no card", app.guide_card() is None)
app.settings["overlay_show_guide"] = True

print("== each rig says what it is on ==")
app.drop_rigs()
rig = app.rigs_at["rigs"][0]
check("a rig put down on a marked deposit is that deposit's commodity",
      rig.get("commodity") == "Rhodplumsite", rig)
check("and says so", "on Rhodplumsite" in app.said[-1], app.said[-1])
check("and the guide moves on to the next deposit",
      app.guide_card()["title"] == "NEXT DEPOSIT", app.guide_card())
app.rigs_up()
check("rigs back up does not send the guide back to placing them",
      app.guide_card()["title"] == "NEXT DEPOSIT", app.guide_card())
away = app_for(os.path.join(TMP, "store2"))
away.fields = {"commodity": type("Box", (), {"get": lambda self: "Monazite"})()}
away.drop_rigs()
check("with no deposit marked near, the Commodity box names it",
      away.rigs_at["rigs"][0].get("commodity") == "Monazite", away.rigs_at)
view = app_for(os.path.join(TMP, "store"))
view.drop_rigs()
marks = view.watch_rigs(view.game)
check("and the type travels with the rig to the map and the overlay",
      marks and marks["rigs"][0].get("commodity") == "Rhodplumsite", marks)
tape = OV.rig_tape_marks(marks, 0.0, 600)
check("the compass tape carries it", tape and tape[0]["commodity"] == "Rhodplumsite", tape)
scope = OV.Overlay(app=None, tk_module=None, settings={})
scope.canvas = _Canvas()
scope._rigs = marks


class _View:
    width = height = 300
    def to_canvas(self, east, north):
        return 150 + east / 10.0, 150 - north / 10.0


scope._rig_marks(_View(), (0.0, 0.0))
scope._scope_labels({"items": []})
drawn = [k.get("text") for n, a, k in scope.canvas.calls if n == "create_text"]
check("the scope writes the type beside the rig", "Rhodplum" in drawn, drawn)

print("== the signal the game has targeted ==")
reader = JN.JournalWatcher(TMP)
reader._read_destination({"System": 1, "Body": 24,
                          "Name": "$SAA_Unknown_Signal:#index=15;"})
check("a targeted mining location's number is read", reader.target_signal == "15",
      reader.target_signal)
reader._read_destination({"System": 1, "Body": 24, "Name": "Some Station"})
check("a destination without one changes nothing", reader.target_signal == "15")
reader._read_destination(None)
check("and no destination at all is not an error", reader.target_signal == "15")
_tele = open(A.__file__, encoding="utf-8").read().split(
    "    def update_telemetry(self, state):")[1].split("\n    def ")[0]
check("every poll with the game running follows the targeted signal",
      "self.follow_target(state)" in _tele)
picked = app_for(os.path.join(TMP, "store3"))
chosen = []
picked.choose_signal = lambda n: chosen.append(n)
picked.follow_target(State(target_signal="15"))
check("the app picks the targeted signal", chosen == ["15"], chosen)
picked.follow_target(State(target_signal="15"))
check("once - a number picked by hand afterwards is not overridden", chosen == ["15"])
picked.follow_target(State(target_signal="16"))
check("until the game targets another", chosen == ["15", "16"], chosen)

print("== driving into a logged signal makes it the one being worked ==")
# The scope in his screenshot read MAP RADIUS 50 km: the box still named the
# signal before, and a deposit marked there would have been filed under it.
import math as _mm
check("every poll with the game running follows the signal you are in",
      "self.follow_arrival(state)" in _tele)
arrive = app_for(os.path.join(TMP, "store-arrive"))
_sys, _body = arrive.here()
_ONE, _FIVE = (12.5, -45.5), (12.5, -45.5 + _mm.degrees(40000 / R))
arrive.store.set_location(_sys, _body, "1", lat=_ONE[0], lon=_ONE[1], radius_m=R)
arrive.store.set_location(_sys, _body, "5", lat=_FIVE[0], lon=_FIVE[1], radius_m=R)
_box = ["1"]
arrive.signal = lambda: _box[0]
arrive.choose_signal = lambda n: (_box.__setitem__(0, n), chosen_here.append(n))
chosen_here = []
arrive.follow_arrival(State(lat=_ONE[0], lon=_ONE[1]))
check("at signal 1 with the box on 1, nothing changes", chosen_here == [], chosen_here)
_near_five = (12.5, -45.5 + _mm.degrees(38500 / R))     # 1.5 km short of it
arrive.follow_arrival(State(lat=_near_five[0], lon=_near_five[1]))
check("drive 38 km to signal 5 and it is picked, once",
      chosen_here == ["5"] and _box[0] == "5", chosen_here)
check("and the commander is told", any("signal 5" in t for t in arrive.said),
      arrive.said[-1:])
_box[0] = "3"                                  # picked by hand while at 5
arrive.follow_arrival(State(lat=_FIVE[0], lon=_FIVE[1]))
check("a number picked by hand while you stand there is left alone",
      chosen_here == ["5"] and _box[0] == "3", chosen_here)
_between = (12.5, -45.5 + _mm.degrees(20000 / R))
arrive.follow_arrival(State(lat=_between[0], lon=_between[1]))
arrive.follow_arrival(State(lat=_ONE[0], lon=_ONE[1]))
check("drive back into signal 1 and it is picked again",
      chosen_here == ["5", "1"], chosen_here)
arrive.follow_arrival(State(lat=_ONE[0], lon=_ONE[1], has_position=False))
check("no surface position, no guess", chosen_here == ["5", "1"])
# Two logged signals close together: the one in the box stays while you are
# in it, so its finds are not split between two numbers.
twin = app_for(os.path.join(TMP, "store-twin"))
_tsys, _tbody = twin.here()
_A, _B = (12.5, -45.5), (12.5, -45.5 + _mm.degrees(3000 / R))
twin.store.set_location(_tsys, _tbody, "8", lat=_A[0], lon=_A[1], radius_m=R)
twin.store.set_location(_tsys, _tbody, "9", lat=_B[0], lon=_B[1], radius_m=R)
_tbox, _tpicked = ["8"], []
twin.signal = lambda: _tbox[0]
twin.choose_signal = lambda n: (_tbox.__setitem__(0, n), _tpicked.append(n))
_closer_b = (12.5, -45.5 + _mm.degrees(2200 / R))
twin.follow_arrival(State(lat=_closer_b[0], lon=_closer_b[1]))
check("nearer 9 but still inside 8, with 8 in the box, 8 stays",
      _tpicked == [] and _tbox[0] == "8", _tpicked)
check("the nearest logged signal is found by the survey module",
      SV.nearest_signal(twin.store.locations_on(_tsys, _tbody), _closer_b[0],
                        _closer_b[1], R, A.PV.SIGNAL_AT_M)["location"] == "9")
check("and one logged with no position is passed over, not guessed at",
      SV.nearest_signal([{"location": "4", "lat": "", "lon": ""}], 0, 0, R,
                        5000) is None)

print("== tonnes refined, put against the deposit they came off ==")
# From the real journals: in the SRV one MiningRefined is one tonne into the
# SRV's hold (47 refined, the SRV's Cargo count 46 a second later; 67 and
# 67; 3 and 3), by-products each under their own name.
import math as _m
GAME = os.path.join(TMP, "refine"); os.makedirs(GAME)
SYS, BODY = "HR 7280", "HR 7280 A 3"
HOME = (20.247482, 159.101089)


def east_of(lat, lon, metres):
    return lat, lon + _m.degrees(metres / (R * _m.cos(_m.radians(lat))))


with open(os.path.join(GAME, "Status.json"), "w") as fh:
    json.dump({"timestamp": "2026-09-22T22:50:00Z", "event": "Status",
               "Flags": (1 << 21) | (1 << 26), "Latitude": HOME[0],
               "Longitude": HOME[1], "Heading": 90, "BodyName": BODY,
               "PlanetRadius": R}, fh)
LOG = os.path.join(GAME, "Journal.2026-09-22T175815.01.log")
with open(LOG, "w") as fh:
    fh.write(json.dumps({"timestamp": "2026-09-22T22:43:42Z", "event": "LaunchSRV",
                         "SRVType": "mev_rhino", "PlayerControlled": True}) + "\n")
reader = JN.JournalWatcher(GAME)
reader.poll()
reader.drain_runs()
with open(LOG, "a") as fh:
    for kind in ("rhodplumsite", "rhodplumsite", "rhodplumsite", "iridium"):
        fh.write(json.dumps({"timestamp": "2026-09-22T22:51:00Z",
                             "event": "MiningRefined", "Type": "$%s_name;" % kind,
                             "Type_Localised": kind.title()}) + "\n")
reader.detected_type = None
reader.poll()
notes = [n for n in reader.drain_runs() if n.get("event") == "Refined"]
check("each MiningRefined reaches the books as a tonne, with where the SRV was",
      len(notes) == 4 and notes[0]["lat"] == HOME[0] and notes[0]["in_srv"],
      notes[:1])
check("named in English off the symbol",
      [n["commodity"] for n in notes] == ["Rhodplumsite"] * 3 + ["Iridium"], notes)
check("and a by-product never fills the Commodity box",
      reader.detected_type is None, reader.detected_type)

miner = app_for(os.path.join(TMP, "mined"))
miner.here = lambda: (SYS, BODY)
miner.store.add_deposit(system=SYS, body=BODY, location="1", commodity="Rhodplumsite",
                        rigs="4", amount="High", density="Low",
                        lat="%.6f" % east_of(*HOME, 90)[0],
                        lon="%.6f" % east_of(*HOME, 90)[1])
miner.store.add_deposit(system=SYS, body=BODY, location="1", commodity="Iridium",
                        rigs="2", amount="High", density="Low",
                        lat="%.6f" % east_of(*HOME, 40)[0],
                        lon="%.6f" % east_of(*HOME, 40)[1])
miner.store.add_deposit(system=SYS, body=BODY, location="1", commodity="Monazite",
                        rigs="2", amount="High", density="Low",
                        lat="%.6f" % east_of(*HOME, 5000)[0],
                        lon="%.6f" % east_of(*HOME, 5000)[1])
for note in notes:
    miner.credit_refined(note)
rows = {r["commodity"]: r for r in miner.store.at(SYS, BODY)}
check("the tonnes go to the deposit of that commodity, even past a nearer one",
      SV.unpack_counts(rows["Rhodplumsite"]["mined"]) == {"Rhodplumsite": 3},
      rows["Rhodplumsite"]["mined"])
check("and the by-product to its own deposit when one is marked close by",
      SV.unpack_counts(rows["Iridium"]["mined"]) == {"Iridium": 1},
      rows["Iridium"]["mined"])
check("a deposit five kilometres off gets none of it",
      rows["Monazite"]["mined"] == "", rows["Monazite"]["mined"])
lone = miner.credit_refined(dict(notes[0], lat=east_of(*HOME, 3000)[0],
                                 lon=east_of(*HOME, 3000)[1]))
check("a tonne with no marked deposit near is nobody's", lone is None)
check("nor is one refined from the ship", miner.credit_refined(
    dict(notes[0], in_srv=False)) is None)
check("nor one with no position", miner.credit_refined(dict(notes[0], lat=None)) is None)
check("they are held, not written a tonne at a time",
      miner._refined_dirty and not open(miner.store.deposits_path if hasattr(
          miner.store, "deposits_path") else os.path.join(TMP, "mined", "deposits.csv"),
          encoding="utf-8").read().count("Rhodplumsite:3"))
miner.save_refined(force=True)
again = SV.Survey(os.path.join(TMP, "mined"))
check("and written when the app saves them",
      {r["commodity"]: r["mined"] for r in again.at(SYS, BODY)}
      == {"Rhodplumsite": "Rhodplumsite:3", "Iridium": "Iridium:1", "Monazite": ""})

print("== the deposit you drive onto is the one picked ==")
dep_app = app_for(os.path.join(TMP, "store-ondep"))
_ds, _db = dep_app.here()
_HERE = (12.5, -45.5)
_near = (12.5, -45.5 + _mm.degrees(60 / R))       # 60 m east
_far = (12.5, -45.5 + _mm.degrees(900 / R))       # 900 m east
dep_app.store.add_deposit(system=_ds, body=_db, location="5", commodity="Haematite",
                          rigs="4", lat="%.6f" % _near[0], lon="%.6f" % _near[1])
dep_app.store.add_deposit(system=_ds, body=_db, location="5", commodity="Copper",
                          rigs="2", lat="%.6f" % _far[0], lon="%.6f" % _far[1])
_hae, _cop = dep_app.store.deposits
_picks = []
dep_app.selected = None
dep_app.pick_deposit = lambda row, guide=True: (_picks.append((row["commodity"], guide)),
                                                setattr(dep_app, "selected", row))
dep_app.game = State(lat=_HERE[0], lon=_HERE[1], in_srv=True)
dep_app.follow_deposit(dep_app.game)
check("in the SRV on a deposit you marked, it is picked - not as a place to go",
      _picks == [("Haematite", False)], _picks)
check("and the commander is told MINED OUT acts on it",
      any("MINED OUT" in t for t in dep_app.said), dep_app.said[-1:])
dep_app.follow_deposit(dep_app.game)
check("once - not again every poll", len(_picks) == 1, _picks)
dep_app.selected = _cop                           # picked by hand meanwhile
dep_app.follow_deposit(dep_app.game)
check("a deposit picked by hand while you stand there is left alone",
      len(_picks) == 1 and dep_app.selected is _cop)
dep_app.game = State(lat=_HERE[0], lon=_HERE[1], in_srv=False)
dep_app._on_deposit = None
dep_app.follow_deposit(dep_app.game)
check("on foot or in the ship, nothing is picked", len(_picks) == 1, _picks)
guide_app = app_for(os.path.join(TMP, "store-ondep"))
guide_app.store = dep_app.store
guide_app.here = dep_app.here
guide_app.pick_deposit = lambda row, guide=True: None
guide_app.guide_to(_cop)
check("a deposit picked by hand is the one the overlay guides to",
      guide_app._guide_to == str(_cop["id"]))
guide_app.game = State(lat=_far[0], lon=_far[1], in_srv=True)
guide_app.follow_deposit(guide_app.game)
check("and arriving at it ends the guiding", guide_app._guide_to is None,
      guide_app._guide_to)
_src = open(A.__file__, encoding="utf-8").read()
check("the map's click guides; the poll follows the deposit you are on",
      "on_select=self.picked_on_map" in _src and "self.follow_deposit(state)" in _tele)

print("== what a deposit gave, what it holds, what is left ==")
_row = {"commodity": "Haematite", "amount": "High",
        "mined": "Haematite:40;Water:3", "cycles": ""}
check("its own commodity is the number; by-products beside it, not added",
      A.tonnes_lines(_row) == ["mined here: 40t", "  by-products: Water 3t"],
      A.tonnes_lines(_row))
_closed = SV.close_cycle(_row, when="2026-09-20T10:00:00Z")
check("worked out, this time's own tonnes are filed as what it held",
      _closed == ("2026-09-20=40", ""), _closed)
check("and nothing is filed when nothing of its own was counted",
      SV.close_cycle({"commodity": "Haematite", "mined": "Water:3"}) is None)
_row2 = {"commodity": "Haematite", "amount": "Medium", "mined": "Haematite:12",
         "cycles": "2026-09-20=40;2026-10-01=52"}
check("worked out before, it says what it holds and about what is left",
      A.tonnes_lines(_row2) == ["mined this time: 12t",
                                "holds about 40-52t (worked out 2 times)",
                                "left: about 28-40t"], A.tonnes_lines(_row2))
check("marked Depleted, no 'left' line",
      "left" not in " ".join(A.tonnes_lines(dict(_row2, amount="Depleted"))))
check("a broken cycles field is skipped, not a crash",
      SV.cycle_tonnes({"cycles": "x=;=9;junk;2026=0"}) == [9])
mm = app_for(os.path.join(TMP, "store-mm"))
mm.store.add_deposit(system="S", body="B", location="1", commodity="Haematite",
                     amount="High", mined="Haematite:40;Water:3", lat="1", lon="1")
mm.selected = mm.store.deposits[0]
_edits = []
mm.deposit_edited = lambda deposit_id, changes: _edits.append(changes)
mm.mark_mined()
check("MINED OUT files the cycle and starts the count again",
      _edits and _edits[0]["amount"] == "Depleted" and _edits[0]["mined"] == ""
      and _edits[0]["cycles"].endswith("=40")
      and "Mined out after 40t" in _edits[0]["notes"], _edits)

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
