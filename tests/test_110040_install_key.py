"""1.10040 (security audit finding 3): this copy of EDSMT's own key.

The community map gives each copy of EDSMT a key of its own (POST
/v1/install) and knows EDSMT by it rather than by its User-Agent, which any
script can copy. The app asks for one once, keeps it in the data folder - not
in settings.json, so it is never in a settings file passed on or turned into
defaults - and sends it with every request to the map. It is never shown.

    python tests/test_110040_install_key.py
"""
import json
import os
import stat
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
TMP = tempfile.mkdtemp(prefix="edsmt-key-")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "xdg")
os.environ["HOME"] = TMP

import installkey as IK   # noqa: E402
import edonline as EDO    # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


KEY = "a" * 20 + "B-c_d" + "9" * 18      # the server's token_urlsafe(32): 43 characters

print("== the key's own file ==")
check("a key the server makes is a key", IK.valid(KEY))
check("anything else is not", not any(IK.valid(x) for x in ("", "short", "has space " * 5, "x" * 300, None, 42,
                                                            "<script>" + "a" * 30)))
folder = os.path.join(TMP, "data")
check("no file yet: no key", IK.load(folder) == "")
check("kept", IK.save(folder, KEY) is True and IK.load(folder) == KEY)
path = os.path.join(folder, IK.FILE_NAME)
check("in a file of its own, not settings.json", os.path.isfile(path) and IK.FILE_NAME != "settings.json")
if os.name != "nt":
    check("readable by this user only", stat.S_IMODE(os.stat(path).st_mode) == 0o600,
          oct(stat.S_IMODE(os.stat(path).st_mode)))
check("a bad key is never written", IK.save(folder, "nope") is False and IK.load(folder) == KEY)
with open(path, "w", encoding="utf-8") as handle:
    handle.write("not a key at all\n")
check("a file with rubbish in it reads as no key", IK.load(folder) == "")
check("the server's answer gives the key", IK.from_reply(json.dumps({"key": KEY, "id": 7})) == KEY)
check("an answer without one gives nothing", IK.from_reply("{}") == "" and IK.from_reply("<html>") == ""
      and IK.from_reply(json.dumps({"key": "x"})) == "")
check("asked for when there is none, not again for a while after a refusal",
      IK.due("", None, 1000.0) and not IK.due(KEY, None, 1000.0)
      and not IK.due("", 1000.0, 1000.0 + 60) and IK.due("", 1000.0, 1000.0 + IK.RETRY_S + 1))

print("== the community client sends it ==")
client = EDO.CommunityClient(EDO.Worker())
client.configure("", enabled=True)
check("no key: no key header", "X-EDSMT-Key" not in client._headers())
client.install_key = KEY
check("with one, every request to the map carries it", client._headers().get("X-EDSMT-Key") == KEY)
client.token = "staff-token"
check("alongside a staff token when there is one",
      client._headers().get("X-EDSMT-Key") == KEY and client._headers().get("Authorization") == "Bearer staff-token")
seen = {}


def fake_post(url, payload, timeout=20.0, headers=None):
    seen.update(url=url, payload=payload, headers=dict(headers or {}))
    return {"key": KEY, "id": 9, "send_as": "X-EDSMT-Key"}


real_post = EDO.post_json
EDO.post_json = fake_post
try:
    fresh = EDO.CommunityClient(EDO.Worker())
    fresh.configure("")
    check("asking is allowed with sharing off - it is not sharing", fresh.ask_install_key() is True)
    import time
    for _ in range(100):
        got = fresh.worker.drain()
        if got:
            break
        time.sleep(0.02)
    check("it asks the map's /v1/install", seen.get("url", "").endswith("/v1/install"), seen.get("url"))
    check("and the answer comes back under its own tag",
          got and got[0][0] == IK.TAG and got[0][1] is True and IK.from_reply(got[0][2]) == KEY, got)
finally:
    EDO.post_json = real_post

print("== no request to the map goes without the client's headers ==")
src = open(os.path.join(REPO, "edonline.py"), encoding="utf-8").read()
body = src[src.index("class CommunityClient"):src.index("\ndef fold(")]
import re  # noqa: E402
calls = re.findall(r"\b(get_json|post_json|get_bytes|patch_json)\(([^\n]*)", body)
bare = [c for c in calls if "headers=" not in c[1] and "install" not in c[1]]
check("every call in the community client passes headers", not bare, bare)

print("== in the app ==")
try:
    import tkinter
    tkinter.Tk().destroy()
    HAVE_DISPLAY = True
except Exception as exc:  # noqa: BLE001
    HAVE_DISPLAY = False
    print("  SKIP  the app needs a display (%s). Run it under xvfb-run." % exc)
if HAVE_DISPLAY:
    import edsmt as A
    A.DATA_DIR = os.path.join(TMP, "appdata-key")
    os.makedirs(A.DATA_DIR, exist_ok=True)
    said = []
    app = A.EDSMT.__new__(A.EDSMT)
    app.settings = dict(A.DEFAULT_SETTINGS)
    app.community = EDO.CommunityClient(EDO.Worker())
    app.community.configure("")
    app.say = lambda text, colour=None: said.append(str(text))
    app.take_install_key(True, json.dumps({"key": KEY, "id": 3}))
    check("the key from the map is kept and used", IK.load(A.DATA_DIR) == KEY and app.community.install_key == KEY)
    check("and never said", not any(KEY in s for s in said), said)
    check("never in the settings", KEY not in json.dumps(app.settings))
    app.take_install_key(False, "HTTP 429")
    check("a refusal changes nothing and says nothing", app.community.install_key == KEY and not said, said)
    app2 = A.EDSMT.__new__(A.EDSMT)
    app2.settings = dict(A.DEFAULT_SETTINGS)
    app2.community = EDO.CommunityClient(EDO.Worker())
    app2.community.configure("")
    asked = []
    app2.community.ask_install_key = lambda: asked.append(1) or True
    app2.load_install_key()
    check("at start a kept key is read back, and not asked for again",
          app2.community.install_key == KEY and not app2.ask_install_key() and not asked)
    os.remove(os.path.join(A.DATA_DIR, IK.FILE_NAME))
    app3 = A.EDSMT.__new__(A.EDSMT)
    app3.settings = dict(A.DEFAULT_SETTINGS)
    app3.community = EDO.CommunityClient(EDO.Worker())
    app3.community.configure("")
    app3.community.ask_install_key = lambda: asked.append(1) or True
    app3.load_install_key()
    check("with none kept, it asks once", app3.ask_install_key() and asked == [1] and not app3.ask_install_key(),
          asked)
    import supportbundle as SB
    import zipfile
    IK.save(A.DATA_DIR, KEY)
    with open(os.path.join(A.DATA_DIR, "app.log"), "w", encoding="utf-8") as handle:
        handle.write("a line\n")
    bundle = SB.make_bundle(os.path.join(TMP, "bundles"), A.DATA_DIR, app.settings, "1.10040")
    with zipfile.ZipFile(bundle) as z:
        inside = b"".join(z.read(n) for n in z.namelist())
    check("the support bundle never carries the key", KEY.encode() not in inside)

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
