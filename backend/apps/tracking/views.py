"""Web pages of tracking: the live map (Day 12), its 10-second feed (Day 13), trips (Day 14),
route history with playback (Day 15)."""

from __future__ import annotations

import datetime as dt

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.formats import get_format
from django.utils.translation import gettext as _

from apps.accounts.roles import MANAGERS, role_required
from apps.fleet.models import Vehicle
from apps.fleet.shifts import hours_minutes

from . import history, livemap, trips
from .models import Trip

PAGE_SIZE = 50


def status_labels() -> dict[str, str]:
    return {livemap.MOVING: _("Moving"), livemap.STOPPED: _("Stopped"),
            livemap.NO_SIGNAL: _("No signal"), livemap.OFF_SHIFT: _("Off shift")}


def _when(at, today) -> str:
    if at is None:
        return ""
    local = timezone.localtime(at)
    return f"{local:%H:%M}" if local.date() == today else f"{local:%d.%m %H:%M}"


def map_data(items: list[livemap.VehicleOnMap]) -> list[dict]:
    """One dict per vehicle: the page's first data and every refresh after it."""
    today = timezone.localdate()
    labels = status_labels()
    return [{
        "id": i.vehicle_id, "plate": i.plate, "model": i.model, "driver": i.driver,
        "phone": i.driver_phone, "shift_id": i.shift_id,
        "status": i.status, "status_label": labels[i.status],
        "lat": i.lat, "lon": i.lon, "heading": i.heading,
        "speed": None if i.speed_kmh is None else round(i.speed_kmh),
        "at": i.at.isoformat() if i.at else None, "when": _when(i.at, today),
        "shift_since": _when(i.shift_started_at, today), "shift_km": i.shift_km,
    } for i in items]


def feed() -> dict:
    items = livemap.fleet()
    return {"vehicles": map_data(items), "counts": livemap.counts(items),
            "now": timezone.now().isoformat()}


def _texts() -> dict[str, str]:
    """Words the page script needs (the rest of the page is translated in the template)."""
    return {
        "no_position": _("No position yet"),
        "kmh": _("km/h"), "km": _("km"),
        "driver": _("Driver"), "phone": _("Phone"), "speed": _("Speed"),
        "last_update": _("Last update"), "on_shift_since": _("On shift since"),
        "distance": _("Distance on this shift"), "shift_log": _("Shift log"),
        "history": _("Route history"),
        "follow": _("Follow"), "close": _("Close"),
        "updated": _("Updated %(time)s"), "offline": _("No connection. Trying again…"),
        "just_now": _("just now"), "minutes_ago": _("%(n)s min ago"),
        "hours_ago": _("%(n)s h ago"),
        # Browsers often lack Uzbek number data, so take the comma from Django.
        "decimal": get_format("DECIMAL_SEPARATOR"),
    }


@role_required(*MANAGERS)
def live_map(request):
    data = feed()
    labels = status_labels()
    return render(request, "tracking/live_map.html", {
        "page_title": _("Live map"),
        "feed": data,
        "statuses": [{"key": s, "label": labels[s], "count": data["counts"][s]}
                     for s in livemap.STATUSES],
        "texts": _texts(),
        "map_config": {"style": settings.MAP_STYLE_URL, "center": settings.MAP_DEFAULT_CENTER,
                       "refresh_s": settings.MAP_REFRESH_SECONDS},
    })


@role_required(*MANAGERS)
def live_map_data(request):
    """Day 13: the page asks for this every MAP_REFRESH_SECONDS."""
    response = JsonResponse(feed())
    response["Cache-Control"] = "no-store"
    return response


# --- trips (Day 14) ------------------------------------------------------------

def _trip_filters(request, qs):
    """?q= driver or plate, ?day=YYYY-MM-DD (trips that started that day)."""
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(shift__driver__full_name__icontains=q)
                       | Q(vehicle__plate__icontains=q.replace(" ", "")))
    try:
        day = parse_date(request.GET.get("day", "").strip())
    except ValueError:  # well-formed but impossible, e.g. 2026-02-30
        day = None
    if day:
        start = dt.datetime.combine(day, dt.time.min, tzinfo=timezone.get_current_timezone())
        qs = qs.filter(started_at__gte=start, started_at__lt=start + dt.timedelta(days=1))
    return qs, {"q": q, "day": day}


@role_required(*MANAGERS)
def trip_list(request):
    now = timezone.now()
    trips.close_quiet(now)  # parked phones send nothing; end their trips first
    qs, filters = _trip_filters(request, Trip.objects.select_related("vehicle", "shift__driver"))
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
    keep = request.GET.copy()
    keep.pop("page", None)
    places = trips.Places()
    for t in page:
        t.hours, t.minutes = hours_minutes((t.ended_at or now) - t.started_at)
        t.km = round(t.distance_m / 1000, 1)
        t.from_place, t.to_place = places.at(t.start_point), places.at(t.end_point)
    total = qs.aggregate(n=Count("pk"), m=Sum("distance_m"))
    return render(request, "tracking/trip_list.html", {
        "page_title": _("Trips"), "page": page, **filters,
        "total_trips": total["n"], "total_km": round((total["m"] or 0) / 1000, 1),
        "stop_minutes": trips.STOP_MINUTES,
        "filtered": any(filters.values()), "page_query": keep.urlencode(),
    })


# --- route history (Day 15) ------------------------------------------------------

def _history_choice(request) -> tuple[history.Choice, Trip | None]:
    """?vehicle=&day=&days= or ?trip= (opens that trip's vehicle and day)."""
    vehicles = Vehicle.objects.filter(is_active=True)
    trip = None
    if request.GET.get("trip", "").isdigit():
        trip = Trip.objects.select_related("vehicle").filter(pk=request.GET["trip"]).first()
    vid = request.GET.get("vehicle", "")
    vehicle = vehicles.filter(pk=vid).first() if vid.isdigit() else None
    if vehicle is None and trip is not None:
        vehicle = trip.vehicle
    if vehicle is None:  # the vehicle that drove last, else the first one
        last = Trip.objects.filter(vehicle__is_active=True).select_related("vehicle").first()
        vehicle = last.vehicle if last else vehicles.order_by("plate").first()
    try:
        day = parse_date(request.GET.get("day", "").strip())
    except ValueError:
        day = None
    if day is None and trip is not None:
        day = timezone.localtime(trip.started_at).date()
    if day is None and vehicle is not None:
        # Today if it drove today, else its last day with trips.
        recent = history.recent_days(vehicle, 1)
        today = timezone.localdate()
        day = today if not recent or recent[0] >= today else recent[0]
    try:
        days = int(request.GET.get("days", "1"))
    except ValueError:
        days = 1
    days = days if days in history.DAY_CHOICES else 1
    if trip is not None and trip.vehicle_id != getattr(vehicle, "pk", None):
        trip = None
    return history.Choice(vehicle, day or timezone.localdate(), days), trip


def _history_texts() -> dict[str, str]:
    return {
        "play": _("Play"), "pause": _("Pause"), "kmh": _("km/h"),
        "stop_at": _("Stop"), "on_the_way": _("On the way"),
        "speed": _("Playback speed"), "position": _("Time on the route"),
        "max_speed": _("max %(v)s km/h"),
    }


@role_required(*MANAGERS)
def route_history(request):
    choice, trip = _history_choice(request)
    data = history.build(choice) if choice.vehicle else None
    return render(request, "tracking/history.html", {
        "page_title": _("Route history"),
        "vehicles": Vehicle.objects.filter(is_active=True).order_by("plate"),
        "choice": choice, "day_choices": history.DAY_CHOICES,
        "recent": history.recent_days(choice.vehicle) if choice.vehicle else [],
        "data": data, "trip_id": trip.pk if trip else None,
        "texts": _history_texts(),
        "map_config": {"style": settings.MAP_STYLE_URL, "center": settings.MAP_DEFAULT_CENTER},
    })
