from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .models import BotUser

LANGUAGE_PREFIX = "lang:"


def language_picker() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"🇺🇿 {label}" if code == "uz" else f"🇷🇺 {label}",
                             callback_data=f"{LANGUAGE_PREFIX}{code}")
        for code, label in BotUser.Language.choices
    ]])
