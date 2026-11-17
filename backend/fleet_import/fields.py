"""Field types for the company data templates.

Each field knows how to turn a raw spreadsheet cell into a clean Python value,
or raise FieldError with a message the company can understand. The same
parsers are reused by the Day 5 Excel import.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Any, Callable


class FieldError(ValueError):
    """A cell value that cannot be accepted."""


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


# --- parsers ---------------------------------------------------------------

def parse_text(value: Any) -> str:
    return str(value).strip()


def parse_int(value: Any, *, minimum: int | None = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise FieldError("must be a whole number")
    if isinstance(value, float):
        if not value.is_integer():
            raise FieldError("must be a whole number")
        value = int(value)
    if isinstance(value, str):
        cleaned = value.replace(" ", "").replace(" ", "")
        if not re.fullmatch(r"-?\d+", cleaned):
            raise FieldError("must be a whole number")
        value = int(cleaned)
    if not isinstance(value, int):
        raise FieldError("must be a whole number")
    if minimum is not None and value < minimum:
        raise FieldError(f"must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise FieldError(f"must be at most {maximum}")
    return value


def parse_decimal(value: Any, *, minimum: float | None = 0) -> float:
    if isinstance(value, bool):
        raise FieldError("must be a number")
    if isinstance(value, str):
        cleaned = value.replace(" ", "").replace(" ", "").replace(",", ".")
        try:
            value = float(cleaned)
        except ValueError as exc:
            raise FieldError("must be a number") from exc
    if not isinstance(value, (int, float)):
        raise FieldError("must be a number")
    value = float(value)
    if minimum is not None and value < minimum:
        raise FieldError(f"must be at least {minimum:g}")
    return value


_DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y")


def parse_date(value: Any) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        for fmt in _DATE_FORMATS:
            try:
                return dt.datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    raise FieldError("must be a date like 31.12.2026")


def parse_time(value: Any) -> dt.time:
    if isinstance(value, dt.datetime):
        return value.time()
    if isinstance(value, dt.time):
        return value
    if isinstance(value, str):
        match = re.fullmatch(r"(\d{1,2}):(\d{2})", value.strip())
        if match and int(match[1]) < 24 and int(match[2]) < 60:
            return dt.time(int(match[1]), int(match[2]))
    raise FieldError("must be a time like 08:30")


# Uzbek plates: private "01 A 123 BC", company "01 123 ABC".
_PLATE_RE = re.compile(r"^\d{2}(?:[A-Z]\d{3}[A-Z]{2}|\d{3}[A-Z]{3})$")


def parse_plate(value: Any) -> str:
    plate = re.sub(r"[\s\-]", "", str(value)).upper()
    if not _PLATE_RE.match(plate):
        raise FieldError("must be an Uzbek plate like 01 A 123 BC or 01 123 ABC")
    return plate


def format_plate(plate: str) -> str:
    """01A123BC -> '01 A 123 BC', 01123ABC -> '01 123 ABC'."""
    if plate[2].isalpha():
        return f"{plate[:2]} {plate[2]} {plate[3:6]} {plate[6:]}"
    return f"{plate[:2]} {plate[2:5]} {plate[5:]}"


def parse_phone(value: Any) -> str:
    """Normalise to +998XXXXXXXXX (the format Telegram shares)."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 9:
        digits = "998" + digits
    if not (len(digits) == 12 and digits.startswith("998")):
        raise FieldError("must be an Uzbek phone number like +998 90 123 45 67")
    return "+" + digits


_VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


def parse_vin(value: Any) -> str:
    vin = re.sub(r"\s", "", str(value)).upper()
    if not _VIN_RE.match(vin):
        raise FieldError("must be 17 letters/digits (no I, O or Q)")
    return vin


def parse_choice(value: Any, choices: tuple[str, ...]) -> str:
    text = str(value).strip()
    for choice in choices:
        if text.casefold() == choice.casefold():
            return choice
    raise FieldError("must be one of: " + ", ".join(choices))


def parse_yes_no(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"yes", "ha", "да", "1", "true"}:
        return True
    if text in {"no", "yo'q", "yoq", "нет", "0", "false"}:
        return False
    raise FieldError("must be Yes or No")


# --- field definition ------------------------------------------------------

@dataclass(frozen=True)
class Field:
    """One column of a template sheet."""

    key: str
    label_uz: str
    label_ru: str
    parser: Callable[[Any], Any] = parse_text
    required: bool = True
    choices: tuple[str, ...] = ()
    example: Any = None
    note: str = ""
    unique: bool = False
    width: int = 18
    extra: dict = field(default_factory=dict)

    @property
    def header(self) -> str:
        return f"{self.label_uz} / {self.label_ru}"

    def clean(self, raw: Any) -> Any:
        if _blank(raw):
            if self.required:
                raise FieldError("is required")
            return None
        if self.choices:
            raw = parse_choice(raw, self.choices)
        return self.parser(raw)
