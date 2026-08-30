from .models import get_user_unread_count

def unread_notifications(request):
    if request.user.is_authenticated:
        return {'unread_notifications_count': get_user_unread_count(request.user.id)}
    return {'unread_notifications_count': 0}

