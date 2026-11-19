"""Web pages of tracking: the live map (Day 12) and its 10-second feed (Day 13)."""

from __future__ import annotations

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.formats import get_format
from django.utils.translation import gettext as _

from apps.accounts.roles import MANAGERS, role_required

from . import livemap


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
