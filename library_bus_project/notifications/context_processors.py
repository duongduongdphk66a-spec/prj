from django.core.cache import cache
from .models import get_user_unread_count


def unread_notifications(request):
    if request.user.is_authenticated:
        user_id = request.user.id
        nav_ctx_key = f"user_nav_ctx_{user_id}"
        nav_ctx = cache.get(nav_ctx_key)
        if nav_ctx is None:
            theme = 'light'
            avatar_url = ''
            try:
                pref = getattr(request.user, 'preferences', None)
                if pref and pref.theme:
                    theme = pref.theme
            except Exception:
                pass
            try:
                prof = getattr(request.user, 'profile', None)
                if prof and prof.avatar and prof.avatar.name != 'avatars/default.png':
                    avatar_url = prof.avatar.url
            except Exception:
                pass
            nav_ctx = {'user_theme': theme, 'user_avatar_url': avatar_url}
            cache.set(nav_ctx_key, nav_ctx, 300)

        return {
            'unread_notifications_count': get_user_unread_count(user_id),
            'user_theme': nav_ctx['user_theme'],
            'user_avatar_url': nav_ctx['user_avatar_url'],
        }
    return {
        'unread_notifications_count': 0,
        'user_theme': 'light',
        'user_avatar_url': '',
    }

