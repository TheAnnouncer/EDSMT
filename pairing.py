"""Pairing EDSMT with the commander's member page on radioraxxla.com (1.10040).

The member page - sign in with Discord, then Tools - makes a pairing code:
eight letters and digits such as PWP4-ZQMA, good for one use and ten
minutes. EDSMT hands the code in once and gets a token back once; the member
page keeps only a fingerprint of it, lists the computer, and revokes it.

Everything here is a plain function. The network call is handed in, so the
checks never reach the member page; the window that asks for the code is
thin wiring in edsmt.py.
"""
import json
import re

CLAIM_URL = "https://join.radioraxxla.com/pair/claim"
PORTAL_URL = "https://radioraxxla.com/portal.html#tools"
TOOL = "edsmt"
# The worker's tag for the claim, so its answer is never shown as it came.
TAG = "pairing"
# The member page's own alphabet: no I, O, 0 or 1, so a code read out loud
# or off a stream is typed right.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LENGTH = 8
NAME_MOST = 40
TOKEN_LEAST, TOKEN_MOST = 20, 100
EXAMPLE = "PWP4-ZQMA"
TIMEOUT_S = 20.0


def normalise(code):
    """The code as the member page reads it: capitals, no spaces or dashes."""
    return re.sub(r"[\s-]", "", str(code or "")).upper()


def looks_right(code):
    """Eight of the member page's letters and digits."""
    code = normalise(code)
    return len(code) == LENGTH and all(ch in ALPHABET for ch in code)


def shown(code):
    """PWP4ZQMA as the member page shows it: PWP4-ZQMA."""
    code = normalise(code)
    return code[:4] + "-" + code[4:] if len(code) == LENGTH else code


def device_name(computer):
    """How the member page lists this computer: "EDSMT on <its name>"."""
    name = "".join(ch for ch in str(computer or "") if ch.isprintable() and not ch.isspace())
    return ("EDSMT on " + name if name else "EDSMT")[:NAME_MOST]


CMDR_MOST = 40


def claim_body(code, name, cmdr=""):
    """What is sent: the code, the tool and the computer's name - and the
    journal's commander name when EDSMT has read one, so the member page can
    take it from the app rather than a typed box. Nothing else."""
    body = {"code": normalise(code), "tool": TOOL, "device_name": str(name or "")[:NAME_MOST]}
    who = " ".join(str(cmdr or "").split())[:CMDR_MOST]
    if who:
        body["cmdr"] = who
    return body


def read_claim(reply):
    """{"token", "device"} from the member page's answer. Anything EDSMT
    cannot use raises RuntimeError, in words for the commander."""
    if isinstance(reply, dict):
        token, device = reply.get("token"), reply.get("device_id")
        tool = str(reply.get("tool") or TOOL).lower()
        if (isinstance(token, str) and TOKEN_LEAST <= len(token) <= TOKEN_MOST
                and isinstance(device, str) and 0 < len(device) <= 40 and tool == TOOL):
            return {"token": token, "device": device}
    raise RuntimeError("The member page sent back nothing EDSMT can use. "
                       "Make a new code and try again.")


def claim_job(code, name, post, cmdr=""):
    """The worker's job: hand the code in with `post` (edonline.post_json)
    and return the token and device as JSON."""
    body = claim_body(code, name, cmdr)
    return lambda: json.dumps(read_claim(post(CLAIM_URL, body, timeout=TIMEOUT_S)))


_REFUSED = re.compile(r"^\S+ refused it \(HTTP \d+\): ")
_TOKENISH = re.compile(r"[A-Za-z0-9_-]{%d,}" % TOKEN_LEAST)


def explain(message):
    """A failed claim in the member page's own words, without the HTTP
    wrapping - and never anything that could be a token."""
    text = str(message or "").strip()
    if text.lower().startswith("could not reach"):
        text = ("Could not reach the member page (%s). Check the connection "
                "and try again." % text.split(":", 1)[-1].strip())
    text = _REFUSED.sub("", text)
    return _TOKENISH.sub("[removed]", text)


def paired(settings):
    """Whether this computer holds a pairing."""
    return isinstance(settings, dict) and bool(str(settings.get("portal_token") or "").strip())


def forget(settings):
    """The settings without the pairing. The member page still lists the
    computer until it is revoked there."""
    out = dict(settings or {})
    out["portal_token"] = ""
    out["portal_device"] = ""
    return out
