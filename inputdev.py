"""Joystick and HOTAS buttons, and a long press of the mouse (1.10035).

Two ways to do something in the Rhino without reaching for the keyboard.

Joystick buttons (#198). Any hotkey action can also be bound to a button on
any joystick, throttle or HOTAS Windows can see - up to 16 devices of 32
buttons. They are read through the multimedia joystick API (winmm), which
ships with Windows, so there is nothing to install. A button is stored the
way it is written on screen: "JOY1 B7" is button 7 on device 1.

A long press of the mouse. While you are in the Rhino with the game in front,
a mouse button held for two seconds counts as a rig placed. A click on the
scanner (under half a second) never does, and a press in between is neither.
Nothing about a press is written down: the watcher holds a start time in
memory for as long as the button is down, and nothing else.

Both are polled, never hooked: no driver, no message hook, nothing that sees
a key. Off Windows both are quietly unavailable. Every call into Windows goes
through an object that can be replaced, so all of it is tested without it.
"""
import ctypes
import os
import re

# ---------------------------------------------------------------------------
# Joystick buttons
# ---------------------------------------------------------------------------

MAX_DEVICES = 16          # joyGetNumDevs on Windows
MAX_BUTTONS = 32          # one bit each in dwButtons
POLL_MS = 50              # how often either is looked at, while it is wanted
JOY_CAPTURE_S = 10        # how long Settings waits for a button to be pressed

# Every action a hotkey can run. Each has a key of its own in settings,
# "joy_" + the action, blank until a button is bound to it. The names are the
# ones the keys use ("hotkey_" + the action); a test holds the two lists to
# each other so a key added later cannot be left without a button.
RIGS = 6
JOY_ACTIONS = (("location", "border", "deposit")
               + tuple("rig%d" % n for n in range(1, RIGS + 1))
               + ("update", "trace")
               + tuple("rig%dup" % n for n in range(1, RIGS + 1))
               + ("allup", "rigs", "centre", "lock", "overlay", "zoom")
               + ("wp_next", "wp_back", "wp_skip", "wp_pause"))


def joy_key(action):
    """The setting that holds the button for an action."""
    return "joy_" + str(action)


def joy_setting(hotkey_name):
    """The joystick setting that goes with a hotkey setting, or "".

    "hotkey_rig3" -> "joy_rig3". A name that is not a hotkey for one of the
    actions above (hotkey_defaults, for one) has no joystick button."""
    name = str(hotkey_name or "")
    if not name.startswith("hotkey_"):
        return ""
    action = name[len("hotkey_"):]
    return joy_key(action) if action in JOY_ACTIONS else ""


_JOY = re.compile(r"^\s*joy\s*(\d{1,2})[\s_-]*b\s*(\d{1,2})\s*$", re.IGNORECASE)


def parse_joy(text):
    """(device, button), both counted from 1, or None.

    "JOY1 B7", "joy1 b7" and "Joy1_B7" are the same button. Device 0, device
    17, button 0 and button 33 are not buttons anybody has."""
    found = _JOY.match(str(text or ""))
    if not found:
        return None
    device, button = int(found.group(1)), int(found.group(2))
    if not 1 <= device <= MAX_DEVICES or not 1 <= button <= MAX_BUTTONS:
        return None
    return device, button


def joy_text(device, button):
    """(1, 7) as it is stored and shown: JOY1 B7."""
    return "JOY%d B%d" % (int(device), int(button))


def clean_joy(text):
    """A stored button in its one spelling, or "" for anything else."""
    parsed = parse_joy(text)
    return joy_text(*parsed) if parsed else ""


class JOYINFOEX(ctypes.Structure):
    """winmm's JOYINFOEX: thirteen DWORDs, 52 bytes."""
    _fields_ = [(name, ctypes.c_uint32) for name in (
        "dwSize", "dwFlags", "dwXpos", "dwYpos", "dwZpos", "dwRpos", "dwUpos",
        "dwVpos", "dwButtons", "dwButtonNumber", "dwPOV", "dwReserved1",
        "dwReserved2")]


JOY_RETURNBUTTONS = 0x80
JOYERR_NOERROR = 0


class WinmmReader:
    """The buttons held on one device, from winmm. None when nothing is there.

    `winmm` is the library to ask; the real one on Windows, nothing
    anywhere else, and a stand-in in the checks."""

    def __init__(self, winmm=None):
        if winmm is None and os.name == "nt":
            winmm = ctypes.WinDLL("winmm")
        self.winmm = winmm

    def devices(self):
        """How many device numbers Windows will answer for."""
        try:
            return max(0, min(MAX_DEVICES, int(self.winmm.joyGetNumDevs())))
        except (AttributeError, OSError, TypeError, ValueError):
            return 0

    def __call__(self, device):
        """The bit mask of buttons down on device number `device` (from 0)."""
        info = JOYINFOEX()
        info.dwSize = ctypes.sizeof(JOYINFOEX)
        info.dwFlags = JOY_RETURNBUTTONS
        try:
            if self.winmm.joyGetPosEx(int(device), ctypes.byref(info)) \
                    != JOYERR_NOERROR:
                return None
        except (AttributeError, OSError, TypeError, ValueError):
            return None
        return int(info.dwButtons)


def default_reader():
    """The reader for this machine, or None where there is no winmm."""
    if os.name != "nt":
        return None
    try:
        return WinmmReader()
    except (AttributeError, OSError):
        return None


class JoystickWatcher:
    """Which buttons were pressed since the last look.

    A press is the moment a button goes down, not the time it stays down: a
    button held is one press, and a HOTAS button the thumb rests on does
    nothing more. What was already down when the watcher first saw a device
    - or first saw it again after it was unplugged - is not a press either.

    `reader(device_from_0)` returns the mask of buttons down, or None for a
    device that is not there; it may also have `devices()`, how many numbers
    to ask. A device that is not there is asked again every RESCAN looks, not
    every look, so sixteen empty slots cost almost nothing."""

    RESCAN = 20

    def __init__(self, reader=None):
        self.reader = reader if reader is not None else default_reader()
        self.muted = False       # Settings is listening for a press
        self._last = {}          # device (from 1) -> the mask last seen
        self._asked = 0
        self._retry = {}         # device number (from 0) -> look number to ask again

    def available(self):
        return self.reader is not None

    def _count(self):
        counter = getattr(self.reader, "devices", None)
        if callable(counter):
            try:
                return max(0, min(MAX_DEVICES, int(counter())))
            except (TypeError, ValueError):
                return MAX_DEVICES
        return MAX_DEVICES

    def read(self):
        """{device (from 1): mask} for every device that answered."""
        out = {}
        if self.reader is None:
            return out
        self._asked += 1
        for number in range(self._count()):
            if self._retry.get(number, 0) > self._asked:
                continue
            mask = self.reader(number)
            if mask is None:
                self._retry[number] = self._asked + self.RESCAN
                continue
            self._retry.pop(number, None)
            out[number + 1] = int(mask) & 0xFFFFFFFF
        return out

    def forget(self):
        """Start again: whatever is held now is the baseline, not a press."""
        self._last = {}

    def rebase(self):
        """Take the baseline now; how many devices answered."""
        self._last = self.read()
        return len(self._last)

    def new_presses(self):
        """[(device, button)] for buttons that went down since the last look."""
        now = self.read()
        out = []
        for device, mask in sorted(now.items()):
            before = self._last.get(device)
            if before is None:
                continue
            fresh = mask & ~before
            for bit in range(MAX_BUTTONS):
                if fresh >> bit & 1:
                    out.append((device, bit + 1))
        self._last = now
        return out

    def poll(self, bindings):
        """The actions whose buttons were pressed. `bindings` maps
        (device, button) to an action. Nothing while Settings is listening."""
        presses = self.new_presses()
        if self.muted:
            return []
        return [bindings[p] for p in presses if p in bindings]


# ---------------------------------------------------------------------------
# A long press of the mouse
# ---------------------------------------------------------------------------

LONG_PRESS_S = 2.0        # held this long, a rig has gone down
CLICK_MAX_S = 0.5         # shorter than this is a click on the scanner
MAX_GAP_S = 0.5           # a look this much later than the last is not trusted
# The game's window is found by what it is, never by what it is called: a
# title is whatever a window says it is (a browser tab, a folder, a document
# can carry the game's name), the window class and the program are not.
GAME_WINDOW_CLASS = "FrontierDevelopmentsAppWinClass"
GAME_PROGRAMS = ("elitedangerous64.exe", "elitedangerous32.exe")
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
VK_LBUTTON, VK_RBUTTON = 0x01, 0x02
BUTTONS = ("left", "right")


def press_kind(seconds):
    """What a press of this length is: "click", "between" or "rig"."""
    seconds = float(seconds)
    if seconds >= LONG_PRESS_S:
        return "rig"
    if seconds < CLICK_MAX_S:
        return "click"
    return "between"


class LongPress:
    """Times the mouse buttons, and says when one has been held long enough.

    `mode` is "left", "right", or "learn": in learn mode, until a button is
    known, the first of the two held for LONG_PRESS_S is taken as the rig
    button (and counts as the rig placed). `step` is called every POLL_MS
    with what the buttons are doing; it returns None, or (button, learned)
    once for each press that reaches LONG_PRESS_S - held longer, it does not
    fire again.

    A press that began while it did not count - the game not in front, not in
    the Rhino - does not count when the game comes back to the front with the
    button still down, and neither does a press that straddles a stall (the
    look before was more than MAX_GAP_S ago, so it may have been a different
    press). Only the moment a button went down is kept, in memory."""

    def __init__(self, mode="left", learned=""):
        self.mode = mode
        self.learned = learned if learned in BUTTONS else ""
        self._since = {b: None for b in BUTTONS}
        self._fired = {b: False for b in BUTTONS}
        self._ignore = {b: False for b in BUTTONS}
        self._at = None

    def watching(self):
        """The buttons that count as the rig button right now."""
        if self.mode in BUTTONS:
            return [self.mode]
        if self.learned in BUTTONS:
            return [self.learned]
        return list(BUTTONS)

    def reset(self, left=False, right=False):
        """Forget every press in progress; a button down now is ignored
        until it is let go."""
        down = {"left": bool(left), "right": bool(right)}
        for button in BUTTONS:
            self._since[button] = None
            self._fired[button] = False
            self._ignore[button] = down[button]
        self._at = None

    def step(self, left, right, active, now):
        down = {"left": bool(left), "right": bool(right)}
        stalled = self._at is not None and now - self._at > MAX_GAP_S
        self._at = now
        if not active or stalled:
            for button in BUTTONS:
                self._since[button] = None
                self._fired[button] = False
                self._ignore[button] = down[button]
            return None
        result = None
        for button in BUTTONS:
            if not down[button]:
                self._since[button] = None
                self._fired[button] = False
                self._ignore[button] = False
                continue
            if self._ignore[button]:
                continue
            if self._since[button] is None:
                self._since[button] = now
                continue
            if button in self.watching() and not self._fired[button] \
                    and press_kind(now - self._since[button]) == "rig":
                self._fired[button] = True
                learned = self.mode == "learn" and not self.learned
                if learned:
                    self.learned = button
                result = (button, learned)
        return result


class HoldWatcher:
    """One binding held for LONG_PRESS_S, from any of its inputs (1.10036).

    The same rules as LongPress, for whatever the game's own Primary or
    Secondary fire is bound to - a mouse button, a key or a joystick button
    (gamebinds.py reads which). `step(down, active, now)` is True once for
    each hold that reaches LONG_PRESS_S, and None otherwise."""

    def __init__(self):
        self.reset()

    def reset(self, down=False):
        self._since = None
        self._fired = False
        self._ignore = bool(down)
        self._at = None

    def step(self, down, active, now):
        stalled = self._at is not None and now - self._at > MAX_GAP_S
        self._at = now
        if not active or stalled:
            self._since, self._fired, self._ignore = None, False, bool(down)
            return None
        if not down:
            self._since, self._fired, self._ignore = None, False, False
            return None
        if self._ignore:
            return None
        if self._since is None:
            self._since = now
            return None
        if not self._fired and press_kind(now - self._since) == "rig":
            self._fired = True
            return True
        return None


class WinMouse:
    """The two mouse buttons, and whether Elite Dangerous is in front.

    `user32` and `kernel32` are the libraries to ask; the real ones on
    Windows, nothing anywhere else, and stand-ins in the checks.
    GetAsyncKeyState says whether a button is down right now - it does not
    say what was pressed before, and nothing here asks it to. The window in
    front is the game's when its class is the game's, or when the program
    behind it is the game's; its title is never looked at."""

    def __init__(self, user32=None, kernel32=None):
        if os.name == "nt":
            # Our own handles on the libraries: the types set below are ours
            # and do not change what any other module sees of them.
            if user32 is None:
                user32 = ctypes.WinDLL("user32")
            if kernel32 is None:
                kernel32 = ctypes.WinDLL("kernel32")
        self.user32 = user32
        self.kernel32 = kernel32
        self._types()

    def _types(self):
        """The argument and result types that 64-bit Windows needs set."""
        try:
            if self.user32 is not None:
                self.user32.GetAsyncKeyState.restype = ctypes.c_short
                self.user32.GetForegroundWindow.restype = ctypes.c_void_p
                self.user32.GetClassNameW.argtypes = [
                    ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
                self.user32.GetWindowThreadProcessId.argtypes = [
                    ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
            if self.kernel32 is not None:
                self.kernel32.OpenProcess.restype = ctypes.c_void_p
                self.kernel32.OpenProcess.argtypes = [
                    ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
                self.kernel32.QueryFullProcessImageNameW.argtypes = [
                    ctypes.c_void_p, ctypes.c_uint32, ctypes.c_wchar_p,
                    ctypes.POINTER(ctypes.c_uint32)]
                self.kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        except AttributeError:
            pass

    def available(self):
        return self.user32 is not None

    def buttons(self):
        """(left, right): whether each is down at this moment."""
        if self.user32 is None:
            return False, False
        return (bool(self.user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000),
                bool(self.user32.GetAsyncKeyState(VK_RBUTTON) & 0x8000))

    def _program_of(self, window):
        """The file name of the program that owns a window, lower case, or ""."""
        if self.kernel32 is None:
            return ""
        pid = ctypes.c_uint32(0)
        self.user32.GetWindowThreadProcessId(window, ctypes.byref(pid))
        if not pid.value:
            return ""
        handle = self.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, 0, pid.value)
        if not handle:
            return ""
        try:
            path = ctypes.create_unicode_buffer(520)
            size = ctypes.c_uint32(520)
            if not self.kernel32.QueryFullProcessImageNameW(
                    handle, 0, path, ctypes.byref(size)):
                return ""
            return path.value.replace("/", "\\").rsplit("\\", 1)[-1].lower()
        finally:
            self.kernel32.CloseHandle(handle)

    def elite_in_front(self):
        """Whether the window in front is the game's."""
        if self.user32 is None:
            return False
        window = self.user32.GetForegroundWindow()
        if not window:
            return False
        name = ctypes.create_unicode_buffer(256)
        self.user32.GetClassNameW(window, name, 256)
        if name.value == GAME_WINDOW_CLASS:
            return True
        return self._program_of(window) in GAME_PROGRAMS
