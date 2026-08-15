# File: blog/forms.py 
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils.html import strip_tags
from django.utils import timezone
from django.db.models import Q, Count
from django.core.cache import cache
from .models import Post, Newsletter, BlogCategory, BlogTag, PostRating
import re


class PostForm(forms.ModelForm):
    """Form nâng cao cho tác giả tạo và chỉnh sửa bài viết blog."""
    
    # Custom fields cho better UX
    new_tags = forms.CharField(required=False, max_length=500, widget=forms.TextInput(attrs={'placeholder': 'Thêm tags mới (cách nhau bởi dấu phẩy)', 'class': 'form-control'}), help_text="Nhập tags mới, cách nhau bởi dấu phẩy")
    
    class Meta:
        model = Post
        fields = ['title', 'excerpt', 'content', 'featured_image', 'featured_image_alt', 'categories', 'tags', 'status', 'publish_date', 'content_type', 'allow_comments', 'is_featured', 'is_pinned', 'seo_title', 'seo_description']
        
        labels = {'title': 'Tiêu đề bài viết', 'excerpt': 'Tóm tắt ngắn', 'content': 'Nội dung chính', 'featured_image': 'Ảnh bìa', 'featured_image_alt': 'Mô tả ảnh (Alt text)', 'categories': 'Chuyên mục', 'tags': 'Tags hiện có', 'status': 'Trạng thái', 'publish_date': 'Thời gian xuất bản', 'content_type': 'Loại nội dung', 'allow_comments': 'Cho phép bình luận', 'is_featured': 'Bài viết nổi bật', 'is_pinned': 'Ghim bài viết', 'seo_title': 'SEO Title', 'seo_description': 'SEO Description'}
        
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập tiêu đề hấp dẫn...'}),
            'excerpt': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Tóm tắt ngắn gọn về bài viết...'}),
            'content': forms.Textarea(attrs={'rows': 15, 'class': 'form-control editor'}),
            'featured_image': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'featured_image_alt': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mô tả ảnh cho SEO và accessibility'}),
            'categories': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-control', 'size': '6'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'publish_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'content_type': forms.Select(attrs={'class': 'form-select'}),
            'allow_comments': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_pinned': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'seo_title': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '160', 'placeholder': 'Title tối ưu cho công cụ tìm kiếm'}),
            'seo_description': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'maxlength': '320', 'placeholder': 'Mô tả ngắn gọn cho search results'})
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Giới hạn quyền cho user thường
        if self.user and not self.user.is_staff:
            self.fields.pop('is_featured', None)
            self.fields.pop('is_pinned', None)
            if 'status' in self.fields:
                self.fields['status'].choices = [('draft', 'Bản nháp'), ('published', 'Đã xuất bản')]
        
        # Tối ưu queryset với cache
        self.fields['categories'].queryset = BlogCategory.objects.filter(is_featured=True).order_by('sort_order', 'name')
        self.fields['tags'].queryset = BlogTag.objects.filter(usage_count__gt=0).order_by('-usage_count', 'name')[:50]  # Giới hạn tags hiển thị

    def clean_title(self):
        title = self.cleaned_data.get('title')
        if not title:
            raise ValidationError("Tiêu đề không được để trống.")
        if len(title) < 10:
            raise ValidationError("Tiêu đề phải có ít nhất 10 ký tự.")
        
        # Kiểm tra trùng lặp với tối ưu query
        existing = Post.objects.filter(title__iexact=title).only('id')
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise ValidationError("Tiêu đề này đã tồn tại. Vui lòng chọn tiêu đề khác.")
        return title

    def clean_content(self):
        content = self.cleaned_data.get('content')
        if not content:
            raise ValidationError("Nội dung không được để trống.")
        
        import bleach
        allowed_tags = ['p', 'b', 'i', 'u', 'em', 'strong', 'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'br', 'img', 'blockquote', 'pre', 'code']
        allowed_attributes = {'*': ['class', 'style'], 'a': ['href', 'title', 'target'], 'img': ['src', 'alt', 'width', 'height']}
        content = bleach.clean(content, tags=allowed_tags, attributes=allowed_attributes, styles=['color', 'text-align', 'font-weight'])
        
        clean_content = strip_tags(content).strip()
        if len(clean_content) < 100:
            raise ValidationError("Nội dung phải có ít nhất 100 ký tự (không tính thẻ HTML).")
        
        # Kiểm tra spam patterns
        spam_patterns = ['click here', 'buy now', 'free money', 'guaranteed']
        content_lower = clean_content.lower()
        spam_count = sum(1 for pattern in spam_patterns if pattern in content_lower)
        if spam_count > 2:
            raise ValidationError("Nội dung có thể chứa spam. Vui lòng kiểm tra lại.")
        
        return content

    def clean_seo_title(self):
        seo_title = self.cleaned_data.get('seo_title')
        if seo_title and len(seo_title) > 160:
            raise ValidationError("SEO Title không được vượt quá 160 ký tự.")
        return seo_title

    def clean_seo_description(self):
        seo_desc = self.cleaned_data.get('seo_description')
        if seo_desc and len(seo_desc) > 320:
            raise ValidationError("SEO Description không được vượt quá 320 ký tự.")
        return seo_desc

    def clean_featured_image(self):
        image = self.cleaned_data.get('featured_image')
        if image:
            if image.size > 5 * 1024 * 1024:  # 5MB
                raise ValidationError("Kích thước ảnh không được vượt quá 5MB.")
            if not image.content_type.startswith('image/'):
                raise ValidationError("File tải lên phải là ảnh.")
            
            # Kiểm tra định dạng được hỗ trợ
            allowed_formats = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
            if image.content_type not in allowed_formats:
                raise ValidationError("Chỉ hỗ trợ định dạng JPG, PNG, WEBP.")
        return image

    def clean_publish_date(self):
        publish_date = self.cleaned_data.get('publish_date')
        status = self.cleaned_data.get('status')
        
        if status == 'published' and publish_date:
            if publish_date > timezone.now() + timezone.timedelta(days=365):
                raise ValidationError("Không thể lên lịch xuất bản quá 1 năm.")
        
        return publish_date

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set author
        if self.user:
            instance.author = self.user
        
        # Auto-generate slug if not exists
        if not instance.slug:
            instance.slug = slugify(instance.title)
        
        # Set publish_date for published posts
        if instance.status == 'published' and not instance.publish_date:
            instance.publish_date = timezone.now()
        
        if commit:
            instance.save()
            
            # Xử lý tags mới
            new_tags = self.cleaned_data.get('new_tags', '')
            if new_tags:
                tag_names = [name.strip() for name in new_tags.split(',') if name.strip()]
                for tag_name in tag_names:
                    tag, created = BlogTag.objects.get_or_create(
                        name=tag_name,
                        defaults={'slug': slugify(tag_name)}
                    )
                    instance.tags.add(tag)
            
            # Lưu M2M relationships
            self.save_m2m()
            
            # Clear cache
            cache.delete_many([
                f"custom:popular_posts_7_5",
                f"custom:recent_posts_5",
                f"custom:related_posts_{instance.id}_4"
            ])
        
        return instance


class QuickPostForm(forms.ModelForm):
    """Form nhanh cho việc tạo bài viết đơn giản."""
    
    class Meta:
        model = Post
        fields = ['title', 'content', 'categories', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tiêu đề bài viết...'}),
            'content': forms.Textarea(attrs={'rows': 10, 'class': 'form-control', 'placeholder': 'Nội dung bài viết...'}),
            'categories': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
            'status': forms.Select(attrs={'class': 'form-select'})
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Giới hạn categories cho form nhanh
        self.fields['categories'].queryset = BlogCategory.objects.filter(is_featured=True).order_by('sort_order')

    def clean_content(self):
        content = self.cleaned_data.get('content')
        if content:
            import bleach
            allowed_tags = ['p', 'b', 'i', 'u', 'em', 'strong', 'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'br', 'img', 'blockquote', 'pre', 'code']
            allowed_attributes = {'*': ['class', 'style'], 'a': ['href', 'title', 'target'], 'img': ['src', 'alt', 'width', 'height']}
            return bleach.clean(content, tags=allowed_tags, attributes=allowed_attributes, styles=['color', 'text-align', 'font-weight'])
        return content

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user:
            instance.author = self.user
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class NewsletterSubscriptionForm(forms.ModelForm):
    """Form đăng ký newsletter với validation nâng cao."""
    
    terms_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Tôi đồng ý nhận email thông báo"
    )
    
    class Meta:
        model = Newsletter
        fields = ['email', 'frequency', 'categories']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'frequency': forms.Select(attrs={'class': 'form-select'}),
            'categories': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
        }
        labels = {
            'email': 'Email của bạn',
            'frequency': 'Tần suất nhận email',
            'categories': 'Chuyên mục quan tâm'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Chỉ hiển thị featured categories
        self.fields['categories'].queryset = BlogCategory.objects.filter(is_featured=True).order_by('sort_order')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Newsletter.objects.filter(email=email).exists():
            raise ValidationError("Email này đã được đăng ký.")
        
        # Kiểm tra email domain
        blocked_domains = ['tempmail.com', '10minutemail.com', 'guerrillamail.com']
        email_domain = email.split('@')[1].lower()
        if email_domain in blocked_domains:
            raise ValidationError("Email tạm thời không được phép.")
        
        return email


class PostSearchForm(forms.Form):
    """Form tìm kiếm bài viết với nhiều tiêu chí."""
    
    query = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tìm kiếm bài viết...'}),
        label=''
    )
    category = forms.ModelChoiceField(
        queryset=BlogCategory.objects.all(),
        required=False,
        empty_label="Tất cả chuyên mục",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    content_type = forms.ChoiceField(
        choices=[('', 'Tất cả loại')] + Post.content_type.field.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    sort_by = forms.ChoiceField(
        choices=[
            ('newest', 'Mới nhất'),
            ('oldest', 'Cũ nhất'),
            ('popular', 'Phổ biến'),
            ('most_liked', 'Được thích nhiều'),
            ('most_viewed', 'Xem nhiều')
        ],
        required=False,
        initial='newest',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tối ưu queryset
        self.fields['category'].queryset = BlogCategory.objects.filter(post_count__gt=0).order_by('sort_order', 'name')


class PostRatingForm(forms.ModelForm):
    """Form đánh giá bài viết."""
    
    class Meta:
        model = PostRating
        fields = ['score']
        widgets = {
            'score': forms.RadioSelect(attrs={'class': 'form-check-input'})
        }
        labels = {
            'score': 'Đánh giá của bạn'
        }

    def __init__(self, *args, **kwargs):
        self.post = kwargs.pop('post', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        if self.post and self.user:
            if PostRating.objects.filter(post=self.post, user=self.user).exists():
                raise ValidationError("Bạn đã đánh giá bài viết này rồi.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.post:
            instance.post = self.post
        if self.user:
            instance.user = self.user
        if commit:
            instance.save()
        return instance


class CommentForm(forms.Form):
    """Form bình luận đơn giản."""
    
    content = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Viết bình luận của bạn...'}),
        max_length=1000,
        label=''
    )
    
    def clean_content(self):
        content = self.cleaned_data.get('content')
        if len(content.strip()) < 5:
            raise ValidationError("Bình luận phải có ít nhất 5 ký tự.")
        
        # Kiểm tra spam
        spam_words = ['spam', 'advertisement', 'click here', 'buy now']
        content_lower = content.lower()
        if any(word in content_lower for word in spam_words):
            raise ValidationError("Bình luận có thể chứa spam.")
        
        return content


class BulkPostActionForm(forms.Form):
    """Form cho admin thực hiện hành động hàng loạt."""
    
    action = forms.ChoiceField(
        choices=[
            ('publish', 'Xuất bản'),
            ('unpublish', 'Hủy xuất bản'),
            ('archive', 'Lưu trữ'),
            ('delete', 'Xóa'),
            ('feature', 'Đánh dấu nổi bật'),
            ('unfeature', 'Hủy nổi bật'),
            ('pin', 'Ghim bài viết'),
            ('unpin', 'Hủy ghim')
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    posts = forms.ModelMultipleChoiceField(
        queryset=Post.objects.all(),
        widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user and not user.is_superuser:
            # Giới hạn cho author
            self.fields['posts'].queryset = Post.objects.filter(author=user).order_by('-created_at')
            # Giới hạn actions
            self.fields['action'].choices = [
                ('publish', 'Xuất bản'),
                ('unpublish', 'Hủy xuất bản'),
                ('archive', 'Lưu trữ')
            ]


class AdvancedSearchForm(forms.Form):
    """Form tìm kiếm nâng cao với nhiều bộ lọc."""
    
    query = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tìm kiếm...'})
    )
    categories = forms.ModelMultipleChoiceField(
        queryset=BlogCategory.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    tags = forms.ModelMultipleChoiceField(
        queryset=BlogTag.objects.filter(usage_count__gt=0),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    content_type = forms.ChoiceField(
        choices=[('', 'Tất cả')] + Post.content_type.field.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    author = forms.ModelChoiceField(
        queryset=User.objects.filter(blog_posts__isnull=False).distinct(),
        required=False,
        empty_label="Tất cả tác giả",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    has_featured_image = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    min_reading_time = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Phút'})
    )
    max_reading_time = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Phút'})
    )
    sort_by = forms.ChoiceField(
        choices=[
            ('newest', 'Mới nhất'),
            ('oldest', 'Cũ nhất'),
            ('popular', 'Phổ biến'),
            ('most_liked', 'Được thích nhiều'),
            ('most_viewed', 'Xem nhiều'),
            ('reading_time', 'Thời gian đọc')
        ],
        initial='newest',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tối ưu queryset với cache
        self.fields['categories'].queryset = BlogCategory.objects.filter(post_count__gt=0).order_by('sort_order', 'name')
        self.fields['tags'].queryset = BlogTag.objects.filter(usage_count__gt=0).order_by('-usage_count', 'name')[:100]
        self.fields['author'].queryset = User.objects.filter(blog_posts__status='published').annotate(post_count=Count('blog_posts')).filter(post_count__gt=0).order_by('-post_count')

    def clean(self):
        cleaned_data = super().clean()
        
        # Validate date range
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        if date_from and date_to and date_from > date_to:
            raise ValidationError("Ngày bắt đầu không thể sau ngày kết thúc.")
        
        # Validate reading time range
        min_time = cleaned_data.get('min_reading_time')
        max_time = cleaned_data.get('max_reading_time')
        if min_time and max_time and min_time > max_time:
            raise ValidationError("Thời gian đọc tối thiểu không thể lớn hơn tối đa.")
        
        return cleaned_data


class CategoryFilterForm(forms.Form):
    """Form lọc theo category cho sidebar."""
    
    category = forms.ModelChoiceField(
        queryset=BlogCategory.objects.filter(post_count__gt=0),
        required=False,
        empty_label="Tất cả chuyên mục",
        widget=forms.Select(attrs={'class': 'form-select', 'onchange': 'this.form.submit()'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = BlogCategory.objects.filter(post_count__gt=0).order_by('sort_order', 'name')


class TagFilterForm(forms.Form):
    """Form lọc theo tag."""
    
    tag = forms.ModelChoiceField(
        queryset=BlogTag.objects.filter(usage_count__gt=0),
        required=False,
        empty_label="Tất cả tags",
        widget=forms.Select(attrs={'class': 'form-select', 'onchange': 'this.form.submit()'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tag'].queryset = BlogTag.objects.filter(usage_count__gt=0).order_by('-usage_count', 'name')[:50]


class PostStatusForm(forms.Form):
    """Form thay đổi trạng thái bài viết nhanh."""
    
    status = forms.ChoiceField(
        choices=Post.status.field.choices,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    publish_date = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        self.post = kwargs.pop('post', None)
        super().__init__(*args, **kwargs)
        
        if self.post:
            self.fields['status'].initial = self.post.status
            self.fields['publish_date'].initial = self.post.publish_date

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        publish_date = cleaned_data.get('publish_date')
        
        if status == 'published' and not publish_date:
            cleaned_data['publish_date'] = timezone.now()
        
        return cleaned_data

# --- MOVED FROM COMMUNITY ---
# File: blog/forms.py
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.forms import ModelForm, CharField, Textarea, Select, CheckboxInput, NumberInput, DateInput, EmailInput
from django.forms.widgets import HiddenInput
from .models import (
    BookReview, Comment, ReviewHelpfulness, Report
)
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Fieldset, Div, Submit, Button, Row, Column
from crispy_forms.bootstrap import InlineRadios, FormActions
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)

class BookReviewForm(ModelForm):
    """Form đánh giá sách với validation và UI được tối ưu"""
    rating = forms.ChoiceField(choices=[(i/2, f'{i/2} ⭐') for i in range(1, 11)], widget=forms.RadioSelect(attrs={'class': 'rating-radio'}))
    review_text = forms.CharField(widget=forms.Textarea(attrs={'rows': 6, 'placeholder': 'Chia sẻ cảm nhận của bạn về cuốn sách này...', 'class': 'form-control'}), required=False)
    title = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'placeholder': 'Tiêu đề cho đánh giá của bạn', 'class': 'form-control'}), required=False)
    
    class Meta:
        model = BookReview
        fields = ['rating', 'title', 'review_text', 'reading_progress', 'is_spoiler']
        widgets = {
            'reading_progress': forms.Select(attrs={'class': 'form-select'}),
            'is_spoiler': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.book = kwargs.pop('book', None)
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset('Đánh giá sách', 
                Row(Column('rating', css_class='col-md-6'), Column('reading_progress', css_class='col-md-6')),
                Field('title'),
                Field('review_text'),
                Field('is_spoiler', wrapper_class='form-check')
            ),
            FormActions(Submit('submit', 'Gửi đánh giá', css_class='btn btn-primary'), Button('cancel', 'Hủy', css_class='btn btn-secondary'))
        )
        
        if self.instance.pk:
            self.helper.layout.append(Button('delete', 'Xóa đánh giá', css_class='btn btn-danger'))
    
    def clean_review_text(self):
        text = self.cleaned_data.get('review_text', '')
        if text and len(text.strip()) < 10:
            raise ValidationError('Nội dung đánh giá phải có ít nhất 10 ký tự.')
        return text.strip()
    
    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        try:
            rating = float(rating)
            if rating < 0.5 or rating > 5.0:
                raise ValidationError('Đánh giá phải từ 0.5 đến 5.0 sao.')
        except (ValueError, TypeError):
            raise ValidationError('Đánh giá không hợp lệ.')
        return rating
    
    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('title') and cleaned_data.get('review_text'):
            cleaned_data['title'] = f"Đánh giá về {self.book.title if self.book else 'cuốn sách'}"
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user: instance.user = self.user
        if self.book: instance.book = self.book
        if commit: instance.save()
        return instance

class CommentForm(ModelForm):
    """Form comment với threading và validation"""
    content = forms.CharField(widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Viết bình luận...', 'class': 'form-control'}), label='Bình luận')
    
    class Meta:
        model = Comment
        fields = ['content']
    
    def __init__(self, *args, **kwargs):
        self.post = kwargs.pop('post', None)
        self.parent = kwargs.pop('parent', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('content'),
            FormActions(Submit('submit', 'Gửi bình luận', css_class='btn btn-primary btn-sm'))
        )
        
        if self.parent:
            self.fields['content'].widget.attrs['placeholder'] = f'Trả lời @{self.parent.author.username}...'
            self.helper.layout = Layout(
                Field('content'),
                FormActions(Submit('submit', 'Trả lời', css_class='btn btn-primary btn-sm'), Button('cancel', 'Hủy', css_class='btn btn-secondary btn-sm'))
            )
    
    def clean_content(self):
        content = self.cleaned_data.get('content', '').strip()
        if len(content) < 5:
            raise ValidationError('Bình luận phải có ít nhất 5 ký tự.')
        return content
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user: instance.author = self.user
        if self.post: instance.post = self.post
        if self.parent: instance.parent = self.parent
        if commit: instance.save()
        return instance


class BookReviewForm(forms.ModelForm):
    class Meta:
        model = BookReview
        fields = ['rating', 'title', 'review_text', 'is_spoiler', 'reading_progress']
        
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.book = kwargs.pop('book', None)
        super().__init__(*args, **kwargs)

class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['reason', 'description']

class ReviewHelpfulnessForm(forms.ModelForm):
    class Meta:
        model = ReviewHelpfulness
        fields = ['is_helpful']

class SearchForm(forms.Form):
    q = forms.CharField(required=False)
