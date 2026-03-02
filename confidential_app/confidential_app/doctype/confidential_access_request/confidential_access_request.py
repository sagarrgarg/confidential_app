import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, getdate, today


class ConfidentialAccessRequest(Document):
	def validate(self):
		self._validate_reference()
		self._validate_duplicate()

	def _validate_reference(self):
		if self.reference_doctype not in ("BOM", "Stock Entry", "Work Order"):
			frappe.throw(_("Access requests are only supported for BOM, Stock Entry, and Work Order."))

		is_confidential = frappe.db.get_value(
			self.reference_doctype, self.reference_name, "is_confidential"
		)
		if not is_confidential:
			frappe.throw(_("The referenced document is not marked as confidential."))

	def _validate_duplicate(self):
		if self.is_new():
			existing = frappe.db.exists(
				"Confidential Access Request",
				{
					"user": self.user,
					"reference_doctype": self.reference_doctype,
					"reference_name": self.reference_name,
					"status": "Pending",
					"name": ("!=", self.name or ""),
				},
			)
			if existing:
				frappe.throw(_("A pending access request already exists for this user and document."))

	@frappe.whitelist()
	def approve(self, response_note=None):
		if "System Manager" not in frappe.get_roles() and "Confidential Manager" not in frappe.get_roles():
			frappe.throw(_("Only System Manager or Confidential Manager can approve requests."),
				frappe.PermissionError)

		self.status = "Approved"
		self.approved_by = frappe.session.user
		self.responded_on = now_datetime()
		if response_note:
			self.response_note = response_note
		self.save(ignore_permissions=True)

		self._grant_access()

		from confidential_app.confidential_app.utils.notifications import notify_access_request_response
		notify_access_request_response(self)

	@frappe.whitelist()
	def reject(self, response_note=None):
		if "System Manager" not in frappe.get_roles() and "Confidential Manager" not in frappe.get_roles():
			frappe.throw(_("Only System Manager or Confidential Manager can reject requests."),
				frappe.PermissionError)

		self.status = "Rejected"
		self.approved_by = frappe.session.user
		self.responded_on = now_datetime()
		if response_note:
			self.response_note = response_note
		self.save(ignore_permissions=True)

		from confidential_app.confidential_app.utils.notifications import notify_access_request_response
		notify_access_request_response(self)

	def _grant_access(self):
		"""Add the requesting user to the document's allowed_users list."""
		doc = frappe.get_doc(self.reference_doctype, self.reference_name)

		existing_users = [d.user for d in doc.get("allowed_users", [])]
		if self.user not in existing_users:
			doc.append("allowed_users", {
				"user": self.user,
				"valid_from": today(),
				"valid_until": self.valid_until,
			})
			doc.flags.ignore_permissions = True
			doc.save()

		from confidential_app.confidential_app.doctype.confidential_access_log.confidential_access_log import log_access
		log_access(
			user=frappe.session.user,
			access_type="Modified",
			reference_doctype=self.reference_doctype,
			reference_name=self.reference_name,
			details=f"Approved access request {self.name} for user {self.user}",
		)
