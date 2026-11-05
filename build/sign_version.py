"""Sign site/version.json with the build machine's key.

    python build\\sign_version.py site\\version.json <key file>

BUILD.bat runs this after site.py when EDSMT_SIGNING_KEY names the key
file. Without the key file nothing is signed and it says so; the app then
treats the update as it did before signing existed, until a public key is
set in the app - after which an unsigned update is refused.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import signing as SG  # noqa: E402


def sign_file(path, key_path):
    """True when version.json at `path` was signed in place."""
    if not (key_path and os.path.isfile(key_path)):
        return False
    try:
        secret = SG.read_secret(key_path)
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return False
    signed = SG.sign_version(data, secret)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(signed, handle, indent=2)
        handle.write("\n")
    return True


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    if sign_file(sys.argv[1], sys.argv[2]):
        print("%s signed." % sys.argv[1])
    else:
        print("NOT signed: no key file at %r. Set EDSMT_SIGNING_KEY to the key file's path." % sys.argv[2])
        sys.exit(1)
