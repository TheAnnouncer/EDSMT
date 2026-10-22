"""What 1.10035 adds on the way out: map pictures, the Discord summary v2,
the ship's hold card, the support bundle.

Driven without a display. Every commander, ship and station is made up; the
numbers have the shape of real sessions (the Rhino's hold at 72 t, crew
wages a fixed share of profit, the ship's hold stated only after DockSRV,
CargoCapacity that changes whenever the racks do).

    python tests/test_110035_output.py
"""
import os, sys, json, re, io, time, zipfile, tempfile, struct, threading
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "stubs"))
import _ctkstub  # noqa
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="edsmt-110035-output-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
import edsmt as A, survey as SV, journal as JN, edonline as EDO  # noqa
import planview as PV, overlay as OV  # noqa
import mapimage as MI, shiphold as SH, supportbundle as SB, sessionledger as SL  # noqa

REPO = os.path.dirname(HERE)
fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)

NOW = time.time()
def stamp(ago_s=0, base=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime((base or NOW) - ago_s))

# The app writes pictures and logs to its data folder; here it is ours.
DATA = os.path.join(TMP, "data")
os.makedirs(DATA)
A.DATA_DIR = DATA

HOOK_ID, HOOK_TOKEN = "123456789012345678", "T0kenSecretValue" + "x" * 52
HOOK = "https://discord.com/api/webhooks/%s/%s" % (HOOK_ID, HOOK_TOKEN)
INARA_KEY = "inara-key-0123456789abcdef"
COMMUNITY_TOKEN = "community-token-ZZZZ9999"
WING = "QW7ERT"
MESSAGE_ID = "998877665544332211"


def write_journal(folder, events, name):
    with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")


def append_journal(folder, events, name):
    with open(os.path.join(folder, name), "a", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")


def deposit(i, commodity, range_m, bearing, rigs="", amount="High", location="3"):
    return {"range_m": range_m, "bearing": bearing,
            "deposit": {"id": "d%d" % i, "commodity": commodity, "rigs": rigs,
                        "amount": amount, "density": "High", "location": location,
                        "system": "Col 1 Sector AA-A c1-1", "body": "Col 1 Sector AA-A c1-1 BC 2",
                        "lat": "12.5", "lon": "-45.5"}}


COLOURS = {"Painite": "#37c6d4", "Iridium": "#ff7a18", "Grandidierite": "#8ad14b"}
def colour(name): return COLOURS.get(name, "#e8d9c8")

SURVEY = {"scan_m": 80, "points": [(0, 0), (50, 50), (100, 100), (-80, 40)],
          "centre": (60.0, 60.0), "border_m": 400.0, "rings": [200.0], "percent": 62, "gaps": []}
RIGS = {"limit_m": 600, "rigs": [
    {"n": 1, "east": 50, "north": 80, "commodity": "Painite", "range_m": 94},
    {"n": 2, "east": -100, "north": 150, "commodity": "Iridium", "range_m": 180}]}
ROWS = [deposit(1, "Painite", 120, 40, "3"), deposit(2, "Painite", 150, 70, "2"),
        deposit(3, "Iridium", 220, 200, "1", "Depleted"), deposit(4, "Grandidierite", 90, 310, "4"),
        deposit(5, "Painite", 300, 10, "")]
TRAIL = [(0, 0), (30, 40), (60, 90), (120, 100)]

# ---------------------------------------------------------------------------
print("== 1. map pictures ==")
ok, why = MI.pillow_status()
check("Pillow is here, so pictures can be made", ok and why == "", why)
import PIL
_v = tuple(int(x) for x in re.findall(r"\d+", PIL.__version__)[:2])
check("and it is a version requirements.txt allows", (10, 1) <= _v < (13, 0), PIL.__version__)

image, scene = MI.render_map(ROWS, system="Col 1 Sector AA-A c1-1", body="Col 1 Sector AA-A c1-1 BC 2",
                             signal="3", anchor=(60.0, 60.0), survey=SURVEY, rigs=RIGS, trail=TRAIL,
                             cmdr="Jameson", when=NOW, version="1.10035", colour=colour)
check("the picture is the size asked for", image.size == MI.SIZE and image.mode == "RGB", image.size)
check("and is a picture, not a blank: many colours drawn", len(image.getcolors(1 << 20) or []) > 40)
check("every deposit is on it, none lost off the edge", len(scene["markers"]) == 5 and scene["beyond"] == 0,
      (len(scene["markers"]), scene["beyond"]))
check("the rigs are numbered on it", [m["n"] for m in scene["rig_marks"]] == [1, 2])
check("the swept ground, the border and the trail are in the scene",
      len(scene["swept"]) == 4 and scene["border"] and len(scene["trail"]) == 4)
check("the scale bar is a ring step, and its length is in pixels",
      scene["scale"]["metres"] in PV.NICE_STEPS_M and scene["scale"]["px"] > 20, scene["scale"])
check("system, body, signal and swept percentage are written on it",
      any("Col 1 Sector AA-A c1-1 / Col 1 Sector AA-A c1-1 BC 2   signal 3" in t for t in scene["texts"])
      and any("swept 62%" in t for t in scene["texts"]), scene["texts"])
check("the date is on it, in UTC", any(re.search(r"\d+ [A-Z][a-z]{2} 20\d\d \d\d:\d\d UTC", t) for t in scene["texts"]),
      scene["texts"])
check("the footer names the app and the version", "EDSMT 1.10035 - radioraxxla.com/EDSMT" in scene["texts"])
check("the best patch is ringed and says how many rigs",
      scene["patch"] and scene["patch"]["rigs"] == 10 and any(t.startswith("BEST PATCH  10R") for t in scene["texts"]))

# A depleted deposit is a ring, an intact one is a disc: probe the pixel in the middle.
depleted = next(m for m in scene["markers"] if m["hollow"])
intact = next(m for m in scene["markers"] if m["commodity"] == "Grandidierite")
def near(pixel, hexcolour, tol=14):
    want = tuple(int(hexcolour[i:i + 2], 16) for i in (1, 3, 5))
    return all(abs(a - b) <= tol for a, b in zip(pixel, want))
check("a depleted deposit is drawn hollow (the middle shows the ground)",
      near(image.getpixel((int(depleted["x"]), int(depleted["y"]))), MI.PLOT)
      and not near(image.getpixel((int(depleted["x"]), int(depleted["y"]))), depleted["colour"]),
      image.getpixel((int(depleted["x"]), int(depleted["y"]))))
check("and an intact one is filled in its commodity's colour",
      near(image.getpixel((int(intact["x"]), int(intact["y"]))), intact["colour"]),
      image.getpixel((int(intact["x"]), int(intact["y"]))))
check("the depleted one's own outline is its colour, not the ground's",
      any(near(image.getpixel((int(depleted["x"] + dx), int(depleted["y"] + dy))), depleted["colour"], 40)
          for dx in range(-8, 9) for dy in range(-8, 9)))

# Three fixtures: full, only rigs, forty deposits some far off.
_rigs_only, _s2 = MI.render_map([], system="Ega", body="Ega 1", rigs=RIGS, colour=colour, when=NOW)
check("a map with only rigs on it still draws", _rigs_only.size == MI.SIZE and len(_s2["rig_marks"]) == 2)
_empty, _s3 = MI.render_map([], system="Ega", body="Ega 1", colour=colour, when=NOW)
check("a map with nothing on it still draws, and says nothing is there",
      _empty.size == MI.SIZE and _s3["markers"] == [] and any("0 deposits" in t for t in _s3["texts"]), _s3["texts"])
many = [deposit(i, ["Painite", "Iridium", "Grandidierite"][i % 3], 60 + i * 35, (i * 47) % 360, str(1 + i % 4))
        for i in range(40)]
_many, _s4 = MI.render_map(many, system="Ega", body="Ega 1", signal="3", colour=colour, when=NOW)
check("forty deposits are drawn without losing any that fit",
      len(_s4["markers"]) + _s4["beyond"] <= 40 and len(_s4["markers"]) >= 10, (len(_s4["markers"]), _s4["beyond"]))
check("and the legend counts them by commodity", sum(e["finds"] for _n, e in _s4["legend"]) == len(_s4["markers"]))

# The commander's name: only when it is given.
_plain = MI.build_scene(ROWS, system="Ega", body="Ega 1", signal="3", cmdr="", colour=colour, when=NOW)
_named = MI.build_scene(ROWS, system="Ega", body="Ega 1", signal="3", cmdr="Jameson", colour=colour, when=NOW)
check("no commander's name is drawn when none is given",
      not any("Jameson" in t for t in _plain["texts"]) and "Jameson" not in json.dumps(_plain["sub"]))
check("and it is drawn when one is", any("CMDR Jameson" in t for t in _named["texts"]))

# Files.
check("the file name is system, body, signal and a date, safe on Windows",
      re.fullmatch(r"Col_1_Sector_AA_A_c1_1_Col_1_Sector_AA_A_c1_1_BC_2_3_\d{8}-\d{4}\.png",
                   MI.picture_name("Col 1 Sector AA-A c1-1", "Col 1 Sector AA-A c1-1 BC 2", "3", NOW)),
      MI.picture_name("Col 1 Sector AA-A c1-1", "Col 1 Sector AA-A c1-1 BC 2", "3", NOW))
check("a name with characters Windows refuses is cleaned",
      not re.search(r'[\\/:*?"<>|]', MI.picture_name('a:b/c', 'd*e?', '<1>', NOW)))
path = MI.save_picture(image, os.path.join(TMP, "p", "one.png"))
raw = open(path, "rb").read()
check("it is saved as a PNG, well under Discord's limit",
      raw[:8] == b"\x89PNG\r\n\x1a\n" and len(raw) < MI.MAX_BYTES, len(raw))
small = MI.png_bytes(image, limit=30000)
check("a picture too large is shrunk until it fits", len(small) <= 30000 and len(small) < len(raw),
      (len(small), len(raw)))
check("the clipboard form is a DIB: header 40, the picture's own size",
      struct.unpack("<I", MI.dib_bytes(image)[:4])[0] == 40
      and struct.unpack("<ii", MI.dib_bytes(image)[4:12]) == MI.SIZE, struct.unpack("<ii", MI.dib_bytes(image)[4:12]))
if os.name != "nt":
    ok, why = MI.copy_to_clipboard(image)
    check("off Windows, copying says so and points at the file", not ok and "Windows" in why, why)
for n in range(5):
    p = os.path.join(TMP, "p", "Ega_1_3_20261001-%04d.png" % n)
    MI.save_picture(image, p)
    os.utime(p, (NOW - 1000 + n, NOW - 1000 + n))
open(os.path.join(TMP, "p", "keep-me.png"), "wb").write(b"x")
check("old pictures are tidied to the newest N, and only ours",
      MI.tidy_pictures(os.path.join(TMP, "p"), keep=3) == 2
      and os.path.exists(os.path.join(TMP, "p", "keep-me.png"))
      and not os.path.exists(os.path.join(TMP, "p", "Ega_1_3_20261001-0000.png"))
      and os.path.exists(os.path.join(TMP, "p", "Ega_1_3_20261001-0004.png")))

# Pillow missing: the app keeps working and says why.
class _Plan:
    pass

def make_plan(rows=ROWS):
    plan = _Plan()
    plan.rows, plan.survey, plan.rigs = list(rows), SURVEY, RIGS
    plan.signal, plan.signal_at, plan.trail = "3", (60.0, 60.0), TRAIL
    return plan

class _Hold:
    pass

def make_app(settings=None):
    app = A.EDSMT.__new__(A.EDSMT)
    app.settings = dict(A.DEFAULT_SETTINGS, last_system="Col 1 Sector AA-A c1-1",
                        last_body="Col 1 Sector AA-A c1-1 BC 2", **(settings or {}))
    app.game = None
    app.watcher = type("W", (), {"cmdr": "Jameson", "in_srv": True})()
    app.plan = make_plan()
    app.said = []
    app.say = lambda text, colour=None: app.said.append(str(text))
    app.trouble = lambda stage, exc: app.said.append("TROUBLE %s %s" % (stage, exc))
    app._boot_at = NOW - 3600
    app._pictures = []
    return app

app = make_app()
result = app.picture_now(when=NOW)
check("the app draws the map it is showing and saves it in pictures\\",
      result["image"] is not None and result["path"].startswith(os.path.join(DATA, "pictures"))
      and os.path.isfile(result["path"]), result)
check("with the commander's name, because sharing the name is on",
      any("CMDR Jameson" in t for t in result["scene"]["texts"]))
app.settings["community_share_cmdr_name"] = False
check("and without it when name sharing is off",
      not any("Jameson" in t for t in app.picture_now(when=NOW, save=False)["scene"]["texts"]))
app.settings["community_share_cmdr_name"] = True

_real_pil = {k: v for k, v in sys.modules.items() if k == "PIL" or k.startswith("PIL.")}
for k in list(_real_pil): del sys.modules[k]
sys.modules["PIL"] = None            # an import of it now raises ImportError
try:
    ok2, why2 = MI.pillow_status()
    app2 = make_app()
    miss = app2.picture_now(when=NOW)
    check("without Pillow the status says why, in a sentence that names it",
          not ok2 and "Pillow" in why2 and why2.endswith("."), why2)
    check("the app does not raise: no picture, and the reason, no file written",
          miss["image"] is None and miss["path"] == "" and "Pillow" in miss["why"], miss["why"])
    note = {"event": "SRVDock", "rhino": True, "player": True, "when": stamp(0)}
    check("a dock without Pillow saves nothing, says why once, and is not a crash",
          app2.dock_picture(note) is False and any("Pillow" in s for s in app2.said), app2.said)
    n_said = len(app2.said)
    app2.dock_picture(note)
    check("and does not say it again every dock", len(app2.said) == n_said, app2.said)
    for button in (app2.save_map_picture, app2.copy_map_picture, app2.share_map):
        before = len(app2.said)
        button()
        check("the %s button says why instead of failing" % button.__name__,
              len(app2.said) == before + 1 and "Pillow" in app2.said[-1], app2.said[-1])
finally:
    del sys.modules["PIL"]
    sys.modules.update(_real_pil)
check("Pillow is back for the rest of the checks", MI.pillow_status()[0])

# Saved automatically on DockSRV, once, and never for an old dock replayed.
app = make_app()
dock = {"event": "SRVDock", "rhino": True, "player": True, "when": stamp(0), "srv_id": 105}
check("coming aboard saves a picture", app.dock_picture(dock) is True and len(app._pictures) == 1
      and os.path.isfile(app._pictures[0][1]), app._pictures)
check("named for the place and the minute", re.search(r"_3_\d{8}-\d{4}\.png$", app._pictures[0][1]))
check("and says so", any("Map picture saved" in s for s in app.said), app.said)
old_dock = dict(dock, when=stamp(7200))
check("a dock from before the app started (the journal read again) saves nothing",
      app.dock_picture(old_dock) is False and len(app._pictures) == 1)
check("a crewmate's SRV and a plain SRV save nothing",
      app.dock_picture(dict(dock, player=False)) is False and app.dock_picture(dict(dock, rhino=False)) is False)
check("the launch is not a dock", app.dock_picture(dict(dock, event="SRVLaunch")) is False)
app.settings["map_picture_auto"] = False
check("and the setting turns it off", app.dock_picture(dict(dock, when=stamp(0))) is False)
app.settings["map_picture_auto"] = True
empty_app = make_app()
empty_app.plan = make_plan([])
empty_app.plan.rigs = None
check("a map with nothing on it makes no picture, and says nothing is there",
      empty_app.dock_picture(dock) is False and empty_app.picture_now(save=False)["image"] is None
      and "nothing on the map" in empty_app.picture_now(save=False)["why"])

# The buttons are real, and Share map is the picture plus the text.
import inspect
BUILD = inspect.getsource(A.EDSMT._build)
BUTTONS = inspect.getsource(A.EDSMT._map_picture_buttons)
TICK = inspect.getsource(A.EDSMT.tick)
check("the status strip builds the three buttons", "self._map_picture_buttons(readout)" in BUILD
      and all(t in BUTTONS for t in ('"Save map..."', '"Copy map"', '"Share map"'))
      and all(c in BUTTONS for c in ("self.save_map_picture", "self.copy_map_picture", "self.share_map")))
check("the tick takes the picture before the rigs come off the map",
      "self.dock_picture(note)" in TICK and TICK.index("self.dock_picture(note)") < TICK.index("self.rigs_on_vehicle(note)"))
clip, opened = [], []
A.put_on_clipboard = lambda widget, text: clip.append(text) or True
_open_folder = SB.open_folder
SB.open_folder = lambda path: opened.append(path) or True
app = make_app()
app.share_map()
check("Share map saves the picture and opens its folder", len(opened) == 1 and opened[0].endswith(".png")
      and os.path.isfile(opened[0]), opened)
check("and copies one line of text for the patch, then each find of its best patch",
      clip and clip[0].splitlines()[0].startswith("Col 1 Sector AA-A c1-1 / ")
      and sum(1 for l in clip[0].splitlines() if l.startswith(A.SHARE_TAG)) >= 2, clip)
check("copied finds are in the same one-line form Import reads back",
      A.read_share_lines(clip[0])[1] == 0 and len(A.read_share_lines(clip[0])[0]) >= 2)
app.copy_map_picture()
check("Copy map off Windows says so and says where the file is",
      os.name == "nt" or ("Windows" in app.said[-1] and ".png" in app.said[-1]), app.said[-1])
SB.open_folder = _open_folder

# ---------------------------------------------------------------------------
print("== 2. Discord mining summary v2 ==")
ROW = {"id": "s1", "started": "2026-10-13T02:48:23Z", "ended": "2026-10-13T05:22:29Z",
       "closed": "2026-10-13T05:22:29Z", "system": "Col 1 Sector AA-A c1-1",
       "body": "Col 1 Sector AA-A c1-1 BC 2", "station": "Merit Port", "sold_in": "Col 1 Sector AA-A c1-1",
       "mined": "Iridium:707", "sold": "Iridium:690", "credits": "134232600", "sales": "1",
       "cmdr": "Jameson", "kind": "rhino", "transferred": "Iridium:690", "trips": "1"}
SUM = {"lines": [], "value": 134232600, "earned": 134232600, "cr_hr": 52264478, "estimated": False,
       "hold": (690, 1239), "rigs": 3, "finds": 9, "worked": 4, "merits_hr": 22500.0,
       "materials": {"Iron": 12, "Carbon": 7, "Sulphur": 3}, "wages": 20134891,
       "merits": 80000, "merits_est": 82000.0, "image": "map.png"}
msg = EDO.discord_session_message(ROW, "Jameson", summary=SUM)
embed = msg["embeds"][0]
fields = {f["name"]: f["value"] for f in embed["fields"]}
check("the patch's start and end times, in UTC", fields.get("Patch worked") == "02:48 to 05:22 UTC", fields)
check("gross as sold, and net after the crew's wages",
      fields.get("Sold (gross)") == "134,232,600 Cr"
      and fields.get("Net (after crew)") == "114,097,709 Cr (crew 20,134,891)", fields)
check("merits as paid against merits as estimated", fields.get("Merits") == "80,000 (estimated 82,000)", fields)
check("materials collected, most first, with the total",
      fields.get("Materials") == "Iron 12, Carbon 7, Sulphur 3 (22 in all)", fields)
check("the map is the embed's picture, named by the attachment",
      embed.get("image") == {"url": "attachment://map.png"}, embed.get("image"))
check("sold sessions say the figures were updated", fields.get("Status") == "Sold - figures updated")
check("nobody is pinged", msg["allowed_mentions"] == {"parse": []})
early = EDO.discord_session_message(dict(ROW, sold="", credits="", sales="0"), "Jameson",
                                    summary=dict(SUM, wages=None, merits=None, image=""))["embeds"][0]
ef = {f["name"]: f["value"] for f in early["fields"]}
check("before the sale: estimates only, no net, no actual merits, no picture",
      ef.get("Merits") == "est. 82,000" and "Net (after crew)" not in ef and "Sold" not in ef
      and "Sold (gross)" not in ef and "image" not in early and ef.get("Status") == "Not sold yet - estimates", ef)
check("a session with no crew at all shows no net line",
      "Net (after crew)" not in {f["name"] for f in EDO.discord_session_message(
          ROW, "J", summary=dict(SUM, wages=None))["embeds"][0]["fields"]})
check("a session that ran past midnight gives both dates",
      EDO.session_span(dict(ROW, started="2026-10-12T23:10:00Z", ended="2026-10-13T02:40:00Z"))
      == "12 Oct 23:10 to 13 Oct 02:40 UTC")
# Ten synthetic sessions through the limits.
shapes = [
    ({}, None), (dict(ROW, mined="", credits="", sold=""), {}), (dict(ROW, paused="600"), SUM),
    (dict(ROW, sold="", credits=""), dict(SUM, wages=None, merits=None)),
    (ROW, dict(SUM, materials={"M%d" % i: i + 1 for i in range(60)})),
    (ROW, dict(SUM, lines=[{"commodity": "Iridium", "worth": 10 ** 9, "where": "x" * 3000}])),
    (dict(ROW, mined=";".join("C%02d:%d" % (i, i + 1) for i in range(60))), SUM),
    (ROW, dict(SUM, merits=0, merits_est=None)), (ROW, dict(SUM, merits_hr=None)),
    (dict(ROW, started="", ended=""), SUM)]
fine = True
for number, (row, summary) in enumerate(shapes):
    try:
        built = EDO.discord_session_message(row, "J" * 400, summary=summary)["embeds"][0]
        sizes = [len(f["value"]) <= 1024 and len(f["name"]) <= 256 for f in built.get("fields", [])]
        fine = fine and all(sizes) and len(built.get("fields", [])) <= 25 \
            and len(built.get("description", "")) <= 4096 and len(built["title"]) <= 256
    except Exception as exc:           # noqa: BLE001
        fine = False
        print("   session %d raised %r" % (number, exc))
check("ten odd sessions: no error, no field over 1,024 characters, no more than 25 fields", fine)

# The upload and the edit, against a stub of the network: what goes on the wire.
sent = []
class _Reply:
    def __init__(self, body): self.body = body
    def read(self): return self.body
    def __enter__(self): return self
    def __exit__(self, *a): return False
def _urlopen(request, timeout=0):
    sent.append({"url": request.full_url, "method": request.get_method(),
                 "headers": {k.lower(): v for k, v in request.header_items()}, "data": request.data})
    return _Reply(json.dumps({"id": MESSAGE_ID, "attachments": [{"id": "5550001", "filename": "map.png"}]}).encode())
_real_urlopen = EDO.urllib.request.urlopen
EDO.urllib.request.urlopen = _urlopen
png = open(path, "rb").read()
answer = EDO.discord_post_file(HOOK, msg, "map.png", png)
req = sent[-1]
check("the picture goes as one multipart POST to the webhook, waiting for the message",
      req["method"] == "POST" and req["url"] == HOOK + "?wait=true"
      and req["headers"]["content-type"].startswith("multipart/form-data; boundary="), req)
body = req["data"]
boundary = req["headers"]["content-type"].split("boundary=")[1].encode()
parts = [p for p in body.split(b"--" + boundary) if b"Content-Disposition" in p]
check("payload_json first, then files[0] holding the PNG bytes",
      len(parts) == 2 and b'name="payload_json"' in parts[0] and b'name="files[0]"; filename="map.png"' in parts[1]
      and png in parts[1] and b"image/png" in parts[1])
sent_json = json.loads(parts[0].split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n", 1)[0])
check("the JSON names the attachment, the embed shows it, nobody is pinged",
      sent_json["attachments"] == [{"id": 0, "filename": "map.png"}]
      and sent_json["embeds"][0]["image"]["url"] == "attachment://map.png"
      and sent_json["allowed_mentions"] == {"parse": []})
check("Discord's answer carries the message id and the attachment id", answer["id"] == MESSAGE_ID
      and answer["attachments"][0]["id"] == "5550001")
edit = EDO.discord_edit(HOOK, MESSAGE_ID, msg, keep=["5550001"])
req = sent[-1]
check("the edit is a PATCH to the same message, not a new post",
      req["method"] == "PATCH" and req["url"] == "%s/messages/%s" % (HOOK, MESSAGE_ID), req["url"])
body = json.loads(req["data"])
check("and keeps the attachment it already has", body["attachments"] == [{"id": "5550001"}]
      and body["allowed_mentions"] == {"parse": []})
for bad in ("../../x", "", "abc", "12"):
    try:
        EDO.discord_edit(HOOK, bad, msg)
        refused = False
    except ValueError:
        refused = True
    check("an edit of message %r is refused before anything is sent" % bad, refused)
try:
    EDO.discord_post_file("https://example.com/x", msg, "map.png", png)
    refused = False
except ValueError as exc:
    refused = HOOK_TOKEN not in str(exc)
check("only a Discord webhook address is ever uploaded to", refused)
EDO.urllib.request.urlopen = _real_urlopen

# The ledger: wages, merits, materials, by the sale's own split.
LED = SL.SessionLedger(os.path.join(TMP, "ledger"))
rows = [{"id": "A", "started": "2026-10-13T02:48:23Z", "closed": "2026-10-13T05:22:29Z"},
        {"id": "B", "started": "2026-10-13T06:00:00Z", "closed": ""}]
def at(h, m, s): return "2026-10-13T%02d:%02d:%02dZ" % (h, m, s)
check("a material is the session it was picked up in",
      LED.note({"event": "MaterialCollected", "when": at(3, 0, 0), "name": "Iron", "count": 4, "n": 1}, rows)
      and LED.note({"event": "MaterialCollected", "when": at(3, 5, 0), "name": "Iron", "count": 3, "n": 1}, rows)
      and LED.note({"event": "MaterialCollected", "when": at(6, 10, 0), "name": "Carbon", "count": 2, "n": 1}, rows)
      and LED.for_session("A")["materials"] == {"Iron": 7} and LED.for_session("B")["materials"] == {"Carbon": 2})
check("a material nobody was mining for is nobody's",
      not LED.note({"event": "MaterialCollected", "when": at(9, 0, 0), "name": "Iron", "count": 1, "n": 1},
                   rows[:1]) and LED.for_session("A")["materials"] == {"Iron": 7})
check("the same journal line read again counts nothing twice",
      not LED.note({"event": "MaterialCollected", "when": at(3, 0, 0), "name": "Iron", "count": 4, "n": 1}, rows)
      and LED.for_session("A")["materials"] == {"Iron": 7})
check("no wage event, no crew: wages are not known, not zero", LED.for_session("A")["wages"] is None)
# One sale, and two crew wage events in the same second as it.
sale = {"event": "MarketSell", "when": at(5, 33, 10)}
check("wages that arrive before the sale are held, then paid to it",
      LED.note({"event": "NpcCrewPaidWage", "when": at(5, 33, 10), "crew_id": "c1", "amount": 10000000, "n": 1}) is False
      and LED.sale(sale, {"A": 134232600.0}) is True
      and LED.for_session("A")["wages"] == 10000000)
check("wages that arrive after the sale are paid to it too, from the second crew member",
      LED.note({"event": "NpcCrewPaidWage", "when": at(5, 33, 10), "crew_id": "c2", "amount": 10134890, "n": 1})
      and LED.for_session("A")["wages"] == 20134890, LED.for_session("A"))
check("a wage in some other second is not this sale's",
      not LED.note({"event": "NpcCrewPaidWage", "when": at(5, 40, 0), "crew_id": "c1", "amount": 5, "n": 1})
      and LED.for_session("A")["wages"] == 20134890)
check("merits paid after the sale are the sale's session's",
      LED.note({"event": "PowerplayMerits", "when": at(5, 33, 20), "merits": 80000, "total": 100080000})
      and LED.for_session("A")["merits"] == 80000, LED.for_session("A"))
check("a merits line that leaves the total where it was is nothing",
      not LED.note({"event": "PowerplayMerits", "when": at(5, 33, 25), "merits": 7, "total": 100080000}))
check("a sale spread over two sessions shares its wage by what each was paid",
      LED.sale({"event": "MarketSell", "when": at(7, 0, 0)}, {"A": 100.0, "B": 300.0})
      and LED.note({"event": "NpcCrewPaidWage", "when": at(7, 0, 0), "crew_id": "c1", "amount": 40, "n": 1})
      and LED.for_session("A")["wages"] == 20134890 + 10 and LED.for_session("B")["wages"] == 30)
check("a mission's merits, handed in after the sale, are not the sale's",
      LED.sale({"event": "MarketSell", "when": at(8, 0, 0)}, {"B": 50.0})
      and not LED.note({"event": "MissionCompleted", "when": at(8, 0, 20)})
      and not LED.note({"event": "PowerplayMerits", "when": at(8, 0, 25), "merits": 40, "total": 100057779})
      and LED.for_session("B")["merits"] == 0)
LED.save(force=True)
LED2 = SL.SessionLedger(os.path.join(TMP, "ledger"))
check("it survives a restart, with what it has already counted",
      LED2.for_session("A") == LED.for_session("A")
      and not LED2.note({"event": "MaterialCollected", "when": at(3, 0, 0), "name": "Iron", "count": 4, "n": 1}, rows))

# The reader queues the three journal events for it.
G2 = os.path.join(TMP, "game2"); os.makedirs(G2)
write_journal(G2, [
    {"timestamp": at(2, 0, 0), "event": "Fileheader", "part": 1, "gameversion": "4.4.1.1"},
    {"timestamp": at(2, 0, 0), "event": "Commander", "Name": "Jameson", "FID": "F1"},
    {"timestamp": at(3, 0, 0), "event": "MaterialCollected", "Category": "Raw", "Name": "iron",
     "Name_Localised": "Iron", "Count": 4},
    {"timestamp": at(5, 33, 10), "event": "NpcCrewPaidWage", "NpcCrewName": "Hale", "NpcCrewId": 77, "Amount": 123},
], "Journal.2026-10-13T020000.01.log")
reader = JN.JournalWatcher(G2)
reader.poll()
queued = {n["event"]: n for n in reader.drain_runs()}
check("MaterialCollected reaches the books' queue with its name and count",
      queued.get("MaterialCollected", {}).get("name") == "Iron" and queued["MaterialCollected"]["count"] == 4, queued)
check("NpcCrewPaidWage reaches it with the amount", queued.get("NpcCrewPaidWage", {}).get("amount") == 123, queued)

# The whole flow in the app: end of session -> one post -> the sale -> one edit.
class _Worker:
    def __init__(self): self.jobs = []
    def submit(self, tag, fn): self.jobs.append((tag, fn))
    def run(self):
        out = []
        for tag, fn in self.jobs:
            out.append((tag, fn()))
        self.jobs = []
        return out

requests = []
def _post_json(url, payload, timeout=20.0, headers=None):
    requests.append(("POST", url, payload))
    return {"id": MESSAGE_ID, "attachments": []}
def _post_file(url, payload, filename, data, timeout=40.0):
    requests.append(("POST-FILE", url, payload, filename, len(data)))
    return {"id": MESSAGE_ID, "attachments": [{"id": "5550001", "filename": filename}]}
_edits = []
def _discord_edit(url, message_id, payload, keep=(), timeout=20.0):
    _edits.append((url, message_id, payload, list(keep)))
    return {"id": message_id}
EDO.post_json, EDO.discord_post_file, EDO.discord_edit = _post_json, _post_file, _discord_edit

def flow_app(tag):
    d = make_app({"discord_webhook": HOOK})
    folder = os.path.join(TMP, "flow-" + tag)
    os.makedirs(folder, exist_ok=True)
    d.earnings = SV.Earnings(folder)
    d.extras = SL.SessionLedger(folder)
    d.post_book = SL.PostBook(folder)
    d.worker = _Worker()
    d.store = SV.Survey(os.path.join(folder, "store"))
    d.merits = SV.MeritRate(folder)
    d.market_book = SV.MarketBook(folder)
    d.watcher = JN.JournalWatcher(G2)
    d.watcher.cmdr = "Jameson"
    return d

d = flow_app("a")
d.post_discord_sessions()                       # first look: nothing closed yet
live = d.earnings.start("Col 1 Sector AA-A c1-1", "Col 1 Sector AA-A c1-1 BC 2", "Jameson", when=stamp(3 * 3600))
live.update({"mined": "Iridium:707", "ended": stamp(3500), "closed": stamp(3500)})
d.earnings.save()
photo = d.picture_now(when=NOW - 3500)
d._pictures = [(NOW - 3500, photo["path"])]
check("a session that ends is posted once, and the post is a job", d.post_discord_sessions() == 1 and len(d.worker.jobs) == 1)
check("and the session is spoken for at once", d.post_book.has(live["id"]))
check("never a second post for it, however often the tick asks",
      all(d.post_discord_sessions() == 0 for _ in range(5)) and len(d.worker.jobs) == 1)
done = d.worker.run()
posted = [r for r in requests if r[0] in ("POST", "POST-FILE")]
check("the map picture went with it, as an upload", posted and posted[-1][0] == "POST-FILE"
      and posted[-1][3] == os.path.basename(photo["path"]) and posted[-1][4] > 1000, posted)
check("the embed shows the picture", posted[-1][2]["embeds"][0]["image"]["url"]
      == "attachment://" + os.path.basename(photo["path"]))
for tag, message in done:
    d.take_discord(tag, True, message)
entry = d.post_book.posted[live["id"]]
check("Discord's message id and attachment id are kept", entry["id"] == MESSAGE_ID and entry["attachments"] == ["5550001"], entry)
check("nothing to edit before a sale", d.post_discord_sessions() == 0 and d.worker.jobs == [])
# The sale comes in, with its wages and merits, seconds apart.
live.update({"sold": "Iridium:690", "credits": "134232600", "sales": "1"})
d.extras.sessions[live["id"]] = {"materials": {"Iron": 12, "Carbon": 7}, "wages": 20134891,
                                 "wage_events": 2, "merits": 80000}
d.post_discord_sessions()
check("an edit waits until things have gone quiet - a sale is several lines", d.worker.jobs == [])
entry["changed_at"] = time.time() - SL.EDIT_QUIET_S - 1
entry["seen_state"] = d.discord_state(live)
check("then the same message is edited: one job", d.post_discord_sessions() == 0 and len(d.worker.jobs) == 1)
d.worker.run()
url, mid, edited, keep = _edits[-1]
ef = {f["name"]: f["value"] for f in edited["embeds"][0]["fields"]}
check("the edit is to the message that was posted, keeping the picture",
      mid == MESSAGE_ID and keep == ["5550001"] and "image" in edited["embeds"][0])
check("and it now carries gross, net, actual merits and materials",
      ef.get("Sold (gross)") == "134,232,600 Cr" and ef.get("Net (after crew)", "").startswith("114,097,709 Cr")
      and ef.get("Merits", "").startswith("80,000") and ef.get("Materials", "").startswith("Iron 12, Carbon 7"), ef)
check("with the original post's time, not the edit's", edited["embeds"][0]["timestamp"]
      == EDO.utc_stamp(entry["when"]), edited["embeds"][0]["timestamp"])
d.worker.jobs = []
check("nothing changed since: no further edit, no further post",
      d.post_discord_sessions() == 0 and d.worker.jobs == [])
check("over the whole session there was exactly one post",
      len([r for r in requests if r[0] in ("POST", "POST-FILE")]) == 1, requests)
# After a restart the message is still the one to edit, and the session is not posted again.
d2 = flow_app("a")
d2.earnings = d.earnings
check("a new run of the app knows the message and posts nothing for the old session",
      d2.post_book.has(live["id"]) and d2.post_discord_sessions() == 0 and d2.worker.jobs == [])
# The message was deleted on Discord.
entry2 = d.post_book.posted[live["id"]]
d.take_discord(EDO.DISCORD_TAG, True, json.dumps({"edsmt_session": live["id"], "edit": True,
                                                  "error": "discord.com refused it (HTTP 404): Unknown Message"}))
check("a deleted message is given up on, and the commander is told",
      entry2["dead"] is True and any("did not take it" in s for s in d.said), d.said)
check("and the webhook is in nothing the commander is shown",
      not any(HOOK in s or HOOK_TOKEN in s for s in d.said), d.said)
d.settings["discord_edit_after_sale"] = False
check("the setting turns edits off", d.discord_edits(HOOK) == 0)
# A picture Discord will not take must not cost the summary.
d3 = flow_app("c")
attempts = []
def _picky(url, payload, filename, data, timeout=40.0):
    attempts.append("file"); raise RuntimeError("discord.com refused it (HTTP 413): too large")
EDO.discord_post_file = _picky
out = json.loads(d3.discord_job(HOOK, EDO.discord_session_message(ROW, "J", summary=dict(SUM)), "s9", ("map.png", b"x")))
check("a refused picture falls back to the summary alone - still one post",
      attempts == ["file"] and out.get("message", {}).get("id") == MESSAGE_ID
      and "image" not in requests[-1][2]["embeds"][0], (out, requests[-1]))
EDO.discord_post_file = _post_file
EDO.post_json = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("could not reach discord.com: refused"))
out = json.loads(d3.discord_job(HOOK, EDO.discord_session_message(ROW, "J", summary=dict(SUM)), "s10"))
check("a post that fails says why, naming the session and never the address",
      out.get("error") and HOOK not in json.dumps(out) and out["edsmt_session"] == "s10", out)
EDO.post_json = _post_json
check("without a webhook nothing is posted or edited",
      flow_app("d").discord_edits("") == 0)
check("the tick keeps asking: sessions are posted from tick, edits from the same call",
      "self.post_discord_sessions()" in TICK)

# ---------------------------------------------------------------------------
print("== 3. the ship's hold card ==")
TOO = "Journal.2026-10-13T020000.01.log"
def ship_world(name, journals):
    folder = os.path.join(TMP, name)
    os.makedirs(folder)
    for fname, events in journals:
        write_journal(folder, events, fname)
    return folder

def base_events(part_stamp, loadout=None, ship_id=5, extra=()):
    ev = [{"timestamp": part_stamp, "event": "Fileheader", "part": 1, "gameversion": "4.4.1.1"},
          {"timestamp": part_stamp, "event": "Commander", "Name": "Jameson", "FID": "F1"},
          {"timestamp": part_stamp, "event": "LoadGame", "Ship": "panthermkii", "ShipID": ship_id}]
    if loadout is not None:
        ev.append({"timestamp": part_stamp, "event": "Loadout", "Ship": "panthermkii",
                   "ShipID": ship_id, "CargoCapacity": loadout})
    return ev + list(extra)

LAUNCH = {"event": "LaunchSRV", "SRVType": "mev_rhino", "SRVType_Localised": "SRV Rhino",
          "ID": 105, "PlayerControlled": True}
DOCK = {"event": "DockSRV", "SRVType": "mev_rhino", "SRVType_Localised": "SRV Rhino", "ID": 105}
def transfer(when, tonnes, direction="toship"):
    return {"timestamp": when, "event": "CargoTransfer", "Transfers": [
        {"Type": "iridium", "Type_Localised": "Iridium", "Count": tonnes, "Direction": direction}]}
def srv_cargo(when, count):
    return {"timestamp": when, "event": "Cargo", "Vessel": "SRV", "Count": count}

def card_of(folder, book=None):
    reader = JN.JournalWatcher(folder)
    reader.poll()
    return reader, SH.hold_card(reader, book)

# (a) The journal has the Loadout, the Rhino has been unloading, the ship's hold has not been seen.
f_a = ship_world("hold-a", [(TOO, base_events(at(2, 0, 0), loadout=1239, extra=[
    {"timestamp": at(2, 5, 0), "event": "Location", "StarSystem": "Col 1", "Docked": False},
    dict(LAUNCH, timestamp=at(2, 10, 0)), srv_cargo(at(2, 20, 0), 18), srv_cargo(at(2, 30, 0), 72),
    transfer(at(2, 31, 0), 17), transfer(at(2, 40, 0), 17), transfer(at(2, 50, 0), 17)]))])
rd, card = card_of(f_a)
check("the reader has the ship's capacity from this journal's Loadout, by ship ID",
      rd.capacities == {5: (1239, at(2, 0, 0))} and rd.ship_id == 5 and rd.cargo_capacity == 1239, rd.capacities)
check("the Rhino's own hold is whatever its last tick said", rd.srv_total == 72 and card["rhino_t"] == 72)
check("the ship's hold was never stated, so it is not known - not guessed from the transfers",
      card["known"] is False and card["tonnes"] is None, card)
check("it says tonnes unloaded this trip and to board the ship",
      card["title"] == "SHIP +51 t this trip" and card["detail"] == "BOARD SHIP FOR FULL HOLD"
      and card["state"] == "unknown" and card["trip_t"] == 51, card)
# the Rhino docks: the ship's whole hold arrives 5-6 s later
append_journal(f_a, [dict(DOCK, timestamp=at(3, 0, 0)),
                     {"timestamp": at(3, 0, 0), "event": "Loadout", "Ship": "panthermkii", "ShipID": 5, "CargoCapacity": 1298},
                     {"timestamp": at(3, 0, 6), "event": "Cargo", "Vessel": "Ship", "Count": 690}], TOO)
rd.poll()
card = SH.hold_card(rd)
check("after DockSRV the ship's hold is stated, and the capacity is the newest Loadout's (1298, not 1239)",
      card["known"] and card["tonnes"] == 690 and card["capacity"] == 1298, card)
check("the card has the words: tonnes of capacity, free, and Rhino loads left",
      card["title"] == "SHIP 690/1298 t" and card["detail"] == "608 t free - 9 loads left"
      and card["loads_left"] == 9 and abs(card["fraction"] - 690 / 1298.0) < 1e-9 and card["state"] == "ok", card)
check("and the trip's unloading is still there to read", "51 t unloaded this trip" in card["line"], card["line"])
# a second trip: counted on from the stated total, and the trip counter starts again
append_journal(f_a, [dict(LAUNCH, timestamp=at(3, 10, 0)), transfer(at(3, 20, 0), 60), transfer(at(3, 30, 0), 40)], TOO)
rd.poll()
card = SH.hold_card(rd)
check("a new trip counts on from the stated total, and its own unloading from nought",
      card["tonnes"] == 790 and card["trip_t"] == 100 and card["known"], card)
append_journal(f_a, [transfer(at(3, 40, 0), 508)], TOO)
rd.poll()
card = SH.hold_card(rd)
check("full is ship tonnes equal to the capacity: HOLD FULL, red, nothing left",
      card["tonnes"] == 1298 and card["full"] and card["detail"] == "HOLD FULL" and card["state"] == "full"
      and card["free"] == 0 and card["loads_left"] == 0 and card["fraction"] == 1.0, card)
append_journal(f_a, [{"timestamp": at(3, 50, 0), "event": "EjectCargo", "Type": "iridium", "Count": 1, "Abandoned": True}], TOO)
rd.poll()
check("a tonne thrown out of the ship takes the hold below full", SH.hold_card(rd)["tonnes"] == 1297
      and not SH.hold_card(rd)["full"])
append_journal(f_a, [{"timestamp": at(4, 0, 0), "event": "MarketSell", "Type": "iridium", "Count": 1297,
                      "SellPrice": 194540, "TotalSale": 252316000, "AvgPricePaid": 0}], TOO)
rd.poll()
card = SH.hold_card(rd)
check("selling the cargo empties it - the card is not stuck on FULL", card["tonnes"] == 0 and not card["full"]
      and card["detail"].startswith("1298 t free"), card)
trip_before = SH.hold_card(rd)["trip_t"]
check("a carrier-to-ship transfer with no Rhino out is not the Rhino's unloading",
      trip_before == 608 and (append_journal(f_a, [dict(DOCK, timestamp=at(4, 5, 0)), transfer(at(4, 10, 0), 30)], TOO),
       rd.poll(), SH.hold_card(rd))[2]["trip_t"] == trip_before
      and rd.ship_total == 30, (trip_before, rd.ship_total))
check("tosrv and tocarrier take tonnes out of the ship",
      (append_journal(f_a, [transfer(at(4, 11, 0), 10, "tocarrier")], TOO), rd.poll(), SH.hold_card(rd)["tonnes"])[2] == 20)

# (b) Loadout only in an earlier file: the book learns it from the older journals.
f_b = ship_world("hold-b", [
    ("Journal.2026-10-08T170000.01.log", base_events(at(1, 0, 0), loadout=1239, ship_id=5)),
    ("Journal.2026-10-10T170000.01.log", base_events(at(1, 30, 0), loadout=1298, ship_id=5)),
    ("Journal.2026-10-11T170000.01.log", base_events(at(1, 45, 0), loadout=256, ship_id=8)),
    ("Journal.2026-10-13T020000.01.log", base_events(at(2, 0, 0), extra=[
        dict(LAUNCH, timestamp=at(2, 10, 0)), transfer(at(2, 31, 0), 17),
        {"timestamp": at(2, 40, 0), "event": "Cargo", "Vessel": "Ship", "Count": 800}]))])
book_b = SH.CapacityBook(os.path.join(TMP, "book-b"))
check("reading the older journals finds each ship's newest Loadout",
      book_b.learn_folder(f_b) >= 2 and book_b.capacity_for(5) == 1298 and book_b.capacity_for(8) == 256,
      book_b.ships)
rd_b, card_b = card_of(f_b, book_b)
check("this journal has no Loadout, so the reader alone has no capacity", rd_b.cargo_capacity is None
      and rd_b.capacities == {})
check("the book supplies it for this ship ID, and the card is complete",
      card_b["capacity"] == 1298 and card_b["known"] and card_b["title"] == "SHIP 800/1298 t"
      and card_b["source"] == "an earlier journal", card_b)
book_c = SH.CapacityBook(os.path.join(TMP, "book-b"))
check("it is kept in ship_capacity.json, and a restart reads it back", os.path.isfile(book_b.path)
      and os.path.basename(book_b.path) == "ship_capacity.json" and book_c.capacity_for(5) == 1298)
files_before = dict(book_b.files)
check("older journals already read are not read again", book_b.learn_folder(f_b) == 0 and book_b.files == files_before)
# older file read AFTER a newer one must not win
book_d = SH.CapacityBook()
book_d.note(5, 1298, "2026-10-10T17:00:00Z"); book_d.note(5, 1024, "2026-10-01T17:00:00Z")
check("whichever order files are read in, the newest Loadout is the capacity", book_d.capacity_for(5) == 1298)
# (c) never a Loadout anywhere
f_c = ship_world("hold-c", [(TOO, base_events(at(2, 0, 0), extra=[
    {"timestamp": at(2, 40, 0), "event": "Cargo", "Vessel": "Ship", "Count": 300}]))])
rd_c, card_c = card_of(f_c, SH.CapacityBook())
check("with no Loadout anywhere the tonnes are shown and the capacity is said to be unknown, not made up",
      card_c["known"] and card_c["capacity"] is None and card_c["title"] == "SHIP 300 t"
      and card_c["detail"] == "capacity not known yet" and card_c["fraction"] is None and not card_c["full"], card_c)
# (d) two ships
f_d = ship_world("hold-d", [(TOO, base_events(at(2, 0, 0), loadout=1298, ship_id=5, extra=[
    {"timestamp": at(2, 1, 0), "event": "Cargo", "Vessel": "Ship", "Count": 400},
    {"timestamp": at(2, 5, 0), "event": "ShipyardSwap", "ShipType": "type10", "ShipID": 8},
    {"timestamp": at(2, 5, 1), "event": "Loadout", "Ship": "type10", "ShipID": 8, "CargoCapacity": 256}]))])
rd_d, card_d = card_of(f_d)
check("a swap to a second ship follows the ship ID: its hold, and its total not yet seen",
      rd_d.ship_id == 8 and card_d["capacity"] == 256 and card_d["known"] is False
      and rd_d.capacities == {5: (1298, at(2, 0, 0)), 8: (256, at(2, 5, 1))}, (rd_d.ship_id, card_d, rd_d.capacities))
append_journal(f_d, [{"timestamp": at(2, 8, 0), "event": "Cargo", "Vessel": "Ship", "Count": 100}], TOO)
rd_d.poll()
check("and the hold stated for the second ship is measured against the second ship",
      SH.hold_card(rd_d)["title"] == "SHIP 100/256 t")
# A hold more than its capacity says the capacity is out of date.
rd_d.ship_total = 300
card = SH.hold_card(rd_d)
check("tonnes above the capacity say the capacity is out of date rather than showing 117%",
      card["capacity"] is None and card["stale"] and card["detail"] == "capacity out of date - board the ship"
      and card["fraction"] is None, card)
check("a reader that does not track the hold gets no card", SH.hold_card(type("R", (), {})()) is None)

# Cargo.json that did not change is not re-read as news every poll.
f_e = ship_world("hold-e", [(TOO, base_events(at(2, 0, 0), loadout=1000, extra=[dict(LAUNCH, timestamp=at(2, 10, 0))]))])
with open(os.path.join(f_e, "Cargo.json"), "w") as fh:
    json.dump({"timestamp": at(2, 0, 0), "event": "Cargo", "Vessel": "Ship", "Count": 100,
               "Inventory": [{"Name": "iridium", "Count": 100}]}, fh)
rd_e = JN.JournalWatcher(f_e); rd_e.poll()
append_journal(f_e, [transfer(at(2, 20, 0), 40)], TOO)
rd_e.poll(); rd_e.poll(); rd_e.poll()
check("a Cargo.json describing the ship, rewritten by nobody, does not undo the transfers on every poll",
      rd_e.ship_total == 140, rd_e.ship_total)

# Through the app: the strip, the overlay and the flash.
hold_app = make_app()
hold_app.watcher = rd_a = JN.JournalWatcher(f_a)
rd_a.poll()
hold_app.ship_book = SH.CapacityBook(os.path.join(TMP, "book-app"))
hold_app.earnings = type("E", (), {"rhino": {"kind": "rhino"}})()
flashes = []
hold_app.flash = lambda title, detail="", colour=None: flashes.append((title, detail, colour))
cargo = hold_app.overlay_cargo()
check("the overlay is handed the card with the usual three numbers", cargo and cargo["hold"]["known"] is True
      and set(("ship_t", "capacity", "rhino_t")) <= set(cargo), cargo)
check("the card's capacity is recorded in the book for next time", hold_app.ship_book.capacity_for(5) == 1298
      and os.path.isfile(hold_app.ship_book.path))
check("no hold line on the strip while the commander is not in the Rhino", hold_app.hold_line() == "")
rd_a.in_srv = True
check("the strip carries a hold line in the Rhino", hold_app.hold_line().startswith("SHIP "), hold_app.hold_line())
rd_a.srv_total = None
unknown = make_app()
unknown.watcher = rd_unknown = JN.JournalWatcher(ship_world("hold-u", [(TOO, base_events(at(2, 0, 0), loadout=500, extra=[
    dict(LAUNCH, timestamp=at(2, 10, 0)), transfer(at(2, 31, 0), 51)]))]))
rd_unknown.poll()
unknown.ship_book = SH.CapacityBook()
unknown.flash = lambda title, detail="", colour=None: flashes.append((title, detail, colour))
unknown.flash_ship_hold("Iridium:51")
check("after a transfer with the ship unseen, the flash says tonnes this trip and to board the ship",
      flashes[-1][:2] == ("SHIP +51 t this trip", "BOARD SHIP FOR FULL HOLD") and flashes[-1][2] == A.AMBER, flashes[-1])
hold_app.flash_ship_hold("Iridium:17")
check("and with it seen, the old flash: tonnes, capacity, room",
      flashes[-1][0].startswith("SHIP ") and "t room" in flashes[-1][0], flashes[-1])
check("the capacity the ship_hold() answers is the book's when the journal has none",
      make_app().__class__ is A.EDSMT and
      (lambda a: (setattr(a, "watcher", rd_b), setattr(a, "ship_book", book_b), a.ship_hold())[-1])(make_app()) == (800, 1298))

# The overlay's STATUS box draws it.
class _Canvas:
    def __init__(self): self.calls = []
    def delete(self, *_a): self.calls = []
    def __getattr__(self, name):
        def record(*args, **kw): self.calls.append((name, args, kw))
        return record
class _Window:
    def __init__(self, w=560, h=120): self.w, self.h = w, h
    def winfo_width(self): return self.w
    def winfo_height(self): return self.h
    def winfo_screenwidth(self): return 1920
    def winfo_screenheight(self): return 1080
OV.foreground_is_game = lambda: None
class _Saver:
    def save_settings(self): pass
def status_drawn(card, rhino_t=None, h=120):
    over = OV.Overlay(app=_Saver(), tk_module=None, settings={"overlay_click_through": True})
    panel = OV.Panel(over, OV.STATUS)
    panel.window, panel.canvas = _Window(560, h), _Canvas()
    over.panels = {OV.STATUS: panel}
    over.draw([], 0.0, body="Ega 3 a", location="2",
              cargo={"ship_t": 0, "capacity": None, "rhino_t": rhino_t, "hold": card})
    return panel.canvas
def words(canvas):
    return [str(kw.get("text", "")) for n, _a, kw in canvas.calls if n == "create_text"]
def bars(canvas):
    return [(a, kw) for n, a, kw in canvas.calls if n == "create_rectangle" and "hold" in (kw.get("tags") or ())]
known = SH.hold_card(rd_a, SH.CapacityBook())
rd_a.ship_total = 790
half = status_drawn(SH.hold_card(rd_a), rhino_t=31)
check("the STATUS box shows the tonnes against the capacity, the room, and the Rhino",
      any(t.startswith("SHIP 790/1298 t") and "508 t free" in t and "RHINO 31t" in t for t in words(half)), words(half))
check("with a fill bar: an outline and a fill part-way across",
      len(bars(half)) == 2 and bars(half)[1][0][2] < bars(half)[0][0][2] and bars(half)[1][0][2] > bars(half)[0][0][0], bars(half))
rd_a.ship_total = 1298
full = status_drawn(SH.hold_card(rd_a))
check("a full hold reads HOLD FULL, in red, with the bar filled right across",
      any("HOLD FULL" in t for t in words(full)) and any(kw.get("fill") == OV.RED for n, _a, kw in full.calls
                                                          if n == "create_text" and "FULL" in str(kw.get("text", "")))
      and bars(full)[1][0][2] == bars(full)[0][0][2], words(full))
rd_a.ship_total = None
unseen = status_drawn(SH.hold_card(rd_a))
check("an unseen hold reads BOARD SHIP FOR FULL HOLD, in amber, with no bar - there is nothing to measure",
      any("BOARD SHIP FOR FULL HOLD" in t for t in words(unseen)) and bars(unseen) == []
      and any(kw.get("fill") == OV.AMBER for n, _a, kw in unseen.calls
              if n == "create_text" and "BOARD" in str(kw.get("text", ""))), words(unseen))
old_style = status_drawn(None)
check("with no card the box draws exactly what it drew before (the old one-line cargo text)",
      not any("BOARD SHIP" in t or "HOLD FULL" in t for t in words(old_style)))

# ---------------------------------------------------------------------------
print("== 4. the support bundle ==")
SUP = os.path.join(TMP, "support-data"); os.makedirs(SUP)
SETTINGS = dict(A.DEFAULT_SETTINGS, inara_api_key=INARA_KEY, community_token=COMMUNITY_TOKEN,
                discord_webhook=HOOK, wing_code=WING, wing_member="a1b2c3d4e5f60718", hotkey_overlay="ALT+0",
                inara_enabled=True)
HOME = os.path.expanduser("~")
open(os.path.join(SUP, "crash.log"), "w", encoding="utf-8").write(
    "\n--- 1.10035 2026-10-13 (Journal) ---\nTraceback (most recent call last):\n"
    "  File \"%s/EDSMT/edsmt.py\", line 9, in tick\nRuntimeError: could not post to %s with key %s\n"
    "{\"apiKey\": \"%s\", \"commander\": \"Jameson\"}\nGET https://api.radioraxxla.com/v1/x?token=%s&a=1\n"
    % (HOME, HOOK, INARA_KEY, INARA_KEY, COMMUNITY_TOKEN))
open(os.path.join(SUP, "journal-mining-events.log"), "w", encoding="utf-8").write(
    "".join("2026-10-13 event %d {\"Name\": \"x\"}\n" % n for n in range(3000)) + "webhook %s\n" % HOOK)
logger = SB.AppLog(SUP)
for n in range(2000):
    logger.write("line %d mined 12 t - community token %s" % (n, COMMUNITY_TOKEN) if n % 500 == 0 else "line %d" % n)
logger.write("Discord did not take it: refused " + HOOK)
bundle = SB.make_bundle(os.path.join(TMP, "support-out"), SUP, SETTINGS, "1.10035", "installed", when=NOW)
check("one zip, named for the version and the time", os.path.isfile(bundle)
      and re.fullmatch(r"EDSMT-support-1\.10035-\d{8}-\d{6}\.zip", os.path.basename(bundle)), bundle)
with zipfile.ZipFile(bundle) as z:
    names = sorted(z.namelist())
    members = {n: z.read(n).decode("utf-8", "replace") for n in names}
check("it holds the version page, the settings, crash.log, the event log, the app log and a file list",
      names == sorted(["about.txt", "settings.json", "crash.log", "journal-mining-events.log", "app.log",
                       "data-folder.txt"]), names)
check("about.txt has the app version, the build and the operating system",
      "1.10035" in members["about.txt"] and "installed" in members["about.txt"]
      and "system" in members["about.txt"] and re.search(r"python\s+3\.", members["about.txt"]))
everything = "\n".join(members.values())
secrets_in = [("webhook address", HOOK), ("webhook token", HOOK_TOKEN), ("webhook id", HOOK_ID),
              ("Inara key", INARA_KEY), ("community token", COMMUNITY_TOKEN), ("wing code", WING),
              ("wing member id", "a1b2c3d4e5f60718")]
for label, value in secrets_in:
    check("the %s is nowhere in the zip" % label, value not in everything and value.encode() not in b"".join(
        zipfile.ZipFile(bundle).read(n) for n in names))
settings_out = json.loads(members["settings.json"])
check("secret settings read [removed], never their value, and empty ones stay empty",
      all(settings_out[k] == "[removed]" for k in ("inara_api_key", "community_token", "discord_webhook",
                                                  "wing_code", "wing_member")))
short_bundle = SB.make_bundle(os.path.join(TMP, "support-out"), SUP, dict(SETTINGS, wing_member="42"),
                              "1.10035", "installed", when=NOW + 7)
with zipfile.ZipFile(short_bundle) as z:
    short_settings = json.loads(z.read("settings.json").decode("utf-8"))
check("a secret too short to search for is still removed from the settings by its name",
      short_settings["wing_member"] == "[removed]" and SB.clean_settings(SETTINGS)["inara_api_key"] == "[removed]",
      short_settings["wing_member"])
check("an unset secret is shown as unset", json.loads(SB.json.dumps(SB.clean_settings(
      dict(SETTINGS, discord_webhook=""))))["discord_webhook"] == "")
check("everything that is not a secret is kept - including the key bindings",
      settings_out["hotkey_overlay"] == "ALT+0" and settings_out["inara_enabled"] is True
      and settings_out["map_picture_auto"] is True and settings_out["journal_dir"] == "")
check("a binding called a key is not mistaken for a secret",
      not SB.is_secret_key("hotkey_overlay") and SB.is_secret_key("inara_api_key") and SB.is_secret_key("some_new_token")
      and SB.is_secret_key("x_webhook") and not SB.is_secret_key("community_url"))
check("the crash log is there, with the traceback and the fault - and the secrets taken out of it",
      "Traceback" in members["crash.log"] and "RuntimeError: could not post to [removed] with key [removed]" in members["crash.log"])
check("the home folder's name is gone from it", HOME not in members["crash.log"] or HOME in ("/", ""), members["crash.log"][:200])
app_lines = members["app.log"].strip().splitlines()
check("the app log is the newest lines only", 300 <= len(app_lines) <= SB.LOG_LINES and "line 1999" in members["app.log"]
      and "line 5 " not in members["app.log"] + " ", len(app_lines))
check("the event log is cut to its newest part", "event 2999" in members["journal-mining-events.log"]
      and len(members["journal-mining-events.log"]) <= SB.TEXT_TAIL_BYTES + 200)
check("the data folder is listed by name and size, not copied", "crash.log" in members["data-folder.txt"]
      and "Traceback" not in members["data-folder.txt"])
empty = SB.make_bundle(os.path.join(TMP, "support-out2"), os.path.join(TMP, "nothing-here"), {}, "1.10035")
with zipfile.ZipFile(empty) as z:
    check("with nothing written yet it still makes a bundle, and says what is missing",
          "no crash.log" in z.read("crash.log").decode() and "no app log" in z.read("app.log").decode())
roll = SB.AppLog(os.path.join(TMP, "roll"))
for n in range(9000):
    roll.write("a long line of text number %d %s" % (n, "x" * 60))
check("the app log rolls over instead of growing without end",
      os.path.getsize(roll.path) <= SB.APP_LOG_MAX_BYTES + 4096, os.path.getsize(roll.path))
check("and the same line twice running is written once",
      (roll.write("same"), roll.write("same"))[1] is False)
check("the app's status line is written to it", "log.write(text)" in inspect.getsource(A.EDSMT.say))
# The button.
ABOUT = inspect.getsource(A.SettingsWindow.__init__)
check("Settings > About has the button", 'text="Make a support bundle"' in ABOUT
      and "command=self.make_support_bundle" in ABOUT)
class _Win: pass
win = A.SettingsWindow.__new__(A.SettingsWindow)
win.app = type("App", (), {"settings": dict(SETTINGS)})()
win.said = []
win.say = lambda text, colour=None: win.said.append(str(text))
A.documents_dir = lambda: os.path.join(TMP, "Documents")
opened = []
SB.open_folder = lambda p: opened.append(p) or True
win.make_support_bundle()
check("pressing it writes the zip to Documents\\EDSMT support and opens its folder",
      len(opened) == 1 and os.path.dirname(opened[0]) == os.path.join(TMP, "Documents", "EDSMT support")
      and zipfile.is_zipfile(opened[0]), opened)
check("and tells the commander where, and that no keys are in it",
      "Support bundle written" in win.said[-1] and "no keys" in win.said[-1] and HOOK not in win.said[-1], win.said)
with zipfile.ZipFile(opened[0]) as z:
    check("the one the button wrote has no secret in it either",
          not any(v.encode() in z.read(n) for n in z.namelist() for _l, v in secrets_in))

# ---------------------------------------------------------------------------
print("== 5. packaging, settings, wording ==")
req = open(os.path.join(REPO, "requirements.txt"), encoding="utf-8").read()
m = re.search(r"^Pillow>=([\d.]+),<([\d.]+)\s*$", req, re.M)
check("requirements.txt asks for Pillow with a lower and an upper bound", bool(m), req)
check("and customtkinter is still pinned", re.search(r"^customtkinter>=5\.2\.2,<6\s*$", req, re.M))
for spec in ("EDSMT.spec", "EDSMT-onefile.spec"):
    text = open(os.path.join(REPO, "build", spec), encoding="utf-8").read()
    check("%s bundles Pillow's image modules by name" % spec,
          all('"%s"' % mod in text for mod in ("PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont")))
    check("%s names the four new modules" % spec,
          all('"%s"' % mod in text for mod in ("mapimage", "shiphold", "sessionledger", "supportbundle")))
    check("%s does not exclude what Pillow needs" % spec,
          not re.search(r'excludes\s*=\s*\[[^\]]*"PIL"', text))
check("every new module exists beside the app", all(os.path.isfile(os.path.join(REPO, m + ".py"))
      for m in ("mapimage", "shiphold", "sessionledger", "supportbundle")))
for key in ("map_picture_auto", "discord_attach_map", "discord_edit_after_sale"):
    check("setting %s: on by default, has a tip, has a switch" % key,
          A.DEFAULT_SETTINGS.get(key) is True and key in A.SETTING_TIPS
          and '"%s"' % key in inspect.getsource(A.SettingsWindow.__init__))
check("the pictures folder button exists in Settings", "command=self.open_pictures_folder"
      in inspect.getsource(A.SettingsWindow.__init__))
shown = " ".join(str(v) for v in (A.SETTING_TIPS["map_picture_auto"], A.SETTING_TIPS["discord_attach_map"],
                                  A.SETTING_TIPS["discord_edit_after_sale"], SB.describe("1", "x")))
for name in ("mapimage.py", "shiphold.py", "sessionledger.py", "supportbundle.py"):
    src = open(os.path.join(REPO, name), encoding="utf-8").read()
    check("%s has no bare except and no bind_all" % name,
          not re.search(r"^\s*except\s*:", src, re.M) and "bind_all" not in src)
check("no log or message in the new Discord code prints the webhook",
      not re.search(r"(print|say)\([^)]*hook[^)]*\)", inspect.getsource(A.EDSMT.discord_job)
                    + inspect.getsource(A.EDSMT.discord_edits) + inspect.getsource(A.EDSMT.discord_answer)))

print()
print("FAILURES: %d" % len(fails))
for f in fails:
    print("  - " + f)
sys.exit(1 if fails else 0)
