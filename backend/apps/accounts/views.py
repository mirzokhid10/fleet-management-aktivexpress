from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import activate
from django.views.decorators.http import require_POST

from .forms import StaffLoginForm

LANGUAGE_CODES = {code for code, _ in settings.LANGUAGES}


def _set_language_cookie(response, code: str):
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, code,
                        max_age=settings.LANGUAGE_COOKIE_AGE, samesite="Lax")
    return response


@method_decorator(login_not_required, name="dispatch")
class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    form_class = StaffLoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        if not form.cleaned_data.get("remember"):
            self.request.session.set_expiry(0)  # until the browser closes
        # The interface follows the language saved on the user.
        return _set_language_cookie(response, form.get_user().language)


class LogoutView(auth_views.LogoutView):
    pass


@login_not_required
@require_POST
def switch_language(request):
    code = request.POST.get("language", "")
    target = request.POST.get("next") or "/"
    if not url_has_allowed_host_and_scheme(target, {request.get_host()},
                                           require_https=request.is_secure()):
        target = "/"
    response = HttpResponseRedirect(target)
    if code not in LANGUAGE_CODES:
        return response
    if request.user.is_authenticated and request.user.language != code:
        request.user.language = code
        request.user.save(update_fields=["language"])
    activate(code)
    return _set_language_cookie(response, code)
