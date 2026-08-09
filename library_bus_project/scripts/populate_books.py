import os
import sys
import json
import urllib.request
import urllib.parse
from io import BytesIO
from urllib.error import URLError
import time

# Set up Django environment
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(current_dir)
sys.path.append(project_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_bus_project.settings')

import django
django.setup()

from django.core.files.base import ContentFile
from inventory.models import Book, Category

def fetch_books(query, limit=20):
    url = f"https://openlibrary.org/search.json?q={urllib.parse.quote(query)}&limit={limit}"
    print(f"Fetching from: {url}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'LibraryBus/1.0'})
        response = urllib.request.urlopen(req)
        data = json.loads(response.read())
        return data.get('docs', [])
    except URLError as e:
        print(f"Error fetching data: {e}")
        return []

def populate_database():
    queries = [
        ('tiểu thuyết', 'Tiểu thuyết', '#ff6b6b', 'fa-book-open'),
        ('khoa học vũ trụ', 'Khoa học', '#4ecdc4', 'fa-flask'),
        ('lịch sử việt nam', 'Lịch sử', '#45b7d1', 'fa-landmark'),
        ('lập trình python', 'Công nghệ thông tin', '#96ceb4', 'fa-laptop-code'),
        ('tâm lý học tội phạm', 'Tâm lý học', '#ffeead', 'fa-brain'),
        ('kinh doanh', 'Kinh tế', '#ff9999', 'fa-chart-line')
    ]
    
    total_added = 0
    
    for query, cat_name, cat_color, cat_icon in queries:
        print(f"\nProcessing query: {query}")
        
        category, created = Category.objects.get_or_create(
            name=cat_name,
            defaults={'color_code': cat_color, 'icon': cat_icon, 'is_active': True}
        )
        if created:
            print(f"Created category: {category.name}")
            
        items = fetch_books(query, limit=15)
        for item in items:
            title = item.get('title', 'Unknown Title')
            
            # Skip if book already exists
            if Book.objects.filter(title=title[:255]).exists():
                print(f"Skipping existing: {title}")
                continue
                
            authors = item.get('author_name', ['Unknown Author'])
            author = ", ".join(authors)[:200]
            
            publishers = item.get('publisher', ['Unknown Publisher'])
            publisher = ", ".join(publishers)[:200]
            
            pub_year = item.get('first_publish_year', 2023)
                
            page_count = item.get('number_of_pages_median', 200)
            if not page_count or page_count == 0: page_count = 200
            
            description = 'Đang cập nhật mô tả cho cuốn sách này.'
            
            # Get ISBN
            isbns = item.get('isbn', [])
            isbn = isbns[0] if isbns else ''
            
            # Create Book
            book = Book(
                title=title[:255],
                author=author,
                publisher=publisher,
                publication_year=pub_year,
                page_count=page_count,
                isbn=isbn[:13],
                description=description,
                category=category,
                language='Tiếng Việt',
                status='available',
                condition='new'
            )
            
            # Fetch Cover Image
            cover_i = item.get('cover_i')
            
            if cover_i:
                cover_url = f"https://covers.openlibrary.org/b/id/{cover_i}-L.jpg"
                try:
                    req = urllib.request.Request(cover_url, headers={'User-Agent': 'LibraryBus/1.0'})
                    img_response = urllib.request.urlopen(req)
                    img_filename = f"{cover_i}.jpg"
                    book.cover_image.save(img_filename, ContentFile(img_response.read()), save=False)
                except Exception as e:
                    print(f"Failed to fetch image for {title}: {e}")
                    
            try:
                book.save()
                total_added += 1
                print(f"Added: {title}")
            except Exception as e:
                print(f"Error saving {title}: {e}")
                
        # Sleep to avoid rate limiting
        time.sleep(2)
                
    print(f"\nCompleted! Total books added: {total_added}")

if __name__ == '__main__':
    print("Starting data population script...")
    populate_database()
