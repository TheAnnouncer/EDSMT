"""Signed updates (1.10040): Ed25519, in plain Python.

version.json names each build's checksum; the build machine signs those
checksums with a private key that never leaves it, and the app holds only
the public key. A checksum proves a file matches the list; the signature
proves who wrote the list.

This is RFC 8032's Ed25519 in plain Python - slow by library standards and
far fast enough for one signature at each update check - so nothing has to
be installed and nothing goes in the bundle an antivirus has opinions
about. verify() never raises: bad input is simply not a valid signature.
"""
import base64
import hashlib

# The curve, as RFC 8032 section 5.1 states it.
_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_I = pow(2, (_P - 1) // 4, _P)
TAG = "edsmt-update"


def _inv(x):
    return pow(x, _P - 2, _P)


def _recover_x(y, sign):
    if y >= _P:
        return None
    x2 = (y * y - 1) * _inv(_D * y * y + 1) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _I % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


_GY = 4 * _inv(5) % _P
_GX = _recover_x(_GY, 0)
_G = (_GX, _GY, 1, _GX * _GY % _P)


def _add(a, b):
    """Extended twisted Edwards addition."""
    x1, y1, z1, t1 = a
    x2, y2, z2, t2 = b
    aa = (y1 - x1) * (y2 - x2) % _P
    bb = (y1 + x1) * (y2 + x2) % _P
    cc = 2 * t1 * t2 * _D % _P
    dd = 2 * z1 * z2 % _P
    e, f, g, h = bb - aa, dd - cc, dd + cc, bb + aa
    return e * f % _P, g * h % _P, f * g % _P, e * h % _P


def _mul(s, point):
    out = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            out = _add(out, point)
        point = _add(point, point)
        s >>= 1
    return out


def _compress(point):
    x, y, z, _t = point
    zi = _inv(z)
    x, y = x * zi % _P, y * zi % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(raw):
    if len(raw) != 32:
        return None
    y = int.from_bytes(raw, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return x, y, 1, x * y % _P


def _same(a, b):
    x1, y1, z1, _ = a
    x2, y2, z2, _ = b
    return (x1 * z2 - x2 * z1) % _P == 0 and (y1 * z2 - y2 * z1) % _P == 0


def _secret_scalar(secret):
    h = hashlib.sha512(secret).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def public_key(secret):
    """The 32-byte public key of a 32-byte secret."""
    a, _prefix = _secret_scalar(bytes(secret))
    return _compress(_mul(a, _G))


def sign(secret, message):
    """A 64-byte signature of `message` by the 32-byte secret."""
    secret, message = bytes(secret), bytes(message)
    a, prefix = _secret_scalar(secret)
    pub = _compress(_mul(a, _G))
    r = int.from_bytes(hashlib.sha512(prefix + message).digest(), "little") % _L
    rs = _compress(_mul(r, _G))
    k = int.from_bytes(hashlib.sha512(rs + pub + message).digest(), "little") % _L
    s = (r + k * a) % _L
    return rs + int.to_bytes(s, 32, "little")


def verify(public, message, signature):
    """Whether `signature` is `message` signed by the holder of `public`.
    Never raises."""
    try:
        public, message, signature = bytes(public), bytes(message), bytes(signature)
        if len(public) != 32 or len(signature) != 64:
            return False
        pub = _decompress(public)
        rs = _decompress(signature[:32])
        if pub is None or rs is None:
            return False
        s = int.from_bytes(signature[32:], "little")
        if s >= _L:
            return False
        k = int.from_bytes(hashlib.sha512(signature[:32] + public + message).digest(), "little") % _L
        return _same(_mul(s, _G), _add(rs, _mul(k, pub)))
    except Exception:
        return False


# ---------------------------------------------------------------- version.json

def encode(raw):
    return base64.b64encode(bytes(raw)).decode("ascii")


def decode(text):
    try:
        return base64.b64decode(str(text or "").strip().encode("ascii"), validate=True)
    except Exception:
        return b""


def message_for(data):
    """What is signed: the version and each kind of build's checksum, in a
    fixed order, so nothing else in the file can be swapped unseen."""
    lines = [TAG, str((data or {}).get("version") or "")]
    for kind in ("installer", "portable"):
        pkg = (data or {}).get(kind)
        if isinstance(pkg, dict) and pkg.get("sha256"):
            lines.append("%s %s" % (kind, str(pkg["sha256"]).strip().lower()))
    return ("\n".join(lines) + "\n").encode("utf-8")


def sign_version(data, secret):
    """version.json's contents with its signature added."""
    out = dict(data)
    out["signature"] = encode(sign(secret, message_for(data)))
    return out


def verified(data, public_text):
    """Whether version.json's contents carry a good signature by the key in
    `public_text`. With no public key set there is nothing to check, and
    the answer is yes - the app before the key existed."""
    if not str(public_text or "").strip():
        return True
    if not isinstance(data, dict):
        return False
    return verify(decode(public_text), message_for(data), decode(data.get("signature")))


def read_secret(path):
    """The 32-byte secret in a key file (its one line, base64)."""
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith("#"):
                raw = decode(line)
                if len(raw) == 32:
                    return raw
    raise ValueError("no key in %s" % path)
