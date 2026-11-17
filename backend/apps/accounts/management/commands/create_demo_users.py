"""Local development only: one user per role, so login by role can be tried.

    python manage.py create_demo_users # random password, printed once
    python manage.py create_demo_users --password ...
"""

import secrets

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User

DEMO_USERS = [
    # The director runs the admin panel (Day 5).
    ("demo-director", "Dilshod", "Rahimov", User.Role.DIRECTOR, "uz",
     {"is_staff": True, "is_superuser": True}),
    ("demo-dispatcher", "Malika", "Karimova", User.Role.DISPATCHER, "uz",
     {"approves_daily": True, "approves_fuel": True, "approves_service": True}),
    ("demo-storekeeper", "Sergey", "Ivanov", User.Role.STOREKEEPER, "ru", {"approves_parts": True}),
    ("demo-driver", "Vali", "Aliyev", User.Role.DRIVER, "uz", {}),
]


class Command(BaseCommand):
    help = "Create or reset the demo users (one per role). Refuses to run with DEBUG off."

    def add_arguments(self, parser):
        parser.add_argument("--password", help="Password for all demo users")

    def handle(self, *args, password=None, **options):
        if not settings.DEBUG:
            raise CommandError("Demo users are for local development (DJANGO_DEBUG=1) only.")
        password = password or secrets.token_urlsafe(9)
        for username, first, last, role, lang, flags in DEMO_USERS:
            user, created = User.objects.update_or_create(
                username=username,
                defaults=dict(first_name=first, last_name=last, role=role, language=lang, **flags),
            )
            user.set_password(password)
            user.save()
            self.stdout.write(f"{'created' if created else 'reset'}: {username} ({role})")
        self.stdout.write(self.style.WARNING(f"Password for all demo users: {password}"))
