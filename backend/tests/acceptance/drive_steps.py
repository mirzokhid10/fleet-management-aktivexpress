"""Steps shared by features that tell a drive through the bot (Days 14–15).

    Given the company places | name | metres north |
    Given "<name>" is on shift at "<place>" sharing live location
    When they drive <n> metres north|south in <m> minutes
    When they stand still for <m> minutes
    When nothing comes from the phone for <m> minutes
    When they end the shift

Moves are kept and sent together just before the first check, timed so the
drive ends "now" (or <m> minutes ago after "nothing comes from the phone").
Use with `from tests.acceptance.drive_steps import *`: pytest-bdd keeps the
steps under generated fixture names, which a star import brings along.
"""

import datetime as dt

import pytest
from django.contrib.gis.geos import Point
from pytest_bdd import given, parsers, when

from apps.fleet.models import Shift
from apps.tracking.models import Geofence
from tests import factories as f
from tests.bot_helpers import link_telegram

LAT, LON = 41.3, 69.2
M_PER_DEG_LAT = 111_195


@pytest.fixture
def ctx():
    return {}


def _go(ctx, seconds: int, meters: float) -> None:
    """Steps are kept and sent together by send_moves(), so the drive can end "now"."""
    ctx["t"] += seconds
    ctx["m"] = meters
    ctx["steps"].append((ctx["t"], meters))


def send_moves(ctx) -> None:
    """Share, then every move, timed so the last one was `silence` minutes ago."""
    if ctx.get("sent"):
        return
    ctx["sent"] = True
    now = dt.datetime.now(dt.UTC).replace(microsecond=0)
    t0 = now - dt.timedelta(seconds=ctx["t"], minutes=ctx["silence"])
    tg = ctx["tg"]
    message_id, _ = tg.share_location(LAT + ctx["start"] / M_PER_DEG_LAT, LON, at=t0,
                                      horizontal_accuracy=10)
    for sec, meters in ctx["steps"]:
        tg.move(message_id, LAT + meters / M_PER_DEG_LAT, LON, horizontal_accuracy=10,
                at=t0 + dt.timedelta(seconds=sec), started=t0)


def _drive(ctx, meters: float, minutes: int) -> None:
    n, start = minutes * 2, ctx["m"]
    for k in range(1, n + 1):
        _go(ctx, 30, start + meters * k / n)


@given("the company places")
def places(datatable):
    _, *rows = datatable
    for name, meters in rows:
        Geofence.objects.create(name=name, kind="Client", address="Toshkent", radius_m=150,
                                center=Point(LON, LAT + int(meters) / M_PER_DEG_LAT, srid=4326))


@given(parsers.parse('"{name}" is on shift at "{place}" sharing live location'))
def on_shift(ctx, name, place):
    person = f.user(role="driver", first_name=name.split()[0], language="uz")
    driver = f.driver(user=person, full_name=name)
    tg = ctx["tg"] = link_telegram(person)
    v = f.vehicle()
    tg.send("/start_shift")
    tg.tap(f"shift:take:{v.pk}")
    ctx["shift"] = Shift.objects.get(driver=driver)
    start = (Geofence.objects.get(name=place).center.y - LAT) * M_PER_DEG_LAT
    ctx.update(t=0, m=start, start=start, steps=[], silence=0)


@when(parsers.parse("they drive {meters:d} metres {way} in {minutes:d} minutes"))
def drive(ctx, meters, way, minutes):
    _drive(ctx, meters if way == "north" else -meters, minutes)


@when(parsers.parse("they stand still for {minutes:d} minutes"))
def stand(ctx, minutes):
    for _ in range(minutes * 2):
        _go(ctx, 30, ctx["m"])


@when(parsers.parse("nothing comes from the phone for {minutes:d} minutes"))
def silent(ctx, minutes):
    ctx["silence"] = minutes


@when("they end the shift")
def end(ctx):
    send_moves(ctx)
    ctx["tg"].send("/end_shift")
    ctx["tg"].tap(f"shift:end:{ctx['shift'].pk}")
