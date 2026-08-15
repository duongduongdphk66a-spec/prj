# File: inventory/views.py 
import os
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count, Avg, Prefetch
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse, reverse_lazy
from django.views.decorators.cache import cache_page

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff

def is_staff_check(user):
    return user.is_staff

staff_required = user_passes_test(is_staff_check)
from django.db import transaction
from django.core.cache import cache
from django.utils import timezone
from django.core.files.storage import default_storage
from .models import LibraryBus, Category, Book, BookStatusHistory, BusRoute, InventoryAlert, BookDonation
from .forms import LibraryBusForm, CategoryForm, BookSearchForm, BookStatusChangeForm, BookForm, BulkBookUploadForm, BusRouteForm, BookDonationForm
import csv
import io
import json
import logging

logger = logging.getLogger(__name__)

# Dashboard View
@staff_required
@login_required
def dashboard(request):
    """Dashboard tổng quan với cache"""
    cache_key = 'dashboard_data'
    data = cache.get(cache_key)
    
    if not data:
        # Pre-annotate bus data to avoid N+1 on capacity_stats
        active_buses = LibraryBus.objects.active_only().with_book_counts()[:10]
        data = {
            'total_buses': LibraryBus.objects.count(),
            'active_buses': LibraryBus.objects.filter(operating_status='active').count(),
            'total_books': Book.objects.count(),
            'available_books': Book.objects.filter(status='available').count(),
            'digital_books': Book.objects.filter(is_digital_only=True).count(),
            'books_with_pdf': Book.objects.exclude(pdf_file='').count(),
            'total_categories': Category.objects.filter(is_active=True).count(),
            'recent_books': Book.objects.with_relations().order_by('-created_at')[:5],
            'low_stock_buses': LibraryBus.objects.filter(_book_count__lt=50),
            'alerts': InventoryAlert.objects.filter(is_resolved=False).order_by('-created_at')[:10],
            'popular_books': Book.objects.order_by('-_popularity_score')[:5],
            'capacity_stats': [{
                'name': bus.name,
                'usage': bus.capacity_usage_percentage,
                'count': bus.current_book_count
            } for bus in active_buses]
        }
        cache.set(cache_key, data, 300)
    
    return render(request, 'inventory/dashboard.html', data)

# LibraryBus Views
class AdminLibraryBusListView(AdminRequiredMixin, ListView):
    model = LibraryBus
    template_name = 'inventory/admin_bus_list.html'
    context_object_name = 'buses'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = LibraryBus.objects.with_book_counts().order_by('name')
        query = self.request.GET.get('query')
        if query:
            queryset = queryset.filter(name__icontains=query)
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(operating_status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_buses'] = LibraryBus.objects.count()
        context['active_buses'] = LibraryBus.objects.filter(operating_status='active').count()
        return context

@method_decorator(cache_page(60 * 5), name='dispatch')
class LibraryBusListView(LoginRequiredMixin, ListView):
    model = LibraryBus
    template_name = 'inventory/bus_list.html'
    context_object_name = 'buses'
    paginate_by = 20
    
    def get_queryset(self):


        return LibraryBus.objects.with_book_counts().order_by('name')
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Prepare buses data for the map
        buses_data = []
        for bus in self.object_list:
            if bus.latitude and bus.longitude:
                buses_data.append({
                    'id': str(bus.id),
                    'name': bus.name,
                    'lat': float(bus.latitude),
                    'lng': float(bus.longitude),
                    'status': bus.get_operating_status_display(),
                    'location_name': bus.location_name,
                    'detail_url': reverse('inventory:bus_detail', args=[bus.id])
                })
        context['buses_json'] = json.dumps(buses_data)
        return context
                
class LibraryBusDetailView(LoginRequiredMixin, DetailView):
    model = LibraryBus
    template_name = 'inventory/bus_detail.html'
    context_object_name = 'bus'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['books'] = self.object.books_on_bus.with_relations().order_by('title')
        context['alerts'] = self.object.alerts.filter(is_resolved=False).order_by('-created_at')
        context['stats'] = {'total': self.object.current_book_count, 'available': self.object.books_on_bus.filter(status='available').count(), 'digital': self.object.books_on_bus.filter(is_digital_only=True).count()}
        return context

class LibraryBusCreateView(AdminRequiredMixin, CreateView):
    model = LibraryBus
    form_class = LibraryBusForm
    template_name = 'inventory/bus_form.html'
    success_url = reverse_lazy('inventory:bus_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Xe bus "{form.instance.name}" đã được tạo!')
        return super().form_valid(form)

class LibraryBusUpdateView(AdminRequiredMixin, UpdateView):
    model = LibraryBus
    form_class = LibraryBusForm
    template_name = 'inventory/bus_form.html'
    success_url = reverse_lazy('inventory:bus_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Xe bus "{form.instance.name}" đã được cập nhật!')
        return super().form_valid(form)

@staff_required
@login_required
@require_http_methods(["POST"])
def bus_location_update(request, pk):
    """Cập nhật vị trí xe bus qua AJAX — có validate input"""
    bus = get_object_or_404(LibraryBus, pk=pk)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Dữ liệu không hợp lệ'}, status=400)
    
    # Validate latitude và longitude
    try:
        lat = float(data.get('latitude', 0))
        lng = float(data.get('longitude', 0))
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return JsonResponse({'status': 'error', 'message': 'Tọa độ không hợp lệ'}, status=400)
    except (TypeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'Tọa độ phải là số'}, status=400)
    
    bus.latitude = lat
    bus.longitude = lng
    bus.location_name = str(data.get('location_name', ''))[:200]  # Limit length
    bus.save(update_fields=['latitude', 'longitude', 'location_name'])
    return JsonResponse({'status': 'success'})

# Category Views
class CategoryListView(AdminRequiredMixin, ListView):
    model = Category
    template_name = 'inventory/category_list.html'
    context_object_name = 'categories'
    
    def get_queryset(self):
        return Category.objects.with_book_counts().order_by('name')

class CategoryCreateView(AdminRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'inventory/category_form.html'
    success_url = reverse_lazy('inventory:category_list')

class CategoryUpdateView(AdminRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'inventory/category_form.html'
    success_url = reverse_lazy('inventory:category_list')

# Book Views
class AdminBookListView(AdminRequiredMixin, ListView):
    model = Book
    template_name = 'inventory/admin_book_list.html'
    context_object_name = 'books'
    paginate_by = 20

    def get_queryset(self):
        queryset = Book.objects.with_relations().order_by('-created_at')
        query = self.request.GET.get('query')
        if query:
            queryset = queryset.filter(Q(title__icontains=query) | Q(author__icontains=query))
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
            
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category_id=category)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_books'] = Book.objects.count()
        context['available_books'] = Book.objects.available().count()
        context['categories'] = Category.objects.filter(is_active=True)
        return context

class BookListView(LoginRequiredMixin, ListView):
    model = Book
    template_name = 'inventory/book_list.html'
    context_object_name = 'books'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Book.objects.with_relations().with_analytics().order_by('title')
        form = BookSearchForm(self.request.GET)
        if form.is_valid():
            query = form.cleaned_data.get('query')
            if query: queryset = queryset.search(query)
            
            title = form.cleaned_data.get('title')
            if title: queryset = queryset.filter(title__icontains=title)
            
            author = form.cleaned_data.get('author')
            if author: queryset = queryset.filter(author__icontains=author)
            
            category = form.cleaned_data.get('category')
            if category: queryset = queryset.filter(category=category)
            location = form.cleaned_data.get('location')
            if location: queryset = queryset.filter(location=location)
            status = form.cleaned_data.get('status')
            if status: queryset = queryset.filter(status=status)
            has_pdf = form.cleaned_data.get('has_pdf')
            if has_pdf: queryset = queryset.exclude(pdf_file='')
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = BookSearchForm(self.request.GET)
        context['available_count'] = Book.objects.available().count()
        context['borrowed_count'] = Book.objects.filter(status='checked_out').count()
        context['categories_count'] = Category.objects.filter(is_active=True).count()
        root_categories = Category.objects.filter(is_active=True, parent__isnull=True).with_book_counts().prefetch_related(
            Prefetch('subcategories', queryset=Category.objects.filter(is_active=True).with_book_counts())
        )
        context['categories'] = root_categories
        
        active_cat_id = self.request.GET.get('category')
        active_parent_id = None
        if active_cat_id:
            try:
                cat_obj = Category.objects.get(id=active_cat_id)
                if cat_obj.parent_id:
                    active_parent_id = str(cat_obj.parent_id)
            except Category.DoesNotExist:
                pass
        context['active_parent_id'] = active_parent_id
        
        return context

class BookDetailView(LoginRequiredMixin, DetailView):
    model = Book
    template_name = 'inventory/book_detail.html'
    context_object_name = 'book'
    
    def get_queryset(self):
        return Book.objects.with_relations().with_analytics()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_history'] = self.object.status_history.select_related('changed_by').order_by('-created_at')[:10]
        context['status_form'] = BookStatusChangeForm(current_status=self.object.status)
        context['file_info'] = self.get_file_info()
        context['related_books'] = Book.objects.filter(category=self.object.category).exclude(id=self.object.id).order_by('-created_at')[:4]
        
        # Ratings
        from django.db.models import Avg
        from .models import BookRating
        ratings = self.object.ratings.all()
        context['average_rating'] = ratings.aggregate(Avg('rating'))['rating__avg'] or 0
        context['rating_count'] = ratings.count()
        context['user_rating'] = ratings.filter(user=self.request.user).first() if self.request.user.is_authenticated else None
        
        return context
    
    def get_file_info(self):
        """Get file information for display"""
        info = {}
        if self.object.pdf_file:
            try:
                info['pdf_size'] = f"{self.object.pdf_file.size / 1024 / 1024:.1f} MB"
                info['pdf_url'] = self.object.pdf_file.url
            except: info['pdf_size'] = "Có file"
        if self.object.cover_image:
            try: info['image_size'] = f"{self.object.cover_image.size / 1024:.1f} KB"
            except: info['image_size'] = "Có file"
        return info

class BookCreateView(AdminRequiredMixin, CreateView):
    model = Book
    form_class = BookForm
    template_name = 'inventory/book_form.html'
    success_url = reverse_lazy('inventory:book_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Sách "{form.instance.title}" đã được thêm!')
        return super().form_valid(form)

class BookUpdateView(AdminRequiredMixin, UpdateView):
    model = Book
    form_class = BookForm
    template_name = 'inventory/book_form.html'
    success_url = reverse_lazy('inventory:book_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Sách "{form.instance.title}" đã được cập nhật!')
        return super().form_valid(form)

@staff_required
@login_required
@require_http_methods(["POST"])
def book_status_change(request, pk):
    """Thay đổi trạng thái sách"""
    book = get_object_or_404(Book, pk=pk)
    form = BookStatusChangeForm(request.POST, current_status=book.status)
    
    if form.is_valid():
        new_status = form.cleaned_data['new_status']
        try:
            with transaction.atomic():
                book.change_status(new_status, user=request.user)
                messages.success(request, f'Trạng thái sách đã được thay đổi thành "{book.get_status_display()}"')
        except Exception as e:
            logger.error(f'Lỗi khi thay đổi trạng thái sách {pk}: {e}')
            messages.error(request, 'Có lỗi xảy ra khi thay đổi trạng thái. Vui lòng thử lại.')
    else:
        messages.error(request, 'Dữ liệu không hợp lệ')
    
    return redirect('inventory:book_detail', pk=pk)

@staff_required
@login_required
def bulk_book_upload(request):
    """Upload sách hàng loạt từ CSV"""
    if request.method == 'POST':
        form = BulkBookUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            default_category = form.cleaned_data['default_category']
            default_location = form.cleaned_data['default_location']
            
            try:
                decoded_file = csv_file.read().decode('utf-8')
                reader = csv.DictReader(decoded_file.splitlines())
                created_count = 0
                error_count = 0
                
                with transaction.atomic():
                    for row in reader:
                        try:
                            book = Book(
                                title=row.get('title', ''), author=row.get('author', ''),
                                publisher=row.get('publisher', ''), publication_year=int(row.get('publication_year', default_category.created_at.year)),
                                page_count=int(row.get('page_count', 100)), isbn=row.get('isbn', ''),
                                category=default_category, location=default_location,
                                description=row.get('description', ''), language=row.get('language', 'Tiếng Việt')
                            )
                            book.full_clean()
                            book.save()
                            created_count += 1
                        except Exception as e:
                            error_count += 1
                            logger.error(f"Error creating book: {e}")
                
                messages.success(request, f'Đã tạo {created_count} sách. {error_count} lỗi.')
                return redirect('inventory:book_list')
            except Exception as e:
                messages.error(request, f'Lỗi đọc file: {str(e)}')
    else:
        form = BulkBookUploadForm()
    
    return render(request, 'inventory/bulk_upload.html', {'form': form})

@staff_required
@login_required
def bulk_pdf_upload(request):
    """Upload PDF hàng loạt"""
    if request.method == 'POST':
        files = request.FILES.getlist('pdf_files')
        updated_count = 0
        errors = []
        
        for file in files:
            try:
                filename = file.name.replace('.pdf', '')
                book = Book.objects.filter(title__icontains=filename).first()
                if book and not book.pdf_file:
                    book.pdf_file = file
                    book.save()
                    updated_count += 1
                elif book and book.pdf_file:
                    errors.append(f"{filename}: Đã có PDF")
                else:
                    errors.append(f"{filename}: Không tìm thấy sách")
            except Exception as e:
                errors.append(f"{file.name}: {str(e)}")
        
        if updated_count > 0:
            messages.success(request, f'Đã cập nhật PDF cho {updated_count} sách')
        if errors:
            messages.warning(request, f'Lỗi: {", ".join(errors[:5])}{"..." if len(errors) > 5 else ""}')
        
        return redirect('inventory:book_list')
    
    context = {
        'books_without_pdf': Book.objects.filter(pdf_file='').count(),
        'books_with_pdf': Book.objects.exclude(pdf_file='').count()
    }
    return render(request, 'inventory/bulk_pdf_upload.html', context)

@staff_required
@login_required
def extract_pdf_metadata(request):
    """Trích xuất metadata từ PDF"""
    if request.method == 'POST':
        book_ids = request.POST.getlist('book_ids')
        updated_count = 0
        
        for book_id in book_ids:
            try:
                book = Book.objects.get(id=book_id)
                if book.pdf_file:
                    # Placeholder for PDF metadata extraction
                    # Can implement with PyPDF2, pdfplumber, etc.
                    updated_count += 1
            except Book.DoesNotExist:
                continue
        
        messages.success(request, f'Đã cập nhật metadata cho {updated_count} sách')
        return redirect('inventory:book_list')
    
    books_with_pdf = Book.objects.exclude(pdf_file='')
    return render(request, 'inventory/extract_metadata.html', {'books': books_with_pdf})

# Alert Views
@staff_required
@login_required
def alerts_list(request):
    """Danh sách cảnh báo"""
    alerts = InventoryAlert.objects.select_related('bus').order_by('-created_at')
    
    status = request.GET.get('status')
    if status == 'unresolved': alerts = alerts.filter(is_resolved=False)
    elif status == 'resolved': alerts = alerts.filter(is_resolved=True)
    
    severity = request.GET.get('severity')
    if severity: alerts = alerts.filter(severity=severity)
    
    paginator = Paginator(alerts, 20)
    alerts = paginator.get_page(request.GET.get('page'))
    
    return render(request, 'inventory/alerts_list.html', {
        'alerts': alerts, 'severity_choices': InventoryAlert.SEVERITY_CHOICES,
        'current_status': status, 'current_severity': severity
    })

@staff_required
@login_required
@require_http_methods(["POST"])
def alert_resolve(request, pk):
    """Giải quyết cảnh báo"""
    alert = get_object_or_404(InventoryAlert, pk=pk)
    alert.is_resolved = True
    alert.resolved_at = timezone.now()
    alert.save()
    messages.success(request, 'Cảnh báo đã được giải quyết')
    return redirect('inventory:alerts_list')

# Route Views
class BusRouteListView(LoginRequiredMixin, ListView):
    model = BusRoute
    template_name = 'inventory/route_list.html'
    context_object_name = 'routes'
    
    def get_queryset(self):
        return BusRoute.objects.select_related('bus').order_by('route_name')

class BusRouteCreateView(AdminRequiredMixin, CreateView):
    model = BusRoute
    form_class = BusRouteForm
    template_name = 'inventory/route_form.html'
    success_url = reverse_lazy('inventory:route_list')

class BusRouteUpdateView(AdminRequiredMixin, UpdateView):
    model = BusRoute
    form_class = BusRouteForm
    template_name = 'inventory/route_form.html'
    success_url = reverse_lazy('inventory:route_list')

class BusRouteDetailView(LoginRequiredMixin, DetailView):
    model = BusRoute
    template_name = 'inventory/route_detail.html'
    context_object_name = 'route'
# API Views
@login_required
def api_bus_locations(request):
    """API vị trí xe bus"""
    buses = LibraryBus.objects.with_location().values('id', 'name', 'latitude', 'longitude', 'location_name', 'operating_status')
    return JsonResponse(list(buses), safe=False)

@login_required
def api_book_search(request):
    """API tìm kiếm sách AJAX"""
    query = request.GET.get('q', '')
    if len(query) < 2: return JsonResponse({'books': []})
    
    books = Book.objects.search(query).with_relations()[:10]
    results = [{
        'id': book.id, 'title': book.title, 'author': book.author,
        'category': book.category.name if book.category else '',
        'location': book.location.name if book.location else '',
        'status': book.get_status_display(),
        'has_pdf': bool(book.pdf_file),
        'url': reverse('inventory:book_detail', args=[book.pk])
    } for book in books]
    
    return JsonResponse({'books': results})

@staff_required
@login_required
def api_dashboard_stats(request):
    """API stats dashboard"""
    stats = {
        'total_books': Book.objects.count(),
        'available_books': Book.objects.filter(status='available').count(),
        'digital_books': Book.objects.filter(is_digital_only=True).count(),
        'books_with_pdf': Book.objects.exclude(pdf_file='').count(),
        'popular_books': list(Book.objects.order_by('-_popularity_score')[:5].values('title', 'author', '_popularity_score')),
        'capacity_usage': [{
            'name': bus.name, 'usage': bus.capacity_usage_percentage,
            'count': bus.current_book_count, 'capacity': bus.capacity
        } for bus in LibraryBus.objects.active_only()[:10]]
    }
    return JsonResponse(stats)

@login_required
def api_book_analytics(request, pk):
    """API analytics cho sách"""
    book = get_object_or_404(Book, pk=pk)
    analytics = {
        'rating': book.average_rating,
        'borrows': book.total_borrows,
        'popularity': book._popularity_score,
        'has_pdf': bool(book.pdf_file),
        'file_size': book.pdf_file.size if book.pdf_file else 0,
        'digital_only': book.is_digital_only
    }
    return JsonResponse(analytics)


@login_required
@require_http_methods(["POST"])
def api_chatbot(request):
    try:
        import json
        import google.generativeai as genai
        
        api_key = os.environ.get('GEMINI_API_KEY', '')
        if not api_key:
            return JsonResponse({'error': 'API key not configured'}, status=503)
        genai.configure(api_key=api_key)
        
        data = json.loads(request.body)
        message = data.get('message', '')
        history = data.get('history', [])
        
        if not message:
            return JsonResponse({'error': 'Message is required'}, status=400)
            
        model = genai.GenerativeModel(
            model_name='gemini-3.5-flash',
            system_instruction="Bạn là một trợ lý ảo thân thiện, thông minh của hệ thống Tủ Sách Lưu Động (Library Bus). Bạn giúp người dùng tìm kiếm sách, giải đáp thắc mắc về các quy định mượn sách, và gợi ý sách hay. Hãy trả lời ngắn gọn, súc tích và sử dụng tiếng Việt."
        )
        
        formatted_history = []
        for msg in history:
            role = 'user' if msg.get('role') == 'user' else 'model'
            formatted_history.append({
                'role': role,
                'parts': [msg.get('text', '')]
            })
            
        chat = model.start_chat(history=formatted_history)
        response = chat.send_message(message)
        
        return JsonResponse({
            'response': response.text
        })
        
    except Exception as e:
        logger.error(f"Chatbot API error: {e}")
        return JsonResponse({'error': 'Có lỗi xảy ra, vui lòng thử lại sau.'}, status=500)


# Export Views
@staff_required
@login_required
def export_books_csv(request):
    """Export sách ra CSV - dùng StreamingHttpResponse để không load all vào memory"""
    from django.http import StreamingHttpResponse
    
    def generate_csv():
        # Header row
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Title', 'Author', 'Publisher', 'Year', 'ISBN', 'Category', 'Location', 'Status', 'Has PDF', 'Digital Only'])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)
        
        # Data rows - dùng iterator() để không load all vào memory
        for book in Book.objects.with_relations().iterator(chunk_size=500):
            writer.writerow([
                book.title, book.author, book.publisher, book.publication_year,
                book.isbn, book.category.name if book.category else '',
                book.location.name if book.location else '', book.get_status_display(),
                'Yes' if book.pdf_file else 'No', 'Yes' if book.is_digital_only else 'No'
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)
    
    response = StreamingHttpResponse(generate_csv(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="books.csv"'
    return response

@staff_required
@login_required
def export_inventory_report(request):
    """Export báo cáo tồn kho - pre-annotate data để tránh N+1"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="inventory_report.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Bus Name', 'Location', 'Total Books', 'Available Books', 'Digital Books', 'Capacity', 'Usage %'])
    
    # Pre-annotate all counts in 1 query thay vì query per-bus
    buses = LibraryBus.objects.annotate(
        total_books_count=Count('books_on_bus'),
        available_books_count=Count('books_on_bus', filter=Q(books_on_bus__status='available')),
        digital_books_count=Count('books_on_bus', filter=Q(books_on_bus__is_digital_only=True)),
    ).order_by('name')
    
    for bus in buses:
        usage = round((bus.total_books_count / bus.capacity * 100), 2) if bus.capacity > 0 else 0
        writer.writerow([
            bus.name, bus.location_name, bus.total_books_count,
            bus.available_books_count, bus.digital_books_count,
            bus.capacity, usage
        ])
    
    return response

@login_required
def book_pdf_viewer(request, pk):
    """Xem PDF của sách"""
    book = get_object_or_404(Book, pk=pk)
    if not book.pdf_file:
        messages.error(request, 'Sách này không có file PDF')
        return redirect('inventory:book_detail', pk=pk)
    
    return render(request, 'inventory/pdf_viewer.html', {'book': book})

@require_http_methods(["POST"])
@staff_required
@login_required
def clear_cache(request):
    """Xóa cache — chỉ cho phép POST để chống CSRF attack"""
    cache.clear()
    messages.success(request, 'Cache đã được xóa')
    return redirect('inventory:dashboard')

@staff_required
@login_required
@require_http_methods(["POST"])
def toggle_route_status(request, pk):
    """AJAX view để bật/tắt trạng thái lộ trình."""
    route = get_object_or_404(BusRoute, pk=pk)
    try:
        data = json.loads(request.body)
        is_active = data.get('is_active', not route.is_active)
        route.is_active = is_active
        route.save(update_fields=['is_active'])
        return JsonResponse({'success': True, 'is_active': route.is_active})
    except Exception as e:
        logger.error(f"Error toggling route status for {pk}: {e}")
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@staff_required
@login_required
@require_http_methods(["POST"])
def delete_route(request, pk):
    """AJAX view để xóa lộ trình."""
    route = get_object_or_404(BusRoute, pk=pk)
    try:
        route.delete()
        return JsonResponse({'success': True, 'message': 'Lộ trình đã được xóa.'})
    except Exception as e:
        logger.error(f"Error deleting route {pk}: {e}")
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

# Book Donation Views
class BookDonationCreateView(LoginRequiredMixin, CreateView):
    model = BookDonation
    form_class = BookDonationForm
    template_name = 'inventory/donation_form.html'
    success_url = reverse_lazy('inventory:book_list')
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Cảm ơn bạn đã đóng góp! Thông tin sách đã được gửi tới Quản trị viên để phê duyệt.')
        return super().form_valid(form)

class BookDonationListView(AdminRequiredMixin, ListView):
    model = BookDonation
    template_name = 'inventory/donation_list.html'
    context_object_name = 'donations'
    paginate_by = 20
    
    def get_queryset(self):
        status = self.request.GET.get('status')
        qs = BookDonation.objects.select_related('user').order_by('-created_at')
        if status:
            qs = qs.filter(status=status)
        return qs

@staff_required
@login_required
@require_http_methods(["POST"])
def donation_status_change(request, pk):
    donation = get_object_or_404(BookDonation, pk=pk)
    new_status = request.POST.get('status')
    if new_status in dict(BookDonation.DONATION_STATUS_CHOICES):
        donation.status = new_status
        donation.save()
        messages.success(request, f'Trạng thái sách quyên góp "{donation.book_title}" đã được cập nhật thành "{donation.get_status_display()}".')
    return redirect('inventory:donation_list')

from django.http import JsonResponse

@login_required
def autocomplete_books(request):
    query = request.GET.get('q', '')
    if len(query) >= 2:
        # Search by title or author
        books = Book.objects.filter(
            Q(title__icontains=query) | Q(author__icontains=query)
        ).values('title', 'author', 'id')[:10]
        results = [{'title': b['title'], 'author': b['author'], 'id': str(b['id'])} for b in books]
        return JsonResponse({'results': results})
    return JsonResponse({'results': []})

from django.views import View
from .models import BookRating

class RateBookView(LoginRequiredMixin, View):
    def post(self, request, pk):
        book = get_object_or_404(Book, pk=pk)
        try:
            rating_val = int(request.POST.get('rating'))
            if 1 <= rating_val <= 5:
                BookRating.objects.update_or_create(
                    book=book,
                    user=request.user,
                    defaults={'rating': rating_val}
                )
                messages.success(request, 'Cảm ơn bạn đã đánh giá cuốn sách này!')
            else:
                messages.error(request, 'Số sao không hợp lệ.')
        except (ValueError, TypeError):
            messages.error(request, 'Dữ liệu đánh giá không hợp lệ.')
        
        return redirect('inventory:book_detail', pk=book.pk)