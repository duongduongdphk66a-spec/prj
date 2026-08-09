import sys

form_code = """
class UserBorrowRequestForm(forms.Form):
    \"\"\"Form cho người dùng chọn mượn sách trực tiếp hoặc yêu cầu giao sách\"\"\"
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
"""

with open('transactions/forms.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'class UserBorrowRequestForm' not in content:
    with open('transactions/forms.py', 'a', encoding='utf-8') as f:
        f.write('\n\n' + form_code)
