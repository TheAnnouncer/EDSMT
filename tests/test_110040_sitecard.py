"""1.10040: a site card from Find and Where to land (#325).

A site on the community map, as a picture: the body's shared finds drawn
where they are, the location asked for in the middle, and a line under it
with what the map knows - rigs, commodities, who found it. Made with the
same drawing as the session map picture, saved in the pictures folder and
opened. The body's finds are fetched when the app does not have them yet,
and the card is drawn when they arrive.

Pure parts run anywhere; the windows on the real toolkit under xvfb:

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_sitecard.py
"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-sitecard-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import sitecard as SCD  # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


ROWS = [
    {"id": "shared-1", "system": "Ega", "body": "Ega 1", "location": "3", "commodity": "Tritium",
     "rigs": "6", "amount": "High", "density": "Medium", "lat": "10.000000", "lon": "20.000000",
     "cmdr": "Rocky Miner", "shared": True, "when": "2026-11-01T10:00:00Z"},
    {"id": "shared-2", "system": "Ega", "body": "Ega 1", "location": "3", "commodity": "Deuterium",
     "rigs": "2", "amount": "Low", "density": "Low", "lat": "10.010000", "lon": "20.010000",
     "cmdr": "Late Comer", "shared": True, "when": "2026-11-02T10:00:00Z"},
    {"id": "shared-3", "system": "Ega", "body": "Ega 1", "location": "7", "commodity": "Gold",
     "rigs": "1", "amount": "Depleted", "density": "", "lat": "-30.000000", "lon": "50.000000",
     "cmdr": "Old Timer", "shared": True, "when": "2026-10-01T10:00:00Z"},
]

print("== the facts under the picture ==")
check("the location's finds, every rig and kind counted",
      SCD.facts(ROWS, "3") == {"finds": 2, "rigs": 8, "commodities": ["Tritium", "Deuterium"],
                               "found_by": "Rocky Miner", "worked_out": 0, "locations": 2},
      SCD.facts(ROWS, "3"))
check("the whole body when no location is asked for",
      SCD.facts(ROWS, "") == {"finds": 3, "rigs": 9, "commodities": ["Tritium", "Deuterium", "Gold"],
                              "found_by": "Old Timer", "worked_out": 1, "locations": 2}, SCD.facts(ROWS, ""))
check("nothing known reads as nothing", SCD.facts([], "3") == {"finds": 0, "rigs": 0, "commodities": [],
                                                                "found_by": "", "worked_out": 0, "locations": 0})
check("the note is one plain line",
      SCD.note(SCD.facts(ROWS, "3")) == "Community map: 2 finds, 8 rigs, Tritium, Deuterium. First found by Rocky Miner.",
      SCD.note(SCD.facts(ROWS, "3")))
check("a worked-out site says so",
      SCD.note(SCD.facts(ROWS, "")).endswith("1 reported worked out. First found by Old Timer."),
      SCD.note(SCD.facts(ROWS, "")))
check("no finds: the note says the map has none", SCD.note(SCD.facts([], "")) == "Nothing shared on this body yet.")
check("the file name says what it is", SCD.picture_name("Ega", "Ega 1", "3").startswith("site_Ega_Ega_1_3_")
      and SCD.picture_name("Ega", "Ega 1", "3").endswith(".png"), SCD.picture_name("Ega", "Ega 1", "3"))
check("rows for the picture: the location's finds first, the rest of the body dimmer",
      [r["id"] for r in SCD.rows_for(ROWS, "3")] == ["shared-1", "shared-2", "shared-3"]
      and SCD.rows_for(ROWS, "3")[2].get("dim") is True and SCD.rows_for(ROWS, "3")[0].get("dim") is not True)

try:
    import tkinter
    tkinter.Tk().destroy()
    HAVE_DISPLAY = True
except Exception as _exc:
    HAVE_DISPLAY = False
    print("  SKIP  the windows need a display (%s). Run it under xvfb-run." % _exc)

if HAVE_DISPLAY:
    import overlay as OV
    OV.foreground_is_game = lambda: None
    import edsmt as A
    import mapimage as MI
    A.DATA_DIR = os.path.join(TMP, "data")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as handle:
        json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS,
                   "welcome_seen_version": A.APP_VERSION}, handle)
    app = A.EDSMT()
    app.geometry("1600x1000+0+0")
    app.updates.check = lambda *a, **k: None
    opened = []
    A.open_path = lambda path: opened.append(path) or True
    said = []
    app.say = lambda text, colour=None: said.append(str(text))
    asked = []
    app.community.body_deposits = lambda system, body: asked.append((system, body)) or True

    def pump(times=3):
        for _ in range(times):
            app.update_idletasks()
            app.update()

    ok, why = MI.pillow_status()
    print("== the card from the app ==")
    if not ok:
        print("  SKIP  no Pillow here: " + why)
    else:
        app.shared = {("ega", "ega 1"): {"at": time.time(), "rows": list(ROWS)}}
        out = app.site_card("Ega", "Ega 1", "3")
        check("drawn and saved in the pictures folder", out["path"] and os.path.isfile(out["path"])
              and os.path.basename(out["path"]).startswith("site_Ega_Ega_1_3_"), out)
        check("and opened", opened[-1:] == [out["path"]], opened)
        check("the note is on the picture", out["note"].startswith("Community map: 2 finds, 8 rigs"), out.get("note"))
        del asked[:]
        out = app.site_card("Ega", "Ega 2", "1")
        check("a body the app has not got yet is asked for", asked == [("Ega", "Ega 2")] and not out["path"], (asked, out))
        check("and the card waits for the answer", app._card_waiting == ("ega", "ega 2", "1"), app._card_waiting)
        check("and says so", said and "fetching" in said[-1].lower(), said[-1:])
        app.take_shared(True, json.dumps({"system": "Ega", "body": "Ega 2", "deposits": [
            {"id": 9, "system": "Ega", "planet": "Ega 2", "spot": "1", "type": "Gold", "rigs": 3,
             "amount": "High", "density": "Medium", "lat": 1.0, "lon": 2.0, "uploader": "Rocky Miner"}]}))
        pump(2)
        check("when the finds arrive, the card is drawn", opened and "site_Ega_Ega_2_1_" in os.path.basename(opened[-1]),
              opened[-1:])
        check("and the wait is over", app._card_waiting is None)

    print("== the buttons ==")
    win = A.FindWindow(app)
    pump(3)
    win._kind = "sites"
    row = {"system": "Ega", "planet": "Ega 1", "spot": "3", "types": "Tritium", "rigs": 8}
    labels = [b[0] for b in win._buttons(row)]
    check("Find's sites rows have a card button", "card" in labels, labels)
    win.destroy()
    land = A.LandWindow(app)
    pump(3)
    import survey as SV
    bodies = SV.rank_bodies("Ega", [{"body": "Ega 1", "landable": True, "planet_class": "Icy body"},
                                    {"body": "Ega 9", "landable": True, "planet_class": "Icy body"}],
                            sites=[{"system": "Ega", "planet": "Ega 1", "spot": "3", "rigs": 8,
                                    "types": "Tritium", "worked_out": False}])
    by = {r["body"]: r for r in bodies}
    check("Where to land's bodies with known sites have one",
          by["Ega 1"]["known"] and "card" in [b[0] for b in land._buttons(by["Ega 1"])],
          [b[0] for b in land._buttons(by["Ega 1"])])
    check("but not a body nobody has mapped", "card" not in [b[0] for b in land._buttons(by["Ega 9"])])
    land.destroy()
    try:
        app.destroy()
    except Exception:
        pass

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
