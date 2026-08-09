# analytics/admin.py - ĐÃ CẬP NHẬT theo core/models.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Avg, Sum
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import (
    UserReadingStats, 
    BookAnalytics, 
    BusAnalytics, 
    UserActivity,
    BookRecommendation,
    DailyStats,
    ArchivedUserActivity
)
from rangefilter.filters import DateRangeFilter
User = get_user_model()

# --- MIXINS ĐÃ CẬP NHẬT ---

class ReadOnlyAdminMixin:
    """Mixin cho admin chỉ đọc"""
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

class CacheAwareAdminMixin:
    """Mixin hiển thị thông tin cache cho admin"""
    
    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        if hasattr(self.model, 'get_current_version'):
            readonly_fields = list(readonly_fields) + ['cache_info']
        return readonly_fields
    
    def cache_info(self, obj):
        """Hiển thị thông tin cache version"""
        if hasattr(obj.__class__, 'get_current_version'):
            version = obj.__class__.get_current_version()
            return format_html(
                '<small style="color: #666;">Cache Version: {}</small>',
                version
            )
        return '-'
    cache_info.short_description = 'Cache Info'

class TimestampedAdminMixin:
    """Mixin cho các model kế thừa TimestampedModel"""
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def get_list_display(self, request):
        """Thêm timestamps vào list_display nếu chưa có"""
        list_display = list(super().get_list_display(request))
        if 'created_at' not in list_display:
            list_display.append('created_at')
        if 'updated_at' not in list_display:
            list_display.append('updated_at')
        return list_display
    
    def get_list_filter(self, request):
        """Thêm timestamps vào list_filter nếu chưa có"""
        list_filter = list(super().get_list_filter(request))
        if 'created_at' not in list_filter:
            list_filter.append('created_at')
        if 'is_active' not in list_filter:
            list_filter.append('is_active')
        return list_filter

# --- ADMIN CLASSES ĐÃ CẬP NHẬT ---

@admin.register(UserReadingStats)
class UserReadingStatsAdmin(ReadOnlyAdminMixin, TimestampedAdminMixin, CacheAwareAdminMixin, admin.ModelAdmin):
    list_display = [
        'user_link', 
        'level_badge', 
        'reputation_score', 
        'books_ratio',
        'completion_rate_display',
        'reading_velocity',
        'last_activity',
        'is_active'
    ]
    list_filter = [
        'member_level', 
        'last_activity',
        ('reputation_score', DateRangeFilter),
        'is_active',
        'created_at',
        'updated_at'
    ]
    search_fields = [
        'user__username', 
        'user__first_name', 
        'user__last_name',
        'user__email'
    ]
    ordering = ['-reputation_score', '-last_activity']
    list_per_page = 50
    
    # Thêm readonly fields cho audit
    readonly_fields = TimestampedAdminMixin.readonly_fields + [
        'created_by', 'modified_by', 'cache_info'
    ]
    
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('user', 'is_active')
        }),
        ('Thống kê đọc sách', {
            'fields': (
                'total_books_borrowed', 'total_books_returned', 
                'total_pages_read', 'reading_streak_days', 'max_reading_streak'
            )
        }),
        ('Điểm và cấp độ', {
            'fields': ('reputation_score', 'member_level')
        }),
        ('Thông tin hệ thống', {
            'fields': ('id', 'created_at', 'updated_at', 'last_activity'),
            'classes': ('collapse',)
        }),
        ('Audit Trail', {
            'fields': ('created_by', 'modified_by', 'cache_info'),
            'classes': ('collapse',)
        })
    )
    
    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'Người dùng'
    
    def level_badge(self, obj):
        colors = {
            'bronze': '#CD7F32',
            'silver': '#C0C0C0', 
            'gold': '#FFD700',
            'platinum': '#E5E4E2',
            'diamond': '#B9F2FF'
        }
        color = colors.get(obj.member_level, '#666')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_member_level_display()
        )
    level_badge.short_description = 'Hạng'
    
    def books_ratio(self, obj):
        return f"{obj.total_books_returned}/{obj.total_books_borrowed}"
    books_ratio.short_description = 'Trả/Mượn'
    
    def completion_rate_display(self, obj):
        rate = obj.completion_rate
        color = '#28a745' if rate >= 80 else '#ffc107' if rate >= 60 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, f"{rate:.1f}%"
        )
    completion_rate_display.short_description = 'Tỷ lệ hoàn thành'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'created_by', 'modified_by')

@admin.register(BookAnalytics)
class BookAnalyticsAdmin(ReadOnlyAdminMixin, TimestampedAdminMixin, CacheAwareAdminMixin, admin.ModelAdmin):
    list_display = [
        'book_title',
        'popularity_score',
        'rating_display',
        'total_borrows',
        'total_views',
        'last_borrowed',
        'is_active'
    ]
    list_filter = [
        ('popularity_score',DateRangeFilter),
        ('average_rating', DateRangeFilter),
        'last_borrowed',
        'is_active',
        'created_at',
        'updated_at'
    ]
    search_fields = [
        'book__title',
        'book__author',
        'book__isbn'
    ]
    ordering = ['-popularity_score', '-total_borrows']
    list_per_page = 50
    
    readonly_fields = TimestampedAdminMixin.readonly_fields + ['cache_info']
    
    fieldsets = (
        ('Thông tin sách', {
            'fields': ('book', 'is_active')
        }),
        ('Thống kê tương tác', {
            'fields': ('total_borrows', 'total_views', 'total_reviews', 'last_borrowed')
        }),
        ('Đánh giá', {
            'fields': ('average_rating', 'popularity_score')
        }),
        ('Thông tin hệ thống', {
            'fields': ('id', 'created_at', 'updated_at', 'cache_info'),
            'classes': ('collapse',)
        })
    )
    
    def book_title(self, obj):
        return format_html(
            '<strong>{}</strong><br><small>by {}</small>',
            obj.book.title[:60] if obj.book else 'N/A',
            obj.book.author[:40] if obj.book and obj.book.author else 'Unknown'
        )
    book_title.short_description = 'Sách'
    
    def rating_display(self, obj):
        if obj.average_rating == 0:
            return '-'
        
        rating = float(obj.average_rating)
        stars = '★' * int(rating) + '☆' * (5 - int(rating))
        return format_html(
            '<span style="color: #ffc107;">{}</span><br>'
            '<small>{} ({} reviews)</small>',
            stars, f"{rating:.1f}", obj.total_reviews
        )
    rating_display.short_description = 'Đánh giá'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('book')

@admin.register(BusAnalytics)
class BusAnalyticsAdmin(ReadOnlyAdminMixin, TimestampedAdminMixin, CacheAwareAdminMixin, admin.ModelAdmin):
    list_display = [
        'bus_name',
        'efficiency_score',
        'total_visits',
        'total_borrows',
        'unique_visitors',
        'is_active'
    ]
    list_filter = [
        ('efficiency_score', DateRangeFilter),
        'is_active',
        'created_at',
        'updated_at'
    ]
    search_fields = ['bus__name', 'bus__location']
    ordering = ['-efficiency_score']
    
    readonly_fields = TimestampedAdminMixin.readonly_fields + ['cache_info']
    
    def bus_name(self, obj):
        return obj.bus.name if hasattr(obj.bus, 'name') else str(obj.bus)
    bus_name.short_description = 'Xe bus'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('bus')

@admin.register(UserActivity)
class UserActivityAdmin(ReadOnlyAdminMixin, TimestampedAdminMixin, CacheAwareAdminMixin, admin.ModelAdmin):
    list_display = [
        'user',
        'activity_type',
        'book_title',
        'points',
        'created_at',
        'is_active'
    ]
    list_filter = [
        'activity_type',
        'created_at',
        ('points', DateRangeFilter),
        'is_active'
    ]
    search_fields = [
        'user__username',
        'book__title',
        'description'
    ]
    ordering = ['-created_at']
    list_per_page = 100
    
    readonly_fields = TimestampedAdminMixin.readonly_fields + [
        'created_by', 'modified_by', 'metadata_display', 'cache_info'
    ]
    
    fieldsets = (
        ('Thông tin hoạt động', {
            'fields': ('user', 'activity_type', 'book', 'bus', 'is_active')
        }),
        ('Chi tiết', {
            'fields': ('points', 'description', 'metadata_display')
        }),
        ('Audit Trail', {
            'fields': ('created_by', 'modified_by'),
            'classes': ('collapse',)
        }),
        ('Thông tin hệ thống', {
            'fields': ('id', 'created_at', 'updated_at', 'cache_info'),
            'classes': ('collapse',)
        })
    )
    
    def book_title(self, obj):
        return obj.book.title if obj.book else '-'
    book_title.short_description = 'Sách'
    
    def metadata_display(self, obj):
        if obj.metadata:
            return format_html('<pre>{}</pre>', str(obj.metadata))
        return '-'
    metadata_display.short_description = 'Metadata'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'book', 'bus', 'created_by', 'modified_by')

@admin.register(BookRecommendation)
class BookRecommendationAdmin(ReadOnlyAdminMixin, TimestampedAdminMixin, CacheAwareAdminMixin, admin.ModelAdmin):
    list_display = [
        'user',
        'book_title',
        'algorithm_type',
        'score',
        'status',
        'created_at',
        'is_active'
    ]
    list_filter = [
        'algorithm_type',
        'is_clicked',
        'is_borrowed',
        'created_at',
        ('score', DateRangeFilter),
        'is_active'
    ]
    search_fields = [
        'user__username',
        'book__title'
    ]
    ordering = ['-score', '-created_at']
    list_per_page = 100
    
    readonly_fields = TimestampedAdminMixin.readonly_fields + [
        'clicked_at', 'borrowed_at', 'cache_info'
    ]
    
    fieldsets = (
        ('Thông tin gợi ý', {
            'fields': ('user', 'book', 'algorithm_type', 'score', 'is_active')
        }),
        ('Trạng thái tương tác', {
            'fields': ('is_clicked', 'clicked_at', 'is_borrowed', 'borrowed_at')
        }),
        ('Thông tin hệ thống', {
            'fields': ('id', 'created_at', 'updated_at', 'cache_info'),
            'classes': ('collapse',)
        })
    )
    
    def book_title(self, obj):
        return obj.book.title[:50] if obj.book else '-'
    book_title.short_description = 'Sách'
    
    def status(self, obj):
        if obj.is_borrowed:
            return format_html('<span style="color: #28a745;">✓ Đã mượn</span>')
        elif obj.is_clicked:
            return format_html('<span style="color: #ffc107;">👁 Đã xem</span>')
        else:
            return format_html('<span style="color: #6c757d;">- Chưa tương tác</span>')
    status.short_description = 'Trạng thái'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'book')

@admin.register(DailyStats)
class DailyStatsAdmin(ReadOnlyAdminMixin, TimestampedAdminMixin, CacheAwareAdminMixin, admin.ModelAdmin):
    list_display = [
        'date',
        'total_users',
        'active_users',
        'activity_ratio',
        'total_borrows',
        'total_returns',
        'new_users',
        'is_active'
    ]
    list_filter = [
        'date',
        'is_active',
        'created_at'
    ]
    ordering = ['-date']
    # date_hierarchy = 'date'
    
    readonly_fields = TimestampedAdminMixin.readonly_fields + ['cache_info']
    
    fieldsets = (
        ('Ngày thống kê', {
            'fields': ('date', 'is_active')
        }),
        ('Thống kê người dùng', {
            'fields': ('total_users', 'active_users', 'new_users')
        }),
        ('Thống kê hoạt động', {
            'fields': ('total_borrows', 'total_returns', 'total_page_views', 'total_searches', 'total_reviews')
        }),
        ('Thông tin hệ thống', {
            'fields': ('id', 'created_at', 'updated_at', 'cache_info'),
            'classes': ('collapse',)
        })
    )
    
    def activity_ratio(self, obj):
        if obj.total_users == 0:
            return '0%'
        ratio = (obj.active_users / obj.total_users) * 100
        color = '#28a745' if ratio >= 20 else '#ffc107' if ratio >= 10 else '#dc3545'
        return format_html(
            '<span style="color: {};">{}</span>',
            color, f"{ratio:.1f}%"
        )
    activity_ratio.short_description = 'Tỷ lệ hoạt động'
    
    def changelist_view(self, request, extra_context=None):
        # Thêm summary statistics
        response = super().changelist_view(request, extra_context=extra_context)
        
        try:
            qs = response.context_data['cl'].queryset
            summary = {
                'total_users_avg': qs.aggregate(avg=Avg('total_users'))['avg'] or 0,
                'total_borrows_sum': qs.aggregate(sum=Sum('total_borrows'))['sum'] or 0,
                'total_returns_sum': qs.aggregate(sum=Sum('total_returns'))['sum'] or 0,
                'period_days': qs.count(),
            }
            response.context_data['summary'] = summary
        except (AttributeError, KeyError):
            pass
        
        return response

@admin.register(ArchivedUserActivity)
class ArchivedUserActivityAdmin(TimestampedAdminMixin, CacheAwareAdminMixin, admin.ModelAdmin):
    """Admin cho dữ liệu lưu trữ - có thể thao tác restore"""
    list_display = [
        'user',
        'activity_type',
        'book_title',
        'original_created_at',
        'deleted_status',
        'deleted_by'
    ]
    list_filter = [
        'activity_type',
        'original_created_at',
        'deleted_at',
        'is_active'
    ]
    search_fields = [
        'user__username',
        'book__title',
        'description'
    ]
    ordering = ['-original_created_at']
    list_per_page = 100
    
    readonly_fields = TimestampedAdminMixin.readonly_fields + [
        'deleted_at', 'deleted_by', 'cache_info'
    ]
    
    actions = ['restore_activities']
    
    def book_title(self, obj):
        return obj.book.title if obj.book else '-'
    book_title.short_description = 'Sách'
    
    def deleted_status(self, obj):
        if obj.deleted_at:
            return format_html(
                '<span style="color: #dc3545;">🗑 Đã xóa {}</span>',
                obj.deleted_at.strftime('%d/%m/%Y')
            )
        return format_html('<span style="color: #28a745;">✓ Hoạt động</span>')
    deleted_status.short_description = 'Trạng thái'
    
    def restore_activities(self, request, queryset):
        """Action để restore các hoạt động đã xóa"""
        count = 0
        for obj in queryset:
            if obj.deleted_at:
                obj.restore()
                count += 1
        
        self.message_user(
            request,
            f"Đã khôi phục {count} hoạt động.",
            level='success' if count > 0 else 'warning'
        )
    restore_activities.short_description = "Khôi phục hoạt động đã chọn"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'book', 'deleted_by')

# --- CUSTOM ADMIN SITE ĐÃ CẬP NHẬT ---

class AnalyticsAdminSite(admin.AdminSite):
    site_header = 'Library Analytics Dashboard'
    site_title = 'Analytics'
    index_title = 'Thống kê thư viện'
    
    def index(self, request, extra_context=None):
        # Thêm thống kê tổng quan với thông tin cache
        from .models import get_user_stats_summary, get_book_stats_summary, get_system_health
        
        extra_context = extra_context or {}
        
        try:
            extra_context.update({
                'user_summary': get_user_stats_summary(),
                'book_summary': get_book_stats_summary(),
                'system_health': get_system_health(),
                'cache_versions': {
                    'UserReadingStats': UserReadingStats.get_current_version(),
                    'BookAnalytics': BookAnalytics.get_current_version(),
                    'UserActivity': UserActivity.get_current_version(),
                    'DailyStats': DailyStats.get_current_version(),
                }
            })
        except Exception as e:
            extra_context['error'] = f"Lỗi tải thống kê: {str(e)}"
        
        return super().index(request, extra_context)
    
    def app_index(self, request, app_label, extra_context=None):
        extra_context = extra_context or {}
        
        # Thêm thống kê cache cho từng app
        if app_label == 'analytics':
            extra_context['cache_info'] = {
                'total_models': 6,
                'models_with_cache': 5,
                'last_updated': timezone.now(),
            }
        
        return super().app_index(request, app_label, extra_context)

# Đăng ký admin site tùy chỉnh
analytics_admin = AnalyticsAdminSite(name='analytics_admin')

# Đăng ký các model vào site tùy chỉnh
analytics_admin.register(UserReadingStats, UserReadingStatsAdmin)
analytics_admin.register(BookAnalytics, BookAnalyticsAdmin)
analytics_admin.register(BusAnalytics, BusAnalyticsAdmin)
analytics_admin.register(UserActivity, UserActivityAdmin)
analytics_admin.register(BookRecommendation, BookRecommendationAdmin)
analytics_admin.register(DailyStats, DailyStatsAdmin)
analytics_admin.register(ArchivedUserActivity, ArchivedUserActivityAdmin)