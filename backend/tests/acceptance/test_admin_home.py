import pytest
from django.forms.models import model_to_dict
from django.urls import reverse
from pytest_bdd import given, parsers, scenarios, then, when

from apps.bot.models import BotGroup
from apps.core.models import CompanySettings
from tests import factories as f

pytestmark = [pytest.mark.acceptance, pytest.mark.django_db]

scenarios("admin_home.feature")

WARNING = "Ogohlantirish guruhi tanlanmagan"
SETTINGS_URL = reverse("admin:core_companysettings_change", args=[1])


@pytest.fixture
def ctx(client):
    director = f.user(role="director", is_superuser=True, is_staff=True)
    client.force_login(director)
    return {"client": client, "director": director}


@given(parsers.parse("{active:d} active vehicles and {retired:d} retired vehicle"))
def vehicles(active, retired):
    for _ in range(active):
        f.vehicle()
    for _ in range(retired):
        f.vehicle(is_active=False)


@given(parsers.parse('"{name}" is on shift'))
def on_shift(name):
    f.shift(driver=f.driver(full_name=name))  # brings one more vehicle


@given(parsers.parse('the bot was added to the Telegram group "{title}"'))
def group(title):
    BotGroup.objects.create(chat_id=-1001234567890, title=title, is_member=True)


@when("the director opens the admin")
def open_admin(ctx):
    ctx["page"] = ctx["client"].get("/admin/")
    assert ctx["page"].status_code == 200


@then(parsers.parse("they see {vehicles:d} active vehicles and {on_shift:d} on shift now"))
def see_counts(ctx, vehicles, on_shift):
    counts = {s["title"]: s["value"] for s in ctx["page"].context["stats"]}
    assert counts["Faol avtomobillar"] == vehicles
    assert counts["Hozir smenada"] == on_shift


@then("they are warned that the alert group is not set")
def warned(ctx):
    assert WARNING in ctx["page"].content.decode()


@when(parsers.parse('they choose "{title}" as the alert group in Company settings'))
def choose(ctx, title):
    chat_id = BotGroup.objects.get(title=title).chat_id
    data = {k: v for k, v in model_to_dict(CompanySettings.load()).items()
            if v is not None and k != "id"}
    data["alert_chat_id"] = chat_id
    response = ctx["client"].post(SETTINGS_URL, data)
    assert response.status_code == 302, response.context["adminform"].form.errors
    assert CompanySettings.load().alert_chat_id == chat_id


@then("the warning is gone")
def warning_gone(ctx):
    open_admin(ctx)
    assert WARNING not in ctx["page"].content.decode()


@then("the change to Company settings is listed under recent changes")
def listed(ctx):
    rows = ctx["page"].context["recent_changes"]["rows"]
    _when, who, _action, what = rows[0]
    assert who == ctx["director"]
    assert "Company settings" in what
