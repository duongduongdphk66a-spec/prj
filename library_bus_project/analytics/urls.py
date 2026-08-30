# analytics/urls.py
from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Dashboard views
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('admin/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    
    # User analytics
    path('user/stats/', views.UserStatsView.as_view(), name='user_stats'),
    path('user/activities/', views.UserActivitiesView.as_view(), name='user_activities'),
    path('user/export/', views.export_user_data, name='export_user_data'),
    
    # Book analytics
    path('books/', views.BookAnalyticsView.as_view(), name='book_analytics'),
    path('books/<uuid:book_id>/', views.BookDetailAnalyticsView.as_view(), name='book_detail_analytics'),
    
    # Leaderboard & Recommendations
    path('leaderboard/', views.LeaderboardView.as_view(), name='leaderboard'),
    path('recommendations/', views.RecommendationsView.as_view(), name='recommendations'),
    
    # Bus analytics (staff only)
    path('buses/', views.BusAnalyticsView.as_view(), name='bus_analytics'),
    
    # Reports (staff only)
    path('reports/', views.ReportsView.as_view(), name='reports'),
    
    # API endpoints
    path('api/track/book/<uuid:book_id>/', views.track_book_view, name='track_book_view'),
    path('api/track/recommendation/<uuid:recommendation_id>/', views.track_recommendation_click, name='track_recommendation_click'),
    path('api/track/bus/<uuid:bus_id>/', views.track_bus_visit, name='track_bus_visit'),
    path('api/user/activities/', views.get_user_activities_json, name='get_user_activities_json'),
    path('api/analytics/summary/', views.get_analytics_summary_json, name='get_analytics_summary_json'),
]