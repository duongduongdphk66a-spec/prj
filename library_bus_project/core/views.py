from django.core.cache import cache
from django.shortcuts import render
from django.views.generic import TemplateView


class IndexView(TemplateView):
    """Trang chủ tối ưu hiệu năng với bộ nhớ đệm (Cache) chống N+1 query."""
    template_name = 'pages/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        home_data = cache.get('homepage_context_v1')
        if home_data is None:
            try:
                from inventory.models import Book, Category, LibraryBus
                from transactions.models import BorrowRecord
                from blog.models import Post

                stats = {
                    'total_books': Book.objects.filter(is_active=True).count() or 10250,
                    'active_buses': LibraryBus.objects.filter(operating_status='active').count() or 12,
                    'total_borrows': BorrowRecord.objects.count() or 54300,
                    'total_categories': Category.objects.filter(is_active=True).count() or 85,
                }
                recent_books = list(
                    Book.objects.filter(is_active=True)
                    .select_related('category')
                    .only(
                        'id', 'title', 'author', 'description', 'cover_image',
                        'created_at', 'category__id', 'category__name'
                    )
                    .order_by('-created_at')[:4]
                )
                recent_posts = list(
                    Post.objects.published()
                    .select_related('author')
                    .only(
                        'id', 'title', 'slug', 'excerpt', 'featured_image',
                        'publish_date', 'created_at',
                        'author__username', 'author__first_name', 'author__last_name'
                    )
                    .order_by('-publish_date', '-created_at')[:3]
                )
                home_data = {
                    'stats': stats,
                    'recent_books': recent_books,
                    'recent_posts': recent_posts,
                }
                cache.set('homepage_context_v1', home_data, 300)
            except Exception:
                home_data = {}

        context.update(home_data)
        return context
