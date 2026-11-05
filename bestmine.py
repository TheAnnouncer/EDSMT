"""What is worth mining here, and what each kind of ground carries (1.10040).

Three questions, one answer to each, in plain functions:

  * what a find, a shared site or one rig of a commodity is worth - the best
    price known for it times what a rig typically brings back (#303);
  * the five commodities worth most in a system, each with where it sells
    best, the bodies here with an intact shared site carrying it, and the
    odds of finding it on the ground here (#303);
  * each kind of ground in a system with the share of shared sites on it
    that carried each commodity (#305).

Pure logic, no toolkit and no network. The app hands in a price source - a
function of a commodity name giving credits a tonne, or (credits, where) -
and what it already knows about the system: the shared sites the server
listed and the Where to land rows.
"""
import planview as PV
import survey as SV

# What a rig brings back, in tonnes. The figure the map's patch values are
# made with, so a value here and a value there can never disagree.
TONNES_PER_RIG = PV.TONNES_PER_RIG
# How many commodities Best to mine names.
TOP = 5


def price(name, price_of):
    """(credits a tonne, where) from a price source, or (0.0, "").

    The source may give a number or a (number, where) pair; one that
    fails, or gives nothing usable, prices the commodity at nothing rather
    than at a guess."""
    try:
        got = price_of(name)
    except Exception:
        return 0.0, ""
    where = ""
    if isinstance(got, (tuple, list)):
        where = str(got[1] or "") if len(got) > 1 else ""
        got = got[0] if got else 0
    try:
        credits = float(got or 0)
    except (TypeError, ValueError):
        return 0.0, ""
    return (credits, where) if credits > 0 else (0.0, "")


def rig_value(name, price_of):
    """Credits one rig of a commodity is worth at its best known price."""
    return price(name, price_of)[0] * TONNES_PER_RIG


def _rigs(value):
    try:
        return max(0, int(float(str(value if value is not None else "").strip() or 0)))
    except (TypeError, ValueError):
        return 0


def find_value(row, price_of):
    """What one find is worth: its rigs at the best known price. Rigs not
    counted yet count as one; a find worked out is worth nothing today."""
    row = row or {}
    if SV.is_depleted(row.get("amount")):
        return 0.0
    name = str(row.get("commodity") or row.get("type") or "").strip()
    if not name:
        return 0.0
    return rig_value(name, price_of) * max(1, _rigs(row.get("rigs")))


def site_value(site, price_of):
    """What a shared site is worth: its rigs at the average value of what it
    carries - the server counts a site's rigs, not each commodity's. A site
    reported worked out is worth nothing."""
    site = site or {}
    if site.get("worked_out"):
        return 0.0
    names = [str(t).strip() for t in (site.get("types") or []) if str(t).strip()]
    if not names:
        return 0.0
    each = sum(rig_value(name, price_of) for name in names) / float(len(names))
    return each * max(1, _rigs(site.get("rigs")))


def _intact_here(sites, system):
    """{commodity folded: (name, [bodies])} for the intact shared sites in a
    system, each body once, in the order the server listed them."""
    out = {}
    wanted = SV.fold(system) if system else None
    for site in sites or []:
        if not isinstance(site, dict) or site.get("worked_out"):
            continue
        if wanted is not None and SV.fold(site.get("system")) != wanted:
            continue
        body = str(site.get("planet") or site.get("body") or "").strip()
        short = SV.short_body(site.get("system") or system, body)
        for name in site.get("types") or []:
            name = SV.canonical(name)
            if not name:
                continue
            entry = out.setdefault(SV.fold(name), (name, []))
            if short and short not in entry[1]:
                entry[1].append(short)
    return out


def _odds_here(rows, grounds):
    """{commodity folded: (name, share, ground, basis)}: the best chance of
    each commodity on any ground in the system, from the same mix Where to
    land's Best bets is made from."""
    out = {}
    for row in rows or []:
        if not isinstance(row, dict) or row.get("landable") is False:
            continue
        ground = str(row.get("ground") or "")
        basis, mix = SV.ground_mix(ground, row.get("planet_class"), grounds)
        for name, share in mix:
            key = SV.fold(name)
            if key not in out or share > out[key][1]:
                out[key] = (name, float(share), ground, basis)
    return out


def best_to_mine(sites, rows, price_of, grounds=None, top=TOP, system=None):
    """The commodities worth most in a system, best first, at most `top`.

    sites   the server's shared sites for the system (/v1/sites rows)
    rows    the Where to land rows for it (survey.rank_bodies)
    grounds the server's /v1/grounds answer, or None

    Each is {"commodity", "price", "where", "value", "bodies", "odds",
    "ground", "basis"}. Ranked by what it is worth here: a rig at its best
    known price, weighed by how likely the ground here is to carry it -
    taken as certain where an intact shared site here already does. A
    commodity nobody has priced is left out: nothing says it is worth the
    drive.
    """
    intact = _intact_here(sites, system)
    odds = _odds_here(rows, grounds)
    out = []
    for key in list(intact) + [k for k in odds if k not in intact]:
        name = intact[key][0] if key in intact else odds[key][0]
        credits, where = price(name, price_of)
        if credits <= 0:
            continue
        bodies = list(intact[key][1]) if key in intact else []
        chance = odds.get(key)
        weight = 1.0 if bodies else (chance[1] if chance else 0.0)
        if weight <= 0:
            continue
        out.append({"commodity": name, "price": credits, "where": where,
                    "value": credits * TONNES_PER_RIG * weight, "bodies": bodies,
                    "odds": chance[1] if chance else None,
                    "ground": chance[2] if chance else "",
                    "basis": chance[3] if chance else ""})
    out.sort(key=lambda item: (-item["value"], -item["price"], item["commodity"].lower()))
    return out[:max(0, int(top))]


def _credits(value):
    return "{:,.0f}".format(float(value or 0))


def best_line(item):
    """One Best to mine line: "Iridium  200,000 Cr at Hub (Ega)  -  on A 1,
    A 2", or the ground odds where no shared site here carries it yet."""
    head = "%s  %s Cr" % (item["commodity"], _credits(item["price"]))
    if item.get("where"):
        head += " " + item["where"] if item["where"].startswith("at ") \
            else " (%s)" % item["where"]
    if item.get("bodies"):
        return head + "  -  intact shared site on " + ", ".join(item["bodies"])
    if item.get("odds") is not None and item.get("ground"):
        percent = int(round(float(item["odds"]) * 100))
        if str(item.get("basis") or "") == "tables":
            return head + "  -  can turn up on %s, by the commodity tables" % item["ground"]
        return head + "  -  %d%% of shared sites on %s" % (percent, item["ground"])
    return head


def by_ground(rows, grounds):
    """Each kind of ground in the system, the most shared sites first.

    rows     the Where to land rows (survey.rank_bodies)
    grounds  the server's /v1/grounds answer, or None

    Each is {"ground", "bodies", "sites", "few", "shares"}: the bodies on it
    (short names), how many shared sites the shares rest on, whether that is
    fewer than Where to land trusts, and [(commodity, share)] highest first.
    """
    table = SV.grounds_by_name(grounds)
    found = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        ground = str(row.get("ground") or "").strip()
        if not ground:
            continue
        entry = found.setdefault(ground.lower(), {"ground": ground, "bodies": []})
        short = str(row.get("short") or row.get("body") or "").strip()
        if short and short not in entry["bodies"]:
            entry["bodies"].append(short)
    out = []
    for key, entry in found.items():
        known = table.get(key) or {}
        try:
            sites = int(known.get("sites") or 0)
        except (TypeError, ValueError):
            sites = 0
        shares = []
        for item in known.get("commodities") or []:
            try:
                share = float(item.get("share") or 0)
            except (TypeError, ValueError, AttributeError):
                continue
            if item.get("name") and share > 0:
                shares.append((str(item["name"]), min(1.0, share)))
        shares.sort(key=lambda pair: (-pair[1], pair[0].lower()))
        out.append(dict(entry, sites=sites, few=0 < sites < SV.LAND_MIN_SITES,
                        shares=shares if sites else []))
    out.sort(key=lambda e: (-e["sites"], e["ground"].lower()))
    return out


def ground_heading(entry):
    """"Rocky body - 9 shared sites (A 1, A 2)"."""
    sites = int(entry.get("sites") or 0)
    text = "%s - %d shared site%s" % (entry["ground"], sites, "" if sites == 1 else "s")
    if entry.get("few"):
        text += ", too few to go by yet"
    if entry.get("bodies"):
        text += " (%s)" % ", ".join(entry["bodies"])
    return text


def share_words(entry):
    """"Haematite 77%, Gold 40%" - the share of the ground's shared sites
    carrying each commodity - or a sentence saying there are none yet."""
    shares = entry.get("shares") or []
    if not shares:
        return "No shared sites on this kind of ground yet."
    return ", ".join("%s %d%%" % (name, int(round(share * 100))) for name, share in shares)
