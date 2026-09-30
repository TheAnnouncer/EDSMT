"""
EDSMT - surface mining survey for the Rhino.

One window. It follows the game, so the layout is built around where you are
right now rather than around a filing cabinet you browse: a telemetry strip
across the top, the sites on this body down the left with the capture
controls under them, and the site itself drawn to scale in the middle with
you on it.

The plan view is the point. A picture you navigate by - north up, the site
centre at the origin, you as an arrow, deposits as pins with their range in
metres - beats a chart you read and then translate into driving. It is drawn
on a plain canvas, which also means no plotting library aboard: the program
starts in about a second instead of ten, and the download is a fraction of
the size.
"""

import os
import re
import sys
import csv
import json
import math
import queue
import inspect
import ctypes
import secrets
import threading
import time
import tkinter as tk

import customtkinter as ctk

import survey as SV
import planview as PV
import journal as JN
import edonline as EDO
import overlay as OV
import coverage as CV
import rigplan as RP

ctk.set_appearance_mode("Dark")

APP_NAME = "EDSMT"
APP_TITLE = "EDSMT - Surface Mining Survey"
APP_VERSION = EDO.APP_VERSION

# Cockpit palette, taken from radioraxxla.com so the tool and the site look
# like the same operation.
#
# Every colour in this file comes from here. It did not before: eleven
# different button colours accumulated one window at a time - blue ones,
# grey ones, maroon ones - because each was typed where it was needed, and
# nothing on screen told you which button was the one you could not undo.
VOID = "#0b0705"         # the window behind everything
PANEL = "#15100b"        # a panel on it
RAIL = "#1b130c"         # the left rail and the top strip
STEEL = "#241a10"        # a control sitting on either of those
RULE = "#3d2404"         # hairlines, borders, and a pressed-in hover
ORANGE = "#ff7a18"       # the instrument colour: live, selected, now
AMBER = "#ffb545"        # its highlight, and every section label
TEXT = "#e9dccd"         # readable
MUTED = "#b49b80"        # readable, one step back
DIM = "#9c6a3c"          # a hint, a unit, a caption
FAINT = "#6d4826"        # the dimmest thing on the map that is still a word
GRID = "#1e1409"         # the crosshair under the plan view
GREEN = "#35d07f"        # it worked
SWEPT = "#12292b"        # ground the scanner has already been over
RED = "#d1483a"          # it did not, or it cannot be undone
CYAN = "#37c6d4"         # telemetry off the game, as opposed to off the disk
WARN = "#6b4a1f"         # a state change worth noticing
DANGER = "#5a3330"       # a destruction

# The type scale. Consolas throughout, ten steps, and no size typed anywhere
# else. There were twelve different font tuples scattered through this file
# and no two screens agreed on what a section heading was.
FONT = "Consolas"
F_TITLE = (FONT, 20, "bold")      # the app's own name, once
F_HEAD = (FONT, 15, "bold")       # where you are; a window's subject
F_ACTION = (FONT, 14, "bold")     # MARK DEPOSIT, and nothing else
F_SECTION = (FONT, 13, "bold")    # every HUD section label
F_READOUT = (FONT, 12)            # instrument values and the status strip
F_STRONG = (FONT, 11, "bold")     # a button with a job
F_BODY = (FONT, 11)               # labels, fields, prose
F_SMALL = (FONT, 10)              # the hint under a control
F_SMALL_B = (FONT, 10, "bold")    # a column heading in a dense table
F_MICRO = (FONT, 9)               # map ticks, and the copy buttons

def _style_table():
    """Every widget style, built from the colours as they are right now.

    A function, so a theme can re-point the colours and have the styles
    follow - see apply_app_theme. The names below are the same dicts for
    the life of the app; a theme changes what is in them.
    """
    return dict(
        # One visual language for buttons, in seven roles. Four are solid
        # and say what pressing them costs; three are ghosts that live
        # inside a list or a table and must not shout over their own
        # contents.
        BTN_PRIMARY=dict(fg_color=ORANGE, hover_color=AMBER, text_color=VOID,
                         corner_radius=0),
        BTN_SECONDARY=dict(fg_color=STEEL, hover_color=RULE, text_color=AMBER,
                           border_width=1, border_color=RULE, corner_radius=0),
        BTN_WARN=dict(fg_color=WARN, hover_color=AMBER, text_color=TEXT,
                      border_width=1, border_color=AMBER, corner_radius=0),
        BTN_DANGER=dict(fg_color=DANGER, hover_color=RED, text_color=TEXT,
                        border_width=1, border_color=RED, corner_radius=0),
        BTN_ROW=dict(fg_color="transparent", hover_color=RULE, text_color=TEXT,
                     corner_radius=0),
        BTN_GHOST=dict(fg_color="transparent", hover_color=RULE, text_color=DIM,
                       corner_radius=0),
        BTN_HEADING=dict(fg_color="transparent", hover_color=RULE,
                         text_color=ORANGE, corner_radius=0),
        # And the same for the things you type into. Left to itself
        # customtkinter draws these in its own blue-grey, which is the
        # single loudest reason the window did not look like the site.
        BOX=dict(fg_color=VOID, border_color=RULE, button_color=RULE,
                 button_hover_color=ORANGE, text_color=TEXT,
                 dropdown_fg_color=PANEL, dropdown_hover_color=RULE,
                 dropdown_text_color=TEXT, corner_radius=0),
        ENTRY=dict(fg_color=VOID, border_color=RULE, text_color=TEXT,
                   placeholder_text_color=FAINT, corner_radius=0),
        SWITCH=dict(fg_color=RULE, progress_color=ORANGE, button_color=MUTED,
                    button_hover_color=AMBER, text_color=TEXT),
        TEXTBOX=dict(fg_color=VOID, border_color=RULE, text_color=TEXT,
                     border_width=1, corner_radius=0),
        LIST=dict(fg_color=PANEL, border_color=RULE, border_width=1,
                  corner_radius=0, scrollbar_button_color=RULE,
                  scrollbar_button_hover_color=ORANGE),
    )


_STYLES = _style_table()
BTN_PRIMARY = _STYLES["BTN_PRIMARY"]
BTN_SECONDARY = _STYLES["BTN_SECONDARY"]
BTN_WARN = _STYLES["BTN_WARN"]
BTN_DANGER = _STYLES["BTN_DANGER"]
BTN_ROW = _STYLES["BTN_ROW"]
BTN_GHOST = _STYLES["BTN_GHOST"]
BTN_HEADING = _STYLES["BTN_HEADING"]
BOX = _STYLES["BOX"]
ENTRY = _STYLES["ENTRY"]
SWITCH = _STYLES["SWITCH"]
TEXTBOX = _STYLES["TEXTBOX"]
LIST = _STYLES["LIST"]


def apply_app_theme(name):
    """Dress the main window in one of the overlay's palettes.

    Called before the window is built, which is why a new app theme needs a
    restart: a Tk widget keeps the colours it was made with. Every colour
    name above is re-pointed and every style dict is refilled in place, so
    anything built after this wears the theme. Returns the theme's name.
    """
    full = OV.theme_palette(name)
    globals().update({key: full[key] for key in OV.PALETTE_KEYS})
    for style, values in _style_table().items():
        target = globals()[style]
        target.clear()
        target.update(values)
    chosen = str(name or "cockpit").strip().lower()
    return chosen if chosen in OV.PALETTES else "cockpit"


MAX_RIGS = 6

# How often another commander's finds on the body you are on are asked for
# again, and how long an unanswered ask waits before trying once more.
SHARED_REFRESH_S = 600
SHARED_WAIT_S = 60

# A shared find within this of one of your own, same commodity, is yours
# coming back from the server - the server buckets positions at about 35 m.
SAME_FIND_M = 40.0

# How close you have to be to a deposit you marked for UPDATE to find it,
# and for MARK to ask whether you meant to mark it again. A deposit's rigs
# sit about sixty metres apart, so this is one patch, not the next one.
SAME_DEPOSIT_M = 100.0
# A deposit of another commodity this close is the same spot: MARK asks
# whether to rename it or add a second one - see mark_deposit. Tighter than
# SAME_DEPOSIT_M, because two commodities a patch apart are real; two at the
# same parking spot are nearly always one rock with the wrong name.
RETYPE_M = 25.0
# Standing this close to a logged signal's centre, LOG SIGNAL means that one,
# whatever the Signal box says. Two mining locations can sit a few km apart,
# so this is tighter than being "at" a signal.
SAME_SIGNAL_M = 1500.0
# ...and UPDATE does the rename for this long after the question.
RETYPE_WAIT_S = 60.0

# How wide one table cell may get before its text wraps, in pixels. Enough
# for a system name like "Col 285 Sector ZL-K b22-2" on one line.
CELL_WRAP = 260

# Rows a result table draws at a time. Five hundred individual deposits,
# each a dozen toolkit widgets, took long enough to draw that the window
# looked hung. A page appears at once; the rest are one click away.
PAGE_ROWS = 100
DENSITY_LEVELS = list(SV.DENSITY_TIERS)      # how concentrated: Low/Medium/High
AMOUNT_LEVELS = list(SV.AMOUNT_TIERS)       # how much is left, down to Depleted

# The game numbers the mining location signals it finds on a body, and a
# well-stocked body runs into the forties. This is only how many the picker
# offers before it grows: it takes the highest of this, what the DSS actually
# reported, and the highest number already logged here - and the box is
# typeable, so a number beyond all three still goes in. A hard cap is the
# same mistake as a commodity whitelist, and it fails the same way: refusing
# to record something real because a number was guessed too low.
MAX_LOCATIONS = 40

# The left rail. Wide enough for its widest button at 10pt Consolas with a
# little to spare, because a clipped button is unusable and a label that
# has to be guessed at is worse than no label. The scrollbar gets its own
# pixels on top rather than eating into the controls.
RAIL_WIDTH = 384
SCROLLBAR_W = 18

# Find's results table. The copy buttons live in the FIRST column, not the
# last: a table with eight columns of system names is wider than any window
# anybody runs, and a control on the far right of it is one nobody will ever
# see. They were there all along and invisible, which is worse than absent.
COPY_COLUMN = 0
# The top bar's readouts need this much room to say where you are and who
# you are without being cut off mid-word; below it the buttons move under.
TOP_READOUT_ROOM = 420
# Two presses of RIG DOWN this close together are one rig pressed twice.
RIG_SAME_M = 8.0
# The rig planner (beta). A rig within PLAN_PIN_DONE_M of a pin is on it;
# the scope closes in on the plan while any pin is within PLAN_NEAR_M; a
# trace not closed in PLAN_TRACE_MAX_S is given up on.
PLAN_PIN_DONE_M = 20.0
PLAN_NEAR_M = 600.0
PLAN_TRACE_MAX_S = 20 * 60
PLAN_SPACING_MIN_M = 20.0
PLAN_SPACING_MAX_M = 500.0
# The wing link (beta): a beat every WING_BEAT_S; a wingmate not heard from
# for WING_STALE_S is taken off the scope. A code is six characters; the
# ones EDSMT makes up leave out I, O, 0 and 1, which are read out wrong.
WING_BEAT_S = 4.0
# A second press on the same Earnings row inside this long deletes it.
DELETE_CONFIRM_S = 6
# The demand a Community Goal station shows: a placeholder, not a market.
PLACEHOLDER_DEMAND = 999999
WING_STALE_S = 30.0
WING_CODE_RE = re.compile(r"^[A-Z2-9]{6}$")
WING_CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _same_place(a, b):
    return str(a or "").strip().lower() == str(b or "").strip().lower() != ""


def new_wing_code():
    return "".join(secrets.choice(WING_CODE_CHARS) for _ in range(6))


def clean_wing_code(text):
    """A wing code as typed - "abc 234" - as the server takes it, or ""."""
    code = re.sub(r"[^A-Za-z0-9]", "", str(text or "")).upper()
    return code if WING_CODE_RE.match(code) else ""
# The game warns at 4 km from the Rhino and destroys a rig at 5 km - tested
# twice to the metre on 4.4.1.1 by the community field guide, and what the
# testers see. The last warning goes up 200 m short of the loss; past the
# loss the rig is gone and stops being watched.
RIG_FINAL_M = 4800.0
RIG_LOST_M = 5000.0
# A rig goes down on a deposit, so the deposit it is on names what it is
# mining. A marked deposit within this of the SRV is taken to be that one.
RIG_ON_DEPOSIT_M = 400.0
# Refined tonnes are written to disk this often while mining, not per tonne.
REFINED_SAVE_S = 20.0
# How often the keys are read and the compass and scope redrawn, in ms. The
# rest of the app ticks at 700 ms; these two are what you steer by.
FAST_TICK_MS = 100
# ...and shown in the details and the deposit list once none has come in
# for this long: after the laser stops, not once a tonne.
TONNES_QUIET_S = 4.0
# The Inara key and the staff token are shown as this until Show is pressed,
# and go back to it by themselves this many seconds later.
MASK = "•"
REVEAL_S = 20
DATA_COLUMN_0 = 1

# How many rows to ask the server for. 50 was the client default and the
# only thing the user ever saw, on a database with thousands of finds in
# it. The server caps at 500; ask for the cap and say so when it is hit,
# rather than quietly showing a fiftieth of the map.
SEARCH_LIMIT = 500

# How far out to look for somebody else's find. The galaxy has roughly 400
# billion systems in it, so an unbounded search does not return the best
# site - it returns the best site in a place nobody will ever travel to.
# 500 Ly is a couple of minutes in a jump-capable ship and roughly the
# distance a commander will actually move to reach a good patch.
DISTANCE_CHOICES = {
    "50 Ly": 50, "100 Ly": 100, "250 Ly": 250, "500 Ly": 500,
    "1000 Ly": 1000, "Anywhere": 0,
}
DEFAULT_DISTANCE = "500 Ly"
NO_DISTANCE_LIMIT = "Anywhere"

# Who broke it before anyone else had to. Kept as a constant so adding the
# next name is one line and never touches the window code.
BETA_TESTERS = [
    "CMDR MJH430", "CMDR StarTopaz", "CMDR Flossy", "CMDR Gamer Joe",
    "CMDR Rumphrend",
]

# What a find is credited to when the commander who shared it chose not to
# put their name on it. That is a setting, not a fault, so the word has to
# read as a deliberate answer rather than as a blank the app failed to fill.
ANONYMOUS = "anonymous"

# Which worker tags belong to the Find window. Named here because the app
# routes on this list and the window switches on it, and an endpoint added
# to one but not the other is answered by the server, collected, and
# silently dropped - the window sits on "Searching..." for ever with
# nothing wrong anywhere.
FIND_TAGS = ("search", "sites", "intact", "market", "sell",
             "commodities", "verify")

# The result kinds that are somebody's FIND. Worked-out and verified are
# properties of a patch in the ground; a station selling ore has neither,
# so those two filters must not be let anywhere near a price table.
FIND_KINDS = ("sites", "search", "intact")

# And the ones that are a price. The system/body box means "near here" on
# these, so filtering the answer by the word that produced it would throw
# away every market that is not literally called Sol.
PRICE_KINDS = ("market", "sell")

# The commodity colours. Chosen to stay apart at 6px on a dark ground, and
# assigned by name so a commodity keeps its colour between sites.
COMMODITY_COLOURS = [
    "#ff7a18", "#37c6d4", "#8ad14b", "#e05fa8", "#f2c94c",
    "#7f9cf5", "#f2765b", "#5fd0a8", "#c58af9", "#e8d9c8",
    "#4fb0e0", "#d99a4a", "#9ee8c8",
]


def colour_for(name):
    """A stable colour per commodity, so it looks the same at every site."""
    known = SV.canonical(name)
    if not known:
        return DIM
    return COMMODITY_COLOURS[sum(ord(c) for c in known.lower()) % len(COMMODITY_COLOURS)]


def hud_header(parent, text, trailing=None, padx=14, pady=(12, 2)):
    """A section label, drawn the way the site draws them.

    A short bright tick, the name in caps, then a hairline out to the right
    edge. EVERY section in the app comes through here. They were built by
    hand before, one window at a time, and drifted into three different
    sizes and two different colours - which is what a "section heading"
    looking like ordinary text does to a screen you read at a glance.

    `trailing` builds a control that belongs on the same line. It is packed
    BEFORE the rule is allowed to expand, because the other order gives the
    rule everything and pushes the control off the edge - the complaint
    this app has had more often than any other.
    """
    bar = ctk.CTkFrame(parent, fg_color="transparent")
    bar.pack(fill="x", padx=padx, pady=pady)
    ctk.CTkFrame(bar, width=4, height=15, fg_color=ORANGE,
                 corner_radius=0).pack(side="left", padx=(0, 8))
    ctk.CTkLabel(bar, text=str(text).upper(), font=F_SECTION,
                 text_color=AMBER, anchor="w").pack(side="left")
    if trailing is not None:
        trailing(bar).pack(side="right", padx=(10, 0))
    ctk.CTkFrame(bar, height=1, fg_color=RULE).pack(side="left", fill="x",
                                                    expand=True, padx=(10, 0))
    return bar


def credits_text(value):
    """Credits with the thousands marked, the way the game writes them.

    2140000 is a number you have to count the digits of. 2,140,000 is one
    you read. Every figure in this app that is money goes through here, so
    the strip and the ledger cannot drift into two different habits.
    """
    try:
        return "{:,}".format(int(round(float(value or 0))))
    except (TypeError, ValueError):
        return "0"


def duration_text(hours):
    """A run's length in hours and minutes, not in decimal hours.

    sessions.csv keeps the raw timestamps because a spreadsheet wants
    those. Nobody reads "1.37 hours" off a screen and knows how long they
    have been out.
    """
    try:
        minutes = int(round(float(hours or 0) * 60))
    except (TypeError, ValueError):
        return "0m"
    if minutes < 60:
        return "%dm" % minutes
    return "%dh %02dm" % divmod(minutes, 60)


def bracket(panel, colour=None, arm=14, weight=2):
    """Put HUD corner brackets on a panel.

    Four L shapes, made of eight thin frames placed over the corners. There
    is no canvas here and a canvas inside every panel would cost more than
    the look is worth; place() floats them above the packed contents without
    disturbing the layout underneath.

    Not for a scrollable frame - its children belong to the inner scrolling
    surface, so the corners would slide away with the content.
    """
    colour = colour or RULE
    for relx in (0.0, 1.0):
        for rely in (0.0, 1.0):
            anchor = ("n" if rely == 0.0 else "s") + ("w" if relx == 0.0 else "e")
            for width, height in ((arm, weight), (weight, arm)):
                ctk.CTkFrame(panel, width=width, height=height,
                             fg_color=colour, corner_radius=0
                             ).place(relx=relx, rely=rely, anchor=anchor)
    return panel


def attr(obj, name, fallback=None):
    """An attribute that was really assigned, or the fallback.

    getattr() is not enough here. Every caller below is a Tk widget
    subclass guarding "has this part of the window been built yet", and
    anything carrying a catch-all __getattr__ - Tk's own option
    machinery, and the headless stubs the tests run under - answers a
    name that was never assigned with something truthy. The guard then
    passes and the next line calls .configure() on it. Only the instance
    dictionary tells the truth, so that is what gets asked.
    """
    return obj.__dict__.get(name, fallback)


def is_colour(text):
    """#rrggbb, and nothing else.

    A colour Tk cannot parse does not fail where it was typed - it fails
    later, on the window that tries to draw with it, which in the overlay's
    case is a window with no status line to complain on.
    """
    text = str(text or "").strip()
    return (len(text) == 7 and text.startswith("#")
            and all(c in "0123456789abcdefABCDEF" for c in text[1:]))


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def flash_lines(text, width=30):
    """A status sentence as a flash: a short heading, the rest under it.

    The heading breaks at a word, never mid-word, and the detail takes the
    rest of the first sentence. ("", "") for nothing to say.
    """
    first = str(text or "").strip().split(". ")[0].strip().rstrip(".")
    if not first:
        return "", ""
    if len(first) <= width:
        return first.upper(), ""
    cut = first.rfind(" ", 0, width)
    cut = cut if cut > 0 else width
    return first[:cut].upper(), first[cut:].strip()[:64]


def parse_metres(text):
    """A distance as a person types it, in metres. None if it is not one.

    3950, 3,950, 3950 m, 3950m and 3.95 km all mean the same. A bare number
    under 20 is taken as kilometres - nobody wants warning five metres from
    a rig, and "4" or "3.95" is someone thinking in km. Blank is 0: off.
    It used to take only what float() took, and a commander had to type
    3950.00 before it would save.
    """
    raw = str(text if text is not None else "").strip().lower().replace(" ", "")
    if not raw:
        return 0.0
    scale = None
    for unit, factor in (("km", 1000.0), ("metres", 1.0), ("meters", 1.0),
                         ("m", 1.0)):
        if raw.endswith(unit):
            raw, scale = raw[:-len(unit)], factor
            break
    raw = raw.replace(",", "")
    try:
        value = float(raw)
    except ValueError:
        return None
    if value < 0 or value != value or value in (float("inf"),):
        return None
    if scale is None:
        scale = 1000.0 if 0 < value < 20 else 1.0
    return value * scale


def warning_sound(profane=False):
    """The rig warning's .wav, or "" if it is not there.

    Inside a build the sounds are unpacked with everything else, under
    sys._MEIPASS; running from source they sit in sounds/ beside this file.
    """
    name = "rig-warning-profane.wav" if profane else "rig-warning.wav"
    base = getattr(sys, "_MEIPASS", app_dir())
    path = os.path.join(base, "sounds", name)
    return path if os.path.isfile(path) else ""


def data_dir():
    """Somewhere writable, whatever folder the program was installed into."""
    here = app_dir()
    if os.path.exists(os.path.join(here, "portable.txt")):
        local = os.path.join(here, "data")
        if _writable(local):
            return local
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA")
        if root:
            path = os.path.join(root, "RadioRaxxla", "EDSMT")
            if _writable(path):
                return path
    else:
        path = os.path.join(os.path.expanduser("~"), ".local", "share",
                            "RadioRaxxla", "EDSMT")
        if _writable(path):
            return path
    local = os.path.join(here, "data")
    return local if _writable(local) else here


def _writable(path):
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".probe")
        with open(probe, "w", encoding="utf-8") as handle:
            handle.write("x")
        os.remove(probe)
        return True
    except OSError:
        return False


DATA_DIR = data_dir()
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "_readme": "Everything here has a Settings window in the app.",
    "inara_enabled": False,
    "inara_api_key": "",
    "inara_is_being_developed": False,
    "community_enabled": False,
    # Pre-filled, because a shared database that every commander has to be
    # told the address of is not a shared database. Nothing is sent until
    # community_enabled is switched on, which is a decision, not a default.
    "community_url": "https://api.radioraxxla.com",
    # Whether the share question has been put to this commander yet. The
    # database is only worth searching if people contribute to it, and a
    # setting nobody is ever shown is a setting nobody ever turns on.
    "asked_to_share": False,
    "community_token": "",
    "community_share_cmdr_name": True,
    # Everyone else's finds on the map, the compass and the radar - not only
    # under Find. Reading is not sharing, so this needs no consent and is on.
    "show_shared_finds": True,
    # A newer build is fetched in the background and waits for a click on
    # INSTALL UPDATE. Off, the button fetches it when pressed instead.
    "auto_download_updates": True,
    # Only means anything with a staff token in Settings: then every find
    # you share is verified in your name as it goes up.
    "verify_my_finds": True,
    "community_auto_share": True,
    "share_market_prices": True,
    "journal_dir": "",
    # The keys are Left Alt + 1 onwards on the number row, in the order the
    # work is done on a signal: centre, border, deposit, then Alt+4 to Alt+9
    # for rigs 1 to 6. The same number with AltGr (Ctrl+Alt) undoes it:
    # AltGr+3 updates the deposit, AltGr+4 to 9 pick rigs 1 to 6 up, AltGr+0
    # is every rig up. Function keys were dropped: too many of them already
    # do something in the game or in a graphics overlay. Windows cannot tell
    # the two Alt keys apart when it hands out a key like this - which is
    # why "up" is Ctrl+Alt, the key a UK or European AltGr sends, and not
    # the right Alt on its own. The table is OV.WORK_KEYS.
    "hotkey_location": OV.WORK_KEYS["hotkey_location"],
    "hotkey_deposit": OV.WORK_KEYS["hotkey_deposit"],
    # Arranging the overlay is something you do with the game in front of
    # you, so it gets a key of its own. Blank by default: three keys taken
    # from a flight sim without being asked is two too many, and the button
    # in the title bar does the same job.
    "hotkey_lock": "",
    # Standing on a deposit you already marked, to write down that its
    # Amount has dropped: the last thing done at a deposit, so the last key.
    "hotkey_update": OV.WORK_KEYS["hotkey_update"],
    # The survey area. The centre needs no key of its own - logging the
    # signal sets it - so it stays blank for anyone who wants to move the
    # centre without logging again. The border is the second thing done.
    "hotkey_centre": "",
    "hotkey_border": OV.WORK_KEYS["hotkey_border"],
    # The next free rig down here, whichever number that is. Blank as it
    # ships, now every rig has a key of its own; there for anyone who would
    # rather spend one key than six.
    "hotkey_rigs": OV.WORK_KEYS["hotkey_rigs"],
    # All the rigs back up.
    "hotkey_allup": OV.WORK_KEYS["hotkey_allup"],
    # The rig planner (beta): drive the deposit's edge after this key and
    # the pins for the rigs come out of it.
    "hotkey_trace": OV.WORK_KEYS["hotkey_trace"],
    # Rig 1 to 6 down (Alt+4 to Alt+9) and up again (AltGr+4 to AltGr+9):
    # numbered, drawn on the scope and the compass with the commodity each
    # is on, and the SRV is warned once it is further away than rig_warn_m.
    **{name: OV.WORK_KEYS[name] for name in OV.WORK_KEYS
       if name.startswith("hotkey_rig") and name != "hotkey_rigs"},
    # Which set of default keys this settings file has been given - see
    # upgrade_hotkeys. A key still on an older default moves with the
    # defaults, once; anything set by hand is left alone.
    "hotkey_defaults": 5,
    # The game says "approaching mining rig maximum operational range" at
    # about 4 km, and a rig drops off the SRV's Contacts at about 2.9 km -
    # both measured in the game. 3.5 km warns before the game does.
    "rig_warn_m": 3500,
    "rig_warn_sound": True,
    # A body at or over this surface gravity gets the big warning when you
    # arrive at it, and a red bar on the GUIDE and STATUS boxes while you are
    # there. In g, as the game shows it. 0 turns it off.
    "high_g_warn": 2.0,
    # Which warning to play: the clean one, or the one with language in it.
    "rig_sound_profane": False,
    # The scanner's reach, and how much neighbouring drive circles overlap.
    # Settings rather than constants: they are measured by the community,
    # not published, and a better number should not need a new build.
    "survey_scan_m": 2000,
    "survey_overlap_m": 250,
    # The in-game overlay. Off until asked for: it puts a window over the
    # game, and that should never be a surprise.
    "overlay_enabled": False,
    # Only while the game is the window in front. Left up over everything,
    # the boxes sat on top of EDSMT's own Find and Earnings windows.
    "overlay_only_over_game": True,
    # A few seconds of "RIG 2 DOWN" over the game when a key does something
    # - the app's status line cannot be seen with the game in front.
    "overlay_flash": True,
    # Which overlay, and what the scope centres on. Both are pickable in
    # Settings; the strip is what you get unless you say otherwise.
    "overlay_mode": "strip",
    "overlay_centre": "site",
    "overlay_click_through": True,
    # WHICH BOXES ARE ON SCREEN. Each panel is its own little window, so
    # you can have the tape across the top AND the scope in the corner AND
    # a list of what is nearest - the thing that kept being asked for and
    # kept being answered with "pick one". All four off means the old
    # overlay_mode still decides, so a settings.json written before panels
    # existed opens exactly what it always opened.
    # Where a border is drawn. The scope is a hole you look through at the
    # ground, so it gets none by default; the cards are panels and read
    # better framed. "all" suits a dark cockpit, "none" suits anyone who
    # wants nothing on screen that is not information.
    "overlay_frame": "cards",
    # The whole palette, not one accent line. "Pick a colour" used to tint
    # exactly one row of the compass tape and nothing else, because every
    # other colour was a constant baked in at import - which is why picking
    # one visibly did nothing.
    "overlay_theme": "cockpit",
    # The main window's own palette - any of the overlay's themes. Worn from
    # the next start, because a window keeps the colours it was built with.
    "app_theme": "cockpit",
    # The five boxes of the default layout: compass, scope, targets, status
    # and the guide. The deposit card is there to switch on.
    "overlay_show_strip": True,
    "overlay_show_radar": True,
    "overlay_show_targets": True,
    "overlay_show_status": True,
    "overlay_show_deposit": False,
    # The step-by-step guide rides along with whichever boxes are on. On by
    # default: it is how a first-timer learns the keys, and one switch turns
    # it off.
    "overlay_show_guide": True,
    # Set once the guide has been followed through to its last step - signal,
    # deposit, rigs. It then switches itself off; turned back on by hand in
    # Settings, it stays on.
    "guide_done": False,
    # Set the first time the server takes a deposit of this commander's own.
    # Find - reading the shared map - opens then. See find_unlocked.
    "find_unlocked": False,
    # The rig planner (beta): drive a deposit's edge once and get a pin for
    # each rig where they fit. Off until switched on in Settings - a beta
    # does not turn up in anybody's cockpit uninvited, and its key is not
    # registered while it is off. The spacing is the community's working
    # figure for two rigs, measured in the field, never published.
    "rig_planner": False,
    "rig_spacing_m": 78,
    # The wing link (beta): commanders on one body see each other's Rhinos
    # and rigs on the scope. Off until switched on; everyone in the wing
    # types the same six-character code. wing_member is this install's own
    # slot in a wing, made up the first time it is needed and never shown.
    "wing_link": False,
    "wing_code": "",
    "wing_member": "",
    # Each overlay box's text as a percentage, on its own and apart from the
    # box's size: a tester wanted bigger words without a bigger scope.
    **{"overlay_text_%s" % _box: 100 for _box in (
        OV.STRIP, OV.RADAR, OV.TARGETS, OV.STATUS, OV.DEPOSIT, OV.GUIDE)},
    # Where each panel sits, as FRACTIONS of the screen - never pixels.
    # Written by dragging, not by hand: a pixel position saved on a 4K
    # monitor is off the side of a 1080p one, and the commander who swaps
    # between a desk and a laptop is the normal case, not the odd one.
    "overlay_layout": {},
    # See upgrade_layout: which default layout this file has been given.
    "overlay_layout_level": 2,
    "overlay_opacity": 0.88,
    # Blank means "work it out from the screen". 900x120 at 60,40 is most of
    # a 1080p monitor and a postage stamp on a 4K one, so a fixed default is
    # wrong on somebody's machine whatever number is picked.
    "overlay_x": "",
    "overlay_y": "",
    "overlay_width": 0,
    "overlay_height": 0,
    "overlay_span_deg": 120,
    "overlay_targets": 6,
    "freshness_half_life_days": 21,
    # The last body the game reported, so finds can still be looked at and
    # corrected with Elite shut.
    "last_system": "",
    "last_body": "",
}


# Settings whose blank is a mistake rather than a meaning. Most blanks say
# "work it out" - journal_dir, overlay_x - but a blank community URL says
# nothing at all, and the merge below lets an old file's empty string beat a
# default that only appeared later. That is how upgrading disconnects
# somebody from the map and then tells them to go and set a URL.
NEVER_BLANK = ("community_url",)


def build_kind():
    """Which build this is, for updating: "installed", "portable" or "".

    installed  the folder build Setup put down - it has Setup's own
               uninstaller beside it, so running the new Setup updates it
    portable   the single-file EDSMT.exe - no _internal folder beside it
    ""         running from source, or a folder build nobody installed:
               there is nothing safe to replace, so it gets the web page
    """
    if not getattr(sys, "frozen", False):
        return ""
    here = app_dir()
    if not os.path.isdir(os.path.join(here, "_internal")):
        return "portable"
    if any(name.lower().startswith("unins") and name.lower().endswith(".exe")
           for name in os.listdir(here)):
        return "installed"
    return ""


def updates_folder():
    return os.path.join(DATA_DIR, "updates")


def tidy_after_update():
    """Clear what an earlier update left behind. Never raises.

    The portable build renames itself to EDSMT.exe.old to make room for its
    replacement (a running program can be renamed, not overwritten), and
    that file can only be removed once it is no longer running - which is
    now. Downloads for this version or older are no longer needed either.
    """
    try:
        old = os.path.abspath(sys.executable) + ".old"
        if getattr(sys, "frozen", False) and os.path.exists(old):
            os.remove(old)
    except OSError:
        pass
    folder = updates_folder()
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for name in names:
        match = re.search(r"-(\d+(?:\.\d+)+)\.exe(?:\.part)?$", name)
        if match and not EDO.is_newer(match.group(1), APP_VERSION):
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass


def settings_backup_path():
    """The last settings file that read back cleanly. Every save copies the
    file it is about to replace here first, so there is always one good copy
    behind the current one. Worked out from SETTINGS_FILE at the time rather
    than fixed at import, so the two can never point at different folders."""
    return SETTINGS_FILE + ".bak"

# Said on the status line once the window is up. Losing somebody's settings
# silently is how "the update wiped my overlay" gets reported a week later
# with nothing left to look at.
SETTINGS_NOTICE = []

# True when the file on disk could not be read AND could not be moved aside.
# Saving over it would destroy whatever is in it, so this session does not.
SETTINGS_READ_ONLY = {"on": False}


def _read_settings_file(path, attempts=5):
    """(dict, None) if the file is a settings object, else (None, reason).

    Never raises. A few quick retries, because the two ways this has been
    seen to fail are both momentary: another copy of the app half way
    through writing it, and a virus scanner holding it open.
    """
    reason = "unreadable"
    for attempt in range(attempts):
        if attempt:
            time.sleep(0.08)
        try:
            with open(path, "rb") as handle:
                raw = handle.read()
        except FileNotFoundError:
            return None, "missing"
        except OSError as exc:
            reason = exc.__class__.__name__
            continue
        # utf-8-sig: Notepad on older Windows saves with a byte-order mark,
        # and a plain json.load refuses the whole file because of it.
        text = raw.decode("utf-8-sig", errors="replace").strip()
        if not text:
            reason = "empty"
            continue
        try:
            data = json.loads(text)
        except ValueError:
            reason = "not valid JSON"
            continue
        if not isinstance(data, dict):
            return None, "not a settings file"
        return data, None
    return None, reason


def _atomic_write(path, text):
    """Write a file so that a reader sees the old one or the new one, never
    half of either.

    The old way truncated settings.json and then wrote it. Anything that
    stopped the app between those two steps - an installer closing it, a
    crash, a power cut - left an empty file, and the next launch treated an
    empty file as "no settings" and saved the defaults over it.
    """
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass
    # A scanner that has the target open makes os.replace fail on Windows
    # for a moment. Try again rather than give up on a save.
    for attempt in range(10):
        try:
            os.replace(temp, path)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.05)


def _set_aside(path):
    """Move an unreadable file out of the way, keeping it. Its new name, or
    None if it could not be moved."""
    kept = "%s.unreadable-%s" % (path, time.strftime("%Y%m%d-%H%M%S"))
    try:
        os.replace(path, kept)
        return kept
    except OSError:
        return None


def load_settings():
    """The commander's settings, or the last good copy of them.

    NEVER WRITES. This used to answer any trouble reading the file - a
    truncated write, a byte-order mark, another copy of the app mid-save -
    by saving the defaults over it. That turned a momentary read failure
    into every overlay position, theme, key and hotkey gone for good, which
    is exactly what an update did to the commander who built this.
    """
    data, why = _read_settings_file(SETTINGS_FILE)
    if data is None and why != "missing":
        kept = _set_aside(SETTINGS_FILE)
        if kept is None:
            # Could not read it and could not move it. Leave it exactly
            # where it is, and do not save over it this session.
            SETTINGS_READ_ONLY["on"] = True
        backup, _ = _read_settings_file(settings_backup_path(), attempts=1)
        if backup is not None:
            data = backup
            SETTINGS_NOTICE.append(
                "Your settings file could not be read (%s), so the last good "
                "copy has been put back." % why)
        else:
            data = {}
            SETTINGS_NOTICE.append(
                "Your settings file could not be read (%s) and there was no "
                "earlier copy, so this is starting from the defaults." % why)
        if kept:
            SETTINGS_NOTICE.append("The unreadable file is kept as %s."
                                   % os.path.basename(kept))
        elif SETTINGS_READ_ONLY["on"]:
            SETTINGS_NOTICE.append(
                "It is in use by something else, so nothing will be saved "
                "over it until EDSMT is restarted.")
    elif data is None:
        # No settings.json at all. A first run - unless a backup exists,
        # in which case something removed it and the backup is the answer.
        backup, _ = _read_settings_file(settings_backup_path(), attempts=1)
        if backup is not None:
            data = backup
            SETTINGS_NOTICE.append("Your settings file was missing, so the "
                                   "last good copy has been put back.")
        else:
            data = {}
    merged = {**DEFAULT_SETTINGS, **data}
    for key in NEVER_BLANK:
        if not str(merged.get(key) or "").strip():
            merged[key] = DEFAULT_SETTINGS[key]
    return upgrade_layout(upgrade_hotkeys(merged, data), data)


# The overlay layout this build ships, as a number. Up to 1.10029 every
# theme change, Save and restart, or Overlay off measured the boxes while
# Windows had them hidden and saved the nonsense - "the overlays keep
# changing". The layout written by those builds cannot be trusted, so it is
# replaced once by the new default: compass across the top, scope and guide
# down the left, targets on the right, status along the bottom.
LAYOUT_LEVEL = 2


def upgrade_layout(merged, saved):
    """Put a pre-1.10030 overlay layout on the new default, once."""
    saved = saved or {}
    try:
        level = int(saved.get("overlay_layout_level") or 1)
    except (TypeError, ValueError):
        level = 1
    if level >= LAYOUT_LEVEL:
        return merged
    stored = saved.get("overlay_layout")
    if saved and isinstance(stored, dict) and stored:
        SETTINGS_NOTICE.append(
            "The overlay boxes are on the new default layout - a bug in the "
            "last build could move them when you changed the theme. Unlock "
            "the overlay to arrange them again; they now stay put.")
    merged["overlay_layout"] = {key: dict(spec)
                                for key, spec in OV.DEFAULT_LAYOUT.items()}
    merged["overlay_layout_level"] = LAYOUT_LEVEL
    return merged


# The keys, in the order the work is done: Left Alt + 1 onwards, then the
# rigs, then the AltGr undo of each.
KEY_ORDER = tuple((name, OV.WORK_KEYS[name]) for name in (
    ("hotkey_location", "hotkey_border", "hotkey_deposit")
    + tuple("hotkey_rig%d" % n for n in range(1, OV.RIG_SLOTS + 1))
    + ("hotkey_update", "hotkey_trace")
    + tuple("hotkey_rig%dup" % n for n in range(1, OV.RIG_SLOTS + 1))
    + ("hotkey_allup", "hotkey_rigs")))
KEYS_LEVEL = 5
# What each of those was given by the layout a settings file is still on.
# A file holding its own layout's default never had that key set by hand,
# so it moves with the defaults; a file holding anything else keeps it.
# Per layout, not one list: on the Alt+F layout a blank UPDATE is a key
# somebody cleared, while before it a blank UPDATE was simply the default.
# An action a layout did not have at all is new, and takes its default -
# unless that key is already on something set by hand.
#   1-2  F9 / F10 (and a test build's F8 / F7)
#   3    Left Alt + F1 onwards, F4 skipped - a 1.10029 test build
#   4    Alt+1 to Alt+6: one RIG DOWN key numbering each rig, Alt+5 all up,
#        Alt+6 update - 1.10029 and 1.10030
OLD_DEFAULT_KEYS = {
    1: {"hotkey_location": ("F9",), "hotkey_deposit": ("F10",),
        "hotkey_border": ("", "F8"), "hotkey_rigs": ("", "F7"),
        "hotkey_allup": ("",), "hotkey_update": ("",)},
    3: {"hotkey_location": ("ALT+F1",), "hotkey_border": ("ALT+F2",),
        "hotkey_deposit": ("ALT+F3",), "hotkey_rigs": ("ALT+F5",),
        "hotkey_allup": ("ALT+F6",), "hotkey_update": ("ALT+F7",)},
    4: {"hotkey_location": ("ALT+1",), "hotkey_border": ("ALT+2",),
        "hotkey_deposit": ("ALT+3",), "hotkey_rigs": ("ALT+4",),
        "hotkey_allup": ("ALT+5",), "hotkey_update": ("ALT+6",)},
}
OLD_DEFAULT_KEYS[2] = OLD_DEFAULT_KEYS[1]
# 1000 m was the rig warning's default until 1.10029, and a guess. A file
# still holding exactly that gets the measured one.
OLD_RIG_WARN_M = 1000


def upgrade_hotkeys(merged, saved):
    """Move a settings file's keys to the current layout, once.

    Only a key still on a default it shipped with moves, and never onto a
    key the commander has put something else on - two actions on one key
    would each fire half the time. After this the file says which layout it
    has, and a key changed later is a key the commander changed.
    """
    saved = saved or {}
    try:
        level = int(saved.get("hotkey_defaults") or 1)
    except (TypeError, ValueError):
        level = 1
    if level >= KEYS_LEVEL:
        return merged

    def norm(value):
        return str(value or "").strip().upper()

    before = OLD_DEFAULT_KEYS.get(level, OLD_DEFAULT_KEYS[1])

    def on_default(name):
        if name in before:
            return norm(saved.get(name)) in before[name]
        # An action this layout never had: new, unless somebody has already
        # written a key for it into the file by hand.
        return not norm(saved.get(name))

    movable = {name for name, _key in KEY_ORDER if on_default(name)}
    kept = {norm(value) for name, value in saved.items()
            if name.startswith("hotkey_") and name != "hotkey_defaults"
            and name not in movable and norm(value)}
    moved = []
    for name, key in KEY_ORDER:
        if name not in movable:
            continue
        if key and key in kept:
            # Its new key is taken by something set by hand: leave it on
            # whatever it had, which still works - or blank, if it is new.
            merged[name] = str(saved.get(name) or "")
            continue
        merged[name] = key
        if key:
            kept.add(key)
            moved.append(key)
    if moved and saved:
        SETTINGS_NOTICE.append(
            "New keys: Alt+4 to Alt+9 put rigs 1 to 6 down, and %s to %s "
            "pick each one up. %s updates the deposit you are on, %s is "
            "every rig up. Alt+1 to Alt+3 are unchanged. Keys you set "
            "yourself were kept. Settings has them all."
            % (key_text("CTRL+ALT+4"), key_text("CTRL+ALT+9"),
               key_text("CTRL+ALT+3"), key_text("CTRL+ALT+0")))
    try:
        if float(saved.get("rig_warn_m", OLD_RIG_WARN_M)) == OLD_RIG_WARN_M:
            merged["rig_warn_m"] = DEFAULT_SETTINGS["rig_warn_m"]
    except (TypeError, ValueError):
        pass
    merged["hotkey_defaults"] = KEYS_LEVEL
    return merged


def worked_out_age(deposit, now=None):
    """"worked out 9 days ago" for a Depleted deposit, from its MINED OUT
    stamp, or "". How fast a deposit grows back is not known, so nothing
    is assumed: the age is shown and the call is the commander's."""
    if not SV.is_depleted(deposit.get("amount")):
        return ""
    found = None
    for line in str(deposit.get("notes") or "").splitlines():
        if line.strip().lower().startswith("mined"):
            match = re.search(r"(\d{2})/(\d{2})/(\d{4})", line)
            if match:
                found = match
    if not found:
        return ""
    day, month, year = (int(x) for x in found.groups())
    try:
        when = time.mktime((year, month, day, 12, 0, 0, 0, 0, -1))
    except (OverflowError, ValueError):
        return ""
    days = int(max(0.0, ((now if now is not None else time.time()) - when) / 86400.0))
    return "worked out %s" % ("today" if days == 0 else "yesterday" if days == 1
                              else "%d days ago" % days)


def tonnes_lines(deposit, peers=None):
    """What a deposit has given, as lines for its details.

    Its own commodity is the number - by-products come off it too and are
    listed beside, not added in. Once it has been worked out, what it gave
    each time says what it holds, and so roughly what is left now. Before
    that, `peers` - the commander's other deposits - give an estimate from
    the ones with the same rigs and density that were worked out (1.10032),
    marked as an estimate and saying how many it rests on."""
    own, others = SV.own_tonnes(deposit)
    held = SV.cycle_tonnes(deposit)
    lines = []
    if own:
        lines.append("mined %s: %dt" % ("this time" if held else "here", own))
    if others:
        lines.append("  by-products: " + ", ".join(
            "%s %dt" % (name, count) for name, count in
            sorted(others.items(), key=lambda pair: -pair[1])))
    if held:
        low, high = min(held), max(held)
        size = ("%dt" % high) if low == high else ("%d-%dt" % (low, high))
        lines.append("holds about %s (worked out %d time%s)"
                     % (size, len(held), "" if len(held) == 1 else "s"))
        if own and not SV.is_depleted(deposit.get("amount")):
            left_low, left_high = max(0, low - own), max(0, high - own)
            left = ("%dt" % left_high) if left_low == left_high else \
                ("%d-%dt" % (left_low, left_high))
            lines.append("left: about %s" % left)
    elif peers and not SV.is_depleted(deposit.get("amount")):
        guess = SV.estimate_tonnes(peers, deposit.get("rigs"),
                                   deposit.get("density"), exclude=deposit)
        if guess:
            low, high, count = guess
            size = ("%dt" % high) if low == high else ("%d-%dt" % (low, high))
            lines.append("est. holds %s - from %d worked out with %s rigs, %s"
                         % (size, count, deposit.get("rigs"),
                            deposit.get("density")))
            if own:
                left_low, left_high = max(0, low - own), max(0, high - own)
                left = ("%dt" % left_high) if left_low == left_high else \
                    ("%d-%dt" % (left_low, left_high))
                lines.append("est. left: %s" % left)
    return lines


def from_centre(store, deposit):
    """Where a deposit is from the middle of its signal, as one line.

    Measured from where the signal was logged - the centre of the survey -
    so it reads the same whoever reads it and wherever they are standing:
    "from the signal centre: 1.24 km NE 045". Blank when the signal was never
    logged with a position, or the deposit has none.
    """
    try:
        row = store.location(deposit.get("system"), deposit.get("body"),
                             deposit.get("location"))
        if not row:
            return ""
        lat0, lon0 = float(row["lat"]), float(row["lon"])
        lat1, lon1 = float(deposit["lat"]), float(deposit["lon"])
        radius = float(row.get("radius_m") or 0) or 1e6
    except (TypeError, ValueError, KeyError, AttributeError):
        return ""
    metres = SV.surface_range_m(lat0, lon0, lat1, lon1, radius)
    if metres < 1:
        return "at the signal centre"
    bearing = SV.bearing_deg(lat0, lon0, lat1, lon1)
    return "from the signal centre: %s %s %03.0f" % (
        _metres(metres), SV.compass(bearing), bearing)


def _windows_clipboard(text, tries=10, wait_s=0.03):
    """Put text on the Windows clipboard directly. True if it went.

    Tk's own clipboard on Windows is handed over when asked for, by the Tk
    that owns it - close EDSMT straight after copying and what was copied
    can go with it. Written through Win32 it stays after EDSMT has gone.
    Another program holding the clipboard open is waited for briefly,
    rather than the copy being dropped.
    """
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.OpenClipboard.argtypes = (wintypes.HWND,)
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.CloseClipboard.restype = wintypes.BOOL
    kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
    kernel32.GlobalFree.argtypes = (wintypes.HGLOBAL,)
    CF_UNICODETEXT, GMEM_MOVEABLE = 13, 0x0002
    data = str(text).encode("utf-16-le") + b"\x00\x00"
    for _attempt in range(tries):
        if user32.OpenClipboard(None):
            break
        time.sleep(wait_s)
    else:
        return False
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            return False
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            kernel32.GlobalFree(handle)
            return False
        ctypes.memmove(pointer, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)      # still ours only if it failed
            return False
        return True
    finally:
        user32.CloseClipboard()


def put_on_clipboard(widget, text):
    """Every copy button comes here. Win32 on Windows, Tk elsewhere or if
    Windows refuses. Raises only if neither worked."""
    if os.name == "nt":
        try:
            if _windows_clipboard(text):
                return True
        except Exception:
            pass
    widget.clipboard_clear()
    widget.clipboard_append(str(text))
    return True


def bound_key(settings, action, button=""):
    """The key for an action as written on screen - "Alt+1" - or, when it
    has none, the button that does it. Any window can ask, with whatever
    settings it holds; none of them keeps its own copy of a key."""
    settings = settings or DEFAULT_SETTINGS
    name = "hotkey_" + action
    bound = key_text(settings.get(name, DEFAULT_SETTINGS.get(name, "")))
    if bound:
        return bound
    return ("the %s button" % button) if button else "its button"


def altgr_word():
    """What to call the "undo" modifier on this keyboard: AltGr where there
    is one, Ctrl+Alt where there is not (a US layout's right Alt is plain
    Alt, and would drop a rig rather than pick it up)."""
    return "AltGr" if OV.altgr_layout() else "Ctrl+Alt"


def key_text(binding):
    """"ALT+1" as a person writes it: "Alt+1"; "CTRL+ALT+4" is "AltGr+4" on
    a keyboard with an AltGr key. Blank stays blank. One spelling, shared
    with the overlay: OV.key_words."""
    return OV.key_words(binding)


def save_settings(data):
    """Write settings safely. False if they could not be written.

    Serialised in memory BEFORE the disk is touched, so a value JSON cannot
    hold fails here rather than half way through the file. The file being
    replaced becomes the backup, but only if it read back cleanly - a broken
    file is never promoted over a good backup.
    """
    if SETTINGS_READ_ONLY["on"]:
        return False
    try:
        text = json.dumps(data, indent=2, default=str)
    except (TypeError, ValueError):
        return False
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        current, _ = _read_settings_file(SETTINGS_FILE, attempts=1)
        if current is not None and current != data:
            _atomic_write(settings_backup_path(), json.dumps(current, indent=2,
                                                      default=str))
        _atomic_write(SETTINGS_FILE, text)
        return True
    except OSError:
        return False




# ---------------------------------------------------------------------------
# Taking somebody else's finds with them
# ---------------------------------------------------------------------------

# Two different layouts of a file called surfaceminingmap.csv are in
# circulation from other surface-mining tools, and both use exactly that name,
# so the filename cannot say which is which. Only the header row can, which
# is why nothing below asks the commander to pick - it reads the first line
# and knows.
#
#   with bearing and range   One deposit per row, carrying the bearing and
#                            range from the signal centre as well as the
#                            position. "direction" is the bearing FROM the
#                            centre TO the deposit.
#
#   with signal centres      No bearing or range at all, and one column this
#                            app has no equivalent for: iscenter marks a row
#                            that IS the mining location signal rather than a
#                            deposit inside it. Those rows become signals
#                            here, which is what they are.
IMPORT_FORMATS = {
    "bearing": {
        "label": "surfaceminingmap.csv (with bearing and range)",
        "columns": ("system", "planet", "mining_spot_number", "type", "rigs",
                    "direction", "distance", "lat", "long"),
    },
    "centres": {
        "label": "surfaceminingmap.csv (with signal centres)",
        "columns": ("system", "planet", "spotnum", "type", "rigs", "lat",
                    "long", "iscenter"),
    },
}


def _import_key(text):
    return str(text or "").strip().lstrip("﻿").lower()


def detect_import_format(header):
    """Which tool wrote this file, from its header row alone.

    Every column the format declares has to be present. A file with extra
    columns still imports - somebody who added a "notes" column of their
    own should not be locked out of their own data - but a file missing
    one of ours is not that format and is refused by name.
    """
    seen = {_import_key(cell) for cell in (header or [])}
    best, score = None, 0
    for key, spec in IMPORT_FORMATS.items():
        if set(spec["columns"]) <= seen and len(spec["columns"]) > score:
            best, score = key, len(spec["columns"])
    return best


def import_expectations():
    """What a refusal has to say, so "unrecognised" is actionable."""
    return "\n".join("%s: %s" % (spec["label"], ", ".join(spec["columns"]))
                     for spec in IMPORT_FORMATS.values())


def _import_ledger_path():
    # Computed on the way in rather than at import time, because DATA_DIR
    # is what the tests move and a constant baked at module level would
    # point at the real %LOCALAPPDATA% while they ran.
    return os.path.join(DATA_DIR, "imported.json")


def load_import_ledger():
    """Which files have already been taken in, by content."""
    try:
        with open(_import_ledger_path(), "r", encoding="utf-8") as handle:
            found = json.load(handle)
        return found if isinstance(found, dict) else {}
    except Exception:
        return {}


def remember_import(digest, detail):
    ledger = load_import_ledger()
    ledger[digest] = detail
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(_import_ledger_path(), "w", encoding="utf-8") as handle:
            json.dump(ledger, handle, indent=2)
    except OSError:
        pass
    return ledger


def _import_digest(path):
    import hashlib
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_import(path):
    """(format key, rows) for a file we recognise, or (None, []).

    The same encoding ladder survey.py reads its own CSVs through. A file
    that has been through Excel on a German Windows is still that
    commander's finds.
    """
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with open(path, "r", encoding=encoding, newline="") as handle:
                reader = csv.reader(handle)
                header = next(reader, [])
                key = detect_import_format(header)
                if not key:
                    return None, []
                names = [_import_key(cell) for cell in header]
                rows = [dict(zip(names, line)) for line in reader if any(line)]
                return key, rows
        except (UnicodeDecodeError, LookupError):
            continue
        except (OSError, csv.Error):
            return None, []
    return None, []


def _import_number(text):
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return None


def _import_rigs(text):
    """Their rig count, or blank. Never a number this game cannot produce."""
    value = _import_number(text)
    if value is None or not 1 <= value <= MAX_RIGS:
        return ""
    return str(int(value))


def _import_position(row):
    lat = _import_number(row.get("lat"))
    lon = _import_number(row.get("long"))
    if lat is None or lon is None:
        return "", ""
    return "%.6f" % lat, "%.6f" % lon


def deposit_fingerprint(system, body, location, commodity, lat, lon):
    """The server's own duplicate rule, run here before anything is added.

    Three decimal places, because two commanders logging the same deposit
    never park in the same place. Matching what the server does matters
    more than the exact tolerance: a row this app calls new and the server
    calls a duplicate is a row that vanishes on the way up.
    """
    key = [str(system or "").strip().lower(), str(body or "").strip().lower(),
           str(location or "").strip().lower(),
           str(commodity or "").strip().lower()]
    lat_f, lon_f = _import_number(lat), _import_number(lon)
    if lat_f is None or lon_f is None:
        key.append("nopos")
    else:
        key += ["%.3f" % lat_f, "%.3f" % lon_f]
    return "|".join(key)


def import_finds(store, path):
    """Take another tool's CSV into this one's database.

    Nothing already here is touched. Every row is either added or counted
    as skipped and said out loud, and the whole database is backed up
    first - the same zip the Back up now button writes - because an import
    is the one moment somebody else's file gets to change yours.
    """
    result = {"ok": False, "reason": "", "format": "", "label": "",
              "taken": 0, "duplicates": 0, "unusable": 0, "signals": 0,
              "backup": "", "backup_failed": "", "rows": 0}
    if not os.path.exists(path):
        result["reason"] = "There is no file at %s" % path
        return result
    try:
        digest = _import_digest(path)
    except OSError as problem:
        result["reason"] = "Could not read that file: %s" % problem
        return result
    already = load_import_ledger().get(digest)
    if already:
        result["reason"] = ("That exact file has already been imported (%s). "
                            "Nothing was added twice."
                            % already.get("when", "earlier"))
        return result

    key, rows = read_import(path)
    if not key:
        result["reason"] = ("That file's header is not one this can read.\n"
                            "Expected one of:\n%s" % import_expectations())
        return result
    result["format"], result["label"] = key, IMPORT_FORMATS[key]["label"]
    result["rows"] = len(rows)

    # Backed up BEFORE the first row goes in, so "undo" is a real answer
    # rather than an apology. survey.py's own migration leans on the .bak
    # that every write leaves; a whole-database zip is the version of that
    # which survives somebody importing the wrong file twice in a row.
    try:
        backup, _ = store.backup_to(DATA_DIR)
        result["backup"] = backup or ""
    except Exception as problem:
        # Not a reason to refuse the import - somebody with a full disk
        # still wants their finds - but it IS a reason to say so, because
        # the whole point of the line was "you can undo this".
        result["backup_failed"] = str(problem)

    seen = {deposit_fingerprint(d.get("system"), d.get("body"),
                                d.get("location"), d.get("commodity"),
                                d.get("lat"), d.get("lon"))
            for d in store.deposits}
    note = "imported from %s" % IMPORT_FORMATS[key]["label"]
    for row in rows:
        system = str(row.get("system") or "").strip()
        body = str(row.get("planet") or "").strip()
        if not (system and body):
            result["unusable"] += 1
            continue
        number = str(row.get("mining_spot_number")
                     or row.get("spotnum") or "1").strip() or "1"
        lat, lon = _import_position(row)

        # The centres layout marks the signal centre as a row of its own.
        # It is a signal here, not a deposit, and a signal already logged is
        # left exactly as it is - an imported file must never quietly move a
        # centre this commander stood on and recorded themselves.
        if str(row.get("iscenter") or "").strip().lower() == "true":
            if store.location(system, body, number) is None:
                store.set_location(system, body, number,
                                   lat=_import_number(row.get("lat")),
                                   lon=_import_number(row.get("long")),
                                   notes=note)
                result["signals"] += 1
            else:
                result["duplicates"] += 1
            continue

        commodity = SV.canonical(row.get("type") or "")
        if not commodity:
            result["unusable"] += 1
            continue
        fingerprint = deposit_fingerprint(system, body, number, commodity,
                                          lat, lon)
        if fingerprint in seen:
            result["duplicates"] += 1
            continue
        seen.add(fingerprint)
        store.add_deposit(system=system, body=body, location=number,
                          commodity=commodity,
                          rigs=_import_rigs(row.get("rigs")),
                          lat=lat, lon=lon,
                          status=SV.STATUS_REPORTED, notes=note)
        result["taken"] += 1

    # A signal row so the body remembers the imported finds are in one,
    # exactly as F10 does for a deposit marked without F9 first.
    for system, body, number in sorted({
            (str(r.get("system") or "").strip(),
             str(r.get("planet") or "").strip(),
             str(r.get("mining_spot_number") or r.get("spotnum") or "1").strip()
             or "1") for r in rows}):
        if system and body and store.location(system, body, number) is None:
            # Where it came from, on the signal itself. A commander looking
            # at a body full of finds they do not remember making deserves
            # an answer that is not "check the deposit notes one at a time".
            store.set_location(system, body, number, notes=note)
            result["signals"] += 1

    result["ok"] = True
    remember_import(digest, {"when": SV.utc_now(),
                             "file": os.path.basename(path),
                             "format": key, "taken": result["taken"]})
    return result


# ---------------------------------------------------------------------------
# One find as a line of text, and back
# ---------------------------------------------------------------------------
#
# Readable first: it goes into Discord, where a person reads it before any
# program does. Anyone running EDSMT pastes it back in and gets the find on
# their own map; anyone who is not can still read where it is and what it is.
SHARE_TAG = "EDSMT find"


def share_line(deposit):
    """A deposit as one line: system, body, signal, what, rigs, where."""
    def bit(value, unknown="?"):
        text = str(value or "").strip().replace("|", "/")
        return text or unknown
    lat, lon = _import_number(deposit.get("lat")), _import_number(deposit.get("lon"))
    where = ("%.5f, %.5f" % (lat, lon)) if lat is not None and lon is not None else "?"
    return " | ".join([
        SHARE_TAG, bit(deposit.get("system")), bit(deposit.get("body")),
        "signal " + bit(deposit.get("location")), bit(deposit.get("commodity")),
        "rigs " + bit(deposit.get("rigs")), "amount " + bit(deposit.get("amount")),
        "density " + bit(deposit.get("density")), where])


def read_share_lines(text):
    """Every find in a block of pasted text, and how many lines were not one.

    Lines that do not start with the tag are somebody talking and are not
    counted at all; a tagged line that cannot be read is counted, so the
    commander hears that something was left out.
    """
    finds, unreadable = [], 0
    for raw in str(text or "").splitlines():
        line = raw.strip().strip("`").strip()
        if not line.lower().startswith(SHARE_TAG.lower()):
            continue
        parts = [part.strip() for part in line.split("|")]
        try:
            _tag, system, body, signal, commodity, rigs, amount, density, where = parts
            lat_text, lon_text = [x.strip() for x in where.split(",")]
            lat, lon = float(lat_text), float(lon_text)
        except ValueError:
            unreadable += 1
            continue

        def after(word, value):
            value = value[len(word):].strip() if value.lower().startswith(word) else value
            return "" if value == "?" else value
        commodity = SV.canonical(commodity) if commodity not in ("", "?") else ""
        if (not system or system == "?" or not body or body == "?" or not commodity
                or not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0)):
            unreadable += 1
            continue
        finds.append({"system": system, "body": body,
                      "location": after("signal", signal) or "1",
                      "commodity": commodity,
                      "rigs": _import_rigs(after("rigs", rigs)),
                      "amount": after("amount", amount),
                      "density": after("density", density),
                      "lat": "%.6f" % lat, "lon": "%.6f" % lon})
    return finds, unreadable


def _already_marked(store, find):
    """True if a deposit of the same commodity is marked within
    SAME_DEPOSIT_M of it - the rule MARK uses, so a find pasted from a
    friend who parked twenty metres further along is still one find. Needs
    the body's size, which a signal logged on it carries; without one only
    the exact position rule applies."""
    radius = None
    for row in store.locations_on(find["system"], find["body"]):
        try:
            radius = float(row.get("radius_m") or 0) or None
        except (TypeError, ValueError):
            radius = None
        if radius:
            break
    if not radius:
        return False
    wanted = SV.fold(find["commodity"])
    for row in store.at(find["system"], find["body"]):
        if SV.fold(row.get("commodity")) != wanted:
            continue
        try:
            metres = SV.surface_range_m(float(find["lat"]), float(find["lon"]),
                                        float(row["lat"]), float(row["lon"]), radius)
        except (TypeError, ValueError, KeyError):
            continue
        if metres <= SAME_DEPOSIT_M:
            return True
    return False


def take_share_lines(store, text):
    """Add the finds in pasted text to this commander's records.

    The same duplicate rule as an import and as the server, so a line pasted
    twice - or a find already marked here - is counted, not added again.
    """
    finds, unreadable = read_share_lines(text)
    result = {"taken": 0, "duplicates": 0, "unreadable": unreadable, "signals": 0}
    seen = {deposit_fingerprint(d.get("system"), d.get("body"), d.get("location"),
                                d.get("commodity"), d.get("lat"), d.get("lon"))
            for d in store.deposits}
    note = "pasted from a shared line %s" % SV.utc_now()[:10]
    for find in finds:
        mark = deposit_fingerprint(find["system"], find["body"], find["location"],
                                   find["commodity"], find["lat"], find["lon"])
        if mark in seen or _already_marked(store, find):
            result["duplicates"] += 1
            continue
        seen.add(mark)
        store.add_deposit(status=SV.STATUS_REPORTED, notes=note, **find)
        result["taken"] += 1
        if store.location(find["system"], find["body"], find["location"]) is None:
            store.set_location(find["system"], find["body"], find["location"],
                               notes=note)
            result["signals"] += 1
    return result


def share_summary(result):
    if not (result["taken"] or result["duplicates"] or result["unreadable"]):
        return ("Nothing to add - paste one or more lines that start "
                "\"%s\" into the box first." % SHARE_TAG)
    bits = ["Added %d find(s)" % result["taken"]]
    if result["duplicates"]:
        bits.append("%d already here, left alone" % result["duplicates"])
    if result["unreadable"]:
        bits.append("%d line(s) could not be read" % result["unreadable"])
    return ", ".join(bits) + "."


def import_summary(result):
    """One line the commander can act on, whichever way it went."""
    if not result["ok"]:
        return result["reason"]
    bits = ["Imported %d find(s) from %s" % (result["taken"], result["label"])]
    if result["signals"]:
        bits.append("%d mining location(s)" % result["signals"])
    if result["duplicates"]:
        bits.append("%d already here, left alone" % result["duplicates"])
    if result["unusable"]:
        bits.append("%d row(s) had no system, body or commodity" % result["unusable"])
    if result["backup"]:
        bits.append("Your database was backed up to %s first"
                    % os.path.basename(result["backup"]))
    elif result.get("backup_failed"):
        bits.append("NOTE: the backup could not be written (%s), so there is "
                    "no zip to go back to" % result["backup_failed"])
    return ". ".join(bits) + "."


# ---------------------------------------------------------------------------
# System-wide hotkeys
# ---------------------------------------------------------------------------

# Every key a commander might reasonably pick, not just the function row.
#
# This used to be F1-F12 and nothing else. Anybody whose function keys are
# already bound in the game, or whose keyboard sends media keys off the top
# row unless Fn is held, had no way out: the Settings box accepted any text
# and then silently bound nothing, because an unrecognised name produced no
# code and no complaint. A key that does nothing and says nothing is worse
# than a key that is taken.
VK = {}
VK.update({"F%d" % n: 0x6F + n for n in range(1, 25)})       # F1 - F24
VK.update({chr(c): c for c in range(0x41, 0x5B)})            # A - Z
VK.update({chr(c): c for c in range(0x30, 0x3A)})            # 0 - 9
VK.update({"NUMPAD%d" % n: 0x60 + n for n in range(0, 10)})
VK.update({
    "NUMPAD*": 0x6A, "NUMPAD+": 0x6B, "NUMPAD-": 0x6D,
    "NUMPAD.": 0x6E, "NUMPAD/": 0x6F,
    "SPACE": 0x20, "ENTER": 0x0D, "TAB": 0x09, "BACKSPACE": 0x08,
    "ESC": 0x1B, "INSERT": 0x2D, "DELETE": 0x2E, "HOME": 0x24,
    "END": 0x23, "PAGEUP": 0x21, "PAGEDOWN": 0x22, "PAUSE": 0x13,
    "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28,
    ";": 0xBA, "=": 0xBB, ",": 0xBC, "-": 0xBD, ".": 0xBE, "/": 0xBF,
    "`": 0xC0, "[": 0xDB, "\\": 0xDC, "]": 0xDD, "'": 0xDE,
})

# Virtual key code back to its name, for a key Tk reports by the character
# a layout made of it (AltGr+4 is the euro sign on a UK keyboard). Letters,
# digits and function keys only - the unambiguous ones.
VK_NAMES = {code: name for name, code in VK.items()
            if re.match(r"^([A-Z0-9]|F\d+)$", name)}

# RegisterHotKey's modifier bits.
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 0x0001, 0x0002, 0x0004, 0x0008
MODIFIERS = (("CTRL", MOD_CONTROL), ("ALT", MOD_ALT),
             ("SHIFT", MOD_SHIFT), ("WIN", MOD_WIN))
MOD_ALIASES = {"CONTROL": "CTRL", "CMD": "WIN", "SUPER": "WIN",
               "META": "WIN", "WINDOWS": "WIN"}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

# Tk reports a key by its X11 keysym, which agrees with the names above for
# letters and function keys and disagrees for most of the rest. Only the
# disagreements are listed.
KEYSYMS = {
    "return": "ENTER", "kp_enter": "ENTER", "escape": "ESC",
    "prior": "PAGEUP", "next": "PAGEDOWN", "plus": "=", "equal": "=",
    "minus": "-", "comma": ",", "period": ".", "slash": "/",
    "semicolon": ";", "grave": "`", "quoteleft": "`", "apostrophe": "'",
    "quoteright": "'", "bracketleft": "[", "bracketright": "]",
    "backslash": "\\", "kp_multiply": "NUMPAD*", "kp_add": "NUMPAD+",
    "kp_subtract": "NUMPAD-", "kp_decimal": "NUMPAD.",
    "kp_divide": "NUMPAD/", "kp_delete": "NUMPAD.",
}
KEYSYMS.update({"kp_%d" % n: "NUMPAD%d" % n for n in range(0, 10)})
# The modifier keys themselves are not bindings - they qualify one.
BARE_MODIFIERS = {"control_l", "control_r", "alt_l", "alt_r", "shift_l",
                  "shift_r", "super_l", "super_r", "win_l", "win_r",
                  "meta_l", "meta_r", "caps_lock", "num_lock"}


def parse_binding(text):
    """"Ctrl+Shift+K" -> (modifier bits, virtual key code), or None.

    None means the app cannot bind it, and the caller has to SAY so rather
    than register nothing and leave the commander pressing a dead key.
    """
    parts = [p.strip().upper() for p in str(text or "").split("+") if p.strip()]
    # A lone "+" is a real key, and splitting on + eats it.
    if str(text or "").strip() in ("+", "NUMPAD+"):
        parts = [str(text).strip().upper()]
    if not parts:
        return None
    bits, key = 0, None
    for part in parts:
        name = MOD_ALIASES.get(part, part)
        found = dict(MODIFIERS).get(name)
        if found is not None:
            bits |= found
        elif key is None:
            key = name
        else:
            return None                      # two real keys is not a binding
    code = VK.get(key)
    return (bits, code) if code else None


def format_binding(bits, key):
    """The canonical spelling, so settings.json never holds two of these."""
    names = [name for name, bit in MODIFIERS if bits & bit]
    return "+".join(names + [str(key).upper()])


def binding_from_event(event):
    """What a commander just pressed, as a binding, or None.

    Reads Tk's own keysym and modifier state rather than a typed string, so
    the Settings screen can work the way the game's own binding screen does:
    click the box, press the key, done.
    """
    keysym = str(getattr(event, "keysym", "") or "")
    if keysym.lower() in BARE_MODIFIERS:
        return None
    name = KEYSYMS.get(keysym.lower(), keysym.upper())
    state = int(getattr(event, "state", 0) or 0)
    if name not in VK:
        # AltGr+4 on a UK keyboard arrives as the euro sign, not as 4: the
        # layout has already turned the key into the character it types.
        # On Windows Tk's keycode is the virtual key, which is the key
        # itself - so read that instead, and AltGr keys can be bound.
        name = VK_NAMES.get(int(getattr(event, "keycode", 0) or 0)) \
            if os.name == "nt" else None
        if not name:
            return None
    bits = 0
    if state & 0x0004: bits |= MOD_CONTROL
    if state & 0x0001: bits |= MOD_SHIFT
    if state & ALT_STATE: bits |= MOD_ALT
    return format_binding(bits, name)


# Which bit of a Tk key event's state means Alt. On Windows it is 0x20000,
# and 0x0008 there is NUM LOCK - reading 0x0008 as Alt put ALT+ on every key
# captured with Num Lock on, so a tester who pressed F1 got Alt+F1, could not
# bind anything without Alt, and Alt+F1 is NVIDIA's screenshot key. On X11,
# where the tests run, Alt is Mod1, which is 0x0008.
ALT_STATE = 0x20000 if os.name == "nt" else 0x0008

# Keys other programs already use, and who uses them. A binding on this list
# still saves - some commanders have those programs off - but it is flagged
# when it is pressed in Settings, because the other program gets the key
# first and EDSMT never hears it. Defaults only: NVIDIA's from its own app,
# AMD's from Adrenalin, the rest from Windows, Steam, Discord and the game.
KEY_CLASHES = {
    "ALT+F1": "NVIDIA screenshot",
    "ALT+F3": "NVIDIA game filters",
    "ALT+F9": "NVIDIA record",
    "ALT+SHIFT+F10": "NVIDIA instant replay",
    "ALT+Z": "NVIDIA and AMD overlay",
    "ALT+R": "NVIDIA performance overlay and AMD Adrenalin",
    "CTRL+SHIFT+E": "AMD record",
    "CTRL+SHIFT+S": "AMD instant replay",
    "CTRL+SHIFT+I": "AMD screenshot",
    "CTRL+SHIFT+O": "AMD performance overlay",
    "CTRL+SHIFT+M": "Discord mute",
    "CTRL+SHIFT+D": "Discord deafen",
    "SHIFT+`": "Discord overlay",
    "SHIFT+TAB": "the Steam overlay",
    "F12": "Steam screenshot",
    "F10": "the game's screenshot",
    "ALT+F10": "the game's high-res screenshot",
    "ALT+TAB": "Windows",
    "ALT+F4": "Windows - it closes the game",
    "ALT+ENTER": "Windows full-screen switch",
    "ALT+SPACE": "Windows",
    "ALT+ESC": "Windows",
}


def key_clash(binding):
    """Who else uses this key by default, in a few words, or "".

    Win+ anything belongs to Windows and the Xbox Game Bar. A key with no
    Ctrl, Alt or Shift on it is flagged too: the game reads plain keys for
    flying, so it would do two things at once.
    """
    parsed = parse_binding(binding)
    if not parsed:
        return ""
    bits, _code = parsed
    parts = [p.strip().upper() for p in str(binding).split("+") if p.strip()]
    key = parts[-1] if parts else ""
    canonical = format_binding(bits, key)
    if canonical in KEY_CLASHES:
        return KEY_CLASHES[canonical]
    if bits & MOD_WIN:
        return "Windows and the Xbox Game Bar"
    if not bits & (MOD_CONTROL | MOD_ALT | MOD_SHIFT) \
            and not re.match(r"F\d+$", key):
        return "the game's own controls - add Ctrl, Alt or Shift"
    return ""


class Hotkeys:
    """The work keys - Alt+1 onwards by default - while the game has focus.

    Runs a Windows message loop on its own thread and posts key names onto a
    queue; the window drains that queue from the Tk loop, so nothing off the
    main thread ever touches a widget.
    """

    def __init__(self):
        self.events = queue.Queue()
        self.active = False
        self.problem = ""
        self.bound = {}          # action -> the binding that actually took
        self._thread = None
        self._thread_id = 0
        self._wanted = {}
        self._ready = threading.Event()

    def start(self, bindings):
        self.stop()
        self._wanted = dict(bindings)
        self.bound = {}
        self.problem = ""
        if os.name != "nt":
            self.problem = "global hotkeys are Windows only"
            return
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        # Registration takes milliseconds. Waiting for it means problem and
        # bound are true the moment start() returns, so Settings can say
        # which keys took instead of what was asked for.
        self._ready.wait(1.0)

    def stop(self):
        """Let go of every key, and WAIT until they are let go.

        A key registered with RegisterHotKey belongs to the thread that
        registered it. Save in Settings used to post the old thread its
        WM_QUIT and start the new one at once; the new one asked for Alt+1
        while the old one still held it, was refused, and reported "already
        taken by another program" - then the old thread quit and unregistered
        everything. Every key was dead from the first Save onwards.
        """
        thread = self._thread
        if thread is not None and thread.is_alive():
            self._ready.wait(1.0)
            if self._thread_id:
                try:
                    ctypes.windll.user32.PostThreadMessageW(
                        self._thread_id, WM_QUIT, 0, 0)
                except Exception:
                    pass
            thread.join(2.0)
        self._thread = None
        self._thread_id = 0
        self.active = False

    def _register(self, user32, index, bits, code):
        """RegisterHotKey, asked three times over a third of a second.

        Belt and braces after stop(): if anything still holds the key for a
        moment - the thread being torn down, a program starting - the first
        refusal is not taken as final."""
        for attempt in range(3):
            if user32.RegisterHotKey(None, index, bits | MOD_NOREPEAT, code):
                return True
            time.sleep(0.1)
        return False

    def _run(self):
        try:
            import ctypes.wintypes
            user32 = ctypes.windll.user32
            self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
            # A message queue exists from the first USER call on a thread;
            # PeekMessage makes one before anything can be posted to it.
            message = ctypes.wintypes.MSG()
            user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
            ids = {}
            trouble = []
            for index, (action, key) in enumerate(self._wanted.items(), start=1):
                parsed = parse_binding(key)
                if not parsed:
                    trouble.append("%s is not a key EDSMT can bind" % key)
                    continue
                bits, code = parsed
                if self._register(user32, index, bits, code):
                    ids[index] = action
                    self.bound[action] = key
                else:
                    # Almost always another overlay holding it. Saying which
                    # key - and who usually has it - matters more than
                    # anything else, because the fix is to pick another.
                    who = key_clash(key)
                    trouble.append("%s is already taken by another program%s "
                                   "- pick another in Settings"
                                   % (key_text(key),
                                      " (usually %s)" % who if who else ""))
            # Reported whether or not anything bound: half-working is the
            # case most likely to be mistaken for working.
            self.problem = "  /  ".join(trouble)
            self._ready.set()
            if not ids:
                return
            self.active = True
            message = ctypes.wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) != 0:
                if message.message == WM_HOTKEY and message.wParam in ids:
                    self.events.put(ids[message.wParam])
            for index in ids:
                user32.UnregisterHotKey(None, index)
        except Exception as exc:
            self.problem = str(exc)
        finally:
            self.active = False
            # Never leave start() or stop() waiting on a thread that died.
            self._ready.set()

    def drain(self):
        out = []
        while True:
            try:
                out.append(self.events.get_nowait())
            except queue.Empty:
                return out




# ---------------------------------------------------------------------------
# The plan view
# ---------------------------------------------------------------------------

class PlanView(tk.Canvas):
    """What is around you, drawn to scale, with you in the middle.

    A plain canvas rather than a plotting library: it redraws several times a
    second as the SRV moves, and it has to ship inside a download people will
    actually wait for.
    """

    def __init__(self, parent, on_select=None, on_edit=None):
        super().__init__(parent, bg=VOID, highlightthickness=0, bd=0)
        self.on_select = on_select
        self.on_edit = on_edit
        self._pan = [0.0, 0.0]
        self._drag_from = None
        self._dragged_far = False
        self.rows = []
        self.heading = 0.0
        self.selected_id = None
        self.caption = ""
        self._plan = None
        # The view radius in metres once the wheel has been used; None is
        # "the signal being worked, fitted to the window". Absolute rather
        # than a multiple of the fitted view, which could never get closer
        # than a tenth of wherever the furthest find dragged it.
        self._extent = None
        self._auto_extent = PV.SIGNAL_VIEW_EMPTY_M
        self._widest = PV.SIGNAL_VIEW_EMPTY_M
        self.signal = ""
        # Not `anchor` or `focus`: both are Tk methods on every widget, and
        # an attribute of the same name quietly replaces them.
        self.signal_at = None
        self._place = None
        self.signal_view = None
        self.hidden_labels = 0
        self._taken = []
        self.survey = None
        self.bind("<Configure>", lambda event: self.redraw())
        self.bind("<Button-1>", self._pressed)
        self.bind("<B1-Motion>", self._dragged)
        self.bind("<ButtonRelease-1>", self._released)
        self.bind("<Double-Button-1>", self._double_clicked)
        self.bind("<Button-3>", lambda e: self.recentre())
        self.bind("<MouseWheel>", self._wheel)
        self.bind("<Button-4>", lambda e: self._zoom_by(1 / 1.25))
        self.bind("<Button-5>", lambda e: self._zoom_by(1.25))

    def show(self, rows, heading=0.0, caption="", survey=None, rigs=None,
             signal=None, anchor=None, place=None):
        """`signal` is the signal being worked and `anchor` where it was
        logged (metres east/north of the commander), so the map can open on
        it. `place` is (system, body, signal): arriving somewhere new puts
        the view back on the signal, whatever it was zoomed to before."""
        self.rows = list(rows or [])
        self.heading = heading or 0.0
        self.caption = caption
        self.survey = survey
        self.rigs = rigs
        self.signal = str(signal or "").strip()
        self.signal_at = anchor
        if place is not None and place != self._place:
            if self._place is not None:
                self._extent = None
                self._pan = [0.0, 0.0]
            self._place = place
        self.redraw()

    def select(self, deposit_id):
        self.selected_id = deposit_id
        self.redraw()

    def _double_clicked(self, event):
        """Double-click a pin to fix it. The single click has already
        selected it, so this only has to open the editor."""
        if not self._plan or not self.on_edit:
            return
        hit = PV.hit_test(self._plan["items"], event.x, event.y)
        if hit:
            self.on_edit(hit["deposit"])

    def _wheel(self, event):
        self._zoom_by(1 / 1.25 if event.delta > 0 else 1.25)

    def _zoom_by(self, factor):
        """Closer or further, in steps, between ZOOM_CLOSEST_M and far
        enough to see every find on the body."""
        start = self._extent if self._extent else self._auto_extent
        wanted = start * factor
        self._extent = max(PV.ZOOM_CLOSEST_M,
                           min(max(self._widest, self._auto_extent), wanted))
        self.redraw()

    @property
    def zoomed_out(self):
        """Out past the signal: the rest of the body is drawn too."""
        return bool(self._extent) and self._extent > self._auto_extent * 1.05

    def _pressed(self, event):
        """A press might become a click or a drag. Do not decide yet."""
        self._drag_from = (event.x, event.y)
        self._dragged_far = False

    def _dragged(self, event):
        if self._drag_from is None:
            return
        dx = event.x - self._drag_from[0]
        dy = event.y - self._drag_from[1]
        # A few pixels of wobble while clicking is not a drag. Without this
        # threshold every click on a pin would also nudge the map, which
        # feels broken in a way nobody can quite describe.
        if not self._dragged_far and (dx * dx + dy * dy) < 25:
            return
        self._dragged_far = True
        self._pan[0] += dx
        self._pan[1] += dy
        self._drag_from = (event.x, event.y)
        self.redraw()

    def _released(self, event):
        was_drag, self._drag_from = self._dragged_far, None
        self._dragged_far = False
        if not was_drag:
            self._clicked(event)

    def recentre(self):
        """Back to you in the middle, zoomed to the signal. Right-click, or
        the button."""
        self._pan = [0.0, 0.0]
        self._extent = None
        self.redraw()

    def _clicked(self, event):
        if not self._plan:
            return
        hit = PV.hit_test(self._plan["items"], event.x, event.y)
        self.selected_id = hit["id"] if hit else None
        self.redraw()
        if self.on_select:
            self.on_select(hit["deposit"] if hit else None)

    def redraw(self):
        self.delete("all")
        width = self.winfo_width() or 640
        height = self.winfo_height() or 480

        # The view opens on the signal being worked: its finds, where it was
        # logged, the survey area and the rigs. The rest of the body waits
        # until the wheel takes the view out past it.
        # Only the signal you are at: one further off than SIGNAL_REACH_M -
        # the box still on the last one - is an arrow and a line in the
        # footer, not a view stretched to hold it.
        view = PV.signal_focus(self.rows, self.signal, self.signal_at,
                               near_m=PV.SIGNAL_REACH_M)
        self.signal_view = view
        points = [PV.to_offset(row.get("range_m"), row.get("bearing"))
                  for row in view["here"]]
        if view["how"] == "logged":
            points.append(view["centre"])
        survey = self.survey if isinstance(self.survey, dict) else None
        if survey and survey.get("centre") and survey.get("border_m"):
            # With a survey area set, the whole of it is in view, so the
            # gaps can be seen - not just the patch around the deposits.
            ce, cn = survey["centre"]
            reach = float(survey["border_m"])
            points += [(ce + reach, cn), (ce - reach, cn),
                       (ce, cn + reach), (ce, cn - reach)]
        rigs = getattr(self, "rigs", None)
        rigs = rigs if isinstance(rigs, dict) else None
        if rigs:
            # The rigs stay in view: they are what you have to drive back to.
            points += [(m["east"], m["north"]) for m in rigs.get("rigs") or []]
        # ...while they are at the signal in view. A border or rigs left at a
        # signal you are not at would stretch the view straight back out.
        fe, fn = view["centre"]
        limit = PV.SIGNAL_REACH_M if view["far"] else PV.SIGNAL_NAMED_REACH_M
        points = [p for p in points
                  if math.hypot(p[0] - fe, p[1] - fn) <= limit]
        floor = PV.SIGNAL_VIEW_FLOOR_M if points else PV.SIGNAL_VIEW_EMPTY_M
        self._auto_extent = PV.extent_for(points, floor_m=floor, headroom=1.3,
                                          cap_m=PV.SIGNAL_VIEW_CAP_M)
        self._widest = PV.extent_for(
            [PV.to_offset(r.get("range_m"), r.get("bearing")) for r in self.rows],
            floor_m=self._auto_extent, headroom=1.3)
        extent = self._extent or self._auto_extent
        shown = self.rows if self.zoomed_out else view["here"]
        viewport = PV.Viewport(width, height, extent, pan=self._pan)
        self._plan = PV.layout(shown, viewport, heading=self.heading)
        self._plan["elsewhere"] = 0 if self.zoomed_out else len(view["away"])
        self._plan["far"] = view["far"]

        # Everything a label must not be printed over: the commander, the
        # rigs, the ring labels, the dots, the labels already placed.
        cx, cy = viewport.centre
        self._taken = [(cx - 12, cy - 12, cx + 12, cy + 12)]
        self._swept_percent = None
        if survey:
            self._survey(viewport, survey)
        self._rings(viewport, self._plan)
        if rigs:
            self._rig_marks(viewport, rigs)
        self._deposits(self._plan)
        self._me(viewport, self._plan)
        self._footer(width, height, self._plan)
        if viewport.panned:
            self.create_text(width / 2, height - 10, anchor="s", fill=AMBER,
                             font=F_SMALL,
                             text="dragged off centre - right-click to recentre")

    def _rig_marks(self, viewport, rigs):
        """Each rig as a numbered square in its commodity's colour, with the
        commodity beside it; the square turns red while it is past the
        limit."""
        limit = float(rigs.get("limit_m") or 0)
        for mark in rigs.get("rigs") or []:
            x, y = viewport.to_canvas(mark["east"], mark["north"])
            what = str(mark.get("commodity") or "")
            tint = colour_for(what) if what else AMBER
            far = limit and mark["range_m"] > limit
            self.create_rectangle(x - 6, y - 6, x + 6, y + 6, fill=VOID,
                                  outline=RED if far else tint,
                                  width=2, tags=("rig",))
            self.create_text(x, y, text=str(mark["n"]), fill=RED if far else tint,
                             font=F_MICRO, tags=("rig",))
            taken = getattr(self, "_taken", None)
            if isinstance(taken, list):
                taken.append((x - 7, y - 7, x + 7, y + 7))
                if what:
                    # Beside it where there is room, like a find's name -
                    # never printed over one.
                    self._label(x, y, 6, what[:12], tint,
                                (0, 0, viewport.width, viewport.height),
                                tags=("rig", "rigtype"))

    def _survey(self, viewport, survey):
        """The ground swept, the survey area, the circles to drive and the
        gaps, under everything else.

        Swept ground is a filled disc of scanner range round every place the
        SRV has been; overlapping discs in one colour read as one area. The
        border is a solid ring, the circles to drive are dashed, and each
        gap still inside the border gets a marker and its size.
        """
        # Only inside the border, once there is one: ground swept outside the
        # area being surveyed is not part of the survey and only muddies it.
        slack = viewport.radius_px(float(survey.get("scan_m") or 0)) + 4
        for shape in PV.swept_shapes(survey.get("points"), survey.get("scan_m"),
                                     survey.get("centre"),
                                     survey.get("border_m")):
            if shape[0] == "disc":
                x, y = viewport.to_canvas(shape[1], shape[2])
                r_px = viewport.radius_px(shape[3])
                if -slack <= x <= viewport.width + slack \
                        and -slack <= y <= viewport.height + slack:
                    self.create_oval(x - r_px, y - r_px, x + r_px, y + r_px,
                                     fill=SWEPT, outline="", tags=("swept",))
            else:
                flat = []
                for east, north in shape[1]:
                    flat.extend(viewport.to_canvas(east, north))
                self.create_polygon(flat, fill=SWEPT, outline="",
                                    tags=("swept",))
        centre = survey.get("centre")
        if not centre:
            return
        cx, cy = viewport.to_canvas(*centre)
        for ring in survey.get("rings") or []:
            r = viewport.radius_px(ring)
            self.create_oval(cx - r, cy - r, cx + r, cy + r,
                             outline=CYAN, dash=(6, 6))
        border = survey.get("border_m")
        if border:
            r = viewport.radius_px(border)
            self.create_oval(cx - r, cy - r, cx + r, cy + r,
                             outline=AMBER, width=2)
            # How much is swept goes in the footer, not on the ring: on the
            # ring it sat where finds are, and a dot drawn after it covered it.
            self._swept_percent = survey.get("percent")
        self.create_line(cx - 7, cy, cx + 7, cy, fill=AMBER, width=2)
        self.create_line(cx, cy - 7, cx, cy + 7, fill=AMBER, width=2)
        for gap in survey.get("gaps") or []:
            gx, gy = viewport.to_canvas(gap["east"], gap["north"])
            self._keep_clear(self.create_text(gx, gy, fill=RED, font=F_SMALL_B,
                                              text="GAP %.1f km2" % gap["area_km2"]))

    def _keep_clear(self, item):
        """No label is printed over this one."""
        taken = getattr(self, "_taken", None)
        box = self.bbox(item) if item else None
        if isinstance(taken, list) and box:
            taken.append(box)

    def _rings(self, viewport, plan):
        """The range rings, each labelled once, on the north-east diagonal.

        The labels used to sit in a column straight up the north line, one
        per ring: with more than a handful of rings they printed on top of
        each other. On the diagonal they are spaced out by the rings
        themselves, and a label that would still touch the one before it,
        or run off the canvas, is left off.
        """
        cx, cy = viewport.centre
        bounds = (0, 0, viewport.width, viewport.height)
        slant = math.sqrt(0.5)
        for ring in plan["rings"]:
            r = ring["radius"]
            self.create_oval(cx - r, cy - r, cx + r, cy + r,
                             outline=RULE, dash=(2, 5))
            label = self.create_text(cx + r * slant + 3, cy - r * slant - 3,
                                     text=_metres(ring["metres"]), anchor="sw",
                                     fill=FAINT, font=F_MICRO, tags=("ringlabel",))
            box = self.bbox(label)
            if not box or PV.label_spot([box], self._taken, bounds=bounds) is None:
                self.delete(label)
            else:
                self._taken.append(box)
        self.create_line(cx, 0, cx, viewport.height, fill=GRID)
        self.create_line(0, cy, viewport.width, cy, fill=GRID)
        north = self.create_text(cx, 13, text="N", fill=DIM, font=F_SMALL_B)
        if self.bbox(north):
            self._taken.append(self.bbox(north))

    def _deposits(self, plan):
        """The finds: a dot each, and a label wherever one fits.

        Every dot is drawn. Labels are placed selected-first, then nearest
        first, each in the first free spot beside, across from, under or
        over its dot; one that can only be printed over another is left off
        and counted in the footer - zooming in makes room for it. Finds past
        the edge are one arrow per direction, with the nearest distance and
        how many lie that way.
        """
        bounds = (0, 0, self.winfo_width() or 640, self.winfo_height() or 480)
        onscreen = [item for item in plan["items"] if not item["offscreen"]]
        for item in onscreen:
            r, x, y = item["radius"], item["x"], item["y"]
            self._taken.append((x - r, y - r, x + r, y + r))

        for group in PV.group_offscreen(plan["items"]):
            colour = colour_for(group["commodity"])
            x, y = group["edge"]
            self.create_polygon(PV.arrow_points(x, y, group["bearing"], 8),
                                fill=colour, outline="", tags=("edge",))
            text = _metres(group["range_m"])
            if group["count"] > 1:
                text += "  x%d" % group["count"]
            self._label(x, y, 8, text, colour, bounds, tags=("edge",))

        chosen_id = self.selected_id
        order = sorted(onscreen, key=lambda i: (i["id"] != chosen_id,
                                                i.get("range_m", 0.0)))
        hidden = 0
        for item in order:
            r, x, y = item["radius"], item["x"], item["y"]
            chosen = item["id"] == chosen_id
            colour = colour_for(item["commodity"])
            if chosen:
                self.create_oval(x - r - 6, y - r - 6, x + r + 6, y + r + 6,
                                 outline=AMBER, width=2)
            OV.dot(self, x, y, r, colour, VOID,
                   shared=bool(item["deposit"].get("shared")))
            rigs = item["deposit"].get("rigs")
            label = "%s  %s" % (item["commodity"], _metres(item["range_m"]))
            if rigs:
                label += "  %sR" % rigs
            placed = self._label(x, y, r, label, TEXT if chosen else MUTED,
                                 bounds, bold=chosen, force=chosen,
                                 tags=("label",))
            if not placed:
                hidden += 1
        self.hidden_labels = hidden

    def _label(self, x, y, r, text, colour, bounds, bold=False, force=False,
               tags=()):
        """Put `text` beside the mark at (x, y) where it touches nothing.

        Tries right, left, below, above. `force` keeps the label even when
        every spot is taken - the selected find is never left unnamed.
        Returns the text item, or None when it was left off.
        """
        item = self.create_text(0, 0, text=text, anchor="nw", fill=colour,
                                font=(FONT, 9, "bold" if bold else "normal"),
                                tags=tags)
        box = self.bbox(item)
        if not box:
            return item
        w, h = box[2] - box[0], box[3] - box[1]
        gap = r + 7
        spots = [(x + gap, y - h / 2.0), (x - gap - w, y - h / 2.0),
                 (x - w / 2.0, y + r + 3), (x - w / 2.0, y - r - 3 - h)]
        candidates = [(sx, sy, sx + w, sy + h) for sx, sy in spots]
        free = PV.label_spot(candidates, self._taken, bounds=bounds)
        if free is None and force:
            free = candidates[0]
        if free is None:
            self.delete(item)
            return None
        self.coords(item, free[0], free[1])
        self._taken.append(free)
        return item

    def _me(self, viewport, plan):
        cx, cy = viewport.centre
        self.create_polygon(PV.arrow_points(cx, cy, plan["heading"]),
                            fill=CYAN, outline=VOID)

    def _footer(self, width, height, plan):
        parts = ["rings %s" % _metres(plan["ring_step_m"])]
        done = attr(self, "_swept_percent", None)
        if done is not None:
            parts.append("swept %d%%" % done)
        far = plan.get("far")
        if far:
            parts.append("signal %s is %s %s" % (far["signal"],
                                                 _metres(far["range_m"]),
                                                 PV.compass_point(far["bearing"])))
        away = sum(1 for i in plan["items"] if i["offscreen"])
        if away:
            parts.append("%d beyond the edge" % away)
        if self.hidden_labels:
            parts.append("%d unlabelled - scroll in" % self.hidden_labels)
        elsewhere = plan.get("elsewhere") or 0
        if elsewhere:
            parts.append("%d elsewhere on this body - scroll out"
                         % elsewhere)
        else:
            parts.append("scroll to zoom")
        left = self.create_text(10, height - 10, anchor="sw", fill=FAINT,
                                font=F_MICRO, text="    ".join(parts))
        if self.caption:
            right = self.create_text(width - 10, height - 10, anchor="se",
                                     fill=DIM, font=F_MICRO, text=self.caption)
            # On a narrow window the two used to print over each other.
            # If they would touch, the caption goes up a line instead.
            try:
                if self.bbox(left)[2] + 12 > self.bbox(right)[0]:
                    self.coords(right, width - 10, height - 26)
            except (TypeError, IndexError, tk.TclError):
                pass


# Where high gravity starts, in g. From Settings; kept here as well so the
# Where to land table, which is drawn by a static method, can read it.
HIGH_G = {"limit": 2.0}


def set_high_g(settings):
    try:
        HIGH_G["limit"] = max(0.0, float((settings or {}).get("high_g_warn", 2.0)
                                         or 0))
    except (TypeError, ValueError):
        HIGH_G["limit"] = 2.0


def is_high_g(gravity):
    """True for a body at or over the high-gravity line."""
    try:
        limit = float(HIGH_G["limit"] or 0)
        return bool(limit) and float(gravity or 0) >= limit
    except (TypeError, ValueError):
        return False


def _join_words(words):
    """"rigs", "amount", "density" -> "rigs, amount and density"."""
    words = [str(w) for w in words if str(w)]
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


def _metres(value):
    try:
        metres = float(value)
    except (TypeError, ValueError):
        return "-"
    if metres >= 10000:
        return "{:,.0f} km".format(metres / 1000.0)
    if metres >= 1000:
        return "%.2f km" % (metres / 1000.0)
    return "%.0f m" % metres


# ---------------------------------------------------------------------------
# The window
# ---------------------------------------------------------------------------

class EDSMT(ctk.CTk):
    """One window that follows the game.

    Nothing has to be set up before a find can be recorded. The game already
    knows the system, the body, the position and often the commodity, so the
    only thing a commander should ever have to do is press one key when the
    scanner pings.
    """

    def __init__(self):
        # The theme first, before a single widget exists: a Tk widget keeps
        # the colours it was made with, so this is the only moment the whole
        # window can be dressed at once.
        self.theme_worn = apply_app_theme(load_settings().get("app_theme", "cockpit"))
        super().__init__()
        # Tk's own hook for exceptions raised inside a callback. Without it
        # Tk prints to a console that does not exist in an installed build
        # and carries on, so a broken button is simply a dead button and
        # the commander is told nothing at all. Every silent failure this
        # app has shipped went out through that hole: the missing _rewrap,
        # the duplicated edit_deposit, the TypeError in mark_deposit.
        #
        # Now it lands in crash.log with a traceback and says so on screen.
        self.report_callback_exception = self._callback_failed
        self.title(APP_TITLE)
        self.geometry("1240x780")
        # Width is the real floor: the rail is a fixed 336 and the plan
        # view needs room to be a map rather than a postage stamp. Height
        # used to be a floor too, because the rail ran off the bottom -
        # it scrolls now, so a short window costs you scrolling instead
        # of costing you the deposit fields.
        # The rail is a fixed width, so the floor is that plus enough
        # map to be worth looking at. Anything less squeezes one of
        # the two into uselessness.
        self.minsize(RAIL_WIDTH + SCROLLBAR_W + 420, 560)
        self.configure(fg_color=VOID)

        self.settings = load_settings()
        self.store = SV.Survey(DATA_DIR)
        # Deliberately the SAME folder the survey uses. backup_to() zips
        # every CSV sitting beside it, so putting the books here is what
        # gets sessions.csv into the backup - a separate folder would have
        # left a commander's whole earnings history out of the one file
        # they are told is everything.
        self.earnings = SV.Earnings(DATA_DIR)
        self.earnings.multi = bool(self.settings.get("earnings_multi_session"))
        set_high_g(self.settings)
        # The old tool's file, brought forward through the same importer
        # every other CSV goes through. The store used to carry its own
        # private version of this, which refused the moment this commander
        # had one find of their own - so anybody who tried the app before
        # migrating could never migrate at all, and was told nothing.
        carried = import_finds(self.store,
                               os.path.join(DATA_DIR, "surfaceminingmap.csv"))

        JN.EVENT_LOG = os.path.join(DATA_DIR, "journal-mining-events.log")
        self.watcher = JN.JournalWatcher(self.settings.get("journal_dir") or None)

        self.worker = EDO.Worker()
        self.inara = EDO.InaraClient(self.worker)
        self.inara.configure(self.settings.get("inara_api_key", ""),
                             self.settings.get("inara_enabled", False),
                             self.settings.get("inara_is_being_developed", False))
        self.community = EDO.CommunityClient(self.worker)
        self.community.configure(self.settings.get("community_url", ""),
                                 self.settings.get("community_token", ""),
                                 self.settings.get("community_enabled", False),
                                 self.settings.get("community_share_cmdr_name", True))
        self.updates = EDO.UpdateCheck(self.worker)
        # A newer build: what the check said, the package for this kind of
        # build, and - once downloaded and checked - where it is.
        self.update_info = None
        self.update_package = None
        self.update_ready = None
        self._update_fetching = False
        self._inara_checked = False
        self._last_reported = None

        # Named 'game', not 'state': a CTk window already has a state()
        # method and customtkinter calls it on startup, so assigning
        # self.state = None replaces that method with None and the app dies
        # before it ever draws.
        self.game = None
        self.selected = None
        self._known_body = None
        self._known_world = None
        # What the scanner itself last put in each box, so a later reading
        # can replace it while anything the commander typed is left alone.
        self._autofilled = {}
        # Declared before _build() rather than relied on turning up later.
        # "Does this attribute exist yet" is not a question you can ask a Tk
        # widget class safely - a missing one can resolve through __getattr__
        # to something callable rather than to None, and the guard that was
        # meant to catch it waves it through.
        self.deposit_list = None
        self.deposit_header = None
        # Faults already written to crash.log, so a fault that persists
        # does not fill the file at eighty tracebacks a minute.
        self._seen_trouble = set()
        # Live community prices, folded name -> credits. Empty until the
        # community server has any, at which point they outrank the coarse
        # value bands the box is sorted by.
        self.prices = {}
        # Other commanders' finds, per body: (system, body) lower-cased ->
        # {"at": when fetched, "rows": deposits}. Asked for when a body is
        # reached and again every SHARED_REFRESH_S while on it.
        self.shared = {}
        self._shared_asked = {}
        # Where to land: what each kind of ground has carried (the server's
        # /v1/grounds answer) and the shared sites per system, lower-cased
        # system -> {"at": when, "rows": sites}. Both asked for only while
        # the window is open.
        self.grounds = None
        self._grounds_at = 0.0
        self._grounds_asked = 0.0
        self.land_sites = {}
        self._land_asked = {}
        self._land_error = ""
        self.lander = None
        # The ground the SRV has swept, per body, and the survey area set on
        # it. One map at a time is live; it is saved as it grows.
        self.survey_book = CV.CoverageBook(DATA_DIR)
        self.cmap = None
        self._cmap_saved = 0.0
        # Where the rigs were put down, and whether the too-far warning has
        # sounded for this excursion.
        self.rigs_at = None
        self._rigs_warned = False

        self.hotkeys = Hotkeys()
        self.hotkeys.start(self.wanted_hotkeys(self.settings))

        self.overlay = OV.Overlay(self, tk, self.settings)

        self._build()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        if carried["taken"] or carried["signals"]:
            self.say(import_summary(carried), GREEN)
        if SETTINGS_NOTICE:
            # Last word on the status line, after anything else start-up
            # has to say, and held there long enough to be read.
            notice = "  ".join(SETTINGS_NOTICE)
            self.after(2500, lambda: self.say(notice, AMBER))
        if self.settings.get("overlay_enabled"):
            self.after(600, self.overlay.show)
        if not self.settings.get("asked_to_share"):
            self.after(900, self.ask_to_share)
        # Once, a couple of seconds in, so it never delays the window
        # appearing and never blocks anything if the site is unreachable.
        self.after(2500, lambda: self.updates.check(APP_VERSION))
        self.after(400, self.tick)
        self.after(450, self.fast_tick)

    # -- the first run ---------------------------------------------------

    def ask_to_share(self):
        """Put the share question once, on first run.

        Buried in Settings it never gets found, and a shared database nobody
        contributes to is an empty one. Asked plainly it costs one click and
        the answer sticks either way.
        """
        # The flag follows the window actually opening, and not one line
        # before it. Written first, a single failure inside WelcomeWindow -
        # swallowed by the except below - retired the only place the shared
        # database is ever offered, for good, without a word on screen.
        try:
            WelcomeWindow(self)
        except Exception as exc:
            return self.say("Could not put the sharing question: %s - "
                            "Settings has it whenever you want it." % exc,
                            AMBER)
        self.settings["asked_to_share"] = True
        save_settings(self.settings)

    def set_sharing(self, wanted):
        """Answer from the first-run window, or the Settings switch."""
        self.settings["community_enabled"] = bool(wanted)
        save_settings(self.settings)
        self.community.configure(self.settings.get("community_url", ""),
                                 self.settings.get("community_token", ""),
                                 bool(wanted),
                                 self.settings.get("community_share_cmdr_name", True))
        if wanted:
            self.say("Sharing on. Your finds go to the community map, and "
                     "Find searches everyone else's.", GREEN)
        else:
            self.say("Sharing off. Nothing leaves this machine. "
                     "Settings has it whenever you want it.")

    # -- the overlay -----------------------------------------------------

    def set_overlay(self, wanted):
        """Turn the in-game strip on or off."""
        self.settings["overlay_enabled"] = bool(wanted)
        save_settings(self.settings)
        if wanted:
            self.overlay.show()
            self.overlay.refresh_settings(self.settings)
            self.redraw()
        else:
            self.overlay.hide()
        self.show_overlay_state()

    def toggle_overlay(self):
        self.set_overlay(not self.settings.get("overlay_enabled"))
        if self.settings.get("overlay_enabled"):
            self.say("Overlay on. It shows while the game is in front - "
                     "borderless or windowed only, never over exclusive "
                     "fullscreen.", AMBER)
        else:
            self.say("Overlay off.")

    @staticmethod
    def wanted_hotkeys(data):
        """The keys to register, from settings. One place, not three.

        A key left blank is a key not registered rather than one registered
        to nothing - RegisterHotKey on an empty binding fails, and a failure
        is reported to the commander as "already taken by another program",
        which would be a lie about a key they deliberately cleared.
        """
        actions = ("deposit", "location", "lock", "update", "centre",
                   "border", "rigs", "allup", "trace") \
            + tuple("rig%d" % n for n in range(1, MAX_RIGS + 1)) \
            + tuple("rig%dup" % n for n in range(1, MAX_RIGS + 1))
        wanted = {action: str(data.get("hotkey_" + action,
                                       DEFAULT_SETTINGS["hotkey_" + action]) or "")
                  for action in actions}
        # The rig planner is a beta and off by default. Its key is left
        # free for other programs until somebody switches it on.
        if not data.get("rig_planner"):
            wanted["trace"] = ""
        return {action: key for action, key in wanted.items() if key.strip()}

    def toggle_overlay_lock(self):
        """Unlock to arrange the boxes, lock to play.

        This is a button and a hotkey rather than a settings row, because
        it is something you do WHILE looking at the overlay, with the game
        in front of you - and a settings window you have to open, change,
        save and close is a window that covers the thing you are trying to
        line up.
        """
        if not self.settings.get("overlay_enabled"):
            return self.say("Turn the overlay on first, then unlock it to "
                            "arrange the boxes.", AMBER)
        locked = self.overlay.set_locked(not self.overlay.locked)
        save_settings(self.settings)
        self.show_overlay_state()
        self.redraw()
        if locked:
            self.say("Overlay locked. Clicks go to the game again.", GREEN)
        else:
            self.say("Overlay unlocked. Drag each box by its bar, resize it "
                     "by the bottom-right corner, then lock it again.", AMBER)

    def reset_overlay_layout(self):
        """Put every box back where it started."""
        self.overlay.reset_layout()
        save_settings(self.settings)
        self.redraw()
        self.say("Overlay boxes are back where they started.", GREEN)

    def show_overlay_state(self):
        """Keep the top-bar buttons honest about the overlay.

        Two facts, two buttons: whether it is up at all, and whether it is
        locked. The lock button only appears to be worth pressing while
        there is something on screen to move.
        """
        on = bool(self.settings.get("overlay_enabled"))
        button = attr(self, "btn_overlay")
        if button is not None:
            try:
                button.configure(text="Overlay on" if on else "Overlay",
                                 **(BTN_PRIMARY if on else BTN_SECONDARY))
            except Exception:
                pass
        lock = attr(self, "btn_lock")
        if lock is not None:
            locked = self.overlay.locked
            try:
                lock.configure(text="Unlock" if locked else "LOCK",
                               state="normal" if on else "disabled",
                               **(BTN_SECONDARY if locked else BTN_PRIMARY))
            except Exception:
                pass

    def draw_overlay(self, rows, heading, centre=None, radius_m=None,
                     survey=None, rigs=None, only=None):
        """Hand the overlay everything it needs, not a third of it.

        body, location and site have been in the scope's signature since the
        day it was written and were never passed, so the scope worked out
        its centre from the deposits and the header read "-" for the body.
        The app knows all three, and `site` in particular is the difference
        between a scope centred on the signal you are working and one
        centred on the average of whatever you happen to have logged.
        """
        if not self.overlay.showing:
            return
        note = "" if rows else "nothing recorded on this body yet"
        system, body = self.here()
        location = self.signal()
        site = self.site_offset(system, body, location, centre, radius_m)
        self.overlay.draw(rows, heading, note, body=body,
                          location=location, site=site, survey=survey,
                          rigs=rigs, guide=self.guide_card(),
                          target=attr(self, "_guide_to", None), only=only,
                          cargo=self.overlay_cargo(),
                          hazard=self.overlay_hazard(),
                          rigplan=self.plan_marks(), wing=self.wing_marks())

    def guide_facts(self):
        """What the guide can see has been done, on the signal being worked."""
        state = attr(self, "game", None)
        system, body = self.here()
        signal = str(self.signal())
        facts = {"signal_no": signal}
        try:
            facts["scanned"] = bool(state is not None and state.mining_signals())
        except Exception:
            facts["scanned"] = False
        here = str(getattr(state, "system", "") or "").lower()
        honked = getattr(state, "honked", None) or set()
        facts["honked"] = bool(here and here in honked)
        approached = getattr(state, "approached", None) or ("", "")
        lander = attr(self, "lander")
        try:
            looked = lander is not None and lander.winfo_exists() and \
                str(attr(self, "_land_opened_in", "")).lower() == here
        except Exception:
            looked = False
        facts["chosen"] = bool(here and (looked or
                                         str(approached[0]).lower() == here))
        facts["signal"] = bool(getattr(state, "target_signal", "")) or bool(
            attr(self, "_signal_picked", False))
        gliding = bool(getattr(state, "gliding", False))
        height = getattr(state, "altitude", None)
        facts["gliding"] = gliding
        facts["altitude"] = height
        # Down, or low enough to deploy: touched down, already in the SRV,
        # or out of glide and under DEPLOY_BELOW_M. Having a position is
        # not enough - the game gives one all the way down the glide, and
        # the guide said LAUNCH THE RHINO from orbit.
        facts["landed"] = bool(state is not None and (
            getattr(state, "landed", False) or getattr(state, "in_srv", False)
            or (not gliding and height is not None
                and height <= DEPLOY_BELOW_M)))
        facts["rhino"] = bool(getattr(state, "in_srv", False))
        try:
            row = self.store.location(system, body, signal)
            facts["centre"] = bool(row and str(row.get("lat") or "").strip())
        except Exception:
            facts["centre"] = False
        cmap = self._survey_map() if hasattr(self, "_survey_map") else None
        facts["border"] = bool(cmap is not None and cmap.border_m)
        try:
            if cmap is not None and cmap.centre is not None and \
                    state is not None and state.has_position:
                facts["from_centre_m"] = SV.surface_range_m(
                    state.lat, state.lon, cmap.centre[0], cmap.centre[1],
                    state.radius_m or 1e6)
        except Exception:
            pass
        try:
            marked = len(self.store.at(system, body, signal))
        except Exception:
            marked = 0
        facts["marked"] = marked
        facts["deposit"] = marked > 0
        placed = attr(self, "_guide_rigs", set()) or set()
        facts["rigs"] = bool(self._rigs_here()) or \
            (str(system).lower(), str(body).lower(), signal) in placed
        return facts

    def guide_card(self):
        """The step for the GUIDE box, or None with the guide switched off.

        The guide is for the first run. Once a commander has been through
        it - signal logged, deposit marked, rigs down - it has done its job:
        it shows its last card for GUIDE_FAREWELL_S so the ending is seen,
        then switches itself off. Settings turns it back on, and a guide
        turned back on by hand stays on."""
        settings = attr(self, "settings", None) or {}
        farewell = attr(self, "_guide_farewell", None)
        if farewell and time.time() < farewell[0]:
            return farewell[1]
        if not settings.get("overlay_show_guide", True):
            return None
        try:
            keys = {action: key_text(settings.get("hotkey_" + action, ""))
                    for action in ("location", "border", "deposit", "rigs", "allup")}
            keys["rigs"] = OV.rig_keys_words(settings) or keys["rigs"]
            keys["rigsup"] = OV.rig_keys_words(settings, up=True)
            card = guide_step(self.guide_facts(), keys)
        except Exception:
            return None
        if card and card["step"] == card["total"] and \
                not settings.get("guide_done"):
            self.retire_guide(card)
        return card

    def retire_guide(self, card=None):
        """The first full run is done: the guide says so and bows out."""
        settings = attr(self, "settings", None)
        if not isinstance(settings, dict):
            return False
        settings["guide_done"] = True
        settings["overlay_show_guide"] = False
        save_settings(settings)
        if card:
            card = dict(card)
            card["detail"] = (card.get("detail", "") + "  First run done - "
                              "the guide switches itself off now. Settings "
                              "turns it back on.").strip()
            self._guide_farewell = (time.time() + GUIDE_FAREWELL_S, card)
        self.say("That is the whole run: signal, deposit, rigs. The guide "
                 "switches itself off now - Settings > Basic settings turns "
                 "it back on.", GREEN)
        return True

    def site_offset(self, system, body, location, centre, radius_m):
        """Metres east and north from the commander to the signal centre.

        None whenever any part of that is unknown - no live position, no
        recorded centre for this signal - and the scope then falls back to
        working it out from the deposits, which is what it did before.
        """
        if not centre or not radius_m:
            return None
        row = self.store.location(system, body, location)
        if not row:
            return None
        try:
            return SV.local_offset(float(centre[0]), float(centre[1]),
                                   float(row["lat"]), float(row["lon"]),
                                   float(radius_m))
        except (TypeError, ValueError, KeyError):
            return None

    def _callback_failed(self, kind, value, trace):
        """Something raised inside a Tk callback. Do not let it vanish."""
        import traceback
        detail = "".join(traceback.format_exception(kind, value, trace))
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(os.path.join(DATA_DIR, "crash.log"), "a",
                      encoding="utf-8") as handle:
                handle.write("\n--- %s %s (callback) ---\n%s"
                             % (APP_VERSION, SV.utc_now(), detail))
        except OSError:
            pass
        try:
            self.say("Something went wrong: %s: %s - written to crash.log"
                     % (getattr(kind, "__name__", kind), value), RED)
        except Exception:
            pass

    def colour_for(self, commodity):
        """The overlay asks the app, so a commodity is the same colour on the
        map and on the strip. overlay.py cannot import this module - that
        would be a circle - so it goes through the window instead."""
        return colour_for(commodity)

    def galactic_position(self):
        """Where the commander is in the galaxy, as upload fields.

        Empty until the game says. Location and FSDJump both carry it, so
        it arrives within one jump of the app starting, and an upload made
        before then is still a perfectly good upload - it just cannot be
        found by distance until somebody re-reports that system.
        """
        watcher = attr(self, "watcher")
        position = getattr(watcher, "star_pos", None)
        address = getattr(watcher, "system_address", None)
        out = {}
        if address is not None:
            out["system_address"] = int(address)
        if position and len(position) == 3:
            out["x"], out["y"], out["z"] = (float(v) for v in position)
        return out

    def star_position(self):
        """The commander's position as a plain triple, or None.

        This was called here() and so was the method 600 lines further
        down that answers with (system, body). Python kept the second
        one, so every caller of the triple got a pair of strings instead
        - which CommunityClient._near quietly rejects for not being three
        numbers long. The effect was that "Within 500 Ly" on the Find
        window has never once reached the server. No error, no empty
        result, just a filter that was never applied.
        """
        position = getattr(attr(self, "watcher"), "star_pos", None)
        if position and len(position) == 3:
            return tuple(float(v) for v in position)
        return None

    # -- layout ----------------------------------------------------------

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self._telemetry()
        self._rail()

        centre = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        centre.grid(row=1, column=1, sticky="nsew")
        centre.grid_rowconfigure(0, weight=1)
        centre.grid_columnconfigure(0, weight=1)
        self.plan = PlanView(centre, on_select=self.picked_on_map,
                             on_edit=self.edit_deposit)
        self.plan.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        bracket(centre, colour=ORANGE)

        # The status line is an instrument, not a footnote: a fixed label
        # says what the readout is, the readout follows it, and a rule
        # separates the pair from the map above. The label is packed first
        # so the expanding readout cannot take its pixels.
        strip = ctk.CTkFrame(self, fg_color=RAIL, corner_radius=0)
        strip.grid(row=2, column=0, columnspan=2, sticky="ew")
        ctk.CTkFrame(strip, height=1, fg_color=RULE).pack(fill="x")
        readout = ctk.CTkFrame(strip, fg_color="transparent")
        readout.pack(fill="x")
        ctk.CTkLabel(readout, text="STATUS", font=F_SMALL_B, width=72,
                     text_color=ORANGE, anchor="w").pack(side="left",
                                                         padx=(14, 0), pady=6)
        self.status = ctk.CTkLabel(readout, text="", font=F_READOUT,
                                   text_color=DIM, anchor="w")
        self.status.pack(side="left", fill="x", expand=True,
                         padx=(4, 14), pady=6)

        # Fill it all in from disk before the window is ever shown. Without
        # this the app opens blank with the game shut and stays blank,
        # because the only code that fills it sits past an early return in
        # update_telemetry.
        self.show_records()

    def _telemetry(self):
        bar = ctk.CTkFrame(self, fg_color=RAIL, corner_radius=0)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        bracket(bar, colour=ORANGE)

        badge = ctk.CTkFrame(bar, fg_color="transparent", width=126)
        badge.grid(row=0, column=0, rowspan=3, padx=(16, 14), pady=8)
        ctk.CTkLabel(badge, text=APP_NAME, font=F_TITLE,
                     text_color=ORANGE).pack(anchor="w")
        ctk.CTkLabel(badge, text="SURFACE SURVEY", font=F_MICRO,
                     text_color=FAINT).pack(anchor="w")
        # The strip is an instrument panel, so it is separated from the
        # rail and the map by a rule rather than by a change of shade
        # nobody can see. Row 4, so row 3 is free for the buttons when the
        # window is too narrow to have them beside the readouts.
        ctk.CTkFrame(bar, height=2, fg_color=RULE, corner_radius=0).grid(
            row=4, column=0, columnspan=4, sticky="ew")

        self.t_where = ctk.CTkLabel(bar, text="Looking for Elite Dangerous...",
                                    font=F_HEAD,
                                    text_color=TEXT, anchor="w")
        self.t_where.grid(row=0, column=1, sticky="w", pady=(9, 0))
        self.t_detail = ctk.CTkLabel(bar, text="", font=F_READOUT,
                                     text_color=DIM, anchor="w")
        self.t_detail.grid(row=1, column=1, sticky="w")
        # What the run is worth, on its own line under where you are. The
        # two answer different questions and a commander reads one of them
        # while driving and the other while deciding whether to go home,
        # so they do not share a line.
        self.t_earnings = ctk.CTkLabel(bar, text="", font=F_READOUT,
                                       text_color=AMBER, anchor="w")
        self.t_earnings.grid(row=2, column=1, sticky="w", pady=(0, 9))

        # Two groups. Where things are - Find, My sites, Where to land,
        # Earnings - sit on the left, straight after the readouts, in the
        # space that used to be empty. What the overlay is doing and Settings
        # sit on the right, where they always were.
        bar.grid_columnconfigure(1, weight=0, minsize=TOP_READOUT_ROOM)
        bar.grid_columnconfigure(2, weight=1)
        nav = ctk.CTkFrame(bar, fg_color="transparent")
        nav.grid(row=0, column=2, rowspan=3, padx=(8, 8), sticky="w")
        side = ctk.CTkFrame(bar, fg_color="transparent")
        side.grid(row=0, column=3, rowspan=3, padx=12, sticky="e")
        self._top_bar, self._top_buttons, self._top_nav = bar, side, nav
        self._top_stacked = False
        bar.bind("<Configure>", self._fit_top_bar, add="+")
        ctk.CTkButton(nav, text="Find", width=74, height=32, font=F_STRONG,
                      **BTN_SECONDARY,
                      command=self.open_find).pack(side="left", padx=4)
        ctk.CTkButton(nav, text="My sites", width=92, height=32, font=F_STRONG,
                      **BTN_SECONDARY,
                      command=self.open_sites).pack(side="left", padx=4)
        ctk.CTkButton(nav, text="Where to land", width=124, height=32,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.open_land).pack(side="left", padx=4)
        ctk.CTkButton(nav, text="Earnings", width=96, height=32, font=F_STRONG,
                      **BTN_SECONDARY,
                      command=self.open_earnings).pack(side="left", padx=4)
        self.btn_overlay = ctk.CTkButton(side, text="Overlay", width=88, height=32,
                                         font=F_STRONG, **BTN_SECONDARY,
                                         command=self.toggle_overlay)
        self.btn_overlay.pack(side="left", padx=4)
        # Arranging the overlay happens WHILE looking at the overlay, so the
        # control is here beside it and not four clicks into Settings.
        self.btn_lock = ctk.CTkButton(side, text="Unlock", width=84, height=32,
                                      font=F_STRONG, **BTN_SECONDARY,
                                      command=self.toggle_overlay_lock)
        self.btn_lock.pack(side="left", padx=4)
        ctk.CTkButton(side, text="Settings", width=94, height=32, font=F_STRONG,
                      **BTN_SECONDARY,
                      command=self.open_settings).pack(side="left", padx=4)
        # Built but not packed. It appears only if the website says there is
        # a newer build, so an up-to-date app never carries a button that
        # does nothing.
        self.btn_update = ctk.CTkButton(side, text="UPDATE AVAILABLE",
                                        width=170, height=32, font=F_STRONG,
                                        **BTN_PRIMARY,
                                        command=self.update_button_pressed)
        self.show_overlay_state()

    def _fit_top_bar(self, event=None):
        """Buttons beside the readouts when there is room, under them when not.

        At the app's narrowest the six buttons took the readouts' room and
        the system name and commander were cut off after a dozen letters -
        the one thing that bar is for.
        """
        bar, side = attr(self, "_top_bar"), attr(self, "_top_buttons")
        nav = attr(self, "_top_nav")
        if bar is None or side is None:
            return
        try:
            width = int(bar.winfo_width())
            if width <= 1:
                return
            needed = (170 + TOP_READOUT_ROOM + int(side.winfo_reqwidth())
                      + (int(nav.winfo_reqwidth()) + 16 if nav is not None else 0)
                      + 24)
            stack = width < needed
            if stack == attr(self, "_top_stacked", False):
                return
            self._top_stacked = stack
            if stack:
                if nav is not None:
                    nav.grid_configure(row=3, column=0, columnspan=2, rowspan=1,
                                       sticky="w", padx=12, pady=(0, 8))
                side.grid_configure(row=3, column=2, columnspan=2, rowspan=1,
                                    sticky="e", padx=12, pady=(0, 8))
            else:
                if nav is not None:
                    nav.grid_configure(row=0, column=2, columnspan=1, rowspan=3,
                                       sticky="w", padx=(8, 8), pady=0)
                side.grid_configure(row=0, column=3, columnspan=1, rowspan=3,
                                    sticky="e", padx=12, pady=0)
        except Exception:
            pass

    def open_download_page(self):
        """Send them to the download page. Do not fetch or run anything."""
        try:
            import webbrowser
            webbrowser.open("https://radioraxxla.com/EDSMT/")
            self.say("Opened the download page in your browser.")
        except Exception as exc:
            self.say("Could not open a browser: %s" % exc, RED)

    def _rail(self):
        # The rail is taller than the window on a small screen, and what
        # falls off the bottom is the MARK DEPOSIT block and the four
        # fields that describe the deposit - the controls the whole app
        # exists for. A packed column has no way to give them back: they
        # are not clipped, they are simply never laid out.
        #
        # So the rail is a fixed-width column holding a scroller, rather
        # than a fixed-width column holding widgets. The width stays put
        # (the map must not be squeezed by a long commodity name) and the
        # height stops mattering. The outer frame carries the extra
        # pixels the scrollbar eats, so the fields are as wide as they
        # were before.
        # 336 was too narrow and the result was worse than the problem it
        # fixed: the scroller's inner frame was wider than its viewport, so
        # every control was clipped from the LEFT - "log this one" rendered
        # as "g this one" and "Worked out" as "ked". A scrollbar that hides
        # the first half of every button is not a layout, it is damage.
        #
        # The width now fits the widest control with the scrollbar's own
        # pixels accounted for separately, and the scroller is pinned to
        # that width so its children can never demand more than it shows.
        frame = ctk.CTkFrame(self, fg_color=RAIL, corner_radius=0,
                             width=RAIL_WIDTH + SCROLLBAR_W)
        frame.grid(row=1, column=0, sticky="nsew")
        frame.grid_propagate(False)
        # MARK DEPOSIT and its four fields are PINNED to the bottom and do
        # not scroll. They are what you press every thirty seconds, and on
        # a 750px window the two lists above ate the space and pushed them
        # off the end - so the one control the app exists for was the one
        # you could not reach. Packed side="bottom" BEFORE the scroller, so
        # Tk gives them their height first and the lists get the remainder.
        pinned = ctk.CTkFrame(frame, fg_color=RAIL, corner_radius=0)
        pinned.pack(side="bottom", fill="x")
        rail = ctk.CTkScrollableFrame(frame, fg_color=RAIL, corner_radius=0,
                                      width=RAIL_WIDTH,
                                      scrollbar_button_color=RULE,
                                      scrollbar_button_hover_color=ORANGE)
        rail.pack(side="top", fill="both", expand=True)

        # ---- the signals on this body, FIRST ----
        #
        # The rail follows the order of operations rather than the order the
        # buttons were written in. You drive into a signal and log it
        # BEFORE you ping anything, so the signal list belongs above the
        # deposit button, not under it.
        hud_header(rail, "Mining locations", trailing=lambda bar:
                   ctk.CTkButton(bar, text="log this one", width=122,
                                 height=26, font=F_SMALL, **BTN_SECONDARY,
                                 command=self.log_location))

        picker = ctk.CTkFrame(rail, fg_color="transparent")
        picker.pack(fill="x", padx=12, pady=(2, 4))
        ctk.CTkLabel(picker, text="Signal", width=76, anchor="w",
                     font=F_BODY, text_color=DIM).pack(side="left")
        self.location_box = ctk.CTkComboBox(
            picker, values=[str(n) for n in range(1, MAX_LOCATIONS + 1)],
            font=F_BODY, height=30, **BOX, command=lambda _: self.redraw())
        self.location_box.set("1")
        self.location_box.bind("<Return>", lambda _e: self.redraw())
        self.location_box.pack(side="left", fill="x", expand=True)

        actions = ctk.CTkFrame(rail, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(4, 0))
        ctk.CTkButton(actions, text="Best patch", height=28,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.show_best_patch).pack(side="left",
                                                         fill="x", expand=True,
                                                         padx=(0, 3))
        ctk.CTkButton(actions, text="Worked out", height=28,
                      font=F_STRONG, **BTN_WARN,
                      command=self.mark_worked_out).pack(side="left",
                                                         fill="x", expand=True,
                                                         padx=(3, 0))

        self.location_note = ctk.CTkLabel(
            rail, text="", font=F_SMALL, text_color=DIM,
            justify="left", anchor="w", wraplength=RAIL_WIDTH - 34)
        self.location_note.pack(fill="x", padx=14, pady=(2, 8))

        self.location_box_list = ctk.CTkScrollableFrame(rail, height=124,
                                                        **LIST)
        self.location_box_list.pack(fill="x", padx=12, pady=(0, 8))

        # ---- the deposits inside the selected signal ----
        #
        # Editing one meant finding its pin on the map and double-clicking it,
        # which is fine when you know and invisible when you do not. Every
        # deposit is now one click from the rail with its own edit button,
        # exactly like the signals above.
        # The count goes on the header itself, so the section label and the
        # instrument reading are the same object rather than two things that
        # can disagree.
        hud_header(rail, "Deposits", pady=(8, 2), trailing=lambda bar:
                   self._deposit_count(bar))

        self.deposit_list = ctk.CTkScrollableFrame(rail, height=122, **LIST)
        self.deposit_list.pack(fill="x", padx=12, pady=(0, 8))

        # ---- the survey area: moving or clearing it ----
        #
        # Setting the centre is logging the signal and the border is on
        # the pad below with the other keys; what is left up here is the
        # occasional: moving the centre, or starting the area again.
        hud_header(rail, "Survey area", pady=(8, 2))
        ctk.CTkLabel(rail, text="Logging the signal (%s) sets the centre. "
                                "Drive to the edge and press BORDER (%s). The "
                                "ground you sweep is painted inside it."
                                % (self.key("location"), self.key("border")),
                     font=F_SMALL, text_color=DIM, justify="left", anchor="w",
                     wraplength=RAIL_WIDTH - 34).pack(fill="x", padx=14,
                                                     pady=(2, 4))
        survey_row = ctk.CTkFrame(rail, fg_color="transparent")
        survey_row.pack(fill="x", padx=12, pady=(0, 8))
        for label, command in (("MOVE CENTRE HERE", self.set_survey_centre),
                               ("CLEAR", self.clear_survey)):
            ctk.CTkButton(survey_row, text=label, height=28,
                          font=F_STRONG, **BTN_SECONDARY,
                          command=command).pack(side="left", fill="x",
                                                expand=True, padx=(0, 6))

        # ---- the pad: every key you press in the SRV, PINNED ----
        #
        # At the standard window size the survey and rig buttons were below
        # the fold of the scroller, so half the job needed scrolling to find.
        # Everything pressed in the SRV now sits in one block that never
        # scrolls, in the order a site is worked: log the signal, set the
        # border, mark deposits, drop rigs, pick them up. Each button carries
        # its key, so the pad doubles as the key card.
        #
        # Built bottom-up, because pack(side="bottom") stacks upwards: the
        # notes go down first, then the fields, then the buttons.
        notes = ctk.CTkFrame(pinned, fg_color="transparent")
        notes.pack(side="bottom", fill="x", padx=12, pady=(2, 8))
        ctk.CTkLabel(notes, text="Amount is how much is left, Density how "
                                 "rich it is. Rigs can wait till you get there.",
                     font=F_SMALL, text_color=FAINT, justify="left",
                     anchor="w", wraplength=RAIL_WIDTH - 30).pack(fill="x",
                                                                 padx=2)
        self.survey_note = ctk.CTkLabel(
            notes, text="Log the signal (%s), then drive to the edge and "
                        "press %s." % (self.key("location"),
                                       self.key("border", "BORDER")),
            font=F_SMALL, text_color=DIM, justify="left", anchor="w",
            wraplength=RAIL_WIDTH - 30)
        self.survey_note.pack(fill="x", padx=2)
        self.rigs_note = ctk.CTkLabel(
            notes, text=self.rigs_hint(), font=F_SMALL, text_color=DIM,
            justify="left", anchor="w", wraplength=RAIL_WIDTH - 30)
        self.rigs_note.pack(fill="x", padx=2)

        # Amount before Density, because that is the order you learn them in.
        self.fields = {}
        for label, key, values in reversed((
                ("Commodity", "commodity", list(SV.KNOWN_COMMODITIES)),
                ("Rigs", "rigs", [""] + [str(n) for n in range(1, MAX_RIGS + 1)]),
                ("Amount", "amount", [""] + AMOUNT_LEVELS),
                ("Density", "density", [""] + DENSITY_LEVELS))):
            row = ctk.CTkFrame(pinned, fg_color="transparent")
            row.pack(side="bottom", fill="x", padx=12, pady=2)
            ctk.CTkLabel(row, text=label, width=76, anchor="w",
                         font=F_BODY, text_color=DIM).pack(side="left")
            box = ctk.CTkComboBox(row, values=values, font=F_BODY,
                                  height=30, **BOX)
            box.set("")
            box.pack(side="left", fill="x", expand=True)
            self.fields[key] = box
            # Every box opens its list when you click or tab into it, and the
            # commodity list follows what you type. The commodity list is
            # worked out afresh each time, so it is always in the right
            # order for the body under you.
            if key == "commodity":
                self._suggest_commodity = Suggest(
                    box, lambda typed: self.refresh_commodities(typed))
            else:
                Suggest(box, values)
            # A choice picked with the mouse from the box's own arrow list
            # leaves the keyboard in the box it was picked in, so Tab goes on
            # to the next one - click, pick, Tab, as with the keys alone.
            box.configure(command=lambda _value, b=box: keep_keyboard(b))
        chain_tab([self.fields["commodity"], self.fields["rigs"],
                   self.fields["amount"], self.fields["density"]])

        # MARK records a new deposit. UPDATE writes what the boxes say onto
        # the one you are already standing on - the Amount going down as
        # you work it - instead of adding a second copy of it.
        mark_row = ctk.CTkFrame(pinned, fg_color="transparent")
        mark_row.pack(side="bottom", fill="x", padx=12, pady=(6, 6))
        # Not btn_update: that name is the top bar's UPDATE AVAILABLE, and
        # sharing it had a new build's announcement relabel this button.
        self.btn_update_deposit = ctk.CTkButton(
            mark_row, text="UPDATE", width=96, height=54,
            font=F_STRONG, **BTN_SECONDARY, command=self.update_deposit_here)
        self.btn_update_deposit.pack(side="right", padx=(6, 0))
        self.btn_mark = ctk.CTkButton(
            mark_row, text="MARK DEPOSIT", height=54,
            font=F_ACTION, **BTN_PRIMARY, command=self.mark_deposit)
        self.btn_mark.pack(side="left", fill="x", expand=True)

        # The site keys, in the order a site is worked.
        keys_row = ctk.CTkFrame(pinned, fg_color="transparent")
        keys_row.pack(side="bottom", fill="x", padx=12, pady=(10, 0))
        self.pad = {}
        for name, command in (("signal", self.log_location),
                              ("border", self.set_survey_border),
                              ("rigs", self.drop_rigs),
                              ("allup", self.rigs_up)):
            button = ctk.CTkButton(keys_row, text=name, height=42, width=84,
                                   font=F_SMALL_B, **BTN_SECONDARY,
                                   command=command)
            button.pack(side="left", fill="x", expand=True,
                        padx=(0 if name == "signal" else 4, 0))
            self.pad[name] = button
        ctk.CTkFrame(pinned, height=2, fg_color=RULE,
                     corner_radius=0).pack(side="bottom", fill="x", padx=12)
        self.refresh_key_labels()

        hud_header(rail, "Selected deposit", pady=(8, 2))
        self.detail = ctk.CTkLabel(rail, text="Click a deposit on the map.",
                                   font=F_BODY, text_color=DIM,
                                   justify="left", anchor="nw", wraplength=RAIL_WIDTH - 34)
        self.detail.pack(fill="both", expand=True, padx=14, pady=10)

        self.detail_buttons = ctk.CTkFrame(rail, fg_color="transparent")
        ctk.CTkButton(self.detail_buttons, text="MINED OUT", height=32,
                      font=F_STRONG, **BTN_WARN,
                      command=self.mark_mined).pack(fill="x", pady=(2, 4))
        ctk.CTkButton(self.detail_buttons, text="Edit  (or double-click it)",
                      height=30, font=F_STRONG, **BTN_SECONDARY,
                      command=self.edit_selected).pack(fill="x", pady=2)
        ctk.CTkButton(self.detail_buttons, text="Copy to share", height=30,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.copy_selected).pack(fill="x", pady=2)
        ctk.CTkButton(self.detail_buttons, text="Delete", height=30,
                      font=F_STRONG, **BTN_DANGER,
                      command=self.delete_selected).pack(fill="x", pady=2)

    def key(self, action, button=""):
        """The key bound to an action, as written on screen - "Alt+1" - or,
        when it has none, the button that does it. Every message that tells
        a commander which key to press asks this, so none of them can go on
        naming a key that was moved."""
        return bound_key(attr(self, "settings", None), action, button)

    def refresh_key_labels(self):
        """The pad's buttons carry the keys actually bound, not the ones
        they shipped with - a commander who moves RIG DOWN to Ctrl+R must
        not be told F7 by the button he reads it off."""
        pad = attr(self, "pad", None) or {}
        settings = attr(self, "settings", None) or {}

        def key(name):
            return str(settings.get(name, DEFAULT_SETTINGS[name]) or "").strip()

        labels = {"signal": ("LOG SIGNAL", key_text(key("hotkey_location"))),
                  "border": ("BORDER", key_text(key("hotkey_border"))),
                  "rigs": ("RIG DOWN", OV.rig_keys_words(settings)
                           or key_text(key("hotkey_rigs"))),
                  "allup": ("RIGS UP", key_text(key("hotkey_allup")))}
        for name, (words, bound) in labels.items():
            button = pad.get(name)
            if button is not None:
                button.configure(text=words + ("\n" + bound if bound else ""))
        mark = attr(self, "btn_mark", None)
        if mark is not None:
            bound = key_text(key("hotkey_deposit"))
            mark.configure(text="MARK DEPOSIT" + ("   " + bound if bound else ""))
        # btn_update_deposit, not btn_update: that one is the top bar's
        # UPDATE AVAILABLE, and relabelling it would announce a new build.
        update = attr(self, "btn_update_deposit", None)
        if update is not None:
            bound = key_text(key("hotkey_update"))
            update.configure(text="UPDATE" + ("\n" + bound if bound else ""))

    def _deposit_count(self, parent):
        """The deposit section's own reading, built into its header."""
        self.deposit_header = ctk.CTkLabel(parent, text="SIGNAL -  (0)",
                                           font=F_SMALL_B, text_color=DIM,
                                           anchor="e")
        return self.deposit_header

    # -- the loop --------------------------------------------------------

    def tick(self):
        """Poll the game. On the Tk loop, never on a thread.

        Four separate things happen in here and only the first one is the
        journal, but every failure in all four came out as "Journal
        problem: ...". A TypeError in the data store was blamed on the
        journal reader for weeks because of it, and the reader was fine.
        The stage is tracked as it goes, so the line on screen names what
        actually broke.
        """
        stage = "Journal"
        try:
            self.game = self.watcher.poll()
            stage = "Earnings"
            # Its own stage, and not part of "Journal". The books decide
            # where one run ends and the next begins, which is a judgement
            # the reader deliberately does not make - so a mistake in here
            # is a mistake in here, and must not go out under the reader's
            # name the way every fault in tick used to.
            for note in self.watcher.drain_runs():
                if note.get("event") == "Refined":
                    self.credit_refined(note)
                self.earnings_note(self.earnings.observe(note))
            self.save_refined()
            self.show_tonnes()
            stage = "Display"
            self.update_telemetry(self.game)
            # Back to Earnings for the readout as well as the bookkeeping.
            # "Display problem: ..." over a broken hold value would send
            # somebody looking at the map code.
            stage = "Earnings"
            self.update_earnings()
            stage = "Online reporting"
            self.report_online(self.game)
        except Exception as exc:
            self.trouble(stage, exc)
        finally:
            # Always, whatever the journal just did. Results are not the
            # game's business.
            self.collect_results()
            self.follow_land()
            self.follow_update()
            try:
                self.wing_tick()
            except Exception as exc:
                self.trouble("Wing link", exc)
            self.after(700, self.tick)

    def fast_tick(self):
        """Ten times a second: the keys, then the compass and the scope.

        Both used to live at the end of tick(), which reads the journal,
        rebuilds the lists and redraws the whole map every 700 ms. So a key
        pressed in the SRV waited up to 0.7 s to be heard - and was never
        heard at all whenever anything earlier in that tick failed, because
        the failure skipped straight past the keys. The compass and scope
        were as old as the last tick, which is what "slow as hell" looked
        like at the Rhino's nose. Here they read only Status.json, and a
        fault in one of them cannot silence the other.
        """
        moved = False
        try:
            watcher = attr(self, "watcher")
            if watcher is not None:
                moved = watcher.poll_status()
                if attr(self, "game") is None:
                    self.game = watcher
        except Exception as exc:
            self.trouble("Status", exc)
        try:
            if moved:
                self.follow_trace(attr(self, "game"))
        except Exception as exc:
            self.trouble("Rig planner", exc)
        try:
            self.run_hotkeys()
        except Exception as exc:
            self.trouble("Hotkey", exc)
        # A search answered by the server waited for the next slow tick -
        # up to 0.7 s after it had arrived, behind a journal read and a map
        # redraw. Collecting is a non-blocking look at a queue.
        try:
            self.collect_results()
        except Exception as exc:
            self.trouble("Results", exc)
        try:
            if moved:
                self.overlay_fast()
        except Exception as exc:
            self.trouble("Overlay", exc)
        finally:
            self.after(FAST_TICK_MS, self.fast_tick)

    def run_hotkeys(self):
        """Every key pressed since last time, each in its own try.

        Each key says what it did over the game; one that flashes nothing
        itself has its status line flashed. A key that fails says which one
        failed and the next key still runs."""
        hotkeys = attr(self, "hotkeys")
        if hotkeys is None:
            return 0
        done = 0
        # What each key runs, and the name a fault in it goes out under.
        table = {
            "location": ("Log location", self.log_location),
            "lock": ("Overlay lock", self.toggle_overlay_lock),
            "update": ("Update deposit", self.update_deposit_here),
            "centre": ("Survey centre", self.set_survey_centre),
            "border": ("Survey border", self.set_survey_border),
            "rigs": ("Rigs down", self.drop_rigs),
            "allup": ("Rigs up", self.rigs_up),
            "deposit": ("Mark deposit", self.mark_deposit),
            "trace": ("Rig planner", self.trace_key),
        }
        # Each rig its own key: rig 1 to 6 down, and up again.
        for n in range(1, MAX_RIGS + 1):
            table["rig%d" % n] = ("Rig %d down" % n,
                                  lambda n=n: self.drop_rigs(n))
            table["rig%dup" % n] = ("Rig %d up" % n,
                                    lambda n=n: self.rig_up(n))
        for action in hotkeys.drain():
            stage, method = table.get(action, ("Hotkey", None))
            if method is None:
                continue
            self._flashed = False
            try:
                method()
                if not attr(self, "_flashed", False):
                    self.flash_said()
                done += 1
            except Exception as exc:
                self.trouble(stage, exc)
        return done

    def overlay_fast(self):
        """The compass and the scope, redrawn from where you are right now.

        Only those two boxes: they are the ones that turn with the Rhino.
        The lists, the cards and the main map keep the 700 ms tick. The
        survey's percentage and gaps are taken from the last full redraw -
        they do not change between two readings of Status.json."""
        overlay = attr(self, "overlay", None)
        if overlay is None or not overlay.showing:
            return False
        state = attr(self, "game")
        system, body = self.here()
        if not (state is not None and state.has_position and system and body):
            return False
        panels = getattr(overlay, "panels", None) or {}
        only = [key for key in (OV.STRIP, OV.RADAR) if key in panels] \
            if panels else None
        if panels and not only:
            return False
        radius = state.radius_m or 1e6
        centre = (state.lat, state.lon)
        rows = self.store.near(system, body, centre[0], centre[1], radius)
        rows = rows + self.shared_near(system, body, centre, radius, rows)
        survey = self.survey_view(system, body, centre, radius, quick=True)
        rigs = self.watch_rigs(state)
        self.draw_overlay(rows, state.heading or 0.0, centre=centre,
                          radius_m=radius, survey=survey, rigs=rigs, only=only)
        return True

    def trouble(self, stage, exc):
        """Something inside tick failed. Name it, and write it down once.

        tick runs every 700ms, so a fault that persists would otherwise put
        the same traceback into crash.log eighty times a minute. The first
        one is the useful one and the rest are noise, so the fingerprint is
        remembered and only the message on screen repeats.
        """
        import traceback
        detail = traceback.format_exc()
        try:
            self.say("%s problem: %s" % (stage, exc), RED)
        except Exception:
            pass
        # isinstance, not "is None". A missing attribute on a Tk widget
        # class resolves through __getattr__ to something callable rather
        # than to None, so the guard that was meant to catch it waves it
        # through and the next line fails on a function.
        seen = attr(self, "_seen_trouble")
        if not isinstance(seen, set):
            seen = self._seen_trouble = set()
        fingerprint = (stage, type(exc).__name__, str(exc))
        if fingerprint in seen:
            return
        seen.add(fingerprint)
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(os.path.join(DATA_DIR, "crash.log"), "a",
                      encoding="utf-8") as handle:
                handle.write("\n--- %s %s (%s) ---\n%s"
                             % (APP_VERSION, SV.utc_now(), stage, detail))
        except OSError:
            pass

    def here(self):
        """Where we are, or failing that, where we last were.

        The fallback is not cosmetic. Tidying up finds is something you do
        with the game shut, and without a body there is nothing to draw, no
        deposits to double-click and no way to correct anything. The last
        body seen is remembered in settings so it survives a restart too.
        """
        if self.game is not None and (self.game.system or self.game.body):
            return self.game.system or "", self.game.body or ""
        return (self.settings.get("last_system", "") or "",
                self.settings.get("last_body", "") or "")

    def remember_body(self, system, body):
        if not (system and body):
            return
        if (self.settings.get("last_system"), self.settings.get("last_body")) \
                != (system, body):
            self.settings["last_system"] = system
            self.settings["last_body"] = body
            save_settings(self.settings)

    def signal(self):
        return self.location_box.get().strip() or "1"

    def update_telemetry(self, state):
        if not state.running:
            trouble = bool(getattr(state, "problem", ""))
            self.t_where.configure(text=state.where,
                                   text_color=RED if trouble else DIM)
            self.t_detail.configure(
                text="Settings -> Test connection says exactly what it can "
                     "and cannot see." if trouble
                else "Start the game and this fills in on its own.")
            self.set_mark_ready(False)
            # The lists and the map still follow the disk. Everything that
            # fills them used to sit PAST this return, so with Elite shut
            # the signal list, the deposit list, the commodity box and the
            # map were all blank - and tidying finds up with the game shut
            # is a thing people do. The fallbacks written for exactly that
            # case were unreachable.
            self.follow_body()
            self.redraw()
            return

        self.t_where.configure(text=state.where, text_color=TEXT)
        self.follow_target(state)
        self.follow_arrival(state)
        self.follow_deposit(state)
        self.follow_gravity(state)

        bits = []
        if state.has_position:
            bits.append("%.5f, %.5f" % (state.lat, state.lon))
            if state.heading is not None:
                bits.append("hdg %03.0f %s" % (state.heading,
                                               SV.compass(state.heading)))
        else:
            bits.append("no surface position - drop to the surface")
        if state.detected_type:
            bits.append("scanner: %s" % state.detected_type)
        if state.detected_density:
            bits.append("density: %s" % state.detected_density)
        found = state.mining_signals()
        if found:
            bits.append("DSS: %d mining location(s)" % found)
        temp = state.body_temperature()
        if temp:
            bits.append("%.0f K" % temp)
        self.t_detail.configure(text="   ".join(bits), text_color=CYAN)

        # everything the game names, filled in without being asked
        if state.detected_type:
            self._autofill("commodity", SV.remember(state.detected_type))
        if state.detected_density:
            self._autofill("density", state.detected_density)

        self.follow_body()
        self.set_mark_ready(state.has_position)
        self.redraw()

    def gravity_here(self, state=None):
        """The surface gravity of the body you are at, in g, or None."""
        state = state if state is not None else attr(self, "game")
        if state is None or not getattr(state, "body", ""):
            return None
        try:
            gravity = float(state.body_profile().get("gravity") or 0)
        except Exception:
            return None
        return gravity or None

    def follow_gravity(self, state):
        """The big warning, once, on arriving at a high-gravity body.

        On the way down - approaching, gliding, or anywhere with a surface
        position - not on the menu screen. Once per body per session: the red
        bar on GUIDE and STATUS stays for as long as you are there, and the
        triangle in the middle of the screen is for the arrival."""
        gravity = self.gravity_here(state)
        body = str(getattr(state, "body", "") or "")
        if not (gravity and is_high_g(gravity) and body):
            return False
        near = (getattr(state, "has_position", False)
                or getattr(state, "gliding", False)
                or tuple(getattr(state, "approached", ("", "")) or ("", ""))[1:]
                == (body,))
        warned = attr(self, "_g_warned", None)
        if not isinstance(warned, set):
            warned = self._g_warned = set()
        if not near or body.lower() in warned:
            return False
        warned.add(body.lower())
        self.say("HIGH GRAVITY - %s is %.2f g. Take the landing and the Rhino "
                 "slowly." % (body, gravity), RED)
        overlay = attr(self, "overlay", None)
        shower = getattr(overlay, "alarm", None)
        if callable(shower):
            try:
                shower("HIGH GRAVITY %.2f g" % gravity, body.upper()[:40])
                self.after(10000, self._gravity_alarm_done)
            except Exception:
                pass
        return True

    def _gravity_alarm_done(self):
        # Not while the rig alarm is up: that one is the same window, and it
        # comes down when the rig is safe, not on a timer.
        if not attr(self, "_rigs_final", False):
            self.clear_rig_alarm()

    def overlay_hazard(self):
        """{"text": ...} for the red bar on the boxes, or None."""
        gravity = self.gravity_here()
        if gravity and is_high_g(gravity):
            return {"text": "HIGH GRAVITY %.2f g" % gravity, "gravity": gravity}
        return None

    def overlay_cargo(self):
        """The ship's and the Rhino's holds for STATUS, during a session."""
        watcher = attr(self, "watcher")
        books = attr(self, "earnings")
        in_srv = bool(getattr(watcher, "in_srv", False))
        live = books is not None and books.rhino is not None
        if not (in_srv or live):
            return None
        holds = dict(getattr(watcher, "holds", None) or {})
        tonnes, capacity = self.ship_hold()
        rhino = sum(int(v) for v in dict(holds.get("SRV") or {}).values() if v)
        return {"ship_t": tonnes, "capacity": capacity,
                "rhino_t": rhino if in_srv else None}

    # -- what the run is worth -------------------------------------------

    def market_prices(self):
        """What the last market seen pays, keyed by commodity name.

        The last one seen rather than the best one anywhere. It is the only
        price this app can stand behind without asking a server, and a hold
        priced at a station the commander has personally stood in is a
        figure they can go and check. Everything the market does not buy
        simply is not in here, so hold_value leaves it out rather than
        guessing at it.
        """
        market = attr(self.watcher, "market") or {}
        prices = {}
        for item in market.get("items") or []:
            name = str(item.get("commodity") or "")
            if name:
                prices[name] = item.get("sell") or 0
        return prices

    def update_earnings(self):
        """The hold and the run in progress, live on the strip.

        Two numbers a commander currently has to leave the game and open a
        spreadsheet to find out. Both are already on disk or already in the
        reader, so this costs nothing and runs every tick.
        """
        label = attr(self, "t_earnings")
        if label is None:
            return
        bits = []
        # Both holds. Out in the SRV, Cargo.json is the SRV's, and a strip
        # that read only that said "hold 6t" over a ship with thirty tonnes
        # of ore in it. Only what a Rhino session dug up (1.10031): hauled
        # cargo is somebody else's business, not these earnings.
        cargo = self.mined_aboard()
        tonnes = sum(int(count) for count in cargo.values())
        if tonnes:
            hold = "mined aboard %dt" % tonnes
            worth = SV.hold_value(cargo, self.market_prices())
            if worth:
                where = (attr(self.watcher, "market") or {}).get("station")
                hold += " worth %s Cr at %s" % (credits_text(worth),
                                                where or "the last market seen")
            else:
                # Saying nothing here reads as "worth nothing". The hold is
                # real either way; what is missing is a price for it - and
                # the galactic average is a fair estimate until there is one.
                guess = self.hold_estimate(cargo)
                hold += (" - about %s Cr at the galactic average"
                         % credits_text(guess)) if guess else \
                    " - no market prices seen yet"
            best, radius, priced, aboard = self.best_nearby(cargo)
            if best:
                hold += ", up to %s Cr within %d Ly" % (credits_text(best),
                                                        radius)
                if priced < aboard:
                    hold += " (%d of %d priced)" % (priced, aboard)
            bits.append(hold)
        run = self.earnings.rhino
        if run is not None:
            hours = SV.session_hours(run)
            mined = sum(SV.unpack_counts(run.get("mined")).values())
            moved = sum(SV.unpack_counts(run.get("transferred")).values())
            text = "Rhino session %s%s - %d t mined, %d t to the ship" % (
                duration_text(hours),
                " PAUSED" if self.earnings.paused else "", mined, moved)
            if SV.earned(run):
                text += ", %s Cr sold" % credits_text(SV.earned(run))
            bits.append(text)
        label.configure(text="   ".join(bits))

    def hold_now(self):
        """Everything aboard, ship and SRV together."""
        watcher = attr(self, "watcher")
        return combined_hold(getattr(watcher, "holds", None),
                             getattr(watcher, "cargo", None))

    def mined_aboard(self):
        """What is aboard that a Rhino session dug up and has not sold.

        The hold with anything bought, hauled or picked up elsewhere left
        out: each commodity is the smaller of what is aboard and what recent
        Rhino sessions mined and nobody has sold yet. That is what the
        earnings are about, and all the Earnings tab prices."""
        try:
            cargo = self.hold_now()
            if not cargo:
                return {}
            unsold = {SV.fold(name): count for name, count in
                      self.earnings.unsold().items()}
        except Exception:
            return {}
        mined = {}
        for name, count in cargo.items():
            spare = min(int(count), int(unsold.get(SV.fold(name), 0)))
            if spare > 0:
                mined[name] = spare
        return mined

    def galactic_average(self, name):
        """(price, "game") from the galactic average column of any market
        seen, else (price, "table") from EDSMT's own table, else (0, "")."""
        means = getattr(attr(self, "watcher"), "means", None) or {}
        mean = int(means.get(SV.fold(name)) or 0)
        if mean > 0:
            return mean, "game"
        table = int(SV.published_price(name) or 0)
        return (table, "table") if table > 0 else (0, "")

    def hold_estimate(self, cargo):
        """What a hold comes to at the galactic average - an estimate."""
        return sum(self.galactic_average(name)[0] * int(count)
                   for name, count in dict(cargo or {}).items())

    def quote_hold(self, radius=None):
        """Ask where what is aboard sells best, near where the commander is.

        Asked from the system the game says we are in, by name, because the
        market index measures its distances from a system name - and it is
        that system's own price that says whether the drive is worth it.
        Returns how many commodities were asked about; 0 says why not.
        """
        community = attr(self, "community")
        if community is None or not community.can_read:
            return 0, "No community URL set. Settings has it."
        system = str(getattr(attr(self, "watcher"), "system", "") or "")
        if not system:
            return 0, "The game has not said which system you are in yet."
        wanted = worth_asking(self.mined_aboard())
        if not wanted:
            return 0, "Nothing mined aboard to price."
        radius = int(radius or QUOTE_DISTANCES[DEFAULT_QUOTE_DISTANCE])
        here = self.star_position()
        self.quote_asked = {"system": system, "radius": radius,
                            "at": time.time(), "wanted": list(wanted)}
        for index, name in enumerate(wanted):
            self.after(index * QUOTE_GAP_MS,
                       lambda n=name: community.sell(
                           commodity=n, near_system=system, limit=20,
                           near=here, within_ly=radius, tag=QUOTE_TAG))
        return len(wanted), ""

    def take_quote(self, ok, message):
        """File one answer from quote_hold, and show it wherever it is shown."""
        asked = attr(self, "quote_asked") or {}
        quotes = self.__dict__.setdefault("sell_quotes", {})
        if ok:
            try:
                commodity, best, here = read_quote(message,
                                                   asked.get("system", ""))
            except (TypeError, ValueError, AttributeError):
                commodity = ""
            if commodity:
                self.__dict__["quote_problem"] = ""
                quotes[SV.fold(commodity)] = {
                    "commodity": commodity, "best": best, "here": here,
                    "system": asked.get("system", ""),
                    "radius": asked.get("radius", 0), "at": time.time()}
        else:
            self.__dict__["quote_problem"] = str(message or "")
        ledger = attr(self, "ledger")
        try:
            if ledger is not None and ledger.winfo_exists():
                ledger.show_quotes()
        except Exception:
            self.ledger = None
        self.update_earnings()

    def fresh_quotes(self):
        """The quotes still good for where the commander is now."""
        system = SV.fold(getattr(attr(self, "watcher"), "system", "") or "")
        now = time.time()
        return {key: quote for key, quote in
                dict(attr(self, "sell_quotes") or {}).items()
                if SV.fold(quote.get("system")) == system
                and now - quote.get("at", 0) < QUOTE_FRESH_S}

    def best_nearby(self, cargo):
        """(credits, radius, priced, aboard) at the best price found for each.

        Only what has a quote is added up, and the count of those beside the
        count aboard says so - a total that quietly leaves out half the hold
        is not "up to" anything.
        """
        quotes = self.fresh_quotes()
        if not cargo or not quotes:
            return 0, 0, 0, len(cargo or {})
        total, radius, priced = 0, 0, 0
        for name, count in cargo.items():
            quote = quotes.get(SV.fold(name))
            if quote is None or not quote.get("best"):
                continue
            total += quote["best"]["sell"] * int(count)
            radius = max(radius, int(quote.get("radius") or 0))
            priced += 1
        return total, radius, priced, len(cargo)

    def credit_refined(self, note):
        """One refined tonne, put against the marked deposit it came off.

        Only in the SRV, only with a position - a tonne refined in a ring
        from the ship is not off any deposit here - and only on the
        commander's own marked deposits. Held until save_refined writes it.
        """
        if not note.get("in_srv") or note.get("lat") is None:
            return None
        system, body = note.get("system"), note.get("body")
        if not (system and body):
            system, body = self.here()
        try:
            row = self.store.credit_refined(
                system, body, note.get("lat"),
                note.get("lon"), note.get("radius_m"), note.get("commodity"))
        except Exception as exc:
            self.trouble("Refined tonne", exc)
            return None
        if row is not None:
            self._refined_dirty = True
            self._refined_at = attr(self, "_refined_at", 0.0) or time.time()
            self._tonnes_changed = (str(row.get("id")), time.time())
        return row

    def show_tonnes(self, now=None):
        """Put new tonnes on the screen once the laser has paused.

        Not a redraw per tonne: the details and the deposit list are
        rewritten once no tonne has come in for TONNES_QUIET_S - a few
        seconds after you stop, which is when you look."""
        changed = attr(self, "_tonnes_changed", None)
        if not changed:
            return False
        if (now or time.time()) - changed[1] < TONNES_QUIET_S:
            return False
        self._tonnes_changed = None
        chosen = attr(self, "selected", None)
        try:
            if chosen and str(chosen.get("id")) == changed[0]:
                self.on_pick(chosen)
            self.refresh_deposits()
        except Exception as exc:
            self.trouble("Showing tonnes mined", exc)
        return True

    def save_refined(self, force=False):
        """Write tonnes counted since the last write - every few seconds
        while mining, not once a tonne, and always on the way out."""
        if not attr(self, "_refined_dirty", False):
            return
        if not force and time.time() - (attr(self, "_refined_at", 0.0) or 0.0) < REFINED_SAVE_S:
            return
        try:
            self.store.save_deposits()
            self._refined_dirty = False
            self._refined_at = 0.0
        except Exception as exc:
            self.trouble("Saving refined tonnes", exc)

    def earnings_note(self, line):
        """Say what the books just did, when it is worth interrupting for.

        Not the mining. Cargo.json changes every few seconds while the
        laser is on, so "mined Olivine:4" on the status line would wipe the
        confirmation from the F10 pressed a second earlier - and that line
        is the only proof the deposit was recorded at all. What came out of
        the ground is on the strip above, live, the whole time.
        """
        if line and not str(line).startswith("mined"):
            self.say(str(line), GREEN)
        if line and str(line).startswith("to ship"):
            self.flash_ship_hold(str(line)[len("to ship:"):].strip())

    def ship_hold(self):
        """(tonnes in the ship, its capacity or None) from the reader."""
        watcher = attr(self, "watcher")
        holds = dict(getattr(watcher, "holds", None) or {})
        ship = dict(holds.get("Ship") or {})
        tonnes = sum(int(count) for count in ship.values() if count)
        return tonnes, getattr(watcher, "cargo_capacity", None)

    def flash_ship_hold(self, moved=""):
        """After every transfer from the Rhino: what is in the ship now.

        The question a transfer raises is "is the ship full yet", and it
        used to take a trip to the ship's panel to answer it."""
        tonnes, capacity = self.ship_hold()
        title = "SHIP %d%s t" % (tonnes, "/%d" % capacity if capacity else "")
        room = ""
        if capacity:
            left = max(0, capacity - tonnes)
            room = "  FULL" if left <= 0 else "  %d t room" % left
        return self.flash(title + room, ("moved " + moved) if moved else "",
                          AMBER if capacity and tonnes >= capacity else GREEN)

    def _autofill(self, key, value):
        """Put what the game just named into a box, without taking it over.

        The box only follows the scanner while it is still showing the
        scanner's own last answer. Prospect Magnesite, drive to the next
        deposit and prospect Olivine, and the box has to move with you:
        the old rule was "fill it only if it is empty", so after the first
        reading of a session the scanner never touched it again and F10
        filed every deposit after that under the first commodity - into
        the community database, with nothing on screen saying so.

        Anything the commander typed themselves is theirs and is left
        exactly where it is.
        """
        box = self.fields[key]
        current = box.get().strip()
        if current and current != attr(self, "_autofilled", {}).get(key):
            return False
        box.set(value)
        # attr() rather than getattr(): on a Tk widget a name that was
        # never assigned comes back as something truthy from the option
        # machinery, so the dict has to be asked for directly.
        filled = attr(self, "_autofilled")
        if not isinstance(filled, dict):
            filled = self._autofilled = {}
        filled[key] = value
        return True

    def follow_body(self):
        """Re-read the disk when the body under us changes.

        Called whether or not the game is running: "which body are we on"
        has a perfectly good answer with Elite shut, and it is the one in
        settings.

        The planet class counts as a change too. It arrives on the Scan,
        which is very often AFTER the body is already known - you drop in,
        land, and the scan lands whenever it lands. The commodity list is
        ordered by what the world can actually hold, so until this was
        watched as well, an icy body kept offering the rocky order all
        session and Low Temperature Diamonds sat forty rows down.
        """
        system, body = self.here()
        world = self.planet_class()
        moved = (system, body) != self._known_body
        if not moved and world == attr(self, "_known_world"):
            return False
        self._known_body = (system, body)
        self._known_world = world
        if moved:
            self.remember_body(system, body)
            self.refresh_locations()
            self.refresh_deposits()
        self.refresh_commodities()
        return True

    def show_records(self):
        """Put every view in step with what is on disk, game or no game.

        _build() left all four empty and the only code that filled them was
        past an early return a shut game never reached, so a cold start with
        Elite closed drew an empty window over a full database.
        """
        self._known_body = self.here()
        self._known_world = self.planet_class()
        self.refresh_locations()
        self.refresh_deposits()
        self.refresh_commodities()
        self.redraw()

    # -- the map ---------------------------------------------------------

    def redraw(self):
        state = self.game
        system, body = self.here()
        live = state is not None and state.has_position and bool(system and body)

        if live:
            radius = state.radius_m or 1e6
            centre = (state.lat, state.lon)
            heading = state.heading or 0.0
            caption = "%s   signal %s" % (body, self.signal())
            world = state.body_profile()
            extra = [bit for bit in (world["planet_class"],
                                     "%sg" % world["gravity"] if world["gravity"] else "",
                                     "%sK" % int(float(world["temperature_k"]))
                                     if world["temperature_k"] else "",
                                     world["volcanism"]) if bit]
            if extra:
                caption += "   " + "  ".join(extra)
        else:
            # Not in an SRV, or the game is shut. Draw the body from its own
            # deposits instead of drawing nothing, so a find can still be
            # found and corrected.
            centre = self.centre_of_record(system, body)
            if centre is None:
                self.plan.show([], caption="waiting for a surface position")
                self.draw_overlay([], 0.0)
                self.refresh_location_note()
                return
            radius = 1e6
            heading = 0.0
            caption = "%s   signal %s   (not in an SRV - showing what is " \
                      "recorded here)" % (body, self.signal())

        rows = self.store.near(system, body, centre[0], centre[1], radius)
        # Everyone else's finds on this body, alongside yours. The map and
        # the overlay used to draw only your own, so a patch somebody else
        # had mapped was invisible until you went looking for it under Find.
        rows = rows + self.shared_near(system, body, centre, radius, rows)
        if live:
            self.want_shared(system, body)
        if live:
            self.track_survey(state)
        rigs = self.watch_rigs(state) if live else None
        survey = self.survey_view(system, body, centre, radius)
        self.plan.show(rows, heading=heading, caption=caption, survey=survey,
                       rigs=rigs, signal=self.signal(),
                       anchor=self.site_offset(system, body, self.signal(),
                                               centre, radius),
                       place=(system, body, self.signal()))
        self.draw_overlay(rows if live else [], heading,
                          centre=centre if live else None,
                          radius_m=radius if live else None,
                          survey=survey if live else None,
                          rigs=rigs)
        self.refresh_location_note()

    def centre_of_record(self, system, body):
        """The middle of what is recorded on this body, or None if nothing is.

        Only used when there is no live position: the map has to be centred
        on something, and the deposits themselves are the only thing left.
        The signal being worked comes first - where it was logged, else its
        own finds - because the middle of every find on a body can be a
        spot thousands of kilometres from all of them.
        """
        if not (system and body):
            return None
        logged = self.store.location(system, body, self.signal())
        try:
            return float(logged["lat"]), float(logged["lon"])
        except (TypeError, ValueError, KeyError):
            pass
        points, signal_points = [], []
        wanted = self.signal()
        for deposit in self.store.at(system, body):
            try:
                point = (float(deposit["lat"]), float(deposit["lon"]))
            except (TypeError, ValueError, KeyError):
                continue
            points.append(point)
            if str(deposit.get("location") or "").strip() == wanted:
                signal_points.append(point)
        points = signal_points or points
        if not points:
            return None
        return (sum(p[0] for p in points) / len(points),
                sum(p[1] for p in points) / len(points))

    def refresh_commodities(self, typed=None):
        """What to offer in the commodity box, in a useful order.

        Three tiers. What this body's own signals said might be here comes
        first, because that is nearly always the answer. Everything else
        follows in rough order of worth, so the stuff worth driving to is
        near the top. Anything typed filters the lot.
        """
        system, body = self.here()
        offered = []
        for row in self.store.locations_on(system, body):
            for name in self.store.offered(row):
                if name not in offered:
                    offered.append(name)
        # What has actually been dug up here counts as much as what the game
        # said would be. A signal can list Magnesite and then hand you
        # Periclase dunite, Samarium and Copper - and if the box only ever
        # knows the game's list, the thing you are standing on is buried
        # under forty commodities nobody has seen on this body.
        for deposit in self.store.at(system, body):
            name = (deposit.get("commodity") or "").strip()
            if name and name not in offered:
                offered.append(name)
        offered = SV.by_value(offered, self.prices)

        # What the rest of the list even CAN be depends on the body. Water
        # and Methanol Crystals only come off ice; Iridium and Gold never do.
        # Sorting forty commodities by price and showing the same order on
        # every world puts things at the top that cannot be underneath you.
        others = [c for c in SV.KNOWN_COMMODITIES if c not in offered]
        possible, elsewhere = SV.for_body(others, self.planet_class())
        names = (offered
                 + SV.by_value(possible, self.prices)
                 + SV.by_value(elsewhere, self.prices))
        if typed:
            names = SV.matches(names, typed)
        self.fields["commodity"].configure(values=names or ["(no match)"])
        return names

    def planet_class(self):
        """The journal's PlanetClass for the body under us, if it said."""
        # body_facts is {body_name: {...}}, so .get("planet_class") on it
        # was always None and the commodity list was never once ordered by
        # the world you are standing on. body_profile() is the accessor
        # that resolves the current body, and mark_deposit two methods
        # away already used it.
        state = self.game
        if state is not None:
            try:
                found = (state.body_profile() or {}).get("planet_class")
            except Exception:
                found = None
            if found:
                return found
        system, body = self.here()
        for row in reversed(self.store.at(system, body)):
            if row.get("planet_class"):
                return row["planet_class"]
        return ""

    def commodity_typed(self, _event=None):
        """Narrow the list as they type, without stealing what they typed."""
        try:
            typed = self.fields["commodity"].get()
        except Exception:
            return
        self.refresh_commodities(typed)

    def signal_choices(self):
        """How many signals to offer on this body.

        The DSS already counted them, so use that. Anything already logged
        here counts too, in case the count arrived after the signals did.
        """
        highest = MAX_LOCATIONS
        state = self.game
        if state is not None:
            try:
                highest = max(highest, int(state.mining_signals() or 0))
            except (TypeError, ValueError):
                pass
        system, body = self.here()
        if system and body:
            for row in self.store.locations_on(system, body):
                try:
                    highest = max(highest, int(float(row.get("location") or 0)))
                except (TypeError, ValueError):
                    continue
        return [str(n) for n in range(1, highest + 1)]

    def refresh_signal_box(self):
        """Keep the picker's list long enough, without losing the selection."""
        chosen = self.location_box.get()
        self.location_box.configure(values=self.signal_choices())
        if chosen:
            self.location_box.set(chosen)

    def refresh_locations(self):
        self.refresh_signal_box()
        for widget in self.location_box_list.winfo_children():
            widget.destroy()
        system, body = self.here()
        if not (system and body):
            ctk.CTkLabel(self.location_box_list, text="Waiting for a body.",
                         font=F_SMALL, text_color=DIM).pack(pady=8)
            return
        rows = self.store.locations_on(system, body)
        if not rows:
            ctk.CTkLabel(self.location_box_list,
                         text="No signals logged on this body yet.\n"
                              "Drive into one and press %s."
                              % self.key("location", "LOG SIGNAL"),
                         font=F_SMALL, text_color=DIM,
                         justify="left").pack(pady=8, padx=6, anchor="w")
            return
        for row in rows:
            number = row["location"]
            found = len(self.store.at(system, body, number))
            offered = self.store.offered(row)
            live = number == self.signal()

            # "4 found  1 offered" meant nothing to anybody. Two different
            # numbers, neither labelled: one is what you have marked, the
            # other is what the game said might be in there. Say both in
            # words, and name the commodities rather than counting them -
            # the names are what you actually want to see.
            marked = "%d deposit%s" % (found, "" if found == 1 else "s")
            if not found:
                marked = "nothing marked yet"
            if offered:
                listed = ", ".join(offered[:3])
                if len(offered) > 3:
                    listed += " +%d" % (len(offered) - 3)
            else:
                listed = "no list recorded"
            text = "Signal %s   %s   %s" % (number, marked, listed)

            line = ctk.CTkFrame(self.location_box_list, fg_color="transparent")
            line.pack(fill="x", pady=1)
            # THE EDIT BUTTON IS PACKED FIRST, AND TO THE RIGHT.
            #
            # Packed after the label it vanished on any row whose text was
            # long - "Signal 2  nothing marked yet  no list recorded" is
            # wider than "Signal 3  4 deposits  Magnesite", and an expanding
            # sibling packed before it simply pushed it off the edge. So the
            # rows that most needed an edit button - the empty ones logged by
            # mistake - were the only rows that did not have one.
            #
            # Tk gives space to fixed-width widgets first when they are
            # packed first. The label takes what is left.
            ctk.CTkButton(
                line, text="edit", width=48, height=28, font=F_SMALL,
                **BTN_GHOST,
                command=lambda r=row: self.edit_location(r)
            ).pack(side="right", padx=(4, 0))
            ctk.CTkButton(
                line, text=text, anchor="w", height=28, font=F_SMALL,
                **(BTN_PRIMARY if live else BTN_ROW),
                command=lambda n=number: self.choose_signal(n)
            ).pack(side="left", fill="x", expand=True)

    def edit_location(self, row):
        """Correct or remove a mining location signal."""
        try:
            EditLocationWindow(self, row)
        except Exception as exc:
            self.say("Could not open that signal: %s" % exc, RED)

    def refresh_deposits(self):
        """Everything marked inside the signal that is selected."""
        box = self.deposit_list
        if box is None:
            return
        for widget in box.winfo_children():
            widget.destroy()
        system, body = self.here()
        signal = self.signal()
        rows = self.store.at(system, body, signal) if system and body else []
        strays = self.stray_deposits(system, body, signal)
        header = self.deposit_header
        if header is not None:
            header.configure(text="SIGNAL %s  (%d)" % (signal, len(rows)))
        if not rows:
            ctk.CTkLabel(box, text="Nothing marked in signal %s yet.\n"
                                   "Drive to a scanner ping and press %s."
                              % (signal, self.key("deposit", "MARK DEPOSIT")),
                         font=F_SMALL, text_color=DIM,
                         justify="left").pack(pady=8, padx=6, anchor="w")
            self._show_strays(box, strays, signal)
            return
        chosen = (self.selected or {}).get("id")
        for row in rows:
            bits = [row.get("commodity") or "unnamed"]
            if row.get("rigs"):
                bits.append("%sR" % row["rigs"])
            if row.get("amount"):
                bits.append(row["amount"])
            mined, _others = SV.own_tonnes(row)
            if mined:
                bits.append("%dt mined" % mined)
            if SV.is_depleted(row.get("amount")):
                bits.append("mined out")
            live = row.get("id") == chosen

            line = ctk.CTkFrame(box, fg_color="transparent")
            line.pack(fill="x", pady=1)
            # Fixed-width button packed FIRST, so a long label cannot push it
            # off the edge - the same trap the signal rows fell into.
            ctk.CTkButton(
                line, text="edit", width=48, height=28, font=F_SMALL,
                **BTN_GHOST,
                command=lambda r=row: self.edit_deposit(r)
            ).pack(side="right", padx=(4, 0))
            ctk.CTkButton(
                line, text="  ".join(bits), anchor="w", height=28,
                font=F_SMALL,
                **(BTN_PRIMARY if live else BTN_ROW),
                command=lambda r=row: self.pick_deposit(r)
            ).pack(side="left", fill="x", expand=True)
        self._show_strays(box, strays, signal)

    def stray_deposits(self, system, body, signal):
        """Finds right here, filed under some other signal's number.

        A number picked wrong in the box files a deposit away from the
        signal it is actually in, and the list for that signal - the one
        you come back to - never showed it. Anything of yours within
        SIGNAL_AT_M of this signal's centre (or of you, before it has one),
        whatever number it carries, is listed under it with a button to put
        the number right."""
        if not (system and body):
            return []
        logged = self.store.location(system, body, signal)
        centre = None
        try:
            centre = (float(logged["lat"]), float(logged["lon"]))
        except (TypeError, ValueError, KeyError):
            state = attr(self, "game")
            if state is not None and getattr(state, "has_position", False):
                centre = (state.lat, state.lon)
        if centre is None:
            return []
        state = attr(self, "game")
        radius = getattr(state, "radius_m", None) or 1e6
        out = []
        for deposit in self.store.at(system, body):
            if str(deposit.get("location") or "").strip() == str(signal).strip():
                continue
            try:
                apart = SV.surface_range_m(centre[0], centre[1],
                                           float(deposit["lat"]),
                                           float(deposit["lon"]), radius)
            except (KeyError, TypeError, ValueError):
                continue
            if apart <= PV.SIGNAL_AT_M:
                out.append(deposit)
        return out

    def _show_strays(self, box, strays, signal):
        if not strays:
            return
        ctk.CTkLabel(box, text="Here, but filed under another signal number:",
                     font=F_SMALL_B, text_color=AMBER, anchor="w",
                     justify="left").pack(fill="x", padx=6, pady=(8, 2))
        for row in strays:
            line = ctk.CTkFrame(box, fg_color="transparent")
            line.pack(fill="x", pady=1)
            ctk.CTkButton(
                line, text="file under %s" % signal, width=110, height=28,
                font=F_SMALL, **BTN_SECONDARY,
                command=lambda r=row: self.refile_deposit(r, signal)
            ).pack(side="right", padx=(4, 0))
            ctk.CTkButton(
                line, text="%s  (signal %s)" % (row.get("commodity") or "unnamed",
                                                row.get("location") or "-"),
                anchor="w", height=28, font=F_SMALL, **BTN_ROW,
                command=lambda r=row: self.pick_deposit(r)
            ).pack(side="left", fill="x", expand=True)

    def refile_deposit(self, row, signal):
        """Put a find under the signal it is actually in."""
        was = str(row.get("location") or "-")
        changes = {"location": str(signal),
                   "notes": SV.stamp_note(row.get("notes"),
                                          "Refiled from signal %s" % was)}
        done = self.deposit_edited(row["id"], changes)
        if done is None:
            return self.say("Could not refile that find.", RED)
        self.refresh_deposits()
        self.redraw()
        return self.say("%s moved from signal %s to signal %s."
                        % (row.get("commodity") or "The find", was, signal),
                        GREEN)

    def pick_deposit(self, row, guide=True):
        """Select it, so the map and the detail panel follow the list.

        Picked by hand, it is also where the overlay guides you: NEXT on the
        scope and STATUS becomes GO to this one, until you get there."""
        self.selected = row
        if guide:
            self.guide_to(row)
        plan = attr(self, "plan", None)
        if plan is not None and row:
            plan.selected_id = row.get("id")
        self.on_pick(row)
        self.refresh_deposits()
        self.redraw()

    def picked_on_map(self, deposit):
        """A click on the map: select it, and guide to it."""
        self.guide_to(deposit)
        self.on_pick(deposit)

    def guide_to(self, deposit):
        """The deposit the overlay points you at, or nothing for nearest."""
        self._guide_to = str(deposit.get("id")) if deposit and deposit.get("id") else None

    def follow_deposit(self, state):
        """Pick the deposit of yours you have driven onto, once per arrival.

        In the SRV, standing on a deposit you marked selects it, so MINED
        OUT, UPDATE, Edit and Copy to share act on it with one click, and
        the map rings it. Arriving at the one the overlay was guiding you to
        ends the guiding. A deposit picked by hand while you stand there is
        left alone until you drive onto another.
        """
        if not (getattr(state, "has_position", False) and getattr(state, "in_srv", False)):
            return
        found = self.own_deposit_here("")
        at = str(found[0].get("id")) if found else None
        if at == attr(self, "_on_deposit", None):
            return
        self._on_deposit = at
        if found is None:
            return
        deposit, metres = found
        if at == attr(self, "_guide_to", None):
            self._guide_to = None
        chosen = attr(self, "selected", None)
        if chosen and str(chosen.get("id")) == at:
            return
        try:
            self.pick_deposit(deposit, guide=False)
            self.say("On your %s deposit, %s away - picked, so MINED OUT and "
                     "UPDATE act on it." % (deposit.get("commodity") or "unnamed",
                                             _metres(metres)), CYAN)
        except Exception as exc:
            self.trouble("Deposit you are on", exc)

    def follow_target(self, state):
        """Pick the signal the game has targeted, once each time it changes.

        Only on a change: a commander who then picks another number by hand
        has the last word until the game targets something new.
        """
        target = str(getattr(state, "target_signal", "") or "").strip()
        if not target or target == attr(self, "_target_applied", ""):
            return
        self._target_applied = target
        if target != str(self.signal()).strip():
            try:
                self.choose_signal(target)
                self.say("Signal %s targeted in the game - picked here too."
                         % target, CYAN)
            except Exception as exc:
                self.trouble("Signal from the game", exc)

    def follow_arrival(self, state):
        """Pick the logged signal you have driven into, once per arrival.

        The box used to keep whatever it said last, so arriving at signal 5
        with it still on 1 had the scope zoomed out to hold signal 1 forty
        kilometres back - and a deposit marked there was filed under 1.
        Only on arriving somewhere new: a number picked by hand while you
        stand there is left alone until you drive into another signal.
        """
        if not getattr(state, "has_position", False) or not state.radius_m:
            return
        system, body = self.here()
        if not (system and body):
            return
        row = SV.nearest_signal(self.store.locations_on(system, body),
                                state.lat, state.lon, state.radius_m,
                                PV.SIGNAL_AT_M)
        at = (system, body, str(row["location"]).strip()) if row else None
        if at == attr(self, "_arrived_at", None):
            return
        self._arrived_at = at
        if at is None or at[2] == str(self.signal()).strip():
            return
        # Two logged signals close together: while the one in the box is
        # also one you are standing in, it stays - its finds are filed
        # under it, and flipping at an invisible line would split them.
        current = self.store.location(system, body, self.signal())
        if current is not None and SV.nearest_signal(
                [current], state.lat, state.lon, state.radius_m,
                PV.SIGNAL_AT_M) is not None:
            return
        try:
            self.choose_signal(at[2])
            self.say("You are at signal %s - picked it for you." % at[2], CYAN)
        except Exception as exc:
            self.trouble("Signal you are at", exc)

    def choose_signal(self, number):
        self._signal_picked = True
        self.location_box.set(number)
        self.refresh_locations()
        self.refresh_deposits()
        self.redraw()

    def refresh_location_note(self):
        system, body = self.here()
        row = self.store.location(system, body, self.signal())
        if row is None:
            self.location_note.configure(
                text="Signal %s not logged yet. Drive into it and press %s - "
                     "it logs the signal and sets the centre. No commodities "
                     "needed." % (self.signal(),
                                  self.key("location", "LOG SIGNAL")),
                text_color=DIM)
            return
        offered = self.store.offered(row)
        gone = set(self.store.worked_out(row))
        if not offered:
            self.location_note.configure(
                text="Signal %s logged. What it holds fills in as you mark "
                     "its deposits." % self.signal(), text_color=DIM)
            return
        parts = []
        for name in offered:
            parts.append(name + (" (depleted)" if name in gone else ""))
        text = "Offers: " + ", ".join(parts)

        summary = self.signal_state(system, body, self.signal())
        if summary:
            text += "\n" + summary
        self.location_note.configure(text=text, text_color=TEXT)

    def signal_state(self, system, body, signal):
        """How much is left in this signal, in one line.

        The offers list says what the game claimed was here. This says what
        is actually left according to what has been marked - which is the
        question you are asking when you look at it a second time.
        """
        rows = self.store.at(system, body, signal)
        if not rows:
            return ""
        ranks = [SV.amount_rank(r.get("amount")) for r in rows]
        known = [r for r in ranks if r >= 0]
        worked = sum(1 for r in rows if SV.is_depleted(r.get("amount")))
        bits = ["%d marked" % len(rows)]
        if worked:
            bits.append("%d worked out" % worked)
        if known:
            average = sum(known) / float(len(known))
            tier = SV.AMOUNT_TIERS[min(len(SV.AMOUNT_TIERS) - 1,
                                       int(round(average)))]
            bits.append("mostly %s" % tier.lower())
        elif not worked:
            bits.append("amounts not recorded")
        return "  -  ".join(bits)

    # -- recording -------------------------------------------------------

    def mark_deposit(self):
        """One key. Where you are, what the scanner said, done."""
        state = self.game
        if not (state and state.has_position):
            self.say("No surface position from the game yet.", AMBER)
            return
        system, body = self.here()
        # Remember it here as well as in the telemetry: the body you last
        # recorded something on is the one you will want back when you sit
        # down later to correct it.
        self.remember_body(system, body)
        commodity = (self.fields["commodity"].get().strip()
                     or state.detected_type or "")
        if not commodity:
            self.say("Which commodity? Pick one on the left, then press %s again."
                     % self.key("deposit", "MARK DEPOSIT"), AMBER)
            self.flash("NOT MARKED - NO COMMODITY",
                       "fill in all four boxes first", AMBER)
            return
        # Marking the one you are standing on a second time is nearly always
        # meant as an update. Ask once; a second press within a few seconds
        # means it really is a separate deposit.
        same = self.own_deposit_here(commodity)
        armed = attr(self, "_mark_armed", None)
        if same is not None and not (armed and armed[0] == same[0]["id"]
                                     and time.time() - armed[1] < 6):
            self._mark_armed = (same[0]["id"], time.time())
            return self.say("You already marked %s %s from here. Press UPDATE "
                            "to change it, or MARK again to add a separate "
                            "deposit." % (same[0].get("commodity") or "a deposit",
                                          _metres(same[1])), AMBER)

        # Another commodity already marked on this very spot is far more
        # often the same rock with the wrong name than a second deposit: the
        # box said Monazite, it was Alexandrite, the box was changed and the
        # key pressed again - and that made a second find at 0 m. So it
        # asks, once, with both answers on one key each: UPDATE renames the
        # one already there (position, history and tonnes kept), MARK again
        # adds a deposit of its own - a patch can hold two.
        other = self.own_deposit_here("")
        retype = attr(self, "_retype_armed", None)
        if other is not None and other[1] <= RETYPE_M and \
                SV.fold(other[0].get("commodity")) != SV.fold(commodity):
            again = (retype and retype[0] == other[0]["id"]
                     and retype[1] == SV.fold(commodity)
                     and time.time() - retype[2] < 6)
            if not again:
                self._retype_armed = (other[0]["id"], SV.fold(commodity),
                                      time.time(), commodity)
                was = other[0].get("commodity") or "a deposit"
                self.flash("%s IS MARKED HERE" % str(was).upper()[:18],
                           "%s renames it %s   %s again adds %s" % (
                               self.key("update", "UPDATE"), commodity[:14],
                               self.key("deposit", "MARK"), commodity[:14]),
                           AMBER)
                return self.say(
                    "%s is marked %s from here. Press %s to rename it %s, or "
                    "%s again to add %s as a deposit of its own."
                    % (was, _metres(other[1]), self.key("update", "UPDATE"),
                       commodity, self.key("deposit", "MARK DEPOSIT"),
                       commodity), AMBER)

        # Every deposit carries all four: what it is, how many rigs, how much
        # is left and how dense it is. Half-filled finds went out to the
        # shared map without their Amount and Density - the two things a
        # commander deciding whether to fly there needs most - so a deposit
        # is not marked until the boxes are full. The scanner's density
        # counts when the game gave one. Asked after "already marked here"
        # and "rename it?", which need nothing filled in to answer.
        missing = self.missing_fields(state)
        if missing:
            self.say("Not marked - fill in %s first. Every deposit needs its "
                     "commodity, rigs, amount and density, so the shared map "
                     "can be trusted. Then press %s again." % (
                         _join_words(missing),
                         self.key("deposit", "MARK DEPOSIT")), AMBER)
            self.flash("NOT MARKED - FILL IN %s" % " + ".join(
                           word.upper() for word in missing),
                       "all four boxes, then %s" % self.key("deposit", "MARK"),
                       AMBER)
            return

        self._mark_armed = None
        self._retype_armed = None

        world = state.body_profile()
        record = self.store.add_deposit(
            system=system, body=body, location=self.signal(),
            commodity=commodity,
            rigs=self.fields["rigs"].get().strip(),
            density=(self.fields["density"].get().strip()
                     or state.detected_density or ""),
            amount=self.fields["amount"].get().strip(),
            lat="%.6f" % state.lat, lon="%.6f" % state.lon,
            temperature_k="" if state.body_temperature() is None
                          else "%.1f" % state.body_temperature(),
            planet_class=world["planet_class"],
            gravity=world["gravity"],
            atmosphere=world["atmosphere"],
            volcanism=world["volcanism"],
            status=SV.STATUS_REPORTED,
            cmdr=state.cmdr or "")

        # a signal row so the body remembers this one exists, even if F9 was
        # never pressed
        if self.store.location(system, body, self.signal()) is None:
            self.store.set_location(system, body, self.signal(),
                                    lat=state.lat, lon=state.lon,
                                    radius_m=state.radius_m or 1e6,
                                    temperature_k=state.body_temperature(),
                                    planet_class=world["planet_class"],
                                    gravity=world["gravity"],
                                    atmosphere=world["atmosphere"],
                                    volcanism=world["volcanism"],
                                    cmdr=state.cmdr or "")
        self.refresh_locations()
        self.refresh_deposits()
        self.refresh_commodities()
        self.redraw()
        self.share(record)
        rigs = record["rigs"]
        # The next deposit is another rock: its rigs, amount and density are
        # read off it, not carried over from this one - carried-over boxes
        # are how a Low Amount went out as the High of the deposit before.
        self.clear_deposit_boxes()
        self.say("Marked %s%s at %.5f, %.5f. Rigs, amount and density cleared "
                 "for the next deposit."
                 % (record["commodity"],
                    " (%s rigs)" % rigs if rigs else "",
                    state.lat, state.lon), GREEN)
        self.flash("MARKED  %s" % str(record["commodity"]).upper()[:24],
                   "  ".join(bit for bit in (
                       "%s rigs" % rigs if rigs else "",
                       str(record.get("amount") or ""),
                       "signal %s" % record.get("location")
                       if record.get("location") else "") if bit))

    def clear_deposit_boxes(self):
        """Empty Rigs, Amount and Density - not the commodity, which the
        scanner keeps filling in as you drive."""
        fields = attr(self, "fields", None) or {}
        for name in ("rigs", "amount", "density"):
            try:
                fields[name].set("")
            except Exception:
                pass
        filled = attr(self, "_autofilled")
        if isinstance(filled, dict):
            filled.pop("density", None)

    def missing_fields(self, state=None):
        """Which of Rigs, Amount and Density are still blank for MARK -
        in the order the boxes are read. Rigs must be 1 to MAX_RIGS."""
        fields = attr(self, "fields", None) or {}
        state = state if state is not None else attr(self, "game")

        def box(name):
            try:
                return str(fields[name].get() or "").strip()
            except Exception:
                return ""
        missing = []
        rigs = box("rigs")
        try:
            if not 1 <= int(float(rigs)) <= MAX_RIGS:
                missing.append("rigs")
        except (TypeError, ValueError):
            missing.append("rigs")
        if not box("amount"):
            missing.append("amount")
        if not (box("density") or getattr(state, "detected_density", "")):
            missing.append("density")
        return missing

    # -- the rigs -------------------------------------------------------------

    def rig_limit(self):
        """How far from a rig before the warning, in metres. 0 is off."""
        try:
            return max(0.0, float(self.settings.get("rig_warn_m") or 0))
        except (TypeError, ValueError):
            return 0.0

    def rigs_hint(self):
        limit = self.rig_limit()
        if not limit:
            return "Rigs: press RIG DOWN as each goes down. Warning off."
        return ("Rigs: press RIG DOWN as each goes down. Warned past %s."
                % _metres(limit))

    def _rigs_here(self):
        """The rigs down on the body you are on, or an empty list."""
        rigs = attr(self, "rigs_at", None)
        if not rigs:
            return []
        system, body = self.here()
        if (str(system).lower(), str(body).lower()) != \
                (str(rigs["system"]).lower(), str(rigs["body"]).lower()):
            return []
        return list(rigs["rigs"])

    def drop_rigs(self, n=None):
        """A rig down, where the SRV is standing now.

        With a number - Alt+4 is rig 1, Alt+9 rig 6 - that rig. A rig already
        down somewhere else under that number was picked up without its key
        being pressed, so it moves here rather than being refused. Without a
        number, the next free one: the RIG DOWN button, and a spare key for
        anyone who would rather press one key six times. A second press on
        the same spot is a double press, not a second rig.
        """
        state = self.game
        system, body = self.here()
        if not (state is not None and state.has_position and system and body):
            return self.say("No surface position from the game yet - press "
                            "a rig key from the SRV as you drop each rig.", AMBER)
        rigs = self._rigs_here()
        if not rigs:
            self.rigs_at = {"system": system, "body": body, "rigs": []}
        radius = state.radius_m or 0

        def metres_to(rig):
            if not radius:
                return None
            return SV.surface_range_m(state.lat, state.lon, rig["lat"],
                                      rig["lon"], radius)

        moved_from = None
        if n is not None:
            try:
                n = int(n)
            except (TypeError, ValueError):
                n = 0
            if not 1 <= n <= MAX_RIGS:
                return self.say("There are %d rigs - no rig %s." % (MAX_RIGS, n),
                                AMBER)
            mine = next((rig for rig in rigs if rig["n"] == n), None)
            if mine is not None:
                away = metres_to(mine)
                if away is not None and away < RIG_SAME_M:
                    return self.say("Rig %d is already down here." % n, AMBER)
                moved_from = away
                self.rigs_at["rigs"] = [r for r in self.rigs_at["rigs"]
                                        if r["n"] != n]
        else:
            for rig in rigs:
                away = metres_to(rig)
                if away is not None and away < RIG_SAME_M:
                    return self.say("Rig %d is already marked here." % rig["n"],
                                    AMBER)
            taken = {rig["n"] for rig in rigs}
            free = [k for k in range(1, MAX_RIGS + 1) if k not in taken]
            if not free:
                return self.say("All %d rigs are marked. %s when you have "
                                "collected them." % (MAX_RIGS,
                                                     self.key("allup", "RIGS UP")),
                                AMBER)
            n = free[0]
        what = self.rig_commodity(state, system, body)
        rig = {"n": n, "lat": state.lat, "lon": state.lon, "at": time.time(),
               "commodity": what}
        self.rigs_at["rigs"].append(rig)
        self.rigs_at["rigs"].sort(key=lambda r: r["n"])
        self._rigs_warned = False
        try:
            # For the guide: rigs have gone down at this signal, which stays
            # true after they come back up.
            self.__dict__.setdefault("_guide_rigs", set()).add(
                (str(system).lower(), str(body).lower(), str(self.signal())))
        except Exception:
            pass
        self.rig_event("RigDown", n)
        self.refresh_rigs_note()
        self.redraw()
        limit = self.rig_limit()
        down = len(self.rigs_at["rigs"])
        self.flash("RIG %d %s%s" % (n, "MOVED" if moved_from is not None else "DOWN",
                                    ("  " + what.upper()) if what else ""),
                   "%d of %d  -  %s" % (down, MAX_RIGS,
                                        "warning past %s" % _metres(limit)
                                        if limit else "distance warning off"))
        if moved_from is not None:
            return self.say("Rig %d moved here%s - %s from where it was marked."
                            " %s picks a rig up." % (
                                n, (" on " + what) if what else "",
                                _metres(moved_from), self.key("rig%dup" % n,
                                                              "RIGS UP")), GREEN)
        pin = self.plan_pin_at(state.lat, state.lon)
        clash = self.wing_clash(state.lat, state.lon)
        if clash:
            self.flash("RIG %d DOWN - CLOSE TO %s" % (n, clash[0].upper()),
                       "%s from their rig %d" % (_metres(clash[2]), clash[1]),
                       AMBER)
        return self.say("Rig %d down%s%s (%d of %d). %s" % (
            n, (" on " + what) if what else "",
            (" at pin P%d" % pin) if pin else "", down, MAX_RIGS,
            "You will be warned past %s from any rig." % _metres(limit) if limit
            else "The distance warning is off in Settings."), GREEN)

    def rig_up(self, n):
        """One rig collected: stop watching it. The last one up is every
        rig up, with everything that goes with that."""
        try:
            n = int(n)
        except (TypeError, ValueError):
            return self.say("No such rig.", AMBER)
        rigs = self._rigs_here()
        if not any(rig["n"] == n for rig in rigs):
            return self.say("Rig %d is not marked down%s." % (
                n, " - no rigs are" if not rigs else ""), AMBER)
        self.rigs_at["rigs"] = [r for r in self.rigs_at["rigs"] if r["n"] != n]
        left = len(self.rigs_at["rigs"])
        if not left:
            return self.rigs_up(picked=n)
        # The warning was about whichever rig was farthest; that may have
        # been this one. The next poll works it out again from the rest.
        self._rigs_warned = False
        self._rigs_final = False
        self.clear_rig_alarm()
        self.refresh_rigs_note()
        self.redraw()
        self.flash("RIG %d UP" % n, "%d still down" % left)
        return self.say("Rig %d up. %d still down: %s." % (
            n, left, ", ".join(str(r["n"]) for r in self.rigs_at["rigs"])), GREEN)

    def rig_event(self, what, n=None):
        """A rig going down or the last one coming up, handed to the books:
        the first rig down starts an Earnings session, the last one up ends
        it. Never raises - the rig is marked whatever the books make of it."""
        try:
            system, body = self.here()
            line = self.earnings.observe({
                "event": what, "when": SV.utc_now(), "rig": n,
                "system": system, "body": body,
                "cmdr": getattr(attr(self, "watcher"), "cmdr", "") or ""})
            if line:
                self.earnings_note(line)
        except Exception:
            pass

    def trace_key(self):
        """The rig planner's key: start tracing a deposit's edge, or finish
        the trace. Beta - off unless switched on in Settings."""
        return self.planner_trace()

    # -- the rig planner (beta) -----------------------------------------------

    def planner_on(self):
        return bool(attr(self, "settings", {}).get("rig_planner"))

    def planner_spacing(self):
        """Metres between two rigs, from Settings, kept to something sane."""
        try:
            spacing = float(self.settings.get("rig_spacing_m")
                            or RP.RIG_SPACING_M)
        except (TypeError, ValueError):
            spacing = RP.RIG_SPACING_M
        return max(PLAN_SPACING_MIN_M, min(PLAN_SPACING_MAX_M, spacing))

    def planner_trace(self):
        """Start tracing the deposit's edge from where the Rhino is, or -
        pressed again while tracing - close the loop here and plan.

        The loop also closes itself when the Rhino comes back round to where
        it started, so most of the time the key is pressed once."""
        if not self.planner_on():
            return self.say("The rig planner is a beta and is off. Switch it "
                            "on in Settings, under Rigs.", AMBER)
        state = attr(self, "game")
        system, body = self.here()
        if not (state is not None and state.has_position and state.radius_m
                and system and body):
            return self.say("No surface position from the game yet - trace "
                            "the edge from the Rhino.", AMBER)
        trace = attr(self, "_trace", None)
        if trace is not None and not trace.closed:
            trace.add(state.lat, state.lon)
            if not trace.close():
                self._trace = None
                self.redraw()
                return self.say("Rig planner: not enough of an edge to plan "
                                "on - trace cancelled. Drive right round the "
                                "deposit's edge, then press it again.", AMBER)
            return self.finish_trace()
        self._trace = RP.Trace(state.lat, state.lon, state.radius_m)
        self._trace_where = (str(system).lower(), str(body).lower())
        self._trace_started = time.time()
        self.rig_plan = None
        key = self.key("trace", "the planner key")
        self.flash("TRACING THE EDGE", "drive round the deposit back to here")
        return self.say("Rig planner: tracing. Drive along the deposit's edge "
                        "and back to where you are now - it closes by itself "
                        "when you get here, or press %s to close it where you "
                        "are." % key, GREEN)

    def follow_trace(self, state):
        """Every new position from the game, while a trace is running. True
        when this one closed the loop and the pins are out."""
        trace = attr(self, "_trace", None)
        if trace is None or trace.closed:
            return False
        system, body = self.here()
        if (str(system).lower(), str(body).lower()) != attr(self, "_trace_where"):
            return self.cancel_trace("you left the body")
        if time.time() - float(attr(self, "_trace_started", 0) or 0) > \
                PLAN_TRACE_MAX_S:
            return self.cancel_trace("%d minutes without closing the loop"
                                     % (PLAN_TRACE_MAX_S // 60))
        if not (state is not None and state.has_position):
            return False
        closed = trace.add(state.lat, state.lon)
        if trace.too_big:
            return self.cancel_trace("that is %s from the start - bigger "
                                     "than any deposit" % _metres(RP.TRACE_MAX_SPAN_M))
        if closed:
            self.finish_trace()
            return True
        return False

    def cancel_trace(self, why):
        self._trace = None
        self.redraw()
        self.say("Rig planner: %s - trace cancelled." % why, AMBER)
        return False

    def finish_trace(self):
        """Plan the rigs for the loop just driven and put the pins out."""
        trace = attr(self, "_trace", None)
        if trace is None:
            return None
        self._trace = None
        state = attr(self, "game")
        start = (state.lat, state.lon) if (state is not None
                                          and state.has_position) else None
        spacing = self.planner_spacing()
        try:
            pins = trace.pins(spacing, start=start)
        except Exception as exc:
            self.trouble("Rig planner", exc)
            return self.say("Rig planner: could not work out the pins for "
                            "that shape.", AMBER)
        if not pins:
            return self.say("Rig planner: no room for a rig inside that "
                            "trace.", AMBER)
        system, body = attr(self, "_trace_where", ("", ""))
        self.rig_plan = {
            "system": system, "body": body, "spacing": spacing,
            "pins": [{"n": i + 1, "lat": lat, "lon": lon}
                     for i, (lat, lon) in enumerate(pins)],
            "outline": trace.outline(), "at": time.time(),
            "area_m2": RP.area(trace.points)}
        self.redraw()
        count = len(pins)
        self.flash("RIG PLAN  %d PIN%s" % (count, "" if count == 1 else "S"),
                   "%d m apart - drive to P1" % round(spacing))
        return self.say("Rig planner: %d rig%s fit %d m apart in what you "
                        "traced (about %s m2). The pins are on the scope in "
                        "driving order - drop a rig on each; the next one is "
                        "amber, done ones go green." % (
                            count, "" if count == 1 else "s", round(spacing),
                            "{:,}".format(int(round(RP.area(trace.points), -1)))),
                        GREEN)

    # -- the wing link (beta) -------------------------------------------------

    def wing_code(self):
        return clean_wing_code(attr(self, "settings", {}).get("wing_code"))

    def wing_on(self):
        return bool(attr(self, "settings", {}).get("wing_link")) and \
            bool(self.wing_code())

    def wing_member(self):
        """This install's slot in a wing: made up once, kept in settings,
        never shown - it is what stops somebody else beating as you."""
        member = str(self.settings.get("wing_member") or "")
        if not re.match(r"^[A-Za-z0-9]{8,32}$", member):
            member = secrets.token_hex(8)
            self.settings["wing_member"] = member
            save_settings(self.settings)
        return member

    def wing_tick(self, now=None):
        """Every WING_BEAT_S while the wing link is on, send where this
        commander is and their rigs; the answer is everybody else's. One
        beat in flight at a time. Switched off, it says goodbye once."""
        now = now or time.time()
        if not self.wing_on():
            if attr(self, "_wing_joined", ""):
                self.wing_leave()
            return False
        community = attr(self, "community")
        if community is None:
            return False
        sent = attr(self, "_wing_sent", 0.0) or 0.0
        if attr(self, "_wing_busy", False) and now - sent < 20.0:
            return False
        if now - sent < WING_BEAT_S:
            return False
        code = self.wing_code()
        joined = attr(self, "_wing_joined", "")
        if joined and joined != code:
            self.wing_leave()
        if not community.wing(code, self.wing_beat()):
            return False
        self._wing_busy, self._wing_sent, self._wing_joined = True, now, code
        return True

    def wing_beat(self, leave=False):
        """What one beat says: who (the journal's name, if sharing names is
        on), where, which way, and where this commander's rigs are."""
        state = attr(self, "game")
        system, body = self.here()
        share = getattr(attr(self, "community"), "share_name", True)
        beat = {"member": self.wing_member(), "leave": bool(leave),
                "name": str(getattr(attr(self, "watcher"), "cmdr", "") or "")[:40]
                if share else "",
                "system": str(system or "")[:120], "body": str(body or "")[:120],
                "in_srv": bool(getattr(state, "in_srv", False)), "rigs": []}
        if state is not None and state.has_position:
            beat["lat"], beat["lon"] = float(state.lat), float(state.lon)
            if state.heading is not None:
                beat["heading"] = float(state.heading) % 360.0
        beat["rigs"] = [{"n": int(rig["n"]), "lat": float(rig["lat"]),
                         "lon": float(rig["lon"])}
                        for rig in self._rigs_here()][:12]
        return beat

    def wing_leave(self):
        code = attr(self, "_wing_joined", "")
        self._wing_joined, self.wing_mates = "", []
        community = attr(self, "community")
        if code and community is not None:
            community.wing(code, self.wing_beat(leave=True))

    def take_wing(self, ok, message):
        """The rest of the wing, as the server last heard them."""
        self._wing_busy = False
        if not ok:
            problem = str(message or "")
            if problem != attr(self, "_wing_problem", ""):
                self.say("Wing link: %s" % problem, AMBER)
            self._wing_problem = problem
            return
        try:
            data = json.loads(message)
        except (TypeError, ValueError):
            return
        mates = [mate for mate in data.get("members") or []
                 if isinstance(mate, dict)]
        before = {str(mate.get("name") or "") for mate in
                  attr(self, "wing_mates", None) or []}
        if attr(self, "_wing_problem", ""):
            self._wing_problem = ""
        joined = [str(mate.get("name") or "") or "a wingmate" for mate in mates
                  if str(mate.get("name") or "") not in before]
        self.wing_mates, self._wing_heard = mates, time.time()
        if joined:
            self.say("Wing: %s on the link." % ", ".join(joined), GREEN)

    def wing_marks(self):
        """Wingmates on this body for the scope, as east/north metres from
        the commander, with their rigs. None when there are none."""
        try:
            return self._wing_marks()
        except Exception:
            return None

    def _wing_marks(self):
        mates = attr(self, "wing_mates", None)
        if not mates or not self.wing_on():
            return None
        state = attr(self, "game")
        if not (state is not None and state.has_position and state.radius_m):
            return None
        heard = time.time() - (attr(self, "_wing_heard", 0.0) or 0.0)
        system, body = self.here()
        marks = []
        for mate in mates:
            if not (_same_place(mate.get("system"), system)
                    and _same_place(mate.get("body"), body)):
                continue
            if float(mate.get("age_s") or 0) + heard > WING_STALE_S:
                continue
            if mate.get("lat") is None or mate.get("lon") is None:
                continue
            east, north = SV.local_offset(state.lat, state.lon, mate["lat"],
                                          mate["lon"], state.radius_m)
            rigs = []
            for rig in mate.get("rigs") or []:
                re_, rn = SV.local_offset(state.lat, state.lon, rig["lat"],
                                          rig["lon"], state.radius_m)
                rigs.append({"n": rig.get("n"), "east": re_, "north": rn})
            marks.append({"name": str(mate.get("name") or "") or "wingmate",
                          "east": east, "north": north,
                          "heading": mate.get("heading"),
                          "in_srv": bool(mate.get("in_srv")), "rigs": rigs})
        return {"mates": marks} if marks else None

    def wing_clash(self, lat, lon):
        """(name, rig, metres) for a wingmate's rig closer than the rig
        spacing to this spot, or None."""
        state = attr(self, "game")
        if not self.wing_on() or state is None or not state.radius_m:
            return None
        system, body = self.here()
        spacing = self.planner_spacing()
        closest = None
        for mate in attr(self, "wing_mates", None) or []:
            if not (_same_place(mate.get("system"), system)
                    and _same_place(mate.get("body"), body)):
                continue
            for rig in mate.get("rigs") or []:
                metres = SV.surface_range_m(lat, lon, rig["lat"], rig["lon"],
                                            state.radius_m)
                if metres < spacing and (closest is None or metres < closest[2]):
                    closest = (str(mate.get("name") or "a wingmate"),
                               rig.get("n"), metres)
        return closest

    @staticmethod
    def pin_reach(plan):
        """How close a rig has to be to a pin to count as on it: half the
        spacing, never less than PLAN_PIN_DONE_M. Nobody drops a rig on the
        exact spot, and at 20 m a rig a car's length off did not count.
        Pins are a full spacing apart, so no rig can count for two."""
        try:
            spacing = float((plan or {}).get("spacing") or 0)
        except (TypeError, ValueError):
            spacing = 0.0
        return max(PLAN_PIN_DONE_M, spacing / 2.0)

    def plan_pin_at(self, lat, lon):
        """The number of the plan's pin at this spot, or None."""
        plan = attr(self, "rig_plan", None)
        state = attr(self, "game")
        if not plan or state is None or not state.radius_m:
            return None
        reach = self.pin_reach(plan)
        for pin in plan["pins"]:
            if SV.surface_range_m(lat, lon, pin["lat"], pin["lon"],
                                  state.radius_m) <= reach:
                return pin["n"]
        return None

    def plan_marks(self):
        """The trace or the plan for the overlay, as east/north metres from
        the commander, or None. Never raises."""
        try:
            return self._plan_marks()
        except Exception:
            return None

    def _plan_marks(self):
        trace = attr(self, "_trace", None)
        plan = attr(self, "rig_plan", None)
        if trace is None and not plan:
            return None
        state = attr(self, "game")
        if not (state is not None and state.has_position and state.radius_m):
            return None
        system, body = self.here()
        where = (str(system).lower(), str(body).lower())
        radius = state.radius_m

        def offset(lat, lon):
            return SV.local_offset(state.lat, state.lon, lat, lon, radius)

        if trace is not None and not trace.closed:
            if where != attr(self, "_trace_where"):
                return None
            return {"tracing": True, "near": True, "pins": [], "spacing": 0,
                    "outline": [offset(lat, lon) for lat, lon in trace.outline()],
                    "next": None, "next_pin": None, "done": 0}
        if not plan or where != (plan["system"], plan["body"]):
            return None
        rigs = self._rigs_here()
        reach = self.pin_reach(plan)
        pins = []
        for pin in plan["pins"]:
            east, north = offset(pin["lat"], pin["lon"])
            done = any(SV.surface_range_m(rig["lat"], rig["lon"], pin["lat"],
                                          pin["lon"], radius) <= reach
                       for rig in rigs)
            pins.append({"n": pin["n"], "east": east, "north": north,
                         "done": done, "range_m": math.hypot(east, north)})
        waiting = [pin for pin in pins if not pin["done"]]
        following = waiting[0] if waiting else None
        next_pin = None
        if following is not None:
            bearing = math.degrees(math.atan2(following["east"],
                                              following["north"])) % 360.0
            turn = (bearing - float(state.heading or 0.0) + 540.0) % 360.0 - 180.0
            next_pin = {"n": following["n"], "range_m": following["range_m"],
                        "offset": turn}
        return {"tracing": False, "pins": pins, "spacing": plan["spacing"],
                "outline": [offset(lat, lon) for lat, lon in plan["outline"]],
                "near": any(pin["range_m"] <= PLAN_NEAR_M for pin in pins),
                "next": following["n"] if following is not None else None,
                "next_pin": next_pin, "done": len(pins) - len(waiting)}

    def rig_commodity(self, state, system, body):
        """What a rig going down here is mining.

        The deposit it is on, when one is marked close by - that is the
        deposit's own record, not a guess. Failing that, whatever is in the
        Commodity box, which is what the commander is about to mark; then
        what the scanner last named. Blank rather than wrong.
        """
        try:
            radius = state.radius_m or 0
            best = None
            for row in self.store.at(system, body):
                try:
                    metres = SV.surface_range_m(state.lat, state.lon,
                                                float(row["lat"]), float(row["lon"]),
                                                radius)
                except (TypeError, ValueError, KeyError):
                    continue
                if radius and metres <= RIG_ON_DEPOSIT_M and \
                        (best is None or metres < best[0]):
                    best = (metres, row.get("commodity") or "")
            if best and best[1]:
                return SV.canonical(best[1])
        except Exception:
            pass
        fields = attr(self, "fields", None) or {}
        typed = ""
        try:
            typed = str(fields["commodity"].get() or "").strip()
        except Exception:
            pass
        if typed and SV.known_commodity(typed):
            return SV.canonical(typed)
        return SV.canonical(getattr(state, "detected_type", "") or "")

    def rigs_up(self, picked=None):
        """Rigs collected: forget them all and stop watching the distance.

        Also the hand-operated off switch for every rig warning - the banner,
        the last warning in the middle of the screen, the lot - so a warning
        that is wrong, or about rigs already lost, is one key from gone.
        `picked` is the rig whose own key brought the last one up."""
        self.clear_rig_alarm()
        if not self._rigs_here() and picked is None:
            self.rigs_at = None
            return self.say("No rigs are marked down.", AMBER)
        count = len(self.rigs_at["rigs"]) if self.rigs_at else 0
        if picked is not None:
            count = 1
        self.rigs_at = None
        self._rigs_warned = False
        self._rigs_final = False
        self.rig_event("RigsUp")
        self.refresh_rigs_note()
        self.redraw()
        if picked is not None:
            self.flash("RIG %d UP" % picked, "all rigs up - warning stood down")
            return self.say("Rig %d up - that was the last. Distance warning "
                            "stood down." % picked, GREEN)
        self.flash("%d RIG%s UP" % (count, "" if count == 1 else "S"),
                   "distance warning stood down")
        return self.say("%d rig(s) up. Distance warning stood down." % count, GREEN)

    def watch_rigs(self, state):
        """Where every rig is from here; warn once per excursion.

        The warning is about the FARTHEST rig: past the limit from any one of
        them is too far. It sounds once as the SRV crosses the line, and is
        re-armed only after coming back inside 90% of it - so driving along
        the line does not set it off every poll. Leaving the body forgets
        the rigs: they are not coming with you. Never raises.
        """
        if not attr(self, "rigs_at", None):
            self.clear_rig_alarm()
            return None
        try:
            rigs = self._rigs_here()
            if not rigs:
                self.rigs_at = None
                self._rigs_warned = False
                self._rigs_final = False
                self.clear_rig_alarm()
                self.refresh_rigs_note()
                return None
            if not (state is not None and state.has_position and state.radius_m):
                return None
            marks = []
            for rig in rigs:
                metres = SV.surface_range_m(state.lat, state.lon, rig["lat"],
                                            rig["lon"], state.radius_m)
                east, north = SV.local_offset(state.lat, state.lon, rig["lat"],
                                              rig["lon"], state.radius_m)
                marks.append({"n": rig["n"], "range_m": metres,
                              "commodity": rig.get("commodity") or "",
                              "east": east, "north": north,
                              "bearing": SV.bearing_deg(state.lat, state.lon,
                                                        rig["lat"], rig["lon"])})
            # Past RIG_LOST_M from the Rhino a rig is destroyed. It is not
            # coming back, so it stops being watched - and a warning about a
            # rig that no longer exists is noise that hides the next real one.
            # Only from the Rhino: from the ship or on foot the distance that
            # counts is the Rhino's, and that is not where Status.json is.
            if getattr(state, "in_srv", False):
                lost = [m for m in marks if m["range_m"] >= RIG_LOST_M]
                if lost:
                    gone = {m["n"] for m in lost}
                    self.rigs_at["rigs"] = [r for r in self.rigs_at["rigs"]
                                            if r["n"] not in gone]
                    marks = [m for m in marks if m["n"] not in gone]
                    names = ", ".join(str(n) for n in sorted(gone))
                    self.say("RIG %s LOST - more than %s from the Rhino. "
                             "Warnings cleared%s." % (
                                 names, _metres(RIG_LOST_M),
                                 "; still watching the rest" if marks else ""),
                             RED)
                    self.flash("RIG %s LOST" % names, "past %s - warning cleared"
                               % _metres(RIG_LOST_M), RED)
                    self._rigs_final = False
                    self.clear_rig_alarm()
                    self.refresh_rigs_note()
                    if not marks:
                        self.rigs_at = None
                        self._rigs_warned = False
                        return None
            farthest = max(marks, key=lambda m: m["range_m"])
            limit = self.rig_limit()
            far = bool(limit) and farthest["range_m"] > limit
            if far and not attr(self, "_rigs_warned", False):
                self._rigs_warned = True
                self.say("TOO FAR FROM RIG %d - %s back to it, bearing %03d."
                         % (farthest["n"], _metres(farthest["range_m"]),
                            round(farthest["bearing"]) % 360), RED)
                if self.settings.get("rig_warn_sound", True):
                    self.sound_alarm()
            elif limit and farthest["range_m"] < limit * 0.9:
                self._rigs_warned = False
            # The last warning. The game's own comes at 4 km and the rig is
            # gone at 5, so 200 m short of that it takes the middle of the
            # screen and sounds again - whatever distance the first warning
            # is set to, because this one is about losing the rig. Silent
            # only if the rig sound is switched off altogether.
            final = farthest["range_m"] >= RIG_FINAL_M
            if final:
                if not attr(self, "_rigs_final", False):
                    self._rigs_final = True
                    self.say("LAST WARNING - RIG %d IS %s AWAY. It is destroyed "
                             "at %s. Turn back: bearing %03d." % (
                                 farthest["n"], _metres(farthest["range_m"]),
                                 _metres(RIG_LOST_M),
                                 round(farthest["bearing"]) % 360), RED)
                    if self.settings.get("rig_warn_sound", True):
                        self.sound_alarm()
                self.show_rig_alarm(farthest, state)
            else:
                if farthest["range_m"] < RIG_FINAL_M - 300:
                    self._rigs_final = False
                self.clear_rig_alarm()
            return {"rigs": marks, "count": len(marks), "n": farthest["n"],
                    "range_m": farthest["range_m"],
                    "bearing": farthest["bearing"], "limit_m": limit,
                    "far": far, "final": final,
                    "offset": SV.relative_bearing(state.heading or 0.0,
                                                  farthest["bearing"])}
        except Exception:
            return None

    def show_rig_alarm(self, farthest, state):
        """The big warning triangle, middle of the screen, over the game."""
        overlay = attr(self, "overlay", None)
        shower = getattr(overlay, "alarm", None)
        if not callable(shower):
            return False
        offset = SV.relative_bearing(getattr(state, "heading", 0.0) or 0.0,
                                     farthest["bearing"])
        try:
            return shower("RIG %d  %s" % (farthest["n"],
                                          _metres(farthest["range_m"])),
                          "LOST AT %s - TURN BACK %s %03d" % (
                              _metres(RIG_LOST_M), OV.turn_arrow(offset),
                              round(farthest["bearing"]) % 360))
        except Exception:
            return False

    def clear_rig_alarm(self):
        overlay = attr(self, "overlay", None)
        clearer = getattr(overlay, "end_alarm", None)
        if callable(clearer):
            try:
                clearer()
            except Exception:
                pass

    def refresh_rigs_note(self):
        note = attr(self, "rigs_note", None)
        if note is None:
            return
        try:
            rigs = self._rigs_here()
            if rigs:
                note.configure(text="%d of %d rigs down on %s: %s." % (
                    len(rigs), MAX_RIGS, self.rigs_at["body"],
                    ", ".join(("%d %s" % (r["n"], r.get("commodity") or "")).strip()
                              for r in sorted(rigs, key=lambda r: r["n"]))),
                    text_color=GREEN)
            else:
                note.configure(text=self.rigs_hint(), text_color=DIM)
        except Exception:
            pass

    def sound_alarm(self):
        """The rig warning, spoken - the clean one or the profane one, as
        Settings says. Windows' own exclamation if the file is missing, the
        bell if there is no sound at all."""
        path = warning_sound(bool(self.settings.get("rig_sound_profane")))
        try:
            import winsound
            if path:
                winsound.PlaySound(path, winsound.SND_FILENAME
                                   | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
                return True
            winsound.PlaySound("SystemExclamation",
                               winsound.SND_ALIAS | winsound.SND_ASYNC)
            return True
        except Exception:
            pass
        try:
            self.bell()
            return True
        except Exception:
            return False

    # -- the survey area ----------------------------------------------------

    def _survey_map(self):
        """The live coverage map, or None. Stub-safe."""
        cmap = attr(self, "cmap", None)
        return cmap if isinstance(cmap, CV.CoverageMap) else None

    def track_survey(self, state):
        """Paint the ground the SRV has swept, and keep the right map live.

        Only in the SRV: the scanner is on the SRV, so ground crossed in the
        ship or on foot has not been swept. A new map starts on a new body,
        or more than SAME_MAP_M from the current one.
        """
        if not (state and state.has_position and state.radius_m):
            return None
        book = attr(self, "survey_book", None)
        if not isinstance(book, CV.CoverageBook):
            return None
        system, body = self.here()
        if not (system and body):
            return None
        cmap = self._survey_map()
        far = cmap.distance_from(state.lat, state.lon) if cmap else None
        if (cmap is None or cmap.system != system or cmap.body != body
                or (far is not None and far > CV.SAME_MAP_M)):
            if cmap is not None and cmap.points:
                book.save(cmap)
            cmap = book.map_for(system, body, state.lat, state.lon, state.radius_m)
            self._configure_survey(cmap)
            self.cmap = cmap
        if getattr(state, "in_srv", False) and cmap.add_fix(state.lat, state.lon):
            if time.time() - (attr(self, "_cmap_saved", 0.0) or 0.0) > 20:
                book.save(cmap)
                self._cmap_saved = time.time()
            self.refresh_survey_note()
        return cmap

    def _configure_survey(self, cmap):
        """The scanner reach and overlap from Settings, onto a map."""
        try:
            scan = float(self.settings.get("survey_scan_m") or CV.SCAN_RADIUS_M)
            overlap = float(self.settings.get("survey_overlap_m") or CV.OVERLAP_M)
        except (TypeError, ValueError):
            scan, overlap = CV.SCAN_RADIUS_M, CV.OVERLAP_M
        if scan > 0 and (cmap.scan_m != scan or cmap.overlap_m != overlap):
            cmap.scan_m, cmap.overlap_m = scan, max(0.0, overlap)
            cmap._reset_raster()

    def _border_after_centre(self, cmap):
        """A border pressed before the centre, now that there is one.

        Only on the body it was pressed on. Returns the border in metres, or
        None - nothing kept, another body, or too close to the centre."""
        waiting = attr(self, "_border_waiting", None)
        if not waiting or cmap is None or cmap.centre is None:
            return None
        system, body = self.here()
        if waiting[:2] != (SV.fold(system), SV.fold(body)):
            return None
        self._border_waiting = None
        return cmap.set_border(waiting[2], waiting[3])

    def set_survey_centre(self):
        """The middle of the area to survey is where you are standing."""
        state = self.game
        cmap = self.track_survey(state)
        if cmap is None:
            return self.say("No surface position from the game yet.", AMBER)
        cmap.set_centre(state.lat, state.lon)
        kept = self._border_after_centre(cmap)
        self.survey_book.save(cmap)
        self.refresh_survey_note()
        self.redraw()
        if kept:
            self.flash("SURVEY CENTRE SET", "border %s, from the point you kept"
                       % _metres(kept))
            return self.say("Survey centre set, and the border you pressed "
                            "first is %s from it." % _metres(kept), GREEN)
        border_key = self.key("border", "BORDER")
        self.flash("SURVEY CENTRE SET",
                   "drive to the edge of the area, then %s" % border_key)
        return self.say("Survey centre set. Drive to the edge of the area you "
                        "want covered and press %s." % border_key, GREEN)

    def set_survey_border(self):
        """The edge of the area is where you are standing now."""
        state = self.game
        cmap = self.track_survey(state)
        if cmap is None:
            return self.say("No surface position from the game yet.", AMBER)
        if cmap.centre is None:
            # Pressed out of order - at the edge before the middle. The
            # point is kept, not refused: the moment the centre is set it
            # becomes the border, measured from there.
            system, body = self.here()
            self._border_waiting = (SV.fold(system), SV.fold(body),
                                    state.lat, state.lon)
            self.flash("BORDER KEPT", "now log the signal in the middle (%s)"
                       % self.key("location", "LOG SIGNAL"))
            return self.say("Border point kept. Log the signal in the middle "
                            "of the area (%s) and it becomes the border."
                            % self.key("location", "LOG SIGNAL"), AMBER)
        border = cmap.set_border(state.lat, state.lon)
        if border is None:
            return self.say("That is too close to the centre to be a border. "
                            "Drive further out and press BORDER again.", AMBER)
        self.survey_book.save(cmap)
        self.refresh_survey_note()
        self.redraw()
        rings = cmap.rings()
        plan = ("drive the circles on the map at %s" % ", ".join(
                    _metres(r) for r in rings)) if rings else \
               "the centre alone covers it"
        self.flash("BORDER SET  %s" % _metres(border), plan)
        return self.say("Border set at %s: %s." % (_metres(border), plan), GREEN)

    def clear_survey(self):
        """Forget the centre and border; keep the ground already swept."""
        cmap = self._survey_map()
        if cmap is None or cmap.centre is None:
            return self.say("There is no survey area set here.", AMBER)
        cmap.centre = None
        cmap.clear_border()
        cmap._reset_raster()
        self.survey_book.save(cmap)
        self.refresh_survey_note()
        self.redraw()
        return self.say("Survey area cleared. The ground you swept is kept.",
                        GREEN)

    def survey_summary(self):
        """One line: how much of the area is swept, and where the gap is."""
        cmap = self._survey_map()
        if cmap is None:
            return ""
        cover = cmap.coverage()
        if cmap.centre is None:
            log = self.key("location", "LOG SIGNAL")
            return ("Swept %.1f km2 here. Log the signal (%s) to centre the "
                    "survey on it." % (cover["painted_km2"], log)
                    if cover["painted_km2"] else
                    "Log the signal (%s) to centre the survey on it." % log)
        if cmap.border_m is None:
            return "Centre set. Drive to the edge and press BORDER."
        line = "Swept %d%% of the %s area." % (cover["percent"],
                                               _metres(cmap.border_m))
        if cover["percent"] >= 100:
            return line + " All of it - nothing left to scan."
        gaps = cmap.gaps(limit=1)
        if gaps:
            gap = gaps[0]
            if gap["distance_m"] < cmap.scan_m:
                line += " Still to sweep: all round the edge."
            else:
                line += " Biggest gap %s %s out." % (
                    SV.compass(gap["bearing"]), _metres(gap["distance_m"]))
        return line

    def refresh_survey_note(self):
        note = attr(self, "survey_note", None)
        if note is None:
            return
        try:
            text = self.survey_summary() or (
                "Log the signal (%s), then drive to the edge and press %s."
                % (self.key("location"), self.key("border", "BORDER")))
            cmap = self._survey_map()
            done = bool(cmap and cmap.border_m and cmap.coverage()["percent"] >= 100)
            note.configure(text=text, text_color=GREEN if done else DIM)
        except Exception:
            pass

    def survey_view(self, system, body, centre, radius, quick=False):
        """Everything the map and overlay draw for the survey, in metres
        east and north of `centre` (where the commander is).

        quick: the fast loop's version. Where things are is worked out
        fresh; how much is swept and where the gaps are is the last full
        tick's answer, because those are the expensive sums and they do not
        move between two readings of Status.json."""
        cmap = self._survey_map()
        if cmap is None or centre is None or cmap.system != system \
                or cmap.body != body:
            return None
        try:
            def rel(lat, lon):
                return SV.local_offset(centre[0], centre[1], lat, lon, radius)
            kept = attr(self, "_survey_sums", None)
            if quick and not (isinstance(kept, dict) and kept.get("map") is cmap):
                quick = False
            cover = kept["cover"] if quick else cmap.coverage()
            if not quick:
                self._survey_sums = {"map": cmap, "cover": cover, "gaps": None}
            view = {"scan_m": cmap.scan_m,
                    "points": [rel(lat, lon) for lat, lon in cmap.points],
                    "centre": rel(*cmap.centre) if cmap.centre else None,
                    "border_m": cmap.border_m,
                    "rings": cmap.rings() if cmap.centre else [],
                    "gaps": [], "percent": None,
                    "painted_km2": cover["painted_km2"]}
            if cmap.centre is not None and cmap.border_m:
                view["percent"] = cover["percent"]
                ce, cn = view["centre"]
                gaps = kept.get("gaps") if quick else None
                if gaps is None:
                    gaps = cmap.gaps(limit=3)
                    self._survey_sums["gaps"] = gaps
                for gap in gaps:
                    rad = math.radians(gap["bearing"])
                    view["gaps"].append({
                        "east": ce + math.sin(rad) * gap["distance_m"],
                        "north": cn + math.cos(rad) * gap["distance_m"],
                        "bearing": gap["bearing"],
                        "distance_m": gap["distance_m"],
                        "area_km2": gap["area_km2"]})
            return view
        except Exception:
            return None

    # -- other commanders' finds -----------------------------------------

    # -- where to land ---------------------------------------------------

    def want_landing(self, system, force=False):
        """Ask for what Where to land needs from the server, if it is time.

        The grounds table changes slowly and is asked for at most every ten
        minutes; a system's shared sites every SHARED_REFRESH_S. Neither is
        asked twice at once. With no server it asks nothing, and the window
        works from the journal and the tables alone.
        """
        community = attr(self, "community")
        if community is None or not getattr(community, "can_read", False):
            return False
        now = time.time()
        asked = False
        grounds_stale = now - float(attr(self, "_grounds_at", 0.0) or 0.0) >= 600
        grounds_waiting = now - float(attr(self, "_grounds_asked", 0.0) or 0.0) < SHARED_WAIT_S
        if (force or grounds_stale) and not grounds_waiting:
            self._grounds_asked = now
            asked = bool(community.grounds()) or asked
        system = str(system or "").strip()
        if system:
            if not isinstance(attr(self, "land_sites", None), dict):
                self.land_sites = {}
            if not isinstance(attr(self, "_land_asked", None), dict):
                self._land_asked = {}
            key = system.lower()
            have = self.land_sites.get(key)
            fresh = have is not None and now - have["at"] < SHARED_REFRESH_S
            waiting = now - self._land_asked.get(key, 0) < SHARED_WAIT_S
            if (force or not fresh) and not waiting:
                self._land_asked[key] = now
                asked = bool(community.system_sites(system)) or asked
        return asked

    def take_grounds(self, ok, message):
        if not ok:
            self._land_error = "Could not load what each kind of ground carries: %s" % message
        else:
            try:
                data = json.loads(message)
                if isinstance(data, dict) and isinstance(data.get("grounds"), list):
                    self.grounds = data
                    self._grounds_at = time.time()
                    self._land_error = ""
            except (ValueError, TypeError):
                self._land_error = "The server's ground table could not be read."
        self._land_changed()

    def take_landing(self, ok, message):
        if not ok:
            self._land_error = "Could not load this system's shared sites: %s" % message
            return self._land_changed()
        try:
            data = json.loads(message)
            system = str(data["system"])
            rows = [r for r in (data.get("sites") or []) if isinstance(r, dict)]
        except (ValueError, KeyError, TypeError):
            self._land_error = "The server's answer for this system could not be read."
            return self._land_changed()
        if not isinstance(attr(self, "land_sites", None), dict):
            self.land_sites = {}
        self.land_sites[system.strip().lower()] = {"at": time.time(), "rows": rows}
        self._land_error = ""
        self._land_changed()

    def _land_changed(self):
        lander = attr(self, "lander")
        try:
            if lander is not None and lander.winfo_exists():
                lander._paint()
        except Exception:
            self.lander = None

    def follow_land(self):
        """Keep an open Where to land window current. Never raises."""
        lander = attr(self, "lander")
        if lander is None:
            return
        try:
            if lander.winfo_exists():
                lander.follow()
            else:
                self.lander = None
        except Exception:
            self.lander = None

    def land_sites_for(self, system):
        have = (attr(self, "land_sites", None) or {}).get(str(system or "").strip().lower())
        return None if have is None else have["rows"]

    def land_problem(self):
        community = attr(self, "community")
        if community is None or not getattr(community, "can_read", False):
            return ("Community off - ranked from your scans and the commodity "
                    "tables only. Turn it on in Settings to see shared sites.")
        problem = str(attr(self, "_land_error", "") or "")
        if problem and getattr(self.watcher, "system", ""):
            if self.land_sites_for(self.watcher.system) is not None:
                problem += " - showing what was loaded earlier."
        return problem

    def land_swept(self, system, bodies):
        """{body lower-cased: best percent swept} from your survey maps."""
        out = {}
        book = attr(self, "survey_book")
        if book is None:
            return out
        for body in bodies:
            try:
                best = None
                for cmap in book.maps_on(system, body):
                    percent = cmap.coverage().get("percent")
                    if percent is not None and (best is None or percent > best):
                        best = percent
                if best is not None:
                    out[str(body).strip().lower()] = best
            except Exception:
                continue
        return out

    def land_rows(self, system, landable_only=True):
        """Where to land, ranked: journal + shared sites + your own data."""
        system = str(system or "").strip()
        if not system:
            return []
        bodies = self.watcher.system_bodies(system)
        store = attr(self, "store")
        deposits = list(getattr(store, "deposits", []) or [])
        locations = list(getattr(store, "locations", []) or [])
        names = {b["body"] for b in bodies}
        names |= {d.get("body") for d in deposits + locations
                  if str(d.get("system") or "").strip().lower() == system.lower()
                  and d.get("body")}
        return SV.rank_bodies(system, bodies, attr(self, "grounds"),
                              self.land_sites_for(system),
                              attr(self, "prices", None) or {},
                              deposits, locations,
                              self.land_swept(system, sorted(names)),
                              landable_only=landable_only)

    def land_signature(self, system):
        """Everything the table depends on, cheaply. Changes = redraw."""
        try:
            bodies = self.watcher.system_bodies(system) if system else []
        except Exception:
            bodies = []
        have = (attr(self, "land_sites", None) or {}).get(str(system or "").lower())
        store = attr(self, "store")
        return (str(system or ""),
                tuple((b["body"], b.get("locations"), b.get("mapped"),
                       b.get("landable")) for b in bodies),
                have["at"] if have else None,
                attr(self, "_grounds_at", 0.0),
                str(attr(self, "_land_error", "") or ""),
                # Moves every time the live survey map is saved, so Swept
                # keeps up while driving without re-reading it every poll.
                attr(self, "_cmap_saved", 0.0),
                len(getattr(store, "deposits", []) or []),
                len(getattr(store, "locations", []) or []))

    def want_shared(self, system, body, force=False):
        """Ask for this body's shared finds, if it is time to.

        Once on arrival and then every SHARED_REFRESH_S, never twice at once,
        and not at all with the switch off or no server to ask.
        """
        if not (system and body and self.settings.get("show_shared_finds", True)):
            return False
        community = attr(self, "community")
        if community is None or not getattr(community, "can_read", False):
            return False
        key = (system.lower(), body.lower())
        now = time.time()
        if not isinstance(attr(self, "shared", None), dict):
            self.shared = {}
        if not isinstance(attr(self, "_shared_asked", None), dict):
            self._shared_asked = {}
        asked = self._shared_asked.get(key, 0)
        have = self.shared.get(key)
        fresh = have is not None and now - have["at"] < SHARED_REFRESH_S
        waiting = now - asked < SHARED_WAIT_S
        if not force and (fresh or waiting):
            return False
        self._shared_asked[key] = now
        return bool(community.body_deposits(system, body))

    def take_shared(self, ok, message):
        """File an answer to want_shared under the body it was about."""
        if not ok:
            return
        try:
            data = json.loads(message)
            system, body = str(data["system"]), str(data["body"])
        except (ValueError, KeyError, TypeError):
            return
        rows = []
        for item in data.get("deposits") or []:
            try:
                lat, lon = float(item["lat"]), float(item["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            rows.append({
                "id": "shared-%s" % item.get("id", len(rows)),
                "system": item.get("system") or system,
                "body": item.get("planet") or body,
                "location": str(item.get("spot") or ""),
                "commodity": SV.remember(item.get("type") or "") or "",
                "rigs": str(item.get("rigs") or ""),
                "amount": ("Depleted" if item.get("worked_out")
                           else str(item.get("amount") or "")),
                "density": str(item.get("density") or ""),
                "lat": "%.6f" % lat, "lon": "%.6f" % lon,
                "notes": "",
                "cmdr": str(item.get("uploader") or ""),
                "status": str(item.get("status") or ""),
                "shared": True,
            })
        if not isinstance(attr(self, "shared", None), dict):
            self.shared = {}
        self.shared[(system.lower(), body.lower())] = {"at": time.time(),
                                                       "rows": rows}
        asked = attr(self, "_shared_asked", None)
        if isinstance(asked, dict):
            asked.pop((system.lower(), body.lower()), None)
        try:
            self.redraw()
        except Exception:
            pass

    def shared_near(self, system, body, centre, radius, mine):
        """Shared finds on this body, as map rows, minus any that are yours.

        Your own finds come back from the server too, once shared. The same
        commodity within SAME_FIND_M of one of yours is that one, and is
        drawn once - as yours, because yours can be edited.
        """
        if not self.settings.get("show_shared_finds", True):
            return []
        book = attr(self, "shared", None)
        if not isinstance(book, dict):
            return []
        entry = book.get((str(system).lower(), str(body).lower()))
        if not entry or centre is None:
            return []
        out = []
        for row in SV.rows_near(entry["rows"], centre[0], centre[1], radius):
            theirs = row["deposit"]
            duplicate = False
            for own in mine:
                ours = own["deposit"]
                if SV.fold(ours.get("commodity")) != SV.fold(theirs.get("commodity")):
                    continue
                try:
                    apart = SV.surface_range_m(float(ours["lat"]), float(ours["lon"]),
                                               row["lat"], row["lon"], radius)
                except (KeyError, TypeError, ValueError):
                    continue
                if apart <= SAME_FIND_M:
                    duplicate = True
                    break
            if not duplicate:
                out.append(row)
        return out

    def own_deposit_here(self, commodity=""):
        """(deposit, metres): the deposit of yours you are standing on.

        Within SAME_DEPOSIT_M of where the game says you are, on this body.
        With a commodity named, only a deposit of that commodity counts -
        a patch can hold two commodities a few metres apart, and the one in
        the commodity box is the one being talked about. None if there is
        nothing close enough.
        """
        state = self.game
        if not (state and state.has_position):
            return None
        system, body = self.here()
        radius = state.radius_m or 1e6
        wanted = SV.fold(commodity) if commodity else ""
        close = []
        for deposit in self.store.at(system, body):
            if wanted and SV.fold(deposit.get("commodity")) != wanted:
                continue
            try:
                metres = SV.surface_range_m(state.lat, state.lon,
                                            float(deposit["lat"]),
                                            float(deposit["lon"]), radius)
            except (KeyError, TypeError, ValueError):
                continue
            if metres <= SAME_DEPOSIT_M:
                close.append((metres, deposit))
        if not close:
            return None
        metres, deposit = min(close, key=lambda pair: pair[0])
        return deposit, metres

    def update_deposit_here(self):
        """Write the rail's Amount (and Density or Rigs, if set) onto the
        deposit you are standing on.

        The Amount is what goes down as a deposit is worked, and marking it
        again would put a second copy on the map. Blank boxes change
        nothing - an update never wipes what was recorded before - and each
        update adds a dated line to the deposit's notes, so it keeps its
        history.
        """
        state = self.game
        if not (state and state.has_position):
            return self.say("No surface position from the game yet.", AMBER)
        commodity = (self.fields["commodity"].get().strip()
                     or state.detected_type or "")
        found = self.own_deposit_here(commodity)
        if found is None and commodity:
            found = self.own_deposit_here("")
        # MARK just asked "rename it, or add another?" - UPDATE is the rename.
        rename = None
        retype = attr(self, "_retype_armed", None)
        if retype and time.time() - retype[2] < RETYPE_WAIT_S:
            system, body = self.here()
            radius = state.radius_m or 1e6
            for deposit in self.store.at(system, body):
                if deposit.get("id") != retype[0]:
                    continue
                try:
                    metres = SV.surface_range_m(state.lat, state.lon,
                                                float(deposit["lat"]),
                                                float(deposit["lon"]), radius)
                except (KeyError, TypeError, ValueError):
                    break
                if metres <= SAME_DEPOSIT_M:
                    found, rename = (deposit, metres), retype[3]
                break
        self._retype_armed = None
        if found is None:
            return self.say("There is no deposit of yours within %s of here. "
                            "MARK DEPOSIT records a new one."
                            % _metres(SAME_DEPOSIT_M), AMBER)
        deposit, metres = found
        changes = {}
        if rename and SV.fold(rename) != SV.fold(deposit.get("commodity")):
            changes["commodity"] = SV.canonical(rename) or rename
        for key in ("amount", "density", "rigs"):
            value = self.fields[key].get().strip()
            if value and value != str(deposit.get(key) or ""):
                changes[key] = value
        if "density" not in changes and state.detected_density \
                and state.detected_density != deposit.get("density"):
            changes["density"] = state.detected_density
        if "rigs" in changes:
            try:
                rigs = int(float(changes["rigs"]))
            except ValueError:
                return self.say("Rigs must be a number.", RED)
            if not 0 <= rigs <= MAX_RIGS:
                return self.say("The Rhino carries %d rigs." % MAX_RIGS, RED)
            changes["rigs"] = str(rigs)
        if not changes:
            return self.say("%s %s from here already says that. Set the Amount "
                            "on the left, then press UPDATE."
                            % (deposit.get("commodity") or "The deposit",
                               _metres(metres)), AMBER)
        was = deposit.get("commodity") or "the deposit"
        said = ", ".join("%s %s" % (key.capitalize(), value)
                         for key, value in changes.items())
        if "commodity" in changes:
            said = said.replace("Commodity %s" % changes["commodity"],
                                "was %s, now %s" % (was, changes["commodity"]))
        changes["notes"] = SV.stamp_note(deposit.get("notes"),
                                         "Updated (%s)" % said)
        row = self.deposit_edited(deposit["id"], changes)
        if row is not None:
            if "commodity" in changes:
                self.say("Renamed the deposit %s from here: %s. Its position, "
                         "history and tonnes are kept." % (_metres(metres), said),
                         GREEN)
                self.flash("RENAMED  %s" % str(row.get("commodity") or "")
                           .upper()[:22], "was %s" % was)
                return row
            self.say("Updated %s %s from here: %s."
                     % (row.get("commodity") or "the deposit", _metres(metres),
                        said), GREEN)
            self.flash("UPDATED  %s" % str(row.get("commodity") or "DEPOSIT")
                       .upper()[:22], said[:64])
        return row

    def signal_to_log(self, state, system, body):
        """(number, why) for LOG SIGNAL: which signal you are standing in.

        Picking the number by hand from a list, then pressing the key, was
        the step testers kept getting wrong. In order:
          - the one the game has targeted, when Status.json names it;
          - the number in the Signal box, if nothing is logged under it yet
            - a number picked on purpose is the answer;
          - the box's signal again, if you are inside it - pressing the key
            twice at one signal is the same signal;
          - a logged signal you are right on top of, whatever the box says;
          - otherwise the lowest number not yet used on this body, so a new
            signal never lands on top of one logged somewhere else.
        """
        targeted = str(getattr(state, "target_signal", "") or "").strip()
        if targeted:
            return targeted, "the game has it targeted"
        radius = state.radius_m or 1e6
        boxed = str(self.signal()).strip()
        logged = self.store.location(system, body, boxed)
        try:
            apart = SV.surface_range_m(state.lat, state.lon, float(logged["lat"]),
                                       float(logged["lon"]), radius)
        except (TypeError, ValueError, KeyError):
            return boxed, ""
        if apart <= PV.SIGNAL_AT_M:
            return boxed, "you are inside it"
        here = SV.nearest_signal(self.store.locations_on(system, body),
                                 state.lat, state.lon, radius, SAME_SIGNAL_M)
        if here is not None:
            return str(here["location"]).strip(), "you are inside it"
        used = set()
        for row in self.store.locations_on(system, body):
            try:
                used.add(int(float(row.get("location") or 0)))
            except (TypeError, ValueError):
                continue
        number = 1
        while number in used:
            number += 1
        return str(number), "signal %s is logged %s away" % (boxed,
                                                           _metres(apart))

    def log_location(self):
        """Record the mining location signal you are standing in.

        No commodities are asked for: they come with the deposits, marked
        one by one. A signal already logged is never moved by pressing the
        key again - its centre stays where it was first logged, and the
        Move the centre key is there for moving it on purpose.
        """
        state = self.game
        if not (state and state.has_position):
            self.say("No surface position from the game yet.", AMBER)
            return
        system, body = self.here()
        number, why = self.signal_to_log(state, system, body)
        if number != str(self.signal()).strip():
            self.choose_signal(number)
        existing = self.store.location(system, body, number)
        placed = existing is not None and str(existing.get("lat") or "").strip()
        offered = []
        if state.detected_type:
            offered.append(SV.remember(state.detected_type))
        for name in self.store.offered(existing):
            if name not in offered:
                offered.append(name)

        self.store.set_location(
            system, body, number,
            lat=None if placed else state.lat,
            lon=None if placed else state.lon,
            radius_m=state.radius_m or 1e6,
            commodities=offered or None,
            temperature_k=state.body_temperature(),
            cmdr=state.cmdr or "")
        self._signal_picked = True
        self._kept_border = None
        centred = self.centre_on_signal(state)
        kept = attr(self, "_kept_border", None) if centred else None
        self.refresh_locations()
        self.refresh_deposits()
        self.redraw()
        border = self.key("border", "BORDER")
        how = (" (%s)" % why) if why else ""
        if placed:
            self.say("Signal %s%s is already logged - its centre stays where it "
                     "is. Hold the mineral scanner down, drive out to the "
                     "location's edge line and press %s there, then keep it "
                     "held while you map the area." % (number, how, border),
                     GREEN)
            return self.flash("SIGNAL %s" % number, "already logged - hold the "
                              "scanner, %s at the edge" % border)
        self.say("Signal %s logged%s%s. Now hold the mineral scanner down and "
                 "keep holding it: drive out to the location's edge line and "
                 "press %s there, then keep it held while you map the area. "
                 "No commodities needed yet - they come with each deposit."
                 % (number, how,
                    (", the survey centre set here and the border you pressed "
                     "first %s from it" % _metres(kept)) if kept else
                    ", and the survey centre set here" if centred else "",
                    border), GREEN)
        self.flash("SIGNAL %s LOGGED" % number,
                   ("centre set, border %s" % _metres(kept)) if kept else
                   "hold the scanner - %s at the edge" % border)

    def centre_on_signal(self, state):
        """Logging a signal sets the survey centre on it - the signal IS the
        middle of the area to survey. Only when there is no centre yet:
        pressing LOG SIGNAL again to add what the signal offers must not drag an
        area that already has a border. CENTRE moves it on purpose.
        True if the centre was set."""
        try:
            cmap = self.track_survey(state)
            if cmap is None or cmap.centre is not None:
                return False
            cmap.set_centre(state.lat, state.lon)
            self._kept_border = self._border_after_centre(cmap)
            self.survey_book.save(cmap)
            self.refresh_survey_note()
            return True
        except Exception as exc:
            # The signal is logged whatever happens here; the fault is
            # written down and the line after this says what did work.
            self.trouble("Survey centre from logging the signal", exc)
            return False

    # -- selection -------------------------------------------------------

    def on_pick(self, deposit):
        self.selected = deposit
        if deposit is None:
            self.detail.configure(text="Click a deposit on the map.", text_color=DIM)
            self.detail_buttons.pack_forget()
            return
        state = self.game
        lines = [deposit.get("commodity") or "unknown", ""]
        if state and state.has_position:
            try:
                radius = state.radius_m or 1e6
                metres = SV.surface_range_m(state.lat, state.lon,
                                            float(deposit["lat"]),
                                            float(deposit["lon"]), radius)
                bearing = SV.bearing_deg(state.lat, state.lon,
                                         float(deposit["lat"]),
                                         float(deposit["lon"]))
                lines.append("%s away, %s %s" % (_metres(metres),
                                                 SV.compass(bearing), 
                                                 "%03.0f" % bearing))
                if state.heading is not None:
                    lines.append("from here: %s" % SV.turn_hint(state.heading, bearing))
            except (TypeError, ValueError):
                lines.append("no position recorded")
        lines.append("")
        lines.append("rigs: %s" % (deposit.get("rigs") or "not recorded yet"))
        amount = deposit.get("amount") or ""
        if amount:
            worked = SV.is_depleted(amount)
            lines.append("amount: %s%s" % (amount,
                                           "  - worked out" if worked else ""))
            age = worked_out_age(deposit)
            if age:
                lines.append(age)
        if deposit.get("planet_class"):
            lines.append("")
            lines.append(deposit["planet_class"])
        lines.append("density: %s" % (deposit.get("density") or "not recorded"))
        lines.append("signal %s" % (deposit.get("location") or "-"))
        centre = from_centre(self.store, deposit)
        if centre:
            lines.append(centre)
        if deposit.get("recorded"):
            lines.append("logged %s" % str(deposit["recorded"])[:10])
        # Counted off the game's own tonne-by-tonne record while EDSMT was
        # running.
        lines.extend(tonnes_lines(deposit, attr(self.store, "deposits", None)))
        if deposit.get("shared"):
            # Somebody else's. It can be driven to; it cannot be edited or
            # deleted from here, because it is not in your records.
            lines.append("")
            lines.append("shared by %s" % (deposit.get("cmdr") or ANONYMOUS))
            if str(deposit.get("status") or "").lower() == "verified":
                lines.append("VERIFIED")
            lines.append("Mark it yourself to add it to your finds.")
            self.detail.configure(text="\n".join(lines), text_color=TEXT)
            self.detail_buttons.pack_forget()
            return
        self.detail.configure(text="\n".join(lines), text_color=TEXT)
        self.detail_buttons.pack(fill="x", padx=12, pady=(0, 12))

    def edit_deposit(self, deposit):
        """Open the editor on one deposit. Double-click on the map, or the
        Edit button - both land here.

        This method was defined TWICE in this class. Python kept the
        second, and the error handling was in the first - so a raise inside
        EditWindow was swallowed by Tk and the Edit button was simply dead
        with nothing said. Same shape as the duplicate here() that made the
        distance filter never fire.
        """
        if not deposit:
            return self.say("Pick a deposit first.", AMBER)
        if deposit.get("shared"):
            return self.say("That one was shared by %s. Mark it yourself to "
                            "add it to your own finds."
                            % (deposit.get("cmdr") or "another commander"), AMBER)
        try:
            window = attr(self, "_editor")
            if window is not None and window.winfo_exists():
                window.destroy()
            self._editor = EditWindow(self, deposit)
        except Exception as exc:
            self.say("Could not open that deposit: %s" % exc, RED)

    def copy_selected(self):
        """The selected find as one line of text, for Discord or a friend."""
        deposit = attr(self, "selected", None)
        if not deposit:
            return self.say("Click a deposit first.", AMBER)
        line = share_line(deposit)
        try:
            put_on_clipboard(self, line)
        except Exception as exc:
            return self.say("Could not reach the clipboard: %s" % exc, RED)
        self.say("Copied - paste it anywhere. Anyone with EDSMT pastes it "
                 "into Settings -> Your finds and presses Import.", GREEN)
        return line

    def edit_selected(self):
        self.edit_deposit(self.selected)

    def mark_mined(self):
        """You worked it out. Say so, and stamp when.

        Not a delete: the deposit is still there, still on the map, still
        worth coming back to. It regenerates - slowly - and a record that
        says "empty as of the tenth" beats no record at all, both for you
        and for whoever reads it in three months.
        """
        if not self.selected:
            return self.say("Pick a deposit first.", AMBER)
        # The re-upload lives in deposit_edited now, so a correction made
        # in the edit window goes up the same way this one does. The guard
        # that used to be here was redundant anyway: share() already
        # checks that the client is ready.
        changes = {"amount": "Depleted",
                   "notes": SV.stamp_note(self.selected.get("notes"), "Mined")}
        # What it gave this time is what it held: filed as a cycle, and the
        # count starts again for when it has grown back.
        cycle = SV.close_cycle(self.selected)
        if cycle:
            changes["cycles"], changes["mined"] = cycle
            own = SV.cycle_tonnes({"cycles": cycle[0]})[-1]
            changes["notes"] = SV.stamp_note(self.selected.get("notes"),
                                             "Mined out after %dt" % own)
        return self.deposit_edited(self.selected["id"], changes)

    def deposit_edited(self, deposit_id, changes):
        """Write an edit back and put every view in step with it."""
        row = self.store.update_deposit(deposit_id, **changes)
        if row is None:
            return self.say("That deposit is no longer there.", AMBER)
        self.selected = row
        self.refresh_locations()
        self.refresh_deposits()
        self.redraw()
        self.on_pick(row)
        # And put the correction where everyone else can see it. Only
        # mark_mined ever did this, so fixing a wrong commodity locally
        # left it wrong in the community database for good. share() decides
        # whether anything actually leaves the machine.
        self.share(row)
        self.say("Corrected %s." % (row.get("commodity") or "the deposit"), GREEN)
        return row

    def location_edited(self, row_id, system, body, old, new, offers):
        """Write a signal correction back, deposits included."""
        try:
            moved = self.store.renumber_location(system, body, old, new)
        except ValueError as exc:
            self.say(str(exc), RED)
            return False
        self.store.set_offered(row_id, offers)
        if str(old) == str(self.signal()):
            self.location_box.set(str(new))
        self.refresh_signal_box()
        self.refresh_locations()
        self.refresh_deposits()
        self.refresh_location_note()
        self.redraw()
        if moved:
            self.say("Signal %s is now %s, and its %d deposit%s moved with it."
                     % (old, new, moved, "" if moved == 1 else "s"), GREEN)
        else:
            self.say("Signal %s updated." % new, GREEN)
        return True

    def delete_location(self, row_id):
        """Forget a signal. Its deposits are left alone, and said so."""
        orphans = self.store.remove_location(row_id)
        if orphans is None:
            return self.say("That signal is no longer there.", AMBER)
        self.refresh_signal_box()
        self.refresh_locations()
        self.refresh_deposits()
        self.refresh_location_note()
        self.redraw()
        if orphans:
            self.say("Signal forgotten. Its %d deposit%s are still on the map."
                     % (orphans, "" if orphans == 1 else "s"), AMBER)
        else:
            self.say("Signal forgotten.")
        return True

    def delete_selected(self):
        if self.selected:
            self.delete_deposit(self.selected["id"])

    def delete_deposit(self, deposit_id):
        """Delete by id rather than by whatever happens to be selected, so
        the editor can delete the deposit it was opened on even if the map
        selection has moved on underneath it."""
        row = next((d for d in self.store.deposits if d["id"] == deposit_id),
                   None)
        name = (row or {}).get("commodity") or "that deposit"
        if self.store.remove_deposit(deposit_id):
            if self.selected and self.selected.get("id") == deposit_id:
                self.selected = None
                self.on_pick(None)
            self.refresh_locations()
            self.refresh_deposits()
            self.redraw()
            self.say("Deleted %s." % name)
            return True
        return False

    # -- online ----------------------------------------------------------

    def show_best_patch(self):
        """Where to put the rigs down.

        The surface equivalent of overlapping hotspots: the tightest group
        with the most rigs and the most different commodities in it. The
        map jumps to its nearest deposit so it is not just a number.
        """
        system, body = self.here()
        if not (system and body):
            return self.say("No body yet.", AMBER)
        rows = self.store.at(system, body, self.signal())
        if not rows:
            return self.say("Nothing marked in signal %s yet." % self.signal(),
                            AMBER)
        # A patch made of deposits you already stripped is not a patch worth
        # driving to. They stay on the map; they just do not win this.
        live = [r for r in rows if not SV.is_depleted(r.get("amount"))]
        if not live:
            return self.say("Everything in signal %s is marked worked out."
                            % self.signal(), AMBER)
        radius = (self.game.radius_m if self.game else None) or 1e6
        patches = EDO.rank_clusters(
            [{"type": r.get("commodity"), "rigs": r.get("rigs"),
              "density": r.get("density"), "lat": r.get("lat"),
              "lon": r.get("lon")} for r in live],
            body_radius_m=radius)
        if not patches:
            return self.say("Not enough positions to work out a patch.", AMBER)

        best = patches[0]
        names = ", ".join(sorted(best["types"])) or "unknown"
        self.say("Best patch: %d deposit(s), %d rig(s), %s, within %s."
                 % (best["deposits"], best["rigs"], names,
                    _metres(best["spread_km"] * 1000.0)), GREEN)
        chosen = [live[i] for i in best["indices"]]
        if chosen:
            self.plan.select(chosen[0].get("id"))
            self.on_pick(chosen[0])

    def mark_worked_out(self):
        """Say this signal is stripped, so nobody drives out to it.

        Not a delete. It drops out of everyone's results and climbs back as
        it regenerates, because that is what surface deposits do.
        """
        system, body = self.here()
        if not (system and body):
            return self.say("No body yet.", AMBER)
        if not self.community.ready:
            return self.say("Turn community sharing on in Settings first.",
                            AMBER)
        self.community.report_depletion(self.watcher.cmdr, system, body,
                                        self.signal())
        self.say("Reported signal %s on %s as worked out."
                 % (self.signal(), body), GREEN)

    def share(self, record):
        if not (self.community.ready
                and self.settings.get("community_auto_share", True)):
            return
        try:
            self.community.upload(self.watcher.cmdr, [{
                "system": record["system"], "planet": record["body"],
                "spot": record["location"], "type": record["commodity"],
                "rigs": int(float(record["rigs"] or 0)),
                # No direction and no distance: there is no spot centre to
                # measure from. The coordinates ARE the position, and the
                # server treats them as the deposit's identity.
                "lat": float(record["lat"]) if record["lat"] else None,
                "lon": float(record["lon"]) if record["lon"] else None,
                "density": record.get("density") or "",
                "amount": record.get("amount") or "",
                "status": record.get("status") or SV.STATUS_REPORTED,
                "planet_class": record.get("planet_class") or "",
                "gravity": record.get("gravity") or None,
                "atmosphere": record.get("atmosphere") or "",
                "volcanism": record.get("volcanism") or "",
                "temperature_k": float(record["temperature_k"])
                                 if record.get("temperature_k") else None,
                "notes": "",
                # Where in the galaxy this is. Sent so that everyone else's
                # copy can answer "what is near me" - which, with 400
                # billion systems in the game, is the only form of the
                # question worth asking. Taken from the journal, never
                # typed, and simply absent if the game has not said yet.
                **self.galactic_position(),
            }])
        except Exception:
            pass
        self.verify_own(record)

    def verify_own(self, record):
        """A staff commander's own finds go up verified.

        Anyone holding a staff token has, by definition, stood on what they
        just mapped, so asking them to go and press Verify on every one is a
        chore that only produces unverified rows. The server still decides:
        it checks the token against the staff list and records the name, so
        nothing here can award itself the badge. Queued behind the upload on
        the same worker, so the site exists by the time the request lands.
        """
        community = attr(self, "community")
        if community is None or not getattr(community, "can_verify", False):
            return False
        if not self.settings.get("verify_my_finds", True):
            return False
        if not (record.get("system") and record.get("body")):
            return False
        try:
            return bool(community.verify(self.watcher.cmdr, record["system"],
                                         record["body"],
                                         str(record.get("location") or "1")))
        except Exception:
            return False

    def report_online(self, state):
        self.inara.set_commander(state.cmdr, state.fid)
        if self.inara.ready and not self._inara_checked:
            self._inara_checked = True
            self.inara.verify()
        here = (state.system, state.body)
        if state.system and here != self._last_reported:
            self._last_reported = here
            self.inara.travel_location(state.system, state.body)
        if state.pending_land:
            land = state.pending_land
            state.pending_land = None
            self.inara.travel_land(land["system"], land["body"],
                                   land["lat"], land["lon"], land["when"])
        self.inara.flush()

        if state.pending_market:
            market = state.pending_market
            state.pending_market = None
            if self.settings.get("share_market_prices", True):
                self.community.upload_prices(self.watcher.cmdr, market)

    def collect_results(self):
        """Hand finished background work to whoever asked for it.

        THIS MUST NOT LIVE INSIDE report_online, and it used to.

        report_online is about the game: it polls the journal, tells Inara
        where you are, and is skipped entirely the moment watcher.poll()
        raises - Elite not running, journal folder missing, a torn line, any
        of it. The worker queue was drained on the way past, so a search
        fired from the Find window was answered by the server, parked in the
        queue, and never collected. The window sat empty for ever and there
        was nothing wrong with the server, the network, or the search.

        Searching the community map has nothing to do with the game being
        on. It gets its own call, from tick's finally block, in its own
        try/except.
        """
        try:
            finished = self.worker.drain()
        except Exception:
            return
        for tag, ok, message in finished:
            if tag == "body":
                self.take_shared(ok, message)
                continue
            if tag == "grounds":
                self.take_grounds(ok, message)
                continue
            if tag == "landing":
                self.take_landing(ok, message)
                continue
            if tag == "wing":
                self.take_wing(ok, message)
                continue
            if tag == QUOTE_TAG:
                try:
                    self.take_quote(ok, message)
                except Exception:
                    pass
                continue
            if tag in FIND_TAGS:
                finder = attr(self, "finder")
                shown = False
                try:
                    # A Find window closed while its answer was in flight is
                    # a destroyed widget, and drawing into one raises. That
                    # must not take the rest of the queue with it.
                    if finder is not None and finder.winfo_exists():
                        finder.results(tag, message, ok)
                        shown = True
                except Exception:
                    self.finder = None
                # A search answer with nobody left to read it is no loss.
                # A write that came back refused is, so that one falls
                # through to the status line rather than into the bin.
                if shown or tag != "verify":
                    continue
            if tag == "update-download":
                self.update_downloaded(ok, message)
                continue
            if tag in ("update", "update-now"):
                # An empty message means there is nothing newer.
                #
                # On LAUNCH that means say nothing: being told you are up to
                # date every time you open the app is noise. From the
                # Settings BUTTON the same empty answer has to become "you
                # are up to date", or a working check and a broken one look
                # exactly the same - which is how this ended up reported as
                # not working when it was doing its job.
                asked = tag == "update-now"
                if not ok:
                    if asked:
                        self.say("Could not check for updates: %s" % message,
                                 RED)
                elif message:
                    self.announce_update(message)
                elif asked:
                    self.say("You are up to date - EDSMT %s is the latest "
                             "build." % APP_VERSION, GREEN)
                continue
            if tag == "share" and ok:
                self.note_shared(message)
            label = {"inara": "Inara", "inara-verify": "Inara key",
                     "share": "Shared", "prices": "Market",
                     "verify": "Verify"}.get(tag, tag)
            try:
                self.say("%s: %s" % (label, message), GREEN if ok else RED)
            except Exception:
                pass

    def announce_update(self, message):
        """A newer build exists. Fetch it if we can, and say so either way.

        The answer from the check is JSON naming the packages. With the
        setting on and a package for this kind of build, the download
        starts now and the button becomes INSTALL UPDATE when it has been
        checked. Otherwise the button offers to fetch it - and only when
        there is nothing it could fetch does it send anyone to the website.
        """
        try:
            info = json.loads(message)
            if not isinstance(info, dict):
                raise ValueError
        except (ValueError, TypeError):
            info = {"message": str(message)}
        self.update_info = info
        # The installed build updates from Setup, the portable one from the
        # single exe. Anything else has nothing it could safely replace.
        wanted = {"installed": "installer", "portable": "portable"}.get(build_kind())
        package = info.get(wanted) if wanted else None
        self.update_package = package if isinstance(package, dict) else None
        try:
            self.say(str(info.get("message") or message), GREEN)
            if self.update_package and self.settings.get("auto_download_updates", True):
                self.fetch_update()
            else:
                self.show_update_button("UPDATE AVAILABLE")
        except Exception:
            pass

    def show_update_button(self, text, ready=True):
        button = attr(self, "btn_update")
        if button is None:
            return
        try:
            button.configure(text=text, state="normal" if ready else "disabled")
            if not button.winfo_ismapped():
                button.pack(side="right", padx=(8, 0))
        except Exception:
            pass

    def update_button_pressed(self):
        """One button, whichever step the update is at."""
        if attr(self, "update_ready", None):
            return self.install_update()
        if attr(self, "update_package", None):
            return self.fetch_update()
        return self.open_download_page()

    def fetch_update(self):
        """Download the new build in the background. Never runs it."""
        info = attr(self, "update_info", None) or {}
        package = attr(self, "update_package", None)
        version = str(info.get("version") or "")
        if not (package and version):
            return self.open_download_page()
        if attr(self, "_update_fetching", False):
            return False
        name = "EDSMT-Setup-%s.exe" if build_kind() == "installed" else "EDSMT-%s.exe"
        dest = os.path.join(updates_folder(), name % version)
        self._update_fetching = True
        self.show_update_button("DOWNLOADING...", ready=False)
        self.say("Downloading EDSMT %s from radioraxxla.com..." % version)
        return self.updates.download(package, dest, version)

    def update_downloaded(self, ok, message):
        """The download finished - checked, or thrown away."""
        self._update_fetching = False
        if not ok:
            self.say("Could not download the update: %s" % message, RED)
            self.show_update_button("UPDATE AVAILABLE")
            return
        try:
            self.update_ready = json.loads(message)
        except (ValueError, TypeError):
            self.update_ready = None
            return self.show_update_button("UPDATE AVAILABLE")
        self.show_update_button("INSTALL UPDATE")
        self.say("EDSMT %s is downloaded and checked. Press INSTALL UPDATE when "
                 "you are ready - EDSMT closes, updates and opens again by "
                 "itself. Your finds and settings are kept."
                 % self.update_ready.get("version", ""), GREEN)

    def follow_update(self):
        """While a download runs, the button counts it up. Never raises."""
        try:
            progress = self.updates.progress
            if progress and attr(self, "_update_fetching", False):
                got, size = progress
                self.show_update_button("DOWNLOADING %d%%" % int(100 * got / max(1, size)),
                                        ready=False)
        except Exception:
            pass

    def install_update(self):
        """The click that installs it. Checks the file again first.

        installed  Setup is started quietly - it shows its progress bar,
                   keeps the folder, the shortcuts and every setting, and
                   opens EDSMT again when it is done
        portable   the running exe is renamed aside, the new one put in its
                   place, and started
        """
        ready = attr(self, "update_ready", None) or {}
        path, digest = str(ready.get("path") or ""), str(ready.get("sha256") or "")
        if not (path and digest and os.path.exists(path)
                and EDO.sha256_of(path) == digest):
            self.update_ready = None
            self.say("The downloaded update is missing or changed since it was "
                     "checked, so it was not run. Fetching it again.", RED)
            return self.fetch_update()
        kind = build_kind()
        try:
            self._save_on_exit()
            if kind == "installed":
                command = [path, "/SILENT", "/SP-", "/NORESTART",
                           "/CLOSEAPPLICATIONS"]
            elif kind == "portable":
                command = [self._swap_portable(path)]
            else:
                return self.open_download_page()
        except Exception as exc:
            self.say("Could not install the update: %s" % exc, RED)
            return False
        # Let go of the one-copy lock first, or the new copy - or Setup,
        # which asks for the same name - finds this one still running.
        release_single_instance()
        try:
            import subprocess
            flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0
            subprocess.Popen(command, close_fds=True, creationflags=flags)
        except Exception as exc:
            claim_single_instance()
            self.say("Could not start the update: %s. It is saved at %s"
                     % (exc, path), RED)
            return False
        self.on_close()
        return True

    @staticmethod
    def _swap_portable(new_exe):
        """Put the new single-file exe where the running one is.

        A running program can be renamed but not overwritten, so this one
        moves aside to EDSMT.exe.old (removed on the next start) and the new
        one is copied into its name. If the copy fails the old one is put
        back, so there is never a moment with no EDSMT.exe at all.
        """
        import shutil
        exe = os.path.abspath(sys.executable)
        old = exe + ".old"
        if os.path.exists(old):
            os.remove(old)
        os.replace(exe, old)
        try:
            shutil.copy2(new_exe, exe)
        except Exception:
            os.replace(old, exe)
            raise
        return exe

    # -- chrome ----------------------------------------------------------

    def say(self, text, colour=None):
        colour = colour or DIM
        self.status.configure(text=text, text_color=colour)
        self._last_said = (text, colour)

    def flash(self, title, detail="", colour=None):
        """Say it over the game as well: a key pressed with the game in
        front does its work where the status line cannot be seen. Never
        raises - a confirmation that fails is not worth an error."""
        self._flashed = True
        overlay = attr(self, "overlay", None)
        if overlay is None:
            return False
        try:
            return overlay.flash(title, detail, colour)
        except Exception:
            return False

    def flash_said(self):
        """After a key: if the action did not flash anything itself, flash
        the first sentence of what it said - "No surface position from the
        game yet" is exactly what needs saying over the game."""
        text, colour = attr(self, "_last_said", None) or ("", DIM)
        title, detail = flash_lines(text)
        if not title:
            return False
        return self.flash(title, detail, RED if colour == RED else
                          AMBER if colour == AMBER else GREEN)

    def open_settings(self):
        SettingsWindow(self)

    def find_unlocked(self):
        """Whether this commander has put a deposit of their own on the
        shared map - which is what opens Find.

        The shared map is only as good as what goes into it, so reading it
        starts with adding to it. Remembered in settings once the server
        takes one. A commander who was already sharing before this rule came
        in - finds of their own, marked with sharing on - is not locked out
        of what they helped build: one complete find of their own counts.
        """
        settings = attr(self, "settings", None) or {}
        if settings.get("find_unlocked"):
            return True
        if not (settings.get("community_enabled")
                and settings.get("community_auto_share", True)):
            return False
        try:
            for row in self.store.deposits:
                if row.get("status") == SV.STATUS_REPORTED and \
                        row.get("commodity") and row.get("lat") and \
                        row.get("amount") and row.get("density"):
                    return True
        except Exception:
            pass
        return False

    def note_shared(self, message):
        """A share the server answered: the first one opens Find."""
        try:
            numbers = [int(n) for n in re.findall(r"\d+", str(message or ""))]
        except ValueError:
            numbers = []
        if not sum(numbers[:2]):
            return False
        if self.settings.get("find_unlocked"):
            return True
        self.settings["find_unlocked"] = True
        save_settings(self.settings)
        self.say("Your first find is on the shared map - Find is open to you "
                 "now.", GREEN)
        return True

    def open_find(self):
        if not self.find_unlocked():
            sharing = self.settings.get("community_enabled")
            self.say("Find opens once you have shared a deposit of your own. "
                     "%s" % ("Mark one - all four boxes filled in - and it "
                             "goes up by itself." if sharing else
                             "Switch sharing on in Settings, then mark one "
                             "with all four boxes filled in."), AMBER)
            return None
        self.finder = FindWindow(self)
        return self.finder

    def open_earnings(self):
        self.ledger = EarningsWindow(self)

    def open_sites(self):
        """One My sites window. Asking again brings it forward, re-read."""
        sites = attr(self, "sites_window")
        try:
            if sites is not None and sites.winfo_exists():
                sites.refresh()
                sites.deiconify()
                sites.lift()
                sites.focus_force()
                return sites
        except Exception:
            pass
        self.sites_window = SitesWindow(self)
        return self.sites_window

    def open_land(self):
        """One Where to land window. Asking again brings it to the front."""
        # The guide's second step is done once this has been opened in the
        # system you are in.
        self._land_opened_in = str(getattr(attr(self, "watcher"), "system", "")
                                   or "")
        lander = attr(self, "lander")
        try:
            if lander is not None and lander.winfo_exists():
                lander.deiconify()
                lander.lift()
                lander.focus_force()
                return lander
        except Exception:
            pass
        self.lander = LandWindow(self)
        return self.lander

    def apply_settings(self, data):
        self.settings = data
        save_settings(data)
        self.inara.configure(data.get("inara_api_key", ""),
                             data.get("inara_enabled", False),
                             data.get("inara_is_being_developed", False))
        self._inara_checked = False
        self.community.configure(data.get("community_url", ""),
                                 data.get("community_token", ""),
                                 data.get("community_enabled", False),
                                 data.get("community_share_cmdr_name", True))
        self.watcher.set_directory(data.get("journal_dir", "") or None)
        self._last_reported = None
        self.hotkeys.start(self.wanted_hotkeys(data))
        self.overlay.settings = data
        if data.get("overlay_enabled"):
            self.overlay.show()
            self.overlay.refresh_settings(data)
        else:
            self.overlay.hide()
        self.show_overlay_state()
        self.refresh_rigs_note()
        self.refresh_key_labels()
        set_high_g(data)
        self.earnings.multi = bool(data.get("earnings_multi_session"))

    def set_mark_ready(self, ready):
        """MARK DEPOSIT is bright when it will work and plainly dark when not.

        Disabled, it used to stay orange with grey writing on it - the one
        button that matters, unreadable, and looking live when it was not.
        """
        button = attr(self, "btn_mark")
        if button is None:
            return
        try:
            if ready:
                button.configure(state="normal", fg_color=ORANGE,
                                 text_color=VOID)
            else:
                button.configure(state="disabled", fg_color=STEEL,
                                 text_color_disabled=DIM)
        except Exception:
            pass

    def save_settings(self):
        """Save now. The overlay calls this the moment a box is dropped.

        It asked for it by name from the start and nothing answered, so a
        dragged box was only written down when the app closed cleanly -
        and an installer closing it for an update is not always clean.
        """
        return save_settings(self.settings)

    def _save_on_exit(self):
        """Everything that has to be on disk before the app goes. Never raises."""
        try:
            self.save_refined(force=True)
        except Exception:
            pass
        try:
            cmap = self._survey_map()
            if cmap is not None and cmap.points:
                self.survey_book.save(cmap)
        except Exception:
            pass
        try:
            self.overlay.remember_position()
            save_settings(self.settings)
        except Exception:
            pass

    def restart_app(self):
        """Start a fresh copy of EDSMT and close this one.

        How a new app theme is worn: the window keeps the colours it was
        built with, so the theme needs a window built after it. The
        one-copy lock is let go first, the same way an update does it, or
        the new copy finds this one still running and refuses to open.
        """
        self._save_on_exit()
        # This program and nothing else: the exe it is, or the script it
        # was started as. Nothing downloaded is ever run from here - that is
        # install_update's job alone, and it checks the hash first.
        if getattr(sys, "frozen", False):
            relaunch = [sys.executable]
        else:
            relaunch = [sys.executable,
                       os.path.abspath(sys.argv[0] if sys.argv and sys.argv[0]
                                       else __file__)]
        release_single_instance()
        try:
            import subprocess
            flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0
            subprocess.Popen(relaunch, close_fds=True, creationflags=flags)
        except Exception as exc:
            claim_single_instance()
            self.say("Could not restart: %s. Close EDSMT and open it again "
                     "to wear the new theme." % exc, RED)
            return False
        self.on_close()
        return True

    def on_close(self):
        self._save_on_exit()
        try:
            self.overlay.hide()
            self.hotkeys.stop()
            self.watcher.close()
        except Exception:
            pass
        self.destroy()


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class SettingsWindow(ctk.CTkToplevel):
    """Everything that would otherwise mean hand-editing settings.json."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("EDSMT - Settings")
        self.geometry("640x700")
        self.configure(fg_color=VOID)
        self.transient(app)

        self.fields, self.toggles = {}, {}
        self.secrets, self._hide_timers = {}, {}
        self.binders, self.bindings = {}, {}
        self.choices = {}
        self.colours = {}
        self._capturing = None
        self._capture_id = None
        body = ctk.CTkScrollableFrame(self, **LIST)
        body.pack(fill="both", expand=True, padx=12, pady=(12, 6))

        # The few things everybody sets, first. Each one lives only here -
        # a setting in two places saves whichever copy was built last.
        self._section(body, "Basic settings",
                      "Everything is set to good defaults, so you can start "
                      "without touching any of it. All of it can be changed "
                      "at any time - this section and everything below it - "
                      "and Save keeps it. The keys and the overlay boxes are "
                      "further down.")
        themes = [(OV.THEME_NAMES[k], k) for k in OV.THEME_ORDER]
        self._choice(body, "app_theme", "App theme", themes,
                     "The main window's colours. Worn from the next start - "
                     "Restart now does it straight away.")
        restart_row = ctk.CTkFrame(body, fg_color="transparent")
        restart_row.pack(fill="x", padx=14, pady=(0, 6))
        ctk.CTkButton(restart_row, text="Save and restart now", width=190,
                      height=28, font=F_STRONG, **BTN_SECONDARY,
                      command=self.save_and_restart).pack(side="left")
        self._choice(body, "overlay_theme", "Overlay theme", themes,
                     "The boxes over the game. Changes as soon as you Save.")
        self._switch(body, "overlay_enabled", "Show the overlay while I play")
        self._switch(body, "overlay_show_guide",
                     "Show the step-by-step guide over the game")
        self._switch(body, "rig_sound_profane",
                     "Use the profane rig warning (strong language)")
        self._entry(body, "high_g_warn",
                    "Big warning on bodies from this gravity (g)", "2.0")

        self._section(body, "Sharing your finds",
                      "Leave EDSMT running while you play. What you map is "
                      "shared, and everyone else's turns up under Find. "
                      "Nothing is sent until you switch this on.")
        self._switch(body, "community_enabled", "Share my finds and search everyone else's")
        self._switch(body, "community_auto_share", "Upload each deposit as I mark it")
        self._switch(body, "community_share_cmdr_name", "Credit finds to my CMDR name")
        self._switch(body, "show_shared_finds",
                     "Show other commanders' finds on the map and overlay")
        self._switch(body, "verify_my_finds",
                     "Verify my own finds as I share them (staff token only)")
        self._switch(body, "share_market_prices", "Share prices from stations I dock at")
        self._entry(body, "community_url", "Community API URL",
                    "https://api.radioraxxla.com")
        ctk.CTkLabel(body, text="Already set. Leave it as it is.",
                     font=F_SMALL, text_color=DIM,
                     anchor="w").pack(fill="x", padx=10, pady=(0, 2))
        self._entry(body, "community_token", "Token, if you were given one",
                    "", secret=True)

        self._section(body, "Inara",
                      "Reports where you are while you play. Your CMDR name is "
                      "read from the journal, never typed.")
        self._switch(body, "inara_enabled", "Send my location to Inara")
        self._entry(body, "inara_api_key", "Inara API key",
                    "from your Inara account settings", secret=True)
        self._switch(body, "inara_is_being_developed", "Mark my events as test data")

        self._section(body, "Game folder",
                      "Found automatically. Only set this if Elite lives "
                      "somewhere unusual, or you run it through Steam Play.")
        self._entry(body, "journal_dir", "Saved Games folder", "leave blank for automatic")

        settings_now = getattr(self.app, "settings", None)
        self._section(body, "Rigs",
                      ("Press a rig's key as it goes down - %s for rigs 1 to "
                       "6 - and the same number with %s as you pick it up. "
                       "Each is shown on the scope and the compass with what "
                       "it is on. Drive further than this from any of them "
                       "and the overlay says TOO FAR FROM RIG, with a sound "
                       "if you want one. The game warns at 4 km and destroys "
                       "a rig at 5 km, so at 4.8 km EDSMT puts a big last "
                       "warning in the middle of the screen and sounds "
                       "again. Past 5 km the rig is gone and the warnings "
                       "clear themselves; %s (every rig up) clears them by "
                       "hand. 0 turns the first warning off.")
                      % (OV.rig_keys_words(settings_now) or "RIG DOWN",
                         altgr_word(), bound_key(settings_now, "allup",
                                                 "RIGS UP")))
        self._entry(body, "rig_warn_m", "Warn me this far from a rig (m)", "3500")
        self._switch(body, "rig_warn_sound", "Sound the warning as well as showing it")
        self._switch(body, "rig_planner",
                     "Rig planner (beta): trace a deposit's edge, get a pin "
                     "for each rig")
        ctk.CTkLabel(body, text=(
            "With the planner on, %s starts tracing: drive along the "
            "deposit's edge and back to where you pressed it. The loop "
            "closes by itself, or press it again to close it where you are. "
            "The pins go on the scope in driving order - drop a rig on each "
            "one. The spacing is the community's working figure, not a "
            "published one; change it if you find better."
            % bound_key(settings_now, "trace", "the planner key")),
            font=F_SMALL, text_color=DIM, justify="left", wraplength=560,
            anchor="w").pack(fill="x", padx=10, pady=(0, 4))
        self._entry(body, "rig_spacing_m", "Rig planner: metres between rigs", "78")

        self._section(body, "Wing link (beta)",
                      "Mining one body with friends - or crew off one ship "
                      "with more than one Rhino? Everyone switches this on "
                      "and types the same code, and each of you sees the "
                      "others' Rhinos and rigs on the scope, so nobody drops "
                      "a rig on top of anybody else's. Your commander name "
                      "goes with it only if name sharing is on. Nothing is "
                      "kept: the server forgets you two minutes after you "
                      "switch it off or close EDSMT.")
        self._switch(body, "wing_link", "Wing link (beta): share my Rhino and "
                                        "rigs with my wing")
        self._entry(body, "wing_code", "Wing code (6 letters and digits)",
                    "the same code for everyone")
        code_row = ctk.CTkFrame(body, fg_color="transparent")
        code_row.pack(fill="x", padx=14, pady=(0, 6))
        ctk.CTkButton(code_row, text="Make a new code", width=160, height=28,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.make_wing_code).pack(side="left")

        self._section(body, "Hotkeys",
                      ("Left Alt and the number row - not the number pad - "
                       "in the order you work a signal: Alt+1 signal, Alt+2 "
                       "border, Alt+3 deposit, Alt+4 to Alt+9 rigs 1 to 6. "
                       "The same number with %s undoes it: %s+3 updates the "
                       "deposit, %s+4 to 9 pick the rigs up, %s+0 is every "
                       "rig up. None of these is used by the game's own "
                       "control schemes. They work with the game in front "
                       "of you. Click one and press the key you want "
                       "instead - any key, with or without Ctrl, Alt or "
                       "Shift - and Reset puts it back. Keep clear of keys "
                       "another program already owns, or it gets the key "
                       "first: NVIDIA uses Alt+F1, Alt+F3, Alt+F9, Alt+Z "
                       "and Alt+R, AMD uses Alt+R and Ctrl+Shift keys, "
                       "Windows uses Win keys, Steam uses Shift+Tab and "
                       "F12, the game uses F10. EDSMT says so when you "
                       "pick one.") % ((altgr_word(),) * 4))
        # Labels say what a key does, not which key: the box beside each
        # shows the key actually bound, and a label naming Alt+1 beside a
        # box saying F5 would be wrong the moment somebody changed it.
        rows = [("hotkey_location", "Log the signal and set the centre"),
                ("hotkey_border", "Survey border here"),
                ("hotkey_deposit", "Mark the deposit"),
                ("hotkey_update", "Update the deposit I am on")]
        rows += [("hotkey_rig%d" % n, "Rig %d down" % n)
                 for n in range(1, MAX_RIGS + 1)]
        rows += [("hotkey_rig%dup" % n, "Rig %d up" % n)
                 for n in range(1, MAX_RIGS + 1)]
        rows += [("hotkey_allup", "Every rig up"),
                 ("hotkey_rigs", "The next free rig down (spare key)"),
                 ("hotkey_trace", "Rig planner: trace the deposit's edge (beta)")]
        for name, label in rows:
            self._binding(body, name, label, DEFAULT_SETTINGS[name])
        self._binding(body, "hotkey_centre", "Move the centre here (no new log)", "")
        self._binding(body, "hotkey_lock", "Lock / unlock the overlay", "")
        self.hotkey_note = ctk.CTkLabel(
            body, text="", font=F_SMALL, text_color=AMBER,
            justify="left", anchor="w")
        self.hotkey_note.pack(fill="x", padx=10, pady=(2, 0))

        self._section(body, "Your finds",
                      "One dated zip with everything in it. Worth doing "
                      "before a Windows reinstall, and worth doing whether "
                      "or not you share - sharing sends deposits, not your "
                      "settings or your notes.")
        backup_row = ctk.CTkFrame(body, fg_color="transparent")
        backup_row.pack(fill="x", padx=10, pady=(0, 4))
        ctk.CTkButton(backup_row, text="Back up now", width=130, height=30,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.backup_now).pack(side="left", padx=(0, 8))
        ctk.CTkButton(backup_row, text="Restore from a backup", width=180,
                      height=30, font=F_STRONG, **BTN_SECONDARY,
                      command=self.restore_now).pack(side="left", padx=8)
        ctk.CTkButton(backup_row, text="Open my data folder", width=170,
                      height=30, font=F_STRONG, **BTN_SECONDARY,
                      command=self.open_data_folder).pack(side="left", padx=8)

        # A second row rather than a fourth button: Settings is 640 wide and
        # the three above already fill it. Same section, because bringing
        # somebody else's finds in belongs with backing your own up - both
        # are the database changing under you, and both want the zip.
        import_row = ctk.CTkFrame(body, fg_color="transparent")
        import_row.pack(fill="x", padx=10, pady=(0, 4))
        ctk.CTkButton(import_row, text="Import another tool's CSV", width=210,
                      height=30, font=F_STRONG, **BTN_SECONDARY,
                      command=self.import_now).pack(side="left", padx=(0, 8))
        # Shared finds come in through a box you can see, not straight off
        # the clipboard: whatever was copied last - a password, half a chat -
        # is not read until you have pasted it here and pressed Import.
        ctk.CTkLabel(body, text="Shared finds - paste the lines here, then "
                                "Import (or Enter):",
                     font=F_BODY, text_color=TEXT, anchor="w").pack(
                         fill="x", padx=10, pady=(6, 2))
        paste_row = ctk.CTkFrame(body, fg_color="transparent")
        paste_row.pack(fill="x", padx=10, pady=(0, 4))
        self.paste_box = ctk.CTkTextbox(paste_row, height=64, font=F_SMALL,
                                        **TEXTBOX)
        self.paste_box.pack(side="left", fill="x", expand=True)
        self.paste_box.bind("<Return>", self._paste_enter)
        ctk.CTkButton(paste_row, text="Import", width=90, height=30,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.paste_shared).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(body,
                     text="The CSV: either surfaceminingmap.csv layout. The box: "
                          "lines made by Copy to share on a deposit - chat "
                          "round them is ignored. Nothing already here is "
                          "changed. Shift+Enter starts a new line.",
                     font=F_SMALL, text_color=DIM, justify="left", anchor="w",
                     wraplength=560).pack(fill="x", padx=10, pady=(0, 4))

        self._section(body, "This build",
                      "EDSMT checks for a newer version on launch and says "
                      "nothing if there is not one. A newer one is downloaded "
                      "from radioraxxla.com, checked, and installed only when "
                      "you press INSTALL UPDATE. Press Check for updates to see the "
                      "answer either way.")
        self._switch(body, "auto_download_updates",
                     "Download new versions by myself (installing waits for you)")
        version_row = ctk.CTkFrame(body, fg_color="transparent")
        version_row.pack(fill="x", padx=10, pady=(0, 4))
        ctk.CTkLabel(version_row, text="Version %s" % APP_VERSION,
                     font=F_READOUT, text_color=TEXT,
                     anchor="w").pack(side="left")
        ctk.CTkButton(version_row, text="Check for updates", width=170,
                      height=30, font=F_STRONG, **BTN_SECONDARY,
                      command=self.check_updates).pack(side="right")

        self._section(body, "In-game overlay",
                      "A compass strip across the top of the screen showing "
                      "which way every recorded deposit is, so you never have "
                      "to alt-tab. It CANNOT appear over the game in exclusive "
                      "fullscreen - that is DirectX, not the app. Set Elite to "
                      "borderless or windowed and it will. Unlock it to drag it "
                      "where you want, then lock it again so clicks reach the "
                      "game.")
        # Four boxes, four switches. The old "which overlay" question only
        # ever had one answer at a time, which is why "I want the option for
        # BOTH" had to be asked for three times.
        self._switch(body, "overlay_show_strip",
                     "Box: COMPASS - the tape, which way to turn")
        self._switch(body, "overlay_show_radar",
                     "Box: SCOPE - the patch from above")
        self._switch(body, "overlay_show_targets",
                     "Box: TARGETS - the nearest finds, in order")
        self._switch(body, "overlay_show_status",
                     "Box: STATUS - body, count, and what is next")
        self._switch(body, "overlay_show_deposit",
                     "Box: MINERAL DEPOSIT - one card, with a signal radar")
        sizes = [("%d%%" % size, str(size)) for size in OV.TEXT_SIZES]
        for key, name in ((OV.STRIP, "COMPASS"), (OV.RADAR, "SCOPE"),
                          (OV.TARGETS, "TARGETS"), (OV.STATUS, "STATUS"),
                          (OV.DEPOSIT, "MINERAL DEPOSIT"), (OV.GUIDE, "GUIDE")):
            self._choice(body, "overlay_text_%s" % key, "Text size: %s" % name,
                         sizes, "The words in each box, on their own - the "
                         "box's size is its corner, when unlocked."
                         if key == OV.GUIDE else "")
        # The mode picker did not exist. The scope was built, shipped and
        # unreachable - indistinguishable from never having been built, and
        # reported as "you removed the radar".
        self._choice(body, "overlay_mode", "Which overlay",
                     [("Compass strip", "strip"), ("Radar scope", "radar")],
                     "Only used when none of the boxes above is switched "
                     "on (the guide, in Basic settings, does not count). "
                     "Turn one on and this stops applying.")
        self._choice(body, "overlay_frame", "Draw a border",
                     [("Round the cards only", "cards"),
                      ("Round everything", "all"), ("Nothing", "none")],
                     "The scope is something you look through. A border "
                     "round it sits in your cockpit whether you are looking "
                     "at it or not.")
        self._choice(body, "overlay_centre", "Radar centres on",
                     [("The mining location", "site"), ("My SRV", "srv")],
                     "Only used by the radar scope.")
        self._switch(body, "overlay_click_through",
                     "Lock the boxes in place (clicks pass through to the game)")
        self._switch(body, "overlay_only_over_game",
                     "Only show the boxes while the game is in front")
        self._switch(body, "overlay_flash",
                     "Say over the game what each key just did (RIG 2 DOWN...)")
        self._entry(body, "overlay_opacity", "Opacity 0.2 - 1.0", "0.88")
        self._entry(body, "overlay_width", "Width (pixels)", "blank = fit my screen")
        self._entry(body, "overlay_height", "Height (pixels)", "blank = fit my screen")
        self._entry(body, "overlay_span_deg", "Horizon shown (degrees)", "120")
        self._entry(body, "overlay_targets", "Deposits shown at once", "6")
        # DEFAULT_SETTINGS says in writing that everything in it has a
        # Settings window, and this was the one that did not - hand-edited
        # in settings.json or not changed at all.
        # A box dragged onto a monitor that has since been unplugged, or
        # shoved off the bottom of the screen, is one button to undo - not
        # a settings.json to hand-edit.
        reset_row = ctk.CTkFrame(body, fg_color="transparent")
        reset_row.pack(fill="x", padx=14, pady=(2, 6))
        ctk.CTkButton(reset_row, text="Reset box positions", width=180,
                      height=28, font=F_STRONG, **BTN_SECONDARY,
                      command=self.reset_boxes).pack(side="left")
        ctk.CTkLabel(reset_row, font=F_SMALL, text_color=DIM, anchor="w",
                     text="  Puts every overlay box back where it started. "
                          "Positions are stored as a share of the screen, so "
                          "they follow you between monitors."
                     ).pack(side="left", fill="x", expand=True)

        self._section(body, "Ranking",
                      "How fast a shared find loses value. Deposits come back "
                      "slowly, so a site halves in score every this many days.")
        self._entry(body, "freshness_half_life_days", "Freshness half-life (days)", "21")

        self._section(body, "Beta testers",
                      "Who drove out to the deposits, found what was wrong "
                      "with this and said so. o7")
        ctk.CTkLabel(body, text="   ".join(BETA_TESTERS),
                     font=F_BODY, text_color=AMBER,
                     justify="left", wraplength=560,
                     anchor="w").pack(fill="x", padx=10, pady=(0, 4))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkButton(buttons, text="Save", width=110, height=32,
                      font=F_STRONG, **BTN_PRIMARY,
                      command=self.save).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="Test connection", width=140, height=32,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.test).pack(side="left", padx=8)
        ctk.CTkButton(buttons, text="Close", width=90, height=32,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.destroy).pack(side="right")

        self.status = ctk.CTkLabel(self, text="", font=F_READOUT,
                                   text_color=DIM, anchor="w", wraplength=600)
        self.status.pack(fill="x", padx=14, pady=(0, 10))
        self.load()

    def _section(self, parent, title, blurb):
        hud_header(parent, title, padx=10, pady=(16, 4))
        ctk.CTkLabel(parent, text=blurb, font=F_SMALL, text_color=DIM,
                     justify="left", wraplength=560, anchor="w").pack(fill="x", padx=10,
                                                                     pady=(0, 6))

    def _switch(self, parent, key, label):
        var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(parent, text=label, variable=var, font=F_BODY,
                      **SWITCH).pack(anchor="w", padx=10, pady=4)
        self.toggles[key] = var

    def _entry(self, parent, key, label, placeholder="", secret=False):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row, text=label, width=250, anchor="w",
                     font=F_BODY, text_color=TEXT).pack(side="left")
        if secret:
            # People show Settings on stream. A key or token is dots until
            # Show is pressed, and goes back to dots by itself - nobody has
            # to remember to hide it again with a chat full of viewers.
            # Packed before the entry so it keeps its width when narrow.
            button = ctk.CTkButton(row, text="Show", width=68, height=30,
                                   font=F_STRONG, **BTN_SECONDARY,
                                   command=lambda: self.reveal(key))
            button.pack(side="right", padx=(6, 0))
            self.secrets[key] = button
        entry = ctk.CTkEntry(row, placeholder_text=placeholder, height=30,
                             font=F_BODY, **ENTRY, show=MASK if secret else "")
        entry.pack(side="left", fill="x", expand=True)
        self.fields[key] = entry

    def reveal(self, key):
        """Show or hide one key box. Shown, it hides again after REVEAL_S."""
        entry, button = self.fields.get(key), self.secrets.get(key)
        if entry is None or button is None:
            return
        if button.cget("text") == "Hide":
            return self.hide_secret(key)
        entry.configure(show="")
        button.configure(text="Hide")
        self._forget_hide(key)
        try:
            self._hide_timers[key] = self.after(int(REVEAL_S * 1000),
                                                lambda: self.hide_secret(key))
        except Exception:
            pass

    def hide_secret(self, key):
        entry, button = self.fields.get(key), self.secrets.get(key)
        self._forget_hide(key)
        if entry is None or button is None:
            return
        try:
            entry.configure(show=MASK)
            button.configure(text="Show")
        except Exception:
            pass    # the window has gone; there is nothing left to show

    def destroy(self):
        # A pending hide would fire into a window that no longer exists.
        for key in list(getattr(self, "_hide_timers", {})):
            self._forget_hide(key)
        super().destroy()

    def hide_secrets(self):
        for key in list(self.secrets):
            self.hide_secret(key)

    def _paste_enter(self, event=None):
        """Enter imports; Shift+Enter is a new line in the box."""
        try:
            if int(getattr(event, "state", 0) or 0) & 0x0001:
                return None
        except (TypeError, ValueError):
            pass
        self.paste_shared()
        return "break"

    def make_wing_code(self):
        """A fresh wing code in the box, for reading out to the wing."""
        box = self.fields.get("wing_code")
        if box is None:
            return
        box.delete(0, "end")
        box.insert(0, new_wing_code())
        self.say("New wing code in the box - read it out to your wing, then "
                 "Save.", GREEN)

    def _forget_hide(self, key):
        timer = self._hide_timers.pop(key, None)
        if timer is not None:
            try:
                self.after_cancel(timer)
            except Exception:
                pass

    def _choice(self, parent, key, label, options, hint=""):
        """A named choice, stored as its value rather than its label.

        The box shows what a person reads; settings.json holds what the
        code tests. Renaming a label then never silently changes a stored
        setting.
        """
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row, text=label, width=250, anchor="w",
                     font=F_BODY, text_color=TEXT).pack(side="left")
        box = ctk.CTkComboBox(row, values=[name for name, _v in options],
                              font=F_BODY, height=30, **BOX)
        box.pack(side="left", fill="x", expand=True)
        Suggest(box, [name for name, _v in options])
        self.choices[key] = (box, list(options))
        if hint:
            ctk.CTkLabel(parent, text=hint, font=F_SMALL,
                         text_color=DIM, justify="left", anchor="w",
                         wraplength=560).pack(fill="x", padx=10, pady=(0, 4))

    def _colour(self, parent, key, label, options, hint=""):
        """A colour, picked by name or typed as a hex.

        A closed list of names on its own would throw away a colour
        somebody had already hand-edited into settings.json - and being
        made to hand-edit it is the thing this control exists to fix, not
        a thing to punish. So an unrecognised value survives the trip.
        """
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row, text=label, width=250, anchor="w",
                     font=F_BODY, text_color=TEXT).pack(side="left")
        # The swatch takes its pixels BEFORE the box is allowed to expand.
        # The other way round the box eats the row and the swatch is never
        # laid out at all.
        patch = ctk.CTkFrame(row, width=34, height=26, fg_color=ORANGE,
                             corner_radius=0, border_width=1,
                             border_color=RULE)
        patch.pack(side="right", padx=(8, 0))
        patch.pack_propagate(False)
        box = ctk.CTkComboBox(row, values=[name for name, _v in options],
                              font=F_BODY, height=30, **BOX,
                              command=lambda _v, k=key: self._show_colour(k))
        box.pack(side="left", fill="x", expand=True)
        self.colours[key] = (box, list(options), patch)
        if hint:
            ctk.CTkLabel(parent, text=hint, font=F_SMALL,
                         text_color=DIM, justify="left", anchor="w",
                         wraplength=560).pack(fill="x", padx=10, pady=(0, 4))

    def _show_colour(self, key):
        """Paint the swatch with whatever the box says now."""
        entry = self.colours.get(key)
        if not entry:
            return
        box, options, patch = entry
        chosen = box.get().strip()
        value = next((v for name, v in options if name == chosen), chosen)
        try:
            patch.configure(fg_color=value if is_colour(value) else ORANGE)
        except Exception:
            pass

    def _binding(self, parent, key, label, fallback):
        """A key binding you set by pressing the key, like the game does.

        Typing a key name into a box was the old way and it was a trap:
        anything unrecognised was accepted, saved, and then bound nothing
        at all. It also only ever understood F1-F12, so a commander whose
        function row is taken by the game - or sends media keys unless Fn
        is held - had nowhere to go.
        """
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row, text=label, width=250, anchor="w",
                     font=F_BODY, text_color=TEXT).pack(side="left")
        # Clear is packed first so it keeps its width when the window is
        # narrow; the button that expands has to come last or it pushes
        # everything after it off the edge.
        ctk.CTkButton(row, text="Reset", width=68, height=30,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=lambda: self._set_binding(key, fallback)
                      ).pack(side="right", padx=(6, 0))
        button = ctk.CTkButton(row, text=fallback, height=30,
                               font=F_STRONG, **BTN_SECONDARY,
                               command=lambda: self._capture(key))
        button.pack(side="left", fill="x", expand=True)
        self.binders[key] = button
        self.bindings[key] = fallback

    def _set_binding(self, key, value):
        self.bindings[key] = value
        button = self.binders.get(key)
        if button is not None:
            button.configure(text=value, **BTN_SECONDARY)

    def _capture(self, key):
        """Listen for one key press, then stop listening.

        Binding every widget at once is forbidden by customtkinter, so
        this binds the window
        itself and unbinds it the moment a key lands. A capture left armed
        would eat every keystroke in Settings.
        """
        if self._capturing:
            return
        self._capturing = key
        button = self.binders.get(key)
        if button is not None:
            button.configure(text="press a key...", **BTN_WARN)
        self.say("Press the key you want, with Ctrl, Alt or Shift if you "
                 "like. Escape cancels.", AMBER)
        try:
            self._capture_id = self.bind("<KeyPress>", self._captured)
            self.focus_force()
        except Exception:
            self._release_capture()

    def _captured(self, event):
        key = self._capturing
        if not key:
            return
        if str(getattr(event, "keysym", "")).lower() == "escape":
            self._release_capture()
            self._set_binding(key, self.bindings.get(key, ""))
            return self.say("Left as it was.")
        chosen = binding_from_event(event)
        if chosen is None:
            # A modifier on its own is somebody still reaching for the key.
            # Anything else genuinely cannot be bound, and has to say so.
            if str(getattr(event, "keysym", "")).lower() not in BARE_MODIFIERS:
                self.say("EDSMT cannot bind that key. Try another.", RED)
            return
        clash = [other for other, value in self.bindings.items()
                 if other != key and value == chosen]
        self._release_capture()
        if clash:
            return self.say("%s is already doing something else in EDSMT."
                            % chosen, RED)
        self._set_binding(key, chosen)
        who = key_clash(chosen)
        if who:
            # Allowed - the other program may be off on this machine - but
            # said, because when it is on it takes the key first and EDSMT
            # never hears it. Alt+F1 went to an NVIDIA screenshot that way.
            return self.say("%s is also %s by default - if that is running it "
                            "gets the key first. Save to keep it anyway, or "
                            "click and press another." % (key_text(chosen), who),
                            AMBER)
        self.say("%s it is. Save to keep it." % key_text(chosen), GREEN)

    def _release_capture(self):
        if self._capture_id is not None:
            try:
                self.unbind("<KeyPress>", self._capture_id)
            except Exception:
                pass
        self._capture_id = None
        self._capturing = None

    def load(self):
        data = self.app.settings
        # Anything reloaded goes back to dots, whatever was shown before.
        self.hide_secrets()
        for key, var in self.toggles.items():
            var.set(bool(data.get(key, DEFAULT_SETTINGS.get(key, False))))
        for key, entry in self.fields.items():
            entry.delete(0, "end")
            value = data.get(key, DEFAULT_SETTINGS.get(key, ""))
            # 3950.0 reads as something other than what was typed; a whole
            # number is shown whole.
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            if value not in (None, ""):
                entry.insert(0, str(value))
        for key, (box, options) in self.choices.items():
            current = str(data.get(key, DEFAULT_SETTINGS.get(key, "")) or "")
            box.set(next((name for name, value in options if value == current),
                         options[0][0]))
        for key, (box, options, _patch) in self.colours.items():
            current = str(data.get(key, DEFAULT_SETTINGS.get(key, "")) or "")
            # An unrecognised value shows as itself rather than snapping
            # back to the first name in the list and silently losing it.
            box.set(next((name for name, value in options if value == current),
                         current or options[0][0]))
            self._show_colour(key)
        # The bindings were seeded with the hardcoded fallback when the row
        # was built and load() never touched them again, so Settings showed
        # F9/F10 whatever you had bound - and save() wrote that lie back.
        # Opening Settings to change the opacity threw your hotkeys away.
        for key in list(self.binders):
            self._set_binding(key, str(data.get(key)
                                       or DEFAULT_SETTINGS.get(key, "")))
        # Whether the keys actually took. Hotkeys.problem was computed in
        # five places and read in none, and this label was built, packed,
        # and never written to - so a key the game already owns failed in
        # total silence. That is the bug a beta tester reported.
        note = attr(self, "hotkey_note")
        if note is not None:
            hotkeys = getattr(self.app, "hotkeys", None)
            trouble = getattr(hotkeys, "problem", "") if hotkeys else ""
            bound = len(getattr(hotkeys, "bound", {}) or {}) if hotkeys else 0
            if trouble:
                note.configure(text=trouble, text_color=RED)
            elif hotkeys is not None and getattr(hotkeys, "active", False):
                note.configure(text="All %d keys are live." % bound
                               if bound else "The keys are live.",
                               text_color=GREEN)
            else:
                note.configure(text="", text_color=DIM)
        self.say("")

    def save(self):
        data = dict(self.app.settings)
        for key, var in self.toggles.items():
            data[key] = bool(var.get())
        for key, (box, options) in self.choices.items():
            chosen = box.get().strip()
            data[key] = next((value for name, value in options
                              if name == chosen), options[0][1])
        for key, (box, options, _patch) in self.colours.items():
            chosen = box.get().strip()
            value = next((v for name, v in options if name == chosen), chosen)
            if not is_colour(value):
                return self.say("%s is not a colour. Pick one from the list "
                                "or type a hex like #ff7a18." % (chosen or "That"),
                                RED)
            data[key] = value
        for key, entry in self.fields.items():
            data[key] = entry.get().strip()

        url = data.get("community_url", "")
        if url and not url.startswith(("http://", "https://")):
            return self.say("The community URL needs to start with https://", RED)
        try:
            half = float(data.get("freshness_half_life_days") or 21)
            if half <= 0:
                raise ValueError
            data["freshness_half_life_days"] = half
        except ValueError:
            return self.say("Freshness half-life must be a number of days.", RED)
        warn = parse_metres(data.get("rig_warn_m"))
        if warn is None:
            return self.say("The rig warning distance must be a distance - "
                            "3500, 3,500, 3500 m or 3.5 km all work. 0 turns "
                            "it off.", RED)
        data["rig_warn_m"] = warn
        spacing = parse_metres(data.get("rig_spacing_m") or RP.RIG_SPACING_M)
        if spacing is None or not PLAN_SPACING_MIN_M <= spacing <= PLAN_SPACING_MAX_M:
            return self.say("The rig planner's spacing must be a distance "
                            "between %d and %d m - 78 is the community's "
                            "figure." % (PLAN_SPACING_MIN_M, PLAN_SPACING_MAX_M),
                            RED)
        data["rig_spacing_m"] = spacing
        raw_code = str(data.get("wing_code") or "").strip()
        code = clean_wing_code(raw_code)
        if raw_code and not code:
            return self.say("A wing code is six letters and digits - "
                            "everyone in the wing types the same one.", RED)
        if data.get("wing_link") and not code:
            return self.say("The wing link needs a code. Make a new one and "
                            "read it out to the rest of your wing.", RED)
        data["wing_code"] = code
        try:
            data["high_g_warn"] = max(0.0, float(
                str(data.get("high_g_warn") or "0").lower().replace("g", "")
                .strip() or 0))
        except ValueError:
            return self.say("The gravity warning must be a number of g - "
                            "2 or 2.5 work. 0 turns it off.", RED)
        # Bindings come from the capture buttons, not from typed text, so
        # the only thing left to check is that they still parse and do not
        # collide with each other.
        for key, value in self.bindings.items():
            value = str(value or "").strip()
            if value and parse_binding(value) is None:
                return self.say("%s is not a key EDSMT can bind. Click it "
                                "and press another." % value, RED)
            data[key] = value
        # Every binding against every other, not just the first two. A third
        # key was added and a pairwise check would have let it collide with
        # either of them in silence.
        taken = {}
        for key, value in self.bindings.items():
            value = str(data.get(key) or "").strip()
            if not value:
                continue
            if value in taken:
                return self.say("%s is bound to two things at once." % value, RED)
            taken[value] = key
        folder = data.get("journal_dir", "")
        if folder and not os.path.isdir(folder):
            return self.say("That folder does not exist.", RED)

        # Overlay numbers are clamped rather than rejected: a silly width is a
        # typo, not a reason to lose everything else typed on this screen.
        try:
            data["overlay_opacity"] = max(
                0.2, min(1.0, float(data.get("overlay_opacity") or 0.88)))
            # Width and height may be left blank, which means "fit my
            # screen" - so 0 has to survive the clamp rather than being
            # rounded up to a number that is wrong on half the machines.
            for key, low, high in (("overlay_width", 240, 6000),
                                   ("overlay_height", 70, 1200)):
                raw = str(data.get(key) or "").strip()
                data[key] = 0 if not raw else max(low, min(high, int(float(raw))))
            for key, low, high, fallback in (("overlay_span_deg", 30, 360, 120),
                                             ("overlay_targets", 1, 20, 6)):
                data[key] = max(low, min(high,
                                         int(float(data.get(key) or fallback))))
        except ValueError:
            return self.say("Overlay size, span and opacity must be numbers.", RED)

        self.app.apply_settings(data)
        warn = data.get("rig_warn_m") or 0
        theme = ""
        if str(data.get("app_theme") or "cockpit") != \
                str(attr(self.app, "theme_worn", "cockpit")):
            theme = " The app theme is worn from the next start - Save and " \
                    "restart now does it."
        self.say("Saved. Live now. %s%s" % (
            ("Rig warning at %s." % _metres(warn)) if warn
            else "Rig warning off.", theme), GREEN)
        self._saved_ok = True
        # Show the distance back as it was understood, whole metres.
        box = self.fields.get("rig_warn_m")
        if box is not None:
            box.delete(0, "end")
            box.insert(0, "%d" % round(float(warn)))

    def test(self):
        notes = []
        if self.app.community.ready:
            self.app.community.sites(limit=1)
            notes.append("asked the community server for a site")
        if self.app.inara.ready:
            self.app.inara.verify()
            notes.append("asked Inara to check the key")
        elif self.toggles["inara_enabled"].get():
            notes.append("Inara needs a key and a running game")
        notes.append(self.app.watcher.diagnosis())
        self.say("  |  ".join(notes))

    def save_and_restart(self):
        """Save, then start EDSMT again so a new app theme is worn."""
        self._saved_ok = False
        self.save()
        if self._saved_ok:
            self.app.restart_app()

    def reset_boxes(self):
        """Settings' handle on the app's layout reset."""
        self.app.reset_overlay_layout()
        self.say("Overlay boxes are back where they started.", GREEN)

    def backup_now(self):
        try:
            from tkinter import filedialog
            folder = filedialog.askdirectory(
                parent=self, title="Where should the backup go?",
                initialdir=os.path.expanduser("~"))
        except Exception:
            folder = DATA_DIR
        if not folder:
            return
        try:
            path, count = self.app.store.backup_to(folder)
        except OSError as problem:
            return self.say("Could not write the backup: %s" % problem, RED)
        if not path:
            return self.say("Nothing to back up yet.", AMBER)
        self.say("Backed up %d file(s) to %s" % (count, path), GREEN)

    def restore_now(self):
        try:
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                parent=self, title="Which backup?",
                filetypes=[("EDSMT backup", "*.zip")],
                initialdir=os.path.expanduser("~"))
        except Exception:
            path = ""
        if not path:
            return
        try:
            restored = self.app.store.restore_from(path)
        except Exception as problem:
            return self.say("That does not look like an EDSMT backup: %s"
                            % problem, RED)
        if not restored:
            return self.say("There was nothing in that backup.", AMBER)
        self.app.refresh_locations()
        # The deposit list was the one view left showing the old database.
        self.app.refresh_deposits()
        self.app.refresh_commodities()
        self.app.redraw()
        self.say("Restored %d file(s). Anything that was here was kept "
                 "alongside, renamed." % restored, GREEN)

    def import_now(self):
        """Take another tool's CSV, without being told which tool wrote it.

        Both files are called surfaceminingmap.csv, so asking would be
        asking the commander to know something the header already says.
        """
        try:
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                parent=self, title="Which CSV?",
                filetypes=[("Surface mining CSV", "*.csv"),
                           ("Any file", "*.*")],
                initialdir=os.path.expanduser("~"))
        except Exception:
            path = ""
        if not path:
            return
        try:
            result = import_finds(self.app.store, path)
        except Exception as problem:
            return self.say("Could not import that file: %s" % problem, RED)
        self.say(import_summary(result), GREEN if result["ok"] else AMBER)
        if not result["ok"]:
            return
        # Every view, not just the deposit list. An import can add a body
        # this commander has never been to, which changes the signal list
        # and the commodity box as much as it changes the map.
        self.app.refresh_locations()
        self.app.refresh_deposits()
        self.app.refresh_commodities()
        self.app.redraw()

    def paste_shared(self):
        """Add the finds in the lines pasted into the box (1.10032: the box,
        not the clipboard - nothing is read that you have not put there)."""
        box = attr(self, "paste_box")
        try:
            text = box.get("1.0", "end") if box is not None else ""
        except Exception:
            text = ""
        if not str(text or "").strip():
            return self.say("Paste the shared lines into the box first, then "
                            "press Import.", AMBER)
        try:
            result = take_share_lines(self.app.store, text)
        except Exception as problem:
            return self.say("Could not add those: %s" % problem, RED)
        self.say(share_summary(result), GREEN if result["taken"] else AMBER)
        if result["taken"] or result.get("duplicates"):
            try:
                box.delete("1.0", "end")
            except Exception:
                pass
        if result["taken"]:
            self.app.refresh_locations()
            self.app.refresh_deposits()
            self.app.refresh_commodities()
            self.app.redraw()
        return result

    def check_updates(self):
        """Ask now, and report the answer whichever way it goes."""
        try:
            self.app.say("Checking for updates...")
            self.app.updates.check(APP_VERSION, force=True)
        except Exception as exc:
            self.app.say("Could not check for updates: %s" % exc, RED)

    def open_data_folder(self):
        try:
            if os.name == "nt":
                os.startfile(DATA_DIR)                    # noqa: S606
            else:
                import subprocess
                subprocess.Popen(["xdg-open", DATA_DIR])
            self.say(DATA_DIR)
        except Exception:
            self.say(DATA_DIR, AMBER)

    def say(self, text, colour=None):
        colour = colour or DIM
        self.status.configure(text=text, text_color=colour)


# ---------------------------------------------------------------------------
# Fixing one you got wrong
# ---------------------------------------------------------------------------

class WelcomeWindow(ctk.CTkToplevel):
    """The share question, asked once, on first run.

    Every commander running EDSMT is a surveyor. Surface deposits are not
    ring hotspots - nobody has mapped them, there is no third-party database
    to look them up in, and one person mapping alone will never cover a
    galaxy. The tool is only worth more than a notepad if the finds pool.

    So the question gets asked plainly rather than left as a switch in
    Settings that nobody finds. It is still a question: the answer sticks
    either way, and No changes nothing about how the tool works locally.
    """

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("EDSMT - Share your finds?")
        self.geometry("560x440")
        self.configure(fg_color=VOID)
        self.transient(app)
        self.resizable(False, False)

        body = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        body.pack(fill="both", expand=True, padx=12, pady=12)
        bracket(body, colour=ORANGE)

        ctk.CTkLabel(body, text="Map together?", font=F_TITLE,
                     text_color=ORANGE, anchor="w").pack(fill="x", padx=16, pady=(16, 2))
        ctk.CTkLabel(body, anchor="w", justify="left", text_color=TEXT,
                     font=F_READOUT, wraplength=490,
                     text="Every commander who shares makes the map better "
                          "for everyone else.\n\nWith sharing on, what you map "
                          "goes to the community map, and Find searches "
                          "everyone else's. "
                          "One commander cannot cover a galaxy; a few thousand "
                          "can.").pack(fill="x", padx=16, pady=(6, 10))

        hud_header(body, "What gets sent", padx=16, pady=(6, 4))
        ctk.CTkLabel(body, anchor="w", justify="left", text_color=DIM,
                     font=F_BODY, wraplength=490,
                     text="System, body, commodity, position and how rich it "
                          "was - and your CMDR name, so the find is credited "
                          "to you. That last part is a switch in Settings.\n"
                          "Not your notes, not your settings, not anything "
                          "else on this machine.").pack(fill="x", padx=16, pady=(0, 14))

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(4, 12))
        ctk.CTkButton(row, text="Share my finds", width=190, height=40,
                      font=F_SECTION, **BTN_PRIMARY,
                      command=lambda: self.answer(True)).pack(side="left")
        ctk.CTkButton(row, text="Not now", width=130, height=40,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=lambda: self.answer(False)).pack(side="left", padx=10)

        ctk.CTkLabel(body, anchor="w", text_color=DIM, font=F_SMALL,
                     text="Either way it is in Settings, and you can change "
                          "your mind whenever.").pack(fill="x", padx=16, pady=(0, 8))

        try:
            self.grab_set()
        except Exception:
            pass

    def answer(self, wanted):
        try:
            self.app.set_sharing(wanted)
        finally:
            self.destroy()


class EditLocationWindow(ctk.CTkToplevel):
    """Correct or remove a mining location signal.

    F9 is pressed with the game in front of you and the signal number comes
    off a dropdown, so logging signal 2 when you meant 3 is a one-key
    mistake. Until now there was no way back from it: locations could be
    written and never unwritten, which left wrong numbers on the map for
    good.

    Renumbering moves the deposits with it. Deleting does not delete them -
    they were real places somebody drove to, and the window says how many
    are about to be left unattached rather than quietly orphaning them.
    """

    def __init__(self, app, row):
        super().__init__(app)
        self.app = app
        self.row_id = row["id"]
        self.system = row["system"]
        self.body = row["body"]
        self.original = str(row["location"])
        self.title("EDSMT - Edit signal %s" % self.original)
        self.configure(fg_color=VOID)
        self.transient(app)

        attached = len(app.store.at(self.system, self.body, self.original))

        # Bottom first, for the same reason as the deposit editor: packed
        # last, the buttons are the first thing a long name pushes away.
        self.status = ctk.CTkLabel(self, text="", font=F_READOUT,
                                   text_color=DIM, anchor="w", wraplength=460,
                                   justify="left")
        self.status.pack(side="bottom", fill="x", padx=14, pady=(0, 10))
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(side="bottom", fill="x", padx=12, pady=(0, 6))
        ctk.CTkButton(buttons, text="Save", width=110, height=32,
                      font=F_STRONG, **BTN_PRIMARY,
                      command=self.save).pack(side="left", padx=(0, 8))
        self.delete_button = ctk.CTkButton(buttons, text="Delete", width=110,
                                           height=32, font=F_STRONG,
                                           **BTN_DANGER,
                                           command=self.remove)
        self.delete_button.pack(side="left", padx=8)
        ctk.CTkButton(buttons, text="Cancel", width=90, height=32,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.destroy).pack(side="right")

        body_frame = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        body_frame.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        bracket(body_frame, colour=ORANGE)

        hud_header(body_frame, "Signal %s" % self.original, padx=12,
                   pady=(14, 4))
        ctk.CTkLabel(body_frame, text="%s\n%s" % (self.system, self.body),
                     font=F_HEAD, text_color=TEXT, justify="left",
                     wraplength=440, anchor="w").pack(fill="x", padx=12,
                                                      pady=(2, 2))
        ctk.CTkLabel(body_frame,
                     text="%d deposit%s recorded under this signal."
                          % (attached, "" if attached == 1 else "s"),
                     font=F_BODY, text_color=DIM,
                     anchor="w").pack(fill="x", padx=12, pady=(0, 10))

        number_row = ctk.CTkFrame(body_frame, fg_color="transparent")
        number_row.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(number_row, text="Signal", width=86, anchor="w",
                     font=F_BODY, text_color=TEXT).pack(side="left")
        self.number = ctk.CTkComboBox(number_row, values=app.signal_choices(),
                                      font=F_BODY, height=30, **BOX)
        self.number.set(self.original)
        self.number.pack(side="left", fill="x", expand=True)
        Suggest(self.number, app.signal_choices())
        ctk.CTkLabel(body_frame,
                     text="Changing this moves its deposits too.",
                     font=F_SMALL, text_color=DIM,
                     anchor="w").pack(fill="x", padx=12, pady=(0, 8))

        ctk.CTkLabel(body_frame, text="What it offers", anchor="w",
                     font=F_BODY,
                     text_color=TEXT).pack(fill="x", padx=12, pady=(4, 2))
        self.offers = ctk.CTkTextbox(body_frame, height=80, font=F_BODY,
                                     **TEXTBOX)
        self.offers.pack(fill="x", padx=12)
        self.offers.insert("1.0", ", ".join(app.store.offered(row)))
        ctk.CTkLabel(body_frame,
                     text="Comma separated, as the game names them. Blank is "
                          "fine - plenty of signals never list anything.",
                     font=F_SMALL, text_color=DIM, justify="left",
                     wraplength=440,
                     anchor="w").pack(fill="x", padx=12, pady=(6, 12))
        fit_to_content(self, 500, 460)

    def save(self):
        wanted = self.number.get().strip()
        if not wanted:
            return self.say("A signal needs a number.", RED)
        offers = [part.strip() for part in
                  self.offers.get("1.0", "end").replace("\n", ",").split(",")]
        offers = [SV.remember(name) for name in offers if name]
        if self.app.location_edited(self.row_id, self.system, self.body,
                                    self.original, wanted, offers):
            self.destroy()

    def remove(self):
        """Two presses, and the second one says what it will leave behind."""
        attached = len(self.app.store.at(self.system, self.body, self.original))
        if not attr(self, "_armed", False):
            self._armed = True
            self.delete_button.configure(text="Press again", fg_color=RED,
                                         hover_color=RED, text_color=VOID)
            if attached:
                return self.say("That forgets signal %s. Its %d deposit%s stay "
                                "on the map. Press again."
                                % (self.original, attached,
                                   "" if attached == 1 else "s"), AMBER)
            return self.say("That forgets signal %s. Press again."
                            % self.original, AMBER)
        self.app.delete_location(self.row_id)
        self.destroy()

    def say(self, text, colour=None):
        colour = colour or DIM
        self.status.configure(text=text, text_color=colour)


class EditWindow(ctk.CTkToplevel):
    """Correct a deposit after the fact.

    Marking a deposit is one keypress with the game in front of you, which is
    the whole point - but it also means the commodity or the signal number can
    be whatever the boxes happened to say at that moment. This is where that
    gets fixed, without going near a CSV.

    Position and time are shown but not editable. They came from the game and
    are the one part that cannot be wrong in a way typing would fix; if a
    deposit really is in the wrong place, delete it and mark it again.
    """

    def __init__(self, app, deposit):
        super().__init__(app)
        self.app = app
        self.deposit_id = deposit["id"]
        self.title("EDSMT - Edit deposit")
        self.configure(fg_color=VOID)
        self.transient(app)

        # The buttons and the status line claim the bottom FIRST. Packed
        # after the form they were the first thing to be pushed off the
        # window, and a Save you cannot see is a Save you cannot press.
        self.status = ctk.CTkLabel(self, text="", font=F_READOUT,
                                   text_color=DIM, anchor="w", wraplength=460,
                                   justify="left")
        self.status.pack(side="bottom", fill="x", padx=14, pady=(0, 10))
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(side="bottom", fill="x", padx=12, pady=(0, 6))
        ctk.CTkButton(buttons, text="Save", width=110, height=32,
                      font=F_STRONG, **BTN_PRIMARY,
                      command=self.save).pack(side="left", padx=(0, 8))
        self.delete_button = ctk.CTkButton(buttons, text="Delete", width=110,
                                           height=32, font=F_STRONG,
                                           **BTN_DANGER,
                                           command=self.remove)
        self.delete_button.pack(side="left", padx=8)
        ctk.CTkButton(buttons, text="Cancel", width=90, height=32,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.destroy).pack(side="right")

        body = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        body.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        bracket(body, colour=ORANGE)

        hud_header(body, "Correct a deposit", padx=12, pady=(14, 4))
        # System and body on their own lines. On one line a long body name
        # ran off the right-hand edge and simply stopped.
        ctk.CTkLabel(body, text="%s\n%s" % (deposit.get("system") or "?",
                                            deposit.get("body") or "?"),
                     font=F_HEAD, text_color=TEXT, justify="left",
                     wraplength=440, anchor="w").pack(fill="x", padx=12,
                                                      pady=(2, 0))

        where = "recorded %s" % (deposit.get("recorded") or "")[:19].replace("T", " ")
        if deposit.get("lat") and deposit.get("lon"):
            where = "%s, %s   %s" % (deposit["lat"], deposit["lon"], where)
        ctk.CTkLabel(body, text=where, font=F_SMALL, text_color=DIM,
                     anchor="w").pack(fill="x", padx=12, pady=(0, 8))

        self.boxes = {}
        self._row(body, "location", "Signal", self.app.signal_choices(),
                  deposit.get("location", ""))
        self._row(body, "commodity", "Commodity", list(SV.KNOWN_COMMODITIES),
                  deposit.get("commodity", ""))
        self._row(body, "rigs", "Rigs",
                  [""] + [str(n) for n in range(1, MAX_RIGS + 1)],
                  deposit.get("rigs", ""))
        # Same order as the rail, so correcting a deposit looks like recording
        # one. Two screens that ask the same questions in different orders is
        # how a wrong value gets typed into the right-looking box.
        self._row(body, "amount", "Amount", [""] + AMOUNT_LEVELS,
                  deposit.get("amount", ""))
        self._row(body, "density", "Density", [""] + DENSITY_LEVELS,
                  deposit.get("density", ""))

        note_row = ctk.CTkFrame(body, fg_color="transparent")
        note_row.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(note_row, text="Notes", width=86, anchor="w",
                     font=F_BODY, text_color=DIM).pack(side="left")
        self.notes = ctk.CTkTextbox(note_row, font=F_BODY, height=74,
                                    wrap="word", **TEXTBOX)
        self.notes.pack(side="left", fill="x", expand=True)
        if deposit.get("notes"):
            self.notes.insert("1.0", deposit["notes"])
        chain_tab([self.boxes[k] for k in ("location", "commodity", "rigs",
                                           "amount", "density")])

        ctk.CTkLabel(body, text="Every box is typeable. A commodity the game "
                               "named that is not in the list still goes in.",
                     font=F_SMALL, text_color=DIM, justify="left",
                     wraplength=440, anchor="w").pack(fill="x", padx=12,
                                                      pady=(8, 12))
        fit_to_content(self, 500, 480)

    def _row(self, parent, key, label, values, current):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row, text=label, width=86, anchor="w",
                     font=F_BODY, text_color=TEXT).pack(side="left")
        # A value already recorded but not in the list would otherwise vanish
        # the moment the box is built, which is how an edit silently deletes
        # the thing it was opened to correct.
        offered = list(values)
        if current and str(current) not in offered:
            offered.insert(0, str(current))
        box = ctk.CTkComboBox(row, values=offered, font=F_BODY,
                              height=30, **BOX)
        box.set(str(current) if current else "")
        box.pack(side="left", fill="x", expand=True)
        self.boxes[key] = box
        Suggest(box, offered)

    def save(self):
        changes = {key: box.get().strip() for key, box in self.boxes.items()}
        changes["notes"] = self.notes.get("1.0", "end").strip()

        if not changes["location"]:
            return self.say("A deposit has to belong to a signal.", RED)
        if changes["rigs"]:
            try:
                rigs = int(float(changes["rigs"]))
            except ValueError:
                return self.say("Rigs must be a number, or blank.", RED)
            if not 0 <= rigs <= MAX_RIGS:
                return self.say("The Rhino carries %d rigs." % MAX_RIGS, RED)
            changes["rigs"] = str(rigs)
        if changes["commodity"]:
            changes["commodity"] = SV.remember(changes["commodity"])

        if self.app.deposit_edited(self.deposit_id, changes):
            self.destroy()

    def remove(self):
        """Two presses, not a confirmation dialogue.

        A modal box on top of a game is a good way to lose a window behind
        the game and wonder why nothing responds. Arming the button instead
        keeps the whole thing inside this window.
        """
        if not attr(self, "_armed", False):
            self._armed = True
            self.delete_button.configure(text="Press again", fg_color=RED,
                                         hover_color=RED, text_color=VOID)
            return self.say("That deletes this deposit. Press it again to "
                            "go through with it.", AMBER)
        self.app.delete_deposit(self.deposit_id)
        self.destroy()

    def say(self, text, colour=None):
        colour = colour or DIM
        self.status.configure(text=text, text_color=colour)


# ---------------------------------------------------------------------------
# Find
# ---------------------------------------------------------------------------

# How many suggestions show before the list scrolls.
SUGGEST_ROWS = 9


class Suggest:
    """A list that opens under a box the moment you click or type in it.

    The toolkit's own dropdown only opens from its arrow, and when it is
    open it takes the keyboard - so it could not be opened while typing
    without eating the keys being typed. This one never takes focus: the
    box keeps the keyboard, the list follows what is typed, and

        Down / Up        move through the list
        Enter or Tab     take the highlighted one (Tab then moves on)
        Escape           close it
        a click          take that one

    `source` is a list, or a function taking what has been typed and giving
    back what to show. `on_pick` runs after a choice is made.
    """

    def __init__(self, box, source, on_pick=None, filter_typing=True):
        self.box = box
        self.source = source
        self.on_pick = on_pick
        self.filter_typing = filter_typing
        self.popup = None
        self.listbox = None
        self._hide_job = None
        # Whether the commander has typed or arrowed in this box since
        # arriving in it. Until they have, the list shows everything and
        # Tab changes nothing - tabbing THROUGH a box must never fill it.
        self._engaged = False
        self._hushed = False
        self.entry = getattr(box, "_entry", None) or box
        # Kept on the box, so whatever owns the box can reach its list.
        try:
            box.suggest = self
        except Exception:
            pass
        for sequence, handler in (("<FocusIn>", self._focus_in),
                                  ("<FocusOut>", self._focus_out),
                                  ("<KeyRelease>", self._typed),
                                  ("<Down>", self._down),
                                  ("<Up>", self._up),
                                  ("<Return>", self._enter),
                                  ("<KP_Enter>", self._enter),
                                  ("<Tab>", self._tab),
                                  ("<Escape>", self._escape),
                                  ("<Button-1>", self._clicked)):
            self.entry.bind(sequence, handler, add="+")

    # -- what to show ------------------------------------------------------

    def choices(self):
        typed = self.text() if (self._engaged and self.filter_typing) else ""
        try:
            if callable(self.source):
                names = list(self.source(typed))
            else:
                names = list(self.source)
        except Exception:
            names = []
        if typed and not callable(self.source):
            names = SV.matches(names, typed)
        # A blank line in a list of choices is a way of saying "none"; it
        # stays selectable in the box but is noise in a suggestion list.
        return [n for n in names if str(n).strip()]

    def text(self):
        try:
            return self.box.get().strip()
        except Exception:
            return ""

    # -- the popup ---------------------------------------------------------

    def show(self):
        names = self.choices()
        if not names:
            return self.hide()
        if self.popup is None or not self._alive():
            self._build()
        box = self.box
        try:
            box.update_idletasks()
            x = box.winfo_rootx()
            y = box.winfo_rooty() + box.winfo_height()
            width = max(box.winfo_width(), 160)
            rows = min(len(names), SUGGEST_ROWS)
            self.listbox.configure(height=rows)
            self.listbox.delete(0, "end")
            for name in names:
                self.listbox.insert("end", " " + str(name))
            typed = self.text()
            chosen = 0
            for index, name in enumerate(names):
                if str(name) == typed:
                    chosen = index
                    break
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(chosen)
            self.listbox.see(chosen)
            self.popup.update_idletasks()
            height = self.listbox.winfo_reqheight()
            # Opens upward when there is no room below - the rail's boxes sit
            # at the bottom of the window.
            if y + height > box.winfo_screenheight():
                y = box.winfo_rooty() - height
            self.popup.geometry("%dx%d+%d+%d" % (width, height, x, y))
            self.popup.deiconify()
            self.popup.lift()
        except Exception:
            self.hide()

    def _build(self):
        top = self.box.winfo_toplevel()
        self.popup = tk.Toplevel(top)
        self.popup.withdraw()
        self.popup.overrideredirect(True)
        try:
            self.popup.transient(top)
            self.popup.attributes("-topmost", True)
        except Exception:
            pass
        self.listbox = tk.Listbox(
            self.popup, bg=PANEL, fg=TEXT, font=F_BODY, bd=1,
            relief="solid", highlightthickness=1, highlightcolor=ORANGE,
            highlightbackground=RULE, selectbackground=ORANGE,
            selectforeground=VOID, activestyle="none", exportselection=False,
            takefocus=0)
        self.listbox.pack(fill="both", expand=True)
        self.listbox.bind("<ButtonRelease-1>", self._list_clicked)
        self.listbox.bind("<Motion>", self._hover)
        # The window moving would leave the list floating where it was.
        try:
            top.bind("<Configure>", lambda _e: self.hide(), add="+")
        except Exception:
            pass

    def _alive(self):
        try:
            return bool(self.popup.winfo_exists())
        except Exception:
            return False

    def visible(self):
        try:
            return self._alive() and bool(self.popup.winfo_viewable())
        except Exception:
            return False

    def hide(self, _event=None):
        if self.popup is not None and self._alive():
            try:
                self.popup.withdraw()
            except Exception:
                pass

    def pick(self, name):
        try:
            self.box.set(str(name).strip())
        except Exception:
            return
        self.hide()
        if self.on_pick is not None:
            try:
                self.on_pick(str(name).strip())
            except Exception:
                pass

    def highlighted(self):
        if not self.visible():
            return None
        try:
            chosen = self.listbox.curselection()
            if chosen:
                return self.listbox.get(chosen[0]).strip()
        except Exception:
            pass
        return None

    # -- keys and clicks -----------------------------------------------------

    def _focus_in(self, _event=None):
        self._cancel_hide()
        self._engaged = False
        if self._hushed:
            self._hushed = False
            return self.hide()
        self.show()

    def hush(self):
        """Close the list, and keep it closed through the focus coming back
        - a choice was just made some other way."""
        self._hushed = True
        self._cancel_hide()
        self.hide()

    def _clicked(self, _event=None):
        self._cancel_hide()
        self.box.after(1, self.show)

    def _focus_out(self, _event=None):
        # Late, so a click on the list lands before the list goes away.
        self._cancel_hide()
        try:
            self._hide_job = self.box.after(180, self.hide)
        except Exception:
            self.hide()

    def _cancel_hide(self):
        if self._hide_job is not None:
            try:
                self.box.after_cancel(self._hide_job)
            except Exception:
                pass
            self._hide_job = None

    def _typed(self, event=None):
        key = getattr(event, "keysym", "")
        if key in ("Up", "Down", "Return", "KP_Enter", "Tab", "Escape",
                   "ISO_Left_Tab", "Shift_L", "Shift_R", "Control_L",
                   "Control_R", "Alt_L", "Alt_R"):
            return
        self._engaged = True
        self.show()

    def _move(self, step):
        self._engaged = True
        if not self.visible():
            self.show()
            return "break"
        try:
            size = self.listbox.size()
            if not size:
                return "break"
            chosen = self.listbox.curselection()
            index = (chosen[0] + step) if chosen else 0
            index = max(0, min(size - 1, index))
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(index)
            self.listbox.see(index)
        except Exception:
            pass
        return "break"

    def _down(self, _event=None):
        return self._move(1)

    def _up(self, _event=None):
        return self._move(-1)

    def _enter(self, _event=None):
        name = self.highlighted()
        if name is not None:
            self.pick(name)
            return "break"
        return None

    def _tab(self, _event=None):
        # Take the highlighted one, then let Tab carry on to the next box.
        name = self.highlighted()
        if self._engaged and name is not None and name != self.text():
            self.pick(name)
        self.hide()
        return None

    def _escape(self, _event=None):
        if self.visible():
            self.hide()
            return "break"
        return None

    def _list_clicked(self, event=None):
        """Take the one clicked, give the keyboard back to the box, and keep
        the list SHUT.

        Clicking the list moves the focus onto it; handing the focus back to
        the box then fired FocusIn, and FocusIn opens the list - so a
        commodity typed and clicked left its list hanging open over the
        rail. The hush is what FocusIn checks first.
        """
        try:
            index = self.listbox.nearest(event.y)
            name = self.listbox.get(index)
        except Exception:
            return
        self.pick(name)
        self._hushed = True
        try:
            self.entry.focus_set()
        except Exception:
            pass
        # If the box never lost the focus there is no FocusIn to spend the
        # hush on, and it must not linger to swallow the next real one.
        try:
            self.box.after(300, self._unhush)
        except Exception:
            self._hushed = False

    def _unhush(self):
        self._hushed = False

    def _hover(self, event=None):
        try:
            index = self.listbox.nearest(event.y)
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(index)
        except Exception:
            pass


def keep_keyboard(box):
    """After a pick from a box's own arrow list: the keyboard stays in that
    box, and its type-ahead list stays shut, so the next key is Tab to the
    next box rather than a list re-opening over it."""
    suggest = getattr(box, "suggest", None)
    if suggest is not None:
        suggest.hush()
    entry = getattr(box, "_entry", None) or box
    try:
        entry.focus_set()
        entry.icursor("end")
    except Exception:
        pass


def chain_tab(widgets):
    """Make Tab go through `widgets` in this order, top to bottom.

    Tab follows the order widgets were CREATED in. The rail builds its
    boxes bottom-up so that MARK DEPOSIT stays pinned, which made Tab go
    Density, Amount, Rigs, Commodity - backwards - and then off somewhere
    else entirely. This states the order instead of leaving it to that.
    """
    entries = [getattr(w, "_entry", None) or w for w in widgets if w is not None]
    for index, entry in enumerate(entries):
        after = entries[(index + 1) % len(entries)]
        before = entries[(index - 1) % len(entries)]

        def forward(_event=None, target=after):
            try:
                target.focus_set()
                target.select_range(0, "end")
                target.icursor("end")
            except Exception:
                pass
            return "break"

        def backward(_event=None, target=before):
            try:
                target.focus_set()
                target.select_range(0, "end")
                target.icursor("end")
            except Exception:
                pass
            return "break"

        entry.bind("<Tab>", forward, add="+")
        for sequence in ("<Shift-Tab>", "<ISO_Left_Tab>"):
            try:
                entry.bind(sequence, backward, add="+")
            except Exception:
                pass


def mini_button(parent, text, command, primary=False):
    """A small button for a table row: a plain Tk label that clicks.

    A toolkit button is a canvas and a label of its own, drawn with rounded
    corners. A page of a hundred rows carried two or three of them each,
    and that - not the server - was most of the "really really slow"
    loading of finds: seconds to draw a page. This is milliseconds, and at
    22 pixels high it looks the same. Its clicks are bound on the label
    itself, nowhere else."""
    # `primary` may be a style of its own - BTN_DANGER for a delete.
    style = primary if isinstance(primary, dict) else \
        (BTN_PRIMARY if primary else BTN_SECONDARY)
    colour = style.get("fg_color") or STEEL
    hover = style.get("hover_color") or RULE
    label = tk.Label(parent, text=text, font=F_MICRO, bg=colour,
                     fg=style.get("text_color") or AMBER, padx=7, pady=1,
                     bd=0, cursor="hand2")
    label.bind("<Button-1>", lambda _event: command())
    label.bind("<Enter>", lambda _event: label.configure(bg=hover))
    label.bind("<Leave>", lambda _event: label.configure(bg=colour))
    return label


def row_buttons(table, index, buttons):
    """A row's copy and verify buttons, in the copy column.

    buttons is [(text, command, primary)]. Nothing is drawn for none."""
    if not buttons:
        return None
    box = tk.Frame(table, bg=PANEL, bd=0)
    box.grid(row=index, column=COPY_COLUMN, padx=6, pady=1, sticky="w")
    for text, command, primary in buttons:
        mini_button(box, text, command, primary).pack(side="left", padx=2)
    return box


def cell_label(table, index, column, text, colour=None, wrap=None):
    """One table cell: a plain Tk label, never the toolkit's."""
    tk.Label(table, text=text, font=F_SMALL, fg=colour or TEXT, bg=PANEL,
             justify="left", anchor="w", wraplength=wrap or CELL_WRAP,
             bd=0).grid(row=index, column=DATA_COLUMN_0 + column,
                        padx=8, pady=2, sticky="w")


class ScrollTable(ctk.CTkFrame):
    """A table that scrolls BOTH ways, and never cuts a column off.

    The Find and Earnings tables used to be a vertical-only scrolling frame,
    and that frame forces its contents to its own width. A table wider than
    the window was not scrollable sideways - its right-hand columns were
    simply cut off, which is how "Found by" and "Score" went missing from
    the Find window on anything but a very wide screen.

    Widgets go into `.inner`. It is as wide as the table needs; when that is
    narrower than the window it stretches to fill it, and when it is wider a
    horizontal scrollbar appears. Scrollbars only show when there is
    something to scroll to.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=PANEL, border_color=RULE,
                         border_width=1, corner_radius=0, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg=PANEL)
        self.vbar = ctk.CTkScrollbar(self, orientation="vertical",
                                     command=self.canvas.yview,
                                     button_color=RULE,
                                     button_hover_color=ORANGE)
        self.hbar = ctk.CTkScrollbar(self, orientation="horizontal",
                                     command=self.canvas.xview,
                                     button_color=RULE,
                                     button_hover_color=ORANGE)
        self.canvas.configure(yscrollcommand=self._show_v,
                              xscrollcommand=self._show_h)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.inner = ctk.CTkFrame(self.canvas, fg_color=PANEL, corner_radius=0)
        self._window = self.canvas.create_window(0, 0, window=self.inner,
                                                 anchor="nw")
        self.inner.bind("<Configure>", self._inner_changed)
        self.canvas.bind("<Configure>", self._canvas_changed)

    # -- keeping the two sizes honest ----------------------------------

    def _inner_changed(self, _event=None):
        try:
            self._fit()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass

    def _canvas_changed(self, _event=None):
        try:
            self._fit()
        except Exception:
            pass

    def _fit(self):
        """Stretch to the window's width, never squeeze below the table's.

        Width only, and only when it actually changes. Setting the height
        too, or re-setting a width that is already right, makes the frame
        report a new size, which calls this again - a loop Tk runs until
        Python's recursion limit stops it.
        """
        if getattr(self, "_fitting", False):
            return
        self._fitting = True
        try:
            width = max(self.inner.winfo_reqwidth(), self.canvas.winfo_width())
            if width != getattr(self, "_fitted_width", None):
                self._fitted_width = width
                self.canvas.itemconfigure(self._window, width=width)
        finally:
            self._fitting = False

    def _show_v(self, low, high):
        self._toggle(self.vbar, low, high, dict(row=0, column=1, sticky="ns"))

    def _show_h(self, low, high):
        self._toggle(self.hbar, low, high, dict(row=1, column=0, sticky="ew"))

    @staticmethod
    def _toggle(bar, low, high, place):
        """A scrollbar is shown only when there is somewhere to scroll.

        grid_forget, not grid_remove. The toolkit remembers a widget's last
        grid() and puts it back whenever it rescales - which Windows makes it
        do at start-up - and only grid_forget clears that memory. With
        grid_remove, every table carried a full-width sideways scrollbar
        with nothing to scroll to."""
        try:
            bar.set(low, high)
            if float(low) <= 0.0 and float(high) >= 1.0:
                if bar.winfo_manager():
                    bar.grid_forget()
                # Forgotten between being gridded and being drawn, Tk can
                # leave it on screen anyway. Handing it to the placer and
                # straight back takes it off for certain.
                if bar.winfo_ismapped():
                    bar.place(x=0, y=0)
                    bar.place_forget()
            elif not bar.winfo_manager():
                bar.grid(**place)
        except Exception:
            pass

    # -- the wheel ---------------------------------------------------------

    def wheel(self, event):
        """Scroll with the wheel; hold Shift to go sideways.

        Bound on the window that owns the table, not application-wide - the
        toolkit refuses that - and not on every cell, because cells are
        rebuilt on every sort and would need binding again each time.
        """
        try:
            if not self.winfo_ismapped():
                return
            delta = getattr(event, "delta", 0) or 0
            num = getattr(event, "num", 0)
            step = -1 if (delta > 0 or num == 4) else 1
            sideways = bool(int(getattr(event, "state", 0) or 0) & 0x0001)
            if sideways:
                self.canvas.xview_scroll(step * 3, "units")
            else:
                self.canvas.yview_scroll(step * 3, "units")
        except Exception:
            pass

    def top(self):
        """Back to the top-left, for a fresh result set."""
        try:
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(0)
        except Exception:
            pass


def fit_to_content(window, least_w, least_h):
    """Size a dialogue to what is in it, then stop it shrinking below that.

    The editors had a fixed 460x430. A long body name, a note with a few
    lines of history, and the Save button was below the bottom edge -
    there, but unreachable unless you knew to drag the window bigger.
    """
    try:
        window.update_idletasks()
        screen_w = int(window.winfo_screenwidth())
        screen_h = int(window.winfo_screenheight())
        width = min(max(least_w, window.winfo_reqwidth()), int(screen_w * 0.9))
        height = min(max(least_h, window.winfo_reqheight()), int(screen_h * 0.9))
        window.geometry("%dx%d" % (width, height))
        window.minsize(min(width, least_w), height)
    except Exception:
        pass


def screen_fraction(window, width_share, height_share, most_w, most_h,
                    least_w, least_h):
    """A size for a window worked out from the screen it is on.

    A fixed 1140x660 is most of a laptop and a postage stamp on a 4K
    monitor, and on the laptop it was still too narrow for the table.
    """
    try:
        screen_w = int(window.winfo_screenwidth())
        screen_h = int(window.winfo_screenheight())
    except Exception:
        screen_w, screen_h = 1920, 1080
    width = max(least_w, min(int(screen_w * width_share), most_w))
    height = max(least_h, min(int(screen_h * height_share), most_h))
    return min(width, screen_w), min(height, screen_h)


class FindWindow(ctk.CTkToplevel):
    """Everyone else's finds, ranked with staleness priced in."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("EDSMT - Find deposits")
        # Sized from the screen, not fixed. 1140 pixels cut the last two
        # columns - Found by and Score - off on every screen it was tried on.
        width, height = screen_fraction(self, 0.9, 0.8, 1800, 1000, 900, 520)
        self.geometry("%dx%d" % (width, height))
        self.minsize(820, 460)
        self.configure(fg_color=VOID)
        self.transient(app)

        # What is on screen, so a sort can redraw it without going back to
        # the server. Set before any widget exists, because _paint can be
        # reached from a filter box the moment the window opens.
        self._rows, self._headers, self._empty = [], [], ""
        self._builder, self._kind = None, ""
        self._sort_column, self._sort_reverse = None, False
        self._awaiting = None
        # The row a verification was sent for, so its answer can be put back
        # on it rather than only in the status line.
        self._verifying = None

        top = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        top.pack(fill="x", padx=12, pady=(12, 6))
        bracket(top, colour=ORANGE)
        hud_header(top, "Shared finds", padx=12, pady=(12, 4))
        # wraplength is not optional on a paragraph this long: without it the
        # label sizes itself to one enormous line and the window clips it at
        # BOTH ends, so the sentence starts mid-word and never finishes.
        self.blurb = ctk.CTkLabel(
            top, text="Shared finds from everyone running EDSMT. Older "
                      "sites rank lower - deposits do not come back "
                      "quickly. A row marked VERIFIED is one somebody "
                      "from Radio Raxxla has stood on; everything else "
                      "is commander-reported and just as welcome.",
            font=F_BODY, text_color=DIM,
            wraplength=920, justify="left", anchor="w")
        self.blurb.pack(fill="x", anchor="w", padx=12, pady=(10, 6))
        # And it has to follow the window, or resizing reintroduces the clip.
        top.bind("<Configure>", self._rewrap)
        self._rewrap()

        row = ctk.CTkFrame(top, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(row, text="Commodity", font=F_BODY,
                     text_color=DIM).pack(side="left")
        self.commodity = ctk.CTkComboBox(row, width=180, font=F_BODY, **BOX,
                                         values=["Any"] + list(SV.KNOWN_COMMODITIES))
        self.commodity.set("Any")
        self.commodity.pack(side="left", padx=(6, 14))
        ctk.CTkLabel(row, text="Min rigs", font=F_BODY,
                     text_color=DIM).pack(side="left")
        self.min_rigs = ctk.CTkComboBox(row, width=70, font=F_BODY, **BOX,
                                        values=[str(n) for n in range(0, 25)])
        self.min_rigs.set("0")
        self.min_rigs.pack(side="left", padx=(6, 14))
        ctk.CTkLabel(row, text="Types in patch", font=F_BODY,
                     text_color=DIM).pack(side="left")
        self.min_types = ctk.CTkComboBox(row, width=64, font=F_BODY, **BOX,
                                         values=["0", "1", "2", "3", "4", "5"])
        self.min_types.set("0")
        self.min_types.pack(side="left", padx=(6, 14))
        ctk.CTkLabel(row, text="Seen within", font=F_BODY,
                     text_color=DIM).pack(side="left")
        self.max_age = ctk.CTkComboBox(row, width=110, font=F_BODY, **BOX,
                                       values=["Any time", "7 days", "14 days",
                                               "30 days", "90 days"])
        self.max_age.set("Any time")
        self.max_age.pack(side="left", padx=(6, 14))
        # The filter that makes the whole thing usable. Without it the top
        # of the list is whatever is best in 400 billion systems, which is
        # a place nobody is going.
        ctk.CTkLabel(row, text="Within", font=F_BODY,
                     text_color=DIM).pack(side="left")
        self.within = ctk.CTkComboBox(row, width=110, font=F_BODY, **BOX,
                                      values=list(DISTANCE_CHOICES))
        self.within.set(DEFAULT_DISTANCE)
        self.within.pack(side="left", padx=6)

        # Second row, because eight filters on one line is how a window
        # ends up with controls off the right-hand edge at 1024 wide.
        #
        # Fixed-width things first, expanding thing last. The entry is the
        # only one allowed to grow, and packing it before the two toggles
        # would push them out of the window exactly the way the edit
        # button went missing off the signal rows.
        row2 = ctk.CTkFrame(top, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(row2, text="System / body", font=F_BODY,
                     text_color=DIM).pack(side="left")
        self.only_verified = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row2, width=130, text="Verified only", variable=self.only_verified,
                        onvalue=True, offvalue=False, font=F_BODY,
                        checkbox_width=18, checkbox_height=18, border_width=2,
                        fg_color=ORANGE, hover_color=AMBER, text_color=DIM,
                        command=self._paint).pack(side="right", padx=(12, 0))
        # On by default. A site somebody has already stripped is not a
        # result, it is a wasted drive, and the server only hides them
        # from the site search - a deposit row can still be sitting on one.
        self.hide_worked = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(row2, width=152, text="Hide worked-out", variable=self.hide_worked,
                        onvalue=True, offvalue=False, font=F_BODY,
                        checkbox_width=18, checkbox_height=18, border_width=2,
                        fg_color=ORANGE, hover_color=AMBER, text_color=DIM,
                        command=self._paint).pack(side="right", padx=(12, 0))
        self.query = ctk.CTkEntry(row2, font=F_BODY, height=30, **ENTRY,
                                  placeholder_text="narrow by system or body "
                                                   "- e.g. Col 285 or Ega 1")
        self.query.pack(side="left", fill="x", expand=True, padx=(6, 4))
        # Narrows what is already on screen as you type. No round trip, so
        # it is instant, and it goes out with the next search as well.
        self.query.bind("<KeyRelease>", lambda _e: self._paint())
        # Every filter opens its list on click or Tab, the commodity one
        # follows what is typed, and Tab walks them left to right.
        Suggest(self.commodity,
                lambda typed: ["Any"] + SV.matches(list(SV.KNOWN_COMMODITIES),
                                                   typed))
        for box in (self.min_rigs, self.min_types, self.max_age, self.within):
            try:
                Suggest(box, list(box.cget("values")))
            except Exception:
                pass
        chain_tab([self.commodity, self.min_rigs, self.min_types,
                   self.max_age, self.within, self.query])

        buttons = ctk.CTkFrame(top, fg_color="transparent")
        buttons.pack(fill="x", padx=12, pady=(0, 10))
        # The right-hand one goes down first. Pack order is claim order,
        # and a button packed last against the far edge is the one that
        # disappears when the window is dragged narrow.
        ctk.CTkButton(buttons, text="Copy all", width=100, height=32,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.copy_all).pack(side="right")
        ctk.CTkButton(buttons, text="Search sites", width=130, height=32,
                      font=F_STRONG, **BTN_PRIMARY,
                      command=self.search_sites).pack(side="left", padx=(0, 8))
        # The one thing here a position generator can never work out for
        # itself, and until now the app had no way of asking for it.
        ctk.CTkButton(buttons, text="Still there", width=120, height=32,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.search_intact).pack(side="left", padx=8)
        ctk.CTkButton(buttons, text="Individual deposits", width=160,
                      height=32, font=F_STRONG, **BTN_SECONDARY,
                      command=self.search_deposits).pack(side="left", padx=8)
        ctk.CTkButton(buttons, text="Best sell prices", width=140, height=32,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.search_prices).pack(side="left", padx=8)

        self.status = ctk.CTkLabel(self, text="", font=F_READOUT,
                                   text_color=DIM, anchor="w")
        self.status.pack(fill="x", padx=14, pady=(0, 4))
        self.scroller = ScrollTable(self)
        self.scroller.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.table = self.scroller.inner
        for sequence in ("<MouseWheel>", "<Shift-MouseWheel>",
                         "<Button-4>", "<Button-5>"):
            self.bind(sequence, self.scroller.wheel, add="+")
        self.refresh()

    def _rewrap(self, event=None):
        """Keep the blurb inside the window when the window is resized.

        wraplength is a pixel count fixed at build time, so a narrower
        window clips the sentence again. This re-measures it.

        It is wrapped in its own try because a <Configure> handler that
        raises fires on every single resize event, and Tk swallows the
        traceback - you get a window that stutters and no reason why.
        """
        try:
            width = int(getattr(event, "width", 0) or self.winfo_width())
        except Exception:
            return
        width -= 48
        if width < 240:
            return
        try:
            if int(self.blurb.cget("wraplength")) != width:
                self.blurb.configure(wraplength=width)
        except Exception:
            pass

    def refresh(self):
        # Silently, and never fatally: the dropdown already works from the
        # thirteen this build ships with, and this only adds anything the
        # server has learned since. A red line over a control that is
        # working would be worse than not asking at all.
        try:
            self.app.community.commodities()
        except Exception:
            pass
        if self.app.community.ready:
            self.say("Ready. Your finds go up, everyone else's come back.")
        elif self.app.community.can_read:
            self.say("Searching everyone else's finds. Your own are staying "
                     "on this machine - Settings turns that round.", AMBER)
        else:
            self.say("No community URL set. Settings has it.", AMBER)

    def _ready(self):
        """Searching is not sharing, and never asked for permission.

        This used to gate every button on the upload switch and then blame
        a URL that was already correct, so the one screen that shows what
        the map is worth was dark for anybody who had not opted in yet.
        """
        if self.app.community.can_read:
            return True
        self.say("No community URL set. Settings has it.", AMBER)
        return False

    def _commodity(self):
        value = self.commodity.get().strip()
        return "" if value in ("", "Any") else value

    def _text(self):
        """Whatever is typed in the system/body box, or nothing."""
        try:
            return self.query.get().strip()
        except Exception:
            return ""

    def _flag(self, var, default=False):
        """A toggle's value, without trusting it to exist.

        A BooleanVar read inside a Tk callback that raises takes the whole
        callback with it, and this one is read from the redraw - so a
        missing or half-built toggle would blank the table rather than
        show it unfiltered.
        """
        try:
            return bool(var.get())
        except Exception:
            return default

    def _extra(self, call):
        """The filters this client has grown a parameter for.

        edonline is not written here and its search methods gain optional
        keywords over time. Sending one it does not have yet is a
        TypeError, and a TypeError raised inside a Tk button command is
        swallowed whole - the button just stops working and says nothing.
        So the signature is asked first, and anything it will not take is
        applied to the rows on the way out instead (see _keep). Either way
        the filter is real; this only decides which end does the work.
        """
        wanted = {
            "system": self._text(),
            # The server's own name for it is the other way round.
            "include_depleted": not self._flag(self.hide_worked, True),
            "verified_only": self._flag(self.only_verified),
        }
        try:
            taken = inspect.signature(call).parameters
        except (TypeError, ValueError):
            return {}
        everything = any(p.kind is p.VAR_KEYWORD for p in taken.values())
        # THE BOX SAYS "System / body", SO IT HAS TO MEAN EITHER.
        #
        # Typing a body - "Ega 1" - into a search that only knows how to
        # narrow by system returns nothing, and nothing is indistinguishable
        # from "nobody has been there". The endpoints that grew a `name`
        # parameter match a system OR a body with it, so that is what this
        # box sends them; the ones that did not still get `system`, and the
        # body half is applied to the rows on the way out by _keep.
        #
        # Never both. `system` AND `name` on the same call is a search for a
        # SYSTEM called "Ega 1", which is the bug this replaces.
        if wanted["system"] and (everything or "name" in taken):
            wanted["name"] = wanted.pop("system")
        if everything:
            return dict(wanted)
        return {k: v for k, v in wanted.items() if k in taken}

    def _int(self, widget):
        try:
            return int(float(widget.get().strip() or 0))
        except ValueError:
            return 0

    def _age(self):
        try:
            return int(self.max_age.get().split()[0])
        except (ValueError, IndexError):
            return 0

    def _within(self):
        """The search radius in light years, and where to measure it from.

        Returns (None, 0) when the commander's position is not known yet,
        which is not an error: the game has simply not said where we are.
        Searching the whole galaxy is a worse answer than searching a
        sphere, but it is a much better answer than refusing.
        """
        try:
            chosen = DISTANCE_CHOICES.get(self.within.get(), 0)
        except Exception:
            chosen = 0
        if not chosen:
            return None, 0
        here = self.app.star_position()
        if here is None:
            return None, 0
        return here, chosen

    def _scope(self):
        """What to say about how wide the net was thrown."""
        here, radius = self._within()
        if not radius:
            if self.within.get() != NO_DISTANCE_LIMIT \
                    and self.app.star_position() is None:
                return " (everywhere - the game has not said where you are yet)"
            return ""
        return " within %d Ly" % radius

    def _fire(self, what, call):
        """Send a request, and be honest about whether it actually went.

        Every one of these returns False when the client cannot send, and
        that return value used to be thrown away - so a request that never
        left the machine looked exactly like one in flight. The window said
        "Searching..." and then nothing, for ever.

        A button that does nothing must SAY it did nothing.
        """
        if not self._ready():
            return
        try:
            sent = call()
        except Exception as exc:
            # A raise inside a Tk button command is swallowed by Tk's own
            # error handler, so the button silently does nothing at all.
            return self.say("Could not search: %s" % exc, RED)
        if not sent:
            return self.say("That request was not sent - no community URL is "
                            "set. Settings has it.", RED)
        self.say("%s..." % what)
        self._awaiting = what
        try:
            self.after(20000, lambda: self._overdue(what))
        except Exception:
            pass

    def _overdue(self, what):
        """Say so, rather than sitting on "Searching..." for ever."""
        if attr(self, "_awaiting") != what:
            return
        self._awaiting = None
        try:
            self.say("%s timed out - the server did not answer within 20 "
                     "seconds. Check you are online and try again." % what,
                     AMBER)
        except Exception:
            pass

    def search_sites(self):
        here, radius = self._within()
        call = self.app.community.sites
        self._fire("Searching sites" + self._scope(),
                   lambda: call(commodity=self._commodity(),
                                min_rigs=self._int(self.min_rigs),
                                min_types=self._int(self.min_types),
                                max_age_days=self._age(),
                                near=here, within_ly=radius,
                                limit=SEARCH_LIMIT,
                                **self._extra(call)))

    def search_intact(self):
        """Ranked by whether the patch is still there, not by how big it is.

        Worked-out sites come back from this one on purpose - the server
        ranks them on the same scale as everything else rather than hiding
        them - so Hide worked-out still does its job on the way in.
        """
        here, radius = self._within()
        call = self.app.community.intact
        self._fire("Checking what is still there" + self._scope(),
                   lambda: call(commodity=self._commodity(),
                                min_rigs=self._int(self.min_rigs),
                                min_types=self._int(self.min_types),
                                near=here, within_ly=radius,
                                limit=SEARCH_LIMIT,
                                **self._extra(call)))

    def search_deposits(self):
        here, radius = self._within()
        call = self.app.community.search
        self._fire("Searching deposits" + self._scope(),
                   lambda: call(commodity=self._commodity(),
                                near=here, within_ly=radius,
                                limit=SEARCH_LIMIT,
                                **self._extra(call)))

    def search_prices(self):
        """Where to sell it, near where the commander actually is.

        This asked for prices in the system the game had just named, matched
        exactly. You are standing on a rock in it. Nobody has ever sold
        anything on a rock, so the answer was nothing - every time, for
        everybody, since the button was added. The question was never "what
        sells HERE", it was "what sells NEAR here", and a position and a
        radius are how you ask that.

        A station is not a find: it cannot be worked out and nobody
        verifies it, so those two toggles have nothing to say here. The
        system/body box does - typing a system means "prices near there"
        rather than near wherever the game currently has us.
        """
        here, radius = self._within()
        near = self._text()
        if not near and here is not None:
            # Nothing typed: near the system the game has us in, BY NAME as
            # well as by position. The market index measures from a system
            # name and only from one - asked with none, it answered with the
            # best price in the galaxy, hundreds of light years off, and no
            # distance at all. Typed, it is prices near what was typed, and
            # the commander's own position is left out of it.
            near = str(getattr(getattr(self.app, "watcher", None),
                               "system", "") or "")
        elif near:
            here = None
        commodity = self._commodity()
        # With a commodity named, /v1/sell answers with the upstream index
        # as well as our own users, and says which each row came from. It
        # refuses without one, so an unfiltered lookup still goes to the
        # plain price table.
        call = self.app.community.sell if commodity \
            else self.app.community.best_prices
        self._fire("Looking up prices" + self._scope(),
                   lambda: call(commodity=commodity, near_system=near,
                                near=here, within_ly=radius))

    def say(self, text, colour=None):
        colour = colour or DIM
        self.status.configure(text=text, text_color=colour)

    def results(self, tag, payload, ok=True):
        self._awaiting = None
        # Not a result set and never JSON: one short sentence about a write.
        # It must be answered before anything tries to parse it, or a
        # perfectly good verification is reported as unreadable.
        if tag == "verify":
            return self._verified(payload, ok)
        if not ok:
            # The commodity list is a courtesy nobody asked for. A server
            # that will not serve it must not wipe the results table or put
            # a red line over a dropdown that is working.
            if tag == "commodities":
                return
            self._forget()
            return self.say("The server said: %s" % payload, RED)
        try:
            data = json.loads(payload)
        except (TypeError, ValueError):
            if tag == "commodities":
                return
            self._forget()
            return self.say("The server sent something unreadable.", RED)

        if tag == "commodities":
            return self._offer(data.get("commodities") or [])
        if tag == "sites":
            self._render(data.get("sites") or [],
                         ["System", "Body", "Signal", "Rigs", "Types",
                          "Last seen", "Found by", "Score"], self._site_row,
                         "Nothing shared yet for that filter.", kind="sites")
        elif tag == "intact":
            self._render(data.get("sites") or [],
                         ["System", "Body", "Signal", "Still there", "Rigs",
                          "Types", "Last seen", "Found by"], self._intact_row,
                         "Nothing shared yet is confident enough to list.",
                         kind="intact")
        elif tag == "sell":
            rows = (data.get("market") or []) + (data.get("community") or [])
            if rows:
                self._render(self._nearest_best(rows),
                             ["Commodity", "Station", "System", "Distance",
                              "Sell", "Demand", "Seen", "Source"],
                             self._sell_row, "No prices matched.", kind="sell")
            else:
                return self._published_prices()
        elif tag == "search":
            self._render(data.get("deposits") or [],
                         ["System", "Body", "Signal", "Commodity", "Rigs",
                          "Density", "Last seen", "Lat", "Long", "Found by"],
                         self._deposit_row, "No deposits matched.",
                         kind="search")
        else:
            rows = data.get("prices") or []
            if rows:
                self._render(self._nearest_best(rows),
                             ["Commodity", "Station", "System", "Distance",
                              "Sell", "Demand", "Seen"], self._price_row,
                             "No prices matched.", kind="market")
            else:
                # An empty table is a dead end, and the community table will
                # be empty until enough people have docked with EDSMT open.
                # The published figures are worth showing in the meantime -
                # they are the only numbers that exist for these commodities.
                # _published_prices sets its own status, after _paint has
                # stamped a count over it.
                return self._published_prices()

    # -- the table -------------------------------------------------------

    def _clear(self):
        for widget in self.table.winfo_children():
            widget.destroy()

    def _forget(self):
        """Throw the last result set away as well as the widgets showing it.

        Clearing only the widgets left the rows in hand, so ticking a
        filter after a failed search redrew the results from BEFORE it,
        under a status line that said the server had just refused.
        """
        self._clear()
        self._rows, self._headers, self._empty = [], [], ""
        self._builder, self._kind = None, ""
        self._sort_column, self._sort_reverse = None, False

    def _render(self, rows, headers, builder, empty, kind=""):
        """Take delivery of a result set. Drawing it is _paint's job.

        The rows are kept rather than drawn and forgotten, because sorting
        a .grid() table means building it again - there is no reorder - and
        going back to the server to re-sort a list already on screen would
        be absurd.
        """
        rows = list(rows)
        if builder is self._site_row:
            # ONLY when the server did not rank them. It now returns
            # intact_confidence, confirmed_by, worked_out_reports and its
            # own score, computed from corroborated depletion reports -
            # the one number this whole project treats as the point. This
            # used to re-rank unconditionally through a local scorer that
            # knows nothing about any of that, overwriting `score` and
            # `age_days` and putting a site three commanders had reported
            # stripped ABOVE an untouched one. The client cannot improve
            # on the server here; it can only throw information away.
            if not any("intact_confidence" in row for row in rows):
                rows = EDO.rank_sites(rows, half_life_days=float(
                    self.app.settings.get("freshness_half_life_days", 21) or 21))
        self._rows, self._headers = rows, list(headers)
        self._builder, self._empty, self._kind = builder, empty, kind
        # A fresh result set arrives in the server's own ranking, which is
        # the best default there is. Clicking a header opts out of it.
        self._sort_column, self._sort_reverse = None, False
        self._paint()
        scroller = attr(self, "scroller")
        if scroller is not None:
            scroller.top()

    def _paint(self):
        """Draw what is in hand, filtered and sorted. Never touches the net.

        Reached from the two toggles and from every keystroke in the filter
        box, so it has to survive being called before the table exists and
        it must not raise: a redraw that throws inside a Tk callback leaves
        a half-built table and no message anywhere.
        """
        table = attr(self, "table")
        if table is None or self._builder is None:
            return
        try:
            self._clear()
            rows = [row for row in self._rows if self._keep(row)]
            rows = self._sorted(rows)
            if not rows:
                ctk.CTkLabel(table, text=self._advice(), font=F_BODY,
                             text_color=DIM, justify="left",
                             wraplength=820).grid(row=0, column=0, padx=14,
                                                  pady=18, sticky="w")
            else:
                self._headings(rows)
                self._shown_rows, self._drawn = rows, 0
                self._more_button = None
                self._draw_page()
            self._count(len(rows))
        except Exception as exc:
            self.say("Could not draw those results: %s" % exc, RED)

    def _draw_page(self):
        """The next PAGE_ROWS rows, and a button for the rest if any are
        left. Appends: the rows already drawn stay where they are."""
        rows = attr(self, "_shown_rows", None) or []
        start = attr(self, "_drawn", 0) or 0
        more = attr(self, "_more_button", None)
        if more is not None:
            try:
                more.destroy()
            except Exception:
                pass
            self._more_button = None
        end = min(len(rows), start + PAGE_ROWS)
        for index in range(start, end):
            self._row(index + 1, rows[index])
        self._drawn = end
        left = len(rows) - end
        if left > 0:
            self._more_button = ctk.CTkButton(
                self.table, text="Show %d more  (%d not drawn yet)"
                % (min(PAGE_ROWS, left), left),
                font=F_STRONG, **BTN_SECONDARY, height=30,
                command=self._draw_page)
            self._more_button.grid(row=end + 1, column=DATA_COLUMN_0,
                                   columnspan=4, padx=8, pady=10, sticky="w")

    def _headings(self, rows):
        """Clickable headers. Click to sort, click again to turn it round."""
        for column, name in enumerate(self._headers):
            text = name
            if column == self._sort_column:
                text = "%s %s" % (name, "v" if self._sort_reverse else "^")
            # width=0 lets the words decide. Left at the toolkit's default
            # every heading was a 140-pixel button, every column at least
            # that wide, and the table ran off the side of the window.
            ctk.CTkButton(self.table, text=text, font=F_SMALL_B,
                          **BTN_HEADING, anchor="w", height=24, width=0,
                          command=lambda c=column: self.sort_by(c)).grid(
                              row=0, column=DATA_COLUMN_0 + column,
                              padx=4, pady=4, sticky="w")
        # Asked of every row on screen, not just the first. A site row
        # with no system name would otherwise take the column away from
        # the twenty rows below it that do have one.
        staff = any(self._verifiable(row) for row in rows)
        if staff or any(self._copies(row) for row in rows):
            ctk.CTkLabel(self.table,
                         text="Copy / verify" if staff else "Copy",
                         font=F_SMALL_B,
                         text_color=ORANGE).grid(row=0, column=COPY_COLUMN,
                                                 padx=8, pady=5, sticky="w")

    def _row(self, index, row):
        cells = [self._cell(c) for c in self._builder(row)]
        for column, (text, colour, _key) in enumerate(cells):
            # A list of five commodities or a long commander name wraps
            # inside its column instead of widening the whole table.
            # A plain label, not the toolkit's: a table is hundreds of cells,
            # and each toolkit label is a canvas of its own - the difference
            # between a page drawing at once and the window looking hung.
            tk.Label(self.table, text=text, font=F_SMALL,
                     fg=colour or TEXT, bg=PANEL, justify="left",
                     anchor="w", wraplength=CELL_WRAP, bd=0).grid(
                         row=index, column=DATA_COLUMN_0 + column,
                         padx=8, pady=2, sticky="w")
        buttons = [(label, lambda w=what, t=text: self.copy_text(w, t), False)
                   for label, what, text in self._copies(row)]
        if self._verifiable(row):
            buttons.append(("verify", lambda r=row: self.verify_site(r), True))
        row_buttons(self.table, index, buttons)

    # -- filtering and sorting -------------------------------------------

    def _keep(self, row):
        """The filters this end has to apply itself.

        Whatever the client took as a query parameter has already been
        applied by the server; running it again here is harmless and keeps
        the answer right when it did not take it.
        """
        text = self._text().lower()
        # Prices are the one table the box does not narrow, because there
        # it went out as near_system - and "near Sol" rightly answers with
        # markets that are not called Sol. Filtering the answer by the word
        # that produced it would throw all of them away.
        if text and self._kind not in PRICE_KINDS:
            hay = " ".join(str(row.get(key) or "") for key in
                           ("system", "planet", "body", "spot", "station",
                            "commodity", "type"))
            if text not in hay.lower():
                return False
        # Worked-out and verified are properties of a find. A price or a
        # published figure has neither, so filtering those tables on them
        # would empty a screen that has nothing to do with the question.
        if self._kind not in FIND_KINDS:
            return True
        if self._flag(self.hide_worked, True) and row.get("worked_out"):
            return False
        if self._flag(self.only_verified):
            if str(row.get("status") or "").strip().lower() != "verified" \
                    and not row.get("verified"):
                return False
        return True

    def _sorted(self, rows):
        column = self._sort_column
        if column is None or not rows:
            return rows
        def key(row):
            cells = self._builder(row)
            if column >= len(cells):
                return _sortable("")
            return self._cell(cells[column])[2]
        return sorted(rows, key=key, reverse=self._sort_reverse)

    def sort_by(self, column):
        """Sort on a column; the same column again turns it round."""
        try:
            if self._sort_column == column:
                self._sort_reverse = not self._sort_reverse
            else:
                self._sort_column, self._sort_reverse = column, False
            self._paint()
        except Exception as exc:
            self.say("Could not sort on that column: %s" % exc, RED)

    @staticmethod
    def _cell(cell):
        """(text, colour, sort key) from a row builder's 2- or 3-tuple.

        The third element exists for columns whose text does not sort the
        way it reads: "today" belongs before "9 days ago", and no amount of
        cleverness on the string will work that out.
        """
        text = str(cell[0])
        colour = cell[1] if len(cell) > 1 else None
        if len(cell) > 2 and cell[2] is not None:
            return text, colour, _sortable(cell[2])
        return text, colour, _sortable(text)

    # -- copying ---------------------------------------------------------

    def _copies(self, row):
        """What this row offers to put on the clipboard.

        The lat/long goes out as "lat, lon" because that is the form every
        other tool takes it in - a pair you paste, not two numbers you
        transcribe one at a time off a screen while driving.
        """
        out = []
        system = str(row.get("system") or "").strip()
        if system:
            out.append(("system", "the system name", system))
        lat, lon = row.get("lat"), row.get("lon")
        if lat is not None and lon is not None:
            pair = "%s, %s" % (_round(lat, 4), _round(lon, 4))
            out.append(("lat/lon", "the coordinates", pair))
        return out

    def _verifiable(self, row):
        """Whether this row can be marked stood-on, and by this commander.

        The "Verified only" filter has shipped since the first version of
        the Find window and has never had a row to match, because nothing
        in the app could set the flag. This is the button that was missing.

        Staff only - the server checks the token against its own list and
        would refuse anyone else, so offering the button to everybody would
        be offering a 403. Finds only, and never one the server already
        believes: a button that resends what is already true teaches people
        it does nothing.
        """
        if self._kind not in FIND_KINDS:
            return False
        if not getattr(self.app.community, "can_verify", False):
            return False
        if str(row.get("status") or "").strip().lower() == "verified":
            return False
        return bool(str(row.get("system") or "").strip()
                    and str(row.get("planet") or row.get("body") or "").strip())

    def _cmdr(self):
        """Who is verifying. Out of the journal, never typed."""
        name = str(getattr(self.app.game, "cmdr", "") or "").strip()
        if name:
            return name
        return str(getattr(attr(self.app, "watcher"), "cmdr", "") or "").strip()

    def verify_site(self, row):
        call = getattr(self.app.community, "verify", None)
        if not callable(call):
            return self.say("This build cannot verify sites.", AMBER)
        system = str(row.get("system") or "").strip()
        planet = str(row.get("planet") or row.get("body") or "").strip()
        spot = str(row.get("spot") or "1").strip() or "1"
        # Kept so the answer can be put on the row that asked for it. The
        # table is showing what the server believed before the click, and
        # nothing else will correct it until the next search.
        self._verifying = row
        self._fire("Verifying %s %s" % (system, planet),
                   lambda: call(self._cmdr(), system, planet, spot))

    def _verified(self, message, ok=True):
        row = attr(self, "_verifying")
        self._verifying = None
        if not ok:
            return self.say("Could not verify that site: %s" % message, RED)
        if row is not None and str(message).startswith("site verified"):
            row["status"] = "verified"
            self._paint()
        return self.say(message, GREEN)

    def _offer(self, names):
        """Merge the server's commodity list into the dropdown.

        The built-in thirteen stay in it whatever comes back. This is
        additive on purpose: the server is the end that gets updated when
        Frontier add a fourteenth, and a reply that arrived short would
        otherwise take commodities off a control that was working.
        """
        wanted = [str(n).strip() for n in names if str(n).strip()]
        if not wanted:
            return
        try:
            chosen = self.commodity.get()
            values = ["Any"] + sorted(set(list(SV.KNOWN_COMMODITIES) + wanted),
                                      key=SV.fold)
            self.commodity.configure(values=values)
            self.commodity.set(chosen if chosen in values else "Any")
        except Exception:
            pass

    def copy_text(self, what, text):
        """One click onto the clipboard, and say what went there.

        Confirming it matters more than it looks: a copy button that
        silently worked and a copy button that silently did nothing are
        the same button until you paste.
        """
        try:
            put_on_clipboard(self, text)
        except Exception as exc:
            return self.say("Could not reach the clipboard: %s" % exc, RED)
        self.say("Copied %s - %s" % (what, text), GREEN)

    def copy_all(self):
        """The whole table as a block, ready to paste into Discord."""
        try:
            block = self.as_text()
        except Exception as exc:
            return self.say("Could not build that: %s" % exc, RED)
        if not block:
            return self.say("Nothing to copy yet - run a search first.", AMBER)
        try:
            put_on_clipboard(self, block)
        except Exception as exc:
            return self.say("Could not reach the clipboard: %s" % exc, RED)
        self.say("Copied %d row(s) - paste it straight into Discord."
                 % (len(block.splitlines()) - 1), GREEN)

    def as_text(self):
        """What is on screen, as plain lines. Empty when nothing is."""
        if self._builder is None:
            return ""
        rows = self._sorted([r for r in self._rows if self._keep(r)])
        if not rows:
            return ""
        lines = [" | ".join(self._headers)]
        for row in rows:
            lines.append(" | ".join(self._cell(c)[0]
                                    for c in self._builder(row)))
        return "\n".join(lines)

    # -- what to say when there is nothing -------------------------------

    def _active(self):
        """The filters currently narrowing things, in plain words."""
        on = []
        if self._text():
            on.append('the system/body box ("%s")' % self._text())
        if self._kind in FIND_KINDS:
            if self._flag(self.hide_worked, True):
                on.append("Hide worked-out")
            if self._flag(self.only_verified):
                on.append("Verified only")
        if self._commodity():
            on.append("Commodity %s" % self._commodity())
        if self.within.get() != NO_DISTANCE_LIMIT:
            on.append("Within %s" % self.within.get())
        return on

    def _advice(self):
        """An empty table has to say what to do next, not just that it is empty."""
        if self._rows:
            return ("%d row(s) came back and your filters hid all of them.\n"
                    "Narrowing it down: %s.\nUntick one, or clear the "
                    "system/body box." % (len(self._rows),
                                          "; ".join(self._active()) or "none"))
        widen = []
        if self.within.get() != NO_DISTANCE_LIMIT:
            widen.append('set Within to "%s"' % NO_DISTANCE_LIMIT)
        if self._int(self.min_rigs):
            widen.append("drop Min rigs to 0")
        if self._int(self.min_types):
            widen.append("drop Types in patch to 0")
        if self._age():
            widen.append('set Seen within to "Any time"')
        if self._commodity():
            widen.append('set Commodity to "Any"')
        if self._text():
            # It goes out as `system`, and the server prefix-matches the
            # SYSTEM name with it. "Ega 1" is a body, no system starts with
            # it, and the honest answer to that is to say so rather than to
            # let somebody retype it slower.
            widen.append("clear the system/body box"
                         + (" - it goes out as a system name, so a body "
                            "typed in full matches nothing at the server"
                            if self._kind in FIND_KINDS else ""))
        if not widen:
            return (self._empty + "\n\nNothing is hidden - nobody has shared "
                    "one yet. Mark a deposit with %s and yours will be the "
                    "first." % bound_key(getattr(self.app, "settings", None),
                                         "deposit", "MARK DEPOSIT"))
        return (self._empty + "\n\nTry again wider: " + ", ".join(widen) + ".")

    def _count(self, shown):
        total = len(self._rows)
        if not total:
            # Not a no-op. Without this the status line is still saying
            # "Searching sites..." from _fire, next to a table that has
            # already finished and found nothing - which reads as a search
            # that hung rather than one that came back empty.
            return self.say("0 result(s).", AMBER)
        if shown == total:
            # A full page means the server stopped counting, not that the
            # galaxy holds exactly this many. Saying "50 result(s)" over a
            # capped page is a lie the user cannot see through.
            if total >= SEARCH_LIMIT:
                return self.say("%d result(s) - the most this asks for at "
                                "once. Narrow it to see past them."
                                % total, AMBER)
            return self.say("%d result(s)." % total, GREEN)
        self.say("%d of %d shown - %d hidden by your filters."
                 % (shown, total, total - shown), AMBER if shown else RED)

    # -- the rows themselves ---------------------------------------------

    def _site_row(self, row):
        age = row.get("age_days") or 0
        seen = ("today" if age < 1 else "yesterday" if age < 2
                else "%d days ago" % age)
        colour = GREEN if age <= 14 else (AMBER if age <= 45 else RED)
        return [(str(row.get("system", "")), None), (str(row.get("planet", "")
                or row.get("body", "")), None),
                (str(row.get("spot", "")), None), (str(row.get("rigs", "")), None),
                (", ".join(row.get("types") or []), None),
                # Sorts on the number of days, not on the sentence: "today"
                # has to come first and alphabetically it comes last.
                (seen, colour, age),
                # Search sites is the search people actually use, and this
                # was on the deposits table only - so the commander who
                # first mapped a site was invisible on every screen that
                # lists sites. Reported twice before it was believed.
                (self._found_by(row), DIM),
                ("%.1f" % (row.get("score") or 0), None)]

    def _deposit_row(self, row):
        seen, days = last_seen(row)
        return [(str(row.get("system", "")), None), (str(row.get("planet", "")), None),
                (str(row.get("spot", "")), None), (str(row.get("type", "")), None),
                (str(row.get("rigs", "")), None), (str(row.get("density") or "-"), None),
                (seen, GREEN if days is not None and days < 7 else
                 DIM if days is None or days < 30 else FAINT,
                 days if days is not None else 1e9),
                (_round(row.get("lat"), 4), None), (_round(row.get("lon"), 4), None),
                (self._found_by(row), DIM)]

    @staticmethod
    def _found_by(row):
        """The commander who shared it, or the fact that nobody is claiming it.

        The server has always stored and returned this and nothing ever
        showed it, so every find on the map was anonymous whether or not
        the commander had asked to be credited. An empty one is normal -
        crediting your name is a switch in Settings - so it reads as an
        answer rather than as a column that failed to load.
        """
        return str(row.get("uploader") or "").strip() or ANONYMOUS

    def _published_prices(self):
        """The published table, while the community one fills up.

        Average and ceiling both, because they say different things: the
        average survives a community goal ending, the ceiling is what one
        market paid on one day and is currently pinned to the CG rate for
        three commodities. Showing only one of them would mislead.
        """
        wanted = self._commodity()
        names = SV.KNOWN_COMMODITIES
        if wanted:
            names = [n for n in names if SV.fold(n) == SV.fold(wanted)] or names
        rows = [{"commodity": n,
                 "category": SV.category(n),
                 "avg": SV.published_price(n),
                 "max": SV.ceiling_price(n),
                 "bodies": SV.bodies_for(n)} for n in names]
        self._render(rows, ["Commodity", "Type", "Average", "Best seen",
                            "Found on"], self._published_row,
                     "No published figure for that commodity.",
                     kind="published")
        self.say("Published figures - no commander prices shared yet. "
                 "Dock with EDSMT running and these become real.", AMBER)

    def _published_row(self, row):
        short = {"High metal content body": "HMC", "Metal rich body": "Rich",
                 "Rocky body": "Rocky", "Rocky ice world": "Rocky ice",
                 "Icy body": "Icy"}
        where = ", ".join(short.get(b, b) for b in row.get("bodies") or ())
        return [(str(row.get("commodity", "")), None),
                (str(row.get("category", "")), None),
                ("{:,}".format(int(row.get("avg") or 0)), GREEN),
                ("{:,}".format(int(row.get("max") or 0)), None),
                (where, DIM)]

    def _price_row(self, row):
        return [(str(row.get("commodity", "")), None),
                (str(row.get("station", "")), None),
                (str(row.get("system", "")), None),
                self._distance(row),
                ("{:,}".format(int(row.get("sell") or 0)), GREEN),
                ("{:,}".format(int(row.get("demand") or 0)), None),
                (str(row.get("seen", ""))[:10], None)]

    def _sell_row(self, row):
        # Which index said so, spelled out rather than blended into the
        # rest. Our own users' Market.json and somebody else's galaxy
        # index are not equally fresh, and a table that hides which is
        # which is a table that quietly invents confidence.
        return self._price_row(row) + [(str(row.get("source") or "-"), DIM)]

    @staticmethod
    def _distance(row):
        """How far the station is, when anybody knows.

        A blank is not a zero. A system nobody has uploaded a position for
        has no distance, and printing 0.0 would put it at the top of a
        nearest-first table as the closest thing in the galaxy.
        """
        far = row.get("distance_ly")
        if far is None:
            far = row.get("distance")
        try:
            return ("%s Ly" % _round(far, 1), None, float(far))
        except (TypeError, ValueError):
            return ("-", DIM, None)

    @staticmethod
    def _nearest_best(rows):
        """Nearest first, best price between equals.

        The server hands these back in price order, which puts a 40,000 Ly
        haul at the top of a list of places you could actually drive to.
        Distance is the axis a commander cannot argue with; the Sell
        heading is one click away for the other one.
        """
        def key(row):
            far = row.get("distance_ly")
            if far is None:
                far = row.get("distance")
            try:
                near = (0, float(far))
            except (TypeError, ValueError):
                near = (1, 0.0)
            try:
                sell = float(row.get("sell") or 0)
            except (TypeError, ValueError):
                sell = 0.0
            return near + (-sell,)
        return sorted(rows, key=key)

    def _intact_row(self, row):
        """The same site, ranked by whether it is still there.

        Confidence leads, because that is the question the endpoint exists
        to answer and a column buried on the right of seven others is a
        column nobody reads.
        """
        age = row.get("age_days") or 0
        seen = ("today" if age < 1 else "yesterday" if age < 2
                else "%d days ago" % age)
        try:
            belief = float(row.get("intact_confidence") or 0)
        except (TypeError, ValueError):
            belief = 0.0
        shade = GREEN if belief >= 0.66 else (AMBER if belief >= 0.33 else RED)
        return [(str(row.get("system", "")), None),
                (str(row.get("planet", "") or row.get("body", "")), None),
                (str(row.get("spot", "")), None),
                ("%d%%" % round(belief * 100), shade, belief),
                (str(row.get("rigs", "")), None),
                (", ".join(row.get("types") or []), None),
                (seen, None, age),
                (self._found_by(row), DIM)]


# ---------------------------------------------------------------------------
# What every run was worth
# ---------------------------------------------------------------------------

# The ledger's columns, in the order a commander reads them: when, where it
# came from, what crossed the counter, what it paid, how fast, and where it
# was sold. Declared once because the headings, the sort and the Copy all
# block all have to agree on them or a paste says one thing and the screen
# says another.
RUN_HEADERS = ("Started", "Mined at", "Mined", "To ship", "Sold", "Credits",
               "Cr/hr", "Time", "Sold at")


class EarningsWindow(ctk.CTkToplevel):
    """Every run this commander has banked, and what they add up to.

    Built on the Find window's table rather than beside it: copy buttons in
    the FIRST column, headings you click to sort, cells that carry their own
    sort key where the text does not sort the way it reads. A second table
    idiom in the same app is a second set of bugs.
    """

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("EDSMT - Session earnings")
        width, height = screen_fraction(self, 0.8, 0.75, 1500, 950, 820, 480)
        self.geometry("%dx%d" % (width, height))
        self.minsize(780, 440)
        self.configure(fg_color=VOID)
        self.transient(app)

        # Held rather than drawn and forgotten, for the same reason Find
        # holds its results: sorting a .grid() table means building it
        # again, because there is no reorder.
        self._rows = []
        self._sort_column, self._sort_reverse = None, False

        top = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        top.pack(fill="x", padx=12, pady=(12, 6))
        bracket(top, colour=ORANGE)
        hud_header(top, "Session earnings", padx=12, pady=(12, 4))

        self.summary = ctk.CTkLabel(top, text="", font=F_READOUT,
                                    text_color=AMBER, anchor="w",
                                    justify="left")
        self.summary.pack(fill="x", anchor="w", padx=12, pady=(6, 2))
        # What is in the hold RIGHT NOW, at the last price seen. The rows
        # below are history; this line is the run you are still on, and it
        # is the reason to have the window open while the game is running.
        self.holding = ctk.CTkLabel(top, text="", font=F_BODY,
                                    text_color=DIM, anchor="w",
                                    justify="left")
        self.holding.pack(fill="x", anchor="w", padx=12, pady=(0, 6))

        # Where what is aboard sells best, from the system you are in. The
        # price at the last station seen is not the answer to "where do I
        # take this": the same Sapphire is worth more two jumps away, and
        # this is the one screen that already knows what is in the hold.
        sell = ctk.CTkFrame(top, fg_color="transparent")
        sell.pack(fill="x", padx=12, pady=(0, 6))
        self.sell_title = ctk.CTkLabel(sell, text="Where to sell what is aboard",
                                       font=F_STRONG, text_color=ORANGE,
                                       anchor="w")
        self.sell_title.pack(side="left")
        ctk.CTkButton(sell, text="Check prices", width=120, height=30,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.check_prices).pack(side="right")
        self.sell_within = ctk.CTkComboBox(sell, width=100, font=F_BODY,
                                           **BOX, values=list(QUOTE_DISTANCES))
        self.sell_within.set(DEFAULT_QUOTE_DISTANCE)
        self.sell_within.pack(side="right", padx=6)
        ctk.CTkLabel(sell, text="within", font=F_BODY,
                     text_color=DIM).pack(side="right")
        self.quote_table = tk.Frame(top, bg=PANEL, bd=0)
        self.quote_table.pack(fill="x", anchor="w", padx=12, pady=(0, 6))

        buttons = ctk.CTkFrame(top, fg_color="transparent")
        buttons.pack(fill="x", padx=12, pady=(0, 10))
        # Right-hand one first. Pack order is claim order, and the button
        # packed last against the far edge is the one that disappears when
        # the window is dragged narrow.
        ctk.CTkButton(buttons, text="Copy all", width=100, height=32,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.copy_all).pack(side="right")
        ctk.CTkButton(buttons, text="Refresh", width=100, height=32,
                      font=F_STRONG, **BTN_PRIMARY,
                      command=self.refresh).pack(side="left")
        # One session across several trips. Off, a session is one outing:
        # the Rhino goes out, fills the ship a hold at a time, and comes
        # back aboard. On, it carries on through the flight to a station,
        # the sale and the trip back, until it is ticked off again.
        self.multi = ctk.BooleanVar(
            value=bool(self.app.settings.get("earnings_multi_session")))
        ctk.CTkCheckBox(buttons, text="Multi-session - keep one session "
                                      "going across trips to a station",
                        variable=self.multi, font=F_BODY,
                        command=self.set_multi).pack(side="left", padx=(14, 6))
        # A session opens on the first rig down or the first tonne refined
        # in the Rhino, and closes on every rig up or the Rhino aboard. These
        # are for doing it by hand: Start before anything is down, Pause for
        # the drive to a station or a break - paused time is not in the
        # Cr/hr - and End.
        self.start_button = ctk.CTkButton(
            buttons, text="Start session", width=120, height=32,
            font=F_STRONG, **BTN_SECONDARY, command=self.start_session)
        self.start_button.pack(side="left", padx=6)
        self.pause_button = ctk.CTkButton(
            buttons, text="Pause", width=100, height=32, font=F_STRONG,
            **BTN_SECONDARY, command=self.pause_session)
        self.pause_button.pack(side="left", padx=6)
        ctk.CTkButton(buttons, text="End session", width=110, height=32,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.end_session).pack(side="left", padx=6)

        self.status = ctk.CTkLabel(self, text="", font=F_READOUT,
                                   text_color=DIM, anchor="w")
        self.status.pack(fill="x", padx=14, pady=(0, 4))
        self.scroller = ScrollTable(self)
        self.scroller.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.table = self.scroller.inner
        for sequence in ("<MouseWheel>", "<Shift-MouseWheel>",
                         "<Button-4>", "<Button-5>"):
            self.bind(sequence, self.scroller.wheel, add="+")
        self.refresh()
        self.show_quotes()
        # Asked for straight away when there is something aboard - the
        # whole reason to open this with a full hold is to find out where
        # to take it. Quietly: an offline commander gets the ledger, not an
        # error, and the button is there to ask again.
        if self.app.mined_aboard():
            self.check_prices(quiet=True)

    # -- sessions -----------------------------------------------------------

    def set_multi(self):
        """The multi-session box: kept in settings, handed to the books.

        Ticked off with a session still open and the Rhino aboard, that
        session is finished there and then - it was only still open because
        the box said so."""
        wanted = bool(self.multi.get())
        self.app.settings["earnings_multi_session"] = wanted
        save_settings(self.app.settings)
        books = self.app.earnings
        books.multi = wanted
        if not wanted and books.rhino is not None and not books._in_rhino:
            books.finish(None, "multi-session switched off", by="button")
        self.refresh()
        self.say("Multi-session on: one session across every trip until you "
                 "untick this." if wanted else
                 "Multi-session off: each Rhino outing is its own session.",
                 GREEN)

    def end_session(self):
        """Finish the session in progress now, whatever it is doing."""
        books = self.app.earnings
        if books.current is None:
            return self.say("No session is running.", AMBER)
        books.finish(None, "ended by hand", by="button")
        self.refresh()
        return self.say("Session ended.", GREEN)

    def start_session(self):
        """Open a session now, before a rig is down or a tonne refined."""
        books = self.app.earnings
        if books.current is not None:
            return self.say("A session is already running%s." % (
                " - paused; Resume carries it on" if books.paused else ""),
                AMBER)
        system, body = self.app.here()
        books.start_now(system, body,
                        getattr(attr(self.app, "watcher"), "cmdr", "") or "")
        self.refresh()
        return self.say("Session started. Every rig up, End session or the "
                        "Rhino coming aboard ends it.", GREEN)

    def pause_session(self):
        """Pause or resume the session in progress."""
        books = self.app.earnings
        if books.current is None:
            return self.say("No session is running to pause.", AMBER)
        if books.paused:
            books.resume()
            self.refresh()
            return self.say("Session running again.", GREEN)
        books.pause()
        self.refresh()
        return self.say("Session paused - the clock has stopped, so the drive "
                        "to a station is not in the Cr/hr. Tonnes and sales "
                        "still count; a rig down, a tonne refined or the "
                        "Rhino going out starts it again by itself.", GREEN)

    def _session_buttons(self):
        """Pause reads Resume while paused; Start is dimmed while running."""
        books = self.app.earnings
        try:
            self.pause_button.configure(
                text="Resume" if books.paused else "Pause",
                state="normal" if books.current is not None else "disabled")
            self.start_button.configure(
                state="disabled" if books.current is not None else "normal")
        except Exception:
            pass

    # -- where to sell ------------------------------------------------------

    def _radius(self):
        try:
            return QUOTE_DISTANCES.get(self.sell_within.get().strip(),
                                       QUOTE_DISTANCES[DEFAULT_QUOTE_DISTANCE])
        except Exception:
            return QUOTE_DISTANCES[DEFAULT_QUOTE_DISTANCE]

    def check_prices(self, quiet=False):
        """Ask the community server where each thing aboard sells best."""
        try:
            count, why = self.app.quote_hold(self._radius())
        except Exception as exc:
            count, why = 0, "Could not ask: %s" % exc
        if not count:
            if not quiet:
                self.say(why, AMBER)
            return 0
        self.say("Asking for the best price for %d commodit%s within %d Ly "
                 "of %s..." % (count, "y" if count == 1 else "ies",
                               self._radius(),
                               self.app.quote_asked.get("system", "here")))
        return count

    def show_quotes(self):
        """Draw what has come back so far. Must not raise."""
        table = attr(self, "quote_table")
        if table is None:
            return
        try:
            for widget in table.winfo_children():
                widget.destroy()
            cargo = self.app.mined_aboard()
            quotes = self.app.fresh_quotes()
            asked = attr(self.app, "quote_asked") or {}
            system = asked.get("system") or getattr(self.app.watcher,
                                                    "system", "") or ""
            if system:
                self.sell_title.configure(
                    text="Where to sell what is aboard - from %s" % system)
            rows = [name for name in worth_asking(cargo, limit=len(cargo))
                    if SV.fold(name) in quotes]
            if not rows:
                problem = attr(self.app, "quote_problem")
                if problem:
                    self.say("Could not get prices - the server said: %s"
                             % problem, AMBER)
                return
            headings = ("Commodity", "Aboard", "Galactic avg (est.)",
                        "In this system",
                        "Best within %d Ly" % self._radius(), "Where",
                        "Price seen", "Worth there")
            for column, text in enumerate(headings):
                tk.Label(table, text=text, font=F_SMALL_B, fg=ORANGE,
                         bg=PANEL, anchor="w", bd=0).grid(
                             row=0, column=column, padx=(0, 14), sticky="w")
            for index, name in enumerate(rows, start=1):
                quote = quotes[SV.fold(name)]
                best, here = quote.get("best"), quote.get("here")
                count = int(cargo.get(name, 0))
                seen = last_seen({"last_seen": (best or {}).get("seen")})[0] \
                    if best else "-"
                average, source = self.app.galactic_average(name)
                cells = (
                    (name, TEXT),
                    ("%dt" % count, TEXT),
                    ((credits_text(average) + ("" if source == "game" else " *"))
                     if average else "-", DIM),
                    (credits_text(here["sell"]) if here else "none known",
                     TEXT if here else DIM),
                    (credits_text(best["sell"]) if best else "none within range",
                     GREEN if best else DIM),
                    (quote_where(best), TEXT),
                    (seen, DIM),
                    (credits_text(best["sell"] * count) + " Cr" if best else "-",
                     GREEN if best else DIM),
                )
                for column, (text, colour) in enumerate(cells):
                    tk.Label(table, text=text, font=F_SMALL, fg=colour,
                             bg=PANEL, anchor="w", bd=0,
                             wraplength=CELL_WRAP).grid(
                                 row=index, column=column, padx=(0, 14),
                                 sticky="w")
            if any(self.app.galactic_average(name)[1] == "table"
                   for name in rows):
                tk.Label(table, text="* EDSMT's own figure. Open any "
                         "commodity market in the game and the game's "
                         "galactic average replaces it.", font=F_SMALL,
                         fg=DIM, bg=PANEL, anchor="w", bd=0).grid(
                             row=len(rows) + 1, column=0, columnspan=8,
                             sticky="w", pady=(4, 0))
        except Exception as exc:
            self.say("Could not show the prices: %s" % exc, RED)

    # -- getting the rows -------------------------------------------------

    def refresh(self):
        """Read the books off disk again and redraw.

        Off disk rather than out of the app's copy on purpose. The run in
        progress is written through on every event, so re-reading is how a
        window left open all evening keeps up with the mining without
        anything having to push at it.
        """
        try:
            self.app.earnings.load()
            self._rows = list(self.app.earnings.recent())
        except Exception as exc:
            self._rows = []
            return self.say("Could not read the session log: %s" % exc, RED)
        self._paint()

    # -- drawing ----------------------------------------------------------

    def _paint(self):
        """Draw what is in hand. Must not raise.

        Reached from a button and from sorting, and a redraw that throws
        inside a Tk callback leaves half a table and no message anywhere.
        """
        table = attr(self, "table")
        if table is None:
            return
        try:
            for widget in table.winfo_children():
                widget.destroy()
            self._summarise()
            rows = self._sorted(list(self._rows))
            if not rows:
                ctk.CTkLabel(table, text=self._advice(), font=F_BODY,
                             text_color=DIM, justify="left",
                             wraplength=820).grid(row=0, column=0, padx=14,
                                                  pady=18, sticky="w")
                return self.say("No Rhino sessions recorded yet.", AMBER)
            self._headings()
            for index, row in enumerate(rows, start=1):
                self._row(index, row)
            self.say("%d Rhino session(s)." % len(rows), GREEN)
        except Exception as exc:
            self.say("Could not draw the ledger: %s" % exc, RED)

    def _headings(self):
        """Clickable headers. Click to sort, click again to turn it round."""
        for column, name in enumerate(RUN_HEADERS):
            text = name
            if column == self._sort_column:
                text = "%s %s" % (name, "v" if self._sort_reverse else "^")
            # width=0 lets the words decide. Left at the toolkit's default
            # every heading was a 140-pixel button, every column at least
            # that wide, and the table ran off the side of the window.
            ctk.CTkButton(self.table, text=text, font=F_SMALL_B,
                          **BTN_HEADING, anchor="w", height=24, width=0,
                          command=lambda c=column: self.sort_by(c)).grid(
                              row=0, column=DATA_COLUMN_0 + column,
                              padx=4, pady=4, sticky="w")
        ctk.CTkLabel(self.table, text="Copy / delete", font=F_SMALL_B,
                     text_color=ORANGE).grid(row=0, column=COPY_COLUMN,
                                             padx=8, pady=5, sticky="w")

    def _row(self, index, row):
        for column, cell in enumerate(self._run_row(row)):
            text, colour, _key = self._cell(cell)
            # A list of five commodities or a long commander name wraps
            # inside its column instead of widening the whole table.
            # A plain label, not the toolkit's: a table is hundreds of cells,
            # and each toolkit label is a canvas of its own - the difference
            # between a page drawing at once and the window looking hung.
            tk.Label(self.table, text=text, font=F_SMALL,
                     fg=colour or TEXT, bg=PANEL, justify="left",
                     anchor="w", wraplength=CELL_WRAP, bd=0).grid(
                         row=index, column=DATA_COLUMN_0 + column,
                         padx=8, pady=2, sticky="w")
        buttons = [(label, lambda w=what, t=text: self.copy_text(w, t), False)
                   for label, what, text in self._copies(row)]
        buttons.append(("delete", lambda r=row: self.delete_session(r),
                        BTN_DANGER))
        row_buttons(self.table, index, buttons)

    def delete_session(self, row):
        """Take a session off the tab and out of sessions.csv.

        Two presses, the second on the same row within a few seconds: one
        click on a row of small buttons is too easy to land on the wrong
        one, and a modal box over a window full of numbers is worse. The
        file before is kept as sessions.csv.bak."""
        row_id = str((row or {}).get("id") or "")
        if not row_id:
            return self.say("That session has no id to delete it by.", RED)
        armed = attr(self, "_delete_armed", None)
        when = str(row.get("started") or "")[:16].replace("T", " ")
        where = " / ".join(str(row.get(k) or "") for k in ("system", "body")
                           if row.get(k)) or "somewhere unrecorded"
        if not (armed and armed[0] == row_id
                and time.time() - armed[1] < DELETE_CONFIRM_S):
            self._delete_armed = (row_id, time.time())
            return self.say("Press delete again on the same row within %d "
                            "seconds to remove the session from %s at %s. "
                            "It cannot be undone here - the file before it "
                            "is kept as sessions.csv.bak."
                            % (DELETE_CONFIRM_S, when or "an unknown time",
                               where), AMBER)
        self._delete_armed = None
        try:
            gone = self.app.earnings.delete(row_id)
        except Exception as exc:
            return self.say("Could not delete it: %s" % exc, RED)
        if gone is None:
            self.refresh()
            return self.say("That session was already gone.", AMBER)
        self.refresh()
        try:
            self.app.update_earnings()
        except Exception:
            pass
        return self.say("Deleted the session from %s at %s." % (
            when or "an unknown time", where), GREEN)

    def _summarise(self):
        """Everything, added up, above the rows it is the sum of."""
        totals = self.app.earnings.totals(self._rows)
        self.summary.configure(
            text="%d Rhino session(s)   %s Cr sold   %s at the face   %s Cr/hr overall"
                 % (totals["runs"], credits_text(totals["earned"]),
                    duration_text(totals["hours"]),
                    credits_text(totals["cr_hr"])))
        self.holding.configure(text=self._holding() or
                               "Nothing mined in the hold, or the game is not "
                               "running.")
        self._session_buttons()

    def _holding(self):
        """The live line: what is aboard, and what it would fetch.

        Wrapped in its own try because this is the one part of the window
        that reaches outside the CSV, into the reader and the last market.
        A ledger that refuses to open because Elite is shut would be a
        ledger nobody can tidy up in the evening.
        """
        try:
            holds = dict(getattr(self.app.watcher, "holds", None) or {})
            cargo = self.app.mined_aboard()
            prices = self.app.market_prices()
        except Exception:
            return ""
        if not cargo:
            return ""
        tonnes = sum(int(count) for count in cargo.values())
        # Ship and SRV each named, because "36t" over a ship with 30 and an
        # SRV with 6 does not tell you whether it is time to go back up.
        # Only what was mined: a hold of hauled Tea is not these earnings.
        mined = {SV.fold(name) for name in cargo}
        parts = []
        for vessel in ("SRV", "Ship"):
            hold = {k: v for k, v in dict(holds.get(vessel) or {}).items()
                    if v and SV.fold(k) in mined}
            if not hold:
                continue
            biggest = sorted(hold.items(), key=lambda pair: -pair[1])[:4]
            parts.append("%s %dt - %s" % (
                "SRV" if vessel == "SRV" else "ship", sum(hold.values()),
                ", ".join("%s %d" % (name, count) for name, count in biggest)))
        if not parts:
            biggest = sorted(cargo.items(), key=lambda pair: -pair[1])[:4]
            parts.append("%dt - %s" % (tonnes, ", ".join(
                "%s %d" % (name, count) for name, count in biggest)))
        text = "Mined, in the hold: " + ";  ".join(parts) + "."
        worth = SV.hold_value(cargo, prices)
        guess = self.app.hold_estimate(cargo)
        if guess:
            text += " About %s Cr at the galactic average." % credits_text(guess)
        if not worth:
            return text + " No market prices seen yet."
        where = (getattr(self.app.watcher, "market", None) or {}).get("station")
        return text + " Worth %s Cr at %s." % (
            credits_text(worth), where or "the last market seen")

    def _advice(self):
        """An empty ledger has to say what fills it, not just that it is empty."""
        return ("No Rhino sessions yet.\n\nA session starts on your first "
                "rig down (the rig keys), or the first tonne the Rhino "
                "refines, or Start session. It ends when every rig is back "
                "up, when the Rhino comes back aboard, or on End session. "
                "Every tonne it refines is counted, every transfer to the "
                "ship is counted, and when you sell what it dug up the "
                "credits are put against it. Nothing else goes in here - not "
                "trading, not hauling, not exploration, not asteroid mining. "
                "Pause stops the clock for a break or the drive to a "
                "station. Tick Multi-session to keep one session going "
                "across trips to a station.")

    # -- the row itself ----------------------------------------------------

    def _run_row(self, row):
        """One session as cells, in RUN_HEADERS order.

        The third element of a cell is its sort key, for the columns whose
        text does not sort the way it reads: "2,140,000 Cr" sorts as a
        string under "900 Cr", and "1h 02m" under "58m".
        """
        started = str(row.get("started") or "")
        live = not str(row.get("closed") or "").strip()
        hours = SV.session_hours(row)
        kept = SV.earned(row)

        def listed(field):
            counts = SV.unpack_counts(row.get(field))
            total = sum(counts.values())
            if not total:
                return "-", 0
            return "%dt: %s" % (total, SV.pack_counts(counts)
                                .replace(":", " ").replace(";", ", ")), total
        mined, mined_t = listed("mined")
        moved, moved_t = listed("transferred")
        sold, sold_t = listed("sold")
        body = str(row.get("body") or "")
        system = str(row.get("system") or "")
        where = ("%s / %s" % (system, body)).strip(" /") or "-"
        trips = int(SV._number(row.get("trips")))
        if trips > 1:
            where += "  (%d trips)" % trips
        return [
            (started[:16].replace("T", " ") or "-",
             AMBER if live else TEXT, started),
            (where, None),
            (mined, None, mined_t),
            (moved, None, moved_t),
            (sold, None, sold_t),
            (credits_text(kept), GREEN if kept else DIM, kept),
            (credits_text(SV.credits_per_hour(row)), None,
             SV.credits_per_hour(row)),
            (duration_text(hours) if hours else "-", None, hours),
            (str(row.get("station") or "") or ("still out" if live else "-"),
             AMBER if live else None),
        ]

    def _copies(self, row):
        """What this row offers to put on the clipboard.

        The system, because that is what somebody pastes into a route
        planner, and the whole line, because that is what gets pasted into
        Discord when a run was worth telling people about.
        """
        out = []
        system = str(row.get("system") or "").strip()
        if system:
            out.append(("system", "the system name", system))
        out.append(("row", "this run",
                    " | ".join(self._cell(c)[0] for c in self._run_row(row))))
        return out

    # -- sorting ------------------------------------------------------------

    def _sorted(self, rows):
        column = self._sort_column
        if column is None or not rows:
            return rows

        def key(row):
            cells = self._run_row(row)
            if column >= len(cells):
                return _sortable("")
            return self._cell(cells[column])[2]
        return sorted(rows, key=key, reverse=self._sort_reverse)

    def sort_by(self, column):
        """Sort on a column; the same column again turns it round."""
        try:
            if self._sort_column == column:
                self._sort_reverse = not self._sort_reverse
            else:
                self._sort_column, self._sort_reverse = column, False
            self._paint()
        except Exception as exc:
            self.say("Could not sort on that column: %s" % exc, RED)

    @staticmethod
    def _cell(cell):
        """(text, colour, sort key) from a row builder's 2- or 3-tuple."""
        text = str(cell[0])
        colour = cell[1] if len(cell) > 1 else None
        if len(cell) > 2 and cell[2] is not None:
            return text, colour, _sortable(cell[2])
        return text, colour, _sortable(text)

    # -- copying -------------------------------------------------------------

    def copy_text(self, what, text):
        """One click onto the clipboard, and say what went there."""
        try:
            put_on_clipboard(self, text)
        except Exception as exc:
            return self.say("Could not reach the clipboard: %s" % exc, RED)
        self.say("Copied %s - %s" % (what, text), GREEN)

    def copy_all(self):
        """The whole ledger as a block, ready to paste into Discord."""
        try:
            block = self.as_text()
        except Exception as exc:
            return self.say("Could not build that: %s" % exc, RED)
        if not block:
            return self.say("Nothing to copy yet - no runs recorded.", AMBER)
        try:
            put_on_clipboard(self, block)
        except Exception as exc:
            return self.say("Could not reach the clipboard: %s" % exc, RED)
        self.say("Copied %d row(s) - paste it straight into Discord."
                 % (len(block.splitlines()) - 1), GREEN)

    def as_text(self):
        """What is on screen, as plain lines. Empty when nothing is."""
        rows = self._sorted(list(self._rows))
        if not rows:
            return ""
        lines = [" | ".join(RUN_HEADERS)]
        for row in rows:
            lines.append(" | ".join(self._cell(c)[0]
                                    for c in self._run_row(row)))
        return "\n".join(lines)

    def say(self, text, colour=None):
        colour = colour or DIM
        self.status.configure(text=text, text_color=colour)

# The Where to land columns. One tuple for the headings, the sort and the
# Copy all block, for the same reason as RUN_HEADERS.
# Read left to right: which body, what it is worth, why - then the detail.
LAND_HEADERS = ("Body", "Est. value", "Why", "Ls", "Locations", "Best bets",
                "Known sites", "Yours", "Swept", "Ground")
# Wrap widths per column, so the prose columns share the width instead of
# each taking the full CELL_WRAP and pushing the table off the screen.
LAND_WRAP = {"Why": 220, "Best bets": 230, "Known sites": 200, "Ground": 170}

LAND_FOOTNOTE = (
    "Est. value is an estimate, not a promise. It is the known sites still "
    "intact at what they carry, plus each location nobody has shared at what "
    "a site on that kind of ground usually carries, at the best prices known. "
    "What sites usually carry comes from everyone's shared finds once %d or "
    "more are logged on that ground, and from the commodity tables until "
    "then - Best bets says which." % SV.LAND_MIN_SITES)


def land_carrying(rows, commodity):
    """The Where to land rows for bodies that carry `commodity`, or all."""
    wanted = SV.fold(SV.canonical(commodity)) if commodity else ""
    if not wanted:
        return list(rows)
    return [row for row in rows if wanted in (row.get("carries") or [])]


class LandWindow(ctk.CTkToplevel):
    """Which body in this system to put the ship down on, best first.

    Fills in from the journal as the system is scanned - FSS, then the DSS -
    and from the community's shared sites when the server answers. Nothing
    has to be typed; leave it open while scanning and it keeps up.
    """

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("EDSMT - Where to land")
        width, height = screen_fraction(self, 0.82, 0.72, 1560, 900, 820, 460)
        self.geometry("%dx%d" % (width, height))
        self.minsize(780, 420)
        self.configure(fg_color=VOID)
        self.transient(app)

        self._rows = []
        self._shown_for = None
        self._sort_column, self._sort_reverse = None, False
        self.show_all = tk.BooleanVar(value=False)

        top = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        top.pack(fill="x", padx=12, pady=(12, 6))
        bracket(top, colour=ORANGE)
        self.heading = ctk.CTkLabel(top, text="Where to land", font=F_HEAD,
                                    text_color=AMBER, anchor="w",
                                    justify="left", wraplength=900)
        self.heading.pack(fill="x", anchor="w", padx=12, pady=(12, 2))
        self.summary = ctk.CTkLabel(top, text="", font=F_READOUT,
                                    text_color=TEXT, anchor="w",
                                    justify="left", wraplength=900)
        self.summary.pack(fill="x", anchor="w", padx=12, pady=(2, 6))

        buttons = ctk.CTkFrame(top, fg_color="transparent")
        buttons.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkButton(buttons, text="Copy all", width=100, height=32,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.copy_all).pack(side="right")
        ctk.CTkButton(buttons, text="Refresh", width=100, height=32,
                      font=F_STRONG, **BTN_PRIMARY,
                      command=self.refresh).pack(side="left")
        ctk.CTkSwitch(buttons, text="Include bodies you cannot land on",
                      variable=self.show_all, font=F_BODY,
                      command=self._paint, **SWITCH).pack(side="left",
                                                          padx=(14, 0))
        # Only the bodies that carry one commodity: what the ground is known
        # or expected to carry, and what has been found on it.
        ctk.CTkLabel(buttons, text="Carrying", font=F_BODY,
                     text_color=DIM).pack(side="left", padx=(14, 6))
        self.carrying = ctk.CTkComboBox(
            buttons, width=190, height=32, font=F_BODY, **BOX,
            values=["Any"] + list(SV.KNOWN_COMMODITIES),
            command=lambda _value: self._paint())
        self.carrying.set("Any")
        self.carrying.pack(side="left")

        # Bottom first, so a short window squeezes the table and never
        # pushes the footnote off the edge.
        self.footnote = ctk.CTkLabel(self, text=LAND_FOOTNOTE, font=F_SMALL,
                                     text_color=DIM, anchor="w",
                                     justify="left", wraplength=900)
        self.footnote.pack(side="bottom", fill="x", padx=14, pady=(0, 10))
        self.status = ctk.CTkLabel(self, text="", font=F_READOUT,
                                   text_color=DIM, anchor="w")
        self.status.pack(fill="x", padx=14, pady=(0, 4))
        self.scroller = ScrollTable(self)
        self.scroller.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self.table = self.scroller.inner
        for sequence in ("<MouseWheel>", "<Shift-MouseWheel>",
                         "<Button-4>", "<Button-5>"):
            self.bind(sequence, self.scroller.wheel, add="+")
        self.bind("<Configure>", self._rewrap, add="+")
        self.refresh()

    # -- keeping up ----------------------------------------------------------

    def refresh(self):
        """Ask the server again, and redraw from what is already known."""
        try:
            self._asked_for = self._system()
            self.app.want_landing(self._asked_for, force=True)
        except Exception:
            pass
        self._paint()

    def follow(self):
        """Called from the app's poll. Redraws only when something changed.

        A scan, a DSS map, an answer from the server or a jump all change
        what the table says; the other 99 polls in 100 change nothing and
        must not rebuild a table somebody may be scrolling.
        """
        try:
            system = self._system()
            if system and system != getattr(self, "_asked_for", None):
                self._asked_for = system
                self.app.want_landing(system)
            if self.app.land_signature(system) != self._shown_for:
                self._paint()
        except Exception:
            pass

    def _system(self):
        return str(getattr(self.app.watcher, "system", "") or "").strip()

    def _rewrap(self, event=None):
        """Long lines follow the window's width instead of a fixed one."""
        try:
            if event is not None and event.widget is not self:
                return
            wrap = max(400, self.winfo_width() - 60)
            for label in (self.heading, self.summary, self.footnote):
                label.configure(wraplength=wrap)
        except Exception:
            pass

    # -- drawing ------------------------------------------------------------

    def _paint(self):
        """Draw what is in hand. Must not raise."""
        table = attr(self, "table")
        if table is None:
            return
        try:
            system = self._system()
            self._shown_for = self.app.land_signature(system)
            self._rows = land_carrying(
                self.app.land_rows(system, landable_only=not self.show_all.get()),
                self._carrying())
            for widget in table.winfo_children():
                widget.destroy()
            self._summarise(system)
            rows = self._sorted(list(self._rows))
            if not rows:
                ctk.CTkLabel(table, text=self._advice(system), font=F_BODY,
                             text_color=DIM, justify="left",
                             wraplength=820).grid(row=0, column=0, padx=14,
                                                  pady=18, sticky="w")
                return
            self._headings()
            for index, row in enumerate(rows, start=1):
                self._row(index, row)
        except Exception as exc:
            self.say("Could not draw the list: %s" % exc, RED)

    def _summarise(self, system):
        if not system:
            self.heading.configure(text="Where to land")
            self.summary.configure(text="")
            return
        self.heading.configure(text="Where to land - %s" % system)
        bodies = self.app.watcher.system_bodies(system)
        landable = sum(1 for b in bodies if b.get("landable"))
        mapped = sum(1 for b in bodies if b.get("mapped"))
        sites = self.app.land_sites_for(system)
        parts = ["%d bod%s scanned" % (len(bodies), "y" if len(bodies) == 1 else "ies"),
                 "%d landable" % landable,
                 "%d mapped with the DSS" % mapped]
        if sites is None:
            parts.append("shared sites not loaded")
        else:
            parts.append("%d site(s) shared in this system" % len(sites))
        self.summary.configure(text=",  ".join(parts) + ".")
        problem = self.app.land_problem()
        if problem:
            self.say(problem, AMBER)
        elif self._rows:
            best = self._rows[0]
            if best["tier"] == 0:
                self.say("Best bet: %s - %s" % (best["short"], best["note"]), GREEN)
            else:
                self.say("Nothing known to be worth it yet - %s" % best["note"],
                         AMBER)
        else:
            self.say("")

    def _carrying(self):
        box = attr(self, "carrying", None)
        try:
            chosen = box.get().strip() if box is not None else ""
        except Exception:
            chosen = ""
        return "" if chosen.lower() in ("", "any") else chosen

    def _advice(self, system):
        if system and self._carrying():
            return ("No body scanned here is known or expected to carry %s.\n\n"
                    "Set Carrying back to Any to see them all." % self._carrying())
        if not system:
            return ("Waiting for the journal to say which system you are in.\n\n"
                    "This list fills itself in: jump in, honk, and every body "
                    "the scanner resolves appears here. Map one with the DSS "
                    "and its mining locations are counted.")
        return ("No landable body in %s has been scanned yet.\n\n"
                "Honk and use the FSS - each body appears here as it is "
                "resolved. Anything already shared by other commanders shows "
                "up as soon as the server answers." % system)

    def _headings(self):
        for column, name in enumerate(LAND_HEADERS):
            text = name
            if column == self._sort_column:
                text = "%s %s" % (name, "v" if self._sort_reverse else "^")
            ctk.CTkButton(self.table, text=text, font=F_SMALL_B,
                          **BTN_HEADING, anchor="w", height=24, width=0,
                          command=lambda c=column: self.sort_by(c)).grid(
                              row=0, column=DATA_COLUMN_0 + column,
                              padx=4, pady=4, sticky="w")
        ctk.CTkLabel(self.table, text="Copy", font=F_SMALL_B,
                     text_color=ORANGE).grid(row=0, column=COPY_COLUMN,
                                             padx=8, pady=5, sticky="w")

    def _row(self, index, row):
        for column, cell in enumerate(self._land_row(row)):
            text, colour, _key = EarningsWindow._cell(cell)
            cell_label(self.table, index, column, text, colour,
                       LAND_WRAP.get(LAND_HEADERS[column], CELL_WRAP))
        row_buttons(self.table, index,
                    [(label, lambda w=what, t=text: self.copy_text(w, t), False)
                     for label, what, text in self._copies(row)])

    @staticmethod
    def _land_row(row):
        """One body as cells, in LAND_HEADERS order, with sort keys."""
        tier_colour = {0: GREEN, 1: AMBER}.get(row["tier"], DIM)
        ls = row.get("distance_ls")
        gravity = row.get("gravity_g") or 0
        locations = row.get("locations")
        if locations is None:
            where = "not mapped"
        else:
            where = str(locations)
        bets = row.get("bets") or []
        if row.get("basis") == "tables":
            bet_text = ", ".join(name for name, _ in bets)
        else:
            bet_text = ", ".join("%s %d%%" % (name, round(share * 100))
                                 for name, share in bets)
        if bet_text and row.get("basis"):
            bet_text += "\n(%s)" % row["basis"]
        known = "-"
        if row.get("known"):
            known = "%d intact, %d rig(s)" % (row["intact"], row["known_rigs"])
            if row.get("worked"):
                known += ", %d worked out" % row["worked"]
            if row.get("verified"):
                known += ", %d verified" % row["verified"]
            if row.get("known_types"):
                known += "\n" + ", ".join(row["known_types"][:4])
        yours = "-"
        if row.get("yours") or row.get("your_deposits"):
            yours = "%d location(s), %d find(s)" % (row["yours"], row["your_deposits"])
            if row.get("your_worked"):
                yours += ", %d depleted" % row["your_worked"]
        swept = row.get("swept")
        return [
            (row["short"] or row["body"], tier_colour, row["short"].lower()),
            (credits_text(row["value"]) + " Cr" if row.get("value") else "-",
             tier_colour, row.get("value") or 0),
            (row.get("note") or "", tier_colour, row.get("tier", 3)),
            ("{:,.0f}".format(ls) if ls is not None else "-", None,
             ls if ls is not None else ""),
            (where, None if locations is not None else AMBER,
             locations if locations is not None else ""),
            (bet_text or "-", None, row.get("per_site") or ""),
            (known, GREEN if row.get("intact") else None, row.get("intact", 0)),
            (yours, None, row.get("your_deposits", 0)),
            ("%d%%" % swept if swept is not None else "-", None,
             swept if swept is not None else ""),
            # Gravity rides with the ground: it is what the SRV drives on -
            # and over the high-gravity line it says so, in red.
            ((row.get("ground") or "-")
             + ("\n%s%.2f g" % ("/!\\ HIGH G " if is_high_g(gravity) else "",
                                gravity) if gravity else ""),
             RED if is_high_g(gravity) else None),
        ]

    def _copies(self, row):
        return [("body", "the body name", row["body"]),
                ("row", "this body",
                 " | ".join(EarningsWindow._cell(c)[0].replace("\n", " ")
                            for c in self._land_row(row)))]

    # -- sorting and copying --------------------------------------------------

    def _sorted(self, rows):
        column = self._sort_column
        if column is None or not rows:
            return rows

        def key(row):
            cells = self._land_row(row)
            if column >= len(cells):
                return _sortable("")
            return EarningsWindow._cell(cells[column])[2]
        return sorted(rows, key=key, reverse=self._sort_reverse)

    def sort_by(self, column):
        try:
            if self._sort_column == column:
                self._sort_reverse = not self._sort_reverse
            else:
                self._sort_column, self._sort_reverse = column, False
            self._paint()
        except Exception as exc:
            self.say("Could not sort on that column: %s" % exc, RED)

    def copy_text(self, what, text):
        try:
            put_on_clipboard(self, text)
        except Exception as exc:
            return self.say("Could not reach the clipboard: %s" % exc, RED)
        self.say("Copied %s - %s" % (what, text.replace("\n", " ")), GREEN)

    def as_text(self):
        rows = self._sorted(list(self._rows))
        if not rows:
            return ""
        lines = ["Where to land - %s" % self._system(), " | ".join(LAND_HEADERS)]
        for row in rows:
            lines.append(" | ".join(EarningsWindow._cell(c)[0].replace("\n", " ")
                                    for c in self._land_row(row)))
        return "\n".join(lines)

    def copy_all(self):
        try:
            block = self.as_text()
        except Exception as exc:
            return self.say("Could not build that: %s" % exc, RED)
        if not block:
            return self.say("Nothing to copy yet.", AMBER)
        try:
            put_on_clipboard(self, block)
        except Exception as exc:
            return self.say("Could not reach the clipboard: %s" % exc, RED)
        self.say("Copied %d bod(ies) - paste it straight into Discord."
                 % (len(block.splitlines()) - 2), GREEN)

    def say(self, text, colour=None):
        colour = colour or DIM
        self.status.configure(text=text, text_color=colour)


def last_seen(row, now=None):
    """(words, days) for when a find was last reported, or ("-", None).

    The site's own last sighting when the server sends it - anyone standing
    on the patch since counts - and the find's first report when it does
    not. A date alone is arithmetic the reader should not have to do; a
    number of days alone hides which day. So: "3 days ago (2026-09-21)".
    """
    stamp = str(row.get("last_seen") or row.get("updated")
                or row.get("created") or row.get("recorded") or "").strip()
    if not stamp:
        return "-", None
    import calendar
    try:
        when = calendar.timegm(time.strptime(stamp[:19].replace("T", " "),
                                             "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        try:
            when = calendar.timegm(time.strptime(stamp[:10], "%Y-%m-%d"))
        except ValueError:
            return stamp[:10], None
    days = max(0.0, ((now if now is not None else time.time()) - when) / 86400.0)
    words = ("today" if days < 1 else "yesterday" if days < 2
             else "%d days ago" % days)
    return "%s (%s)" % (words, stamp[:10]), days


# -- the guide over the game --------------------------------------------------

# The steps, in the order a signal is worked. Each is (fact, title, detail):
# the fact is what the app can see once that step is done, so the guide moves
# on by itself and never asks for something already done. {keys} are filled
# from the keys actually bound.
GUIDE_STEPS = (
    ("honked", "JUMP IN AND HONK",
     "Jump to the system and fire the discovery scanner, so every body "
     "in it shows."),
    ("chosen", "CLICK WHERE TO LAND",
     "Click Where to land in EDSMT. It ranks this system's bodies for the "
     "Rhino - pick one and fly to it."),
    ("scanned", "MAP THE BODY",
     "Probe it with the DSS. Its mining locations show here."),
    ("signal", "PICK A SIGNAL",
     "Target a mining location. Its number goes in the Signal box - "
     "EDSMT fills it in when the game names it."),
    ("landed", "LAND AT THE SIGNAL",
     "Glide down and set down by the mining location."),
    ("rhino", "DEPLOY THE RHINO",
     "Out of glide and under 30 m: deploy the SRV."),
    ("centre", "LOG THE CENTRE  {location}",
     "Drive to the middle of the signal and press {location}. No "
     "commodities needed - they come with the deposits."),
    ("border", "SET THE BORDER  {border}",
     "Hold the mineral scanner down and keep holding it. Drive out to the "
     "location's edge line and press {border} there, then keep it held "
     "while you map the area.{from_centre}"),
    ("deposit", "MARK A DEPOSIT  {deposit}",
     "Drive to a deposit and fill in all four boxes - commodity, rigs, "
     "amount and density - then press {deposit}."),
    ("rigs", "PLACE RIGS  {rigs}",
     "One key per rig as it goes down: {rigs} is rigs 1 to 6. Its type goes "
     "on the scope and the compass."),
    ("again", "NEXT DEPOSIT",
     "{marked} marked at signal {signal}. Next one: {deposit}, then {rigs} "
     "for the rigs. {rigsup} picks each one up, {allup} is all of them."),
)

# How long the guide's last card stays up after the first full run, before
# the guide switches itself off.
GUIDE_FAREWELL_S = 30.0

# The Rhino deploys only below this, out of glide. From the testers, and the
# guide will not say DEPLOY until both are true.
DEPLOY_BELOW_M = 30.0


def guide_step(facts, keys=None):
    """The step the guide is on: {step, total, title, detail, next}.

    The step after the LAST fact that is true, not the first that is false:
    a commander who logs the centre before the game has said it is landed,
    or skips the border, is past those steps, and the guide says what comes
    after what they have actually done. The last step repeats - there is
    always another deposit.
    """
    facts = dict(facts or {})
    keys = dict(keys or {})
    words = {"location": "the LOG SIGNAL button", "border": "BORDER",
             "deposit": "MARK DEPOSIT", "rigs": "RIG DOWN",
             "allup": "RIGS UP", "rigsup": "its key", "marked": 0,
             "signal": "-", "from_centre": ""}
    words.update({k: v for k, v in keys.items() if v})
    words["marked"] = facts.get("marked", 0)
    words["signal"] = facts.get("signal_no") or "-"
    far = facts.get("from_centre_m")
    if far:
        words["from_centre"] = " You are %s from the centre." % _metres(far)
    done = -1
    for index, (fact, _title, _detail) in enumerate(GUIDE_STEPS[:-1]):
        if facts.get(fact):
            done = index
    step = min(done + 1, len(GUIDE_STEPS) - 1)
    fact, title, detail = GUIDE_STEPS[step]
    following = GUIDE_STEPS[step + 1][1] if step + 1 < len(GUIDE_STEPS) else ""
    # Coming down to the signal: the step does not say DEPLOY while you are
    # still gliding or too high - it says what is in the way.
    if fact == "landed":
        height = facts.get("altitude")
        if facts.get("gliding"):
            title = "GLIDING"
            detail = ("Ride the glide down. The Rhino only deploys once you "
                      "are out of glide and under %d m." % DEPLOY_BELOW_M)
        elif height is not None and height > DEPLOY_BELOW_M:
            detail = ("Down to under %d m - you are at %d m. Then deploy the "
                      "Rhino." % (DEPLOY_BELOW_M, int(round(height))))

    def fill(text):
        try:
            return text.format(**words)
        except (KeyError, IndexError, ValueError):
            return text
    return {"step": step + 1, "total": len(GUIDE_STEPS), "title": fill(title),
            "detail": fill(detail), "next": fill(following).split("  ")[0]}


# -- where to sell what is aboard ---------------------------------------------

# How many of the commodities aboard get a price asked for, and how far apart
# the asks go. The server lets one call through to the market index a second
# and answers the rest from its own users alone, so five asks fired together
# came back with the index missing from four of them.
QUOTE_MAX = 5
QUOTE_GAP_MS = 1300
# A quote is for the system it was asked from. Older than this, or asked from
# somewhere else, and the strip stops quoting it.
QUOTE_FRESH_S = 30 * 60
QUOTE_DISTANCES = {"25 Ly": 25, "50 Ly": 50, "100 Ly": 100, "250 Ly": 250,
                   "500 Ly": 500}
DEFAULT_QUOTE_DISTANCE = "100 Ly"
# The worker tag for these, routed to the app rather than the Find window.
QUOTE_TAG = "hold-sell"


def combined_hold(holds, cargo=None):
    """Ship and SRV added together, {name: tonnes}.

    The reader keeps both holds; the older single-vessel view is the
    fallback, so this still answers against a reader that has only that.
    """
    total = {}
    sources = list(dict(holds or {}).values()) or [dict(cargo or {})]
    for hold in sources:
        for name, count in dict(hold or {}).items():
            try:
                count = int(count or 0)
            except (TypeError, ValueError):
                continue
            if count > 0:
                total[name] = total.get(name, 0) + count
    return total


def worth_asking(counts, limit=QUOTE_MAX):
    """The commodities aboard worth a price lookup, most valuable first.

    Valued at the published average only to put them in order - a tonne of
    Sapphire is asked about before forty of Haematite. Anything with no
    published figure still gets asked about, after the rest.
    """
    ranked = sorted(dict(counts or {}).items(),
                    key=lambda pair: (-(SV.published_price(pair[0]) * pair[1]),
                                      -pair[1], pair[0]))
    return [name for name, count in ranked if count > 0][:limit]


def read_quote(payload, system):
    """(commodity, best, here) out of a /v1/sell answer.

    best is the highest price anywhere in the answer. here is the highest in
    the system the commander is in, which is the number that says whether
    the drive to the better one is worth it - Joey in HR 7280 needs to see
    HR 7280's price beside Ten Mandi's, not just Ten Mandi's.
    """
    data = json.loads(payload) if isinstance(payload, str) else dict(payload)
    rows = []
    for row in list(data.get("market") or []) + list(data.get("community") or []):
        if not isinstance(row, dict):
            continue
        try:
            price = int(row.get("sell") or 0)
            demand = int(row.get("demand") or 0)
        except (TypeError, ValueError):
            continue
        # Demand 999,999 is a Community Goal's placeholder, not a market -
        # and it is where the inflated "best" prices came from.
        if price > 0 and demand != PLACEHOLDER_DEMAND:
            rows.append(dict(row, sell=price))
    commodity = SV.canonical(data.get("commodity") or "")
    best = max(rows, key=lambda r: r["sell"], default=None)
    folded = SV.fold(system)
    here = max((r for r in rows if folded and SV.fold(r.get("system")) == folded),
               key=lambda r: r["sell"], default=None)
    return commodity, best, here


def quote_where(row):
    """"Station, System (8.2 Ly)" for a price row, whatever it carries."""
    if not row:
        return "-"
    place = ", ".join(str(part) for part in (row.get("station"),
                                             row.get("system")) if part)
    far = row.get("distance_ly")
    if far is None:
        far = row.get("distance")
    try:
        place += " (%s Ly)" % _round(float(far), 1)
    except (TypeError, ValueError):
        pass
    return place or "-"


def _round(value, places=1):
    try:
        return ("%%.%df" % places) % float(value)
    except (TypeError, ValueError):
        return "-"


# ---------------------------------------------------------------------------
# My sites - everywhere you have logged a signal or marked a find
# ---------------------------------------------------------------------------

SITES_HEADERS = ("System", "Body", "Signal", "What is there", "Finds", "Rigs",
                 "Mined", "Last there")
SITES_WRAP = {"What is there": 300}
SITES_FOOTNOTE = ("Your own records, on this PC - every body, not just the one "
                  "you are on. Copy a system name and paste it into the "
                  "galaxy map to plot a route back. Rigs counts the rigs still "
                  "to be had at deposits not marked Depleted; Mined is the "
                  "tonnes refined there.")


def site_cells(site, here=("", "")):
    """One of Survey.sites() as table cells, in SITES_HEADERS order."""
    at = (SV.fold(site["system"]) == SV.fold(here[0])
          and SV.fold(site["body"]) == SV.fold(here[1]))
    colour = GREEN if at else None
    types = sorted(site["types"].items(), key=lambda kv: (-kv[1], kv[0].lower()))
    there = ", ".join("%s x%d" % (name, n) if n > 1 else name
                      for name, n in types)
    waiting = [c for c in site["offers"]
               if c not in site["types"] and c not in site["depleted"]]
    if waiting:
        there = (there + "\n" if there else "") + "offers " + ", ".join(waiting)
    if site["depleted"]:
        there = (there + "\n" if there else "") + "worked out: " + \
            ", ".join(site["depleted"])
    finds = "-"
    if site["finds"]:
        finds = str(site["finds"])
        if site["intact"] != site["finds"]:
            finds += " (%d depleted)" % (site["finds"] - site["intact"])
    tonnes = sum(site["mined"].values())
    when, days = last_seen({"recorded": site["last"]})
    return [
        (site["system"], colour, site["system"].lower()),
        (site["body"] + ("  (here)" if at else ""), colour, site["body"].lower()),
        (site["signal"] or "-", colour, site["signal"]),
        (there or "-", None, there.lower()),
        (finds, None, site["finds"]),
        (str(site["rigs"]) if site["rigs"] else "-", None, site["rigs"]),
        ("%dt" % tonnes if tonnes else "-", None, tonnes),
        (when, None, days if days is not None else 1e9),
    ]


def sites_matching(sites, text):
    """The sites whose system, body, signal or commodities hold `text`."""
    wanted = SV.fold(text)
    if not wanted:
        return list(sites)
    out = []
    for site in sites:
        words = [site["system"], site["body"], site["signal"]] + \
            list(site["types"]) + list(site["offers"])
        if any(wanted in SV.fold(word) for word in words):
            out.append(site)
    return out


class SitesWindow(ctk.CTkToplevel):
    """Everywhere you have logged a signal or marked a find, on any body.

    Asked for by a tester: "how to find a list of the planets and spots I've
    logged ... so I can return to them". The main window shows the body you
    are on and nothing else, and Find searches what everybody has shared -
    neither answers it.
    """

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("EDSMT - My sites")
        width, height = screen_fraction(self, 0.8, 0.7, 1500, 880, 820, 440)
        self.geometry("%dx%d" % (width, height))
        self.minsize(760, 400)
        self.configure(fg_color=VOID)
        self.transient(app)

        self._sites, self._rows = [], []
        self._sort_column, self._sort_reverse = None, False

        top = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        top.pack(fill="x", padx=12, pady=(12, 6))
        bracket(top, colour=ORANGE)
        hud_header(top, "My sites", padx=12, pady=(12, 4))
        self.summary = ctk.CTkLabel(top, text="", font=F_READOUT,
                                    text_color=TEXT, anchor="w",
                                    justify="left", wraplength=900)
        self.summary.pack(fill="x", anchor="w", padx=12, pady=(2, 6))
        row = ctk.CTkFrame(top, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkButton(row, text="Copy all", width=100, height=32,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.copy_all).pack(side="right")
        ctk.CTkButton(row, text="Refresh", width=100, height=32,
                      font=F_STRONG, **BTN_PRIMARY,
                      command=self.refresh).pack(side="left")
        ctk.CTkLabel(row, text="Filter", font=F_BODY,
                     text_color=DIM).pack(side="left", padx=(14, 6))
        self.filter_box = ctk.CTkEntry(row, width=260, height=32, font=F_BODY,
                                   placeholder_text="system, body or commodity",
                                   **ENTRY)
        self.filter_box.pack(side="left")
        self.filter_box.bind("<KeyRelease>", lambda _e: self._paint(), add="+")

        self.footnote = ctk.CTkLabel(self, text=SITES_FOOTNOTE, font=F_SMALL,
                                     text_color=DIM, anchor="w",
                                     justify="left", wraplength=900)
        self.footnote.pack(side="bottom", fill="x", padx=14, pady=(0, 10))
        self.status = ctk.CTkLabel(self, text="", font=F_READOUT,
                                   text_color=DIM, anchor="w")
        self.status.pack(fill="x", padx=14, pady=(0, 4))
        self.scroller = ScrollTable(self)
        self.scroller.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self.table = self.scroller.inner
        for sequence in ("<MouseWheel>", "<Shift-MouseWheel>",
                         "<Button-4>", "<Button-5>"):
            self.bind(sequence, self.scroller.wheel, add="+")
        self.bind("<Configure>", self._rewrap, add="+")
        self.refresh()

    def refresh(self):
        """Read the records again - a find marked since opening shows up."""
        try:
            self._sites = self.app.store.sites()
        except Exception as exc:
            self._sites = []
            self.say("Could not read your records: %s" % exc, RED)
        self._paint()

    def _here(self):
        try:
            system, body = self.app.here()
            return system or "", body or ""
        except Exception:
            return "", ""

    def _rewrap(self, event=None):
        try:
            if event is not None and event.widget is not self:
                return
            wrap = max(400, self.winfo_width() - 60)
            for label in (self.summary, self.footnote):
                label.configure(wraplength=wrap)
        except Exception:
            pass

    def _paint(self):
        """Draw what is in hand. Must not raise."""
        table = attr(self, "table")
        if table is None:
            return
        try:
            shown = sites_matching(self._sites, self.filter_box.get())
            self._rows = self._sorted(shown)
            for widget in table.winfo_children():
                widget.destroy()
            self._summarise(shown)
            if not self._rows:
                ctk.CTkLabel(table, text=self._advice(), font=F_BODY,
                             text_color=DIM, justify="left",
                             wraplength=820).grid(row=0, column=0, padx=14,
                                                  pady=18, sticky="w")
                return
            self._headings()
            self._drawn, self._more_button = 0, None
            self._draw_page()
            self.scroller.top()
        except Exception as exc:
            self.say("Could not draw the list: %s" % exc, RED)

    def _draw_page(self):
        """The next PAGE_ROWS sites, and a button for the rest. A commander
        with a few hundred signals logged got every one drawn at once."""
        rows = attr(self, "_rows", None) or []
        start = attr(self, "_drawn", 0) or 0
        more = attr(self, "_more_button", None)
        if more is not None:
            try:
                more.destroy()
            except Exception:
                pass
            self._more_button = None
        here = self._here()
        end = min(len(rows), start + PAGE_ROWS)
        for index in range(start, end):
            self._row(index + 1, rows[index], here)
        self._drawn = end
        left = len(rows) - end
        if left > 0:
            self._more_button = ctk.CTkButton(
                self.table, text="Show %d more  (%d not drawn yet)"
                % (min(PAGE_ROWS, left), left),
                font=F_STRONG, **BTN_SECONDARY, height=30,
                command=self._draw_page)
            self._more_button.grid(row=end + 1, column=DATA_COLUMN_0,
                                   columnspan=4, padx=8, pady=10, sticky="w")

    def _summarise(self, shown):
        sites = self._sites
        bodies = {(SV.fold(s["system"]), SV.fold(s["body"])) for s in sites}
        systems = {SV.fold(s["system"]) for s in sites}
        text = "%d signal(s) on %d bod%s in %d system(s)." % (
            len(sites), len(bodies), "y" if len(bodies) == 1 else "ies",
            len(systems))
        if len(shown) != len(sites):
            text += "  %d match the filter." % len(shown)
        self.summary.configure(text=text)

    def _advice(self):
        if self._sites:
            return "Nothing matches that filter. Clear it to see them all."
        return ("Nothing logged yet.\n\nDrive into a mining signal and press "
                "%s to log it, or %s on a deposit to mark a find - every one "
                "of them is listed here, whichever body it is on."
                % (bound_key(getattr(self.app, "settings", None), "location",
                             "LOG SIGNAL"),
                   bound_key(getattr(self.app, "settings", None), "deposit",
                             "MARK DEPOSIT")))

    def _headings(self):
        for column, name in enumerate(SITES_HEADERS):
            text = name
            if column == self._sort_column:
                text = "%s %s" % (name, "v" if self._sort_reverse else "^")
            ctk.CTkButton(self.table, text=text, font=F_SMALL_B,
                          **BTN_HEADING, anchor="w", height=24, width=0,
                          command=lambda c=column: self.sort_by(c)).grid(
                              row=0, column=DATA_COLUMN_0 + column,
                              padx=4, pady=4, sticky="w")
        ctk.CTkLabel(self.table, text="Copy", font=F_SMALL_B,
                     text_color=ORANGE).grid(row=0, column=COPY_COLUMN,
                                             padx=8, pady=5, sticky="w")

    def _row(self, index, site, here):
        cells = site_cells(site, here)
        for column, cell in enumerate(cells):
            text, colour, _key = EarningsWindow._cell(cell)
            cell_label(self.table, index, column, text, colour,
                       SITES_WRAP.get(SITES_HEADERS[column], CELL_WRAP))
        line = " | ".join(EarningsWindow._cell(c)[0].replace("\n", " ")
                          for c in cells)
        row_buttons(self.table, index, [
            ("system", lambda s=site["system"]: self.copy_text(
                "the system name", s), False),
            ("row", lambda s=line: self.copy_text("this site", s), False)])

    def _sorted(self, sites):
        column = self._sort_column
        here = self._here()
        if column is None or not sites:
            # Where you are first, then the most recent: the body you are on
            # is the one you opened this to look at more often than not.
            at = (SV.fold(here[0]), SV.fold(here[1]))
            return sorted(sites, key=lambda site: (SV.fold(site["system"]),
                                                   SV.fold(site["body"])) != at)

        def key(site):
            return EarningsWindow._cell(site_cells(site, here)[column])[2]
        return sorted(sites, key=key, reverse=self._sort_reverse)

    def sort_by(self, column):
        try:
            if self._sort_column == column:
                self._sort_reverse = not self._sort_reverse
            else:
                self._sort_column, self._sort_reverse = column, False
            self._paint()
        except Exception as exc:
            self.say("Could not sort on that column: %s" % exc, RED)

    def copy_text(self, what, text):
        try:
            put_on_clipboard(self, text)
        except Exception as exc:
            return self.say("Could not reach the clipboard: %s" % exc, RED)
        self.say("Copied %s - %s" % (what, text.replace("\n", " ")), GREEN)

    def as_text(self):
        if not self._rows:
            return ""
        here = self._here()
        lines = ["My sites", " | ".join(SITES_HEADERS)]
        for site in self._rows:
            lines.append(" | ".join(EarningsWindow._cell(c)[0].replace("\n", " ")
                                    for c in site_cells(site, here)))
        return "\n".join(lines)

    def copy_all(self):
        block = self.as_text()
        if not block:
            return self.say("Nothing to copy yet.", AMBER)
        self.copy_text("%d site(s)" % (len(block.splitlines()) - 2), block)

    def say(self, text, colour=None):
        colour = colour or DIM
        self.status.configure(text=text, text_color=colour)


def _sortable(value):
    """A key that sorts a column of table cells the way a person expects.

    Every cell in a column has to produce the same shape of key or the
    comparison raises, so this is always a 3-tuple. Numbers come out in
    the first slot and sort ahead of words, which puts "-" and a blank at
    the bottom of a numeric column rather than scattered through it -
    6 rigs, 2 rigs, then the ones nobody filled in.
    """
    if isinstance(value, bool):
        return (1, 0.0, str(value).lower())
    if isinstance(value, (int, float)):
        return (0, float(value), "")
    raw = str(value).replace(",", "").strip()
    try:
        return (0, float(raw), "")
    except ValueError:
        return (1, 0.0, raw.lower())


# One copy at a time. The installer asks for this same name (AppMutex in
# installer.iss), so an update waits for EDSMT to be closed instead of
# replacing it underneath itself.
INSTANCE_NAME = "RadioRaxxla.EDSMT.Running"
_INSTANCE = {}


def claim_single_instance():
    """True if this is the only copy running.

    Two copies share one data folder and each believes its settings and
    finds are the real ones. Whichever closes last wins, and the loser's
    changes - or, with the old loader, everything - are gone. That is what
    running the source copy beside the installed one does.

    A Windows named mutex rather than a lock file: Windows releases it
    when the process ends however it ends, so a crash never leaves the app
    refusing to start. Elsewhere, an advisory lock on a file.
    """
    if os.name == "nt":
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateMutexW.restype = ctypes.c_void_p
            kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool,
                                              ctypes.c_wchar_p)
            handle = kernel32.CreateMutexW(None, False, INSTANCE_NAME)
            already = ctypes.get_last_error() == 183    # ERROR_ALREADY_EXISTS
            _INSTANCE["handle"] = handle                  # held until exit
            return not already
        except Exception:
            return True
    try:
        import fcntl
        handle = open(os.path.join(DATA_DIR, ".instance.lock"), "w")
    except (ImportError, OSError):
        return True
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return False
    except OSError:
        return True
    _INSTANCE["handle"] = handle
    return True


def release_single_instance():
    """Let go of the one-copy lock, for an update that starts a new copy."""
    handle = _INSTANCE.pop("handle", None)
    if handle is None:
        return
    try:
        if os.name == "nt":
            ctypes.WinDLL("kernel32").CloseHandle(ctypes.c_void_p(handle))
        else:
            handle.close()
    except Exception:
        pass


def already_running():
    """Tell them, rather than open a second window that quietly fights the
    first over the same files."""
    try:
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        messagebox.showinfo(APP_TITLE, "EDSMT is already running.\n\n"
                            "Look for it on the taskbar. Only one copy runs "
                            "at a time, so your finds and settings are never "
                            "written by two copies at once.")
        root.destroy()
    except Exception:
        pass


def report_crash(exc):
    """No console when installed, so write a log and say something."""
    import traceback
    detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    log = os.path.join(DATA_DIR, "crash.log")
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(log, "a", encoding="utf-8") as handle:
            handle.write("\n--- %s %s ---\n%s"
                         % (APP_VERSION, SV.utc_now(), detail))
    except OSError:
        pass
    try:
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        messagebox.showerror(APP_TITLE,
                             "%s: %s\n\nDetails written to:\n%s"
                             % (type(exc).__name__, exc, log))
        root.destroy()
    except Exception:
        print(detail)


if __name__ == "__main__":
    if not claim_single_instance():
        already_running()
        raise SystemExit(0)
    tidy_after_update()
    try:
        window = EDSMT()
        icon = os.path.join(getattr(sys, "_MEIPASS", app_dir()), "radioraxxla.ico")
        if os.path.exists(icon):
            try:
                window.iconbitmap(icon)
            except Exception:
                pass
        window.mainloop()
    except Exception as exc:
        report_crash(exc)
        raise SystemExit(1)
