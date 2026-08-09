# File: transactions/admin.py
# Mô tả: Cấu hình giao diện admin cho ứng dụng Transactions
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Q, Count, Sum
from django.http import HttpResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone
from .models import BorrowRecord, BookReservation, ShippingRequest, FinePayment, BulkTransaction
import csv

# === INLINE CLASSES ===
class FinePaymentInline(admin.TabularInline):
    model = FinePayment
    extra = 0
    readonly_fields = ('payment_date', 'final_amount', 'payment_status')
    fields = ('amount', 'discount_amount', 'payment_method', 'payment_status', 'processed_by', 'notes')

class ShippingRequestInline(admin.TabularInline):
    model = ShippingRequest
    extra = 0
    fields = ('status', 'shipping_partner', 'tracking_code', 'shipping_fee')
    readonly_fields = ('tracking_code',)

# === MAIN ADMIN CLASSES ===
@admin.register(BorrowRecord)
class BorrowRecordAdmin(admin.ModelAdmin):
    list_display = ('user_link', 'book_link', 'borrow_date', 'due_date_display', 'return_date', 'status_display', 'fine_display', 'actions_display')
    list_display_links = ('user_link', 'book_link')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'book__title', 'book__isbn')
    list_filter = ('borrow_date', 'due_date', 'return_date', 'is_lost', 'is_damaged', 'pickup_location', 'renewal_count')
    # date_hierarchy = 'borrow_date'
    autocomplete_fields = ['user', 'book', 'pickup_location', 'return_location', 'staff_processed']
    readonly_fields = ('borrow_date', 'is_overdue', 'days_overdue', 'fine_amount', 'can_renew')
    inlines = [FinePaymentInline, ShippingRequestInline]
    actions = ['mark_as_returned', 'mark_as_lost', 'bulk_renew', 'export_to_csv']
    list_per_page = 25
    
    fieldsets = (
        ('Thông tin cơ bản', {'fields': ('user', 'book', 'borrow_date', 'due_date', 'return_date')}),
        ('Trạng thái', {'fields': ('renewal_count', 'is_lost', 'is_damaged', ('is_overdue', 'days_overdue', 'fine_amount', 'can_renew'))}),
        ('Địa điểm', {'fields': ('pickup_location', 'return_location')}),
        ('Xử lý', {'fields': ('staff_processed', 'notes')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'book', 'pickup_location', 'return_location', 'staff_processed').prefetch_related('payments')

    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username)
    user_link.short_description = 'Người mượn'

    def book_link(self, obj):
        url = reverse('admin:inventory_book_change', args=[obj.book.pk])
        return format_html('<a href="{}">{}</a>', url, obj.book.title)
    book_link.short_description = 'Sách'

    def due_date_display(self, obj):
        if obj.is_overdue:
            return format_html('<span style="color: red; font-weight: bold;">{}</span>', obj.due_date)
        elif obj.due_date and (obj.due_date - timezone.now().date()).days <= 3:
            return format_html('<span style="color: orange;">{}</span>', obj.due_date)
        return obj.due_date
    due_date_display.short_description = 'Hạn trả'

    def status_display(self, obj):
        if obj.return_date:
            return format_html('<span style="color: green;">✓ Đã trả</span>')
        elif obj.is_lost:
            return format_html('<span style="color: red;">⚠ Mất sách</span>')
        elif obj.is_damaged:
            return format_html('<span style="color: orange;">🔧 Hỏng</span>')
        elif obj.is_overdue:
            return format_html('<span style="color: red;">⏰ Quá hạn {} ngày</span>', obj.days_overdue)
        else:
            return format_html('<span style="color: blue;">📖 Đang mượn</span>')
    status_display.short_description = 'Trạng thái'

    def fine_display(self, obj):
        if obj.fine_amount > 0:
            return format_html('<span style="color: red; font-weight: bold;">{}đ</span>', "{:,.0f}".format(obj.fine_amount))
        return '-'
    fine_display.short_description = 'Phạt'

    def actions_display(self, obj):
        actions = []
        if not obj.return_date:
            if obj.can_renew:
                actions.append('<a href="#" onclick="renewBook({})">Gia hạn</a>'.format(obj.pk))
            actions.append('<a href="#" onclick="returnBook({})">Trả sách</a>'.format(obj.pk))
        return format_html(' | '.join(actions)) if actions else '-'
    actions_display.short_description = 'Thao tác'

    def mark_as_returned(self, request, queryset):
        count = 0
        for record in queryset.filter(return_date__isnull=True):
            record.return_book(returned_by=request.user)
            count += 1
        self.message_user(request, f'Đã trả {count} sách.')
    mark_as_returned.short_description = 'Đánh dấu đã trả'

    def mark_as_lost(self, request, queryset):
        updated = queryset.update(is_lost=True)
        self.message_user(request, f'Đã đánh dấu {updated} sách bị mất.')
    mark_as_lost.short_description = 'Đánh dấu mất sách'

    def bulk_renew(self, request, queryset):
        count = 0
        for record in queryset.filter(return_date__isnull=True):
            if record.can_renew:
                record.renew()
                count += 1
        self.message_user(request, f'Đã gia hạn {count} sách.')
    bulk_renew.short_description = 'Gia hạn hàng loạt'

    def export_to_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="borrow_records.csv"'
        writer = csv.writer(response)
        writer.writerow(['Người mượn', 'Sách', 'Ngày mượn', 'Hạn trả', 'Ngày trả', 'Trạng thái', 'Phạt'])
        for obj in queryset:
            writer.writerow([obj.user.username, obj.book.title, obj.borrow_date, obj.due_date, obj.return_date or '', 'Quá hạn' if obj.is_overdue else 'Bình thường', obj.fine_amount])
        return response
    export_to_csv.short_description = 'Xuất CSV'

@admin.register(BookReservation)
class BookReservationAdmin(admin.ModelAdmin):
    list_display = ('user_link', 'book_link', 'queue_position', 'status_display', 'expires_date', 'notification_sent', 'created_at')
    list_display_links = ('user_link', 'book_link')
    search_fields = ('user__username', 'book__title', 'book__isbn')
    list_filter = ('is_fulfilled', 'notification_sent', 'expires_date', 'preferred_pickup_location')
    autocomplete_fields = ['user', 'book', 'preferred_pickup_location']
    readonly_fields = ('queue_position', 'fulfilled_date')
    actions = ['fulfill_reservations', 'send_notifications', 'cancel_expired']
    list_per_page = 25

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'book', 'preferred_pickup_location')

    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username)
    user_link.short_description = 'Người đặt'

    def book_link(self, obj):
        url = reverse('admin:inventory_book_change', args=[obj.book.pk])
        return format_html('<a href="{}">{}</a>', url, obj.book.title)
    book_link.short_description = 'Sách'

    def status_display(self, obj):
        if obj.is_fulfilled:
            return format_html('<span style="color: green;">✓ Đã thực hiện</span>')
        elif obj.expires_date < timezone.now().date():
            return format_html('<span style="color: red;">⏰ Hết hạn</span>')
        else:
            return format_html('<span style="color: blue;">📋 Đang chờ (#{0})</span>', obj.queue_position)
    status_display.short_description = 'Trạng thái'

    def fulfill_reservations(self, request, queryset):
        count = 0
        for reservation in queryset.filter(is_fulfilled=False):
            reservation.fulfill()
            count += 1
        self.message_user(request, f'Đã thực hiện {count} yêu cầu đặt trước.')
    fulfill_reservations.short_description = 'Thực hiện đặt trước'

    def send_notifications(self, request, queryset):
        # Logic gửi thông báo sẽ được implement sau
        count = queryset.filter(notification_sent=False).update(notification_sent=True)
        self.message_user(request, f'Đã gửi thông báo cho {count} yêu cầu.')
    send_notifications.short_description = 'Gửi thông báo'

    def cancel_expired(self, request, queryset):
        expired = queryset.filter(is_fulfilled=False, expires_date__lt=timezone.now().date())
        count = expired.delete()[0]
        self.message_user(request, f'Đã hủy {count} yêu cầu hết hạn.')
    cancel_expired.short_description = 'Hủy yêu cầu hết hạn'

@admin.register(ShippingRequest)
class ShippingRequestAdmin(admin.ModelAdmin):
    list_display = ('user_link', 'status','book_link', 'status_display', 'shipping_partner', 'tracking_code', 'shipping_fee', 'created_at')
    list_display_links = ('user_link', 'book_link')
    search_fields = ('user__username', 'book__title', 'tracking_code', 'recipient_name', 'phone_number')
    list_filter = ('status', 'shipping_partner', 'created_at')
    list_editable = ('status',)
    autocomplete_fields = ['user', 'book', 'borrow_record']
    readonly_fields = ('tracking_code', 'actual_delivery')
    actions = ['generate_tracking_codes', 'mark_as_shipped', 'mark_as_delivered']
    list_per_page = 25

    fieldsets = (
        ('Thông tin đơn hàng', {'fields': ('user', 'book', 'borrow_record', 'status')}),
        ('Thông tin giao hàng', {'fields': ('recipient_name', 'phone_number', 'shipping_address')}),
        ('Vận chuyển', {'fields': ('shipping_partner', 'tracking_code', 'shipping_fee', 'estimated_delivery', 'actual_delivery')}),
        ('Ghi chú', {'fields': ('delivery_notes', 'internal_notes')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'book', 'borrow_record')

    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username)
    user_link.short_description = 'Người nhận'

    def book_link(self, obj):
        url = reverse('admin:inventory_book_change', args=[obj.book.pk])
        return format_html('<a href="{}">{}</a>', url, obj.book.title)
    book_link.short_description = 'Sách'

    def status_display(self, obj):
        status_colors = {'pending': 'orange', 'processing': 'blue', 'shipped': 'purple', 'delivered': 'green', 'failed': 'red', 'cancelled': 'gray'}
        status_icons = {'pending': '⏳', 'processing': '📦', 'shipped': '🚚', 'delivered': '✅', 'failed': '❌', 'cancelled': '🚫'}
        color = status_colors.get(obj.status, 'black')
        icon = status_icons.get(obj.status, '❓')
        return format_html('<span style="color: {};">{} {}</span>', color, icon, obj.get_status_display())
    status_display.short_description = 'Trạng thái'

    def generate_tracking_codes(self, request, queryset):
        count = 0
        for shipping in queryset.filter(tracking_code=''):
            shipping.generate_tracking_code()
            count += 1
        self.message_user(request, f'Đã tạo mã tracking cho {count} đơn hàng.')
    generate_tracking_codes.short_description = 'Tạo mã tracking'

    def mark_as_shipped(self, request, queryset):
        count = 0
        for shipping in queryset.filter(status__in=['pending', 'processing']):
            shipping.mark_as_shipped()
            count += 1
        self.message_user(request, f'Đã đánh dấu {count} đơn hàng đã gửi.')
    mark_as_shipped.short_description = 'Đánh dấu đã gửi'

    def mark_as_delivered(self, request, queryset):
        count = 0
        for shipping in queryset.filter(status='shipped'):
            shipping.status = 'delivered'
            shipping.actual_delivery = timezone.now()
            shipping.save()
            count += 1
        self.message_user(request, f'Đã đánh dấu {count} đơn hàng đã giao.')
    mark_as_delivered.short_description = 'Đánh dấu đã giao'

@admin.register(FinePayment)
class FinePaymentAdmin(admin.ModelAdmin):
    list_display = ('borrow_record_link', 'final_amount_display', 'payment_status_display', 'payment_method', 'payment_date', 'processed_by')
    list_display_links = ('borrow_record_link',)
    search_fields = ('borrow_record__user__username', 'borrow_record__book__title', 'transaction_id', 'gateway_reference')
    list_filter = ('payment_status', 'payment_method', 'payment_date', 'processed_by')
    autocomplete_fields = ['borrow_record', 'processed_by']
    readonly_fields = ('final_amount', 'payment_date')
    actions = ['mark_as_completed', 'apply_discount', 'export_payments']
    list_per_page = 25

    fieldsets = (
        ('Thông tin thanh toán', {'fields': ('borrow_record', 'amount', 'discount_amount', 'final_amount')}),
        ('Phương thức', {'fields': ('payment_method', 'payment_status')}),
        ('Giao dịch', {'fields': ('transaction_id', 'gateway_reference', 'processed_by')}),
        ('Ghi chú', {'fields': ('notes',)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('borrow_record__user', 'borrow_record__book', 'processed_by')

    def borrow_record_link(self, obj):
        url = reverse('admin:transactions_borrowrecord_change', args=[obj.borrow_record.pk])
        return format_html('<a href="{}">{} - {}</a>', url, obj.borrow_record.user.username, obj.borrow_record.book.title)
    borrow_record_link.short_description = 'Giao dịch mượn'

    def final_amount_display(self, obj):
        if obj.discount_amount > 0:
            return format_html('<span style="text-decoration: line-through;">{}đ</span> <span style="color: green; font-weight: bold;">{}đ</span>', "{:,.0f}".format(obj.amount), "{:,.0f}".format(obj.final_amount))
        return format_html('<span style="font-weight: bold;">{}đ</span>', "{:,.0f}".format(obj.final_amount))
    final_amount_display.short_description = 'Số tiền'

    def payment_status_display(self, obj):
        status_colors = {'pending': 'orange', 'processing': 'blue', 'completed': 'green', 'failed': 'red', 'refunded': 'purple'}
        color = status_colors.get(obj.payment_status, 'black')
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.get_payment_status_display())
    payment_status_display.short_description = 'Trạng thái'

    def mark_as_completed(self, request, queryset):
        count = queryset.exclude(payment_status='completed').update(payment_status='completed')
        self.message_user(request, f'Đã hoàn thành {count} thanh toán.')
    mark_as_completed.short_description = 'Đánh dấu hoàn thành'

    def apply_discount(self, request, queryset):
        # Logic áp dụng giảm giá sẽ được implement với form riêng
        self.message_user(request, 'Chức năng áp dụng giảm giá đang được phát triển.')
    apply_discount.short_description = 'Áp dụng giảm giá'

    def export_payments(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="payments.csv"'
        writer = csv.writer(response)
        writer.writerow(['Người mượn', 'Sách', 'Số tiền gốc', 'Giảm giá', 'Thành tiền', 'Phương thức', 'Trạng thái', 'Ngày thanh toán'])
        for obj in queryset:
            writer.writerow([obj.borrow_record.user.username, obj.borrow_record.book.title, obj.amount, obj.discount_amount, obj.final_amount, obj.get_payment_method_display(), obj.get_payment_status_display(), obj.payment_date])
        return response
    export_payments.short_description = 'Xuất CSV'

@admin.register(BulkTransaction)
class BulkTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_type', 'processed_by', 'records_processed', 'records_failed', 'is_completed', 'created_at')
    list_filter = ('transaction_type', 'is_completed', 'created_at')
    search_fields = ('processed_by__username',)
    readonly_fields = ('records_processed', 'records_failed', 'processing_log', 'created_at', 'updated_at')
    autocomplete_fields = ['processed_by']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('processed_by')

# === CUSTOM ADMIN SITE CUSTOMIZATION ===
admin.site.site_header = 'Quản lý Thư viện'
admin.site.site_title = 'Library Admin'
admin.site.index_title = 'Bảng điều khiển Quản lý'