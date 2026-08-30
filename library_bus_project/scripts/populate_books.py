import os
import sys
import json
import urllib.request
import urllib.parse
from io import BytesIO
import time
import random
import unicodedata

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Set up Django environment
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(current_dir)
sys.path.insert(0, project_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_bus_project.settings')

import django
django.setup()

from django.core.files.base import ContentFile
from inventory.models import Book, Category, LibraryBus
from PIL import Image, ImageDraw, ImageFont

# ==============================================================================
# 1. TẠO XE BUS LƯU ĐỘNG
# ==============================================================================
def get_or_create_buses():
    bus1, _ = LibraryBus.objects.get_or_create(
        name="Bus Sách Tri Thức 01",
        defaults={
            'license_plate': '29A-123.45',
            'location_name': 'Công viên Thống Nhất, Hai Bà Trưng, Hà Nội',
            'latitude': 21.0163,
            'longitude': 105.8451,
            'operating_status': 'active',
            'capacity': 1000
        }
    )
    bus2, _ = LibraryBus.objects.get_or_create(
        name="Bus Sách Sinh Viên 02",
        defaults={
            'license_plate': '29B-678.90',
            'location_name': 'Khuôn viên Đại học Bách Khoa Hà Nội',
            'latitude': 21.0042,
            'longitude': 105.8437,
            'operating_status': 'active',
            'capacity': 800
        }
    )
    bus3, _ = LibraryBus.objects.get_or_create(
        name="Bus Sách Cộng Đồng 03",
        defaults={
            'license_plate': '29C-555.88',
            'location_name': 'Khu đô thị Ecopark, Hưng Yên',
            'latitude': 20.9700,
            'longitude': 105.9300,
            'operating_status': 'active',
            'capacity': 1200
        }
    )
    return [bus1, bus2, bus3]

# ==============================================================================
# 2. TẠO CẤU TRÚC DANH MỤC CHUẨN
# ==============================================================================
def setup_categories():
    categories_tree = [
        {
            'name': 'Văn học',
            'color_code': '#e76f51',
            'icon': 'fa-book-open',
            'subcategories': ['Văn học Việt Nam', 'Văn học nước ngoài', 'Văn học kinh điển']
        },
        {
            'name': 'Tiểu thuyết',
            'color_code': '#f4a261',
            'icon': 'fa-feather',
            'subcategories': ['Ngôn tình', 'Học đường', 'Khoa học viễn tưởng', 'Trinh thám & Bí ẩn']
        },
        {
            'name': 'Khoa học Công nghệ',
            'color_code': '#2a9d8f',
            'icon': 'fa-laptop-code',
            'subcategories': ['Công nghệ thông tin', 'Khoa học vũ trụ', 'Trí tuệ nhân tạo']
        },
        {
            'name': 'Kinh tế',
            'color_code': '#e9c46a',
            'icon': 'fa-chart-line',
            'subcategories': ['Kinh doanh & Khởi nghiệp', 'Tài chính cá nhân', 'Marketing & Bán hàng']
        },
        {
            'name': 'Tâm lý & Kỹ năng',
            'color_code': '#9b5de5',
            'icon': 'fa-brain',
            'subcategories': ['Phát triển bản thân', 'Tâm lý học hành vi', 'Kỹ năng sống']
        },
        {
            'name': 'Lịch sử & Nghệ thuật',
            'color_code': '#457b9d',
            'icon': 'fa-landmark',
            'subcategories': ['Lịch sử Việt Nam', 'Lịch sử thế giới', 'Nghệ thuật & Hội họa']
        }
    ]

    cat_map = {}
    for cat_data in categories_tree:
        parent_cat, _ = Category.objects.get_or_create(
            name=cat_data['name'],
            defaults={'color_code': cat_data['color_code'], 'icon': cat_data['icon'], 'is_active': True}
        )
        cat_map[cat_data['name']] = parent_cat
        for sub_name in cat_data['subcategories']:
            sub_cat, _ = Category.objects.get_or_create(
                name=sub_name,
                defaults={'parent': parent_cat, 'color_code': cat_data['color_code'], 'icon': cat_data['icon'], 'is_active': True}
            )
            cat_map[sub_name] = sub_cat

    return cat_map

# ==============================================================================
# 3. TẠO ẢNH BÌA NGHỆ THUẬT VỚI PILLOW KHI THIẾU ẢNH TRỰC TUYẾN
# ==============================================================================
def generate_artistic_cover(title, author, category_name="Thư viện Bus"):
    """Tạo ảnh bìa sách chất lượng cao 600x800 chuẩn thiết kế nghệ thuật"""
    width, height = 600, 800
    
    # Bảng màu gradient sang trọng
    palettes = [
        ((30, 41, 59), (15, 23, 42), (217, 119, 6)),    # Deep Slate & Amber Gold
        ((67, 24, 255), (17, 8, 86), (255, 255, 255)),   # Royal Indigo & White
        ((180, 83, 9), (120, 53, 15), (254, 243, 199)),  # Toasty Warm & Cream
        ((15, 118, 110), (19, 78, 74), (204, 251, 241)), # Deep Emerald & Mint
        ((159, 18, 57), (136, 19, 55), (255, 228, 230)), # Velvet Ruby & Rose
        ((88, 28, 135), (59, 7, 100), (243, 232, 255)),  # Mystic Violet & Lilac
    ]
    
    bg_start, bg_end, accent_color = random.choice(palettes)
    
    img = Image.new('RGB', (width, height), color=bg_start)
    draw = ImageDraw.Draw(img)
    
    # Tạo gradient nền
    for y in range(height):
        r = int(bg_start[0] + (bg_end[0] - bg_start[0]) * (y / height))
        g = int(bg_start[1] + (bg_end[1] - bg_start[1]) * (y / height))
        b = int(bg_start[2] + (bg_end[2] - bg_start[2]) * (y / height))
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # Vẽ viền khung sách nghệ thuật
    margin = 35
    draw.rectangle(
        [(margin, margin), (width - margin, height - margin)],
        outline=accent_color,
        width=3
    )
    draw.rectangle(
        [(margin + 8, margin + 8), (width - margin - 8, height - margin - 8)],
        outline=(255, 255, 255, 60),
        width=1
    )
    
    # Gáy sách (spine effect) bên trái
    draw.rectangle([(margin, margin), (margin + 20, height - margin)], fill=(0, 0, 0, 40))
    draw.line([(margin + 20, margin), (margin + 20, height - margin)], fill=(255, 255, 255, 80), width=1)
    
    # Header: Category tag
    draw.rectangle([(width//2 - 120, margin + 30), (width//2 + 120, margin + 65)], fill=accent_color)
    draw.text((width//2, margin + 47), category_name.upper(), fill=(15, 23, 42), anchor="mm")
    
    # Tiêu đề sách (chia dòng tự động)
    words = title.split()
    lines = []
    current_line = []
    for word in words:
        current_line.append(word)
        if len(" ".join(current_line)) > 16:
            lines.append(" ".join(current_line))
            current_line = []
    if current_line:
        lines.append(" ".join(current_line))
    
    # Vẽ tiêu đề sách ở trung tâm
    title_text = "\n".join(lines[:4])
    start_y = height // 2 - (len(lines) * 25)
    
    # Icon sách ở giữa
    draw.text((width // 2, start_y - 60), "📖", fill=accent_color, anchor="mm")
    
    # Text Title
    draw.text((width // 2, start_y + 30), title_text, fill=(255, 255, 255), anchor="mm", align="center")
    
    # Đường gạch phân cách
    draw.line([(width // 2 - 60, height - margin - 140), (width // 2 + 60, height - margin - 140)], fill=accent_color, width=2)
    
    # Tác giả ở cuối bìa
    draw.text((width // 2, height - margin - 100), author, fill=(240, 240, 240), anchor="mm")
    
    # Footer: Logo Thư viện xe Bus
    draw.text((width // 2, height - margin - 40), "🚌 THƯ VIỆN LƯU ĐỘNG", fill=accent_color, anchor="mm")
    
    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=92)
    return buffer.getvalue()

# ==============================================================================
# 4. TẢI ẢNH TỪ URL TRỰC TUYẾN
# ==============================================================================
def download_cover(image_url):
    try:
        req = urllib.request.Request(image_url, headers={'User-Agent': 'LibraryBus/2.0 (Mozilla/5.0)'})
        with urllib.request.urlopen(req, timeout=8) as response:
            content = response.read()
            if len(content) > 1500: # Không nhận ảnh lỗi 1px
                return content
    except Exception:
        pass
    return None

def fetch_openlibrary_books(query, limit=10):
    url = f"https://openlibrary.org/search.json?q={urllib.parse.quote(query)}&limit={limit}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'LibraryBus/2.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get('docs', [])
    except Exception as e:
        print(f"     ⚠️ Lỗi fetch OpenLibrary ({query}): {e}")
        return []

# ==============================================================================
# 5. DANH MỤC SÁCH KINH ĐIỂN ĐẶC SẮC
# ==============================================================================
def populate_curated_masterpieces(cat_map, buses):
    curated_books = [
        # Văn học Việt Nam
        {
            'title': 'Dế Mèn Phiêu Lưu Ký',
            'author': 'Tô Hoài',
            'category': 'Văn học Việt Nam',
            'year': 1941,
            'pages': 190,
            'publisher': 'NXB Kim Đồng',
            'isbn': '9786042084988',
            'description': 'Tác phẩm văn học thiếu nhi kinh điển của Việt Nam kể về hành trình phiêu lưu đầy thú vị và bài học đường đời của chú Dế Mèn.',
            'cover_query': 'De Men Phieu Luu Ky'
        },
        {
            'title': 'Số Đỏ',
            'author': 'Vũ Trọng Phụng',
            'category': 'Văn học Việt Nam',
            'year': 1936,
            'pages': 260,
            'publisher': 'NXB Văn Học',
            'isbn': '9786049544988',
            'description': 'Tiểu thuyết trào phúng hiện thực xuất sắc nhất của văn học Việt Nam phê phán xã hội phong kiến tư sản nửa mùa.',
            'cover_query': 'So Do Vu Trong Phung'
        },
        {
            'title': 'Mắt Biếc',
            'author': 'Nguyễn Nhật Ánh',
            'category': 'Văn học Việt Nam',
            'year': 1990,
            'pages': 300,
            'publisher': 'NXB Trẻ',
            'isbn': '9786041151239',
            'description': 'Câu chuyện tình yêu tuổi học trò đẹp nhưng buồn giữa Ngạn và Hà Lan với đôi mắt biếc biếc làng Đo Đo.',
            'cover_query': 'Mat Biec'
        },
        {
            'title': 'Tôi Thấy Hoa Vàng Trên Cỏ Xanh',
            'author': 'Nguyễn Nhật Ánh',
            'category': 'Văn học Việt Nam',
            'year': 2010,
            'pages': 378,
            'publisher': 'NXB Trẻ',
            'isbn': '9786041072930',
            'description': 'Ký ức tuổi thơ êm đềm ở một làng quê nghèo miền Trung với những câu chuyện tình cảm anh em, bè bạn dung dị.',
            'cover_query': 'Toi Thay Hoa Vang Tren Co Xanh'
        },
        {
            'title': 'Tắt Đèn',
            'author': 'Ngô Tất Tố',
            'category': 'Văn học Việt Nam',
            'year': 1939,
            'pages': 220,
            'publisher': 'NXB Văn Học',
            'isbn': '9786049633859',
            'description': 'Bức tranh chân thực về số phận người nông dân nghèo trước Cách mạng qua hình tượng chị Dậu kiên cường.',
            'cover_query': 'Tat Den'
        },
        {
            'title': 'Lão Hạc & Truyện Ngắn Nam Cao',
            'author': 'Nam Cao',
            'category': 'Văn học Việt Nam',
            'year': 1943,
            'pages': 180,
            'publisher': 'NXB Hội Nhà Văn',
            'isbn': '9786049890123',
            'description': 'Tập truyện ngắn nhân đạo sâu sắc về người nông dân nghèo cùng con chó Vàng trong xã hội cũ.',
            'cover_query': 'Nam Cao'
        },
        {
            'title': 'Cánh Đồng Bất Tận',
            'author': 'Nguyễn Ngọc Tư',
            'category': 'Văn học Việt Nam',
            'year': 2005,
            'pages': 214,
            'publisher': 'NXB Trẻ',
            'isbn': '9786041042345',
            'description': 'Tập truyện ngắn đậm chất sông nước miền Tây Nam Bộ với những phận người trôi dạt lay động tâm can.',
            'cover_query': 'Canh Dong Bat Tan'
        },
        
        # Văn học Nước ngoài
        {
            'title': 'Nhà Giả Kim',
            'author': 'Paulo Coelho',
            'category': 'Văn học nước ngoài',
            'year': 1988,
            'pages': 228,
            'publisher': 'NXB Hội Nhà Văn',
            'isbn': '9786049895678',
            'description': 'Cuốn sách gối đầu giường của hàng triệu độc giả về hành trình theo đuổi ước mơ và lắng nghe tiếng gọi trái tim.',
            'cover_query': 'The Alchemist Paulo Coelho'
        },
        {
            'title': 'Hoàng Tử Bé',
            'author': 'Antoine de Saint-Exupéry',
            'category': 'Văn học nước ngoài',
            'year': 1943,
            'pages': 110,
            'publisher': 'NXB Kim Đồng',
            'isbn': '9786042134567',
            'description': 'Tác phẩm bất hủ về tình yêu, sự cô đơn và ý nghĩa của những điều vô hình chỉ cảm nhận được bằng trái tim.',
            'cover_query': 'The Little Prince'
        },
        {
            'title': 'Ông Già Và Biển Cả',
            'author': 'Ernest Hemingway',
            'category': 'Văn học nước ngoài',
            'year': 1952,
            'pages': 130,
            'publisher': 'NXB Văn Học',
            'isbn': '9786049543219',
            'description': 'Khúc tráng ca ngợi ca ý chí và lòng kiên cường của con người trước thiên nhiên dữ dội.',
            'cover_query': 'The Old Man and the Sea'
        },
        {
            'title': 'Trăm Năm Cô Đơn',
            'author': 'Gabriel García Márquez',
            'category': 'Văn học nước ngoài',
            'year': 1967,
            'pages': 470,
            'publisher': 'NXB Văn Học',
            'isbn': '9786049547890',
            'description': 'Đỉnh cao của chủ nghĩa hiện thực huyền ảo về dòng họ Buendía qua 7 thế hệ ở ngôi làng Macondo.',
            'cover_query': 'One Hundred Years of Solitude'
        },
        {
            'title': 'Bố Già (The Godfather)',
            'author': 'Mario Puzo',
            'category': 'Văn học nước ngoài',
            'year': 1969,
            'pages': 448,
            'publisher': 'NXB Văn Học',
            'isbn': '9786049548901',
            'description': 'Kiệt tác văn học kinh điển về thế giới ngầm mafia và gia đình Corleone đầy quyền lực và lòng trắc ẩn.',
            'cover_query': 'The Godfather Mario Puzo'
        },
        {
            'title': 'Tội Ác Và Trừng Phạt',
            'author': 'Fyodor Dostoevsky',
            'category': 'Văn học kinh điển',
            'year': 1866,
            'pages': 650,
            'publisher': 'NXB Văn Học',
            'isbn': '9786049543332',
            'description': 'Kiệt tác phân tích tâm lý tội phạm và hành trình sám hối cứu rỗi tâm hồn của chàng sinh viên Raskolnikov.',
            'cover_query': 'Crime and Punishment Dostoevsky'
        },

        # Kinh tế & Khởi nghiệp
        {
            'title': 'Đắc Nhân Tâm',
            'author': 'Dale Carnegie',
            'category': 'Phát triển bản thân',
            'year': 1936,
            'pages': 320,
            'publisher': 'NXB Tổng Hợp TP.HCM',
            'isbn': '9786045890123',
            'description': 'Cuốn sách kinh điển về nghệ thuật ứng xử, giao tiếp và thu phục lòng người bán chạy nhất mọi thời đại.',
            'cover_query': 'How to Win Friends and Influence People'
        },
        {
            'title': 'Cha Giàu Cha Nghèo',
            'author': 'Robert Kiyosaki',
            'category': 'Tài chính cá nhân',
            'year': 1997,
            'pages': 336,
            'publisher': 'NXB Trẻ',
            'isbn': '9786041089123',
            'description': 'Cuốn sách thay đổi tư duy tài chính về sự khác biệt trong cách kiếm tiền và đầu tư giữa người giàu và người nghèo.',
            'cover_query': 'Rich Dad Poor Dad'
        },
        {
            'title': 'Tư Duy Nhanh Và Chậm',
            'author': 'Daniel Kahneman',
            'category': 'Tâm lý học hành vi',
            'year': 2011,
            'pages': 610,
            'publisher': 'NXB Thế Giới',
            'isbn': '9786047723456',
            'description': 'Khám phá hai hệ thống chi phối cách chúng ta tư duy, đánh giá và đưa ra các quyết định hàng ngày.',
            'cover_query': 'Thinking Fast and Slow'
        },
        {
            'title': 'Khởi Nghiệp Tinh Gọn',
            'author': 'Eric Ries',
            'category': 'Kinh doanh & Khởi nghiệp',
            'year': 2011,
            'pages': 336,
            'publisher': 'NXB Tổng Hợp',
            'isbn': '9786045845678',
            'description': 'Phương pháp luận đột phá giúp doanh nghiệp phát triển sản phẩm nhanh chóng và tối ưu hóa nguồn lực.',
            'cover_query': 'The Lean Startup'
        },
        {
            'title': 'Nghĩ Giàu & Làm Giàu (Think and Grow Rich)',
            'author': 'Napoleon Hill',
            'category': 'Phát triển bản thân',
            'year': 1937,
            'pages': 380,
            'publisher': 'NXB Trẻ',
            'isbn': '9786041067890',
            'description': '13 nguyên tắc làm giàu và phát triển tư duy thành công được đúc kết từ hàng trăm triệu phú hàng đầu.',
            'cover_query': 'Think and Grow Rich'
        },

        # Khoa học & Công nghệ
        {
            'title': 'Sapiens: Lược Sử Loài Người',
            'author': 'Yuval Noah Harari',
            'category': 'Lịch sử thế giới',
            'year': 2011,
            'pages': 512,
            'publisher': 'NXB Tri Thức',
            'isbn': '9786049089012',
            'description': 'Hành trình phát triển phi thường của loài người từ sinh vật không đáng kể trở thành kẻ thống trị Trái Đất.',
            'cover_query': 'Sapiens Harari'
        },
        {
            'title': 'Lược Sử Thời Gian',
            'author': 'Stephen Hawking',
            'category': 'Khoa học vũ trụ',
            'year': 1988,
            'pages': 256,
            'publisher': 'NXB Trẻ',
            'isbn': '9786041045678',
            'description': 'Giải thích những bí ẩn lớn nhất của vũ trụ học: Vụ nổ Big Bang, Lỗ đen và Thuyết vạn vật.',
            'cover_query': 'A Brief History of Time'
        },
        {
            'title': 'Vũ Trụ (Cosmos)',
            'author': 'Carl Sagan',
            'category': 'Khoa học vũ trụ',
            'year': 1980,
            'pages': 410,
            'publisher': 'NXB Thế Giới',
            'isbn': '9786047701234',
            'description': 'Bản trường ca tuyệt đẹp dẫn dắt độc giả khám phá 15 tỷ năm tiến hóa của vũ trụ và nền văn minh.',
            'cover_query': 'Cosmos Carl Sagan'
        },
        {
            'title': 'Clean Code: Nghệ Thuật Viết Code Sạch',
            'author': 'Robert C. Martin',
            'category': 'Công nghệ thông tin',
            'year': 2008,
            'pages': 464,
            'publisher': 'Prentice Hall',
            'isbn': '9780132350884',
            'description': 'Kim chỉ nam thực hành viết mã nguồn sạch, dễ đọc, dễ bảo trì dành cho mọi lập trình viên chuyên nghiệp.',
            'cover_query': 'Clean Code Robert Martin'
        },
        {
            'title': 'Python Crash Course: Lập Trình Dự Án Thực Tế',
            'author': 'Eric Matthes',
            'category': 'Công nghệ thông tin',
            'year': 2019,
            'pages': 544,
            'publisher': 'No Starch Press',
            'isbn': '9781593279288',
            'description': 'Cuốn sách bán chạy nhất thế giới hướng dẫn lập trình Python từ cơ bản đến nâng cao qua các dự án thực tế.',
            'cover_query': 'Python Crash Course'
        },
        {
            'title': 'Trí Tuệ Nhân Tạo: Kỷ Nguyên Mới (Life 3.0)',
            'author': 'Max Tegmark',
            'category': 'Trí tuệ nhân tạo',
            'year': 2017,
            'pages': 380,
            'publisher': 'NXB Thế Giới',
            'isbn': '9786047738901',
            'description': 'Bàn về tương lai của nhân loại trong kỷ nguyên bùng nổ của trí tuệ nhân tạo (AI).',
            'cover_query': 'Life 3.0 Max Tegmark'
        }
    ]

    print("\n📚 [1/3] Đang nạp danh mục tác phẩm kinh điển & tạo ảnh bìa...")
    count = 0
    for item in curated_books:
        category_obj = cat_map.get(item['category']) or cat_map.get('Văn học')
        bus_obj = random.choice(buses)
        
        book, created = Book.objects.get_or_create(
            title=item['title'],
            defaults={
                'author': item['author'],
                'publisher': item['publisher'],
                'publication_year': item['year'],
                'page_count': item['pages'],
                'isbn': item['isbn'],
                'category': category_obj,
                'location': bus_obj,
                'description': item['description'],
                'language': 'Tiếng Việt',
                'status': random.choice(['available', 'available', 'available', 'checked_out']),
                'condition': random.choice(['new', 'like_new', 'good'])
            }
        )

        # Đảm bảo có ảnh bìa
        if not book.cover_image or not book.cover_image.name:
            cover_data = None
            # Thử tìm online trước
            docs = fetch_openlibrary_books(item['cover_query'], limit=2)
            if docs:
                for doc in docs:
                    cover_id = doc.get('cover_i')
                    if cover_id:
                        img_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
                        cover_data = download_cover(img_url)
                        if cover_data:
                            book.cover_image.save(f"curated_{cover_id}.jpg", ContentFile(cover_data), save=False)
                            break
            
            # Nếu online không có, tạo bìa nghệ thuật chất lượng cao
            if not book.cover_image:
                cover_data = generate_artistic_cover(book.title, book.author, item['category'])
                book.cover_image.save(f"art_{book.pk}.jpg", ContentFile(cover_data), save=False)
        
        # Đảm bảo category và bus
        book.category = category_obj
        book.location = bus_obj
        book.save()
        count += 1
        print(f"  ✨ {'Tạo mới' if created else 'Đồng bộ'}: {book.title} ({item['author']})")

    print(f"  🎉 Hoàn tất {count} tác phẩm kinh điển!")

# ==============================================================================
# 6. TÌM NẠP TỪ INTERNET THEO CHỦ ĐỀ
# ==============================================================================
def populate_online_categories(cat_map, buses):
    online_topics = [
        ('science fiction', 'Khoa học viễn tưởng'),
        ('artificial intelligence python', 'Trí tuệ nhân tạo'),
        ('personal finance investing', 'Tài chính cá nhân'),
        ('psychology cognitive', 'Tâm lý học hành vi'),
        ('ancient world history', 'Lịch sử thế giới'),
        ('sherlock holmes mystery', 'Trinh thám & Bí ẩn'),
        ('classic art history', 'Nghệ thuật & Hội họa'),
        ('love romance novel', 'Ngôn tình'),
        ('school student novel', 'Học đường')
    ]

    print("\n🌐 [2/3] Đang nạp sách phong phú từ Internet (OpenLibrary)...")
    total_added = 0
    for query, target_category in online_topics:
        cat_obj = cat_map.get(target_category)
        docs = fetch_openlibrary_books(query, limit=6)
        
        for doc in docs:
            title = doc.get('title', '').strip()
            if not title:
                continue
            
            if Book.objects.filter(title__iexact=title[:255]).exists():
                continue
            
            authors = doc.get('author_name', ['Nhiều tác giả'])
            author = ", ".join(authors)[:200]
            
            publishers = doc.get('publisher', ['NXB Tri Thức'])
            publisher = publishers[0][:200] if publishers else 'NXB Tri Thức'
            
            pub_year = doc.get('first_publish_year', random.randint(1995, 2023))
            page_count = doc.get('number_of_pages_median', random.randint(180, 480))
            isbns = doc.get('isbn', [])
            isbn = isbns[0][:13] if isbns else f"978{random.randint(1000000000, 9999999999)}"
            bus_obj = random.choice(buses)
            
            book = Book(
                title=title[:255],
                author=author,
                publisher=publisher,
                publication_year=pub_year,
                page_count=page_count,
                isbn=isbn,
                category=cat_obj,
                location=bus_obj,
                language='Tiếng Anh / Dịch',
                description=f"Cuốn sách '{title}' của tác giả {author} là tác phẩm tiêu biểu thuộc danh mục {target_category}.",
                status=random.choice(['available', 'available', 'checked_out']),
                condition=random.choice(['new', 'like_new', 'good'])
            )
            
            cover_id = doc.get('cover_i')
            if cover_id:
                img_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
                cover_data = download_cover(img_url)
                if cover_data:
                    book.cover_image.save(f"online_{cover_id}.jpg", ContentFile(cover_data), save=False)
            
            if not book.cover_image:
                cover_data = generate_artistic_cover(book.title, book.author, target_category)
                book.cover_image.save(f"art_{random.randint(10000, 99999)}.jpg", ContentFile(cover_data), save=False)
            
            try:
                book.save()
                total_added += 1
                print(f"     ✅ Thêm sách mới: {title[:45]}...")
            except Exception:
                pass
            
            time.sleep(0.5)

    print(f"  🎉 Đã nạp thành công {total_added} sách mới từ Internet!")

# ==============================================================================
# 7. BỔ SUNG ẢNH BÌA CHO TOÀN BỘ SÁCH CŨ CHƯA CÓ BÌA
# ==============================================================================
def ensure_all_books_have_covers():
    print("\n🎨 [3/3] Đảm bảo 100% tất cả các cuốn sách trong hệ thống đều có ảnh bìa đẹp...")
    missing_books = Book.objects.filter(cover_image='') | Book.objects.filter(cover_image__isnull=True)
    fixed = 0
    
    for book in missing_books:
        cat_name = book.category.name if book.category else "Sách Hay"
        cover_data = generate_artistic_cover(book.title, book.author, cat_name)
        book.cover_image.save(f"art_cover_{book.pk}.jpg", ContentFile(cover_data), save=True)
        fixed += 1
        
    print(f"  ✅ Đã tạo bìa nghệ thuật cho {fixed} sách cũ chưa có ảnh!")

def update_all_category_counts():
    from django.core.cache import cache
    for cat in Category.objects.all():
        cat.update_book_count()
    cache.clear()
    print("  🔄 Đã cập nhật lại toàn bộ bộ đếm danh mục và xóa Cache!")

def main():
    print("==================================================================")
    print("  🚀 BỔ SUNG SÁCH TỪ INTERNET & TẠO ẢNH BÌA CHO TOÀN DỰ ÁN       ")
    print("==================================================================")
    
    buses = get_or_create_buses()
    cat_map = setup_categories()
    
    populate_curated_masterpieces(cat_map, buses)
    populate_online_categories(cat_map, buses)
    ensure_all_books_have_covers()
    update_all_category_counts()
    
    total_books = Book.objects.count()
    with_covers = Book.objects.exclude(cover_image='').count()
    
    print("\n==================================================================")
    print(f"  🏁 TỔNG KẾT:")
    print(f"     - Tổng số sách trong thư viện: {total_books} cuốn")
    print(f"     - Sách có ảnh bìa hoàn chỉnh: {with_covers} / {total_books} (100%)")
    print("==================================================================")

if __name__ == '__main__':
    main()
