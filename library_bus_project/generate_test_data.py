import os
import sys
import django
import random
import datetime
from faker import Faker

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_bus_project.settings')
django.setup()

from django.contrib.auth.models import User
from inventory.models import Book
from transactions.models import BorrowRecord, BookReservation
from django.utils import timezone

fake = Faker('vi_VN')

def create_seed_data():
    print("Starting data generation...")
    
    users = []
    print("Creating 50 accounts...")
    for i in range(50):
        # Tạo username unique
        username = fake.user_name() + str(random.randint(10000, 99999))
        email = fake.email()
        try:
            user = User.objects.create_user(username=username, email=email, password='password123')
            user.first_name = fake.first_name()
            user.last_name = fake.last_name()
            user.save()
            users.append(user)
        except Exception as e:
            print(f"Error creating user {username}: {e}")
            
    print(f"Created {len(users)} new users.")

    books = list(Book.objects.all())
    if not books:
        print("Error: No books in the database to create requests!")
        return

    print("Generating 200 random requests (Borrow / Reservation)...")
    requests_created = 0
    
    # Cố gắng lặp nhiều hơn 200 để bù đắp các case bị lỗi do unique constraints
    for _ in range(400):
        if requests_created >= 200:
            break
            
        user = random.choice(users)
        book = random.choice(books)
        request_type = random.choice(['borrow', 'reservation'])
        
        try:
            if request_type == 'borrow':
                # Kiểm tra constraint: một người không mượn cùng 1 quyển sách đang active
                if not BorrowRecord.objects.filter(user=user, book=book, return_date__isnull=True).exists():
                    due_date = timezone.now().date() + datetime.timedelta(days=random.randint(7, 30))
                    # 20% khả năng bị overdue (quá hạn) để test
                    if random.random() < 0.2:
                        due_date = timezone.now().date() - datetime.timedelta(days=random.randint(1, 10))
                        
                    BorrowRecord.objects.create(
                        user=user,
                        book=book,
                        due_date=due_date
                    )
                    requests_created += 1
            else:
                # Kiểm tra constraint: active reservation
                if not BookReservation.objects.filter(user=user, book=book, is_fulfilled=False).exists():
                    BookReservation.objects.create(
                        user=user,
                        book=book
                    )
                    requests_created += 1
        except Exception as e:
            # Bỏ qua nếu có lỗi constraint
            pass
            
    print(f"Successfully created {requests_created} requests.")
    print("Data generation process completed!")

if __name__ == '__main__':
    create_seed_data()
