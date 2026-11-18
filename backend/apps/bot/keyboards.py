from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
                           ReplyKeyboardMarkup)
from django.utils.translation import gettext as _

from .models import BotUser

LANGUAGE_PREFIX = "lang:"
LOGIN_PREFIX = "login:"


def language_picker() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"🇺🇿 {label}" if code == "uz" else f"🇷🇺 {label}",
                             callback_data=f"{LANGUAGE_PREFIX}{code}")
        for code, label in BotUser.Language.choices
    ]])


def phone_request() -> ReplyKeyboardMarkup:
    """Telegram's own button: sends the person's verified number, not a typed one."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 " + _("Send my phone number"), request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True)


def login_numbers(login_id: int, numbers: tuple[int, ...]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(n), callback_data=f"{LOGIN_PREFIX}{login_id}:{n}")
         for n in numbers],
        [InlineKeyboardButton(text="❌ " + _("It wasn't me"),
                              callback_data=f"{LOGIN_PREFIX}{login_id}:no")],
    ])


# --- shifts (Day 8) --------------------------------------------------------

SHIFT_TAKE = "shift:take:"
SHIFT_END = "shift:end:"
SHIFT_KEEP = "shift:keep"


def vehicle_picker(vehicles, own_id: int | None) -> InlineKeyboardMarkup:
    """One vehicle per row; the driver's own vehicle is starred."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=("⭐ " if v.pk == own_id else "") + str(v),
                              callback_data=f"{SHIFT_TAKE}{v.pk}")]
        for v in vehicles
    ])


def end_confirm(shift_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ " + _("Yes, end the shift"),
                              callback_data=f"{SHIFT_END}{shift_id}")],
        [InlineKeyboardButton(text=_("No, keep working"), callback_data=SHIFT_KEEP)],
    ])
