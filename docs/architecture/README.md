# Tài Liệu Kiến Trúc Hệ Thống Tủ Sách Lưu Động (Archify Architecture Hub)

Dự án áp dụng công cụ **[Archify](https://github.com/tt-a1i/archify)** để quản lý, biểu diễn và tự động biên dịch toàn bộ sơ đồ kiến trúc, quy trình nghiệp vụ và luồng dữ liệu của hệ sinh thái **Tủ Sách Lưu Động (Library Bus System)**.

---

## 1. Mục Tiêu & Lợi Ích Của Archify Trong Dự Án

- **Sơ đồ là Mã (Diagram-as-Code)**: Thay vì vẽ bằng các công cụ kéo thả thủ công dễ lỗi thời, kiến trúc được định nghĩa bằng **Typed JSON IR** (Intermediate Representation) có schema chặt chẽ, dễ dàng phiên bản hóa bằng Git (`git diff`, PR review).
- **Kiểm Định Tự Động 9 Tiêu Chí (Showcase Profile)**: Toàn bộ sơ đồ đều bắt buộc vượt qua 9 bài kiểm tra hình học và độ dễ đọc (orthogonal routing, label route clearance, no ambiguous corridors, no border runs, rhythm, finite SVG, desktop readability).
- **Trực Quan Hóa Tương Tác Cấp Cao**: Các file HTML sinh ra là các Single-File SVG ứng dụng tương tác hoàn chỉnh: hỗ trợ đổi góc nhìn (Views / Scenarios), animation dòng chảy tín hiệu (`trace`), zoom/pan mượt mà và chế độ tối (Dark mode) chuẩn phong cách **Neo-Bakery**.

---

## 2. Danh Mục Sơ Đồ Đã Triển Khai

| STT | Loại Sơ Đồ | File Định Nghĩa (JSON IR) | File HTML Biên Dịch | Mô Tả Nghiệp Vụ |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Architecture** | [`system-architecture.architecture.json`](./system-architecture.architecture.json) | [`system-architecture.html`](./system-architecture.html) | Kiến trúc tổng thể 10 thành phần: Django 5.2 Modular Monolith, Nginx Gateway, MySQL 8.0 ACID, Redis 7 (Cache DB1 + Broker DB0), Celery Worker/Beat và Gemini 1.5 Flash AI. |
| **2** | **Workflow** | [`borrowing-workflow.workflow.json`](./borrowing-workflow.workflow.json) | [`borrowing-workflow.html`](./borrowing-workflow.html) | Quy trình mượn sách mượt mà với 6 làn bơi (Lanes): Tra cứu, khóa bi quan `select_for_update` chống race-condition, xác thực vị trí GPS trạm xe bus, bàn giao tận tay và quét phạt trễ hạn 0h. |
| **3** | **Dataflow** | [`analytics-dataflow.dataflow.json`](./analytics-dataflow.dataflow.json) | [`analytics-dataflow.html`](./analytics-dataflow.html) | Luồng 5 giai đoạn: Thu thập giao dịch & GPS xe, hàng đợi Redis DB0, Celery Worker tính điểm uy tín bạn đọc, tổng hợp báo cáo tuyến xe và Gemini AI cá nhân hóa đề xuất sách. |
| **Portal**| **Hub Portal** | — | [`index.html`](./index.html) | Cổng giao diện Neo-Bakery tập trung chuyển đổi nhanh và xem trực tiếp cả 3 sơ đồ trong một khung nhìn tiện lợi. |

---

## 3. Hướng Dẫn Sử Dụng & Biên Dịch (CLI)

Bộ công cụ Archify đã được tích hợp cục bộ tại `.agents/skills/archify` cùng file điều phối nhanh `scripts/archify.mjs`.

### 3.1. Kiểm tra tính hợp lệ (Validation)
Kiểm tra sơ đồ theo tiêu chuẩn chất lượng cao nhất (`showcase`):

```bash
# Kiểm tra sơ đồ kiến trúc
node scripts/archify.mjs validate architecture docs/architecture/system-architecture.architecture.json --quality showcase

# Kiểm tra quy trình mượn sách
node scripts/archify.mjs validate workflow docs/architecture/borrowing-workflow.workflow.json --quality showcase

# Kiểm tra luồng dữ liệu phân tích
node scripts/archify.mjs validate dataflow docs/architecture/analytics-dataflow.dataflow.json --quality showcase
```

### 3.2. Biên dịch & Xuất bản Artifact (Delivery)
Xuất bản ra file HTML độc lập (tự chứa CSS, JS runtime, không phụ thuộc internet):

```bash
# Biên dịch Architecture
node scripts/archify.mjs deliver architecture docs/architecture/system-architecture.architecture.json docs/architecture/system-architecture.html --quality showcase

# Biên dịch Workflow
node scripts/archify.mjs deliver workflow docs/architecture/borrowing-workflow.workflow.json docs/architecture/borrowing-workflow.html --quality showcase

# Biên dịch Dataflow
node scripts/archify.mjs deliver dataflow docs/architecture/analytics-dataflow.dataflow.json docs/architecture/analytics-dataflow.html --quality showcase
```

---

## 4. Điểm Nhấn Kiến Trúc Trọng Tâm Của Dự Án

### 4.1. Giải pháp chống Race Condition khi mượn sách
Trong phân hệ `transactions/services.py`, hàm `create_borrow` áp dụng cơ chế khóa mức dòng (Pessimistic Locking):
```python
with transaction.atomic():
    book = Book.objects.select_for_update().get(pk=book.pk)
    User.objects.select_for_update().get(pk=user.pk)
    # Kiểm tra tính khả dụng và giới hạn mượn an toàn
    ...
```
Khóa này ngăn chặn tình huống 2 bạn đọc cùng thao tác mượn cuốn sách cuối cùng tại cùng một thời điểm.

### 4.2. Tách biệt Hàng Đợi & Bộ Đệm trên Redis
Hệ thống sử dụng Redis 7 với 2 database độc lập:
- **DB 0**: Celery Broker chuyên trách truyền tin nhắn cho các tác vụ nặng (gửi mail, tính tiền phạt quá hạn, tổng hợp analytics).
- **DB 1**: Bộ đệm danh mục sách hot, thông tin tuyến xe buýt và phiên đăng nhập của người dùng.

### 4.3. Tích hợp Trí Tuệ Nhân Tạo (Gemini 1.5 Flash)
Trợ lý AI được tích hợp tại phân hệ `ai_assistant` và `analytics`, phân tích lịch sử đọc sách và cấp độ thành viên (đồng, bạc, vàng, kim cương) để đưa ra các gợi ý tác phẩm phù hợp nhất trên ứng dụng di động của bạn đọc.
