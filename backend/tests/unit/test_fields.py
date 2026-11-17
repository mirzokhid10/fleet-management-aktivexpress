import datetime as dt

import pytest

from fleet_import.fields import (
    Field,
    FieldError,
    format_plate,
    parse_date,
    parse_decimal,
    parse_int,
    parse_phone,
    parse_plate,
    parse_time,
    parse_vin,
    parse_yes_no,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("raw, expected", [
    ("01 A 123 BC", "01A123BC"),
    ("01a123bc", "01A123BC"),
    ("01 123 ABC", "01123ABC"),
    ("30-777-AAA", "30777AAA"),
])
def test_plate_accepts_private_and_company_formats(raw, expected):
    assert parse_plate(raw) == expected


@pytest.mark.parametrize("raw", ["", "A 123 BC", "01 A 12 BC", "01 1234 AB", "ABC"])
def test_plate_rejects_bad_formats(raw):
    with pytest.raises(FieldError):
        parse_plate(raw)


@pytest.mark.parametrize("plate, shown", [("01A123BC", "01 A 123 BC"), ("01123ABC", "01 123 ABC")])
def test_format_plate(plate, shown):
    assert format_plate(plate) == shown


@pytest.mark.parametrize("raw", [
    "+998 90 123 45 67", "998901234567", "90 123 45 67", "(90) 123-45-67", 998901234567,
    998901234567.0,
])
def test_phone_normalises_to_telegram_format(raw):
    assert parse_phone(raw) == "+998901234567"


@pytest.mark.parametrize("raw", ["+7 900 123 45 67", "12345", "+998 90 123 45"])
def test_phone_rejects_non_uzbek_numbers(raw):
    with pytest.raises(FieldError):
        parse_phone(raw)


def test_vin_uppercases_and_strips_spaces():
    assert parse_vin("jalc4b16507 000001") == "JALC4B16507000001"


@pytest.mark.parametrize("raw", ["JALC4B1650700000", "JALC4B16507000O01", "JALC4B165070000011"])
def test_vin_rejects_wrong_length_or_letters(raw):
    with pytest.raises(FieldError):
        parse_vin(raw)


@pytest.mark.parametrize("raw", ["31.12.2026", "2026-12-31", "31/12/2026",
                                 dt.date(2026, 12, 31), dt.datetime(2026, 12, 31, 10, 0)])
def test_date_accepts_common_formats(raw):
    assert parse_date(raw) == dt.date(2026, 12, 31)


@pytest.mark.parametrize("raw", ["12.31.2026", "tomorrow", 45000])
def test_date_rejects_unknown_formats(raw):
    with pytest.raises(FieldError):
        parse_date(raw)


def test_time_parses_hh_mm():
    assert parse_time("8:30") == dt.time(8, 30)
    with pytest.raises(FieldError):
        parse_time("25:00")


@pytest.mark.parametrize("raw, expected", [(154300, 154300), (154300.0, 154300),
                                           ("154 300", 154300)])
def test_int_accepts_numbers_and_spaced_text(raw, expected):
    assert parse_int(raw) == expected


@pytest.mark.parametrize("raw", [12.5, "12a", -1, True])
def test_int_rejects_fractions_text_and_negatives(raw):
    with pytest.raises(FieldError):
        parse_int(raw)


def test_int_range():
    with pytest.raises(FieldError, match="at most 2030"):
        parse_int(2031, minimum=1980, maximum=2030)


def test_decimal_accepts_comma_separator():
    assert parse_decimal("14,5") == 14.5


def test_yes_no_in_three_languages():
    assert parse_yes_no("Ha") is True
    assert parse_yes_no("нет") is False
    with pytest.raises(FieldError):
        parse_yes_no("maybe")


def test_field_required_and_optional_blanks():
    assert Field("x", "x", "x", required=False).clean("  ") is None
    with pytest.raises(FieldError, match="required"):
        Field("x", "x", "x").clean(None)


def test_field_choice_is_case_insensitive_and_canonical():
    f = Field("fuel", "f", "f", choices=("Dizel", "Metan"))
    assert f.clean("metan") == "Metan"
    with pytest.raises(FieldError, match="one of"):
        f.clean("Benzin")


def test_field_choice_then_parser():
    f = Field("ok", "o", "o", parse_yes_no, choices=("Yes", "No"))
    assert f.clean("yes") is True


def test_field_header_is_bilingual():
    assert Field("plate", "Davlat raqami", "Госномер").header == "Davlat raqami / Госномер"
