"""
Boot session module for Confidential App.
Adds confidential-related data to the boot info sent to the client.
"""

import frappe

__version__ = "0.0.1"


def boot_session(bootinfo):
	"""Add confidential app info to boot data."""
	if frappe.session.user == "Guest":
		return

	bootinfo.confidential_app = {
		"has_confidential_manager": "Confidential Manager" in frappe.get_roles(),
		"has_confidential_user": "Confidential User" in frappe.get_roles(),
	}
