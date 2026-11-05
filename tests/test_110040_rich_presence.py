"""1.10040 (#312): Discord Rich Presence.

"Playing EDSMT - Mining Platinum" on the commander's Discord profile, from
the Rhino session, over the Discord desktop app's own local socket. Off
until switched on; the application id comes from the community map's
/v1/health, never from the code; at most one update every 15 seconds and
never the same one twice; streamer mode keeps the body and system off it.

    python tests/test_110040_rich_presence.py
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import richpresence as RP  # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


print("== the wire, as Discord documents it ==")
raw = RP.frame(0, {"v": 1, "client_id": "123456789012345678"})
body = json.dumps({"v": 1, "client_id": "123456789012345678"}, separators=(",", ":")).encode()
check("a frame: opcode and length, 32-bit little-endian, then the JSON",
      raw[:8] == struct.pack("<II", 0, len(body)) and raw[8:] == body, raw[:16])
chunks = [raw[:3], raw[3:10], raw[10:]]


def reader(parts):
    data = b"".join(parts)
    pos = [0]

    def read(n):
        out = data[pos[0]:pos[0] + n]
        pos[0] += n
        return out
    return read


check("and read back whatever size the pieces arrive in",
      RP.read_frame(reader(chunks)) == (0, {"v": 1, "client_id": "123456789012345678"}))
_raises = True
try:
    RP.read_frame(reader([raw[:5]]))
    _raises = False
except OSError:
    pass
check("(a frame cut short raises OSError)", _raises)
check("Windows: the named pipes discord-ipc-0 to 9",
      RP.ipc_paths("win32", {}) == [r"\\?\pipe\discord-ipc-%d" % n for n in range(10)])
check("Linux: XDG_RUNTIME_DIR first, then TMPDIR, TMP, TEMP and /tmp",
      RP.ipc_paths("linux", {"XDG_RUNTIME_DIR": "/run/user/1000", "TMP": "/t"})[:2]
      == ["/run/user/1000/discord-ipc-0", "/run/user/1000/discord-ipc-1"]
      and "/t/discord-ipc-0" in RP.ipc_paths("linux", {"XDG_RUNTIME_DIR": "/run/user/1000", "TMP": "/t"})
      and RP.ipc_paths("linux", {})[0] == "/tmp/discord-ipc-0")

print("== what it says ==")
STATE = {"cmdr": "Jameson", "system": "Ega", "body": "Ega 1", "mining": ["Platinum", "Osmium"],
         "session": {"running": True, "paused": False, "seconds": 600},
         "cr_hr": 4200000, "cr_hr_text": "4,200,000", "rigs_down": 3}
act = RP.activity(STATE, now=1_800_000_000)
check("Playing, with what is being mined", act["type"] == 0 and act["details"] == "Mining Platinum, Osmium", act)
check("and where, the Cr/hr and the rigs", act["state"] == "Ega 1 · 4,200,000 Cr/hr · 3 rigs down", act["state"])
check("timed from the session's start, in seconds", act["timestamps"]["start"] == 1_800_000_000 - 600)
check("the EDSMT picture", act["assets"]["large_image"] == "edsmt")
check("two buttons at most, labels inside Discord's 32",
      len(act["buttons"]) == 2 and all(1 <= len(b["label"]) <= 32 and b["url"].startswith("https://")
                                       for b in act["buttons"])
      and [b["label"] for b in act["buttons"]] == ["Get EDSMT", "Join Radio Raxxla"], act["buttons"])
hidden = RP.activity(dict(STATE, body="a body", system="a system 60 Ly from Sol"), now=1_800_000_000,
                     hidden=True)
check("streamer mode: no body, no system", "Ega" not in json.dumps(hidden) and "a body" not in hidden["state"],
      hidden["state"])
idle = RP.activity({"session": {"running": False}, "mining": [], "body": "Ega 1"}, now=1_800_000_000)
check("no session: on the surface, no clock", idle["details"] == "On the surface" and "timestamps" not in idle,
      idle)
long = RP.activity(dict(STATE, mining=["Low Temperature Diamonds"] * 20), now=1_800_000_000)
check("never longer than Discord takes (128)", len(long["details"]) <= 128 and len(long["state"]) <= 128)

print("== how often, and when Discord is not there ==")


class Fake:
    def __init__(self, fail=False):
        self.sent, self.opened, self.closed, self.fail = [], [], 0, fail

    def connect(self, client_id):
        if self.fail:
            raise OSError("no Discord")
        self.opened.append(client_id)

    def send(self, payload):
        self.sent.append(payload)

    def close(self):
        self.closed += 1


fake = Fake()
p = RP.Presence(lambda: fake, pid=4242)
p.tick(0.0)
check("no application id: never connects", not fake.opened)
p.client_id = "123456789012345678"
p.update(act, 100.0)
p.tick(100.0)
check("first update: the handshake with the application id, then SET_ACTIVITY with this process",
      fake.opened == ["123456789012345678"] and len(fake.sent) == 1
      and fake.sent[0]["cmd"] == "SET_ACTIVITY" and fake.sent[0]["args"]["pid"] == 4242
      and fake.sent[0]["args"]["activity"] == act and fake.sent[0].get("nonce"), fake.sent)
newer = dict(act, state="later")
p.update(newer, 105.0)
p.tick(105.0)
check("another within 15 s waits", len(fake.sent) == 1)
p.update(dict(act, state="latest"), 110.0)
p.tick(116.0)
check("then the newest goes, once the 15 s are up",
      len(fake.sent) == 2 and fake.sent[1]["args"]["activity"]["state"] == "latest", fake.sent[-1:])
p.update(dict(act, state="latest"), 140.0)
p.tick(140.0)
check("the same again is not sent", len(fake.sent) == 2)
p.clear(150.0)
p.tick(150.0)
check("cleared: SET_ACTIVITY with no activity, and the socket closed",
      fake.sent[-1]["cmd"] == "SET_ACTIVITY" and "activity" not in fake.sent[-1]["args"] and fake.closed == 1,
      fake.sent[-1])
gone = Fake(fail=True)
q = RP.Presence(lambda: gone, pid=1)
q.client_id = "123456789012345678"
q.update(act, 0.0)
q.tick(0.0)
q.tick(30.0)
check("Discord not running: no error, and not tried again inside a minute", q.attempts == 1, q.attempts)
q.tick(61.0)
check("tried again after it", q.attempts == 2, q.attempts)
_head = open(RP.__file__, encoding="utf-8").read().split("class IpcTransport")[0]
check("the real transport is the only thing that touches a socket",
      "import socket" not in _head and "socket.socket" not in _head and "open(" not in _head.replace(
          "open(path", ""))

print("== in the app ==")
try:
    import tkinter
    tkinter.Tk().destroy()
    HAVE_DISPLAY = True
except Exception as exc:  # noqa: BLE001
    HAVE_DISPLAY = False
    print("  SKIP  the app needs a display (%s). Run it under xvfb-run." % exc)
if HAVE_DISPLAY:
    import tempfile
    os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="edsmt-rp-")
    import edsmt as A
    import edonline as EDO
    check("off until switched on", A.DEFAULT_SETTINGS["discord_presence"] is False)
    check("the app keeps RP for the rig planner; Rich Presence has a name of its own",
          A.RP.__name__ == "rigplan" and A.DRP.__name__ == "richpresence")
    app = A.EDSMT.__new__(A.EDSMT)
    app.settings = dict(A.DEFAULT_SETTINGS)
    seen = Fake()
    app.presence = RP.Presence(lambda: seen, pid=7)
    app.presence_threaded = False
    asked = []
    app.community = EDO.CommunityClient(EDO.Worker())
    app.community.configure("")
    app.community.ask_health = lambda: asked.append(1) or True
    app.stream_now = lambda now=None: STATE
    app.streamer_names = lambda now=None: []
    app.follow_presence(1000.0)
    check("switched off: nothing asked, nothing sent", not asked and not seen.sent)
    app.settings["discord_presence"] = True
    app.follow_presence(1001.0)
    check("switched on: the application id is asked of the community map", asked == [1])
    app.take_health(True, json.dumps({"ok": True, "discord_app_id": "not an id"}))
    check("anything not shaped like a Discord id is ignored", app.presence.client_id == "")
    app.take_health(True, json.dumps({"ok": True, "discord_app_id": "123456789012345678"}))
    check("a Discord id is used", app.presence.client_id == "123456789012345678")
    app.follow_presence(1002.0)
    check("and the session goes to Discord", seen.sent and seen.sent[-1]["args"]["activity"]["details"]
          == "Mining Platinum, Osmium", seen.sent[-1:])
    app.streamer_names = lambda now=None: [("Ega 1", "a body")]
    app.stream_now = lambda now=None: dict(STATE, body="a body")
    app.follow_presence(1030.0)
    check("streamer mode: the body is not on it", "Ega" not in json.dumps(seen.sent[-1])
          and "a body" not in json.dumps(seen.sent[-1]), seen.sent[-1:])
    app.settings["discord_presence"] = False
    app.follow_presence(1031.0)
    check("switched off again: the presence is cleared", "activity" not in seen.sent[-1]["args"]
          and seen.closed >= 1, seen.sent[-1:])

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
