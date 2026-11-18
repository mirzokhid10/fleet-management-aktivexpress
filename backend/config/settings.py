"""Django settings. Everything that differs between machines comes from the environment."""

from pathlib import Path
import os
from dotenv import load_dotenv

from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise ImproperlyConfigured(f"Set the {name} environment variable")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-insecure-key" if DEBUG else None)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")

INSTALLED_APPS = [
    # Unfold (admin theme) must come before django.contrib.admin.
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "apps.core",
    "apps.accounts",
    "apps.fleet",
    "apps.tracking",
    "apps.entries",
    "apps.store",
    "apps.documents",
    "apps.audit",
    "apps.maintenance",
    "apps.bot",
]

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.navigation",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "NAME": env("POSTGRES_DB", "fleet"),
        "USER": env("POSTGRES_USER", "fleet"),
        "PASSWORD": env("POSTGRES_PASSWORD", "fleet" if DEBUG else None),
        "CONN_MAX_AGE": 60,
    }
}

REDIS_URL = env("REDIS_URL", "redis://localhost:6379/0")
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache",
                      "LOCATION": REDIS_URL}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Uzbek first, Russian second. Full translation setup is Day 4.
LANGUAGE_CODE = "uz"
LANGUAGES = [("uz", "O'zbekcha"), ("ru", "Русский")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Photos and scans. Local disk now, MinIO (S3) from Day 20.
MEDIA_URL = "media/"
MEDIA_ROOT = Path(env("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media")))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Telegram bot (Day 6) ------------------------------------------------------
# The token comes from @BotFather and lives only in .env.
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", "")
# Optional: asked from Telegram (getMe) and cached when empty.
TELEGRAM_BOT_USERNAME = env("TELEGRAM_BOT_USERNAME", "")
# polling: local development, no public URL needed.
# webhook: on the server; Telegram calls BOT_WEBHOOK_URL, checked with BOT_WEBHOOK_SECRET.
BOT_MODE = env("BOT_MODE", "polling")
BOT_WEBHOOK_URL = env("BOT_WEBHOOK_URL", "")
BOT_WEBHOOK_SECRET = env("BOT_WEBHOOK_SECRET", "")
BOT_WEBHOOK_PORT = int(env("BOT_WEBHOOK_PORT", "8080"))


# --- Django admin look: Unfold (https://unfoldadmin.com) -----------------------
# For superusers only. Colours follow the brand blue of the web app (TailAdmin).
def _admin_link(title, icon, app, model):
    return {
        "title": title, "icon": icon,
        "link": reverse_lazy(f"admin:{app}_{model}_changelist"),
        "permission": lambda request: request.user.has_perm(f"{app}.view_{model}"),
    }


UNFOLD = {
    "SITE_TITLE": "Aktiv Fleet admin",
    "SITE_HEADER": "Aktiv Fleet",
    "SITE_SUBHEADER": _("Admin"),
    "SITE_URL": "/",
    "SITE_SYMBOL": "local_shipping",
    "ENVIRONMENT": "apps.core.admin_dashboard.environment",
    "DASHBOARD_CALLBACK": "apps.core.admin_dashboard.dashboard",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "COLORS": {
        "primary": {
            "50": "rgb(236 243 255)", "100": "rgb(221 233 255)", "200": "rgb(194 214 255)",
            "300": "rgb(156 185 255)", "400": "rgb(117 146 255)", "500": "rgb(70 95 255)",
            "600": "rgb(54 65 245)", "700": "rgb(42 49 216)", "800": "rgb(37 45 174)",
            "900": "rgb(38 46 137)", "950": "rgb(22 25 80)",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {"title": _("Overview"), "items": [
                {"title": _("Dashboard"), "icon": "dashboard", "link": reverse_lazy("admin:index")},
                {"title": _("Open the web app"), "icon": "open_in_new", "link": "/"},
            ]},
            {"title": _("Fleet"), "collapsible": True, "items": [
                _admin_link(_("Vehicles"), "local_shipping", "fleet", "vehicle"),
                _admin_link(_("Drivers"), "badge", "fleet", "driver"),
                _admin_link(_("Shifts"), "schedule", "fleet", "shift"),
                _admin_link(_("Documents"), "description", "documents", "document"),
            ]},
            {"title": _("Tracking"), "collapsible": True, "items": [
                _admin_link(_("Location sharing"), "share_location", "tracking", "livesession"),
                _admin_link(_("Location points"), "location_on", "tracking", "locationpoint"),
                _admin_link(_("Location alerts"), "location_off", "tracking", "sharinggap"),
                _admin_link(_("Geofences"), "fence", "tracking", "geofence"),
            ]},
            {"title": _("Driver entries"), "collapsible": True, "items": [
                _admin_link(_("Entries"), "assignment", "entries", "entry"),
                _admin_link(_("Photos"), "photo_camera", "entries", "photo"),
                _admin_link(_("Tyre change wheels"), "tire_repair", "entries", "tirechangewheel"),
            ]},
            {"title": _("Maintenance & store"), "collapsible": True, "items": [
                _admin_link(_("Service records"), "build", "maintenance", "servicerecord"),
                _admin_link(_("Service intervals"), "event_repeat", "maintenance",
                            "serviceinterval"),
                _admin_link(_("Store items"), "inventory_2", "store", "storeitem"),
                _admin_link(_("Stock movements"), "swap_vert", "store", "stockmovement"),
                _admin_link(_("Suppliers"), "storefront", "store", "supplier"),
            ]},
            {"title": _("People & Telegram"), "collapsible": True, "items": [
                _admin_link(_("Users"), "person", "accounts", "user"),
                _admin_link(_("Permission groups"), "group", "auth", "group"),
                _admin_link(_("Telegram users"), "chat", "bot", "botuser"),
                _admin_link(_("Telegram groups"), "forum", "bot", "botgroup"),
            ]},
            {"title": _("System"), "collapsible": True, "items": [
                _admin_link(_("Company settings"), "settings", "core", "companysettings"),
                _admin_link(_("Audit log"), "history", "audit", "auditlog"),
            ]},
        ],
    },
}
