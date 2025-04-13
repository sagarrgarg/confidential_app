import frappe
import os

# Configuration settings for confidential_app
# Centralize all configuration in one place for easier management

# Debug mode - controlled via environment variable
DEBUG_MODE = os.environ.get('CONFIDENTIAL_DEBUG', '0') == '1'

# Permission cache timeout in seconds (5 minutes)
PERMISSION_CACHE_TIMEOUT = 300

# Roles with special access
CONFIDENTIAL_ROLES = ['Confidential Manager', 'Confidential User']

# System level roles that always have access
ADMIN_ROLES = ['System Manager', 'Administrator']

# Doctypes managed by the confidential app
MANAGED_DOCTYPES = ['BOM', 'Stock Entry', 'Work Order']

# Default roles to assign when creating a new confidential doctype
DEFAULT_ALLOWED_ROLES = ['Confidential Manager']

def get_settings():
    """
    Get system-specific settings from database, falling back to defaults
    """
    try:
        settings = frappe.get_doc("Confidential Settings")
        return settings
    except Exception:
        # Return default values if settings can't be loaded
        return frappe._dict({
            "enabled": True,
            "debug_mode": DEBUG_MODE,
            "default_allowed_roles": DEFAULT_ALLOWED_ROLES
        })

def is_enabled():
    """Check if the confidential protection system is enabled"""
    try:
        settings = get_settings()
        return bool(settings.enabled)
    except Exception:
        # Default to enabled if settings can't be loaded
        return True 