"""Updates that download themselves, and only install on a click.

What has to hold: a download comes only from radioraxxla.com over HTTPS, is
kept only if it is exactly the file version.json describes, is checked again
at the moment it is run, and is run only by the INSTALL UPDATE button. No
network and no Windows needed - urlopen, Popen and the executable's path are
all replaced with stand-ins that record what was asked of them.
"""
import os, sys, json, hashlib, tempfile, shutil, io, urllib.error
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "stubs"))
import _ctkstub  # noqa
sys.path.insert(0, os.path.dirname(HERE))
TMP = tempfile.mkdtemp(prefix="edsmt-update-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
import edsmt as A, edonline as EDO  # noqa
A.DATA_DIR = os.path.join(TMP, "data"); os.makedirs(A.DATA_DIR, exist_ok=True)
A.SETTINGS_FILE = os.path.join(A.DATA_DIR, "settings.json")

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)

BUILD = b"MZ" + b"new build of EDSMT " * 5000
SHA = hashlib.sha256(BUILD).hexdigest()
GOOD = {"url": "https://radioraxxla.com/EDSMT/EDSMT-Setup.exe?v=1.10099",
        "sha256": SHA, "bytes": len(BUILD)}

print("== version.json's download entries are checked before anything is fetched ==")
check("a sound entry is accepted", EDO.update_package({"installer": GOOD}, "installer") == GOOD)
def bent(**change):
    return EDO.update_package({"installer": dict(GOOD, **change)}, "installer")
check("plain http is refused", bent(url=GOOD["url"].replace("https", "http")) is None)
check("another host is refused", bent(url="https://example.com/EDSMT-Setup.exe") is None)
check("a look-alike host is refused",
      bent(url="https://radioraxxla.com.example.net/EDSMT-Setup.exe") is None)
check("a missing or malformed checksum is refused",
      bent(sha256="") is None and bent(sha256="abc") is None
      and bent(sha256="z" * 64) is None)
check("a size of nothing, or of half a gigabyte, is refused",
      bent(bytes=0) is None and bent(bytes=EDO.UPDATE_MAX_BYTES + 1) is None
      and bent(bytes="lots") is None)
check("no entry at all is simply none", EDO.update_package({}, "portable") is None
      and EDO.update_package(None, "portable") is None)

print("== the check hands the app the packages as well as the words ==")
_real_get = EDO.get_json
_asked = []
def _fake_get(url, timeout=10.0, headers=None):
    _asked.append(url)
    return {"version": "1.10099", "url": "https://radioraxxla.com/EDSMT/",
            "headline": "Where to land", "installer": GOOD,
            "portable": dict(GOOD, url="https://evil.example/EDSMT.exe")}
EDO.get_json = _fake_get
answer = json.loads(EDO.UpdateCheck._look("1.10028", EDO.VERSION_URL))
check("a newer build comes back as JSON with its version",
      answer["version"] == "1.10099" and "1.10099 is out" in answer["message"], answer)
check("the sound package is passed on", answer["installer"] == GOOD)
check("the one pointing elsewhere is dropped, not passed on", answer["portable"] is None)
check("the check dodges a stale cached version.json",
      _asked and _asked[-1].startswith(EDO.VERSION_URL + "?t="), _asked[-1:])
check("up to date is still an empty answer", EDO.UpdateCheck._look("1.10099", EDO.VERSION_URL) == "")
EDO.get_json = _real_get

print("== a download is kept only if it is exactly the promised file ==")
class _Resp:
    def __init__(self, body, final):
        self.body, self.final, self.at = body, final, 0
    def geturl(self): return self.final
    def read(self, n=-1):
        chunk = self.body[self.at:self.at + (n if n > 0 else len(self.body))]
        self.at += len(chunk); return chunk
    def __enter__(self): return self
    def __exit__(self, *a): return False
_served = {"body": BUILD, "final": GOOD["url"], "calls": 0}
def _fake_open(request, timeout=None):
    _served["calls"] += 1
    if _served.get("fail"):
        raise urllib.error.URLError("no route")
    return _Resp(_served["body"], _served["final"])
_real_open = EDO.urllib.request.urlopen
EDO.urllib.request.urlopen = _fake_open
DL = os.path.join(TMP, "dl")
dest = os.path.join(DL, "EDSMT-Setup-1.10099.exe")
seen = []
got = EDO.download_verified(GOOD["url"], dest, SHA, len(BUILD),
                            progress=lambda a, b: seen.append((a, b)))
check("the right file is kept under its final name",
      got == dest and open(dest, "rb").read() == BUILD)
check("and no .part is left behind", not os.path.exists(dest + ".part"))
check("progress was reported as it came in, ending at the full size",
      seen and seen[-1] == (len(BUILD), len(BUILD)), seen[-1:])
calls = _served["calls"]
EDO.download_verified(GOOD["url"], dest, SHA, len(BUILD))
check("a file already downloaded and checked is not fetched again", _served["calls"] == calls)

def refused(body=BUILD, final=GOOD["url"], sha=SHA, size=len(BUILD), url=GOOD["url"], fail=False):
    _served.update(body=body, final=final, fail=fail)
    target = os.path.join(DL, "try.exe")
    try:
        EDO.download_verified(url, target, sha, size)
        return "kept", os.path.exists(target)
    except Exception as exc:
        return str(exc), os.path.exists(target) or os.path.exists(target + ".part")
_why, _left = refused(body=BUILD[:-1] + b"X")
check("one byte different: thrown away, nothing left", "checksum" in _why and not _left, _why)
_why, _left = refused(body=BUILD[: len(BUILD) // 2])
check("cut short: said so, nothing left", "short" in _why and not _left, _why)
_why, _left = refused(body=BUILD + b"extra")
check("longer than promised: stopped, nothing left", "bigger" in _why and not _left, _why)
_why, _left = refused(final="https://elsewhere.example/x.exe")
check("redirected off the website: refused, nothing left", "redirected" in _why and not _left, _why)
_why, _left = refused(url="https://elsewhere.example/x.exe")
check("asked for another host directly: refused before connecting", "refused" in _why and not _left, _why)
_why, _left = refused(fail=True)
check("no connection: said so, nothing left", "could not reach" in _why and not _left, _why)
_served.update(body=BUILD, final=GOOD["url"], fail=False)
EDO.urllib.request.urlopen = _real_open

print("== the app: fetch on its own, install only on the click ==")
class _Button:
    def __init__(self): self.text, self.state, self.mapped = "UPDATE AVAILABLE", "normal", False
    def configure(self, **kw):
        self.text = kw.get("text", self.text); self.state = kw.get("state", self.state)
    def winfo_ismapped(self): return self.mapped
    def pack(self, **kw): self.mapped = True
class _Updates:
    def __init__(self): self.asked, self.progress = [], None
    def download(self, package, dest, version):
        self.asked.append((package, dest, version)); return True
def probe(kind="installed", auto=True):
    app = A.EDSMT.__new__(A.EDSMT)
    app.said = []
    app.say = lambda t, c=None: app.said.append(t)
    app.btn_update = _Button()
    app.settings = dict(A.DEFAULT_SETTINGS, auto_download_updates=auto)
    app.updates = _Updates()
    app.update_info = app.update_package = app.update_ready = None
    app._update_fetching = False
    app.closed = []
    app.on_close = lambda: app.closed.append(True)
    app._save_on_exit = lambda: app.closed.append("saved")
    app.open_download_page = lambda: app.said.append("PAGE")
    A.build_kind = lambda: kind
    return app
_real_kind = A.build_kind
NEWER = json.dumps({"version": "1.10099", "message": "EDSMT 1.10099 is out.",
                    "installer": GOOD, "portable": None})
app = probe()
app.announce_update(NEWER)
check("a newer build starts downloading by itself", len(app.updates.asked) == 1)
check("into the data folder's updates, named for its version",
      app.updates.asked[0][1] == os.path.join(A.updates_folder(), "EDSMT-Setup-1.10099.exe"),
      app.updates.asked[0][1])
check("the button says so and cannot be pressed meanwhile",
      app.btn_update.text.startswith("DOWNLOADING") and app.btn_update.state == "disabled")
app.announce_update(NEWER)
check("a second announcement does not start a second download", len(app.updates.asked) == 1)
app.updates.progress = (512, 1024); app.follow_update()
check("the button counts the download up", app.btn_update.text == "DOWNLOADING 50%", app.btn_update.text)
check("nothing is installed while it downloads", not app.closed)

off = probe(auto=False)
off.announce_update(NEWER)
check("with the setting off nothing is fetched until asked",
      not off.updates.asked and off.btn_update.text == "UPDATE AVAILABLE")
off.update_button_pressed()
check("and the button fetches it rather than opening the website",
      len(off.updates.asked) == 1 and "PAGE" not in off.said)
src_only = probe(kind="")
src_only.announce_update(NEWER)
check("running from source it never downloads a Windows build",
      not src_only.updates.asked)
src_only.update_button_pressed()
check("and the button falls back to the download page", "PAGE" in src_only.said)
no_pkg = probe(kind="portable")
no_pkg.announce_update(NEWER)
check("no package for this kind of build: the page, not a guess",
      not no_pkg.updates.asked and (no_pkg.update_button_pressed(), "PAGE" in no_pkg.said)[1])
old_style = probe()
old_style.announce_update("EDSMT 1.10099 is out. Get it at the website")
check("a plain-words answer is still shown, not dropped",
      old_style.said and "1.10099 is out" in old_style.said[0])

app.update_downloaded(False, "the download did not match its checksum")
check("a refused download says why and offers again",
      "checksum" in app.said[-1] and app.btn_update.text == "UPDATE AVAILABLE"
      and app.btn_update.state == "normal" and not app._update_fetching)
os.makedirs(A.updates_folder(), exist_ok=True)
SETUP = os.path.join(A.updates_folder(), "EDSMT-Setup-1.10099.exe")
with open(SETUP, "wb") as fh:
    fh.write(BUILD)
app.update_downloaded(True, json.dumps({"path": SETUP, "version": "1.10099", "sha256": SHA}))
check("a checked download turns the button into INSTALL UPDATE",
      app.btn_update.text == "INSTALL UPDATE" and app.btn_update.state == "normal")
check("and the line says it closes, updates and reopens",
      "INSTALL UPDATE" in app.said[-1] and "opens again" in app.said[-1], app.said[-1])
check("still nothing has been run", not app.closed)

import subprocess
_launched = []
_real_popen = subprocess.Popen
subprocess.Popen = lambda cmd, **kw: _launched.append((cmd, kw)) or object()
_released = []
_real_release, _real_claim = A.release_single_instance, A.claim_single_instance
A.release_single_instance = lambda: _released.append(True)
A.claim_single_instance = lambda: _released.append("claimed") or True

with open(SETUP, "r+b") as fh:
    fh.seek(10); fh.write(b"!")
app.update_button_pressed()
check("a file changed after it was checked is NOT run",
      not _launched and not app.closed, _launched)
check("it is fetched again instead", len(app.updates.asked) >= 2 and app.update_ready is None)
with open(SETUP, "wb") as fh:
    fh.write(BUILD)
app._update_fetching = False
app.update_downloaded(True, json.dumps({"path": SETUP, "version": "1.10099", "sha256": SHA}))
app.update_button_pressed()
check("the click runs Setup, quietly, over the same install",
      _launched and _launched[0][0][0] == SETUP and "/SILENT" in _launched[0][0]
      and "/SP-" in _launched[0][0], _launched)
check("everything is saved, the one-copy lock let go, then the app closes - in that order",
      app.closed == ["saved", True] and _released == [True], (app.closed, _released))

_launched.clear(); _released.clear()
bad = probe()
bad.update_ready = {"path": SETUP, "version": "1.10099", "sha256": SHA}
subprocess.Popen = lambda cmd, **kw: (_ for _ in ()).throw(OSError("blocked"))
bad.install_update()
check("if Setup cannot start, the app stays open and takes its lock back",
      True not in bad.closed and _released == [True, "claimed"] and "blocked" in bad.said[-1],
      (bad.closed, _released, bad.said[-1:]))
subprocess.Popen = lambda cmd, **kw: _launched.append((cmd, kw)) or object()

print("== the portable build swaps itself, and can never be left with no exe ==")
PORT = os.path.join(TMP, "portable"); os.makedirs(PORT)
EXE = os.path.join(PORT, "EDSMT.exe")
with open(EXE, "wb") as fh:
    fh.write(b"old build")
NEW = os.path.join(A.updates_folder(), "EDSMT-1.10099.exe")
with open(NEW, "wb") as fh:
    fh.write(BUILD)
_real_exe = sys.executable
sys.executable = EXE
check("the swap puts the new build where the old one was",
      A.EDSMT._swap_portable(NEW) == EXE and open(EXE, "rb").read() == BUILD)
check("and the old one is kept aside, to be tidied next start",
      open(EXE + ".old", "rb").read() == b"old build")
os.remove(EXE + ".old")
with open(EXE, "wb") as fh:
    fh.write(b"old build")
_real_copy = shutil.copy2
shutil.copy2 = lambda a, b: (_ for _ in ()).throw(OSError("disk full"))
try:
    A.EDSMT._swap_portable(NEW)
    _raised = False
except OSError:
    _raised = True
shutil.copy2 = _real_copy
check("a copy that fails puts the old exe straight back",
      _raised and open(EXE, "rb").read() == b"old build" and not os.path.exists(EXE + ".old"))
port = probe(kind="portable")
port.update_ready = {"path": NEW, "version": "1.10099", "sha256": SHA}
_launched.clear(); _released.clear()
port.install_update()
check("the click starts the new portable exe, from where the old one was",
      _launched and _launched[0][0] == [EXE] and open(EXE, "rb").read() == BUILD, _launched)

print("== the next start tidies up ==")
A.sys.frozen = True
SAME, OLDER, NEWER_NAME = ("EDSMT-Setup-%s.exe" % A.APP_VERSION, "EDSMT-1.1.exe.part",
                           "EDSMT-Setup-99.1.exe")
for name in (SAME, OLDER, NEWER_NAME):
    with open(os.path.join(A.updates_folder(), name), "wb") as fh:
        fh.write(b"x")
with open(EXE + ".old", "wb") as fh:
    fh.write(b"old")
A.tidy_after_update()
left = sorted(os.listdir(A.updates_folder()))
check("the renamed-aside exe is removed", not os.path.exists(EXE + ".old"))
check("downloads for this version or older are removed, a newer one is kept",
      SAME not in left and OLDER not in left and NEWER_NAME in left, left)

print("== which build this is ==")
A.build_kind = _real_kind
FOLDER = os.path.join(TMP, "installed"); os.makedirs(os.path.join(FOLDER, "_internal"))
sys.executable = os.path.join(FOLDER, "EDSMT.exe")
check("a folder build nobody installed is not updated in place", A.build_kind() == "")
open(os.path.join(FOLDER, "unins000.exe"), "wb").close()
check("with Setup's uninstaller beside it, it is the installed build", A.build_kind() == "installed")
sys.executable = EXE
check("a single exe with no _internal is the portable build", A.build_kind() == "portable")
del A.sys.frozen
check("running from source is neither", A.build_kind() == "")

sys.executable = _real_exe
subprocess.Popen = _real_popen
A.release_single_instance, A.claim_single_instance = _real_release, _real_claim

print("== the build publishes the checksums, in the right order ==")
REPO = os.path.dirname(HERE)
site = io.open(os.path.join(REPO, "build", "site.py"), encoding="utf-8").read()
check("site.py writes a sha256 and a size for each download",
      '"sha256"' in site and '"bytes"' in site and "EDSMT-Setup.exe" in site)
bat = io.open(os.path.join(REPO, "BUILD.bat"), encoding="utf-8").read()
check("BUILD.bat builds the installer BEFORE writing version.json",
      bat.index('build\\installer.iss"') < bat.index("build\\site.py"))
check("and says to upload version.json last", "version.json LAST" in bat)
ci = io.open(os.path.join(REPO, ".github", "workflows", "build.yml"), encoding="utf-8").read()
check("CI writes version.json after both downloads exist",
      ci.index("installer.iss") < ci.index("build/site.py")
      and ci.index("dist\\EDSMT.exe upload") < ci.index("build/site.py"))
iss = io.open(os.path.join(REPO, "build", "installer.iss"), encoding="utf-8").read()
_relaunch = [l for l in iss.splitlines() if "skipifnotsilent" in l]
check("a silent update opens EDSMT again afterwards", len(_relaunch) == 1, _relaunch)
check("as the user, not with Setup's admin rights",
      _relaunch and "runasoriginaluser" in _relaunch[0], _relaunch)

shutil.rmtree(TMP, ignore_errors=True)
print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
