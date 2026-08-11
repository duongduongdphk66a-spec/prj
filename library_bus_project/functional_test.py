import os
import sys
import django

# Fix encoding
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_bus_project.settings')
django.setup()

from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')

from django.test import Client
from django.contrib.auth import get_user_model
from inventory.models import Book, LibraryBus
from blog.models import Post
from django.urls import reverse

User = get_user_model()
client = Client()

def report(status, step_name, detail=""):
    color = "\033[92m" if status == "PASS" else "\033[91m"
    reset = "\033[0m"
    print(f"[{color}{status}{reset}] {step_name} {('- ' + detail) if detail else ''}")

def test_public_pages():
    print("\n--- Testing Public Pages ---")
    pages = [
        ('Trang chủ', '/'),
        ('Giới thiệu', '/about/'),
        ('Liên hệ', '/contact/'),
    ]
    for name, url in pages:
        response = client.get(url)
        if response.status_code == 200:
            report("PASS", f"Truy cập {name} ({url})")
        else:
            report("FAIL", f"Truy cập {name} ({url})", f"Status code: {response.status_code}")

def test_auth():
    print("\n--- Testing Authentication ---")
    # Đảm bảo có user 'admin'/'admin'
    admin_user, created = User.objects.get_or_create(username='admin', defaults={'email': 'admin@example.com'})
    admin_user.set_password('admin')
    admin_user.is_superuser = True
    admin_user.is_staff = True
    admin_user.save()
        
    response = client.get(reverse('users:login'))
    if response.status_code == 200:
        report("PASS", "Truy cập trang Đăng nhập")
    else:
        report("FAIL", "Truy cập trang Đăng nhập", f"Status code: {response.status_code}")

    login_success = client.login(username='admin', password='admin')
    if login_success:
        report("PASS", "Đăng nhập thành công với tài khoản admin")
    else:
        report("FAIL", "Đăng nhập thất bại")

def test_inventory():
    print("\n--- Testing Inventory ---")
    response = client.get(reverse('inventory:book_list'))
    if response.status_code == 200:
        report("PASS", "Truy cập danh sách sách")
    else:
        report("FAIL", "Truy cập danh sách sách", f"Status code: {response.status_code}")
        
    # Tạo dữ liệu test nếu chưa có
    book = Book.objects.first()
    if not book:
        book = Book.objects.create(title="Sách test E2E", author="Tác giả test", page_count=100)
    
    response = client.get(reverse('inventory:book_detail', kwargs={'pk': book.pk}))
    if response.status_code == 200:
        report("PASS", f"Truy cập chi tiết sách '{book.title}'")
    else:
        report("FAIL", f"Truy cập chi tiết sách '{book.title}'", f"Status code: {response.status_code}")

def test_buses():
    print("\n--- Testing Library Buses ---")
    response = client.get(reverse('inventory:bus_list'))
    if response.status_code == 200:
        report("PASS", "Truy cập danh sách xe bus")
    else:
        report("FAIL", "Truy cập danh sách xe bus", f"Status code: {response.status_code}")
        
    bus = LibraryBus.objects.first()
    if not bus:
        bus = LibraryBus.objects.create(name="Bus test E2E", license_plate="29A-99999")
        
    response = client.get(reverse('inventory:bus_detail', kwargs={'pk': bus.pk}))
    if response.status_code == 200:
        report("PASS", f"Truy cập chi tiết xe bus '{bus.name}'")
    else:
        report("FAIL", f"Truy cập chi tiết xe bus '{bus.name}'", f"Status code: {response.status_code}")

def test_blog():
    print("\n--- Testing Blog ---")
    response = client.get(reverse('blog:post_list'))
    if response.status_code == 200:
        report("PASS", "Truy cập danh sách bài viết blog")
    else:
        report("FAIL", "Truy cập danh sách bài viết blog", f"Status code: {response.status_code}")
        
    post = Post.objects.filter(status='published').first()
    if not post:
        author = User.objects.first()
        post = Post.objects.create(title="Bài test E2E", content="Nội dung test", author=author, status='published')
        
    response = client.get(reverse('blog:post_detail', kwargs={'slug': post.slug}))
    if response.status_code == 200:
        report("PASS", f"Truy cập chi tiết bài blog '{post.title}'")
    else:
        report("FAIL", f"Truy cập chi tiết bài blog '{post.title}'", f"Status code: {response.status_code}")

def test_admin():
    print("\n--- Testing Admin Panel ---")
    client.login(username='admin', password='admin')
    response = client.get('/admin/')
    # Dashboard admin trong Django trả về 200 nếu login thành công, 302 nếu chưa
    if response.status_code == 200:
        report("PASS", "Truy cập trang Admin Dashboard")
    else:
        report("FAIL", "Truy cập trang Admin Dashboard", f"Status code: {response.status_code}")

def run_all_tests():
    try:
        test_public_pages()
        test_auth()
        test_inventory()
        test_buses()
        test_blog()
        test_admin()
        print("\n\033[92m[DONE]\033[0m Hoàn tất kịch bản kiểm thử mô phỏng.")
    except Exception as e:
        print(f"\n\033[91m[ERROR]\033[0m Quá trình kiểm thử bị gián đoạn do lỗi: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    run_all_tests()
