import frappe
import json
from frappe.model.document import Document
from frappe.utils import now

CONFIDENTIAL_SETTINGS_CACHE_KEY = "confidential_settings_v2"


class ConfidentialSettings(Document):
	def validate(self):
		if not self.debug_mode and self.debug_logs:
			self.debug_logs = ""

	def on_update(self):
		frappe.cache().delete_key(CONFIDENTIAL_SETTINGS_CACHE_KEY)
		add_debug_log("Confidential Settings updated")


def add_debug_log(message, details=None):
	"""Adds a log entry to Confidential Settings if debug mode is enabled."""
	try:
		settings = get_settings()
		if not settings or not settings.get("debug_mode"):
			return

		settings_doc = frappe.get_single("Confidential Settings")
		if not settings_doc.debug_mode:
			return

		log_entry = f"{now()}: {message}"
		if details:
			try:
				log_entry += f"\nDetails: {json.dumps(details, indent=2, default=str)}"
			except Exception:
				log_entry += f"\nDetails: {details}"

		new_logs = f"{log_entry}\n---\n{settings_doc.debug_logs or ''}"

		max_log_size = 50 * 1024
		if len(new_logs) > max_log_size:
			new_logs = new_logs[:max_log_size] + "\n... (truncated)"

		frappe.db.set_value(
			"Confidential Settings", "Confidential Settings",
			"debug_logs", new_logs, update_modified=False,
		)
	except Exception as e:
		pass


def get_settings():
	"""Get the current Confidential Settings with caching and fallback."""
	settings = frappe.cache().get_value(CONFIDENTIAL_SETTINGS_CACHE_KEY)
	if settings:
		return settings

	try:
		db_settings = frappe.db.get_singles_dict("Confidential Settings")

		settings = {
			"enable_confidential_protection": int(db_settings.get("enable_confidential_protection", 1)),
			"protect_bom": int(db_settings.get("protect_bom", 1)),
			"protect_stock_entry": int(db_settings.get("protect_stock_entry", 1)),
			"protect_work_order": int(db_settings.get("protect_work_order", 1)),
			"restrict_print": int(db_settings.get("restrict_print", 1)),
			"restrict_export": int(db_settings.get("restrict_export", 1)),
			"enable_audit_trail": int(db_settings.get("enable_audit_trail", 1)),
			"enable_access_notifications": int(db_settings.get("enable_access_notifications", 1)),
			"debug_mode": int(db_settings.get("debug_mode", 0)),
		}

		frappe.cache().set_value(CONFIDENTIAL_SETTINGS_CACHE_KEY, settings)
		return settings

	except Exception:
		return {
			"enable_confidential_protection": 0,
			"protect_bom": 0,
			"protect_stock_entry": 0,
			"protect_work_order": 0,
			"restrict_print": 0,
			"restrict_export": 0,
			"enable_audit_trail": 0,
			"enable_access_notifications": 0,
			"debug_mode": 0,
		}


def is_protection_enabled(doctype="BOM"):
	"""Check if confidential protection is enabled for a specific doctype."""
	settings = get_settings()
	if not settings.get("enable_confidential_protection"):
		return False

	doctype_map = {
		"BOM": "protect_bom",
		"Stock Entry": "protect_stock_entry",
		"Work Order": "protect_work_order",
	}
	key = doctype_map.get(doctype)
	if key:
		return bool(settings.get(key, 1))
	return False
