"""Vehicles, drivers and the driver ↔ vehicle shift log."""

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.core.choices import FuelType
from apps.core.validators import validate_phone, validate_plate, validate_vin
from fleet_import.fields import format_plate


class Vehicle(models.Model):
    plate = models.CharField(max_length=8, unique=True, validators=[validate_plate],
                             help_text="Stored without spaces: 01A123BC")
    brand = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    year = models.PositiveSmallIntegerField()
    vin = models.CharField(max_length=17, unique=True, validators=[validate_vin])
    fuel_type = models.CharField(max_length=10, choices=FuelType.choices)
    fuel_norm = models.DecimalField(max_digits=5, decimal_places=2,
                                    help_text="l or m³ per 100 km")
    second_fuel_type = models.CharField(max_length=10, choices=FuelType.choices, blank=True)
    second_fuel_norm = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    # Last *confirmed* odometer. Only confirmed entries move it (approval rule 5).
    odometer_km = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["plate"]
        constraints = [
            models.CheckConstraint(name="vehicle_fuel_norm_positive", condition=Q(fuel_norm__gt=0)),
            models.CheckConstraint(
                name="vehicle_second_fuel_complete",
                condition=(Q(second_fuel_type="") & Q(second_fuel_norm__isnull=True))
                # isnull=False is needed: a NULL comparison would let the CHECK pass.
                | (~Q(second_fuel_type="") & Q(second_fuel_norm__isnull=False)
                   & Q(second_fuel_norm__gt=0)),
            ),
            models.CheckConstraint(name="vehicle_second_fuel_differs",
                                   condition=~Q(second_fuel_type=F("fuel_type"))),
        ]

    def __str__(self) -> str:
        return f"{format_plate(self.plate)} · {self.brand} {self.model}"

    @property
    def plate_display(self) -> str:
        return format_plate(self.plate)

    @property
    def fuel_types(self) -> list[str]:
        return [t for t in (self.fuel_type, self.second_fuel_type) if t]


class Driver(models.Model):
    """The employee record. Exists before the driver ever opens the bot;
    `user` is linked on Telegram registration (Day 7)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                null=True, blank=True, related_name="driver")
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=13, unique=True, validators=[validate_phone])
    licence_number = models.CharField(max_length=20, unique=True)
    licence_categories = models.CharField(max_length=30, blank=True)
    licence_expiry = models.DateField()
    default_vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True,
                                        blank=True, related_name="default_drivers")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self) -> str:
        return self.full_name


class Shift(models.Model):
    """/start_shift … /end_shift. Location points outside a shift are ignored."""

    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="shifts")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="shifts")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["vehicle", "started_at"])]
        constraints = [
            models.UniqueConstraint(fields=["driver"], condition=Q(ended_at__isnull=True),
                                    name="one_open_shift_per_driver"),
            models.UniqueConstraint(fields=["vehicle"], condition=Q(ended_at__isnull=True),
                                    name="one_open_shift_per_vehicle"),
            models.CheckConstraint(name="shift_ends_after_start",
                                   condition=Q(ended_at__isnull=True)
                                   | Q(ended_at__gt=F("started_at"))),
        ]

    def __str__(self) -> str:
        return f"{self.driver} · {self.vehicle.plate_display} · {self.started_at:%d.%m.%Y %H:%M}"

    @property
    def is_open(self) -> bool:
        return self.ended_at is None
