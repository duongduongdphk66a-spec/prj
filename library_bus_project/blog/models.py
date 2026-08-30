# File: blog/models.py 
from PIL import Image
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.text import slugify
from django.utils.html import strip_tags
from django.core.validators import MinLengthValidator, FileExtensionValidator
from django.core.cache import cache
from django.db.models import Q, Count, Avg, F, Prefetch
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from core.models import TimestampedModel, SoftDeleteModel, CacheMixin, BaseManager, BaseQuerySet

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db.models import Sum, Max
import logging
logger = logging.getLogger(__name__)


# --- OPTIMIZED QUERYSETS ---
class BlogQuerySet(BaseQuerySet):
    """Tối ưu QuerySet với select_related và prefetch_related"""
    def published(self): return self.filter(status='published', publish_date__lte=timezone.now())
    def draft(self): return self.filter(status='draft')
    def featured(self): return self.filter(is_featured=True)
    def popular(self, days=30): return self.filter(created_at__gte=timezone.now() - timedelta(days=days)).order_by('-view_count', '-like_count')
    def by_category(self, category_slug): return self.filter(categories__slug=category_slug)
    def search(self, query): return self.filter(Q(title__icontains=query) | Q(content__icontains=query) | Q(excerpt__icontains=query) | Q(tags__name__icontains=query)).distinct()
    def with_full_data(self): return self.select_related('author').prefetch_related('categories', 'tags', Prefetch('comments', queryset=Comment.objects.filter(is_approved=True))).annotate(comment_count=Count('comments', filter=Q(comments__is_approved=True)), avg_rating=Avg('ratings__score'))
    def list_optimized(self): return self.select_related('author').prefetch_related('categories', 'tags').only('id', 'title', 'slug', 'excerpt', 'featured_image', 'author__username', 'author__first_name', 'author__last_name', 'created_at', 'view_count', 'like_count', 'is_featured', 'is_pinned')
    def with_stats(self): return self

class BlogManager(BaseManager):
    def get_queryset(self): return BlogQuerySet(self.model, using=self._db)
    def published(self): return self.get_queryset().published()
    def popular(self, days=30): return self.get_queryset().popular(days)
    def search(self, query): return self.get_queryset().search(query)
    def list_optimized(self): return self.get_queryset().list_optimized()

# --- CATEGORY MODEL ---
class BlogCategory(TimestampedModel):
    """Chuyên mục blog tối ưu với cache"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Tên chuyên mục", db_index=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True, verbose_name="Đường dẫn")
    description = models.TextField(blank=True, verbose_name="Mô tả")
    color_code = models.CharField(max_length=7, blank=True, default="#007bff", verbose_name="Mã màu")
    icon = models.CharField(max_length=50, blank=True, verbose_name="Icon CSS class")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name="Chuyên mục cha")
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name="Thứ tự", db_index=True)
    post_count = models.PositiveIntegerField(default=0, verbose_name="Số bài viết", db_index=True)  # Denormalized field
    seo_title = models.CharField(max_length=160, blank=True, verbose_name="SEO Title")
    seo_description = models.CharField(max_length=320, blank=True, verbose_name="SEO Description")
    is_featured = models.BooleanField(default=False, verbose_name="Nổi bật", db_index=True)

    class Meta:
        verbose_name = "Chuyên mục Blog"
        verbose_name_plural = "Chuyên mục Blog"
        ordering = ['sort_order', 'name']
        indexes = [models.Index(fields=['slug']), models.Index(fields=['parent', 'sort_order']), models.Index(fields=['-post_count'])]

    def __str__(self): return self.name
    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self): return reverse('blog:category_detail', args=[self.slug])
    
    @classmethod
    def get_featured_categories(cls, limit=6):
        """Cache featured categories"""
        return cls.get_cached_custom_data('featured_categories', lambda: list(cls.objects.filter(is_featured=True).order_by('sort_order')[:limit]), timeout=3600)

# --- TAG MODEL ---
class BlogTag(TimestampedModel):
    """Tag với usage tracking"""
    name = models.CharField(max_length=50, unique=True, verbose_name="Tên tag", db_index=True)
    slug = models.SlugField(max_length=50, unique=True, blank=True)
    description = models.TextField(blank=True, max_length=200, verbose_name="Mô tả")
    usage_count = models.PositiveIntegerField(default=0, verbose_name="Số lần dùng", db_index=True)
    is_trending = models.BooleanField(default=False, verbose_name="Xu hướng", db_index=True)

    class Meta:
        verbose_name = "Tag Blog"
        verbose_name_plural = "Tag Blog"
        ordering = ['-usage_count', 'name']
        indexes = [models.Index(fields=['slug']), models.Index(fields=['-usage_count'])]

    def __str__(self): return self.name
    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self): return reverse('blog:tag_detail', args=[self.slug])

    @classmethod
    def get_trending_tags(cls, limit=10):
        """Cache trending tags"""
        return cls.get_cached_custom_data('trending_tags', lambda: list(cls.objects.filter(is_trending=True).order_by('-usage_count')[:limit]), timeout=1800)

# --- POST MODEL ---
def post_image_upload_path(instance, filename): return f'blog/posts/{instance.created_at.year}/{instance.created_at.month}/{filename}'

class Post(SoftDeleteModel, CacheMixin):
    """Optimized Post model"""
    title = models.CharField(max_length=255, unique=True, verbose_name="Tiêu đề", validators=[MinLengthValidator(10)], db_index=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True, verbose_name="Đường dẫn", db_index=True)
    excerpt = models.TextField(max_length=500, blank=True, verbose_name="Tóm tắt")
    content = models.TextField(verbose_name="Nội dung")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_posts', verbose_name="Tác giả", db_index=True)
    categories = models.ManyToManyField(BlogCategory, related_name='posts', verbose_name="Chuyên mục")
    tags = models.ManyToManyField(BlogTag, blank=True, related_name='posts', verbose_name="Tags")
    publish_date = models.DateTimeField(null=True, blank=True, verbose_name="Ngày xuất bản", db_index=True)
    
    # Media & SEO
    featured_image = models.ImageField(upload_to=post_image_upload_path, null=True, blank=True, verbose_name="Ảnh bìa", validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])])
    featured_image_alt = models.CharField(max_length=200, blank=True, verbose_name="Alt text")
    seo_title = models.CharField(max_length=160, blank=True, verbose_name="SEO Title")
    seo_description = models.CharField(max_length=320, blank=True, verbose_name="SEO Description")
    
    # Denormalized fields for performance
    view_count = models.PositiveIntegerField(default=0, verbose_name="Lượt xem", db_index=True)
    like_count = models.PositiveIntegerField(default=0, verbose_name="Lượt thích", db_index=True)
    comment_count = models.PositiveIntegerField(default=0, verbose_name="Số bình luận", db_index=True)
    reading_time = models.PositiveSmallIntegerField(default=1, verbose_name="Thời gian đọc (phút)")
    
    # Flags
    is_featured = models.BooleanField(default=False, verbose_name="Nổi bật", db_index=True)
    is_pinned = models.BooleanField(default=False, verbose_name="Ghim", db_index=True)
    allow_comments = models.BooleanField(default=True, verbose_name="Cho phép bình luận")
    content_type = models.CharField(max_length=20, choices=[('article', 'Bài viết'), ('review', 'Đánh giá'), ('interview', 'Phỏng vấn'), ('tutorial', 'Hướng dẫn'), ('news', 'Tin tức')], default='article', verbose_name="Loại nội dung", db_index=True)
    
    status = models.CharField(max_length=20, choices=[('draft', 'Bản nháp'), ('pending', 'Chờ duyệt'), ('published', 'Đã xuất bản'), ('rejected', 'Bị từ chối'), ('archived', 'Lưu trữ')], default='draft', verbose_name="Trạng thái", db_index=True)
    moderated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='moderated_posts', verbose_name="Người duyệt")
    moderated_at = models.DateTimeField(null=True, blank=True, verbose_name="Ngày duyệt")
    moderation_note = models.TextField(blank=True, verbose_name="Ghi chú duyệt")


    objects = BlogManager()
    
    class Meta:
        ordering = ['-is_pinned', '-publish_date', '-created_at']
        verbose_name = "Bài viết Blog"
        verbose_name_plural = "Bài viết Blog"
        indexes = [
            models.Index(fields=['status', 'publish_date']), models.Index(fields=['author', 'status']),
            models.Index(fields=['-view_count']), models.Index(fields=['-like_count']),
            models.Index(fields=['is_featured', 'status']), models.Index(fields=['content_type', 'status']),
            models.Index(fields=['slug', 'status']), models.Index(fields=['-created_at'])
        ]

    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.title)
        if self.status == 'published' and not self.publish_date: self.publish_date = timezone.now()
        if not self.excerpt and self.content: self.excerpt = self.generate_excerpt()
        self.reading_time = self.calculate_reading_time()
        super().save(*args, **kwargs)
        if self.featured_image: self.resize_featured_image()

    def generate_excerpt(self, max_length=400):
        """Tạo excerpt từ content"""
        clean_content = strip_tags(self.content)
        if len(clean_content) <= max_length: return clean_content
        return clean_content[:max_length].rsplit(' ', 1)[0] + '...'

    def calculate_reading_time(self, wpm=200):
        """Tính thời gian đọc"""
        word_count = len(strip_tags(self.content).split())
        return max(1, round(word_count / wpm))

    def resize_featured_image(self):
        """Resize ảnh để tối ưu"""
        try:
            if self.featured_image:
                img = Image.open(self.featured_image.path)
                if img.width > 1200 or img.height > 800:
                    img.thumbnail((1200, 800), Image.Resampling.LANCZOS)
                    img.save(self.featured_image.path, optimize=True, quality=85)
        except Exception: pass

    def get_absolute_url(self): return reverse('blog:post_detail', args=[self.slug])

    def increment_view_count(self):
        """Tăng view count với cache lock"""
        cache_key = f'post_view_lock_{self.id}'
        if not cache.get(cache_key):
            Post.objects.filter(id=self.id).update(view_count=F('view_count') + 1)
            cache.set(cache_key, True, 30)


    @property
    def is_published(self): return self.status == 'published' and (not self.publish_date or self.publish_date <= timezone.now())

    @property
    def engagement_score(self): return (self.view_count * 0.1) + (self.like_count * 0.3) + (self.comment_count * 0.6)

    def get_related_posts(self, limit=4):
        """Lấy bài viết liên quan với cache"""
        key_suffix = f"related_posts_{self.id}_{limit}"
        
        def fetch_related():
            # Tìm theo tags
            tag_related = Post.objects.published().filter(tags__in=self.tags.all()).exclude(id=self.id).distinct()[:limit]
            related_list = list(tag_related)
            
            if len(related_list) < limit:
                # Bổ sung từ categories
                exclude_ids = [p.id for p in related_list] + [self.id]
                cat_related = Post.objects.published().filter(categories__in=self.categories.all()).exclude(id__in=exclude_ids)[:limit - len(related_list)]
                related_list.extend(list(cat_related))
            
            return related_list

        return Post.get_cached_custom_data(key_suffix, fetch_related, timeout=1800)

    @classmethod
    def get_popular_posts(cls, days=7, limit=5):
        """Popular posts với cache"""
        key_suffix = f"popular_posts_{days}_{limit}"
        
        def fetch_popular():
            return list(cls.objects.published().filter(created_at__gte=timezone.now() - timedelta(days=days)).order_by('-view_count', '-like_count')[:limit])
        
        return cls.get_cached_custom_data(key_suffix, fetch_popular, timeout=900)

    @classmethod
    def get_recent_posts(cls, limit=5):
        """Recent posts với cache"""
        key_suffix = f"recent_posts_{limit}"
        
        def fetch_recent():
            return list(cls.objects.published().order_by('-publish_date')[:limit])
        
        return cls.get_cached_custom_data(key_suffix, fetch_recent, timeout=300)


# --- INTERACTION MODELS ---
class PostRating(TimestampedModel):
    """Đánh giá bài viết"""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='ratings', db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_ratings')
    score = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)], verbose_name="Điểm")
    
    class Meta:
        unique_together = ['post', 'user']
        verbose_name = "Đánh giá bài viết"
        verbose_name_plural = "Đánh giá bài viết"
        indexes = [models.Index(fields=['post', 'score'])]

class PostLike(TimestampedModel):
    """Like bài viết"""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes', db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_likes')
    
    class Meta:
        unique_together = ['post', 'user']
        verbose_name = "Thích bài viết"
        verbose_name_plural = "Thích bài viết"
        indexes = [models.Index(fields=['post', 'user'])]

class PostView(TimestampedModel):
    """Tracking lượt xem tối ưu"""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='detailed_views', db_index=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(verbose_name="IP", db_index=True)
    user_agent = models.TextField(blank=True)
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    read_duration = models.PositiveIntegerField(default=0, verbose_name="Thời gian đọc (giây)")
    
    class Meta:
        verbose_name = "Lượt xem"
        verbose_name_plural = "Lượt xem"
        indexes = [models.Index(fields=['post', 'created_at']), models.Index(fields=['ip_address', 'created_at'])]

class Newsletter(TimestampedModel):
    """Newsletter subscription"""
    email = models.EmailField(unique=True, verbose_name="Email")
    is_confirmed = models.BooleanField(default=False, verbose_name="Đã xác nhận", db_index=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    categories = models.ManyToManyField(BlogCategory, blank=True, verbose_name="Chuyên mục")
    frequency = models.CharField(max_length=10, choices=[('daily', 'Hàng ngày'), ('weekly', 'Hàng tuần'), ('monthly', 'Hàng tháng')], default='weekly', verbose_name="Tần suất")
    
    class Meta:
        verbose_name = "Newsletter"
        verbose_name_plural = "Newsletter"
        indexes = [models.Index(fields=['email', 'is_confirmed'])]

# --- SIGNALS ---
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver

@receiver(post_save, sender=PostLike)
def update_like_count_on_save(sender, instance, created, **kwargs):
    """Cập nhật like_count khi có like mới"""
    if created:
        Post.objects.filter(id=instance.post.id).update(like_count=F('like_count') + 1)
        # Xóa cache related posts
        cache.delete(f"custom:related_posts_{instance.post.id}_4")

@receiver(post_delete, sender=PostLike)
def update_like_count_on_delete(sender, instance, **kwargs):
    """Cập nhật like_count khi xóa like"""
    Post.objects.filter(id=instance.post.id).update(like_count=F('like_count') - 1)
    cache.delete(f"custom:related_posts_{instance.post.id}_4")

@receiver(m2m_changed, sender=Post.categories.through)
def update_category_post_count(sender, instance, action, pk_set, **kwargs):
    """Cập nhật post_count của category"""
    if action in ['post_add', 'post_remove'] and pk_set:
        for category_id in pk_set:
            try:
                category = BlogCategory.objects.get(id=category_id)
                category.post_count = category.posts.published().count()
                category.save(update_fields=['post_count'])
            except BlogCategory.DoesNotExist: pass
        
        # Xóa cache featured categories
        BlogCategory.invalidate_model_cache()
@receiver(post_save, sender='blog.Comment')
def update_comment_count_on_save(sender, instance, created, **kwargs):
    if created and instance.is_approved:
        if instance.post: 
            Post.objects.filter(id=instance.post_id).update(comment_count=F('comment_count') + 1)

@receiver(post_delete, sender='blog.Comment')
def update_comment_count_on_delete(sender, instance, **kwargs):
    if instance.is_approved:
        Post.objects.filter(id=instance.post_id).update(comment_count=F('comment_count') - 1)

@receiver(m2m_changed, sender=Post.tags.through)
def update_tag_usage_count(sender, instance, action, pk_set, **kwargs):
    """Cập nhật usage_count của tag"""
    if action in ['post_add', 'post_remove'] and pk_set:
        for tag_id in pk_set:
            try:
                tag = BlogTag.objects.get(id=tag_id)
                tag.usage_count = tag.posts.published().count()
                tag.save(update_fields=['usage_count'])
            except BlogTag.DoesNotExist: pass
        
        # Xóa cache trending tags
        BlogTag.invalidate_model_cache()
        
        # Xóa cache related posts
        if isinstance(instance, Post):
            cache.delete(f"custom:related_posts_{instance.id}_4")

@receiver(post_save, sender=Post)
def invalidate_post_caches(sender, instance, **kwargs):
    """Xóa cache khi post được cập nhật"""
    # Xóa cache popular và recent posts
    cache.delete_many([
        f"custom:popular_posts_7_5",
        f"custom:recent_posts_5",
        f"custom:related_posts_{instance.id}_4"
    ])
    

# --- COMMENT & INTERACTION MODELS ---
class CommentQuerySet(models.QuerySet):
    """Custom QuerySet cho Comment với tối ưu"""
    def approved(self): return self.filter(is_approved=True)
    def pending(self): return self.filter(is_approved=False)
    def top_level(self): return self.filter(parent__isnull=True)
    def replies(self): return self.filter(parent__isnull=False)
    def with_author(self): return self.select_related('author')
    def with_replies(self): return self.prefetch_related('replies')

class CommentManager(models.Manager):
    def get_queryset(self): return CommentQuerySet(self.model, using=self._db)
    def approved(self): return self.get_queryset().approved()
    def get_thread(self, post_id):
        """Lấy comment thread với optimal prefetch"""
        return self.filter(post_id=post_id).select_related('author', 'parent').prefetch_related(
            Prefetch('replies', queryset=self.select_related('author').filter(is_approved=True))
        )

class Comment(SoftDeleteModel):
    """Model cho comment bài viết với threading và moderation được tối ưu"""
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='comments', db_index=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='authored_community_comments', db_index=True)
    content = models.TextField(validators=[MinLengthValidator(5)], verbose_name="Nội dung")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies', db_index=True)
    is_approved = models.BooleanField(default=True, verbose_name="Đã duyệt", db_index=True)
    is_pinned = models.BooleanField(default=False, verbose_name="Được ghim")
    likes_count = models.PositiveIntegerField(default=0, verbose_name="Lượt thích", db_index=True)
    depth = models.PositiveSmallIntegerField(default=0, editable=False, db_index=True)
    thread_id = models.UUIDField(null=True, blank=True, db_index=True)  # Denormalized thread root
    
    objects = CommentManager()
    
    class Meta:
        verbose_name = "Bình luận"
        verbose_name_plural = "Bình luận"
        ordering = ['-is_pinned', '-created_at']
        indexes = [
            models.Index(fields=['post', 'is_approved', 'parent']),
            models.Index(fields=['author', 'created_at']),
            models.Index(fields=['thread_id', 'depth']),
            models.Index(fields=['likes_count']),
        ]

    def __str__(self): return f'{self.author.username} - {self.post.title[:50]}...'

    def get_absolute_url(self):
        return reverse('blog:post_detail', kwargs={'slug': self.post.slug}) + f'#comment-{self.id}'

    def save(self, *args, **kwargs):
        if self.parent:
            self.depth = self.parent.depth + 1
            self.thread_id = self.parent.thread_id or self.parent.id
        else:
            self.depth = 0
            # Do not unconditionally set thread_id to None
            
        super().save(*args, **kwargs)
        if self.thread_id is None and self.id:
            self.thread_id = self.id
            self.save(update_fields=['thread_id'])

    @property
    def can_reply(self): return self.depth < 3

class CommentLike(TimestampedModel):
    """Like cho comment với tối ưu"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comment_likes')
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='likes')
    
    class Meta:
        unique_together = ['user', 'comment']
        verbose_name = "Thích bình luận"
        indexes = [
            models.Index(fields=['comment', 'user']),
            models.Index(fields=['user', 'created_at']),
        ]

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            Comment.objects.filter(id=self.comment_id).update(likes_count=F('likes_count') + 1)

    def delete(self, *args, **kwargs):
        comment_id = self.comment_id
        super().delete(*args, **kwargs)
        Comment.objects.filter(id=comment_id).update(likes_count=F('likes_count') - 1)


class Report(TimestampedModel):
    """Model báo cáo nội dung vi phạm"""
    REASON_CHOICES = [
        ('spam', 'Spam'), ('offensive', 'Nội dung xúc phạm'),
        ('inappropriate', 'Không phù hợp'), ('copyright', 'Vi phạm bản quyền'),
        ('other', 'Khác')
    ]
    STATUS_CHOICES = [('pending', 'Chờ xử lý'), ('reviewed', 'Đã xử lý')]

    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports')
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True)
    moderator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='handled_reports')
    moderator_notes = models.TextField(blank=True)

    # Generic Foreign Key to link to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=36)
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        verbose_name = "Báo cáo"
        verbose_name_plural = "Báo cáo"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Report by {self.reporter.username} on {self.content_object}"

# ================== SIGNALS ==================

@receiver(post_save, sender=Report)
def increment_report_count(sender, instance, created, **kwargs):
    """Tăng report_count trên content object khi có report mới"""
    if created:
        content_object = instance.content_object
        if hasattr(content_object, 'report_count'):
            content_object.report_count = F('report_count') + 1
            content_object.save(update_fields=['report_count'])

