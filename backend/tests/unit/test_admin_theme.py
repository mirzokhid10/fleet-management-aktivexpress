"""Unit tests for the Django admin theme (Unfold) and its sidebar."""

import pytest
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.utils import translation
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import StackedInline, TabularInline

from apps.core.admin_dashboard import environment
from tests import factories as f

pytestmark = pytest.mark.unit


def _sidebar_items():
    return [item for group in settings.UNFOLD["SIDEBAR"]["navigation"]
            for item in group["items"]]


def _request(user):
    request = RequestFactory().get("/admin/")
    request.user = user
    return request


@pytest.mark.parametrize("model, model_admin", list(admin.site._registry.items()),
                         ids=lambda x: getattr(x, "__name__", type(x).__name__))
def test_every_admin_page_uses_the_theme(model, model_admin):
    assert isinstance(model_admin, UnfoldModelAdmin)
    for inline in model_admin.inlines:
        assert issubclass(inline, (StackedInline, TabularInline)), inline


def test_every_link_in_the_sidebar_resolves():
    links = [str(item["link"]) for item in _sidebar_items()]
    assert all(link.startswith("/") for link in links)
    assert len(links) == len(set(links))


def test_every_admin_model_is_in_the_sidebar():
    linked = {str(item["link"]) for item in _sidebar_items()}
    for model in admin.site._registry:
        url = f"/admin/{model._meta.app_label}/{model._meta.model_name}/"
        assert url in linked, f"{model.__name__} is missing from UNFOLD['SIDEBAR']"


@pytest.mark.django_db
def test_sidebar_link_shows_only_with_permission():
    vehicles = next(i for i in _sidebar_items() if str(i["link"]) == "/admin/fleet/vehicle/")
    boss = f.user(is_superuser=True, is_staff=True)
    clerk = f.user(is_staff=True)
    assert vehicles["permission"](_request(boss)) is True
    assert vehicles["permission"](_request(clerk)) is False
    assert vehicles["permission"](_request(AnonymousUser())) is False


def test_environment_badge_only_in_development(settings):
    settings.DEBUG = True
    with translation.override("uz"):
        assert environment(None) == ["Sinov nusxasi", "warning"]
    with translation.override("ru"):
        assert environment(None) == ["Тестовая копия", "warning"]
    settings.DEBUG = False
    assert environment(None) is None
