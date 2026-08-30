# File: inventory/models.py 
from django.db import models, transaction
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db.models import F, Count, Avg, Q, Prefetch
from django.core.cache import cache
from django.conf import settings
from core.models import TimestampedModel, SoftDeleteModel, CacheMixin, BaseQuerySet
from analytics.models import BookAnalytics
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class LibraryBusQuerySet(BaseQuerySet):
    """Custom QuerySet cho LibraryBus với các tối ưu hoá"""
    
    def with_book_counts(self):
        """Tính số lượng sách cùng lúc để tránh N+1 queries"""
        return self.annotate(
            book_count=Count('books_on_bus', filter=Q(books_on_bus__status='available')),
            total_books=Count('books_on_bus')
        )
    
    def active_only(self):
        """Chỉ lấy xe bus đang hoạt động"""
        return self.filter(operating_status='active')
    
    def with_location(self):
        """Chỉ lấy xe bus có thông tin vị trí"""
        return self.filter(latitude__isnull=False, longitude__isnull=False)

class LibraryBus(TimestampedModel):
    """Model cho xe bus sách (thư viện di động) - OPTIMIZED"""
    
    # Cache keys
    CACHE_KEY_BOOK_COUNT = 'bus_book_count_{}'
    CACHE_KEY_CAPACITY_USAGE = 'bus_capacity_usage_{}'
    CACHE_TIMEOUT = 300  # 5 phút
    
    name = models.CharField(max_length=100, unique=True, verbose_name="Tên xe bus", db_index=True)
    license_plate = models.CharField(max_length=20, unique=True, verbose_name="Biển số xe", db_index=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Vĩ độ")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Kinh độ")
    location_name = models.CharField(max_length=255, blank=True, verbose_name="Tên địa điểm", db_index=True)
    operating_status = models.CharField(
        max_length=50, 
        choices=[
            ('active', 'Đang hoạt động'),
            ('parked', 'Tạm nghỉ'),
            ('maintenance', 'Bảo trì'),
            ('moving', 'Đang di chuyển')
        ],
        default='parked',
        verbose_name="Trạng thái hoạt động",
        db_index=True  # Thêm index cho filtering
    )
    capacity = models.PositiveIntegerField(
        default=500,
        validators=[MinValueValidator(1), MaxValueValidator(2000)],
        verbose_name="Sức chứa sách"
    )
    description = models.TextField(blank=True, verbose_name="Mô tả")
    contact_phone = models.CharField(max_length=15, blank=True, verbose_name="Số điện thoại liên hệ")
    operating_hours = models.CharField(max_length=100, blank=True, default="08:00 - 17:00", verbose_name="Giờ hoạt động")
    
    # Denormalized fields để tránh tính toán lại
    _book_count = models.PositiveIntegerField(default=0, verbose_name="Số sách hiện tại")
    _last_book_update = models.DateTimeField(auto_now=True, verbose_name="Cập nhật sách lần cuối")
    
    objects = LibraryBusQuerySet.as_manager()
    
    class Meta:
        verbose_name = "Xe Bus Sách"
        verbose_name_plural = "Các Xe Bus Sách"
        ordering = ['name']
        indexes = [
            models.Index(fields=['operating_status']),
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['updated_at']),
            models.Index(fields=['name', 'operating_status']),  # Composite index
            models.Index(fields=['_book_count']),  # Index cho denormalized field
        ]

    def __str__(self):
        return f"{self.name} ({self.license_plate})"

    @property
    def current_book_count(self):
        """Sử dụng cache và denormalized field"""
        cache_key = self.CACHE_KEY_BOOK_COUNT.format(self.id)
        count = cache.get(cache_key)
        
        if count is None:
            count = self.books_on_bus.filter(status='available').count()
            cache.set(cache_key, count, self.CACHE_TIMEOUT)
            
            # Update denormalized field nếu khác biệt
            if self._book_count != count:
                self._book_count = count
                self.save(update_fields=['_book_count', '_last_book_update'])
        
        return count

    @property
    def capacity_usage_percentage(self):
        """Tính % sử dụng công suất với cache"""
        cache_key = self.CACHE_KEY_CAPACITY_USAGE.format(self.id)
        usage = cache.get(cache_key)
        
        if usage is None:
            count = self.current_book_count
            usage = (count / self.capacity * 100) if self.capacity > 0 else 0
            cache.set(cache_key, usage, self.CACHE_TIMEOUT)
        
        return usage

    def invalidate_cache(self):
        """Xóa cache khi có thay đổi"""
        cache_keys = [
            self.CACHE_KEY_BOOK_COUNT.format(self.id),
            self.CACHE_KEY_CAPACITY_USAGE.format(self.id),
        ]
        cache.delete_many(cache_keys)

    def save(self, *args, **kwargs):
        """Override save để invalidate cache"""
        super().save(*args, **kwargs)
        self.invalidate_cache()

class CategoryQuerySet(BaseQuerySet):
    """Custom QuerySet cho Category"""
    
    def active_only(self):
        return self.filter(is_active=True)
    
    def with_book_counts(self):
        return self.annotate(
            book_count=Count('books', filter=Q(books__status='available')),
            total_books=Count('books')
        )

class Category(TimestampedModel):
    """Model cho lĩnh vực/thể loại sách - OPTIMIZED"""
    
    name = models.CharField(max_length=100, unique=True, verbose_name="Tên lĩnh vực", db_index=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True, db_index=True)
    description = models.TextField(blank=True, verbose_name="Mô tả")
    color_code = models.CharField(max_length=7, blank=True, default="#007bff", verbose_name="Mã màu")
    icon = models.CharField(max_length=50, blank=True, verbose_name="Icon")
    is_active = models.BooleanField(default=True, verbose_name="Đang hoạt động", db_index=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories',
        verbose_name="Danh mục cha",
        db_index=True
    )
    
    # Denormalized field
    _book_count = models.PositiveIntegerField(default=0, verbose_name="Số sách")
    
    objects = CategoryQuerySet.as_manager()

    class Meta:
        verbose_name = "Lĩnh vực"
        verbose_name_plural = "Các lĩnh vực"
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active']),
            models.Index(fields=['is_active', 'name']),  # Composite index
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def update_book_count(self):
        """Cập nhật số lượng sách"""
        count = self.books.filter(status='available').count()
        if self._book_count != count:
            self._book_count = count
            self.save(update_fields=['_book_count'])

class BookQuerySet(BaseQuerySet):
    """Custom QuerySet cho Book với nhiều tối ưu hoá"""
    
    def available(self):
        """Chỉ lấy sách có sẵn"""
        return self.filter(status='available')
    
    def with_list_relations(self):
        """Prefetch nhẹ cho danh sách sách (tránh load status_history thừa)"""
        return self.select_related('category', 'location')
    
    def with_relations(self):
        """Prefetch đầy đủ các relationship bao gồm cả lịch sử trạng thái"""
        return self.select_related('category', 'location').prefetch_related(
            Prefetch('status_history', queryset=BookStatusHistory.objects.select_related('changed_by'))
        )
    
    def with_analytics(self):
        """Prefetch analytics data"""
        return self.select_related('analytics')
    
    def search(self, query):
        """Tìm kiếm tối ưu với full-text search"""
        if not query:
            return self
        
        # Sử dụng Q objects cho complex search
        return self.filter(
            Q(title__icontains=query) |
            Q(author__icontains=query) |
            Q(isbn__icontains=query) |
            Q(publisher__icontains=query)
        )
    
    def by_category(self, category):
        """Filter theo category (bao gồm cả danh mục con)"""
        if category:
            return self.filter(Q(category=category) | Q(category__parent=category))
        return self
    
    def by_location(self, location):
        """Filter theo location"""
        if location:
            return self.filter(location=location)
        return self
    
    def recent(self, days=30):
        """Sách được thêm gần đây"""
        from datetime import timedelta
        return self.filter(created_at__gte=timezone.now() - timedelta(days=days))

class Book(TimestampedModel):
    """Model cho sách - HEAVILY OPTIMIZED"""
    
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('checked_out', 'Checked Out'),
        ('reserved', 'Reserved'),
        ('maintenance', 'Under Maintenance'),
        ('lost', 'Lost')
    ]
    
    CONDITION_CHOICES = [
        ('new', 'Mới'),
        ('like_new', 'Như mới'),
        ('good', 'Tốt'),
        ('fair', 'Khá'),
        ('poor', 'Cũ')
    ]
    
    title = models.CharField(max_length=255, verbose_name="Tên sách", db_index=True)
    author = models.CharField(max_length=200, verbose_name="Tác giả", db_index=True)
    publisher = models.CharField(max_length=200, verbose_name="Nhà xuất bản", db_index=True)
    publication_year = models.IntegerField(
        verbose_name="Năm xuất bản",
        validators=[MinValueValidator(1800), MaxValueValidator(datetime.now().year + 1)],
        db_index=True
    )
    page_count = models.PositiveIntegerField(verbose_name="Số trang", validators=[MinValueValidator(1)])
    isbn = models.CharField(max_length=13, blank=True, verbose_name="ISBN", db_index=True)
    
    # Foreign Keys với proper indexing
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name="books",
        verbose_name="Lĩnh vực",
        db_index=True
    )
    location = models.ForeignKey(
        LibraryBus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='books_on_bus',
        verbose_name="Vị trí sách (trên xe bus)",
        db_index=True
    )
    
    # File fields
    cover_image = models.ImageField(upload_to='book_covers/', null=True, blank=True, verbose_name="Ảnh bìa")
    pdf_file = models.FileField(upload_to='book_pdfs/', null=True, blank=True, verbose_name="File PDF")
    
    # Text fields
    description = models.TextField(blank=True, verbose_name="Mô tả")
    language = models.CharField(max_length=50, default="Tiếng Việt", verbose_name="Ngôn ngữ", db_index=True)
    
    # Status fields
    condition = models.CharField(
        max_length=20,
        choices=CONDITION_CHOICES,
        default='good',
        verbose_name="Tình trạng sách",
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='available',
        db_index=True
    )
    last_status_change = models.DateTimeField(auto_now_add=True, db_index=True)
    is_digital_only = models.BooleanField(default=False, verbose_name="Chỉ có bản điện tử", db_index=True)
    
    # Denormalized analytics fields
    _average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0, verbose_name="Đánh giá TB")
    _total_borrows = models.PositiveIntegerField(default=0, verbose_name="Tổng lượt mượn")
    _popularity_score = models.FloatField(default=0, verbose_name="Điểm phổ biến")
    
    objects = BookQuerySet.as_manager()

    class Meta:
        ordering = ['title']
        verbose_name = "Sách"
        verbose_name_plural = "Các đầu sách"
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['location', 'status']),
            models.Index(fields=['title']),
            models.Index(fields=['author']),
            models.Index(fields=['publication_year']),
            models.Index(fields=['isbn']),
            models.Index(fields=['created_at']),
            models.Index(fields=['_popularity_score']),  # Cho sorting
            models.Index(fields=['status', 'category', 'location']),  # Composite cho filtering
        ]

    def __str__(self):
        return f"{self.title} - {self.author}"

    @property
    def analytics_data(self):
        """Cached analytics data"""
        cache_key = f'book_analytics_{self.id}'
        data = cache.get(cache_key)
        
        if data is None:
            data, _ = BookAnalytics.objects.get_or_create(book=self)
            cache.set(cache_key, data, 600)  # 10 phút
        
        return data

    @property
    def average_rating(self):
        """Sử dụng denormalized field"""
        return float(self._average_rating) if self._average_rating else 0

    @property
    def total_borrows(self):
        """Sử dụng denormalized field"""
        return self._total_borrows

    @property
    def popularity_score(self):
        """Sử dụng denormalized field"""
        return self._popularity_score

    @property
    def is_available(self):
        """Property để tương thích ngược và tiện lợi"""
        return self.status == 'available'

    def update_analytics(self):
        """Cập nhật denormalized analytics fields"""
        try:
            analytics = self.analytics_data
            self._average_rating = analytics.average_rating or 0
            self._total_borrows = analytics.total_borrows or 0
            self._popularity_score = self.calculate_popularity_score()
            self.save(update_fields=['_average_rating', '_total_borrows', '_popularity_score'])
        except Exception as e:
            logger.error(f"Error updating analytics for book {self.id}: {e}")

    def calculate_popularity_score(self):
        """Tính điểm phổ biến dựa trên rating và lượt mượn"""
        rating_weight = 0.3
        borrow_weight = 0.7
        
        normalized_rating = (self._average_rating / 5) * 100 if self._average_rating else 0
        normalized_borrows = min(self._total_borrows / 100, 1) * 100  # Cap at 100 borrows
        
        return (normalized_rating * rating_weight) + (normalized_borrows * borrow_weight)

    def change_status(self, new_status, user=None):
        """Thay đổi status với history tracking"""
        old_status = self.status
        
        if old_status != new_status:
            with transaction.atomic():
                self.status = new_status
                self.last_status_change = timezone.now()
                self.save(update_fields=['status', 'last_status_change'])
                
                # Tạo history record
                BookStatusHistory.objects.create(
                    book=self,
                    from_status=old_status,
                    to_status=new_status,
                    changed_by=user
                )
                
                # Invalidate related caches
                self.invalidate_related_caches()

    def invalidate_related_caches(self):
        """Xóa cache liên quan khi có thay đổi"""
        if self.location:
            self.location.invalidate_cache()
        if self.category:
            cache.delete(f'category_books_{self.category.id}')

class BookStatusHistory(TimestampedModel):
    """Lịch sử thay đổi trạng thái sách"""
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='status_history')
    from_status = models.CharField(max_length=20, db_index=True)
    to_status = models.CharField(max_length=20, db_index=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        db_index=True
    )
    
    class Meta:
        ordering = ['-created_at']
        get_latest_by = 'created_at'
        verbose_name = "Lịch sử trạng thái sách"
        verbose_name_plural = "Lịch sử trạng thái sách"
        indexes = [
            models.Index(fields=['book', '-created_at']),
            models.Index(fields=['from_status', 'to_status']),
        ]

class BusRoute(TimestampedModel):
    """Lộ trình di chuyển của xe bus"""
    bus = models.ForeignKey(LibraryBus, on_delete=models.CASCADE, related_name='routes')
    route_name = models.CharField(max_length=100, db_index=True)
    stops = models.JSONField()  # [{"name": "Hồ Gươm", "lat": ..., "lng": ..., "duration": 60}]
    schedule = models.JSONField()  # {"monday": ["08:00", "14:00"], "tuesday": [...]}
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = "Lộ trình xe bus"
        verbose_name_plural = "Lộ trình xe bus"
        indexes = [
            models.Index(fields=['bus', 'is_active']),
        ]

class InventoryAlert(TimestampedModel):
    """Cảnh báo tồn kho và vận hành"""
    
    ALERT_TYPE_CHOICES = [
        ('low_stock', 'Thiếu sách'),
        ('overstock', 'Thừa sách'),
        ('popular_demand', 'Nhu cầu cao'),
        ('maintenance', 'Cần bảo trì')
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Thấp'),
        ('medium', 'Trung bình'),
        ('high', 'Cao'),
        ('critical', 'Nghiêm trọng')
    ]
    
    bus = models.ForeignKey(LibraryBus, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES, db_index=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, db_index=True)
    message = models.TextField()
    is_resolved = models.BooleanField(default=False, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Cảnh báo tồn kho"
        verbose_name_plural = "Cảnh báo tồn kho"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['bus', 'is_resolved']),
            models.Index(fields=['alert_type', 'severity']),
            models.Index(fields=['created_at']),
        ]

class BookDonation(TimestampedModel):
    """Model lưu trữ thông tin quyên góp sách từ người dùng phổ thông"""
    
    DONATION_STATUS_CHOICES = [
        ('pending', 'Chờ phê duyệt'),
        ('approved', 'Đã phê duyệt'),
        ('rejected', 'Từ chối')
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='donations',
        verbose_name="Người dùng"
    )
    book_title = models.CharField(max_length=255, verbose_name="Tên sách quyên góp")
    author = models.CharField(max_length=200, blank=True, verbose_name="Tác giả")
    description = models.TextField(blank=True, verbose_name="Mô tả / Tình trạng sách")
    status = models.CharField(
        max_length=20, 
        choices=DONATION_STATUS_CHOICES, 
        default='pending',
        verbose_name="Trạng thái"
    )
    book_file = models.FileField(
        upload_to='donations/books/', 
        blank=True, 
        null=True, 
        verbose_name="File sách đính kèm (nếu có)"
    )
    
    class Meta:
        verbose_name = "Quyên góp sách"
        verbose_name_plural = "Quyên góp sách"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.book_title} ({self.get_status_display()})"

from django.core.validators import MinValueValidator, MaxValueValidator

class BookRating(TimestampedModel):
    """Model lưu trữ đánh giá sao cho sách từ người dùng"""
    
    book = models.ForeignKey(
        'Book',
        on_delete=models.CASCADE,
        related_name='ratings',
        verbose_name="Sách"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='book_ratings',
        verbose_name="Người dùng"
    )
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Số sao"
    )
    
    class Meta:
        verbose_name = "Đánh giá sách"
        verbose_name_plural = "Đánh giá sách"
        unique_together = ('book', 'user')
        indexes = [
            models.Index(fields=['book', 'rating']),
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.book.title} ({self.rating} sao)"