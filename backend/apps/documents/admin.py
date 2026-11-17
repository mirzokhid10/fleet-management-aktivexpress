from django.contrib import admin

from apps.audit.admin import AuditedAdmin

from .models import Document


@admin.register(Document)
class DocumentAdmin(AuditedAdmin):
    list_display = ("doc_type", "vehicle", "driver", "number", "expires_on")
    list_filter = ("doc_type",)
    search_fields = ("number", "vehicle__plate", "driver__full_name")
    date_hierarchy = "expires_on"
    autocomplete_fields = ("vehicle", "driver")
