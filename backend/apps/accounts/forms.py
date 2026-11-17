from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _

from .roles import can_use_web


class StaffLoginForm(AuthenticationForm):
    remember = forms.BooleanField(label=_("Keep me logged in"), required=False, initial=True)

    error_messages = {
        **AuthenticationForm.error_messages,
        "driver": _("Drivers use the Telegram bot, not the web app."),
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not can_use_web(user):
            raise forms.ValidationError(self.error_messages["driver"], code="driver")
