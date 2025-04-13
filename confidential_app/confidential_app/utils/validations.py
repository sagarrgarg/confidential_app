# Copyright (c) 2023, Your Organization and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from confidential_app.confidential_app.doctype.confidential_settings.confidential_settings import add_debug_log, get_settings
# Import the core permission checking functions if needed for save validation
from .permissions import has_bom_permission, has_stock_entry_permission, has_work_order_permission

# Simple debug log
def debug_log(message):
    """Write to a simple log file to debug validation issues"""
    try:
        with open('/home/ubuntu/frappe-bench/logs/conf_valid_debug.log', 'a') as f:
            f.write(f"{frappe.utils.now()}: {message}\n")
    except:
        pass # Silent fail if logging fails

# Flag to control whether validations should run
ENABLE_VALIDATIONS = True

def validate_bom_permissions_on_save(doc, method=None):
    """Validate permissions when saving a BOM"""
    if not ENABLE_VALIDATIONS:
        return
    
    # System Manager can always save
    if "System Manager" in frappe.get_roles():
        return
    
    # If marking as confidential, ensure roles are provided
    if doc.is_confidential and not doc.get("allowed_roles"):
        debug_log(f"ERROR: BOM {doc.name} marked confidential but no allowed roles specified")
        frappe.throw(_("You must specify at least one allowed role for a confidential BOM."))

    # Only System Manager can change confidentiality status or roles after creation
    if not doc.is_new():
        try:
            old_doc = frappe.get_doc("BOM", doc.name)
            
            confidentiality_changed = old_doc.is_confidential != doc.is_confidential
            
            # Check if allowed roles changed using simple comparison
            old_roles = set([d.role for d in old_doc.get("allowed_roles", [])])
            new_roles = set([d.role for d in doc.get("allowed_roles", [])])
            roles_changed = old_roles != new_roles
            
            if (confidentiality_changed or roles_changed) and "System Manager" not in frappe.get_roles():
                debug_log(f"ERROR: Non-SysAdmin {frappe.session.user} tried to modify confidentiality settings of BOM {doc.name}")
                frappe.throw(_("Only System Manager can change the confidentiality status or allowed roles of an existing BOM."),
                           frappe.PermissionError)
        except Exception as e:
            debug_log(f"Error checking BOM {doc.name} changes: {str(e)}")

def validate_stock_entry_permissions_on_save(doc, method=None):
    """Validate permissions when saving a Stock Entry"""
    if not ENABLE_VALIDATIONS:
        return
    
    # System Manager can always save
    if "System Manager" in frappe.get_roles():
        return
    
    # If this is a manufacturing entry with a BOM, check if user has BOM permission
    if doc.bom_no and (doc.purpose == "Manufacture" or doc.purpose == "Material Transfer for Manufacture"):
        # If user has permission to the BOM, allow them to create/edit the Stock Entry
        if has_bom_permission(doc.bom_no):
            debug_log(f"User has permission to BOM {doc.bom_no}, allowing Stock Entry operation")
            return
    
    # Simple check for consistency (only if not already approved through BOM permission)
    if doc.is_confidential and not doc.get("allowed_roles"):
        debug_log(f"ERROR: Stock Entry {doc.name} marked confidential but no allowed roles specified")
        frappe.throw(_("You must specify at least one allowed role for a confidential Stock Entry."))

    # Only System Manager can change confidentiality status or roles after creation
    if not doc.is_new():
        try:
            old_doc = frappe.get_doc("Stock Entry", doc.name)
            
            confidentiality_changed = old_doc.is_confidential != doc.is_confidential
            
            # Check if allowed roles changed using simple comparison
            old_roles = set([d.role for d in old_doc.get("allowed_roles", [])])
            new_roles = set([d.role for d in doc.get("allowed_roles", [])])
            roles_changed = old_roles != new_roles
            
            if (confidentiality_changed or roles_changed) and "System Manager" not in frappe.get_roles():
                debug_log(f"ERROR: Non-SysAdmin {frappe.session.user} tried to modify confidentiality settings of Stock Entry {doc.name}")
                frappe.throw(_("Only System Manager can change the confidentiality status or allowed roles of an existing Stock Entry."),
                           frappe.PermissionError)
        except Exception as e:
            debug_log(f"Error checking Stock Entry {doc.name} changes: {str(e)}")

def set_stock_entry_confidentiality(doc, method=None):
    """Set confidentiality on Stock Entry based on BOM if applicable"""
    if not ENABLE_VALIDATIONS:
        return
    
    if not doc.bom_no:
        return
    
    try:
        # Check if BOM exists and is accessible (could be confidential)
        bom = None
        try:
            bom = frappe.get_doc("BOM", doc.bom_no)
        except frappe.PermissionError:
            debug_log(f"Permission error accessing BOM {doc.bom_no}")
            # If we can't access BOM but this is a manufacturing entry, we need to 
            # at least get the confidentiality status safely
            if doc.purpose == "Manufacture" or doc.purpose == "Material Transfer for Manufacture":
                # Force a direct DB check bypassing permission system
                is_confidential = frappe.db.get_value("BOM", doc.bom_no, "is_confidential")
                if is_confidential:
                    debug_log(f"BOM {doc.bom_no} is confidential but user lacks permission")
                    # At this point, we know user can't see BOM but tries to create Stock Entry
                    # We'll prevent this by throwing an error
                    frappe.throw(_("You don't have permission to create Stock Entries for this confidential BOM."))
            return
            
        if not bom:
            return
        
        if bom.is_confidential:
            debug_log(f"Setting Stock Entry {doc.name} as confidential based on BOM {doc.bom_no}")
            doc.is_confidential = 1
            
            # Clear any existing roles
            doc.set("allowed_roles", [])
            
            # Copy roles from BOM
            for bom_role in bom.get("allowed_roles", []):
                doc.append("allowed_roles", {"role": bom_role.role})
            
            debug_log(f"Copied roles to Stock Entry {doc.name}: {[d.role for d in doc.get('allowed_roles', [])]}")
        else:
            # Ensure not confidential if BOM isn't
            doc.is_confidential = 0
            doc.set("allowed_roles", [])
    except Exception as e:
        debug_log(f"Error setting Stock Entry {doc.name} confidentiality from BOM {doc.bom_no}: {str(e)}")

def update_stock_entries_on_bom_change(doc, method=None):
    """Update linked Stock Entries and Work Orders when BOM confidentiality changes"""
    if not ENABLE_VALIDATIONS:
        return
    
    old_doc = doc.get_doc_before_save()
    if not old_doc:
        return
    
    # Check if confidentiality or roles changed
    confidentiality_changed = old_doc.is_confidential != doc.is_confidential
    
    # Compare roles using simple list comprehension
    old_roles = set([d.role for d in old_doc.get("allowed_roles", [])])
    new_roles = set([d.role for d in doc.get("allowed_roles", [])])
    roles_changed = old_roles != new_roles
    
    if not (confidentiality_changed or roles_changed):
        return
    
    debug_log(f"Updating linked documents for BOM {doc.name} due to confidentiality changes")
    
    # Find all Stock Entries linked to this BOM
    stock_entries = frappe.get_all(
        "Stock Entry",
        filters={"bom_no": doc.name},
        pluck="name"
    )
    
    for se_name in stock_entries:
        try:
            se = frappe.get_doc("Stock Entry", se_name)
            needs_update = False
            
            if se.is_confidential != doc.is_confidential:
                se.is_confidential = doc.is_confidential
                needs_update = True
            
            se_roles = set([d.role for d in se.get("allowed_roles", [])])
            if se_roles != new_roles:
                # Clear and rebuild roles
                se.set("allowed_roles", [])
                for role_name in new_roles:
                    se.append("allowed_roles", {"role": role_name})
                needs_update = True
                
            if needs_update:
                se.flags.ignore_permissions = True  # Allow update even if user doesn't have permission
                se.save()
                debug_log(f"Updated Stock Entry {se_name} based on BOM {doc.name} change")
        except Exception as e:
            debug_log(f"Error updating Stock Entry {se_name}: {str(e)}")
    
    # Find all Work Orders linked to this BOM
    work_orders = frappe.get_all(
        "Work Order",
        filters={"bom_no": doc.name},
        pluck="name"
    )
    
    for wo_name in work_orders:
        try:
            wo = frappe.get_doc("Work Order", wo_name)
            needs_update = False
            
            if wo.is_confidential != doc.is_confidential:
                wo.is_confidential = doc.is_confidential
                needs_update = True
            
            wo_roles = set([d.role for d in wo.get("allowed_roles", [])])
            if wo_roles != new_roles:
                # Clear and rebuild roles
                wo.set("allowed_roles", [])
                for role_name in new_roles:
                    wo.append("allowed_roles", {"role": role_name})
                needs_update = True
                
            if needs_update:
                wo.flags.ignore_permissions = True  # Allow update even if user doesn't have permission
                wo.save()
                debug_log(f"Updated Work Order {wo_name} based on BOM {doc.name} change")
        except Exception as e:
            debug_log(f"Error updating Work Order {wo_name}: {str(e)}")

def validate_work_order_permissions_on_save(doc, method=None):
    """Validate permissions when saving a Work Order"""
    if not ENABLE_VALIDATIONS:
        return
    
    # System Manager can always save
    if "System Manager" in frappe.get_roles():
        return
    
    # If this work order is linked to a BOM, check if user has BOM permission
    if doc.bom_no:
        # If user has permission to the BOM, allow them to create/edit the Work Order
        if has_bom_permission(doc.bom_no):
            debug_log(f"User has permission to BOM {doc.bom_no}, allowing Work Order operation")
            return
    
    # Simple check for consistency (only if not already approved through BOM permission)
    if doc.is_confidential and not doc.get("allowed_roles"):
        debug_log(f"ERROR: Work Order {doc.name} marked confidential but no allowed roles specified")
        frappe.throw(_("You must specify at least one allowed role for a confidential Work Order."))

    # Only System Manager can change confidentiality status or roles after creation
    if not doc.is_new():
        try:
            old_doc = frappe.get_doc("Work Order", doc.name)
            
            confidentiality_changed = old_doc.is_confidential != doc.is_confidential
            
            # Check if allowed roles changed using simple comparison
            old_roles = set([d.role for d in old_doc.get("allowed_roles", [])])
            new_roles = set([d.role for d in doc.get("allowed_roles", [])])
            roles_changed = old_roles != new_roles
            
            if (confidentiality_changed or roles_changed) and "System Manager" not in frappe.get_roles():
                debug_log(f"ERROR: Non-SysAdmin {frappe.session.user} tried to modify confidentiality settings of Work Order {doc.name}")
                frappe.throw(_("Only System Manager can change the confidentiality status or allowed roles of an existing Work Order."),
                           frappe.PermissionError)
        except Exception as e:
            debug_log(f"Error checking Work Order {doc.name} changes: {str(e)}")

def set_work_order_confidentiality(doc, method=None):
    """Set confidentiality on Work Order based on BOM if applicable"""
    if not ENABLE_VALIDATIONS:
        return
    
    if not doc.bom_no:
        return
    
    try:
        # Check if BOM exists and is accessible (could be confidential)
        bom = None
        try:
            bom = frappe.get_doc("BOM", doc.bom_no)
        except frappe.PermissionError:
            debug_log(f"Permission error accessing BOM {doc.bom_no}")
            # If we can't access BOM, we need to at least get the confidentiality status safely
            # Force a direct DB check bypassing permission system
            is_confidential = frappe.db.get_value("BOM", doc.bom_no, "is_confidential")
            if is_confidential:
                debug_log(f"BOM {doc.bom_no} is confidential but user lacks permission")
                # At this point, we know user can't see BOM but tries to create Work Order
                # We'll prevent this by throwing an error
                frappe.throw(_("You don't have permission to create Work Orders for this confidential BOM."))
            return
            
        if not bom:
            return
        
        if bom.is_confidential:
            debug_log(f"Setting Work Order {doc.name} as confidential based on BOM {doc.bom_no}")
            doc.is_confidential = 1
            
            # Clear any existing roles
            doc.set("allowed_roles", [])
            
            # Copy roles from BOM
            for bom_role in bom.get("allowed_roles", []):
                doc.append("allowed_roles", {"role": bom_role.role})
            
            debug_log(f"Copied roles to Work Order {doc.name}: {[d.role for d in doc.get('allowed_roles', [])]}")
        else:
            # Ensure not confidential if BOM isn't
            doc.is_confidential = 0
            doc.set("allowed_roles", [])
    except Exception as e:
        debug_log(f"Error setting Work Order {doc.name} confidentiality from BOM {doc.bom_no}: {str(e)}")