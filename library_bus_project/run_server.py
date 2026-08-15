import os
from waitress import serve
from library_bus_project.wsgi import application

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    print(f"Bắt đầu khởi chạy Waitress Server (Production Mode) tại cổng {port} với 500 threads...")
    print("WARNING: Đảm bảo bạn đã tăng max_connections trong cấu hình MySQL (my.ini) lên >= 600!")
    
    # Khởi chạy waitress với cấu hình threads=500 để chịu tải 500 concurrent requests
    serve(application, host='0.0.0.0', port=port, threads=500)
