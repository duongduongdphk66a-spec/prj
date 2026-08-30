# notifications/tasks.py
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger('notifications')

@shared_task(name="notifications.tasks.send_async_email_task", max_retries=3, default_retry_delay=60)
def send_async_email_task(subject, message, recipient_list, from_email=None):
    """
    Gửi email bất đồng bộ qua Celery worker để không làm nghẽn request cycle và DB locks.
    """
    if not recipient_list:
        return 0

    sender = from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@librarybus.com')
    try:
        sent = send_mail(
            subject=subject,
            message=message,
            from_email=sender,
            recipient_list=recipient_list,
            fail_silently=False,
        )
        logger.info(f"Đã gửi email thành công tới {recipient_list} (subject: {subject[:30]}...)")
        return sent
    except Exception as e:
        logger.error(f"Lỗi khi gửi async email tới {recipient_list}: {e}", exc_info=True)
        # Không raise lại exception trong môi trường dev nếu chưa cấu hình SMTP
        return 0
