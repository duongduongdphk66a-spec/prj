# File: transactions/models.py
import datetime
from datetime import timedelta
from decimal import Decimal
from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.db.models import Q, F, Count, Sum, Avg
from django.utils.functional import cached_property
from django.core.cache import cache
from inventory.models import Book
from core.models import TimestampedModel, SoftDeleteModel

# --- SERVICE LAYER ---
# TransactionService đã được chuyển sang transactions/services.py
# Import khi cần: from transactions.services import TransactionService

class TransactionQuerySet(models.QuerySet):
    """Custom QuerySet cho các transaction"""
    def active_borrows(self): return self.filter(return_date__isnull=True, is_lost=False)
    def overdue(self): return self.filter(return_date__isnull=True, due_date__lt=timezone.now().date())
    def returned(self): return self.filter(return_date__isnull=False)
    def by_user(self, user): return self.filter(user=user)
    def by_book(self, book): return self.filter(book=book)
    def this_month(self): return self.filter(created_at__month=timezone.now().month, created_at__year=timezone.now().year)
    def popular_books(self): return self.values('book').annotate(borrow_count=Count('id')).order_by('-borrow_count')

class TransactionManager(models.Manager):
    def get_queryset(self): return TransactionQuerySet(self.model, using=self._db)
    def active_borrows(self): return self.get_queryset().active_borrows()
    def overdue(self): return self.get_queryset().overdue()
    def get_user_stats(self, user): return self.get_queryset().by_user(user).aggregate(total=Count('id'), returned=Count('return_date'))

class BorrowRecord(SoftDeleteModel): # CẬP NHẬT: Kế thừa từ SoftDeleteModel
    """Lịch sử mượn sách"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='borrow_records')
    book = models.ForeignKey('inventory.Book', on_delete=models.CASCADE, related_name='borrow_records')
    borrow_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)
    # Status fields
    renewal_count = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0)])
    is_lost = models.BooleanField(default=False, db_index=True)
    is_damaged = models.BooleanField(default=False, verbose_name="Sách bị hỏng")
    
    # Enhanced tracking
    pickup_location = models.ForeignKey('inventory.LibraryBus', on_delete=models.SET_NULL, null=True, blank=True, related_name='pickup_records', verbose_name="Nơi lấy sách")
    return_location = models.ForeignKey('inventory.LibraryBus', on_delete=models.SET_NULL, null=True, blank=True, related_name='return_records', verbose_name="Nơi trả sách")
    
    # Metadata
    notes = models.TextField(blank=True, verbose_name="Ghi chú")
    staff_processed = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_borrows', verbose_name="Nhân viên xử lý")
    
    objects = TransactionManager()
    
    class Meta:
        ordering = ['-borrow_date']
        verbose_name = "Lịch sử Mượn sách"
        verbose_name_plural = "Lịch sử Mượn sách"
        constraints = [models.UniqueConstraint(fields=['user', 'book'], condition=Q(return_date__isnull=True), name='unique_active_borrow')]
        indexes = [models.Index(fields=['user', 'return_date']), models.Index(fields=['book', 'borrow_date']), models.Index(fields=['due_date', 'return_date'])]

    def __str__(self): return f"{self.user.username} - {self.book.title} ({self.borrow_date})"

    @cached_property
    def is_overdue(self): return not self.return_date and self.due_date < timezone.now().date()
    
    @cached_property
    def days_overdue(self): return max(0, (timezone.now().date() - self.due_date).days) if self.is_overdue else 0
    
    @cached_property
    def fine_amount(self): 
        from transactions.services import TransactionService
        return TransactionService.calculate_fine(self)
    
    @cached_property
    def can_renew(self): return self.renewal_count < 2 and not self.is_overdue and not self.book.reservations.filter(is_fulfilled=False).exists()
    
    def clean(self):
        """Thêm validation phức tạp"""
        if self.due_date and self.due_date < timezone.now().date():
            raise ValidationError({'due_date': "Ngày hết hạn không thể trong quá khứ."})
        
        if self.return_date and self.borrow_date and self.return_date < self.borrow_date:
            raise ValidationError({'return_date': "Ngày trả không thể trước ngày mượn."})

    def return_book(self, condition_notes="", returned_by=None):
        """Đơn giản hóa method, gọi service"""
        return TransactionService.return_borrow(self.id, condition_notes, returned_by)
    
    def renew(self, days=14):
        """Gia hạn sách với validation"""
        if not self.can_renew: raise ValidationError("Không thể gia hạn sách này")
        with transaction.atomic():
            self.due_date += datetime.timedelta(days=days)
            self.renewal_count = F('renewal_count') + 1
            self.save(update_fields=['due_date', 'renewal_count'])
            # Invalidate cache
            cache.delete(f'borrow_record_{self.id}')


class ReservationQuerySet(models.QuerySet):
    """Custom QuerySet cho reservations"""
    def active(self): return self.filter(is_fulfilled=False, expires_date__gte=timezone.now().date())
    def expired(self): return self.filter(is_fulfilled=False, expires_date__lt=timezone.now().date())
    def by_priority(self): return self.order_by('queue_position', 'created_at')

class BookReservation(TimestampedModel):
    """Đặt trước sách với queue management"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reservations', db_index=True)
    book = models.ForeignKey('inventory.Book', on_delete=models.CASCADE, related_name='reservations', db_index=True)
    expires_date = models.DateField(db_index=True)
    is_fulfilled = models.BooleanField(default=False, db_index=True)
    fulfilled_date = models.DateTimeField(null=True, blank=True)
    queue_position = models.PositiveIntegerField(default=1)
    notification_sent = models.BooleanField(default=False, db_index=True)
    preferred_pickup_location = models.ForeignKey('inventory.LibraryBus', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Nơi nhận ưu tiên")
    
    objects = models.Manager.from_queryset(ReservationQuerySet)()

    class Meta:
        ordering = ['queue_position', 'created_at']
        verbose_name = "Đặt trước sách"
        verbose_name_plural = "Đặt trước sách"
        constraints = [models.UniqueConstraint(fields=['user', 'book'], condition=Q(is_fulfilled=False), name='unique_active_reservation')]
        indexes = [models.Index(fields=['book', 'is_fulfilled', 'queue_position']), models.Index(fields=['user', 'is_fulfilled'])]

    def __str__(self): return f"{self.user.username} - {self.book.title} (#{self.queue_position})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        if is_new and not self.expires_date: self.expires_date = timezone.now().date() + datetime.timedelta(days=7)
        if is_new: self.queue_position = (self.book.reservations.filter(is_fulfilled=False).aggregate(max_pos=models.Max('queue_position'))['max_pos'] or 0) + 1
        super().save(*args, **kwargs)

    def fulfill(self):
        """Thực hiện đặt trước - sách đã có sẵn"""
        with transaction.atomic():
            self.is_fulfilled = True
            self.fulfilled_date = timezone.now()
            self.save(update_fields=['is_fulfilled', 'fulfilled_date'])
            # Reorder queue positions
            self.book.reservations.filter(is_fulfilled=False, queue_position__gt=self.queue_position).update(queue_position=F('queue_position') - 1)

class ShippingRequest(SoftDeleteModel):
    """Yêu cầu giao sách với tracking nâng cao"""
    SHIPPING_STATUS = [('pending', 'Đang chờ xử lý'), ('processing', 'Đang chuẩn bị'), ('shipped', 'Đang giao'), ('delivered', 'Đã giao'), ('failed', 'Giao thất bại'), ('cancelled', 'Đã hủy')]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shipping_requests', db_index=True)
    book = models.ForeignKey('inventory.Book', on_delete=models.CASCADE, related_name='shipping_requests')
    borrow_record = models.OneToOneField(BorrowRecord, on_delete=models.CASCADE, related_name='shipping_request', null=True, blank=True)
    
    # Shipping details
    shipping_address = models.TextField(verbose_name="Địa chỉ giao hàng")
    phone_number = models.CharField(max_length=15, validators=[RegexValidator(regex=r'^(\+84|0)[0-9]{9,10}$')])
    recipient_name = models.CharField(max_length=100, verbose_name="Tên người nhận")
    
    # Status tracking
    status = models.CharField(max_length=20, choices=SHIPPING_STATUS, default='pending', db_index=True)
    tracking_code = models.CharField(max_length=50, blank=True, unique=True, db_index=True)
    shipping_partner = models.CharField(max_length=50, blank=True, choices=[('ghn', 'Giao Hàng Nhanh'), ('viettel', 'Viettel Post'), ('vnpost', 'VN Post')], verbose_name="Đối tác giao hàng")
    
    # Costs and timing
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'), validators=[MinValueValidator(0)])
    estimated_delivery = models.DateTimeField(null=True, blank=True, verbose_name="Dự kiến giao hàng")
    actual_delivery = models.DateTimeField(null=True, blank=True, verbose_name="Thời gian giao thực tế")
    
    # Notes
    delivery_notes = models.TextField(blank=True, verbose_name="Ghi chú giao hàng")
    internal_notes = models.TextField(blank=True, verbose_name="Ghi chú nội bộ")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Yêu cầu giao sách"
        verbose_name_plural = "Các yêu cầu giao sách"
        indexes = [models.Index(fields=['status', 'created_at']), models.Index(fields=['user', 'status'])]

    def __str__(self): return f"Giao {self.book.title} cho {self.user.username}"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status = self.status

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if not is_new and self._original_status == 'pending' and self.status in ['processing', 'shipped', 'delivered']:
            from transactions.services import NotificationService
            NotificationService.notify_user_shipping_approved(self)
            
        self._original_status = self.status

    @cached_property
    def is_deliverable(self): return self.status in ['pending', 'processing']
    
    def generate_tracking_code(self):
        """Tạo mã tracking unique"""
        if not self.tracking_code:
            import uuid
            self.tracking_code = f"LB{timezone.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
            self.save(update_fields=['tracking_code'])

    def mark_as_shipped(self, partner=None, estimated_delivery=None):
        """Đánh dấu đã gửi hàng"""
        with transaction.atomic():
            self.status = 'shipped'
            if partner: self.shipping_partner = partner
            if estimated_delivery: self.estimated_delivery = estimated_delivery
            if not self.tracking_code: self.generate_tracking_code()
            self.save(update_fields=['status', 'shipping_partner', 'estimated_delivery', 'tracking_code'])

class FinePayment(TimestampedModel):
    """Thanh toán phí phạt với audit trail"""
    PAYMENT_METHODS = [('cash', 'Tiền mặt'), ('transfer', 'Chuyển khoản'), ('momo', 'MoMo'), ('zalopay', 'ZaloPay'), ('credit_card', 'Thẻ tín dụng')]
    PAYMENT_STATUS = [('pending', 'Đang chờ'), ('processing', 'Đang xử lý'), ('completed', 'Hoàn thành'), ('failed', 'Thất bại'), ('refunded', 'Đã hoàn')]
    
    borrow_record = models.ForeignKey(BorrowRecord, on_delete=models.CASCADE, related_name='payments', db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'), validators=[MinValueValidator(0)])
    final_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='completed', db_index=True)
    
    # Transaction details
    transaction_id = models.CharField(max_length=100, blank=True, db_index=True)
    gateway_reference = models.CharField(max_length=100, blank=True, verbose_name="Mã tham chiếu gateway")
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_payments', verbose_name="Nhân viên xử lý")
    
    # Metadata
    payment_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, verbose_name="Ghi chú thanh toán")

    class Meta:
        ordering = ['-payment_date']
        verbose_name = "Thanh toán phạt"
        verbose_name_plural = "Thanh toán phạt"
        indexes = [models.Index(fields=['payment_status', 'payment_date']), models.Index(fields=['borrow_record', 'payment_status'])]

    def __str__(self): return f"Phạt {self.final_amount}đ - {self.borrow_record}"

    def save(self, *args, **kwargs):
        # Auto-calculate final amount
        self.final_amount = self.amount - self.discount_amount
        super().save(*args, **kwargs)

    def apply_discount(self, discount_percent):
        """Áp dụng giảm giá"""
        if 0 <= discount_percent <= 100:
            self.discount_amount = self.amount * Decimal(discount_percent) / 100
            self.save(update_fields=['discount_amount', 'final_amount'])

class BulkTransaction(TimestampedModel):
    """Giao dịch hàng loạt cho thao tác admin"""
    TRANSACTION_TYPES = [('bulk_return', 'Trả hàng loạt'), ('bulk_renew', 'Gia hạn hàng loạt'), ('bulk_fine', 'Tính phạt hàng loạt')]
    
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, db_index=True)
    processed_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bulk_transactions')
    records_processed = models.PositiveIntegerField(default=0)
    records_failed = models.PositiveIntegerField(default=0)
    processing_log = models.JSONField(default=dict, blank=True)
    is_completed = models.BooleanField(default=False, db_index=True)
    
    class Meta:
        verbose_name = "Giao dịch hàng loạt"
        verbose_name_plural = "Giao dịch hàng loạt"