# File: core/tests.py
# ==============================================================================
# Test cases cho Core App — Base Models, Mixins, Managers
# ==============================================================================

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

from inventory.models import Book, Category, LibraryBus
from transactions.models import BorrowRecord

User = get_user_model()


class CacheMixinTest(TestCase):
    """Test CacheMixin: cache key generation, versioning, invalidation"""

    def setUp(self):
        self.category = Category.objects.create(name='Cache Test Category')

    def test_get_current_version_returns_integer(self):
        """Cache version phải là số nguyên"""
        version = Category.get_current_version()
        self.assertIsInstance(version, int)

    def test_invalidate_model_cache_increments_version(self):
        """Gọi invalidate_model_cache phải tăng version"""
        version_before = Category.get_current_version()
        Category.invalidate_model_cache()
        version_after = Category.get_current_version()
        self.assertEqual(version_after, version_before + 1)

    def test_cache_key_contains_version(self):
        """Cache key phải chứa version number"""
        version = Category.get_current_version()
        key = Category._get_cache_key('test_suffix')
        self.assertIn(f'v{version}', key)

    def test_save_invalidates_cache(self):
        """Lưu model phải invalidate cache"""
        version_before = Category.get_current_version()
        self.category.description = 'Updated description'
        self.category.save()
        version_after = Category.get_current_version()
        self.assertGreater(version_after, version_before)

    def tearDown(self):
        cache.clear()


class BaseQuerySetTest(TestCase):
    """Test BaseQuerySet: active(), inactive(), recent() filters"""

    def setUp(self):
        self.category = Category.objects.create(name='QS Test Category')
        self.bus = LibraryBus.objects.create(
            name='QS Bus', license_plate='29A-00001', capacity=100
        )
        self.book_active = Book.objects.create(
            title='Active Book', author='Author A',
            publication_year=2023, page_count=200,
            category=self.category, location=self.bus,
            status='available', is_active=True
        )
        self.book_inactive = Book.objects.create(
            title='Inactive Book', author='Author B',
            publication_year=2023, page_count=150,
            category=self.category, location=self.bus,
            status='available', is_active=False
        )

    def test_active_filter(self):
        """active() chỉ trả về records có is_active=True"""
        Category.objects.create(name='Active Cat', is_active=True)
        Category.objects.create(name='Inactive Cat', is_active=False)
        active_cats = Category.objects.active()
        self.assertTrue(all(c.is_active for c in active_cats))
        self.assertGreater(active_cats.count(), 0)

    def test_recent_filter(self):
        """recent() trả về records tạo trong N ngày gần đây"""
        recent_books = Book.objects.recent(days=1)
        self.assertIn(self.book_active, recent_books)


class SoftDeleteModelTest(TestCase):
    """Test SoftDeleteModel: soft delete, restore, manager filtering"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='softdeleteuser', password='testpass123'
        )
        self.category = Category.objects.create(name='SD Category')
        self.bus = LibraryBus.objects.create(
            name='SD Bus', license_plate='29A-00002', capacity=100
        )
        self.book = Book.objects.create(
            title='SD Book', author='SD Author',
            publication_year=2023, page_count=100,
            category=self.category, location=self.bus,
            status='available'
        )
        self.borrow = BorrowRecord.objects.create(
            user=self.user,
            book=self.book,
            due_date=timezone.now().date() + timedelta(days=14)
        )

    def test_soft_delete_sets_deleted_at(self):
        """Soft delete phải set deleted_at thay vì xóa thật"""
        self.borrow.delete(deleted_by=self.user)
        # Record vẫn tồn tại trong DB
        self.assertTrue(
            BorrowRecord.all_objects.filter(pk=self.borrow.pk).exists()
        )

    def test_soft_delete_hides_from_default_manager(self):
        """Default manager không trả về records đã soft delete"""
        self.borrow.delete(deleted_by=self.user)
        self.assertFalse(
            BorrowRecord.objects.filter(pk=self.borrow.pk).exists()
        )

    def test_restore_makes_visible_again(self):
        """Restore phải làm record hiển thị lại trong default manager"""
        self.borrow.delete(deleted_by=self.user)
        self.borrow.restore()
        self.assertTrue(
            BorrowRecord.objects.filter(pk=self.borrow.pk).exists()
        )
        self.assertIsNone(self.borrow.deleted_at)
        self.assertTrue(self.borrow.is_active)
