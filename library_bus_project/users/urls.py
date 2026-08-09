# File: users/urls.py
# Mô tả: Định tuyến URL cho ứng dụng Users
# ==============================================================================

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'users'

urlpatterns = [
    # ==========================================================================
    # URL cho xác thực (Authentication)
    # ==========================================================================
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # ==========================================================================
    # URL cho xác thực email
    # ==========================================================================
    path('verify/<str:uidb64>/<str:token>/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification, name='resend_verification'),

    # ==========================================================================
    # URL cho khôi phục mật khẩu (sử dụng các view có sẵn của Django)
    # ==========================================================================
    path('password-reset/', views.password_reset_request, name='password_reset_request'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='users/password/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name="users/password/password_reset_confirm.html"), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='users/password/password_reset_complete.html'), name='password_reset_complete'),

    # ==========================================================================
    # URL cho Profile người dùng
    # ==========================================================================
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/export/', views.export_profile_data, name='export_profile_data'),
    path('profile/<str:username>/', views.profile_detail, name='profile_detail'),

    # ==========================================================================
    # URL cho Cài đặt (Settings)
    # ==========================================================================
    path('settings/', views.settings_view, name='settings'),
    path('settings/password/', views.change_password, name='change_password'),
    path('settings/preferences/', views.preferences_view, name='preferences'),
    path('settings/interests/', views.interests_view, name='interests'),
    path('settings/interests/<int:interest_id>/delete/', views.delete_interest, name='delete_interest'),

    # ==========================================================================
    # URL cho tính năng xã hội (Social)
    # ==========================================================================
    path('users/', views.UserListView.as_view(), name='user_list'),
    
    # ==========================================================================
    # URL cho Dashboard và các trang khác
    # ==========================================================================
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('activity/', views.activity_history, name='activity_history'),
    path('membership/upgrade/', views.membership_upgrade, name='membership_upgrade'),

    # ==========================================================================
    # URL cho AJAX
    # ==========================================================================
    path('ajax/profile-stats/', views.ajax_profile_stats, name='ajax_profile_stats'),
    path('ajax/avatar/update/', views.ajax_update_avatar, name='ajax_update_avatar'),

    # ==========================================================================
    # URL cho quản lý (Admin-like features)
    # ==========================================================================
    path('manage/users/', views.UserManagementView.as_view(), name='user_management'),
]
