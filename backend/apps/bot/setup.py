"""Build the bot and dispatcher. Used by `runbot` and by the tests."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.types import BotCommand
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import translation
from django.utils.translation import gettext as _

from .handlers import make_router
from .middleware import BotUserMiddleware


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.update.outer_middleware(BotUserMiddleware())
    dp.include_router(make_router())
    return dp


def build_bot(token: str | None = None, session: BaseSession | None = None) -> Bot:
    token = token or settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise ImproperlyConfigured("Set TELEGRAM_BOT_TOKEN in .env (token from @BotFather)")
    return Bot(token=token, session=session)


def commands(language: str) -> list[BotCommand]:
    with translation.override(language):
        return [BotCommand(command="start", description=_("start")),
                BotCommand(command="language", description=_("change the language")),
                BotCommand(command="help", description=_("this help"))]


async def set_commands(bot: Bot) -> None:
    """The command menu next to the text box, in the person's Telegram language."""
    await bot.set_my_commands(commands("uz"))
    for code in ("uz", "ru"):
        await bot.set_my_commands(commands(code), language_code=code)
