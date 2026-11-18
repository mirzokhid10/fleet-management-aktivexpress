"""Alerts to the managers' Telegram group and reminders to drivers (Day 11).

The bot process runs watch_loop(): every 30 seconds it asks the watcher
what changed and posts it. Group messages are in the company language
(settings.LANGUAGE_CODE); driver reminders in the driver's own language.

The group: add the bot to a Telegram group; the bot remembers it (BotGroup)
and the director picks it in Company settings.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from aiogram import Bot, Router
from aiogram.filters import ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER
from aiogram.types import ChatMemberUpdated
from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from apps.tracking import watch

from .location_handlers import how_to_share
from .models import BotGroup

logger = logging.getLogger(__name__)
EVERY_SECONDS = 30


def _who(event: watch.Event) -> str:
    return f"{event.shift.driver.full_name} · {event.shift.vehicle.plate_display}"


def _map_link(event: watch.Event) -> str:
    p = event.last_point
    if p is None:
        return ""
    lat, lon = f"{p.point.y:.6f}", f"{p.point.x:.6f}"
    return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}"


def gap_text(event: watch.Event) -> str:
    lines = ["⚠️ " + _("%(who)s: location is off for %(minutes)s min (since %(time)s).") % {
        "who": _who(event), "minutes": event.minutes,
        "time": f"{timezone.localtime(event.since):%H:%M}"}]
    if event.last_point is None:
        lines.append(_("No location since the shift started."))
    else:
        lines.append(_("Last place: %(link)s") % {"link": _map_link(event)})
    return "\n".join(lines)


def back_text(event: watch.Event) -> str:
    return "✅ " + _("%(who)s: location is on again (it was off for %(minutes)s min).") % {
        "who": _who(event), "minutes": event.minutes}


def reminder_text(event: watch.Event) -> str:
    return "\n".join([
        "⚠️ " + _("Your location has been off for %(minutes)s min. The dispatcher is "
                  "informed.") % {"minutes": event.minutes},
        how_to_share(),
    ])


async def _send(bot: Bot, chat_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id, text, disable_web_page_preview=True)
    except Exception:  # blocked by the driver, group gone, Telegram down…
        logger.exception("could not send an alert to %s", chat_id)


async def send_events(bot: Bot, events: list[watch.Event], group_id: int | None) -> None:
    for event in events:
        if group_id:
            with translation.override(settings.LANGUAGE_CODE):
                text = gap_text(event) if event.kind == watch.GAP else back_text(event)
            await _send(bot, group_id, text)
        if event.kind == watch.GAP and event.driver_chat_id:
            with translation.override(event.driver_language or settings.LANGUAGE_CODE):
                text = reminder_text(event)
            await _send(bot, event.driver_chat_id, text)
    if events and not group_id:
        logger.warning("%s alert(s) not posted: no alert group in Company settings",
                       len(events))


async def check_once(bot: Bot, now=None) -> list[watch.Event]:
    events = await sync_to_async(watch.check)(now)
    if events:
        group_id = await sync_to_async(watch.alert_chat_id)()
        await send_events(bot, events, group_id)
    return events


async def watch_loop(bot: Bot, every: float = EVERY_SECONDS) -> None:
    while True:
        try:
            await check_once(bot)
        except Exception:  # never let one bad round stop the watching
            logger.exception("location watch failed")
        await asyncio.sleep(every)


def run_with(dp) -> None:
    """Start the watcher together with the bot (polling or webhook)."""
    tasks: list[asyncio.Task] = []

    async def start(bot: Bot) -> None:
        tasks.append(asyncio.create_task(watch_loop(bot)))

    async def stop() -> None:
        for t in tasks:
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await t

    dp.startup.register(start)
    dp.shutdown.register(stop)


# --- groups the bot is added to --------------------------------------------

def _remember_group(chat_id: int, title: str, member: bool) -> None:
    BotGroup.objects.update_or_create(chat_id=chat_id,
                                      defaults={"title": title[:128], "is_member": member})


async def added_to_group(event: ChatMemberUpdated) -> None:
    if event.chat.type not in ("group", "supergroup"):
        return
    await sync_to_async(_remember_group)(event.chat.id, event.chat.title or "", True)
    with translation.override(settings.LANGUAGE_CODE):
        text = _("Hello! I will post alerts here once the director chooses this group in "
                 "Company settings.")
    await event.answer(text)


async def removed_from_group(event: ChatMemberUpdated) -> None:
    await sync_to_async(_remember_group)(event.chat.id, event.chat.title or "", False)


def register(router: Router) -> None:
    router.my_chat_member.register(added_to_group,
                                   ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
    router.my_chat_member.register(removed_from_group,
                                   ChatMemberUpdatedFilter(IS_MEMBER >> IS_NOT_MEMBER))
