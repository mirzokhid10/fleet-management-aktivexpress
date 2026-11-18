from django.contrib import admin

from apps.core.admin_base import ModelAdmin

from . import log
from .models import AuditLog


class AuditedAdmin(ModelAdmin):
    """ModelAdmin that writes an audit log row for every add, change and delete."""

    def save_model(self, request, obj, form, change):
        before = {}
        if change:
            before = log.snapshot(type(obj).objects.get(pk=obj.pk))
        super().save_model(request, obj, form, change)
        changes = log.diff(before, log.snapshot(obj))
        if change and not changes:
            return
        log.record(obj, AuditLog.Action.UPDATE if change else AuditLog.Action.CREATE,
                   source=AuditLog.Source.WEB, actor=request.user, changes=changes)

    def delete_model(self, request, obj):
        log.record(obj, AuditLog.Action.DELETE, source=AuditLog.Source.WEB, actor=request.user)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            log.record(obj, AuditLog.Action.DELETE, source=AuditLog.Source.WEB,
                       actor=request.user)
        super().delete_queryset(request, queryset)


@admin.register(AuditLog)
class AuditLogAdmin(ModelAdmin):
    """Read-only: the database refuses UPDATE and DELETE on this table anyway."""

    list_display = ("at", "actor", "source", "action", "content_type", "object_repr")
    list_filter = ("source", "action", "content_type")
    search_fields = ("object_repr", "reason")
    date_hierarchy = "at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
