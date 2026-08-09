# File: users/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, Prefetch
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, UpdateView, CreateView
from django.urls import reverse_lazy, reverse
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from datetime import datetime, timedelta
import json
import logging
from .models import Profile, UserInterest, LoginHistory, UserPreference, UserRole
from .forms import (UserRegistrationForm, UserLoginForm, UserUpdateForm, ProfileUpdateForm, 
                   UserInterestForm, UserPreferenceForm, PasswordChangeForm, 
                   EmailVerificationForm, CustomPasswordResetForm, MembershipUpgradeForm)
from .utils import get_client_ip, get_user_agent_info, send_verification_email

logger = logging.getLogger(__name__)

# =========== ===================================================================
# AUTHENTICATION VIEWS
# ==============================================================================

def register_view(request):
    """Đăng ký tài khoản với validation nâng cao"""
    if request.user.is_authenticated:
        return redirect('users:dashboard')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    user.set_password(form.cleaned_data['password'])
                    user.is_active = True
                    user.save()
                    
                    # Ghi log đăng ký
                    logger.info(f"New user registered: {user.username}")
                    
                    # Gửi email xác thực
                    try:
                        send_verification_email(user)
                        messages.success(request, 'Đăng ký thành công! Vui lòng kiểm tra email để xác thực tài khoản.')
                    except Exception as e:
                        logger.error(f"Error sending verification email: {e}")
                        messages.warning(request, 'Đăng ký thành công nhưng không thể gửi email xác thực.')
                    
                    return redirect('users:login')
            except Exception as e:
                logger.error(f"Registration error: {e}")
                messages.error(request, 'Có lỗi xảy ra khi đăng ký. Vui lòng thử lại.')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'users/register.html', {'form': form})

def login_view(request):
    """Đăng nhập với hỗ trợ email và tracking"""
    if request.user.is_authenticated:
        return redirect('users:dashboard')
    
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            # Ghi log đăng nhập
            ip_address = get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            device_info = get_user_agent_info(user_agent)
            LoginHistory.objects.create(
                user=user, ip_address=ip_address, user_agent=user_agent,
                device_info=device_info, is_successful=True
            )
            
            # Cập nhật thông tin profile
            if hasattr(user, 'profile'):
                user.profile.last_login_ip = ip_address
                user.profile.login_count += 1
                user.profile.save(update_fields=['last_login_ip', 'login_count'])
            
            # Xử lý remember me
            if form.cleaned_data.get('remember_me'):
                request.session.set_expiry(settings.SESSION_COOKIE_AGE)
            else:
                request.session.set_expiry(0)
            
            messages.success(request, f'Chào mừng {user.get_full_name() or user.username}!')
            
            # Redirect đến trang được yêu cầu hoặc dashboard
            next_url = request.GET.get('next', 'users:dashboard')
            return redirect(next_url)
        else:
            # Ghi log đăng nhập thất bại
            username = request.POST.get('username', '')
            if username:
                try:
                    user = User.objects.get(Q(username=username) | Q(email=username))
                    LoginHistory.objects.create(
                        user=user, ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', ''),
                        is_successful=False
                    )
                except User.DoesNotExist:
                    pass
            messages.error(request, 'Thông tin đăng nhập không đúng.')
    else:
        form = UserLoginForm()
    
    return render(request, 'users/login.html', {'form': form})

@login_required
def logout_view(request):
    """Đăng xuất với thông báo"""
    username = request.user.username
    logout(request)
    messages.success(request, f'Đã đăng xuất thành công. Tạm biệt {username}!')
    return redirect('users:login')

# ==============================================================================
# PROFILE VIEWS
# ==============================================================================

@login_required
def profile_view(request):
    """Hiển thị profile cá nhân"""
    profile = get_object_or_404(Profile, user=request.user)
    recent_activities = request.user.login_history.order_by('-created_at')[:5]
    reading_stats = profile.reading_stats_summary
    
    active_borrows = request.user.borrow_records.filter(return_date__isnull=True).select_related('book')
    active_reservations = request.user.reservations.filter(is_fulfilled=False).select_related('book')
    
    context = {
        'profile': profile,
        'recent_activities': recent_activities,
        'reading_stats': reading_stats,
        'completion_percentage': profile.completion_percentage,
        'active_borrows': active_borrows,
        'active_reservations': active_reservations,
    }
    return render(request, 'users/profile.html', context)

@login_required
def profile_edit(request):
    """Chỉnh sửa profile"""
    profile = get_object_or_404(Profile, user=request.user)
    
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user, user=request.user)
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            try:
                with transaction.atomic():
                    user_form.save()
                    profile_form.save()
                    messages.success(request, 'Cập nhật thông tin thành công!')
                    return redirect('users:profile')
            except Exception as e:
                logger.error(f"Profile update error: {e}")
                messages.error(request, 'Có lỗi xảy ra khi cập nhật.')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=profile)
    
    return render(request, 'users/profile_edit.html', {
        'user_form': user_form, 'profile_form': profile_form, 'profile': profile
    })

def profile_detail(request, username):
    """Xem profile công khai của user khác"""
    user = get_object_or_404(User, username=username)
    profile = get_object_or_404(Profile, user=user)
    
    # Kiểm tra quyền xem
    if not profile.privacy_settings.get('public_profile', True) and user != request.user:
        messages.error(request, 'Hồ sơ này không công khai.')
        return redirect('users:user_list')
    
    context = {
        'profile': profile,
        'user_obj': user,
        'reading_stats': profile.reading_stats_summary,
        'interests': user.interests.all()[:10] if profile.privacy_settings.get('show_interests', True) else [],
    }
    return render(request, 'users/profile_detail.html', context)

# ==============================================================================
# SETTINGS VIEWS
# ==============================================================================

@login_required
def settings_view(request):
    """Trang cài đặt tổng quan"""
    return render(request, 'users/settings.html')

@login_required
def change_password(request):
    """Đổi mật khẩu"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            try:
                user = request.user
                user.set_password(form.cleaned_data['new_password'])
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Đổi mật khẩu thành công!')
                return redirect('users:settings')
            except Exception as e:
                logger.error(f"Password change error: {e}")
                messages.error(request, 'Có lỗi xảy ra khi đổi mật khẩu.')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'users/change_password.html', {'form': form})

@login_required
def preferences_view(request):
    """Cài đặt tùy chọn người dùng"""
    preferences, created = UserPreference.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = UserPreferenceForm(request.POST, instance=preferences)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cập nhật tùy chọn thành công!')
            return redirect('users:preferences')
    else:
        form = UserPreferenceForm(instance=preferences)
    
    return render(request, 'users/settings/preferences.html', {'form': form})

@login_required
def interests_view(request):
    """Quản lý sở thích"""
    interests = request.user.interests.all().order_by('interest_type', '-weight')
    
    if request.method == 'POST':
        form = UserInterestForm(request.POST)
        if form.is_valid():
            interest = form.save(commit=False)
            interest.user = request.user
            try:
                interest.save()
                messages.success(request, 'Thêm sở thích thành công!')
                return redirect('users:interests')
            except Exception as e:
                messages.error(request, 'Sở thích này đã tồn tại.')
    else:
        form = UserInterestForm()
    
    return render(request, 'users/settings/interests.html', {'form': form, 'interests': interests})

@login_required
@require_POST
def delete_interest(request, interest_id):
    """Xóa sở thích"""
    interest = get_object_or_404(UserInterest, id=interest_id, user=request.user)
    interest.delete()
    messages.success(request, 'Đã xóa sở thích.')
    return redirect('users:interests')

# ==============================================================================
# SOCIAL FEATURES
# ==============================================================================



class UserListView(ListView):
    """Danh sách người dùng với tìm kiếm và filter"""
    model = User
    template_name = 'users/user_list.html'
    context_object_name = 'users'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = User.objects.select_related('profile').filter(is_active=True)
        
        # Tìm kiếm
        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) | Q(first_name__icontains=search) | 
                Q(last_name__icontains=search) | Q(email__icontains=search) |
                Q(profile__city__icontains=search) | Q(profile__occupation__icontains=search)
            )
        
        # Filter theo thành phố
        city = self.request.GET.get('city')
        if city:
            queryset = queryset.filter(profile__city__iexact=city)
        
        # Filter theo membership
        membership = self.request.GET.get('membership')
        if membership:
            queryset = queryset.filter(profile__membership_level=membership)
        
        # Sắp xếp
        sort_by = self.request.GET.get('sort', 'username')
        if sort_by == 'join_date':
            queryset = queryset.order_by('-date_joined')
        elif sort_by == 'activity':
            queryset = queryset.order_by('-last_login')
        else:
            queryset = queryset.order_by('username')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('search', '')
        context['city'] = self.request.GET.get('city', '')
        context['membership'] = self.request.GET.get('membership', '')
        context['sort'] = self.request.GET.get('sort', 'username')
        
        # Danh sách thành phố cho filter (có cache)
        from django.core.cache import cache
        cities = cache.get('user_cities_list')
        if not cities:
            cities = list(Profile.objects.exclude(city='').values_list('city', flat=True).distinct())
            cache.set('user_cities_list', cities, 3600)  # Cache 1 giờ
        context['cities'] = cities
        
        return context

# ==============================================================================
# VERIFICATION & RECOVERY
# ==============================================================================

def verify_email(request, uidb64, token):
    """Xác thực email qua link"""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user and default_token_generator.check_token(user, token):
        if hasattr(user, 'profile'):
            user.profile.is_verified = True
            user.profile.save()
            messages.success(request, 'Email đã được xác thực thành công!')
            return redirect('users:login')
    
    messages.error(request, 'Link xác thực không hợp lệ hoặc đã hết hạn.')
    return redirect('users:login')

@login_required
def resend_verification(request):
    """Gửi lại email xác thực"""
    if request.user.profile.is_verified:
        messages.info(request, 'Tài khoản đã được xác thực.')
        return redirect('users:profile')
    
    try:
        send_verification_email(request.user)
        messages.success(request, 'Đã gửi lại email xác thực.')
    except Exception as e:
        logger.error(f"Resend verification error: {e}")
        messages.error(request, 'Không thể gửi email xác thực.')
    
    return redirect('users:profile')

def password_reset_request(request):
    """Yêu cầu reset mật khẩu"""
    if request.method == 'POST':
        form = CustomPasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email__iexact=email)
                # Gửi email reset password
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                reset_url = request.build_absolute_uri(
                    reverse('users:password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
                )
                
                send_mail(
                    subject='Đặt lại mật khẩu',
                    message=f'Nhấp vào link sau để đặt lại mật khẩu: {reset_url}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    html_message=render_to_string('users/password_reset_email.html', {
                        'user': user, 'reset_url': reset_url
                    })
                )
                messages.success(request, 'Đã gửi hướng dẫn đặt lại mật khẩu qua email.')
                return redirect('users:login')
            except Exception as e:
                logger.error(f"Password reset error: {e}")
                messages.error(request, 'Có lỗi xảy ra khi gửi email.')
    else:
        form = CustomPasswordResetForm()
    
    return render(request, 'users/password/password_reset_request.html', {'form': form})

# ==============================================================================
# AJAX VIEWS
# ==============================================================================

@login_required
def ajax_profile_stats(request):
    """API trả về thống kê profile"""
    profile = request.user.profile
    data = {
        'completion_percentage': profile.completion_percentage,
        'interests_count': request.user.interests.count(),
    }
    return JsonResponse(data)

@login_required
@require_POST
def ajax_update_avatar(request):
    """Cập nhật avatar qua AJAX"""
    if 'avatar' not in request.FILES:
        return JsonResponse({'error': 'Không có file được tải lên'}, status=400)
    
    try:
        profile = request.user.profile
        profile.avatar = request.FILES['avatar']
        profile.save()
        
        return JsonResponse({
            'success': True,
            'avatar_url': profile.avatar.url,
            'message': 'Cập nhật ảnh đại diện thành công!'
        })
    except Exception as e:
        logger.error(f"Avatar update error: {e}")
        return JsonResponse({'error': 'Có lỗi xảy ra khi cập nhật ảnh'}, status=500)



# ==============================================================================
# ADMIN/MANAGEMENT VIEWS
# ==============================================================================

@method_decorator(login_required, name='dispatch')
class UserManagementView(UserPassesTestMixin, ListView):
    """View quản lý user cho admin"""
    model = User
    template_name = 'users/user_management.html'
    context_object_name = 'users'
    paginate_by = 25
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.userrole_set.filter(role='admin').exists()
    
    def get_queryset(self):
        return User.objects.select_related('profile').prefetch_related('groups').order_by('-date_joined')

@login_required
def membership_upgrade(request):
    """Nâng cấp membership"""
    if request.method == 'POST':
        form = MembershipUpgradeForm(request.POST)
        if form.is_valid():
            # Logic xử lý nâng cấp membership
            level = form.cleaned_data['membership_level']
            duration = form.cleaned_data['duration_months']
            
            # Tạo payment record và xử lý thanh toán
            # Tạm thời chỉ update trực tiếp
            request.user.profile.membership_level = level
            request.user.profile.save()
            
            messages.success(request, f'Nâng cấp lên {level.upper()} thành công!')
            return redirect('users:profile')
    else:
        form = MembershipUpgradeForm()
    
    return render(request, 'users/membership_upgrade.html', {'form': form})

# ==============================================================================
# DASHBOARD & ANALYTICS
# ==============================================================================

@login_required
def dashboard_view(request):
    """Dashboard cá nhân"""
    active_borrows = request.user.borrow_records.filter(return_date__isnull=True).select_related('book')
    active_reservations = request.user.reservations.filter(is_fulfilled=False).select_related('book')
    
    context = {
        'user': request.user,
        'profile': request.user.profile,
        'recent_activities': request.user.login_history.order_by('-created_at')[:5],
        'reading_stats': request.user.profile.reading_stats_summary,
        'completion_percentage': request.user.profile.completion_percentage,
        'active_borrows': active_borrows,
        'active_reservations': active_reservations,
    }
    return render(request, 'users/dashboard.html', context)

@login_required
def activity_history(request):
    """Lịch sử hoạt động"""
    activities = request.user.login_history.order_by('-created_at')
    paginator = Paginator(activities, 20)
    page = request.GET.get('page')
    activities = paginator.get_page(page)
    
    return render(request, 'users/activity_history.html', {'activities': activities})

@login_required
def export_profile_data(request):
    """Xuất dữ liệu profile (GDPR compliance)"""
    profile = request.user.profile
    data = {
        'user_info': {
            'username': request.user.username,
            'email': request.user.email,
            'full_name': request.user.get_full_name(),
            'date_joined': request.user.date_joined.isoformat(),
            'last_login': request.user.last_login.isoformat() if request.user.last_login else None,
        },
        'profile_info': {
            'phone_number': profile.phone_number,
            'city': profile.city,
            'district': profile.district,
            'date_of_birth': profile.date_of_birth.isoformat() if profile.date_of_birth else None,
            'gender': profile.get_gender_display(),
            'occupation': profile.occupation,
            'bio': profile.bio,
            'membership_level': profile.get_membership_level_display(),
            'is_verified': profile.is_verified,
        },
        'interests': [{'type': i.interest_type, 'value': i.interest_value, 'weight': i.weight} 
                     for i in request.user.interests.all()],
        'login_history': [{'date': h.created_at.isoformat(), 'ip': h.ip_address} 
                         for h in request.user.login_history.all()[:50]]
    }
    
    response = HttpResponse(json.dumps(data, indent=2, ensure_ascii=False), content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="profile_data_{request.user.username}.json"'
    return response