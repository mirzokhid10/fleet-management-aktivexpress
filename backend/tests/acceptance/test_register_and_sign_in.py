import datetime as dt
import html

import pytest
from aiogram.types import Contact, Message, Update
from django.test import Client
from pytest_bdd import given, parsers, scenarios, then, when

from apps.bot.models import RegistrationRequest
from apps.fleet.models import Driver
from fleet_import.fields import parse_phone
from tests import factories as f
from tests.bot_helpers import FakeTelegram, _ids, telegram_sign_in

pytestmark = [pytest.mark.acceptance, pytest.mark.django_db]

scenarios("register_and_sign_in.feature")


@pytest.fixture
def ctx(sent_by_bot):
    return {"sent": sent_by_bot, "tg": FakeTelegram(telegram_id=3003, first_name="Ali")}


def _bot_texts(ctx):
    return FakeTelegram.texts(ctx["tg"].session.calls) + [t for _, t in ctx["sent"]]


def _share(ctx, phone):
    tg = ctx["tg"]
    tg.send("/start")
    tg.tap("lang:uz")
    msg = Message(message_id=next(_ids), date=dt.datetime.now(dt.UTC), chat=tg.chat,
                  from_user=tg.user,
                  contact=Contact(phone_number=phone, first_name="Ali", user_id=tg.user.id))
    tg._feed(Update(update_id=next(_ids), message=msg))


@given(parsers.parse('"{name}" is in the driver list with phone "{phone}"'))
def in_driver_list(ctx, name, phone):
    ctx["phone"] = parse_phone(phone)
    f.driver(full_name=name, phone=ctx["phone"])


@given(parsers.parse('dispatcher "{name}" has phone "{phone}"'))
def dispatcher_with_phone(ctx, name, phone):
    ctx["phone"] = parse_phone(phone)
    first, last = name.split()
    ctx["staff"] = f.user(role="dispatcher", first_name=first, last_name=last,
                          phone=ctx["phone"])


@when("they open the bot, choose Uzbek and share their phone number")
def share_own(ctx):
    _share(ctx, ctx["phone"])


@when(parsers.parse('someone with phone "{phone}" opens the bot, chooses Uzbek and shares it'))
def stranger(ctx, phone):
    _share(ctx, parse_phone(phone))


def _confirm(role, name):
    client = Client()
    client.force_login(f.user(role=role))
    req = next(r for r in RegistrationRequest.objects.all() if r.person_name.startswith(
        name.split()[0]))
    assert client.post(f"/users/requests/{req.pk}/approve/").status_code == 302


@when(parsers.parse('a dispatcher confirms "{name}" on the New users page'))
def dispatcher_confirms(ctx, name):
    _confirm("dispatcher", name)


@when(parsers.parse('the director confirms "{name}" on the New users page'))
def director_confirms(ctx, name):
    _confirm("director", name)


@when("they sign in on the website with Telegram")
def sign_in(ctx):
    ctx["browser"] = Client()
    ctx["status"] = telegram_sign_in(ctx["browser"], ctx["tg"])


@then(parsers.parse('the bot says "{text}"'))
def bot_says(ctx, text):
    assert any(t.startswith(text) or text in t for t in _bot_texts(ctx)), _bot_texts(ctx)


@then(parsers.parse('"{name}" is linked to their Telegram account'))
def linked(ctx, name):
    assert Driver.objects.get(full_name=name).user.telegram_id == 3003


@then("nothing waits on the New users page")
def nothing_waits(ctx):
    assert not RegistrationRequest.objects.exists()


@then("they see the dashboard")
def dashboard(ctx):
    assert ctx["status"].json()["status"] == "ok"
    text = html.unescape(ctx["browser"].get("/").content.decode())
    assert "Karimova" in text and 'data-menu="dashboard"' in text
