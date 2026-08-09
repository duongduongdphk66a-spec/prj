# File: inventory/admin.py 
from django.contrib import admin
from django.utils.html import format_html
from django.http import HttpResponse, JsonResponse
from django.core.files.storage import default_storage
from django.contrib import messages
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.contrib.admin import SimpleListFilter
from django.core.cache import cache
from django.utils import timezone
from django.urls import path, reverse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
import json
from .models import LibraryBus, Category, Book, BookStatusHistory, BusRoute, InventoryAlert

class BookCountFilter(SimpleListFilter):
    title = 'Số lượng sách'
    parameter_name = 'book_count'
    
    def lookups(self, request, model_admin):
        return (('empty', 'Không có sách'), ('low', 'Ít sách (<50)'), ('medium', 'Trung bình (50-200)'), ('high', 'Nhiều sách (>200)'))
    
    def queryset(self, request, queryset):
        queryset = queryset.with_book_counts()
        if self.value() == 'empty': return queryset.filter(total_books=0)
        elif self.value() == 'low': return queryset.filter(total_books__lt=50, total_books__gt=0)
        elif self.value() == 'medium': return queryset.filter(total_books__gte=50, total_books__lte=200)
        elif self.value() == 'high': return queryset.filter(total_books__gt=200)
        return queryset

class ActiveStatusFilter(SimpleListFilter):
    title = 'Trạng thái hoạt động'
    parameter_name = 'is_active_status'
    
    def lookups(self, request, model_admin):
        return (('active', 'Đang hoạt động'), ('inactive', 'Không hoạt động'))
    
    def queryset(self, request, queryset):
        if hasattr(queryset.model, 'is_active'):
            if self.value() == 'active': return queryset.filter(is_active=True)
            elif self.value() == 'inactive': return queryset.filter(is_active=False)
        elif hasattr(queryset.model, 'operating_status'):
            if self.value() == 'active': return queryset.filter(operating_status='active')
            elif self.value() == 'inactive': return queryset.exclude(operating_status='active')
        return queryset

@admin.register(LibraryBus)
class LibraryBusAdmin(admin.ModelAdmin):
    list_display = ('name', 'license_plate', 'operating_status_colored', 'location_display', 'book_stats', 'capacity_usage', 'last_updated')
    list_filter = ('operating_status', BookCountFilter, 'created_at')
    search_fields = ('name', 'license_plate', 'location_name', 'contact_phone')
    list_per_page = 25
    actions = ['mark_as_active', 'mark_as_maintenance', 'clear_cache']
    readonly_fields = ('created_at', 'updated_at', 'current_book_count_display',  '_book_count', '_last_book_update')
    
    def get_queryset(self, request):
        return super().get_queryset(request).with_book_counts()
    
    def operating_status_colored(self, obj):
        colors = {'active': 'green', 'parked': 'orange', 'maintenance': 'red', 'moving': 'blue'}
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', colors.get(obj.operating_status, 'black'), obj.get_operating_status_display())
    operating_status_colored.short_description = 'Trạng thái'
    
    def location_display(self, obj):
        if obj.latitude and obj.longitude: return format_html('{}<br><small>({}, {})</small>', obj.location_name or 'Chưa có tên', obj.latitude, obj.longitude)
        return obj.location_name or 'Chưa cập nhật'
    location_display.short_description = 'Vị trí'
    
    def book_stats(self, obj):
        count = getattr(obj, 'total_books', obj.current_book_count)
        return format_html('<strong>{}</strong> quyển', count)
    book_stats.short_description = 'Số sách'
    
    def capacity_usage(self, obj):
        count = getattr(obj, 'total_books', obj.current_book_count)
        usage_pct = (count / obj.capacity * 100) if obj.capacity > 0 else 0
        color = 'red' if usage_pct > 90 else 'orange' if usage_pct > 70 else 'green'
        return format_html('<span style="color: {};">{}</span>', color, f"{usage_pct:.1f}%")
    capacity_usage.short_description = 'Tỷ lệ sử dụng'
    
    def current_book_count_display(self, obj):
        return f'{obj.current_book_count} quyển (Cache: {obj._book_count})'
    current_book_count_display.short_description = 'Số sách hiện tại'
    
    def last_updated(self, obj): return obj.updated_at.strftime('%d/%m/%Y %H:%M')
    last_updated.short_description = 'Cập nhật'

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'color_preview', 'icon_display', 'book_count', 'is_active', 'created_at')
    list_filter = (ActiveStatusFilter, 'created_at')
    search_fields = ('name', 'description', 'slug')
    list_editable = ('is_active',)
    prepopulated_fields = {'slug': ('name',)}
    
    def get_queryset(self, request):
        return super().get_queryset(request).with_book_counts()
    
    def color_preview(self, obj):
        return format_html('<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc; border-radius: 3px;"></div>', obj.color_code)
    color_preview.short_description = 'Màu'
    
    def icon_display(self, obj): return obj.icon if obj.icon else '-'
    icon_display.short_description = 'Icon'
    
    def book_count(self, obj):
        return getattr(obj, 'total_books', obj._book_count)
    book_count.short_description = 'Số sách'

class BookStatusHistoryInline(admin.TabularInline):
    model = BookStatusHistory
    extra = 0
    readonly_fields = ('created_at', 'from_status', 'to_status', 'changed_by')
    can_delete = False
    max_num = 5
    ordering = ['-created_at']
    
    def has_add_permission(self, request, obj=None): return False

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'category', 'status_colored', 'location', 'condition_badge', 'digital_badge', 'file_status', 'analytics_summary', 'last_updated')
    list_filter = ('status', 'category', 'location', 'is_digital_only', 'language', 'condition', 'created_at')
    search_fields = ('title', 'author', 'isbn', 'publisher')
    list_per_page = 30
    readonly_fields = ('last_status_change', 'created_at', 'updated_at',  '_average_rating', '_total_borrows', '_popularity_score', 'file_info_display')
    autocomplete_fields = ['category', 'location']
    inlines = [BookStatusHistoryInline]
    actions = ['mark_available', 'mark_maintenance', 'update_analytics', 'bulk_pdf_upload']
    
    fieldsets = (
        ('Thông tin cơ bản', {'fields': ('title', 'author', 'category', 'description')}),
        ('Media & Files', {'fields': ('cover_image', 'pdf_file', 'file_info_display'), 'classes': ('collapse',)}),
        ('Thông tin xuất bản', {'fields': ('publisher', 'publication_year', 'page_count', 'isbn', 'language')}),
        ('Tồn kho & Trạng thái', {'fields': ('status', 'condition', 'location', 'is_digital_only')}),
        ('Analytics (Tự động)', {'fields': ('analytics_summary_display', '_average_rating', '_total_borrows', '_popularity_score'), 'classes': ('collapse',)}),
        ('Metadata', {'fields': ('created_at', 'updated_at', 'last_status_change'), 'classes': ('collapse',)})
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).with_relations().with_analytics()
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('bulk-pdf-upload/', self.admin_site.admin_view(self.bulk_pdf_upload_view), name='inventory_book_bulk_pdf_upload'),
            path('update-book-info/', self.admin_site.admin_view(self.update_book_info_view), name='inventory_book_update_info'),
        ]
        return custom_urls + urls
    
    def status_colored(self, obj):
        colors = {'available': 'green', 'checked_out': 'orange', 'reserved': 'blue', 'maintenance': 'red', 'lost': 'gray'}
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', colors.get(obj.status, 'black'), obj.get_status_display())
    status_colored.short_description = 'Trạng thái'
    
    def condition_badge(self, obj):
        colors = {'new': 'green', 'like_new': 'lightgreen', 'good': 'blue', 'fair': 'orange', 'poor': 'red'}
        return format_html('<span style="background: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{}</span>', colors.get(obj.condition, 'gray'), obj.get_condition_display())
    condition_badge.short_description = 'Tình trạng'
    
    def digital_badge(self, obj):
        return format_html('<span style="background: purple; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">Digital</span>') if obj.is_digital_only else '-'
    digital_badge.short_description = 'Loại'
    
    def file_status(self, obj):
        has_pdf = '📄' if obj.pdf_file else '❌'
        has_image = '🖼️' if obj.cover_image else '❌'
        return format_html('{} {}', has_pdf, has_image)
    file_status.short_description = 'Files'
    
    def file_info_display(self, obj):
        info = []
        if obj.pdf_file:
            try:
                size = obj.pdf_file.size / 1024 / 1024  # MB
                info.append(f'PDF: {size:.1f} MB')
            except:
                info.append('PDF: Có file')
        if obj.cover_image:
            try:
                size = obj.cover_image.size / 1024  # KB
                info.append(f'Ảnh: {size:.1f} KB')
            except:
                info.append('Ảnh: Có file')
        return ', '.join(info) if info else 'Chưa có file'
    file_info_display.short_description = 'Thông tin file'
    
    def analytics_summary(self, obj):
        return format_html('⭐ {} | 📚 {} | 🔥 {}', f"{obj.average_rating:.1f}", obj.total_borrows, f"{obj._popularity_score:.0f}")
    analytics_summary.short_description = 'Rating | Mượn | Phổ biến'
    
    def last_updated(self, obj): return obj.updated_at.strftime('%d/%m/%Y %H:%M')
    last_updated.short_description = 'Cập nhật'
    
    def bulk_pdf_upload_view(self, request):
        """View để upload PDF hàng loạt"""
        if request.method == 'POST':
            return self.handle_bulk_pdf_upload(request)
        
        context = {
            'title': 'Upload PDF hàng loạt',
            'books_without_pdf': Book.objects.filter(pdf_file='').count(),
            'opts': self.model._meta,
            'has_view_permission': True,
        }
        return render(request, 'admin/inventory/book/bulk_pdf_upload.html', context)
    
    @method_decorator(csrf_exempt)
    def handle_bulk_pdf_upload(self, request):
        """Xử lý upload PDF hàng loạt"""
        try:
            files = request.FILES.getlist('pdf_files')
            updated_count = 0
            
            for file in files:
                # Tìm sách dựa trên tên file (có thể customize logic này)
                filename = file.name.replace('.pdf', '')
                book = Book.objects.filter(title__icontains=filename).first()
                
                if book and not book.pdf_file:
                    book.pdf_file = file
                    book.save()
                    updated_count += 1
            
            return JsonResponse({'success': True, 'updated': updated_count})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    def update_book_info_view(self, request):
        """View để cập nhật thông tin sách từ metadata PDF"""
        if request.method == 'POST':
            book_ids = request.POST.getlist('book_ids')
            updated_count = 0
            
            for book_id in book_ids:
                try:
                    book = Book.objects.get(id=book_id)
                    if book.pdf_file:
                        # Ở đây có thể thêm logic extract metadata từ PDF
                        # Ví dụ: sử dụng PyPDF2 hoặc pdfplumber
                        self.extract_pdf_metadata(book)
                        updated_count += 1
                except Book.DoesNotExist:
                    continue
            
            messages.success(request, f'Đã cập nhật thông tin cho {updated_count} sách.')
            return self.changelist_view(request)
        
        books_with_pdf = Book.objects.filter(pdf_file__isnull=False).exclude(pdf_file='')
        context = {
            'title': 'Cập nhật thông tin từ PDF',
            'books': books_with_pdf,
            'opts': self.model._meta,
        }
        return render(request, 'admin/inventory/book/update_info.html', context)
    
    def extract_pdf_metadata(self, book):
        """Extract metadata từ PDF file"""
        try:
            # Placeholder - implement actual PDF metadata extraction
            # Có thể sử dụng PyPDF2, pdfplumber, hoặc libraries khác
            pass
        except Exception as e:
            print(f"Error extracting metadata for {book.title}: {e}")
    
    def bulk_pdf_upload(self, request, queryset):
        """Action để redirect đến bulk upload page"""
        return self.bulk_pdf_upload_view(request)
    bulk_pdf_upload.short_description = 'Upload PDF hàng loạt'
    
    def changelist_view(self, request, extra_context=None):
        """Override changelist để thêm custom buttons"""
        extra_context = extra_context or {}
        extra_context['bulk_pdf_upload_url'] = reverse('admin:inventory_book_bulk_pdf_upload')
        extra_context['update_book_info_url'] = reverse('admin:inventory_book_update_info')
        return super().changelist_view(request, extra_context=extra_context)

@admin.register(BookStatusHistory)
class BookStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('book', 'from_status', 'to_status', 'changed_by', 'created_at')
    list_filter = ('from_status', 'to_status', 'created_at')
    search_fields = ('book__title', 'book__author', 'book__isbn')
    readonly_fields = ('created_at',)
    # date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('book', 'changed_by')
    
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False

@admin.register(BusRoute)
class BusRouteAdmin(admin.ModelAdmin):
    list_display = ('route_name', 'bus', 'stops_count', 'is_active', 'created_at')
    list_filter = (ActiveStatusFilter, 'bus', 'created_at')
    search_fields = ('route_name', 'bus__name', 'bus__license_plate')
    list_editable = ('is_active',)
    autocomplete_fields = ['bus']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('bus')
    
    def stops_count(self, obj):
        try: return len(obj.stops) if obj.stops else 0
        except: return 0
    stops_count.short_description = 'Số điểm dừng'

@admin.register(InventoryAlert)
class InventoryAlertAdmin(admin.ModelAdmin):
    list_display = ('bus', 'alert_type_badge', 'severity_badge', 'message_preview', 'status_badge', 'created_at', 'is_resolved')
    list_filter = ('alert_type', 'severity', 'is_resolved', 'bus', 'created_at')
    search_fields = ('message', 'bus__name', 'bus__license_plate')
    list_editable = ('is_resolved',)
    actions = ['mark_resolved', 'mark_unresolved']
    # date_hierarchy = 'created_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('bus')
    
    def alert_type_badge(self, obj):
        colors = {'low_stock': 'red', 'overstock': 'orange', 'popular_demand': 'green', 'maintenance': 'purple'}
        return format_html('<span style="background: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{}</span>', colors.get(obj.alert_type, 'gray'), obj.get_alert_type_display())
    alert_type_badge.short_description = 'Loại cảnh báo'
    
    def severity_badge(self, obj):
        colors = {'low': 'green', 'medium': 'orange', 'high': 'red', 'critical': 'darkred'}
        return format_html('<span style="background: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{}</span>', colors.get(obj.severity, 'gray'), obj.get_severity_display())
    severity_badge.short_description = 'Mức độ'
    
    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Nội dung'
    
    def status_badge(self, obj):
        if obj.is_resolved: return format_html('<span style="color: green;">✓ Đã xử lý</span>')
        return format_html('<span style="color: red;">⚠ Chưa xử lý</span>')
    status_badge.short_description = 'Trạng thái'

admin.site.site_header = "Hệ thống quản lý thư viện di động"
admin.site.site_title = "Library Bus Admin"
admin.site.index_title = "Bảng điều khiển quản lý"