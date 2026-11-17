"""Check a filled data-template workbook and report every problem by row.

Used on Day 1 to tell the company what to fix, and on Day 5 as the first step
of the Excel import (only a report with no errors gets imported).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from .fields import FieldError, parse_phone, parse_plate
from .schema import ALL_SHEETS, Sheet
from .workbook import FIRST_DATA_ROW


@dataclass(frozen=True)
class Issue:
    sheet: str
    row: int | None
    column: str | None
    message: str

    def __str__(self) -> str:
        where = self.sheet
        if self.row is not None:
            where += f", row {self.row}"
        if self.column:
            where += f", {self.column}"
        return f"{where}: {self.message}"


@dataclass
class Report:
    rows: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def error(self, sheet: Sheet, row: int | None, column: str | None, message: str) -> None:
        self.issues.append(Issue(sheet.title, row, column, message))

    def summary(self) -> str:
        counts = ", ".join(f"{k}: {len(v)}" for k, v in self.rows.items())
        if self.ok:
            return f"OK — {counts}"
        lines = [f"{len(self.issues)} problem(s) — {counts}"]
        lines += [f"  - {issue}" for issue in self.issues]
        return "\n".join(lines)


def _is_blank_row(values: tuple) -> bool:
    return all(v is None or (isinstance(v, str) and not v.strip()) for v in values)


def _read_sheet(ws, sheet: Sheet, report: Report) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    width = len(sheet.fields)
    seen: dict[str, dict[Any, int]] = {f.key: {} for f in sheet.fields if f.unique}

    for row_no, values in enumerate(
        ws.iter_rows(min_row=FIRST_DATA_ROW, max_col=width, values_only=True),
        start=FIRST_DATA_ROW,
    ):
        values = tuple(values) + (None,) * (width - len(values))
        if _is_blank_row(values):
            continue
        clean: dict[str, Any] = {"_row": row_no}
        for fld, raw in zip(sheet.fields, values):
            try:
                clean[fld.key] = fld.clean(raw)
            except FieldError as exc:
                report.error(sheet, row_no, fld.header, f"{exc} (got {raw!r})")
                clean[fld.key] = None
                continue
            if fld.unique and clean[fld.key] is not None:
                first = seen[fld.key].setdefault(clean[fld.key], row_no)
                if first != row_no:
                    report.error(sheet, row_no, fld.header, f"duplicate of row {first}")
        rows.append(clean)

    if sheet.single_row and len(rows) != 1:
        report.error(sheet, None, None, f"fill exactly one row (found {len(rows)})")
    return rows


def _cross_checks(report: Report) -> None:
    by_key = {s.key: s for s in ALL_SHEETS}
    vehicles = report.rows.get("vehicles", [])
    drivers = report.rows.get("drivers", [])
    plates = {v["plate"]: v for v in vehicles if v.get("plate")}
    phones = {d["phone"] for d in drivers if d.get("phone")}
    models = {v["model"] for v in vehicles if v.get("model")}

    def unknown_plate(sheet_key: str, col: str, row: dict) -> None:
        sheet = by_key[sheet_key]
        report.error(sheet, row["_row"], sheet.field(col).header,
                     f"vehicle {row[col]} is not in the Vehicles sheet")

    vsheet = by_key["vehicles"]
    for v in vehicles:
        second, norm = v.get("second_fuel_type"), v.get("second_fuel_norm")
        if second and norm is None:
            report.error(vsheet, v["_row"], vsheet.field("second_fuel_norm").header,
                         "is required when there is a second fuel")
        elif norm is not None and not second:
            report.error(vsheet, v["_row"], vsheet.field("second_fuel_type").header,
                         "is required when there is a second fuel norm")
        if second and second == v.get("fuel_type"):
            report.error(vsheet, v["_row"], vsheet.field("second_fuel_type").header,
                         "must differ from the first fuel")
        for key in ("fuel_norm", "second_fuel_norm"):
            if v.get(key) == 0:
                report.error(vsheet, v["_row"], vsheet.field(key).header,
                             "must be more than 0")

    for d in drivers:
        if d.get("default_plate") and d["default_plate"] not in plates:
            unknown_plate("drivers", "default_plate", d)

    for s in report.rows.get("last_service", []):
        plate = s.get("plate")
        if not plate:
            continue
        if plate not in plates:
            unknown_plate("last_service", "plate", s)
        elif (s.get("odometer_km") is not None and plates[plate].get("odometer_km") is not None
              and s["odometer_km"] > plates[plate]["odometer_km"]):
            report.error(by_key["last_service"], s["_row"],
                         by_key["last_service"].field("odometer_km").header,
                         "is higher than the vehicle's current odometer")

    for i in report.rows.get("service_intervals", []):
        if i.get("model") and i["model"] not in models:
            sheet = by_key["service_intervals"]
            report.error(sheet, i["_row"], sheet.field("model").header,
                         f"model {i['model']} is not used by any vehicle")

    for doc in report.rows.get("documents", []):
        sheet = by_key["documents"]
        owner_header = sheet.field("owner").header
        if not doc.get("owner") or not doc.get("owner_type"):
            continue
        try:
            if doc["owner_type"] == "Vehicle":
                if parse_plate(doc["owner"]) not in plates:
                    report.error(sheet, doc["_row"], owner_header,
                                 f"vehicle {doc['owner']} is not in the Vehicles sheet")
            elif parse_phone(doc["owner"]) not in phones:
                report.error(sheet, doc["_row"], owner_header,
                             f"driver {doc['owner']} is not in the Drivers sheet")
        except FieldError as exc:
            report.error(sheet, doc["_row"], owner_header, str(exc))

    for g in report.rows.get("geofences", []):
        if (g.get("latitude") is None) != (g.get("longitude") is None):
            sheet = by_key["geofences"]
            report.error(sheet, g["_row"], None, "give both latitude and longitude, or neither")

    for st in report.rows.get("settings", []):
        if st.get("work_start") and st.get("work_end") and st["work_start"] >= st["work_end"]:
            sheet = by_key["settings"]
            report.error(sheet, st["_row"], sheet.field("work_end").header,
                         "must be later than the start of work")


def validate_workbook(path: str | Path) -> Report:
    report = Report()
    wb = load_workbook(path, data_only=True, read_only=True)
    try:
        for sheet in ALL_SHEETS:
            if sheet.title not in wb.sheetnames:
                report.error(sheet, None, None, "sheet is missing")
                report.rows[sheet.key] = []
                continue
            report.rows[sheet.key] = _read_sheet(wb[sheet.title], sheet, report)
    finally:
        wb.close()
    _cross_checks(report)
    return report
