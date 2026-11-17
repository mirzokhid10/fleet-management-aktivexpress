"""Everyone who has opened the Telegram bot.

A row appears on the first message, before the person is known to the
company. Registration by phone (Day 7) links it to a User and a Driver.
"""

from django.conf import settings
from django.db import models


class BotUser(models.Model):
    class Language(models.TextChoices):
        UZ = "uz", "O'zbekcha"
        RU = "ru", "Русский"

    telegram_id = models.BigIntegerField(unique=True)
    first_name = models.CharField(max_length=64, blank=True)
    last_name = models.CharField(max_length=64, blank=True)
    username = models.CharField(max_length=32, blank=True)
    # Empty until the person picks one; the bot asks on /start.
    language = models.CharField(max_length=2, choices=Language.choices, blank=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                blank=True, related_name="bot_user")
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(name="bot_user_language_valid",
                                   condition=models.Q(language__in=["", "uz", "ru"])),
        ]

    def __str__(self) -> str:
        name = " ".join(p for p in (self.first_name, self.last_name) if p)
        return name or (f"@{self.username}" if self.username else str(self.telegram_id))
