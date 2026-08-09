import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_bus_project.settings')
django.setup()

from inventory.models import LibraryBus, BusRoute

def create_sample_routes():
    # Lấy xe bus đầu tiên
    bus = LibraryBus.objects.first()
    if not bus:
        print("Không có xe bus nào trong hệ thống. Đang tạo xe bus mẫu...")
        bus = LibraryBus.objects.create(
            name="Bus Sách Tri Thức 01",
            license_plate="29A-12345",
            latitude=21.028511,
            longitude=105.804817,
            location_name="Hà Nội",
            operating_status="active"
        )
    
    routes_data = [
        {
            "route_name": "Tuyến Nội thành Hà Nội - Số 1",
            "stops": [
                {"name": "Hồ Gươm", "lat": 21.0285, "lng": 105.8522, "duration": 120},
                {"name": "Đại học Bách Khoa", "lat": 21.0042, "lng": 105.8437, "duration": 180},
                {"name": "Công viên Thống Nhất", "lat": 21.0163, "lng": 105.8451, "duration": 90}
            ],
            "schedule": {
                "monday": ["08:00", "14:00"],
                "wednesday": ["08:00", "14:00"],
                "friday": ["08:00", "14:00"]
            }
        },
        {
            "route_name": "Tuyến Cầu Giấy - Thanh Xuân",
            "stops": [
                {"name": "Đại học Quốc Gia", "lat": 21.0378, "lng": 105.7818, "duration": 180},
                {"name": "Công viên Cầu Giấy", "lat": 21.0315, "lng": 105.7925, "duration": 120},
                {"name": "Ngã tư Sở", "lat": 21.0039, "lng": 105.8198, "duration": 90}
            ],
            "schedule": {
                "tuesday": ["09:00", "15:00"],
                "thursday": ["09:00", "15:00"],
                "saturday": ["09:00", "15:00"]
            }
        }
    ]

    count = 0
    for data in routes_data:
        route, created = BusRoute.objects.get_or_create(
            bus=bus,
            route_name=data["route_name"],
            defaults={
                "stops": data["stops"],
                "schedule": data["schedule"],
                "is_active": True
            }
        )
        if created:
            count += 1
            print(f"Đã tạo lộ trình: {route.route_name}")
        else:
            print(f"Lộ trình đã tồn tại: {route.route_name}")

    print(f"Đã hoàn thành! Tạo thành công {count} lộ trình.")

if __name__ == '__main__':
    create_sample_routes()
