import os
import sys
import threading
import django

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_bus_project.settings')
django.setup()

from django.contrib.auth import get_user_model
from inventory.models import Book, Category, LibraryBus
from transactions.models import BookReservation
from transactions.services import TransactionService
from django.db import connection

User = get_user_model()

def test_reservation_race_condition():
    # Setup data
    category, _ = Category.objects.get_or_create(name='Tech')
    bus, _ = LibraryBus.objects.get_or_create(name='Bus', license_plate='1234')
    book, _ = Book.objects.get_or_create(title='Race Condition Book', defaults={
        'author': 'Tester', 'publication_year': 2021, 'page_count': 100, 
        'category': category, 'location': bus, 'status': 'checked_out'
    })
    
    # Xóa các reservation cũ
    BookReservation.objects.filter(book=book).delete()
    
    # Tạo 5 users
    users = []
    for i in range(5):
        user, _ = User.objects.get_or_create(username=f'rc_user_{i}', defaults={'email': f'u{i}@test.com'})
        users.append(user)

    def make_reservation(user, book):
        try:
            TransactionService.create_reservation(user, book)
        except Exception as e:
            print(f"Error for {user.username}: {e}")
        finally:
            connection.close()

    threads = []
    print("Bắt đầu thử đặt trước 1 user...")
    make_reservation(users[0], book)
    
    print("Bắt đầu giả lập 5 luồng đặt trước cùng lúc...")
    for user in users:
        t = threading.Thread(target=make_reservation, args=(user, book))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()

    # Kiểm tra kết quả queue_position
    reservations = BookReservation.objects.filter(book=book).order_by('queue_position')
    print("Kết quả queue_position:")
    positions = []
    for res in reservations:
        print(f"- {res.user.username}: Vị trí {res.queue_position}")
        positions.append(res.queue_position)
        
    if len(positions) != len(set(positions)):
        print("\n\033[91m[PHÁT HIỆN LỖI]\033[0m Có Race Condition! Các vị trí bị trùng lặp.")
    else:
        print("\n\033[92m[PASS]\033[0m Không phát hiện trùng lặp vị trí.")

if __name__ == '__main__':
    test_reservation_race_condition()
