"""The web app through Django's test client, against the real PostGIS and Redis."""

import pytest
from django.core.management import call_command

pytestmark = [pytest.mark.functional, pytest.mark.django_db]


def test_dashboard_renders_tailadmin_layout(login_as):
    html = login_as("director").get("/").content.decode()

    assert 'data-testid="sidebar-nav"' in html
    assert "/static/css/app.css" in html
    assert "/static/vendor/alpine.min.js" in html
    assert "<title>Bosh sahifa | Aktiv Fleet</title>" in html


def test_dashboard_link_is_active_and_unbuilt_pages_are_disabled(login_as):
    html = login_as("director").get("/").content.decode()

    assert 'data-menu="dashboard"' in html
    assert 'aria-current="page"' in html
    assert html.count('aria-disabled="true"') == 8  # live: vehicles, drivers, shifts, map…
    assert "14-kun" in html  # Trips, "Day 14" in Uzbek


def test_health_reports_postgis_and_cache(client):
    response = client.get("/health/")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["checks"]["database"]["postgis"].startswith("3.")
    assert body["checks"]["cache"] == {"ok": True}


def test_health_returns_503_when_a_service_is_down(client, monkeypatch):
    from apps.core import health

    def down():
        raise ConnectionError

    monkeypatch.setitem(health.CHECKS, "cache", down)
    response = client.get("/health/")
    assert response.status_code == 503
    assert response.json()["checks"]["cache"] == {"ok": False, "error": "ConnectionError"}


def test_admin_login_page_is_served(client):
    assert client.get("/admin/login/").status_code == 200


def test_no_missing_migrations():
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)
