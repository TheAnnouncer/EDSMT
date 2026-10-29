"""1.10039: a release tells the Radio Raxxla Discord about itself.

build/discord_post.py turns the CHANGELOG entry for a version into the post
an announcement channel wants, and the release job on GitHub sends it to
the channel's webhook - only when the webhook is set.

    python tests/test_110039_discord_post.py
"""
import http.server
import io
import json
import os
import re
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "build"))
import discord_post as DP  # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


SAMPLE = """### New — two things and a fix

- **The first thing.** It does one job. It also does a second job that
  nobody asked for. A third sentence is never shown.
- **Second thing**, which is short.
- A bullet with no bold lead. Short one. And a third.
- **Changed:** the fourth bullet with a colon lead.
- **Fifth** and **bold inside** stays plain.
- **Sixth** sixth.
- **Seventh** never shows: six is the most.

### Fixed

- Something small.
"""

print("== the shape of the post ==")
DP.entry = lambda version: SAMPLE
text = DP.post("1.10099")
lines = text.split("\n")
check("the headline is the CHANGELOG's New line with the version",
      lines[0] == "## ⛏️ EDSMT 1.10099 — two things and a fix", lines[0])
bullets = [l for l in lines if l.startswith("• ")]
check("at most six bullets", len(bullets) == 6, len(bullets))
check("a sentence lead becomes 'lead - first sentences', never the third",
      bullets[0] == "• **The first thing** — It does one job. It also does a second job that nobody asked for.", bullets[0])
check("a lead followed by a comma keeps the comma",
      bullets[1] == "• **Second thing**, which is short.", bullets[1])
check("a short sentence with no lead gets the next one too",
      bullets[2] == "• A bullet with no bold lead. Short one.", bullets[2])
check("a colon lead", bullets[3] == "• **Changed** — the fourth bullet with a colon lead.", bullets[3])
check("stars inside the sentence are taken out", "**bold inside**" not in bullets[4] and "bold inside" in bullets[4], bullets[4])
check("the download and the release page are on one line",
      "Download: https://radioraxxla.com/EDSMT/" in text
      and "https://github.com/TheAnnouncer/EDSMT/releases/tag/v1.10099" in text)
check("the line for people who have it", "Already installed? The app offers the update on its next start." in lines[-1])
check("no role: no mention line", "<@&" not in text)
with_role = DP.post("1.10099", role="42")
check("with a role: the mention is the last line", with_role.split("\n")[-1] == "<@&42>")

print("== a long entry is cut from the bottom, never the links ==")
LONG = "### New — much\n\n" + "".join("- **Thing %d.** %s\n" % (i, "word " * 60) for i in range(6))
DP.entry = lambda version: LONG
long_text = DP.post("1.10099", role="42")
check("under Discord's limit", len(long_text) <= 2000, len(long_text))
check("the links and the mention survive", "Download:" in long_text and long_text.endswith("<@&42>"))
check("every bullet is cut to a readable length",
      all(len(l) <= DP.BULLET_CHARS + 2 for l in long_text.split("\n") if l.startswith("• ")))

print("== the payload only ever pings the one role ==")
DP.entry = lambda version: SAMPLE
data = DP.payload("1.10099", role="42")
check("content, a name, and allowed_mentions", set(data) == {"content", "username", "allowed_mentions"}, sorted(data))
check("nothing parsed from the text, the role alone", data["allowed_mentions"] == {"parse": [], "roles": ["42"]}, data["allowed_mentions"])
check("no role: nobody can be mentioned", DP.payload("1.10099")["allowed_mentions"] == {"parse": [], "roles": []})

print("== sending ==")
got = {}


class Hook(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        got["body"] = json.loads(self.rfile.read(n).decode("utf-8"))
        got["type"] = self.headers.get("Content-Type")
        self.send_response(204)
        self.end_headers()

    def log_message(self, *a):
        pass


server = http.server.HTTPServer(("127.0.0.1", 0), Hook)
threading.Thread(target=server.serve_forever, daemon=True).start()
url = "http://127.0.0.1:%d/api/webhooks/1/abc" % server.server_port
status = DP.send(url, data)
check("posted as JSON", status == 204 and got.get("type") == "application/json", (status, got.get("type")))
check("the body is the payload", got.get("body") == data)
server.shutdown()

print("== the command line ==")
old = dict(os.environ)
os.environ.pop("DISCORD_WEBHOOK", None)
os.environ["DISCORD_ROLE"] = "42"
out = io.StringIO()
sys.stdout, keep = out, sys.stdout
try:
    rc = DP.main(["discord_post.py", "v1.10099", "--send"])
finally:
    sys.stdout = keep
check("no webhook: nothing sent, says so, exit 0", rc == 0 and "nothing posted" in out.getvalue(), out.getvalue())
os.environ["DISCORD_WEBHOOK"] = "http://example.invalid/not-a-discord-hook"
out = io.StringIO()
sys.stdout = out
try:
    rc = DP.main(["discord_post.py", "v1.10099", "--send"])
finally:
    sys.stdout = keep
check("a webhook that is not Discord's is refused without a request", rc == 0 and "nothing posted" in out.getvalue())
os.environ.clear()
os.environ.update(old)

print("== the real CHANGELOG ==")
import importlib  # noqa: E402
importlib.reload(DP)
import edonline  # noqa: E402
real = DP.post(edonline.APP_VERSION, role="1")
check("the current version has a post", real.startswith("## ⛏️ EDSMT %s — " % edonline.APP_VERSION), real[:60])
check("with bullets", sum(1 for l in real.split("\n") if l.startswith("• ")) >= 1)
check("and fits", len(real) <= 2000, len(real))

print("== the release job sends it ==")
yml = io.open(os.path.join(REPO, ".github", "workflows", "build.yml"), encoding="utf-8").read()
release = yml.split("\n  release:\n")[1]
check("after the files are attached, the post goes out",
      release.index("softprops/action-gh-release") < release.index("build/discord_post.py"))
check("with the webhook and the role from secrets",
      re.search(r"DISCORD_WEBHOOK:\s*\$\{\{\s*secrets\.DISCORD_WEBHOOK\s*\}\}", release)
      and re.search(r"DISCORD_ROLE:\s*\$\{\{\s*secrets\.DISCORD_ROLE\s*\}\}", release))
check("and --send", "--send" in release)

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
