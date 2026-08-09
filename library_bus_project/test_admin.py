import django
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_bus_project.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from transactions.models import ShippingRequest

c = Client(SERVER_NAME='127.0.0.1')
admin = User.objects.get(username='admin')
c.force_login(admin)

obj = ShippingRequest.objects.get(pk='cba1f41c-18de-4967-a546-b4760f30c263')

data = {
    'user': obj.user_id,
    'book': obj.book_id,
    'borrow_record': obj.borrow_record_id,
    'status': 'delivered',
    'recipient_name': 'mvh',
    'phone_number': '0985441735',
    'shipping_address': 'Đơn giao hàng',
    'shipping_fee': 0,
    'initial-shipping_fee': 0,
    '_save': 'Save'
}

response = c.post(f'/admin/transactions/shippingrequest/{obj.pk}/change/', data)
print(response.status_code)

import re
errors = re.findall(r'<ul class="errorlist">(.*?)</ul>', response.content.decode(), re.DOTALL)
for err in errors:
    print("ERROR:", err.strip())
