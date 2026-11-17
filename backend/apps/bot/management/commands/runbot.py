"""python manage.py runbot [--mode polling|webhook]

polling  — local development: the bot asks Telegram for updates. No public URL needed.
webhook  — server: Telegram posts updates to BOT_WEBHOOK_URL (HTTPS), which the
           reverse proxy forwards to this process on BOT_WEBHOOK_PORT.
"""

import asyncio
import logging

from aiohttp import web
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.bot.setup import build_bot, build_dispatcher, set_commands
from apps.bot.webhook import WEBHOOK_PATH, make_app


class Command(BaseCommand):
    help = "Run the Telegram bot."

    def add_arguments(self, parser):
        parser.add_argument("--mode", choices=["polling", "webhook"], default=settings.BOT_MODE)

    def handle(self, mode, **options):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
        try:
            bot = build_bot()
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        dp = build_dispatcher()
        if mode == "polling":
            asyncio.run(self.polling(dp, bot))
        else:
            self.webhook(dp, bot)

    async def polling(self, dp, bot):
        await bot.delete_webhook(drop_pending_updates=False)  # polling and webhook exclude each other
        await set_commands(bot)
        me = await bot.get_me()
        self.stdout.write(f"Polling as @{me.username}. Stop with Ctrl+C.")
        await dp.start_polling(bot)

    def webhook(self, dp, bot):
        url, secret = settings.BOT_WEBHOOK_URL, settings.BOT_WEBHOOK_SECRET
        if not url.startswith("https://") or not url.rstrip("/").endswith(WEBHOOK_PATH):
            raise CommandError(f"BOT_WEBHOOK_URL must be https://<domain>{WEBHOOK_PATH}")
        if not secret:
            raise CommandError("Set BOT_WEBHOOK_SECRET (any long random string)")

        async def on_startup(bot):
            await set_commands(bot)
            await bot.set_webhook(url, secret_token=secret,
                                  allowed_updates=dp.resolve_used_update_types())

        dp.startup.register(on_startup)
        web.run_app(make_app(dp, bot, secret), host="0.0.0.0", port=settings.BOT_WEBHOOK_PORT)
