"""What 1.10034 adds, each piece held down so it stays built.

Driven without a display, like the other suites.

    python tests/test_110034.py
"""
import os, sys, json, re, time, tempfile, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "stubs"))
import _ctkstub  # noqa
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="edsmt-110034-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
import edsmt as A, survey as SV  # noqa

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)


SRC = open(A.__file__, encoding="utf-8").read()
SURVEY_SRC = open(SV.__file__, encoding="utf-8").read()


def method(cls, name):
    m = re.search(r"\n    def %s\(.*?(?=\n    def |\nclass |\Z)" % name,
                  SRC[SRC.index("class %s" % cls):], re.S)
    return m.group(0) if m else ""


# ---------------------------------------------------------------------------
print("== no check can reach the commander's own settings ==")
# Every BUILD.bat run put his overlay, theme and keys back to the defaults:
# test_wiring imported the app without moving %LOCALAPPDATA%, so the
# windows it drove saved their test settings over his real ones - the file
# he found said Ega / Ega 1, the test's own system.
tests = sorted(n for n in os.listdir(HERE) if n.startswith("test_") and n.endswith(".py"))
unguarded = []
for name in tests:
    text = open(os.path.join(HERE, name), encoding="utf-8").read()
    imp = re.search(r"^\s*import edsmt\b|^\s*from edsmt import", text, re.M)
    if not imp:
        continue
    guard = text.find('os.environ["LOCALAPPDATA"]')
    if guard < 0 or guard > imp.start():
        unguarded.append(name)
check("every check that imports the app moves %LOCALAPPDATA% first",
      not unguarded, unguarded)
check("test_wiring, the one that did not, now does",
      "test_wiring.py" in tests and "test_wiring.py" not in unguarded)
runner = open(os.path.join(HERE, "run_all.py"), encoding="utf-8").read()
check("and run_all gives every check a sandbox %LOCALAPPDATA% before any runs",
      0 <= runner.find('os.environ["LOCALAPPDATA"]') < runner.find("subprocess.run("))

# ---------------------------------------------------------------------------
print("== dated copies of the settings ==")
hist = os.path.join(TMP, "hist")
base = dict(A.DEFAULT_SETTINGS, app_theme="gold", overlay_preset="streamer",
            overlay_layout={"radar": {"x": 0.1, "y": 0.2, "w": 0.1, "h": 0.2}})
t0 = time.mktime((2026, 10, 7, 12, 0, 0, 0, 0, -1))
first = A.keep_settings_copy(base, now=t0, folder=hist)
check("the first save writes a copy", first and os.path.isfile(first), first)
check("named by when it was taken",
      first and os.path.basename(first) == "settings-20261007-120000.json")
again = A.keep_settings_copy(dict(base, app_theme="red"), now=t0 + 60, folder=hist)
check("a second change inside the window adds nothing",
      again is None and len(A.settings_history(hist)) == 1)
moved_only = A.keep_settings_copy(dict(base, last_system="Ega", last_body="Ega 1"),
                                  now=t0 + 3600, folder=hist)
check("where you were last is not a setting: no copy for that alone",
      moved_only is None and len(A.settings_history(hist)) == 1)
changed = A.keep_settings_copy(dict(base, overlay_preset="minimal"),
                               now=t0 + 3600, folder=hist)
check("a real change after the window is copied", changed is not None
      and len(A.settings_history(hist)) == 2)
newest = A.settings_history(hist)
check("newest first", newest[0][1] == changed and newest[1][1] == first)
for k in range(40):
    A.keep_settings_copy(dict(base, overlay_targets=k),
                         now=t0 + 7200 + k * 3600, folder=hist)
check("only the newest %d are kept" % A.SETTINGS_HISTORY_KEPT,
      len(A.settings_history(hist)) == A.SETTINGS_HISTORY_KEPT,
      len(A.settings_history(hist)))
label = A.settings_copy_label(*A.settings_history(hist)[0])
check("the picker says when, and the theme and layout it holds",
      "2026" in label and "theme gold" in label and "layout streamer" in label, label)
check("a file this did not write is not offered",
      A._history_when("settings.json.bak") is None
      and A._history_when("settings-junk.json") is None)
check("save_settings takes the copy every time it writes",
      "keep_settings_copy(data)" in re.search(
          r"def save_settings\(data\):.*?\n\n\n", SRC, re.S).group(0))

print("== putting a copy back ==")
os.makedirs(A.DATA_DIR, exist_ok=True)
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as fh:
    json.dump(dict(A.DEFAULT_SETTINGS, last_system="Ega", last_body="Ega 1"), fh)
when, path = A.settings_history(hist)[-1]
put = A.restore_settings_copy(path, now=t0 + 999999)
now_on_disk = json.load(open(A.SETTINGS_FILE, encoding="utf-8"))
check("the copy is the settings now", now_on_disk.get("app_theme") == "gold"
      and now_on_disk.get("overlay_layout", {}).get("radar"), now_on_disk.get("app_theme"))
aside = [n for n in os.listdir(A.DATA_DIR) if n.startswith("settings.json.before-restore-")]
check("and what was there is kept beside it", len(aside) == 1, aside)
try:
    A.restore_settings_copy(os.path.join(TMP, "nothing-here.json"))
    refused = False
except ValueError:
    refused = True
check("a copy that cannot be read is refused, and nothing is touched", refused)
loaded = A.load_settings()
check("and loading wears it: theme and overlay placement come back",
      loaded.get("app_theme") == "gold"
      and loaded.get("overlay_layout", {}).get("radar", {}).get("x") == 0.1)

print("== Settings offers them ==")
build = method("SettingsWindow", "__init__")
check("Settings lists the dated copies", "settings_history()" in build
      and "self.history_box" in build and 'state="readonly"' in build)
check("with a button that puts the picked one back",
      "command=self.restore_settings_now" in build)
restore = method("SettingsWindow", "restore_settings_now")
check("putting one back wears it at once, not at the next start",
      "restore_settings_copy(path)" in restore
      and "self.app.apply_settings(load_settings())" in restore)
check("and closes Settings, which still shows the old ones",
      "self.destroy()" in restore)
zipped = method("SettingsWindow", "restore_now")
check("restoring a backup zip now wears the settings in it too",
      "self.app.apply_settings(load_settings())" in zipped
      and "self.destroy()" in zipped)

# ---------------------------------------------------------------------------
print("== a backup carries the survey and the settings copies ==")
data = os.path.join(TMP, "data")
store = SV.Survey(data)
store.set_location("Ega", "Ega 1", 1, 12.0, -45.0, 1.2e6)
os.makedirs(os.path.join(data, "coverage"), exist_ok=True)
with open(os.path.join(data, "coverage", "Ega_Ega_1-abc.json"), "w") as fh:
    fh.write('{"points": [[1, 2]]}')
os.makedirs(os.path.join(data, "settings-history"), exist_ok=True)
with open(os.path.join(data, "settings-history", "settings-20261007-120000.json"), "w") as fh:
    fh.write('{"app_theme": "gold"}')
with open(os.path.join(data, "settings.json"), "w") as fh:
    fh.write('{"app_theme": "gold", "overlay_preset": "streamer"}')
out = os.path.join(TMP, "backups")
zip_path, count = store.backup_to(out)
names = zipfile.ZipFile(zip_path).namelist()
check("the settings are in it", "settings.json" in names, names)
check("the swept ground and survey area of every body are in it",
      "coverage/Ega_Ega_1-abc.json" in names, names)
check("the dated settings copies are in it",
      "settings-history/settings-20261007-120000.json" in names, names)
check("the count says so", count == len(names), (count, len(names)))

fresh = os.path.join(TMP, "fresh")
SV.Survey(fresh)
os.makedirs(os.path.join(fresh, "coverage"), exist_ok=True)
with open(os.path.join(fresh, "coverage", "Ega_Ega_1-abc.json"), "w") as fh:
    fh.write('{"points": []}')
restored = SV.Survey(fresh).restore_from(zip_path)
check("restoring puts the coverage back",
      json.load(open(os.path.join(fresh, "coverage", "Ega_Ega_1-abc.json")))["points"] == [[1, 2]])
check("and the settings copies",
      os.path.isfile(os.path.join(fresh, "settings-history", "settings-20261007-120000.json")))
check("what was there is kept beside it, renamed",
      any(n.startswith("Ega_Ega_1-abc.json.before-restore-")
          for n in os.listdir(os.path.join(fresh, "coverage"))))
check("every file in the zip came back", restored == len(names), (restored, len(names)))

print("== nothing in a zip can write outside the data folder ==")
for bad in ("../evil.json", "/etc/evil.json", "coverage/../../evil.json",
            "C:/evil.json", "other/evil.json", "coverage/deeper/evil.json",
            "coverage\\evil.json", "", "coverage/"):
    check("refused: %r" % bad, not SV.backup_member_ok(bad))
for good in ("deposits.csv", "settings.json", "coverage/x.json",
             "settings-history/settings-20261007-120000.json"):
    check("allowed: %r" % good, SV.backup_member_ok(good))
evil = os.path.join(TMP, "evil.zip")
with zipfile.ZipFile(evil, "w") as bundle:
    bundle.writestr("../escaped.json", "{}")
    bundle.writestr("other/escaped.json", "{}")
    bundle.writestr("deposits.csv", "id\n")
target = os.path.join(TMP, "victim")
SV.Survey(target).restore_from(evil)
check("a zip that tries to climb out writes nothing outside",
      not os.path.exists(os.path.join(TMP, "escaped.json"))
      and not os.path.exists(os.path.join(target, "other")))
check("survey.py names the folders a backup carries",
      'BACKUP_FOLDERS = ("coverage", "settings-history")' in SURVEY_SRC)

# ---------------------------------------------------------------------------
print("== the guide's box goes when the guide does ==")
import overlay as OV  # noqa
class _Panels:
    def __init__(self):
        self.panels = {OV.RADAR: object(), OV.GUIDE: object()}
        self.refreshed = 0
    def refresh_settings(self, settings):
        self.refreshed += 1
        if not settings.get("overlay_show_guide"):
            self.panels.pop(OV.GUIDE, None)
g = A.EDSMT.__new__(A.EDSMT)
g.settings = dict(A.DEFAULT_SETTINGS, overlay_show_guide=True)
g.overlay = _Panels()
g.say = lambda *a, **k: None
last = {"step": 11, "total": 11, "title": "Rigs down", "detail": "Done."}
g.retire_guide(last)
check("finishing the run switches the guide off", not g.settings["overlay_show_guide"]
      and g.settings["guide_done"])
check("the farewell card is shown first", g.guide_card() and OV.GUIDE in g.overlay.panels)
g._guide_farewell = (time.time() - 1, last)
check("once the farewell has been read, there is no card", g.guide_card() is None)
check("and the GUIDE box is taken down, not left frozen on its last card",
      OV.GUIDE not in g.overlay.panels and OV.RADAR in g.overlay.panels,
      list(g.overlay.panels))
before = g.overlay.refreshed
g.guide_card()
check("and it is not asked again every tick", g.overlay.refreshed == before)
h = A.EDSMT.__new__(A.EDSMT)
h.settings = dict(A.DEFAULT_SETTINGS, overlay_show_guide=False)
h.overlay = _Panels()
check("a guide switched off in Settings loses its box the same way",
      h.guide_card() is None and OV.GUIDE not in h.overlay.panels)
k = A.EDSMT.__new__(A.EDSMT)
k.settings = dict(A.DEFAULT_SETTINGS, overlay_show_guide=False)
k.overlay = None
check("with no overlay at all it simply says no", k.close_guide_box() is False)

# ---------------------------------------------------------------------------
print("== Where to land remembers a system honked in an earlier session ==")
import bodybook as BB, journal as JN, threading  # noqa
HOME = "Col 285 Sector KB-W c2-14"
GAME = os.path.join(TMP, "game"); os.makedirs(GAME)
JN.EVENT_LOG = os.path.join(GAME, "events.log")
def write(name, events, mtime):
    path = os.path.join(GAME, name)
    with open(path, "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")
    os.utime(path, (mtime, mtime))
    return path
T0 = time.time() - 9 * 86400
# Nine days ago: jumped in, honked, scanned. An older journal: the Scan
# events do not carry the system's name, the jump before them does.
write("Journal.2026-09-28T211706.01.log", [
    {"timestamp": "2026-09-28T21:17:06Z", "event": "Fileheader", "part": 1},
    {"timestamp": "2026-09-28T21:20:00Z", "event": "FSDJump", "StarSystem": HOME,
     "SystemAddress": 3932344554146, "StarPos": [1.0, 2.0, 3.0]},
    {"timestamp": "2026-09-28T21:20:30Z", "event": "FSSDiscoveryScan", "BodyCount": 4,
     "SystemName": HOME, "SystemAddress": 3932344554146},
    {"timestamp": "2026-09-28T21:21:00Z", "event": "Scan", "BodyName": HOME + " BC 1",
     "PlanetClass": "High metal content body", "Landable": True,
     "DistanceFromArrivalLS": 1559.5, "SurfaceGravity": 5.82, "Radius": 2541200.0,
     "Volcanism": ""},
    {"timestamp": "2026-09-28T21:21:10Z", "event": "Scan", "BodyName": HOME + " BC 2",
     "PlanetClass": "High metal content body", "Landable": True,
     "DistanceFromArrivalLS": 1536.0, "SurfaceGravity": 5.94},
    {"timestamp": "2026-09-28T21:22:00Z", "event": "SAASignalsFound", "BodyName": HOME + " BC 1",
     "Signals": [{"Type": "$PlanetaryMiningLocation_Name;",
                  "Type_Localised": "Planetary Mining Location", "Count": 23}]},
    {"timestamp": "2026-09-28T21:30:00Z", "event": "FSDJump", "StarSystem": "Elsewhere",
     "SystemAddress": 1, "StarPos": [0, 0, 0]},
    {"timestamp": "2026-09-28T21:31:00Z", "event": "Scan", "BodyName": "Elsewhere 1",
     "PlanetClass": "Icy body", "Landable": True, "DistanceFromArrivalLS": 10.0},
], T0)
# Today: a new game session, back home, honked - and the honk describes no
# body, because they were described nine days ago.
write("Journal.2026-10-07T163554.01.log", [
    {"timestamp": "2026-10-07T16:35:54Z", "event": "Fileheader", "part": 1},
    {"timestamp": "2026-10-07T16:40:00Z", "event": "FSDJump", "StarSystem": HOME,
     "SystemAddress": 3932344554146, "StarPos": [1.0, 2.0, 3.0]},
    {"timestamp": "2026-10-07T16:40:30Z", "event": "FSSDiscoveryScan", "BodyCount": 4,
     "SystemName": HOME, "SystemAddress": 3932344554146},
], time.time())
watch = JN.JournalWatcher(GAME)
watch.poll()
check("today's journal alone knows no body here - the bug as reported",
      watch.system == HOME and watch.system_bodies(HOME) == [],
      (watch.system, watch.system_bodies(HOME)))
check("but it does know the honk counted four", watch.body_counts.get(HOME.lower()) == 4,
      watch.body_counts)

book = BB.BodyBook(os.path.join(TMP, "bookdata"))
read, filed = BB.backfill(book, GAME)
check("the older journals are read once", read == 2 and filed >= 4, (read, filed))
home = book.bodies(HOME)
check("the bodies scanned nine days ago are remembered, under the right system",
      sorted(home) == [HOME + " BC 1", HOME + " BC 2"], sorted(home))
check("with what the scan said",
      home[HOME + " BC 1"]["facts"].get("planet_class") == "High metal content body"
      and home[HOME + " BC 1"]["facts"].get("landable") is True
      and home[HOME + " BC 1"]["facts"].get("distance_ls") == 1559.5)
check("and what the DSS mapped", home[HOME + " BC 1"]["mapped"]
      and home[HOME + " BC 1"]["signals"][0]["count"] == 23)
check("a body in the next system is filed under that one",
      list(book.bodies("Elsewhere")) == ["Elsewhere 1"])
check("the honk's count is kept", (book.system(HOME) or {}).get("body_count") == 4)
check("a file already read is not read again",
      BB.backfill(book, GAME) == (0, 0))
stop = threading.Event(); stop.set()
check("and a stopped run reads nothing",
      BB.backfill(BB.BodyBook(os.path.join(TMP, "stopped")), GAME, stop=stop) == (0, 0))
added = BB.seed_watcher(watch, book, HOME)
listed = {b["body"]: b for b in watch.system_bodies(HOME)}
check("put back into the reader, Where to land lists them", added == 2
      and HOME + " BC 1" in listed and listed[HOME + " BC 1"]["landable"], listed)
check("with the mining locations counted", listed[HOME + " BC 1"]["locations"] == 23,
      listed[HOME + " BC 1"])
check("and the DSS map honoured", listed[HOME + " BC 1"]["mapped"])

print("== the journal always wins ==")
book2 = BB.BodyBook(os.path.join(TMP, "book2"))
book2.put("S", "S 1", {"landable": True, "planet_class": "Rocky body", "gravity": 2.0})
book2.put("S", "S 1", {"landable": False, "planet_class": "Icy body",
                       "temperature_k": 150.0}, source=BB.SOURCE_PUBLIC)
one = book2.bodies("S")["S 1"]
check("a public answer never overwrites what the journal said",
      one["facts"]["landable"] is True and one["facts"]["planet_class"] == "Rocky body"
      and one["source"] == BB.SOURCE_JOURNAL, one)
check("it only fills what the journal left out", one["facts"].get("temperature_k") == 150.0)
book2.put("S", "S 2", {"landable": True}, signals=[{"type": "mining", "count": 3}],
          source=BB.SOURCE_PUBLIC)
book2.put("S", "S 2", {"landable": False}, signals=[{"type": "mining", "count": 5}])
two = book2.bodies("S")["S 2"]
check("a body first known from the public database is the journal's once it scans it",
      two["source"] == BB.SOURCE_JOURNAL and two["facts"]["landable"] is False
      and two["signals"][0]["count"] == 5, two)
rev = book2.revision
check("writing the same thing twice changes nothing",
      book2.put("S", "S 2", {"landable": False}, signals=[{"type": "mining", "count": 5}])
      is False and book2.revision == rev)
seen = {}
w2 = JN.JournalWatcher(os.path.join(TMP, "nowhere"))
w2.body_facts["T 1"] = {"system": "T", "landable": True}
check("the reader's bodies are written down", BB.remember_watcher(w2, book2, "T", seen) == 1)
check("and not again while nothing has changed", BB.remember_watcher(w2, book2, "T", seen) == 0)
w2.body_facts["T 1"]["gravity"] = 3.0
check("but again when something has", BB.remember_watcher(w2, book2, "T", seen) == 1)
w2.body_facts["T 1"]["source"] = BB.SOURCE_PUBLIC
w2._record_body("Scan", {"BodyName": "T 1", "StarSystem": "T", "Landable": True})
check("a scan makes a body the journal's own", "source" not in w2.body_facts["T 1"])

print("== the public body database, through the server ==")
facts, sig = BB.public_rows_to_facts({"body": "X 1", "landable": True, "distance_ls": 12.5,
                                      "planet_class": "Icy body", "gravity_g": 0.5,
                                      "radius_km": 1000.0, "mining_locations": 19,
                                      "volcanism": "None"})
check("gravity comes back in the journal's units",
      abs(facts["gravity"] - 0.5 * 9.80665) < 1e-9)
check("and the radius in metres", facts["radius_m"] == 1000000.0)
check("mining locations become a signal the reader counts",
      JN.MINING_SIGNAL.search(sig[0]["type"]) and sig[0]["count"] == 19)

class _Community:
    can_read = True
    def __init__(self): self.asked = []
    def bodies(self, address, system=""):
        self.asked.append((address, system)); return True
app = A.EDSMT.__new__(A.EDSMT)
app.watcher = JN.JournalWatcher(GAME)
app.watcher.poll()
app.bodybook = BB.BodyBook(os.path.join(TMP, "appbook"))
app.community = _Community()
app._bodies_seen, app._bodies_asked, app._bodies_asking = {}, set(), {}
app._backfill = "not now"           # the background read is tested above
app.follow_bodies(now=1000.0)
check("in a system it knows too little about, the app asks the server once",
      app.community.asked == [(3932344554146, HOME)], app.community.asked)
app.follow_bodies(now=1001.0)
check("and only once", len(app.community.asked) == 1)
answer = {"system": HOME, "address": 3932344554146, "body_count": 21, "status": "live",
          "bodies": [{"body": HOME + " ABC 1 a", "landable": True, "distance_ls": 2598.3,
                      "planet_class": "Icy body", "gravity_g": 0.078,
                      "mining_locations": 19, "volcanism": "carbon dioxide geysers volcanism"}]}
app._land_changed = lambda: None
app.take_bodies(True, json.dumps(answer))
app.follow_bodies(now=1010.0)
listed = {b["body"]: b for b in app.watcher.system_bodies(HOME)}
check("the answer reaches Where to land", HOME + " ABC 1 a" in listed
      and listed[HOME + " ABC 1 a"]["locations"] == 19, sorted(listed))
check("marked as from the public database, so the window can say so",
      app.public_body_count(HOME) == 1, app.public_body_count(HOME))
check("when it was asked is kept, so it is not asked again for a month",
      (app.bodybook.system(HOME) or {}).get("public_at"))
app2 = A.EDSMT.__new__(A.EDSMT)
app2.watcher, app2.bodybook = app.watcher, app.bodybook
app2.community = _Community()
app2._bodies_seen, app2._bodies_asked, app2._bodies_asking = {}, set(), {}
app2._backfill = "not now"
app2.follow_bodies(now=2000.0)
check("a restart a day later does not ask again", app2.community.asked == [],
      app2.community.asked)
check("but Refresh can", app2.ask_public_bodies(HOME, force=True)
      and len(app2.community.asked) == 1)
full = A.EDSMT.__new__(A.EDSMT)
full.watcher = JN.JournalWatcher(os.path.join(TMP, "x"))
full.watcher.system, full.watcher.system_address = "Full", 5
full.watcher.body_counts = {"full": 1}
full.watcher.body_facts = {"Full 1": {"system": "Full", "landable": True}}
full.bodybook = BB.BodyBook(os.path.join(TMP, "fullbook"))
full.community = _Community()
full._bodies_asked, full._bodies_asking = set(), {}
check("a system the journal has described in full is not asked about",
      full.ask_public_bodies("Full", now=1.0) is False and full.community.asked == [])
land = A.LandWindow.__new__(A.LandWindow)
land.app = app
land.heading = _ctkstub.ctk.CTkLabel(None)
land.summary = _ctkstub.ctk.CTkLabel(None)
land.status = _ctkstub.ctk.CTkLabel(None)
land._rows = []
app.land_sites_for = lambda system: None
app.land_problem = lambda: ""
app._backfill_progress = (3, 10)
land._summarise(HOME)
said = land.summary.cget("text") if hasattr(land.summary, "cget") else ""
check("Where to land says how many came from the public database, and that it is "
      "still reading older journals", "from the public body database" in str(said)
      and "reading your older journals" in str(said), said)
check("the source tree lists the new file, and both builds carry it",
      "bodybook.py" in open(os.path.join(os.path.dirname(HERE), "CONTRIBUTING.md")).read()
      and all('"bodybook"' in open(os.path.join(os.path.dirname(HERE), "build", n)).read()
              for n in ("EDSMT.spec", "EDSMT-onefile.spec")))

# ---------------------------------------------------------------------------
print("== your own Discord channel (#150) ==")
import edonline as EDO  # noqa
HOOK = "https://discord.com/api/webhooks/123456789012345678/" + "a" * 68
for good in (HOOK, HOOK.replace("discord.com", "discordapp.com"),
             HOOK.replace("https://", "https://canary."), HOOK + "/"):
    check("a webhook address is taken: %s..." % good[:40], EDO.discord_hook_ok(good))
for bad in ("", "http://discord.com/api/webhooks/1234567/" + "a" * 68,
            "https://discord.com.evil.example/api/webhooks/1234567/" + "a" * 68,
            "https://discord.com/api/webhooks/1234567", HOOK + "?wait=true",
            "https://example.com/api/webhooks/1234567/" + "a" * 68):
    check("and anything else is not: %r" % bad[:48], not EDO.discord_hook_ok(bad))
find = EDO.discord_find_message({"commodity": "Monazite", "rigs": "4", "system": "Ega",
                                 "body": "Ega 1", "location": "7", "amount": "High",
                                 "density": "Medium", "lat": "12.5", "lon": "-45.25"},
                                "Jameson")
embed = find["embeds"][0]
check("a find reads as one", embed["title"] == "New find: Monazite - 4 rigs", embed["title"])
check("with where it is", {f["name"]: f["value"] for f in embed["fields"]}.get("Lat, long")
      == "12.5000, -45.2500", embed["fields"])
check("and nobody is pinged, whatever was typed", find["allowed_mentions"] == {"parse": []})
long = EDO.discord_message("x" * 999, [("Note", "y" * 5000)], description="z" * 9000)
check("everything is cut to Discord's limits",
      len(long["embeds"][0]["title"]) <= 256 and len(long["embeds"][0]["fields"][0]["value"]) <= 1024
      and len(long["embeds"][0]["description"]) <= 4096)
run = {"id": "r1", "started": "2026-10-07T18:00:00Z", "ended": "2026-10-07T19:30:00Z",
       "closed": "2026-10-07T19:30:00Z", "system": "Ega", "body": "Ega 1",
       "mined": "Monazite:96;Painite:24", "credits": "24000000", "station": "Port",
       "sold_in": "Ega"}
summary = EDO.discord_session_message(run, "Jameson")["embeds"][0]
check("a session says what came out of the ground", summary["title"] == "Rhino session: 120 t mined"
      and "Monazite: 96 t" in summary["description"], summary)
check("and what it paid", any(f["name"] == "Credits" and "24,000,000" in f["value"]
                              for f in summary["fields"]), summary["fields"])
sent = []
real_post = EDO.post_json
EDO.post_json = lambda url, payload, timeout=20.0, headers=None: sent.append(url) or {"id": "1"}
EDO.discord_post(HOOK, find)
check("it waits for Discord to confirm, so a dead webhook says so",
      sent and sent[-1].endswith("?wait=true"), sent)
try:
    EDO.discord_post("https://example.com/x", find)
    refused = False
except ValueError:
    refused = True
check("an address that is not a webhook is never sent anything",
      refused and len(sent) == 1)
EDO.post_json = real_post
check("an error names the host, never the address with its token",
      EDO._host_of(HOOK) == "discord.com")

class _Worker:
    def __init__(self): self.jobs = []
    def submit(self, tag, fn): self.jobs.append(tag)
d = A.EDSMT.__new__(A.EDSMT)
d.worker = _Worker()
d.settings = dict(A.DEFAULT_SETTINGS)
d.watcher = type("W", (), {"cmdr": "Jameson"})()
check("with no webhook set, nothing is posted", d.post_discord_find({"commodity": "Gold"}) is False
      and d.worker.jobs == [])
d.settings["discord_webhook"] = HOOK
check("with one, a find goes", d.post_discord_find({"commodity": "Gold"})
      and d.worker.jobs == [EDO.DISCORD_TAG])
d.settings["discord_post_finds"] = False
check("unless finds are switched off", d.post_discord_find({"commodity": "Gold"}) is False)
d.earnings = type("E", (), {"sessions": [dict(run, id="old")]})()
check("sessions already over when EDSMT starts are not posted",
      d.post_discord_sessions() == 0 and len(d.worker.jobs) == 1)
d.earnings.sessions.append(dict(run, id="new"))
d.earnings.sessions.append(dict(run, id="empty", mined=""))
d.earnings.sessions.append(dict(run, id="live", closed=""))
check("one that ends is posted once", d.post_discord_sessions() == 1
      and d.worker.jobs.count(EDO.DISCORD_TAG) == 2, d.worker.jobs)
check("and not again", d.post_discord_sessions() == 0)
built = method("SettingsWindow", "__init__")
check("Settings has a Discord section, the address behind dots",
      '"discord_webhook", "Webhook URL"' in built and "secret=True" in
      built[built.index('"discord_webhook"'):built.index('"discord_webhook"') + 200])
check("with the two switches and a test button",
      '"discord_post_finds"' in built and '"discord_post_sessions"' in built
      and "command=self.test_discord" in built)
saving = method("SettingsWindow", "save")
check("and Save refuses an address that is not a webhook",
      "EDO.discord_hook_ok(hook)" in saving)
check("a marked find is posted from the one place finds are recorded",
      "self.post_discord_find(record)" in method("EDSMT", "mark_deposit"))
check("ended sessions are looked for every tick",
      "self.post_discord_sessions()" in method("EDSMT", "tick"))

# ---------------------------------------------------------------------------
print("== rigs survive a restart (#193) ==")
RR = 1_800_000.0
SPOT = (12.5, -45.5)
class _State:
    def __init__(self, lat, lon, heading=0.0, rhino=True):
        self.lat, self.lon, self.heading = lat, lon, heading
        self.radius_m = RR
        self.has_position = True
        self.in_rhino = self.in_srv = rhino
def rig_app(offset=0, **extra):
    r = A.EDSMT.__new__(A.EDSMT)
    r.said, r.flashes, r.redraws = [], [], []
    r.say = lambda t, c=None: r.said.append((t, c))
    r.flash = lambda t, d="", c=None: r.flashes.append((t, d, c))
    r.settings = dict(A.DEFAULT_SETTINGS, rig_offset_m=offset, **extra)
    r.here = lambda: ("Ega", "Ega 1")
    r.redraw = lambda: r.redraws.append(True)
    r.sound_alarm = lambda: None
    r.rigs_at, r._rigs_warned = None, False
    r.game = _State(*SPOT)
    return r
rigfile = os.path.join(TMP, "rigs-test.json")
check("no file, no rigs", A.load_rigs(rigfile) is None)
r = rig_app()
r.drop_rigs()
r.game = _State(*SV.destination(SPOT[0], SPOT[1], 90, 200, RR))
r.drop_rigs()
check("two rigs down", len(r.rigs_at["rigs"]) == 2)
check("written to disk", A.save_rigs(r.rigs_at, rigfile))
back = A.load_rigs(rigfile)
check("and read back exactly", back and [x["n"] for x in back["rigs"]] == [1, 2]
      and back["system"] == "Ega" and abs(back["rigs"][1]["lat"] - r.rigs_at["rigs"][1]["lat"]) < 1e-12)
with open(rigfile, "w") as fh:
    fh.write("{not json")
check("a broken file is no rigs, not a crash", A.load_rigs(rigfile) is None)
with open(rigfile, "w") as fh:
    json.dump({"rigs_at": {"system": "Ega", "body": "Ega 1",
                           "rigs": [{"n": "x"}, {"n": 2, "lat": 1, "lon": 2}]}}, fh)
check("a rig without a position is dropped, the good one kept",
      [x["n"] for x in A.load_rigs(rigfile)["rigs"]] == [2])
p_app = rig_app()
p_app.rigs_at = r.rigs_at
p_app._rigs_saved = None
saved_to = []
real_save = A.save_rigs
A.save_rigs = lambda rigs_at, path=None: saved_to.append(rigs_at) or True
check("the app writes them when they change", p_app.persist_rigs() and len(saved_to) == 1)
check("and not while they do not", p_app.persist_rigs() is False and len(saved_to) == 1)
p_app.rigs_at = None
check("and when they are all up", p_app.persist_rigs() and saved_to[-1] is None)
A.save_rigs = real_save
init = method("EDSMT", "__init__")
check("starting up reads them back", "self.rigs_at = load_rigs()" in init)
check("every tick writes them if they moved", "self.persist_rigs()" in method("EDSMT", "tick"))
fresh = rig_app()
fresh.rigs_at = back = {"system": "Ega", "body": "Ega 1",
                        "rigs": [{"n": 1, "lat": 12.5, "lon": -45.5, "at": 0}]}
fresh.here = lambda: ("", "")
fresh.watch_rigs(None)
check("with nobody yet saying where we are, the rigs read off disk are kept",
      fresh.rigs_at is back)
fresh.here = lambda: ("Ega", "Ega 2")
fresh.watch_rigs(None)
check("on another body they are let go, as before", fresh.rigs_at is None)

print("== where a rig really lands (#195) ==")
lat2, lon2 = SV.destination(SPOT[0], SPOT[1], 90.0, 1000.0, RR)
check("the destination maths: 1 km east is 1 km away",
      abs(SV.surface_range_m(SPOT[0], SPOT[1], lat2, lon2, RR) - 1000.0) < 0.01)
check("and due east", abs(SV.bearing_deg(SPOT[0], SPOT[1], lat2, lon2) - 90.0) < 0.01)
o = rig_app(offset=7)
o.game = _State(SPOT[0], SPOT[1], heading=0.0)
spot = o.rig_spot(o.game)
check("facing north, the rig is 7 m behind: south",
      abs(SV.surface_range_m(SPOT[0], SPOT[1], spot[0], spot[1], RR) - 7.0) < 0.01
      and abs(SV.bearing_deg(SPOT[0], SPOT[1], spot[0], spot[1]) - 180.0) < 0.5, spot)
o.drop_rigs()
check("and that is where it is marked",
      abs(o.rigs_at["rigs"][0]["lat"] - spot[0]) < 1e-12)
check("with no offset it is where the cockpit is",
      rig_app(offset=0).rig_spot(_State(*SPOT)) == SPOT)
nohead = _State(*SPOT); nohead.heading = None
check("and without a heading too", rig_app(offset=7).rig_spot(nohead) == SPOT)
check("the default is the measured 7 m", A.DEFAULT_SETTINGS["rig_offset_m"] == 7.0)

print("== your own rigs: too close, and pick it up (#194) ==")
c = rig_app()
c.drop_rigs()
c.game = _State(*SV.destination(SPOT[0], SPOT[1], 0, 40, RR))
cue = c.rig_cue(now=time.time())
check("40 m from rig 1 the boxes say TOO CLOSE", cue and cue["kind"] == "too_close"
      and cue["text"].startswith("TOO CLOSE TO RIG 1"), cue)
c.drop_rigs()
check("dropping one there anyway is marked, and warned about",
      len(c.rigs_at["rigs"]) == 2 and any("CLOSE TO RIG 1" in f[0] for f in c.flashes),
      c.flashes)
c.game = _State(*SV.destination(SPOT[0], SPOT[1], 180, 500, RR))
check("500 m away there is no cue", c.rig_cue(now=time.time()) is None)
c.game = _State(*SV.destination(SPOT[0], SPOT[1], 0, 3, RR))
check("back at a rig just dropped, it does not say COLLECT",
      (c.rig_cue(now=time.time()) or {}).get("kind") != "collect")
check("but once it has been working a while, it does",
      (c.rig_cue(now=time.time() + 600) or {}).get("kind") == "collect")
check("in cyan, the one cue that is good news",
      (c.rig_cue(now=time.time() + 600) or {}).get("colour") == A.CYAN)
c.game.in_rhino = c.game.in_srv = False
check("in the ship or on foot there is no rig cue", c.rig_cue(now=time.time() + 600) is None)
c.game.in_rhino = c.game.in_srv = True
c.gravity_here = lambda: 3.0
c.watcher = type("W", (), {"in_srv": True, "low_fuel": False})()
check("a rig cue comes before high gravity on the red bar",
      (c.overlay_hazard() or {}).get("kind") in ("collect", "too_close"))

print("== the SRV's fuel (#207) ==")
f = rig_app()
f.rigs_at = None
f.gravity_here = lambda: 0.5
f.watcher = type("W", (), {"in_srv": True, "low_fuel": True})()
check("the game's low-fuel flag in the SRV puts SRV FUEL LOW on the boxes",
      (f.overlay_hazard() or {}).get("text", "").startswith("SRV FUEL LOW"))
f.watcher.in_srv = False
check("and not in the ship", f.overlay_hazard() is None)
status_dir = os.path.join(TMP, "status"); os.makedirs(status_dir)
with open(os.path.join(status_dir, "Status.json"), "w") as fh:
    json.dump({"timestamp": "2026-10-07T20:00:00Z", "event": "Status",
               "Flags": (1 << 26) | (1 << 19) | (1 << 21), "Latitude": 1.0,
               "Longitude": 2.0, "Heading": 10, "BodyName": "Ega 1",
               "PlanetRadius": 1800000.0}, fh)
sw = JN.JournalWatcher(status_dir)
sw.poll()
check("the reader takes the flag off Status.json", sw.low_fuel is True and sw.in_srv)

print("== a Rhino docking takes its own rigs off the scope (#196) ==")
d2 = rig_app()
d2._rhino_now = lambda: 11
d2.drop_rigs()
d2._rhino_now = lambda: 22
d2.game = _State(*SV.destination(SPOT[0], SPOT[1], 90, 300, RR))
d2.drop_rigs()
check("two Rhinos, a rig each", sorted(x["srv"] for x in d2.rigs_at["rigs"]) == [11, 22])
d2.rigs_on_vehicle({"event": "SRVDock", "srv_id": 11, "player": True})
check("Rhino 11 docks: its rig goes, the other Rhino's stays",
      [x["srv"] for x in d2.rigs_at["rigs"]] == [22], d2.rigs_at)
off = rig_app(rigs_clear_on_dock=False)
off.drop_rigs()
check("switched off in Settings, nothing is cleared",
      off.rigs_on_vehicle({"event": "SRVDock", "player": True}) is False
      and len(off.rigs_at["rigs"]) == 1)
check("a crewmate docking is not you", rig_app().rigs_on_vehicle(
    {"event": "SRVDock", "player": False}) is False)
check("the books' notes reach it", "self.rigs_on_vehicle(note)" in method("EDSMT", "tick"))
built = method("SettingsWindow", "__init__")
check("Settings has the offset and the switch", '"rig_offset_m"' in built
      and '"rigs_clear_on_dock"' in built)
saving = method("SettingsWindow", "save")
check("and reads the offset as plain metres, not km",
      "parse_metres" not in saving[saving.index("rig_offset_m"):saving.index("rig_offset_m") + 400])

print("== tonnes an hour (#210) ==")
tph = SV.tonnes_per_hour({"started": "2026-10-07T18:00:00Z", "ended": "2026-10-07T20:00:00Z",
                          "mined": "Monazite:96;Painite:24"})
check("120 t in two hours is 60 t an hour", abs(tph - 60.0) < 1e-9, tph)
check("no time, no rate", SV.tonnes_per_hour({"mined": "Gold:5"}) == 0.0)
check("Earnings has the column, after Cr/hr", A.RUN_HEADERS.index("t/hr")
      == A.RUN_HEADERS.index("Cr/hr") + 1)
ew = A.EarningsWindow.__new__(A.EarningsWindow)
cells = ew._run_row({"started": "2026-10-07T18:00:00Z", "ended": "2026-10-07T20:00:00Z",
                     "closed": "2026-10-07T20:00:00Z", "mined": "Monazite:96;Painite:24"})
check("one cell per heading", len(cells) == len(A.RUN_HEADERS), (len(cells), len(A.RUN_HEADERS)))
check("reading 60.0 t", cells[A.RUN_HEADERS.index("t/hr")][0] == "60.0 t",
      cells[A.RUN_HEADERS.index("t/hr")])
check("and the Discord summary carries it", any(
    f["name"] == "t/hr" and f["value"] == "60.0" for f in EDO.discord_session_message(
        {"started": "2026-10-07T18:00:00Z", "ended": "2026-10-07T20:00:00Z",
         "mined": "Monazite:96;Painite:24"})["embeds"][0]["fields"]))

print("== the overlay off in the Rhino: say where it is (#144) ==")
h = rig_app()
h.settings["overlay_enabled"] = False
saved_settings = []
real_ss = A.save_settings
A.save_settings = lambda data: saved_settings.append(dict(data)) or True
check("in the Rhino with the overlay off, it says how to turn it on",
      h.overlay_hint() and "Alt+0" in h.flashes[-1][1] and "Overlay button" in h.said[-1][0],
      (h.flashes, h.said))
check("once a session", h.overlay_hint() is False)
check("and counts the sessions told", saved_settings[-1]["overlay_hint_shown"] == 1)
h2 = rig_app(); h2.settings.update(overlay_enabled=False, overlay_hint_shown=A.OVERLAY_HINTS)
check("after %d sessions it stops" % A.OVERLAY_HINTS, h2.overlay_hint() is False and not h2.flashes)
h3 = rig_app(); h3.settings["overlay_enabled"] = True
check("with the overlay on there is nothing to say", h3.overlay_hint() is False)
h4 = rig_app(); h4.settings["overlay_enabled"] = False; h4.game.in_rhino = h4.game.in_srv = False
check("nor in the ship", h4.overlay_hint() is False)
A.save_settings = real_ss
check("it is asked every tick, with the Rhino-only overlay",
      "self.overlay_hint()" in method("EDSMT", "follow_vehicle_overlay"))

print("== a note on every control (#166) ==")
import ast as _ast
_tree = _ast.parse(SRC)
CONTROLS = {"CTkButton", "CTkComboBox", "CTkEntry", "CTkSwitch", "CTkCheckBox",
            "CTkOptionMenu", "CTkSegmentedButton"}
def untipped(cls_name, wanted=None):
    cls = next(n for n in _tree.body if isinstance(n, _ast.ClassDef) and n.name == cls_name)
    missing = []
    for fn in cls.body:
        if not isinstance(fn, _ast.FunctionDef) or (wanted and fn.name not in wanted):
            continue
        parents = {}
        for node in _ast.walk(fn):
            for child in _ast.iter_child_nodes(node):
                parents[child] = node
        tipped = {_ast.unparse(n.args[0]) for n in _ast.walk(fn)
                  if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Name)
                  and n.func.id == "tip" and n.args}
        for node in _ast.walk(fn):
            if not (isinstance(node, _ast.Call) and isinstance(node.func, _ast.Attribute)
                    and node.func.attr in CONTROLS):
                continue
            up = parents.get(node)
            if isinstance(up, _ast.Call) and isinstance(up.func, _ast.Name) and up.func.id == "tip":
                continue
            if isinstance(up, _ast.Assign) and any(_ast.unparse(t) in tipped for t in up.targets):
                continue
            missing.append("%s.%s line %d" % (cls_name, fn.name, node.lineno))
    return missing
main = untipped("EDSMT", {"_build", "_rail", "_telemetry"})
check("every control in the main window has a note", not main, main)
settings_missing = untipped("SettingsWindow")
check("and every control in Settings", not settings_missing, settings_missing)
check("Settings rows take their note from the key they save, so a new row cannot "
      "miss one quietly",
      all("SETTING_TIPS.get(key)" in method("SettingsWindow", n)
          for n in ("_switch", "_entry", "_choice", "_colour")))
keys_used = set(re.findall(r'self\._(?:switch|entry|choice|colour)\(body, "([a-z_0-9]+)"', SRC))
others = [m for name in ("FindWindow", "EarningsWindow", "SitesWindow", "LandWindow",
                         "EditLocationWindow", "EditWindow", "WelcomeWindow", "TourWindow")
          for m in untipped(name)]
check("and in every other window - Find, Earnings, My sites, Where to land, the "
      "edit windows, the first run and the tour", not others, others)
check("and every key Settings shows has its note written",
      not (keys_used - set(A.SETTING_TIPS)), sorted(keys_used - set(A.SETTING_TIPS)))
check("notes can be switched off", "show_tips" in A.DEFAULT_SETTINGS
      and '"show_tips"' in method("SettingsWindow", "__init__"))
check("the tour shows the window round once, for new and old commanders alike",
      "self.app.start_tour" in method("WelcomeWindow", "answer")
      and "self.start_tour" in method("EDSMT", "__init__"))
check("every step of the tour points at something the window has",
      all(spec is None or (spec if isinstance(spec, str) else spec[0]) in SRC
          for spec, _t, _w in A.TOUR_STEPS))

tw = A.EDSMT.__new__(A.EDSMT)
tw.settings = dict(A.DEFAULT_SETTINGS)
tw.touring = None
waits = []
tw.after = lambda ms, fn: waits.append(ms)
real_front = A.OV.foreground_is_game
A.OV.foreground_is_game = lambda: True
check("with the game in front at start-up, the tour waits rather than open over it",
      tw.start_tour() is False and waits == [A.TOUR_WAIT_MS], waits)
A.OV.foreground_is_game = real_front
tw.settings["tour_done"] = True
check("seen once, it does not come back by itself", tw.start_tour() is False)

print("== installed under C:\\EDTools\\RadioRaxxla, and moved there (#167) ==")
ISS = open(os.path.join(os.path.dirname(HERE), "build", "installer.iss"), encoding="utf-8").read()
check("a new install goes to C:\\EDTools\\RadioRaxxla\\EDSMT",
      "DefaultDirName={sd}\\EDTools\\RadioRaxxla\\EDSMT" in ISS)
check("in a Start menu folder called Radio Raxxla", "DefaultGroupName=Radio Raxxla" in ISS)
check("an update moves an older install rather than staying put",
      "UsePreviousAppDir=no" in ISS and "UsePreviousGroup=no" in ISS)
check("the old copy is found from its uninstall entry, same AppId",
      "B4E7A1C9-3D62-4F08-9A15-7C2E5B8D4610}_is1" in ISS and "'Inno Setup: App Path'" in ISS)
code = ISS[ISS.index("\n[Code]"):]
check("only after the new one is in", "ssPostInstall" in code)
check("and only the files the old Setup put there, by name",
      "DelTree(Base + '_internal'" in code and "DeleteFile(Base + '{#ExeName}')" in code
      and "DelTree(Dir" not in code and "DelTree(OldDir" not in code)
check("the old folder goes only if that leaves it empty", "RemoveDir(Dir);" in code)
_code_only = "\n".join(l for l in code.splitlines() if not l.strip().startswith("//"))
check("never the finds and settings", "localappdata" not in _code_only.lower()
      and "{userappdata}" not in _code_only)
check("the old Start menu entries go too", "{userprograms}\\EDSMT" in code)
check("and nothing is done when it is already where it belongs",
      "CompareText(RemoveBackslashUnlessRoot(OldDir)" in code)

print("== how a deposit was rigged, shared (#218) ==")
class _LayoutComm:
    can_read = ready = True
    def __init__(self): self.sent, self.asked = [], []
    def share_layout(self, cmdr, layout): self.sent.append(layout); return True
    def rig_layouts(self, system, planet, spot): self.asked.append((system, planet, spot)); return True
L = rig_app()
L.community = _LayoutComm()
L.watcher = type("W", (), {"cmdr": "Jameson"})()
L.signal = lambda: "3"
L.rig_label = lambda r: str(r["n"])
L.rig_event = lambda *a: None
L.refresh_rigs_note = lambda: None
L.clear_rig_alarm = lambda: None
L._rhino_now = lambda: 7
for k, metres in enumerate((0, 90, 180)):
    L.game = _State(*SV.destination(SPOT[0], SPOT[1], 90, metres, RR))
    L.drop_rigs(k + 1)
L.rig_up(1)
L.rig_up(2)
check("rigs picked up one by one leave nothing to share until the last",
      L.community.sent == [])
L.rig_up(3)
check("the last one up shares how all three went down", len(L.community.sent) == 1
      and len(L.community.sent[0]["placed"]) == 3, L.community.sent)
sent = L.community.sent[0]
check("on the deposit's signal, with the rig numbers",
      sent["spot"] == "3" and sorted(p[2] for p in sent["placed"]) == [1, 2, 3]
      and sent["system"] == "Ega" and sent["planet"] == "Ega 1", sent)
check("a layout is sent once", L.share_rig_layout(
    [{"n": 1, "lat": sent["placed"][0][0], "lon": sent["placed"][0][1]},
     {"n": 2, "lat": sent["placed"][1][0], "lon": sent["placed"][1][1]},
     {"n": 3, "lat": sent["placed"][2][0], "lon": sent["placed"][2][1]}]) is False
      or len(L.community.sent) == 1)
check("one rig is not a layout", L.share_rig_layout([{"n": 1, "lat": 1.0, "lon": 2.0}]) is False)
L.rig_plan = {"system": "Ega", "body": "Ega 1", "spacing": 78.0, "area_m2": 50000.0,
              "pins": [{"n": 1, "lat": 12.5, "lon": -45.5}, {"n": 2, "lat": 12.501, "lon": -45.5}],
              "outline": [(12.5 + i * 1e-5, -45.5) for i in range(1000)]}
lay = L.rig_layout([{"n": 1, "lat": 12.5, "lon": -45.5}, {"n": 2, "lat": 12.501, "lon": -45.5}])
check("with the planner's edge and pins when it was used",
      lay["spacing"] == 78.0 and len(lay["pins"]) == 2 and lay["area_m2"] == 50000.0)
check("the edge thinned to what the server takes", 0 < len(lay["outline"]) <= A.LAYOUT_OUTLINE_MAX,
      len(lay["outline"]))
L.rig_plan = None
check("the layouts for the signal you are on are asked for", L.follow_layouts(now=100.0)
      and L.community.asked == [("Ega", "Ega 1", "3")])
check("and not again straight away", L.follow_layouts(now=200.0) is False)
L.redraw = lambda: None
best = {"system": "Ega", "planet": "Ega 1", "spot": "3", "rigs": 6, "spacing": 78.0,
        "uploader": "CMDR Rigger", "outline": [[12.5, -45.5], [12.501, -45.5]],
        "placed": [[12.5 + i * 0.0006, -45.5, i + 1] for i in range(6)]}
L.take_layouts(True, json.dumps({"count": 1, "layouts": [best]}))
plan = L.shared_plan()
check("the best one shows as pins when you have no plan of your own",
      plan and plan["shared"] and len(plan["pins"]) == 6 and plan["by"] == "CMDR Rigger", plan)
L.game = _State(*SPOT)
marks = L.plan_marks()
check("on the scope, marked as shared and whose", marks and marks["shared"]
      and marks["by"] == "CMDR Rigger" and len(marks["pins"]) == 6, marks)
L.rig_plan = {"system": "Ega", "body": "Ega 1", "spacing": 78.0,
              "pins": [{"n": 1, "lat": 12.5, "lon": -45.5}], "outline": []}
check("your own plan comes first", not (L.plan_marks() or {}).get("shared"))
L.rig_plan = None
L.settings["show_shared_layouts"] = False
check("and the setting turns shared ones off", L.shared_plan() is None)
check("Settings has the switch", '"show_shared_layouts"' in method("SettingsWindow", "__init__"))
check("the answer is routed", "self.take_layouts(ok, message)" in method("EDSMT", "collect_results"))

print("== Settings in tabs (#142) ==")
built = method("SettingsWindow", "__init__")
check("seven tabs, in reading order", A.SETTINGS_TABS ==
      ("Basics", "Overlay", "Keys", "Rigs", "Sharing", "Your data", "About"))
check("built as a tab view, a scroller in each", "ctk.CTkTabview(" in built
      and "self.tabs.add(name)" in built and "ctk.CTkScrollableFrame(" in built)
sections = re.findall(r'body = self\.pages\["([^"]+)"\]\n\s+self\._section\(body, "([^"]+)"', built)
placed = dict((title, tab) for tab, title in sections)
check("every section is put in a tab", len(sections) == built.count("self._section(body,"),
      (len(sections), built.count("self._section(body,")))
check("where it belongs", placed.get("Hotkeys") == "Keys" and placed.get("Discord") == "Sharing"
      and placed.get("In-game overlay") == "Overlay" and placed.get("Your finds") == "Your data"
      and placed.get("Rigs") == "Rigs" and placed.get("About EDSMT") == "About", placed)


print("== rigs past 6 km are forgotten, and out of the Rhino nothing warns ==")
w = rig_app()
w.drop_rigs()
w.clear_rig_alarm = lambda: None
w.show_rig_alarm = lambda *a: w.flashes.append(("ALARM", "", None))
w.refresh_rigs_note = lambda: None
w.rigs_after_relog = lambda *a: False
w._rhino_now = lambda: None
w._same_rhino = lambda rig, rhino: True
ship = _State(*SV.destination(SPOT[0], SPOT[1], 90, 4900, RR), rhino=False)
seen = w.watch_rigs(ship)
check("4.9 km away in the ship: no last warning, no too far",
      seen and not seen["final"] and not seen["far"]
      and not any(f[0] == "ALARM" for f in w.flashes), seen)
check("and the rig is still marked", w.rigs_at and len(w.rigs_at["rigs"]) == 1)
w.watch_rigs(_State(*SV.destination(SPOT[0], SPOT[1], 90, 6100, RR), rhino=False))
check("past 6 km from the ship the rig is forgotten", w.rigs_at is None)
check("and it says so", any("forgotten" in s[0] for s in w.said), w.said)

print("== a rig on somebody else's deposit is on their commodity ==")
k = rig_app()
k.store = type("S", (), {"at": lambda self, s, b: []})()
k.fields = {"commodity": type("B", (), {"get": lambda self: "Bastnasite"})()}
k.game.detected_type = ""
k.shared = {("ega", "ega 1"): {"at": 0, "rows": [
    {"commodity": "Monazite", "lat": SPOT[0], "lon": SPOT[1], "shared": True}]}}
check("a shared find under the Rhino names the rig",
      k.rig_commodity(k.game, "Ega", "Ega 1") == "Monazite")
k.shared = {}
k.selected = {"commodity": "Alexandrite", "lat": SPOT[0], "lon": SPOT[1], "shared": True}
check("so does the one you picked", k.rig_commodity(k.game, "Ega", "Ega 1") == "Alexandrite")

print("== double-click a rig to put it right ==")
e = rig_app()
e.persist_rigs = lambda: True
e.refresh_rigs_note = lambda: None
e.drop_rigs()
e.game = _State(*SV.destination(SPOT[0], SPOT[1], 90, 200, RR))
e.drop_rigs()
two = e.rigs_at["rigs"][1]
check("a map square finds its rig", e.rig_for(e.rig_label(two)) is two)
check("its commodity can be set", e.set_rig_commodity(two, "monazite")
      and two["commodity"] == "Monazite")
check("and it can be picked up on its own", e.pick_up_rig(two)
      and len(e.rigs_at["rigs"]) == 1)
check("the map hands a double-clicked rig over",
      "self.on_edit_rig(mark)" in method("PlanView", "_double_clicked")
      and "on_edit_rig=self.edit_rig" in SRC)
check("the editor exists", hasattr(A, "RigEditWindow"))

print("== the suggestion list goes away ==")
check("a click elsewhere in the window shuts it",
      "_clicked_elsewhere" in method("Suggest", "_build"))
check("a second click in the box shuts it", "return self.hide()" in method("Suggest", "_clicked"))
check("no wrong note left on the mark boxes",
      SRC.count("Every dated copy of your settings, newest first.") == 1)

print("== staff can take a wrong find off the map ==")
check("the client can ask", callable(getattr(EDO.CommunityClient, "remove", None))
      if hasattr(EDO, "CommunityClient") else "def remove(" in open(EDO.__file__).read())
check("Find offers it to staff", "self.remove_find(r)" in SRC
      and "def _removable" in SRC and '"remove"' in SRC)


print()
print("FAILURES: %d" % len(fails))
for f in fails:
    print("  - " + f)
sys.exit(1 if fails else 0)
