# Page Override Specification: Landing Page (`index.html`)

> **Inherits from**: [MASTER.md](../MASTER.md)  
> **Route**: `/` (`index`)  
> **Pattern**: *Hero-Centric + Storytelling + Social Proof*  

---

## 1. Page Dial Overrides

- **`--variance: 8`**: Tăng độ biến thiên bố cục cho các khối Bento giới thiệu sách nổi bật và lộ trình xe buýt, tạo nhịp điệu thị giác hấp dẫn.
- **`--motion: 7`**: Tận dụng GSAP ScrollTrigger batching cho khối sách, hiệu ứng counter cho số liệu thống kê cộng đồng, và micro-parallax nhẹ nhàng ở Hero banner.
- **`--density: 3`**: Không gian thoáng đãng tối đa cho trải nghiệm văn học, khoảng cách giữa các phần đạt 64px - 96px.

---

## 2. Section Structure & Conversion Journey

1. **Hero Section (Above the fold)**:
   - Thông điệp: *"Mang Tri Thức Đến Mọi Nẻo Đường"*.
   - Call to Action kép: Nút chính *"Khám phá sách"* (`.btn-hero.primary`) & Nút phụ *"Lộ trình xe buýt"* (`.btn-hero.secondary`).
   - Kích thước chạm mobile: Tối thiểu 48px chiều cao.
2. **Impact Metrics Bar (Social Proof)**:
   - Các chỉ số: Số lượng sách, điểm dừng xe buýt, độc giả đã phục vụ, số chuyến xe đã lăn bánh.
   - Định dạng số: `tabular-nums` tránh giật layout khi số nhảy.
3. **Bento Grid: Tuyển Chọn Sách Nổi Bật**:
   - Thẻ Featured lớn (2 cột) kết hợp 4 thẻ phụ (1 cột).
   - Tỉ lệ ảnh bìa sách: `aspect-ratio: 2/3` chống layout shift (CLS).
4. **Live Fleet Map Preview**:
   - Bản đồ tương tác vị trí các xe buýt đang hoạt động và lịch dừng hôm nay.
5. **Community Story & Testimonials**:
   - Cảm nhận của bạn đọc, phụ huynh và học sinh tại các điểm dừng xe.
6. **Closing CTA & Newsletter Subscription**:
   - Form nhận lịch trình xe cập nhật hàng tuần qua email.
