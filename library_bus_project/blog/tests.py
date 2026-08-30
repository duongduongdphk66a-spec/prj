# File: blog/tests.py
# ==============================================================================
# Test cases cho Blog App — Models, Signals, QuerySets, Views
# ==============================================================================

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from django.db import IntegrityError
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from blog.models import (
    Post, BlogCategory, BlogTag, Comment, CommentLike,
    PostLike, PostRating, PostView, Newsletter
)
from inventory.models import Book, Category as InvCategory, LibraryBus

User = get_user_model()


class BlogCategoryModelTest(TestCase):
    """Test BlogCategory model"""

    def setUp(self):
        self.category = BlogCategory.objects.create(
            name='Công Nghệ', description='Bài viết về công nghệ'
        )

    def test_auto_slug_generation(self):
        """BlogCategory phải tự tạo slug từ name"""
        self.assertIsNotNone(self.category.slug)
        self.assertNotEqual(self.category.slug, '')

    def test_str_representation(self):
        """__str__ phải trả về tên category"""
        self.assertEqual(str(self.category), 'Công Nghệ')

    def test_get_absolute_url(self):
        """get_absolute_url phải trả về URL hợp lệ"""
        url = self.category.get_absolute_url()
        self.assertIn(self.category.slug, url)

    def test_parent_child_relationship(self):
        """Category con phải liên kết đúng với cha"""
        child = BlogCategory.objects.create(
            name='AI/ML', parent=self.category
        )
        self.assertEqual(child.parent, self.category)
        self.assertIn(child, self.category.children.all())


class BlogTagModelTest(TestCase):
    """Test BlogTag model"""

    def setUp(self):
        self.tag = BlogTag.objects.create(name='Python')

    def test_auto_slug_generation(self):
        """BlogTag phải tự tạo slug"""
        self.assertIsNotNone(self.tag.slug)

    def test_str_representation(self):
        """__str__ phải trả về tên tag"""
        self.assertEqual(str(self.tag), 'Python')


class PostModelTest(TestCase):
    """Test Post model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='blogger', password='pass123'
        )
        self.category = BlogCategory.objects.create(name='Tech')
        self.post = Post.objects.create(
            title='Test Post Title For Blog',
            content='This is the test content for the blog post. ' * 20,
            author=self.user,
            status='published'
        )
        self.post.categories.add(self.category)

    def test_auto_slug_generation(self):
        """Post phải tự tạo slug từ title"""
        self.assertIsNotNone(self.post.slug)
        self.assertNotEqual(self.post.slug, '')

    def test_auto_excerpt_generation(self):
        """Post phải tự tạo excerpt từ content nếu chưa có"""
        self.assertIsNotNone(self.post.excerpt)
        self.assertNotEqual(self.post.excerpt, '')

    def test_calculate_reading_time(self):
        """calculate_reading_time phải trả về giá trị >= 1"""
        reading_time = self.post.calculate_reading_time()
        self.assertGreaterEqual(reading_time, 1)

    def test_is_published_property(self):
        """is_published = True khi status='published' và có publish_date"""
        self.assertTrue(self.post.is_published)

    def test_is_not_published_when_draft(self):
        """is_published = False khi status='draft'"""
        self.post.status = 'draft'
        self.post.save()
        self.assertFalse(self.post.is_published)

    def test_engagement_score_calculation(self):
        """engagement_score phải tính đúng từ views, likes, comments"""
        self.post.view_count = 100
        self.post.like_count = 10
        self.post.comment_count = 5
        # (100 × 0.1) + (10 × 0.3) + (5 × 0.6) = 10 + 3 + 3 = 16
        self.assertEqual(self.post.engagement_score, 16.0)

    def test_increment_view_count(self):
        """increment_view_count phải tăng view_count lên 1"""
        initial = self.post.view_count
        self.post.increment_view_count()
        self.post.refresh_from_db()
        self.assertEqual(self.post.view_count, initial + 1)

    def test_increment_view_count_cache_lock(self):
        """Gọi increment_view_count liên tục trong 30s chỉ tăng 1 lần"""
        initial = self.post.view_count
        self.post.increment_view_count()
        self.post.increment_view_count()
        self.post.refresh_from_db()
        self.assertEqual(self.post.view_count, initial + 1)

    def test_published_date_auto_set(self):
        """publish_date tự set khi status='published'"""
        new_post = Post.objects.create(
            title='Auto Publish Date Test Post',
            content='Content ' * 20,
            author=self.user,
            status='published'
        )
        self.assertIsNotNone(new_post.publish_date)

    def tearDown(self):
        cache.clear()


class PostQuerySetTest(TestCase):
    """Test custom BlogQuerySet"""

    def setUp(self):
        self.user = User.objects.create_user(username='qsuser', password='pass')
        self.published = Post.objects.create(
            title='Published Post QS Test',
            content='Content published ' * 10,
            author=self.user, status='published'
        )
        self.draft = Post.objects.create(
            title='Draft Post QS Test',
            content='Content draft ' * 10,
            author=self.user, status='draft'
        )

    def test_published_filter(self):
        """published() chỉ trả về posts đã publish"""
        published = Post.objects.published()
        self.assertIn(self.published, published)
        self.assertNotIn(self.draft, published)

    def test_draft_filter(self):
        """draft() chỉ trả về posts draft"""
        drafts = Post.objects.get_queryset().draft()
        self.assertIn(self.draft, drafts)
        self.assertNotIn(self.published, drafts)

    def test_search_by_title(self):
        """search() tìm theo title"""
        results = Post.objects.search('Published')
        self.assertIn(self.published, results)


class CommentModelTest(TestCase):
    """Test Comment model — threading và depth"""

    def setUp(self):
        self.user = User.objects.create_user(username='cmtuser', password='pass')
        self.post = Post.objects.create(
            title='Comment Test Post Title',
            content='Content ' * 10,
            author=self.user, status='published'
        )

    def test_top_level_comment_depth_zero(self):
        """Top-level comment phải có depth = 0"""
        comment = Comment.objects.create(
            post=self.post, author=self.user,
            content='Top level comment', is_approved=True
        )
        self.assertEqual(comment.depth, 0)

    def test_top_level_comment_thread_id_is_self(self):
        """Top-level comment phải có thread_id = self.id"""
        comment = Comment.objects.create(
            post=self.post, author=self.user,
            content='Thread test', is_approved=True
        )
        self.assertEqual(comment.thread_id, comment.id)

    def test_reply_depth_increments(self):
        """Reply phải có depth = parent.depth + 1"""
        parent = Comment.objects.create(
            post=self.post, author=self.user,
            content='Parent comment', is_approved=True
        )
        reply = Comment.objects.create(
            post=self.post, author=self.user,
            content='Reply comment', parent=parent, is_approved=True
        )
        self.assertEqual(reply.depth, 1)
        self.assertEqual(reply.thread_id, parent.id)

    def test_nested_reply_depth(self):
        """Reply cấp 2 phải có depth = 2"""
        parent = Comment.objects.create(
            post=self.post, author=self.user,
            content='Parent', is_approved=True
        )
        reply1 = Comment.objects.create(
            post=self.post, author=self.user,
            content='Reply L1', parent=parent, is_approved=True
        )
        reply2 = Comment.objects.create(
            post=self.post, author=self.user,
            content='Reply L2', parent=reply1, is_approved=True
        )
        self.assertEqual(reply2.depth, 2)
        self.assertEqual(reply2.thread_id, parent.id)

    def test_can_reply_max_depth(self):
        """can_reply = False khi depth >= 3"""
        c1 = Comment.objects.create(
            post=self.post, author=self.user,
            content='L0', is_approved=True
        )
        c2 = Comment.objects.create(
            post=self.post, author=self.user,
            content='L1', parent=c1, is_approved=True
        )
        c3 = Comment.objects.create(
            post=self.post, author=self.user,
            content='L2', parent=c2, is_approved=True
        )
        c4 = Comment.objects.create(
            post=self.post, author=self.user,
            content='L3', parent=c3, is_approved=True
        )
        self.assertTrue(c3.can_reply)   # depth=2, < 3
        self.assertFalse(c4.can_reply)  # depth=3, >= 3


class PostLikeSignalTest(TestCase):
    """Test PostLike signal cập nhật like_count"""

    def setUp(self):
        self.user = User.objects.create_user(username='likeuser', password='pass')
        self.post = Post.objects.create(
            title='Like Signal Test Post',
            content='Content ' * 10,
            author=self.user, status='published'
        )

    def test_like_increments_count(self):
        """Tạo PostLike phải tăng like_count"""
        PostLike.objects.create(post=self.post, user=self.user)
        self.post.refresh_from_db()
        self.assertEqual(self.post.like_count, 1)

    def test_delete_like_decrements_count(self):
        """Xóa PostLike phải giảm like_count"""
        like = PostLike.objects.create(post=self.post, user=self.user)
        like.delete()
        self.post.refresh_from_db()
        self.assertEqual(self.post.like_count, 0)

    def test_unique_like_per_user(self):
        """Mỗi user chỉ like 1 lần"""
        PostLike.objects.create(post=self.post, user=self.user)
        with self.assertRaises(IntegrityError):
            PostLike.objects.create(post=self.post, user=self.user)


class NewsletterModelTest(TestCase):
    """Test Newsletter model"""

    def test_create_newsletter_subscription(self):
        """Tạo subscription thành công"""
        newsletter = Newsletter.objects.create(
            email='test@example.com', frequency='weekly'
        )
        self.assertFalse(newsletter.is_confirmed)

    def test_unique_email(self):
        """Email phải unique"""
        Newsletter.objects.create(email='unique@example.com')
        with self.assertRaises(IntegrityError):
            Newsletter.objects.create(email='unique@example.com')


class BlogViewTest(TestCase):
    """Test blog views"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='blogviewuser', password='pass123'
        )
        self.category = BlogCategory.objects.create(name='View Cat')
        self.post = Post.objects.create(
            title='Blog View Test Post Title',
            content='Content for view testing ' * 20,
            author=self.user, status='published'
        )
        self.post.categories.add(self.category)

    def test_post_list_page(self):
        """Trang danh sách bài viết phải trả về 200"""
        response = self.client.get(reverse('blog:post_list'))
        self.assertEqual(response.status_code, 200)

    def test_post_detail_page(self):
        """Trang chi tiết bài viết phải trả về 200"""
        response = self.client.get(
            reverse('blog:post_detail', kwargs={'slug': self.post.slug})
        )
        self.assertEqual(response.status_code, 200)

    def test_search_page(self):
        """Trang tìm kiếm phải trả về 200"""
        response = self.client.get(reverse('blog:search'), {'q': 'test'})
        self.assertEqual(response.status_code, 200)

    def test_post_create_requires_login(self):
        """Trang tạo bài viết yêu cầu login"""
        response = self.client.get(reverse('blog:post_create'))
        self.assertEqual(response.status_code, 302)

    def test_category_detail_page(self):
        """Trang chi tiết chuyên mục phải trả về 200"""
        response = self.client.get(
            reverse('blog:category_detail', kwargs={'slug': self.category.slug})
        )
        self.assertEqual(response.status_code, 200)
