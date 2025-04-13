app_name = "confidential_app"
app_title = "Confidential App"
app_publisher = "Sagar Ratan Garg"
app_description = "confidential_app"
app_email = "sagar1ratan1garg1@gmail.com"
app_license = "mit"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/confidential_app/css/confidential_app.css"
# app_include_js = "/assets/confidential_app/js/confidential_app.js"

# include js, css files in header of web template
# web_include_css = "/assets/confidential_app/css/confidential_app.css"
# web_include_js = "/assets/confidential_app/js/confidential_app.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "confidential_app/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "BOM": "public/js/bom.js",
    "Stock Entry": "public/js/stock_entry.js",
    "Work Order": "public/js/work_order.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
doctype_list_js = {
    "BOM": "public/js/bom_list.js",
    "Stock Entry": "public/js/stock_entry_list.js",
    "Work Order": "public/js/work_order_list.js"
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Fixtures
# --------
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["name", "in", [
                "BOM-is_confidential",
                "BOM-allowed_roles",
                "Stock Entry-is_confidential",
                "Stock Entry-allowed_roles",
                "Work Order-is_confidential",
                "Work Order-allowed_roles"
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
            ["parent", "in", ["BOM", "Stock Entry", "Work Order", "Confidential Settings", "Role", "Confidential Role Mapping"]],
            ["role", "in", ["Confidential Manager", "Confidential User"]]
        ]
    }
]

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
#	"methods": "confidential_app.utils.jinja_methods",
#	"filters": "confidential_app.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "confidential_app.install.before_install"
# after_install = "confidential_app.setup.after_install.after_install"

# Uninstallation
# ------------

# before_uninstall = "confidential_app.uninstall.before_uninstall"
# after_uninstall = "confidential_app.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "confidential_app.utils.before_app_install"
# after_app_install = "confidential_app.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "confidential_app.utils.before_app_uninstall"
# after_app_uninstall = "confidential_app.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "confidential_app.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
#	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
permission_query_conditions = {
    "BOM": "confidential_app.confidential_app.utils.permissions.get_bom_permission_query_conditions",
    "Stock Entry": "confidential_app.confidential_app.utils.permissions.get_stock_entry_permission_query_conditions",
    "Work Order": "confidential_app.confidential_app.utils.permissions.get_work_order_permission_query_conditions"
}

# has_permission = {
#	"Event": "frappe.desk.doctype.event.event.has_permission",
# }
has_permission = {
    "BOM": "confidential_app.confidential_app.utils.permissions.has_bom_permission",
    "Stock Entry": "confidential_app.confidential_app.utils.permissions.has_stock_entry_submit_permission",
    "Work Order": "confidential_app.confidential_app.utils.permissions.has_work_order_permission"
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
#	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

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
    }
}

# Boot Session
# -----------
# Make sure our boot.py file is called on server startup
boot_session = "confidential_app.boot.boot_session"

# Apply our monkey patches on app init
after_app_install = "confidential_app.confidential_app.override.bom_override.apply_patches"
after_app_init = "confidential_app.confidential_app.override.bom_override.apply_patches"

# Scheduled Tasks
# ---------------

# scheduler_events = {
#	"all": [
#		"confidential_app.tasks.all"
#	],
#	"daily": [
#		"confidential_app.tasks.daily"
#	],
#	"hourly": [
#		"confidential_app.tasks.hourly"
#	],
#	"weekly": [
#		"confidential_app.tasks.weekly"
#	],
#	"monthly": [
#		"confidential_app.tasks.monthly"
#	],
# }

# Testing
# -------

# before_tests = "confidential_app.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#	"frappe.desk.doctype.event.event.get_events": "confidential_app.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#	"Task": "confidential_app.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["confidential_app.utils.before_request"]
# after_request = ["confidential_app.utils.after_request"]

# Job Events
# ----------
# before_job = ["confidential_app.utils.before_job"]
# after_job = ["confidential_app.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
#	{
#		"doctype": "{doctype_1}",
#		"filter_by": "{filter_by}",
#		"redact_fields": ["{field_1}", "{field_2}"],
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_2}",
#		"filter_by": "{filter_by}",
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_3}",
#		"strict": False,
#	},
#	{
#		"doctype": "{doctype_4}"
#	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#	"confidential_app.auth.validate"
# ]

# Clear permission cache when cache is cleared
on_app_update = "confidential_app.config.events.on_app_update"
on_login = "confidential_app.config.events.on_login"
after_migrate = "confidential_app.config.events.after_migrate"
after_sync_fixtures = "confidential_app.config.events.after_sync_fixtures"