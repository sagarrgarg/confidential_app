"""
Boot session handler for the Confidential App.
Adds confidential-related data to boot info and ensures monkey-patches are applied.
"""

import frappe

__version__ = "0.0.1"


def boot_session(bootinfo):
    """Apply BOM override patches and add confidential app info to boot data."""
    from confidential_app.confidential_app.override.bom_override import apply_patches
    apply_patches()

    if frappe.session.user == "Guest":
        return

    bootinfo.confidential_app = {
        "has_confidential_manager": "Confidential Manager" in frappe.get_roles(),
        "has_confidential_user": "Confidential User" in frappe.get_roles(),
    }
