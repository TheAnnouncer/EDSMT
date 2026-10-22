"""Product screenshots of the real app, from a made-up session.

Runs EDSMT itself - the real window, the real overlay, the real Find, Where
to land, Powerplay and Earnings windows and the real map picture - against a
synthetic journal in a folder of its own, and saves a PNG of each. Nothing
here is anybody's real data: the commander is "Example", and the system,
the stations and every number are invented.

Nothing leaves the machine while it runs. Every network connection is
refused before EDSMT is imported, and the answers the windows would have
had from the community map are handed to them by hand, the same way the
tests do it.

Needs Linux with an X display (xvfb is fine), Python 3.12 with tkinter,
customtkinter and Pillow, and ImageMagick's `import` for the window grabs:

    xvfb-run -a -s "-screen 0 1920x1200x24" python3.12 tools/screenshots.py OUT [--publish]

OUT defaults to ./screenshots. Written there: raw-*.png, one per window,
straight off the screen. With --publish they are also made into the
pictures the project uses: docs/images/*.png for the README (each kept under
400 KB) and site/edsmt-*.jpg for the web page, full size and 800 wide.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

PUBLISH = "--publish" in sys.argv[1:]
_ARGS = [a for a in sys.argv[1:] if a != "--publish"]
OUT = os.path.abspath(_ARGS[0] if _ARGS else "screenshots")
os.makedirs(OUT, exist_ok=True)
TMP = tempfile.mkdtemp(prefix="edsmt-shots-")
os.environ["HOME"] = TMP
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")


# -- no network at all ---------------------------------------------------------

_real_connect = socket.socket.connect


def _refuse(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        raise OSError("screenshots run offline")
    return _real_connect(self, address)


socket.socket.connect = _refuse
socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(
    OSError("screenshots run offline"))


# -- the made-up session -------------------------------------------------------

CMDR = "Example"
SYSTEM = "Phrua Aowsy KD-B c14-7"
BODY = SYSTEM + " A 3"
RADIUS = 1_870_000.0                   # metres
HOME = (-21.4172, 63.8851)             # the signal's centre, lat / lon
STAR_POS = [-412.3, -38.9, 1186.6]
STATION, PORT_SYSTEM = "Okoye Terminal", SYSTEM
NOW = time.time()
SESSION_S = 74 * 60                    # the Rhino went out this long ago


def stamp(ago_s=0.0):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(NOW - ago_s))


POWER = "Li Yong-Rui"
# Systems the journal has been in round here: (name, offset in Ly, the Power
# in control, its state, another Power present).
NEIGHBOURS = [
    ("Phrua Aowsy LY-Z b45-2", (6.2, -3.1, 7.0), "", "Unoccupied", ""),
    ("Phrua Aowsy FG-X d1-88", (-9.8, 4.4, -8.3), POWER, "Stronghold", ""),
    ("Phrua Aowsy MT-K c13-21", (11.9, 7.5, 9.6), "Archon Delaine", "Exploited", POWER),
    ("Phrua Aowsy QJ-P a72-4", (-18.6, -6.2, -15.1), "", "Unoccupied", ""),
    ("Phrua Aowsy BA-R b48-1", (4.1, 2.2, -5.9), POWER, "Exploited", ""),
    ("Phrua Aowsy HN-U c16-3", (29.4, -12.0, 27.7), "Felicia Winters", "Fortified", ""),
    ("Phrua Aowsy WE-G b46-0", (-3.3, 13.8, 11.2), "", "Unoccupied", ""),
]
JOURNALS = os.path.join(TMP, "journals")
os.makedirs(JOURNALS, exist_ok=True)
JOURNAL = os.path.join(JOURNALS, "Journal.%s.01.log"
                       % time.strftime("%Y-%m-%dT%H%M%S", time.gmtime(NOW - 4 * 3600)))


def emit(*events):
    with open(JOURNAL, "a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")


def status(lat, lon, heading=90, flags=(1 << 21) | (1 << 26)):
    with open(os.path.join(JOURNALS, "Status.json"), "w", encoding="utf-8") as handle:
        json.dump({"timestamp": stamp(), "event": "Status", "Flags": flags,
                   "Latitude": lat, "Longitude": lon, "Heading": heading,
                   "BodyName": BODY, "PlanetRadius": RADIUS}, handle)


def body_scan(name, distance_ls, planet_class, gravity_g, temp_k, landable=True,
              volcanism=""):
    return {"timestamp": stamp(3 * 3600 - 60), "event": "Scan", "ScanType": "Detailed",
            "BodyName": name, "StarSystem": SYSTEM, "DistanceFromArrivalLS": distance_ls,
            "PlanetClass": planet_class, "Landable": landable, "Volcanism": volcanism,
            "SurfaceGravity": gravity_g * 9.80665, "SurfaceTemperature": temp_k,
            "Radius": RADIUS if name == BODY else 1_400_000.0, "AtmosphereType": ""}


emit({"timestamp": stamp(4 * 3600), "event": "Fileheader", "part": 1,
      "language": "English/UK", "Odyssey": True, "gameversion": "4.4.1.1",
      "build": "r000000/r0 "},
     {"timestamp": stamp(4 * 3600), "event": "Commander", "FID": "F0000000",
      "Name": CMDR},
     {"timestamp": stamp(4 * 3600), "event": "LoadGame", "FID": "F0000000",
      "Commander": CMDR, "Horizons": True, "Odyssey": True, "Ship": "Type9",
      "ShipID": 7, "ShipName": "", "ShipIdent": "", "GameMode": "Open",
      "Credits": 412000000},
     {"timestamp": stamp(4 * 3600), "event": "Loadout", "Ship": "type9", "ShipID": 7,
      "ShipName": "", "ShipIdent": "", "CargoCapacity": 512, "Modules": []},
     {"timestamp": stamp(4 * 3600), "event": "Cargo", "Vessel": "Ship", "Count": 0,
      "Inventory": []},
     {"timestamp": stamp(4 * 3600), "event": "Powerplay", "Power": POWER,
      "Rank": 41, "Merits": 212480, "TimePledged": 9100000},
     *[{"timestamp": stamp(4 * 3600 - 400 * (n + 1)), "event": "FSDJump",
        "StarSystem": name, "SystemAddress": 908620436200 + n,
        "StarPos": [STAR_POS[0] + dx, STAR_POS[1] + dy, STAR_POS[2] + dz],
        **({"ControllingPower": power} if power else {}),
        "PowerplayState": state, "Powers": [p for p in (power, rival) if p]}
       for n, (name, (dx, dy, dz), power, state, rival) in enumerate(NEIGHBOURS)],
     {"timestamp": stamp(3 * 3600 - 5), "event": "Location", "Docked": False,
      "StarSystem": SYSTEM, "SystemAddress": 908620436162, "StarPos": STAR_POS,
      "Body": SYSTEM + " A", "BodyType": "Star", "ControllingPower": POWER,
      "PowerplayState": "Fortified", "Powers": [POWER, "Archon Delaine"]},
     body_scan(SYSTEM + " A 1", 212.4, "Rocky body", 0.08, 171.0),
     body_scan(SYSTEM + " A 2", 388.0, "Metal rich body", 0.31, 402.0,
               volcanism="minor metallic magma volcanism"),
     body_scan(BODY, 640.7, "High metal content body", 0.19, 214.0),
     body_scan(SYSTEM + " A 4", 1120.0, "Rocky body", 0.12, 188.0),
     body_scan(SYSTEM + " A 5", 2250.0, "Icy body", 0.42, 64.0, landable=False),
     {"timestamp": stamp(3 * 3600 - 40), "event": "SAASignalsFound",
      "BodyName": BODY, "Signals": [
          {"Type": "$SAA_SignalType_PlanetaryMiningLocation;",
           "Type_Localised": "Mining location", "Count": 7}]},
     {"timestamp": stamp(3 * 3600 - 35), "event": "SAASignalsFound",
      "BodyName": SYSTEM + " A 1", "Signals": [
          {"Type": "$SAA_SignalType_PlanetaryMiningLocation;",
           "Type_Localised": "Mining location", "Count": 3}]},
     {"timestamp": stamp(SESSION_S + 600), "event": "ApproachBody",
      "StarSystem": SYSTEM, "Body": BODY},
     {"timestamp": stamp(SESSION_S + 300), "event": "Touchdown",
      "PlayerControlled": True, "Latitude": HOME[0], "Longitude": HOME[1],
      "NearestDestination": "$SAA_Unknown_Signal:#type=$PlanetaryMiningLocation_Name;:#index=3;",
      "StarSystem": SYSTEM, "Body": BODY, "OnStation": False, "OnPlanet": True},
     {"timestamp": stamp(SESSION_S + 60), "event": "LaunchSRV", "SRVType": "mev_rhino",
      "SRVType_Localised": "SRV Rhino", "Loadout": "default", "ID": 1,
      "PlayerControlled": True})
# The run so far: a tonne refined every minute and a half or so, Iridium
# with some Rhodplumsite, and one trip back to the ship with 30 t.
_REFINED = [("Iridium", 26), ("Rhodplumsite", 9), ("Iridium", 12)]
_tick = SESSION_S
for _name, _count in _REFINED:
    for _ in range(_count):
        _tick -= 88
        emit({"timestamp": stamp(_tick), "event": "MiningRefined",
              "Type": "$%s_name;" % _name.lower(), "Type_Localised": _name})
    if _name == "Rhodplumsite":
        emit({"timestamp": stamp(_tick - 30), "event": "CargoTransfer", "Transfers": [
            {"Type": "iridium", "Type_Localised": "Iridium", "Count": 26,
             "Direction": "toship"},
            {"Type": "rhodplumsite", "Type_Localised": "Rhodplumsite", "Count": 4,
             "Direction": "toship"}]})
with open(os.path.join(JOURNALS, "Cargo.json"), "w", encoding="utf-8") as _f:
    json.dump({"timestamp": stamp(60), "event": "Cargo", "Vessel": "SRV", "Count": 17,
               "Inventory": [{"Name": "iridium", "Name_Localised": "Iridium", "Count": 12,
                              "Stolen": 0},
                             {"Name": "rhodplumsite", "Name_Localised": "Rhodplumsite",
                              "Count": 5, "Stolen": 0}]}, _f)
status(*HOME)


# -- the real app ----------------------------------------------------------------

import customtkinter  # noqa: E402,F401
import overlay as OV  # noqa: E402
# Whatever is in front of an X server with no window manager is not the game;
# "cannot tell" is the answer that keeps the boxes up.
OV.foreground_is_game = lambda: None
import edsmt as A     # noqa: E402
import survey as SV   # noqa: E402
import planview as PV  # noqa: E402

A.DATA_DIR = os.path.join(TMP, "data")
os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")
with open(A.SETTINGS_FILE, "w", encoding="utf-8") as _f:
    json.dump({"asked_to_share": True, "tour_done": True, "guide_done": True,
               "show_tips": False, "journal_dir": JOURNALS,
               "overlay_enabled": True, "overlay_hint_shown": 9,
               "community_share_cmdr_name": True, "rig_offset_m": 0,
               "golden_radius_m": 600}, _f)

app = A.EDSMT()
app.updates.check = lambda *args, **kwargs: None
# Nothing goes to the worker thread: every answer below is handed in by hand.
app.worker.submit = lambda tag, fn: None


def pump(times=4, wait=0.0):
    for _ in range(times):
        app.update_idletasks()
        app.update()
        if wait:
            time.sleep(wait)


def settle(seconds=1.0):
    until = time.time() + seconds
    while time.time() < until:
        pump(1)
        time.sleep(0.03)


app.geometry("1600x1000+0+0")
settle(1.5)


def grab(name, widget=None, box=None):
    """The screen, cropped to a window. Saved as OUT/raw-NAME.png."""
    from PIL import Image
    pump(6)
    full = os.path.join(TMP, "screen.png")
    subprocess.run(["import", "-silent", "-window", "root", full], check=True)
    image = Image.open(full).convert("RGB")
    if box is None and widget is not None:
        x, y = widget.winfo_rootx(), widget.winfo_rooty()
        box = (x, y, x + widget.winfo_width(), y + widget.winfo_height())
    if box is not None:
        image = image.crop(box)
    path = os.path.join(OUT, "raw-%s.png" % name)
    image.save(path)
    print("  saved", path, image.size)
    return path


# -- a signal, a drive round it, the finds and two rigs ---------------------------

def dest(lat, lon, bearing, metres):
    return SV.destination(lat, lon, bearing, metres, RADIUS)


def move(bearing, metres, heading=None):
    """Drive from where the app thinks you are; the app reads it back."""
    here = app.game
    lat, lon = dest(here.lat, here.lon, bearing, metres)
    status(lat, lon, bearing if heading is None else heading)
    app.game = app.watcher.poll()
    app.track_survey(app.game)


def go_to(lat, lon, step_m=60.0):
    """Drive in a straight line to a spot, a status update every step."""
    here = app.game
    away = SV.surface_range_m(here.lat, here.lon, lat, lon, RADIUS)
    bearing = SV.bearing_deg(here.lat, here.lon, lat, lon)
    steps = max(1, int(away // step_m))
    for _ in range(steps):
        move(bearing, away / steps)


PRICES = {"Iridium": 248300, "Rhodplumsite": 191600, "Sapphire": 141200,
          "Ruby": 118900, "Diamond": 139400}
# (bearing from the signal centre, metres, commodity, rigs, amount, density)
FINDS = [(32, 640, "Iridium", "4", "High", "High"),
         (43, 705, "Iridium", "3", "High", "Medium"),
         (24, 760, "Iridium", "2", "Medium", "High"),
         (52, 585, "Rhodplumsite", "3", "High", "Medium"),
         (37, 840, "Sapphire", "2", "High", "Low"),
         (118, 900, "Sapphire", "2", "High", "Low"),
         (152, 1180, "Ruby", "1", "Medium", "Medium"),
         (205, 980, "Iridium", "3", "Depleted", "High"),
         (262, 1320, "Diamond", "2", "Low", "Low")]


RIG_SAID = []                          # what the app said as rig 2 went down


def build_session():
    app.market_prices = lambda: dict(PRICES)
    app.game = app.watcher.poll()
    app.log_location()                                  # signal 3, centre here
    for bearing, metres, commodity, rigs, amount, density in FINDS:
        lat, lon = dest(HOME[0], HOME[1], bearing, metres)
        app.store.add_deposit(system=SYSTEM, body=BODY, location="3",
                              commodity=commodity, rigs=rigs, amount=amount,
                              density=density, lat="%.6f" % lat, lon="%.6f" % lon,
                              cmdr=CMDR)
    app.refresh_deposits()
    # The drive: out west and round to the north-east patch.
    for bearing, metres in ((270, 900), (330, 700), (20, 600), (60, 500),
                            (110, 300)):
        steps = int(metres // 60)
        for _ in range(steps):
            move(bearing, metres / steps)
    # To the best Iridium and two rigs down on it, 40 m apart.
    lat, lon = dest(HOME[0], HOME[1], 32, 640)
    go_to(lat, lon, 40.0)
    app.drop_rigs()
    move(75, 85.0)
    app.drop_rigs()
    RIG_SAID[:] = list(getattr(app, "_last_said", None) or ())
    move(160, 60.0)
    move(200, 36.0, heading=300)
    app.redraw()
    settle(1.0)


def overlay_off():
    app.settings["overlay_enabled"] = False
    app.overlay.hide()
    settle(0.4)


def shot_map():
    """The main window: the deposit map with the trail, the golden group and
    the rig radar's rings."""
    overlay_off()
    app.deiconify()
    app.geometry("1600x1000+0+0")
    settle(0.8)
    app.plan._extent = 640.0
    app.refresh_locations()
    app.refresh_deposits()
    app.redraw()
    if RIG_SAID:
        app.say(*RIG_SAID)               # the app's own words, put back
    settle(1.0)
    return grab("map", app)


# The overlay boxes, laid out close together for the picture. Fractions of
# the screen, the way Settings stores a layout.
SHOT_LAYOUT = {
    OV.STRIP:   {"x": 0.004, "y": 0.004, "w": 0.505, "h": 0.100},
    OV.RADAR:   {"x": 0.004, "y": 0.116, "w": 0.255, "h": 0.408},
    OV.TARGETS: {"x": 0.266, "y": 0.116, "w": 0.243, "h": 0.170},
}


def shot_overlay():
    """The boxes the overlay puts over the game: compass, scope and
    targets. Each is its own window; they are grabbed off the screen as
    they stand, with nothing behind them."""
    app.withdraw()
    layout = dict(app.settings.get("overlay_layout") or {})
    layout.update({k: dict(v) for k, v in SHOT_LAYOUT.items()})
    app.settings.update(overlay_enabled=True, overlay_layout=layout,
                        overlay_show_strip=True, overlay_show_radar=True,
                        overlay_show_targets=True, overlay_show_status=False,
                        overlay_show_guide=False, overlay_show_deposit=False,
                        overlay_flash=False)
    app.overlay.hide()
    settle(0.3)
    app.overlay.show()
    app.overlay.set_zoom(2)
    settle(3.5)                       # any flash from the rig keys is gone
    app.redraw()
    settle(0.6)
    boxes = [p.window for p in app.overlay.panels.values() if p.alive()]
    left = min(w.winfo_rootx() for w in boxes) - 12
    top = min(w.winfo_rooty() for w in boxes) - 12
    right = max(w.winfo_rootx() + w.winfo_width() for w in boxes) + 12
    bottom = max(w.winfo_rooty() + w.winfo_height() for w in boxes) + 12
    path = grab("overlay", box=(max(0, left), max(0, top), right, bottom))
    overlay_off()
    app.deiconify()
    return path


# -- markets read, earlier sessions, merits learnt ---------------------------------

# Boards the commander has read: (system, station, type, pad, hours ago, prices)
BOARDS = [
    (SYSTEM, STATION, "Coriolis", "L", 3.2,
     {"Iridium": (248300, 6120), "Rhodplumsite": (191600, 2310),
      "Sapphire": (141200, 880), "Ruby": (118900, 1290)}),
    ("Phrua Aowsy FG-X d1-88", "Ishida Hub", "Orbis", "L", 20.5,
     {"Iridium": (262900, 3480), "Rhodplumsite": (184100, 1020)}),
]


def seed_books():
    for system, station, kind, pad, hours, items in BOARDS:
        app.market_book.note_market({
            "system": system, "station": station, "when": stamp(hours * 3600),
            "station_type": kind, "pad": pad,
            "items": [{"commodity": name, "sell": sell, "demand": demand}
                      for name, (sell, demand) in items.items()]})
    # The merit rate, learnt from four sales. Made-up figures for the
    # picture - not anybody's real rate.
    app.merits.pairs = [
        {"when": stamp(86400 * days), "credits": credits, "merits": merits,
         "commodity": what, "tonnes": tonnes}
        for days, credits, merits, what, tonnes in (
            (6.2, 61204400, 12976, "Iridium", 241), (4.1, 48877000, 10411, "Iridium", 196),
            (3.0, 22910800, 4170, "Rhodplumsite", 120), (1.9, 30112400, 5390, "Rhodplumsite", 158))]
    # Earlier Rhino sessions, for the table under the one running now.
    history = [
        (1.2, 2.4, "Phrua Aowsy KD-B c14-7", "A 3", "Iridium:71;Rhodplumsite:18",
         "Iridium:71;Rhodplumsite:18", 21065100, STATION),
        (2.1, 1.6, "Phrua Aowsy FG-X d1-88", "B 2 a", "Iridium:52",
         "Iridium:52", 13671000, "Ishida Hub"),
        (3.0, 2.9, "Phrua Aowsy LY-Z b45-2", "1 b", "Rhodplumsite:84;Ruby:22",
         "Rhodplumsite:84;Ruby:22", 18749200, STATION),
        (4.8, 1.1, "Phrua Aowsy KD-B c14-7", "A 1", "Sapphire:31;Ruby:9",
         "Sapphire:31;Ruby:9", 5428600, STATION),
        (6.2, 3.3, "Phrua Aowsy KD-B c14-7", "A 3", "Iridium:96;Sapphire:14",
         "Iridium:96;Sapphire:14", 25811900, "Ishida Hub"),
    ]
    for days, hours, system, body, mined, sold, credits, station in history:
        row = {key: "" for key in SV.SESSION_FIELDS}
        start = NOW - days * 86400
        row.update({"id": "past%d" % int(days * 10), "kind": SV.RHINO,
                    "started": stamp(days * 86400),
                    "ended": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                           time.gmtime(start + hours * 3600)),
                    "system": system, "body": "%s %s" % (system, body),
                    "station": station, "sold_in": SYSTEM if station == STATION
                    else "Phrua Aowsy FG-X d1-88",
                    "mined": mined, "transferred": mined, "sold": sold,
                    "credits": str(credits), "cost": "0", "sales": "1",
                    "trips": "2", "cmdr": CMDR})
        row["closed"] = row["ended"]
        app.earnings.sessions.append(row)
    app.earnings.save()


def quote(commodity, rows):
    """The community map's answer for one commodity, as the app files it."""
    app.quote_asked = {"system": SYSTEM, "radius": 50, "at": time.time(),
                       "wanted": ["Iridium", "Rhodplumsite"]}
    app.take_quote(True, json.dumps({"commodity": commodity, "market": rows,
                                     "community": []}))


SELL_ROWS = {
    "Iridium": [
        {"commodity": "Iridium", "station": "Ishida Hub", "system": "Phrua Aowsy FG-X d1-88",
         "distance_ly": 13.5, "sell": 262900, "demand": 3480, "seen": stamp(20.5 * 3600),
         "source": "community", "pad": "L", "station_type": "Orbis"},
        {"commodity": "Iridium", "station": STATION, "system": SYSTEM, "distance_ly": 0.0,
         "sell": 248300, "demand": 6120, "seen": stamp(3.2 * 3600),
         "source": "community", "pad": "L", "station_type": "Coriolis"},
        {"commodity": "Iridium", "station": "Varga Orbital", "system": "Phrua Aowsy MT-K c13-21",
         "distance_ly": 17.0, "sell": 271400, "demand": 1840, "seen": stamp(9 * 3600),
         "source": "market", "pad": "L", "station_type": "Ocellus"},
        {"commodity": "Iridium", "station": "Hollis Dock", "system": "Phrua Aowsy LY-Z b45-2",
         "distance_ly": 9.8, "sell": 255000, "demand": 920, "seen": stamp(14 * 3600),
         "source": "market", "pad": "M", "station_type": "Outpost"},
        {"commodity": "Iridium", "station": "Kerr Point", "system": "Phrua Aowsy WE-G b46-0",
         "distance_ly": 18.0, "sell": 266750, "demand": 2210, "seen": stamp(26 * 3600),
         "source": "market", "pad": "L", "station_type": "Coriolis"},
        {"commodity": "Iridium", "station": "Q7T-41B", "system": "Phrua Aowsy BA-R b48-1",
         "distance_ly": 7.5, "sell": 259500, "demand": 500, "seen": stamp(2 * 3600),
         "source": "market", "pad": "L", "station_type": "FleetCarrier"},
    ],
    "Rhodplumsite": [
        {"commodity": "Rhodplumsite", "station": STATION, "system": SYSTEM, "distance_ly": 0.0,
         "sell": 191600, "demand": 2310, "seen": stamp(3.2 * 3600),
         "source": "community", "pad": "L", "station_type": "Coriolis"},
        {"commodity": "Rhodplumsite", "station": "Varga Orbital",
         "system": "Phrua Aowsy MT-K c13-21", "distance_ly": 17.0, "sell": 203800,
         "demand": 760, "seen": stamp(9 * 3600), "source": "market", "pad": "L",
         "station_type": "Ocellus"},
        {"commodity": "Rhodplumsite", "station": "Ishida Hub",
         "system": "Phrua Aowsy FG-X d1-88", "distance_ly": 13.5, "sell": 184100,
         "demand": 1020, "seen": stamp(20.5 * 3600), "source": "community", "pad": "L",
         "station_type": "Orbis"},
        {"commodity": "Rhodplumsite", "station": "Bremner Base",
         "system": "Phrua Aowsy QJ-P a72-4", "distance_ly": 24.8, "sell": 209300,
         "demand": 410, "seen": stamp(31 * 3600), "source": "market", "pad": "M",
         "station_type": "CraterOutpost"},
    ],
}


def shot_find():
    """Find: best sell prices for the two commodities aboard, filtered."""
    app.settings["find_unlocked"] = True
    app.open_find()
    settle(1.0)
    finder = app.finder
    finder.geometry("1500x640+0+0")
    finder.commodity.set("Iridium, Rhodplumsite")
    finder.within.set("50 Ly") if "50 Ly" in finder.within.cget("values") else None
    filters = finder._filters
    filters.pad_box.set("L only")
    filters.age_box.set("3 days")
    filters.show_box.set("Best five payers per commodity")
    filters.changed()
    rows = SELL_ROWS["Iridium"] + SELL_ROWS["Rhodplumsite"]
    finder._asked = ["Iridium", "Rhodplumsite"]
    finder.results("sell", json.dumps({"commodity": "Iridium",
                                       "commodities": ["Iridium", "Rhodplumsite"],
                                       "market": rows, "community": []}), True)
    settle(1.2)
    path = grab("find", finder)
    finder.destroy()
    settle(0.3)
    return path


def shot_land():
    """Where to land: this system's bodies, ranked."""
    app.community.grounds = lambda: True
    app.community.system_sites = lambda system: True
    lander = app.open_land()
    settle(0.8)
    lander.geometry("1720x660+0+0")
    app.take_grounds(True, json.dumps({"count": 3, "grounds": [
        {"ground": "High metal content body", "sites": 41, "commodities": [
            {"name": "Iridium", "sites": 29, "share": 0.71, "rigs": 118},
            {"name": "Rhodplumsite", "sites": 17, "share": 0.41, "rigs": 52},
            {"name": "Sapphire", "sites": 14, "share": 0.34, "rigs": 37}]},
        {"ground": "Rocky body", "sites": 63, "commodities": [
            {"name": "Rhodplumsite", "sites": 30, "share": 0.48, "rigs": 96},
            {"name": "Ruby", "sites": 22, "share": 0.35, "rigs": 54},
            {"name": "Monazite", "sites": 19, "share": 0.30, "rigs": 61}]},
        {"ground": "Metal rich body", "sites": 18, "commodities": [
            {"name": "Iridium", "sites": 11, "share": 0.61, "rigs": 40},
            {"name": "Diamond", "sites": 6, "share": 0.33, "rigs": 14}]}]}))
    app.take_landing(True, json.dumps({"system": SYSTEM, "count": 2, "sites": [
        {"system": SYSTEM, "planet": BODY, "spot": "3", "rigs": 15,
         "types": ["Iridium", "Rhodplumsite"], "worked_out": False,
         "status": "reported", "uploader": "CMDR Example"},
        {"system": SYSTEM, "planet": SYSTEM + " A 1", "spot": "2", "rigs": 7,
         "types": ["Rhodplumsite", "Ruby"], "worked_out": False,
         "status": "reported", "uploader": ""}]}))
    settle(1.2)
    path = grab("land", lander)
    lander.destroy()
    settle(0.3)
    return path


def shot_powerplay():
    """Powerplay: where selling what is aboard counts for the pledge."""
    window = app.open_powerplay()
    settle(0.8)
    window.geometry("1500x820+0+0")
    window.follow(force=True)
    settle(1.0)
    path = grab("powerplay", window)
    window.destroy()
    settle(0.3)
    return path


def shot_earnings():
    """Earnings: the session running now first, then the ones before."""
    app.open_earnings()
    settle(1.0)
    ledger = app.ledger
    ledger.geometry("1900x900+0+0")
    for commodity in ("Iridium", "Rhodplumsite"):
        quote(commodity, SELL_ROWS[commodity])
    ledger.refresh()
    settle(1.5)
    path = grab("earnings", ledger)
    ledger.destroy()
    settle(0.3)
    return path


def shot_picture():
    """The map picture EDSMT saves when the Rhino docks, for Discord."""
    result = app.picture_now(save=False)
    if result["image"] is None:
        raise SystemExit("no map picture: %s" % result["why"])
    path = os.path.join(OUT, "raw-session-map.png")
    result["image"].save(path)
    print("  saved", path, result["image"].size)
    return path


# -- the pictures the project uses ---------------------------------------------

# raw name -> published name
PUBLISHED = {"map": "map", "overlay": "overlay", "session-map": "session-map",
             "find": "find", "land": "where-to-land", "powerplay": "powerplay",
             "earnings": "earnings"}
README_LIMIT = 400 * 1024


def readme_png(image, path):
    """A PNG for the README under README_LIMIT: lossless if it fits, else
    the same picture on a 256-colour palette, which a flat-coloured window
    loses next to nothing to."""
    image.save(path, optimize=True)
    if os.path.getsize(path) > README_LIMIT:
        image.quantize(256, dither=0).save(path, optimize=True)
    if os.path.getsize(path) > README_LIMIT:
        raise SystemExit("%s is still %d KB" % (path, os.path.getsize(path) // 1024))
    return path


def site_jpg(image, path, width=None):
    """A JPEG for the web page, `width` wide or as captured. Full-resolution
    colour, not subsampled: coloured text goes soft without it."""
    if width and image.width > width:
        image = image.resize((width, round(image.height * width / image.width)),
                             resample=3)    # bicubic
    image.save(path, quality=90, subsampling=0, optimize=True, progressive=True)
    return path


def publish(raw_paths):
    from PIL import Image
    docs = os.path.join(REPO, "docs", "images")
    site = os.path.join(REPO, "site")
    os.makedirs(docs, exist_ok=True)
    for raw in raw_paths:
        key = os.path.basename(raw)[len("raw-"):-len(".png")]
        name = PUBLISHED[key]
        image = Image.open(raw).convert("RGB")
        for path in (readme_png(image, os.path.join(docs, name + ".png")),
                     site_jpg(image, os.path.join(site, "edsmt-%s-full.jpg" % name)),
                     site_jpg(image, os.path.join(site, "edsmt-%s-800.jpg" % name), 800)):
            print("  %-48s %4d KB" % (os.path.relpath(path, REPO),
                                     os.path.getsize(path) // 1024))


def main():
    build_session()
    seed_books()
    shots = [shot_map(), shot_overlay(), shot_picture(), shot_find(),
             shot_land(), shot_powerplay(), shot_earnings()]
    print("%d pictures in %s" % (len(shots), OUT))
    app.destroy()
    if PUBLISH:
        publish(shots)


if __name__ == "__main__":
    main()
