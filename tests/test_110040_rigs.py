"""1.10040: a site can take twelve rigs (Discord feedback, 4 Nov 2026).

A Rhino carries six rigs; a good deposit takes two Rhinos' worth. The
rig count recorded against a site now goes to 12, everywhere one is typed
or read: the rail, the deposit and correction windows, chat, imports. The
Rhino itself is unchanged - the rig keys are still 1 to 6, the sixth rig
down is still "rigs full", and two Rhinos' rigs are still 1-6 and 7-12.

Pure parts run anywhere; the app on the real toolkit under xvfb:

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_rigs.py
"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-rigs-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import chattags as CT   # noqa: E402
import importers as IMP  # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


cmd = CT.parse_command
print("== chat ==")
check("seven rigs is a site, not a mistake", cmd("!rr alex h/m 7").get("rigs") == "7", cmd("!rr alex h/m 7"))
check("twelve is the most", cmd("!rr alex h/m 12").get("rigs") == "12", cmd("!rr alex h/m 12"))
check("thirteen is not", "12 rigs" in cmd("!rr alex h/m 13").get("why", ""), cmd("!rr alex h/m 13"))
check("nor is none", "12 rigs" in cmd("!rr alex h/m 0").get("why", ""), cmd("!rr alex h/m 0"))
check("the rig keys are still the Rhino's six",
      cmd("!rr rig down 6").get("action") == "rig_down" and cmd("!rr rig down 7").get("action") == "error",
      (cmd("!rr rig down 6"), cmd("!rr rig down 7")))

print("== imports ==")
CSV = ("System,Body,LocationSignalNumber,Commodity,RigCount,MineralAmount,Density,MarkerLatitude,MarkerLongitude\n"
       "Ega,Ega 1,3,Alexandrite,12,High,Medium,10.0,20.0\n"
       "Ega,Ega 1,4,Alexandrite,13,High,Medium,11.0,21.0\n")
got = IMP.read_text(CSV)
check("a survey CSV with 12 rigs keeps them, and 13 is left blank rather than clipped",
      [f["rigs"] for f in got.finds] == ["12", ""], [f.get("rigs") for f in got.finds])
check("the importer's own ceiling is twelve", IMP.SITE_RIGS == 12
      and IMP._rigs("12", IMP.SITE_RIGS) == "12" and IMP._rigs("13", IMP.SITE_RIGS) == "")

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
    JOURNALS = os.path.join(TMP, "journals")
    os.makedirs(JOURNALS, exist_ok=True)
    with open(A.SETTINGS_FILE, "w", encoding="utf-8") as handle:
        json.dump({"asked_to_share": True, "tour_done": True, "journal_dir": JOURNALS,
                   "welcome_seen_version": A.APP_VERSION, "overlay_enabled": False}, handle)
    print("== the app ==")
    check("a Rhino still carries six; a site takes twelve", A.MAX_RIGS == 6 and A.SITE_RIGS == 12)
    check("an imported count of 12 is kept, 13 is not", A._import_rigs("12") == "12" and A._import_rigs("13") == "")
    app = A.EDSMT()
    app.geometry("1400x900+0+0")
    app.updates.check = lambda *a, **k: None

    def pump(times=3):
        for _ in range(times):
            app.update_idletasks()
            app.update()

    pump(5)
    choices = list(app.fields["rigs"].cget("values"))
    check("the rail's Rigs box offers 1 to 12", choices[-1:] == ["12"] and "7" in choices, choices)
    app.fields["rigs"].set("12")
    check("twelve is not a missing field", "rigs" not in app.missing_fields(None))
    app.fields["rigs"].set("13")
    check("thirteen is", "rigs" in app.missing_fields(None))
    app.fields["rigs"].set("")
    row = app.store.add_deposit(system="Ega", body="Ega 1", location="3", commodity="Alexandrite",
                                rigs="6", amount="High", density="Medium", lat="1.0", lon="2.0")
    win = A.EditWindow(app, row)
    pump(4)
    choices = list(win.boxes["rigs"].cget("values"))
    check("the deposit editor offers 1 to 12 too", "12" in choices and "7" in choices, choices)
    win.boxes["rigs"].set("13")
    win.save()
    pump(2)
    check("thirteen is refused with the site's ceiling", "12 rigs" in str(win.status.cget("text")),
          win.status.cget("text"))
    win.boxes["rigs"].set("12")
    win.save()
    pump(4)
    now = [r for r in app.store.at("Ega", "Ega 1") if r["id"] == row["id"]][0]
    check("and twelve is written back", now.get("rigs") == "12", now.get("rigs"))
    try:
        app.destroy()
    except Exception:
        pass

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
