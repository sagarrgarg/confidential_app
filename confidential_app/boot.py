"""
This module contains functions that are executed during application boot
"""

import frappe
import json

__version__ = '0.0.1'

# Apply our module patches when app loads
def boot_session(bootinfo):
    """Apply our patches when Frappe boots up."""
    from confidential_app.confidential_app.override.bom_override import apply_patches
    apply_patches() 