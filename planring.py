"""The planning circle (1.10040, #215).

A 4.5 km ring put down on the map with a right-click: rig and drive inside
it and no rig is ever far enough away for the game to take it - it destroys
a rig left 5 km behind, and 4.5 km leaves room for the drive back. Kept as a
place on the body, so it stays where it was put while you drive, and shown
on the map and on the overlay's scope.

Plain logic: no window.
"""
import math

import survey as SV

RADIUS_M = 4500.0


def make(system, body, lat, lon):
    """The circle, centred on (lat, lon) on this body; None without a place."""
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not system or not body or not (-90.0 <= lat <= 90.0):
        return None
    return {"system": str(system), "body": str(body), "lat": lat, "lon": lon}


def place_at(system, body, east_m, north_m, lat, lon, radius_m):
    """The circle centred `east_m`, `north_m` from (lat, lon) - where a
    right-click on the map landed, measured from you."""
    if not radius_m:
        return None
    distance = math.hypot(float(east_m), float(north_m))
    bearing = math.degrees(math.atan2(float(east_m), float(north_m))) % 360.0
    plat, plon = SV.destination(float(lat), float(lon), bearing, distance, float(radius_m))
    return make(system, body, plat, plon)


def offset(ring, system, body, lat, lon, radius_m):
    """Where the circle's centre is from (lat, lon), as (east, north) in
    metres, or None when it is on another body or cannot be placed."""
    if not isinstance(ring, dict) or not radius_m or lat is None or lon is None:
        return None
    if ring.get("system") != system or ring.get("body") != body:
        return None
    try:
        per_degree = (2.0 * math.pi * float(radius_m)) / 360.0
        east = (float(ring["lon"]) - float(lon)) * per_degree * math.cos(math.radians(float(lat)))
        north = (float(ring["lat"]) - float(lat)) * per_degree
    except (KeyError, TypeError, ValueError):
        return None
    # Across the date line the short way round.
    half = 180.0 * per_degree * math.cos(math.radians(float(lat)))
    if east > half:
        east -= 2 * half
    elif east < -half:
        east += 2 * half
    return east, north


def room_m(centre):
    """From you to the circle's edge, in metres: how far you can still go
    from its centre outward when inside (positive), how far outside you are
    (negative)."""
    if centre is None:
        return None
    return RADIUS_M - math.hypot(centre[0], centre[1])


def words(centre):
    """The circle in a few words for the map's footer and the scope."""
    room = room_m(centre)
    if room is None:
        return ""
    if room >= 0:
        return "Planning circle: %s to its edge" % distance_text(room)
    return "Outside the planning circle by %s" % distance_text(-room)


def distance_text(metres):
    return "%.1f km" % (metres / 1000.0) if metres >= 1000 else "%d m" % int(round(metres))
