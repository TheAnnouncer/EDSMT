"""One mining signal as a CSV file (1.10040, #216).

Everything EDSMT knows about one Planetary Mining Location signal, in one
file a spreadsheet or a map tool can open: where the signal was logged, the
survey centre and border, every deposit marked in it, each traced deposit
edge with its rig pins, and the line the SRV drove.

One row per thing. The first column says which:

    export   the app, its version, the file format and when it was written
    signal   where the signal was logged and what it says is inside
    centre   the survey centre
    border   the survey centre again, with the border's radius in metres
    deposit  one marked deposit
    trace    one point of a traced deposit edge, in driving order
    pin      one planned rig, with the spacing it was planned at
    drive    one point of the line the SRV drove, in order

`group` ties a trace to its pins, and a border to its centre, when there is
more than one. Text a spreadsheet would run as a formula goes in with a
leading apostrophe; numbers go in as numbers.

Pure: rows in, rows out, and one function that writes the file.
"""
import csv
import math
import os
import re

import rigplan as RP
import survey as SV

FORMAT = 1
COLUMNS = ("kind", "group", "seq", "system", "body", "signal", "lat", "lon", "metres",
           "commodity", "density", "amount", "rigs", "rigs_fit", "status", "cmdr",
           "recorded", "notes")
KINDS = ("export", "signal", "centre", "border", "deposit", "trace", "pin", "drive")
# A map or plan this close to where the signal was logged belongs to it,
# whatever number it was saved under: the same reach the map uses.
REACH_M = 8000.0
# What a spreadsheet takes as the start of a formula.
_FORMULA = ("=", "+", "-", "@", "\t", "\r")
_UNSAFE_NAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def _text(value):
    """Text for a cell, never something a spreadsheet would run."""
    text = " ".join(str(value if value is not None else "").split())
    if text.startswith(_FORMULA):
        return "'" + text
    return text


def _float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _coord(value):
    number = _float(value)
    return "" if number is None else "%.6f" % number


def _metres(value):
    number = _float(value)
    return "" if number is None else "%.1f" % number


def _row(kind, location, **cells):
    row = {name: "" for name in COLUMNS}
    row["kind"] = kind
    row["system"] = _text(location.get("system"))
    row["body"] = _text(location.get("body"))
    row["signal"] = _text(location.get("location"))
    for name, value in cells.items():
        if name in ("lat", "lon"):
            row[name] = _coord(value)
        elif name == "metres":
            row[name] = _metres(value)
        elif name in ("group", "seq"):
            row[name] = "" if value in (None, "") else str(int(value))
        else:
            row[name] = _text(value)
    return row


def _key(value):
    """Names compared the way the survey compares them: trimmed, any case."""
    return " ".join(str(value or "").split()).lower()


def _where(location):
    lat, lon = _float(location.get("lat")), _float(location.get("lon"))
    return None if lat is None or lon is None else (lat, lon)


def _within(here, there, radius_m, reach_m):
    if here is None or there is None or not radius_m:
        return False
    return SV.surface_range_m(here[0], here[1], there[0], there[1], radius_m) <= reach_m


def pick_maps(maps, location, radius_m=None, reach_m=REACH_M):
    """The survey maps that belong to this signal: those saved under its
    number, else those whose centre (or first point) is within reach of
    where it was logged."""
    number = str(location.get("location") or "").strip()
    system, body = _key(location.get("system")), _key(location.get("body"))
    here = _where(location)
    named, near = [], []
    for cmap in maps or []:
        if _key(getattr(cmap, "system", "")) != system or _key(getattr(cmap, "body", "")) != body:
            continue
        if number and str(getattr(cmap, "signal", "") or "").strip() == number:
            named.append(cmap)
            continue
        anchor = getattr(cmap, "centre", None) or (cmap.points[0] if getattr(cmap, "points", None) else None)
        if _within(here, anchor, radius_m or getattr(cmap, "radius_m", 0), reach_m):
            near.append(cmap)
    return named or near


def pick_plans(plans, location, deposit_ids, radius_m=None, reach_m=REACH_M):
    """The rig plans that belong to this signal: those linked to one of its
    deposits, and those whose middle is within reach of where it was logged."""
    system, body = _key(location.get("system")), _key(location.get("body"))
    here = _where(location)
    out = []
    for plan in plans or []:
        if _key(plan.get("system")) != system or _key(plan.get("body")) != body:
            continue
        if plan.get("deposit") and plan["deposit"] in deposit_ids:
            out.append(plan)
        elif not plan.get("deposit") and _within(here, RP.plan_centre(plan),
                                                   radius_m or plan.get("radius_m"), reach_m):
            out.append(plan)
    return out


def _offers(location):
    offered = SV.Survey.offered(location)
    gone = {SV.fold(c) for c in SV.Survey.worked_out(location)}
    return "; ".join("%s (depleted)" % c if SV.fold(c) in gone else c for c in offered)


def _trail(cmap):
    try:
        return list(cmap.trail())
    except (AttributeError, TypeError, ValueError):
        return list(getattr(cmap, "points", None) or [])


def rows(location, deposits, maps=(), plans=(), version="", when=None):
    """Every row of the file, as dicts with COLUMNS for keys, in order."""
    location = location or {}
    radius = _float(location.get("radius_m"))
    out = [_row("export", location, recorded=when or SV.utc_now(),
                notes="EDSMT %s, signal export format %d" % (version, FORMAT))]
    out.append(_row("signal", location, lat=location.get("lat"), lon=location.get("lon"),
                    commodity=_offers(location), cmdr=location.get("cmdr"),
                    recorded=location.get("recorded"), notes=location.get("notes")))
    mine = pick_maps(maps, location, radius)
    for group, cmap in enumerate(mine, start=1):
        centre = getattr(cmap, "centre", None)
        if centre is None:
            continue
        tag = group if len(mine) > 1 else None
        out.append(_row("centre", location, group=tag, lat=centre[0], lon=centre[1]))
        if getattr(cmap, "border_m", None):
            out.append(_row("border", location, group=tag, lat=centre[0], lon=centre[1],
                            metres=cmap.border_m))
    ordered = sorted(deposits or [], key=lambda d: (str(d.get("recorded") or ""), str(d.get("id") or "")))
    for deposit in ordered:
        out.append(_row("deposit", location, lat=deposit.get("lat"), lon=deposit.get("lon"),
                        commodity=deposit.get("commodity"), density=deposit.get("density"),
                        amount=deposit.get("amount"), rigs=deposit.get("rigs"),
                        rigs_fit=deposit.get("rigs_fit"), status=deposit.get("status"),
                        cmdr=deposit.get("cmdr"), recorded=deposit.get("recorded"),
                        notes=deposit.get("notes")))
    by_id = {d.get("id"): d for d in ordered if d.get("id")}
    for group, plan in enumerate(pick_plans(plans, location, set(by_id), radius), start=1):
        for seq, point in enumerate(plan.get("outline") or [], start=1):
            out.append(_row("trace", location, group=group, seq=seq, lat=point[0], lon=point[1]))
        what = (by_id.get(plan.get("deposit")) or {}).get("commodity", "")
        for pin in plan.get("pins") or []:
            out.append(_row("pin", location, group=group, seq=pin.get("n"), lat=pin.get("lat"),
                            lon=pin.get("lon"), metres=plan.get("spacing"), commodity=what))
    for group, cmap in enumerate(mine, start=1):
        tag = group if len(mine) > 1 else None
        for seq, point in enumerate(_trail(cmap), start=1):
            out.append(_row("drive", location, group=tag, seq=seq, lat=point[0], lon=point[1]))
    return out


def file_name(location):
    """EDSMT signal - <system> - <body> - <number>.csv, safe on Windows."""
    parts = [str((location or {}).get(key) or "").strip() or "unknown"
             for key in ("system", "body", "location")]
    name = "EDSMT signal - %s.csv" % " - ".join(parts)
    return _UNSAFE_NAME.sub("_", name)


def write(path, table):
    """Write the rows; True when the file is there. UTF-8 with a byte-order
    mark, so a spreadsheet reads commander names with accents right."""
    temp = path + ".tmp"
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(temp, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\r\n")
            writer.writeheader()
            for row in table:
                writer.writerow({name: row.get(name, "") for name in COLUMNS})
        os.replace(temp, path)
        return True
    except OSError:
        try:
            os.remove(temp)
        except OSError:
            pass
        return False
