# Import celery_app để đảm bảo nó được load khi Django khởi động.
from .celery import app as celery_app

__all__ = ('celery_app',)
