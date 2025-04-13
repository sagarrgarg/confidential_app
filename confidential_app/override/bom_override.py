import frappe
from frappe import _
import functools
from erpnext.manufacturing.doctype.bom.bom import get_bom_items as original_get_bom_items
from confidential_app.utils.permissions import debug_log

# Store the original function for later use
original_get_bom_items_func = original_get_bom_items

# Define our patched function with permission check
@frappe.whitelist()
def get_bom_items_with_permission_check(bom, company, qty=1, fetch_exploded=1):
    """
    Override of erpnext.manufacturing.doctype.bom.bom.get_bom_items that adds permission checks.
    """
    debug_log(f"BOM ITEMS REQUEST: bom={bom}, user={frappe.session.user}")
    
    # First check if this BOM is confidential
    is_confidential = frappe.db.get_value("BOM", bom, "is_confidential")
    
    if is_confidential:
        debug_log(f"BOM {bom} is confidential, checking permissions")
        
        # System Manager always has access
        if "System Manager" in frappe.get_roles(frappe.session.user):
            debug_log(f"System Manager access granted for BOM {bom}")
        else:
            # Get user roles
            user_roles = set(frappe.get_roles(frappe.session.user))
            debug_log(f"User roles: {user_roles}")
            
            # Get allowed roles for this BOM
            allowed_roles = frappe.db.sql("""
                SELECT role FROM `tabConfidential Role Mapping`
                WHERE parent=%s AND parenttype='BOM' AND parentfield='allowed_roles'
            """, bom, as_dict=True)
            
            allowed_role_names = [r.role for r in allowed_roles]
            debug_log(f"BOM allowed roles: {allowed_role_names}")
            
            # If no roles specified, deny access
            if not allowed_role_names:
                debug_log(f"No allowed roles specified for confidential BOM {bom}")
                frappe.throw(_("You don't have permission to access this confidential BOM."), frappe.PermissionError)
            
            # Check if user has any of the allowed roles
            role_match = False
            for role in user_roles:
                if role in allowed_role_names:
                    role_match = True
                    debug_log(f"User has required role {role} for BOM {bom}")
                    break
            
            if not role_match:
                debug_log(f"User lacks required roles for BOM {bom}")
                frappe.throw(_("You don't have permission to access this confidential BOM."), frappe.PermissionError)
    
    # If we got here, the user has permission to access the BOM
    # Call the original function
    debug_log(f"Permission check passed, calling original get_bom_items for BOM {bom}")
    return original_get_bom_items_func(bom=bom, company=company, qty=float(qty), fetch_exploded=int(fetch_exploded))

def apply_patches():
    """Apply our patches to the erpnext modules."""
    debug_log("Applying BOM override patches")
    
    # Replace the original get_bom_items function with our patched version
    import erpnext.manufacturing.doctype.bom.bom
    erpnext.manufacturing.doctype.bom.bom.get_bom_items = get_bom_items_with_permission_check
    
    debug_log("BOM patches applied successfully") 