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
import guidance as GD
import bodybook as BB
import mapimage as MI
import shiphold as SH
import sessionledger as SL
import supportbundle as SB
import finder as FD
import powerplay as PW
import sellplan as SP
import chattags as CT
import inputdev as IND
import inputmix as IM
import importers as IMP
import regrowth as RG
import sitebook as SBK
import markerfilter as MF
import board as LB
import crowd as CR
import presale as PS
import gamebinds as GB
import galaxy as GX
import zone as ZN
import gametheme as GT
import x11keys as XK

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


def refresh_game_theme(**where):
    """Read what the game's HUD is coloured right now and make it the "game"
    theme (1.10039, #287). Called before the window is dressed, so a
    commander on the game theme starts in today's colours, and again from
    the Theme tab's Match button. `where` names stand-in folders for the
    checks. Never raises: a broken file leaves the standard orange."""
    try:
        found = GT.read_game_theme(**where)
    except Exception as exc:
        found = {"source": "standard", "file": "", "matrix": None, "accent": None,
                 "palette": GT.standard_palette(),
                 "words": "The game is on its standard colours (the game's files "
                          "could not be read: %s)." % exc}
    OV.set_game_palette(found["palette"])
    return found


MAX_RIGS = 6

# How often another commander's finds on the body you are on are asked for
# again, and how long an unanswered ask waits before trying once more.
SHARED_REFRESH_S = 600
# 1.10035: how long the arrival line waits for the shared sites, how long
# the unmarked-refine prompt stays, and how many finds an import sends at
# once.
ARRIVAL_WAIT_S = 6.0
REFINE_PROMPT_S = 90.0
IMPORT_SHARE_BATCH = 100
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
# so this is tighter than being "at" a signal. One figure with zone.py, which
# uses it to let your own centre win over a shared one (1.10038).
SAME_SIGNAL_M = ZN.ZONE_OWN_M
# ...and UPDATE does the rename for this long after the question.
RETYPE_WAIT_S = 60.0

# How wide one table cell may get before its text wraps, in pixels. Enough
# for a system name like "Col 285 Sector ZL-K b22-2" on one line.
CELL_WRAP = 260

# Rows a result table draws at a time. Five hundred individual deposits,
# each a dozen toolkit widgets, took long enough to draw that the window
# looked hung. A page appears at once; the rest are one click away.
PAGE_ROWS = 100
# Staff "remove" in Find needs a second press within this many seconds.
REMOVE_CONFIRM_S = 6.0
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
# Within this of one of your own rigs (1.10034): COLLECT RIG n on the boxes.
# Not for a rig dropped in the last RIG_COLLECT_AFTER_S - the Rhino is
# sitting on the rig it has just put down.
RIG_COLLECT_M = 6.0
RIG_COLLECT_AFTER_S = 120.0
# Where a rig lands, behind the cockpit Status.json places: the community's
# measured 7 m. A setting, 0 to RIG_OFFSET_MAX_M.
RIG_OFFSET_M = 7.0
RIG_OFFSET_MAX_M = 20.0
RIGS_FILE_NAME = "rigs.json"
# Shared rig layouts are asked for again after this long on one signal.
LAYOUTS_REFRESH_S = 900.0
# The most points of a traced edge sent with a layout.
LAYOUT_OUTLINE_MAX = 400
# The rig planner. A rig within PLAN_PIN_DONE_M of a pin is on it;
# the scope closes in on the plan while any pin is within PLAN_NEAR_M; a
# trace not closed in PLAN_TRACE_MAX_S is given up on.
PLAN_PIN_DONE_M = 20.0
PLAN_NEAR_M = 600.0
PLAN_TRACE_MAX_S = 20 * 60
PLAN_SPACING_MIN_M = 20.0
PLAN_SPACING_MAX_M = 500.0
# The rig radar (1.10035) only holds a rig to a traced deposit edge when you
# are inside it or within this of it - on another deposit it is not yours to
# be told about. And the colours the map draws its new layers in: gold for
# the golden groups, a light teal for the driven trail.
RADAR_PLAN_REACH_M = 150.0
GOLD = OV.GOLD
TRAIL_LINE = OV.TRAIL_COLOUR
# The wing link (beta): a beat every WING_BEAT_S; a wingmate not heard from
# for WING_STALE_S is taken off the scope. A code is six characters; the
# ones EDSMT makes up leave out I, O, 0 and 1, which are read out wrong.
WING_BEAT_S = 4.0
# A second press on the same Earnings row inside this long deletes it.
DELETE_CONFIRM_S = 6
# With two Rhinos' rigs down, RIGS UP takes up the rigs of the Rhino you are
# in; pressed again inside this long it takes up the other Rhino's as well.
RIGS_ALL_CONFIRM_S = 6
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
# Past this from wherever you are - ship, on foot or Rhino - the rigs are
# behind you: forgotten, and every warning about them with them (1.10034).
RIG_FORGET_M = 6000.0
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
# An open Session earnings window redraws its current session this often
# (1.10035) - the clock and the tonnes move while you mine.
LEDGER_LIVE_S = 5.0
# The Inara key and the staff token are shown as this until Show is pressed,
# and go back to it by themselves this many seconds later.
MASK = "•"
REVEAL_S = 20
DATA_COLUMN_0 = 1

# How many rows a page of a search asks for. 50 was the client default and
# the only thing the user ever saw. Since 1.10036 this is only the first
# page: Find asks for every page after it (edonline.every_page), so a
# search is never cut off at 500 - only at EDO.CommunityClient.ALL_ROWS.
SEARCH_LIMIT = 500

# How far out to look for somebody else's find. The galaxy has roughly 400
# billion systems in it, so an unbounded search does not return the best
# site - it returns the best site in a place nobody will ever travel to.
# 500 Ly is a couple of minutes in a jump-capable ship and roughly the
# distance a commander will actually move to reach a good patch.
DISTANCE_CHOICES = {
    "25 Ly": 25, "50 Ly": 50, "100 Ly": 100, "200 Ly": 200, "250 Ly": 250,
    "500 Ly": 500, "1000 Ly": 1000, "Anywhere": 0,
}
DEFAULT_DISTANCE = "500 Ly"
NO_DISTANCE_LIMIT = "Anywhere"

# Who broke it before anyone else had to. Kept as a constant so adding the
# next name is one line and never touches the window code.
BETA_TESTERS = [
    "CMDR MJH430", "CMDR StarTopaz", "CMDR Flossy", "CMDR Gamer Joe",
    "CMDR Rumphrend", "CMDR Todd Jenkins",
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
             "commodities", "verify", "remove", GX.TAG)

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


# The Rhino, shown on the first-run window and in Settings > About EDSMT.
# Screenshot by CMDR TheAnnouncer; Elite Dangerous (c) Frontier Developments plc.
WELCOME_PICTURE = "rhino-banner.png"
ABOUT_PICTURE = "rhino-about.png"
# The first-run window's size, with the picture across its top and without.
WELCOME_SIZE, WELCOME_SIZE_PLAIN = (560, 620), (560, 460)


def picture(name, master=None):
    """A picture shipped with the app, as a Tk image, or None.

    From the bundle when frozen - the images folder beside the sounds - and from
    the images folder beside the source otherwise. A file that is missing or will not
    load is not an error: the window is simply laid out without it, because
    a decoration is never a reason for a window not to open."""
    path = os.path.join(getattr(sys, "_MEIPASS", app_dir()), "images", name)
    try:
        if os.path.isfile(path):
            return tk.PhotoImage(master=master, file=path)
    except Exception:
        pass
    return None


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


def local_number(text):
    """A number as a person types it, a decimal comma included (#275).

    "3,95" is 3.95 and "1.234,5" is 1234.5 - Windows in most of Europe
    writes them that way. "3,950" (a comma before exactly three digits) is
    still three thousand nine hundred and fifty, and "1,234.5" is what it
    always was. Raises ValueError for anything that is not a number."""
    raw = str(text if text is not None else "").strip()
    raw = raw.replace(" ", "").replace("\u00a0", "").replace("\u202f", "")
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif raw.count(",") == 1:
        whole, frac = raw.split(",")
        digits = whole.lstrip("+-")
        if len(frac) == 3 and digits.isdigit() and digits.lstrip("0"):
            raw = whole + frac
        else:
            raw = whole + "." + frac
    elif raw.count(",") > 1:
        raw = raw.replace(",", "")
    return float(raw)


_PAIR_NUMBER = re.compile(r"[+-]?\d+(?:[.,]\d+)?")


def read_pair(text):
    """Latitude and longitude from "12.34567, -45.6789", and from the same
    with decimal commas, "12,34567; -45,6789" or "12,34567, -45,6789".
    Raises ValueError when it is not two numbers."""
    found = _PAIR_NUMBER.findall(str(text or ""))
    if len(found) == 1 and found[0].count(",") == 1:
        found = found[0].split(",")
    if len(found) != 2:
        raise ValueError("not a latitude and a longitude")
    # Inside one coordinate a comma is only ever the decimal point.
    return float(found[0].replace(",", ".")), float(found[1].replace(",", "."))


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
    try:
        value = local_number(raw)
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
        # Linux (1.10039): $XDG_DATA_HOME, which the base directory
        # specification says is ~/.local/share when unset or empty.
        root = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share")
        path = os.path.join(root, "RadioRaxxla", "EDSMT")
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

# Before every INSTALL UPDATE the finds, sessions and settings are backed up
# (#143: "REMIND PEOPLE TO BACKUP SETTINGS BEFORE THEY UPDATE"). Into
# Documents, where people look, not AppData, where they do not. The newest
# AUTO_BACKUPS_KEPT of THESE are kept; a backup made by hand is never
# touched. A backup that cannot be written stops the install, and pressing
# INSTALL UPDATE again within UPDATE_NO_BACKUP_S goes ahead without one.
AUTO_BACKUP_PREFIX = "EDSMT-before-update-"
AUTO_BACKUPS_KEPT = 10
UPDATE_NO_BACKUP_S = 30


def documents_dir():
    """The commander's Documents folder, wherever Windows keeps it - which,
    with OneDrive, is not always under the profile."""
    if os.name == "nt":
        try:
            path = ctypes.c_wchar_p()
            # FOLDERID_Documents {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
            guid = (ctypes.c_ubyte * 16)(*bytes.fromhex(
                "D09AD3FD8F23AF46ADB46C85480369C7"))
            shell = ctypes.windll.shell32
            if shell.SHGetKnownFolderPath(ctypes.byref(guid), 0, None,
                                          ctypes.byref(path)) == 0:
                folder = path.value
                ctypes.windll.ole32.CoTaskMemFree(path)
                if folder:
                    return folder
        except Exception:
            pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def backups_dir():
    """Where the automatic backups go: Documents > EDSMT backups."""
    return os.path.join(documents_dir(), "EDSMT backups")


def tidy_auto_backups(folder, keep=AUTO_BACKUPS_KEPT):
    """Keep the newest `keep` automatic backups in `folder`. Only files
    this made are ever removed - a backup made by hand is never touched."""
    try:
        mine = sorted((name for name in os.listdir(folder)
                       if name.startswith(AUTO_BACKUP_PREFIX)
                       and name.endswith(".zip")),
                      key=lambda name: os.path.getmtime(os.path.join(folder, name)))
    except OSError:
        return 0
    gone = 0
    for name in mine[:max(0, len(mine) - keep)]:
        try:
            os.remove(os.path.join(folder, name))
            gone += 1
        except OSError:
            pass
    return gone

# The key that turns the overlay on and off. Not bound by the game's own
# schemes, by Windows or by the overlays that grab keys - the same checks as
# the work keys beside it (OV.WORK_KEYS).
OVERLAY_KEY = "ALT+0"
# The scope's zoom step, 1x then 2x then 4x then 1x again (1.10035). Alt+minus
# sits beside Alt+0 and is on no overlay's, no driver's and no Windows list.
SCOPE_ZOOM_KEY = "ALT+-"

DEFAULT_SETTINGS = {
    "_readme": "Everything here has a Settings window in the app.",
    "inara_enabled": False,
    "inara_api_key": "",
    "inara_is_being_developed": False,
    # Your own Discord channel (1.10034): a webhook you made in the
    # channel's Integrations, and what goes to it. Blank sends nothing.
    "discord_webhook": "",
    # 1.10035: one summary a session, and every find only if asked for -
    # a post per find was a channel nobody could read.
    "discord_post_finds": False,
    "discord_post_sessions": True,
    "discord_finds_level": 1,
    # 1.10035: the map picture saved when the Rhino docks, sent with the
    # summary, and the summary edited (not posted again) after the sale.
    "map_picture_auto": True,
    "discord_attach_map": True,
    "discord_edit_after_sale": True,
    # Every find is shared with every commander, always (October 2026: "we
    # do not hold back on that information"). These three are no longer
    # choices - ALWAYS_SHARED puts them back on in any file that says
    # otherwise. Your CMDR name on them is still yours to give or not.
    "community_enabled": True,
    # The address is fixed in edonline; this key is kept only so that older
    # settings files read the same way.
    "community_url": "https://api.radioraxxla.com",
    # Whether the share question has been put to this commander yet. The
    # database is only worth searching if people contribute to it, and a
    # setting nobody is ever shown is a setting nobody ever turns on.
    "asked_to_share": False,
    "community_token": "",
    "community_share_cmdr_name": True,
    # The community leaderboard (1.10036). Everyone is on it - the names are
    # on the finds already - and Leave in its window takes a commander off.
    "leaderboard_optin": True,
    # Find, My sites, Where to land, Earnings, Powerplay and Leaderboard as
    # tabs of the main window (1.10036, #147). Off: a window each, as before.
    "tools_as_tabs": True,
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
    # The overlay on and off from the game, without reaching for EDSMT's
    # window (asked for on the forum). Alt+0, next to the work keys.
    "hotkey_overlay": OVERLAY_KEY,
    "hotkey_zoom": SCOPE_ZOOM_KEY,
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
    # The rig planner: drive the deposit's edge after this key and the pins
    # for the rigs come out of it.
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
    # 1.10035: any of the keys above can also be a joystick or HOTAS button,
    # stored the way it is written on screen ("JOY1 B7"). Blank is no button.
    **{IND.joy_key(action): "" for action in IND.JOY_ACTIONS},
    # 1.10035: commands typed in the game's chat. Off: local chat is public,
    # so a command typed there is read by everyone near you.
    "chat_tags": False,
    "chat_prefix": CT.DEFAULT_PREFIX,
    # 1.10035: a mouse button held for two seconds counts as a rig placed.
    # Which button: left, right, or learn (the first one held that long).
    "long_press_rig": False,
    # 1.10036: "primary" or "secondary" - the game's own SRV fire binding,
    # read from the commander's .binds. Older "left"/"right"/"learn" read as
    # primary/secondary/primary (inputmix.fire_choice).
    "long_press_button": "primary",
    "long_press_learned": "",
    # The game says "approaching mining rig maximum operational range" at
    # about 4 km, and a rig drops off the SRV's Contacts at about 2.9 km -
    # both measured in the game. 3.5 km warns before the game does.
    "rig_warn_m": 3500,
    "rig_warn_sound": True,
    # A body at or over this surface gravity gets the big warning when you
    # arrive at it, and a red bar on the GUIDE and STATUS boxes while you are
    # there. In g, as the game shows it. 0 turns it off.
    "high_g_warn": 1.2,
    # Light years a jump, for "sell within N jumps" (1.10035). 0 takes the
    # range from the ship's own Loadout.
    "jump_range_ly": 0,
    # The Earnings page last on show (1.10038): This session, Where to
    # sell, Sessions or System prices.
    "earnings_page": "This session",
    # Which warning to play: the clean one, or the one with language in it.
    "rig_sound_profane": True,
    # The scanner's reach, and how much neighbouring drive circles overlap.
    # Settings rather than constants: they are measured by the community,
    # not published, and a better number should not need a new build.
    "survey_scan_m": 2000,
    "survey_overlap_m": 250,
    # The in-game overlay. Off until asked for: it puts a window over the
    # game, and that should never be a surprise.
    "overlay_enabled": False,
    # The boxes only while a Rhino is being driven: down in the ship, on
    # foot and in the Nomad, back up when the Rhino is. Unlocked, to arrange
    # them, they stay up anywhere.
    "overlay_rhino_only": False,
    # Only while the game is the window in front. Left up over everything,
    # the boxes sat on top of EDSMT's own Find and Earnings windows.
    "overlay_only_over_game": False,
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
    "overlay_frame": "none",
    # The whole palette, not one accent line. "Pick a colour" used to tint
    # exactly one row of the compass tape and nothing else, because every
    # other colour was a constant baked in at import - which is why picking
    # one visibly did nothing.
    "overlay_theme": "gold",
    # The main window's own palette - any of the overlay's themes. Worn from
    # the next start, because a window keeps the colours it was built with.
    "app_theme": "gold",
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
    # How many sessions have been told where the overlay is (#144).
    "overlay_hint_shown": 0,
    # A word on every control when the mouse rests on it (#166).
    "show_tips": True,
    # The first-run tour has been seen, or skipped (#166).
    "tour_done": False,
    # Set the first time the server takes a deposit of this commander's own.
    # Whether the server has taken a find of yours yet: the first is thanked
    # for. (Find itself is open to everybody.)
    "find_unlocked": False,
    # The rig planner: drive a deposit's edge once and get a pin for each rig
    # where they fit. The spacing is the community's working figure for two
    # rigs, measured in the field, never published.
    "rig_spacing_m": 78,
    # 1.10035: what the map and the scope draw. The driven trail, the lines
    # from you to the nearest deposit of the same commodity and of the next
    # cheaper one, the golden groups (a knot of deposits worth a stop, with
    # the radius they are looked for in) and the rig radar - a ring of the
    # spacing round every rig, and NEXT RIG. The trail painted at scanner
    # range on the scope is off until there is a border: a plate over the
    # game was a bug once.
    "map_trail": True,
    "map_lines": True,
    "map_golden": True,
    "golden_radius_m": 1250,
    "rig_radar": True,
    "overlay_trail_paint": False,
    # Where to go next (1.10035): the guided survey's waypoints and how close
    # counts as there, the pointer to the parked Rhino (and to the ship from
    # the Rhino), and the line from orbit to the deposit or the signal. The
    # four keys step the waypoints on, back, skip one, or pause them; they
    # start unbound.
    "survey_guide": True,
    "waypoint_radius_m": 250,
    "rhino_pointer": True,
    "orbit_guide": True,
    **{name: key for name, key in GD.WAYPOINT_KEYS},
    # 1.10035: which deposits the map and the scope draw - a list of
    # commodity names, an amount and a density floor, and whether names are
    # written beside them - and how many days a site removed from My sites
    # waits in the bin before it is deleted for good.
    "map_filter_commodities": [],
    "map_filter_amount": "Any",
    "map_filter_density": "Any",
    "map_labels": True,
    "trash_days": 30,
    # Where a rig really lands, behind the cockpit (1.10034), and whether a
    # Rhino docking in the ship takes its rigs off the scope.
    "rig_offset_m": RIG_OFFSET_M,
    "rigs_clear_on_dock": True,
    # The best rig layout other commanders shared for the deposit you are
    # on, as pins on the scope when you have no plan of your own (#218).
    "show_shared_layouts": True,
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
    # The last layout preset applied - Standard, Map focus, Minimal or
    # Streamer (OV.LAYOUT_PRESETS). Applying one writes overlay_layout and
    # the overlay_show_* switches; the boxes can be dragged from there.
    "overlay_preset": "streamer",
    # How the ground already swept shows on the scope: faint, clear or
    # solid (OV.SWEPT_LOOKS). Clear from 1.10033 - faint was hard to see.
    "overlay_swept": "faint",
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
# The map is everybody's: what you find goes on it, what anybody finds comes
# back under Find. Not switches any more, whatever an older file says.
ALWAYS_SHARED = ("community_enabled", "community_auto_share", "share_market_prices",
                 # 1.10036: finds carry the name of the commander who
                 # found them, and everybody's are shown.
                 "community_share_cmdr_name", "show_shared_finds",
                 "verify_my_finds")


def build_kind(platform=None):
    """Which build this is, for updating: "installed", "portable" or "".

    installed  the folder build Setup put down - it has Setup's own
               uninstaller beside it, so running the new Setup updates it
    portable   the single-file EDSMT.exe - no _internal folder beside it
    ""         running from source, or a folder build nobody installed:
               there is nothing safe to replace, so it gets the web page
               - and the Linux build (1.10039): the packages version.json
               names are Windows programs, so it gets the web page too

    `platform` is os.name; the checks pass their own.
    """
    if not getattr(sys, "frozen", False):
        return ""
    if (os.name if platform is None else platform) != "nt":
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


def linux_notes(platform=None):
    """What Linux does differently, said in Settings and nowhere else
    (1.10039): one note per section it touches, {} on Windows.

    Each is a plain statement of what works and what does not, so a
    commander on Linux is never left pressing a dead switch."""
    platform = os.name if platform is None else platform
    if platform == "nt":
        return {}
    # Asked about Linux from Windows (the checks run there too), the note
    # is Linux's, not this machine's.
    here = OV.PLATFORM if platform == os.name else OV.WindowPlatform(windows=False)
    return {
        "overlay": here.note(),
        "long_press": ("On Linux the long press is not read: the mouse and "
                       "the game's window cannot be watched from outside the "
                       "game there. The rig keys, joystick buttons and chat "
                       "commands all still work."),
        "joystick": ("On Linux the buttons come from the kernel's joystick "
                     "interface (/dev/input/js*): no root, nothing to "
                     "install. A stick plugged in while EDSMT runs is found "
                     "on the next look."),
        "hotkeys": ("On Linux the keys are grabbed on the X server through "
                    "python-xlib, which RUN.sh installs; the line below says "
                    "whether they took. On a Wayland session they are off - "
                    "use joystick buttons or chat commands there."),
        "journal": JN.journal_hint(platform),
    }


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
    if data.get("community_enabled") is False or data.get("community_share_cmdr_name") is False:
        SETTINGS_NOTICE.append(
            "From this version every find goes on the community map with the "
            "CMDR name of the commander who found it, and everybody's finds "
            "are on your map.")
    for key in ALWAYS_SHARED:
        merged[key] = True
    # 1.10036: the rig button is the game's fire binding, no longer a mouse
    # button picked here. Right was the game's Secondary fire by default.
    merged["long_press_button"] = IM.fire_choice(merged)
    merged["long_press_learned"] = ""
    return upgrade_discord(
        keep_new_keys_free(upgrade_layout(upgrade_hotkeys(merged, data), data),
                           data), data)


def upgrade_discord(merged, saved):
    """Per-find Discord posts off, once, for a file written before 1.10035.

    1.10034 posted every find by default, and saved that default into the
    file, so a commander who never touched the switch could not be told
    apart from one who wanted it. Off once; ticked again, it stays ticked."""
    saved = saved or {}
    try:
        level = int(saved.get("discord_finds_level") or 0)
    except (TypeError, ValueError):
        level = 0
    if level < 1:
        merged["discord_post_finds"] = False
    merged["discord_finds_level"] = 1
    return merged


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


def keep_new_keys_free(merged, saved):
    """A key added since this settings file was written gets its default
    only if nothing in the file is already on that key - two actions on one
    key would each fire half the time. Otherwise it starts blank, and
    Settings has it."""
    saved = saved or {}
    if "hotkey_overlay" not in saved:
        taken = {str(value or "").strip().upper() for name, value in saved.items()
                 if name.startswith("hotkey_") and name != "hotkey_defaults"}
        if OVERLAY_KEY in taken:
            merged["hotkey_overlay"] = ""
    if "hotkey_zoom" not in saved:
        taken = {str(value or "").strip().upper() for name, value in saved.items()
                 if name.startswith("hotkey_") and name != "hotkey_defaults"}
        if SCOPE_ZOOM_KEY in taken:
            merged["hotkey_zoom"] = ""
    return merged


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
        keep_settings_copy(data)
        return True
    except OSError:
        return False


# Dated copies of the settings, so a bad day is one click from undone
# (7 Oct 2026: "back up all the settings people have like placements
# overlays the lot"). A copy is taken when something that matters has
# changed since the newest one - where you were last is not a setting - and
# at most one every SETTINGS_HISTORY_EVERY_S, so dragging a box about does
# not push the good copies out. The newest SETTINGS_HISTORY_KEPT are kept,
# and every backup zip carries the folder.
SETTINGS_HISTORY = "settings-history"
SETTINGS_HISTORY_KEPT = 30
SETTINGS_HISTORY_EVERY_S = 15 * 60
SETTINGS_VOLATILE = ("last_system", "last_body", "_readme")
NO_SETTINGS_COPIES = "None yet - kept from 1.10034 on"
# Sessions the "overlay is off" hint is given on, at most (#144).
OVERLAY_HINTS = 3
# With the game in front at start-up, the tour looks again this often.
TOUR_WAIT_MS = 5000
# How often the bodies of the system you are in are written to the body
# book, and how long the public database's answer for a system is trusted.
BODY_SAVE_S = 5.0
POWER_SAVE_S = 20.0
PUBLIC_BODIES_DAYS = 30


def settings_history_dir():
    return os.path.join(DATA_DIR, SETTINGS_HISTORY)


def _history_when(name):
    """The time in a copy's name, or None for a file this did not write."""
    if not (name.startswith("settings-") and name.endswith(".json")):
        return None
    try:
        return time.mktime(time.strptime(name[9:-5], "%Y%m%d-%H%M%S"))
    except (ValueError, OverflowError):
        return None


def settings_history(folder=None):
    """The dated copies, newest first, as (when, path)."""
    folder = folder or settings_history_dir()
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    found = [(_history_when(name), os.path.join(folder, name)) for name in names]
    return sorted(((when, path) for when, path in found if when is not None),
                  reverse=True)


def _settings_that_matter(data):
    return {key: value for key, value in (data or {}).items()
            if key not in SETTINGS_VOLATILE}


def keep_settings_copy(data, now=None, folder=None):
    """Write a dated copy of `data` when it differs from the newest copy in
    anything that matters. The path written, or None. Never raises."""
    now = time.time() if now is None else now
    folder = folder or settings_history_dir()
    try:
        copies = settings_history(folder)
        if copies:
            when, newest = copies[0]
            if 0 <= now - when < SETTINGS_HISTORY_EVERY_S:
                return None
            kept, _ = _read_settings_file(newest, attempts=1)
            if kept is not None and \
                    _settings_that_matter(kept) == _settings_that_matter(data):
                return None
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, "settings-%s.json" % time.strftime(
            "%Y%m%d-%H%M%S", time.localtime(now)))
        _atomic_write(target, json.dumps(data, indent=2, default=str))
        for _when, old in settings_history(folder)[SETTINGS_HISTORY_KEPT:]:
            try:
                os.remove(old)
            except OSError:
                pass
        return target
    except (OSError, TypeError, ValueError):
        return None


def restore_settings_copy(path, now=None):
    """Put a dated copy back as the settings. What was there is kept beside
    it as settings.json.before-restore-<time>. The settings put back, or
    raises ValueError when the copy cannot be read."""
    data, why = _read_settings_file(path, attempts=1)
    if data is None:
        raise ValueError(why)
    now = time.time() if now is None else now
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(SETTINGS_FILE):
        import shutil
        shutil.copy2(SETTINGS_FILE, SETTINGS_FILE + ".before-restore-" + stamp)
    _atomic_write(SETTINGS_FILE, json.dumps(data, indent=2, default=str))
    return data


def rigs_path():
    return os.path.join(DATA_DIR, RIGS_FILE_NAME)


def load_rigs(path=None):
    """The rigs that were down when EDSMT last closed, or None (1.10034:
    they were held in memory only, and a restart lost every one)."""
    try:
        with open(path or rigs_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    rigs_at = data.get("rigs_at") if isinstance(data, dict) else None
    if not isinstance(rigs_at, dict) or not rigs_at.get("system") or \
            not rigs_at.get("body") or not isinstance(rigs_at.get("rigs"), list):
        return None
    kept = []
    for rig in rigs_at["rigs"]:
        try:
            if isinstance(rig, dict) and int(rig["n"]) >= 1:
                float(rig["lat"]), float(rig["lon"])
                kept.append(rig)
        except (KeyError, TypeError, ValueError):
            continue
    if not kept:
        return None
    rigs_at["rigs"] = kept
    rigs_at.setdefault("rhinos", [])
    return rigs_at


def save_rigs(rigs_at, path=None):
    """Write the rigs down as they change. False if they could not be."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        _atomic_write(path or rigs_path(),
                      json.dumps({"saved": time.time(), "rigs_at": rigs_at},
                                 indent=1, default=str))
        return True
    except (OSError, TypeError, ValueError):
        return False


def settings_copy_label(when, path):
    """One line for the picker: when, and what makes it recognisable."""
    data, _ = _read_settings_file(path, attempts=1)
    data = data or {}
    bits = [time.strftime("%a %d %b %Y, %H:%M", time.localtime(when))]
    theme = data.get("app_theme")
    if theme:
        bits.append("theme %s" % theme)
    preset = data.get("overlay_preset")
    if preset:
        bits.append("layout %s" % preset)
    return "  -  ".join(bits)




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
        pass
    try:
        return local_number(text)
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
            lat, lon = read_pair(where)
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
    main thread ever touches a widget. On Linux (1.10039) the same queue is
    fed by x11keys, which grabs the keys on the X server.
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
        self._x11 = None

    def start(self, bindings):
        self.stop()
        self._wanted = dict(bindings)
        self.bound = {}
        self.problem = ""
        if os.name != "nt":
            self._x11 = XK.X11Hotkeys(events=self.events)
            self._x11.start(self._wanted)
            self.bound, self.problem = self._x11.bound, self._x11.problem
            self.active = self._x11.active
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
        x11, self._x11 = self._x11, None
        if x11 is not None:
            x11.stop()
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
        if self._x11 is not None:
            # The X loop can stop on its own; say so where Settings looks.
            self.active = self._x11.active
            if self._x11.problem and not self.problem:
                self.problem = self._x11.problem
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

    def __init__(self, parent, on_select=None, on_edit=None, on_edit_rig=None):
        super().__init__(parent, bg=VOID, highlightthickness=0, bd=0)
        self.on_select = on_select
        self.on_edit = on_edit
        self.on_edit_rig = on_edit_rig
        self._rig_hits = []
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
        self.rows = MF.apply(list(rows or []), self._map_prefs())
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
        selected it, so this only has to open the editor. A rig's square
        opens the rig's own editor (1.10034)."""
        for x, y, mark in list(getattr(self, "_rig_hits", None) or []):
            if abs(event.x - x) <= 9 and abs(event.y - y) <= 9:
                if self.on_edit_rig:
                    self.on_edit_rig(mark)
                return
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
        self._rig_hits = []
        if rigs:
            self._rig_marks(viewport, rigs)
        self._map_under(viewport, rigs)
        self._deposits(self._plan)
        self._me(viewport, self._plan)
        self._map_over(viewport, rigs)
        self._guidance(viewport, self._plan)
        top = self._footer(width, height, self._plan)
        self._clear_footer(top)
        if viewport.panned:
            # Above the footer, not on it: centred on the same line it was
            # printed through the legend and the body's facts.
            self.create_text(width / 2, top - 4, anchor="s", fill=AMBER,
                             font=F_SMALL,
                             text="dragged off centre - right-click to recentre")

    def _rig_marks(self, viewport, rigs):
        """Each rig as a numbered square in its commodity's colour, with the
        commodity beside it; the square turns red while it is past the
        limit."""
        limit = float(rigs.get("limit_m") or 0)
        for mark in rigs.get("rigs") or []:
            x, y = viewport.to_canvas(mark["east"], mark["north"])
            if isinstance(getattr(self, "_rig_hits", None), list):
                self._rig_hits.append((x, y, mark))
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

    # -- 1.10035: the trail, the lines, golden groups, the rig radar ------

    def _map_prefs(self):
        prefs = getattr(self, "map_prefs", None)
        return prefs if isinstance(prefs, dict) else {}

    def _map_under(self, viewport, rigs):
        """What goes under the dots: the driven trail, the golden circles,
        the rig rings and the lines to the nearest deposits; and the two
        short lists in the corners, claimed so no label lands on them."""
        prefs = self._map_prefs()
        plan = self._plan
        self._map_golden = []
        self._map_lines = None
        if not prefs or not plan:
            return
        survey = self.survey if isinstance(self.survey, dict) else None
        if prefs.get("trail") and survey:
            self._trail(viewport, survey.get("trail") or [])
        if prefs.get("golden"):
            me = plan["commander"]
            self._map_golden = PV.golden_groups(
                [i for i in plan["items"]], prefs.get("prices") or {},
                prefs.get("golden_radius_m"), start=(me["east_m"], me["north_m"]))
            self._golden_circles(viewport, self._map_golden)
        radar = rigs.get("radar") if isinstance(rigs, dict) and prefs.get("radar") else None
        if radar:
            self._radar_rings(viewport, radar)
        if prefs.get("lines"):
            me = plan["commander"]
            focus = PV.focus_commodity(plan["items"], prefs.get("target"),
                                       prefs.get("last"))
            self._map_lines = PV.nearest_lines(plan["items"], prefs.get("prices") or {},
                                           focus)
            self._nearest_lines(viewport, plan, self._map_lines)
        if self._map_golden:
            self._golden_list(viewport, self._map_golden)
        if radar:
            self._radar_text(radar)

    def _map_over(self, viewport, rigs):
        """What goes over them: the labels of the lines and the golden
        circles (placed after the finds' own, so a find is named first), and
        the Rhino's arrow in the colour of the radar's verdict."""
        prefs = self._map_prefs()
        plan = self._plan
        if not prefs or not plan:
            return
        bounds = (0, 0, viewport.width, viewport.height)
        for group in attr(self, "_map_golden", None) or []:
            x, y = viewport.to_canvas(group["east_m"], group["north_m"])
            top = y - viewport.radius_px(group["radius_m"])
            self._label(x, top, 0, "P%d  %dR  %s" % (
                group["n"], group["rigs"], self._rate_text(group)), GOLD, bounds,
                bold=True, force=False, tags=("golden",))
        lines = attr(self, "_map_lines", None)
        for kind in ("same", "cheaper"):
            found = (lines or {}).get(kind)
            if not found:
                continue
            me = plan["commander"]
            item = found["item"]
            end = item["edge"] if item["offscreen"] else (item["x"], item["y"])
            self._label((me["x"] + end[0]) / 2.0, (me["y"] + end[1]) / 2.0, 0,
                        _metres(found["range_m"]), colour_for(found["commodity"]),
                        bounds, tags=("mapline",))
        radar = rigs.get("radar") if isinstance(rigs, dict) and prefs.get("radar") else None
        if radar:
            cx, cy = viewport.centre
            self.create_polygon(PV.arrow_points(cx, cy, plan["heading"]),
                                fill=self._radar_colour(radar["state"]),
                                outline=VOID, tags=("radar",))

    @staticmethod
    def _radar_colour(state):
        return {"ok": GREEN, "edge": AMBER, "close": RED}.get(state, DIM)

    @staticmethod
    def _rate_text(group):
        rate = group.get("cr_per_h")
        return "%s Cr/h" % OV.money(rate) if rate else "no price"

    def _trail(self, viewport, line):
        """The driven line: thin, over the swept ground, ending at you."""
        if len(line) < 2:
            return
        flat = []
        for east, north in line:
            flat.extend(viewport.to_canvas(east, north))
        self.create_line(*flat, fill=TRAIL_LINE, width=1, tags=("trail",))

    def _golden_circles(self, viewport, groups):
        for group in groups:
            x, y = viewport.to_canvas(group["east_m"], group["north_m"])
            r = viewport.radius_px(group["radius_m"])
            self.create_oval(x - r, y - r, x + r, y + r, outline=GOLD, width=2,
                             tags=("golden",))

    def _golden_list(self, viewport, groups):
        """"Top groups", top right: most rigs first, what each is worth an
        hour with the drive, and how far it is from you."""
        y = 12
        for group in groups:
            text = "P%d  %d rigs  %s  %s %03d" % (
                group["n"], group["rigs"], self._rate_text(group),
                _metres(group["range_m"]), round(group["bearing"]) % 360)
            item = self.create_text(viewport.width - 10, y, anchor="ne", fill=GOLD,
                                    font=F_SMALL_B, text=text, tags=("goldlist",))
            self._keep_clear(item)
            y += 16

    def _radar_rings(self, viewport, radar):
        """A ring of the spacing round every rig, in the colour of how you
        stand to it, and where the nearest spot a rig can go is."""
        # A band, not a line: 76 m to 80 m at the usual spacing. Every band
        # is red while the rig's spot is inside 80 m of any rig, green once
        # it is clear of every one.
        band = radar.get("band") or ("green" if all(
            r["state"] == "ok" for r in radar["rings"]) else "red")
        colour = self._radar_colour("ok" if band == "green" else "close")
        for ring in radar["rings"]:
            x, y = viewport.to_canvas(ring["east"], ring["north"])
            inner = ring.get("inner", ring["radius"] - 2.0)
            outer = ring.get("outer", ring["radius"] + 2.0)
            for reach, line in ((inner, 1), ((inner + outer) / 2.0,
                                             max(2, int(round(viewport.radius_px(outer - inner))))),
                                (outer, 1)):
                r = viewport.radius_px(reach)
                self.create_oval(x - r, y - r, x + r, y + r, outline=colour,
                                 width=line, tags=("rigring", "rigband"))
        legal = radar.get("legal")
        if radar["state"] == "close" and legal:
            sx, sy = viewport.to_canvas(*radar["spot"])
            lx, ly = viewport.to_canvas(*legal)
            self.create_line(sx, sy, lx, ly, fill=AMBER, dash=(3, 3), tags=("rigring",))
            self.create_oval(lx - 4, ly - 4, lx + 4, ly + 4, outline=GREEN, width=2,
                             tags=("rigring",))

    def _radar_text(self, radar):
        item = self.create_text(10, 14, anchor="nw", fill=self._radar_colour(radar["state"]),
                                font=F_SMALL_B, text=radar["text"], tags=("radar",))
        self._keep_clear(item)

    def _nearest_lines(self, viewport, plan, lines):
        """From you to the nearest deposit of the commodity in hand (solid)
        and to the next cheaper one (dotted). A deposit off the map is
        followed to the edge."""
        me = plan["commander"]
        for kind in ("same", "cheaper"):
            found = (lines or {}).get(kind)
            if not found:
                continue
            item = found["item"]
            end = item["edge"] if item["offscreen"] else (item["x"], item["y"])
            self.create_line(me["x"], me["y"], end[0], end[1],
                             fill=colour_for(found["commodity"]),
                             width=2 if kind == "same" else 1,
                             dash=None if kind == "same" else (2, 4),
                             tags=("mapline", "line_" + kind))

    def _clear_footer(self, top):
        """Nothing printed over the footer. An arrow at the foot of the map
        for a find beyond the edge put its distance on the line of words
        there; the label moves up, clear of the footer, and the arrow stays."""
        try:
            for item in self.find_withtag("edge"):
                if self.type(item) != "text":
                    continue
                box = self.bbox(item)
                if box and box[3] > top - 1:
                    self.move(item, 0, (top - 2) - box[3])
        except (TypeError, IndexError, tk.TclError):
            pass

    def _guidance(self, viewport, plan):
        """Where to go next: the waypoints as dots with the current one
        ringed, a chevron beside you pointing at each thing to go to, and the
        words in the top left under the rig radar's line."""
        guide = getattr(self, "guidance", None)
        if not isinstance(guide, dict) or not guide:
            return
        cx, cy = viewport.centre
        lines = []
        for key, colour in (("wp", OV.WAYPOINT_COLOUR), ("ship", OV.POINTER_COLOUR),
                            ("rhino", OV.POINTER_COLOUR), ("orbit", OV.WAYPOINT_COLOUR)):
            item = guide.get(key)
            if not item:
                continue
            lines.append((key, colour, item))
            if key == "wp" and not item.get("complete"):
                for point in item.get("points") or []:
                    x, y = viewport.to_canvas(point["east"], point["north"])
                    if not (-8 <= x <= viewport.width + 8 and -8 <= y <= viewport.height + 8):
                        continue
                    if point["state"] == "current":
                        r = max(7.0, viewport.radius_px(item.get("arrive_m") or 250.0))
                        self.create_oval(x - r, y - r, x + r, y + r, outline=colour,
                                         width=2, tags=("wp", "wpnow"))
                        self.create_oval(x - 3, y - 3, x + 3, y + 3, fill=colour,
                                         outline="", tags=("wp", "wpnow"))
                        label = self.create_text(x + r + 3, y, anchor="w", fill=colour,
                                                 font=F_SMALL_B, text="WP %d" % point["n"],
                                                 tags=("wp", "wplabel"))
                        self._keep_clear(label)
                    elif point["state"] == "todo":
                        self.create_oval(x - 3, y - 3, x + 3, y + 3, outline=colour,
                                         tags=("wp", "wpnext"))
                    else:
                        self.create_oval(x - 2, y - 2, x + 2, y + 2, fill=FAINT,
                                         outline="", tags=("wp", "wpdone"))
            if item.get("complete") or "bearing" not in item:
                continue
            dx = math.sin(math.radians(item["bearing"]))
            dy = -math.cos(math.radians(item["bearing"]))
            self.create_polygon(PV.arrow_points(cx + dx * 30, cy + dy * 30,
                                                item["bearing"], 11),
                                fill=colour, outline=VOID, tags=("chevron", key))
        top = 14
        for found in self.find_withtag("radar"):
            if self.type(found) == "text" and self.bbox(found):
                top = max(top, self.bbox(found)[3] + 4)
        for key, colour, item in lines:
            line = self.create_text(10, top, anchor="nw", fill=colour, font=F_SMALL_B,
                                    text=item["text"], tags=("wptext", key))
            self._keep_clear(line)
            box = self.bbox(line)
            top = (box[3] if box else top + 14) + 2

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
                   shared=bool(item["deposit"].get("shared")),
                   spent=SV.is_depleted(item["deposit"].get("amount")))
            if not chosen and not MF.labels_on(self._map_prefs()):
                continue
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
        # Where the footer starts, so whatever goes above it clears it.
        tops = []
        for item in (left, right if self.caption else None):
            try:
                if item is not None:
                    tops.append(float(self.bbox(item)[1]))
            except (TypeError, IndexError, tk.TclError):
                pass
        return min(tops) if tops else height - 26


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

class EDSMT(GD.GuidanceMixin, ctk.CTk):
    """One window that follows the game.

    Nothing has to be set up before a find can be recorded. The game already
    knows the system, the body, the position and often the commodity, so the
    only thing a commander should ever have to do is press one key when the
    scanner pings.
    """

    def __init__(self):
        # The theme first, before a single widget exists: a Tk widget keeps
        # the colours it was made with, so this is the only moment the whole
        # window can be dressed at once. The game's own colours are read
        # first, so the "game" theme is today's HUD and not yesterday's.
        self.game_theme = refresh_game_theme()
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
        # 1.10035: every market this commander has read, by station, and the
        # Powerplay merits his sales have paid - both his own.
        self.market_book = SV.MarketBook(DATA_DIR)
        self._book_read = ""
        self.merits = SV.MeritRate(DATA_DIR)
        # 1.10035: each ship's hold as its newest Loadout said, what each
        # session carried beyond its row, the Discord message each one was
        # posted as, the app's own log, and the map pictures made this run.
        self.ship_book = SH.CapacityBook(DATA_DIR)
        self.extras = SL.SessionLedger(DATA_DIR)
        self.post_book = SL.PostBook(DATA_DIR)
        self.applog = SB.AppLog(DATA_DIR)
        self._pictures = []
        self._boot_at = time.time()
        # 1.10035: the commander's Powerplay record from his own journal, and
        # the searches he has saved by name.
        self.powerbook = PW.PowerBook(DATA_DIR)
        self.searches = FD.Favourites(DATA_DIR)
        # 1.10035: the last two readings of every station's prices, so a
        # station can say which way its price and demand are moving.
        self.trends = SP.Trends(DATA_DIR)
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
        # The guided survey's waypoints and the kept rig plans (1.10035).
        self.guide_init(DATA_DIR)
        # Every body ever described, per system, on disk (1.10034): the
        # journal as it happens, every older journal once in the background,
        # and the public body database through the server.
        self.bodybook = BB.BodyBook(DATA_DIR)
        self._bodies_seen = {}
        self._bodies_asked = set()
        self._bodies_asking = {}
        self._backfill = None
        self._backfill_stop = threading.Event()
        self._backfill_progress = None
        self.cmap = None
        self._cmap_saved = 0.0
        # Where the rigs were put down, and whether the too-far warning has
        # sounded for this excursion. Kept on disk from 1.10034: a restart
        # used to lose every rig.
        self.rigs_at = load_rigs()
        self._rigs_saved = json.dumps(self.rigs_at, sort_keys=True, default=str)
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
            self.after(600, self.follow_vehicle_overlay)
        if not self.settings.get("asked_to_share"):
            self.after(900, self.ask_to_share)
        elif not self.settings.get("tour_done"):
            # Everyone already past the first question sees the tour once,
            # on the first start of 1.10034 (#166).
            self.after(1500, self.start_tour)
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

    def start_tour(self, force=False):
        """The first-run tour, once - or again, asked for (#166). True if
        it opened."""
        settings = attr(self, "settings", None) or {}
        if settings.get("tour_done") and not force:
            return False
        open_now = attr(self, "touring", None)
        try:
            if open_now is not None and open_now.winfo_exists():
                return True
        except Exception:
            pass
        if not force:
            # Never over the game: EDSMT started with Elite in front waits
            # until its own window is looked at.
            try:
                front = OV.foreground_is_game()
            except Exception:
                front = None
            if front:
                try:
                    self.after(TOUR_WAIT_MS, self.start_tour)
                except Exception:
                    pass
                return False
        try:
            self.touring = TourWindow(self)
            return True
        except Exception as exc:
            self.say("Could not open the tour: %s" % exc, AMBER)
            return False

    def tour_finished(self):
        """Seen or skipped, the tour does not come back by itself."""
        self.touring = None
        settings = attr(self, "settings", None)
        if isinstance(settings, dict) and not settings.get("tour_done"):
            settings["tour_done"] = True
            save_settings(settings)

    def set_name_credit(self, wanted=True):
        """The first run, read. Every find carries the commander's name
        (1.10036, ALWAYS_SHARED) - `wanted` is kept for older callers and
        changes nothing."""
        del wanted
        self.settings["community_share_cmdr_name"] = True
        save_settings(self.settings)
        self.community.configure(self.settings.get("community_url", ""),
                                 self.settings.get("community_token", ""),
                                 True, True)
        self.say("Your finds go on the community map with your CMDR name "
                 "on them.", GREEN)

    # -- the overlay -----------------------------------------------------

    def set_overlay(self, wanted):
        """Turn the in-game strip on or off."""
        self.settings["overlay_enabled"] = bool(wanted)
        save_settings(self.settings)
        if not wanted:
            self.overlay.hide()
        elif self.overlay_wanted_now():
            self.overlay.show()
            self.overlay.refresh_settings(self.settings)
            self.redraw()
        self.show_overlay_state()

    def toggle_overlay(self):
        """The Overlay button, and its key (Alt+0)."""
        self.set_overlay(not self.settings.get("overlay_enabled"))
        if not self.settings.get("overlay_enabled"):
            self.say("Overlay off.")
        elif self.overlay_wanted_now():
            self.say("Overlay on. It shows while the game is in front - "
                     "borderless or windowed only, never over exclusive "
                     "fullscreen.", AMBER)
        else:
            self.say("Overlay on. It comes up when you are driving a Rhino "
                     "- Settings > Overlay can show it everywhere.", AMBER)

    def overlay_wanted_now(self):
        """Whether the boxes should be up this moment.

        Up when switched on - and, with "only in the Rhino" (the default),
        only while a Rhino is being driven: in the ship, on foot or in the
        Nomad they are down, and they come back with the Rhino. Unlocked to
        be arranged, they stay up wherever you are."""
        if not self.settings.get("overlay_enabled"):
            return False
        if not self.settings.get("overlay_rhino_only", True):
            return True
        overlay = attr(self, "overlay", None)
        if overlay is not None and not overlay.locked:
            return True
        return bool(getattr(attr(self, "game"), "in_rhino", False)) or self.guidance_wanted()

    def follow_vehicle_overlay(self):
        """Put the boxes up or take them down as the Rhino comes and goes.
        True when it changed anything."""
        overlay = attr(self, "overlay", None)
        if overlay is None:
            return False
        self.overlay_hint()
        wanted = self.overlay_wanted_now()
        if wanted and not overlay.showing:
            overlay.show()
            overlay.refresh_settings(self.settings)
            self.redraw()
            return overlay.showing
        if not wanted and overlay.showing:
            overlay.hide()
            return True
        return False

    def overlay_hint(self):
        """In a Rhino with the overlay off, say once where it is (#144: a
        tester found the Overlay button late). Once a session, and on no more
        than OVERLAY_HINTS sessions - after that they know. True if said."""
        settings = attr(self, "settings", None) or {}
        if settings.get("overlay_enabled") or attr(self, "_overlay_hinted", False):
            return False
        state = attr(self, "game", None)
        if state is None or not getattr(state, "in_rhino", getattr(state, "in_srv", False)):
            return False
        try:
            shown = int(settings.get("overlay_hint_shown") or 0)
        except (TypeError, ValueError):
            shown = 0
        self._overlay_hinted = True
        if shown >= OVERLAY_HINTS:
            return False
        settings["overlay_hint_shown"] = shown + 1
        save_settings(settings)
        key = key_text(settings.get("hotkey_overlay", "")) or "the Overlay button"
        self.flash("THE OVERLAY IS OFF", "%s turns it on - compass, scope, rigs" % key,
                   AMBER)
        self.say("You are in the Rhino and the overlay is off. %s turns it on, "
                 "or the Overlay button at the top right of this window - the "
                 "compass, the scope and your rigs, over the game." % key, AMBER)
        return True

    @staticmethod
    def wanted_hotkeys(data):
        """The keys to register, from settings. One place, not three.

        A key left blank is a key not registered rather than one registered
        to nothing - RegisterHotKey on an empty binding fails, and a failure
        is reported to the commander as "already taken by another program",
        which would be a lie about a key they deliberately cleared.
        """
        actions = ("deposit", "location", "lock", "overlay", "update", "centre",
                   "border", "rigs", "allup", "trace") \
            + tuple("rig%d" % n for n in range(1, MAX_RIGS + 1)) \
            + tuple("rig%dup" % n for n in range(1, MAX_RIGS + 1))
        wanted = {action: str(data.get("hotkey_" + action,
                                       DEFAULT_SETTINGS["hotkey_" + action]) or "")
                  for action in actions}
        wanted["zoom"] = str(data.get("hotkey_zoom", SCOPE_ZOOM_KEY) or "")
        for name, fallback in GD.WAYPOINT_KEYS:
            wanted[name[len("hotkey_"):]] = str(data.get(name, fallback) or "")
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
        # Unlocked to be arranged, the boxes are up even out of the Rhino;
        # locked again, they follow the Rhino.
        self.follow_vehicle_overlay()
        self.show_overlay_state()
        self.redraw()
        if locked:
            self.say("Overlay locked. Clicks go to the game again.", GREEN)
        else:
            self.say("Overlay unlocked. Drag each box by its bar, resize it "
                     "by the bottom-right corner, press SHAPE in its bar to "
                     "fit it to the cockpit, then lock it again.", AMBER)

    def apply_overlay_preset(self, name):
        """A whole overlay layout in one pick (OV.LAYOUT_PRESETS). Returns
        the set of boxes switched on."""
        shown = self.overlay.apply_preset(name)
        save_settings(self.settings)
        if self.settings.get("overlay_enabled"):
            # Boxes switched off close, boxes switched on open, every one
            # where the preset put it.
            self.overlay.hide()
            self.overlay.show()
        self.redraw()
        return shown

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
        self.overlay.map_prefs = self.map_prefs()
        self.overlay.guidance = self.guidance_view(attr(self, "game", None), centre, radius_m)
        self.overlay.draw(rows, heading, note, body=body,
                          location=location, site=site, survey=survey,
                          rigs=rigs, guide=self.guide_card(),
                          target=attr(self, "_guide_to", None), only=only,
                          cargo=self.overlay_cargo(),
                          hazard=self.overlay_hazard(),
                          rigplan=self.plan_marks(), wing=self.wing_marks(),
                          zone=self.zone_card())

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
        # The Nomad sets the same In SRV flag: only a Rhino is the Rhino.
        facts["rhino"] = bool(getattr(state, "in_rhino",
                                      getattr(state, "in_srv", False)))
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
        if farewell:
            self._guide_farewell = None
        if not settings.get("overlay_show_guide", True):
            # The box goes as well as the words. Retiring the guide switched
            # the setting off and nothing told the overlay, so the GUIDE box
            # stayed up, frozen on its last card, until the next start
            # (7 Oct 2026: "the tutorial stays open when I complete it").
            self.close_guide_box()
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

    def close_guide_box(self):
        """Take the GUIDE box down when the guide is switched off. True if
        it was up. Never raises."""
        overlay = attr(self, "overlay", None)
        settings = attr(self, "settings", None) or {}
        if overlay is None or settings.get("overlay_show_guide", True):
            return False
        try:
            if OV.GUIDE not in (overlay.panels or {}):
                return False
            overlay.refresh_settings(settings)
            return OV.GUIDE not in overlay.panels
        except Exception:
            return False

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
                 "switches itself off now - Settings > Basics turns "
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
        # Where the tools go when they open as tabs (1.10036): in the map's
        # place, one at a time.
        self.tool_area = centre
        self.plan = PlanView(centre, on_select=self.picked_on_map,
                             on_edit=self.edit_deposit,
                             on_edit_rig=self.edit_rig)
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
        self._map_picture_buttons(readout)
        self.status = ctk.CTkLabel(readout, text="", font=F_READOUT,
                                   text_color=DIM, anchor="w")
        self.status.pack(side="left", fill="x", expand=True,
                         padx=(4, 14), pady=6)

        # Fill it all in from disk before the window is ever shown. Without
        # this the app opens blank with the game shut and stays blank,
        # because the only code that fills it sits past an early return in
        # update_telemetry.
        self.show_records()

    def _map_picture_buttons(self, parent):
        """Save map, Copy map and Share map (1.10035): the plan view as a
        picture. Packed to the right of the status line before it expands."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(side="right", padx=(0, 10), pady=4)
        self._map_button_row = row
        for text, command, hint in (
                ("Filter...", self.open_map_filter,
                 "Which deposits the map and the scope draw: by commodity, amount and density, and whether names are written."),
                ("Save map...", self.save_map_picture,
                 "Saves a picture of the map - deposits, rigs, the ground swept - where you choose."),
                ("Copy map", self.copy_map_picture,
                 "Puts the picture of the map on the clipboard, ready to paste into Discord."),
                ("Share map", self.share_map,
                 "Saves the picture, copies the best patch's finds as text, and opens the folder.")):
            tip(ctk.CTkButton(row, text=text, width=96, height=26, font=F_SMALL,
                              **BTN_SECONDARY, command=command), hint).pack(
                                  side="left", padx=(6, 0))
        # Shown for a moment after a tonne is refined where nothing is marked.
        self.refine_button = tip(ctk.CTkButton(
            row, text="Mark it", width=80, height=26, font=F_SMALL,
            **BTN_PRIMARY, command=self.mark_refined_here),
            "Marks a deposit of the commodity just refined, here.")

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
                                    font=F_HEAD, justify="left",
                                    text_color=TEXT, anchor="w")
        self.t_where.grid(row=0, column=1, sticky="w", pady=(9, 0))
        self.t_detail = ctk.CTkLabel(bar, text="", font=F_READOUT,
                                     justify="left", text_color=DIM, anchor="w")
        self.t_detail.grid(row=1, column=1, sticky="w")
        # What the run is worth, on its own line under where you are. The
        # two answer different questions and a commander reads one of them
        # while driving and the other while deciding whether to go home,
        # so they do not share a line.
        self.t_earnings = ctk.CTkLabel(bar, text="", font=F_READOUT,
                                       justify="left", text_color=AMBER, anchor="w")
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
        # The tabs (1.10036, #147): the map, then the six tools. With tools
        # as windows the same buttons open the windows.
        self.tab_buttons = {}
        for key, text, width, command in (
                ("map", "Map", 64, self.show_map),
                ("find", "Find", 74, self.open_find),
                ("sites", "My sites", 92, self.open_sites),
                ("land", "Where to land", 124, self.open_land),
                ("earnings", "Earnings", 96, self.open_earnings),
                ("powerplay", "Powerplay", 104, self.open_powerplay),
                ("leaderboard", "Leaderboard", 116, self.open_leaderboard)):
            button = tip(ctk.CTkButton(nav, text=text, width=width, height=32,
                                       font=F_STRONG, **BTN_SECONDARY,
                                       command=command), TIPS[key])
            button.pack(side="left", padx=4)
            self.tab_buttons[key] = button
        self.tour_find = self.tab_buttons["find"]
        self.active_tab = "map"
        self.paint_tabs()
        self.btn_overlay = ctk.CTkButton(side, text="Overlay", width=88, height=32,
                                         font=F_STRONG, **BTN_SECONDARY,
                                         command=self.toggle_overlay)
        tip(self.btn_overlay, TIPS["overlay"]).pack(side="left", padx=4)
        # Arranging the overlay happens WHILE looking at the overlay, so the
        # control is here beside it and not four clicks into Settings.
        self.btn_lock = ctk.CTkButton(side, text="Unlock", width=84, height=32,
                                      font=F_STRONG, **BTN_SECONDARY,
                                      command=self.toggle_overlay_lock)
        tip(self.btn_lock, TIPS["lock"]).pack(side="left", padx=4)
        self.tour_settings = tip(ctk.CTkButton(side, text="Settings", width=94,
                                               height=32, font=F_STRONG,
                                               **BTN_SECONDARY,
                                               command=self.open_settings),
                                 TIPS["settings"])
        self.tour_settings.pack(side="left", padx=4)
        # Built but not packed. It appears only if the website says there is
        # a newer build, so an up-to-date app never carries a button that
        # does nothing.
        self.btn_update = ctk.CTkButton(side, text="UPDATE AVAILABLE",
                                        width=170, height=32, font=F_STRONG,
                                        **BTN_PRIMARY,
                                        command=self.update_button_pressed)
        tip(self.btn_update, TIPS["update"])
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
            buttons = (int(side.winfo_reqwidth())
                       + (int(nav.winfo_reqwidth()) + 16 if nav is not None else 0)
                       + 24)
            room = width - 170 - buttons
            stack = room < TOP_READOUT_ROOM
            # The readouts wrap inside the room they have rather than take
            # the buttons' room. "mined aboard ... worth ... at ..." runs to
            # a hundred and thirty characters, and a label asks for all of
            # it: the column grew, the buttons shrank, and "Where to land"
            # read "re to l" with Earnings pushed off the end.
            self._wrap_readouts(width - 170 - 24 if stack else room)
            # Stacked, the tabs and the right-hand buttons share a row while
            # both fit, and take a row each when they do not (1.10036: the
            # Map tab made the pair wider than the narrowest window).
            apart = stack and nav is not None and \
                int(nav.winfo_reqwidth()) + int(side.winfo_reqwidth()) + 48 > width
            shape = (stack, apart)
            if shape == attr(self, "_top_shape", (False, False)):
                return
            self._top_shape = shape
            self._top_stacked = stack
            if stack:
                if nav is not None:
                    nav.grid_configure(row=3, column=0, columnspan=2 if not apart else 4,
                                       rowspan=1, sticky="w", padx=12,
                                       pady=(0, 4 if apart else 8))
                side.grid_configure(row=4 if apart else 3, column=2 if not apart else 0,
                                    columnspan=2 if not apart else 4, rowspan=1,
                                    sticky="e", padx=12, pady=(0, 8))
            else:
                if nav is not None:
                    nav.grid_configure(row=0, column=2, columnspan=1, rowspan=3,
                                       sticky="w", padx=(8, 8), pady=0)
                side.grid_configure(row=0, column=3, columnspan=1, rowspan=3,
                                    sticky="e", padx=12, pady=0)
        except Exception:
            pass

    def _wrap_readouts(self, room):
        """Wrap the three readout lines at `room` pixels. Only when it
        changes: a label that rewraps resizes the bar, and the bar
        resizing calls the fitter again."""
        room = max(240, int(room))
        if room == attr(self, "_readout_room", None):
            return
        self._readout_room = room
        for name in ("t_where", "t_detail", "t_earnings"):
            label = attr(self, name)
            if label is None:
                continue
            try:
                scale = float(label._apply_widget_scaling(1.0)) or 1.0
            except Exception:
                scale = 1.0
            label.configure(wraplength=int(room / scale))

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
        # Kept so a tool on show as a tab can have the window's whole width.
        self.rail_frame = frame
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
                   tip(ctk.CTkButton(bar, text="log this one", width=122,
                                 height=26, font=F_SMALL, **BTN_SECONDARY,
                                 command=self.log_location), "Logs the signal you are in, with its number, where you are standing."))

        picker = ctk.CTkFrame(rail, fg_color="transparent")
        picker.pack(fill="x", padx=12, pady=(2, 4))
        ctk.CTkLabel(picker, text="Signal", width=76, anchor="w",
                     font=F_BODY, text_color=DIM).pack(side="left")
        self.location_box = tip(ctk.CTkComboBox(
            picker, values=[str(n) for n in range(1, MAX_LOCATIONS + 1)],
            font=F_BODY, height=30, **BOX, command=lambda _: self.redraw()), TIPS["signal"])
        self.location_box.set("1")
        self.location_box.bind("<Return>", lambda _e: self.redraw())
        tip(self.location_box, TIPS["signal"]).pack(side="left", fill="x", expand=True)

        actions = ctk.CTkFrame(rail, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(4, 0))
        tip(ctk.CTkButton(actions, text="Best patch", height=28,
                          font=F_STRONG, **BTN_SECONDARY,
                          command=self.show_best_patch),
            TIPS["best_patch"]).pack(side="left", fill="x", expand=True,
                                     padx=(0, 3))
        tip(ctk.CTkButton(actions, text="Worked out", height=28,
                          font=F_STRONG, **BTN_WARN,
                          command=self.mark_worked_out),
            TIPS["worked_out"]).pack(side="left", fill="x", expand=True,
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
        for label, command, words in (
                ("MOVE CENTRE HERE", self.set_survey_centre, TIPS["move_centre"]),
                ("CLEAR", self.clear_survey, TIPS["clear_survey"])):
            tip(ctk.CTkButton(survey_row, text=label, height=28,
                              font=F_STRONG, **BTN_SECONDARY,
                              command=command), words).pack(side="left", fill="x",
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
            tip(box, TIPS.get(key)).pack(side="left", fill="x", expand=True)
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
        tip(self.btn_update_deposit, TIPS["update_deposit"]).pack(side="right",
                                                                  padx=(6, 0))
        # A deposit seen from the Rhino, marked where it is (1.10035, #197).
        self.btn_range = ctk.CTkButton(
            mark_row, text="FROM\nRANGE", width=70, height=54,
            font=F_SMALL_B, **BTN_SECONDARY, command=self.open_range_window)
        tip(self.btn_range, TIPS["range_mark"]).pack(side="right", padx=(6, 0))
        self.btn_mark = ctk.CTkButton(
            mark_row, text="MARK DEPOSIT", height=54,
            font=F_ACTION, **BTN_PRIMARY, command=self.mark_deposit)
        tip(self.btn_mark, TIPS["mark"]).pack(side="left", fill="x", expand=True)

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
            tip(button, TIPS["pad_" + name]).pack(side="left", fill="x", expand=True,
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
        tip(ctk.CTkButton(self.detail_buttons, text="MINED OUT", height=32,
                          font=F_STRONG, **BTN_WARN,
                          command=self.mark_mined), TIPS["mined_out"]).pack(
                              fill="x", pady=(2, 4))
        tip(ctk.CTkButton(self.detail_buttons, text="Edit  (or double-click it)",
                          height=30, font=F_STRONG, **BTN_SECONDARY,
                          command=self.edit_selected), TIPS["edit"]).pack(
                              fill="x", pady=2)
        tip(ctk.CTkButton(self.detail_buttons, text="Copy to share", height=30,
                          font=F_STRONG, **BTN_SECONDARY,
                          command=self.copy_selected), TIPS["copy_share"]).pack(
                              fill="x", pady=2)
        # 1.10035: shown only on a deposit marked depleted (SET ACTIVE) and
        # on one that is due a look (STILL DEPLETED); placed above Delete.
        self.btn_still = tip(ctk.CTkButton(
            self.detail_buttons, text="CONFIRM DEPLETED", height=30, font=F_STRONG,
            **BTN_SECONDARY, command=self.still_depleted),
            "You looked: it is still empty. The first date is kept and the mark comes off a week after this look.")
        self.btn_active = tip(ctk.CTkButton(
            self.detail_buttons, text="REGROWN", height=30, font=F_STRONG,
            **BTN_SECONDARY, command=self.set_active),
            "It has grown back. Takes the depleted mark off and sets its amount to unread until you read it again.")
        self.btn_delete = tip(ctk.CTkButton(
            self.detail_buttons, text="Delete", height=30,
            font=F_STRONG, **BTN_DANGER,
            command=self.delete_selected), TIPS["delete"])
        self.btn_delete.pack(fill="x", pady=2)

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
            self.follow_prompts(self.game)
            stage = "Earnings"
            # Its own stage, and not part of "Journal". The books decide
            # where one run ends and the next begins, which is a judgement
            # the reader deliberately does not make - so a mistake in here
            # is a mistake in here, and must not go out under the reader's
            # name the way every fault in tick used to.
            self.book_market()
            for note in self.watcher.drain_runs():
                self.extras_seen(note)
                if self.note_prices(note):
                    continue
                if note.get("event") == "Refined":
                    self.credit_refined(note)
                    self.refine_check(note)
                # The picture first: coming aboard takes the rigs off the map.
                self.dock_picture(note)
                self.rigs_on_vehicle(note)
                self.earnings_note(self.earnings.observe(note))
                self.extras_booked(note)
            self.save_refined()
            self.show_tonnes()
            stage = "Display"
            self.update_telemetry(self.game)
            # Back to Earnings for the readout as well as the bookkeeping.
            # "Display problem: ..." over a broken hold value would send
            # somebody looking at the map code.
            stage = "Earnings"
            self.update_earnings()
            self.post_discord_sessions()
            stage = "Online reporting"
            self.report_online(self.game)
        except Exception as exc:
            self.trouble(stage, exc)
        finally:
            # Always, whatever the journal just did. Results are not the
            # game's business.
            self.collect_results()
            self.persist_rigs()
            self.follow_bodies()
            self.follow_power()
            self.follow_layouts()
            self.follow_land()
            self.follow_ledger()
            self.follow_update()
            self.follow_input()
            try:
                self.follow_vehicle_overlay()
            except Exception as exc:
                self.trouble("Overlay", exc)
            try:
                self.wing_tick()
            except Exception as exc:
                self.trouble("Wing link", exc)
            try:
                self.keep_board()
            except Exception as exc:
                self.trouble("Leaderboard", exc)
            try:
                self.follow_crowd()
            except Exception as exc:
                self.trouble("Community figures", exc)
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

    # -- 1.10035 input: chat tags, from range, joystick, long press (inputmix.py)

    def follow_input(self):
        """Once a tick: chat commands, and the joystick and long-press timers."""
        IM.follow_input(self)

    def refine_ranged(self, commodity="", spec=None):
        """MARK or UPDATE at the spot of a deposit placed from range moves it
        there. The refined deposit, or None when there was nothing to refine."""
        return IM.refine_ranged(self, commodity, spec)

    def mark_from_range(self, bearing, metres, spec=None):
        """A deposit `metres` away on `bearing` from the Rhino. The new
        deposit, or None after saying why not."""
        return IM.mark_from_range(self, bearing, metres, spec)

    def open_range_window(self):
        """FROM RANGE: ask for the bearing and the distance."""
        try:
            window = attr(self, "_range_window")
            if window is not None and window.winfo_exists():
                window.destroy()
            self._range_window = RangeMarkWindow(self)
        except Exception as exc:
            self.say("Could not open that: %s" % exc, RED)

    @staticmethod
    def input_tones():
        """The colours the input features say things in, read when asked so
        a theme change is followed."""
        return {"ok": GREEN, "warn": AMBER, "bad": RED}

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
            "overlay": ("Overlay", self.toggle_overlay),
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
        table["zoom"] = ("Scope zoom", self.cycle_scope_zoom)
        table["wp_next"] = ("Survey waypoint", self.wp_next)
        table["wp_back"] = ("Survey waypoint", self.wp_back)
        table["wp_skip"] = ("Survey waypoint", self.wp_skip)
        table["wp_pause"] = ("Survey waypoint", self.wp_pause)
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
        rigs = self.rig_radar(state, rigs)
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
        self.follow_touchdown(state)
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
        """{"text": ...} for the red bar on the boxes, or None. A rig at
        your wheels comes first: it is the one you act on this second."""
        try:
            cue = self.rig_cue()
        except Exception:
            cue = None
        if cue:
            return cue
        watcher = attr(self, "watcher")
        if getattr(watcher, "in_srv", False) and getattr(watcher, "low_fuel", False):
            return {"text": "SRV FUEL LOW - HEAD BACK TO THE SHIP", "kind": "fuel"}
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
        out = {"ship_t": tonnes, "capacity": capacity,
               "rhino_t": rhino if in_srv else None}
        # The ship's hold card (1.10035), for a reader that tracks it.
        card = self.ship_card()
        if card is not None:
            out["hold"] = card
        return out

    # -- the ship's hold, map pictures, the session ledger (1.10035) ------

    def ship_card(self):
        """The ship's hold card - see shiphold.hold_card - or None for a
        reader that does not track the hold. Capacities the reader has seen
        go into the book, which also knows what earlier journals said.
        Never raises."""
        try:
            watcher = attr(self, "watcher")
            book = attr(self, "ship_book", None)
            if book is not None and book.observe(watcher):
                book.save()
            return SH.hold_card(watcher, book)
        except Exception:
            return None

    def hold_line(self):
        """The ship's hold as one line for the strip, while in the Rhino."""
        watcher = attr(self, "watcher")
        if not getattr(watcher, "in_srv", False):
            return ""
        card = self.ship_card()
        return card["line"] if card else ""

    def extras_seen(self, note):
        """A reader note, for what a session summary carries beyond its row:
        materials, crew wages, merits. Never raises."""
        try:
            books, ledger = attr(self, "earnings"), attr(self, "extras", None)
            if books is None or ledger is None:
                return False
            if note.get("event") == "MarketSell":
                self._sale_before = {str(r.get("id")): float(SV.earned(r) or 0)
                                     for r in books.sessions}
            changed = ledger.note(note, books.sessions)
            ledger.save()
            if changed and note.get("event") == "PowerplayMerits":
                self.board_merits(note)
            return changed
        except Exception:
            return False

    def board_merits(self, note):
        """Merits the game paid for selling mined cargo go on the
        leaderboard beside the commander's Power (1.10036). Not for a
        commander who pressed Leave. Never raises."""
        try:
            settings = attr(self, "settings", None) or {}
            community = attr(self, "community")
            if community is None or not settings.get("leaderboard_optin", True):
                return False
            report = LB.merits_report(note, getattr(attr(self, "watcher"), "power", ""),
                                      self.board_cmdr())
            return bool(report) and bool(community.report_merits(report, tag=LB_MERITS_TAG))
        except Exception:
            return False

    def extras_booked(self, note):
        """The books have taken a note. For a sale: which sessions it was
        booked to, and for how much, so its wages and merits find them."""
        try:
            books, ledger = attr(self, "earnings"), attr(self, "extras", None)
            before = attr(self, "_sale_before", None)
            if note.get("event") != "MarketSell" or ledger is None \
                    or books is None or before is None:
                return False
            self._sale_before = None
            split = {}
            for row in books.sessions:
                gained = float(SV.earned(row) or 0) - before.get(str(row.get("id")), 0.0)
                if gained > 0:
                    split[str(row.get("id"))] = gained
            return ledger.sale(note, split)
        except Exception:
            return False

    def plan_inputs(self):
        """What the map shows, as a picture would draw it, or None when it
        shows nothing."""
        plan = attr(self, "plan", None)
        rows = list(attr(plan, "rows", None) or []) if plan is not None else []
        rigs = attr(plan, "rigs", None) if plan is not None else None
        if not rows and not (isinstance(rigs, dict) and rigs.get("rigs")):
            return None
        survey = attr(plan, "survey", None)
        trail = attr(plan, "trail", None) or (survey.get("trail")
                                              if isinstance(survey, dict) else None)
        system, body = self.here()
        return {"rows": rows, "system": system, "body": body,
                "signal": str(attr(plan, "signal", "") or ""),
                "anchor": attr(plan, "signal_at", None), "survey": survey,
                "rigs": rigs, "trail": trail}

    def picture_now(self, when=None, save=True, path=None):
        """Draw the map as it is now and, with `save`, keep it in the
        pictures folder (or at `path`). Always answers with a dict: image,
        scene, path, name, why - why says in a sentence when there is no
        picture. Never raises."""
        out = {"image": None, "scene": None, "path": "", "name": "", "why": ""}
        ok, why = MI.pillow_status()
        if not ok:
            out["why"] = why
            return out
        inputs = self.plan_inputs()
        if inputs is None:
            out["why"] = "There is nothing on the map to draw yet."
            return out
        settings = attr(self, "settings", None) or {}
        cmdr = ""
        if settings.get("community_share_cmdr_name", True):
            cmdr = str(getattr(attr(self, "watcher"), "cmdr", "") or "")
        try:
            image, scene = MI.render_map(
                inputs["rows"], system=inputs["system"], body=inputs["body"],
                signal=inputs["signal"], anchor=inputs["anchor"],
                survey=inputs["survey"], rigs=inputs["rigs"], trail=inputs["trail"],
                cmdr=cmdr, when=when if when is not None else time.time(),
                version=APP_VERSION, colour=colour_for)
            out.update(image=image, scene=scene, name=MI.picture_name(
                inputs["system"], inputs["body"], inputs["signal"], when))
            if save:
                folder = MI.pictures_dir(DATA_DIR)
                out["path"] = MI.save_picture(image, path or os.path.join(folder, out["name"]))
                MI.tidy_pictures(folder)
        except OSError as problem:
            out["why"] = "The map picture could not be saved: %s" % problem
        except Exception as exc:
            self.trouble("Drawing the map picture", exc)
            out["why"] = "The map picture could not be drawn: %s" % exc
        return out

    def dock_picture(self, note):
        """The Rhino coming aboard: keep the map as it stood, before the
        rigs come off it (a setting). Only a dock that happens now - the
        reader gives every dock in the journal again on a restart. Never
        raises; True when a picture was saved."""
        try:
            if note.get("event") != "SRVDock" or not note.get("rhino") \
                    or note.get("player") is False:
                return False
            settings = attr(self, "settings", None) or {}
            if not settings.get("map_picture_auto", True):
                return False
            at = SV._epoch(note.get("when"))
            if not at or at < float(attr(self, "_boot_at", 0) or 0) - 2:
                return False
            result = self.picture_now(when=at)
            if result["path"]:
                self._pictures = (attr(self, "_pictures", None) or [])[-20:] + [(at, result["path"])]
                self.say("Map picture saved: %s" % result["name"], GREEN)
                return True
            if result["why"] and not attr(self, "_picture_told", False):
                self._picture_told = True
                self.say(result["why"], AMBER)
        except Exception as exc:
            self.trouble("Saving the map picture", exc)
        return False

    def save_map_picture(self):
        """Save map... : the picture, where the commander says."""
        result = self.picture_now(save=False)
        if result["image"] is None:
            return self.say(result["why"], AMBER)
        path = ""
        try:
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(
                parent=self, title="Save the map picture",
                initialdir=MI.pictures_dir(DATA_DIR), initialfile=result["name"],
                defaultextension=".png", filetypes=[("PNG picture", "*.png")])
        except Exception:
            path = os.path.join(MI.pictures_dir(DATA_DIR), result["name"])
        if not path:
            return None
        try:
            MI.save_picture(result["image"], path)
        except OSError as problem:
            return self.say("Could not save the map picture: %s" % problem, RED)
        return self.say("Map picture saved: %s" % path, GREEN)

    def copy_map_picture(self):
        """Copy map: the picture on the Windows clipboard, and saved too."""
        result = self.picture_now()
        if result["image"] is None:
            return self.say(result["why"], AMBER)
        ok, why = MI.copy_to_clipboard(result["image"])
        if ok:
            return self.say("Map picture copied - paste it into Discord or a "
                            "post. It is saved too: %s" % result["name"], GREEN)
        return self.say("%s Saved to %s" % (why, result["path"] or "the pictures folder"), AMBER)

    def share_map(self):
        """Share map: the picture saved, the finds of the best patch as text
        on the clipboard, and the folder open with the picture picked."""
        result = self.picture_now()
        if result["image"] is None:
            return self.say(result["why"], AMBER)
        scene = result["scene"]
        lines = [scene["title"] + " - " + scene["sub"]]
        lines += [share_line(d) for d in (scene.get("patch_deposits")
                                          or scene.get("deposits") or [])[:8]]
        try:
            put_on_clipboard(self, "\n".join(lines))
        except Exception as exc:
            return self.say("Could not reach the clipboard: %s" % exc, RED)
        if result["path"]:
            SB.open_folder(result["path"])
        return self.say("Map saved and the finds copied as text - paste the "
                        "text, drag the picture in: %s" % result["name"], GREEN)

    def discord_state(self, row):
        """What the Discord message for a session would have to say again if
        it changed: the credits sold, wages, merits, materials."""
        ledger = attr(self, "extras", None)
        extra = list(ledger.state_of(row.get("id"))) if ledger is not None else []
        return [int(SV.earned(row) or 0)] + extra

    def discord_picture(self, row):
        """(file name, bytes) of the map picture for a session, or None: the
        one saved when its Rhino docked, else - for a session that has just
        ended some other way - the map as it is now."""
        try:
            settings = attr(self, "settings", None) or {}
            if not settings.get("discord_attach_map", True):
                return None
            first = SV._epoch(row.get("started")) or 0
            last = SV._epoch(row.get("closed") or row.get("ended")) or time.time()
            path = ""
            for at, found in attr(self, "_pictures", None) or []:
                if first - 60 <= at <= last + 120 and os.path.isfile(found):
                    path = found
            if not path and time.time() - last <= 180:
                path = self.picture_now()["path"]
            if not path:
                return None
            with open(path, "rb") as handle:
                data = handle.read()
            if len(data) > MI.MAX_BYTES:
                return None
            return os.path.basename(path), data
        except Exception:
            return None

    def discord_job(self, hook, payload, sid, picture=None):
        """On the worker thread: post one session summary, with its map when
        there is one, and answer with JSON that names the session. Never
        raises - an answer that says what went wrong is still an answer."""
        try:
            try:
                if picture:
                    reply = EDO.discord_post_file(hook, payload, picture[0], picture[1])
                else:
                    reply = EDO.discord_post(hook, payload)
            except Exception:
                if not picture:
                    raise
                # A picture Discord would not take must not cost the summary.
                bare = json.loads(json.dumps(payload))
                bare["embeds"][0].pop("image", None)
                reply = EDO.discord_post(hook, bare)
            return json.dumps({"edsmt_session": sid, "message": reply})
        except Exception as exc:
            return json.dumps({"edsmt_session": sid, "error": str(exc)})

    def discord_edit_job(self, hook, payload, sid, message_id, keep):
        try:
            reply = EDO.discord_edit(hook, message_id, payload, keep=keep)
            return json.dumps({"edsmt_session": sid, "edit": True, "message": reply})
        except Exception as exc:
            return json.dumps({"edsmt_session": sid, "edit": True, "error": str(exc)})

    def discord_edits(self, hook):
        """Edit the message of every session whose figures have changed
        since it was posted - the sale, its wages, its merits - once things
        have gone quiet. The same message, never another one. Never raises;
        how many edits were queued."""
        try:
            book, books = attr(self, "post_book", None), attr(self, "earnings")
            settings = attr(self, "settings", None) or {}
            if book is None or books is None or not hook \
                    or not settings.get("discord_edit_after_sale", True):
                return 0
            rows = {str(r.get("id")): r for r in books.sessions}
            queued = 0
            for sid, entry in list(book.posted.items()):
                row = rows.get(sid)
                state = self.discord_state(row) if row is not None else None
                if row is None or not book.watch(sid, state):
                    continue
                summary = self.discord_summary(row)
                if summary is None:
                    continue
                if entry.get("image"):
                    summary["image"] = entry["image"]
                payload = EDO.discord_session_message(
                    row, row.get("cmdr") or "", when=entry.get("when"), summary=summary)
                book.edited(sid, state)
                self.worker.submit(
                    EDO.DISCORD_TAG,
                    lambda p=payload, s=sid, m=entry["id"], k=list(entry.get("attachments") or []):
                    self.discord_edit_job(hook, p, s, m, k))
                queued += 1
            return queued
        except Exception:
            return 0

    def discord_answer(self, message):
        """Discord's answer to a session post or edit: keep the message id,
        or say why not. False for anything that is not one."""
        try:
            data = json.loads(message)
        except (TypeError, ValueError):
            return False
        if not isinstance(data, dict) or "edsmt_session" not in data:
            return False
        sid, book = str(data["edsmt_session"]), attr(self, "post_book", None)
        if data.get("error"):
            if data.get("edit") and "404" in str(data["error"]) and book is not None:
                book.gone(sid)
            self.say("Discord did not take it: %s" % data["error"], AMBER)
            return True
        if book is not None:
            book.answered(sid, data.get("message"))
        return True

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
        return self.market_here()[0]

    def market_here(self, cargo=None):
        """(prices, station, when) of the market a hold is priced at.

        Docked, it is the station docked at, from this commander's own read
        of its board - and nothing at all when he has never read it, rather
        than (1.10034) whichever station's Market.json happened to be last.
        Undocked, his own read of a station in the system he is in - the one
        that pays most for `cargo` - and only without one the last market
        seen. 1.10034 had only the last: mining on 13 October with 89 t of
        Iridium aboard, that was a fleet carrier two systems away that buys
        none, and the window said "No market prices seen yet"."""
        watcher = attr(self, "watcher")
        book = attr(self, "market_book")
        self.book_market()
        station = str(getattr(watcher, "station", "") or "")
        system = str(getattr(watcher, "system", "") or "")
        if book is not None and getattr(watcher, "docked", False) and station:
            entry = book.stations.get(SV._station_key(system, station)) or {}
            return book.prices_at(system, station), station, entry.get("when") or ""
        if book is not None and system and not getattr(watcher, "docked", False):
            local = book.best_in(system, cargo)
            if local is not None:
                return local
        market = getattr(watcher, "market", None) or {}
        prices = {}
        for item in market.get("items") or []:
            name = str(item.get("commodity") or "")
            if name:
                prices[name] = item.get("sell") or 0
        return prices, market.get("station") or "", market.get("when") or ""

    def book_market(self):
        """The reader's last Market.json into the book of this commander's
        own reads, once each. Never raises."""
        book = attr(self, "market_book")
        market = getattr(attr(self, "watcher"), "market", None)
        if book is None or not isinstance(market, dict):
            return False
        when = str(market.get("when") or "")
        if not when or when == attr(self, "_book_read"):
            return False
        self._book_read = when
        try:
            self.presale_now(market)
        except Exception as exc:
            self.trouble("Selling here", exc)
        try:
            if book.note_market(market):
                book.save()
                return True
        except Exception:
            return False
        return False

    def presale_now(self, market=None):
        """Docked with the commodities board open and Rhino cargo aboard:
        what selling it here comes to, said once for each board read
        (#260). The line, or "" when there is nothing to say."""
        watcher = attr(self, "watcher")
        market = market if market is not None else getattr(watcher, "market", None)
        if watcher is None or not getattr(watcher, "docked", False) \
                or not isinstance(market, dict):
            return ""
        hold = self.aboard_for_sale()
        if not hold:
            return ""
        show, note = PS.merits_count(getattr(watcher, "power", ""),
                                     getattr(watcher, "power_here", {}))
        rate = None
        merits = attr(self, "merits", None)
        if show and merits is not None:
            rate = merits.per_credit()
        ledger, books = attr(self, "extras", None), attr(self, "earnings", None)
        wages = PS.wage_share(getattr(ledger, "sessions", {}),
                              getattr(books, "sessions", []))
        found = PS.quote(hold, market, rate, wages, show)
        if not found:
            return ""
        line = PS.words(found, note)
        self.presale = found
        self.say(line, GREEN)
        self.flash("SELLING HERE", "%d t - %s cr" % (found["tonnes"], PS.money(found["credits"])),
                   GREEN)
        return line

    def note_prices(self, note):
        """A reader note for the price book and the merit rate.

        A sale is what that station paid, and the merits that follow it are
        how Powerplay pays for it. True for a note only these want - the
        merits - so the books never see it. Never raises."""
        try:
            name = note.get("event")
            merits = attr(self, "merits")
            if merits is not None and merits.observe(note):
                merits.save()
            if name == "MarketSell":
                book = attr(self, "market_book")
                if book is not None and book.note_sale(
                        note.get("system"), note.get("station"),
                        note.get("commodity"), note.get("sell_price"),
                        note.get("when")):
                    book.save()
            return name in ("PowerplayMerits", "MissionCompleted")
        except Exception:
            return False

    def aboard_for_sale(self):
        """What is aboard to sell - SRV and ship together, as they are now -
        of every commodity the Rhino digs or recently dug.

        1.10034 priced the smaller of what is aboard and what the books said
        was mined and unsold, which put 33 t beside a hold of 89 t. The hold
        is the hold; bought or hauled goods are still left out."""
        try:
            hold = self.hold_now()
            ours = {SV.fold(name) for name in self.mined_aboard()}
            ours.update(SV.fold(name) for name in SV.KNOWN_COMMODITIES)
        except Exception:
            return {}
        out = {}
        for name, count in dict(hold or {}).items():
            try:
                count = int(count or 0)
            except (TypeError, ValueError):
                continue
            if count > 0 and SV.fold(name) in ours:
                out[name] = count
        return out

    def jump_range(self):
        """Light years a jump: the setting if one is set, else what the
        ship's newest Loadout said. None when neither is known."""
        try:
            setting = float((attr(self, "settings", None) or {}).get("jump_range_ly") or 0)
        except (TypeError, ValueError):
            setting = 0.0
        if setting > 0:
            return setting
        ship = getattr(attr(self, "watcher"), "max_jump_ly", None)
        try:
            return float(ship) if ship and float(ship) > 0 else None
        except (TypeError, ValueError):
            return None

    def hold_split(self):
        """(tonnes in the ship, tonnes in the SRV) as the reader has them."""
        holds = dict(getattr(attr(self, "watcher"), "holds", None) or {})
        def total(name):
            return sum(int(v or 0) for v in dict(holds.get(name) or {}).values()
                       if str(v).lstrip("-").isdigit() and int(v) > 0)
        return total("Ship"), total("SRV")

    def one_stop(self, within_ly=None, top=3):
        """The stations that take the most of what is aboard, best first
        (SP.whole_hold), from every price this app has. Never raises."""
        try:
            hold = self.aboard_for_sale()
            return SP.whole_hold(hold, self.sell_rows_for, within_ly=within_ly,
                                 top=top, trends=attr(self, "trends", None))
        except Exception:
            return []

    def price_rows_for(self, name):
        """Every price known for one commodity from here, judged: this
        commander's own reads in this system, and the server's answer."""
        self.book_market()
        rows = []
        quote = self.fresh_quotes().get(SV.fold(name))
        if quote:
            rows.extend(quote.get("rows") or [r for r in (quote.get("best"),
                                                          quote.get("here")) if r])
        book = attr(self, "market_book")
        system = str(getattr(attr(self, "watcher"), "system", "") or "")
        if book is not None and system:
            rows.extend(book.rows(name, system=system))
        return judge_prices(rows)

    def best_price(self, name):
        """(credits a tonne, row or None, how) to estimate a commodity with.

        how is "fresh" - under a day old and not a lone outlier - or "stale"
        for the best older price, or "average" for the galactic average, or
        "" when nothing is known."""
        try:
            system = str(getattr(attr(self, "watcher"), "system", "") or "")
            picked = pick_prices(self.price_rows_for(name), system)
        except Exception:
            picked = {}
        for key, how in (("credible", "fresh"), ("stale_pick", "stale")):
            row = picked.get(key)
            if row:
                return int(row["sell"]), row, how
        average = self.galactic_average(name)[0]
        return (int(average), None, "average") if average else (0, None, "")

    def session_estimate(self, run):
        """What a Rhino session is worth so far, told as plainly as it can be.

        Sold credits as they are, and every tonne mined and not yet sold at
        the best credible price - so a session that has not been to a
        station yet still has a value and a Cr/hr. Merits from the rate
        learnt off this commander's own sales, or None. Never raises."""
        out = {"hours": 0.0, "tonnes": 0, "t_hr": 0.0, "earned": 0.0,
               "value": 0.0, "cr_hr": 0.0, "merits_hr": None, "lines": [],
               "kinds": set()}
        if not run:
            return out
        try:
            mined = SV.unpack_counts(run.get("mined"))
            sold = {SV.fold(k): v for k, v in SV.unpack_counts(run.get("sold")).items()}
            hours = SV.session_hours(run)
            earned = float(SV.earned(run) or 0)
            value = earned
            for name, tonnes in sorted(mined.items(), key=lambda kv: -kv[1]):
                left = max(0, int(tonnes) - int(sold.get(SV.fold(name), 0)))
                price, row, how = self.best_price(name)
                if left and how:
                    out["kinds"].add(how)
                value += left * price
                out["lines"].append({"commodity": name, "tonnes": int(tonnes),
                                     "t_hr": tonnes / hours if hours > 0 else 0.0,
                                     "price": price, "row": row, "how": how,
                                     "worth": left * price})
            out.update(hours=hours, tonnes=sum(mined.values()), earned=earned,
                       value=value, t_hr=SV.tonnes_per_hour(run),
                       cr_hr=value / hours if hours > 0 else 0.0)
            merits = attr(self, "merits")
            if merits is not None and hours > 0:
                # Each commodity at its own learnt rate (1.10035).
                earnt = session_merits(merits, out["lines"], sold, earned)
                out["merits_hr"] = earnt / hours if earnt else None
        except Exception:
            return out
        return out

    def finds_in(self, run):
        """How many deposits this commander marked during a session."""
        store = attr(self, "store")
        first, last = SV._epoch(run.get("started")), SV._epoch(run.get("ended"))
        if store is None or not first:
            return 0
        last = last or time.time()
        count = 0
        for row in list(getattr(store, "deposits", None) or []):
            at = SV._epoch(row.get("recorded"))
            if at and first <= at <= last:
                count += 1
        return count

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
        # The ship's hold, while in the Rhino (1.10035).
        hold_card_line = self.hold_line()
        if hold_card_line:
            bits.append(hold_card_line)
        # Both holds. Out in the SRV, Cargo.json is the SRV's, and a strip
        # that read only that said "hold 6t" over a ship with thirty tonnes
        # of ore in it. Only what a Rhino session dug up (1.10031): hauled
        # cargo is somebody else's business, not these earnings.
        # 1.10035: the hold as it is, SRV and ship (aboard_for_sale), priced
        # at the station docked at, or undocked at your own read of a market
        # in this system (market_here).
        cargo = self.aboard_for_sale()
        tonnes = sum(int(count) for count in cargo.values())
        if tonnes:
            hold = "mined aboard %dt" % tonnes
            prices, where, _when = self.market_here(cargo)
            worth = SV.hold_value(cargo, prices)
            if worth:
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
            best, radius, priced, aboard, stale = self.best_nearby(cargo,
                                                                  detail=True)
            if best:
                hold += ", up to %s Cr within %d Ly" % (credits_text(best),
                                                        radius)
                if priced < aboard:
                    hold += " (%d of %d priced)" % (priced, aboard)
                if stale:
                    hold += " - stale prices"
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
            return 0, "Not connected to the community map - check Settings > Sharing."
        system = str(getattr(attr(self, "watcher"), "system", "") or "")
        if not system:
            return 0, "The game has not said which system you are in yet."
        wanted = worth_asking(self.aboard_for_sale())
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
                    # Every row, not just the top two (1.10035): the top
                    # one can be stale or a lone outlier, and the next is
                    # then the price to go by.
                    "rows": answer_rows(json.loads(message)
                                        if isinstance(message, str)
                                        else dict(message)),
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

    def best_nearby(self, cargo, detail=False):
        """(credits, radius, priced, aboard) at the best price found for each.

        Only what has a quote is added up, and the count of those beside the
        count aboard says so - a total that quietly leaves out half the hold
        is not "up to" anything. The best is judged (1.10035): Demand 0 is
        not a price, a fresh one beats a stale one, and with detail a fifth
        value says whether any price used is more than a day old.
        """
        quotes = self.fresh_quotes()
        if not cargo or not quotes:
            return (0, 0, 0, len(cargo or {})) + ((False,) if detail else ())
        total, radius, priced, stale = 0, 0, 0, False
        for name, count in cargo.items():
            quote = quotes.get(SV.fold(name))
            if quote is None or not quote.get("best"):
                continue
            best = pick_prices(self.price_rows_for(name))["best"]
            if not best:
                continue
            total += best["sell"] * int(count)
            radius = max(radius, int(quote.get("radius") or 0))
            priced += 1
            stale = stale or bool(best.get("stale"))
        return (total, radius, priced, len(cargo)) + ((stale,) if detail else ())

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
            if CR.first_tonne_back(row, note.get("commodity")):
                self.report_regrown(row, "refined", SV._epoch(note.get("when")) or None)
            self._refined_dirty = True
            self._refined_at = attr(self, "_refined_at", 0.0) or time.time()
            self._tonnes_changed = (str(row.get("id")), time.time())
            # When each marked deposit last gave a tonne, on the journal's
            # clock: a session's "deposits worked" (1.10035).
            worked = attr(self, "_worked", None)
            if worked is None:
                worked = self._worked = {}
            worked[str(row.get("id"))] = SV._epoch(note.get("when")) or time.time()
        return row

    def deposits_worked(self, run):
        """How many of the commander's marked deposits gave tonnes during a
        session, as far as this run of EDSMT saw. 0 when it saw none."""
        worked = attr(self, "_worked", None) or {}
        first, last = SV._epoch(run.get("started")), SV._epoch(run.get("ended"))
        if not first:
            return 0
        last = last or time.time()
        return sum(1 for at in list(worked.values()) if first <= at <= last)

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
        capacity = getattr(watcher, "cargo_capacity", None)
        card = self.ship_card()
        if card is not None:
            # What the journal stated, and what an earlier journal said the
            # hold was rated at, when this one has no Loadout.
            if card["known"]:
                tonnes = card["tonnes"]
            capacity = card["capacity"]
        return tonnes, capacity

    def flash_ship_hold(self, moved=""):
        """After every transfer from the Rhino: what is in the ship now.

        The question a transfer raises is "is the ship full yet", and it
        used to take a trip to the ship's panel to answer it."""
        card = self.ship_card()
        if card is not None and not card["known"]:
            # Not seen this session: the tonnes moved are all there is to
            # say, and the ship's own panel is the answer to the rest.
            return self.flash(card["title"], card["detail"], AMBER)
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
        rigs = self.rig_radar(state, rigs)
        survey = self.survey_view(system, body, centre, radius)
        self.plan.map_prefs = self.map_prefs(prices=True)
        self.plan.guidance = self.guidance_view(state, centre, radius) if live else None
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
            # 1.10035: the three most valuable it can hold, each once -
            # what the signal offers and what has been marked in it.
            names = SBK.location_names(
                offered, [d.get("commodity") for d in self.store.at(system, body, number)])
            top = SBK.best_commodities(names, self.market_prices())
            if top:
                every = SBK.best_commodities(names, None, count=len(names) or 1)
                listed = ", ".join(top)
                if len(every) > len(top):
                    listed += " +%d" % (len(every) - len(top))
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
        # 1.10038: what other commanders found in this signal, under yours.
        # On a body where you have marked nothing yet, this is what the
        # signal holds.
        theirs = []
        if system and body:
            try:
                theirs = self.zone_finds(system, body, signal)[1]
            except Exception as exc:
                self.trouble("Shared finds in this signal", exc)
        header = self.deposit_header
        if header is not None:
            header.configure(text="SIGNAL %s  (%d)%s" % (
                signal, len(rows), "  +%d shared" % len(theirs) if theirs else ""))
        if not rows:
            ctk.CTkLabel(box, text="Nothing marked in signal %s yet.\n"
                                   "Drive to a scanner ping and press %s."
                              % (signal, self.key("deposit", "MARK DEPOSIT")),
                         font=F_SMALL, text_color=DIM,
                         justify="left").pack(pady=8, padx=6, anchor="w")
            self._show_strays(box, strays, signal)
            self._show_shared(box, theirs)
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
        self._show_shared(box, theirs)

    def _show_shared(self, box, theirs):
        """Other commanders' finds in this signal, one row each: pick one
        and the card on the right is its, and the overlay guides to it. Not
        editable from here - they are not in your records."""
        if not theirs:
            return
        chosen = (self.selected or {}).get("id")
        ctk.CTkLabel(box, text="Shared finds in this signal:",
                     font=F_SMALL_B, text_color=DIM, anchor="w",
                     justify="left").pack(fill="x", padx=6, pady=(8, 2))
        for row in theirs:
            bits = [row.get("commodity") or "unnamed"]
            if row.get("rigs"):
                bits.append("%sR" % row["rigs"])
            if row.get("amount"):
                bits.append(row["amount"])
            bits.append("- %s" % (row.get("cmdr") or ANONYMOUS))
            line = ctk.CTkFrame(box, fg_color="transparent")
            line.pack(fill="x", pady=1)
            ctk.CTkButton(
                line, text="  ".join(bits), anchor="w", height=28,
                font=F_SMALL,
                **(BTN_PRIMARY if row.get("id") == chosen else BTN_ROW),
                command=lambda r=row: self.pick_deposit(r)
            ).pack(side="left", fill="x", expand=True)

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

    def follow_touchdown(self, state):
        """The mining location the game says you touched down nearest.

        Touchdown and Liftoff name it: "#index=4" in NearestDestination.
        Nearest, not chosen, so it is a hint: on a body with nothing logged
        yet, and nothing targeted, it sets the Signal box; otherwise it is
        only said. Once each time it changes."""
        touched = str(getattr(state, "touchdown_signal", "") or "").strip()
        if not touched or touched == attr(self, "_touchdown_applied", ""):
            return
        self._touchdown_applied = touched
        if str(getattr(state, "target_signal", "") or "").strip():
            return
        try:
            system, body = self.here()
            fresh = not self.store.locations_on(system, body)
            if fresh and touched != str(self.signal()).strip():
                self.choose_signal(touched)
                self.say("Touched down by mining location %s - the Signal box "
                         "is set to it." % touched, CYAN)
            else:
                self.say("Touched down nearest mining location %s." % touched,
                         DIM)
        except Exception as exc:
            self.trouble("Signal from the touchdown", exc)

    def follow_arrival(self, state):
        """Pick the signal you have come into, once per arrival, and say
        what is in it.

        The box used to keep whatever it said last, so arriving at signal 5
        with it still on 1 had the scope zoomed out to hold signal 1 forty
        kilometres back - and a deposit marked there was filed under 1.
        Only on arriving somewhere new: a number picked by hand while you
        stand there is left alone until you drive into another signal.

        1.10038: not only your own logged signals. On a body where you have
        logged nothing, the finds other commanders shared say which
        location you are in and what it holds - from the glide down, not
        only once the game has it targeted. zone.py decides; a location the
        game has targeted right now keeps the box.
        """
        if not getattr(state, "has_position", False) or not state.radius_m:
            return
        system, body = self.here()
        if not (system and body):
            return
        zone = ZN.zone_here(self.store.locations_on(system, body),
                            self.shared_finds_on(system, body),
                            state.lat, state.lon, state.radius_m,
                            getattr(state, "altitude", None))
        at = (system, body, zone["signal"]) if zone else None
        if at == attr(self, "_arrived_at", None):
            if at is None:
                self.zone_quiet(state, system, body)
            return
        self._arrived_at = at
        if at is None:
            self.zone_quiet(state, system, body)
            return
        boxed = str(self.signal()).strip()
        # Two logged signals close together: while the one in the box is
        # also one you are standing in, it stays - its finds are filed
        # under it, and flipping at an invisible line would split them.
        current = self.store.location(system, body, boxed)
        if at[2] != boxed and current is not None and SV.nearest_signal(
                [current], state.lat, state.lon, state.radius_m,
                PV.SIGNAL_AT_M) is not None:
            return
        targeted = str(getattr(state, "destination_signal", "") or "").strip()
        try:
            picked = at[2] != boxed and not targeted
            if picked:
                self.choose_signal(at[2])
            mine, theirs = self.zone_finds(system, body, at[2])
            line = ZN.zone_line(zone, mine, theirs)
            if picked:
                line += " - signal %s picked for you." % at[2]
            self.say(line, CYAN)
        except Exception as exc:
            self.trouble("Signal you are at", exc)

    def shared_finds_on(self, system, body):
        """Other commanders' finds on this body, as take_shared filed them,
        or nothing - with the shared finds switched off, nothing too."""
        if not self.settings.get("show_shared_finds", True):
            return []
        book = attr(self, "shared", None)
        if not isinstance(book, dict):
            return []
        entry = book.get((str(system).lower(), str(body).lower()))
        return list(entry["rows"]) if entry else []

    def zone_finds(self, system, body, signal):
        """(yours, theirs): what is filed under one signal on this body -
        your own deposits, and the shared finds that are not yours come
        back from the server."""
        mine = self.store.at(system, body, signal)
        state = attr(self, "game", None)
        radius = getattr(state, "radius_m", None) or 1e6
        theirs = ZN.others(ZN.finds_in(signal, self.shared_finds_on(system, body)),
                           mine, radius, SAME_FIND_M)
        return mine, theirs

    def zone_quiet(self, state, system, body):
        """Nothing known within reach: one dim line, once per body, so the
        commander knows why nothing shows. Waits for this body's shared
        finds when they have been asked for; with no server to ask it
        speaks at once."""
        told = attr(self, "_zone_told", None)
        if not isinstance(told, set):
            told = self._zone_told = set()
        key = (str(system).lower(), str(body).lower())
        if key in told:
            return False
        community = attr(self, "community")
        asking = (community is not None and getattr(community, "can_read", False)
                  and self.settings.get("show_shared_finds", True))
        book = attr(self, "shared", None)
        answered = isinstance(book, dict) and key in book
        if asking and not answered:
            return False
        told.add(key)
        try:
            count = state.mining_signals()
        except Exception:
            count = 0
        self.say(ZN.nothing_line(ZN.reach_m(getattr(state, "altitude", None)), count), DIM)
        return True

    def zone_card(self):
        """The location you are in, for the overlay's STATUS box - its
        number and top finds - or None when you are in none, or have no
        position to be in one with."""
        at = attr(self, "_arrived_at", None)
        state = attr(self, "game", None)
        if not at or state is None or not getattr(state, "has_position", False):
            return None
        system, body, signal = at
        try:
            mine, theirs = self.zone_finds(system, body, signal)
        except Exception:
            return None
        return ZN.status_card(signal, mine, theirs)

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
        if self.refine_ranged(commodity):
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
            rigs_fit=self.rigs_fit_here(state, self.fields["rigs"].get()),
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
        self.post_discord_find(record)
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

    # -- several Rhinos off one ship ---------------------------------------
    #
    # A Panther Clipper carries two Rhinos: six rigs each, twelve on the
    # ground. The game gives each Rhino its own ID, and the journal says
    # which one the commander climbs into. The rig keys act on the Rhino
    # being driven - or, on foot or in the ship, the last one driven - so
    # Alt+4 is rig 1 of whichever Rhino you are in. With rigs from two
    # Rhinos down they show as A1-A6 and B1-B6, in the order each Rhino
    # dropped its first; with one Rhino's, plain 1-6 as ever.

    def _rhino_now(self):
        """The Rhino the rig keys act on, by the game's ID, or None."""
        state = attr(self, "game", None)
        try:
            rid = state.current_rhino() if state is not None else None
        except Exception:
            rid = None
        return None if rid is None else str(rid)

    def _rig_rhinos(self):
        """The Rhinos with rigs marked here, in the order each dropped one."""
        rigs = attr(self, "rigs_at", None) or {}
        order = list(rigs.get("rhinos") or [])
        for rig in rigs.get("rigs") or []:
            if rig.get("srv") not in order:
                order.append(rig.get("srv"))
        return order

    def rig_label(self, rig):
        """'3' while only one Rhino's rigs are down, 'A3' or 'B3' once two."""
        order = [srv for srv in self._rig_rhinos() if srv is not None]
        n = rig.get("n")
        if len(order) < 2:
            return "%s" % n
        try:
            letter = SV.RHINO_LETTERS[order.index(rig.get("srv"))]
        except (ValueError, IndexError):
            letter = "?"
        return "%s%s" % (letter, n)

    @staticmethod
    def _same_rhino(rig, rhino):
        """Whether a rig belongs to this Rhino. Not knowing either side
        means yes - one Rhino, as it always was."""
        return rhino is None or rig.get("srv") is None or rig.get("srv") == rhino

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
            self.rigs_at = {"system": system, "body": body, "rigs": [],
                            "rhinos": []}
        rhino = self._rhino_now()
        radius = state.radius_m or 0
        # Where the rig itself is: behind the cockpit Status.json places.
        spot_lat, spot_lon = self.rig_spot(state)

        def metres_to(rig):
            if not radius:
                return None
            return SV.surface_range_m(spot_lat, spot_lon, rig["lat"],
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
            mine = next((rig for rig in rigs if rig["n"] == n
                         and self._same_rhino(rig, rhino)), None)
            if mine is not None:
                away = metres_to(mine)
                if away is not None and away < RIG_SAME_M:
                    return self.say("Rig %s is already down here."
                                    % self.rig_label(mine), AMBER)
                moved_from = away
                self.rigs_at["rigs"] = [
                    r for r in self.rigs_at["rigs"]
                    if not (r["n"] == n and self._same_rhino(r, rhino))]
        else:
            for rig in rigs:
                away = metres_to(rig)
                if away is not None and away < RIG_SAME_M:
                    return self.say("Rig %s is already marked here."
                                    % self.rig_label(rig), AMBER)
            taken = {rig["n"] for rig in rigs if self._same_rhino(rig, rhino)}
            free = [k for k in range(1, MAX_RIGS + 1) if k not in taken]
            if not free:
                return self.say("All %d rigs of this Rhino are marked. %s when "
                                "you have collected them." % (
                                    MAX_RIGS, self.key("allup", "RIGS UP")),
                                AMBER)
            n = free[0]
        what = self.rig_commodity(state, system, body)
        rig = {"n": n, "lat": spot_lat, "lon": spot_lon, "at": time.time(),
               "commodity": what, "srv": rhino}
        self.rigs_at.setdefault("rhinos", [])
        if rhino not in self.rigs_at["rhinos"]:
            self.rigs_at["rhinos"].append(rhino)
        self.rigs_at["rigs"].append(rig)
        # Every rig put down this time on the body, kept after it comes up,
        # so the layout can be shared when the last one does (#218) - rigs
        # picked up one by one leave nothing in "rigs" by then.
        history = self.rigs_at.setdefault("placed_all", [])
        history[:] = [r for r in history
                      if not (r.get("n") == rig["n"] and r.get("srv") == rig.get("srv"))]
        history.append(dict(rig))
        order = self._rig_rhinos()
        self.rigs_at["rigs"].sort(key=lambda r: (order.index(r.get("srv"))
                                                 if r.get("srv") in order else 0,
                                                 r["n"]))
        label = self.rig_label(rig)
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
        # Counted per Rhino: "3 of 6" is this Rhino's, whatever the other
        # one has down.
        down = len([r for r in self.rigs_at["rigs"]
                    if self._same_rhino(r, rhino)])
        self.flash("RIG %s %s%s" % (label,
                                    "MOVED" if moved_from is not None else "DOWN",
                                    ("  " + what.upper()) if what else ""),
                   "%d of %d  -  %s" % (down, MAX_RIGS,
                                        "warning past %s" % _metres(limit)
                                        if limit else "distance warning off"))
        if moved_from is not None:
            return self.say("Rig %s moved here%s - %s from where it was marked."
                            " %s picks a rig up." % (
                                label, (" on " + what) if what else "",
                                _metres(moved_from), self.key("rig%dup" % n,
                                                              "RIGS UP")), GREEN)
        pin = self.plan_pin_at(spot_lat, spot_lon)
        clash = self.wing_clash(spot_lat, spot_lon)
        crowded = self.own_clash(spot_lat, spot_lon, exclude=rig)
        if clash:
            self.flash("RIG %s DOWN - CLOSE TO %s" % (label, clash[0].upper()),
                       "%s from their rig %d" % (_metres(clash[2]), clash[1]),
                       AMBER)
        elif crowded:
            # Your own rigs, the same check as a wingmate's (1.10034).
            self.flash("RIG %s DOWN - CLOSE TO RIG %s" % (label, crowded[1]),
                       "%s apart - inside the %s spacing" % (
                           _metres(crowded[2]), _metres(self.planner_spacing())),
                       AMBER)
        return self.say("Rig %s down%s%s (%d of %d). %s" % (
            label, (" on " + what) if what else "",
            (" at pin P%d" % pin) if pin else "", down, MAX_RIGS,
            "You will be warned past %s from any rig." % _metres(limit) if limit
            else "The distance warning is off in Settings."), GREEN)

    def rig_up(self, n):
        """One rig collected: stop watching it. The last one up is every
        rig up, with everything that goes with that. With two Rhinos' rigs
        down it is rig n of the Rhino you are in."""
        try:
            n = int(n)
        except (TypeError, ValueError):
            return self.say("No such rig.", AMBER)
        rigs = self._rigs_here()
        rhino = self._rhino_now()
        mine = [rig for rig in rigs
                if rig["n"] == n and self._same_rhino(rig, rhino)]
        if not mine:
            return self.say("Rig %d is not marked down%s." % (
                n, " - no rigs are" if not rigs else
                (" from this Rhino" if any(r["n"] == n for r in rigs) else "")),
                AMBER)
        label = self.rig_label(mine[0])
        self.rigs_at["rigs"] = [r for r in self.rigs_at["rigs"]
                                if r is not mine[0]]
        left = len(self.rigs_at["rigs"])
        if not left:
            return self.rigs_up(picked=label)
        # The warning was about whichever rig was farthest; that may have
        # been this one. The next poll works it out again from the rest.
        self._rigs_warned = False
        self._rigs_final = False
        self.clear_rig_alarm()
        self.refresh_rigs_note()
        self.redraw()
        self.flash("RIG %s UP" % label, "%d still down" % left)
        return self.say("Rig %s up. %d still down: %s." % (
            label, left, ", ".join(self.rig_label(r)
                                   for r in self.rigs_at["rigs"])), GREEN)

    def rig_event(self, what, n=None):
        """A rig going down or the last one coming up, handed to the books:
        the first rig down starts an Earnings session, the last one up ends
        it. Never raises - the rig is marked whatever the books make of it."""
        try:
            system, body = self.here()
            line = self.earnings.observe({
                "event": what, "when": SV.utc_now(), "rig": n,
                "srv_id": self._rhino_now(),
                "system": system, "body": body,
                "cmdr": getattr(attr(self, "watcher"), "cmdr", "") or ""})
            if line:
                self.earnings_note(line)
        except Exception:
            pass

    def trace_key(self):
        """The rig planner's key: start tracing a deposit's edge, or finish
        the trace."""
        return self.planner_trace()

    # -- the rig planner -------------------------------------------------------

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
            "area_m2": RP.area(trace.points),
            "fit": RP.fit_count(trace.points, spacing, pins=pins)}
        try:
            self.save_rig_plan(self.rig_plan, state)
        except Exception as exc:
            self.trouble("Rig planner", exc)
        self.redraw()
        count = len(pins)
        self.flash("RIG PLAN  %d PIN%s" % (count, "" if count == 1 else "S"),
                   "%d m apart - drive to P1" % round(spacing))
        return self.say("Rig planner: %d rig%s fit %d m apart in what you "
                        "traced (about %s m2). The pins are on the scope in "
                        "driving order - drop a rig on each; the next one is "
                        "amber, done ones go green.%s" % (
                            count, "" if count == 1 else "s", round(spacing),
                            "{:,}".format(int(round(RP.area(trace.points), -1))),
                            " Room for %d in all; a Rhino carries %d."
                            % (self.rig_plan["fit"], MAX_RIGS)
                            if self.rig_plan["fit"] > MAX_RIGS else ""),
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
        # Two Rhinos' rigs go as 1-6 and 7-12: the server takes 1 to 12.
        order = [srv for srv in self._rig_rhinos() if srv is not None]
        beat["rigs"] = [{"n": int(rig["n"]) + 6 * (
                             order.index(rig.get("srv")) % 2
                             if rig.get("srv") in order else 0),
                         "lat": float(rig["lat"]), "lon": float(rig["lon"])}
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

    def rig_offset(self):
        """How far behind the cockpit a rig lands, in metres (a setting)."""
        try:
            value = float((attr(self, "settings", None) or {}).get(
                "rig_offset_m", RIG_OFFSET_M))
        except (TypeError, ValueError):
            value = RIG_OFFSET_M
        return max(0.0, min(RIG_OFFSET_MAX_M, value))

    def rig_spot(self, state):
        """(lat, lon) of a rig dropped now: the position Status.json gives,
        moved back along the heading by the rig offset (1.10034). Without a
        heading or a radius, the position as given."""
        offset = self.rig_offset()
        heading = getattr(state, "heading", None)
        radius = getattr(state, "radius_m", None)
        if not offset or heading is None or not radius:
            return state.lat, state.lon
        return SV.destination(state.lat, state.lon, (float(heading) + 180.0) % 360.0,
                              offset, radius)

    def own_clash(self, lat, lon, exclude=None):
        """(label, rig label, metres) for your own rig closest to this spot
        inside the rig spacing, or None. Every Rhino's rigs count."""
        state = attr(self, "game")
        if state is None or not getattr(state, "radius_m", None):
            return None
        spacing = self.planner_spacing()
        closest = None
        for rig in self._rigs_here():
            if exclude is not None and rig is exclude:
                continue
            metres = SV.surface_range_m(lat, lon, rig["lat"], rig["lon"],
                                        state.radius_m)
            if metres < spacing and (closest is None or metres < closest[2]):
                closest = ("rig", self.rig_label(rig), metres)
        return closest

    def rig_cue(self, state=None, now=None):
        """COLLECT RIG n within RIG_COLLECT_M of one of your rigs, TOO CLOSE
        TO RIG n inside the spacing - so you know before you drop the next
        one. {"text", "colour", "kind"} or None. Only in a Rhino."""
        state = attr(self, "game") if state is None else state
        if state is None or not getattr(state, "has_position", False) or \
                not getattr(state, "radius_m", None):
            return None
        if not getattr(state, "in_rhino", getattr(state, "in_srv", False)):
            return None
        rigs = self._rigs_here()
        if not rigs:
            return None
        now = time.time() if now is None else now
        nearest = None
        for rig in rigs:
            metres = SV.surface_range_m(state.lat, state.lon, rig["lat"],
                                        rig["lon"], state.radius_m)
            if nearest is None or metres < nearest[0]:
                nearest = (metres, rig)
        metres, rig = nearest
        label = self.rig_label(rig)
        if metres <= RIG_COLLECT_M and now - float(rig.get("at") or 0) >= RIG_COLLECT_AFTER_S:
            return {"text": "COLLECT RIG %s  %s" % (label, _metres(metres)),
                    "colour": CYAN, "kind": "collect"}
        if metres < self.planner_spacing():
            return {"text": "TOO CLOSE TO RIG %s  %s - %s APART" % (
                        label, _metres(metres), _metres(self.planner_spacing())),
                    "colour": RED, "kind": "too_close"}
        return None

    def persist_rigs(self):
        """Write the rigs to disk when they have changed. Never raises."""
        try:
            now = json.dumps(attr(self, "rigs_at", None), sort_keys=True, default=str)
        except (TypeError, ValueError):
            return False
        if now == attr(self, "_rigs_saved", None):
            return False
        if save_rigs(attr(self, "rigs_at", None)):
            self._rigs_saved = now
            return True
        return False

    def rigs_on_vehicle(self, note):
        """A Rhino docking in the ship takes its own rigs off the scope
        (1.10034, a setting). Its rigs only - another Rhino's stay. True if
        any were cleared."""
        settings = attr(self, "settings", None) or {}
        if not settings.get("rigs_clear_on_dock", True) or \
                note.get("event") != "SRVDock" or note.get("player") is False:
            return False
        rigs = self._rigs_here()
        if not rigs:
            return False
        vid = note.get("srv_id")
        gone = [r for r in rigs if vid is None or r.get("srv") in (vid, None)]
        if not gone:
            return False
        if len(gone) == len(rigs):
            self.rigs_up()
        else:
            self.share_rig_layout(
                [r for r in self.rigs_at.get("placed_all") or []
                 if vid is None or r.get("srv") in (vid, None)] or gone)
            keep = [r for r in self.rigs_at["rigs"] if not any(r is g for g in gone)]
            self.rigs_at["rigs"] = keep
            self.refresh_rigs_note()
            self.redraw()
        self.say("Rhino docked - its %d rig(s) taken off the scope. Settings > "
                 "Rigs turns this off." % len(gone), GREEN)
        return True

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
        if trace is None:
            self.restore_plan()
        plan = attr(self, "rig_plan", None)
        if not plan and trace is None:
            try:
                plan = self.shared_plan()
            except Exception:
                plan = None
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
                "shared": bool(plan.get("shared")), "by": plan.get("by", ""),
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
            # Yours, then everybody else's shared finds on this body, then
            # the one you picked: a rig on somebody else's deposit is on
            # their commodity, not on whatever the box last said (1.10034).
            rows = list(self.store.at(system, body))
            book = attr(self, "shared", None)
            if isinstance(book, dict):
                entry = book.get((str(system).lower(), str(body).lower())) or {}
                rows += list(entry.get("rows") or [])
            picked = attr(self, "selected", None)
            if isinstance(picked, dict) and picked not in rows:
                rows.append(picked)
            for row in rows:
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
        # Two Rhinos' rigs down: the first press is the Rhino you are in,
        # a second press inside RIGS_ALL_CONFIRM_S is everything.
        rigs = self._rigs_here()
        rhino = self._rhino_now()
        owners = {r.get("srv") for r in rigs}
        if picked is None and rhino is not None and len(owners) > 1:
            now = time.time()
            again = now - float(attr(self, "_rigs_all_at", 0) or 0) \
                <= RIGS_ALL_CONFIRM_S
            mine = [r for r in rigs if r.get("srv") == rhino]
            if mine and not again:
                self._rigs_all_at = now
                letter = self.rig_label(mine[0])[:1]
                self.rigs_at["rigs"] = [r for r in rigs
                                        if r.get("srv") != rhino]
                self._rigs_warned = False
                self._rigs_final = False
                self.refresh_rigs_note()
                self.redraw()
                rest = len(self.rigs_at["rigs"])
                self.flash("RHINO %s: %d RIG%s UP" % (letter, len(mine),
                                                       "" if len(mine) == 1 else "S"),
                           "%d still down from the other Rhino" % rest)
                return self.say("Rhino %s's %d rig(s) up. %d still down from "
                                "the other Rhino - press %s again within %d s "
                                "to clear those too." % (
                                    letter, len(mine), rest,
                                    self.key("allup", "RIGS UP"),
                                    RIGS_ALL_CONFIRM_S), GREEN)
            self._rigs_all_at = 0
        count = len(self.rigs_at["rigs"]) if self.rigs_at else 0
        if picked is not None:
            count = 1
        # How the deposit was rigged goes to the community map before the
        # rigs are forgotten (#218).
        if self.rigs_at:
            self.share_rig_layout(list(self.rigs_at.get("placed_all")
                                       or self.rigs_at["rigs"]))
        self.rigs_at = None
        self._rigs_warned = False
        self._rigs_final = False
        self.rig_event("RigsUp")
        self.refresh_rigs_note()
        self.redraw()
        if picked is not None:
            self.flash("RIG %s UP" % picked, "all rigs up - warning stood down")
            return self.say("Rig %s up - that was the last. Distance warning "
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
                system, body = self.here()
                if not (system or body):
                    # Nobody has said where we are yet - a fresh start with
                    # the rigs read back off disk. Not a reason to drop them.
                    return None
                self.rigs_at = None
                self._rigs_warned = False
                self._rigs_final = False
                self.clear_rig_alarm()
                self.refresh_rigs_note()
                return None
            self.rigs_after_relog(state, rigs)
            if not (state is not None and state.has_position and state.radius_m):
                return None
            # The distance that counts is from the Rhino that dropped the rig:
            # a second Rhino's rigs go on working while it is parked by
            # them, so only the rigs of the Rhino being driven are watched.
            rhino = self._rhino_now()
            marks = []
            for rig in rigs:
                metres = SV.surface_range_m(state.lat, state.lon, rig["lat"],
                                            rig["lon"], state.radius_m)
                east, north = SV.local_offset(state.lat, state.lon, rig["lat"],
                                              rig["lon"], state.radius_m)
                marks.append({"n": rig["n"], "range_m": metres,
                              "label": self.rig_label(rig),
                              "watched": self._same_rhino(rig, rhino),
                              "rig": rig,
                              "commodity": rig.get("commodity") or "",
                              "east": east, "north": north,
                              "bearing": SV.bearing_deg(state.lat, state.lon,
                                                        rig["lat"], rig["lon"])})
            # Past RIG_LOST_M from the Rhino a rig is destroyed. It is not
            # coming back, so it stops being watched - and a warning about a
            # rig that no longer exists is noise that hides the next real one.
            # Only from the Rhino: from the ship or on foot the distance that
            # counts is the Rhino's, and that is not where Status.json is -
            # and the Nomad sets the same In SRV flag, so it must be a Rhino.
            if getattr(state, "in_rhino", getattr(state, "in_srv", False)):
                lost = [m for m in marks
                        if m["watched"] and m["range_m"] >= RIG_LOST_M]
                if lost:
                    gone = [m["rig"] for m in lost]
                    self.rigs_at["rigs"] = [
                        r for r in self.rigs_at["rigs"]
                        if not any(r is g for g in gone)]
                    marks = [m for m in marks if m not in lost]
                    names = ", ".join(m["label"] for m in lost)
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
            behind = [m for m in marks if m["range_m"] >= RIG_FORGET_M]
            if behind:
                gone = [m["rig"] for m in behind]
                self.rigs_at["rigs"] = [r for r in self.rigs_at["rigs"]
                                        if not any(r is g for g in gone)]
                marks = [m for m in marks if m not in behind]
                self.say("Rig(s) %s forgotten - more than %s behind you. "
                         "Warnings cleared." % (
                             ", ".join(m["label"] for m in behind),
                             _metres(RIG_FORGET_M)), AMBER)
                self._rigs_final = False
                self.clear_rig_alarm()
                self.refresh_rigs_note()
                if not marks:
                    self.rigs_at = None
                    self._rigs_warned = False
                    return None
            for mark in marks:
                mark.pop("rig", None)
            watched = [m for m in marks if m["watched"]]
            # Out of the Rhino - in the ship, on foot - the distance from
            # here is not the Rhino's, so nothing is warned about.
            if hasattr(state, "in_srv") and not getattr(
                    state, "in_rhino", getattr(state, "in_srv", False)):
                watched = []
            if not watched:
                # Only the other Rhino's rigs are down: drawn, never warned.
                self._rigs_final = False
                self.clear_rig_alarm()
                return {"rigs": marks, "count": len(marks), "n": None,
                        "label": "", "range_m": 0.0, "bearing": 0.0,
                        "limit_m": self.rig_limit(), "far": False,
                        "final": False, "offset": 0.0}
            farthest = max(watched, key=lambda m: m["range_m"])
            limit = self.rig_limit()
            far = bool(limit) and farthest["range_m"] > limit
            if far and not attr(self, "_rigs_warned", False):
                self._rigs_warned = True
                self.say("TOO FAR FROM RIG %s - %s back to it, bearing %03d."
                         % (farthest["label"], _metres(farthest["range_m"]),
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
                    self.say("LAST WARNING - RIG %s IS %s AWAY. It is destroyed "
                             "at %s. Turn back: bearing %03d." % (
                                 farthest["label"], _metres(farthest["range_m"]),
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
                    "label": farthest["label"],
                    "range_m": farthest["range_m"],
                    "bearing": farthest["bearing"], "limit_m": limit,
                    "far": far, "final": final,
                    "offset": SV.relative_bearing(state.heading or 0.0,
                                                  farthest["bearing"])}
        except Exception:
            return None

    def rigs_after_relog(self, state, rigs):
        """Rigs marked before the game was logged into again may not have
        survived it - commanders report rigs gone after a disconnect. There
        is no journal event for a rig, so EDSMT cannot know: it says so once
        per game session and leaves the choice, one key away. Never clears
        anything by itself. Returns True when it spoke."""
        started = getattr(state, "game_started", None)
        if not started or not rigs:
            return False
        older = [r for r in rigs if float(r.get("at") or 0) < float(started) - 5]
        if not older or attr(self, "_relog_asked", None) == started:
            return False
        self._relog_asked = started
        names = ", ".join(self.rig_label(r) for r in older)
        self.flash("RIGS FROM BEFORE THE RELOG", "%s - still there? %s clears"
                   % (names, self.key("allup", "RIGS UP")), AMBER)
        self.say("Rig(s) %s were marked before you logged back in. Rigs have "
                 "been reported lost in a disconnect - if they are gone, %s "
                 "clears them; if they are still there, carry on." % (
                     names, self.key("allup", "RIGS UP")), AMBER)
        return True

    def show_rig_alarm(self, farthest, state):
        """The big warning triangle, middle of the screen, over the game."""
        overlay = attr(self, "overlay", None)
        shower = getattr(overlay, "alarm", None)
        if not callable(shower):
            return False
        offset = SV.relative_bearing(getattr(state, "heading", 0.0) or 0.0,
                                     farthest["bearing"])
        try:
            return shower("RIG %s  %s" % (farthest.get("label") or farthest["n"],
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
                rhinos = max(1, len({r.get("srv") for r in rigs}))
                note.configure(text="%d of %d rigs down on %s: %s." % (
                    len(rigs), MAX_RIGS * rhinos, self.rigs_at["body"],
                    ", ".join(("%s %s" % (self.rig_label(r),
                                          r.get("commodity") or "")).strip()
                              for r in rigs)),
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
        # An empty map - one picked up in the ship, out of reach of the
        # survey - is never kept on arrival: it is asked for again, so the
        # map with the centre and border on it is found. Kept, it started
        # painting a new map on top of the old area, and a survey set
        # before a trip to the ship was gone when the Rhino came back down.
        if (cmap is None or cmap.anchor is None
                or cmap.system != system or cmap.body != body
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
        self.wp_track(state, cmap)
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
            view["trail"] = self.trail_view(cmap, rel)
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

    # -- the trail, the lines, golden groups, the rig radar (1.10035) ----

    def trail_view(self, cmap, rel):
        """The driven trail for the map and scope: the coverage map's own
        simplified line, as metres east and north of the commander and
        ending at the commander. [] when it cannot be worked out."""
        try:
            line = [rel(lat, lon) for lat, lon in cmap.trail()]
        except (TypeError, ValueError, IndexError, ZeroDivisionError, OverflowError):
            return []
        if line:
            line.append((0.0, 0.0))
        return line

    def golden_radius(self):
        """How far apart a golden group's deposits may be, in metres: the
        Settings figure, held to 500-2,500."""
        return PV.golden_radius((attr(self, "settings", None) or {}).get(
            "golden_radius_m", PV.GOLDEN_RADIUS_M))

    def last_marked_commodity(self, system=None, body=None):
        """The commodity of the deposit you marked last on this body, or "".
        The map's lines are drawn for it when nothing is being driven to."""
        store = attr(self, "store", None)
        if system is None or body is None:
            system, body = self.here()
        if store is None or not (system and body):
            return ""
        try:
            rows = [r for r in store.at(system, body) if str(r.get("commodity") or "").strip()]
        except (TypeError, ValueError, AttributeError):
            return ""
        if not rows:
            return ""
        return str(max(rows, key=lambda r: str(r.get("recorded") or ""))["commodity"]).strip()

    def map_prefs(self, prices=False):
        """What the map and the scope draw on top of the finds, from
        Settings, with what the lines need to know. The plan view also takes
        the prices; the scope asks the app for those itself."""
        settings = attr(self, "settings", None) or {}
        prefs = {"trail": bool(settings.get("map_trail", True)),
                 "lines": bool(settings.get("map_lines", True)),
                 "golden": bool(settings.get("map_golden", True)),
                 "golden_radius_m": self.golden_radius(),
                 "radar": bool(settings.get("rig_radar", True)),
                 "trail_paint": bool(settings.get("overlay_trail_paint", False)),
                 "target": attr(self, "_guide_to", None) or "",
                 "last": self.last_marked_commodity(),
                 "filter": MF.from_settings(settings)}
        if prices:
            prefs["prices"] = self.market_prices()
        return prefs

    def cycle_scope_zoom(self):
        """The zoom key: the scope goes 1x, 2x, 4x, 1x. Past 1x it follows
        the Rhino instead of the signal, so it is the ground you are about
        to drive that fills it."""
        overlay = attr(self, "overlay", None)
        if overlay is None or not hasattr(overlay, "cycle_zoom"):
            return self.say("The overlay is off - %s turns it on."
                            % self.key("overlay", "Overlay"), AMBER)
        step = overlay.cycle_zoom()
        self.flash("SCOPE %dx" % step, "press again for the next step")
        self.redraw()
        return self.say("Scope zoom %dx. The same key steps it: 1x, 2x, 4x." % step,
                        GREEN)

    def rig_radar(self, state, rigs):
        """`rigs` as watch_rigs gave it, with the rig radar's verdict on
        the spot the next rig would land on under "radar": a ring of the
        spacing round every rig down, and whether one can go here. Only in
        a Rhino, only with rigs down, and only with the radar on."""
        if not isinstance(rigs, dict) or not (attr(self, "settings", None) or {}).get("rig_radar", True):
            return rigs
        try:
            radar = self._rig_radar(state, rigs)
        except Exception as exc:
            self.trouble("Spacing rings", exc)
            return rigs
        return dict(rigs, radar=radar) if radar else rigs

    def _rig_radar(self, state, rigs):
        if state is None or not getattr(state, "has_position", False) or \
                not getattr(state, "radius_m", None):
            return None
        if not getattr(state, "in_rhino", getattr(state, "in_srv", False)):
            return None
        marks = rigs.get("rigs") or []
        if not marks:
            return None
        centres = [(m["east"], m["north"]) for m in marks]
        if self.wing_on():
            for mate in (self.wing_marks() or {}).get("mates") or []:
                centres += [(r["east"], r["north"]) for r in mate.get("rigs") or []]
        # Where the next rig lands: behind the cockpit, as drop_rigs puts it.
        offset, heading = self.rig_offset(), getattr(state, "heading", None)
        if offset and heading is not None:
            behind = math.radians(float(heading) + 180.0)
            spot = (offset * math.sin(behind), offset * math.cos(behind))
        else:
            spot = (0.0, 0.0)
        # The traced edge of a deposit, when one is planned and you are on
        # or close to it: a rig has to land on the deposit.
        polygon = None
        plan = attr(self, "rig_plan", None)
        system, body = self.here()
        if plan and len(plan.get("outline") or []) >= 3 and \
                (str(system).lower(), str(body).lower()) == (plan.get("system"), plan.get("body")):
            outline = [SV.local_offset(state.lat, state.lon, lat, lon, state.radius_m)
                       for lat, lon in plan["outline"]]
            if RP.usable(outline, 0.0, 0.0) or \
                    RP.edge_distance(outline, 0.0, 0.0) <= RADAR_PLAN_REACH_M:
                polygon = outline
        down = len([m for m in marks if m.get("watched", True)])
        return RP.radar(spot, centres, self.planner_spacing(), polygon, down, MAX_RIGS)

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

    def follow_ledger(self, now=None):
        """Keep an open Session earnings window's current session and hold
        lines moving while you mine - every LEDGER_LIVE_S, not only when a
        button is pressed (1.10035). Never raises."""
        ledger = attr(self, "ledger")
        if ledger is None:
            return False
        now = time.time() if now is None else now
        if now - (attr(self, "_ledger_at", 0.0) or 0.0) < LEDGER_LIVE_S:
            return False
        self._ledger_at = now
        try:
            if not ledger.winfo_exists():
                self.ledger = None
                return False
            ledger.live()
            return True
        except Exception:
            self.ledger = None
            return False

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

    # -- Powerplay, and searching what the app remembers (1.10035) --------

    def follow_power(self, now=None):
        """Feed the Powerplay record from the journal reader, keep it on disk
        and keep an open Powerplay window current. Never raises.

        The ledger of mined goods is trimmed to what is aboard only while
        docked with the hold known: trimming against a hold that has not been
        read yet would forget every tonne."""
        book = attr(self, "powerbook")
        watcher = attr(self, "watcher")
        if book is None or watcher is None:
            return False
        now = time.time() if now is None else now
        fed = False
        try:
            for note in watcher.drain_power():
                fed = book.observe(note) or fed
            if getattr(watcher, "docked", False) and \
                    "Ship" in (getattr(watcher, "holds", None) or {}):
                fed = book.trim_to_hold(self.hold_now()) or fed
            if book.dirty and now - float(attr(self, "_power_saved_at", 0) or 0) \
                    >= POWER_SAVE_S:
                self._power_saved_at = now
                book.save()
        except Exception:
            return False
        window = attr(self, "power_window")
        if window is not None:
            try:
                if window.winfo_exists():
                    window.follow()
                else:
                    self.power_window = None
            except Exception:
                self.power_window = None
        return fed

    def system_position(self, system):
        """(x, y, z) of a system by name, or None: the game's own position
        when it is the system we are in, else what the Powerplay record or
        the body book remembered from a journal."""
        name = str(system or "").strip()
        if not name:
            return None
        watcher = attr(self, "watcher")
        if watcher is not None and SV.fold(getattr(watcher, "system", "")) \
                == SV.fold(name):
            here = self.star_position()
            if here is not None:
                return here
        for source in (attr(self, "powerbook"), attr(self, "bodybook")):
            if source is None:
                continue
            try:
                found = source.position(name)
            except Exception:
                found = None
            if found:
                return tuple(found)
        return None

    def sell_rows_for(self, name):
        """Every price this app has for one commodity, judged: Demand 0 is
        dropped, each carries its age, and each gets a distance from here
        where one can be measured. From the server's answers to the hold
        quotes, and every market this commander has read."""
        self.book_market()
        rows = []
        for quote in dict(attr(self, "sell_quotes") or {}).values():
            if SV.fold(quote.get("commodity")) == SV.fold(name):
                rows.extend(quote.get("rows") or [r for r in (
                    quote.get("best"), quote.get("here")) if r])
        book = attr(self, "market_book")
        if book is not None:
            rows.extend(book.rows(name))
        here = self.star_position()
        out = []
        for row in rows:
            row = dict(row)
            if FD.row_distance(row) is None and here is not None:
                far = FD.light_years(here, self.system_position(row.get("system")))
                if far is not None:
                    row["distance_ly"] = round(far, 1)
            out.append(row)
        judged = judge_prices(out)
        trends = attr(self, "trends", None)
        if trends is not None:
            trends.note(judged, name)
            if trends.dirty and time.time() - float(attr(self, "_trends_saved_at", 0) or 0) > 60:
                self._trends_saved_at = time.time()
                trends.save()
        return judged

    def sell_prices_at(self, system, names):
        """{commodity: credits a tonne} that `system` pays: the fresh price if
        there is one, else the stale one."""
        out = {}
        for name in names:
            there = [r for r in self.sell_rows_for(name)
                     if SV.fold(r.get("system")) == SV.fold(system)]
            there.sort(key=lambda r: (r["stale"], -r["sell"]))
            if there:
                out[name] = there[0]["sell"]
        return out

    def power_view(self, sell=None, origin=None):
        """PW.assess for the hold aboard now, or None without a record."""
        book = attr(self, "powerbook")
        if book is None:
            return None
        here = str(getattr(attr(self, "watcher"), "system", "") or "")
        hold = self.hold_now()
        sell = sell or here
        return PW.assess(book, attr(self, "merits"), hold, here, sell,
                         self.sell_prices_at(sell, list(hold)), origin)

    def sell_side(self, by="price", origin=None):
        """Per commodity aboard: the five best payers and the five nearest
        buyers, from the prices already in hand, never Demand 0, each with
        its age and - with a pledge - what selling there does for it."""
        book = attr(self, "powerbook")
        hold = self.hold_now()
        origin = origin or (book.hold_origin(hold) if book is not None else "") \
            or str(getattr(attr(self, "watcher"), "system", "") or "")
        out = []
        for name, tonnes in sorted(hold.items(), key=lambda kv: -kv[1]):
            five = FD.best_five(self.sell_rows_for(name))
            for key in five:
                if book is not None and book.power:
                    five[key] = PW.annotate(book, five[key], origin)
            out.append({"commodity": name, "tonnes": tonnes,
                        "rows": five["nearest" if by == "distance" else "payers"]})
        return out

    def sell_signature(self):
        """Cheap: changes when a price the sell side uses might have."""
        quotes = dict(attr(self, "sell_quotes") or {})
        book = attr(self, "market_book")
        return (tuple(sorted((k, q.get("at", 0)) for k, q in quotes.items())),
                len(getattr(book, "stations", {}) or {}),
                tuple(sorted(self.hold_now().items())))

    def remembered_bodies(self, spec):
        """Every body the body book remembers, as FD.body_row rows, for the
        scope in `spec` (Near here: inside its radius). Never raises."""
        book = attr(self, "bodybook")
        if book is None:
            return []
        here = self.star_position()
        radius = float(spec.get("within_ly") or 0) if spec.get("scope") == "near" else 0
        try:
            found = book.rows(near=here, within_ly=radius) if (here and radius) \
                else book.rows()
        except Exception:
            return []
        return [FD.body_row(r["system"], r["body"], r["facts"], r["signals"],
                            r["mapped"], r["source"], r["pos"], here)
                for r in found]

    def live_signal_counts(self, body):
        """{kind: count} of the signals the scanners reported on a body of
        the system we are in."""
        signals = (getattr(attr(self, "watcher"), "body_signals", None) or {}).get(body)
        return FD.signal_counts(signals)

    def site_bodies(self, sites):
        """{(system, body) folded: FD.body_row} for the bodies of these
        sites - what the scans and the body book know about each."""
        here = self.star_position()
        watcher = attr(self, "watcher")
        book = attr(self, "bodybook")
        live = {}
        if watcher is not None:
            for item in watcher.system_bodies(getattr(watcher, "system", "")):
                live[SV.fold(item["body"])] = item
        out, remembered = {}, {}
        for site in sites:
            system, body = site["system"], site["body"]
            key = (SV.fold(system), SV.fold(body))
            if key in out:
                continue
            where = self.system_position(system)
            facts, signals, mapped = {}, None, False
            item = live.get(key[1]) if key[0] == SV.fold(getattr(
                watcher, "system", "")) else None
            if item is not None:
                facts = dict(item)
                signals = [{"type": k, "count": v} for k, v in
                           self.live_signal_counts(item["body"]).items()]
                mapped = bool(item.get("mapped"))
            elif book is not None:
                if key[0] not in remembered:
                    remembered[key[0]] = {SV.fold(b): v for b, v in
                                          book.bodies(system).items()}
                found = remembered[key[0]].get(key[1])
                if found:
                    facts, signals, mapped = found["facts"], found["signals"], \
                        found["mapped"]
            out[key] = FD.body_row(system, body, facts, signals, mapped, "",
                                   where, here)
        return out

    # -- what the community has measured (1.10036, crowd.py) ------------

    def crowd_figures(self):
        crowd = attr(self, "crowd", None)
        if crowd is None:
            crowd = self.crowd = CR.Crowd()
        return crowd

    def follow_crowd(self, now=None):
        """Every few hours: how long deposits take to come back, and how
        close rigs have gone. Cheap when it is not time."""
        crowd = self.crowd_figures()
        community = attr(self, "community")
        if community is None or not crowd.due(now):
            return False
        crowd.asked_at = time.time() if now is None else now
        asked = community.crowd("regrowth", tag=CR.REGROWTH_TAG)
        community.crowd("rig-spacing", tag=CR.SPACING_TAG)
        return bool(asked)

    def take_crowd(self, tag, ok, message):
        if not ok:
            if tag == CR.REGROWTH_SHARE_TAG:
                self.say("Regrowth report: %s" % message, AMBER)
            return False
        try:
            data = json.loads(message)
        except (TypeError, ValueError):
            return False
        took = self.crowd_figures().take(tag, data)
        if tag == CR.REGROWTH_SHARE_TAG and isinstance(data, dict) and data.get("accepted"):
            self.say("Thanks - the community map now knows that deposit came back "
                     "after %s days." % CR._days(data.get("days")), GREEN)
        return took

    def report_regrown(self, deposit, how, when=None):
        """Tell the community map a worked-out deposit came back. Once per
        deposit and depletion; never raises."""
        try:
            system, body = deposit.get("system"), deposit.get("body")
            message = CR.regrowth_message(deposit, how, when, system, body)
            community = attr(self, "community")
            if message is None or community is None:
                return False
            if not self.crowd_figures().once(message):
                return False
            return bool(community.report_regrowth(self.board_cmdr(), message,
                                                  tag=CR.REGROWTH_SHARE_TAG))
        except Exception:
            return False

    def open_leaderboard(self):
        """One leaderboard window. Asking again brings it to the front."""
        window = attr(self, "board_window")
        try:
            if window is not None and window.winfo_exists():
                window.wm_deiconify()
                window.focus_set()
                window.ask()
                return window
        except Exception:
            pass
        self.board_window = LeaderboardWindow(self)
        return self.board_window

    # -- the community leaderboard (1.10036, board.py) -------------------

    def board_cmdr(self):
        return str(getattr(attr(self, "watcher"), "cmdr", "") or "").strip()

    def board_settings_changed(self):
        """Join or Leave was pressed: tell the server again for whoever plays
        next. Off is told once it is turned off."""
        self._board_sent = {}
        settings = attr(self, "settings", None) or {}
        self._board_tell_off = not settings.get("leaderboard_optin", True)
        self.keep_board()

    def keep_standing(self):
        """Once a tick, and cheap: the commander's Powerplay standing as the
        game reports it (Power, rank, total merits), for the board's
        Powerplay overall view. Sent when it changes, not every tick (1.10038)."""
        community = attr(self, "community")
        settings = attr(self, "settings", None)
        if community is None or not isinstance(settings, dict) \
                or not settings.get("leaderboard_optin", True):
            return False
        report = LB.standing_report(attr(self, "watcher"), self.board_cmdr())
        if not report or report == attr(self, "_standing_sent", None):
            return False
        try:
            if community.report_standing(report, tag=LB_STANDING_TAG):
                self._standing_sent = report
                return True
        except Exception:
            pass
        return False

    def keep_board(self):
        """Once a tick, and cheap: put the commander in the journal on the
        board (once a session), or take them off after the switch went off."""
        community = attr(self, "community")
        settings = attr(self, "settings", None)
        if community is None or not isinstance(settings, dict):
            return False
        try:
            self.keep_standing()
        except Exception:
            pass
        sent = attr(self, "_board_sent", None)
        if sent is None:
            sent = self._board_sent = {}
        cmdr = self.board_cmdr()
        send, on = LB.should_send(settings, cmdr, sent,
                                  bool(attr(self, "_board_tell_off", False)))
        if not send:
            return False
        sent[cmdr.lower()] = on
        try:
            return bool(community.leaderboard_optin(cmdr, on, tag=LB_OPTIN_TAG))
        except Exception:
            return False

    def set_board(self, on):
        """Join or leave, from the leaderboard window."""
        settings = self.settings
        before = dict(settings)
        settings["leaderboard_optin"] = bool(on)
        save_settings(settings)
        if LB.changed(before, settings):
            self.board_settings_changed()
        return True

    def take_board(self, tag, ok, message):
        if tag == LB_OPTIN_TAG:
            data = LB.parse(message) if ok else None
            if data is None:
                # Tried again next session, or at the next change.
                self._board_sent = {}
                if not ok:
                    self.say("Leaderboard: %s" % message, AMBER)
                return
            if data.get("on"):
                self.say("You are on the community leaderboard as %s." % data.get("cmdr"), GREEN)
            else:
                self.say("%s is off the community leaderboard." % data.get("cmdr"), GREEN)
            window = attr(self, "board_window")
            try:
                if window is not None and window.winfo_exists():
                    window.ask()
            except Exception:
                self.board_window = None
            return
        window = attr(self, "board_window")
        try:
            if window is not None and window.winfo_exists():
                window.results(ok, message)
        except Exception:
            self.board_window = None

    def open_powerplay(self):
        """One Powerplay window. Asking again brings it to the front."""
        window = attr(self, "power_window")
        try:
            if window is not None and window.winfo_exists():
                window.wm_deiconify()
                window.focus_set()
                window.follow(force=True)
                return window
        except Exception:
            pass
        self.power_window = PowerplayWindow(self)
        return self.power_window

    # -- bodies remembered (1.10034) ------------------------------------

    def _start_backfill(self):
        """Read every older journal once, in the background. Never raises."""
        if attr(self, "_backfill", None) is not None:
            return False
        watcher = attr(self, "watcher")
        folder = getattr(watcher, "directory", None)
        book = attr(self, "bodybook")
        if not folder or book is None:
            return False

        def progress(done, total):
            self._backfill_progress = (done, total)

        def run():
            try:
                read, filed = BB.backfill(book, folder, stop=self._backfill_stop,
                                          progress=progress)
                self._backfill_progress = ("done", read, filed)
            except Exception:
                self._backfill_progress = ("done", 0, 0)
            # The same older journals, once each, for every sale the game
            # paid Powerplay merits on (1.10035).
            merits = attr(self, "merits")
            if merits is not None:
                try:
                    merits.learn_folder(folder, stop=self._backfill_stop)
                except Exception as exc:
                    self._backfill_fault("merit rate", exc)
            # And what each ship's hold was fitted at (1.10035).
            holds = attr(self, "ship_book", None)
            if holds is not None:
                try:
                    holds.learn_folder(folder, stop=self._backfill_stop)
                except Exception as exc:
                    self._backfill_fault("ship holds", exc)
            # And for the Powerplay record: the pledge, and every system's
            # state, from every journal on disk (1.10035).
            power = attr(self, "powerbook")
            if power is not None:
                try:
                    power.learn_folder(folder, stop=self._backfill_stop)
                except Exception as exc:
                    self._backfill_fault("Powerplay record", exc)

        self._backfill = threading.Thread(target=run, name="EDSMT older journals",
                                          daemon=True)
        self._backfill.start()
        return True

    def _backfill_fault(self, what, exc):
        """One part of the older-journal read failed. It runs on its own
        thread, so nothing goes on screen: it is written to the app's log,
        which the support bundle carries. Never raises."""
        faults = attr(self, "_backfill_faults", None)
        if not isinstance(faults, list):
            faults = self._backfill_faults = []
        faults.append(what)
        log = attr(self, "applog", None)
        if log is not None:
            try:
                log.write("older journals: %s not read (%s: %s)"
                          % (what, type(exc).__name__, exc))
            except Exception:
                pass

    def backfill_note(self):
        """A few words on the older-journal read, while it is going."""
        progress = attr(self, "_backfill_progress", None)
        if not progress or progress[0] == "done":
            return ""
        done, total = progress
        return "reading your older journals for bodies (%d of %d)" % (done, total)

    def follow_bodies(self, now=None):
        """Remember the bodies of the system you are in, and put back what
        is remembered about it. Never raises."""
        book = attr(self, "bodybook")
        watcher = attr(self, "watcher")
        if book is None or watcher is None:
            return
        now = time.time() if now is None else now
        try:
            self._start_backfill()
            system = str(getattr(watcher, "system", "") or "").strip()
            if not system:
                return
            if system != attr(self, "_bodies_for", None) or \
                    book.revision != attr(self, "_bodies_rev", -1):
                BB.seed_watcher(watcher, book, system)
                self._bodies_for = system
                self._bodies_rev = book.revision
            if now - float(attr(self, "_bodies_saved_at", 0) or 0) >= BODY_SAVE_S:
                self._bodies_saved_at = now
                if not isinstance(attr(self, "_bodies_seen", None), dict):
                    self._bodies_seen = {}
                BB.remember_watcher(watcher, book, system, self._bodies_seen)
                self._bodies_rev = book.revision
            self.ask_public_bodies(system, now=now)
        except Exception:
            pass

    def ask_public_bodies(self, system, force=False, now=None):
        """Ask the server for a system's bodies, once a session, when the
        journals here have not described them all. True if asked."""
        watcher = attr(self, "watcher")
        book = attr(self, "bodybook")
        community = attr(self, "community")
        if watcher is None or book is None or community is None or \
                not getattr(community, "can_read", False):
            return False
        now = time.time() if now is None else now
        key = str(system or "").strip().lower()
        asked = attr(self, "_bodies_asked", None)
        if not isinstance(asked, set):
            asked = self._bodies_asked = set()
        if not key or (key in asked and not force):
            return False
        address = getattr(watcher, "system_address", None)
        if not address or key != str(getattr(watcher, "system", "")).strip().lower():
            return False
        info = book.system(system) or {}
        if not force and info.get("public_at") and \
                now - float(info["public_at"]) < PUBLIC_BODIES_DAYS * 86400:
            asked.add(key)
            return False
        known = len(watcher.system_bodies(system))
        counted = (getattr(watcher, "body_counts", {}) or {}).get(key) or \
            info.get("body_count")
        if not force and known and counted and known >= counted:
            asked.add(key)
            return False
        asked.add(key)
        if not isinstance(attr(self, "_bodies_asking", None), dict):
            self._bodies_asking = {}
        self._bodies_asking[int(address)] = system
        return bool(community.bodies(address, system))

    def take_bodies(self, ok, message):
        """The public body database's answer: filed under what the journal
        has said, never over it."""
        if not ok:
            self._land_error = "Could not load this system's bodies: %s" % message
            return self._land_changed()
        try:
            data = json.loads(message)
            address = int(data.get("address") or 0)
            rows = [r for r in (data.get("bodies") or []) if isinstance(r, dict)]
        except (ValueError, TypeError):
            return
        book = attr(self, "bodybook")
        if book is None:
            return
        system = (attr(self, "_bodies_asking", None) or {}).pop(address, None) \
            or str(data.get("system") or "")
        if not system:
            return
        for row in rows:
            facts, signals = BB.public_rows_to_facts(row)
            book.put(system, row.get("body"), facts, signals=signals,
                     source=BB.SOURCE_PUBLIC, commit=False)
        book.commit()
        count = data.get("body_count")
        book.note_system(system, address=address or None,
                         body_count=count if isinstance(count, int) else None,
                         public_at=time.time())
        self._land_changed()

    # -- how deposits are rigged, shared (1.10034, #218) ------------------

    def rig_layout(self, rigs, system=None, body=None, signal=None):
        """The layout to share for these rigs, or None: where each went
        down, what they were on, and the planner's edge and pins when it
        was used on this body."""
        rigs = [r for r in rigs or [] if isinstance(r, dict)
                and r.get("lat") is not None and r.get("lon") is not None]
        if len(rigs) < 2:
            return None
        here_system, here_body = self.here()
        system = system or (self.rigs_at or {}).get("system") or here_system
        body = body or (self.rigs_at or {}).get("body") or here_body
        if not (system and body):
            return None
        what = [str(r.get("commodity") or "") for r in rigs if r.get("commodity")]
        commodity = max(set(what), key=what.count) if what else ""
        layout = {"system": system, "planet": body,
                  "spot": str(signal if signal is not None else self.signal() or "1"),
                  "radius_m": self.layout_radius(),
                  "commodity": commodity,
                  "placed": [[round(float(r["lat"]), 6), round(float(r["lon"]), 6),
                              min(12, int(r.get("n") or i + 1))]
                             for i, r in enumerate(rigs[:12])]}
        plan = attr(self, "rig_plan", None)
        if plan and (str(plan.get("system")).lower(), str(plan.get("body")).lower()) \
                == (str(system).lower(), str(body).lower()):
            outline = list(plan.get("outline") or [])
            step = max(1, -(-len(outline) // LAYOUT_OUTLINE_MAX))
            layout.update(
                spacing=plan.get("spacing"), area_m2=plan.get("area_m2"),
                outline=[[round(lat, 6), round(lon, 6)] for lat, lon in outline[::step]],
                pins=[[round(p["lat"], 6), round(p["lon"], 6)] for p in plan["pins"][:12]])
        return layout

    def layout_radius(self):
        """The body's radius for a shared layout, so the gap between rigs is
        known in metres (#157). None when the game has not said."""
        try:
            radius = float(getattr(attr(self, "game"), "radius_m", 0) or 0)
        except (TypeError, ValueError):
            return None
        return round(radius, 1) if 50_000 <= radius <= 100_000_000 else None

    def share_rig_layout(self, rigs):
        """Send how these rigs were laid out, once. Never raises."""
        try:
            layout = self.rig_layout(rigs)
            community = attr(self, "community")
            if not layout or community is None:
                return False
            mark = json.dumps(sorted(map(tuple, layout["placed"])))
            sent = attr(self, "_layouts_sent", None)
            if not isinstance(sent, set):
                sent = self._layouts_sent = set()
            if mark in sent:
                return False
            sent.add(mark)
            return bool(community.share_layout(
                getattr(attr(self, "watcher"), "cmdr", "") or "", layout))
        except Exception:
            return False

    def follow_layouts(self, now=None):
        """Ask for the shared layouts of the signal you are on, now and
        then. Never raises."""
        try:
            community = attr(self, "community")
            if community is None or not getattr(community, "can_read", False):
                return False
            system, body = self.here()
            signal = str(self.signal() or "")
            if not (system and body and signal):
                return False
            now = time.time() if now is None else now
            key = (str(system).lower(), str(body).lower(), signal)
            asked = attr(self, "_layouts_asked", None)
            if not isinstance(asked, dict):
                asked = self._layouts_asked = {}
            if key in asked and now - asked[key] < LAYOUTS_REFRESH_S:
                return False
            asked[key] = now
            if not isinstance(attr(self, "_layouts_asking", None), list):
                self._layouts_asking = []
            self._layouts_asking.append(key)
            return bool(community.rig_layouts(system, body, signal))
        except Exception:
            return False

    def take_layouts(self, ok, message):
        if not ok:
            return
        try:
            data = json.loads(message)
            rows = [r for r in data.get("layouts") or [] if isinstance(r, dict)]
        except (ValueError, TypeError, AttributeError):
            return
        asking = attr(self, "_layouts_asking", None) or []
        key = asking.pop(0) if asking else None
        if rows:
            first = rows[0]
            key = (str(first.get("system", "")).lower(),
                   str(first.get("planet", "")).lower(), str(first.get("spot", "")))
        if key is None:
            return
        if not isinstance(attr(self, "layouts", None), dict):
            self.layouts = {}
        self.layouts[key] = rows
        self.redraw()

    def shared_plan(self):
        """The best layout shared for the signal you are on, shaped like a
        rig plan so the scope shows its pins - or None. Only when you have
        no plan of your own, and the setting is on."""
        settings = attr(self, "settings", None) or {}
        if not settings.get("show_shared_layouts", True):
            return None
        system, body = self.here()
        key = (str(system).lower(), str(body).lower(), str(self.signal() or ""))
        rows = (attr(self, "layouts", None) or {}).get(key) or []
        if not rows:
            return None
        best = rows[0]
        placed = [p for p in best.get("placed") or [] if len(p) >= 2]
        if len(placed) < 2:
            return None
        return {"system": key[0], "body": key[1], "shared": True,
                "by": str(best.get("uploader") or "") or ANONYMOUS,
                "spacing": float(best.get("spacing") or self.planner_spacing()),
                "pins": [{"n": i + 1, "lat": float(p[0]), "lon": float(p[1])}
                         for i, p in enumerate(placed)],
                "outline": [(float(a), float(b)) for a, b in best.get("outline") or []]}

    # -- your own Discord channel (1.10034) --------------------------------

    def _discord_hook(self, switch):
        settings = attr(self, "settings", None) or {}
        hook = str(settings.get("discord_webhook") or "").strip()
        if not hook or not settings.get(switch, True) or not EDO.discord_hook_ok(hook):
            return ""
        return hook

    def post_discord_find(self, record):
        """A find just marked, to the commander's own channel. Never raises."""
        hook = self._discord_hook("discord_post_finds")
        if not hook or not record:
            return False
        try:
            cmdr = getattr(attr(self, "watcher"), "cmdr", "") or ""
            payload = EDO.discord_find_message(record, cmdr)
            self.worker.submit(EDO.DISCORD_TAG,
                               lambda: json.dumps(EDO.discord_post(hook, payload)))
            return True
        except Exception:
            return False

    def post_discord_sessions(self):
        """Every Rhino session that has ended since the last look, once.
        Sessions already over when EDSMT started are not posted. Never raises."""
        books = attr(self, "earnings")
        if books is None:
            return 0
        try:
            closed = {str(row.get("id")): row for row in books.sessions
                      if str(row.get("closed") or "").strip()}
        except Exception:
            return 0
        posted = attr(self, "_discord_seen", None)
        if posted is None:
            self._discord_seen = set(closed)
            return 0
        fresh = [row for key, row in closed.items() if key not in posted]
        posted.update(closed)
        hook = self._discord_hook("discord_post_sessions")
        sent = 0
        book = attr(self, "post_book", None)
        for row in fresh:
            if not hook or not SV.unpack_counts(row.get("mined") or ""):
                continue
            # One post a session, ever - across a restart too (1.10035). It
            # is edited when the sale comes in; see discord_edits.
            if book is not None and book.has(row.get("id")):
                continue
            try:
                # One summary a session (1.10035), with what it is worth
                # and where, rigs, finds and Cr/hr - not one post a find.
                summary = self.discord_summary(row)
                picture = self.discord_picture(row)
                if picture and summary is not None:
                    summary["image"] = picture[0]
                payload = EDO.discord_session_message(
                    row, row.get("cmdr") or "", summary=summary)
                sid = str(row.get("id"))
                if book is not None:
                    book.sent(sid, self.discord_state(row), picture[0] if picture else "")
                self.worker.submit(
                    EDO.DISCORD_TAG,
                    lambda p=payload, s=sid, pic=picture: self.discord_job(hook, p, s, pic))
                sent += 1
            except Exception:
                continue
        self.discord_edits(hook)
        return sent

    def discord_summary(self, row):
        """What a session's Discord summary carries beyond its row. Never
        raises; None when it cannot be worked out."""
        try:
            est = self.session_estimate(row)
            used, capacity = self.ship_hold()
            lines = []
            for line in est["lines"]:
                where = quote_where(line["row"]) if line["row"] else (
                    "the galactic average" if line["how"] == "average" else "")
                lines.append(dict(line, where=where, row=None))
            return {"lines": lines, "value": est["value"], "earned": est["earned"],
                    "cr_hr": est["cr_hr"], "estimated": bool(est["kinds"]),
                    "hold": (used, capacity),
                    "rigs": sum(part["rigs"] for part in SV.rhino_split(row)),
                    "finds": self.finds_in(row),
                    "worked": self.deposits_worked(row),
                    "merits_hr": est["merits_hr"],
                    "merits_est": (est["merits_hr"] * est["hours"]
                                   if est["merits_hr"] else None),
                    **self.discord_extras(row)}
        except Exception:
            return None

    def discord_extras(self, row):
        """Materials, crew wages and merits the game paid, for a session."""
        ledger = attr(self, "extras", None)
        if ledger is None:
            return {}
        got = ledger.for_session(row.get("id"))
        return {"materials": got["materials"], "wages": got["wages"],
                "merits": got["merits"] or None}

    def take_discord(self, tag, ok, message):
        if ok:
            if tag == EDO.DISCORD_TEST_TAG:
                self.say("Discord took the test message.", GREEN)
            else:
                self.discord_answer(message)
            return
        self.say("Discord did not take it: %s" % message, AMBER)

    def public_body_count(self, system):
        """How many of a system's bodies are known only from the public
        database - Where to land says so."""
        watcher = attr(self, "watcher")
        try:
            return sum(1 for facts in watcher.body_facts.values()
                       if str(facts.get("system") or "").lower() == str(system).lower()
                       and facts.get("source") == BB.SOURCE_PUBLIC)
        except Exception:
            return 0

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
                # When anyone last reported it (1.10038): the zone line says
                # how old what it names is.
                "when": str(item.get("last_seen") or item.get("created") or ""),
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
        if self.refine_ranged(commodity):
            return
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
        if deposit.get("rigs_fit"):
            lines.append("rigs that fit: %s (a Rhino carries %d)"
                         % (deposit["rigs_fit"], MAX_RIGS))
        amount = deposit.get("amount") or ""
        if amount:
            worked = SV.is_depleted(amount)
            lines.append("amount: %s%s" % (amount,
                                           "  - worked out" if worked else ""))
            age = worked_out_age(deposit)
            regrowth = RG.card_lines(deposit)
            if regrowth:
                lines.extend(regrowth)
            elif age:
                lines.append(age)
            said = self.crowd_figures().card_line(deposit)
            if said:
                lines.append(said)
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
        self._regrowth_buttons(deposit)

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

    def rig_for(self, label):
        """The rig behind a map square, by its label ("2", "B3")."""
        for rig in self._rigs_here():
            if self.rig_label(rig) == str(label):
                return rig
        return None

    def edit_rig(self, mark):
        """Double-click a rig's square on the map (1.10034): fix what it is
        mining, or pick it up."""
        rig = self.rig_for((mark or {}).get("label") or (mark or {}).get("n"))
        if rig is None:
            return self.say("That rig is not marked down any more.", AMBER)
        try:
            window = attr(self, "_rig_editor")
            if window is not None and window.winfo_exists():
                window.destroy()
            self._rig_editor = RigEditWindow(self, rig)
        except Exception as exc:
            self.say("Could not open that rig: %s" % exc, RED)

    def set_rig_commodity(self, rig, commodity):
        """A rig's commodity, put right by hand. True if it changed."""
        name = str(commodity or "").strip()
        name = SV.canonical(name) or name
        if not name or rig.get("commodity") == name:
            return False
        for placed in (self.rigs_at or {}).get("placed_all") or []:
            if placed is not rig and placed.get("n") == rig.get("n") \
                    and placed.get("lat") == rig.get("lat") \
                    and placed.get("lon") == rig.get("lon"):
                placed["commodity"] = name
        rig["commodity"] = name
        self.persist_rigs()
        self.refresh_rigs_note()
        self.redraw()
        self.say("Rig %s is on %s." % (self.rig_label(rig), name), GREEN)
        return True

    def pick_up_rig(self, rig):
        """One rig up from its editor. The last one is RIGS UP."""
        rigs = self._rigs_here()
        if not any(r is rig for r in rigs):
            return False
        if len(rigs) == 1:
            self.rigs_up(picked=self.rig_label(rig))
            return True
        self.rigs_at["rigs"] = [r for r in self.rigs_at["rigs"] if r is not rig]
        self.persist_rigs()
        self.refresh_rigs_note()
        self.redraw()
        self.say("Rig %s up." % self.rig_label(rig), GREEN)
        return True

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
        # 1.10035: the first depletion date is kept across looks, and tonnes
        # refined since it was marked make this a new depletion (regrowth.py).
        dates, _kind = RG.mark_changes(self.selected)
        changes["depleted_at"], changes["rechecks"] = dates["depleted_at"], dates["rechecks"]
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
        # Placed from range is a guess at a few hundred metres, not a reading:
        # it goes up when MARK or UPDATE at the spot has put it right.
        if CT.is_ranged(record):
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
            if tag == EDO.BODIES_TAG:
                self.take_bodies(ok, message)
                continue
            if tag in (EDO.DISCORD_TAG, EDO.DISCORD_TEST_TAG):
                self.take_discord(tag, ok, message)
                continue
            if tag == EDO.LAYOUTS_TAG:
                self.take_layouts(ok, message)
                continue
            if tag == EDO.LAYOUT_SHARE_TAG:
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
            if tag in (LB_TAG, LB_OPTIN_TAG):
                self.take_board(tag, ok, message)
                continue
            if tag in (LB_MERITS_TAG, LB_STANDING_TAG):
                # Merits and standing for the board: nothing to show either way.
                continue
            if tag in (CR.REGROWTH_TAG, CR.SPACING_TAG, CR.REGROWTH_SHARE_TAG):
                self.take_crowd(tag, ok, message)
                continue
            if tag == SYSTEM_PRICE_TAG:
                # Only the Earnings window asks, and a window closed while
                # its answer was in flight is no loss.
                ledger = attr(self, "ledger")
                try:
                    if ledger is not None and ledger.winfo_exists():
                        ledger.system_results(ok, message)
                except Exception:
                    self.ledger = None
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
                if shown or tag not in ("verify", "remove"):
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
                     "verify": "Verify", "remove": "Remove"}.get(tag, tag)
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
        # The version names the file on disk: only a version number may.
        if not (package and version and re.fullmatch(r"\d+(?:\.\d+){0,3}", version)):
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
                 "you are ready - EDSMT backs up your finds and settings to "
                 "Documents > EDSMT backups first, then closes, updates and "
                 "opens again by itself."
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
        # Everything on disk first, so the backup holds this evening too.
        self._save_on_exit()
        if not self.backup_before_update(ready.get("version", "")):
            return False
        kind = build_kind()
        try:
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

    def backup_before_update(self, version="", folder=None, now=None):
        """Back up the finds, sessions and settings before an update runs.

        True when it is safe to go on: the backup is written, or there was
        nothing to back up, or the commander pressed INSTALL UPDATE a second
        time after being told the backup could not be made.
        """
        now = time.time() if now is None else now
        failed_at = float(attr(self, "_backup_failed_at", 0) or 0)
        if failed_at and now - failed_at <= UPDATE_NO_BACKUP_S:
            self._backup_failed_at = 0
            self.say("Installing without a backup, as asked.", AMBER)
            return True
        store = attr(self, "store", None)
        if store is None:
            return True
        folder = folder or backups_dir()
        try:
            path, count = store.backup_to(folder)
            if path:
                stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
                named = os.path.join(folder, "%s%s-%s.zip" % (
                    AUTO_BACKUP_PREFIX, str(version or "next").replace(" ", ""), stamp))
                os.replace(path, named)
                tidy_auto_backups(folder)
                self.say("Backed up %d file(s) to %s before updating."
                         % (count, named), GREEN)
            return True
        except Exception as exc:
            self._backup_failed_at = now
            self.say("Could not back up before updating (%s), so the update "
                     "was not started. Press INSTALL UPDATE again within %d s "
                     "to install without a backup." % (exc, UPDATE_NO_BACKUP_S),
                     RED)
            return False

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
        log = attr(self, "applog", None)
        if log is not None:
            log.write(text)

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
        self.say("Your first find is on the community map - thank you.", GREEN)
        return True

    def open_find(self):
        # Open to everybody: every commander's finds go on the map, so every
        # commander reads it. (It used to open only after a find of your own.)
        # As a tab there is one Find; as windows each press opens another.
        docked = self.docked_tools.get("find")
        if docked is not None and docked.winfo_exists():
            self.show_tab(docked)
            return docked
        self.finder = FindWindow(self)
        return self.finder

    def open_earnings(self):
        docked = self.docked_tools.get("earnings")
        if docked is not None and docked.winfo_exists():
            self.show_tab(docked)
            return docked
        self.ledger = EarningsWindow(self)
        return self.ledger

    # -- the tools as tabs (1.10036, #147) --------------------------------

    @property
    def docked_tools(self):
        tools = self.__dict__.get("_docked_tools")
        if tools is None:
            tools = self._docked_tools = {}
        return tools

    def tools_as_tabs(self):
        """Whether a tool opened now goes in a tab of this window."""
        settings = attr(self, "settings", None) or {}
        return bool(settings.get("tools_as_tabs", True)) \
            and attr(self, "tool_area", None) is not None

    def tool_host(self):
        return self.tool_area

    @staticmethod
    def tool_key(tool):
        return TOOL_KEYS.get(type(tool).__name__, type(tool).__name__.lower())

    def dock_tool(self, tool):
        """A tool built as a tab: it takes the place of any older tab of its
        kind, and is shown."""
        key = self.tool_key(tool)
        old = self.docked_tools.get(key)
        self.docked_tools[key] = tool
        if old is not None and old is not tool:
            try:
                old.destroy()
            except Exception:
                pass
        self.show_tab(tool)

    def undock_tool(self, tool):
        key = self.tool_key(tool)
        if self.docked_tools.get(key) is tool:
            del self.docked_tools[key]
            if attr(self, "active_tab", "map") == key:
                self.show_map()

    def show_tab(self, tool):
        """One tab on show, in the map's place; the map and the rest out of
        sight but kept as they were."""
        key = self.tool_key(tool)
        if not getattr(tool, "docked", True):
            # Popped out to a window of its own (1.10038): that window
            # comes forward, and the main window stays as it is.
            try:
                tool.deiconify()
                tool.lift()
            except Exception:
                return False
            return True
        try:
            self.plan.grid_remove()
        except Exception:
            pass
        for other in list(self.docked_tools.values()):
            if other is not tool:
                try:
                    other.grid_remove()
                except Exception:
                    pass
        try:
            tool.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
            # Tk's own raise. The tool's tkraise means "show this tab" and
            # came straight back here, a few hundred times a press, until
            # the recursion limit stopped it (1.10038).
            tk.Misc.tkraise(tool)
        except Exception:
            return False
        # A table wants the width; the rail's controls are for the map.
        rail = attr(self, "rail_frame", None)
        try:
            if rail is not None:
                rail.grid_remove()
                self.tool_area.grid_configure(column=0, columnspan=2)
        except Exception:
            pass
        self.active_tab = key
        self.paint_tabs()
        return True

    def show_map(self):
        for tool in list(self.docked_tools.values()):
            try:
                tool.grid_remove()
            except Exception:
                pass
        try:
            self.plan.grid()
        except Exception:
            pass
        rail = attr(self, "rail_frame", None)
        try:
            if rail is not None:
                self.tool_area.grid_configure(column=1, columnspan=1)
                rail.grid()
        except Exception:
            pass
        self.active_tab = "map"
        self.paint_tabs()
        return True

    def paint_tabs(self):
        """The tab on show lit."""
        buttons = attr(self, "tab_buttons", None) or {}
        active = attr(self, "active_tab", "map")
        for key, button in buttons.items():
            try:
                button.configure(**(BTN_PRIMARY if key == active else BTN_SECONDARY))
            except Exception:
                pass

    # -- 1.10035: sites, the bin, importing, regrowth, the prompts --------

    def site_book(self):
        """Favourites and the bin for this commander's records."""
        book = attr(self, "_site_book", None)
        if book is None:
            book = self._site_book = SBK.SiteBook(self.store.folder)
        return book

    def open_import(self):
        """One import window: asking again replaces it with a fresh one."""
        window = attr(self, "import_window")
        try:
            if window is not None and window.winfo_exists():
                window.destroy()
        except Exception:
            pass
        self.import_window = ImportWindow(self)
        return self.import_window

    def open_map_filter(self):
        """One map filter window: asking again replaces it with a fresh one."""
        window = attr(self, "filter_window")
        try:
            if window is not None and window.winfo_exists():
                window.destroy()
        except Exception:
            pass
        self.filter_window = MapFilterWindow(self)
        return self.filter_window

    def refresh_everything(self):
        """Every view of the records, after something changed them."""
        for name in ("refresh_locations", "refresh_deposits",
                     "refresh_commodities", "redraw"):
            try:
                getattr(self, name)()
            except Exception as exc:
                self.trouble("Refreshing after a change", exc)

    def share_imported(self, records):
        """Send the finds an import added to the community map, a hundred at
        a time, when sharing is on and the link is ready. How many went."""
        community = attr(self, "community")
        if community is None or not getattr(community, "ready", False):
            return 0
        if not self.settings.get("community_auto_share", True):
            return 0
        rows = IMP.community_rows(records)
        sent = 0
        for start in range(0, len(rows), IMPORT_SHARE_BATCH):
            chunk = rows[start:start + IMPORT_SHARE_BATCH]
            try:
                if community.upload(attr(self, "watcher").cmdr, chunk):
                    sent += len(chunk)
            except Exception as exc:
                self.trouble("Sharing imported finds", exc)
                break
        return sent

    def follow_prompts(self, state, now=None):
        """The small things said on a tick: where you have arrived, a tonne
        refined with nothing marked, a depleted deposit you are standing at.
        Each is separate and none of them may stop the tick."""
        now = time.time() if now is None else now
        for step in (self.arrival_check, self.regrowth_check,
                     self.refine_prompt_expire):
            try:
                step(state, now)
            except Exception as exc:
                self.trouble("Prompts", exc)

    def arrival_check(self, state, now=None):
        """On arriving in a system - a jump, or the game's own Location -
        one line: "2 of your sites here, 3 shared", when either is above 0.
        The shared sites are asked for on arrival; the line waits a few
        seconds for the answer and is said without it after that."""
        system = str(getattr(state, "system", "") or "").strip()
        if not system:
            return False
        now = time.time() if now is None else now
        key = system.lower()
        if key != attr(self, "_arrived_in", None):
            self._arrived_in = key
            self._arrival = {"system": system, "at": now}
            try:
                self.want_landing(system)
            except Exception as exc:
                self.trouble("Asking for this system's shared sites", exc)
            try:
                if RG.expire_marks(self.store, now):
                    self.refresh_everything()
            except Exception as exc:
                self.trouble("Taking off depleted marks", exc)
        pending = attr(self, "_arrival", None)
        if not isinstance(pending, dict):
            return False
        sites = attr(self, "land_sites", None)
        have = sites.get(key) if isinstance(sites, dict) else None
        community = attr(self, "community")
        asking = community is not None and getattr(community, "can_read", False)
        answered = have is not None and (have["at"] >= pending["at"]
                                         or now - have["at"] < SHARED_REFRESH_S)
        if asking and not answered and now - pending["at"] < ARRIVAL_WAIT_S:
            return False
        self._arrival = None
        mine, shared = SBK.arrival_counts(
            self.store, system, (have or {}).get("rows") or [])
        line = SBK.arrival_line(mine, shared)
        if not line:
            return False
        self.say(line, GREEN)
        self.flash(line, "", GREEN)
        return True

    def regrowth_check(self, state, now=None):
        """Standing at a depleted deposit that is due a look: say so, once."""
        if not (state and getattr(state, "has_position", False)):
            return False
        system, body = self.here()
        if not (system and body):
            return False
        told = attr(self, "_look_told", None)
        if not isinstance(told, set):
            told = self._look_told = set()
        for row, _metres in RG.due_near(self.store, system, body, state.lat,
                                        state.lon, state.radius_m, now):
            if row["id"] in told:
                continue
            told.add(row["id"])
            info = RG.standing(row, now)
            self.say("%s here: %s. Click it on the map: CONFIRM DEPLETED if it "
                     "is, REGROWN if it has grown back."
                     % (row.get("commodity") or "A deposit", info["text"]), AMBER)
            self.flash("%s: %s" % (str(row.get("commodity") or "DEPOSIT").upper()[:18],
                                   info["text"]), "", AMBER)
            return True
        return False

    def refine_check(self, note):
        """A tonne refined in the Rhino with nothing marked there: one line
        and a button to mark it. Once for each place and commodity."""
        spots = attr(self, "_refine_spots", None)
        if not isinstance(spots, list):
            spots = self._refine_spots = []
        note = dict(note)
        if not (note.get("system") and note.get("body")):
            note["system"], note["body"] = self.here()
        found = SBK.unmarked_refine(self.store, note, SAME_DEPOSIT_M, spots)
        if not found:
            return False
        found["at"] = time.time()
        self._refine_prompt = found
        line = SBK.refine_line(found["commodity"], self.key("deposit", "MARK"))
        self.say(line, AMBER)
        self.flash("REFINED %s - NOTHING MARKED" % found["commodity"].upper()[:18],
                   "mark it? %s" % self.key("deposit", "MARK"), AMBER)
        try:
            self.refine_button.pack(side="left", padx=(6, 0))
        except Exception:
            pass
        return True

    def clear_refine_prompt(self):
        self._refine_prompt = None
        try:
            self.refine_button.pack_forget()
        except Exception:
            pass

    def refine_prompt_expire(self, state=None, now=None):
        prompt = attr(self, "_refine_prompt", None)
        if isinstance(prompt, dict) and (time.time() if now is None else now) \
                - prompt["at"] > REFINE_PROMPT_S:
            self.clear_refine_prompt()
            return True
        return False

    def mark_refined_here(self):
        """The prompt's button: put the commodity just refined in the box and
        mark a deposit where you are standing, by the usual rules."""
        prompt = attr(self, "_refine_prompt", None)
        self.clear_refine_prompt()
        if not isinstance(prompt, dict):
            return self.say("Nothing to mark.", AMBER)
        try:
            self.fields["commodity"].set(prompt["commodity"])
        except Exception:
            pass
        return self.mark_deposit()

    def _regrowth_buttons(self, deposit):
        """CONFIRM DEPLETED on a deposit that is due a recheck, REGROWN on any
        that is marked depleted."""
        info = RG.standing(deposit)
        for button, show in ((attr(self, "btn_still"), info["due"]),
                             (attr(self, "btn_active"), RG.depleted(deposit))):
            if button is None:
                continue
            try:
                button.pack_forget()
                if show:
                    button.pack(fill="x", pady=2, before=self.btn_delete)
            except Exception:
                pass

    def still_depleted(self):
        """You looked and it is still empty: the first date stays, the look
        is kept, and the mark comes off a week after it."""
        chosen = attr(self, "selected")
        if not chosen:
            return self.say("Pick a deposit first.", AMBER)
        changes, kind = RG.still_depleted_changes(chosen)
        if kind != "recheck":
            return self.say("That one is not due a look yet.", AMBER)
        row = self.store.update_deposit(chosen["id"], **changes)
        if row is None:
            return self.say("That deposit is no longer there.", AMBER)
        self.selected = row
        self.refresh_deposits()
        self.redraw()
        self.on_pick(row)
        return self.say("%s: %s." % (row.get("commodity") or "Deposit",
                                     RG.standing(row)["text"]), GREEN)

    def set_active(self):
        """It has grown back: the depleted mark off, the amount unread."""
        chosen = attr(self, "selected")
        if not chosen:
            return self.say("Pick a deposit first.", AMBER)
        if not RG.depleted(chosen):
            return self.say("That deposit is not marked depleted.", AMBER)
        self.report_regrown(chosen, "seen")
        row = self.deposit_edited(chosen["id"], RG.set_active_changes(chosen))
        if row is not None:
            self.say("%s is active again. Its amount is unread - read it on "
                     "the deposit and Edit it." % (row.get("commodity") or "Deposit"),
                     GREEN)
        return row

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
        before = attr(self, "settings", None) or {}
        for key in ALWAYS_SHARED:
            data[key] = True
        self.settings = data
        save_settings(data)
        if LB.changed(before, data):
            self.board_settings_changed()
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
        if self.overlay_wanted_now():
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
            self.persist_rigs()
        except Exception:
            pass
        try:
            self._backfill_stop.set()
            BB.remember_watcher(self.watcher, self.bodybook,
                                str(getattr(self.watcher, "system", "") or ""),
                                self._bodies_seen)
        except Exception:
            pass
        try:
            self.save_refined(force=True)
        except Exception:
            pass
        try:
            # Materials, wages and merits seen in the last few seconds.
            self.extras.save(force=True)
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

# ---------------------------------------------------------------------------
# A word on every control (1.10034, #166)
# ---------------------------------------------------------------------------
# "Tell everyone on the first load what each thing does." Rest the mouse on
# any control and it says what it is for. Plain Tk underneath: a small
# window with no frame, shown after TIP_DELAY_MS and gone the moment the
# mouse moves off or clicks. Settings > Basic turns them off.

TIP_DELAY_MS = 600
TIP_WIDTH = 360

# The main window, by name.
TIPS = {
    "find": "Search every commander's shared finds: deposits, sites, what "
            "is still there, and the best places to sell. Tick several "
            "commodities at once.",
    "map": "The deposit map - back from any tab.",
    "sites": "Every signal and deposit you have logged, on every body - "
             "with tonnes mined and when you were last there.",
    "land": "The bodies in the system you are in, ranked by what they are "
            "likely to hold, with shared sites and what you have swept.",
    "earnings": "Your Rhino sessions: what you dug, sold and earned, per "
                "hour. Also the last known prices in any system.",
    "powerplay": "Whether selling what is aboard would Expand, Reinforce or "
                 "Undermine for your Power or earn nothing - will it count, "
                 "and the best five places to sell.",
    "leaderboard": "The community leaderboard: this week since the Powerplay "
                   "tick, this month, last month and all time. Points for finds, "
                   "first finds on a body, confirmed sites, worked-out reports and "
                   "rig layouts, and the Powerplay merits your mining earned. "
                   "Leave takes you off.",
    "overlay": "The boxes over the game - compass, scope, targets, status, "
               "deposit card and guide. Alt+0 does the same from the game.",
    "lock": "Unlock to drag and resize the overlay boxes; lock again and "
            "clicks go through them to the game.",
    "settings": "Keys, overlay, rigs, sharing, Discord, Inara, backups and "
                "the rest.",
    "update": "A newer EDSMT is ready. Your finds and settings are backed up "
              "first, then it installs.",
    "signal": "The mining location signal you are working. Logging one "
              "sets it; pick another to look at it.",
    "best_patch": "Points the map at the richest group of deposits you can "
                  "rig from one place.",
    "worked_out": "Tell everyone the selected site is stripped, so nobody "
                  "drives out to an empty patch.",
    "move_centre": "Moves the survey centre to where you are now, without "
                   "logging the signal again.",
    "clear_survey": "Forgets the centre, border and swept ground of this "
                    "signal.",
    "commodity": "What the deposit is. Type to narrow the list; the "
                 "scanner fills it in when the game names it.",
    "rigs": "How many rigs fit on the deposit. Can wait until you are "
            "there.",
    "amount": "How much is left - it drops as the deposit is worked.",
    "density": "How rich the deposit is.",
    "mark": "Records a new deposit where you are standing. Needs the "
            "commodity, rigs, amount and density.",
    "range_mark": "Marks a deposit you can see but are not at: a bearing "
                  "and a distance from the Rhino, with the boxes on the "
                  "left. MARK or UPDATE at the spot later puts it exactly "
                  "where it is.",
    "update_deposit": "Writes what the boxes say onto the deposit you are "
                      "standing on - the Amount going down as you work it.",
    "pad_signal": "Logs the signal and sets the survey centre where you "
                  "are. The key is on the button.",
    "pad_border": "Sets the survey border here - drive to the edge first.",
    "pad_rigs": "Marks the next rig down where the Rhino is. The rig keys "
                "mark each rig by number.",
    "pad_allup": "Every rig up: stops the distance warnings.",
    "mined_out": "Marks the selected deposit as worked out.",
    "edit": "Change the selected deposit - commodity, rigs, amount, "
            "density, notes. Double-clicking it on the map does the same.",
    "copy_share": "Copies the selected find as one line you can paste into "
                  "Discord, or into another EDSMT.",
    "delete": "Deletes the selected deposit. Press twice.",
}

# Every Settings row, by the key it saves.
SETTING_TIPS = {
    "chat_tags": "Reads the messages you send in the game's chat and runs the "
                 "ones that start with the prefix below. Off by default: "
                 "local chat is public, so everyone near you reads what you "
                 "type.",
    "chat_prefix": "What a chat command starts with: !rr alexandrite h/m 4, "
                   "!rr 135 1.2km alexandrite, !rr rig down 3, !rr undo. 2 to "
                   "12 characters, no spaces.",
    "long_press_rig": "While you are in the Rhino with the game in front, your "
                      "fire button held for two seconds counts as a rig "
                      "placed, as the rig-down key does. A click never does. "
                      "Nothing about a press is saved.",
    "long_press_button": "Primary or Secondary fire, as you bound it for the "
                         "SRV in the game's Controls - mouse, key or joystick.",
    "app_theme": "The colours of this window. A new theme shows after a restart.",
    "overlay_theme": "The colours of the boxes over the game.",
    "overlay_preset": "A layout for the boxes: Standard, Map focus, Minimal or Streamer.",
    "overlay_swept": "How strongly ground you have scanned is shaded on the scope.",
    "overlay_centre": "What the scope is centred on: the signal you are working, or the Rhino.",
    "overlay_frame": "Whether each box has a frame drawn round it.",
    "overlay_mode": "The shape used when no box is switched on.",
    "overlay_enabled": "The boxes over the game, on or off. Alt+0 from the game.",
    "overlay_rhino_only": "Only show the boxes while you are driving a Rhino.",
    "overlay_only_over_game": "Hide the boxes when the game is not the window in front.",
    "overlay_click_through": "Clicks go through the boxes to the game while they are locked.",
    "overlay_flash": "A few words over the game when a key does something - RIG 2 DOWN.",
    "overlay_show_strip": "The compass tape across the top.",
    "overlay_show_radar": "The scope: deposits, rigs and swept ground around you.",
    "overlay_show_targets": "The nearest deposits, with range and turn.",
    "overlay_show_status": "Where you are, the holds, and warnings.",
    "overlay_show_deposit": "The card for the deposit you are at.",
    "overlay_show_guide": "The step-by-step guide. It turns itself off after your first full run.",
    "overlay_opacity": "How see-through the boxes are, 0.2 to 1.",
    "overlay_width": "Width of the old single overlay, in pixels. Blank fits your screen.",
    "overlay_height": "Height of the old single overlay, in pixels. Blank fits your screen.",
    "overlay_span_deg": "How many degrees of compass the tape shows.",
    "overlay_targets": "How many nearest deposits TARGETS lists.",
    "community_share_cmdr_name": "Every find goes up with your CMDR name on it.",
    "tools_as_tabs": "Find, My sites, Where to land, Earnings, Powerplay and Leaderboard open as tabs in this window. Off: each opens in a window of its own. Pop out, at the right of any tab's header, moves just that one out to a window, and Dock brings it back.",
    "leaderboard_optin": "Your CMDR name and points on the community leaderboard. Leave in the Leaderboard window takes them off.",
    "show_shared_finds": "Other commanders' finds on your map, scope and compass.",
    "verify_my_finds": "With a staff token: your finds go up already verified.",
    "community_token": "Only if Radio Raxxla gave you one. Most people leave it blank.",
    "inara_enabled": "Send where you are to Inara as you play.",
    "inara_api_key": "Your Inara API key, from your Inara account settings.",
    "inara_is_being_developed": "Marks your Inara events as test data.",
    "discord_webhook": "The webhook of a channel of yours. It is a password for that channel.",
    "discord_post_finds": "Off: finds are counted in the session summary. On: each find is posted as well, one message each.",
    "discord_post_sessions": "One summary when a Rhino session ends: time, tonnes, t/hr, what it is worth and where, rigs, finds, deposits worked, Cr/hr.",
    "map_picture_auto": "Save a picture of the map to the pictures folder each time the Rhino docks.",
    "discord_attach_map": "Send that picture with the Discord summary.",
    "discord_edit_after_sale": "When the cargo is sold, update the same Discord message with the sale, the crew's wages and the merits. Never a second post.",
    "journal_dir": "Where the game writes its journal. Blank finds it.",
    "rig_warn_m": "Warn this far from a rig. The game destroys a rig at 5 km. 0 is off.",
    "rig_warn_sound": "Sound the rig warning as well as showing it.",
    "rig_sound_profane": "The rude version of the rig warning.",
    "rig_offset_m": "How far behind the cockpit a rig lands. 7 m is the measured figure.",
    "rigs_clear_on_dock": "When a Rhino docks in the ship, its rigs come off the scope.",
    "show_shared_layouts": "With no plan of your own, the best layout other commanders used on this deposit shows as pins. Yours is shared when your rigs come up.",
    "rig_spacing_m": "How far apart rigs have to be. 78 m is the community's figure.",
    "rig_radar": "A band round each rig, 76 to 80 m at the usual spacing: red while you are in it or inside it, green once clear. And NEXT RIG: how far to the nearest spot a rig can go.",
    "map_trail": "A thin line along where the Rhino has driven, on the map and the scope.",
    "survey_guide": "Numbered waypoints over the survey area, one at a time, on the compass, the scope and the map. Reaching one moves on to the next.",
    "waypoint_radius_m": "How close counts as having reached a waypoint, 50 to 1,000 m. 250 is the usual.",
    "rhino_pointer": "On foot or in the ship near the ground: where the Rhino was left. In the Rhino: where the ship came down.",
    "orbit_guide": "In the ship on the way down: how far, and which way, to the deposit you are driving to, or the signal.",
    "overlay_trail_paint": "Shade the ground the scanner has covered along the trail on the scope even before a border is set. Off keeps the scope clear.",
    "map_lines": "From you to the nearest deposit of the commodity in hand (solid) and to the next cheaper one in view (dotted), with the distance.",
    "map_golden": "Circle the three best patches of intact deposits, with the rigs and Cr/h of each.",
    "golden_radius_m": "How far apart a top patch's deposits may be, 500 to 2,500 m. 1,250 is the usual.",
    "trash_days": "How many days a site you remove from My sites waits in the bin before it is deleted for good. 30 is the usual.",
    "wing_link": "Beta: see your wing's Rhinos and rigs on your scope.",
    "wing_code": "Six letters and digits. Everyone in the wing types the same one.",
    "freshness_half_life_days": "How fast an old report counts for less when ranking finds.",
    "high_g_warn": "Warn above this gravity, in g. 0 is off.",
    "jump_range_ly": "Light years a jump, for selling within 1, 2, 4 or 8 jumps. Blank or 0 uses your ship's own range from the game.",
    "auto_download_updates": "Fetch a new version in the background; it installs only when you press the button.",
    "show_tips": "These notes, when the mouse rests on a control.",
}
BINDING_TIP = ("Click, then press the key you want - like binding a key in "
               "the game. Reset puts the default back.")


def tips_on():
    """Whether tooltips are wanted, from the running app's settings."""
    app = getattr(tk, "_default_root", None)
    settings = getattr(app, "settings", None)
    return not isinstance(settings, dict) or bool(settings.get("show_tips", True))


class Tooltip:
    """What a control is for, once the mouse rests on it. Never raises.

    `always`: the words are the table's own content - a "Why" cell's whole
    sentence (1.10038) - not a note on a control, so they show with tips
    switched off too."""

    def __init__(self, widget, text, always=False):
        self.widget, self.text = widget, str(text or "")
        self.always = bool(always)
        self._after = None
        self._win = None
        for sequence, handler in (("<Enter>", self._enter), ("<Leave>", self._leave),
                                  ("<ButtonPress>", self._leave)):
            try:
                widget.bind(sequence, handler, add="+")
            except Exception:
                pass

    def _enter(self, _event=None):
        self._cancel()
        try:
            self._after = self.widget.after(TIP_DELAY_MS, self._show)
        except Exception:
            self._after = None

    def _leave(self, _event=None):
        self._cancel()
        self._hide()

    def _cancel(self):
        if self._after is not None:
            try:
                self.widget.after_cancel(self._after)
            except Exception:
                pass
            self._after = None

    def _show(self):
        self._after = None
        if not self.text or not (self.always or tips_on()) or self._win is not None:
            return
        try:
            win = tk.Toplevel(self.widget)
            win.wm_overrideredirect(True)
            try:
                win.attributes("-topmost", True)
            except Exception:
                pass
            tk.Label(win, text=self.text, justify="left", wraplength=TIP_WIDTH,
                     bg=PANEL, fg=TEXT, font=F_SMALL, bd=1, relief="solid",
                     padx=8, pady=5).pack()
            win.update_idletasks()
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
            right = self.widget.winfo_screenwidth() - win.winfo_reqwidth() - 8
            bottom = self.widget.winfo_screenheight() - win.winfo_reqheight() - 8
            if y > bottom:
                y = self.widget.winfo_rooty() - win.winfo_reqheight() - 6
            win.geometry("+%d+%d" % (max(0, min(x, right)), max(0, y)))
            self._win = win
        except Exception:
            self._win = None

    def _hide(self):
        if self._win is not None:
            try:
                self._win.destroy()
            except Exception:
                pass
            self._win = None


def tip(widget, text, always=False):
    """Give a control its tooltip; hands the control back, so it can be
    packed in the same breath. A blank text adds nothing."""
    if text:
        note = Tooltip(widget, text, always)
        try:
            widget._edsmt_tip = str(text)
            widget._edsmt_tooltip = note
        except Exception:
            pass
    return widget


# ---------------------------------------------------------------------------
# The first-run tour (1.10034, #166)
# ---------------------------------------------------------------------------
# One small window that walks round the main window, lighting up each part
# in turn and saying what it is for. Once, on the first start of 1.10034 or
# later; Settings > Basic runs it again. Back, Next, and Skip - Esc skips.

# (what to light up - an attribute of the app or None - title, what it is)
TOUR_STEPS = (
    (None, "Welcome to EDSMT",
     "A minute's tour of the window. Rest the mouse on anything later for a "
     "note on what it does. Esc skips the tour."),
    ("t_where", "Where you are",
     "System, body and position, read from the game as you play. You never "
     "type a coordinate."),
    ("location_box", "The signal you are working",
     "Each mining location signal is numbered. Logging one sets it here; "
     "pick another to look at it."),
    (("pad", "signal"), "The keys, in the order you work",
     "Log the signal at the middle (Alt+1), set the border at the edge "
     "(Alt+2), then rigs down and up. Each button shows its key."),
    (("fields", "commodity"), "What the deposit is",
     "Commodity, rigs, amount and density. The scanner fills in what the "
     "game names; all four are needed to mark one."),
    ("btn_mark", "Mark the deposit",
     "Records it where you are standing (Alt+3), and puts it on the "
     "community map. UPDATE beside it writes a dropping Amount."),
    ("plan", "Your map",
     "Your deposits, rigs, the survey border and the ground you have swept. "
     "Click one to select it; double-click to edit it."),
    ("btn_overlay", "The overlay",
     "Compass, scope, targets, status and the deposit card over the game. "
     "Alt+0 from the game; Unlock beside it to arrange the boxes."),
    ("tour_find", "Find, My sites, Where to land, Earnings",
     "Everyone's finds; everything you have logged; the best body in this "
     "system; and what your Rhino sessions earned."),
    ("tour_settings", "Settings",
     "Keys, overlay, rigs, Discord, Inara and backups. Your settings are "
     "kept in dated copies - Settings puts any of them back."),
    (None, "That is it",
     "Fly safe, Commander. The tour is in Settings whenever you want it "
     "again."),
)


def tour_target(app, spec):
    """The widget a tour step lights up, or None."""
    if spec is None:
        return None
    try:
        if isinstance(spec, tuple):
            holder = getattr(app, spec[0], None) or {}
            return holder.get(spec[1]) if isinstance(holder, dict) else None
        found = getattr(app, spec, None)
        # The map is a plan view object; its canvas is the thing on screen.
        return getattr(found, "canvas", None) or getattr(found, "widget", None) \
            if found is not None and not hasattr(found, "winfo_exists") else found
    except Exception:
        return None


class TourWindow(ctk.CTkToplevel):
    """The first-run tour. Never takes the app down with it."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.at = 0
        self._lit = None
        self.title("EDSMT - Tour")
        self.configure(fg_color=PANEL)
        self.resizable(False, False)
        self.transient(app)
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass
        self.counter = ctk.CTkLabel(self, text="", font=F_SMALL, text_color=DIM,
                                    anchor="w")
        self.counter.pack(fill="x", padx=16, pady=(12, 0))
        self.heading = ctk.CTkLabel(self, text="", font=F_HEAD, text_color=ORANGE,
                                    anchor="w", justify="left")
        self.heading.pack(fill="x", padx=16, pady=(2, 4))
        self.words = ctk.CTkLabel(self, text="", font=F_BODY, text_color=TEXT,
                                  anchor="w", justify="left", wraplength=360)
        self.words.pack(fill="x", padx=16, pady=(0, 10))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 14))
        self.skip_button = tip(ctk.CTkButton(row, text="Skip tour", width=96, height=30,
                                         font=F_STRONG, **BTN_GHOST,
                                         command=self.finish), "Close the tour. Settings runs it again.")
        self.skip_button.pack(side="left")
        self.next_button = tip(ctk.CTkButton(row, text="Next", width=96, height=30,
                                         font=F_STRONG, **BTN_PRIMARY,
                                         command=self.forward), "The next step. The right arrow key does the same.")
        self.next_button.pack(side="right")
        self.back_button = tip(ctk.CTkButton(row, text="Back", width=80, height=30,
                                         font=F_STRONG, **BTN_SECONDARY,
                                         command=self.backward), "The step before. The left arrow key does the same.")
        self.back_button.pack(side="right", padx=8)
        self.bind("<Escape>", lambda _e: self.finish())
        self.bind("<Right>", lambda _e: self.forward())
        self.bind("<Left>", lambda _e: self.backward())
        self.protocol("WM_DELETE_WINDOW", self.finish)
        self.show()

    def show(self):
        target, title, text = TOUR_STEPS[self.at]
        self.counter.configure(text="%d of %d" % (self.at + 1, len(TOUR_STEPS)))
        self.heading.configure(text=title)
        self.words.configure(text=text)
        last = self.at == len(TOUR_STEPS) - 1
        self.next_button.configure(text="Done" if last else "Next")
        self.back_button.configure(state="disabled" if self.at == 0 else "normal")
        self.light(tour_target(self.app, target))
        self.place_near(tour_target(self.app, target))

    def light(self, widget):
        """Ring the step's control in the instrument colour; put the last
        one back as it was."""
        self.unlight()
        if widget is None:
            return
        # A button or a box takes a ring; a plain Tk canvas (the map) takes
        # a highlight; a label takes the colour.
        for change in ({"border_width": 3, "border_color": ORANGE},
                       {"highlightthickness": 3, "highlightbackground": ORANGE},
                       {"text_color": ORANGE}):
            try:
                before = {key: widget.cget(key) for key in change}
                widget.configure(**change)
                self._lit = (widget, before)
                return
            except Exception:
                continue
        self._lit = None

    def unlight(self):
        if self._lit is not None:
            widget, before = self._lit
            try:
                widget.configure(**before)
            except Exception:
                pass
            self._lit = None

    def place_near(self, widget):
        """Beside the control when there is room, under it when not, and
        always on the screen."""
        try:
            self.update_idletasks()
            w, h = self.winfo_reqwidth(), self.winfo_reqheight()
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            if widget is None:
                x = self.app.winfo_rootx() + (self.app.winfo_width() - w) // 2
                y = self.app.winfo_rooty() + (self.app.winfo_height() - h) // 3
            else:
                x = widget.winfo_rootx() + widget.winfo_width() + 16
                y = widget.winfo_rooty()
                if x + w > sw:
                    x = widget.winfo_rootx()
                    y = widget.winfo_rooty() + widget.winfo_height() + 12
            x = max(0, min(int(x), sw - w - 8))
            y = max(0, min(int(y), sh - h - 48))
            self.geometry("+%d+%d" % (x, y))
        except Exception:
            pass

    def forward(self):
        if self.at >= len(TOUR_STEPS) - 1:
            return self.finish()
        self.at += 1
        self.show()

    def backward(self):
        if self.at > 0:
            self.at -= 1
            self.show()

    def finish(self):
        self.unlight()
        try:
            self.app.tour_finished()
        finally:
            try:
                self.destroy()
            except Exception:
                pass


# Settings' tabs, in the order they are read (#142).
SETTINGS_TABS = ("Basics", "Theme", "Overlay", "Keys", "Rigs", "Sharing", "Your data", "About")
# The colours a theme picker's swatch row shows, in order (1.10039).
SWATCH_KEYS = ("ORANGE", "AMBER", "TEXT", "MUTED", "GREEN", "RED", "CYAN")


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
        self.joy_binders, self.joy_bindings = {}, {}
        self._joy_capturing = None
        self._joy_after = None
        self._joy_escape = None
        self._joy_ticks = 0
        self.choices = {}
        self.colours = {}
        self._capturing = None
        self._capture_id = None
        # In tabs (1.10034, #142: a tester did not know Settings scrolls).
        # Each tab scrolls on its own; Save and Close are under all of them.
        self.tabs = ctk.CTkTabview(
            self, fg_color=VOID, border_width=0, corner_radius=0,
            segmented_button_fg_color=PANEL,
            segmented_button_selected_color=ORANGE,
            segmented_button_selected_hover_color=AMBER,
            segmented_button_unselected_color=STEEL,
            segmented_button_unselected_hover_color=RULE, text_color=TEXT)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=(6, 4))
        self.pages = {}
        for name in SETTINGS_TABS:
            page = ctk.CTkScrollableFrame(self.tabs.add(name), **LIST)
            page.pack(fill="both", expand=True)
            self.pages[name] = page
        body = self.pages[SETTINGS_TABS[0]]

        # The few things everybody sets, first. Each one lives only here -
        # a setting in two places saves whichever copy was built last.
        body = self.pages["Basics"]
        self._section(body, "Basic settings",
                      "Good defaults throughout; all of it can be changed at "
                      "any time and Save keeps it. Colours are on the Theme "
                      "tab, the keys and the overlay boxes on theirs.")
        # First on the page (1.10038): the one setting people asked for and
        # could not find. Pop out, on any tab, moves one tool for now.
        self._switch(body, "tools_as_tabs",
                     "Open Find, Earnings and the other tools as tabs "
                     "(off: each in its own window)")
        self._switch(body, "overlay_enabled", "Show the overlay while I play")
        self._switch(body, "overlay_rhino_only",
                     "Only while I am driving a Rhino")
        self._switch(body, "overlay_show_guide",
                     "Show the step-by-step guide over the game")
        self._switch(body, "rig_sound_profane",
                     "Use the profane rig warning (strong language)")
        self._entry(body, "high_g_warn",
                    "Big warning on bodies from this gravity (g)", "2.0")
        self._entry(body, "jump_range_ly",
                    "Jump range for selling within N jumps (Ly)",
                    "blank = my ship's")
        self._switch(body, "show_tips",
                     "A note on what each control does, when the mouse rests on it")
        tour_row = ctk.CTkFrame(body, fg_color="transparent")
        tour_row.pack(fill="x", padx=10, pady=(2, 4))
        tip(ctk.CTkButton(tour_row, text="Show me round again", width=200,
                          height=30, font=F_STRONG, **BTN_SECONDARY,
                          command=lambda: self.app.start_tour(force=True)),
            "The first-run tour of the main window.").pack(side="left")

        # 1.10039 (#287): a tab of its own for the colours, second from the
        # left so it is seen. Both pickers, a swatch row under each, the
        # game match in big letters, and the Powers under their own heading.
        body = self.pages["Theme"]
        self._section(body, "Theme",
                      "One look for the main window and the boxes over the "
                      "game. The app theme is worn from the next start; the "
                      "overlay theme changes as soon as you Save.")
        themes = [(OV.THEME_NAMES[k], k) for k in OV.THEME_ORDER]
        self.swatches = {}
        self._choice(body, "app_theme", "App theme", themes, "",
                     command=lambda _v: self.theme_picked("app_theme"))
        self._swatch_row(body, "app_theme")
        restart_row = ctk.CTkFrame(body, fg_color="transparent")
        restart_row.pack(fill="x", padx=14, pady=(0, 8))
        tip(ctk.CTkButton(restart_row, text="Save and restart now", width=190,
                      height=28, font=F_STRONG, **BTN_SECONDARY,
                      command=self.save_and_restart), "Saves Settings and starts EDSMT again, so a new app theme shows.").pack(side="left")
        self._choice(body, "overlay_theme", "Overlay theme", themes, "",
                     command=lambda _v: self.theme_picked("overlay_theme"))
        self._swatch_row(body, "overlay_theme")
        body = self.pages["Theme"]
        self._section(body, "Match my in-game HUD colours",
                      "Reads the colours the game is using - the HUD colour "
                      "matrix, or EDHM when it is installed - and makes a "
                      "theme of them for the app and the overlay together.")
        match_row = ctk.CTkFrame(body, fg_color="transparent")
        match_row.pack(fill="x", padx=10, pady=(2, 4))
        tip(ctk.CTkButton(match_row, text="Match my in-game HUD colours",
                          width=320, height=44, font=F_ACTION, **BTN_PRIMARY,
                          command=self.match_game_theme),
            "Reads the game's HUD colours now and sets both themes to match them.").pack(side="left")
        self.game_line = ctk.CTkLabel(body, text="", font=F_SMALL, text_color=DIM,
                                      justify="left", anchor="w", wraplength=560)
        self.game_line.pack(fill="x", padx=10, pady=(0, 6))
        body = self.pages["Theme"]
        self._section(body, "Powerplay",
                      "A theme in the colours of each Power. Pick one and "
                      "both the app and the overlay take it.")
        power_row = ctk.CTkFrame(body, fg_color="transparent")
        power_row.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(power_row, text="Power", width=250, anchor="w",
                     font=F_BODY, text_color=TEXT).pack(side="left")
        powers = [power for _key, power, _accent in OV.POWERPLAY]
        self.power_box = tip(ctk.CTkComboBox(power_row, values=powers, font=F_BODY,
                                             height=30, **BOX,
                                             command=self.power_picked),
                             "Sets the app theme and the overlay theme to this Power's colours.")
        self.power_box.pack(side="left", fill="x", expand=True)
        self.power_box.set(powers[0])

        # 1.10036: no community map section. Every find goes up with the
        # CMDR name of whoever found it, everybody's finds are on the map,
        # and there is nothing to switch (ALWAYS_SHARED). The leaderboard's
        # Join and Leave are in its own window.
        body = self.pages["Sharing"]
        self._section(body, "Inara",
                      "Reports where you are while you play. Your CMDR name is "
                      "read from the journal, never typed.")
        self._switch(body, "inara_enabled", "Send my location to Inara")
        self._entry(body, "inara_api_key", "Inara API key",
                    "from your Inara account settings", secret=True)
        self._switch(body, "inara_is_being_developed", "Mark my events as test data")

        body = self.pages["Sharing"]
        self._section(body, "Discord",
                      "Your own channel: one summary of every Rhino session "
                      "when it ends - and every find you mark as well, if you "
                      "tick it. In Discord: "
                      "the channel's settings > Integrations > Webhooks > New "
                      "Webhook > Copy Webhook URL, and paste it here. It is a "
                      "password for that channel - it stays behind dots.")
        self._entry(body, "discord_webhook", "Webhook URL",
                    "https://discord.com/api/webhooks/...", secret=True)
        self._switch(body, "discord_post_sessions",
                     "Post a summary when a Rhino session ends")
        self._switch(body, "discord_post_finds",
                     "Also post every find I mark (one message each)")
        self._switch(body, "discord_attach_map",
                     "Send the map picture with the summary")
        self._switch(body, "discord_edit_after_sale",
                     "Update the same message when the cargo is sold")
        discord_row = ctk.CTkFrame(body, fg_color="transparent")
        discord_row.pack(fill="x", padx=10, pady=(0, 4))
        tip(ctk.CTkButton(discord_row, text="Send a test message", width=190,
                      height=30, font=F_STRONG, **BTN_SECONDARY,
                      command=self.test_discord), "Posts one message to the webhook in the box, saved or not.").pack(side="left")

        body = self.pages["Sharing"]
        self._section(body, "Radio Raxxla staff",
                      "Only for staff who confirm finds. Everyone else leaves "
                      "this blank.")
        self._entry(body, "community_token", "Staff token", "", secret=True)

        body = self.pages["Your data"]
        self._section(body, "Game folder",
                      "Found automatically. Only set this if Elite lives "
                      "somewhere unusual, or you run it through Steam Play.")
        self._entry(body, "journal_dir", "Saved Games folder", "leave blank for automatic")
        self._linux_note(body, "journal")

        settings_now = getattr(self.app, "settings", None)
        body = self.pages["Rigs"]
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
        self._entry(body, "rig_offset_m",
                    "A rig lands this far behind the cockpit (m)", "7")
        self._switch(body, "rigs_clear_on_dock",
                     "Take a Rhino's rigs off the scope when it docks in the ship")
        self._switch(body, "show_shared_layouts",
                     "Show the best rig layout others used on this deposit")
        ctk.CTkLabel(body, text=(
            "The rig planner: %s starts tracing. Drive along the "
            "deposit's edge and back to where you pressed it. The loop "
            "closes by itself, or press it again to close it where you are. "
            "The pins go on the scope in driving order - drop a rig on each "
            "one - and the plan is kept with the deposit for your next visit. "
            "The spacing is the community's working figure, not a "
            "published one; change it if you find better."
            % bound_key(settings_now, "trace", "the planner key")),
            font=F_SMALL, text_color=DIM, justify="left", wraplength=560,
            anchor="w").pack(fill="x", padx=10, pady=(0, 4))
        self._entry(body, "rig_spacing_m", "Rig planner: metres between rigs", "78")
        try:
            measured = CR.spacing_words(self.app.crowd_figures().spacing)
        except Exception:
            measured = ""
        if measured:
            ctk.CTkLabel(body, text="From the community map: " + measured,
                         font=F_SMALL, text_color=DIM, justify="left",
                         wraplength=560, anchor="w").pack(fill="x", padx=10, pady=(0, 4))
        self._switch(body, "rig_radar",
                     "Spacing rings: a ring of that spacing round each rig, and "
                     "NEXT RIG on the map and scope")

        body = self.pages["Rigs"]
        self._section(body, "Wing link (beta)",
                      "Mining one body with friends - or crew off one ship "
                      "with more than one Rhino? Everyone switches this on "
                      "and types the same code, and each of you sees the "
                      "others' Rhinos and rigs on the scope, so nobody drops "
                      "a rig on top of anybody else's, with your commander "
                      "name beside yours. Nothing is "
                      "kept: the server forgets you two minutes after you "
                      "switch it off or close EDSMT.")
        self._switch(body, "wing_link", "Wing link (beta): share my Rhino and "
                                        "rigs with my wing")
        self._entry(body, "wing_code", "Wing code (6 letters and digits)",
                    "the same code for everyone")
        code_row = ctk.CTkFrame(body, fg_color="transparent")
        code_row.pack(fill="x", padx=14, pady=(0, 6))
        tip(ctk.CTkButton(code_row, text="Make a new code", width=160, height=28,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.make_wing_code), "A fresh six-character wing code to read out to your wing.").pack(side="left")

        body = self.pages["Rigs"]
        self._section(body, "Long press for a rig",
                      "In the Rhino with the game in front, your fire button "
                      "held for two seconds counts as a rig placed - what the "
                      "rig-down key does. A click never does, and a press of "
                      "half a second to two is neither. The button is read "
                      "from your own binds in the game. Windows only. Nothing "
                      "about a press is written down.")
        self._linux_note(body, "long_press")
        self._switch(body, "long_press_rig", "Count a long press as a rig placed")
        self._choice(body, "long_press_button", "Rig button",
                     [("Primary fire", "primary"), ("Secondary fire", "secondary")])
        self.binds_line = ctk.CTkLabel(body, text="", font=F_SMALL, text_color=DIM,
                                       justify="left", anchor="w", wraplength=560)
        self.binds_line.pack(fill="x", padx=10, pady=(0, 2))
        binds_row = ctk.CTkFrame(body, fg_color="transparent")
        binds_row.pack(fill="x", padx=10, pady=(0, 4))
        tip(ctk.CTkButton(binds_row, text="Read my binds again", width=190,
                          height=28, font=F_STRONG, **BTN_SECONDARY,
                          command=lambda: self.show_binds(force=True)),
            "Reads the game's binds file now - after you change your "
            "controls in the game.").pack(side="left")
        self.show_binds()

        body = self.pages["Keys"]
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
        self._linux_note(body, "hotkeys")
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
                 ("hotkey_trace", "Rig planner: trace the deposit's edge")]
        for name, label in rows:
            self._binding(body, name, label, DEFAULT_SETTINGS[name])
        self._binding(body, "hotkey_centre", "Move the centre here (no new log)", "")
        self._binding(body, "hotkey_lock", "Lock / unlock the overlay", "")
        self._binding(body, "hotkey_overlay", "Overlay on / off", OVERLAY_KEY)
        self._binding(body, "hotkey_zoom", "Scope zoom: 1x, 2x, 4x", SCOPE_ZOOM_KEY)
        for name, label, fallback in (
                ("hotkey_wp_next", "Survey waypoint: next", GD.WAYPOINT_KEYS[0][1]),
                ("hotkey_wp_back", "Survey waypoint: back", GD.WAYPOINT_KEYS[1][1]),
                ("hotkey_wp_skip", "Survey waypoint: skip this one", GD.WAYPOINT_KEYS[2][1]),
                ("hotkey_wp_pause", "Survey waypoint: pause / resume", GD.WAYPOINT_KEYS[3][1])):
            self._binding(body, name, label, fallback)
        self.hotkey_note = ctk.CTkLabel(
            body, text="", font=F_SMALL, text_color=AMBER,
            justify="left", anchor="w")
        self.hotkey_note.pack(fill="x", padx=10, pady=(2, 0))
        body = self.pages["Keys"]
        self._section(body, "Joystick and HOTAS buttons",
                      ("Each key above has a Joystick button beside it: click "
                       "it and press the button you want on any joystick, "
                       "throttle or HOTAS %s lists - up to 16 devices of "
                       "32 buttons. EDSMT reads the device itself, so pick a "
                       "button the game does not use, or it does both. Reset "
                       "clears it.%s")
                      % (("Windows", " Windows only.") if os.name == "nt"
                         else ("the system", "")))
        self._linux_note(body, "joystick")
        body = self.pages["Keys"]
        self._section(body, "Chat commands",
                      "Messages you send in the game's chat that start with "
                      "the prefix run a command: alexandrite h/m 4 marks it "
                      "here (amount, density, rigs); 135 1.2km alexandrite "
                      "marks it that far away on that bearing; rig down 3, "
                      "rig up 3, rigs up, centre and undo do what they say. "
                      "Only your own messages are read. Local chat is public: "
                      "everyone near you can read a command as you type it.")
        self._switch(body, "chat_tags", "Run commands I type in the game's chat")
        self._entry(body, "chat_prefix", "Commands start with", "!rr")

        body = self.pages["Your data"]
        self._section(body, "Map pictures",
                      "A picture of the map - deposits, rigs, the ground swept, "
                      "a scale bar - saved when the Rhino docks, and by the "
                      "Save, Copy and Share map buttons under the map.")
        self._switch(body, "map_picture_auto", "Save a map picture each time the Rhino docks")
        pictures_row = ctk.CTkFrame(body, fg_color="transparent")
        pictures_row.pack(fill="x", padx=10, pady=(0, 4))
        tip(ctk.CTkButton(pictures_row, text="Open the pictures folder", width=200,
                      height=30, font=F_STRONG, **BTN_SECONDARY,
                      command=self.open_pictures_folder), "Opens the folder the map pictures are saved in.").pack(side="left")
        body = self.pages["Your data"]
        self._section(body, "Your finds",
                      "One dated zip with everything in it. Worth doing "
                      "before a Windows reinstall, and worth doing whether "
                      "or not you share - sharing sends deposits, not your "
                      "settings or your notes.")
        backup_row = ctk.CTkFrame(body, fg_color="transparent")
        backup_row.pack(fill="x", padx=10, pady=(0, 4))
        tip(ctk.CTkButton(backup_row, text="Back up now", width=130, height=30,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.backup_now), "One dated zip of your finds, sessions, survey and settings, wherever you choose.").pack(side="left", padx=(0, 8))
        tip(ctk.CTkButton(backup_row, text="Restore from a backup", width=180,
                      height=30, font=F_STRONG, **BTN_SECONDARY,
                      command=self.restore_now), "Puts a backup zip back. What is here now is kept beside it, renamed.").pack(side="left", padx=8)
        tip(ctk.CTkButton(backup_row, text="Open my data folder", width=170,
                      height=30, font=F_STRONG, **BTN_SECONDARY,
                      command=self.open_data_folder), "Opens the folder your finds and settings are kept in.").pack(side="left", padx=8)

        # A second row rather than a fourth button: Settings is 640 wide and
        # the three above already fill it. Same section, because bringing
        # somebody else's finds in belongs with backing your own up - both
        # are the database changing under you, and both want the zip.
        import_row = ctk.CTkFrame(body, fg_color="transparent")
        import_row.pack(fill="x", padx=10, pady=(0, 4))
        tip(ctk.CTkButton(import_row, text="Import another tool's CSV", width=210,
                      height=30, font=F_STRONG, **BTN_SECONDARY,
                      command=self.import_now), "Brings in finds from another surface-mining tool's surfaceminingmap.csv.").pack(side="left", padx=(0, 8))
        tip(ctk.CTkButton(import_row, text="Import from another tool...", width=210,
                      height=30, font=F_STRONG, **BTN_SECONDARY,
                      command=self.open_import_window), "Brings in a bookmark database, share lines, a survey CSV or a map file, with a preview and a backup first.").pack(side="left", padx=8)
        self._entry(body, "trash_days",
                    "Keep removed sites in the bin for (days)", "30")
        # Dated copies of the settings (1.10034): overlay placement, layout,
        # theme, keys - the lot - one pick away from coming back.
        ctk.CTkLabel(body, text="Earlier settings - overlay placement, "
                                "layout, theme, keys, the lot:",
                     font=F_BODY, text_color=TEXT, anchor="w").pack(
                         fill="x", padx=10, pady=(6, 2))
        history_row = ctk.CTkFrame(body, fg_color="transparent")
        history_row.pack(fill="x", padx=10, pady=(0, 4))
        self._history = settings_history()
        labels = [settings_copy_label(when, path)
                  for when, path in self._history] or [NO_SETTINGS_COPIES]
        self.history_box = tip(ctk.CTkComboBox(history_row, values=labels,
                                           width=380, font=F_BODY,
                                           state="readonly", **BOX), "Every dated copy of your settings, newest first.")
        self.history_box.set(labels[0])
        self.history_box.pack(side="left", padx=(0, 8))
        tip(ctk.CTkButton(history_row, text="Put these back", width=150,
                      height=30, font=F_STRONG, **BTN_SECONDARY,
                      command=self.restore_settings_now), "Puts the picked copy of your settings back - overlay, layout, keys, the lot.").pack(side="left", padx=8)
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
        tip(ctk.CTkButton(paste_row, text="Import", width=90, height=30,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.paste_shared), "Adds the shared finds pasted in the box.").pack(side="left", padx=(8, 0))
        ctk.CTkLabel(body,
                     text="The CSV: either surfaceminingmap.csv layout. The box: "
                          "lines made by Copy to share on a deposit - chat "
                          "round them is ignored. Nothing already here is "
                          "changed. Shift+Enter starts a new line.",
                     font=F_SMALL, text_color=DIM, justify="left", anchor="w",
                     wraplength=560).pack(fill="x", padx=10, pady=(0, 4))

        body = self.pages["About"]
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
        tip(ctk.CTkButton(version_row, text="Check for updates", width=170,
                      height=30, font=F_STRONG, **BTN_SECONDARY,
                      command=self.check_updates), "Asks the website whether a newer EDSMT is out.").pack(side="right")
        body = self.pages["About"]
        self._section(body, "Support",
                      "Something wrong? One zip with the version, your system, "
                      "your settings with every key, token and webhook taken "
                      "out, crash.log, the journal event log and the newest "
                      "lines of the app log. Read it first if you like - it is "
                      "plain text. Then send it with your report.")
        support_row = ctk.CTkFrame(body, fg_color="transparent")
        support_row.pack(fill="x", padx=10, pady=(0, 4))
        tip(ctk.CTkButton(support_row, text="Make a support bundle", width=200,
                      height=30, font=F_STRONG, **BTN_SECONDARY,
                      command=self.make_support_bundle), "Writes one zip for a bug report, with no keys in it, and opens its folder.").pack(side="left")

        body = self.pages["Overlay"]
        self._section(body, "In-game overlay",
                      "A compass strip across the top of the screen showing "
                      "which way every recorded deposit is, so you never have "
                      "to alt-tab. It CANNOT appear over the game in exclusive "
                      "fullscreen - that is DirectX, not the app. Set Elite to "
                      "borderless or windowed and it will. Unlock it to drag it "
                      "where you want, then lock it again so clicks reach the "
                      "game.")
        # Four boxes, four switches. The old "which overlay" question only
        # ever had one answer at a time, and testers wanted more than one.
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
        self._linux_note(body, "overlay")
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
        self._choice(body, "overlay_swept", "Swept ground on the scope",
                     list(OV.SWEPT_LOOKS),
                     "Clear shows the ground you have already scanned plainly; "
                     "Faint is a light mesh that hides less of the game; Solid "
                     "is the easiest to see on a big screen.")
        body = self.pages["Overlay"]
        self._section(body, "Map and scope",
                      "What the main map and the scope draw on top of the "
                      "finds. Top patches are the knots of deposits worth a "
                      "stop: at least five rigs' worth within the radius "
                      "below (four, when no knot has five), the best three "
                      "circled, with what each is worth an hour, "
                      "driving included. The zoom key (%s) steps the scope "
                      "1x, 2x, 4x - past 1x it follows the Rhino."
                      % (key_text((settings_now or {}).get("hotkey_zoom", SCOPE_ZOOM_KEY))
                         or "not set"))
        self._switch(body, "map_trail", "Draw the line I have driven")
        self._switch(body, "overlay_trail_paint",
                     "Paint the ground I have driven on the scope before a "
                     "border is set")
        self._switch(body, "map_lines",
                     "Lines to the nearest deposit of the same commodity and "
                     "the next cheaper one")
        self._switch(body, "map_golden", "Top patches: circle the best knots "
                                         "of deposits")
        self._entry(body, "golden_radius_m", "Top patch radius (m, 500-2,500)",
                    "1250")
        self._switch(body, "survey_guide",
                     "Guided survey: numbered waypoints over the survey area")
        self._entry(body, "waypoint_radius_m", "Waypoint reached within (m, 50-1,000)",
                    "250")
        self._switch(body, "rhino_pointer",
                     "Point to the parked Rhino, and to the ship from the Rhino")
        self._switch(body, "orbit_guide",
                     "In the ship: distance and bearing to the deposit or signal")
        filter_row = ctk.CTkFrame(body, fg_color="transparent")
        filter_row.pack(fill="x", padx=10, pady=(2, 4))
        tip(ctk.CTkButton(filter_row, text="Marker filters...", width=170,
                          height=30, font=F_STRONG, **BTN_SECONDARY,
                          command=self.open_filter_window),
            "Choose which deposits the map and the scope draw, by commodity, amount and density, and whether names are written beside them.").pack(side="left")
        # A whole layout in one pick - "disable all other windows and have
        # the map triple the size" on a 3440x1440 screen.
        self._choice(body, "overlay_preset", "Layout",
                     list(OV.LAYOUT_PRESETS),
                     "Map focus: the scope three times the size, every other "
                     "box off. Minimal: compass and status. Streamer: clear of "
                     "a webcam and chat. Press Apply layout - then drag any "
                     "box from there.")
        preset_row = ctk.CTkFrame(body, fg_color="transparent")
        preset_row.pack(fill="x", padx=14, pady=(2, 6))
        tip(ctk.CTkButton(preset_row, text="Apply layout", width=180,
                      height=28, font=F_STRONG, **BTN_SECONDARY,
                      command=self.apply_preset), "Moves the overlay boxes to the picked layout.").pack(side="left")
        reset_row = ctk.CTkFrame(body, fg_color="transparent")
        reset_row.pack(fill="x", padx=14, pady=(2, 6))
        tip(ctk.CTkButton(reset_row, text="Reset box positions", width=180,
                      height=28, font=F_STRONG, **BTN_SECONDARY,
                      command=self.reset_boxes), "Puts every overlay box back where it starts - for a box dragged off screen.").pack(side="left")
        ctk.CTkLabel(reset_row, font=F_SMALL, text_color=DIM, anchor="w",
                     text="  Puts every overlay box back where it started. "
                          "Positions are stored as a share of the screen, so "
                          "they follow you between monitors."
                     ).pack(side="left", fill="x", expand=True)

        body = self.pages["Sharing"]
        self._section(body, "Ranking",
                      "How fast a shared find loses value. Deposits come back "
                      "slowly, so a site halves in score every this many days.")
        self._entry(body, "freshness_half_life_days", "Freshness half-life (days)", "21")

        body = self.pages["About"]
        self._section(body, "Beta testers",
                      "Who drove out to the deposits, found what was wrong "
                      "with this and said so. o7")
        ctk.CTkLabel(body, text="   ".join(BETA_TESTERS),
                     font=F_BODY, text_color=AMBER,
                     justify="left", wraplength=560,
                     anchor="w").pack(fill="x", padx=10, pady=(0, 4))

        body = self.pages["About"]
        self._section(body, "About EDSMT", ABOUT_LINE)
        self._about_picture = picture(ABOUT_PICTURE, self)
        if self._about_picture is not None:
            tk.Label(body, image=self._about_picture, bg=PANEL, bd=0,
                     highlightthickness=0).pack(anchor="w", padx=10,
                                                pady=(2, 6))
        ctk.CTkLabel(body, text=about_text(), font=F_SMALL, text_color=DIM,
                     justify="left", wraplength=560,
                     anchor="w").pack(fill="x", padx=10, pady=(0, 8))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=12, pady=(0, 8))
        tip(ctk.CTkButton(buttons, text="Save", width=110, height=32,
                      font=F_STRONG, **BTN_PRIMARY,
                      command=self.save), "Saves every change on this screen.").pack(side="left", padx=(0, 8))
        tip(ctk.CTkButton(buttons, text="Test connection", width=140, height=32,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.test), "Checks the community map and Inara answer with what is in the boxes.").pack(side="left", padx=8)
        tip(ctk.CTkButton(buttons, text="Close", width=90, height=32,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.destroy), "Closes Settings without saving.").pack(side="right")

        self.status = ctk.CTkLabel(self, text="", font=F_READOUT,
                                   text_color=DIM, anchor="w", wraplength=600)
        self.status.pack(fill="x", padx=14, pady=(0, 10))
        self.load()

    def show_binds(self, force=False):
        """Say what the game's binds make the rig button: the file, and what
        Primary and Secondary fire are bound to for the SRV."""
        label = attr(self, "binds_line", None)
        if label is None:
            return ""
        try:
            found = IM.rig_binds(self.app, force=force)
        except Exception as exc:
            found = {"why": "The game's binds could not be read: %s" % exc}
        if found.get("why"):
            text = ("%s Until they can be, Primary fire is the left mouse button "
                    "and Secondary fire the right, as the game sets them."
                    % found["why"])
        else:
            text = ("From your binds (%s): Primary fire is %s; Secondary fire is %s."
                    % (os.path.basename(found.get("file") or ""),
                       GB.words(found.get("primary")), GB.words(found.get("secondary"))))
        try:
            label.configure(text=text)
        except Exception:
            pass
        return text

    def _section(self, parent, title, blurb):
        hud_header(parent, title, padx=10, pady=(16, 4))
        ctk.CTkLabel(parent, text=blurb, font=F_SMALL, text_color=DIM,
                     justify="left", wraplength=560, anchor="w").pack(fill="x", padx=10,
                                                                     pady=(0, 6))

    def _linux_note(self, parent, key):
        """The Linux-only note for a section, where there is one."""
        text = linux_notes().get(key, "")
        if text:
            ctk.CTkLabel(parent, text=text, font=F_SMALL, text_color=AMBER,
                         justify="left", wraplength=560, anchor="w").pack(
                fill="x", padx=10, pady=(0, 6))

    def _switch(self, parent, key, label):
        var = ctk.BooleanVar(value=False)
        tip(ctk.CTkSwitch(parent, text=label, variable=var, font=F_BODY,
                          **SWITCH), SETTING_TIPS.get(key)).pack(anchor="w",
                                                                 padx=10, pady=4)
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
            button = tip(ctk.CTkButton(row, text="Show", width=68, height=30,
                                   font=F_STRONG, **BTN_SECONDARY,
                                   command=lambda: self.reveal(key)), "Shows the key for a few seconds, then hides it again.")
            button.pack(side="right", padx=(6, 0))
            self.secrets[key] = button
        entry = ctk.CTkEntry(row, placeholder_text=placeholder, height=30,
                             font=F_BODY, **ENTRY, show=MASK if secret else "")
        tip(entry, SETTING_TIPS.get(key)).pack(side="left", fill="x", expand=True)
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

    def _choice(self, parent, key, label, options, hint="", command=None):
        """A named choice, stored as its value rather than its label.

        The box shows what a person reads; settings.json holds what the
        code tests. Renaming a label then never silently changes a stored
        setting. `command`, when given, runs with the label picked from the
        list (1.10039: the theme pickers repaint their swatches).
        """
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row, text=label, width=250, anchor="w",
                     font=F_BODY, text_color=TEXT).pack(side="left")
        box = ctk.CTkComboBox(row, values=[name for name, _v in options],
                              font=F_BODY, height=30, **BOX,
                              **({"command": command} if command else {}))
        tip(box, SETTING_TIPS.get(key)).pack(side="left", fill="x", expand=True)
        Suggest(box, [name for name, _v in options], on_pick=command)
        self.choices[key] = (box, list(options))
        if hint:
            ctk.CTkLabel(parent, text=hint, font=F_SMALL,
                         text_color=DIM, justify="left", anchor="w",
                         wraplength=560).pack(fill="x", padx=10, pady=(0, 4))

    # 1.10039 (#287): the Theme tab.
    def _swatch_row(self, parent, key):
        """A strip of the chosen theme's colours under a theme picker: the
        accent, the highlight, the text ranks and the OK, warning and
        telemetry colours, on that theme's panel. Painted by load() and
        repainted whenever the picker changes."""
        strip = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=0,
                             border_width=1, border_color=RULE, height=34)
        strip.pack(fill="x", padx=14, pady=(0, 6))
        strip.pack_propagate(False)
        patches = {"_strip": strip}
        for name in SWATCH_KEYS:
            patch = ctk.CTkFrame(strip, width=44, height=22, fg_color=ORANGE,
                                 corner_radius=0)
            patch.pack(side="left", padx=(6, 0), pady=5)
            patch.pack_propagate(False)
            patches[name] = patch
        self.swatches[key] = patches

    def _theme_key(self, key):
        """The theme key the picker `key` shows, or the cockpit."""
        try:
            box, options = self.choices[key]
            shown = str(box.get() or "").strip()
            return next((value for name, value in options if name == shown), "cockpit")
        except (KeyError, AttributeError):
            return "cockpit"

    def _paint_swatches(self, key):
        patches = (attr(self, "swatches", None) or {}).get(key)
        if not patches:
            return
        palette = OV.theme_palette(self._theme_key(key))
        try:
            patches["_strip"].configure(fg_color=palette["PANEL"], border_color=palette["RULE"])
            for name in SWATCH_KEYS:
                patches[name].configure(fg_color=palette[name])
        except Exception:
            pass        # the window has gone; there is nothing left to paint

    def theme_picked(self, key):
        """A theme picker changed: repaint its swatches."""
        self._paint_swatches(key)

    def _pick_theme(self, theme):
        """Put one theme in both pickers, and paint both swatch rows."""
        for key in ("app_theme", "overlay_theme"):
            box, options = self.choices[key]
            box.set(next((name for name, value in options if value == theme), options[0][0]))
            self._paint_swatches(key)

    def power_picked(self, power):
        """A Power picked: its theme for the app and the overlay together."""
        theme = next((key for key, name, _accent in OV.POWERPLAY
                      if name == str(power or "").strip()), None)
        if theme is None:
            return
        self._pick_theme(theme)
        self.say("%s for the app and the overlay. Save keeps it; Save and restart "
                 "now shows the app in it straight away." % OV.THEME_NAMES[theme], GREEN)

    def match_game_theme(self, **where):
        """The big button: read the game's HUD colours now, make them the game
        theme, pick it for both, and say what was found."""
        found = refresh_game_theme(**where)
        self.app.game_theme = found
        self._pick_theme(OV.GAME_THEME)
        self._show_game_line()
        self.say("Matched. Save keeps it; Save and restart now shows the app in it "
                 "straight away.", GREEN)

    def _show_game_line(self):
        line = attr(self, "game_line", None)
        found = getattr(self.app, "game_theme", None) or {}
        if line is None:
            return
        try:
            line.configure(text=str(found.get("words") or ""))
        except Exception:
            pass

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
        box = tip(ctk.CTkComboBox(row, values=[name for name, _v in options],
                              font=F_BODY, height=30, **BOX,
                              command=lambda _v, k=key: self._show_colour(k)), SETTING_TIPS.get(key))
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
        tip(ctk.CTkButton(row, text="Reset", width=68, height=30,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=lambda: self._reset_binding(key, fallback)
                      ), "Puts this key back to its default, and clears its joystick "
                         "button.").pack(side="right", padx=(6, 0))
        joy = IND.joy_setting(key)
        if joy:
            self._joystick_button(row, joy, label)
        button = ctk.CTkButton(row, text=fallback, height=30,
                               font=F_STRONG, **BTN_SECONDARY,
                               command=lambda: self._capture(key))
        tip(button, "%s. %s" % (label, BINDING_TIP)).pack(side="left", fill="x",
                                                          expand=True)
        self.binders[key] = button
        self.bindings[key] = fallback

    def _reset_binding(self, key, fallback):
        """Reset: the key back to its default and its joystick button off."""
        self._set_binding(key, fallback)
        joy = IND.joy_setting(key)
        if joy in self.joy_binders:
            self._set_joy(joy, "")

    def _joystick_button(self, row, joy, label):
        """The joystick side of a key row (1.10035, #198): click, then press
        the button on the stick, throttle or HOTAS."""
        button = tip(ctk.CTkButton(row, text="Joystick", width=104, height=30,
                                   font=F_STRONG, **BTN_SECONDARY,
                                   command=lambda: self._capture_joy(joy)),
                     "%s: click, then press the joystick button you want. "
                     "Escape cancels, Reset clears it. Pick one the game "
                     "does not use." % label)
        button.pack(side="right", padx=(6, 0))
        self.joy_binders[joy] = button
        self.joy_bindings[joy] = ""

    def _set_joy(self, joy, value):
        self.joy_bindings[joy] = value
        button = self.joy_binders.get(joy)
        if button is not None:
            button.configure(text=value or "Joystick", **BTN_SECONDARY)

    def _capture_joy(self, joy):
        """Listen for one joystick button, then stop listening. The app's own
        joystick timer is held (muted) meanwhile, so the press that is being
        bound does not also run what it was bound to before."""
        if self._joy_capturing:
            return
        watcher = IM.state(self.app).joystick
        if not watcher.available():
            return self.say("Joystick buttons are read on Windows and Linux only.", AMBER)
        if not watcher.rebase():
            return self.say("No joystick or HOTAS found. Plug it in, then "
                            "click again.", AMBER)
        watcher.muted = True
        self._joy_capturing = joy
        self._joy_ticks = 0
        self.joy_binders[joy].configure(text="press a button...", **BTN_WARN)
        self.say("Press the joystick button you want. Escape cancels.", AMBER)
        try:
            self._joy_escape = self.bind("<Escape>", lambda _e: self._joy_done(None))
        except Exception:
            self._joy_escape = None
        self._joy_after = self.after(IND.POLL_MS, self._joy_poll)

    def _joy_poll(self):
        if not self._joy_capturing:
            return
        try:
            presses = IM.state(self.app).joystick.new_presses()
            self._joy_ticks += 1
            if presses:
                return self._joy_done(IND.joy_text(*presses[0]))
            if self._joy_ticks * IND.POLL_MS >= IND.JOY_CAPTURE_S * 1000:
                return self._joy_done(None, "No button pressed - left as it was.")
            self._joy_after = self.after(IND.POLL_MS, self._joy_poll)
        except Exception:
            self._joy_done(None)

    def _joy_done(self, value, note="Left as it was."):
        joy, self._joy_capturing = self._joy_capturing, None
        IM.state(self.app).joystick.muted = False
        try:
            if self._joy_escape is not None:
                self.unbind("<Escape>", self._joy_escape)
        except Exception:
            pass
        self._joy_escape = None
        if not joy:
            return
        try:
            if not value:
                self._set_joy(joy, self.joy_bindings.get(joy, ""))
                return self.say(note)
            clash = [other for other, held in self.joy_bindings.items()
                     if other != joy and held == value]
            if clash:
                self._set_joy(joy, self.joy_bindings.get(joy, ""))
                return self.say("%s is already doing something else in EDSMT."
                                % value, RED)
            self._set_joy(joy, value)
            self.say("%s it is. Save to keep it." % value, GREEN)
        except Exception:
            pass     # the window was closed while it was listening

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
        for key in list(attr(self, "swatches", None) or {}):
            self._paint_swatches(key)
        self._show_game_line()
        # The bindings were seeded with the hardcoded fallback when the row
        # was built and load() never touched them again, so Settings showed
        # F9/F10 whatever you had bound - and save() wrote that lie back.
        # Opening Settings to change the opacity threw your hotkeys away.
        for key in list(self.binders):
            self._set_binding(key, str(data.get(key)
                                       or DEFAULT_SETTINGS.get(key, "")))
        for joy in list(attr(self, "joy_binders", None) or {}):
            self._set_joy(joy, IND.clean_joy(data.get(joy)))
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
        # Plain metres: parse_metres reads a bare 7 as 7 km, which is right
        # for a warning distance and wrong for a few metres behind a cab.
        try:
            raw = str(data.get("rig_offset_m", RIG_OFFSET_M)).strip().lower()
            offset = float(raw.rstrip("m").strip()) if raw else RIG_OFFSET_M
        except ValueError:
            offset = None
        if offset is None or not 0 <= offset <= RIG_OFFSET_MAX_M:
            return self.say("A rig lands 0 to %d m behind the cockpit - 7 is "
                            "the measured figure." % RIG_OFFSET_MAX_M, RED)
        data["rig_offset_m"] = offset
        spacing = parse_metres(data.get("rig_spacing_m") or RP.RIG_SPACING_M)
        if spacing is None or not PLAN_SPACING_MIN_M <= spacing <= PLAN_SPACING_MAX_M:
            return self.say("The rig planner's spacing must be a distance "
                            "between %d and %d m - 78 is the community's "
                            "figure." % (PLAN_SPACING_MIN_M, PLAN_SPACING_MAX_M),
                            RED)
        data["rig_spacing_m"] = spacing
        raw = str(data.get("golden_radius_m") or "").strip().lower().replace(",", "")
        try:
            radius = (float(raw[:-2].strip()) * 1000.0 if raw.endswith("km")
                      else float(raw.rstrip("m").strip())) if raw else PV.GOLDEN_RADIUS_M
        except ValueError:
            radius = None
        if radius is None or not PV.GOLDEN_RADIUS_MIN_M <= radius <= PV.GOLDEN_RADIUS_MAX_M:
            return self.say("A top patch's radius is 500 to 2,500 m - 1,250 "
                            "is the usual.", RED)
        data["golden_radius_m"] = int(radius) if float(radius).is_integer() else radius
        arrive = parse_metres(data.get("waypoint_radius_m") or GD.WP.ARRIVE_M)
        if arrive is None or not GD.WP.ARRIVE_MIN_M <= arrive <= GD.WP.ARRIVE_MAX_M:
            return self.say("A waypoint counts as reached within 50 to 1,000 m - "
                            "250 is the usual.", RED)
        data["waypoint_radius_m"] = int(arrive) if float(arrive).is_integer() else arrive
        raw = str(data.get("trash_days") or "").strip()
        try:
            days = int(float(raw)) if raw else SBK.TRASH_DAYS
        except ValueError:
            days = None
        if days is None or not 1 <= days <= SBK.TRASH_DAYS_MAX:
            return self.say("The bin keeps a removed site for 1 to %d days - "
                            "30 is the usual." % SBK.TRASH_DAYS_MAX, RED)
        data["trash_days"] = days
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
        raw_jump = str(data.get("jump_range_ly") or "").lower().replace("ly", "") \
            .replace(",", ".").strip()
        try:
            jump = float(raw_jump) if raw_jump else 0.0
        except ValueError:
            jump = -1.0
        if not 0.0 <= jump <= 150.0:
            return self.say("The jump range is light years a jump - 20 or "
                            "42.7 work. Leave it blank to use your ship's.", RED)
        data["jump_range_ly"] = int(jump) if jump.is_integer() else round(jump, 2)
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
        seen_joy = {}
        for joy, value in (attr(self, "joy_bindings", None) or {}).items():
            if value and value in seen_joy:
                return self.say("%s is bound to two things at once." % value, RED)
            seen_joy[value] = joy
            data[joy] = value
        prefix = re.sub(r"\s+", "", str(data.get("chat_prefix") or ""))
        if prefix and not 2 <= len(prefix) <= 12:
            return self.say("A chat command starts with 2 to 12 characters, "
                            "no spaces - !rr is the usual.", RED)
        data["chat_prefix"] = prefix or CT.DEFAULT_PREFIX
        # Nothing is learned any more: the button is the game's own binding.
        data["long_press_learned"] = ""
        folder = data.get("journal_dir", "")
        if folder and not os.path.isdir(folder):
            return self.say("That folder does not exist.", RED)
        hook = str(data.get("discord_webhook") or "").strip()
        if hook and not EDO.discord_hook_ok(hook):
            return self.say("That is not a Discord webhook address. In Discord: "
                            "channel settings > Integrations > Webhooks > Copy "
                            "Webhook URL.", RED)
        data["discord_webhook"] = hook

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

    def apply_preset(self):
        """Lay the overlay out as the preset picked in the Layout box, and
        set the box switches here to match, so Save does not undo it."""
        name = "standard"
        try:
            box, options = self.choices["overlay_preset"]
            shown = str(box.get() or "").strip().lower()
            name = next((value for label, value in options
                         if label.lower() == shown or value == shown), name)
        except Exception:
            pass
        on = self.app.apply_overlay_preset(name)
        for key in OV.PANEL_ORDER:
            var = self.toggles.get("overlay_show_%s" % key)
            if var is not None:
                var.set(key in on)
        label = dict((v, l) for l, v in OV.LAYOUT_PRESETS).get(name, name)
        self.say("%s layout applied. Unlock the overlay to drag any box from "
                 "there." % label, GREEN)

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
        # The settings in the zip are on disk now, but the app was still
        # holding the old ones and would have saved them straight back over
        # it - so they are read and worn now, and this window, which shows
        # the old ones, closes rather than offering to save them again.
        self.app.apply_settings(load_settings())
        self.app.redraw()
        self.app.say("Restored %d file(s), settings included. Anything that "
                     "was here was kept alongside, renamed. A different app "
                     "theme shows after a restart." % restored, GREEN)
        self.destroy()

    def test_discord(self):
        """Post one message with what is in the box now, saved or not."""
        entry = self.fields.get("discord_webhook")
        hook = entry.get().strip() if entry is not None else ""
        if not hook:
            return self.say("Paste the webhook URL first.", AMBER)
        if not EDO.discord_hook_ok(hook):
            return self.say("That is not a Discord webhook address.", RED)
        payload = EDO.discord_message(
            "EDSMT is connected",
            [("CMDR", getattr(getattr(self.app, "watcher", None), "cmdr", "") or "")],
            description="Finds and Rhino sessions will be posted here.")
        self.app.worker.submit(EDO.DISCORD_TEST_TAG,
                               lambda: json.dumps(EDO.discord_post(hook, payload)))
        self.say("Sent a test message - look in the channel.", GREEN)

    def restore_settings_now(self):
        """Put the picked dated copy of the settings back, and wear it."""
        copies = attr(self, "_history", None) or []
        if not copies:
            return self.say("No earlier settings are saved yet - EDSMT keeps "
                            "them from 1.10034 on, whenever they change.", AMBER)
        try:
            picked = self.history_box.get()
        except Exception:
            picked = ""
        labels = [settings_copy_label(when, path) for when, path in copies]
        when, path = copies[labels.index(picked) if picked in labels else 0]
        try:
            restore_settings_copy(path)
        except Exception as problem:
            return self.say("Could not put those settings back: %s" % problem,
                            RED)
        self.app.apply_settings(load_settings())
        self.app.redraw()
        self.app.say("Settings from %s are back - overlay, layout, keys and "
                     "the rest. The ones you had are kept beside them. A "
                     "different app theme shows after a restart."
                     % time.strftime("%d %b %H:%M", time.localtime(when)), GREEN)
        self.destroy()

    def open_import_window(self):
        try:
            self.app.open_import()
        except Exception as problem:
            self.say("Could not open the importer: %s" % problem, RED)

    def open_filter_window(self):
        try:
            self.app.open_map_filter()
        except Exception as problem:
            self.say("Could not open the filters: %s" % problem, RED)

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

    def open_pictures_folder(self):
        folder = MI.pictures_dir(DATA_DIR)
        try:
            os.makedirs(folder, exist_ok=True)
            if os.name == "nt":
                os.startfile(folder)                      # noqa: S606
            else:
                import subprocess
                subprocess.Popen(["xdg-open", folder])
            self.say(folder)
        except Exception:
            self.say(folder, AMBER)

    def make_support_bundle(self):
        """One zip for a bug report: no secrets in it, and its folder opened."""
        path, problem = "", None
        for folder in (os.path.join(documents_dir(), "EDSMT support"),
                       os.path.join(DATA_DIR, "support")):
            try:
                path = SB.make_bundle(folder, DATA_DIR, dict(self.app.settings),
                                      APP_VERSION, build_kind())
                break
            except OSError as caught:
                problem = caught
        if not path:
            return self.say("Could not write the support bundle: %s" % problem, RED)
        SB.open_folder(path)
        return self.say("Support bundle written: %s - no keys, tokens or "
                        "webhooks are in it." % path, GREEN)

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

ABOUT_LINE = ("The Radio Raxxla surface-mining companion for the Rhino. "
              "Free, and every find goes on one community map.")


def about_text():
    """Settings > About EDSMT: which build, whose, and the small print."""
    return ("EDSMT %s  -  radioraxxla.com/EDSMT\n"
            "Copyright (C) 2026 Radio Raxxla. GPL-3.0-only - the source is on "
            "GitHub at TheAnnouncer/EDSMT.\n"
            "The Rhino: screenshot by CMDR TheAnnouncer. Elite Dangerous and "
            "the Rhino are (C) Frontier Developments plc. EDSMT is not "
            "affiliated with Frontier Developments." % APP_VERSION)


class WelcomeWindow(ctk.CTkToplevel):
    """What happens to a find, said once, on first run.

    Every commander running EDSMT is a surveyor. Surface deposits are not
    ring hotspots - nobody has mapped them, there is no third-party database
    to look them up in, and one person mapping alone will never cover a
    galaxy. So every find goes on the community map with the name of the
    commander who found it, and this says so plainly before the first one
    does. Since 1.10036 there is no choice to make here - one button.
    """

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("EDSMT - The community map")
        # The Rhino across the top, when the picture is there to show.
        self._picture = picture(WELCOME_PICTURE, self)
        self.geometry("%dx%d" % (WELCOME_SIZE if self._picture is not None
                                 else WELCOME_SIZE_PLAIN))
        self.configure(fg_color=VOID)
        self.transient(app)
        self.resizable(False, False)

        body = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        body.pack(fill="both", expand=True, padx=12, pady=12)
        bracket(body, colour=ORANGE)
        if self._picture is not None:
            tk.Label(body, image=self._picture, bg=PANEL, bd=0,
                     highlightthickness=0).pack(padx=16, pady=(16, 0))

        ctk.CTkLabel(body, text="One map, everybody's", font=F_TITLE,
                     text_color=ORANGE, anchor="w").pack(fill="x", padx=16, pady=(16, 2))
        ctk.CTkLabel(body, anchor="w", justify="left", text_color=TEXT,
                     font=F_READOUT, wraplength=490,
                     text="Every deposit you mark goes on the community map "
                          "with your CMDR name on it, and every deposit anybody "
                          "else marks comes back to you under Find and on the "
                          "map. One commander cannot cover a galaxy; a few "
                          "thousand can.").pack(fill="x", padx=16, pady=(6, 10))

        hud_header(body, "What gets sent", padx=16, pady=(6, 4))
        ctk.CTkLabel(body, anchor="w", justify="left", text_color=DIM,
                     font=F_BODY, wraplength=490,
                     text="System, body, commodity, position and how rich it "
                          "was, and the market prices you open.\n"
                          "Not your notes, not your sessions, not your "
                          "settings, not anything else on this "
                          "machine.").pack(fill="x", padx=16, pady=(0, 10))

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(4, 12))
        tip(ctk.CTkButton(row, text="Let's go", width=190, height=40,
                      font=F_SECTION, **BTN_PRIMARY,
                      command=lambda: self.answer(True)),
            "Your finds go on the community map with your CMDR name on them.").pack(side="left")

        try:
            self.grab_set()
        except Exception:
            pass

    def answer(self, wanted):
        try:
            self.app.set_name_credit(wanted)
        finally:
            self.destroy()
            # The first question answered, the window is shown round.
            try:
                self.app.after(500, self.app.start_tour)
            except Exception:
                pass


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
        tip(ctk.CTkButton(buttons, text="Save", width=110, height=32,
                      font=F_STRONG, **BTN_PRIMARY,
                      command=self.save), "Keeps the change.").pack(side="left", padx=(0, 8))
        self.delete_button = tip(ctk.CTkButton(buttons, text="Delete", width=110,
                                           height=32, font=F_STRONG,
                                           **BTN_DANGER,
                                           command=self.remove), "Forgets this signal. Its deposits stay on the map. Press twice.")
        self.delete_button.pack(side="left", padx=8)
        tip(ctk.CTkButton(buttons, text="Cancel", width=90, height=32,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.destroy), "Closes without changing anything.").pack(side="right")

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
        self.number = tip(ctk.CTkComboBox(number_row, values=app.signal_choices(),
                                      font=F_BODY, height=30, **BOX), "The signal number this really is.")
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


class RigEditWindow(ctk.CTkToplevel):
    """One rig, opened by double-clicking its square on the map (1.10034):
    what it is mining, put right, or the rig picked up."""

    def __init__(self, app, rig):
        super().__init__(app)
        self.app = app
        self.rig = rig
        label = app.rig_label(rig)
        self.title("EDSMT - Rig %s" % label)
        self.configure(fg_color=VOID)
        self.transient(app)
        ctk.CTkLabel(self, text="RIG %s" % label, font=F_STRONG,
                     text_color=ORANGE, anchor="w").pack(fill="x", padx=14,
                                                         pady=(12, 4))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row, text="Commodity", width=90, anchor="w", font=F_BODY,
                     text_color=DIM).pack(side="left")
        self.commodity = tip(ctk.CTkComboBox(
            row, values=list(SV.KNOWN_COMMODITIES), font=F_BODY, height=30,
            width=220, **BOX), "What this rig is mining.")
        self.commodity.set(str(rig.get("commodity") or ""))
        self.commodity.pack(side="left", fill="x", expand=True)
        Suggest(self.commodity, list(SV.KNOWN_COMMODITIES))
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=12, pady=(8, 12))
        tip(ctk.CTkButton(buttons, text="Save", width=100, height=32,
                          font=F_STRONG, **BTN_PRIMARY, command=self.save),
            "Keeps the commodity for this rig.").pack(side="left", padx=(0, 8))
        tip(ctk.CTkButton(buttons, text="Pick it up", width=110, height=32,
                          font=F_STRONG, **BTN_DANGER, command=self.pick_up),
            "Takes this rig off the map, as its AltGr key does.").pack(side="left")
        tip(ctk.CTkButton(buttons, text="Close", width=90, height=32,
                          font=F_STRONG, **BTN_SECONDARY, command=self.destroy),
            "Closes without changing anything.").pack(side="right")

    def save(self):
        self.app.set_rig_commodity(self.rig, self.commodity.get())
        self.destroy()

    def pick_up(self):
        self.app.pick_up_rig(self.rig)
        self.destroy()


# What the distance box in FROM RANGE can be read in.
RANGE_UNITS = ["auto", "m", "km"]


class RangeMarkWindow(ctk.CTkToplevel):
    """FROM RANGE (1.10035, #197): a deposit you can see, marked where it is.

    A bearing and a distance from where the Rhino is now. What the deposit is
    - commodity, rigs, amount, density - is the boxes on the rail, as for MARK
    DEPOSIT. The place is worked out across the body's own curve, and the
    deposit is marked "placed from range": it stays on this machine until MARK
    or UPDATE at the spot puts it exactly where it is."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("EDSMT - Mark from range")
        self.configure(fg_color=VOID)
        self.transient(app)
        self.status = ctk.CTkLabel(self, text="", font=F_READOUT,
                                   text_color=DIM, anchor="w", wraplength=400,
                                   justify="left")
        self.status.pack(side="bottom", fill="x", padx=14, pady=(0, 10))
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(side="bottom", fill="x", padx=12, pady=(0, 6))
        tip(ctk.CTkButton(buttons, text="Mark it", width=110, height=32,
                          font=F_STRONG, **BTN_PRIMARY, command=self.place),
            "Marks the deposit that far away on that bearing, using the "
            "boxes on the left.").pack(side="left", padx=(0, 8))
        tip(ctk.CTkButton(buttons, text="Close", width=90, height=32,
                          font=F_STRONG, **BTN_SECONDARY, command=self.destroy),
            "Closes without marking anything.").pack(side="right")
        ctk.CTkLabel(self, text="MARK FROM RANGE", font=F_STRONG,
                     text_color=ORANGE, anchor="w").pack(fill="x", padx=14,
                                                         pady=(12, 2))
        self.summary = ctk.CTkLabel(self, text=self.boxes_words(), font=F_SMALL,
                                    text_color=DIM, anchor="w", wraplength=400,
                                    justify="left")
        self.summary.pack(fill="x", padx=14, pady=(0, 6))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row, text="Bearing", width=90, anchor="w", font=F_BODY,
                     text_color=TEXT).pack(side="left")
        self.bearing = tip(ctk.CTkEntry(
            row, placeholder_text="degrees: 0 is north, 90 east", height=30,
            font=F_BODY, **ENTRY),
            "Which way the deposit is from the Rhino, in degrees: 0 north, "
            "90 east, 180 south, 270 west.")
        self.bearing.pack(side="left", fill="x", expand=True)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row, text="Distance", width=90, anchor="w", font=F_BODY,
                     text_color=TEXT).pack(side="left")
        self.unit = tip(ctk.CTkComboBox(row, values=RANGE_UNITS, width=84,
                                        font=F_BODY, height=30, **BOX),
                        "m or km. Auto reads a number under 20 as km and "
                        "anything else as metres; a unit typed with the "
                        "number wins.")
        self.unit.set(RANGE_UNITS[0])
        self.unit.pack(side="right", padx=(6, 0))
        self.distance = tip(ctk.CTkEntry(
            row, placeholder_text="850 or 1.2 km, up to %s"
            % CT.distance_words(CT.MAX_RANGE_M), height=30, font=F_BODY,
            **ENTRY), "How far away it is, from the scanner.")
        self.distance.pack(side="left", fill="x", expand=True)
        chain_tab([self.bearing, self.distance])
        self.bind("<Return>", lambda _event: self.place())
        fit_to_content(self, 440, 260)
        self.bearing.focus_set()

    def boxes_words(self):
        """What the boxes on the rail hold, as one line."""
        have = IM.boxes(self.app)
        bits = [have["commodity"],
                "%s rigs" % have["rigs"] if have["rigs"] else "",
                have["amount"], have["density"]]
        said = ", ".join(bit for bit in bits if bit)
        return ("Uses the boxes on the left: %s." % said) if said else \
            "Fill in the boxes on the left first: commodity, rigs, amount, density."

    def place(self):
        bearing = CT.parse_bearing(self.bearing.get())
        if bearing is None:
            return self.say("The bearing is 0 to 359 degrees - 0 is north, "
                            "90 east.", RED)
        metres = CT.parse_distance(self.distance.get(), self.unit.get())
        if metres is None:
            return self.say("The distance is 850, 850 m or 1.2 km, up to %s."
                            % CT.distance_words(CT.MAX_RANGE_M), RED)
        if self.app.mark_from_range(bearing, metres):
            self.destroy()
        else:
            self.say((attr(self.app, "_last_said", None) or ("",))[0], AMBER)

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
        tip(ctk.CTkButton(buttons, text="Save", width=110, height=32,
                      font=F_STRONG, **BTN_PRIMARY,
                      command=self.save), "Keeps the change, and sends the correction to the community map.").pack(side="left", padx=(0, 8))
        self.delete_button = tip(ctk.CTkButton(buttons, text="Delete", width=110,
                                           height=32, font=F_STRONG,
                                           **BTN_DANGER,
                                           command=self.remove), "Deletes this deposit. Press twice.")
        self.delete_button.pack(side="left", padx=8)
        tip(ctk.CTkButton(buttons, text="Cancel", width=90, height=32,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.destroy), "Closes without changing anything.").pack(side="right")

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
        box = tip(ctk.CTkComboBox(row, values=offered, font=F_BODY,
                              height=30, **BOX), "Pick from the list or type - the list follows what you type.")
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
# A ticked row in a multi-pick list: the mark. Its row is GREEN on SWEPT,
# which every theme defines.
TICK_MARK = "\u2713"


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

    `multi` makes it a list you tick rather than pick from (#188): a click
    adds a commodity or takes it off again and the list STAYS OPEN for the
    next one, the box reads "Monazite, Bastnasite", and `none` - "Any" -
    clears the lot. Typing filters on whatever follows the last comma, and
    Enter ticks the highlighted one. The box's own arrow list ticks too.
    """

    def __init__(self, box, source, on_pick=None, filter_typing=True,
                 multi=False, none="Any"):
        self.box = box
        self.source = source
        self.on_pick = on_pick
        self.filter_typing = filter_typing
        self.multi = bool(multi)
        self.none = none
        self.popup = None
        self.listbox = None
        self._hide_job = None
        # What each row of the list is, so a row drawn as "[x] Ruby" is
        # still picked as "Ruby".
        self._shown = []
        # The ticked names as they stood after the last change - what the
        # box's own arrow list toggles against, since the toolkit has
        # already overwritten the box by the time it says what was picked.
        self._ticked = []
        # Whether the commander has typed or arrowed in this box since
        # arriving in it. Until they have, the list shows everything and
        # Tab changes nothing - tabbing THROUGH a box must never fill it.
        self._engaged = False
        self._hushed = False
        # The toolkit's box keeps its real text field as _entry. Anything
        # without a working one - a plain entry - is its own text field.
        entry = getattr(box, "_entry", None)
        self.entry = entry if callable(getattr(entry, "bind", None)) else box
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
        if self.multi:
            self._ticked = self.picked()
            # The toolkit's arrow list replaces the box with what was picked
            # and then calls the box's command. Put in front of that
            # command, the pick becomes a tick added to (or taken off) what
            # was already there - and whatever the command did before still
            # runs, with the whole list.
            try:
                before = box.cget("command")
            except Exception:
                before = None

            def ticked_from_arrow(value, before=before):
                self._ticked = toggle_pick(self._ticked, value, self.none)
                self._write(self._ticked)
                if before is not None:
                    try:
                        before(self.box.get())
                    except Exception:
                        pass
                elif self.on_pick is not None:
                    try:
                        self.on_pick(self.box.get())
                    except Exception:
                        pass
            try:
                box.configure(command=ticked_from_arrow)
            except Exception:
                pass

    # -- what to show ------------------------------------------------------

    def choices(self):
        typed = self.text() if (self._engaged and self.filter_typing) else ""
        if self.multi:
            typed = self.fragment() if typed else ""
        try:
            if callable(self.source):
                names = list(self.source(typed))
            else:
                names = list(self.source)
        except Exception:
            names = []
        if typed and not callable(self.source):
            names = SV.matches(names, typed)
        if self.multi and typed and not SV.fold(self.none).startswith(SV.fold(typed)):
            # A word being typed that matches nothing must leave nothing to
            # take - with "Any" still in the list, Enter on a typo cleared
            # every tick in the box.
            names = [n for n in names if str(n).strip() != self.none]
        # A blank line in a list of choices is a way of saying "none"; it
        # stays selectable in the box but is noise in a suggestion list.
        return [n for n in names if str(n).strip()]

    def text(self):
        try:
            return self.box.get().strip()
        except Exception:
            return ""

    # -- ticking several (#188) ----------------------------------------------

    def known(self):
        """Every name the list can offer, unfiltered."""
        try:
            names = list(self.source("")) if callable(self.source) \
                else list(self.source)
        except Exception:
            names = []
        return [str(n).strip() for n in names
                if str(n).strip() and str(n).strip() != self.none]

    def fragment(self):
        """What is being typed now: whatever follows the last comma."""
        text = self.text()
        if text == self.none:
            return ""
        return text.rsplit(",", 1)[-1].strip()

    def picked(self):
        """The names ticked in the box, in the order they were ticked."""
        if not self.multi:
            text = self.text()
            return [] if text in ("", self.none) else [text]
        return parse_picks(self.text(), self.known(), self.none)

    def _write(self, names):
        try:
            self.box.set(pick_text(names, self.none))
        except Exception:
            pass

    def tidy(self):
        """Put the box back into its own words: "Ruby, Sapphire", or Any.

        A half-typed name that matches nothing is not kept - it would go
        to the server as a commodity nobody has heard of and empty the
        table without saying why."""
        if not self.multi:
            return
        self._ticked = self.picked()
        self._write(self._ticked)

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
            self._shown = [str(name).strip() for name in names]
            ticked = [SV.fold(n) for n in self.picked()] if self.multi else []
            for name in self._shown:
                if not self.multi:
                    self.listbox.insert("end", " " + name)
                elif name == self.none:
                    self.listbox.insert("end", " %s - clear" % name)
                elif SV.fold(name) in ticked:
                    # A tick, in green, on its own colour (1.10035): "[x]"
                    # beside "[ ]" read as two empty boxes at a glance.
                    self.listbox.insert("end", " %s %s" % (TICK_MARK, name))
                    self.listbox.itemconfig("end", fg=GREEN, bg=SWEPT)
                else:
                    self.listbox.insert("end", "    %s" % name)
            typed = self.fragment() if self.multi else self.text()
            chosen = 0
            for index, name in enumerate(self._shown):
                if name == typed or (self.multi and typed
                                     and SV.fold(name).startswith(SV.fold(typed))):
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
        # The window moving would leave the list floating where it was, and
        # a click anywhere else in it means the list is not wanted.
        try:
            top.bind("<Configure>", lambda _e: self.hide(), add="+")
            top.bind("<Button-1>", self._clicked_elsewhere, add="+")
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
        if self.multi:
            name = str(name).strip()
            if self._engaged and self.fragment():
                # Typed, then taken: "Ruby, sapph" and Enter on Sapphire
                # ADDS Sapphire to the Ruby. The half-typed word is the
                # thing being chosen, so it must not count as already
                # ticked - or Enter would take it straight off again.
                text = self.text()
                head = text.rsplit(",", 1)[0] if "," in text else ""
                ticked = parse_picks(head, self.known(), self.none)
                if name == self.none:
                    ticked = []
                elif SV.fold(name) not in [SV.fold(n) for n in ticked]:
                    ticked.append(name)
            else:
                # Clicked: tick it, or untick it if it was ticked.
                ticked = toggle_pick(self.picked(), name, self.none)
            self._ticked = ticked
            self._write(self._ticked)
            self._engaged = False
            if self.visible():
                self.show()
            if self.on_pick is not None:
                try:
                    self.on_pick(self.text())
                except Exception:
                    pass
            return
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

    def _name_at(self, index):
        """The name on row `index` of the list, without its tick box."""
        try:
            return self._shown[int(index)]
        except (IndexError, TypeError, ValueError):
            try:
                return self.listbox.get(index).strip()
            except Exception:
                return None

    def highlighted(self):
        if not self.visible():
            return None
        try:
            chosen = self.listbox.curselection()
            if chosen:
                return self._name_at(chosen[0])
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
        # A second click in a box whose list is already open shuts it
        # (1.10034: the list would not go away). This runs before the click
        # moves the keyboard, so "already open" means open before the click.
        try:
            already = self.visible() and self.box.focus_get() is self.entry
        except Exception:
            already = False
        if already:
            self._hushed = False
            return self.hide()
        self.box.after(1, self.show)

    def _clicked_elsewhere(self, event=None):
        """A click anywhere else in the window shuts the list. Clicking the
        map or a panel never takes the keyboard, so the box never heard it
        had lost it and the list stayed open over everything."""
        if getattr(event, "widget", None) is self.entry:
            return
        if self.visible():
            self._cancel_hide()
            self.hide()

    def _focus_out(self, _event=None):
        # Late, so a click on the list lands before the list goes away.
        self._cancel_hide()
        try:
            self._hide_job = self.box.after(180, self._left)
        except Exception:
            self._left()

    def _left(self):
        """The keyboard has gone elsewhere: shut the list, tidy the box."""
        self._hide_job = None
        self.hide()
        if self.multi:
            try:
                focus = self.box.focus_get()
            except Exception:
                focus = None
            if focus is not self.entry:
                self.tidy()

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
        if self.multi:
            self._ticked = self.picked()
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
        if self.multi:
            # Ticked only if something was being typed for it - tabbing
            # through must never tick or untick anything - and only ever
            # added, never taken off, by the key that means "move on".
            if self._engaged and name is not None and self.fragment() \
                    and name != self.none \
                    and SV.fold(name) not in [SV.fold(n) for n in self.picked()]:
                self.pick(name)
            self.hide()
            self.tidy()
            return None
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
            name = self._name_at(index)
        except Exception:
            return
        if name is None:
            return
        if self.multi:
            # Ticked, and the list stays where it is for the next one. The
            # keyboard goes back to the box WITHOUT the hush, so the focus
            # coming back re-opens it rather than shutting it.
            self.pick(name)
            self._cancel_hide()
            try:
                self.entry.focus_set()
            except Exception:
                pass
            self.box.after(1, self.show)
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


def parse_picks(text, known, none="Any"):
    """The names ticked in a multi-pick box, from what the box says.

    "Ruby, sapphire ,  Any" -> ["Ruby", "Sapphire"]. Each part is matched
    loosely to a known name - the spelling in the list wins - and a part
    that is the start of exactly one known name is taken as that name, so
    "Mona" is Monazite. A part that matches nothing, or several, is left
    out. "Any" on its own, or nothing, is no names at all.
    """
    known = [str(k).strip() for k in known if str(k).strip()]
    by_fold = {SV.fold(k): k for k in known}
    names = []
    for part in str(text or "").split(","):
        part = part.strip()
        if not part or part == none:
            continue
        name = by_fold.get(SV.fold(part))
        if name is None:
            starts = [k for k in known if SV.fold(k).startswith(SV.fold(part))]
            name = starts[0] if len(starts) == 1 else None
        if name is not None and name not in names:
            names.append(name)
    return names


def pick_text(names, none="Any"):
    """What a multi-pick box says for these names."""
    return ", ".join(names) if names else none


def toggle_pick(names, name, none="Any"):
    """Tick `name`, or untick it if it was ticked. `none` clears them all."""
    name = str(name or "").strip()
    if not name or name == none:
        return []
    folded = SV.fold(name)
    if any(SV.fold(n) == folded for n in names):
        return [n for n in names if SV.fold(n) != folded]
    return list(names) + [name]


def picks_of(box, none="Any"):
    """The names chosen in a commodity box, one or several, as a list.

    A box with a multi-pick list says so; any other box is one name or
    none, so a caller asks every box the same way."""
    suggest = getattr(box, "suggest", None)
    if suggest is not None and getattr(suggest, "multi", False):
        return suggest.picked()
    try:
        text = box.get().strip()
    except Exception:
        return []
    return [] if text in ("", none) else [text]


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


def cell_full(cell):
    """A table cell's whole text: its fourth part, when the cell shows a
    short form of a sentence (1.10038), else what it shows. What Copy
    takes."""
    if len(cell) > 3 and cell[3]:
        return str(cell[3])
    return str(cell[0])


def cell_label(table, index, column, text, colour=None, wrap=None, full=None):
    """One table cell: a plain Tk label, never the toolkit's. `full`, when
    it says more than `text`, is the cell's tooltip."""
    label = tk.Label(table, text=text, font=F_SMALL, fg=colour or TEXT, bg=PANEL,
                     justify="left", anchor="w", wraplength=wrap or CELL_WRAP,
                     bd=0)
    label.grid(row=index, column=DATA_COLUMN_0 + column, padx=8, pady=2, sticky="w")
    if full and str(full) != str(text):
        tip(label, full, always=True)
    return label


# A scrollbar decision settles within this many rounds, and a bar shown and
# hidden SCROLL_FLIPS times inside SCROLL_FLIP_S stays shown (1.10037).
SCROLL_ROUNDS, SCROLL_FLIPS, SCROLL_FLIP_S, SCROLL_RESIZE_PX = 3, 3, 1.5, 40


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
            # Resized by more than a scrollbar's own width: the commander
            # changed the window, not the bars, so a bar kept showing may go.
            width = int(self.canvas.winfo_width())
            if abs(width - getattr(self, "_settled_width", width)) > SCROLL_RESIZE_PX:
                for bar in (self.vbar, self.hbar):
                    ScrollTable.settle(bar)
            self._settled_width = width
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
        with nothing to scroll to.

        1.10037: never inside itself, and never for ever. The toolkit's
        set() redraws at once, and that redraw reports the scroll position
        straight back here. At some window sizes the answer flips every
        time - the bar is needed only while it is hidden - so each decision
        started the next one from inside itself, until Windows ran out of
        stack ("the box flashes, then it hangs, then crashes", the Find tab
        at 1240 x 780). A report that comes in during a decision is settled
        after it, at most three rounds, and a bar that cannot make up its
        mind stays shown."""
        if getattr(bar, "_edsmt_busy", False):
            bar._edsmt_pending = (low, high)
            return
        bar._edsmt_busy = True
        try:
            rounds, wanted = 0, False
            while True:
                bar._edsmt_pending = None
                bar.set(low, high)
                needed = not (float(low) <= 0.0 and float(high) >= 1.0)
                wanted = wanted or needed
                ScrollTable._place_bar(bar, needed, place)
                pending = getattr(bar, "_edsmt_pending", None)
                rounds += 1
                if pending is None:
                    break
                if rounds >= SCROLL_ROUNDS:
                    if wanted:
                        bar._edsmt_sticky = True
                        ScrollTable._place_bar(bar, True, place)
                    break
                low, high = pending
        except Exception:
            pass
        finally:
            bar._edsmt_busy = False
            bar._edsmt_pending = None

    @staticmethod
    def _place_bar(bar, needed, place):
        """Show or hide one bar, counting the changes. Three in
        SCROLL_FLIP_S and it stays shown: an unused bar is harmless, a
        flashing one is not."""
        now = time.monotonic()
        flips = [t for t in getattr(bar, "_edsmt_flips", ()) if now - t < SCROLL_FLIP_S]
        if not needed:
            if getattr(bar, "_edsmt_sticky", False):
                bar._edsmt_flips = flips
                return
            if bar.winfo_manager():
                bar.grid_forget()
                flips.append(now)
            # Forgotten between being gridded and being drawn, Tk can
            # leave it on screen anyway. Handing it to the placer and
            # straight back takes it off for certain.
            if bar.winfo_ismapped():
                bar.place(x=0, y=0)
                bar.place_forget()
        elif not bar.winfo_manager():
            bar.grid(**place)
            flips.append(now)
            if len(flips) >= SCROLL_FLIPS:
                bar._edsmt_sticky = True
        bar._edsmt_flips = flips

    @staticmethod
    def settle(bar):
        """Let a bar that was kept showing go again."""
        bar._edsmt_sticky = False
        bar._edsmt_flips = []

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


WHEEL_EVENTS = ("<MouseWheel>", "<Shift-MouseWheel>", "<Button-4>", "<Button-5>")


def unbind_one(widget, sequence, funcid):
    """Take one handler off a widget's binding and leave the rest.

    tkinter's own unbind(sequence, funcid) clears EVERY handler on that
    sequence (until Python 3.13), which would take the other tabs' wheels
    off the main window with it. Never raises."""
    try:
        script = str(widget.tk.call("bind", widget._w, sequence) or "")
        kept = "\n".join(line for line in script.split("\n") if funcid not in line)
        widget.tk.call("bind", widget._w, sequence, kept)
        widget.deletecommand(funcid)
        return True
    except Exception:
        return False


class ToolShell(ctk.CTkToplevel):
    """The window a tool sits in when tools open as separate windows."""

    def __init__(self, app):
        super().__init__(app)
        self.configure(fg_color=VOID)
        self.tool = None
        self._dying = False
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _close(self):
        tool = self.tool
        handler = getattr(tool, "_on_close", None) if tool is not None else None
        try:
            (handler or (tool.destroy if tool is not None else self.destroy))()
        except Exception:
            self.destroy()

    def destroy(self):
        if self._dying:
            return
        self._dying = True
        super().destroy()


class PoppedShell:
    """The window a tab becomes when Pop out is pressed (1.10038).

    Tk cannot move a widget into another window, so the tool is not moved
    and not rebuilt: its own frame is handed to the window manager (wm
    manage) and becomes a window, with everything typed, ticked and found
    still in it; wm forget makes it a frame again for Dock. This answers
    the window calls ToolWindow forwards to its shell, on that frame."""

    def __init__(self, tool):
        self.tool = tool
        self._dying = False

    def _wm(self, name, *args):
        return self.tool.tk.call("wm", name, self.tool._w, *args)

    def title(self, text=None):
        if text is None:
            return str(self._wm("title"))
        self._wm("title", str(text))
        return None

    def geometry(self, spec=None):
        if spec is None:
            return str(self._wm("geometry"))
        self._wm("geometry", spec)
        return ""

    def minsize(self, *args):
        return self._wm("minsize", *args)

    def maxsize(self, *args):
        return self._wm("maxsize", *args)

    def resizable(self, *args):
        return self._wm("resizable", *args)

    def transient(self, *args):
        return self._wm("transient", *[getattr(a, "_w", a) for a in args])

    def attributes(self, *args):
        return self._wm("attributes", *args)

    def protocol(self, name=None, func=None):
        if func is None:
            return str(self._wm("protocol", name))
        return self._wm("protocol", name, self.tool.register(func))

    def state(self, *args):
        return str(self._wm("state", *args))

    def wm_deiconify(self):
        return self._wm("deiconify")

    def withdraw(self):
        return self._wm("withdraw")

    def lift(self, *_args):
        return self.tool.tk.call("raise", self.tool._w)

    def focus_force(self):
        return self.tool.tk.call("focus", "-force", self.tool._w)

    def iconbitmap(self, *args):
        return self._wm("iconbitmap", *args)

    def manage(self):
        """The tool's frame handed to the window manager: a window from here."""
        return self._wm("manage")

    def forget(self):
        """And a plain frame again, for Dock."""
        return self._wm("forget")

    def _close(self):
        tool = self.tool
        handler = getattr(tool, "_on_close", None)
        try:
            (handler or tool.destroy)()
        except Exception:
            tool.destroy()

    def destroy(self):
        # The tool is the window; destroying it is the tool's own job.
        self._dying = True


POP_OUT_TIP = ("Opens this tool in a window of its own, as it stands. Dock on "
               "that window puts it back as a tab.")
DOCK_TIP = "Puts this window back as a tab of the main window, as it stands."


class ToolWindow(ctk.CTkFrame):
    """Find, My sites, Where to land, Earnings, Powerplay and Leaderboard
    (1.10036, #147): a tab of the main window, or - with the setting off -
    a window of its own, the way they all were before.

    The tools were written as windows, so this answers the window calls
    they make (title, geometry, transient, protocol, deiconify, lift,
    focus_force, a wheel bound on the window) in both forms: forwarded to
    the shell window, or turned into "show this tab". The tool code is the
    same either way."""

    def __init__(self, app, **kwargs):
        self._tool_app = app
        self._gone = False
        self._on_close = None
        self._tab_title = ""
        self._wheels = []
        self._wheel_funcs = []
        # The size and minimum the tool asks for as a window, kept while it
        # is a tab for the day it is popped out.
        self._asked_geometry = None
        self._asked_minsize = None
        docked = False
        try:
            docked = bool(app.tools_as_tabs())
        except Exception:
            docked = False
        self._shell = None if docked else ToolShell(app)
        super().__init__(app.tool_host() if docked else self._shell, fg_color=VOID,
                         corner_radius=0, **kwargs)
        # Pop out, at the right of the header (1.10038): this tab out to a
        # window of its own; on that window it reads Dock. Placed over the
        # header rather than in it, so every tool gets it without its own
        # header changing, and lifted again once the tool has built its
        # header under it. A tool opened as a window (the setting off) has
        # no tab to go back to, so it shows neither.
        self.dock_button = tip(ctk.CTkButton(
            self, text="Pop out", width=72, height=24, font=F_SMALL,
            **BTN_SECONDARY, command=self.toggle_dock), POP_OUT_TIP)
        self._paint_dock_button()
        self.after_idle(self._paint_dock_button)
        if self._shell is not None:
            self._shell.tool = self
            self.pack(fill="both", expand=True)
        else:
            app.dock_tool(self)

    @property
    def docked(self):
        return self._shell is None

    # -- the window calls, in both forms -----------------------------------

    def title(self, text=None):
        if self._shell is not None:
            return self._shell.title(text) if text is not None else self._shell.title()
        if text is None:
            return self._tab_title
        self._tab_title = str(text)
        return None

    def geometry(self, spec=None):
        if spec is not None and "x" in str(spec):
            self._asked_geometry = str(spec).split("+")[0].split("-")[0]
        if self._shell is not None:
            return self._shell.geometry(spec) if spec is not None else self._shell.geometry()
        if spec is None:
            return "%dx%d+0+0" % (self.winfo_width(), self.winfo_height())
        return ""

    wm_geometry = geometry

    def _shell_call(self, name, *args, **kwargs):
        if self._shell is None:
            return None
        return getattr(self._shell, name)(*args, **kwargs)

    def minsize(self, *args, **kwargs):
        if len(args) == 2:
            self._asked_minsize = args
        return self._shell_call("minsize", *args, **kwargs)

    def maxsize(self, *args, **kwargs):
        return self._shell_call("maxsize", *args, **kwargs)

    def resizable(self, *args, **kwargs):
        return self._shell_call("resizable", *args, **kwargs)

    def transient(self, *args, **kwargs):
        return self._shell_call("transient", *args, **kwargs)

    def attributes(self, *args, **kwargs):
        return self._shell_call("attributes", *args, **kwargs)

    def protocol(self, name=None, func=None):
        if name == "WM_DELETE_WINDOW":
            self._on_close = func
            return None
        return self._shell_call("protocol", name, func)

    def wm_deiconify(self):
        if self._shell is not None:
            return self._shell.wm_deiconify()
        return self._tool_app.show_tab(self)

    deiconify = wm_deiconify

    def withdraw(self):
        if self._shell is not None:
            return self._shell.withdraw()
        return self._tool_app.show_map()

    iconify = withdraw

    def lift(self, *args):
        if self._shell is not None:
            return self._shell.lift(*args)
        return self._tool_app.show_tab(self)

    tkraise = lift

    def focus_force(self):
        if self._shell is not None:
            return self._shell.focus_force()
        self._tool_app.show_tab(self)
        return super().focus_set()

    def state(self, *args):
        if self._shell is not None:
            return self._shell.state(*args)
        return "normal"

    def bind(self, sequence=None, func=None, add=None):
        # A wheel bound on a window reaches it from every widget inside; a
        # frame's does not. So the wheel goes on the window holding the tab
        # - the main window, or the shell. Each table's wheel handler only
        # acts while its table is on screen.
        if sequence in WHEEL_EVENTS and func is not None:
            self._wheel_funcs.append((sequence, func))
            return self._bind_wheel(sequence, func)
        return super().bind(sequence, func, add)

    def _bind_wheel(self, sequence, func):
        if isinstance(self._shell, PoppedShell):
            # Popped out, the frame is the window: events inside it reach
            # it, not the main window. Bound on the frame itself - the
            # toolkit's bind would put it on the frame's canvas.
            target, ident = self, tk.Misc.bind(self, sequence, func, add="+")
        else:
            target = self._shell if self._shell is not None else self._tool_app
            ident = target.bind(sequence, func, add="+")
        self._wheels.append((target, sequence, ident))
        return ident

    def _rebind_wheels(self):
        """The wheel handlers onto whichever window the tool is in now."""
        for target, sequence, ident in self._wheels:
            unbind_one(target, sequence, ident)
        self._wheels = []
        for sequence, func in list(self._wheel_funcs):
            try:
                self._bind_wheel(sequence, func)
            except Exception:
                pass

    # -- Pop out and Dock (1.10038) -----------------------------------------

    @property
    def popped(self):
        return isinstance(self._shell, PoppedShell)

    def toggle_dock(self):
        return self.dock() if self.popped else self.pop_out()

    def pop_out(self):
        """This tab out to a window of its own, exactly as it stands. The
        main window goes back to the map if this was the tab on show."""
        app = self._tool_app
        if self._shell is not None or self._gone:
            return False
        key = app.tool_key(self)
        was_active = attr(app, "active_tab", "map") == key
        shell = PoppedShell(self)
        try:
            self.grid_remove()
            shell.manage()
        except Exception:
            try:
                app.show_tab(self)
            except Exception:
                pass
            return False
        self._shell = shell
        shell.title(self._tab_title or APP_TITLE)
        size = self._asked_geometry or "%dx%d" % (max(self.winfo_width(), 400),
                                                  max(self.winfo_height(), 300))
        for call in ((shell.geometry, size),
                     (shell.minsize,) + tuple(self._asked_minsize or ()),
                     (shell.protocol, "WM_DELETE_WINDOW", shell._close)):
            try:
                if len(call) > 1:
                    call[0](*call[1:])
            except Exception:
                pass
        try:
            # The app's icon, where the platform lets a window be asked
            # for the one it wears; the toolkit's default otherwise.
            icon = app.tk.call("wm", "iconbitmap", app._w)
            if icon:
                shell.iconbitmap(icon)
        except Exception:
            pass
        self._rebind_wheels()
        self._paint_dock_button()
        if was_active:
            app.show_map()
        try:
            shell.lift()
        except Exception:
            pass
        return True

    def dock(self):
        """A popped-out window back as the tab on show, as it stands."""
        if not self.popped or self._gone:
            return False
        try:
            self._shell.forget()
        except Exception:
            return False
        self._shell._dying = True
        self._shell = None
        self._rebind_wheels()
        self._paint_dock_button()
        self._tool_app.show_tab(self)
        return True

    def _paint_dock_button(self):
        """Pop out on a tab, Dock on a popped-out window, nothing on a
        window opened as one; over the header's right end, above it."""
        button = attr(self, "dock_button", None)
        if button is None or self._gone:
            return
        try:
            if self._shell is not None and not self.popped:
                button.place_forget()
                return
            text, note = ("Dock", DOCK_TIP) if self.popped else ("Pop out", POP_OUT_TIP)
            button.configure(text=text)
            tooltip = getattr(button, "_edsmt_tooltip", None)
            if tooltip is not None:
                tooltip.text = note
            button.place(relx=1.0, anchor="ne", x=-26, y=22)
            button.lift()
        except Exception:
            pass

    def destroy(self):
        if self._gone:
            return
        self._gone = True
        for target, sequence, ident in self._wheels:
            unbind_one(target, sequence, ident)
        self._wheels = []
        shell = self._shell
        if shell is None or isinstance(shell, PoppedShell):
            try:
                self._tool_app.undock_tool(self)
            except Exception:
                pass
        super().destroy()
        if shell is not None and not shell._dying:
            try:
                shell.destroy()
            except Exception:
                pass


# Find's searches (1.10038): what each does, on its segment of the switch and
# on the status line when it is chosen. finder.MODES has their names.
FIND_MODE_TIPS = {
    "sites": "Sites - one patch, every commodity in it - best first.",
    "intact": "Sites ranked by how likely they are to still be there.",
    "deposits": "Every single deposit, with its position.",
    "prices": "Where to sell the ticked commodities, nearest first.",
    "bodies": "Bodies with mining locations near where you are, nearest first, "
              "with the odds for the first ticked commodity on that kind of ground.",
}
PLACE_WORDS = {
    # The system box narrows finds to a system or body; for prices it says
    # where to measure from.
    False: ("System / body", "narrow by system or body - e.g. Col 285 or Ega 1",
            "A system or body to narrow to - the start of the name is enough."),
    True: ("Near system", "near which system - blank is where you are",
           "Prices near this system. Blank: near the system you are in."),
}


def packed_with(widget):
    """The options a widget was packed with, as it was asked - before the
    toolkit scaled them - so it can be packed again exactly as it was."""
    call = getattr(widget, "_last_geometry_manager_call", None)
    if isinstance(call, dict) and isinstance(call.get("kwargs"), dict):
        return dict(call["kwargs"])
    try:
        info = dict(widget.pack_info())
    except Exception:
        return {}
    info.pop("in", None)
    return info


class FindWindow(ToolWindow):
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
        # The commodities the last search asked for, and the answers still
        # to come when Best sell prices was asked about several (#188).
        self._asked, self._sell_batch = [], None

        top = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        top.pack(fill="x", padx=12, pady=(12, 6))
        bracket(top, colour=ORANGE)
        hud_header(top, "Shared finds", padx=12, pady=(12, 4))
        # One line (1.10038): what each search does is on its tip and on the
        # status line when it is chosen. wraplength stays, so a narrow
        # window wraps it rather than clipping it at both ends.
        self.blurb = ctk.CTkLabel(
            top, text="Finds and prices shared by everyone running EDSMT. "
                      "VERIFIED: Radio Raxxla staff have stood on it.",
            font=F_BODY, text_color=DIM,
            wraplength=920, justify="left", anchor="w")
        self.blurb.pack(fill="x", anchor="w", padx=12, pady=(6, 6))
        # And it has to follow the window, or resizing reintroduces the clip.
        top.bind("<Configure>", self._rewrap)
        self._rewrap()

        # 1.10038: one search at a time, chosen here, with only its own
        # filters under it and one Search button. The five buttons it
        # replaces each ran a different search over the same wall of
        # filters, half of which did nothing for the one pressed.
        self.mode = None
        self._tables = {}
        self.mode_switch = tip(ctk.CTkSegmentedButton(
            top, values=[label for _key, label in FD.MODES], height=30,
            font=F_STRONG, fg_color=PANEL, selected_color=ORANGE,
            selected_hover_color=AMBER, unselected_color=STEEL,
            unselected_hover_color=RULE, text_color=TEXT,
            command=self._mode_picked),
            "The search the Search button runs. Only its own filters are "
            "shown; the others keep their values.")
        self.mode_switch.pack(anchor="w", padx=12, pady=(0, 8))
        segments = getattr(self.mode_switch, "_buttons_dict", None) or {}
        for key, label in FD.MODES:
            if label in segments:
                tip(segments[label], FIND_MODE_TIPS[key])

        # The filters, a row at a time. Which are on screen is the mode's
        # (finder.MODE_FILTERS); _show_filters puts them up.
        self.filter_box = ctk.CTkFrame(top, fg_color="transparent")
        self.filter_box.pack(fill="x", padx=12)
        self._labels = {}
        row = self._row_main = ctk.CTkFrame(self.filter_box, fg_color="transparent")
        row.pack(fill="x", pady=(0, 10))
        self._labels["commodity"] = ctk.CTkLabel(row, text="Commodity", font=F_BODY,
                                                 text_color=DIM)
        self._labels["commodity"].pack(side="left")
        # Several at once (#188): tick Monazite AND Bastnasite and every
        # search asks for either. Wider than one name needs, for two.
        self.commodity = tip(ctk.CTkComboBox(row, width=240, font=F_BODY, **BOX,
                                         values=["Any"] + list(SV.KNOWN_COMMODITIES)), "Tick one or several commodities; Any clears them. Or type them, comma separated, and press Enter.")
        self.commodity.set("Any")
        self.commodity.pack(side="left", padx=(6, 14))
        self._labels["min_rigs"] = ctk.CTkLabel(row, text="Min rigs", font=F_BODY,
                                                text_color=DIM)
        self._labels["min_rigs"].pack(side="left")
        self.min_rigs = tip(ctk.CTkComboBox(row, width=70, font=F_BODY, **BOX,
                                        values=[str(n) for n in range(0, 25)]), "Only sites or deposits with at least this many rigs.")
        self.min_rigs.set("0")
        self.min_rigs.pack(side="left", padx=(6, 14))
        self._labels["min_types"] = ctk.CTkLabel(row, text="Types in patch", font=F_BODY,
                                                 text_color=DIM)
        self._labels["min_types"].pack(side="left")
        self.min_types = tip(ctk.CTkComboBox(row, width=64, font=F_BODY, **BOX,
                                         values=["0", "1", "2", "3", "4", "5"]), "Only sites carrying at least this many different commodities.")
        self.min_types.set("0")
        self.min_types.pack(side="left", padx=(6, 14))
        self._labels["seen"] = ctk.CTkLabel(row, text="Seen within", font=F_BODY,
                                            text_color=DIM)
        self._labels["seen"].pack(side="left")
        self.max_age = tip(ctk.CTkComboBox(row, width=110, font=F_BODY, **BOX,
                                       values=["Any time", "7 days", "14 days",
                                               "30 days", "90 days"]), "Only finds reported this recently.")
        self.max_age.set("Any time")
        self.max_age.pack(side="left", padx=(6, 14))
        # The filter that makes the whole thing usable. Without it the top
        # of the list is whatever is best in 400 billion systems, which is
        # a place nobody is going.
        self._labels["within"] = ctk.CTkLabel(row, text="Within", font=F_BODY,
                                              text_color=DIM)
        self._labels["within"].pack(side="left")
        self.within = tip(ctk.CTkComboBox(row, width=110, font=F_BODY, **BOX,
                                      values=list(DISTANCE_CHOICES)), "Only finds this many light years from where you are.")
        self.within.set(DEFAULT_DISTANCE)
        self.within.pack(side="left", padx=6)

        # Second row, because eight filters on one line is how a window
        # ends up with controls off the right-hand edge at 1024 wide.
        #
        # Fixed-width things first, expanding thing last. The entry is the
        # only one allowed to grow, and packing it before the two toggles
        # would push them out of the window exactly the way the edit
        # button went missing off the signal rows.
        row2 = self._row_place = ctk.CTkFrame(self.filter_box, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 8))
        self._labels["place"] = ctk.CTkLabel(row2, text="System / body", font=F_BODY,
                                             text_color=DIM)
        self._labels["place"].pack(side="left")
        self.only_verified = ctk.BooleanVar(value=False)
        self.verified_box = tip(ctk.CTkCheckBox(row2, width=130, text="Verified only", variable=self.only_verified,
                        onvalue=True, offvalue=False, font=F_BODY,
                        checkbox_width=18, checkbox_height=18, border_width=2,
                        fg_color=ORANGE, hover_color=AMBER, text_color=DIM,
                        command=self._paint), "Only finds a Radio Raxxla staff member has stood on.")
        self.verified_box.pack(side="right", padx=(12, 0))
        # On by default. A site somebody has already stripped is not a
        # result, it is a wasted drive, and the server only hides them
        # from the site search - a deposit row can still be sitting on one.
        self.hide_worked = ctk.BooleanVar(value=True)
        self.hide_worked_box = tip(ctk.CTkCheckBox(row2, width=152, text="Hide worked-out", variable=self.hide_worked,
                        onvalue=True, offvalue=False, font=F_BODY,
                        checkbox_width=18, checkbox_height=18, border_width=2,
                        fg_color=ORANGE, hover_color=AMBER, text_color=DIM,
                        command=self._paint), "Leaves out sites somebody has reported stripped.")
        self.hide_worked_box.pack(side="right", padx=(12, 0))
        self.query = tip(ctk.CTkEntry(row2, font=F_BODY, height=30, **ENTRY,
                                  placeholder_text="narrow by system or body "
                                                   "- e.g. Col 285 or Ega 1"), "A system or body to narrow to - the start of the name is enough.")
        self.query.pack(side="left", fill="x", expand=True, padx=(6, 4))
        # Narrows what is already on screen as you type. No round trip, so
        # it is instant, and it goes out with the next search as well.
        self.query.bind("<KeyRelease>", lambda _e: self._paint())
        # Every filter opens its list on click or Tab, the commodity one
        # follows what is typed, and Tab walks them left to right.
        Suggest(self.commodity, self._commodity_choices, multi=True)
        for box in (self.min_rigs, self.min_types, self.max_age, self.within):
            try:
                Suggest(box, list(box.cget("values")))
            except Exception:
                pass

        # Mining bodies' own line: what the odds in its table rest on.
        row3 = self._row_note = ctk.CTkFrame(self.filter_box, fg_color="transparent")
        row3.pack(fill="x", pady=(0, 8))
        self.bodies_note = ctk.CTkLabel(
            row3, text="The odds are from what commanders have shared; one "
                       "resting on fewer than %d sites is shown in amber."
                       % GX.SMALL_SAMPLE,
            font=F_SMALL, text_color=DIM, anchor="w", justify="left")
        self.bodies_note.pack(side="left")

        # 1.10035: pad, price age, demand, price, station type, Powerplay
        # and the best five of each commodity. From goes on the first row,
        # beside Within: the two ends of one distance window.
        self._want_sort = None
        actions = ctk.CTkFrame(top, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(2, 10))
        self._filters = FindFilters(self, self.filter_box, lead=self._row_main,
                                    actions=actions)
        # Within is the far end of the distance window as well as the radius
        # a search is sent with: narrowing it narrows what is on screen at
        # once, From being the near end.
        self.within.configure(command=lambda _value: self._paint())
        if getattr(self.within, "suggest", None) is not None:
            self.within.suggest.on_pick = lambda _value: self._paint()

        # One primary action, then Reset and Saved; Copy all at the right.
        # The right-hand one goes down first. Pack order is claim order,
        # and a button packed last against the far edge is the one that
        # disappears when the window is dragged narrow.
        tip(ctk.CTkButton(actions, text="Copy all", width=100, height=32,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.copy_all), "Copies the table as text, ready to paste into Discord.").pack(side="right")
        self.search_button = tip(ctk.CTkButton(
            actions, text="Search", width=120, height=32, font=F_STRONG,
            **BTN_PRIMARY, command=self.search),
            "Runs the search chosen above with these filters. Enter in any box does the same.")
        self.search_button.pack(side="left", padx=(0, 8))
        tip(ctk.CTkButton(actions, text="Reset", width=80, height=32,
                          font=F_STRONG, **BTN_SECONDARY,
                          command=self._filters.reset),
            "Puts every filter back to how the window opens.").pack(side="left", padx=8)
        self._filters.saved.button.pack(side="left", padx=8)

        # Tab walks every filter on screen, left to right and row by row;
        # the ones out of sight are stepped over. Enter in any of them runs
        # the search - unless a list is open, where Enter takes its choice.
        f = self._filters
        boxes = [self.commodity, self.min_rigs, self.min_types, self.max_age,
                 f.far_box, self.within, self.query, f.pad_box, f.age_box,
                 f.price_box, f.demand_low, f.demand_high, f.station_box,
                 f.power_state_box, f.power_side_box, f.show_box]
        chain_tab(boxes)
        for box in boxes:
            for sequence in ("<Return>", "<KP_Enter>"):
                try:
                    box.bind(sequence, self._enter_key, add="+")
                except Exception:
                    pass
        self._layout = self._filter_layout()

        self.status = ctk.CTkLabel(self, text="", font=F_READOUT,
                                   text_color=DIM, anchor="w")
        self.status.pack(fill="x", padx=14, pady=(0, 4))
        self.scroller = ScrollTable(self)
        self.scroller.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.table = self.scroller.inner
        for sequence in ("<MouseWheel>", "<Shift-MouseWheel>",
                         "<Button-4>", "<Button-5>"):
            self.bind(sequence, self.scroller.wheel, add="+")
        # The search it was left on last time (1.10038) - written to the
        # settings the first time too, since the toolkit does not report a
        # press on the segment already up.
        self.set_mode(app.settings.get("find_mode"))
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

    # -- one search at a time (1.10038) ------------------------------------

    def _mode_picked(self, label):
        self.set_mode(label)

    def set_mode(self, mode, remember=True, table=True):
        """Show one search: its filters on screen, the others kept as they
        are but out of sight, and the table it last drew. `table` False
        leaves the table to the caller - an answer that is about to draw
        its own. Remembered in settings as find_mode."""
        mode = FD.mode_key(mode)
        switch = attr(self, "mode_switch")
        if switch is not None and switch.get() != FD.mode_label(mode):
            switch.set(FD.mode_label(mode))
        # Remembered first: pressing the segment already up counts as
        # choosing it, so it is the one Find opens on next time.
        settings = attr(self.app, "settings", None)
        if remember and isinstance(settings, dict) \
                and settings.get("find_mode") != mode:
            settings["find_mode"] = mode
            save_settings(settings)
        old = attr(self, "mode", None)
        if old == mode:
            return mode
        tables = attr(self, "_tables", None)
        if tables is None:
            tables = self._tables = {}
        if self._builder is not None:
            tables[FD.mode_of_kind(self._kind) or old] = self._table_state()
        self.mode = mode
        self._show_filters()
        state = tables.pop(mode, None)
        if not table:
            return mode
        if state is not None:
            self._put_table_state(state)
            self._paint()
        else:
            self._forget()
            self.say("%s Set the filters and press Search." % FIND_MODE_TIPS[mode])
        return mode

    def _table_state(self):
        return {"rows": self._rows, "headers": self._headers,
                "builder": self._builder, "empty": self._empty, "kind": self._kind,
                "sort": (self._sort_column, self._sort_reverse),
                "cut": attr(self, "_cut", False)}

    def _put_table_state(self, state):
        self._rows, self._headers = state["rows"], state["headers"]
        self._builder, self._empty, self._kind = state["builder"], state["empty"], state["kind"]
        self._sort_column, self._sort_reverse = state["sort"]
        self._cut = state["cut"]

    def _filter_layout(self):
        """The filter rows top to bottom, each with its widgets in packing
        order: (row, row's pack options, [(widget, filter, pack options)]).
        Read once, when everything is packed, so a mode can take widgets
        away and put them back exactly where they were."""
        f, labels = self._filters, self._labels
        rows = [(self._row_main, [
                    (labels["commodity"], "commodity"), (self.commodity, "commodity"),
                    (labels["min_rigs"], "min_rigs"), (self.min_rigs, "min_rigs"),
                    (labels["min_types"], "min_types"), (self.min_types, "min_types"),
                    (labels["seen"], "seen"), (self.max_age, "seen"),
                    (f.labels["from"], "from"), (f.far_box, "from"),
                    (labels["within"], "within"), (self.within, "within")]),
                # Fixed-width things first, the expanding box last: packed
                # the other way round it pushes the two toggles off the edge.
                (self._row_place, [
                    (labels["place"], "place"), (self.verified_box, "verified"),
                    (self.hide_worked_box, "hide_worked"), (self.query, "place")])]
        rows += list(zip(f.rows, f.parts))
        rows.append((self._row_note, [(self.bodies_note, "bodies_note")]))
        return [(row, packed_with(row),
                 [(widget, key, packed_with(widget)) for widget, key in items])
                for row, items in rows]

    def _show_filters(self):
        """Only the filters of the search on show. Packed again in their
        own order, every time, so nothing comes back in the wrong place."""
        mode = attr(self, "mode", None) or FD.DEFAULT_MODE
        wanted = set(FD.mode_filters(mode))
        if mode == "bodies":
            wanted.add("bodies_note")
        layout = attr(self, "_layout", None) or []
        for row, _row_pack, items in layout:
            for widget, _key, _pack in items:
                widget.pack_forget()
            row.pack_forget()
        for row, row_pack, items in layout:
            keep = [(widget, pack) for widget, key, pack in items if key in wanted]
            if not keep:
                continue
            row.pack(**row_pack)
            for widget, pack in keep:
                widget.pack(**pack)
        label, holder, hint = PLACE_WORDS[mode == "prices"]
        try:
            self._labels["place"].configure(text=label)
            self.query.configure(placeholder_text=holder)
            note = getattr(self.query, "_edsmt_tooltip", None)
            if note is not None:
                note.text = hint
        except Exception:
            pass

    def search(self):
        """The one Search button: the search chosen at the top."""
        mode = attr(self, "mode", None) or FD.DEFAULT_MODE
        return {"sites": self.search_sites, "intact": self.search_intact,
                "deposits": self.search_deposits, "prices": self.search_prices,
                "bodies": self.search_bodies}[mode]()

    def _enter_key(self, _event=None):
        self.search()
        return "break"

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
            self.say("Not connected to the community map - check Settings > Sharing.", AMBER)

    def _ready(self):
        """Searching is not sharing, and never asked for permission.

        This used to gate every button on the upload switch and then blame
        a URL that was already correct, so the one screen that shows what
        the map is worth was dark for anybody who had not opted in yet.
        """
        if self.app.community.can_read:
            return True
        self.say("Not connected to the community map - check Settings > Sharing.", AMBER)
        return False

    def _commodity_choices(self, typed=""):
        """The commodity list, server's additions included, filtered."""
        try:
            names = [n for n in self.commodity.cget("values") if n != "Any"]
        except Exception:
            names = list(SV.KNOWN_COMMODITIES)
        return ["Any"] + (SV.matches(names, typed) if typed else names)

    def _commodities(self):
        """The commodities ticked, as a list. None ticked is any."""
        return picks_of(self.commodity)

    def _commodity(self):
        """The same, as the server takes it: "Monazite,Bastnasite", or ""."""
        return ",".join(self._commodities())

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
            # Every page, not the first 500 (1.10036) - for a client that
            # knows how to ask for them.
            "every": True,
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

    def _here(self):
        """Where the commander is, for the distance column: measured from
        whether or not a radius was picked. None until the game has said."""
        try:
            return self.app.star_position()
        except Exception:
            return None

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
        self._asked = self._commodities()
        if not what.startswith("Looking up prices"):
            self._sell_batch = None
        try:
            sent = call()
        except Exception as exc:
            # A raise inside a Tk button command is swallowed by Tk's own
            # error handler, so the button silently does nothing at all.
            return self.say("Could not search: %s" % exc, RED)
        if not sent:
            return self.say("That request was not sent - not connected to the "
                            "community map. Check Settings > Sharing.", RED)
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
        here = here or self._here()
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
        here = here or self._here()
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
        here = here or self._here()
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
        names = self._commodities()
        if len(names) > 1:
            return self._sell_several(names, near, here, radius)
        self._sell_batch = None
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

    def _sell_several(self, names, near, here, radius):
        """Best sell prices for several commodities, as one table.

        The market index is asked about one commodity at a time and the
        server paces its calls to it, so these go a little apart - the same
        spacing the Earnings window uses for a hold - and each answer is
        added to the table as it lands rather than all held back for the
        slowest.
        """
        sell = self.app.community.sell
        self._sell_batch = {"want": len(names), "got": 0, "rows": [],
                            "names": list(names)}
        first = names[0]
        self._fire("Looking up prices for %d commodities%s" % (
                       len(names), self._scope()),
                   lambda: sell(commodity=first, near_system=near,
                                near=here, within_ly=radius))
        if attr(self, "_awaiting") is None:
            # Not sent. _fire has already said why.
            self._sell_batch = None
            return
        for index, name in enumerate(names[1:], start=1):
            self.after(index * QUOTE_GAP_MS,
                       lambda n=name: sell(commodity=n, near_system=near,
                                           near=here, within_ly=radius))

    def search_bodies(self):
        """Bodies with mining locations near where the commander is (1.10036,
        #200), within the window's distance - Anywhere being as far as the
        server goes - with the ground odds for the first ticked commodity
        (#133). The server takes one commodity for the odds."""
        try:
            chosen = DISTANCE_CHOICES.get(self.within.get(), 0)
        except Exception:
            chosen = 0
        within = min(chosen or GX.MOST_LY, GX.MOST_LY)
        near = self._here() or str(getattr(attr(self.app, "watcher"), "system", "")
                                   or "").strip()
        if not near:
            return self.say("The game has not said where you are yet - jump or "
                            "log in, then try again.", AMBER)
        names = self._commodities()
        call = self.app.community.mining_bodies
        self._fire("Looking for mining bodies within %d Ly" % within,
                   lambda: call(near=near, within_ly=within,
                                commodity=names[0] if names else "", tag=GX.TAG))

    def _bodies(self, data):
        """Draw a mining bodies answer, with its headline over it."""
        self._cut = False
        self._render(GX.rows(data), list(GX.HEADERS), self._body_row,
                     GX.headline(data), kind="bodies")
        self.say(GX.headline(data), GREEN if GX.tone(data) == "good" else AMBER)

    @staticmethod
    def _body_row(row):
        shades = {"good": GREEN, "warn": AMBER, "dim": DIM}
        return [(text, shades.get(key), sort) for text, key, sort in GX.cells(row)]

    def _batch_reply(self, rows, ok=True):
        """One answer of several. Returns everything so far, or None if
        there is no batch running."""
        batch = attr(self, "_sell_batch")
        if not batch:
            return None
        batch["got"] += 1
        if ok:
            batch["rows"].extend(rows)
        else:
            batch["failed"] = batch.get("failed", 0) + 1
        return batch["rows"]

    def _batch_note(self):
        """Say how far through several commodities the answers are."""
        batch = attr(self, "_sell_batch")
        if not batch:
            return
        if batch["got"] < batch["want"]:
            self.say("Prices for %d of %d commodities so far - the rest are "
                     "on their way." % (batch["got"], batch["want"]), AMBER)
        elif batch.get("failed"):
            self.say("%d of %d commodities could not be priced - the server "
                     "did not answer for them." % (batch["failed"],
                                                    batch["want"]), AMBER)

    def _older_server(self, data):
        """Several commodities asked for, and a server that cannot hear it.

        A server from before 1.10033 reads "Monazite,Bastnasite" as one
        commodity nobody has heard of and answers with nothing at all - which
        looks exactly like nobody having found either. A newer one says what
        it filtered on, so its silence on that is the tell."""
        asked = attr(self, "_asked") or []
        if len(asked) > 1 and isinstance(data, dict) \
                and "commodities" not in data:
            self.say("The community map has not been updated to search several "
                     "commodities at once yet - tick one for now.", AMBER)
            return True
        return False

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
        if tag == "remove":
            return self._removed(payload, ok)
        if not ok:
            # The commodity list is a courtesy nobody asked for. A server
            # that will not serve it must not wipe the results table or put
            # a red line over a dropdown that is working.
            if tag == "commodities":
                return
            # One commodity of several not answering is not the others'
            # problem: what has come back stays on screen.
            if tag == "sell" and self._batch_reply([], ok=False) is not None:
                return self._batch_note()
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
        if tag == GX.TAG:
            return self._bodies(data)
        if tag in ("sites", "intact", "search", "market") \
                and self._older_server(data):
            return self._forget()
        # Whether a paged search stopped before the end (1.10036). An older
        # server sends one page and no word either way: a full page from it
        # is still short.
        self._cut = (data.get("complete") is False if "complete" in data
                     else len(data.get("sites") or data.get("deposits") or []) >= SEARCH_LIMIT)
        if tag == "sites":
            self._render(data.get("sites") or [],
                         ["System", "Distance", "Body", "Signal", "Rigs",
                          "Types", "Last seen", "Found by", "Score"],
                         self._site_row,
                         "Nothing shared yet for that filter.", kind="sites")
        elif tag == "intact":
            self._render(data.get("sites") or [],
                         ["System", "Distance", "Body", "Signal",
                          "Still there", "Rigs", "Types", "Last seen",
                          "Found by"], self._intact_row,
                         "Nothing shared yet is confident enough to list.",
                         kind="intact")
        elif tag == "sell":
            rows = (data.get("market") or []) + (data.get("community") or [])
            so_far = self._batch_reply(rows)
            if so_far is not None:
                rows = list(so_far)
            if rows:
                self._render(self._nearest_best(rows),
                             ["Commodity", "Station", "System", "Distance",
                              "Sell", "Demand", "Seen", "Source"],
                             self._sell_row, "No prices matched.", kind="sell")
                self._batch_note()
            elif so_far is not None and \
                    self._sell_batch["got"] < self._sell_batch["want"]:
                self._batch_note()
            else:
                return self._published_prices()
        elif tag == "search":
            self._render(data.get("deposits") or [],
                         ["System", "Distance", "Body", "Signal",
                          "Commodity", "Rigs", "Density", "Last seen", "Lat",
                          "Long", "Found by"],
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
        # An answer brings its own search up with it (1.10038), so the
        # filters on screen are always the ones acting on the table.
        mode = FD.mode_of_kind(kind)
        if mode and attr(self, "mode", None) not in (None, mode):
            self.set_mode(mode, table=False)
        headers, builder = self._widen(headers, builder, kind)
        self._rows, self._headers = rows, list(headers)
        self._builder, self._empty, self._kind = builder, empty, kind
        # A fresh result set arrives in the server's own ranking, which is
        # the best default there is. Clicking a header opts out of it.
        self._sort_column, self._sort_reverse = None, False
        self._restore_sort()
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
            rows = self._sorted(self._visible())
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
            self._more_button = tip(ctk.CTkButton(
                self.table, text="Show %d more  (%d not drawn yet)"
                % (min(PAGE_ROWS, left), left),
                font=F_STRONG, **BTN_SECONDARY, height=30,
                command=self._draw_page), "Draws the next page of results.")
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
            tip(ctk.CTkButton(self.table, text=text, font=F_SMALL_B,
                          **BTN_HEADING, anchor="w", height=24, width=0,
                          command=lambda c=column: self.sort_by(c)), "Click to sort by this column; click again to turn it round.").grid(
                              row=0, column=DATA_COLUMN_0 + column,
                              padx=4, pady=4, sticky="w")
        # Asked of every row on screen, not just the first. A site row
        # with no system name would otherwise take the column away from
        # the twenty rows below it that do have one.
        staff = any(self._verifiable(row) or self._removable(row) for row in rows)
        if staff or any(self._copies(row) for row in rows):
            ctk.CTkLabel(self.table,
                         text="Copy / staff" if staff else "Copy",
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
        if self._removable(row):
            buttons.append(("remove", lambda r=row: self.remove_find(r), False))
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
        # that produced it would throw all of them away. The published
        # figures belong to Sell prices too (1.10038), so the same goes.
        if text and self._kind not in PRICE_KINDS + ("published",):
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

    def _visible(self):
        """The rows past every filter: the ones above, then 1.10035's."""
        kept = [row for row in self._rows if self._keep(row)]
        filters = attr(self, "_filters")
        return kept if filters is None else filters.narrow(kept, self._kind)

    def _widen(self, headers, builder, kind):
        """The result set's headers and row builder with the columns the
        1.10035 filters are about added (pad, type, price age, Powerplay)."""
        filters = attr(self, "_filters")
        if filters is None:
            return headers, builder
        return filters.widen(headers, builder, kind)

    def _restore_sort(self):
        """A loaded search's sort order, once, when the column exists."""
        want = attr(self, "_want_sort")
        self._want_sort = None
        if want and want[0] in self._headers:
            self._sort_column = self._headers.index(want[0])
            self._sort_reverse = bool(want[1])

    def _hidden_line(self, shown, total):
        """The sentence when filters hid rows: how many, and why."""
        filters = attr(self, "_filters")
        if filters is None:
            return ("%d of %d shown - %d hidden by your filters."
                    % (shown, total, total - shown))
        return FD.count_line(shown, total, filters.counts)

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

    def _removable(self, row):
        """Staff only (1.10034): a wrong find, or a wrong site, can be taken
        off the community map. The server checks the token anyway."""
        if self._kind not in FIND_KINDS:
            return False
        if not getattr(self.app.community, "can_verify", False):
            return False
        return bool(str(row.get("system") or "").strip()
                    and str(row.get("planet") or row.get("body") or "").strip())

    def remove_find(self, row, now=None):
        """Second press within REMOVE_CONFIRM_S takes it off the map: a find
        by its id, a site row the whole site."""
        call = getattr(self.app.community, "remove", None)
        if not callable(call):
            return self.say("This build cannot remove finds.", AMBER)
        system = str(row.get("system") or "").strip()
        planet = str(row.get("planet") or row.get("body") or "").strip()
        spot = str(row.get("spot") or "1").strip() or "1"
        deposit_id = row.get("id") if str(row.get("id") or "").isdigit() else None
        what = "%s %s signal %s" % (system, planet, spot)
        if deposit_id:
            what = "the %s find on %s" % (row.get("type") or row.get("commodity")
                                          or "unnamed", what)
        else:
            what = "the whole site %s" % what
        now = time.time() if now is None else now
        armed = attr(self, "_remove_armed", None)
        if not armed or armed[0] is not row or now - armed[1] > REMOVE_CONFIRM_S:
            self._remove_armed = (row, now)
            return self.say("Press remove again to take %s off the community "
                            "map." % what, AMBER)
        self._remove_armed = None
        self._removing = row
        self._fire("Removing %s" % what,
                   lambda: call(self._cmdr(), system, planet, spot,
                                int(deposit_id) if deposit_id else None))

    def _removed(self, message, ok=True):
        row = attr(self, "_removing")
        self._removing = None
        if not ok:
            return self.say("Could not remove it: %s" % message, RED)
        try:
            rows = attr(self, "_rows", None)
            if row is not None and isinstance(rows, list):
                rows[:] = [r for r in rows if r is not row]
                self._paint()
        except Exception:
            pass
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
            chosen = self._commodities()
            values = ["Any"] + sorted(set(list(SV.KNOWN_COMMODITIES) + wanted),
                                      key=SV.fold)
            self.commodity.configure(values=values)
            # Whatever was ticked stays ticked - several names are not one
            # of the values, and must not be mistaken for a stale one.
            kept = [n for n in chosen if n in values]
            self.commodity.set(pick_text(kept))
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
        rows = self._sorted(self._visible())
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
        if self._commodities():
            on.append("Commodity %s" % pick_text(self._commodities()))
        filters = attr(self, "_filters")
        # With the 1.10035 filters, Within is one of theirs and they list it.
        if filters is None and self.within.get() != NO_DISTANCE_LIMIT:
            on.append("Within %s" % self.within.get())
        if filters is not None:
            on.extend(filters.active())
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
        if len(self._commodities()) == 1:
            widen.append('tick another commodity, or set Commodity to "Any"')
        elif self._commodities():
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
            # Every page is fetched now (1.10036). Only a search that hit the
            # very top - tens of thousands - is short, and it says so.
            if attr(self, "_cut", False):
                return self.say("{:,} result(s) - the first {:,}; narrow it to "
                                "see past them.".format(total, total), AMBER)
            return self.say("{:,} result(s).".format(total), GREEN)
        self.say(self._hidden_line(shown, total), AMBER if shown else RED)

    # -- the rows themselves ---------------------------------------------

    def _site_row(self, row):
        age = row.get("age_days") or 0
        seen = ("today" if age < 1 else "yesterday" if age < 2
                else "%d days ago" % age)
        colour = GREEN if age <= 14 else (AMBER if age <= 45 else RED)
        return [(str(row.get("system", "")), None),
                # How far from where you are now (1.10034), when the server
                # knows where that system is. A blank is not a zero.
                self._distance(row),
                (str(row.get("planet", "") or row.get("body", "")), None),
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
        return [(str(row.get("system", "")), None), self._distance(row),
                (str(row.get("planet", "")), None),
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
        wanted = [SV.fold(n) for n in self._commodities()]
        names = SV.KNOWN_COMMODITIES
        if wanted:
            names = [n for n in names if SV.fold(n) in wanted] or names
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
        # Neutral words (1.10035), never the name the server was given.
        return self._price_row(row) + [(price_source(row.get("source")), DIM)]

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
        return [(str(row.get("system", "")), None), self._distance(row),
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
               "Cr/hr", "t/hr", "Merits", "Time", "Sold at")

# The Earnings window's pages (1.10038), in order. The one on show is kept
# as the setting earnings_page.
EARNINGS_PAGES = ("This session", "Where to sell", "Sessions", "System prices")
EARNINGS_PAGE_TIPS = {
    "This session": "The session you are on: its numbers, the hold, and Start, "
                    "Pause and End.",
    "Where to sell": "Where what is aboard sells best within the distance, and "
                     "one stop for the whole hold.",
    "Sessions": "Every Rhino session, and what they add up to.",
    "System prices": "The last known prices at every market in a system you name.",
}
# The narrowest a stat card is laid out at.
CARD_MIN_W = 150


def earnings_page(name):
    """The Earnings page called `name`, or This session for any other."""
    text = str(name or "").strip().lower()
    for page in EARNINGS_PAGES:
        if page.lower() == text:
            return page
    return EARNINGS_PAGES[0]


def stat_card(parent, title, note=None):
    """One number with its name over it, in a box of its own (1.10038):
    how This session shows the numbers that matter, big enough to read
    across the room. (box, the number's label)."""
    box = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=6,
                       border_width=1, border_color=RULE)
    name = ctk.CTkLabel(box, text=title, font=F_SMALL_B, text_color=DIM, anchor="w")
    name.pack(fill="x", padx=12, pady=(8, 0))
    value = ctk.CTkLabel(box, text=CARD_NONE, font=F_HEAD, text_color=DIM, anchor="w")
    value.pack(fill="x", padx=12, pady=(0, 8))
    for widget in (box, name, value):
        tip(widget, note)
    return box, value


class EarningsWindow(ToolWindow):
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

        # The session you are on, in one line under the title (1.10035:
        # "current session data is the one that is important"): which one,
        # and what is sold so far. Its numbers are the cards on This
        # session (1.10038); the sessions before it are the Sessions page.
        self.current = ctk.CTkLabel(top, text="", font=F_READOUT,
                                    text_color=AMBER, anchor="w",
                                    justify="left")
        self.current.pack(fill="x", anchor="w", padx=12, pady=(2, 4))

        # Four pages (1.10038: "the tabs for earning ... feel cluttered and
        # filters should actually match what the tabs are"). Each shows its
        # own controls and nothing else; the one picked is remembered.
        switch = ctk.CTkFrame(top, fg_color="transparent")
        switch.pack(fill="x", padx=12, pady=(2, 10))
        self.page_buttons = {}
        for name in EARNINGS_PAGES:
            button = tip(ctk.CTkButton(switch, text=name, width=130, height=30,
                                       font=F_STRONG, **BTN_SECONDARY,
                                       command=lambda n=name: self.show_page(n)),
                         EARNINGS_PAGE_TIPS[name])
            button.pack(side="left", padx=(0, 6))
            self.page_buttons[name] = button

        # -- This session: the cards, the hold, and the session's controls.
        self.session_page = ctk.CTkFrame(self, fg_color="transparent")
        self.card_row = tk.Frame(self.session_page, bg=VOID, bd=0)
        self.card_row.pack(fill="x", pady=(0, 2))
        self.cards = {}
        for name in SESSION_CARDS:
            self.cards[name] = stat_card(self.card_row, name, SESSION_CARD_TIPS[name])
        self._card_columns = 0
        self._lay_cards(len(SESSION_CARDS) * CARD_MIN_W)
        self.card_row.bind("<Configure>", self._lay_cards, add="+")
        self.card_row.bind("<Configure>", self._rewrap, add="+")
        # What the value rests on, in one line under the cards.
        self.session_note = ctk.CTkLabel(self.session_page, text="", font=F_SMALL,
                                         text_color=DIM, anchor="w", justify="left")
        self.session_note.pack(fill="x", anchor="w", padx=2)
        # What is in the hold RIGHT NOW, at the last price seen. The rows
        # on Sessions are history; this line is the run you are still on,
        # and it is the reason to have the window open while the game is
        # running.
        self.holding = ctk.CTkLabel(self.session_page, text="", font=F_BODY,
                                    text_color=DIM, anchor="w",
                                    justify="left")
        self.holding.pack(fill="x", anchor="w", padx=2, pady=(4, 6))
        buttons = ctk.CTkFrame(self.session_page, fg_color="transparent")
        buttons.pack(fill="x", pady=(0, 2))
        # Right-hand one first. Pack order is claim order, and the button
        # packed last against the far edge is the one that disappears when
        # the window is dragged narrow.
        self.session_copy = tip(ctk.CTkButton(
            buttons, text="Copy", width=90, height=32, font=F_STRONG,
            **BTN_SECONDARY, command=self.copy_session),
            "Copies this session as text, ready to paste into Discord.")
        self.session_copy.pack(side="right")
        # A session opens on the first rig down or the first tonne refined
        # in the Rhino, and closes on every rig up or the Rhino aboard. These
        # are for doing it by hand: Start before anything is down, Pause for
        # the drive to a station or a break - paused time is not in the
        # Cr/hr - and End.
        self.start_button = tip(ctk.CTkButton(
            buttons, text="Start session", width=120, height=32,
            font=F_STRONG, **BTN_SECONDARY, command=self.start_session), "Starts a session by hand. The first rig down or tonne refined starts one anyway.")
        self.start_button.pack(side="left", padx=(0, 6))
        self.pause_button = tip(ctk.CTkButton(
            buttons, text="Pause", width=100, height=32, font=F_STRONG,
            **BTN_SECONDARY, command=self.pause_session), "Stops the clock for a break or a trip; Cr/hr leaves the pause out.")
        self.pause_button.pack(side="left", padx=6)
        self.end_button = tip(ctk.CTkButton(
            buttons, text="End session", width=110, height=32, font=F_STRONG,
            **BTN_SECONDARY, command=self.end_session), "Ends the session now.")
        self.end_button.pack(side="left", padx=6)
        # One session across several trips. Off, a session is one outing:
        # the Rhino goes out, fills the ship a hold at a time, and comes
        # back aboard. On, it carries on through the flight to a station,
        # the sale and the trip back, until it is ticked off again.
        self.multi = ctk.BooleanVar(
            value=bool(self.app.settings.get("earnings_multi_session")))
        self.multi_box = tip(ctk.CTkCheckBox(
            buttons, text="Multi-session - keep one session going across "
                          "trips to a station",
            variable=self.multi, font=F_BODY, command=self.set_multi),
            "One session across trips to a station, instead of a new one each time the Rhino comes aboard.")
        self.multi_box.pack(side="left", padx=(14, 6))

        # -- Where to sell what is aboard, from the system you are in. The
        # price at the last station seen is not the answer to "where do I
        # take this": the same Sapphire is worth more two jumps away, and
        # this is the one screen that already knows what is in the hold.
        self.sell_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.sell_title = ctk.CTkLabel(self.sell_bar, text="Where to sell what is aboard",
                                       font=F_STRONG, text_color=ORANGE,
                                       anchor="w")
        self.sell_title.pack(side="left")
        self.check_button = tip(ctk.CTkButton(
            self.sell_bar, text="Check prices", width=120, height=30,
            font=F_STRONG, **BTN_PRIMARY, command=self.check_prices),
            "Prices what is aboard: galactic average, best here, and best within the distance.")
        self.check_button.pack(side="right")
        self.sell_within = tip(ctk.CTkComboBox(self.sell_bar, width=100, font=F_BODY,
                                           **BOX, values=list(QUOTE_DISTANCES)
                                           + [name for name, _n in SP.JUMP_CHOICES]),
                               "How far you would fly to sell: in light years, or in "
                               "jumps at your jump range (Settings > Basics).")
        self.sell_within.set(DEFAULT_QUOTE_DISTANCE)
        self.sell_within.pack(side="right", padx=6)
        ctk.CTkLabel(self.sell_bar, text="within", font=F_BODY,
                     text_color=DIM).pack(side="right")
        # The prices, then one stop for the whole hold - scrolled, so a
        # full hold on a short window is never cut off.
        self.sell_scroller = ScrollTable(self)
        self.quote_table = self.sell_scroller.inner

        # -- Sessions: the table, the all-time line, Copy all.
        self.sessions_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.sessions_copy = tip(ctk.CTkButton(
            self.sessions_bar, text="Copy all", width=100, height=32,
            font=F_STRONG, **BTN_SECONDARY, command=self.copy_all),
            "Copies the sessions as text, ready to paste into Discord.")
        self.sessions_copy.pack(side="right")
        self.refresh_button = tip(ctk.CTkButton(
            self.sessions_bar, text="Refresh", width=100, height=32,
            font=F_STRONG, **BTN_PRIMARY, command=self.refresh),
            "Reads the sessions again.")
        self.refresh_button.pack(side="left")

        # -- System prices (#187): the last known sell price of each
        # commodity at every market in any system you name - what
        # commanders read off their own markets and what the market index
        # last saw, whichever is newer, and whose it was. Blank is the
        # system you are in.
        #
        # Right-hand things first, the expanding box last: pack order is
        # claim order, and the box packed before them would push the button
        # off the edge of a narrow window.
        self.prices_bar = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(self.prices_bar, text="System", font=F_STRONG,
                     text_color=ORANGE, anchor="w").pack(side="left")
        self.prices_copy = tip(ctk.CTkButton(
            self.prices_bar, text="Copy all", width=100, height=30,
            font=F_STRONG, **BTN_SECONDARY, command=self.copy_all),
            "Copies the prices as text, ready to paste into Discord.")
        self.prices_copy.pack(side="right")
        self.search_button = tip(ctk.CTkButton(
            self.prices_bar, text="Search system", width=130, height=30,
            font=F_STRONG, **BTN_PRIMARY, command=self.search_system),
            "The last known sell price of each commodity at every market in the system.")
        self.search_button.pack(side="right", padx=(0, 10))
        self.system_best = ctk.BooleanVar(value=True)
        self.best_box = tip(ctk.CTkCheckBox(
            self.prices_bar, width=150, text="Best market only",
            variable=self.system_best, onvalue=True, offvalue=False,
            font=F_BODY, checkbox_width=18, checkbox_height=18, border_width=2,
            fg_color=ORANGE, hover_color=AMBER, text_color=DIM,
            command=self._paint), "One row per commodity - the best station. Untick for every station.")
        self.best_box.pack(side="right", padx=(10, 8))
        self.system_pick = tip(ctk.CTkComboBox(
            self.prices_bar, width=240, font=F_BODY, **BOX,
            values=["Any"] + list(SV.KNOWN_COMMODITIES)), "Tick the commodities to price; Any is all of them.")
        self.system_pick.set("Any")
        self.system_pick.pack(side="right", padx=(6, 0))
        ctk.CTkLabel(self.prices_bar, text="for", font=F_BODY,
                     text_color=DIM).pack(side="right")
        self.system_box = tip(ctk.CTkEntry(
            self.prices_bar, height=30, font=F_BODY, **ENTRY,
            placeholder_text="system name - blank is the one you are in"), "The system to look at. Blank is the one you are in.")
        self.system_box.pack(side="left", fill="x", expand=True, padx=(10, 8))
        self.system_box.bind("<Return>", lambda _e: self.search_system(),
                             add="+")
        Suggest(self.system_pick,
                lambda typed: ["Any"] + SV.matches(list(SV.KNOWN_COMMODITIES),
                                                   typed), multi=True)
        chain_tab([self.system_box, self.system_pick])

        # Sessions and System prices share one table: it shows the
        # sessions, or the prices from the last system search.
        self._view = "sessions"
        self._system_answer, self._system_asked = None, {}
        self._price_sort = (None, False)

        self.status = ctk.CTkLabel(self, text="", font=F_READOUT,
                                   text_color=DIM, anchor="w")
        # All-time totals, under the sessions they add up.
        self.summary = ctk.CTkLabel(self, text="", font=F_READOUT,
                                    text_color=AMBER, anchor="w",
                                    justify="left")
        self.scroller = ScrollTable(self)
        self.table = self.scroller.inner
        for scroller in (self.scroller, self.sell_scroller):
            for sequence in ("<MouseWheel>", "<Shift-MouseWheel>",
                             "<Button-4>", "<Button-5>"):
                self.bind(sequence, scroller.wheel, add="+")
        settings = attr(app, "settings", None) or {}
        self.show_page(settings.get("earnings_page"), keep=False)
        self.refresh()
        self.show_quotes()
        # Asked for straight away when there is something aboard - the
        # whole reason to open this with a full hold is to find out where
        # to take it. Quietly: an offline commander gets the ledger, not an
        # error, and the button is there to ask again.
        if self.app.aboard_for_sale():
            self.check_prices(quiet=True)

    # -- the pages (1.10038) --------------------------------------------------

    def show_page(self, name, keep=True):
        """Show one of the four pages, and nothing of the other three.

        An unknown name is This session. `keep`: remember it for next time
        (the setting earnings_page)."""
        page = earnings_page(name)
        self.page = page
        if page == "Sessions":
            self._view = "sessions"
        elif page == "System prices":
            self._view = "prices"
        for other, button in (attr(self, "page_buttons") or {}).items():
            try:
                button.configure(**(BTN_PRIMARY if other == page else BTN_SECONDARY))
            except Exception:
                pass
        self._arrange()
        # The status line is the page's: what another page said is not news.
        self.say("")
        if page in ("Sessions", "System prices"):
            self._paint()
            self.scroller.top()
        settings = attr(self.app, "settings", None)
        if keep and isinstance(settings, dict) and settings.get("earnings_page") != page:
            settings["earnings_page"] = page
            save_settings(settings)

    def _arrange(self):
        """Pack the page on show in the order every tool has: its own
        controls, the status line, then its table."""
        for widget in (self.session_page, self.sell_bar, self.sell_scroller,
                       self.sessions_bar, self.prices_bar, self.status,
                       self.summary, self.scroller):
            widget.pack_forget()
        page = self.page
        own = {"This session": self.session_page, "Where to sell": self.sell_bar,
               "Sessions": self.sessions_bar, "System prices": self.prices_bar}[page]
        own.pack(fill="x", padx=12, pady=(0, 4))
        self.status.pack(fill="x", padx=14, pady=(0, 4))
        if page == "Where to sell":
            self.sell_scroller.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        elif page in ("Sessions", "System prices"):
            if page == "Sessions":
                # Packed before the table, at the bottom, so a short window
                # squeezes the table and not this line.
                self.summary.pack(side="bottom", fill="x", anchor="w", padx=14,
                                  pady=(0, 10))
            self.scroller.pack(fill="both", expand=True, padx=12, pady=(0, 4))

    def _lay_cards(self, event=None):
        """The cards in as many columns as the width takes: one row on a
        wide window, two or more on a narrow one. Must not raise."""
        try:
            width = event if isinstance(event, int) else int(event.width)
            cards = list((attr(self, "cards", None) or {}).values())
            if not cards or width < 2:
                return
            rows = -(-len(cards) // max(1, width // CARD_MIN_W))
            columns = -(-len(cards) // rows)
            if columns == self._card_columns:
                return
            self._card_columns = columns
            for index, (box, _value) in enumerate(cards):
                box.grid(row=index // columns, column=index % columns,
                         padx=(0, 8), pady=(0, 8), sticky="nsew")
            for column in range(len(cards)):
                self.card_row.grid_columnconfigure(
                    column, weight=1 if column < columns else 0,
                    uniform="card" if column < columns else "")
        except Exception:
            pass

    def _table_say(self, text, colour=None):
        """The table's own word on the status line - only while the table
        is on show. On This session, "6 Rhino session(s)" is not news."""
        if attr(self, "page", "Sessions") in ("Sessions", "System prices"):
            self.say(text, colour)

    def _rewrap(self, event=None):
        """The hold line and the note under the cards wrap at the page's
        width, not off the edge of a narrow window. Must not raise."""
        try:
            wrap = max(300, int(event.width) - 20)
            for label in (self.holding, self.session_note):
                label.configure(wraplength=wrap)
        except Exception:
            pass

    def show_view(self, name):
        """The table's two pages by their old names: the sessions, or the
        last system search's prices."""
        self.show_page("System prices" if name == "prices" else "Sessions")

    def copy_session(self):
        """This session as text, ready to paste into Discord."""
        try:
            lines = current_session_lines(self.app, attr(self, "_rows", None) or [])
            put_on_clipboard(self, "\n".join(line for line in lines if line))
        except Exception as exc:
            return self.say("Could not copy the session: %s" % exc, RED)
        return self.say("Copied the session - paste it straight into Discord.", GREEN)

    def _system_wanted(self):
        """The system typed, or the one the game has us in."""
        try:
            typed = self.system_box.get().strip()
        except Exception:
            typed = ""
        if typed:
            return typed
        return str(getattr(attr(self.app, "watcher"), "system", "") or "").strip()

    def search_system(self):
        """Ask for the last known prices at every market in one system."""
        system = self._system_wanted()
        if not system:
            return self.say("Type a system name - the game has not said "
                            "which system you are in yet.", AMBER)
        community = attr(self.app, "community")
        if community is None or not community.can_read:
            return self.say("Not connected to the community map - check "
                            "Settings > Sharing.", AMBER)
        suggest = getattr(self.system_pick, "suggest", None)
        if suggest is not None:
            suggest.tidy()
        picked = picks_of(self.system_pick)
        try:
            sent = community.system_prices(system, picked, tag=SYSTEM_PRICE_TAG)
        except Exception as exc:
            return self.say("Could not ask: %s" % exc, RED)
        if not sent:
            return self.say("That request was not sent - not connected to "
                            "the community map.", RED)
        self._system_asked = {"system": system, "picked": list(picked),
                              "at": time.time()}
        self.say("Asking for the last known prices in %s..." % system)
        return True

    def system_results(self, ok, message):
        """The answer to search_system. Must not raise."""
        asked = attr(self, "_system_asked") or {}
        system = asked.get("system") or "that system"
        if not ok:
            return self.say("Could not get prices for %s: %s" % (system, message),
                            RED)
        try:
            data = json.loads(message)
            if not isinstance(data, dict):
                raise ValueError
        except (TypeError, ValueError):
            return self.say("The server sent something unreadable.", RED)
        self._system_answer = {
            "system": str(data.get("system") or system),
            "rows": [row for row in data.get("prices") or []
                     if isinstance(row, dict)],
            "status": str(data.get("upstream_status") or ""),
            "picked": list(asked.get("picked") or [])}
        self._price_sort = (None, False)
        self.show_view("prices")

    def _price_cells(self, row):
        """One price row as (text, colour, sort key) cells."""
        # Its age, and past a day "stale" in words, not just a dimmer colour.
        words, age = price_age(row.get("seen"))
        days = None if age is None else age / 86400.0
        if age is None or age > PRICE_STALE_S:
            words += " - stale"
        try:
            sell = int(row.get("sell") or 0)
        except (TypeError, ValueError):
            sell = 0
        try:
            demand = int(row.get("demand") or 0)
        except (TypeError, ValueError):
            demand = 0
        return [
            (str(row.get("commodity") or ""), TEXT),
            (credits_text(sell), GREEN, sell),
            (str(row.get("station") or "-"), TEXT),
            (station_kind(row.get("station_type")), DIM),
            (pad_size(row.get("pad")), DIM),
            ("{:,}".format(demand), TEXT, demand),
            (words, GREEN if days is not None and days < 1 else
             DIM if days is None or days < 30 else FAINT,
             days if days is not None else 1e9),
            # Neutral words only (1.10035): the server once sent a
            # provider's own name here, and it went straight on screen.
            (price_source(row.get("source")), DIM),
            (str(row.get("markets") or ""), DIM, row.get("markets") or 0),
        ]

    def _price_rows(self):
        answer = attr(self, "_system_answer") or {}
        rows = system_price_rows(answer.get("rows") or [],
                                 best_only=bool(self.system_best.get()))
        column, backwards = attr(self, "_price_sort") or (None, False)
        if column is None:
            return rows
        return sorted(rows, key=lambda r: self._cell(
            self._price_cells(r)[column])[2], reverse=backwards)

    def sort_prices(self, column):
        column_now, backwards = attr(self, "_price_sort") or (None, False)
        self._price_sort = (column, (not backwards) if column == column_now
                            else False)
        self._paint()

    def _paint_prices(self):
        """Draw the last system search. Must not raise."""
        table = attr(self, "table")
        if table is None:
            return
        try:
            for widget in table.winfo_children():
                widget.destroy()
            self._summarise()
            answer = attr(self, "_system_answer")
            if not answer:
                ctk.CTkLabel(table, text=SYSTEM_PRICE_ADVICE, font=F_BODY,
                             text_color=DIM, justify="left",
                             wraplength=820).grid(row=0, column=0, padx=14,
                                                  pady=18, sticky="w")
                return self._table_say("No system searched yet.", AMBER)
            rows = self._price_rows()
            if not rows:
                ctk.CTkLabel(table, text=system_price_empty(answer),
                             font=F_BODY, text_color=DIM, justify="left",
                             wraplength=820).grid(row=0, column=0, padx=14,
                                                  pady=18, sticky="w")
                return self._table_say(system_price_status(answer, rows), AMBER)
            column_now, backwards = attr(self, "_price_sort") or (None, False)
            for column, name in enumerate(PRICE_HEADERS):
                text = name
                if column == column_now:
                    text = "%s %s" % (name, "v" if backwards else "^")
                tip(ctk.CTkButton(table, text=text, font=F_SMALL_B,
                              **BTN_HEADING, anchor="w", height=24, width=0,
                              command=lambda c=column: self.sort_prices(c)), "Click to sort by this column; click again to turn it round.").grid(
                                  row=0, column=DATA_COLUMN_0 + column,
                                  padx=4, pady=4, sticky="w")
            for index, row in enumerate(rows, start=1):
                for column, cell in enumerate(self._price_cells(row)):
                    text, colour, _key = self._cell(cell)
                    tk.Label(table, text=text, font=F_SMALL, fg=colour or TEXT,
                             bg=PANEL, justify="left", anchor="w",
                             wraplength=CELL_WRAP, bd=0).grid(
                                 row=index, column=DATA_COLUMN_0 + column,
                                 padx=8, pady=2, sticky="w")
            colour = GREEN if answer.get("status") in ("live", "cached", "off",
                                                       "not configured") else AMBER
            self._table_say(system_price_status(answer, rows), colour)
        except Exception as exc:
            self.say("Could not draw the prices: %s" % exc, RED)

    def prices_text(self):
        """The prices on screen as plain lines. Empty when there are none."""
        answer = attr(self, "_system_answer") or {}
        rows = self._price_rows() if answer else []
        if not rows:
            return ""
        lines = ["%s - last known prices" % answer.get("system", ""),
                 " | ".join(PRICE_HEADERS)]
        for row in rows:
            lines.append(" | ".join(self._cell(c)[0]
                                    for c in self._price_cells(row)))
        return "\n".join(lines)

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
            choice = self.sell_within.get().strip()
            jumps = SP.radius_for(choice, self.app.jump_range())
            if jumps is not None:
                return int(math.ceil(min(jumps[0], max(QUOTE_DISTANCES.values()))))
            return QUOTE_DISTANCES.get(choice, QUOTE_DISTANCES[DEFAULT_QUOTE_DISTANCE])
        except Exception:
            return QUOTE_DISTANCES[DEFAULT_QUOTE_DISTANCE]

    def _jump_note(self):
        """"4 jumps at 42.7 Ly" - or why the jump range is a guess."""
        try:
            jumps = SP.radius_for(self.sell_within.get().strip(), self.app.jump_range())
        except Exception:
            jumps = None
        if jumps is None:
            return ""
        if jumps[2]:
            return ("at %g Ly a jump - set your own in Settings > Basics, or "
                    "board your ship so the game says it" % jumps[1])
        return "at %g Ly a jump" % jumps[1]

    def check_prices(self, quiet=False):
        """Ask the community server where each thing aboard sells best."""
        try:
            count, why = self.app.quote_hold(self._radius())
        except Exception as exc:
            count, why = 0, "Could not ask: %s" % exc
        if not count:
            if not quiet:
                self._sell_say(why, AMBER)
            return 0
        self._sell_say("Asking for the best price for %d commodit%s within %d Ly "
                       "of %s..." % (count, "y" if count == 1 else "ies",
                                     self._radius(),
                                     self.app.quote_asked.get("system", "here")))
        return count

    def _sell_say(self, text, colour=None):
        """The price check's word on the status line - only on Where to
        sell, whose news it is. The check the window runs by itself when
        something is aboard used to say "Asking..." over This session."""
        if attr(self, "page", "Where to sell") == "Where to sell":
            self.say(text, colour)

    def show_quotes(self):
        """Draw what has come back so far. Must not raise."""
        table = attr(self, "quote_table")
        if table is None:
            return
        try:
            for widget in table.winfo_children():
                widget.destroy()
            # 1.10035: Aboard is the hold as it is now, SRV and ship; every
            # price is judged - own read first, age shown, past a day stale,
            # Demand 0 out, a lone high price flagged (judge_prices).
            cargo = self.app.aboard_for_sale()
            asked = attr(self.app, "quote_asked") or {}
            system = asked.get("system") or getattr(self.app.watcher,
                                                    "system", "") or ""
            if system:
                self.sell_title.configure(
                    text="Where to sell what is aboard - from %s" % system)
            here_system = getattr(self.app.watcher, "system", "") or system
            picked = {name: pick_prices(self.app.price_rows_for(name), here_system)
                      for name in worth_asking(cargo, limit=len(cargo))}
            rows = [name for name, pick in picked.items()
                    if pick["best"] or pick["here"]]
            if not rows:
                problem = attr(self.app, "quote_problem")
                if problem:
                    self._sell_say("Could not get prices - the server said: %s"
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
            notes = []
            for index, name in enumerate(rows, start=1):
                pick = picked[name]
                best, here = pick["best"], pick["here"]
                count = int(cargo.get(name, 0))
                seen = ("%s - %s" % (price_age(best.get("seen"))[0],
                                     best["source"])) if best else "-"
                average, source = self.app.galactic_average(name)
                # Every price says how old it is; past a day, stale.
                if here and here.get("stale"):
                    here_text = "%s - %s, stale" % (credits_text(here["sell"]),
                                                     price_age(here.get("seen"))[0])
                elif here:
                    here_text = "%s - %s" % (credits_text(here["sell"]),
                                             price_age(here.get("seen"))[0])
                else:
                    here_text = "none known"
                tone = (DIM if best is None or best.get("stale") else
                        AMBER if best.get("outlier") else GREEN)
                cells = (
                    (name, TEXT),
                    ("%dt" % count, TEXT),
                    ((credits_text(average) + ("" if source == "game" else " *"))
                     if average else "-", DIM),
                    (here_text, DIM if here is None or here.get("stale") else TEXT),
                    (credits_text(best["sell"]) + price_note(best)
                     if best else "none within range", tone),
                    (quote_where(best), TEXT),
                    (seen, DIM),
                    (credits_text(best["sell"] * count) + " Cr" + price_note(best)
                     if best else "-", tone),
                )
                higher = pick.get("higher_stale")
                if higher:
                    notes.append("%s: %s Cr at %s, %s - older than a day, so "
                                 "not used." % (name, credits_text(higher["sell"]),
                                                quote_where(higher),
                                                price_age(higher.get("seen"))[0]))
                for column, (text, colour) in enumerate(cells):
                    tk.Label(table, text=text, font=F_SMALL, fg=colour,
                             bg=PANEL, anchor="w", bd=0,
                             wraplength=CELL_WRAP).grid(
                                 row=index, column=column, padx=(0, 14),
                                 sticky="w")
            if any(self.app.galactic_average(name)[1] == "table"
                   for name in rows):
                notes.append("* EDSMT's own figure. Open any commodity market "
                             "in the game and the game's galactic average "
                             "replaces it.")
            judged = [picked[name][key] for name in rows
                      for key in ("best", "here") if picked[name][key]]
            if any(row.get("stale") for row in judged):
                notes.append("Stale: last seen more than a day ago - check the "
                             "market before you fly. Never counted as what a "
                             "system pays now.")
            if any(row.get("outlier") for row in judged):
                notes.append("Unconfirmed: one market's price, far above every "
                             "other in range - an old or mistaken read until "
                             "someone sees it again.")
            for extra, text in enumerate(notes, start=1):
                tk.Label(table, text=text, font=F_SMALL,
                         fg=DIM, bg=PANEL, anchor="w", bd=0,
                         wraplength=CELL_WRAP * 6).grid(
                             row=len(rows) + extra, column=0, columnspan=8,
                             sticky="w", pady=(4 if extra == 1 else 0, 0))
            self._one_stop(table, len(rows) + len(notes) + 1)
        except Exception as exc:
            self.say("Could not show the prices: %s" % exc, RED)

    def one_stop_lines(self):
        """[(text, colour)] for "one stop for the whole hold": the stations
        that take the most of what is aboard, within the distance picked,
        with what each takes, how old its prices are and which way they
        are moving. Shared by the table below and the tests."""
        radius = self._radius()
        jump_ly = self.app.jump_range()
        note = self._jump_note()
        lines = [("One stop for the whole hold - within %d Ly%s, no fleet "
                  "carriers, prices from the last day" % (
                      radius, (" (" + note + ")") if note else ""), ORANGE)]
        ship, srv = self.app.hold_split()
        if srv:
            lines.append(("Aboard: %d t in the ship + %d t in the SRV - counted, "
                          "it goes to the ship when the Rhino docks." % (ship, srv), DIM))
        found = self.app.one_stop(within_ly=radius)
        if not found:
            lines.append(("No one station has a fresh price for this hold within "
                          "%d Ly yet. Press Check prices, or widen the distance." % radius, DIM))
            return lines
        for place, spot in enumerate(found, start=1):
            far = spot.get("distance_ly")
            jumps = SP.jumps_for(far, jump_ly or SP.JUMP_FALLBACK_LY)
            where = ", ".join(str(x) for x in (spot["station"], spot["system"]) if x)
            if far is not None:
                where += " (%s Ly%s)" % (_round(float(far), 1),
                                         "" if jumps is None else
                                         ", here" if jumps == 0 else
                                         ", ~%d jump%s" % (jumps, "" if jumps == 1 else "s"))
            takes = ("takes your whole hold" if spot["tonnes"] >= spot["of"]
                     else "takes %d of %d t" % (spot["tonnes"], spot["of"]))
            lines.append(("#%d  %s Cr at %s - %s - prices %s old" % (
                place, credits_text(spot["total"]), where, takes,
                SP.age_words(spot.get("oldest_s"))), GREEN if place == 1 else TEXT))
            parts = []
            for part in spot["parts"]:
                text = "%s %d t at %s" % (part["commodity"], part["tonnes"],
                                          credits_text(part["sell"]))
                if part["tonnes"] < part["aboard"]:
                    text += " (demand %d of your %d t)" % (part["tonnes"], part["aboard"])
                moved = SP.trend_words(part.get("trend"))
                if moved:
                    text += " - " + moved
                parts.append(text)
            if spot["missing"]:
                parts.append("not bought there: " + ", ".join(spot["missing"]))
            lines.append(("      " + "; ".join(parts), DIM))
        return lines

    def _one_stop(self, table, start):
        """Draw one_stop_lines under the price table. Must not raise."""
        try:
            lines = self.one_stop_lines()
        except Exception as exc:
            lines = [("One stop for the whole hold: could not work it out (%s)" % exc, DIM)]
        for offset, (text, colour) in enumerate(lines):
            label = tk.Label(table, text=text, font=F_SMALL,
                             fg=colour, bg=PANEL, anchor="w", bd=0, justify="left",
                             wraplength=CELL_WRAP * 6)
            if offset == 0:
                label.configure(font=F_SMALL_B)
            label.grid(row=start + offset, column=0, columnspan=8, sticky="w",
                       pady=(8 if offset == 0 else 0, 0))

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
        if attr(self, "_view") == "prices":
            return self._paint_prices()
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
                return self._table_say("No Rhino sessions recorded yet.", AMBER)
            self._headings()
            for index, row in enumerate(rows, start=1):
                self._row(index, row)
            self._table_say("%d Rhino session(s)." % len(rows), GREEN)
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
            tip(ctk.CTkButton(self.table, text=text, font=F_SMALL_B,
                          **BTN_HEADING, anchor="w", height=24, width=0,
                          command=lambda c=column: self.sort_by(c)), "Click to sort by this column; click again to turn it round.").grid(
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
        """The session you are on at the top; everything, added up, under
        the rows it is the sum of."""
        totals = self.app.earnings.totals(self._rows)
        self.summary.configure(
            text="All time: %d Rhino session(s)   %s Cr sold   %s at the face   %s Cr/hr overall"
                 % (totals["runs"], credits_text(totals["earned"]),
                    duration_text(totals["hours"]),
                    credits_text(totals["cr_hr"])))
        self._show_current()
        self.holding.configure(text=self._holding() or
                               "Nothing mined in the hold, or the game is not "
                               "running.")
        self._session_buttons()

    def live(self):
        """The current session and the hold, redrawn - not the table, which
        is history. From the app's tick, every LEDGER_LIVE_S (1.10035)."""
        self._show_current()
        holding = attr(self, "holding")
        if holding is not None:
            holding.configure(text=self._holding() or
                              "Nothing mined in the hold, or the game is not "
                              "running.")

    def _show_current(self):
        """The session on show: the line under the title, the cards and the
        line under them (1.10038). Must not raise."""
        try:
            view = current_session(self.app, attr(self, "_rows", None) or [])
        except Exception as exc:
            view = {"head": "Current session: could not be worked out (%s)." % exc,
                    "cards": [], "note": ""}
        cards = attr(self, "cards", None) or {}
        try:
            current = attr(self, "current")
            if current is not None:
                current.configure(text=view["head"])
            for name, text, colour in view["cards"]:
                if name in cards:
                    cards[name][1].configure(text=text, text_color=colour)
            note = attr(self, "session_note")
            if note is not None:
                note.configure(text=view["note"])
        except Exception:
            pass

    def _holding(self):
        """The live line: what is aboard, and what it would fetch.

        Wrapped in its own try because this is the one part of the window
        that reaches outside the CSV, into the reader and the last market.
        A ledger that refuses to open because Elite is shut would be a
        ledger nobody can tidy up in the evening.
        """
        try:
            holds = dict(getattr(self.app.watcher, "holds", None) or {})
            # The same hold the sell table prices (1.10035), at the station
            # docked at, or at your own read of a market in this system -
            # not whichever Market.json came last.
            cargo = self.app.aboard_for_sale()
            prices, where, when = self.app.market_here(cargo)
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
            if getattr(self.app.watcher, "docked", False) and where:
                if when:
                    return text + (" %s buys none of it, by your last read of "
                                   "its board (%s)." % (where, price_age(when)[0]))
                return text + (" %s's board has not been read yet - open its "
                               "commodity market to price the hold here." % where)
            # Undocked with no read of your own that buys it (1.10035). "No
            # market prices seen yet" sat over a sell table full of them.
            if where:
                return text + (" %s, the last market you read, buys none of "
                               "it - Where to sell has the prices known "
                               "nearby." % where)
            return text + (" No market you have read buys it yet - Where to "
                           "sell has the prices known nearby.")
        age = (", by your read %s%s" % (price_age(when)[0], " - stale"
                                        if (price_age(when)[1] or 0) > PRICE_STALE_S
                                        else "")) if when else ""
        return text + " Worth %s Cr at %s%s." % (
            credits_text(worth), where or "the last market seen", age)

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
        # More than one Rhino in the session: what each one did, under the
        # total - "Rhino A: 57t, 6 rigs, 22m". The game gives each Rhino its
        # own ID, so the split is the journal's, not a guess.
        split = SV.rhino_split(row)
        if len(split) > 1:
            for part in split:
                worked = max(0, SV._epoch(part["last"]) - SV._epoch(part["first"]))
                bits = ["%dt" % part["tonnes"]]
                if part["rigs"]:
                    bits.append("%d rig%s" % (part["rigs"],
                                              "" if part["rigs"] == 1 else "s"))
                if worked:
                    bits.append(duration_text(worked / 3600.0))
                mined += "\nRhino %s: %s" % (part["label"], ", ".join(bits))
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
            # Tonnes an hour (1.10034): what the digging itself is doing,
            # whatever the market paid for it.
            ("%.1f t" % SV.tonnes_per_hour(row) if SV.tonnes_per_hour(row) else "-",
             None, SV.tonnes_per_hour(row)),
            # Powerplay merits the game paid for this session's sales
            # (1.10036), counted from its own merit events - not estimated.
            self._merits_cell(row),
            (duration_text(hours) if hours else "-", None, hours),
            (str(row.get("station") or "") or ("still out" if live else "-"),
             AMBER if live else None),
        ]

    def _merits_cell(self, row):
        merits = session_merits_earned(self.app, row)
        if not merits:
            return ("-", DIM, 0)
        return ("{:,}".format(merits), GREEN, merits)

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
        """The whole ledger as a block, ready to paste into Discord - or the
        system's prices, when those are what is showing."""
        try:
            block = self.prices_text() if attr(self, "_view") == "prices" \
                else self.as_text()
        except Exception as exc:
            return self.say("Could not build that: %s" % exc, RED)
        if not block:
            return self.say("Nothing to copy yet - %s." % (
                "search a system first" if attr(self, "_view") == "prices"
                else "no runs recorded"), AMBER)
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
LAND_WRAP = {"Why": 250, "Best bets": 230, "Known sites": 200, "Ground": 170}

LAND_FOOTNOTE = (
    "Est. value is an estimate, not a promise. It is the known sites still "
    "intact at what they carry, plus each location nobody has shared at what "
    "a site on that kind of ground usually carries, at the best prices known. "
    "What sites usually carry comes from everyone's shared finds once %d or "
    "more are logged on that ground, and from the commodity tables until "
    "then - Best bets says which." % SV.LAND_MIN_SITES)


def land_carrying(rows, commodity):
    """The Where to land rows for bodies that carry `commodity`, or all.

    `commodity` is one name or several - a list, or "Ruby, Sapphire" - and
    a body carrying any one of them is kept (#188)."""
    if isinstance(commodity, str):
        commodity = [part for part in commodity.split(",") if part.strip()]
    wanted = {SV.fold(SV.canonical(name.strip())) for name in commodity or ()
              if str(name).strip() and str(name).strip().lower() != "any"}
    wanted.discard("")
    if not wanted:
        return list(rows)
    return [row for row in rows
            if wanted & set(row.get("carries") or [])]


class LandWindow(ToolWindow):
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
        tip(ctk.CTkButton(buttons, text="Copy all", width=100, height=32,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.copy_all), "Copies the table as text, ready to paste into Discord.").pack(side="right")
        tip(ctk.CTkButton(buttons, text="Refresh", width=100, height=32,
                      font=F_STRONG, **BTN_PRIMARY,
                      command=self.refresh), "Asks again: shared sites, and the public body database for this system.").pack(side="left")
        tip(ctk.CTkSwitch(buttons, text="Include bodies you cannot land on",
                      variable=self.show_all, font=F_BODY,
                      command=self._paint, **SWITCH), "Lists every body, not only the landable ones.").pack(side="left",
                                                          padx=(14, 0))
        # Only the bodies that carry one commodity: what the ground is known
        # or expected to carry, and what has been found on it.
        ctk.CTkLabel(buttons, text="Carrying", font=F_BODY,
                     text_color=DIM).pack(side="left", padx=(14, 6))
        self.carrying = tip(ctk.CTkComboBox(
            buttons, width=240, height=32, font=F_BODY, **BOX,
            values=["Any"] + list(SV.KNOWN_COMMODITIES),
            command=lambda _value: self._paint()), "Only bodies known or likely to carry the ticked commodities.")
        self.carrying.set("Any")
        self.carrying.pack(side="left")
        # Tick several and a body carrying any of them stays (#188).
        Suggest(self.carrying,
                lambda typed: ["Any"] + SV.matches(list(SV.KNOWN_COMMODITIES),
                                                   typed),
                on_pick=lambda _value: self._paint(), multi=True)

        # 1.10035: body and signal search, over this system or every one
        # the journals remember.
        self._far_rows, self._was_far = [], False
        self._bodies = BodyFilterBar(self, top, "land")

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
            bar = attr(self, "_bodies")
            if bar is not None and self._far_view(bar):
                return
            self._rows = land_carrying(
                self.app.land_rows(system, landable_only=not self.show_all.get()),
                self._carrying())
            if bar is not None:
                self._rows = bar.narrow_here(self._rows)
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
        parts = ["%d bod%s known" % (len(bodies), "y" if len(bodies) == 1 else "ies"),
                 "%d landable" % landable,
                 "%d mapped with the DSS" % mapped]
        public = self.app.public_body_count(system)
        if public:
            # Said, not hidden: these came from other commanders' scans
            # through the public body database, not from this PC.
            parts.append("%d from the public body database" % public)
        reading = self.app.backfill_note()
        if reading:
            parts.append(reading)
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
        """The commodities ticked in Carrying, as a list. None is any."""
        box = attr(self, "carrying", None)
        return picks_of(box) if box is not None else []

    def _advice(self, system):
        if system and self._carrying():
            return ("No body scanned here is known or expected to carry %s.\n\n"
                    "Set Carrying back to Any to see them all."
                    % " or ".join(self._carrying()))
        if not system:
            return ("Waiting for the journal to say which system you are in.\n\n"
                    "This list fills itself in: jump in, honk, and every body "
                    "the scanner resolves appears here. Map one with the DSS "
                    "and its mining locations are counted.")
        reading = self.app.backfill_note()
        return ("No landable body in %s is known yet.\n\n"
                "EDSMT remembers every body your journals have ever described "
                "and asks the public body database for the rest%s. Honk and "
                "use the FSS and each body appears here as it is resolved; "
                "anything other commanders have shared shows up as soon as "
                "the server answers."
                % (system, " - it is %s now" % reading if reading else ""))

    def _far_view(self, bar):
        """Where to land asked about more than this system: a table of the
        bodies the journals remember, nearest first. True when it drew one."""
        far = bar.far()
        if far != attr(self, "_was_far", False):
            # The two tables have different columns; a sort on one means
            # nothing on the other.
            self._was_far = far
            self._sort_column, self._sort_reverse = None, False
        if not far:
            self._far_rows = []
            return False
        rows = bar.narrow_far()
        self._far_rows, self._rows = rows, []
        for widget in self.table.winfo_children():
            widget.destroy()
        self.heading.configure(text="Where to land - bodies your journals remember")
        self.summary.configure(text="%d bod%s listed." % (
            len(rows), "y" if len(rows) == 1 else "ies"))
        self.say("")
        rows = self._sorted_far(rows)
        if not rows:
            ctk.CTkLabel(self.table, text=(
                "No remembered body matches. Loosen a filter, or widen Look in "
                "- bodies are remembered from every journal EDSMT has read."),
                font=F_BODY, text_color=DIM, justify="left",
                wraplength=820).grid(row=0, column=0, padx=14, pady=18,
                                     sticky="w")
            return True
        self._headings(LAND_FAR_HEADERS)
        for index, row in enumerate(rows, start=1):
            for column, cell in enumerate(land_far_cells(row)):
                text, colour, _key = EarningsWindow._cell(cell)
                cell_label(self.table, index, column, text, colour, CELL_WRAP)
            row_buttons(self.table, index, [
                ("system", lambda s=row["system"]: self.copy_text(
                    "the system name", s), False),
                ("body", lambda b=row["body"]: self.copy_text(
                    "the body name", b), False)])
        return True

    def _sorted_far(self, rows):
        column = self._sort_column
        if column is None or not rows:
            return rows

        def key(row):
            cells = land_far_cells(row)
            if column >= len(cells):
                return _sortable("")
            return EarningsWindow._cell(cells[column])[2]
        return sorted(rows, key=key, reverse=self._sort_reverse)

    def _far_text(self, rows):
        lines = ["Where to land - bodies your journals remember",
                 " | ".join(LAND_FAR_HEADERS)]
        for row in self._sorted_far(rows):
            lines.append(" | ".join(EarningsWindow._cell(c)[0].replace("\n", " ")
                                    for c in land_far_cells(row)))
        return "\n".join(lines)

    def _headings(self, headers=LAND_HEADERS):
        for column, name in enumerate(headers):
            text = name
            if column == self._sort_column:
                text = "%s %s" % (name, "v" if self._sort_reverse else "^")
            tip(ctk.CTkButton(self.table, text=text, font=F_SMALL_B,
                          **BTN_HEADING, anchor="w", height=24, width=0,
                          command=lambda c=column: self.sort_by(c)), "Click to sort by this column; click again to turn it round.").grid(
                              row=0, column=DATA_COLUMN_0 + column,
                              padx=4, pady=4, sticky="w")
        ctk.CTkLabel(self.table, text="Copy", font=F_SMALL_B,
                     text_color=ORANGE).grid(row=0, column=COPY_COLUMN,
                                             padx=8, pady=5, sticky="w")

    def _row(self, index, row):
        for column, cell in enumerate(self._land_row(row)):
            text, colour, _key = EarningsWindow._cell(cell)
            cell_label(self.table, index, column, text, colour,
                       LAND_WRAP.get(LAND_HEADERS[column], CELL_WRAP),
                       full=cell_full(cell))
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
            # A few words; the sentence is the tooltip and the copy (1.10038).
            (row.get("why") or row.get("note") or "", tier_colour,
             row.get("tier", 3), row.get("note") or ""),
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
                 " | ".join(cell_full(c).replace("\n", " ")
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
        far = attr(self, "_far_rows", None)
        if far:
            return self._far_text(far)
        rows = self._sorted(list(self._rows))
        if not rows:
            return ""
        lines = ["Where to land - %s" % self._system(), " | ".join(LAND_HEADERS)]
        for row in rows:
            lines.append(" | ".join(cell_full(c).replace("\n", " ")
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
    rows = answer_rows(data)
    commodity = SV.canonical(data.get("commodity") or "")
    best = max(rows, key=lambda r: r["sell"], default=None)
    folded = SV.fold(system)
    here = max((r for r in rows if folded and SV.fold(r.get("system")) == folded),
               key=lambda r: r["sell"], default=None)
    return commodity, best, here


def answer_rows(data):
    """Every usable row of a /v1/sell answer, upstream and community alike."""
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
    return rows


# -- whose price, how old, and whether to believe it (1.10035) ----------------
#
# 1.10034 put a four-day-old upstream price beside "Best within 100 Ly", an
# upstream "in this system" figure over the commander's own read of the board
# he was docked at, and an upstream provider's name in a Source column. The
# rules now: his own read first, then other EDSMT users', then market data;
# every price carries its age; past a day it is stale and never shown as what
# this system pays now; Demand 0 is not a market; a lone price far above every
# other in range is flagged.
PRICE_STALE_S = SV.PRICE_STALE_S
OUTLIER_RATIO = 1.5
SOURCE_RANK = {SV.OWN_SOURCE: 0, "community": 1, "market data": 2}


def price_source(source):
    """The words a price's source goes under. Never a provider's name."""
    text = str(source or "").strip().lower()
    if text == SV.OWN_SOURCE:
        return SV.OWN_SOURCE
    if text == "community":
        return "community"
    return "market data"


def price_age(seen, now=None):
    """(words, seconds) for a price's age: "12 min ago", "5 h ago",
    "4 days ago (2026-10-08)". ("age unknown", None) without a time."""
    at = SV._epoch(seen)
    if not at:
        return "age unknown", None
    age = max(0.0, (time.time() if now is None else now) - at)
    if age < 3600:
        return "%d min ago" % max(1, int(age // 60)), age
    if age < 86400:
        return "%d h ago" % int(age // 3600), age
    days = int(age // 86400)
    return "%d day%s ago (%s)" % (days, "" if days == 1 else "s",
                                  str(seen)[:10]), age


def judge_prices(rows, now=None):
    """Price rows fit to act on, highest first, each marked.

    Every row comes back with `source` in neutral words, `age_s`, `stale`
    and `outlier`. Dropped: no price, Demand 0 - a market that lists it and
    buys none - and a Community Goal's placeholder demand. One station priced
    twice keeps one row: fresh before stale, then the commander's own read,
    then community, then market data, then the newer."""
    now = time.time() if now is None else now
    kept = {}
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        try:
            sell = int(row.get("sell") or 0)
        except (TypeError, ValueError):
            continue
        demand = row.get("demand")
        try:
            demand = None if demand in (None, "") else int(demand)
        except (TypeError, ValueError):
            demand = None
        if sell <= 0 or demand == 0 or demand == PLACEHOLDER_DEMAND:
            continue
        at = SV._epoch(row.get("seen"))
        out = dict(row, sell=sell, demand=demand,
                   source=price_source(row.get("source")),
                   age_s=(now - at) if at else None,
                   stale=(not at) or now - at > PRICE_STALE_S, outlier=False)
        key = (SV.fold(out.get("system")), SV.fold(out.get("station")))
        rank = (out["stale"], SOURCE_RANK.get(out["source"], 3), -at)
        if key not in kept or rank < kept[key][0]:
            kept[key] = (rank, out)
    judged = sorted((row for _rank, row in kept.values()),
                    key=lambda r: (-r["sell"], r["stale"]))
    for group in ([r for r in judged if not r["stale"]],
                  [r for r in judged if r["stale"]]):
        if len(group) >= 2 and group[0]["sell"] > OUTLIER_RATIO * group[1]["sell"]:
            group[0]["outlier"] = True
    return judged


def pick_prices(judged, system=""):
    """What judged rows say, from where the commander is.

    here: the best price in this system - fresh if there is one; a stale
      one only marked stale.
    best: the best fresh price in range, outlier or not (it is flagged);
      the best stale one only when nothing fresh is known.
    credible: the best fresh price that is not a lone outlier - the one an
      estimate is made with. stale_pick: the best stale non-outlier, for an
      estimate when nothing is fresh. higher_stale: a stale price above
      `best`, to be mentioned and not used."""
    folded = SV.fold(system)
    fresh = [r for r in judged if not r["stale"]]
    stale = [r for r in judged if r["stale"]]
    local = [r for r in judged if folded and SV.fold(r.get("system")) == folded]
    here = next((r for r in local if not r["stale"]), None) or \
        next(iter(local), None)
    best = (fresh or stale or [None])[0]
    credible = next((r for r in fresh if not r["outlier"]), None)
    stale_pick = next((r for r in stale if not r["outlier"]), None)
    higher = next((r for r in stale if best is not None and not best["stale"]
                   and r["sell"] > best["sell"]), None)
    return {"here": here, "best": best, "credible": credible,
            "stale_pick": stale_pick, "higher_stale": higher}


def price_note(row):
    """" - stale", " - unconfirmed", both, or nothing, after a price. A lone
    high price is flagged whether or not it is also old."""
    if not row:
        return ""
    flags = [word for key, word in (("stale", "stale"), ("outlier", "unconfirmed"))
             if row.get(key)]
    return (" - " + ", ".join(flags)) if flags else ""


MERITS_TIP = ("Estimated from your own sales, learnt from your journals as "
              "you play. Frontier publish no formula, so until %d sales have "
              "been seen this shows \u2014." % SV.MERIT_MIN_PAIRS)

# This session's numbers, one stat card each, in reading order (1.10038).
SESSION_CARDS = ("Time", "Mined", "t/hr", "Est. value", "Cr/hr", "Merits earned",
                 "Merits/hr")
SESSION_CARD_TIPS = {
    "Time": "How long the session has run, to now. Paused time is left out.",
    "Mined": "Tonnes the Rhino has refined this session.",
    "t/hr": "Tonnes refined an hour: what the digging itself is doing.",
    "Est. value": "What is sold, plus what is still aboard at the best price "
                  "that can be trusted. The line under the cards says which.",
    "Cr/hr": "The estimated value, an hour.",
    "Merits earned": "The Powerplay merits the game paid for this session's sales.",
    "Merits/hr": MERITS_TIP,
}
# A card with no figure yet.
CARD_NONE = "\u2014"


def session_merits(rate, lines, sold, earned):
    """Powerplay merits a session's credits are estimated to earn, or None
    until the rate is learnt (1.10035).

    Each commodity at its own rate (MeritRate.per_credit): what is still
    unsold at its estimated worth, and what was sold at its share of the
    credits, split by tonnes sold. Never raises."""
    try:
        if rate is None or not rate.per_credit():
            return None
        merits = 0.0
        for line in lines or ():
            merits += float(line.get("worth") or 0) * (
                rate.per_credit(line.get("commodity")) or 0.0)
        sold = {key: int(count) for key, count in dict(sold or {}).items()
                if int(count or 0) > 0}
        earned = float(earned or 0)
        if earned > 0:
            total = sum(sold.values())
            if total:
                for key, count in sold.items():
                    merits += earned * count / total * (rate.per_credit(key) or 0.0)
            else:
                merits += earned * rate.per_credit()
        return merits or None
    except Exception:
        return None


def current_session_lines(app, rows=(), now=None):
    """(headline, value, merits) for the Rhino session in progress - or,
    with none open, the last one, and it says so. The session as text: what
    This session's Copy takes. Never raises."""
    return current_session(app, rows, now)["lines"]


def current_session(app, rows=(), now=None):
    """The Rhino session Earnings leads with: the one in progress or, with
    none open, the last one (1.10038). A dict:

    head   one line under the window's title - which session, what is sold
    cards  [(name, figure, colour)] in SESSION_CARDS order
    note   one line under the cards: what the estimated value rests on
    lines  the session as three lines of text (current_session_lines)
    """
    books = attr(app, "earnings")
    live = getattr(books, "rhino", None) if books is not None else None
    run, label = live, "CURRENT SESSION"
    if run is None:
        done = [r for r in rows or () if str(r.get("closed") or "").strip()]
        if not done:
            none = ("CURRENT SESSION: none running. One starts on your first "
                    "rig down, the first tonne the Rhino refines, or Start "
                    "session.")
            return {"head": none, "lines": (none, "", ""), "note": "",
                    "cards": [(name, CARD_NONE, DIM) for name in SESSION_CARDS]}
        run = max(done, key=lambda r: SV._epoch(r.get("started")))
        label = "LAST SESSION (ended %s)" % str(run.get("ended") or "")[:16].replace("T", " ")
    else:
        # Elapsed is to now, not to the last thing the journal said: twenty
        # minutes' drive to the next deposit is still the session.
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)) \
            if now is not None else SV.utc_now()
        if SV._epoch(stamp) > SV._epoch(run.get("ended")):
            run = dict(run, ended=stamp)
        if getattr(books, "paused", False):
            label += " - PAUSED"
    est = app.session_estimate(run)
    head = "%s   %s   %d t mined   %.1f t/hr   sold so far %s Cr" % (
        label, duration_text(est["hours"]), est["tonnes"], est["t_hr"],
        credits_text(est["earned"]))
    kinds = est["kinds"]
    if est["value"] > 0:
        basis = ("as sold" if not kinds else
                 "partly at the galactic average - no market price known"
                 if "average" in kinds else
                 "partly at prices more than a day old" if "stale" in kinds
                 else "at the best price seen in the last day")
        value = "Estimated %s Cr   %s Cr/hr   (%s)" % (
            credits_text(est["value"]), credits_text(est["cr_hr"]), basis)
    elif est["tonnes"]:
        value = ("No price known for what is mined yet - open a commodity "
                 "market, or Check prices.")
    else:
        value = ""
    rate = est["merits_hr"]
    earned = session_merits_earned(app, run)
    merits = ("Powerplay merits earned: {:,}".format(earned) if earned
              else "Powerplay merits earned: none yet")
    merits += ("   ~%s/hr (estimated from your own sales)"
               % "{:,}".format(int(round(rate))) if rate else "")
    worth = est["value"] > 0
    cards = [
        ("Time", duration_text(est["hours"]), TEXT),
        ("Mined", "%d t" % est["tonnes"], TEXT),
        ("t/hr", "%.1f" % est["t_hr"], TEXT),
        ("Est. value", credits_text(est["value"]) + " Cr" if worth else CARD_NONE,
         GREEN if worth else DIM),
        ("Cr/hr", credits_text(est["cr_hr"]) if worth else CARD_NONE,
         GREEN if worth else DIM),
        ("Merits earned", "{:,}".format(earned) if earned else "none yet",
         GREEN if earned else DIM),
        ("Merits/hr", "~{:,}".format(int(round(rate))) if rate else CARD_NONE,
         TEXT if rate else DIM),
    ]
    if worth:
        note = "Est. value and Cr/hr: %s." % basis
    elif est["tonnes"]:
        note = ("No price known for what is mined yet - open a commodity "
                "market, or Check prices on Where to sell.")
    else:
        note = ""
    sold = ("%s   sold so far %s Cr" if live is not None else "%s   sold %s Cr")
    return {"head": sold % (label, credits_text(est["earned"])),
            "lines": (head, value, merits), "cards": cards, "note": note}


def session_merits_earned(app, row):
    """The Powerplay merits the game paid for a session's sales, from its
    own merit events (the session ledger), or 0. Never raises."""
    try:
        ledger = attr(app, "extras", None)
        if ledger is None or not row:
            return 0
        return int(ledger.for_session(row.get("id")).get("merits") or 0)
    except Exception:
        return 0


# The system price search's worker tag (#187), routed to the Earnings window.
SYSTEM_PRICE_TAG = "system-prices"
TOOL_KEYS = {"FindWindow": "find", "SitesWindow": "sites", "LandWindow": "land",
             "EarningsWindow": "earnings", "PowerplayWindow": "powerplay",
             "LeaderboardWindow": "leaderboard"}
LB_TAG = "leaderboard"
LB_OPTIN_TAG = "leaderboard-optin"
LB_MERITS_TAG = "leaderboard-merits"
LB_STANDING_TAG = "leaderboard-standing"

# Its columns, in reading order: what, what it pays, where, then the detail.
# Markets is how many in the system buy it - with Best market only ticked,
# the one row shown is the best of that many.
PRICE_HEADERS = ("Commodity", "Sell", "Station", "Type", "Pad", "Demand",
                 "Last known", "Source", "Markets")

SYSTEM_PRICE_ADVICE = (
    "Type a system name into System - or leave it blank for the one you "
    "are in - pick commodities if you only want some, and press Search "
    "system.\n\nYou get the last known sell price of each commodity at every "
    "market there: what commanders running EDSMT read off their own markets, "
    "and what the market index last saw - whichever is newer, and it says "
    "which.")


def station_kind(kind):
    """"CraterOutpost" -> "Crater outpost"; a settlement is a settlement."""
    text = str(kind or "").strip()
    if not text:
        return "-"
    if "settlement" in text.lower():
        return "Settlement"
    words = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text).split()
    return " ".join([words[0]] + [w.lower() for w in words[1:]]) if words else "-"


def pad_size(pad):
    """The largest landing pad, as the game says it: S, M or L."""
    if isinstance(pad, str) and pad.strip().upper() in ("S", "M", "L"):
        return pad.strip().upper()
    try:
        return {1: "S", 2: "M", 3: "L"}.get(int(pad), "-")
    except (TypeError, ValueError):
        return "-"


def system_price_rows(rows, best_only=True):
    """A system's price rows, ready to show.

    Grouped by commodity, the commodity that pays most first (1.10035 - they
    came alphabetically), best price first within each, and every row told
    how many markets in the system buy that commodity. A market with Demand
    0 lists it and buys none, so it is not a row. With best_only, one row per
    commodity - the best of them.
    """
    groups, order = {}, []
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        try:
            sell = int(row.get("sell") or 0)
        except (TypeError, ValueError):
            continue
        if sell <= 0:
            continue
        demand = row.get("demand")
        try:
            if demand not in (None, "") and int(demand) <= 0:
                continue
        except (TypeError, ValueError):
            pass
        key = SV.fold(row.get("commodity"))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(dict(row, sell=sell))
    out = []
    order.sort(key=lambda key: -max(r["sell"] for r in groups[key]))
    for key in order:
        group = sorted(groups[key], key=lambda r: -r["sell"])
        for row in group:
            row["markets"] = len(group)
        out.extend(group[:1] if best_only else group)
    return out


def system_price_status(answer, rows):
    """The status line under a system search: what came back, from where."""
    system = answer.get("system") or "that system"
    status = answer.get("status") or ""
    commodities = len({SV.fold(r.get("commodity")) for r in rows})
    markets = len({SV.fold(r.get("station")) for r in answer.get("rows") or []})
    said = ("%s: %d commodit%s priced at %d market%s."
            % (system, commodities, "y" if commodities == 1 else "ies",
               markets, "" if markets == 1 else "s")) if rows else \
        "%s: no prices known." % system
    extra = {
        "unavailable": " The market index did not answer - these are "
                       "commanders' own reads only. Try again in a minute.",
        "unknown system": " The market index has never heard of a system "
                          "called that - check the spelling.",
        "server not updated": " The community map has not been updated for "
                              "system searches yet, so these are only "
                              "commanders' own reads.",
    }.get(status, "")
    return said + extra


def system_price_empty(answer):
    """What an empty system search says, in place of an empty table."""
    picked = answer.get("picked") or []
    what = (" for " + " or ".join(picked)) if picked else ""
    if answer.get("status") == "unknown system":
        return ("No system called %s is known to the market index. Check the "
                "spelling - it is the system's name, not a station's."
                % answer.get("system", "that"))
    return ("No market in %s has a known price%s.\n\nNobody running EDSMT has "
            "opened a market there, and the market index has no reading "
            "either. Dock and open the commodity market with EDSMT running "
            "and the next commander gets yours." % (answer.get("system", "it"),
                                                    what))


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
                  "to be had at deposits not marked Depleted (and, in "
                  "brackets, how many fit on them); Mined is the "
                  "tonnes refined there.")


def site_cells(site, here=("", ""), prices=None):
    """One of Survey.sites() as table cells, in SITES_HEADERS order.

    Handed prices (a dict, even an empty one), the cell for what is there
    starts with the three most valuable commodities, each once (1.10035)."""
    at = (SV.fold(site["system"]) == SV.fold(here[0])
          and SV.fold(site["body"]) == SV.fold(here[1]))
    colour = GREEN if at else None
    types = sorted(site["types"].items(), key=lambda kv: (-kv[1], kv[0].lower()))
    there = ", ".join("%s x%d" % (name, n) if n > 1 else name
                      for name, n in types)
    if prices is not None:
        best = SBK.best_commodities(list(site["types"]) + list(site["offers"]),
                                    prices)
        if len(best) > 1:
            there = "best: " + ", ".join(best) + ("\n" + there if there else "")
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
        ((str(site["rigs"]) if site["rigs"] else "-")
         + (" (fit %d)" % site["fit"] if site.get("fit") else ""), None, site["rigs"]),
        ("%dt" % tonnes if tonnes else "-", None, tonnes),
        (when, None, days if days is not None else 1e9),
    ]


def sites_matching(sites, text, commodities=()):
    """The sites whose system, body, signal or commodities hold `text`.

    Commas in `text` are alternatives - "Ega, Col 285" is either - and
    `commodities` keeps only the sites carrying any of those ticked (#188).
    """
    terms = [SV.fold(part) for part in str(text or "").split(",")]
    terms = [term for term in terms if term]
    picked = {SV.fold(name) for name in commodities or () if SV.fold(name)}
    if not terms and not picked:
        return list(sites)
    out = []
    for site in sites:
        words = [site["system"], site["body"], site["signal"]] + \
            list(site["types"]) + list(site["offers"])
        if terms and not any(term in SV.fold(word)
                             for term in terms for word in words):
            continue
        if picked and not picked & {SV.fold(name) for name in
                                    list(site["types"]) + list(site["offers"])}:
            continue
        out.append(site)
    return out


class SitesWindow(ToolWindow):
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
        self._view, self._stars, self._prices_now = "sites", set(), None

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
        tip(ctk.CTkButton(row, text="Copy all", width=100, height=32,
                      font=F_STRONG, **BTN_SECONDARY,
                      command=self.copy_all), "Copies the list as text, ready to paste into Discord.").pack(side="right")
        tip(ctk.CTkButton(row, text="Refresh", width=100, height=32,
                      font=F_STRONG, **BTN_PRIMARY,
                      command=self.refresh), "Reads your finds again.").pack(side="left")
        ctk.CTkLabel(row, text="Filter", font=F_BODY,
                     text_color=DIM).pack(side="left", padx=(14, 6))
        self.filter_box = tip(ctk.CTkEntry(row, width=260, height=32, font=F_BODY,
                                   placeholder_text="system, body or commodity",
                                   **ENTRY), "Narrows the list to a system, body or commodity.")
        self.filter_box.pack(side="left")
        self.filter_box.bind("<KeyRelease>", lambda _e: self._paint(), add="+")
        # Tick as many as you like; a site carrying any of them stays (#188).
        ctk.CTkLabel(row, text="Commodity", font=F_BODY,
                     text_color=DIM).pack(side="left", padx=(14, 6))
        self.commodity = tip(ctk.CTkComboBox(
            row, width=240, height=32, font=F_BODY, **BOX,
            values=["Any"] + list(SV.KNOWN_COMMODITIES),
            command=lambda _value: self._paint()), "Tick one or several commodities; Any clears them.")
        self.commodity.set("Any")
        self.commodity.pack(side="left")
        Suggest(self.commodity,
                lambda typed: ["Any"] + SV.matches(list(SV.KNOWN_COMMODITIES),
                                                   typed),
                on_pick=lambda _value: self._paint(), multi=True)

        # 1.10035: stars, the bin and the importer.
        extra = ctk.CTkFrame(top, fg_color="transparent")
        extra.pack(fill="x", padx=12, pady=(0, 8))
        self.fav_only = ctk.BooleanVar(value=False)
        tip(ctk.CTkCheckBox(extra, text="Favourites only", variable=self.fav_only,
                            font=F_BODY, command=self._paint),
            "Shows only the sites you have starred.").pack(side="left")
        self.bin_button = tip(ctk.CTkButton(
            extra, text="Bin", width=120, height=30, font=F_STRONG,
            **BTN_SECONDARY, command=self.toggle_bin),
            "Sites you removed wait here until they are deleted for good. Restore puts one back.")
        self.bin_button.pack(side="left", padx=(14, 0))
        self.empty_button = tip(ctk.CTkButton(
            extra, text="Empty bin", width=100, height=30, font=F_STRONG,
            **BTN_DANGER, command=self.empty_bin),
            "Deletes everything in the bin for good, after asking.")
        tip(ctk.CTkButton(extra, text="Import...", width=100, height=30,
                          font=F_STRONG, **BTN_SECONDARY,
                          command=self.open_import),
            "Brings in a bookmark database, share lines, a survey CSV or a map file from another tool.").pack(side="right")

        # 1.10035: the same body and signal filters as Where to land, judged
        # on the body each site is on.
        self._bodies = BodyFilterBar(self, top, "sites")

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
        book = self._book()
        if book is not None:
            try:
                book.purge(self.app.settings.get("trash_days"))
            except Exception as exc:
                self.say("Could not clear old sites out of the bin: %s" % exc, RED)
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
            if attr(self, "_view", "sites") == "bin":
                return self._paint_bin()
            self._sync_bin_controls()
            self._prices_now = self._market()
            self._stars = self._starred_keys()
            shown = sites_matching(self._sites, self.filter_box.get(),
                                   picks_of(self.commodity))
            shown = self._narrow(shown)
            shown = self._starred(shown)
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

    def _narrow(self, sites):
        """The sites past the body and signal filters (1.10035)."""
        bar = attr(self, "_bodies")
        return sites if bar is None else bar.narrow_sites(sites)

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
            self._more_button = tip(ctk.CTkButton(
                self.table, text="Show %d more  (%d not drawn yet)"
                % (min(PAGE_ROWS, left), left),
                font=F_STRONG, **BTN_SECONDARY, height=30,
                command=self._draw_page), "Draws the next page.")
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
            tip(ctk.CTkButton(self.table, text=text, font=F_SMALL_B,
                          **BTN_HEADING, anchor="w", height=24, width=0,
                          command=lambda c=column: self.sort_by(c)), "Click to sort by this column; click again to turn it round.").grid(
                              row=0, column=DATA_COLUMN_0 + column,
                              padx=4, pady=4, sticky="w")
        ctk.CTkLabel(self.table, text="Copy", font=F_SMALL_B,
                     text_color=ORANGE).grid(row=0, column=COPY_COLUMN,
                                             padx=8, pady=5, sticky="w")

    def _row(self, index, site, here):
        cells = site_cells(site, here, attr(self, "_prices_now", None))
        for column, cell in enumerate(cells):
            text, colour, _key = EarningsWindow._cell(cell)
            cell_label(self.table, index, column, text, colour,
                       SITES_WRAP.get(SITES_HEADERS[column], CELL_WRAP))
        line = " | ".join(EarningsWindow._cell(c)[0].replace("\n", " ")
                          for c in cells)
        buttons = [
            ("system", lambda s=site["system"]: self.copy_text(
                "the system name", s), False),
            ("row", lambda s=line: self.copy_text("this site", s), False)]
        if self._book() is not None:
            starred = SBK.key_of(site) in (attr(self, "_stars", None) or ())
            buttons += [
                ("\u2605" if starred else "\u2606",
                 lambda s=site: self.toggle_star(s), bool(starred)),
                ("remove", lambda s=site: self.remove_site(s), BTN_DANGER)]
        row_buttons(self.table, index, buttons)

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
                                    for c in site_cells(
                                        site, here, attr(self, "_prices_now", None))))
        return "\n".join(lines)

    def copy_all(self):
        block = self.as_text()
        if not block:
            return self.say("Nothing to copy yet.", AMBER)
        self.copy_text("%d site(s)" % (len(block.splitlines()) - 2), block)

    def say(self, text, colour=None):
        colour = colour or DIM
        self.status.configure(text=text, text_color=colour)

    # -- 1.10035: stars, the bin and the importer ---------------------------

    def _book(self):
        """The favourites and the bin, or None when this app has none (a
        window opened over a stand-in for the app)."""
        if getattr(type(self.app), "site_book", None) is None:
            return None
        try:
            return self.app.site_book()
        except Exception:
            return None

    def _market(self):
        """Prices for the best-three line; {} when there are none to hand."""
        if getattr(type(self.app), "market_prices", None) is None:
            return {}
        try:
            found = self.app.market_prices()
            return found if isinstance(found, dict) else {}
        except Exception:
            return {}

    def _starred_keys(self):
        book = self._book()
        try:
            return book.favourites() if book is not None else set()
        except Exception:
            return set()

    def _starred(self, sites):
        """Only the starred ones, when Favourites only is ticked."""
        try:
            wanted = bool(self.fav_only.get())
        except Exception:
            wanted = False
        if not wanted:
            return sites
        stars = attr(self, "_stars", None) or set()
        return [site for site in sites if SBK.key_of(site) in stars]

    def _refresh_app(self):
        if getattr(type(self.app), "refresh_everything", None) is not None:
            self.app.refresh_everything()

    def toggle_star(self, site):
        book = self._book()
        if book is None:
            return None
        try:
            on = book.toggle_favourite(SBK.key_of(site))
        except Exception as exc:
            return self.say("Could not star that site: %s" % exc, RED)
        self.say("%s %s signal %s." % ("Starred" if on else "Unstarred",
                                       site["body"], site["signal"] or "-"), GREEN)
        self._paint()
        return on

    def remove_site(self, site):
        """A site to the bin, with its finds and signal: out of the records
        and the maps now, deleted for good only when the bin lets it go."""
        book = self._book()
        if book is None:
            return self.say("Removing needs the full app.", AMBER)
        try:
            entry = book.remove_site(self.app.store, site["system"],
                                     site["body"], site["signal"])
        except Exception as exc:
            return self.say("Could not remove that site: %s" % exc, RED)
        if entry is None:
            return self.say("There is nothing recorded at that site to remove.", AMBER)
        days = SBK.retention_days(self.app.settings.get("trash_days"))
        self.refresh()
        self._refresh_app()
        self.say("Removed %s signal %s to the bin (%d find(s)). It stays %d "
                 "day(s); Bin has Restore." % (
                     entry["body"], entry["signal"] or "-",
                     len(entry["deposits"]), days), GREEN)
        return entry

    def toggle_bin(self):
        self._view = "sites" if attr(self, "_view", "sites") == "bin" else "bin"
        self._paint()

    def _sync_bin_controls(self):
        """The Bin button says how many are in it, or takes you back; Empty
        bin is only there while you are looking in the bin."""
        in_bin = attr(self, "_view", "sites") == "bin"
        book = self._book()
        try:
            count = book.binned() if book is not None else 0
        except Exception:
            count = 0
        try:
            self.bin_button.configure(text="Back to sites" if in_bin
                                      else "Bin (%d)" % count)
            self.empty_button.pack_forget()
            if in_bin:
                self.empty_button.pack(side="left", padx=(8, 0))
        except Exception:
            pass

    def _paint_bin(self):
        table = attr(self, "table")
        book = self._book()
        entries = book.bin() if book is not None else []
        days = SBK.retention_days(self.app.settings.get("trash_days"))
        for widget in table.winfo_children():
            widget.destroy()
        self._sync_bin_controls()
        self._bin_rows = entries
        self.summary.configure(
            text="%d removed site(s) in the bin. Each is deleted for good %d "
                 "day(s) after it was removed." % (len(entries), days))
        if not entries:
            ctk.CTkLabel(table, text="The bin is empty. A site you remove "
                                     "waits here until it is deleted for good "
                                     "- Restore puts it back.",
                         font=F_BODY, text_color=DIM, justify="left",
                         wraplength=820).grid(row=0, column=0, padx=14,
                                              pady=18, sticky="w")
            return
        for column, name in enumerate(BIN_HEADERS):
            cell_label(table, 0, column, name, ORANGE)
        for index, entry in enumerate(entries, 1):
            finds = len(entry.get("deposits") or [])
            cells = (entry.get("system") or "", entry.get("body") or "",
                     entry.get("signal") or "-", str(finds) if finds else "-",
                     str(entry.get("binned") or "")[:10],
                     "%d d" % SBK.SiteBook.days_left(entry, days))
            for column, text in enumerate(cells):
                cell_label(table, index, column, text)
            row_buttons(table, index, [
                ("restore", lambda e=entry: self.restore_entry(e), True)])

    def restore_entry(self, entry):
        book = self._book()
        if book is None:
            return None
        try:
            back = book.restore(self.app.store, entry.get("id"))
        except Exception as exc:
            return self.say("Could not restore that site: %s" % exc, RED)
        if back is None:
            return self.say("That site is no longer in the bin.", AMBER)
        self.refresh()
        self._refresh_app()
        self.say("Restored %s signal %s: %d find(s), %d signal(s)."
                 % (entry.get("body"), entry.get("signal") or "-", back[0], back[1]),
                 GREEN)
        return back

    def empty_bin(self):
        """Delete everything in the bin for good - after asking."""
        book = self._book()
        count = book.binned() if book is not None else 0
        if not count:
            return self.say("The bin is already empty.", AMBER)
        if not confirm(self, "Empty the bin?",
                       "This deletes %d removed site(s), and every find in "
                       "them, for good. They cannot be restored." % count):
            return self.say("Left the bin as it was.", AMBER)
        gone = book.empty()
        self._paint()
        return self.say("Emptied the bin: %d site(s) deleted for good." % gone, GREEN)

    def open_import(self):
        if getattr(type(self.app), "open_import", None) is None:
            return self.say("Importing needs the full app.", AMBER)
        try:
            return self.app.open_import()
        except Exception as exc:
            return self.say("Could not open the importer: %s" % exc, RED)


BIN_HEADERS = ("System", "Body", "Signal", "Finds", "Removed", "Left")
IMPORT_INTRO = ("Reads a bookmark database (.db), share lines pasted from a "
                "chat, a survey CSV or a surveyed-body map (.json), and "
                "recognises each by what is inside it. Nothing is sent back to "
                "the other tool. Your records are backed up first, and a find "
                "you already have is never changed: the same commodity within "
                "%d m of one is the same find." % SAME_DEPOSIT_M)
NO_COMMODITY_CHOICE = "(none - skip them)"


def confirm(window, title, text):
    """Ask yes or no; True on yes. A function of its own so a test can
    answer it without a dialogue box."""
    try:
        from tkinter import messagebox
        return bool(messagebox.askyesno(title, text, parent=window))
    except Exception:
        return False


class ImportWindow(ctk.CTkToplevel):
    """Bringing finds in from another tool, with a preview first (1.10035)."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("EDSMT - Import from another tool")
        width, height = screen_fraction(self, 0.5, 0.75, 780, 760, 560, 520)
        self.geometry("%dx%d" % (width, height))
        self.minsize(520, 460)
        self.configure(fg_color=VOID)
        self.transient(app)
        self._path, self._source, self._plan = "", None, None

        top = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        top.pack(fill="x", padx=12, pady=(12, 6))
        bracket(top, colour=ORANGE)
        hud_header(top, "Import from another tool", padx=12, pady=(12, 4))
        self.intro = ctk.CTkLabel(top, text=IMPORT_INTRO, font=F_BODY,
                                  text_color=DIM, anchor="w", justify="left",
                                  wraplength=700)
        self.intro.pack(fill="x", padx=12, pady=(2, 8))
        pick = ctk.CTkFrame(top, fg_color="transparent")
        pick.pack(fill="x", padx=12, pady=(0, 6))
        tip(ctk.CTkButton(pick, text="Choose a file...", width=140, height=32,
                          font=F_STRONG, **BTN_PRIMARY, command=self.choose_file),
            "A bookmark database, survey CSV or map file.").pack(side="left")
        self.path_label = ctk.CTkLabel(pick, text="no file chosen", font=F_SMALL,
                                       text_color=DIM, anchor="w")
        self.path_label.pack(side="left", padx=10)
        ctk.CTkLabel(top, text="Or paste share lines here (the text of a "
                               "survey CSV or a map file works too):",
                     font=F_BODY, text_color=TEXT, anchor="w").pack(
                         fill="x", padx=12, pady=(4, 2))
        self.paste = ctk.CTkTextbox(top, height=96, font=F_SMALL, **TEXTBOX)
        self.paste.pack(fill="x", padx=12, pady=(0, 6))
        choice = ctk.CTkFrame(top, fg_color="transparent")
        choice.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(choice, text="Commodity for deposits that do not name one",
                     font=F_BODY, text_color=DIM).pack(side="left")
        self.default_box = tip(ctk.CTkComboBox(
            choice, width=220, height=30, font=F_BODY, state="readonly", **BOX,
            values=[NO_COMMODITY_CHOICE] + list(SV.KNOWN_COMMODITIES),
            command=lambda _value: self.preview()),
            "A map file records where deposits are, not what they are. Pick one to take them as.")
        self.default_box.set(NO_COMMODITY_CHOICE)
        self.default_box.pack(side="left", padx=10)
        buttons = ctk.CTkFrame(top, fg_color="transparent")
        buttons.pack(fill="x", padx=12, pady=(0, 10))
        tip(ctk.CTkButton(buttons, text="Preview", width=110, height=32,
                          font=F_STRONG, **BTN_SECONDARY, command=self.preview),
            "Reads it and says what would be added. Nothing is changed.").pack(side="left")
        self.import_button = tip(ctk.CTkButton(
            buttons, text="Import", width=110, height=32, font=F_STRONG,
            **BTN_PRIMARY, command=self.do_import),
            "Backs up your records, then adds the new finds.")
        self.import_button.pack(side="left", padx=10)
        self.import_button.configure(state="disabled")

        self.result = ctk.CTkLabel(self, text="", font=F_READOUT, text_color=TEXT,
                                   anchor="nw", justify="left", wraplength=720)
        self.result.pack(fill="x", padx=16, pady=(6, 4))
        self.status = ctk.CTkLabel(self, text="", font=F_READOUT, text_color=DIM,
                                   anchor="w")
        self.status.pack(side="bottom", fill="x", padx=14, pady=(0, 10))
        self.bind("<Configure>", self._rewrap, add="+")

    def _rewrap(self, event=None):
        try:
            if event is not None and event.widget is not self:
                return
            wrap = max(360, self.winfo_width() - 70)
            for label in (self.intro, self.result):
                label.configure(wraplength=wrap)
        except Exception:
            pass

    def say(self, text, colour=None):
        self.status.configure(text=text, text_color=colour or DIM)

    def _default(self):
        try:
            value = self.default_box.get()
        except Exception:
            return ""
        return "" if value == NO_COMMODITY_CHOICE else value

    def choose_file(self):
        try:
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                parent=self, title="Which file?",
                filetypes=[("Bookmark database, survey CSV or map",
                            "*.db *.sqlite *.csv *.json"), ("Any file", "*.*")],
                initialdir=os.path.expanduser("~"))
        except Exception:
            path = ""
        if not path:
            return None
        self._path = path
        self.path_label.configure(text=os.path.basename(path))
        return self.preview()

    def _read(self):
        text = self.paste.get("1.0", "end").strip()
        if text:
            return IMP.read_text(text, self._default(), MAX_RIGS), "pasted text"
        if self._path:
            return (IMP.read_path(self._path, self._default(), MAX_RIGS),
                    os.path.basename(self._path))
        return None, ""

    def preview(self):
        """Read the source and say what would happen. Changes nothing."""
        self._plan = None
        self.import_button.configure(state="disabled")
        try:
            source, where = self._read()
            if source is None:
                self.result.configure(text="", text_color=TEXT)
                return self.say("Choose a file or paste something first.", AMBER)
            self._source = source
            if source.error:
                self.result.configure(text=source.error, text_color=RED)
                return self.say("Nothing to import.", AMBER)
            plan = IMP.make_plan(source, self.app.store, SAME_DEPOSIT_M,
                                self._default())
            self._plan = plan
            lines = ["%s: %d row(s) read from %s." % (source.label, source.rows, where),
                     plan.preview()]
            lines.extend(source.notes)
            if plan.new:
                lines.append(IMP.sharing_line(
                    getattr(self.app, "settings", None) or {},
                    attr(self.app, "community"), ALWAYS_SHARED))
            self.result.configure(text="\n".join(lines), text_color=TEXT)
            self.import_button.configure(state="normal" if plan.new else "disabled")
            return self.say("Preview only - nothing has been changed." if plan.new
                            else "Nothing new to add.", DIM if plan.new else AMBER)
        except Exception as exc:
            self.result.configure(text="", text_color=TEXT)
            return self.say("Could not read that: %s" % exc, RED)

    def do_import(self):
        """Backup, then add - worked out afresh, so a click made after the
        records changed still cannot add a find twice."""
        if self._plan is None or self._source is None:
            return self.say("Preview something with new finds in it first.", AMBER)
        try:
            plan = IMP.make_plan(self._source, self.app.store, SAME_DEPOSIT_M,
                                self._default())
            result = IMP.apply(plan, self.app.store, DATA_DIR, SAME_DEPOSIT_M)
        except Exception as exc:
            return self.say("Could not import that: %s" % exc, RED)
        line = IMP.summary(result, plan)
        if not result["ok"]:
            return self.say(line, RED)
        sent = self.app.share_imported(result["records"]) if result["records"] else 0
        if sent:
            line += " %d shared with the community map." % sent
        self._plan = None
        self.import_button.configure(state="disabled")
        self.result.configure(text=line, text_color=TEXT)
        self.say(line, GREEN)
        self.app.refresh_everything()
        try:
            sites = attr(self.app, "sites_window")
            if sites is not None and sites.winfo_exists():
                sites.refresh()
        except Exception:
            pass
        return result


class MapFilterWindow(ctk.CTkToplevel):
    """Which deposits the map and the scope draw (1.10035). What is chosen
    is written to the settings, so it is there next time."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("EDSMT - Map and scope filters")
        self.geometry("520x330")
        self.minsize(460, 300)
        self.configure(fg_color=VOID)
        self.transient(app)
        flt = MF.from_settings(getattr(app, "settings", None) or {})

        top = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        top.pack(fill="both", expand=True, padx=12, pady=12)
        bracket(top, colour=ORANGE)
        hud_header(top, "Map and scope filters", padx=12, pady=(12, 4))
        ctk.CTkLabel(top, text="A deposit whose amount or density has not been "
                               "read stays on the map.", font=F_SMALL,
                     text_color=DIM, anchor="w", justify="left").pack(
                         fill="x", padx=12, pady=(0, 6))
        row = ctk.CTkFrame(top, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=3)
        ctk.CTkLabel(row, text="Commodities", width=110, anchor="w", font=F_BODY,
                     text_color=TEXT).pack(side="left")
        self.commodity = tip(ctk.CTkComboBox(
            row, width=300, height=30, font=F_BODY, **BOX,
            values=["Any"] + list(SV.KNOWN_COMMODITIES)),
            "Tick one or several; Any shows them all.")
        self.commodity.set(pick_text(flt["commodities"], "Any"))
        self.commodity.pack(side="left", fill="x", expand=True)
        Suggest(self.commodity,
                lambda typed: ["Any"] + SV.matches(list(SV.KNOWN_COMMODITIES), typed),
                multi=True)
        self.amount = self._choice(top, "Amount", MF.AMOUNT_CHOICES, flt["amount"])
        self.density = self._choice(top, "Density", MF.DENSITY_CHOICES, flt["density"])
        self.labels = ctk.BooleanVar(value=flt["labels"])
        tip(ctk.CTkCheckBox(top, text="Write names beside the deposits",
                            variable=self.labels, font=F_BODY),
            "Off draws the dots alone, on the map and the scope.").pack(
                anchor="w", padx=12, pady=6)
        buttons = ctk.CTkFrame(top, fg_color="transparent")
        buttons.pack(fill="x", padx=12, pady=(4, 6))
        tip(ctk.CTkButton(buttons, text="Apply", width=100, height=32,
                          font=F_STRONG, **BTN_PRIMARY, command=self.apply),
            "Uses these and remembers them.").pack(side="left")
        tip(ctk.CTkButton(buttons, text="Show everything", width=150, height=32,
                          font=F_STRONG, **BTN_SECONDARY, command=self.clear),
            "Clears the filters and puts the names back.").pack(side="left", padx=8)
        self.status = ctk.CTkLabel(top, text=MF.describe(flt), font=F_READOUT,
                                   text_color=DIM, anchor="w", justify="left",
                                   wraplength=460)
        self.status.pack(fill="x", padx=12, pady=(4, 8))

    def _choice(self, parent, label, choices, current):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=3)
        ctk.CTkLabel(row, text=label, width=110, anchor="w", font=F_BODY,
                     text_color=TEXT).pack(side="left")
        box = ctk.CTkComboBox(row, width=200, height=30, font=F_BODY,
                              state="readonly", values=list(choices), **BOX)
        box.set(current)
        box.pack(side="left")
        return box

    def apply(self):
        values = MF.to_settings(picks_of(self.commodity), self.amount.get(),
                                self.density.get(), self.labels.get())
        self.app.settings.update(values)
        try:
            save_settings(self.app.settings)
        except Exception as exc:
            return self.say("Could not save these: %s" % exc, RED)
        self.app.redraw()
        return self.say(MF.describe(MF.from_settings(values)), GREEN)

    def clear(self):
        self.commodity.set("Any")
        self.amount.set(MF.AMOUNT_CHOICES[0])
        self.density.set(MF.DENSITY_CHOICES[0])
        self.labels.set(True)
        return self.apply()

    def say(self, text, colour=None):
        self.status.configure(text=text, text_color=colour or DIM)


# ---------------------------------------------------------------------------
# Searching (1.10035): Find's price filters, the body and signal filters of
# Where to land and My sites, and the Powerplay window. What a filter keeps is
# decided in finder.py and powerplay.py; this is the widgets and the glue.
# ---------------------------------------------------------------------------

FROM_CHOICES = (("Any", None), ("25 Ly", 25.0), ("50 Ly", 50.0),
                ("100 Ly", 100.0), ("200 Ly", 200.0), ("500 Ly", 500.0))
POWER_ROW_CAP = 400
POWER_TABLE_WRAP = {"Why": 380}
# Where to land, when it is asked about more than the system you are in.
LAND_FAR_HEADERS = ("Body", "System", "Ly", "Ls", "Type", "Volcanism",
                    "Gravity", "Temp", "Signals", "Landable", "Mapped")
SELL_HEADERS = ("Commodity", "Aboard", "Station", "System", "Ly", "Sell",
                "Demand", "Price age", "Pad", "Type", "Powerplay")
SYSTEM_HEADERS = ("System", "Ly from here", "Power", "State", "Selling here",
                  "Why")
SAVED_PLACEHOLDER = "Saved searches"


def filter_label(row, text, first=False):
    label = ctk.CTkLabel(row, text=text, font=F_BODY, text_color=DIM)
    label.pack(side="left", padx=(0 if first else 12, 6))
    return label


def filter_combo(row, values, width, hint, change, current=None):
    """A drop-down that redraws when it changes, and opens on a click or Tab
    like the rest of Find."""
    values = list(values)
    box = tip(ctk.CTkComboBox(row, width=width, font=F_BODY, **BOX,
                              values=values,
                              command=lambda _value: change()), hint)
    box.set(values[0] if current is None else current)
    box.pack(side="left")
    Suggest(box, values, on_pick=lambda _value: change())
    return box


def filter_picks(row, values, width, hint, change):
    """A list you tick several of; Any clears them."""
    values = list(values)
    box = tip(ctk.CTkComboBox(row, width=width, font=F_BODY, **BOX,
                              values=["Any"] + values,
                              command=lambda _value: change()), hint)
    box.set("Any")
    box.pack(side="left")
    Suggest(box, lambda typed: ["Any"] + SV.matches(values, typed),
            on_pick=lambda _value: change(), multi=True)
    return box


def filter_entry(row, width, hint, holder, change):
    box = tip(ctk.CTkEntry(row, width=width, height=30, font=F_BODY, **ENTRY,
                           placeholder_text=holder), hint)
    box.pack(side="left")
    box.bind("<KeyRelease>", lambda _e: change())
    return box


def entry_number(box):
    """The number typed in a box - "1,500", "100k" - or None."""
    return FD.parse_number(box.get(), None)


def set_entry(box, text):
    box.delete(0, "end")
    if text not in (None, ""):
        box.insert(0, str(text))


def set_picks(box, names):
    """Tick exactly these in a multi-pick box."""
    box.set(pick_text(list(names)))
    suggest = getattr(box, "suggest", None)
    if suggest is not None:
        suggest.tidy()


class SavedRow:
    """The Saved row of a filter panel: choose a saved search to load it,
    type a name and press Save to keep the filters as they stand, Delete,
    and Reset to put everything back as the window opens (1.10035).

    The searches are in the app's searches.json, a file of their own beside
    the other records; a window with none to hand says so rather than
    pretending to have saved."""

    def __init__(self, parent, app, key, snapshot, restore, reset):
        self.app, self.key = app, key
        self.snapshot, self.restore, self.reset = snapshot, restore, reset
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 4))
        filter_label(row, "Saved", first=True)
        self.pick_box = tip(ctk.CTkComboBox(
            row, width=220, font=F_BODY, **BOX, values=[SAVED_PLACEHOLDER],
            command=self.load), "Choose a saved search to load every filter in it.")
        self.pick_box.set(SAVED_PLACEHOLDER)
        self.pick_box.pack(side="left")
        self.name_box = tip(ctk.CTkEntry(
            row, width=170, height=30, font=F_BODY, **ENTRY,
            placeholder_text="name this search"),
            "Type a name, then Save, to keep these filters.")
        self.name_box.pack(side="left", padx=(8, 4))
        tip(ctk.CTkButton(row, text="Save", width=64, height=30, font=F_STRONG,
                          **BTN_PRIMARY, command=self.save),
            "Keeps every filter as it stands under that name.").pack(side="left", padx=4)
        tip(ctk.CTkButton(row, text="Delete", width=70, height=30,
                          font=F_STRONG, **BTN_SECONDARY, command=self.delete),
            "Deletes the saved search chosen on the left.").pack(side="left", padx=4)
        tip(ctk.CTkButton(row, text="Reset", width=70, height=30,
                          font=F_STRONG, **BTN_SECONDARY, command=self.reset),
            "Puts every filter back to how the window opens.").pack(side="left", padx=4)
        self.message = ctk.CTkLabel(row, text="", font=F_SMALL, text_color=DIM,
                                    anchor="w")
        self.message.pack(side="left", padx=(10, 0))
        self.refresh_names()

    def book(self):
        return attr(self.app, "searches")

    def say(self, text, colour=None):
        self.message.configure(text=text, text_color=colour or DIM)

    def refresh_names(self, current=None):
        book = self.book()
        names = book.names(self.key) if book is not None else []
        self.pick_box.configure(values=names or [SAVED_PLACEHOLDER])
        self.pick_box.set(current if current in names else SAVED_PLACEHOLDER)

    def save(self):
        book = self.book()
        if book is None:
            return self.say("Saved searches are not available in this build.", AMBER)
        name = book.tidy(self.name_box.get())
        if not name:
            return self.say("Type a name for this search first.", AMBER)
        if not book.put(name, self.snapshot(), window=self.key):
            return self.say("Could not save it - %d saved searches is the most "
                            "kept." % FD.SEARCHES_MAX, RED)
        self.refresh_names(name)
        self.say('Saved "%s".' % name, GREEN)

    def load(self, name):
        book = self.book()
        state = book.get(name) if book is not None else None
        if state is None:
            return False
        self.restore(state)
        self.say('Loaded "%s".' % name, GREEN)
        return True

    def delete(self):
        book = self.book()
        name = self.pick_box.get()
        if book is not None and book.delete(name):
            self.refresh_names()
            return self.say('Deleted "%s".' % name, GREEN)
        self.say("Choose a saved search to delete first.", AMBER)


class SavedMenu:
    """Find's saved searches as one Saved button beside Reset (1.10038). Its
    menu saves the filters as they stand under a name, loads a saved search
    - with the search it was saved on - or deletes one. What happened goes
    on the window's status line; there is no row of its own any more.

    The searches are in the app's searches.json, as before. `ask` gives the
    name for a new one - a small box asks for it - and can be replaced."""

    def __init__(self, parent, app, key, snapshot, restore, say):
        self.app, self.key = app, key
        self.snapshot, self.restore, self.say = snapshot, restore, say
        self.ask = self._ask_name
        self.menu = self.delete_menu = None
        self.button = tip(ctk.CTkButton(
            parent, text="Saved", width=90, height=32, font=F_STRONG,
            **BTN_SECONDARY, command=self.open),
            "Save these filters under a name, load a saved search, or delete one.")

    def book(self):
        return attr(self.app, "searches")

    def names(self):
        book = self.book()
        return list(book.names(self.key)) if book is not None else []

    def build_menu(self):
        """The menu as it stands now: Save these filters, each saved search
        (choose one to load it), then Delete with each of them again."""
        for old in (self.delete_menu, self.menu):
            try:
                if old is not None:
                    old.destroy()
            except Exception:
                pass
        style = dict(tearoff=0, bg=PANEL, fg=TEXT, activebackground=ORANGE,
                     activeforeground=VOID, disabledforeground=DIM, font=F_BODY)
        menu = self.menu = tk.Menu(self.button, **style)
        menu.add_command(label="Save these filters...", command=self.save)
        self.delete_menu = tk.Menu(menu, **style)
        names = self.names()
        if not names:
            menu.add_command(label="No saved searches yet", state="disabled")
            return menu
        menu.add_separator()
        for name in names:
            menu.add_command(label=name, command=lambda n=name: self.load(n))
            self.delete_menu.add_command(label=name,
                                         command=lambda n=name: self.delete(n))
        menu.add_separator()
        menu.add_cascade(label="Delete", menu=self.delete_menu)
        return menu

    def open(self):
        menu = self.build_menu()
        try:
            menu.tk_popup(self.button.winfo_rootx(),
                          self.button.winfo_rooty() + self.button.winfo_height())
        except Exception:
            pass
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    @staticmethod
    def _ask_name():
        dialog = ctk.CTkInputDialog(
            title="EDSMT - Save this search", text="A name for these filters:",
            font=F_BODY, fg_color=VOID, text_color=TEXT, button_fg_color=ORANGE,
            button_hover_color=AMBER, button_text_color=VOID,
            entry_fg_color=STEEL, entry_border_color=RULE, entry_text_color=TEXT)
        return dialog.get_input()

    def save(self, name=None):
        book = self.book()
        if book is None:
            return self.say("Saved searches are not available in this build.", AMBER)
        if name is None:
            name = self.ask()
        name = book.tidy(name)
        if not name:
            return self.say("Not saved - a saved search needs a name.", AMBER)
        if not book.put(name, self.snapshot(), window=self.key):
            return self.say("Could not save it - %d saved searches is the most "
                            "kept." % FD.SEARCHES_MAX, RED)
        self.say('Saved "%s".' % name, GREEN)

    def load(self, name):
        book = self.book()
        state = book.get(name) if book is not None else None
        if state is None:
            self.say('No saved search is called "%s".' % name, AMBER)
            return False
        self.restore(state)
        self.say('Loaded "%s".' % name, GREEN)
        return True

    def delete(self, name):
        book = self.book()
        if book is not None and book.delete(name):
            return self.say('Deleted "%s".' % name, GREEN)
        self.say('No saved search is called "%s".' % name, AMBER)


class FindFilters:
    """Find's second set of filters, at the level of the sites that built
    this kind of search (1.10035): a distance window, pad size, price age,
    demand window, a minimum price, station type with a no-fleet-carriers
    switch, Powerplay state and side, the best five of each commodity, saved
    searches and Reset. Which rows stay is finder.why_hidden's decision; the
    count line gives the reason for every row hidden."""

    def __init__(self, window, parent, lead=None, actions=None):
        self.window = window
        self.counts = {}
        self._building = True
        # 1.10038: the two rows go straight into Find's filter box, so the
        # window can show them for Sell prices only, and From goes on the
        # `lead` row beside Within. The saved searches are a menu button in
        # `actions`, the row with Search on it.
        self.labels, self.rows, self.parts = {}, [], []

        def line():
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=(0, 8))
            self.rows.append(row)
            self.parts.append([])
            return row

        def part(key, *widgets):
            self.parts[-1].extend((widget, key) for widget in widgets)

        one = line()
        home = one if lead is None else lead
        self.labels["from"] = filter_label(home, "From", first=True)
        self.far_box = filter_combo(
            home, [n for n, _v in FROM_CHOICES], 96,
            "Only rows at least this far away, for when the close ones are no use.",
            self.changed)
        if lead is None:
            part("from", self.labels["from"], self.far_box)
        else:
            # Spaced like the boxes it sits among.
            self.labels["from"].pack(side="left")
            self.far_box.pack(side="left", padx=(6, 14))
        label = filter_label(one, "Pad", first=lead is not None)
        self.pad_box = filter_combo(
            one, [n for n, _k in FD.PAD_CHOICES], 120,
            "The smallest landing pad that will do. A price that does not say "
            "its pad is hidden once this is on.", self.changed)
        part("pad", label, self.pad_box)
        label = filter_label(one, "Price age")
        self.age_box = filter_combo(
            one, [n for n, _s in FD.PRICE_AGES], 110,
            "Only prices read this recently. An undated price is hidden "
            "once this is on.", self.changed)
        part("price_age", label, self.age_box)
        label = filter_label(one, "Min price")
        self.price_box = filter_entry(one, 90, "Only prices at least this many "
                                      "credits a tonne. 100k works.", "Cr / t",
                                      self.changed)
        part("min_price", label, self.price_box)
        label = filter_label(one, "Demand")
        self.demand_low = filter_entry(one, 80, "Only stations that want at "
                                       "least this many tonnes.", "at least",
                                       self.changed)
        to = filter_label(one, "to")
        self.demand_high = filter_entry(one, 80, "Only stations that want no "
                                        "more than this many tonnes.",
                                        "at most", self.changed)
        part("demand", label, self.demand_low, to, self.demand_high)
        two = line()
        label = filter_label(two, "Station", first=True)
        self.station_box = filter_combo(
            two, [n for n, _k in FD.STATION_CHOICES], 140,
            "The kind of station. A row that does not say what it is is "
            "hidden once this is on.", self.changed)
        part("station", label, self.station_box)
        self.carriers_off = ctk.BooleanVar(value=True)
        self.carriers_box = tip(ctk.CTkCheckBox(
            two, width=170, text="No fleet carriers", variable=self.carriers_off,
            onvalue=True, offvalue=False, font=F_BODY, checkbox_width=18,
            checkbox_height=18, border_width=2, fg_color=ORANGE,
            hover_color=AMBER, text_color=DIM, command=self.changed),
            "Leaves fleet carrier markets out.")
        self.carriers_box.pack(side="left", padx=(12, 0))
        part("carriers", self.carriers_box)
        label = filter_label(two, "Powerplay state")
        self.power_state_box = filter_combo(
            two, FD.POWER_STATES, 120,
            "Only systems in that Powerplay state, from the systems your "
            "journal has been in. Anywhere you have not been is hidden once "
            "this is on.", self.changed)
        part("power_state", label, self.power_state_box)
        label = filter_label(two, "Side")
        self.power_side_box = filter_combo(
            two, [n for n, _k in FD.POWER_SIDES], 130,
            "Your Power's systems, another Power's, or nobody's.", self.changed)
        part("power_side", label, self.power_side_box)
        label = filter_label(two, "Show")
        self.show_box = filter_combo(
            two, [n for n, _k in FD.SHOW_CHOICES], 250,
            "All the rows, or only the five best payers - or the five "
            "nearest buyers - of each commodity.", self.changed)
        part("show", label, self.show_box)
        self.saved = SavedMenu(parent if actions is None else actions, window.app,
                               "find", self.snapshot, self.restore, window.say)
        self._building = False

    # -- reading the boxes ---------------------------------------------------

    def changed(self):
        if not self._building:
            self.window._paint()

    def spec(self, mode=None):
        """The filters as finder.py takes them. With a mode (1.10038), only
        the ones that search shows: a filter out of sight does not act."""
        far = dict(FROM_CHOICES).get(self.far_box.get())
        if far is None:
            far = entry_number(self.far_box)
        try:
            near = DISTANCE_CHOICES.get(self.window.within.get(), 0)
        except Exception:
            near = 0
        spec = FD.find_spec(
            from_ly=far or None, to_ly=near or None,
            pad=dict(FD.PAD_CHOICES).get(self.pad_box.get(), ""),
            age_s=dict(FD.PRICE_AGES).get(self.age_box.get(), 0),
            min_price=entry_number(self.price_box),
            min_demand=entry_number(self.demand_low),
            max_demand=entry_number(self.demand_high),
            station=dict(FD.STATION_CHOICES).get(self.station_box.get(), ""),
            no_carriers=bool(self.carriers_off.get()),
            state="" if self.power_state_box.get() == "Any"
            else self.power_state_box.get(),
            power=dict(FD.POWER_SIDES).get(self.power_side_box.get(), ""),
            show=dict(FD.SHOW_CHOICES).get(self.show_box.get(), ""))
        return FD.mode_spec(spec, mode) if mode else spec

    def active(self):
        """The filters that are on, in plain words (for the empty-table advice)."""
        win = self.window
        return FD.active_filters(self.spec(FD.mode_of_kind(win._kind)
                                           or attr(win, "mode", None)))

    def narrow(self, rows, kind):
        """The rows that pass, with the reason for every one that did not
        kept in self.counts for the count line."""
        spec = self.spec(FD.mode_of_kind(kind))
        app = self.window.app
        book = attr(app, "powerbook")
        power_of = book.entry if book is not None else None
        mine = book.power if book is not None else ""
        now = time.time()
        self.counts, kept = {}, []
        for row in rows:
            why = FD.why_hidden(row, spec, kind, now, power_of, mine)
            if why:
                self.counts[why] = self.counts.get(why, 0) + 1
            else:
                kept.append(row)
        if spec.get("show") and kind in PRICE_KINDS:
            best = FD.top_per_commodity(kept, 5, spec["show"])
            if len(best) != len(kept):
                self.counts["top"] = len(kept) - len(best)
            kept = best
        return kept

    # -- the columns the filters are about -----------------------------------

    def widen(self, headers, builder, kind):
        """Headers and a row builder with the columns the filters act on
        added after the ones the table already had."""
        extra_heads, extra_cells = [], []
        if kind in PRICE_KINDS:
            extra_heads += ["Pad", "Station type", "Price age"]
            extra_cells.append(self._price_cells)
        book = attr(self.window.app, "powerbook")
        if kind in PRICE_KINDS + FIND_KINDS and book is not None \
                and book.systems:
            extra_heads.append("Powerplay")
            extra_cells.append(self._power_cells)
        if not extra_heads:
            return headers, builder

        def wide(row):
            cells = list(builder(row))
            for make in extra_cells:
                cells.extend(make(row))
            return cells
        return list(headers) + extra_heads, wide

    @staticmethod
    def _price_cells(row):
        rank = FD.pad_rank(row.get("pad"))
        group = FD.station_group(row.get("station_type"), row.get("station"))
        kind = station_kind(row.get("station_type"))
        if kind == "-" and group == "carrier":
            kind = "Fleet carrier"
        words, age = price_age(row.get("seen"))
        shade = DIM if age is None else GREEN if age < PRICE_STALE_S else AMBER
        return [(pad_size(row.get("pad")), None, rank),
                (kind, RED if group == "carrier" else None, kind.lower()),
                (words, shade, age if age is not None else 1e12)]

    def _power_cells(self, row):
        book = attr(self.window.app, "powerbook")
        entry = book.entry(row.get("system")) if book is not None else None
        if not entry or not entry.get("state"):
            return [("-", DIM, "")]
        text = "%s - %s" % (entry["state"], entry.get("power") or "no Power")
        mine = book.power and str(entry.get("power")).lower() == book.power.lower()
        return [(text, GREEN if mine else None, text.lower())]

    # -- saved searches ------------------------------------------------------

    def snapshot(self):
        """Every filter in the window as it stands, ready to save."""
        win = self.window
        sort = None
        if win._sort_column is not None and win._sort_column < len(win._headers):
            sort = [win._headers[win._sort_column], bool(win._sort_reverse)]
        return {
            "far": self.far_box.get(), "pad": self.pad_box.get(),
            "age": self.age_box.get(), "price": self.price_box.get(),
            "demand_low": self.demand_low.get(),
            "demand_high": self.demand_high.get(),
            "station": self.station_box.get(),
            "carriers_off": bool(self.carriers_off.get()),
            "power_state": self.power_state_box.get(),
            "power_side": self.power_side_box.get(),
            "show": self.show_box.get(), "commodity": win._commodities(),
            "min_rigs": win.min_rigs.get(), "min_types": win.min_types.get(),
            "max_age": win.max_age.get(), "within": win.within.get(),
            "text": win._text(),
            "hide_worked": win._flag(win.hide_worked, True),
            "only_verified": win._flag(win.only_verified), "sort": sort,
            # The search it was saved on (1.10038).
            "mode": attr(win, "mode", None) or FD.DEFAULT_MODE}

    def restore(self, state):
        """Put the window back as a saved search had it. Anything the saved
        search does not mention goes back to how the window opens - except
        the search on show, which only a search saved with one changes."""
        state = state or {}
        win = self.window
        if state.get("mode") and attr(win, "mode", None) is not None:
            win.set_mode(state["mode"])
        self._building = True
        try:
            for box, key, fallback in (
                    (self.far_box, "far", FROM_CHOICES[0][0]),
                    (self.pad_box, "pad", FD.PAD_CHOICES[0][0]),
                    (self.age_box, "age", FD.PRICE_AGES[0][0]),
                    (self.station_box, "station", FD.STATION_CHOICES[0][0]),
                    (self.power_state_box, "power_state", FD.POWER_STATES[0]),
                    (self.power_side_box, "power_side", FD.POWER_SIDES[0][0]),
                    (self.show_box, "show", FD.SHOW_CHOICES[0][0]),
                    (win.min_rigs, "min_rigs", "0"),
                    (win.min_types, "min_types", "0"),
                    (win.max_age, "max_age", "Any time"),
                    (win.within, "within", DEFAULT_DISTANCE)):
                box.set(str(state.get(key) or fallback))
            for box, key in ((self.price_box, "price"),
                             (self.demand_low, "demand_low"),
                             (self.demand_high, "demand_high"),
                             (win.query, "text")):
                set_entry(box, state.get(key))
            self.carriers_off.set(bool(state.get("carriers_off", True)))
            win.hide_worked.set(bool(state.get("hide_worked", True)))
            win.only_verified.set(bool(state.get("only_verified", False)))
            set_picks(win.commodity, state.get("commodity") or [])
        finally:
            self._building = False
        sort = state.get("sort")
        win._want_sort = tuple(sort) if isinstance(sort, (list, tuple)) \
            and len(sort) == 2 else None
        win._restore_sort()
        win._paint()

    def reset(self):
        self.restore({})
        self.window.say("Every filter is back to how the window opens.", GREEN)


BODY_FILTER_HINT = ("Search bodies by type, volcanism, gravity, temperature and "
                    "signals - in this system, or in every system your "
                    "journals have been to.")


class BodyFilterBar:
    """The body and signal filters of Where to land and My sites (1.10035):
    body type, volcanism, gravity and temperature ranges, signal types and
    counts, landable, mapped, distance from the star - over this system,
    near here, or every system the body book remembers.

    A body nobody has measured does not pass a filter that needs the
    measurement; the line under the title says how many were left out and
    why. Where to land shows a body from another system in a table of its
    own (LAND_FAR_HEADERS); My sites keeps its table and filters it."""

    def __init__(self, window, parent, kind):
        self.window = window
        self.kind = kind
        self.counts = {}
        self.expanded = False
        self._building = True
        self.scopes = FD.SCOPES if kind == "land" else FD.SITE_SCOPES
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        panel.pack(fill="x", padx=12, pady=(0, 8))
        head = ctk.CTkFrame(panel, fg_color="transparent")
        head.pack(fill="x")
        self.toggle_button = tip(ctk.CTkButton(
            head, text="Body filters  +", width=140, height=28, font=F_STRONG,
            **BTN_SECONDARY, command=self.toggle), BODY_FILTER_HINT)
        self.toggle_button.pack(side="left")
        self.line = ctk.CTkLabel(head, text="", font=F_READOUT, text_color=DIM,
                                 anchor="w", justify="left")
        self.line.pack(side="left", fill="x", expand=True, padx=(12, 0))
        self.detail = ctk.CTkFrame(panel, fg_color="transparent")

        def row():
            made = ctk.CTkFrame(self.detail, fg_color="transparent")
            made.pack(fill="x", pady=(0, 4))
            return made

        one = row()
        filter_label(one, "Look in", first=True)
        self.scope_box = filter_combo(
            one, [n for n, _k in self.scopes], 190,
            "Which bodies to search: this system, the ones near here, or every "
            "body your journals have described.", self.changed)
        filter_label(one, "Within")
        self.within_box = filter_combo(
            one, list(FD.NEAR_LY), 100, "How far counts as near here. Needs "
            "the position of the systems, which your journals give.",
            self.changed, "100 Ly")
        filter_label(one, "Type")
        self.type_box = filter_picks(
            one, [n for n, _f in FD.BODY_SHORT], 170,
            "Tick the kinds of body to keep.", self.changed)
        filter_label(one, "Volcanism")
        self.volc_box = filter_picks(
            one, FD.VOLCANISM_CHOICES[1:], 190,
            "Tick the kinds of volcanism to keep. None means no volcanism; "
            "a body the scan has not described is not None.", self.changed)
        two = row()
        filter_label(two, "Signals", first=True)
        self.signal_box = filter_picks(
            two, FD.SIGNAL_CHOICES[1:], 190,
            "Bodies carrying every ticked kind of signal.", self.changed)
        filter_label(two, "at least")
        self.signal_min_box = filter_combo(
            two, [str(n) for n in range(1, 10)], 60,
            "How many of each ticked signal a body needs.", self.changed)
        filter_label(two, "Gravity g")
        self.g_low = filter_entry(two, 70, "Lowest gravity, in g.", "from",
                                  self.changed)
        filter_label(two, "to")
        self.g_high = filter_entry(two, 70, "Highest gravity, in g.", "to",
                                   self.changed)
        filter_label(two, "Temperature K")
        self.k_low = filter_entry(two, 70, "Lowest surface temperature, in "
                                  "kelvin.", "from", self.changed)
        filter_label(two, "to")
        self.k_high = filter_entry(two, 70, "Highest surface temperature, in "
                                   "kelvin.", "to", self.changed)
        three = row()
        filter_label(three, "Up to", first=True)
        self.ls_box = filter_entry(three, 80, "How far from the star, in light "
                                   "seconds, at most.", "Ls", self.changed)
        self.landable_var = ctk.BooleanVar(value=False)
        self.mapped_var = ctk.BooleanVar(value=False)
        for text, var, hint in (
                ("Landable", self.landable_var, "Only bodies you can land on."),
                ("Mapped", self.mapped_var, "Only bodies mapped with the DSS.")):
            tip(ctk.CTkCheckBox(
                three, width=120, text=text, variable=var, onvalue=True,
                offvalue=False, font=F_BODY, checkbox_width=18,
                checkbox_height=18, border_width=2, fg_color=ORANGE,
                hover_color=AMBER, text_color=DIM, command=self.changed),
                hint).pack(side="left", padx=(12, 0))
        self.saved = SavedRow(self.detail, window.app, kind, self.snapshot,
                              self.restore, self.reset)
        self._building = False

    def toggle(self):
        self.expanded = not self.expanded
        if self.expanded:
            self.detail.pack(fill="x", pady=(6, 0))
        else:
            self.detail.pack_forget()
        self.mark()

    def mark(self, spec=None):
        spec = spec or self.spec()
        on = len(FD.body_filters_on(spec)) + (1 if spec["scope"] != self.scopes[0][1]
                                              else 0)
        self.toggle_button.configure(text="Body filters  %s" % (
            "-" if self.expanded else ("+" if not on else "(%d on)" % on)))

    def changed(self):
        if not self._building:
            self.window._paint()

    # -- what is asked ----------------------------------------------------------

    def spec(self):
        short = dict(FD.BODY_SHORT)
        here = str(getattr(attr(self.window.app, "watcher"), "system", "") or "")
        return FD.body_spec(
            scope=dict(self.scopes).get(self.scope_box.get(), self.scopes[0][1]),
            within_ly=float(FD.NEAR_LY.get(self.within_box.get(), 100)),
            system=here,
            classes=[short[n] for n in picks_of(self.type_box) if n in short],
            volcanism=picks_of(self.volc_box),
            g_min=entry_number(self.g_low), g_max=entry_number(self.g_high),
            k_min=entry_number(self.k_low), k_max=entry_number(self.k_high),
            signals=picks_of(self.signal_box),
            signal_min=FD.whole_number(self.signal_min_box.get(), 1) or 1,
            landable=bool(self.landable_var.get()),
            mapped=bool(self.mapped_var.get()),
            ls_max=entry_number(self.ls_box))

    def far(self):
        """Whether Where to land is asked about more than this system."""
        return self.kind == "land" and self.spec()["scope"] != "here"

    def report(self, shown, total, spec=None, note=""):
        spec = spec or self.spec()
        self.mark(spec)
        on = FD.body_filters_on(spec)
        if not on and shown == total and not note:
            return self.line.configure(text="")
        text = FD.body_count_line(shown, total, self.counts)
        if on:
            text += "  Filters: " + "; ".join(on) + "."
        self.line.configure(text=text + note,
                            text_color=AMBER if shown != total else DIM)

    def narrow_here(self, rows):
        """Where to land rows, this system, past the body filters."""
        spec = self.spec()
        self.counts = {}
        if not FD.body_filters_on(spec):
            self.report(len(rows), len(rows), spec)
            return rows
        app = self.window.app
        # Where to land's rows are this system's and do not carry its name;
        # without it "This system" would hide every one of them.
        counted = [dict(r, counts=app.live_signal_counts(r["body"]),
                        system=r.get("system") or spec["system"]) for r in rows]
        kept, self.counts = FD.filter_bodies(counted, spec)
        self.report(len(kept), len(counted), spec)
        return kept

    def narrow_far(self):
        """Remembered bodies from the body book, past the body filters,
        nearest first, at most FD.BODY_ROW_CAP."""
        spec = self.spec()
        rows = self.window.app.remembered_bodies(spec)
        kept, self.counts = FD.filter_bodies(rows, spec)
        kept.sort(key=lambda r: (r["distance_ly"] is None, r["distance_ly"] or 0.0,
                                 r["distance_ls"] is None, r["distance_ls"] or 0.0,
                                 r["system"].lower(), r["body"].lower()))
        note = ""
        if len(kept) > FD.BODY_ROW_CAP:
            note = "  The nearest %d are listed." % FD.BODY_ROW_CAP
        total = len(rows)
        shown = len(kept)
        self.report(shown, total, spec, note)
        return kept[:FD.BODY_ROW_CAP]

    def narrow_sites(self, sites):
        """My sites past the body filters - each site is judged on the body
        it is on. Nothing is hidden while every filter is off."""
        spec = self.spec()
        self.counts = {}
        if not FD.body_filters_on(spec) and spec["scope"] == "all":
            self.report(len(sites), len(sites), spec)
            return sites
        facts = self.window.app.site_bodies(sites)
        kept = []
        for site in sites:
            why = FD.why_body_hidden(
                facts[(SV.fold(site["system"]), SV.fold(site["body"]))], spec)
            if why:
                self.counts[why] = self.counts.get(why, 0) + 1
            else:
                kept.append(site)
        self.report(len(kept), len(sites), spec)
        return kept

    # -- saved searches ----------------------------------------------------------

    def snapshot(self):
        return {"scope": self.scope_box.get(), "within": self.within_box.get(),
                "types": picks_of(self.type_box),
                "volcanism": picks_of(self.volc_box),
                "signals": picks_of(self.signal_box),
                "signal_min": self.signal_min_box.get(),
                "g_low": self.g_low.get(), "g_high": self.g_high.get(),
                "k_low": self.k_low.get(), "k_high": self.k_high.get(),
                "ls": self.ls_box.get(),
                "landable": bool(self.landable_var.get()),
                "mapped": bool(self.mapped_var.get())}

    def restore(self, state):
        state = state or {}
        self._building = True
        try:
            for box, key, fallback in (
                    (self.scope_box, "scope", self.scopes[0][0]),
                    (self.within_box, "within", "100 Ly"),
                    (self.signal_min_box, "signal_min", "1")):
                box.set(str(state.get(key) or fallback))
            for box, key in ((self.type_box, "types"), (self.volc_box, "volcanism"),
                             (self.signal_box, "signals")):
                set_picks(box, state.get(key) or [])
            for box, key in ((self.g_low, "g_low"), (self.g_high, "g_high"),
                             (self.k_low, "k_low"), (self.k_high, "k_high"),
                             (self.ls_box, "ls")):
                set_entry(box, state.get(key))
            self.landable_var.set(bool(state.get("landable")))
            self.mapped_var.set(bool(state.get("mapped")))
        finally:
            self._building = False
        self.window._paint()

    def reset(self):
        self.restore({})
        self.saved.say("Every body filter is cleared.", GREEN)


def land_far_cells(row):
    """One remembered body as cells in LAND_FAR_HEADERS order."""
    far = row.get("distance_ly")
    ls = row.get("distance_ls")
    gravity = row.get("gravity_g")
    kelvin = row.get("temperature_k")
    counts = row.get("counts") or {}
    signals = ", ".join("%s %d" % (kind, n) for kind, n in sorted(counts.items())
                        if n) or ("none" if row.get("mapped") else "not scanned")
    landable = row.get("landable")
    volcano = row.get("volcanism") or "unknown"
    return [
        (row.get("short") or row["body"], None, (row.get("short") or row["body"]).lower()),
        (row["system"], None, row["system"].lower()),
        ("%.1f" % far if far is not None else "-", None,
         far if far is not None else ""),
        ("{:,.0f}".format(ls) if ls is not None else "-", None,
         ls if ls is not None else ""),
        (row.get("planet_class") or "-", None, (row.get("planet_class") or "").lower()),
        (volcano, None, volcano.lower()),
        ("%s g" % ("%.2f" % gravity) if gravity is not None else "-",
         RED if gravity is not None and is_high_g(gravity) else None,
         gravity if gravity is not None else ""),
        ("{:,.0f} K".format(kelvin) if kelvin is not None else "-", None,
         kelvin if kelvin is not None else ""),
        (signals, None, sum(counts.values()) if counts else ""),
        ("yes" if landable else "no" if landable is not None else "?",
         GREEN if landable else None, 1 if landable else 0),
        ("yes" if row.get("mapped") else "no", None, 1 if row.get("mapped") else 0),
    ]


class GridTable:
    """A small sortable table for the Powerplay window. Rows are lists of
    cells in the form Find's tables use: (text, colour, sort key)."""

    def __init__(self, scroller, copy=None):
        self.scroller = scroller
        self.table = scroller.inner
        self.copy = copy
        self.headers, self.rows, self.empty, self.wrap = [], [], "", {}
        self.tail = []
        self.sort_column, self.sort_reverse = None, False

    def show(self, headers, rows, empty="", wrap=None, tail=None):
        """`tail` is rows that are not results - "no price known" - kept
        below the rest whichever way the table is sorted."""
        if list(headers) != self.headers:
            self.sort_column, self.sort_reverse = None, False
        self.headers, self.rows = list(headers), list(rows) + list(tail or [])
        self.tail = list(tail or [])
        self.empty, self.wrap = empty, dict(wrap or {})
        self.paint()

    def ordered(self):
        tail = attr(self, "tail", None) or []
        rows = list(self.rows[:len(self.rows) - len(tail)])
        column = self.sort_column
        if column is None or not rows:
            return rows + tail

        def key(cells):
            if column >= len(cells):
                return _sortable("")
            return EarningsWindow._cell(cells[column])[2]
        return sorted(rows, key=key, reverse=self.sort_reverse) + tail

    def sort_by(self, column):
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column, self.sort_reverse = column, False
        self.paint()

    def paint(self):
        for widget in self.table.winfo_children():
            widget.destroy()
        if not self.rows:
            ctk.CTkLabel(self.table, text=self.empty, font=F_BODY,
                         text_color=DIM, justify="left", wraplength=820).grid(
                             row=0, column=0, padx=14, pady=18, sticky="w")
            return
        for column, name in enumerate(self.headers):
            text = name
            if column == self.sort_column:
                text = "%s %s" % (name, "v" if self.sort_reverse else "^")
            tip(ctk.CTkButton(self.table, text=text, font=F_SMALL_B,
                              **BTN_HEADING, anchor="w", height=24, width=0,
                              command=lambda c=column: self.sort_by(c)),
                "Click to sort by this column; click again to turn it round.").grid(
                    row=0, column=DATA_COLUMN_0 + column, padx=4, pady=4,
                    sticky="w")
        for index, cells in enumerate(self.ordered()[:POWER_ROW_CAP], start=1):
            for column, cell in enumerate(cells):
                text, colour, _key = EarningsWindow._cell(cell)
                cell_label(self.table, index, column, text, colour,
                           self.wrap.get(self.headers[column], CELL_WRAP),
                           full=cell_full(cell))
            if self.copy is not None:
                line = self.line_of(cells)
                row_buttons(self.table, index, [
                    ("row", lambda t=line: self.copy("this row", t), False)])

    @staticmethod
    def line_of(cells):
        return " | ".join(cell_full(c).replace("\n", " ") for c in cells)

    def as_text(self):
        if not self.rows:
            return ""
        return "\n".join([" | ".join(self.headers)]
                         + [self.line_of(c) for c in self.ordered()[:POWER_ROW_CAP]])


class PowerplayWindow(ToolWindow):
    """Whether selling what is aboard would count for the Power the commander
    is pledged to, and where it pays best (1.10035).

    Two pages. Where it counts: the pledge from the journal, what selling in
    a system would be - Expand, Reinforce, Undermine or nothing - for every
    system the journals have been in, whether the cargo will count at all,
    and the merits the hold should earn. Where to sell: for each commodity
    aboard, the five best payers or the five nearest buyers from the prices
    already in hand. No server is asked for either."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("EDSMT - Powerplay")
        width, height = screen_fraction(self, 0.84, 0.8, 1640, 960, 860, 520)
        self.geometry("%dx%d" % (width, height))
        self.minsize(820, 480)
        self.configure(fg_color=VOID)
        self.transient(app)
        self._signature, self._page = None, 0

        top = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        top.pack(fill="x", padx=12, pady=(12, 6))
        bracket(top, colour=ORANGE)
        hud_header(top, "Powerplay", padx=12, pady=(12, 4))
        self.pledge = ctk.CTkLabel(top, text="", font=F_READOUT, text_color=TEXT,
                                   anchor="w", justify="left", wraplength=900)
        self.pledge.pack(fill="x", anchor="w", padx=12, pady=(2, 4))
        bar = ctk.CTkFrame(top, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(0, 10))
        tip(ctk.CTkButton(bar, text="Copy all", width=100, height=32,
                          font=F_STRONG, **BTN_SECONDARY, command=self.copy_all),
            "Copies the table on show as text, ready to paste into Discord."
            ).pack(side="right")
        self.page_buttons = []
        for index, name in enumerate(("Where it counts", "Where to sell")):
            button = tip(ctk.CTkButton(
                bar, text=name, width=150, height=32, font=F_STRONG,
                **(BTN_PRIMARY if index == 0 else BTN_SECONDARY),
                command=lambda i=index: self.show_page(i)),
                "Whether selling here would count for your Power." if index == 0
                else "The best five payers and the five nearest buyers of what "
                     "is aboard.")
            button.pack(side="left", padx=(0, 8))
            self.page_buttons.append(button)
        tip(ctk.CTkButton(bar, text="Refresh", width=100, height=32,
                          font=F_STRONG, **BTN_SECONDARY,
                          command=lambda: self.follow(force=True)),
            "Reads the hold and the record again.").pack(side="left", padx=8)

        self.status = ctk.CTkLabel(self, text="", font=F_READOUT, text_color=DIM,
                                   anchor="w", justify="left", wraplength=900)
        self.status.pack(side="bottom", fill="x", padx=14, pady=(0, 10))

        # Page one: where it counts.
        self.count_page = ctk.CTkFrame(self, fg_color="transparent")
        controls = ctk.CTkFrame(self.count_page, fg_color="transparent")
        controls.pack(fill="x", padx=12, pady=(0, 6))
        filter_label(controls, "Mined in", first=True)
        self.mined_box = filter_entry(
            controls, 190, "Where the goods were mined. Blank: where most of "
            "the mined hold came from, else the system you are in.",
            "blank = from the journal", self.repaint)
        filter_label(controls, "Selling in")
        self.sell_box = filter_entry(
            controls, 190, "The system to sell in. Blank: the system you are "
            "in.", "blank = here", self.repaint)
        self.range_on = ctk.BooleanVar(value=getattr(
            attr(app, "powerbook"), "range_rule", True))
        tip(ctk.CTkCheckBox(
            controls, width=230, text="Undermine needs range",
            variable=self.range_on, onvalue=True, offvalue=False, font=F_BODY,
            checkbox_width=18, checkbox_height=18, border_width=2,
            fg_color=ORANGE, hover_color=AMBER, text_color=DIM,
            command=self.range_changed),
            "On: a rival system counts for Undermine only within 30 Ly of one "
            "of your Strongholds or 20 Ly of a Fortified system. Off: any "
            "rival system.").pack(side="left", padx=(14, 0))
        self.only_counts = ctk.BooleanVar(value=False)
        tip(ctk.CTkCheckBox(
            controls, width=200, text="Only where it counts",
            variable=self.only_counts, onvalue=True, offvalue=False,
            font=F_BODY, checkbox_width=18, checkbox_height=18, border_width=2,
            fg_color=ORANGE, hover_color=AMBER, text_color=DIM,
            command=self.repaint), "Hides systems where selling earns nothing."
            ).pack(side="left", padx=(14, 0))
        self.headline = ctk.CTkLabel(self.count_page, text="", font=F_BODY,
                                     text_color=TEXT, anchor="w", justify="left",
                                     wraplength=900)
        self.headline.pack(fill="x", padx=14, pady=(0, 2))
        self.warning = ctk.CTkLabel(self.count_page, text="", font=F_BODY,
                                    text_color=AMBER, anchor="w", justify="left",
                                    wraplength=900)
        self.warning.pack(fill="x", padx=14, pady=(0, 2))
        self.hold_line = ctk.CTkLabel(self.count_page, text="", font=F_SMALL,
                                      text_color=DIM, anchor="w", justify="left",
                                      wraplength=900)
        self.hold_line.pack(fill="x", padx=14, pady=(0, 6))
        self.count_scroll = ScrollTable(self.count_page)
        self.count_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self.count_grid = GridTable(self.count_scroll, self.copy_text)

        # Page two: where to sell.
        self.sell_page = ctk.CTkFrame(self, fg_color="transparent")
        controls = ctk.CTkFrame(self.sell_page, fg_color="transparent")
        controls.pack(fill="x", padx=12, pady=(0, 6))
        filter_label(controls, "Order", first=True)
        self.order_box = filter_combo(
            controls, ("Best price", "Nearest"), 130,
            "The five best payers of each commodity, or the five nearest "
            "buyers.", self.order_changed)
        tip(ctk.CTkButton(controls, text="Ask for prices", width=130, height=32,
                          font=F_STRONG, **BTN_SECONDARY, command=self.ask),
            "Asks the community map where what is aboard sells, near where "
            "you are. The answers appear here as they arrive."
            ).pack(side="left", padx=(14, 0))
        self.sell_note = ctk.CTkLabel(self.sell_page, text="", font=F_SMALL,
                                      text_color=DIM, anchor="w", justify="left",
                                      wraplength=900)
        self.sell_note.pack(fill="x", padx=14, pady=(0, 6))
        self.sell_scroll = ScrollTable(self.sell_page)
        self.sell_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self.sell_grid = GridTable(self.sell_scroll, self.copy_text)

        for scroll in (self.count_scroll, self.sell_scroll):
            for sequence in ("<MouseWheel>", "<Shift-MouseWheel>",
                             "<Button-4>", "<Button-5>"):
                self.bind(sequence, scroll.wheel, add="+")
        self.bind("<Configure>", self._rewrap, add="+")
        self.show_page(0)

    def _rewrap(self, event=None):
        try:
            if event is not None and event.widget is not self:
                return
            wrap = max(400, self.winfo_width() - 60)
            for label in (self.pledge, self.headline, self.warning,
                          self.hold_line, self.sell_note, self.status):
                label.configure(wraplength=wrap)
        except Exception:
            pass

    # -- pages and keeping up ----------------------------------------------------

    def show_page(self, index):
        self._page = index
        for number, button in enumerate(self.page_buttons):
            button.configure(**(BTN_PRIMARY if number == index else BTN_SECONDARY))
        self.count_page.pack_forget()
        self.sell_page.pack_forget()
        (self.count_page if index == 0 else self.sell_page).pack(
            fill="both", expand=True)
        self.follow(force=True)

    def signature(self):
        app = self.app
        book = attr(app, "powerbook")
        watcher = attr(app, "watcher")
        return (book.revision if book is not None else -1,
                str(getattr(watcher, "system", "") or ""),
                bool(getattr(watcher, "docked", False)),
                app.sell_signature(), self._page)

    def follow(self, force=False):
        """Called from the app's poll: redraws only when something changed."""
        try:
            sign = self.signature()
            if force or sign != self._signature:
                self._signature = sign
                self.repaint()
        except Exception as exc:
            self.say("Could not read the Powerplay record: %s" % exc, RED)

    def repaint(self):
        try:
            self.paint_pledge()
            if self._page == 0:
                self.paint_counts()
            else:
                self.paint_sell()
        except Exception as exc:
            self.say("Could not draw that: %s" % exc, RED)

    def order_changed(self):
        """Best price or Nearest is an order of its own: a column sort
        clicked before it would hide it."""
        self.sell_grid.sort_column, self.sell_grid.sort_reverse = None, False
        self.repaint()

    def range_changed(self):
        book = attr(self.app, "powerbook")
        if book is not None:
            book.range_rule = bool(self.range_on.get())
            book.dirty = True
        self.repaint()

    def say(self, text, colour=None):
        self.status.configure(text=text, text_color=colour or DIM)

    # -- drawing ---------------------------------------------------------------------

    def paint_pledge(self):
        book = attr(self.app, "powerbook")
        if book is None:
            return self.pledge.configure(text="No Powerplay record in this build.")
        if not book.power:
            return self.pledge.configure(
                text="No pledge in your journal. The game writes it when you "
                     "log in; EDSMT also reads your older journals. If you "
                     "are not pledged, no merits are paid and everything "
                     "below says Unknown.")
        me = book.me
        bits = ["Pledged to %s" % book.power]
        if me.get("rank") is not None:
            bits.append("rank %s" % me["rank"])
        if me.get("merits") is not None:
            try:
                bits.append("{:,} merits".format(int(me["merits"])))
            except (TypeError, ValueError):
                pass
        bits.append("%d systems in your record" % len(book.systems))
        self.pledge.configure(text=", ".join(bits) + ".")

    @staticmethod
    def _goal_colour(goal):
        return GREEN if goal in PW.COUNTS else AMBER if goal == PW.UNKNOWN else DIM

    def paint_counts(self):
        app = self.app
        book = attr(app, "powerbook")
        if book is None:
            return
        book.range_rule = bool(self.range_on.get())
        view = app.power_view(self.sell_box.get().strip() or None,
                              self.mined_box.get().strip() or None)
        self.headline.configure(
            text=view["headline"], text_color=self._goal_colour(view["goal"]))
        self.warning.configure(text="  ".join(
            i["text"] for i in view["risk"] + view.get("elsewhere", [])))
        lines = []
        merits = view["merits"]
        for item in merits["lines"]:
            # What the hold should earn, never what it is worked out from.
            lines.append("%d t %s: about %s merits" % (
                item["tonnes"], item["commodity"], "{:,}".format(item["merits"])))
        if merits["missing"]:
            lines.append("no price known in %s for %s" % (
                view["sell"] or "this system", ", ".join(merits["missing"])))
        flagged = [s for s in book.sale_flags() if not s["counts"]][-3:]
        for sale in flagged:
            lines.append("last sale of %s on %s: %s" % (
                sale["name"] or sale["commodity"], str(sale["when"])[:10],
                sale["note"]))
        origin = view["origin"] or "unknown"
        self.hold_line.configure(text="Mined in %s%s.  %s" % (
            origin, "" if view["origin_known"] else " (assumed - no mining of "
            "this hold in your record)", "   ".join(lines)))
        rows = PW.system_rows(book, view["origin"], app.star_position())
        if self.only_counts.get():
            rows = [r for r in rows if r["goal"] in PW.COUNTS]
        cells = []
        for r in rows:
            mine = book.power and r["power"].lower() == book.power.lower()
            cells.append([
                (r["system"], None, r["system"].lower()),
                ("%.1f" % r["ly"] if r["ly"] is not None else "-", None,
                 r["ly"] if r["ly"] is not None else ""),
                (r["power"] or "-", GREEN if mine else None, r["power"].lower()),
                (r["state"] or "-", None, r["state"]),
                (r["goal"], self._goal_colour(r["goal"]),
                 PW.COUNTS.index(r["goal"]) if r["goal"] in PW.COUNTS else 9),
                # A few words; the sentence is the tooltip and the copy.
                (r.get("brief") or r["why"], DIM,
                 (r.get("brief") or r["why"]).lower(), r["why"])])
        self.count_grid.show(
            SYSTEM_HEADERS, cells,
            "No systems in your Powerplay record yet. Jump around with EDSMT "
            "running, or let it finish reading your older journals.",
            POWER_TABLE_WRAP)
        self.say("%d of %d systems shown." % (len(cells), len(book.systems))
                 if book.systems else "", DIM)

    def paint_sell(self):
        app = self.app
        by = "distance" if self.order_box.get() == "Nearest" else "price"
        groups = app.sell_side(by)
        book = attr(app, "powerbook")
        cells, unpriced = [], []
        for group in groups:
            if not group["rows"]:
                # Not a result: below every price, whatever the sort.
                unpriced.append([(group["commodity"], None, group["commodity"].lower()),
                                 (str(group["tonnes"]) + " t", None, group["tonnes"]),
                                 ("no price known - press Ask for prices", AMBER, "")]
                                + [("", None, "")] * 8)
                continue
            for row in group["rows"]:
                words, age = price_age(row.get("seen"))
                goal = row.get("goal") or "-"
                cells.append([
                    (group["commodity"], None, group["commodity"].lower()),
                    (str(group["tonnes"]) + " t", None, group["tonnes"]),
                    (str(row.get("station") or "-"), None,
                     str(row.get("station") or "").lower()),
                    (str(row.get("system") or "-"), None,
                     str(row.get("system") or "").lower()),
                    FindWindow._distance(row),
                    ("{:,}".format(row["sell"]), GREEN, row["sell"]),
                    ("{:,}".format(row["demand"]) if row.get("demand") else "-",
                     None, row.get("demand") or 0),
                    (words, GREEN if age is not None and age < PRICE_STALE_S
                     else AMBER, age if age is not None else 1e12),
                    (pad_size(row.get("pad")), None, FD.pad_rank(row.get("pad"))),
                    (station_kind(row.get("station_type")), None,
                     str(row.get("station_type") or "").lower()),
                    (goal, self._goal_colour(goal),
                     PW.COUNTS.index(goal) if goal in PW.COUNTS else 9)])
        self.sell_grid.show(
            SELL_HEADERS, cells,
            "Nothing aboard to sell. Fill the hold, then come back." if not groups
            else "No prices.", {"Station": 220}, tail=unpriced)
        self.sell_note.configure(
            text="Five %s of each commodity aboard, from the markets you have "
                 "read and the community map's last answers. Demand 0 is never "
                 "listed. %s" % (
                     "nearest buyers" if by == "distance" else "best payers",
                     "Powerplay shows what selling there would do for goods "
                     "mined in %s." % (book.hold_origin(app.hold_now()) or "this system")
                     if book is not None and book.power else
                     "You are not pledged, so Powerplay is left blank."))

    def ask(self):
        sent, why = self.app.quote_hold()
        self.say("Asked for %d price(s); they appear here as they arrive." % sent
                 if sent else why, DIM if sent else AMBER)

    # -- copying -------------------------------------------------------------------------

    def copy_text(self, what, text):
        try:
            put_on_clipboard(self, text)
        except Exception as exc:
            return self.say("Could not reach the clipboard: %s" % exc, RED)
        self.say("Copied %s - %s" % (what, text.replace("\n", " ")), GREEN)

    def copy_all(self):
        grid = self.count_grid if self._page == 0 else self.sell_grid
        block = grid.as_text()
        if not block:
            return self.say("Nothing to copy yet.", AMBER)
        self.copy_text("%d row(s)" % (len(block.splitlines()) - 1), block)


class LeaderboardWindow(ToolWindow):
    """The community leaderboard (1.10036, #158).

    This week (since the Powerplay tick), this month, last month and all
    time, by points or by Powerplay merits from mined cargo, with totals per
    Power. Everyone who shares a find is on it until they press Leave; Join
    and Leave are here as well as in Settings. The working-out is in
    board.py; this is the window."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("EDSMT - Leaderboard")
        width, height = screen_fraction(self, 0.7, 0.75, 1280, 900, 760, 480)
        self.geometry("%dx%d" % (width, height))
        self.minsize(720, 440)
        self.configure(fg_color=VOID)
        self.transient(app)
        self.choice = LB.SEASONS[0][0]
        self.view = LB.VIEWS[0][0]
        self.answer = None

        top = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        top.pack(fill="x", padx=12, pady=(12, 6))
        bracket(top, colour=ORANGE)
        hud_header(top, "Leaderboard", padx=12, pady=(12, 4))
        self.headline = ctk.CTkLabel(top, text="Asking the community map...",
                                     font=F_READOUT, text_color=TEXT, anchor="w",
                                     justify="left", wraplength=900)
        self.headline.pack(fill="x", anchor="w", padx=12, pady=(2, 2))
        self.you = ctk.CTkLabel(top, text="", font=F_BODY, text_color=ORANGE,
                                anchor="w", justify="left", wraplength=900)
        self.you.pack(fill="x", anchor="w", padx=12, pady=(0, 4))
        bar = ctk.CTkFrame(top, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(0, 10))
        self.season_buttons = {}
        for name, _season in LB.SEASONS:
            button = tip(ctk.CTkButton(
                bar, text=name, width=120, height=32, font=F_STRONG,
                **(BTN_PRIMARY if name == self.choice else BTN_SECONDARY),
                command=lambda n=name: self.pick(n)),
                "This week runs from the Powerplay tick, Thursday 07:00 UTC. "
                "Months are calendar months, in UTC. All time counts "
                "everything since the board began.")
            button.pack(side="left", padx=(0, 8))
            self.season_buttons[name] = button
        views = ctk.CTkFrame(top, fg_color="transparent")
        views.pack(fill="x", padx=12, pady=(0, 10))
        self.view_buttons = {}
        for name, _sort in LB.VIEWS:
            button = tip(ctk.CTkButton(
                views, text=name, width=170, height=30, font=F_STRONG,
                **(BTN_PRIMARY if name == self.view else BTN_SECONDARY),
                command=lambda n=name: self.pick_view(n)),
                "Points are for what makes the map better. Merits are what "
                "the game paid for selling cargo you mined, for your Power; "
                "they are shown beside the points, not added to them.")
            button.pack(side="left", padx=(0, 8))
            self.view_buttons[name] = button
        tip(ctk.CTkButton(bar, text="Refresh", width=100, height=32,
                          font=F_STRONG, **BTN_SECONDARY, command=self.ask),
            "Asks the community map again.").pack(side="left", padx=8)
        tip(ctk.CTkButton(bar, text="Copy all", width=100, height=32,
                          font=F_STRONG, **BTN_SECONDARY, command=self.copy_all),
            "Copies the board as text, ready to paste into Discord."
            ).pack(side="right")
        tip(ctk.CTkButton(bar, text="On the web", width=110, height=32,
                          font=F_STRONG, **BTN_SECONDARY, command=self.open_web),
            "The board, and what the community map took in lately, in your "
            "browser - a page you can share.").pack(side="right", padx=(8, 0))
        self.join = ctk.CTkButton(bar, text="Join", width=100, height=32,
                                  font=F_STRONG, **BTN_SECONDARY,
                                  command=self.toggle)
        tip(self.join, SETTING_TIPS.get("leaderboard_optin")).pack(side="right", padx=8)

        self.status = ctk.CTkLabel(self, text="", font=F_READOUT, text_color=DIM,
                                   anchor="w", justify="left", wraplength=900)
        self.status.pack(side="bottom", fill="x", padx=14, pady=(0, 10))
        self.points = ctk.CTkLabel(self, text=LB.points_words(), font=F_SMALL,
                                   text_color=DIM, anchor="w", justify="left",
                                   wraplength=900)
        self.points.pack(side="bottom", fill="x", padx=14, pady=(0, 4))
        self.powers = ctk.CTkLabel(self, text="", font=F_BODY, text_color=TEXT,
                                   anchor="w", justify="left", wraplength=900)
        self.powers.pack(side="bottom", fill="x", padx=14, pady=(0, 4))
        self.scroll = ScrollTable(self)
        self.scroll.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self.grid_table = GridTable(self.scroll, self.copy_text)
        for sequence in ("<MouseWheel>", "<Shift-MouseWheel>",
                         "<Button-4>", "<Button-5>"):
            self.bind(sequence, self.scroll.wheel, add="+")
        self.bind("<Configure>", self._rewrap, add="+")
        self.paint_you()
        self.ask()

    def _rewrap(self, event=None):
        try:
            if event is not None and event.widget is not self:
                return
            wrap = max(400, self.winfo_width() - 60)
            for label in (self.headline, self.you, self.points, self.powers,
                          self.status):
                label.configure(wraplength=wrap)
        except Exception:
            pass

    def say(self, text, colour=None):
        try:
            self.status.configure(text=text, text_color=colour or DIM)
        except Exception:
            pass

    def opted(self):
        settings = attr(self.app, "settings", None) or {}
        return bool(settings.get("leaderboard_optin", True)), True

    def pick(self, name):
        self.choice = name
        for other, button in self.season_buttons.items():
            button.configure(**(BTN_PRIMARY if other == name else BTN_SECONDARY))
        self.ask()

    def pick_view(self, name):
        self.view = name
        for other, button in self.view_buttons.items():
            button.configure(**(BTN_PRIMARY if other == name else BTN_SECONDARY))
        self.ask()

    def ask(self):
        community = attr(self.app, "community")
        season = LB.season_for(self.choice)
        try:
            asked = bool(community is not None and community.leaderboard(
                season=season, cmdr=self.app.board_cmdr(),
                limit=LB.ROW_LIMIT, tag=LB_TAG, sort=dict(LB.VIEWS)[self.view]))
        except Exception as exc:
            asked = False
            self.say("Could not ask the community map: %s" % exc, RED)
            return False
        if not asked:
            self.say("The community map cannot be reached from this copy.", AMBER)
            return False
        self.say("Asking the community map...")
        return True

    def results(self, ok, message):
        if not ok:
            return self.say("The leaderboard did not come: %s" % message, RED)
        data = LB.parse(message)
        if data is None:
            return self.say("The leaderboard answer was not readable.", RED)
        self.answer = data
        self.headline.configure(text=LB.board_words(data))
        self.points.configure(text=LB.points_words(data.get("points")))
        self.powers.configure(text=LB.powers_words(data))
        rows = []
        for cells in LB.cells(data, self.app.board_cmdr()):
            rows.append([(text, ORANGE if tone == "you" else TEXT, key)
                         for text, tone, key in cells])
        merits = data.get("sort") == "merits"
        self.grid_table.show(LB.HEADERS, rows, empty=(
            ("Nobody has Powerplay merits from mining for %s yet." if merits else
             "Nobody has points for %s yet. Points come from finds, first finds "
             "on a body, confirmed sites, worked-out reports and rig layouts.")
            % LB.season_words(data.get("season"), None, data.get("week_start"))))
        self.paint_you()
        self.say("Up to date.", GREEN)
        return True

    def paint_you(self):
        opted, sharing = self.opted()
        try:
            self.you.configure(text=LB.you_words(
                self.answer, self.app.board_cmdr(), opted, sharing))
            self.join.configure(text="Leave" if opted else "Join")
        except Exception:
            pass

    def open_web(self):
        try:
            import webbrowser
            webbrowser.open(LB.WEB_PAGE)
            self.say("Opened the leaderboard in your browser.")
            return True
        except Exception as exc:
            self.say("Could not open a browser: %s" % exc, RED)
            return False

    def toggle(self):
        opted, _sharing = self.opted()
        if not self.app.board_cmdr():
            return self.say("Your CMDR name comes from the journal - start the "
                            "game once first.", AMBER)
        self.app.set_board(not opted)
        self.paint_you()
        self.say("Telling the community map...")
        return True

    def copy_text(self, what, text):
        try:
            put_on_clipboard(self, text)
        except Exception as exc:
            return self.say("Could not reach the clipboard: %s" % exc, RED)
        self.say("Copied %s - %s" % (what, text.replace("\n", " ")), GREEN)

    def copy_all(self):
        block = self.grid_table.as_text()
        if not block:
            return self.say("Nothing to copy yet.", AMBER)
        head = "EDSMT leaderboard - %s" % LB.season_words(
            (self.answer or {}).get("season"))
        self.copy_text("%d row(s)" % (len(block.splitlines()) - 1),
                       head + "\n" + block)


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
