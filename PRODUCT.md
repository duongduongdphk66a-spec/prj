# Product Specification — Tủ Sách Lưu Động (Library Bus)
<!-- Formalized following Impeccable Design System architecture (pbakaus/impeccable) -->

## Register
hybrid (brand + product)
- **Brand Surface**: Landing page, About, Blog, FAQ, Community book showcase.
- **Product Surface**: Inventory management, Bus fleet tracking, Book borrowing/reservation workflow, Donation pipelines, Metadata extraction dashboard.

## Users
- **Primary Readers**: Học sinh, sinh viên, độc giả trẻ tại các điểm dừng xe thư viện lưu động trên toàn thành phố Hà Nội và các tỉnh thành lân cận.
- **Librarians & Staff**: Cán bộ quản lý thư viện, thủ thư vận hành kiểm kê sách trên từng xe, xử lý mượn trả và điều phối tuyến xe.
- **Donors & Community**: Các cá nhân, tổ chức quyên góp sách và đóng góp bài viết chia sẻ văn hóa đọc.

## Product Purpose
Mang tri thức và sách giấy chất lượng cao đến tận tay độc giả thông qua mô hình xe buýt thư viện lưu động hiện đại kết hợp nền tảng số hóa quản lý thông minh.

## Brand Personality
**Cultured, Welcoming, Editorial** (Tri thức, Thân thiện, Tinh tế).
- **Tone of Voice**: Ấm áp, truyền cảm hứng đọc sách, rõ ràng, không dùng sáo ngữ công nghệ.
- **Design Metaphor**: Không gian tiệm sách ấm cúng kết hợp xe lưu động cổ điển (gỗ gụ sẫm, mật mía, bánh nướng, bơ mật ong và trang sách thơm mùi giấy).

## Typography Anchor
- **Display & Headings**: `Lora`, Georgia, serif — Kiểu chữ serif đương đại mang hơi thở thư viện, giàu tính thẩm mỹ văn học và nghệ thuật in ấn.
- **Body & Controls**: `Outfit`, sans-serif — Rõ ràng, thoáng đãng, hỗ trợ tối ưu hiển thị số liệu dạng tabular numbers trên giao diện số.

## Anti-References & Strict Bans
- ❌ **No AI Clichés**: Cấm hoàn toàn gradient tím-xanh generic (`#667eea` -> `#764ba2`).
- ❌ **No Untinted Darks**: Cấm dùng màu đen/xám thuần (`#000`, `#666`, `#888`); luôn nhuộm màu tối theo sắc mật mía (`#4E0705`) hoặc gỗ ấm.
- ❌ **No Card Soup**: Tránh lồng thẻ trong thẻ (Card in Card) không mục đích.
- ❌ **No Low-Contrast Text**: Đảm bảo độ tương phản WCAG AAA giữa chữ và nền ở cả Light & Dark mode.
