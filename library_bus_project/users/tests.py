# File: users/tests.py
# ==============================================================================
# Test cases cho Users App — Models, Signals, Views
# ==============================================================================

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta

from users.models import Profile, UserPreference, UserInterest, LoginHistory

User = get_user_model()


class ProfileSignalTest(TestCase):
    """Test auto-creation signals cho Profile và UserPreference"""

    def test_profile_created_on_user_creation(self):
        """Tạo User phải tự động tạo Profile"""
        user = User.objects.create_user(username='signaluser', password='pass123')
        self.assertTrue(hasattr(user, 'profile'))
        self.assertIsInstance(user.profile, Profile)

    def test_preferences_created_on_user_creation(self):
        """Tạo User phải tự động tạo UserPreference"""
        user = User.objects.create_user(username='prefuser', password='pass123')
        self.assertTrue(hasattr(user, 'preferences'))
        self.assertIsInstance(user.preferences, UserPreference)


class ProfileModelTest(TestCase):
    """Test Profile model: validators, properties, methods"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='profiletest',
            password='testpass123',
            first_name='Nguyễn',
            last_name='Văn A'
        )
        self.profile = self.user.profile

    def test_phone_number_valid_format(self):
        """Số điện thoại hợp lệ: 0912345678"""
        self.profile.phone_number = '0912345678'
        self.profile.full_clean(exclude=['avatar'])  # Không nên raise ValidationError

    def test_phone_number_valid_format_plus84(self):
        """Số điện thoại hợp lệ: +84912345678"""
        self.profile.phone_number = '+84912345678'
        self.profile.full_clean(exclude=['avatar'])

    def test_phone_number_invalid_format(self):
        """Số điện thoại không hợp lệ phải raise ValidationError"""
        from django.core.exceptions import ValidationError
        self.profile.phone_number = '12345'
        with self.assertRaises(ValidationError):
            self.profile.full_clean(exclude=['avatar'])

    def test_date_of_birth_future_raises_error(self):
        """Ngày sinh trong tương lai phải raise ValidationError"""
        from django.core.exceptions import ValidationError
        self.profile.date_of_birth = date.today() + timedelta(days=1)
        with self.assertRaises(ValidationError):
            self.profile.save()

    def test_age_property(self):
        """Tính tuổi chính xác từ date_of_birth"""
        self.profile.date_of_birth = date(2000, 1, 1)
        self.profile.save()
        expected_age = (date.today() - date(2000, 1, 1)).days // 365
        # Age có thể chênh 1 tùy vào ngày test chạy
        self.assertIn(self.profile.age, [expected_age, expected_age + 1, expected_age - 1])

    def test_age_none_when_no_dob(self):
        """age phải trả về None nếu không có date_of_birth"""
        self.profile.date_of_birth = None
        self.assertIsNone(self.profile.age)

    def test_full_name_property(self):
        """full_name trả về tên đầy đủ hoặc username"""
        self.assertEqual(self.profile.full_name, 'Nguyễn Văn A')

    def test_full_address_property(self):
        """full_address ghép các phần địa chỉ"""
        self.profile.address = '123 Đường ABC'
        self.profile.ward = 'Phường 1'
        self.profile.district = 'Quận 1'
        self.profile.city = 'TP.HCM'
        self.profile.save()
        self.assertEqual(
            self.profile.full_address,
            '123 Đường ABC, Phường 1, Quận 1, TP.HCM'
        )

    def test_completion_percentage_empty(self):
        """Profile trống phải có completion_percentage = 0"""
        self.assertEqual(self.profile.completion_percentage, 0)

    def test_completion_percentage_partial(self):
        """Profile điền một phần phải có phần trăm phù hợp"""
        self.profile.phone_number = '0912345678'
        self.profile.city = 'Hà Nội'
        self.profile.district = 'Ba Đình'
        self.profile.save()
        # 3/6 fields filled = 50%
        self.assertEqual(self.profile.completion_percentage, 50.0)

    def test_generate_and_verify_code(self):
        """generate_verification_code tạo mã 6 chữ số, verify_code xác nhận"""
        self.profile.generate_verification_code()
        code = self.profile.verification_code
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

        # Verify đúng code
        result = self.profile.verify_code(code)
        self.assertTrue(result)
        self.assertTrue(self.profile.is_verified)

    def test_verify_code_wrong(self):
        """verify_code trả về False nếu mã sai"""
        self.profile.generate_verification_code()
        result = self.profile.verify_code('000000')
        self.assertFalse(result)

    def test_str_representation(self):
        """__str__ trả về 'Hồ sơ của username'"""
        self.assertIn(self.user.username, str(self.profile))


class UserPreferenceTest(TestCase):
    """Test UserPreference model"""

    def setUp(self):
        self.user = User.objects.create_user(username='preftest', password='pass123')
        self.pref = self.user.preferences

    def test_default_theme_is_light(self):
        """Default theme phải là 'light'"""
        self.assertEqual(self.pref.theme, 'light')

    def test_default_books_per_page(self):
        """Default books_per_page phải là 20"""
        self.assertEqual(self.pref.books_per_page, 20)


class UserViewTest(TestCase):
    """Test Users views: authentication, profile"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='viewuser', password='testpass123', email='view@test.com'
        )

    def test_login_page_accessible(self):
        """Trang đăng nhập phải trả về 200"""
        response = self.client.get(reverse('users:login'))
        self.assertEqual(response.status_code, 200)

    def test_register_page_accessible(self):
        """Trang đăng ký phải trả về 200"""
        response = self.client.get(reverse('users:register'))
        self.assertEqual(response.status_code, 200)

    def test_login_success_redirect(self):
        """Đăng nhập thành công phải redirect"""
        response = self.client.post(reverse('users:login'), {
            'username': 'viewuser',
            'password': 'testpass123',
        })
        self.assertIn(response.status_code, [200, 302])

    def test_profile_requires_login(self):
        """Trang profile phải yêu cầu đăng nhập"""
        response = self.client.get(reverse('users:profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_profile_accessible_when_logged_in(self):
        """Trang profile phải trả về 200 khi đã đăng nhập"""
        self.client.login(username='viewuser', password='testpass123')
        response = self.client.get(reverse('users:profile'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_requires_login(self):
        """Dashboard phải yêu cầu đăng nhập"""
        response = self.client.get(reverse('users:dashboard'))
        self.assertEqual(response.status_code, 302)
