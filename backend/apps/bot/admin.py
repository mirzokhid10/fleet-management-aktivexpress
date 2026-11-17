from django.contrib import admin

from .models import BotUser


@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    list_display = ("telegram_id", "first_name", "last_name", "username", "language", "user",
                    "last_seen_at")
    list_filter = ("language",)
    search_fields = ("telegram_id", "first_name", "last_name", "username")
    raw_id_fields = ("user",)
    readonly_fields = ("telegram_id", "created_at", "last_seen_at")
