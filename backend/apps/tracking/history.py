"""Route history: where a vehicle went on chosen days, for the map and playback (Day 15).

Everything comes from what is already stored: the good points (Day 10) of
the vehicle's shifts that overlap the days, their trips (Day 14) and the
stops between them (found again with the same rules as the trips).

Times go to the page as epoch milliseconds; labels are made here, because
browsers often lack Uzbek date data.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from django.contrib.gis.geos import Point
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.formats import number_format
from django.utils.translation import gettext as _

from apps.fleet.models import Shift, Vehicle

from . import trips
from .models import Trip

MAX_DAYS = 7
DAY_CHOICES = (1, 2, 3, 7)


def ms(at: dt.datetime) -> int:
    return int(at.timestamp() * 1000)


def window(day: dt.date, days: int) -> tuple[dt.datetime, dt.datetime]:
    tz = timezone.get_current_timezone()
    start = dt.datetime.combine(day, dt.time.min, tzinfo=tz)
    return start, start + dt.timedelta(days=max(1, min(days, MAX_DAYS)))


def clock(at: dt.datetime, with_day: bool) -> str:
    local = timezone.localtime(at)
    return f"{local:%d.%m %H:%M}" if with_day else f"{local:%H:%M}"


def duration(span: dt.timedelta) -> str:
    minutes = max(int(span.total_seconds() // 60), 0)
    h, m = divmod(minutes, 60)
    if h:
        return _("%(h)s h %(m)s min") % {"h": h, "m": m}
    return _("%(n)s min") % {"n": m}


def km(meters: float) -> str:
    return number_format(round((meters or 0) / 1000, 1), 1)


@dataclass(frozen=True)
class Choice:
    vehicle: Vehicle | None
    day: dt.date
    days: int


def recent_days(vehicle: Vehicle, limit: int = 10) -> list[dt.date]:
    """Days this vehicle made trips, newest first: shortcuts for the date picker."""
    return list(Trip.objects.filter(vehicle=vehicle)
                .annotate(day=TruncDate("started_at", tzinfo=timezone.get_current_timezone()))
                .order_by("-day").values_list("day", flat=True).distinct()[:limit])


def build(choice: Choice, now: dt.datetime | None = None) -> dict:
    """Everything the history page draws, as plain JSON-able data."""
    now = now or timezone.now()
    start, end = window(choice.day, choice.days)
    multi = choice.days > 1
    shifts = list(Shift.objects.filter(vehicle=choice.vehicle, started_at__lt=end)
                  .exclude(ended_at__lte=start).select_related("driver")
                  .order_by("started_at"))
    places = trips.Places()
    out_shifts, out_trips, out_stops = [], [], []
    total_m, moving_s = 0.0, 0.0

    for shift in shifts:
        rows = list(shift.points.filter(is_valid=True).order_by("recorded_at", "pk")
                    .values_list("recorded_at", "point", "distance_m", "speed_kmh"))
        if not rows:
            continue
        pts = [trips.Pt(at, p.x, p.y, d or 0.0, v) for at, p, d, v in rows]
        times = [p.at for p in pts]
        out_shifts.append({
            "id": shift.pk, "driver": shift.driver.full_name,
            "points": [[ms(p.at), round(p.lon, 6), round(p.lat, 6),
                        None if p.speed_kmh is None else round(p.speed_kmh)] for p in pts],
        })
        s = len(out_shifts) - 1

        for trip in shift.trips.order_by("started_at"):
            # Its points: from the place it left (one point before the start for a
            # trip after a silent stop) to where it arrived or is now.
            first = max(_index_at_or_before(times, trip.started_at), 0)
            a = pts[first]
            if first and (a.lon, a.lat) != (trip.start_point.x, trip.start_point.y):
                first -= 1
            last = _index_at_or_before(times, trip.ended_at or trip.last_point_at)
            frm, to = places.at(trip.start_point), places.at(trip.end_point)
            span = (trip.ended_at or now) - trip.started_at
            total_m += trip.distance_m
            moving_s += span.total_seconds()
            out_trips.append({
                "id": trip.pk, "shift": s, "i0": first, "i1": max(last, first),
                "start": ms(trip.started_at), "end": ms(trip.ended_at or trip.last_point_at),
                "open": trip.is_open,
                "from": frm.name if frm else "", "to": to.name if to else "",
                "start_label": clock(trip.started_at, multi),
                "end_label": clock(trip.ended_at, multi) if trip.ended_at else "",
                "duration": duration(span), "km": km(trip.distance_m),
                "max_speed": None if trip.max_speed_kmh is None else round(trip.max_speed_kmh),
            })

        for st in trips.stops(pts, shift.ended_at or now):
            p = pts[st.first]
            left = st.left_at or shift.ended_at or now
            place = places.at(Point(p.lon, p.lat, srid=4326))
            out_stops.append({
                "shift": s, "lon": round(p.lon, 6), "lat": round(p.lat, 6),
                "start": ms(st.arrived_at), "end": ms(left),
                "minutes": int((left - st.arrived_at).total_seconds() // 60),
                "label": clock(st.arrived_at, multi), "duration": duration(left - st.arrived_at),
                "place": place.name if place else "",
            })

    return {
        "shifts": out_shifts, "trips": out_trips, "stops": out_stops,
        "summary": {"km": km(total_m), "trips": len(out_trips),
                    "driving": duration(dt.timedelta(seconds=moving_s))},
        "multi_day": multi,
        # Browser clocks may be in another zone: the page adds this to show local time.
        "tz_offset_min": int(timezone.localtime(start).utcoffset().total_seconds() // 60),
    }


def _index_at_or_before(times: list[dt.datetime], at: dt.datetime) -> int:
    """Index of the last time <= at (-1 if none). Times are sorted."""
    lo, hi = 0, len(times)
    while lo < hi:
        mid = (lo + hi) // 2
        if times[mid] <= at:
            lo = mid + 1
        else:
            hi = mid
    return lo - 1
