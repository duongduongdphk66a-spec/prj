from django.test import TestCase
from django.contrib.auth import get_user_model
from blog.models import Post, BlogCategory, Comment

User = get_user_model()

class BlogModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='blogger', password='password')
        self.category = BlogCategory.objects.create(name='Tech')
        self.post = Post.objects.create(
            title='Test Post Title',
            content='This is the test content for the post.',
            author=self.user,
            status='published'
        )
        self.post.categories.add(self.category)

    def test_increment_view_count(self):
        initial_views = self.post.view_count
        self.post.increment_view_count()
        self.post.refresh_from_db()
        self.assertEqual(self.post.view_count, initial_views + 1)
        
        # Test cache lock (nếu gọi liên tục trong 30s sẽ không tăng)
        self.post.increment_view_count()
        self.post.refresh_from_db()
        self.assertEqual(self.post.view_count, initial_views + 1)

    def test_comment_thread_logic(self):
        # Tạo top-level comment
        comment1 = Comment.objects.create(
            post=self.post, author=self.user, content='Top level', is_approved=True
        )
        self.assertEqual(comment1.depth, 0)
        self.assertEqual(comment1.thread_id, comment1.id)
        
        # Tạo reply (depth 1)
        comment2 = Comment.objects.create(
            post=self.post, author=self.user, content='Reply 1', parent=comment1, is_approved=True
        )
        self.assertEqual(comment2.depth, 1)
        self.assertEqual(comment2.thread_id, comment1.id)
        
        # Tạo sub-reply (depth 2)
        comment3 = Comment.objects.create(
            post=self.post, author=self.user, content='Reply 2', parent=comment2, is_approved=True
        )
        self.assertEqual(comment3.depth, 2)
        self.assertEqual(comment3.thread_id, comment1.id)
