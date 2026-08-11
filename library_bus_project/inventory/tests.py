from django.test import TestCase
from inventory.models import Book, Category, LibraryBus

class InventoryModelTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Khoa Học')
        self.bus = LibraryBus.objects.create(name='Bus 1', license_plate='29A-12345', capacity=100)
        
    def test_bus_book_count_and_capacity(self):
        # Ban đầu xe bus trống
        self.assertEqual(self.bus.current_book_count, 0)
        self.assertEqual(self.bus.capacity_usage_percentage, 0)
        
        # Thêm sách vào xe bus
        book1 = Book.objects.create(
            title='Sách 1', author='Tác giả 1', publication_year=2021, 
            page_count=200, category=self.category, location=self.bus, status='available'
        )
        
        # Refresh cache (vì property sử dụng cache)
        self.bus.invalidate_cache()
        self.assertEqual(self.bus.current_book_count, 1)
        self.assertEqual(self.bus.capacity_usage_percentage, 1.0)
        
        # Thêm sách thứ 2 nhưng bị hỏng (status != available)
        book2 = Book.objects.create(
            title='Sách 2', author='Tác giả 2', publication_year=2021, 
            page_count=200, category=self.category, location=self.bus, status='maintenance'
        )
        self.bus.invalidate_cache()
        
        # Chỉ đếm sách available
        self.assertEqual(self.bus.current_book_count, 1)
        
    def test_book_change_status_history(self):
        book = Book.objects.create(
            title='Sách 3', author='Tác giả 3', publication_year=2021, 
            page_count=200, category=self.category, location=self.bus, status='available'
        )
        
        book.change_status('checked_out')
        
        self.assertEqual(book.status, 'checked_out')
        self.assertEqual(book.status_history.count(), 1)
        history = book.status_history.first()
        self.assertEqual(history.from_status, 'available')
        self.assertEqual(history.to_status, 'checked_out')
