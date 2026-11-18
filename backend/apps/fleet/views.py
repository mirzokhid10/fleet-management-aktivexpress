"""Vehicle and driver lists, the Excel import (Day 5) and the shift log (Days 8–9)."""

from __future__ import annotations

import datetime as dt
import io
import secrets
from pathlib import Path
from zipfile import BadZipFile

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Exists, Max, OuterRef, Q, Sum
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from openpyxl.utils.exceptions import InvalidFileException

from apps.accounts.roles import MANAGERS, role_required
from apps.audit.models import AuditLog
from apps.bot import notify
from apps.tracking.models import LiveSession, LocationPoint
from fleet_import.schema import DRIVERS, VEHICLES
from fleet_import.workbook import build_workbook

from . import shifts
from .forms import ImportForm
from .importer import CREATE, UPDATE, ImportBlocked, apply_import, plan_import
from .models import Driver, Shift, Vehicle

PAGE_SIZE = 50
LICENCE_WARN_DAYS = 30
SESSION_KEY = "fleet_import_token"


def _search(request, queryset, fields):
    """?q= matches any of fields; spaces are ignored for plates and phones."""
    q = request.GET.get("q", "").strip()
    if q:
        cond = Q()
        for name in fields:
            value = q.replace(" ", "") if name in ("plate", "phone") else q
            cond |= Q(**{f"{name}__icontains": value})
        queryset = queryset.filter(cond)
    return q, queryset


@role_required(*MANAGERS)
def vehicle_list(request):
    q, qs = _search(request, Vehicle.objects.all(), ["plate", "brand", "model", "vin"])
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "fleet/vehicle_list.html", {
        "page_title": _("Vehicles"), "page": page, "q": q, "total": Vehicle.objects.count()})


@role_required(*MANAGERS)
def driver_list(request):
    q, qs = _search(request, Driver.objects.select_related("default_vehicle"),
                    ["full_name", "phone", "licence_number"])
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
    today = timezone.localdate()
    for d in page:
        d.licence_status = ("expired" if d.licence_expiry < today else
                            "soon" if d.licence_expiry <= today + dt.timedelta(LICENCE_WARN_DAYS)
                            else "ok")
    return render(request, "fleet/driver_list.html", {
        "page_title": _("Drivers"), "page": page, "q": q, "total": Driver.objects.count(),
        "warn_days": LICENCE_WARN_DAYS})


# --- import ----------------------------------------------------------------

def _upload_dir() -> Path:
    path = Path(settings.MEDIA_ROOT) / "imports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _upload_path(token: str) -> Path:
    return _upload_dir() / f"{token}.xlsx"


def _column(sheet, name: str) -> str:
    key = "default_plate" if name == "default_vehicle" else name
    return sheet.field(key).header


def _preview(plan) -> dict:
    """Counts and per-row changes, with the column names people know from Excel."""
    for sheet, rows in ((VEHICLES, plan.vehicles), (DRIVERS, plan.drivers)):
        for r in rows:
            r.changes_shown = {_column(sheet, k): v for k, v in r.changes.items()}
    return {
        "counts": [
            (_("New vehicles"), plan.count("vehicles", CREATE)),
            (_("Changed vehicles"), plan.count("vehicles", UPDATE)),
            (_("New drivers"), plan.count("drivers", CREATE)),
            (_("Changed drivers"), plan.count("drivers", UPDATE)),
        ],
        "sections": [(_("Vehicles"), plan.vehicles), (_("Drivers"), plan.drivers)],
    }


@role_required(*MANAGERS)
def import_upload(request):
    """Step 1: upload. Step 2 (same page): see what would change."""
    form = ImportForm(request.POST or None, request.FILES or None)
    context = {"page_title": _("Import from Excel"), "form": form}
    if request.method == "POST" and form.is_valid():
        token = secrets.token_urlsafe(16)
        path = _upload_path(token)
        with path.open("wb") as out:
            for chunk in form.cleaned_data["file"].chunks():
                out.write(chunk)
        try:
            plan = plan_import(path)
        except (BadZipFile, InvalidFileException, KeyError, OSError):
            path.unlink(missing_ok=True)
            form.add_error("file", _("This is not a valid Excel file."))
            return render(request, "fleet/import.html", context)
        old = request.session.get(SESSION_KEY)
        if old:
            _upload_path(old).unlink(missing_ok=True)
        if plan.ok:
            request.session[SESSION_KEY] = token
        else:
            path.unlink(missing_ok=True)
            request.session.pop(SESSION_KEY, None)
        context.update(plan=plan, token=token if plan.ok else None,
                       file_name=form.cleaned_data["file"].name, **_preview(plan))
    return render(request, "fleet/import.html", context)


@require_POST
@role_required(*MANAGERS)
def import_confirm(request):
    """Step 3: write it. Only the file this user just previewed can be imported."""
    token = request.POST.get("token", "")
    if not token or request.session.get(SESSION_KEY) != token:
        messages.error(request, _("The preview has expired. Upload the file again."))
        return redirect("fleet:import")
    path = _upload_path(token)
    try:
        plan = apply_import(path, actor=request.user)
    except (ImportBlocked, FileNotFoundError):
        messages.error(request, _("The data changed since the preview. Upload the file again."))
        return redirect("fleet:import")
    finally:
        path.unlink(missing_ok=True)
        request.session.pop(SESSION_KEY, None)
    messages.success(request, _(
        "Imported: %(nv)s new and %(uv)s changed vehicles, %(nd)s new and %(ud)s changed "
        "drivers.") % {"nv": plan.count("vehicles", CREATE),
                       "uv": plan.count("vehicles", UPDATE),
                       "nd": plan.count("drivers", CREATE),
                       "ud": plan.count("drivers", UPDATE)})
    return redirect("fleet:vehicles")


@role_required(*MANAGERS)
def import_template(request):
    """The blank company data template, always matching the current import."""
    buffer = io.BytesIO()
    build_workbook().save(buffer)
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename="fleet-data-template.xlsx")


# --- shift log (Day 8) -----------------------------------------------------

def _shift_filters(request, qs):
    """?q= driver or plate, ?day=YYYY-MM-DD (shifts that overlap that day), ?open=1."""
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(driver__full_name__icontains=q)
                       | Q(vehicle__plate__icontains=q.replace(" ", "")))
    try:
        day = parse_date(request.GET.get("day", "").strip())
    except ValueError:  # well-formed but impossible, e.g. 2026-02-30
        day = None
    if day:
        tz = timezone.get_current_timezone()
        day_start = dt.datetime.combine(day, dt.time.min, tzinfo=tz)
        day_end = day_start + dt.timedelta(days=1)
        qs = qs.filter(Q(started_at__lt=day_end),
                       Q(ended_at__isnull=True) | Q(ended_at__gt=day_start))
    only_open = request.GET.get("open") == "1"
    if only_open:
        qs = qs.filter(ended_at__isnull=True)
    return qs, {"q": q, "day": day, "only_open": only_open}


@role_required(*MANAGERS)
def shift_list(request):
    sharing = LiveSession.objects.filter(shift=OuterRef("pk"), ended_at__isnull=True)
    qs, filters = _shift_filters(request, Shift.objects.select_related("driver", "vehicle")
                                 .annotate(n_points=Count("points"), sharing=Exists(sharing),
                                           # Day 10: clean track only
                                           meters=Sum("points__distance_m",
                                                      filter=Q(points__is_valid=True)),
                                           top_speed=Max("points__speed_kmh",
                                                         filter=Q(points__is_valid=True)))
                                 # GROUP BY drops Meta.ordering, so say it again.
                                 .order_by("-started_at", "-pk"))
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
    keep = request.GET.copy()
    keep.pop("page", None)
    now = timezone.now()
    # Day 9: the latest point of each shift on this page, in one query.
    last = {p.shift_id: p for p in LocationPoint.objects
            .filter(shift__in=[s.pk for s in page]).order_by("shift_id", "-recorded_at")
            .distinct("shift_id")}
    for s in page:
        s.hours, s.minutes = shifts.hours_minutes(shifts.duration(s, now))
        s.last_point = last.get(s.pk)
        s.km = round((s.meters or 0) / 1000, 1)
    open_now = Shift.objects.filter(ended_at__isnull=True)
    return render(request, "fleet/shift_list.html", {
        "page_title": _("Shifts"), "page": page, **filters,
        "on_shift": open_now.count(),
        "sharing_now": open_now.filter(Exists(sharing)).count(),
        "filtered": any(filters.values()), "page_query": keep.urlencode(),
    })


@require_POST
@role_required(*MANAGERS)
def shift_end(request, pk):
    shift = get_object_or_404(Shift.objects.select_related("driver__user", "vehicle"), pk=pk)
    if not shifts.end(shift, actor=request.user, source=AuditLog.Source.WEB,
                      reason="Ended by a manager"):
        messages.error(request, _("This shift has already ended."))
    else:
        messages.success(request, _("The shift of %(driver)s with %(vehicle)s is ended.") % {
            "driver": shift.driver.full_name, "vehicle": shift.vehicle.plate_display})
        person = shift.driver.user
        if person and person.telegram_id:
            ended_at = timezone.localtime(shift.ended_at)
            notify.send(person.telegram_id, person.language, lambda: "\n".join([_(
                "The dispatcher ended your shift with %(vehicle)s at %(time)s. Send "
                "/start_shift when you take a vehicle again.") % {
                    "vehicle": shift.vehicle.plate_display, "time": f"{ended_at:%H:%M}"},
                _("You can stop sharing your location now.")]))
    back = request.POST.get("back", "")
    # Back to the same filtered list; only our own page, never another site.
    return redirect(back if back.startswith("/shifts/?") else "fleet:shifts")
