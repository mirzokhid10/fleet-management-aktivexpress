"""Day 6: /start, language choice, /help. Registration comes on Day 7."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from django.utils import translation
from django.utils.translation import gettext as _

from .keyboards import LANGUAGE_PREFIX, language_picker
from .models import BotUser

# Shown before a language is chosen, so it is in both.
CHOOSE_LANGUAGE = "Tilni tanlang · Выберите язык"


def greeting(bot_user: BotUser) -> str:
    return "\n\n".join([
        _("Hello, %(name)s! This is the Aktiv Fleet bot.") % {"name": bot_user.first_name
                                                               or bot_user},
        _("Here you will start and end shifts, share your location and send vehicle data."),
        _("Commands: /help"),
    ])


def help_text() -> str:
    return "\n".join([
        _("What the bot can do:"),
        "/start — " + _("start"),
        "/language — " + _("change the language"),
        "/help — " + _("this help"),
    ])


async def start(message: Message, bot_user: BotUser) -> None:
    if not bot_user.language:
        await message.answer(CHOOSE_LANGUAGE, reply_markup=language_picker())
        return
    await message.answer(greeting(bot_user))


async def change_language(message: Message) -> None:
    await message.answer(CHOOSE_LANGUAGE, reply_markup=language_picker())


async def language_chosen(query: CallbackQuery, bot_user: BotUser) -> None:
    code = query.data.removeprefix(LANGUAGE_PREFIX)
    if code not in BotUser.Language.values:
        await query.answer()
        return
    first_time = not bot_user.language
    bot_user.language = code
    await bot_user.asave(update_fields=["language", "last_seen_at"])
    if bot_user.user_id:  # keep the web app in the same language
        from apps.accounts.models import User
        await User.objects.filter(pk=bot_user.user_id).aupdate(language=code)

    with translation.override(code):
        done = _("Language: %(language)s") % {"language": BotUser.Language(code).label}
        await query.answer(done)
        if query.message:
            await query.message.edit_text(f"✅ {done}")
            if first_time:
                await query.message.answer(greeting(bot_user))


async def show_help(message: Message) -> None:
    await message.answer(help_text())


async def anything_else(message: Message) -> None:
    await message.answer(_("I don't understand this yet. Send /help to see what I can do."))


def make_router() -> Router:
    """A new router each time: an aiogram router can belong to one dispatcher only."""
    router = Router(name="start")
    router.message.register(start, CommandStart())
    router.message.register(change_language, Command("language"))
    router.callback_query.register(language_chosen, F.data.startswith(LANGUAGE_PREFIX))
    router.message.register(show_help, Command("help"))
    router.message.register(anything_else)  # last: catches everything else
    return router
