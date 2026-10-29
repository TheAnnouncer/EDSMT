#!/usr/bin/env python3
"""Tell the Radio Raxxla Discord about a release, from CHANGELOG.md.

    python build/discord_post.py 1.10039            print the post
    python build/discord_post.py 1.10039 --send     post it to $DISCORD_WEBHOOK

The post is the one the release page and the website are built from, cut to
the shape an announcement channel wants: a headline, a few short bullets,
the download links, one line for people who already have it, and the ping
for the people who asked to be pinged. It is sent by the release job on
GitHub once a tag's files are attached, and only when the webhook is set,
so a fork or a build with no webhook never posts anything.

DISCORD_WEBHOOK  the channel's webhook URL (a secret: it is a password for
                 the channel).
DISCORD_ROLE     the id of the role to mention, if any. Only that role is
                 allowed to be mentioned; the text can never ping anyone
                 else, whatever the patch notes say.
"""
import io
import json
import os
import re
import sys
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "build"))
from release_notes import entry  # noqa: E402

DOWNLOAD = "https://radioraxxla.com/EDSMT/"
RELEASES = "https://github.com/TheAnnouncer/EDSMT/releases/tag/v%s"
MOST_BULLETS = 6
BULLET_CHARS = 240       # Discord shows a few lines per bullet before it is a wall
POST_CHARS = 1900        # Discord refuses more than 2,000 in one message


def headline(body):
    """The words after '### New -' (or Changed / Fixed), without the dash."""
    m = re.search(r"^### +\w+ *[-—–] *(.+)$", body, re.M)
    return m.group(1).strip() if m else ""


def bullets(body):
    """Each top-level '- ' item as one short line: its bold lead and the
    first sentence after it, in plain words (no markdown stars)."""
    out = []
    for m in re.finditer(r"^- (.+?)(?=^- |^#|\Z)", body, re.M | re.S):
        text = " ".join(m.group(1).split())
        lead = re.match(r"\*\*(.+?)\*\*\s*(.*)", text)
        if lead:
            head, rest = lead.group(1), lead.group(2)
        else:
            head, rest = "", text
        rest = re.sub(r"\*\*", "", rest)
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z`])", rest, maxsplit=2)
        first = parts[0].strip()
        # A short first sentence on its own says little ("The FAQ said X.");
        # give it the next one too.
        if len(first) < 80 and len(parts) > 1:
            first = (first + " " + parts[1]).strip()
        if head.endswith((".", ":")):
            # The lead was a sentence of its own: "Linux." -> "Linux - ..."
            line = "**%s** — %s" % (head.rstrip(".:"), first)
        elif head and first[:1] in ",;:":
            line = "**%s**%s" % (head, first)      # "themes, one in each..."
        elif head:
            line = "**%s** %s" % (head, first)
        else:
            line = first
        line = line.strip()
        if len(line) > BULLET_CHARS:
            line = line[:BULLET_CHARS - 1].rstrip() + "…"
        out.append(line)
        if len(out) == MOST_BULLETS:
            break
    return out


def post(version, role=""):
    body = entry(version)
    if not body:
        sys.exit("CHANGELOG.md has no '## %s' entry" % version)
    lines = ["## ⛏️ EDSMT %s — %s" % (version, headline(body) or "a new build")]
    lines += ["• " + b for b in bullets(body)]
    lines.append("Download: %s  ·  GitHub: %s" % (DOWNLOAD, RELEASES % version))
    lines.append("Already installed? The app offers the update on its next start.")
    if role:
        lines.append("<@&%s>" % role)
    tail = 3 if role else 2             # the lines after the bullets
    text = "\n".join(lines)
    while len(text) > POST_CHARS and len(lines) > tail + 1:
        # Drop the last bullet rather than cut the links off the end.
        del lines[len(lines) - tail - 1]
        text = "\n".join(lines)
    return text


def payload(version, role=""):
    return {
        "content": post(version, role),
        "username": "EDSMT",
        "allowed_mentions": {"parse": [], "roles": [role] if role else []},
    }


def send(webhook, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(webhook, data=body, method="POST", headers={
        "Content-Type": "application/json", "User-Agent": "EDSMT-release"})
    with urllib.request.urlopen(req, timeout=20) as reply:
        return reply.status


def main(argv):
    if len(argv) < 2:
        sys.exit("usage: discord_post.py <version> [--send]")
    version = argv[1].strip().lstrip("vV")
    role = os.environ.get("DISCORD_ROLE", "").strip()
    data = payload(version, role)
    if "--send" in argv:
        webhook = os.environ.get("DISCORD_WEBHOOK", "").strip()
        if not webhook.startswith("https://discord.com/api/webhooks/"):
            print("no DISCORD_WEBHOOK set - nothing posted")
            return 0
        status = send(webhook, data)
        print("posted to Discord (HTTP %s)" % status)
        return 0
    sys.stdout.write(data["content"] + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
