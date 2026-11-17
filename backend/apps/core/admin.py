from django.contrib import admin

from apps.audit.admin import AuditedAdmin

from .models import CompanySettings

admin.site.site_header = "Aktiv Fleet — admin"
admin.site.site_title = "Aktiv Fleet admin"
admin.site.index_title = "Data"
admin.site.site_url = "/"


@admin.register(CompanySettings)
class CompanySettingsAdmin(AuditedAdmin):
    """One row (id=1). It cannot be added twice or deleted."""

    def has_add_permission(self, request):
        return not CompanySettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
