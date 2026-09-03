# Tủ Sách Lưu Động — Design System Master

> **Source of Truth**: Generated following UI/UX Pro Max Architecture (NextLevelBuilder v2.13+)  
> **Platform**: Django 5.x + Modern Web Frontend  
> **Design Register**: Hybrid (Cultural Brand Surface + Data-Dense Product Surface)  

---

## 1. Design System Summary & Reasoning

| Field | Specification |
| :--- | :--- |
| **Product Domain** | Public Service & Cultural Education (Library Bus Fleet & Digital Borrowing) |
| **Recommended Pattern** | *Storytelling-Driven + Hero-Centric + Social Proof* (Public) / *Data-Dense Dashboard* (Admin) |
| **Style Priority** | *Editorial Warmth (Neo-Bakery & Classic Library) + Bento Box Grid + Accessible & Ethical* |
| **Design Dials** | `--variance: 7` (Asymmetric rhythm) \| `--motion: 6` (Tactile spring curves) \| `--density: 4` (Public) / `8` (Admin) |
| **Primary Typography** | `Lora` (Serif Display & Storytelling) + `Outfit` (Sans-Serif Controls & Metrics) |
| **Monospace** | `JetBrains Mono` (Code & Barcode IDs) |
| **Core Color Anchor** | 6-Tone Molasses-Butter Palette (Mahogany Ink on Ivory Paper) |

---

## 2. Design Dials Configuration

```css
:root {
  /* Dials Configuration */
  --dial-variance: 7; /* Asymmetric editorial pacing, avoiding monotonous 3-card repetition */
  --dial-motion:   6; /* Tactile spring curves, ScrollTrigger batching, number counters */
  --dial-density:  4; /* Generous literary breathing room on public pages */
}
```

- **Variance (7)**: Employs varied card scales (e.g. 2:1 bento featured hero cards, 1:1 secondary book items) rather than rigid uniform rows.
- **Motion (6)**: Interactive elements react with spring easing (`cubic-bezier(0.175, 0.885, 0.32, 1.275)`). Scroll revelations use `ScrollTrigger.batch()`.
- **Density (4 / 8)**: Marketing and catalog exploration utilize airy spacing (24px - 32px gap), while librarian checkout and inventory tables use compact density (8px - 12px padding).

---

## 3. Canonical 16-Token Semantic Palette

### Light Mode (Ivory Canvas)
```css
:root {
  --color-primary:          #BD5705; /* Roast: caramel bronze call-to-action */
  --color-on-primary:       #FFFFFF; /* Pure crisp white text */
  --color-secondary:        #812203; /* Well-browned: roasted chestnut accent */
  --color-on-secondary:     #FFFDF9; /* Ivory white on secondary */
  --color-accent:           #ED9040; /* Toasty: amber orange highlight */
  --color-on-accent:        #4E0705; /* Molasses text on amber */
  --color-background:       #FFFDF9; /* Crisp ivory paper ground */
  --color-foreground:       #3A0806; /* High-contrast molasses ink (WCAG AAA 11.2:1) */
  --color-card:             #FFFFFF; /* Elevated card surface */
  --color-card-foreground:  #3A0806; /* Body text inside cards */
  --color-muted:            #F4ECE1; /* Sunken input & chip background */
  --color-muted-foreground: #96523E; /* Muted terracotta for secondary meta */
  --color-border:           rgba(129, 34, 3, 0.16); /* Hairline roasted divider */
  --color-destructive:      #A31B18; /* Warm crimson danger token */
  --color-on-destructive:   #FFFFFF; /* White on danger button */
  --color-ring:             #BD5705; /* High visibility focus ring indicator */
}
```

### Dark Mode (Espresso Canvas)
```css
[data-theme="dark"] {
  --color-primary:          #ED9040; /* Toasty: warm amber glow */
  --color-on-primary:       #170706; /* Deep espresso text on primary */
  --color-secondary:        #FFC270; /* Greasey: warm honey butter */
  --color-on-secondary:     #170706;
  --color-accent:           #FDE971; /* Butter: soft pastry highlight */
  --color-on-accent:        #170706;
  --color-background:       #170706; /* Deep molasses night */
  --color-foreground:       #FFF5EB; /* Crisp warm eggshell text (WCAG AAA) */
  --color-card:             #2B100E; /* Elevated dark card surface */
  --color-card-foreground:  #FFF5EB;
  --color-muted:            #1D0908; /* Sunken dark input background */
  --color-muted-foreground: #B88675; /* Soft terracotta meta */
  --color-border:           rgba(255, 194, 112, 0.18); /* Honey hairline */
  --color-destructive:      #E53E3E;
  --color-on-destructive:   #FFFFFF;
  --color-ring:             #ED9040;
}
```

---

## 4. Typography Scale & Hierarchy

| Token | Size | Weight | Font Family | Usage |
| :--- | :--- | :--- | :--- | :--- |
| `display-1` | `clamp(2.4rem, 4.5vw, 3.6rem)` | 800/900 | `Lora`, serif | Hero Display Title |
| `heading-1` | `clamp(2.0rem, 3.8vw, 2.75rem)` | 700 | `Lora`, serif | Major Page Section Title |
| `heading-2` | `clamp(1.5rem, 2.8vw, 2.0rem)` | 700 | `Lora`, serif | Sub-section Header, Category |
| `heading-3` | `1.25rem - 1.4rem` | 600 | `Lora`, serif | Book Title, Bento Card Title |
| `body-lead` | `1.15rem` | 400 | `Outfit`, sans-serif | Intro lead paragraph |
| `body` | `1.0rem (16px)` | 400 | `Outfit`, sans-serif | Default prose text |
| `body-sm` | `0.875rem (14px)` | 500 | `Outfit`, sans-serif | Metadata, author, bus route |
| `caption` | `0.75rem (12px)` | 600 | `Outfit`, sans-serif | Badges, timestamps, pills |
| `mono` | `0.85rem` | 500 | `JetBrains Mono` | ISBN, barcode, inventory counts |

---

## 5. Strict Anti-Patterns & Bans

1. ❌ **No Emojis as UI Icons**: Do not place raw emojis (`🔒`, `✅`, `📬`, `⚠`) inside buttons, status pills, or form messages. Use FontAwesome SVG icons with proper accessible titles.
2. ❌ **No Untinted Grays/Blacks**: Always tint dark surfaces with warm mahogany (`#170706`) and shadows with molasses tint (`rgba(78, 7, 5, 0.08)`).
3. ❌ **No AI Clichés**: Ban generic violet/purple gradients (`#6366F1` -> `#A855F7`). Use warm amber gradients (`--gradient-hero`, `--gradient-primary`).
4. ❌ **No Unlabeled Icon Buttons**: All icon buttons (`.notification-btn`, `.theme-toggle`, `.close-btn`) must include `aria-label`.
5. ❌ **No Sub-44px Touch Targets**: Mobile buttons and navigation links must maintain minimum `44px x 44px` clickable dimensions.

---

## 6. Pre-Delivery Checklist

- [x] Canonical 16-token semantic color system mapped to Light & Dark modes.
- [x] Skip link (`<a href="#main-content" class="skip-link">`) present for keyboard accessibility.
- [x] Visible focus rings (`:focus-visible`) configured with high-contrast amber/roast color.
- [x] Mobile touch targets meet `44px` minimum standard.
- [x] All numbers and tabular metrics use `font-variant-numeric: tabular-nums`.
- [x] GSAP and CSS animations strictly comply with `prefers-reduced-motion`.
- [x] All templates replace raw emoji icons with semantic SVGs / FontAwesome icons.
