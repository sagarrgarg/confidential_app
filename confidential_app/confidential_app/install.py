import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def after_install():
    create_required_custom_fields()
    
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
    
    # Create the Confidential Settings single doctype record if it doesn't exist
    if not frappe.db.exists("Confidential Settings", "Confidential Settings"):
        settings = frappe.new_doc("Confidential Settings")
        settings.enable_confidential_protection = 1
        settings.protect_bom = 1
        settings.protect_stock_entry = 1
        settings.debug_mode = 0
        settings.insert(ignore_permissions=True)