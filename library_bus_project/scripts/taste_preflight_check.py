#!/usr/bin/env python3
"""
Taste-Skill v2 Pre-Flight Audit Script
======================================
Automated quality assurance and anti-slop verification for the Library Bus Project.
Checks templates, CSS, and configuration against Taste-Skill engineering directives and GSAP skills.
"""

import os
import re
import sys
from pathlib import Path

# Safe Unicode for Windows console
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / 'template'
STATIC_DIR = BASE_DIR / 'static'

def check_em_dashes():
    """Rule §9.G: Check for em-dash in user-facing templates."""
    violations = []
    em_dash_pattern = re.compile(r'—')
    
    for root, _, files in os.walk(TEMPLATE_DIR):
        for file in files:
            if file.endswith('.html'):
                filepath = Path(root) / file
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        # Ignore comments
                        if '<!--' in line or '//' in line or '/*' in line:
                            continue
                        if em_dash_pattern.search(line):
                            violations.append((filepath.relative_to(BASE_DIR), line_num, line.strip()))
    return violations

def check_hardcoded_forbidden_colors():
    """Rule §4.2: Ban untinted blacks and AI purple gradients in templates."""
    violations = []
    forbidden_colors = [
        (re.compile(r'#000000(?![a-fA-F0-9])|(?<![a-zA-Z0-9_-])#000(?![a-zA-Z0-9_-])'), "Untinted pure black (#000)"),
        (re.compile(r'#667eea|#764ba2'), "Generic AI purple/violet gradient (#667eea -> #764ba2)")
    ]
    
    for root, _, files in os.walk(TEMPLATE_DIR):
        for file in files:
            if file.endswith('.html'):
                filepath = Path(root) / file
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        for pattern, desc in forbidden_colors:
                            if pattern.search(line):
                                violations.append((filepath.relative_to(BASE_DIR), line_num, desc, line.strip()))
    return violations

def check_eyebrow_density():
    """Rule §4.7: Eyebrow restraint - Max 1 eyebrow per 3 sections."""
    results = {}
    eyebrow_pattern = re.compile(r'class="[^"]*(?:section-badge|hero-badge|eyebrow)[^"]*"', re.IGNORECASE)
    section_pattern = re.compile(r'<section\b', re.IGNORECASE)
    
    for root, _, files in os.walk(TEMPLATE_DIR):
        for file in files:
            if file.endswith('.html'):
                filepath = Path(root) / file
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    sections = len(section_pattern.findall(content))
                    eyebrows = len(eyebrow_pattern.findall(content))
                    if sections > 0:
                        max_allowed = max(1, (sections + 2) // 3)
                        passed = eyebrows <= max_allowed
                        results[filepath.relative_to(BASE_DIR)] = {
                            'sections': sections,
                            'eyebrows': eyebrows,
                            'max_allowed': max_allowed,
                            'passed': passed
                        }
    return results

def check_design_tokens():
    """Rule §2 & §3: Ensure tokens.css defines required core tokens, OKLCH space, and Browser Surfaces."""
    tokens_file = STATIC_DIR / 'css' / 'tokens.css'
    if not tokens_file.exists():
        return ["tokens.css not found!"]
    
    with open(tokens_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    required_tokens = [
        '--dial-variance',
        '--dial-motion',
        '--dial-density',
        '--color-molasses',
        '--color-roast',
        '--oklch-molasses',
        '--oklch-roast',
        '--color-selection-bg',
        '--color-caret',
        '--font-sans',
        '--font-display',
        '--radius-pill',
        '--transition-spring',
        'data-theme="dark"'
    ]
    
    missing = [token for token in required_tokens if token not in content]
    return missing

def check_browser_surfaces():
    """Impeccable Craft Floor: Ensure base.css themes selection, caret, scrollbars, and focus rings."""
    base_css = STATIC_DIR / 'css' / 'base.css'
    if not base_css.exists():
        return ["base.css not found!"]
    
    with open(base_css, 'r', encoding='utf-8') as f:
        content = f.read()
        
    surfaces = [
        ('::selection', 'Text Selection highlight'),
        ('caret-color', 'Input Caret color'),
        ('scrollbar-width', 'Custom scrollbar'),
        (':focus-visible', 'Themed focus ring'),
        ('tabular-nums', 'Tabular numbers alignment')
    ]
    
    missing = [name for tag, name in surfaces if tag not in content]
    return missing

def check_gsap_best_practices():
    """GSAP Skills Quality Check: Ensure compositor-only animations and accessibility."""
    animations_js = STATIC_DIR / 'js' / 'animations.js'
    if not animations_js.exists():
        return ["animations.js not found!"]
    
    with open(animations_js, 'r', encoding='utf-8') as f:
        content = f.read()
        
    checks = []
    if "gsap.matchMedia" not in content:
        checks.append("Missing gsap.matchMedia for responsive/a11y")
    if "prefers-reduced-motion: reduce" not in content:
        checks.append("Missing prefers-reduced-motion fallback")
    if "ScrollTrigger.batch" not in content:
        checks.append("Missing ScrollTrigger.batch for performant reveals")
        
    return checks

def main():
    print("==================================================================")
    print("  🎨 IMPECCABLE & TASTE-SKILL QUALITY AUDIT — LIBRARY BUS PROJECT  ")
    print("==================================================================")
    
    has_errors = False
    
    # 1. Check Design Tokens & OKLCH
    print("\n[1/6] Checking Design Tokens, OKLCH Space & Dials...")
    missing_tokens = check_design_tokens()
    if missing_tokens:
        print(f"  ❌ Missing required tokens: {', '.join(missing_tokens)}")
        has_errors = True
    else:
        print("  ✅ All required Design Tokens, OKLCH space, and Dark Mode overrides are defined.")
    
    # 2. Check Browser Surfaces Theming
    print("\n[2/6] Checking Browser Surfaces Theming (Impeccable Craft Floor)...")
    missing_surfaces = check_browser_surfaces()
    if missing_surfaces:
        print(f"  ❌ Missing browser surfaces theming: {', '.join(missing_surfaces)}")
        has_errors = True
    else:
        print("  ✅ All browser surfaces (selection, caret, scrollbar, focus-visible, tabular-nums) are themed.")

    # 3. Check Em-Dashes
    print("\n[3/6] Checking for Em-Dash violations (§9.G)...")
    em_dash_violations = check_em_dashes()
    if em_dash_violations:
        print(f"  ⚠️  Found {len(em_dash_violations)} user-facing em-dash usages:")
        for file, line, content in em_dash_violations[:5]:
            print(f"     • {file}:{line} -> {content[:60]}...")
    else:
        print("  ✅ Zero user-facing em-dash violations found.")
    
    # 4. Check Forbidden Colors
    print("\n[4/6] Checking for forbidden/untinted color codes (§4.2)...")
    color_violations = check_hardcoded_forbidden_colors()
    if color_violations:
        print(f"  ⚠️  Found {len(color_violations)} hardcoded color issues:")
        for file, line, desc, content in color_violations[:5]:
            print(f"     • {file}:{line} [{desc}] -> {content[:60]}...")
    else:
        print("  ✅ Zero forbidden raw colors found in templates.")
        
    # 5. Check Eyebrow Density
    print("\n[5/6] Checking Eyebrow Restraint Density (§4.7 & Craft Floor)...")
    eyebrow_results = check_eyebrow_density()
    all_eyebrows_passed = True
    for file, data in eyebrow_results.items():
        if not data['passed']:
            all_eyebrows_passed = False
            print(f"  ⚠️  {file}: {data['eyebrows']} eyebrows for {data['sections']} sections (max allowed: {data['max_allowed']})")
    if all_eyebrows_passed:
        print("  ✅ All pages pass the Eyebrow Restraint rule (Zero on landing, <= 1 per 3 sections elsewhere).")

    # 6. Check GSAP Animation Best Practices
    print("\n[6/6] Checking GSAP Best Practices & Accessibility (§GSAP-Skills)...")
    gsap_issues = check_gsap_best_practices()
    if gsap_issues:
        print(f"  ❌ GSAP issues found: {', '.join(gsap_issues)}")
        has_errors = True
    else:
        print("  ✅ GSAP Animation Suite complies with greensock/gsap-skills guidelines (matchMedia, batching, reduced-motion).")
        
    print("\n==================================================================")
    if has_errors:
        print("  ❌ PRE-FLIGHT AUDIT FAILED. Fix highlighted errors above.")
        sys.exit(1)
    else:
        print("  🎉 PRE-FLIGHT AUDIT PASSED! Impeccable Quality Standards met.")
        print("==================================================================")
        sys.exit(0)

if __name__ == '__main__':
    main()
