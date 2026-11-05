"""The ship minimap (1.10040, #126).

Flying low over a body with finds on the map, the scope comes up by itself
in the ship: the body's sites round the ship, the range widened to suit a
ship's speed and height. Plain functions; the app wires them into when the
boxes are wanted and how far the scope reaches.
"""

# Below this height above the ground the scope comes up in the ship. The
# journal blanks the height in orbital cruise (it is measured from the
# body's average radius there), so nothing is drawn from orbit.
MINIMAP_ALTITUDE_M = 10000.0
# A ship sees further than a Rhino: the floor is twice the height, capped.
MINIMAP_RANGE_CAP_M = 15000.0


def _height(state):
    try:
        return float(getattr(state, "altitude", None))
    except (TypeError, ValueError):
        return None


def minimap_wanted(settings, state, has_rows):
    """Whether the scope should be up in the ship this moment: the switch
    on (it is, unless turned off), in the main ship, not landed or on foot,
    a position and a height above the ground below MINIMAP_ALTITUDE_M, and
    something on the body to draw."""
    if not (settings or {}).get("ship_minimap", True) or not has_rows or state is None:
        return False
    if not getattr(state, "in_ship", False) or getattr(state, "in_srv", False) \
            or getattr(state, "on_foot", False) or getattr(state, "landed", False):
        return False
    if not getattr(state, "has_position", False) or getattr(state, "altitude_from_average", False):
        return False
    height = _height(state)
    return height is not None and 0 <= height <= MINIMAP_ALTITUDE_M


def range_floor_m(altitude_m, floor_m):
    """How far the scope reaches at least, in the ship: the scope's own
    floor on the ground, twice the height up to the cap."""
    try:
        height = float(altitude_m)
    except (TypeError, ValueError):
        return float(floor_m)
    return max(float(floor_m), min(MINIMAP_RANGE_CAP_M, height * 2.0))


def caption(altitude_m):
    """The scope's header in the ship."""
    try:
        height = float(altitude_m)
    except (TypeError, ValueError):
        return "ship"
    if height >= 1000:
        return "ship · %.1f km up" % (height / 1000.0)
    return "ship · %d m up" % round(height)
