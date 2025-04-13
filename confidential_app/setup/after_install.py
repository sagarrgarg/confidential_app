import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from confidential_app.confidential_app.utils.permissions import clear_permission_cache

def after_install():
    """
    Function to run after app installation
    Creates required custom fields and configurations
    """
    frappe.log_error("Running Confidential App after_install", "Confidential App Install")
    
    # Create custom fields for BOM, Stock Entry, and Work Order
    create_required_custom_fields()
    
    # Create required roles if they don't exist
    create_roles()
    
    # Clear any permission caches
    clear_permission_cache()
    
    frappe.msgprint(_("Confidential App installed successfully. Custom fields and roles have been created."))

def create_required_custom_fields():
    """Create the custom fields required for the app"""
    custom_fields = {
        "BOM": [
            {
                "fieldname": "is_confidential",
                "label": "Is Confidential",
                "fieldtype": "Check",
                "insert_after": "with_operations",
                "description": "Mark this BOM as confidential - only users with specific roles can access it"
            },
            {
                "fieldname": "allowed_roles",
                "label": "Allowed Roles",
                "fieldtype": "Table MultiSelect",
                "options": "Confidential Role Mapping",
                "insert_after": "is_confidential",
                "depends_on": "eval:doc.is_confidential==1",
                "mandatory_depends_on": "eval:doc.is_confidential==1",
                "description": "Only users with these roles can access this confidential BOM"
            }
        ],
        "Stock Entry": [
            {
                "fieldname": "is_confidential",
                "label": "Is Confidential",
                "fieldtype": "Check",
                "insert_after": "stock_entry_type",
                "description": "This Stock Entry contains confidential information from a confidential BOM",
                "read_only": 1
            },
            {
                "fieldname": "allowed_roles",
                "label": "Allowed Roles",
                "fieldtype": "Table MultiSelect",
                "options": "Confidential Role Mapping",
                "insert_after": "is_confidential",
                "depends_on": "eval:doc.is_confidential==1",
                "read_only": 1,
                "description": "Only users with these roles can access this confidential Stock Entry"
            }
        ],
        "Work Order": [
            {
                "fieldname": "is_confidential",
                "label": "Is Confidential",
                "fieldtype": "Check",
                "insert_after": "bom_no",
                "description": "This Work Order contains confidential information from a confidential BOM",
                "read_only": 1
            },
            {
                "fieldname": "allowed_roles",
                "label": "Allowed Roles",
                "fieldtype": "Table MultiSelect",
                "options": "Confidential Role Mapping",
                "insert_after": "is_confidential",
                "depends_on": "eval:doc.is_confidential==1",
                "read_only": 1,
                "description": "Only users with these roles can access this confidential Work Order"
            }
        ]
    }
    
    create_custom_fields(custom_fields)
    frappe.db.commit()
    
def create_roles():
    """Create the required roles if they don't exist"""
    roles = ["Confidential Manager", "Confidential User"]
    
    for role in roles:
        if not frappe.db.exists("Role", role):
            doc = frappe.new_doc("Role")
            doc.role_name = role
            doc.desk_access = 1
            doc.insert(ignore_permissions=True)
            frappe.db.commit() 