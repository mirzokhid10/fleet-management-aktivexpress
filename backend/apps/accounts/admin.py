from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from apps.audit.admin import AuditedAdmin
from apps.core.admin_base import ModelAdmin

from .models import User


@admin.register(User)
class UserAdmin(AuditedAdmin, BaseUserAdmin):
    # Unfold's versions of the user forms, so passwords and the rest look the same.
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm

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


# Django registers Group with its plain admin; register it again in the theme.
admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass
