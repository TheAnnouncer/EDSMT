"""1.10040: signed updates (security audit item 2).

version.json names each build's checksum; from now on it also carries a
signature over those checksums, made on the build machine with a private
key that never leaves it. The app holds only the public key. With a public
key set, an update whose version.json is unsigned, or signed with any other
key, is refused and the app points at the download page instead - a
checksum alone proves the file matches the list, not who wrote the list.
Until the key exists the public key is blank and updates work as before.

The signature is Ed25519, checked by a small pure-Python verifier (nothing
to install, nothing an antivirus has opinions about), proven here against
RFC 8032's own test vectors.

    python tests/test_110040_signed.py
"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "build"))

import signing as SG    # noqa: E402
import edonline as EDO  # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else "   <-- %s" % (extra,)))
    if not cond:
        fails.append(label)


# RFC 8032, section 7.1.
TESTS = [
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", b"",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", bytes([0x72]),
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    ("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
     "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025", bytes.fromhex("af82"),
     "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"),
]

print("== the verifier, against RFC 8032 ==")
for i, (secret, public, message, sig) in enumerate(TESTS, 1):
    pub = bytes.fromhex(public)
    check("test %d: the public key comes out of the secret" % i, SG.public_key(bytes.fromhex(secret)) == pub)
    check("test %d: the known signature verifies" % i, SG.verify(pub, message, bytes.fromhex(sig)))
    check("test %d: and the secret makes that very signature" % i,
          SG.sign(bytes.fromhex(secret), message) == bytes.fromhex(sig))
    wrong = bytearray(bytes.fromhex(sig))
    wrong[5] ^= 1
    check("test %d: one bit wrong and it fails" % i, not SG.verify(pub, message, bytes(wrong)))
    check("test %d: another message fails" % i, not SG.verify(pub, message + b"x", bytes.fromhex(sig)))
check("rubbish never raises", not SG.verify(b"short", b"m", b"sig") and not SG.verify(bytes(32), b"m", bytes(64)))
started = time.time()
SG.verify(bytes.fromhex(TESTS[0][1]), b"", bytes.fromhex(TESTS[0][3]))
check("a check takes well under a second", time.time() - started < 1.0, time.time() - started)

print("== what is signed ==")
data = {"version": "1.10040", "installer": {"url": "https://radioraxxla.com/EDSMT/x.exe", "sha256": "a" * 64, "bytes": 5},
        "portable": {"url": "https://radioraxxla.com/EDSMT/y.zip", "sha256": "b" * 64, "bytes": 6}}
check("the message is the version and each kind's checksum, in a fixed order",
      SG.message_for(data) == b"edsmt-update\n1.10040\ninstaller " + b"a" * 64 + b"\nportable " + b"b" * 64 + b"\n")
check("a missing kind is left out, not guessed", SG.message_for({"version": "1.1", "portable": {"sha256": "c" * 64}})
      == b"edsmt-update\n1.1\nportable " + b"c" * 64 + b"\n")

secret = bytes.fromhex(TESTS[0][0])
pub_text = SG.encode(SG.public_key(secret))
signed = SG.sign_version(dict(data), secret)
check("signing adds one field, the signature in text", set(signed) - set(data) == {"signature"}
      and SG.decode(signed["signature"]) == SG.sign(secret, SG.message_for(data)))
check("and it verifies with the public key", SG.verified(signed, pub_text))
tampered = json.loads(json.dumps(signed))
tampered["installer"]["sha256"] = "d" * 64
check("a changed checksum fails", not SG.verified(tampered, pub_text))
check("no signature fails", not SG.verified(dict(data), pub_text))
check("another key fails", not SG.verified(signed, SG.encode(SG.public_key(bytes.fromhex(TESTS[1][0])))))
check("no public key set: not checked, as before", SG.verified(dict(data), "") and SG.verified(signed, ""))

print("== the app ==")
check("the public key slot is in edonline, blank until the key is made",
      hasattr(EDO, "UPDATE_PUBLIC_KEY") and (EDO.UPDATE_PUBLIC_KEY == "" or len(SG.decode(EDO.UPDATE_PUBLIC_KEY)) == 32))
kept = EDO.UPDATE_PUBLIC_KEY
try:
    EDO.UPDATE_PUBLIC_KEY = pub_text
    check("with a key, an unsigned version.json offers no package", EDO.update_package(dict(data), "installer") is None)
    check("a signed one does", EDO.update_package(signed, "installer") is not None)
    check("a tampered one does not", EDO.update_package(tampered, "installer") is None)
    EDO.UPDATE_PUBLIC_KEY = ""
    check("without a key, as before", EDO.update_package(dict(data), "installer") is not None)
finally:
    EDO.UPDATE_PUBLIC_KEY = kept

print("== the build machine ==")
import make_signing_key as MK  # noqa: E402
import sign_version as SVN     # noqa: E402
tmp = tempfile.mkdtemp(prefix="edsmt-sign-")
key_path = os.path.join(tmp, "edsmt-signing.key")
shown = MK.make(key_path)
check("the key file is made, and only the public key is shown",
      os.path.isfile(key_path) and len(SG.decode(shown)) == 32 and SG.read_secret(key_path) not in shown.encode()
      and shown not in open(key_path, encoding="utf-8").read())
check("making it again refuses to overwrite", MK.make(key_path) is None)
vj = os.path.join(tmp, "version.json")
with open(vj, "w", encoding="utf-8") as handle:
    json.dump(data, handle)
check("sign_version signs in place", SVN.sign_file(vj, key_path) and SG.verified(json.load(open(vj, encoding="utf-8")), shown))
check("and refuses without the key file", not SVN.sign_file(vj, os.path.join(tmp, "nope.key")))
src = open(os.path.join(REPO, "build", "site.py"), encoding="utf-8").read()
check("the site build signs version.json when the key is there", "sign_version" in src)
batch = open(os.path.join(REPO, "BUILD.bat"), encoding="utf-8", errors="replace").read()
check("BUILD.bat says where the key is read from", "EDSMT_SIGNING_KEY" in batch)
check("the key file is never in the repo", not os.path.exists(os.path.join(REPO, "edsmt-signing.key"))
      and "*.key" in open(os.path.join(REPO, ".gitignore"), encoding="utf-8").read())

print()
print("FAILURES:", len(fails))
for f in fails:
    print("  -", f)
sys.exit(1 if fails else 0)
