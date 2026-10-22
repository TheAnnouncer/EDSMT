"""1.10036: the rig long-press comes from the commander's own game binds.

The rig button is Primary fire or Secondary fire, as bound
in Elite Dangerous for the SRV - read from the game's .binds file, mouse
button, key or joystick button alike - and nothing else. The files here are
made in the shape the game writes (checked against real 4.2 binds files on
21 Oct 2026: <BuggyPrimaryFireButton><Primary Device="Mouse"
Key="Mouse_1"/><Secondary Device="334444B0" Key="Joy_1"/>, modifiers as
<Modifier> children, StartPreset.4.start one preset per line).

    python tests/test_110036_binds.py
"""
import os, sys, json, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-binds-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["HOME"] = TMP

import gamebinds as GB    # noqa: E402
import inputdev as IND   # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond:
        fails.append(label)


def section(title):
    def wrap(fn):
        print("== " + title + " ==")
        try:
            fn()
        except Exception as exc:
            import traceback
            check(title + " (ran to the end)", False, "%s: %s" % (type(exc).__name__, exc))
            traceback.print_exc(limit=4)
        return fn
    return wrap


def binds(preset, primary_fire, secondary_fire, minor=2):
    def block(name, pair):
        (d1, k1, m1), (d2, k2, m2) = pair
        def one(tag, device, key, mods):
            if not mods:
                return '\t\t<%s Device="%s" Key="%s" />\n' % (tag, device, key)
            inner = "".join('\t\t\t<Modifier Device="Keyboard" Key="%s" />\n' % m for m in mods)
            return '\t\t<%s Device="%s" Key="%s">\n%s\t\t</%s>\n' % (tag, device, key, inner, tag)
        return "\t<%s>\n%s%s\t</%s>\n" % (name, one("Primary", d1, k1, m1), one("Secondary", d2, k2, m2), name)
    return ('<?xml version="1.0" encoding="UTF-8" ?>\n'
            '<Root PresetName="%s" MajorVersion="4" MinorVersion="%d">\n'
            '\t<KeyboardLayout>en-GB</KeyboardLayout>\n' % (preset, minor)
            + block("PrimaryFire", (("Joy", "Joy_9", []), ("{NoDevice}", "", [])))
            + block("BuggyPrimaryFireButton", primary_fire)
            + block("BuggySecondaryFireButton", secondary_fire)
            + "</Root>\n")


NONE = ("{NoDevice}", "", [])


def folder_with(files, start=None):
    path = tempfile.mkdtemp(dir=TMP)
    for name, text in files.items():
        with open(os.path.join(path, name), "w", encoding="utf-8") as out:
            out.write(text)
    if start is not None:
        with open(os.path.join(path, "StartPreset.4.start"), "w", encoding="utf-8") as out:
            out.write("\n".join(start))
    return path


@section("gamebinds: finding the commander's SRV binds")
def _find():
    check("the bindings folder is under LOCALAPPDATA",
          GB.bindings_folder().endswith(os.path.join("Frontier Developments", "Elite Dangerous",
                                                     "Options", "Bindings")), GB.bindings_folder())
    folder = folder_with({
        "HCS Custom.4.2.binds": binds("HCS Custom", (("Mouse", "Mouse_1", []), NONE), (("Mouse", "Mouse_2", []), NONE)),
        "Custom.4.2.binds": binds("Custom", (("Mouse", "Mouse_1", []), ("334444B0", "Joy_1", [])),
                                  (("Mouse", "Mouse_2", []), ("T16000M", "Joy_1", []))),
        "Custom.4.1.binds": binds("Custom", (("Keyboard", "Key_Z", []), NONE), (NONE, NONE), minor=1),
    }, start=["HCS Custom", "HCS Custom", "Custom", "HCS Custom"])
    check("StartPreset.4.start: one preset per line, in order",
          GB.active_presets(folder) == ["HCS Custom", "HCS Custom", "Custom", "HCS Custom"])
    check("the newest version of a preset's file", GB.binds_file(folder, "Custom").endswith("Custom.4.2.binds"))
    found = GB.fire_bindings(folder)
    check("the SRV line (the third) decides which file", found["preset"] == "Custom"
          and found["file"].endswith("Custom.4.2.binds"), found)
    check("primary fire: left mouse button and a joystick button",
          [(i["device"], i["key"]) for i in found["primary"]] == [("Mouse", "Mouse_1"), ("334444B0", "Joy_1")],
          found["primary"])
    check("secondary fire: right mouse button and the T16000M's button 1",
          [(i["device"], i["key"]) for i in found["secondary"]] == [("Mouse", "Mouse_2"), ("T16000M", "Joy_1")])
    check("the ship's PrimaryFire is not the SRV's", all(i["key"] != "Joy_9" for i in found["primary"]))
    old = folder_with({"KeyboardMouseOnly.3.0.binds": binds("KeyboardMouseOnly",
                                                             (("Mouse", "Mouse_1", []), NONE),
                                                             (("Mouse", "Mouse_2", []), NONE))})
    with open(os.path.join(old, "StartPreset.start"), "w", encoding="utf-8") as out:
        out.write("KeyboardMouseOnly")
    check("an older single-line StartPreset.start works too",
          GB.fire_bindings(old)["preset"] == "KeyboardMouseOnly")
    check("no folder: an answer that says so, never an error",
          GB.fire_bindings(os.path.join(TMP, "nowhere"))["why"])
    broken = folder_with({"Bad.4.2.binds": "<Root><BuggyPrimaryFireButton><Primary"}, start=["Bad"] * 4)
    check("a broken file: says so", "could not be read" in GB.fire_bindings(broken)["why"],
          GB.fire_bindings(broken))
    mods = folder_with({"M.4.2.binds": binds("M", (("Keyboard", "Key_K", ["Key_LeftAlt"]), NONE), (NONE, NONE))},
                       start=["M"] * 4)
    key = GB.fire_bindings(mods)["primary"][0]
    check("a key held with a modifier keeps the modifier", key["key"] == "Key_K"
          and key["modifiers"] == ["Key_LeftAlt"], key)


@section("gamebinds: saying it and watching it")
def _say():
    check("mouse buttons in words", GB.describe({"device": "Mouse", "key": "Mouse_1", "modifiers": []})
          == "left mouse button" and GB.describe({"device": "Mouse", "key": "Mouse_2", "modifiers": []})
          == "right mouse button" and GB.describe({"device": "Mouse", "key": "Mouse_4", "modifiers": []})
          == "mouse button 4")
    check("keys in words, modifiers first", GB.describe({"device": "Keyboard", "key": "Key_K",
                                                         "modifiers": ["Key_LeftAlt"]}) == "Left Alt + K")
    check("joystick buttons in words", GB.describe({"device": "334444B0", "key": "Joy_1", "modifiers": []})
          == "joystick 3344:44B0 button 1")
    check("virtual keys for the mouse", GB.vk_of("Mouse_1") == 0x01 and GB.vk_of("Mouse_2") == 0x02
          and GB.vk_of("Mouse_3") == 0x04 and GB.vk_of("Mouse_4") == 0x05 and GB.vk_of("Mouse_5") == 0x06)
    check("and for keys", GB.vk_of("Key_K") == ord("K") and GB.vk_of("Key_7") == ord("7")
          and GB.vk_of("Key_Space") == 0x20 and GB.vk_of("Key_LeftAlt") == 0xA4 and GB.vk_of("Key_F5") == 0x74)
    check("a device id is vendor and product", GB.device_ids("334444B0") == (0x3344, 0x44B0)
          and GB.device_ids("044FB10A") == (0x044F, 0xB10A))
    check("a named device the game knows", GB.device_ids("T16000M") == (0x044F, 0xB10A))
    check("an unknown name is None, not a guess", GB.device_ids("SomeStickNobodyMade") is None)
    check("a joystick button number", GB.joy_button("Joy_12") == 12 and GB.joy_button("Joy_POV1Up") is None)

    class Win:
        """user32 and winmm stand-ins: what is down, and which device is which."""
        def __init__(self):
            self.down = set()
            self.joy = {}          # device index -> mask
            self.caps = {0: (0x3344, 0x44B0), 1: (0x044F, 0xB10A)}

        def key_down(self, vk):
            return vk in self.down

        def joy_mask(self, index):
            return self.joy.get(index)

        def joy_ids(self, index):
            return self.caps.get(index)

    win = Win()
    reader = GB.BindReader(win)
    inputs = [{"device": "Mouse", "key": "Mouse_1", "modifiers": []},
              {"device": "334444B0", "key": "Joy_1", "modifiers": []},
              {"device": "Keyboard", "key": "Key_K", "modifiers": ["Key_LeftAlt"]}]
    check("nothing held, nothing down", reader.any_down(inputs) is False)
    win.down = {0x01}
    check("the left mouse button", reader.any_down(inputs))
    win.down = set()
    win.joy = {0: 0b1}
    check("button 1 on the stick with that vendor and product", reader.any_down(inputs))
    win.joy = {1: 0b1}
    check("not the same button on another stick", reader.any_down(inputs) is False)
    win.joy = {}
    win.down = {ord("K")}
    check("a key whose modifier is not held is not the binding", reader.any_down(inputs) is False)
    win.down = {ord("K"), 0xA4}
    check("with it, it is", reader.any_down(inputs))


@section("inputdev: a hold of any bound input")
def _hold():
    hold = IND.HoldWatcher()
    t = 100.0
    check("down at the start does not count until let go", hold.step(True, True, t) is None)
    hold.reset(False)
    for step in range(0, 25):
        hit = hold.step(True, True, t + step * 0.1)
        if hit:
            break
    check("held two seconds: one rig", hit is True and step >= 20, step)
    check("held longer: still one", hold.step(True, True, t + 3.0) is None)
    hold.step(False, True, t + 3.1)
    check("a click is nothing", hold.step(True, True, t + 3.2) is None and hold.step(False, True, t + 3.4) is None)
    hold.step(True, True, t + 4.0)
    check("the game not in front: nothing", hold.step(True, False, t + 6.5) is None)


@section("the setting: Primary or Secondary fire, older answers read across")
def _setting():
    import inputmix as IM
    check("primary and secondary as they are", IM.fire_choice({"long_press_button": "primary"}) == "primary"
          and IM.fire_choice({"long_press_button": "secondary"}) == "secondary")
    check("an older Left or Learn is Primary fire, Right is Secondary fire (the game's defaults)",
          IM.fire_choice({"long_press_button": "left"}) == "primary"
          and IM.fire_choice({"long_press_button": "learn"}) == "primary"
          and IM.fire_choice({"long_press_button": "right"}) == "secondary"
          and IM.fire_choice({}) == "primary")


if __name__ == "__main__":
    print("\n%d failure(s)" % len(fails) if fails else "\nall passed")
    sys.exit(1 if fails else 0)
