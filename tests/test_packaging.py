"""The bundle itself: the checks that used to be done by eye before a release.

Every one of these is here because it went wrong once, and by definition none
of them are caught by testing the app's logic:

  * a stub that imported matplotlib, so the suite passed on a machine that
    happened to have it and died on a clean build box
  * batch files written with Unix line endings, where `goto` silently stops
    working
  * `echo  EDSMT.exe <-- the download` in a .bat, where cmd reads the `<` as
    a redirection and prints "The system cannot find the file specified"
  * a version bumped in four places out of five
  * files named in the README that do not exist
  * functions written, never wired to anything, and shipped anyway
"""
import ast, io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

fails = []
def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"   <-- {extra}"))
    if not cond: fails.append(label)

def read(*parts):
    return io.open(os.path.join(REPO, *parts), encoding="utf-8",
                   errors="replace").read()

SHIPPED = ["edsmt.py", "survey.py", "planview.py", "journal.py", "overlay.py",
           "edonline.py"]

print("== the batch files run on Windows ==")
for name in ("BUILD.bat", "RUN.bat"):
    raw = io.open(os.path.join(REPO, name), "rb").read()
    crlf, lf = raw.count(b"\r\n"), raw.count(b"\n")
    check("%s uses CRLF throughout" % name, crlf == lf and crlf > 0,
          "%d CRLF of %d lines" % (crlf, lf))
    # An unescaped < > | or & in an echo is read by cmd as redirection or
    # chaining, not as text.
    bad = []
    for number, line in enumerate(raw.decode("ascii", "replace").splitlines(), 1):
        stripped = line.strip()
        if not stripped.lower().startswith("echo"):
            continue
        for index, char in enumerate(stripped):
            if char in "<>|&" and (index == 0 or stripped[index - 1] != "^"):
                bad.append("%s:%d %s" % (name, number, stripped[:60]))
                break
    check("%s escapes every < > | and & it prints" % name, not bad, bad)

print("== the test stub needs nothing that is not installed ==")
stub = read("tests", "stubs", "_ctkstub.py")
installed = read("requirements.txt")
for library in ("matplotlib", "numpy", "pandas", "scipy"):
    check("the stub does not import %s" % library,
          not re.search(r"^\s*import\s+%s\b" % library, stub, re.M), library)
    check("and %s is not a dependency either" % library,
          library not in installed)

print("== versions agree everywhere ==")
found = {}
def version(path, pattern, label):
    text = read(*path.split("/"))
    m = re.search(pattern, text)
    if not m:
        fails.append("no version in " + path)
        print("  FAIL  a version could be read from %s" % path)
        return
    found.setdefault(m.group(1).replace(",", "."), []).append(label)
version("build/installer.iss", r'#define AppVersion "([\d.]+)"', "installer.iss")
version("build/installer.iss", r'VersionInfoVersion=([\d.]+)', "installer.iss VersionInfo")
version("build/version_info.txt", r"filevers=\((\d+,\d+,\d+,\d+)\)", "version_info filevers")
version("build/version_info.txt", r"'FileVersion', '([\d.]+)'", "version_info FileVersion")
version("edonline.py", r'APP_VERSION\s*=\s*"([\d.]+)"', "edonline")
version("server/main.py", r'APP_VERSION\s*=\s*"([\d.]+)"', "server")
def _norm(v):
    # Strip trailing zero COMPONENTS, not trailing zero characters. A plain
    # rstrip(".0") turns 1.10010 into 1.1001 and then reports drift that is
    # not there - and would do it only on versions ending in a zero, which
    # is the kind of bug that waits months to appear.
    parts = v.split(".")
    while len(parts) > 2 and parts[-1] == "0":
        parts.pop()
    return ".".join(parts)
same = {_norm(v) for v in found}
check("one version across the app, the installer and the API",
      len(same) == 1, found)

print("== both build specs are actually used ==")
build = read("BUILD.bat")
for spec in ("EDSMT.spec", "EDSMT-onefile.spec"):
    check("BUILD.bat builds %s" % spec, spec in build)
    check("%s exists" % spec, os.path.exists(os.path.join(REPO, "build", spec)))
check("the installer packages the folder build, not the onefile",
      "dist\\EDSMT\\*" in read("build", "installer.iss"))

print("== nothing shipped is dead or unused ==")
everything = ""
for dirpath, dirs, files in os.walk(REPO):
    dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "dist",
                                            "upload", ".venv", ".venv-build")]
    for name in files:
        if name.endswith((".py", ".bat", ".iss", ".spec", ".yml", ".md")):
            everything += io.open(os.path.join(dirpath, name), encoding="utf-8",
                                  errors="replace").read()

unused_imports, orphans = [], []
for name in SHIPPED + ["server/main.py"]:
    source = read(*name.split("/"))
    tree = ast.parse(source)
    for node in ast.walk(tree):
        imported = []
        if isinstance(node, ast.Import):
            imported = [(a.asname or a.name.split(".")[0], node.lineno)
                        for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
            imported = [(a.asname or a.name, node.lineno) for a in node.names]
        for alias, line in imported:
            if len(re.findall(r"\b%s\b" % re.escape(alias), source)) <= 1:
                unused_imports.append("%s:%d %s" % (name, line, alias))
    if name in SHIPPED:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                if len(re.findall(r"\b%s\b" % re.escape(node.name), everything)) <= 1:
                    orphans.append("%s:%d %s()" % (name, node.lineno, node.name))
check("no unused imports", not unused_imports, unused_imports)
check("nothing is written and then never wired up", not orphans, orphans)

print("== the docs do not describe features that were taken out ==")
# The sweep and the clock were removed from the deposit card on request
# ("get rid of that its bs"). The README went on describing both for a
# release. A doc that promises something the app does not do reads, to a
# commander, exactly like the app being broken.
_PLAYER_FACING = ("README.md", "CHANGELOG.md", "site/edsmt.html")
_GONE = ("sweep", "sweeping")
_stale = []
for _doc in _PLAYER_FACING:
    _path = os.path.join(REPO, *_doc.split("/"))
    if not os.path.exists(_path):
        continue
    _text = read(*_doc.split("/")).lower()
    for _word in _GONE:
        if re.search(r"\b%s\b" % _word, _text):
            _stale.append("%s: %s" % (_doc, _word))
check("nothing player-facing still promises the scan sweep", not _stale, _stale)
check("and the overlay really has no sweep left to promise",
      "def sweep_wedge" not in read("overlay.py")
      and "SWEEP" not in read("overlay.py"))

print("== the docs do not name files that are not there ==")
missing = []
KNOWN_OUTPUT = {
    "EDSMT.exe", "EDSMT-Setup.exe", "EDSMT-source.zip", "deposits.csv",
    "locations.csv", "settings.json", "journal-mining-events.log",
    "crash.log", "Market.json", "Status.json", "portable.txt", "index.html",
    "is.exe", "innosetup.exe", "main.py", "01.log", "www.py",
}
def prose_only(text):
    """Strip command blocks before looking for filenames.

    A deployment doc names plenty of paths that are not in this bundle and
    never should be - a proxy's own config file lives on a
    server. Those are always inside a command block. Prose naming a file is
    the case worth checking, because that is where a doc claims the bundle
    contains something it does not.
    """
    out, fenced = [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if fenced or line.startswith("    ") or line.startswith("\t"):
            continue
        out.append(line)
    return "\n".join(out)


for doc in ("README.md", "JOURNAL-NOTES.md", "server/DEPLOY.md"):
    text = prose_only(read(*doc.split("/")))
    # The leading dot matters: ".github/workflows/build.yml" is a real path
    # and dropping the dot makes a present file look missing.
    for m in re.finditer(r"(\.?[A-Za-z0-9_\-]+(?:[\\/][A-Za-z0-9_\-]+)*"
                         r"\.(?:py|bat|iss|spec|ico|yml|sh|conf))", text):
        named = m.group(1).replace("\\", "/")
        if named.rsplit("/", 1)[-1] in KNOWN_OUTPUT or named.startswith(("http", "%")):
            continue
        candidates = [named, "build/" + named, "tests/" + named,
                      "server/" + named, ".github/workflows/" + named,
                      named.split("/")[-1], "server/" + named.split("/")[-1]]
        if not any(os.path.exists(os.path.join(REPO, c)) for c in candidates):
            missing.append("%s names %s" % (doc, named))
check("every file the docs name exists", not missing, missing)

print("== the source zip is source, not a build ==")
# EDSMT-source.zip shipped at 25 MB once, because PyInstaller's scratch tree
# lives in build\\work and the exclusion list in BUILD.bat only ever sees
# top-level names. GPL-3.0 asks for the source; nobody needs 20 MB of
# unpacked Qt and numpy back again.
bat = read("BUILD.bat")
zip_at = bat.find("Compress-Archive")
check("the source zip is built at all", zip_at > 0)
before = bat[:zip_at]
check("PyInstaller's scratch tree is cleared before the zip is made",
      re.search(r'rmdir /s /q "build.work"', before) is not None)
check("and so are the __pycache__ folders",
      "__pycache__) do if exist" in before)
check("the workpath the specs are built into is the one that gets cleared",
      "--workpath build\\work" in bat)
check("the build workflow is offered as source, since the README names it",
      "'.github'" not in bat[zip_at:zip_at + 400], "still excluded from the zip")

print("== the container is handed every setting the API reads ==")
# RR_STAFF was read by main.py and never passed through docker-compose.yml,
# so the verify endpoint could not have worked on a real deployment however
# carefully the .env was filled in. Nothing failed; verification simply
# rejected everyone, quietly, forever. Env vars are wiring like any other.
api_src = read("server", "main.py")
compose = read("server", "docker-compose.yml")
wanted = sorted({m for m in re.findall(r'os\.environ\.get\(\s*"(RR_[A-Z_]+)"', api_src)}
                - {"RR_DB"})
unpassed = [name for name in wanted if name + ":" not in compose]
check("every RR_ setting main.py reads is passed to the container",
      not unpassed, unpassed)
check("and the compose file names the port the host binds",
      "RR_HOST_PORT" in compose)

print("== the server scripts agree with the compose file ==")
# verify.sh defaulted to 8080 - the port inside the container - while the
# host binds 9110, so the one command whose whole job is proving the API
# works connected to nothing and reported failure on a healthy service.
vsh = read("server", "verify.sh")
port = re.search(r"RR_HOST_PORT:-(\d+)", compose)
check("the compose file has a default host port", port is not None)
check("verify.sh defaults to that same port",
      port is not None and ("RR_HOST_PORT:-%s" % port.group(1)) in vsh,
      re.findall(r"127\.0\.0\.1:[^\"}]*", vsh))
check("nothing in the server scripts still points at the in-container port",
      "127.0.0.1:8080" not in vsh)

print("== an update replaces the old version and keeps the finds ==")
# The failure this guards against is silent: install 1.2 over 1.1 and a
# stale .pyd left behind in _internal gets loaded in preference to nothing,
# producing a crash that makes no sense against the current source.
iss = read("build", "installer.iss")
check("the AppId is a fixed GUID, so Windows replaces rather than duplicates",
      re.search(r"^AppId=\{\{[0-9A-F-]{36}\}", iss, re.M) is not None)
check("it installs back into the folder it is already in",
      "UsePreviousAppDir=yes" in iss)
check("the running app is closed before its DLLs are replaced",
      "CloseApplications=yes" in iss)
check("the previous build's runtime is cleared first",
      re.search(r"^\[InstallDelete\]", iss, re.M) is not None
      and "_internal" in iss.split("[InstallDelete]")[1].split("[")[0])
# Only the Name: directives matter here - a comment mentioning the data
# folder is documentation, a delete rule naming it is a lost survey.
delete_targets = [line for line in iss.splitlines()
                  if line.strip().lower().startswith("type:")
                  and "name:" in line.lower()]
check("no delete rule points anywhere near the finds",
      not [t for t in delete_targets
           if "localappdata" in t.lower() or "radioraxxla" in t.lower()],
      delete_targets)
check("the only thing cleared is the program's own runtime",
      all("{app}" in t for t in delete_targets), delete_targets)
check("the app files overwrite regardless of timestamp",
      "ignoreversion" in iss)

print("== the version can be moved on in one command ==")
# Six version fields across four files. Every release that edited five of
# them shipped a build reporting the wrong number somewhere.
check("build/bump.py exists", os.path.exists(os.path.join(REPO, "build", "bump.py")))
bump = read("build", "bump.py")
for path in ("edonline.py", "server/main.py", "build/installer.iss",
             "build/version_info.txt"):
    check("bump.py covers %s" % path, '"%s"' % path in bump)
check("bump.py refuses a number Windows cannot store", "65535" in bump)
# Not the README. That one ships inside the installer, and a commander who
# downloaded a mining tool has no use for a version-bump script - which is
# the whole reason the contributor material was moved out of it.
check("the contributor guide tells people to run it",
      "bump.py" in read("CONTRIBUTING.md"))
check("and the shipped README does not mention it at all",
      "bump.py" not in read("README.md"))

print("== the app fetches a new build, and runs it only when asked ==")
# A tool nobody knows has updated is a tool nobody updates, and one that
# sends everybody to a website to fetch it by hand is one most people leave
# alone. So a new build downloads by itself - under rules that keep it from
# ever being something else: radioraxxla.com over HTTPS only, the exact
# SHA-256 published in version.json, checked again at the moment it is run,
# and run only by the INSTALL UPDATE button. tests/test_update.py drives all
# of that; these lines keep the shape of it from being quietly undone.
site_py = read("build", "site.py")
check("build/site.py writes the version file", "version.json" in site_py)
check("BUILD.bat ships it to the website", "version.json" in read("BUILD.bat"))
online = read("edonline.py")
check("the app knows where to look", "VERSION_URL" in online)
check("versions are compared as numbers, not strings",
      "def version_tuple" in online and "def is_newer" in online)
app_src = read("edsmt.py")
check("the check runs on launch", "updates.check(APP_VERSION)" in app_src)
check("nothing anywhere uses the unchecked urlretrieve",
      "urlretrieve" not in app_src and "urlretrieve" not in online)
check("downloads are allowed from the website's own hosts only",
      'UPDATE_HOSTS = ("radioraxxla.com", "www.radioraxxla.com")' in online)
check("and every download is checked against its SHA-256 before it is kept",
      "digest.hexdigest() != sha256" in online.split("def download_verified")[1])
install = app_src.split("    def install_update(self):")[1].split("\n    def ")[0]
check("and again at the moment it is run",
      "EDO.sha256_of(path) == digest" in install)
check("the only thing that runs a download is install_update",
      app_src.count("subprocess.Popen(command") == 1
      and "subprocess.Popen(command" in install)
check("and install_update is reached from the button alone",
      app_src.count("self.install_update()") == 1
      and "return self.install_update()" in
      app_src.split("    def update_button_pressed(self):")[1].split("\n    def ")[0])
page = app_src.split("def open_download_page")[1].split("\n    def ")[0]
check("with no usable download, the button still just opens the web page",
      "webbrowser.open" in page and "radioraxxla.com/EDSMT/" in page
      and not any(bad in page for bad in ("startfile", "Popen", ".exe")))

print("== the licence the installer needs is present ==")
check("LICENSE is in the bundle", os.path.exists(os.path.join(REPO, "LICENSE")))
check("and the installer points at it", "LicenseFile" in read("build", "installer.iss"))

print("== nothing that ships carries an address, a key or a database ==")
# A server's real address in a public file lets anyone walk straight past whatever
# sits in front of the server. A four-part game version is the same shape as
# an address, so versions are excluded by pattern rather than by guessing.
_V4 = re.compile(r"(?<![\d.])((?:\d{1,3}\.){3}\d{1,3})(?![\d.])")
_V6 = re.compile(r"\b(?:[0-9a-f]{1,4}:){2,}[0-9a-f]{0,4}\b", re.I)
_VERSIONISH = re.compile(r"^(?:[0-9]|[12][0-9]|3[01])\.\d{1,2}\.\d+\.\d+$")

def _is_private(ip):
    if _VERSIONISH.match(ip):
        return True
    try:
        a, b = (int(x) for x in ip.split(".")[:2])
    except ValueError:
        return True
    return (a in (0, 10, 127) or (a == 192 and b == 168)
            or (a == 172 and 16 <= b <= 31) or a == 255 or a > 255)

# Everything that ships: the whole repo except the internal folder and the
# build's scratch.
_NOT_SHIPPED = {".git", "__pycache__", "dist", "upload", ".venv",
                ".venv-build", "node_modules", "internal", "work"}
PUBLIC_FILES = []
for _dp, _ds, _fs in os.walk(REPO):
    _ds[:] = [d for d in _ds if d not in _NOT_SHIPPED]
    for _f in _fs:
        if _f.endswith((".md", ".py", ".yml", ".yaml", ".sh", ".bat", ".conf",
                        ".html", ".iss", ".json", ".txt", ".spec", ".cfg")) \
                or _f in ("Dockerfile", "LICENSE", ".gitignore"):
            PUBLIC_FILES.append(os.path.join(_dp, _f))

_leaks, _secrets = [], []
for _path in PUBLIC_FILES:
    _rel = os.path.relpath(_path, REPO)
    _text = io.open(_path, encoding="utf-8", errors="replace").read()
    for _m in _V4.finditer(_text):
        if not _is_private(_m.group(1)):
            _leaks.append("%s: %s" % (_rel, _m.group(1)))
    for _m in _V6.finditer(_text):
        _hit = _m.group(0)
        if any(_c in "abcdef" for _c in _hit.lower()) \
                and not _hit.lower().startswith(("fe80", "ff02")):
            _leaks.append("%s: %s" % (_rel, _hit))
    for _pat, _what in (
            (r"RR_STAFF\s*=\s*[A-Za-z][^$<\n]*:[A-Za-z0-9]{8,}", "a staff token"),
            (r"RR_WRITE_TOKEN\s*=\s*[A-Za-z0-9]{8,}", "a write token"),
            (r"Bearer\s+[A-Za-z0-9]{16,}", "a bearer token")):
        if re.search(_pat, _text):
            _secrets.append("%s: %s" % (_rel, _what))
check("no public address is written into anything that ships",
      not _leaks, _leaks[:8])
check("no real token is written into anything that ships", not _secrets, _secrets)
check("there is no .env in the bundle",
      not os.path.exists(os.path.join(REPO, ".env"))
      and not os.path.exists(os.path.join(REPO, "server", ".env")))
check("and .gitignore keeps one out", ".env" in read(".gitignore"))
check("no database is in the bundle either",
      not [_f for _f in os.listdir(REPO) if _f.endswith(".db")])

print("== nothing public contains a private term ==")
# The list of what must never appear - the machine, the services beside the
# API, other people's tools - is itself private, so it lives in
# internal/LEAK-TERMS.txt and this reads it when it is there. On the machine
# that builds a release it always is. Anywhere else it says so, out loud.
# The private folder: EDSMT-Private beside this project, or the older
# internal/ inside it.
_terms_file = next((f for f in (os.path.join(REPO, "internal", "LEAK-TERMS.txt"),
                                os.path.join(os.path.dirname(REPO), "EDSMT-Private",
                                             "LEAK-TERMS.txt"))
                    if os.path.exists(f)), "")
if _terms_file:
    _terms = [l.strip().lower() for l in io.open(_terms_file, encoding="utf-8")
              if l.strip() and not l.lstrip().startswith("#")]
    _hits = []
    for _path in PUBLIC_FILES:
        _rel = os.path.relpath(_path, REPO)
        _low = io.open(_path, encoding="utf-8", errors="replace").read().lower()
        for _t in _terms:
            _pat = (r"\b%s\b" % re.escape(_t)) if re.fullmatch(r"[a-z]+", _t) \
                else re.escape(_t)
            if re.search(_pat, _low):
                _hits.append("%s: %s" % (_rel, _t))
    check("no public file contains any of the %d private terms" % len(_terms),
          not _hits, _hits[:12])
else:
    print("  SKIP  the private folder (EDSMT-Private) is not beside this one, "
          "so the private-term scan cannot run")

print("== nothing player-facing talks about how the server is run ==")
# README and the patch notes ship inside the installer and go on the website.
_INFRA = ("nginx", "docker",
          "/opt/", "/var/www", "proxy host", "waf", "rate-limit zone",
          "limit_req", "letsencrypt", "crontab", "ssh", "putty", "winscp",
          "rr_staff", "rr_write_token", "deposits.db", "sqlite", "origin")
_INSIDE_BASEBALL = ("assertion", "mutation test", "compacted", "transcript",
                    "subagent", "on the record", "i wrote", "runbook",
                    "devlog", "test suite")
_PLAYER = ["CHANGELOG.md", "README.md", "site/index.html", "site/edsmt.html",
           "JOURNAL-NOTES.md"]
_leaky, _cringe = [], []
for _f in _PLAYER:
    _path = os.path.join(REPO, _f)
    if not os.path.exists(_path):
        continue
    _low = io.open(_path, encoding="utf-8").read().lower()
    for _term in _INFRA:
        if re.search(r"(?<![a-z])%s(?![a-z])" % re.escape(_term), _low):
            _leaky.append("%s: %s" % (_f, _term))
    if _f in ("CHANGELOG.md", "README.md"):
        _cringe += ["%s: %s" % (_f, t) for t in _INSIDE_BASEBALL if t in _low]
check("no player-facing file names the infrastructure", not _leaky, _leaky[:8])
check("and none of them reads like a build log", not _cringe, _cringe)

print("== internal documents never ship ==")
_build = read("BUILD.bat")
_gi = read(".gitignore")
check("the source zip leaves out the internal folder",
      "'internal'" in _build, "it would ship to every downloader")
check(".gitignore keeps the internal folder out of the public repo",
      re.search(r"^/?internal/?$", _gi, re.M) is not None)
_stray = [f for f in ("RUNBOOK.md", "DEVLOG.md", "DECISIONS.md", "BACKLOG.md",
                      "UPDATE-GUIDE.md", "LEAK-TERMS.txt")
          if os.path.exists(os.path.join(REPO, f))]
check("no internal document is lying at the top of the repo", not _stray, _stray)
check("the site generator publishes the patch notes, not the devlog",
      "DEVLOG" not in read("build", "site.py"))
check("the shipped bytecode carries no docstrings - both builds",
      all("optimize=2" in read("build", s) for s in ("EDSMT.spec", "EDSMT-onefile.spec")))
check("and the PyInstaller that understands that is the one installed",
      '"pyinstaller>=6.0,<7"' in read("BUILD.bat")
      and '"pyinstaller>=6.0,<7"' in read(".github", "workflows", "build.yml"))
_iss_files = [l for l in read("build", "installer.iss").splitlines()
              if l.startswith("Source:")]
check("the installer puts only the program, README and LICENCE on a PC",
      len(_iss_files) == 3 and all(("dist" in l or "README.md" in l or "LICENSE" in l)
                                   for l in _iss_files), _iss_files)
check("and an update removes the developer notes an older one left behind",
      'Name: "{app}\\JOURNAL-NOTES.md"' in read("build", "installer.iss"))
check("the installer carries only the player's documents",
      not [d for d in ("RUNBOOK", "DEVLOG", "DECISIONS", "BACKLOG", "CONTRIBUTING",
                       "DEPLOY") if d in read("build", "installer.iss")])

print("== the public deploy guide describes any box, not one box ==")
_dep = read("server", "DEPLOY.md")
check("the public API hostname is named, because every copy connects to it",
      "api.radioraxxla.com" in _dep)
check("and the guide says up front its names are examples",
      "is an example" in _dep[:900])
_compose = read("server", "docker-compose.yml")
_services = set(re.findall(r"^  ([a-z0-9][a-z0-9_-]*):$", _compose, re.M))
_cname = re.search(r"container_name:\s*(\S+)", _compose)
check("the compose service and container agree",
      _cname and _cname.group(1) in _services, (_cname and _cname.group(1), _services))
_wrong = []
for _f in ("server/DEPLOY.md", "README.md", "CONTRIBUTING.md"):
    for _line in read(*_f.split("/")).split("\n"):
        _cmd = _line.strip().lstrip("$ ")
        _m = re.match(r"docker compose (?:exec|run)\s+(?:-\S+\s+)*([a-z][a-z0-9_-]*)", _cmd)
        if _m and _m.group(1) not in _services:
            _wrong.append("%s: %s" % (_f, _cmd[:60]))
check("no public doc execs a compose service that does not exist", not _wrong, _wrong)
for _name in ("verify.sh", "backup.sh"):
    if "docker exec" in read("server", _name):
        check("%s takes the container name from the environment" % _name,
              "RR_CONTAINER" in read("server", _name))
check("the settings table covers every RR_ setting the server reads",
      not [v for v in re.findall(r'os\.environ\.get\(\s*"(RR_[A-Z_]+)"', read("server", "main.py"))
           if v not in _dep and v != "RR_REGEN_DAYS"],
      [v for v in re.findall(r'os\.environ\.get\(\s*"(RR_[A-Z_]+)"', read("server", "main.py"))
       if v not in _dep])

print()
print("FAILURES:", len(fails))
for f in fails: print("  -", f)
sys.exit(1 if fails else 0)
