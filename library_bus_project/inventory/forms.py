# File: inventory/forms.py 
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.db.models import Q
from .models import LibraryBus, Category, Book, BookStatusHistory, BusRoute, InventoryAlert, BookDonation
import json

class LibraryBusForm(forms.ModelForm):
    """Form cho xe bus sách với validation nâng cao"""
    
    class Meta:
        model = LibraryBus
        fields = ['name', 'license_plate', 'latitude', 'longitude', 'location_name', 'operating_status', 'capacity', 'description', 'contact_phone', 'operating_hours']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên xe bus'}),
            'license_plate': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '29A-12345'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001', 'placeholder': '21.028511'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001', 'placeholder': '105.804817'}),
            'location_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Hồ Gươm, Hà Nội'}),
            'operating_status': forms.Select(attrs={'class': 'form-select'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '2000'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0123456789'}),
            'operating_hours': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '08:00 - 17:00'})
        }
    
    def clean_license_plate(self):
        """Validate định dạng biển số xe"""
        license_plate = self.cleaned_data.get('license_plate')
        if license_plate:
            # Kiểm tra format biển số Việt Nam cơ bản
            import re
            pattern = r'^\d{2}[A-Z]-\d{4,5}$'
            if not re.match(pattern, license_plate.upper()):
                raise ValidationError('Biển số xe không đúng định dạng (VD: 29A-12345)')
            license_plate = license_plate.upper()
        return license_plate
    
    def clean_contact_phone(self):
        """Validate số điện thoại"""
        phone = self.cleaned_data.get('contact_phone')
        if phone:
            import re
            pattern = r'^(0|\+84)[0-9]{9,10}$'
            if not re.match(pattern, phone):
                raise ValidationError('Số điện thoại không đúng định dạng')
        return phone
    
    def clean(self):
        """Validation toàn form"""
        cleaned_data = super().clean()
        lat = cleaned_data.get('latitude')
        lng = cleaned_data.get('longitude')
        
        # Nếu có một trong hai tọa độ thì phải có cả hai
        if (lat is not None and lng is None) or (lat is None and lng is not None):
            raise ValidationError('Vui lòng nhập đầy đủ tọa độ hoặc để trống cả hai')
        
        # Kiểm tra tọa độ hợp lệ cho Việt Nam
        if lat is not None and lng is not None:
            if not (8.0 <= lat <= 23.5) or not (102.0 <= lng <= 110.0):
                raise ValidationError('Tọa độ không nằm trong phạm vi Việt Nam')
        
        return cleaned_data

class CategoryForm(forms.ModelForm):
    """Form cho lĩnh vực sách"""
    
    class Meta:
        model = Category
        fields = ['name', 'description', 'color_code', 'icon', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Văn học, Khoa học...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'color_code': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'book, science...'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def clean_name(self):
        """Validate tên category unique"""
        name = self.cleaned_data.get('name')
        if name:
            # Kiểm tra duplicate (trừ instance hiện tại nếu đang edit)
            query = Category.objects.filter(name__iexact=name)
            if self.instance and self.instance.pk:
                query = query.exclude(pk=self.instance.pk)
            if query.exists():
                raise ValidationError('Tên lĩnh vực đã tồn tại')
        return name

class BookForm(forms.ModelForm):
    """Form cho sách với file upload và validation"""
    
    # Custom fields
    pdf_file = forms.FileField(
        required=False,
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf'})
    )
    cover_image = forms.ImageField(
        required=False,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'})
    )
    
    class Meta:
        model = Book
        fields = ['title', 'author', 'publisher', 'publication_year', 'page_count', 'isbn', 'category', 'location', 'cover_image', 'pdf_file', 'description', 'language', 'condition', 'status', 'is_digital_only']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên sách'}),
            'author': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tác giả'}),
            'publisher': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhà xuất bản'}),
            'publication_year': forms.NumberInput(attrs={'class': 'form-control', 'min': '1800', 'max': str(timezone.now().year + 1)}),
            'page_count': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'isbn': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '978-604-XXXXXXX'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'language': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tiếng Việt'}),
            'condition': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'is_digital_only': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter active categories và buses
        self.fields['category'].queryset = Category.objects.filter(is_active=True)
        self.fields['location'].queryset = LibraryBus.objects.filter(operating_status='active')
        
        # Thêm empty option
        self.fields['category'].empty_label = "Chọn lĩnh vực"
        self.fields['location'].empty_label = "Chọn xe bus"
    
    def clean_isbn(self):
        """Validate ISBN format"""
        isbn = self.cleaned_data.get('isbn')
        if isbn:
            # Remove dashes and spaces
            isbn_clean = isbn.replace('-', '').replace(' ', '')
            
            if not isbn_clean.isdigit():
                raise ValidationError('ISBN chỉ được chứa các chữ số')
                
            if len(isbn_clean) not in [10, 13]:
                raise ValidationError('ISBN phải có 10 hoặc 13 chữ số')
            
            # Check if already exists
            query = Book.objects.filter(isbn=isbn_clean)
            if self.instance and self.instance.pk:
                query = query.exclude(pk=self.instance.pk)
            if query.exists():
                raise ValidationError('ISBN này đã tồn tại trong hệ thống')
            return isbn_clean
        return isbn
    
    def clean_pdf_file(self):
        """Validate PDF file size"""
        pdf_file = self.cleaned_data.get('pdf_file')
        if pdf_file:
            if pdf_file.size > 50 * 1024 * 1024:  # 50MB limit
                raise ValidationError('File PDF không được vượt quá 50MB')
        return pdf_file
    
    def clean_cover_image(self):
        """Validate cover image"""
        cover_image = self.cleaned_data.get('cover_image')
        if cover_image:
            if cover_image.size > 5 * 1024 * 1024:  # 5MB limit
                raise ValidationError('Ảnh bìa không được vượt quá 5MB')
        return cover_image
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        is_digital_only = cleaned_data.get('is_digital_only')
        location = cleaned_data.get('location')
        pdf_file = cleaned_data.get('pdf_file')
        
        # Nếu là digital only thì không cần location
        if is_digital_only and location:
            raise ValidationError('Sách điện tử không cần vị trí vật lý')
        
        # Nếu không phải digital only thì nên có location
        if not is_digital_only and not location:
            self.add_error('location', 'Sách vật lý cần có vị trí')
        
        # Nếu digital only thì nên có PDF
        if is_digital_only and not pdf_file and not (self.instance and self.instance.pdf_file):
            self.add_error('pdf_file', 'Sách điện tử nên có file PDF')
        
        return cleaned_data

class BookStatusChangeForm(forms.Form):
    """Form thay đổi trạng thái sách"""
    
    new_status = forms.ChoiceField(
        choices=Book.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    reason = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Lý do thay đổi (tùy chọn)'})
    )
    
    def __init__(self, *args, current_status=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Loại bỏ trạng thái hiện tại khỏi choices
        if current_status:
            choices = [choice for choice in Book.STATUS_CHOICES if choice[0] != current_status]
            self.fields['new_status'].choices = choices

class BusRouteForm(forms.ModelForm):
    """Form cho lộ trình xe bus"""
    
    # Custom field cho stops (JSON)
    stops_json = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    schedule_json = forms.CharField(
        label="Lịch trình JSON",
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        help_text='VD: {"monday": ["08:00", "14:00"], "tuesday": ["09:00"]}'
    )

    class Meta:
        model = BusRoute
        fields = ['route_name', 'bus', 'is_active']
        fields = ['route_name', 'bus', 'is_active', 'stops_json', 'schedule_json']
        widgets = {
            'route_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên lộ trình'}),
            'bus': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['bus'].queryset = LibraryBus.objects.all()
        
        # Load existing stops data
        if self.instance and self.instance.pk and self.instance.stops:
            self.fields['stops_json'].initial = json.dumps(self.instance.stops)
    
    def clean_stops_json(self):
        """Validate JSON stops data"""
        stops_json = self.cleaned_data.get('stops_json')
        if stops_json:
            try:
                stops = json.loads(stops_json)
                # Validate structure
                if not isinstance(stops, list):
                    raise ValidationError('Dữ liệu điểm dừng phải là mảng')
                
                for stop in stops:
                    if not isinstance(stop, dict):
                        raise ValidationError('Mỗi điểm dừng phải là object')
                    
                    required_fields = ['name', 'lat', 'lng']
                    for field in required_fields:
                        if field not in stop:
                            raise ValidationError(f'Thiếu trường {field} trong điểm dừng')
                
                return stops
            except json.JSONDecodeError:
                raise ValidationError('Dữ liệu JSON không hợp lệ')
        return []
    
    def clean_schedule_json(self):
        """Validate JSON schedule data"""
        schedule_json = self.cleaned_data.get('schedule_json')
        if not schedule_json:
            return {}
        try:
            schedule = json.loads(schedule_json)
            if not isinstance(schedule, dict):
                raise ValidationError('Dữ liệu lịch trình phải là một JSON object.')
            return schedule
        except json.JSONDecodeError:
            raise ValidationError('Dữ liệu JSON cho lịch trình không hợp lệ.')
    
    def save(self, commit=True):
        """Custom save to handle stops data"""
        instance = super().save(commit=False)
        
        # Set stops from cleaned JSON data
        stops_data = self.cleaned_data.get('stops_json', [])
        instance.stops = stops_data
        instance.schedule = self.cleaned_data.get('schedule_json', {})

        if commit:
            instance.save()
        
        return instance
    


class InventoryAlertForm(forms.ModelForm):
    """Form cho cảnh báo tồn kho"""
    
    class Meta:
        model = InventoryAlert
        fields = ['bus', 'alert_type', 'severity', 'message']
        widgets = {
            'bus': forms.Select(attrs={'class': 'form-select'}),
            'alert_type': forms.Select(attrs={'class': 'form-select'}),
            'severity': forms.Select(attrs={'class': 'form-select'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 4})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['bus'].queryset = LibraryBus.objects.all()

class BulkBookUploadForm(forms.Form):
    """Form upload sách hàng loạt"""
    
    csv_file = forms.FileField(
        validators=[FileExtensionValidator(allowed_extensions=['csv'])],
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.csv'})
    )
    default_category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        empty_label="Chọn lĩnh vực mặc định",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    default_location = forms.ModelChoiceField(
        queryset=LibraryBus.objects.filter(operating_status='active'),
        empty_label="Chọn xe bus mặc định",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def clean_csv_file(self):
        """Validate CSV file"""
        csv_file = self.cleaned_data.get('csv_file')
        if csv_file:
            if csv_file.size > 10 * 1024 * 1024:  # 10MB limit
                raise ValidationError('File CSV không được vượt quá 10MB')
        return csv_file

class BookSearchForm(forms.Form):
    """Form tìm kiếm sách nâng cao"""
    
    query = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tìm kiếm sách...'})
    )
    title = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên sách'})
    )
    author = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên tác giả'})
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        empty_label="Tất cả lĩnh vực",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    location = forms.ModelChoiceField(
        queryset=LibraryBus.objects.all(),
        empty_label="Tất cả xe bus",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    status = forms.ChoiceField(
        choices=[('', 'Tất cả trạng thái')] + Book.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    language = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ngôn ngữ'})
    )
    year_from = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Từ năm'})
    )
    year_to = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Đến năm'})
    )
    has_pdf = forms.ChoiceField(
        choices=[('', 'Tất cả'), ('yes', 'Có PDF'), ('no', 'Không có PDF')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    def clean(self):
        """Validate year range"""
        cleaned_data = super().clean()
        year_from = cleaned_data.get('year_from')
        year_to = cleaned_data.get('year_to')
        
        if year_from and year_to and year_from > year_to:
            raise ValidationError('Năm bắt đầu không thể lớn hơn năm kết thúc')
        
        return cleaned_data

class BookDonationForm(forms.ModelForm):
    """Form cho người dùng đóng góp sách"""
    class Meta:
        model = BookDonation
        fields = ['book_title', 'author', 'description', 'book_file']
        widgets = {
            'book_title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập tên sách'}),
            'author': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tác giả (nếu có)'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Mô tả tình trạng sách (mới, cũ, rách trang...)'}),
            'book_file': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.epub,.doc,.docx'}),
        }