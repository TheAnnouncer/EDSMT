"""1.10040: one build per version, on the website and on GitHub alike.

The desk build (BUILD.bat) is what the website offers and what version.json
describes. build/publish_release.py puts exactly those files on the GitHub
release; GitHub's own build of the tag only adds the Linux file and tells
the Discord. Before this, a version could carry two different exes.

    python tests/test_110040_release_pipeline.py
"""
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "build"))
import publish_release as PR  # noqa: E402
import edonline  # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


VERSION = edonline.APP_VERSION
TMP = tempfile.mkdtemp(prefix="edsmt-publish-")


def make_upload(name, version=VERSION, tamper=None, drop=None):
    up = os.path.join(TMP, name)
    os.makedirs(up)
    info = {"version": version}
    for fname in PR.FILES:
        if fname == drop:
            continue
        with open(os.path.join(up, fname), "wb") as fh:
            fh.write(("%s %s" % (fname, version)).encode("utf-8"))
    for kind, fname in PR.KINDS.items():
        path = os.path.join(up, fname)
        if os.path.isfile(path):
            info[kind] = {"sha256": hashlib.sha256(open(path, "rb").read()).hexdigest(),
                          "bytes": os.path.getsize(path)}
    if tamper:
        with open(os.path.join(up, tamper), "ab") as fh:
            fh.write(b"changed after version.json was written")
    with io.open(os.path.join(up, "version.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh)
    return up


print("== what may be published ==")
good = make_upload("good")
check("files that match version.json and this version may go", PR.problems(good) == [], PR.problems(good))
old = make_upload("old", version="1.00001")
check("a version.json for another version is refused",
      any("1.00001" in p for p in PR.problems(old)), PR.problems(old))
changed = make_upload("changed", tamper="EDSMT.exe")
check("an exe that is not the one version.json describes is refused",
      any("EDSMT.exe" in p and "version.json" in p for p in PR.problems(changed)), PR.problems(changed))
missing = make_upload("missing", drop="EDSMT-source.zip")
check("a missing download is refused", any("EDSMT-source.zip" in p for p in PR.problems(missing)))
empty = os.path.join(TMP, "empty")
os.makedirs(empty)
check("no version.json at all is refused, saying to build", any("BUILD.bat" in p for p in PR.problems(empty)))

print("== the commands ==")
new = PR.commands("1.10099", False, "notes.md", good)
check("a new release is created from the tag that already exists, named EDSMT <version>",
      len(new) == 1 and new[0][:4] == ["gh", "release", "create", "v1.10099"]
      and "--verify-tag" in new[0] and new[0][new[0].index("--title") + 1] == "EDSMT 1.10099")
check("with the notes file and all three files", new[0][new[0].index("--notes-file") + 1] == "notes.md"
      and all(os.path.join(good, f) in new[0] for f in PR.FILES))
again = PR.commands("1.10099", True, "notes.md", good)
check("an existing release (GitHub's Linux job got there first) is renamed and given its notes",
      again[0][:4] == ["gh", "release", "edit", "v1.10099"] and "EDSMT 1.10099" in again[0])
check("and the desk's files replace whatever is there",
      again[1][:4] == ["gh", "release", "upload", "v1.10099"] and "--clobber" in again[1]
      and all(os.path.join(good, f) in again[1] for f in PR.FILES))

print("== running it ==")


class Done:
    def __init__(self, code=0, err=""):
        self.returncode, self.stderr, self.stdout = code, err, ""


calls = []


def runner(view_code):
    def run(cmd, **kw):
        calls.append(cmd)
        return Done(view_code if cmd[1:3] == ["release", "view"] else 0)
    return run


real_upload = os.path.join(REPO, "upload")
saved = None
if os.path.isdir(real_upload):
    saved = real_upload + ".kept-by-test"
    os.rename(real_upload, saved)
try:
    shutil.copytree(good, real_upload)
    out = io.StringIO()
    keep, sys.stdout = sys.stdout, out
    try:
        calls.clear()
        rc = PR.main(["publish_release.py"], run=runner(1))
    finally:
        sys.stdout = keep
    check("check only: it asks whether the release exists and changes nothing",
          rc == 0 and [c[1:3] for c in calls] == [["release", "view"]], calls)
    check("and says what it would do", "release create" in out.getvalue(), out.getvalue())
    out = io.StringIO()
    sys.stdout = out
    try:
        calls.clear()
        rc = PR.main(["publish_release.py", "--go"], run=runner(0))
    finally:
        sys.stdout = keep
    check("--go on a release that exists: edit, then upload with --clobber",
          rc == 0 and [c[1:3] for c in calls] == [["release", "view"], ["release", "edit"], ["release", "upload"]],
          [c[1:3] for c in calls])
    notes = calls[1][calls[1].index("--notes-file") + 1]
    text = io.open(notes, encoding="utf-8").read()
    check("the notes file is UTF-8 with this version's CHANGELOG entry and the downloads footer",
          text.startswith("### ") and "EDSMT-Setup.exe" in text and "﻿" not in text, text[:40])
    shutil.rmtree(real_upload)
    shutil.copytree(old, real_upload)
    out = io.StringIO()
    sys.stdout = out
    try:
        calls.clear()
        rc = PR.main(["publish_release.py", "--go"], run=runner(0))
    finally:
        sys.stdout = keep
    check("a build that does not match is refused before anything runs",
          rc == 1 and calls == [] and "NOT PUBLISHED" in out.getvalue(), (rc, calls))
finally:
    if os.path.isdir(real_upload):
        shutil.rmtree(real_upload)
    if saved:
        os.rename(saved, real_upload)

print("== GitHub's build of a tag ==")
yml = io.open(os.path.join(REPO, ".github", "workflows", "build.yml"), encoding="utf-8").read()
release = yml.split("\n  release:\n")[1]
check("the release job needs the Linux build only - a flaky Windows runner never holds it back",
      re.search(r"needs:\s*\[\s*linux\s*\]", release), release[:120])
check("it attaches the Linux file and none of the Windows ones (those come from the desk)",
      "upload/EDSMT-linux-x86_64.tar.gz" in release and "EDSMT-Setup.exe" not in release.split("body_path")[0]
      and "upload/EDSMT.exe" not in release)
check("it names the release EDSMT <version>, not the bare tag",
      re.search(r"name:\s*EDSMT \$\{\{\s*env\.VERSION\s*\}\}", release), release[:400])
check("the version comes from the tag", "GITHUB_REF_NAME#v" in release)
check("and posts nothing to Discord - the Radio Raxxla bot announces releases from the release page",
      "discord" not in release.lower() and not os.path.exists(os.path.join(REPO, "build", "discord_post.py")))
check("the Windows job still builds and tests every push", "\n  windows:\n" in yml and "tests/run_all.py" in yml.split("\n  linux:\n")[0])
batch = io.open(os.path.join(REPO, "BUILD.bat"), encoding="utf-8", errors="replace").read()
check("BUILD.bat ends by saying how to publish the release", "publish_release.py" in batch)

print("== every action pinned to a commit ==")
# A tag can be moved to other code; a commit cannot. Each `uses:` names the
# full 40-character commit, with the tag beside it as a note.
uses = re.findall(r"uses:\s*(\S+)", yml)
loose = [u for u in uses if not re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", u)]
check("%d actions, every one at a commit" % len(uses), uses and not loose, loose)
check("and each says which tag that was", all(re.search(r"uses:\s*%s\s+# v\d" % re.escape(u), yml) for u in uses))

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if fails else 0)
