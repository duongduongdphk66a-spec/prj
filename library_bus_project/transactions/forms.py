# File: transactions/forms.py
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .models import BorrowRecord, BookReservation, ShippingRequest, FinePayment, BulkTransaction
from inventory.models import Book, LibraryBus

class BorrowRecordForm(forms.ModelForm):
    """Form mượn sách với validation nâng cao"""
    due_days = forms.IntegerField(initial=14, min_value=1, max_value=90, label="Số ngày mượn", help_text="Từ 1-90 ngày")
    
    class Meta:
        model = BorrowRecord
        fields = ['user', 'book', 'pickup_location', 'notes']
        widgets = {
            'user': forms.Select(attrs={'class': 'form-select', 'data-live-search': 'true'}),
            'book': forms.Select(attrs={'class': 'form-select', 'data-live-search': 'true'}),
            'pickup_location': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Ghi chú về tình trạng sách, yêu cầu đặc biệt...'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Chỉ hiển thị sách available và user active
        self.fields['book'].queryset = Book.objects.filter(status='available').select_related('category')
        self.fields['user'].queryset = User.objects.filter(is_active=True).order_by('username')
        self.fields['pickup_location'].queryset = LibraryBus.objects.filter(is_active=True)
    
    def clean(self):
        cleaned_data = super().clean()
        book = cleaned_data.get('book')
        user = cleaned_data.get('user')
        
        if book and user:
            # Kiểm tra user có borrow record active cho sách này không
            if BorrowRecord.objects.filter(user=user, book=book, return_date__isnull=True).exists():
                raise ValidationError("Người dùng đã mượn cuốn sách này và chưa trả.")
            
            # Kiểm tra giới hạn số sách đang mượn
            active_borrows = BorrowRecord.objects.filter(user=user, return_date__isnull=True).count()
            if active_borrows >= 5:  # Giới hạn tối đa 5 cuốn
                raise ValidationError(f"Người dùng đã mượn {active_borrows} cuốn. Vượt quá giới hạn cho phép.")
        
        return cleaned_data

class BorrowReturnForm(forms.Form):
    """Form trả sách với đánh giá tình trạng"""
    CONDITION_CHOICES = [('good', 'Tốt'), ('minor_damage', 'Hỏng nhẹ'), ('major_damage', 'Hỏng nặng'), ('lost', 'Mất sách')]
    
    condition = forms.ChoiceField(choices=CONDITION_CHOICES, initial='good', label="Tình trạng sách", widget=forms.RadioSelect)
    condition_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Mô tả chi tiết tình trạng sách nếu có vấn đề...'}), label="Ghi chú tình trạng")
    return_location = forms.ModelChoiceField(queryset=LibraryBus.objects.filter(is_active=True), required=False, label="Nơi trả sách")
    
    def __init__(self, *args, borrow_record=None, **kwargs):
        self.borrow_record = borrow_record
        super().__init__(*args, **kwargs)
    
    def clean_condition_notes(self):
        condition = self.cleaned_data.get('condition')
        notes = self.cleaned_data.get('condition_notes')
        if condition in ['minor_damage', 'major_damage', 'lost'] and not notes:
            raise ValidationError("Vui lòng mô tả chi tiết tình trạng sách.")
        return notes

class BookReservationForm(forms.ModelForm):
    """Form đặt trước sách với validation"""
    class Meta:
        model = BookReservation
        fields = ['preferred_pickup_location']
        widgets = {'preferred_pickup_location': forms.Select(attrs={'class': 'form-select'})}
    
    def __init__(self, *args, book=None, user=None, **kwargs):
        self.book = book
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['preferred_pickup_location'].queryset = LibraryBus.objects.filter(is_active=True)
        if not self.fields['preferred_pickup_location'].queryset.exists():
            self.fields['preferred_pickup_location'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        if self.book and self.user:
            # Kiểm tra đã có reservation active chưa
            if BookReservation.objects.filter(user=self.user, book=self.book, is_fulfilled=False).exists():
                raise ValidationError("Bạn đã đặt trước cuốn sách này rồi.")
            
            # Kiểm tra đã mượn cuốn này chưa
            if BorrowRecord.objects.filter(user=self.user, book=self.book, return_date__isnull=True).exists():
                raise ValidationError("Bạn đang mượn cuốn sách này.")
            
            # Kiểm tra sách có available không
            if self.book.is_available:
                raise ValidationError("Sách hiện đang available, bạn có thể mượn trực tiếp.")
        
        return cleaned_data

class ShippingRequestForm(forms.ModelForm):
    """Form yêu cầu giao sách với validation địa chỉ"""
    accept_shipping_fee = forms.BooleanField(required=True, label="Tôi đồng ý thanh toán phí giao hàng")
    
    class Meta:
        model = ShippingRequest
        fields = ['recipient_name', 'phone_number', 'shipping_address', 'delivery_notes']
        widgets = {
            'recipient_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Họ và tên người nhận'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0901234567'}),
            'shipping_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Số nhà, tên đường, phường/xã, quận/huyện, tỉnh/thành phố'}),
            'delivery_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Ghi chú cho shipper: thời gian nhận hàng, gọi trước khi giao...'}),
        }
    
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        # Pre-fill user info if available
        if user and hasattr(user, 'profile'):
            profile = user.profile
            self.fields['recipient_name'].initial = user.get_full_name() or user.username
            self.fields['phone_number'].initial = getattr(profile, 'phone_number', '')
            self.fields['shipping_address'].initial = getattr(profile, 'address', '')
    
    def clean_phone_number(self):
        phone = self.cleaned_data['phone_number']
        if not phone.startswith(('0', '+84')):
            raise ValidationError("Số điện thoại phải bắt đầu bằng 0 hoặc +84")
        return phone

class RenewalForm(forms.Form):
    """Form gia hạn sách"""
    renewal_days = forms.IntegerField(initial=14, min_value=7, max_value=30, label="Số ngày gia hạn", help_text="Từ 7-30 ngày")
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Lý do gia hạn (không bắt buộc)'}), label="Lý do")
    
    def __init__(self, *args, borrow_record=None, **kwargs):
        self.borrow_record = borrow_record
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        if self.borrow_record and not self.borrow_record.can_renew:
            raise ValidationError("Không thể gia hạn sách này. Kiểm tra lại điều kiện gia hạn.")
        return cleaned_data

class FinePaymentForm(forms.ModelForm):
    """Form thanh toán phạt"""
    apply_discount = forms.BooleanField(required=False, label="Áp dụng giảm giá")
    discount_percent = forms.DecimalField(max_digits=5, decimal_places=2, initial=0, min_value=0, max_value=100, required=False, label="% giảm giá")
    
    class Meta:
        model = FinePayment
        fields = ['payment_method', 'notes']
        widgets = {
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Ghi chú về thanh toán...'}),
        }
    
    def __init__(self, *args, borrow_record=None, **kwargs):
        self.borrow_record = borrow_record
        super().__init__(*args, **kwargs)
        if borrow_record:
            self.calculated_fine = borrow_record.fine_amount
    
    def clean_discount_percent(self):
        apply_discount = self.cleaned_data.get('apply_discount', False)
        discount = self.cleaned_data.get('discount_percent', 0)
        if apply_discount and discount <= 0:
            raise ValidationError("Vui lòng nhập % giảm giá hợp lệ.")
        return discount

class BulkOperationForm(forms.Form):
    """Form cho các thao tác hàng loạt"""
    OPERATION_CHOICES = [('return', 'Trả sách hàng loạt'), ('renew', 'Gia hạn hàng loạt'), ('calculate_fines', 'Tính phạt hàng loạt')]
    
    operation = forms.ChoiceField(choices=OPERATION_CHOICES, widget=forms.RadioSelect, label="Thao tác")
    borrow_records = forms.ModelMultipleChoiceField(queryset=BorrowRecord.objects.none(), widget=forms.CheckboxSelectMultiple, label="Chọn các bản ghi")
    confirm_action = forms.BooleanField(required=True, label="Tôi xác nhận thực hiện thao tác này")
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Ghi chú cho thao tác hàng loạt...'}), label="Ghi chú")
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Chỉ hiển thị records phù hợp
        if user and user.is_staff:
            self.fields['borrow_records'].queryset = BorrowRecord.objects.filter(return_date__isnull=True).select_related('user', 'book')
    
    def clean(self):
        cleaned_data = super().clean()
        operation = cleaned_data.get('operation')
        records = cleaned_data.get('borrow_records')
        
        if not records:
            raise ValidationError("Vui lòng chọn ít nhất một bản ghi.")
        
        # Validation theo operation
        if operation == 'renew':
            non_renewable = [r for r in records if not r.can_renew]
            if non_renewable:
                raise ValidationError(f"Có {len(non_renewable)} bản ghi không thể gia hạn.")
        
        return cleaned_data

class AdminSearchForm(forms.Form):
    """Form tìm kiếm cho admin"""
    SEARCH_TYPES = [('user', 'Theo người dùng'), ('book', 'Theo sách'), ('overdue', 'Sách quá hạn'), ('active', 'Đang mượn')]
    
    search_type = forms.ChoiceField(choices=SEARCH_TYPES, initial='user', widget=forms.Select(attrs={'class': 'form-select'}))
    query = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập từ khóa...'}))
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), label="Từ ngày")
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), label="Đến ngày")
    location = forms.ModelChoiceField(queryset=LibraryBus.objects.filter(is_active=True), required=False, widget=forms.Select(attrs={'class': 'form-select'}), label="Địa điểm")
    
    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise ValidationError("Ngày bắt đầu không thể sau ngày kết thúc.")
        
        return cleaned_data


class UserBorrowRequestForm(forms.Form):
    """Form cho người dùng chọn mượn sách trực tiếp hoặc yêu cầu giao sách"""
    RECEIVE_CHOICES = [
        ('pickup', 'Nhận sách tại xe/thư viện'),
        ('shipping', 'Giao sách tận nơi')
    ]
    
    receive_method = forms.ChoiceField(
        choices=RECEIVE_CHOICES, 
        initial='pickup', 
        widget=forms.RadioSelect, 
        label="Phương thức nhận sách"
    )
    
    # Fields for pickup
    pickup_location = forms.ModelChoiceField(
        queryset=LibraryBus.objects.none(), 
        required=False, 
        widget=forms.Select(attrs={'class': 'form-select'}), 
        label="Điểm lấy sách"
    )
    
    # Fields for shipping
    recipient_name = forms.CharField(
        max_length=100, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Họ và tên người nhận'})
    )
    phone_number = forms.CharField(
        max_length=15, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Số điện thoại'})
    )
    shipping_address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Địa chỉ chi tiết (số nhà, đường, phường, quận...)'})
    )
    delivery_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Ghi chú cho shipper (ví dụ: giao giờ hành chính)'})
    )
    
    def __init__(self, *args, book=None, user=None, **kwargs):
        self.book = book
        self.user = user
        super().__init__(*args, **kwargs)
        
        self.fields['pickup_location'].queryset = LibraryBus.objects.filter(is_active=True)
        
        # Pre-fill user info if available
        if user and hasattr(user, 'profile'):
            profile = user.profile
            self.fields['recipient_name'].initial = user.get_full_name() or user.username
            self.fields['phone_number'].initial = getattr(profile, 'phone_number', '')
            self.fields['shipping_address'].initial = getattr(profile, 'address', '')
            
    def clean(self):
        cleaned_data = super().clean()
        receive_method = cleaned_data.get('receive_method')
        
        if self.book and self.user:
            if BorrowRecord.objects.filter(user=self.user, book=self.book, return_date__isnull=True).exists():
                raise ValidationError("Bạn đang mượn cuốn sách này.")
                
            active_borrows = BorrowRecord.objects.filter(user=self.user, return_date__isnull=True).count()
            limit = getattr(self.user.profile, 'borrow_limit', 5) if hasattr(self.user, 'profile') else 5
            if active_borrows >= limit:
                raise ValidationError(f"Bạn đã đạt giới hạn mượn sách ({active_borrows}/{limit} cuốn).")
                
            if not self.book.is_available:
                raise ValidationError("Sách này hiện không có sẵn để mượn.")
        
        if receive_method == 'shipping':
            if not cleaned_data.get('recipient_name'):
                self.add_error('recipient_name', "Vui lòng nhập tên người nhận.")
            
            phone = cleaned_data.get('phone_number')
            if not phone:
                self.add_error('phone_number', "Vui lòng nhập số điện thoại.")
            elif not phone.startswith(('0', '+84')):
                self.add_error('phone_number', "Số điện thoại phải bắt đầu bằng 0 hoặc +84.")
                
            if not cleaned_data.get('shipping_address'):
                self.add_error('shipping_address', "Vui lòng nhập địa chỉ giao hàng.")
        elif receive_method == 'pickup':
            if not cleaned_data.get('pickup_location'):
                self.add_error('pickup_location', "Vui lòng chọn điểm nhận sách.")
                
        return cleaned_data
