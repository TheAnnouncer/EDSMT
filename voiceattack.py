"""
A VoiceAttack profile for EDSMT (1.10040, #152).

"Mark signal", "rig three down", "lock overlay": each spoken command
presses the key the commander has bound to that job in Settings > Keys, so
the profile is always the commander's own keys - made again, it follows
any key changed since.

VoiceAttack exports a profile as a .vap file, either compressed or as
expanded XML; this writes the expanded XML, the one VoiceAttack says can
be read in a text editor. What is and is not confirmed about that format
is in docs/VOICEATTACK.md.

Plain logic: no window, no VoiceAttack needed to make the file.
"""

import os
import uuid
from xml.sax.saxutils import escape

PROFILE_NAME = "Radio Raxxla EDSMT"
FILE_NAME = "Radio Raxxla EDSMT.vap"

_RIG_WORDS = ("one", "two", "three", "four", "five", "six")

# What is said, and the EDSMT key it presses.
COMMANDS = ((("mark signal", "hotkey_location"),
             ("set border", "hotkey_border"),
             ("mark deposit", "hotkey_deposit"))
            + tuple(("rig %s down" % word, "hotkey_rig%d" % n)
                    for n, word in enumerate(_RIG_WORDS, 1))
            + (("rigs up", "hotkey_allup"),
               ("update deposit", "hotkey_update"),
               ("next waypoint", "hotkey_wp_next"),
               ("overlay", "hotkey_overlay"),
               ("lock overlay", "hotkey_lock")))

# Where VoiceAttack keeps its Sounds folder unless it is moved in VoiceAttack's
# Options: "Sounds" under VoiceAttack's own folder (VoiceAttack's guide,
# {VA_SOUNDS}). Its guide has a sound pack as a folder inside it - which is
# how Celestia's voice-pack reminders know to switch on by themselves.
VA_FOLDERS = ("VoiceAttack", "VoiceAttack 2")


def steam_libraries(vdf_text):
    """Every library path in Steam's libraryfolders.vdf, in the order there."""
    out = []
    for line in str(vdf_text or "").splitlines():
        parts = line.strip().split('"')
        if len(parts) >= 4 and parts[1].lower() == "path":
            out.append(parts[3].replace("\\\\", "\\"))
    return out


def sounds_folders(env, libraries=()):
    """Where VoiceAttack's Sounds folder is by default: under VoiceAttack in
    Program Files, or in a Steam library."""
    bases = [env.get(name) for name in ("ProgramFiles(x86)", "ProgramFiles", "ProgramW6432")]
    places = []
    for base in [b for b in bases if b]:
        places += ["%s\\%s\\Sounds" % (base.rstrip("\\/"), name) for name in VA_FOLDERS]
    for library in libraries or ():
        places += ["%s\\steamapps\\common\\%s\\Sounds" % (str(library).rstrip("\\/"), name)
                   for name in VA_FOLDERS]
    seen = []
    for place in places:
        if place.lower() not in [p.lower() for p in seen]:
            seen.append(place)
    return seen


def has_sound_packs(folders):
    """True when any of these Sounds folders holds a folder: a sound pack.
    Never raises - a folder that cannot be read is no pack."""
    for folder in folders or ():
        try:
            if any(os.path.isdir(os.path.join(folder, name)) for name in os.listdir(folder)):
                return True
        except OSError:
            continue
    return False


def find_sound_packs(env=None, read=None):
    """Whether VoiceAttack has a sound pack on this computer, from its usual
    places and Steam's libraries. False away from Windows or on any fault."""
    env = os.environ if env is None else env
    libraries = []
    steam = env.get("ProgramFiles(x86)")
    if steam:
        vdf = os.path.join(steam, "Steam", "steamapps", "libraryfolders.vdf")
        try:
            with (read or open)(vdf, encoding="utf-8", errors="replace") as handle:
                libraries = steam_libraries(handle.read())
        except (OSError, TypeError):
            libraries = [os.path.join(steam, "Steam")]
    return has_sound_packs(sounds_folders(env, libraries))


# A binding's modifiers, as Windows' RegisterHotKey numbers them (the bits
# EDSMT's own keys are registered with), and the left-hand key pressed for
# each: Windows virtual-key codes. Ctrl+Alt - AltGr - is both.
MOD_KEYS = ((0x0002, 0xA2, "Left Ctrl"),
            (0x0001, 0xA4, "Left Alt"),
            (0x0004, 0xA0, "Left Shift"),
            (0x0008, 0x5B, "Left Win"))
# How long each key is held, in seconds.
HOLD_S = 0.1


def key_codes(parsed):
    """(modifier bits, virtual key) - what EDSMT's parse_binding gives - as
    the keys pressed together, modifiers first; None for no key."""
    if not parsed:
        return None
    try:
        bits, code = int(parsed[0]), int(parsed[1])
    except (TypeError, ValueError, IndexError):
        return None
    if not 0 < code < 256:
        return None
    return [vk for bit, vk, _name in MOD_KEYS if bits & bit] + [code]


def key_caption(binding, parsed):
    """"Left Alt+1": what VoiceAttack shows the action as."""
    if not parsed:
        return ""
    bits = int(parsed[0])
    key = str(binding or "").split("+")[-1].strip() or "?"
    return "+".join([name for bit, _vk, name in MOD_KEYS if bits & bit] + [key])


def profile_commands(settings, parse, defaults=None):
    """([(phrase, binding, key codes, caption)], [phrase with no key]): the
    commands with a key bound in `settings` (else `defaults`), and the ones
    left out because the job has no key. `parse` reads a binding."""
    settings = settings or {}
    defaults = defaults or {}
    made, missing = [], []
    for phrase, name in COMMANDS:
        binding = str(settings.get(name, defaults.get(name, "")) or "").strip()
        parsed = parse(binding) if binding else None
        codes = key_codes(parsed)
        if not codes:
            missing.append(phrase)
            continue
        made.append((phrase, binding, codes, key_caption(binding, parsed)))
    return made, missing


def _guid(new_id):
    return str(new_id())


def profile_xml(commands, name=PROFILE_NAME, new_id=uuid.uuid4):
    """The profile as expanded XML: one command a phrase, each one action
    that presses its keys together for HOLD_S and lets go."""
    profile_id = _guid(new_id)
    out = ['<?xml version="1.0" encoding="utf-8"?>',
           '<Profile xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
           'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">',
           "  <HasMB>false</HasMB>",
           "  <Id>%s</Id>" % profile_id,
           "  <Name>%s</Name>" % escape(name),
           "  <Commands>"]
    for phrase, _binding, codes, caption in commands:
        command_id, action_id = _guid(new_id), _guid(new_id)
        said = "Press %s keys and hold for %s seconds and release" % (caption, HOLD_S)
        out += ["    <Command>",
                "      <Referrer xsi:nil=\"true\" />",
                "      <ExecType>3</ExecType>",
                "      <Confidence>0</Confidence>",
                "      <PrefixActionCount>0</PrefixActionCount>",
                "      <IsDynamicallyCreated>false</IsDynamicallyCreated>",
                "      <TargetProcessSet>false</TargetProcessSet>",
                "      <TargetProcessType>0</TargetProcessType>",
                "      <TargetProcessLevel>0</TargetProcessLevel>",
                "      <CompareType>0</CompareType>",
                "      <ExecFromWildcard>false</ExecFromWildcard>",
                "      <IsSubCommand>false</IsSubCommand>",
                "      <IsOverride>false</IsOverride>",
                "      <BaseId>%s</BaseId>" % command_id,
                "      <OriginId>00000000-0000-0000-0000-000000000000</OriginId>",
                "      <SessionEnabled>true</SessionEnabled>",
                "      <Id>%s</Id>" % command_id,
                "      <CommandString>%s</CommandString>" % escape(phrase),
                "      <ActionSequence>",
                "        <CommandAction>",
                "          <PairingSet>false</PairingSet>",
                "          <PairingSetElse>false</PairingSetElse>",
                "          <Ordinal>0</Ordinal>",
                "          <ConditionMet xsi:nil=\"true\" />",
                "          <IndentLevel>0</IndentLevel>",
                "          <ConditionSkip>false</ConditionSkip>",
                "          <IsSuffixAction>false</IsSuffixAction>",
                "          <DecimalTransient1>0</DecimalTransient1>",
                "          <Caption>%s</Caption>" % escape(said),
                "          <Id>%s</Id>" % action_id,
                "          <ActionType>PressKey</ActionType>",
                "          <Duration>%s</Duration>" % HOLD_S,
                "          <Delay>0</Delay>",
                "          <KeyCodes>"]
        out += ["            <unsignedShort>%d</unsignedShort>" % code for code in codes]
        out += ["          </KeyCodes>",
                "          <Context />",
                "          <X>0</X>",
                "          <Y>0</Y>",
                "          <Z>0</Z>",
                "          <InputMode>0</InputMode>",
                "          <ConditionPairing>0</ConditionPairing>",
                "          <ConditionGroup>0</ConditionGroup>",
                "          <ConditionStartOperator>0</ConditionStartOperator>",
                "          <ConditionStartValue>0</ConditionStartValue>",
                "          <ConditionStartValueType>0</ConditionStartValueType>",
                "          <ConditionStartType>0</ConditionStartType>",
                "          <DecimalContext1>0</DecimalContext1>",
                "          <DecimalContext2>0</DecimalContext2>",
                "          <Disabled>false</Disabled>",
                "        </CommandAction>",
                "      </ActionSequence>",
                "      <Async>true</Async>",
                "      <Enabled>true</Enabled>",
                "      <Category>%s</Category>" % escape(name),
                "      <UseShortcut>false</UseShortcut>",
                "      <UseSpokenPhrase>true</UseSpokenPhrase>",
                "      <UseJoystick>false</UseJoystick>",
                "      <UseMouse>false</UseMouse>",
                "      <SourceProfile>%s</SourceProfile>" % profile_id,
                # The command lock: 0 leaves the command open to be edited.
                "      <CL>0</CL>",
                "    </Command>"]
    out += ["  </Commands>",
            # The profile's own locks, right above its closing tag: 0 leaves
            # it open to new commands and to being exported as XML again.
            "  <CR>0</CR>",
            "  <BE>0</BE>",
            "</Profile>", ""]
    return "\n".join(out)


def write_profile(folder, settings, parse, defaults=None, new_id=uuid.uuid4):
    """Write the profile into `folder`. (path, commands made, phrases left
    out for want of a key). Raises OSError when it cannot be written."""
    made, missing = profile_commands(settings, parse, defaults)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, FILE_NAME)
    text = profile_xml(made, new_id=new_id)
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(text)
    os.replace(temp, path)
    return path, made, missing
