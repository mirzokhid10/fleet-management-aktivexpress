"""Clean track: distance and speed between points, bad points left out (Day 10).

Each new point is compared with the last *valid* point of the same shift:

  accuracy worse than 100 m           -> bad (Telegram itself is unsure)
  faster than 150 km/h to get there   -> bad (a GPS jump)
  moved less than 15 m                -> good, but 0 m: standing still, GPS jitter
  otherwise                           -> good, distance and speed recorded

If the last valid point was itself the wrong one, every later point would
look like a jump. So when a "jump" point is followed by a point that is
plausible from it, both are accepted and the track continues from there.

Bad points are kept (is_valid=False) for checking, but never count in
distance, speed or alerts.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Max, Sum

MAX_ACCURACY_M = 100
MAX_SPEED_KMH = 150
JITTER_M = 15
EARTH_RADIUS_M = 6_371_008.8


def distance_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance (haversine); under 0.5 % off on a city scale."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class Sample:
    at: dt.datetime
    lon: float
    lat: float
    accuracy_m: float | None = None
    is_valid: bool = True

    @property
    def low_accuracy(self) -> bool:
        return self.accuracy_m is not None and self.accuracy_m > MAX_ACCURACY_M

    @property
    def was_jump(self) -> bool:
        return not self.is_valid and not self.low_accuracy


@dataclass(frozen=True)
class Verdict:
    is_valid: bool
    distance_m: float | None = None
    speed_kmh: float | None = None
    accept_previous: bool = False  # the previous "jump" was right after all


def _step(a: Sample, b: Sample) -> tuple[float, float | None]:
    seconds = (b.at - a.at).total_seconds()
    meters = distance_m(a.lon, a.lat, b.lon, b.lat)
    return meters, (meters / seconds * 3.6 if seconds > 0 else None)


def _good(meters: float, speed: float | None, **kw) -> Verdict:
    if meters < JITTER_M:
        return Verdict(True, 0.0, 0.0, **kw)
    return Verdict(True, round(meters, 1), None if speed is None else round(speed, 1), **kw)


def assess(point: Sample, last_valid: Sample | None, last_any: Sample | None) -> Verdict:
    if point.low_accuracy:
        return Verdict(False)
    if last_valid is None:
        return Verdict(True)  # first point of the shift: nothing to measure from
    meters, speed = _step(last_valid, point)
    if speed is None or speed <= MAX_SPEED_KMH:
        return _good(meters, speed)
    # Too fast from the last valid point. Was that point the wrong one?
    if last_any is not None and last_any.was_jump:
        meters, speed = _step(last_any, point)
        if speed is not None and speed <= MAX_SPEED_KMH:
            return _good(meters, speed, accept_previous=True)
    return Verdict(False)


# --- database --------------------------------------------------------------

def _sample(p) -> Sample:
    return Sample(p.recorded_at, p.point.x, p.point.y, p.accuracy_m, p.is_valid)


def apply(point) -> None:
    """Fill distance/speed/is_valid of a new point (not saved yet)."""
    from .models import LocationPoint

    earlier = LocationPoint.objects.filter(shift_id=point.shift_id,
                                           recorded_at__lt=point.recorded_at)
    last_valid = earlier.filter(is_valid=True).order_by("-recorded_at").first()
    last_any = earlier.order_by("-recorded_at").first()
    verdict = assess(_sample(point), last_valid and _sample(last_valid),
                     last_any and _sample(last_any))
    point.is_valid, point.distance_m, point.speed_kmh = (
        verdict.is_valid, verdict.distance_m, verdict.speed_kmh)
    if verdict.accept_previous:
        LocationPoint.objects.filter(pk=last_any.pk).update(is_valid=True)


@transaction.atomic
def recalculate(shift) -> int:
    """Assess every point of a shift again, in time order. Returns how many changed."""
    points = list(shift.points.order_by("recorded_at", "pk"))
    last_valid = last_any = None
    done: list = []
    for p in points:
        p.is_valid = True  # judged afresh
        verdict = assess(_sample(p), last_valid, last_any)
        if verdict.accept_previous:
            done[-1].is_valid = True
            last_valid = _sample(done[-1])
        p.is_valid, p.distance_m, p.speed_kmh = (
            verdict.is_valid, verdict.distance_m, verdict.speed_kmh)
        s = _sample(p)
        if p.is_valid:
            last_valid = s
        last_any = s
        done.append(p)
    before = {p.pk: (p.is_valid, p.distance_m, p.speed_kmh)
              for p in shift.points.only("is_valid", "distance_m", "speed_kmh")}
    changed = [p for p in done if before[p.pk] != (p.is_valid, p.distance_m, p.speed_kmh)]
    if changed:
        shift.points.model.objects.bulk_update(changed, ["is_valid", "distance_m", "speed_kmh"])
    return len(changed)


@dataclass(frozen=True)
class Totals:
    distance_km: float
    max_speed_kmh: float | None
    points: int
    bad_points: int


def totals(shift) -> Totals:
    agg = shift.points.filter(is_valid=True).aggregate(m=Sum("distance_m"), v=Max("speed_kmh"))
    all_points = shift.points.count()
    good = shift.points.filter(is_valid=True).count()
    return Totals(round((agg["m"] or 0) / 1000, 1), agg["v"], all_points, all_points - good)
