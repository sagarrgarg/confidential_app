# Copyright (c) 2023, Your Organization and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from confidential_app.confidential_app.doctype.confidential_settings.confidential_settings import add_debug_log, get_settings

# Alias the add_debug_log function for backward compatibility
debug_log = add_debug_log

def _has_document_permission(doctype, doc, user=None, permission_type=None):
    """Generic permission check for confidential documents"""
    user = user or frappe.session.user
    debug_log(f"{doctype} PERMISSION CHECK: user={user}, doc={doc.name if hasattr(doc, 'name') else doc}")
    
    # System Manager bypass
    if "System Manager" in frappe.get_roles(user):
        debug_log(f"  ALLOW: SysAdmin access for {user}")
        return True
    
    # If we can't identify the document, deny access
    doc_name = doc.name if hasattr(doc, 'name') else (doc if isinstance(doc, str) else None)
    if not doc_name:
        debug_log(f"  DENY: Cannot identify {doctype} document")
        return False
    
    # Check if document is confidential
    try:
        is_confidential = None
        if hasattr(doc, 'is_confidential'):
            is_confidential = doc.is_confidential
        else:
            is_confidential = frappe.db.get_value(doctype, doc_name, "is_confidential")
        
        debug_log(f"  Doc {doc_name} is_confidential: {is_confidential}")
        
        # If not confidential, standard permissions apply
        if not is_confidential:
            debug_log(f"  STANDARD: Not confidential, using standard permissions")
            return None
    except Exception as e:
        debug_log(f"  ERROR checking confidentiality: {str(e)}")
        return False
    
    # Document IS confidential - check user's roles against the allowed roles
    user_roles = frappe.get_roles(user)
    debug_log(f"  User roles: {user_roles}")
    
    # Get allowed roles directly from database to avoid any child table issues
    try:
        # This approach directly queries the child table to get the roles
        allowed_roles = frappe.db.sql("""
            SELECT role FROM `tabConfidential Role Mapping`
            WHERE parent=%s AND parenttype=%s AND parentfield='allowed_roles'
        """, (doc_name, doctype), as_dict=True)
        
        allowed_role_names = [r.role for r in allowed_roles]
        debug_log(f"  Allowed roles: {allowed_role_names}")
        
        # If no roles specified, deny access to confidential document
        if not allowed_role_names:
            debug_log(f"  DENY: No allowed roles specified for confidential doc")
            return False
            
        # Check if user has any of the allowed roles
        for role in user_roles:
            if role in allowed_role_names:
                debug_log(f"  ALLOW: User has required role {role}")
                return True
        
        # User doesn't have any of the allowed roles
        debug_log(f"  DENY: User lacks required roles")
        return False
    except Exception as e:
        debug_log(f"  ERROR during role check: {str(e)}")
        return False

# Permission check function for BOM
def has_bom_permission(doc, user=None, permission_type=None):
    """Check if user has permission to access BOM"""
    return _has_document_permission("BOM", doc, user, permission_type)

# Permission check function for Stock Entry
def has_stock_entry_permission(doc, user=None, permission_type=None):
    """Check if user has permission to access Stock Entry"""
    return _has_document_permission("Stock Entry", doc, user, permission_type)

def _get_permission_query_conditions(doctype, user):
    """Generic function to filter confidential documents in list view"""
    debug_log(f"LIST VIEW FILTER for {doctype}: user={user}")
    
    # System Manager can see all documents
    if "System Manager" in frappe.get_roles(user):
        debug_log(f"  LIST VIEW: Showing all {doctype}s for SysAdmin")
        return ""
    
    # Get all the user's roles
    user_roles = frappe.get_roles(user)
    debug_log(f"  LIST VIEW: User roles: {user_roles}")
    
    # Construct a query that shows:
    # 1. All non-confidential documents
    # 2. Confidential documents where the user has at least one of the allowed roles
    
    # First, include all non-confidential documents
    condition = f"(`tab{doctype}`.`is_confidential` = 0 OR `tab{doctype}`.`is_confidential` IS NULL"
    
    # Only proceed with role check if user has any roles to check
    if user_roles:
        # Then include confidential documents where user has an allowed role
        # IMPORTANT: We need to escape the roles as SQL parameters
        placeholders = ', '.join(['"' + role.replace('"', '""') + '"' for role in user_roles])
        
        roles_condition = f" OR (`tab{doctype}`.`is_confidential` = 1 AND EXISTS (SELECT 1 FROM `tabConfidential Role Mapping` \
            WHERE `tabConfidential Role Mapping`.`parent` = `tab{doctype}`.`name` \
            AND `tabConfidential Role Mapping`.`parenttype` = '{doctype}' \
            AND `tabConfidential Role Mapping`.`parentfield` = 'allowed_roles' \
            AND `tabConfidential Role Mapping`.`role` IN ({placeholders})))"
        
        # Close the parenthesis from the first condition
        condition += roles_condition
    
    condition += ")"
    
    debug_log(f"  LIST VIEW: {doctype} filter condition: {condition}")
    return condition

# List view filtering for BOM
def get_bom_permission_query_conditions(user):
    """Filter confidential BOMs in list view"""
    return _get_permission_query_conditions("BOM", user)

# List view filtering for Stock Entry
def get_stock_entry_permission_query_conditions(user):
    """Filter confidential Stock Entries in list view"""
    return _get_permission_query_conditions("Stock Entry", user)

# Simple permission check function for BOM
@frappe.whitelist()
def check_bom_permission(bom):
    """
    Check if the current user has permission to access the specified BOM.
    Returns True if the user has permission, False otherwise.
    """
    return has_bom_permission(bom)