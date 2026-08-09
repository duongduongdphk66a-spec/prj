# File: blog/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import BookReview
from analytics.tasks import update_book_analytics_task

@receiver(post_save, sender=BookReview)
def trigger_update_book_analytics_on_review(sender, instance, created, **kwargs):
    """
    Khi có review mới, kích hoạt task nền để cập nhật analytics.
    """
    if created:
        # Gọi task để chạy ở background
        update_book_analytics_task.delay(instance.book.id)