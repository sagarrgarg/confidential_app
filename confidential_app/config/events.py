import frappe
from frappe import _
from confidential_app.confidential_app.utils.permissions import clear_permission_cache

def on_app_update():
    """Clear permission cache when app is updated"""
    frappe.log_error("Clearing confidentiality permission cache due to app update", 
                   "Confidential App Update")
    clear_permission_cache()

def on_login(login_manager):
    """Clear permission cache when user logs in"""
    clear_permission_cache()
    
def after_migrate():
    """Clear permission cache after migrations"""
    frappe.log_error("Clearing confidentiality permission cache due to migration", 
                   "Confidential App Migration")
    clear_permission_cache()
    
def after_sync_fixtures():
    """Clear permission cache after syncing fixtures"""
    frappe.log_error("Clearing confidentiality permission cache due to fixture sync", 
                   "Confidential App Fixtures")
    clear_permission_cache() 