"""Everyone who has opened the Telegram bot.

A row appears on the first message, before the person is known to the
company. Registration by phone (Day 7) links it to a User and a Driver.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


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
    # Shared with the bot's "send my number" button (Day 7); always +998XXXXXXXXX.
    phone = models.CharField(max_length=13, blank=True)
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


class RegistrationRequest(models.Model):
    """A person shared their phone number in the bot and it matched a driver
    or a staff member. A manager confirms it is really them (Day 7)."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Waiting")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")

    class RejectReason(models.TextChoices):
        NOT_EMPLOYEE = "not_employee", _("Not our employee")
        WRONG_PERSON = "wrong_person", _("The number belongs to someone else")
        OTHER = "other", _("Other")

    bot_user = models.ForeignKey(BotUser, on_delete=models.CASCADE,
                                 related_name="registration_requests")
    phone = models.CharField(max_length=13)
    # Exactly one of these: who the phone number belongs to.
    driver = models.ForeignKey("fleet.Driver", on_delete=models.CASCADE, null=True, blank=True,
                               related_name="registration_requests")
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True,
                              blank=True, related_name="registration_requests")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True,
                                   blank=True, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    reject_reason = models.CharField(max_length=20, choices=RejectReason.choices, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                name="registration_matches_one_person",
                condition=(Q(driver__isnull=False) & Q(staff__isnull=True))
                | (Q(driver__isnull=True) & Q(staff__isnull=False))),
            models.UniqueConstraint(fields=["bot_user"], condition=Q(status="pending"),
                                    name="one_pending_registration_per_bot_user"),
            models.CheckConstraint(
                name="registration_decision_complete",
                condition=(Q(status="pending") & Q(decided_at__isnull=True))
                | (~Q(status="pending") & Q(decided_at__isnull=False)
                   & Q(decided_by__isnull=False))),
            models.CheckConstraint(
                name="registration_reject_has_reason",
                condition=~Q(status="rejected") | ~Q(reject_reason="")),
        ]

    def __str__(self) -> str:
        return f"{self.person_name} · {self.phone}"

    @property
    def person_name(self) -> str:
        return str(self.driver or self.staff)

    @property
    def is_staff_request(self) -> bool:
        return self.staff_id is not None


class BotGroup(models.Model):
    """A Telegram group the bot was added to (Day 11).

    The director chooses one of them in Company settings for manager alerts.
    """

    chat_id = models.BigIntegerField(unique=True)
    title = models.CharField(max_length=128, blank=True)
    is_member = models.BooleanField(default=True, help_text="False once the bot is removed")
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title or str(self.chat_id)
