# analytics/tests.py
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta, datetime
from unittest.mock import patch, MagicMock
from decimal import Decimal
# from rangefilter.filter import DateRangeFilter, DateTimeRangeFilter
# Import models
from inventory.models import Book, LibraryBus
from transactions.models import BorrowRecord
from .models import (
    UserReadingStats, BookAnalytics, BusAnalytics, UserActivity,
    BookRecommendation, DailyStats, ArchivedUserActivity,
    get_user_stats_summary, get_book_stats_summary, get_system_health
)
# Import views
from .views import (
    DashboardView, AdminDashboardView, UserStatsView, UserActivitiesView,
    BookAnalyticsView, BookDetailAnalyticsView, LeaderboardView,
    RecommendationsView, BusAnalyticsView, ReportsView,
    track_book_view, track_recommendation_click, get_user_activities_json,
    get_analytics_summary_json, track_bus_visit, export_user_data
)
# Import tasks
from .tasks import (
    update_analytics_on_borrow_task, update_book_view_analytics,
    update_review_analytics, generate_daily_stats_task,
    update_user_streaks_task, cleanup_old_activities_task,
    recalculate_popularity_scores_task, generate_user_recommendations_task,
    update_bus_analytics_task, cache_warmup_task, invalidate_stale_cache_task
)
# Import admin
from .admin import (
    UserReadingStatsAdmin, BookAnalyticsAdmin, BusAnalyticsAdmin,
    UserActivityAdmin, BookRecommendationAdmin, DailyStatsAdmin,
    ArchivedUserActivityAdmin, AnalyticsAdminSite
)

# Mock models from other apps

class BaseAnalyticsTest(TestCase):
    pass


class AnalyticsModelsTest(BaseAnalyticsTest):
    def setUp(self):
        self.user1 = User.objects.create_user(username='testuser1', password='password1')
        self.user2 = User.objects.create_user(username='testuser2', password='password2')
        self.book1 = Book.objects.create(id=1, title='The Great Novel', author='Author A', publisher='Pub', publication_year=2020, page_count=100)
        self.book2 = Book.objects.create(id=2, title='Another Story', author='Author B', publisher='Pub', publication_year=2021, page_count=200)
        self.bus1 = LibraryBus.objects.create(id=1, name='Bus Alpha', license_plate='LP-1')
        self.bus2 = LibraryBus.objects.create(id=2, name='Bus Beta', license_plate='LP-2')

        # Clear cache before each test
        cache.clear()

    def test_user_reading_stats_creation(self):
        # UserReadingStats should be created automatically via signal
        stats = UserReadingStats.objects.get(user=self.user1)
        self.assertIsNotNone(stats)
        self.assertEqual(stats.total_books_borrowed, 0)
        self.assertEqual(stats.reputation_score, 100)
        self.assertEqual(stats.member_level, 'bronze')

    def test_user_reading_stats_properties(self):
        stats = UserReadingStats.objects.get(user=self.user1)
        stats.total_books_borrowed = 10
        stats.total_books_returned = 8
        stats.total_pages_read = 500
        stats.reading_streak_days = 5
        stats.save()

        self.assertEqual(stats.completion_rate, 80.0)
        self.assertEqual(stats.reading_velocity, 100.0) # 500 pages / 5 days

    def test_user_reading_stats_update_level(self):
        stats = UserReadingStats.objects.get(user=self.user1)
        stats.reputation_score = 250
        stats.save()
        stats.update_level()
        self.assertEqual(stats.member_level, 'silver')

        stats.reputation_score = 700
        stats.save()
        stats.update_level()
        self.assertEqual(stats.member_level, 'platinum')

    def test_user_reading_stats_add_reputation(self):
        stats = UserReadingStats.objects.get(user=self.user1)
        initial_score = stats.reputation_score
        stats.add_reputation(50, "Test reason")
        self.assertEqual(stats.reputation_score, initial_score + 50)
        self.assertTrue(UserActivity.objects.filter(user=self.user1, activity_type='reputation_gained').exists())

    def test_user_reading_stats_cached_methods(self):
        UserReadingStats.objects.get(user=self.user1).add_reputation(100)
        UserReadingStats.objects.get(user=self.user2).add_reputation(50)

        top_readers = UserReadingStats.get_top_readers(1)
        self.assertEqual(len(top_readers), 1)
        self.assertEqual(top_readers[0].user, self.user1)

        level_dist = UserReadingStats.get_level_distribution()
        self.assertGreater(len(level_dist), 0)
        self.assertIn({'member_level': 'bronze', 'count': 1}, level_dist)
        self.assertIn({'member_level': 'silver', 'count': 1}, level_dist)

    def test_book_analytics_creation(self):
        analytics, created = BookAnalytics.objects.get_or_create(book_id=self.book1.id)
        self.assertTrue(created)
        self.assertEqual(analytics.total_borrows, 0)

    def test_book_analytics_calculate_popularity(self):
        analytics, _ = BookAnalytics.objects.get_or_create(book_id=self.book1.id)
        analytics.total_borrows = 10
        analytics.total_views = 100
        analytics.average_rating = 4.5
        analytics.last_borrowed = timezone.now() - timedelta(days=10)
        analytics.save()
        analytics.calculate_popularity()
        # The exact score depends on the formula, just check it's non-zero
        self.assertGreater(analytics.popularity_score, 0)

    def test_book_analytics_cached_methods(self):
        BookAnalytics.objects.create(book_id=self.book1.id, popularity_score=Decimal('90.00'), total_borrows=50)
        BookAnalytics.objects.create(book_id=self.book2.id, popularity_score=Decimal('70.00'), total_borrows=30)
        
        # Mock the book objects for the values() call
        with patch('analytics.models.BookAnalytics.objects.active') as mock_active:
            mock_active.return_value.select_related.return_value.order_by.return_value.values.return_value = [
                {'book__id': self.book1.id, 'book__title': self.book1.title, 'book__author': self.book1.author, 'popularity_score': Decimal('90.00'), 'total_borrows': 50, 'average_rating': Decimal('4.00')},
                {'book__id': self.book2.id, 'book__title': self.book2.title, 'book__author': self.book2.author, 'popularity_score': Decimal('70.00'), 'total_borrows': 30, 'average_rating': Decimal('3.00')},
            ]
            popular_books = BookAnalytics.get_popular_books(1)
            self.assertEqual(len(popular_books), 1)
            self.assertEqual(popular_books[0]['book__id'], self.book1.id)

        BookAnalytics.objects.filter(book_id=self.book1.id).update(last_borrowed=timezone.now())
        with patch('analytics.models.BookAnalytics.objects.active') as mock_active:
            mock_active.return_value.filter.return_value.select_related.return_value.order_by.return_value.values.return_value = [
                {'book__id': self.book1.id, 'book__title': self.book1.title, 'book__author': self.book1.author, 'popularity_score': Decimal('90.00'), 'total_borrows': 50, 'last_borrowed': timezone.now()},
            ]
            trending_books = BookAnalytics.get_trending_books(7, 1)
            self.assertEqual(len(trending_books), 1)
            self.assertEqual(trending_books[0]['book__id'], self.book1.id)

    def test_bus_analytics_creation(self):
        analytics, created = BusAnalytics.objects.get_or_create(bus_id=self.bus1.id)
        self.assertTrue(created)
        self.assertEqual(analytics.total_visits, 0)

    def test_bus_analytics_calculate_efficiency(self):
        analytics, _ = BusAnalytics.objects.get_or_create(bus_id=self.bus1.id)
        analytics.total_visits = 100
        analytics.total_borrows = 50
        analytics.save()
        analytics.calculate_efficiency()
        self.assertEqual(analytics.efficiency_score, Decimal('50.00'))

    def test_bus_analytics_cached_methods(self):
        BusAnalytics.objects.create(bus_id=self.bus1.id, efficiency_score=Decimal('80.00'))
        BusAnalytics.objects.create(bus_id=self.bus2.id, efficiency_score=Decimal('60.00'))

        with patch('analytics.models.BusAnalytics.objects.active') as mock_active:
            mock_active.return_value.select_related.return_value.order_by.return_value.values.return_value = [
                {'bus__id': self.bus1.id, 'bus__name': self.bus1.name, 'bus__route': self.bus1.route, 'efficiency_score': Decimal('80.00'), 'total_visits': 100, 'total_borrows': 80},
            ]
            top_buses = BusAnalytics.get_top_performing_buses(1)
            self.assertEqual(len(top_buses), 1)
            self.assertEqual(top_buses[0]['bus__id'], self.bus1.id)

    def test_user_activity_creation(self):
        activity = UserActivity.objects.create(
            user=self.user1, activity_type='borrow', book=self.book1,
            description='Borrowed a book'
        )
        self.assertIsNotNone(activity.pk)
        self.assertEqual(activity.user, self.user1)

    def test_user_activity_cached_methods(self):
        UserActivity.objects.create(user=self.user1, activity_type='borrow', book=self.book1)
        UserActivity.objects.create(user=self.user2, activity_type='return', book=self.book2)

        recent_activities_all = UserActivity.get_recent_activities(limit=1)
        self.assertEqual(len(recent_activities_all), 1)

        recent_activities_user1 = UserActivity.get_recent_activities(user=self.user1, limit=1)
        self.assertEqual(len(recent_activities_user1), 1)
        self.assertEqual(recent_activities_user1[0].user, self.user1)

    def test_book_recommendation_creation(self):
        rec = BookRecommendation.objects.create(user=self.user1, book=self.book1, score=0.8)
        self.assertIsNotNone(rec.pk)
        self.assertEqual(rec.user, self.user1)

    def test_book_recommendation_mark_clicked_borrowed(self):
        rec = BookRecommendation.objects.create(user=self.user1, book=self.book1, score=0.8)
        self.assertFalse(rec.is_clicked)
        self.assertIsNone(rec.clicked_at)

        rec.mark_clicked()
        self.assertTrue(rec.is_clicked)
        self.assertIsNotNone(rec.clicked_at)

        rec.mark_borrowed()
        self.assertTrue(rec.is_borrowed)
        self.assertIsNotNone(rec.borrowed_at)

    def test_book_recommendation_generate_popular_recommendations(self):
        BookAnalytics.objects.create(book_id=self.book1.id, popularity_score=Decimal('90.00'))
        BookAnalytics.objects.create(book_id=self.book2.id, popularity_score=Decimal('70.00'))

        # Mock borrowed books for the user
        with patch.object(self.user1, 'borrow_records') as mock_borrow_records:
            mock_borrow_records.values_list.return_value = [] # User has not borrowed any books

            recs = BookRecommendation.generate_popular_recommendations(self.user1, limit=1)
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0].book, self.book1) # Should recommend the most popular

    def test_book_recommendation_get_user_recommendations(self):
        BookRecommendation.objects.create(user=self.user1, book=self.book1, score=0.9)
        BookRecommendation.objects.create(user=self.user1, book=self.book2, score=0.7)

        recs = BookRecommendation.get_user_recommendations(self.user1, limit=1)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].book, self.book1)

    def test_daily_stats_creation(self):
        today = timezone.now().date()
        stats = DailyStats.generate_daily_stats(today)
        self.assertIsNotNone(stats.pk)
        self.assertEqual(stats.date, today)
        self.assertEqual(stats.total_users, User.objects.count())

    def test_daily_stats_get_weekly_stats(self):
        today = timezone.now().date()
        DailyStats.generate_daily_stats(today)
        DailyStats.generate_daily_stats(today - timedelta(days=1))

        weekly_stats = DailyStats.get_weekly_stats(weeks=1)
        self.assertEqual(len(weekly_stats), 2) # Should include today and yesterday

    def test_archived_user_activity_soft_delete_restore(self):
        activity = UserActivity.objects.create(user=self.user1, activity_type='view_book', book=self.book1)
        activity_id = activity.id
        
        # Simulate soft delete (handled by cleanup_old_activities_task)
        # For direct testing, we can manually create an archived entry and delete the original
        ArchivedUserActivity.objects.create(
            user=activity.user,
            activity_type=activity.activity_type,
            book=activity.book,
            description=activity.description,
            original_created_at=activity.created_at,
            created_by=activity.created_by,
            modified_by=activity.modified_by
        )
        activity.delete() # Simulate deletion after archiving

        archived_activity = ArchivedUserActivity.objects.get(original_created_at=activity.created_at)
        self.assertIsNotNone(archived_activity.pk)
        self.assertTrue(archived_activity.is_deleted)

        archived_activity.restore()
        self.assertFalse(archived_activity.is_deleted)
        # Verify it's back in UserActivity (this requires a more complex mock or actual DB)
        # For now, just check the archived object's status

    def test_utility_functions_with_cache(self):
        # Ensure these functions use the CacheMixin and return data
        summary = get_user_stats_summary()
        self.assertIn('total_users', summary)

        book_summary = get_book_stats_summary()
        self.assertIn('total_books', book_summary)

        system_health = get_system_health()
        self.assertIn('cache_version', system_health)


class AnalyticsViewsTest(BaseAnalyticsTest):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='testuser', password='password')
        self.staff_user = User.objects.create_user(username='staffuser', password='password', is_staff=True)
        
        self.book1 = Book.objects.create(id=1, title='Test Book 1', author='Author A', publisher='Pub', publication_year=2020, page_count=100)
        self.book2 = Book.objects.create(id=2, title='Test Book 2', author='Author B', publisher='Pub', publication_year=2021, page_count=200)
        self.bus1 = LibraryBus.objects.create(id=1, name='Test Bus 1', license_plate='LP-3')

        # Create some initial data
        self.user_stats = UserReadingStats.objects.get(user=self.user)
        self.user_stats.total_books_borrowed = 5
        self.user_stats.total_books_returned = 3
        self.user_stats.save()

        self.book_analytics1, _ = BookAnalytics.objects.get_or_create(book_id=self.book1.id, defaults={'popularity_score': 80})
        self.book_analytics2, _ = BookAnalytics.objects.get_or_create(book_id=self.book2.id, defaults={'popularity_score': 60})

        UserActivity.objects.create(user=self.user, activity_type='borrow', book=self.book1)
        UserActivity.objects.create(user=self.user, activity_type='view_book', book=self.book2)

        BookRecommendation.objects.create(user=self.user, book=self.book1, score=0.9)
        DailyStats.generate_daily_stats(timezone.now().date())
        DailyStats.generate_daily_stats(timezone.now().date() - timedelta(days=1))

        BusAnalytics.objects.get_or_create(bus_id=self.bus1.id, defaults={'efficiency_score': 75})

    def test_dashboard_view(self):
        request = self.factory.get('/dashboard/')
        request.user = self.user
        response = DashboardView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('user_stats', response.context_data)
        self.assertIn('user_activities', response.context_data)
        self.assertIn('user_recommendations', response.context_data)

    def test_admin_dashboard_view(self):
        request = self.factory.get('/admin-dashboard/')
        request.user = self.staff_user
        response = AdminDashboardView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_users', response.context_data)
        self.assertIn('popular_books', response.context_data)

    def test_user_stats_view(self):
        request = self.factory.get('/user-stats/')
        request.user = self.user
        response = UserStatsView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('user_stats', response.context_data)
        self.assertIn('user_rank', response.context_data)

    def test_user_activities_view(self):
        request = self.factory.get('/user-activities/')
        request.user = self.user
        response = UserActivitiesView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('activities', response.context_data)
        self.assertIn('activities_stats', response.context_data)

    def test_book_analytics_view(self):
        request = self.factory.get('/book-analytics/')
        request.user = self.user # User doesn't need to be staff for this view
        response = BookAnalyticsView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('book_analytics', response.context_data)
        self.assertIn('popular_books', response.context_data)

    def test_book_detail_analytics_view(self):
        request = self.factory.get(f'/book-analytics/{self.book1.id}/')
        request.user = self.user
        with patch('analytics.tasks.update_book_view_analytics.delay') as mock_delay:
            response = BookDetailAnalyticsView.as_view()(request, book_id=self.book1.id)
            self.assertEqual(response.status_code, 200)
            self.assertIn('book_analytics', response.context_data)
            mock_delay.assert_called_once_with(self.book1.id, self.user.id)

    def test_leaderboard_view(self):
        request = self.factory.get('/leaderboard/')
        request.user = self.user
        response = LeaderboardView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('top_readers', response.context_data)

    def test_recommendations_view(self):
        request = self.factory.get('/recommendations/')
        request.user = self.user
        with patch('analytics.tasks.generate_user_recommendations_task.delay') as mock_delay:
            response = RecommendationsView.as_view()(request)
            self.assertEqual(response.status_code, 200)
            self.assertIn('recommendations', response.context_data)
            # If no recommendations initially, it should trigger generation
            if not BookRecommendation.objects.filter(user=self.user).exists():
                mock_delay.assert_called_once_with(self.user.id)

    def test_bus_analytics_view(self):
        request = self.factory.get('/bus-analytics/')
        request.user = self.staff_user
        response = BusAnalyticsView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('bus_analytics', response.context_data)

    def test_reports_view(self):
        request = self.factory.get('/reports/')
        request.user = self.staff_user
        response = ReportsView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('daily_stats', response.context_data)

    def test_track_book_view_api(self):
        request = self.factory.post(f'/api/track-book-view/{self.book1.id}/')
        request.user = self.user
        with patch('analytics.tasks.update_book_view_analytics.delay') as mock_delay:
            response = track_book_view(request, self.book1.id)
            self.assertEqual(response.status_code, 200)
            self.assertJSONEqual(str(response.content, encoding='utf8'), {'status': 'tracked'})
            mock_delay.assert_called_once_with(self.book1.id, self.user.id)

    def test_track_recommendation_click_api(self):
        rec = BookRecommendation.objects.create(user=self.user, book=self.book1, score=0.8)
        request = self.factory.post(f'/api/track-recommendation-click/{rec.id}/')
        request.user = self.user
        response = track_recommendation_click(request, rec.id)
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(str(response.content, encoding='utf8'), {'status': 'tracked'})
        rec.refresh_from_db()
        self.assertTrue(rec.is_clicked)

    def test_get_user_activities_json_api(self):
        request = self.factory.get('/api/user-activities-json/')
        request.user = self.user
        response = get_user_activities_json(request)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('activities', data)
        self.assertIn('pagination', data)
        self.assertGreater(len(data['activities']), 0)

    def test_get_analytics_summary_json_api(self):
        request = self.factory.get('/api/analytics-summary-json/')
        request.user = self.staff_user
        response = get_analytics_summary_json(request)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('user_stats', data)
        self.assertIn('book_stats', data)

    def test_track_bus_visit_api(self):
        request = self.factory.post(f'/api/track-bus-visit/{self.bus1.id}/')
        request.user = self.user
        with patch('analytics.tasks.update_bus_analytics_task.delay') as mock_delay:
            response = track_bus_visit(request, self.bus1.id)
            self.assertEqual(response.status_code, 200)
            self.assertJSONEqual(str(response.content, encoding='utf8'), {'status': 'tracked'})
            mock_delay.assert_called_once_with(self.bus1.id, visit_count=1)
            self.assertTrue(UserActivity.objects.filter(user=self.user, activity_type='bus_visit', bus=self.bus1).exists())

    def test_export_user_data_api(self):
        request = self.factory.get('/api/export-user-data/')
        request.user = self.user
        response = export_user_data(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertIn(f'filename="user_data_{self.user.username}.json"', response['Content-Disposition'])
        data = response.json()
        self.assertIn('user_info', data)
        self.assertIn('reading_stats', data)
        self.assertIn('activities', data)


class AnalyticsTasksTest(BaseAnalyticsTest):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.book = Book.objects.create(id=1, title='Task Test Book', author='Author', publisher='Pub', publication_year=2020, page_count=100)
        self.bus = LibraryBus.objects.create(id=1, name='Task Test Bus', license_plate='LP-4')
        cache.clear()

        # Mock BorrowRecord.DoesNotExist for specific tests
        self.original_borrow_record_get = BorrowRecord.objects.get

    def tearDown(self):
        # Restore original method after tests
        BorrowRecord.objects.get = self.original_borrow_record_get

    def test_update_analytics_on_borrow_task_borrow(self):
        # Mock a borrow record creation
        mock_borrow = MagicMock()
        mock_borrow.id = 1
        mock_borrow.user = self.user
        mock_borrow.book = self.book
        mock_borrow.return_date = None # Not returned yet

        # Patch the get method to return our mock
        BorrowRecord.objects.get = MagicMock(return_value=mock_borrow)

        update_analytics_on_borrow_task(mock_borrow.id, created=True)

        stats = UserReadingStats.objects.get(user=self.user)
        self.assertEqual(stats.total_books_borrowed, 1)
        self.assertEqual(stats.reputation_score, 105) # Initial 100 + 5 points
        self.assertTrue(UserActivity.objects.filter(user=self.user, activity_type='borrow').exists())

        book_analytics = BookAnalytics.objects.get(book_id=self.book.id)
        self.assertEqual(book_analytics.total_borrows, 1)
        self.assertIsNotNone(book_analytics.last_borrowed)
        self.assertGreater(book_analytics.popularity_score, 0)

    def test_update_analytics_on_borrow_task_return(self):
        # First, simulate a borrow
        UserReadingStats.objects.get(user=self.user).total_books_borrowed = 1
        UserReadingStats.objects.get(user=self.user).save()
        BookAnalytics.objects.get_or_create(book_id=self.book.id, defaults={'total_borrows': 1})

        # Mock a borrow record return
        mock_borrow = MagicMock()
        mock_borrow.id = 2
        mock_borrow.user = self.user
        mock_borrow.book = self.book
        mock_borrow.return_date = timezone.now() # Marked as returned

        # Patch the get method to return our mock
        BorrowRecord.objects.get = MagicMock(return_value=mock_borrow)

        update_analytics_on_borrow_task(mock_borrow.id, created=False)

        stats = UserReadingStats.objects.get(user=self.user)
        self.assertEqual(stats.total_books_returned, 1)
        self.assertEqual(stats.reputation_score, 110) # Initial 100 + 10 points (for return)
        self.assertTrue(UserActivity.objects.filter(user=self.user, activity_type='return').exists())

    def test_update_book_view_analytics(self):
        update_book_view_analytics(self.book.id, self.user.id)
        book_analytics = BookAnalytics.objects.get(book_id=self.book.id)
        self.assertEqual(book_analytics.total_views, 1)
        self.assertTrue(UserActivity.objects.filter(user=self.user, activity_type='view_book').exists())

        # Test popularity recalculation after 10 views (mocking)
        book_analytics.total_views = 9 # Set to 9 views
        book_analytics.save()
        update_book_view_analytics(self.book.id) # This will make it 10 views
        book_analytics.refresh_from_db()
        self.assertEqual(book_analytics.total_views, 10)
        # Assert popularity score was updated (exact value depends on formula)
        self.assertGreater(book_analytics.popularity_score, 0)

    def test_update_review_analytics(self):
        update_review_analytics(self.book.id, 4, self.user.id)
        book_analytics = BookAnalytics.objects.get(book_id=self.book.id)
        self.assertEqual(book_analytics.total_reviews, 1)
        self.assertEqual(book_analytics.average_rating, Decimal('4.00'))
        self.assertTrue(UserActivity.objects.filter(user=self.user, activity_type='review').exists())
        stats = UserReadingStats.objects.get(user=self.user)
        self.assertEqual(stats.reputation_score, 103) # Initial 100 + 3 points

    def test_generate_daily_stats_task(self):
        today = timezone.now().date()
        generate_daily_stats_task(today.isoformat())
        stats = DailyStats.objects.get(date=today)
        self.assertEqual(stats.date, today)
        self.assertEqual(stats.total_users, User.objects.count())

    def test_update_user_streaks_task(self):
        yesterday = timezone.now().date() - timedelta(days=1)
        # Simulate activity yesterday for user
        UserActivity.objects.create(user=self.user, activity_type='borrow', created_at=yesterday)
        
        # Ensure last_activity is set for streak calculation
        user_stats = UserReadingStats.objects.get(user=self.user)
        user_stats.last_activity = yesterday
        user_stats.save()

        update_user_streaks_task()
        stats = UserReadingStats.objects.get(user=self.user)
        self.assertEqual(stats.reading_streak_days, 1) # Should start at 1 if active yesterday

        # Simulate another day of activity
        today = timezone.now().date()
        UserActivity.objects.create(user=self.user, activity_type='borrow', created_at=today)
        user_stats.last_activity = today # Update last_activity for today
        user_stats.save()

        update_user_streaks_task()
        stats.refresh_from_db()
        self.assertEqual(stats.reading_streak_days, 2) # Should increment

        # Test reset for inactive user
        inactive_user = User.objects.create_user(username='inactive', password='password')
        inactive_stats = UserReadingStats.objects.get(user=inactive_user)
        inactive_stats.reading_streak_days = 5
        inactive_stats.save()

        update_user_streaks_task() # Run again, inactive_user should reset
        inactive_stats.refresh_from_db()
        self.assertEqual(inactive_stats.reading_streak_days, 0)

    def test_cleanup_old_activities_task(self):
        old_date = timezone.now() - timedelta(days=91)
        activity_to_archive = UserActivity.objects.create(
            user=self.user, activity_type='borrow', book=self.book, created_at=old_date
        )
        
        cleanup_old_activities_task()
        
        self.assertFalse(UserActivity.objects.filter(pk=activity_to_archive.pk).exists())
        self.assertTrue(ArchivedUserActivity.objects.filter(original_created_at=old_date).exists())

    def test_recalculate_popularity_scores_task(self):
        BookAnalytics.objects.create(book_id=self.book.id, total_borrows=10, average_rating=3.0)
        recalculate_popularity_scores_task()
        book_analytics = BookAnalytics.objects.get(book_id=self.book.id)
        self.assertGreater(book_analytics.popularity_score, 0) # Should be calculated

    def test_generate_user_recommendations_task(self):
        BookAnalytics.objects.create(book_id=self.book.id, popularity_score=Decimal('90.00'))
        generate_user_recommendations_task(self.user.id)
        self.assertTrue(BookRecommendation.objects.filter(user=self.user, book=self.book).exists())

    def test_update_bus_analytics_task(self):
        update_bus_analytics_task(self.bus.id, visit_count=5, borrow_count=2)
        bus_analytics = BusAnalytics.objects.get(bus_id=self.bus.id)
        self.assertEqual(bus_analytics.total_visits, 5)
        self.assertEqual(bus_analytics.total_borrows, 2)
        self.assertGreater(bus_analytics.efficiency_score, 0)

    def test_cache_warmup_task(self):
        # This task primarily calls cached methods, so we check if it runs without error
        try:
            cache_warmup_task()
            # No explicit assertion, just that it completes without raising exceptions
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"cache_warmup_task raised an exception: {e}")

    def test_invalidate_stale_cache_task(self):
        # This task invalidates caches, so we check if it runs without error
        try:
            invalidate_stale_cache_task()
            # No explicit assertion, just that it completes without raising exceptions
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"invalidate_stale_cache_task raised an exception: {e}")


class AnalyticsAdminTest(BaseAnalyticsTest):
    def setUp(self):
        self.site = AnalyticsAdminSite()
        self.factory = RequestFactory()
        self.superuser = User.objects.create_superuser(username='admin', password='password')
        self.user1 = User.objects.create_user(username='testuser1', password='password1')
        self.book1 = Book.objects.create(id=1, title='Admin Test Book 1', author='Author', publisher='Pub', publication_year=2020, page_count=100)
        self.bus1 = LibraryBus.objects.create(id=1, name='Admin Test Bus 1', license_plate='LP-5')

        # Create instances for admin tests
        self.user_stats = UserReadingStats.objects.get(user=self.user1)
        self.book_analytics = BookAnalytics.objects.create(book_id=self.book1.id, popularity_score=50)
        self.bus_analytics = BusAnalytics.objects.create(bus_id=self.bus1.id, efficiency_score=60)
        self.user_activity = UserActivity.objects.create(user=self.user1, activity_type='borrow', book=self.book1)
        self.book_recommendation = BookRecommendation.objects.create(user=self.user1, book=self.book1, score=0.7)
        self.daily_stats = DailyStats.objects.create(date=timezone.now().date(), total_users=1)
        self.archived_activity = ArchivedUserActivity.objects.create(
            user=self.user1, activity_type='old_activity', original_created_at=timezone.now() - timedelta(days=100)
        )
        self.archived_activity.soft_delete(deleted_by=self.superuser)


    def test_readonly_admin_mixin(self):
        mixin = UserReadingStatsAdmin(UserReadingStats, self.site)
        request = self.factory.get('/')
        request.user = self.superuser
        self.assertFalse(mixin.has_add_permission(request))
        self.assertFalse(mixin.has_delete_permission(request))
        self.assertFalse(mixin.has_change_permission(request))

    def test_cache_aware_admin_mixin(self):
        mixin = UserReadingStatsAdmin(UserReadingStats, self.site)
        info = mixin.cache_info(self.user_stats)
        self.assertIn('Cache Version', info)

    def test_timestamped_admin_mixin(self):
        mixin = UserReadingStatsAdmin(UserReadingStats, self.site)
        request = self.factory.get('/')
        list_display = mixin.get_list_display(request)
        self.assertIn('created_at', list_display)
        self.assertIn('updated_at', list_display)

        list_filter = mixin.get_list_filter(request)
        self.assertIn('created_at', list_filter)
        self.assertIn('is_active', list_filter)

    def test_user_reading_stats_admin_display_methods(self):
        admin_instance = UserReadingStatsAdmin(UserReadingStats, self.site)
        
        # Mock request for get_queryset
        request = self.factory.get('/')
        request.user = self.superuser
        qs = admin_instance.get_queryset(request)
        self.assertIn(self.user_stats, qs)

        self.assertIn(self.user1.username, admin_instance.user_link(self.user_stats))
        self.assertIn('span', admin_instance.level_badge(self.user_stats))
        self.assertEqual(admin_instance.books_ratio(self.user_stats), "0/0") # Default values
        self.assertIn('%', admin_instance.completion_rate_display(self.user_stats))

    def test_book_analytics_admin_display_methods(self):
        admin_instance = BookAnalyticsAdmin(BookAnalytics, self.site)
        self.assertIn(self.book1.title, admin_instance.book_title(self.book_analytics))
        self.assertIn('★', admin_instance.rating_display(self.book_analytics))

    def test_bus_analytics_admin_display_methods(self):
        admin_instance = BusAnalyticsAdmin(BusAnalytics, self.site)
        self.assertEqual(admin_instance.bus_name(self.bus_analytics), self.bus1.name)

    def test_user_activity_admin_display_methods(self):
        admin_instance = UserActivityAdmin(UserActivity, self.site)
        self.assertEqual(admin_instance.book_title(self.user_activity), self.book1.title)
        self.assertEqual(admin_instance.metadata_display(self.user_activity), '-') # Default empty metadata

    def test_book_recommendation_admin_display_methods(self):
        admin_instance = BookRecommendationAdmin(BookRecommendation, self.site)
        self.assertEqual(admin_instance.book_title(self.book_recommendation), self.book1.title)
        self.assertIn('Chưa tương tác', admin_instance.status(self.book_recommendation))

    def test_daily_stats_admin_display_methods(self):
        admin_instance = DailyStatsAdmin(DailyStats, self.site)
        self.assertIn('%', admin_instance.activity_ratio(self.daily_stats))

    def test_daily_stats_admin_changelist_view(self):
        request = self.factory.get('/admin/analytics/dailystats/')
        request.user = self.superuser
        response = DailyStatsAdmin(DailyStats, self.site).changelist_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('summary', response.context_data)
        self.assertIn('total_users_avg', response.context_data['summary'])

    def test_archived_user_activity_admin_display_methods(self):
        admin_instance = ArchivedUserActivityAdmin(ArchivedUserActivity, self.site)
        self.assertEqual(admin_instance.book_title(self.archived_activity), '-') # No book in mock
        self.assertIn('Đã xóa', admin_instance.deleted_status(self.archived_activity))

    def test_archived_user_activity_admin_restore_action(self):
        admin_instance = ArchivedUserActivityAdmin(ArchivedUserActivity, self.site)
        request = self.factory.post('/')
        request.user = self.superuser
        
        # Mock queryset for the action
        queryset = ArchivedUserActivity.objects.filter(pk=self.archived_activity.pk)
        
        # Patch the restore method of the model instance
        with patch.object(self.archived_activity, 'restore') as mock_restore:
            admin_instance.restore_activities(request, queryset)
            mock_restore.assert_called_once()
            # Check for success message (requires mocking message_user)
            self.assertIn("Đã khôi phục 1 hoạt động.", admin_instance.message_user.call_args[0][1])

    def test_analytics_admin_site_index(self):
        request = self.factory.get('/admin/')
        request.user = self.superuser
        response = self.site.index(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('user_summary', response.context_data)
        self.assertIn('book_summary', response.context_data)
        self.assertIn('system_health', response.context_data)
        self.assertIn('cache_versions', response.context_data)

    def test_analytics_admin_site_app_index(self):
        request = self.factory.get('/admin/analytics/')
        request.user = self.superuser
        response = self.site.app_index(request, 'analytics')
        self.assertEqual(response.status_code, 200)
        self.assertIn('cache_info', response.context_data)
        self.assertEqual(response.context_data['cache_info']['total_models'], 6)
