"""
Boot session handler for the Confidential App.
Adds confidential-related data to boot info and ensures monkey-patches are applied.
"""

import frappe

__version__ = "0.0.1"


def boot_session(bootinfo):
    """Apply BOM override patches and add confidential app info to boot data."""
    # Multi-tenant safety: boot_session fires on every site that loads this
    # module, but the monkey-patches and bootinfo only make sense for sites
    # where confidential_app is actually installed. Skip both otherwise.
    try:
        if "confidential_app" not in frappe.get_installed_apps():
            return
    except Exception:
        return

    from confidential_app.confidential_app.override.bom_override import apply_patches
    apply_patches()

    if frappe.session.user == "Guest":
        return

    bootinfo.confidential_app = {
        "has_confidential_manager": "Confidential Manager" in frappe.get_roles(),
        "has_confidential_user": "Confidential User" in frappe.get_roles(),
    }
