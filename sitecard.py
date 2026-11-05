"""A site card from Find and Where to land (1.10040, #325).

A site on the community map as a picture: the body's shared finds where
they are, the location asked for in the middle, and one line under it with
what the map knows. The drawing is mapimage's - the same picture as the
session map - so this only decides which rows go on it, what the line says
and what the file is called. Everything here is a plain function.
"""
import time

import mapimage as MI


def _rigs(row):
    try:
        return int(str(row.get("rigs") or "0").strip() or 0)
    except ValueError:
        return 0


def _same(a, b):
    return str(a or "").strip().lower() == str(b or "").strip().lower()


def facts(rows, spot=""):
    """What the map knows about a location (or, with no `spot`, the whole
    body): finds, rigs, the commodities in order of first sighting, who
    found it first, how many are reported worked out, and how many
    locations the body has."""
    mine = [r for r in rows or [] if not spot or _same(r.get("location"), spot)]
    kinds = []
    for r in mine:
        name = str(r.get("commodity") or "").strip()
        if name and name not in kinds:
            kinds.append(name)
    dated = sorted(mine, key=lambda r: str(r.get("when") or ""))
    first = next((str(r.get("cmdr") or "").strip() for r in dated if str(r.get("cmdr") or "").strip()), "")
    return {"finds": len(mine), "rigs": sum(_rigs(r) for r in mine), "commodities": kinds,
            "found_by": first,
            "worked_out": sum(1 for r in mine if str(r.get("amount") or "").lower() == "depleted"),
            "locations": len({str(r.get("location") or "") for r in rows or [] if str(r.get("location") or "")})}


def note(got):
    """The line under the picture."""
    if not got["finds"]:
        return "Nothing shared on this body yet."
    parts = ["%d find%s" % (got["finds"], "" if got["finds"] == 1 else "s"),
             "%d rig%s" % (got["rigs"], "" if got["rigs"] == 1 else "s")]
    parts += got["commodities"][:4]
    line = "Community map: " + ", ".join(parts) + "."
    if got["worked_out"]:
        line += " %d reported worked out." % got["worked_out"]
    if got["found_by"]:
        line += " First found by %s." % got["found_by"]
    return line


def rows_for(rows, spot=""):
    """The rows the picture draws: the location's finds first, then the
    rest of the body marked dim, so the card is about the site and still
    shows the body round it."""
    mine = [dict(r) for r in rows or [] if not spot or _same(r.get("location"), spot)]
    rest = [dict(r, dim=True) for r in rows or [] if spot and not _same(r.get("location"), spot)]
    return mine + rest


def picture_name(system, body, spot="", when=None):
    """site_<system>_<body>_<location>_<yyyymmdd-hhmm>.png, safe on Windows."""
    moment = time.gmtime(when if when is not None else time.time())
    return "site_%s_%s_%s_%s.png" % (MI._clean(system), MI._clean(body), MI._clean(spot or "all", 8),
                                     time.strftime("%Y%m%d-%H%M", moment))
