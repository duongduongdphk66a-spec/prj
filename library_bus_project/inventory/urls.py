# File: inventory/urls.py
from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # LibraryBus URLs
    path('manage/buses/', views.AdminLibraryBusListView.as_view(), name='admin_bus_list'),
    path('buses/', views.LibraryBusListView.as_view(), name='bus_list'),
    path('buses/new/', views.LibraryBusCreateView.as_view(), name='bus_create'),
    path('buses/<uuid:pk>/', views.LibraryBusDetailView.as_view(), name='bus_detail'),
    path('buses/<uuid:pk>/edit/', views.LibraryBusUpdateView.as_view(), name='bus_update'),
    path('buses/<uuid:pk>/update-location/', views.bus_location_update, name='bus_location_update'),

    # Category URLs
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/new/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<slug:slug>/edit/', views.CategoryUpdateView.as_view(), name='category_update'),

    # Book URLs
    path('manage/books/', views.AdminBookListView.as_view(), name='admin_book_list'),
    path('books/', views.BookListView.as_view(), name='book_list'),
    path('books/new/', views.BookCreateView.as_view(), name='book_create'),
    path('books/autocomplete/', views.autocomplete_books, name='book_autocomplete'),
    path('books/<uuid:pk>/', views.BookDetailView.as_view(), name='book_detail'),
    path('books/<uuid:pk>/edit/', views.BookUpdateView.as_view(), name='book_update'),
    path('books/<uuid:pk>/change-status/', views.book_status_change, name='book_status_change'),
    path('books/<uuid:pk>/view-pdf/', views.book_pdf_viewer, name='book_pdf_viewer'),
    path('books/<uuid:pk>/rate/', views.RateBookView.as_view(), name='book_rate'),
    path('books/donate/', views.BookDonationCreateView.as_view(), name='book_donate'),

    # Donation URLs (Admin)
    path('donations/', views.BookDonationListView.as_view(), name='donation_list'),
    path('donations/<int:pk>/change-status/', views.donation_status_change, name='donation_status_change'),


    # Bulk Operations
    path('books/bulk-upload-csv/', views.bulk_book_upload, name='bulk_book_upload'),
    path('books/bulk-upload-pdf/', views.bulk_pdf_upload, name='bulk_pdf_upload'),
    path('books/extract-metadata/', views.extract_pdf_metadata, name='extract_pdf_metadata'),

    # BusRoute URLs
    path('routes/', views.BusRouteListView.as_view(), name='route_list'),
    path('routes/new/', views.BusRouteCreateView.as_view(), name='route_create'),
    path('routes/<uuid:pk>/', views.BusRouteDetailView.as_view(), name='route_detail'),
    path('routes/<uuid:pk>/edit/', views.BusRouteUpdateView.as_view(), name='route_update'),

    # Alert URLs
    path('alerts/', views.alerts_list, name='alerts_list'),
    path('alerts/<uuid:pk>/resolve/', views.alert_resolve, name='alert_resolve'),

    # Export URLs
    path('export/books-csv/', views.export_books_csv, name='export_books_csv'),
    path('export/inventory-report/', views.export_inventory_report, name='export_inventory_report'),
    
    # System URLs
    path('clear-cache/', views.clear_cache, name='clear_cache'),
    
    path('route/<uuid:pk>/toggle/', views.toggle_route_status, name='route_toggle_status'),
    path('route/<uuid:pk>/delete/', views.delete_route, name='route_delete'),
    # API URLs
    path('api/bus-locations/', views.api_bus_locations, name='api_bus_locations'),
    path('api/book-search/', views.api_book_search, name='api_book_search'),
    path('api/dashboard-stats/', views.api_dashboard_stats, name='api_dashboard_stats'),
    path('api/books/<uuid:pk>/analytics/', views.api_book_analytics, name='api_book_analytics'),
    path('api/chatbot/', views.api_chatbot, name='api_chatbot'),
]
