"""Store: catalogue and a stock ledger.

Stock on hand is the sum of movements, never a number someone types in. That
keeps "who took what, for which vehicle" and the current quantity in one place.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q, Sum


class Supplier(models.Model):
    name = models.CharField(max_length=120, unique=True)
    phone = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class StoreItem(models.Model):
    name = models.CharField(max_length=120, unique=True)
    category = models.CharField(max_length=50)
    unit = models.CharField(max_length=10, help_text="l, pcs, kg …")
    min_level = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category", "name"]
        constraints = [models.CheckConstraint(name="item_min_level_non_negative",
                                              condition=Q(min_level__gte=0))]

    def __str__(self) -> str:
        return self.name

    def stock(self) -> Decimal:
        return self.movements.aggregate(total=Sum("quantity"))["total"] or Decimal(0)


class StockMovement(models.Model):
    """quantity is signed: + comes in, − goes out."""

    class Kind(models.TextChoices):
        OPENING = "opening", "Opening balance"
        PURCHASE = "purchase", "Purchase"
        ISSUE = "issue", "Issued to vehicle"
        ADJUSTMENT = "adjust", "Stock-take adjustment"

    item = models.ForeignKey(StoreItem, on_delete=models.PROTECT, related_name="movements")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    # purchase / opening
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, null=True, blank=True)
    unit_price_uzs = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    warranty_until = models.DateField(null=True, blank=True)
    # issue
    vehicle = models.ForeignKey("fleet.Vehicle", on_delete=models.PROTECT, null=True,
                                blank=True, related_name="parts_issued")
    part_request = models.OneToOneField("entries.PartRequest", on_delete=models.PROTECT,
                                        null=True, blank=True, related_name="issue")
    note = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["item", "created_at"]),
                   models.Index(fields=["vehicle", "created_at"])]
        constraints = [
            models.CheckConstraint(
                name="movement_sign_matches_kind",
                condition=(Q(kind__in=["opening", "purchase"]) & Q(quantity__gt=0))
                | (Q(kind="issue") & Q(quantity__lt=0))
                | (Q(kind="adjust") & ~Q(quantity=0)),
            ),
            models.CheckConstraint(
                name="issue_has_vehicle",
                condition=~Q(kind="issue") | Q(vehicle__isnull=False),
            ),
            models.CheckConstraint(
                name="only_purchases_have_supplier",
                condition=Q(kind__in=["opening", "purchase"]) | Q(supplier__isnull=True),
            ),
        ]
