# File: notifications/tests.py
# ==============================================================================
# Test cases cho Notifications App — Models, Helpers, Views
# ==============================================================================

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta

from notifications.models import (
    UserNotification, create_notification,
    get_user_unread_count, cleanup_old_notifications
)

User = get_user_model()


class UserNotificationModelTest(TestCase):
    """Test UserNotification model và các methods"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='notifuser', password='pass123', email='notif@test.com'
        )
        self.notification = UserNotification.objects.create(
            recipient=self.user,
            title='Test Notification',
            message='Test message content',
            notification_type='info'
        )

    def test_notification_created_unread(self):
        """Notification mới tạo phải có is_read=False"""
        self.assertFalse(self.notification.is_read)
        self.assertIsNone(self.notification.read_at)

    def test_mark_as_read(self):
        """mark_as_read phải cập nhật is_read và read_at"""
        self.notification.mark_as_read()
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)
        self.assertIsNotNone(self.notification.read_at)

    def test_mark_as_read_idempotent(self):
        """Gọi mark_as_read lần 2 không thay đổi gì"""
        self.notification.mark_as_read()
        first_read_at = self.notification.read_at
        self.notification.mark_as_read()
        self.assertEqual(self.notification.read_at, first_read_at)

    def test_str_representation(self):
        """__str__ phải chứa username và title"""
        result = str(self.notification)
        self.assertIn(self.user.username, result)

    def tearDown(self):
        cache.clear()


class NotificationQuerySetTest(TestCase):
    """Test custom QuerySet filters"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='qsuser', password='pass123'
        )
        self.unread = UserNotification.objects.create(
            recipient=self.user, title='Unread', message='msg',
            is_read=False
        )
        self.read = UserNotification.objects.create(
            recipient=self.user, title='Read', message='msg',
            is_read=True, read_at=timezone.now()
        )

    def test_unread_filter(self):
        """unread() chỉ trả về thông báo chưa đọc"""
        unread = UserNotification.objects.unread()
        self.assertIn(self.unread, unread)
        self.assertNotIn(self.read, unread)

    def test_unread_for_user(self):
        """unread_for_user trả về thông báo chưa đọc của user cụ thể"""
        count = UserNotification.objects.unread_for_user(self.user).count()
        self.assertEqual(count, 1)


class CreateNotificationHelperTest(TestCase):
    """Test create_notification helper function"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='helperuser', password='pass123', email='helper@test.com'
        )

    def test_create_notification_success(self):
        """create_notification tạo notification thành công"""
        notif = create_notification(
            recipient=self.user,
            title='Helper Test',
            message='Created via helper',
            notification_type='success',
            send_email=False
        )
        self.assertIsNotNone(notif)
        self.assertEqual(notif.title, 'Helper Test')
        self.assertEqual(notif.recipient, self.user)

    def test_create_notification_clears_cache(self):
        """create_notification phải clear unread count cache"""
        cache_key = f"unread_count_{self.user.id}"
        cache.set(cache_key, 99)
        create_notification(
            recipient=self.user,
            title='Cache Clear Test',
            message='msg',
            send_email=False
        )
        cached_value = cache.get(cache_key)
        self.assertIsNone(cached_value)

    def tearDown(self):
        cache.clear()


class GetUnreadCountTest(TestCase):
    """Test get_user_unread_count helper"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='countuser', password='pass123'
        )

    def test_unread_count_zero_when_no_notifications(self):
        """Không có notification thì count = 0"""
        count = get_user_unread_count(self.user.id)
        self.assertEqual(count, 0)

    def test_unread_count_correct(self):
        """Count phải chính xác với số notifications chưa đọc"""
        for i in range(3):
            UserNotification.objects.create(
                recipient=self.user, title=f'Notif {i}',
                message='msg', is_read=False
            )
        UserNotification.objects.create(
            recipient=self.user, title='Read Notif',
            message='msg', is_read=True
        )
        cache.clear()
        count = get_user_unread_count(self.user.id)
        self.assertEqual(count, 3)

    def tearDown(self):
        cache.clear()


class CleanupOldNotificationsTest(TestCase):
    """Test cleanup_old_notifications utility"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='cleanupuser', password='pass123'
        )

    def test_cleanup_deletes_old_read_notifications(self):
        """cleanup_old_notifications xóa notifications cũ đã đọc"""
        # Tạo notification cũ đã đọc
        old_notif = UserNotification.objects.create(
            recipient=self.user, title='Old', message='msg',
            is_read=True, read_at=timezone.now()
        )
        # Force set created_at cũ
        UserNotification.objects.filter(pk=old_notif.pk).update(
            created_at=timezone.now() - timedelta(days=60)
        )

        deleted = cleanup_old_notifications(days=30)
        self.assertEqual(deleted, 1)

    def test_cleanup_keeps_unread_notifications(self):
        """cleanup_old_notifications giữ notifications chưa đọc"""
        old_unread = UserNotification.objects.create(
            recipient=self.user, title='Old Unread', message='msg',
            is_read=False
        )
        UserNotification.objects.filter(pk=old_unread.pk).update(
            created_at=timezone.now() - timedelta(days=60)
        )

        cleanup_old_notifications(days=30)
        self.assertTrue(
            UserNotification.objects.filter(pk=old_unread.pk).exists()
        )


class NotificationViewTest(TestCase):
    """Test notification views"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='viewnotifuser', password='pass123'
        )
        self.notification = UserNotification.objects.create(
            recipient=self.user, title='View Test', message='msg'
        )

    def test_notification_list_requires_login(self):
        """Trang danh sách notifications yêu cầu login"""
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, 302)

    def test_notification_list_accessible_when_logged_in(self):
        """Trang danh sách notifications trả về 200 khi đã login"""
        self.client.login(username='viewnotifuser', password='pass123')
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, 200)

    def test_mark_all_read_requires_login(self):
        """API mark-all-read yêu cầu login"""
        response = self.client.post(reverse('notifications:api_mark_all_read'))
        self.assertEqual(response.status_code, 302)
