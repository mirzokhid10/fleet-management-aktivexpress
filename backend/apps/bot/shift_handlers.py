"""/start_shift and /end_shift (Day 8).

/start_shift  -> "Which vehicle?" buttons (own vehicle first), or type part of the plate
tap a vehicle -> shift starts; a vehicle someone else is on is refused (call the dispatcher)
/end_shift    -> "End your shift?" yes / no
"""

from __future__ import annotations

import datetime as dt

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async
from django.utils import timezone
from django.utils.formats import number_format
from django.utils.translation import gettext as _

from apps.fleet import shifts
from apps.fleet.models import Driver, Shift
from apps.tracking import track

from .keyboards import SHIFT_END, SHIFT_KEEP, SHIFT_TAKE, end_confirm, vehicle_picker
from .location_handlers import how_to_share
from .models import BotUser


class ShiftStates(StatesGroup):
    picking = State()  # the next typed text is part of a plate


# --- wording ---------------------------------------------------------------

def when(moment: dt.datetime) -> str:
    """08:15 today, 17.11 08:15 another day (company time zone)."""
    local = timezone.localtime(moment)
    if local.date() == timezone.localdate():
        return f"{local:%H:%M}"
    return f"{local:%d.%m %H:%M}"


def span(delta: dt.timedelta) -> str:
    hours, minutes = shifts.hours_minutes(delta)
    if hours:
        return _("%(hours)s h %(minutes)s min") % {"hours": hours, "minutes": minutes}
    return _("%(minutes)s min") % {"minutes": minutes}


def on_shift_text(shift: Shift) -> str:
    return _("You are already on shift with %(vehicle)s since %(time)s. Send /end_shift to "
             "end it.") % {"vehicle": shift.vehicle.plate_display, "time": when(shift.started_at)}


def busy_text(shift: Shift) -> str:
    return _("%(vehicle)s is on shift with %(driver)s since %(time)s. If that is wrong, call "
             "the dispatcher.") % {"vehicle": shift.vehicle.plate_display,
                                   "driver": shift.driver.full_name,
                                   "time": when(shift.started_at)}


def started_text(shift: Shift) -> str:
    return "\n".join([
        "✅ " + _("Shift started: %(vehicle)s at %(time)s.") % {
            "vehicle": shift.vehicle.plate_display, "time": when(shift.started_at)},
        how_to_share(),
        _("Send /end_shift when you finish."),
    ])


def ended_text(shift: Shift, totals: track.Totals | None = None) -> str:
    lines = ["✅ " + _("Shift ended: %(vehicle)s, %(start)s–%(end)s (%(duration)s).") % {
        "vehicle": shift.vehicle.plate_display, "start": when(shift.started_at),
        "end": when(shift.ended_at), "duration": span(shifts.duration(shift))}]
    if totals and totals.points:
        lines.append(_("Distance: %(km)s km.") % {
            "km": number_format(totals.distance_km, decimal_pos=1)})
    lines.append(_("You can stop sharing your location now."))
    return "\n".join(lines)


# --- who is asking ---------------------------------------------------------

def _driver(bot_user: BotUser) -> Driver | None:
    return shifts.driver_of(bot_user.user_id)


async def _driver_or_refuse(message: Message, bot_user: BotUser) -> Driver | None:
    if not bot_user.user_id:
        await message.answer(_("You are not registered yet. Send /start and share your phone "
                               "number first."))
        return None
    driver = await sync_to_async(_driver)(bot_user)
    if driver is None:
        await message.answer(_("Shifts are for drivers only."))
    return driver


# --- /start_shift ----------------------------------------------------------

async def _show_picker(message: Message, driver: Driver, search: str = "") -> bool:
    vehicles = await sync_to_async(shifts.free_vehicles)(driver, search)
    if not vehicles:
        if search:
            await message.answer(_("No free vehicle matches “%(text)s”. Try again or call the "
                                   "dispatcher.") % {"text": search})
        else:
            await message.answer(_("There are no free vehicles. Call the dispatcher."))
        return False
    shown = vehicles[:shifts.PICKER_SIZE]
    lines = [_("Which vehicle are you taking?")]
    if len(vehicles) > len(shown):
        lines.append(_("Showing %(shown)s of %(total)s.") % {"shown": len(shown),
                                                             "total": len(vehicles)})
    lines.append(_("Not in the list? Type part of the plate number, for example 123."))
    await message.answer("\n".join(lines),
                         reply_markup=vehicle_picker(shown, driver.default_vehicle_id))
    return True


async def start_shift(message: Message, bot_user: BotUser, state: FSMContext) -> None:
    await state.clear()
    driver = await _driver_or_refuse(message, bot_user)
    if driver is None:
        return
    current = await sync_to_async(shifts.open_shift)(driver)
    if current:
        await message.answer(on_shift_text(current))
        return
    if await _show_picker(message, driver):
        await state.set_state(ShiftStates.picking)


async def plate_typed(message: Message, bot_user: BotUser) -> None:
    driver = await sync_to_async(_driver)(bot_user)
    if driver is None:
        return
    await _show_picker(message, driver, search=message.text.strip()[:12])


async def vehicle_taken(query: CallbackQuery, bot_user: BotUser, state: FSMContext) -> None:
    vehicle_id = query.data.removeprefix(SHIFT_TAKE)
    await query.answer()
    if not vehicle_id.isdigit() or query.message is None:
        return
    driver = await sync_to_async(_driver)(bot_user)
    if driver is None:
        await query.message.edit_text(_("Shifts are for drivers only."))
        return
    outcome = await sync_to_async(shifts.start)(driver, int(vehicle_id), driver.user)
    if outcome.result == shifts.STARTED:
        await state.clear()
        await query.message.edit_text(started_text(outcome.shift))
    elif outcome.result == shifts.ALREADY_ON_SHIFT:
        await state.clear()
        await query.message.edit_text(on_shift_text(outcome.shift))
    elif outcome.result == shifts.VEHICLE_BUSY:
        await query.message.answer(busy_text(outcome.shift))
    else:
        await query.message.answer(_("This vehicle can no longer be chosen. Send /start_shift "
                                     "again."))


# --- /end_shift ------------------------------------------------------------

async def end_shift(message: Message, bot_user: BotUser, state: FSMContext) -> None:
    await state.clear()
    driver = await _driver_or_refuse(message, bot_user)
    if driver is None:
        return
    current = await sync_to_async(shifts.open_shift)(driver)
    if current is None:
        await message.answer(_("You have no open shift. Send /start_shift to start one."))
        return
    await message.answer(
        _("End your shift with %(vehicle)s? Started at %(time)s, %(duration)s ago.") % {
            "vehicle": current.vehicle.plate_display, "time": when(current.started_at),
            "duration": span(shifts.duration(current))},
        reply_markup=end_confirm(current.pk))


def _own_open_shift(bot_user: BotUser, shift_id: int) -> Shift | None:
    return Shift.objects.select_related("vehicle", "driver__user").filter(
        pk=shift_id, driver__user_id=bot_user.user_id).first() if bot_user.user_id else None


async def end_confirmed(query: CallbackQuery, bot_user: BotUser) -> None:
    shift_id = query.data.removeprefix(SHIFT_END)
    await query.answer()
    if not shift_id.isdigit() or query.message is None:
        return
    shift = await sync_to_async(_own_open_shift)(bot_user, int(shift_id))
    if shift is None:
        return
    if not await sync_to_async(shifts.end)(shift, actor=shift.driver.user):
        await query.message.edit_text(_("This shift has already ended."))
        return
    totals = await sync_to_async(track.totals)(shift)
    await query.message.edit_text(ended_text(shift, totals))


async def end_cancelled(query: CallbackQuery) -> None:
    await query.answer()
    if query.message:
        await query.message.edit_text(_("OK, the shift goes on."))


def register(router: Router) -> None:
    router.message.register(start_shift, Command("start_shift"))
    router.message.register(end_shift, Command("end_shift"))
    router.message.register(plate_typed, StateFilter(ShiftStates.picking), F.text,
                            ~F.text.startswith("/"))
    router.callback_query.register(vehicle_taken, F.data.startswith(SHIFT_TAKE))
    router.callback_query.register(end_confirmed, F.data.startswith(SHIFT_END))
    router.callback_query.register(end_cancelled, F.data == SHIFT_KEEP)

