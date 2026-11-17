from django import forms
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _

MAX_UPLOAD_MB = 5


class ImportForm(forms.Form):
    file = forms.FileField(label=_("Filled data template (.xlsx)"),
                           validators=[FileExtensionValidator(["xlsx"])])

    def clean_file(self):
        f = self.cleaned_data["file"]
        if f.size > MAX_UPLOAD_MB * 1024 * 1024:
            raise forms.ValidationError(_("The file is larger than %(mb)s MB."),
                                        params={"mb": MAX_UPLOAD_MB})
        return f
