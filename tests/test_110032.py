"""What 1.10032 adds, each piece held down so it stays built.

    python tests/test_110032.py
"""
import os, sys, math, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "stubs"))
import _ctkstub  # noqa
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="edsmt-110032-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
import edsmt as A, survey as SV, overlay as OV  # noqa
import rigplan as RP  # noqa

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)


SRC = open(A.__file__, encoding="utf-8").read()
OVSRC = open(OV.__file__, encoding="utf-8").read()

print("== est. held and left, from deposits like it that were worked out ==")
mine = [
    {"commodity": "Ruby", "rigs": "3", "density": "High", "cycles": "2026-09-20=48"},
    {"commodity": "Gold", "rigs": "3", "density": "High", "cycles": "2026-09-21=52;2026-09-25=44"},
    {"commodity": "Ruby", "rigs": "3", "density": "Low", "cycles": "2026-09-22=20"},
    {"commodity": "Ruby", "rigs": "4", "density": "High", "cycles": "2026-09-23=70"},
]
check("three cycles with 3 rigs and High density: 44-52 t",
      SV.estimate_tonnes(mine, "3", "high") == (44, 52, 3),
      SV.estimate_tonnes(mine, "3", "high"))
check("nothing like it is no estimate, not a guess",
      SV.estimate_tonnes(mine, "5", "High") is None
      and SV.estimate_tonnes(mine, "", "High") is None
      and SV.estimate_tonnes(mine, "3", "") is None)
many = [{"rigs": 2, "density": "Medium", "cycles": "d=%d" % t}
        for t in (10, 30, 31, 32, 33, 34, 90)]
check("with five or more, one odd run does not stretch the range",
      SV.estimate_tonnes(many, 2, "Medium")[:2] == (30, 34),
      SV.estimate_tonnes(many, 2, "Medium"))
fresh = {"commodity": "Ruby", "rigs": "3", "density": "High", "amount": "High",
         "mined": "Ruby:10"}
lines = A.tonnes_lines(fresh, mine + [fresh])
check("a deposit never worked out shows the estimate, and says what it rests on",
      any(l.startswith("est. holds 44-52t - from 3 worked out with 3 rigs, High")
          for l in lines), lines)
check("and what is left of it after what you have taken",
      "est. left: 34-42t" in lines, lines)
check("a worked-out deposit's own measure still wins over the estimate",
      not any("est." in l for l in A.tonnes_lines(dict(fresh, cycles="d=60"), mine)))
check("a depleted one gets no estimate",
      not any("est." in l for l in A.tonnes_lines(dict(fresh, amount="Depleted"), mine)))
check("the details window passes the commander's deposits in",
      "tonnes_lines(deposit, attr(self.store, \"deposits\", None))" in SRC)

print("== a rig counts on a pin within half the spacing ==")
check("78 m spacing: a rig 39 m off still counts",
      A.EDSMT.pin_reach({"spacing": 78.0}) == 39.0)
check("never tighter than 20 m, whatever the spacing",
      A.EDSMT.pin_reach({"spacing": 20.0}) == A.PLAN_PIN_DONE_M == 20.0
      and A.EDSMT.pin_reach(None) == 20.0)
R = 2_000_000.0
HOME = (10.0, 20.0)


class _State:
    def __init__(self, lat, lon):
        self.lat, self.lon, self.heading = lat, lon, 0.0
        self.radius_m, self.has_position, self.in_srv = R, True, True


papp = A.EDSMT.__new__(A.EDSMT)
papp.here = lambda: ("Ega", "Ega 1")
papp.game = _State(*HOME)
pin = RP.from_local(HOME, 0.0, 100.0, R)
papp.rig_plan = {"system": "ega", "body": "ega 1", "spacing": 78.0,
                 "pins": [{"n": 1, "lat": pin[0], "lon": pin[1]},
                          {"n": 2, "lat": RP.from_local(HOME, 78.0, 100.0, R)[0],
                           "lon": RP.from_local(HOME, 78.0, 100.0, R)[1]}],
                 "outline": []}
near = RP.from_local(HOME, 30.0, 100.0, R)
papp.rigs_at = {"system": "Ega", "body": "Ega 1",
                "rigs": [{"n": 1, "lat": near[0], "lon": near[1]}]}
marks = papp.plan_marks()
check("a rig dropped 30 m from P1 ticks P1 off, and P2 is next",
      marks and marks["pins"][0]["done"] and not marks["pins"][1]["done"]
      and marks["next"] == 2, marks and [(p["n"], p["done"]) for p in marks["pins"]])
check("and its message names the pin", papp.plan_pin_at(*near) == 1)

print("== the next pin is on the compass tape ==")
check("the tape draws the next pin, pinned to the end with an arrow when behind",
      '"pintape"' in OVSRC and 'label = "P%d %s" % (pin["n"], format_range(pin["range_m"]))'
      in OVSRC)

print("== shared finds come in through a box, not straight off the clipboard ==")
_paste = SRC.split("    def paste_shared(self):")[1].split("\n    def ")[0]
check("Import reads the box, never the clipboard",
      "clipboard_get" not in _paste and 'box.get("1.0", "end")' in _paste)
check("an empty box says what to do", "into the box first" in _paste)
check("Enter imports and Shift+Enter is a new line",
      'self.paste_box.bind("<Return>", self._paste_enter)' in SRC
      and "def _paste_enter" in SRC)
check("the message after Copy to share says where it goes",
      "into Settings -> Your finds and presses Import" in SRC)

print("== deleting a session from Earnings ==")
books = SV.Earnings(os.path.join(TMP, "books"))
a1 = books.start("Ega", "Ega 1", when="2026-09-30T10:00:00Z", by="button")
books.finish("2026-09-30T10:30:00Z", by="button")
a2 = books.start("Ega", "Ega 2", when="2026-09-30T11:00:00Z", by="button")
check("a session is taken out by its id",
      books.delete(a1["id"]) is a1 and [r["id"] for r in books.sessions] == [a2["id"]])
check("from the file too", a1["id"] not in open(books.path, encoding="utf-8").read())
check("an id that is not there is None, not an error",
      books.delete("nope") is None and books.delete("") is None)
check("the window asks for a second press on the same row before it deletes",
      "def delete_session" in SRC and "DELETE_CONFIRM_S" in SRC
      and '("delete", lambda r=row: self.delete_session(r),' in SRC)

print("== prices: the Community Goal's placeholder is not a market ==")
_c, best, _h = A.read_quote({"commodity": "Iridium", "market": [
    {"station": "CG", "system": "Ega", "sell": 1038104, "demand": 999999},
    {"station": "Real", "system": "Somewhere", "sell": 640000, "demand": 5000}]},
    "Somewhere")
check("a row with demand 999,999 is left out of the best price",
      best and best["station"] == "Real", best)
check("the table is the 21 September figures, after the CG",
      SV.ceiling_price("Iridium") == 699340 and SV.ceiling_price("Thortveitite") == 629453
      and SV.published_price("Helium") == 105367)
check("and Methanol Crystals turn up on rocky ice worlds too",
      SV.ROCKY_ICE in SV.bodies_for("Methanol Crystals")
      if hasattr(SV, "ROCKY_ICE") else "Rocky ice world" in SV.bodies_for("Methanol Crystals"))
try:
    os.environ["RR_DB"] = os.path.join(TMP, "sell.db")
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
    import main as SERVER  # noqa
except Exception as exc:                                   # noqa: BLE001
    SERVER = None
    print("  SKIP  no FastAPI here (%s)" % exc.__class__.__name__)
if SERVER is not None:
    import json as _json
    import urllib.request as _ur

    class _Reply:
        def __init__(self, data): self.data = data
        def read(self): return _json.dumps(self.data).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    _rows = [{"commodityName": "iridium", "stationName": "CG", "systemName": "Ega",
              "sellPrice": 1038104, "demand": 999999, "distance": 5.0},
             {"commodityName": "iridium", "stationName": "Real", "systemName": "HR 7280",
              "sellPrice": 640000, "demand": 800, "distance": 9.0}]
    _was, _base = _ur.urlopen, SERVER.SELL_UPSTREAM_BASE
    _ur.urlopen = lambda req, timeout=None: _Reply(_rows)
    SERVER.SELL_UPSTREAM_BASE = "https://index.invalid"
    try:
        _got = SERVER.fetch_upstream_sell("Iridium", "HR 7280", 50, 20)
    finally:
        _ur.urlopen, SERVER.SELL_UPSTREAM_BASE = _was, _base
    check("the server leaves the placeholder row out too",
          [r["station"] for r in _got] == ["Real"], _got)

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
