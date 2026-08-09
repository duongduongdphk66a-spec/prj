# File: transactions/tasks.py
from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.auth.models import User
from django.db.models import Q, F
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

@shared_task
def check_overdue_books():
    """Kiểm tra sách quá hạn và tính phạt"""
    from .models import BorrowRecord, FinePayment
    overdue_records = BorrowRecord.objects.filter(return_date__isnull=True, due_date__lt=timezone.now().date())
    count = 0
    for record in overdue_records:
        if record.fine_amount > 0 and not record.payments.filter(payment_status='completed').exists():
            FinePayment.objects.get_or_create(borrow_record=record, defaults={'amount': record.fine_amount})
            count += 1
    logger.info(f"Đã tạo {count} thanh toán phạt cho sách quá hạn")
    return count

@shared_task
def send_due_reminders():
    """Gửi nhắc nhở sách sắp hết hạn"""
    from .models import BorrowRecord
    tomorrow = timezone.now().date() + timedelta(days=1)
    due_records = BorrowRecord.objects.filter(return_date__isnull=True, due_date=tomorrow).select_related('user', 'book')
    
    for record in due_records:
        try:
            send_mail(
                subject=f'Nhắc nhở: Sách "{record.book.title}" sắp hết hạn',
                message=render_to_string('emails/due_reminder.txt', {'record': record}),
                from_email='library@system.com',
                recipient_list=[record.user.email],
                fail_silently=False
            )
        except Exception as e:
            logger.error(f"Lỗi gửi email cho {record.user.email}: {e}")
    
    return due_records.count()

@shared_task
def process_reservation_queue():
    """Xử lý hàng đợi đặt trước khi có sách available"""
    from .models import BookReservation
    from inventory.models import Book
    
    available_books = Book.objects.filter(status='available')
    count = 0
    
    for book in available_books:
        next_reservation = book.reservations.filter(is_fulfilled=False).order_by('queue_position').first()
        if next_reservation:
            next_reservation.fulfill()
            send_availability_notification.delay(next_reservation.id)
            count += 1
    
    return count

@shared_task
def send_availability_notification(reservation_id):
    """Gửi thông báo sách đã có sẵn"""
    from .models import BookReservation
    try:
        reservation = BookReservation.objects.get(id=reservation_id)
        send_mail(
            subject=f'Sách "{reservation.book.title}" đã có sẵn!',
            message=render_to_string('emails/book_available.txt', {'reservation': reservation}),
            from_email='library@system.com',
            recipient_list=[reservation.user.email],
            fail_silently=False
        )
        reservation.notification_sent = True
        reservation.save(update_fields=['notification_sent'])
    except BookReservation.DoesNotExist:
        logger.error(f"Reservation {reservation_id} không tồn tại")

@shared_task
def cleanup_expired_reservations():
    """Xóa các đặt trước hết hạn"""
    from .models import BookReservation
    expired_count = BookReservation.objects.filter(is_fulfilled=False, expires_date__lt=timezone.now().date()).delete()[0]
    logger.info(f"Đã xóa {expired_count} đặt trước hết hạn")
    return expired_count

@shared_task
def update_shipping_status():
    """Cập nhật trạng thái giao hàng từ API đối tác"""
    from .models import ShippingRequest
    pending_shipments = ShippingRequest.objects.filter(status='shipped', tracking_code__isnull=False)
    
    for shipping in pending_shipments:
        # Mock API call - thay thế bằng API thực tế
        if shipping.estimated_delivery and shipping.estimated_delivery <= timezone.now():
            shipping.status = 'delivered'
            shipping.actual_delivery = timezone.now()
            shipping.save(update_fields=['status', 'actual_delivery'])
    
    return pending_shipments.count()

@shared_task
def generate_monthly_report():
    """Tạo báo cáo thống kê hàng tháng"""
    from .models import BorrowRecord, FinePayment
    from django.db.models import Count, Sum
    
    current_month = timezone.now().replace(day=1)
    last_month = current_month - timedelta(days=1)
    
    stats = {
        'total_borrows': BorrowRecord.objects.filter(borrow_date__month=last_month.month).count(),
        'total_returns': BorrowRecord.objects.filter(return_date__month=last_month.month).count(),
        'overdue_books': BorrowRecord.objects.filter(return_date__isnull=True, due_date__lt=current_month.date()).count(),
        'fine_collected': FinePayment.objects.filter(payment_date__month=last_month.month, payment_status='completed').aggregate(total=Sum('final_amount'))['total'] or 0,
        'popular_books': BorrowRecord.objects.filter(borrow_date__month=last_month.month).values('book__title').annotate(count=Count('id')).order_by('-count')[:10]
    }
    
    logger.info(f"Báo cáo tháng {last_month.month}: {stats}")
    return stats

@shared_task
def bulk_renew_expiring_books():
    """Gia hạn tự động cho sách sắp hết hạn (nếu có thể)"""
    from .models import BorrowRecord
    tomorrow = timezone.now().date() + timedelta(days=1)
    expiring_records = BorrowRecord.objects.filter(return_date__isnull=True, due_date=tomorrow)
    
    renewed_count = 0
    for record in expiring_records:
        if record.can_renew:
            record.renew(days=7)  # Gia hạn 7 ngày
            renewed_count += 1
    
    return renewed_count

@shared_task
def sync_user_borrow_limits():
    """Đồng bộ giới hạn mượn sách theo role user"""
    from django.contrib.auth.models import User
    from .models import BorrowRecord
    
    updated_count = 0
    for user in User.objects.filter(is_active=True).select_related('profile'):
        active_count = BorrowRecord.objects.filter(user=user, return_date__isnull=True).count()
        # Cập nhật thông tin vào reading stats thay vì profile (profile không có field này)
        if hasattr(user, 'profile'):
            try:
                from analytics.models import UserReadingStats
                stats, _ = UserReadingStats.objects.get_or_create(
                    user=user,
                    defaults={
                        'total_books_borrowed': active_count,
                        'total_books_returned': 0,
                        'reputation_score': 100,
                        'member_level': 'bronze',
                        'created_by': user,
                        'modified_by': user
                    }
                )
                updated_count += 1
            except Exception as e:
                logger.error(f"Error syncing borrow limits for {user.username}: {e}")
    
    logger.info(f"Đã đồng bộ giới hạn mượn cho {updated_count} users")
    return updated_count

@shared_task
def archive_old_transactions():
    """Lưu trữ các giao dịch cũ"""
    from .models import BorrowRecord, FinePayment
    cutoff_date = timezone.now().date() - timedelta(days=365)
    
    # Soft delete các bản ghi cũ hơn 1 năm (SoftDeleteModel dùng deleted_at + is_active)
    old_records = BorrowRecord.objects.filter(return_date__lt=cutoff_date, return_date__isnull=False)
    archived_count = old_records.update(deleted_at=timezone.now(), is_active=False)
    
    logger.info(f"Đã lưu trữ {archived_count} giao dịch cũ")
    return archived_count