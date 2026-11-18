import datetime as dt

import pytest
from aiogram.methods import SendMessage
from asgiref.sync import async_to_sync
from django.utils import timezone
from pytest_bdd import given, parsers, scenarios, then, when

from apps.bot import alerts
from apps.bot.setup import build_bot
from apps.core.models import CompanySettings
from apps.fleet import shifts
from apps.fleet.models import Shift
from apps.tracking import live
from fleet_import.fields import parse_plate
from tests import factories as f
from tests.bot_helpers import TOKEN, FakeTelegram, RecordingSession, link_telegram

pytestmark = [pytest.mark.acceptance, pytest.mark.django_db]

scenarios("stop_sharing_alert.feature")

TODAY = timezone.localdate()


def at(hhmm: str) -> dt.datetime:
    parts = [int(x) for x in hhmm.split(":")]
    return timezone.make_aware(dt.datetime.combine(TODAY, dt.time(*parts)))


@pytest.fixture
def ctx():
    session = RecordingSession()
    return {"session": session, "bot": build_bot(TOKEN, session=session), "seen": 0}


def _new_messages(ctx):
    calls = [c for c in ctx["session"].calls if isinstance(c, SendMessage)]
    new, ctx["seen"] = calls[ctx["seen"]:], len(calls)
    return [(c.chat_id, c.text) for c in new]


def _check(ctx, hhmm):
    """The bot's 30-second rounds from the last check up to hhmm."""
    t = ctx.setdefault("clock", at("09:00"))
    end = at(hhmm)
    while t < end:
        t = min(t + dt.timedelta(seconds=30), end)
        async_to_sync(alerts.check_once)(ctx["bot"], t)
    ctx["clock"] = t


@given(parsers.parse('the bot was added to the group "{title}"'))
def added(ctx, title):
    FakeTelegram(telegram_id=9001).bot_in_group(-100777, title)
    ctx["group"] = -100777


@given("the director chose that group for alerts")
def chose(ctx):
    cs = CompanySettings.load()
    cs.alert_chat_id = ctx["group"]
    cs.stop_alert_minutes = 10
    cs.save()


@given(parsers.parse('"{name}" is on shift with "{plate}" and sharing live location'))
def on_shift(ctx, name, plate):
    person = f.user(role="driver", first_name=name.split()[0], language="uz")
    ctx["tg"] = link_telegram(person)
    ctx["chat"] = person.telegram_id
    d = f.driver(user=person, full_name=name)
    ctx["shift"] = f.shift(driver=d, vehicle=f.vehicle(plate=parse_plate(plate)),
                           started_at=at("08:00"))
    ctx["user_id"] = person.pk
    ctx["message_id"] = 1
    live.receive(person.pk, live.Fix(ctx["chat"], 1, 41.3, 69.2, at("08:00:30"),
                                     live_period=0x7FFFFFFF), edited=False)
    for minute in range(1, 120):  # updates until 10:00
        live.receive(person.pk, live.Fix(ctx["chat"], 1, 41.3, 69.2,
                                         at("08:00") + dt.timedelta(minutes=minute),
                                         live_period=0x7FFFFFFF), edited=True)


@when(parsers.parse("they stop sharing at {hhmm}"))
def stop(ctx, hhmm):
    _check(ctx, hhmm)
    live.receive(ctx["user_id"], live.Fix(ctx["chat"], ctx["message_id"], 41.3, 69.2, at(hhmm)),
                 edited=True)
    _new_messages(ctx)


@when(parsers.parse("they share again at {hhmm}"))
def share_again(ctx, hhmm):
    _check(ctx, hhmm)
    ctx["message_id"] += 1
    live.receive(ctx["user_id"], live.Fix(ctx["chat"], ctx["message_id"], 41.31, 69.21, at(hhmm),
                                          live_period=0x7FFFFFFF), edited=False)


@when(parsers.parse("they end the shift at {hhmm}"))
def end_shift(ctx, hhmm):
    _check(ctx, hhmm)
    shifts.end(Shift.objects.get(pk=ctx["shift"].pk))


@then(parsers.parse("at {hhmm} nobody has been alerted"))
@then(parsers.parse("at {hhmm} nobody is alerted again"))
def nobody(ctx, hhmm):
    _check(ctx, hhmm)
    assert _new_messages(ctx) == []


@then(parsers.parse('by {hhmm} the group got "{text}"'))
def group_got(ctx, hhmm, text):
    _check(ctx, hhmm)
    ctx["last"] = _new_messages(ctx)
    assert (ctx["group"], text) in [(c, t.split("\n")[0]) for c, t in ctx["last"]]


@then(parsers.parse('the driver got "{text}"'))
def driver_got(ctx, text):
    assert (ctx["chat"], text) in [(c, t.split("\n")[0]) for c, t in ctx["last"]]
