# Copyright (c) 2023, Your Organization and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
import os
import logging
from confidential_app.confidential_app.doctype.confidential_settings.confidential_settings import add_debug_log, get_settings
from confidential_app.config.settings import (
    DEBUG_MODE, 
    PERMISSION_CACHE_TIMEOUT,
    ADMIN_ROLES,
    MANAGED_DOCTYPES,
    is_enabled
)

# Environment variable to control debug logging
DEBUG_ENABLED = DEBUG_MODE

# Structured debug logging
def debug_log(message):
    """Write to a log file to debug permission issues, controlled by environment variable"""
    if not DEBUG_ENABLED:
        return
        
    try:
        log_file = '/home/ubuntu/frappe-bench/logs/conf_perm_debug.log'
        logging.basicConfig(filename=log_file, level=logging.DEBUG, 
                           format='%(asctime)s - %(levelname)s - %(message)s')
        logging.debug(message)
    except Exception:
        # Silent fail if logging fails
        pass

# Permission check base function to reduce code duplication
def has_doctype_permission(doctype, doc, user=None, permission_type=None):
    """Base permission check function for confidential doctypes"""
    # First check if confidential protection is enabled
    if not is_enabled():
        return None
    
    if permission_type == "create" and (isinstance(doc, str) or doc.is_new()):
        return None  # Return None to use standard permission system for creation
        
    user = user or frappe.session.user
    debug_log(f"{doctype} PERMISSION CHECK: user={user}, doc={doc.name if hasattr(doc, 'name') else doc}")
    
    # Admin roles bypass
    user_roles = frappe.get_roles(user)
    if any(role in ADMIN_ROLES for role in user_roles):
        debug_log(f"  ALLOW: Admin access for {user}")
        return True
    
    # If we can't identify the document, allow standard permissions (likely a new document)
    doc_name = None
    if hasattr(doc, 'name') and doc.name:
        doc_name = doc.name
    elif isinstance(doc, str) and doc:
        doc_name = doc

    # If document name is still not known (likely a new doc), allow creation
    if not doc_name:
        debug_log(f"  ALLOW: New {doctype} document creation - skipping confidential check")
        return None
    
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
        frappe.log_error(f"Error checking confidentiality of {doctype} {doc_name}: {str(e)}", 
                        f"Confidential {doctype} Permission Error")
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
        frappe.log_error(f"Error checking roles for {doctype} {doc_name}: {str(e)}", 
                        f"Confidential {doctype} Permission Error")
        return False

# Permission check function for BOM
def has_bom_permission(doc, user=None, permission_type=None):
    """Check if user has permission to access BOM"""
    
    return has_doctype_permission("BOM", doc, user, permission_type)

# Permission check function for Stock Entry
def has_stock_entry_permission(doc, user=None, permission_type=None):
    """Check if user has permission to access Stock Entry"""
    return has_doctype_permission("Stock Entry", doc, user, permission_type)

# Permission check function for Work Order
def has_work_order_permission(doc, user=None, permission_type=None):
    """Check if user has permission to access Work Order"""
    return has_doctype_permission("Work Order", doc, user, permission_type)

# List view filtering base function
def get_permission_query_conditions(doctype, user):
    """Base function to filter confidential documents in list view"""
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
        # Escape the roles as SQL parameters
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
    return get_permission_query_conditions("BOM", user)

# List view filtering for Stock Entry
def get_stock_entry_permission_query_conditions(user):
    """Filter confidential Stock Entries in list view"""
    return get_permission_query_conditions("Stock Entry", user)

# List view filtering for Work Order
def get_work_order_permission_query_conditions(user):
    """Filter confidential Work Orders in list view"""
    return get_permission_query_conditions("Work Order", user)

# Add caching for permission checks
_permission_cache = {}
_cache_timeout = PERMISSION_CACHE_TIMEOUT  # Default from settings

def clear_permission_cache():
    """Clear the permission cache"""
    global _permission_cache
    _permission_cache = {}
    debug_log("Permission cache cleared")

@frappe.whitelist()
def check_bom_permission(bom):
    """
    Check if the current user has permission to access the specified BOM.
    Returns True if the user has permission, False otherwise.
    Uses caching to improve performance.
    """
    # First check if confidential protection is enabled
    if not is_enabled():
        return True
        
    user = frappe.session.user
    cache_key = f"bom_perm:{bom}:{user}"
    
    # Check if result is in cache
    if cache_key in _permission_cache:
        from time import time
        cache_time, result = _permission_cache[cache_key]
        
        # Check if cache entry is still valid
        if time() - cache_time < _cache_timeout:
            debug_log(f"BOM {bom} permission from cache: {result}")
            return result
    
    debug_log(f"BOM PERMISSION CHECK: bom={bom}, user={user}")
    
    # First check if this BOM is confidential
    is_confidential = frappe.db.get_value("BOM", bom, "is_confidential")
    
    if not is_confidential:
        debug_log(f"BOM {bom} is not confidential, permission granted")
        result = True
    else:
        debug_log(f"BOM {bom} is confidential, checking permissions")
        
        # Admin roles always have access
        user_roles = set(frappe.get_roles(user))
        if any(role in ADMIN_ROLES for role in user_roles):
            debug_log(f"Admin access granted for BOM {bom}")
            result = True
        else:
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
                result = False
            else:
                # Check if user has any of the allowed roles
                for role in user_roles:
                    if role in allowed_role_names:
                        debug_log(f"User has required role {role} for BOM {bom}")
                        result = True
                        break
                else:
                    debug_log(f"User lacks required roles for BOM {bom}")
                    result = False
    
    # Cache the result
    from time import time
    _permission_cache[cache_key] = (time(), result)
    
    return result

# Stock Entry submission permission check with improved error handling
@frappe.whitelist()
def has_stock_entry_submit_permission(doc, user=None, permission_type=None):
    """
    Check if user has permission to access a Stock Entry.
    This is an enhanced version that specially handles manufacturing scenarios.
    """
    # First check if confidential protection is enabled
    if not is_enabled():
        return None
        
    user = user or frappe.session.user
    debug_log(f"STOCK ENTRY PERMISSION CHECK: SE={doc.name if hasattr(doc, 'name') else doc}, user={user}, type={permission_type}")
    
    # Admin roles always have permission
    user_roles = frappe.get_roles(user)
    if any(role in ADMIN_ROLES for role in user_roles):
        debug_log(f"  ALLOW: Admin access for {user}")
        return True
    
    try:
        # Get Stock Entry doc if string name was provided
        if isinstance(doc, str):
            try:
                doc = frappe.get_doc("Stock Entry", doc)
            except frappe.DoesNotExistError:
                debug_log(f"  ERROR: Stock Entry {doc} does not exist")
                frappe.log_error(f"Stock Entry {doc} does not exist during permission check", 
                                "Stock Entry Permission Error")
                return False
        
        # Check if the is_confidential field exists, if not default to False
        is_confidential = getattr(doc, 'is_confidential', 0)
        
        # If it's not confidential, standard permissions apply
        if not is_confidential:
            debug_log(f"  STANDARD: Stock Entry {doc.name} not confidential")
            return None
        
        # Special handling for BOM-related operations
        if doc.bom_no and (doc.purpose == "Manufacture" or doc.purpose == "Material Transfer for Manufacture"):
            # Cache the BOM permission result to improve performance
            if has_bom_permission(doc.bom_no, user):
                debug_log(f"  ALLOW: User has access to BOM {doc.bom_no}")
                return True
        
        # Otherwise fall back to standard role-based permission check
        return has_stock_entry_permission(doc, user, permission_type)
        
    except Exception as e:
        debug_log(f"  ERROR checking Stock Entry permission: {str(e)}")
        frappe.log_error(f"Error checking permission for Stock Entry {doc if isinstance(doc, str) else doc.name}: {str(e)}", 
                        "Stock Entry Permission Error")
        # In case of error, deny access by default for security
        return False