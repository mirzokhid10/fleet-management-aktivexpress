"""The Django admin in the Unfold theme: every page opens, the home page sums up the fleet."""

import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.urls import reverse

from apps.audit import log
from apps.audit.models import AuditLog
from apps.bot.models import BotGroup
from apps.core.models import CompanySettings
from tests import factories as f

pytestmark = [pytest.mark.functional, pytest.mark.django_db]

MODELS = list(admin.site._registry.items())
IDS = [m.__name__ for m, _ in MODELS]


@pytest.fixture
def boss(client):
    user = f.user(is_superuser=True, is_staff=True, first_name="Bosh", last_name="Direktor")
    client.force_login(user)
    client.user = user
    return client


def _url(model, page, *args):
    return reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_{page}", args=args)


@pytest.mark.parametrize("model, model_admin", MODELS, ids=IDS)
def test_every_list_and_add_page_opens(boss, model, model_admin):
    assert boss.get(_url(model, "changelist")).status_code == 200
    request = RequestFactory().get("/")
    request.user = boss.user
    expected = 200 if model_admin.has_add_permission(request) else 403
    assert boss.get(_url(model, "add")).status_code == expected


def test_pages_carry_the_theme(client):
    html = client.get("/admin/login/").content.decode()
    assert "unfold/css/styles.css" in html
    assert "Aktiv Fleet" in html


def test_people_without_staff_access_are_sent_to_the_admin_login(login_as):
    client = login_as("dispatcher")
    response = client.get("/admin/")
    assert response.status_code == 302
    assert response["Location"].startswith("/admin/login/")


def test_user_pages_use_the_theme_forms(boss):
    user = f.user(first_name="Vali")
    html = boss.get(_url(user._meta.model, "change", user.pk)).content.decode()
    assert "Aktiv Fleet" in html and "../password/" in html
    response = boss.get(reverse("admin:auth_user_password_change", args=[user.pk]))
    assert response.status_code == 200
    assert "Aktiv Fleet" in response.content.decode()


def test_company_settings_page_offers_bot_groups(boss):
    BotGroup.objects.create(chat_id=-100123, title="Dispetcherlar", is_member=True)
    CompanySettings.load()
    response = boss.get(_url(CompanySettings, "change", 1))
    assert "Dispetcherlar" in response.content.decode()
    field = response.context["adminform"].form["alert_chat_id"]
    assert "rounded-default" in str(field)  # the theme's select, not Django's plain one


def test_home_page_counts_the_fleet(boss):
    f.vehicle(), f.vehicle(), f.vehicle(is_active=False)
    f.shift(ended_at=f.timezone.now()), f.shift()  # each brings its own vehicle and driver
    response = boss.get("/admin/")
    counts = {s["title"]: s["value"] for s in response.context["stats"]}
    # The admin speaks the company language (Uzbek) like the rest of the site.
    assert counts == {"Faol avtomobillar": 4, "Faol haydovchilar": 2, "Hozir smenada": 1,
                      "Hozir joylashuvni ulashmoqda": 0, "Ochiq joylashuv ogohlantirishlari": 0}
    html = response.content.decode()
    for stat in response.context["stats"]:
        assert stat["title"] in html and f'href="{stat["url"]}"' in html.replace("&amp;", "&")


def test_home_page_warns_until_the_alert_group_is_chosen(boss):
    warning = "Ogohlantirish guruhi tanlanmagan"
    assert warning in boss.get("/admin/").content.decode()
    settings = CompanySettings.load()
    settings.alert_chat_id = -100123
    settings.save()
    assert warning not in boss.get("/admin/").content.decode()


def test_home_page_lists_recent_changes(boss):
    vehicle = f.vehicle(plate="01A777AA")
    log.record(vehicle, AuditLog.Action.CREATE, source=AuditLog.Source.WEB, actor=boss.user)
    response = boss.get("/admin/")
    rows = response.context["recent_changes"]["rows"]
    assert len(rows) == 1
    _when, who, _action, what = rows[0]
    assert str(who) == str(boss.user) and str(vehicle) in what
    html = response.content.decode()
    assert str(vehicle) in html
    assert reverse("admin:audit_auditlog_changelist") in html
