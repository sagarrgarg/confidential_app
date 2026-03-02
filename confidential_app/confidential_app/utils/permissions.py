import frappe
from frappe import _
from frappe.utils import getdate, today
from confidential_app.config.settings import (
	ADMIN_ROLES,
	MANAGED_DOCTYPES,
)


def debug_log(message):
	"""Write debug log if debug mode is enabled in Confidential Settings."""
	try:
		from confidential_app.confidential_app.doctype.confidential_settings.confidential_settings import (
			add_debug_log,
		)
		add_debug_log(message)
	except Exception:
		pass


def _is_protection_enabled():
	"""Check if confidential protection is globally enabled."""
	try:
		from confidential_app.confidential_app.doctype.confidential_settings.confidential_settings import (
			get_settings,
		)
		settings = get_settings()
		return bool(settings.get("enable_confidential_protection"))
	except Exception:
		return True


def _is_admin(user):
	"""Check if user has an admin role that bypasses confidential checks."""
	user_roles = frappe.get_roles(user)
	return any(role in ADMIN_ROLES for role in user_roles)


def _get_allowed_roles(doctype, doc_name):
	"""Get allowed roles for a confidential document from the child table."""
	return frappe.db.sql(
		"""
		SELECT role FROM `tabConfidential Role Mapping`
		WHERE parent=%s AND parenttype=%s AND parentfield='allowed_roles'
		""",
		(doc_name, doctype),
		as_dict=True,
	)


def _get_allowed_users(doctype, doc_name):
	"""Get allowed users for a confidential document with time-bound filtering."""
	users = frappe.db.sql(
		"""
		SELECT user, valid_from, valid_until
		FROM `tabConfidential User Mapping`
		WHERE parent=%s AND parenttype=%s AND parentfield='allowed_users'
		""",
		(doc_name, doctype),
		as_dict=True,
	)
	current_date = getdate(today())
	active_users = []
	for u in users:
		if u.valid_from and getdate(u.valid_from) > current_date:
			continue
		if u.valid_until and getdate(u.valid_until) < current_date:
			continue
		active_users.append(u.user)
	return active_users


def _check_sub_bom_confidentiality(bom_name, user, checked=None):
	"""
	Recursively check if any sub-BOM in the BOM tree is confidential
	and the user lacks access. Returns True if user has access to all sub-BOMs.
	"""
	if checked is None:
		checked = set()

	if bom_name in checked:
		return True
	checked.add(bom_name)

	sub_boms = frappe.db.sql(
		"""
		SELECT bom_no FROM `tabBOM Item`
		WHERE parent=%s AND bom_no IS NOT NULL AND bom_no != ''
		""",
		bom_name,
		as_dict=True,
	)

	for row in sub_boms:
		sub_bom = row.bom_no
		is_confidential = frappe.db.get_value("BOM", sub_bom, "is_confidential")
		if is_confidential:
			if not _user_has_doc_access("BOM", sub_bom, user):
				debug_log(f"Sub-BOM cascade DENY: user={user} lacks access to sub-BOM {sub_bom}")
				return False

		if not _check_sub_bom_confidentiality(sub_bom, user, checked):
			return False

	return True


def _user_has_doc_access(doctype, doc_name, user):
	"""
	Core access check: does user have role-level or user-level access
	to a specific confidential document?
	"""
	user_roles = set(frappe.get_roles(user))
	allowed_roles = _get_allowed_roles(doctype, doc_name)
	allowed_role_names = {r.role for r in allowed_roles}

	if allowed_role_names & user_roles:
		return True

	allowed_users = _get_allowed_users(doctype, doc_name)
	if user in allowed_users:
		return True

	return False


def _log_access(user, access_type, doctype, doc_name, details=None):
	"""Create an audit trail entry."""
	try:
		from confidential_app.confidential_app.doctype.confidential_access_log.confidential_access_log import (
			log_access,
		)
		log_access(user, access_type, doctype, doc_name, details)
	except Exception:
		pass


# ---------------------------------------------------------------------------
# has_permission hooks
# ---------------------------------------------------------------------------

def has_doctype_permission(doctype, doc, user=None, permission_type=None):
	"""Base permission check for confidential doctypes."""
	if not _is_protection_enabled():
		return None

	if permission_type == "create" and (isinstance(doc, str) or doc.is_new()):
		return None

	user = user or frappe.session.user

	if _is_admin(user):
		return True

	doc_name = None
	if hasattr(doc, "name") and doc.name:
		doc_name = doc.name
	elif isinstance(doc, str) and doc:
		doc_name = doc

	if not doc_name:
		return None

	try:
		is_confidential = None
		if hasattr(doc, "is_confidential"):
			is_confidential = doc.is_confidential
		else:
			is_confidential = frappe.db.get_value(doctype, doc_name, "is_confidential")

		if not is_confidential:
			return None
	except Exception as e:
		debug_log(f"ERROR checking confidentiality for {doctype} {doc_name}: {e}")
		frappe.log_error(
			f"Error checking confidentiality of {doctype} {doc_name}: {e}",
			f"Confidential {doctype} Permission Error",
		)
		return False

	if _user_has_doc_access(doctype, doc_name, user):
		debug_log(f"ALLOW: {user} has access to {doctype} {doc_name}")
		_log_access(user, "View", doctype, doc_name)
		return True

	# Sub-assembly cascade: for BOM, also check sub-BOMs
	if doctype == "BOM":
		if not _check_sub_bom_confidentiality(doc_name, user):
			debug_log(f"DENY: {user} lacks sub-BOM access for {doc_name}")
			_log_access(user, "Denied", doctype, doc_name, "Denied via sub-assembly cascade")
			_notify_denied(user, doctype, doc_name)
			return False

	debug_log(f"DENY: {user} lacks access to {doctype} {doc_name}")
	_log_access(user, "Denied", doctype, doc_name)
	_notify_denied(user, doctype, doc_name)
	return False


def _notify_denied(user, doctype, doc_name):
	"""Fire a notification for access denial (rate-limited per session)."""
	cache_key = f"conf_deny_notified:{user}:{doctype}:{doc_name}"
	if frappe.cache().get_value(cache_key):
		return
	frappe.cache().set_value(cache_key, 1, expires_in_sec=300)

	try:
		from confidential_app.confidential_app.utils.notifications import notify_access_denied
		notify_access_denied(user, doctype, doc_name)
	except Exception:
		pass


def has_bom_permission(doc, user=None, permission_type=None):
	"""Check if user has permission to access a BOM."""
	return has_doctype_permission("BOM", doc, user, permission_type)


def has_stock_entry_permission(doc, user=None, permission_type=None):
	"""Check if user has permission to access a Stock Entry."""
	return has_doctype_permission("Stock Entry", doc, user, permission_type)


def has_work_order_permission(doc, user=None, permission_type=None):
	"""Check if user has permission to access a Work Order."""
	return has_doctype_permission("Work Order", doc, user, permission_type)


def has_stock_entry_submit_permission(doc, user=None, permission_type=None):
	"""
	Enhanced permission check for Stock Entry that handles manufacturing scenarios.
	Registered as the has_permission hook in hooks.py.
	"""
	if not _is_protection_enabled():
		return None

	user = user or frappe.session.user

	if _is_admin(user):
		return True

	try:
		if isinstance(doc, str):
			try:
				doc = frappe.get_doc("Stock Entry", doc)
			except frappe.DoesNotExistError:
				return False

		is_confidential = getattr(doc, "is_confidential", 0)
		if not is_confidential:
			return None

		if doc.bom_no and doc.purpose in ("Manufacture", "Material Transfer for Manufacture"):
			bom_name = doc.bom_no
			if _user_has_doc_access("BOM", bom_name, user):
				_log_access(user, "View", "Stock Entry", doc.name, f"Via BOM {bom_name} access")
				return True

		return has_stock_entry_permission(doc, user, permission_type)

	except Exception as e:
		debug_log(f"ERROR in Stock Entry permission: {e}")
		frappe.log_error(
			f"Error checking permission for Stock Entry: {e}",
			"Stock Entry Permission Error",
		)
		return False


# ---------------------------------------------------------------------------
# permission_query_conditions hooks (list view filtering)
# ---------------------------------------------------------------------------

def get_permission_query_conditions(doctype, user):
	"""Base list-view filter for confidential documents."""
	if not _is_protection_enabled():
		return ""

	if "System Manager" in frappe.get_roles(user):
		return ""

	user_roles = frappe.get_roles(user)

	escaped_roles = ", ".join([frappe.db.escape(r) for r in user_roles])
	escaped_user = frappe.db.escape(user)
	today_str = frappe.db.escape(today())

	condition = (
		f"(`tab{doctype}`.`is_confidential` = 0 "
		f"OR `tab{doctype}`.`is_confidential` IS NULL "
		f"OR (`tab{doctype}`.`is_confidential` = 1 AND ("
		f"EXISTS (SELECT 1 FROM `tabConfidential Role Mapping` "
		f"WHERE `tabConfidential Role Mapping`.`parent` = `tab{doctype}`.`name` "
		f"AND `tabConfidential Role Mapping`.`parenttype` = {frappe.db.escape(doctype)} "
		f"AND `tabConfidential Role Mapping`.`parentfield` = 'allowed_roles' "
		f"AND `tabConfidential Role Mapping`.`role` IN ({escaped_roles})) "
		f"OR EXISTS (SELECT 1 FROM `tabConfidential User Mapping` "
		f"WHERE `tabConfidential User Mapping`.`parent` = `tab{doctype}`.`name` "
		f"AND `tabConfidential User Mapping`.`parenttype` = {frappe.db.escape(doctype)} "
		f"AND `tabConfidential User Mapping`.`parentfield` = 'allowed_users' "
		f"AND `tabConfidential User Mapping`.`user` = {escaped_user} "
		f"AND (`tabConfidential User Mapping`.`valid_from` IS NULL OR `tabConfidential User Mapping`.`valid_from` <= {today_str}) "
		f"AND (`tabConfidential User Mapping`.`valid_until` IS NULL OR `tabConfidential User Mapping`.`valid_until` >= {today_str})"
		f")"
		f")))"
	)

	return condition


def get_bom_permission_query_conditions(user):
	return get_permission_query_conditions("BOM", user)


def get_stock_entry_permission_query_conditions(user):
	return get_permission_query_conditions("Stock Entry", user)


def get_work_order_permission_query_conditions(user):
	return get_permission_query_conditions("Work Order", user)


# ---------------------------------------------------------------------------
# Whitelisted API for client-side permission check
# ---------------------------------------------------------------------------

@frappe.whitelist()
def check_bom_permission(bom):
	"""Client-callable check if current user can access a BOM."""
	if not _is_protection_enabled():
		return True

	user = frappe.session.user
	if _is_admin(user):
		return True

	is_confidential = frappe.db.get_value("BOM", bom, "is_confidential")
	if not is_confidential:
		return True

	return _user_has_doc_access("BOM", bom, user)


def clear_permission_cache():
	"""Clear any permission-related caches."""
	debug_log("Permission cache cleared")


# ---------------------------------------------------------------------------
# Print / Export restriction helpers
# ---------------------------------------------------------------------------

def check_print_permission(doc, method=None):
	"""Block printing of confidential documents for unauthorized users."""
	if not _is_protection_enabled():
		return

	if not getattr(doc, "is_confidential", 0):
		return

	user = frappe.session.user
	if _is_admin(user):
		_log_access(user, "Print", doc.doctype, doc.name)
		return

	if not _user_has_doc_access(doc.doctype, doc.name, user):
		_log_access(user, "Denied", doc.doctype, doc.name, "Print attempt denied")
		frappe.throw(
			_("You do not have permission to print this confidential document."),
			frappe.PermissionError,
		)

	_log_access(user, "Print", doc.doctype, doc.name)


def check_export_permission(doctype, doc_name):
	"""Check if user can export a confidential document."""
	if not _is_protection_enabled():
		return True

	is_confidential = frappe.db.get_value(doctype, doc_name, "is_confidential")
	if not is_confidential:
		return True

	user = frappe.session.user
	if _is_admin(user):
		_log_access(user, "Export", doctype, doc_name)
		return True

	if not _user_has_doc_access(doctype, doc_name, user):
		_log_access(user, "Denied", doctype, doc_name, "Export attempt denied")
		return False

	_log_access(user, "Export", doctype, doc_name)
	return True
