import frappe
from frappe import _
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
from confidential_app.confidential_app.utils.permissions import debug_log, has_bom_permission

class StockEntryOverride(StockEntry):
    @frappe.whitelist()
    def get_items(self):
        # Check if we should skip BOM data processing due to permission issues
        if hasattr(self, 'flags') and getattr(self.flags, 'ignore_bom_data', False):
            debug_log(f"Skipping BOM items fetch for {self.name} due to permission restriction")
            return []
        
        # If we have a BOM, verify permissions first
        if self.bom_no and (self.purpose == "Manufacture" or self.purpose == "Material Transfer for Manufacture"):
            try:
                # Check BOM permission - this will throw an error if no permission
                if not has_bom_permission(self.bom_no):
                    debug_log(f"No permission to access BOM {self.bom_no} for stock entry {self.name}")
                    self.flags.ignore_bom_data = True
                    return []
            except frappe.PermissionError:
                debug_log(f"Permission error accessing BOM {self.bom_no}")
                self.flags.ignore_bom_data = True
                return []
        
        # Call the original method if no permission issues
        return super(StockEntryOverride, self).get_items() 