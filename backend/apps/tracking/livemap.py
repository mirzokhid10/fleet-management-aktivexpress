"""Where every vehicle is now, and in what state (Day 12, the live map).

Status of a vehicle:

  off shift   nobody is on shift with it; shown at its last known place, if any
  no signal   on shift, but not sharing location, or the share went silent
              for stop_alert_minutes (Company settings, as in the Day 11
              watcher). Stopping the share shows at once; the alert to the
              group still waits those minutes.
  moving      on shift, location coming, the last point is under 2 minutes
              old and its speed at least 5 km/h (a moving phone reports every
              few seconds; an old "40 km/h" says nothing about now)
  stopped     on shift, location coming, otherwise

Only valid points count (Day 10): a GPS jump never moves a marker.
Plain (sync) functions; the web view turns the result into JSON for the map.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from django.db.models import Exists, OuterRef, Q, Subquery
from django.utils import timezone

from apps.core.models import CompanySettings
from apps.fleet.models import Shift, Vehicle

from .models import LiveSession, LocationPoint

MOVING_KMH = 5  # slower is GPS creep or a crawl in a yard: "stopped"
MOVING_RECENT = dt.timedelta(minutes=2)

MOVING, STOPPED, NO_SIGNAL, OFF_SHIFT = "moving", "stopped", "no_signal", "off_shift"
STATUSES = (MOVING, STOPPED, NO_SIGNAL, OFF_SHIFT)  # also the list order


@dataclass(frozen=True)
class VehicleOnMap:
    vehicle_id: int
    plate: str
    model: str
    status: str
    driver: str = ""
    shift_id: int | None = None
    lat: float | None = None  # last valid point; None: never seen
    lon: float | None = None
    at: dt.datetime | None = None  # time of that point
    speed_kmh: float | None = None
    heading: int | None = None

    @property
    def on_map(self) -> bool:
        return self.lat is not None


def _status(shift: Shift | None, fresh: bool, point: LocationPoint | None,
            now: dt.datetime) -> str:
    if shift is None:
        return OFF_SHIFT
    if not fresh:
        return NO_SIGNAL
    moving = (point is not None and point.recorded_at >= now - MOVING_RECENT
              and (point.speed_kmh or 0) >= MOVING_KMH)
    return MOVING if moving else STOPPED


def fleet(now: dt.datetime | None = None) -> list[VehicleOnMap]:
    """Every active vehicle (and any vehicle on shift), moving ones first.

    A fixed number of queries however big the fleet: the last point of each
    vehicle comes from the (vehicle, recorded_at) index, one lookup per vehicle
    inside one query.
    """
    now = now or timezone.now()
    since = now - dt.timedelta(minutes=CompanySettings.load().stop_alert_minutes)

    open_shifts = Shift.objects.filter(ended_at__isnull=True)
    last_point = (LocationPoint.objects.filter(vehicle=OuterRef("pk"), is_valid=True)
                  .order_by("-recorded_at").values("pk")[:1])
    vehicles = list(Vehicle.objects
                    .filter(Q(is_active=True) | Exists(open_shifts.filter(vehicle=OuterRef("pk"))))
                    .annotate(last_point_id=Subquery(last_point)))

    shifts = {s.vehicle_id: s for s in open_shifts.select_related("driver").annotate(
        fresh=Exists(LiveSession.objects.filter(shift=OuterRef("pk"), ended_at__isnull=True,
                                                last_update_at__gte=since)))}
    points = LocationPoint.objects.in_bulk([v.last_point_id for v in vehicles if v.last_point_id])

    out = []
    for v in vehicles:
        shift, point = shifts.get(v.pk), points.get(v.last_point_id)
        out.append(VehicleOnMap(
            vehicle_id=v.pk, plate=v.plate_display, model=f"{v.brand} {v.model}".strip(),
            status=_status(shift, bool(shift and shift.fresh), point, now),
            driver=shift.driver.full_name if shift else "",
            shift_id=shift.pk if shift else None,
            lat=point.point.y if point else None, lon=point.point.x if point else None,
            at=point.recorded_at if point else None,
            speed_kmh=point.speed_kmh if point else None,
            heading=point.heading if point else None,
        ))
    out.sort(key=lambda x: (STATUSES.index(x.status), x.plate))
    return out


def counts(items: list[VehicleOnMap]) -> dict[str, int]:
    return {s: sum(1 for i in items if i.status == s) for s in STATUSES}
