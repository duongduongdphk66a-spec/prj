// File: blog/static/blog/js/blog_scripts.js
document.addEventListener('DOMContentLoaded', function() {

    // Lấy CSRF token từ cookie
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    const csrftoken = getCookie('csrftoken');

    // Xử lý Like/Unlike
    const likeButton = document.getElementById('like-btn');
    if (likeButton) {
        likeButton.addEventListener('click', function(e) {
            e.preventDefault();
            const postId = this.dataset.postId;
            const url = `/blog/post/${postId}/like/`;

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'X-Requested-With': 'XMLHttpRequest',
                },
            })
            .then(response => response.json())
            .then(data => {
                if (data.liked) {
                    this.classList.add('active'); // Thêm class để đổi style
                    this.innerHTML = `<i class="fas fa-heart"></i> Liked`;
                } else {
                    this.classList.remove('active');
                    this.innerHTML = `<i class="far fa-heart"></i> Like`;
                }
                // Cập nhật số lượt thích
                const likeCountSpan = document.getElementById('like-count');
                if (likeCountSpan) {
                    likeCountSpan.textContent = data.like_count;
                }
            })
            .catch(error => console.error('Error:', error));
        });
    }

    // Xử lý Rating
    const ratingForm = document.getElementById('rating-form');
    if (ratingForm) {
        ratingForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const postId = this.dataset.postId;
            const url = `/blog/post/${postId}/rate/`;
            const formData = new FormData(this);

            fetch(url, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': csrftoken,
                    'X-Requested-With': 'XMLHttpRequest',
                },
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Cập nhật hiển thị rating
                    document.getElementById('avg-rating').textContent = data.avg_rating;
                    document.getElementById('rating-count').textContent = data.rating_count;
                    alert('Cảm ơn bạn đã đánh giá!');
                } else {
                    alert('Lỗi: ' + data.error);
                }
            })
            .catch(error => console.error('Error:', error));
        });
    }

    // Xử lý thêm comment
    const commentForm = document.getElementById('comment-form');
    if (commentForm) {
        commentForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const postId = this.dataset.postId;
            const url = `/blog/post/${postId}/comment/`;
            const formData = new FormData(this);

            fetch(url, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': csrftoken,
                    'X-Requested-With': 'XMLHttpRequest',
                },
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Thêm comment mới vào danh sách mà không cần reload
                    const commentList = document.querySelector('.comment-list');
                    commentList.insertAdjacentHTML('afterbegin', data.comment_html);
                    this.reset(); // Xóa nội dung form
                } else {
                    alert('Lỗi: ' + (data.error || 'Không thể gửi bình luận.'));
                }
            })
            .catch(error => console.error('Error:', error));
        });
    }
});