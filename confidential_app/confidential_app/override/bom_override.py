import frappe
from frappe import _
import functools
from erpnext.manufacturing.doctype.bom.bom import get_bom_items as original_get_bom_items
from confidential_app.confidential_app.utils.permissions import debug_log, has_bom_permission

# Store the original function for later use
original_get_bom_items_func = original_get_bom_items

# Define our patched function with permission check
@frappe.whitelist()
def get_bom_items_with_permission_check(bom, company, qty=1, fetch_exploded=1):
    """
    Override of erpnext.manufacturing.doctype.bom.bom.get_bom_items that adds permission checks.
    """
    debug_log(f"BOM ITEMS REQUEST: bom={bom}, user={frappe.session.user}")
    
    # Use our centralized permission check function
    if not has_bom_permission(bom):
        frappe.throw(_("You don't have permission to access this confidential BOM."), frappe.PermissionError)
    
    # If we got here, the user has permission to access the BOM
    # Call the original function
    debug_log(f"Permission check passed, calling original get_bom_items for BOM {bom}")
    return original_get_bom_items_func(bom=bom, company=company, qty=float(qty), fetch_exploded=int(fetch_exploded))

def apply_patches(app_name=None):
    """Apply our patches to the erpnext modules."""
    debug_log("Applying BOM override patches")
    
    # Replace the original get_bom_items function with our patched version
    import erpnext.manufacturing.doctype.bom.bom
    erpnext.manufacturing.doctype.bom.bom.get_bom_items = get_bom_items_with_permission_check
    
    debug_log("BOM patches applied successfully") 