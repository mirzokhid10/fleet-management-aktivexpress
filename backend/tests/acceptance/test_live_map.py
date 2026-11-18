import datetime as dt
from unittest import mock

import pytest
from django.conf import settings
from django.test import Client
from pytest_bdd import given, parsers, scenarios, then, when

from apps.fleet.models import Shift
from fleet_import.fields import parse_plate
from tests import factories as f
from tests.bot_helpers import link_telegram

pytestmark = [pytest.mark.acceptance, pytest.mark.django_db]

scenarios("live_map.feature")

M_PER_DEG_LAT = 111_195
STEP_S = 30


@pytest.fixture
def ctx():
    dispatcher = Client()
    dispatcher.force_login(f.user(role="dispatcher"))
    dispatcher.cookies[settings.LANGUAGE_COOKIE_NAME] = "uz"
    t = dt.datetime.now(dt.UTC).replace(microsecond=0)
    return {"dispatcher": dispatcher, "t": t, "lat": 41.3, "lon": 69.2}


def _tick(ctx, seconds=STEP_S):
    ctx["t"] += dt.timedelta(seconds=seconds)
    return ctx["t"]


def _map(ctx) -> dict[str, dict]:
    """The dispatcher opens /map/ at the scenario's time."""
    with mock.patch("django.utils.timezone.now", return_value=ctx["t"] + dt.timedelta(seconds=5)):
        response = ctx["dispatcher"].get("/map/")
    assert response.status_code == 200
    return {v["plate"]: v for v in response.context["vehicles"]}


@given(parsers.parse('driver "{name}" is registered in the bot'))
def registered(ctx, name):
    person = f.user(role="driver", first_name=name.split()[0], language="uz")
    ctx["driver"] = f.driver(user=person, full_name=name)
    ctx["tg"] = link_telegram(person)


@given(parsers.parse('vehicle "{plate}" is parked and has never been tracked'))
def parked(plate):
    f.vehicle(plate=parse_plate(plate))


@when(parsers.parse('"{name}" starts a shift with "{plate}"'))
def start(ctx, name, plate):
    v = f.vehicle(plate=parse_plate(plate))
    ctx["tg"].send("/start_shift")
    ctx["tg"].tap(f"shift:take:{v.pk}")


def _share(ctx):
    ctx["started"] = ctx["t"]
    ctx["message_id"], _ = ctx["tg"].share_location(ctx["lat"], ctx["lon"], at=ctx["t"])


def _move(ctx, meters_north: float, **kw):
    ctx["lat"] += meters_north / M_PER_DEG_LAT
    ctx["tg"].move(ctx["message_id"], ctx["lat"], ctx["lon"], at=_tick(ctx),
                   started=ctx["started"], **kw)


@when(parsers.parse("they share their live location and drive north at {kmh:d} km/h "
                    "for {minutes:d} minutes"))
def share_and_drive(ctx, kmh, minutes):
    _share(ctx)
    for _ in range(minutes * 60 // STEP_S):
        _move(ctx, kmh / 3.6 * STEP_S)


@given(parsers.parse('"{name}" is on shift with "{plate}" and driving'))
def driving(ctx, name, plate):
    start(ctx, name, plate)
    share_and_drive(ctx, 40, 2)


@when(parsers.parse("they stand still for {minutes:d} minutes"))
def stand(ctx, minutes):
    for _ in range(minutes * 60 // STEP_S):
        _move(ctx, 0)


@when("they stop sharing")
def stop(ctx):
    ctx["tg"].move(ctx["message_id"], ctx["lat"], ctx["lon"], live_period=None, at=_tick(ctx),
                   started=ctx["started"])


@when("they end the shift")
def end(ctx):
    shift = Shift.objects.get(driver=ctx["driver"])
    ctx["tg"].send("/end_shift")
    ctx["tg"].tap(f"shift:end:{shift.pk}")


@when(parsers.parse("nothing arrives from their phone for {minutes:d} minutes"))
def silence(ctx, minutes):
    # Each check is counted from the last update, not from the previous check.
    ctx.setdefault("last_update", ctx["t"])
    ctx["t"] = ctx["last_update"] + dt.timedelta(minutes=minutes)


def _vehicle(ctx, plate, status):
    v = _map(ctx)[plate]
    assert v["status_label"] == status, v
    return v


@then(parsers.parse('the map shows "{plate}" as "{status}" with no position'))
def no_position(ctx, plate, status):
    assert _vehicle(ctx, plate, status)["lat"] is None


@then(parsers.parse('the map shows "{plate}" as "{status}" with driver "{name}" at the last place'))
def with_driver(ctx, plate, status, name):
    v = _vehicle(ctx, plate, status)
    assert v["driver"] == name
    assert (v["lat"], v["lon"]) == pytest.approx((ctx["lat"], ctx["lon"]))
    assert v["speed"] == pytest.approx(40, abs=1)


@then(parsers.parse('the map shows "{plate}" as "{status}" at the last place'))
def at_last_place(ctx, plate, status):
    v = _vehicle(ctx, plate, status)
    assert (v["lat"], v["lon"]) == pytest.approx((ctx["lat"], ctx["lon"]))


@then(parsers.parse('the map shows "{plate}" as "{status}"'))
def shows(ctx, plate, status):
    _vehicle(ctx, plate, status)
