"""Web pages of tracking (Day 12: the live map)."""

from __future__ import annotations

from django.conf import settings
from django.shortcuts import render
from django.utils import timezone
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
    """What the page script needs, one dict per vehicle (also the shape Day 13 refreshes)."""
    today = timezone.localdate()
    labels = status_labels()
    return [{
        "id": i.vehicle_id, "plate": i.plate, "model": i.model, "driver": i.driver,
        "status": i.status, "status_label": labels[i.status],
        "lat": i.lat, "lon": i.lon, "heading": i.heading,
        "speed": None if i.speed_kmh is None else round(i.speed_kmh),
        "at": i.at.isoformat() if i.at else None, "when": _when(i.at, today),
    } for i in items]


@role_required(*MANAGERS)
def live_map(request):
    items = livemap.fleet()
    labels = status_labels()
    counts = livemap.counts(items)
    return render(request, "tracking/live_map.html", {
        "page_title": _("Live map"),
        "vehicles": map_data(items),
        "statuses": [{"key": s, "label": labels[s], "count": counts[s]}
                     for s in livemap.STATUSES],
        "map_style_url": settings.MAP_STYLE_URL,
        "map_center": settings.MAP_DEFAULT_CENTER,
    })
