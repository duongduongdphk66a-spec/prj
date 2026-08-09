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

# ================== BOOK REVIEW TASKS ==================

@shared_task(bind=True, max_retries=3)
def update_book_rating(self, book_id):
    """
    Cập nhật rating trung bình của sách và cache thống kê
    """
    try:
        from .models import BookReview
        from inventory.models import Book
        
        with transaction.atomic():
            # Lấy stats mới nhất
            stats = BookReview.objects.filter(
                book_id=book_id, 
                is_published=True
            ).aggregate(
                avg_rating=Avg('rating'),
                total_reviews=Count('id'),
                five_star=Count('id', filter=Q(rating=5)),
                four_star=Count('id', filter=Q(rating=4)),
                three_star=Count('id', filter=Q(rating=3)),
                two_star=Count('id', filter=Q(rating=2)),
                one_star=Count('id', filter=Q(rating=1))
            )
            
            # Cập nhật rating trong Book model
            if stats['avg_rating']:
                Book.objects.filter(id=book_id).update(
                    average_rating=stats['avg_rating'],
                    total_reviews=stats['total_reviews'],
                    updated_at=timezone.now()
                )
            
            # Cập nhật cache
            cache_key = f'book_stats_{book_id}'
            cache.set(cache_key, stats, 3600)  # Cache 1 giờ
            
            logger.info(f"Updated rating for book {book_id}: {stats['avg_rating']}")
            return stats
            
    except Exception as exc:
        logger.error(f"Error updating book rating {book_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)

@shared_task
def batch_update_helpfulness_scores(review_ids):
    """
    Cập nhật helpfulness score cho nhiều reviews cùng lúc
    """
    try:
        from .models import BookReview
        BookReview.batch_ops.bulk_update_helpfulness(review_ids)
        logger.info(f"Updated helpfulness scores for {len(review_ids)} reviews")
        return len(review_ids)
    except Exception as exc:
        logger.error(f"Error batch updating helpfulness scores: {exc}")
        raise exc

@shared_task
def moderate_reviews_batch(review_ids, action, moderator_id):
    """
    Duyệt/từ chối nhiều reviews cùng lúc
    """
    try:
        from .models import BookReview
        
        with transaction.atomic():
            updated = BookReview.objects.filter(
                id__in=review_ids,
                moderation_status='pending'
            ).update(
                moderation_status=action,
                moderated_by_id=moderator_id,
                updated_at=timezone.now()
            )
            
            # Cập nhật cache cho các sách liên quan
            book_ids = BookReview.objects.filter(
                id__in=review_ids
            ).values_list('book_id', flat=True).distinct()
            
            for book_id in book_ids:
                cache.delete(f'book_stats_{book_id}')
                update_book_rating.delay(book_id)
        
        logger.info(f"Moderated {updated} reviews with action: {action}")
        return updated
        
    except Exception as exc:
        logger.error(f"Error moderating reviews: {exc}")
        raise exc

@shared_task
def cleanup_old_review_votes():
    """
    Dọn dẹp các vote cũ (chạy hàng tuần)
    """
    try:
        from .models import ReviewHelpfulness
        
        cutoff_date = timezone.now() - timedelta(days=365)  # 1 năm
        deleted_count = ReviewHelpfulness.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old review votes")
        return deleted_count
        
    except Exception as exc:
        logger.error(f"Error cleaning up review votes: {exc}")
        raise exc

# ================== CHALLENGE TASKS ==================
# Note: Challenge tasks were removed as the ChallengeParticipation feature is not implemented.


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
        if comment.author.profile.is_trusted:
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

# ================== ANALYTICS TASKS ==================

@shared_task
def generate_daily_community_stats():
    """
    Tạo thống kê hàng ngày cho community
    """
    try:
        from .models import BookReview, Comment
        
        today = timezone.now().date()
        
        stats = {
            'date': today,
            'new_reviews': BookReview.objects.filter(created_at__date=today).count(),
            'new_comments': Comment.objects.filter(created_at__date=today).count(),
        }
        
        # Lưu vào cache
        cache.set(f'daily_stats_{today}', stats, 86400)  # Cache 24 giờ
        
        logger.info(f"Generated daily stats for {today}")
        return stats
        
    except Exception as exc:
        logger.error(f"Error generating daily stats: {exc}")
        raise exc

# ================== MAINTENANCE TASKS ==================

@shared_task
def cleanup_orphaned_data():
    """
    Dọn dẹp dữ liệu không còn sử dụng
    """
    try:
        from .models import ReviewHelpfulness, CommentLike
        
        # Xóa votes cho reviews đã bị xóa
        orphaned_votes = ReviewHelpfulness.objects.filter(
            review__isnull=True
        ).delete()[0]
        
        # Xóa likes cho comments đã bị xóa
        orphaned_likes = CommentLike.objects.filter(
            comment__isnull=True
        ).delete()[0]
        
        logger.info(f"Cleaned up {orphaned_votes} votes and {orphaned_likes} likes")
        return orphaned_votes + orphaned_likes
        
    except Exception as exc:
        logger.error(f"Error cleaning up orphaned data: {exc}")
        raise exc

@shared_task
def rebuild_denormalized_fields():
    """
    Rebuild tất cả denormalized fields (chạy hàng tuần)
    """
    try:
        from .models import BookReview, Comment
        
        # Rebuild helpfulness scores
        review_ids = list(BookReview.objects.values_list('id', flat=True))
        if review_ids:
            batch_update_helpfulness_scores.delay(review_ids)
        
        # Rebuild challenge stats
        
        
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
    # Placeholder - tích hợp với ML service thực tế
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