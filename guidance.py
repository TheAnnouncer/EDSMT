"""Where to go next, said on the map, the scope and the compass (1.10035).

Four pieces of guidance, each with a switch in Settings:

  the guided survey   numbered waypoints over the survey area, one at a time
  the Rhino pointer   on foot, or in the ship near the ground: where the Rhino
                      was left; in the Rhino: where the ship came down
  the orbit line      in the ship on the way down: how far, and which way, to
                      the deposit being driven to, or to the signal
  the rig plans       the pins and traced edge kept with the deposit, and how
                      many rigs fit on it

This is the application's half of it, as a mixin so that it stays out of the
window's own file; the geometry is in waypoints.py and rigplan.py and needs
no window. Everything here is handed to the drawing code as plain data in
metres east and north of the commander.
"""

import math
import time

import survey as SV
import rigplan as RP
import waypoints as WP

# The four waypoint actions. Unbound until the commander picks a key in
# Settings > Keys: nothing here takes a key another action may already use.
WAYPOINT_KEYS = (("hotkey_wp_next", ""),
                 ("hotkey_wp_back", ""),
                 ("hotkey_wp_skip", ""),
                 ("hotkey_wp_pause", ""))
# A kept rig plan is brought back when the commander is within this of it.
PLAN_RESTORE_M = 600.0
# A deposit marked this close to a kept plan's middle is on that plan.
PLAN_DEPOSIT_M = 150.0
# How often a body's kept plans are looked through, at most.
PLAN_LOOK_S = 3.0


def distance_text(metres):
    """The same distances the map prints: 640 m, 1.50 km, 25 km."""
    try:
        value = float(metres)
    except (TypeError, ValueError):
        return "-"
    if value >= 10000:
        return "{:,.0f} km".format(value / 1000.0)
    if value >= 1000:
        return "%.2f km" % (value / 1000.0)
    return "%.0f m" % value


def say_where(label, east, north, extra=""):
    """"WP 3/12: 1.50 km, bearing 087" from a place east and north of the
    commander, and the numbers it was made from."""
    away = math.hypot(east, north)
    bearing = math.degrees(math.atan2(east, north)) % 360.0
    return {"text": "%s: %s, bearing %03d%s" % (label, distance_text(away),
                                                 int(round(bearing)) % 360, extra),
            "range_m": away, "bearing": bearing, "east": east, "north": north}


def _get(obj, name, default=None):
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def _own(obj, name, default=None):
    """What was really assigned to the window, or the default. A plain
    getattr() would be answered by a catch-all __getattr__ (the headless
    stubs, Tk's option machinery) for a part that was never built."""
    try:
        return vars(obj).get(name, default)
    except TypeError:
        return default


class GuidanceMixin:
    """Mixed into the application window. Every method is safe to call at
    any time: with nothing to guide to, it answers None and draws nothing."""

    # -- set up ------------------------------------------------------------

    def guide_init(self, folder):
        self.waypoint_book = WP.WaypointBook(folder)
        self.plan_book = RP.PlanBook(folder)
        self._wp_guide = None
        self._plan_looked = (None, 0.0)

    def _switch_on(self, name, default=True):
        return bool((_own(self, "settings", None) or {}).get(name, default))

    def wp_arrive_m(self):
        return WP.arrive_radius((_own(self, "settings", None) or {}).get(
            "waypoint_radius_m", WP.ARRIVE_M))

    # -- the guided survey ---------------------------------------------------

    def wp_guide(self, cmap, state=None, create=True):
        """The guide for the live survey map: the saved one for this body
        when it was built from the same centre and border, else a new one.
        None when there is no centre and border yet, or the switch is off."""
        if not self._switch_on("survey_guide") or cmap is None:
            return None
        if cmap.centre is None or not cmap.border_m or not cmap.radius_m:
            return None
        key = WP.area_key(cmap.centre, cmap.border_m, cmap.scan_m)
        book = _own(self, "waypoint_book", None)
        if book is None:
            return None
        guide = _own(self, "_wp_guide", None)
        if guide is None or guide.key != key or \
                (guide.system, guide.body) != (cmap.system, cmap.body):
            guide = book.get(cmap.system, cmap.body)
            if guide is not None and guide.key != key:
                guide = None
            self._wp_guide = guide
        if guide is None and create:
            start = 0.0
            if state is not None and _get(state, "has_position", False):
                start = SV.bearing_deg(cmap.centre[0], cmap.centre[1], state.lat, state.lon)
            points = WP.build(cmap.centre, cmap.border_m, cmap.radius_m, cmap.scan_m,
                              swept=cmap.swept_at, start_bearing=start)
            guide = WP.Guide(cmap.system, cmap.body, key, points)
            book.put(guide)
            book.save()
            self._wp_guide = guide
        return guide

    def wp_track(self, state, cmap):
        """Every tick in the Rhino: build the waypoints when the area is
        set, and move on when the current one has been reached. Never
        raises - a fault here must not cost the survey its painting."""
        try:
            if not _get(state, "in_srv", False):
                return False
            guide = self.wp_guide(cmap, state)
            if guide is None:
                return False
            before = guide.index, guide.done
            moved = guide.update(state.lat, state.lon, state.radius_m,
                                 self.wp_arrive_m(), swept=cmap.swept_at)
            if moved:
                self.waypoint_book.save()
                self.wp_said(guide, before)
            return moved
        except Exception as exc:
            self.trouble("Guided survey", exc)
            return False

    def wp_said(self, guide, before=None):
        if guide.done:
            left = len(guide.skipped)
            if left:
                self.flash("SURVEY COMPLETE", "%d skipped" % left)
                return self.say("Guided survey: finished, %d waypoint%s skipped." % (
                    left, "" if left == 1 else "s"), WP_GREEN)
            self.flash("SURVEY COMPLETE", "every waypoint reached")
            return self.say("Guided survey: every waypoint reached.", WP_GREEN)
        self.flash(guide.label(), "next waypoint")
        return self.say("Guided survey: on to %s." % guide.label(), WP_GREEN)

    def _wp_key_guide(self):
        cmap = self._survey_map()
        guide = self.wp_guide(cmap, _own(self, "game", None), create=True) if cmap else None
        if guide is None:
            self.say("No survey to guide yet - log the signal, then drive to "
                     "the edge and set the border. Then the waypoints come.", WP_AMBER)
        return guide

    def wp_next(self):
        guide = self._wp_key_guide()
        if guide is None:
            return False
        cmap = self._survey_map()
        if guide.done:
            return self.say("Guided survey: every waypoint has been reached.", WP_GREEN)
        guide.advance(cmap.swept_at if cmap else None)
        self.waypoint_book.save()
        self.wp_said(guide)
        self.redraw()
        return True

    def wp_skip(self):
        """Leave the waypoint out - a cliff or a crater in the way - and go
        to the next. Remembered, and counted at the end."""
        guide = self._wp_key_guide()
        if guide is None:
            return False
        cmap = self._survey_map()
        if guide.done:
            return self.say("Guided survey: every waypoint has been reached.", WP_GREEN)
        left = guide.label()
        guide.skip(cmap.swept_at if cmap else None)
        self.waypoint_book.save()
        if guide.done:
            self.wp_said(guide)
        else:
            self.flash(guide.label(), "%s skipped" % left)
            self.say("Guided survey: %s skipped, on to %s." % (left, guide.label()), WP_GREEN)
        self.redraw()
        return True

    def wp_back(self):
        guide = self._wp_key_guide()
        if guide is None:
            return False
        if not guide.back():
            return self.say("Guided survey: this is the first waypoint.", WP_AMBER)
        self.waypoint_book.save()
        self.flash(guide.label(), "back one waypoint")
        self.say("Guided survey: back to %s." % guide.label(), WP_GREEN)
        self.redraw()
        return True

    def wp_pause(self):
        guide = self._wp_key_guide()
        if guide is None:
            return False
        paused = guide.toggle_pause()
        self.waypoint_book.save()
        self.flash("WAYPOINTS PAUSED" if paused else "WAYPOINTS ON",
                   "the same key starts them again" if paused else guide.label())
        self.say("Guided survey %s." % ("paused" if paused else "running again"), WP_GREEN)
        self.redraw()
        return True

    # -- what is handed to the drawing code ----------------------------------

    def guidance_wanted(self):
        """True when there is something to point at outside the Rhino - the
        Rhino left on the ground, or a deposit or signal to come down to in
        the ship - and its switch is on. It keeps the boxes up where "only in
        the Rhino" would take them down, because pointing back at a parked
        Rhino from a box that is not there is no pointer."""
        state = _own(self, "game", None)
        if state is None or not _get(state, "has_position", False) or \
                _get(state, "in_srv", False):
            return False
        system, body = self.here()
        if not (system and body):
            return False
        parked = _get(state, "rhino_parked", None)
        if self._switch_on("rhino_pointer") and parked and \
                str(parked.get("body", "")).lower() == str(body).lower():
            return True
        if self._switch_on("orbit_guide") and _get(state, "in_ship", False) \
                and not _get(state, "on_foot", False) and not _get(state, "landed", False):
            return self._orbit_target(system, body, lambda lat, lon: (0.0, 0.0)) is not None
        return False

    def guidance_view(self, state, centre, radius):
        """What the map, the scope and the compass draw for guidance, in
        metres east and north of `centre` (where the commander is), or None
        when there is nothing to say. Never raises."""
        try:
            return self._guidance_view(state, centre, radius)
        except Exception as exc:
            self.trouble("Guidance", exc)
            return None

    def _guidance_view(self, state, centre, radius):
        if state is None or centre is None or not radius or \
                not _get(state, "has_position", False):
            return None
        system, body = self.here()
        if not (system and body):
            return None

        def rel(lat, lon):
            return SV.local_offset(centre[0], centre[1], lat, lon, radius)

        out = {}
        if _get(state, "in_srv", False):
            found = self._wp_view(rel, system, body, state)
            if found:
                out["wp"] = found
            if self._switch_on("rhino_pointer"):
                ship = self._pointer(rel, _get(state, "ship_down", None), body, "SHIP")
                if ship:
                    out["ship"] = ship
        else:
            if self._switch_on("rhino_pointer"):
                parked = self._pointer(rel, _get(state, "rhino_parked", None), body, "RHINO")
                if parked:
                    out["rhino"] = parked
            if self._switch_on("orbit_guide") and _get(state, "in_ship", False) \
                    and not _get(state, "on_foot", False):
                orbit = self._orbit_line(rel, state, system, body)
                if orbit:
                    out["orbit"] = orbit
        return out or None

    def _wp_view(self, rel, system, body, state):
        cmap = self._survey_map()
        if cmap is None or (cmap.system, cmap.body) != (system, body):
            return None
        guide = self.wp_guide(cmap, state, create=False)
        if guide is None or not guide.waypoints:
            return None
        points = []
        for at, point in enumerate(guide.waypoints):
            east, north = rel(point["lat"], point["lon"])
            if guide.done or at < guide.index:
                mark = "done"
            elif at == guide.index:
                mark = "current"
            else:
                mark = "todo"
            points.append({"n": point["n"], "east": east, "north": north, "state": mark})
        if guide.done:
            text = "SURVEY COMPLETE"
            if guide.skipped:
                text += " (%d skipped)" % len(guide.skipped)
            return {"complete": True, "text": text, "total": guide.total,
                    "points": points, "paused": False}
        point = guide.current()
        east, north = rel(point["lat"], point["lon"])
        view = say_where("%s%s" % (guide.label(), " (paused)" if guide.paused else ""),
                         east, north)
        view.update(complete=False, n=point["n"], total=guide.total,
                    paused=guide.paused, points=points,
                    arrive_m=self.wp_arrive_m())
        return view

    def _pointer(self, rel, spot, body, label):
        """The Rhino's parked spot, or the ship's, as a pointer - only for
        this body."""
        if not spot or str(spot.get("body", "")).lower() != str(body).lower():
            return None
        try:
            east, north = rel(float(spot["lat"]), float(spot["lon"]))
        except (KeyError, TypeError, ValueError):
            return None
        view = say_where(label, east, north)
        view["label"] = label
        return view

    def _orbit_target(self, system, body, rel):
        """The deposit being driven to, else the signal's centre: (label, east,
        north), or None."""
        store = _own(self, "store", None)
        picked = _own(self, "_guide_to", None)
        if store is not None and picked:
            for row in store.at(system, body):
                if str(row.get("id")) == str(picked):
                    try:
                        east, north = rel(float(row["lat"]), float(row["lon"]))
                    except (KeyError, TypeError, ValueError):
                        break
                    return "TO %s" % (str(row.get("commodity") or "DEPOSIT").upper()[:14]), east, north
        place = None
        signal = str(self.signal() or "")
        if store is not None:
            logged = store.location(system, body, signal)
            if logged:
                try:
                    place = (float(logged["lat"]), float(logged["lon"]))
                except (KeyError, TypeError, ValueError):
                    place = None
        cmap = self._survey_map()
        if place is None and cmap is not None and (cmap.system, cmap.body) == (system, body) \
                and cmap.centre is not None:
            place = cmap.centre
        if place is None:
            return None
        east, north = rel(*place)
        return "TO SIGNAL %s" % signal if signal else "TO SIGNAL", east, north

    def _orbit_line(self, rel, state, system, body):
        found = self._orbit_target(system, body, rel)
        if not found:
            return None
        label, east, north = found
        extra = ""
        height = _get(state, "altitude", None)
        if height is not None:
            extra = ", alt %s" % distance_text(height)
        view = say_where(label, east, north, extra)
        view["label"] = label
        return view

    # -- rig plans: kept with the deposit --------------------------------------

    def save_rig_plan(self, plan, state=None):
        """Keep a plan just made, with the deposit it is on, and its fit."""
        book = _own(self, "plan_book", None)
        state = state or _own(self, "game", None)
        if book is None or not plan or state is None:
            return False
        record = dict(plan, radius_m=_get(state, "radius_m", 0.0) or 0.0)
        record["outline"] = [tuple(p) for p in plan.get("outline") or []]
        middle = RP.plan_centre(record)
        deposit = self._deposit_near(plan["system"], plan["body"], middle, PLAN_DEPOSIT_M,
                                     record["radius_m"]) if middle else None
        if deposit is not None:
            record["deposit"] = str(deposit.get("id") or "")
        saved = book.put(record)
        if deposit is not None and record.get("fit"):
            self.store.update_deposit(deposit["id"], rigs_fit=str(int(record["fit"])))
        return saved

    def _deposit_near(self, system, body, spot, within_m, radius):
        store = _own(self, "store", None)
        if store is None or not spot or not radius:
            return None
        best = None
        for row in store.at(system, body):
            try:
                away = SV.surface_range_m(spot[0], spot[1], float(row["lat"]),
                                          float(row["lon"]), radius)
            except (KeyError, TypeError, ValueError):
                continue
            if away <= within_m and (best is None or away < best[0]):
                best = (away, row)
        return best[1] if best else None

    def restore_plan(self):
        """Bring back the rig plan kept for the ground the commander is on,
        when there is none up. Looked for every few seconds at most."""
        state = _own(self, "game", None)
        book = _own(self, "plan_book", None)
        if book is None or state is None or not _get(state, "has_position", False) \
                or not _get(state, "radius_m", None):
            return None
        system, body = self.here()
        if not (system and body):
            return None
        current = _own(self, "rig_plan", None)
        where = (str(system).lower(), str(body).lower())
        if current and (current.get("system"), current.get("body")) == where:
            middle = RP.plan_centre(current)
            if middle and math.hypot(*RP.to_local((state.lat, state.lon), middle,
                                                  state.radius_m)) <= PLAN_RESTORE_M * 2.5:
                return None
        looked = _own(self, "_plan_looked", (None, 0.0))
        now = time.time()
        if looked[0] == where and now - looked[1] < PLAN_LOOK_S:
            return None
        self._plan_looked = (where, now)
        found = book.nearest(system, body, state.lat, state.lon, state.radius_m,
                             PLAN_RESTORE_M)
        if found is None:
            return None
        self.rig_plan = dict(found, restored=True)
        return self.rig_plan

    def rigs_fit_here(self, state, entry=""):
        """How many rigs fit on the deposit being marked: from the kept plan
        on this ground when there is one, else the commander's own entry."""
        book = _own(self, "plan_book", None)
        system, body = self.here()
        if book is not None and state is not None and _get(state, "radius_m", None):
            found = book.nearest(system, body, state.lat, state.lon, state.radius_m,
                                 PLAN_DEPOSIT_M)
            if found is not None and found.get("fit"):
                return str(int(found["fit"]))
        return str(entry or "").strip()


# The colours the messages go out in; the same ones the window uses.
WP_GREEN = "#5fd068"
WP_AMBER = "#ffb545"
