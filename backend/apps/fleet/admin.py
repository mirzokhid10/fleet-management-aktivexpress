from django.contrib import admin

from apps.audit.admin import AuditedAdmin

from .models import Driver, Shift, Vehicle


@admin.register(Vehicle)
class VehicleAdmin(AuditedAdmin):
    list_display = ("plate_display", "brand", "model", "year", "fuel_type", "second_fuel_type",
                    "odometer_km", "is_active")
    list_filter = ("is_active", "fuel_type", "brand")
    search_fields = ("plate", "vin", "brand", "model")

    @admin.display(description="Plate", ordering="plate")
    def plate_display(self, obj):
        return obj.plate_display


@admin.register(Driver)
class DriverAdmin(AuditedAdmin):
    list_display = ("full_name", "phone", "licence_number", "licence_expiry", "default_vehicle",
                    "user", "is_active")
    list_filter = ("is_active",)
    search_fields = ("full_name", "phone", "licence_number")
    autocomplete_fields = ("default_vehicle", "user")


@admin.register(Shift)
class ShiftAdmin(AuditedAdmin):
    list_display = ("driver", "vehicle", "started_at", "ended_at")
    list_filter = ("vehicle",)
    date_hierarchy = "started_at"
    autocomplete_fields = ("driver", "vehicle")
