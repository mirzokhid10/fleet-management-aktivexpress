"""Trips: a shift's clean track cut into drives from A to B (Day 14).

A trip ends where the vehicle stops for STOP_MINUTES (5) or more, and the
next one starts when it leaves. A stop is either of:

  - stayed: every point for 5+ minutes is within STOP_RADIUS_M (100 m) of
    where it arrived (traffic jams barely moving count too)
  - went quiet: Telegram sends almost nothing while a phone stands still,
    so a 5+ minute gap between two points counts as a stop when the vehicle
    covered it slower than STOP_SPEED_KMH (5 km/h) on average. A gap covered
    faster (sharing was off while driving) stays inside the trip.

The trip after a quiet stop starts at the place of the stop, at the time of
the first point that shows it moving again.

Only good points (Day 10) count. A "trip" shorter than MIN_TRIP_M (200 m)
is moving around the yard, not a trip, and is left out.

Trips are rebuilt from the points whenever a point arrives, so they always
match the track; rebuild() keeps the rows of trips that did not change.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from django.contrib.gis.geos import Point
from django.db import transaction
from django.utils import timezone

from .track import distance_m

STOP_MINUTES = 5
STOP_RADIUS_M = 100
STOP_SPEED_KMH = 5
MIN_TRIP_M = 200


@dataclass(frozen=True)
class Pt:
    at: dt.datetime
    lon: float
    lat: float
    distance_m: float = 0.0  # from the previous good point (Day 10)
    speed_kmh: float | None = None


@dataclass(frozen=True)
class Stop:
    first: int  # index of the point it arrived at
    last: int  # index of the last point still at the place
    arrived_at: dt.datetime
    left_at: dt.datetime | None  # None: still there when the data ends


@dataclass(frozen=True)
class Leg:
    """A trip found in the points (not stored yet)."""

    start: int  # index of the point it left from
    end: int  # index of the point it arrived at (or the newest one)
    started_at: dt.datetime
    ended_at: dt.datetime | None  # None: still on the way
    distance_m: float
    max_speed_kmh: float | None

    @property
    def points(self) -> int:
        return self.end - self.start + 1


def _apart(a: Pt, b: Pt) -> float:
    return distance_m(a.lon, a.lat, b.lon, b.lat)


def _quiet(a: Pt, b: Pt) -> bool:
    """A long gap between two points, covered at walking pace: it stood still."""
    seconds = (b.at - a.at).total_seconds()
    if seconds < STOP_MINUTES * 60:
        return False
    return _apart(a, b) / seconds * 3.6 < STOP_SPEED_KMH


def stops(points: list[Pt], until: dt.datetime) -> list[Stop]:
    """Where the vehicle stood for STOP_MINUTES or more. `until`: end of the data
    (shift end, or now for an open shift), so a vehicle standing at its last
    point counts as stopped once enough time has passed."""
    n, out, i = len(points), [], 0
    least = dt.timedelta(minutes=STOP_MINUTES)
    while i < n:
        j = i + 1
        while j < n and _apart(points[i], points[j]) <= STOP_RADIUS_M:
            j += 1
        last = j - 1
        if j < n:
            left_at = points[j].at if _quiet(points[last], points[j]) else points[last].at
        else:
            left_at = None
        if (left_at or until) - points[i].at >= least:
            out.append(Stop(i, last, points[i].at, left_at))
            i = j
        else:
            i += 1
    return out


def _leg(points: list[Pt], start: int, end: int, started_at, ended_at) -> Leg | None:
    moving = points[start + 1:end + 1]
    meters = sum(p.distance_m or 0 for p in moving)
    if meters < MIN_TRIP_M:
        return None
    speeds = [p.speed_kmh for p in moving if p.speed_kmh is not None]
    return Leg(start, end, started_at, ended_at, round(meters, 1),
               max(speeds) if speeds else None)


def detect(points: list[Pt], until: dt.datetime, is_open: bool) -> list[Leg]:
    """The trips in a shift's good points, oldest first."""
    if not points:
        return []
    legs: list[Leg | None] = []
    start, started_at = 0, points[0].at
    for st in stops(points, until):
        if st.first > start:
            legs.append(_leg(points, start, st.first, started_at, st.arrived_at))
        if st.left_at is None:
            return [leg for leg in legs if leg]
        start, started_at = st.last, st.left_at
    last = len(points) - 1
    if last > start:
        legs.append(_leg(points, start, last, started_at, None if is_open else points[last].at))
    return [leg for leg in legs if leg]


# --- database --------------------------------------------------------------

def _points(shift) -> list[Pt]:
    rows = (shift.points.filter(is_valid=True).order_by("recorded_at", "pk")
            .values_list("recorded_at", "point", "distance_m", "speed_kmh"))
    return [Pt(at, p.x, p.y, d or 0.0, v) for at, p, d, v in rows]


@transaction.atomic
def rebuild(shift, now: dt.datetime | None = None) -> int:
    """Make the shift's trips match its points. Returns how many trips it has.

    A shift without points is left alone: once retention (Day 16) deletes
    old points, their trips are all that is left of them.
    """
    from .models import Trip

    points = _points(shift)
    if not points:
        return shift.trips.count()
    is_open = shift.ended_at is None
    legs = detect(points, shift.ended_at or now or timezone.now(), is_open)

    existing = {t.started_at: t for t in shift.trips.select_for_update()}
    wanted = {leg.started_at for leg in legs}
    shift.trips.filter(pk__in=[t.pk for at, t in existing.items() if at not in wanted]).delete()
    new = []
    # Closed trips first: only one trip of a shift may be open at a time.
    for leg in sorted(legs, key=lambda x: x.ended_at is None):
        a, b = points[leg.start], points[leg.end]
        values = dict(ended_at=leg.ended_at, start_point=Point(a.lon, a.lat, srid=4326),
                      end_point=Point(b.lon, b.lat, srid=4326), last_point_at=b.at,
                      distance_m=leg.distance_m, max_speed_kmh=leg.max_speed_kmh,
                      points=leg.points)
        trip = existing.get(leg.started_at)
        if trip is None:
            new.append(Trip(shift=shift, vehicle_id=shift.vehicle_id,
                            started_at=leg.started_at, **values))
        elif any(getattr(trip, k) != v for k, v in values.items()):
            for k, v in values.items():
                setattr(trip, k, v)
            trip.save(update_fields=list(values))
    if new:
        # One at a time, so a new open trip is saved after the old one was closed.
        for trip in sorted(new, key=lambda t: t.ended_at is None):
            trip.save()
    return len(legs)


def close_quiet(now: dt.datetime | None = None) -> int:
    """End trips of vehicles that have stood (or gone silent) for STOP_MINUTES.

    rebuild() runs when a point arrives; a parked phone sends nothing, so the
    trips page calls this first. Returns how many trips it looked at.
    """
    from .models import Trip

    now = now or timezone.now()
    quiet = (Trip.objects.filter(ended_at__isnull=True,
                                 last_point_at__lte=now - dt.timedelta(minutes=STOP_MINUTES))
             .select_related("shift"))
    shifts = {t.shift for t in quiet}
    for shift in shifts:
        rebuild(shift, now)
    return len(shifts)


# --- places ------------------------------------------------------------------

class Places:
    """Name a trip's ends after the company's places (warehouses, clients)."""

    def __init__(self):
        from .models import Geofence

        self.fences = list(Geofence.objects.filter(is_active=True))

    def at(self, point: Point):
        for g in self.fences:
            if g.area is not None:
                if g.area.contains(point):
                    return g
            elif g.center is not None and distance_m(
                    g.center.x, g.center.y, point.x, point.y) <= g.radius_m:
                return g
        return None
