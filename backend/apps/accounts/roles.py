"""Who may open which part of the web app (Day 1 kickoff, section 2).

Drivers never use the web app; they work only in the Telegram bot.
"""

from __future__ import annotations

from functools import wraps

from django.core.exceptions import PermissionDenied

from .models import User

DIRECTOR = User.Role.DIRECTOR
DISPATCHER = User.Role.DISPATCHER
STOREKEEPER = User.Role.STOREKEEPER
DRIVER = User.Role.DRIVER

STAFF = frozenset({DIRECTOR, DISPATCHER, STOREKEEPER})
MANAGERS = frozenset({DIRECTOR, DISPATCHER})


def can_use_web(user) -> bool:
    return bool(user.is_authenticated and (user.role in STAFF or user.is_superuser))


def has_role(user, roles) -> bool:
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.role in roles


def role_required(*roles):
    """View decorator: 403 unless the user has one of the roles."""
    allowed = frozenset(roles)

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not has_role(request.user, allowed):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
