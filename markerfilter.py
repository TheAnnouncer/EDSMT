"""Which deposits the map and the scope draw (1.10035).

Four settings, remembered between runs:

    map_filter_commodities   a list of commodity names; empty shows them all
    map_filter_amount        Any / Not depleted / Medium or more / High only
    map_filter_density       Any / Medium or more / High only
    map_labels               names beside the deposits on the map and scope

A deposit whose amount or density has not been read cannot be judged against
either, so it stays: a filter is for narrowing what is known, not for hiding
what is not.

No window code: rows in, rows out.
"""

import survey as SV

AMOUNT_CHOICES = ("Any", "Not depleted", "Medium or more", "High only")
DENSITY_CHOICES = ("Any", "Medium or more", "High only")

KEYS = ("map_filter_commodities", "map_filter_amount", "map_filter_density",
        "map_labels")

DEFAULTS = {"map_filter_commodities": [], "map_filter_amount": "Any",
            "map_filter_density": "Any", "map_labels": True}

# Where each choice draws its line, on SV's own scales.
_AMOUNT_MIN = {"not depleted": 1, "medium or more": 2, "high only": 3}
_DENSITY_MIN = {"medium or more": 2, "high only": 3}


def _choice(value, choices):
    text = str(value or "").strip().lower()
    for choice in choices:
        if choice.lower() == text:
            return choice
    return choices[0]


def commodity_list(value):
    """A settings value as a clean list of commodity names: a list, or the
    comma-separated text a box holds."""
    if isinstance(value, str):
        value = value.split(",")
    out, seen = [], set()
    for name in value if isinstance(value, (list, tuple)) else []:
        tidy = SV.canonical(name)
        if tidy and SV.fold(tidy) not in seen:
            seen.add(SV.fold(tidy))
            out.append(tidy)
    return out


def from_settings(settings):
    """The filter, as the dict the map and scope are handed."""
    settings = settings if isinstance(settings, dict) else {}
    return {"commodities": commodity_list(settings.get("map_filter_commodities")),
            "amount": _choice(settings.get("map_filter_amount"), AMOUNT_CHOICES),
            "density": _choice(settings.get("map_filter_density"), DENSITY_CHOICES),
            "labels": bool(settings.get("map_labels", True))}


def to_settings(commodities, amount, density, labels):
    """The four settings values for a choice made in the filter window."""
    return {"map_filter_commodities": commodity_list(commodities),
            "map_filter_amount": _choice(amount, AMOUNT_CHOICES),
            "map_filter_density": _choice(density, DENSITY_CHOICES),
            "map_labels": bool(labels)}


def narrows(flt):
    """True when the filter hides anything at all."""
    flt = flt if isinstance(flt, dict) else {}
    return bool(flt.get("commodities")) or \
        _choice(flt.get("amount"), AMOUNT_CHOICES) != "Any" or \
        _choice(flt.get("density"), DENSITY_CHOICES) != "Any"


def keeps(row, flt):
    """Does the filter keep this map row (a dict with a "deposit")?"""
    deposit = (row.get("deposit") if isinstance(row, dict) else None) or row or {}
    name = str(row.get("commodity") or deposit.get("commodity") or "") \
        if isinstance(row, dict) else ""
    wanted = {SV.fold(n) for n in flt.get("commodities") or ()}
    if wanted and SV.fold(name) not in wanted:
        return False
    amount = str(deposit.get("amount") or "").strip()
    need = _AMOUNT_MIN.get(_choice(flt.get("amount"), AMOUNT_CHOICES).lower())
    if need and amount:
        rank = SV.amount_rank(amount)
        if rank >= 0 and rank < need:
            return False
    density = str(deposit.get("density") or "").strip()
    need = _DENSITY_MIN.get(_choice(flt.get("density"), DENSITY_CHOICES).lower())
    if need and density:
        rank = SV.density_rank(density)
        if rank >= 0 and rank < need:
            return False
    return True


def apply(rows, prefs):
    """The rows the map or scope should draw, given the map preferences it
    was handed (their "filter" entry). All of them when there is none."""
    flt = (prefs or {}).get("filter") if isinstance(prefs, dict) else None
    rows = list(rows or [])
    if not isinstance(flt, dict) or not narrows(flt):
        return rows
    return [row for row in rows if keeps(row, flt)]


def labels_on(prefs):
    """Whether names are drawn beside the deposits."""
    flt = (prefs or {}).get("filter") if isinstance(prefs, dict) else None
    return bool(flt.get("labels", True)) if isinstance(flt, dict) else True


def describe(flt):
    """One line saying what is showing, for the filter window."""
    flt = flt if isinstance(flt, dict) else {}
    bits = []
    if flt.get("commodities"):
        bits.append(", ".join(flt["commodities"]))
    if _choice(flt.get("amount"), AMOUNT_CHOICES) != "Any":
        bits.append("amount: " + _choice(flt.get("amount"), AMOUNT_CHOICES).lower())
    if _choice(flt.get("density"), DENSITY_CHOICES) != "Any":
        bits.append("density: " + _choice(flt.get("density"), DENSITY_CHOICES).lower())
    return "Showing " + ("; ".join(bits) if bits else "every deposit") + \
        ("" if flt.get("labels", True) else " (names off)") + "."
