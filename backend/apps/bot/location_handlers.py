"""Live location from drivers on shift (Day 9).

Most updates arrive silently every few seconds; the bot answers only when
something changes for the driver: sharing started, sharing stopped, or the
location cannot be used (no shift, not live).
"""

from __future__ import annotations

import datetime as dt

from aiogram import F, Router
from aiogram.types import Message
from asgiref.sync import sync_to_async
from django.utils.translation import gettext as _

from apps.tracking import live

from .models import BotUser


def how_to_share() -> str:
    return _("Share your live location: tap 📎, choose Location, then “Share My Live "
             "Location” and “Until I turn it off”.")


def _when(message: Message, edited: bool) -> dt.datetime:
    """Telegram's time of this location: the edit time for updates.

    aiogram gives `date` as a datetime but `edit_date` as Unix seconds.
    """
    if edited and message.edit_date:
        return dt.datetime.fromtimestamp(int(message.edit_date), tz=dt.UTC)
    return message.date


def _fix(message: Message, edited: bool) -> live.Fix:
    loc = message.location
    return live.Fix(chat_id=message.chat.id, message_id=message.message_id,
                    latitude=loc.latitude, longitude=loc.longitude,
                    at=_when(message, edited),
                    live_period=loc.live_period, accuracy_m=loc.horizontal_accuracy,
                    heading=loc.heading)


async def _answer(message: Message, bot_user: BotUser, result: str) -> None:
    if result == live.STARTED:
        await message.answer("📍 " + _("Your location is on. Keep sharing it until /end_shift."))
    elif result == live.STOPPED:
        await message.answer("\n".join([
            "⚠️ " + _("You stopped sharing your location. While you are on shift, please "
                      "share it again."), how_to_share()]))
    elif result == live.NOT_LIVE:
        await message.answer("\n".join([_("This is a one-time location. I need a live one."),
                                        how_to_share()]))
    elif result == live.NO_SHIFT:
        await message.answer(_("Start a shift first with /start_shift, then share your live "
                               "location."))
    elif result == live.NOT_DRIVER:
        if bot_user.user_id:
            await message.answer(_("Shifts are for drivers only."))
        else:
            await message.answer(_("You are not registered yet. Send /start and share your "
                                   "phone number first."))


async def location_shared(message: Message, bot_user: BotUser) -> None:
    result = await sync_to_async(live.receive)(bot_user.user_id, _fix(message, False), False)
    await _answer(message, bot_user, result)


async def location_moved(message: Message, bot_user: BotUser) -> None:
    result = await sync_to_async(live.receive)(bot_user.user_id, _fix(message, True), True)
    await _answer(message, bot_user, result)


def register(router: Router) -> None:
    router.message.register(location_shared, F.location)
    router.edited_message.register(location_moved, F.location)
