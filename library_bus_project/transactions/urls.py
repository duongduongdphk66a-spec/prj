# File: transactions/urls.py
# Mô tả: Định tuyến URL cho ứng dụng transactions.
# ==============================================================================

from django.urls import path
from . import views

app_name = 'transactions'

urlpatterns = [
    # ==========================================================================
    # Dashboard & Báo cáo
    # ==========================================================================
    path('', views.dashboard, name='dashboard'),
    path('statistics/', views.statistics_view, name='statistics'),

    # ==========================================================================
    # Quản lý Mượn/Trả sách (Borrow Records)
    # ==========================================================================
    path('borrows/', views.BorrowListView.as_view(), name='borrow_list'),
    path('borrows/new/', views.BorrowCreateView.as_view(), name='borrow_create'),
    path('borrows/<uuid:pk>/', views.BorrowDetailView.as_view(), name='borrow_detail'),
    path('borrows/<uuid:pk>/return/', views.return_book, name='return_book'),
    path('borrows/<uuid:pk>/renew/', views.renew_book, name='renew_book'),

    # ==========================================================================
    # Quản lý Đặt trước sách (Reservations)
    # ==========================================================================
    path('reservations/', views.ReservationListView.as_view(), name='reservation_list'),
    path('reservations/book/<uuid:book_id>/new/', views.CreateReservationView.as_view(), name='reservation_create'),
    path('reservations/<uuid:pk>/', views.ReservationDetailView.as_view(), name='reservation_detail'),
    path('reservations/<uuid:pk>/cancel/', views.cancel_reservation, name='reservation_cancel'),

    # ==========================================================================
    # Quản lý Giao hàng & Phí phạt (Shipping & Fines)
    # (Thêm các URL này khi các view tương ứng được triển khai)
    # ==========================================================================
    # path('shipping/', views.ShippingListView.as_view(), name='shipping_list'),
    # path('shipping/new/', views.ShippingCreateView.as_view(), name='shipping_create'),
    # path('fines/', views.FineListView.as_view(), name='fine_list'),
    # path('fines/<uuid:pk>/pay/', views.pay_fine, name='pay_fine'),

    # ==========================================================================
    # Thao tác hàng loạt & Công cụ Admin
    # ==========================================================================
    path('bulk-operations/', views.BulkOperationView.as_view(), name='bulk_operations'),

    # ==========================================================================
    # API Endpoints (AJAX)
    # ==========================================================================
    path('ajax/book-info/', views.ajax_book_info, name='ajax_book_info'),
    path('ajax/user-info/', views.ajax_user_info, name='ajax_user_info'),
]