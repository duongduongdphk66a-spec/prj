import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import UserNotification, get_user_unread_count

@login_required
def notification_list(request):
    """Hiển thị danh sách thông báo của người dùng đã đăng nhập."""
    notifications_qs = UserNotification.objects.filter(recipient=request.user)
    
    # Simple filtering
    search_term = request.GET.get('search')
    if search_term:
        notifications_qs = notifications_qs.filter(
            Q(title__icontains=search_term) | Q(message__icontains=search_term)
        )

    paginator = Paginator(notifications_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'notifications': page_obj,
        'unread_count': get_user_unread_count(request.user.id),
    }
    return render(request, 'notifications/notification_list.html', context)


@login_required
def notification_detail(request, pk):
    """Hiển thị chi tiết một thông báo và đánh dấu là đã đọc."""
    notification = get_object_or_404(UserNotification, pk=pk, recipient=request.user)
    if not notification.is_read:
        notification.mark_as_read()
    
    context = {'notification': notification}
    return render(request, 'notifications/notification_detail.html', context)


@login_required
@require_POST
def mark_notification_read(request, pk):
    """API endpoint để đánh dấu một thông báo là đã đọc."""
    notification = get_object_or_404(UserNotification, pk=pk, recipient=request.user)
    if not notification.is_read:
        notification.mark_as_read()
    
    return JsonResponse({
        'status': 'success',
        'unread_count': get_user_unread_count(request.user.id)
    })


@login_required
@require_POST
def mark_all_read(request):
    """API endpoint để đánh dấu tất cả thông báo là đã đọc."""
    count = UserNotification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True, 
        read_at=timezone.now()
    )
    # Clear cache
    from django.core.cache import cache
    cache.delete(f"unread_count_{request.user.id}")
    return JsonResponse({'status': 'success', 'marked_count': count})
