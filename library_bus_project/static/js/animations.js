/**
 * Library Bus - GSAP Universal Animation Suite
 * Built following official GreenSock AI Skills guidelines (greensock/gsap-skills):
 * - Applied across 100% of templates via base.html & specialized sub-bases
 * - Core tweens with transform aliases (x, y, scale, rotation) & autoAlpha (compositor-only)
 * - Master Timeline sequencing with position parameters
 * - Comprehensive ScrollTrigger.batch() for all grids, tables, forms, and cards
 * - Smooth dynamic count-up numbers using GSAP tweens (tabular-nums)
 * - Interactive 3D card tilt micro-physics using gsap.utils.clamp & mapRange
 * - Article reading progress bar scrubbed to scroll position
 * - Bus route timeline stop revelations
 * - Universal responsive & accessibility support with gsap.matchMedia()
 */

(function() {
    'use strict';

    if (typeof gsap === 'undefined') {
        console.warn('GSAP is not loaded. Skipping GSAP animations.');
        return;
    }

    if (typeof ScrollTrigger !== 'undefined') {
        gsap.registerPlugin(ScrollTrigger);
    }

    document.addEventListener('DOMContentLoaded', function() {
        const mm = gsap.matchMedia();

        // =========================================================================
        // 1. STANDARD MOTION SUITE (prefers-reduced-motion: no-preference)
        // =========================================================================
        mm.add("(prefers-reduced-motion: no-preference)", () => {

            // ========== A. HERO & BANNER MASTER TIMELINES ==========
            const heroSection = document.querySelector('.hero-premium, .about-hero, .hero-section, .blog-hero, .auth-hero');
            if (heroSection) {
                const tl = gsap.timeline({
                    defaults: {
                        duration: 0.85,
                        ease: "power3.out"
                    }
                });

                const badge = heroSection.querySelector('.hero-badge, .about-badge, .section-badge, .badge-hero');
                const title = heroSection.querySelector('.hero-title, .about-title, .blog-hero h1, h1');
                const desc = heroSection.querySelector('.hero-desc, .about-subtitle, .blog-hero p, .lead');
                const search = heroSection.querySelector('.hero-search-wrapper, .search-container, .blog-search-box');
                const buttons = heroSection.querySelector('.hero-actions, .hero-buttons, .cta-group, .auth-actions');
                const visual = heroSection.querySelector('.hero-visual-card, .features-img, .hero-illustration, .auth-visual');

                if (badge) {
                    tl.from(badge, { y: 20, autoAlpha: 0, duration: 0.55 }, 0.05);
                }
                if (title) {
                    tl.from(title, { y: 32, autoAlpha: 0, duration: 0.85 }, "-=0.35");
                }
                if (desc) {
                    tl.from(desc, { y: 24, autoAlpha: 0, duration: 0.75 }, "-=0.55");
                }
                if (search) {
                    tl.from(search, { y: 20, autoAlpha: 0, duration: 0.65 }, "-=0.45");
                }
                if (buttons && buttons.children.length > 0) {
                    tl.from(buttons.children, { y: 18, autoAlpha: 0, stagger: 0.08, duration: 0.55 }, "-=0.4");
                }
                if (visual) {
                    tl.from(visual, { scale: 0.94, y: 30, autoAlpha: 0, duration: 1.0, ease: "power2.out" }, "-=0.65");
                }
            }

            // ========== B. UNIVERSAL SCROLLTRIGGER BATCH REVEALS ==========
            if (typeof ScrollTrigger !== 'undefined') {
                // 1. Page & Section Headers
                ScrollTrigger.batch(".section-header, .page-header, .inventory-page-header, .content-header, .dashboard-header, .analytics-header", {
                    start: "top 88%",
                    once: true,
                    onEnter: (batch) => {
                        gsap.from(batch, {
                            y: 35,
                            autoAlpha: 0,
                            duration: 0.8,
                            stagger: 0.12,
                            ease: "power2.out",
                            overwrite: "auto"
                        });
                    }
                });

                // 2. Stat & Metric Cards (Across Index, Dashboard, Analytics, Transactions, Inventory)
                ScrollTrigger.batch(".stat-card, .metric-card, .stat-box, .inventory-stat-card, .analytics-card, .stats-box", {
                    start: "top 88%",
                    once: true,
                    onEnter: (batch) => {
                        gsap.from(batch, {
                            y: 35,
                            autoAlpha: 0,
                            duration: 0.75,
                            stagger: 0.08,
                            ease: "power2.out",
                            overwrite: "auto"
                        });

                        // Dynamic Counter Animation
                        batch.forEach(card => {
                            const countEl = card.querySelector('.count-up, [data-target]');
                            if (countEl && !countEl.dataset.animated) {
                                countEl.dataset.animated = "true";
                                const rawTarget = (countEl.getAttribute('data-target') || countEl.textContent).replace(/\D/g, '');
                                const targetVal = parseInt(rawTarget, 10) || 0;
                                if (targetVal > 0) {
                                    const obj = { val: 0 };
                                    gsap.to(obj, {
                                        val: targetVal,
                                        duration: 1.8,
                                        ease: "power2.out",
                                        onUpdate: () => {
                                            countEl.textContent = Math.floor(obj.val).toLocaleString('vi-VN');
                                        },
                                        onComplete: () => {
                                            countEl.textContent = targetVal.toLocaleString('vi-VN');
                                        }
                                    });
                                }
                            }
                        });
                    }
                });

                // 3. Book Cards & Inventory Grids
                ScrollTrigger.batch(".book-card, .book-card-item, .inventory-card, .book-item", {
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

                // 4. Bus Fleet & Route Cards
                ScrollTrigger.batch(".bus-card, .route-card, .fleet-card, .bus-item", {
                    start: "top 88%",
                    interval: 0.08,
                    batchMax: 4,
                    once: true,
                    onEnter: (batch) => {
                        gsap.from(batch, {
                            y: 35,
                            autoAlpha: 0,
                            duration: 0.75,
                            stagger: 0.1,
                            ease: "power2.out",
                            overwrite: "auto"
                        });
                    }
                });

                // 5. Blog Posts, Articles, Quotes & FAQ Items
                ScrollTrigger.batch(".post-card-home, .blog-card, .quote-box, .goal-card, .faq-item, .article-preview", {
                    start: "top 88%",
                    interval: 0.08,
                    batchMax: 4,
                    once: true,
                    onEnter: (batch) => {
                        gsap.from(batch, {
                            y: 30,
                            autoAlpha: 0,
                            duration: 0.7,
                            stagger: 0.08,
                            ease: "power2.out",
                            overwrite: "auto"
                        });
                    }
                });

                // 6. User Profile, Activity History & Notification Cards
                ScrollTrigger.batch(".activity-item, .notification-item, .notification-card, .borrow-record-card, .reservation-card", {
                    start: "top 90%",
                    interval: 0.06,
                    batchMax: 5,
                    once: true,
                    onEnter: (batch) => {
                        gsap.from(batch, {
                            x: -20,
                            autoAlpha: 0,
                            duration: 0.6,
                            stagger: 0.06,
                            ease: "power2.out",
                            overwrite: "auto"
                        });
                    }
                });

                // 7. Category & Tag Pills (Elastic Spring Animation)
                ScrollTrigger.batch(".category-pill, .cat-pill, .tag-pill, .badge-pill", {
                    start: "top 92%",
                    once: true,
                    onEnter: (batch) => {
                        gsap.from(batch, {
                            scale: 0.85,
                            autoAlpha: 0,
                            duration: 0.5,
                            stagger: 0.04,
                            ease: "back.out(1.4)",
                            overwrite: "auto"
                        });
                    }
                });

                // 8. Form Cards & Auth Boxes (Login, Register, Password Reset, Settings)
                ScrollTrigger.batch(".auth-card, .form-card, .login-box, .register-box, .settings-card", {
                    start: "top 88%",
                    once: true,
                    onEnter: (batch) => {
                        gsap.from(batch, {
                            y: 30,
                            scale: 0.98,
                            autoAlpha: 0,
                            duration: 0.7,
                            stagger: 0.1,
                            ease: "power2.out",
                            overwrite: "auto"
                        });
                    }
                });

                // 9. Table & Data Containers
                ScrollTrigger.batch(".table-responsive, .data-table-container, .table-card", {
                    start: "top 88%",
                    once: true,
                    onEnter: (batch) => {
                        gsap.from(batch, {
                            y: 25,
                            autoAlpha: 0,
                            duration: 0.65,
                            ease: "power2.out",
                            overwrite: "auto"
                        });
                    }
                });

                // 10. Route Stop Timeline Reveal
                const routeTimeline = document.querySelector('.route-stops-timeline, .stops-list, .timeline-container');
                if (routeTimeline) {
                    const stops = routeTimeline.querySelectorAll('.route-stop-item, .stop-card, .timeline-item');
                    if (stops.length > 0) {
                        gsap.from(stops, {
                            x: -25,
                            autoAlpha: 0,
                            duration: 0.6,
                            stagger: 0.12,
                            ease: "power2.out",
                            scrollTrigger: {
                                trigger: routeTimeline,
                                start: "top 85%",
                                once: true
                            }
                        });
                    }
                }

                // 11. Article Reading Progress Bar
                const articleBody = document.querySelector('.article-content, .post-content, .article-body, .blog-detail-content');
                let progressBar = document.querySelector('.reading-progress-bar');
                if (articleBody) {
                    if (!progressBar) {
                        progressBar = document.createElement('div');
                        progressBar.className = 'reading-progress-bar';
                        document.body.appendChild(progressBar);
                    }
                    gsap.to(progressBar, {
                        scaleX: 1,
                        ease: "none",
                        scrollTrigger: {
                            trigger: articleBody,
                            start: "top top+=80",
                            end: "bottom bottom",
                            scrub: 0.2
                        }
                    });
                }
            }

            // ========== C. 3D CARD MICRO-TILT (gsap.utils.mapRange & clamp) ==========
            const tiltCards = document.querySelectorAll('.hero-visual-card, .featured-book-hero, .card-tilt-3d, .book-detail-cover');
            tiltCards.forEach(card => {
                card.addEventListener('mousemove', (e) => {
                    const rect = card.getBoundingClientRect();
                    const x = e.clientX - rect.left;
                    const y = e.clientY - rect.top;
                    
                    const rotX = gsap.utils.clamp(-8, 8, gsap.utils.mapRange(0, rect.height, 8, -8, y));
                    const rotY = gsap.utils.clamp(-8, 8, gsap.utils.mapRange(0, rect.width, -8, 8, x));

                    gsap.to(card, {
                        rotationX: rotX,
                        rotationY: rotY,
                        transformPerspective: 900,
                        duration: 0.35,
                        ease: "power1.out",
                        overwrite: "auto"
                    });
                });

                card.addEventListener('mouseleave', () => {
                    gsap.to(card, {
                        rotationX: 0,
                        rotationY: 0,
                        duration: 0.6,
                        ease: "power2.out",
                        overwrite: "auto"
                    });
                });
            });

            // ========== D. INTERACTIVE STAR RATING MICRO-ANIMATIONS ==========
            const ratingStars = document.querySelectorAll('.rating-star-btn, .star-select i, .book-rating-input i');
            ratingStars.forEach(star => {
                star.addEventListener('mouseenter', () => {
                    gsap.to(star, { scale: 1.25, duration: 0.2, ease: "back.out(2)" });
                });
                star.addEventListener('mouseleave', () => {
                    gsap.to(star, { scale: 1, duration: 0.2, ease: "power2.out" });
                });
            });

        }); // End prefers-reduced-motion: no-preference

        // =========================================================================
        // 2. ACCESSIBILITY FALLBACK (prefers-reduced-motion: reduce)
        // =========================================================================
        mm.add("(prefers-reduced-motion: reduce)", () => {
            gsap.set(".hero-badge, .hero-title, .hero-desc, .hero-search-wrapper, .hero-actions, .stat-card, .book-card, .post-card-home, .section-header, .route-stop-item, .auth-card, .form-card, .activity-item, .notification-item", {
                autoAlpha: 1,
                y: 0,
                x: 0,
                scale: 1,
                rotationX: 0,
                rotationY: 0
            });
            document.querySelectorAll('.count-up, [data-target]').forEach(countEl => {
                const rawTarget = (countEl.getAttribute('data-target') || countEl.textContent).replace(/\D/g, '');
                const targetVal = parseInt(rawTarget, 10) || 0;
                countEl.textContent = targetVal.toLocaleString('vi-VN');
            });
        });

        // =========================================================================
        // 3. TOAST GSAP SMOOTH ANIMATION (Global Utilities)
        // =========================================================================
        window.animateToastIn = function(toastEl) {
            gsap.fromTo(toastEl, 
                { x: 80, autoAlpha: 0, scale: 0.95 },
                { x: 0, autoAlpha: 1, scale: 1, duration: 0.45, ease: "back.out(1.4)" }
            );
        };

        window.animateToastOut = function(toastEl, callback) {
            gsap.to(toastEl, {
                x: 60,
                autoAlpha: 0,
                scale: 0.9,
                duration: 0.3,
                ease: "power2.in",
                onComplete: () => {
                    if (typeof callback === 'function') callback();
                    else toastEl.remove();
                }
            });
        };

    });
})();
