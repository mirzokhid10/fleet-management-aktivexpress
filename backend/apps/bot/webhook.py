"""Webhook mode: a small aiohttp server Telegram posts updates to.

Telegram sends the secret in the X-Telegram-Bot-Api-Secret-Token header;
updates without it are refused with 401.
"""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

WEBHOOK_PATH = "/bot/webhook"


async def health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


def make_app(dp: Dispatcher, bot: Bot, secret: str, *,
             handle_in_background: bool = True) -> web.Application:
    if not secret:
        raise ValueError("webhook mode needs BOT_WEBHOOK_SECRET")
    app = web.Application()
    app.router.add_get("/bot/health", health)
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=secret,
                         handle_in_background=handle_in_background).register(app,
                                                                              path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    return app
