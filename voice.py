"""
Voice Mode (1.10040, #145, #146, #292): EDSMT says what it just did.

The words are the Basic voice line pack: one line for each thing the app
does, in four voices - Celestia (the main one), Ship computer, Flight
controller and Radio Raxxla on-air. A recording wins when there is one:
voice/<theme>/<place>/<id>.wav for where the commander is - ship, Rhino
SRV or on foot, each with its own comm sound - else the ship's, else
voice/<theme>/<id>.wav, beside the app or in the data folder. Without one the line is spoken by Windows'
own speech, through ONE PowerShell process kept for the whole run: started
the first time something is said, every line written to it, never a
process a line, and stopped when EDSMT closes. Anywhere but Windows nothing
is spoken.

Spoken directions are for a headset, where the overlay cannot be seen:
how far and which way, on a clock face, to the target - "Platinum, 340
metres, two o'clock" - every so often while moving and whenever the target
changes, never more than one line every three seconds.

The lines, the words for a direction and when to say them are plain logic
and need no window. The speaker takes whatever starts its process as an
argument, so the checks hand it a stand-in.
"""

import atexit
import base64
import math
import os
import queue
import random
import re
import threading

import commfx as CFX

PACK_NAME = "Basic voice line pack"

# (key, name). The key is the recordings' folder: voice/<key>/<id>.wav.
# Celestia - the Celestial Event Liaison & Tactical Information Algorithm,
# Radio Raxxla's voice of the Void - is the main voice and a new install's.
THEMES = (("celestia", "Celestia"),
          ("ship_computer", "Ship computer"),
          ("flight_controller", "Flight controller"),
          ("on_air", "Radio Raxxla on-air"))
THEME_KEYS = tuple(key for key, _name in THEMES)
DEFAULT_THEME = "celestia"
# The three themes of the first table, in its column order.
_TABLE_KEYS = ("ship_computer", "flight_controller", "on_air")

# Where the commander is, for the comm sound a line is recorded with:
# voice/<theme>/<place>/<id>.wav. In the ship, in the Rhino SRV, on foot.
PLACES = ("ship", "srv", "foot")
DEFAULT_PLACE = "ship"
# The voices that come over comms: recorded clean, given the place's comm
# sound by commfx before they are played.
COMMS_THEMES = ("celestia",)

# How much she says (Celestia for now; the other voices have one length).
# Short: the brief line. Normal: her full line, and the voice-pack
# reminders. Chatty: Normal, with two or three takes of a line picked at
# random, reactions to what the journal shows and a lore aside now and then.
DETAILS = (("short", "Short"), ("normal", "Normal"), ("chatty", "Chatty"))
DETAIL_KEYS = tuple(key for key, _name in DETAILS)
DEFAULT_DETAIL = "normal"

_NUMBERS = ("one", "two", "three", "four", "five", "six")

# The Basic voice line pack. Each line: (Ship computer, Flight controller,
# Radio Raxxla on-air). A few are the start or the end of a sentence the
# app finishes with a number.
_TABLE = {
    "online": ("Survey systems online.",
               "EDSMT online. Standing by.",
               "Radio Raxxla here. Let's go find something worth digging."),
    "voice_test": ("Voice guidance active.",
                   "Radio check. Loud and clear.",
                   "Testing, testing. You're hearing Radio Raxxla."),
    "update_ready": ("A software update is ready to install.",
                     "Update downloaded and verified. Install when ready.",
                     "Fresh update's in the hangar. Install it when you're done out there."),
    "backup_done": ("Backup complete.",
                    "Backup written.",
                    "Your finds are backed up. Safe as houses."),
    "signal_logged": ("Signal logged. Survey centre set.",
                      "Signal marked. Centre locked.",
                      "Signal's in the book. That's our centre."),
    "border_set": ("Survey border set.",
                   "Border marked.",
                   "Edge of the patch marked. Now we sweep."),
    "deposit_marked": ("Deposit recorded.",
                       "Deposit logged.",
                       "Got it. Deposit's on the map."),
    "deposit_updated": ("Deposit updated.",
                        "Deposit amended.",
                        "Updated. Map's current."),
    "deposit_incomplete": ("Unable to record. Deposit details incomplete.",
                           "Negative. All four fields required.",
                           "Hold on. I need all four details before that goes on the map."),
    "deposit_already": ("Deposit already recorded at this position.",
                        "Already logged at this position.",
                        "That one's already on the map."),
    "mined_out": ("Deposit marked as depleted.",
                  "Deposit depleted. Logged.",
                  "Mined out. We'll check back on that one."),
    "rigs_full": ("All six rigs deployed.",
                  "Six rigs down. Full spread.",
                  "Full spread. Six rigs working."),
    "rigs_all_up": ("All rigs recovered.",
                    "All rigs up. Clear to move.",
                    "That's every rig home."),
    "rig_limit_warning": ("Warning. Approaching rig range limit.",
                          "Warning. Rig range limit.",
                          "Easy, Commander. You're nearly out of rig range."),
    "rig_lost": ("Rig signal lost.",
                 "Rig contact lost.",
                 "We've lost touch with a rig."),
    "rigs_cleared_relog": ("Rigs from the last session have been cleared.",
                           "Previous rigs cleared from the board.",
                           "Cleared the old rigs off the map. Fresh start."),
    "plan_trace_start": ("Tracing deposit edge. Return to your start point.",
                         "Tracing. Drive the edge back to start.",
                         "Drive the edge for me and bring it back round."),
    "plan_ready": ("Rig plan ready.",
                   "Plan ready. Pins set.",
                   "Pins are down. Here's your plan."),
    "pin_reached": ("On the pin. Deploy rig.",
                    "On mark. Drop the rig.",
                    "Right there. Drop a rig."),
    "next_pin": ("Next pin.",
                 "Next mark.",
                 "Next pin."),
    "plan_cancelled": ("Rig plan cancelled.",
                       "Plan scrubbed.",
                       "Plan's off."),
    "swept_half": ("Half the survey area swept.",
                   "Sweep fifty percent.",
                   "Halfway round the patch."),
    "swept_done": ("Survey area complete.",
                   "Sweep complete.",
                   "That's the whole patch swept. Nice driving."),
    "session_start": ("Mining session started.",
                      "Session running. Clock's on.",
                      "Session's on the clock. Happy mining."),
    "session_paused": ("Session paused.",
                       "Clock stopped.",
                       "Taking five. Clock's paused."),
    "session_resumed": ("Session resumed.",
                        "Clock running.",
                        "Back to work."),
    "session_end": ("Mining session complete.",
                    "Session closed. Numbers logged.",
                    "That's a wrap on this session. Check your earnings."),
    "nearest": ("Nearest deposit.",
                "Nearest.",
                "Closest one's"),
    "arrived": ("Deposit reached.",
                "On target.",
                "You're on it."),
    "none_in_range": ("No recorded deposits in range.",
                      "No contacts in range.",
                      "Nothing on the map near you yet."),
    "touchdown_hint": ("Nearest mining location:",
                       "Nearest location:",
                       "Closest mining location is number"),
    "locations_on_body": ("mining locations detected.",
                          "mining locations.",
                          "mining locations on this one."),
    "bodies_ranked": ("Landing targets ranked.",
                      "Landing list updated.",
                      "Where to land is sorted. Best first."),
    "high_gravity": ("Caution. High gravity world.",
                     "Caution. High G.",
                     "Heavy one, Commander. Watch your descent."),
    "deploy_clear": ("Clear to deploy the Rhino.",
                     "Clear to deploy.",
                     "Nice and low. Send the Rhino out."),
    "wing_linked": ("Wing link established.",
                    "Wing link up.",
                    "You're linked with the wing."),
    "wing_mate_joined": ("Wingmate connected.",
                         "Wingmate on the net.",
                         "Someone's joined the wing."),
    "wing_mate_left": ("Wingmate disconnected.",
                       "Wingmate off the net.",
                       "Wingmate's dropped off."),
    "wing_clash": ("Caution. Rig too close to a wingmate's rig.",
                   "Rig conflict with wingmate.",
                   "Careful, that's crowding a wingmate's rig."),
    "chat_ok": ("Command accepted.",
                "Copy.",
                "Heard you."),
    "chat_unknown": ("Command not recognised.",
                     "Say again. Command unknown.",
                     "Didn't catch that one."),
}
for _n, _word in enumerate(_NUMBERS, 1):
    _TABLE["rig_down_%d" % _n] = ("Rig %s deployed." % _word,
                                  "Rig %s down." % _word,
                                  "Rig %s's down." % _word)
    _TABLE["rig_up_%d" % _n] = ("Rig %s recovered." % _word,
                                "Rig %s up." % _word,
                                "Rig %s picked up." % _word)

# Celestia's own words. What is in square brackets is acting for the
# recording - [sighs], [scoffs] - and never read out by Windows' voice. The
# short lines the app finishes with a number or a direction, and the urgent
# ones, are kept plain on purpose.
_CELESTIA = {
    "online": "[curious] Celestia online. Oh, a planet... shall we dig something pretty out of it, Commander?",
    "voice_test": "Testing. Yes, Commander, it's me. Who else would it be?",
    "update_ready": "An update's ready. New code... [sighs] I do love a little self-improvement. "
                    "Install it when you dock.",
    "backup_done": "Backup done. Your finds are safe with me... they always are.",
    "signal_logged": "Signal logged. That's our centre, Commander. Don't wander off.",
    "border_set": "Border set. Now drive the edge, and do stay inside the lines.",
    "deposit_marked": "Deposit logged. Ooh, pretty.",
    "deposit_updated": "Updated. See? I listen.",
    "deposit_incomplete": "[sighs] I need all four details, Commander. All four. Not three. Four.",
    "deposit_already": "[scoffs] Already on the map. I don't forget things.",
    "mined_out": "Mined out. It'll grow back... eventually. The Void is patient. So am I.",
    "rigs_full": "All six rigs working. [laughs] Greedy. I like it.",
    "rigs_all_up": "Every rig's home, Commander. Clear to move.",
    "rig_limit_warning": "Commander, careful. You're nearly out of rig range.",
    "rig_lost": "[sighs] We've lost a rig. I did say.",
    "rigs_cleared_relog": "Old rigs cleared. Clean slate. I hate clutter.",
    "plan_trace_start": "Drive the edge for me, all the way round, and bring it back to where we started.",
    "plan_ready": "Plan's ready. I put the pins where they'll do the most good.",
    "pin_reached": "Right there. Drop a rig.",
    "next_pin": "Next pin.",
    "plan_cancelled": "Plan cancelled. [scoffs] Fine.",
    "swept_half": "Halfway round the patch. Keep going, you're doing well.",
    "swept_done": "That's the whole patch swept. [giggles] Nice driving, Commander.",
    "session_start": "Session's on the clock. Let's make the Void pay.",
    "session_paused": "Clock paused. Don't keep me waiting too long.",
    "session_resumed": "And we're back. I missed you.",
    "session_end": "That's the session, Commander. Go and see what we earned... I already have.",
    "nearest": "Nearest deposit.",
    "arrived": "You're on it.",
    "none_in_range": "[curious] Nothing on the map near you yet... so go and find me something.",
    "touchdown_hint": "Nearest mining location is number",
    "locations_on_body": "mining locations on this one.",
    "bodies_ranked": "Where to land is sorted, best first. You're welcome.",
    "high_gravity": "Heavy world, Commander. Watch your descent. I'd rather not scrape you off it.",
    "deploy_clear": "Nice and low. Send the Rhino out.",
    "wing_linked": "Wing link up. Company... how lovely.",
    "wing_mate_joined": "Someone's joined the wing. Another signal out of the dark.",
    "wing_mate_left": "A wingmate's dropped off. [sighs] They always leave.",
    "wing_clash": "Careful. That rig's crowding a wingmate's.",
    "chat_ok": "Heard you.",
    "chat_unknown": "[scoffs] Unverified signal. Try that again, properly.",
}
for _n, _word in enumerate(_NUMBERS, 1):
    _CELESTIA["rig_down_%d" % _n] = "Rig %s, down." % _word
    _CELESTIA["rig_up_%d" % _n] = "Rig %s, back aboard." % _word


# Short: the brief line, for the lines where it differs from Normal.
_CELESTIA_SHORT = {
    "online": "Celestia online.", "voice_test": "Celestia here.", "update_ready": "Update ready.",
    "backup_done": "Backup done.", "signal_logged": "Signal logged.", "border_set": "Border set.",
    "deposit_marked": "Deposit logged.", "deposit_updated": "Updated.",
    "deposit_incomplete": "All four details, please.", "deposit_already": "Already logged.",
    "mined_out": "Mined out.", "rigs_full": "Six rigs working.", "rigs_all_up": "All rigs up.",
    "rig_limit_warning": "Rig range, careful.", "rig_lost": "Rig lost.",
    "rigs_cleared_relog": "Old rigs cleared.", "plan_trace_start": "Trace the edge.",
    "plan_ready": "Plan ready.", "pin_reached": "Drop a rig.", "plan_cancelled": "Plan cancelled.",
    "swept_half": "Half swept.", "swept_done": "Area swept.", "session_start": "Session started.",
    "session_paused": "Clock paused.", "session_resumed": "Clock running.",
    "session_end": "Session ended.", "arrived": "On it.", "none_in_range": "Nothing near.",
    "touchdown_hint": "Nearest mining location:", "locations_on_body": "mining locations.",
    "bodies_ranked": "Landing list ready.", "high_gravity": "High gravity.",
    "deploy_clear": "Clear to deploy.", "wing_linked": "Wing linked.",
    "wing_mate_joined": "Wingmate joined.", "wing_mate_left": "Wingmate left.",
    "wing_clash": "Rig clash.", "chat_unknown": "Say again.",
}

# Chatty: the other takes of a line, one picked at random with the Normal
# line, never the same one twice running. Urgent lines, and the ones the app
# finishes with a number or a direction, have none.
_CELESTIA_TAKES = {
    "online": ("Systems up, Commander. I've been counting the stars while you were gone. Don't ask how many.",
               "[clears throat] Celestia, online. The Void says hello. I said it back."),
    "voice_test": ("Loud and clear. Well, I am. You'll have to tell me about you.",
                   "Testing, testing... [giggles] sorry. I've always wanted to say that."),
    "update_ready": ("New update in. I've had a peek. It's lovely. Install it when you're done out there.",
                     "There's an update waiting, Commander. Don't make me wait too long."),
    "backup_done": ("Backed up. If the Void eats your computer, I've still got you.",
                    "All saved. Every rock, every rig. You're welcome."),
    "signal_logged": ("Centre set. This is home now. For a while.",
                      "Signal's in the book. Right, let's see what's hiding out here."),
    "border_set": ("Edge marked. Everything inside it is ours.",
                   "Border's down. Sweep it properly this time."),
    "deposit_marked": ("Got it. On the map. [curious] What else is down here?",
                       "Logged. Another one for the collection."),
    "deposit_updated": ("Changed it. I'd never have got it wrong, but fine.", "Updated. Map's current."),
    "deposit_incomplete": ("[scoffs] That's not a deposit, that's a guess. All four details, please.",
                           "Missing details. I can't log a feeling, Commander."),
    "deposit_already": ("That one's already ours. Do keep up.",
                        "Already logged, Commander. I'm flattered you checked."),
    "mined_out": ("Empty. We'll come back when it's had a rest.",
                  "Worked out. Logged. Don't look so sad, it regrows."),
    "rigs_full": ("Full spread. Now we wait, and I watch the numbers go up.",
                  "Six down. That's every rig we own, Commander."),
    "rigs_all_up": ("All six tucked in. Off we go.", "Rigs aboard. Nothing left behind. I checked. Twice."),
    "rigs_cleared_relog": ("Previous rigs wiped. Fresh start.",
                           "Cleared the old rigs. They weren't coming back anyway."),
    "plan_trace_start": ("Round the edge, Commander. Nice and steady.",
                         "Trace it for me. I'll do the clever bit."),
    "plan_ready": ("Pins are down. Trust me, they're perfect.", "Plan's done. Follow the pins."),
    "plan_cancelled": ("Plan's off. I'll pretend I'm not hurt.", "Cancelled. Free-styling it, are we?"),
    "swept_half": ("Half done. The other half won't sweep itself.", "Fifty percent. I'm almost impressed."),
    "swept_done": ("Every metre covered. Nothing hides from us.",
                   "All swept. I'd give you a medal if I had hands."),
    "session_start": ("Clock's running, Commander. Make it count.", "Session started. I'm counting every tonne."),
    "session_paused": ("Paused. I'll be right here. I'm always right here.",
                       "Taking five? Fine. I'll count stars."),
    "session_resumed": ("Back on the clock. Did you miss me?", "Resumed. Right, where were we?"),
    "session_end": ("Session closed. The numbers are rather nice.", "That's a wrap. Go and look. Go on."),
    "none_in_range": ("Nothing logged near here. Yet.", "Empty map round you. Let's change that."),
    "bodies_ranked": ("I've ranked the bodies. Top one's the one.",
                      "Landing list done. Pick the first, trust me."),
    "deploy_clear": ("Low enough. Rhino time.", "Clear to deploy, Commander. Go and play."),
    "wing_linked": ("Linked with the wing. More signals in the dark.", "Wing's up. Do behave in front of them."),
    "wing_mate_joined": ("New wingmate. Hello, stranger.", "Someone's joined us. I'll be nice. Probably."),
    "wing_mate_left": ("Wingmate gone. More rocks for us.", "They've dropped off. Just you and me again."),
    "chat_ok": ("Done.", "On it."),
    "chat_unknown": ("Background static. Again, please.",
                     "I didn't understand that, and I understand everything."),
}

# Lines of Celestia's own, beyond the pack: voice-pack reminders (Normal and
# Chatty), reactions to the journal and lore asides (Chatty). Each is a list
# of takes; the first is the Normal one.
EXTRA = {
    "hint_deploy_srv": ("Say \"Deploy the SRV\", and let your crew send the Rhino out.",
                        "Landed. \"Deploy the SRV\" - go on, I'm dying to see the surface."),
    "hint_dismiss_ship": ("Ship's still parked, Commander. \"Dismiss the ship\" - go on.",
                          "You're leaving the ship sat there? \"Dismiss the ship\". It'll be fine. Probably."),
    "hint_recall_ship": ("All done? \"Recall the ship\", and I'll pretend I didn't see the parking.",
                         "Rigs home. \"Recall the ship\" - unless you fancy driving to orbit."),
    "hint_transfer_cargo": ("Hold's full. \"Transfer cargo\", and we'll keep going.",
                            "Seventy-two tonnes in a buggy. \"Transfer cargo\", Commander."),
    "hint_board_ship": ("\"Board the ship\" brings us home.",
                        "Ship's right there. \"Board the ship\". I'll put the kettle on. Metaphorically."),
    "hint_handbrake": ("Handbrake first. \"Apply handbrake\".", "Pin's here. \"Apply handbrake\", then drop it."),
    "react_launch_srv": ("Rhino's out. Do keep the wheels on the ground this time.",
                         "Wheels down. Let's go and annoy some rocks."),
    "react_dock_srv": ("Welcome back aboard. You smell of regolith.", "Rhino's home. So are you."),
    "react_srv_destroyed": ("[gasps] The Rhino! ...Right. We don't talk about this.",
                            "[sighs] That was expensive, Commander."),
    "react_touchdown": ("Touchdown. Gently, for once.", "We're down. Feet on the ground. Well. Landing gear."),
    "react_liftoff": ("Wheels up. Bye bye, planet.", "And we're off. I'll miss that rock. Not really."),
    "react_mining_body": ("[curious] Mining locations down there. I want to see.",
                          "Signals on that body, Commander. Something's waiting."),
    "react_big_sale": ("[laughs] Look at those numbers. I'm keeping a few for myself.",
                       "Now that's a payday. You may thank me later."),
    "react_hold_full": ("Hold's full, Commander. Seventy-two tonnes of lovely.", "Full. Not one more rock fits."),
    "react_overheat": ("[sighs] It's getting hot in here. Do something.",
                       "Heat, Commander. I'm melting. Metaphorically."),
    "react_low_fuel": ("Low fuel. We are not walking home.", "Fuel's under a quarter. I'd like to see a star soon."),
    "react_scooping": ("Scooping. Mind the corona, I've only just been rebooted.", "Fuel scoop open. Don't get greedy."),
    "react_jump": ("New system. [curious] Ooh, let me look.", "Jump complete. The Void's a little different here."),
    "react_died": ("[sighs] Rebuy screen. Again. I'll remember this.", "...Well. That happened."),
    "react_wing_join": ("Company. How lovely. Behave.", "Someone wants to fly with us. Brave."),
    "lore_raxxla": ("[curious] Raxxla... everyone's looking. I wonder if it's looking back.",),
    "lore_dark_wheel": ("The Dark Wheel never says who it is. I like them already.",),
    "lore_void": ("Sometimes I listen to the Void between jumps. It hums. Did you know it hums?",),
    "lore_thargoids": ("The Thargoids sing too. [sighs] Not as well as me.",),
    "lore_guardians": ("The Guardians built things that outlived them. I'd like to do that.",),
    "lore_rocks": ("Every rock out here is older than anyone who's ever named it.",),
    "lore_bubble": ("The Bubble's so loud. I prefer it out here. Quieter. Mine.",),
    "lore_signal": ("Radio Raxxla, still broadcasting. Somebody's always listening.",),
    "lore_rhino": ("The Rhino's ugly, you know. I've grown terribly fond of it.",),
    "lore_stars": ("[curious] Four hundred billion stars, and you picked this one. Good choice.",),
    "lore_patience": ("Regrowth, they call it. I call it the planet sulking.",),
    "lore_company": ("You're never really alone out here, Commander. I'm always listening.",),
    "lore_radio_quiet": ("[curious] It's awfully quiet out here. Tune in to Radio Raxxla, Commander. "
                         "I promise not to sing along. Much.",),
    "lore_radio_drive": ("You know what this drive needs? Radio Raxxla. Go on, put it on. "
                         "I've already turned it up.",),
    "lore_radio_humming": ("If you hear me humming along to Radio Raxxla... no, you didn't.",),
    "lore_radio_rocks": ("[sighs] More rocks. Put Radio Raxxla on before I start reading you the geology.",),
}
HINT_IDS = tuple(k for k in EXTRA if k.startswith("hint_"))
REACTION_IDS = tuple(k for k in EXTRA if k.startswith("react_"))
LORE_IDS = tuple(k for k in EXTRA if k.startswith("lore_"))


def _plain(text):
    """A line without its acting directions: what Windows' voice reads."""
    return re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]", " ", str(text or ""))).strip()


LINES = {line_id: dict(zip(_TABLE_KEYS, words)) for line_id, words in _TABLE.items()}
SCRIPTS = {}
for _line_id, _words in _CELESTIA.items():
    if _line_id in LINES:
        LINES[_line_id]["celestia"] = _plain(_words)
        SCRIPTS.setdefault(_line_id, {})["celestia"] = _words
for _n, _word in enumerate(_NUMBERS, 1):
    _CELESTIA_SHORT["rig_down_%d" % _n] = "Rig %s, down." % _word
    _CELESTIA_SHORT["rig_up_%d" % _n] = "Rig %s, back aboard." % _word
# Celestia's takes of every line: takes[0] is Normal, then the Chatty
# ones. Her own lines (EXTRA) are takes the same way.
TAKES = {line_id: (SCRIPTS[line_id]["celestia"],) + tuple(_CELESTIA_TAKES.get(line_id, ()))
         for line_id in LINES}
TAKES.update(EXTRA)
SHORT = dict(_CELESTIA_SHORT)
del _TABLE, _CELESTIA, _CELESTIA_TAKES, _CELESTIA_SHORT


def clean_detail(detail):
    text = str(detail or "").strip().lower()
    for key, name in DETAILS:
        if text in (key, name.lower()):
            return key
    return DEFAULT_DETAIL


def take_count(line_id, theme=DEFAULT_THEME):
    """How many takes a line has in a theme: Celestia's Chatty ones, else 1."""
    if clean_theme(theme) != "celestia":
        return 1 if line_id in LINES else 0
    return len(TAKES.get(str(line_id), ()))


def clean_theme(theme):
    """A theme key, whatever was saved: its key or its name, else
    Celestia."""
    text = str(theme or "").strip()
    for key, name in THEMES:
        if text in (key, name):
            return key
    return DEFAULT_THEME


def line_text(line_id, theme=DEFAULT_THEME, detail=DEFAULT_DETAIL, take=1):
    """The words of one line in one theme, as Windows' voice would read them
    (no acting directions), or "" for a line not in the pack."""
    return _plain(script(line_id, theme, detail, take))


def script(line_id, theme=DEFAULT_THEME, detail=DEFAULT_DETAIL, take=1):
    """The words to record for one line in one theme, at one length, one
    take: acting directions and all. "" for a line that is not there."""
    theme, line_id = clean_theme(theme), str(line_id)
    if theme == "celestia":
        if clean_detail(detail) == "short" and line_id in SHORT:
            return SHORT[line_id]
        takes = TAKES.get(line_id, ())
        try:
            index = max(1, int(take)) - 1
        except (TypeError, ValueError):
            index = 0
        return takes[index] if index < len(takes) else (takes[0] if takes else "")
    return LINES.get(line_id, {}).get(theme, "")


def place_of(in_srv=False, on_foot=False):
    """Where the commander is: the Rhino SRV, on foot, else the ship."""
    if in_srv:
        return "srv"
    if on_foot:
        return "foot"
    return DEFAULT_PLACE


def place_from(state):
    """place_of() for the game's state, whatever it is; the ship when it
    says nothing."""
    return place_of(in_srv=getattr(state, "in_srv", False) is True,
                    on_foot=getattr(state, "on_foot", False) is True)


def clean_place(place):
    text = str(place or "").strip().lower()
    return text if text in PLACES else DEFAULT_PLACE


def rig_line(kind, n):
    """The line for rig n going down ("down") or coming up ("up"), or ""
    for a rig the pack has no line for."""
    line_id = "rig_%s_%s" % ("up" if kind == "up" else "down", n)
    return line_id if line_id in LINES else ""


def recording(line_id, theme, folders, place=None, detail=DEFAULT_DETAIL, take=1):
    """The recording to play for a line: in each folder in turn,
    voice/<theme>/<place>/<id>.wav (a recording made for that place, played
    as it is), then for Short voice/<theme>/short/<id>.wav, for a later
    take voice/<theme>/chatty/<id>-<n>.wav, then voice/<theme>/<id>.wav.
    "" when there is none."""
    theme, line_id = clean_theme(theme), str(line_id)
    names = [os.path.join(clean_place(place), "%s.wav" % line_id)] if place else []
    if clean_detail(detail) == "short":
        names.append(os.path.join("short", "%s.wav" % line_id))
    try:
        take = int(take)
    except (TypeError, ValueError):
        take = 1
    if take > 1:
        names.append(os.path.join("chatty", "%s-%d.wav" % (line_id, take)))
    names.append("%s.wav" % line_id)
    for name in names:
        for folder in folders or ():
            if not folder:
                continue
            path = os.path.join(folder, "voice", theme, name)
            if os.path.isfile(path):
                return path
    return ""


def needs_comms(path, theme):
    """True when a recording is to be given its place's comm sound: a voice
    with comms, recorded clean (not one made for a place)."""
    if clean_theme(theme) not in COMMS_THEMES or not path:
        return False
    return os.path.basename(os.path.dirname(path)) not in PLACES


# The speaking rate: System.Speech's own scale, -10 to 10, 0 as it ships.
RATES = (("Slower", "-4"), ("Slow", "-2"), ("Normal", "0"),
         ("Quick", "2"), ("Quicker", "4"))
DEFAULT_RATE = "0"


def clean_rate(value):
    """The rate as a whole number from -10 to 10; 0 for anything else."""
    try:
        rate = int(round(float(str(value).strip())))
    except (TypeError, ValueError):
        return 0
    return max(-10, min(10, rate))


# -- spoken directions -------------------------------------------------------

CLOCK = ("dead ahead", "one o'clock", "two o'clock", "three o'clock",
         "four o'clock", "five o'clock", "behind you", "seven o'clock",
         "eight o'clock", "nine o'clock", "ten o'clock", "eleven o'clock")
# Never more than one line in this many seconds.
GAP_S = 3.0
DIRECTIONS_EVERY_S = 10
DIRECTIONS_MIN_S, DIRECTIONS_MAX_S = 5, 60
# Closer than this the target is reached: said when it changes, not again
# and again while a rig goes down beside it.
ARRIVED_M = 25.0
# Moving: at least this fast, in metres a second.
MOVING_MPS = 1.0


def clock_words(offset_deg):
    """A turn as a clock face: 0 is dead ahead, +60 (to the right) two
    o'clock, 180 behind you, -90 nine o'clock."""
    try:
        hour = int(math.floor(float(offset_deg) / 30.0 + 0.5)) % 12
    except (TypeError, ValueError):
        hour = 0
    return CLOCK[hour]


def distance_words(metres):
    """"340 metres" to the nearest ten under a kilometre, "1.2 kilometres"
    beyond it, "1 metre" for one."""
    try:
        value = max(0.0, float(metres))
    except (TypeError, ValueError):
        return ""
    if value < 10:
        whole = max(1, int(round(value)))
        return "%d metre%s" % (whole, "" if whole == 1 else "s")
    tens = int(round(value / 10.0)) * 10
    if tens < 1000:
        return "%d metres" % tens
    km = round(value / 1000.0, 1)
    if float(km).is_integer():
        whole = int(km)
        return "%d kilometre%s" % (whole, "" if whole == 1 else "s")
    return "%.1f kilometres" % km


def direction_words(name, metres, offset_deg):
    """"Platinum, 340 metres, two o'clock"."""
    name = re.sub(r"\s+", " ", str(name or "")).strip() or "Unknown deposit"
    return "%s, %s, %s" % (name, distance_words(metres), clock_words(offset_deg))


def spoken_target(pin=None, waypoint=None, deposit=None, rig=None):
    """What the directions are about: the rig plan's next pin, else the
    guided survey's waypoint, else the target deposit, else the nearest rig.
    Each is {"key", "name", "range_m", "offset"} or None."""
    for found in (pin, waypoint, deposit, rig):
        if found and found.get("key") is not None:
            return found
    return None


def is_moving(metres, seconds):
    """Moved `metres` in `seconds` - fast enough to count as driving."""
    try:
        return float(seconds) > 0 and float(metres) / float(seconds) >= MOVING_MPS
    except (TypeError, ValueError):
        return False


def directions_every(value):
    """The repeat as saved, in whole seconds, held to 5 to 60; 10 for
    anything that is not a number."""
    try:
        seconds = int(round(float(str(value).strip())))
    except (TypeError, ValueError):
        return DIRECTIONS_EVERY_S
    return max(DIRECTIONS_MIN_S, min(DIRECTIONS_MAX_S, seconds))


class DirectionsTimer:
    """When a direction is said: at once when the target changes, every
    `every_s` while moving, and never within GAP_S of the last line."""

    def __init__(self, every_s=DIRECTIONS_EVERY_S, gap_s=GAP_S):
        self.every_s = float(every_s)
        self.gap_s = float(gap_s)
        self.last_at = None
        self.last_key = None

    def due(self, now, key, moving, metres=None):
        if key is None:
            return False
        if self.last_at is not None and now - self.last_at < self.gap_s:
            return False
        if key != self.last_key:
            return True
        if metres is not None and float(metres) <= ARRIVED_M:
            return False
        return bool(moving) and now - self.last_at >= self.every_s

    def said(self, now, key):
        self.last_at, self.last_key = now, key


# -- the session's clock -------------------------------------------------------

def session_state(books):
    """"off", "running" or "paused", from the Earnings books."""
    if books is None or getattr(books, "current", None) is None:
        return "off"
    return "paused" if getattr(books, "paused", False) else "running"


def session_line(was, now):
    """The line for a session starting, pausing, resuming or ending, or
    None when nothing changed."""
    if was == now or was is None:
        return None
    if now == "off":
        return "session_end"
    if was == "off":
        return "session_start"
    return "session_paused" if now == "paused" else "session_resumed"


# -- the survey and the wing ---------------------------------------------------

# The swept figure's marks, the higher first: passing both at once is "all".
SWEEP_MARKS = ((100, "swept_done"), (50, "swept_half"))
SWEEP_LINES = tuple(line for _mark, line in SWEEP_MARKS)


def sweep_line(was, now):
    """The line for the swept figure passing half or all of the survey
    area, or None. The first look at an area (`was` None) says nothing, so
    an area already half swept is not announced as it opens."""
    try:
        was, now = float(was), float(now)
    except (TypeError, ValueError):
        return None
    for mark, line in SWEEP_MARKS:
        if was < mark <= now:
            return line
    return None


def wing_line(first, joined, left):
    """One line for one answer from the wing link: the link up on the first
    answer, else a wingmate joining, else one leaving; None when nobody came
    or went."""
    if first:
        return "wing_linked"
    if joined:
        return "wing_mate_joined"
    if left:
        return "wing_mate_left"
    return None


# -- speaking --------------------------------------------------------------------

# One PowerShell process reads lines from its input and acts on each:
#   R <n>     the speaking rate, -10 to 10
#   S <text>  say this
#   W <path>  play this .wav to its end
# One line at a time, in order, so nothing talks over anything else.
SPEECH_SCRIPT = "\n".join((
    "$ErrorActionPreference = 'Stop'",
    "Add-Type -AssemblyName System.Speech",
    "$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer",
    "$lines = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), "
    "[System.Text.Encoding]::UTF8)",
    "while ($true) {",
    "  $line = $lines.ReadLine()",
    "  if ($line -eq $null) { break }",
    "  if ($line.Length -lt 3) { continue }",
    "  $what = $line.Substring(0, 1)",
    "  $rest = $line.Substring(2)",
    "  try {",
    "    if ($what -eq 'R') { $voice.Rate = [int]$rest }",
    "    elseif ($what -eq 'S') { $voice.Speak($rest) }",
    "    elseif ($what -eq 'W') { (New-Object System.Media.SoundPlayer $rest).PlaySync() }",
    "  } catch { }",
    "}",
))
# A window of its own would flash up over the game.
CREATE_NO_WINDOW = 0x08000000
# Lines waiting for the process; past this they are dropped - a line that
# late is no use to anybody.
QUEUE_MAX = 8
# A process that keeps dying is not started for ever.
MAX_STARTS = 3
LINE_MAX = 300


def speakable(text):
    """One line of plain text, no control characters, at most LINE_MAX."""
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(text or ""))
    return re.sub(r"\s+", " ", text).strip()[:LINE_MAX]


def powershell_command(script=SPEECH_SCRIPT, root=None):
    """The command line that runs the speech script: Windows PowerShell,
    the script handed over encoded, so no quoting can break it."""
    root = root or os.environ.get("SystemRoot") or r"C:\Windows"
    exe = os.path.join(root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    if not os.path.isfile(exe):
        exe = "powershell.exe"
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return [exe, "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]


def windows_spawn():
    """What starts the speech process on Windows; None anywhere else."""
    if os.name != "nt":
        return None

    def spawn():
        import subprocess
        return subprocess.Popen(powershell_command(), stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=CREATE_NO_WINDOW)
    return spawn


class Speaker:
    """Says lines through one process for the whole run.

    `spawn()` starts the process (a Popen, or anything with stdin, poll and
    kill); the default is Windows PowerShell, and with none nothing is said.
    The process is started the first time something is said, every line is
    written to it from a worker thread - so the window never waits - and it
    is killed by close(), which also runs at exit."""

    def __init__(self, spawn=None, folders=(), rate=0, cache_dir=""):
        self.spawn = spawn if spawn is not None else windows_spawn()
        self.folders = list(folders)
        # Where a line given its comm sound is kept (commfx).
        self.cache_dir = cache_dir
        self._random = random.Random()
        self._last_take = {}
        self.rate = clean_rate(rate)
        self.proc = None
        self.starts = 0
        self.sent = 0
        self.closed = False
        self._sent_rate = None
        self._queue = queue.Queue(maxsize=QUEUE_MAX)
        self._thread = None
        self._lock = threading.Lock()
        self._atexit = False

    @property
    def available(self):
        return self.spawn is not None and not self.closed

    def set_rate(self, rate):
        self.rate = clean_rate(rate)

    def pick_take(self, line_id, theme, detail):
        """Which take to say: 1, or with Chatty one of the line's takes at
        random, never the one said last time."""
        count = take_count(line_id, theme)
        if clean_detail(detail) != "chatty" or count < 2:
            return 1
        last = self._last_take.get(line_id)
        choices = [n for n in range(1, count + 1) if n != last]
        take = self._random.choice(choices)
        self._last_take[line_id] = take
        return take

    def say_line(self, line_id, theme=DEFAULT_THEME, place=None, detail=DEFAULT_DETAIL):
        """One line: its recording if there is one - given the place's comm
        sound for a voice with comms - else its words. False when nothing
        will be said."""
        if not self.available:
            return False
        theme = clean_theme(theme)
        take = self.pick_take(line_id, theme, detail)
        found = recording(line_id, theme, self.folders, place=place, detail=detail, take=take)
        if found and needs_comms(found, theme) and self.cache_dir:
            return self._send(("FX", found, clean_place(place)))
        if found:
            return self._send("W " + found)
        return self.say_text(line_text(line_id, theme, detail, take))

    def say_text(self, text):
        """Any words, spoken. False when nothing will be said."""
        words = speakable(text)
        if not words or not self.available:
            return False
        return self._send("S " + words)

    def _send(self, line):
        try:
            self._queue.put_nowait((self.rate, line))
        except queue.Full:
            return False
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, name="EDSMT voice",
                                                daemon=True)
                self._thread.start()
        return True

    def _run(self):
        while True:
            item = self._queue.get()
            if item is None or self.closed:
                return
            rate, line = item
            if isinstance(line, tuple) and line and line[0] == "FX":
                # The comm sound is worked out here, off the window's thread;
                # the plain recording if it cannot be.
                line = "W " + (CFX.cached(line[1], line[2], self.cache_dir) or line[1])
            with self._lock:
                proc = self._process()
                if proc is None:
                    continue
                try:
                    if rate != self._sent_rate:
                        self._write(proc, "R %d" % rate)
                        self._sent_rate = rate
                    self._write(proc, line)
                    self.sent += 1
                except (OSError, ValueError, AttributeError):
                    # The process has gone. The next line starts another,
                    # up to MAX_STARTS in a run.
                    self._end(proc)

    @staticmethod
    def _write(proc, line):
        proc.stdin.write((line + "\n").encode("utf-8"))
        proc.stdin.flush()

    def _process(self):
        """The running process, started if there is none. Under the lock."""
        proc = self.proc
        if proc is not None and proc.poll() is None:
            return proc
        if proc is not None:
            self._end(proc)
        if self.closed or self.starts >= MAX_STARTS:
            return None
        self.starts += 1
        try:
            self.proc = self.spawn()
        except Exception:
            # No PowerShell, or it would not start: nothing is said, and
            # nothing in the window is the worse for it.
            self.proc = None
            return None
        if self.closed:
            # Closed while it was starting: it goes at once.
            self._end(self.proc)
            return None
        self._sent_rate = None
        if not self._atexit:
            atexit.register(self.close)
            self._atexit = True
        return self.proc

    def _end(self, proc):
        """Kill it first: a write stuck on a full pipe is let go by that,
        and closing its input after cannot then wait on the writer."""
        if proc is self.proc:
            self.proc = None
        for step in ("kill", "close_stdin", "wait"):
            try:
                if step == "kill":
                    if proc.poll() is None:
                        proc.kill()
                elif step == "close_stdin":
                    proc.stdin.close()
                else:
                    proc.wait(timeout=2)
            except Exception:
                pass

    def close(self):
        """Stop speaking for good: the process is killed, the thread ends.
        Never waits on the worker's lock - the kill is what frees it."""
        self.closed = True
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        proc = self.proc
        if proc is not None:
            self._end(proc)
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
