import os
import sys
import django
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_bus_project.settings')
django.setup()

from inventory.models import LibraryBus, Category, Book

def seed_data():
    # 1. Create Buses
    bus1, _ = LibraryBus.objects.get_or_create(
        name="Bus Sách Trung Tâm",
        license_plate="29A-12345",
        defaults={
            'latitude': 21.028511,
            'longitude': 105.804817,
            'location_name': "Công viên Thống Nhất",
            'operating_status': 'active',
            'capacity': 1000
        }
    )
    bus2, _ = LibraryBus.objects.get_or_create(
        name="Bus Sách Sinh Viên",
        license_plate="29B-67890",
        defaults={
            'latitude': 21.004111,
            'longitude': 105.843694,
            'location_name': "Đại học Bách Khoa",
            'operating_status': 'active',
            'capacity': 800
        }
    )
    buses = [bus1, bus2]

    # 2. Create Categories
    cat_names = ["Văn học", "Khoa học Kỹ thuật", "Kinh tế", "Tâm lý học", "Nghệ thuật", "Lịch sử"]
    categories = []
    for name in cat_names:
        cat, _ = Category.objects.get_or_create(name=name, defaults={'description': f"Sách về {name}"})
        categories.append(cat)
        
    # 3. Create Books
    book_titles = [
        "Đắc Nhân Tâm", "Nhà Giả Kim", "Tội Ác Và Trừng Phạt", "Hai Số Phận", "Lược Sử Loài Người",
        "Tư Duy Nhanh Và Chậm", "Cha Giàu Cha Nghèo", "Nghĩ Giàu Làm Giàu", "Đọc Vị Bất Kỳ Ai", 
        "Lược Sử Thời Gian", "Bản Cực", "Vũ Trụ Của Carl Sagan", "Sự Im Lặng Của Bầy Cừu",
        "Tiếng Chim Hót Trong Bụi Mận Gai", "Cuốn Theo Chiều Gió", "Không Gia Đình", 
        "Hoàng Tử Bé", "Chúa Tể Những Chiếc Nhẫn", "Bắt Trẻ Đồng Xanh", "Mật Mã Da Vinci",
        "Bố Già", "Suối Nguồn", "Một Trăm Năm Cô Đơn", "Ông Già Và Biển Cả", "Kafka Bên Bờ Biển"
    ]
    
    authors = ["Dale Carnegie", "Paulo Coelho", "Fyodor Dostoevsky", "Jeffrey Archer", "Yuval Noah Harari", 
               "Daniel Kahneman", "Robert Kiyosaki", "Napoleon Hill", "David J. Lieberman",
               "Stephen Hawking", "Dan Brown", "Carl Sagan", "Thomas Harris", 
               "Colleen McCullough", "Margaret Mitchell", "Hector Malot", 
               "Antoine de Saint-Exupéry", "J.R.R. Tolkien", "J.D. Salinger", "Dan Brown",
               "Mario Puzo", "Ayn Rand", "Gabriel García Márquez", "Ernest Hemingway", "Haruki Murakami"]
    
    status_choices = ['available', 'available', 'available', 'available', 'checked_out', 'reserved']
    
    for i, title in enumerate(book_titles):
        author = authors[i % len(authors)]
        category = random.choice(categories)
        bus = random.choice(buses)
        status = random.choice(status_choices)
        
        book, created = Book.objects.get_or_create(
            title=title,
            author=author,
            defaults={
                'publisher': "NXB Tổng Hợp",
                'publication_year': random.randint(1990, 2023),
                'page_count': random.randint(150, 800),
                'isbn': f"978{random.randint(1000000000, 9999999999)}",
                'category': category,
                'location': bus,
                'status': status,
                'description': f"Cuốn sách {title} của tác giả {author} là một tác phẩm nổi tiếng."
            }
        )
        if not created:
            # If exists, ensure it's available for demonstration if it's currently something else
            if random.random() > 0.3:
                book.status = 'available'
                book.save()
        
    print(f"Seeded {len(book_titles)} books!")

if __name__ == '__main__':
    seed_data()
