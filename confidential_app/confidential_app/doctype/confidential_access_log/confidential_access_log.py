import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class ConfidentialAccessLog(Document):
	def before_insert(self):
		if not self.timestamp:
			self.timestamp = now_datetime()
		if not self.ip_address:
			self.ip_address = frappe.local.request_ip if hasattr(frappe.local, "request_ip") else ""


def log_access(user, access_type, reference_doctype, reference_name, details=None):
	"""Create an audit log entry for confidential document access."""
	try:
		log = frappe.get_doc({
			"doctype": "Confidential Access Log",
			"user": user,
			"access_type": access_type,
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"details": details,
			"timestamp": now_datetime(),
			"ip_address": frappe.local.request_ip if hasattr(frappe.local, "request_ip") else "",
		})
		log.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error("Failed to create Confidential Access Log", frappe.get_traceback())
