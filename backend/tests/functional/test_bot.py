"""The bot end to end, with Telegram faked (Day 6)."""

import json

import pytest
from aiogram.methods import SetMyCommands
from aiohttp.test_utils import TestClient, TestServer
from asgiref.sync import async_to_sync
from django.core.management import CommandError, call_command

from apps.bot.models import BotUser
from apps.bot.setup import set_commands
from apps.bot.webhook import WEBHOOK_PATH, make_app
from tests import factories as f
from tests.bot_helpers import FakeTelegram

pytestmark = [pytest.mark.functional, pytest.mark.django_db]

T = FakeTelegram


def test_first_start_remembers_the_person_and_asks_for_a_language():
    tg = FakeTelegram(first_name="Vali", last_name="Aliyev", username="vali90")
    calls = tg.send("/start")
    assert T.texts(calls) == ["Tilni tanlang · Выберите язык"]
    assert [d for _, d in T.buttons(calls)] == ["lang:uz", "lang:ru"]
    bu = BotUser.objects.get(telegram_id=1001)
    assert (bu.first_name, bu.last_name, bu.username, bu.language) == \
        ("Vali", "Aliyev", "vali90", "")


def test_choosing_russian_switches_the_bot_to_russian():
    tg = FakeTelegram()
    tg.send("/start")
    calls = tg.tap("lang:ru")
    assert T.popups(calls) == ["Язык: Русский"]
    assert T.texts(calls)[0] == "✅ Язык: Русский"
    assert T.texts(calls)[1].startswith("Здравствуйте, Vali!")
    assert BotUser.objects.get(telegram_id=1001).language == "ru"

    assert T.texts(tg.send("/start"))[0].startswith("Здравствуйте")  # no picker any more
    assert T.texts(tg.send("/help"))[0].startswith("Что умеет бот:")


def test_changing_language_later_does_not_greet_again():
    tg = FakeTelegram()
    tg.send("/start")
    tg.tap("lang:ru")
    assert T.buttons(tg.send("/language"))
    calls = tg.tap("lang:uz")
    assert T.texts(calls) == ["✅ Til: O'zbekcha"]
    assert T.texts(tg.send("/help"))[0].startswith("Bot nimalar qila oladi:")


def test_unknown_message_before_choosing_uses_the_telegram_language():
    calls = FakeTelegram(language_code="ru").send("salom")
    assert T.texts(calls) == ["Пока не понимаю. Отправьте /help, чтобы увидеть, что я умею."]


def test_unknown_language_code_is_ignored():
    tg = FakeTelegram()
    tg.send("/start")
    calls = tg.tap("lang:en")
    assert T.texts(calls) == []
    assert BotUser.objects.get(telegram_id=1001).language == ""


def test_linked_user_gets_the_same_language_on_the_web():
    user = f.user(role="driver", language="uz")
    BotUser.objects.create(telegram_id=1001, user=user)
    FakeTelegram().tap("lang:ru")
    user.refresh_from_db()
    assert user.language == "ru"


def test_names_are_kept_up_to_date():
    FakeTelegram(first_name="Vali").send("/start")
    FakeTelegram(first_name="Valijon").send("/help")
    assert BotUser.objects.get(telegram_id=1001).first_name == "Valijon"


def test_command_menu_is_set_for_both_languages():
    tg = FakeTelegram()
    async_to_sync(set_commands)(tg.bot)
    sent = [c for c in tg.session.calls if isinstance(c, SetMyCommands)]
    assert [c.language_code for c in sent] == [None, "uz", "ru"]


# --- webhook ---------------------------------------------------------------

def _post_update(secret_header: str | None):
    tg = FakeTelegram()
    app = make_app(tg.dp, tg.bot, "s3cret", handle_in_background=False)
    update = {"update_id": 1, "message": {
        "message_id": 1, "date": 0, "chat": {"id": 1001, "type": "private"},
        "from": {"id": 1001, "is_bot": False, "first_name": "Vali", "language_code": "ru"},
        "text": "/start"}}

    async def go():
        async with TestClient(TestServer(app)) as client:
            headers = {"X-Telegram-Bot-Api-Secret-Token": secret_header} if secret_header else {}
            resp = await client.post(WEBHOOK_PATH, data=json.dumps(update),
                                     headers={"Content-Type": "application/json", **headers})
            health = await client.get("/bot/health")
            return resp.status, health.status

    return async_to_sync(go)(), tg


def test_webhook_refuses_updates_without_the_secret():
    (status, _), tg = _post_update(None)
    assert status == 401
    assert tg.session.calls == []


def test_webhook_handles_updates_with_the_secret():
    (status, health), tg = _post_update("s3cret")
    assert (status, health) == (200, 200)
    assert FakeTelegram.texts(tg.session.calls) == ["Tilni tanlang · Выберите язык"]


@pytest.mark.parametrize("url, secret, error", [
    ("http://fleet.example/bot/webhook", "x", "https://"),
    ("https://fleet.example/other", "x", "https://"),
    ("https://fleet.example/bot/webhook", "", "BOT_WEBHOOK_SECRET"),
])
def test_runbot_checks_the_webhook_settings(settings, url, secret, error):
    settings.TELEGRAM_BOT_TOKEN = "42:TEST"
    settings.BOT_WEBHOOK_URL, settings.BOT_WEBHOOK_SECRET = url, secret
    with pytest.raises(CommandError, match=error):
        call_command("runbot", "--mode", "webhook")


def test_runbot_without_a_token_says_where_to_put_it(settings):
    settings.TELEGRAM_BOT_TOKEN = ""
    with pytest.raises(CommandError, match="TELEGRAM_BOT_TOKEN in .env"):
        call_command("runbot")
