import html

import pytest
from django.conf import settings
from django.test import Client
from pytest_bdd import given, parsers, scenarios, then, when

from apps.fleet.models import Shift, Vehicle
from fleet_import.fields import parse_plate
from tests import factories as f
from tests.bot_helpers import FakeTelegram, link_telegram

pytestmark = [pytest.mark.acceptance, pytest.mark.django_db]

scenarios("shift_log.feature")


@pytest.fixture
def ctx(sent_by_bot):
    dispatcher = Client()
    dispatcher.force_login(f.user(role="dispatcher"))
    dispatcher.cookies[settings.LANGUAGE_COOKIE_NAME] = "uz"
    return {"sent": sent_by_bot, "drivers": {}, "bots": {}, "last": [],
            "dispatcher": dispatcher}


def _vehicle(plate) -> Vehicle:
    return Vehicle.objects.get(plate=parse_plate(plate))


def _driver(ctx, name, **kw):
    first = name.split()[0]
    person = f.user(role="driver", first_name=first, language="uz")
    ctx["drivers"][name] = f.driver(user=person, full_name=name, **kw)
    ctx["bots"][name] = link_telegram(person)
    return ctx["drivers"][name]


@given(parsers.parse('vehicle "{plate}" is the main vehicle of driver "{name}"'))
def main_vehicle(ctx, plate, name):
    _driver(ctx, name, default_vehicle=f.vehicle(plate=parse_plate(plate)))


@given(parsers.parse('vehicle "{plate}" is also in the fleet'))
def also(plate):
    f.vehicle(plate=parse_plate(plate))


@given(parsers.parse('driver "{name}" is on shift with "{plate}"'))
def on_shift(ctx, name, plate):
    f.shift(driver=_driver(ctx, name), vehicle=_vehicle(plate))


@when(parsers.parse('"{name}" sends /start_shift'))
def start_shift(ctx, name):
    ctx["name"] = name
    ctx["last"] = ctx["bots"][name].send("/start_shift")


@then(parsers.parse('the bot offers "{label}" first'))
def offers_first(ctx, label):
    assert FakeTelegram.buttons(ctx["last"])[0][0] == label


@then(parsers.parse('the bot does not offer "{plate}"'))
def does_not_offer(ctx, plate):
    assert not any(plate in text for text, _ in FakeTelegram.buttons(ctx["last"]))


@when(parsers.parse('they tap "{plate}"'))
def tap(ctx, plate):
    ctx["last"] = ctx["bots"][ctx["name"]].tap(f"shift:take:{_vehicle(plate).pk}")


@then(parsers.parse('the bot says the shift started on "{plate}"'))
def started(ctx, plate):
    assert FakeTelegram.texts(ctx["last"])[0].startswith(f"✅ Smena boshlandi: {plate}, ")


@then(parsers.parse('the dispatcher sees "{name}" on shift with "{plate}"'))
def dispatcher_sees(ctx, name, plate):
    body = html.unescape(ctx["dispatcher"].get("/shifts/", {"open": "1"}).content.decode())
    assert name in body and plate in body and "Smenada" in body


@when(parsers.parse('"{name}" sends /end_shift and confirms'))
def end_shift(ctx, name):
    tg = ctx["bots"][name]
    asked = tg.send("/end_shift")
    yes = FakeTelegram.buttons(asked)[0][1]
    ctx["last"] = tg.tap(yes)


@then(parsers.parse('the bot says the shift ended on "{plate}"'))
def ended(ctx, plate):
    assert FakeTelegram.texts(ctx["last"])[0].startswith(f"✅ Smena tugadi: {plate}, ")


@then(parsers.parse('the shift log shows the shift of "{name}" as ended'))
def log_shows_ended(ctx, name):
    shift = Shift.objects.get(driver=ctx["drivers"][name])
    assert shift.ended_at is not None
    r = ctx["dispatcher"].get("/shifts/")
    row = [s for s in r.context["page"] if s.pk == shift.pk][0]
    assert not row.is_open
    assert 'data-testid="on-shift">0<' in r.content.decode()


@when(parsers.parse('the dispatcher ends the shift of "{name}"'))
def dispatcher_ends(ctx, name):
    shift = Shift.objects.get(driver=ctx["drivers"][name], ended_at__isnull=True)
    assert ctx["dispatcher"].post(f"/shifts/{shift.pk}/end/").status_code == 302


@then(parsers.parse('"{name}" gets a message in the bot that the dispatcher ended it'))
def told(ctx, name):
    telegram_id = ctx["drivers"][name].user.telegram_id
    assert [chat for chat, _ in ctx["sent"]] == [telegram_id]
    assert ctx["sent"][0][1].startswith("Dispetcher 01 A 123 BC bilan smenangizni ")


@then(parsers.parse('"{name}" can take "{plate}"'))
def can_take(ctx, name, plate):
    tg = ctx["bots"][name]
    offered = FakeTelegram.buttons(tg.send("/start_shift"))
    assert any(plate in text for text, _ in offered)
    tg.tap(f"shift:take:{_vehicle(plate).pk}")
    assert Shift.objects.get(vehicle=_vehicle(plate), ended_at__isnull=True).driver == \
        ctx["drivers"][name]
