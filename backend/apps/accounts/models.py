from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.validators import validate_phone


class User(AbstractUser):
    """Everyone who uses the web app or the bot.

    Staff log in to the web with username + password; drivers only use the bot
    and are matched by their Telegram phone number (Day 7).
    """

    class Role(models.TextChoices):
        DIRECTOR = "director", _("Director")
        DISPATCHER = "dispatcher", _("Dispatcher")
        STOREKEEPER = "storekeeper", _("Storekeeper")
        DRIVER = "driver", _("Driver")

    class Language(models.TextChoices):
        UZ = "uz", "O'zbekcha"
        RU = "ru", "Русский"

    role = models.CharField(max_length=20, choices=Role.choices)
    phone = models.CharField(max_length=13, unique=True, null=True, blank=True,
                             validators=[validate_phone], help_text="+998XXXXXXXXX")
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True)
    language = models.CharField(max_length=2, choices=Language.choices, default=Language.UZ)

    # "Who confirms what" (Day 1 template sheet). Only dispatchers, storekeepers
    # and directors can hold these.
    approves_daily = models.BooleanField(default=False)
    approves_fuel = models.BooleanField(default=False)
    approves_service = models.BooleanField(default=False)
    approves_parts = models.BooleanField(default=False)

    REQUIRED_FIELDS = ["role"]  # createsuperuser asks for it

    class Meta:
        constraints = [
            models.CheckConstraint(name="user_role_valid",
                                   condition=models.Q(role__in=["director", "dispatcher",
                                                                "storekeeper", "driver"])),
            models.CheckConstraint(
                name="driver_cannot_approve",
                condition=~models.Q(role="driver")
                | models.Q(approves_daily=False, approves_fuel=False,
                           approves_service=False, approves_parts=False),
            ),
        ]

    def __str__(self) -> str:
        return self.get_full_name() or self.username
