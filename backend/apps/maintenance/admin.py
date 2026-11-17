from django.contrib import admin

from apps.audit.admin import AuditedAdmin

from .models import ServiceInterval, ServiceRecord


@admin.register(ServiceInterval)
class ServiceIntervalAdmin(AuditedAdmin):
    list_display = ("vehicle_model", "service", "interval_km", "interval_months")
    list_filter = ("service",)


@admin.register(ServiceRecord)
class ServiceRecordAdmin(AuditedAdmin):
    list_display = ("vehicle", "service", "done_on", "odometer_km", "source", "cost_uzs")
    list_filter = ("service", "source")
    date_hierarchy = "done_on"
    autocomplete_fields = ("vehicle",)
    raw_id_fields = ("entry",)
