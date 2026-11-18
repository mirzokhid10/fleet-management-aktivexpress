"""The look of the Django admin: the Unfold theme (https://unfoldadmin.com).

Every admin class in the project inherits ModelAdmin (or AuditedAdmin, which
inherits it) from here, and inlines use the classes below, so the whole admin
gets the same style. Plain django.contrib.admin classes would render unstyled.
"""

from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import StackedInline as UnfoldStackedInline
from unfold.admin import TabularInline as UnfoldTabularInline


class ModelAdmin(UnfoldModelAdmin):
    warn_unsaved_form = True  # ask before leaving a form with changes
    list_filter_submit = True  # filters apply on a button, not on every click
    list_per_page = 50


class StackedInline(UnfoldStackedInline):
    pass


class TabularInline(UnfoldTabularInline):
    pass
