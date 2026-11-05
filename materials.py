"""Which materials the commodity lists offer (1.10040, #306).

A tick list of the thirteen surface materials and every other one EDSMT
knows decides what the commodity type-ahead and the commodity filters
offer. What is kept is what was left unticked, so a material learnt later
is offered from the start. Every one is offered to begin with.

Pure logic: the app hands in its settings and the names it would offer.
"""
import edonline as EDO
import survey as SV

SETTING = "materials_hidden"
GROUPS = ("The thirteen", "Extras")


def _left_out(settings):
    value = (settings or {}).get(SETTING)
    if not isinstance(value, (list, tuple)):
        return set()
    return {SV.fold(name) for name in value if SV.fold(name)}


def choices(known):
    """[(group, [names])]: the thirteen in their own order, then every other
    material known, once each, worth most first as the lists show them."""
    thirteen = list(EDO.SURFACE_COMMODITIES)
    taken = {SV.fold(name) for name in thirteen}
    extras = []
    for name in known or []:
        key = SV.fold(name)
        if key and key not in taken:
            taken.add(key)
            extras.append(name)
    return [(GROUPS[0], thirteen), (GROUPS[1], extras)]


def is_offered(name, settings):
    return SV.fold(name) not in _left_out(settings)


def offered(names, settings, keep=()):
    """`names` without the ones left unticked. Anything in `keep` - "Any", or
    what the body under you is known to carry - stays whatever the ticks."""
    out = _left_out(settings)
    if not out:
        return list(names)
    kept = {SV.fold(name) for name in keep or ()}
    return [name for name in names if SV.fold(name) in kept or SV.fold(name) not in out]


def hidden_from(ticked, every):
    """What to keep in settings: every name not ticked."""
    chosen = {SV.fold(name) for name in ticked or ()}
    return [name for name in every if SV.fold(name) not in chosen]
