import os
import re
import glob
import sys
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

template_dir = Path('template')
templates = list(template_dir.rglob('*.html'))

print(f"=== AUDIT OF ALL {len(templates)} HTML TEMPLATES ===")

# App base layouts
app_bases = [
    'template/base.html',
    'template/analytics/base_analytics.html',
    'template/blog/baseblog.html',
    'template/inventory/base_inventory.html',
    'template/notifications/base_notifications.html',
    'template/transactions/base_transactions.html',
    'template/users/base_user.html'
]

print("\n--- 1. App Base Layouts Status ---")
for b in app_bases:
    p = Path(b)
    if p.exists():
        content = p.read_text(encoding='utf-8', errors='ignore')
        has_tokens = 'tokens.css' in content or 'extends "base.html"' in content or "extends 'base.html'" in content
        print(f"  • {b}: Inherits base/tokens: {has_tokens}")
    else:
        print(f"  • {b}: NOT FOUND")

print("\n--- 2. Templates with Internal <style> blocks ---")
styled_templates = []
for t in templates:
    content = t.read_text(encoding='utf-8', errors='ignore')
    if '<style>' in content:
        styled_templates.append(t.as_posix())

print(f"Total templates with custom <style> blocks: {len(styled_templates)}")
for s in sorted(styled_templates):
    print(f"  • {s}")

print("\n--- 3. Templates with raw hex inline colors ---")
hex_pattern = re.compile(r'style=[\'"][^\'"]*#[0-9a-fA-F]{3,6}', re.IGNORECASE)
raw_colored = []
for t in templates:
    content = t.read_text(encoding='utf-8', errors='ignore')
    matches = hex_pattern.findall(content)
    if matches:
        raw_colored.append((t.as_posix(), len(matches)))

print(f"Total templates with inline raw hex colors: {len(raw_colored)}")
for path, count in sorted(raw_colored, key=lambda x: x[1], reverse=True):
    print(f"  • {path}: {count} inline hex styles")
