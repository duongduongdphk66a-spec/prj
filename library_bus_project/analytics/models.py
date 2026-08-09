# analytics/models.py 
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db.models import Count, Avg, Sum, F, Q
from django.core.cache import cache
from datetime import datetime, timedelta
import json
from decimal import Decimal

# Import từ core models
from core.models import TimestampedModel, SoftDeleteModel, AuditMixin, CacheMixin

class UserReadingStats(TimestampedModel, AuditMixin):
    """Thống kê đọc sách của người dùng - kế thừa từ TimestampedModel"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='reading_stats')
    
    # Thống kê cơ bản
    total_books_borrowed = models.PositiveIntegerField(default=0)
    total_books_returned = models.PositiveIntegerField(default=0)
    total_pages_read = models.PositiveIntegerField(default=0)
    reading_streak_days = models.PositiveIntegerField(default=0)
    max_reading_streak = models.PositiveIntegerField(default=0)
    
    # Điểm và cấp độ
    reputation_score = models.IntegerField(
        default=100, 
        validators=[MinValueValidator(0), MaxValueValidator(1000)]
    )
    member_level = models.CharField(
        max_length=20,
        choices=[
            ('bronze', 'Đồng'),
            ('silver', 'Bạc'), 
            ('gold', 'Vàng'),
            ('platinum', 'Bạch kim'),
            ('diamond', 'Kim cương')
        ],
        default='bronze'
    )
    
    # Thời gian hoạt động cuối (bổ sung vào TimestampedModel)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Thống kê đọc sách"
        verbose_name_plural = "Thống kê đọc sách"
        indexes = [
            models.Index(fields=['reputation_score']),
            models.Index(fields=['member_level']),
            models.Index(fields=['last_activity']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.get_member_level_display()}"
    
    @property
    def completion_rate(self):
        """Tỷ lệ hoàn thành sách"""
        if self.total_books_borrowed == 0:
            return 100
        return round((self.total_books_returned / self.total_books_borrowed) * 100, 1)
    
    @property
    def reading_velocity(self):
        """Tốc độ đọc (trang/ngày)"""
        if self.total_pages_read == 0 or self.reading_streak_days == 0:
            return 0
        return round(self.total_pages_read / self.reading_streak_days, 1)
    
    @property
    def total_books_read(self):
        """Tính tổng số sách đã đọc (trả thành công)."""
        return self.total_books_returned

    @property
    def current_streak(self):
        """Trả về chuỗi đọc hiện tại."""
        return self.reading_streak_days

    @property
    def total_points(self):
        """Tính tổng điểm từ các hoạt động."""
        return self.user.activities.aggregate(total=Sum('points'))['total'] or 0
    
    @property
    def total_reviews(self):
        """Đếm tổng số review của người dùng."""
        return self.user.activities.filter(activity_type='review').count()
    
    def update_level(self):
        """Cập nhật level dựa trên điểm reputation"""
        old_level = self.member_level
        
        if self.reputation_score >= 800:
            new_level = 'diamond'
        elif self.reputation_score >= 600:
            new_level = 'platinum'
        elif self.reputation_score >= 400:
            new_level = 'gold'
        elif self.reputation_score >= 200:
            new_level = 'silver'
        else:
            new_level = 'bronze'
        
        if old_level != new_level:
            self.member_level = new_level
            self.save(update_fields=['member_level'])
            return True
        return False
    
    def add_reputation(self, points, reason=""):
        """Thêm điểm reputation"""
        self.reputation_score = min(self.reputation_score + points, 1000)
        self.save(update_fields=['reputation_score'])
        self.update_level()
        
        # Log activity
        UserActivity.objects.create(
            user=self.user,
            activity_type='reputation_gained',
            points=points,
            description=reason
        )
    
    # Sử dụng cache methods từ CacheMixin
    @classmethod
    def get_top_readers(cls, limit=10):
        """Lấy top độc giả với cache"""
        return cls.get_cached_custom_data(
            f'top_readers_{limit}',
            lambda: list(cls.objects.active().order_by('-reputation_score')[:limit]),
            timeout=1800  # 30 phút
        )
    
    @classmethod
    def get_level_distribution(cls):
        """Thống kê phân bố level với cache"""
        return cls.get_cached_custom_data(
            'level_distribution',
            lambda: list(cls.objects.active().values('member_level').annotate(count=Count('id')).order_by('-count')),
            timeout=3600  # 1 giờ
        )

class BookAnalytics(TimestampedModel):
    """Thống kê sách - kế thừa từ TimestampedModel"""
    book = models.OneToOneField('inventory.Book', on_delete=models.CASCADE, related_name='analytics')
    
    # Thống kê cơ bản
    total_borrows = models.PositiveIntegerField(default=0)
    total_views = models.PositiveIntegerField(default=0)
    total_reviews = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    trend_direction = models.CharField(max_length=10, default='stable', choices=[('up', 'Tăng'), ('down', 'Giảm'), ('stable', 'Ổn định')])

    # Điểm phổ biến (tính toán đơn giản)
    popularity_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Thời gian mượn cuối
    last_borrowed = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Thống kê sách"
        verbose_name_plural = "Thống kê sách"
        ordering = ['-popularity_score', '-total_borrows']
        indexes = [
            models.Index(fields=['popularity_score']),
            models.Index(fields=['total_borrows']),
            models.Index(fields=['last_borrowed']),
        ]
    
    def __str__(self):
        return f"Stats: {self.book.title}"
    
    def calculate_popularity(self):
        """Tính điểm phổ biến đơn giản"""
        # Trọng số đơn giản: 60% lượt mượn, 30% đánh giá, 10% lượt xem
        borrow_score = min(self.total_borrows * 5, 100)  # Max 100 points
        rating_score = float(self.average_rating) * 20   # Max 100 points
        view_score = min(self.total_views * 0.1, 100)   # Max 100 points
        
        # Bonus cho sách mới (mượn trong 30 ngày gần đây)
        recency_bonus = 0
        if self.last_borrowed and (timezone.now() - self.last_borrowed).days <= 30:
            recency_bonus = 20
        
        self.popularity_score = Decimal(
            borrow_score * 0.6 + 
            rating_score * 0.3 + 
            view_score * 0.1 + 
            recency_bonus
        )
        self.save(update_fields=['popularity_score'])
    
    @property
    def total_readers(self):
        """Đếm số người dùng duy nhất đã mượn sách này."""
        return UserActivity.objects.filter(book=self.book, activity_type='borrow').values('user').distinct().count()
    
    # Sử dụng cache methods từ CacheMixin
    @classmethod
    def get_popular_books(cls, limit=10):
        """Lấy sách phổ biến với cache"""
        return cls.get_cached_custom_data(
            f'popular_books_{limit}',
            lambda: list(
                cls.objects.active()
                .select_related('book')
                .order_by('-popularity_score')
                .values(
                    'book__id',
                    'book__title',
                    'book__author',
                    'popularity_score',
                    'total_borrows',
                    'average_rating'
                )[:limit]
            ),
            timeout=1800  # 30 phút
        )
    
    @classmethod
    def get_trending_books(cls, days=7, limit=10):
        """Lấy sách trending với cache"""
        return cls.get_cached_custom_data(
            f'trending_books_{days}_{limit}',
            lambda: list(
                cls.objects.active()
                .filter(last_borrowed__gte=timezone.now() - timedelta(days=days))
                .select_related('book')
                .order_by('-popularity_score', '-total_borrows')
                .values(
                    'book__id',
                    'book__title',
                    'book__author',
                    'popularity_score',
                    'total_borrows',
                    'last_borrowed'
                )[:limit]
            ),
            timeout=900  # 15 phút
        )

class BusAnalytics(TimestampedModel):
    """Thống kê xe bus - kế thừa từ TimestampedModel"""
    bus = models.OneToOneField('inventory.LibraryBus', on_delete=models.CASCADE, related_name='analytics')
    
    # Thống kê cơ bản
    total_visits = models.PositiveIntegerField(default=0)
    total_borrows = models.PositiveIntegerField(default=0)
    unique_visitors = models.PositiveIntegerField(default=0)
    
    # Hiệu suất
    efficiency_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    class Meta:
        verbose_name = "Thống kê xe bus"
        verbose_name_plural = "Thống kê xe bus"
        ordering = ['-efficiency_score']
    
    def __str__(self):
        return f"Bus Stats: {self.bus.name}"
    
    def calculate_efficiency(self):
        """Tính hiệu suất đơn giản"""
        if self.total_visits == 0:
            self.efficiency_score = 0
        else:
            borrow_rate = (self.total_borrows / self.total_visits) * 100
            self.efficiency_score = min(borrow_rate, 100)
        
        self.save(update_fields=['efficiency_score'])
    
    # Sử dụng cache methods từ CacheMixin
    @classmethod
    def get_top_performing_buses(cls, limit=5):
        """Lấy xe bus hiệu quả nhất với cache"""
        return cls.get_cached_custom_data(
            f'top_buses_{limit}',
            lambda: list(
                cls.objects.active()
                .select_related('bus')
                .order_by('-efficiency_score')
                .values(
                    'bus__id',
                    'bus__name',
                    'bus__route',
                    'efficiency_score',
                    'total_visits',
                    'total_borrows'
                )[:limit]
            ),
            timeout=1800  # 30 phút
        )

class UserActivity(TimestampedModel, AuditMixin):
    """Log hoạt động người dùng - kế thừa từ TimestampedModel và AuditMixin"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(
        max_length=30,
        choices=[
            ('borrow', 'Mượn sách'),
            ('return', 'Trả sách'),
            ('review', 'Đánh giá'),
            ('reputation_gained', 'Tăng điểm'),
            ('level_up', 'Lên hạng'),
            ('login', 'Đăng nhập'),
            ('view_book', 'Xem sách'),
        ]
    )
    book = models.ForeignKey('inventory.Book', on_delete=models.CASCADE, null=True, blank=True)
    bus = models.ForeignKey('inventory.LibraryBus', on_delete=models.CASCADE, null=True, blank=True)
    points = models.IntegerField(default=0)
    description = models.CharField(max_length=200, blank=True)
    
    # Metadata bổ sung
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = "Hoạt động người dùng"
        verbose_name_plural = "Hoạt động người dùng"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['activity_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.get_activity_type_display()}"
    
    # Sử dụng cache methods từ CacheMixin
    @classmethod
    def get_recent_activities(cls, user=None, limit=20):
        """Lấy hoạt động gần đây với cache"""
        if user:
            cache_key = f'user_activities_{user.id}_{limit}'
            return cls.get_cached_custom_data(
                cache_key,
                lambda: list(
                    cls.objects.filter(user=user)
                    .select_related('user', 'book', 'bus')
                    .order_by('-created_at')[:limit]
                ),
                timeout=300  # 5 phút
            )
        else:
            return cls.get_cached_custom_data(
                f'recent_activities_{limit}',
                lambda: list(
                    cls.objects.active()
                    .select_related('user', 'book', 'bus')
                    .order_by('-created_at')[:limit]
                ),
                timeout=300  # 5 phút
            )

class BookRecommendation(TimestampedModel):
    """Gợi ý sách - kế thừa từ TimestampedModel"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recommendations')
    book = models.ForeignKey('inventory.Book', on_delete=models.CASCADE)
    
    # Thuật toán đơn giản
    algorithm_type = models.CharField(
        max_length=20,
        choices=[
            ('popular', 'Phổ biến'),
            ('similar_users', 'Người dùng tương tự'),
            ('same_category', 'Cùng thể loại'),
            ('trending', 'Xu hướng'),
            ('personalized', 'Cá nhân hóa'),
        ],
        default='popular'
    )
    
    score = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    is_clicked = models.BooleanField(default=False)
    is_borrowed = models.BooleanField(default=False)
    
    # Thời gian tương tác
    clicked_at = models.DateTimeField(null=True, blank=True)
    borrowed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Gợi ý sách"
        verbose_name_plural = "Gợi ý sách"
        ordering = ['-score', '-created_at']
        unique_together = ['user', 'book']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['score']),
            models.Index(fields=['algorithm_type']),
        ]
    
    def __str__(self):
        return f"{self.user.username} -> {self.book.title}"
    
    def mark_clicked(self):
        """Đánh dấu đã click"""
        if not self.is_clicked:
            self.is_clicked = True
            self.clicked_at = timezone.now()
            self.save(update_fields=['is_clicked', 'clicked_at'])
    
    def mark_borrowed(self):
        """Đánh dấu đã mượn"""
        if not self.is_borrowed:
            self.is_borrowed = True
            self.borrowed_at = timezone.now()
            self.save(update_fields=['is_borrowed', 'borrowed_at'])
    
    @classmethod
    def generate_popular_recommendations(cls, user, limit=5):
        """Tạo gợi ý dựa trên sách phổ biến"""
        # Lấy sách phổ biến mà user chưa mượn
        borrowed_books = user.borrow_records.values_list('book_id', flat=True)
        
        popular_books = BookAnalytics.objects.active().exclude(
            book_id__in=borrowed_books
        ).select_related('book').order_by('-popularity_score')[:limit]
        
        recommendations = []
        for book_analytics in popular_books:
            rec, created = cls.objects.get_or_create(
                user=user,
                book=book_analytics.book,
                defaults={
                    'algorithm_type': 'popular',
                    'score': min(book_analytics.popularity_score / 100, 1.0)
                }
            )
            recommendations.append(rec)
        
        return recommendations
    
    @classmethod
    def get_user_recommendations(cls, user, limit=10):
        """Lấy gợi ý cho user với cache"""
        return cls.get_cached_custom_data(
            f'user_recommendations_{user.id}_{limit}',
            lambda: list(
                cls.objects.filter(user=user)
                .active()
                .select_related('book')
                .order_by('-score', '-created_at')[:limit]
            ),
            timeout=900  # 15 phút
        )

class DailyStats(TimestampedModel):
    """Thống kê hàng ngày - kế thừa từ TimestampedModel"""
    date = models.DateField(unique=True)
    
    # Thống kê cơ bản
    total_users = models.PositiveIntegerField(default=0)
    active_users = models.PositiveIntegerField(default=0)
    total_borrows = models.PositiveIntegerField(default=0)
    total_returns = models.PositiveIntegerField(default=0)
    new_users = models.PositiveIntegerField(default=0)
    
    # Thống kê chi tiết
    total_page_views = models.PositiveIntegerField(default=0)
    total_searches = models.PositiveIntegerField(default=0)
    total_reviews = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = "Thống kê hàng ngày"
        verbose_name_plural = "Thống kê hàng ngày"
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"Stats {self.date}"
    
    @classmethod
    def generate_daily_stats(cls, date=None):
        """Tạo thống kê cho ngày"""
        if date is None:
            date = timezone.now().date()
        
        # Tính toán thống kê
        total_users = User.objects.count()
        active_users = User.objects.filter(
            last_login__date=date
        ).count()
        
        total_borrows = UserActivity.objects.filter(
            activity_type='borrow',
            created_at__date=date
        ).count()
        
        total_returns = UserActivity.objects.filter(
            activity_type='return',
            created_at__date=date
        ).count()
        
        new_users = User.objects.filter(
            date_joined__date=date
        ).count()
        
        total_page_views = UserActivity.objects.filter(
            activity_type='view_book',
            created_at__date=date
        ).count()
        
        total_reviews = UserActivity.objects.filter(
            activity_type='review',
            created_at__date=date
        ).count()
        
        # Tạo hoặc cập nhật record
        stats, created = cls.objects.update_or_create(
            date=date,
            defaults={
                'total_users': total_users,
                'active_users': active_users,
                'total_borrows': total_borrows,
                'total_returns': total_returns,
                'new_users': new_users,
                'total_page_views': total_page_views,
                'total_reviews': total_reviews,
            }
        )
        
        return stats
    
    @classmethod
    def get_weekly_stats(cls, weeks=4):
        """Lấy thống kê theo tuần với cache"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(weeks=weeks)
        
        return cls.get_cached_custom_data(
            f'weekly_stats_{weeks}',
            lambda: list(
                cls.objects.filter(date__gte=start_date, date__lte=end_date)
                .order_by('-date')
            ),
            timeout=3600  # 1 giờ
        )

# --- SOFT DELETE MODELS ---
class ArchivedUserActivity(SoftDeleteModel):
    """Hoạt động người dùng đã lưu trữ - sử dụng SoftDeleteModel"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='archived_activities')
    activity_type = models.CharField(max_length=30)
    book = models.ForeignKey('inventory.Book', on_delete=models.CASCADE, null=True, blank=True)
    description = models.TextField(blank=True)
    original_created_at = models.DateTimeField()
    
    class Meta:
        verbose_name = "Hoạt động lưu trữ"
        verbose_name_plural = "Hoạt động lưu trữ"
        ordering = ['-original_created_at']
    
    def __str__(self):
        return f"Archived: {self.user.username} - {self.activity_type}"

# --- UTILITY FUNCTIONS CẬP NHẬT ---
def get_user_stats_summary():
    """Lấy tổng quan thống kê người dùng - sử dụng cache từ CacheMixin"""
    return UserReadingStats.get_cached_custom_data(
        'user_stats_summary',
        lambda: {
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(
                last_login__gte=timezone.now() - timedelta(days=30)
            ).count(),
            'top_readers': UserReadingStats.get_top_readers(5),
            'level_distribution': UserReadingStats.get_level_distribution()
        },
        timeout=3600  # 1 giờ
    )

def get_book_stats_summary():
    """Lấy tổng quan thống kê sách - sử dụng cache từ CacheMixin"""
    return BookAnalytics.get_cached_custom_data(
        'book_stats_summary',
        lambda: {
            'total_books': BookAnalytics.objects.active().count(),
            'total_borrows': BookAnalytics.objects.active().aggregate(
                total=Sum('total_borrows')
            )['total'] or 0,
            'avg_rating': BookAnalytics.objects.active().aggregate(
                avg=Avg('average_rating')
            )['avg'] or 0,
            'popular_books': BookAnalytics.get_popular_books(5),
            'trending_books': BookAnalytics.get_trending_books(7, 5)
        },
        timeout=3600  # 1 giờ
    )

def get_system_health():
    """Kiểm tra sức khỏe hệ thống với cache"""
    return DailyStats.get_cached_custom_data(
        'system_health',
        lambda: {
            'cache_version': {
                'users': UserReadingStats.get_current_version(),
                'books': BookAnalytics.get_current_version(),
                'activities': UserActivity.get_current_version(),
            },
            'recent_stats': DailyStats.get_weekly_stats(1),
            'active_users_today': User.objects.filter(
                last_login__date=timezone.now().date()
            ).count(),
        },
        timeout=300  # 5 phút
    )

# --- SIGNAL HANDLERS (Tùy chọn) ---
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_stats(sender, instance, created, **kwargs):
    """Tự động tạo UserReadingStats khi user được tạo"""
    if created:
        UserReadingStats.objects.create(
            user=instance,
            created_by=instance,
            modified_by=instance
        )

@receiver(post_save, sender=UserActivity)
def invalidate_activity_cache(sender, instance, **kwargs):
    """Xóa cache khi có activity mới"""
    # Cache sẽ tự động invalidate nhờ CacheMixin
    pass