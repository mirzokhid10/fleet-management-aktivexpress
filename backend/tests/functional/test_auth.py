"""Login, logout, role access and language switching through real requests."""

import pytest
from django.conf import settings

from tests import factories as f

pytestmark = [pytest.mark.functional, pytest.mark.django_db]

PASSWORD = "test-only-Passw0rd"


def make_user(role="dispatcher", **kw):
    user = f.user(role=role, **kw)
    user.set_password(PASSWORD)
    user.save()
    return user


def test_anonymous_visitors_are_sent_to_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response["Location"] == "/accounts/login/?next=/"


def test_health_and_login_page_need_no_login(client):
    assert client.get("/health/").status_code == 200
    page = client.get("/accounts/login/")
    assert page.status_code == 200
    assert "Kirishni kompaniya Telegram botida tasdiqlang." in page.content.decode()


def test_administrator_password_login_lands_on_dashboard_in_their_language(client):
    user = make_user(role="director", language="ru", is_superuser=True, is_staff=True)
    response = client.post("/accounts/login/", {"username": user.username, "password": PASSWORD,
                                                "remember": "on"})
    assert response.status_code == 302 and response["Location"] == "/"
    assert response.cookies[settings.LANGUAGE_COOKIE_NAME].value == "ru"

    page = client.get("/").content.decode()
    assert "<title>Главная | Aktiv Fleet</title>" in page
    assert "Директор" in page  # role under the user's name


def test_staff_cannot_use_a_password_any_more(client):
    user = make_user(role="dispatcher")
    response = client.post("/accounts/login/", {"username": user.username, "password": PASSWORD})
    assert "Telegram orqali kiring" in response.content.decode()
    assert "_auth_user_id" not in client.session


def test_login_without_remember_ends_with_the_browser(client):
    user = make_user(role="director", is_superuser=True)
    client.post("/accounts/login/", {"username": user.username, "password": PASSWORD})
    assert client.session.get_expire_at_browser_close() is True


def test_driver_cannot_log_in_to_the_web(client):
    driver = make_user(role="driver")
    response = client.post("/accounts/login/", {"username": driver.username,
                                                "password": PASSWORD})
    assert response.status_code == 200
    assert "Telegram botdan foydalanadi" in response.content.decode()
    assert "_auth_user_id" not in client.session


def test_wrong_password_is_refused(client):
    user = make_user(role="director", is_superuser=True)
    response = client.post("/accounts/login/", {"username": user.username, "password": "nope"})
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session
    assert 'role="alert"' in response.content.decode()


def test_driver_with_a_session_gets_403_not_the_dashboard(client):
    client.force_login(f.user(role="driver"))
    response = client.get("/")
    assert response.status_code == 403
    assert "Ruxsat yo'q" in response.content.decode()


def test_logout_needs_post_and_returns_to_login(login_as):
    client = login_as("director")
    assert client.get("/accounts/logout/").status_code == 405
    response = client.post("/accounts/logout/")
    assert response["Location"] == "/accounts/login/"
    assert client.get("/").status_code == 302


def test_language_switch_is_saved_on_the_user(login_as):
    client = login_as("dispatcher")
    response = client.post("/accounts/language/", {"language": "ru", "next": "/"})
    assert response["Location"] == "/"
    client.user.refresh_from_db()
    assert client.user.language == "ru"
    assert "Главная" in client.get("/").content.decode()


def test_language_switch_ignores_unknown_language_and_foreign_redirects(login_as):
    client = login_as("dispatcher")
    response = client.post("/accounts/language/", {"language": "en",
                                                   "next": "https://evil.example/"})
    assert response["Location"] == "/"
    client.user.refresh_from_db()
    assert client.user.language == "uz"


def test_language_switch_works_before_login(client):
    response = client.post("/accounts/language/", {"language": "ru",
                                                   "next": "/accounts/login/"})
    assert response.cookies[settings.LANGUAGE_COOKIE_NAME].value == "ru"
    assert "Подтвердите вход в Telegram-боте компании." in \
        client.get("/accounts/login/").content.decode()


@pytest.mark.parametrize("role, shown, hidden", [
    ("director", ["settings", "map"], []),
    ("dispatcher", ["map", "vehicles"], ["settings"]),
    ("storekeeper", ["store", "maintenance"], ["map", "vehicles", "settings"]),
])
def test_sidebar_shows_only_what_the_role_may_use(login_as, role, shown, hidden):
    page = login_as(role).get("/").content.decode()
    for key in shown:
        assert f'data-menu="{key}"' in page
    for key in hidden:
        assert f'data-menu="{key}"' not in page


@pytest.mark.parametrize("url", ["/", "/accounts/login/"])
def test_language_switch_offers_uzbek_and_russian(login_as, url):
    page = login_as("director").get(url) if url == "/" else None
    if page is None:
        from django.test import Client
        page = Client().get(url)
    body = page.content.decode()
    assert 'name="language" value="uz"' in body
    assert 'name="language" value="ru"' in body
