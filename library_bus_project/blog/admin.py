# File: blog/admin.py 
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Avg, F
from django.contrib.admin import SimpleListFilter
from django.core.cache import cache
from .models import BlogCategory, BlogTag, Post, PostRating, PostLike, PostView, Newsletter

# Custom Filters
class PublishStatusFilter(SimpleListFilter):
    title = 'Trạng thái xuất bản'
    parameter_name = 'publish_status'
    
    def lookups(self, request, model_admin):
        return (('published_now', 'Đã xuất bản'), ('scheduled', 'Đã lên lịch'), ('draft', 'Bản nháp'))
    
    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'published_now': return queryset.filter(status='published', publish_date__lte=now)
        elif self.value() == 'scheduled': return queryset.filter(status='published', publish_date__gt=now)
        elif self.value() == 'draft': return queryset.filter(status='draft')
        return queryset

class ViewCountFilter(SimpleListFilter):
    title = 'Lượt xem'
    parameter_name = 'view_range'
    
    def lookups(self, request, model_admin):
        return (('high', '> 1000'), ('medium', '100-1000'), ('low', '< 100'))
    
    def queryset(self, request, queryset):
        if self.value() == 'high': return queryset.filter(view_count__gte=1000)
        elif self.value() == 'medium': return queryset.filter(view_count__range=(100, 999))
        elif self.value() == 'low': return queryset.filter(view_count__lt=100)
        return queryset

# Admin Classes
@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'colored_tag', 'post_count_display', 'parent', 'sort_order', 'is_featured')
    list_display_links = ('name',)
    list_filter = ('is_featured', 'parent', 'created_at')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('sort_order', 'is_featured')
    ordering = ('sort_order', 'name')
    readonly_fields = ('post_count', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Thông tin cơ bản', {'fields': ('name', 'slug', 'description', 'parent')}),
        ('Hiển thị', {'fields': ('color_code', 'icon', 'sort_order', 'is_featured')}),
        ('SEO', {'fields': ('seo_title', 'seo_description'), 'classes': ('collapse',)}),
        ('Thống kê', {'fields': ('post_count', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('parent')
    
    def colored_tag(self, obj):
        return format_html('<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>', obj.color_code, obj.name)
    colored_tag.short_description = 'Màu sắc'
    
    def post_count_display(self, obj):
        return format_html('<strong>{}</strong> bài viết', obj.post_count)
    post_count_display.short_description = 'Số bài viết'
    post_count_display.admin_order_field = 'post_count'

@admin.register(BlogTag)
class BlogTagAdmin(admin.ModelAdmin):
    list_display = ('name','is_trending', 'slug', 'usage_count', 'trending_status', 'created_at')
    list_display_links = ('name',)
    list_filter = ('is_trending', 'created_at')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('is_trending',)
    ordering = ('-usage_count', 'name')
    readonly_fields = ('usage_count', 'created_at', 'updated_at')
    
    def trending_status(self, obj):
        if obj.is_trending: return format_html('<span style="color: #e74c3c;">🔥 Trending</span>')
        return '—'
    trending_status.short_description = 'Xu hướng'

class PostRatingInline(admin.TabularInline):
    model = PostRating
    extra = 0
    readonly_fields = ('user', 'score', 'created_at')
    can_delete = True
    max_num = 10

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title_with_status', 'author', 'status_badge', 'publish_info', 'engagement_stats', 'feature_flags', 'created_at')
    list_display_links = ('title_with_status',)
    list_filter = (PublishStatusFilter, ViewCountFilter, 'content_type', 'is_featured', 'is_pinned', 'allow_comments', 'categories', 'author')
    search_fields = ('title', 'content', 'excerpt', 'author__username', 'author__first_name', 'author__last_name')
    prepopulated_fields = {'slug': ('title',)}
    autocomplete_fields = ('author',)
    filter_horizontal = ('categories', 'tags')
    readonly_fields = ('view_count', 'like_count', 'comment_count', 'reading_time', 'engagement_score', 'avg_rating_display', 'created_at', 'updated_at')
    inlines = [PostRatingInline]
    list_per_page = 25
    save_on_top = True
    
    fieldsets = (
        ('📝 Nội dung chính', {'fields': ('title', 'slug', 'author', 'content_type')}),
        ('📊 Trạng thái', {'fields': ('status', 'publish_date', 'is_featured', 'is_pinned', 'allow_comments')}),
        ('📄 Nội dung', {'fields': ('excerpt', 'content')}),
        ('🖼️ Media', {'fields': ('featured_image', 'featured_image_alt')}),
        ('🏷️ Phân loại', {'fields': ('categories', 'tags')}),
        ('🔍 SEO', {'fields': ('seo_title', 'seo_description'), 'classes': ('collapse',)}),
        ('📈 Thống kê', {'fields': ('view_count', 'like_count', 'comment_count', 'reading_time', 'engagement_score', 'avg_rating_display'), 'classes': ('collapse',)}),
        ('ℹ️ Hệ thống', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('author').prefetch_related('categories', 'tags').annotate(avg_rating=Avg('ratings__score'))
    
    def title_with_status(self, obj):
        icon = '📌' if obj.is_pinned else ('⭐' if obj.is_featured else '📄')
        title = obj.title[:50] + ('...' if len(obj.title) > 50 else '')
        return format_html('{} {}', icon, title)
    title_with_status.short_description = 'Tiêu đề'
    title_with_status.admin_order_field = 'title'
    
    def status_badge(self, obj):
        colors = {'published': '#27ae60', 'draft': '#f39c12', 'archived': '#95a5a6'}
        labels = {'published': 'Xuất bản', 'draft': 'Nháp', 'archived': 'Lưu trữ'}
        color = colors.get(obj.status, '#6c757d')
        label = labels.get(obj.status, obj.status)
        return format_html('<span style="background: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>', color, label)
    status_badge.short_description = 'Trạng thái'
    status_badge.admin_order_field = 'status'
    
    def publish_info(self, obj):
        if obj.status == 'published':
            if obj.publish_date and obj.publish_date > timezone.now():
                return format_html('<span style="color: #e67e22;">📅 {}</span>', obj.publish_date.strftime('%d/%m/%Y %H:%M'))
            return format_html('<span style="color: #27ae60;">✅ Đã xuất bản</span>')
        return '—'
    publish_info.short_description = 'Xuất bản'
    publish_info.admin_order_field = 'publish_date'
    
    def engagement_stats(self, obj):
        return format_html('👁️ {} | 👍 {} | 💬 {}', obj.view_count, obj.like_count, obj.comment_count)
    engagement_stats.short_description = 'Tương tác'
    
    def feature_flags(self, obj):
        flags = []
        if obj.is_featured: flags.append('⭐')
        if obj.is_pinned: flags.append('📌')
        if not obj.allow_comments: flags.append('🚫💬')
        return ' '.join(flags) if flags else '—'
    feature_flags.short_description = 'Cờ'
    
    def engagement_score(self, obj):
        return f"{obj.engagement_score:.1f}"
    engagement_score.short_description = 'Điểm tương tác'
    
    def avg_rating_display(self, obj):
        avg = getattr(obj, 'avg_rating', None)
        if avg: return format_html('⭐ <strong>{}</strong>/5', f"{avg:.1f}")
        return 'Chưa có đánh giá'
    avg_rating_display.short_description = 'Đánh giá TB'
    
    actions = ['make_featured', 'remove_featured', 'make_published', 'make_draft', 'clear_cache']
    
    def make_featured(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'Đã đánh dấu {updated} bài viết là nổi bật.')
    make_featured.short_description = 'Đánh dấu nổi bật'
    
    def remove_featured(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'Đã bỏ đánh dấu nổi bật cho {updated} bài viết.')
    remove_featured.short_description = 'Bỏ đánh dấu nổi bật'
    
    def make_published(self, request, queryset):
        updated = queryset.update(status='published', publish_date=timezone.now())
        self.message_user(request, f'Đã xuất bản {updated} bài viết.')
    make_published.short_description = 'Xuất bản ngay'
    
    def make_draft(self, request, queryset):
        updated = queryset.update(status='draft')
        self.message_user(request, f'Đã chuyển {updated} bài viết về nháp.')
    make_draft.short_description = 'Chuyển về nháp'
    
    def clear_cache(self, request, queryset):
        cache.clear()
        self.message_user(request, 'Đã xóa cache thành công.')
    clear_cache.short_description = 'Xóa cache'

@admin.register(PostRating)
class PostRatingAdmin(admin.ModelAdmin):
    list_display = ('post', 'user', 'score_stars', 'created_at')
    list_filter = ('score', 'created_at')
    search_fields = ('post__title', 'user__username')
    readonly_fields = ('post', 'user', 'score', 'created_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('post', 'user')
    
    def score_stars(self, obj):
        return '⭐' * obj.score + '☆' * (5 - obj.score)
    score_stars.short_description = 'Đánh giá'
    
    def has_add_permission(self, request): return False

@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display = ('post', 'user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('post__title', 'user__username')
    readonly_fields = ('post', 'user', 'created_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('post', 'user')
    
    def has_add_permission(self, request): return False

@admin.register(PostView)
class PostViewAdmin(admin.ModelAdmin):
    list_display = ('post', 'user_info', 'ip_address', 'read_duration', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('post__title', 'user__username', 'ip_address')
    readonly_fields = ('post', 'user', 'ip_address', 'user_agent', 'session_key', 'read_duration', 'created_at')
    # date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('post', 'user')
    
    def user_info(self, obj):
        if obj.user: return format_html('<strong>{}</strong>', obj.user.username)
        return format_html('<em>Khách ({})</em>', obj.session_key[:8] if obj.session_key else 'N/A')
    user_info.short_description = 'Người dùng'
    
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False

@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = ('email', 'status_badge', 'frequency', 'categories_list', 'confirmed_at', 'created_at')
    list_filter = ('is_confirmed', 'frequency', 'categories', 'created_at')
    search_fields = ('email',)
    filter_horizontal = ('categories',)
    readonly_fields = ('confirmed_at', 'created_at', 'updated_at')
    # date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Thông tin đăng ký', {'fields': ('email', 'is_confirmed', 'confirmed_at')}),
        ('Tùy chọn', {'fields': ('frequency', 'categories')}),
        ('Hệ thống', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('categories')
    
    def status_badge(self, obj):
        if obj.is_confirmed: return format_html('<span style="color: #27ae60;">✅ Đã xác nhận</span>')
        return format_html('<span style="color: #e74c3c;">❌ Chưa xác nhận</span>')
    status_badge.short_description = 'Trạng thái'
    status_badge.admin_order_field = 'is_confirmed'
    
    def categories_list(self, obj):
        categories = obj.categories.all()
        if categories:
            names = [cat.name for cat in categories[:3]]
            result = ', '.join(names)
            if categories.count() > 3: result += '...'
            return result
        return 'Tất cả'
    categories_list.short_description = 'Chuyên mục'
    
    actions = ['send_confirmation_email', 'mark_confirmed']
    
    def send_confirmation_email(self, request, queryset):
        count = queryset.filter(is_confirmed=False).count()
        self.message_user(request, f'Đã gửi email xác nhận đến {count} địa chỉ.')
    send_confirmation_email.short_description = 'Gửi email xác nhận'
    
    def mark_confirmed(self, request, queryset):
        updated = queryset.update(is_confirmed=True, confirmed_at=timezone.now())
        self.message_user(request, f'Đã xác nhận {updated} đăng ký.')
    mark_confirmed.short_description = 'Đánh dấu đã xác nhận'

# --- MOVED FROM COMMUNITY ---
# File: blog/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, NoReverseMatch
from django.utils import timezone
from django.db.models import Count, Avg, Q
from django.contrib.admin import SimpleListFilter
from django.core.cache import cache
from django.contrib import messages
from django.shortcuts import redirect
from django.http import HttpResponseRedirect
from .models import (
    Comment, CommentLike, Report,
)
import logging

logger = logging.getLogger(__name__)
# ================== CUSTOM ACTIONS ==================

def approve_comments(modeladmin, request, queryset):
    """Duyệt comments hàng loạt"""
    updated = queryset.filter(is_approved=False).update(is_approved=True)
    messages.success(request, f'Đã duyệt {updated} bình luận')
approve_comments.short_description = "Duyệt các bình luận đã chọn"

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['author', 'post_title', 'content_preview', 'is_approved', 'likes_count', 'depth', 'created_at', 'is_pinned']
    list_filter = ['is_approved', 'is_pinned', 'depth', 'created_at']
    search_fields = ['author__username', 'post__title', 'content']
    list_editable = ['is_approved', 'is_pinned']
    readonly_fields = ['likes_count', 'depth', 'thread_id']
    # date_hierarchy = 'created_at'
    actions = [approve_comments]
    
    fieldsets = (
        ('Nội dung', {'fields': ('author', 'post', 'content', 'parent')}),
        ('Trạng thái', {'fields': ('is_approved', 'is_pinned')}),
        ('Thống kê', {'fields': ('likes_count', 'depth', 'thread_id'), 'classes': ('collapse',)}),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('author', 'post', 'parent')
    
    def post_title(self, obj): return obj.post.title
    post_title.short_description = 'Bài viết'
    post_title.admin_order_field = 'post__title'
    
    def content_preview(self, obj): return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Nội dung'

@admin.register(CommentLike)
class CommentLikeAdmin(admin.ModelAdmin):
    list_display = ['user', 'comment_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'comment__content', 'comment__author__username']
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'comment', 'comment__author')
    
    def comment_preview(self, obj): return f"{obj.comment.content[:50]}..." if len(obj.comment.content) > 50 else obj.comment.content
    comment_preview.short_description = 'Bình luận'
    
    def has_add_permission(self, request): return False

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('reporter', 'content_object_link', 'reason', 'status', 'created_at')
    list_filter = ('status', 'reason', 'content_type')
    search_fields = ('reporter__username', 'description')
    list_editable = ('status',)
    readonly_fields = ('reporter', 'content_type', 'object_id', 'content_object_link')
    # date_hierarchy = 'created_at'
    actions = ['mark_as_reviewed']

    def content_object_link(self, obj):
        if obj.content_object:
            try:
                admin_url = reverse(f'admin:{obj.content_type.app_label}_{obj.content_type.model}_change', args=[obj.object_id])
                return format_html('<a href="{}">{}</a>', admin_url, obj.content_object)
            except NoReverseMatch:
                return f"{obj.content_object} (No admin URL)"
        return "N/A"
    content_object_link.short_description = 'Nội dung bị báo cáo'

    def mark_as_reviewed(self, request, queryset):
        updated = queryset.update(status='reviewed', moderator=request.user)
        messages.success(request, f'Đã đánh dấu {updated} báo cáo là đã xử lý.')
    mark_as_reviewed.short_description = 'Đánh dấu là đã xử lý'

class CommunityAdminMixin:
    """Mixin để thêm các tính năng chung cho admin"""
    
    def get_actions(self, request):
        actions = super().get_actions(request)
        # Xóa action delete mặc định cho một số models nhạy cảm
        if hasattr(self, 'disable_delete') and self.disable_delete:
            if 'delete_selected' in actions:
                del actions['delete_selected']
        return actions
    
    def changelist_view(self, request, extra_context=None):
        """Thêm thống kê vào changelist"""
        extra_context = extra_context or {}
        
        # Thêm cache stats nếu có
        if hasattr(self, 'get_stats'):
            cache_key = f'admin_stats_{self.model._meta.label_lower}'
            stats = cache.get(cache_key)
            if stats is None:
                stats = self.get_stats(request)
                cache.set(cache_key, stats, 300)  # Cache 5 phút
            extra_context['stats'] = stats
        
        return super().changelist_view(request, extra_context)

admin.site.site_header = 'Quản trị Thư viện Di động'
admin.site.site_title = 'Library Bus Admin'
admin.site.index_title = 'Quản trị hệ thống'

def admin_index_context(request):
    """Context cho trang admin index"""
    context = {}
    
    today = timezone.now().date()
    context.update({
        'pending_comments': Comment.objects.filter(is_approved=False).count(),
        'today_comments': Comment.objects.filter(created_at__date=today).count(),
        'pending_reports': Report.objects.filter(status='pending').count(),
    })
    
    return context

# Register custom context processor
try:
    from django.template.context_processors import request
    if not hasattr(admin.site, '_original_each_context'):
        admin.site._original_each_context = admin.site.each_context
        admin.site.each_context = lambda req: {**admin.site._original_each_context(req), **admin_index_context(req)}
except ImportError:
    pass

