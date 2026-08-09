import sys

new_method = """
    @staticmethod
    def notify_admin_new_shipping_request(shipping_request) -> bool:
        \"\"\"Gửi thông báo yêu cầu giao sách mới cho admin\"\"\"
        try:
            admins = User.objects.filter(is_staff=True, is_active=True)
            admin_emails = [admin.email for admin in admins if admin.email]
            if not admin_emails:
                return False
                
            subject = f'Yêu cầu giao sách mới: {shipping_request.book.title}'
            message = f'''Xin chào Admin,

Có một yêu cầu giao sách mới trên hệ thống:
- Người yêu cầu: {shipping_request.user.username}
- Sách: {shipping_request.book.title}
- Ngày yêu cầu: {shipping_request.created_at.strftime("%d/%m/%Y %H:%M") if hasattr(shipping_request, "created_at") else ""}

Thông tin giao hàng:
- Người nhận: {shipping_request.recipient_name}
- SĐT: {shipping_request.phone_number}
- Địa chỉ: {shipping_request.shipping_address}
- Ghi chú: {shipping_request.delivery_notes}

Vui lòng đăng nhập hệ thống để duyệt yêu cầu này.
'''
            send_mail(subject=subject, message=message, from_email='library@system.com', recipient_list=admin_emails, fail_silently=False)
            return True
        except Exception as e:
            logger.error(f"Lỗi gửi thông báo cho admin: {e}")
            return False
"""

with open('transactions/services.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'def notify_admin_new_shipping_request' not in content:
    content = content.replace('    @staticmethod\n    def send_shipping_update', new_method + '\n    @staticmethod\n    def send_shipping_update')
    with open('transactions/services.py', 'w', encoding='utf-8') as f:
        f.write(content)
