# File: users/admin.py
# Mô tả: Cấu hình giao diện admin nâng cao cho ứng dụng Users
# ==============================================================================

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.contrib.admin import SimpleListFilter
from django.utils import timezone
from datetime import timedelta
from .models import (
    Profile, UserInterest, LoginHistory, 
    UserPreference, UserRole
)


# ============================================================================== 
# CUSTOM FILTERS
# ==============================================================================

class MembershipLevelFilter(SimpleListFilter):
    title = 'Hạng thành viên'
    parameter_name = 'membership_level'

    def lookups(self, request, model_admin):
        return [
            ('basic', 'Basic'),
            ('premium', 'Premium'), 
            ('vip', 'VIP'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(profile__membership_level=self.value())
        return queryset


class RecentLoginFilter(SimpleListFilter):
    title = 'Đăng nhập gần đây'
    parameter_name = 'recent_login'

    def lookups(self, request, model_admin):
        return [
            ('today', 'Hôm nay'),
            ('week', '7 ngày qua'),
            ('month', '30 ngày qua'),
            ('inactive', 'Không hoạt động >30 ngày'),
        ]

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'today':
            return queryset.filter(last_login__date=now.date())
        elif self.value() == 'week':
            return queryset.filter(last_login__gte=now - timedelta(days=7))
        elif self.value() == 'month':
            return queryset.filter(last_login__gte=now - timedelta(days=30))
        elif self.value() == 'inactive':
            return queryset.filter(
                Q(last_login__lt=now - timedelta(days=30)) | Q(last_login__isnull=True)
            )
        return queryset


class ProfileCompletionFilter(SimpleListFilter):
    title = 'Độ hoàn thành hồ sơ'
    parameter_name = 'profile_completion'

    def lookups(self, request, model_admin):
        return [
            ('high', 'Cao (>80%)'),
            ('medium', 'Trung bình (50-80%)'),
            ('low', 'Thấp (<50%)'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'high': # > 80% (ít nhất 5/6 trường quan trọng)
            return queryset.filter(
                profile__phone_number__isnull=False,
                profile__date_of_birth__isnull=False,
                profile__city__isnull=False,
                profile__district__isnull=False,
                profile__occupation__isnull=False,
            )
        elif self.value() == 'low': # < 50% (thiếu ít nhất 4/6 trường)
            return queryset.filter(
                Q(profile__phone_number__isnull=True) |
                Q(profile__date_of_birth__isnull=True) |
                Q(profile__city__isnull=True) |
                Q(profile__district__isnull=True) |
                Q(profile__occupation__isnull=True) |
                Q(profile__bio__exact='')
            ).distinct()
        elif self.value() == 'medium':
            # Lấy những user không thuộc high và low
            high_pks = queryset.filter(
                profile__phone_number__isnull=False,
                profile__date_of_birth__isnull=False,
                profile__city__isnull=False,
                profile__district__isnull=False,
                profile__occupation__isnull=False,
            ).values_list('pk', flat=True)
            
            low_pks = queryset.filter(
                Q(profile__phone_number__isnull=True) |
                Q(profile__date_of_birth__isnull=True) |
                Q(profile__city__isnull=True) |
                Q(profile__district__isnull=True) |
                Q(profile__occupation__isnull=True) |
                Q(profile__bio__exact='')
            ).values_list('pk', flat=True)
            
            return queryset.exclude(pk__in=list(high_pks)).exclude(pk__in=list(low_pks))
            
        return queryset



# ============================================================================== 
# INLINE ADMIN CLASSES
# ==============================================================================

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Hồ sơ người dùng'
    fk_name = 'user'
    
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('phone_number', 'date_of_birth', 'gender', 'avatar')
        }),
        ('Địa chỉ', {
            'fields': ('address', 'city', 'district', 'ward', 'postal_code'),
            'classes': ('collapse',)
        }),
        ('Thông tin nghề nghiệp & sở thích', {
            'fields': ('occupation', 'bio', 'favorite_categories', 'reading_goal_monthly'),
            'classes': ('collapse',)
        }),
        ('Trạng thái tài khoản', {
            'fields': ('is_verified', 'membership_level', 'preferred_language'),
        }),
        ('Metadata (chỉ xem)', {
            'fields': ('login_count', 'last_login_ip', 'completion_percentage'),
            'classes': ('collapse',),
        }),
    )
    
    readonly_fields = ('login_count', 'last_login_ip', 'completion_percentage')
    filter_horizontal = ('favorite_categories',)

    def completion_percentage(self, obj):
        if obj and obj.pk:
            return f"{obj.completion_percentage}%"
        return "N/A"
    completion_percentage.short_description = "Độ hoàn thành hồ sơ"


class UserInterestInline(admin.TabularInline):
    model = UserInterest
    extra = 1
    verbose_name = "Sở thích"
    verbose_name_plural = "Sở thích người dùng"


class UserPreferenceInline(admin.StackedInline):
    model = UserPreference
    can_delete = False
    verbose_name_plural = 'Tùy chọn cá nhân'
    fieldsets = (
        ('Giao diện & Hiển thị', {
            'fields': ('theme', 'books_per_page')
        }),
        ('Cài đặt tính năng', {
            'fields': ('auto_renew_books', 'show_reading_progress', 'public_reading_list')
        }),
    )


class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 0
    verbose_name = "Vai trò"
    verbose_name_plural = "Vai trò & Quyền hạn"
    fields = ('role', 'scope', 'valid_from', 'valid_to')


# ============================================================================== 
# MAIN ADMIN CLASSES
# ==============================================================================

class UserAdmin(BaseUserAdmin):
    """Tùy chỉnh UserAdmin với thông tin Profile tích hợp"""
    
    inlines = (ProfileInline, UserPreferenceInline, UserInterestInline, UserRoleInline)
    
    list_display = (
        'username', 'email', 'first_name', 'last_name', 
        'get_membership_level', 'get_verification_status', 
        'get_profile_completion', 'is_staff', 'last_login'
    )
    
    list_filter = BaseUserAdmin.list_filter + (
        MembershipLevelFilter, RecentLoginFilter, ProfileCompletionFilter,
        'profile__is_verified', 'profile__gender', 'profile__city'
    )
    
    search_fields = BaseUserAdmin.search_fields + (
        'profile__phone_number', 'profile__city', 'profile__district'
    )
    
    list_select_related = ('profile',)
    list_per_page = 25

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('profile')

    def get_membership_level(self, obj):
        if hasattr(obj, 'profile'):
            level = obj.profile.membership_level
            colors = {'basic': 'gray', 'premium': 'blue', 'vip': 'gold'}
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                colors.get(level, 'black'),
                level.upper()
            )
        return "N/A"
    get_membership_level.short_description = 'Hạng TV'
    get_membership_level.admin_order_field = 'profile__membership_level'

    def get_verification_status(self, obj):
        if hasattr(obj, 'profile'):
            if obj.profile.is_verified:
                return format_html('<span style="color: green;">✓ Đã xác thực</span>')
            else:
                return format_html('<span style="color: red;">✗ Chưa xác thực</span>')
        return "N/A"
    get_verification_status.short_description = 'Xác thực'
    get_verification_status.admin_order_field = 'profile__is_verified'

    def get_profile_completion(self, obj):
        if hasattr(obj, 'profile'):
            percentage = obj.profile.completion_percentage
            if percentage >= 80:
                color = 'green'
            elif percentage >= 50:
                color = 'orange'
            else:
                color = 'red'
            return format_html(
                '<span style="color: {};">{}</span>',
                color, f"{percentage:.1f}%"
            )
        return "N/A"
    get_profile_completion.short_description = 'Hoàn thành'


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Admin cho Profile với tính năng nâng cao"""
    
    list_display = (
        'user', 'full_name', 'phone_number', 'city_district', 
        'age', 'membership_level_badge', 'verification_status',
        'completion_percentage', 'updated_at'
    )
    
    search_fields = (
        'user__username', 'user__first_name', 'user__last_name', 
        'phone_number', 'city', 'district', 'occupation'
    )
    
    list_filter = (
        'is_verified', 'membership_level', 'gender', 'city', 
        'district', 'preferred_language', 'created_at'
    )
    
    readonly_fields = (
        'created_at', 'updated_at', 'login_count', 'last_login_ip',
        'completion_percentage_display', 'reading_stats_display',
        'user_link'
    )
    
    fieldsets = (
        ('Người dùng', {
            'fields': ('user_link',)
        }),
        ('Thông tin cá nhân', {
            'fields': (
                'phone_number', 'date_of_birth', 'gender', 
                'occupation', 'bio', 'avatar'
            )
        }),
        ('Địa chỉ', {
            'fields': ('address', 'city', 'district', 'ward', 'postal_code'),
            'classes': ('collapse',)
        }),
        ('Tài khoản & Cài đặt', {
            'fields': (
                'is_verified', 'membership_level', 'preferred_language',
                'reading_goal_monthly', 'favorite_categories'
            )
        }),
        ('Thống kê & Metadata', {
            'fields': (
                'completion_percentage_display', 'reading_stats_display',
                'login_count', 'last_login_ip', 'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    filter_horizontal = ('favorite_categories',)
    list_select_related = ('user',)
    list_per_page = 20
    # date_hierarchy = 'created_at'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

    def city_district(self, obj):
        parts = [obj.city, obj.district]
        return ' - '.join([p for p in parts if p]) or "Chưa cập nhật"
    city_district.short_description = 'Thành phố - Quận/Huyện'

    def membership_level_badge(self, obj):
        colors = {'basic': '#6c757d', 'premium': '#007bff', 'vip': '#ffc107'}
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.membership_level, '#6c757d'),
            obj.get_membership_level_display()
        )
    membership_level_badge.short_description = 'Hạng thành viên'

    def verification_status(self, obj):
        if obj.is_verified:
            return format_html('<span style="color: green; font-weight: bold;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    verification_status.short_description = 'XM'

    def completion_percentage_display(self, obj):
        percentage = obj.completion_percentage
        return format_html(
            '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; background-color: #007bff; height: 20px; border-radius: 3px; text-align: center; color: white; font-size: 12px; line-height: 20px;">'
            '{}</div></div>',
            percentage, f"{percentage:.1f}%"
        )
    completion_percentage_display.short_description = 'Độ hoàn thành hồ sơ'

    def reading_stats_display(self, obj):
        stats = obj.reading_stats_summary
        return format_html(
            '<strong>Đã mượn:</strong> {} | <strong>Đã trả:</strong> {} | <strong>Streak:</strong> {} ngày',
            stats['books_borrowed'], stats['books_returned'], stats['streak_days']
        )
    reading_stats_display.short_description = 'Thống kê đọc sách'

    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return "N/A"
    user_link.short_description = 'Người dùng'

    actions = ['verify_users', 'upgrade_to_premium', 'send_verification_code']

    def verify_users(self, request, queryset):
        count = queryset.update(is_verified=True)
        self.message_user(request, f'Đã xác thực {count} người dùng.')
    verify_users.short_description = 'Xác thực người dùng đã chọn'

    def upgrade_to_premium(self, request, queryset):
        count = queryset.update(membership_level='premium')
        self.message_user(request, f'Đã nâng cấp {count} người dùng lên Premium.')
    upgrade_to_premium.short_description = 'Nâng cấp lên Premium'


@admin.register(UserInterest)
class UserInterestAdmin(admin.ModelAdmin):
    list_display = ('user', 'interest_type', 'interest_value', 'weight', 'created_at')
    search_fields = ('user__username', 'interest_value')
    list_filter = ('interest_type', 'weight')
    list_select_related = ('user',)


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'ip_address', 'created_at', 'is_successful')
    search_fields = ('user__username', 'ip_address')
    list_filter = ('is_successful', 'created_at')
    readonly_fields = ('user', 'ip_address', 'user_agent', 'device_info', 'created_at')
    list_select_related = ('user',)
    # date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False  # Không cho phép thêm thủ công

    def has_change_permission(self, request, obj=None):
        return False  # Chỉ xem, không sửa


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'theme', 'books_per_page', 'auto_renew_books', 'public_reading_list')
    search_fields = ('user__username',)
    list_filter = ('theme', 'auto_renew_books', 'show_reading_progress', 'public_reading_list')
    list_select_related = ('user',)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'valid_from', 'valid_to', 'is_active')
    search_fields = ('user__username', 'user__email')
    list_filter = ('role', 'valid_from', 'valid_to')
    list_select_related = ('user',)
    # date_hierarchy = 'valid_from'

    def is_active(self, obj):
        now = timezone.now()
        if obj.valid_to:
            return obj.valid_from <= now <= obj.valid_to
        return obj.valid_from <= now
    is_active.boolean = True
    is_active.short_description = 'Đang hoạt động'


# ============================================================================== 
# ADMIN SITE CUSTOMIZATION
# ==============================================================================

# Đăng ký lại User model với UserAdmin tùy chỉnh
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
