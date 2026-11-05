"""Discord Rich Presence (1.10040, #312).

"Playing EDSMT - Mining Platinum, Osmium" on the commander's Discord
profile, from the Rhino session, over the Discord desktop app's own local
socket - nothing goes over the network from here. As Discord documents it
(developer docs, RPC over IPC; research notes kept with the project):

  - the socket is the named pipe \\\\?\\pipe\\discord-ipc-N on Windows, and
    discord-ipc-N under XDG_RUNTIME_DIR, TMPDIR, TMP, TEMP or /tmp elsewhere;
  - every message is an opcode and a length, two 32-bit little-endian
    integers, then JSON; a HANDSHAKE (0) with the application id opens it,
    and every request after is a FRAME (1);
  - SET_ACTIVITY carries this process's id and the activity, at most two
    buttons with labels of up to 32 characters;
  - one update every 15 seconds: the newest is kept and sent when it may be.

Off until switched on. The application id is handed in (it comes from the
community map, never from here). The socket is only ever touched by
IpcTransport, so everything else is checked without Discord.
"""
import json
import os
import struct
import sys
import uuid

HANDSHAKE, FRAME, CLOSE = 0, 1, 2
EVERY_S = 15.0            # Discord's own limit on presence updates
RETRY_S = 60.0            # after Discord was not there
MAX_TEXT = 128
LARGE_IMAGE = "edsmt"
BUTTONS = (("Get EDSMT", "https://radioraxxla.com/EDSMT/"),
           ("Join Radio Raxxla", "https://discord.gg/DjH9uZabet"))


def frame(op, payload):
    """One message on the socket."""
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return struct.pack("<II", int(op), len(body)) + body


def read_frame(read):
    """(opcode, payload) from `read(n)`, which may return less than asked
    for; OSError when the socket ends part way."""
    def exactly(n):
        out = b""
        while len(out) < n:
            part = read(n - len(out))
            if not part:
                raise OSError("Discord closed the socket")
            out += part
        return out
    op, length = struct.unpack("<II", exactly(8))
    data = exactly(length) if length else b"{}"
    try:
        return op, json.loads(data.decode("utf-8"))
    except ValueError:
        raise OSError("Discord sent something that is not JSON")


def ipc_paths(platform=None, environ=None):
    """Where Discord's socket may be, in the order Discord looks."""
    platform = sys.platform if platform is None else platform
    environ = os.environ if environ is None else environ
    if str(platform).startswith("win"):
        return [r"\\?\pipe\discord-ipc-%d" % n for n in range(10)]
    bases = [environ.get(key) for key in ("XDG_RUNTIME_DIR", "TMPDIR", "TMP", "TEMP")]
    bases = [b.rstrip("/") for b in bases if b] + ["/tmp"]
    out = []
    for base in bases:
        for n in range(10):
            path = "%s/discord-ipc-%d" % (base, n)
            if path not in out:
                out.append(path)
    return out


def _clip(text, limit=MAX_TEXT):
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "\u2026"


def activity(state, now, hidden=False):
    """The presence for what /state.json says (streamout.stream_state).
    `hidden` is streamer mode hiding where you are: no body, no system."""
    state = state if isinstance(state, dict) else {}
    session = state.get("session") if isinstance(state.get("session"), dict) else {}
    mining = [str(m) for m in (state.get("mining") or []) if m]
    running = bool(session.get("running"))
    details = ("Mining " + ", ".join(mining)) if running and mining else \
        ("Rhino session" if running else "On the surface")
    parts = []
    body = str(state.get("body") or "").strip()
    if body and not hidden:
        parts.append(body)
    if running and state.get("cr_hr"):
        parts.append("%s Cr/hr" % (state.get("cr_hr_text") or "{:,}".format(int(state["cr_hr"]))))
    rigs = int(state.get("rigs_down") or 0)
    if rigs:
        parts.append("%d rig%s down" % (rigs, "" if rigs == 1 else "s"))
    out = {"type": 0, "details": _clip(details),
           "assets": {"large_image": LARGE_IMAGE, "large_text": "EDSMT - Surface Mining Tool"},
           "buttons": [{"label": label[:32], "url": url} for label, url in BUTTONS[:2]]}
    if parts:
        out["state"] = _clip(" \u00b7 ".join(parts))
    if running:
        out["timestamps"] = {"start": int(now - float(session.get("seconds") or 0))}
    return out


class Presence:
    """The presence kept up to date: `update` with the newest, `clear` to
    take it away, `tick` once a second or so to send what is due. The
    transport comes from `connect_to()`, which tests replace."""

    def __init__(self, connect_to=None, pid=None):
        self.connect_to = connect_to or IpcTransport
        self.pid = os.getpid() if pid is None else pid
        self.client_id = ""
        self.attempts = 0
        self._transport = None
        self._pending = None
        self._clear = False
        self._last = None
        self._sent_at = None
        self._failed_at = None

    def update(self, act, now):
        self._pending, self._clear = act, False

    def clear(self, now):
        self._pending, self._clear = None, True

    def tick(self, now):
        """Send what is due. Never raises; True when something went."""
        if self._clear:
            self._clear = False
            sent = self._transport is not None and self._send({"pid": self.pid})
            self._close()
            self._last = None
            return sent
        if self._pending is None or not self.client_id or self._pending == self._last:
            return False
        if self._sent_at is not None and now - self._sent_at < EVERY_S:
            return False
        if self._transport is None:
            if self._failed_at is not None and now - self._failed_at < RETRY_S:
                return False
            self.attempts += 1
            try:
                transport = self.connect_to()
                transport.connect(self.client_id)
            except (OSError, ValueError):
                self._failed_at = now
                return False
            self._transport, self._failed_at = transport, None
        act = self._pending
        if not self._send({"pid": self.pid, "activity": act}):
            self._close()
            self._failed_at = now
            return False
        self._last, self._sent_at = act, now
        return True

    def _send(self, args):
        try:
            self._transport.send({"cmd": "SET_ACTIVITY", "args": args, "nonce": str(uuid.uuid4())})
            return True
        except (OSError, ValueError, AttributeError):
            return False

    def _close(self):
        transport, self._transport = self._transport, None
        if transport is not None:
            try:
                transport.close()
            except OSError:
                pass


class IpcTransport:
    """The Discord desktop app's local socket. The only part that touches it."""

    def __init__(self, platform=None, environ=None):
        self.platform = sys.platform if platform is None else platform
        self.environ = os.environ if environ is None else environ
        self._io = None

    def connect(self, client_id):
        last = None
        for path in ipc_paths(self.platform, self.environ):
            try:
                self._io = self._open(path)
                break
            except OSError as problem:
                last = problem
        if self._io is None:
            raise OSError("Discord is not running (%s)" % (last,))
        self._write(frame(HANDSHAKE, {"v": 1, "client_id": str(client_id)}))
        op, data = read_frame(self._read)
        if op != FRAME or data.get("evt") != "READY":
            self.close()
            raise OSError("Discord did not accept EDSMT (%s)" % str(data.get("data") or data)[:120])

    def send(self, payload):
        self._write(frame(FRAME, payload))
        op, _data = read_frame(self._read)
        if op == CLOSE:
            raise OSError("Discord closed the connection")

    def close(self):
        io, self._io = self._io, None
        if io is not None:
            try:
                io.close()
            except OSError:
                pass

    def _open(self, path):
        if str(self.platform).startswith("win"):
            return open(path, "r+b", buffering=0)
        import socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        try:
            sock.connect(path)
        except OSError:
            sock.close()
            raise
        return sock

    def _write(self, data):
        if hasattr(self._io, "sendall"):
            self._io.sendall(data)
        else:
            self._io.write(data)
            self._io.flush()

    def _read(self, n):
        if hasattr(self._io, "recv"):
            return self._io.recv(n)
        return self._io.read(n)
