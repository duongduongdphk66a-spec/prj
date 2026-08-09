# File: blog/urls.py
from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    # ========== HOME & LISTING VIEWS ==========
    path('', views.PostListView.as_view(), name='post_list'), # Sử dụng PostListView làm trang chủ
    path('home/', views.BlogHomeView.as_view(), name='home'), # Hoặc một trang chủ riêng
    # ========== POST CRUD VIEWS ==========
    path('post/new/', views.PostCreateView.as_view(), name='post_create'),
    path('post/<slug:slug>/', views.PostDetailView.as_view(), name='post_detail'),
    path('post/<slug:slug>/edit/', views.PostUpdateView.as_view(), name='post_update'),
    path('post/<slug:slug>/delete/', views.PostDeleteView.as_view(), name='post_delete'),

    # ========== CATEGORY & TAG VIEWS ==========
    path('category/<slug:slug>/', views.CategoryDetailView.as_view(), name='category_detail'),
    path('tag/<slug:slug>/', views.TagDetailView.as_view(), name='tag_detail'),

    # ========== AUTHOR VIEWS ==========
    path('author/<str:username>/', views.AuthorPostListView.as_view(), name='author_posts'),

    # ========== MODERATION VIEWS ==========
    path('dashboard/pending/', views.PendingPostsView.as_view(), name='pending_posts'),
    path('dashboard/moderate/<uuid:post_id>/', views.moderate_post, name='moderate_post'),

    # ========== AJAX & INTERACTION VIEWS ==========
    path('ajax/post/<uuid:post_id>/like/', views.toggle_like, name='toggle_like'),
    path('ajax/post/<uuid:post_id>/rate/', views.rate_post, name='rate_post'),
    path('ajax/post/<uuid:post_id>/comment/', views.add_comment, name='add_comment'),

    # ========== SEARCH VIEW ==========
    path('search/', views.SearchView.as_view(), name='search'),

    # ========== FEED VIEWS ==========
    path('feed/latest/', views.LatestPostsFeed(), name='latest_feed'),
    path('feed/category/<slug:category_slug>/', views.CategoryFeed(), name='category_feed'),

    # ========== NEWSLETTER VIEWS ==========
    path('newsletter/subscribe/', views.newsletter_subscribe, name='newsletter_subscribe'),
    path('newsletter/unsubscribe/<str:token>/', views.newsletter_unsubscribe, name='newsletter_unsubscribe'),

    # ========== DASHBOARD & QUICK ACTIONS ==========
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/quick-post/', views.quick_post, name='quick_post'),

    # Book Review, Comment, Notification views removed during simplification

]
