"""Send a bot message from the web app (e.g. "you are approved").

Sending must never break the web action that triggered it: failures are
logged and reported back as False. Day 11+ moves this to a background queue.
"""

from __future__ import annotations

import logging

from asgiref.sync import async_to_sync
from django.utils import translation

from .setup import build_bot

logger = logging.getLogger(__name__)


async def _send(chat_id: int, text: str) -> None:
    bot = build_bot()
    try:
        await bot.send_message(chat_id, text)
    finally:
        await bot.session.close()


def send(chat_id: int, language: str, make_text) -> bool:
    """make_text() is called with the person's language active."""
    with translation.override(language or "uz"):
        text = str(make_text())
    try:
        async_to_sync(_send)(chat_id, text)
    except Exception:  # Telegram down, bot blocked by the person, no token…
        logger.exception("could not send a bot message to %s", chat_id)
        return False
    return True
