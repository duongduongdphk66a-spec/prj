from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from inventory.models import Book, Category, LibraryBus

class WebFlowIntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Tạo dữ liệu phụ thuộc
        self.category = Category.objects.create(name="Sách Giáo Khoa", slug="sgk", is_active=True)
        self.bus = LibraryBus.objects.create(
            name="Bus 01", 
            license_plate="29A-12345", 
            capacity=100, 
            operating_status='active'
        )
        
        # Tạo tài khoản admin để thêm sách
        self.admin_user = User.objects.create_superuser(
            email='duongduong.dphk66a@gmail.com',
            username='admin_test',
            password='dddphk66'
        )

    def test_full_web_flow(self):
        # 1. Đăng ký tài khoản mới
        response = self.client.post(reverse('users:register'), {
            'username': 'newuser123',
            'email': 'newuser123@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'password': 'Password123!',
            'password2': 'Password123!',
            'terms_agreed': True
        })
        self.assertIn(response.status_code, [302, 200], "Đăng ký không thành công")
        self.assertTrue(User.objects.filter(username='newuser123').exists())
        
        # 2. Đăng nhập
        response = self.client.post(reverse('users:login'), {
            'username': 'newuser123@example.com',
            'password': 'Password123!'
        })
        self.assertEqual(response.status_code, 302, "Đăng nhập không thành công")
        
        # 3. Thêm sách (cần quyền admin)
        self.client.login(username='admin_test', password='dddphk66')
        
        response = self.client.post(reverse('inventory:book_create'), {
            'title': 'Sách Kiểm Thử 1',
            'author': 'Nguyễn Văn A',
            'publisher': 'NXB Trẻ',
            'publication_year': 2024,
            'page_count': 300,
            'category': self.category.id,
            'location': self.bus.id,
            'condition': 'new',
            'status': 'available',
            'language': 'Tiếng Việt'
        })
        self.assertIn(response.status_code, [302, 200], "Thêm sách không thành công")
        self.assertTrue(Book.objects.filter(title='Sách Kiểm Thử 1').exists())
        book = Book.objects.get(title='Sách Kiểm Thử 1')
        
        # 4. Thay đổi trạng thái sách (Mượn sách)
        response = self.client.post(reverse('inventory:book_status_change', kwargs={'pk': book.id}), {
            'new_status': 'checked_out'
        })
        self.assertIn(response.status_code, [302, 200], "Mượn sách không thành công")
        book.refresh_from_db()
        self.assertEqual(book.status, 'checked_out')
