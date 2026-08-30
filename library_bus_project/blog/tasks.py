# File: blog/tasks.py
from celery import shared_task
from django.db import transaction, connection
from django.core.cache import cache
from django.db.models import F, Avg, Count, Q, Max
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from datetime import timedelta, date
import logging
from django.contrib.contenttypes.models import ContentType

logger = logging.getLogger(__name__)

# ================== COMMENT TASKS ==================

@shared_task
def process_comment_moderation(comment_id):
    """
    Xử lý auto-moderation cho comment
    """
    try:
        from .models import Comment
        
        comment = Comment.objects.get(id=comment_id)
        
        # Tự động duyệt comment từ user đáng tin cậy
        if hasattr(comment.author, 'profile') and getattr(comment.author.profile, 'is_trusted', False):
            comment.is_approved = True
            comment.save(update_fields=['is_approved'])
            return True
            
        # Kiểm tra spam/toxic content (tích hợp với ML service)
        if check_content_quality(comment.content):
            comment.is_approved = True
            comment.save(update_fields=['is_approved'])
        else:
            # Gửi thông báo cho moderator
            notify_moderators_new_comment.delay(comment_id)
            
        logger.info(f"Processed moderation for comment {comment_id}")
        return True
        
    except Exception as exc:
        logger.error(f"Error processing comment moderation: {exc}")
        raise exc

@shared_task
def update_comment_thread_cache(post_id):
    """
    Cập nhật cache cho comment thread
    """
    try:
        from .models import Comment
        
        cache_key = f'comment_thread_{post_id}'
        
        # Xóa cache cũ
        cache.delete(cache_key)
        
        # Tạo cache mới
        comments = Comment.objects.filter(
            post_id=post_id,
            is_approved=True
        ).select_related('author', 'parent').prefetch_related('replies')
        
        cache.set(cache_key, list(comments), 1800)  # Cache 30 phút
        
        logger.info(f"Updated comment thread cache for post {post_id}")
        return len(comments)
        
    except Exception as exc:
        logger.error(f"Error updating comment thread cache: {exc}")
        raise exc

@shared_task
def notify_moderators_new_comment(comment_id):
    """
    Thông báo cho moderators về comment mới cần duyệt
    """
    try:
        from .models import Comment
        from django.contrib.auth.models import User
        
        comment = Comment.objects.select_related('author', 'post').get(id=comment_id)
        
        moderators = User.objects.filter(
            groups__name='Moderators',
            is_active=True
        ).values_list('email', flat=True)
        
        if not moderators:
            return False
            
        subject = f"Comment mới cần duyệt: {comment.post.title}"
        
        html_content = render_to_string('blog/emails/new_comment_moderation.html', {
            'comment': comment,
            'moderation_url': f"{settings.SITE_URL}/admin/blog/comment/{comment.id}/change/"
        })
        
        send_mail(
            subject=subject,
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=list(moderators),
            html_message=html_content
        )
        
        logger.info(f"Notified moderators about comment {comment_id}")
        return True
        
    except Exception as exc:
        logger.error(f"Error notifying moderators: {exc}")
        raise exc

# ================== MAINTENANCE TASKS ==================

@shared_task
def cleanup_orphaned_data():
    """
    Dọn dẹp dữ liệu không còn sử dụng
    """
    try:
        from .models import CommentLike
        
        # Xóa likes cho comments đã bị xóa
        orphaned_likes = CommentLike.objects.filter(
            comment__isnull=True
        ).delete()[0]
        
        logger.info(f"Cleaned up {orphaned_likes} orphaned likes")
        return orphaned_likes
        
    except Exception as exc:
        logger.error(f"Error cleaning up orphaned data: {exc}")
        raise exc

@shared_task
def rebuild_denormalized_fields():
    """
    Rebuild tất cả denormalized fields (chạy hàng tuần)
    """
    try:
        from .models import Comment
        
        # Rebuild comment likes count
        Comment.objects.all().update(
            likes_count=Count('likes')
        )
        
        logger.info("Rebuilt denormalized fields")
        return True
        
    except Exception as exc:
        logger.error(f"Error rebuilding denormalized fields: {exc}")
        raise exc

# ================== HELPER FUNCTIONS ==================

def check_content_quality(content):
    """
    Kiểm tra chất lượng nội dung (placeholder cho ML service)
    """
    banned_words = ['spam', 'fake', 'scam']
    return not any(word in content.lower() for word in banned_words)

@shared_task(max_retries=3)
def send_notification(recipient_id, actor_id, verb, target_id=None, target_model=None, action_object_id=None, action_object_model=None):
    """
    Tạo một thông báo trong ứng dụng một cách bất đồng bộ.
    """
    try:
        from notifications.models import create_notification
        
        recipient = User.objects.get(id=recipient_id)
        actor = User.objects.get(id=actor_id)

        if recipient == actor:
            return "Recipient and actor are the same, no notification created."

        related_object = None
        if action_object_id and action_object_model:
            app_label, model = action_object_model.split('.')
            ct = ContentType.objects.get(app_label=app_label, model=model)
            related_object = ct.get_object_for_this_type(id=action_object_id)
        elif target_id and target_model:
            app_label, model = target_model.split('.')
            ct = ContentType.objects.get(app_label=app_label, model=model)
            related_object = ct.get_object_for_this_type(id=target_id)
            
        create_notification(
            recipient=recipient,
            title=f"{actor.username} {verb}",
            message=f"{actor.username} {verb}",
            notification_type="community",
            related_object=related_object
        )
        logger.info(f"Sent notification to {recipient.username}")
        return True

    except User.DoesNotExist:
        logger.warning(f"Could not send notification. User not found.")
    except ContentType.DoesNotExist:
        logger.warning(f"Could not send notification. ContentType not found.")
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        raise e