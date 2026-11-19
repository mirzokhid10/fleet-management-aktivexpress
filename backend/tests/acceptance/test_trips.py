import datetime as dt
import html
import re

import pytest
from django.conf import settings
from django.contrib.gis.geos import Point
from django.test import Client
from pytest_bdd import given, parsers, scenarios, then, when

from apps.fleet.models import Shift
from apps.tracking.models import Geofence
from tests import factories as f
from tests.bot_helpers import link_telegram

pytestmark = [pytest.mark.acceptance, pytest.mark.django_db]

scenarios("trips.feature")

LAT, LON = 41.3, 69.2
M_PER_DEG_LAT = 111_195


@pytest.fixture
def ctx():
    return {}


def _go(ctx, seconds: int, meters: float) -> None:
    """Steps are kept and sent together by _send(), so the drive can end "now"."""
    ctx["t"] += seconds
    ctx["m"] = meters
    ctx["steps"].append((ctx["t"], meters))


def _send(ctx) -> None:
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
    _send(ctx)
    ctx["tg"].send("/end_shift")
    ctx["tg"].tap(f"shift:end:{ctx['shift'].pk}")


def _trips_page(ctx):
    _send(ctx)
    client = Client()
    client.force_login(f.user(role="dispatcher"))
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = "uz"
    return client.get("/trips/")


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(fragment))).strip()


@then("the dispatcher sees these trips")
def sees_trips(ctx, datatable):
    _, *rows = datatable
    body = _trips_page(ctx).content.decode()
    routes = [_text(m) for m in re.findall(r'data-testid="route">(.*?)</td>', body, re.S)]
    km = [_text(m).split(" maks.")[0]
          for m in re.findall(r'data-testid="distance">(.*?)</td>', body, re.S)]
    assert [[r, d] for r, d in zip(routes, km, strict=True)] == [
        [_text(r), d] for r, d in rows]


@then(parsers.parse("the trips total {km} km"))
def total(ctx, km):
    assert _text(_trips_page(ctx).content.decode().split('data-testid="total-km">')[1]
                 .split("</p>")[0]) == f"{km} km"


@then(parsers.parse("the dispatcher sees {n:d} trip on the way"))
@then(parsers.parse("the dispatcher sees {n:d} trips on the way"))
def on_the_way(ctx, n):
    assert _trips_page(ctx).content.decode().count('data-open="1"') == n
