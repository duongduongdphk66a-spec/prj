from django.contrib import admin
from .models import UserNotification

@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'title', 'notification_type', 'is_read', 'created_at')
    list_filter = ('is_read', 'notification_type', 'created_at')
    search_fields = ('recipient__username', 'title', 'message')
    readonly_fields = ('created_at', 'updated_at', 'read_at')
