"""The commander's own SRV fire binds, read from the game (1.10036, #253).

The rig long-press watches Primary fire or Secondary fire exactly as the
commander bound them for the SRV in Elite Dangerous - a mouse button, a
key (with its modifiers) or a joystick button - and nothing else. The game
keeps its binds in %LOCALAPPDATA%\\Frontier Developments\\Elite
Dangerous\\Options\\Bindings:

  StartPreset.4.start   one preset name per line, a line per controls page
                        (general, ship, SRV, on foot); an older install has
                        a single-line StartPreset.start
  <Preset>.4.2.binds    XML, one element per control, e.g.
                        <BuggyPrimaryFireButton>
                          <Primary Device="Mouse" Key="Mouse_1" />
                          <Secondary Device="334444B0" Key="Joy_1" />
                        </BuggyPrimaryFireButton>
                        a key held with another carries <Modifier> children.

Checked against real binds files on 21 Oct 2026. Reading only: this
module never writes in that folder. The Windows calls go through an object
the checks replace (BindReader), so all of it is tested without Windows.
"""
import ctypes
import os
import re
import xml.etree.ElementTree as ET

FIRE = {"primary": "BuggyPrimaryFireButton", "secondary": "BuggySecondaryFireButton"}
NO_DEVICE = "{NoDevice}"
SRV_LINE = 2          # the third line of StartPreset.4.start: the SRV page

# Devices the game names rather than numbers, as (vendor, product). Only
# ones known for certain; any other name is said, never guessed at.
NAMED_DEVICES = {
    "t16000m": (0x044F, 0xB10A),
    "t16000mfcs": (0x044F, 0xB10A),
}

_MOUSE_VK = {1: 0x01, 2: 0x02, 3: 0x04, 4: 0x05, 5: 0x06}
_NAMED_VK = {
    "space": 0x20, "enter": 0x0D, "return": 0x0D, "tab": 0x09, "escape": 0x1B,
    "backspace": 0x08, "delete": 0x2E, "insert": 0x2D, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "uparrow": 0x26, "downarrow": 0x28,
    "leftarrow": 0x25, "rightarrow": 0x27, "leftshift": 0xA0, "rightshift": 0xA1,
    "leftcontrol": 0xA2, "rightcontrol": 0xA3, "leftalt": 0xA4, "rightalt": 0xA5,
    "capslock": 0x14, "minus": 0xBD, "equals": 0xBB, "leftbracket": 0xDB,
    "rightbracket": 0xDD, "semicolon": 0xBA, "apostrophe": 0xDE, "comma": 0xBC,
    "period": 0xBE, "slash": 0xBF, "backslash": 0xDC, "grave": 0xC0,
    "numpad_enter": 0x0D, "numpad_add": 0x6B, "numpad_subtract": 0x6D,
    "numpad_multiply": 0x6A, "numpad_divide": 0x6F, "numpad_decimal": 0x6E,
}
_WORDS = {"leftalt": "Left Alt", "rightalt": "Right Alt", "leftshift": "Left Shift",
          "rightshift": "Right Shift", "leftcontrol": "Left Ctrl",
          "rightcontrol": "Right Ctrl", "space": "Space"}
_VERSION = re.compile(r"^(?P<name>.+?)\.(?P<major>\d+)\.(?P<minor>\d+)\.binds$", re.I)


def bindings_folder(localappdata=None):
    base = localappdata or os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Frontier Developments", "Elite Dangerous",
                        "Options", "Bindings")


def active_presets(folder):
    """The preset named on each line of StartPreset.4.start, or the one in
    StartPreset.start, or []."""
    for name in ("StartPreset.4.start", "StartPreset.start"):
        try:
            with open(os.path.join(folder, name), "r", encoding="utf-8-sig") as handle:
                lines = [line.strip() for line in handle.read().splitlines()]
        except OSError:
            continue
        lines = [line for line in lines if line]
        if lines:
            return lines
    return []


def binds_file(folder, preset):
    """The newest <preset>.<major>.<minor>.binds, else <preset>.binds, or ""."""
    best = None
    try:
        names = os.listdir(folder)
    except OSError:
        return ""
    for name in names:
        found = _VERSION.match(name)
        if found and found.group("name").lower() == str(preset).lower():
            rank = (int(found.group("major")), int(found.group("minor")))
            if best is None or rank > best[0]:
                best = (rank, name)
    if best:
        return os.path.join(folder, best[1])
    plain = os.path.join(folder, "%s.binds" % preset)
    return plain if os.path.isfile(plain) else ""


def _inputs(element):
    out = []
    for tag in ("Primary", "Secondary"):
        child = element.find(tag)
        if child is None:
            continue
        device, key = child.get("Device") or "", child.get("Key") or ""
        if not key or device == NO_DEVICE:
            continue
        mods = [m.get("Key") or "" for m in child.findall("Modifier") if m.get("Key")]
        out.append({"device": device, "key": key, "modifiers": mods})
    return out


def read_fire(path):
    """{"primary": [input...], "secondary": [input...]} from one .binds file.
    Raises ValueError for a file that is not readable XML."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise ValueError(str(exc)) from None
    out = {}
    for which, tag in FIRE.items():
        element = root.find(tag)
        out[which] = _inputs(element) if element is not None else []
    return out


def fire_bindings(folder=None):
    """What Primary and Secondary fire are bound to for the SRV.

    {"file", "preset", "primary", "secondary", "why"} - `why` is "" when the
    binds were read, else a sentence saying why not. Never raises."""
    folder = folder or bindings_folder()
    answer = {"file": "", "preset": "", "primary": [], "secondary": [], "why": ""}
    presets = active_presets(folder)
    if not presets:
        answer["why"] = "The game's binds were not found on this PC."
        return answer
    order = [presets[SRV_LINE]] if len(presets) > SRV_LINE else []
    order += [p for p in presets if p not in order]
    for preset in order:
        path = binds_file(folder, preset)
        if not path:
            continue
        try:
            fire = read_fire(path)
        except ValueError as exc:
            answer.update(file=path, preset=preset,
                          why="The binds file %s could not be read (%s)."
                          % (os.path.basename(path), exc))
            return answer
        answer.update(file=path, preset=preset, why="", **fire)
        return answer
    answer["why"] = "No binds file for %s was found." % ", ".join(sorted(set(presets)))
    return answer


def device_ids(device):
    """(vendor, product) for a joystick the game wrote as eight hex digits
    or by a name it knows; None for a name that is not known."""
    text = str(device or "").strip()
    if re.fullmatch(r"[0-9A-Fa-f]{8}", text):
        return int(text[:4], 16), int(text[4:], 16)
    return NAMED_DEVICES.get(text.lower())


def joy_button(key):
    found = re.fullmatch(r"Joy_(\d{1,2})", str(key or ""))
    return int(found.group(1)) if found else None


def vk_of(key):
    """The Windows virtual-key code of a mouse button or a key, or None."""
    key = str(key or "")
    found = re.fullmatch(r"Mouse_(\d)", key)
    if found:
        return _MOUSE_VK.get(int(found.group(1)))
    if not key.startswith("Key_"):
        return None
    name = key[4:]
    if len(name) == 1 and name.isalnum():
        return ord(name.upper())
    found = re.fullmatch(r"F(\d{1,2})", name)
    if found and 1 <= int(found.group(1)) <= 24:
        return 0x6F + int(found.group(1))
    found = re.fullmatch(r"Numpad_(\d)", name)
    if found:
        return 0x60 + int(found.group(1))
    return _NAMED_VK.get(name.lower())


def describe(inp):
    """"left mouse button", "Left Alt + K", "joystick 3344:44B0 button 1"."""
    device, key = str(inp.get("device") or ""), str(inp.get("key") or "")
    if device == "Mouse":
        number = re.fullmatch(r"Mouse_(\d)", key)
        number = int(number.group(1)) if number else 0
        return {1: "left mouse button", 2: "right mouse button",
                3: "middle mouse button"}.get(number, "mouse button %d" % number)
    if device == "Keyboard":
        def word(k):
            bare = k[4:] if k.startswith("Key_") else k
            return _WORDS.get(bare.lower(), bare)
        return " + ".join([word(m) for m in inp.get("modifiers") or ()] + [word(key)])
    ids = device_ids(device)
    button = joy_button(key)
    stick = ("joystick %04X:%04X" % ids) if ids and re.fullmatch(r"[0-9A-Fa-f]{8}", device) \
        else "joystick %s" % device
    return "%s button %s" % (stick, button if button else key)


def words(bound):
    """Every input of one fire binding, in words, or "not bound"."""
    return ", ".join(describe(i) for i in bound) if bound else "not bound"


class WinInputs:
    """The real Windows calls: a key or mouse button down, a joystick's
    button mask and its vendor and product. Nothing off Windows."""

    def __init__(self):
        self.user32 = self.winmm = None
        if os.name == "nt":
            try:
                self.user32 = ctypes.WinDLL("user32")
                self.user32.GetAsyncKeyState.restype = ctypes.c_short
                self.winmm = ctypes.WinDLL("winmm")
            except (AttributeError, OSError):
                self.user32 = self.winmm = None
        self._reader = None

    def available(self):
        return self.user32 is not None

    def key_down(self, vk):
        if self.user32 is None:
            return False
        return bool(self.user32.GetAsyncKeyState(int(vk)) & 0x8000)

    def joy_mask(self, index):
        if self.winmm is None:
            return None
        if self._reader is None:
            import inputdev as IND
            self._reader = IND.WinmmReader(self.winmm)
        return self._reader(index)

    def joy_ids(self, index):
        if self.winmm is None:
            return None
        caps = JOYCAPSW()
        try:
            if self.winmm.joyGetDevCapsW(int(index), ctypes.byref(caps),
                                         ctypes.sizeof(JOYCAPSW)) != 0:
                return None
        except (AttributeError, OSError, TypeError, ValueError):
            return None
        return int(caps.wMid), int(caps.wPid)


class JOYCAPSW(ctypes.Structure):
    _fields_ = ([("wMid", ctypes.c_ushort), ("wPid", ctypes.c_ushort),
                 ("szPname", ctypes.c_wchar * 32)]
                + [(name, ctypes.c_uint) for name in (
                    "wXmin", "wXmax", "wYmin", "wYmax", "wZmin", "wZmax",
                    "wNumButtons", "wPeriodMin", "wPeriodMax", "wRmin", "wRmax",
                    "wUmin", "wUmax", "wVmin", "wVmax", "wCaps", "wMaxAxes",
                    "wNumAxes", "wMaxButtons")]
                + [("szRegKey", ctypes.c_wchar * 32), ("szOEMVxD", ctypes.c_wchar * 260)])


class BindReader:
    """Whether any input of a binding is held right now. `win` answers
    key_down(vk), joy_mask(index) and joy_ids(index)."""

    JOY_DEVICES = 16

    def __init__(self, win=None):
        self.win = win if win is not None else WinInputs()
        self._ids = None

    def available(self):
        check = getattr(self.win, "available", None)
        return bool(check()) if callable(check) else True

    def forget(self):
        """Look for the joysticks again (one was plugged in or out)."""
        self._ids = None

    def _devices(self):
        if self._ids is None:
            self._ids = {}
            for index in range(self.JOY_DEVICES):
                ids = self.win.joy_ids(index)
                if ids:
                    self._ids.setdefault(tuple(ids), []).append(index)
        return self._ids

    def down(self, inp):
        device, key = str(inp.get("device") or ""), str(inp.get("key") or "")
        if device in ("Mouse", "Keyboard"):
            vk = vk_of(key)
            if vk is None or not self.win.key_down(vk):
                return False
            for mod in inp.get("modifiers") or ():
                mvk = vk_of(mod)
                if mvk is None or not self.win.key_down(mvk):
                    return False
            return True
        ids, button = device_ids(device), joy_button(key)
        if not ids or not button:
            return False
        for index in self._devices().get(tuple(ids), ()):
            mask = self.win.joy_mask(index)
            if mask is not None and (int(mask) >> (button - 1)) & 1:
                return True
        return False

    def any_down(self, inputs):
        return any(self.down(inp) for inp in inputs or ())
