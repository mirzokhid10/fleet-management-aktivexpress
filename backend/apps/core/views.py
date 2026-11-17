from django.contrib.auth.decorators import login_not_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext as _

from apps.accounts.roles import STAFF, role_required

from .health import run_checks


@role_required(*STAFF)
def dashboard(request):
    return render(request, "core/dashboard.html", {"page_title": _("Dashboard")})


@login_not_required
def health(request):
    result = run_checks()
    return JsonResponse(result, status=200 if result["ok"] else 503)
