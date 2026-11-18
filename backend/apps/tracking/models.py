"""Telegram live-location tracking.

Volume (roadmap): 50 vehicles × 1 point / 30 s × 10 h ≈ 60,000 points a day,
≈ 5.4 million in 3 months. Indexed by (vehicle, recorded_at) for history and
map queries; old rows are deleted nightly by retention (Day 16). If it ever
grows past that, the table can be partitioned by month without model changes.
"""

from django.contrib.gis.db import models
from django.db.models import Q

from apps.fleet.models import Shift, Vehicle


class Geofence(models.Model):
    """Warehouse or client site (template sheet "Places").

    Imported as a circle (centre + radius); Day 51 lets managers draw a
    polygon on the map, which then takes precedence.
    """

    class Kind(models.TextChoices):
        WAREHOUSE = "Warehouse", "Warehouse"
        CLIENT = "Client", "Client"

    name = models.CharField(max_length=120, unique=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    address = models.CharField(max_length=250)
    center = models.PointField(srid=4326, null=True, blank=True)
    radius_m = models.PositiveIntegerField(default=150)
    area = models.PolygonField(srid=4326, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class LiveSession(models.Model):
    """One Telegram live-location share (one message, updated many times).

    A shift can have several if the driver stops and shares again; the gap
    between them is what the stop-sharing alert (Day 11) reports.
    """

    class EndReason(models.TextChoices):
        STOPPED_BY_DRIVER = "stopped", "Driver stopped sharing"
        PERIOD_EXPIRED = "expired", "Live period ran out"
        NO_UPDATES = "silent", "No updates for too long"
        SHIFT_ENDED = "shift_ended", "Shift ended"

    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name="live_sessions")
    chat_id = models.BigIntegerField()
    message_id = models.BigIntegerField()
    live_period_s = models.PositiveIntegerField(help_text="0x7FFFFFFF = until turned off")
    started_at = models.DateTimeField()
    last_update_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    end_reason = models.CharField(max_length=20, choices=EndReason.choices, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["chat_id", "message_id"], name="live_session_message"),
            models.CheckConstraint(
                name="live_session_end_has_reason",
                condition=(Q(ended_at__isnull=True) & Q(end_reason=""))
                | (Q(ended_at__isnull=False) & ~Q(end_reason="")),
            ),
        ]


class LocationPoint(models.Model):
    id = models.BigAutoField(primary_key=True)
    # Same as shift.vehicle; stored again so map/history queries need no join.
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="points")
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name="points")
    session = models.ForeignKey(LiveSession, on_delete=models.SET_NULL, null=True,
                                related_name="points")
    recorded_at = models.DateTimeField(help_text="Time from Telegram (edit_date / date)")
    received_at = models.DateTimeField(auto_now_add=True)
    point = models.PointField(srid=4326)
    accuracy_m = models.FloatField(null=True, blank=True,
                                   help_text="Telegram horizontal_accuracy")
    heading = models.PositiveSmallIntegerField(null=True, blank=True)
    # Calculated from the previous valid point of the same shift (Day 10).
    distance_m = models.FloatField(null=True, blank=True)
    speed_kmh = models.FloatField(null=True, blank=True)
    is_valid = models.BooleanField(default=True, help_text="False: low accuracy or a jump")

    class Meta:
        ordering = ["recorded_at"]
        indexes = [
            models.Index(fields=["vehicle", "recorded_at"]),
            models.Index(fields=["shift", "recorded_at"]),
            models.Index(fields=["recorded_at"], name="point_retention_idx"),
        ]
        constraints = [
            models.CheckConstraint(name="point_speed_non_negative",
                                   condition=Q(speed_kmh__isnull=True) | Q(speed_kmh__gte=0)),
            models.CheckConstraint(name="point_accuracy_non_negative",
                                   condition=Q(accuracy_m__isnull=True) | Q(accuracy_m__gte=0)),
        ]


class SharingGap(models.Model):
    """A driver on shift without live location for too long (Day 11).

    Opened when the alert goes out, closed when location comes back or the
    shift ends. Gaps are what the stop-sharing reports are built from.
    """

    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name="sharing_gaps")
    since = models.DateTimeField(help_text="Last time location was known (or shift start)")
    alerted_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-since"]
        constraints = [
            models.UniqueConstraint(fields=["shift"], condition=Q(resolved_at__isnull=True),
                                    name="one_open_gap_per_shift"),
        ]

    def __str__(self) -> str:
        return f"{self.shift} · {self.since:%H:%M}"
