"""Managers confirm who registered in the bot (Day 7)."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.accounts.roles import DIRECTOR, MANAGERS, has_role, role_required

from . import notify
from . import registration as reg
from .models import RegistrationRequest

RECENT = 20


def _visible(user):
    qs = RegistrationRequest.objects.select_related("bot_user", "driver", "staff", "decided_by")
    # Dispatchers see driver requests only; staff requests are the director's.
    return qs if has_role(user, {DIRECTOR}) else qs.filter(staff__isnull=True)


@role_required(*MANAGERS)
def request_list(request):
    qs = _visible(request.user)
    return render(request, "bot/request_list.html", {
        "page_title": _("New users"),
        "pending": qs.filter(status=RegistrationRequest.Status.PENDING).order_by("created_at"),
        "recent": qs.exclude(status=RegistrationRequest.Status.PENDING)
                    .order_by("-decided_at")[:RECENT],
        "reasons": RegistrationRequest.RejectReason.choices,
    })


def _decide(request, pk):
    req = get_object_or_404(RegistrationRequest, pk=pk)
    if not reg.can_decide(request.user, req):
        raise PermissionDenied
    if req.status != RegistrationRequest.Status.PENDING:
        messages.error(request, _("Someone has already decided this request."))
        return None
    return req


@require_POST
@role_required(*MANAGERS)
def approve(request, pk):
    req = _decide(request, pk)
    if req:
        user = reg.approve(req, request.user)
        sent = notify.send(req.bot_user.telegram_id, req.bot_user.language, lambda: _(
            "✅ Your registration is confirmed. Welcome, %(name)s!") % {"name": user.first_name
                                                                       or user})
        messages.success(request, _("%(name)s is registered.") % {"name": req.person_name})
        if not sent:
            messages.error(request, _("The bot could not send them a message."))
    return redirect("bot:requests")


@require_POST
@role_required(*MANAGERS)
def reject(request, pk):
    req = _decide(request, pk)
    if req:
        reason = request.POST.get("reason", "")
        if reason not in RegistrationRequest.RejectReason.values:
            reason = RegistrationRequest.RejectReason.OTHER
        reg.reject(req, request.user, reason)
        notify.send(req.bot_user.telegram_id, req.bot_user.language, lambda: _(
            "❌ Your registration was not confirmed. Ask the dispatcher if this is a mistake."))
        messages.success(request, _("The request was rejected."))
    return redirect("bot:requests")
