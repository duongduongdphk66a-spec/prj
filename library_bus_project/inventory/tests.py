# File: inventory/tests.py
# ==============================================================================
# Test cases cho Inventory App — Models, QuerySets, Views
# ==============================================================================

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone

from inventory.models import (
    Book, Category, LibraryBus, BookStatusHistory,
    BusRoute, InventoryAlert, BookDonation, BookRating
)

User = get_user_model()


class LibraryBusModelTest(TestCase):
    """Test LibraryBus model"""

    def setUp(self):
        self.bus = LibraryBus.objects.create(
            name='Bus Test', license_plate='29A-12345', capacity=100
        )
        self.category = Category.objects.create(name='Khoa Học')

    def test_bus_str_representation(self):
        """__str__ phải chứa tên và biển số"""
        result = str(self.bus)
        self.assertIn('Bus Test', result)
        self.assertIn('29A-12345', result)

    def test_bus_book_count_empty(self):
        """Bus mới tạo phải có book count = 0"""
        self.assertEqual(self.bus.current_book_count, 0)

    def test_bus_capacity_usage_zero(self):
        """Bus trống phải có capacity usage = 0"""
        self.assertEqual(self.bus.capacity_usage_percentage, 0)

    def test_bus_book_count_with_available_books(self):
        """current_book_count chỉ đếm sách available"""
        Book.objects.create(
            title='Available Book', author='Author',
            publication_year=2023, page_count=200,
            category=self.category, location=self.bus, status='available'
        )
        Book.objects.create(
            title='Maintenance Book', author='Author',
            publication_year=2023, page_count=200,
            category=self.category, location=self.bus, status='maintenance'
        )
        self.bus.invalidate_cache()
        self.assertEqual(self.bus.current_book_count, 1)

    def test_bus_capacity_usage_percentage(self):
        """capacity_usage_percentage tính đúng phần trăm"""
        Book.objects.create(
            title='Book 1', author='Author',
            publication_year=2023, page_count=200,
            category=self.category, location=self.bus, status='available'
        )
        self.bus.invalidate_cache()
        # 1/100 = 1%
        self.assertEqual(self.bus.capacity_usage_percentage, 1.0)

    def test_bus_invalidate_cache(self):
        """invalidate_cache phải xóa cache entries"""
        cache_key = self.bus.CACHE_KEY_BOOK_COUNT.format(self.bus.id)
        cache.set(cache_key, 999)
        self.bus.invalidate_cache()
        self.assertIsNone(cache.get(cache_key))

    def tearDown(self):
        cache.clear()


class CategoryModelTest(TestCase):
    """Test Category model"""

    def setUp(self):
        self.category = Category.objects.create(name='Văn Học')

    def test_auto_slug_generation(self):
        """Category phải tự động tạo slug từ name"""
        self.assertIsNotNone(self.category.slug)
        self.assertNotEqual(self.category.slug, '')

    def test_str_representation(self):
        """__str__ phải trả về tên category"""
        self.assertEqual(str(self.category), 'Văn Học')

    def test_subcategory(self):
        """Category con phải liên kết đúng với category cha"""
        child = Category.objects.create(name='Tiểu Thuyết', parent=self.category)
        self.assertEqual(child.parent, self.category)
        self.assertIn(child, self.category.subcategories.all())

    def test_update_book_count(self):
        """update_book_count phải cập nhật _book_count chính xác"""
        bus = LibraryBus.objects.create(
            name='Count Bus', license_plate='29A-COUNT', capacity=100
        )
        Book.objects.create(
            title='Count Book', author='Author',
            publication_year=2023, page_count=200,
            category=self.category, location=bus, status='available'
        )
        self.category.update_book_count()
        self.category.refresh_from_db()
        self.assertEqual(self.category._book_count, 1)


class BookModelTest(TestCase):
    """Test Book model"""

    def setUp(self):
        self.category = Category.objects.create(name='Test Cat')
        self.bus = LibraryBus.objects.create(
            name='Test Bus', license_plate='29A-BOOK', capacity=100
        )
        self.book = Book.objects.create(
            title='Test Book', author='Test Author',
            publisher='Test Publisher',
            publication_year=2023, page_count=300,
            category=self.category, location=self.bus,
            status='available'
        )

    def test_is_available_property(self):
        """is_available phải trả về True khi status = 'available'"""
        self.assertTrue(self.book.is_available)

    def test_is_not_available_when_checked_out(self):
        """is_available phải trả về False khi status != 'available'"""
        self.book.status = 'checked_out'
        self.book.save()
        self.assertFalse(self.book.is_available)

    def test_change_status_creates_history(self):
        """change_status phải tạo BookStatusHistory record"""
        user = User.objects.create_user(username='statususer', password='pass')
        self.book.change_status('checked_out', user=user)
        self.assertEqual(self.book.status, 'checked_out')
        history = BookStatusHistory.objects.filter(book=self.book)
        self.assertEqual(history.count(), 1)
        self.assertEqual(history.first().from_status, 'available')
        self.assertEqual(history.first().to_status, 'checked_out')

    def test_change_status_same_no_history(self):
        """change_status với cùng status không tạo history"""
        self.book.change_status('available')
        history = BookStatusHistory.objects.filter(book=self.book)
        self.assertEqual(history.count(), 0)

    def test_calculate_popularity_score(self):
        """calculate_popularity_score phải trả về giá trị hợp lệ"""
        self.book._average_rating = 4.0
        self.book._total_borrows = 50
        score = self.book.calculate_popularity_score()
        self.assertGreater(score, 0)

    def test_str_representation(self):
        """__str__ phải chứa title và author"""
        result = str(self.book)
        self.assertIn('Test Book', result)
        self.assertIn('Test Author', result)


class BookQuerySetTest(TestCase):
    """Test BookQuerySet custom methods"""

    def setUp(self):
        self.category = Category.objects.create(name='QS Cat')
        self.bus = LibraryBus.objects.create(
            name='QS Bus', license_plate='29A-QSET', capacity=100
        )
        self.book1 = Book.objects.create(
            title='Django Tutorial', author='John Doe',
            publisher='Pub A',
            publication_year=2023, page_count=400,
            category=self.category, location=self.bus,
            status='available'
        )
        self.book2 = Book.objects.create(
            title='Python Basics', author='Jane Smith',
            publisher='Pub B',
            publication_year=2022, page_count=250,
            category=self.category, location=self.bus,
            status='checked_out'
        )

    def test_available_filter(self):
        """available() chỉ trả về sách có status='available'"""
        available = Book.objects.available()
        self.assertIn(self.book1, available)
        self.assertNotIn(self.book2, available)

    def test_search_by_title(self):
        """search() tìm theo title"""
        results = Book.objects.get_queryset().search('Django')
        self.assertIn(self.book1, results)
        self.assertNotIn(self.book2, results)

    def test_search_by_author(self):
        """search() tìm theo author"""
        results = Book.objects.get_queryset().search('Jane')
        self.assertIn(self.book2, results)

    def test_search_empty_returns_all(self):
        """search() với chuỗi rỗng trả về tất cả"""
        results = Book.objects.get_queryset().search('')
        self.assertEqual(results.count(), Book.objects.count())

    def test_by_category_filter(self):
        """by_category() filter đúng theo category"""
        results = Book.objects.get_queryset().by_category(self.category)
        self.assertEqual(results.count(), 2)

    def test_by_location_filter(self):
        """by_location() filter đúng theo bus location"""
        results = Book.objects.get_queryset().by_location(self.bus)
        self.assertEqual(results.count(), 2)

    def test_recent_filter(self):
        """recent() trả về sách tạo trong N ngày gần đây"""
        results = Book.objects.get_queryset().recent(days=1)
        self.assertEqual(results.count(), 2)


class BookDonationTest(TestCase):
    """Test BookDonation model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='donateuser', password='pass123'
        )
        self.donation = BookDonation.objects.create(
            user=self.user,
            book_title='Quyên góp Sách',
            author='Tác giả quyên góp',
            description='Sách tình trạng tốt',
            status='pending'
        )

    def test_default_status_pending(self):
        """Donation mới phải có status = 'pending'"""
        self.assertEqual(self.donation.status, 'pending')

    def test_str_representation(self):
        """__str__ phải chứa tên sách và status"""
        result = str(self.donation)
        self.assertIn('Quyên góp Sách', result)


class BookRatingTest(TestCase):
    """Test BookRating model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='rateuser', password='pass123'
        )
        self.category = Category.objects.create(name='Rate Cat')
        self.bus = LibraryBus.objects.create(
            name='Rate Bus', license_plate='29A-RATE', capacity=100
        )
        self.book = Book.objects.create(
            title='Rate Book', author='Rate Author',
            publication_year=2023, page_count=200,
            category=self.category, location=self.bus,
            status='available'
        )

    def test_create_rating(self):
        """Tạo rating thành công"""
        rating = BookRating.objects.create(
            book=self.book, user=self.user, rating=5
        )
        self.assertEqual(rating.rating, 5)

    def test_unique_constraint_book_user(self):
        """Mỗi user chỉ rate 1 lần cho mỗi sách"""
        from django.db import IntegrityError
        BookRating.objects.create(book=self.book, user=self.user, rating=4)
        with self.assertRaises(IntegrityError):
            BookRating.objects.create(book=self.book, user=self.user, rating=3)


class InventoryViewTest(TestCase):
    """Test inventory views"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='invviewuser', password='pass123'
        )
        self.category = Category.objects.create(name='View Cat')
        self.bus = LibraryBus.objects.create(
            name='View Bus', license_plate='29A-VIEW', capacity=100
        )
        self.book = Book.objects.create(
            title='View Book', author='View Author',
            publication_year=2023, page_count=200,
            category=self.category, location=self.bus,
            status='available'
        )

    def test_book_list_page(self):
        """Trang danh sách sách phải trả về 200"""
        self.client.login(username='invviewuser', password='pass123')
        response = self.client.get(reverse('inventory:book_list'))
        self.assertEqual(response.status_code, 200)

    def test_book_detail_page(self):
        """Trang chi tiết sách phải trả về 200"""
        self.client.login(username='invviewuser', password='pass123')
        response = self.client.get(
            reverse('inventory:book_detail', kwargs={'pk': self.book.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_bus_list_page(self):
        """Trang danh sách xe bus phải trả về 200"""
        self.client.login(username='invviewuser', password='pass123')
        response = self.client.get(reverse('inventory:bus_list'))
        self.assertEqual(response.status_code, 200)

    def test_category_list_page(self):
        """Trang danh sách categories phải trả về 200"""
        self.user.is_staff = True
        self.user.save()
        self.client.login(username='invviewuser', password='pass123')
        response = self.client.get(reverse('inventory:category_list'))
        self.assertEqual(response.status_code, 200)
