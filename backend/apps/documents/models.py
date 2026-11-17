"""Documents with an expiry date. Scans are Photos attached to the document."""

from django.db import models
from django.db.models import Q

from apps.core.choices import DocumentType

VEHICLE_DOCUMENTS = [DocumentType.INSURANCE, DocumentType.INSPECTION, DocumentType.GAS_CYLINDER]
DRIVER_DOCUMENTS = [DocumentType.LICENCE, DocumentType.POWER_OF_ATTORNEY]


class Document(models.Model):
    doc_type = models.CharField(max_length=30, choices=DocumentType.choices)
    vehicle = models.ForeignKey("fleet.Vehicle", on_delete=models.CASCADE, null=True,
                                blank=True, related_name="documents")
    driver = models.ForeignKey("fleet.Driver", on_delete=models.CASCADE, null=True,
                               blank=True, related_name="documents")
    number = models.CharField(max_length=50, blank=True)
    issued_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["expires_on"]
        indexes = [models.Index(fields=["expires_on"])]
        constraints = [
            models.CheckConstraint(
                name="document_owner_matches_type",
                condition=(Q(doc_type__in=VEHICLE_DOCUMENTS) & Q(vehicle__isnull=False)
                           & Q(driver__isnull=True))
                | (Q(doc_type__in=DRIVER_DOCUMENTS) & Q(driver__isnull=False)
                   & Q(vehicle__isnull=True)),
            ),
            models.CheckConstraint(
                name="document_expires_after_issue",
                condition=Q(issued_on__isnull=True) | Q(expires_on__gt=models.F("issued_on")),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_doc_type_display()} · {self.vehicle or self.driver}"

    @property
    def owner(self):
        return self.vehicle or self.driver
