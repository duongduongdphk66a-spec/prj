# File: core/models.py 
# ==============================================================================
from django.db import models
from django.utils import timezone
from django.core.cache import cache
from django.db.models import QuerySet
from django.conf import settings
import uuid

# --- MIXINS  ---

class CacheMixin:
    """
    Mixin cung cấp chức năng cache thống nhất với cơ chế versioning.
    """
    # --- Cache Versioning ---
    @classmethod
    def _get_version_key(cls):
        return f"{cls.__name__.lower()}:version"

    @classmethod
    def get_current_version(cls):
        return cache.get_or_set(cls._get_version_key(), 1)

    @classmethod
    def invalidate_model_cache(cls):
        """Tăng version để mọi cache key cũ của model này trở thành invalid."""
        try:
            cache.incr(cls._get_version_key())
        except ValueError: # Nếu key chưa tồn tại, set là 2
            cache.set(cls._get_version_key(), 2)

    # --- Key Generation ---
    @classmethod
    def _get_cache_key(cls, key_suffix):
        """Tạo cache key với version hiện tại."""
        version = cls.get_current_version()
        return f"{cls.__module__}.{cls.__name__}:v{version}:{key_suffix}"

    @classmethod
    def _get_instance_cache_key(cls, pk):
        return cls._get_cache_key(f"instance:{pk}")

    @classmethod
    def _get_custom_cache_key(cls, key_suffix):
        return cls._get_cache_key(f"custom:{key_suffix}")

    # --- Caching Methods ---
    @classmethod
    def get_cached_instance(cls, pk, timeout=300):
        key = cls._get_instance_cache_key(pk)
        return cache.get_or_set(key, lambda: cls.objects.get(pk=pk), timeout)

    @classmethod
    def get_cached_custom_data(cls, key_suffix, fetch_func, timeout=300):
        key = cls._get_custom_cache_key(key_suffix)
        return cache.get_or_set(key, fetch_func, timeout)

    # --- Automatic Invalidation on Save/Delete ---
    def save(self, *args, **kwargs):
        # 1. Luôn xóa cache của instance cụ thể
        if hasattr(self, 'pk') and self.pk:
            cache.delete(self._get_instance_cache_key(self.pk))
        
        # 2. Tinh chỉnh Invalidation toàn Model:
        # Nếu chỉ cập nhật các trường tracking/counter/metadata nhỏ thì không tăng model version,
        # tránh gây giật giảm hit-rate cache của hàng ngàn độc giả đang đọc danh sách.
        update_fields = kwargs.get('update_fields')
        minor_tracking_fields = {
            'last_activity', 'last_borrowed', 'login_count', 'last_login_ip',
            '_book_count', '_last_book_update', 'view_count', 'like_count', 
            'updated_at', 'modified_at', 'reading_streak_days', 'max_reading_streak'
        }
        
        if not update_fields or not set(update_fields).issubset(minor_tracking_fields):
            self.__class__.invalidate_model_cache()
            
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if hasattr(self, 'pk') and self.pk:
            cache.delete(self._get_instance_cache_key(self.pk))
        self.__class__.invalidate_model_cache()
        super().delete(*args, **kwargs)



class AuditMixin(models.Model):
    """Theo dõi lịch sử thay đổi ai đã tạo/sửa"""
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='created_%(class)s',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='modified_%(class)s',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class Meta:
        abstract = True

# --- BASE MODELS ĐÃ CẬP NHẬT ---
class BaseQuerySet(QuerySet):
    """Custom QuerySet với các method tiện ích"""
    def active(self): return self.filter(is_active=True)
    def inactive(self): return self.filter(is_active=False)
    def recent(self, days=30): return self.filter(created_at__gte=timezone.now() - timezone.timedelta(days=days))

class BaseManager(models.Manager):
    def get_queryset(self): return BaseQuerySet(self.model, using=self._db)
    def active(self): return self.get_queryset().active()
    def recent(self, days=30): return self.get_queryset().recent(days)

class TimestampedModel(CacheMixin, models.Model):
    """Base model với UUID và timestamps. Tất cả các model khác kế thừa từ đây sẽ có chức năng cache."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Ngày tạo")
    updated_at = models.DateTimeField(auto_now=True, db_index=True, verbose_name="Cập nhật lần cuối")
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Trạng thái hoạt động")
    
    objects = BaseManager()
    
    class Meta:
        abstract = True
        get_latest_by = 'created_at'

class SoftDeleteManager(BaseManager):
    def get_queryset(self): return super().get_queryset().filter(deleted_at__isnull=True)

class SoftDeleteModel(TimestampedModel, AuditMixin): 
    """Model hỗ trợ soft delete với audit trail"""
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='deleted_%(class)s',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    objects = SoftDeleteManager()
    all_objects = BaseManager()
    
    def delete(self, deleted_by=None, using=None, keep_parents=False): 
        self.deleted_at = timezone.now()
        self.is_active = False
        self.deleted_by = deleted_by
        self.save(update_fields=['deleted_at', 'is_active', 'deleted_by'])
    
    def restore(self):
        self.deleted_at = None
        self.is_active = True
        self.deleted_by = None
        self.save(update_fields=['deleted_at', 'is_active', 'deleted_by'])
    
    class Meta:
        abstract = True