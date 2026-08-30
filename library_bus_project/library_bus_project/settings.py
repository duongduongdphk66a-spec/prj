# File: library_bus_project/settings.py
# =============================================================================
# LIBRARY BUS PROJECT - OPTIMIZED FOR 50,000 USERS / 500 CONCURRENT
# =============================================================================
import os
from pathlib import Path
from django.contrib.messages import constants as messages_constants
from django.core.exceptions import ImproperlyConfigured
from celery.schedules import crontab
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# --- SECURITY ---
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "SECRET_KEY environment variable is required. "
        "Set it in your .env file. Generate one with: "
        "python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
    )
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')


# --- APPLICATION DEFINITION ---
DJANGO_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.forms',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
]

THIRD_PARTY_APPS = [
    'rangefilter',
]

LOCAL_APPS = [
    'core.apps.CoreConfig',
    'users.apps.UsersConfig',
    'inventory.apps.InventoryConfig',
    'transactions.apps.TransactionsConfig',
    'analytics.apps.AnalyticsConfig',
    'notifications.apps.NotificationsConfig',
    'blog.apps.BlogConfig',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS


# --- MIDDLEWARE ---
# Thêm WhiteNoise (static files) và GZip (compression) cho production
# LƯU Ý: GZipMiddleware phải ở đầu stack để nén response trước khi các middleware khác xử lý.
# CẢNH BÁO BREACH: GZip + HTTPS có thể bị tấn công BREACH nếu response chứa secrets.
# Django CSRF protection đã có biện pháp chống BREACH (random mask trên token).
MIDDLEWARE = [
    'django.middleware.gzip.GZipMiddleware',                # Nén response (phải ở đầu)
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',           # Serve static files hiệu quả
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'library_bus_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
         'DIRS': [os.path.join(BASE_DIR, 'template')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'notifications.context_processors.unread_notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'library_bus_project.wsgi.application'


# --- DATABASE ---
# MySQL với connection pooling cho 500 concurrent users
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'tsdd'),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'CONN_MAX_AGE': 600,             # Giữ connection 10 phút, tránh tạo mới liên tục
        'CONN_HEALTH_CHECKS': True,       # Kiểm tra connection còn sống trước khi dùng lại
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        },
    }
}


# --- CACHING ---
# Chuyển từ LocMemCache → Redis cache cho multi-process/multi-worker
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 600},
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "RETRY_ON_TIMEOUT": True,
        },
        "KEY_PREFIX": "lbp",
        "TIMEOUT": 300,  # Default cache timeout: 5 phút
    }
}

# Fallback: Tự động detect Redis. Nếu Redis chưa sẵn sàng, dùng LocMemCache
def _check_redis_available():
    """Kiểm tra Redis có đang chạy không."""
    try:
        import redis
        r = redis.Redis.from_url(os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'), socket_timeout=1)
        r.ping()
        return True
    except Exception:
        return False

if not _check_redis_available():
    import logging
    logging.getLogger(__name__).warning("⚠️  Redis không khả dụng. Dùng LocMemCache (chỉ phù hợp cho dev).")
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        }
    }
    # Fallback session về DB nếu không có Redis
    SESSION_ENGINE = "django.contrib.sessions.backends.db"
else:
    # --- SESSION ---
    # Dùng Redis cache cho sessions → scale across workers
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "default"

SESSION_COOKIE_AGE = 86400  # 24 giờ
SESSION_COOKIE_HTTPONLY = True   # Ngăn JavaScript truy cập session cookie
CSRF_COOKIE_HTTPONLY = False     # Cho phép JS đọc CSRF token (chuẩn Django cho AJAX requests)
X_FRAME_OPTIONS = 'DENY'        # Chống clickjacking
SECURE_CONTENT_TYPE_NOSNIFF = True  # Chống MIME-type sniffing (bật cả dev lẫn production)


# --- CELERY SETTINGS ---
# QUAN TRỌNG: Đã xóa CELERY_TASK_ALWAYS_EAGER = True
# Tasks sẽ chạy async qua Redis broker
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/0')
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Ho_Chi_Minh'

# Celery performance tuning
CELERY_WORKER_PREFETCH_MULTIPLIER = 4
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_TIME_LIMIT = 300       # Hard limit: 5 phút
CELERY_TASK_SOFT_TIME_LIMIT = 240  # Soft limit: 4 phút

CELERY_BEAT_SCHEDULE = {
    'daily_midnight_maintenance': {
        'task': 'core.tasks.daily_maintenance',
        'schedule': crontab(hour=0, minute=0),
    },
    'recalculate-popularity': {
        'task': 'recalculate_popularity_scores_task',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),
    },
    'cache-warmup': {
        'task': 'cache_warmup_task',
        'schedule': crontab(hour=5, minute=0),
    },
    'check-overdue-books': {
        'task': 'transactions.tasks.check_overdue_books',
        'schedule': crontab(hour=6, minute=0),
    },
    'send-due-reminders': {
        'task': 'transactions.tasks.send_due_reminders',
        'schedule': crontab(hour=8, minute=0),
    },
    'process-reservation-queue': {
        'task': 'transactions.tasks.process_reservation_queue',
        'schedule': crontab(minute='*/30'),
    },
}


# --- PASSWORD VALIDATION & HASHING ---
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# --- INTERNATIONALIZATION ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_TZ = True


# --- STATIC & MEDIA FILES ---
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# --- SITE ---
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'yourdomain.com')
SITE_NAME = os.environ.get('SITE_NAME', 'Library System')
SITE_URL = f'https://{SITE_DOMAIN}' if not DEBUG else f'http://localhost:8000'


# --- EMAIL ---
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend' if not DEBUG else 'django.core.mail.backends.console.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'library@system.com')


# --- AUTHENTICATION ---
LOGIN_URL = 'users:login'
LOGIN_REDIRECT_URL = 'users:dashboard'
LOGOUT_REDIRECT_URL = 'index'


# --- DEFAULT PRIMARY KEY FIELD TYPE ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# --- MESSAGES ---
MESSAGE_TAGS = {
    messages_constants.DEBUG: 'secondary',
    messages_constants.INFO: 'info',
    messages_constants.SUCCESS: 'success',
    messages_constants.WARNING: 'warning',
    messages_constants.ERROR: 'danger',
}


# --- LOGGING ---
# Structured logging cho production debugging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} {module}.{funcName}:{lineno} - {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'] if not DEBUG else ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',  # Đổi thành DEBUG để xem SQL queries
            'propagate': False,
        },
        # App loggers
        'users': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'inventory': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'transactions': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'analytics': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'blog': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'notifications': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'celery': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}


# --- PRODUCTION SECURITY ---
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SAMESITE = 'Lax'
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

# --- JAZZMIN SETTINGS ---
JAZZMIN_SETTINGS = {
    "site_title": "Thư viện Di động Admin",
    "site_header": "Hệ thống Quản lý Thư viện Di động",
    "site_brand": "Thư viện Di động",
    "site_logo": None,
    "welcome_sign": "Chào mừng đến với hệ thống quản trị Thư viện Di động",
    "copyright": "Thư viện Di động Ltd",
    "search_model": ["auth.User"],
    "user_avatar": None,
    "topmenu_links": [
        {"name": "Trang chủ", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "Về Website", "url": "/", "new_window": True},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "users.User": "fas fa-user",
        "users.Profile": "fas fa-id-card",
        "users.UserPreference": "fas fa-sliders-h",
        "users.UserInterest": "fas fa-heart",
        "users.UserRole": "fas fa-user-shield",
        "users.LoginHistory": "fas fa-sign-in-alt",
        "inventory.Book": "fas fa-book",
        "inventory.LibraryBus": "fas fa-bus",
        "inventory.BusRoute": "fas fa-route",
        "inventory.Category": "fas fa-tags",
        "inventory.BookDonation": "fas fa-hand-holding-heart",
        "inventory.BookRating": "fas fa-star",
        "inventory.InventoryAlert": "fas fa-exclamation-triangle",
        "transactions.BorrowRecord": "fas fa-clipboard-list",
        "transactions.BookReservation": "fas fa-clock",
        "transactions.ShippingRequest": "fas fa-shipping-fast",
        "transactions.FinePayment": "fas fa-money-bill-wave",
        "transactions.BulkTransaction": "fas fa-layer-group",
        "analytics.DailyStats": "fas fa-chart-line",
        "analytics.BookAnalytics": "fas fa-chart-bar",
        "analytics.BusAnalytics": "fas fa-chart-pie",
        "analytics.UserReadingStats": "fas fa-book-reader",
        "analytics.UserActivity": "fas fa-user-clock",
        "analytics.BookRecommendation": "fas fa-magic",
        "blog.Post": "fas fa-newspaper",
        "blog.Comment": "fas fa-comments",
        "blog.BlogCategory": "fas fa-list",
        "blog.BlogTag": "fas fa-tag",
        "blog.Newsletter": "fas fa-envelope-open-text",
        "blog.Report": "fas fa-flag",
        "notifications.UserNotification": "fas fa-bell",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": False,
    "custom_css": "css/admin_premium.css",
    "custom_js": None,
    "show_ui_builder": False,
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-primary",
    "accent": "accent-primary",
    "navbar": "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed": False,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-light-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "default_theme_mode": "light",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    },
    "actions_sticky_top": False
}