#!/usr/bin/env python3
"""Print one version's patch notes from CHANGELOG.md, for a GitHub release.

    python build/release_notes.py 1.10028

The release page on GitHub and the "what changed" on the website come from
the same entry, so the two can never say different things. A tag with no
entry for its version fails here, on purpose: a release nobody wrote patch
notes for is a release nobody can tell apart from the last one.
"""
import io
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FOOTER = """
---

**EDSMT-Setup.exe** is the download - a normal installer, no admin needed.
**EDSMT.exe** is the same program as a single portable file.
**EDSMT-source.zip** is the source it was built from, as GPL-3.0 requires.

Windows SmartScreen will warn on first run because the build is not code
signed. More info, then Run anyway. SECURITY.md explains that in full.
"""


def entry(version):
    """The body of the `## <version>` block, without its heading."""
    text = io.open(os.path.join(REPO, "CHANGELOG.md"), encoding="utf-8").read()
    blocks = re.split(r"^## ", text, flags=re.M)[1:]
    for block in blocks:
        heading, _, body = block.partition("\n")
        if heading.strip().split()[0:1] == [version]:
            body = re.split(r"^---\s*$", body, flags=re.M)[0]
            return body.strip()
    return None


def main(argv):
    if len(argv) != 2:
        sys.exit("usage: release_notes.py <version>   e.g. 1.10028 or v1.10028")
    version = argv[1].strip().lstrip("vV")
    # The tag has to be the build. A tag of v1.10029 on a commit that still
    # says 1.10028 would publish one version's exe under another's notes.
    built = re.search(r'APP_VERSION\s*=\s*"([\d.]+)"', io.open(
        os.path.join(REPO, "edonline.py"), encoding="utf-8").read())
    if not built or built.group(1) != version:
        sys.exit("the tag says %s but edonline.APP_VERSION is %s - run "
                 "build/bump.py first" % (version, built.group(1) if built else "missing"))
    body = entry(version)
    if not body:
        sys.exit("CHANGELOG.md has no '## %s' entry - write the patch notes "
                 "before tagging the release." % version)
    sys.stdout.write(body + "\n" + FOOTER)


if __name__ == "__main__":
    main(sys.argv)
