from django.contrib import admin
from .models import TelegramLog

@admin.register(TelegramLog)
class TelegramLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "ok", "kind", "chat_id")
    readonly_fields = ("created_at", "response_text", "message_preview")