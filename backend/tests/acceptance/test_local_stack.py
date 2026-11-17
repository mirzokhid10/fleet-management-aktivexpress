import re

import pytest
from pytest_bdd import parsers, scenarios, then, when

pytestmark = [pytest.mark.acceptance, pytest.mark.django_db]

scenarios("local_stack.feature")


@when("I open the home page", target_fixture="page")
def open_home(client):
    response = client.get("/")
    assert response.status_code == 200
    return response.content.decode()


@when("I open the health check", target_fixture="health")
def open_health(client):
    return client.get("/health/")


@then(parsers.parse('I see the page title "{title}"'))
def page_title(page, title):
    assert re.search(rf"<h2[^>]*>\s*{re.escape(title)}\s*</h2>", page)


def _menu_entries(page):
    """(label, tag) of each sidebar entry, in page order."""
    nav = page.split('data-testid="sidebar-nav"', 1)[1].split("</nav>", 1)[0]
    return re.findall(r'data-menu="[^"]+"[\s\S]*?class="menu-item-text"[^>]*>([^<]+)<', nav)


@then("the sidebar lists these pages in order")
def sidebar_pages(page, datatable):
    assert _menu_entries(page) == [row[0] for row in datatable[1:]]


@then(parsers.parse('"{label}" is marked as coming on day {day:d}'))
def coming_on_day(page, label, day):
    entry = re.search(rf'<span data-menu="[^"]+" aria-disabled="true" title="Coming on day {day}"'
                      rf'[\s\S]*?>{re.escape(label)}<', page)
    assert entry, f"{label} not disabled for day {day}"


@then("the database answers with PostGIS")
def database_ok(health):
    assert health.status_code == 200
    assert health.json()["checks"]["database"]["postgis"]


@then("the cache answers")
def cache_ok(health):
    assert health.json()["checks"]["cache"]["ok"] is True
