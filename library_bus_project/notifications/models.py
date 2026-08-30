import json
from datetime import datetime, timedelta
from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

from core.models import TimestampedModel, BaseQuerySet, BaseManager

class NotificationQuerySet(BaseQuerySet):
    def unread(self): return self.filter(is_read=False)
    def read(self): return self.filter(is_read=True)
    def recent(self, days=7): return self.filter(created_at__gte=timezone.now()-timedelta(days=days))
    def for_user(self, user): return self.filter(recipient=user)

class NotificationManager(BaseManager):
    def get_queryset(self): return NotificationQuerySet(self.model, using=self._db)
    def unread(self): return self.get_queryset().unread()
    def unread_for_user(self, user): return self.get_queryset().for_user(user).unread()
    def bulk_mark_read(self, user, notification_ids): 
        return self.filter(recipient=user, id__in=notification_ids).update(is_read=True, read_at=timezone.now())

class UserNotification(TimestampedModel):
    """Thông báo trực tiếp trên website"""
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='system_notifications', db_index=True, verbose_name="Người nhận")
    title = models.CharField(max_length=200, verbose_name="Tiêu đề")
    message = models.TextField(verbose_name="Nội dung")
    notification_type = models.CharField(max_length=30, default="info", verbose_name="Loại thông báo", db_index=True)
    
    # Metadata
    is_read = models.BooleanField(default=False, db_index=True, verbose_name="Đã đọc")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="Thời gian đọc")
    action_url = models.URLField(blank=True, verbose_name="URL hành động")
    
    # Optional Relations
    related_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    related_object_id = models.CharField(max_length=255, null=True, blank=True)
    related_object = GenericForeignKey('related_content_type', 'related_object_id')
    
    objects = NotificationManager()

    class Meta:
        verbose_name = "Thông báo"
        verbose_name_plural = "Thông báo"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
        ]

    def __str__(self): return f"{self.recipient.username}: {self.title[:50]}"

    def mark_as_read(self):
        """Đánh dấu đã đọc"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
            # Clear cache
            cache.delete(f"unread_count_{self.recipient_id}")

    @classmethod
    def get_unread_count(cls, user_id):
        """Lấy số thông báo chưa đọc của user (có cache)."""
        key_suffix = f"unread_count_{user_id}"
        
        def fetch_count():
            return cls.objects.filter(recipient_id=user_id, is_read=False).count()
            
        return cls.get_cached_custom_data(key_suffix, fetch_count, timeout=300)

# Helper Functions
def get_user_unread_count(user_id):
    """Lấy số thông báo chưa đọc (có cache)"""
    cache_key = f"unread_count_{user_id}"
    count = cache.get(cache_key)
    if count is None:
        count = UserNotification.objects.filter(recipient_id=user_id, is_read=False).count()
        cache.set(cache_key, count, 300)
    return count

from django.conf import settings
import logging

logger = logging.getLogger('notifications')

def create_notification(recipient, title, message, notification_type='info', action_url='', related_object=None, send_email=True, **kwargs):
    """Tạo thông báo trong ứng dụng và gửi email bất đồng bộ qua Celery"""
    try:
        notification = UserNotification.objects.create(
            recipient=recipient,
            title=title,
            message=message,
            notification_type=notification_type,
            action_url=action_url,
            related_object=related_object,   
        )
        
        # Clear cache số đếm thông báo chưa đọc
        cache.delete(f"unread_count_{recipient.id}")
        
        # Gửi email bất đồng bộ qua Celery nếu user có email
        if send_email and recipient.email:
            try:
                full_url = f"{settings.SITE_URL}{action_url}" if hasattr(settings, 'SITE_URL') and action_url else action_url
                email_body = f"{message}\n\nXem chi tiết: {full_url}" if full_url else message
                from notifications.tasks import send_async_email_task
                send_async_email_task.delay(
                    subject=title,
                    message=email_body,
                    recipient_list=[recipient.email]
                )
            except Exception as mail_err:
                logger.warning(f"Không thể kích hoạt Celery email task cho {recipient.email}: {mail_err}")
                
        return notification
    except Exception as e:
        logger.error(f"Lỗi khi tạo UserNotification cho user {getattr(recipient, 'id', 'N/A')}: {e}", exc_info=True)
        return None

# Management Commands Helper
def cleanup_old_notifications(days=30):
    """Dọn dẹp thông báo cũ"""
    cutoff_date = timezone.now() - timedelta(days=days)
    deleted_count = UserNotification.objects.filter(created_at__lt=cutoff_date, is_read=True).delete()[0]
    return deleted_count

# Signals
@receiver(post_save, sender='transactions.BorrowRecord')
def create_due_soon_notification(sender, instance, created, **kwargs):
    """Tạo thông báo khi sách sắp đến hạn (3 ngày trước)"""
    if not created and instance.due_date:
        days_until_due = (instance.due_date - timezone.now().date()).days
        if days_until_due == 3 and not instance.return_date:
            create_notification(
                recipient=instance.user,
                title="Sách sắp đến hạn trả",
                message=f"Cuốn sách '{instance.book.title}' của bạn sẽ đến hạn trả vào ngày {instance.due_date.strftime('%d/%m/%Y')}.",
                notification_type='due_soon',
                action_url=f"/transactions/borrows/{instance.id}/",
                related_object=instance
            )

@receiver(post_save, sender='transactions.BorrowRecord')  
def create_overdue_notification(sender, instance, created, **kwargs):
    """Thông báo sách quá hạn"""
    if not created and instance.is_overdue and not instance.return_date:
        days_overdue = (timezone.now().date() - instance.due_date).days
        create_notification(
            recipient=instance.user,
            title="Sách đã quá hạn",
            message=f"Cuốn sách '{instance.book.title}' của bạn đã quá hạn {days_overdue} ngày. Vui lòng trả sách sớm nhất có thể.",
            notification_type='overdue',
            action_url=f"/transactions/borrows/{instance.id}/",
            related_object=instance
        )

@receiver(post_save, sender='transactions.BookReservation')
def create_reservation_available_notification(sender, instance, created, **kwargs):
    """Thông báo khi sách đặt trước có sẵn"""
    if not created and instance.book.is_available and not instance.is_fulfilled:
        create_notification(
            recipient=instance.user,
            title="Sách đặt trước đã có sẵn",
            message=f"Cuốn sách '{instance.book.title}' mà bạn đặt trước hiện đã có sẵn. Bạn có thể đến mượn ngay.",
            notification_type='reserved_available',
            action_url=f"/transactions/reservations/{instance.id}/",
            related_object=instance
        )

@receiver(post_save, sender='analytics.UserReadingStats')
def create_achievement_notification(sender, instance, **kwargs):
    """Thông báo thành tích mới"""
    old_level = getattr(instance, '_old_member_level', None)
    if old_level and old_level != instance.member_level:
        create_notification(
            recipient=instance.user,
            title="Thăng cấp thành viên!",
            message=f"Chúc mừng! Hạng của bạn vừa được nâng từ {old_level} lên {instance.member_level}.",
            notification_type='achievement_unlocked',
            action_url="/profile/achievements/",
            related_object=instance
        )
