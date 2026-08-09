# ==============================================================================
# File: library_bus_project/urls.py 
# Mô tả: File URL chính của dự án, điều hướng các request đến các ứng dụng con.
# ==============================================================================
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

admin.site.site_header = "Hệ thống Quản lý Thư viện Di động"
admin.site.site_title = "Admin Panel - Thư viện Di động"
admin.site.index_title = "Bảng điều khiển trung tâm"

urlpatterns = [
    # --- ADMIN SITE ---
    # Giao diện quản trị của Django
    path('admin/', admin.site.urls),

    # --- STATIC PAGES ---
    # Các trang tĩnh như trang chủ, giới thiệu, liên hệ
    # Sử dụng TemplateView cho các trang đơn giản không cần logic phức tạp
    path('', TemplateView.as_view(template_name='pages/index.html'), name='index'),
    path('about/', TemplateView.as_view(template_name='pages/about.html'), name='about'),
    path('contact/', TemplateView.as_view(template_name='pages/contact.html'), name='contact'),
    path('faq/', TemplateView.as_view(template_name='pages/faq.html'), name='faq'),
    path('privacy/', TemplateView.as_view(template_name='pages/privacy.html'), name='privacy'),
    path('terms/', TemplateView.as_view(template_name='pages/terms.html'), name='terms'),

    # --- APPLICATION URLS ---
    # Bao gồm các file urls.py của từng ứng dụng con
    # Sử dụng namespace để tránh xung đột tên URL
    path('users/', include('users.urls', namespace='users')),
    path('inventory/', include('inventory.urls', namespace='inventory')),
    path('transactions/', include('transactions.urls', namespace='transactions')),
    path('analytics/', include('analytics.urls', namespace='analytics')),
    path('notifications/', include('notifications.urls', namespace='notifications')),
    path('blog/', include('blog.urls', namespace='blog')),

    # --- API URLS ---
    # (Tùy chọn) Dành cho việc phát triển API sau này
    # path('api/v1/', include('api.urls', namespace='api')),
]

# --- DEBUG TOOLBAR & MEDIA/STATIC FILES ---
# Cấu hình phục vụ file media và static trong môi trường development (DEBUG=True)
if settings.DEBUG:
    # Thêm URL cho các file media được người dùng tải lên
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # Thêm URL cho các file static
    # Lưu ý: Django development server tự động phục vụ file static nếu APP_DIRS=True
    # nhưng thêm dòng này để rõ ràng hơn.
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # (Tùy chọn) Thêm Django Debug Toolbar nếu được cài đặt
    try:
        import debug_toolbar # type: ignore
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass