"""The window's side of 1.10035's input: chat tags, deposits marked from
range, joystick buttons and the long press of the mouse.

chattags.py and inputdev.py know nothing of the window; this is where they
meet it. Everything here is a function of the main window ("app"), called
from small methods on it, so the window keeps one place per feature and this
file can be read, and checked, on its own.

What each part does to the window:

  - chat: the journal reader queues the commander's own SendText lines; every
    tick they are read, and any that start with the prefix in Settings are run
    as the key or the button they stand for, with a line on the status bar and
    over the game saying what was done (or why not).
  - from range: a bearing and a distance from the Rhino become a place on the
    body. The deposit is marked "placed from range" and stays on this machine;
    MARK or UPDATE pressed within REFINE_M of it moves it to where it really
    is, and only then is it shared.
  - joystick: a timer, only while a button is bound, queues the same action
    names the hotkeys use, so a button and a key run exactly the same code.
  - long press: a timer, only in the Rhino with the switch on, queues "rigs".
"""
import time

import chattags as CT
import gamebinds as GB
import inputdev as IND
import survey as SV

# A deposit marked longer ago than this is not "the last one": !rr undo will
# not reach back through a night's work to take away something old.
UNDO_WITHIN_S = 600.0
SEEN_MAX = 200
# Where a timer that hit a fault looks again.
RETRY_MS = 1000


class InputState:
    """What the input features keep between ticks. One per window."""

    def __init__(self):
        self.started_at = time.time()      # chat older than this is history
        self.joystick = IND.JoystickWatcher()
        self.mouse = IND.WinMouse()          # whether the game is in front
        self.longpress = IND.LongPress()     # kept for older callers
        # 1.10036: the rig button is the game's own Primary or Secondary fire
        # for the SRV, read from the commander's .binds (gamebinds.py).
        self.reader = GB.BindReader()
        self.hold = IND.HoldWatcher()
        self.binds = None                    # what fire_bindings() last said
        self.binds_at = -1e9
        self.clock = time.monotonic        # replaceable, for the checks
        self.joy_after = None              # the pending timer, or None
        self.mouse_after = None
        self.seen = []                     # (when, message) already run


def state(app):
    """The window's InputState, made on first use."""
    held = app.__dict__.get("_edsmt_input")
    if held is None:
        held = app._edsmt_input = InputState()
    return held


def tones(app):
    """The colours the window says things in: ok, warn, bad."""
    try:
        return app.input_tones()
    except AttributeError:
        return {}


def settings_of(app):
    return app.__dict__.get("settings") or {}


# ---------------------------------------------------------------------------
# Saying what happened
# ---------------------------------------------------------------------------

def reply(app, kind, title, detail="", text=None, via=""):
    """One line on the status bar and a short one over the game."""
    colour = tones(app).get(kind)
    words = text if text is not None else ("%s. %s" % (title, detail)).strip(". ")
    app.say(("Chat tag: %s" % words) if via == "chat" else words, colour)
    app.flash(title, detail, colour)
    return None


def refuse(app, why, via=""):
    """Not done, and said why - on screen and over the game."""
    return reply(app, "warn", "NOT DONE" if via != "chat" else "CHAT TAG - NOT DONE",
                 why[:70], text=why, via=via)


# ---------------------------------------------------------------------------
# Marking a deposit: here, or from range
# ---------------------------------------------------------------------------

def boxes(app):
    """What the four boxes on the rail say."""
    fields = app.__dict__.get("fields") or {}
    out = {}
    for name in ("commodity", "rigs", "amount", "density"):
        try:
            out[name] = str(fields[name].get() or "").strip()
        except (KeyError, AttributeError):
            out[name] = ""
    return out


def clear_boxes(app, names):
    fields = app.__dict__.get("fields") or {}
    for name in names:
        try:
            fields[name].set("")
        except (KeyError, AttributeError):
            pass
    filled = app.__dict__.get("_autofilled")
    if isinstance(filled, dict) and "density" in names:
        filled.pop("density", None)


def nearest_same(app, system, body, commodity, lat, lon, radius_m, ranged=None):
    """(metres, row) for the nearest own deposit of this commodity to a point.

    `ranged` True keeps only deposits placed from range, False only the rest,
    None all."""
    wanted = SV.fold(commodity)
    best = None
    for row in app.store.at(system, body):
        if wanted and SV.fold(row.get("commodity")) != wanted:
            continue
        if ranged is not None and CT.is_ranged(row) != ranged:
            continue
        try:
            metres = SV.surface_range_m(lat, lon, float(row["lat"]),
                                        float(row["lon"]), radius_m)
        except (KeyError, TypeError, ValueError):
            continue
        if best is None or metres < best[0]:
            best = (metres, row)
    return best


def mark(app, spec=None, bearing=None, metres=None, via=""):
    """Mark a deposit where the Rhino is, or `metres` away on `bearing`.

    `spec` carries what the message or window said - commodity, amount,
    density, rigs; anything it leaves out is read off the boxes on the rail
    (and the scanner, for density), exactly as MARK DEPOSIT reads them.
    Returns the new row, or None after saying why not."""
    spec = spec or {}
    game = app.game
    if not (game and game.has_position):
        return refuse(app, "No surface position from the game yet.", via)
    ranged = bearing is not None
    radius = game.radius_m
    if ranged and not radius:
        return refuse(app, "The game has not said how big this body is yet, so "
                           "a distance cannot be worked out. Try again in a "
                           "moment.", via)
    have = boxes(app)
    taken = []

    def pick(name, fallback=""):
        if spec.get(name):
            return str(spec[name]).strip()
        value = have[name] or fallback
        if have[name]:
            taken.append(name)
        return value

    typed = spec.get("commodity") or have["commodity"] or game.detected_type or ""
    if not typed:
        return refuse(app, "Which commodity? Say it in the message, or pick "
                           "one on the left.", via)
    commodity = SV.canonical(typed) or typed
    if not spec.get("commodity") and have["commodity"]:
        taken.append("commodity")
    amount = pick("amount")
    density = pick("density", getattr(game, "detected_density", "") or "")
    rigs = pick("rigs")
    try:
        rigs = str(int(float(rigs))) if rigs != "" else ""
    except ValueError:
        rigs = ""
    missing = [word for word, value in (("rigs", rigs), ("amount", amount),
                                        ("density", density)) if not value]
    if rigs and not 1 <= int(rigs) <= IND.RIGS:
        return refuse(app, "The Rhino carries %d rigs, so 1 to %d."
                           % (IND.RIGS, IND.RIGS), via)
    if missing:
        return refuse(app, "Not marked - it still needs the %s. Say them in "
                           "the message, or fill in the boxes on the left."
                           % " and ".join(missing), via)

    system, body = app.here()
    if ranged:
        lat, lon = CT.place(game.lat, game.lon, bearing, metres, radius)
    else:
        # MARK DEPOSIT at the spot of a deposit placed from range is the
        # refinement, whichever way MARK was asked for.
        refined = refine_ranged(app, commodity, spec, via)
        if refined is not None:
            return refined
        lat, lon = game.lat, game.lon
    twin = nearest_same(app, system, body, commodity, lat, lon,
                        radius or 1e6, ranged=None)
    if twin is not None and twin[0] <= CT.SAME_SPOT_M:
        return refuse(app, "%s is already marked %s from there. UPDATE at the "
                           "spot changes it, and undo takes the last one back."
                           % (commodity, CT.distance_words(twin[0])), via)

    app.remember_body(system, body)
    world = game.body_profile()
    temperature = game.body_temperature()
    record = app.store.add_deposit(
        system=system, body=body, location=app.signal(), commodity=commodity,
        rigs=rigs, density=density, amount=amount,
        lat="%.6f" % lat, lon="%.6f" % lon,
        temperature_k="" if temperature is None else "%.1f" % temperature,
        planet_class=world["planet_class"], gravity=world["gravity"],
        atmosphere=world["atmosphere"], volcanism=world["volcanism"],
        status=SV.STATUS_REPORTED, cmdr=game.cmdr or "",
        notes=CT.ranged_note("", bearing, metres) if ranged else "")
    if not ranged and app.store.location(system, body, app.signal()) is None:
        app.store.set_location(system, body, app.signal(), lat=game.lat,
                               lon=game.lon, radius_m=radius or 1e6,
                               temperature_k=temperature,
                               planet_class=world["planet_class"],
                               gravity=world["gravity"],
                               atmosphere=world["atmosphere"],
                               volcanism=world["volcanism"], cmdr=game.cmdr or "")
    app.refresh_locations()
    app.refresh_deposits()
    app.refresh_commodities()
    app.redraw()
    if not ranged:
        app.share(record)
        app.post_discord_find(record)
    clear_boxes(app, [n for n in taken if n != "commodity"])
    rigs_words = " (%s rigs)" % rigs if rigs else ""
    if ranged:
        where = "%s on %03.0f°" % (CT.distance_words(metres), bearing)
        reply(app, "ok", "FROM RANGE  %s" % commodity.upper()[:20], where,
              text="Marked %s%s %s away, placed from range. It stays on this "
                   "machine until you MARK or UPDATE at the spot." % (
                       commodity, rigs_words, where), via=via)
    else:
        reply(app, "ok", "MARKED  %s" % commodity.upper()[:22],
              "%s rigs, %s" % (rigs, amount) if rigs else amount,
              text="Marked %s%s at %.5f, %.5f." % (commodity, rigs_words,
                                                   lat, lon), via=via)
    return record


def mark_from_range(app, bearing, metres, spec=None):
    """The window's entry point: a bearing and a distance, and the boxes."""
    return mark(app, spec, bearing=bearing, metres=metres)


def refine_ranged(app, commodity="", spec=None, via=""):
    """MARK or UPDATE at the spot of a deposit placed from range: move it
    there. The refined row, or None when there is nothing to refine.

    Only a deposit placed from range, within REFINE_M, of the commodity
    asked for (any, if none is). Standing on a deposit that was marked at
    its spot is not this - that one is the one being talked about."""
    game = app.game
    if not (game and game.has_position):
        return None
    system, body = app.here()
    radius = game.radius_m or 1e6
    found = nearest_same(app, system, body, commodity, game.lat, game.lon,
                         radius, ranged=True)
    if found is None or found[0] > CT.REFINE_M:
        return None
    real = nearest_same(app, system, body, commodity, game.lat, game.lon,
                        radius, ranged=False)
    if real is not None and real[0] <= CT.SAME_SPOT_M:
        return None
    moved, row = found
    spec = spec or {}
    have = boxes(app)
    changes = {"lat": "%.6f" % game.lat, "lon": "%.6f" % game.lon,
               "notes": CT.refined_note(row.get("notes"), moved)}
    taken = []
    for name in ("amount", "density", "rigs"):
        value = str(spec.get(name) or have[name] or "").strip()
        if have[name] and not spec.get(name):
            taken.append(name)
        if value and value != str(row.get(name) or ""):
            changes[name] = value
    if "density" not in changes and getattr(game, "detected_density", "") \
            and not row.get("density"):
        changes["density"] = game.detected_density
    updated = app.deposit_edited(row["id"], changes)
    if not updated:
        return None
    app.post_discord_find(updated)
    clear_boxes(app, taken)
    reply(app, "ok", "REFINED  %s" % str(row.get("commodity") or "").upper()[:20],
          "moved %s" % CT.distance_words(moved),
          text="%s is now where you are, %s from where range put it. It has "
               "gone to the community map." % (row.get("commodity") or "The "
                                               "deposit", CT.distance_words(moved)),
          via=via)
    return updated


def undo_last(app, via=""):
    """Take back the deposit marked last, if that was in the last ten minutes."""
    now = time.time()
    newest = None
    for row in app.store.deposits:
        stamp = SV._epoch(row.get("recorded"))
        if stamp and 0 <= now - stamp <= UNDO_WITHIN_S \
                and (newest is None or stamp >= newest[0]):
            newest = (stamp, row)
    if newest is None:
        return refuse(app, "Nothing was marked in the last %d minutes to take "
                           "back." % (UNDO_WITHIN_S // 60), via)
    row = newest[1]
    name = row.get("commodity") or "the deposit"
    if not app.delete_deposit(row["id"]):
        return refuse(app, "That deposit is no longer there.", via)
    reply(app, "ok", "TAKEN BACK  %s" % str(name).upper()[:20], "",
          text="Took back %s. It is gone from this machine." % name, via=via)
    return row


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

def run_command(app, cmd):
    """Do what a parsed chat command says. Returns what it was, for the checks."""
    action = cmd.get("action")
    if action == "error":
        refuse(app, cmd.get("why") or "Not understood.", "chat")
    elif action == "mark":
        mark(app, cmd, via="chat")
    elif action == "range":
        mark(app, cmd, bearing=cmd["bearing"], metres=cmd["metres"], via="chat")
    elif action == "undo":
        undo_last(app, "chat")
    elif action in ("rig_down", "rig_up", "all_up", "centre"):
        run = {"rig_down": lambda: app.drop_rigs(cmd.get("rig")),
               "rig_up": lambda: app.rig_up(cmd.get("rig")),
               "all_up": app.rigs_up,
               "centre": app.set_survey_centre}[action]
        app._flashed = False
        run()
        if not app.__dict__.get("_flashed"):
            app.flash_said()
    return action


def handle_chat(app, note):
    """One SendText from the journal. The command run, or None.

    Only a message the game sent (Sent not false), starting with the prefix
    as a word of its own, typed since EDSMT began looking and not long
    before now, and not already run."""
    if not note.get("sent", True):
        return None
    prefix = CT.clean_prefix(settings_of(app).get("chat_prefix"))
    if CT.addressed(note.get("message"), prefix) is None:
        return None
    st = state(app)
    if not CT.is_fresh(note, since=st.started_at - 2.0):
        return None
    key = (note.get("when"), note.get("message"))
    if key in st.seen:
        return None
    st.seen.append(key)
    del st.seen[:-SEEN_MAX]
    cmd = CT.parse_command(note.get("message"), prefix)
    return run_command(app, cmd) if cmd else None


def take_chat(app):
    """Everything the commander typed since last tick. Read and dropped when
    the switch is off, so turning it on never replays the past."""
    drain = getattr(app.watcher, "drain_chat", None)
    notes = drain() if callable(drain) else []
    if not settings_of(app).get("chat_tags"):
        return []
    done = []
    for note in notes:
        # One command that fails must not take the ones after it with it:
        # they have been drained and would not be read again.
        try:
            done.append(handle_chat(app, note))
        except Exception as exc:
            app.trouble("Chat command", exc)
    return done


# ---------------------------------------------------------------------------
# Joystick buttons and the long press
# ---------------------------------------------------------------------------

def press(app, action):
    """Run an action as its hotkey would: queued for the next fast tick, where
    the same table runs it with the same flash and the same fault handling."""
    keys = app.__dict__.get("hotkeys")
    events = getattr(keys, "events", None)
    if events is None:
        return False
    events.put(action)
    return True


def joystick_bindings(app):
    """{(device, button): action} from settings."""
    settings = settings_of(app)
    out = {}
    for action in IND.JOY_ACTIONS:
        parsed = IND.parse_joy(settings.get(IND.joy_key(action)))
        if parsed:
            out[parsed] = action
    return out


def ensure_joystick(app):
    st = state(app)
    if st.joy_after is None and st.joystick.available() and joystick_bindings(app):
        st.joystick.forget()
        st.joy_after = app.after(IND.POLL_MS, lambda: joystick_tick(app))


def joystick_tick(app):
    """One look at the buttons; asks to be called again while any is bound."""
    st = state(app)
    st.joy_after = None
    bindings = joystick_bindings(app)
    if not bindings or not st.joystick.available():
        return
    delay = IND.POLL_MS
    try:
        # Settings is listening for a button to bind: it takes the presses.
        if not st.joystick.muted:
            for action in st.joystick.poll(bindings):
                press(app, action)
    except Exception as exc:
        # Named on screen, and looked at again in a second rather than twenty
        # times a second: a fault that persists must not flood the status bar.
        app.trouble("Joystick", exc)
        delay = RETRY_MS
    st.joy_after = app.after(delay, lambda: joystick_tick(app))


def mouse_wanted(app):
    """In the Rhino, and the switch is on."""
    if not settings_of(app).get("long_press_rig"):
        return False
    game = app.__dict__.get("game")
    return bool(game is not None
                and getattr(game, "in_rhino", getattr(game, "in_srv", False)))


BINDS_REFRESH_S = 30.0
# The game's own defaults, for a PC whose binds cannot be read: Primary fire
# is the left mouse button and Secondary fire the right.
DEFAULT_FIRE = {"primary": [{"device": "Mouse", "key": "Mouse_1", "modifiers": []}],
                "secondary": [{"device": "Mouse", "key": "Mouse_2", "modifiers": []}]}


def fire_choice(settings):
    """"primary" or "secondary". Older settings said "left", "right" or
    "learn", and read as the fire button those were on the game's defaults."""
    value = str((settings or {}).get("long_press_button") or "primary").lower()
    return "secondary" if value in ("secondary", "right") else "primary"


def rig_binds(app, now=None, force=False):
    """The commander's SRV fire binds, read again every BINDS_REFRESH_S
    (a change in the game's Controls takes effect without a restart)."""
    st = state(app)
    now = st.clock() if now is None else now
    if force or st.binds is None or now - st.binds_at >= BINDS_REFRESH_S:
        st.binds = GB.fire_bindings()
        st.binds_at = now
        st.reader.forget()
    return st.binds


def rig_inputs(app, now=None):
    """What a long press of counts as a rig: the chosen fire binding."""
    which = fire_choice(settings_of(app))
    found = rig_binds(app, now) or {}
    return list(found.get(which) or DEFAULT_FIRE[which]) if not found.get("why") \
        else list(DEFAULT_FIRE[which])


def ensure_mouse(app):
    st = state(app)
    if st.mouse_after is None and st.mouse.available() and mouse_wanted(app):
        # Held already on the way into the Rhino is not the start of a press.
        st.hold.reset(st.reader.any_down(rig_inputs(app)))
        st.mouse_after = app.after(IND.POLL_MS, lambda: mouse_tick(app))


def mouse_tick(app):
    """One look at the fire binding; asks to be called again while wanted."""
    st = state(app)
    st.mouse_after = None
    if not mouse_wanted(app):
        st.hold.reset()
        return
    delay = IND.POLL_MS
    try:
        down = st.reader.any_down(rig_inputs(app))
        if st.hold.step(down, st.mouse.elite_in_front(), st.clock()):
            press(app, "rigs")
    except Exception as exc:
        app.trouble("Long press", exc)
        delay = RETRY_MS
    st.mouse_after = app.after(delay, lambda: mouse_tick(app))


def follow_input(app):
    """Once a tick: the chat, and the two timers kept alive while wanted.
    A fault here is named on screen and never stops the tick."""
    try:
        take_chat(app)
        ensure_joystick(app)
        ensure_mouse(app)
    except Exception as exc:
        app.trouble("Input", exc)
