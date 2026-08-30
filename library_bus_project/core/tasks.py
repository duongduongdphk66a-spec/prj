# core/tasks.py
from celery import shared_task
from django.utils import timezone
from django.contrib.sessions.models import Session
from django.core.cache import cache
import logging

logger = logging.getLogger('core')

@shared_task(name="core.tasks.daily_maintenance")
def daily_maintenance():
    """
    Tác vụ bảo trì hệ thống định kỳ nửa đêm (00:00 hàng ngày):
    1. Dọn dẹp session đã hết hạn trong cơ sở dữ liệu.
    2. Kiểm tra tính toàn vẹn của cache.
    3. Ghi nhận log sức khỏe hệ thống.
    """
    logger.info("=== Bắt đầu tác vụ bảo trì định kỳ hàng ngày (daily_maintenance) ===")
    
    # 1. Dọn dẹp session hết hạn
    try:
        now = timezone.now()
        deleted_sessions, _ = Session.objects.filter(expire_date__lt=now).delete()
        logger.info(f"Đã dọn dẹp {deleted_sessions} session hết hạn.")
    except Exception as e:
        logger.error(f"Lỗi khi dọn dẹp expired sessions: {e}")
        deleted_sessions = 0

    # 2. Kiểm tra trạng thái Redis cache
    try:
        test_key = "healthcheck:daily_maintenance"
        cache.set(test_key, "ok", timeout=60)
        cache_status = cache.get(test_key) == "ok"
        logger.info(f"Trạng thái Cache Backend: {'Bình thường' if cache_status else 'Cảnh báo'}")
    except Exception as e:
        logger.error(f"Lỗi khi kiểm tra cache backend: {e}")
        cache_status = False

    logger.info("=== Hoàn tất tác vụ bảo trì định kỳ hàng ngày ===")
    return {
        "status": "success",
        "deleted_sessions": deleted_sessions,
        "cache_healthy": cache_status,
        "timestamp": timezone.now().isoformat()
    }
