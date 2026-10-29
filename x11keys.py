"""Global hotkeys on Linux, through the X server (1.10039).

On Windows the work keys are RegisterHotKey. On Linux the same thing is a
passive key grab on the root window: XGrabKey tells the X server that a
key with a given set of modifiers belongs to this client, whichever window
has the keyboard, and the server reports the KeyPress to the client that
asked. The root window is an ancestor of every window, which is what makes
the grab global.

What that needs, and what it does without:

  * python-xlib. Optional: without it the keys are off and Settings says
    which library to install. Nothing else in the app needs it.
  * An X display. On a Wayland session the grab would reach only the
    programs that run through XWayland, and whether the game is one of
    them depends on the launcher, so the keys are off there and Settings
    says so. Joystick buttons and chat commands still work.
  * A key nobody else holds. A second grab of the same key and modifiers
    is refused by the server (BadAccess), which is how "already taken by
    another program" is known.

Caps Lock and Num Lock are modifiers to the server, so each key is grabbed
four times - plain, with Lock, with Mod2 (Num Lock), with both - or Alt+1
would stop working the moment Num Lock went on. Alt is Mod1 and the Super
key is Mod4 on every usual keymap.

Every call into the X server goes through XServer, which is the only
thing here that imports the library; the checks give X11Hotkeys a stand-in
with the same five methods. No key is written down anywhere.
"""
import os
import queue
import threading
import time

# X protocol modifier masks (X.h), as the server reports them.
SHIFT, LOCK, CONTROL, MOD1, MOD2, MOD4 = 0x01, 0x02, 0x04, 0x08, 0x10, 0x40
# Lock keys make no difference to a binding; these are the four ways they
# can be, and the mask that is left once they are taken off a press.
LOCKS = (0, LOCK, MOD2, LOCK | MOD2)
RELEVANT = SHIFT | CONTROL | MOD1 | MOD4
# How often the loop looks for presses; a key feels instant well under this.
POLL_S = 0.02

MODIFIER_MASKS = {"CTRL": CONTROL, "CONTROL": CONTROL, "ALT": MOD1,
                  "SHIFT": SHIFT, "WIN": MOD4, "SUPER": MOD4, "META": MOD4,
                  "CMD": MOD4, "WINDOWS": MOD4}

# The app's key names (edsmt.VK) that are not already an X keysym name.
# Letters go through lower(); digits and F-keys are the same in both.
KEYSYMS = {
    "ENTER": "Return", "ESC": "Escape", "SPACE": "space", "TAB": "Tab",
    "BACKSPACE": "BackSpace", "INSERT": "Insert", "DELETE": "Delete",
    "HOME": "Home", "END": "End", "PAGEUP": "Prior", "PAGEDOWN": "Next",
    "PAUSE": "Pause", "LEFT": "Left", "UP": "Up", "RIGHT": "Right",
    "DOWN": "Down",
    "NUMPAD*": "KP_Multiply", "NUMPAD+": "KP_Add", "NUMPAD-": "KP_Subtract",
    "NUMPAD.": "KP_Decimal", "NUMPAD/": "KP_Divide",
    ";": "semicolon", "=": "equal", ",": "comma", "-": "minus",
    ".": "period", "/": "slash", "`": "grave", "[": "bracketleft",
    "\\": "backslash", "]": "bracketright", "'": "apostrophe", "+": "plus",
}
KEYSYMS.update({"NUMPAD%d" % n: "KP_%d" % n for n in range(10)})


def parse(binding):
    """"CTRL+ALT+K" -> (X modifier mask, keysym name), or None.

    None is a binding the X side cannot make - two real keys, nothing, or a
    key with no keysym name here - and the caller says so by name."""
    text = str(binding or "").strip()
    # A key that IS a plus sign ends the text with one, which splitting on
    # + would eat: take it off first and put it back as the key.
    plus = None
    for tail in ("NUMPAD+", "+"):
        if text.upper().endswith(tail):
            plus, text = tail, text[:-len(tail)]
            break
    parts = [p.strip().upper() for p in text.split("+") if p.strip()]
    if plus:
        parts.append(plus)
    if not parts:
        return None
    mask, key = 0, None
    for part in parts:
        if part in MODIFIER_MASKS:
            mask |= MODIFIER_MASKS[part]
        elif key is None:
            key = part
        else:
            return None
    if key is None:
        return None
    if key in KEYSYMS:
        return mask, KEYSYMS[key]
    if len(key) == 1 and key.isalnum():
        return mask, key.lower()
    if len(key) in (2, 3) and key[0] == "F" and key[1:].isdigit():
        return mask, key
    return None


def why_not(environ, have_xlib=None):
    """Why the keys are off on this desktop, or "" when they can be on.

    `have_xlib` is whether python-xlib imports; None asks."""
    if have_xlib is None:
        have_xlib = XServer.available()
    if not have_xlib:
        return ("global hotkeys on Linux need python-xlib - "
                "pip install python-xlib, then restart EDSMT")
    if environ.get("WAYLAND_DISPLAY") or \
            str(environ.get("XDG_SESSION_TYPE", "")).lower() == "wayland":
        return ("global hotkeys are off on a Wayland session - use joystick "
                "buttons or chat commands, or log in to an X11 session")
    if not environ.get("DISPLAY"):
        return "global hotkeys need an X display, and there is none"
    return ""


class XServer:
    """The real X server, through python-xlib. Five calls, nothing else.

    Made only when start() has decided the keys can be on; the import is
    inside so the module loads where the library is not installed."""

    @staticmethod
    def available():
        try:
            import Xlib.display                       # noqa: F401
        except ImportError:
            return False
        return True

    def __init__(self):
        from Xlib import X, XK, display, error
        self._X, self._XK, self._error = X, XK, error
        self.display = display.Display()
        self.root = self.display.screen().root

    def keycode(self, keysym):
        """The keycode for a keysym name, or 0 for a key this keymap lacks."""
        code = self._XK.string_to_keysym(keysym)
        return int(self.display.keysym_to_keycode(code)) if code else 0

    def grab(self, keycode, mask):
        """A passive grab on the root window; False when another client
        already holds that key and modifiers (BadAccess)."""
        catcher = self._error.CatchError(self._error.BadAccess)
        self.root.grab_key(keycode, mask, False, self._X.GrabModeAsync,
                           self._X.GrabModeAsync, onerror=catcher)
        self.display.sync()
        return catcher.get_error() is None

    def ungrab(self, keycode, mask):
        self.root.ungrab_key(keycode, mask)
        self.display.sync()

    def presses(self):
        """Every key event waiting: (kind, keycode, state, time)."""
        out = []
        while self.display.pending_events():
            event = self.display.next_event()
            if event.type == self._X.KeyPress:
                out.append(("press", int(event.detail), int(event.state), int(event.time)))
            elif event.type == self._X.KeyRelease:
                out.append(("release", int(event.detail), int(event.state), int(event.time)))
        return out

    def close(self):
        self.display.close()


class X11Hotkeys:
    """The work keys on Linux: the same shape as the Windows Hotkeys, so the
    window cannot tell which it has.

    start(bindings) grabs every key it can and says, in `problem`, which it
    could not and why; `bound` is what took and `active` whether anything
    did. Presses are queued as action names and read with drain() from the
    Tk loop. stop() lets every key go and waits until it has.

    `server` is the X server to use: an object with keycode, grab, ungrab,
    presses and close, or None for the real one; `environ` is the desktop
    to judge (os.environ when None); `events` a queue to share."""

    def __init__(self, server=None, environ=None, events=None):
        self._given = server
        self._environ = environ
        self.events = events if events is not None else queue.Queue()
        self.active = False
        self.problem = ""
        self.bound = {}
        self._server = None
        self._grabs = []             # (keycode, mask) held right now
        self._actions = {}           # (keycode, relevant mask) -> action
        self._thread = None
        self._running = False

    def start(self, bindings):
        self.stop()
        self.bound, self.problem = {}, ""
        environ = os.environ if self._environ is None else self._environ
        self.problem = why_not(environ, have_xlib=True if self._given is not None else None)
        if self.problem:
            return
        try:
            server = self._given if self._given is not None else XServer()
        except Exception as exc:
            self.problem = "could not open the X display: %s" % exc
            return
        self._server = server
        trouble = []
        for action, key in dict(bindings).items():
            parsed = parse(key)
            code = server.keycode(parsed[1]) if parsed else 0
            if not parsed or not code:
                trouble.append("%s is not a key EDSMT can bind here" % key)
                continue
            mask = parsed[0]
            held = []
            for lock in LOCKS:
                if server.grab(code, mask | lock):
                    held.append((code, mask | lock))
                elif lock == 0:
                    break
            if not held or held[0][1] != mask:
                for code_, mask_ in held:
                    server.ungrab(code_, mask_)
                trouble.append("%s is already taken by another program - pick "
                               "another in Settings" % key)
                continue
            self._grabs.extend(held)
            self._actions[(code, mask)] = action
            self.bound[action] = key
        self.problem = "  /  ".join(trouble)
        if not self._actions:
            self._let_go()
            return
        self._running = True
        self.active = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _let_go(self):
        server, self._server = self._server, None
        if server is None:
            return
        for code, mask in self._grabs:
            try:
                server.ungrab(code, mask)
            except Exception:
                pass
        self._grabs, self._actions = [], {}
        try:
            server.close()
        except Exception:
            pass

    def stop(self):
        self._running = False
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive():
            thread.join(2.0)
        self._let_go()
        self.active = False

    def _run(self):
        # Auto-repeat is a release and a press with one timestamp; the
        # second press of such a pair is the key still held, not pressed.
        last_release = None
        try:
            while self._running:
                for kind, code, state, when in self._server.presses():
                    if kind == "release":
                        last_release = (code, when)
                        continue
                    if last_release == (code, when):
                        continue
                    action = self._actions.get((code, state & RELEVANT))
                    if action is not None:
                        self.events.put(action)
                time.sleep(POLL_S)
        except Exception as exc:
            self.problem = str(exc)
        finally:
            self.active = False

    def drain(self):
        out = []
        while True:
            try:
                out.append(self.events.get_nowait())
            except queue.Empty:
                return out
