"""1.10040 (#306): choose which materials the commodity lists offer.

- A tick list of the thirteen surface materials and the extras decides what
  the commodity type-ahead and the commodity filters offer. All of them to
  begin with.
- Settings -> Basics opens it, and so does a gear beside Find's commodity
  filter: the same picker either way.
- What is picked is kept. What the game says the body under you offers is
  still offered in the type-ahead, ticked or not.

Pure parts run anywhere; the app on the real toolkit under xvfb:

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tests/test_110040_materials.py
"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-materials-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import edonline as EDO     # noqa: E402
import materials as MT     # noqa: E402
import survey as SV        # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def section(title):
    def wrap(fn):
        print("== " + title + " ==")
        try:
            fn()
        except Exception as exc:
            import traceback
            check(title + " (ran to the end)", False, "%s: %s" % (type(exc).__name__, exc))
            traceback.print_exc(limit=6)
        return fn
    return wrap


@section("which materials are offered")
def _pure():
    groups = MT.choices(SV.KNOWN_COMMODITIES)
    check("two groups: the thirteen, then the extras",
          [g for g, _n in groups] == ["The thirteen", "Extras"]
          and groups[0][1] == list(EDO.SURFACE_COMMODITIES), groups[0])
    extras = groups[1][1]
    check("the extras are every other material known, once each, none of the thirteen",
          extras and len(set(extras)) == len(extras)
          and not {SV.fold(n) for n in extras} & {SV.fold(n) for n in EDO.SURFACE_COMMODITIES}
          and "Gold" in extras and "Water" in extras, extras[:6])
    names = ["Gold", "Water", "Iridium", "Bastnäsite"]
    check("nothing chosen: everything is offered", MT.offered(names, {}) == names
          and MT.offered(names, {MT.SETTING: []}) == names)
    settings = {MT.SETTING: ["water", "Bastnasite"]}
    check("the ones left unticked are not offered, whatever their spelling",
          MT.offered(names, settings) == ["Gold", "Iridium"], MT.offered(names, settings))
    check("what must stay - Any, or what the body offers - stays",
          MT.offered(["Any"] + names, settings, keep=("Any", "Water")) == ["Any", "Gold", "Water", "Iridium"])
    check("ticked or not, a name is asked of the setting",
          MT.is_offered("Gold", settings) and not MT.is_offered("WATER", settings))
    hidden = MT.hidden_from(["Gold", "Iridium"], names)
    check("the ticks saved as what is left out, so a new material is offered from the start",
          sorted(hidden) == ["Bastnäsite", "Water"], hidden)
    check("a setting that is not a list is ignored", MT.offered(names, {MT.SETTING: "Gold"}) == names)


# ---------------------------------------------------------------------------
# The app on the real toolkit. Nothing leaves the machine.
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as _exc:
    print("  SKIP  the app needs a display (%s). Run it under xvfb-run." % _exc)
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    raise SystemExit(1 if fails else 0)

import socket            # noqa: E402


def _refuse(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        raise OSError("this check runs offline")
    return _real_connect(self, address)


_real_connect = socket.socket.connect
socket.socket.connect = _refuse
socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(OSError("offline"))

import overlay as OV     # noqa: E402
OV.foreground_is_game = lambda: None
import edsmt as A        # noqa: E402
A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
    json.dump({"asked_to_share": True, "welcome_seen_version": A.APP_VERSION, "tour_done": True,
               "journal_dir": JOURNALS, "find_unlocked": True, "overlay_enabled": False}, _f)

check("a new install offers every material", A.DEFAULT_SETTINGS.get(MT.SETTING) == [])

app = A.EDSMT()
app.geometry("1600x1000+0+0")
app.updates.check = lambda *args, **kwargs: None
app.community.enabled = False


def pump(times=3):
    for _ in range(times):
        app.update_idletasks()
        app.update()


def settle(seconds=1.0):
    until = time.time() + seconds
    while time.time() < until:
        pump(1)
        time.sleep(0.02)


def pickers():
    return [w for w in app.winfo_children() if isinstance(w, A.MaterialsWindow)]


settle(3.0)


@section("the app: the gear beside Find's commodity filter opens the picker")
def _gear():
    app.open_find()
    settle(1.0)
    finder = app.finder
    gear = finder.materials_button
    check("the gear sits beside the commodity filter",
          gear.winfo_ismapped() and gear.master is finder.commodity.master
          and abs(gear.winfo_rootx() - (finder.commodity.winfo_rootx() + finder.commodity.winfo_width())) < 40,
          (gear.winfo_rootx(), finder.commodity.winfo_rootx(), finder.commodity.winfo_width()))
    check("everything offered to begin with",
          "Water" in finder.commodity.cget("values") and "Gold" in finder.commodity.cget("values"))
    gear.invoke()
    settle(0.8)
    opened = pickers()
    check("pressed: the picker opens", len(opened) == 1)
    picker = opened[0]
    check("a tick for each of the thirteen and each extra, all ticked",
          set(picker.ticks) >= set(EDO.SURFACE_COMMODITIES) | {"Gold", "Water"}
          and all(var.get() for var in picker.ticks.values()), len(picker.ticks))
    picker.ticks["Water"].set(False)
    picker.ticks["Gold"].set(False)
    picker.save()
    settle(0.6)
    check("saved: kept as what is left out", sorted(app.settings.get(MT.SETTING) or []) == ["Gold", "Water"],
          app.settings.get(MT.SETTING))
    with open(A.SETTINGS_FILE, encoding="utf-8") as handle:
        on_disk = json.load(handle)
    check("and written to the settings file", sorted(on_disk.get(MT.SETTING) or []) == ["Gold", "Water"])
    check("the picker closes", not pickers() or not pickers()[0].winfo_exists())
    values = list(finder.commodity.cget("values"))
    check("Find's commodity filter no longer offers them", "Water" not in values and "Gold" not in values
          and "Iridium" in values and values[0] == "Any", values[:6])
    check("nor does its type-ahead", "Gold" not in finder._commodity_choices("go"),
          finder._commodity_choices("go"))
    finder._offer(["Gold", "Painite"])
    check("names the server adds are sifted the same way",
          "Gold" not in finder.commodity.cget("values") and "Painite" in finder.commodity.cget("values"))


@section("the app: the other lists follow")
def _lists():
    names = app.refresh_commodities()
    check("the commodity type-ahead in the main window", "Water" not in names and "Iridium" in names,
          names[:8])
    lander = app.open_land()
    settle(0.8)
    values = list(lander.carrying.cget("values"))
    check("Where to land's Carrying", "Gold" not in values and "Iridium" in values, values[:6])
    sites = app.open_sites()
    settle(0.8)
    values = list(sites.commodity.cget("values"))
    check("My sites' Commodity", "Gold" not in values and "Iridium" in values, values[:6])


@section("the app: Settings -> Basics opens the same picker, as it was left")
def _settings():
    app.open_settings()
    settle(1.0)
    window = [w for w in app.winfo_children() if isinstance(w, A.SettingsWindow)][-1]
    window.materials_button.invoke()
    settle(0.8)
    opened = [p for p in pickers() if p.winfo_exists()]
    check("Basics has the button, and it opens the picker", len(opened) == 1)
    picker = opened[-1]
    check("with the ticks as saved", picker.ticks["Water"].get() is False and picker.ticks["Gold"].get() is False
          and picker.ticks["Iridium"].get() is True)
    picker.tick_all(True)
    picker.save()
    settle(0.6)
    check("all ticked again: everything offered", app.settings.get(MT.SETTING) == []
          and "Gold" in app.finder.commodity.cget("values"))


@section("the app: what the body offers is offered, ticked or not")
def _body():
    app.settings[MT.SETTING] = ["Water"]
    app.here = lambda: ("Ega", "Ega 1")
    app.store.set_location("Ega", "Ega 1", "1", lat=1.0, lon=1.0, radius_m=2e6)
    app.store.add_deposit(system="Ega", body="Ega 1", location="1", commodity="Water", rigs="1",
                          amount="High", density="Medium", lat="1.000000", lon="1.000000")
    names = app.refresh_commodities()
    check("Water is mined here, so the type-ahead still has it", "Water" in names, names[:6])


if __name__ == "__main__":
    print()
    print("FAILURES:", len(fails))
    for f in fails:
        print("  -", f)
    try:
        app.destroy()
    except Exception:
        pass
    sys.exit(1 if fails else 0)
