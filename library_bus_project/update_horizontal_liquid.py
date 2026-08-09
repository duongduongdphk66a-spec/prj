import sys
import re

with open('template/base.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the after element block
start_idx_after = content.find('    button:not(.btn-close):not(.btn-close-alert)')
if start_idx_after != -1:
    end_idx_after = content.find('    /* Color mapping for text to be darker shades on hover */')
    if end_idx_after != -1:
        
        # We rewrite everything from the start of the Universal Liquid Buttons
        start_idx = content.find('    /* Universal Liquid Buttons & Nav Links */')
        
        new_css = """    /* Universal Liquid Buttons & Nav Links */
    button:not(.btn-close):not(.btn-close-alert):not(.chatbot-toggle):not(.chatbot-close):not(.mobile-menu-toggle):not(.profile-trigger):not(.back-to-top), 
    [class*="btn-"]:not(.btn-close):not(.btn-close-alert), 
    .btn, .upgrade-btn, .action-btn, .page-btn, .filter-btn, .back-btn, input[type="submit"],
    .nav-link, .dropdown-item, .profile-dropdown-item, .category-link, .subcategory-link, .search-filter-option {
        position: relative;
        overflow: hidden;
        z-index: 1;
        transition: color 0.4s ease, border-color 0.4s ease, background 0.4s ease, box-shadow 0.4s ease, transform 0.4s ease !important;
        /* Ensure inline elements clip the overflow */
        display: inline-flex;
        align-items: center;
        justify-content: center;
    }
    
    button:not(.btn-close):not(.btn-close-alert):not(.chatbot-toggle):not(.chatbot-close):not(.mobile-menu-toggle):not(.profile-trigger):not(.back-to-top)::after, 
    [class*="btn-"]:not(.btn-close):not(.btn-close-alert)::after, 
    .btn::after, .upgrade-btn::after, .action-btn::after, .page-btn::after, .filter-btn::after, .back-btn::after, input[type="submit"]::after,
    .nav-link::after, .dropdown-item::after, .profile-dropdown-item::after, .category-link::after, .subcategory-link::after, .search-filter-option::after {
        content: '';
        position: absolute;
        width: 150%;
        height: 150%;
        top: -25%;
        left: -150%;
        border-radius: 45%;
        background-color: rgba(255, 255, 255, 0.35); /* Liquid wave moving from left */
        transition: all 0.5s cubic-bezier(0.64, 0.04, 0.35, 1);
        z-index: -1;
        pointer-events: none;
    }
    
    button:not(.btn-close):not(.btn-close-alert):not(.chatbot-toggle):not(.chatbot-close):not(.mobile-menu-toggle):not(.profile-trigger):not(.back-to-top):hover::after, 
    [class*="btn-"]:not(.btn-close):not(.btn-close-alert):hover::after, 
    .btn:hover::after, .upgrade-btn:hover::after, .action-btn:hover::after, .page-btn:hover::after, .filter-btn:hover::after, .back-btn:hover::after, input[type="submit"]:hover::after,
    .nav-link:hover::after, .dropdown-item:hover::after, .profile-dropdown-item:hover::after, .category-link:hover::after, .subcategory-link:hover::after, .search-filter-option:hover::after {
        left: -20%;
        border-radius: 30%;
    }
    
    button:not(.btn-close):not(.btn-close-alert):not(.chatbot-toggle):not(.chatbot-close):not(.mobile-menu-toggle):not(.profile-trigger):not(.back-to-top):hover, 
    [class*="btn-"]:not(.btn-close):not(.btn-close-alert):hover, 
    .btn:hover, .upgrade-btn:hover, .action-btn:hover, .page-btn:hover, .filter-btn:hover, .back-btn:hover, input[type="submit"]:hover,
    .nav-link:hover, .dropdown-item:hover, .profile-dropdown-item:hover, .category-link:hover, .subcategory-link:hover, .search-filter-option:hover {
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
        transform: translateY(-2px);
    }

    /* Universal color mapping for ALL buttons text on hover */
    button:not(.btn-close):not(.btn-close-alert):not(.chatbot-toggle):not(.chatbot-close):not(.mobile-menu-toggle):not(.profile-trigger):not(.back-to-top):hover, 
    [class*="btn-"]:not(.btn-close):not(.btn-close-alert):hover, 
    .btn:hover, .action-btn:hover, .page-btn:hover, .filter-btn:hover, .back-btn:hover, input[type="submit"]:hover {
        color: var(--dark-brown) !important;
        font-weight: 700 !important;
    }

    /* Color mapping for text to be darker shades on hover */
    .nav-link:hover, .profile-dropdown-item:hover, .dropdown-item:hover {
        color: var(--dark-brown) !important;
        font-weight: 700 !important;
    }
    
    .category-link:hover, .subcategory-link:hover, .search-filter-option:hover {
        color: #4b0082 !important; /* Dark purple to match pastel purple */
        font-weight: 700 !important;
    }
    
    /* Exceptions for buttons with dark backgrounds */
    .btn-primary:hover, .btn-danger:hover, .btn-action.btn-warning:hover, .upgrade-btn:hover, .btn-dashboard-primary:hover, .btn-login:hover {
        color: var(--gold) !important; 
    }
    
    .btn-secondary:hover, .action-btn.secondary:hover {
        color: var(--white) !important;
        background-color: var(--dark-brown) !important;
    }
"""
        end_idx = content.find('    /* Base .btn colors */')
        if start_idx != -1 and end_idx != -1:
            content = content[:start_idx] + new_css + content[end_idx:]
            with open('template/base.html', 'w', encoding='utf-8') as f:
                f.write(content)
            print("Replaced CSS successfully.")
        else:
            print("Could not find start/end idx for replace.")
