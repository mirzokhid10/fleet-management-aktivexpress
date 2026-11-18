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
