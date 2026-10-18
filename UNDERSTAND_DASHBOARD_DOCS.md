# 📚 TÀI LIỆU ĐẶC TẢ KỸ THUẬT & KIẾN TRÚC HỆ THỐNG
## BẢN ĐỒ RADAR VÒNG TRÒN ĐỒNG TÂM VÀ KIẾN TRÚC DJANGO MODULAR MONOLITH
**Dự án:** Hệ thống Quản lý Tủ Sách Lưu Động (Library Bus System)  
**Tệp phân tích:** [`understand_dashboard.html`](understand_dashboard.html)  
**Tệp tài liệu Word:** [`UNDERSTAND_DASHBOARD_DOCS.docx`](UNDERSTAND_DASHBOARD_DOCS.docx)  
**Phiên bản:** 2.0.0 | **Ngày phân tích:** 2026-09-03 | **Commit:** `09912103a`

---

## 📑 MỤC LỤC
1. [Phần 1: Tổng Quan Dự Án & Bối Cảnh Kiến Trúc](#phần-1-tổng-quan-dự-án--bối-cảnh-kiến-trúc)
2. [Phần 2: Thống Kê Định Lượng & Chỉ Số Đồ Thị (Metrics)](#phần-2-thống-kê-định-lượng--chỉ-số-đồ-thị-metrics)
3. [Phần 3: Thuyết Minh Chi Tiết 18 Loại Quan Hệ Kiến Trúc Phân Cấp](#phần-3-thuyết-minh-chi-tiết-18-loại-quan-hệ-kiến-trúc-phân-cấp)
4. [Phần 4: Phân Tích Sâu 6 Tầng Vòng Tròn Đồng Tâm (The 6 Concentric Rings)](#phần-4-phân-tích-sâu-6-tầng-vòng-tròn-đồng-tâm-the-6-concentric-rings)
5. [Phần 5: Chi Tiết 7 Phân Hệ Nghiệp Vụ (Django Apps)](#phần-5-chi-tiết-7-phân-hệ-nghiệp-vụ-django-apps)
6. [Phần 6: Lộ Trình Khám Phá Kiến Trúc 7 Bước (The 7-Step Guided Tour)](#phần-6-lộ-trình-khám-phá-kiến-trúc-7-bước-the-7-step-guided-tour)
7. [Phần 7: Các Tính Năng Tương Tác Chuyên Sâu Trên Dashboard](#phần-7-các-tính-năng-tương-tác-chuyên-sâu-trên-dashboard)
8. [Phần 8: Hướng Dẫn Vận Hành, Bảo Trì & Cập Nhật Dữ Liệu](#phần-8-hướng-dẫn-vận-hành-bảo-trì--cập-nhật-dữ-liệu)

---

## PHẦN 1: TỔNG QUAN DỰ ÁN & BỐI CẢNH KIẾN TRÚC

### 1.1. Giới thiệu Dự án Tủ Sách Lưu Động
Dự án **Tủ Sách Lưu Động (Library Bus System)** là nền tảng công nghệ số hóa kết hợp với mạng lưới các xe buýt thư viện lưu động thực tế. Sứ mệnh cốt lõi của dự án là mang tri thức và sách đọc đến tận các trường học, khu công nghiệp, khu dân cư ngoại thành và các vùng nông thôn xa xôi – nơi các thư viện truyền thống cố định chưa thể đáp ứng đầy đủ nhu cầu của bạn đọc.

### 1.2. Triết lý kiến trúc: Lựa chọn Django Modular Monolith
Hệ thống được xây dựng theo mô hình **High-Performance Django Modular Monolith** nhờ vào 3 ưu điểm vượt trội:
1. **Ranh giới miền nghiệp vụ nghiêm ngặt (Strict Bounded Contexts)**: Hệ thống được chia thành 7 Django Apps độc lập (`core`, `users`, `inventory`, `transactions`, `analytics`, `notifications`, `blog`). Mỗi app quản lý trọn vẹn domain của mình.
2. **Đảm bảo tính toàn vẹn giao dịch ACID**: Xử lý mượn/trả sách tức thời thông qua khóa bi quan (`select_for_update`) trên CSDL MySQL 8.0, loại bỏ hoàn toàn chi phí điều phối mạng và độ trễ của giao dịch phân tán (Two-Phase Commit hoặc Saga Pattern).
3. **Tối ưu chi phí hạ tầng & Triển khai**: Toàn bộ hệ thống được đóng gói trong một Docker Container đồng nhất, giảm thiểu tối đa tài nguyên máy chủ và công sức vận hành DevOps.

### 1.3. Vấn đề giải quyết của Dashboard Concentric Radar (`understand_dashboard.html`)
Khi mã nguồn phát triển vượt qua mốc 700 thành phần và 1.300 liên kết, đồ thị mạng lực tự do truyền thống thường gây rối ren, đè chữ. Tệp [understand_dashboard.html](file:///c:/Users/ADMIN/Documents/prj/understand_dashboard.html) áp dụng mô hình **Radar Vòng Tròn Đồng Tâm**:
* Lấy Lõi hệ thống (Core & Config) làm tâm điểm, mở rộng dần ra các tầng dữ liệu, nghiệp vụ, điều phối và giao diện ngoài cùng.
* Vô hiệu hóa tính toán động lực học của đồ thị (`physics: { enabled: false }`), tính toán tọa độ lượng giác cố định giúp canvas đạt tốc độ khung hình ổn định 60 FPS.
* **100% Offline Standalone**: Nhúng trực tiếp toàn bộ 500+ KB JSON dữ liệu và thư viện Vis.js nội bộ, mở được ngay trên mọi trình duyệt web mà không cần server.

---

## PHẦN 2: THỐNG KÊ ĐỊNH LƯỢNG & CHỈ SỐ ĐỒ THỊ (METRICS)

Dữ liệu đồ thị trích xuất từ mã nguồn thực tế tại Git commit `09912103a`:

### 2.1. Phân bố các Đỉnh (702 Nodes)
| Phân loại Node (`type`) | Số lượng | Tỷ lệ | Diễn giải vai trò kiến trúc |
| :--- | :---: | :---: | :--- |
| **Class (Lớp đối tượng)** | **288** | 41.0% | Django ORM Models, Forms, QuerySets, Class-Based Views, ModelAdmin, Unit Tests |
| **File (Tệp mã nguồn)** | **219** | 31.2% | Tệp Python (`.py`), HTML Templates, CSS, Shell scripts, Dockerfile |
| **Function (Hàm logic)** | **179** | 25.5% | Hàm API Views, Celery Task functions, Helper handlers, Data seeders |
| **Document (Tài liệu kỹ thuật)** | **9** | 1.3% | Tài liệu đặc tả Markdown (`README.md`, `DESIGN.md`, `PROJECT_STRUCTURE.md`,...) |
| **Config (Tệp cấu hình)** | **5** | 0.7% | `pyproject.toml`, `docker-compose.yml`, `requirements.txt`, `.env.example` |
| **Service (Dịch vụ nghiệp vụ)** | **2** | 0.3% | Dịch vụ giao dịch tập trung (`TransactionService`) và tích hợp AI ngoại vi |
| **TỔNG CỘNG** | **702** | **100%** | **Toàn bộ thực thể cấu thành hệ sinh thái mã nguồn Tủ Sách Lưu Động** |

> [!NOTE]
> **Phân bố độ phức tạp mã nguồn (Code Complexity Distribution):**
> * **Đơn giản (Simple):** 460 nodes (65.5%) — Các thuộc tính model cơ bản, hàm get/set, forms đơn giản.
> * **Trung bình (Moderate):** 152 nodes (21.7%) — Các Views xử lý nhiều query, QuerySet tùy biến, kịch bản gieo dữ liệu.
> * **Phức tạp (Complex):** 90 nodes (12.8%) — Tập trung tại các khối xử lý khóa bi quan chống race condition, các Celery tasks ngầm, cấu hình Django Admin có Inline và các models cốt lõi (`Book`, `LibraryBus`, `BorrowRecord`).

---

## PHẦN 3: THUYẾT MINH CHI TIẾT 18 LOẠI QUAN HỆ KIẾN TRÚC PHÂN CẤP

Đồ thị ghi nhận tổng cộng **1.303 cạnh liên kết có hướng**:

| STT | Loại quan hệ (`type`) | Số lượng | Tỷ lệ | Cặp đỉnh (Source ➔ Target) | Cơ chế kỹ thuật |
| :---: | :--- | :---: | :---: | :--- | :--- |
| **1** | `contains` | **467** | 35.84% | File ➔ Class / Function | Cú pháp khai báo `class X:` / `def y():` |
| **2** | `exports` | **467** | 35.84% | File ➔ Class / Function | Quan hệ đối ứng cung cấp đối tượng ra ngoài |
| **3** | `renders` | **97** | 7.44% | Python View ➔ HTML Template | `render(request, template, context)` |
| **4** | `extends` | **96** | 7.37% | HTML Template ➔ HTML Template | Cú pháp DTL `{% extends "base.html" %}` |
| **5** | `imports` | **83** | 6.37% | Python File ➔ Python File | `from app.models import ModelName` |
| **6** | `migrates` | **19** | 1.46% | Migration File ➔ Model File | Django Migration Operations (`CreateModel`) |
| **7** | `package_init` | **15** | 1.15% | `__init__.py` ➔ AppConfig | Khởi tạo module và nạp cấu hình app |
| **8** | `loads_asset` | **12** | 0.92% | HTML Template ➔ CSS / JS | Cú pháp DTL `{% static "css/..." %}` |
| **9** | `tested_by` | **11** | 0.84% | Model / Service ➔ Test Script | Bộ kiểm thử tự động & Stress Test |
| **10** | `documents` | **10** | 0.77% | Document ➔ `settings.py` | Tài liệu kỹ thuật Markdown neo vào cấu hình |
| **11** | `configures` | **8** | 0.61% | Config File ➔ `settings.py` | `pyproject.toml`, `requirements.txt`, `.env` |
| **12** | `routes_to` | **6** | 0.46% | Root URLconf ➔ App URLconf | `path('subpath/', include('app.urls'))` |
| **13** | `script_for` | **5** | 0.38% | CLI Script ➔ `manage.py` | Kịch bản vận hành nạp `django.setup()` |
| **14** | `deploys` | **3** | 0.23% | Dockerfile / Compose ➔ `manage.py` | Chỉ thị đóng gói và khởi chạy container |
| **15** | `triggers` | **1** | 0.08% | GitHub Actions ➔ `tests.py` | Tự động kích hoạt CI/CD khi push code |
| **16** | `listens_to` | **1** | 0.08% | `signals.py` ➔ `models.py` | Observer Pattern `@receiver(post_save)` |
| **17** | `bootstraps` | **1** | 0.08% | `asgi.py` ➔ `settings.py` | Khởi tạo ASGI application cho Async |
| **18** | `configures_admin`| **1** | 0.08% | `admin.py` ➔ `models.py` | `admin.site.register(Model)` |
| **Σ** | **18 Loại** | **1.303** | **100%** | — | — |

---

## PHẦN 4: PHÂN TÍCH SÂU 6 TẦNG VÒNG TRÒN ĐỒNG TÂM

| Vòng (Ring) | Bán kính | Mã màu | Quy mô | Đặc tả trách nhiệm kiến trúc |
| :--- | :---: | :---: | :---: | :--- |
| **Vòng 1: Core & Config** | $140\text{ px}$ | Sky Cyan (`#38BDF8`) | 30 tệp | Trọng tâm hệ thống: `settings.py`, `manage.py`, `celery.py`, `AuditMixin`, `SoftDeleteModel`, `BaseQuerySet`. |
| **Vòng 2: Models & DB** | $270\text{ px}$ | Emerald Green (`#10B981`) | 32 tệp | Mô hình dữ liệu ORM chuẩn 3NF: `Book`, `LibraryBus`, `Profile`, `BorrowRecord`. Tối ưu hóa truy vấn chống $N+1$. |
| **Vòng 3: Services & Tasks** | $390\text{ px}$ | Amber Orange (`#F59E0B`) | 7 tệp | Tầng nghiệp vụ giao dịch mượn/trả, khóa bi quan `select_for_update`, Celery tasks chạy ngầm, Google Gemini AI. |
| **Vòng 4: Views & Admin** | $520\text{ px}$ | Indigo Blue (`#6366F1`) | 32 tệp | Tầng điều phối HTTP, định tuyến URL, phân quyền người dùng RBAC, Django Forms xác thực dữ liệu. |
| **Vòng 5: Testing & QA** | $650\text{ px}$ | Violet Purple (`#8B5CF6`) | 20 tệp | Bộ kiểm thử tự động toàn diện: Unit Tests, Integration Tests, Stress QA 100 luồng và tài liệu đặc tả. |
| **Vòng 6-7: Templates & UI** | $780 - 920\text{ px}$ | Hot Pink (`#EC4899`) | 114 tệp | Tầng giao diện người dùng ngoài cùng: 114 HTML templates xếp so le 2 quỹ đạo, bảng màu Neo-Bakery, PDF Viewer. |

---

## PHẦN 5: CHI TIẾT 7 PHÂN HỆ NGHIỆP VỤ (DJANGO APPS)

1. **Phân hệ Core (Nền tảng hạ tầng chia sẻ)**:
   * `CacheMixin`: Cơ chế Cache Versioning thông minh. Tự động tăng version key để vô hiệu hóa cache cũ mà không gây nghẽn Redis; bỏ qua các cập nhật trường nhỏ (`view_count`, `last_activity`) để duy trì hit-rate.
   * `SoftDeleteModel`: Xóa mềm bằng cờ `is_deleted = True`, bảo vệ tính toàn vẹn quan hệ khóa ngoại.
   * `AuditMixin`: Tự động theo dõi `created_by`, `modified_by`.
2. **Phân hệ Users (Độc giả, Phân quyền & Hội viên VIP)**:
   * Thuật toán băm mật khẩu Argon2 siêu an toàn.
   * Model `Profile`: Cấp bậc thẻ hội viên (Standard, Silver, Gold, VIP), điểm thưởng và hạn mức mượn tối đa (`borrow_limit`).
   * Phân quyền RBAC: Độc giả, Thủ thư, Tài xế xe buýt, Quản trị viên.
3. **Phân hệ Inventory (Kho sách & Đội xe buýt lưu động)**:
   * Model `Book`: Quản lý ISBN, tồn kho trên từng xe, tệp đọc thử PDF.
   * Model `LibraryBus` & `BusRoute`: Lộ trình trạm dừng định vị GPS.
   * Trình đọc sách điện tử PDF Viewer trực tuyến.
4. **Phân hệ Transactions (Mượn trả & Chống Race Condition)**:
   * Khóa bi quan `select_for_update()` ngăn chặn mượn trùng sách khi có tranh chấp đồng thời.
   * Hàng đợi đặt trước FIFO (`BookReservation`).
   * Tính tiền phạt trễ hạn (`FinePayment`) và đơn giao sách (`ShippingRequest`).
5. **Phân hệ Analytics (Thống kê số liệu & Trí tuệ nhân tạo Gemini)**:
   * Bảng vàng độc giả (Leaderboard), thống kê thể loại yêu thích.
   * Tích hợp Google Gemini AI sinh gợi ý 5 cuốn sách phù hợp nhất cho từng cá nhân.
6. **Phân hệ Notifications (Thông báo đa kênh)**:
   * In-app badge trên thanh điều hướng qua Context Processor.
   * Celery tasks gửi email tự động nhắc hẹn trả sách trước 1 ngày.
7. **Phân hệ Blog (Cổng truyền thông & Tương tác cộng đồng)**:
   * Bài viết tin tức văn hóa đọc, bình luận, đánh giá 5 sao.
   * Hệ thống bản tin Newsletter định kỳ.

---

## PHẦN 6: LỘ TRÌNH KHÁM PHÁ KIẾN TRÚC 7 BƯỚC (THE 7-STEP GUIDED TOUR)
*(Mỗi bước được thuyết minh chi tiết xấp xỉ 100 chữ)*

```
[1. Tổng quan Monolith] ➔ [2. Điểm vào & Cấu hình] ➔ [3. Tầng dữ liệu cốt lõi]
                                                               ⬇
[7. Kiểm thử & QA] ⬅ [6. Giao diện & Template] ⬅ [5. Celery & Redis] ⬅ [4. Giao dịch & Race Condition]
```

### 📍 Bước 1: Tổng quan dự án & Cấu trúc Monolith (Tài liệu nền tảng)
Bước mở đầu của hành trình dẫn dắt người xem tiếp cận bức tranh toàn cảnh về kiến trúc hệ thống thông qua hai tệp tài liệu kỹ thuật cốt lõi là `PROJECT_STRUCTURE.md` và `README.md`. Tại đây, dự án được định hình rõ nét theo mô hình High-Performance Django Modular Monolith, phân định ranh giới nghiệp vụ độc lập giữa 7 phân hệ chuyên biệt. Thay vì phân tán phức tạp như microservices hay rối ren như monolith truyền thống, kiến trúc này kết hợp sức mạnh xử lý giao dịch tập trung với khả năng đóng gói module hóa sạch sẽ. Điều này giúp các thành viên mới nhanh chóng nắm bắt luồng chảy thông tin tổng thể, tiêu chuẩn công nghệ (Django 5.2, MySQL 8.0, Redis 7, Celery 5.5) và triết lý thiết kế hệ thống chỉ trong vài phút đầu tiên.

### 📍 Bước 2: Điểm vào hệ thống & Cấu hình tập trung (Khởi tạo Runtime)
Bước thứ hai tập trung vào cổng khởi động và bộ não điều khiển toàn cục của ứng dụng, đại diện bởi ba tệp: `manage.py`, `settings.py` và `urls.py` gốc. Tệp `manage.py` đóng vai trò là cửa ngõ giao tiếp dòng lệnh (CLI Gateway) để thiết lập biến môi trường và nạp runtime Django. Tiếp đó, `settings.py` cấu hình toàn bộ hạ tầng then chốt: kết nối CSDL MySQL 8.0 với pool kết nối tối ưu, bộ nhớ đệm phân tán Redis 7, thuật toán băm mật khẩu Argon2 siêu an toàn và đăng ký 7 ứng dụng nghiệp vụ. Cuối cùng, `urls.py` gốc đóng vai trò nhạc trưởng điều phối mạng lưới phân tuyến cấp cao, phân nhánh lưu lượng truy cập tới 6 nhánh URL con thông qua cú pháp `include()` mô-đun hóa.

### 📍 Bước 3: Tầng dữ liệu cốt lõi (Core & Models 3NF)
Bước thứ ba đưa người xem thâm nhập vào tầng cấu trúc dữ liệu quan hệ chuẩn 3NF thông qua các tệp `models.py` của `core`, `inventory`, `transactions` và `users`. Nền tảng hạ tầng dùng chung tại `core/models.py` cung cấp các giải pháp tối ưu vượt trội: `CacheMixin` với cơ chế Versioning thông minh giúp vô hiệu hóa bộ nhớ đệm tự động mà không gây nghẽn Redis, `SoftDeleteModel` bảo vệ tính toàn vẹn quan hệ khóa ngoại khi xóa bản ghi, và `AuditMixin` ghi vết lịch sử tự động. Tại các miền nghiệp vụ, các mô hình thực thể như `Book`, `LibraryBus`, `Profile` và `BorrowRecord` được thiết lập chỉ mục (index) chặt chẽ, tối ưu hóa truy vấn chống lỗi N+1 và liên kết mạch lạc với nhau.

### 📍 Bước 4: Tầng nghiệp vụ giao dịch & Chống Race Condition (Khóa bi quan)
Bước thứ tư khám phá trái tim xử lý nghiệp vụ tại `transactions/services.py` và `transactions/views.py`, nơi giải quyết triệt để bài toán xung đột dữ liệu đồng thời khi nhiều độc giả cùng mượn một cuốn sách duy nhất. Thay vì phó mặc cho ORM thông thường, hệ thống triển khai giải thuật khóa bi quan (`select_for_update`) kết hợp khối `transaction.atomic()` của MySQL. Khi một giao dịch đang diễn ra, bản ghi cuốn sách và hạn mức người dùng bị khóa ở cấp độ dòng (row-level lock), buộc các tiến trình khác phải chờ. Nếu sách hết, hệ thống tự động định tuyến độc giả vào hàng đợi giữ chỗ FIFO (`BookReservation`). Tác vụ phụ chỉ kích hoạt qua hook `transaction.on_commit()`, loại trừ hoàn toàn rủi ro âm kho sách.

```python
# Minh họa giải thuật khóa bi quan chống Race Condition trong transactions/services.py:
with transaction.atomic():
    # 1. Khóa bản ghi cuốn sách ngay tại CSDL MySQL (Pessimistic Row-Level Lock)
    book = Book.objects.select_for_update().get(pk=book.pk)
    if not book.is_available:
        raise ValidationError("Sách không còn khả dụng để mượn")
    
    # 2. Khóa luôn người dùng để tránh mượn vượt quá hạn mức đồng thời (TOCTOU Race)
    User.objects.select_for_update().get(pk=user.pk)
    active_count = BorrowRecord.objects.filter(user=user, return_date__isnull=True).count()
    if active_count >= user.profile.borrow_limit:
        raise ValidationError("Người dùng đã đạt giới hạn mượn sách")
    
    # 3. Tạo phiếu mượn và cập nhật trạng thái kho
    borrow = BorrowRecord.objects.create(user=user, book=book, ...)
    book.change_status('checked_out')
    
    # 4. Kích hoạt task ngầm sau khi commit DB thành công
    transaction.on_commit(trigger_borrow_analytics)
```

### 📍 Bước 5: Xử lý bất đồng bộ với Celery & Redis (Tác vụ nền & Gemini AI)
Bước thứ năm làm sáng tỏ cơ chế giải phóng tài nguyên máy chủ Web thông qua hệ sinh thái xử lý tác vụ nền Celery 5.5 và Message Broker Redis 7 tại `transactions/tasks.py` và `analytics/tasks.py`. Hệ thống tách rời các công việc tốn thời gian ra khỏi vòng đời HTTP Request: bộ lập lịch Celery Beat tự động quét các phiếu mượn quá hạn lúc 00:00 hàng đêm để tính phạt trễ, và gửi email nhắc hẹn lúc 08:00 sáng. Đặc biệt, phân hệ Analytics kích hoạt các tác vụ AI chạy ngầm gọi API Google Gemini (`gemini-1.5-flash`), phân tích lịch sử đọc sách để sinh danh sách gợi ý cá nhân hóa và gửi thông báo in-app đến độc giả mà không gây gián đoạn trải nghiệm người dùng.

### 📍 Bước 6: Giao diện người dùng & Kiến trúc Template (Neo-Bakery & GSAP)
Bước thứ sáu đưa người xem ra tầng ngoại vi của hệ thống với hơn 70 giao diện mẫu HTML, đại diện bởi `template/base.html` và `book_list.html`. Toàn bộ giao diện kế thừa layout chuẩn từ `base.html` qua ngôn ngữ mẫu Django Template Language, đảm bảo tính nhất quán tuyệt đối về cấu trúc và điều hướng. Tầng hiển thị áp dụng hệ thống thiết kế độc bản Neo-Bakery Design System với bảng màu 6 tông ấm áp (mật ong, bơ nướng, cà phê đậm), kết hợp phông chữ hiện đại Plus Jakarta Sans. Đặc biệt, thư viện hoạt ảnh GSAP 3.x (ScrollTrigger và hiệu ứng nghiêng 3D micro-tilt) giúp giao diện đạt tốc độ phản hồi 60 FPS mượt mà, tích hợp trình đọc PDF và bản đồ trạm xe GPS sống động.

### 📍 Bước 7: Đảm bảo chất lượng & Bộ kiểm thử tự động (Stress QA & CI/CD)
Bước cuối cùng khẳng định độ tin cậy và sự vững chắc của toàn bộ kiến trúc thông qua mạng lưới kiểm thử tự động tại `core/tests.py`, `transactions/tests.py`, `functional_test.py` và kịch bản `test_race_condition.py`. Hệ thống sở hữu bộ test suite bao quát từ Unit Test các Mixin/Manager, Integration Test luồng mượn trả đến kịch bản kiểm thử áp lực đa luồng mô phỏng 100 threads đồng thời cùng tranh chấp tài nguyên. Mọi kịch bản đều chứng minh hệ thống không bao giờ xảy ra lỗi dữ liệu (zero negative inventory). Toàn bộ quy trình này được tích hợp vào pipeline GitHub Actions CI/CD (`ci.yml`), tự động kích hoạt kiểm tra nghiêm ngặt mỗi khi có commit mới, đảm bảo chất lượng phần mềm luôn đạt chuẩn trước khi release.

---

## PHẦN 7: CÁC TÍNH NĂNG TƯƠNG TÁC CHUYÊN SÂU TRÊN DASHBOARD
1. **App Filter Bar**: Cô lập đồ thị theo từng phân hệ hoặc xem toàn cảnh.
2. **Instant Search Box**: Tìm kiếm tức thì theo tên file, model, view, hàm; tự động phóng to (Scale $1.3\times$) và căn giữa (Focus Animation $500\text{ ms}$).
3. **Inspector Panel**: Thanh chi tiết hiển thị tóm tắt nghiệp vụ và danh sách liên kết 2 chiều: *Được tham chiếu bởi ($\leftarrow$)* và *Kết nối / Trực thuộc ($\rightarrow$)* kèm cơ chế drill-down traversal.
4. **Mật độ nhãn & Lọc Templates**: Tùy biến ẩn/hiện nhãn và ẩn 114 template để tối ưu không gian phân tích backend.
5. **Vòng quỹ đạo phát sáng**: Hook Canvas `beforeDrawing` vẽ các đường nét đứt phát sáng và watermark tên tầng.

---

## PHẦN 8: HƯỚNG DẪN VẬN HÀNH, BẢO TRÌ & CẬP NHẬT DỮ LIỆU
1. **Khởi chạy**: Nhấp đúp chuột vào tệp [understand_dashboard.html](file:///c:/Users/ADMIN/Documents/prj/understand_dashboard.html) trên máy tính để mở trên Chrome, Edge, Firefox mà không cần web server.
2. **Cập nhật dữ liệu khi codebase thay đổi**: Chạy kịch bản phân tích mã nguồn để xuất chuỗi JSON mới và dán vào giữa cặp thẻ:
   ```html
   <script id="ua-graph-data" type="application/json">
     /* Dán JSON mới tại đây */
   </script>
   ```
3. **Hiệu năng**: Giữ nguyên `physics: { enabled: false }` để đồ thị luôn ổn định theo cấu trúc vòng tròn đồng tâm.
