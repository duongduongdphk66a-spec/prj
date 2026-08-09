import sys
import re

with open('transactions/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Make sure we import UserBorrowRequestForm
if 'UserBorrowRequestForm' not in content:
    content = content.replace('from .forms import (', 'from .forms import (\n    UserBorrowRequestForm,')

new_view = '''class CreateReservationView(LoginRequiredMixin, CreateView):
    """Allows a user to create a reservation for a book."""
    model = BookReservation
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
            return self.form_invalid(form)'''

pattern = r'class CreateReservationView\(LoginRequiredMixin, CreateView\):.*?def form_valid.*?return self\.form_invalid\(form\)'

content = re.sub(pattern, new_view, content, flags=re.DOTALL)

with open('transactions/views.py', 'w', encoding='utf-8') as f:
    f.write(content)
