import os
import django
import random
from faker import Faker
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_bus_project.settings')
django.setup()

from django.contrib.auth.models import User
from blog.models import Post, Comment, BlogCategory

fake = Faker('vi_VN')

def create_blog_data():
    print("Starting blog data generation...")
    
    users = list(User.objects.all())
    if not users:
        print("Error: No users found!")
        return
    
    # Đảm bảo có ít nhất 1 category
    categories = list(BlogCategory.objects.all())
    if not categories:
        print("Creating default categories...")
        cat1 = BlogCategory.objects.create(name="Sự kiện sắp tới", slug="su-kien-sap-toi")
        cat2 = BlogCategory.objects.create(name="Góc Review", slug="goc-review")
        categories = [cat1, cat2]
        
    print("Creating 50 blog posts...")
    posts_created = 0
    posts = []
    
    # Cố gắng lặp nhiều hơn phòng trường hợp trùng title
    for _ in range(100):
        if posts_created >= 50:
            break
            
        author = random.choice(users)
        title = fake.sentence(nb_words=6) + " " + str(random.randint(1000, 99999))
        content = "\n\n".join(fake.paragraphs(nb=5))
        
        try:
            post = Post.objects.create(
                title=title,
                content=content,
                author=author,
                status='published',
                publish_date=timezone.now()
            )
            # Thêm ngẫu nhiên 1-2 category
            post.categories.set(random.sample(categories, k=random.randint(1, min(2, len(categories)))))
            posts.append(post)
            posts_created += 1
        except Exception as e:
            pass # Bỏ qua nếu bị lỗi unique constraint
        
    print(f"Created {len(posts)} posts.")
    
    if not posts:
        print("Error: Could not create any posts.")
        return
        
    print("Creating 150 comments...")
    comments_created = 0
    for _ in range(150):
        post = random.choice(posts)
        author = random.choice(users)
        content = fake.paragraph(nb_sentences=3)
        
        try:
            Comment.objects.create(
                post=post,
                author=author,
                content=content,
                is_approved=True
            )
            comments_created += 1
        except Exception as e:
            pass
            
    print(f"Successfully created {comments_created} comments.")
    
    from django.core.cache import cache
    cache.clear()
    print("Cleared Django cache to show new posts immediately.")
    
    print("Blog data generation completed!")

if __name__ == '__main__':
    create_blog_data()
