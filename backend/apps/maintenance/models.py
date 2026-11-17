"""Service intervals and the service history reminders are calculated from.

A ServiceRecord is the single "this vehicle had this service at this km/date"
fact. It comes from a confirmed oil/tire entry, the Day 5 import (last service
before go-live), or a repair logged in the web (Day 36). The reminder engine
(Day 33) only needs the latest record per vehicle and service item.
"""

from django.db import models
from django.db.models import Q

from apps.core.choices import ServiceItem


class ServiceInterval(models.Model):
    """Per vehicle model: whichever comes first, km or months."""

    vehicle_model = models.CharField(max_length=50, help_text="Same text as Vehicle.model")
    service = models.CharField(max_length=10, choices=ServiceItem.choices)
    interval_km = models.PositiveIntegerField()
    interval_months = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["vehicle_model", "service"]
        constraints = [
            models.UniqueConstraint(fields=["vehicle_model", "service"],
                                    name="interval_once_per_model_service"),
            models.CheckConstraint(name="interval_positive",
                                   condition=Q(interval_km__gt=0) & Q(interval_months__gt=0)),
        ]

    def __str__(self) -> str:
        return f"{self.vehicle_model} · {self.service}: {self.interval_km} km / {self.interval_months} mo"


class ServiceRecord(models.Model):
    class Source(models.TextChoices):
        ENTRY = "entry", "Driver entry"
        IMPORT = "import", "Initial import"
        REPAIR = "repair", "Repair log"

    vehicle = models.ForeignKey("fleet.Vehicle", on_delete=models.CASCADE,
                                related_name="service_records")
    service = models.CharField(max_length=10, choices=ServiceItem.choices)
    done_on = models.DateField()
    odometer_km = models.PositiveIntegerField()
    source = models.CharField(max_length=10, choices=Source.choices)
    entry = models.OneToOneField("entries.Entry", on_delete=models.PROTECT, null=True,
                                 blank=True, related_name="service_record")
    cost_uzs = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-done_on"]
        indexes = [models.Index(fields=["vehicle", "service", "done_on"])]
        constraints = [
            models.CheckConstraint(name="service_record_entry_matches_source",
                                   condition=(Q(source="entry") & Q(entry__isnull=False))
                                   | (~Q(source="entry") & Q(entry__isnull=True))),
        ]
