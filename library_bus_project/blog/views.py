# File: blog/views.py 
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, F, Prefetch
from django.http import JsonResponse, HttpResponse, Http404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views.generic.base import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from django.utils.decorators import method_decorator
from django.db import models
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from django.urls import reverse_lazy
from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Atom1Feed
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
import json
from .models import Post, BlogCategory, BlogTag, PostLike, PostRating, Newsletter, PostView
from .forms import PostForm, NewsletterSubscriptionForm, PostSearchForm, CommentForm, PostRatingForm, AdvancedSearchForm, QuickPostForm

# ========== HOME & LISTING VIEWS ==========
class BlogHomeView(ListView):
    """Trang chá»§ blog vá»›i featured posts vÃ  sidebar"""
    model = Post
    template_name = 'blog/home.html'
    context_object_name = 'posts'
    paginate_by = 8
    
    def get_queryset(self):
        return Post.objects.published().with_stats().select_related('author').prefetch_related('categories', 'tags')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['featured_posts'] = Post.objects.published().featured().with_stats()[:4]
        context['categories'] = BlogCategory.objects.annotate(post_count=Count('posts', filter=Q(posts__status='published')))[:8]
        context['popular_tags'] = BlogTag.objects.filter(is_trending=True).order_by('-usage_count')[:10]
        context['recent_posts'] = Post.objects.published().select_related('author')[:5]
        return context

@method_decorator(cache_page(900), name='dispatch')
class PostListView(ListView):
    """Danh sÃ¡ch bÃ i viáº¿t vá»›i filter vÃ  search"""
    model = Post
    template_name = 'blog/post_list.html'
    context_object_name = 'posts'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Post.objects.published().with_stats()
        query = self.request.GET.get('q')
        category = self.request.GET.get('category')
        tag = self.request.GET.get('tag')
        sort = self.request.GET.get('sort', 'newest')
        
        if query: queryset = queryset.search(query)
        if category: queryset = queryset.filter(categories__slug=category)
        if tag: queryset = queryset.filter(tags__slug=tag)
        
        # Sorting
        if sort == 'popular': queryset = queryset.order_by('-view_count', '-like_count')
        elif sort == 'rating': queryset = queryset.annotate(avg_rating=Avg('ratings__score')).order_by('-avg_rating')
        elif sort == 'oldest': queryset = queryset.order_by('publish_date')
        else: queryset = queryset.order_by('-publish_date')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = PostSearchForm(self.request.GET)
        context['current_category'] = self.request.GET.get('category')
        context['current_tag'] = self.request.GET.get('tag')
        context['sort_by'] = self.request.GET.get('sort', 'newest')
        return context

class PostDetailView(DetailView):
    """Chi tiáº¿t bÃ i viáº¿t vá»›i tracking vÃ  tÆ°Æ¡ng tÃ¡c"""
    model = Post
    template_name = 'blog/post_detail.html'
    context_object_name = 'post'
    
    def get_queryset(self):
        return Post.objects.published().with_stats().select_related('author').prefetch_related('categories', 'tags', 'comments__author')
    
    def get_object(self):
        post = super().get_object()
        # Track view
        self.track_view(post)
        # Increment view count
        post.increment_view_count()
        return post
    
    def track_view(self, post):
        """Track chi tiáº¿t lÆ°á»£t xem"""
        ip = self.get_client_ip()
        session_key = self.request.session.session_key
        if not session_key: 
            self.request.session.create()
            session_key = self.request.session.session_key
        
        # Chá»‰ track náº¿u chÆ°a xem trong 30 phÃºt
        recent_view = PostView.objects.filter(post=post, ip_address=ip, created_at__gte=timezone.now() - timedelta(minutes=30)).first()
        if not recent_view:
            PostView.objects.create(post=post, user=self.request.user if self.request.user.is_authenticated else None, ip_address=ip, user_agent=self.request.META.get('HTTP_USER_AGENT', ''), session_key=session_key)
    
    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for: return x_forwarded_for.split(',')[0]
        return self.request.META.get('REMOTE_ADDR')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = self.object
        context['related_posts'] = post.get_related_posts()
        context['user_liked'] = PostLike.objects.filter(post=post, user=self.request.user).exists() if self.request.user.is_authenticated else False
        context['user_rating'] = PostRating.objects.filter(post=post, user=self.request.user).first() if self.request.user.is_authenticated else None
        context['comments'] = post.comments.filter(is_approved=True).select_related('author').order_by('-created_at')
        context['comment_form'] = CommentForm()
        context['rating_form'] = PostRatingForm()
        context['avg_rating'] = post.ratings.aggregate(avg=Avg('score'))['avg'] or 0
        context['rating_count'] = post.ratings.count()
        return context

# ========== CATEGORY & TAG VIEWS ==========
class CategoryDetailView(ListView):
    """Chi tiáº¿t chuyÃªn má»¥c vá»›i bÃ i viáº¿t"""
    model = Post
    template_name = 'blog/category_detail.html'
    context_object_name = 'posts'
    paginate_by = 12
    
    def get_queryset(self):
        self.category = get_object_or_404(BlogCategory, slug=self.kwargs['slug'])
        return Post.objects.published().filter(categories=self.category).with_stats()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        context['subcategories'] = self.category.children.all()
        return context

class TagDetailView(ListView):
    """Chi tiáº¿t tag vá»›i bÃ i viáº¿t"""
    model = Post
    template_name = 'blog/tag_detail.html'
    context_object_name = 'posts'
    paginate_by = 12
    
    def get_queryset(self):
        self.tag = get_object_or_404(BlogTag, slug=self.kwargs['slug'])
        return Post.objects.published().filter(tags=self.tag).with_stats()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tag'] = self.tag
        context['related_tags'] = BlogTag.objects.filter(posts__tags=self.tag).exclude(id=self.tag.id).distinct()[:10]
        return context

# ========== AUTHOR VIEWS ==========
class AuthorPostListView(ListView):
    """Danh sÃ¡ch bÃ i viáº¿t theo tÃ¡c giáº£"""
    model = Post
    template_name = 'blog/author_posts.html'
    context_object_name = 'posts'
    paginate_by = 12
    
    def get_queryset(self):
        from django.contrib.auth.models import User
        self.author = get_object_or_404(User, username=self.kwargs['username'])
        return Post.objects.published().filter(author=self.author).with_stats()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['author'] = self.author
        context['author_stats'] = {'total_posts': self.author.blog_posts.published().count(), 'total_views': self.author.blog_posts.published().aggregate(total=models.Sum('view_count'))['total'] or 0}
        return context

# ========== ADMIN VIEWS ==========
class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin yÃªu cáº§u quyá»n staff"""
    def test_func(self):
        return self.request.user.is_staff

class PostCreateView(LoginRequiredMixin, CreateView):
    """Táº¡o bÃ i viáº¿t má»›i"""
    model = Post
    form_class = PostForm
    template_name = 'blog/post_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.author = self.request.user
        
        # Náº¿u khÃ´ng pháº£i staff/admin, Ä‘áº·t status lÃ  pending
        if not self.request.user.is_staff:
            form.instance.status = 'pending'
        
        response = super().form_valid(form)
        
        # ThÃ´ng bÃ¡o khÃ¡c nhau tÃ¹y theo quyá»n
        if form.instance.status == 'pending':
            messages.success(self.request, 'BÃ i viáº¿t Ä‘Ã£ Ä‘Æ°á»£c gá»­i vÃ  Ä‘ang chá» duyá»‡t tá»« admin!')
            # Gá»­i email thÃ´ng bÃ¡o cho admin
            self.notify_admin_new_post(form.instance)
        else:
            messages.success(self.request, 'BÃ i viáº¿t Ä‘Ã£ Ä‘Æ°á»£c táº¡o thÃ nh cÃ´ng!')
        
        return response
    
    def notify_admin_new_post(self, post):
        """Gá»­i email thÃ´ng bÃ¡o cho admin vá» bÃ i viáº¿t má»›i cáº§n duyá»‡t"""
        from django.contrib.auth.models import User
        admins = User.objects.filter(is_staff=True, is_active=True)
        
        if admins.exists():
            subject = f'BÃ i viáº¿t má»›i cáº§n duyá»‡t: {post.title}'
            message = render_to_string('blog/emails/new_post_notification.html', {
                'post': post,
                'author': post.author,
                'admin_url': f"{settings.SITE_URL}/admin/blog/post/{post.id}/change/",
                'site_url': settings.SITE_URL
            })
            
            admin_emails = [admin.email for admin in admins if admin.email]
            if admin_emails:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=admin_emails,
                    html_message=message,
                    fail_silently=True
                )

class PostUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Chá»‰nh sá»­a bÃ i viáº¿t"""
    model = Post
    form_class = PostForm
    template_name = 'blog/post_form.html'
    
    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author or self.request.user.is_staff
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        # Náº¿u bÃ i viáº¿t Ä‘Ã£ Ä‘Æ°á»£c duyá»‡t vÃ  ngÆ°á»i dÃ¹ng khÃ´ng pháº£i staff
        # thÃ¬ chuyá»ƒn láº¡i vá» pending khi chá»‰nh sá»­a
        if (self.object.status == 'published' and 
            not self.request.user.is_staff and
            self.request.user == self.object.author):
            form.instance.status = 'pending'
            form.instance.moderated_at = None
            form.instance.moderated_by = None
            form.instance.moderation_note = ''
        
        # Táº¡o phiÃªn báº£n má»›i náº¿u bÃ i viáº¿t Ä‘Ã£ Ä‘Æ°á»£c xuáº¥t báº£n
        if self.object.status == 'published':
            self.object.create_new_version(self.request.user)
        
        response = super().form_valid(form)
        
        if form.instance.status == 'pending':
            messages.success(self.request, 'BÃ i viáº¿t Ä‘Ã£ Ä‘Æ°á»£c cáº­p nháº­t vÃ  Ä‘ang chá» duyá»‡t láº¡i!')
            # Gá»­i email thÃ´ng bÃ¡o cho admin
            self.notify_admin_updated_post(form.instance)
        else:
            messages.success(self.request, 'BÃ i viáº¿t Ä‘Ã£ Ä‘Æ°á»£c cáº­p nháº­t!')
        
        return response
    
    def notify_admin_updated_post(self, post):
        """Gá»­i email thÃ´ng bÃ¡o cho admin vá» bÃ i viáº¿t Ä‘Æ°á»£c cáº­p nháº­t"""
        from django.contrib.auth.models import User
        admins = User.objects.filter(is_staff=True, is_active=True)
        
        if admins.exists():
            subject = f'BÃ i viáº¿t Ä‘Æ°á»£c cáº­p nháº­t cáº§n duyá»‡t láº¡i: {post.title}'
            message = render_to_string('blog/emails/updated_post_notification.html', {
                'post': post,
                'author': post.author,
                'admin_url': f"{settings.SITE_URL}/admin/blog/post/{post.id}/change/",
                'site_url': settings.SITE_URL
            })
            
            admin_emails = [admin.email for admin in admins if admin.email]
            if admin_emails:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=admin_emails,
                    html_message=message,
                    fail_silently=True
                )

class PostDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """XÃ³a bÃ i viáº¿t"""
    model = Post
    template_name = 'blog/post_confirm_delete.html'
    success_url = reverse_lazy('blog:post_list')
    
    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author or self.request.user.is_staff
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'BÃ i viáº¿t Ä‘Ã£ Ä‘Æ°á»£c xÃ³a!')
        return super().delete(request, *args, **kwargs)

# ========== MODERATION VIEWS ==========
class PendingPostsView(StaffRequiredMixin, ListView):
    """Danh sÃ¡ch bÃ i viáº¿t chá» duyá»‡t (chá»‰ dÃ nh cho staff)"""
    model = Post
    template_name = 'blog/pending_posts.html'
    context_object_name = 'posts'
    paginate_by = 20
    
    def get_queryset(self):
        return Post.objects.filter(status='pending').select_related('author').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_pending'] = Post.objects.filter(status='pending').count()
        return context

@login_required
def moderate_post(request, post_id):
    """Duyá»‡t hoáº·c tá»« chá»‘i bÃ i viáº¿t"""
    if not request.user.is_staff:
        messages.error(request, 'Báº¡n khÃ´ng cÃ³ quyá»n thá»±c hiá»‡n hÃ nh Ä‘á»™ng nÃ y.')
        return redirect('blog:home')
    
    post = get_object_or_404(Post, id=post_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        moderation_note = request.POST.get('moderation_note', '')
        
        if action == 'approve':
            post.status = 'published'
            post.publish_date = timezone.now()
            post.moderated_by = request.user
            post.moderated_at = timezone.now()
            post.moderation_note = moderation_note
            post.save()
            
            # Gá»­i email thÃ´ng bÃ¡o duyá»‡t bÃ i
            send_approval_email(post)
            messages.success(request, f'BÃ i viáº¿t "{post.title}" Ä‘Ã£ Ä‘Æ°á»£c duyá»‡t vÃ  xuáº¥t báº£n!')
            
        elif action == 'reject':
            post.status = 'rejected'
            post.moderated_by = request.user
            post.moderated_at = timezone.now()
            post.moderation_note = moderation_note
            post.save()
            
            # Gá»­i email thÃ´ng bÃ¡o tá»« chá»‘i
            send_rejection_email(post)
            messages.success(request, f'BÃ i viáº¿t "{post.title}" Ä‘Ã£ bá»‹ tá»« chá»‘i!')
        
        return redirect('blog:pending_posts')
    
    return render(request, 'blog/moderate_post.html', {'post': post})

def send_approval_email(post):
    """Gá»­i email thÃ´ng bÃ¡o bÃ i viáº¿t Ä‘Æ°á»£c duyá»‡t"""
    if post.author.email:
        subject = f'BÃ i viáº¿t "{post.title}" Ä‘Ã£ Ä‘Æ°á»£c duyá»‡t'
        message = render_to_string('blog/emails/post_approved.html', {
            'post': post,
            'author': post.author,
            'post_url': f"{settings.SITE_URL}{post.get_absolute_url()}",
            'site_url': settings.SITE_URL
        })
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[post.author.email],
            html_message=message,
            fail_silently=True
        )

def send_rejection_email(post):
    """Gá»­i email thÃ´ng bÃ¡o bÃ i viáº¿t bá»‹ tá»« chá»‘i"""
    if post.author.email:
        subject = f'BÃ i viáº¿t "{post.title}" cáº§n chá»‰nh sá»­a'
        message = render_to_string('blog/emails/post_rejected.html', {
            'post': post,
            'author': post.author,
            'moderation_note': post.moderation_note,
            'edit_url': f"{settings.SITE_URL}/blog/post/{post.id}/edit/",
            'site_url': settings.SITE_URL
        })
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[post.author.email],
            html_message=message,
            fail_silently=True
        )

# ========== AJAX VIEWS ==========
@login_required
def toggle_like(request, post_id):
    """Toggle like/unlike bÃ i viáº¿t"""
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    post = get_object_or_404(Post, id=post_id)
    like, created = PostLike.objects.get_or_create(post=post, user=request.user)
    
    if not created:
        like.delete()
        liked = False
    else:
        liked = True
    
    post.refresh_from_db(fields=['like_count'])
    return JsonResponse({'liked': liked, 'like_count': post.like_count})

@login_required
def rate_post(request, post_id):
    """Ä Ã¡nh giÃ¡ bÃ i viáº¿t"""
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    post = get_object_or_404(Post, id=post_id)
    score = request.POST.get('score')
    
    try:
        score = int(score)
        if score < 1 or score > 5: raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid rating score'}, status=400)
    
    rating, created = PostRating.objects.get_or_create(post=post, user=request.user, defaults={'score': score})
    if not created:
        rating.score = score
        rating.save()
    
    # TÃ­nh láº¡i rating trung bÃ¬nh
    avg_rating = post.ratings.aggregate(avg=Avg('score'))['avg'] or 0
    rating_count = post.ratings.count()
    
    return JsonResponse({'success': True, 'avg_rating': round(avg_rating, 1), 'rating_count': rating_count, 'user_rating': score})

@login_required
def add_comment(request, post_id):
    """Thêm bình luận"""
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    post = get_object_or_404(Post, id=post_id)
    if not post.allow_comments: return JsonResponse({'error': 'Comments not allowed'}, status=403)
    
    form = CommentForm(request.POST)
    if form.is_valid():
        from blog.models import Comment
        comment = Comment.objects.create(post=post, author=request.user, content=form.cleaned_data['content'])
        
        # Render comment HTML
        comment_html = render_to_string('blog/partials/comment.html', {'comment': comment}, request=request)
        return JsonResponse({'success': True, 'comment_html': comment_html})
    
    return JsonResponse({'error': 'Invalid comment data'}, status=400)

# ========== SEARCH VIEWS ==========
class SearchView(ListView):
    """Tìm kiếm nâng cao"""
    model = Post
    template_name = 'blog/search_results.html'
    context_object_name = 'posts'
    paginate_by = 15
    
    def get_queryset(self):
        form = AdvancedSearchForm(self.request.GET)
        queryset = Post.objects.published().with_stats()
        
        if form.is_valid():
            query = form.cleaned_data.get('query')
            categories = form.cleaned_data.get('categories')
            tags = form.cleaned_data.get('tags')
            content_type = form.cleaned_data.get('content_type')
            difficulty = form.cleaned_data.get('difficulty_level')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            author = form.cleaned_data.get('author')
            has_image = form.cleaned_data.get('has_featured_image')
            min_time = form.cleaned_data.get('min_reading_time')
            max_time = form.cleaned_data.get('max_reading_time')
            sort_by = form.cleaned_data.get('sort_by')
            
            if query: queryset = queryset.search(query)
            if categories: queryset = queryset.filter(categories__in=categories)
            if tags: queryset = queryset.filter(tags__in=tags)
            if content_type: queryset = queryset.filter(content_type=content_type)
            if difficulty: queryset = queryset.filter(difficulty_level=difficulty)
            if date_from: queryset = queryset.filter(publish_date__gte=date_from)
            if date_to: queryset = queryset.filter(publish_date__lte=date_to)
            if author: queryset = queryset.filter(author=author)
            if has_image: queryset = queryset.filter(featured_image__isnull=False)
            if min_time: queryset = queryset.filter(reading_time__gte=min_time)
            if max_time: queryset = queryset.filter(reading_time__lte=max_time)
            
            # Sorting
            if sort_by == 'popular': queryset = queryset.order_by('-view_count')
            elif sort_by == 'most_liked': queryset = queryset.order_by('-like_count')
            elif sort_by == 'reading_time': queryset = queryset.order_by('reading_time')
            elif sort_by == 'oldest': queryset = queryset.order_by('publish_date')
            else: queryset = queryset.order_by('-publish_date')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = AdvancedSearchForm(self.request.GET)
        context['query'] = self.request.GET.get('query', '')
        return context

# ========== FEED VIEWS ==========
class LatestPostsFeed(Feed):
    """RSS Feed cho bÃ i viáº¿t má»›i nháº¥t"""
    title = "Blog - BÃ i viáº¿t má»›i nháº¥t"
    link = "/blog/"
    description = "Cáº­p nháº­t bÃ i viáº¿t má»›i nháº¥t tá»« blog"
    
    def items(self):
        return Post.objects.published().order_by('-publish_date')[:10]
    
    def item_title(self, item):
        return item.title
    
    def item_description(self, item):
        return item.excerpt or item.content[:200]
    
    def item_link(self, item):
        return item.get_absolute_url()
    
    def item_pubdate(self, item):
        return item.publish_date or item.created_at

class CategoryFeed(Feed):
    """RSS Feed theo chuyÃªn má»¥c"""
    def get_object(self, request, category_slug):
        return get_object_or_404(BlogCategory, slug=category_slug)
    
    def title(self, obj):
        return f"Blog - {obj.name}"
    
    def link(self, obj):
        return obj.get_absolute_url()
    
    def description(self, obj):
        return f"BÃ i viáº¿t má»›i nháº¥t tá»« chuyÃªn má»¥c {obj.name}"
    
    def items(self, obj):
        return Post.objects.published().filter(categories=obj).order_by('-publish_date')[:10]

# ========== NEWSLETTER VIEWS ==========
def newsletter_subscribe(request):
    """ÄÄƒng kÃ½ newsletter"""
    if request.method == 'POST':
        form = NewsletterSubscriptionForm(request.POST)
        if form.is_valid():
            newsletter = form.save()
            messages.success(request, 'ÄÄƒng kÃ½ newsletter thÃ nh cÃ´ng! Vui lÃ²ng kiá»ƒm tra email Ä‘á»ƒ xÃ¡c nháº­n.')
            return redirect('blog:home')
    else:
        form = NewsletterSubscriptionForm()
    
    return render(request, 'blog/newsletter_subscribe.html', {'form': form})

def newsletter_unsubscribe(request, token):
    """Há»§y Ä‘Äƒng kÃ½ newsletter"""
    # Logic xÃ¡c thá»±c token vÃ  há»§y Ä‘Äƒng kÃ½
    messages.success(request, 'ÄÃ£ há»§y Ä‘Äƒng kÃ½ newsletter thÃ nh cÃ´ng!')
    return redirect('blog:home')

# ========== DASHBOARD VIEWS ==========
@login_required
def dashboard(request):
    """Dashboard cho tÃ¡c giáº£"""
    user_posts = Post.objects.filter(author=request.user).with_stats()
    stats = {
        'total_posts': user_posts.count(),
        'published_posts': user_posts.published().count(),
        'pending_posts': user_posts.filter(status='pending').count(),
        'rejected_posts': user_posts.filter(status='rejected').count(),
        'draft_posts': user_posts.draft().count(),
        'total_views': user_posts.aggregate(total=models.Sum('view_count'))['total'] or 0,
        'total_likes': user_posts.aggregate(total=models.Sum('like_count'))['total'] or 0
    }
    
    recent_posts = user_posts.order_by('-created_at')[:10]
    pending_posts = user_posts.filter(status='pending').order_by('-created_at')[:5]
    rejected_posts = user_posts.filter(status='rejected').order_by('-moderated_at')[:5]
    
    return render(request, 'blog/dashboard.html', {
        'stats': stats,
        'recent_posts': recent_posts,
        'pending_posts': pending_posts,
        'rejected_posts': rejected_posts
    })

@login_required
def quick_post(request):
    """Táº¡o bÃ i viáº¿t nhanh"""
    if request.method == 'POST':
        form = QuickPostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            
            # Náº¿u khÃ´ng pháº£i staff, Ä‘áº·t status lÃ  pending
            if not request.user.is_staff:
                post.status = 'pending'
            
            post.save()
            form.save_m2m()
            
            if post.status == 'pending':
                messages.success(request, 'Bài viết nhanh đã được tạo và đang chờ duyệt!')
            else:
                messages.success(request, 'Bài viết nhanh đã được tạo thành công!')
            
            return redirect('blog:dashboard')
    else:
        form = QuickPostForm()
    
    return render(request, 'blog/dashboard.html', {'quick_form': form})
