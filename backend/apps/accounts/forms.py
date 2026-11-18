from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _

from .roles import can_use_web


class StaffLoginForm(AuthenticationForm):
    remember = forms.BooleanField(label=_("Keep me logged in"), required=False, initial=True)

    error_messages = {
        **AuthenticationForm.error_messages,
        "driver": _("Drivers use the Telegram bot, not the web app."),
        "telegram": _("Sign in with Telegram. Passwords are only for administrators."),
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not can_use_web(user):
            raise forms.ValidationError(self.error_messages["driver"], code="driver")
        if not user.is_superuser:  # Day 7: staff sign in through the bot
            raise forms.ValidationError(self.error_messages["telegram"], code="telegram")
