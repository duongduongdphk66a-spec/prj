# File: analytics/tests.py
# ==============================================================================
# Test cases cho Analytics App — Models, Stats, Recommendations
# ==============================================================================

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
from decimal import Decimal

from analytics.models import (
    UserReadingStats, BookAnalytics, BusAnalytics,
    UserActivity, BookRecommendation, DailyStats
)
from inventory.models import Book, Category, LibraryBus

User = get_user_model()


class UserReadingStatsTest(TestCase):
    """Test UserReadingStats model và methods"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='statsuser', password='pass123'
        )
        self.stats = UserReadingStats.objects.get(user=self.user)

    def test_auto_created_on_user_creation(self):
        """UserReadingStats phải được tự động tạo khi tạo User"""
        self.assertIsNotNone(self.stats)
        self.assertEqual(self.stats.member_level, 'bronze')

    def test_completion_rate_no_borrows(self):
        """completion_rate = 100% khi chưa mượn sách nào"""
        self.assertEqual(self.stats.completion_rate, 100)

    def test_completion_rate_with_borrows(self):
        """completion_rate tính đúng tỷ lệ trả/mượn"""
        self.stats.total_books_borrowed = 10
        self.stats.total_books_returned = 8
        self.stats.save()
        self.assertEqual(self.stats.completion_rate, 80.0)

    def test_reading_velocity_zero_when_no_data(self):
        """reading_velocity = 0 khi chưa có dữ liệu"""
        self.assertEqual(self.stats.reading_velocity, 0)

    def test_reading_velocity_calculation(self):
        """reading_velocity tính đúng trang/ngày"""
        self.stats.total_pages_read = 1000
        self.stats.reading_streak_days = 50
        self.stats.save()
        self.assertEqual(self.stats.reading_velocity, 20.0)

    def test_update_level_bronze_to_silver(self):
        """update_level phải cập nhật từ bronze lên silver khi đạt 200 điểm"""
        self.stats.reputation_score = 250
        self.stats.save()
        changed = self.stats.update_level()
        self.assertTrue(changed)
        self.assertEqual(self.stats.member_level, 'silver')

    def test_update_level_to_gold(self):
        """update_level phải cập nhật lên gold khi đạt 400 điểm"""
        self.stats.reputation_score = 450
        self.stats.save()
        self.stats.update_level()
        self.assertEqual(self.stats.member_level, 'gold')

    def test_update_level_to_diamond(self):
        """update_level phải cập nhật lên diamond khi đạt 800 điểm"""
        self.stats.reputation_score = 850
        self.stats.save()
        self.stats.update_level()
        self.assertEqual(self.stats.member_level, 'diamond')

    def test_update_level_no_change(self):
        """update_level trả về False khi level không đổi"""
        self.stats.reputation_score = 50  # Vẫn bronze
        self.stats.save()
        changed = self.stats.update_level()
        self.assertFalse(changed)

    def test_add_reputation_capped_at_1000(self):
        """add_reputation không vượt quá 1000"""
        self.stats.reputation_score = 990
        self.stats.save()
        self.stats.add_reputation(50, reason='Test bonus')
        self.stats.refresh_from_db()
        self.assertEqual(self.stats.reputation_score, 1000)

    def test_add_reputation_creates_activity(self):
        """add_reputation phải tạo UserActivity"""
        self.stats.add_reputation(10, reason='Test')
        activity = UserActivity.objects.filter(
            user=self.user, activity_type='reputation_gained'
        ).first()
        self.assertIsNotNone(activity)
        self.assertEqual(activity.points, 10)

    def test_str_representation(self):
        """__str__ phải chứa username và level"""
        result = str(self.stats)
        self.assertIn(self.user.username, result)


class BookAnalyticsTest(TestCase):
    """Test BookAnalytics model"""

    def setUp(self):
        self.category = Category.objects.create(name='Analytics Cat')
        self.bus = LibraryBus.objects.create(
            name='Analytics Bus', license_plate='29A-ANLY', capacity=100
        )
        self.book = Book.objects.create(
            title='Analytics Book', author='Author X',
            publication_year=2023, page_count=300,
            category=self.category, location=self.bus,
            status='available'
        )
        self.analytics, _ = BookAnalytics.objects.get_or_create(book=self.book)

    def test_calculate_popularity_zero_stats(self):
        """popularity_score phải = 0 khi tất cả stats = 0"""
        self.analytics.calculate_popularity()
        self.assertEqual(float(self.analytics.popularity_score), 0.0)

    def test_calculate_popularity_with_borrows(self):
        """popularity_score phải > 0 khi có borrows"""
        self.analytics.total_borrows = 20
        self.analytics.average_rating = Decimal('4.5')
        self.analytics.save()
        self.analytics.calculate_popularity()
        self.assertGreater(float(self.analytics.popularity_score), 0)

    def test_calculate_popularity_recency_bonus(self):
        """Sách mượn gần đây phải có recency bonus"""
        self.analytics.total_borrows = 10
        self.analytics.last_borrowed = timezone.now()
        self.analytics.save()

        self.analytics.calculate_popularity()
        score_with_bonus = float(self.analytics.popularity_score)

        # So sánh với không có bonus
        self.analytics.last_borrowed = timezone.now() - timedelta(days=60)
        self.analytics.save()
        self.analytics.calculate_popularity()
        score_without_bonus = float(self.analytics.popularity_score)

        self.assertGreater(score_with_bonus, score_without_bonus)


class BusAnalyticsTest(TestCase):
    """Test BusAnalytics model"""

    def setUp(self):
        self.bus = LibraryBus.objects.create(
            name='Bus Analytics Test', license_plate='29A-BUST', capacity=100
        )
        self.analytics, _ = BusAnalytics.objects.get_or_create(bus=self.bus)

    def test_efficiency_zero_when_no_visits(self):
        """efficiency_score = 0 khi không có visits"""
        self.analytics.calculate_efficiency()
        self.assertEqual(float(self.analytics.efficiency_score), 0)

    def test_efficiency_calculation(self):
        """efficiency_score tính đúng borrow_rate"""
        self.analytics.total_visits = 100
        self.analytics.total_borrows = 75
        self.analytics.save()
        self.analytics.calculate_efficiency()
        self.assertEqual(float(self.analytics.efficiency_score), 75.0)

    def test_efficiency_capped_at_100(self):
        """efficiency_score không vượt quá 100"""
        self.analytics.total_visits = 10
        self.analytics.total_borrows = 200
        self.analytics.save()
        self.analytics.calculate_efficiency()
        self.assertLessEqual(float(self.analytics.efficiency_score), 100)


class BookRecommendationTest(TestCase):
    """Test BookRecommendation model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='recuser', password='pass123'
        )
        self.category = Category.objects.create(name='Rec Cat')
        self.bus = LibraryBus.objects.create(
            name='Rec Bus', license_plate='29A-RECC', capacity=100
        )
        self.book = Book.objects.create(
            title='Rec Book', author='Rec Author',
            publication_year=2023, page_count=200,
            category=self.category, location=self.bus,
            status='available'
        )
        self.recommendation = BookRecommendation.objects.create(
            user=self.user, book=self.book,
            algorithm_type='popular', score=Decimal('0.85')
        )

    def test_mark_clicked(self):
        """mark_clicked phải set is_clicked=True và clicked_at"""
        self.recommendation.mark_clicked()
        self.recommendation.refresh_from_db()
        self.assertTrue(self.recommendation.is_clicked)
        self.assertIsNotNone(self.recommendation.clicked_at)

    def test_mark_clicked_idempotent(self):
        """Gọi mark_clicked lần 2 không thay đổi clicked_at"""
        self.recommendation.mark_clicked()
        first_click = self.recommendation.clicked_at
        self.recommendation.mark_clicked()
        self.assertEqual(self.recommendation.clicked_at, first_click)

    def test_mark_borrowed(self):
        """mark_borrowed phải set is_borrowed=True và borrowed_at"""
        self.recommendation.mark_borrowed()
        self.recommendation.refresh_from_db()
        self.assertTrue(self.recommendation.is_borrowed)
        self.assertIsNotNone(self.recommendation.borrowed_at)


class DailyStatsTest(TestCase):
    """Test DailyStats model"""

    def test_generate_daily_stats(self):
        """generate_daily_stats phải tạo record cho ngày chỉ định"""
        stats = DailyStats.generate_daily_stats(date=timezone.now().date())
        self.assertIsNotNone(stats)
        self.assertEqual(stats.date, timezone.now().date())

    def test_generate_daily_stats_idempotent(self):
        """Gọi generate_daily_stats 2 lần cho cùng ngày chỉ update, không tạo mới"""
        today = timezone.now().date()
        stats1 = DailyStats.generate_daily_stats(date=today)
        stats2 = DailyStats.generate_daily_stats(date=today)
        self.assertEqual(stats1.pk, stats2.pk)
        self.assertEqual(DailyStats.objects.filter(date=today).count(), 1)

    def tearDown(self):
        cache.clear()
