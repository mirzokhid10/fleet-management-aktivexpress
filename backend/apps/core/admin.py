from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy
from unfold.widgets import UnfoldAdminSelectWidget

from apps.audit.admin import AuditedAdmin

from .models import CompanySettings

# Title of the admin home page (the rest of the branding is in settings.UNFOLD).
admin.site.index_title = gettext_lazy("Dashboard")


def _group_choices():
    from apps.bot.models import BotGroup

    return [("", "— none —")] + [(g.chat_id, g.title or g.chat_id)
                                 for g in BotGroup.objects.filter(is_member=True)]


class CompanySettingsForm(forms.ModelForm):
    # Day 11: pick from the groups the bot was added to, not a raw chat id.
    alert_chat_id = forms.TypedChoiceField(
        label="Alert group", required=False, coerce=int, empty_value=None,
        widget=UnfoldAdminSelectWidget,  # a custom field: give it the theme's look by hand
        help_text="Telegram group for manager alerts. Add the bot to the group first; "
                  "it then appears here.")

    class Meta:
        model = CompanySettings
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = _group_choices()
        current = self.instance.alert_chat_id
        if current and current not in {c for c, _ in choices}:
            choices.append((current, f"{current} (bot is no longer in this group)"))
        self.fields["alert_chat_id"].choices = choices


@admin.register(CompanySettings)
class CompanySettingsAdmin(AuditedAdmin):
    """One row (id=1). It cannot be added twice or deleted."""

    form = CompanySettingsForm

    def has_add_permission(self, request):
        return not CompanySettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
