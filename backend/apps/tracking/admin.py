from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from apps.audit.admin import AuditedAdmin

from .models import Geofence, LiveSession, LocationPoint, SharingGap, Trip


@admin.register(Geofence)
class GeofenceAdmin(AuditedAdmin, GISModelAdmin):
    list_display = ("name", "kind", "address", "radius_m", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("name", "address")


@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    list_display = ("shift", "started_at", "last_update_at", "ended_at", "end_reason")
    date_hierarchy = "started_at"
    raw_id_fields = ("shift",)


@admin.register(LocationPoint)
class LocationPointAdmin(admin.ModelAdmin):
    """Points come from the bot only; the admin can look but not touch."""

    list_display = ("vehicle", "recorded_at", "speed_kmh", "accuracy_m", "is_valid")
    list_filter = ("is_valid",)
    date_hierarchy = "recorded_at"
    raw_id_fields = ("vehicle", "shift", "session")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SharingGap)
class SharingGapAdmin(admin.ModelAdmin):
    list_display = ("shift", "since", "alerted_at", "resolved_at")
    date_hierarchy = "since"
    raw_id_fields = ("shift",)


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    """Trips are made from points (apps/tracking/trips.py); look, don't touch."""

    list_display = ("vehicle", "started_at", "ended_at", "distance_m", "max_speed_kmh", "points")
    date_hierarchy = "started_at"
    raw_id_fields = ("vehicle", "shift")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
