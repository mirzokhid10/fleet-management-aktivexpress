"""Audit log: who entered, confirmed or changed what (feature 37).

Append-only. A database trigger (migration 0002) refuses UPDATE and DELETE,
so not even a bug or the admin panel can rewrite history.
"""

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AuditLog(models.Model):
    class Source(models.TextChoices):
        WEB = "web", "Web"
        BOT = "bot", "Telegram bot"
        SYSTEM = "system", "System job"
        IMPORT = "import", "Excel import"

    class Action(models.TextChoices):
        CREATE = "create", "Created"
        UPDATE = "update", "Changed"
        DELETE = "delete", "Deleted"
        SUBMIT = "submit", "Submitted"
        CONFIRM = "confirm", "Confirmed"
        REJECT = "reject", "Rejected"
        HAND_OVER = "hand_over", "Handed over"

    id = models.BigAutoField(primary_key=True)
    at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True,
                              blank=True, related_name="+", help_text="Empty for system jobs")
    source = models.CharField(max_length=10, choices=Source.choices)
    action = models.CharField(max_length=10, choices=Action.choices)
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.CharField(max_length=40)
    object_repr = models.CharField(max_length=200)
    changes = models.JSONField(default=dict, blank=True,
                               help_text='{"field": [before, after]}')
    reason = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-at"]
        indexes = [models.Index(fields=["content_type", "object_id", "at"])]

    def __str__(self) -> str:
        return f"{self.at:%d.%m.%Y %H:%M} {self.actor or 'system'} {self.action} {self.object_repr}"
