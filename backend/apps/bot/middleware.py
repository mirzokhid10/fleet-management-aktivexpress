"""Runs before every handler: knows who is writing and in which language."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser
from django.utils import translation

from .models import BotUser


def guess_language(tg_user: TgUser) -> str:
    """Before the person picks a language: Russian if their Telegram is in
    Russian, otherwise Uzbek (the company default)."""
    return "ru" if (tg_user.language_code or "").startswith("ru") else "uz"


async def remember(tg_user: TgUser) -> BotUser:
    bot_user, _ = await BotUser.objects.aupdate_or_create(
        telegram_id=tg_user.id,
        defaults={"first_name": tg_user.first_name[:64],
                  "last_name": (tg_user.last_name or "")[:64],
                  "username": (tg_user.username or "")[:32]},
    )
    return bot_user


class BotUserMiddleware(BaseMiddleware):
    """Puts `bot_user` into handler data and switches Django's translation to
    the person's language for the whole update."""

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
                       event: TelegramObject, data: dict[str, Any]) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)
        bot_user = await remember(tg_user)
        data["bot_user"] = bot_user
        with translation.override(bot_user.language or guess_language(tg_user)):
            return await handler(event, data)
