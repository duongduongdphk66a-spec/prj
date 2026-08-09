from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # Giao diện người dùng
    path('', views.notification_list, name='list'),
    path('<uuid:pk>/', views.notification_detail, name='detail'),
    
    # API endpoints
    path('api/<uuid:pk>/read/', views.mark_notification_read, name='api_mark_read'),
    path('api/mark-all-read/', views.mark_all_read, name='api_mark_all_read'),
]
