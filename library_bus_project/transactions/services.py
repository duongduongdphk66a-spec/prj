# File: transactions/services.py
from datetime import timedelta, datetime
from decimal import Decimal
from typing import Optional, Dict, List, Any
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.db.models import Q, F, Count, Sum, Max, Avg 
from django.core.cache import cache
from inventory.models import Book, LibraryBus
from notifications.models import UserNotification
from .models import BorrowRecord, BookReservation, ShippingRequest, FinePayment, BulkTransaction
import logging

logger = logging.getLogger(__name__)

class TransactionService:
    """Unified service for all transaction-related operations"""
    
    # --- BORROW OPERATIONS ---
    @staticmethod
    def create_borrow(user: User, book: Book, due_days: int = 14, pickup_location: Optional[LibraryBus] = None, staff_member: Optional[User] = None) -> BorrowRecord:
        """Tạo mượn sách với validation đầy đủ"""
        with transaction.atomic():
            book = Book.objects.select_for_update().get(pk=book.pk)
            if not book.is_available:
                raise ValidationError(f"Sách '{book.title}' không khả dụng để mượn")
            
            # Check user borrow limit
            active_count = BorrowRecord.objects.filter(user=user, return_date__isnull=True).count()
            if hasattr(user, 'profile') and active_count >= getattr(user.profile, 'borrow_limit', 5):
                raise ValidationError(f"Người dùng đã đạt giới hạn mượn sách ({active_count} cuốn)")
            
            borrow = BorrowRecord.objects.create(user=user, book=book, due_date=timezone.now().date() + timedelta(days=due_days), pickup_location=pickup_location, staff_processed=staff_member)
            book.change_status('checked_out', user=staff_member or user)
            
            # Clear cache
            cache.delete(f'user_active_borrows_{user.id}')
            cache.delete(f'book_status_{book.id}')
            
            logger.info(f"Tạo mượn sách thành công: {user.username} - {book.title}")
            return borrow

    @staticmethod
    def return_book(borrow_record_id: int, condition_notes: str = "", returned_by: Optional[User] = None, return_location: Optional[LibraryBus] = None) -> BorrowRecord:
        """Trả sách với validation và xử lý phạt"""
        with transaction.atomic():
            borrow = BorrowRecord.objects.select_for_update().get(pk=borrow_record_id)
            if borrow.return_date:
                raise ValidationError("Sách đã được trả trước đó")
            
            borrow.return_date = timezone.now().date()
            borrow.return_location = return_location
            if condition_notes:
                borrow.notes = f"{borrow.notes}\nTrả sách: {condition_notes}".strip()
            borrow.save(update_fields=['return_date', 'return_location', 'notes'])
            
            # Update book status
            borrow.book.change_status('available', user=returned_by)
            
            # Create fine payment if overdue
            if borrow.is_overdue and borrow.fine_amount > 0:
                FinePayment.objects.get_or_create(borrow_record=borrow, defaults={'amount': borrow.fine_amount, 'processed_by': returned_by})
            
            # Clear cache
            cache.delete(f'user_active_borrows_{borrow.user.id}')
            cache.delete(f'book_status_{borrow.book.id}')
            
            logger.info(f"Trả sách thành công: {borrow.user.username} - {borrow.book.title}")
            return borrow

    @staticmethod
    def renew_book(borrow_record_id: int, days: int = 14) -> BorrowRecord:
        """Gia hạn sách với validation"""
        with transaction.atomic():
            borrow = BorrowRecord.objects.select_for_update().get(pk=borrow_record_id)
            if not borrow.can_renew:
                raise ValidationError("Không thể gia hạn sách này")
            
            borrow.due_date += timedelta(days=days)
            borrow.renewal_count = F('renewal_count') + 1
            borrow.save(update_fields=['due_date', 'renewal_count'])
            
            cache.delete(f'borrow_record_{borrow.id}')
            logger.info(f"Gia hạn sách thành công: {borrow.user.username} - {borrow.book.title}")
            return borrow

    # --- RESERVATION OPERATIONS ---
    @staticmethod
    def create_reservation(user: User, book: Book, preferred_location: Optional[LibraryBus] = None) -> BookReservation:
        """Tạo đặt trước sách"""
        if book.is_available:
            raise ValidationError("Sách đang có sẵn, không cần đặt trước")
        
        existing = BookReservation.objects.filter(user=user, book=book, is_fulfilled=False).first()
        if existing:
            raise ValidationError("Bạn đã đặt trước sách này rồi")
        
        reservation = BookReservation.objects.create(user=user, book=book, preferred_pickup_location=preferred_location)
        logger.info(f"Tạo đặt trước: {user.username} - {book.title} (vị trí #{reservation.queue_position})")
        return reservation

    @staticmethod
    def cancel_reservation(reservation_id: int) -> bool:
        """Hủy đặt trước và sắp xếp lại queue"""
        with transaction.atomic():
            reservation = BookReservation.objects.get(id=reservation_id)
            if reservation.is_fulfilled:
                raise ValidationError("Không thể hủy đặt trước đã hoàn thành")
            
            queue_position = reservation.queue_position
            book = reservation.book
            reservation.delete()
            
            # Reorder queue
            book.reservations.filter(is_fulfilled=False, queue_position__gt=queue_position).update(queue_position=F('queue_position') - 1)
            
            logger.info(f"Hủy đặt trước: {reservation.user.username} - {book.title}")
            return True

    @staticmethod
    def fulfill_next_reservation(book: Book) -> Optional[BookReservation]:
        """Hoàn thành đặt trước tiếp theo khi sách có sẵn"""
        next_reservation = book.reservations.filter(is_fulfilled=False).order_by('queue_position').first()
        if next_reservation:
            next_reservation.fulfill()
            NotificationService.send_book_available_notification(next_reservation)
            return next_reservation
        return None

    # --- SHIPPING OPERATIONS ---
    @staticmethod
    def create_shipping_request(user: User, book: Book, shipping_address: str, phone_number: str, recipient_name: str) -> ShippingRequest:
        """Tạo yêu cầu giao sách"""
        import uuid
        tracking_code = f"LB{timezone.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
        shipping = ShippingRequest.objects.create(user=user, book=book, shipping_address=shipping_address, phone_number=phone_number, recipient_name=recipient_name, tracking_code=tracking_code)
        
        # Create associated borrow record
        borrow = TransactionService.create_borrow(user, book, due_days=21)  # Longer due date for shipping
        shipping.borrow_record = borrow
        shipping.save(update_fields=['borrow_record'])
        
        logger.info(f"Tạo yêu cầu giao sách: {user.username} - {book.title}")
        return shipping

    @staticmethod
    def process_shipping(shipping_id: int, partner: str, estimated_delivery: Optional[datetime] = None) -> ShippingRequest:
        """Xử lý giao hàng"""
        with transaction.atomic():
            shipping = ShippingRequest.objects.get(id=shipping_id)
            if not shipping.is_deliverable:
                raise ValidationError("Yêu cầu giao hàng không thể xử lý")
            
            shipping.mark_as_shipped(partner=partner, estimated_delivery=estimated_delivery)
            logger.info(f"Xử lý giao hàng: {shipping.tracking_code}")
            return shipping

    # --- FINE OPERATIONS ---
    @staticmethod
    def calculate_fine(borrow_record: BorrowRecord) -> Decimal:
        """Tính phạt cho sách quá hạn"""
        if not borrow_record.is_overdue:
            return Decimal('0')
        
        base_fine = Decimal('5000')  # 5k per day
        days_overdue = borrow_record.days_overdue
        
        # Progressive fine calculation
        if days_overdue <= 7:
            return base_fine * days_overdue
        elif days_overdue <= 30:
            return base_fine * 7 + Decimal('10000') * (days_overdue - 7)
        else:
            return base_fine * 7 + Decimal('10000') * 23 + Decimal('15000') * (days_overdue - 30)

    @staticmethod
    def create_fine_payment(borrow_record: BorrowRecord, amount: Optional[Decimal] = None, payment_method: str = 'cash', processed_by: Optional[User] = None) -> FinePayment:
        """Tạo thanh toán phạt"""
        fine_amount = amount or TransactionService.calculate_fine(borrow_record)
        if fine_amount <= 0:
            raise ValidationError("Không có phạt để thanh toán")
        
        payment = FinePayment.objects.create(borrow_record=borrow_record, amount=fine_amount, payment_method=payment_method, processed_by=processed_by)
        logger.info(f"Tạo thanh toán phạt: {payment.final_amount}đ - {borrow_record}")
        return payment

    @staticmethod
    def apply_fine_discount(payment_id: int, discount_percent: float, reason: str = "") -> FinePayment:
        """Áp dụng giảm giá phạt"""
        if not 0 <= discount_percent <= 100:
            raise ValidationError("Tỷ lệ giảm giá phải từ 0-100%")
        
        payment = FinePayment.objects.get(id=payment_id)
        payment.apply_discount(discount_percent)
        if reason:
            payment.notes = f"{payment.notes}\nGiảm giá {discount_percent}%: {reason}".strip()
            payment.save(update_fields=['notes'])
        
        logger.info(f"Áp dụng giảm giá {discount_percent}% cho thanh toán {payment.id}")
        return payment

    # --- BULK OPERATIONS ---
    @staticmethod
    def bulk_return_books(borrow_record_ids: List[int], processed_by: User, condition_notes: str = "") -> Dict[str, Any]:
        """Trả hàng loạt sách"""
        bulk_transaction = BulkTransaction.objects.create(transaction_type='bulk_return', processed_by=processed_by)
        
        success_count = 0
        failed_count = 0
        errors = []
        
        for record_id in borrow_record_ids:
            try:
                TransactionService.return_book(record_id, condition_notes, processed_by)
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f"Record {record_id}: {str(e)}")
        
        bulk_transaction.records_processed = success_count
        bulk_transaction.records_failed = failed_count
        bulk_transaction.processing_log = {'errors': errors}
        bulk_transaction.is_completed = True
        bulk_transaction.save()
        
        logger.info(f"Trả hàng loạt: {success_count} thành công, {failed_count} thất bại")
        return {'success': success_count, 'failed': failed_count, 'errors': errors}

    @staticmethod
    def bulk_renew_books(borrow_record_ids: List[int], days: int = 14, processed_by: Optional[User] = None) -> Dict[str, Any]:
        """Gia hạn hàng loạt sách"""
        bulk_transaction = BulkTransaction.objects.create(transaction_type='bulk_renew', processed_by=processed_by)
        
        success_count = 0
        failed_count = 0
        errors = []
        
        for record_id in borrow_record_ids:
            try:
                TransactionService.renew_book(record_id, days)
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f"Record {record_id}: {str(e)}")
        
        bulk_transaction.records_processed = success_count
        bulk_transaction.records_failed = failed_count
        bulk_transaction.processing_log = {'errors': errors}
        bulk_transaction.is_completed = True
        bulk_transaction.save()
        
        logger.info(f"Gia hạn hàng loạt: {success_count} thành công, {failed_count} thất bại")
        return {'success': success_count, 'failed': failed_count, 'errors': errors}


class NotificationService:
    """Service for handling notifications"""
    
    @staticmethod
    def send_due_reminder(borrow_record: BorrowRecord) -> bool:
        """Gửi nhắc nhở sách sắp hết hạn"""
        try:
            send_mail(subject=f'Nhắc nhở: Sách "{borrow_record.book.title}" sắp hết hạn', message=render_to_string('emails/due_reminder.txt', {'record': borrow_record}), from_email='library@system.com', recipient_list=[borrow_record.user.email], fail_silently=False)
            logger.info(f"Gửi nhắc nhở thành công: {borrow_record.user.email}")
            return True
        except Exception as e:
            logger.error(f"Lỗi gửi nhắc nhở: {e}")
            return False

    @staticmethod
    def send_overdue_notification(borrow_record: BorrowRecord) -> bool:
        """Gửi thông báo sách quá hạn"""
        try:
            send_mail(subject=f'Thông báo: Sách "{borrow_record.book.title}" đã quá hạn', message=render_to_string('emails/overdue_notification.txt', {'record': borrow_record}), from_email='library@system.com', recipient_list=[borrow_record.user.email], fail_silently=False)
            return True
        except Exception as e:
            logger.error(f"Lỗi gửi thông báo quá hạn: {e}")
            return False

    @staticmethod
    def send_book_available_notification(reservation: BookReservation) -> bool:
        """Gửi thông báo sách đã có sẵn"""
        try:
            send_mail(subject=f'Thông báo: Sách "{reservation.book.title}" đã có sẵn!', message=render_to_string('emails/book_available.txt', {'reservation': reservation}), from_email='library@system.com', recipient_list=[reservation.user.email], fail_silently=False)
            reservation.notification_sent = True
            reservation.save(update_fields=['notification_sent'])
            return True
        except Exception as e:
            logger.error(f"Lỗi gửi thông báo sách có sẵn: {e}")
            return False


    @staticmethod
    def notify_user_shipping_approved(shipping_request) -> bool:
        """Gửi thông báo cho người dùng khi yêu cầu giao sách được phê duyệt"""
        try:
            title = f'Yêu cầu giao sách đã được duyệt'
            message = f'Yêu cầu giao sách "{shipping_request.book.title}" của bạn đã được duyệt và đang được xử lý.'
            
            UserNotification.objects.create(
                recipient=shipping_request.user,
                title=title,
                message=message,
                notification_type='success',
                action_url='/users/profile/'
            )
            logger.info(f"Đã gửi thông báo phê duyệt giao sách cho user {shipping_request.user.username}")
            return True
        except Exception as e:
            logger.error(f"Lỗi gửi thông báo phê duyệt giao sách: {e}")
            return False

    @staticmethod
    def notify_admin_new_shipping_request(shipping_request) -> bool:
        """Gửi thông báo yêu cầu giao sách mới cho admin (qua web)"""
        try:
            admins = User.objects.filter(is_staff=True, is_active=True)
            if not admins.exists():
                return False
                
            title = f'Yêu cầu giao sách mới: {shipping_request.book.title}'
            message = f"""Người yêu cầu: {shipping_request.user.username}
Người nhận: {shipping_request.recipient_name}
SĐT: {shipping_request.phone_number}
Địa chỉ: {shipping_request.shipping_address}
Ghi chú: {shipping_request.delivery_notes}"""

            for admin in admins:
                UserNotification.objects.create(
                    recipient=admin,
                    title=title,
                    message=message,
                    notification_type='warning',
                    action_url=f'/admin/transactions/shippingrequest/{shipping_request.id}/change/'
                )
            
            logger.info(f"Đã gửi thông báo web cho admin về yêu cầu giao sách {shipping_request.id}")
            return True
        except Exception as e:
            logger.error(f"Lỗi gửi thông báo web cho admin: {e}")
            return False
                
            subject = f'Yêu cầu giao sách mới: {shipping_request.book.title}'
            message = f'''Xin chào Admin,

Có một yêu cầu giao sách mới trên hệ thống:
- Người yêu cầu: {shipping_request.user.username}
- Sách: {shipping_request.book.title}
- Ngày yêu cầu: {shipping_request.created_at.strftime("%d/%m/%Y %H:%M") if hasattr(shipping_request, "created_at") else ""}

Thông tin giao hàng:
- Người nhận: {shipping_request.recipient_name}
- SĐT: {shipping_request.phone_number}
- Địa chỉ: {shipping_request.shipping_address}
- Ghi chú: {shipping_request.delivery_notes}

Vui lòng đăng nhập hệ thống để duyệt yêu cầu này.
'''
            send_mail(subject=subject, message=message, from_email='library@system.com', recipient_list=admin_emails, fail_silently=False)
            return True
        except Exception as e:
            logger.error(f"Lỗi gửi thông báo cho admin: {e}")
            return False

    @staticmethod
    def send_shipping_update(shipping_request: ShippingRequest) -> bool:
        """Gửi cập nhật trạng thái giao hàng"""
        try:
            send_mail(subject=f'Cập nhật giao hàng: {shipping_request.tracking_code}', message=render_to_string('emails/shipping_update.txt', {'shipping': shipping_request}), from_email='library@system.com', recipient_list=[shipping_request.user.email], fail_silently=False)
            return True
        except Exception as e:
            logger.error(f"Lỗi gửi cập nhật giao hàng: {e}")
            return False


class ReportService:
    """Service for generating reports and statistics"""
    
    @staticmethod
    def get_user_statistics(user: User) -> Dict[str, Any]:
        """Thống kê người dùng"""
        active_borrows = BorrowRecord.objects.filter(user=user, return_date__isnull=True)
        all_borrows = BorrowRecord.objects.filter(user=user)
        
        return {'user': user.username, 'active_borrows': active_borrows.count(), 'total_borrows': all_borrows.count(), 'overdue_count': active_borrows.filter(due_date__lt=timezone.now().date()).count(), 'total_fines': FinePayment.objects.filter(borrow_record__user=user, payment_status='completed').aggregate(total=Sum('final_amount'))['total'] or 0, 'reservation_count': BookReservation.objects.filter(user=user, is_fulfilled=False).count()}

    @staticmethod
    def get_book_statistics(book: Book) -> Dict[str, Any]:
        """Thống kê sách"""
        all_borrows = BorrowRecord.objects.filter(book=book)
        
        return {'book': book.title, 'total_borrows': all_borrows.count(), 'current_borrower': all_borrows.filter(return_date__isnull=True).first(), 'reservation_queue': BookReservation.objects.filter(book=book, is_fulfilled=False).count(), 'average_borrow_days': all_borrows.filter(return_date__isnull=False).aggregate(avg_days=Avg(F('return_date') - F('borrow_date')))['avg_days'] or 0}

    @staticmethod
    def get_monthly_report(year: int, month: int) -> Dict[str, Any]:
        """Báo cáo tháng"""
        start_date = datetime(year, month, 1).date()
        end_date = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        
        borrows = BorrowRecord.objects.filter(borrow_date__range=[start_date, end_date])
        returns = BorrowRecord.objects.filter(return_date__range=[start_date, end_date])
        fines = FinePayment.objects.filter(payment_date__range=[start_date, end_date], payment_status='completed')
        
        return {'period': f"{month:02d}/{year}", 'total_borrows': borrows.count(), 'total_returns': returns.count(), 'overdue_books': BorrowRecord.objects.filter(return_date__isnull=True, due_date__lt=end_date).count(), 'fine_collected': fines.aggregate(total=Sum('final_amount'))['total'] or 0, 'popular_books': borrows.values('book__title').annotate(count=Count('id')).order_by('-count')[:10], 'active_users': borrows.values('user__username').distinct().count()}

    @staticmethod
    def get_overdue_report() -> Dict[str, Any]:
        """Báo cáo sách quá hạn"""
        overdue_records = BorrowRecord.objects.filter(return_date__isnull=True, due_date__lt=timezone.now().date()).select_related('user', 'book')
        
        return {'total_overdue': overdue_records.count(), 'total_fine_amount': sum(record.fine_amount for record in overdue_records), 'overdue_by_days': {'1_7_days': overdue_records.filter(due_date__gte=timezone.now().date() - timedelta(days=7)).count(), '8_30_days': overdue_records.filter(due_date__range=[timezone.now().date() - timedelta(days=30), timezone.now().date() - timedelta(days=8)]).count(), 'over_30_days': overdue_records.filter(due_date__lt=timezone.now().date() - timedelta(days=30)).count()}, 'top_offenders': overdue_records.values('user__username').annotate(count=Count('id')).order_by('-count')[:10]}


class AnalyticsService:
    """Service for advanced analytics and insights"""
    
    @staticmethod
    def get_borrowing_trends(days: int = 30) -> Dict[str, Any]:
        """Xu hướng mượn sách"""
        start_date = timezone.now().date() - timedelta(days=days)
        daily_borrows = BorrowRecord.objects.filter(borrow_date__gte=start_date).extra(select={'day': 'date(borrow_date)'}).values('day').annotate(count=Count('id')).order_by('day')
        
        return {'period_days': days, 'daily_borrows': list(daily_borrows), 'peak_day': max(daily_borrows, key=lambda x: x['count']) if daily_borrows else None, 'average_per_day': sum(item['count'] for item in daily_borrows) / len(daily_borrows) if daily_borrows else 0}

    @staticmethod
    def get_popular_books(limit: int = 20) -> List[Dict[str, Any]]:
        """Sách phổ biến nhất"""
        popular = BorrowRecord.objects.values('book__title', 'book__author').annotate(borrow_count=Count('id'), unique_borrowers=Count('user', distinct=True)).order_by('-borrow_count')[:limit]
        
        return [{'title': item['book__title'], 'author': item['book__author'], 'borrow_count': item['borrow_count'], 'unique_borrowers': item['unique_borrowers']} for item in popular]

    @staticmethod
    def get_user_behavior_insights() -> Dict[str, Any]:
        """Phân tích hành vi người dùng"""
        total_users = User.objects.filter(is_active=True).count()
        active_borrowers = BorrowRecord.objects.filter(return_date__isnull=True).values('user').distinct().count()
        
        return {'total_active_users': total_users, 'active_borrowers': active_borrowers, 'borrowing_rate': round((active_borrowers / total_users) * 100, 2) if total_users > 0 else 0, 'average_books_per_user': round(BorrowRecord.objects.filter(return_date__isnull=True).count() / active_borrowers, 2) if active_borrowers > 0 else 0, 'renewal_rate': round((BorrowRecord.objects.filter(renewal_count__gt=0).count() / BorrowRecord.objects.count()) * 100, 2) if BorrowRecord.objects.count() > 0 else 0}

    @staticmethod 
    def predict_return_date(borrow_record: BorrowRecord) -> datetime:
        """Dự đoán ngày trả sách dựa trên lịch sử"""
        # Simple prediction based on user's historical behavior
        user_history = BorrowRecord.objects.filter(user=borrow_record.user, return_date__isnull=False)
        if user_history.exists():
            avg_days = user_history.aggregate(avg=Avg(F('return_date') - F('borrow_date')))['avg']
            if avg_days:
                return borrow_record.borrow_date + avg_days
        
        # Default to due date if no history
        return datetime.combine(borrow_record.due_date, datetime.min.time())