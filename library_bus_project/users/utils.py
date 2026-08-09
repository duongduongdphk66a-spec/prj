# File: users/utils.py
# Mô tả: Utility functions cho hệ thống người dùng
# ==============================================================================

import re
import json
import logging
import requests
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from user_agents import parse
from django.utils import timezone

logger = logging.getLogger(__name__)

def get_client_ip(request):
    """Lấy IP address thực của client"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_user_agent_info(user_agent_string):
    """Phân tích thông tin user agent"""
    if not user_agent_string:
        return {'browser': 'Unknown', 'os': 'Unknown', 'device': 'Unknown'}
    
    try:
        user_agent = parse(user_agent_string)
        return {
            'browser': f"{user_agent.browser.family} {user_agent.browser.version_string}",
            'os': f"{user_agent.os.family} {user_agent.os.version_string}",
            'device': user_agent.device.family,
            'is_mobile': user_agent.is_mobile,
            'is_tablet': user_agent.is_tablet,
            'is_pc': user_agent.is_pc,
        }
    except Exception as e:
        logger.error(f"Error parsing user agent: {e}")
        return {'browser': 'Unknown', 'os': 'Unknown', 'device': 'Unknown'}



def send_verification_email(user):
    """Gửi email xác thực tài khoản"""
    try:
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # Tạo URL xác thực (cần có domain trong settings)
        domain = getattr(settings, 'SITE_DOMAIN', 'localhost:8000')
        verify_url = f"http://{domain}{reverse('users:verify_email', kwargs={'uidb64': uid, 'token': token})}"
        
        context = {
            'user': user,
            'verify_url': verify_url,
            'site_name': getattr(settings, 'SITE_NAME', 'Library System'),
        }
        
        subject = 'Xác thực tài khoản'
        html_message = render_to_string('users/emails/verification_email.html', context)
        plain_message = render_to_string('users/emails/verification_email.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Verification email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending verification email to {user.email}: {e}")
        return False

def validate_vietnamese_phone(phone):
    """Validate số điện thoại Việt Nam"""
    if not phone:
        return False
    
    # Regex cho số điện thoại VN
    patterns = [
        r'^(0|\+84)[0-9]{9,10}$',  # Cơ bản
        r'^(03|05|07|08|09)[0-9]{8}$',  # Di động
        r'^(02)[0-9]{8,9}$',  # Cố định
    ]
    
    return any(re.match(pattern, phone) for pattern in patterns)

def format_phone_number(phone):
    """Format số điện thoại về dạng chuẩn"""
    if not phone:
        return phone
    
    # Loại bỏ khoảng trắng và ký tự đặc biệt
    phone = re.sub(r'[^\d+]', '', phone)
    
    # Chuyển đổi +84 thành 0
    if phone.startswith('+84'):
        phone = '0' + phone[3:]
    
    return phone

def generate_username_suggestions(first_name, last_name, email):
    """Tạo gợi ý username từ tên và email"""
    suggestions = []
    
    # Từ tên
    if first_name and last_name:
        suggestions.extend([
            f"{first_name.lower()}.{last_name.lower()}",
            f"{first_name.lower()}{last_name.lower()}",
            f"{last_name.lower()}.{first_name.lower()}",
        ])
    
    # Từ email
    if email and '@' in email:
        email_prefix = email.split('@')[0].lower()
        suggestions.append(email_prefix)
    
    # Loại bỏ ký tự đặc biệt
    cleaned_suggestions = []
    for suggestion in suggestions:
        cleaned = re.sub(r'[^a-zA-Z0-9._]', '', suggestion)
        if len(cleaned) >= 3:
            cleaned_suggestions.append(cleaned)
    
    return list(set(cleaned_suggestions))  # Loại bỏ trùng lặp

def check_password_strength(password):
    """Kiểm tra độ mạnh mật khẩu"""
    if len(password) < 8:
        return {'score': 0, 'message': 'Mật khẩu phải có ít nhất 8 ký tự'}
    
    score = 0
    messages = []
    
    # Kiểm tra các tiêu chí
    if re.search(r'[a-z]', password):
        score += 1
    else:
        messages.append('Cần có chữ thường')
    
    if re.search(r'[A-Z]', password):
        score += 1
    else:
        messages.append('Cần có chữ hoa')
    
    if re.search(r'[0-9]', password):
        score += 1
    else:
        messages.append('Cần có số')
    
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        score += 1
    else:
        messages.append('Cần có ký tự đặc biệt')
    
    # Tính điểm
    if score >= 4:
        return {'score': 4, 'message': 'Mật khẩu rất mạnh', 'level': 'strong'}
    elif score >= 3:
        return {'score': 3, 'message': 'Mật khẩu khá mạnh', 'level': 'good'}
    elif score >= 2:
        return {'score': 2, 'message': 'Mật khẩu trung bình', 'level': 'medium'}
    else:
        return {'score': 1, 'message': 'Mật khẩu yếu: ' + ', '.join(messages), 'level': 'weak'}

def sanitize_user_input(text, max_length=None):
    """Làm sạch input từ user"""
    if not text:
        return text
    
    # Loại bỏ HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Loại bỏ ký tự đặc biệt nguy hiểm
    text = re.sub(r'[<>"\']', '', text)
    
    # Trim và giới hạn độ dài
    text = text.strip()
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    return text

def calculate_profile_completion(profile):
    """Tính phần trăm hoàn thành profile"""
    required_fields = {
        'phone_number': 15,
        'date_of_birth': 10,
        'city': 10,
        'district': 5,
        'occupation': 10,
        'bio': 15,
        'avatar': 20,  # Kiểm tra khác default
        'gender': 5,
        'address': 10,
    }
    
    total_score = 0
    max_score = sum(required_fields.values())
    
    for field, score in required_fields.items():
        if field == 'avatar':
            if profile.avatar and profile.avatar.name != 'avatars/default.png':
                total_score += score
        else:
            if getattr(profile, field, None):
                total_score += score
    
    return round((total_score / max_score) * 100, 1)

def get_membership_benefits(level):
    """Lấy danh sách quyền lợi theo membership level"""
    benefits = {
        'basic': {
            'borrow_limit': 3,
            'borrow_duration': 14,
            'renewal_times': 1,
            'features': ['Mượn sách cơ bản', 'Đọc tại chỗ', 'Tìm kiếm sách'],
        },
        'premium': {
            'borrow_limit': 5,
            'borrow_duration': 21,
            'renewal_times': 2,
            'features': ['Mượn sách nâng cao', 'Đặt trước sách', 'Tư vấn sách', 'Thông báo sách mới'],
        },
        'vip': {
            'borrow_limit': 10,
            'borrow_duration': 30,
            'renewal_times': 3,
            'features': ['Mượn sách VIP', 'Ưu tiên đặt trước', 'Tư vấn cá nhân', 'Sự kiện độc quyền', 'Giao sách tận nơi'],
        },
    }
    
    return benefits.get(level, benefits['basic'])

def log_user_activity(user, action, details=None):
    """Ghi log hoạt động của user"""
    try:
        log_data = {
            'user_id': user.id,
            'username': user.username,
            'action': action,
            'details': details or {},
            'timestamp': str(timezone.now()),
        }
        
        logger.info(f"User activity: {json.dumps(log_data, ensure_ascii=False)}")
    except Exception as e:
        logger.error(f"Error logging user activity: {e}")

def check_user_permissions(user, permission_name):
    """Kiểm tra quyền của user"""
    if user.is_superuser:
        return True
    
    # Kiểm tra qua groups
    if user.groups.filter(permissions__codename=permission_name).exists():
        return True
    
    # Kiểm tra qua UserRole
    if hasattr(user, 'userrole_set'):
        roles = user.userrole_set.filter(
            valid_from__lte=timezone.now(),
            valid_to__isnull=True
        )
        # Logic kiểm tra permission theo role
        for role in roles:
            if permission_name in role.scope.get('permissions', []):
                return True
    
    return False

def send_notification_email(user, subject, template_name, context):
    """Gửi email thông báo chung"""
    try:
        # Kiểm tra cài đặt nhận email
        if hasattr(user, 'preferences') and not user.preferences.email_notifications:
            return False
        
        context.update({
            'user': user,
            'site_name': getattr(settings, 'SITE_NAME', 'Library System'),
        })
        
        html_message = render_to_string(f'users/emails/{template_name}.html', context)
        plain_message = render_to_string(f'users/emails/{template_name}.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Notification email sent to {user.email}: {subject}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending notification email: {e}")
        return False