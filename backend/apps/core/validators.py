"""Model-field validators. They reuse the template parsers so the web, the bot
and the Excel import accept exactly the same values."""

from django.core.exceptions import ValidationError

from fleet_import.fields import FieldError, parse_phone, parse_plate, parse_vin


def _wrap(parser, value):
    try:
        normalised = parser(value)
    except FieldError as exc:
        message = str(exc)
        raise ValidationError(message[:1].upper() + message[1:], code="invalid") from exc
    if normalised != value:
        raise ValidationError(f"Write it as {normalised}", code="not_normalised")


def validate_plate(value: str) -> None:
    _wrap(parse_plate, value)


def validate_phone(value: str) -> None:
    _wrap(parse_phone, value)


def validate_vin(value: str) -> None:
    _wrap(parse_vin, value)
