# analytics/tasks.py
from celery import shared_task
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta, datetime
import logging
from .models import BookAnalytics, UserActivity, UserReadingStats, DailyStats, BusAnalytics, ArchivedUserActivity, BookRecommendation
from django.contrib.auth.models import User
from transactions.models import BorrowRecord
    
logger = logging.getLogger(__name__)

@shared_task(name="update_analytics_on_borrow_task")
def update_analytics_on_borrow_task(borrow_record_id, created):
    """
    Task bất đồng bộ để cập nhật các thống kê liên quan khi có giao dịch mượn/trả.
    Tối ưu cho 10k users - sử dụng bulk update và cache invalidation thông minh.
    """
    

    try:
        borrow = BorrowRecord.objects.select_related('user', 'book').get(id=borrow_record_id)
        
        with transaction.atomic():
            # 1. Cập nhật UserReadingStats
            stats, stats_created = UserReadingStats.objects.get_or_create(
                user=borrow.user,
                defaults={
                    'total_books_borrowed': 0,
                    'total_books_returned': 0,
                    'reputation_score': 100,
                    'member_level': 'bronze',
                    'created_by': borrow.user,
                    'modified_by': borrow.user
                }
            )
            
            # Cập nhật thống kê user
            user_updates = {'last_activity': timezone.now()}
            points_earned = 0
            activity_type = ''
            
            if created:  # Mượn sách mới
                user_updates['total_books_borrowed'] = F('total_books_borrowed') + 1
                points_earned = 5
                activity_type = 'borrow'
            elif borrow.return_date:  # Trả sách
                user_updates['total_books_returned'] = F('total_books_returned') + 1
                points_earned = 10
                activity_type = 'return'
            
            # Cập nhật stats - Cache sẽ tự động invalidate nhờ CacheMixin
            UserReadingStats.objects.filter(pk=stats.pk).update(**user_updates)
            
            # Thêm điểm reputation nếu có
            if points_earned > 0:
                stats.add_reputation(points_earned, f"Hoạt động: {activity_type}")
            
            # 2. Cập nhật BookAnalytics
            book_analytics, book_created = BookAnalytics.objects.get_or_create(
                book=borrow.book,
                defaults={
                    'total_borrows': 0,
                    'total_views': 0,
                    'total_reviews': 0,
                    'average_rating': 0,
                    'popularity_score': 0
                }
            )
            
            book_updates = {'last_borrowed': timezone.now()}
            if created:
                book_updates['total_borrows'] = F('total_borrows') + 1
            
            # Cache sẽ tự động invalidate nhờ CacheMixin
            BookAnalytics.objects.filter(pk=book_analytics.pk).update(**book_updates)
            
            # Tính lại popularity score nếu có thay đổi đáng kể
            if created:
                # Refresh object để lấy giá trị mới sau khi update
                book_analytics.refresh_from_db()
                book_analytics.calculate_popularity()
            
            # 3. Tạo UserActivity log
            UserActivity.objects.create(
                user=borrow.user,
                activity_type=activity_type,
                book=borrow.book,
                points=points_earned,
                description=f"Hoạt động mượn/trả sách: {borrow.book.title}",
                created_by=borrow.user,
                modified_by=borrow.user
            )
        
        logger.info(f"Analytics updated for borrow record {borrow_record_id}")
        
    except BorrowRecord.DoesNotExist:
        logger.warning(f"BorrowRecord with id {borrow_record_id} not found for analytics update.")
    except Exception as e:
        logger.error(f"Error updating analytics for borrow record {borrow_record_id}: {str(e)}")
        raise  # Re-raise để Celery retry task nếu cần

@shared_task(name="update_book_view_analytics")
def update_book_view_analytics(book_id, user_id=None):
    """
    Cập nhật thống kê lượt xem sách.
    Chỉ chạy khi có view thực tế để tránh spam.
    """  
    try:
        book_analytics, created = BookAnalytics.objects.get_or_create(
            book_id=book_id,
            defaults={
                'total_borrows': 0,
                'total_views': 0,
                'total_reviews': 0,
                'average_rating': 0,
                'popularity_score': 0
            }
        )
        
        # Cập nhật lượt xem - Cache sẽ tự động invalidate nhờ CacheMixin
        BookAnalytics.objects.filter(pk=book_analytics.pk).update(
            total_views=F('total_views') + 1
        )
        
        # Tính lại popularity score mỗi 10 views
        book_analytics.refresh_from_db()
        if book_analytics.total_views % 10 == 0:
            book_analytics.calculate_popularity()
        
        # Tạo UserActivity log nếu có user_id
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                UserActivity.objects.create(
                    user=user,
                    activity_type='view_book',
                    book_id=book_id,
                    points=0,
                    description=f"Xem sách: {book_analytics.book.title}",
                    created_by=user,
                    modified_by=user
                )
            except User.DoesNotExist:
                logger.warning(f"User with id {user_id} not found for view activity log")
        
        logger.debug(f"View analytics updated for book {book_id}")
        
    except Exception as e:
        logger.error(f"Error updating view analytics for book {book_id}: {str(e)}")

@shared_task(name="update_review_analytics")
def update_review_analytics(book_id, rating, user_id=None):
    """
    Cập nhật thống kê đánh giá sách.
    """
    try:
        with transaction.atomic():
            book_analytics, created = BookAnalytics.objects.get_or_create(
                book_id=book_id,
                defaults={
                    'total_borrows': 0,
                    'total_views': 0,
                    'total_reviews': 0,
                    'average_rating': 0,
                    'popularity_score': 0
                }
            )
            
            # Tính lại rating trung bình
            current_total = book_analytics.total_reviews * float(book_analytics.average_rating)
            new_total = current_total + rating
            new_count = book_analytics.total_reviews + 1
            new_average = new_total / new_count
            
            # Cache sẽ tự động invalidate nhờ CacheMixin
            BookAnalytics.objects.filter(pk=book_analytics.pk).update(
                total_reviews=F('total_reviews') + 1,
                average_rating=round(new_average, 2)
            )
            
            # Tính lại popularity score
            book_analytics.refresh_from_db()
            book_analytics.calculate_popularity()
            
            # Tạo UserActivity log nếu có user_id
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                    UserActivity.objects.create(
                        user=user,
                        activity_type='review',
                        book_id=book_id,
                        points=3,  # 3 điểm cho việc review
                        description=f"Đánh giá sách: {book_analytics.book.title} - {rating} sao",
                        created_by=user,
                        modified_by=user
                    )
                    
                    # Thêm điểm reputation cho user
                    stats, _ = UserReadingStats.objects.get_or_create(
                        user=user,
                        defaults={
                            'total_books_borrowed': 0,
                            'total_books_returned': 0,
                            'reputation_score': 100,
                            'member_level': 'bronze',
                            'created_by': user,
                            'modified_by': user
                        }
                    )
                    stats.add_reputation(3, f"Đánh giá sách: {book_analytics.book.title}")
                    
                except User.DoesNotExist:
                    logger.warning(f"User with id {user_id} not found for review activity log")
        
        logger.info(f"Review analytics updated for book {book_id}, rating: {rating}")
        
    except Exception as e:
        logger.error(f"Error updating review analytics for book {book_id}: {str(e)}")

@shared_task(name="generate_daily_stats_task")
def generate_daily_stats_task(date_str=None):
    """
    Tạo thống kê hàng ngày.
    Chạy hàng ngày vào lúc 0:00 AM.
    """
    try:
        if date_str:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            date = (timezone.now() - timedelta(days=1)).date()  # Thống kê ngày hôm qua
        
        # Cache sẽ tự động invalidate nhờ CacheMixin khi save
        stats = DailyStats.generate_daily_stats(date)
        
        logger.info(f"Daily stats generated for {date}: {stats}")
        
    except Exception as e:
        logger.error(f"Error generating daily stats for {date_str}: {str(e)}")

@shared_task(name="update_user_streaks_task")
def update_user_streaks_task():
    """
    Cập nhật reading streak cho tất cả users.
    Chạy hàng ngày vào lúc 1:00 AM.
    """
    
    try:
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        # Lấy users có hoạt động hôm qua
        active_users = User.objects.filter(
            borrow_records__borrow_date__date=yesterday
        ).distinct()
        
        # Cập nhật streak cho users active
        for user in active_users.iterator(chunk_size=1000):
            stats, created = UserReadingStats.objects.get_or_create(
                user=user,
                defaults={
                    'total_books_borrowed': 0,
                    'total_books_returned': 0,
                    'reputation_score': 100,
                    'member_level': 'bronze',
                    'created_by': user,
                    'modified_by': user
                }
            )
            
            # Kiểm tra xem user có hoạt động liên tục không
            if stats.last_activity.date() == yesterday:
                stats.reading_streak_days += 1
                if stats.reading_streak_days > stats.max_reading_streak:
                    stats.max_reading_streak = stats.reading_streak_days
            else:
                stats.reading_streak_days = 1
            
            # Cache sẽ tự động invalidate nhờ CacheMixin
            stats.save(update_fields=['reading_streak_days', 'max_reading_streak'])
        
        # Reset streak cho users không active
        UserReadingStats.objects.exclude(
            user__in=active_users
        ).filter(
            reading_streak_days__gt=0
        ).update(reading_streak_days=0)
        
        logger.info(f"User streaks updated for {len(active_users)} active users")
        
    except Exception as e:
        logger.error(f"Error updating user streaks: {str(e)}")

@shared_task(name="cleanup_old_activities_task")
def cleanup_old_activities_task():
    """
    Dọn dẹp các activity cũ (> 3 tháng).
    Chuyển sang ArchivedUserActivity thay vì xóa hoàn toàn.
    Chạy hàng tuần để tránh database quá lớn.
    """
    
    try:
        cutoff_date = timezone.now() - timedelta(days=90)
        
        # Lấy activities cũ
        old_activities_qs = UserActivity.objects.filter(
            created_at__lt=cutoff_date
        )
        
        # Tạo archived records theo batch
        archived_activities = []
        batch_size = 5000
        count = 0
        
        for activity in old_activities_qs.select_related('user', 'book').iterator(chunk_size=batch_size):
            archived_activities.append(ArchivedUserActivity(
                user=activity.user,
                activity_type=activity.activity_type,
                book=activity.book,
                description=activity.description,
                original_created_at=activity.created_at,
                created_by=activity.created_by,
                modified_by=activity.modified_by
            ))
            
            count += 1
            if len(archived_activities) >= batch_size:
                ArchivedUserActivity.objects.bulk_create(archived_activities)
                archived_activities = []
                
        if archived_activities:
            ArchivedUserActivity.objects.bulk_create(archived_activities)
        
        # Xóa activities cũ
        # Note: Delete with large limit might lock table, so we delete using primary keys
        deleted_count = 0
        while True:
            ids = list(old_activities_qs.values_list('id', flat=True)[:batch_size])
            if not ids:
                break
            deleted_count += UserActivity.objects.filter(id__in=ids).delete()[0]
        
        logger.info(f"Archived and cleaned up {deleted_count} old user activities")
        
    except Exception as e:
        logger.error(f"Error cleaning up old activities: {str(e)}")

@shared_task(name="recalculate_popularity_scores_task")
def recalculate_popularity_scores_task():
    """
    Tính lại popularity score cho tất cả sách.
    Chạy hàng tuần để cập nhật ranking.
    """
    from .models import BookAnalytics
    
    try:
        # Lấy tất cả book analytics và tính lại popularity (dùng iterator để tránh OOM)
        book_analytics_qs = BookAnalytics.objects.all()
        count = 0
        
        for book_analytics in book_analytics_qs.iterator(chunk_size=1000):
            # Cache sẽ tự động invalidate nhờ CacheMixin khi save
            book_analytics.calculate_popularity()
            count += 1
        
        logger.info(f"Recalculated popularity scores for {count} books")
        
    except Exception as e:
        logger.error(f"Error recalculating popularity scores: {str(e)}")

@shared_task(name="generate_user_recommendations_task")
def generate_user_recommendations_task(user_id=None):
    """
    Tạo gợi ý sách cho users.
    Chạy hàng ngày hoặc khi có request cụ thể.
    """
    
    try:
        if user_id:
            users = User.objects.filter(id=user_id)
        else:
            # Tạo gợi ý cho users active trong 7 ngày gần đây
            users = User.objects.filter(
                last_login__gte=timezone.now() - timedelta(days=7)
            )
        
        recommendations_created = 0
        
        for user in users:
            # Tạo gợi ý phổ biến
            popular_recs = BookRecommendation.generate_popular_recommendations(user, limit=5)
            recommendations_created += len(popular_recs)
            
            # Có thể thêm các thuật toán khác như similar_users, same_category, etc.
            
        logger.info(f"Generated {recommendations_created} recommendations for {len(users)} users")
        
    except Exception as e:
        logger.error(f"Error generating recommendations: {str(e)}")

@shared_task(name="update_bus_analytics_task")
def update_bus_analytics_task(bus_id, visit_count=1, borrow_count=0):
    """
    Cập nhật thống kê xe bus.
    """
    try:
        bus_analytics, created = BusAnalytics.objects.get_or_create(
            bus_id=bus_id,
            defaults={
                'total_visits': 0,
                'total_borrows': 0,
                'unique_visitors': 0,
                'efficiency_score': 0
            }
        )
        
        # Cập nhật stats - Cache sẽ tự động invalidate nhờ CacheMixin
        updates = {}
        if visit_count > 0:
            updates['total_visits'] = F('total_visits') + visit_count
        if borrow_count > 0:
            updates['total_borrows'] = F('total_borrows') + borrow_count
        
        if updates:
            BusAnalytics.objects.filter(pk=bus_analytics.pk).update(**updates)
            
            # Tính lại efficiency score
            bus_analytics.refresh_from_db()
            bus_analytics.calculate_efficiency()
        
        logger.debug(f"Bus analytics updated for bus {bus_id}")
        
    except Exception as e:
        logger.error(f"Error updating bus analytics for bus {bus_id}: {str(e)}")

@shared_task(name="cache_warmup_task")
def cache_warmup_task():
    """
    Làm nóng cache cho các data thường xuyên được truy cập.
    Chạy vào lúc 5:00 AM mỗi ngày.
    """
    try:
        # Warm up popular data
        logger.info("Starting cache warmup...")
        
        # Top readers
        UserReadingStats.get_top_readers(10)
        UserReadingStats.get_level_distribution()
        
        # Popular books
        BookAnalytics.get_popular_books(10)
        BookAnalytics.get_trending_books(7, 10)
        
        # Weekly stats
        DailyStats.get_weekly_stats(4)
        
        # System summaries
        from .models import get_user_stats_summary, get_book_stats_summary, get_system_health
        get_user_stats_summary()
        get_book_stats_summary()
        get_system_health()
        
        logger.info("Cache warmup completed successfully")
        
    except Exception as e:
        logger.error(f"Error during cache warmup: {str(e)}")

@shared_task(name="invalidate_stale_cache_task")
def invalidate_stale_cache_task():
    """
    Xóa cache cũ và tăng version để đảm bảo tính nhất quán.
    Chạy mỗi 6 tiếng.
    """
    
    try:
        # Invalidate model caches
        UserReadingStats.invalidate_model_cache()
        BookAnalytics.invalidate_model_cache()
        UserActivity.invalidate_model_cache()
        DailyStats.invalidate_model_cache()
        
        logger.info("Stale cache invalidated for all models")
        
    except Exception as e:
        logger.error(f"Error invalidating stale cache: {str(e)}")