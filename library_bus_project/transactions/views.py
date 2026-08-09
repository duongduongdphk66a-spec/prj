# File: transactions/views.py

import logging
from typing import Any, Dict
from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, FormView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import User
# Local application imports
from .models import BorrowRecord, BookReservation, ShippingRequest, FinePayment
from .forms import (
    UserBorrowRequestForm,
    BorrowRecordForm, BorrowReturnForm, BookReservationForm, ShippingRequestForm,
    RenewalForm, FinePaymentForm, BulkOperationForm, AdminSearchForm
)
from .services import TransactionService, ReportService, AnalyticsService, NotificationService
from inventory.models import Book

# Get an instance of a logger
logger = logging.getLogger(__name__)

# === HELPER FUNCTIONS FOR PERMISSIONS ===

def is_librarian(user):
    """Check if the user is a staff member or belongs to the 'Librarian' group."""
    return user.is_authenticated and (user.is_staff or user.groups.filter(name='Librarian').exists())

class LibrarianRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure the user is a librarian."""
    def test_func(self):
        return is_librarian(self.request.user)

# === DASHBOARD & STATISTICS VIEWS ===

@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """
    Displays a dashboard with relevant transaction information.
    Shows admin-level stats for staff and user-specific data for regular users.
    """
    context = {}
    user = request.user
    try:
        if is_librarian(user):
            # Librarian/Admin dashboard
            context = ReportService.get_monthly_report(timezone.now().year, timezone.now().month)
            context['pending_reservations'] = BookReservation.objects.active().count()
            context['recent_borrows'] = BorrowRecord.objects.select_related('user', 'book').order_by('-borrow_date')[:10]
        else:
            # Regular user dashboard
            context = ReportService.get_user_statistics(user)
            context['active_borrows'] = BorrowRecord.objects.by_user(user).active_borrows().select_related('book')
            context['active_reservations'] = BookReservation.objects.filter(user=user, is_fulfilled=False).select_related('book')

    except Exception as e:
        logger.error(f"Error loading dashboard for {user.username}: {e}")
        messages.error(request, "Không thể tải dữ liệu dashboard. Vui lòng thử lại.")

    return render(request, 'transactions/dashboard.html', context)


@login_required
@user_passes_test(is_librarian)
def statistics_view(request: HttpRequest) -> HttpResponse:
    """
    Displays advanced analytics and statistics for librarians.
    """
    try:
        context = {
            'borrowing_trends': AnalyticsService.get_borrowing_trends(days=30),
            'popular_books': AnalyticsService.get_popular_books(limit=10),
            'user_insights': AnalyticsService.get_user_behavior_insights(),
            'overdue_report': ReportService.get_overdue_report(),
        }
    except Exception as e:
        logger.error(f"Error loading statistics page: {e}")
        messages.error(request, "Không thể tải dữ liệu thống kê.")
        context = {}
    return render(request, 'transactions/statistics.html', context)


# === BORROW RECORD VIEWS (CLASS-BASED) ===

class BorrowListView(LoginRequiredMixin, ListView):
    """Displays a list of borrow records."""
    model = BorrowRecord
    template_name = 'transactions/borrow_list.html'
    context_object_name = 'borrows'
    paginate_by = 20

    def get_queryset(self) -> QuerySet[BorrowRecord]:
        """
        Filter records based on user role and query parameters.
        """
        user = self.request.user
        if is_librarian(user):
            queryset = BorrowRecord.objects.select_related('user', 'book').all()
        else:
            queryset = BorrowRecord.objects.filter(user=user).select_related('book')

        # Filtering logic
        status_filter = self.request.GET.get('status')
        if status_filter == 'active':
            queryset = queryset.active_borrows()
        elif status_filter == 'overdue':
            queryset = queryset.overdue()
        elif status_filter == 'returned':
            queryset = queryset.returned()

        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(book__title__icontains=search_query) |
                Q(user__username__icontains=search_query)
            )

        return queryset.order_by('-borrow_date')

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['search_form'] = AdminSearchForm(self.request.GET)
        return context


class BorrowDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Displays details of a single borrow record."""
    model = BorrowRecord
    template_name = 'transactions/borrow_detail.html'
    context_object_name = 'borrow'

    def test_func(self) -> bool:
        """Allow access if user is staff or the owner of the record."""
        return is_librarian(self.request.user) or self.get_object().user == self.request.user

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        borrow = self.get_object()
        context['payments'] = borrow.payments.all()
        context['shipping_request'] = getattr(borrow, 'shipping_request', None)
        # Add forms for actions
        if not borrow.return_date:
            context['return_form'] = BorrowReturnForm(borrow_record=borrow)
            if borrow.can_renew:
                context['renewal_form'] = RenewalForm(borrow_record=borrow)
        return context


class BorrowCreateView(LoginRequiredMixin, LibrarianRequiredMixin, CreateView):
    """View for librarians to create a new borrow record."""
    model = BorrowRecord
    form_class = BorrowRecordForm
    template_name = 'transactions/borrow_create.html'

    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form: BorrowRecordForm) -> HttpResponse:
        """
        Process the valid form using the TransactionService.
        """
        try:
            borrow = TransactionService.create_borrow(
                user=form.cleaned_data['user'],
                book=form.cleaned_data['book'],
                due_days=form.cleaned_data['due_days'],
                pickup_location=form.cleaned_data['pickup_location'],
                staff_member=self.request.user,
                notes=form.cleaned_data['notes']
            )
            messages.success(self.request, f'Đã tạo phiếu mượn cho {borrow.user.username} - {borrow.book.title}')
            logger.info(f"Borrow record {borrow.id} created by {self.request.user.username}")
            return redirect('transactions:borrow_detail', pk=borrow.pk)
        except Exception as e:
            logger.error(f"Error creating borrow record: {e}")
            messages.error(self.request, f'Lỗi khi tạo phiếu mượn: {e}')
            return self.form_invalid(form)


# === BORROW ACTIONS (FUNCTION-BASED FOR SIMPLICITY) ===

@login_required
@require_http_methods(["POST"])
def return_book(request: HttpRequest, pk: int) -> HttpResponse:
    """Handles the book return process."""
    borrow = get_object_or_404(BorrowRecord, pk=pk)
    if not (is_librarian(request.user) or borrow.user == request.user):
        messages.error(request, "Bạn không có quyền thực hiện thao tác này.")
        return redirect('transactions:borrow_detail', pk=pk)

    form = BorrowReturnForm(request.POST, borrow_record=borrow)
    if form.is_valid():
        try:
            TransactionService.return_book(
                borrow_record_id=borrow.id,
                condition_notes=form.cleaned_data['condition_notes'],
                return_location=form.cleaned_data['return_location'],
                returned_by=request.user
            )
            messages.success(request, f'Đã ghi nhận trả sách: {borrow.book.title}')
            logger.info(f"Book {borrow.book.title} returned by {borrow.user.username}, processed by {request.user.username}")
        except Exception as e:
            logger.error(f"Error returning book (borrow_id={pk}): {e}")
            messages.error(request, f'Lỗi khi trả sách: {e}')
    else:
        messages.error(request, "Dữ liệu không hợp lệ. Vui lòng kiểm tra lại.")

    return redirect('transactions:borrow_detail', pk=pk)


@login_required
@require_http_methods(["POST"])
def renew_book(request: HttpRequest, pk: int) -> HttpResponse:
    """Handles the book renewal process."""
    borrow = get_object_or_404(BorrowRecord, pk=pk)
    if not (is_librarian(request.user) or borrow.user == request.user):
        messages.error(request, "Bạn không có quyền gia hạn sách này.")
        return redirect('transactions:borrow_detail', pk=pk)

    form = RenewalForm(request.POST, borrow_record=borrow)
    if form.is_valid():
        try:
            TransactionService.renew_book(
                borrow_record_id=borrow.id,
                days=form.cleaned_data['renewal_days']
            )
            messages.success(request, f'Đã gia hạn sách thành công thêm {form.cleaned_data["renewal_days"]} ngày.')
            logger.info(f"Book {borrow.book.title} renewed for user {borrow.user.username}")
        except Exception as e:
            logger.error(f"Error renewing book (borrow_id={pk}): {e}")
            messages.error(request, f'Lỗi khi gia hạn: {e}')
    else:
        messages.error(request, "Không thể gia hạn sách này.")

    return redirect('transactions:borrow_detail', pk=pk)


# === RESERVATION VIEWS ===

class ReservationListView(LoginRequiredMixin, ListView):
    """Displays a list of book reservations."""
    template_name = 'transactions/reservation_list.html'
    context_object_name = 'reservations'
    paginate_by = 25

    def get_queryset(self) -> QuerySet[BookReservation]:
        user = self.request.user
        if is_librarian(user):
            queryset = BookReservation.objects.select_related('user', 'book').all()
        else:
            queryset = BookReservation.objects.filter(user=user).select_related('book')
        return queryset.order_by('book', 'queue_position')


class CreateReservationView(LoginRequiredMixin, FormView):
    """Allows a user to create a reservation for a book."""
    form_class = UserBorrowRequestForm
    template_name = 'transactions/reservation_create.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['book'] = get_object_or_404(Book, pk=self.kwargs['book_id'])
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['book'] = get_object_or_404(Book, pk=self.kwargs['book_id'])
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        try:
            book = get_object_or_404(Book, pk=self.kwargs['book_id'])
            receive_method = form.cleaned_data.get('receive_method')
            
            if receive_method == 'pickup':
                # Create BorrowRecord immediately
                borrow = TransactionService.create_borrow(
                    user=self.request.user,
                    book=book,
                    pickup_location=form.cleaned_data.get('pickup_location')
                )
                messages.success(self.request, f'Mượn sách "{book.title}" thành công. Vui lòng đến lấy sách.')
                return redirect('transactions:borrow_detail', pk=borrow.pk)
                
            elif receive_method == 'shipping':
                # Create ShippingRequest
                shipping = TransactionService.create_shipping_request(
                    user=self.request.user,
                    book=book,
                    shipping_address=form.cleaned_data.get('shipping_address'),
                    phone_number=form.cleaned_data.get('phone_number'),
                    recipient_name=form.cleaned_data.get('recipient_name')
                )
                if form.cleaned_data.get('delivery_notes'):
                    shipping.delivery_notes = form.cleaned_data.get('delivery_notes')
                    shipping.save(update_fields=['delivery_notes'])
                    
                # Send notification to admin
                NotificationService.notify_admin_new_shipping_request(shipping)
                
                messages.success(self.request, f'Yêu cầu giao sách "{book.title}" đã được tạo và chờ duyệt.')
                return redirect('transactions:borrow_detail', pk=shipping.borrow_record.pk)
                
        except Exception as e:
            logger.error(f"Error creating borrow/shipping for book {self.kwargs['book_id']} by user {self.request.user.username}: {e}")
            messages.error(self.request, f"Lỗi: {e}")
            return self.form_invalid(form)


class ReservationDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Displays details of a single reservation."""
    template_name = 'transactions/reservation_detail.html'

    def test_func(self) -> bool:
        return is_librarian(self.request.user) or self.get_object().user == self.request.user

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        reservation = self.get_object()
        context['queue_ahead'] = BookReservation.objects.filter(
            book=reservation.book,
            queue_position__lt=reservation.queue_position,
            is_fulfilled=False
        ).count()
        return context


@login_required
@require_http_methods(["POST"])
def cancel_reservation(request: HttpRequest, pk: int) -> HttpResponse:
    """Cancels an active reservation."""
    reservation = get_object_or_404(BookReservation, pk=pk)
    if not (is_librarian(request.user) or reservation.user == request.user):
        messages.error(request, "Bạn không có quyền hủy đặt trước này.")
        return redirect('transactions:dashboard')

    try:
        TransactionService.cancel_reservation(reservation.id)
        messages.success(request, f'Đã hủy đặt trước cho sách "{reservation.book.title}".')
        logger.info(f"Reservation {pk} cancelled by user {request.user.username}")
    except Exception as e:
        logger.error(f"Error cancelling reservation {pk}: {e}")
        messages.error(request, f"Lỗi khi hủy đặt trước: {e}")

    return redirect('transactions:reservation_list')


# === BULK OPERATIONS VIEW ===

class BulkOperationView(LoginRequiredMixin, LibrarianRequiredMixin, FormView):
    """Handles bulk operations like returns and renewals."""
    template_name = 'transactions/bulk_operations.html'
    form_class = BulkOperationForm
    success_url = reverse_lazy('transactions:bulk_operations')

    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form: BulkOperationForm) -> HttpResponse:
        operation = form.cleaned_data['operation']
        records = form.cleaned_data['borrow_records']
        record_ids = list(records.values_list('id', flat=True))
        user = self.request.user
        result = {}

        try:
            if operation == 'return':
                result = TransactionService.bulk_return_books(record_ids, user)
            elif operation == 'renew':
                result = TransactionService.bulk_renew_books(record_ids, user)
            
            messages.success(self.request, f"Thao tác hàng loạt '{operation}' hoàn tất. Thành công: {result.get('success', 0)}, Thất bại: {result.get('failed', 0)}.")
            if result.get('errors'):
                messages.warning(self.request, f"Chi tiết lỗi: {result['errors']}")
            logger.info(f"Bulk operation '{operation}' performed by {user.username} with result: {result}")

        except Exception as e:
            logger.error(f"Critical error during bulk operation '{operation}' by {user.username}: {e}")
            messages.error(self.request, f"Đã xảy ra lỗi nghiêm trọng: {e}")

        return super().form_valid(form)


# === AJAX VIEWS ===

@require_http_methods(["GET"])
@login_required
def ajax_book_info(request: HttpRequest) -> JsonResponse:
    """AJAX endpoint to get book information."""
    book_id = request.GET.get('book_id')
    if not book_id:
        return JsonResponse({'error': 'Thiếu book_id'}, status=400)
    try:
        book = get_object_or_404(Book, pk=book_id)
        data = ReportService.get_book_statistics(book)
        return JsonResponse(data)
    except Exception as e:
        logger.warning(f"AJAX book info request failed for book_id {book_id}: {e}")
        return JsonResponse({'error': 'Sách không tồn tại'}, status=404)


@require_http_methods(["GET"])
@login_required
def ajax_user_info(request: HttpRequest) -> JsonResponse:
    """AJAX endpoint to get user borrowing information."""
    user_id = request.GET.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'Thiếu user_id'}, status=400)
    try:
        user = get_object_or_404(User, pk=user_id)
        data = ReportService.get_user_statistics(user)
        return JsonResponse(data)
    except Exception as e:
        logger.warning(f"AJAX user info request failed for user_id {user_id}: {e}")
        return JsonResponse({'error': 'Người dùng không tồn tại'}, status=404)

# Note: Shipping and Fine Payment views can be added here following the same CBV and service-layer pattern.
# For brevity, they are omitted but would look similar to Borrow/Reservation views.
