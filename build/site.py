#!/usr/bin/env python3
"""Put the current version and the latest changes onto the landing page.

The download page has to say which build it is offering and what changed in
it, or the release is invisible: people who already have EDSMT have no way
of knowing there is any reason to download it again. Doing that by hand
means the page eventually claims a version the installer is not, which is
worse than saying nothing.

So the page carries markers, and this fills them from the two files that are
already the truth: edonline.APP_VERSION and the top entry of CHANGELOG.md.

    python build/site.py

BUILD.bat runs it, so the page in upload\\ always matches the exe beside it.
"""
import html
import io
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(REPO, "site", "index.html")


def read(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def version():
    m = re.search(r'APP_VERSION\s*=\s*"([\d.]+)"',
                  read(os.path.join(REPO, "edonline.py")))
    if not m:
        sys.exit("no APP_VERSION in edonline.py")
    return m.group(1)


def latest_entry():
    """The top ## block of the changelog, without its own heading."""
    text = read(os.path.join(REPO, "CHANGELOG.md"))
    blocks = re.split(r"^## ", text, flags=re.M)
    if len(blocks) < 2:
        sys.exit("no ## entry in CHANGELOG.md")
    body = blocks[1]
    # Drop the heading line, and stop at the rule that ends the entry.
    body = body.split("\n", 1)[1] if "\n" in body else ""
    body = re.split(r"^---\s*$", body, flags=re.M)[0]
    return body.strip()


def inline(text):
    """The little markdown the changelog actually uses, and nothing else."""
    out = html.escape(text)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", out)
    # Single-star italics after the bold, so **bold** is never half-eaten.
    # The patch notes use it for setting names - *This build* - and without
    # this the page showed the asterisks.
    out = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])", r"<i>\1</i>", out)
    out = out.replace(" -- ", " &mdash; ").replace(" - ", " &mdash; ")
    return out


def to_html(markdown):
    parts, bullets = [], []

    def flush():
        if bullets:
            parts.append("<ul>" + "".join("<li>%s</li>" % b for b in bullets)
                         + "</ul>")
            del bullets[:]

    for chunk in re.split(r"\n\s*\n", markdown):
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk.startswith("### "):
            flush()
            parts.append("<h3>%s</h3>" % inline(chunk[4:].strip()))
        elif chunk.startswith("- "):
            for line in chunk.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    bullets.append(inline(line[2:].strip()))
                elif bullets:
                    bullets[-1] += " " + inline(line)
        else:
            flush()
            parts.append("<p>%s</p>" % inline(" ".join(chunk.split("\n"))))
    flush()
    return "\n    ".join(parts)


def fill(page, marker, replacement):
    open_tag, close_tag = "<!--%s-->" % marker, "<!--/%s-->" % marker
    pattern = re.escape(open_tag) + r".*?" + re.escape(close_tag)
    if not re.search(pattern, page, re.S):
        sys.exit("no %s marker in site/index.html" % marker)
    return re.sub(pattern, lambda _: open_tag + replacement + close_tag,
                  page, flags=re.S)


def headline():
    """The first real line of the latest changelog entry, for the banner."""
    for line in latest_entry().splitlines():
        line = line.strip()
        if line.startswith("### "):
            return line[4:].strip()
    for line in latest_entry().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line.rstrip(".")
    return ""


# The two downloads, by the name they have in upload\ and on the website.
DOWNLOADS = {"installer": "EDSMT-Setup.exe", "portable": "EDSMT.exe"}
SITE = "https://radioraxxla.com/EDSMT/"


def package(name, now):
    """What the app needs to fetch one download and prove it is the right
    file: where it is, how big, and its SHA-256. None if it was not built.

    The ?v= is there for any cache in front of the website: the file name
    never changes between builds, the address with the version on it does.
    """
    import hashlib
    path = os.path.join(REPO, "upload", name)
    if not os.path.isfile(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return {"url": "%s%s?v=%s" % (SITE, name, now),
            "sha256": digest.hexdigest(),
            "bytes": os.path.getsize(path)}


def write_version_file(now):
    """The file the app checks on launch.

    Static, and on the website rather than the API: a commander should be
    told about a new build even on a day the API is down, and a static file
    can be served from a cache without touching the API.

    It carries each download's size and SHA-256, so the app can fetch the
    new build by itself and refuse anything that is not exactly this file.
    Run it AFTER the installer is built, and upload it AFTER the exes.
    """
    import json
    path = os.path.join(REPO, "site", "version.json")
    payload = {
        "version": now,
        "url": SITE,
        "headline": headline(),
    }
    for kind, name in DOWNLOADS.items():
        found = package(name, now)
        if found:
            payload[kind] = found
            print("  %-9s %s  %d bytes  sha256 %s..." % (kind, name, found["bytes"],
                                                         found["sha256"][:16]))
        else:
            print("  %-9s %s NOT FOUND in upload\\ - copies of EDSMT will be "
                  "sent to the download page for this one" % (kind, name))
    with io.open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    print("site/version.json -> %s" % now)


def main():
    now = version()
    write_version_file(now)
    page = read(PAGE)
    page = fill(page, "VERSION", now)
    page = fill(page, "WHATSNEW", "\n    " + to_html(latest_entry()) + "\n    ")
    with io.open(PAGE, "w", encoding="utf-8") as fh:
        fh.write(page)
    print("site/index.html -> %s" % now)
    print("what changed: %d characters" % len(latest_entry()))


if __name__ == "__main__":
    main()
