"""1.10040: EDSMT's own address is edsmt.radioraxxla.com.

Every Radio Raxxla tool gets a host of its own (EDOST and EDSQT will sit
beside this one). The app talks to edsmt.radioraxxla.com; the first address,
api.radioraxxla.com, is still answered by the same map, so an app that cannot
reach the new name yet (a stale DNS cache, a firewall rule that names the old
one) tries the old one once and keeps to it for the rest of the session. A
reply from the map - even a refusal - is an answer and is never retried.

    python tests/test_110040_address.py
"""
import io
import os
import re
import socket
import sys
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
import edonline as EDO  # noqa: E402
import board            # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


NEW, OLD = "https://edsmt.radioraxxla.com", "https://api.radioraxxla.com"

print("== the address ==")
check("the community map is edsmt.radioraxxla.com", EDO.HOME_URL == NEW and EDO.CommunityClient.DEFAULT_URL == NEW,
      (EDO.HOME_URL, EDO.CommunityClient.DEFAULT_URL))
check("the leaderboard and live pages are there too", board.WEB_PAGE == NEW + "/leaderboard"
      and board.LIVE_PAGE == NEW + "/live", (board.WEB_PAGE, board.LIVE_PAGE))


class Reply:
    def __init__(self, body):
        self.body = body.encode()

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


asked = []


def fake_urlopen(request, timeout=0):
    url = request.full_url
    asked.append(url)
    if url.startswith(NEW) and BEHAVIOUR == "dns":
        raise urllib.error.URLError(socket.gaierror(11001, "getaddrinfo failed"))
    if BEHAVIOUR == "refused":
        raise urllib.error.HTTPError(url, 403, "Forbidden", {}, io.BytesIO(b'{"detail": "not you"}'))
    return Reply('{"ok": true, "from": "%s"}' % url.split("/v1")[0])


EDO.urllib.request.urlopen = fake_urlopen

print("== the new name cannot be reached yet ==")
BEHAVIOUR = "dns"
EDO.reset_host()
got = EDO.get_json(NEW + "/v1/health")
check("it is tried first, then the old name answers", asked == [NEW + "/v1/health", OLD + "/v1/health"]
      and got.get("from") == OLD, (asked, got))
del asked[:]
EDO.post_json(NEW + "/v1/deposits", {"a": 1})
check("and the session keeps to the old name, posts too", asked == [OLD + "/v1/deposits"], asked)

print("== the new name answers ==")
BEHAVIOUR = "ok"
EDO.reset_host()
del asked[:]
check("it is used, and only it", EDO.get_json(NEW + "/v1/health").get("from") == NEW and asked == [NEW + "/v1/health"],
      asked)

print("== the map answered with a refusal ==")
BEHAVIOUR = "refused"
EDO.reset_host()
del asked[:]
try:
    EDO.post_json(NEW + "/v1/deposits", {"a": 1})
    said = ""
except RuntimeError as problem:
    said = str(problem)
check("it is reported, never sent again to the other name", asked == [NEW + "/v1/deposits"] and "not you" in said,
      (asked, said))

print("== someone else's address is never changed ==")
BEHAVIOUR = "dns"
EDO.reset_host()
del asked[:]
try:
    EDO.get_json("https://example.com/x")
except RuntimeError:
    pass
check("one try, as it was", asked == ["https://example.com/x"], asked)

print("== nothing public still points at the old name ==")
stale = []
for root, dirs, files in os.walk(REPO):
    # Build output (upload, dist) and local environments are not the
    # public tree: an old build's upload\index.html is on a desk until the
    # next build replaces it.
    dirs[:] = [d for d in dirs if d not in ("tests", "__pycache__", ".git", "build", "dist", "upload",
                                            ".venv", ".venv-build", "venv", "env")]
    for name in files:
        if name.endswith((".py", ".html", ".md", ".json")):
            path = os.path.join(root, name)
            for n, line in enumerate(io.open(path, encoding="utf-8", errors="replace"), 1):
                if "api.radioraxxla.com" in line and not re.search(r"^\s*OLD_URL\s*=", line) \
                        and not line.lstrip().startswith("#") and "edsmt.radioraxxla.com" not in line:
                    stale.append("%s:%d" % (os.path.relpath(path, REPO), n))
check("only the fallback (and comments about it) names api.radioraxxla.com", not stale, stale)

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
