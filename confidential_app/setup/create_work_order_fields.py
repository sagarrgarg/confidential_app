import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def execute():
    """Create Work Order custom fields"""
    print("Creating custom fields for Work Order...")
    
    work_order_fields = {
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
    
    create_custom_fields(work_order_fields)
    print("Custom fields for Work Order created successfully!")
    
    # Update any existing Work Orders associated with confidential BOMs
    print("Updating existing Work Orders linked to confidential BOMs...")
    
    # Find all confidential BOMs
    confidential_boms = frappe.get_all(
        "BOM",
        filters={"is_confidential": 1},
        fields=["name"]
    )
    
    if not confidential_boms:
        print("No confidential BOMs found.")
        return
    
    bom_names = [b.name for b in confidential_boms]
    
    # Find all Work Orders linked to confidential BOMs
    work_orders = frappe.get_all(
        "Work Order",
        filters={"bom_no": ["in", bom_names]},
        fields=["name", "bom_no"]
    )
    
    if not work_orders:
        print("No Work Orders found linked to confidential BOMs.")
        return
    
    count = 0
    for wo in work_orders:
        try:
            # Get BOM allowed roles
            bom = frappe.get_doc("BOM", wo.bom_no)
            
            # Update Work Order
            work_order = frappe.get_doc("Work Order", wo.name)
            work_order.is_confidential = 1
            
            # Clear existing roles
            work_order.set("allowed_roles", [])
            
            # Copy roles from BOM
            for bom_role in bom.get("allowed_roles", []):
                work_order.append("allowed_roles", {"role": bom_role.role})
            
            work_order.flags.ignore_permissions = True
            work_order.save()
            count += 1
            
            print(f"Updated Work Order {wo.name} based on BOM {wo.bom_no}")
        except Exception as e:
            print(f"Error updating Work Order {wo.name}: {str(e)}")
    
    print(f"Updated {count} Work Orders successfully.")

if __name__ == "__main__":
    execute() 