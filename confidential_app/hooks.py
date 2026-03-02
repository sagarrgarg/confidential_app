app_name = "confidential_app"
app_title = "Confidential App"
app_publisher = "Sagar Ratan Garg"
app_description = "confidential_app"
app_email = "sagar1ratan1garg1@gmail.com"
app_license = "mit"

# include js, css files in header of desk.html
# app_include_css = "/assets/confidential_app/css/confidential_app.css"
app_include_js = "/assets/confidential_app/js/confidential_utils.js"

# include js in doctype views
doctype_js = {
    "BOM": "public/js/bom.js",
    "Stock Entry": "public/js/stock_entry.js",
    "Work Order": "public/js/work_order.js"
}
doctype_list_js = {
    "BOM": "public/js/bom_list.js",
    "Stock Entry": "public/js/stock_entry_list.js",
    "Work Order": "public/js/work_order_list.js"
}

# Fixtures
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["name", "in", [
                "BOM-is_confidential",
                "BOM-allowed_roles",
                "BOM-allowed_users",
                "Stock Entry-is_confidential",
                "Stock Entry-allowed_roles",
                "Stock Entry-allowed_users",
                "Work Order-is_confidential",
                "Work Order-allowed_roles",
                "Work Order-allowed_users"
            ]]
        ]
    },
    {
        "dt": "Role",
        "filters": [
            ["name", "in", ["Confidential Manager", "Confidential User"]]
        ]
    },
    {
        "dt": "DocPerm",
        "filters": [
            ["role", "in", ["Confidential Manager", "Confidential User"]],
            ["parent", "in", ["BOM", "Stock Entry", "Work Order", "Confidential Settings",
                              "Confidential Role Mapping", "Confidential User Mapping",
                              "Confidential Access Log", "Confidential Access Request", "Role"]]
        ]
    }
]

# Permissions
permission_query_conditions = {
    "BOM": "confidential_app.confidential_app.utils.permissions.get_bom_permission_query_conditions",
    "Stock Entry": "confidential_app.confidential_app.utils.permissions.get_stock_entry_permission_query_conditions",
    "Work Order": "confidential_app.confidential_app.utils.permissions.get_work_order_permission_query_conditions"
}

has_permission = {
    "BOM": "confidential_app.confidential_app.utils.permissions.has_bom_permission",
    "Stock Entry": "confidential_app.confidential_app.utils.permissions.has_stock_entry_submit_permission",
    "Work Order": "confidential_app.confidential_app.utils.permissions.has_work_order_permission"
}

# Document Events
doc_events = {
    "BOM": {
        "validate": "confidential_app.confidential_app.utils.validations.validate_bom_permissions_on_save",
        "on_update_after_submit": "confidential_app.confidential_app.utils.validations.update_stock_entries_on_bom_change"
    },
    "Stock Entry": {
        "validate": "confidential_app.confidential_app.utils.validations.validate_stock_entry_permissions_on_save",
        "before_insert": "confidential_app.confidential_app.utils.validations.set_stock_entry_confidentiality"
    },
    "Work Order": {
        "validate": "confidential_app.confidential_app.utils.validations.validate_work_order_permissions_on_save",
        "before_insert": "confidential_app.confidential_app.utils.validations.set_work_order_confidentiality"
    },
    "Confidential Access Request": {
        "after_insert": "confidential_app.confidential_app.utils.notifications.notify_access_request_submitted"
    }
}

# Boot Session
boot_session = "confidential_app.boot.boot_session"

# Apply patches on app init
override_whitelisted_methods = {
    "erpnext.manufacturing.doctype.bom.bom.get_bom_items": "confidential_app.confidential_app.override.bom_override.get_bom_items_with_permission_check"
}

# Clear permission cache on various events
on_app_update = "confidential_app.config.events.on_app_update"
on_login = "confidential_app.config.events.on_login"
after_migrate = "confidential_app.config.events.after_migrate"
after_sync_fixtures = "confidential_app.config.events.after_sync_fixtures"
