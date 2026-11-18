from django.contrib import admin

from apps.core.admin_base import ModelAdmin, StackedInline, TabularInline

from .models import (DailyReport, Entry, OilChange, PartRequest, Photo, Refuel, TireChange,
                     TireChangeWheel)


class DailyReportInline(StackedInline):
    model = DailyReport


class RefuelInline(StackedInline):
    model = Refuel


class OilChangeInline(StackedInline):
    model = OilChange


class TireChangeInline(StackedInline):
    model = TireChange


class PartRequestInline(StackedInline):
    model = PartRequest
    autocomplete_fields = ("item",)


class PhotoInline(TabularInline):
    model = Photo
    fk_name = "entry"
    extra = 0
    fields = ("kind", "file", "taken_at", "uploaded_by")
    raw_id_fields = ("uploaded_by",)


@admin.register(Entry)
class EntryAdmin(ModelAdmin):
    """For looking things up. Confirming and rejecting happens in the web
    approval inbox (Day 21), which keeps the audit log and the rules."""

    list_display = ("id", "kind", "status", "driver", "vehicle", "odometer_km", "submitted_at",
                    "decided_by")
    list_filter = ("kind", "status")
    date_hierarchy = "submitted_at"
    search_fields = ("driver__full_name", "vehicle__plate")
    raw_id_fields = ("driver", "vehicle", "shift", "decided_by", "resubmission_of")
    inlines = (DailyReportInline, RefuelInline, OilChangeInline, TireChangeInline,
               PartRequestInline, PhotoInline)

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(TireChangeWheel)
class TireChangeWheelAdmin(ModelAdmin):
    list_display = ("tire_change", "position")


@admin.register(Photo)
class PhotoAdmin(ModelAdmin):
    list_display = ("id", "kind", "entry", "document", "taken_at")
    list_filter = ("kind",)
    raw_id_fields = ("entry", "document", "uploaded_by")
