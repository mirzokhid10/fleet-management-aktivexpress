from django.contrib import admin

from apps.core.admin_base import ModelAdmin

from .models import BotGroup, BotUser


@admin.register(BotUser)
class BotUserAdmin(ModelAdmin):
    list_display = ("telegram_id", "first_name", "last_name", "username", "language", "user",
                    "last_seen_at")
    list_filter = ("language",)
    search_fields = ("telegram_id", "first_name", "last_name", "username")
    raw_id_fields = ("user",)
    readonly_fields = ("telegram_id", "created_at", "last_seen_at")


@admin.register(BotGroup)
class BotGroupAdmin(ModelAdmin):
    """Groups the bot was added to; they come from Telegram, not typed in."""

    list_display = ("title", "chat_id", "is_member", "added_at")
    readonly_fields = ("chat_id", "title", "is_member", "added_at", "updated_at")

    def has_add_permission(self, request):
        return False
