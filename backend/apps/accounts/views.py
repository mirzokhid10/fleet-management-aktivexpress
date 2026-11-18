import segno
from django.conf import settings
from django.contrib.auth import login
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import activate
from django.views.decorators.http import require_POST

from . import telegram_login as tl
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


# --- sign in with Telegram (Day 7) ------------------------------------------

SESSION_LOGIN = "telegram_login_id"
SESSION_NEXT = "telegram_login_next"


def _safe_next(request, target: str) -> str:
    if target and url_has_allowed_host_and_scheme(target, {request.get_host()},
                                                  require_https=request.is_secure()):
        return target
    return reverse(settings.LOGIN_REDIRECT_URL)


@login_not_required
@require_POST
def telegram_start(request):
    """The "Sign in with Telegram" button: a new one-time sign-in for this browser."""
    login_ = tl.start(request.META.get("HTTP_USER_AGENT", ""), request.META.get("REMOTE_ADDR"))
    request.session[SESSION_LOGIN] = login_.pk
    request.session[SESSION_NEXT] = _safe_next(request, request.POST.get("next", ""))
    return redirect("accounts:telegram")


@login_not_required
def telegram_wait(request):
    """Shows the number to pick in the bot, the link and a QR code; polls status."""
    login_ = tl.TelegramLogin.objects.filter(pk=request.session.get(SESSION_LOGIN),
                                            status=tl.TelegramLogin.Status.PENDING).first()
    if login_ is None:
        return redirect("accounts:login")
    link = tl.deep_link(login_)
    qr = segno.make(link, error="m").svg_inline(scale=5, border=2, dark="#101828")
    return render(request, "accounts/telegram_wait.html", {
        "login": login_, "link": link, "qr": qr,
        "seconds": int(tl.LIFETIME.total_seconds())})


@login_not_required
def telegram_status(request):
    result, user = tl.status(request.session.get(SESSION_LOGIN))
    if result != "approved":
        return JsonResponse({"status": result})
    target = request.session.get(SESSION_NEXT) or reverse(settings.LOGIN_REDIRECT_URL)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    response = JsonResponse({"status": "ok", "next": target})
    return _set_language_cookie(response, user.language)
