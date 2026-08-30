---
name: gsap
description: Official GSAP animation skills and best practices for the Library Bus project. Covers core tweens, timeline choreography, ScrollTrigger batching, plugins, performance optimization (60 FPS, compositor-only), and accessibility (prefers-reduced-motion).
---

# GSAP Animation Skill & Best Practices

This skill defines the official animation guidelines and engineering directives for the project, aligned with GreenSock's official Agent Skills standards (`greensock/gsap-skills`).

## 1. Core Principles
- **Free Ecosystem**: 100% of GSAP and its plugins (SplitText, MorphSVG, DrawSVG, ScrollSmoother, Flip, MotionPath, etc.) are completely free.
- **Compositor-Only Animations**: Always animate `transform` (`x`, `y`, `z`, `xPercent`, `yPercent`, `scale`, `rotation`) and `autoAlpha`.
  - ❌ NEVER animate layout-triggering properties: `top`, `left`, `width`, `height`, `margin`, `padding`.
- **Visibility Control**: Use `autoAlpha` instead of `opacity` (automatically toggles `visibility: hidden` when opacity reaches 0).

## 2. Timelines & Sequencing
- Prefer `gsap.timeline()` over chained `delay` values.
- Use position parameters for organic, overlapping choreography:
  ```javascript
  const tl = gsap.timeline({ defaults: { duration: 0.6, ease: "power2.out" } });
  tl.from(badge, { y: 20, autoAlpha: 0 })
    .from(title, { y: 30, autoAlpha: 0 }, "-=0.3")
    .from(desc, { y: 20, autoAlpha: 0 }, "-=0.3")
    .from(buttons.children, { y: 15, autoAlpha: 0, stagger: 0.08 }, "-=0.2");
  ```

## 3. ScrollTrigger & Viewport Batching
- Register plugin: `gsap.registerPlugin(ScrollTrigger);`
- Use `ScrollTrigger.batch()` for performance when revealing grids of items:
  ```javascript
  ScrollTrigger.batch(".book-card", {
      start: "top 90%",
      interval: 0.08,
      batchMax: 6,
      once: true,
      onEnter: (batch) => {
          gsap.from(batch, {
              y: 40,
              autoAlpha: 0,
              duration: 0.75,
              stagger: 0.08,
              ease: "power2.out",
              overwrite: "auto"
          });
      }
  });
  ```
- Always call `ScrollTrigger.refresh()` after dynamic DOM or layout changes.

## 4. GSAP Utilities & Math
- `gsap.utils.clamp(min, max, value)`: Limit range.
- `gsap.utils.mapRange(inMin, inMax, outMin, outMax, value)`: Map input to output range for micro-interactions (e.g. mouse cursor 3D card tilt).
- `gsap.utils.interpolate(start, end, progress)`: Smooth interpolation.

## 5. Accessibility & Responsive (`gsap.matchMedia`)
Always wrap animation suites in `gsap.matchMedia()`:
```javascript
const mm = gsap.matchMedia();

mm.add("(prefers-reduced-motion: no-preference)", () => {
    // Full interactive timelines & ScrollTriggers
});

mm.add("(prefers-reduced-motion: reduce)", () => {
    // Fallback: immediately show elements with gsap.set()
    gsap.set(".hero-title, .stat-card, .book-card", { autoAlpha: 1, y: 0, scale: 1 });
});
```
