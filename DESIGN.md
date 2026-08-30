---
name: Library Bus Design Tokens
description: Impeccable Neo-Bakery & Classic Library system. 6-tone Molasses-Butter anchor on warm ivory paper and deep mahogany lacquer with Lora serif typography.

colors:
  # Core 6-Tone Palette
  molasses: "#4E0705"         # Deep mahogany ink / page ground dark
  well-browned: "#812203"     # Roasted chestnut / hover accent
  roast: "#BD5705"            # Caramel bronze / Primary CTA
  toasty: "#ED9040"           # Amber glow / active border
  greasey: "#FFC270"          # Warm honey butter / badge background
  butter: "#FDE971"           # Soft pastry yellow / dark text highlight

  # Surfaces (Light Mode)
  bg-page: "#FFFDF9"          # Crisp ivory
  bg-page-alt: "#FAF4EC"      # Warm rice paper
  bg-surface: "#FFFFFF"       # Elevated card surface
  bg-surface-raised: "#FAF5EF"# Interactive surface
  bg-surface-sunken: "#F4ECE1"# Input recessed surface

  # Dark Mode Surfaces
  dark-page: "#170706"        # Deep espresso ground
  dark-surface: "#240C0B"     # Dark card surface
  dark-surface-raised: "#331210"

  # Tinted Shadows
  shadow-xs: "0 1px 2px rgba(78, 7, 5, 0.05)"
  shadow-sm: "0 2px 8px rgba(78, 7, 5, 0.06)"
  shadow-md: "0 8px 24px rgba(78, 7, 5, 0.09)"
  shadow-hover: "0 20px 48px -10px rgba(78, 7, 5, 0.18)"

typography:
  display-font: "'Lora', Georgia, serif"
  body-font: "'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
  mono-font: "'JetBrains Mono', Consolas, monospace"

  scale:
    "11": "0.6875rem"   # Badge, tag, eyebrow
    "12": "0.75rem"     # Caption, table meta
    "14": "0.875rem"    # Secondary text, list meta
    "16": "1rem"        # Default body text
    "18": "1.125rem"    # Card heading, lead intro
    "20": "1.25rem"     # Subsection title
    "24": "1.5rem"      # Section title
    "32": "2rem"        # Large section header
    "40": "2.5rem"      # Hero display
    "48": "3rem"        # Major display banner

rounded:
  xs: "4px"
  sm: "8px"
  md: "14px"
  lg: "20px"
  xl: "28px"
  pill: "9999px"

spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  "2xl": "48px"
  "3xl": "64px"

components:
  btn-primary:
    background: "var(--gradient-primary)"
    textColor: "#FFFDF9"
    rounded: "var(--radius-pill)"
    hover: "scale(1.02) translateY(-2px)"
  btn-secondary:
    background: "var(--bg-surface-sunken)"
    textColor: "var(--text-primary)"
    borderColor: "var(--border-color)"
    rounded: "var(--radius-pill)"
  card:
    background: "var(--bg-surface)"
    border: "1px solid var(--border-color)"
    rounded: "var(--radius-lg)"
    shadow: "var(--shadow-sm)"

motion:
  duration:
    instant: "0.15s"
    fast: "0.25s"
    normal: "0.5s"
    deliberate: "0.85s"
    epic: "1.2s"
  easing:
    smooth-out: "power2.out"
    smooth-in-out: "power2.inOut"
    cinematic: "power3.out"
    spring: "back.out(1.4)"
    elastic: "elastic.out(1, 0.3)"
  rules:
    - "Always animate transform (x, y, scale, rotation) and autoAlpha. Never animate top/left/width/height/margin/padding."
    - "All interactive reveal animations must use ScrollTrigger.batch() with stagger: 0.08s."
    - "Every GSAP suite must support prefers-reduced-motion: reduce via gsap.matchMedia()."
---

# Design Language Specifications

1. **Literary Hierarchy**: All narrative elements, book titles, author credits, article headings, and section titles utilize **`Lora`** serif typography with generous optical letter spacing.
2. **Tactile Interaction**: Buttons and interactive elements utilize tactile feedback (`:active scale(0.98)`), spring curves (`cubic-bezier(0.175, 0.885, 0.32, 1.275)`), and warm tinted glow on focus.
3. **Data Clarity**: Numerical data, bus capacities, book counts, and queue orders enforce `font-variant-numeric: tabular-nums` to eliminate layout shift.
4. **Cinematic Motion (GSAP)**: Staggered entrances, scroll-linked viewport revelations, and number counters are orchestrated via GSAP 3.12+ engine with compositor-only rendering.

