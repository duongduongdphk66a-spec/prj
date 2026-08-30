import os
from waitress import serve
from library_bus_project.wsgi import application

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting Waitress Server (Production Mode) on port {port} with 500 threads...")
    print("WARNING: Make sure you have increased max_connections in MySQL config (my.ini) to >= 600!")
    
    # Khởi chạy waitress với cấu hình threads=500 để chịu tải 500 concurrent requests
    serve(application, host='0.0.0.0', port=port, threads=500)
