"""Import vehicles and drivers from the company data template (Day 5).

Two steps, so nobody imports blind:

    plan = plan_import(path)          # read + check + compare with the database
    plan = apply_import(path, actor)  # same, then write it all in one transaction

Rows are matched by plate (vehicles) and Telegram phone (drivers), so the
same file can be imported again after fixes: existing rows are updated, new
rows are added, nothing is deleted. Only the Vehicles and Drivers sheets are
used today; the other sheets are imported on their own roadmap days.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.audit import log
from apps.audit.models import AuditLog
from fleet_import.fields import format_plate
from fleet_import.schema import DRIVERS, VEHICLES, Sheet
from fleet_import.validate import Issue, validate_workbook

from .models import Driver, Vehicle

SHEETS = (VEHICLES, DRIVERS)
CREATE, UPDATE, SAME = "create", "update", "same"


class ImportBlocked(Exception):
    """apply_import was called on a file that still has problems."""


@dataclass
class RowPlan:
    row: int
    key: str  # plate as people write it, or phone
    label: str  # brand + model, or full name
    action: str  # create / update / same
    changes: dict[str, list[Any]] = field(default_factory=dict)


@dataclass
class ImportPlan:
    vehicles: list[RowPlan] = field(default_factory=list)
    drivers: list[RowPlan] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def count(self, kind: str, action: str) -> int:
        return sum(1 for r in getattr(self, kind) if r.action == action)

    def summary(self) -> str:
        parts = [f"{kind}: {self.count(kind, CREATE)} new, {self.count(kind, UPDATE)} changed, "
                 f"{self.count(kind, SAME)} unchanged" for kind in ("vehicles", "drivers")]
        lines = ["; ".join(parts)]
        if self.issues:
            lines.insert(0, f"{len(self.issues)} problem(s) — nothing imported")
            lines += [f"  - {issue}" for issue in self.issues]
        return "\n".join(lines)


def _dec(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(value)).quantize(Decimal("0.01"))


def _vehicle_values(row: dict) -> dict[str, Any]:
    return {
        "brand": row["brand"],
        "model": row["model"],
        "year": row["year"],
        "vin": row["vin"],
        "odometer_km": row["odometer_km"],
        "fuel_type": row["fuel_type"],
        "fuel_norm": _dec(row["fuel_norm"]),
        "second_fuel_type": row.get("second_fuel_type") or "",
        "second_fuel_norm": _dec(row.get("second_fuel_norm")),
        "notes": row.get("notes") or "",
    }


def _driver_values(row: dict, vehicles: dict[str, Vehicle]) -> dict[str, Any]:
    plate = row.get("default_plate")
    return {
        "full_name": row["full_name"],
        "licence_number": row["licence_number"],
        "licence_categories": row.get("licence_categories") or "",
        "licence_expiry": row["licence_expiry"],
        "default_vehicle": vehicles.get(plate) if plate else None,
    }


def _issue(sheet: Sheet, row: int, column: str | None, message: str) -> Issue:
    header = sheet.field(column).header if column else None
    return Issue(sheet.title, row, header, message)


def _changes(current, values: dict[str, Any]) -> dict[str, list[Any]]:
    """{field: [now, from the file]} for values that differ from the database."""
    def plain(value):
        return value.plate_display if isinstance(value, Vehicle) else log.plain(value)

    return {name: [plain(getattr(current, name)), plain(value)]
            for name, value in values.items()
            if plain(getattr(current, name)) != plain(value)}


def _model_errors(sheet: Sheet, row: int, obj, column_of: dict[str, str]) -> list[Issue]:
    """Run the model's own checks (validators, unique, constraints) on obj."""
    try:
        obj.full_clean(exclude=["user"] if isinstance(obj, Driver) else None)
    except ValidationError as exc:
        return [_issue(sheet, row, column_of.get(name), " ".join(msgs))
                for name, msgs in exc.message_dict.items()]
    return []


_VEHICLE_COLUMNS = {f: f for f in ("brand", "model", "year", "vin", "odometer_km", "fuel_type",
                                   "fuel_norm", "second_fuel_type", "second_fuel_norm",
                                   "notes")} | {"plate": "plate"}
_DRIVER_COLUMNS = {"full_name": "full_name", "phone": "phone",
                   "licence_number": "licence_number", "licence_categories": "licence_categories",
                   "licence_expiry": "licence_expiry", "default_vehicle": "default_plate"}


def _build(path: str | Path) -> tuple[ImportPlan, list[Vehicle], list[Driver]]:
    """Check the file and build unsaved objects. Writes nothing."""
    report = validate_workbook(path)
    plan = ImportPlan()
    titles = {s.title for s in SHEETS}
    plan.issues = [i for i in report.issues if i.sheet in titles]
    if plan.issues:
        return plan, [], []

    existing_v = {v.plate: v for v in Vehicle.objects.filter(
        plate__in=[r["plate"] for r in report.rows["vehicles"]])}
    vehicles: list[Vehicle] = []
    by_plate: dict[str, Vehicle] = dict(existing_v)
    for row in report.rows["vehicles"]:
        values = _vehicle_values(row)
        current = existing_v.get(row["plate"])
        changes = _changes(current, values) if current else {}
        obj = current or Vehicle(plate=row["plate"])
        if current and values["odometer_km"] < current.odometer_km:
            plan.issues.append(_issue(VEHICLES, row["_row"], "odometer_km",
                                      f"is lower than {current.odometer_km} km already in the "
                                      "system; the odometer cannot go back"))
        for name, value in values.items():
            setattr(obj, name, value)
        plan.issues += _model_errors(VEHICLES, row["_row"], obj, _VEHICLE_COLUMNS)
        action = CREATE if not current else (UPDATE if changes else SAME)
        plan.vehicles.append(RowPlan(row["_row"], format_plate(row["plate"]),
                                     f"{row['brand']} {row['model']}", action, changes))
        vehicles.append(obj)
        by_plate[row["plate"]] = obj

    existing_d = {d.phone: d for d in Driver.objects.select_related("default_vehicle").filter(
        phone__in=[r["phone"] for r in report.rows["drivers"]])}
    drivers: list[Driver] = []
    for row in report.rows["drivers"]:
        values = _driver_values(row, by_plate)
        current = existing_d.get(row["phone"])
        changes = _changes(current, values) if current else {}
        obj = current or Driver(phone=row["phone"])
        for name, value in values.items():
            setattr(obj, name, value)
        plan.issues += _model_errors(DRIVERS, row["_row"], obj, _DRIVER_COLUMNS)
        action = CREATE if not current else (UPDATE if changes else SAME)
        plan.drivers.append(RowPlan(row["_row"], row["phone"], row["full_name"], action,
                                    changes))
        drivers.append(obj)
    return plan, vehicles, drivers


def plan_import(path: str | Path) -> ImportPlan:
    return _build(path)[0]


def apply_import(path: str | Path, actor=None) -> ImportPlan:
    """Import the file, all or nothing. Raises ImportBlocked if it has problems."""
    with transaction.atomic():
        plan, vehicles, drivers = _build(path)
        if not plan.ok:
            raise ImportBlocked(plan)
        try:
            for objs, rows in ((vehicles, plan.vehicles), (drivers, plan.drivers)):
                for obj, row in zip(objs, rows):
                    if row.action == SAME:
                        continue
                    obj.save()  # a driver's new default vehicle already has its id here
                    if row.action == CREATE:
                        changes = {k: v for k, v in log.diff({}, log.snapshot(obj)).items()
                                   if v[1] not in ("", None)}
                        log.record(obj, AuditLog.Action.CREATE, source=AuditLog.Source.IMPORT,
                                   actor=actor, changes=changes)
                    else:
                        log.record(obj, AuditLog.Action.UPDATE, source=AuditLog.Source.IMPORT,
                                   actor=actor, changes=row.changes)
        except IntegrityError as exc:  # e.g. two rows swapping VINs
            raise ImportBlocked(plan) from exc
    return plan
