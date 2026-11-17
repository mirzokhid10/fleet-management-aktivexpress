"""Write audit log rows. Every change to fleet data goes through here."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db import models

from .models import AuditLog

# Never copied into the log.
SECRET_FIELDS = frozenset({"password"})


def plain(value: Any) -> Any:
    """JSON-safe value for the `changes` column."""
    if isinstance(value, models.Model):
        return str(value)
    if isinstance(value, (Decimal, dt.date, dt.time)):
        return str(value)
    if hasattr(value, "wkt"):  # GEOS geometry
        return value.wkt
    return value


def snapshot(obj: models.Model) -> dict[str, Any]:
    """Field values of obj, keyed by field name (FKs by their id)."""
    return {f.name: getattr(obj, f.attname) for f in obj._meta.concrete_fields
            if not f.primary_key and f.name not in SECRET_FIELDS}


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[Any]]:
    return {k: [plain(before.get(k)), plain(v)] for k, v in after.items()
            if before.get(k) != v}


def record(obj: models.Model, action: str, *, source: str, actor=None,
           changes: dict | None = None, reason: str = "") -> AuditLog:
    return AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        source=source,
        action=action,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=str(obj.pk),
        object_repr=str(obj)[:200],
        changes=changes or {},
        reason=reason[:300],
    )
