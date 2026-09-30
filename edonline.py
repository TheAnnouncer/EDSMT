"""
Online services for the Radio Raxxla Surface Mining Map.

Three separate things live here:

  InaraClient      reports the commander's location to inara.cz. Inara asks
                   for TWO REQUESTS PER MINUTE AT MAXIMUM, so that ceiling is
                   enforced here rather than left to the caller.

  CommunityClient  talks to the deposit-sharing API. Inara has no endpoint for
                   surface mining deposits and EDDN has no schema for them yet,
                   so this speaks to a server of our own. The wire format is
                   deliberately close to what an EDDN schema would look like,
                   so it can be repointed later without touching the app.

  MarketWatch      reads Market.json, which the game writes whenever the
                   commodity screen is opened. Frontier's 4.4.1.0 commodities
                   were missing from the community commodity-ID list the
                   market services key off when this was written; they are in
                   it now. Our own users' reads are still collected - a price
                   seen today at a station is the freshest there is.

  analysis         pure functions over recorded deposits: clustering, overlap
                   detection, freshness decay, nearest sites. No I/O, so it is
                   all testable.

Every network call runs on a worker thread and reports back through a queue.
Nothing here touches a widget.
"""

from __future__ import annotations

import os
import re
import json
import time
import queue
import hashlib
import threading
import urllib.error
import urllib.parse
import urllib.request
from math import radians, sin, cos, sqrt, pi

APP_NAME = "EDSMT"
APP_VERSION = "1.10032"
# An honest, contactable User-Agent. Bot filters at the edge judge
# unattended clients on exactly this, and a bare name with no way to
# reach anyone reads as something worth blocking.
USER_AGENT = f"{APP_NAME}/{APP_VERSION} (+https://radioraxxla.com/EDSMT/)"

INARA_URL = "https://inara.cz/inapi/v1"


# Wire-format identifiers. Shaped like EDDN envelopes on purpose: if a real
# community schema ever appears, only the transport changes.
DEPOSIT_SCHEMA = "radioraxxla/surfacemining/1"
DEPLETION_SCHEMA = "radioraxxla/surfacemining-depletion/1"
MARKET_SCHEMA = "radioraxxla/surfacemining-market/1"
VERIFY_SCHEMA = "radioraxxla/surfacemining-verify/1"

# Inara's author, on the API board: "please ensure your apps are doing TWO
# requests per minute AT MAXIMUM". Batching is how you stay under it - queue
# events up and send them together.
INARA_MIN_INTERVAL = 35.0


# ---------------------------------------------------------------------------
# Shared plumbing
# ---------------------------------------------------------------------------



# Markers a web front end's "are you a browser?" page carries. Matched on the
# BODY, because the status code alone does not say it: a check page arrives
# as 403 or 503, and so does an ordinary refusal.
CHALLENGE_MARKS = ("cf_chl_opt", "__cf_chl", "cf-mitigated", "just a moment")
CHALLENGE_SAYS = ("The server answered with a browser check instead of an "
                  "answer, which a desktop app cannot pass. Nothing is wrong "
                  "with EDSMT or with your settings - it is a setting at the "
                  "server's end. Please report it in the Radio Raxxla "
                  "Discord.")


def _challenged(body: str) -> bool:
    """Is this a browser-check page rather than an answer?

    Worth detecting by name. Without this a challenge surfaces as "HTTP 403"
    or as a JSON parse error on a page of HTML, and the commander reads that
    as "Find is broken" - which is precisely the class of failure that has
    cost this project a release every time it has happened.
    """
    return any(mark in (body or "").lower() for mark in CHALLENGE_MARKS)


def _host_of(url: str) -> str:
    """"https://inara.cz/inapi/v1" -> "inara.cz". For the error message."""
    try:
        return urllib.parse.urlparse(url).hostname or "the server"
    except Exception:
        return "the server"


def _decode(raw: str, url: str) -> dict:
    """Turn a response body into JSON, or say what arrived instead.

    Everything this app receives goes through here, because a bare
    json.loads on somebody else's server reaches the commander as

        Expecting value: line 1 column 1 (char 0)

    which is a sentence about a parser, not about anything they can act on.
    It was on the status line under "Inara key" for a whole release, reading
    for all the world like the key was wrong when the key was fine.
    """
    host = _host_of(url)
    text = (raw or "").strip()
    if not text:
        raise RuntimeError("%s accepted the request and sent nothing back. "
                           "That is the server, not EDSMT - try again in a "
                           "few minutes." % host)
    if _challenged(text) and not text.startswith(("{", "[")):
        raise RuntimeError(CHALLENGE_SAYS)
    try:
        data = json.loads(text)
    except ValueError:
        if text.lstrip()[:1] == "<":
            raise RuntimeError("%s sent a web page instead of an answer, "
                               "which usually means it is down or behind a "
                               "maintenance screen. Nothing is wrong with "
                               "EDSMT or with your key." % host) from None
        raise RuntimeError("%s sent something that is not JSON: %s"
                           % (host, _snippet(text))) from None
    if not isinstance(data, dict):
        raise RuntimeError("%s sent %s where an object was expected."
                           % (host, type(data).__name__))
    return data


def _snippet(text: str, limit: int = 120) -> str:
    """The first readable line of a body, short enough for a status line."""
    line = " ".join(str(text or "").split())
    return line[:limit] + ("..." if len(line) > limit else "")


def _read_error(exc: urllib.error.HTTPError, url: str) -> RuntimeError:
    """An HTTP error status, turned into something worth reading.

    The body has to come out of the exception: a challenge and a refusal
    both arrive WITH an error code, and urllib never hands back a response
    to read it from.
    """
    body = ""
    try:
        body = exc.read().decode("utf-8", errors="replace")
    except Exception:
        pass
    if _challenged(body):
        return RuntimeError(CHALLENGE_SAYS)
    host = _host_of(url)
    # A JSON error body is the useful case - most APIs say why in it.
    try:
        data = json.loads(body)
        said = ""
        if isinstance(data, dict):
            head = data.get("header")
            if isinstance(head, dict) and head.get("eventStatusText"):
                said = str(head["eventStatusText"])
            else:
                said = str(data.get("detail") or data.get("error")
                           or data.get("message") or "")
        if said:
            return RuntimeError("%s refused it (HTTP %s): %s"
                                % (host, exc.code, _snippet(said)))
    except ValueError:
        pass
    if exc.code in (401, 403):
        return RuntimeError("%s would not accept the request (HTTP %s). "
                            "Check the key in Settings." % (host, exc.code))
    if exc.code in (500, 502, 503, 504):
        return RuntimeError("%s is having trouble at its end (HTTP %s). "
                            "Nothing is wrong with EDSMT - try again in a "
                            "few minutes." % (host, exc.code))
    return RuntimeError("%s replied HTTP %s." % (host, exc.code))


def post_json(url: str, payload: dict, timeout: float = 20.0,
              headers: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("User-Agent", USER_AGENT)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise _read_error(exc, url) from None
    except urllib.error.URLError as exc:
        raise RuntimeError("could not reach %s: %s"
                           % (_host_of(url), exc.reason)) from None
    return _decode(raw, url)


def get_json(url: str, timeout: float = 20.0, headers: dict | None = None) -> dict:
    request = urllib.request.Request(url, method="GET")
    request.add_header("User-Agent", USER_AGENT)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise _read_error(exc, url) from None
    except urllib.error.URLError as exc:
        raise RuntimeError("could not reach %s: %s"
                           % (_host_of(url), exc.reason)) from None
    return _decode(raw, url)


def utc_stamp(when: float | None = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(when))


class Worker:
    """Runs callables off the UI thread and hands results back on a queue."""

    def __init__(self):
        self.results: queue.Queue[tuple[str, bool, str]] = queue.Queue()
        self._jobs: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def submit(self, tag: str, fn) -> None:
        self._jobs.put((tag, fn))

    def _run(self) -> None:
        while True:
            tag, fn = self._jobs.get()
            try:
                message = fn()
                self.results.put((tag, True, message or ""))
            except urllib.error.HTTPError as exc:
                self.results.put((tag, False, f"HTTP {exc.code}"))
            except urllib.error.URLError as exc:
                self.results.put((tag, False, f"no connection ({exc.reason})"))
            except Exception as exc:                  # noqa: BLE001
                self.results.put((tag, False, str(exc)))

    def drain(self) -> list[tuple[str, bool, str]]:
        out = []
        while True:
            try:
                out.append(self.results.get_nowait())
            except queue.Empty:
                return out


# ---------------------------------------------------------------------------
# Inara
# ---------------------------------------------------------------------------

class InaraClient:
    """Batches events and posts them to Inara, within the rate limit."""

    def __init__(self, worker: Worker):
        self.worker = worker
        self.api_key = ""
        self.cmdr = ""
        self.fid = ""
        self.developing = False
        self.enabled = False
        self.last_sent = 0.0
        self.last_result = ""
        self._pending: list[dict] = []
        self._lock = threading.Lock()

    def configure(self, api_key: str, enabled: bool, developing: bool = False) -> None:
        self.api_key = (api_key or "").strip()
        self.enabled = bool(enabled and self.api_key)
        self.developing = developing

    def set_commander(self, name: str, fid: str = "") -> None:
        """From the journal's Commander / LoadGame events, never typed by hand.

        Inara's docs are explicit that the CMDR name must come from the
        journal or cAPI so it matches the in-game name exactly.
        """
        if name:
            self.cmdr = name
        if fid:
            self.fid = fid

    @property
    def ready(self) -> bool:
        return bool(self.enabled and self.api_key and self.cmdr)

    def header(self) -> dict:
        head = {
            "appName": APP_NAME,
            "appVersion": APP_VERSION,
            "isBeingDeveloped": bool(self.developing),
            "APIkey": self.api_key,
            "commanderName": self.cmdr,
        }
        if self.fid:
            head["commanderFrontierID"] = self.fid
        return head

    def add(self, event_name: str, data: dict, when: str | None = None) -> None:
        if not self.ready:
            return
        with self._lock:
            self._pending.append({
                "eventName": event_name,
                "eventTimestamp": when or utc_stamp(),
                "eventData": data,
            })

    # -- the three events that matter for a surface mining tool -----------

    def travel_location(self, system: str, body: str = "",
                        coords=None, when: str | None = None) -> None:
        data: dict = {"starsystemName": system}
        if body:
            data["stellarBodyName"] = body
        if coords:
            data["starsystemCoords"] = list(coords)
        self.add("setCommanderTravelLocation", data, when)

    def travel_land(self, system: str, body: str,
                    lat: float | None = None, lon: float | None = None,
                    when: str | None = None) -> None:
        """Journal Touchdown. Inara accepts the body and its coordinates."""
        data: dict = {"starsystemName": system, "stellarBodyName": body}
        if lat is not None and lon is not None:
            data["stellarBodyCoords"] = [round(float(lat), 5), round(float(lon), 5)]
        self.add("addCommanderTravelLand", data, when)

    # -- sending ----------------------------------------------------------

    def due(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        with self._lock:
            has_work = bool(self._pending)
        return has_work and self.ready and (now - self.last_sent) >= INARA_MIN_INTERVAL

    def flush(self, force: bool = False) -> bool:
        """Send the batch if the rate limit allows. Returns True if sent."""
        if not force and not self.due():
            return False
        with self._lock:
            if not self._pending:
                return False
            batch, self._pending = self._pending, []
        self.last_sent = time.time()
        payload = {"header": self.header(), "events": batch}
        self.worker.submit("inara", lambda: self._send(payload))
        return True

    def verify(self) -> None:
        """Check the API key by asking for the commander's own profile."""
        payload = {
            "header": self.header(),
            "events": [{
                "eventName": "getCommanderProfile",
                "eventTimestamp": utc_stamp(),
                "eventData": {"searchName": self.cmdr},
            }],
        }
        self.worker.submit("inara-verify", lambda: self._send(payload))

    @staticmethod
    def _send(payload: dict) -> str:
        reply = post_json(INARA_URL, payload)
        header = reply.get("header") or {}
        status = int(header.get("eventStatus") or 0)
        if status >= 400:
            raise RuntimeError(header.get("eventStatusText") or f"Inara error {status}")

        problems = [
            (e.get("eventStatusText") or "rejected")
            for e in (reply.get("events") or [])
            if int(e.get("eventStatus") or 200) >= 400
        ]
        count = len(payload.get("events") or [])
        if problems:
            return f"{count} sent, {len(problems)} rejected: {problems[0]}"
        return f"{count} event(s) accepted"


# ---------------------------------------------------------------------------
# Update check
# ---------------------------------------------------------------------------

# A small static file beside the download, written by build/site.py. NOT the
# community API: a commander needs to be told about a new build even on a day
# the API is down, and a static file on the website is served from
# a cache without touching the API at all.
VERSION_URL = "https://radioraxxla.com/EDSMT/version.json"


def version_tuple(text):
    """'1.10002' -> (1, 10002). Anything unparseable sorts lowest.

    Comparing version strings as strings says '1.9' > '1.10002', which is
    how an updater ends up telling everybody they are up to date for ever.
    """
    parts = []
    for chunk in str(text or "").strip().split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def is_newer(candidate, current):
    """Is `candidate` a later version than `current`?"""
    if not candidate:
        return False
    a, b = version_tuple(candidate), version_tuple(current)
    length = max(len(a), len(b))
    a = a + (0,) * (length - len(a))
    b = b + (0,) * (length - len(b))
    return a > b


# Where an update may be downloaded from. version.json NAMES a download; it
# does not get to choose where the app goes to fetch it, so a file that
# points anywhere else is refused, and so is a redirect off these hosts.
UPDATE_HOSTS = ("radioraxxla.com", "www.radioraxxla.com")
UPDATE_MAX_BYTES = 400 * 1024 * 1024
UPDATE_KINDS = ("installer", "portable")


def update_package(data, kind):
    """The {url, sha256, bytes} version.json gives for one kind of build.

    None unless every part of it is sound: HTTPS, one of UPDATE_HOSTS, a
    64-character SHA-256 and a believable size. Anything less and the app
    falls back to pointing at the download page, which is what it did
    before downloads existed.
    """
    pkg = data.get(kind) if isinstance(data, dict) else None
    if not isinstance(pkg, dict):
        return None
    url = str(pkg.get("url") or "").strip()
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    if parts.scheme != "https" or (parts.hostname or "").lower() not in UPDATE_HOSTS:
        return None
    digest = str(pkg.get("sha256") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        return None
    try:
        size = int(pkg.get("bytes") or 0)
    except (TypeError, ValueError):
        return None
    if not 0 < size <= UPDATE_MAX_BYTES:
        return None
    return {"url": url, "sha256": digest, "bytes": size}


def sha256_of(path):
    """The file's SHA-256, or "" if it cannot be read."""
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def download_verified(url, dest, sha256, size, progress=None, timeout=30.0):
    """Fetch `url` to `dest`, and keep it only if it is exactly what was
    promised: the right number of bytes with the right SHA-256.

    Written to dest + ".part" and renamed into place only once it checks
    out, so a half-finished or wrong file is never left where the app would
    run it. A file already at `dest` with the right checksum is kept and
    not fetched again.
    """
    if os.path.exists(dest) and sha256_of(dest) == sha256:
        return dest
    if (urllib.parse.urlsplit(url).hostname or "").lower() not in UPDATE_HOSTS:
        raise RuntimeError("refused a download from %s" % _host_of(url))
    folder = os.path.dirname(dest)
    if folder:
        os.makedirs(folder, exist_ok=True)
    part = dest + ".part"
    request = urllib.request.Request(url, method="GET")
    request.add_header("User-Agent", USER_AGENT)
    digest, got = hashlib.sha256(), 0
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            final = (urllib.parse.urlsplit(response.geturl()).hostname or "").lower()
            if final not in UPDATE_HOSTS:
                raise RuntimeError("the download was redirected to %s - refused"
                                   % (final or "somewhere unnamed"))
            with open(part, "wb") as fh:
                while True:
                    chunk = response.read(1 << 16)
                    if not chunk:
                        break
                    got += len(chunk)
                    if got > size:
                        raise RuntimeError("the download is bigger than "
                                           "version.json said - not kept")
                    digest.update(chunk)
                    fh.write(chunk)
                    if progress is not None:
                        progress(got, size)
    except urllib.error.HTTPError as exc:
        _discard(part)
        raise _read_error(exc, url) from None
    except urllib.error.URLError as exc:
        _discard(part)
        raise RuntimeError("could not reach %s: %s"
                           % (_host_of(url), exc.reason)) from None
    except BaseException:
        _discard(part)
        raise
    if got != size:
        _discard(part)
        raise RuntimeError("the download stopped short (%d of %d bytes) - "
                           "it will be tried again next time" % (got, size))
    if digest.hexdigest() != sha256:
        _discard(part)
        raise RuntimeError("the download did not match its checksum, so it "
                           "was thrown away. Nothing was installed.")
    os.replace(part, dest)
    return dest


def _discard(path):
    try:
        os.remove(path)
    except OSError:
        pass


class UpdateCheck:
    """Ask the website whether there is a newer build, and fetch it.

    Asked once on launch and again from the Settings button. A newer build
    is DOWNLOADED in the background - from radioraxxla.com only, checked
    against the SHA-256 published beside it - and then waits for the
    commander to press INSTALL. Nothing is run without that click: the app
    may be closed mid-run otherwise, and a tool that replaces itself while
    somebody is out on the surface is a tool that loses a run.
    """

    def __init__(self, worker: Worker):
        self.worker = worker
        self.checked = False
        # (bytes so far, bytes expected) while a download runs. Written by
        # the worker thread, read by the Tk loop to show a percentage; a
        # tuple swapped whole, so the reader never sees half of one.
        self.progress = None

    def download(self, package: dict, dest: str, version: str) -> bool:
        """Fetch a checked package in the background (tag update-download).

        The answer is JSON: where the file is, which version, its checksum.
        """
        if not package:
            return False

        def fetch():
            self.progress = (0, int(package["bytes"]))
            try:
                path = download_verified(
                    package["url"], dest, package["sha256"], package["bytes"],
                    progress=lambda got, size: setattr(self, "progress", (got, size)))
            finally:
                self.progress = None
            return json.dumps({"path": path, "version": version,
                               "sha256": package["sha256"]})

        self.worker.submit("update-download", fetch)
        return True

    def check(self, current_version: str, url: str = VERSION_URL,
              force: bool = False) -> bool:
        """Ask the website. `force` is the Settings button, and ignores the
        once-per-run guard - otherwise pressing it after launch would do
        nothing at all, which is the very complaint it exists to answer."""
        if self.checked and not force:
            return False
        self.checked = True
        tag = "update-now" if force else "update"
        self.worker.submit(tag, lambda: self._look(current_version, url))
        return True

    @staticmethod
    def _look(current_version: str, url: str) -> str:
        """A NEWER build returns a message. Up to date returns "".

        The empty string matters: on launch it means say nothing, because
        being told you are up to date every single time you open the app is
        noise. The Settings button turns the same empty answer into "you are
        up to date", so the check can be seen to work - a silent success and
        a silent failure looked identical, and there was no way to tell them
        apart without reading the source.
        """
        # A quarter-hour stamp on the address, so a cache in front of the
        # website can hold version.json for fifteen minutes at most rather
        # than for as long as it likes.
        stamp = "t=%d" % (time.time() // 900)
        data = get_json(url + ("&" if "?" in url else "?") + stamp, timeout=10.0)
        latest = str(data.get("version") or "")
        if not latest:
            raise ValueError("version.json has no version field")
        if not is_newer(latest, current_version):
            return ""
        where = str(data.get("url") or "https://radioraxxla.com/EDSMT/")
        headline = str(data.get("headline") or "").strip()
        note = " - %s" % headline if headline else ""
        # JSON, so the app gets the packages as well as the words. The
        # message is still in it, whole, for anything that only says it.
        answer = {"version": latest, "page": where, "headline": headline,
                  "message": "EDSMT %s is out%s." % (latest, note)}
        for kind in UPDATE_KINDS:
            answer[kind] = update_package(data, kind)
        return json.dumps(answer)


# ---------------------------------------------------------------------------
# Community deposit sharing
# ---------------------------------------------------------------------------

class CommunityClient:
    """Client for the deposit-sharing API.

    The wire format mirrors what an EDDN schema would carry - a header
    naming the uploading software and commander, and a message holding the
    observation - so that if a community schema does appear, only the
    transport changes.
    """

    def __init__(self, worker: Worker):
        self.worker = worker
        self.base_url = ""
        self.token = ""
        self.enabled = False
        self.share_name = True

    # Where the community map lives. Used when a settings file carries a
    # blank URL - which every settings.json written before the address
    # existed does, and an empty string beats the default when the two are
    # merged. Upgrading should not silently disconnect somebody.
    DEFAULT_URL = "https://api.radioraxxla.com"

    def configure(self, base_url: str, token: str = "",
                  enabled: bool = False, share_name: bool = True) -> None:
        self.base_url = (base_url or "").strip().rstrip("/") or self.DEFAULT_URL
        self.token = (token or "").strip()
        self.enabled = bool(enabled)
        self.share_name = share_name

    @property
    def ready(self) -> bool:
        """May we UPLOAD? Only with the commander's say-so."""
        return bool(self.enabled and self.base_url)

    @property
    def can_read(self) -> bool:
        """May we SEARCH? Yes - reading is not sharing.

        Making somebody upload before they may look things up is a toll
        gate on a community map, and it is the wrong way round: people
        decide whether to contribute after they have seen the thing is
        worth contributing to. Search works for everyone; only uploads
        wait for consent.
        """
        return bool(self.base_url)

    @property
    def can_verify(self) -> bool:
        """May we VERIFY? Only somebody carrying a staff token.

        Not gated on the upload switch. Verification is not sharing a find
        of your own, it is standing behind somebody else's, and the server
        checks the token against the staff list anyway - so gating it here
        on a setting the server never sees would only mean the button was
        missing for the one person entitled to press it.
        """
        return bool(self.base_url and self.token)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @staticmethod
    def envelope(cmdr: str, deposits: list[dict], share_name: bool = True) -> dict:
        return {
            "$schema": DEPOSIT_SCHEMA,
            "header": {
                "uploaderID": cmdr if share_name else "",
                "softwareName": APP_NAME,
                "softwareVersion": APP_VERSION,
                "gatewayTimestamp": utc_stamp(),
            },
            "message": {"deposits": deposits},
        }

    def upload(self, cmdr: str, deposits: list[dict]) -> bool:
        if not self.ready or not deposits:
            return False
        payload = self.envelope(cmdr, deposits, self.share_name)
        url = f"{self.base_url}/v1/deposits"
        self.worker.submit(
            "share",
            lambda: self._report(post_json(url, payload, headers=self._headers())))
        return True

    @staticmethod
    def _flag(name, value):
        """A boolean query parameter, or nothing at all.

        Only sent when it is on. Every one of these is False at the server
        too, so spelling out the default would put a parameter on the wire
        that means "leave it as it was" - and an older server that has not
        grown the flag yet would reject the request rather than ignore it.
        The value is lowercase because that is the spelling every HTTP
        toolchain agrees on; Python's own str(True) is not.
        """
        return {name: "true"} if value else {}

    @staticmethod
    def _near(near, within_ly):
        """Turn "where I am" into query parameters, or nothing at all.

        A radius without a position is meaningless, and a position without
        a radius is a filter nobody asked for, so it is both or neither.
        """
        if not within_ly or not near or len(near) != 3:
            return {}
        try:
            x, y, z = (float(v) for v in near)
        except (TypeError, ValueError):
            return {}
        return {"near_x": x, "near_y": y, "near_z": z,
                "within_ly": float(within_ly)}

    def search(self, commodity: str = "", system: str = "", limit: int = 50,
               near=None, within_ly: float = 0) -> bool:
        if not self.can_read:
            return False
        params = {k: v for k, v in
                  (("commodity", commodity), ("system", system), ("limit", limit))
                  if v}
        params.update(self._near(near, within_ly))
        url = f"{self.base_url}/v1/deposits?" + urllib.parse.urlencode(params)
        self.worker.submit(
            "search", lambda: json.dumps(get_json(url, headers=self._headers())))
        return True

    def grounds(self) -> bool:
        """What each kind of ground has carried, from every shared find."""
        if not self.can_read:
            return False
        url = f"{self.base_url}/v1/grounds"
        self.worker.submit(
            "grounds", lambda: json.dumps(get_json(url, headers=self._headers())))
        return True

    def system_sites(self, system: str) -> bool:
        """Every shared site in one system, worked out ones included."""
        if not (self.can_read and system):
            return False
        params = {"system": system, "limit": 500, "include_depleted": "true"}
        url = f"{self.base_url}/v1/sites?" + urllib.parse.urlencode(params)
        self.worker.submit(
            "landing", lambda: json.dumps({"system": system,
                                           **get_json(url, headers=self._headers())}))
        return True

    def body_deposits(self, system: str, body: str) -> bool:
        """Every shared find on one body, for the map and the overlay.

        Asked by the body's exact name - the planet filter is an exact
        match - so a busy system does not bring back every other body in
        it. Reading needs no consent: it is not sharing anything.
        """
        if not (self.can_read and system and body):
            return False
        params = {"planet": body, "limit": 500}
        url = f"{self.base_url}/v1/deposits?" + urllib.parse.urlencode(params)
        self.worker.submit(
            "body", lambda: json.dumps({"system": system, "body": body,
                                        **get_json(url, headers=self._headers())}))
        return True

    def sites(self, commodity: str = "", min_rigs: int = 0, min_types: int = 0,
              max_age_days: int = 0, limit: int = 50,
              near=None, within_ly: float = 0, system: str = "",
              verified_only: bool = False,
              include_depleted: bool = False, body: str = "",
              name: str = "") -> bool:
        """Ranked sites, ranked by overlap the way ring miners rank hotspots.

        A ring hotspot is permanent; a surface deposit is not. Frontier were
        explicit that deposits "regenerate at a very slow rate", so age is a
        first-class filter here rather than a detail - a site stripped last
        week is worse than no result at all.

        Distance is the other first-class filter, for the same reason in
        space rather than time: the best site in the galaxy is 40,000 Ly
        away and nobody is driving there.

        `system` and `body` narrow by one or the other; `name` matches
        either. The app's box is labelled "System / body" and the person
        typing into it knows which they meant - the app does not, and it is
        not going to guess. `name` is the one to send from that box.
        """
        if not self.can_read:
            return False
        params = {k: v for k, v in (("commodity", commodity),
                                    ("system", system),
                                    ("body", body),
                                    ("name", name),
                                    ("min_rigs", min_rigs),
                                    ("min_types", min_types),
                                    ("max_age_days", max_age_days),
                                    ("limit", limit)) if v}
        params.update(self._near(near, within_ly))
        params.update(self._flag("verified_only", verified_only))
        params.update(self._flag("include_depleted", include_depleted))
        url = f"{self.base_url}/v1/sites?" + urllib.parse.urlencode(params)
        self.worker.submit(
            "sites", lambda: json.dumps(get_json(url, headers=self._headers())))
        return True

    def intact(self, commodity: str = "", min_rigs: int = 0,
               min_types: int = 0, min_confidence: float = 0.5,
               limit: int = 50, near=None, within_ly: float = 0,
               system: str = "", body: str = "", name: str = "",
               verified_only: bool = False) -> bool:
        """The sites most likely to STILL BE THERE, rather than the biggest.

        Deposit positions come out of the body address and anybody with the
        algorithm has them all without leaving the dock. Whether the last
        commander through took the lot is the one thing no generator knows,
        and it is the only question this endpoint answers.

        min_confidence is sent whatever it is, including 0. It is the one
        number here with a non-zero default at the far end, so dropping it
        for being falsy would silently restore 0.5 exactly when somebody
        asked to see everything.
        """
        if not self.can_read:
            return False
        params = {k: v for k, v in (("commodity", commodity),
                                    ("system", system),
                                    ("body", body),
                                    ("name", name),
                                    ("min_rigs", min_rigs),
                                    ("min_types", min_types),
                                    ("limit", limit)) if v}
        params["min_confidence"] = float(min_confidence)
        params.update(self._near(near, within_ly))
        params.update(self._flag("verified_only", verified_only))
        url = f"{self.base_url}/v1/intact?" + urllib.parse.urlencode(params)
        self.worker.submit(
            "intact", lambda: json.dumps(get_json(url, headers=self._headers())))
        return True

    def commodities(self) -> bool:
        """What the server will match a commodity filter against.

        The app ships its own list of the thirteen. The server keeps the
        canonical spellings and the density tiers, and it is the end that
        gets updated when Frontier add a fourteenth - so asking beats
        waiting for everyone to reinstall.
        """
        if not self.can_read:
            return False
        url = f"{self.base_url}/v1/commodities"
        self.worker.submit(
            "commodities",
            lambda: json.dumps(get_json(url, headers=self._headers())))
        return True

    def report_depletion(self, cmdr: str, system: str, planet: str,
                         spot: str, worked_out: bool = True) -> bool:
        """Say a site has been worked out, so nobody else drives out to it."""
        if not self.ready:
            return False
        payload = {
            "$schema": DEPLETION_SCHEMA,
            "header": {
                "uploaderID": cmdr if self.share_name else "",
                "softwareName": APP_NAME,
                "softwareVersion": APP_VERSION,
                "gatewayTimestamp": utc_stamp(),
            },
            "message": {"system": system, "planet": planet, "spot": spot,
                        "worked_out": bool(worked_out)},
        }
        url = f"{self.base_url}/v1/depletion"
        self.worker.submit(
            "deplete",
            lambda: self._depleted(post_json(url, payload, headers=self._headers())))
        return True

    def verify(self, cmdr: str, system: str, planet: str, spot: str = "1",
               verified: bool = True) -> bool:
        """Say somebody from Radio Raxxla has stood on this site.

        Nothing in the app could set this, so the "Verified only" filter has
        never had a single row to match - a control that could only ever
        empty the table. The server has carried the column since the first
        version of the API; this is the end that was missing.
        """
        if not self.can_verify or not system or not planet:
            return False
        payload = {
            "$schema": VERIFY_SCHEMA,
            "header": {
                "uploaderID": cmdr if self.share_name else "",
                "softwareName": APP_NAME,
                "softwareVersion": APP_VERSION,
                "gatewayTimestamp": utc_stamp(),
            },
            "message": {"system": system, "planet": planet,
                        "spot": spot or "1", "verified": bool(verified)},
        }
        url = f"{self.base_url}/v1/verify"
        self.worker.submit(
            "verify",
            lambda: self._verified(post_json(url, payload, headers=self._headers())))
        return True

    def wing(self, code: str, beat: dict) -> bool:
        """One beat of the wing link (beta): where this commander is, and
        back, where the rest of the wing is. The server keeps nothing past
        two minutes, and the code is the only key. Not gated on sharing -
        this is not the map, and it only goes on when switched on."""
        if not self.can_read or not code or not beat:
            return False
        url = "%s/v1/wing/%s" % (self.base_url, urllib.parse.quote(
            str(code).strip().upper()))
        self.worker.submit("wing", lambda: json.dumps(
            post_json(url, beat, timeout=8.0, headers=self._headers())))
        return True

    def upload_prices(self, cmdr: str, market: dict) -> bool:
        """Share one station's prices for the surface-mining commodities.

        When this was written the 4.4.1.0 commodities were missing from the
        community commodity-ID list, and every market service keyed off it
        was blind to them. They have been added since; our own users' reads
        stay, because a price somebody saw today is the freshest there is.
        """
        if not self.ready or not market or not market.get("items"):
            return False
        payload = {
            "$schema": MARKET_SCHEMA,
            "header": {
                "uploaderID": cmdr if self.share_name else "",
                "softwareName": APP_NAME,
                "softwareVersion": APP_VERSION,
                "gatewayTimestamp": utc_stamp(),
            },
            "message": market,
        }
        url = f"{self.base_url}/v1/market"
        self.worker.submit(
            "prices",
            lambda: self._priced(post_json(url, payload, headers=self._headers())))
        return True

    def best_prices(self, commodity: str = "", near_system: str = "",
                    limit: int = 20, near=None, within_ly: float = 0) -> bool:
        """Where the stuff sells. Answered from what our own users have seen.

        near_system and near are not alternatives to each other. The first
        names a system; the second is where the commander actually is, and
        it is the one that works from a planet surface - which is where
        anybody asking this question is sitting. Asking by name for the
        system you are standing in answers with nothing, every time,
        because nobody has ever sold anything on a rock.
        """
        if not self.can_read:
            return False
        params = {k: v for k, v in (("commodity", commodity),
                                    ("near", near_system),
                                    ("limit", limit)) if v}
        params.update(self._near(near, within_ly))
        url = f"{self.base_url}/v1/prices?" + urllib.parse.urlencode(params)
        self.worker.submit(
            "market", lambda: json.dumps(get_json(url, headers=self._headers())))
        return True

    def sell(self, commodity: str, near_system: str = "", limit: int = 20,
             near=None, within_ly: float = 0, tag: str = "sell") -> bool:
        """Best sell price for ONE commodity, our figures and the upstream's.

        Kept apart from best_prices rather than folded into it because the
        answer is a different shape: two lists, labelled by where each came
        from, and a headline figure across both. Blending them would hide
        which rows are somebody's own Market.json from this week and which
        are an index that may not have been near the station in months.

        The commodity is required, not optional - the server answers 422
        without one, and a request that is going to be refused is better
        refused here, where the caller still knows why.
        """
        if not self.can_read or not commodity:
            return False
        params = {k: v for k, v in (("commodity", commodity),
                                    ("near", near_system),
                                    ("limit", limit)) if v}
        params.update(self._near(near, within_ly))
        url = f"{self.base_url}/v1/sell?" + urllib.parse.urlencode(params)
        # The tag says who asked: the Find window, or the hold's own lookup
        # in the earnings, which is answered somewhere else entirely.
        self.worker.submit(
            tag, lambda: json.dumps(get_json(url, headers=self._headers())))
        return True

    @staticmethod
    def _report(reply: dict) -> str:
        accepted = reply.get("accepted", 0)
        duplicates = reply.get("duplicates", 0)
        return f"{accepted} shared, {duplicates} already known"

    @staticmethod
    def _verified(reply: dict) -> str:
        if not reply.get("ok"):
            return "not recorded"
        who = str(reply.get("by") or "").strip()
        if reply.get("status") != "verified":
            return "verification withdrawn"
        return "site verified" + (" by %s" % who if who else "")

    @staticmethod
    def _depleted(reply: dict) -> str:
        return "site marked worked out" if reply.get("ok") else "not recorded"

    @staticmethod
    def _priced(reply: dict) -> str:
        return f"{reply.get('accepted', 0)} price(s) shared"


# ---------------------------------------------------------------------------
# Market.json
# ---------------------------------------------------------------------------

# The 13 commodities from 4.4.1.0. Frontier spell the first one with an
# umlaut; the journal and the market can use either form, so both match.
SURFACE_COMMODITIES = [
    "Bastn\u00e4site", "Deuterium", "Diamond", "Helium", "Helium-3", "Iridium",
    "Magnesite", "Olivine", "Periclase dunite", "Quartz pyroxenite",
    "Ruby", "Sapphire", "Thortveitite",
]


def fold(text) -> str:
    """Compare commodity names the way the game does not: loosely.

    Bastn\u00e4site / Bastnasite / $bastnasite_name; / BASTNASITE all have to land
    on the same commodity, or half the finds go in under a second name.
    """
    import unicodedata
    raw = unicodedata.normalize("NFKD", str(text))
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return "".join(c for c in raw.lower() if c.isalnum())


SURFACE_LOOKUP = {fold(name): name for name in SURFACE_COMMODITIES}


def canonical_commodity(name):
    """Frontier's own spelling for a commodity, or None if not one of ours."""
    return SURFACE_LOOKUP.get(fold(name))


def commodity_symbol(raw) -> str:
    """"$sapphire_name;" -> "sapphire". The same in every language."""
    text = str(raw or "").strip().strip("$;")
    if text.lower().endswith("_name"):
        text = text[:-5]
    return text


def parse_market(data: dict, only_surface: bool = True, namer=None) -> dict:
    """Turn a Market.json document into something worth uploading.

    Written defensively on purpose. Frontier have not published a schema for
    the new commodities, so every field is treated as optional and anything
    unrecognised is skipped rather than guessed at.

    The symbol ("$sapphire_name;") is matched first and the localised name
    only after it. Localised first meant a French client's "Saphir" matched
    nothing, so their markets were never priced at all. namer, when given,
    names what is not one of ours - the app passes survey.english_name.
    """
    if not isinstance(data, dict):
        return {}
    items = data.get("Items") or []
    if not isinstance(items, list):
        items = []

    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        symbol = commodity_symbol(item.get("Name"))
        local = str(item.get("Name_Localised") or "")
        known = (canonical_commodity(symbol) if symbol else None) \
            or canonical_commodity(local)
        if only_surface and not known:
            continue
        if known:
            raw = known
        elif namer is not None:
            raw = namer(item.get("Name"), local)
        else:
            raw = local or symbol
        try:
            sell = int(item.get("SellPrice") or 0)
            buy = int(item.get("BuyPrice") or 0)
            demand = int(item.get("Demand") or 0)
            stock = int(item.get("Stock") or 0)
        except (TypeError, ValueError):
            continue
        if sell <= 0 and buy <= 0:
            continue
        rows.append({
            "commodity": known or str(raw),
            "sell": sell,
            "buy": buy,
            "demand": demand,
            "stock": stock,
            "demand_bracket": item.get("DemandBracket"),
        })

    if not rows:
        return {}
    return {
        "market_id": data.get("MarketID"),
        "station": str(data.get("StationName") or ""),
        "system": str(data.get("StarSystem") or ""),
        "station_type": str(data.get("StationType") or ""),
        "when": str(data.get("timestamp") or utc_stamp()),
        "items": rows,
    }


# ---------------------------------------------------------------------------
# Analysis - pure functions, no I/O
# ---------------------------------------------------------------------------

# Deposit density drives both yield and rig efficiency - 4.4.1.0 lists
# "Deposit capacity per density level" and "Efficiency based on deposit
# density". Frontier have not published the tier names, so these are the
# forms seen so far and anything else is kept verbatim rather than dropped.
DENSITY_TIERS = ["Depleted", "Low", "Medium", "High", "Pristine"]
DENSITY_RANK = {fold(name): i for i, name in enumerate(DENSITY_TIERS)}
# Words the game might use for the same idea, mapped onto the same ladder.
DENSITY_RANK.update({
    fold("very low"): 1, fold("moderate"): 2, fold("very high"): 4,
    fold("rich"): 4, fold("major"): 4, fold("minor"): 1, fold("common"): 2,
    fold("exhausted"): 0, fold("empty"): 0,
})


def density_rank(value) -> int:
    """0-4 for a density label, or -1 when it is not one we recognise."""
    if value in (None, ""):
        return -1
    return DENSITY_RANK.get(fold(value), -1)


def freshness_factor(age_days: float, half_life_days: float = 21.0) -> float:
    """How much a find is still worth, given deposits regenerate slowly.

    Frontier: deposits "regenerate at a very slow rate". A shared surface
    database therefore rots in a way a hotspot database never does, so age
    is applied as a decay rather than shown as a column and ignored. Halves
    every three weeks by default; never reaches zero, because a stripped
    site is still a site worth knowing about.
    """
    try:
        age = max(0.0, float(age_days))
    except (TypeError, ValueError):
        return 1.0
    if half_life_days <= 0:
        return 1.0
    return 0.5 ** (age / float(half_life_days))

def polar_to_offset(direction_deg, distance_km):
    """A deposit's bearing and range from a spot centre as flat x/y in km.

    Only for rows uploaded by the older build, which recorded a bearing and
    a range instead of coordinates. Nothing produces these any more.
    """
    angle = radians(float(direction_deg))
    return (float(distance_km) * sin(angle), float(distance_km) * cos(angle))


def latlon_to_offset(lat, lon, ref_lat, ref_lon, body_radius_m):
    """East/north from a reference point, in km.

    Over the few km a mining site spans, treating the surface as flat is
    accurate to well under a metre, so this is a scaled difference rather
    than anything spherical. The body's radius matters: a degree of
    longitude is 36 km on a small moon and 110 km on a large world, and
    clustering with the wrong scale groups deposits that are nowhere near
    each other.
    """
    metres_per_degree = (2.0 * pi * float(body_radius_m)) / 360.0
    east = (float(lon) - float(ref_lon)) * metres_per_degree * cos(radians(float(ref_lat)))
    north = (float(lat) - float(ref_lat)) * metres_per_degree
    return (east / 1000.0, north / 1000.0)


def _offsets(deposits, body_radius_m=None):
    """Flat x/y in km for each deposit, or None where it cannot be placed.

    Coordinates first, because that is what the app records now. A row with
    only the older bearing/range pair still places, so a database holding
    both kinds still clusters as one.
    """
    ref = None
    if body_radius_m:
        for row in deposits:
            if row.get("lat") not in (None, "") and row.get("lon") not in (None, ""):
                try:
                    ref = (float(row["lat"]), float(row["lon"]))
                    break
                except (TypeError, ValueError):
                    continue

    points = []
    for row in deposits:
        placed = None
        if ref is not None:
            try:
                placed = latlon_to_offset(row["lat"], row["lon"],
                                          ref[0], ref[1], body_radius_m)
            except (KeyError, TypeError, ValueError):
                placed = None
        if placed is None:
            try:
                placed = polar_to_offset(row["direction"], row["distance"])
            except (KeyError, TypeError, ValueError):
                placed = None
        points.append(placed)
    return points


def cluster_deposits(deposits: list[dict], radius_km: float = 0.35,
                     body_radius_m: float | None = None) -> list[list[int]]:
    """Group deposits that sit within radius_km of each other.

    This is the surface equivalent of overlapping ring hotspots: a patch
    where several deposits are close enough to work without moving far.
    Returns lists of indices into the input, largest cluster first.
    """
    points = _offsets(deposits, body_radius_m)

    parent = list(range(len(points)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        a, b = find(i), find(j)
        if a != b:
            parent[b] = a

    for i in range(len(points)):
        if points[i] is None:
            continue
        for j in range(i + 1, len(points)):
            if points[j] is None:
                continue
            dx = points[i][0] - points[j][0]
            dy = points[i][1] - points[j][1]
            if (dx * dx + dy * dy) <= radius_km * radius_km:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(len(points)):
        if points[i] is None:
            continue
        groups.setdefault(find(i), []).append(i)
    return sorted(groups.values(), key=len, reverse=True)


def score_cluster(deposits: list[dict], indices: list[int],
                  body_radius_m: float | None = None) -> dict:
    """Describe one cluster: how many rigs, how many types, how tight."""
    rigs = 0
    types: dict[str, int] = {}
    placed = _offsets(deposits, body_radius_m)
    points = []
    densities = []
    for i in indices:
        row = deposits[i]
        try:
            rigs += int(float(row.get("rigs") or 0))
        except (TypeError, ValueError):
            pass
        name = str(row.get("type") or "").strip()
        if name:
            types[name] = types.get(name, 0) + 1
        rank = density_rank(row.get("density"))
        if rank >= 0:
            densities.append(rank)
        if placed[i] is not None:
            points.append(placed[i])

    spread = 0.0
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            dx = points[i][0] - points[j][0]
            dy = points[i][1] - points[j][1]
            spread = max(spread, sqrt(dx * dx + dy * dy))

    return {
        "deposits": len(indices),
        "rigs": rigs,
        "types": types,
        "distinct_types": len(types),
        "spread_km": round(spread, 3),
        "density": round(sum(densities) / len(densities), 2) if densities else None,
        "best_density": DENSITY_TIERS[max(densities)] if densities else "",
        "indices": list(indices),
    }


def rank_clusters(deposits: list[dict], radius_km: float = 0.35,
                  body_radius_m: float | None = None) -> list[dict]:
    """Best patches first.

    Ordered by rigs you can put down, then by how many different commodities
    are in reach, then by tightness - a patch you can work without driving.
    """
    scored = [score_cluster(deposits, group, body_radius_m)
              for group in cluster_deposits(deposits, radius_km, body_radius_m)]
    return sorted(scored,
                  key=lambda c: (-c["rigs"], -c["distinct_types"],
                                 -(c["density"] if c["density"] is not None else -1),
                                 c["spread_km"]))


def site_score(site: dict, age_days: float = 0.0,
               half_life_days: float = 21.0) -> float:
    """One number for "is this site worth the trip".

    Rigs first, because six rigs down is the whole point of the Rhino.
    Overlap second - several commodities inside one patch is the surface
    equivalent of a triple hotspot, and the reason to prefer one site over
    a richer single-commodity one. Density third. Then the lot is decayed
    by age, because these deposits do not come back quickly.
    """
    try:
        rigs = float(site.get("rigs") or 0)
    except (TypeError, ValueError):
        rigs = 0.0
    try:
        types = float(site.get("distinct_types") or 0)
    except (TypeError, ValueError):
        types = 0.0
    density = site.get("density")
    density = 2.0 if density in (None, "") else float(density)

    # Density deliberately absent, as it is on the community map: its
    # effect is unproven and the observed trend runs inverse, so weighting it
    # ranks on a belief the project's own research does not hold.
    raw = rigs + (types * 2.5)
    return round(raw * freshness_factor(age_days, half_life_days), 3)


def rank_sites(sites: list[dict], now_iso: str = "",
               half_life_days: float = 21.0) -> list[dict]:
    """Best sites first, with staleness already priced in."""
    now = _parse_iso(now_iso) if now_iso else time.time()
    out = []
    for site in sites:
        entry = dict(site)
        seen = _parse_iso(str(site.get("recorded") or site.get("updated") or ""))
        age = max(0.0, (now - seen) / 86400.0) if seen else 0.0
        entry["age_days"] = round(age, 2)
        entry["freshness"] = round(freshness_factor(age, half_life_days), 3)
        entry["score"] = site_score(site, age, half_life_days)
        out.append(entry)
    return sorted(out, key=lambda s: -s["score"])


def _parse_iso(text: str) -> float:
    """Journal and API timestamps to epoch seconds. 0.0 when unreadable."""
    text = (text or "").strip()
    if not text:
        return 0.0
    cleaned = text.replace("Z", "+0000")
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = time.strptime(cleaned, fmt)
        except ValueError:
            continue
        try:
            import calendar
            return calendar.timegm(parsed)
        except Exception:
            return 0.0
    return 0.0
