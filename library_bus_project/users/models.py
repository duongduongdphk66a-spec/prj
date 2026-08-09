# File: users/models.py
import os
import sys
from PIL import Image
import logging
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator, FileExtensionValidator, MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth.models import AbstractUser
from django.db.models import Q, Count, Avg
from core.models import TimestampedModel, SoftDeleteModel, CacheMixin

NOTIFICATION_FREQUENCY = [('instant', 'Ngay lập tức'), ('daily', 'Hàng ngày'), ('weekly', 'Hàng tuần'), ('never', 'Không nhận')]
MEMBERSHIP_LEVELS = [('basic', 'Basic'), ('premium', 'Premium'), ('vip', 'VIP')]
ROLE_CHOICES = [('admin', 'Admin'), ('librarian', 'Librarian'), ('member', 'Member')]

logger = logging.getLogger(__name__)

def avatar_upload_path(instance, filename):
    """Tạo đường dẫn upload avatar động"""
    ext = filename.split('.')[-1].lower()
    filename = f'avatar_{instance.user.id}_{timezone.now().strftime("%Y%m%d")}.{ext}'
    return os.path.join('avatars', str(instance.user.id), filename)

def validate_avatar_file_size(value):
    """Validate kích thước file avatar"""
    if value.size > 5 * 1024 * 1024:  # 5MB
        raise ValidationError('File avatar không được vượt quá 5MB.')

class ProfileQuerySet(models.QuerySet):
    """Custom QuerySet cho Profile"""
    def verified(self): return self.filter(is_verified=True)
    def by_location(self, city=None, district=None): 
        filters = Q()
        if city: filters &= Q(city__icontains=city)
        if district: filters &= Q(district__icontains=district)
        return self.filter(filters)
    def active_readers(self): return self.filter(user__borrow_records__isnull=False).distinct()
    def with_reading_stats(self): return self.select_related('user__reading_stats')

class ProfileManager(models.Manager):
    def verified(self): return self.get_queryset().verified()
    def active_readers(self): return self.get_queryset().active_readers()

class Profile(TimestampedModel, CacheMixin):
    """Profile mở rộng cho User với thông tin chi tiết"""
    GENDER_CHOICES = [('M', 'Nam'), ('F', 'Nữ'), ('O', 'Khác'), ('P', 'Không muốn tiết lộ')]
    phone_regex = RegexValidator(regex=r'^(\+84|0)[0-9]{9,10}$', message="Số điện thoại không hợp lệ (VD: 0912345678 hoặc +84912345678)")
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="Người dùng", related_name='profile')
    phone_number = models.CharField(max_length=15, blank=True, null=True, validators=[phone_regex], verbose_name="Số điện thoại", db_index=True, unique=True)
    avatar = models.ImageField(upload_to=avatar_upload_path, default='avatars/default.png', verbose_name="Ảnh đại diện", validators=[validate_avatar_file_size, FileExtensionValidator(['jpg', 'jpeg', 'png', 'gif'])])
    
    # Thông tin địa chỉ chi tiết
    address = models.TextField(blank=True, verbose_name="Địa chỉ chi tiết", max_length=500)
    city = models.CharField(max_length=100, blank=True, verbose_name="Thành phố", db_index=True)
    district = models.CharField(max_length=100, blank=True, verbose_name="Quận/Huyện", db_index=True)
    ward = models.CharField(max_length=100, blank=True, verbose_name="Phường/Xã")
    postal_code = models.CharField(max_length=10, blank=True, verbose_name="Mã bưu điện")
    
    # Thông tin cá nhân
    date_of_birth = models.DateField(blank=True, null=True, verbose_name="Ngày sinh", db_index=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, verbose_name="Giới tính")
    occupation = models.CharField(max_length=100, blank=True, verbose_name="Nghề nghiệp")
    bio = models.TextField(max_length=300, blank=True, verbose_name="Giới thiệu bản thân")
    
    membership_level = models.CharField(max_length=20, choices=MEMBERSHIP_LEVELS, default='basic')
    email_confirmed = models.BooleanField(default=False)

    # Trạng thái tài khoản
    is_verified = models.BooleanField(default=False, verbose_name="Đã xác thực", db_index=True)

    verification_code = models.CharField(max_length=6, blank=True, verbose_name="Mã xác thực")
    verification_expires = models.DateTimeField(blank=True, null=True, verbose_name="Hết hạn mã xác thực")
    
    # Sở thích và cài đặt
    favorite_categories = models.ManyToManyField('inventory.Category', blank=True, verbose_name="Lĩnh vực yêu thích", related_name='favorite_users')
    preferred_language = models.CharField(max_length=10, default='vi', choices=[('vi', 'Tiếng Việt'), ('en', 'English')], verbose_name="Ngôn ngữ ưa thích")
    reading_goal_monthly = models.PositiveSmallIntegerField(default=2, validators=[MinValueValidator(1), MaxValueValidator(50)], verbose_name="Mục tiêu đọc sách/tháng")
    
    # Metadata
    last_login_ip = models.GenericIPAddressField(blank=True, null=True, verbose_name="IP đăng nhập cuối")
    login_count = models.PositiveIntegerField(default=0, verbose_name="Số lần đăng nhập")
    privacy_settings = models.JSONField(default=dict, blank=True, verbose_name="Cài đặt riêng tư")
    
    objects = ProfileManager()
    
    class Meta:
        verbose_name = "Hồ sơ người dùng"
        verbose_name_plural = "Hồ sơ người dùng"
        indexes = [
            models.Index(fields=['city', 'district']),
            models.Index(fields=['date_of_birth']),
            models.Index(fields=['is_verified', 'is_active']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['membership_level']),
            models.Index(fields=['user', 'is_verified']),
        ]

    def __str__(self): return f'Hồ sơ của {self.user.username}'
    def get_absolute_url(self):
        return reverse('user-profile', kwargs={'username': self.user.username})
   
    @property
    def full_name(self): return self.user.get_full_name() or self.user.username
        
    @property
    def age(self):
        if not self.date_of_birth: return None
        today = timezone.now().date()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))

    @property
    def full_address(self):
        """Trả về địa chỉ đầy đủ"""
        parts = [self.address, self.ward, self.district, self.city]
        return ', '.join([part for part in parts if part])

    @property
    def reading_stats_summary(self):
        """Tóm tắt thống kê đọc sách"""
        try:
            stats = self.user.reading_stats
            return {
                'books_borrowed': stats.total_books_borrowed,
                'books_returned': stats.total_books_returned,
                'streak_days': stats.reading_streak_days,
                'level': stats.get_member_level_display()
            }
        except: return {'books_borrowed': 0, 'books_returned': 0, 'streak_days': 0, 'level': 'Đồng'}

    @property
    def completion_percentage(self):
        """Tính % hoàn thành hồ sơ"""
        fields = ['phone_number', 'date_of_birth', 'city', 'district', 'occupation', 'bio']
        completed = sum([1 for field in fields if getattr(self, field)])
        return round((completed / len(fields)) * 100, 1)

    def generate_verification_code(self):
        """Tạo mã xác thực mới"""
        import random
        self.verification_code = str(random.randint(100000, 999999))
        self.verification_expires = timezone.now() + timezone.timedelta(minutes=15)
        self.save(update_fields=['verification_code', 'verification_expires'])

    def verify_code(self, code):
        """Xác thực mã code"""
        if self.verification_code == code and self.verification_expires and timezone.now() < self.verification_expires:
            self.is_verified = True
            self.verification_code = ''
            self.verification_expires = None
            self.save(update_fields=['is_verified', 'verification_code', 'verification_expires'])
            return True
        return False

    def get_absolute_url(self): return reverse('users:profile_detail', args=[self.user.username])

    def save(self, *args, **kwargs):
        # Validate ngày sinh
        if self.date_of_birth and self.date_of_birth > timezone.now().date():
            raise ValidationError('Ngày sinh không thể ở tương lai.')
        
        super().save(*args, **kwargs)
        
        # Xử lý resize avatar
        if self.avatar and self.avatar.name != 'avatars/default.png':
            try:
                img = Image.open(self.avatar.path)
                if img.height > 400 or img.width > 400:
                    output_size = (400, 400)
                    img.thumbnail(output_size, Image.Resampling.LANCZOS)
                    img.save(self.avatar.path, optimize=True, quality=85)
            except (IOError, FileNotFoundError) as e:
                logger.error(f"Error processing avatar for user {self.user.id}: {e}")

class UserInterest(TimestampedModel):
    """Sở thích chi tiết của người dùng"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interests')
    interest_type = models.CharField(max_length=20, choices=[('author', 'Tác giả'), ('genre', 'Thể loại'), ('topic', 'Chủ đề'), ('publisher', 'NXB')], db_index=True)
    interest_value = models.CharField(max_length=200, verbose_name="Giá trị sở thích")
    weight = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(10)], verbose_name="Mức độ quan tâm (1-10)")

    class Meta:
        unique_together = ['user', 'interest_type', 'interest_value']
        verbose_name = "Sở thích người dùng"
        verbose_name_plural = "Sở thích người dùng"
        indexes = [models.Index(fields=['user', 'interest_type'])]


class LoginHistory(TimestampedModel):
    """Lịch sử đăng nhập"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    ip_address = models.GenericIPAddressField(verbose_name="Địa chỉ IP")
    user_agent = models.TextField(verbose_name="User Agent")
    device_info = models.JSONField(default=dict, blank=True, verbose_name="Thông tin thiết bị")

    is_successful = models.BooleanField(default=True, verbose_name="Đăng nhập thành công")

    class Meta:
        verbose_name = "Lịch sử đăng nhập"
        verbose_name_plural = "Lịch sử đăng nhập"
        indexes = [models.Index(fields=['user', 'created_at']), models.Index(fields=['ip_address'])]

class UserPreference(TimestampedModel):
    """Cài đặt tùy chọn người dùng"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')
    theme = models.CharField(max_length=10, choices=[('light', 'Sáng'), ('dark', 'Tối'), ('auto', 'Tự động')], default='light')
    books_per_page = models.PositiveSmallIntegerField(default=20, validators=[MinValueValidator(5), MaxValueValidator(100)])
    auto_renew_books = models.BooleanField(default=False, verbose_name="Tự động gia hạn sách")
    show_reading_progress = models.BooleanField(default=True, verbose_name="Hiển thị tiến độ đọc")
    public_reading_list = models.BooleanField(default=True, verbose_name="Công khai danh sách đọc")


    class Meta:
        verbose_name = "Tùy chọn người dùng"
        verbose_name_plural = "Tùy chọn người dùng"

# Signals
@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Tự động tạo profile và preferences khi tạo user mới"""
    if created:
        Profile.objects.create(user=instance)
        UserPreference.objects.create(user=instance)
    else:
        # Đảm bảo profile luôn tồn tại
        if not hasattr(instance, 'profile'):
            Profile.objects.create(user=instance)
        if not hasattr(instance, 'preferences'):
            UserPreference.objects.create(user=instance)
class UserRole(models.Model):
    """Hệ thống phân quyền chi tiết"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)
    scope = models.JSONField()  # {'library_bus': [1,2], 'permissions': [...]}
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'role'],
                name='unique_user_role',
                condition=Q(valid_to__isnull=True)
            )
        ]
@receiver(pre_save, sender=Profile)
def update_profile_metadata(sender, instance, **kwargs):
    """Cập nhật metadata khi save profile"""
    if instance.pk:  # Chỉ update khi đã tồn tại
        try:
            old_instance = Profile.objects.get(pk=instance.pk)
            # Track thay đổi thông tin quan trọng
            important_fields = ['phone_number', 'city', 'district']
            changes = []
            for field in important_fields:
                if getattr(old_instance, field) != getattr(instance, field):
                    changes.append(field)
            if changes:
                logger.info(f"Profile {instance.user.username} updated fields: {', '.join(changes)}")
        except Profile.DoesNotExist:
            pass

@receiver(post_save, sender=User)
def update_profile_login_stats(sender, instance, **kwargs):
    """Cập nhật thống kê đăng nhập - dùng update() để tránh recursive save"""
    try:
        from users.models import Profile
        Profile.objects.filter(user=instance).update(
            login_count=instance.login_history.count()
        )
    except Exception:
        pass