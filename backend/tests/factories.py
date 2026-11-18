"""Small builders for test data. Each takes overrides as keyword arguments."""

from __future__ import annotations

import datetime as dt
import itertools
from decimal import Decimal

from django.contrib.gis.geos import Point
from django.utils import timezone

_seq = itertools.count(1)


def _n() -> int:
    return next(_seq)


def user(**kw):
    from apps.accounts.models import User

    n = _n()
    kw.setdefault("username", f"user{n}")
    kw.setdefault("role", User.Role.DISPATCHER)
    return User.objects.create(**kw)


def vehicle(**kw):
    from apps.fleet.models import Vehicle

    n = _n()
    defaults = dict(plate=f"01A{n % 1000:03d}BC", brand="Isuzu", model="NPR 82", year=2021,
                    vin=f"JALC4B165070{n % 100000:05d}", fuel_type="Dizel",
                    fuel_norm=Decimal("14.5"), odometer_km=150_000)
    defaults.update(kw)
    return Vehicle.objects.create(**defaults)


def driver(**kw):
    from apps.fleet.models import Driver

    n = _n()
    defaults = dict(full_name=f"Driver {n}", phone=f"+99890{n % 10_000_000:07d}",
                    licence_number=f"AF{n:07d}", licence_expiry=dt.date(2028, 12, 31))
    defaults.update(kw)
    return Driver.objects.create(**defaults)


def shift(**kw):
    from apps.fleet.models import Shift

    # Not setdefault(…, driver()): that would build a spare one even when given.
    if "driver" not in kw:
        kw["driver"] = driver()
    if "vehicle" not in kw:
        kw["vehicle"] = vehicle()
    kw.setdefault("started_at", timezone.now() - dt.timedelta(hours=2))
    return Shift.objects.create(**kw)


def point(sh, lon: float, lat: float, at: dt.datetime, **kw):
    from apps.tracking.models import LocationPoint

    return LocationPoint.objects.create(shift=sh, vehicle=sh.vehicle, point=Point(lon, lat),
                                        recorded_at=at, **kw)


def entry(**kw):
    from apps.entries.models import Entry

    kw.setdefault("kind", Entry.Kind.DAILY)
    kw.setdefault("driver", driver())
    kw.setdefault("vehicle", vehicle())
    kw.setdefault("submitted_at", timezone.now())
    if kw["kind"] != Entry.Kind.PART:
        kw.setdefault("odometer_km", 150_100)
    return Entry.objects.create(**kw)


def store_item(**kw):
    from apps.store.models import StoreItem

    kw.setdefault("name", f"Item {_n()}")
    kw.setdefault("category", "Oil")
    kw.setdefault("unit", "l")
    return StoreItem.objects.create(**kw)
