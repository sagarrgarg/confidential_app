import frappe
from frappe.tests.utils import FrappeTestCase
from confidential_app.confidential_app.utils.permissions import (
	_user_has_doc_access,
	check_export_permission,
)


class TestEdgeCases(FrappeTestCase):
	"""Edge case tests: cancelled docs, empty roles, protection disabled, etc."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._ensure_roles()
		cls._create_test_items()
		cls._create_test_users()

	@classmethod
	def _ensure_roles(cls):
		for role_name in ("Confidential Manager", "Confidential User"):
			if not frappe.db.exists("Role", role_name):
				frappe.get_doc({
					"doctype": "Role",
					"role_name": role_name,
					"desk_access": 1,
				}).insert(ignore_permissions=True)

	@classmethod
	def _create_test_items(cls):
		for item_code in ("EDGE_ITEM_A", "EDGE_ITEM_B"):
			if not frappe.db.exists("Item", item_code):
				frappe.get_doc({
					"doctype": "Item",
					"item_code": item_code,
					"item_name": item_code,
					"item_group": "Products",
					"stock_uom": "Nos",
				}).insert(ignore_permissions=True)

	@classmethod
	def _create_test_users(cls):
		cls.regular_user = "edge_regular@test.local"
		if not frappe.db.exists("User", cls.regular_user):
			frappe.get_doc({
				"doctype": "User",
				"email": cls.regular_user,
				"first_name": "EdgeRegular",
				"send_welcome_email": 0,
				"roles": [{"role": "Manufacturing User"}, {"role": "Stock User"}],
			}).insert(ignore_permissions=True)
		frappe.db.commit()

	def _set_protection(self, enabled=True):
		settings = frappe.get_single("Confidential Settings")
		settings.enable_confidential_protection = 1 if enabled else 0
		settings.enable_audit_trail = 0
		settings.enable_access_notifications = 0
		settings.save(ignore_permissions=True)
		frappe.db.commit()

	def _create_confidential_bom(self, roles=None, users=None):
		bom = frappe.get_doc({
			"doctype": "BOM",
			"item": "EDGE_ITEM_A",
			"quantity": 1,
			"is_active": 1,
			"is_confidential": 1,
			"items": [{"item_code": "EDGE_ITEM_B", "qty": 1, "uom": "Nos", "rate": 100}],
		})
		for role in (roles or ["Confidential Manager"]):
			bom.append("allowed_roles", {"role": role})
		for u in (users or []):
			bom.append("allowed_users", {"user": u})
		bom.insert(ignore_permissions=True)
		frappe.db.commit()
		return bom

	# -----------------------------------------------------------------------
	# Protection disabled
	# -----------------------------------------------------------------------

	def test_protection_disabled_allows_access(self):
		self._set_protection(enabled=False)
		bom = self._create_confidential_bom()

		from confidential_app.confidential_app.utils.permissions import has_bom_permission
		result = has_bom_permission(bom, user=self.regular_user)
		self.assertIsNone(result)

		self._set_protection(enabled=True)

	# -----------------------------------------------------------------------
	# Empty roles - confidential doc with no roles should deny
	# -----------------------------------------------------------------------

	def test_confidential_no_roles_no_users_denied(self):
		bom = frappe.get_doc({
			"doctype": "BOM",
			"item": "EDGE_ITEM_A",
			"quantity": 1,
			"is_active": 1,
			"is_confidential": 1,
			"items": [{"item_code": "EDGE_ITEM_B", "qty": 1, "uom": "Nos", "rate": 100}],
		})
		bom.insert(ignore_permissions=True)
		frappe.db.commit()

		self._set_protection(enabled=True)
		self.assertFalse(_user_has_doc_access("BOM", bom.name, self.regular_user))

	# -----------------------------------------------------------------------
	# Export restriction
	# -----------------------------------------------------------------------

	def test_export_denied_for_unauthorized(self):
		self._set_protection(enabled=True)
		bom = self._create_confidential_bom()
		result = check_export_permission("BOM", bom.name)
		# Running as Administrator, should be allowed
		self.assertTrue(result)

	def test_export_denied_regular_user(self):
		self._set_protection(enabled=True)
		bom = self._create_confidential_bom()
		frappe.set_user(self.regular_user)
		try:
			result = check_export_permission("BOM", bom.name)
			self.assertFalse(result)
		finally:
			frappe.set_user("Administrator")

	# -----------------------------------------------------------------------
	# Access request
	# -----------------------------------------------------------------------

	def test_access_request_creation(self):
		self._set_protection(enabled=True)
		bom = self._create_confidential_bom()

		req = frappe.get_doc({
			"doctype": "Confidential Access Request",
			"user": self.regular_user,
			"reference_doctype": "BOM",
			"reference_name": bom.name,
			"reason": "I need to review this BOM for production planning",
			"access_type": "View",
		})
		req.insert(ignore_permissions=True)
		frappe.db.commit()

		self.assertEqual(req.status, "Pending")

	def test_access_request_duplicate_blocked(self):
		self._set_protection(enabled=True)
		bom = self._create_confidential_bom()

		req1 = frappe.get_doc({
			"doctype": "Confidential Access Request",
			"user": self.regular_user,
			"reference_doctype": "BOM",
			"reference_name": bom.name,
			"reason": "First request",
			"access_type": "View",
		})
		req1.insert(ignore_permissions=True)
		frappe.db.commit()

		req2 = frappe.get_doc({
			"doctype": "Confidential Access Request",
			"user": self.regular_user,
			"reference_doctype": "BOM",
			"reference_name": bom.name,
			"reason": "Duplicate request",
			"access_type": "View",
		})
		self.assertRaises(frappe.ValidationError, req2.insert, ignore_permissions=True)

	def test_access_request_approve_grants_access(self):
		self._set_protection(enabled=True)
		bom = self._create_confidential_bom()

		req = frappe.get_doc({
			"doctype": "Confidential Access Request",
			"user": self.regular_user,
			"reference_doctype": "BOM",
			"reference_name": bom.name,
			"reason": "I need access for review",
			"access_type": "View",
		})
		req.insert(ignore_permissions=True)
		frappe.db.commit()

		self.assertFalse(_user_has_doc_access("BOM", bom.name, self.regular_user))

		req.approve(response_note="Approved for review")
		frappe.db.commit()

		self.assertEqual(req.status, "Approved")
		self.assertTrue(_user_has_doc_access("BOM", bom.name, self.regular_user))

	def test_access_request_non_confidential_rejected(self):
		bom = frappe.get_doc({
			"doctype": "BOM",
			"item": "EDGE_ITEM_A",
			"quantity": 1,
			"is_active": 1,
			"is_confidential": 0,
			"items": [{"item_code": "EDGE_ITEM_B", "qty": 1, "uom": "Nos", "rate": 100}],
		})
		bom.insert(ignore_permissions=True)
		frappe.db.commit()

		req = frappe.get_doc({
			"doctype": "Confidential Access Request",
			"user": self.regular_user,
			"reference_doctype": "BOM",
			"reference_name": bom.name,
			"reason": "Shouldn't work",
			"access_type": "View",
		})
		self.assertRaises(frappe.ValidationError, req.insert, ignore_permissions=True)
