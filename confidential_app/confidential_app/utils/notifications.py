import frappe
from frappe import _


def notify_confidentiality_change(doc, action="marked"):
	"""Notify relevant users when a document's confidentiality status changes."""
	doctype = doc.doctype
	doc_name = doc.name

	if action == "marked":
		subject = _("{0} {1} has been marked as confidential").format(doctype, doc_name)
		message = _("{0} {1} has been marked as confidential by {2}. "
			"Access is now restricted to specified roles and users.").format(
			doctype, doc_name, frappe.session.user
		)
	else:
		subject = _("{0} {1} is no longer confidential").format(doctype, doc_name)
		message = _("{0} {1} has been unmarked as confidential by {2}. "
			"Standard permissions now apply.").format(
			doctype, doc_name, frappe.session.user
		)

	recipients = _get_confidential_managers()

	for user in recipients:
		if user != frappe.session.user:
			_create_notification_log(user, subject, message, doctype, doc_name)


def notify_access_denied(user, doctype, doc_name):
	"""Notify Confidential Managers when access is denied."""
	managers = _get_confidential_managers()
	subject = _("Access denied: {0} tried to access confidential {1} {2}").format(
		user, doctype, doc_name
	)
	message = _("User {0} attempted to access confidential {1} {2} but was denied "
		"because they lack the required roles or user-level access.").format(
		user, doctype, doc_name
	)

	for manager in managers:
		_create_notification_log(manager, subject, message, doctype, doc_name)


def notify_access_request_submitted(request_doc, method=None):
	"""Notify Confidential Managers about a new access request."""
	managers = _get_confidential_managers()
	subject = _("New access request from {0} for {1} {2}").format(
		request_doc.user, request_doc.reference_doctype, request_doc.reference_name
	)
	message = _("User {0} has requested {1} access to confidential {2} {3}.\n"
		"Reason: {4}").format(
		request_doc.user,
		request_doc.access_type,
		request_doc.reference_doctype,
		request_doc.reference_name,
		request_doc.reason,
	)

	for manager in managers:
		_create_notification_log(
			manager, subject, message,
			"Confidential Access Request", request_doc.name,
		)


def notify_access_request_response(request_doc):
	"""Notify the requesting user about the response to their access request."""
	status = request_doc.status
	subject = _("Your access request for {0} {1} has been {2}").format(
		request_doc.reference_doctype, request_doc.reference_name, status.lower()
	)

	if status == "Approved":
		validity = ""
		if request_doc.valid_until:
			validity = _(" Access is valid until {0}.").format(request_doc.valid_until)
		message = _("Your request for {0} access to {1} {2} has been approved by {3}.{4}").format(
			request_doc.access_type,
			request_doc.reference_doctype,
			request_doc.reference_name,
			request_doc.approved_by,
			validity,
		)
	else:
		note = ""
		if request_doc.response_note:
			note = _(" Note: {0}").format(request_doc.response_note)
		message = _("Your request for access to {0} {1} has been rejected by {2}.{3}").format(
			request_doc.reference_doctype,
			request_doc.reference_name,
			request_doc.approved_by,
			note,
		)

	_create_notification_log(
		request_doc.user, subject, message,
		"Confidential Access Request", request_doc.name,
	)


def notify_roles_changed(doc, old_roles, new_roles):
	"""Notify when allowed roles change on a confidential document."""
	added = new_roles - old_roles
	removed = old_roles - new_roles

	if not added and not removed:
		return

	parts = []
	if added:
		parts.append(_("Added: {0}").format(", ".join(added)))
	if removed:
		parts.append(_("Removed: {0}").format(", ".join(removed)))

	subject = _("Access roles changed on confidential {0} {1}").format(doc.doctype, doc.name)
	message = _("The allowed roles for confidential {0} {1} have been updated by {2}. {3}").format(
		doc.doctype, doc.name, frappe.session.user, ". ".join(parts)
	)

	recipients = _get_confidential_managers()
	for user in recipients:
		if user != frappe.session.user:
			_create_notification_log(user, subject, message, doc.doctype, doc.name)


def _get_confidential_managers():
	"""Get all users with the Confidential Manager or System Manager role."""
	users = set()
	for role in ("Confidential Manager", "System Manager"):
		role_users = frappe.get_all(
			"Has Role",
			filters={"role": role, "parenttype": "User"},
			pluck="parent",
		)
		users.update(role_users)

	enabled_users = frappe.get_all(
		"User",
		filters={"name": ("in", list(users)), "enabled": 1},
		pluck="name",
	)
	return enabled_users


def _create_notification_log(user, subject, message, doctype=None, doc_name=None):
	"""Create a notification log entry."""
	try:
		notification = frappe.get_doc({
			"doctype": "Notification Log",
			"for_user": user,
			"from_user": frappe.session.user,
			"subject": subject,
			"type": "Alert",
			"email_content": message,
			"document_type": doctype,
			"document_name": doc_name,
		})
		notification.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error("Failed to create notification", frappe.get_traceback())
