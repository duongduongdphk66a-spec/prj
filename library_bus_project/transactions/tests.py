# File: transactions/tests.py
# ==============================================================================
# Test cases cho Transactions App — Models, Services, Views
# ==============================================================================

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.cache import cache
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from inventory.models import Book, Category, LibraryBus
from transactions.models import (
    BorrowRecord, BookReservation, FinePayment,
    ShippingRequest, BulkTransaction
)
from transactions.services import TransactionService, ReportService

User = get_user_model()


class BorrowRecordModelTest(TestCase):
    """Test BorrowRecord model properties"""

    def setUp(self):
        self.user = User.objects.create_user(username='borrowuser', password='pass123')
        self.category = Category.objects.create(name='Borrow Cat')
        self.bus = LibraryBus.objects.create(
            name='Borrow Bus', license_plate='29A-BRRW', capacity=100
        )
        self.book = Book.objects.create(
            title='Borrow Book', author='Author', publication_year=2023,
            page_count=200, category=self.category, location=self.bus,
            status='available'
        )

    def test_is_overdue_false_when_not_due(self):
        """is_overdue phải trả về False khi chưa quá hạn"""
        borrow = BorrowRecord.objects.create(
            user=self.user, book=self.book,
            due_date=timezone.now().date() + timedelta(days=7)
        )
        self.assertFalse(borrow.is_overdue)

    def test_is_overdue_true_when_past_due(self):
        """is_overdue phải trả về True khi đã quá hạn"""
        borrow = BorrowRecord.objects.create(
            user=self.user, book=self.book,
            due_date=timezone.now().date() - timedelta(days=5)
        )
        self.assertTrue(borrow.is_overdue)

    def test_is_overdue_false_when_returned(self):
        """is_overdue phải trả về False khi đã trả sách"""
        borrow = BorrowRecord.objects.create(
            user=self.user, book=self.book,
            due_date=timezone.now().date() - timedelta(days=5),
            return_date=timezone.now().date()
        )
        self.assertFalse(borrow.is_overdue)

    def test_days_overdue_calculation(self):
        """days_overdue phải tính đúng số ngày quá hạn"""
        borrow = BorrowRecord.objects.create(
            user=self.user, book=self.book,
            due_date=timezone.now().date() - timedelta(days=10)
        )
        self.assertEqual(borrow.days_overdue, 10)

    def test_days_overdue_zero_when_not_overdue(self):
        """days_overdue = 0 khi chưa quá hạn"""
        borrow = BorrowRecord.objects.create(
            user=self.user, book=self.book,
            due_date=timezone.now().date() + timedelta(days=7)
        )
        self.assertEqual(borrow.days_overdue, 0)

    def test_str_representation(self):
        """__str__ phải chứa username và book title"""
        borrow = BorrowRecord.objects.create(
            user=self.user, book=self.book,
            due_date=timezone.now().date() + timedelta(days=14)
        )
        result = str(borrow)
        self.assertIn(self.user.username, result)
        self.assertIn(self.book.title, result)


class BookReservationModelTest(TestCase):
    """Test BookReservation model"""

    def setUp(self):
        self.user = User.objects.create_user(username='resuser', password='pass123')
        self.user2 = User.objects.create_user(username='resuser2', password='pass123')
        self.category = Category.objects.create(name='Res Cat')
        self.bus = LibraryBus.objects.create(
            name='Res Bus', license_plate='29A-RESV', capacity=100
        )
        self.book = Book.objects.create(
            title='Res Book', author='Author', publication_year=2023,
            page_count=200, category=self.category, location=self.bus,
            status='checked_out'
        )

    def test_auto_expires_date(self):
        """Reservation phải tự set expires_date nếu không cung cấp"""
        res = BookReservation.objects.create(
            user=self.user, book=self.book
        )
        self.assertIsNotNone(res.expires_date)

    def test_auto_queue_position(self):
        """Queue position phải tự động tăng"""
        res1 = BookReservation.objects.create(user=self.user, book=self.book)
        res2 = BookReservation.objects.create(user=self.user2, book=self.book)
        self.assertEqual(res1.queue_position, 1)
        self.assertEqual(res2.queue_position, 2)

    def test_fulfill_updates_fields(self):
        """fulfill() phải set is_fulfilled và fulfilled_date"""
        res = BookReservation.objects.create(user=self.user, book=self.book)
        res.fulfill()
        res.refresh_from_db()
        self.assertTrue(res.is_fulfilled)
        self.assertIsNotNone(res.fulfilled_date)


class FinePaymentModelTest(TestCase):
    """Test FinePayment model"""

    def setUp(self):
        self.user = User.objects.create_user(username='fineuser', password='pass123')
        self.category = Category.objects.create(name='Fine Cat')
        self.bus = LibraryBus.objects.create(
            name='Fine Bus', license_plate='29A-FINE', capacity=100
        )
        self.book = Book.objects.create(
            title='Fine Book', author='Author', publication_year=2023,
            page_count=200, category=self.category, location=self.bus,
            status='available'
        )
        self.borrow = BorrowRecord.objects.create(
            user=self.user, book=self.book,
            due_date=timezone.now().date() + timedelta(days=14)
        )

    def test_auto_calculate_final_amount(self):
        """save() phải tự tính final_amount = amount - discount"""
        payment = FinePayment.objects.create(
            borrow_record=self.borrow,
            amount=Decimal('50000'),
            discount_amount=Decimal('10000')
        )
        self.assertEqual(payment.final_amount, Decimal('40000'))

    def test_apply_discount(self):
        """apply_discount phải cập nhật discount_amount đúng"""
        payment = FinePayment.objects.create(
            borrow_record=self.borrow,
            amount=Decimal('100000')
        )
        payment.apply_discount(20)  # 20%
        payment.refresh_from_db()
        self.assertEqual(payment.discount_amount, Decimal('20000'))
        self.assertEqual(payment.final_amount, Decimal('80000'))


class TransactionServiceCreateBorrowTest(TestCase):
    """Test TransactionService.create_borrow"""

    def setUp(self):
        self.user = User.objects.create_user(username='svcuser', password='pass123')
        self.category = Category.objects.create(name='Svc Cat')
        self.bus = LibraryBus.objects.create(
            name='Svc Bus', license_plate='29A-SVCE', capacity=100
        )
        self.book = Book.objects.create(
            title='Svc Book', author='Author', publication_year=2023,
            page_count=200, category=self.category, location=self.bus,
            status='available'
        )

    def test_create_borrow_success(self):
        """Mượn sách thành công"""
        borrow = TransactionService.create_borrow(self.user, self.book)
        self.assertIsNotNone(borrow)
        self.assertEqual(borrow.user, self.user)
        self.assertEqual(borrow.book, self.book)
        self.book.refresh_from_db()
        self.assertEqual(self.book.status, 'checked_out')

    def test_create_borrow_unavailable_book_raises(self):
        """Mượn sách không available phải raise ValidationError"""
        self.book.status = 'checked_out'
        self.book.save()
        with self.assertRaises(ValidationError):
            TransactionService.create_borrow(self.user, self.book)

    def test_create_borrow_sets_due_date(self):
        """Borrow phải có due_date đúng (default 14 ngày)"""
        borrow = TransactionService.create_borrow(self.user, self.book)
        expected_due = timezone.now().date() + timedelta(days=14)
        self.assertEqual(borrow.due_date, expected_due)

    def test_create_borrow_custom_due_days(self):
        """Borrow với due_days custom"""
        borrow = TransactionService.create_borrow(self.user, self.book, due_days=7)
        expected_due = timezone.now().date() + timedelta(days=7)
        self.assertEqual(borrow.due_date, expected_due)


class TransactionServiceReturnBookTest(TestCase):
    """Test TransactionService.return_book"""

    def setUp(self):
        self.user = User.objects.create_user(username='retuser', password='pass123')
        self.category = Category.objects.create(name='Ret Cat')
        self.bus = LibraryBus.objects.create(
            name='Ret Bus', license_plate='29A-RETN', capacity=100
        )
        self.book = Book.objects.create(
            title='Return Book', author='Author', publication_year=2023,
            page_count=200, category=self.category, location=self.bus,
            status='available'
        )

    def test_return_book_on_time_no_fine(self):
        """Trả sách đúng hạn không có phạt"""
        borrow = TransactionService.create_borrow(self.user, self.book)
        returned = TransactionService.return_book(borrow.id)
        self.assertIsNotNone(returned.return_date)
        self.book.refresh_from_db()
        self.assertEqual(self.book.status, 'available')
        fines = FinePayment.objects.filter(borrow_record=returned)
        self.assertEqual(fines.count(), 0)

    def test_return_book_overdue_creates_fine(self):
        """Trả sách quá hạn phải tạo fine payment"""
        borrow = TransactionService.create_borrow(self.user, self.book)
        borrow.due_date = timezone.now().date() - timedelta(days=10)
        borrow.save()

        returned = TransactionService.return_book(borrow.id)
        fine = FinePayment.objects.get(borrow_record=returned)
        # 7 ngày đầu × 5000 + 3 ngày sau × 10000 = 35000 + 30000 = 65000
        self.assertEqual(fine.final_amount, Decimal('65000.00'))

    def test_return_already_returned_raises(self):
        """Trả sách đã trả rồi phải raise ValidationError"""
        borrow = TransactionService.create_borrow(self.user, self.book)
        TransactionService.return_book(borrow.id)
        with self.assertRaises(ValidationError):
            TransactionService.return_book(borrow.id)


class TransactionServiceFineCalculationTest(TestCase):
    """Test TransactionService.calculate_fine — progressive tiers"""

    def setUp(self):
        self.user = User.objects.create_user(username='fineuser2', password='pass123')
        self.category = Category.objects.create(name='Fine Cat 2')
        self.bus = LibraryBus.objects.create(
            name='Fine Bus 2', license_plate='29A-FIN2', capacity=100
        )
        self.book = Book.objects.create(
            title='Fine Book 2', author='Author', publication_year=2023,
            page_count=200, category=self.category, location=self.bus,
            status='available'
        )

    def test_fine_not_overdue_zero(self):
        """Sách chưa quá hạn: fine = 0"""
        borrow = BorrowRecord.objects.create(
            user=self.user, book=self.book,
            due_date=timezone.now().date() + timedelta(days=7)
        )
        fine = TransactionService.calculate_fine(borrow)
        self.assertEqual(fine, Decimal('0'))

    def test_fine_tier1_within_7_days(self):
        """Quá hạn 5 ngày: 5 × 5000 = 25000"""
        borrow = BorrowRecord.objects.create(
            user=self.user, book=self.book,
            due_date=timezone.now().date() - timedelta(days=5)
        )
        fine = TransactionService.calculate_fine(borrow)
        self.assertEqual(fine, Decimal('25000'))

    def test_fine_tier2_8_to_30_days(self):
        """Quá hạn 10 ngày: 7×5000 + 3×10000 = 65000"""
        borrow = BorrowRecord.objects.create(
            user=self.user, book=self.book,
            due_date=timezone.now().date() - timedelta(days=10)
        )
        fine = TransactionService.calculate_fine(borrow)
        self.assertEqual(fine, Decimal('65000'))

    def test_fine_tier3_over_30_days(self):
        """Quá hạn 35 ngày: 7×5000 + 23×10000 + 5×15000 = 35000+230000+75000 = 340000"""
        borrow = BorrowRecord.objects.create(
            user=self.user, book=self.book,
            due_date=timezone.now().date() - timedelta(days=35)
        )
        fine = TransactionService.calculate_fine(borrow)
        self.assertEqual(fine, Decimal('340000'))


class TransactionServiceReservationTest(TestCase):
    """Test TransactionService reservation operations"""

    def setUp(self):
        self.user = User.objects.create_user(username='resuser3', password='pass123')
        self.user2 = User.objects.create_user(username='resuser4', password='pass123')
        self.user3 = User.objects.create_user(username='resuser5', password='pass123')
        self.category = Category.objects.create(name='Res Cat 2')
        self.bus = LibraryBus.objects.create(
            name='Res Bus 2', license_plate='29A-RES2', capacity=100
        )
        self.book = Book.objects.create(
            title='Res Book 2', author='Author', publication_year=2023,
            page_count=200, category=self.category, location=self.bus,
            status='checked_out'
        )

    def test_create_reservation_success(self):
        """Đặt trước sách đang checked_out thành công"""
        res = TransactionService.create_reservation(self.user, self.book)
        self.assertIsNotNone(res)
        self.assertEqual(res.queue_position, 1)

    def test_create_reservation_available_book_raises(self):
        """Đặt trước sách đang available phải raise ValidationError"""
        self.book.status = 'available'
        self.book.save()
        with self.assertRaises(ValidationError):
            TransactionService.create_reservation(self.user, self.book)

    def test_create_reservation_duplicate_raises(self):
        """Đặt trước trùng lặp phải raise ValidationError"""
        TransactionService.create_reservation(self.user, self.book)
        with self.assertRaises(ValidationError):
            TransactionService.create_reservation(self.user, self.book)

    def test_cancel_reservation_reorders_queue(self):
        """Hủy reservation phải sắp xếp lại queue"""
        res1 = TransactionService.create_reservation(self.user, self.book)
        res2 = TransactionService.create_reservation(self.user2, self.book)
        res3 = TransactionService.create_reservation(self.user3, self.book)

        TransactionService.cancel_reservation(res2.id)

        res3.refresh_from_db()
        self.assertEqual(res3.queue_position, 2)


class TransactionServiceBulkTest(TestCase):
    """Test TransactionService bulk operations"""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='bulkadmin', password='pass123', is_staff=True
        )
        self.category = Category.objects.create(name='Bulk Cat')
        self.bus = LibraryBus.objects.create(
            name='Bulk Bus', license_plate='29A-BULK', capacity=100
        )

    def test_bulk_return_success_count(self):
        """bulk_return_books phải trả về số lượng success/fail đúng"""
        books = []
        borrows = []
        for i in range(3):
            book = Book.objects.create(
                title=f'Bulk Book {i}', author='Author',
                publication_year=2023, page_count=200,
                category=self.category, location=self.bus,
                status='available'
            )
            borrow = TransactionService.create_borrow(self.admin, book)
            books.append(book)
            borrows.append(borrow)

        ids = [b.id for b in borrows]
        result = TransactionService.bulk_return_books(ids, self.admin)
        self.assertEqual(result['success'], 3)
        self.assertEqual(result['failed'], 0)


class ReportServiceTest(TestCase):
    """Test ReportService"""

    def setUp(self):
        self.user = User.objects.create_user(username='rptuser', password='pass123')
        self.category = Category.objects.create(name='Rpt Cat')
        self.bus = LibraryBus.objects.create(
            name='Rpt Bus', license_plate='29A-REPT', capacity=100
        )
        self.book = Book.objects.create(
            title='Rpt Book', author='Author', publication_year=2023,
            page_count=200, category=self.category, location=self.bus,
            status='available'
        )

    def test_get_user_statistics(self):
        """get_user_statistics phải trả về dict với các keys đúng"""
        TransactionService.create_borrow(self.user, self.book)
        stats = ReportService.get_user_statistics(self.user)
        self.assertIn('active_borrows', stats)
        self.assertIn('total_borrows', stats)
        self.assertEqual(stats['active_borrows'], 1)

    def test_get_book_statistics(self):
        """get_book_statistics phải trả về dict với các keys đúng"""
        stats = ReportService.get_book_statistics(self.book)
        self.assertIn('book', stats)
        self.assertIn('total_borrows', stats)
        self.assertEqual(stats['book'], self.book.title)


class TransactionViewTest(TestCase):
    """Test transaction views"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='txviewuser', password='pass123'
        )

    def test_borrow_list_requires_login(self):
        """Trang danh sách mượn yêu cầu login"""
        response = self.client.get(reverse('transactions:borrow_list'))
        self.assertEqual(response.status_code, 302)

    def test_borrow_list_accessible_when_logged_in(self):
        """Trang danh sách mượn trả về 200 khi đã login"""
        self.client.login(username='txviewuser', password='pass123')
        response = self.client.get(reverse('transactions:borrow_list'))
        self.assertEqual(response.status_code, 200)

    def test_reservation_list_requires_login(self):
        """Trang danh sách đặt trước yêu cầu login"""
        response = self.client.get(reverse('transactions:reservation_list'))
        self.assertEqual(response.status_code, 302)

    def test_borrow_create_view_post_with_notes(self):
        """Thủ thư submit BorrowCreateView kèm notes phải thành công không bị TypeError"""
        staff = User.objects.create_user(username='staff_test_view', password='pass', is_staff=True)
        borrower = User.objects.create_user(username='borrower_view', password='pass')
        cat = Category.objects.create(name='Cat View')
        bus = LibraryBus.objects.create(name='Bus View', license_plate='29A-VIEW')
        book = Book.objects.create(
            title='Book View', author='Author', publication_year=2024,
            page_count=150, category=cat, location=bus, status='available'
        )

        self.client.login(username='staff_test_view', password='pass')
        response = self.client.post(reverse('transactions:borrow_create'), {
            'user': borrower.id,
            'book': book.id,
            'due_days': 14,
            'pickup_location': bus.id,
            'notes': 'Ghi chú kiểm thử tạo phiếu mượn'
        })
        self.assertEqual(response.status_code, 302)
        borrow = BorrowRecord.objects.get(user=borrower, book=book)
        self.assertEqual(borrow.notes, 'Ghi chú kiểm thử tạo phiếu mượn')
        self.assertEqual(borrow.book.status, 'checked_out')

    def test_email_templates_render_successfully(self):
        """Kiểm tra 4 email template của transactions được render đầy đủ không lỗi TemplateDoesNotExist"""
        from django.template.loader import render_to_string
        cat = Category.objects.create(name='Email Cat')
        bus = LibraryBus.objects.create(name='Email Bus', license_plate='29A-EML')
        book = Book.objects.create(
            title='Email Book', author='Author', publication_year=2024,
            page_count=120, category=cat, location=bus, status='available'
        )
        borrow = BorrowRecord.objects.create(
            user=self.user, book=book, due_date=timezone.now().date() + timedelta(days=7)
        )
        res = BookReservation.objects.create(user=self.user, book=book)
        shipping = ShippingRequest.objects.create(
            user=self.user, book=book, shipping_address='123 Test St',
            phone_number='0987654321', recipient_name='Tester', tracking_code='LBTEST123'
        )

        due_txt = render_to_string('emails/due_reminder.txt', {'record': borrow})
        self.assertIn('Email Book', due_txt)

        overdue_txt = render_to_string('emails/overdue_notification.txt', {'record': borrow})
        self.assertIn('Email Book', overdue_txt)

        avail_txt = render_to_string('emails/book_available.txt', {'reservation': res})
        self.assertIn('Email Book', avail_txt)

        ship_txt = render_to_string('emails/shipping_update.txt', {'shipping': shipping})
        self.assertIn('LBTEST123', ship_txt)

