import frappe
from frappe import _
from erpnext.manufacturing.doctype.bom.bom import get_bom_items as original_get_bom_items
from confidential_app.confidential_app.utils.permissions import (
	_is_admin,
	_is_protection_enabled,
	_user_has_doc_access,
	debug_log,
)


@frappe.whitelist()
def get_bom_items_with_permission_check(bom, company, qty=1, fetch_exploded=1):
	"""
	Override of erpnext.manufacturing.doctype.bom.bom.get_bom_items
	that adds confidential permission checks before returning items.
	"""
	if _is_protection_enabled():
		is_confidential = frappe.db.get_value("BOM", bom, "is_confidential")
		if is_confidential:
			user = frappe.session.user
			if not _is_admin(user) and not _user_has_doc_access("BOM", bom, user):
				debug_log(f"DENY: {user} tried to get items for confidential BOM {bom}")
				frappe.throw(
					_("You don't have permission to access this confidential BOM."),
					frappe.PermissionError,
				)

	return original_get_bom_items(
		bom=bom, company=company, qty=float(qty), fetch_exploded=int(fetch_exploded)
	)


def apply_patches(app_name=None):
	"""Legacy patch applicator - kept for backward compatibility but no longer needed.
	The override is now handled via override_whitelisted_methods in hooks.py."""
	pass
