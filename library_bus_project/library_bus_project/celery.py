# File: library_bus_project/celery.py
import os
from celery import Celery

# Đặt biến môi trường mặc định cho Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_bus_project.settings')

app = Celery('library_bus_project')

# Sử dụng chuỗi cấu hình từ Django settings, với namespace='CELERY'
app.config_from_object('django.conf:settings', namespace='CELERY')

# Tự động tìm các file tasks.py trong các app đã cài đặt
app.autodiscover_tasks()
