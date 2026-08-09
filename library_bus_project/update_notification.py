import sys
import re

with open('transactions/services.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add import for UserNotification if not present
if 'UserNotification' not in content:
    content = content.replace('from .models import BorrowRecord', 'from notifications.models import UserNotification\nfrom .models import BorrowRecord')

new_method = '''    @staticmethod
    def notify_admin_new_shipping_request(shipping_request) -> bool:
        """Gửi thông báo yêu cầu giao sách mới cho admin (qua web)"""
        try:
            admins = User.objects.filter(is_staff=True, is_active=True)
            if not admins.exists():
                return False
                
            title = f'Yêu cầu giao sách mới: {shipping_request.book.title}'
            message = f"""Người yêu cầu: {shipping_request.user.username}
Người nhận: {shipping_request.recipient_name}
SĐT: {shipping_request.phone_number}
Địa chỉ: {shipping_request.shipping_address}
Ghi chú: {shipping_request.delivery_notes}"""

            for admin in admins:
                UserNotification.objects.create(
                    recipient=admin,
                    title=title,
                    message=message,
                    notification_type='warning',
                    action_url=f'/admin/transactions/shippingrequest/{shipping_request.id}/change/'
                )
            
            logger.info(f"Đã gửi thông báo web cho admin về yêu cầu giao sách {shipping_request.id}")
            return True
        except Exception as e:
            logger.error(f"Lỗi gửi thông báo web cho admin: {e}")
            return False'''

# We need to replace the old notify_admin_new_shipping_request
pattern = r'    @staticmethod\n    def notify_admin_new_shipping_request\(.*?\).*?return False'
content = re.sub(pattern, new_method, content, flags=re.DOTALL)

with open('transactions/services.py', 'w', encoding='utf-8') as f:
    f.write(content)
