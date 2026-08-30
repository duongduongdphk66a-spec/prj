# analytics/views.py
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.contrib.auth.models import User
from django.views.generic import ListView, DetailView, TemplateView
from django.utils.decorators import method_decorator
from datetime import datetime, timedelta
from django.db.models.functions import Extract, TruncDate
from .models import (
    UserReadingStats, BookAnalytics, BusAnalytics, UserActivity, 
    BookRecommendation, DailyStats, get_user_stats_summary, get_book_stats_summary, get_system_health
)
from inventory.models import Category 
from .tasks import (
    update_book_view_analytics, generate_user_recommendations_task,
    update_bus_analytics_task
)


# =============================================================================
# MIXINS - Tái sử dụng logic chung
# =============================================================================

class CacheAwareMixin:
    """Mixin thêm cache info vào context"""
    def get_cache_info(self):
        # Giả định model có phương thức get_current_version từ CacheMixin
        version_func = getattr(self.model, 'get_current_version', lambda: 'N/A')
        return {
            'timestamp': timezone.now(),
            'version': version_func(),
            'ttl': getattr(self, 'cache_timeout', 900)
        }

class StatsContextMixin:
    """Mixin thêm stats chung vào context"""
    def get_stats_context(self):
        return {
            'user_stats': get_user_stats_summary(),
            'book_stats': get_book_stats_summary(),
            'system_health': get_system_health(),
        }

class PaginationMixin:
    """Mixin xử lý pagination với custom page size"""
    def get_paginate_by(self, queryset):
        return int(self.request.GET.get('per_page', self.paginate_by or 20))

# =============================================================================
# DASHBOARD VIEWS
# =============================================================================

@method_decorator(login_required, name='dispatch')
class DashboardView(CacheAwareMixin, StatsContextMixin, TemplateView):
    template_name = 'analytics/dashboard.html'
    model = DailyStats # Gán model để CacheAwareMixin hoạt động

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Lấy dữ liệu thống kê chung
        context.update(self.get_stats_context())
        
        # Lấy dữ liệu thống kê riêng của người dùng
        user_stats, _ = UserReadingStats.objects.get_or_create(user=self.request.user)
        
        context.update({
            'user_specific_stats': user_stats,
            'user_activities': UserActivity.get_recent_activities(self.request.user, limit=5),
            'user_recommendations': BookRecommendation.get_user_recommendations(self.request.user, limit=5),
            'daily_stats': DailyStats.get_weekly_stats(weeks=1),
            'cache_info': self.get_cache_info(),
        })
        return context

@method_decorator(staff_member_required, name='dispatch')
class AdminDashboardView(CacheAwareMixin, StatsContextMixin, TemplateView):
    template_name = 'analytics/admin_dashboard.html'
    model = DailyStats # Gán model để CacheAwareMixin hoạt động

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        
        context.update(self.get_stats_context())
        context.update({
            'total_users': User.objects.count(),
            'active_users_today': User.objects.filter(last_login__date=today).count(),
            'total_books': BookAnalytics.objects.count(),
            'total_borrows_today': UserActivity.objects.filter(activity_type='borrow', created_at__date=today).count(),
            'popular_books': BookAnalytics.get_popular_books(5),
            'top_readers': UserReadingStats.get_top_readers(5),
            'level_distribution': UserReadingStats.get_level_distribution(),
            'weekly_stats': DailyStats.get_weekly_stats(4),
            'top_buses': BusAnalytics.get_top_performing_buses(5),
            'cache_info': self.get_cache_info(),
        })
        return context

# =============================================================================
# USER ANALYTICS VIEWS
# =============================================================================

@method_decorator(login_required, name='dispatch')
class UserStatsView(CacheAwareMixin, DetailView):
    model = UserReadingStats
    template_name = 'analytics/user_stats.html'
    context_object_name = 'user_stats'
    
    def get_object(self):
        stats, _ = UserReadingStats.objects.get_or_create(user=self.request.user)
        return stats
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        context.update({
            'recent_activities': UserActivity.get_recent_activities(user, limit=5),
            'recommendations': BookRecommendation.get_user_recommendations(user, limit=5),
            'user_rank': self.get_user_rank(user),
            'achievement_progress': self.get_achievement_progress(self.object),
            'cache_info': self.get_cache_info(),
        })
        return context
    
    def get_user_rank(self, user):
        """Tính thứ hạng của người dùng dựa trên điểm uy tín."""
        if not hasattr(user, 'reading_stats'):
            return User.objects.count()
        
        user_score = user.reading_stats.reputation_score
        higher_rank_count = UserReadingStats.objects.filter(reputation_score__gt=user_score).count()
        return higher_rank_count + 1
    
    def get_achievement_progress(self, stats):
        """Tính toán tiến trình cho các thành tích."""
        if not stats: return {}
        
        level_thresholds = {'bronze': 200, 'silver': 400, 'gold': 600, 'platinum': 800, 'diamond': 1000}
        current_level = stats.member_level
        next_threshold = level_thresholds.get(current_level, 1000)

        return {
            'next_level': {
                'completed': current_level == 'diamond',
                'progress': min((stats.reputation_score / next_threshold) * 100, 100) if next_threshold > 0 else 100,
                'points_needed': max(0, next_threshold - stats.reputation_score)
            },
            'streak_milestone': self._calculate_milestone_progress(stats.current_streak, [7, 30, 90, 180, 365]),
            'reading_milestone': self._calculate_milestone_progress(stats.total_books_read, [10, 25, 50, 100, 200]),
        }

    def _calculate_milestone_progress(self, current_value, milestones):
        """Hàm trợ giúp tính tiến trình cho các cột mốc."""
        for milestone in milestones:
            if current_value < milestone:
                return {
                    'target': milestone, 'current': current_value,
                    'progress': (current_value / milestone) * 100
                }
        return {'completed': True, 'progress': 100, 'target': milestones[-1], 'current': current_value}

@method_decorator(login_required, name='dispatch')
class UserActivitiesView(CacheAwareMixin, PaginationMixin, ListView):
    model = UserActivity
    template_name = 'analytics/user_activities.html'
    context_object_name = 'activities'
    paginate_by = 20
    
    def get_queryset(self):
        return UserActivity.objects.filter(user=self.request.user).select_related('book', 'bus').order_by('-created_at')

# =============================================================================
# BOOK ANALYTICS VIEWS
# =============================================================================

@method_decorator(cache_page(900), name='dispatch')
class BookAnalyticsView(CacheAwareMixin, PaginationMixin, ListView):
    model = BookAnalytics
    template_name = 'analytics/book_analytics.html'
    context_object_name = 'book_analytics'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('book', 'book__category')
        
        # Filter logic
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(book__title__icontains=search) |
                Q(book__author__icontains=search) |
                Q(book__isbn__icontains=search)
            )
        
        category = self.request.GET.get('category', '')
        if category:
            queryset = queryset.filter(book__category=category)
        
        # Sort logic
        sort_by = self.request.GET.get('sort', 'popularity')
        sort_map = {
            'borrows': '-total_borrows',
            'rating': '-average_rating',
            'recent': '-last_borrowed',
            'popularity': '-popularity_score'
        }
        queryset = queryset.order_by(sort_map.get(sort_by, '-popularity_score'))
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        seven_days_ago = timezone.now() - timedelta(days=7)
        fourteen_days_ago = timezone.now() - timedelta(days=14)
        
        # Bổ sung logic truy vấn các sách đặc biệt
        top_trending_book = BookAnalytics.objects.filter(last_borrowed__gte=seven_days_ago).order_by('-total_borrows').first()
        top_rated_book = BookAnalytics.objects.filter(total_reviews__gte=5).order_by('-average_rating').first()
        
        # PRE-COMPUTE trends: 2 bulk queries thay vì 2*N queries
        current_week_counts = dict(
            UserActivity.objects.filter(
                activity_type='borrow', created_at__gte=seven_days_ago
            ).values('book_id').annotate(count=Count('id')).values_list('book_id', 'count')
        )
        previous_week_counts = dict(
            UserActivity.objects.filter(
                activity_type='borrow',
                created_at__lt=seven_days_ago,
                created_at__gte=fourteen_days_ago
            ).values('book_id').annotate(count=Count('id')).values_list('book_id', 'count')
        )
        
        book_list = list(context['book_analytics'])
        for stat in book_list:
            current = current_week_counts.get(stat.book_id, 0)
            previous = previous_week_counts.get(stat.book_id, 0)
            
            if current > previous * 1.2:
                stat.trend_direction = 'up'
            elif current < previous * 0.8:
                stat.trend_direction = 'down'
            else:
                stat.trend_direction = 'stable'

        context.update({
            'book_analytics': book_list,
            'popular_books': BookAnalytics.get_popular_books(5),
            'trending_books': BookAnalytics.get_trending_books(7, 5),
            'top_trending_book': top_trending_book,
            'top_rated_book': top_rated_book,
            'categories': Category.objects.all(),
            'cache_info': self.get_cache_info(),
        })
        return context


@method_decorator(login_required, name='dispatch')
class BookDetailAnalyticsView(CacheAwareMixin, DetailView):
    model = BookAnalytics
    template_name = 'analytics/book_detail_analytics.html'
    context_object_name = 'book_analytics'
    pk_url_kwarg = 'book_id'

    def get_object(self):
        book_id = self.kwargs['book_id']
        analytics, created = BookAnalytics.objects.get_or_create(
            book_id=book_id,
            defaults={
                'total_borrows': 0, 'total_views': 0, 'total_reviews': 0,
                'average_rating': 0, 'popularity_score': 0
            })
        return super().get_object()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        book = self.object.book
        
        context.update({
            'recent_activities': UserActivity.objects.filter(book=book).select_related('user').order_by('-created_at')[:10],
            'borrow_history': self.get_borrow_history(book),
            'similar_books': self.get_similar_books(book),
            'cache_info': self.get_cache_info(),
        })
        return context
    
    def get_borrow_history(self, book):
        """Lấy lịch sử mượn sách và đổi tên 'count' thành 'borrows'."""
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        return UserActivity.objects.filter(
            book=book, activity_type='borrow',
            created_at__date__gte=thirty_days_ago
        ).annotate(date=TruncDate('created_at')) \
         .values('date') \
         .annotate(borrows=Count('id')) \
         .order_by('date')
    
    def get_rating_distribution(self, book):
        # Placeholder for Review model
        return {'5': 0, '4': 0, '3': 0, '2': 0, '1': 0}
    
    def get_similar_books(self, book):
        if not book.category:
            return BookAnalytics.objects.none()
        return BookAnalytics.objects.filter(
            book__category=book.category
        ).exclude(book=book).select_related('book').order_by('-popularity_score')[:5]
    
# =============================================================================
# LEADERBOARD & RECOMMENDATIONS
# =============================================================================

@method_decorator(cache_page(1800), name='dispatch')
class LeaderboardView(CacheAwareMixin, TemplateView):
    template_name = 'analytics/leaderboard.html'
    model = UserReadingStats

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'top_readers': UserReadingStats.get_top_readers(50),
            'level_distribution': UserReadingStats.get_level_distribution(),
            'recent_level_ups': UserActivity.objects.filter(
                activity_type='level_up',
                created_at__gte=timezone.now() - timedelta(days=7)
            ).select_related('user').order_by('-created_at')[:10],
            'top_streaks': UserReadingStats.objects.filter(
                reading_streak_days__gt=0
            ).order_by('-reading_streak_days')[:20],
            'cache_info': self.get_cache_info(),
        })
        return context

@method_decorator(login_required, name='dispatch')
class RecommendationsView(CacheAwareMixin, PaginationMixin, ListView):
    model = BookRecommendation
    template_name = 'analytics/recommendations.html'
    context_object_name = 'recommendations'
    paginate_by = 20
    
    def get_queryset(self):
        return BookRecommendation.objects.filter(user=self.request.user).select_related('book').order_by('-score', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Generate recommendations if empty
        if not context['recommendations']:
            try:
                generate_user_recommendations_task.delay(self.request.user.id)
                context['generating'] = True
            except Exception:
                context['generating'] = False
        
        context.update({
            'recommendation_stats': self.get_recommendation_stats(),
            'algorithm_types': BookRecommendation.objects.filter(user=self.request.user).values('algorithm_type').annotate(count=Count('id')).order_by('-count'),
            'cache_info': self.get_cache_info(),
        })
        return context
    
    def get_recommendation_stats(self):
        user = self.request.user
        total_recs = BookRecommendation.objects.filter(user=user).count()
        
        if total_recs == 0:
            return {'accuracy': 0, 'click_rate': 0, 'borrow_rate': 0}
        
        clicked = BookRecommendation.objects.filter(user=user, is_clicked=True).count()
        borrowed = BookRecommendation.objects.filter(user=user, is_borrowed=True).count()
        
        return {
            'total': total_recs, 'clicked': clicked, 'borrowed': borrowed,
            'click_rate': round((clicked / total_recs) * 100, 1),
            'borrow_rate': round((borrowed / total_recs) * 100, 1),
        }

# =============================================================================
# BUS ANALYTICS & REPORTS
# =============================================================================

@method_decorator(staff_member_required, name='dispatch')
class BusAnalyticsView(CacheAwareMixin, PaginationMixin, ListView):
    model = BusAnalytics
    template_name = 'analytics/bus_analytics.html'
    context_object_name = 'bus_analytics'
    paginate_by = 20
    
    def get_queryset(self):
        return BusAnalytics.objects.select_related('bus').order_by('-efficiency_score')

@method_decorator(staff_member_required, name='dispatch')
class ReportsView(CacheAwareMixin, TemplateView):
    template_name = 'analytics/reports.html'
    model = DailyStats # Gán model để CacheAwareMixin hoạt động

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Lấy khoảng thời gian từ request GET
        try:
            start_date_str = self.request.GET.get('start_date')
            end_date_str = self.request.GET.get('end_date')
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else timezone.now().date() - timedelta(days=29)
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else timezone.now().date()
        except (ValueError, TypeError):
            start_date = timezone.now().date() - timedelta(days=29)
            end_date = timezone.now().date()
        
        days = (end_date - start_date).days + 1
        
        # Dữ liệu kỳ hiện tại
        current_period_stats = DailyStats.objects.filter(date__range=[start_date, end_date])
        current_summary = current_period_stats.aggregate(
            total_borrows=Sum('total_borrows'),
            total_returns=Sum('total_returns'),
            total_new_users=Sum('new_users')
        )
        
        # Dữ liệu kỳ trước đó để so sánh
        previous_start_date = start_date - timedelta(days=days)
        previous_end_date = start_date - timedelta(days=1)
        previous_period_stats = DailyStats.objects.filter(date__range=[previous_start_date, previous_end_date])
        previous_summary = previous_period_stats.aggregate(
            total_borrows=Sum('total_borrows'),
            total_new_users=Sum('new_users')
        )

        # Hàm trợ giúp tính phần trăm thay đổi
        def get_change_percent(current, previous):
            if previous is None or previous == 0: return 100.0
            if current is None: current = 0
            return ((current - previous) / previous) * 100

        # Tính toán các chỉ số thay đổi
        borrow_change = get_change_percent(current_summary['total_borrows'], previous_summary['total_borrows'])
        user_change = get_change_percent(current_summary['total_new_users'], previous_summary['total_new_users'])

        # Tính các chỉ số khác
        total_borrows_period = current_summary['total_borrows'] or 0
        total_returns_period = current_summary['total_returns'] or 0
        completion_rate = (total_returns_period / total_borrows_period * 100) if total_borrows_period > 0 else 0
        
        # Lấy top sách và tính phần trăm
        top_books_period = UserActivity.objects.filter(
            activity_type='borrow', created_at__date__range=[start_date, end_date]
        ).values('book__title', 'book__author').annotate(borrow_count=Count('id')).order_by('-borrow_count')[:5]
        
        if total_borrows_period > 0:
            for book in top_books_period:
                book['percentage'] = (book['borrow_count'] / total_borrows_period) * 100
        
        context.update({
            'chart_data': list(current_period_stats.values('date', 'total_borrows', 'total_returns', 'new_users').order_by('date')),
            'days': days,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            
            # Các chỉ số cho thẻ summary
            'total_borrows_period': total_borrows_period,
            'new_users_period': current_summary['total_new_users'] or 0,
            'active_buses_period': BusAnalytics.objects.filter(bus__is_active=True).count(),
            'total_buses': BusAnalytics.objects.count(),
            'completion_rate': completion_rate,
            'borrow_change': borrow_change,
            'user_change': user_change,

            # Dữ liệu cho bảng
            'top_books_period': top_books_period,
            'top_users_period': UserActivity.objects.filter(
                activity_type='borrow', created_at__date__range=[start_date, end_date]
            ).values('user__username', 'user__email').annotate(
                borrow_count=Count('id'),
                total_points=Sum('points')
            ).order_by('-borrow_count')[:5],
        })
        return context

# =============================================================================
# API ENDPOINTS
# =============================================================================

@login_required
def track_book_view(request, book_id):
    if request.method == 'POST':
        update_book_view_analytics.delay(book_id, request.user.id)
        return JsonResponse({'status': 'tracked'})
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def track_recommendation_click(request, recommendation_id):
    if request.method == 'POST':
        try:
            recommendation = BookRecommendation.objects.get(id=recommendation_id, user=request.user)
            recommendation.mark_clicked()
            return JsonResponse({'status': 'tracked'})
        except BookRecommendation.DoesNotExist:
            return JsonResponse({'error': 'Recommendation not found'}, status=404)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def get_user_activities_json(request):
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 10))
    
    activities = UserActivity.objects.filter(user=request.user).select_related('book', 'bus').order_by('-created_at')
    paginator = Paginator(activities, per_page)
    page_obj = paginator.get_page(page)
    
    data = {
        'activities': [
            {
                'id': activity.id, 'type': activity.activity_type,
                'description': activity.description, 'points': activity.points,
                'created_at': activity.created_at.isoformat(),
                'book': {'title': activity.book.title, 'author': activity.book.author} if activity.book else None,
                'bus': {'name': activity.bus.name} if activity.bus else None,
            }
            for activity in page_obj.object_list
        ],
        'pagination': {
            'current_page': page_obj.number, 'total_pages': paginator.num_pages,
            'has_next': page_obj.has_next(), 'has_previous': page_obj.has_previous(),
            'total_items': paginator.count,
        }
    }
    return JsonResponse(data)

@staff_member_required
def get_analytics_summary_json(request):
    user_stats = get_user_stats_summary() or {}
    top_readers_data = [
        {
            'username': r.user.username if getattr(r, 'user', None) else 'Unknown',
            'reputation_score': getattr(r, 'reputation_score', 0),
            'member_level': getattr(r, 'member_level', 'bronze'),
            'total_books_read': getattr(r, 'total_books_read', 0)
        } for r in user_stats.get('top_readers', [])
    ]
    user_stats_clean = {
        'total_users': user_stats.get('total_users', 0),
        'active_users': user_stats.get('active_users', 0),
        'top_readers': top_readers_data,
        'level_distribution': list(user_stats.get('level_distribution', []))
    }
    
    book_stats = get_book_stats_summary() or {}
    popular_books_data = [
        {
            'title': b.book.title if getattr(b, 'book', None) else 'Unknown',
            'total_borrows': getattr(b, 'total_borrows', 0),
            'popularity_score': float(getattr(b, 'popularity_score', 0))
        } for b in book_stats.get('popular_books', [])
    ]
    trending_books_data = [
        {
            'title': b.book.title if getattr(b, 'book', None) else 'Unknown',
            'total_borrows': getattr(b, 'total_borrows', 0)
        } for b in book_stats.get('trending_books', [])
    ]
    book_stats_clean = {
        'total_books': book_stats.get('total_books', 0),
        'total_borrows': book_stats.get('total_borrows', 0),
        'avg_rating': float(book_stats.get('avg_rating', 0)),
        'popular_books': popular_books_data,
        'trending_books': trending_books_data,
    }
    
    sys_health = get_system_health() or {}
    recent_stats_clean = [
        {
            'date': s.date.isoformat() if hasattr(s, 'date') and s.date else str(s),
            'total_borrows': getattr(s, 'total_borrows', 0),
            'total_returns': getattr(s, 'total_returns', 0),
            'active_users': getattr(s, 'active_users', 0)
        } for s in sys_health.get('recent_stats', [])
    ]
    sys_health_clean = {
        'cache_version': sys_health.get('cache_version', {}),
        'recent_stats': recent_stats_clean,
        'active_users_today': sys_health.get('active_users_today', 0)
    }

    data = {
        'user_stats': user_stats_clean,
        'book_stats': book_stats_clean,
        'system_health': sys_health_clean,
        'timestamp': timezone.now().isoformat(),
    }
    return JsonResponse(data)

@login_required
def track_bus_visit(request, bus_id):
    if request.method == 'POST':
        update_bus_analytics_task.delay(bus_id, visit_count=1)
        UserActivity.objects.create(
            user=request.user, activity_type='bus_visit', bus_id=bus_id,
            description=f"Ghé thăm xe bus", created_by=request.user, modified_by=request.user
        )
        return JsonResponse({'status': 'tracked'})
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def export_user_data(request):
    """Export user data for GDPR compliance"""
    user = request.user
    
    user_data = {
        'user_info': {
            'username': user.username, 'email': user.email,
            'date_joined': user.date_joined.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None,
        },
        'reading_stats': {},
        'activities': [],
        'recommendations': [],
    }
    
    # Reading stats
    if hasattr(user, 'reading_stats'):
        stats = user.reading_stats
        user_data['reading_stats'] = {
            'total_books_borrowed': stats.total_books_borrowed,
            'total_books_returned': stats.total_books_returned,
            'total_pages_read': stats.total_pages_read,
            'reading_streak_days': stats.reading_streak_days,
            'max_reading_streak': stats.max_reading_streak,
            'reputation_score': stats.reputation_score,
            'member_level': stats.member_level,
        }
    
    # Activities
    activities = UserActivity.objects.filter(user=user).select_related('book', 'bus')
    user_data['activities'] = [
        {
            'type': activity.activity_type, 'description': activity.description,
            'points': activity.points, 'created_at': activity.created_at.isoformat(),
            'book_title': activity.book.title if activity.book else None,
            'bus_name': activity.bus.name if activity.bus else None,
        }
        for activity in activities
    ]
    
    # Recommendations
    recommendations = BookRecommendation.objects.filter(user=user).select_related('book')
    user_data['recommendations'] = [
        {
            'book_title': rec.book.title, 'algorithm_type': rec.algorithm_type,
            'score': float(rec.score), 'is_clicked': rec.is_clicked,
            'is_borrowed': rec.is_borrowed, 'created_at': rec.created_at.isoformat(),
        }
        for rec in recommendations
    ]
    
    response = JsonResponse(user_data, json_dumps_params={'ensure_ascii': False, 'indent': 2})
    response['Content-Disposition'] = f'attachment; filename="user_data_{user.username}.json"'
    return response

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_popular_time_slots():
    """Get popular time slots for borrowing"""
    return UserActivity.objects.filter(
        activity_type='borrow',
        created_at__gte=timezone.now() - timedelta(days=30)
    ).annotate(hour=Extract('created_at', 'hour')).values('hour').annotate(count=Count('id')).order_by('-count')[:5]

def get_category_trends():
    """Get trending book categories"""
    return UserActivity.objects.filter(
        activity_type='borrow',
        created_at__gte=timezone.now() - timedelta(days=30)
    ).values('book__category').annotate(count=Count('id')).order_by('-count')[:10]