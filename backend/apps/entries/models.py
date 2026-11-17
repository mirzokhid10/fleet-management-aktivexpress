"""Driver entries and their approval.

One rule for every entry (Day 1 kickoff, section 3): the driver submits in the
bot with photos, a dispatcher confirms or rejects, and only confirmed data
counts. So every entry type shares one `Entry` row (status, who decided, flags)
and keeps its own fields in a one-to-one detail table. The dispatcher inbox is
a single query on Entry.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.choices import FuelType


class Entry(models.Model):
    class Kind(models.TextChoices):
        DAILY = "daily", "Daily data"
        REFUEL = "refuel", "Refuel"
        OIL = "oil", "Oil change"
        TIRES = "tires", "Tire change"
        PART = "part", "Part from store"

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"

    class RejectReason(models.TextChoices):
        UNCLEAR_PHOTO = "unclear_photo", "Unclear photo"
        WRONG_NUMBERS = "wrong_numbers", "Wrong numbers"
        NOT_ALLOWED = "not_allowed", "Not allowed"
        OTHER = "other", "Other"

    # Which approver flag on User may decide each kind.
    APPROVER_FLAG = {
        Kind.DAILY: "approves_daily",
        Kind.REFUEL: "approves_fuel",
        Kind.OIL: "approves_service",
        Kind.TIRES: "approves_service",
        Kind.PART: "approves_parts",
    }
    # Photos the bot must collect before the entry can be sent.
    REQUIRED_PHOTOS = {
        Kind.DAILY: ["odometer"],
        Kind.REFUEL: ["odometer", "receipt"],
        Kind.OIL: ["certificate"],
        Kind.TIRES: ["certificate", "tires"],
        Kind.PART: [],
    }

    kind = models.CharField(max_length=10, choices=Kind.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    driver = models.ForeignKey("fleet.Driver", on_delete=models.PROTECT, related_name="entries")
    vehicle = models.ForeignKey("fleet.Vehicle", on_delete=models.PROTECT, related_name="entries")
    shift = models.ForeignKey("fleet.Shift", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="entries")
    odometer_km = models.PositiveIntegerField(null=True, blank=True)
    submitted_at = models.DateTimeField()
    # Automatic checks (Day 22), e.g. ["odometer_lower_than_last", "over_norm"].
    flags = models.JSONField(default=list, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   null=True, blank=True, related_name="decisions")
    decided_at = models.DateTimeField(null=True, blank=True)
    reject_reason = models.CharField(max_length=20, choices=RejectReason.choices, blank=True)
    reject_note = models.CharField(max_length=300, blank=True)
    resubmission_of = models.OneToOneField("self", on_delete=models.SET_NULL, null=True,
                                           blank=True, related_name="resubmission")

    class Meta:
        verbose_name_plural = "entries"
        ordering = ["-submitted_at"]
        indexes = [
            models.Index(fields=["status", "kind", "submitted_at"], name="entry_inbox_idx"),
            models.Index(fields=["vehicle", "kind", "submitted_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                name="entry_decision_matches_status",
                condition=(Q(status="pending") & Q(decided_by__isnull=True)
                           & Q(decided_at__isnull=True) & Q(reject_reason=""))
                | (Q(status="confirmed") & Q(decided_by__isnull=False)
                   & Q(decided_at__isnull=False) & Q(reject_reason=""))
                | (Q(status="rejected") & Q(decided_by__isnull=False)
                   & Q(decided_at__isnull=False) & ~Q(reject_reason="")),
            ),
            models.CheckConstraint(
                name="entry_odometer_required",
                condition=Q(kind="part") | Q(odometer_km__isnull=False),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} · {self.vehicle.plate_display} · {self.get_status_display()}"


class DailyReport(models.Model):
    entry = models.OneToOneField(Entry, on_delete=models.CASCADE, primary_key=True,
                                 related_name="daily")
    fuel_level_pct = models.PositiveSmallIntegerField(null=True, blank=True)
    gas_level_pct = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True, help_text="Notes or problems with the vehicle")

    class Meta:
        constraints = [
            models.CheckConstraint(name="daily_levels_are_percent",
                                   condition=Q(fuel_level_pct__isnull=True)
                                   | Q(fuel_level_pct__lte=100)),
            models.CheckConstraint(name="daily_gas_level_is_percent",
                                   condition=Q(gas_level_pct__isnull=True)
                                   | Q(gas_level_pct__lte=100)),
        ]


class Refuel(models.Model):
    entry = models.OneToOneField(Entry, on_delete=models.CASCADE, primary_key=True,
                                 related_name="refuel")
    fuel_type = models.CharField(max_length=10, choices=FuelType.choices)
    quantity = models.DecimalField(max_digits=7, decimal_places=2, help_text="l or m³")
    price_per_unit_uzs = models.DecimalField(max_digits=10, decimal_places=2)
    total_uzs = models.DecimalField(max_digits=14, decimal_places=2)
    station = models.CharField(max_length=120, blank=True)
    # Filled on confirm (Day 29): consumption since the previous confirmed refill.
    consumption_per_100km = models.DecimalField(max_digits=6, decimal_places=2, null=True,
                                                blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(name="refuel_positive",
                                   condition=Q(quantity__gt=0) & Q(price_per_unit_uzs__gt=0)
                                   & Q(total_uzs__gt=0)),
        ]


class OilChange(models.Model):
    entry = models.OneToOneField(Entry, on_delete=models.CASCADE, primary_key=True,
                                 related_name="oil_change")
    oil_brand = models.CharField(max_length=80)
    service_place = models.CharField(max_length=120)
    next_change_km = models.PositiveIntegerField(null=True, blank=True)
    next_change_date = models.DateField(null=True, blank=True)
    warranty_until = models.DateField(null=True, blank=True)


class TireChange(models.Model):
    entry = models.OneToOneField(Entry, on_delete=models.CASCADE, primary_key=True,
                                 related_name="tire_change")
    brand = models.CharField(max_length=80)
    size = models.CharField(max_length=30, help_text="e.g. 215/75 R17.5")


class TireChangeWheel(models.Model):
    """Which wheel positions a tire change covered (tires per wheel, feature 21)."""

    class Position(models.TextChoices):
        FRONT_LEFT = "FL", "Front left"
        FRONT_RIGHT = "FR", "Front right"
        REAR_LEFT = "RL", "Rear left"
        REAR_RIGHT = "RR", "Rear right"
        REAR_LEFT_INNER = "RLI", "Rear left inner"
        REAR_RIGHT_INNER = "RRI", "Rear right inner"
        SPARE = "SP", "Spare"

    tire_change = models.ForeignKey(TireChange, on_delete=models.CASCADE, related_name="wheels")
    position = models.CharField(max_length=3, choices=Position.choices)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tire_change", "position"],
                                               name="tire_change_position_once")]


class PartRequest(models.Model):
    entry = models.OneToOneField(Entry, on_delete=models.CASCADE, primary_key=True,
                                 related_name="part_request")
    item = models.ForeignKey("store.StoreItem", on_delete=models.PROTECT,
                             related_name="requests")
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=300)

    class Meta:
        constraints = [models.CheckConstraint(name="part_request_quantity_positive",
                                              condition=Q(quantity__gt=0))]


def photo_path(instance, filename: str) -> str:
    owner = f"entry-{instance.entry_id}" if instance.entry_id else f"doc-{instance.document_id}"
    return f"photos/{owner}/{instance.kind}-{filename}"


class Photo(models.Model):
    """Every photo is kept and attached to its record (feature 38).

    Files go to local media now and MinIO later (Day 20); the Telegram file id
    lets the bot re-send a photo without downloading it.
    """

    class Kind(models.TextChoices):
        ODOMETER = "odometer", "Odometer"
        RECEIPT = "receipt", "Payment receipt"
        CERTIFICATE = "certificate", "Service certificate"
        TIRES = "tires", "Tires"
        OLD_PART = "old_part", "Old part"
        SCAN = "scan", "Document scan"

    kind = models.CharField(max_length=12, choices=Kind.choices)
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, null=True, blank=True,
                              related_name="photos")
    document = models.ForeignKey("documents.Document", on_delete=models.CASCADE, null=True,
                                 blank=True, related_name="scans")
    file = models.FileField(upload_to=photo_path, blank=True)
    telegram_file_id = models.CharField(max_length=200, blank=True)
    telegram_file_unique_id = models.CharField(max_length=64, blank=True)
    taken_at = models.DateTimeField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="+")

    class Meta:
        ordering = ["taken_at"]
        constraints = [
            models.CheckConstraint(
                name="photo_has_exactly_one_owner",
                condition=(Q(entry__isnull=False) & Q(document__isnull=True))
                | (Q(entry__isnull=True) & Q(document__isnull=False)),
            ),
            models.CheckConstraint(
                name="photo_has_a_source",
                condition=~Q(file="") | ~Q(telegram_file_id=""),
            ),
            models.UniqueConstraint(
                fields=["telegram_file_unique_id"], condition=~Q(telegram_file_unique_id=""),
                name="photo_telegram_file_once",
            ),
        ]
