import frappe
from frappe import _

def after_install():
    """
    Set up roles and permissions after app installation
    """
    setup_roles()
    setup_role_permissions()

def setup_roles():
    """
    Create the necessary roles if they don't exist
    """
    # Create Confidential Manager role
    if not frappe.db.exists("Role", "Confidential Manager"):
        frappe.get_doc({
            "doctype": "Role",
            "role_name": "Confidential Manager",
            "desk_access": 1,
            "search_bar": 1,
            "disabled": 0,
            "is_custom": 1
        }).insert(ignore_permissions=True)
    
    # Create Confidential User role
    if not frappe.db.exists("Role", "Confidential User"):
        frappe.get_doc({
            "doctype": "Role",
            "role_name": "Confidential User",
            "desk_access": 1,
            "search_bar": 1,
            "disabled": 0,
            "is_custom": 1
        }).insert(ignore_permissions=True)

def setup_role_permissions():
    """
    Set up role permissions for pages and reports
    """
    # First, check if Confidential Settings page exists
    if frappe.db.exists("DocType", "Page") and frappe.db.exists("Page", "Confidential Settings"):
        # Add page role
        page_role = frappe.db.get_value("Has Role", {
            "parent": "Confidential Settings",
            "role": "Confidential Manager"
        })
        
        if not page_role:
            # Get the Page doc
            page = frappe.get_doc("Page", "Confidential Settings")
            
            # Add the role
            page.append("roles", {
                "role": "Confidential Manager"
            })
            
            # Save changes
            page.save(ignore_permissions=True)
    
    # Check if Confidential BOM Report exists
    if frappe.db.exists("DocType", "Report") and frappe.db.exists("Report", "Confidential BOM Report"):
        # Add report roles
        report = frappe.get_doc("Report", "Confidential BOM Report")
        
        # Check if roles already exist
        existing_roles = [r.role for r in report.roles]
        
        # Add Confidential Manager role if not present
        if "Confidential Manager" not in existing_roles:
            report.append("roles", {
                "role": "Confidential Manager"
            })
        
        # Add Confidential User role if not present
        if "Confidential User" not in existing_roles:
            report.append("roles", {
                "role": "Confidential User"
            })
        
        # Save changes
        report.save(ignore_permissions=True) 