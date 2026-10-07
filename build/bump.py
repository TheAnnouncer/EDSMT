#!/usr/bin/env python3
"""Move the version on, in every file that carries it, in one go.

The version lives in seven fields across three files, and every release that
edited six of them shipped a build that reported the wrong number
somewhere. This is not a nicety - it is the only way the audit stays true.

    python build/bump.py            1.10001 -> 1.10002
    python build/bump.py 1.20000    set it explicitly

Run it for EVERY change, however small. A build you cannot name is a bug
report you cannot place.
"""
import io, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# path, pattern, how to write the new version into it
TARGETS = [
    ("edonline.py",           r'(APP_VERSION\s*=\s*")([\d.]+)(")',        "plain"),
    ("build/installer.iss",   r'(#define AppVersion ")([\d.]+)(")',       "plain"),
    ("build/installer.iss",   r'(VersionInfoVersion=)([\d.]+)()',         "quad"),
    ("build/version_info.txt", r'(filevers=\()([\d, ]+)(\))',             "tuple"),
    ("build/version_info.txt", r'(prodvers=\()([\d, ]+)(\))',             "tuple"),
    ("build/version_info.txt", r"('FileVersion', ')([\d.]+)(')",          "quad"),
    ("build/version_info.txt", r"('ProductVersion', ')([\d.]+)(')",       "quad"),
]

# The API carries the same number. Its source is not in this project; on
# the machine that builds releases it is in the private folder beside it,
# and moves on with everything else. Anywhere else there is nothing to move.
SERVER_MAIN = os.path.join("..", "EDSMT-Private", "server", "main.py")
if os.path.exists(os.path.join(REPO, SERVER_MAIN)):
    TARGETS.append((SERVER_MAIN, r'(APP_VERSION\s*=\s*")([\d.]+)(")', "plain"))


def read(path):
    with io.open(os.path.join(REPO, path), encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path, text):
    with io.open(os.path.join(REPO, path), "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def current():
    m = re.search(r'APP_VERSION\s*=\s*"([\d.]+)"', read("edonline.py"))
    if not m:
        sys.exit("could not read the current version from edonline.py")
    return m.group(1)


def nextafter(version):
    """1.10001 -> 1.10002. The last component carries the count."""
    parts = version.split(".")
    try:
        parts[-1] = str(int(parts[-1]) + 1)
    except ValueError:
        sys.exit("cannot count on from %r - pass the new version explicitly"
                 % version)
    return ".".join(parts)


def quad(version):
    """Windows wants four numbers. Pad, never truncate."""
    parts = [p for p in version.split(".") if p.isdigit()]
    parts = (parts + ["0", "0", "0", "0"])[:4]
    for p in parts:
        if int(p) > 65535:
            sys.exit("%s will not fit a Windows version field (max 65535)" % p)
    return parts


def main():
    was = current()
    now = sys.argv[1] if len(sys.argv) > 1 else nextafter(was)
    if not re.fullmatch(r"[\d]+(\.[\d]+)+", now):
        sys.exit("%r is not a version" % now)
    q = quad(now)

    touched = {}
    for path, pattern, shape in TARGETS:
        text = touched.get(path, read(path))
        value = {"plain": now,
                 "quad": ".".join(q),
                 "tuple": ",".join(q)}[shape]
        text, n = re.subn(pattern, lambda m: m.group(1) + value + m.group(3),
                          text, count=1)
        if not n:
            sys.exit("no match for %s in %s - bump.py is out of date with the "
                     "file it is meant to keep honest" % (pattern, path))
        touched[path] = text

    for path, text in touched.items():
        write(path, text)
        print("  %s" % path)
    print("%s -> %s" % (was, now))
    print("Run the tests, then BUILD.bat.")


if __name__ == "__main__":
    main()
