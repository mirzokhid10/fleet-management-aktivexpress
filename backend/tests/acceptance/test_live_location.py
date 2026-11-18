import datetime as dt
import html

import pytest
from django.conf import settings
from django.test import Client
from pytest_bdd import given, parsers, scenarios, then, when

from apps.fleet.models import Shift, Vehicle
from apps.tracking.models import LocationPoint
from fleet_import.fields import parse_plate
from tests import factories as f
from tests.bot_helpers import FakeTelegram, link_telegram

pytestmark = [pytest.mark.acceptance, pytest.mark.django_db]

scenarios("live_location.feature")

T = FakeTelegram


@pytest.fixture
def ctx():
    dispatcher = Client()
    dispatcher.force_login(f.user(role="dispatcher"))
    dispatcher.cookies[settings.LANGUAGE_COOKIE_NAME] = "uz"
    return {"dispatcher": dispatcher, "t": dt.datetime.now(dt.UTC), "calls": []}


def _say(ctx, calls):
    ctx["calls"] = calls
    return calls


def _tick(ctx):
    ctx["t"] += dt.timedelta(seconds=30)
    return ctx["t"]


@given(parsers.parse('driver "{name}" is registered in the bot'))
def registered(ctx, name):
    person = f.user(role="driver", first_name=name.split()[0], language="uz")
    ctx["driver"] = f.driver(user=person, full_name=name)
    ctx["tg"] = link_telegram(person)


@when(parsers.parse('"{name}" starts a shift with "{plate}"'))
def start(ctx, name, plate):
    v = f.vehicle(plate=parse_plate(plate))
    ctx["tg"].send("/start_shift")
    _say(ctx, ctx["tg"].tap(f"shift:take:{v.pk}"))


@given(parsers.parse('"{name}" is on shift with "{plate}" and sharing live location'))
def on_shift_sharing(ctx, name, plate):
    start(ctx, name, plate)
    share(ctx)


@then("the bot asks them to share their live location")
def asks(ctx):
    assert "Jonli joylashuvni ulashing: 📎 ni bosing" in T.texts(ctx["calls"])[0]


@when("they share their live location and it moves 5 times")
def share_and_move(ctx):
    share(ctx)
    for n in range(5):
        ctx["tg"].move(ctx["message_id"], 41.3 + n / 1000, 69.2, at=_tick(ctx),
                       started=ctx["started"])


def share(ctx):
    ctx["started"] = ctx["t"]
    ctx["message_id"], calls = ctx["tg"].share_location(41.3, 69.2, at=ctx["t"])
    _say(ctx, calls)


@then(parsers.parse("the shift has {n:d} points"))
def has_points(ctx, n):
    assert Shift.objects.get(driver=ctx["driver"]).points.count() == n


def _page(ctx):
    return html.unescape(ctx["dispatcher"].get("/shifts/").content.decode())


@then(parsers.parse("the dispatcher sees the shift sharing location with {n:d} points"))
def sees_sharing(ctx, n):
    body = _page(ctx)
    assert "Ulashmoqda" in body and f"Nuqtalar: {n}" in body
    assert 'data-testid="sharing">1 / 1<' in body


@then("the dispatcher sees the shift is not sharing location")
def sees_not_sharing(ctx):
    body = _page(ctx)
    assert "Ulashmayapti" in body
    assert 'data-testid="sharing">0 / 1<' in body


@when("they end the shift")
def end(ctx):
    shift = Shift.objects.get(driver=ctx["driver"])
    ctx["tg"].send("/end_shift")
    _say(ctx, ctx["tg"].tap(f"shift:end:{shift.pk}"))


@then("the bot says they can stop sharing their location")
def can_stop(ctx):
    assert T.texts(ctx["calls"])[0].endswith(
        "Endi joylashuvni ulashishni to'xtatishingiz mumkin.")


@then("further updates are not stored")
def not_stored(ctx):
    before = LocationPoint.objects.count()
    ctx["tg"].move(ctx["message_id"], 41.4, 69.3, at=_tick(ctx), started=ctx["started"])
    assert LocationPoint.objects.count() == before


@when("they stop sharing")
def stop(ctx):
    _say(ctx, ctx["tg"].move(ctx["message_id"], 41.3, 69.2, live_period=None, at=_tick(ctx),
                             started=ctx["started"]))


@then("the bot asks them to share it again")
def asks_again(ctx):
    assert T.texts(ctx["calls"])[0].startswith(
        "⚠️ Siz joylashuvni ulashishni to'xtatdingiz.")


@when(parsers.parse('"{name}" shares their live location without a shift'))
def share_without_shift(ctx, name):
    share(ctx)


@then("the bot tells them to start a shift first")
def start_first(ctx):
    assert T.texts(ctx["calls"]) == [
        "Avval /start_shift bilan smenani boshlang, keyin jonli joylashuvni ulashing."]


@then("no points are stored")
def no_points():
    assert not LocationPoint.objects.exists()
    assert not Vehicle.objects.filter(points__isnull=False).exists()
