import threading
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from inventory.models import Book, Category, LibraryBus
from transactions.models import BorrowRecord, BookReservation, FinePayment
from transactions.services import TransactionService
from django.core.exceptions import ValidationError

User = get_user_model()

class TransactionServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.category = Category.objects.create(name='Test Category')
        self.bus = LibraryBus.objects.create(name='Test Bus', license_plate='1234')
        self.book1 = Book.objects.create(
            title='Book 1', author='Author 1', publication_year=2020, 
            page_count=100, category=self.category, location=self.bus, status='available'
        )
        self.book2 = Book.objects.create(
            title='Book 2', author='Author 2', publication_year=2020, 
            page_count=100, category=self.category, location=self.bus, status='available'
        )

    def test_create_borrow_success(self):
        borrow = TransactionService.create_borrow(self.user, self.book1)
        self.assertIsNotNone(borrow)
        self.assertEqual(borrow.user, self.user)
        self.assertEqual(borrow.book, self.book1)
        
        # Sách phải chuyển sang trạng thái checked_out
        self.book1.refresh_from_db()
        self.assertEqual(self.book1.status, 'checked_out')

    def test_create_borrow_unavailable_book(self):
        self.book1.status = 'checked_out'
        self.book1.save()
        
        with self.assertRaises(ValidationError):
            TransactionService.create_borrow(self.user, self.book1)

    def test_return_book_on_time(self):
        borrow = TransactionService.create_borrow(self.user, self.book1)
        # Act
        returned_borrow = TransactionService.return_book(borrow.id)
        
        self.assertIsNotNone(returned_borrow.return_date)
        self.book1.refresh_from_db()
        self.assertEqual(self.book1.status, 'available')
        
        # Không có tiền phạt
        fines = FinePayment.objects.filter(borrow_record=returned_borrow)
        self.assertEqual(fines.count(), 0)

    def test_return_book_overdue_fine(self):
        borrow = TransactionService.create_borrow(self.user, self.book1)
        # Giả lập sách quá hạn 10 ngày
        borrow.due_date = timezone.now().date() - timedelta(days=10)
        borrow.save()
        
        # Act
        returned_borrow = TransactionService.return_book(borrow.id)
        
        # 10 ngày quá hạn: 7 ngày đầu * 5000 + 3 ngày sau * 10000 = 35000 + 30000 = 65000
        fine = FinePayment.objects.get(borrow_record=returned_borrow)
        self.assertEqual(fine.final_amount, Decimal('65000.00'))

    def test_reservation_queue_ordering(self):
        user2 = User.objects.create_user(username='user2', password='password')
        user3 = User.objects.create_user(username='user3', password='password')
        
        # Make book unavailable
        self.book1.status = 'checked_out'
        self.book1.save()
        
        res1 = TransactionService.create_reservation(self.user, self.book1)
        res2 = TransactionService.create_reservation(user2, self.book1)
        res3 = TransactionService.create_reservation(user3, self.book1)
        
        self.assertEqual(res1.queue_position, 1)
        self.assertEqual(res2.queue_position, 2)
        self.assertEqual(res3.queue_position, 3)
        
        # Hủy res2
        TransactionService.cancel_reservation(res2.id)
        
        res3.refresh_from_db()
        self.assertEqual(res3.queue_position, 2)
