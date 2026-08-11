# File: users/forms.py
# Mô tả: Forms tối ưu cho hệ thống người dùng với validation nâng cao
# ==============================================================================

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, timedelta
import re
from .models import Profile, UserInterest, UserPreference, MEMBERSHIP_LEVELS

class UserRegistrationForm(forms.ModelForm):
    """Form đăng ký tối ưu với validation nâng cao."""
    password = forms.CharField(label='Mật khẩu', widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Nhập mật khẩu'}))
    password2 = forms.CharField(label='Xác nhận mật khẩu', widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Nhập lại mật khẩu'}))
    terms_agreed = forms.BooleanField(label='Tôi đồng ý với điều khoản sử dụng', required=True)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')
        labels = {'username': 'Tên đăng nhập', 'email': 'Email', 'first_name': 'Tên', 'last_name': 'Họ'}
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên đăng nhập'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên của bạn'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Họ của bạn'}),
        }
        help_texts = {'username': 'Chỉ chứa chữ cái, số và dấu gạch dưới. Độ dài 3-150 ký tự.'}

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not re.match(r'^[a-zA-Z0-9_]{3,150}$', username):
            raise ValidationError('Tên đăng nhập chỉ chứa chữ cái, số, dấu gạch dưới và từ 3-150 ký tự.')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('Tên đăng nhập đã tồn tại.')
        return username.lower()

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Email đã được sử dụng.')
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                raise ValidationError(e.messages)
        return password

    def clean_password2(self):
        password1 = self.cleaned_data.get('password')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError('Mật khẩu không khớp.')
        return password2

    def clean_first_name(self):
        name = self.cleaned_data.get('first_name', '').strip()
        if name and not re.match(r'^[a-zA-ZÀ-ỹ\s]{1,30}$', name):
            raise ValidationError('Tên chỉ chứa chữ cái và khoảng trắng, tối đa 30 ký tự.')
        return name.title()

    def clean_last_name(self):
        name = self.cleaned_data.get('last_name', '').strip()
        if name and not re.match(r'^[a-zA-ZÀ-ỹ\s]{1,150}$', name):
            raise ValidationError('Họ chỉ chứa chữ cái và khoảng trắng, tối đa 150 ký tự.')
        return name.title()

class UserLoginForm(AuthenticationForm):
    """Form đăng nhập tối ưu với hỗ trợ email."""
    username = forms.CharField(
        label='Tên đăng nhập/Email',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên đăng nhập hoặc Email', 'autofocus': True})
    )
    password = forms.CharField(
        label='Mật khẩu',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Mật khẩu'})
    )
    remember_me = forms.BooleanField(label='Ghi nhớ đăng nhập', required=False)

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        # Hỗ trợ đăng nhập bằng email
        if '@' in username:
            try:
                user = User.objects.get(email__iexact=username)
                return user.username
            except User.DoesNotExist:
                pass
        return username

class UserUpdateForm(forms.ModelForm):
    """Form cập nhật thông tin User cơ bản."""
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')
        labels = {'first_name': 'Tên', 'last_name': 'Họ', 'email': 'Email'}
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if self.user and User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise ValidationError('Email đã được sử dụng.')
        return email

    def clean_first_name(self):
        name = self.cleaned_data.get('first_name', '').strip()
        if name and not re.match(r'^[a-zA-ZÀ-ỹ\s]{1,30}$', name):
            raise ValidationError('Tên không hợp lệ.')
        return name.title()

    def clean_last_name(self):
        name = self.cleaned_data.get('last_name', '').strip()
        if name and not re.match(r'^[a-zA-ZÀ-ỹ\s]{1,150}$', name):
            raise ValidationError('Họ không hợp lệ.')
        return name.title()

class ProfileUpdateForm(forms.ModelForm):
    """Form cập nhật Profile với validation nâng cao."""
    date_of_birth = forms.DateField(
        label='Ngày sinh',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False
    )
    
    class Meta:
        model = Profile
        fields = (
            'avatar', 'bio', 'phone_number', 'date_of_birth', 'gender',
            'address', 'city', 'district', 'ward', 'postal_code',
            'occupation', 'reading_goal_monthly', 'preferred_language'
        )
        labels = {
            'avatar': 'Ảnh đại diện', 'bio': 'Giới thiệu', 'phone_number': 'Số điện thoại',
            'gender': 'Giới tính', 'address': 'Địa chỉ', 'city': 'Thành phố',
            'district': 'Quận/Huyện', 'ward': 'Phường/Xã', 'postal_code': 'Mã bưu điện',
            'occupation': 'Nghề nghiệp', 'reading_goal_monthly': 'Mục tiêu đọc/tháng',
            'preferred_language': 'Ngôn ngữ'
        }
        widgets = {
            'avatar': forms.FileInput(attrs={'class': 'd-none', 'accept': 'image/*'}),
            'bio': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'maxlength': '300'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'pattern': r'^(\+84|0)[0-9]{9,10}$'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'maxlength': '500'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'list': 'cities'}),
            'district': forms.TextInput(attrs={'class': 'form-control', 'list': 'districts'}),
            'ward': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control', 'pattern': r'^\d{5,6}$'}),
            'occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'reading_goal_monthly': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '50'}),
            'preferred_language': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            if dob > date.today():
                raise ValidationError('Ngày sinh không thể ở tương lai.')
            if dob < date.today() - timedelta(days=365*120):
                raise ValidationError('Ngày sinh không hợp lệ.')
        return dob

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number', '').strip()
        if phone:
            # Chuẩn hóa số điện thoại
            if phone.startswith('0'):
                phone = '+84' + phone[1:]
            elif not phone.startswith('+84'):
                raise ValidationError('Số điện thoại phải bắt đầu bằng 0 hoặc +84.')
            
            # Kiểm tra trùng lặp
            if Profile.objects.filter(phone_number=phone).exclude(pk=self.instance.pk).exists():
                raise ValidationError('Số điện thoại đã được sử dụng.')
        return phone

    def clean_bio(self):
        bio = self.cleaned_data.get('bio', '').strip()
        if bio and len(bio) < 10:
            raise ValidationError('Giới thiệu ít nhất 10 ký tự.')
        return bio

class UserInterestForm(forms.ModelForm):
    """Form quản lý sở thích người dùng."""
    class Meta:
        model = UserInterest
        fields = ('interest_type', 'interest_value', 'weight')
        labels = {'interest_type': 'Loại sở thích', 'interest_value': 'Giá trị', 'weight': 'Mức độ (1-10)'}
        widgets = {
            'interest_type': forms.Select(attrs={'class': 'form-control'}),
            'interest_value': forms.TextInput(attrs={'class': 'form-control'}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10'}),
        }

class UserPreferenceForm(forms.ModelForm):
    """Form cài đặt tùy chọn người dùng."""
    class Meta:
        model = UserPreference
        fields = ('theme', 'books_per_page', 'auto_renew_books', 'show_reading_progress', 'public_reading_list')
        labels = {
            'theme': 'Giao diện', 'books_per_page': 'Số sách/trang',
            'auto_renew_books': 'Tự động gia hạn', 'show_reading_progress': 'Hiển thị tiến độ',
            'public_reading_list': 'Công khai danh sách đọc'
        }
        widgets = {
            'theme': forms.Select(attrs={'class': 'form-control'}),
            'books_per_page': forms.NumberInput(attrs={'class': 'form-control', 'min': '5', 'max': '100'}),
            'auto_renew_books': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_reading_progress': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'public_reading_list': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class PasswordChangeForm(forms.Form):
    """Form đổi mật khẩu tùy chỉnh."""
    current_password = forms.CharField(
        label='Mật khẩu hiện tại',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password = forms.CharField(
        label='Mật khẩu mới',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    confirm_password = forms.CharField(
        label='Xác nhận mật khẩu mới',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        password = self.cleaned_data.get('current_password')
        if not self.user.check_password(password):
            raise ValidationError('Mật khẩu hiện tại không đúng.')
        return password

    def clean_new_password(self):
        password = self.cleaned_data.get('new_password')
        if password:
            try:
                validate_password(password, self.user)
            except ValidationError as e:
                raise ValidationError(e.messages)
        return password

    def clean_confirm_password(self):
        new_password = self.cleaned_data.get('new_password')
        confirm_password = self.cleaned_data.get('confirm_password')
        if new_password and confirm_password and new_password != confirm_password:
            raise ValidationError('Mật khẩu mới không khớp.')
        return confirm_password

class EmailVerificationForm(forms.Form):
    """Form xác thực email."""
    verification_code = forms.CharField(
        label='Mã xác thực',
        max_length=6,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '6 chữ số'})
    )

    def clean_verification_code(self):
        code = self.cleaned_data.get('verification_code', '').strip()
        if not re.match(r'^\d{6}$', code):
            raise ValidationError('Mã xác thực phải là 6 chữ số.')
        return code

class CustomPasswordResetForm(PasswordResetForm):
    """Form reset mật khẩu tùy chỉnh."""
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Nhập email của bạn'})
    )

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        # SECURITY: Không tiết lộ email có tồn tại hay không để chống user enumeration
        return email

# Forms nâng cao cho admin
class BulkUserActionForm(forms.Form):
    """Form thực hiện hành động hàng loạt cho users."""
    action = forms.ChoiceField(
        choices=[
            ('activate', 'Kích hoạt'),
            ('deactivate', 'Vô hiệu hóa'),
            ('verify', 'Xác thực'),
            ('unverify', 'Bỏ xác thực'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    user_ids = forms.CharField(widget=forms.HiddenInput())

class MembershipUpgradeForm(forms.Form):
    """Form nâng cấp membership."""
    membership_level = forms.ChoiceField(
        choices=MEMBERSHIP_LEVELS,
        label='Loại thành viên',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    duration_months = forms.IntegerField(
        label='Thời hạn (tháng)',
        min_value=1,
        max_value=36,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )