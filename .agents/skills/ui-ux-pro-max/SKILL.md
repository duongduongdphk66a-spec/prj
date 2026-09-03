---
name: ui-ux-pro-max
description: AI-powered design intelligence for building professional UI/UX. Includes 84 UI styles, 192 color palettes, 74 font pairings, 98 UX guidelines, 25 chart types, 192 reasoning rules, and 3 design dials (variance, motion, density). Use when designing interfaces, selecting typography/color palettes, implementing animations (GSAP), optimizing accessibility (WCAG), or generating comprehensive design systems.
---

# UI/UX Pro Max Design Intelligence Skill

This skill provides design intelligence, design dials, semantic token rules, UX best practices, and pre-delivery checklists derived from NextLevelBuilder's `ui-ux-pro-max-skill`.

---

## 1. Design Dials System (1-10)

Fine-tune design decisions using three dials that modulate creativity, interaction fidelity, and information density:

### A. Design Variance (`--variance`: 1-10)
- **1 - 3 (Centered / Minimal)**: Clean, symmetric, grid-based, low cognitive load, corporate/utility clarity.
- **4 - 7 (Balanced / Modern)**: Structured yet organic, intentional asymmetry, generous typography scales, avoids rigid "card soup" repetition.
- **8 - 10 (Bold / Asymmetric)**: Bento box grids, experimental visual rhythm, magazine editorial pacing, high artistic expression.

### B. Motion Intensity (`--motion`: 1-10)
- **1 - 3 (Subtle)**: Fast micro-interactions (150-200ms), CSS transitions only, no scroll hijacking.
- **4 - 7 (Standard)**: Tactile spring curves (`back.out(1.4)`), scroll-triggered reveal batches (`ScrollTrigger.batch`), stagger delays (0.08s).
- **8 - 10 (Complex)**: Multi-layer parallax, SVG morphing, number ticker animations, cinematic hero timelines.
- *Strict Rule*: Always wrap animations in `prefers-reduced-motion` queries and animate only compositor properties (`transform`, `opacity`/`autoAlpha`).

### C. Visual Density (`--density`: 1-10)
- **1 - 3 (Spacious)**: Marketing, luxury, literature, long-form editorial (xs: 4px, sm: 8px, md: 24px, lg: 32px, xl: 48px, 2xl: 64px, 3xl: 96px).
- **4 - 7 (Standard)**: Typical web apps, e-commerce, user settings (xs: 4px, sm: 8px, md: 16px, lg: 24px, xl: 32px, 2xl: 48px, 3xl: 64px).
- **8 - 10 (Dense / Dashboard)**: Data tables, analytics, bus dispatch control, inventory tables (xs: 2px, sm: 4px, md: 8px, lg: 12px, xl: 16px, 2xl: 24px, 3xl: 32px).

---

## 2. Canonical 16-Token Semantic Color System

Every theme MUST expose these 16 variables to ensure interchangeable components and consistent contrast:

```css
:root {
  --color-primary:          #...; /* Main brand call-to-action */
  --color-on-primary:       #...; /* High contrast text on primary */
  --color-secondary:        #...; /* Secondary actions & badges */
  --color-on-secondary:     #...; /* High contrast text on secondary */
  --color-accent:           #...; /* Highlights, badges, active tabs */
  --color-on-accent:        #...; /* Text on accent */
  --color-background:       #...; /* Page ground canvas */
  --color-foreground:       #...; /* Default body text */
  --color-card:             #...; /* Elevated card surface */
  --color-card-foreground:  #...; /* Card body text */
  --color-muted:            #...; /* Recessed/sunken inputs & chips */
  --color-muted-foreground: #...; /* Subtle text, timestamps, captions */
  --color-border:           #...; /* Hairline borders & dividers */
  --color-destructive:      #...; /* Error states, delete actions */
  --color-on-destructive:   #...; /* Text on destructive */
  --color-ring:             #...; /* Focus ring indicator */
}
```

---

## 3. Core UX Guidelines & Anti-Patterns (98 Rules Summary)

### Navigation & Layout
- **Skip Links**: Always provide `<a href="#main-content" class="skip-link">` for keyboard & screen reader users.
- **Semantic Elements**: Never create "div soup". Use `<header>`, `<nav>`, `<main>`, `<article>`, `<aside>`, `<footer>`.
- **Sticky Nav Compensation**: When navigation is fixed/sticky, add appropriate padding-top or layout reservation to prevent hero overlap.
- **No Cumulative Layout Shift (CLS)**: Always set `aspect-ratio` on book covers, avatars, and media slots.

### Touch & Mobile First
- **Touch Target Size**: Minimum `44px x 44px` on mobile for every clickable icon, button, checkbox, and pagination item.
- **Touch Spacing**: Minimum 8px gap between adjacent touch targets.
- **Responsive Testing**: Seamless across 375px (mobile), 768px (tablet), 1024px (small desktop), 1440px (wide screen).

### Interaction & Accessibility
- **Focus States**: Never use `outline: none` without providing a visible, high-contrast `:focus-visible` ring.
- **Text Contrast**: Minimum 4.5:1 ratio for normal text (WCAG AA) and 7:1 (WCAG AAA).
- **Tabular Numerals**: Apply `font-variant-numeric: tabular-nums` to numbers, dates, timestamps, and stat metrics to avoid layout jank.
- **Color Independence**: Never rely on color alone to communicate state. Combine colors with icons and descriptive text labels.

### Icons & Imagery
- **No Emojis as Icons**: Strictly forbidden to use emojis (e.g. 📚, 🚌, 🔒, ✅, ⚠) as UI control icons. Use standard SVGs (Lucide, Heroicons, FontAwesome).
- **Descriptive Alt Text**: All meaningful images must contain contextual `alt` attributes. Decorative images should have `alt=""` and `aria-hidden="true"`.

---

## 4. Pre-Delivery Checklist

Before completing any frontend UI task, verify each item:
- [ ] No emojis as icons (use SVG / FontAwesome).
- [ ] `cursor: pointer` on all clickable elements.
- [ ] Interaction timing follows 150-250ms feedback curves.
- [ ] Text contrast meets minimum 4.5:1 (WCAG AA/AAA).
- [ ] Focus states visible for keyboard navigation (`:focus-visible`).
- [ ] `prefers-reduced-motion` respected in CSS & GSAP.
- [ ] Text, chips, and badges reflow without horizontal clipping.
- [ ] Responsive layouts verified at 375px, 768px, 1024px, 1440px.
- [ ] Touch target size is at least 44px on mobile devices.
- [ ] Skip link is present and working.
