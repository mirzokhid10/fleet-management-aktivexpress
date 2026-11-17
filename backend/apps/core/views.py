from django.http import JsonResponse
from django.shortcuts import render

from .health import run_checks


def dashboard(request):
    return render(request, "core/dashboard.html", {"page_title": "Dashboard"})


def health(request):
    result = run_checks()
    return JsonResponse(result, status=200 if result["ok"] else 503)
