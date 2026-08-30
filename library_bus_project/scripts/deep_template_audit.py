import os
import re
import sys
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / 'template'
STATIC_DIR = BASE_DIR / 'static'

templates = sorted(list(TEMPLATE_DIR.rglob('*.html')))

print(f"==================================================================")
print(f"   🔎 TOÀN DIỆN KIỂM TOÁN TẤT CẢ {len(templates)} TEMPLATES THEO IMPECCABLE")
print(f"==================================================================")

# 1. Check template inheritance
no_inheritance = []
for t in templates:
    content = t.read_text(encoding='utf-8', errors='ignore')
    # If it's not base.html, partial, or email template, it should have extends or include
    is_base = t.name.startswith('base') or t.name == '404.html'
    is_partial = 'partials' in t.as_posix() or t.name.startswith('_')
    is_email = 'emails' in t.as_posix() or 'email' in t.name
    
    if not (is_base or is_partial or is_email):
        if '{% extends' not in content:
            no_inheritance.append(t.relative_to(BASE_DIR).as_posix())

print("\n1. Kiểm tra thừa kế Base Layout (Global Tokens, Surfaces & CSS):")
if not no_inheritance:
    print(f"  ✅ 100% templates người dùng ({len(templates) - len(no_inheritance)}/{len(templates)}) đều kế thừa trực tiếp/gián tiếp base.html.")
else:
    print(f"  ⚠️  Có {len(no_inheritance)} templates không kế thừa base:")
    for item in no_inheritance:
        print(f"     • {item}")

# 2. Check for leftover eyebrows / kickers
print("\n2. Kiểm tra lệnh cấm Eyebrow / Kicker (Craft Floor Ban):")
eyebrow_regex = re.compile(r'class="[^"]*(?:hero-badge|section-badge|eyebrow|kicker)[^"]*"', re.IGNORECASE)
found_eyebrows = []
for t in templates:
    content = t.read_text(encoding='utf-8', errors='ignore')
    matches = eyebrow_regex.findall(content)
    if matches:
        found_eyebrows.append((t.relative_to(BASE_DIR).as_posix(), len(matches)))

if not found_eyebrows:
    print("  ✅ 100% các trang sạch bóng Eyebrows/Kickers (Đạt chuẩn Impeccable Craft Floor).")
else:
    print(f"  ⚠️  Phát hiện {len(found_eyebrows)} templates còn chứa eyebrow/kicker:")
    for path, count in found_eyebrows:
        print(f"     • {path}: {count} eyebrows")

# 3. Check for leftover em-dashes
print("\n3. Kiểm tra dấu gạch ngang Em-Dash (—):")
em_dash_regex = re.compile(r'—')
found_dashes = []
for t in templates:
    content = t.read_text(encoding='utf-8', errors='ignore')
    lines = content.splitlines()
    for line_idx, line in enumerate(lines, 1):
        if '<!--' in line or '//' in line or '/*' in line:
            continue
        if em_dash_regex.search(line):
            found_dashes.append((t.relative_to(BASE_DIR).as_posix(), line_idx, line.strip()))

if not found_dashes:
    print("  ✅ 100% templates sạch dấu gạch ngang em-dash trong text hiển thị.")
else:
    print(f"  ⚠️  Phát hiện {len(found_dashes)} chỗ còn dấu em-dash:")
    for path, lnum, txt in found_dashes[:5]:
        print(f"     • {path}:{lnum} -> {txt[:60]}...")

# 4. Check for untinted black/gray colors in inline styles
print("\n4. Kiểm tra mã màu cấm / Untinted Black (#000, #000000, AI purple):")
forbidden_pattern = re.compile(r'#000000(?![a-fA-F0-9])|(?<![a-zA-Z0-9_-])#000(?![a-zA-Z0-9_-])|#667eea|#764ba2')
found_colors = []
for t in templates:
    content = t.read_text(encoding='utf-8', errors='ignore')
    lines = content.splitlines()
    for line_idx, line in enumerate(lines, 1):
        if forbidden_pattern.search(line):
            found_colors.append((t.relative_to(BASE_DIR).as_posix(), line_idx, line.strip()))

if not found_colors:
    print("  ✅ 100% templates không chứa mã màu cấm (#000, gradient tím AI).")
else:
    print(f"  ⚠️  Phát hiện {len(found_colors)} chỗ còn chứa mã màu cấm:")
    for path, lnum, txt in found_colors:
        print(f"     • {path}:{lnum} -> {txt[:60]}...")

print("\n==================================================================")
