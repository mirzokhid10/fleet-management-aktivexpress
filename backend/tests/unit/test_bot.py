"""Bot pieces that need no database (Day 6)."""

import pytest
from aiogram.types import User
from django.core.exceptions import ImproperlyConfigured

from apps.bot.keyboards import language_picker
from apps.bot.middleware import guess_language
from apps.bot.setup import build_bot, build_dispatcher, commands
from apps.bot.webhook import make_app

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("code, expected", [("ru", "ru"), ("ru-RU", "ru"), ("uz", "uz"),
                                            ("en", "uz"), (None, "uz")])
def test_language_is_guessed_from_telegram_until_chosen(code, expected):
    assert guess_language(User(id=1, is_bot=False, first_name="A", language_code=code)) == expected


def test_language_picker_offers_uzbek_and_russian():
    row = language_picker().inline_keyboard[0]
    assert [b.callback_data for b in row] == ["lang:uz", "lang:ru"]
    assert "O'zbekcha" in row[0].text and "Русский" in row[1].text


def test_command_menu_is_translated():
    assert [c.command for c in commands("uz")] == ["start", "language", "help"]
    assert commands("ru")[1].description == "сменить язык"
    assert commands("uz")[1].description == "tilni o'zgartirish"


def test_bot_needs_a_token(settings):
    settings.TELEGRAM_BOT_TOKEN = ""
    with pytest.raises(ImproperlyConfigured, match="TELEGRAM_BOT_TOKEN"):
        build_bot()


def test_webhook_needs_a_secret():
    with pytest.raises(ValueError, match="BOT_WEBHOOK_SECRET"):
        make_app(build_dispatcher(), build_bot("42:TEST"), secret="")
