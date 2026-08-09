from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from users.models import Profile, UserPreference, UserInterest

class UsersModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', 
            email='testuser@example.com', 
            password='TestPassword123!'
        )
        self.user2 = User.objects.create_user(
            username='testuser2', 
            email='testuser2@example.com', 
            password='TestPassword123!'
        )

    def test_profile_and_preference_creation_signals(self):
        """Kiểm tra tín hiệu tạo Profile và Preference khi tạo User"""
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertTrue(hasattr(self.user, 'preferences'))
        self.assertEqual(self.user.profile.user.username, 'testuser')
        self.assertEqual(self.user.preferences.theme, 'light')

    def test_user_interest(self):
        """Kiểm tra chức năng tạo sở thích"""
        interest = UserInterest.objects.create(
            user=self.user, 
            interest_type='topic', 
            interest_value='Science',
            weight=8
        )
        self.assertEqual(self.user.interests.count(), 1)
        self.assertEqual(interest.interest_value, 'Science')

class UsersViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser', 
            email='testuser@example.com', 
            password='TestPassword123!'
        )

    def test_login_view_status_code(self):
        """Kiểm tra trang đăng nhập tải thành công"""
        response = self.client.get(reverse('users:login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/login.html')

    def test_register_view_status_code(self):
        """Kiểm tra trang đăng ký tải thành công"""
        response = self.client.get(reverse('users:register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/register.html')

    def test_user_login(self):
        """Kiểm tra xử lý đăng nhập thành công"""
        response = self.client.post(reverse('users:login'), {
            'username': 'testuser',
            'password': 'TestPassword123!'
        })
        # Đăng nhập thành công sẽ redirect về dashboard
        self.assertRedirects(response, reverse('users:dashboard'))

    def test_profile_view_unauthenticated(self):
        """Kiểm tra trang profile redirect nếu chưa đăng nhập"""
        response = self.client.get(reverse('users:profile'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('users:login')))

    def test_profile_view_authenticated(self):
        """Kiểm tra trang profile truy cập được khi đã đăng nhập"""
        self.client.login(username='testuser', password='TestPassword123!')
        response = self.client.get(reverse('users:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/profile.html')
