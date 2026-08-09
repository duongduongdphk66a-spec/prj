import sys

with open('template/base.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Add nav-link, dropdown-item, profile-dropdown-item to the universal selector
new_selector = """    /* Universal Liquid Buttons & Nav Links */
    button:not(.btn-close):not(.btn-close-alert):not(.chatbot-toggle):not(.chatbot-close):not(.mobile-menu-toggle):not(.profile-trigger):not(.back-to-top), 
    [class*="btn-"]:not(.btn-close):not(.btn-close-alert), 
    .btn, .upgrade-btn, .action-btn, .page-btn, .filter-btn, .back-btn, input[type="submit"],
    .nav-link, .dropdown-item, .profile-dropdown-item, .category-link, .subcategory-link, .search-filter-option"""

old_selector_1 = """    /* Universal Liquid Buttons */
    button:not(.btn-close):not(.btn-close-alert):not(.chatbot-toggle):not(.chatbot-close):not(.mobile-menu-toggle):not(.profile-trigger):not(.back-to-top), 
    [class*="btn-"]:not(.btn-close):not(.btn-close-alert), 
    .btn, .upgrade-btn, .action-btn, .page-btn, .filter-btn, .back-btn, input[type="submit"]"""

content = content.replace(old_selector_1, new_selector)

new_selector_after = """    button:not(.btn-close):not(.btn-close-alert):not(.chatbot-toggle):not(.chatbot-close):not(.mobile-menu-toggle):not(.profile-trigger):not(.back-to-top)::after, 
    [class*="btn-"]:not(.btn-close):not(.btn-close-alert)::after, 
    .btn::after, .upgrade-btn::after, .action-btn::after, .page-btn::after, .filter-btn::after, .back-btn::after, input[type="submit"]::after,
    .nav-link::after, .dropdown-item::after, .profile-dropdown-item::after, .category-link::after, .subcategory-link::after, .search-filter-option::after"""

old_selector_after = """    button:not(.btn-close):not(.btn-close-alert):not(.chatbot-toggle):not(.chatbot-close):not(.mobile-menu-toggle):not(.profile-trigger):not(.back-to-top)::after, 
    [class*="btn-"]:not(.btn-close):not(.btn-close-alert)::after, 
    .btn::after, .upgrade-btn::after, .action-btn::after, .page-btn::after, .filter-btn::after, .back-btn::after, input[type="submit"]::after"""

content = content.replace(old_selector_after, new_selector_after)

new_selector_hover_after = """    button:not(.btn-close):not(.btn-close-alert):not(.chatbot-toggle):not(.chatbot-close):not(.mobile-menu-toggle):not(.profile-trigger):not(.back-to-top):hover::after, 
    [class*="btn-"]:not(.btn-close):not(.btn-close-alert):hover::after, 
    .btn:hover::after, .upgrade-btn:hover::after, .action-btn:hover::after, .page-btn:hover::after, .filter-btn:hover::after, .back-btn:hover::after, input[type="submit"]:hover::after,
    .nav-link:hover::after, .dropdown-item:hover::after, .profile-dropdown-item:hover::after, .category-link:hover::after, .subcategory-link:hover::after, .search-filter-option:hover::after"""

old_selector_hover_after = """    button:not(.btn-close):not(.btn-close-alert):not(.chatbot-toggle):not(.chatbot-close):not(.mobile-menu-toggle):not(.profile-trigger):not(.back-to-top):hover::after, 
    [class*="btn-"]:not(.btn-close):not(.btn-close-alert):hover::after, 
    .btn:hover::after, .upgrade-btn:hover::after, .action-btn:hover::after, .page-btn:hover::after, .filter-btn:hover::after, .back-btn:hover::after, input[type="submit"]:hover::after"""

content = content.replace(old_selector_hover_after, new_selector_hover_after)

new_selector_hover = """    button:not(.btn-close):not(.btn-close-alert):not(.chatbot-toggle):not(.chatbot-close):not(.mobile-menu-toggle):not(.profile-trigger):not(.back-to-top):hover, 
    [class*="btn-"]:not(.btn-close):not(.btn-close-alert):hover, 
    .btn:hover, .upgrade-btn:hover, .action-btn:hover, .page-btn:hover, .filter-btn:hover, .back-btn:hover, input[type="submit"]:hover,
    .nav-link:hover, .dropdown-item:hover, .profile-dropdown-item:hover, .category-link:hover, .subcategory-link:hover, .search-filter-option:hover"""

old_selector_hover = """    button:not(.btn-close):not(.btn-close-alert):not(.chatbot-toggle):not(.chatbot-close):not(.mobile-menu-toggle):not(.profile-trigger):not(.back-to-top):hover, 
    [class*="btn-"]:not(.btn-close):not(.btn-close-alert):hover, 
    .btn:hover, .upgrade-btn:hover, .action-btn:hover, .page-btn:hover, .filter-btn:hover, .back-btn:hover, input[type="submit"]:hover"""

content = content.replace(old_selector_hover, new_selector_hover)


# Add specific text color updates
text_color_css = """
    /* Color mapping for text to be darker shades on hover */
    .nav-link:hover, .profile-dropdown-item:hover, .dropdown-item:hover {
        color: var(--dark-brown) !important;
        font-weight: 700 !important;
    }
    
    .category-link:hover, .subcategory-link:hover, .search-filter-option:hover {
        color: #4b0082 !important; /* Dark purple to match pastel purple */
        font-weight: 700 !important;
    }
    
    .btn-primary:hover, .upgrade-btn:hover {
        color: var(--gold) !important; /* Gold text on dark brown buttons */
    }
    
    .btn-secondary:hover, .action-btn.secondary:hover {
        color: var(--white) !important;
        background-color: var(--dark-brown) !important;
    }
"""

# Insert text color css
start_idx = content.find('/* Base .btn colors */')
if start_idx != -1:
    content = content[:start_idx] + text_color_css + content[start_idx:]
    with open('template/base.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced base.html successfully.")
else:
    print("Could not find insertion point.")
