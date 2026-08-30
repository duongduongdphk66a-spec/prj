#!/usr/bin/env python3
"""
Image Optimization Utility
==========================
Converts static PNG/JPEG images to optimized WebP format with quality retention.
Reduces network payload for fast landing page loads.
"""

import sys
from pathlib import Path
from PIL import Image

if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_IMG_DIR = BASE_DIR / 'static' / 'img'

def optimize_images():
    print("==================================================================")
    print("  🖼️  IMAGE OPTIMIZATION PIPELINE — LIBRARY BUS PROJECT            ")
    print("==================================================================")
    
    if not STATIC_IMG_DIR.exists():
        print(f"Directory {STATIC_IMG_DIR} does not exist.")
        return

    total_original_size = 0
    total_optimized_size = 0

    for file in STATIC_IMG_DIR.iterdir():
        if file.is_file() and file.suffix.lower() in ['.png', '.jpg', '.jpeg']:
            original_size = file.stat().st_size
            total_original_size += original_size
            
            webp_path = file.with_suffix('.webp')
            try:
                with Image.open(file) as img:
                    # Convert RGBA to RGB if saving with lossy compression or preserve alpha
                    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                        img.save(webp_path, 'WEBP', quality=85, method=6)
                    else:
                        img.convert('RGB').save(webp_path, 'WEBP', quality=85, method=6)
                
                webp_size = webp_path.stat().st_size
                total_optimized_size += webp_size
                savings = (1 - webp_size / original_size) * 100
                print(f"  ✅ Converted: {file.name} ({original_size / 1024:.1f} KB) -> {webp_path.name} ({webp_size / 1024:.1f} KB) [Savings: {savings:.1f}%]")
            except Exception as e:
                print(f"  ❌ Error optimizing {file.name}: {e}")

    if total_original_size > 0:
        total_savings = (1 - total_optimized_size / total_original_size) * 100
        print("\n------------------------------------------------------------------")
        print(f"  🎉 Total Original:  {total_original_size / (1024 * 1024):.2f} MB")
        print(f"  🚀 Total Optimized: {total_optimized_size / (1024 * 1024):.2f} MB")
        print(f"  ⚡ Overall Savings: {total_savings:.1f}% bandwidth reduction")
        print("==================================================================")

if __name__ == '__main__':
    optimize_images()
