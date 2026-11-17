from django.db import models
from django.db.models import F, Q


class CompanySettings(models.Model):
    """Company-wide rules (template sheet "Settings"). Exactly one row, id=1."""

    work_start = models.TimeField(default="08:00")
    work_end = models.TimeField(default="19:00")
    work_days = models.CharField(max_length=20, default="Mon-Sat")
    speed_limit_city_kmh = models.PositiveSmallIntegerField(default=70)
    speed_limit_highway_kmh = models.PositiveSmallIntegerField(default=100)
    retention_months = models.PositiveSmallIntegerField(default=3)
    daily_reminder_at = models.TimeField(default="18:00")
    stop_alert_minutes = models.PositiveSmallIntegerField(default=10)

    class Meta:
        verbose_name_plural = "company settings"
        constraints = [
            models.CheckConstraint(name="settings_singleton", condition=Q(id=1)),
            models.CheckConstraint(name="settings_retention_1_or_3",
                                   condition=Q(retention_months__in=[1, 3])),
            models.CheckConstraint(name="settings_work_end_after_start",
                                   condition=Q(work_end__gt=F("work_start"))),
        ]

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "CompanySettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self) -> str:
        return "Company settings"
