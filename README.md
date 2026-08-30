# 🚌 Tủ Sách Lưu Động (Library Bus System)

[![CI Pipeline](https://github.com/duongduongdphk66a-spec/prj/actions/workflows/ci.yml/badge.svg)](https://github.com/duongduongdphk66a-spec/prj/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.2+-green.svg)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Design](https://img.shields.io/badge/Design%20System-Neo--Bakery%206--Tone-orange.svg)](DESIGN.md)

Hệ thống quản lý, điều phối và phân phối sách thông qua **Mạng lưới Xe Bus Thư Viện Lưu Động**, mang tri thức đến tận tay người đọc tại các khu dân cư, trường học và địa bàn ngoại thành.

---

## 🏗️ Kiến Trúc Hệ Thống

Dự án được xây dựng theo mô hình kiến trúc **Django Monolith Phân Hệ Cao Cấp (High-Performance Modular Monolith)** được thiết kế chịu tải **50.000 người dùng** và **500 truy cập đồng thời**:

* **`core`**: Base models, versioned cache mixin (`CacheMixin`), middleware, utility base querysets.
* **`users`**: Quản lý định danh, hồ sơ độc giả, xác thực Argon2, nâng cấp membership, tracking lịch sử đăng nhập.
* **`inventory`**: Quản lý kho sách (sách giấy & PDF viewer), danh mục phân cấp, đội xe bus lưu động, lộ trình & trạm dừng GPS, trợ lý ảo Gemini AI.
* **`transactions`**: Nghiệp vụ mượn, trả, gia hạn, đặt trước theo hàng đợi, vận chuyển giao nhận sách tận nơi, xử lý phí phạt với cơ chế khóa bi quan `select_for_update` chống race-condition.
* **`analytics`**: Thống kê thói quen đọc sách, bảng xếp hạng độc giả (Leaderboard), phân tích hiệu suất tuyến xe buýt, hệ thống gợi ý sách tự động.
* **`notifications`**: Hệ thống thông báo thời gian thực đa kênh (In-app notification badge, Email).
* **`blog`**: Cổng thông tin tin tức, bài viết, sự kiện, đánh giá sách tương tác.

---

## 🎨 Giao Diện & Chuyển Động Chuẩn GSAP

Dự án áp dụng ngôn ngữ thiết kế **Neo-Bakery & Classic Library** (bảng màu 6 sắc thái Mật Mía & Bơ nướng ấm áp) kết hợp bộ chuyển động chuẩn **[greensock/gsap-skills](https://github.com/greensock/gsap-skills)**:
* **Compositor-Only Animations:** 100% chuyển động sử dụng `transform` (`x`, `y`, `scale`, `rotation`) và `autoAlpha` đạt chuẩn mượt mà 60 FPS.
* **ScrollTrigger.batch():** Gom nhóm hiệu ứng xuất hiện cho danh mục thẻ sách, trạm xe buýt và bài viết blog.
* **Dynamic Tabular Counter:** Đếm số liệu tăng dần mượt mà khi cuộn tới phần Thống kê.
* **3D Micro-Tilt Physics:** Hiệu ứng nghiêng 3D chân thực khi di chuột qua thẻ sách nổi bật.
* **Accessibility (A11y):** Tự động phát hiện và tắt chuyển động khi người dùng bật `prefers-reduced-motion: reduce`.

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Môi Trường Local

### Yêu Cầu Tiên Quyết
* Python `>= 3.11`
* MySQL Server `>= 8.0`
* Redis `>= 6.0` (Khuyến nghị cho Cache & Celery)

### 1. Khởi Tạo Môi Trường Ảo
```bash
# Clone repository
git clone https://github.com/duongduongdphk66a-spec/prj.git
cd prj

# Tạo và kích hoạt virtual environment
python -m venv venv
# Trên Windows:
venv\Scripts\activate
# Trên Linux/macOS:
source venv/bin/activate

# Cài đặt thư viện dependencies
pip install -r requirements-dev.txt
```

### 2. Cấu Hình Biến Môi Trường (.env)
Tạo file `.env` tại thư mục `library_bus_project/.env` từ file mẫu:
```bash
cp library_bus_project/.env.example library_bus_project/.env
```
Điền các tham số cấu hình cơ bản:
```ini
SECRET_KEY=your-super-secret-key-change-me
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=tsdd
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_HOST=127.0.0.1
DB_PORT=3306

REDIS_URL=redis://127.0.0.1:6379/1
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0

GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL_NAME=gemini-1.5-flash
```

### 3. Migrate Cơ Sở Dữ Liệu & Khởi Tạo Admin
```bash
cd library_bus_project

# Thực thi migration
python manage.py migrate

# Tạo tài khoản quản trị Admin
python manage.py createsuperuser
```

### 4. Chạy Ứng Dụng
```bash
# Cách 1: Chạy qua Waitress Server đa luồng (Tối ưu cho dev)
python run_server.py

# Cách 2: Chạy Django Development Server
python manage.py runserver
```
Truy cập hệ thống tại: `http://localhost:8000/`

---

## ⚡ Khởi Chạy Tác Vụ Bất Đồng Bộ (Celery)

Mở 2 terminal riêng biệt:

```bash
# Terminal 1: Chạy Celery Worker
celery -A library_bus_project worker -l info --pool=threads

# Terminal 2: Chạy Celery Beat Scheduler (Định kỳ kiểm tra sách quá hạn, cập nhật stats)
celery -A library_bus_project beat -l info
```

---

## 🐳 Triển Khai Bằng Docker Compose

Hệ thống cung cấp sẵn file orchestration `docker-compose.yml` gồm 5 dịch vụ độc lập:
* `web` (Django + Gunicorn)
* `db` (MySQL 8.0)
* `redis` (Redis 7)
* `celery_worker` (Xử lý hàng đợi)
* `celery_beat` (Lập lịch tác vụ định kỳ)

```bash
# Khởi động toàn bộ stack
docker-compose up -d --build

# Xem logs
docker-compose logs -f web

# Thực hiện migration bên trong container
docker-compose exec web python manage.py migrate
```

---

## 🧪 Kiểm Thử & Đảm Bảo Chất Lượng (QA)

### 1. Kiểm Tra Chuẩn Thiết Kế & GSAP (Taste Preflight Audit)
```bash
python library_bus_project/scripts/taste_preflight_check.py
```

### 2. Kiểm Thử Chức Năng Tự Động (Functional E2E Test)
```bash
python library_bus_project/functional_test.py
```

### 3. Chạy Toàn Bộ Test Suite
```bash
pytest
# Hoặc:
python library_bus_project/manage.py test users inventory transactions analytics blog notifications
```

---

## 📜 Giấy Phép (License)

Dự án được phân phối dưới giấy phép **MIT License**. Chi tiết xem tại tệp `LICENSE`.
