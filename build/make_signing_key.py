"""Make the update-signing key, once, on the build machine.

    python build\\make_signing_key.py <path outside the repo>

Writes the private key to that file and prints ONLY the public key, which
goes into edonline.UPDATE_PUBLIC_KEY. The private key never leaves the
machine and is never printed: back the file up somewhere safe, because an
update signed with any other key will be refused by every EDSMT that has
this public key. It refuses to overwrite a file that is already there.
"""
import os
import secrets
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import signing as SG  # noqa: E402


def make(path):
    """The public key, in text, or None when the file already exists."""
    if os.path.exists(path):
        return None
    secret = secrets.token_bytes(32)
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("# EDSMT update-signing key. Private. Never commit, never paste.\n")
        handle.write(SG.encode(secret) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return SG.encode(SG.public_key(secret))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    shown = make(sys.argv[1])
    if shown is None:
        print("%s already exists - not overwritten. Delete it yourself if you mean to make a new key." % sys.argv[1])
        sys.exit(1)
    print("Private key written to %s - keep it safe, never share it." % sys.argv[1])
    print("Public key (paste this into edonline.UPDATE_PUBLIC_KEY):")
    print(shown)
