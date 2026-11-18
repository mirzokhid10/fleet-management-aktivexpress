"""Bot conversation: language (Day 6), registration by phone and web sign-in (Day 7)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from asgiref.sync import sync_to_async
from django.utils import translation
from django.utils.translation import gettext as _

from apps.accounts import telegram_login as tl
from apps.accounts.models import User
from fleet_import.fields import FieldError, parse_phone

from . import registration as reg
from .keyboards import (LANGUAGE_PREFIX, LOGIN_PREFIX, language_picker, login_numbers,
                        phone_request)
from .models import BotUser, RegistrationRequest

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


def ask_phone_text() -> str:
    return _("To start, send your phone number with the button below. It must be the number "
             "the company has for you.")


def _pending(bot_user: BotUser) -> bool:
    return bot_user.registration_requests.filter(
        status=RegistrationRequest.Status.PENDING).exists()


async def _next_step(message: Message, bot_user: BotUser) -> None:
    """What a person who knows the language should do next."""
    if bot_user.user_id:
        await message.answer(greeting(bot_user), reply_markup=ReplyKeyboardRemove())
    elif await sync_to_async(_pending)(bot_user):
        await message.answer(_("Your registration is waiting for a manager to confirm it. "
                               "I will write to you here."))
    else:
        await message.answer(greeting(bot_user))
        await message.answer(ask_phone_text(), reply_markup=phone_request())


# --- /start, language ------------------------------------------------------

async def start(message: Message, bot_user: BotUser) -> None:
    if not bot_user.language:
        await message.answer(CHOOSE_LANGUAGE, reply_markup=language_picker())
        return
    await _next_step(message, bot_user)


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
        await User.objects.filter(pk=bot_user.user_id).aupdate(language=code)

    with translation.override(code):
        done = _("Language: %(language)s") % {"language": BotUser.Language(code).label}
        await query.answer(done)
        if query.message:
            await query.message.edit_text(f"✅ {done}")
            if first_time:
                await _next_step(query.message, bot_user)


async def show_help(message: Message) -> None:
    await message.answer(help_text())


# --- registration by phone -------------------------------------------------

async def contact_shared(message: Message, bot_user: BotUser) -> None:
    contact = message.contact
    if contact.user_id != message.from_user.id:
        await message.answer(_("Please send your own number with the button."),
                             reply_markup=phone_request())
        return
    try:
        phone = parse_phone(contact.phone_number)
    except FieldError:
        await message.answer(_("Only Uzbek phone numbers (+998) can be registered."),
                             reply_markup=ReplyKeyboardRemove())
        return
    outcome = await sync_to_async(reg.share_phone)(bot_user, phone)
    done = ReplyKeyboardRemove()
    if outcome.kind == reg.LINKED:
        await message.answer(_("You are already registered."), reply_markup=done)
    elif outcome.kind == reg.PENDING:
        await message.answer(_("Your registration is waiting for a manager to confirm it. "
                               "I will write to you here."), reply_markup=done)
    elif outcome.kind == reg.UNKNOWN:
        await message.answer(_("The number %(phone)s is not in the company list. Ask the "
                               "dispatcher to add you, then send it again with /start.")
                             % {"phone": phone}, reply_markup=done)
    else:
        await message.answer(_("Thank you! A manager will confirm your registration soon. "
                               "I will write to you here."), reply_markup=done)


# --- sign in to the web ----------------------------------------------------

def _linked_user(bot_user: BotUser) -> User | None:
    return User.objects.filter(pk=bot_user.user_id).first() if bot_user.user_id else None


def _refusal(result: str) -> str:
    return {
        tl.EXPIRED: _("This sign-in link has expired. Start again on the website."),
        tl.NOT_REGISTERED: _("You are not registered yet. Send /start and share your phone "
                             "number first."),
        tl.NOT_STAFF: _("Your account cannot use the web app. Drivers work in this bot only."),
        tl.WRONG_NUMBER: _("Wrong number. The sign-in was cancelled. Start again on the "
                           "website."),
        tl.DENIED: _("The sign-in was cancelled. If you did not try to sign in, tell the "
                     "director."),
    }[result]


async def login_link(message: Message, command: CommandObject, bot_user: BotUser) -> None:
    token = (command.args or "").removeprefix(tl.START_PREFIX)
    user = await sync_to_async(_linked_user)(bot_user)
    opened = await sync_to_async(tl.open_link)(token, user)
    if opened.result != tl.OK:
        await message.answer(_refusal(opened.result))
        return
    lines = [_("Sign in to the Aktiv Fleet web app?")]
    if opened.login.browser:
        lines.append(_("Browser: %(browser)s") % {"browser": opened.login.browser})
    lines.append(_("Tap the number shown on your screen."))
    await message.answer("\n".join(lines),
                         reply_markup=login_numbers(opened.login.pk, opened.numbers))


async def login_pick(query: CallbackQuery, bot_user: BotUser) -> None:
    login_id, _sep, picked = query.data.removeprefix(LOGIN_PREFIX).partition(":")
    if not login_id.isdigit() or not (picked.isdigit() or picked == "no"):
        await query.answer()
        return
    user = await sync_to_async(_linked_user)(bot_user)
    result = await sync_to_async(tl.pick)(int(login_id), user,
                                          int(picked) if picked.isdigit() else None)
    text = ("✅ " + _("You are signed in. You can go back to the browser.")
            if result == tl.OK else "❌ " + _refusal(result))
    await query.answer()
    if query.message:
        await query.message.edit_text(text)


async def anything_else(message: Message) -> None:
    await message.answer(_("I don't understand this yet. Send /help to see what I can do."))


def make_router() -> Router:
    """A new router each time: an aiogram router can belong to one dispatcher only."""
    router = Router(name="start")
    router.message.register(login_link, CommandStart(deep_link=True,
                                                     magic=F.args.startswith(tl.START_PREFIX)))
    router.message.register(start, CommandStart())
    router.message.register(change_language, Command("language"))
    router.message.register(show_help, Command("help"))
    router.message.register(contact_shared, F.contact)
    router.callback_query.register(language_chosen, F.data.startswith(LANGUAGE_PREFIX))
    router.callback_query.register(login_pick, F.data.startswith(LOGIN_PREFIX))
    router.message.register(anything_else)  # last: catches everything else
    return router
