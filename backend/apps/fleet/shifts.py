"""Start and end shifts (Day 8).

A shift ties one driver to one vehicle from /start_shift to /end_shift.
The database already refuses a second open shift for the same driver or
vehicle; these functions turn that into answers the bot can word.

Plain (sync) functions: the web calls them directly, the bot via sync_to_async.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.audit import log
from apps.audit.models import AuditLog

from .models import Driver, Shift, Vehicle

# Results of start(), for the bot to word.
STARTED, ALREADY_ON_SHIFT, VEHICLE_BUSY, VEHICLE_UNAVAILABLE = (
    "started", "already_on_shift", "vehicle_busy", "vehicle_unavailable")

PICKER_SIZE = 8  # vehicles shown as buttons; more are found by typing the plate


def driver_of(user_id: int | None) -> Driver | None:
    """The active driver record behind a linked bot user."""
    if not user_id:
        return None
    return Driver.objects.filter(user_id=user_id, is_active=True) \
        .select_related("default_vehicle", "user").first()


def open_shift(driver: Driver) -> Shift | None:
    return driver.shifts.filter(ended_at__isnull=True).select_related("vehicle").first()


def free_vehicles(driver: Driver, search: str = "") -> list[Vehicle]:
    """Active vehicles nobody is on shift with; the driver's own vehicle first.

    search matches part of the plate, ignoring spaces and case ("123 bc").
    """
    busy = Shift.objects.filter(vehicle=OuterRef("pk"), ended_at__isnull=True)
    qs = Vehicle.objects.filter(is_active=True).exclude(Exists(busy))
    if search:
        qs = qs.filter(plate__icontains=search.replace(" ", "").upper())
    vehicles = list(qs.order_by("plate"))
    own = driver.default_vehicle_id
    return sorted(vehicles, key=lambda v: v.pk != own)  # stable: plate order kept


@dataclass(frozen=True)
class Started:
    result: str
    shift: Shift | None = None  # the new shift, or the one in the way


def start(driver: Driver, vehicle_id: int, actor=None) -> Started:
    current = open_shift(driver)
    if current:
        return Started(ALREADY_ON_SHIFT, current)
    vehicle = Vehicle.objects.filter(pk=vehicle_id, is_active=True).first()
    if vehicle is None:
        return Started(VEHICLE_UNAVAILABLE)
    try:
        with transaction.atomic():
            shift = Shift.objects.create(driver=driver, vehicle=vehicle,
                                         started_at=timezone.now())
            log.record(shift, AuditLog.Action.CREATE, source=AuditLog.Source.BOT, actor=actor)
    except IntegrityError:
        # Someone took the vehicle (or this driver started elsewhere) a moment ago.
        current = open_shift(driver)
        if current:
            return Started(ALREADY_ON_SHIFT, current)
        other = Shift.objects.filter(vehicle=vehicle, ended_at__isnull=True) \
            .select_related("driver", "vehicle").first()
        return Started(VEHICLE_BUSY, other)
    return Started(STARTED, shift)


def holder(vehicle_id: int) -> Shift | None:
    """The open shift on this vehicle, if any."""
    return Shift.objects.filter(vehicle_id=vehicle_id, ended_at__isnull=True) \
        .select_related("driver", "vehicle").first()


@transaction.atomic
def end(shift: Shift, *, actor=None, source: str = AuditLog.Source.BOT,
        reason: str = "") -> bool:
    """End an open shift. False if it was already ended (by someone else)."""
    now = timezone.now()
    ended = Shift.objects.filter(pk=shift.pk, ended_at__isnull=True).update(ended_at=now)
    if not ended:
        return False
    shift.ended_at = now
    log.record(shift, AuditLog.Action.UPDATE, source=source, actor=actor,
               changes={"ended_at": [None, now.isoformat()]}, reason=reason)
    return True


def duration(shift: Shift, now: dt.datetime | None = None) -> dt.timedelta:
    return (shift.ended_at or now or timezone.now()) - shift.started_at


def hours_minutes(span: dt.timedelta) -> tuple[int, int]:
    minutes = max(int(span.total_seconds() // 60), 0)
    return divmod(minutes, 60)
