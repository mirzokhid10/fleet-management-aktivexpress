from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.audit.admin import AuditedAdmin

from .models import User


@admin.register(User)
class UserAdmin(AuditedAdmin, BaseUserAdmin):
    list_display = ("username", "first_name", "last_name", "role", "phone", "language",
                    "is_active", "last_login")
    list_filter = ("role", "is_active", "language", "is_staff")
    search_fields = ("username", "first_name", "last_name", "phone")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Aktiv Fleet", {"fields": ("role", "phone", "telegram_id", "language")}),
        ("Confirms driver entries", {"fields": ("approves_daily", "approves_fuel",
                                                "approves_service", "approves_parts")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Aktiv Fleet", {"fields": ("role", "first_name", "last_name", "phone", "language")}),
    )

