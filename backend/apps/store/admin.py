from django.contrib import admin

from apps.audit.admin import AuditedAdmin

from .models import StockMovement, StoreItem, Supplier


@admin.register(Supplier)
class SupplierAdmin(AuditedAdmin):
    list_display = ("name", "phone")
    search_fields = ("name", "phone")


@admin.register(StoreItem)
class StoreItemAdmin(AuditedAdmin):
    list_display = ("name", "category", "unit", "min_level", "stock", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name",)


@admin.register(StockMovement)
class StockMovementAdmin(AuditedAdmin):
    list_display = ("created_at", "item", "kind", "quantity", "supplier", "vehicle")
    list_filter = ("kind",)
    date_hierarchy = "created_at"
    autocomplete_fields = ("item", "supplier", "vehicle")
    raw_id_fields = ("part_request", "created_by")
