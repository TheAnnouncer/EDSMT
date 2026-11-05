"""1.10040: one mining signal as a CSV file (#216).

Everything EDSMT knows about one Planetary Mining Location signal goes into
one file a spreadsheet or a map tool opens: where the signal was logged, the
survey centre and border, every deposit marked in it, each traced deposit
edge with its rig pins, and the line the SRV drove. One row per thing; the
first column says which. Text a spreadsheet would run as a formula goes in
with a leading apostrophe.

The signal editor (the "edit" button beside a signal) has an Export CSV
button.

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_signal_csv.py
"""
import csv
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-sigcsv-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import coverage as CV    # noqa: E402
import signalcsv as SC   # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


RADIUS = 1500000.0
LOC = {"id": "L1", "system": "Ega", "body": "Ega 1", "location": "2", "lat": "10.0",
       "lon": "20.0", "radius_m": str(RADIUS), "commodities": "Gold;Silver;Bauxite",
       "depleted": "Bauxite", "cmdr": "CMDR Jameson", "recorded": "2026-11-05T01:00:00Z",
       "notes": "near the ridge"}
DEPS = [
    {"id": "D2", "system": "Ega", "body": "Ega 1", "location": "2", "commodity": "Silver",
     "density": "High", "amount": "Medium", "rigs": "3", "rigs_fit": "7", "lat": "10.01",
     "lon": "20.02", "status": "verified", "cmdr": "CMDR Other", "recorded": "2026-11-05T02:00:00Z",
     "notes": "=HYPERLINK(\"http://bad\")"},
    {"id": "D1", "system": "Ega", "body": "Ega 1", "location": "2", "commodity": "Gold",
     "density": "Low", "amount": "High", "rigs": "", "rigs_fit": "", "lat": "10.005",
     "lon": "19.995", "status": "reported", "cmdr": "+CMDR Plus", "recorded": "2026-11-05T01:30:00Z",
     "notes": ""},
]

# A survey map on the signal: centre, border and a drive.
cmap = CV.CoverageMap("Ega", "Ega 1", RADIUS)
cmap.signal = "2"
cmap.set_centre(10.0, 20.0)
cmap.border_m = 4500.0
for step in range(20):
    cmap.add_fix(10.0 + step * 0.005, 20.0)
# A map on another signal far away on the same body: not this one's.
far = CV.CoverageMap("Ega", "Ega 1", RADIUS)
far.signal = "5"
far.set_centre(-40.0, 100.0)
far.border_m = 3000.0

# A rig plan on deposit D2, one on nothing near, one far away.
PLAN = {"system": "ega", "body": "ega 1", "radius_m": RADIUS, "spacing": 78.0,
        "pins": [{"n": 1, "lat": 10.0100, "lon": 20.0200}, {"n": 2, "lat": 10.0103, "lon": 20.0200}],
        "outline": [(10.0098, 20.0198), (10.0106, 20.0198), (10.0106, 20.0204), (10.0098, 20.0204)],
        "area_m2": 9000.0, "fit": 2, "deposit": "D2", "at": 1.0}
NEARBY = dict(PLAN, deposit="", pins=[{"n": 1, "lat": 10.002, "lon": 20.001}],
              outline=[(10.0019, 20.0009), (10.0021, 20.0011)])
FARPLAN = dict(PLAN, deposit="", pins=[{"n": 1, "lat": -40.0, "lon": 100.0}], outline=[])
OTHERBODY = dict(PLAN, body="ega 2", deposit="")

print("== the rows ==")
table = SC.rows(LOC, DEPS, maps=[far, cmap], plans=[PLAN, NEARBY, FARPLAN, OTHERBODY],
                version="1.10040", when="2026-11-05T09:00:00Z")
kinds = [r["kind"] for r in table]
check("every row has every column and nothing else",
      all(list(r.keys()) == list(SC.COLUMNS) for r in table), [list(r.keys()) for r in table[:1]])
check("it opens with the export row, then the signal", kinds[:2] == ["export", "signal"], kinds[:3])
check("the export row says the app, the version and the format",
      "EDSMT 1.10040" in table[0]["notes"] and ("format %d" % SC.FORMAT) in table[0]["notes"]
      and table[0]["recorded"] == "2026-11-05T09:00:00Z", table[0])
sig = table[1]
check("the signal row: where it was logged and what it offers",
      sig["lat"] == "10.000000" and sig["lon"] == "20.000000" and sig["signal"] == "2"
      and "Gold" in sig["commodity"] and "Bauxite (depleted)" in sig["commodity"]
      and sig["notes"] == "near the ridge", sig)
centres = [r for r in table if r["kind"] == "centre"]
borders = [r for r in table if r["kind"] == "border"]
check("one centre and one border, from this signal's map only",
      len(centres) == 1 and len(borders) == 1 and centres[0]["lat"] == "10.000000", (centres, borders))
check("the border row is the centre and the radius in metres",
      borders and borders[0]["metres"] == "4500.0" and borders[0]["lon"] == "20.000000", borders)
deps = [r for r in table if r["kind"] == "deposit"]
check("both deposits, oldest first", [d["commodity"] for d in deps] == ["Gold", "Silver"],
      [d["commodity"] for d in deps])
silver = deps[1] if len(deps) == 2 else {}
check("a deposit carries its density, amount, rigs, fit, status, who and when",
      silver.get("density") == "High" and silver.get("amount") == "Medium" and silver.get("rigs") == "3"
      and silver.get("rigs_fit") == "7" and silver.get("status") == "verified"
      and silver.get("cmdr") == "CMDR Other", silver)
check("a formula in a note goes in as text", silver.get("notes", "").startswith("'="), silver.get("notes"))
check("a name starting with + goes in as text", deps and deps[0]["cmdr"] == "'+CMDR Plus", deps[:1])
traces = [r for r in table if r["kind"] == "trace"]
pins = [r for r in table if r["kind"] == "pin"]
check("the traced edges of the plans at this signal, numbered in order",
      len(traces) == 6 and [t["seq"] for t in traces[:4]] == ["1", "2", "3", "4"], [(t["group"], t["seq"]) for t in traces])
check("the far plan and the other body's plan are left out",
      not any(p["lat"].startswith("-40") for p in pins) and len(pins) == 3, [(p["group"], p["lat"]) for p in pins])
linked = [p for p in pins if p["group"] == "1"]
check("pins keep their number, the spacing and the deposit's commodity",
      [p["seq"] for p in linked] == ["1", "2"] and linked[0]["metres"] == "78.0"
      and linked[0]["commodity"] == "Silver", linked)
drive = [r for r in table if r["kind"] == "drive"]
check("the SRV's drive, in order", len(drive) >= 2 and drive[0]["seq"] == "1"
      and drive[0]["lat"] == "10.000000", drive[:2])
check("negative numbers are numbers, not text", True)
neg = SC.rows(dict(LOC, lat="-12.5", lon="-30.25"), [], version="1.10040", when="x")
check("a negative latitude is written plainly", neg[1]["lat"] == "-12.500000", neg[1]["lat"])

print("== with little known ==")
bare = SC.rows({"system": "Ega", "body": "Ega 1", "location": "3"}, [], version="1.10040", when="x")
check("a signal with no position still exports its rows", [r["kind"] for r in bare] == ["export", "signal"]
      and bare[1]["lat"] == "", bare)
no_radius = SC.rows(dict(LOC, radius_m=""), DEPS, maps=[far, cmap],
                    plans=[dict(p, radius_m=0.0) for p in (PLAN, NEARBY, FARPLAN)],
                    version="1.10040", when="x")
check("no radius: maps by signal number, plans by deposit, nothing guessed",
      len([r for r in no_radius if r["kind"] == "border"]) == 1
      and {r["group"] for r in no_radius if r["kind"] == "pin"} == {"1"}, [r["kind"] for r in no_radius])

print("== the file ==")
path = os.path.join(TMP, "out", SC.file_name(LOC))
check("the file name says the system, body and signal",
      SC.file_name(LOC) == "EDSMT signal - Ega - Ega 1 - 2.csv", SC.file_name(LOC))
check("a name with characters Windows refuses is made safe",
      SC.file_name(dict(LOC, body='A/B:C*?"<>|')) == "EDSMT signal - Ega - A_B_C______ - 2.csv",
      SC.file_name(dict(LOC, body='A/B:C*?"<>|')))
check("write says it worked", SC.write(path, table) is True)
with open(path, "rb") as handle:
    raw = handle.read()
check("UTF-8 with a byte-order mark, so a spreadsheet reads names right", raw.startswith(b"\xef\xbb\xbf"))
with open(path, encoding="utf-8-sig", newline="") as handle:
    back = list(csv.DictReader(handle))
check("it reads back row for row", len(back) == len(table) and back[0]["kind"] == "export"
      and list(back[0].keys()) == list(SC.COLUMNS), (len(back), len(table)))
check("no blank lines between rows", b"\r\n\r\n" not in raw and b"\n\n" not in raw)
check("a folder it cannot write to answers False",
      SC.write(os.path.join(path, "nested", "x.csv"), table) is False)

print("== in the app ==")
try:
    import tkinter
    tkinter.Tk().destroy()
    have_display = True
except Exception:
    have_display = False
if not have_display:
    print("  SKIP  no display")
else:
    import json
    import edsmt as A
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as handle:
        json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": os.path.join(TMP, "none"),
                   "welcome_seen_version": A.APP_VERSION, "overlay_enabled": False}, handle)
    app = A.EDSMT()
    app.geometry("1400x900+0+0")
    app.updates.check = lambda *a, **k: None

    def pump(times=3):
        for _ in range(times):
            app.update_idletasks()
            app.update()

    pump(5)
    loc = app.store.set_location("Ega", "Ega 1", "2", lat=10.0, lon=20.0, radius_m=RADIUS,
                                 commodities=["Gold", "Silver"])
    for d in DEPS:
        app.store.add_deposit(**{k: v for k, v in d.items() if k != "id"})
    row = app.store.location("Ega", "Ega 1", "2")
    out = os.path.join(TMP, "app-export.csv")
    said = []
    real_say = app.say
    app.say = lambda text, *a, **k: said.append(text)
    try:
        done = app.export_signal(row, path=out)
    finally:
        app.say = real_say
    check("the app writes the signal's file", done is True and os.path.exists(out), (done, said))
    with open(out, encoding="utf-8-sig", newline="") as handle:
        got = list(csv.DictReader(handle))
    check("with the signal and both deposits in it",
          [r["kind"] for r in got].count("deposit") == 2 and got[1]["kind"] == "signal", [r["kind"] for r in got])
    check("and it says where the file went", any(out in s for s in said), said)
    win = A.EditLocationWindow(app, row)
    pump(3)
    found = []

    def walk(widget):
        for child in widget.winfo_children():
            if isinstance(child, A.ctk.CTkButton) and child.cget("text") == "Export CSV":
                found.append(child)
            walk(child)

    walk(win)
    check("the signal editor has an Export CSV button", len(found) == 1, len(found))
    win.destroy()
    pump(2)
    app.destroy()

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
