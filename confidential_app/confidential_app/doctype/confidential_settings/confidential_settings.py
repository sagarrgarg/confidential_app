# Copyright (c) 2023, Your Organization and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import now

# Simplified Global Cache Key
CONFIDENTIAL_SETTINGS_CACHE_KEY = 'confidential_settings_v1'

class ConfidentialSettings(Document):
    def validate(self):
        # Clear debug logs if debug mode is disabled
        if not self.debug_mode and self.debug_logs:
            self.debug_logs = ""

    def on_update(self):
        """Clear cache when settings are updated"""
        frappe.cache().delete_key(CONFIDENTIAL_SETTINGS_CACHE_KEY)

        # **Removed permlevel logic**
        # # Clear DocType cache for affected doctypes if perm levels changed
        # frappe.clear_cache(doctype="BOM")
        # frappe.clear_cache(doctype="Stock Entry")

        # Log update (optional)
        add_debug_log("Confidential Settings updated")

# **Simplified and Fixed add_debug_log**
# Avoids db_update within logging function
def add_debug_log(message, details=None):
    """Adds a log entry to Confidential Settings if debug mode is enabled."""
    try:
        # Check debug_mode without loading the full doc every time if possible
        # Using cache helps here
        settings = get_settings()
        if not settings or not settings.get("debug_mode"):
            return

        # If debug mode is on, fetch the actual document to append log
        settings_doc = frappe.get_single("Confidential Settings")
        if not settings_doc.debug_mode: # Double check after getting doc
             return

        log_entry = f"{now()}: {message}"
        if details:
            try:
                log_entry += f"\nDetails: {json.dumps(details, indent=2, default=str)}"
            except Exception:
                log_entry += f"\nDetails: {str(details)} (Error serializing)"

        new_logs = f"{log_entry}\n---\n{settings_doc.debug_logs or ''}"

        # Limit log size (e.g., keep last 50kb)
        max_log_size = 50 * 1024
        if len(new_logs) > max_log_size:
             new_logs = new_logs[:max_log_size] + "\n... (truncated)"

        # Update the field directly without triggering all hooks via db_update()
        frappe.db.set_value("Confidential Settings", "Confidential Settings", "debug_logs", new_logs, update_modified=False)
        # No frappe.db.commit() here - let the transaction complete normally.

    except Exception as e:
        # Avoid errors in logging stopping execution flow
        print(f"Error adding debug log: {e}")
        # frappe.log_error("Error in add_debug_log", frappe.get_traceback())


def get_settings():
    """Get the current Confidential Settings with fallback values"""
    settings = frappe.cache().get_value(CONFIDENTIAL_SETTINGS_CACHE_KEY)
    if settings:
        return settings

    try:
        # Fetch necessary fields directly
        db_settings = frappe.db.get_singles_dict("Confidential Settings")

        settings = {
            "enable_confidential_protection": db_settings.get("enable_confidential_protection", 1),
            "protect_bom": db_settings.get("protect_bom", 1),
            "protect_stock_entry": db_settings.get("protect_stock_entry", 1),
            "debug_mode": db_settings.get("debug_mode", 0),
            # Removed permlevel fields
        }

        # Cache the simplified settings
        frappe.cache().set_value(CONFIDENTIAL_SETTINGS_CACHE_KEY, settings)

        return settings

    except Exception as e:
         # Handle case where settings doctype might not exist yet during install etc.
         print(f"Error getting Confidential Settings: {e}")
         # Return safe defaults if settings cannot be fetched
         return {
            "enable_confidential_protection": 0,
            "protect_bom": 0,
            "protect_stock_entry": 0,
            "debug_mode": 0,
         }


def is_protection_enabled(doctype="BOM"):
    """Check if confidential protection is enabled for a specific doctype"""
    settings = get_settings()
    if not settings.get("enable_confidential_protection"):
        return False

    if doctype == "BOM":
        return settings.get("protect_bom", 1)
    elif doctype == "Stock Entry":
        return settings.get("protect_stock_entry", 1)
    else:
        # Protection only configured for BOM and Stock Entry
        return False

# Removed get_default_allowed_roles - simplify first

# ... (rest of file, if any)