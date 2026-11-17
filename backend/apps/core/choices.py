"""Fixed lists shared by models, the bot and the company data template."""

from django.db import models


class FuelType(models.TextChoices):
    DIESEL = "Dizel", "Dizel"
    AI80 = "AI-80", "AI-80"
    AI92 = "AI-92", "AI-92"
    METHANE = "Metan", "Metan"
    PROPANE = "Propan", "Propan"

    @classmethod
    def unit(cls, value: str) -> str:
        """Methane is sold in m³, everything else in litres."""
        return "m3" if value == cls.METHANE else "l"


class ServiceItem(models.TextChoices):
    OIL = "Oil", "Oil"
    TIRES = "Tires", "Tires"
    FILTERS = "Filters", "Filters"
    BRAKES = "Brakes", "Brakes"


class DocumentType(models.TextChoices):
    INSURANCE = "Insurance", "Insurance"
    INSPECTION = "Technical inspection", "Technical inspection"
    GAS_CYLINDER = "Gas cylinder certificate", "Gas cylinder certificate"
    LICENCE = "Driving licence", "Driving licence"
    POWER_OF_ATTORNEY = "Power of attorney", "Power of attorney"
